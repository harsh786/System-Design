"""
Inference Server Implementation Concepts
=========================================
Simulates key components of a production LLM inference server:
- vLLM-style continuous batching and PagedAttention
- Request scheduling (FCFS, priority, fair-share)
- Token budget enforcement
- Model loading and hot-swapping
- Health checking and readiness
- Metrics collection
- Auto-scaling trigger logic
- Multi-LoRA serving patterns
"""

import time
import heapq
import threading
import uuid
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import defaultdict


# =============================================================================
# 1. KV CACHE MANAGEMENT (PagedAttention Simulation)
# =============================================================================

class KVBlock:
    """Fixed-size block for KV cache (analogous to memory page)."""
    
    BLOCK_SIZE = 16  # tokens per block
    
    def __init__(self, block_id: int, num_heads: int = 8, head_dim: int = 128):
        self.block_id = block_id
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.num_filled = 0  # how many token slots are used
        self.ref_count = 0  # for copy-on-write sharing
        # In real impl, this would be GPU tensor storage
        self.memory_bytes = 2 * num_heads * head_dim * self.BLOCK_SIZE * 2  # K+V, fp16
    
    @property
    def is_full(self) -> bool:
        return self.num_filled >= self.BLOCK_SIZE
    
    @property
    def free_slots(self) -> int:
        return self.BLOCK_SIZE - self.num_filled


class PagedKVCacheManager:
    """
    Manages KV cache blocks using paging (like vLLM's PagedAttention).
    
    Key ideas:
    - Pre-allocate a pool of blocks on GPU memory
    - Allocate blocks to sequences on demand
    - Free blocks when sequences complete
    - Support copy-on-write for prefix sharing
    """
    
    def __init__(self, total_gpu_memory_gb: float = 80.0, model_memory_gb: float = 35.0,
                 num_layers: int = 80, num_kv_heads: int = 8, head_dim: int = 128):
        self.num_layers = num_layers
        self.num_kv_heads = num_kv_heads
        self.head_dim = head_dim
        
        # Calculate available memory for KV cache
        available_memory_gb = total_gpu_memory_gb - model_memory_gb
        available_memory_bytes = int(available_memory_gb * 1024**3)
        
        # Memory per block (across all layers)
        bytes_per_block = (
            2  # K and V
            * num_layers
            * num_kv_heads
            * head_dim
            * KVBlock.BLOCK_SIZE
            * 2  # fp16
        )
        
        self.num_blocks = available_memory_bytes // bytes_per_block
        self.bytes_per_block = bytes_per_block
        
        # Block pool
        self.free_blocks: list[int] = list(range(self.num_blocks))
        self.allocated_blocks: dict[str, list[int]] = {}  # seq_id -> block_ids
        self.block_ref_counts: dict[int, int] = defaultdict(int)
        
        # Prefix cache: hash(prefix_tokens) -> block_ids
        self.prefix_cache: dict[int, list[int]] = {}
        
        print(f"[KVCacheManager] Initialized with {self.num_blocks} blocks "
              f"({available_memory_gb:.1f} GB available, {bytes_per_block/1024:.1f} KB/block)")
    
    def allocate_blocks(self, seq_id: str, num_tokens: int) -> Optional[list[int]]:
        """Allocate blocks for a new sequence."""
        num_blocks_needed = (num_tokens + KVBlock.BLOCK_SIZE - 1) // KVBlock.BLOCK_SIZE
        
        if num_blocks_needed > len(self.free_blocks):
            return None  # OOM - need to preempt or reject
        
        allocated = []
        for _ in range(num_blocks_needed):
            block_id = self.free_blocks.pop()
            allocated.append(block_id)
            self.block_ref_counts[block_id] = 1
        
        self.allocated_blocks[seq_id] = allocated
        return allocated
    
    def append_token(self, seq_id: str) -> Optional[int]:
        """Allocate space for one more token in a sequence."""
        blocks = self.allocated_blocks.get(seq_id, [])
        
        if not blocks:
            # First token - allocate first block
            return self._allocate_one_block(seq_id)
        
        # Check if last block has space (simplified - tracking fill level)
        # In practice, we'd track fill per block
        return self._allocate_one_block(seq_id)
    
    def _allocate_one_block(self, seq_id: str) -> Optional[int]:
        if not self.free_blocks:
            return None
        block_id = self.free_blocks.pop()
        self.block_ref_counts[block_id] = 1
        if seq_id not in self.allocated_blocks:
            self.allocated_blocks[seq_id] = []
        self.allocated_blocks[seq_id].append(block_id)
        return block_id
    
    def free_sequence(self, seq_id: str):
        """Free all blocks for a completed sequence."""
        blocks = self.allocated_blocks.pop(seq_id, [])
        for block_id in blocks:
            self.block_ref_counts[block_id] -= 1
            if self.block_ref_counts[block_id] <= 0:
                self.free_blocks.append(block_id)
                del self.block_ref_counts[block_id]
    
    def share_prefix(self, source_seq_id: str, target_seq_id: str, num_shared_blocks: int):
        """Copy-on-write sharing of prefix blocks between sequences."""
        source_blocks = self.allocated_blocks.get(source_seq_id, [])
        shared = source_blocks[:num_shared_blocks]
        
        for block_id in shared:
            self.block_ref_counts[block_id] += 1
        
        self.allocated_blocks[target_seq_id] = shared.copy()
    
    @property
    def utilization(self) -> float:
        allocated = self.num_blocks - len(self.free_blocks)
        return allocated / self.num_blocks if self.num_blocks > 0 else 0.0
    
    @property
    def available_blocks(self) -> int:
        return len(self.free_blocks)


