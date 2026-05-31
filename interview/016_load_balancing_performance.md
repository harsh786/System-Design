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
