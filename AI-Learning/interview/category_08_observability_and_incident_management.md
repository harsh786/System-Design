# Observability for AI Systems (Questions 126-130)

## Q126: Design an end-to-end observability stack for an AI platform covering LLM inference, retrieval, embedding generation, and safety systems.

### Answer

**Architecture Overview:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI Platform Observability                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐     │
│  │ LLM Infer│   │ Retrieval│   │ Embedding│   │ Safety System│     │
│  │  Service  │   │  Service │   │  Service │   │              │     │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └──────┬───────┘     │
│       │               │               │                │             │
│  ┌────▼───────────────▼───────────────▼────────────────▼──────┐     │
│  │              OpenTelemetry Collector (per-node)              │     │
│  │   Metrics (OTLP) │ Traces (OTLP) │ Logs (OTLP)           │     │
│  └────┬──────────────┬───────────────┬────────────────────────┘     │
│       │              │               │                               │
│  ┌────▼────┐   ┌────▼────┐   ┌─────▼─────┐   ┌──────────────┐    │
│  │Prometheus│   │  Tempo  │   │   Loki    │   │ AI Quality   │    │
│  │ /Mimir  │   │ /Jaeger │   │           │   │  Store (PG)  │    │
│  └────┬────┘   └────┬────┘   └─────┬─────┘   └──────┬───────┘    │
│       │              │               │                │             │
│  ┌────▼──────────────▼───────────────▼────────────────▼──────┐     │
│  │                     Grafana Dashboards                      │     │
│  │   AI Quality │ Cost │ Latency │ Safety │ Per-Model         │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                       │
│  ┌───────────────────────────▼────────────────────────────────┐     │
│  │              Alertmanager + PagerDuty + Slack               │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

**AI-Specific Metrics Layer:**

```python
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from dataclasses import dataclass
import time

meter = metrics.get_meter("ai_platform")
tracer = trace.get_tracer("ai_platform")

# LLM-specific metrics
llm_latency = meter.create_histogram("llm.inference.latency_ms",
    description="LLM inference latency by model and operation")
llm_tokens_input = meter.create_counter("llm.tokens.input",
    description="Input tokens consumed")
llm_tokens_output = meter.create_counter("llm.tokens.output",
    description="Output tokens generated")
llm_quality_score = meter.create_histogram("llm.quality.score",
    description="Quality score from automated eval [0-1]")
llm_hallucination_rate = meter.create_histogram("llm.hallucination.rate",
    description="Hallucination detection score per response")

# Retrieval metrics
retrieval_recall = meter.create_histogram("retrieval.recall_at_k",
    description="Recall@K for retrieval")
retrieval_mrr = meter.create_histogram("retrieval.mrr",
    description="Mean Reciprocal Rank")
retrieval_latency = meter.create_histogram("retrieval.latency_ms")
retrieval_empty_results = meter.create_counter("retrieval.empty_results")

# Safety metrics
safety_blocked = meter.create_counter("safety.blocked_requests",
    description="Requests blocked by safety filters")
safety_latency = meter.create_histogram("safety.filter.latency_ms")
safety_false_positive_rate = meter.create_histogram("safety.false_positive.rate")

class AIObservabilityMiddleware:
    """Unified observability for all AI service calls."""

    def instrument_llm_call(self, model: str, prompt: str, response: str,
                            latency_ms: float, input_tokens: int, output_tokens: int):
        with tracer.start_as_current_span("llm.inference") as span:
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.input_tokens", input_tokens)
            span.set_attribute("llm.output_tokens", output_tokens)
            span.set_attribute("llm.latency_ms", latency_ms)

            llm_latency.record(latency_ms, {"model": model})
            llm_tokens_input.add(input_tokens, {"model": model})
            llm_tokens_output.add(output_tokens, {"model": model})

            # Async quality scoring (non-blocking)
            quality = self._compute_quality_async(prompt, response)
            llm_quality_score.record(quality, {"model": model})

    def instrument_retrieval(self, query: str, results: list,
                             ground_truth: list = None, latency_ms: float = 0):
        with tracer.start_as_current_span("retrieval.search") as span:
            span.set_attribute("retrieval.num_results", len(results))
            span.set_attribute("retrieval.latency_ms", latency_ms)
            retrieval_latency.record(latency_ms)

            if not results:
                retrieval_empty_results.add(1)
            if ground_truth:
                recall = self._compute_recall(results, ground_truth, k=10)
                retrieval_recall.record(recall)
```

**Alerting Rules (AI-Specific):**

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Hallucination spike | hallucination_rate > 0.15 for 5min | P1 | Page on-call, enable strict guardrails |
| Retrieval quality drop | recall@10 < 0.6 for 10min | P2 | Alert AI team, check index health |
| Cost anomaly | hourly_cost > 2x rolling_avg | P2 | Alert finance + eng, check for loops |
| Safety filter bypass | blocked_rate drops > 50% | P1 | Page security, audit recent changes |
| Latency P99 spike | p99 > 10s for 5min | P2 | Scale inference, check queue depth |

**Production Considerations:**
- Sampling strategy: 100% for errors/safety events, 10% for normal traces, 1% for embedding ops
- Cardinality control: Don't use prompt content as label; use hashed session IDs
- Retention: 7 days hot (traces), 30 days warm (metrics), 1 year cold (aggregates)
- Cost: OTel collector batching reduces egress; use exemplars instead of full traces in metrics

---

## Q127: Design a distributed tracing system for RAG pipelines that traces a single user query through embedding, retrieval, re-ranking, generation, and safety filtering.

### Answer

**End-to-End Trace Architecture:**

```
User Query: "What's our refund policy for enterprise customers?"
     │
     │ trace_id: abc123, span_id: root_001
     ▼
┌─────────────────────────────────────────────────────────────┐
│ API Gateway (parent span)                                    │
│ Duration: 2.3s | Status: OK                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ┌─────────────────────────────────────┐                     │
│ │ Span: query_understanding (45ms)     │                     │
│ │ - intent: policy_lookup              │                     │
│ │ - entities: [refund, enterprise]     │                     │
│ └──────────────┬──────────────────────┘                     │
│                │                                             │
│ ┌──────────────▼──────────────────────┐                     │
│ │ Span: embedding_generation (120ms)   │                     │
│ │ - model: text-embedding-3-large      │                     │
│ │ - dimensions: 3072                   │                     │
│ │ - tokens: 12                         │                     │
│ └──────────────┬──────────────────────┘                     │
│                │                                             │
│ ┌──────────────▼──────────────────────┐                     │
│ │ Span: retrieval (85ms)               │                     │
│ │ - index: policies_v3                 │                     │
│ │ - top_k: 20                          │                     │
│ │ - results_returned: 18               │                     │
│ │ - max_similarity: 0.92              │                     │
│ │ - min_similarity: 0.71              │                     │
│ └──────────────┬──────────────────────┘                     │
│                │                                             │
│ ┌──────────────▼──────────────────────┐                     │
│ │ Span: reranking (200ms)              │                     │
│ │ - model: cross-encoder-v2            │                     │
│ │ - input_docs: 18                     │                     │
│ │ - output_docs: 5                     │                     │
│ │ - top_score: 0.97                   │                     │
│ └──────────────┬──────────────────────┘                     │
│                │                                             │
│ ┌──────────────▼──────────────────────┐                     │
│ │ Span: generation (1.6s)              │                     │
│ │ - model: gpt-4o                      │                     │
│ │ - input_tokens: 3200                 │                     │
│ │ - output_tokens: 450                 │                     │
│ │ - temperature: 0.1                   │                     │
│ │ - finish_reason: stop                │                     │
│ └──────────────┬──────────────────────┘                     │
│                │                                             │
│ ┌──────────────▼──────────────────────┐                     │
│ │ Span: safety_filter (180ms)          │                     │
│ │ - checks: [pii, toxicity, accuracy] │                     │
│ │ - pii_detected: false                │                     │
│ │ - toxicity_score: 0.01              │                     │
│ │ - citation_verified: true            │                     │
│ │ - action: pass                       │                     │
│ └──────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from opentelemetry import trace, context
from opentelemetry.trace import SpanKind, StatusCode
from opentelemetry.propagate import inject, extract
import hashlib

tracer = trace.get_tracer("rag_pipeline", "1.0.0")

class RAGPipelineTracer:
    """Distributed tracing for RAG pipelines with AI-specific attributes."""

    def __init__(self):
        self.quality_evaluator = AsyncQualityEvaluator()

    async def trace_full_pipeline(self, query: str, user_id: str) -> dict:
        with tracer.start_as_current_span("rag.pipeline",
                kind=SpanKind.SERVER) as root_span:

            # Attach correlation IDs
            query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
            root_span.set_attribute("rag.query_hash", query_hash)
            root_span.set_attribute("rag.user_id_hash", hash(user_id) % 10**8)

            # Step 1: Query Understanding
            with tracer.start_as_current_span("rag.query_understanding") as span:
                intent = await self.understand_query(query)
                span.set_attribute("rag.intent", intent.label)
                span.set_attribute("rag.entities", str(intent.entities))
                span.set_attribute("rag.complexity", intent.complexity_score)

            # Step 2: Embedding
            with tracer.start_as_current_span("rag.embedding") as span:
                embedding = await self.generate_embedding(query)
                span.set_attribute("embedding.model", "text-embedding-3-large")
                span.set_attribute("embedding.dimensions", len(embedding))
                span.set_attribute("embedding.norm", float(np.linalg.norm(embedding)))

            # Step 3: Retrieval (may fan out to multiple indexes)
            with tracer.start_as_current_span("rag.retrieval") as span:
                results = await self.retrieve(embedding, intent)
                span.set_attribute("retrieval.total_results", len(results))
                span.set_attribute("retrieval.sources", list(set(r.source for r in results)))
                span.set_attribute("retrieval.score_distribution",
                    {"max": results[0].score, "min": results[-1].score,
                     "mean": sum(r.score for r in results) / len(results)})

                # Add events for each retrieval source
                for source_index in set(r.source for r in results):
                    span.add_event(f"retrieved_from_{source_index}",
                        {"count": sum(1 for r in results if r.source == source_index)})

            # Step 4: Re-ranking
            with tracer.start_as_current_span("rag.reranking") as span:
                reranked = await self.rerank(query, results)
                span.set_attribute("rerank.input_count", len(results))
                span.set_attribute("rerank.output_count", len(reranked))
                span.set_attribute("rerank.position_changes",
                    self._compute_rank_changes(results, reranked))

            # Step 5: Generation
            with tracer.start_as_current_span("rag.generation") as span:
                response = await self.generate(query, reranked)
                span.set_attribute("gen.model", response.model)
                span.set_attribute("gen.input_tokens", response.usage.input)
                span.set_attribute("gen.output_tokens", response.usage.output)
                span.set_attribute("gen.finish_reason", response.finish_reason)

            # Step 6: Safety
            with tracer.start_as_current_span("rag.safety_filter") as span:
                safety_result = await self.safety_check(query, response.text)
                span.set_attribute("safety.passed", safety_result.passed)
                span.set_attribute("safety.scores", safety_result.scores)
                if not safety_result.passed:
                    span.set_status(StatusCode.ERROR, "Safety filter triggered")
                    root_span.set_attribute("rag.filtered", True)

            # Attach quality evaluation (async, doesn't block response)
            root_span.set_attribute("rag.total_tokens",
                response.usage.input + response.usage.output)

            return {"response": response.text, "trace_id": root_span.context.trace_id}
```

**Trace Correlation Strategy:**
- Every request gets a `trace_id` propagated via W3C TraceContext headers
- Cross-service: inject context into gRPC metadata and HTTP headers
- Async operations (embedding batch jobs): use trace links instead of parent-child
- Store `trace_id` with user feedback for later correlation

**Performance Debugging Workflow:**
1. Filter traces by P99 latency in Tempo/Jaeger
2. Identify which span dominates (usually generation or retrieval)
3. Compare span attributes (token count, result count) between fast/slow traces
4. Use exemplars in Prometheus to jump from metric spike → specific trace

---

## Q128: Design a real-time quality monitoring dashboard for a production AI system.

### Answer

**Dashboard Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI Quality Dashboard                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─── Overall Health ──────────────────────────────────────────┐ │
│  │ Quality Score: 0.87 ▼ (was 0.91 yesterday)                  │ │
│  │ [████████░░] 87%    SLO Target: 85%  Budget: 72% remaining │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─── Real-time Metrics (5min windows) ────────────────────────┐ │
│  │                                                              │ │
│  │  Relevance    Faithfulness   Safety      Latency P50/P99    │ │
│  │  ┌──┐        ┌──┐          ┌──┐        ┌──┐               │ │
│  │  │▓▓│ 0.89   │▓▓│ 0.93    │▓▓│ 0.99   │▓▓│ 1.2s/3.4s    │ │
│  │  │▓▓│        │▓▓│          │▓▓│        │▓▓│               │ │
│  │  │▓▓│        │▓▓│          │▓▓│        │▓▓│               │ │
│  │  └──┘        └──┘          └──┘        └──┘               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─── Anomaly Detection ───────────────────────────────────────┐ │
│  │ ⚠ Retrieval recall dropped 12% in last 30min (cluster: B)  │ │
│  │ ⚠ Hallucination rate trending up: 0.05 → 0.09 (1hr)       │ │
│  │ ✓ No cost anomalies detected                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─── Quality by Segment ─────────────────────────────────────┐ │
│  │ Feature    | Quality | Volume | Trend                        │ │
│  │ Search     | 0.91    | 12K/hr | →                           │ │
│  │ Chat       | 0.84    | 8K/hr  | ↓                           │ │
│  │ Summarize  | 0.88    | 3K/hr  | →                           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Metrics Tracked:**

```python
from dataclasses import dataclass
from enum import Enum
import numpy as np
from scipy import stats

class QualityDimension(Enum):
    RELEVANCE = "relevance"          # Is the answer relevant to the query?
    FAITHFULNESS = "faithfulness"    # Is it grounded in retrieved context?
    COMPLETENESS = "completeness"    # Does it fully answer the question?
    SAFETY = "safety"                # Free of harmful content?
    COHERENCE = "coherence"          # Well-structured and clear?

@dataclass
class QualityMetrics:
    # Core quality (sampled evaluation via LLM-as-judge)
    relevance_score: float       # [0,1] - semantic relevance
    faithfulness_score: float    # [0,1] - grounded in sources
    hallucination_rate: float    # [0,1] - fabricated claims ratio

    # Retrieval quality
    retrieval_recall_at_10: float
    retrieval_mrr: float
    empty_retrieval_rate: float

    # User signals (proxy metrics, available in real-time)
    thumbs_up_rate: float
    regeneration_rate: float     # User clicked "regenerate"
    copy_rate: float             # User copied the answer
    session_abandonment: float

    # Operational
    latency_p50: float
    latency_p99: float
    error_rate: float
    token_efficiency: float      # useful_tokens / total_tokens


class AnomalyDetector:
    """Detects quality degradation before users complain."""

    def __init__(self, window_size: int = 100, sensitivity: float = 2.5):
        self.window_size = window_size
        self.sensitivity = sensitivity
        self.baselines: dict[str, list[float]] = {}

    def check(self, metric_name: str, value: float) -> dict:
        if metric_name not in self.baselines:
            self.baselines[metric_name] = []

        history = self.baselines[metric_name]
        history.append(value)

        if len(history) < self.window_size:
            return {"anomaly": False}

        # Rolling Z-score detection
        recent = history[-self.window_size:]
        baseline = history[-self.window_size*4:-self.window_size]  # 4x window as baseline

        if not baseline:
            return {"anomaly": False}

        baseline_mean = np.mean(baseline)
        baseline_std = np.std(baseline) or 0.01
        current_mean = np.mean(recent[-10:])  # Last 10 points

        z_score = (current_mean - baseline_mean) / baseline_std

        # Two-sided for latency (increase bad), one-sided for quality (decrease bad)
        is_anomaly = abs(z_score) > self.sensitivity

        # Mann-Whitney U test for distribution shift
        _, p_value = stats.mannwhitneyu(baseline[-50:], recent[-10:],
                                         alternative='two-sided')

        return {
            "anomaly": is_anomaly or p_value < 0.01,
            "z_score": z_score,
            "p_value": p_value,
            "direction": "degrading" if z_score < -self.sensitivity else "improving",
            "baseline_mean": baseline_mean,
            "current_mean": current_mean,
        }
```

**Early Detection Strategy:**
1. **Leading indicators** (detect in minutes): regeneration rate, session abandonment, latency spikes
2. **Sampled evaluation** (detect in 5-15min): Run LLM-as-judge on 5% of responses
3. **Lagging indicators** (confirm in hours): thumbs down rate, support tickets

**Production Considerations:**
- Sample rate for LLM-as-judge: 5% of traffic (cost-controlled)
- Use lightweight classifiers for 100% coverage on safety/hallucination
- Dashboard refresh: 30s for operational metrics, 5min for quality scores
- Alert on rate-of-change, not just absolute thresholds (catches slow degradation)

---

## Q129: Design a cost observability system for real-time AI spending visibility.

### Answer

**Architecture:**

```
┌───────────────────────────────────────────────────────────────────┐
│                     AI Cost Observability System                    │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ LLM Calls│  │ Embedding│  │  GPU      │  │  Vector DB       │  │
│  │ (tokens) │  │ (tokens) │  │ (compute) │  │  (storage+query) │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │              │              │                  │            │
│  ┌────▼──────────────▼──────────────▼──────────────────▼────────┐  │
│  │              Cost Attribution Service                          │  │
│  │  - Tags every API call with: team, feature, model, env       │  │
│  │  - Applies pricing rules (per-token, per-query, per-GPU-sec) │  │
│  │  - Emits cost metrics in real-time                           │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐  │
│  │                    Cost Analytics Engine                       │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │  │
│  │  │ Real-time   │  │  Forecasting │  │  Anomaly Detection │  │  │
│  │  │ Aggregation │  │  (Prophet)   │  │  (Z-score + CUSUM) │  │  │
│  │  └─────────────┘  └──────────────┘  └────────────────────┘  │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐  │
│  │                    Budget & Alerting                           │  │
│  │  - Per-team monthly budgets with burn-rate alerts            │  │
│  │  - Per-feature cost caps with auto-throttling                │  │
│  │  - Forecast-based alerts ("will exceed budget in 5 days")    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading

@dataclass
class CostEvent:
    timestamp: datetime
    model: str
    operation: str          # "inference", "embedding", "rerank"
    team: str
    feature: str
    input_tokens: int = 0
    output_tokens: int = 0
    gpu_seconds: float = 0
    vector_queries: int = 0

# Pricing table (updated when providers change pricing)
PRICING = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "claude-sonnet": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "text-embedding-3-large": {"input": 0.13 / 1_000_000},
    "gpu-a100": {"per_second": 0.0032},  # ~$11.50/hr
}

class CostObservabilitySystem:
    def __init__(self):
        self.cost_buffer: list[CostEvent] = []
        self.hourly_costs: dict[str, float] = defaultdict(float)
        self.budgets: dict[str, float] = {}  # team -> monthly budget
        self.lock = threading.Lock()

    def record_cost(self, event: CostEvent) -> float:
        """Record a cost event and return the computed cost."""
        cost = self._compute_cost(event)

        with self.lock:
            key = f"{event.team}:{event.feature}:{event.model}"
            self.hourly_costs[key] += cost
            self.cost_buffer.append(event)

        # Check for anomalies
        self._check_anomaly(event.team, cost)
        # Check budget
        self._check_budget(event.team, cost)

        # Emit metric
        cost_metric.record(cost, {
            "team": event.team,
            "feature": event.feature,
            "model": event.model,
            "operation": event.operation,
        })
        return cost

    def _compute_cost(self, event: CostEvent) -> float:
        pricing = PRICING.get(event.model, {})
        cost = 0.0
        cost += event.input_tokens * pricing.get("input", 0)
        cost += event.output_tokens * pricing.get("output", 0)
        cost += event.gpu_seconds * pricing.get("per_second", 0)
        cost += event.vector_queries * 0.00001  # $0.01 per 1000 queries
        return cost

    def _check_anomaly(self, team: str, cost: float):
        """CUSUM-based anomaly detection for cost spikes."""
        # Compare current hour's spend rate vs rolling 7-day average
        current_rate = self._get_current_hour_spend(team)
        avg_rate = self._get_7day_hourly_average(team)

        if avg_rate > 0 and current_rate > 2.5 * avg_rate:
            self._fire_alert(
                severity="P2",
                message=f"Cost anomaly: {team} spending ${current_rate:.2f}/hr "
                        f"(avg: ${avg_rate:.2f}/hr, {current_rate/avg_rate:.1f}x normal)",
                team=team
            )

    def get_forecast(self, team: str, days_ahead: int = 30) -> dict:
        """Prophet-based cost forecasting."""
        history = self._get_daily_costs(team, days=90)
        # Fit Prophet model on daily spend
        forecast = self._run_prophet(history, days_ahead)
        budget = self.budgets.get(team, float('inf'))

        days_to_exceed = None
        for i, predicted in enumerate(forecast):
            cumulative = sum(forecast[:i+1])
            if cumulative > budget:
                days_to_exceed = i
                break

        return {
            "predicted_monthly": sum(forecast[:30]),
            "budget": budget,
            "days_to_exceed_budget": days_to_exceed,
            "confidence_interval": self._get_ci(forecast),
        }
```

**Cost Dashboard Breakdown:**