# =============================================================================
# 2. REQUEST SCHEDULING
# =============================================================================

class RequestPriority(Enum):
    CRITICAL = 0    # Real-time, user-facing
    HIGH = 1        # Interactive, low latency needed
    NORMAL = 2      # Standard requests
    LOW = 3         # Batch processing, can wait
    BACKGROUND = 4  # Offline jobs


@dataclass(order=True)
class InferenceRequest:
    priority: int = field(compare=True)
    arrival_time: float = field(compare=True)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8], compare=False)
    input_tokens: int = field(default=0, compare=False)
    max_output_tokens: int = field(default=512, compare=False)
    model_id: str = field(default="base", compare=False)
    lora_adapter: Optional[str] = field(default=None, compare=False)
    # Runtime state
    output_tokens_generated: int = field(default=0, compare=False)
    status: str = field(default="queued", compare=False)
    start_time: Optional[float] = field(default=None, compare=False)
    end_time: Optional[float] = field(default=None, compare=False)
    tenant_id: str = field(default="default", compare=False)


class FCFSScheduler:
    """First-Come-First-Served scheduling."""
    
    def __init__(self):
        self.queue: list[InferenceRequest] = []
    
    def add_request(self, request: InferenceRequest):
        self.queue.append(request)
    
    def get_next_batch(self, max_batch_size: int, max_tokens: int) -> list[InferenceRequest]:
        batch = []
        total_tokens = 0
        
        remaining = []
        for req in self.queue:
            token_cost = req.input_tokens + req.max_output_tokens
            if len(batch) < max_batch_size and total_tokens + token_cost <= max_tokens:
                batch.append(req)
                total_tokens += token_cost
            else:
                remaining.append(req)
        
        self.queue = remaining
        return batch


class PriorityScheduler:
    """Priority-based scheduling with starvation prevention."""
    
    def __init__(self, max_wait_promotion_sec: float = 30.0):
        self.heap: list[InferenceRequest] = []
        self.max_wait_promotion = max_wait_promotion_sec
    
    def add_request(self, request: InferenceRequest):
        heapq.heappush(self.heap, request)
    
    def get_next_batch(self, max_batch_size: int, max_tokens: int) -> list[InferenceRequest]:
        now = time.time()
        batch = []
        total_tokens = 0
        remaining = []
        
        # Promote starved requests
        for req in self.heap:
            wait_time = now - req.arrival_time
            if wait_time > self.max_wait_promotion:
                req.priority = max(0, req.priority - 1)
        
        heapq.heapify(self.heap)
        
        while self.heap and len(batch) < max_batch_size:
            req = heapq.heappop(self.heap)
            token_cost = req.input_tokens + req.max_output_tokens
            if total_tokens + token_cost <= max_tokens:
                batch.append(req)
                total_tokens += token_cost
            else:
                remaining.append(req)
                break
        
        for req in remaining:
            heapq.heappush(self.heap, req)
        
        return batch


class FairShareScheduler:
    """Fair-share scheduling across tenants with weighted quotas."""
    
    def __init__(self, tenant_weights: Optional[dict[str, float]] = None):
        self.tenant_queues: dict[str, list[InferenceRequest]] = defaultdict(list)
        self.tenant_weights = tenant_weights or {}
        self.tenant_usage: dict[str, float] = defaultdict(float)  # tokens consumed
        self.default_weight = 1.0
    
    def add_request(self, request: InferenceRequest):
        self.tenant_queues[request.tenant_id].append(request)
    
    def get_next_batch(self, max_batch_size: int, max_tokens: int) -> list[InferenceRequest]:
        """Select requests ensuring fair share across tenants."""
        batch = []
        total_tokens = 0
        
        # Calculate fair share: weight / total_weight * max_tokens
        active_tenants = [t for t, q in self.tenant_queues.items() if q]
        if not active_tenants:
            return []
        
        total_weight = sum(self.tenant_weights.get(t, self.default_weight) for t in active_tenants)
        
        # Round-robin with weight consideration
        tenant_cycle = sorted(active_tenants, 
                             key=lambda t: self.tenant_usage[t] / self.tenant_weights.get(t, self.default_weight))
        
        for tenant_id in tenant_cycle:
            if len(batch) >= max_batch_size:
                break
            queue = self.tenant_queues[tenant_id]
            if queue:
                req = queue.pop(0)
                token_cost = req.input_tokens + req.max_output_tokens
                if total_tokens + token_cost <= max_tokens:
                    batch.append(req)
                    total_tokens += token_cost
                    self.tenant_usage[tenant_id] += token_cost
                else:
                    queue.insert(0, req)
        
        return batch


# =============================================================================
# 3. TOKEN BUDGET ENFORCEMENT
# =============================================================================

