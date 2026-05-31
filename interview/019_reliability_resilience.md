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
