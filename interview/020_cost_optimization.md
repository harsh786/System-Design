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
