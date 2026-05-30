"""
Module 12: AI Observability - Metrics Collection System

Prometheus-style metrics for AI systems: token usage, cost, latency,
quality scores, error rates, cache performance, and per-tenant tracking.
"""

import time
import threading
import json
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    Info,
    CollectorRegistry,
    generate_latest,
    start_http_server,
    REGISTRY,
)


# =============================================================================
# METRIC REGISTRY & CONFIGURATION
# =============================================================================

@dataclass
class MetricsConfig:
    namespace: str = "ai"
    subsystem: str = "agent"
    port: int = 9090
    enable_per_tenant: bool = True
    cost_alert_threshold_hourly: float = 50.0
    latency_buckets: tuple = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
    token_buckets: tuple = (50, 100, 250, 500, 1000, 2500, 5000, 10000, 50000, 100000)
    score_buckets: tuple = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


class AIMetricsRegistry:
    """
    Central registry for all AI observability metrics.
    Organizes metrics by category with consistent labeling.
    """

    def __init__(self, config: MetricsConfig = None, registry: CollectorRegistry = None):
        self.config = config or MetricsConfig()
        self.registry = registry or REGISTRY
        self._setup_metrics()

    def _setup_metrics(self):
        ns = self.config.namespace
        sub = self.config.subsystem
        lat_buckets = self.config.latency_buckets
        tok_buckets = self.config.token_buckets
        score_buckets = self.config.score_buckets

        # =====================================================================
        # REQUEST METRICS
        # =====================================================================
        self.requests_total = Counter(
            f"{ns}_{sub}_requests_total",
            "Total AI requests",
            ["tenant_id", "request_type", "status"],
            registry=self.registry,
        )

        self.request_latency = Histogram(
            f"{ns}_{sub}_request_latency_seconds",
            "End-to-end request latency",
            ["tenant_id", "request_type"],
            buckets=lat_buckets,
            registry=self.registry,
        )

        self.active_requests = Gauge(
            f"{ns}_{sub}_active_requests",
            "Currently processing requests",
            ["tenant_id"],
            registry=self.registry,
        )

        # =====================================================================
        # TOKEN USAGE METRICS
        # =====================================================================
        self.tokens_input = Counter(
            f"{ns}_{sub}_tokens_input_total",
            "Total input tokens consumed",
            ["model", "tenant_id"],
            registry=self.registry,
        )

        self.tokens_output = Counter(
            f"{ns}_{sub}_tokens_output_total",
            "Total output tokens generated",
            ["model", "tenant_id"],
            registry=self.registry,
        )

        self.tokens_per_request = Histogram(
            f"{ns}_{sub}_tokens_per_request",
            "Total tokens (input+output) per request",
            ["model", "tenant_id"],
            buckets=tok_buckets,
            registry=self.registry,
        )

        # =====================================================================
        # COST METRICS
        # =====================================================================
        self.cost_total = Counter(
            f"{ns}_{sub}_cost_usd_total",
            "Total cost in USD",
            ["model", "tenant_id"],
            registry=self.registry,
        )

        self.cost_per_request = Histogram(
            f"{ns}_{sub}_cost_per_request_usd",
            "Cost per request in USD",
            ["model", "tenant_id", "request_type"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0),
            registry=self.registry,
        )

        self.cost_hourly = Gauge(
            f"{ns}_{sub}_cost_hourly_usd",
            "Rolling hourly cost estimate",
            ["tenant_id"],
            registry=self.registry,
        )

        # =====================================================================
        # LATENCY BREAKDOWN METRICS (per component)
        # =====================================================================
        self.component_latency = Histogram(
            f"{ns}_{sub}_component_latency_seconds",
            "Latency per pipeline component",
            ["component", "tenant_id"],  # component: retrieval, rerank, llm, tool, guardrail
            buckets=lat_buckets,
            registry=self.registry,
        )

        self.llm_time_to_first_token = Histogram(
            f"{ns}_{sub}_ttft_seconds",
            "Time to first token for streaming",
            ["model", "tenant_id"],
            buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
            registry=self.registry,
        )

        # =====================================================================
        # QUALITY METRICS
        # =====================================================================
        self.groundedness_score = Histogram(
            f"{ns}_{sub}_groundedness_score",
            "Groundedness score distribution",
            ["tenant_id"],
            buckets=score_buckets,
            registry=self.registry,
        )

        self.relevance_score = Histogram(
            f"{ns}_{sub}_relevance_score",
            "Answer relevance score distribution",
            ["tenant_id"],
            buckets=score_buckets,
            registry=self.registry,
        )

        self.retrieval_score = Histogram(
            f"{ns}_{sub}_retrieval_score",
            "Retrieval relevance score distribution (top-k scores)",
            ["tenant_id", "index"],
            buckets=score_buckets,
            registry=self.registry,
        )

        self.feedback_score = Histogram(
            f"{ns}_{sub}_feedback_score",
            "User feedback score distribution",
            ["tenant_id", "feedback_type"],  # thumbs, rating, etc.
            buckets=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
            registry=self.registry,
        )

        self.feedback_total = Counter(
            f"{ns}_{sub}_feedback_total",
            "Total feedback received",
            ["tenant_id", "sentiment"],  # positive, negative, neutral
            registry=self.registry,
        )

        # =====================================================================
        # ERROR METRICS
        # =====================================================================
        self.errors_total = Counter(
            f"{ns}_{sub}_errors_total",
            "Total errors by type",
            ["error_type", "tenant_id", "component"],
            # error_type: model_error, tool_error, guardrail_block, timeout, rate_limit
            registry=self.registry,
        )

        self.retries_total = Counter(
            f"{ns}_{sub}_retries_total",
            "Total retries",
            ["component", "tenant_id", "reason"],
            registry=self.registry,
        )

        self.timeouts_total = Counter(
            f"{ns}_{sub}_timeouts_total",
            "Total timeouts",
            ["component", "tenant_id"],
            registry=self.registry,
        )

        self.loops_detected = Counter(
            f"{ns}_{sub}_loops_detected_total",
            "Agent loops detected and terminated",
            ["tenant_id"],
            registry=self.registry,
        )

        # =====================================================================
        # GUARDRAIL METRICS
        # =====================================================================
        self.guardrail_decisions = Counter(
            f"{ns}_{sub}_guardrail_decisions_total",
            "Guardrail decisions by outcome",
            ["guardrail_name", "decision", "tenant_id"],
            # decision: allow, block, warn, modify
            registry=self.registry,
        )

        self.safety_block_rate = Gauge(
            f"{ns}_{sub}_safety_block_rate",
            "Rolling safety block rate",
            ["tenant_id"],
            registry=self.registry,
        )

        # =====================================================================
        # TOOL METRICS
        # =====================================================================
        self.tool_calls_total = Counter(
            f"{ns}_{sub}_tool_calls_total",
            "Total tool calls",
            ["tool_name", "status", "tenant_id"],
            registry=self.registry,
        )

        self.tool_latency = Histogram(
            f"{ns}_{sub}_tool_latency_seconds",
            "Tool execution latency",
            ["tool_name", "tenant_id"],
            buckets=lat_buckets,
            registry=self.registry,
        )

        # =====================================================================
        # CACHE METRICS
        # =====================================================================
        self.cache_hits = Counter(
            f"{ns}_{sub}_cache_hits_total",
            "Cache hits",
            ["cache_type", "tenant_id"],  # cache_type: semantic, exact, embedding
            registry=self.registry,
        )

        self.cache_misses = Counter(
            f"{ns}_{sub}_cache_misses_total",
            "Cache misses",
            ["cache_type", "tenant_id"],
            registry=self.registry,
        )

        self.cache_hit_rate = Gauge(
            f"{ns}_{sub}_cache_hit_rate",
            "Rolling cache hit rate",
            ["cache_type", "tenant_id"],
            registry=self.registry,
        )

        # =====================================================================
        # ESCALATION & FALLBACK METRICS
        # =====================================================================
        self.escalations_total = Counter(
            f"{ns}_{sub}_escalations_total",
            "Escalations to human",
            ["reason", "tenant_id"],
            registry=self.registry,
        )

        self.fallbacks_total = Counter(
            f"{ns}_{sub}_fallbacks_total",
            "Fallback responses triggered",
            ["fallback_type", "tenant_id"],
            registry=self.registry,
        )

        # =====================================================================
        # AGENT STEP METRICS
        # =====================================================================
        self.agent_steps_per_request = Histogram(
            f"{ns}_{sub}_agent_steps_per_request",
            "Number of agent steps per request",
            ["tenant_id"],
            buckets=(1, 2, 3, 4, 5, 7, 10, 15, 20, 30),
            registry=self.registry,
        )