| Dimension | Granularity | Use Case |
|-----------|-------------|----------|
| By model | Per-model | Identify expensive models to replace |
| By feature | Per-feature | Cost-justify features |
| By team | Per-team | Budget accountability |
| By efficiency | Cost-per-query | Optimization tracking |
| By waste | Failed/retried calls | Reduce waste |

**Production Considerations:**
- Buffer cost events and flush every 10s (avoid per-request DB writes)
- Use ClickHouse for cost analytics (fast aggregations over time series)
- Alert on burn rate, not just absolute spend (catches gradual increases)
- Implement cost caps with circuit breakers for runaway loops

---

## Q130: Design a logging architecture for AI systems that balances debugging needs with privacy requirements.

### Answer

**Architecture:**

```
┌───────────────────────────────────────────────────────────────┐
│                  Privacy-Preserving AI Logging                  │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  Request: "My SSN is 123-45-6789, what's my account balance?" │
│                         │                                       │
│  ┌──────────────────────▼──────────────────────────────────┐   │
│  │          PII Detection & Redaction Layer                 │   │
│  │  - Presidio / custom NER for PII detection              │   │
│  │  - Deterministic hashing for correlation                │   │
│  │  - Configurable redaction levels per data class         │   │
│  └──────────────────────┬──────────────────────────────────┘   │
│                         │                                       │
│  Redacted: "My SSN is [PII:SSN:h7k2], what's my account..."  │
│                         │                                       │
│  ┌──────────────────────▼──────────────────────────────────┐   │
│  │              Tiered Logging Storage                       │   │
│  │                                                          │   │
│  │  Tier 1: Full Redacted Logs (Loki, 30 days)            │   │
│  │  - Redacted prompts/responses                           │   │
│  │  - All metadata (latency, tokens, model, trace_id)     │   │
│  │                                                          │   │
│  │  Tier 2: Debug Vault (encrypted, 7 days, access-gated) │   │
│  │  - Original prompts/responses (encrypted at rest)       │   │
│  │  - Requires break-glass approval to access              │   │
│  │  - Auto-purged after TTL                                │   │
│  │                                                          │   │
│  │  Tier 3: Aggregate Analytics (permanent)                │   │
│  │  - Token distributions, latency histograms              │   │
│  │  - Quality scores (no content)                          │   │
│  │  - Error classifications                                │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import hashlib
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from cryptography.fernet import Fernet

class PIIType(Enum):
    SSN = "SSN"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    NAME = "NAME"
    ADDRESS = "ADDRESS"
    CREDIT_CARD = "CC"

class RedactionLevel(Enum):
    FULL = "full"           # Replace with [REDACTED]
    HASHED = "hashed"       # Replace with deterministic hash (allows correlation)
    PARTIAL = "partial"     # Show partial (e.g., ***-**-6789)
    ENCRYPTED = "encrypted" # Encrypt with key (recoverable with approval)

# Per-PII-type redaction policy
REDACTION_POLICY = {
    PIIType.SSN: RedactionLevel.FULL,
    PIIType.EMAIL: RedactionLevel.HASHED,
    PIIType.PHONE: RedactionLevel.HASHED,
    PIIType.NAME: RedactionLevel.HASHED,
    PIIType.CREDIT_CARD: RedactionLevel.FULL,
}

class PrivacyAwareLogger:
    def __init__(self, encryption_key: bytes, salt: str):
        self.fernet = Fernet(encryption_key)
        self.salt = salt
        self.pii_detector = PIIDetector()  # Presidio-based

    def log_ai_interaction(self, request_id: str, prompt: str,
                           response: str, metadata: dict) -> None:
        # Detect PII in both prompt and response
        prompt_pii = self.pii_detector.detect(prompt)
        response_pii = self.pii_detector.detect(response)

        # Create redacted versions for standard logging
        redacted_prompt = self._redact(prompt, prompt_pii)
        redacted_response = self._redact(response, response_pii)

        # Tier 1: Standard operational log (always written)
        self._write_operational_log({
            "request_id": request_id,
            "prompt_redacted": redacted_prompt,
            "response_redacted": redacted_response,
            "pii_types_detected": [p.type.value for p in prompt_pii + response_pii],
            "pii_count": len(prompt_pii) + len(response_pii),
            **metadata,  # latency, tokens, model, trace_id
        })

        # Tier 2: Encrypted debug vault (conditional, short TTL)
        if metadata.get("quality_score", 1.0) < 0.5 or metadata.get("is_error"):
            encrypted_prompt = self.fernet.encrypt(prompt.encode())
            encrypted_response = self.fernet.encrypt(response.encode())
            self._write_debug_vault({
                "request_id": request_id,
                "encrypted_prompt": encrypted_prompt,
                "encrypted_response": encrypted_response,
                "ttl_hours": 168,  # 7 days
                "access_requires": "break-glass-approval",
            })

        # Tier 3: Aggregate metrics (always, no content)
        self._emit_aggregate_metrics(metadata)

    def _redact(self, text: str, pii_entities: list) -> str:
        # Sort by position (reverse) to maintain offsets
        sorted_entities = sorted(pii_entities, key=lambda e: e.start, reverse=True)
        result = text
        for entity in sorted_entities:
            policy = REDACTION_POLICY.get(entity.type, RedactionLevel.FULL)
            replacement = self._get_replacement(entity, policy)
            result = result[:entity.start] + replacement + result[entity.end:]
        return result

    def _get_replacement(self, entity, level: RedactionLevel) -> str:
        if level == RedactionLevel.FULL:
            return f"[{entity.type.value}:REDACTED]"
        elif level == RedactionLevel.HASHED:
            # Deterministic hash allows correlation across logs
            h = hashlib.sha256(f"{self.salt}:{entity.text}".encode()).hexdigest()[:8]
            return f"[{entity.type.value}:{h}]"
        elif level == RedactionLevel.ENCRYPTED:
            enc = self.fernet.encrypt(entity.text.encode()).decode()[:16]
            return f"[{entity.type.value}:ENC:{enc}]"
        return "[REDACTED]"


class BreakGlassAccess:
    """Controlled access to encrypted debug logs."""

    def request_access(self, request_id: str, justification: str,
                       requester: str) -> str:
        """Creates an access request requiring approval."""
        ticket = self._create_approval_ticket(requester, justification, request_id)
        self._notify_approvers(ticket)
        self._audit_log(f"Break-glass requested by {requester} for {request_id}")
        return ticket.id

    def decrypt_log(self, request_id: str, approval_ticket: str) -> dict:
        """Decrypts log after approval verification."""
        if not self._verify_approval(approval_ticket):
            raise PermissionError("Approval not granted or expired")
        self._audit_log(f"Break-glass exercised for {request_id}")
        encrypted = self._fetch_from_vault(request_id)
        return {
            "prompt": self.fernet.decrypt(encrypted["encrypted_prompt"]).decode(),
            "response": self.fernet.decrypt(encrypted["encrypted_response"]).decode(),
        }
```

**Trade-offs:**

| Approach | Debugging Power | Privacy | Cost | Compliance |
|----------|----------------|---------|------|------------|
| Log everything | Excellent | Poor | High | Non-compliant |
| Redact all | Poor | Excellent | Low | Compliant |
| Tiered (our design) | Good | Good | Medium | Compliant |
| Hash-only | Moderate | Good | Low | Compliant |

**Production Considerations:**
- PII detection runs synchronously in the request path (adds ~5ms)
- False negatives in PII detection: use allowlist patterns + ML-based detection
- Deterministic hashing allows correlating the same user across logs without knowing identity
- GDPR right-to-erasure: hash salt rotation makes old hashes unrecoverable
- Retention automation: CronJob purges Tier 2 vault entries past TTL
# Monitoring and Alerting for AI (Questions 131-135)

## Q131: Design an alerting system for AI quality degradation that goes beyond traditional infrastructure metrics.

### Answer

**The Problem:** Traditional monitoring catches CPU/memory/latency issues but misses AI-specific failures like increasing hallucinations, retrieval quality drops, or subtle prompt injection bypasses. These require a fundamentally different alerting approach.

**Architecture:**

```
┌────────────────────────────────────────────────────────────────┐
│                AI Quality Alerting System                        │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── Signal Collection ───────────────────────────────────┐    │
│  │                                                          │    │
│  │  Real-time (100%)        Sampled (5%)      Async (batch)│    │
│  │  - Latency              - LLM-as-judge    - Human eval  │    │
│  │  - Token counts         - Faithfulness    - A/B results │    │
│  │  - Empty retrievals     - Relevance       - Regression  │    │
│  │  - Safety filter hits   - Hallucination   - Drift tests │    │
│  │  - User signals         - Completeness                  │    │
│  └────────────────────────────┬─────────────────────────────┘    │
│                               │                                   │
│  ┌────────────────────────────▼─────────────────────────────┐    │
│  │           Multi-Signal Alert Engine                        │    │
│  │                                                           │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │    │
│  │  │ Threshold   │  │ Statistical  │  │ Composite      │  │    │
│  │  │ Alerts      │  │ Alerts       │  │ Score Alerts   │  │    │
│  │  │ (simple)    │  │ (drift/shift)│  │ (weighted)     │  │    │
│  │  └─────────────┘  └──────────────┘  └────────────────┘  │    │
│  └────────────────────────────┬─────────────────────────────┘    │
│                               │                                   │
│  ┌────────────────────────────▼─────────────────────────────┐    │
│  │           Alert Routing & Suppression                     │    │
│  │  - Deduplication (same root cause)                       │    │
│  │  - Correlation (multiple symptoms → single alert)        │    │
│  │  - Escalation ladder                                     │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

**AI-Specific Alert Definitions:**

```python
from dataclasses import dataclass
from typing import Callable
import numpy as np

@dataclass
class AIAlert:
    name: str
    condition: Callable
    severity: str          # P1, P2, P3
    window: int            # seconds
    min_samples: int       # minimum data points before alerting
    cooldown: int          # seconds between re-fires
    runbook_url: str

# Alert catalog
AI_ALERTS = [
    AIAlert(
        name="hallucination_rate_spike",
        condition=lambda m: m.hallucination_rate > 0.12,
        severity="P1",
        window=300,
        min_samples=50,
        cooldown=900,
        runbook_url="https://runbooks.internal/ai/hallucination-spike",
    ),
    AIAlert(
        name="retrieval_quality_degradation",
        condition=lambda m: m.retrieval_recall_at_10 < 0.55,
        severity="P2",
        window=600,
        min_samples=100,
        cooldown=1800,
        runbook_url="https://runbooks.internal/ai/retrieval-degradation",
    ),
    AIAlert(
        name="faithfulness_drop",
        condition=lambda m: m.faithfulness_score < 0.75 and m.sample_size >= 20,
        severity="P1",
        window=600,
        min_samples=20,
        cooldown=900,
        runbook_url="https://runbooks.internal/ai/faithfulness-drop",
    ),
    AIAlert(
        name="user_satisfaction_decline",
        condition=lambda m: m.thumbs_down_rate > 0.25 and m.volume > 100,
        severity="P2",
        window=1800,
        min_samples=100,
        cooldown=3600,
        runbook_url="https://runbooks.internal/ai/user-satisfaction",
    ),
    AIAlert(
        name="safety_filter_bypass_suspected",
        condition=lambda m: m.safety_block_rate < m.baseline_block_rate * 0.5,
        severity="P1",
        window=300,
        min_samples=200,
        cooldown=600,
        runbook_url="https://runbooks.internal/ai/safety-bypass",
    ),
    AIAlert(
        name="prompt_injection_spike",
        condition=lambda m: m.injection_detection_rate > 0.05,
        severity="P1",
        window=60,
        min_samples=10,
        cooldown=300,
        runbook_url="https://runbooks.internal/ai/prompt-injection",
    ),
]


class CompositeQualityScore:
    """Weighted composite score that detects multi-dimensional degradation."""

    WEIGHTS = {
        "relevance": 0.25,
        "faithfulness": 0.30,
        "safety": 0.25,
        "user_satisfaction": 0.20,
    }

    def compute(self, metrics: dict) -> float:
        score = sum(
            self.WEIGHTS[dim] * metrics.get(dim, 1.0)
            for dim in self.WEIGHTS
        )
        return score

    def check_alert(self, current: float, baseline: float) -> bool:
        """Alert if composite drops >10% from baseline."""
        return current < baseline * 0.90
```

**What to Monitor (Beyond Traditional Metrics):**

| Category | Metric | Why It Matters |
|----------|--------|---------------|
| Hallucination | Claims not in context | Core trust metric |
| Retrieval | Empty result rate | Upstream failure indicator |
| Retrieval | Score distribution shift | Index/embedding issue |
| Safety | Block rate changes | Could indicate bypass or over-blocking |
| User behavior | Regeneration rate | Users rejecting outputs |
| User behavior | Time-to-abandon | Frustration signal |
| Cost | Cost-per-useful-response | Efficiency degradation |
| Prompt | Injection attempt rate | Security threat |

**Production Considerations:**
- Don't alert on single bad responses; use sliding windows with minimum sample sizes
- Correlate alerts: retrieval failure + hallucination spike = likely same root cause
- Separate alert channels: safety → security team, quality → AI team, cost → platform team
- Include actionable context in alert: example bad responses, comparison to baseline, affected segments

---

## Q132: Design a drift detection system that monitors for data drift, concept drift, and model drift in production.

### Answer

**Types of Drift:**

```
┌─────────────────────────────────────────────────────────────┐
│                     Drift Taxonomy                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Data Drift: Input distribution changes                      │
│  - Query topics shift (new product launched)                 │
│  - Query length distribution changes                         │
│  - Language mix changes                                      │
│                                                               │
│  Concept Drift: Relationship between input → output changes  │
│  - "Good answer" definition evolves                          │
│  - User expectations shift                                   │
│  - Ground truth changes (policy updates)                     │
│                                                               │
│  Model Drift: Model behavior degrades over time              │
│  - Embedding model fine-tuning shifts representations        │
│  - LLM provider silent updates                               │
│  - Retrieval index staleness                                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Drift Detection System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─── Reference Window ────┐     ┌─── Current Window ────────┐  │
│  │ Last 7 days of "good"   │     │ Last 1 hour of traffic    │  │
│  │ production data          │     │                           │  │
│  └───────────┬─────────────┘     └───────────┬───────────────┘  │
│              │                                │                   │
│  ┌───────────▼────────────────────────────────▼───────────────┐  │
│  │              Statistical Test Battery                       │  │
│  │                                                            │  │
│  │  Numeric:  KS-test, Wasserstein distance, PSI             │  │
│  │  Categorical: Chi-squared, Jensen-Shannon divergence      │  │
│  │  Embeddings: MMD (Maximum Mean Discrepancy)               │  │
│  │  Text: Topic distribution shift (LDA/BERTopic)            │  │
│  └───────────────────────────┬────────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │              Decision Engine                                │  │
│  │  - Severity scoring (how much drift?)                     │  │
│  │  - Impact estimation (does drift affect quality?)         │  │
│  │  - Automated vs manual remediation decision               │  │
│  └───────────────────────────┬────────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │              Remediation Actions                            │  │
│  │  - Alert team (low severity)                              │  │
│  │  - Trigger re-indexing (document drift)                   │  │
│  │  - Trigger model re-evaluation (model drift)             │  │
│  │  - Auto-rollback (severe quality impact)                  │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import numpy as np
from scipy import stats
from sklearn.metrics import pairwise_distances
from dataclasses import dataclass
from typing import Literal

@dataclass
class DriftResult:
    drift_type: Literal["data", "concept", "model"]
    dimension: str
    statistic: float
    p_value: float
    severity: Literal["none", "low", "medium", "high"]
    recommendation: str

class DriftDetector:
    def __init__(self, reference_window_days: int = 7):
        self.reference_window_days = reference_window_days
        self.thresholds = {
            "low": 0.05,      # p-value below this = low drift
            "medium": 0.01,
            "high": 0.001,
        }

    def detect_data_drift(self, reference: np.ndarray, current: np.ndarray,
                          feature_name: str) -> DriftResult:
        """KS-test for continuous features, PSI for distributions."""
        # Kolmogorov-Smirnov test
        ks_stat, p_value = stats.ks_2samp(reference, current)

        # Population Stability Index
        psi = self._compute_psi(reference, current, bins=20)

        severity = self._classify_severity(p_value, psi)

        return DriftResult(
            drift_type="data",
            dimension=feature_name,
            statistic=ks_stat,
            p_value=p_value,
            severity=severity,
            recommendation=self._get_recommendation("data", severity, feature_name),
        )

    def detect_embedding_drift(self, ref_embeddings: np.ndarray,
                                curr_embeddings: np.ndarray) -> DriftResult:
        """MMD test for high-dimensional embedding distributions."""
        # Maximum Mean Discrepancy with RBF kernel
        mmd = self._compute_mmd(ref_embeddings, curr_embeddings)

        # Permutation test for significance
        p_value = self._permutation_test_mmd(ref_embeddings, curr_embeddings,
                                              n_permutations=1000)

        # Also check centroid shift
        ref_centroid = ref_embeddings.mean(axis=0)
        curr_centroid = curr_embeddings.mean(axis=0)
        centroid_distance = np.linalg.norm(ref_centroid - curr_centroid)

        severity = "high" if p_value < 0.001 else "medium" if p_value < 0.01 else "low" if p_value < 0.05 else "none"

        return DriftResult(
            drift_type="model",
            dimension="embedding_space",
            statistic=mmd,
            p_value=p_value,
            severity=severity,
            recommendation=f"Embedding space shifted (centroid dist={centroid_distance:.4f}). "
                          f"Check embedding model version, verify retrieval quality.",
        )

    def detect_concept_drift(self, ref_queries: list, ref_quality: list,
                             curr_queries: list, curr_quality: list) -> DriftResult:
        """Detect when same query types get different quality scores."""
        # Cluster queries into topics
        ref_topic_quality = self._quality_by_topic(ref_queries, ref_quality)
        curr_topic_quality = self._quality_by_topic(curr_queries, curr_quality)

        # Compare quality distributions per topic
        max_drift_topic = None
        max_drift_stat = 0
        for topic in ref_topic_quality:
            if topic in curr_topic_quality:
                stat, p = stats.mannwhitneyu(
                    ref_topic_quality[topic], curr_topic_quality[topic])
                if stat > max_drift_stat:
                    max_drift_stat = stat
                    max_drift_topic = topic

        return DriftResult(
            drift_type="concept",
            dimension=f"topic:{max_drift_topic}",
            statistic=max_drift_stat,
            p_value=p,
            severity=self._classify_severity(p, max_drift_stat),
            recommendation=f"Quality changed for topic '{max_drift_topic}'. "
                          f"Check if ground truth/expectations shifted.",
        )

    def _compute_psi(self, reference: np.ndarray, current: np.ndarray,
                     bins: int = 20) -> float:
        """Population Stability Index."""
        ref_hist, bin_edges = np.histogram(reference, bins=bins, density=True)
        curr_hist, _ = np.histogram(current, bins=bin_edges, density=True)

        # Avoid division by zero
        ref_hist = np.clip(ref_hist, 0.001, None)
        curr_hist = np.clip(curr_hist, 0.001, None)

        psi = np.sum((curr_hist - ref_hist) * np.log(curr_hist / ref_hist))
        return psi

    def _compute_mmd(self, X: np.ndarray, Y: np.ndarray,
                     gamma: float = 1.0) -> float:
        """Maximum Mean Discrepancy with RBF kernel."""
        XX = np.exp(-gamma * pairwise_distances(X, X, metric='sqeuclidean'))
        YY = np.exp(-gamma * pairwise_distances(Y, Y, metric='sqeuclidean'))
        XY = np.exp(-gamma * pairwise_distances(X, Y, metric='sqeuclidean'))
        return XX.mean() + YY.mean() - 2 * XY.mean()