class TokenBudget:
    """
    Enforce token budgets per tenant/user to prevent cost overruns.
    Supports:
    - Per-request limits
    - Per-minute rate limits
    - Daily/monthly quotas
    - Burst allowance
    """
    
    def __init__(self):
        self.tenant_configs: dict[str, dict] = {}
        self.tenant_usage: dict[str, dict] = defaultdict(lambda: {
            "minute": {"tokens": 0, "reset_at": 0},
            "daily": {"tokens": 0, "reset_at": 0},
            "monthly": {"tokens": 0, "reset_at": 0},
        })
    
    def set_tenant_limits(self, tenant_id: str, 
                          max_tokens_per_request: int = 4096,
                          tokens_per_minute: int = 100_000,
                          tokens_per_day: int = 10_000_000,
                          tokens_per_month: int = 100_000_000):
        self.tenant_configs[tenant_id] = {
            "max_tokens_per_request": max_tokens_per_request,
            "tokens_per_minute": tokens_per_minute,
            "tokens_per_day": tokens_per_day,
            "tokens_per_month": tokens_per_month,
        }
    
    def check_budget(self, tenant_id: str, requested_tokens: int) -> tuple[bool, str]:
        """Check if request is within budget. Returns (allowed, reason)."""
        config = self.tenant_configs.get(tenant_id)
        if not config:
            return True, "no_limits"
        
        # Per-request limit
        if requested_tokens > config["max_tokens_per_request"]:
            return False, f"exceeds_per_request_limit ({requested_tokens} > {config['max_tokens_per_request']})"
        
        now = time.time()
        usage = self.tenant_usage[tenant_id]
        
        # Reset windows
        if now > usage["minute"]["reset_at"]:
            usage["minute"] = {"tokens": 0, "reset_at": now + 60}
        if now > usage["daily"]["reset_at"]:
            usage["daily"] = {"tokens": 0, "reset_at": now + 86400}
        
        # Check rate limits
        if usage["minute"]["tokens"] + requested_tokens > config["tokens_per_minute"]:
            return False, "rate_limit_minute"
        if usage["daily"]["tokens"] + requested_tokens > config["tokens_per_day"]:
            return False, "quota_exceeded_daily"
        
        return True, "allowed"
    
    def record_usage(self, tenant_id: str, tokens_consumed: int):
        usage = self.tenant_usage[tenant_id]
        usage["minute"]["tokens"] += tokens_consumed
        usage["daily"]["tokens"] += tokens_consumed
        usage["monthly"]["tokens"] += tokens_consumed


# =============================================================================
# 4. CONTINUOUS BATCHING ENGINE
# =============================================================================

class ContinuousBatchingEngine:
    """
    Simulates continuous batching (iteration-level scheduling).
    
    At each decode step:
    1. Remove completed sequences from batch
    2. Add new sequences from waiting queue
    3. Execute one forward pass for all active sequences
    """
    
    def __init__(self, max_batch_size: int = 64, max_total_tokens: int = 32768,
                 decode_time_per_step_ms: float = 30.0):
        self.max_batch_size = max_batch_size
        self.max_total_tokens = max_total_tokens
        self.decode_time_ms = decode_time_per_step_ms
        
        self.active_batch: list[InferenceRequest] = []
        self.waiting_queue: list[InferenceRequest] = []
        self.completed: list[InferenceRequest] = []
        
        self.kv_cache = PagedKVCacheManager()
        self.scheduler = PriorityScheduler()
        
        # Metrics
        self.total_tokens_generated = 0
        self.total_forward_passes = 0
        self.step_count = 0
    
    def add_request(self, request: InferenceRequest):
        """Submit a new request to the engine."""
        self.scheduler.add_request(request)
    
    def step(self) -> dict:
        """Execute one decode iteration."""
        self.step_count += 1
        
        # 1. Remove completed sequences
        still_active = []
        for req in self.active_batch:
            if req.output_tokens_generated >= req.max_output_tokens:
                req.status = "completed"
                req.end_time = time.time()
                self.completed.append(req)
                self.kv_cache.free_sequence(req.request_id)
            elif random.random() < 0.02:  # Simulate EOS token
                req.status = "completed"
                req.end_time = time.time()
                self.completed.append(req)
                self.kv_cache.free_sequence(req.request_id)
            else:
                still_active.append(req)
        
        self.active_batch = still_active
        
        # 2. Fill batch with waiting requests
        available_slots = self.max_batch_size - len(self.active_batch)
        if available_slots > 0:
            current_tokens = sum(r.input_tokens + r.output_tokens_generated for r in self.active_batch)
            available_token_budget = self.max_total_tokens - current_tokens
            
            new_requests = self.scheduler.get_next_batch(available_slots, available_token_budget)
            for req in new_requests:
                req.status = "running"
                req.start_time = time.time()
                blocks = self.kv_cache.allocate_blocks(req.request_id, req.input_tokens)
                if blocks is not None:
                    self.active_batch.append(req)
                else:
                    # KV cache full - put back in queue
                    self.scheduler.add_request(req)
        
        # 3. Execute forward pass (generate one token per sequence)
        tokens_this_step = 0
        for req in self.active_batch:
            req.output_tokens_generated += 1
            tokens_this_step += 1
        
        self.total_tokens_generated += tokens_this_step
        self.total_forward_passes += 1
        
        return {
            "step": self.step_count,
            "active_batch_size": len(self.active_batch),
            "tokens_generated": tokens_this_step,
            "queue_depth": len(self.scheduler.heap),
            "completed_total": len(self.completed),
            "kv_cache_util": self.kv_cache.utilization,
            "throughput_tokens_per_step": tokens_this_step,
        }
    
    def run(self, num_steps: int = 100, print_every: int = 10):
        """Run the engine for N decode steps."""
        print(f"\n{'='*60}")
        print(f"Continuous Batching Engine - Running {num_steps} steps")
        print(f"{'='*60}")
        
        for i in range(num_steps):
            metrics = self.step()
            if (i + 1) % print_every == 0:
                print(f"  Step {metrics['step']:4d} | Batch: {metrics['active_batch_size']:3d} | "
                      f"Tokens/step: {metrics['tokens_generated']:3d} | "
                      f"Queue: {metrics['queue_depth']:3d} | "
                      f"KV util: {metrics['kv_cache_util']:.1%}")
        
        avg_throughput = self.total_tokens_generated / self.total_forward_passes if self.total_forward_passes else 0
        print(f"\n  Summary: {self.total_tokens_generated} tokens in {self.total_forward_passes} steps")
        print(f"  Avg tokens/step: {avg_throughput:.1f}")
        print(f"  Completed requests: {len(self.completed)}")