# =============================================================================
# METRICS COLLECTOR (High-level API)
# =============================================================================

class AIMetricsCollector:
    """
    High-level metrics collection API for AI pipelines.
    Records metrics at each stage of processing.
    """

    def __init__(self, registry: AIMetricsRegistry = None):
        self.registry = registry or AIMetricsRegistry()
        self._cost_tracker = RollingCostTracker()
        self._cache_tracker = CacheRateTracker()

    # -------------------------------------------------------------------------
    # REQUEST LIFECYCLE
    # -------------------------------------------------------------------------

    def record_request_start(self, tenant_id: str, request_type: str = "chat"):
        self.registry.active_requests.labels(tenant_id=tenant_id).inc()

    def record_request_end(
        self,
        tenant_id: str,
        request_type: str,
        status: str,
        latency_seconds: float,
        total_tokens: int = 0,
        total_cost: float = 0.0,
        model: str = "unknown",
    ):
        self.registry.active_requests.labels(tenant_id=tenant_id).dec()
        self.registry.requests_total.labels(
            tenant_id=tenant_id, request_type=request_type, status=status
        ).inc()
        self.registry.request_latency.labels(
            tenant_id=tenant_id, request_type=request_type
        ).observe(latency_seconds)

        if total_cost > 0:
            self.registry.cost_per_request.labels(
                model=model, tenant_id=tenant_id, request_type=request_type
            ).observe(total_cost)
            self._cost_tracker.add(tenant_id, total_cost)
            self.registry.cost_hourly.labels(tenant_id=tenant_id).set(
                self._cost_tracker.get_hourly(tenant_id)
            )

    # -------------------------------------------------------------------------
    # TOKEN & COST TRACKING
    # -------------------------------------------------------------------------

    def record_llm_usage(
        self,
        model: str,
        tenant_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_seconds: float,
        ttft_seconds: Optional[float] = None,
    ):
        self.registry.tokens_input.labels(model=model, tenant_id=tenant_id).inc(input_tokens)
        self.registry.tokens_output.labels(model=model, tenant_id=tenant_id).inc(output_tokens)
        self.registry.tokens_per_request.labels(model=model, tenant_id=tenant_id).observe(
            input_tokens + output_tokens
        )
        self.registry.cost_total.labels(model=model, tenant_id=tenant_id).inc(cost_usd)
        self.registry.component_latency.labels(component="llm", tenant_id=tenant_id).observe(
            latency_seconds
        )
        if ttft_seconds is not None:
            self.registry.llm_time_to_first_token.labels(
                model=model, tenant_id=tenant_id
            ).observe(ttft_seconds)

    # -------------------------------------------------------------------------
    # COMPONENT LATENCY
    # -------------------------------------------------------------------------

    def record_component_latency(
        self, component: str, tenant_id: str, latency_seconds: float
    ):
        """Record latency for: retrieval, rerank, llm, tool, guardrail, embedding."""
        self.registry.component_latency.labels(
            component=component, tenant_id=tenant_id
        ).observe(latency_seconds)

    # -------------------------------------------------------------------------
    # QUALITY METRICS
    # -------------------------------------------------------------------------

    def record_quality_scores(
        self,
        tenant_id: str,
        groundedness: Optional[float] = None,
        relevance: Optional[float] = None,
    ):
        if groundedness is not None:
            self.registry.groundedness_score.labels(tenant_id=tenant_id).observe(groundedness)
        if relevance is not None:
            self.registry.relevance_score.labels(tenant_id=tenant_id).observe(relevance)

    def record_retrieval_scores(
        self, tenant_id: str, scores: list[float], index: str = "default"
    ):
        for score in scores:
            self.registry.retrieval_score.labels(tenant_id=tenant_id, index=index).observe(score)

    def record_feedback(
        self, tenant_id: str, score: float, feedback_type: str = "thumbs"
    ):
        self.registry.feedback_score.labels(
            tenant_id=tenant_id, feedback_type=feedback_type
        ).observe(score)
        sentiment = "positive" if score >= 0.5 else "negative"
        self.registry.feedback_total.labels(
            tenant_id=tenant_id, sentiment=sentiment
        ).inc()

    # -------------------------------------------------------------------------
    # ERROR TRACKING
    # -------------------------------------------------------------------------

    def record_error(
        self, error_type: str, tenant_id: str, component: str
    ):
        """error_type: model_error, tool_error, guardrail_block, timeout, rate_limit, parse_error"""
        self.registry.errors_total.labels(
            error_type=error_type, tenant_id=tenant_id, component=component
        ).inc()

    def record_retry(self, component: str, tenant_id: str, reason: str):
        self.registry.retries_total.labels(
            component=component, tenant_id=tenant_id, reason=reason
        ).inc()

    def record_timeout(self, component: str, tenant_id: str):
        self.registry.timeouts_total.labels(component=component, tenant_id=tenant_id).inc()

    def record_loop_detected(self, tenant_id: str):
        self.registry.loops_detected.labels(tenant_id=tenant_id).inc()

    # -------------------------------------------------------------------------
    # GUARDRAIL METRICS
    # -------------------------------------------------------------------------

    def record_guardrail_decision(
        self, guardrail_name: str, decision: str, tenant_id: str
    ):
        self.registry.guardrail_decisions.labels(
            guardrail_name=guardrail_name, decision=decision, tenant_id=tenant_id
        ).inc()

    # -------------------------------------------------------------------------
    # TOOL METRICS
    # -------------------------------------------------------------------------

    def record_tool_call(
        self, tool_name: str, status: str, tenant_id: str, latency_seconds: float
    ):
        self.registry.tool_calls_total.labels(
            tool_name=tool_name, status=status, tenant_id=tenant_id
        ).inc()
        self.registry.tool_latency.labels(
            tool_name=tool_name, tenant_id=tenant_id
        ).observe(latency_seconds)

    # -------------------------------------------------------------------------
    # CACHE METRICS
    # -------------------------------------------------------------------------

    def record_cache_hit(self, cache_type: str, tenant_id: str):
        self.registry.cache_hits.labels(cache_type=cache_type, tenant_id=tenant_id).inc()
        self._cache_tracker.record_hit(cache_type, tenant_id)
        self.registry.cache_hit_rate.labels(cache_type=cache_type, tenant_id=tenant_id).set(
            self._cache_tracker.get_rate(cache_type, tenant_id)
        )

    def record_cache_miss(self, cache_type: str, tenant_id: str):
        self.registry.cache_misses.labels(cache_type=cache_type, tenant_id=tenant_id).inc()
        self._cache_tracker.record_miss(cache_type, tenant_id)
        self.registry.cache_hit_rate.labels(cache_type=cache_type, tenant_id=tenant_id).set(
            self._cache_tracker.get_rate(cache_type, tenant_id)
        )

    # -------------------------------------------------------------------------
    # ESCALATION & FALLBACK
    # -------------------------------------------------------------------------

    def record_escalation(self, reason: str, tenant_id: str):
        self.registry.escalations_total.labels(reason=reason, tenant_id=tenant_id).inc()

    def record_fallback(self, fallback_type: str, tenant_id: str):
        self.registry.fallbacks_total.labels(fallback_type=fallback_type, tenant_id=tenant_id).inc()

    # -------------------------------------------------------------------------
    # AGENT STEPS
    # -------------------------------------------------------------------------

    def record_agent_steps(self, tenant_id: str, step_count: int):
        self.registry.agent_steps_per_request.labels(tenant_id=tenant_id).observe(step_count)


