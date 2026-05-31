"""
GPU Resource Scheduler for Model Inference
============================================

Simulates GPU resource scheduling in a multi-tenant AI inference cluster.
Demonstrates production patterns for efficient GPU utilization:

- Bin packing: Fit multiple small models onto shared GPUs
- Priority queues: Serve high-priority requests first
- Multi-tenant allocation: Fair sharing with quotas
- Preemption: Evict low-priority work for urgent requests
- Memory management: Track GPU memory fragmentation
"""

import time
import random
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class Priority(Enum):
    CRITICAL = 0   # Real-time serving, SLA-bound
    HIGH = 1       # Interactive users
    MEDIUM = 2     # Batch predictions
    LOW = 3        # Training, experimentation

    def __lt__(self, other):
        return self.value < other.value


@dataclass
class GPU:
    """Represents a single GPU device."""
    id: str
    total_memory_mb: int = 16384  # 16GB
    used_memory_mb: int = 0
    allocated_models: List[str] = field(default_factory=list)

    @property
    def free_memory_mb(self) -> int:
        return self.total_memory_mb - self.used_memory_mb

    @property
    def utilization(self) -> float:
        return self.used_memory_mb / self.total_memory_mb

    def can_fit(self, memory_mb: int) -> bool:
        return self.free_memory_mb >= memory_mb

    def allocate(self, model_id: str, memory_mb: int) -> bool:
        if not self.can_fit(memory_mb):
            return False
        self.used_memory_mb += memory_mb
        self.allocated_models.append(model_id)
        return True

    def deallocate(self, model_id: str, memory_mb: int):
        self.used_memory_mb = max(0, self.used_memory_mb - memory_mb)
        if model_id in self.allocated_models:
            self.allocated_models.remove(model_id)


@dataclass(order=True)
class InferenceRequest:
    """A request for model inference."""
    priority: Priority = field(compare=True)
    arrival_time: float = field(compare=True)
    request_id: str = field(compare=False)
    tenant_id: str = field(compare=False)
    model_id: str = field(compare=False)
    memory_required_mb: int = field(compare=False)
    compute_time_ms: float = field(compare=False)


@dataclass
class Tenant:
    """Represents a tenant with GPU quota."""
    id: str
    name: str
    gpu_quota_mb: int  # Max GPU memory this tenant can use
    gpu_used_mb: int = 0
    requests_served: int = 0
    requests_queued: int = 0
    requests_preempted: int = 0

    @property
    def quota_remaining_mb(self) -> int:
        return self.gpu_quota_mb - self.gpu_used_mb