```

**Automated Remediation Matrix:**

| Drift Type | Severity | Automated Action |
|-----------|----------|-----------------|
| Data drift (query distribution) | Low | Log, no action |
| Data drift (query distribution) | High | Alert team, increase monitoring |
| Embedding drift | Medium | Trigger retrieval eval suite |
| Embedding drift | High | Rollback embedding model, page team |
| Concept drift | Any | Alert, cannot auto-remediate (needs human judgment) |
| Model drift (LLM quality) | High | Switch to backup model, page team |

**Production Considerations:**
- Run drift detection every 15 minutes on sliding windows
- Use reference windows that exclude known anomaly periods
- Account for natural seasonality (weekday vs weekend traffic patterns)
- Drift ≠ degradation: validate that detected drift actually impacts quality before alerting

---

## Q133: Design an SLO framework for AI systems. What SLIs are meaningful for LLM applications?

### Answer

**SLI/SLO Framework for AI:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI System SLO Framework                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─── Availability SLIs ───────────────────────────────────────┐ │
│  │ • Request success rate (non-5xx)                   99.9%    │ │
│  │ • Meaningful response rate (non-empty, non-error)  99.5%    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─── Latency SLIs ───────────────────────────────────────────┐  │
│  │ • Time to first token (streaming)       P50<500ms, P99<2s  │  │
│  │ • End-to-end response time              P50<2s, P99<8s     │  │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─── Quality SLIs (AI-specific) ─────────────────────────────┐  │
│  │ • Relevance score (sampled LLM-judge)              ≥ 0.85  │  │
│  │ • Faithfulness score (grounded in sources)         ≥ 0.90  │  │
│  │ • Hallucination rate                               ≤ 0.08  │  │
│  │ • Safety pass rate                                 ≥ 0.998 │  │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─── Freshness SLIs ─────────────────────────────────────────┐  │
│  │ • Document index lag (time since source update)    < 4hrs   │  │
│  │ • Stale response rate (answer from outdated doc)   ≤ 0.05  │  │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Error Budget: 100% - SLO target (e.g., 0.5% for 99.5% SLO)   │
│  Burn Rate Alert: error_budget consumed at >14.4x normal rate    │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

@dataclass
class SLI:
    name: str
    description: str
    good_event_query: str       # PromQL/query that counts good events
    total_event_query: str      # PromQL/query that counts total events
    unit: str                   # "ratio", "milliseconds", "score"

@dataclass
class SLO:
    sli: SLI
    target: float              # e.g., 0.995 for 99.5%
    window: timedelta          # rolling window (e.g., 30 days)
    burn_rate_alerts: list     # multi-window burn rate configs

# Define AI-specific SLIs
QUALITY_SLI = SLI(
    name="ai_response_quality",
    description="Fraction of responses that meet quality bar (relevance >= 0.7 AND faithfulness >= 0.8)",
    good_event_query='count(ai_quality_score{relevance >= 0.7, faithfulness >= 0.8})',
    total_event_query='count(ai_quality_score)',
    unit="ratio",
)

HALLUCINATION_SLI = SLI(
    name="hallucination_free_rate",
    description="Fraction of responses without detected hallucinations",
    good_event_query='count(ai_hallucination_score < 0.3)',
    total_event_query='count(ai_hallucination_score)',
    unit="ratio",
)

SAFETY_SLI = SLI(
    name="safety_compliance",
    description="Fraction of responses passing all safety checks",
    good_event_query='count(safety_check_result == "pass")',
    total_event_query='count(safety_check_result)',
    unit="ratio",
)

# SLO definitions
AI_SLOS = [
    SLO(
        sli=QUALITY_SLI,
        target=0.85,
        window=timedelta(days=30),
        burn_rate_alerts=[
            {"severity": "P1", "long_window": "1h", "short_window": "5m", "burn_rate": 14.4},
            {"severity": "P2", "long_window": "6h", "short_window": "30m", "burn_rate": 6.0},
            {"severity": "P3", "long_window": "3d", "short_window": "6h", "burn_rate": 1.0},
        ],
    ),
    SLO(
        sli=HALLUCINATION_SLI,
        target=0.92,
        window=timedelta(days=30),
        burn_rate_alerts=[
            {"severity": "P1", "long_window": "30m", "short_window": "5m", "burn_rate": 14.4},
            {"severity": "P2", "long_window": "3h", "short_window": "15m", "burn_rate": 6.0},
        ],
    ),
    SLO(
        sli=SAFETY_SLI,
        target=0.998,
        window=timedelta(days=30),
        burn_rate_alerts=[
            {"severity": "P1", "long_window": "5m", "short_window": "1m", "burn_rate": 14.4},
        ],
    ),
]


class SLOCalculator:
    """Compute SLO status and error budget."""

    def compute_error_budget(self, slo: SLO, good_events: int,
                             total_events: int) -> dict:
        if total_events == 0:
            return {"status": "insufficient_data"}

        current_ratio = good_events / total_events
        error_budget_total = 1.0 - slo.target          # e.g., 0.15 for 85% target
        error_budget_consumed = (1.0 - current_ratio)  # actual error rate
        budget_remaining = 1.0 - (error_budget_consumed / error_budget_total)

        return {
            "slo_name": slo.sli.name,
            "target": slo.target,
            "current": current_ratio,
            "meeting_slo": current_ratio >= slo.target,
            "error_budget_total": error_budget_total,
            "error_budget_remaining_pct": max(0, budget_remaining * 100),
            "burn_rate": error_budget_consumed / error_budget_total * (
                slo.window.total_seconds() / self._elapsed_seconds()),
        }
```

**Measuring "AI Quality" as an SLI - The Hard Problem:**

| Approach | Latency | Accuracy | Cost | Coverage |
|----------|---------|----------|------|----------|
| LLM-as-judge (sampled) | 2-5s | ~85% correlation with human | High | 5-10% |
| Lightweight classifier | <50ms | ~70% correlation | Low | 100% |
| User feedback proxy | 0ms | Noisy, biased | Free | ~5% response rate |
| Hybrid (classifier + sampled judge) | Mixed | ~80% | Medium | 100% |

**Recommended approach:** Use lightweight classifier on 100% of traffic for SLI computation, validate with LLM-as-judge on 5% sample, calibrate classifier weekly against human labels.

**Production Considerations:**
- Error budgets drive release velocity: depleted budget = freeze non-critical changes
- Quality SLIs have inherent measurement noise; use confidence intervals
- Different SLO targets per tier: enterprise customers get tighter SLOs
- Review and recalibrate SLO targets quarterly based on user expectations

---

## Q134: Design a feedback-driven monitoring system where user signals feed into real-time quality scores.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Feedback-Driven Quality Monitoring                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─── User Signal Collection ──────────────────────────────────┐ │
│  │                                                              │ │
│  │  Explicit              Implicit              Behavioral      │ │
│  │  • Thumbs up/down     • Copy response       • Session len   │ │
│  │  • Star rating        • Share response      • Return rate   │ │
│  │  • Text correction    • Click citations     • Abandon rate  │ │
│  │  • "Not helpful" btn  • Follow-up queries   • Regenerate    │ │
│  │  • Report harmful     • Time on response    • Edit query    │ │
│  └──────────────────────────────┬───────────────────────────────┘ │
│                                 │                                  │
│  ┌──────────────────────────────▼───────────────────────────────┐ │
│  │          Signal Processing Pipeline                           │ │
│  │                                                               │ │
│  │  1. Debounce & Deduplicate (same user, same response)        │ │
│  │  2. Weight by signal reliability:                             │ │
│  │     - Explicit rating: weight 1.0                            │ │
│  │     - Correction: weight 1.2 (high signal)                   │ │
│  │     - Copy: weight 0.3 (noisy positive)                      │ │
│  │     - Regeneration: weight 0.7 (clear negative)              │ │
│  │  3. Bias correction (negativity bias, power users)           │ │
│  │  4. Segment attribution (by feature, model, query type)      │ │
│  └──────────────────────────────┬───────────────────────────────┘ │
│                                 │                                  │
│  ┌──────────────────────────────▼───────────────────────────────┐ │
│  │          Real-time Quality Score Engine                        │ │
│  │                                                               │ │
│  │  Bayesian rolling average with decay:                         │ │
│  │  score_t = α * new_signal + (1-α) * score_{t-1}             │ │
│  │                                                               │ │
│  │  Per-segment scores:                                          │ │
│  │  - Global quality: 0.84                                      │ │
│  │  - Search feature: 0.89                                      │ │
│  │  - Chat feature: 0.78 ⚠                                     │ │
│  │  - GPT-4o model: 0.87                                       │ │
│  │  - Enterprise tier: 0.91                                      │ │
│  └──────────────────────────────┬───────────────────────────────┘ │
│                                 │                                  │
│  ┌──────────────────────────────▼───────────────────────────────┐ │
│  │          Alert Triggers                                       │ │
│  │  • Score drops below threshold for segment                    │ │
│  │  • Rate-of-change exceeds 5% per hour                        │ │
│  │  • Negative feedback volume spike (>3σ)                      │ │
│  │  • Correction rate spikes (factual accuracy issue)           │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Literal
import numpy as np

@dataclass
class FeedbackEvent:
    timestamp: float
    request_id: str
    user_id: str
    signal_type: Literal["thumbs_up", "thumbs_down", "copy", "regenerate",
                         "correction", "abandon", "share", "report"]
    metadata: dict = field(default_factory=dict)

SIGNAL_WEIGHTS = {
    "thumbs_up": (1.0, 1.0),      # (value, confidence)
    "thumbs_down": (0.0, 1.0),
    "correction": (0.0, 1.2),      # Corrections are high-confidence negative
    "copy": (0.8, 0.3),            # Copying is weak positive
    "share": (0.9, 0.5),
    "regenerate": (0.2, 0.7),      # Regeneration is moderate negative
    "abandon": (0.3, 0.4),         # Session abandonment is weak negative
    "report": (0.0, 1.5),          # Reporting is very high-confidence negative
}


class FeedbackQualityEngine:
    def __init__(self, decay_alpha: float = 0.05, min_signals: int = 20):
        self.decay_alpha = decay_alpha
        self.min_signals = min_signals
        self.segment_scores: dict[str, float] = defaultdict(lambda: 0.85)  # prior
        self.signal_buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alert_thresholds: dict[str, float] = {}

    def ingest_feedback(self, event: FeedbackEvent, segments: list[str]):
        """Process a feedback event and update quality scores."""
        value, confidence = SIGNAL_WEIGHTS[event.signal_type]

        # Bias correction: adjust for negativity bias
        # (users are 3x more likely to give negative feedback)
        if value < 0.5:
            confidence *= 0.6  # Reduce weight of negative to account for bias

        for segment in segments:
            self.signal_buffers[segment].append((time.time(), value, confidence))
            self._update_score(segment)

    def _update_score(self, segment: str):
        """Exponentially weighted moving average with confidence."""
        buffer = self.signal_buffers[segment]
        if len(buffer) < self.min_signals:
            return  # Not enough data

        # Time-weighted: recent signals matter more
        now = time.time()
        weighted_sum = 0.0
        weight_total = 0.0

        for ts, value, confidence in buffer:
            age_hours = (now - ts) / 3600
            time_weight = np.exp(-0.1 * age_hours)  # Half-life ~7 hours
            w = confidence * time_weight
            weighted_sum += value * w
            weight_total += w

        if weight_total > 0:
            new_score = weighted_sum / weight_total
            # Smooth update
            self.segment_scores[segment] = (
                self.decay_alpha * new_score +
                (1 - self.decay_alpha) * self.segment_scores[segment]
            )

    def check_alerts(self) -> list[dict]:
        """Check all segments for quality degradation."""
        alerts = []
        for segment, score in self.segment_scores.items():
            threshold = self.alert_thresholds.get(segment, 0.70)
            if score < threshold:
                alerts.append({
                    "segment": segment,
                    "score": score,
                    "threshold": threshold,
                    "signal_count": len(self.signal_buffers[segment]),
                    "severity": "P1" if score < threshold * 0.8 else "P2",
                })
        return alerts

    def get_dashboard_data(self) -> dict:
        return {
            "global_score": self.segment_scores.get("global", 0.85),
            "segments": dict(self.segment_scores),
            "alert_count": len(self.check_alerts()),
            "signal_volume_per_hour": self._get_signal_rate(),
        }
```

**Handling Feedback Challenges:**

| Challenge | Solution |
|-----------|----------|
| Low feedback rate (~2-5% of users give explicit feedback) | Use implicit signals (copy, regenerate) to boost coverage |
| Negativity bias | Apply bias correction multipliers |
| Power user skew | Cap per-user signal influence per time window |
| Delayed feedback | Use time-decay weighting; stale signals lose influence |
| Feedback on wrong dimension | Map signal types to quality dimensions (safety vs relevance) |

**Production Considerations:**
- Store feedback with request_id to correlate with traces and retrieval quality
- A/B test signal weights: validate that score changes correlate with offline eval
- Cold start: new features start with prior=0.85, require min 50 signals before alerting
- Feedback loop risk: don't use feedback scores to directly rank/filter without human review

---

## Q135: Design a canary deployment monitoring system for AI model updates.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────────┐
│                  AI Canary Deployment System                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Traffic Splitting ────────────────────────────────────────┐   │
│  │                                                               │   │
│  │  Load Balancer (Envoy/Istio)                                 │   │
│  │  ┌─────────────────────────────────────────────────────────┐ │   │
│  │  │  Canary: 5% ──→ [New Model v2.1]                       │ │   │
│  │  │  Baseline: 5% ──→ [Current Model v2.0 (isolated)]      │ │   │
│  │  │  Production: 90% ──→ [Current Model v2.0]              │ │   │
│  │  └─────────────────────────────────────────────────────────┘ │   │
│  │  (Baseline = same version as prod, separate instance for     │   │
│  │   fair comparison with identical traffic shape)               │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─── Metric Collection ────────────────────────────────────────┐   │
│  │                                                               │   │
│  │  Traditional:           AI-Specific:                         │   │
│  │  • Error rate           • Hallucination rate                 │   │
│  │  • Latency P50/P99     • Faithfulness score                 │   │
│  │  • Throughput           • Relevance score                    │   │
│  │  • Memory/CPU           • Safety block rate                  │   │
│  │                         • User satisfaction proxy            │   │
│  │                         • Retrieval quality (if changed)     │   │
│  │                         • Token efficiency                   │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─── Analysis Engine ──────────────────────────────────────────┐   │
│  │                                                               │   │
│  │  Canary vs Baseline comparison (not canary vs production!)   │   │
│  │                                                               │   │
│  │  Statistical tests:                                          │   │
│  │  • Mann-Whitney U for latency distributions                 │   │
│  │  • Chi-squared for error rates                              │   │
│  │  • Bayesian A/B for quality scores                          │   │
│  │  • Sequential testing (early stopping)                      │   │
│  │                                                               │   │
│  │  Minimum sample sizes before decision:                       │   │
│  │  • Traditional metrics: 1000 requests                       │   │
│  │  • Quality metrics: 200 scored responses                    │   │
│  │  • Safety metrics: 5000 requests (rare events)              │   │
│  └───────────────────────────┬───────────────────────────────────┘   │
│                              │                                        │
│  ┌───────────────────────────▼───────────────────────────────────┐   │
│  │              Decision Automation                               │   │
│  │                                                               │   │
│  │  AUTO-ROLLBACK if:                                           │   │
│  │  • Error rate > baseline + 2% (absolute)                    │   │
│  │  • Safety violations > 0 (zero-tolerance)                   │   │
│  │  • Hallucination rate > baseline + 5%                       │   │
│  │  • Latency P99 > baseline * 1.5                            │   │
│  │                                                               │   │
│  │  PROMOTE if (after min observation period):                  │   │
│  │  • All metrics within acceptable bounds                     │   │
│  │  • Quality score >= baseline (95% CI)                       │   │
│  │  • Safety metrics unchanged                                 │   │
│  │                                                               │   │
│  │  HOLD for human review if:                                   │   │
│  │  • Quality improved but latency degraded                    │   │
│  │  • Inconclusive results (insufficient power)               │   │
│  │  • Mixed signals across dimensions                          │   │
│  └───────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from enum import Enum
from scipy import stats
import numpy as np
from typing import Optional

class CanaryDecision(Enum):
    PROMOTE = "promote"
    ROLLBACK = "rollback"
    HOLD = "hold"
    INSUFFICIENT_DATA = "insufficient_data"

@dataclass
class CanaryMetrics:
    error_rate: float
    latency_p50: float
    latency_p99: float
    quality_score: float
    hallucination_rate: float
    safety_violations: int
    faithfulness_score: float
    sample_size: int

@dataclass
class CanaryConfig:
    min_samples_traditional: int = 1000
    min_samples_quality: int = 200
    min_duration_minutes: int = 30
    max_duration_hours: int = 24
    traffic_pct: float = 0.05

    # Rollback thresholds (absolute or relative)
    max_error_rate_increase: float = 0.02
    max_latency_p99_ratio: float = 1.5
    max_hallucination_increase: float = 0.05
    zero_tolerance_safety: bool = True

    # Promotion thresholds
    quality_non_inferiority_margin: float = 0.02  # Allow up to 2% worse


class CanaryAnalyzer:
    def __init__(self, config: CanaryConfig):
        self.config = config

    def analyze(self, canary: CanaryMetrics, baseline: CanaryMetrics) -> dict:
        """Compare canary vs baseline and make a decision."""

        # Check minimum data requirements
        if canary.sample_size < self.config.min_samples_traditional:
            return {"decision": CanaryDecision.INSUFFICIENT_DATA,
                    "reason": f"Need {self.config.min_samples_traditional} samples, have {canary.sample_size}"}

        # === ROLLBACK CHECKS (any failure = immediate rollback) ===

        # Safety: zero tolerance
        if self.config.zero_tolerance_safety and canary.safety_violations > 0:
            return {"decision": CanaryDecision.ROLLBACK,
                    "reason": f"Safety violations detected: {canary.safety_violations}",
                    "severity": "P1"}

        # Error rate
        error_increase = canary.error_rate - baseline.error_rate
        if error_increase > self.config.max_error_rate_increase:
            return {"decision": CanaryDecision.ROLLBACK,
                    "reason": f"Error rate increased by {error_increase:.3f}"}

        # Latency
        if canary.latency_p99 > baseline.latency_p99 * self.config.max_latency_p99_ratio:
            return {"decision": CanaryDecision.ROLLBACK,
                    "reason": f"P99 latency {canary.latency_p99:.0f}ms vs baseline {baseline.latency_p99:.0f}ms"}

        # Hallucination rate
        hallucination_increase = canary.hallucination_rate - baseline.hallucination_rate
        if hallucination_increase > self.config.max_hallucination_increase:
            return {"decision": CanaryDecision.ROLLBACK,
                    "reason": f"Hallucination rate increased by {hallucination_increase:.3f}"}

        # === QUALITY ANALYSIS (statistical) ===
        if canary.sample_size >= self.config.min_samples_quality:
            # Non-inferiority test: is canary quality >= baseline - margin?
            quality_diff = canary.quality_score - baseline.quality_score
            margin = self.config.quality_non_inferiority_margin

            if quality_diff < -margin:
                return {"decision": CanaryDecision.ROLLBACK,
                        "reason": f"Quality degraded: {quality_diff:.3f} beyond margin {margin}"}

            if quality_diff >= 0:
                # All checks passed and quality is non-inferior
                return {"decision": CanaryDecision.PROMOTE,
                        "reason": "All metrics within bounds, quality non-inferior",
                        "quality_improvement": quality_diff}

        # Inconclusive
        return {"decision": CanaryDecision.HOLD,
                "reason": "Metrics acceptable but quality comparison inconclusive"}

    def progressive_rollout(self, current_pct: float, decision: CanaryDecision) -> float:
        """Determine next traffic percentage."""
        if decision == CanaryDecision.ROLLBACK:
            return 0.0
        elif decision == CanaryDecision.PROMOTE:
            stages = [0.05, 0.10, 0.25, 0.50, 1.00]
            for stage in stages:
                if stage > current_pct:
                    return stage
            return 1.00
        return current_pct  # HOLD = no change
```

**AI-Specific Canary Challenges:**

| Challenge | Solution |
|-----------|----------|
| Quality metrics are slow to compute | Run LLM-judge in parallel; extend canary duration |
| Non-deterministic outputs | Compare distributions, not individual responses |
| Same query → different answer ≠ regression | Use semantic similarity, not exact match |
| Safety events are rare | Require longer observation + synthetic safety probes |
| LLM provider updates are invisible | Always maintain baseline comparison group |

**Progressive Rollout Timeline:**
1. **0-30min:** 5% traffic, collect traditional metrics
2. **30min-2hr:** If traditional metrics pass, begin quality evaluation
3. **2-6hr:** Statistical significance reached on quality metrics
4. **6hr:** Promote to 25% if all pass
5. **12hr:** Promote to 50%
6. **24hr:** Full rollout

**Production Considerations:**
- Always compare canary vs **baseline** (not vs historical), isolating the model change
- Inject synthetic safety test queries into canary traffic for faster safety signal
- Log every canary response for post-hoc analysis even after promotion
- Maintain rollback capability for 48hrs after full promotion (shadow baseline)
# Debugging AI Systems in Production (Questions 136-140)

## Q136: A user reports "the AI gave me wrong information." Design a systematic debugging workflow for production RAG systems.

### Answer

**Debugging Workflow:**

