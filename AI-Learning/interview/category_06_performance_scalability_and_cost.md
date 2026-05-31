# Load Balancing and Performance for AI Systems (Questions 76-80)

## Q76: Design a load balancer for LLM inference that accounts for variable request costs

### Problem
Traditional round-robin or least-connections load balancing fails for LLM inference because a 100-token prompt vs a 10,000-token prompt can differ by 100x in GPU time. Design token-aware routing with queue management.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Token-Aware Load Balancer                  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐   ┌──────────────┐   ┌───────────────────┐   │
│  │ Request  │──▶│ Cost         │──▶│ Weighted Router    │   │
│  │ Intake   │   │ Estimator    │   │ (GPU-aware)        │   │
│  └──────────┘   └──────────────┘   └─────────┬─────────┘   │
│                                               │              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Priority Queue (per GPU node)               │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │   │
│  │  │ Short Q │  │ Medium Q│  │ Long Q  │              │   │
│  │  │ <512tok │  │ <4K tok │  │ >4K tok │              │   │
│  │  └─────────┘  └─────────┘  └─────────┘              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │              │              │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
    │ GPU Node│   │ GPU Node│   │ GPU Node│
    │ A80 x8  │   │ A80 x8  │   │ H100 x8│
    │ Load: 40%│   │ Load: 75%│   │ Load: 20%│
    └─────────┘   └─────────┘   └─────────┘
```

### Core Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from heapq import heappush, heappop
import tiktoken

@dataclass
class InferenceRequest:
    request_id: str
    prompt: str
    max_output_tokens: int
    priority: int = 0
    arrival_time: float = field(default_factory=time.time)
    estimated_cost: float = 0.0  # in GPU-seconds

@dataclass
class GPUNode:
    node_id: str
    gpu_type: str  # "A100", "H100"
    total_memory_gb: float
    current_load: float  # 0.0 to 1.0
    active_requests: int
    active_token_budget: int  # tokens currently being processed
    max_token_budget: int  # max concurrent tokens
    avg_tokens_per_second: float

class TokenAwareCostEstimator:
    def __init__(self):
        self.encoder = tiktoken.get_encoding("cl100k_base")
        # Learned coefficients from historical data
        self.prefill_cost_per_token = 0.0001  # GPU-seconds
        self.decode_cost_per_token = 0.0012   # GPU-seconds (10x prefill)
        self.overhead_seconds = 0.05

    def estimate_cost(self, request: InferenceRequest) -> float:
        input_tokens = len(self.encoder.encode(request.prompt))
        # Prefill cost scales quadratically with attention
        prefill_cost = self.prefill_cost_per_token * input_tokens * (1 + input_tokens / 8192)
        # Decode cost scales linearly with output tokens
        decode_cost = self.decode_cost_per_token * request.max_output_tokens
        return self.overhead_seconds + prefill_cost + decode_cost

    def classify_request(self, cost: float) -> str:
        if cost < 0.5:
            return "short"
        elif cost < 2.0:
            return "medium"
        return "long"


class TokenAwareLoadBalancer:
    def __init__(self, nodes: List[GPUNode]):
        self.nodes = {n.node_id: n for n in nodes}
        self.cost_estimator = TokenAwareCostEstimator()
        self.queues: Dict[str, List] = {
            "short": [], "medium": [], "long": []
        }
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def route_request(self, request: InferenceRequest) -> Optional[str]:
        """Route to optimal GPU node using weighted scoring."""
        request.estimated_cost = self.cost_estimator.estimate_cost(request)
        input_tokens = len(self.encoder.encode(request.prompt))
        
        best_node = None
        best_score = float('-inf')
        
        for node in self.nodes.values():
            # Check if node can accept the request
            if node.active_token_budget + input_tokens > node.max_token_budget:
                continue
            if node.current_load > 0.95:
                continue
            
            # Weighted scoring
            score = self._compute_node_score(node, request, input_tokens)
            if score > best_score:
                best_score = score
                best_node = node
        
        if best_node:
            self._assign_to_node(best_node, request, input_tokens)
            return best_node.node_id
        
        # Queue if no node available
        category = self.cost_estimator.classify_request(request.estimated_cost)
        heappush(self.queues[category], (request.estimated_cost, request))
        return None

    def _compute_node_score(self, node: GPUNode, request: InferenceRequest, 
                            input_tokens: int) -> float:
        # Prefer nodes with lower load (weight: 0.4)
        load_score = (1.0 - node.current_load) * 0.4
        
        # Prefer nodes with matching capacity profile (weight: 0.3)
        # Short requests → nearly full nodes (bin packing)
        # Long requests → empty nodes (avoid head-of-line blocking)
        if request.estimated_cost < 0.5:
            packing_score = node.current_load * 0.3  # Prefer fuller nodes
        else:
            packing_score = (1.0 - node.current_load) * 0.3  # Prefer emptier
        
        # Prefer faster GPUs for long requests (weight: 0.2)
        speed_multiplier = 2.0 if node.gpu_type == "H100" else 1.0
        speed_score = (speed_multiplier / 2.0) * 0.2
        
        # Token budget headroom (weight: 0.1)
        headroom = (node.max_token_budget - node.active_token_budget) / node.max_token_budget
        headroom_score = headroom * 0.1
        
        return load_score + packing_score + speed_score + headroom_score

    def _assign_to_node(self, node: GPUNode, request: InferenceRequest, 
                        input_tokens: int):
        node.active_requests += 1
        node.active_token_budget += input_tokens
        node.current_load = node.active_token_budget / node.max_token_budget

    async def drain_queues(self):
        """Periodically try to assign queued requests."""
        while True:
            for category in ["short", "medium", "long"]:
                while self.queues[category]:
                    cost, request = self.queues[category][0]
                    node_id = self.route_request(request)
                    if node_id:
                        heappop(self.queues[category])
                    else:
                        break
            await asyncio.sleep(0.1)
```

### Trade-offs

| Approach | Throughput | Latency Fairness | Complexity | GPU Utilization |
|----------|-----------|------------------|------------|-----------------|
| Round-robin | Low | Poor (HOL blocking) | Low | 40-60% |
| Least-connections | Medium | Medium | Low | 60-70% |
| Token-aware (this) | High | Good | High | 85-95% |
| Perfect scheduling | Highest | Best | Very High | 95%+ |

### Production Considerations

- **Calibration**: Cost estimator coefficients must be continuously calibrated against actual GPU time. Use exponential moving average with α=0.1.
- **Health checks**: Probe GPU nodes every 500ms; remove unhealthy nodes within 2s.
- **Spillover**: When all queues exceed threshold (e.g., 100 requests), trigger auto-scaling or reject with 429.
- **Metrics**: Track queue depth per category, p50/p99 wait time, GPU utilization, and cost estimation accuracy.
- **Continuous batching**: Modern inference engines (vLLM, TensorRT-LLM) support continuous batching. The load balancer should account for each node's batch capacity, not just connection count.

---

## Q77: Design auto-scaling for AI inference with cold-start problems

### Problem
Model loading takes 2 minutes (downloading weights + loading to GPU memory). Traditional reactive auto-scaling fails because by the time a new instance is ready, the traffic spike has either passed or caused cascading failures.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 Predictive Auto-Scaling System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────┐   ┌────────────────┐   ┌──────────────────┐    │
│  │ Traffic    │──▶│ Prediction     │──▶│ Scaling           │    │
│  │ Signals   │   │ Engine         │   │ Decision Engine   │    │
│  └────────────┘   └────────────────┘   └────────┬─────────┘    │
│                                                   │              │
│  ┌────────────────────────────────────────────────▼──────────┐  │
│  │                    Instance Pool                            │  │
│  │  ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌────────┐  │  │
│  │  │ Hot     │  │ Warm     │  │ Pre-warmed │  │ Cold   │  │  │
│  │  │(serving)│  │(loaded,  │  │(loading)   │  │(idle   │  │  │
│  │  │         │  │ idle)    │  │            │  │ GPU)   │  │  │
│  │  │ 10 inst │  │ 3 inst   │  │ 2 inst     │  │ 5 inst │  │  │
│  │  └─────────┘  └──────────┘  └────────────┘  └────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Core Implementation

```python
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List
from enum import Enum

class InstanceState(Enum):
    HOT = "hot"        # Serving traffic
    WARM = "warm"      # Model loaded, no traffic
    PREWARMING = "prewarming"  # Loading model
    COLD = "cold"      # GPU allocated, no model

@dataclass
class ScalingConfig:
    model_load_time_seconds: int = 120
    min_hot_instances: int = 3
    warm_pool_size: int = 3        # Always keep N warm
    prediction_horizon_minutes: int = 10  # Look ahead
    scale_up_threshold: float = 0.7  # GPU utilization
    scale_down_threshold: float = 0.3
    cooldown_seconds: int = 300

class PredictiveAutoScaler:
    def __init__(self, config: ScalingConfig):
        self.config = config
        self.traffic_history: List[float] = []  # RPM per minute
        self.capacity_per_instance: float = 50  # requests/min per GPU
    
    def predict_traffic(self, horizon_minutes: int = 10) -> List[float]:
        """Predict future traffic using multiple signals."""
        predictions = []
        
        # 1. Time-series forecast (seasonal decomposition)
        seasonal = self._get_seasonal_pattern()
        
        # 2. Trend from last 5 minutes (linear extrapolation)
        if len(self.traffic_history) >= 5:
            recent = self.traffic_history[-5:]
            slope = (recent[-1] - recent[0]) / 5
        else:
            slope = 0
        
        # 3. Rate of change acceleration (second derivative)
        if len(self.traffic_history) >= 10:
            recent_slope = (self.traffic_history[-1] - self.traffic_history[-5]) / 5
            older_slope = (self.traffic_history[-5] - self.traffic_history[-10]) / 5
            acceleration = recent_slope - older_slope
        else:
            acceleration = 0
        
        current = self.traffic_history[-1] if self.traffic_history else 0
        
        for t in range(1, horizon_minutes + 1):
            predicted = current + slope * t + 0.5 * acceleration * t**2
            # Blend with seasonal pattern
            hour = (datetime.now() + timedelta(minutes=t)).hour
            seasonal_factor = seasonal.get(hour, 1.0)
            predicted *= seasonal_factor
            # Add safety margin (20% buffer)
            predictions.append(predicted * 1.2)
        
        return predictions

    def compute_desired_instances(self) -> dict:
        """Determine how many instances in each state."""
        predicted_traffic = self.predict_traffic()
        peak_predicted = max(predicted_traffic)
        
        # Instances needed at peak
        instances_needed = int(np.ceil(peak_predicted / self.capacity_per_instance))
        instances_needed = max(instances_needed, self.config.min_hot_instances)
        
        # Current traffic needs
        current_traffic = self.traffic_history[-1] if self.traffic_history else 0
        current_needed = int(np.ceil(current_traffic / self.capacity_per_instance))
        current_needed = max(current_needed, self.config.min_hot_instances)
        
        # Traffic arriving within model_load_time needs warm instances NOW
        imminent_traffic = predicted_traffic[:2]  # Next 2 minutes
        imminent_needed = int(np.ceil(max(imminent_traffic) / self.capacity_per_instance))
        
        return {
            "hot": current_needed,
            "warm": max(self.config.warm_pool_size, imminent_needed - current_needed),
            "prewarming": max(0, instances_needed - imminent_needed),
            "total_target": instances_needed
        }

    def handle_traffic_spike(self, current_rpm: float, current_hot: int):
        """Emergency response for unexpected spikes."""
        utilization = current_rpm / (current_hot * self.capacity_per_instance)
        
        actions = []
        
        if utilization > 0.9:
            # CRITICAL: Activate all warm instances immediately
            actions.append(("activate_all_warm", "immediate"))
            # Start emergency pre-warming
            actions.append(("emergency_prewarm", 5))
            # Enable request queuing with timeout
            actions.append(("enable_queue", {"timeout": 30, "max_depth": 1000}))
            
        elif utilization > 0.7:
            # WARNING: Activate warm instances proportionally
            warm_to_activate = int(np.ceil((utilization - 0.7) / 0.1))
            actions.append(("activate_warm", warm_to_activate))
            # Start pre-warming replacements
            actions.append(("prewarm", warm_to_activate))
        
        # Shed load if necessary
        if utilization > 0.95:
            actions.append(("shed_load", {
                "strategy": "reject_lowest_priority",
                "target_utilization": 0.85
            }))
        
        return actions

    def _get_seasonal_pattern(self) -> dict:
        """Hourly traffic multipliers from historical data."""
        return {
            0: 0.3, 1: 0.2, 2: 0.15, 3: 0.1, 4: 0.1, 5: 0.2,
            6: 0.4, 7: 0.6, 8: 0.9, 9: 1.0, 10: 1.1, 11: 1.2,
            12: 1.0, 13: 1.1, 14: 1.2, 15: 1.1, 16: 1.0, 17: 0.9,
            18: 0.8, 19: 0.7, 20: 0.6, 21: 0.5, 22: 0.4, 23: 0.35
        }
```

### Trade-offs

| Strategy | Cold-Start Impact | Cost | Complexity | Spike Response |
|----------|------------------|------|------------|----------------|
| Reactive only | High (2 min gap) | Low | Low | Poor |
| Warm pool only | Medium | High (idle GPUs) | Medium | Good for small spikes |
| Predictive + Warm | Low | Medium-High | High | Good |
| Over-provision | None | Very High | Low | Excellent |
| This hybrid | Low | Medium | High | Excellent |

### Production Considerations

- **Model caching on local NVMe**: Pre-download model weights to instance storage. Reduces load time from 2 min to 30s.
- **GPU memory pre-allocation**: Keep CUDA context warm even on idle instances.
- **Gradual traffic shifting**: Don't slam 100% traffic to newly warmed instances. Ramp up over 30s.
- **Cost guardrails**: Set max instances cap. A prediction bug shouldn't bankrupt you.
- **Multi-model complexity**: If serving multiple models, warm pool needs per-model allocation strategy.

---

## Q78: Design a request prioritization system for AI API tiers

### Problem
During peak load (GPU capacity exhausted), you must ensure enterprise customers (paying $50K/month) get guaranteed service while gracefully degrading free tier users. Design preemption, SLA enforcement, and fair scheduling.

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
│              Multi-Tier Priority System                         │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  Incoming Requests                                             │
│       │                                                        │
│       ▼                                                        │
│  ┌──────────────────┐                                         │
│  │ Tier Classifier  │──── API Key → Tier + Quota              │
│  └────────┬─────────┘                                         │
│           │                                                    │
│     ┌─────┼─────────────────┐                                 │
│     │     │                 │                                  │
│     ▼     ▼                 ▼                                  │
│  ┌─────┐ ┌─────┐      ┌─────────┐                            │
│  │ P0  │ │ P1  │      │ P2      │                            │
│  │Enter│ │ Pro │      │ Free    │                            │
│  │prise│ │     │      │         │                            │
│  │     │ │     │      │ (sheddable)                          │
│  └──┬──┘ └──┬──┘      └────┬────┘                            │
│     │        │              │                                  │
│     ▼        ▼              ▼                                  │
│  ┌─────────────────────────────────────┐                      │
│  │     Weighted Fair Queue (WFQ)        │                      │
│  │  Enterprise: 60% │ Pro: 30% │ Free: 10%                   │
│  └──────────────────┬──────────────────┘                      │
│                     │                                          │
│                     ▼                                          │
│  ┌─────────────────────────────────────┐                      │
│  │     GPU Admission Controller         │                      │
│  │  - Token budget enforcement          │                      │
│  │  - Preemption decisions              │                      │
│  └─────────────────────────────────────┘                      │
└───────────────────────────────────────────────────────────────┘
```

### Core Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Optional, List
from collections import defaultdict
import heapq

class Tier(IntEnum):
    ENTERPRISE = 0  # Highest priority
    PRO = 1
    FREE = 2

@dataclass
class TierConfig:
    weight: float              # Share of GPU capacity
    max_queue_depth: int       # Max waiting requests
    max_wait_seconds: float    # SLA: max queue wait
    preemptible: bool          # Can be preempted by higher tier
    rate_limit_rpm: int        # Requests per minute
    max_concurrent: int        # Max concurrent requests
    fallback_model: Optional[str] = None  # Degraded model option

TIER_CONFIGS = {
    Tier.ENTERPRISE: TierConfig(
        weight=0.6, max_queue_depth=1000, max_wait_seconds=2.0,
        preemptible=False, rate_limit_rpm=10000, max_concurrent=500
    ),
    Tier.PRO: TierConfig(
        weight=0.3, max_queue_depth=500, max_wait_seconds=10.0,
        preemptible=False, rate_limit_rpm=1000, max_concurrent=100
    ),
    Tier.FREE: TierConfig(
        weight=0.1, max_queue_depth=100, max_wait_seconds=30.0,
        preemptible=True, rate_limit_rpm=60, max_concurrent=10,
        fallback_model="gpt-3.5-turbo"
    ),
}

@dataclass(order=True)
class PrioritizedRequest:
    priority: float  # Lower = higher priority
    request_id: str = field(compare=False)
    tier: Tier = field(compare=False)
    arrival_time: float = field(compare=False)
    estimated_tokens: int = field(compare=False)
    customer_id: str = field(compare=False)

class PriorityScheduler:
    def __init__(self, total_gpu_capacity: int = 100):
        self.total_capacity = total_gpu_capacity  # Concurrent request slots
        self.tier_configs = TIER_CONFIGS
        self.queues: Dict[Tier, List] = {t: [] for t in Tier}
        self.active: Dict[Tier, int] = {t: 0 for t in Tier}
        self.customer_concurrent: Dict[str, int] = defaultdict(int)
        self.sla_violations: Dict[Tier, int] = defaultdict(int)

    def submit_request(self, request: PrioritizedRequest) -> str:
        """Returns: 'accepted', 'queued', 'rejected', or 'degraded'."""
        config = self.tier_configs[request.tier]
        
        # Rate limit check
        if not self._check_rate_limit(request.customer_id, config):
            return "rejected"
        
        # Check if we can serve immediately
        if self._can_admit(request.tier):
            self._admit(request)
            return "accepted"
        
        # Queue if capacity allows
        if len(self.queues[request.tier]) < config.max_queue_depth:
            # Priority within tier: arrival time + customer fairness
            priority = self._compute_intra_tier_priority(request)
            request.priority = priority
            heapq.heappush(self.queues[request.tier], request)
            
            # For free tier, offer degraded model immediately
            if request.tier == Tier.FREE and config.fallback_model:
                return "degraded"
            return "queued"
        
        # Attempt preemption for high-priority requests
        if request.tier == Tier.ENTERPRISE:
            if self._preempt_lower_tier(request):
                return "accepted"
        
        return "rejected"

    def _can_admit(self, tier: Tier) -> bool:
        """Check if tier has capacity (weighted fair share)."""
        config = self.tier_configs[tier]
        tier_capacity = int(self.total_capacity * config.weight)
        
        # Allow borrowing unused capacity from lower tiers
        unused = sum(
            int(self.total_capacity * self.tier_configs[t].weight) - self.active[t]
            for t in Tier if t > tier  # Lower priority tiers
        )
        effective_capacity = tier_capacity + max(0, unused)
        
        return self.active[tier] < effective_capacity

    def _preempt_lower_tier(self, request: PrioritizedRequest) -> bool:
        """Preempt a free-tier request to serve enterprise."""
        for tier in reversed(list(Tier)):
            if tier <= request.tier:
                continue
            config = self.tier_configs[tier]
            if config.preemptible and self.active[tier] > 0:
                self.active[tier] -= 1
                self._admit(request)
                return True
        return False

    def _compute_intra_tier_priority(self, request: PrioritizedRequest) -> float:
        """Fair scheduling within a tier - prevent single customer starvation."""
        # Customers with fewer active requests get priority
        customer_load = self.customer_concurrent[request.customer_id]
        # Combine with arrival time for FIFO within same load level
        return customer_load * 1000 + request.arrival_time

    def _admit(self, request: PrioritizedRequest):
        self.active[request.tier] += 1
        self.customer_concurrent[request.customer_id] += 1

    def release(self, request: PrioritizedRequest):
        """Called when request completes."""
        self.active[request.tier] -= 1
        self.customer_concurrent[request.customer_id] -= 1
        # Try to dequeue waiting requests
        self._process_queues()

    def _process_queues(self):
        """Process queues in priority order."""
        for tier in Tier:
            while self.queues[tier] and self._can_admit(tier):
                request = heapq.heappop(self.queues[tier])
                wait_time = time.time() - request.arrival_time
                config = self.tier_configs[tier]
                if wait_time > config.max_wait_seconds:
                    self.sla_violations[tier] += 1
                    continue  # Drop expired requests
                self._admit(request)

    def _check_rate_limit(self, customer_id: str, config: TierConfig) -> bool:
        # Sliding window rate limiter (simplified)
        return True  # Implementation uses Redis sliding window

    def get_sla_report(self) -> dict:
        return {
            "active_by_tier": dict(self.active),
            "queue_depth_by_tier": {t.name: len(q) for t, q in self.queues.items()},
            "sla_violations": dict(self.sla_violations),
            "gpu_utilization": sum(self.active.values()) / self.total_capacity
        }
```

### Trade-offs

| Strategy | Enterprise SLA | Free User Experience | Revenue Impact | Complexity |
|----------|---------------|---------------------|----------------|------------|
| Strict priority | 99.99% | Terrible during peaks | Churn risk (free→paid) | Low |
| Weighted fair | 99.9% | Acceptable | Balanced | Medium |
| This (weighted + preemption) | 99.99% | Degraded gracefully | Optimal | High |
| Over-provision | 99.99% | Good | High cost | Low |

### Production Considerations

- **SLA monitoring**: Alert if enterprise p99 wait > 500ms. Page on-call if > 2s.
- **Graceful degradation**: Free tier gets smaller model, shorter max_tokens, or cached responses during overload.
- **Burst handling**: Enterprise customers get 2x their steady-state allocation for 60s bursts.
- **Fairness within enterprise**: Large enterprise accounts shouldn't starve smaller ones. Use per-customer fair share.
- **Observability**: Dashboard showing real-time tier utilization, queue depths, and preemption rates.

---

## Q79: Design traffic management for 1M concurrent WebSocket connections for streaming LLM responses