# =============================================================================
# ROLLING COST TRACKER
# =============================================================================

class RollingCostTracker:
    """Tracks rolling hourly cost per tenant using a sliding window."""

    def __init__(self, window_seconds: int = 3600):
        self.window = window_seconds
        self._entries: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._lock = threading.Lock()

    def add(self, tenant_id: str, cost: float):
        now = time.time()
        with self._lock:
            self._entries[tenant_id].append((now, cost))

    def get_hourly(self, tenant_id: str) -> float:
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            entries = self._entries[tenant_id]
            # Prune old entries
            self._entries[tenant_id] = [
                (t, c) for t, c in entries if t > cutoff
            ]
            return sum(c for t, c in self._entries[tenant_id])


# =============================================================================
# CACHE RATE TRACKER
# =============================================================================

class CacheRateTracker:
    """Tracks rolling cache hit rate."""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._hits: dict[str, int] = defaultdict(int)
        self._total: dict[str, int] = defaultdict(int)

    def _key(self, cache_type: str, tenant_id: str) -> str:
        return f"{cache_type}:{tenant_id}"

    def record_hit(self, cache_type: str, tenant_id: str):
        key = self._key(cache_type, tenant_id)
        self._hits[key] += 1
        self._total[key] += 1

    def record_miss(self, cache_type: str, tenant_id: str):
        key = self._key(cache_type, tenant_id)
        self._total[key] += 1

    def get_rate(self, cache_type: str, tenant_id: str) -> float:
        key = self._key(cache_type, tenant_id)
        total = self._total[key]
        if total == 0:
            return 0.0
        return self._hits[key] / total