# =============================================================================
# 5. MODEL MANAGER (Loading, Hot-Swapping, Multi-LoRA)
# =============================================================================

@dataclass
class ModelInfo:
    model_id: str
    size_gb: float
    num_params_b: float
    quantization: str = "fp16"
    loaded: bool = False
    load_time_sec: float = 0.0
    gpu_ids: list[int] = field(default_factory=list)


@dataclass 
class LoRAAdapter:
    adapter_id: str
    base_model_id: str
    rank: int = 16
    size_mb: float = 100.0
    loaded: bool = False


class ModelManager:
    """
    Manages model lifecycle:
    - Loading/unloading models
    - Hot-swapping between models
    - Multi-LoRA adapter management
    - GPU memory tracking
    """
    
    def __init__(self, gpu_memory_gb: dict[int, float] = None):
        self.gpu_memory = gpu_memory_gb or {0: 80.0, 1: 80.0}
        self.gpu_used_memory: dict[int, float] = {k: 0.0 for k in self.gpu_memory}
        self.loaded_models: dict[str, ModelInfo] = {}
        self.loaded_adapters: dict[str, LoRAAdapter] = {}
        self.model_registry: dict[str, ModelInfo] = {}
    
    def register_model(self, model: ModelInfo):
        self.model_registry[model.model_id] = model
    
    def load_model(self, model_id: str, gpu_ids: list[int]) -> tuple[bool, str]:
        """Load a model onto specified GPUs (tensor parallel if multiple)."""
        model = self.model_registry.get(model_id)
        if not model:
            return False, f"Model {model_id} not in registry"
        
        # Check memory
        per_gpu_memory = model.size_gb / len(gpu_ids)
        for gpu_id in gpu_ids:
            available = self.gpu_memory[gpu_id] - self.gpu_used_memory[gpu_id]
            if per_gpu_memory > available:
                return False, f"Insufficient memory on GPU {gpu_id} ({available:.1f}GB available, need {per_gpu_memory:.1f}GB)"
        
        # Simulate loading
        load_start = time.time()
        time.sleep(0.01)  # Simulated load time
        model.load_time_sec = time.time() - load_start
        
        # Allocate memory
        for gpu_id in gpu_ids:
            self.gpu_used_memory[gpu_id] += per_gpu_memory
        
        model.loaded = True
        model.gpu_ids = gpu_ids
        self.loaded_models[model_id] = model
        
        print(f"[ModelManager] Loaded {model_id} ({model.size_gb:.1f}GB, {model.quantization}) "
              f"on GPUs {gpu_ids}")
        return True, "success"
    
    def unload_model(self, model_id: str) -> bool:
        model = self.loaded_models.pop(model_id, None)
        if not model:
            return False
        
        per_gpu_memory = model.size_gb / len(model.gpu_ids)
        for gpu_id in model.gpu_ids:
            self.gpu_used_memory[gpu_id] -= per_gpu_memory
        
        # Unload associated adapters
        adapters_to_remove = [
            aid for aid, a in self.loaded_adapters.items() 
            if a.base_model_id == model_id
        ]
        for aid in adapters_to_remove:
            self.unload_adapter(aid)
        
        model.loaded = False
        print(f"[ModelManager] Unloaded {model_id}")
        return True
    
    def load_adapter(self, adapter: LoRAAdapter) -> tuple[bool, str]:
        """Load a LoRA adapter (requires base model to be loaded)."""
        if adapter.base_model_id not in self.loaded_models:
            return False, f"Base model {adapter.base_model_id} not loaded"
        
        base_model = self.loaded_models[adapter.base_model_id]
        gpu_id = base_model.gpu_ids[0]  # Load adapter on first GPU
        
        size_gb = adapter.size_mb / 1024
        available = self.gpu_memory[gpu_id] - self.gpu_used_memory[gpu_id]
        if size_gb > available:
            return False, "Insufficient GPU memory for adapter"
        
        self.gpu_used_memory[gpu_id] += size_gb
        adapter.loaded = True
        self.loaded_adapters[adapter.adapter_id] = adapter
        
        print(f"[ModelManager] Loaded LoRA adapter '{adapter.adapter_id}' "
              f"(rank={adapter.rank}, {adapter.size_mb:.0f}MB) on base '{adapter.base_model_id}'")
        return True, "success"
    
    def unload_adapter(self, adapter_id: str) -> bool:
        adapter = self.loaded_adapters.pop(adapter_id, None)
        if not adapter:
            return False
        
        base_model = self.loaded_models.get(adapter.base_model_id)
        if base_model:
            gpu_id = base_model.gpu_ids[0]
            self.gpu_used_memory[gpu_id] -= adapter.size_mb / 1024
        
        adapter.loaded = False
        return True
    
    def hot_swap_model(self, old_model_id: str, new_model_id: str) -> tuple[bool, str]:
        """Swap one model for another (drain + unload + load)."""
        old_model = self.loaded_models.get(old_model_id)
        if not old_model:
            return False, f"Model {old_model_id} not currently loaded"
        
        gpu_ids = old_model.gpu_ids
        
        print(f"[ModelManager] Hot-swapping {old_model_id} → {new_model_id}")
        self.unload_model(old_model_id)
        success, msg = self.load_model(new_model_id, gpu_ids)
        
        if not success:
            # Rollback
            self.load_model(old_model_id, gpu_ids)
            return False, f"Swap failed: {msg}. Rolled back."
        
        return True, "success"
    
    def get_status(self) -> dict:
        return {
            "loaded_models": {mid: {"size_gb": m.size_gb, "gpus": m.gpu_ids, "quant": m.quantization}
                             for mid, m in self.loaded_models.items()},
            "loaded_adapters": {aid: {"base": a.base_model_id, "rank": a.rank}
                               for aid, a in self.loaded_adapters.items()},
            "gpu_memory": {gpu_id: {"used": self.gpu_used_memory[gpu_id], 
                                     "total": self.gpu_memory[gpu_id],
                                     "util": self.gpu_used_memory[gpu_id] / self.gpu_memory[gpu_id]}
                          for gpu_id in self.gpu_memory},
        }