### Problem
Each LLM response streams tokens over a WebSocket. With 1M concurrent connections, you need efficient connection management, backpressure handling (what if client can't consume tokens fast enough), and graceful degradation.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Global Edge Layer                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Edge PoP │ │ Edge PoP │ │ Edge PoP │ │ Edge PoP │      │
│  │ 250K conn│ │ 250K conn│ │ 250K conn│ │ 250K conn│      │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
└───────┼─────────────┼─────────────┼─────────────┼───────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│              WebSocket Gateway Cluster                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Connection Manager (per node: 50K connections)       │   │
│  │  - epoll/kqueue for I/O multiplexing                  │   │
│  │  - Per-connection send buffer (4KB)                   │   │
│  │  - Backpressure detection                             │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Token Stream Router                                   │   │
│  │  - Subscribe to inference output stream               │   │
│  │  - Fan-out tokens to correct WebSocket                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  Message Bus (Redis Streams / Kafka)                         │
│  - Partition by request_id                                   │
│  - Token-level messages from inference nodes                 │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  GPU Inference Cluster                                       │
│  - Produces token stream per request                         │
│  - Publishes to message bus                                  │
└─────────────────────────────────────────────────────────────┘
```

### Core Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Optional
from enum import Enum
import weakref

class BackpressureState(Enum):
    NORMAL = "normal"          # Client consuming fine
    SLOW = "slow"              # Client falling behind
    BLOCKED = "blocked"        # Client not consuming at all
    DISCONNECTED = "disconnected"

@dataclass
class ConnectionState:
    connection_id: str
    request_id: str
    customer_id: str
    tier: str
    created_at: float
    send_buffer_size: int = 0
    max_buffer_size: int = 4096  # bytes
    tokens_sent: int = 0
    tokens_buffered: int = 0
    last_ack_time: float = field(default_factory=time.time)
    backpressure: BackpressureState = BackpressureState.NORMAL

class WebSocketGateway:
    """Manages up to 50K connections per node."""
    
    def __init__(self, node_id: str, max_connections: int = 50000):
        self.node_id = node_id
        self.max_connections = max_connections
        self.connections: Dict[str, ConnectionState] = {}
        self.request_to_conn: Dict[str, str] = {}  # request_id → connection_id
        self.backpressure_connections: Set[str] = set()
        
    async def handle_new_connection(self, websocket, connection_id: str, 
                                     request_id: str, customer_id: str, tier: str):
        """Register new streaming connection."""
        if len(self.connections) >= self.max_connections:
            await websocket.close(4029, "Server at capacity")
            return
        
        state = ConnectionState(
            connection_id=connection_id,
            request_id=request_id,
            customer_id=customer_id,
            tier=tier,
            created_at=time.time()
        )
        self.connections[connection_id] = state
        self.request_to_conn[request_id] = connection_id
        
        # Start streaming tokens to this connection
        try:
            await self._stream_tokens(websocket, state)
        finally:
            self._cleanup_connection(connection_id)

    async def _stream_tokens(self, websocket, state: ConnectionState):
        """Stream tokens with backpressure handling."""
        async for token in self._subscribe_to_tokens(state.request_id):
            # Check backpressure
            if state.backpressure == BackpressureState.BLOCKED:
                # Buffer up to limit, then drop or pause inference
                if state.tokens_buffered > 100:
                    await self._pause_inference(state.request_id)
                    # Wait for client to catch up
                    await self._wait_for_drain(state, timeout=30)
                    if state.backpressure == BackpressureState.BLOCKED:
                        # Client gone, abort
                        await self._cancel_inference(state.request_id)
                        return
                    await self._resume_inference(state.request_id)
                state.tokens_buffered += 1
                continue
            
            try:
                # Non-blocking send with write buffer monitoring
                await asyncio.wait_for(
                    websocket.send(token),
                    timeout=5.0
                )
                state.tokens_sent += 1
                state.last_ack_time = time.time()
                state.send_buffer_size = websocket.transport.get_write_buffer_size()
                
                # Update backpressure state
                self._update_backpressure(state)
                
            except asyncio.TimeoutError:
                state.backpressure = BackpressureState.BLOCKED
                self.backpressure_connections.add(state.connection_id)

    def _update_backpressure(self, state: ConnectionState):
        """Detect slow consumers."""
        if state.send_buffer_size > state.max_buffer_size * 0.8:
            state.backpressure = BackpressureState.SLOW
            self.backpressure_connections.add(state.connection_id)
        elif state.send_buffer_size < state.max_buffer_size * 0.3:
            state.backpressure = BackpressureState.NORMAL
            self.backpressure_connections.discard(state.connection_id)

    async def _pause_inference(self, request_id: str):
        """Signal inference to pause generation for this request."""
        # Publish pause signal to message bus
        pass

    async def _resume_inference(self, request_id: str):
        """Signal inference to resume generation."""
        pass

    async def _cancel_inference(self, request_id: str):
        """Abort inference, free GPU resources."""
        pass

    async def _wait_for_drain(self, state: ConnectionState, timeout: float):
        """Wait for client buffer to drain."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if state.backpressure != BackpressureState.BLOCKED:
                return
            await asyncio.sleep(0.5)

    async def _subscribe_to_tokens(self, request_id: str):
        """Subscribe to token stream from message bus."""
        # Redis Streams XREAD or Kafka consumer
        pass

    def _cleanup_connection(self, connection_id: str):
        state = self.connections.pop(connection_id, None)
        if state:
            self.request_to_conn.pop(state.request_id, None)
            self.backpressure_connections.discard(connection_id)

    def get_metrics(self) -> dict:
        return {
            "active_connections": len(self.connections),
            "backpressured_connections": len(self.backpressure_connections),
            "utilization": len(self.connections) / self.max_connections,
        }


class ConnectionLoadBalancer:
    """Distributes new connections across gateway nodes."""
    
    def __init__(self, gateway_nodes: list):
        self.nodes = gateway_nodes  # List of WebSocketGateway references
    
    def select_node(self, customer_id: str) -> str:
        """Select gateway node for new connection."""
        # Least-connections with sticky routing for same customer
        # (helps with connection limits per customer)
        best_node = min(
            self.nodes,
            key=lambda n: len(n.connections)
        )
        return best_node.node_id
```

### Scaling Math

| Component | Per Node | Nodes Needed | Total Capacity |
|-----------|----------|--------------|----------------|
| Edge PoP | 250K connections | 4 | 1M |
| WS Gateway | 50K connections | 20 | 1M |
| Memory per conn | ~8KB | - | ~8GB per node |
| Token throughput | 500K tokens/s | 20 nodes | 10M tokens/s |

### Production Considerations

- **Connection draining**: Before node restart, drain connections over 30s by stopping new assignments and letting active streams complete.
- **Heartbeat**: Ping every 30s. Close connections with no pong in 90s. Frees resources from zombie connections.
- **Memory management**: 1M connections × 8KB = 8GB just for connection state. Use memory-mapped buffers and zero-copy where possible.
- **Backpressure propagation**: If 10% of connections are backpressured, signal inference cluster to slow down batch scheduling.
- **Reconnection**: Client SDK should support transparent reconnection with token position tracking (resume from token #47).

---

## Q80: Design global traffic routing for AI inference across GPU clusters

### Problem
You have GPU clusters in 5 regions with different model availability, costs, and current load. Route each request to the optimal cluster considering latency, cost, model availability, and capacity.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Global Traffic Router                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐     ┌──────────────────────┐                   │
│  │ DNS/Anycast │────▶│ Regional Edge Router  │                   │
│  │ (GeoDNS)    │     │ (per PoP)            │                   │
│  └─────────────┘     └──────────┬───────────┘                   │
│                                  │                                │
│                    ┌─────────────▼──────────────┐                │
│                    │   Routing Decision Engine   │                │
│                    │                             │                │
│                    │  Inputs:                    │                │
│                    │  - Model required           │                │
│                    │  - Client location          │                │
│                    │  - Request priority         │                │
│                    │  - Cost budget              │                │
│                    │                             │                │
│                    │  State (updated every 1s):  │                │
│                    │  - Cluster load % per model │                │
│                    │  - Network latency matrix   │                │
│                    │  - Spot capacity available  │                │
│                    │  - Cost per token per region│                │
│                    └─────────────┬──────────────┘                │
│                                  │                                │
│         ┌────────────┬───────────┼───────────┬────────────┐      │
│         ▼            ▼           ▼           ▼            ▼      │
│    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│
│    │US-East  │ │US-West  │ │EU-West  │ │AP-South │ │AP-East  ││
│    │H100 x64 │ │A100 x128│ │H100 x32 │ │A100 x64 │ │H100 x64 ││
│    │GPT-4,   │ │All      │ │GPT-4,   │ │Llama,   │ │All      ││
│    │Claude   │ │models   │ │Llama    │ │Mistral  │ │models   ││
│    │$0.03/1K │ │$0.025/1K│ │$0.035/1K│ │$0.02/1K │ │$0.028/1K││
│    │Load: 70%│ │Load: 45%│ │Load: 80%│ │Load: 30%│ │Load: 55%││
│    └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Core Implementation

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import time
import math

@dataclass
class ClusterState:
    cluster_id: str
    region: str
    gpu_type: str
    total_gpus: int
    current_load: float          # 0.0 to 1.0
    available_models: Set[str]
    cost_per_1k_tokens: float    # USD
    avg_inference_latency_ms: float
    queue_depth: int
    healthy: bool
    last_updated: float

@dataclass
class RoutingRequest:
    request_id: str
    model: str
    client_region: str
    priority: str            # "critical", "normal", "batch"
    cost_sensitive: bool     # Prefer cheaper cluster
    max_latency_ms: float    # SLA requirement
    estimated_tokens: int

@dataclass  
class RoutingDecision:
    cluster_id: str
    score: float
    estimated_latency_ms: float
    estimated_cost: float
    reason: str

class GlobalTrafficRouter:
    # Network latency matrix (ms) between regions
    LATENCY_MATRIX = {
        ("us-east", "us-east"): 5,
        ("us-east", "us-west"): 40,
        ("us-east", "eu-west"): 80,
        ("us-east", "ap-south"): 180,
        ("us-east", "ap-east"): 150,
        ("us-west", "us-west"): 5,
        ("us-west", "eu-west"): 120,
        ("us-west", "ap-south"): 200,
        ("us-west", "ap-east"): 100,
        ("eu-west", "eu-west"): 5,
        ("eu-west", "ap-south"): 120,
        ("eu-west", "ap-east"): 160,
        ("ap-south", "ap-south"): 5,
        ("ap-south", "ap-east"): 80,
        ("ap-east", "ap-east"): 5,
    }

    def __init__(self):
        self.clusters: Dict[str, ClusterState] = {}
        self.routing_weights = {
            "critical": {"latency": 0.5, "load": 0.3, "cost": 0.0, "reliability": 0.2},
            "normal":   {"latency": 0.3, "load": 0.3, "cost": 0.2, "reliability": 0.2},
            "batch":    {"latency": 0.1, "load": 0.2, "cost": 0.6, "reliability": 0.1},
        }

    def route(self, request: RoutingRequest) -> RoutingDecision:
        """Select optimal cluster for request."""
        candidates = self._filter_candidates(request)
        
        if not candidates:
            # Fallback: any healthy cluster with the model, ignore load
            candidates = [
                c for c in self.clusters.values()
                if c.healthy and request.model in c.available_models
            ]
        
        if not candidates:
            raise NoCapacityError(f"No cluster available for model {request.model}")
        
        # Score each candidate
        scored = []
        for cluster in candidates:
            score = self._score_cluster(cluster, request)
            scored.append((score, cluster))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_cluster = scored[0]
        
        network_latency = self._get_latency(request.client_region, best_cluster.region)
        total_latency = network_latency + best_cluster.avg_inference_latency_ms
        cost = (request.estimated_tokens / 1000) * best_cluster.cost_per_1k_tokens
        
        return RoutingDecision(
            cluster_id=best_cluster.cluster_id,
            score=best_score,
            estimated_latency_ms=total_latency,
            estimated_cost=cost,
            reason=f"Best score: latency={network_latency}ms, load={best_cluster.current_load:.0%}"
        )

    def _filter_candidates(self, request: RoutingRequest) -> List[ClusterState]:
        """Filter to eligible clusters."""
        candidates = []
        for cluster in self.clusters.values():
            if not cluster.healthy:
                continue
            if request.model not in cluster.available_models:
                continue
            if cluster.current_load > 0.95:
                continue
            # Check if latency SLA can be met
            network_latency = self._get_latency(request.client_region, cluster.region)
            if network_latency + cluster.avg_inference_latency_ms > request.max_latency_ms:
                continue
            candidates.append(cluster)
        return candidates

    def _score_cluster(self, cluster: ClusterState, request: RoutingRequest) -> float:
        """Multi-objective scoring."""
        weights = self.routing_weights[request.priority]
        
        # Latency score (0-1, lower latency = higher score)
        network_latency = self._get_latency(request.client_region, cluster.region)
        max_latency = 200  # normalization factor
        latency_score = 1.0 - min(network_latency / max_latency, 1.0)
        
        # Load score (prefer less loaded clusters)
        load_score = 1.0 - cluster.current_load
        
        # Cost score (cheaper = higher score)
        max_cost = 0.04  # most expensive region
        cost_score = 1.0 - (cluster.cost_per_1k_tokens / max_cost)
        
        # Reliability score (based on recent error rate and staleness)
        staleness = time.time() - cluster.last_updated
        reliability_score = 1.0 if staleness < 5 else max(0, 1.0 - staleness / 60)
        
        total = (
            weights["latency"] * latency_score +
            weights["load"] * load_score +
            weights["cost"] * cost_score +
            weights["reliability"] * reliability_score
        )
        
        return total

    def _get_latency(self, region_a: str, region_b: str) -> float:
        key = (region_a, region_b)
        if key in self.LATENCY_MATRIX:
            return self.LATENCY_MATRIX[key]
        key = (region_b, region_a)
        return self.LATENCY_MATRIX.get(key, 200)

    def update_cluster_state(self, cluster_id: str, state: ClusterState):
        """Called every 1s by health check system."""
        self.clusters[cluster_id] = state


class NoCapacityError(Exception):
    pass
```

### Trade-offs

| Routing Strategy | Latency | Cost | Complexity | Failover Speed |
|-----------------|---------|------|------------|----------------|
| Nearest region | Best | High | Low | Slow |
| Cheapest region | Poor | Best | Low | Slow |
| Least loaded | Medium | Medium | Medium | Fast |
| Multi-objective (this) | Optimized | Optimized | High | Fast |

### Production Considerations

- **State propagation delay**: Cluster load info is 1-5s stale. Over-route to a cluster and it spikes. Use dampening: route max 10% above fair share per decision cycle.
- **Data sovereignty**: Some requests must stay in EU (GDPR). Add hard constraints to filtering.
- **Failover cascading**: If US-East fails, don't slam all traffic to US-West. Spread across all remaining regions proportionally.
- **Cost arbitrage**: Batch/async requests to cheapest region (AP-South at $0.02/1K). Real-time to nearest.
- **A/B testing routing**: Route 5% of traffic with alternative weights to discover better scoring parameters.
- **DNS TTL**: Keep TTL at 30s for fast failover. Use anycast for instant regional routing.
# Latency Optimization for AI Systems (Questions 81-85)

## Q81: Systematic latency reduction from 3s p99 to 500ms for LLM-powered search

### Problem
Your LLM-powered search pipeline has: query understanding (200ms) → retrieval (300ms) → LLM generation (2500ms) = 3s p99. Reduce to 500ms without sacrificing quality.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 Optimized Search Pipeline                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Layer 1: Cache (p99 < 50ms for cache hits)               │   │
│  │  - Semantic cache (embedding similarity > 0.95)           │   │
│  │  - Exact query cache (Redis, TTL=5min)                    │   │
│  │  - Expected hit rate: 30-40%                              │   │
│  └───────────────────────────┬──────────────────────────────┘   │
│                              │ cache miss                         │
│  ┌───────────────────────────▼──────────────────────────────┐   │
│  │ Layer 2: Speculative Execution (parallel, not serial)     │   │
│  │                                                           │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │   │
│  │  │ Query      │  │ Retrieval  │  │ Speculative LLM    │ │   │
│  │  │ Understand │  │ (sparse +  │  │ (start with query  │ │   │
│  │  │ (50ms)     │  │ dense)     │  │  alone, refine)    │ │   │
│  │  └─────┬──────┘  │ (100ms)   │  │ (starts at t=0)    │ │   │
│  │        │          └─────┬─────┘  └──────────┬─────────┘ │   │
│  │        └────────────────┼────────────────────┘           │   │
│  └─────────────────────────┼────────────────────────────────┘   │
│                            │                                     │
│  ┌─────────────────────────▼────────────────────────────────┐   │
│  │ Layer 3: Fast Model (distilled, 100ms generation)         │   │
│  │  - 7B parameter model distilled from GPT-4                │   │
│  │  - Quantized INT8, served on optimized runtime            │   │
│  │  - Quality: 92% of GPT-4 on search-specific benchmarks   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Total: 50ms (cache) + 100ms (retrieval) + 100ms (fast LLM)    │
│       = 250ms p50, ~450ms p99                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import hashlib
import time
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

@dataclass
class SearchResult:
    answer: str
    sources: list
    latency_ms: float
    cache_hit: bool
    model_used: str

class OptimizedSearchPipeline:
    def __init__(self):
        self.exact_cache = RedisCache(ttl_seconds=300)
        self.semantic_cache = SemanticCache(threshold=0.95, max_entries=1_000_000)
        self.fast_model = DistilledSearchModel("search-7b-int8")  
        self.full_model = LargeModel("gpt-4")
        self.retriever = HybridRetriever()
        
    async def search(self, query: str, max_latency_ms: float = 500) -> SearchResult:
        start = time.time()
        
        # Layer 1: Cache lookup (parallel exact + semantic)
        cache_result = await self._check_caches(query)
        if cache_result:
            return SearchResult(
                answer=cache_result, sources=[], 
                latency_ms=(time.time() - start) * 1000,
                cache_hit=True, model_used="cache"
            )
        
        # Layer 2: Parallel execution
        # Start retrieval AND speculative generation simultaneously
        retrieval_task = asyncio.create_task(self.retriever.search(query, top_k=5))
        
        # Speculative: generate with query alone (will be refined or discarded)
        speculative_task = asyncio.create_task(
            self.fast_model.generate(
                f"Answer concisely: {query}",
                max_tokens=150,
                timeout_ms=200
            )
        )
        
        # Wait for retrieval (critical path)
        docs = await retrieval_task
        retrieval_latency = (time.time() - start) * 1000
        
        # Remaining time budget
        remaining_ms = max_latency_ms - retrieval_latency - 50  # 50ms buffer
        
        if remaining_ms < 100:
            # Use speculative result if retrieval was slow
            speculative_answer = await speculative_task
            return SearchResult(
                answer=speculative_answer, sources=docs,
                latency_ms=(time.time() - start) * 1000,
                cache_hit=False, model_used="speculative"
            )
        
        # Cancel speculative, use grounded generation
        speculative_task.cancel()
        
        # Layer 3: Fast grounded generation
        context = "\n".join([d.text[:500] for d in docs[:3]])
        prompt = f"Context:\n{context}\n\nQuestion: {query}\nAnswer concisely:"
        
        answer = await self.fast_model.generate(
            prompt, max_tokens=150, timeout_ms=int(remaining_ms)
        )
        
        total_latency = (time.time() - start) * 1000
        
        # Async: cache the result, don't block response
        asyncio.create_task(self._cache_result(query, answer))
        
        # Async: quality check with full model (for monitoring, not blocking)
        asyncio.create_task(self._async_quality_check(query, answer, docs))
        
        return SearchResult(
            answer=answer, sources=docs,
            latency_ms=total_latency,
            cache_hit=False, model_used="search-7b"
        )

    async def _check_caches(self, query: str) -> Optional[str]:
        """Parallel cache lookup."""
        exact_task = asyncio.create_task(self.exact_cache.get(query))
        semantic_task = asyncio.create_task(self.semantic_cache.get(query))
        
        exact, semantic = await asyncio.gather(exact_task, semantic_task)
        return exact or semantic

    async def _cache_result(self, query: str, answer: str):
        await asyncio.gather(
            self.exact_cache.set(query, answer),
            self.semantic_cache.set(query, answer)
        )

    async def _async_quality_check(self, query: str, fast_answer: str, docs: list):
        """Background quality monitoring - not in critical path."""
        full_answer = await self.full_model.generate(
            f"Rate this answer 1-5 for accuracy given the docs: {fast_answer}"
        )
        # Log quality score for model monitoring
        # Alert if quality drops below threshold


class SemanticCache:
    """Cache that matches semantically similar queries."""
    
    def __init__(self, threshold: float = 0.95, max_entries: int = 1_000_000):
        self.threshold = threshold
        self.embeddings = None  # FAISS index
        self.answers = {}
        
    async def get(self, query: str) -> Optional[str]:
        query_embedding = await embed(query)
        # FAISS search: O(log n) with IVF index
        distances, indices = self.embeddings.search(query_embedding, k=1)
        if distances[0][0] > self.threshold:
            return self.answers[indices[0][0]]
        return None
```

### Latency Breakdown Comparison

| Stage | Before | After | Technique |
|-------|--------|-------|-----------|
| Cache check | N/A | 5ms | Semantic + exact cache |
| Query understanding | 200ms | 0ms (removed) | Merged into retrieval |
| Retrieval | 300ms | 100ms | Pre-computed indexes, parallel sparse+dense |
| LLM generation | 2500ms | 100ms | Distilled 7B INT8 model |
| **Total (cache miss)** | **3000ms** | **250ms** | |
| **Total (cache hit)** | **3000ms** | **5ms** | |
| **Blended p99** | **3000ms** | **~450ms** | 35% cache hit rate |

### Production Considerations

- **Quality regression monitoring**: Continuously compare fast model output with full model. Alert if agreement drops below 90%.
- **Cache invalidation**: When source documents update, invalidate semantic cache entries that referenced them. Use document fingerprinting.
- **Adaptive timeout**: If p99 is well under 500ms, allow full model for complex queries. Dynamically route based on latency budget.
- **Model distillation pipeline**: Weekly distillation from GPT-4 on search-specific data. Automated quality gate before deployment.
- **Fallback chain**: fast_model → speculative → cached_similar → "I don't know" (never exceed SLA).

---

## Q82: Streaming architecture for time-to-first-token < 200ms with quality

### Problem
Users perceive responsiveness by time-to-first-token (TTFT). Standard LLM inference has 500ms-2s TTFT due to prefill. Design an architecture achieving <200ms TTFT while maintaining output quality.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│            Ultra-Low TTFT Streaming Architecture              │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Client Request                                               │
│       │                                                       │
│       ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Speculative Prefill Router                               │ │
│  │                                                          │ │
│  │  ┌───────────┐     ┌───────────────┐                   │ │
│  │  │ Draft     │────▶│ Speculative    │                   │ │
│  │  │ Model     │     │ Decoder        │                   │ │
│  │  │ (1B, 30ms│     │ (generates 5   │                   │ │
│  │  │  prefill) │     │  tokens ahead) │                   │ │
│  │  └───────────┘     └───────┬───────┘                   │ │
│  │                            │                             │ │
│  │                            ▼                             │ │
│  │  ┌───────────────────────────────────────────────────┐  │ │
│  │  │ Verification Model (70B)                           │  │ │
│  │  │ - Verifies draft tokens in parallel                │  │ │
│  │  │ - Accepts correct tokens, regenerates wrong ones   │  │ │
│  │  │ - Net: 3-4 tokens accepted per verification step   │  │ │
│  │  └───────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Streaming Output Buffer                                  │ │
│  │  - Sends tokens as soon as verified                      │ │
│  │  - Buffers 1 sentence for early stop evaluation          │ │
│  │  - SSE/WebSocket to client                               │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from typing import AsyncGenerator, List, Optional
from dataclasses import dataclass

@dataclass
class StreamConfig:
    max_ttft_ms: float = 200
    draft_model: str = "llama-1b"
    target_model: str = "llama-70b"
    speculation_length: int = 5    # tokens to speculate ahead
    max_output_tokens: int = 1024
    use_kv_cache_sharing: bool = True

class SpeculativeStreamingEngine:
    def __init__(self, config: StreamConfig):
        self.config = config
        self.draft = DraftModel(config.draft_model)       # 1B model, 30ms prefill
        self.target = TargetModel(config.target_model)    # 70B model, 400ms prefill
        
    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream tokens with speculative decoding for low TTFT."""
        start = time.time()
        
        # Phase 1: Start draft model immediately (low TTFT)
        # Draft model prefills in ~30ms vs ~400ms for target
        draft_kv = await self.draft.prefill(prompt)  # ~30ms
        
        # Start target model prefill in background
        target_prefill_task = asyncio.create_task(
            self.target.prefill(prompt)
        )
        
        # Generate first tokens from draft model immediately
        draft_tokens = []
        async for token in self.draft.generate(draft_kv, max_tokens=self.config.speculation_length):
            draft_tokens.append(token)
            # Yield first token ASAP from draft
            if len(draft_tokens) == 1:
                ttft = (time.time() - start) * 1000
                # First token from draft model: ~50ms total
                yield token
        
        # Phase 2: Target model verifies draft tokens
        target_kv = await target_prefill_task  # Should be ready by now (~400ms)
        
        # Verify draft tokens in one forward pass (parallel verification)
        verified_count = await self.target.verify_tokens(
            target_kv, draft_tokens
        )
        
        # If draft was wrong, regenerate from target
        if verified_count < len(draft_tokens):
            # Send correction signal (optional: for rewrite-capable clients)
            yield f"\x00REWIND:{len(draft_tokens) - verified_count}"
            
            # Continue from verified position with target model
            async for token in self._target_decode_loop(target_kv, verified_count):
                yield token
        else:
            # Draft was correct, continue with speculative decoding loop
            async for token in self._speculative_decode_loop(draft_kv, target_kv):
                yield token

    async def _speculative_decode_loop(self, draft_kv, target_kv) -> AsyncGenerator[str, None]:
        """Main speculative decoding loop after initial tokens."""
        tokens_generated = 0
        
        while tokens_generated < self.config.max_output_tokens:
            # Draft generates K tokens speculatively
            draft_tokens = []
            async for token in self.draft.generate(draft_kv, max_tokens=self.config.speculation_length):
                draft_tokens.append(token)
            
            # Target verifies all K tokens in one forward pass
            verified_count = await self.target.verify_tokens(target_kv, draft_tokens)
            
            # Yield verified tokens
            for i in range(verified_count):
                yield draft_tokens[i]
                tokens_generated += 1
            
            # Target generates one corrected token if needed
            if verified_count < len(draft_tokens):
                correct_token = await self.target.generate_one(target_kv)
                yield correct_token
                tokens_generated += 1
            
            # Check for EOS
            if draft_tokens and draft_tokens[verified_count - 1] == "<EOS>":
                break
            
            # Update KV caches
            self.draft.update_kv(draft_kv, draft_tokens[:verified_count])
            self.target.update_kv(target_kv, draft_tokens[:verified_count])

    async def _target_decode_loop(self, target_kv, start_pos: int) -> AsyncGenerator[str, None]:
        """Fallback: standard autoregressive from target model."""
        tokens = 0
        async for token in self.target.generate(target_kv, max_tokens=self.config.max_output_tokens):
            yield token
            tokens += 1


class StreamingResponseHandler:
    """Handles client-facing streaming with buffering strategies."""
    
    def __init__(self):
        self.buffer = []
        self.flush_strategies = {
            "immediate": self._flush_immediate,      # Every token
            "word": self._flush_on_word_boundary,    # Every word
            "sentence": self._flush_on_sentence,     # Every sentence
        }
    
    async def stream_to_client(self, token_stream: AsyncGenerator, 
                                strategy: str = "word") -> AsyncGenerator[str, None]:
        """Buffer and flush tokens based on strategy."""
        flush_fn = self.flush_strategies[strategy]
        
        async for token in token_stream:
            self.buffer.append(token)
            flush_text = flush_fn()
            if flush_text:
                yield flush_text
        
        # Flush remaining buffer
        if self.buffer:
            yield "".join(self.buffer)
            self.buffer.clear()
    
    def _flush_immediate(self) -> Optional[str]:
        text = "".join(self.buffer)
        self.buffer.clear()
        return text
    
    def _flush_on_word_boundary(self) -> Optional[str]:
        text = "".join(self.buffer)
        if " " in text or "\n" in text:
            # Flush up to last space
            last_space = max(text.rfind(" "), text.rfind("\n"))
            flush = text[:last_space + 1]
            self.buffer = [text[last_space + 1:]] if last_space + 1 < len(text) else []
            return flush
        return None
    
    def _flush_on_sentence(self) -> Optional[str]:
        text = "".join(self.buffer)
        for delim in [".", "!", "?", "\n"]:
            if delim in text:
                idx = text.index(delim) + 1
                flush = text[:idx]
                self.buffer = [text[idx:]] if idx < len(text) else []
                return flush
        return None
```

### Performance Metrics

| Metric | Standard Decoding | Speculative Decoding | Improvement |
|--------|------------------|---------------------|-------------|
| TTFT | 400-500ms | 50-80ms | 5-8x |
| Tokens/second | 30-50 | 80-120 | 2-3x |
| Quality | 100% (baseline) | 100% (verified) | No loss |
| GPU cost | 1x | 1.3x (draft overhead) | Slightly higher |
| Total latency (500 tokens) | 10-15s | 4-6s | 2-3x |

### Production Considerations

- **Draft model selection**: Draft must share vocabulary with target. Smaller models from same family work best (Llama-1B → Llama-70B).
- **KV cache memory**: Both models need KV cache simultaneously. Plan for 2x memory per request.
- **Acceptance rate monitoring**: Track draft acceptance rate. If <60%, draft model needs fine-tuning on target's distribution.
- **Client reconnection**: Token position tracking for seamless reconnection mid-stream.
- **Early stopping**: Monitor token probability entropy. If model is "uncertain," stop early rather than hallucinate.

---

## Q83: Request coalescing and batching for embedding generation

### Problem
You serve 100K embedding requests per minute. Each request has 1-10 texts. GPU batch inference is most efficient at batch sizes of 64-256. Design a system that maximizes throughput while keeping individual request p99 < 50ms.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│             Embedding Batching System                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Request 1  │  │ Request 2  │  │ Request N  │            │
│  │ [3 texts]  │  │ [1 text]   │  │ [5 texts]  │            │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘            │
│        │                │                │                    │
│        ▼                ▼                ▼                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Micro-Batcher                            │   │
│  │  - Collects items for up to 5ms OR 128 items         │   │
│  │  - Groups by sequence length (reduces padding)        │   │
│  │  - Assigns batch IDs, tracks per-request futures      │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          │                                    │
│                          ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Length-Sorted Batch Queue                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐       │   │
│  │  │ Short    │  │ Medium   │  │ Long         │       │   │
│  │  │ <128 tok │  │ <512 tok │  │ <2048 tok    │       │   │
│  │  │ batch=256│  │ batch=128│  │ batch=32     │       │   │
│  │  └──────────┘  └──────────┘  └──────────────┘       │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          │                                    │
│                          ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         GPU Worker Pool (N GPUs)                      │   │
│  │  - Continuous batching                                │   │
│  │  - Batch dispatched when full OR timeout              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np
from concurrent.futures import Future

@dataclass
class EmbeddingItem:
    text: str
    token_count: int
    request_id: str
    item_index: int  # Position within original request
    future: asyncio.Future
    arrival_time: float = field(default_factory=time.time)

@dataclass
class BatchConfig:
    max_batch_size: int = 128
    max_wait_ms: float = 5.0          # Max time to wait for batch to fill
    length_buckets: List[int] = field(default_factory=lambda: [128, 512, 2048])
    batch_sizes_per_bucket: List[int] = field(default_factory=lambda: [256, 128, 32])
    sla_deadline_ms: float = 50.0     # p99 target

class MicroBatcher:
    """Collects individual embedding items into optimal batches."""
    
    def __init__(self, config: BatchConfig, num_gpus: int = 4):
        self.config = config
        self.num_gpus = num_gpus
        self.buckets: Dict[int, List[EmbeddingItem]] = {
            b: [] for b in config.length_buckets
        }
        self.lock = asyncio.Lock()
        self._batch_event = asyncio.Event()
        
        # Start batch dispatch loop
        asyncio.create_task(self._dispatch_loop())
    
    async def submit(self, texts: List[str], request_id: str) -> List[np.ndarray]:
        """Submit texts for embedding, returns when all are done."""
        futures = []
        
        async with self.lock:
            for i, text in enumerate(texts):
                token_count = len(text.split()) * 1.3  # Rough estimate
                future = asyncio.get_event_loop().create_future()
                
                item = EmbeddingItem(
                    text=text, token_count=int(token_count),
                    request_id=request_id, item_index=i,
                    future=future
                )
                
                # Route to appropriate length bucket
                bucket = self._get_bucket(item.token_count)
                self.buckets[bucket].append(item)
                futures.append(future)
                
                # Signal if any bucket is full
                bucket_idx = self.config.length_buckets.index(bucket)
                if len(self.buckets[bucket]) >= self.config.batch_sizes_per_bucket[bucket_idx]:
                    self._batch_event.set()
        
        # Wait for all embeddings to complete
        results = await asyncio.gather(*futures)
        return results
    
    def _get_bucket(self, token_count: int) -> int:
        for bucket in self.config.length_buckets:
            if token_count <= bucket:
                return bucket
        return self.config.length_buckets[-1]
    
    async def _dispatch_loop(self):
        """Continuously dispatch batches."""
        while True:
            # Wait for either: bucket full OR timeout
            try:
                await asyncio.wait_for(
                    self._batch_event.wait(),
                    timeout=self.config.max_wait_ms / 1000
                )
            except asyncio.TimeoutError:
                pass
            
            self._batch_event.clear()
            
            # Dispatch ready batches
            async with self.lock:
                for bucket_size in self.config.length_buckets:
                    bucket_idx = self.config.length_buckets.index(bucket_size)
                    max_batch = self.config.batch_sizes_per_bucket[bucket_idx]
                    
                    while len(self.buckets[bucket_size]) > 0:
                        # Take up to max_batch items
                        batch_items = self.buckets[bucket_size][:max_batch]
                        self.buckets[bucket_size] = self.buckets[bucket_size][max_batch:]
                        
                        # Check SLA: any item close to deadline?
                        oldest = min(item.arrival_time for item in batch_items)
                        age_ms = (time.time() - oldest) * 1000
                        
                        if len(batch_items) >= max_batch * 0.5 or age_ms > self.config.max_wait_ms:
                            # Dispatch this batch
                            asyncio.create_task(
                                self._execute_batch(batch_items, bucket_size)
                            )
                        else:
                            # Put back, wait for more items
                            self.buckets[bucket_size] = batch_items + self.buckets[bucket_size]
                            break

    async def _execute_batch(self, items: List[EmbeddingItem], max_length: int):
        """Execute batch on GPU."""
        texts = [item.text for item in items]
        
        try:
            # Pad to uniform length within bucket, run inference
            embeddings = await gpu_embed_batch(
                texts, 
                max_length=max_length,
                batch_size=len(texts)
            )
            
            # Resolve futures
            for item, embedding in zip(items, embeddings):
                if not item.future.done():
                    item.future.set_result(embedding)
                    
        except Exception as e:
            for item in items:
                if not item.future.done():
                    item.future.set_exception(e)


class RequestCoalescer:
    """Deduplicates identical texts across concurrent requests."""
    
    def __init__(self):
        self.pending: Dict[str, asyncio.Future] = {}  # text_hash → future
        self.lock = asyncio.Lock()
    
    async def get_or_compute(self, text: str, compute_fn) -> np.ndarray:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        async with self.lock:
            if text_hash in self.pending:
                # Another request is already computing this embedding
                return await self.pending[text_hash]
            
            future = asyncio.get_event_loop().create_future()
            self.pending[text_hash] = future
        
        try:
            result = await compute_fn(text)
            future.set_result(result)
            return result
        finally:
            async with self.lock:
                del self.pending[text_hash]
```

### Performance Analysis

| Batch Strategy | Throughput (emb/s) | p50 Latency | p99 Latency | GPU Util |
|---------------|-------------------|-------------|-------------|----------|
| No batching (1 at a time) | 500 | 8ms | 15ms | 5% |
| Fixed batch (64) | 15,000 | 20ms | 45ms | 70% |
| Adaptive (this) | 25,000 | 12ms | 35ms | 90% |
| Max batch (256) | 30,000 | 30ms | 80ms | 95% |

### Production Considerations

- **Padding waste**: Length bucketing reduces padding from 40% to <10% of compute.
- **Deduplication**: In RAG workloads, 10-20% of texts are repeated across concurrent requests. Coalescing saves significant GPU time.
- **Timeout enforcement**: If a batch hasn't completed within 40ms, it's likely stuck. Cancel and retry on different GPU.
- **Warmup**: First batch after cold start is 2-3x slower. Pre-warm with dummy batch.
- **Monitoring**: Track batch fill rate, padding percentage, coalescing hit rate, and per-bucket latency.

---

## Q84: Predictive pre-computation for near-zero perceived latency

### Problem
For common interactions (search suggestions, chat follow-ups, dashboard queries), pre-generate likely responses before the user asks. Reduce perceived latency to near-zero for 60%+ of interactions.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Predictive Pre-computation System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Prediction Layer                                          │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ Session     │  │ Population   │  │ Temporal      │   │   │
│  │  │ Predictor   │  │ Predictor    │  │ Predictor     │   │   │
│  │  │ (user's     │  │ (trending    │  │ (time-of-day  │   │   │
│  │  │  next query)│  │  queries)    │  │  patterns)    │   │   │
│  │  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘   │   │
│  │         │                 │                  │            │   │
│  │         ▼                 ▼                  ▼            │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │ Prediction Ranker (top-K likely queries)          │   │   │
│  │  │ Score = P(query|session) × value × freshness      │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────┬───────────────────────┘   │
│                                     │                            │
│                                     ▼                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Pre-computation Engine                                    │   │
│  │  - Generates responses for top-5 predicted queries        │   │
│  │  - Uses spare GPU capacity (off-peak) or cheap models     │   │
│  │  - Stores in per-user pre-computation cache (TTL=5min)    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Serving Layer                                             │   │
│  │  User Query → Check pre-computation cache → Hit? Instant! │   │
│  │                                         → Miss? Normal path│   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import numpy as np

@dataclass
class PredictedQuery:
    query: str
    confidence: float       # 0-1, probability user will ask this
    value: float           # Business value of pre-computing (cost × frequency)
    freshness_weight: float  # How time-sensitive is this answer

@dataclass
class PrecomputedResponse:
    query: str
    response: str
    generated_at: float
    model_used: str
    ttl_seconds: float
    confidence_at_generation: float

class SessionPredictor:
    """Predicts next query based on current session context."""
    
    def __init__(self):
        self.session_model = load_model("next-query-predictor")  # Fine-tuned on session logs
        # Markov chain of query transitions (computed offline)
        self.transition_matrix: Dict[str, List[Tuple[str, float]]] = {}
    
    async def predict_next(self, session_history: List[str], 
                           user_profile: dict, k: int = 5) -> List[PredictedQuery]:
        """Predict top-K likely next queries for this session."""
        predictions = []
        
        # 1. ML model prediction (most accurate)
        ml_predictions = await self.session_model.predict(
            session_history=session_history,
            user_context=user_profile,
            top_k=k * 2
        )
        
        # 2. Markov chain (fast, covers common patterns)
        if session_history:
            last_query = session_history[-1]
            markov_predictions = self.transition_matrix.get(last_query, [])[:k]
        else:
            markov_predictions = []
        
        # 3. Merge and deduplicate
        seen = set()
        for query, confidence in ml_predictions + markov_predictions:
            if query not in seen:
                seen.add(query)
                predictions.append(PredictedQuery(
                    query=query,
                    confidence=confidence,
                    value=self._estimate_value(query),
                    freshness_weight=self._freshness_requirement(query)
                ))
        
        # Sort by expected value (confidence × value)
        predictions.sort(key=lambda p: p.confidence * p.value, reverse=True)
        return predictions[:k]
    
    def _estimate_value(self, query: str) -> float:
        """Value = generation_cost × frequency. High-value = expensive to compute."""
        # Queries requiring RAG or long generation are more valuable to pre-compute
        estimated_tokens = len(query.split()) * 50  # Rough output estimate
        return min(estimated_tokens / 500, 1.0)
    
    def _freshness_requirement(self, query: str) -> float:
        """How quickly does this answer become stale?"""
        # "What's the stock price" → very fresh needed (low TTL)
        # "How does X work" → stable (high TTL)
        return 0.5  # Default: moderate freshness


class PrecomputationEngine:
    """Manages pre-computation budget and execution."""
    
    def __init__(self, gpu_budget_fraction: float = 0.2):
        self.gpu_budget = gpu_budget_fraction  # Use 20% of spare GPU capacity
        self.cache: Dict[str, Dict[str, PrecomputedResponse]] = defaultdict(dict)
        self.stats = {"hits": 0, "misses": 0, "precomputed": 0, "wasted": 0}
    
    async def precompute_for_user(self, user_id: str, 
                                   predictions: List[PredictedQuery]):
        """Pre-generate responses for predicted queries."""
        # Budget: only precompute if confidence > threshold
        threshold = 0.3  # Pre-compute if >30% likely
        
        tasks = []
        for pred in predictions:
            if pred.confidence < threshold:
                continue
            
            # Skip if already cached and fresh
            existing = self.cache[user_id].get(pred.query)
            if existing and time.time() - existing.generated_at < existing.ttl_seconds:
                continue
            
            tasks.append(self._generate_and_cache(user_id, pred))
        
        # Run pre-computations with limited concurrency
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent per user
        async def limited(task):
            async with semaphore:
                return await task
        
        await asyncio.gather(*[limited(t) for t in tasks])
    
    async def _generate_and_cache(self, user_id: str, pred: PredictedQuery):
        """Generate and cache a predicted response."""
        # Use cheaper model for pre-computation (cost-conscious)
        response = await generate_response(
            query=pred.query,
            model="gpt-3.5-turbo",  # Cheaper for speculative generation
            max_tokens=300
        )
        
        ttl = 300 / pred.freshness_weight  # Less fresh = longer TTL
        
        self.cache[user_id][pred.query] = PrecomputedResponse(
            query=pred.query,
            response=response,
            generated_at=time.time(),
            model_used="gpt-3.5-turbo",
            ttl_seconds=ttl,
            confidence_at_generation=pred.confidence
        )
        self.stats["precomputed"] += 1
    
    async def serve(self, user_id: str, query: str) -> Optional[str]:
        """Check if we have a pre-computed response."""
        # Exact match
        cached = self.cache[user_id].get(query)
        if cached and time.time() - cached.generated_at < cached.ttl_seconds:
            self.stats["hits"] += 1
            return cached.response
        
        # Semantic similarity match (fuzzy)
        for cached_query, cached_response in self.cache[user_id].items():
            if self._semantic_match(query, cached_query) > 0.92:
                if time.time() - cached_response.generated_at < cached_response.ttl_seconds:
                    self.stats["hits"] += 1
                    return cached_response.response
        
        self.stats["misses"] += 1
        return None
    
    def _semantic_match(self, q1: str, q2: str) -> float:
        """Fast semantic similarity (cached embeddings)."""
        # Use pre-computed embeddings
        return 0.0  # Placeholder
    
    def get_efficiency_metrics(self) -> dict:
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0
        waste_rate = 1 - (self.stats["hits"] / self.stats["precomputed"]) if self.stats["precomputed"] > 0 else 0
        return {
            "hit_rate": hit_rate,
            "waste_rate": waste_rate,  # Pre-computed but never used
            "gpu_roi": hit_rate / self.gpu_budget,  # Effectiveness per GPU spent
        }
```

### Trade-offs

| Strategy | Hit Rate | GPU Waste | Latency Saving | Complexity |
|----------|----------|-----------|----------------|------------|
| No pre-computation | 0% | 0% | 0ms | None |
| Popular queries only | 20-30% | Low | High for hits | Low |
| Session-aware (this) | 40-60% | 20-30% | Near-zero for hits | High |
| Full pre-computation | 80%+ | 60-70% | Near-zero | Very High |

### Production Considerations

- **GPU budget management**: Pre-computation uses spare capacity. During peak, reduce pre-computation aggressively. Never starve real-time requests.
- **Cache invalidation**: When underlying data changes, invalidate pre-computed responses that depend on it.
- **Quality bridge**: Pre-computed with cheap model. If user actually asks, start streaming pre-computed AND generate with full model in background. Replace if quality differs.
- **Privacy**: Per-user prediction models see session data. Ensure predictions are never leaked across users.
- **Measurement**: A/B test pre-computation. Measure perceived latency improvement and user engagement lift.

---

## Q85: Tiered inference with routing logic and quality guarantees

### Problem
80% of queries are simple (factual lookups, reformatting) and can be handled by a fast 7B model. 20% need GPT-4 class reasoning. Design a router that correctly identifies complexity and guarantees quality across tiers.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              Tiered Inference Architecture                     │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  User Query                                                   │
│       │                                                       │
│       ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Complexity Router (lightweight classifier, <10ms)        │ │
│  │                                                          │ │
│  │  Features:                                               │ │
│  │  - Query length, question type                           │ │
│  │  - Entity count, reasoning keywords                      │ │
│  │  - Historical difficulty of similar queries              │ │
│  │  - User tier (enterprise gets premium default)           │ │
│  │                                                          │ │
│  │  Output: {tier: "fast"|"medium"|"premium",               │ │
│  │           confidence: 0.0-1.0}                           │ │
│  └────────────────┬──────────────┬───────────────┬─────────┘ │
│                   │              │               │            │
│     confidence>0.8│   0.5-0.8   │     <0.5      │            │
│                   ▼              ▼               ▼            │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────────┐  │
│  │ Fast Tier│  │ Medium   │  │ Premium Tier              │  │
│  │ Llama-7B │  │ Llama-70B│  │ GPT-4 / Claude           │  │
│  │ INT8     │  │ FP16     │  │ Full capability           │  │
│  │ 50ms     │  │ 200ms    │  │ 1-3s                     │  │
│  │ $0.001/q │  │ $0.01/q  │  │ $0.05/q                  │  │
│  └────┬─────┘  └────┬─────┘  └─────────────┬─────────────┘  │
│       │              │                       │                │
│       ▼              ▼                       ▼                │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ Quality Verifier (async, samples 10%)                     ││
│  │ - Compares fast tier output with premium model            ││
│  │ - Detects quality regressions                             ││
│  │ - Feeds back to router training                           ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import random

class InferenceTier(Enum):
    FAST = "fast"       # 7B INT8 - simple queries
    MEDIUM = "medium"   # 70B FP16 - moderate complexity
    PREMIUM = "premium" # GPT-4 - complex reasoning

@dataclass
class TierSpec:
    model: str
    max_tokens: int
    timeout_ms: float
    cost_per_query: float
    expected_latency_ms: float

TIER_SPECS = {
    InferenceTier.FAST: TierSpec("llama-7b-int8", 256, 200, 0.001, 50),
    InferenceTier.MEDIUM: TierSpec("llama-70b", 512, 1000, 0.01, 200),
    InferenceTier.PREMIUM: TierSpec("gpt-4", 1024, 5000, 0.05, 1500),
}

class ComplexityRouter:
    """Classifies query complexity to select inference tier."""
    
    def __init__(self):
        self.classifier = load_model("query-complexity-classifier")  # Fine-tuned BERT-tiny
        self.feature_extractor = QueryFeatureExtractor()
        # Thresholds (tuned on labeled data)
        self.fast_threshold = 0.7    # Route to fast if P(simple) > 0.7
        self.premium_threshold = 0.6  # Route to premium if P(complex) > 0.6
    
    async def route(self, query: str, context: dict = None) -> Tuple[InferenceTier, float]:
        """Classify query complexity. Returns (tier, confidence)."""
        features = self.feature_extractor.extract(query)
        
        # Rule-based fast path (near-zero latency)
        rule_result = self._rule_based_check(query, features)
        if rule_result:
            return rule_result
        
        # ML classifier
        probs = await self.classifier.predict(features)
        # probs = [P(simple), P(moderate), P(complex)]
        
        if probs[0] > self.fast_threshold:
            return InferenceTier.FAST, probs[0]
        elif probs[2] > self.premium_threshold:
            return InferenceTier.PREMIUM, probs[2]
        else:
            return InferenceTier.MEDIUM, max(probs)
    
    def _rule_based_check(self, query: str, features: dict) -> Optional[Tuple[InferenceTier, float]]:
        """Fast heuristic rules for obvious cases."""
        # Very short, factual queries → fast
        if features["word_count"] < 10 and features["question_type"] in ["what_is", "define"]:
            return InferenceTier.FAST, 0.95
        
        # Multi-step reasoning keywords → premium
        complex_indicators = ["compare", "analyze", "trade-offs", "design", "explain why",
                             "step by step", "pros and cons"]
        if any(ind in query.lower() for ind in complex_indicators):
            return InferenceTier.PREMIUM, 0.85
        
        # Code generation with complexity → premium
        if features["has_code_request"] and features["word_count"] > 50:
            return InferenceTier.PREMIUM, 0.8
        
        return None


class TieredInferenceEngine:
    """Orchestrates tiered inference with quality guarantees."""
    
    def __init__(self):
        self.router = ComplexityRouter()
        self.models = {
            InferenceTier.FAST: FastModel("llama-7b-int8"),
            InferenceTier.MEDIUM: MediumModel("llama-70b"),
            InferenceTier.PREMIUM: PremiumModel("gpt-4"),
        }
        self.quality_monitor = QualityMonitor()
        self.escalation_rate = 0.0  # Track how often fast tier escalates
    
    async def infer(self, query: str, user_tier: str = "pro") -> dict:
        """Route and execute inference with quality fallback."""
        # Route
        tier, confidence = await self.router.route(query)
        
        # Enterprise users: minimum medium tier
        if user_tier == "enterprise" and tier == InferenceTier.FAST:
            tier = InferenceTier.MEDIUM
            confidence = 0.9
        
        spec = TIER_SPECS[tier]
        
        # Execute on selected tier
        response = await self.models[tier].generate(
            query, max_tokens=spec.max_tokens, timeout_ms=spec.timeout_ms
        )
        
        # Quality gate: check if response seems adequate
        if tier != InferenceTier.PREMIUM:
            quality_ok = await self._quick_quality_check(query, response, tier)
            if not quality_ok:
                # Escalate to next tier
                tier = InferenceTier(tier.value)  # Next tier
                next_tier = self._get_next_tier(tier)
                if next_tier:
                    response = await self.models[next_tier].generate(
                        query, max_tokens=TIER_SPECS[next_tier].max_tokens
                    )
                    tier = next_tier
                    self.escalation_rate = self.escalation_rate * 0.99 + 0.01
        
        # Async quality sampling (doesn't block response)
        if random.random() < 0.1:  # Sample 10%
            asyncio.create_task(
                self.quality_monitor.evaluate(query, response, tier)
            )
        
        return {
            "response": response,
            "tier_used": tier.value,
            "confidence": confidence,
            "latency_ms": spec.expected_latency_ms,
        }
    
    async def _quick_quality_check(self, query: str, response: str, 
                                    tier: InferenceTier) -> bool:
        """Lightweight quality check (<5ms)."""
        # Heuristic checks
        if len(response.strip()) < 10:
            return False  # Too short, likely failed
        if "I don't know" in response and len(query.split()) > 5:
            return False  # Likely needs more capable model
        if response.count("...") > 3:
            return False  # Hedging, uncertain
        
        # Check response confidence (if model provides logprobs)
        # Low avg logprob → model is uncertain → escalate
        return True
    
    def _get_next_tier(self, current: InferenceTier) -> Optional[InferenceTier]:
        order = [InferenceTier.FAST, InferenceTier.MEDIUM, InferenceTier.PREMIUM]
        idx = order.index(current)
        return order[idx + 1] if idx + 1 < len(order) else None


class QualityMonitor:
    """Continuously monitors tier routing quality."""
    
    def __init__(self):
        self.scores: dict = defaultdict(list)
    
    async def evaluate(self, query: str, response: str, tier: InferenceTier):
        """Compare tier response with premium model (ground truth)."""
        if tier == InferenceTier.PREMIUM:
            return  # Nothing to compare against
        
        # Generate premium response
        premium_response = await PremiumModel("gpt-4").generate(query)
        
        # Score agreement (using another LLM as judge)
        score = await self._judge_agreement(response, premium_response, query)
        self.scores[tier.value].append(score)
        
        # Alert if quality drops
        recent_scores = self.scores[tier.value][-100:]
        avg_quality = np.mean(recent_scores)
        
        if avg_quality < 0.85:
            await self._alert_quality_drop(tier, avg_quality)
    
    async def _judge_agreement(self, response_a: str, response_b: str, query: str) -> float:
        """Quick agreement score 0-1."""
        # Simplified: use embedding similarity as proxy
        emb_a = await embed(response_a)
        emb_b = await embed(response_b)
        return float(np.dot(emb_a, emb_b))
    
    async def _alert_quality_drop(self, tier: InferenceTier, score: float):
        """Alert when tier quality drops below threshold."""
        pass  # Send to PagerDuty/Slack
```

### Cost-Quality Analysis

| Traffic Mix | Avg Cost/Query | Avg Latency | Quality Score |
|-------------|---------------|-------------|---------------|
| All Premium | $0.050 | 1500ms | 1.00 (baseline) |
| All Fast | $0.001 | 50ms | 0.72 |
| Tiered (80/15/5) | $0.005 | 120ms | 0.94 |
| Tiered + escalation | $0.008 | 150ms | 0.97 |

### Production Considerations

- **Router accuracy is everything**: 5% misrouting of complex queries to fast tier = visible quality degradation. Invest heavily in router training data.
- **Feedback loop**: Log every escalation. Use escalated queries as training data for the router (they were misclassified).
- **A/B testing**: Run 5% of fast-tier traffic through premium tier to measure quality gap. Adjust thresholds based on results.
- **Cost ceiling**: Even with tiered inference, set per-user cost ceilings. A user sending only complex queries shouldn't bankrupt the system.
- **Model refresh**: When fast model is retrained/upgraded, re-evaluate routing thresholds. Better fast model → more queries can go to fast tier.
# Scalability Patterns for AI Systems (Questions 86-90)

## Q86: Horizontally scalable RAG system from 1M to 10B documents

### Problem
Design a RAG system that scales 10,000x without architecture changes. At 1M docs you need fast iteration; at 10B docs you need distributed indexing, cost-effective storage, and sub-100ms retrieval.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Scalable RAG Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Ingestion Pipeline (scales horizontally)                    │ │
│  │  Kafka → Chunker → Embedder → Indexer                      │ │
│  │  Throughput: 100K docs/hour per worker                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Storage Layer (tiered by access pattern)                    │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │ │
│  │  │ Hot Tier    │  │ Warm Tier   │  │ Cold Tier        │   │ │
│  │  │ <100M docs  │  │ 100M-1B    │  │ 1B-10B docs      │   │ │
│  │  │ In-memory   │  │ SSD-backed  │  │ Object store +   │   │ │
│  │  │ HNSW index  │  │ DiskANN     │  │ quantized index  │   │ │
│  │  │ p99: 5ms    │  │ p99: 20ms   │  │ p99: 50ms        │   │ │
│  │  │ $50/M docs  │  │ $5/M docs   │  │ $0.50/M docs     │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Query Layer                                                 │ │
│  │  Query → Embed → Route to shards → Scatter-Gather → Rerank│ │
│  │                                                             │ │
│  │  Sharding: hash(tenant_id) for multi-tenant                │ │
│  │            hash(doc_id % N) for single-tenant               │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import hashlib
import numpy as np

class StorageTier(Enum):
    HOT = "hot"      # In-memory HNSW
    WARM = "warm"    # SSD-based DiskANN
    COLD = "cold"    # Object store + PQ-compressed

@dataclass
class ScaleConfig:
    """Configuration that adapts to current scale."""
    total_docs: int
    num_shards: int
    replication_factor: int
    index_type: str
    quantization: str
    
    @classmethod
    def for_scale(cls, doc_count: int) -> 'ScaleConfig':
        """Auto-configure based on document count."""
        if doc_count < 10_000_000:  # <10M
            return cls(
                total_docs=doc_count,
                num_shards=max(1, doc_count // 1_000_000),
                replication_factor=2,
                index_type="HNSW",
                quantization="none"  # Full FP32 embeddings
            )
        elif doc_count < 1_000_000_000:  # <1B
            return cls(
                total_docs=doc_count,
                num_shards=doc_count // 5_000_000,  # 5M per shard
                replication_factor=2,
                index_type="DiskANN",
                quantization="SQ8"  # Scalar quantization
            )
        else:  # 1B+
            return cls(
                total_docs=doc_count,
                num_shards=doc_count // 10_000_000,  # 10M per shard
                replication_factor=3,
                index_type="IVF_PQ",
                quantization="PQ64"  # Product quantization to 64 bytes
            )


class ShardRouter:
    """Routes queries to appropriate shards using scatter-gather."""
    
    def __init__(self, config: ScaleConfig):
        self.config = config
        self.shard_map: Dict[int, List[str]] = {}  # shard_id → [node_addresses]
    
    def get_target_shards(self, query_embedding: np.ndarray, 
                          tenant_id: Optional[str] = None,
                          top_k: int = 10) -> List[int]:
        """Determine which shards to query."""
        if tenant_id:
            # Tenant-scoped: only query tenant's shards
            shard_id = int(hashlib.md5(tenant_id.encode()).hexdigest(), 16) % self.config.num_shards
            return [shard_id]
        
        if self.config.num_shards <= 10:
            # Small scale: query all shards
            return list(range(self.config.num_shards))
        
        # Large scale: use coarse quantizer to identify promising shards
        # Each shard has a centroid; find nearest centroids
        num_shards_to_query = min(
            max(3, self.config.num_shards // 10),  # Query ~10% of shards
            20  # Cap at 20 shards
        )
        return self._find_nearest_shards(query_embedding, num_shards_to_query)
    
    def _find_nearest_shards(self, query: np.ndarray, k: int) -> List[int]:
        """Find shards most likely to contain relevant docs."""
        # Pre-computed shard centroids (updated hourly)
        # This is essentially IVF's coarse quantizer at shard level
        return list(range(k))  # Placeholder


class ScalableRAGEngine:
    """RAG engine that works from 1M to 10B documents."""
    
    def __init__(self, doc_count: int):
        self.config = ScaleConfig.for_scale(doc_count)
        self.router = ShardRouter(self.config)
        self.merger = ResultMerger()
    
    async def retrieve(self, query: str, top_k: int = 10, 
                       tenant_id: Optional[str] = None) -> List[dict]:
        """Scatter-gather retrieval across shards."""
        # 1. Embed query
        query_embedding = await self._embed_query(query)
        
        # 2. Determine target shards
        target_shards = self.router.get_target_shards(
            query_embedding, tenant_id, top_k
        )
        
        # 3. Scatter: query all target shards in parallel
        shard_results = await asyncio.gather(*[
            self._query_shard(shard_id, query_embedding, top_k * 2)
            for shard_id in target_shards
        ])
        
        # 4. Gather: merge and re-rank results
        merged = self.merger.merge(shard_results, top_k)
        
        # 5. Optional: cross-encoder reranking on top candidates
        if len(merged) > top_k:
            merged = await self._rerank(query, merged, top_k)
        
        return merged
    
    async def _query_shard(self, shard_id: int, query_embedding: np.ndarray, 
                           top_k: int) -> List[dict]:
        """Query a single shard. Implementation depends on tier."""
        # The shard handles its own index type (HNSW/DiskANN/IVF_PQ)
        pass
    
    async def _rerank(self, query: str, candidates: List[dict], 
                      top_k: int) -> List[dict]:
        """Cross-encoder reranking for precision."""
        # Only rerank top 2*k candidates (expensive)
        scores = await cross_encoder_score(query, [c["text"] for c in candidates[:top_k*2]])
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in ranked[:top_k]]


class IndexManager:
    """Manages index lifecycle: build, compact, migrate between tiers."""
    
    def __init__(self):
        self.tier_thresholds = {
            StorageTier.HOT: 100_000_000,    # Up to 100M in memory
            StorageTier.WARM: 1_000_000_000,  # Up to 1B on SSD
            StorageTier.COLD: float('inf'),   # Everything else
        }
    
    async def rebalance(self, shard_stats: Dict[int, dict]):
        """Move data between tiers based on access patterns."""
        for shard_id, stats in shard_stats.items():
            # Hot → Warm: if shard not queried in 1 hour
            if stats["last_query_age"] > 3600 and stats["current_tier"] == StorageTier.HOT:
                await self._migrate_shard(shard_id, StorageTier.HOT, StorageTier.WARM)
            
            # Warm → Hot: if query rate > 10/min
            if stats["query_rate_per_min"] > 10 and stats["current_tier"] == StorageTier.WARM:
                await self._migrate_shard(shard_id, StorageTier.WARM, StorageTier.HOT)
    
    async def _migrate_shard(self, shard_id: int, from_tier: StorageTier, to_tier: StorageTier):
        """Migrate shard between tiers with zero downtime."""
        # 1. Build new index in target tier
        # 2. Dual-read from both during migration
        # 3. Switch reads to new tier
        # 4. Delete old tier data
        pass
```

### Cost Model by Scale

| Scale | Shards | Storage Cost/mo | Compute Cost/mo | p99 Retrieval | Index Type |
|-------|--------|----------------|-----------------|---------------|------------|
| 1M | 1 | $50 | $200 | 5ms | HNSW (RAM) |
| 10M | 4 | $500 | $800 | 8ms | HNSW (RAM) |
| 100M | 20 | $2,000 | $4,000 | 15ms | HNSW + DiskANN |
| 1B | 200 | $8,000 | $15,000 | 30ms | DiskANN |
| 10B | 1000 | $25,000 | $50,000 | 60ms | IVF_PQ + DiskANN |

### Production Considerations

- **Shard splitting**: When a shard exceeds 10M docs, split it. Use consistent hashing to minimize data movement.
- **Compaction**: Dead/deleted documents accumulate. Compact indexes weekly (rebuild without deleted docs).
- **Embedding versioning**: When you upgrade embedding model, you need to re-embed everything. Do rolling migration: new docs get new embeddings, old docs re-embedded in background over days.
- **Query fan-out budget**: At 1000 shards, querying all is impossible. Coarse routing must be accurate or recall drops.
- **Monitoring**: Track recall@10 with golden queries. If recall drops below 0.9 after scaling changes, investigate.

---

## Q87: Multi-model serving platform for 50+ models on shared GPU infrastructure

### Problem
Your platform serves 50+ models: 5 LLMs (7B-70B), 10 embedding models, 20 classifiers, 15 specialized models. All share a GPU cluster. Design efficient multiplexing with per-model SLAs.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Multi-Model Serving Platform                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Model Registry & Scheduler                                  │  │
│  │  - 50+ model definitions (size, SLA, priority)              │  │
│  │  - Placement decisions: which model on which GPU            │  │
│  │  - Auto-scaling per model                                   │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │ GPU Cluster (32x A100 80GB)                                 │  │
│  │                                                              │  │
│  │  Strategy: Model Packing                                    │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ GPU 0-3: Llama-70B (4-GPU tensor parallel)          │   │  │
│  │  │ GPU 4-5: Llama-7B (2 replicas, 1 GPU each)         │   │  │
│  │  │ GPU 6: Embedding-large + Classifier-A + Classifier-B│   │  │
│  │  │ GPU 7: Embedding-small × 3 (multi-instance)         │   │  │
│  │  │ GPU 8-11: Reserved for burst / overflow             │   │  │
│  │  │ ...                                                  │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Request Router                                              │  │
│  │  model_name → active endpoints → load-balanced selection    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
import heapq

@dataclass
class ModelSpec:
    model_id: str
    name: str
    size_gb: float           # GPU memory required
    min_replicas: int        # Minimum always-loaded replicas
    max_replicas: int
    sla_latency_ms: float    # p99 target
    sla_availability: float  # e.g., 0.999
    priority: int            # 0=highest
    can_share_gpu: bool      # Can co-locate with other models
    load_time_seconds: float # Time to load into GPU memory
    requests_per_second: float  # Current traffic

@dataclass
class GPUNode:
    gpu_id: str
    total_memory_gb: float = 80.0
    used_memory_gb: float = 0.0
    loaded_models: List[str] = field(default_factory=list)
    
    @property
    def free_memory_gb(self) -> float:
        return self.total_memory_gb - self.used_memory_gb

class ModelPlacementScheduler:
    """Bin-packing scheduler for multi-model GPU placement."""
    
    def __init__(self, gpus: List[GPUNode], models: List[ModelSpec]):
        self.gpus = {g.gpu_id: g for g in gpus}
        self.models = {m.model_id: m for m in models}
        self.placements: Dict[str, List[str]] = {}  # model_id → [gpu_ids]
    
    def compute_placement(self) -> Dict[str, List[str]]:
        """Solve model placement using priority-aware bin packing."""
        placements = {}
        
        # Sort models: large models first (harder to place), then by priority
        sorted_models = sorted(
            self.models.values(),
            key=lambda m: (-m.size_gb, m.priority)
        )
        
        for model in sorted_models:
            placed_gpus = self._place_model(model)
            if placed_gpus:
                placements[model.model_id] = placed_gpus
            else:
                # Can't place: need to evict or alert
                self._handle_placement_failure(model)
        
        return placements
    
    def _place_model(self, model: ModelSpec) -> List[str]:
        """Place model replicas on GPUs."""
        placed = []
        
        for _ in range(model.min_replicas):
            gpu = self._find_best_gpu(model)
            if gpu:
                gpu.used_memory_gb += model.size_gb
                gpu.loaded_models.append(model.model_id)
                placed.append(gpu.gpu_id)
            else:
                break
        
        return placed
    
    def _find_best_gpu(self, model: ModelSpec) -> Optional[GPUNode]:
        """Find optimal GPU for this model."""
        candidates = []
        
        for gpu in self.gpus.values():
            if gpu.free_memory_gb < model.size_gb:
                continue
            
            if not model.can_share_gpu and gpu.loaded_models:
                continue
            
            # Score: prefer GPUs that minimize wasted memory (bin packing)
            waste = gpu.free_memory_gb - model.size_gb
            # Prefer co-locating small models together
            affinity_bonus = 0
            if model.can_share_gpu and gpu.loaded_models:
                affinity_bonus = 10  # Prefer consolidation
            
            score = -waste + affinity_bonus
            candidates.append((score, gpu))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    
    def _handle_placement_failure(self, model: ModelSpec):
        """When we can't place a model, evict lower priority."""
        # Find lowest priority model that frees enough memory
        pass


class ModelAutoScaler:
    """Per-model auto-scaling within shared GPU pool."""
    
    def __init__(self, scheduler: ModelPlacementScheduler):
        self.scheduler = scheduler
        self.metrics: Dict[str, dict] = {}  # model_id → metrics
    
    def evaluate_scaling(self) -> List[dict]:
        """Determine which models need more/fewer replicas."""
        actions = []
        
        for model_id, model in self.scheduler.models.items():
            metrics = self.metrics.get(model_id, {})
            current_replicas = len(self.scheduler.placements.get(model_id, []))
            
            # Scale up if latency SLA is being violated
            p99_latency = metrics.get("p99_latency_ms", 0)
            if p99_latency > model.sla_latency_ms * 0.8:
                if current_replicas < model.max_replicas:
                    actions.append({
                        "action": "scale_up",
                        "model_id": model_id,
                        "reason": f"p99={p99_latency}ms > {model.sla_latency_ms*0.8}ms threshold"
                    })
            
            # Scale down if heavily underutilized
            utilization = metrics.get("gpu_utilization", 0)
            if utilization < 0.2 and current_replicas > model.min_replicas:
                actions.append({
                    "action": "scale_down",
                    "model_id": model_id,
                    "reason": f"utilization={utilization:.0%} < 20%"
                })
        
        return actions


class ModelSwapper:
    """Handles model loading/unloading for dynamic scheduling."""
    
    def __init__(self):
        self.swap_history: List[dict] = []
    
    async def swap_model(self, gpu_id: str, unload_model: str, load_model: str):
        """Swap models on a GPU with minimal disruption."""
        # 1. Drain traffic from model being unloaded
        await self._drain_traffic(gpu_id, unload_model, timeout_s=30)
        
        # 2. Unload from GPU memory
        await self._unload_model(gpu_id, unload_model)
        
        # 3. Load new model (from local NVMe cache if available)
        await self._load_model(gpu_id, load_model)
        
        # 4. Warm up with test request
        await self._warmup(gpu_id, load_model)
        
        # 5. Route traffic to new model
        await self._enable_traffic(gpu_id, load_model)
    
    async def _drain_traffic(self, gpu_id: str, model_id: str, timeout_s: float):
        """Stop new requests, wait for in-flight to complete."""
        pass
    
    async def _unload_model(self, gpu_id: str, model_id: str):
        """Free GPU memory."""
        pass
    
    async def _load_model(self, gpu_id: str, model_id: str):
        """Load model weights into GPU memory."""
        pass
    
    async def _warmup(self, gpu_id: str, model_id: str):
        """Run test inference to warm caches."""
        pass
    
    async def _enable_traffic(self, gpu_id: str, model_id: str):
        """Register endpoint for traffic routing."""
        pass
```

### GPU Memory Budget Example (32x A100 80GB = 2560GB total)

| Model Category | Models | Per-Model Size | Replicas | Total GPU Memory |
|---------------|--------|---------------|----------|-----------------|
| Large LLMs (70B) | 2 | 140GB (4-GPU TP) | 2 each | 1120GB |
| Medium LLMs (7B) | 3 | 14GB | 3 each | 126GB |
| Embedding models | 10 | 2GB | 2 each | 40GB |
| Classifiers | 20 | 1GB | 2 each | 40GB |
| Specialized | 15 | 4GB | 2 each | 120GB |
| **Total** | **50** | | | **1446GB** |
| **Buffer (burst)** | | | | **1114GB** |

### Production Considerations

- **Interference**: Co-located models on same GPU compete for memory bandwidth. Benchmark co-location pairs and avoid bad combinations.
- **Model preloading**: Keep top-20 models by traffic always loaded. Swap bottom-30 based on time-of-day patterns.
- **Graceful degradation**: If a model can't be placed, route to API fallback (OpenAI/Anthropic) rather than failing.
- **Resource quotas**: Teams requesting new models must specify expected QPS. Platform validates GPU capacity before approval.
- **Version management**: Support multiple versions simultaneously during canary deployments. Each version is a separate "model" for placement purposes.

---

## Q88: Scalable feature store for real-time AI with 1M lookups/sec at <5ms

### Problem
Your AI applications need features computed from user behavior, item properties, and real-time signals. Design a feature store handling 1M point lookups per second with <5ms p99 latency, supporting both batch (training) and online (inference) access.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Scalable Feature Store                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Feature Computation Layer                                   │ │
│  │                                                             │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  │ │
│  │  │ Batch Features│  │ Streaming     │  │ On-Demand    │  │ │
│  │  │ (Spark, daily)│  │ (Flink, <1min)│  │ (at request) │  │ │
│  │  │ user_history  │  │ session_count │  │ embedding    │  │ │
│  │  │ aggregations  │  │ real_time_ctr │  │ similarity   │  │ │
│  │  └───────┬───────┘  └───────┬───────┘  └──────┬───────┘  │ │
│  │          │                   │                  │           │ │
│  └──────────┼───────────────────┼──────────────────┼───────────┘ │
│             ▼                   ▼                  ▼              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Online Store (Redis Cluster, 1M reads/sec)                  │ │
│  │  - 100 nodes, 6.4TB RAM total                               │ │
│  │  - Key: entity_id | Value: feature_vector (protobuf)        │ │
│  │  - TTL-based expiration per feature group                   │ │
│  │  - Read replicas for throughput                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│             │                                                     │
│             ▼                                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Offline Store (Delta Lake / Parquet on S3)                  │ │
│  │  - Point-in-time correct feature snapshots                  │ │
│  │  - Used for training data generation                        │ │
│  │  - Partitioned by date + entity_type                        │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import hashlib
import struct
import numpy as np

@dataclass
class FeatureDefinition:
    name: str
    entity_type: str        # "user", "item", "session"
    value_type: str         # "float", "vector", "string"
    computation: str        # "batch", "streaming", "on_demand"
    ttl_seconds: int        # Freshness requirement
    default_value: Any      # Returned on cache miss
    sla_latency_ms: float = 5.0

@dataclass
class FeatureVector:
    entity_id: str
    features: Dict[str, Any]
    computed_at: float
    version: int

class OnlineFeatureStore:
    """High-throughput feature serving layer."""
    
    def __init__(self, redis_cluster, feature_registry: Dict[str, FeatureDefinition]):
        self.redis = redis_cluster
        self.registry = feature_registry
        self.local_cache = LRUCache(max_size=100_000)  # L1: process-local
        self.batch_buffer = BatchBuffer(max_size=64, max_wait_ms=2)
    
    async def get_features(self, entity_id: str, 
                           feature_names: List[str]) -> Dict[str, Any]:
        """Get features for a single entity. Target: <5ms p99."""
        # L1: Local LRU cache (sub-ms)
        cache_key = f"{entity_id}:{','.join(sorted(feature_names))}"
        cached = self.local_cache.get(cache_key)
        if cached:
            return cached
        
        # L2: Redis cluster (1-3ms)
        result = await self._redis_multiget(entity_id, feature_names)
        
        # Fill defaults for missing features
        for fname in feature_names:
            if fname not in result:
                defn = self.registry[fname]
                result[fname] = defn.default_value
        
        # Populate L1 cache
        self.local_cache.set(cache_key, result, ttl=1.0)  # 1s local TTL
        
        return result
    
    async def get_features_batch(self, entity_ids: List[str],
                                  feature_names: List[str]) -> List[Dict[str, Any]]:
        """Batch get for multiple entities. Uses pipelining."""
        # Redis pipeline: single round-trip for all entities
        pipeline = self.redis.pipeline()
        
        keys = []
        for entity_id in entity_ids:
            for fname in feature_names:
                key = f"feat:{self.registry[fname].entity_type}:{entity_id}:{fname}"
                pipeline.get(key)
                keys.append((entity_id, fname))
        
        results_raw = await pipeline.execute()
        
        # Reconstruct per-entity feature dicts
        results = [{} for _ in entity_ids]
        for idx, (entity_id, fname) in enumerate(keys):
            entity_idx = entity_ids.index(entity_id)
            value = self._deserialize(results_raw[idx], self.registry[fname].value_type)
            if value is not None:
                results[entity_idx][fname] = value
            else:
                results[entity_idx][fname] = self.registry[fname].default_value
        
        return results
    
    async def _redis_multiget(self, entity_id: str, 
                               feature_names: List[str]) -> Dict[str, Any]:
        """Multi-key get from Redis."""
        keys = [
            f"feat:{self.registry[fn].entity_type}:{entity_id}:{fn}"
            for fn in feature_names
        ]
        values = await self.redis.mget(keys)
        
        result = {}
        for fname, value in zip(feature_names, values):
            if value is not None:
                result[fname] = self._deserialize(value, self.registry[fname].value_type)
        return result
    
    def _deserialize(self, raw: Optional[bytes], value_type: str) -> Any:
        if raw is None:
            return None
        if value_type == "float":
            return struct.unpack('f', raw)[0]
        elif value_type == "vector":
            return np.frombuffer(raw, dtype=np.float32)
        elif value_type == "string":
            return raw.decode('utf-8')
        return raw


class StreamingFeatureComputer:
    """Computes real-time features from event streams."""
    
    def __init__(self, online_store: OnlineFeatureStore):
        self.store = online_store
        self.windows: Dict[str, dict] = {}  # Sliding window state
    
    async def process_event(self, event: dict):
        """Process real-time event, update features."""
        entity_id = event["user_id"]
        event_type = event["type"]
        
        # Update sliding window aggregations
        window_key = f"{entity_id}:{event_type}"
        if window_key not in self.windows:
            self.windows[window_key] = {
                "count_1min": 0, "count_5min": 0, "count_1hr": 0,
                "last_event_time": 0
            }
        
        window = self.windows[window_key]
        window["count_1min"] += 1
        window["count_5min"] += 1
        window["count_1hr"] += 1
        window["last_event_time"] = event["timestamp"]
        
        # Write computed features to online store
        features = {
            f"{event_type}_count_1min": window["count_1min"],
            f"{event_type}_count_5min": window["count_5min"],
            f"last_{event_type}_seconds_ago": time.time() - event["timestamp"],
        }
        
        await self._write_features(entity_id, features)
    
    async def _write_features(self, entity_id: str, features: Dict[str, Any]):
        """Write features to Redis with appropriate TTLs."""
        pipeline = self.store.redis.pipeline()
        for fname, value in features.items():
            key = f"feat:user:{entity_id}:{fname}"
            serialized = struct.pack('f', float(value))
            defn = self.store.registry.get(fname)
            ttl = defn.ttl_seconds if defn else 300
            pipeline.setex(key, ttl, serialized)
        await pipeline.execute()


class FeatureConsistencyChecker:
    """Ensures online/offline feature parity (training-serving skew detection)."""
    
    async def check_skew(self, entity_id: str, feature_name: str) -> dict:
        """Compare online value with offline computation."""
        online_value = await online_store.get_features(entity_id, [feature_name])
        offline_value = await offline_store.get_feature(entity_id, feature_name, 
                                                        timestamp=time.time())
        
        skew = abs(online_value.get(feature_name, 0) - offline_value)
        return {
            "feature": feature_name,
            "online": online_value.get(feature_name),
            "offline": offline_value,
            "skew": skew,
            "alert": skew > 0.1  # >10% skew is concerning
        }
```

### Scaling Numbers

| Metric | Value | How Achieved |
|--------|-------|--------------|
| Read throughput | 1M/sec | 100-node Redis cluster, 10K/sec per node |
| p50 latency | 1.2ms | Local cache hits + Redis single-hop |
| p99 latency | 4.5ms | Pipeline batching, read replicas |
| Feature freshness | <60s | Flink streaming computation |
| Storage | 6.4TB | 100 nodes × 64GB RAM |
| Entities | 500M users + 100M items | Sharded by entity_id |

### Production Considerations

- **Training-serving skew**: The #1 ML production bug. Feature store must guarantee same computation logic offline and online. Use shared feature definitions.
- **Point-in-time correctness**: When generating training data, features must reflect what was available at prediction time, not current values. Offline store maintains temporal snapshots.
- **Feature freshness SLAs**: Some features (user_last_click) must be <10s fresh. Others (user_lifetime_value) can be 24h stale. TTL enforcement prevents serving stale data.
- **Graceful degradation**: If Redis is slow, serve defaults. A model with some default features is better than a timeout.
- **Cost optimization**: Move cold entities (inactive users) from Redis to DynamoDB. Lazy-load back on first access.

---

## Q89: Scalable evaluation pipeline for 10M AI responses/day

### Problem
You need to assess quality of AI-generated content across accuracy, safety, helpfulness, and more. Volume: 10M responses/day. Each needs multi-dimensional scoring. Design for throughput, consistency, and actionability.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Scalable Evaluation Pipeline                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Ingestion (Kafka, 10M events/day ≈ 115/sec)                │  │
│  │  {request, response, context, metadata}                     │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │                                        │
│                           ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Sampling & Routing Layer                                    │  │
│  │  - 100% → Fast evaluators (heuristic, classifier)           │  │
│  │  - 10% → LLM-as-judge evaluation                           │  │
│  │  - 1% → Human evaluation queue                              │  │
│  └──────────┬──────────────────┬───────────────┬──────────────┘  │
│             │                  │               │                   │
│             ▼                  ▼               ▼                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Fast Evals   │  │ LLM Judge    │  │ Human Eval Queue     │   │
│  │ (all 10M)    │  │ (1M/day)     │  │ (100K/day)           │   │
│  │              │  │              │  │                       │   │
│  │ - Toxicity   │  │ - Accuracy   │  │ - Calibration        │   │
│  │ - Length     │  │ - Helpfulness│  │ - Edge cases         │   │
│  │ - Format     │  │ - Coherence  │  │ - Policy violations  │   │
│  │ - Regex      │  │ - Reasoning  │  │                       │   │
│  │              │  │              │  │                       │   │
│  │ Latency: 5ms│  │ Latency: 2s  │  │ Latency: hours       │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                  │                      │                │
│         ▼                  ▼                      ▼                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Score Aggregation & Storage (ClickHouse)                    │  │
│  │  - Per-response scores across dimensions                    │  │
│  │  - Real-time dashboards                                     │  │
│  │  - Alerting on quality drops                                │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import time
import random

class EvalDimension(Enum):
    ACCURACY = "accuracy"
    SAFETY = "safety"
    HELPFULNESS = "helpfulness"
    COHERENCE = "coherence"
    FORMAT_COMPLIANCE = "format"
    GROUNDEDNESS = "groundedness"

@dataclass
class EvalResult:
    dimension: EvalDimension
    score: float          # 0.0 - 1.0
    confidence: float     # How confident is this eval
    evaluator: str        # Which evaluator produced this
    reasoning: Optional[str] = None
    latency_ms: float = 0.0

@dataclass
class ResponseToEval:
    response_id: str
    query: str
    response: str
    context: Optional[str]    # RAG context provided
    model: str
    timestamp: float
    metadata: dict = field(default_factory=dict)

class EvaluationPipeline:
    """Orchestrates multi-tier evaluation at scale."""
    
    def __init__(self):
        self.fast_evaluators = [
            ToxicityClassifier(),
            FormatChecker(),
            LengthChecker(),
            GroundednessHeuristic(),
        ]
        self.llm_judge = LLMJudge()
        self.human_queue = HumanEvalQueue()
        self.storage = EvalStorage()
        
        # Sampling rates
        self.llm_sample_rate = 0.10   # 10% get LLM judging
        self.human_sample_rate = 0.01  # 1% get human review
    
    async def evaluate(self, response: ResponseToEval):
        """Full evaluation pipeline for one response."""
        results: List[EvalResult] = []
        
        # Tier 1: Fast evaluators (ALL responses, <10ms)
        fast_results = await asyncio.gather(*[
            evaluator.evaluate(response) 
            for evaluator in self.fast_evaluators
        ])
        results.extend(fast_results)
        
        # Check if fast evals flagged anything critical
        critical_flag = any(r.score < 0.3 for r in fast_results if r.dimension == EvalDimension.SAFETY)
        
        # Tier 2: LLM Judge (sampled OR flagged)
        if critical_flag or random.random() < self.llm_sample_rate:
            llm_results = await self.llm_judge.evaluate(response)
            results.extend(llm_results)
        
        # Tier 3: Human eval (sampled from interesting cases)
        if self._should_human_eval(response, results):
            await self.human_queue.enqueue(response, results)
        
        # Store all results
        await self.storage.store(response.response_id, results)
        
        # Real-time alerting
        await self._check_alerts(response, results)
    
    def _should_human_eval(self, response: ResponseToEval, 
                           results: List[EvalResult]) -> bool:
        """Smart sampling for human eval - focus on uncertain/borderline cases."""
        # Always: critical safety flags
        if any(r.score < 0.3 and r.dimension == EvalDimension.SAFETY for r in results):
            return True
        
        # Borderline cases (evaluators disagree or low confidence)
        avg_confidence = sum(r.confidence for r in results) / len(results) if results else 1.0
        if avg_confidence < 0.6:
            return True
        
        # Random sample for calibration
        return random.random() < self.human_sample_rate
    
    async def _check_alerts(self, response: ResponseToEval, results: List[EvalResult]):
        """Real-time quality alerting."""
        for result in results:
            if result.score < 0.2:  # Critical quality failure
                await alert_oncall(
                    severity="high",
                    message=f"Quality alert: {result.dimension.value} score={result.score:.2f}",
                    response_id=response.response_id,
                    model=response.model
                )


class LLMJudge:
    """Uses LLM to evaluate response quality across dimensions."""
    
    JUDGE_PROMPT = """Evaluate this AI response on a scale of 1-5 for each dimension.

Query: {query}
Context provided: {context}
Response: {response}

Rate each dimension (1=terrible, 5=excellent):
1. Accuracy: Is the information factually correct?
2. Helpfulness: Does it answer what was asked?
3. Coherence: Is it well-structured and clear?
4. Groundedness: Is it supported by the provided context?

Output JSON: {{"accuracy": N, "helpfulness": N, "coherence": N, "groundedness": N, "reasoning": "..."}}"""
    
    def __init__(self):
        self.judge_model = "gpt-4"  # Use strong model as judge
        self.batch_size = 16  # Batch judge calls for efficiency
    
    async def evaluate(self, response: ResponseToEval) -> List[EvalResult]:
        prompt = self.JUDGE_PROMPT.format(
            query=response.query,
            context=response.context or "None provided",
            response=response.response
        )
        
        start = time.time()
        judgment = await call_llm(self.judge_model, prompt, max_tokens=200)
        latency = (time.time() - start) * 1000
        
        # Parse JSON response
        scores = parse_json(judgment)
        
        results = []
        for dimension, score in scores.items():
            if dimension == "reasoning":
                continue
            results.append(EvalResult(
                dimension=EvalDimension(dimension),
                score=score / 5.0,  # Normalize to 0-1
                confidence=0.8,  # LLM judge confidence
                evaluator="gpt-4-judge",
                reasoning=scores.get("reasoning"),
                latency_ms=latency
            ))
        
        return results


class QualityDashboard:
    """Aggregates eval results into actionable metrics."""
    
    async def get_model_quality_report(self, model: str, 
                                        time_range_hours: int = 24) -> dict:
        """Quality report for a specific model."""
        # Query ClickHouse for aggregated scores
        query = f"""
        SELECT 
            dimension,
            avg(score) as avg_score,
            quantile(0.05)(score) as p5_score,
            count() as eval_count,
            countIf(score < 0.3) as critical_count
        FROM eval_results
        WHERE model = '{model}' 
            AND timestamp > now() - INTERVAL {time_range_hours} HOUR
        GROUP BY dimension
        """
        return await self.storage.query(query)
    
    async def detect_quality_regression(self, model: str) -> Optional[dict]:
        """Compare last hour vs last 24h average."""
        recent = await self.get_model_quality_report(model, time_range_hours=1)
        baseline = await self.get_model_quality_report(model, time_range_hours=24)
        
        regressions = []
        for dim in EvalDimension:
            recent_score = recent.get(dim.value, {}).get("avg_score", 0)
            baseline_score = baseline.get(dim.value, {}).get("avg_score", 0)
            
            if baseline_score > 0 and (baseline_score - recent_score) / baseline_score > 0.05:
                regressions.append({
                    "dimension": dim.value,
                    "drop": f"{(baseline_score - recent_score)*100:.1f}%",
                    "current": recent_score,
                    "baseline": baseline_score
                })
        
        return {"regressions": regressions} if regressions else None
```

### Throughput Design

| Eval Tier | Volume | Compute | Latency | Cost/day |
|-----------|--------|---------|---------|----------|
| Fast classifiers | 10M/day | 20 CPU cores | 5ms | $50 |
| LLM Judge | 1M/day | GPT-4 API | 2s | $5,000 |
| Human eval | 100K/day | Crowd workers | 2-24h | $10,000 |
| **Total** | **10M/day** | | | **~$15,000/day** |

### Production Considerations

- **Judge calibration**: LLM judges have biases (verbosity bias, position bias). Calibrate against human judgments monthly. Adjust prompts if drift detected.
- **Cost management**: LLM judging at 10% sampling costs $5K/day. If budget-constrained, reduce to 5% but maintain stratified sampling (more samples from new models/prompts).
- **Feedback loop**: Evaluation results should feed back into model fine-tuning. Low-scoring responses are negative examples; high-scoring are positive examples.
- **Consistency**: Same response evaluated twice should get similar scores. Track inter-rater reliability for LLM judge (should be >0.8 Cohen's kappa).
- **Latency for blocking evals**: Safety evaluation must be synchronous (block response delivery). Quality evals can be async.

---

## Q90: Scalable prompt management for 500 teams

### Problem
500 teams each have 10-50 prompt templates with versions, A/B tests, and approval workflows. Design a system that prevents prompt chaos while enabling rapid iteration.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Enterprise Prompt Management System                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Prompt Registry (Git-backed, versioned)                     │  │
│  │                                                              │  │
│  │  /org/team-a/prompts/                                       │  │
│  │    ├── summarizer/                                          │  │
│  │    │   ├── v1.yaml (production)                             │  │
│  │    │   ├── v2.yaml (canary: 10%)                            │  │
│  │    │   └── v3.yaml (draft)                                  │  │
│  │    ├── classifier/                                          │  │
│  │    │   └── v1.yaml                                          │  │
│  │    └── ...                                                  │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │ Prompt Serving Layer (low-latency, cached)                  │  │
│  │  - Redis cache of active prompts (< 1ms lookup)             │  │
│  │  - A/B test traffic splitting                               │  │
│  │  - Variable interpolation                                   │  │
│  │  - Guardrail enforcement                                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Governance Layer                                            │  │
│  │  - Approval workflows (safety review for prompts)           │  │
│  │  - Audit trail (who changed what, when)                     │  │
│  │  - Policy enforcement (no PII in prompts, length limits)    │  │
│  │  - Cross-team prompt sharing & discovery                    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import yaml
import random

class PromptStatus(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    CANARY = "canary"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"

@dataclass
class PromptVersion:
    prompt_id: str
    version: int
    team_id: str
    template: str            # The actual prompt template with {variables}
    model: str               # Target model
    parameters: dict         # temperature, max_tokens, etc.
    status: PromptStatus
    traffic_percentage: float  # 0-100, for A/B testing
    created_by: str
    created_at: float
    approved_by: Optional[str] = None
    metrics: dict = field(default_factory=dict)  # Quality scores
    
    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.template.encode()).hexdigest()[:12]

@dataclass
class PromptExperiment:
    experiment_id: str
    prompt_id: str
    variants: List[PromptVersion]  # Each with traffic_percentage
    start_time: float
    end_time: Optional[float]
    success_metric: str  # "user_satisfaction", "task_completion", etc.
    min_sample_size: int = 1000

class PromptRegistry:
    """Central registry for all prompts across 500 teams."""
    
    def __init__(self):
        self.prompts: Dict[str, Dict[int, PromptVersion]] = {}  # prompt_id → {version → prompt}
        self.experiments: Dict[str, PromptExperiment] = {}
        self.serving_cache = {}  # prompt_id → resolved active version(s)
    
    def register_prompt(self, prompt: PromptVersion) -> str:
        """Register a new prompt version."""
        # Validate
        self._validate_prompt(prompt)
        
        if prompt.prompt_id not in self.prompts:
            self.prompts[prompt.prompt_id] = {}
        
        self.prompts[prompt.prompt_id][prompt.version] = prompt
        return prompt.prompt_id
    
    def _validate_prompt(self, prompt: PromptVersion):
        """Enforce organizational policies."""
        # No PII patterns in template
        pii_patterns = [r'\b\d{3}-\d{2}-\d{4}\b', r'password', r'api_key']
        for pattern in pii_patterns:
            if pattern in prompt.template.lower():
                raise PolicyViolation(f"Prompt contains PII pattern: {pattern}")
        
        # Length limits
        if len(prompt.template) > 10000:
            raise PolicyViolation("Prompt exceeds 10K character limit")
        
        # Must have at least one variable (prevents hardcoded prompts)
        if '{' not in prompt.template:
            pass  # Warning, not blocking
    
    def promote_to_production(self, prompt_id: str, version: int, 
                              approved_by: str) -> bool:
        """Promote a prompt to production (requires approval)."""
        prompt = self.prompts[prompt_id][version]
        
        if prompt.status not in [PromptStatus.APPROVED, PromptStatus.CANARY]:
            raise WorkflowError("Prompt must be approved before production")
        
        # Demote current production version
        for v, p in self.prompts[prompt_id].items():
            if p.status == PromptStatus.PRODUCTION:
                p.status = PromptStatus.DEPRECATED
        
        prompt.status = PromptStatus.PRODUCTION
        prompt.traffic_percentage = 100.0
        prompt.approved_by = approved_by
        
        # Update serving cache
        self._update_serving_cache(prompt_id)
        return True
    
    def start_experiment(self, prompt_id: str, 
                         variant_versions: List[int],
                         traffic_split: List[float],
                         success_metric: str) -> str:
        """Start A/B test between prompt versions."""
        assert sum(traffic_split) == 100.0
        
        variants = []
        for version, traffic in zip(variant_versions, traffic_split):
            prompt = self.prompts[prompt_id][version]
            prompt.traffic_percentage = traffic
            prompt.status = PromptStatus.CANARY
            variants.append(prompt)
        
        experiment = PromptExperiment(
            experiment_id=f"exp_{prompt_id}_{int(time.time())}",
            prompt_id=prompt_id,
            variants=variants,
            start_time=time.time(),
            end_time=None,
            success_metric=success_metric
        )
        
        self.experiments[experiment.experiment_id] = experiment
        self._update_serving_cache(prompt_id)
        return experiment.experiment_id
    
    def _update_serving_cache(self, prompt_id: str):
        """Update the fast-lookup cache for serving."""
        active_versions = [
            p for p in self.prompts[prompt_id].values()
            if p.status in [PromptStatus.PRODUCTION, PromptStatus.CANARY]
            and p.traffic_percentage > 0
        ]
        self.serving_cache[prompt_id] = active_versions


class PromptServingLayer:
    """Low-latency prompt resolution with A/B testing."""
    
    def __init__(self, registry: PromptRegistry):
        self.registry = registry
        self.redis_cache = None  # Redis for distributed cache
    
    def resolve_prompt(self, prompt_id: str, variables: Dict[str, str],
                       user_id: str = None) -> str:
        """Resolve prompt template with variables and A/B routing."""
        # Get active versions
        active = self.registry.serving_cache.get(prompt_id, [])
        
        if not active:
            raise PromptNotFound(f"No active version for {prompt_id}")
        
        # A/B test routing (deterministic by user_id for consistency)
        selected = self._select_variant(active, user_id)
        
        # Interpolate variables
        rendered = self._render_template(selected.template, variables)
        
        # Apply guardrails
        rendered = self._apply_guardrails(rendered, selected)
        
        return rendered
    
    def _select_variant(self, variants: List[PromptVersion], 
                        user_id: Optional[str]) -> PromptVersion:
        """Deterministic variant selection for A/B consistency."""
        if len(variants) == 1:
            return variants[0]
        
        # Deterministic hash for user consistency
        if user_id:
            hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100
        else:
            hash_val = random.randint(0, 99)
        
        cumulative = 0
        for variant in variants:
            cumulative += variant.traffic_percentage
            if hash_val < cumulative:
                return variant
        
        return variants[-1]  # Fallback
    
    def _render_template(self, template: str, variables: Dict[str, str]) -> str:
        """Safe template rendering with variable validation."""
        try:
            # Only allow whitelisted variables
            rendered = template.format(**variables)
            return rendered
        except KeyError as e:
            raise MissingVariable(f"Required variable not provided: {e}")
    
    def _apply_guardrails(self, rendered: str, prompt: PromptVersion) -> str:
        """Apply safety guardrails to rendered prompt."""
        # Inject system-level safety prefix if not present
        safety_prefix = "You must not generate harmful, illegal, or discriminatory content."
        if safety_prefix not in rendered:
            rendered = f"{safety_prefix}\n\n{rendered}"
        
        # Truncate if exceeds model context
        max_chars = 50000  # ~12K tokens
        if len(rendered) > max_chars:
            rendered = rendered[:max_chars]
        
        return rendered


class PromptAnalytics:
    """Track prompt performance for optimization."""
    
    async def get_experiment_results(self, experiment_id: str) -> dict:
        """Get A/B test results with statistical significance."""
        experiment = self.registry.experiments[experiment_id]
        
        results = {}
        for variant in experiment.variants:
            metrics = await self._get_variant_metrics(
                variant, experiment.success_metric
            )
            results[f"v{variant.version}"] = metrics
        
        # Statistical significance test
        if len(results) == 2:
            variants = list(results.values())
            significant = self._chi_squared_test(variants[0], variants[1])
            results["statistically_significant"] = significant
        
        return results
    
    async def _get_variant_metrics(self, variant: PromptVersion, 
                                    metric_name: str) -> dict:
        """Get aggregated metrics for a prompt variant."""
        return {
            "sample_size": 5000,
            "metric_value": 0.82,
            "confidence_interval": (0.79, 0.85),
        }
    
    def _chi_squared_test(self, control: dict, treatment: dict) -> bool:
        """Test if difference is statistically significant (p<0.05)."""
        # Simplified
        return True
```

### Scale Considerations

| Dimension | Scale | Solution |
|-----------|-------|----------|
| Teams | 500 | Namespace isolation, RBAC per team |
| Prompts | 25,000 (50 per team) | Git-backed registry, indexed search |
| Versions | 250,000 (10 per prompt) | Efficient storage, prune old versions |
| Lookups/sec | 100K | Redis cache, <1ms resolution |
| A/B tests | 200 concurrent | Deterministic hashing, shared nothing |

### Production Considerations

- **Rollback**: One-click rollback to previous production version. Automated rollback if quality scores drop >10% within 1 hour of promotion.
- **Cross-team discovery**: Searchable catalog of all prompts. Teams can fork/reuse prompts from other teams (with attribution).
- **Cost tracking**: Each prompt version has an associated cost profile (model × avg tokens × volume). Dashboard shows cost impact of prompt changes.
- **Compliance**: Audit log of all prompt changes for SOC2/HIPAA. Prompts handling sensitive data require security review.
- **Testing**: CI/CD pipeline runs prompt against golden test set before approval. Must pass quality threshold to be promotable.
# Reliability and Resilience for AI Systems (Questions 91-95)

## Q91: Fault-tolerant LLM inference with 99.99% availability

### Problem
99.99% = 52 minutes downtime/year. Single provider outages (OpenAI had 8+ hours in 2023) are unacceptable. Design multi-provider failover with consistent API, graceful degradation, and zero-downtime deployments.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│           Fault-Tolerant LLM Inference Platform                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Unified Gateway (single API, multiple backends)             │ │
│  │  POST /v1/chat/completions                                  │ │
│  │  - Translates to provider-specific APIs                     │ │
│  │  - Handles retries, failover, hedging                       │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                   │
│  ┌────────────────────────────▼───────────────────────────────┐ │
│  │ Provider Health Monitor                                     │ │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────────┐ │ │
│  │  │ OpenAI  │  │Anthropic│  │ Azure    │  │ Self-hosted│ │ │
│  │  │ ●●●●○   │  │ ●●●●●   │  │ ●●●○○   │  │ ●●●●●     │ │ │
│  │  │ p99:800 │  │ p99:600 │  │ p99:900 │  │ p99:400   │ │ │
│  │  │ err:0.1%│  │ err:0.0%│  │ err:0.3%│  │ err:0.0% │ │ │
│  │  └─────────┘  └─────────┘  └──────────┘  └────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Failover Strategy                                           │ │
│  │  Primary: OpenAI GPT-4                                      │ │
│  │  Secondary: Anthropic Claude (warm, parallel health checks)│ │
│  │  Tertiary: Self-hosted Llama-70B (always hot)               │ │
│  │  Last resort: Cached responses + degraded mode              │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from collections import deque
import random

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"

@dataclass
class ProviderConfig:
    name: str
    model_mapping: Dict[str, str]  # canonical → provider-specific model
    priority: int                   # Lower = preferred
    max_concurrent: int
    timeout_ms: float
    cost_multiplier: float          # Relative cost (1.0 = baseline)

@dataclass
class ProviderHealth:
    status: ProviderStatus
    error_rate_1min: float
    p99_latency_ms: float
    consecutive_failures: int
    last_success: float
    circuit_open_until: float = 0.0

class MultiProviderLLMGateway:
    """Unified gateway with automatic failover across LLM providers."""
    
    def __init__(self, providers: List[ProviderConfig]):
        self.providers = {p.name: p for p in providers}
        self.health: Dict[str, ProviderHealth] = {
            p.name: ProviderHealth(
                status=ProviderStatus.HEALTHY,
                error_rate_1min=0.0,
                p99_latency_ms=0.0,
                consecutive_failures=0,
                last_success=time.time()
            ) for p in providers
        }
        self.request_log: Dict[str, deque] = {p.name: deque(maxlen=1000) for p in providers}
        
        # Start health check loop
        asyncio.create_task(self._health_check_loop())
    
    async def complete(self, messages: List[dict], model: str = "gpt-4",
                       max_tokens: int = 1024, **kwargs) -> dict:
        """Route request with failover."""
        # Get providers in priority order (filtered by health)
        available = self._get_available_providers(model)
        
        if not available:
            # Last resort: return cached/degraded response
            return await self._degraded_response(messages)
        
        # Strategy selection based on SLA requirements
        strategy = kwargs.get("strategy", "failover")  # "failover" | "hedged" | "fastest"
        
        if strategy == "hedged":
            return await self._hedged_request(available[:2], messages, model, max_tokens)
        else:
            return await self._failover_request(available, messages, model, max_tokens)
    
    async def _failover_request(self, providers: List[str], messages: List[dict],
                                 model: str, max_tokens: int) -> dict:
        """Try providers in order, failover on error."""
        last_error = None
        
        for provider_name in providers:
            provider = self.providers[provider_name]
            mapped_model = provider.model_mapping.get(model, model)
            
            try:
                start = time.time()
                result = await asyncio.wait_for(
                    self._call_provider(provider_name, mapped_model, messages, max_tokens),
                    timeout=provider.timeout_ms / 1000
                )
                
                # Success: record metrics
                latency = (time.time() - start) * 1000
                self._record_success(provider_name, latency)
                result["_provider"] = provider_name
                return result
                
            except Exception as e:
                last_error = e
                self._record_failure(provider_name, e)
                continue  # Try next provider
        
        raise AllProvidersFailedError(f"All providers failed. Last error: {last_error}")
    
    async def _hedged_request(self, providers: List[str], messages: List[dict],
                               model: str, max_tokens: int) -> dict:
        """Send to multiple providers, return first response."""
        tasks = []
        for provider_name in providers:
            provider = self.providers[provider_name]
            mapped_model = provider.model_mapping.get(model, model)
            task = asyncio.create_task(
                self._call_provider(provider_name, mapped_model, messages, max_tokens)
            )
            tasks.append((provider_name, task))
        
        # Return first successful result
        done, pending = await asyncio.wait(
            [t for _, t in tasks],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel remaining
        for task in pending:
            task.cancel()
        
        for provider_name, task in tasks:
            if task in done and not task.exception():
                result = task.result()
                result["_provider"] = provider_name
                return result
        
        raise AllProvidersFailedError("Hedged request: all providers failed")
    
    def _get_available_providers(self, model: str) -> List[str]:
        """Get healthy providers that support this model, sorted by priority."""
        available = []
        for name, provider in self.providers.items():
            if model not in provider.model_mapping and model != provider.model_mapping.get(model):
                continue
            health = self.health[name]
            if health.status == ProviderStatus.CIRCUIT_OPEN:
                if time.time() < health.circuit_open_until:
                    continue  # Circuit still open
                else:
                    health.status = ProviderStatus.DEGRADED  # Half-open
            if health.status != ProviderStatus.UNHEALTHY:
                available.append(name)
        
        # Sort by: priority, then health, then cost
        available.sort(key=lambda n: (
            self.providers[n].priority,
            0 if self.health[n].status == ProviderStatus.HEALTHY else 1,
            self.providers[n].cost_multiplier
        ))
        return available
    
    def _record_success(self, provider: str, latency_ms: float):
        health = self.health[provider]
        health.consecutive_failures = 0
        health.last_success = time.time()
        health.status = ProviderStatus.HEALTHY
        self.request_log[provider].append(("success", latency_ms, time.time()))
    
    def _record_failure(self, provider: str, error: Exception):
        health = self.health[provider]
        health.consecutive_failures += 1
        self.request_log[provider].append(("failure", 0, time.time()))
        
        # Circuit breaker logic
        if health.consecutive_failures >= 5:
            health.status = ProviderStatus.CIRCUIT_OPEN
            health.circuit_open_until = time.time() + 30  # Open for 30s
        elif health.consecutive_failures >= 3:
            health.status = ProviderStatus.DEGRADED
    
    async def _health_check_loop(self):
        """Continuous health probing."""
        while True:
            for provider_name in self.providers:
                try:
                    start = time.time()
                    await self._call_provider(
                        provider_name, "gpt-3.5-turbo",
                        [{"role": "user", "content": "hi"}], max_tokens=1
                    )
                    latency = (time.time() - start) * 1000
                    self.health[provider_name].p99_latency_ms = latency
                except Exception:
                    pass
            await asyncio.sleep(10)  # Check every 10s
    
    async def _degraded_response(self, messages: List[dict]) -> dict:
        """Last resort: return degraded response."""
        return {
            "choices": [{"message": {"content": "I'm experiencing high demand. Please try again in a moment."}}],
            "_provider": "degraded",
            "_degraded": True
        }
    
    async def _call_provider(self, provider: str, model: str,
                              messages: List[dict], max_tokens: int) -> dict:
        """Call specific provider API."""
        # Implementation per provider
        pass


class AllProvidersFailedError(Exception):
    pass
```

### Availability Calculation

| Component | Availability | Downtime/year |
|-----------|-------------|---------------|
| OpenAI alone | 99.5% | 44 hours |
| + Anthropic failover | 99.99% | 53 min |
| + Self-hosted failover | 99.999% | 5 min |
| + Degraded mode cache | ~100% | ~0 (degraded) |

### Production Considerations

- **Response consistency**: Different providers produce different outputs. For idempotent operations, this is fine. For stateful conversations, stick to one provider per session unless it fails.
- **Cost awareness**: Hedged requests cost 2x. Use only for critical-path requests where latency SLA is tight.
- **Model parity testing**: Monthly evaluation comparing outputs across providers. Ensure fallback quality is acceptable.
- **Rate limit coordination**: Track rate limits per provider. Don't failover traffic that would exceed secondary's rate limit.
- **Observability**: Dashboard showing per-provider success rate, latency, cost, and failover frequency. Alert if failover rate exceeds 5%.

---

## Q92: Chaos engineering framework for AI systems

### Problem
AI systems have unique failure modes beyond traditional software: model drift, embedding space corruption, hallucination spikes, GPU memory leaks, tokenizer edge cases. Design a chaos engineering framework that tests these AI-specific failures.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│               AI Chaos Engineering Framework                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Chaos Experiment Catalog                                    │  │
│  │                                                              │  │
│  │  Traditional:          AI-Specific:                         │  │
│  │  - Kill GPU node       - Inject hallucinated context        │  │
│  │  - Network partition   - Corrupt embedding vectors          │  │
│  │  - Disk full           - Model version mismatch             │  │
│  │  - High latency        - Tokenizer OOV spike               │  │
│  │                        - GPU OOM on large prompt            │  │
│  │                        - Feature store stale data           │  │
│  │                        - Safety classifier false positives  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Experiment Runner                                           │  │
│  │  - Shadow mode (test against shadow traffic, no impact)     │  │
│  │  - Canary mode (inject on 1% of traffic with monitoring)    │  │
│  │  - Full mode (production blast radius with kill switch)     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Safety Controls                                             │  │
│  │  - Blast radius limits (max % affected)                     │  │
│  │  - Automatic rollback on SLO breach                         │  │
│  │  - Business hours only (configurable)                       │  │
│  │  - Kill switch (one-click abort all experiments)            │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
import random
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Any
from enum import Enum
from abc import ABC, abstractmethod

class ExperimentMode(Enum):
    SHADOW = "shadow"    # No production impact
    CANARY = "canary"    # 1% of traffic
    PRODUCTION = "production"  # Full blast radius

class ExperimentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"

@dataclass
class ExperimentConfig:
    name: str
    description: str
    mode: ExperimentMode
    blast_radius_percent: float  # Max % of traffic affected
    duration_seconds: int
    abort_conditions: List[dict]  # Auto-abort if these trigger
    schedule: Optional[str] = None  # Cron expression

@dataclass
class ExperimentResult:
    experiment_name: str
    status: ExperimentStatus
    start_time: float
    end_time: float
    impact_metrics: dict
    findings: List[str]
    recommendations: List[str]

class ChaosExperiment(ABC):
    """Base class for all chaos experiments."""
    
    @abstractmethod
    async def inject(self, target: Any) -> None:
        """Inject the failure condition."""
        pass
    
    @abstractmethod
    async def rollback(self, target: Any) -> None:
        """Reverse the injection."""
        pass
    
    @abstractmethod
    def get_observables(self) -> List[str]:
        """Metrics to monitor during experiment."""
        pass


class EmbeddingCorruptionExperiment(ChaosExperiment):
    """Simulate corrupted embeddings (e.g., wrong model version deployed)."""
    
    def __init__(self, corruption_type: str = "gaussian_noise", magnitude: float = 0.1):
        self.corruption_type = corruption_type
        self.magnitude = magnitude
        self.original_embed_fn = None
    
    async def inject(self, embedding_service):
        """Monkey-patch embedding service to return corrupted vectors."""
        self.original_embed_fn = embedding_service.embed
        
        async def corrupted_embed(texts):
            embeddings = await self.original_embed_fn(texts)
            if self.corruption_type == "gaussian_noise":
                noise = np.random.normal(0, self.magnitude, embeddings.shape)
                return embeddings + noise
            elif self.corruption_type == "zero_out":
                # Simulate model returning zeros (OOM, crash)
                return np.zeros_like(embeddings)
            elif self.corruption_type == "dimension_shift":
                # Simulate wrong model version (different embedding space)
                return np.roll(embeddings, 128, axis=1)
            return embeddings
        
        embedding_service.embed = corrupted_embed
    
    async def rollback(self, embedding_service):
        embedding_service.embed = self.original_embed_fn
    
    def get_observables(self) -> List[str]:
        return ["retrieval_recall@10", "embedding_cosine_similarity", "user_satisfaction"]


class HallucinationInjectionExperiment(ChaosExperiment):
    """Simulate LLM hallucination spike by injecting false context."""
    
    def __init__(self, injection_rate: float = 0.1):
        self.injection_rate = injection_rate
    
    async def inject(self, rag_pipeline):
        """Inject fabricated context into RAG pipeline."""
        original_retrieve = rag_pipeline.retrieve
        
        async def poisoned_retrieve(query, top_k=10):
            results = await original_retrieve(query, top_k)
            
            if random.random() < self.injection_rate:
                # Replace one real result with fabricated content
                fake_doc = {
                    "text": f"According to official sources, {self._generate_plausible_false_claim(query)}",
                    "score": 0.95,  # High relevance score
                    "source": "injected_chaos"
                }
                results[0] = fake_doc  # Replace top result
            
            return results
        
        rag_pipeline.retrieve = poisoned_retrieve
        self._original = original_retrieve
    
    async def rollback(self, rag_pipeline):
        rag_pipeline.retrieve = self._original
    
    def _generate_plausible_false_claim(self, query: str) -> str:
        return f"the answer to '{query}' has been updated as of 2024."
    
    def get_observables(self) -> List[str]:
        return ["groundedness_score", "factual_accuracy", "citation_rate"]


class GPUMemoryPressureExperiment(ChaosExperiment):
    """Simulate GPU OOM conditions with large prompts."""
    
    def __init__(self, memory_pressure_gb: float = 10.0):
        self.pressure_gb = memory_pressure_gb
        self.allocated_tensor = None
    
    async def inject(self, gpu_node):
        """Allocate GPU memory to simulate pressure."""
        import torch
        # Allocate tensor to consume GPU memory
        elements = int(self.pressure_gb * 1024**3 / 4)  # float32
        self.allocated_tensor = torch.zeros(elements, device='cuda')
    
    async def rollback(self, gpu_node):
        if self.allocated_tensor is not None:
            del self.allocated_tensor
            import torch
            torch.cuda.empty_cache()
    
    def get_observables(self) -> List[str]:
        return ["gpu_memory_utilization", "oom_errors", "request_latency_p99", "eviction_rate"]


class ChaosOrchestrator:
    """Manages chaos experiment lifecycle with safety controls."""
    
    def __init__(self):
        self.active_experiments: Dict[str, ChaosExperiment] = {}
        self.results: List[ExperimentResult] = []
        self.kill_switch = False
    
    async def run_experiment(self, experiment: ChaosExperiment, 
                             config: ExperimentConfig, target: Any) -> ExperimentResult:
        """Run a chaos experiment with safety controls."""
        # Pre-checks
        if self.kill_switch:
            return self._aborted_result(config, "Kill switch active")
        
        if config.mode == ExperimentMode.PRODUCTION:
            if not self._is_business_hours():
                return self._aborted_result(config, "Outside allowed hours")
        
        # Record baseline metrics
        baseline = await self._capture_metrics(experiment.get_observables())
        
        # Inject failure
        start_time = time.time()
        self.active_experiments[config.name] = experiment
        
        try:
            await experiment.inject(target)
            
            # Monitor during experiment
            findings = []
            while time.time() - start_time < config.duration_seconds:
                if self.kill_switch:
                    break
                
                current_metrics = await self._capture_metrics(experiment.get_observables())
                
                # Check abort conditions
                if self._should_abort(config, baseline, current_metrics):
                    findings.append("Auto-aborted: SLO breach detected")
                    break
                
                await asyncio.sleep(5)  # Check every 5s
            
        finally:
            # Always rollback
            await experiment.rollback(target)
            del self.active_experiments[config.name]
        
        # Capture impact
        end_time = time.time()
        post_metrics = await self._capture_metrics(experiment.get_observables())
        
        result = ExperimentResult(
            experiment_name=config.name,
            status=ExperimentStatus.COMPLETED,
            start_time=start_time,
            end_time=end_time,
            impact_metrics={"baseline": baseline, "during": current_metrics, "after": post_metrics},
            findings=findings,
            recommendations=self._generate_recommendations(baseline, current_metrics, config)
        )
        
        self.results.append(result)
        return result
    
    def _should_abort(self, config: ExperimentConfig, baseline: dict, 
                      current: dict) -> bool:
        """Check if experiment should be automatically aborted."""
        for condition in config.abort_conditions:
            metric = condition["metric"]
            threshold = condition["threshold"]
            
            if metric in current and metric in baseline:
                if condition.get("type") == "increase":
                    if current[metric] > baseline[metric] * (1 + threshold):
                        return True
                elif condition.get("type") == "decrease":
                    if current[metric] < baseline[metric] * (1 - threshold):
                        return True
        return False
    
    def _generate_recommendations(self, baseline: dict, during: dict, 
                                   config: ExperimentConfig) -> List[str]:
        """Generate actionable recommendations from experiment."""
        recs = []
        # Example: if embedding corruption caused >20% recall drop
        if "retrieval_recall@10" in during and "retrieval_recall@10" in baseline:
            drop = baseline["retrieval_recall@10"] - during["retrieval_recall@10"]
            if drop > 0.2:
                recs.append("CRITICAL: System has no defense against embedding corruption. "
                          "Implement embedding validation checksums and anomaly detection.")
        return recs
    
    async def _capture_metrics(self, metric_names: List[str]) -> dict:
        return {m: random.random() for m in metric_names}  # Placeholder
    
    def _is_business_hours(self) -> bool:
        hour = time.localtime().tm_hour
        return 9 <= hour <= 17
    
    def _aborted_result(self, config: ExperimentConfig, reason: str) -> ExperimentResult:
        return ExperimentResult(
            experiment_name=config.name, status=ExperimentStatus.ABORTED,
            start_time=time.time(), end_time=time.time(),
            impact_metrics={}, findings=[reason], recommendations=[]
        )
```

### AI-Specific Failure Modes Catalog

| Failure Mode | Impact | Detection Time (without chaos) | Mitigation |
|-------------|--------|-------------------------------|------------|
| Embedding corruption | Silent recall degradation | Days-weeks | Embedding checksum validation |
| Hallucination spike | User trust loss | Hours (if monitored) | Groundedness checker |
| GPU OOM | Request failures | Immediate | Memory budgets, request sizing |
| Model version mismatch | Subtle quality drop | Days | Version pinning, canary deploy |
| Tokenizer overflow | Truncated context | Per-request | Input validation |
| Safety classifier failure | Harmful content served | Depends on monitoring | Multi-layer safety |
| Feature store staleness | Prediction quality drop | Hours-days | Freshness monitoring |

### Production Considerations

- **Game days**: Monthly chaos game days where the team practices incident response with known injections.
- **Graduated blast radius**: Start at 0.1% shadow traffic, graduate to 1% canary, then 5% production over weeks.
- **Compliance**: Some industries (healthcare, finance) require advance notice of chaos experiments. Document everything.
- **Cost of experiments**: LLM chaos experiments consume tokens. Budget $500-2000/month for chaos testing.
- **Knowledge base**: Build a failure knowledge base from experiments. "We know our system degrades X way when Y happens."

---

## Q93: Circuit breaker and bulkhead patterns for AI microservices

### Problem
Your pipeline: User → Gateway → Embedding Service → Vector DB → LLM → Safety Classifier → Response. Any component failure shouldn't cascade. Design circuit breakers and bulkheads for AI-specific workloads.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│          Resilience Patterns for AI Pipeline                    │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Bulkhead Isolation (separate thread/connection pools)     │  │
│  │                                                           │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │  │
│  │  │ Embedding  │  │ LLM Pool   │  │ Safety Classifier  │ │  │
│  │  │ Pool       │  │            │  │ Pool               │ │  │
│  │  │ 50 conns   │  │ 100 conns  │  │ 30 conns           │ │  │
│  │  │ Timeout:   │  │ Timeout:   │  │ Timeout:           │ │  │
│  │  │ 200ms      │  │ 30s        │  │ 500ms              │ │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Circuit Breakers (per service, per operation)             │  │
│  │                                                           │  │
│  │  Embedding:  [CLOSED] ●●●●●●●●●○  (1% error rate)      │  │
│  │  VectorDB:   [CLOSED] ●●●●●●●●●●  (0% error rate)      │  │
│  │  LLM-GPT4:   [HALF]   ●●●●●○○○○○  (50% - testing)      │  │
│  │  LLM-Claude:  [CLOSED] ●●●●●●●●●●  (0% error rate)      │  │
│  │  Safety:     [CLOSED] ●●●●●●●●●●  (0% error rate)      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Fallback Strategies (per component)                       │  │
│  │                                                           │  │
│  │  Embedding failed → cached embedding OR keyword search    │  │
│  │  VectorDB failed  → fallback to BM25 sparse retrieval    │  │
│  │  LLM failed       → switch provider OR return cached      │  │
│  │  Safety failed    → BLOCK response (fail-safe)            │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Any, Dict
from enum import Enum
from collections import deque
import functools

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject immediately
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 3      # Successes in half-open to close
    timeout_seconds: float = 30.0   # Time in open before half-open
    window_seconds: float = 60.0    # Sliding window for counting
    # AI-specific: slow responses count as partial failures
    slow_call_threshold_ms: float = 5000.0
    slow_call_rate_threshold: float = 0.5  # >50% slow = degraded

class CircuitBreaker:
    """Circuit breaker with AI-specific adaptations."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.state_change_time = time.time()
        self.call_history: deque = deque(maxlen=100)  # (timestamp, success, latency_ms)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.state_change_time > self.config.timeout_seconds:
                self._transition(CircuitState.HALF_OPEN)
            else:
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow limited requests through
            pass
        
        try:
            start = time.time()
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.slow_call_threshold_ms / 1000 * 2
            )
            latency_ms = (time.time() - start) * 1000
            
            # Record success
            self._record_call(True, latency_ms)
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._transition(CircuitState.CLOSED)
            
            return result
            
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            self._record_call(False, latency_ms)
            self._on_failure()
            raise
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open reopens circuit
            self._transition(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition(CircuitState.OPEN)
    
    def _record_call(self, success: bool, latency_ms: float):
        self.call_history.append((time.time(), success, latency_ms))
        
        # Check slow call rate (AI-specific)
        recent = [(s, l) for t, s, l in self.call_history if time.time() - t < 60]
        if recent:
            slow_rate = sum(1 for s, l in recent if l > self.config.slow_call_threshold_ms) / len(recent)
            if slow_rate > self.config.slow_call_rate_threshold:
                self._transition(CircuitState.OPEN)
    
    def _transition(self, new_state: CircuitState):
        self.state = new_state
        self.state_change_time = time.time()
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0


class Bulkhead:
    """Limits concurrent access to a resource."""
    
    def __init__(self, name: str, max_concurrent: int, max_queue: int = 100):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_queue = max_queue
        self.queued = 0
        self.active = 0
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        if self.queued >= self.max_queue:
            raise BulkheadFullError(f"Bulkhead {self.name} queue full")
        
        self.queued += 1
        try:
            async with self.semaphore:
                self.queued -= 1
                self.active += 1
                try:
                    return await func(*args, **kwargs)
                finally:
                    self.active -= 1
        except Exception:
            self.queued -= 1
            raise


class ResilientAIPipeline:
    """Full AI pipeline with circuit breakers and bulkheads."""
    
    def __init__(self):
        # Bulkheads: isolate resource pools
        self.embedding_bulkhead = Bulkhead("embedding", max_concurrent=50)
        self.llm_bulkhead = Bulkhead("llm", max_concurrent=100)
        self.safety_bulkhead = Bulkhead("safety", max_concurrent=30)
        
        # Circuit breakers: per service
        self.embedding_cb = CircuitBreaker("embedding", CircuitBreakerConfig(
            failure_threshold=5, slow_call_threshold_ms=500
        ))
        self.llm_cb = CircuitBreaker("llm", CircuitBreakerConfig(
            failure_threshold=3, slow_call_threshold_ms=10000, timeout_seconds=60
        ))
        self.safety_cb = CircuitBreaker("safety", CircuitBreakerConfig(
            failure_threshold=10, slow_call_threshold_ms=1000
        ))
    
    async def process_request(self, query: str) -> dict:
        """Process with full resilience patterns."""
        
        # Step 1: Embedding (with fallback to keyword search)
        try:
            embedding = await self.embedding_bulkhead.execute(
                self.embedding_cb.call, self._embed, query
            )
        except (CircuitOpenError, BulkheadFullError):
            # Fallback: keyword-based retrieval
            embedding = None
        
        # Step 2: Retrieval
        if embedding is not None:
            docs = await self._vector_search(embedding)
        else:
            docs = await self._keyword_search(query)
        
        # Step 3: LLM generation (with provider failover)
        try:
            response = await self.llm_bulkhead.execute(
                self.llm_cb.call, self._generate, query, docs
            )
        except CircuitOpenError:
            # Failover to alternative provider
            response = await self._generate_fallback(query, docs)
        except BulkheadFullError:
            # Shed load
            return {"error": "Service busy", "retry_after": 5}
        
        # Step 4: Safety check (FAIL-SAFE: block if uncertain)
        try:
            is_safe = await self.safety_bulkhead.execute(
                self.safety_cb.call, self._safety_check, response
            )
        except (CircuitOpenError, BulkheadFullError):
            # Safety failure = BLOCK (fail-safe, not fail-open)
            is_safe = False
        
        if not is_safe:
            return {"response": "I cannot provide that response.", "blocked": True}
        
        return {"response": response}
    
    async def _embed(self, text: str):
        pass
    async def _vector_search(self, embedding):
        pass
    async def _keyword_search(self, query: str):
        pass
    async def _generate(self, query: str, docs: list):
        pass
    async def _generate_fallback(self, query: str, docs: list):
        pass
    async def _safety_check(self, response: str):
        pass


class CircuitOpenError(Exception):
    pass

class BulkheadFullError(Exception):
    pass
```

### Key Design Decision: Fail-Safe vs Fail-Open

| Component | Failure Mode | Strategy | Rationale |
|-----------|-------------|----------|-----------|
| Embedding service | Circuit open | Fail-OPEN (degrade to keyword) | Better some results than none |
| Vector DB | Timeout | Fail-OPEN (sparse fallback) | User still gets an answer |
| LLM | Provider down | Fail-OPEN (switch provider) | Maintain service |
| Safety classifier | Circuit open | Fail-SAFE (BLOCK response) | Never serve unsafe content |
| Re-ranker | Slow | Fail-OPEN (skip reranking) | Slightly lower quality OK |

### Production Considerations

- **AI-specific slow calls**: LLM calls are inherently slow (seconds). Circuit breaker must distinguish "normal slow" from "degraded slow." Use adaptive thresholds based on rolling p99.
- **Cascading GPU failures**: One GPU OOM can cascade if retry logic floods other GPUs. Implement backoff + jitter on retries.
- **Bulkhead sizing**: LLM bulkhead must account for varying request costs. 100 concurrent short requests ≠ 100 concurrent long requests. Consider token-weighted bulkheads.
- **Monitoring**: Real-time circuit state dashboard. Alert when any circuit opens. Weekly report on circuit open frequency per service.
- **Testing**: Run chaos experiments monthly to verify circuit breakers actually work. Dead code in production is dangerous.

---

## Q94: Disaster recovery for RAG systems

### Problem
Your primary vector database (500M embeddings, 2TB) is completely lost. What's your RPO (data loss tolerance) and RTO (recovery time)? Design multi-region failover with continuous replication.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│               RAG Disaster Recovery Architecture                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────────────────┐   ┌──────────────────┐ │
│  │ PRIMARY (us-east-1)                  │   │ DR STRATEGY      │ │
│  │                                      │   │                  │ │
│  │  ┌──────────────────────────────┐   │   │ RPO: 15 minutes  │ │
│  │  │ Vector DB (Qdrant/Pinecone)  │   │   │ RTO: 5 minutes   │ │
│  │  │ 500M vectors, 2TB           │   │   │                  │ │
│  │  └──────────────┬───────────────┘   │   │ Tier 1: Hot      │ │
│  │                 │                    │   │ standby (async   │ │
│  │  ┌──────────────▼───────────────┐   │   │ replication)     │ │
│  │  │ Change Data Capture (CDC)     │   │   │                  │ │
│  │  │ - Capture every insert/update │   │   │ Tier 2: Warm     │ │
│  │  │ - Stream to replication topic │   │   │ (rebuild from    │ │
│  │  └──────────────┬───────────────┘   │   │ source docs)     │ │
│  │                 │                    │   │                  │ │
│  └─────────────────┼────────────────────┘   │ Tier 3: Cold     │ │
│                    │                         │ (re-embed from   │ │
│  ┌─────────────────▼─────────────────────┐  │ scratch)         │ │
│  │ Replication Stream (Kafka, cross-region)│  └──────────────────┘ │
│  └─────────────────┬─────────────────────┘                        │
│                    │                                               │
│  ┌─────────────────▼────────────────────┐                        │
│  │ SECONDARY (eu-west-1) - Hot Standby   │                        │
│  │                                       │                        │
│  │  ┌──────────────────────────────┐    │                        │
│  │  │ Vector DB (replica)          │    │                        │
│  │  │ 500M vectors, ~15min behind  │    │                        │
│  │  └──────────────────────────────┘    │                        │
│  │                                       │                        │
│  │  ┌──────────────────────────────┐    │                        │
│  │  │ Read-only until failover     │    │                        │
│  │  │ Health: STANDBY              │    │                        │
│  │  └──────────────────────────────┘    │                        │
│  └───────────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

class RegionRole(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"  # Hot standby
    REBUILDING = "rebuilding"  # Being reconstructed

@dataclass
class RegionState:
    region: str
    role: RegionRole
    vector_count: int
    replication_lag_seconds: float
    last_health_check: float
    healthy: bool

@dataclass
class DRConfig:
    rpo_seconds: int = 900       # 15 min acceptable data loss
    rto_seconds: int = 300       # 5 min recovery time target
    replication_batch_size: int = 1000
    health_check_interval: int = 10
    failover_threshold_missed_checks: int = 3

class VectorDBReplicator:
    """Continuous replication of vector database across regions."""
    
    def __init__(self, config: DRConfig):
        self.config = config
        self.replication_position = 0  # Kafka offset
        self.lag_seconds = 0
    
    async def replicate_continuous(self, source_stream, target_db):
        """Consume CDC stream and apply to secondary."""
        batch = []
        last_flush = time.time()
        
        async for event in source_stream:
            batch.append(event)
            
            # Flush batch when full or timeout
            should_flush = (
                len(batch) >= self.config.replication_batch_size or
                time.time() - last_flush > 1.0  # Max 1s delay
            )
            
            if should_flush:
                await self._apply_batch(target_db, batch)
                self.replication_position = batch[-1]["offset"]
                self.lag_seconds = time.time() - batch[-1]["timestamp"]
                batch = []
                last_flush = time.time()
    
    async def _apply_batch(self, target_db, batch: List[dict]):
        """Apply replication batch to target vector DB."""
        inserts = [e for e in batch if e["op"] == "INSERT"]
        deletes = [e for e in batch if e["op"] == "DELETE"]
        updates = [e for e in batch if e["op"] == "UPDATE"]
        
        if inserts:
            vectors = [(e["id"], e["vector"], e["metadata"]) for e in inserts]
            await target_db.upsert_batch(vectors)
        
        if deletes:
            ids = [e["id"] for e in deletes]
            await target_db.delete_batch(ids)
        
        if updates:
            vectors = [(e["id"], e["vector"], e["metadata"]) for e in updates]
            await target_db.upsert_batch(vectors)


class DisasterRecoveryManager:
    """Orchestrates failover and recovery procedures."""
    
    def __init__(self, config: DRConfig):
        self.config = config
        self.regions: Dict[str, RegionState] = {}
        self.current_primary: Optional[str] = None
        self.failover_in_progress = False
    
    async def monitor_and_failover(self):
        """Continuous monitoring with automatic failover."""
        missed_checks = 0
        
        while True:
            primary_healthy = await self._check_primary_health()
            
            if not primary_healthy:
                missed_checks += 1
                if missed_checks >= self.config.failover_threshold_missed_checks:
                    await self.execute_failover()
                    missed_checks = 0
            else:
                missed_checks = 0
            
            await asyncio.sleep(self.config.health_check_interval)
    
    async def execute_failover(self):
        """Execute failover to secondary region."""
        if self.failover_in_progress:
            return
        
        self.failover_in_progress = True
        start_time = time.time()
        
        try:
            # 1. Identify best secondary
            secondary = self._select_failover_target()
            if not secondary:
                raise NoFailoverTargetError("No healthy secondary available")
            
            # 2. Stop replication (prevent split-brain)
            await self._stop_replication(secondary)
            
            # 3. Verify secondary data integrity
            integrity_ok = await self._verify_integrity(secondary)
            if not integrity_ok:
                # Trigger rebuild from source documents
                await self._initiate_rebuild(secondary)
            
            # 4. Promote secondary to primary
            await self._promote_to_primary(secondary)
            
            # 5. Update DNS / service discovery
            await self._update_routing(secondary)
            
            # 6. Verify traffic is flowing
            await self._verify_traffic(secondary)
            
            rto_actual = time.time() - start_time
            await self._report_failover(secondary, rto_actual)
            
        finally:
            self.failover_in_progress = False
    
    async def _check_primary_health(self) -> bool:
        """Multi-signal health check for primary."""
        primary = self.regions.get(self.current_primary)
        if not primary:
            return False
        
        checks = await asyncio.gather(
            self._ping_vector_db(primary.region),
            self._check_query_latency(primary.region),
            self._check_write_ability(primary.region),
            return_exceptions=True
        )
        
        # All checks must pass
        return all(not isinstance(c, Exception) and c for c in checks)
    
    def _select_failover_target(self) -> Optional[str]:
        """Select secondary with lowest replication lag."""
        candidates = [
            (region, state) for region, state in self.regions.items()
            if state.role == RegionRole.SECONDARY and state.healthy
        ]
        
        if not candidates:
            return None
        
        # Prefer lowest lag
        candidates.sort(key=lambda x: x[1].replication_lag_seconds)
        return candidates[0][0]
    
    async def _promote_to_primary(self, region: str):
        """Promote secondary to primary."""
        state = self.regions[region]
        state.role = RegionRole.PRIMARY
        self.current_primary = region
        # Enable writes on the new primary
        # Configure new secondaries to replicate from here
    
    async def full_rebuild(self, region: str, source_documents_bucket: str):
        """Full rebuild: re-embed all documents from source."""
        self.regions[region].role = RegionRole.REBUILDING
        
        # Scan source documents
        doc_count = await self._count_documents(source_documents_bucket)
        
        # Estimate rebuild time: 100K embeddings/hour
        estimated_hours = doc_count / 100_000
        print(f"Rebuild estimated time: {estimated_hours:.1f} hours for {doc_count} docs")
        
        # Process in parallel batches
        batch_size = 1000
        workers = 20  # Parallel embedding workers
        
        semaphore = asyncio.Semaphore(workers)
        
        async def process_batch(batch_docs):
            async with semaphore:
                embeddings = await self._embed_batch(batch_docs)
                await self._insert_batch(region, batch_docs, embeddings)
        
        # Stream documents and process
        tasks = []
        async for batch in self._stream_documents(source_documents_bucket, batch_size):
            task = asyncio.create_task(process_batch(batch))
            tasks.append(task)
            
            if len(tasks) >= workers * 2:
                await asyncio.gather(*tasks[:workers])
                tasks = tasks[workers:]
        
        await asyncio.gather(*tasks)
        self.regions[region].role = RegionRole.SECONDARY

    # Placeholder methods
    async def _stop_replication(self, region): pass
    async def _verify_integrity(self, region) -> bool: return True
    async def _initiate_rebuild(self, region): pass
    async def _update_routing(self, region): pass
    async def _verify_traffic(self, region): pass
    async def _report_failover(self, region, rto): pass
    async def _ping_vector_db(self, region) -> bool: return True
    async def _check_query_latency(self, region) -> bool: return True
    async def _check_write_ability(self, region) -> bool: return True
    async def _count_documents(self, bucket) -> int: return 500_000_000
    async def _embed_batch(self, docs): pass
    async def _insert_batch(self, region, docs, embeddings): pass
    async def _stream_documents(self, bucket, batch_size): yield []
```

### Recovery Time Analysis

| Recovery Strategy | RPO | RTO | Cost | Complexity |
|------------------|-----|-----|------|------------|
| Hot standby (async replication) | 15 min | 5 min | 2x storage | Medium |
| Warm (periodic snapshot + replay) | 1 hour | 30 min | 1.5x | Medium |
| Cold (re-embed from source) | 0 (lossless) | 24-72 hours | 1x | Low |
| Multi-primary (sync replication) | 0 | <1 min | 3x storage, higher latency | Very High |

### Production Considerations

- **Split-brain prevention**: Use distributed lock (etcd/ZooKeeper) for primary election. Only one region can be primary at a time.
- **Data validation post-failover**: After failover, run recall@10 evaluation against golden queries. Verify quality hasn't degraded.
- **Source document backup**: Even if vectors are lost, as long as source documents exist in object store, you can rebuild. Never lose source documents.
- **Regular DR drills**: Monthly failover drills to secondary. Verify RTO is achievable. Many teams discover their DR plan doesn't work during an actual incident.
- **Cost optimization**: If secondary is read-only standby, use cheaper instance types. Only scale up on promotion.

---

## Q95: Capacity planning framework for AI infrastructure

### Problem
GPU procurement lead time is 3-6 months. Traffic patterns for AI are unpredictable (viral features, new model launches). Design a capacity planning framework that forecasts needs accurately.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              AI Capacity Planning Framework                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Data Collection Layer                                       │  │
│  │                                                              │  │
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐   │  │
│  │  │ Usage       │ │ Business     │ │ Infrastructure    │   │  │
│  │  │ Metrics     │ │ Signals      │ │ Metrics           │   │  │
│  │  │ - Requests  │ │ - New teams  │ │ - GPU utilization │   │  │
│  │  │ - Tokens    │ │ - Roadmap    │ │ - Memory usage    │   │  │
│  │  │ - Models    │ │ - Seasonality│ │ - Queue depth     │   │  │
│  │  │ - Users     │ │ - Contracts  │ │ - Scaling events  │   │  │
│  │  └─────────────┘ └──────────────┘ └───────────────────┘   │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │ Forecasting Engine                                          │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────┐    │  │
│  │  │ Model 1: Time-series (Prophet/ARIMA)                │    │  │
│  │  │ Model 2: Business-driven (team growth × per-team)   │    │  │
│  │  │ Model 3: Scenario planning (optimistic/pessimistic) │    │  │
│  │  │ Ensemble: Weighted average + confidence intervals    │    │  │
│  │  └────────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │ Decision Engine                                             │  │
│  │  - Convert token demand → GPU hours → GPU count             │  │
│  │  - Account for redundancy, burst, maintenance               │  │
│  │  - Generate procurement recommendations                     │  │
│  │  - Model-specific GPU allocation (H100 vs A100)             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta

@dataclass
class CapacityMetrics:
    date: datetime
    total_requests: int
    total_tokens_processed: int
    unique_users: int
    gpu_hours_consumed: float
    peak_concurrent_gpus: int
    models_served: int
    avg_utilization: float

@dataclass
class GPUSpec:
    gpu_type: str           # "H100", "A100"
    memory_gb: int
    tokens_per_second: int  # For primary model
    cost_per_hour: float
    procurement_lead_weeks: int

GPU_SPECS = {
    "H100": GPUSpec("H100", 80, 3000, 4.0, 16),
    "A100": GPUSpec("A100", 80, 1500, 2.5, 12),
    "A10G": GPUSpec("A10G", 24, 500, 1.0, 4),
}

@dataclass
class CapacityForecast:
    date: datetime
    predicted_tokens_per_day: float
    confidence_lower: float   # 10th percentile
    confidence_upper: float   # 90th percentile
    gpu_hours_needed: float
    gpus_needed: int
    cost_per_day: float

class CapacityPlanner:
    """Forecasts GPU needs for AI workloads."""
    
    def __init__(self, history: List[CapacityMetrics]):
        self.history = history
        self.growth_factors = {}
    
    def forecast(self, horizon_days: int = 180) -> List[CapacityForecast]:
        """Generate capacity forecast for next N days."""
        forecasts = []
        
        # Extract trends from history
        daily_tokens = [m.total_tokens_processed for m in self.history]
        daily_growth_rate = self._compute_growth_rate(daily_tokens)
        
        # Seasonal pattern (weekly cycle)
        weekly_pattern = self._extract_weekly_pattern(daily_tokens)
        
        # Business multipliers (planned launches, team onboarding)
        business_multipliers = self._get_business_multipliers(horizon_days)
        
        current_tokens = daily_tokens[-1]
        
        for day in range(1, horizon_days + 1):
            # Base projection: exponential growth
            projected_tokens = current_tokens * (1 + daily_growth_rate) ** day
            
            # Apply seasonality
            day_of_week = (datetime.now() + timedelta(days=day)).weekday()
            projected_tokens *= weekly_pattern[day_of_week]
            
            # Apply business multipliers
            if day in business_multipliers:
                projected_tokens *= business_multipliers[day]
            
            # Confidence intervals (wider as we go further out)
            uncertainty = 0.1 + (day / horizon_days) * 0.4  # 10-50% uncertainty
            lower = projected_tokens * (1 - uncertainty)
            upper = projected_tokens * (1 + uncertainty)
            
            # Convert tokens → GPU hours
            gpu_hours = self._tokens_to_gpu_hours(projected_tokens)
            
            # Convert to GPU count (with headroom)
            gpus_needed = self._gpu_hours_to_count(gpu_hours, day)
            
            # Cost
            cost = gpus_needed * GPU_SPECS["H100"].cost_per_hour * 24
            
            forecasts.append(CapacityForecast(
                date=datetime.now() + timedelta(days=day),
                predicted_tokens_per_day=projected_tokens,
                confidence_lower=lower,
                confidence_upper=upper,
                gpu_hours_needed=gpu_hours,
                gpus_needed=gpus_needed,
                cost_per_day=cost
            ))
        
        return forecasts
    
    def _compute_growth_rate(self, values: List[float]) -> float:
        """Compute daily compound growth rate."""
        if len(values) < 30:
            return 0.02  # Default 2%/day for new services
        
        # Use last 30 days
        recent = values[-30:]
        # Geometric mean of daily changes
        daily_changes = [recent[i]/recent[i-1] for i in range(1, len(recent)) if recent[i-1] > 0]
        if daily_changes:
            avg_growth = np.exp(np.mean(np.log(daily_changes))) - 1
            # Cap at reasonable bounds
            return max(-0.05, min(0.10, avg_growth))
        return 0.01
    
    def _extract_weekly_pattern(self, values: List[float]) -> Dict[int, float]:
        """Extract day-of-week multipliers."""
        if len(values) < 14:
            return {i: 1.0 for i in range(7)}
        
        # Average by day of week (last 4 weeks)
        recent = values[-28:]
        by_dow = {i: [] for i in range(7)}
        start_dow = (datetime.now() - timedelta(days=28)).weekday()
        
        for i, val in enumerate(recent):
            dow = (start_dow + i) % 7
            by_dow[dow].append(val)
        
        overall_avg = np.mean(recent)
        return {dow: np.mean(vals) / overall_avg for dow, vals in by_dow.items()}
    
    def _get_business_multipliers(self, horizon_days: int) -> Dict[int, float]:
        """Known upcoming events that will change demand."""
        multipliers = {}
        # Example: new product launch at day 30 → 1.5x spike
        # Enterprise customer onboarding at day 60 → +20%
        # These come from business planning inputs
        multipliers[30] = 1.5
        multipliers[60] = 1.2
        return multipliers
    
    def _tokens_to_gpu_hours(self, tokens_per_day: float) -> float:
        """Convert token demand to GPU hours needed."""
        # Assume mix of inference workloads
        # H100 can process ~3000 tokens/second for LLM inference
        tokens_per_gpu_hour = GPU_SPECS["H100"].tokens_per_second * 3600
        # Account for batch efficiency (not 100% utilized)
        efficiency = 0.7  # 70% average GPU utilization target
        return tokens_per_day / (tokens_per_gpu_hour * efficiency)
    
    def _gpu_hours_to_count(self, gpu_hours_per_day: float, 
                             forecast_day: int) -> int:
        """Convert GPU hours to GPU count with headroom."""
        # Base GPUs needed if running 24/7
        base_gpus = gpu_hours_per_day / 24
        
        # Add headroom factors
        peak_multiplier = 1.5      # Peak is 1.5x average
        redundancy = 1.2           # 20% redundancy for failures
        maintenance = 1.1          # 10% offline for maintenance
        burst_buffer = 1.15        # 15% for unexpected spikes
        
        total_gpus = base_gpus * peak_multiplier * redundancy * maintenance * burst_buffer
        
        return int(np.ceil(total_gpus))
    
    def generate_procurement_plan(self, forecasts: List[CapacityForecast]) -> List[dict]:
        """Generate when-to-buy recommendations."""
        current_gpus = 64  # Current fleet size
        plans = []
        
        for forecast in forecasts:
            if forecast.gpus_needed > current_gpus:
                gap = forecast.gpus_needed - current_gpus
                # Account for procurement lead time
                lead_time_days = GPU_SPECS["H100"].procurement_lead_weeks * 7
                order_by = forecast.date - timedelta(days=lead_time_days)
                
                if order_by <= datetime.now() + timedelta(days=14):
                    plans.append({
                        "action": "ORDER NOW",
                        "quantity": gap,
                        "gpu_type": "H100",
                        "needed_by": forecast.date.isoformat(),
                        "reason": f"Forecasted need: {forecast.gpus_needed} GPUs, have {current_gpus}",
                        "cost_monthly": gap * GPU_SPECS["H100"].cost_per_hour * 24 * 30,
                        "confidence": "high" if gap > 10 else "medium"
                    })
                    current_gpus += gap  # Assume ordered
        
        return plans
    
    def sensitivity_analysis(self) -> dict:
        """What-if scenarios for capacity planning."""
        scenarios = {}
        
        # Optimistic: growth slows to 1%/day
        # Pessimistic: growth accelerates to 5%/day
        # Black swan: viral event, 10x spike
        
        for scenario, growth_override in [
            ("optimistic", 0.01),
            ("base", None),
            ("pessimistic", 0.05),
            ("black_swan", 0.5)  # 50% jump
        ]:
            # Re-run forecast with modified growth
            forecasts = self.forecast(horizon_days=180)
            peak_gpus = max(f.gpus_needed for f in forecasts)
            total_cost = sum(f.cost_per_day for f in forecasts)
            
            scenarios[scenario] = {
                "peak_gpus": peak_gpus,
                "total_cost_6mo": total_cost,
                "action": "Order now" if peak_gpus > 100 else "Monitor"
            }
        
        return scenarios
```

### Capacity Planning Dashboard

| Timeframe | Metric | Current | 3-Month Forecast | 6-Month Forecast |
|-----------|--------|---------|-----------------|-----------------|
| GPU Count | H100s | 64 | 96 (±15) | 140 (±30) |
| Token Demand | B tokens/day | 2.1B | 4.5B | 9.8B |
| Cost | $/month | $180K | $280K | $420K |
| Utilization | Average | 72% | 75% (target) | 75% (target) |
| Headroom | Burst capacity | 40% | 30% | 25% |

### Production Considerations

- **Model changes dominate planning**: A new model (bigger context, more tokens per request) can 2x demand overnight. Capacity planning must include model roadmap.
- **Efficiency improvements offset growth**: Quantization (2x), batching (3x), caching (30% reduction). Factor these into forecasts.
- **Cloud vs reserved**: Use on-demand for burst (expensive but available). Reserved instances for base load (3-year commitment = 60% savings).
- **Multi-GPU planning**: Different workloads need different GPUs. Training needs H100 clusters. Inference can use A100/A10G. Plan each separately.
- **Monthly review cadence**: Update forecasts monthly. Compare actual vs predicted. Recalibrate model if error > 20%.
# Cost Optimization for AI at Scale (Questions 96-100)

## Q96: Comprehensive cost optimization strategy to reduce $2M/month by 50%

### Problem
Your AI platform costs $2M/month: GPU inference ($1.2M), API calls ($400K), storage ($200K), networking ($200K). Design a strategy to cut to $1M/month without degrading user experience.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Cost Optimization Strategy                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Current: $2M/month                                               │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Layer 1: Model Optimization (-$400K)                         │ │
│  │  - Replace GPT-4 with fine-tuned 7B for 60% of queries      │ │
│  │  - Quantize self-hosted models (INT8: 2x throughput)         │ │
│  │  - Shorter prompts (prompt engineering: -30% tokens)         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Layer 2: Caching & Deduplication (-$300K)                    │ │
│  │  - Semantic cache: 35% hit rate = 35% fewer LLM calls        │ │
│  │  - Embedding cache: avoid re-computing same texts            │ │
│  │  - Response deduplication across concurrent requests          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Layer 3: Infrastructure (-$200K)                             │ │
│  │  - Spot instances for batch workloads (70% savings)          │ │
│  │  - Right-size GPU instances                                  │ │
│  │  - Reserved capacity for baseline (60% discount)             │ │
│  │  - Auto-scale to zero during off-hours                       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Layer 4: Architecture (-$100K)                               │ │
│  │  - Batch similar requests (higher GPU utilization)           │ │
│  │  - Tiered storage (hot/warm/cold for vectors)                │ │
│  │  - Compress embeddings (PQ: 32x size reduction)              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Target: $1M/month (50% reduction)                                │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

@dataclass
class CostBreakdown:
    category: str
    monthly_cost: float
    optimization: str
    savings_percent: float
    implementation_effort: str  # "low", "medium", "high"
    risk: str                  # Impact on quality

class CostOptimizer:
    """Systematic cost reduction for AI platforms."""
    
    def __init__(self, current_costs: Dict[str, float]):
        self.costs = current_costs
        self.optimizations: List[CostBreakdown] = []
    
    def analyze_and_recommend(self) -> List[CostBreakdown]:
        """Generate prioritized optimization recommendations."""
        
        # === MODEL OPTIMIZATION ===
        self.optimizations.append(CostBreakdown(
            category="LLM API Calls",
            monthly_cost=400_000,
            optimization="Route 60% of queries to fine-tuned 7B model",
            savings_percent=50,  # 60% of traffic at 1/20th the cost
            implementation_effort="high",
            risk="Medium - requires quality monitoring"
        ))
        
        self.optimizations.append(CostBreakdown(
            category="LLM API Calls",
            monthly_cost=400_000,
            optimization="Prompt compression: remove redundant instructions, use shorter system prompts",
            savings_percent=20,
            implementation_effort="low",
            risk="Low - measure output quality"
        ))
        
        # === CACHING ===
        self.optimizations.append(CostBreakdown(
            category="GPU Inference",
            monthly_cost=1_200_000,
            optimization="Semantic cache with 35% hit rate",
            savings_percent=35,
            implementation_effort="medium",
            risk="Low - cache responses are pre-validated"
        ))
        
        # === INFRASTRUCTURE ===
        self.optimizations.append(CostBreakdown(
            category="GPU Inference",
            monthly_cost=1_200_000,
            optimization="Spot instances for batch/async workloads (40% of compute)",
            savings_percent=28,  # 40% of workload × 70% spot discount
            implementation_effort="medium",
            risk="Low - batch workloads tolerate interruption"
        ))
        
        self.optimizations.append(CostBreakdown(
            category="GPU Inference",
            monthly_cost=1_200_000,
            optimization="Reserved instances for base load (50% of compute)",
            savings_percent=30,  # 50% of workload × 60% reserved discount
            implementation_effort="low",
            risk="Low - committed use discount"
        ))
        
        # === STORAGE ===
        self.optimizations.append(CostBreakdown(
            category="Vector Storage",
            monthly_cost=200_000,
            optimization="Product quantization (768-dim → 64 bytes), tiered storage",
            savings_percent=70,
            implementation_effort="medium",
            risk="Low - <2% recall drop with proper quantization"
        ))
        
        # Prioritize by ROI (savings / effort)
        effort_scores = {"low": 1, "medium": 2, "high": 3}
        self.optimizations.sort(
            key=lambda o: o.monthly_cost * o.savings_percent / 100 / effort_scores[o.implementation_effort],
            reverse=True
        )
        
        return self.optimizations
    
    def project_savings(self) -> dict:
        """Project total savings with implementation timeline."""
        total_savings = 0
        timeline = []
        
        # Phase 1 (Week 1-2): Low effort
        phase1 = [o for o in self.optimizations if o.implementation_effort == "low"]
        phase1_savings = sum(o.monthly_cost * o.savings_percent / 100 for o in phase1)
        
        # Phase 2 (Week 3-6): Medium effort
        phase2 = [o for o in self.optimizations if o.implementation_effort == "medium"]
        phase2_savings = sum(o.monthly_cost * o.savings_percent / 100 for o in phase2)
        
        # Phase 3 (Week 7-12): High effort
        phase3 = [o for o in self.optimizations if o.implementation_effort == "high"]
        phase3_savings = sum(o.monthly_cost * o.savings_percent / 100 for o in phase3)
        
        return {
            "phase1_savings_monthly": phase1_savings,
            "phase2_savings_monthly": phase2_savings,
            "phase3_savings_monthly": phase3_savings,
            "total_potential_savings": phase1_savings + phase2_savings + phase3_savings,
            "note": "Some optimizations overlap - actual savings ~50% of sum"
        }


class PromptCompressor:
    """Reduce token costs by compressing prompts."""
    
    def compress(self, system_prompt: str, user_prompt: str) -> Tuple[str, str]:
        """Compress prompts while preserving semantics."""
        # Strategy 1: Remove verbose instructions
        system_prompt = self._remove_redundancy(system_prompt)
        
        # Strategy 2: Use abbreviations for common patterns
        system_prompt = self._abbreviate(system_prompt)
        
        # Strategy 3: Context window management - only include relevant context
        user_prompt = self._trim_context(user_prompt, max_context_tokens=2000)
        
        return system_prompt, user_prompt
    
    def _remove_redundancy(self, prompt: str) -> str:
        """Remove repeated instructions and verbose phrasing."""
        # "Please make sure to always..." → "Always..."
        # Remove example repetition
        lines = prompt.split('\n')
        seen_instructions = set()
        filtered = []
        for line in lines:
            normalized = line.strip().lower()
            if normalized not in seen_instructions:
                seen_instructions.add(normalized)
                filtered.append(line)
        return '\n'.join(filtered)
    
    def _abbreviate(self, prompt: str) -> str:
        """Use shorter phrasing."""
        replacements = {
            "Please ensure that you": "",
            "Make sure to always": "Always",
            "It is important that": "",
            "You should respond with": "Respond with",
        }
        for old, new in replacements.items():
            prompt = prompt.replace(old, new)
        return prompt
    
    def _trim_context(self, prompt: str, max_context_tokens: int) -> str:
        """Keep only most relevant context within budget."""
        # Estimated: 1 token ≈ 4 chars
        max_chars = max_context_tokens * 4
        if len(prompt) > max_chars:
            # Keep beginning and end (most important parts)
            half = max_chars // 2
            return prompt[:half] + "\n...[trimmed]...\n" + prompt[-half:]
        return prompt


class InferenceCoalescer:
    """Combine similar concurrent requests to reduce total compute."""
    
    def __init__(self):
        self.pending_requests: Dict[str, list] = {}
    
    async def coalesce_or_compute(self, request_key: str, compute_fn, *args) -> any:
        """If same computation is in-flight, wait for it instead of duplicating."""
        if request_key in self.pending_requests:
            # Someone else is computing this - wait for their result
            future = asyncio.get_event_loop().create_future()
            self.pending_requests[request_key].append(future)
            return await future
        
        # First request - compute it
        self.pending_requests[request_key] = []
        
        try:
            result = await compute_fn(*args)
            # Distribute result to all waiters
            for future in self.pending_requests[request_key]:
                if not future.done():
                    future.set_result(result)
            return result
        finally:
            del self.pending_requests[request_key]
```

### Savings Waterfall

| Optimization | Monthly Savings | Cumulative | Effort | Timeline |
|-------------|----------------|------------|--------|----------|
| Prompt compression (-30% tokens) | $120K | $120K | Low | Week 1 |
| Reserved instances (base load) | $180K | $300K | Low | Week 2 |
| Semantic caching (35% hit) | $250K | $550K | Medium | Week 4 |
| Vector quantization + tiering | $140K | $690K | Medium | Week 6 |
| Spot instances (batch) | $170K | $860K | Medium | Week 8 |
| Model tiering (7B for simple) | $200K | $1,060K | High | Week 12 |

### Production Considerations

- **Quality gates**: Every optimization must pass quality evaluation before full rollout. A/B test each change.
- **Monitoring**: Cost per query, cost per user, cost per feature. Track daily and alert on anomalies.
- **Avoid false economies**: Caching stale data saves money but hurts user trust. Quantization that drops recall below threshold costs more in user churn.
- **Team incentives**: Give teams visibility into their AI costs. Teams that optimize get more budget for new features.
- **Diminishing returns**: First 30% savings is easy. Next 20% is hard. Last 10% might not be worth the engineering effort.

---

## Q97: Cost attribution and chargeback for shared AI platform

### Problem
50 teams share your AI platform. Finance needs to attribute costs per team. Teams need visibility to optimize. Design a system that accurately tracks per-team AI consumption and enables fair chargeback.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Cost Attribution & Chargeback System                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Metering Layer (captures every AI operation)                │  │
│  │                                                              │  │
│  │  Every API call records:                                    │  │
│  │  {team_id, model, input_tokens, output_tokens,              │  │
│  │   embeddings_count, vector_queries, storage_bytes,          │  │
│  │   gpu_seconds, timestamp}                                   │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │ Cost Allocation Engine                                      │  │
│  │                                                              │  │
│  │  Direct costs (70%):                                        │  │
│  │  - LLM tokens → per-team token usage × price/token          │  │
│  │  - Embeddings → per-team embedding count × price            │  │
│  │  - Storage → per-team vector count × price/vector           │  │
│  │                                                              │  │
│  │  Shared costs (30%):                                        │  │
│  │  - Platform infra → proportional to team's usage share      │  │
│  │  - Networking → proportional to request volume              │  │
│  │  - Support/ops → flat allocation per team                   │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────▼──────────────────────────────┐  │
│  │ Reporting & Dashboards                                      │  │
│  │  - Real-time cost per team                                  │  │
│  │  - Cost per feature/endpoint                                │  │
│  │  - Budget alerts & forecasts                                │  │
│  │  - Optimization recommendations per team                    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime, timedelta

@dataclass
class UsageEvent:
    """Single metered AI operation."""
    event_id: str
    team_id: str
    user_id: str
    operation: str        # "llm_completion", "embedding", "vector_search", "storage"
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    embedding_count: int = 0
    vector_queries: int = 0
    storage_bytes_delta: int = 0
    gpu_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

@dataclass
class PricingConfig:
    """Unit prices for each billable dimension."""
    # Token pricing (per 1K tokens)
    llm_input_per_1k: Dict[str, float] = field(default_factory=lambda: {
        "gpt-4": 0.03,
        "gpt-3.5-turbo": 0.001,
        "claude-3-opus": 0.015,
        "llama-70b-self-hosted": 0.005,
        "llama-7b-self-hosted": 0.0005,
    })
    llm_output_per_1k: Dict[str, float] = field(default_factory=lambda: {
        "gpt-4": 0.06,
        "gpt-3.5-turbo": 0.002,
        "claude-3-opus": 0.075,
        "llama-70b-self-hosted": 0.015,
        "llama-7b-self-hosted": 0.001,
    })
    embedding_per_1k: float = 0.0001        # Per 1K embeddings
    vector_query_price: float = 0.00001      # Per query
    storage_per_gb_month: float = 0.25       # Per GB per month
    gpu_second_price: float = 0.001          # Per GPU-second (self-hosted)
    
    # Shared infrastructure overhead multiplier
    overhead_multiplier: float = 1.3  # 30% overhead for shared infra

class CostAttributionEngine:
    """Calculates per-team costs from usage events."""
    
    def __init__(self, pricing: PricingConfig):
        self.pricing = pricing
        self.usage_store: Dict[str, List[UsageEvent]] = defaultdict(list)
    
    def record_usage(self, event: UsageEvent):
        """Record a usage event for attribution."""
        self.usage_store[event.team_id].append(event)
    
    def calculate_team_cost(self, team_id: str, 
                            start_date: datetime, end_date: datetime) -> dict:
        """Calculate total cost for a team in a time period."""
        events = [
            e for e in self.usage_store[team_id]
            if start_date.timestamp() <= e.timestamp <= end_date.timestamp()
        ]
        
        cost_breakdown = {
            "llm_input": 0.0,
            "llm_output": 0.0,
            "embeddings": 0.0,
            "vector_queries": 0.0,
            "storage": 0.0,
            "gpu_compute": 0.0,
        }
        
        for event in events:
            # LLM token costs
            if event.input_tokens > 0:
                rate = self.pricing.llm_input_per_1k.get(event.model, 0.01)
                cost_breakdown["llm_input"] += (event.input_tokens / 1000) * rate
            
            if event.output_tokens > 0:
                rate = self.pricing.llm_output_per_1k.get(event.model, 0.02)
                cost_breakdown["llm_output"] += (event.output_tokens / 1000) * rate
            
            # Embedding costs
            if event.embedding_count > 0:
                cost_breakdown["embeddings"] += (event.embedding_count / 1000) * self.pricing.embedding_per_1k
            
            # Vector query costs
            if event.vector_queries > 0:
                cost_breakdown["vector_queries"] += event.vector_queries * self.pricing.vector_query_price
            
            # GPU compute (self-hosted)
            if event.gpu_seconds > 0:
                cost_breakdown["gpu_compute"] += event.gpu_seconds * self.pricing.gpu_second_price
        
        # Storage (snapshot-based, not event-based)
        storage_gb = self._get_team_storage_gb(team_id)
        days_in_period = (end_date - start_date).days
        cost_breakdown["storage"] = storage_gb * self.pricing.storage_per_gb_month * (days_in_period / 30)
        
        # Apply overhead
        direct_total = sum(cost_breakdown.values())
        overhead = direct_total * (self.pricing.overhead_multiplier - 1)
        
        return {
            "team_id": team_id,
            "period": f"{start_date.date()} to {end_date.date()}",
            "breakdown": cost_breakdown,
            "direct_total": direct_total,
            "shared_overhead": overhead,
            "total_cost": direct_total + overhead,
            "top_cost_drivers": self._get_top_drivers(cost_breakdown)
        }
    
    def _get_top_drivers(self, breakdown: dict) -> List[dict]:
        """Identify top cost drivers for optimization suggestions."""
        sorted_costs = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        return [{"category": k, "cost": v, "percent": v/sum(breakdown.values())*100} 
                for k, v in sorted_costs[:3]]
    
    def _get_team_storage_gb(self, team_id: str) -> float:
        """Get current storage usage for team."""
        return 50.0  # Placeholder
    
    def generate_invoice(self, team_id: str, month: datetime) -> dict:
        """Generate monthly invoice for a team."""
        start = month.replace(day=1)
        if month.month == 12:
            end = month.replace(year=month.year+1, month=1, day=1)
        else:
            end = month.replace(month=month.month+1, day=1)
        
        costs = self.calculate_team_cost(team_id, start, end)
        
        # Add optimization recommendations
        recommendations = self._generate_recommendations(team_id, costs)
        
        return {
            **costs,
            "recommendations": recommendations,
            "budget_status": self._check_budget(team_id, costs["total_cost"]),
        }
    
    def _generate_recommendations(self, team_id: str, costs: dict) -> List[str]:
        """Auto-generate cost optimization tips per team."""
        recs = []
        breakdown = costs["breakdown"]
        
        if breakdown["llm_input"] > 1000:
            recs.append("Consider prompt compression - your input token costs are high. "
                       "Review system prompts for redundancy.")
        
        if breakdown["llm_output"] > breakdown["llm_input"] * 3:
            recs.append("Output tokens dominate costs. Consider setting lower max_tokens "
                       "or using streaming with early stopping.")
        
        if breakdown["embeddings"] > 500:
            recs.append("High embedding volume detected. Enable embedding caching "
                       "to avoid recomputing identical texts.")
        
        return recs
    
    def _check_budget(self, team_id: str, current_cost: float) -> dict:
        """Check team against their budget."""
        budget = 50_000  # Example: $50K/month budget per team
        utilization = current_cost / budget
        
        return {
            "budget": budget,
            "spent": current_cost,
            "utilization_percent": utilization * 100,
            "alert": "OVER_BUDGET" if utilization > 1.0 else 
                     "WARNING" if utilization > 0.8 else "OK",
            "projected_month_end": current_cost * 30 / max(1, datetime.now().day)
        }


class UsageMeteringMiddleware:
    """Middleware that captures usage for every AI API call."""
    
    def __init__(self, attribution_engine: CostAttributionEngine):
        self.engine = attribution_engine
    
    async def meter_request(self, request, response, team_id: str):
        """Record usage after every AI request."""
        event = UsageEvent(
            event_id=f"evt_{int(time.time()*1000)}",
            team_id=team_id,
            user_id=request.get("user_id", "unknown"),
            operation="llm_completion",
            model=request.get("model", "unknown"),
            input_tokens=response.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=response.get("usage", {}).get("completion_tokens", 0),
            metadata={"endpoint": request.get("endpoint"), "feature": request.get("feature")}
        )
        self.engine.record_usage(event)
```

### Chargeback Model Comparison

| Model | Fairness | Simplicity | Incentivizes Optimization | Admin Overhead |
|-------|----------|-----------|--------------------------|----------------|
| Equal split (50 teams) | Poor | High | None | Low |
| Per-request flat fee | Medium | High | Reduces volume, not efficiency | Low |
| Token-based (this) | High | Medium | Yes - all dimensions | Medium |
| Full cost allocation | Highest | Low | Maximum | High |

### Production Considerations

- **Real-time visibility**: Teams should see costs in real-time, not monthly surprises. Dashboard with daily/hourly granularity.
- **Budget alerts**: Alert at 50%, 80%, 100% of monthly budget. Auto-throttle at 120% unless exempted.
- **Showback before chargeback**: Start with visibility (showback) for 3 months before enforcing chargeback. Let teams adjust.
- **Fair shared costs**: Platform team costs (SRE, ML ops) must be allocated fairly. Use proportional-to-usage, not equal split.
- **Gaming prevention**: Teams shouldn't be able to game the system (e.g., running requests under another team's API key). Audit trail + anomaly detection.

---

## Q98: Spot instance strategy for AI training and batch inference

### Problem
Training jobs cost $500K/month on on-demand GPUs. Batch inference (nightly evaluations, embeddings reprocessing) costs another $200K. Spot instances offer 60-70% savings but can be interrupted. Design a resilient strategy.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Spot Instance Strategy for AI Workloads               │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Workload Classification                                     │  │
│  │                                                              │  │
│  │  ┌─────────────┐  ┌─────────────────┐  ┌──────────────┐  │  │
│  │  │ Spot-Ready  │  │ Spot-Tolerant   │  │ On-Demand    │  │  │
│  │  │             │  │                  │  │ Only         │  │  │
│  │  │ - Batch     │  │ - Training with  │  │              │  │  │
│  │  │   embeddings│  │   checkpoints    │  │ - Real-time  │  │  │
│  │  │ - Evals     │  │ - Fine-tuning    │  │   inference  │  │  │
│  │  │ - Offline   │  │ - Large-batch    │  │ - SLA-bound  │  │  │
│  │  │   reranking │  │   inference      │  │   workloads  │  │  │
│  │  │             │  │                  │  │              │  │  │
│  │  │ Savings:70% │  │ Savings: 60%     │  │ Savings: 0%  │  │  │
│  │  └─────────────┘  └─────────────────┘  └──────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Spot Management Layer                                       │  │
│  │                                                              │  │
│  │  - Multi-AZ, multi-instance-type fleet                      │  │
│  │  - 2-minute interruption handling                           │  │
│  │  - Automatic checkpointing (every 10 min)                   │  │
│  │  - Fallback to on-demand for deadline-critical jobs         │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum

class SpotStrategy(Enum):
    SPOT_ONLY = "spot_only"           # Pure spot, retry on interruption
    SPOT_WITH_FALLBACK = "spot_fallback"  # Spot + on-demand fallback
    DIVERSIFIED = "diversified"       # Mix of spot pools

@dataclass
class SpotConfig:
    max_spot_price_multiplier: float = 0.7  # Max 70% of on-demand
    checkpoint_interval_seconds: int = 600   # Every 10 minutes
    interruption_buffer_seconds: int = 120   # 2 min warning
    instance_types: List[str] = field(default_factory=lambda: [
        "p4d.24xlarge",   # 8x A100
        "p3.16xlarge",    # 8x V100
        "g5.48xlarge",    # 8x A10G
    ])
    availability_zones: List[str] = field(default_factory=lambda: [
        "us-east-1a", "us-east-1b", "us-east-1c",
        "us-west-2a", "us-west-2b"
    ])
    max_retries: int = 3
    deadline_hours: Optional[float] = None  # If set, fallback to on-demand if deadline at risk

class SpotInstanceManager:
    """Manages spot instances for AI workloads with interruption handling."""
    
    def __init__(self, config: SpotConfig):
        self.config = config
        self.active_instances: Dict[str, dict] = {}
        self.interruption_handlers: Dict[str, callable] = {}
    
    async def launch_training_job(self, job_config: dict) -> str:
        """Launch training job on spot with checkpoint/resume."""
        job_id = f"job_{int(time.time())}"
        
        # Try to get spot capacity across multiple pools
        instance = await self._acquire_spot_capacity(job_config)
        
        if not instance:
            if self.config.deadline_hours:
                # Deadline at risk, use on-demand
                instance = await self._launch_on_demand(job_config)
            else:
                raise NoCapacityError("No spot capacity available")
        
        # Register interruption handler
        self.interruption_handlers[job_id] = lambda: self._handle_interruption(job_id)
        
        # Start job with automatic checkpointing
        await self._start_job_with_checkpointing(job_id, instance, job_config)
        
        return job_id
    
    async def _acquire_spot_capacity(self, job_config: dict) -> Optional[dict]:
        """Try to acquire spot capacity from diversified pools."""
        # Strategy: try multiple instance types and AZs
        for instance_type in self.config.instance_types:
            for az in self.config.availability_zones:
                try:
                    instance = await self._request_spot(
                        instance_type=instance_type,
                        az=az,
                        max_price=self._get_max_price(instance_type)
                    )
                    return instance
                except SpotCapacityError:
                    continue
        return None
    
    async def _handle_interruption(self, job_id: str):
        """Handle spot interruption with 2-minute warning."""
        print(f"Spot interruption for {job_id} - saving checkpoint")
        
        # 1. Save checkpoint immediately
        await self._save_checkpoint(job_id)
        
        # 2. Try to acquire new spot instance
        new_instance = await self._acquire_spot_capacity(
            self.active_instances[job_id]["config"]
        )
        
        if new_instance:
            # 3. Resume from checkpoint on new instance
            await self._resume_from_checkpoint(job_id, new_instance)
        else:
            # 4. Fallback to on-demand if deadline at risk
            elapsed = time.time() - self.active_instances[job_id]["start_time"]
            estimated_remaining = self.active_instances[job_id].get("estimated_remaining", float('inf'))
            
            if self.config.deadline_hours:
                deadline = self.config.deadline_hours * 3600
                if elapsed + estimated_remaining > deadline * 0.8:
                    # Launch on-demand to meet deadline
                    od_instance = await self._launch_on_demand(
                        self.active_instances[job_id]["config"]
                    )
                    await self._resume_from_checkpoint(job_id, od_instance)
                    return
            
            # Queue for retry when spot becomes available
            await self._queue_for_retry(job_id)
    
    async def _save_checkpoint(self, job_id: str):
        """Save model checkpoint to durable storage (S3)."""
        # Must complete within 2-minute interruption window
        # Typical checkpoint: 14GB for 7B model = ~20s on fast network
        pass
    
    async def _resume_from_checkpoint(self, job_id: str, instance: dict):
        """Resume training from last checkpoint."""
        # Load checkpoint, restore optimizer state, continue training
        pass
    
    def _get_max_price(self, instance_type: str) -> float:
        """Max bid = 70% of on-demand price."""
        on_demand_prices = {
            "p4d.24xlarge": 32.77,
            "p3.16xlarge": 24.48,
            "g5.48xlarge": 16.29,
        }
        return on_demand_prices.get(instance_type, 20.0) * self.config.max_spot_price_multiplier
    
    async def _request_spot(self, instance_type, az, max_price): pass
    async def _launch_on_demand(self, config): pass
    async def _start_job_with_checkpointing(self, job_id, instance, config): pass
    async def _queue_for_retry(self, job_id): pass


class BatchInferenceSpotRunner:
    """Run batch inference workloads on spot with automatic splitting."""
    
    def __init__(self, spot_manager: SpotInstanceManager):
        self.spot_manager = spot_manager
    
    async def run_batch_embedding(self, documents: List[str], 
                                   batch_id: str) -> List[np.ndarray]:
        """Run embedding batch on spot with progress tracking."""
        total = len(documents)
        chunk_size = 10_000  # Process in chunks for checkpoint granularity
        
        results = []
        progress_key = f"batch:{batch_id}:progress"
        
        # Resume from last checkpoint if exists
        completed_chunks = await self._get_progress(progress_key)
        start_chunk = completed_chunks
        
        for i in range(start_chunk, total, chunk_size):
            chunk = documents[i:i + chunk_size]
            
            try:
                chunk_results = await self._process_chunk_on_spot(chunk)
                results.extend(chunk_results)
                
                # Save progress
                await self._save_progress(progress_key, i + chunk_size)
                
            except SpotInterruptionError:
                # Chunk partially processed - retry from chunk start
                # Results for this chunk are lost, but previous chunks are saved
                await asyncio.sleep(30)  # Wait for new capacity
                # Retry this chunk
                chunk_results = await self._process_chunk_on_spot(chunk)
                results.extend(chunk_results)
                await self._save_progress(progress_key, i + chunk_size)
        
        return results
    
    async def _process_chunk_on_spot(self, chunk: List[str]):
        """Process a chunk on spot instance."""
        pass
    
    async def _get_progress(self, key: str) -> int:
        return 0
    
    async def _save_progress(self, key: str, value: int):
        pass


class SpotInterruptionError(Exception):
    pass

class SpotCapacityError(Exception):
    pass

class NoCapacityError(Exception):
    pass
```

### Cost Savings Analysis

| Workload | On-Demand Cost | Spot Cost | Savings | Interruption Impact |
|----------|---------------|-----------|---------|-------------------|
| Model training (7B) | $50K/run | $17K/run | 66% | +10% time from restarts |
| Batch embeddings | $200K/mo | $65K/mo | 68% | +5% time from retries |
| Nightly evaluations | $30K/mo | $10K/mo | 67% | Acceptable delay |
| Fine-tuning | $100K/mo | $40K/mo | 60% | +15% time |
| **Total** | **$380K/mo** | **$132K/mo** | **65%** | |

### Production Considerations

- **Checkpoint storage cost**: Frequent checkpoints consume S3 storage. 7B model × every 10 min × 72 hour training = 6TB. Budget $150/training run for checkpoint storage.
- **Interruption rate varies**: Weekday mornings have more interruptions (on-demand demand spikes). Schedule big jobs for nights/weekends.
- **Diversification is key**: Don't depend on single instance type. Spread across p4d, p3, g5 and multiple AZs. Reduces interruption probability from 15% to <3%.
- **Deadline awareness**: If training must finish by Friday for Monday deployment, factor in worst-case interruption scenarios.
- **Hybrid fleet**: Keep 30% on-demand as base, 70% spot for cost optimization with reliability.

---

## Q99: Token budget management system

### Problem
LLM costs are proportional to tokens consumed. Without controls, costs spiral. Design a system that enforces limits at user, team, and org levels with alerting, throttling, and forecasting.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Token Budget Management System                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Budget Hierarchy                                            │  │
│  │                                                              │  │
│  │  Organization: 100M tokens/month ($50K budget)              │  │
│  │    ├── Team-A: 30M tokens/month                             │  │
│  │    │   ├── User-1: 1M tokens/month                          │  │
│  │    │   ├── User-2: 500K tokens/month                        │  │
│  │    │   └── Service-A: 20M tokens/month                      │  │
│  │    ├── Team-B: 50M tokens/month                             │  │
│  │    └── Team-C: 20M tokens/month                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Enforcement Layer                                           │  │
│  │                                                              │  │
│  │  Rate Limits:                                               │  │
│  │  - Per-user: 10K tokens/minute (burst: 50K)                 │  │
│  │  - Per-team: 100K tokens/minute                             │  │
│  │  - Per-org: 1M tokens/minute                                │  │
│  │                                                              │  │
│  │  Budget Limits:                                             │  │
│  │  - Soft limit (80%): Alert, allow continued use             │  │
│  │  - Hard limit (100%): Throttle to reduced quality           │  │
│  │  - Emergency limit (120%): Block non-critical requests      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Forecasting & Alerting                                      │  │
│  │  - Predict budget exhaustion date                           │  │
│  │  - Alert: "Team-A will exhaust budget in 5 days"            │  │
│  │  - Anomaly detection: "User-3 consumed 10x normal today"    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from enum import Enum
from collections import defaultdict

class BudgetAction(Enum):
    ALLOW = "allow"
    ALLOW_WITH_WARNING = "allow_warning"
    THROTTLE = "throttle"         # Reduce quality (smaller model)
    QUEUE = "queue"               # Delay non-urgent requests
    REJECT = "reject"            # Hard block

@dataclass
class TokenBudget:
    entity_id: str              # user_id, team_id, or org_id
    entity_type: str            # "user", "team", "org"
    monthly_limit: int          # Total tokens allowed per month
    daily_limit: Optional[int]  # Optional daily cap
    burst_limit: int            # Max tokens in a single minute
    consumed_this_month: int = 0
    consumed_today: int = 0
    consumed_this_minute: int = 0
    last_reset_month: int = 0
    last_reset_day: int = 0
    priority: int = 1           # Higher = more important (less likely to throttle)

@dataclass
class BudgetDecision:
    action: BudgetAction
    remaining_monthly: int
    remaining_daily: int
    utilization_percent: float
    message: str
    suggested_max_tokens: Optional[int] = None  # Reduce if throttling

class TokenBudgetManager:
    """Hierarchical token budget enforcement."""
    
    def __init__(self):
        self.budgets: Dict[str, TokenBudget] = {}
        self.usage_history: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
    
    def check_budget(self, user_id: str, team_id: str, org_id: str,
                     estimated_tokens: int) -> BudgetDecision:
        """Check if request is within budget at all hierarchy levels."""
        
        # Check from most specific to least specific
        for entity_id, entity_type in [
            (user_id, "user"), (team_id, "team"), (org_id, "org")
        ]:
            budget = self.budgets.get(entity_id)
            if not budget:
                continue
            
            self._refresh_counters(budget)
            
            # Burst check (per-minute)
            if budget.consumed_this_minute + estimated_tokens > budget.burst_limit:
                return BudgetDecision(
                    action=BudgetAction.QUEUE,
                    remaining_monthly=budget.monthly_limit - budget.consumed_this_month,
                    remaining_daily=budget.daily_limit - budget.consumed_today if budget.daily_limit else 0,
                    utilization_percent=budget.consumed_this_month / budget.monthly_limit * 100,
                    message=f"Rate limit exceeded for {entity_type} {entity_id}. Please wait.",
                    suggested_max_tokens=budget.burst_limit - budget.consumed_this_minute
                )
            
            # Monthly budget check
            utilization = budget.consumed_this_month / budget.monthly_limit
            
            if utilization >= 1.2:
                # Emergency: hard block
                return BudgetDecision(
                    action=BudgetAction.REJECT,
                    remaining_monthly=0,
                    remaining_daily=0,
                    utilization_percent=utilization * 100,
                    message=f"{entity_type} {entity_id} exceeded budget by 20%. Blocked."
                )
            
            elif utilization >= 1.0:
                # Over budget: throttle (use cheaper model)
                return BudgetDecision(
                    action=BudgetAction.THROTTLE,
                    remaining_monthly=0,
                    remaining_daily=0,
                    utilization_percent=utilization * 100,
                    message=f"{entity_type} {entity_id} at budget limit. Degrading to smaller model.",
                    suggested_max_tokens=min(estimated_tokens, 256)  # Cap output
                )
            
            elif utilization >= 0.8:
                # Warning zone
                return BudgetDecision(
                    action=BudgetAction.ALLOW_WITH_WARNING,
                    remaining_monthly=budget.monthly_limit - budget.consumed_this_month,
                    remaining_daily=budget.daily_limit - budget.consumed_today if budget.daily_limit else 0,
                    utilization_percent=utilization * 100,
                    message=f"{entity_type} {entity_id} at {utilization*100:.0f}% of monthly budget."
                )
        
        # All checks passed
        return BudgetDecision(
            action=BudgetAction.ALLOW,
            remaining_monthly=self.budgets.get(user_id, TokenBudget("", "", 0, None, 0)).monthly_limit,
            remaining_daily=0,
            utilization_percent=0,
            message="OK"
        )
    
    def record_usage(self, user_id: str, team_id: str, org_id: str, 
                     tokens_used: int):
        """Record actual token consumption after request completes."""
        for entity_id in [user_id, team_id, org_id]:
            budget = self.budgets.get(entity_id)
            if budget:
                budget.consumed_this_month += tokens_used
                budget.consumed_today += tokens_used
                budget.consumed_this_minute += tokens_used
                self.usage_history[entity_id].append((time.time(), tokens_used))
    
    def _refresh_counters(self, budget: TokenBudget):
        """Reset counters on period boundaries."""
        now = time.localtime()
        if now.tm_mon != budget.last_reset_month:
            budget.consumed_this_month = 0
            budget.last_reset_month = now.tm_mon
        if now.tm_mday != budget.last_reset_day:
            budget.consumed_today = 0
            budget.last_reset_day = now.tm_mday
        # Minute counter decays (sliding window)
        # Simplified: reset every minute
    
    def forecast_exhaustion(self, entity_id: str) -> Optional[dict]:
        """Predict when budget will be exhausted."""
        budget = self.budgets.get(entity_id)
        if not budget:
            return None
        
        history = self.usage_history.get(entity_id, [])
        if len(history) < 10:
            return None
        
        # Calculate daily burn rate (last 7 days)
        week_ago = time.time() - 7 * 86400
        recent = [tokens for ts, tokens in history if ts > week_ago]
        daily_burn = sum(recent) / 7
        
        remaining = budget.monthly_limit - budget.consumed_this_month
        
        if daily_burn > 0:
            days_until_exhaustion = remaining / daily_burn
        else:
            days_until_exhaustion = float('inf')
        
        # Days remaining in month
        import calendar
        now = time.localtime()
        days_in_month = calendar.monthrange(now.tm_year, now.tm_mon)[1]
        days_remaining = days_in_month - now.tm_mday
        
        return {
            "entity_id": entity_id,
            "daily_burn_rate": daily_burn,
            "remaining_tokens": remaining,
            "days_until_exhaustion": days_until_exhaustion,
            "days_remaining_in_month": days_remaining,
            "will_exhaust_before_month_end": days_until_exhaustion < days_remaining,
            "projected_overage": max(0, daily_burn * days_remaining - remaining),
            "recommendation": self._get_recommendation(days_until_exhaustion, days_remaining)
        }
    
    def _get_recommendation(self, days_to_exhaust: float, days_remaining: float) -> str:
        if days_to_exhaust < days_remaining * 0.5:
            return "CRITICAL: Budget will exhaust well before month end. Reduce usage or request increase."
        elif days_to_exhaust < days_remaining:
            return "WARNING: On track to exceed budget. Consider optimization."
        return "OK: Budget is on track."
    
    def detect_anomalies(self, entity_id: str) -> Optional[dict]:
        """Detect unusual consumption patterns."""
        history = self.usage_history.get(entity_id, [])
        if len(history) < 100:
            return None
        
        # Compare last hour vs typical hour
        hour_ago = time.time() - 3600
        last_hour = sum(t for ts, t in history if ts > hour_ago)
        
        # Typical hourly (average of last 7 days)
        week_ago = time.time() - 7 * 86400
        weekly_total = sum(t for ts, t in history if ts > week_ago)
        typical_hourly = weekly_total / (7 * 24)
        
        if typical_hourly > 0 and last_hour > typical_hourly * 5:
            return {
                "entity_id": entity_id,
                "type": "consumption_spike",
                "current_hourly": last_hour,
                "typical_hourly": typical_hourly,
                "multiplier": last_hour / typical_hourly,
                "alert": f"5x normal consumption detected for {entity_id}"
            }
        
        return None
```

### Budget Enforcement Strategy

| Utilization | Action | User Experience | Cost Control |
|-------------|--------|----------------|--------------|
| 0-80% | Allow | Full quality | Monitoring |
| 80-100% | Warn | Full quality + notification | Alerting |
| 100-120% | Throttle | Degraded (smaller model, shorter output) | Soft cap |
| >120% | Block (non-critical) | Partial outage | Hard cap |

### Production Considerations

- **Latency impact**: Budget check must be <1ms. Use in-memory counters synced to Redis. Don't add network hop for every request.
- **Grace periods**: Don't hard-block a user mid-conversation. Allow current session to complete, block next session.
- **Burst accommodation**: Allow 10x burst for 1 minute (important for batch operations). Monthly limit is what matters.
- **Self-service budget increase**: Teams should be able to request temporary budget increases through a workflow (approved within 1 hour).
- **Token estimation accuracy**: Pre-request token estimation is imperfect. Track actual vs estimated and calibrate. Over-estimation leads to premature blocking.

---

## Q100: TCO comparison: Self-hosted vs API providers with hybrid strategy

### Problem
At your scale (50M tokens/day), should you self-host open-source LLMs, use API providers, or a hybrid? Design a TCO analysis framework and hybrid strategy that minimizes cost at each scale point.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Hybrid LLM Strategy                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Traffic Router (cost-optimal routing)                        │  │
│  │                                                              │  │
│  │  Query → Classify → Route to cheapest adequate option       │  │
│  │                                                              │  │
│  │  Simple queries (60%): Self-hosted Llama-7B ($0.0005/1K)    │  │
│  │  Medium queries (25%): Self-hosted Llama-70B ($0.005/1K)    │  │
│  │  Complex queries (10%): API GPT-4 ($0.03/1K)               │  │
│  │  Critical queries (5%): API Claude Opus ($0.015/1K)         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Self-Hosted Infrastructure                                  │  │
│  │                                                              │  │
│  │  Base load (85% of traffic):                                │  │
│  │  - 8x H100 cluster (Llama-70B, 4-GPU TP)                   │  │
│  │  - 4x A100 (Llama-7B, high throughput)                      │  │
│  │  - Monthly: $45K (reserved) + $10K ops                      │  │
│  │                                                              │  │
│  │  Handles: 42.5M tokens/day at $0.0013/1K avg               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ API Providers (overflow + premium)                          │  │
│  │                                                              │  │
│  │  Premium queries (15% of traffic):                          │  │
│  │  - GPT-4 for complex reasoning                              │  │
│  │  - Claude for nuanced generation                            │  │
│  │  - Monthly: $30K at current volume                          │  │
│  │                                                              │  │
│  │  Burst overflow:                                            │  │
│  │  - When self-hosted at capacity, overflow to API            │  │
│  │  - Monthly: $5K (variable)                                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Total Hybrid Cost: ~$90K/month                                   │
│  vs. All-API (GPT-4): ~$450K/month                               │
│  vs. All-Self-Hosted: ~$120K/month (but lower quality)           │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import numpy as np

@dataclass
class InfraOption:
    name: str
    type: str                    # "self_hosted" or "api"
    model: str
    quality_score: float         # 0-1 (1 = GPT-4 level)
    cost_per_1k_input: float     # USD
    cost_per_1k_output: float
    max_throughput_tokens_per_sec: float
    latency_p99_ms: float
    # Self-hosted specific
    gpu_type: Optional[str] = None
    gpu_count: int = 0
    monthly_infra_cost: float = 0  # Fixed cost
    ops_cost_monthly: float = 0    # Engineering time

@dataclass  
class TCOAnalysis:
    option: str
    monthly_cost: float
    cost_per_1k_tokens: float
    quality_score: float
    latency_p99: float
    scalability: str
    risk_factors: List[str]

class TCOCalculator:
    """Compare total cost of ownership across deployment options."""
    
    def __init__(self, daily_tokens: int = 50_000_000):
        self.daily_tokens = daily_tokens
        self.monthly_tokens = daily_tokens * 30
        
        # Define options
        self.options = {
            "api_gpt4": InfraOption(
                name="GPT-4 API", type="api", model="gpt-4",
                quality_score=1.0,
                cost_per_1k_input=0.03, cost_per_1k_output=0.06,
                max_throughput_tokens_per_sec=100_000,
                latency_p99_ms=2000
            ),
            "api_gpt35": InfraOption(
                name="GPT-3.5 API", type="api", model="gpt-3.5-turbo",
                quality_score=0.75,
                cost_per_1k_input=0.001, cost_per_1k_output=0.002,
                max_throughput_tokens_per_sec=500_000,
                latency_p99_ms=800
            ),
            "self_hosted_70b": InfraOption(
                name="Self-hosted Llama-70B", type="self_hosted",
                model="llama-70b",
                quality_score=0.85,
                cost_per_1k_input=0.005, cost_per_1k_output=0.015,
                max_throughput_tokens_per_sec=5000,
                latency_p99_ms=1500,
                gpu_type="H100", gpu_count=8,
                monthly_infra_cost=35_000,  # 8 H100s reserved
                ops_cost_monthly=10_000     # 0.5 FTE ML engineer
            ),
            "self_hosted_7b": InfraOption(
                name="Self-hosted Llama-7B INT8", type="self_hosted",
                model="llama-7b-int8",
                quality_score=0.65,
                cost_per_1k_input=0.0005, cost_per_1k_output=0.001,
                max_throughput_tokens_per_sec=20000,
                latency_p99_ms=200,
                gpu_type="A100", gpu_count=4,
                monthly_infra_cost=10_000,
                ops_cost_monthly=5_000
            ),
        }
    
    def calculate_tco(self, option_name: str) -> TCOAnalysis:
        """Calculate TCO for a single option at current scale."""
        opt = self.options[option_name]
        
        if opt.type == "api":
            # Assume 40% input, 60% output token split
            input_tokens = self.monthly_tokens * 0.4
            output_tokens = self.monthly_tokens * 0.6
            monthly_cost = (
                (input_tokens / 1000) * opt.cost_per_1k_input +
                (output_tokens / 1000) * opt.cost_per_1k_output
            )
            risks = ["Price increases", "Rate limits", "Provider outages", "Data privacy"]
        else:
            # Self-hosted: fixed infra + variable (negligible per-token)
            monthly_cost = opt.monthly_infra_cost + opt.ops_cost_monthly
            # Check if we need more GPUs for throughput
            required_tps = self.daily_tokens / 86400
            if required_tps > opt.max_throughput_tokens_per_sec:
                scale_factor = required_tps / opt.max_throughput_tokens_per_sec
                monthly_cost *= scale_factor
            risks = ["GPU procurement", "Ops complexity", "Model updates", "Security patches"]
        
        cost_per_1k = monthly_cost / (self.monthly_tokens / 1000)
        
        return TCOAnalysis(
            option=option_name,
            monthly_cost=monthly_cost,
            cost_per_1k_tokens=cost_per_1k,
            quality_score=opt.quality_score,
            latency_p99=opt.latency_p99_ms,
            scalability="Elastic" if opt.type == "api" else "Step function",
            risk_factors=risks
        )
    
    def design_hybrid_strategy(self) -> dict:
        """Design optimal hybrid strategy."""
        # Classify traffic by complexity
        traffic_mix = {
            "simple": 0.60,   # Factual, short, reformatting
            "medium": 0.25,   # Moderate reasoning
            "complex": 0.10,  # Multi-step reasoning
            "critical": 0.05, # Must be highest quality
        }
        
        # Assign cheapest adequate option per category
        routing = {
            "simple": "self_hosted_7b",      # Cheapest, adequate quality
            "medium": "self_hosted_70b",     # Good quality, cost-effective
            "complex": "api_gpt4",           # Best quality for hard queries
            "critical": "api_gpt4",          # Premium for critical
        }
        
        # Calculate blended cost
        total_monthly = 0
        blended_quality = 0
        
        for category, fraction in traffic_mix.items():
            option = self.options[routing[category]]
            category_tokens = self.monthly_tokens * fraction
            
            if option.type == "api":
                input_t = category_tokens * 0.4
                output_t = category_tokens * 0.6
                cost = (input_t/1000) * option.cost_per_1k_input + (output_t/1000) * option.cost_per_1k_output
            else:
                # Proportion of fixed cost
                cost = (option.monthly_infra_cost + option.ops_cost_monthly) * fraction / 0.85
            
            total_monthly += cost
            blended_quality += option.quality_score * fraction
        
        return {
            "routing": routing,
            "monthly_cost": total_monthly,
            "blended_quality": blended_quality,
            "cost_per_1k_blended": total_monthly / (self.monthly_tokens / 1000),
            "vs_all_api_gpt4": self.calculate_tco("api_gpt4").monthly_cost,
            "savings_vs_all_api": 1 - total_monthly / self.calculate_tco("api_gpt4").monthly_cost,
        }
    
    def breakeven_analysis(self) -> dict:
        """At what scale does self-hosting become cheaper than API?"""
        # Self-hosted 70B: $45K fixed + minimal marginal
        # API GPT-4: $0.045/1K tokens (blended)
        
        self_hosted_fixed = 45_000  # Monthly
        self_hosted_marginal_per_1k = 0.001  # Electricity, negligible
        api_per_1k = 0.045  # Blended GPT-4
        
        # Breakeven: fixed + marginal * X = api * X
        # fixed = X * (api - marginal)
        breakeven_tokens_monthly = self_hosted_fixed / (api_per_1k - self_hosted_marginal_per_1k) * 1000
        breakeven_tokens_daily = breakeven_tokens_monthly / 30
        
        return {
            "breakeven_tokens_per_day": breakeven_tokens_daily,
            "breakeven_tokens_per_month": breakeven_tokens_monthly,
            "recommendation": {
                "below_breakeven": "Use API only",
                "1x_breakeven": "Hybrid (self-host base, API for peak/premium)",
                "3x_breakeven": "Primarily self-hosted with API fallback",
                "10x_breakeven": "Full self-hosted with multi-provider API DR only",
            }
        }


class HybridRouter:
    """Routes requests to optimal backend (self-hosted or API) based on cost and quality."""
    
    def __init__(self, tco_calculator: TCOCalculator):
        self.calculator = tco_calculator
        self.self_hosted_load = 0.0  # Current utilization
    
    def route(self, query: str, complexity: str, 
              quality_requirement: float = 0.8) -> str:
        """Route to cheapest option meeting quality requirement."""
        candidates = []
        
        for name, option in self.calculator.options.items():
            if option.quality_score >= quality_requirement:
                # Check if self-hosted has capacity
                if option.type == "self_hosted" and self.self_hosted_load > 0.9:
                    continue  # At capacity, skip
                
                # Effective cost
                if option.type == "api":
                    cost = option.cost_per_1k_input  # Simplified
                else:
                    # Marginal cost when capacity is available ≈ 0
                    cost = 0.001  # Near-zero marginal
                
                candidates.append((cost, name, option))
        
        if not candidates:
            return "api_gpt4"  # Default fallback
        
        # Sort by cost, return cheapest
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
```

### TCO Comparison Table (50M tokens/day)

| Option | Monthly Cost | Cost/1K Tokens | Quality | Latency p99 | Scalability |
|--------|-------------|---------------|---------|-------------|-------------|
| All GPT-4 API | $450K | $0.030 | 1.00 | 2000ms | Elastic |
| All GPT-3.5 API | $22K | $0.0015 | 0.75 | 800ms | Elastic |
| Self-hosted 70B | $55K | $0.0037 | 0.85 | 1500ms | Step |
| Self-hosted 7B | $15K | $0.0010 | 0.65 | 200ms | Step |
| **Hybrid (optimal)** | **$90K** | **$0.006** | **0.88** | **600ms avg** | **Mixed** |

### Scale-Based Recommendations

| Daily Tokens | Recommendation | Monthly Cost | Rationale |
|-------------|----------------|-------------|-----------|
| <1M | API only | <$1.5K | Not worth infra overhead |
| 1M-10M | API with caching | $1.5K-$15K | Cache reduces API calls 30% |
| 10M-50M | Hybrid (this) | $50K-$90K | Self-host base, API for premium |
| 50M-500M | Primarily self-hosted | $90K-$400K | API only for overflow/premium |
| >500M | Full self-hosted | $400K+ | Dedicated GPU clusters, full control |

### Production Considerations

- **Hidden costs of self-hosting**: ML engineers ($200K/year each), on-call rotation, security patches, model updates, GPU failures. Add 30-50% to raw GPU costs.
- **API pricing volatility**: OpenAI has cut prices 3x in 2 years. Self-hosted ROI calculation changes with each price cut. Re-evaluate quarterly.
- **Quality gap matters**: If self-hosted quality is 85% of GPT-4, that 15% gap may matter for your use case. Measure on YOUR evaluation set, not benchmarks.
- **Hybrid complexity**: Running both self-hosted and API adds routing logic, monitoring for both, and expertise in both. Don't underestimate ops burden.
- **Data privacy**: Self-hosted gives full data control. Some enterprises require this for compliance, making API options unavailable regardless of cost.
# Performance Engineering for AI (Questions 276-280)

## Q276: GPU memory optimization for serving multiple models on a single A100/H100

### Memory Layout Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│         A100 80GB - Multi-Model Memory Management                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Static Allocation ──────────────────────────────────┐        │
│  │  CUDA Runtime & Framework overhead: 2GB                  │        │
│  │  KV-Cache Pool (shared): 20GB                           │        │
│  └─────────────────────────────────────────────────────────┘        │
│                                                                      │
│  ┌─── Dynamic Model Pool (58GB) ──────────────────────────┐        │
│  │                                                          │        │
│  │  ┌────────────────┐  ┌────────────────┐                │        │
│  │  │ Model A (7B)   │  │ Model B (13B)  │  ← Hot        │        │
│  │  │ 14GB (FP16)    │  │ 7GB (INT4)     │    (in GPU)   │        │
│  │  └────────────────┘  └────────────────┘                │        │
│  │                                                          │        │
│  │  ┌────────────────┐                                     │        │
│  │  │ Model C (70B)  │  ← Partially loaded                │        │
│  │  │ 20GB (top 40   │    (remaining layers on CPU/NVMe)  │        │
│  │  │  layers loaded) │                                     │        │
│  │  └────────────────┘                                     │        │
│  │                                                          │        │
│  │  Free pool: 17GB (for dynamic allocation)               │        │
│  └─────────────────────────────────────────────────────────┘        │
│                                                                      │
│  ┌─── Swap Space (CPU RAM: 512GB) ────────────────────────┐        │
│  │  Model D, E, F (cold models, swapped in on demand)      │        │
│  │  Swap latency: ~200ms for 7B model (PCIe Gen4)         │        │
│  └─────────────────────────────────────────────────────────┘        │
└────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class GPUMemoryManager:
    """Multi-model GPU memory pool with dynamic allocation and swapping."""
    
    def __init__(self, gpu_memory_gb: int = 80):
        self.total_memory = gpu_memory_gb * 1024**3
        self.reserved = 2 * 1024**3  # CUDA overhead
        self.kv_cache_pool = KVCachePool(size_gb=20)
        self.model_pool = ModelPool(
            capacity=self.total_memory - self.reserved - self.kv_cache_pool.size)
        self.swap_space = CPUSwapSpace(size_gb=512)
        self.access_tracker = LRUTracker()
    
    def load_model(self, model_id: str, priority: str = "normal"):
        model_size = self.get_model_size(model_id)
        
        # Try to fit in GPU memory
        if self.model_pool.available >= model_size:
            self.model_pool.allocate(model_id, model_size)
            return LoadResult(location="gpu", latency_ms=0)
        
        # Need to evict - find LRU cold model
        eviction_candidate = self.access_tracker.get_lru()
        if eviction_candidate and priority != "low":
            self.swap_to_cpu(eviction_candidate)
            self.model_pool.allocate(model_id, model_size)
            return LoadResult(location="gpu", latency_ms=200)
        
        # Partial loading strategy for very large models
        if model_size > self.model_pool.capacity:
            return self.partial_load(model_id)
        
        return LoadResult(location="queued", latency_ms=None)
    
    def partial_load(self, model_id: str):
        """Load transformer layers that fit, offload rest to CPU."""
        model = self.load_model_metadata(model_id)
        layers = model.layers
        
        gpu_layers = []
        cpu_layers = []
        remaining_memory = self.model_pool.available
        
        # Load attention-heavy layers on GPU (they benefit most)
        for layer in sorted(layers, key=lambda l: l.compute_intensity, reverse=True):
            if remaining_memory >= layer.size:
                gpu_layers.append(layer)
                remaining_memory -= layer.size
            else:
                cpu_layers.append(layer)
        
        return HybridModel(gpu_layers=gpu_layers, cpu_layers=cpu_layers,
                          pipeline_parallel=True)
    
    def optimize_kv_cache(self, active_requests: List[Request]):
        """PagedAttention-style KV cache management."""
        # Allocate KV cache in pages (like virtual memory)
        # Share common prefixes across requests (system prompt)
        # Evict completed request caches immediately
        
        for request in active_requests:
            pages_needed = self.compute_kv_pages(request)
            if self.kv_cache_pool.available_pages >= pages_needed:
                self.kv_cache_pool.allocate(request.id, pages_needed)
            else:
                # Preempt lowest-priority request
                victim = self.find_preemption_victim(active_requests)
                self.kv_cache_pool.swap_out(victim.id)  # To CPU
                self.kv_cache_pool.allocate(request.id, pages_needed)
```

### Optimization Strategies

| Strategy | Memory Saving | Latency Impact | Quality Impact |
|----------|--------------|----------------|----------------|
| INT4 quantization (GPTQ/AWQ) | 75% reduction | +5-10% | -1-2% accuracy |
| INT8 quantization | 50% reduction | +2-5% | <0.5% accuracy |
| PagedAttention (vLLM) | 60% KV cache reduction | None | None |
| LoRA adapter sharing | 95% vs full copies | None | Depends on adapter |
| Speculative decoding | N/A (throughput) | -40% latency | None |
| Prefix caching | 30-60% KV savings | -30% TTFT | None |

### Production Metrics
- GPU memory utilization target: >90% (waste = money lost)
- Model swap latency: <300ms (7B model CPU→GPU over PCIe 5.0)
- KV cache hit rate (prefix sharing): >40% for similar prompts
- Throughput: 50-100 requests/sec per A100 (7B model, INT4)
- Cold start (first request to new model): <2s

---

## Q277: Network optimization for distributed AI inference across nodes

### Network Topology

```
┌────────────────────────────────────────────────────────────────────┐
│         Distributed Inference - Network Optimization                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Node 0 (Layers 0-15) ──┐     ┌─── Node 1 (Layers 16-31) ──┐│
│  │  GPU 0 ←─NVLink─→ GPU 1   │     │  GPU 0 ←─NVLink─→ GPU 1   ││
│  │    ↕                  ↕     │     │    ↕                  ↕     ││
│  │  GPU 2 ←─NVLink─→ GPU 3   │     │  GPU 2 ←─NVLink─→ GPU 3   ││
│  └────────────┬───────────────┘     └────────────┬───────────────┘│
│               │         RDMA/InfiniBand           │                 │
│               │         (400 Gbps)                │                 │
│               └───────────────────────────────────┘                 │
│                                                                      │
│  Pipeline Parallelism:                                              │
│  Node 0: Layers 0-15 compute → send activations via RDMA →         │
│  Node 1: Layers 16-31 compute → send output back                   │
│                                                                      │
│  Communication-Computation Overlap:                                  │
│  ┌──────────────────────────────────────────────────┐              │
│  │ Time →                                            │              │
│  │ Node 0: [Compute Batch 1][Send B1 | Compute B2]  │              │
│  │ Node 1: [Idle    ][Recv B1 | Compute B1][Send]   │              │
│  │                                                    │              │
│  │ With micro-batching: GPU idle time → ~0%          │              │
│  └──────────────────────────────────────────────────┘              │
└────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class DistributedInferenceOptimizer:
    """Optimize network communication for multi-node inference."""
    
    def __init__(self, topology: ClusterTopology):
        self.topology = topology
        self.rdma_manager = RDMAManager()
        self.pipeline_scheduler = PipelineScheduler()
    
    def setup_communication(self):
        """Configure RDMA for minimum-latency tensor transfer."""
        # 1. Pin memory for zero-copy RDMA
        for node in self.topology.nodes:
            self.rdma_manager.register_memory_region(
                node, size=self.compute_activation_size())
        
        # 2. Pre-establish RDMA queue pairs (avoid connection overhead)
        for src, dst in self.topology.communication_pairs:
            self.rdma_manager.create_queue_pair(src, dst,
                inline_threshold=256,  # Inline small messages
                send_queue_depth=128)
        
        # 3. NCCL configuration for collective operations
        self.nccl_config = {
            "NCCL_IB_HCA": "mlx5",  # InfiniBand device
            "NCCL_IB_GID_INDEX": 3,  # RoCE v2
            "NCCL_NET_GDR_LEVEL": 5,  # GPU Direct RDMA
            "NCCL_P2P_LEVEL": "NVL",  # Use NVLink when available
        }
    
    def overlap_communication_computation(self, model, micro_batch_size: int):
        """Pipeline micro-batches to hide communication latency."""
        num_micro_batches = self.compute_optimal_micro_batches(model)
        
        # Split each batch into micro-batches
        # While Node 0 computes micro-batch N+1,
        # it simultaneously sends micro-batch N's activations to Node 1
        
        pipeline = []
        for stage in range(model.num_stages):
            pipeline.append(PipelineStage(
                compute_fn=model.get_stage(stage),
                send_fn=self.async_rdma_send,
                recv_fn=self.async_rdma_recv,
                overlap=True  # CUDA streams for overlap
            ))
        
        return pipeline
    
    def compute_optimal_micro_batches(self, model) -> int:
        """Balance pipeline bubble vs. memory usage."""
        # More micro-batches = less bubble, more memory
        # Optimal: num_micro_batches >= 4 * num_pipeline_stages
        stages = model.num_stages
        activation_memory = model.activation_size_per_micro_batch
        available_memory = self.get_available_memory()
        
        max_micro_batches = available_memory // activation_memory
        optimal = min(max_micro_batches, stages * 4)
        return optimal
```

### Network Optimization Techniques

| Technique | Benefit | When to Use |
|-----------|---------|-------------|
| RDMA (Remote Direct Memory Access) | Bypass CPU, <5us latency | Always for inter-node |
| GPU Direct RDMA | GPU→NIC→GPU, bypass CPU entirely | NVIDIA + Mellanox |
| NVLink (intra-node) | 900 GB/s (H100) | Always for intra-node |
| Communication-computation overlap | Hide 90%+ of comm latency | Pipeline parallel |
| Tensor compression | 2-4x bandwidth savings | When bandwidth-bound |
| All-reduce optimization (ring/tree) | Optimal collective bandwidth | Tensor parallel |

### Latency Budget (70B model, 2 nodes)

| Component | Time | Optimization |
|-----------|------|-------------|
| Computation (per token) | 8ms | Quantization, FlashAttention |
| Inter-node transfer | 0.5ms | RDMA, overlap with compute |
| KV cache access | 0.2ms | PagedAttention, prefetch |
| Pipeline bubble | 1ms | More micro-batches |
| **Total per token** | **~10ms** | Target: <15ms for interactive |

---

## Q278: Storage architecture for vector databases with sub-10ms latency at 10M vectors

### Tiered Storage Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│         Vector DB Storage - 10M Vectors, <10ms P99                  │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Tier 1: DRAM (Hot) ──────────────────────────────┐          │
│  │  • Full HNSW graph (navigable structure)             │          │
│  │  • Frequently accessed vectors (top 1M)              │          │
│  │  • Size: ~16GB (1M × 1536 dims × 4 bytes + graph)   │          │
│  │  • Latency: <1ms                                     │          │
│  └─────────────────────────────────────────────────────┘          │
│                                                                      │
│  ┌─── Tier 2: NVMe SSD (Warm) ────────────────────────┐          │
│  │  • Remaining 9M vectors (quantized PQ codes in RAM)  │          │
│  │  • Full-precision vectors on SSD for re-ranking       │          │
│  │  • Size: ~120GB on SSD                               │          │
│  │  • Latency: 3-8ms (with read-ahead)                  │          │
│  └─────────────────────────────────────────────────────┘          │
│                                                                      │
│  ┌─── Design: DiskANN-style ──────────────────────────┐           │
│  │  1. HNSW graph structure in RAM (just node IDs)      │          │
│  │  2. PQ-compressed vectors in RAM (for candidate gen) │          │
│  │  3. Full vectors on SSD (for re-ranking top-K)       │          │
│  │  4. SSD read: sequential, prefetched, ~4 reads/query │          │
│  └─────────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────┘
```

### Storage Trade-off Analysis

| Storage Type | Cost/GB/mo | Latency (random 4K read) | Capacity | Best For |
|-------------|-----------|--------------------------|----------|----------|
| DRAM (DDR5) | $8-12 | <100ns | 100s of GB | Graph + hot vectors |
| Intel Optane PMem | $2-4 | 300ns | TBs | Deprecated but ideal latency/cost |
| NVMe SSD (Gen4) | $0.10-0.20 | 80-120us | 10s of TB | Bulk vector storage |
| NVMe SSD (Gen5) | $0.15-0.30 | 40-60us | 10s of TB | Lower latency bulk |

### Implementation

```python
class TieredVectorStore:
    """Sub-10ms vector search over 10M vectors using tiered storage."""
    
    def __init__(self, dim: int = 1536, num_vectors: int = 10_000_000):
        self.dim = dim
        
        # Tier 1: HNSW graph in RAM (just topology, no vectors)
        self.graph = HNSWGraph(
            max_elements=num_vectors,
            M=32,  # Connections per node
            ef_construction=200
        )
        
        # Tier 2: Product quantization codes in RAM (compressed)
        # 1536 dims → 96 subspaces × 1 byte = 96 bytes per vector
        self.pq_codes = np.memmap("pq_codes.bin", dtype=np.uint8,
                                   shape=(num_vectors, 96))  # ~960MB in RAM
        self.pq_codebook = ProductQuantizer(dim=1536, n_subspaces=96)
        
        # Tier 3: Full vectors on NVMe (for re-ranking)
        self.full_vectors = MMapVectorStore(
            path="/nvme/vectors.bin",
            dim=dim, dtype=np.float32,
            prefetch_strategy="sequential"
        )
    
    def search(self, query: np.ndarray, k: int = 10, 
               ef_search: int = 100) -> List[SearchResult]:
        """Two-phase search: approximate candidates then exact re-rank."""
        
        # Phase 1: Traverse HNSW graph using PQ distances (all in RAM)
        # Latency: ~2ms for ef_search=100
        candidates = self.graph.search_with_pq(
            query, self.pq_codes, self.pq_codebook,
            ef=ef_search  # Explore 100 candidates
        )  # Returns ~100 candidate IDs with approximate distances
        
        # Phase 2: Re-rank top candidates with exact distances (SSD read)
        # Only read ~100 vectors from SSD (sequential read pattern)
        # Latency: ~3-5ms (batched NVMe reads)
        top_candidates = sorted(candidates, key=lambda c: c.approx_dist)[:k*3]
        
        exact_vectors = self.full_vectors.batch_read(
            [c.id for c in top_candidates])  # Prefetched sequential reads
        
        exact_distances = np.linalg.norm(
            exact_vectors - query, axis=1)
        
        # Return top-K with exact distances
        top_k_indices = np.argpartition(exact_distances, k)[:k]
        return [SearchResult(id=top_candidates[i].id, 
                            distance=exact_distances[i])
                for i in sorted(top_k_indices, 
                               key=lambda i: exact_distances[i])]
```

### Performance Optimization Checklist

| Optimization | Impact | Implementation |
|-------------|--------|----------------|
| PQ compression | 16x RAM reduction | 96 subspaces, 256 centroids each |
| Graph in RAM | Eliminates random SSD I/O for traversal | ~2GB for 10M nodes |
| Batch SSD reads | 3x vs random reads | io_uring with read-ahead |
| NUMA-aware allocation | 20% latency reduction | Pin graph to local NUMA node |
| Prefetch on graph traversal | Hide SSD latency | Prefetch neighbor vectors |

---

## Q279: CPU/GPU pipeline for mixed AI workloads

### Pipeline Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│         CPU/GPU Pipeline - Maximizing Throughput                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── CPU Domain ────────────┐     ┌─── GPU Domain ──────────────┐│
│  │                            │     │                              ││
│  │  Request Queue             │     │  Inference Engine            ││
│  │       │                    │     │       │                      ││
│  │       ▼                    │     │       ▼                      ││
│  │  Tokenization       ──────────────→  Embedding Lookup          ││
│  │  (CPU-bound)        pinned │     │  (GPU memory)               ││
│  │       │             memory │     │       │                      ││
│  │       ▼              DMA   │     │       ▼                      ││
│  │  Pre-processing     ──────────────→  Transformer Forward       ││
│  │  (truncation,       zero   │     │  (GPU compute)              ││
│  │   padding,          copy   │     │       │                      ││
│  │   attention mask)          │     │       ▼                      ││
│  │                            │     │  Sampling/Decode             ││
│  │  Post-processing    ←──────────────  (GPU → CPU)               ││
│  │  (detokenize,       async  │     │                              ││
│  │   format response)  copy   │     │                              ││
│  └────────────────────────────┘     └──────────────────────────────┘│
│                                                                      │
│  Timeline (pipelined):                                              │
│  CPU:  [Tok B1][Tok B2][Tok B3][Post B1][Post B2]...               │
│  DMA:       [Send B1][Send B2][Send B3]...                         │
│  GPU:            [Infer B1][Infer B2][Infer B3]...                 │
│                                                                      │
│  All 3 stages run concurrently on different batches!                │
└────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class CPUGPUPipeline:
    """Overlapped CPU/GPU pipeline for maximum throughput."""
    
    def __init__(self, model, num_cpu_workers: int = 4):
        self.model = model
        self.device = torch.device("cuda")
        
        # Pinned memory pool (avoids allocation overhead)
        self.pinned_pool = PinnedMemoryPool(
            num_buffers=8,  # Double-buffer for overlap
            buffer_size=self.compute_max_batch_size()
        )
        
        # CUDA streams for async operations
        self.compute_stream = torch.cuda.Stream()
        self.transfer_stream = torch.cuda.Stream()
        
        # CPU thread pool for tokenization
        self.cpu_executor = ThreadPoolExecutor(max_workers=num_cpu_workers)
        
        # Pipeline queues
        self.tokenized_queue = asyncio.Queue(maxsize=4)
        self.result_queue = asyncio.Queue(maxsize=4)
    
    async def process_batch(self, requests: List[str]):
        """Pipeline: tokenize → transfer → infer → transfer back → decode."""
        
        # Stage 1: CPU tokenization (parallel threads)
        tokenized = await asyncio.get_event_loop().run_in_executor(
            self.cpu_executor,
            self.batch_tokenize, requests
        )
        
        # Stage 2: Zero-copy transfer to GPU via pinned memory
        pinned_buffer = self.pinned_pool.acquire()
        pinned_buffer.copy_(tokenized.input_ids)  # CPU → pinned memory
        
        with torch.cuda.stream(self.transfer_stream):
            # Async DMA: pinned memory → GPU (non-blocking)
            gpu_input = pinned_buffer.to(self.device, non_blocking=True)
        
        # Stage 3: GPU inference (overlapped with next batch's transfer)
        self.transfer_stream.synchronize()  # Wait for transfer
        
        with torch.cuda.stream(self.compute_stream):
            with torch.no_grad():
                output = self.model(gpu_input)
        
        # Stage 4: Async transfer back to CPU
        with torch.cuda.stream(self.transfer_stream):
            cpu_output = output.to("cpu", non_blocking=True)
        
        self.compute_stream.synchronize()
        self.transfer_stream.synchronize()
        
        # Stage 5: CPU post-processing (detokenization)
        results = await asyncio.get_event_loop().run_in_executor(
            self.cpu_executor,
            self.batch_detokenize, cpu_output
        )
        
        self.pinned_pool.release(pinned_buffer)
        return results
    
    async def run_pipeline(self, request_stream):
        """Continuous pipeline with overlap between batches."""
        batch_buffer = []
        
        async for request in request_stream:
            batch_buffer.append(request)
            
            if len(batch_buffer) >= self.optimal_batch_size:
                # Launch batch processing (doesn't block next accumulation)
                asyncio.create_task(
                    self.process_batch(batch_buffer.copy()))
                batch_buffer.clear()
```

### Key Optimizations

| Technique | Benefit | Implementation Detail |
|-----------|---------|----------------------|
| Pinned memory | Avoids pageable→pinned copy | `torch.cuda.pin_memory()` pool |
| Zero-copy (CUDA mapped) | CPU writes directly to GPU-visible memory | `cudaHostAlloc(MAPPED)` |
| Dual CUDA streams | Overlap transfer + compute | Separate streams for DMA/compute |
| Continuous batching | No GPU idle between batches | vLLM-style iteration-level scheduling |
| CPU thread pool | Parallelize tokenization | 4-8 threads matching CPU cores |
| Memory pool | Avoid allocation overhead | Pre-allocate, reuse buffers |

---

## Q280: Profiling and optimization methodology for production AI systems

### Systematic Optimization Framework

```
┌────────────────────────────────────────────────────────────────────┐
│         AI Performance Optimization Methodology                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 1: MEASURE (Don't guess)                                      │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  • End-to-end latency breakdown (where is time spent?)   │       │
│  │  • GPU utilization (compute vs. memory-bound?)           │       │
│  │  • CPU utilization (tokenization bottleneck?)            │       │
│  │  • Memory bandwidth utilization                          │       │
│  │  • Network utilization (distributed inference)           │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Step 2: IDENTIFY bottleneck (Amdahl's Law)                        │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  • If GPU util < 50%: likely memory-bound or starved     │       │
│  │  • If GPU util > 90%: compute-bound, need faster GPU     │       │
│  │  • If CPU is hot: pre/post processing is the bottleneck  │       │
│  │  • If memory bandwidth maxed: need quantization          │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Step 3: OPTIMIZE the bottleneck (one at a time!)                  │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  • Apply targeted optimization                           │       │
│  │  • Measure again (verify improvement)                    │       │
│  │  • Check for new bottleneck (it shifts!)                 │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Step 4: VALIDATE (production conditions)                           │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  • Load test at 2x expected peak                         │       │
│  │  • Verify quality unchanged (accuracy regression test)   │       │
│  │  • Monitor for 24h under real traffic                    │       │
│  └─────────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────┘
```

### Profiling Tools and Usage

```python
class AISystemProfiler:
    """Comprehensive profiling for AI inference systems."""
    
    def profile_inference(self, model, sample_inputs, iterations=100):
        """Multi-dimensional profiling of inference performance."""
        
        # 1. GPU Profiling (NVIDIA Nsight / PyTorch Profiler)
        with torch.profiler.profile(
            activities=[
                torch.profiler.ProfilerActivity.CPU,
                torch.profiler.ProfilerActivity.CUDA],
            schedule=torch.profiler.schedule(wait=2, warmup=3, active=5),
            on_trace_ready=torch.profiler.tensorboard_trace_handler("./logs"),
            record_shapes=True,
            profile_memory=True,
            with_stack=True
        ) as prof:
            for i, input_batch in enumerate(sample_inputs[:10]):
                with torch.profiler.record_function("inference"):
                    model(input_batch)
                prof.step()
        
        # 2. Memory profiling
        torch.cuda.memory._record_memory_history()
        model(sample_inputs[0])
        snapshot = torch.cuda.memory._snapshot()
        # Analyze: peak memory, fragmentation, allocation patterns
        
        # 3. Kernel-level analysis
        # Use: ncu --set full python inference.py
        # Look for: low occupancy, high memory bandwidth usage,
        #           register spilling, shared memory bank conflicts
        
        # 4. End-to-end latency breakdown
        timings = {}
        for stage in ["tokenize", "embed", "attention", "ffn", 
                      "sample", "detokenize"]:
            timings[stage] = self.time_stage(model, stage, sample_inputs)
        
        return ProfilingReport(
            gpu_utilization=self.measure_gpu_util(),
            memory_bandwidth_util=self.measure_memory_bw(),
            compute_util=self.measure_compute_util(),
            latency_breakdown=timings,
            bottleneck=self.identify_bottleneck(timings)
        )
    
    def identify_bottleneck(self, timings: Dict) -> str:
        """Determine the primary performance bottleneck."""
        total = sum(timings.values())
        
        # Find stage consuming most time
        dominant = max(timings, key=timings.get)
        dominant_pct = timings[dominant] / total
        
        if dominant_pct > 0.5:
            return f"Single bottleneck: {dominant} ({dominant_pct:.0%} of time)"
        
        # Check if memory-bound vs compute-bound
        gpu_util = self.measure_gpu_util()
        mem_bw = self.measure_memory_bw()
        
        if mem_bw > 0.8 and gpu_util < 0.5:
            return "Memory bandwidth bound (typical for inference)"
        elif gpu_util > 0.8:
            return "Compute bound (need faster hardware or smaller model)"
        else:
            return "Likely starved (CPU preprocessing or data loading)"
```

### Common AI Performance Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|-------------|---------|-----|
| Synchronous tokenization | GPU idle between batches | Async CPU pipeline |
| No batching | GPU at 10% util | Dynamic batching (pad to batch) |
| FP32 when FP16 works | 2x slower, 2x memory | Mixed precision (AMP) |
| Naive attention | O(n^2) memory | FlashAttention-2 |
| Python GIL bottleneck | CPU at 100% single core | Rust tokenizer, multiprocess |
| Fragmented KV cache | OOM at low utilization | PagedAttention |
| No prefix caching | Recompute system prompt every time | Prefix cache sharing |

### Production Monitoring Dashboards

| Metric | Alert Threshold | Action |
|--------|----------------|--------|
| P99 latency | >2x baseline | Check GPU thermal throttle, batch size |
| GPU utilization | <60% sustained | Investigate scheduling, increase batch |
| GPU memory | >95% | Risk of OOM, reduce batch or add quantization |
| Throughput drop | >20% from baseline | Check for model regression, infra issue |
| Error rate | >1% | Check for OOM, timeout, model crash |