class GPUScheduler:
    """
    Schedules inference requests across a GPU cluster.
    
    Implements:
    1. First-Fit Decreasing bin packing for model placement
    2. Priority queue for request ordering
    3. Tenant quotas for fair sharing
    4. Preemption for critical requests
    
    In production, similar to:
    - NVIDIA Triton Inference Server's scheduling
    - Kubernetes GPU device plugin + scheduler extender
    - Ray Serve's replica scheduling
    - AWS SageMaker multi-model endpoints
    """

    def __init__(self, num_gpus: int = 4, gpu_memory_mb: int = 16384):
        self.gpus = [GPU(id=f"gpu-{i}", total_memory_mb=gpu_memory_mb) for i in range(num_gpus)]
        self.request_queue: List[InferenceRequest] = []
        self.tenants: Dict[str, Tenant] = {}
        self.completed_requests: List[Dict] = []
        self.preempted_requests: List[str] = []
        self.total_scheduled = 0
        self.total_rejected = 0

    def register_tenant(self, tenant: Tenant):
        self.tenants[tenant.id] = tenant
        print(f"    Registered tenant: {tenant.name} (quota: {tenant.gpu_quota_mb}MB)")

    def submit_request(self, req: InferenceRequest) -> str:
        """Submit an inference request to the scheduler."""
        # Check tenant quota
        tenant = self.tenants.get(req.tenant_id)
        if tenant and tenant.quota_remaining_mb < req.memory_required_mb:
            self.total_rejected += 1
            return "REJECTED_QUOTA"

        heapq.heappush(self.request_queue, req)
        if tenant:
            tenant.requests_queued += 1
        return "QUEUED"

    def find_gpu_bin_pack(self, memory_mb: int) -> Optional[GPU]:
        """
        First-Fit Decreasing bin packing strategy.
        Find the GPU with the LEAST free space that can still fit this request.
        This minimizes fragmentation by packing GPUs tightly.
        """
        candidates = [g for g in self.gpus if g.can_fit(memory_mb)]
        if not candidates:
            return None
        # Pick the fullest GPU that can fit (best-fit decreasing)
        candidates.sort(key=lambda g: g.free_memory_mb)
        return candidates[0]

    def try_preempt(self, memory_needed: int, priority: Priority) -> Optional[GPU]:
        """
        Try to preempt lower-priority work to make room.
        Only preempts if the incoming request has HIGHER priority.
        """
        for gpu in self.gpus:
            # In a real system, we'd track priority per allocation
            # Here we simulate: if GPU is full, we can preempt LOW priority work
            if not gpu.can_fit(memory_needed) and priority.value <= Priority.HIGH.value:
                if gpu.allocated_models:
                    evicted = gpu.allocated_models[0]
                    gpu.deallocate(evicted, memory_needed)
                    self.preempted_requests.append(evicted)
                    return gpu
        return None

    def schedule_batch(self) -> List[Dict]:
        """
        Process the request queue and schedule requests to GPUs.
        Returns list of scheduling decisions.
        """
        decisions = []

        while self.request_queue:
            req = heapq.heappop(self.request_queue)
            tenant = self.tenants.get(req.tenant_id)

            # Try bin-packing placement
            gpu = self.find_gpu_bin_pack(req.memory_required_mb)

            if gpu is None and req.priority.value <= Priority.HIGH.value:
                # Try preemption for high-priority requests
                gpu = self.try_preempt(req.memory_required_mb, req.priority)
                if gpu:
                    decisions.append({
                        "request_id": req.request_id,
                        "action": "PREEMPTED",
                        "gpu": gpu.id,
                        "priority": req.priority.name,
                    })
                    if tenant:
                        tenant.requests_preempted += 1

            if gpu is None:
                decisions.append({
                    "request_id": req.request_id,
                    "action": "NO_CAPACITY",
                    "priority": req.priority.name,
                })
                self.total_rejected += 1
                continue

            # Allocate
            gpu.allocate(req.model_id, req.memory_required_mb)
            if tenant:
                tenant.gpu_used_mb += req.memory_required_mb
                tenant.requests_served += 1

            self.total_scheduled += 1
            decisions.append({
                "request_id": req.request_id,
                "action": "SCHEDULED",
                "gpu": gpu.id,
                "memory_mb": req.memory_required_mb,
                "priority": req.priority.name,
                "tenant": tenant.name if tenant else "unknown",
            })

            # Simulate completion (free memory after compute)
            time.sleep(req.compute_time_ms / 10000)  # Scaled down
            gpu.deallocate(req.model_id, req.memory_required_mb)
            if tenant:
                tenant.gpu_used_mb -= req.memory_required_mb

        return decisions

    def print_cluster_status(self):
        print(f"\n    {'─'*55}")
        print(f"    GPU Cluster Status:")
        for gpu in self.gpus:
            bar_len = 30
            filled = int(gpu.utilization * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"      {gpu.id}: [{bar}] {gpu.utilization:.0%} "
                  f"({gpu.used_memory_mb}/{gpu.total_memory_mb}MB) "
                  f"models={len(gpu.allocated_models)}")
        print(f"    {'─'*55}")

    def print_tenant_status(self):
        print(f"\n    Tenant Status:")
        print(f"    {'Tenant':<15} {'Quota':>8} {'Used':>8} {'Served':>8} {'Preempted':>10}")
        print(f"    {'─'*55}")
        for t in self.tenants.values():
            print(f"    {t.name:<15} {t.gpu_quota_mb:>6}MB {t.gpu_used_mb:>6}MB "
                  f"{t.requests_served:>8} {t.requests_preempted:>10}")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          GPU RESOURCE SCHEDULER                              ║