# =============================================================================
# 6. HEALTH CHECKING AND READINESS
# =============================================================================

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    NOT_READY = "not_ready"


class HealthChecker:
    """
    Health checking for inference servers.
    
    Checks:
    - Model loaded and responsive
    - GPU memory not critically full
    - Latency within bounds
    - Error rate below threshold
    - Queue depth manageable
    """
    
    def __init__(self, model_manager: ModelManager,
                 max_p99_latency_ms: float = 5000.0,
                 max_error_rate: float = 0.05,
                 max_queue_depth: int = 1000,
                 gpu_memory_critical_pct: float = 0.95):
        self.model_manager = model_manager
        self.max_p99_latency_ms = max_p99_latency_ms
        self.max_error_rate = max_error_rate
        self.max_queue_depth = max_queue_depth
        self.gpu_memory_critical_pct = gpu_memory_critical_pct
        
        # Tracked metrics
        self.recent_latencies: list[float] = []
        self.recent_errors: int = 0
        self.recent_requests: int = 0
        self.current_queue_depth: int = 0
        self.is_ready: bool = False
    
    def record_request(self, latency_ms: float, success: bool):
        self.recent_latencies.append(latency_ms)
        self.recent_requests += 1
        if not success:
            self.recent_errors += 1
        
        # Keep window of 100 requests
        if len(self.recent_latencies) > 100:
            self.recent_latencies = self.recent_latencies[-100:]
    
    def check_health(self) -> tuple[HealthStatus, dict]:
        """Comprehensive health check."""
        issues = []
        
        # 1. Model loaded?
        if not self.model_manager.loaded_models:
            return HealthStatus.NOT_READY, {"reason": "no_model_loaded"}
        
        # 2. GPU memory
        for gpu_id, mem in self.model_manager.gpu_memory.items():
            util = self.model_manager.gpu_used_memory[gpu_id] / mem
            if util > self.gpu_memory_critical_pct:
                issues.append(f"GPU {gpu_id} memory critical ({util:.1%})")
        
        # 3. Latency
        if self.recent_latencies:
            sorted_lat = sorted(self.recent_latencies)
            p99_idx = int(len(sorted_lat) * 0.99)
            p99 = sorted_lat[min(p99_idx, len(sorted_lat) - 1)]
            if p99 > self.max_p99_latency_ms:
                issues.append(f"P99 latency {p99:.0f}ms > {self.max_p99_latency_ms:.0f}ms")
        
        # 4. Error rate
        if self.recent_requests > 0:
            error_rate = self.recent_errors / self.recent_requests
            if error_rate > self.max_error_rate:
                issues.append(f"Error rate {error_rate:.1%} > {self.max_error_rate:.1%}")
        
        # 5. Queue depth
        if self.current_queue_depth > self.max_queue_depth:
            issues.append(f"Queue depth {self.current_queue_depth} > {self.max_queue_depth}")
        
        if not issues:
            return HealthStatus.HEALTHY, {"status": "all_checks_passed"}
        elif len(issues) <= 1:
            return HealthStatus.DEGRADED, {"issues": issues}
        else:
            return HealthStatus.UNHEALTHY, {"issues": issues}
    
    def liveness_probe(self) -> bool:
        """K8s liveness: is the process alive and not deadlocked?"""
        return True  # Would check for deadlocks, OOM, etc.
    
    def readiness_probe(self) -> bool:
        """K8s readiness: can this instance serve traffic?"""
        status, _ = self.check_health()
        return status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    
    def startup_probe(self) -> bool:
        """K8s startup: has the model finished loading?"""
        return len(self.model_manager.loaded_models) > 0


# =============================================================================
# 7. METRICS COLLECTION
# =============================================================================