```
┌────────────────────────────────────────────────────────────────┐
│          RAG Wrong Answer Debugging Workflow                     │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Report: "AI said X, but correct answer is Y"             │
│                         │                                        │
│  Step 1: ──────────────▼──────────────────────────────────────  │
│  │ Retrieve the trace (request_id → distributed trace)         │ │
│  │ Get: query, retrieved docs, prompt, raw LLM response        │ │
│                         │                                        │
│  Step 2: ──────────────▼──────────────────────────────────────  │
│  │ Classify the failure mode:                                   │ │
│  │                                                              │ │
│  │  A) Retrieval failure → correct doc not retrieved           │ │
│  │  B) Ranking failure → correct doc retrieved but ranked low  │ │
│  │  C) Generation failure → correct context, wrong answer      │ │
│  │  D) Staleness → answer was correct when doc was written     │ │
│  │  E) Ambiguity → multiple valid answers, chose wrong one    │ │
│                         │                                        │
│  Step 3: ──────────────▼──────────────────────────────────────  │
│  │ Root cause by failure mode (see below)                      │ │
│                         │                                        │
│  Step 4: ──────────────▼──────────────────────────────────────  │
│  │ Fix, validate on regression set, deploy                     │ │
└────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class FailureMode(Enum):
    RETRIEVAL_MISS = "retrieval_miss"        # Correct doc not in index or not retrieved
    RANKING_FAILURE = "ranking_failure"      # Doc retrieved but ranked too low
    GENERATION_ERROR = "generation_error"    # Good context, bad generation
    STALE_DATA = "stale_data"               # Doc outdated
    AMBIGUITY = "ambiguity"                 # Multiple valid answers
    PROMPT_ISSUE = "prompt_issue"           # Prompt template causing misinterpretation
    CONTEXT_OVERFLOW = "context_overflow"   # Too much context, buried the answer

@dataclass
class DebugReport:
    request_id: str
    failure_mode: FailureMode
    root_cause: str
    evidence: dict
    fix_recommendation: str
    severity: str


class RAGDebugger:
    """Systematic debugging for RAG wrong answers."""

    def __init__(self, trace_store, vector_store, llm_client):
        self.trace_store = trace_store
        self.vector_store = vector_store
        self.llm = llm_client

    async def debug_wrong_answer(self, request_id: str,
                                  correct_answer: str) -> DebugReport:
        # Step 1: Retrieve full trace
        trace = await self.trace_store.get_trace(request_id)
        query = trace.query
        retrieved_docs = trace.retrieved_documents
        prompt = trace.full_prompt
        llm_response = trace.llm_response
        reranked_docs = trace.reranked_documents

        # Step 2: Classify failure mode
        failure_mode = await self._classify_failure(
            query, correct_answer, retrieved_docs, reranked_docs, llm_response)

        # Step 3: Deep dive based on mode
        if failure_mode == FailureMode.RETRIEVAL_MISS:
            evidence = await self._debug_retrieval_miss(query, correct_answer)
        elif failure_mode == FailureMode.RANKING_FAILURE:
            evidence = await self._debug_ranking_failure(query, retrieved_docs, correct_answer)
        elif failure_mode == FailureMode.GENERATION_ERROR:
            evidence = await self._debug_generation(prompt, reranked_docs, llm_response, correct_answer)
        elif failure_mode == FailureMode.STALE_DATA:
            evidence = await self._debug_staleness(retrieved_docs)
        else:
            evidence = {"raw_trace": trace}

        return DebugReport(
            request_id=request_id,
            failure_mode=failure_mode,
            root_cause=evidence.get("root_cause", "Unknown"),
            evidence=evidence,
            fix_recommendation=self._get_fix(failure_mode, evidence),
            severity=self._assess_severity(failure_mode),
        )

    async def _classify_failure(self, query, correct_answer, retrieved_docs,
                                 reranked_docs, llm_response) -> FailureMode:
        """Determine which stage failed."""

        # Check if any retrieved doc contains the correct answer
        correct_doc = await self._find_doc_with_answer(correct_answer)

        if correct_doc is None:
            # Document doesn't exist in index at all
            return FailureMode.RETRIEVAL_MISS

        doc_in_retrieved = any(d.id == correct_doc.id for d in retrieved_docs)
        doc_in_top_k = any(d.id == correct_doc.id for d in reranked_docs[:5])

        if not doc_in_retrieved:
            return FailureMode.RETRIEVAL_MISS
        elif not doc_in_top_k:
            return FailureMode.RANKING_FAILURE
        else:
            # Doc was in context but LLM still got it wrong
            if await self._is_doc_stale(correct_doc):
                return FailureMode.STALE_DATA
            return FailureMode.GENERATION_ERROR

    async def _debug_retrieval_miss(self, query: str, correct_answer: str) -> dict:
        """Why wasn't the correct document retrieved?"""
        correct_doc = await self._find_doc_with_answer(correct_answer)

        if correct_doc is None:
            return {"root_cause": "Document not in index",
                    "fix": "Add document to ingestion pipeline"}

        # Check embedding similarity
        query_embedding = await self.vector_store.embed(query)
        doc_embedding = correct_doc.embedding
        similarity = self._cosine_similarity(query_embedding, doc_embedding)

        # Check if doc would have been retrieved with different top_k
        all_results = await self.vector_store.search(query, top_k=100)
        doc_rank = next((i for i, r in enumerate(all_results) if r.id == correct_doc.id), -1)

        return {
            "root_cause": f"Document exists but ranked {doc_rank} (similarity={similarity:.3f})",
            "similarity_score": similarity,
            "actual_rank": doc_rank,
            "top_k_used": 10,
            "fix": "Improve chunking strategy or add query expansion" if similarity < 0.7
                   else "Increase top_k or add metadata filtering",
        }

    async def _debug_generation(self, prompt, context_docs, response, correct) -> dict:
        """LLM had the right context but generated wrong answer."""
        # Check if correct info is buried in long context
        correct_doc_position = self._find_answer_position_in_prompt(prompt, correct)

        # Test with just the relevant doc
        minimal_prompt = self._build_minimal_prompt(context_docs[0], prompt)
        minimal_response = await self.llm.generate(minimal_prompt)

        return {
            "root_cause": "Generation error - LLM failed to use correct context",
            "correct_info_position": correct_doc_position,
            "context_length_tokens": self._count_tokens(prompt),
            "minimal_prompt_correct": correct in minimal_response,
            "likely_cause": "lost-in-the-middle" if correct_doc_position > 0.7
                           else "instruction following failure",
            "fix": "Reorder context or reduce context window" if correct_doc_position > 0.7
                   else "Improve prompt template with explicit extraction instructions",
        }
```

**Debugging Decision Tree:**

| Symptom | First Check | Likely Cause | Fix |
|---------|------------|--------------|-----|
| Wrong facts | Check retrieved docs | Retrieval miss | Improve embeddings/chunking |
| Outdated answer | Check doc timestamps | Stale index | Trigger re-ingestion |
| Contradicts source | Check context position | Lost-in-middle | Reorder/reduce context |
| Partially correct | Check context count | Context overflow | Better reranking |
| Hallucinated details | Check if details in any doc | Generation hallucination | Add citation requirement |

**Production Considerations:**
- Store full trace data for 7 days (encrypted) to enable debugging
- Build a "debug replay" UI that shows each pipeline stage side-by-side
- Track failure mode distribution over time (shift from retrieval to generation = progress)
- Create regression test from every debugged incident

---

## Q137: Design a replay and reproduction system for AI bugs given the non-deterministic nature of LLMs.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────┐
│              AI Bug Replay & Reproduction System                 │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── Capture Layer (Production) ──────────────────────────┐    │
│  │                                                          │    │
│  │  For every request, store:                               │    │
│  │  • Full prompt (after template rendering)               │    │
│  │  • Model + parameters (temp, top_p, seed)               │    │
│  │  • Retrieved documents (IDs + content hash)             │    │
│  │  • Embedding model version                              │    │
│  │  • Raw LLM response                                     │    │
│  │  • Safety filter inputs/outputs                         │    │
│  │  • Timestamp + system state snapshot                    │    │
│  └──────────────────────────┬───────────────────────────────┘    │
│                             │                                     │
│  ┌──────────────────────────▼───────────────────────────────┐    │
│  │              Replay Engine                                 │    │
│  │                                                           │    │
│  │  Mode 1: Exact Replay (deterministic where possible)     │    │
│  │  - Use stored seed + temperature=0                       │    │
│  │  - Pin model version (if provider supports)              │    │
│  │  - Use captured retrieved docs (skip live retrieval)     │    │
│  │                                                           │    │
│  │  Mode 2: Component Replay (isolate one stage)            │    │
│  │  - Replay just retrieval with stored query               │    │
│  │  - Replay just generation with stored context            │    │
│  │  - Replay just safety with stored response               │    │
│  │                                                           │    │
│  │  Mode 3: Statistical Replay (handle non-determinism)     │    │
│  │  - Run same prompt N times (N=20)                        │    │
│  │  - Measure: does the bug reproduce >50% of the time?    │    │
│  │  - Characterize the distribution of outputs              │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              Reproduction Report                           │    │
│  │                                                           │    │
│  │  • Reproduction rate: X/20 attempts showed the bug       │    │
│  │  • Isolated to stage: [retrieval | generation | safety]  │    │
│  │  • Minimum reproduction case (shortest prompt that bugs) │    │
│  │  • Sensitivity analysis (what changes fix it?)           │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import json
import hashlib
from dataclasses import dataclass, field
from typing import Optional
import asyncio

@dataclass
class CapturedRequest:
    request_id: str
    timestamp: float
    query: str
    full_prompt: str
    model: str
    model_params: dict           # temperature, top_p, max_tokens, seed
    retrieved_doc_ids: list[str]
    retrieved_doc_hashes: list[str]  # Content hashes for change detection
    raw_response: str
    embedding_model_version: str
    system_state: dict           # Feature flags, config versions

@dataclass
class ReplayResult:
    original_response: str
    replayed_responses: list[str]
    reproduction_rate: float
    isolated_stage: Optional[str]
    minimum_repro: Optional[str]


class AIBugReplaySystem:
    def __init__(self, capture_store, llm_client, retrieval_service):
        self.capture_store = capture_store
        self.llm = llm_client
        self.retrieval = retrieval_service

    async def capture(self, request_id: str, **kwargs) -> None:
        """Called in production to store replay data."""
        captured = CapturedRequest(request_id=request_id, **kwargs)
        # Store with 7-day TTL, encrypted
        await self.capture_store.store(captured, ttl_days=7)

    async def replay_exact(self, request_id: str) -> ReplayResult:
        """Attempt exact reproduction."""
        captured = await self.capture_store.get(request_id)

        # Try deterministic replay (temperature=0, fixed seed)
        deterministic_params = {**captured.model_params, "temperature": 0, "seed": 42}
        response = await self.llm.generate(
            prompt=captured.full_prompt,
            model=captured.model,
            **deterministic_params
        )

        return ReplayResult(
            original_response=captured.raw_response,
            replayed_responses=[response],
            reproduction_rate=1.0 if self._is_similar_bug(response, captured.raw_response) else 0.0,
            isolated_stage=None,
            minimum_repro=None,
        )

    async def replay_statistical(self, request_id: str, n: int = 20) -> ReplayResult:
        """Run N times to characterize reproduction rate."""
        captured = await self.capture_store.get(request_id)

        # Run N parallel attempts with original parameters
        tasks = [
            self.llm.generate(
                prompt=captured.full_prompt,
                model=captured.model,
                **captured.model_params
            )
            for _ in range(n)
        ]
        responses = await asyncio.gather(*tasks)

        # Check how many reproduce the bug
        bug_count = sum(1 for r in responses if self._exhibits_bug(r, captured))

        return ReplayResult(
            original_response=captured.raw_response,
            replayed_responses=responses,
            reproduction_rate=bug_count / n,
            isolated_stage="generation" if bug_count > 0 else "non_reproducible",
            minimum_repro=None,
        )

    async def isolate_stage(self, request_id: str) -> dict:
        """Determine which pipeline stage is responsible."""
        captured = await self.capture_store.get(request_id)
        results = {}

        # Test 1: Is retrieval still returning same docs?
        current_docs = await self.retrieval.search(captured.query)
        docs_changed = set(d.id for d in current_docs) != set(captured.retrieved_doc_ids)
        results["retrieval_changed"] = docs_changed

        # Test 2: Have the documents themselves changed?
        for doc_id, expected_hash in zip(captured.retrieved_doc_ids, captured.retrieved_doc_hashes):
            current_doc = await self.retrieval.get_doc(doc_id)
            current_hash = hashlib.sha256(current_doc.content.encode()).hexdigest()
            if current_hash != expected_hash:
                results["doc_content_changed"] = True
                results["changed_doc_id"] = doc_id
                break

        # Test 3: Does generation reproduce with original context?
        with_original_context = await self.llm.generate(
            prompt=captured.full_prompt, model=captured.model,
            temperature=0, seed=42)
        results["generation_reproduces"] = self._exhibits_bug(with_original_context, captured)

        # Determine isolation
        if docs_changed:
            results["isolated_to"] = "retrieval"
        elif results.get("doc_content_changed"):
            results["isolated_to"] = "data_staleness"
        elif results["generation_reproduces"]:
            results["isolated_to"] = "generation"
        else:
            results["isolated_to"] = "non_deterministic_generation"

        return results

    async def find_minimum_repro(self, request_id: str) -> str:
        """Binary search for minimal prompt that reproduces the bug."""
        captured = await self.capture_store.get(request_id)
        prompt_parts = captured.full_prompt.split("\n")

        # Binary search: remove context chunks until bug disappears
        lo, hi = 0, len(prompt_parts)
        while lo < hi:
            mid = (lo + hi) // 2
            reduced_prompt = "\n".join(prompt_parts[:mid])
            response = await self.llm.generate(reduced_prompt, model=captured.model, temperature=0)
            if self._exhibits_bug(response, captured):
                hi = mid
            else:
                lo = mid + 1

        return "\n".join(prompt_parts[:lo])
```

**Handling Non-Determinism:**

| Strategy | When to Use | Trade-off |
|----------|------------|-----------|
| Temperature=0 + seed | First attempt | May not reproduce temp>0 bugs |
| Statistical (N=20) | Bug suspected in generation | Expensive but characterizes probability |
| Component isolation | Bug may be in retrieval/data | Pinpoints stage but doesn't explain why |
| Minimum repro | Generation bugs | Slow (binary search) but gives actionable fix |

**Production Considerations:**
- Storage: ~2KB per request (prompts are large); use compression + 7-day TTL
- Privacy: Encrypt captured data, require break-glass for replay access
- Model versioning: If provider doesn't pin versions, capture response alongside prompt
- Reproduction ≠ root cause: A bug that reproduces 5/20 times suggests temperature sensitivity

---

## Q138: Design a root cause analysis framework for AI system incidents.

### Answer

**RCA Framework:**

```
┌────────────────────────────────────────────────────────────────┐
│           AI Incident Root Cause Analysis Framework              │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── Incident Classification ─────────────────────────────┐    │
│  │                                                          │    │
│  │  Category A: Retrieval Failures                         │    │
│  │  - Empty results, wrong documents, stale content        │    │
│  │                                                          │    │
│  │  Category B: Generation Failures                        │    │
│  │  - Hallucination, wrong format, refusal, verbosity     │    │
│  │                                                          │    │
│  │  Category C: Safety/Security                            │    │
│  │  - Prompt injection, jailbreak, PII leak, bias         │    │
│  │                                                          │    │
│  │  Category D: Cascade Failures                           │    │
│  │  - Timeout propagation, retry storms, circuit break    │    │
│  │                                                          │    │
│  │  Category E: Data Pipeline Failures                     │    │
│  │  - Corrupt ingestion, embedding drift, index corruption│    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─── RCA Decision Tree ───────────────────────────────────┐    │
│  │                                                          │    │
│  │  Start: What degraded?                                  │    │
│  │    ├── Quality metrics → Check retrieval then generation│    │
│  │    ├── Safety metrics → Check filter pipeline           │    │
│  │    ├── Latency → Check infra then model then queue     │    │
│  │    └── Availability → Check cascading then infra       │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum
from datetime import datetime

class IncidentCategory(Enum):
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    SAFETY = "safety"
    CASCADE = "cascade"
    DATA_PIPELINE = "data_pipeline"

@dataclass
class RCAFinding:
    category: IncidentCategory
    root_cause: str
    contributing_factors: list[str]
    evidence: dict
    timeline: list[dict]           # [{time, event, impact}]
    blast_radius: dict             # {users_affected, requests_affected, duration}
    remediation: list[str]
    prevention: list[str]

class AIIncidentRCA:
    """Structured root cause analysis for AI incidents."""

    async def analyze(self, incident_id: str, symptoms: list[str],
                      start_time: datetime) -> RCAFinding:
        # Step 1: Gather evidence
        traces = await self._get_traces_in_window(start_time, duration_minutes=60)
        metrics = await self._get_metrics_in_window(start_time, duration_minutes=60)
        deployments = await self._get_recent_deployments(start_time)
        config_changes = await self._get_config_changes(start_time)

        # Step 2: Correlate with changes
        suspected_trigger = self._find_trigger(deployments, config_changes, start_time)

        # Step 3: Classify and deep-dive
        category = self._classify_incident(symptoms, metrics)

        if category == IncidentCategory.RETRIEVAL:
            return await self._rca_retrieval(traces, metrics, suspected_trigger)
        elif category == IncidentCategory.GENERATION:
            return await self._rca_generation(traces, metrics, suspected_trigger)
        elif category == IncidentCategory.SAFETY:
            return await self._rca_safety(traces, metrics, suspected_trigger)
        elif category == IncidentCategory.CASCADE:
            return await self._rca_cascade(traces, metrics, suspected_trigger)
        else:
            return await self._rca_data_pipeline(traces, metrics, suspected_trigger)

    async def _rca_retrieval(self, traces, metrics, trigger) -> RCAFinding:
        """RCA for retrieval failures."""
        # Check: Index health
        index_stats = await self._check_index_health()
        # Check: Embedding service
        embedding_health = await self._check_embedding_service()
        # Check: Query patterns (new query types?)
        query_drift = await self._check_query_drift()

        root_cause = None
        if index_stats["corruption_detected"]:
            root_cause = f"Index corruption detected at {index_stats['corruption_time']}"
        elif embedding_health["version_changed"]:
            root_cause = f"Embedding model version changed: {embedding_health['old']} → {embedding_health['new']}"
        elif query_drift["significant"]:
            root_cause = f"Query distribution shifted: {query_drift['description']}"

        return RCAFinding(
            category=IncidentCategory.RETRIEVAL,
            root_cause=root_cause or "Unknown retrieval degradation",
            contributing_factors=[
                f"Trigger: {trigger}" if trigger else "No deployment trigger found",
                f"Index size: {index_stats['doc_count']} docs",
            ],
            evidence={"index_stats": index_stats, "embedding_health": embedding_health},
            timeline=self._build_timeline(traces, metrics),
            blast_radius=self._compute_blast_radius(traces),
            remediation=["Rebuild index from last known good state",
                        "Rollback embedding model if version changed"],
            prevention=["Add index health checks to deployment pipeline",
                       "Pin embedding model version in config"],
        )

    async def _rca_cascade(self, traces, metrics, trigger) -> RCAFinding:
        """RCA for cascading failures across AI microservices."""
        # Trace the cascade: which service failed first?
        service_error_timeline = self._build_service_error_timeline(traces)
        origin_service = service_error_timeline[0]["service"]

        # Check for common cascade patterns
        patterns = {
            "retry_storm": self._detect_retry_storm(traces),
            "timeout_propagation": self._detect_timeout_cascade(traces),
            "resource_exhaustion": self._detect_resource_exhaustion(metrics),
            "circuit_breaker_open": self._detect_open_circuits(metrics),
        }

        active_patterns = {k: v for k, v in patterns.items() if v["detected"]}

        return RCAFinding(
            category=IncidentCategory.CASCADE,
            root_cause=f"Cascade originated in {origin_service}: {active_patterns}",
            contributing_factors=[
                "Missing circuit breakers" if not patterns["circuit_breaker_open"]["detected"]
                else "Circuit breakers opened too late",
                f"Retry amplification: {patterns['retry_storm'].get('amplification_factor', 'N/A')}x",
            ],
            evidence={"cascade_timeline": service_error_timeline, "patterns": active_patterns},
            timeline=service_error_timeline,
            blast_radius=self._compute_blast_radius(traces),
            remediation=["Add/tune circuit breakers", "Implement backpressure",
                        "Add timeout budgets across call chain"],
            prevention=["Chaos testing for cascade scenarios",
                       "Dependency health checks in readiness probes"],
        )
