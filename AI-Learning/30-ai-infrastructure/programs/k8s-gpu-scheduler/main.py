"""
Kubernetes GPU Scheduler Simulator
====================================
Simulates Kubernetes GPU scheduling decisions for AI workloads.

Demonstrates:
1. GPU node modeling with different types (H100, A100, T4)
2. Incoming inference pods with resource requests
3. Bin-packing and topology-aware placement
4. Scheduling decisions and fragmentation metrics
5. MIG (Multi-Instance GPU) slicing for smaller models

Usage: python3 main.py

Staff Architect Tool: Understand how scheduling decisions impact GPU utilization
and how topology-aware placement prevents performance degradation.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
import random
import math


# =============================================================================
# Node and GPU Modeling
# =============================================================================

class GPUType(Enum):
    H100_SXM = "H100_SXM"
    A100_80GB = "A100_80GB"
    T4 = "T4"


@dataclass
class MIGSlice:
    """A MIG partition of a GPU."""
    profile: str  # e.g., "3g.40gb", "1g.10gb"
    memory_gb: float
    compute_fraction: float  # Fraction of full GPU compute
    allocated: bool = False
    pod_name: Optional[str] = None


@dataclass
class GPU:
    """Represents a single GPU on a node."""
    gpu_id: int
    gpu_type: GPUType
    memory_gb: float
    nvlink_group: int  # GPUs in same NVLink group can communicate fast
    numa_node: int
    allocated: bool = False
    pod_name: Optional[str] = None
    mig_slices: List[MIGSlice] = field(default_factory=list)
    mig_enabled: bool = False

    @property
    def available_memory_gb(self) -> float:
        if self.mig_enabled:
            return sum(s.memory_gb for s in self.mig_slices if not s.allocated)
        return 0 if self.allocated else self.memory_gb


GPU_SPECS = {
    GPUType.H100_SXM: {"memory_gb": 80, "nvlink": True, "mig_capable": True},
    GPUType.A100_80GB: {"memory_gb": 80, "nvlink": True, "mig_capable": True},
    GPUType.T4: {"memory_gb": 16, "nvlink": False, "mig_capable": False},
}


@dataclass
class Node:
    """Represents a Kubernetes GPU node."""
    name: str
    gpu_type: GPUType
    gpus: List[GPU]
    cpu_cores: int
    memory_gb: float
    cpu_used: float = 0
    memory_used_gb: float = 0
    has_nvlink: bool = False
    has_infiniband: bool = False

    @property
    def total_gpus(self) -> int:
        return len(self.gpus)

    @property
    def available_gpus(self) -> int:
        return sum(1 for g in self.gpus if not g.allocated)

    @property
    def gpu_utilization(self) -> float:
        allocated = sum(1 for g in self.gpus if g.allocated)
        return allocated / len(self.gpus) if self.gpus else 0

    def get_available_gpus_in_numa(self, numa_node: int) -> List[GPU]:
        return [g for g in self.gpus if not g.allocated and g.numa_node == numa_node]

    def get_available_gpus_in_nvlink_group(self, group: int) -> List[GPU]:
        return [g for g in self.gpus if not g.allocated and g.nvlink_group == group]


def create_h100_node(name: str) -> Node:
    """Create an 8-GPU H100 node with NVLink topology."""
    gpus = []
    for i in range(8):
        gpu = GPU(
            gpu_id=i,
            gpu_type=GPUType.H100_SXM,
            memory_gb=80,
            nvlink_group=0,  # All connected via NVSwitch
            numa_node=0 if i < 4 else 1,  # 4 GPUs per NUMA node
        )
        gpus.append(gpu)
    return Node(
        name=name, gpu_type=GPUType.H100_SXM, gpus=gpus,
        cpu_cores=128, memory_gb=2048, has_nvlink=True, has_infiniband=True,
    )


def create_a100_node(name: str) -> Node:
    """Create an 8-GPU A100 node."""
    gpus = []
    for i in range(8):
        gpu = GPU(
            gpu_id=i,
            gpu_type=GPUType.A100_80GB,
            memory_gb=80,
            nvlink_group=i // 4,  # 2 NVLink groups of 4
            numa_node=0 if i < 4 else 1,
        )
        gpus.append(gpu)
    return Node(
        name=name, gpu_type=GPUType.A100_80GB, gpus=gpus,
        cpu_cores=96, memory_gb=1024, has_nvlink=True, has_infiniband=True,
    )


def create_t4_node(name: str) -> Node:
    """Create a 4-GPU T4 node (no NVLink)."""
    gpus = []
    for i in range(4):
        gpu = GPU(
            gpu_id=i,
            gpu_type=GPUType.T4,
            memory_gb=16,
            nvlink_group=-1,  # No NVLink
            numa_node=0,
        )
        gpus.append(gpu)
    return Node(
        name=name, gpu_type=GPUType.T4, gpus=gpus,
        cpu_cores=48, memory_gb=256, has_nvlink=False, has_infiniband=False,
    )


def create_mig_node(name: str) -> Node:
    """Create an H100 node with MIG enabled (for small model serving)."""
    gpus = []
    for i in range(8):
        gpu = GPU(
            gpu_id=i,
            gpu_type=GPUType.H100_SXM,
            memory_gb=80,
            nvlink_group=0,
            numa_node=0 if i < 4 else 1,
            mig_enabled=True,
            mig_slices=[
                MIGSlice(profile="3g.40gb", memory_gb=40, compute_fraction=3/7),
                MIGSlice(profile="3g.40gb", memory_gb=40, compute_fraction=3/7),
                # Remaining 1/7 is overhead
            ],
        )
        gpus.append(gpu)
    return Node(
        name=name, gpu_type=GPUType.H100_SXM, gpus=gpus,
        cpu_cores=128, memory_gb=2048, has_nvlink=True, has_infiniband=True,
    )


# =============================================================================
# Pod Definitions
# =============================================================================

@dataclass
class PodRequest:
    """An inference pod requesting GPU resources."""
    name: str
    gpu_count: int
    gpu_type_required: Optional[GPUType] = None
    memory_gb_required: float = 0
    cpu_required: float = 0
    requires_nvlink: bool = False
    requires_same_numa: bool = False
    mig_profile: Optional[str] = None  # e.g., "3g.40gb"
    priority: int = 0  # Higher = more important
    model_name: str = ""
    model_size_gb: float = 0


# =============================================================================
# Scheduler Implementation
# =============================================================================

class SchedulingPolicy(Enum):
    FIRST_FIT = "first_fit"
    BEST_FIT = "best_fit"  # Bin-packing
    TOPOLOGY_AWARE = "topology_aware"


@dataclass
class SchedulingDecision:
    """Result of a scheduling decision."""
    pod: PodRequest
    node: Optional[Node]
    gpus_assigned: List[int]
    success: bool
    reason: str
    policy_used: str


class GPUScheduler:
    """Simulates Kubernetes GPU scheduling with topology awareness."""

    def __init__(self, nodes: List[Node], policy: SchedulingPolicy = SchedulingPolicy.TOPOLOGY_AWARE):
        self.nodes = nodes
        self.policy = policy
        self.decisions: List[SchedulingDecision] = []
        self.pending_pods: List[PodRequest] = []

    def schedule(self, pod: PodRequest) -> SchedulingDecision:
        """Schedule a pod onto a node."""
        if pod.mig_profile:
            return self._schedule_mig(pod)

        if self.policy == SchedulingPolicy.FIRST_FIT:
            return self._schedule_first_fit(pod)
        elif self.policy == SchedulingPolicy.BEST_FIT:
            return self._schedule_best_fit(pod)
        else:
            return self._schedule_topology_aware(pod)

    def _schedule_mig(self, pod: PodRequest) -> SchedulingDecision:
        """Schedule onto a MIG slice."""
        for node in self.nodes:
            for gpu in node.gpus:
                if not gpu.mig_enabled:
                    continue
                for slice in gpu.mig_slices:
                    if not slice.allocated and slice.profile == pod.mig_profile:
                        slice.allocated = True
                        slice.pod_name = pod.name
                        decision = SchedulingDecision(
                            pod=pod, node=node, gpus_assigned=[gpu.gpu_id],
                            success=True,
                            reason=f"MIG slice {slice.profile} on {node.name} GPU {gpu.gpu_id}",
                            policy_used="mig",
                        )
                        self.decisions.append(decision)
                        return decision

        decision = SchedulingDecision(
            pod=pod, node=None, gpus_assigned=[],
            success=False, reason=f"No available MIG slice {pod.mig_profile}",
            policy_used="mig",
        )
        self.decisions.append(decision)
        return decision

    def _schedule_first_fit(self, pod: PodRequest) -> SchedulingDecision:
        """Simple first-fit: first node with enough GPUs."""
        for node in self.nodes:
            if self._node_fits(node, pod):
                gpus = self._allocate_gpus(node, pod, topology_aware=False)
                decision = SchedulingDecision(
                    pod=pod, node=node, gpus_assigned=gpus,
                    success=True,
                    reason=f"First-fit on {node.name}",
                    policy_used="first_fit",
                )
                self.decisions.append(decision)
                return decision

        return self._fail(pod, "No node with sufficient resources (first-fit)")

    def _schedule_best_fit(self, pod: PodRequest) -> SchedulingDecision:
        """Bin-packing: node with least remaining GPUs after allocation."""
        best_node = None
        best_remaining = float('inf')

        for node in self.nodes:
            if self._node_fits(node, pod):
                remaining = node.available_gpus - pod.gpu_count
                if remaining < best_remaining:
                    best_remaining = remaining
                    best_node = node

        if best_node:
            gpus = self._allocate_gpus(best_node, pod, topology_aware=False)
            decision = SchedulingDecision(
                pod=pod, node=best_node, gpus_assigned=gpus,
                success=True,
                reason=f"Best-fit on {best_node.name} (leaves {best_remaining} GPUs free)",
                policy_used="best_fit",
            )
            self.decisions.append(decision)
            return decision

        return self._fail(pod, "No node with sufficient resources (best-fit)")

    def _schedule_topology_aware(self, pod: PodRequest) -> SchedulingDecision:
        """Topology-aware: prefer same NUMA node, same NVLink group."""
        candidates = []

        for node in self.nodes:
            if not self._node_fits(node, pod):
                continue

            score = 0
            reason_parts = []

            # Prefer correct GPU type
            if pod.gpu_type_required and node.gpu_type == pod.gpu_type_required:
                score += 100
                reason_parts.append("correct GPU type")
            elif pod.gpu_type_required and node.gpu_type != pod.gpu_type_required:
                continue  # Hard requirement

            # Prefer NVLink if required
            if pod.requires_nvlink and not node.has_nvlink:
                continue
            if node.has_nvlink and pod.gpu_count > 1:
                score += 50
                reason_parts.append("NVLink available")

            # Prefer same NUMA node
            if pod.requires_same_numa or pod.gpu_count > 1:
                for numa in range(2):
                    available_in_numa = len(node.get_available_gpus_in_numa(numa))
                    if available_in_numa >= pod.gpu_count:
                        score += 30
                        reason_parts.append(f"fits in NUMA {numa}")
                        break

            # Bin-packing score (prefer fuller nodes)
            utilization_score = int(node.gpu_utilization * 20)
            score += utilization_score
            reason_parts.append(f"utilization={node.gpu_utilization:.0%}")

            candidates.append((score, node, ", ".join(reason_parts)))

        if not candidates:
            return self._fail(pod, "No node satisfies topology requirements")

        # Pick highest score
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_node, reason = candidates[0]

        gpus = self._allocate_gpus(best_node, pod, topology_aware=True)
        decision = SchedulingDecision(
            pod=pod, node=best_node, gpus_assigned=gpus,
            success=True,
            reason=f"Topology-aware on {best_node.name} ({reason})",
            policy_used="topology_aware",
        )
        self.decisions.append(decision)
        return decision

    def _node_fits(self, node: Node, pod: PodRequest) -> bool:
        """Check if node has enough resources."""
        if node.available_gpus < pod.gpu_count:
            return False
        if pod.gpu_type_required and node.gpu_type != pod.gpu_type_required:
            return False
        if pod.requires_nvlink and not node.has_nvlink:
            return False
        return True

    def _allocate_gpus(self, node: Node, pod: PodRequest, topology_aware: bool) -> List[int]:
        """Allocate specific GPUs on a node."""
        allocated = []

        if topology_aware and pod.gpu_count > 1:
            # Try same NUMA node first
            for numa in range(2):
                available = node.get_available_gpus_in_numa(numa)
                if len(available) >= pod.gpu_count:
                    for gpu in available[:pod.gpu_count]:
                        gpu.allocated = True
                        gpu.pod_name = pod.name
                        allocated.append(gpu.gpu_id)
                    return allocated

        # Fallback: any available GPUs
        for gpu in node.gpus:
            if not gpu.allocated and len(allocated) < pod.gpu_count:
                gpu.allocated = True
                gpu.pod_name = pod.name
                allocated.append(gpu.gpu_id)

        return allocated

    def _fail(self, pod: PodRequest, reason: str) -> SchedulingDecision:
        decision = SchedulingDecision(
            pod=pod, node=None, gpus_assigned=[],
            success=False, reason=reason,
            policy_used=self.policy.value,
        )
        self.decisions.append(decision)
        self.pending_pods.append(pod)
        return decision

    def get_cluster_metrics(self) -> Dict:
        """Calculate cluster-wide metrics."""
        total_gpus = sum(n.total_gpus for n in self.nodes)
        allocated_gpus = sum(n.total_gpus - n.available_gpus for n in self.nodes)
        fragmented_nodes = sum(
            1 for n in self.nodes
            if 0 < n.available_gpus < 4  # Partially used, can't fit TP=4
        )
        return {
            "total_gpus": total_gpus,
            "allocated_gpus": allocated_gpus,
            "utilization": allocated_gpus / total_gpus if total_gpus > 0 else 0,
            "fragmented_nodes": fragmented_nodes,
            "pending_pods": len(self.pending_pods),
            "successful_schedules": sum(1 for d in self.decisions if d.success),
            "failed_schedules": sum(1 for d in self.decisions if not d.success),
        }


# =============================================================================
# Simulation Scenarios
# =============================================================================

def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_cluster_state(nodes: List[Node]):
    """Visualize cluster GPU allocation."""
    print("\n  Cluster State:")
    print(f"  {'Node':<20} {'Type':<12} {'GPUs Used':<12} {'Utilization':<12}")
    print(f"  {'─'*56}")
    for node in nodes:
        used = node.total_gpus - node.available_gpus
        bar = "█" * used + "░" * node.available_gpus
        print(f"  {node.name:<20} {node.gpu_type.value:<12} [{bar}] {node.gpu_utilization:.0%}")


def scenario_basic_scheduling():
    """Demonstrate basic scheduling policies."""
    print_header("SCENARIO 1: Scheduling Policies Comparison")

    # Create cluster
    nodes = [
        create_h100_node("h100-node-1"),
        create_h100_node("h100-node-2"),
        create_a100_node("a100-node-1"),
        create_t4_node("t4-node-1"),
        create_t4_node("t4-node-2"),
    ]

    # Workloads
    pods = [
        PodRequest("llm-70b-replica-1", gpu_count=4, gpu_type_required=GPUType.H100_SXM,
                   requires_nvlink=True, requires_same_numa=True, model_name="LLaMA-70B", model_size_gb=140),
        PodRequest("llm-70b-replica-2", gpu_count=4, gpu_type_required=GPUType.H100_SXM,
                   requires_nvlink=True, requires_same_numa=True, model_name="LLaMA-70B", model_size_gb=140),
        PodRequest("llm-13b-serve", gpu_count=1, gpu_type_required=GPUType.A100_80GB,
                   model_name="LLaMA-13B", model_size_gb=26),
        PodRequest("embedding-model", gpu_count=1, gpu_type_required=GPUType.T4,
                   model_name="E5-Large", model_size_gb=1.3),
        PodRequest("llm-7b-serve-1", gpu_count=1, gpu_type_required=GPUType.A100_80GB,
                   model_name="LLaMA-7B", model_size_gb=14),
        PodRequest("llm-7b-serve-2", gpu_count=1, gpu_type_required=GPUType.T4,
                   model_name="LLaMA-7B-INT4", model_size_gb=4),
        PodRequest("llm-70b-replica-3", gpu_count=4, gpu_type_required=GPUType.H100_SXM,
                   requires_nvlink=True, model_name="LLaMA-70B", model_size_gb=140),
    ]

    scheduler = GPUScheduler(nodes, SchedulingPolicy.TOPOLOGY_AWARE)

    print("\n  Scheduling pods with TOPOLOGY_AWARE policy:\n")
    for pod in pods:
        decision = scheduler.schedule(pod)
        status = "✓" if decision.success else "✗"
        print(f"  {status} {pod.name:<25} GPUs={pod.gpu_count}  →  {decision.reason}")

    print_cluster_state(nodes)

    metrics = scheduler.get_cluster_metrics()
    print(f"\n  Cluster Metrics:")
    print(f"    Total GPUs: {metrics['total_gpus']}")
    print(f"    Allocated: {metrics['allocated_gpus']}")
    print(f"    Utilization: {metrics['utilization']:.1%}")
    print(f"    Fragmented nodes: {metrics['fragmented_nodes']}")
    print(f"    Pending pods: {metrics['pending_pods']}")


def scenario_mig_scheduling():
    """Demonstrate MIG slicing for small models."""
    print_header("SCENARIO 2: MIG Slicing for Small Models")

    print("""
  Problem: Running a 7B model (14GB) on a full H100 (80GB) wastes 82% of memory.
  Solution: Use MIG to partition H100 into 3g.40gb slices (2 per GPU).
  Result: Single H100 serves 2 independent 7B models.
    """)

    nodes = [create_mig_node("h100-mig-node-1")]
    scheduler = GPUScheduler(nodes, SchedulingPolicy.TOPOLOGY_AWARE)

    # Schedule many small models onto MIG slices
    pods = [
        PodRequest(f"small-model-{i}", gpu_count=1, mig_profile="3g.40gb",
                   model_name=f"7B-model-{i}", model_size_gb=14)
        for i in range(16)  # Try to fit 16 small models
    ]

    print("  Scheduling 16 small models onto MIG slices (2 slices per GPU, 8 GPUs):\n")
    for pod in pods:
        decision = scheduler.schedule(pod)
        status = "✓" if decision.success else "✗"
        print(f"  {status} {pod.name:<20} →  {decision.reason}")

    metrics = scheduler.get_cluster_metrics()
    print(f"\n  Results:")
    print(f"    Models scheduled: {metrics['successful_schedules']}")
    print(f"    Models pending: {metrics['failed_schedules']}")
    print(f"    MIG slices per GPU: 2 (3g.40gb profile)")
    print(f"    Total capacity: 8 GPUs × 2 slices = 16 small models")

    # Cost comparison
    h100_cost = 12.26  # $/hr on-demand
    t4_cost = 0.53
    print(f"\n  Cost Comparison (16 small models):")
    print(f"    Without MIG: 16× H100 = ${16 * h100_cost:.2f}/hr (${16 * h100_cost * 730:,.0f}/month)")
    print(f"    With MIG:    1× H100 node (8 GPUs) = ${8 * h100_cost:.2f}/hr (${8 * h100_cost * 730:,.0f}/month)")
    print(f"    With T4:     16× T4 = ${16 * t4_cost:.2f}/hr (${16 * t4_cost * 730:,.0f}/month)")
    print(f"\n    MIG saves {(16-8)/16*100:.0f}% vs naive H100 allocation")
    print(f"    T4 saves {(1 - 16*t4_cost/(8*h100_cost))*100:.0f}% vs MIG (if model fits in 16GB)")


def scenario_fragmentation():
    """Demonstrate GPU fragmentation problem."""
    print_header("SCENARIO 3: GPU Fragmentation Problem")

    print("""
  Problem: Random scheduling creates fragmentation where no single node
  has enough contiguous GPUs for large TP=4 workloads.
    """)

    nodes = [
        create_h100_node("h100-node-1"),
        create_h100_node("h100-node-2"),
        create_h100_node("h100-node-3"),
    ]

    # First: schedule many 1-GPU pods spreading across nodes
    small_pods = [
        PodRequest(f"small-job-{i}", gpu_count=1, gpu_type_required=GPUType.H100_SXM,
                   model_name="misc", model_size_gb=10)
        for i in range(15)  # 15 single-GPU jobs across 3 nodes (24 GPUs total)
    ]

    # Use first-fit (causes fragmentation)
    scheduler = GPUScheduler(nodes, SchedulingPolicy.FIRST_FIT)
    print("  Phase 1: Schedule 15 single-GPU pods (first-fit):\n")
    for pod in small_pods:
        scheduler.schedule(pod)

    print_cluster_state(nodes)

    # Now try to schedule a TP=4 job
    large_pod = PodRequest("llm-70b-urgent", gpu_count=4, gpu_type_required=GPUType.H100_SXM,
                           requires_nvlink=True, requires_same_numa=True, model_name="LLaMA-70B", model_size_gb=140)

    print(f"\n  Phase 2: Try scheduling TP=4 pod (requires 4 GPUs in same NUMA):")
    decision = scheduler.schedule(large_pod)
    status = "✓" if decision.success else "✗"
    print(f"  {status} {large_pod.name} →  {decision.reason}")

    # Show the fix
    print(f"\n  With BEST-FIT policy (bin-packing), fragmentation is reduced.")
    print(f"  With TOPOLOGY-AWARE + preemption, lower-priority pods yield to TP=4 workloads.")


def scenario_autoscaling():
    """Demonstrate scaling decisions."""
    print_header("SCENARIO 4: Auto-Scaling Simulation")

    print("""
  Simulates traffic pattern and GPU pod scaling over 24 hours.
  Base: 2 replicas (TP=4 each = 8 GPUs minimum)
  Peak: up to 8 replicas (32 GPUs)
    """)

    # Simulate 24-hour traffic pattern
    hours = list(range(24))
    # Traffic multiplier: low at night, high during business hours
    traffic = [
        0.2, 0.1, 0.1, 0.1, 0.2, 0.3,  # 00:00 - 05:00 (low)
        0.5, 0.8, 1.0, 1.0, 0.9, 1.0,   # 06:00 - 11:00 (ramp up)
        0.8, 1.0, 1.0, 0.9, 0.8, 0.7,   # 12:00 - 17:00 (sustained)
        0.6, 0.5, 0.4, 0.3, 0.3, 0.2,   # 18:00 - 23:00 (ramp down)
    ]

    base_replicas = 2
    max_replicas = 8
    gpus_per_replica = 4
    cost_per_gpu_hr = 7.50  # Reserved H100

    print(f"\n  {'Hour':<6} {'Traffic':<10} {'Replicas':<10} {'GPUs':<8} {'Cost/hr':<10}")
    print(f"  {'─'*44}")

    total_cost = 0
    total_gpu_hours = 0

    for hour, load in zip(hours, traffic):
        # Scale replicas proportional to load
        needed_replicas = max(base_replicas, math.ceil(max_replicas * load))
        gpus_used = needed_replicas * gpus_per_replica
        hourly_cost = gpus_used * cost_per_gpu_hr
        total_cost += hourly_cost
        total_gpu_hours += gpus_used

        bar = "█" * needed_replicas + "░" * (max_replicas - needed_replicas)
        print(f"  {hour:02d}:00  {load:<10.1f} [{bar}] {needed_replicas:<4} {gpus_used:<8} ${hourly_cost:.0f}")

    print(f"\n  Daily Summary:")
    print(f"    Total GPU-hours: {total_gpu_hours}")
    print(f"    Daily cost: ${total_cost:,.0f}")
    print(f"    Monthly cost (30d): ${total_cost * 30:,.0f}")
    always_on_cost = max_replicas * gpus_per_replica * cost_per_gpu_hr * 24
    print(f"\n    vs Always-on (8 replicas): ${always_on_cost:,.0f}/day (${always_on_cost * 30:,.0f}/month)")
    print(f"    Savings from auto-scaling: {(1 - total_cost/always_on_cost)*100:.0f}%")


# =============================================================================
# Main
# =============================================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║              KUBERNETES GPU SCHEDULER SIMULATOR                       ║
║                                                                      ║
║  Demonstrates GPU scheduling, topology awareness, MIG slicing,       ║
║  fragmentation problems, and auto-scaling decisions.                 ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    scenario_basic_scheduling()
    scenario_mig_scheduling()
    scenario_fragmentation()
    scenario_autoscaling()

    print_header("KEY INSIGHTS FOR STAFF ARCHITECTS")
    print("""
  1. TOPOLOGY-AWARE scheduling prevents cross-NUMA GPU placement
     that degrades tensor parallelism by 30-50%.

  2. MIG enables cost-efficient multi-tenant small model serving
     on expensive GPUs (2× density per GPU for 7B models).

  3. BIN-PACKING (best-fit) reduces fragmentation but may concentrate
     failures. Balance with spread for availability.

  4. Auto-scaling saves 40-60% vs always-on for variable traffic.
     But GPU pod startup (model loading) is 1-10 minutes — plan warm pools.

  5. Gang scheduling (not shown) is critical for distributed training:
     all pods must schedule together or none should start.
    """)


if __name__ == "__main__":
    main()