class InferenceMetrics:
    """
    Collects and exposes metrics for inference serving.
    Compatible with Prometheus exposition format.
    """
    
    def __init__(self):
        self.counters: dict[str, float] = defaultdict(float)
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.gauges: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def inc_counter(self, name: str, value: float = 1.0, labels: dict = None):
        key = self._make_key(name, labels)
        with self._lock:
            self.counters[key] += value
    
    def observe_histogram(self, name: str, value: float, labels: dict = None):
        key = self._make_key(name, labels)
        with self._lock:
            self.histograms[key].append(value)
            # Keep last 10000 observations
            if len(self.histograms[key]) > 10000:
                self.histograms[key] = self.histograms[key][-5000:]
    
    def set_gauge(self, name: str, value: float, labels: dict = None):
        key = self._make_key(name, labels)
        with self._lock:
            self.gauges[key] = value
    
    def _make_key(self, name: str, labels: dict = None) -> str:
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name
    
    def get_summary(self) -> dict:
        """Get current metrics summary."""
        with self._lock:
            summary = {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": {},
            }
            for key, values in self.histograms.items():
                if values:
                    sorted_v = sorted(values)
                    n = len(sorted_v)
                    summary["histograms"][key] = {
                        "count": n,
                        "mean": sum(sorted_v) / n,
                        "p50": sorted_v[n // 2],
                        "p95": sorted_v[int(n * 0.95)],
                        "p99": sorted_v[int(n * 0.99)],
                        "max": sorted_v[-1],
                    }
            return summary
    
    def prometheus_format(self) -> str:
        """Export in Prometheus text format."""
        lines = []
        for key, value in self.counters.items():
            lines.append(f"# TYPE {key.split('{')[0]} counter")
            lines.append(f"{key} {value}")
        for key, value in self.gauges.items():
            lines.append(f"# TYPE {key.split('{')[0]} gauge")
            lines.append(f"{key} {value}")
        return "\n".join(lines)


# Standard metrics for inference serving
def create_standard_metrics() -> InferenceMetrics:
    """Create metrics instance with standard inference metrics."""
    m = InferenceMetrics()
    # Initialize gauges
    m.set_gauge("inference_batch_size_current", 0)
    m.set_gauge("inference_queue_depth", 0)
    m.set_gauge("inference_gpu_memory_utilization", 0)
    m.set_gauge("inference_kv_cache_utilization", 0)
    m.set_gauge("inference_active_lora_adapters", 0)
    return m


# =============================================================================
# 8. AUTO-SCALING TRIGGER LOGIC
# =============================================================================

@dataclass
class ScalingDecision:
    action: str  # "scale_up", "scale_down", "no_action"
    current_replicas: int
    target_replicas: int
    reason: str
    confidence: float


class AutoScaler:
    """
    GPU inference auto-scaler.
    
    Scaling signals:
    - Token throughput demand vs capacity
    - Queue depth and growth rate
    - P99 latency vs SLO
    - GPU utilization
    
    Constraints:
    - Min/max replicas
    - Scale-up cooldown (avoid thrashing)
    - Scale-down delay (avoid premature downscale)
    - Budget limits
    """
    
    def __init__(self, 
                 min_replicas: int = 1,
                 max_replicas: int = 16,
                 target_utilization: float = 0.75,
                 scale_up_threshold: float = 0.80,
                 scale_down_threshold: float = 0.30,
                 scale_up_cooldown_sec: float = 120,
                 scale_down_delay_sec: float = 300,
                 tokens_per_sec_per_replica: float = 2000):
        
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.target_utilization = target_utilization
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.scale_up_cooldown_sec = scale_up_cooldown_sec
        self.scale_down_delay_sec = scale_down_delay_sec
        self.tokens_per_sec_per_replica = tokens_per_sec_per_replica
        
        self.current_replicas = min_replicas
        self.last_scale_up_time = 0
        self.last_scale_down_time = 0
        self.below_threshold_since: Optional[float] = None
        
        # Metrics history for decisions
        self.utilization_history: list[tuple[float, float]] = []  # (timestamp, util)
        self.queue_depth_history: list[tuple[float, int]] = []
    
    def record_metrics(self, utilization: float, queue_depth: int, 
                       demand_tokens_per_sec: float, p99_latency_ms: float):
        """Record current metrics for scaling decisions."""
        now = time.time()
        self.utilization_history.append((now, utilization))
        self.queue_depth_history.append((now, queue_depth))
        
        # Keep 10 minutes of history
        cutoff = now - 600
        self.utilization_history = [(t, u) for t, u in self.utilization_history if t > cutoff]
        self.queue_depth_history = [(t, q) for t, q in self.queue_depth_history if t > cutoff]
    
    def evaluate(self, current_utilization: float, queue_depth: int,
                 demand_tokens_per_sec: float, p99_latency_ms: float,
                 latency_slo_ms: float = 5000) -> ScalingDecision:
        """Evaluate whether to scale up/down."""
        now = time.time()
        
        # Calculate required replicas based on demand
        required_capacity = demand_tokens_per_sec / self.target_utilization
        demand_based_replicas = max(
            self.min_replicas,
            min(self.max_replicas, 
                int(required_capacity / self.tokens_per_sec_per_replica) + 1)
        )
        
        # --- SCALE UP LOGIC ---
        should_scale_up = False
        scale_up_reason = ""
        
        # Condition 1: Utilization above threshold
        if current_utilization > self.scale_up_threshold:
            should_scale_up = True
            scale_up_reason = f"utilization {current_utilization:.1%} > {self.scale_up_threshold:.1%}"
        
        # Condition 2: Latency SLO violation
        if p99_latency_ms > latency_slo_ms * 0.9:  # 90% of SLO = warning
            should_scale_up = True
            scale_up_reason = f"p99 latency {p99_latency_ms:.0f}ms approaching SLO {latency_slo_ms:.0f}ms"
        
        # Condition 3: Queue growing
        if len(self.queue_depth_history) >= 3:
            recent_depths = [q for _, q in self.queue_depth_history[-3:]]
            if all(recent_depths[i] < recent_depths[i+1] for i in range(len(recent_depths)-1)):
                if queue_depth > 50:
                    should_scale_up = True
                    scale_up_reason = f"queue growing: {recent_depths}"
        
        if should_scale_up:
            # Check cooldown
            if now - self.last_scale_up_time < self.scale_up_cooldown_sec:
                return ScalingDecision("no_action", self.current_replicas, self.current_replicas,
                                      f"scale_up_cooldown (last scaled {now - self.last_scale_up_time:.0f}s ago)", 0.5)
            
            target = min(self.max_replicas, max(demand_based_replicas, self.current_replicas + 1))
            if target > self.current_replicas:
                return ScalingDecision("scale_up", self.current_replicas, target,
                                      scale_up_reason, 0.9)
        
        # --- SCALE DOWN LOGIC ---
        if current_utilization < self.scale_down_threshold and queue_depth == 0:
            if self.below_threshold_since is None:
                self.below_threshold_since = now
            
            time_below = now - self.below_threshold_since
            if time_below > self.scale_down_delay_sec:
                target = max(self.min_replicas, demand_based_replicas)
                if target < self.current_replicas:
                    self.below_threshold_since = None
                    return ScalingDecision("scale_down", self.current_replicas, target,
                                          f"utilization {current_utilization:.1%} < {self.scale_down_threshold:.1%} "
                                          f"for {time_below:.0f}s", 0.8)
        else:
            self.below_threshold_since = None
        
        return ScalingDecision("no_action", self.current_replicas, self.current_replicas,
                              "metrics within bounds", 0.5)
    
    def apply_decision(self, decision: ScalingDecision):
        """Apply scaling decision."""
        if decision.action == "scale_up":
            self.current_replicas = decision.target_replicas
            self.last_scale_up_time = time.time()
            print(f"[AutoScaler] SCALE UP: {decision.current_replicas} → {decision.target_replicas} "
                  f"({decision.reason})")
        elif decision.action == "scale_down":
            self.current_replicas = decision.target_replicas
            self.last_scale_down_time = time.time()
            print(f"[AutoScaler] SCALE DOWN: {decision.current_replicas} → {decision.target_replicas} "
                  f"({decision.reason})")


# =============================================================================
# 9. MULTI-LORA SERVING PATTERN
# =============================================================================

class MultiLoRAServer:
    """
    Serves multiple LoRA adapters on a shared base model.
    
    Pattern:
    - One base model loaded on GPU
    - Multiple LoRA adapters (small, ~100MB each)
    - Request routing to appropriate adapter
    - Batching across adapters (with grouped computation)
    """
    
    def __init__(self, base_model_id: str, max_adapters: int = 64):
        self.base_model_id = base_model_id
        self.max_adapters = max_adapters
        self.adapters: dict[str, LoRAAdapter] = {}
        self.adapter_request_counts: dict[str, int] = defaultdict(int)
        self.lru_order: list[str] = []  # Least recently used for eviction
    
    def register_adapter(self, adapter: LoRAAdapter) -> bool:
        if len(self.adapters) >= self.max_adapters:
            # Evict LRU adapter
            if self.lru_order:
                evict_id = self.lru_order.pop(0)
                del self.adapters[evict_id]
                print(f"[MultiLoRA] Evicted adapter '{evict_id}' (LRU)")
        
        self.adapters[adapter.adapter_id] = adapter
        self.lru_order.append(adapter.adapter_id)
        print(f"[MultiLoRA] Registered adapter '{adapter.adapter_id}' "
              f"({len(self.adapters)}/{self.max_adapters} slots used)")
        return True
    
    def route_request(self, request: InferenceRequest) -> Optional[str]:
        """Route request to appropriate adapter."""
        adapter_id = request.lora_adapter
        
        if adapter_id is None:
            return self.base_model_id  # Use base model
        
        if adapter_id not in self.adapters:
            print(f"[MultiLoRA] Warning: adapter '{adapter_id}' not found, using base model")
            return self.base_model_id
        
        # Update LRU
        if adapter_id in self.lru_order:
            self.lru_order.remove(adapter_id)
        self.lru_order.append(adapter_id)
        
        self.adapter_request_counts[adapter_id] += 1
        return adapter_id
    
    def batch_by_adapter(self, requests: list[InferenceRequest]) -> dict[str, list[InferenceRequest]]:
        """Group requests by adapter for efficient batched computation."""
        groups: dict[str, list[InferenceRequest]] = defaultdict(list)
        for req in requests:
            adapter = self.route_request(req)
            groups[adapter].append(req)
        return groups
    
    def get_stats(self) -> dict:
        return {
            "base_model": self.base_model_id,
            "num_adapters": len(self.adapters),
            "adapter_usage": dict(self.adapter_request_counts),
            "total_requests": sum(self.adapter_request_counts.values()),
        }


# =============================================================================
# 10. FULL INFERENCE SERVER (Putting it all together)
# =============================================================================

class InferenceServer:
    """
    Complete inference server combining all components.
    
    vLLM-inspired architecture:
    - PagedAttention KV cache
    - Continuous batching
    - Multi-LoRA support
    - Priority scheduling
    - Token budgets
    - Health checks
    - Auto-scaling signals
    - Metrics export
    """
    
    def __init__(self, config: dict = None):
        config = config or {}
        
        # Core components
        self.engine = ContinuousBatchingEngine(
            max_batch_size=config.get("max_batch_size", 64),
            max_total_tokens=config.get("max_total_tokens", 32768),
        )
        self.model_manager = ModelManager(
            gpu_memory_gb=config.get("gpu_memory", {0: 80.0})
        )
        self.token_budget = TokenBudget()
        self.metrics = create_standard_metrics()
        self.health_checker = HealthChecker(self.model_manager)
        self.autoscaler = AutoScaler(
            min_replicas=config.get("min_replicas", 1),
            max_replicas=config.get("max_replicas", 8),
        )
        self.multi_lora = None  # Initialized after model load
        
        self.running = False
        self.request_count = 0
    
    def start(self, model_id: str, gpu_ids: list[int] = None):
        """Start the inference server."""
        gpu_ids = gpu_ids or [0]
        
        print(f"\n{'='*60}")
        print(f"Starting Inference Server")
        print(f"{'='*60}")
        
        success, msg = self.model_manager.load_model(model_id, gpu_ids)
        if not success:
            raise RuntimeError(f"Failed to load model: {msg}")
        
        self.multi_lora = MultiLoRAServer(model_id)
        self.running = True
        self.health_checker.is_ready = True
        
        print(f"[Server] Ready to serve requests")
        print(f"  Model: {model_id}")
        print(f"  GPUs: {gpu_ids}")
        print(f"  Max batch: {self.engine.max_batch_size}")
        print(f"  Max tokens: {self.engine.max_total_tokens}")
    
    def handle_request(self, request: InferenceRequest) -> dict:
        """Handle an inference request end-to-end."""
        self.request_count += 1
        
        # 1. Token budget check
        total_tokens = request.input_tokens + request.max_output_tokens
        allowed, reason = self.token_budget.check_budget(request.tenant_id, total_tokens)
        if not allowed:
            self.metrics.inc_counter("inference_requests_rejected", labels={"reason": reason})
            return {"status": "rejected", "reason": reason}
        
        # 2. Route LoRA adapter
        if self.multi_lora:
            self.multi_lora.route_request(request)
        
        # 3. Submit to engine
        self.engine.add_request(request)
        self.metrics.inc_counter("inference_requests_submitted")
        self.metrics.set_gauge("inference_queue_depth", len(self.engine.scheduler.heap))
        
        return {"status": "accepted", "request_id": request.request_id}
    
    def run_demo(self, num_requests: int = 50, num_steps: int = 200):
        """Run a demonstration of the server."""
        # Generate synthetic requests
        for i in range(num_requests):
            req = InferenceRequest(
                priority=random.choice([1, 2, 2, 2, 3]),
                arrival_time=time.time() + random.uniform(0, 0.1),
                input_tokens=random.randint(100, 2000),
                max_output_tokens=random.randint(50, 500),
                tenant_id=random.choice(["tenant_a", "tenant_b", "tenant_c"]),
                lora_adapter=random.choice([None, None, "customer_support", "code_gen"]),
            )
            self.handle_request(req)
        
        # Run engine
        self.engine.run(num_steps=num_steps, print_every=20)
        
        # Print final metrics
        print(f"\n{'='*60}")
        print("Server Metrics Summary")
        print(f"{'='*60}")
        print(f"  Total requests: {self.request_count}")
        print(f"  Completed: {len(self.engine.completed)}")
        print(f"  KV Cache utilization: {self.engine.kv_cache.utilization:.1%}")
        
        if self.multi_lora:
            stats = self.multi_lora.get_stats()
            print(f"  LoRA adapters active: {stats['num_adapters']}")
            print(f"  Adapter usage: {stats['adapter_usage']}")


# =============================================================================
# DEMO
# =============================================================================

def main():
    """Demonstrate all inference server components."""
    
    # --- Register models ---
    server = InferenceServer(config={
        "max_batch_size": 32,
        "max_total_tokens": 16384,
        "gpu_memory": {0: 80.0},
        "min_replicas": 1,
        "max_replicas": 8,
    })
    
    # Register model in registry
    llama_70b = ModelInfo(
        model_id="llama-70b-int4",
        size_gb=35.0,
        num_params_b=70.0,
        quantization="int4-awq",
    )
    server.model_manager.register_model(llama_70b)
    
    # Start server
    server.start("llama-70b-int4", gpu_ids=[0])
    
    # Register LoRA adapters
    adapters = [
        LoRAAdapter("customer_support", "llama-70b-int4", rank=16, size_mb=100),
        LoRAAdapter("code_gen", "llama-70b-int4", rank=32, size_mb=200),
        LoRAAdapter("medical_qa", "llama-70b-int4", rank=16, size_mb=100),
    ]
    for adapter in adapters:
        server.model_manager.load_adapter(adapter)
        server.multi_lora.register_adapter(adapter)
    
    # Set token budgets
    server.token_budget.set_tenant_limits("tenant_a", tokens_per_minute=50000, tokens_per_day=5000000)
    server.token_budget.set_tenant_limits("tenant_b", tokens_per_minute=100000, tokens_per_day=10000000)
    server.token_budget.set_tenant_limits("tenant_c", tokens_per_minute=20000, tokens_per_day=1000000)
    
    # Run demo
    server.run_demo(num_requests=80, num_steps=150)
    
    # --- Auto-scaling demo ---
    print(f"\n{'='*60}")
    print("Auto-Scaling Demo")
    print(f"{'='*60}")
    
    scaler = server.autoscaler
    
    # Simulate increasing load
    scenarios = [
        (0.4, 5, 1000, 200, "low load"),
        (0.6, 20, 3000, 500, "medium load"),
        (0.85, 80, 6000, 2000, "high load"),
        (0.92, 200, 8000, 4500, "overloaded"),
        (0.3, 0, 500, 100, "load dropped"),
    ]
    
    for util, queue, demand_tps, p99, desc in scenarios:
        scaler.record_metrics(util, queue, demand_tps, p99)
        decision = scaler.evaluate(util, queue, demand_tps, p99)
        print(f"  [{desc:12s}] util={util:.0%} queue={queue:3d} → {decision.action} "
              f"(replicas: {decision.current_replicas}→{decision.target_replicas}) | {decision.reason}")
        scaler.apply_decision(decision)
        # Reset cooldown for demo
        scaler.last_scale_up_time = 0
        scaler.last_scale_down_time = 0
        scaler.below_threshold_since = time.time() - 400  # Simulate time passed
    
    # --- Health check demo ---
    print(f"\n{'='*60}")
    print("Health Check")
    print(f"{'='*60}")
    
    hc = server.health_checker
    for _ in range(50):
        hc.record_request(random.uniform(100, 3000), random.random() > 0.03)
    
    status, details = hc.check_health()
    print(f"  Status: {status.value}")
    print(f"  Details: {details}")
    print(f"  Liveness: {hc.liveness_probe()}")
    print(f"  Readiness: {hc.readiness_probe()}")


if __name__ == "__main__":
    main()