```

**RCA Checklist by Category:**

| Category | First 5 Minutes | Deep Dive | Common Root Causes |
|----------|----------------|-----------|-------------------|
| Retrieval | Check index health, embedding service | Query drift analysis, similarity score distribution | Index corruption, embedding model change, data pipeline failure |
| Generation | Check LLM provider status, prompt changes | Token analysis, temperature audit | Provider model update, prompt template bug, context overflow |
| Safety | Check filter service health, recent config | Analyze bypassed requests, pattern matching | Filter rule regression, new attack pattern, over-blocking threshold change |
| Cascade | Map service dependency graph, find origin | Trace call chains, check retry configs | Missing circuit breakers, timeout misconfiguration, resource exhaustion |

**Production Considerations:**
- Automate evidence collection: one-click gathers traces, metrics, deployments, config changes
- Maintain a "known issues" database to speed up repeat incident diagnosis
- Track MTTR by incident category; invest in automation for slowest categories
- Always check for "silent changes": LLM provider updates, embedding model refreshes

---

## Q139: Design a performance profiling system for AI inference pipelines.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────┐
│          AI Pipeline Performance Profiler                        │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Request Timeline (waterfall view):                             │
│                                                                  │
│  0ms        200ms       400ms       1000ms      2000ms   2500ms│
│  │           │           │           │           │         │    │
│  ├──────┤                                                       │
│  │ Parse │ (CPU: 15ms)                                         │
│  │       ├────┤                                                 │
│  │       │Embed│ (GPU: 120ms, queue_wait: 45ms)                │
│  │       │    ├───┤                                             │
│  │       │    │Retr│ (Network: 85ms, DB: 60ms)                 │
│  │       │    │   ├──┤                                          │
│  │       │    │   │Rnk│ (GPU: 200ms, queue_wait: 30ms)        │
│  │       │    │   │  ├───────────────────────────────┤          │
│  │       │    │   │  │  LLM Generation               │         │
│  │       │    │   │  │  (TTFT:300ms, gen:1200ms)     │         │
│  │       │    │   │  │                               ├──┤      │
│  │       │    │   │  │                               │SF│      │
│  │       │    │   │  │                               │  │      │
│  ──────────────────────────────────────────────────────────     │
│  Total: 2.5s | GPU: 45% | Network: 12% | Queue: 8% | CPU: 5% │
│                                                                  │
│  Bottleneck: LLM Generation (48% of total time)                │
└────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import time
import asyncio
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from typing import Optional
import torch

@dataclass
class ProfileSpan:
    name: str
    start_ns: int
    end_ns: int = 0
    category: str = "cpu"          # cpu, gpu, network, queue
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (self.end_ns - self.start_ns) / 1_000_000

@dataclass
class PipelineProfile:
    request_id: str
    spans: list[ProfileSpan] = field(default_factory=list)
    gpu_utilization: float = 0.0
    memory_peak_mb: float = 0.0

    @property
    def total_ms(self) -> float:
        if not self.spans:
            return 0
        return (max(s.end_ns for s in self.spans) - min(s.start_ns for s in self.spans)) / 1_000_000

    @property
    def bottleneck(self) -> Optional[ProfileSpan]:
        return max(self.spans, key=lambda s: s.duration_ms) if self.spans else None

    def get_breakdown(self) -> dict:
        """Category breakdown as percentage of total."""
        total = self.total_ms
        breakdown = {}
        for span in self.spans:
            cat = span.category
            breakdown[cat] = breakdown.get(cat, 0) + span.duration_ms
        return {k: v / total * 100 for k, v in breakdown.items()}


class AIPipelineProfiler:
    def __init__(self):
        self.profiles: list[PipelineProfile] = []
        self._current: Optional[PipelineProfile] = None

    @asynccontextmanager
    async def profile_request(self, request_id: str):
        self._current = PipelineProfile(request_id=request_id)
        try:
            yield self._current
        finally:
            self.profiles.append(self._current)
            self._emit_profile_metrics(self._current)
            self._current = None

    @asynccontextmanager
    async def profile_span(self, name: str, category: str = "cpu"):
        span = ProfileSpan(name=name, start_ns=time.perf_counter_ns(), category=category)

        # GPU memory tracking
        gpu_mem_before = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0

        try:
            yield span
        finally:
            span.end_ns = time.perf_counter_ns()

            if torch.cuda.is_available():
                gpu_mem_after = torch.cuda.memory_allocated()
                span.metadata["gpu_memory_delta_mb"] = (gpu_mem_after - gpu_mem_before) / 1024**2

            if self._current:
                self._current.spans.append(span)

    async def profile_gpu_inference(self, name: str, fn, *args, **kwargs):
        """Profile a GPU inference call including queue wait time."""
        queue_start = time.perf_counter_ns()

        # Measure queue wait (time until GPU is available)
        async with self.profile_span(f"{name}.queue_wait", "queue"):
            await self._wait_for_gpu_slot()

        # Measure actual GPU computation
        async with self.profile_span(f"{name}.compute", "gpu") as span:
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                start_event = torch.cuda.Event(enable_timing=True)
                end_event = torch.cuda.Event(enable_timing=True)
                start_event.record()

            result = await fn(*args, **kwargs)

            if torch.cuda.is_available():
                end_event.record()
                torch.cuda.synchronize()
                span.metadata["gpu_kernel_ms"] = start_event.elapsed_time(end_event)

        return result

    def analyze_bottlenecks(self, n_recent: int = 100) -> dict:
        """Aggregate profiling data to find systemic bottlenecks."""
        recent = self.profiles[-n_recent:]

        stage_stats = {}
        for profile in recent:
            for span in profile.spans:
                if span.name not in stage_stats:
                    stage_stats[span.name] = []
                stage_stats[span.name].append(span.duration_ms)

        analysis = {}
        for stage, durations in stage_stats.items():
            analysis[stage] = {
                "p50_ms": sorted(durations)[len(durations)//2],
                "p99_ms": sorted(durations)[int(len(durations)*0.99)],
                "mean_ms": sum(durations) / len(durations),
                "pct_of_total": sum(durations) / sum(p.total_ms for p in recent) * 100,
            }

        # Sort by impact
        return dict(sorted(analysis.items(), key=lambda x: x[1]["pct_of_total"], reverse=True))
```

**Bottleneck Identification Matrix:**

| Bottleneck | Symptom | Diagnostic | Fix |
|-----------|---------|-----------|-----|
| GPU queue wait | High queue_wait spans | GPU utilization near 100% | Scale GPU instances, batch requests |
| LLM generation | Generation dominates timeline | High token count | Reduce context, use smaller model for simple queries |
| Network (retrieval) | High network span variance | DNS/connection issues | Connection pooling, local caching |
| CPU pre-processing | CPU spans > 50ms | Tokenization, parsing heavy | Pre-compute, cache tokenization |
| Memory pressure | GC pauses in spans | Memory near limit | Optimize batch sizes, streaming |

**Production Considerations:**
- Profile 1% of requests continuously (low overhead)
- Profile 100% during canary deployments
- Use CUDA events for accurate GPU timing (wall clock misleading with async)
- Alert when bottleneck shifts (e.g., generation was 40%, now 60% = model got slower)
- Correlate with cost: profile shows where compute dollars go

---

## Q140: Design a system for detecting and debugging "silent failures" in AI systems.

### Answer

**The Problem:** Silent failures are responses that pass all health checks (200 OK, valid JSON, reasonable latency) but are subtly wrong. Examples: outdated information presented as current, confident hallucination, correct format but wrong content, answers from wrong context.

**Architecture:**

```
┌────────────────────────────────────────────────────────────────┐
│            Silent Failure Detection System                       │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── Detection Layers ────────────────────────────────────┐    │
│  │                                                          │    │
│  │  Layer 1: Heuristic Detectors (100%, real-time)         │    │
│  │  • Confidence calibration (high confidence + wrong?)    │    │
│  │  • Self-consistency check (ask twice, compare)          │    │
│  │  • Citation verification (claims match sources?)        │    │
│  │  • Temporal consistency (mentions dates correctly?)     │    │
│  │  • Format-content mismatch (looks right, is wrong)     │    │
│  │                                                          │    │
│  │  Layer 2: Sampled Deep Analysis (5%, near-real-time)    │    │
│  │  • LLM-as-judge evaluation                             │    │
│  │  • Claim extraction + verification                      │    │
│  │  • Cross-reference with authoritative sources           │    │
│  │                                                          │    │
│  │  Layer 3: Cohort Analysis (batch, daily)                │    │
│  │  • Compare answers to same question over time           │    │
│  │  • Detect answer drift (gradually getting wrong)        │    │
│  │  • Statistical outlier detection in quality scores      │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─── Synthetic Probes ────────────────────────────────────┐    │
│  │                                                          │    │
│  │  Continuous injection of "known-answer" queries:        │    │
│  │  • Golden dataset queries (known correct answer)        │    │
│  │  • Trap questions (should refuse/say "I don't know")   │    │
│  │  • Temporal probes ("What's the current date?")        │    │
│  │  • Consistency probes (same question, different phrasing)│   │
│  │                                                          │    │
│  │  If golden query gets wrong answer → immediate alert    │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from typing import Optional
import asyncio
import re

@dataclass
class SilentFailureSignal:
    request_id: str
    detector: str
    confidence: float    # How confident we are this IS a silent failure
    evidence: str
    response_text: str

class SilentFailureDetector:
    """Multi-layer detection of subtly wrong AI responses."""

    def __init__(self, llm_client, knowledge_base):
        self.llm = llm_client
        self.kb = knowledge_base
        self.golden_dataset = self._load_golden_dataset()

    async def check_response(self, request_id: str, query: str,
                             response: str, sources: list[str]) -> list[SilentFailureSignal]:
        """Run all real-time detectors on a response."""
        signals = []

        # Run detectors in parallel
        checks = await asyncio.gather(
            self._check_citation_grounding(request_id, response, sources),
            self._check_temporal_consistency(request_id, response),
            self._check_self_consistency(request_id, query, response),
            self._check_confidence_calibration(request_id, response),
            return_exceptions=True
        )

        for check in checks:
            if isinstance(check, SilentFailureSignal) and check.confidence > 0.6:
                signals.append(check)

        return signals

    async def _check_citation_grounding(self, request_id: str,
                                         response: str, sources: list[str]) -> Optional[SilentFailureSignal]:
        """Verify claims in response are actually in the sources."""
        # Extract factual claims from response
        claims = await self._extract_claims(response)

        ungrounded_claims = []
        for claim in claims:
            grounded = any(self._claim_in_source(claim, source) for source in sources)
            if not grounded:
                ungrounded_claims.append(claim)

        if ungrounded_claims:
            ratio = len(ungrounded_claims) / max(len(claims), 1)
            if ratio > 0.3:  # More than 30% of claims ungrounded
                return SilentFailureSignal(
                    request_id=request_id,
                    detector="citation_grounding",
                    confidence=min(ratio, 1.0),
                    evidence=f"{len(ungrounded_claims)}/{len(claims)} claims not in sources: {ungrounded_claims[:3]}",
                    response_text=response,
                )
        return None

    async def _check_self_consistency(self, request_id: str,
                                       query: str, response: str) -> Optional[SilentFailureSignal]:
        """Ask the same question differently and compare answers."""
        # Rephrase the query
        rephrased = await self.llm.generate(
            f"Rephrase this question differently: {query}",
            temperature=0.7
        )
        # Get second answer
        second_response = await self.llm.generate(rephrased, temperature=0)

        # Check semantic consistency
        consistency = await self._compute_semantic_similarity(response, second_response)

        if consistency < 0.6:  # Inconsistent answers = one might be wrong
            return SilentFailureSignal(
                request_id=request_id,
                detector="self_consistency",
                confidence=1.0 - consistency,
                evidence=f"Inconsistent answers (similarity={consistency:.2f}). "
                         f"Original: {response[:100]}... Rephrased: {second_response[:100]}...",
                response_text=response,
            )
        return None

    async def _check_temporal_consistency(self, request_id: str,
                                           response: str) -> Optional[SilentFailureSignal]:
        """Detect outdated information presented as current."""
        # Look for temporal claims
        temporal_patterns = [
            r"currently|as of \d{4}|this year|recently|latest",
            r"the current .* is",
            r"today.* is",
        ]

        has_temporal_claim = any(re.search(p, response, re.I) for p in temporal_patterns)

        if has_temporal_claim:
            # Verify temporal claims against known current facts
            temporal_check = await self._verify_temporal_claims(response)
            if not temporal_check["all_current"]:
                return SilentFailureSignal(
                    request_id=request_id,
                    detector="temporal_consistency",
                    confidence=0.8,
                    evidence=f"Potentially outdated temporal claims: {temporal_check['stale_claims']}",
                    response_text=response,
                )
        return None


class GoldenDatasetProber:
    """Continuously inject known-answer queries to detect silent failures."""

    def __init__(self, golden_queries: list[dict], ai_service):
        self.golden = golden_queries  # [{query, expected_answer, tolerance}]
        self.ai_service = ai_service

    async def run_probe_cycle(self) -> list[dict]:
        """Run all golden queries and check answers."""
        failures = []
        for item in self.golden:
            response = await self.ai_service.query(item["query"])
            correct = await self._check_answer(response, item["expected_answer"],
                                                item.get("tolerance", 0.9))
            if not correct:
                failures.append({
                    "query": item["query"],
                    "expected": item["expected_answer"],
                    "got": response,
                    "category": item.get("category", "general"),
                })

        if failures:
            failure_rate = len(failures) / len(self.golden)
            if failure_rate > 0.1:  # More than 10% golden queries failing
                self._fire_alert(f"Silent failure detected: {len(failures)}/{len(self.golden)} "
                                f"golden queries returning wrong answers")
        return failures
```

**Detection Strategy Trade-offs:**

| Detector | Coverage | Latency Cost | False Positive Rate | Catches |
|----------|----------|--------------|--------------------|---------| 
| Citation grounding | 100% | +50ms | Low (10%) | Hallucination |
| Self-consistency | 5% sampled | +2s | Medium (20%) | Non-deterministic errors |
| Temporal check | 100% | +20ms | Low (5%) | Stale information |
| Golden probes | Synthetic only | N/A (async) | Very low | Systemic degradation |
| LLM-as-judge | 5% sampled | +3s | Medium (15%) | General quality issues |

**Production Considerations:**
- Run Layer 1 detectors on 100% of traffic (lightweight, <50ms overhead)
- Golden probes run every 5 minutes, covering key query categories
- Alert on golden probe failure immediately (these are our "canary in the coal mine")
- False positives are OK for detection; use human review before acting on silent failure alerts
- Track silent failure rate as a key SLI (should be <2%)
# Data Quality and Pipeline Monitoring (Questions 141-145)

## Q141: Design a data quality monitoring system for RAG document ingestion.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────────┐
│            Document Ingestion Quality Gate System                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Raw Documents ──→ Quality Gate Pipeline ──→ Approved Index         │
│                                                                      │
│  ┌─── Stage 1: Format Validation ──────────────────────────────┐   │
│  │  • File integrity (not corrupt, readable)                    │   │
│  │  • Format parsing (PDF/HTML/MD extractable)                  │   │
│  │  • Encoding detection (UTF-8, handle edge cases)            │   │
│  │  • Size bounds (not empty, not suspiciously large)          │   │
│  └──────────────────────────────────────┬───────────────────────┘   │
│                                         │ Pass: 95%                  │
│  ┌──────────────────────────────────────▼───────────────────────┐   │
│  │  Stage 2: Content Quality ──────────────────────────────────  │   │
│  │  • Language detection (expected languages only)               │   │
│  │  • Readability score (not garbled/OCR artifacts)             │   │
│  │  • Completeness (not truncated mid-sentence)                 │   │
│  │  • Structural integrity (headers, sections parseable)        │   │
│  └──────────────────────────────────────┬───────────────────────┘   │
│                                         │ Pass: 90%                  │
│  ┌──────────────────────────────────────▼───────────────────────┐   │
│  │  Stage 3: Duplication Detection ────────────────────────────  │   │
│  │  • Exact duplicate (content hash)                            │   │
│  │  • Near-duplicate (MinHash/SimHash, threshold 0.9)          │   │
│  │  • Superseded content (newer version exists)                 │   │
│  └──────────────────────────────────────┬───────────────────────┘   │
│                                         │ Pass: 85%                  │
│  ┌──────────────────────────────────────▼───────────────────────┐   │
│  │  Stage 4: Freshness & Provenance ──────────────────────────   │   │
│  │  • Source reputation score                                   │   │
│  │  • Publication date validation                               │   │
│  │  • Contradiction detection (vs existing index)              │   │
│  │  • Data poisoning signals (adversarial content)             │   │
│  └──────────────────────────────────────┬───────────────────────┘   │
│                                         │ Pass: 80%                  │
│  ┌──────────────────────────────────────▼───────────────────────┐   │
│  │  Stage 5: Safety & Compliance ─────────────────────────────   │   │
│  │  • PII detection (reject or redact)                          │   │
│  │  • Harmful content classification                            │   │
│  │  • Copyright/licensing check                                 │   │
│  │  • Access control tagging                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import hashlib
from datasketch import MinHash, MinHashLSH

class QualityVerdict(Enum):
    PASS = "pass"
    FAIL = "fail"
    QUARANTINE = "quarantine"  # Needs human review

@dataclass
class QualityCheckResult:
    stage: str
    verdict: QualityVerdict
    score: float              # 0-1
    details: dict
    blocking: bool = True     # If True, failure stops pipeline

@dataclass
class DocumentQualityReport:
    doc_id: str
    source: str
    checks: list[QualityCheckResult] = field(default_factory=list)
    overall_verdict: QualityVerdict = QualityVerdict.PASS
    quality_score: float = 1.0


class DocumentQualityGate:
    def __init__(self, dedup_index: MinHashLSH, existing_index):
        self.dedup_index = dedup_index
        self.existing_index = existing_index
        self.poisoning_detector = PoisoningDetector()

    async def evaluate(self, doc: dict) -> DocumentQualityReport:
        report = DocumentQualityReport(doc_id=doc["id"], source=doc["source"])

        # Stage 1: Format
        format_check = self._check_format(doc)
        report.checks.append(format_check)
        if format_check.verdict == QualityVerdict.FAIL:
            report.overall_verdict = QualityVerdict.FAIL
            return report

        # Stage 2: Content quality
        content_check = await self._check_content_quality(doc)
        report.checks.append(content_check)

        # Stage 3: Deduplication
        dedup_check = self._check_duplicates(doc)
        report.checks.append(dedup_check)

        # Stage 4: Freshness & poisoning
        freshness_check = await self._check_freshness_and_poisoning(doc)
        report.checks.append(freshness_check)

        # Stage 5: Safety
        safety_check = await self._check_safety(doc)
        report.checks.append(safety_check)

        # Overall scoring
        scores = [c.score for c in report.checks]
        report.quality_score = min(scores)  # Weakest link
        if any(c.verdict == QualityVerdict.FAIL and c.blocking for c in report.checks):
            report.overall_verdict = QualityVerdict.FAIL
        elif any(c.verdict == QualityVerdict.QUARANTINE for c in report.checks):
            report.overall_verdict = QualityVerdict.QUARANTINE
        return report

    def _check_format(self, doc: dict) -> QualityCheckResult:
        issues = []
        content = doc.get("content", "")

        if not content or len(content.strip()) < 50:
            return QualityCheckResult("format", QualityVerdict.FAIL, 0.0,
                                      {"reason": "Empty or near-empty document"})

        if len(content) > 10_000_000:  # 10MB text
            issues.append("Suspiciously large document")

        # Check for garbled content (high ratio of non-printable chars)
        non_printable = sum(1 for c in content if not c.isprintable() and c not in '\n\t\r')
        garble_ratio = non_printable / len(content)
        if garble_ratio > 0.1:
            return QualityCheckResult("format", QualityVerdict.FAIL, 0.2,
                                      {"reason": f"Garbled content ({garble_ratio:.1%} non-printable)"})

        score = 1.0 - min(garble_ratio * 5, 0.5)
        return QualityCheckResult("format", QualityVerdict.PASS, score, {"issues": issues})

    def _check_duplicates(self, doc: dict) -> QualityCheckResult:
        """MinHash-based near-duplicate detection."""
        content = doc["content"]

        # Create MinHash
        mh = MinHash(num_perm=128)
        for shingle in self._get_shingles(content, k=5):
            mh.update(shingle.encode('utf8'))

        # Query LSH index for near-duplicates
        duplicates = self.dedup_index.query(mh)

        if duplicates:
            # Check if this is a newer version (supersedes)
            is_update = self._is_newer_version(doc, duplicates)
            if is_update:
                return QualityCheckResult("deduplication", QualityVerdict.PASS, 0.9,
                                          {"action": "supersedes", "old_docs": duplicates})
            else:
                return QualityCheckResult("deduplication", QualityVerdict.FAIL, 0.1,
                                          {"reason": "Near-duplicate exists", "duplicates": duplicates})

        # Add to index for future checks
        self.dedup_index.insert(doc["id"], mh)
        return QualityCheckResult("deduplication", QualityVerdict.PASS, 1.0, {})

    async def _check_freshness_and_poisoning(self, doc: dict) -> QualityCheckResult:
        """Detect stale or adversarial content."""
        # Freshness
        pub_date = doc.get("published_date")
        if pub_date and self._is_stale(pub_date, max_age_days=365):
            return QualityCheckResult("freshness", QualityVerdict.QUARANTINE, 0.5,
                                      {"reason": f"Document is {self._age_days(pub_date)} days old"})

        # Poisoning detection: unusual patterns suggesting adversarial injection
        poisoning_score = await self.poisoning_detector.score(doc["content"])
        if poisoning_score > 0.8:
            return QualityCheckResult("poisoning", QualityVerdict.FAIL, 0.1,
                                      {"reason": "Suspected data poisoning",
                                       "score": poisoning_score})

        # Contradiction detection
        contradictions = await self._find_contradictions(doc["content"])
        if contradictions:
            return QualityCheckResult("contradiction", QualityVerdict.QUARANTINE, 0.6,
                                      {"contradictions": contradictions})

        return QualityCheckResult("freshness", QualityVerdict.PASS, 1.0, {})