║          Multi-Tenant Inference Cluster Simulation            ║
╠══════════════════════════════════════════════════════════════╣
║  Pattern: Bin-pack models onto GPUs, priority scheduling,    ║
║  tenant quotas, and preemption for critical requests.         ║
╚══════════════════════════════════════════════════════════════╝
""")

    scheduler = GPUScheduler(num_gpus=4, gpu_memory_mb=16384)

    # Register tenants with quotas
    print("  Step 1: Registering tenants with GPU quotas")
    print("  " + "─" * 50)
    tenants = [
        Tenant("t1", "FraudTeam", gpu_quota_mb=32768),    # 2 GPUs worth
        Tenant("t2", "SearchTeam", gpu_quota_mb=24576),    # 1.5 GPUs
        Tenant("t3", "AdsTeam", gpu_quota_mb=16384),       # 1 GPU
        Tenant("t4", "ExperimentalML", gpu_quota_mb=8192), # 0.5 GPU
    ]
    for t in tenants:
        scheduler.register_tenant(t)

    # --- Scenario 1: Normal mixed workload ---
    print(f"\n{'━'*60}")
    print("  Step 2: Simulating mixed priority workload")
    print("━" * 60)
    print("  Submitting requests from all tenants at various priorities...\n")

    request_id = 0
    models = [
        ("bert-fraud", 4096),
        ("gpt-search", 8192),
        ("ad-ranker", 2048),
        ("experimental-llm", 12288),
        ("small-classifier", 1024),
    ]

    for _ in range(20):
        model_name, memory = random.choice(models)
        tenant = random.choice(tenants)
        priority = random.choice(list(Priority))
        req = InferenceRequest(
            priority=priority,
            arrival_time=time.time(),
            request_id=f"req-{request_id:04d}",
            tenant_id=tenant.id,
            model_id=model_name,
            memory_required_mb=memory,
            compute_time_ms=random.uniform(10, 100),
        )
        status = scheduler.submit_request(req)
        request_id += 1

    decisions = scheduler.schedule_batch()

    # Print scheduling decisions
    print(f"    Scheduling decisions ({len(decisions)} requests):")
    print(f"    {'ID':<10} {'Action':<13} {'GPU':<8} {'Priority':<10} {'Tenant':<12}")
    print(f"    {'─'*55}")
    for d in decisions[:15]:  # Show first 15
        print(f"    {d['request_id']:<10} {d['action']:<13} "
              f"{d.get('gpu', 'N/A'):<8} {d['priority']:<10} "
              f"{d.get('tenant', 'N/A'):<12}")
    if len(decisions) > 15:
        print(f"    ... and {len(decisions) - 15} more")

    scheduler.print_cluster_status()
    scheduler.print_tenant_status()

    # --- Scenario 2: Priority preemption ---
    print(f"\n{'━'*60}")
    print("  Step 3: Priority preemption scenario")
    print("━" * 60)
    print("  Filling cluster, then submitting CRITICAL request...\n")

    # Fill GPUs
    for i in range(8):
        req = InferenceRequest(
            priority=Priority.LOW,
            arrival_time=time.time(),
            request_id=f"fill-{i:03d}",
            tenant_id="t4",
            model_id="experimental-llm",
            memory_required_mb=6000,
            compute_time_ms=500,
        )
        scheduler.submit_request(req)

    # Now submit critical request
    critical_req = InferenceRequest(
        priority=Priority.CRITICAL,
        arrival_time=time.time(),
        request_id="critical-001",
        tenant_id="t1",
        model_id="bert-fraud",
        memory_required_mb=4096,
        compute_time_ms=20,
    )
    scheduler.submit_request(critical_req)
    print("    Submitted CRITICAL fraud-detection request")

    decisions = scheduler.schedule_batch()
    for d in decisions:
        action_icon = {"SCHEDULED": "✓", "PREEMPTED": "⚡", "NO_CAPACITY": "✗"}.get(d["action"], "?")
        print(f"    {action_icon} {d['request_id']}: {d['action']} "
              f"(priority={d['priority']}, gpu={d.get('gpu', 'N/A')})")

    # --- Scenario 3: Bin packing efficiency ---
    print(f"\n{'━'*60}")
    print("  Step 4: Bin packing demonstration")
    print("━" * 60)
    print("  Showing how small models pack efficiently onto GPUs\n")

    # Reset cluster
    scheduler2 = GPUScheduler(num_gpus=2, gpu_memory_mb=16384)
    scheduler2.register_tenant(Tenant("t1", "PackingDemo", gpu_quota_mb=65536))

    # Submit various sized models
    small_models = [
        ("tiny-classifier", 1024),
        ("embedding-svc", 2048),
        ("ner-model", 1536),
        ("sentiment", 1024),
        ("toxicity", 2048),
        ("language-id", 512),
        ("spell-check", 768),
        ("summarizer", 4096),
        ("translator", 3072),
    ]

    print("    Submitting models for bin-packing:")
    for name, mem in small_models:
        req = InferenceRequest(
            priority=Priority.MEDIUM,
            arrival_time=time.time(),
            request_id=f"bp-{name}",
            tenant_id="t1",
            model_id=name,
            memory_required_mb=mem,
            compute_time_ms=50,
        )
        scheduler2.submit_request(req)
        print(f"      {name}: {mem}MB")

    total_mem = sum(m[1] for m in small_models)
    print(f"\n    Total memory requested: {total_mem}MB across 2 GPUs (32768MB total)")
    print(f"    Theoretical utilization: {total_mem/32768:.1%}")

    decisions = scheduler2.schedule_batch()
    scheduled = [d for d in decisions if d["action"] == "SCHEDULED"]
    print(f"    Successfully packed: {len(scheduled)}/{len(small_models)} models")

    # --- Summary ---
    print(f"""
{'━'*60}
  SCHEDULING SUMMARY
{'━'*60}
  Total scheduled: {scheduler.total_scheduled}
  Total rejected:  {scheduler.total_rejected}
  Preemptions:     {len(scheduler.preempted_requests)}

{'━'*60}
  KEY TAKEAWAYS
{'━'*60}
  1. BIN PACKING: Pack small models tightly to maximize GPU utilization
     - Best-fit decreasing minimizes fragmentation
     - Real systems use NVIDIA MPS/MIG for GPU partitioning
     
  2. PRIORITY QUEUES: Not all inference is equal
     - Real-time serving (CRITICAL) > batch predictions (LOW)
     - Preemption ensures SLAs are met for critical paths
     
  3. MULTI-TENANT QUOTAS: Fair sharing in shared clusters
     - Prevents one team from monopolizing GPUs
     - Burst capacity when others aren't using their quota
     
  4. PRODUCTION TOOLS:
     - NVIDIA Triton: Model-level scheduling + batching
     - Kubernetes + GPU operator: Node-level scheduling
     - Ray Serve: Replica-based autoscaling
     - KServe: Serverless inference with scale-to-zero
     - NVIDIA MIG: Hardware-level GPU partitioning
     
  5. KEY METRICS TO MONITOR:
     - GPU memory utilization (target: >80%)
     - Queue depth and wait time per priority
     - Preemption rate (high = need more capacity)
     - Per-tenant quota utilization
{'━'*60}
""")


if __name__ == "__main__":
    main()