# =============================================================================
# METRIC AGGREGATION & ROLLUP
# =============================================================================

class MetricAggregator:
    """
    Aggregates metrics over time windows for dashboard consumption.
    Computes percentiles, rates, and derived metrics.
    """

    def __init__(self):
        self._latency_samples: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def add_latency_sample(self, key: str, value: float):
        with self._lock:
            self._latency_samples[key].append(value)
            # Keep only last 10000 samples
            if len(self._latency_samples[key]) > 10000:
                self._latency_samples[key] = self._latency_samples[key][-5000:]

    def get_percentiles(self, key: str) -> dict[str, float]:
        with self._lock:
            samples = sorted(self._latency_samples.get(key, []))
        if not samples:
            return {"p50": 0, "p95": 0, "p99": 0}
        n = len(samples)
        return {
            "p50": samples[int(n * 0.50)],
            "p95": samples[int(n * 0.95)] if n > 20 else samples[-1],
            "p99": samples[int(n * 0.99)] if n > 100 else samples[-1],
            "count": n,
            "mean": sum(samples) / n,
        }

    def compute_summary(self) -> dict:
        """Compute full summary across all tracked keys."""
        result = {}
        with self._lock:
            keys = list(self._latency_samples.keys())
        for key in keys:
            result[key] = self.get_percentiles(key)
        return result


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_metrics_collection():
    """Demonstrates recording metrics through a full AI request lifecycle."""

    # Initialize
    registry = AIMetricsRegistry()
    collector = AIMetricsCollector(registry)

    tenant = "tenant-acme"
    start = time.time()

    # Request starts
    collector.record_request_start(tenant, "rag_chat")

    # Retrieval
    collector.record_component_latency("retrieval", tenant, 0.089)
    collector.record_retrieval_scores(tenant, [0.92, 0.87, 0.81, 0.73, 0.68])

    # Cache check
    collector.record_cache_miss("semantic", tenant)

    # Rerank
    collector.record_component_latency("rerank", tenant, 0.034)

    # LLM call
    collector.record_llm_usage(
        model="gpt-4o",
        tenant_id=tenant,
        input_tokens=1850,
        output_tokens=320,
        cost_usd=0.0125,
        latency_seconds=1.2,
        ttft_seconds=0.3,
    )

    # Guardrail
    collector.record_guardrail_decision("groundedness_check", "allow", tenant)
    collector.record_component_latency("guardrail", tenant, 0.015)

    # Quality scores
    collector.record_quality_scores(tenant, groundedness=0.91, relevance=0.88)

    # Request ends
    total_latency = time.time() - start
    collector.record_request_end(
        tenant_id=tenant,
        request_type="rag_chat",
        status="success",
        latency_seconds=total_latency,
        total_tokens=2170,
        total_cost=0.0125,
        model="gpt-4o",
    )

    # User feedback (would come later)
    collector.record_feedback(tenant, score=1.0, feedback_type="thumbs")

    # Export metrics (Prometheus format)
    print("Prometheus metrics exported. Sample:")
    metrics_output = generate_latest(registry.registry).decode("utf-8")
    # Print first 50 lines
    for line in metrics_output.split("\n")[:50]:
        print(line)