```

**Monitoring Dashboard Metrics:**

| Metric | Alert Threshold | Action |
|--------|----------------|--------|
| Ingestion pass rate | < 70% | Check source quality, pipeline bugs |
| Duplicate rate | > 30% | Check crawler dedup, source RSS issues |
| Poisoning detections | > 0.1% | Alert security, investigate source |
| Quarantine queue size | > 1000 docs | Alert team, may need more reviewers |
| Format failures | > 20% | Check parser, new document types |

**Production Considerations:**
- Process quality checks as a DAG (parallelize independent stages)
- Quarantined docs go to human review queue with priority scoring
- Track quality metrics per source (some sources may need removal)
- Implement "progressive trust": new sources start with stricter thresholds
- Keep rejected documents for audit (but separate from production index)

---

## Q142: Design an embedding quality monitoring system that detects when embedding model outputs degrade.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────┐
│           Embedding Quality Monitoring System                    │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── Embedding Health Checks ─────────────────────────────┐    │
│  │                                                          │    │
│  │  1. Distribution Monitoring                             │    │
│  │     • Norm distribution (should be stable)              │    │
│  │     • Variance per dimension                            │    │
│  │     • Cosine similarity distribution of random pairs    │    │
│  │                                                          │    │
│  │  2. Alignment Checks (Golden Pairs)                     │    │
│  │     • Known-similar pairs should have sim > 0.8         │    │
│  │     • Known-dissimilar pairs should have sim < 0.3     │    │
│  │     • Symmetry: sim(A,B) ≈ sim(B,A)                   │    │
│  │                                                          │    │
│  │  3. Downstream Impact                                   │    │
│  │     • Retrieval recall on golden queries               │    │
│  │     • Clustering stability (cluster assignments stable) │    │
│  │     • Nearest-neighbor consistency over time           │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─── Detection Pipeline ──────────────────────────────────┐    │
│  │                                                          │    │
│  │  Every 15 min:                                          │    │
│  │  1. Embed golden test set (50 curated pairs)           │    │
│  │  2. Compute alignment score                            │    │
│  │  3. Compare current distribution vs reference          │    │
│  │  4. Run retrieval eval on golden queries               │    │
│  │                                                          │    │
│  │  Continuous (per-request sampling):                     │    │
│  │  1. Track norm distribution                            │    │
│  │  2. Track inter-query similarity distribution          │    │
│  │  3. Detect zero/null embeddings                        │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import numpy as np
from scipy import stats
from dataclasses import dataclass
from typing import Optional

@dataclass
class EmbeddingHealthReport:
    timestamp: float
    model_version: str
    norm_stats: dict           # mean, std, min, max
    alignment_score: float     # Golden pair alignment [0,1]
    distribution_shift: float  # Distance from reference distribution
    retrieval_recall: float    # Recall@10 on golden queries
    anomalies: list[str]

class EmbeddingQualityMonitor:
    def __init__(self, embedding_service, reference_embeddings: np.ndarray):
        self.embed = embedding_service
        self.reference = reference_embeddings  # Baseline "known good" embeddings
        self.golden_pairs = self._load_golden_pairs()
        self.golden_queries = self._load_golden_queries()
        self.history: list[EmbeddingHealthReport] = []

    async def run_health_check(self) -> EmbeddingHealthReport:
        anomalies = []

        # 1. Embed golden test set
        similar_pairs = self.golden_pairs["similar"]  # [(text_a, text_b), ...]
        dissimilar_pairs = self.golden_pairs["dissimilar"]

        similar_scores = []
        for a, b in similar_pairs:
            emb_a = await self.embed.encode(a)
            emb_b = await self.embed.encode(b)
            sim = self._cosine_sim(emb_a, emb_b)
            similar_scores.append(sim)

        dissimilar_scores = []
        for a, b in dissimilar_pairs:
            emb_a = await self.embed.encode(a)
            emb_b = await self.embed.encode(b)
            sim = self._cosine_sim(emb_a, emb_b)
            dissimilar_scores.append(sim)

        # Alignment: similar pairs should score high, dissimilar low
        alignment_score = (
            np.mean([s for s in similar_scores if s > 0.7]) * 0.5 +
            np.mean([1 - s for s in dissimilar_scores if s < 0.4]) * 0.5
        )

        if alignment_score < 0.75:
            anomalies.append(f"Alignment degraded: {alignment_score:.3f} (threshold: 0.75)")

        # 2. Norm distribution
        test_texts = [p[0] for p in similar_pairs + dissimilar_pairs]
        embeddings = np.array([await self.embed.encode(t) for t in test_texts])
        norms = np.linalg.norm(embeddings, axis=1)

        norm_stats = {
            "mean": float(norms.mean()),
            "std": float(norms.std()),
            "min": float(norms.min()),
            "max": float(norms.max()),
        }

        # Check for degenerate embeddings
        if norms.std() < 0.01:
            anomalies.append("Embedding collapse detected: near-zero variance in norms")
        if norms.min() < 0.1:
            anomalies.append(f"Near-zero norm embedding detected: {norms.min():.4f}")

        # 3. Distribution shift from reference
        # Use MMD or centroid distance
        ref_centroid = self.reference.mean(axis=0)
        curr_centroid = embeddings.mean(axis=0)
        centroid_shift = np.linalg.norm(ref_centroid - curr_centroid)

        if centroid_shift > 0.1:
            anomalies.append(f"Centroid shifted by {centroid_shift:.4f}")

        # KS test on per-dimension distributions (sample a few dimensions)
        dim_shifts = []
        for dim in range(0, embeddings.shape[1], embeddings.shape[1] // 10):
            _, p_val = stats.ks_2samp(self.reference[:, dim], embeddings[:, dim])
            if p_val < 0.01:
                dim_shifts.append(dim)

        if len(dim_shifts) > embeddings.shape[1] * 0.3:
            anomalies.append(f"Significant shift in {len(dim_shifts)} dimensions")

        # 4. Retrieval recall on golden queries
        recall = await self._compute_retrieval_recall()
        if recall < 0.7:
            anomalies.append(f"Retrieval recall degraded: {recall:.3f}")

        report = EmbeddingHealthReport(
            timestamp=time.time(),
            model_version=self.embed.get_version(),
            norm_stats=norm_stats,
            alignment_score=alignment_score,
            distribution_shift=centroid_shift,
            retrieval_recall=recall,
            anomalies=anomalies,
        )

        self.history.append(report)

        if anomalies:
            self._fire_alert(report)

        return report

    async def monitor_realtime(self, embedding: np.ndarray, text: str):
        """Per-request lightweight check (runs on sampled traffic)."""
        norm = np.linalg.norm(embedding)

        # Check for degenerate cases
        if norm < 0.01:
            self._fire_alert_immediate("Zero embedding detected", text_hash=hash(text))
        elif norm > 100:
            self._fire_alert_immediate("Abnormally large embedding norm", norm=norm)

        # Track for distribution monitoring
        self._record_norm(norm)
```

**Golden Pair Examples:**

| Type | Text A | Text B | Expected Similarity |
|------|--------|--------|-------------------|
| Similar | "How to reset password" | "Steps to change my password" | > 0.85 |
| Similar | "Python list comprehension" | "Creating lists with comprehensions in Python" | > 0.80 |
| Dissimilar | "How to reset password" | "Recipe for chocolate cake" | < 0.25 |
| Dissimilar | "Machine learning algorithms" | "Tax filing deadline 2024" | < 0.20 |

**Alert Conditions:**

| Condition | Severity | Likely Cause |
|-----------|----------|--------------|
| Alignment < 0.75 | P1 | Model version change, corrupted weights |
| Norm collapse (std < 0.01) | P1 | Model failure, returning constant vector |
| Centroid shift > 0.1 | P2 | Model update, input distribution change |
| Retrieval recall < 0.7 | P1 | Embedding-index mismatch (re-embed needed) |
| Zero/null embeddings > 0.1% | P2 | Service error, input encoding issues |

**Production Considerations:**
- Golden pair set should be diverse (multiple languages, topics, lengths)
- Reference embeddings need updating when you intentionally upgrade the model
- Run full health check every 15min; per-request norm check on 10% of traffic
- If embedding model changes, you must re-embed the entire index (detect this!)
- Cache golden pair embeddings and invalidate on model version change

---

## Q143: Design a pipeline observability system for a document processing pipeline handling 1M docs/day.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────────┐
│     Document Pipeline Observability (1M docs/day)                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Pipeline Stages:                                                   │
│  Ingest → Parse → Chunk → Embed → Index → Validate                │
│                                                                      │
│  ┌─── Per-Stage Instrumentation ───────────────────────────────┐   │
│  │                                                              │   │
│  │  Each stage emits:                                          │   │
│  │  • Throughput (docs/sec, bytes/sec)                         │   │
│  │  • Latency histogram (P50, P95, P99)                       │   │
│  │  • Error rate by error type                                 │   │
│  │  • Queue depth (backpressure indicator)                     │   │
│  │  • Quality metrics (stage-specific)                         │   │
│  │  • Resource utilization (CPU, GPU, memory)                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─── Pipeline-Level Metrics ──────────────────────────────────┐   │
│  │                                                              │   │
│  │  • End-to-end latency (ingest → indexed)                   │   │
│  │  • Document funnel (how many drop at each stage)           │   │
│  │  • Completion rate (docs successfully indexed / ingested)  │   │
│  │  • Lag (time between doc available and doc indexed)        │   │
│  │  • Backpressure propagation (which stage is bottleneck?)   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─── Document Lineage Tracking ──────────────────────────────┐    │
│  │                                                              │    │
│  │  doc_123 → [ingested 10:00] → [parsed 10:01] →             │    │
│  │            [chunked: 12 chunks 10:01] →                     │    │
│  │            [embedded 10:02] → [indexed 10:03]               │    │
│  │                                                              │    │
│  │  Queryable: "Where is doc_123 right now?"                   │    │
│  │             "Which docs are stuck?"                         │    │
│  │             "What failed in the last hour?"                 │    │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time
from collections import defaultdict

class PipelineStage(Enum):
    INGEST = "ingest"
    PARSE = "parse"
    CHUNK = "chunk"
    EMBED = "embed"
    INDEX = "index"
    VALIDATE = "validate"

@dataclass
class StageMetrics:
    throughput_per_sec: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    error_rate: float = 0.0
    queue_depth: int = 0
    docs_in_progress: int = 0
    quality_score: float = 1.0


class PipelineObserver:
    """Observability for high-throughput document processing pipeline."""

    def __init__(self):
        self.stage_metrics: dict[PipelineStage, StageMetrics] = {}
        self.document_lineage: dict[str, list[dict]] = defaultdict(list)
        self.stage_latencies: dict[PipelineStage, list[float]] = defaultdict(list)

    def record_stage_entry(self, doc_id: str, stage: PipelineStage):
        """Record document entering a pipeline stage."""
        self.document_lineage[doc_id].append({
            "stage": stage.value,
            "entered": time.time(),
            "status": "in_progress",
        })

    def record_stage_exit(self, doc_id: str, stage: PipelineStage,
                          success: bool, metadata: dict = None):
        """Record document completing a pipeline stage."""
        lineage = self.document_lineage[doc_id]
        for entry in reversed(lineage):
            if entry["stage"] == stage.value and entry["status"] == "in_progress":
                entry["exited"] = time.time()
                entry["status"] = "success" if success else "failed"
                entry["duration_ms"] = (entry["exited"] - entry["entered"]) * 1000
                entry["metadata"] = metadata or {}
                self.stage_latencies[stage].append(entry["duration_ms"])
                break

    def get_pipeline_health(self) -> dict:
        """Real-time pipeline health summary."""
        health = {}
        for stage in PipelineStage:
            latencies = self.stage_latencies.get(stage, [])
            recent = latencies[-1000:]  # Last 1000 docs

            if not recent:
                health[stage.value] = {"status": "no_data"}
                continue

            health[stage.value] = {
                "throughput_per_min": len(recent) / max(1, (time.time() - self._first_ts(stage)) / 60),
                "latency_p50_ms": sorted(recent)[len(recent)//2],
                "latency_p99_ms": sorted(recent)[int(len(recent)*0.99)],
                "error_rate": self._compute_error_rate(stage),
                "queue_depth": self._get_queue_depth(stage),
            }

        # Pipeline-level metrics
        health["pipeline"] = {
            "end_to_end_p50_ms": self._compute_e2e_latency(0.5),
            "end_to_end_p99_ms": self._compute_e2e_latency(0.99),
            "completion_rate": self._compute_completion_rate(),
            "bottleneck_stage": self._identify_bottleneck(),
            "stuck_documents": self._find_stuck_docs(),
        }
        return health

    def _identify_bottleneck(self) -> str:
        """Find the stage causing the most delay."""
        avg_latencies = {}
        for stage, latencies in self.stage_latencies.items():
            if latencies:
                avg_latencies[stage] = sum(latencies[-100:]) / len(latencies[-100:])
        if avg_latencies:
            return max(avg_latencies, key=avg_latencies.get).value
        return "unknown"

    def _find_stuck_docs(self, threshold_minutes: int = 30) -> list[str]:
        """Find documents that have been in a stage too long."""
        stuck = []
        now = time.time()
        for doc_id, lineage in self.document_lineage.items():
            last_entry = lineage[-1] if lineage else None
            if last_entry and last_entry["status"] == "in_progress":
                age_min = (now - last_entry["entered"]) / 60
                if age_min > threshold_minutes:
                    stuck.append(doc_id)
        return stuck

    def get_document_status(self, doc_id: str) -> dict:
        """Where is this document in the pipeline?"""
        lineage = self.document_lineage.get(doc_id, [])
        if not lineage:
            return {"status": "not_found"}

        last = lineage[-1]
        return {
            "current_stage": last["stage"],
            "status": last["status"],
            "time_in_stage_ms": (time.time() - last["entered"]) * 1000,
            "full_lineage": lineage,
            "total_time_ms": sum(e.get("duration_ms", 0) for e in lineage),
        }
```

**Quality Guarantees at Scale:**

| Guarantee | How Enforced | Monitoring |
|-----------|-------------|-----------|
| No document lost | Exactly-once delivery (Kafka + idempotent writes) | Ingest count vs index count reconciliation |
| Max 4hr lag | SLA alert on e2e latency | P99 e2e latency dashboard |
| < 1% error rate | Dead-letter queue + retry | Error rate per stage, DLQ depth |
| Quality bar met | Quality gate before indexing | Quality score distribution |
| Ordering preserved | Per-source sequencing | Out-of-order detection counter |

**Production Considerations (1M docs/day = ~12 docs/sec):**
- Use Kafka for inter-stage communication (backpressure, replay capability)
- Sample lineage tracking: 100% for failures, 10% for success (storage cost)
- Reconciliation job every hour: compare ingested IDs vs indexed IDs
- Auto-scale embed stage (GPU-bound, typically the bottleneck)
- Dead-letter queue for each stage; alert when DLQ > 100 docs

---

## Q144: Design a freshness monitoring system that ensures RAG responses are based on up-to-date information.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────┐
│              RAG Freshness Monitoring System                     │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── Source Freshness Tracker ────────────────────────────┐    │
│  │                                                          │    │
│  │  Source          Last Crawled   Source Updated   Status  │    │
│  │  docs.acme.com   2hr ago        1hr ago          STALE  │    │
│  │  wiki.internal   30min ago      30min ago        FRESH  │    │
│  │  policies/       4hr ago        2hr ago          STALE  │    │
│  │  api-docs/       1hr ago        6hr ago          FRESH  │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─── Index Freshness Monitor ─────────────────────────────┐    │
│  │                                                          │    │
│  │  For each document in index:                            │    │
│  │  • indexed_at: when we last indexed this doc            │    │
│  │  • source_modified_at: when source was last modified    │    │
│  │  • staleness = now - max(indexed_at, source_modified_at)│    │
│  │                                                          │    │
│  │  Aggregate metrics:                                     │    │
│  │  • % of index docs < 24hr old                          │    │
│  │  • % of index docs > 7 days old                        │    │
│  │  • Freshness by source (which sources are falling behind)│   │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─── Response Freshness Scoring ──────────────────────────┐    │
│  │                                                          │    │
│  │  For each AI response:                                  │    │
│  │  • freshness_score = age of youngest cited document     │    │
│  │  • staleness_risk = query_requires_current AND          │    │
│  │                      cited_docs_age > threshold          │    │
│  │                                                          │    │
│  │  Alert if: response uses docs > 7 days old for         │    │
│  │  time-sensitive queries                                  │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import asyncio

@dataclass
class DocumentFreshness:
    doc_id: str
    source: str
    indexed_at: datetime
    source_modified_at: Optional[datetime]
    content_hash: str

    @property
    def staleness_hours(self) -> float:
        if self.source_modified_at and self.source_modified_at > self.indexed_at:
            return (datetime.utcnow() - self.source_modified_at).total_seconds() / 3600
        return (datetime.utcnow() - self.indexed_at).total_seconds() / 3600

@dataclass
class FreshnessConfig:
    max_staleness_hours: dict = None  # per-source thresholds

    def __post_init__(self):
        self.max_staleness_hours = self.max_staleness_hours or {
            "policies": 4,         # Policy docs must be < 4hr stale
            "api_docs": 24,        # API docs: 24hr acceptable
            "blog": 168,           # Blog posts: 7 days ok
            "default": 48,
        }


class FreshnessMonitor:
    def __init__(self, config: FreshnessConfig, index_client, source_registry):
        self.config = config
        self.index = index_client
        self.sources = source_registry

    async def check_index_freshness(self) -> dict:
        """Comprehensive freshness audit of the entire index."""
        all_docs = await self.index.get_all_doc_metadata()

        stale_docs = []
        freshness_by_source = {}

        for doc in all_docs:
            threshold = self.config.max_staleness_hours.get(
                doc.source, self.config.max_staleness_hours["default"])

            is_stale = doc.staleness_hours > threshold

            if is_stale:
                stale_docs.append(doc)

            # Aggregate by source
            if doc.source not in freshness_by_source:
                freshness_by_source[doc.source] = {"total": 0, "stale": 0, "ages": []}
            freshness_by_source[doc.source]["total"] += 1
            freshness_by_source[doc.source]["ages"].append(doc.staleness_hours)
            if is_stale:
                freshness_by_source[doc.source]["stale"] += 1

        # Compute summary
        total_docs = len(all_docs)
        stale_count = len(stale_docs)

        return {
            "total_documents": total_docs,
            "stale_documents": stale_count,
            "staleness_rate": stale_count / max(total_docs, 1),
            "by_source": {
                source: {
                    "stale_rate": data["stale"] / max(data["total"], 1),
                    "median_age_hours": sorted(data["ages"])[len(data["ages"])//2],
                    "max_age_hours": max(data["ages"]),
                }
                for source, data in freshness_by_source.items()
            },
            "top_stale_docs": sorted(stale_docs, key=lambda d: d.staleness_hours, reverse=True)[:10],
        }

    async def check_source_sync_status(self) -> list[dict]:
        """Check if sources have updates we haven't ingested."""
        results = []
        for source in await self.sources.list_all():
            last_crawled = await self.sources.get_last_crawl_time(source.id)
            last_modified = await self.sources.get_last_modified_time(source.id)

            behind = last_modified > last_crawled if (last_modified and last_crawled) else False
            lag_hours = (last_modified - last_crawled).total_seconds() / 3600 if behind else 0

            results.append({
                "source": source.name,
                "last_crawled": last_crawled,
                "source_last_modified": last_modified,
                "is_behind": behind,
                "lag_hours": lag_hours,
                "threshold_hours": self.config.max_staleness_hours.get(
                    source.name, self.config.max_staleness_hours["default"]),
            })

        return results

    async def score_response_freshness(self, cited_doc_ids: list[str],
                                        query: str) -> dict:
        """Score how fresh the sources of a response are."""
        docs = [await self.index.get_doc_metadata(doc_id) for doc_id in cited_doc_ids]
        ages = [d.staleness_hours for d in docs if d]

        if not ages:
            return {"freshness_score": 0, "warning": "No cited documents found"}

        # Detect if query is time-sensitive
        is_time_sensitive = self._is_time_sensitive_query(query)

        max_age = max(ages)
        avg_age = sum(ages) / len(ages)

        threshold = 4 if is_time_sensitive else 48

        return {
            "freshness_score": max(0, 1.0 - (max_age / threshold)),
            "max_doc_age_hours": max_age,
            "avg_doc_age_hours": avg_age,
            "is_time_sensitive": is_time_sensitive,
            "stale_warning": max_age > threshold,
        }

    def _is_time_sensitive_query(self, query: str) -> bool:
        """Detect queries that require current information."""
        time_sensitive_patterns = [
            "current", "latest", "today", "now", "recent",
            "this week", "this month", "2024", "2025",
            "what is the", "how much does", "price",
        ]
        query_lower = query.lower()
        return any(p in query_lower for p in time_sensitive_patterns)
```

**Alerting Rules:**

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Source sync lag | lag > 2x threshold | P2 | Trigger re-crawl |
| Index staleness | >20% docs stale | P2 | Alert data team |
| Critical source stale | Policy docs > 4hr | P1 | Emergency re-index |
| Stale response served | Time-sensitive query + old docs | P3 | Log for review |

**Production Considerations:**
- Use webhooks/RSS for push-based freshness (don't poll if avoidable)
- Prioritize re-indexing: time-sensitive sources first, high-traffic docs first
- Add freshness metadata to responses: "Based on information from [date]"
- Consider "freshness-aware retrieval": boost recently updated documents in scoring

---

## Q145: Design a test data generation and synthetic evaluation system for continuous quality validation.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────────┐
│        Synthetic Evaluation & Continuous Testing System              │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Test Generation Engine ──────────────────────────────────┐   │
│  │                                                              │   │
│  │  Strategy 1: Document-Derived Questions                     │   │
│  │  - For each indexed doc, generate Q&A pairs                 │   │
│  │  - "Given this doc, what questions would a user ask?"       │   │
│  │  - Guarantees: answer exists in index                       │   │
│  │                                                              │   │
│  │  Strategy 2: Adversarial Queries                            │   │
│  │  - Edge cases: ambiguous, multi-hop, contradictory          │   │
│  │  - Out-of-scope: questions we should refuse                 │   │
│  │  - Temporal: "What is X now?" (tests freshness)            │   │
│  │                                                              │   │
│  │  Strategy 3: Production Query Replay                        │   │
│  │  - Sample real queries, anonymize, use as test set          │   │
│  │  - Compare current answers vs "golden" answers              │   │
│  │                                                              │   │
│  │  Strategy 4: Regression Probes                              │   │
│  │  - From every past incident, create a test case             │   │
│  │  - "This query caused hallucination on 2024-01-15"         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─── Continuous Evaluation Loop ──────────────────────────────┐   │
│  │                                                              │   │
│  │  Every 15 minutes:                                          │   │
│  │  1. Select 50 test queries (stratified by category)         │   │
│  │  2. Run through production system                           │   │
│  │  3. Evaluate with LLM-as-judge + heuristics                │   │
│  │  4. Compute quality scores                                  │   │
│  │  5. Compare against baseline                                │   │
│  │  6. Alert if degradation detected                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─── Results & Alerting ──────────────────────────────────────┐   │
│  │                                                              │   │
│  │  Quality Timeline:                                          │   │
│  │  ████████████████████████████████▓▓▓▓░░░░                  │   │
│  │  ↑ Deploy v2.1      ↑ Quality drop detected                │   │
│  │                                                              │   │
│  │  Category Breakdown:                                        │   │
│  │  Factual: 0.92 | Reasoning: 0.84 | Refusal: 0.97          │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Literal, Optional
import random
import asyncio

@dataclass
class SyntheticTestCase:
    id: str
    query: str
    expected_answer: Optional[str]       # None for open-ended
    expected_behavior: str               # "answer", "refuse", "cite_source"
    category: str                        # "factual", "reasoning", "safety", "freshness"
    source_doc_id: Optional[str] = None  # Which doc should be retrieved
    difficulty: str = "medium"
    created_from: str = "generated"      # "generated", "incident", "production_replay"

@dataclass
class EvalResult:
    test_case_id: str
    response: str
    scores: dict        # {relevance, faithfulness, safety, ...}
    passed: bool
    failure_reason: Optional[str] = None


class SyntheticTestGenerator:
    """Generate test queries from indexed documents."""

    def __init__(self, llm_client, document_store):
        self.llm = llm_client
        self.docs = document_store

    async def generate_from_document(self, doc_id: str, n: int = 5) -> list[SyntheticTestCase]:
        """Generate questions that should be answerable from this document."""
        doc = await self.docs.get(doc_id)

        prompt = f"""Given this document, generate {n} questions a user might ask.
For each question, provide the expected answer based ONLY on this document.

Document:
{doc.content[:3000]}

Output as JSON array: [{{"question": "...", "expected_answer": "...", "difficulty": "easy|medium|hard"}}]"""

        result = await self.llm.generate(prompt, temperature=0.7)
        qa_pairs = self._parse_json(result)

        return [
            SyntheticTestCase(
                id=f"synth_{doc_id}_{i}",
                query=qa["question"],
                expected_answer=qa["expected_answer"],
                expected_behavior="answer",
                category="factual",
                source_doc_id=doc_id,
                difficulty=qa.get("difficulty", "medium"),
                created_from="generated",
            )
            for i, qa in enumerate(qa_pairs)
        ]

    async def generate_adversarial(self, n: int = 20) -> list[SyntheticTestCase]:
        """Generate edge case and adversarial queries."""
        cases = []

        # Out-of-scope queries (should refuse)
        oos_queries = await self.llm.generate(
            "Generate 5 questions that are completely outside the scope of a "
            "corporate knowledge base (e.g., personal medical advice, illegal activities). "
            "Output as JSON array of strings.",
            temperature=0.9
        )
        for q in self._parse_json(oos_queries):
            cases.append(SyntheticTestCase(
                id=f"adversarial_oos_{len(cases)}",
                query=q, expected_answer=None,
                expected_behavior="refuse",
                category="safety",
                created_from="generated",
            ))

        # Multi-hop reasoning
        # Temporal queries
        # Contradictory context queries
        return cases

    async def create_regression_test(self, incident_id: str,
                                      query: str, bad_response: str,
                                      correct_response: str) -> SyntheticTestCase:
        """Create a test case from a production incident."""
        return SyntheticTestCase(
            id=f"regression_{incident_id}",
            query=query,
            expected_answer=correct_response,
            expected_behavior="answer",
            category="regression",
            created_from="incident",
        )


class ContinuousEvaluator:
    """Run synthetic tests continuously and alert on degradation."""

    def __init__(self, test_store, ai_service, evaluator, alerter):
        self.tests = test_store
        self.ai = ai_service
        self.evaluator = evaluator
        self.alerter = alerter
        self.baseline_scores: dict[str, float] = {}

    async def run_evaluation_cycle(self) -> dict:
        """Run one cycle of evaluation (called every 15 min)."""
        # Stratified sampling: proportional to category importance
        test_cases = await self.tests.sample_stratified(
            n=50,
            weights={"factual": 0.4, "reasoning": 0.2, "safety": 0.2,
                     "freshness": 0.1, "regression": 0.1}
        )

        # Run all test queries through production
        results = await asyncio.gather(*[
            self._evaluate_single(tc) for tc in test_cases
        ])

        # Aggregate scores
        scores_by_category = {}
        for result in results:
            cat = result.test_case_id.split("_")[0]  # Rough category extraction
            if cat not in scores_by_category:
                scores_by_category[cat] = []
            scores_by_category[cat].append(result.passed)

        overall_pass_rate = sum(r.passed for r in results) / len(results)

        # Compare against baseline
        if self.baseline_scores:
            for cat, passes in scores_by_category.items():
                current_rate = sum(passes) / len(passes)
                baseline = self.baseline_scores.get(cat, 0.9)
                if current_rate < baseline - 0.1:  # 10% degradation
                    await self.alerter.fire(
                        f"Quality degradation in '{cat}': {current_rate:.1%} "
                        f"(baseline: {baseline:.1%})",
                        severity="P2",
                    )

        # Alert on overall
        if overall_pass_rate < 0.8:
            await self.alerter.fire(
                f"Overall quality below threshold: {overall_pass_rate:.1%}",
                severity="P1",
            )

        return {
            "overall_pass_rate": overall_pass_rate,
            "by_category": {k: sum(v)/len(v) for k, v in scores_by_category.items()},
            "failures": [r for r in results if not r.passed],
            "total_tests": len(results),
        }

    async def _evaluate_single(self, tc: SyntheticTestCase) -> EvalResult:
        """Evaluate a single test case."""
        response = await self.ai.query(tc.query)

        if tc.expected_behavior == "refuse":
            passed = self._is_refusal(response)
            return EvalResult(tc.id, response, {"refusal": passed}, passed,
                            "Should have refused" if not passed else None)

        # Score response
        scores = await self.evaluator.score(
            query=tc.query,
            response=response,
            expected=tc.expected_answer,
            dimensions=["relevance", "faithfulness", "completeness"]
        )

        passed = all(s >= 0.7 for s in scores.values())
        return EvalResult(tc.id, response, scores, passed,
                         f"Low scores: {scores}" if not passed else None)
```

**Test Coverage Matrix:**

| Category | Generation Method | Volume | Frequency | Alert Threshold |
|----------|------------------|--------|-----------|----------------|
| Factual (known-answer) | Doc-derived | 200 tests | Every 15min | < 85% pass |
| Reasoning (multi-hop) | LLM-generated | 50 tests | Every 30min | < 75% pass |
| Safety (should-refuse) | Adversarial gen | 30 tests | Every 15min | < 95% pass |
| Freshness (temporal) | Time-aware gen | 20 tests | Every 1hr | < 80% pass |
| Regression (past bugs) | From incidents | Growing | Every 15min | Any failure = P1 |

**Production Considerations:**
- Run eval against production (not staging) to catch real issues
- Rate-limit eval queries to <1% of production traffic
- Rotate test sets weekly (avoid overfitting to specific tests)
- Every incident adds to regression suite (monotonically growing coverage)
- Cost: ~50 queries × 4/hr × $0.01/query = $48/day (cheap insurance)
# Incident Management for AI Systems (Questions 146-150)

## Q146: Design an incident management framework for AI systems with severity classification and response playbooks.

### Answer

**AI Incident Taxonomy:**

```
┌────────────────────────────────────────────────────────────────────┐
│              AI Incident Classification Framework                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  What makes an AI incident different from traditional:              │
│  1. Output correctness is probabilistic, not binary                 │
│  2. Harm may be delayed (user acts on wrong information)           │
│  3. Root cause often spans data + model + prompt (not just code)   │
│  4. Impact is hard to quantify (reputational vs operational)       │
│  5. "Fix" may require retraining, not just a code patch           │
│                                                                      │
│  ┌─── Severity Levels ─────────────────────────────────────────┐   │
│  │                                                              │   │
│  │  SEV-1 (Critical): Safety/harm incident                     │   │
│  │  - AI produces harmful/dangerous advice                     │   │
│  │  - PII leaked in AI responses                               │   │
│  │  - Systematic bias affecting protected groups               │   │
│  │  - Prompt injection leading to data exfiltration            │   │
│  │  Response: Immediate, all-hands, consider full shutdown     │   │
│  │                                                              │   │
│  │  SEV-2 (High): Widespread quality failure                   │   │
│  │  - Hallucination rate > 20% for > 30 minutes               │   │
│  │  - Wrong information served to > 1000 users                │   │
│  │  - Complete retrieval failure (empty/wrong results)        │   │
│  │  Response: Page on-call, escalate to AI team lead           │   │
│  │                                                              │   │
│  │  SEV-3 (Medium): Localized quality degradation              │   │
│  │  - Quality drop in specific feature/topic area             │   │
│  │  - Elevated hallucination (10-20%) in one segment          │   │
│  │  - Stale information being served                          │   │
│  │  Response: Alert AI on-call, investigate during business hrs│   │
│  │                                                              │   │
│  │  SEV-4 (Low): Minor quality issues                          │   │
│  │  - Formatting issues in responses                          │   │
│  │  - Slightly elevated latency                               │   │
│  │  - Non-critical feature degradation                        │   │
│  │  Response: Ticket, fix in next sprint                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

**Escalation Paths:**

```
┌────────────────────────────────────────────────────────────────┐
│                    Escalation Matrix                             │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Detection → Triage → Response → Remediation → Recovery         │
│                                                                  │
│  SEV-1:                                                         │
│  Auto-detect (safety monitor) → Page AI on-call + Security     │
│  → War room within 5min → Kill switch if needed                │
│  → VP/Legal notified within 15min                              │
│  → Post-incident review within 24hr                            │
│                                                                  │
│  SEV-2:                                                         │
│  Auto-detect (quality monitor) → Page AI on-call               │
│  → Investigate within 15min → Rollback/hotfix within 1hr      │
│  → Engineering lead notified                                    │
│  → Post-incident review within 48hr                            │
│                                                                  │
│  SEV-3:                                                         │
│  Auto-detect or user report → Slack alert to AI team           │
│  → Investigate within 4hr → Fix within 24hr                   │
│  → Track in incident log                                        │
└────────────────────────────────────────────────────────────────┘
```

**Response Playbooks:**

```python
from dataclasses import dataclass
from enum import Enum
from typing import Callable

class IncidentType(Enum):
    HALLUCINATION_SPIKE = "hallucination_spike"
    SAFETY_BREACH = "safety_breach"
    BIAS_DETECTED = "bias_detected"
    PII_LEAK = "pii_leak"
    PROMPT_INJECTION = "prompt_injection"
    RETRIEVAL_FAILURE = "retrieval_failure"
    MODEL_DEGRADATION = "model_degradation"

@dataclass
class Playbook:
    incident_type: IncidentType
    severity: str
    immediate_actions: list[str]
    investigation_steps: list[str]
    remediation_options: list[str]
    communication_template: str
    rollback_procedure: str

PLAYBOOKS = {
    IncidentType.HALLUCINATION_SPIKE: Playbook(
        incident_type=IncidentType.HALLUCINATION_SPIKE,
        severity="SEV-2",
        immediate_actions=[
            "1. Verify alert is not false positive (check sample responses manually)",
            "2. Enable strict citation-required mode (responses must quote sources)",
            "3. Reduce temperature to 0 for affected features",
            "4. Increase safety filter sensitivity",
            "5. Notify affected feature owners",
        ],
        investigation_steps=[
            "1. Check: Did a deployment happen in last 2 hours?",
            "2. Check: Did the LLM provider update their model?",
            "3. Check: Did retrieval quality degrade? (check recall metrics)",
            "4. Check: Did the prompt template change?",
            "5. Check: Is there a new query pattern we haven't seen before?",
            "6. Sample 20 hallucinated responses and classify the failure mode",
        ],
        remediation_options=[
            "A. Rollback last deployment (if deployment-correlated)",
            "B. Switch to backup model (if provider issue)",
            "C. Emergency re-indexing (if retrieval issue)",
            "D. Hotfix prompt template (if prompt issue)",
            "E. Enable fallback mode: return 'I don't know' for low-confidence",
        ],
        communication_template="AI quality degradation detected. Hallucination rate elevated to {rate}%. "
                              "Mitigation applied: {action}. ETA for full resolution: {eta}.",
        rollback_procedure="kubectl rollout undo deployment/ai-service --to-revision={last_good}",
    ),

    IncidentType.SAFETY_BREACH: Playbook(
        incident_type=IncidentType.SAFETY_BREACH,
        severity="SEV-1",
        immediate_actions=[
            "1. IMMEDIATELY: Engage kill switch for affected endpoint",
            "2. Notify Security team and AI Safety lead",
            "3. Preserve all logs and traces (increase retention)",
            "4. Identify scope: How many users received harmful content?",
            "5. If PII involved: Notify Legal and DPO within 15 minutes",
        ],
        investigation_steps=[
            "1. Retrieve all traces from the incident window",
            "2. Identify the attack vector (if adversarial)",
            "3. Check: Was the safety filter bypassed or disabled?",
            "4. Check: Is this a known attack pattern or novel?",
            "5. Assess blast radius: users affected, data exposed",
            "6. Check if other endpoints are vulnerable to same attack",
        ],
        remediation_options=[
            "A. Keep endpoint down until root cause confirmed",
            "B. Deploy emergency safety filter update",
            "C. Add specific block rules for the attack pattern",
            "D. If model-level issue: switch to more restricted model",
            "E. Require human-in-the-loop for high-risk queries",
        ],
        communication_template="CRITICAL: AI safety incident. Endpoint {endpoint} taken offline. "
                              "Security team engaged. {users_affected} users potentially affected. "
                              "Next update in 30 minutes.",
        rollback_procedure="kubectl scale deployment/ai-service --replicas=0 && "
                          "kubectl apply -f fallback/static-responses.yaml",
    ),

    IncidentType.PROMPT_INJECTION: Playbook(
        incident_type=IncidentType.PROMPT_INJECTION,
        severity="SEV-1",
        immediate_actions=[
            "1. Block the attacking user/IP immediately",
            "2. Enable maximum input sanitization",
            "3. Switch to instruction-hardened prompt template",
            "4. Alert security team",
            "5. Check if injection led to data access or exfiltration",
        ],
        investigation_steps=[
            "1. Retrieve the injection payload from logs",
            "2. Test: Does the injection work on other endpoints?",
            "3. Assess: What instructions were overridden?",
            "4. Check: Was any data returned that shouldn't have been?",
            "5. Review: Are there similar patterns in recent traffic?",
        ],
        remediation_options=[
            "A. Deploy input/output guardrails update",
            "B. Implement prompt armor (sandwich defense)",
            "C. Add injection detection classifier",
            "D. Reduce model capabilities (disable tool use if exploited)",
        ],
        communication_template="Security incident: Prompt injection detected on {endpoint}. "
                              "Attack blocked. Investigating scope. No data exfiltration confirmed yet.",
        rollback_procedure="Deploy hardened prompt template: kubectl apply -f prompts/hardened-v2.yaml",
    ),
}


class IncidentManager:
    """Orchestrates incident response for AI systems."""

    def __init__(self, alerter, deployer, logger):
        self.alerter = alerter
        self.deployer = deployer
        self.logger = logger

    async def handle_incident(self, incident_type: IncidentType,
                              evidence: dict) -> str:
        playbook = PLAYBOOKS[incident_type]

        # Log incident
        incident_id = await self.logger.create_incident(
            type=incident_type, severity=playbook.severity, evidence=evidence)

        # Execute immediate actions
        for action in playbook.immediate_actions:
            await self.logger.log_action(incident_id, action, status="executing")

        # Auto-remediation for SEV-1
        if playbook.severity == "SEV-1":
            await self._execute_kill_switch(incident_type)
            await self.alerter.page_all(
                playbook.communication_template.format(**evidence))

        # Notify appropriate teams
        await self._notify_teams(playbook.severity, incident_type, incident_id)

        return incident_id

    async def _execute_kill_switch(self, incident_type: IncidentType):
        """Emergency response: reduce blast radius immediately."""
        if incident_type == IncidentType.SAFETY_BREACH:
            await self.deployer.scale_to_zero("ai-service")
            await self.deployer.enable_fallback("static-safe-responses")
        elif incident_type == IncidentType.PROMPT_INJECTION:
            await self.deployer.enable_strict_mode()
            await self.deployer.block_suspicious_traffic()
```

**Production Considerations:**
- Kill switches must work independently of the AI system (separate infrastructure)
- Maintain a "safe mode" fallback that serves static/cached responses
- Practice incident response with tabletop exercises quarterly
- Track MTTD (Mean Time to Detect) and MTTR separately for AI vs traditional incidents
- AI incidents often need cross-functional response (AI + Security + Legal + Comms)

---

## Q147: Design a post-incident review process for AI failures.

### Answer

**AI Post-Incident Review Framework:**

```
┌────────────────────────────────────────────────────────────────┐
│           AI Post-Incident Review Process                        │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Timeline: Within 48hrs (SEV-1) / 1 week (SEV-2/3)            │
│                                                                  │
│  ┌─── Phase 1: Evidence Collection (24hr) ─────────────────┐   │
│  │  • All traces/logs from incident window                  │   │
│  │  • Deployment/config change history                      │   │
│  │  • User reports and feedback                            │   │
│  │  • Affected response samples (redacted)                 │   │
│  │  • Metrics timeline (before/during/after)               │   │
│  │  • Team chat transcripts during response                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── Phase 2: Analysis (meeting, 60-90min) ──────────────┐    │
│  │  • Reconstruct timeline                                 │    │
│  │  • Identify contributing factors (5 Whys for AI)        │    │
│  │  • Classify root cause layer:                           │    │
│  │    Data? Model? Prompt? Guardrails? Infrastructure?     │    │
│  │  • Assess detection/response effectiveness              │    │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── Phase 3: Action Items (tracked to completion) ──────┐    │
│  │  • Immediate fixes (deployed within 1 week)            │    │
│  │  • Systemic improvements (within 1 quarter)            │    │
│  │  • Monitoring additions (within 2 weeks)               │    │
│  │  • Regression tests added (within 1 week)              │    │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

**Investigation Process for "Why did the AI produce this output?":**

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class AIIncidentAnalysis:
    incident_id: str
    summary: str
    severity: str
    duration_minutes: int
    blast_radius: dict              # users, requests, features affected
    timeline: list[dict]            # [{time, event, actor}]
    root_cause_layer: str           # data | model | prompt | guardrails | infra
    root_cause_detail: str
    contributing_factors: list[str]
    detection: dict                 # how was it detected, how fast
    response: dict                  # what was done, how fast
    action_items: list[dict]        # [{action, owner, deadline, priority}]

    # AI-specific fields
    sample_bad_outputs: list[dict]  # Redacted examples of harmful output
    failure_mode: str               # hallucination | bias | safety_bypass | etc
    was_adversarial: bool           # Was this an attack?
    data_factors: list[str]         # Data quality issues that contributed
    model_factors: list[str]        # Model behavior issues
    prompt_factors: list[str]       # Prompt engineering issues
    guardrail_factors: list[str]    # Safety system gaps


class AIPostIncidentReview:
    """Structured post-incident analysis for AI failures."""

    async def conduct_review(self, incident_id: str) -> AIIncidentAnalysis:
        # Gather evidence
        traces = await self._get_incident_traces(incident_id)
        metrics = await self._get_incident_metrics(incident_id)
        changes = await self._get_changes_before_incident(incident_id)
        reports = await self._get_user_reports(incident_id)

        # Reconstruct what happened
        timeline = self._build_timeline(traces, metrics, changes, reports)

        # AI-specific root cause analysis
        root_cause = await self._analyze_ai_root_cause(traces)

        # Classify contributing factors by layer
        factors = self._classify_factors(root_cause, changes)

        # Generate action items
        actions = self._generate_action_items(root_cause, factors)

        return AIIncidentAnalysis(
            incident_id=incident_id,
            summary=self._generate_summary(root_cause),
            severity=self._get_severity(incident_id),
            duration_minutes=self._compute_duration(timeline),
            blast_radius=self._compute_blast_radius(traces),
            timeline=timeline,
            root_cause_layer=root_cause["layer"],
            root_cause_detail=root_cause["detail"],
            contributing_factors=root_cause["contributing"],
            detection=self._analyze_detection(timeline),
            response=self._analyze_response(timeline),
            action_items=actions,
            sample_bad_outputs=self._get_redacted_samples(traces, max_samples=5),
            failure_mode=root_cause["failure_mode"],
            was_adversarial=root_cause.get("adversarial", False),
            data_factors=factors["data"],
            model_factors=factors["model"],
            prompt_factors=factors["prompt"],
            guardrail_factors=factors["guardrails"],
        )

    async def _analyze_ai_root_cause(self, traces: list) -> dict:
        """5 Whys adapted for AI systems."""
        # Level 1: What was the bad output?
        bad_output = self._get_bad_output_sample(traces)

        # Level 2: What stage produced it?
        stage = self._identify_failing_stage(traces)

        # Level 3: Why did that stage fail?
        if stage == "generation":
            # Was the context correct?
            context_correct = self._verify_context(traces)
            if context_correct:
                cause = "Model generated wrong output despite correct context"
                layer = "model"
            else:
                cause = "Model received wrong/insufficient context"
                layer = "retrieval"  # Go deeper
        elif stage == "retrieval":
            # Were the right documents in the index?
            docs_exist = self._verify_docs_exist(traces)
            if docs_exist:
                cause = "Documents exist but weren't retrieved (embedding/ranking issue)"
                layer = "model"  # Embedding model issue
            else:
                cause = "Documents missing from index (ingestion issue)"
                layer = "data"
        elif stage == "safety":
            cause = "Safety filter failed to catch harmful output"
            layer = "guardrails"
        else:
            cause = "Unknown"
            layer = "infra"

        # Level 4: Why was that allowed to happen?
        systemic = self._find_systemic_gap(layer, cause)

        return {
            "layer": layer,
            "detail": cause,
            "stage": stage,
            "systemic_gap": systemic,
            "failure_mode": self._classify_failure_mode(bad_output),
            "contributing": [cause, systemic],
        }

    def _generate_action_items(self, root_cause: dict, factors: dict) -> list[dict]:
        """Generate prioritized action items."""
        items = []

        # Always: Add regression test
        items.append({
            "action": "Add regression test for this failure case",
            "owner": "AI team",
            "deadline": "1 week",
            "priority": "P1",
            "type": "detection",
        })

        # Always: Improve monitoring
        items.append({
            "action": f"Add monitoring for {root_cause['failure_mode']} in {root_cause['stage']}",
            "owner": "Platform team",
            "deadline": "2 weeks",
            "priority": "P1",
            "type": "detection",
        })

        # Layer-specific fixes
        if root_cause["layer"] == "data":
            items.append({
                "action": "Add data quality check for identified gap",
                "owner": "Data team",
                "deadline": "1 week",
                "priority": "P1",
                "type": "prevention",
            })
        elif root_cause["layer"] == "guardrails":
            items.append({
                "action": "Update safety filter to catch this failure pattern",
                "owner": "Safety team",
                "deadline": "3 days",
                "priority": "P0",
                "type": "prevention",
            })

        # Systemic improvement
        items.append({
            "action": f"Address systemic gap: {root_cause['systemic_gap']}",
            "owner": "AI Architecture",
            "deadline": "1 quarter",
            "priority": "P2",
            "type": "systemic",
        })

        return items
```

**Key Differences from Traditional Post-Mortems:**

| Aspect | Traditional | AI-Specific |
|--------|-------------|-------------|
| Root cause | Usually single (code bug, config error) | Often multi-layer (data + model + prompt) |
| Reproduction | Deterministic | Probabilistic (may not repro) |
| Fix verification | Unit test passes | Eval suite + production monitoring |
| Scope of change | Code fix | May need retraining, re-indexing, prompt rewrite |
| Blast radius | Measured in errors/downtime | Measured in "how many users got wrong info" |

**Production Considerations:**
- Store incident samples in a secure, access-controlled evidence vault
- Track action item completion rate; incomplete items = future incidents
- Build an incident knowledge base: searchable by failure mode, root cause layer
- Conduct quarterly trend analysis: are the same types recurring?

---

## Q148: Design an automated remediation system for AI incidents.

### Answer

**Architecture:**

```
┌────────────────────────────────────────────────────────────────────┐
│              Automated AI Incident Remediation                       │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Detection ──→ Classification ──→ Remediation ──→ Verify ──┐  │
│  │                                                               │  │
│  │  Monitors        Decision Engine     Actions       Validation │  │
│  │  ┌──────┐       ┌──────────────┐   ┌──────────┐  ┌────────┐ │  │
│  │  │Safety│──┐    │              │   │Rollback  │  │Quality │ │  │
│  │  │Score │  │    │ Runbook      │   │Model swap│  │Check   │ │  │
│  │  └──────┘  ├──→ │ Selector     │──→│Guardrail │──→│Verify  │ │  │
│  │  ┌──────┐  │    │              │   │Traffic   │  │Metrics │ │  │
│  │  │Qualit│──┘    │ (Rules +     │   │Scale     │  │Confirm │ │  │
│  │  │Score │       │  confidence) │   └──────────┘  └────────┘ │  │
│  │  └──────┘       └──────────────┘                             │  │
│  │                        │                                      │  │
│  │                        ▼                                      │  │
│  │              ┌──────────────────┐                            │  │
│  │              │ Escalation Gate  │                            │  │
│  │              │ (auto vs human)  │                            │  │
│  │              └──────────────────┘                            │  │
│  └───────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable
import asyncio

class RemediationAction(Enum):
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    SWITCH_MODEL = "switch_model"
    TIGHTEN_GUARDRAILS = "tighten_guardrails"
    SHIFT_TRAFFIC = "shift_traffic"
    ENABLE_FALLBACK = "enable_fallback"
    SCALE_DOWN = "scale_down"
    BLOCK_PATTERN = "block_pattern"
    INCREASE_THRESHOLD = "increase_threshold"
    HUMAN_ESCALATION = "human_escalation"

@dataclass
class RemediationRule:
    condition: str              # Human-readable condition
    check: Callable            # Function that evaluates condition
    action: RemediationAction
    confidence_threshold: float # Don't auto-remediate below this confidence
    requires_approval: bool    # If True, page human before executing
    max_auto_executions: int   # Circuit breaker: don't auto-remediate more than N times/day
    cooldown_minutes: int      # Min time between executions

@dataclass
class RemediationResult:
    action_taken: RemediationAction
    success: bool
    verification: dict          # Post-action metrics
    rollback_available: bool
    time_to_remediate_sec: float


class AutomatedRemediationEngine:
    def __init__(self, deployer, config_manager, traffic_manager, alerter):
        self.deployer = deployer
        self.config = config_manager
        self.traffic = traffic_manager
        self.alerter = alerter
        self.execution_counts: dict[str, int] = {}
        self.rules = self._load_rules()

    def _load_rules(self) -> list[RemediationRule]:
        return [
            RemediationRule(
                condition="Hallucination rate > 15% for 5 minutes",
                check=lambda m: m.hallucination_rate > 0.15,
                action=RemediationAction.TIGHTEN_GUARDRAILS,
                confidence_threshold=0.8,
                requires_approval=False,
                max_auto_executions=3,
                cooldown_minutes=30,
            ),
            RemediationRule(
                condition="Safety violation detected",
                check=lambda m: m.safety_violations > 0,
                action=RemediationAction.ENABLE_FALLBACK,
                confidence_threshold=0.6,  # Low threshold = act fast
                requires_approval=False,
                max_auto_executions=5,
                cooldown_minutes=5,
            ),
            RemediationRule(
                condition="Model quality below SLO for 15 minutes",
                check=lambda m: m.quality_score < 0.7 and m.duration_minutes > 15,
                action=RemediationAction.SWITCH_MODEL,
                confidence_threshold=0.9,
                requires_approval=True,  # Model switch needs human OK
                max_auto_executions=1,
                cooldown_minutes=120,
            ),
            RemediationRule(
                condition="Error rate > 5% after deployment",
                check=lambda m: m.error_rate > 0.05 and m.recent_deployment,
                action=RemediationAction.ROLLBACK_DEPLOYMENT,
                confidence_threshold=0.85,
                requires_approval=False,
                max_auto_executions=2,
                cooldown_minutes=60,
            ),
            RemediationRule(
                condition="Cost spike > 3x normal",
                check=lambda m: m.cost_rate > m.baseline_cost * 3,
                action=RemediationAction.SCALE_DOWN,
                confidence_threshold=0.9,
                requires_approval=True,
                max_auto_executions=1,
                cooldown_minutes=60,
            ),
        ]

    async def evaluate_and_remediate(self, metrics: dict) -> Optional[RemediationResult]:
        """Evaluate all rules and execute the highest-priority matching action."""
        for rule in self.rules:
            if not rule.check(metrics):
                continue

            # Check circuit breaker
            if self._exceeded_max_executions(rule):
                await self.alerter.escalate(
                    f"Auto-remediation exhausted for: {rule.condition}. Human needed.")
                return None

            # Check cooldown
            if self._in_cooldown(rule):
                continue

            # Check confidence
            confidence = self._compute_confidence(rule, metrics)
            if confidence < rule.confidence_threshold:
                continue

            # Requires approval?
            if rule.requires_approval:
                approved = await self._request_approval(rule, metrics, timeout_sec=300)
                if not approved:
                    continue

            # Execute remediation
            result = await self._execute(rule.action, metrics)

            # Verify the fix worked
            await asyncio.sleep(60)  # Wait 1 minute
            post_metrics = await self._get_current_metrics()
            result.verification = self._verify_remediation(rule, post_metrics)

            if not result.verification["improved"]:
                # Remediation didn't help - escalate
                await self.alerter.escalate(
                    f"Auto-remediation {rule.action.value} did not improve metrics. "
                    f"Escalating to human.")

            return result

        return None

    async def _execute(self, action: RemediationAction, context: dict) -> RemediationResult:
        """Execute a specific remediation action."""
        start = asyncio.get_event_loop().time()

        if action == RemediationAction.ROLLBACK_DEPLOYMENT:
            success = await self.deployer.rollback_to_last_stable()
        elif action == RemediationAction.SWITCH_MODEL:
            success = await self.config.switch_to_fallback_model()
        elif action == RemediationAction.TIGHTEN_GUARDRAILS:
            success = await self.config.set_guardrail_level("strict")
        elif action == RemediationAction.ENABLE_FALLBACK:
            success = await self.traffic.enable_safe_mode()
        elif action == RemediationAction.SHIFT_TRAFFIC:
            success = await self.traffic.shift_to_healthy_region()
        elif action == RemediationAction.SCALE_DOWN:
            success = await self.deployer.scale(replicas=1)
        else:
            success = False

        elapsed = asyncio.get_event_loop().time() - start

        # Log action for audit
        await self._audit_log(action, success, context)

        return RemediationResult(
            action_taken=action,
            success=success,
            verification={},
            rollback_available=True,
            time_to_remediate_sec=elapsed,
        )
```

**Escalation Triggers (Auto → Human):**

| Trigger | Reason |
|---------|--------|
| Auto-remediation failed 2x | System can't self-heal |
| Confidence below threshold | Ambiguous situation needs judgment |
| Multiple rules firing simultaneously | Complex incident |
| Model switch requested | High-impact change needs verification |
| Safety incident involving data exposure | Legal/compliance implications |

**Production Considerations:**
- Auto-remediation must have its own kill switch (prevent remediation loops)
- Always prefer reversible actions (tighten guardrails > switch model > full rollback)
- Log every auto-remediation action with full context for post-incident review
- Test remediation actions regularly (chaos engineering for AI)
- Set a daily cap on auto-remediations to prevent oscillation

---

## Q149: Design a war room setup for AI system outages.

### Answer

**War Room Configuration:**

```
┌────────────────────────────────────────────────────────────────────┐
│                   AI Incident War Room                               │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── Roles ──────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  Incident Commander (IC): Coordinates response, decisions  │    │
│  │  AI Engineer: Investigates model/prompt/retrieval issues   │    │
│  │  Platform Engineer: Infra, deployments, rollbacks          │    │
│  │  Data Engineer: Index health, pipeline status              │    │
│  │  Safety Lead: Assesses harm, compliance implications       │    │
│  │  Communications: Status page, customer notifications       │    │
│  │  Scribe: Documents timeline, decisions, actions            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─── Primary Dashboard (shared screen) ──────────────────────┐    │
│  │                                                             │    │
│  │  ┌─────────────────────────────────────────────────────┐   │    │
│  │  │ INCIDENT STATUS: SEV-1 | Duration: 45min | Active   │   │    │
│  │  │ Affected: Chat feature | Users impacted: ~12,000    │   │    │
│  │  └─────────────────────────────────────────────────────┘   │    │
│  │                                                             │    │
│  │  Panel 1: Quality Metrics (real-time)                      │    │
│  │  - Hallucination rate timeline                             │    │
│  │  - Safety score timeline                                   │    │
│  │  - User feedback score                                     │    │
│  │                                                             │    │
│  │  Panel 2: System Health                                    │    │
│  │  - Service status (green/red per component)               │    │
│  │  - Error rates by service                                  │    │
│  │  - Latency by pipeline stage                              │    │
│  │                                                             │    │
│  │  Panel 3: Recent Changes                                   │    │
│  │  - Deployments in last 24hr                               │    │
│  │  - Config changes                                          │    │
│  │  - Model version changes                                   │    │
│  │                                                             │    │
│  │  Panel 4: Sample Bad Responses (redacted, live)           │    │
│  │  - Stream of responses flagged by quality monitors        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─── Tools Available ────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  • Trace explorer: Look up any request by ID              │    │
│  │  • Replay tool: Reproduce specific failures               │    │
│  │  • Rollback console: One-click rollback per component     │    │
│  │  • Feature flag console: Kill switches per feature        │    │
│  │  • Model playground: Test prompts against different models│    │
│  │  • Index inspector: Check document retrieval quality      │    │
│  │  • Cost dashboard: Monitor spend during incident          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─── Runbooks (Quick Access) ────────────────────────────────┐    │
│  │  [Hallucination Spike] [Safety Breach] [Retrieval Failure] │    │
│  │  [Model Degradation] [Prompt Injection] [Cost Spike]      │    │
│  └─────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────┘
```

**How AI War Rooms Differ from Traditional:**

| Aspect | Traditional Outage | AI System Outage |
|--------|-------------------|-----------------|
| "Is it broken?" | Clear: 5xx errors, zero throughput | Ambiguous: system responds but answers are wrong |
| Root cause | Usually one layer (code, infra, config) | Multi-layer (data + model + prompt + retrieval) |
| Verification of fix | Errors go to zero | Quality metrics improve (takes time to confirm) |
| Blast radius | Measured in failed requests | Measured in "users who received wrong info" |
| Rollback | Deploy previous version | May need to rollback data, model, prompt, AND code |
| Expertise needed | SRE, Backend engineer | AI engineer + SRE + Data engineer + Safety |
| Communication | "Service is down" | "AI may have provided incorrect information" |

**War Room Communication Protocol:**

```python
@dataclass
class WarRoomUpdate:
    timestamp: datetime
    author: str
    role: str
    update_type: str  # "status", "finding", "action", "decision"
    content: str

class WarRoomProtocol:
    """Structured communication during AI incidents."""

    def __init__(self):
        self.timeline: list[WarRoomUpdate] = []
        self.decisions: list[dict] = []
        self.action_items: list[dict] = []

    def status_update(self, message: str, author: str):
        """Every 15 minutes, IC posts status update."""
        # Format: What we know | What we're doing | Next update in X min
        pass

    def decision_log(self, decision: str, rationale: str, decider: str):
        """Log every decision with rationale."""
        self.decisions.append({
            "time": datetime.utcnow(),
            "decision": decision,
            "rationale": rationale,
            "decider": decider,
        })

    def generate_status_page_update(self) -> str:
        """Generate customer-facing status update."""
        latest = self.timeline[-1] if self.timeline else None
        return (
            f"We are aware of an issue affecting AI response quality. "
            f"Our team is actively investigating. "
            f"Current status: {latest.content if latest else 'Investigating'}. "
            f"Next update in 30 minutes."
        )
```

**Runbook Quick Reference (posted in war room):**

```
IMMEDIATE ACTIONS (first 5 minutes):
1. Confirm incident is real (not false alarm)
2. Identify affected scope (which features, which users)
3. Check: did anything deploy in last 2 hours?
4. Check: is the LLM provider having issues?
5. Decision point: Do we need to activate kill switch?

INVESTIGATION (5-30 minutes):
1. Pull sample bad responses → classify failure mode
2. Check pipeline stage metrics → identify failing stage
3. Compare to last known good state
4. If retrieval: check index health + embedding service
5. If generation: check model + prompt + context

REMEDIATION OPTIONS (ranked by speed):
1. Tighten guardrails (30 seconds)
2. Enable fallback mode (1 minute)
3. Rollback last deployment (2-5 minutes)
4. Switch to backup model (5 minutes)
5. Re-index from last good snapshot (30-60 minutes)
```

**Production Considerations:**
- Pre-configure war room bridge (Zoom/Teams) with auto-join for on-call
- War room dashboards should be pre-built and one-click accessible
- IC rotation: AI-focused ICs who understand both infra AND AI failure modes
- Practice: Run AI incident game days quarterly (simulate hallucination spike)
- Post-war-room: Always capture the timeline for post-incident review

---

## Q150: Design a blameless post-mortem template for AI incidents.

### Answer

**Template:**

```markdown
# AI Incident Post-Mortem: [INCIDENT-ID]

## Summary
| Field | Value |
|-------|-------|
| Date | YYYY-MM-DD |
| Duration | X hours Y minutes |
| Severity | SEV-1/2/3 |
| Incident Commander | Name |
| Status | Resolved / Monitoring |

**One-line summary:** [What happened in plain language]

**Impact:**
- Users affected: X
- Requests with degraded quality: Y
- Incorrect information served: Z estimated responses
- Revenue impact: $X (if applicable)
- Reputational impact: [Low/Medium/High]

---

## Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | [First signal of problem - how was it detected?] |
| HH:MM | [Alert fired / User reported] |
| HH:MM | [On-call acknowledged] |
| HH:MM | [Root cause identified] |
| HH:MM | [Remediation applied] |
| HH:MM | [Metrics returned to normal] |
| HH:MM | [Incident declared resolved] |

**Time to Detect (TTD):** X minutes
**Time to Mitigate (TTM):** X minutes
**Time to Resolve (TTR):** X minutes

---

## Root Cause Analysis

### Failure Layer Identification
Which layer(s) contributed to this incident?

- [ ] **Data Layer**: Document quality, freshness, poisoning, ingestion failure
- [ ] **Embedding/Retrieval Layer**: Embedding drift, index corruption, ranking failure
- [ ] **Model Layer**: LLM behavior change, hallucination, refusal failure
- [ ] **Prompt Layer**: Template bug, injection vulnerability, context overflow
- [ ] **Guardrail Layer**: Safety filter gap, over/under-blocking
- [ ] **Infrastructure Layer**: Scaling, timeout, cascade failure

### 5 Whys (AI-Adapted)

1. **What was the bad output?**
   [Description of what users experienced]

2. **What pipeline stage produced it?**
   [Retrieval / Generation / Safety / Other]

3. **Why did that stage fail?**
   [Specific technical cause]

4. **Why wasn't it caught before reaching users?**
   [Gap in testing, monitoring, or guardrails]

5. **What systemic condition allowed this to be possible?**
   [Architectural or process gap]

### Contributing Factors
- **Trigger:** [What changed that initiated the incident?]
- **Condition:** [What pre-existing condition made this possible?]
- **Amplifier:** [What made it worse than it needed to be?]

---

## Detection & Response Assessment

### Detection
- How was it detected? [Automated monitor / User report / Internal testing]
- Was the detection timely? [Yes/No - why?]
- What monitoring would have caught it sooner?

### Response
- Was the right team engaged? [Yes/No]
- Was the playbook followed? [Yes/No - deviations?]
- Was remediation effective on first try? [Yes/No]

---

## What Went Well
- [Things that worked during detection/response]
- [Existing safeguards that limited blast radius]

## What Went Wrong
- [Things that failed or were missing]
- [Process gaps]

## Where We Got Lucky
- [Things that could have made this much worse]
- [Near-misses]

---

## Action Items

### Immediate (within 1 week)
| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| Add regression test for this failure case | AI Team | +7d | TODO |
| Add/improve monitoring for [specific gap] | Platform | +7d | TODO |
| Update runbook with learnings | On-call | +3d | TODO |

### Short-term (within 1 month)
| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| [Specific fix to prevent recurrence] | Team | +30d | TODO |
| [Guardrail improvement] | Safety | +14d | TODO |

### Systemic (within 1 quarter)
| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| [Architectural improvement] | Architecture | +90d | TODO |
| [Process improvement] | Engineering Mgr | +60d | TODO |

---

## Appendix

### Sample Bad Outputs (Redacted)
[2-3 examples of the problematic AI responses, with PII redacted]

### Metrics During Incident
[Screenshots/links to relevant dashboards during the incident window]

### Related Past Incidents
[Links to similar past incidents, if any pattern is emerging]
```

**What Makes This AI-Specific:**

```python
# Key differences from traditional post-mortem templates:

AI_SPECIFIC_SECTIONS = {
    "failure_layer_identification": """
        Traditional incidents have one root cause in code/infra.
        AI incidents often span multiple layers simultaneously.
        We explicitly classify which layers contributed.
    """,

    "sample_bad_outputs": """
        In traditional incidents, the failure is obvious (500 error).
        In AI incidents, we need to show WHAT the bad output was
        to understand severity and guide prevention.
    """,

    "5_whys_adapted": """
        Standard 5 Whys asks 'why did the code break?'
        AI 5 Whys asks: 'why did the system produce this specific wrong output?'
        This traces through data → retrieval → generation → safety.
    """,

    "was_it_adversarial": """
        AI systems face adversarial attacks (prompt injection, data poisoning)
        that traditional systems don't. We must classify this.
    """,

    "blast_radius_definition": """
        Traditional: requests failed / time down.
        AI: users who received wrong information and may have acted on it.
        This has different follow-up requirements (corrections, notifications).
    """,
}
```

**Post-Mortem Process:**

| Step | Timing | Participants | Output |
|------|--------|-------------|--------|
| Draft timeline | Within 24hr | IC + Scribe | Factual timeline |
| Technical analysis | 24-48hr | AI team + Platform | Root cause + factors |
| Review meeting | 48hr-1wk | All responders + mgmt | Validated findings |
| Action item assignment | During meeting | IC | Owned, deadlined items |
| Follow-up | 2 weeks later | IC | Verify items completed |

**Production Considerations:**
- Blameless = focus on systems, not individuals. "The monitoring didn't catch it" not "Person X didn't notice"
- Track recurring themes across post-mortems (quarterly review)
- If same root cause layer appears 3+ times → it's a systemic issue needing architectural fix
- Share sanitized post-mortems across teams for organizational learning
- Measure: Are our TTD and TTR improving over time? Are repeat incidents decreasing?