def example_error_scenarios():
    """Demonstrates error metric recording."""

    registry = AIMetricsRegistry()
    collector = AIMetricsCollector(registry)
    tenant = "tenant-beta"

    # Tool error
    collector.record_tool_call("web_search", "error", tenant, 5.0)
    collector.record_error("tool_error", tenant, "web_search")
    collector.record_retry("tool", tenant, "timeout")

    # Rate limit
    collector.record_error("rate_limit", tenant, "llm")
    collector.record_retry("llm", tenant, "rate_limit")

    # Agent loop
    collector.record_agent_steps(tenant, 15)
    collector.record_loop_detected(tenant)
    collector.record_error("timeout", tenant, "agent")

    # Guardrail block
    collector.record_guardrail_decision("toxicity_filter", "block", tenant)
    collector.record_error("guardrail_block", tenant, "output_filter")

    # Fallback
    collector.record_fallback("simpler_model", tenant)

    print("Error scenario metrics recorded successfully.")


def start_metrics_server(port: int = 9090):
    """Start Prometheus metrics HTTP server."""
    start_http_server(port)
    print(f"Metrics server running on http://localhost:{port}/metrics")


if __name__ == "__main__":
    print("=" * 60)
    print("Example: Full Metrics Collection")
    print("=" * 60)
    example_metrics_collection()

    print("\n" + "=" * 60)
    print("Example: Error Scenarios")
    print("=" * 60)
    example_error_scenarios()
