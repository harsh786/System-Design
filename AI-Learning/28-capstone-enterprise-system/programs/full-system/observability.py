"""
Observability module.
Request tracing, metrics collection, and trace export.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Span:
    name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    metadata: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def end(self, **metadata):
        self.end_time = time.time()
        self.metadata.update(metadata)


@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:8]}")
    spans: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

    def start_span(self, name: str) -> Span:
        span = Span(name=name)
        self.spans.append(span)
        return span

    def add_metric(self, key: str, value):
        self.metrics[key] = value

    def total_duration_ms(self) -> float:
        return (time.time() - self.start_time) * 1000


class ObservabilitySystem:
    """Collects traces and metrics for all requests."""

    def __init__(self):
        self.traces: list[Trace] = []
        self.aggregate_metrics = {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "routes": {"simple": 0, "medium": 0, "complex": 0, "blocked": 0},
            "avg_latency_ms": 0.0,
        }
        print("[OBSERVABILITY] Initialized")

    def create_trace(self) -> Trace:
        trace = Trace()
        self.traces.append(trace)
        self.aggregate_metrics["total_requests"] += 1
        return trace

    def record_request(self, trace: Trace):
        """Record final metrics from a completed trace."""
        route = trace.metrics.get("route", "unknown")
        if route in self.aggregate_metrics["routes"]:
            self.aggregate_metrics["routes"][route] += 1

        tokens = trace.metrics.get("tokens_total", 0)
        cost = trace.metrics.get("cost", 0.0)
        self.aggregate_metrics["total_tokens"] += tokens
        self.aggregate_metrics["total_cost"] += cost

        # Update rolling average latency
        n = self.aggregate_metrics["total_requests"]
        old_avg = self.aggregate_metrics["avg_latency_ms"]
        new_latency = trace.total_duration_ms()
        self.aggregate_metrics["avg_latency_ms"] = old_avg + (new_latency - old_avg) / n

    def print_trace(self, trace: Trace):
        """Print a human-readable trace."""
        print("\n" + "═" * 50)
        print(f"TRACE: {trace.trace_id}")
        print("═" * 50)

        for i, span in enumerate(trace.spans):
            prefix = "├─" if i < len(trace.spans) - 1 else "└─"
            print(f"{prefix} {span.name}: {span.duration_ms:.0f}ms", end="")
            if span.metadata:
                details = ", ".join(f"{k}={v}" for k, v in span.metadata.items())
                print(f" ({details})", end="")
            print()

        print(f"\nMETRICS:")
        for key, value in trace.metrics.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")
        print("═" * 50 + "\n")

    def get_summary(self) -> dict:
        return self.aggregate_metrics.copy()


# Global instance
observability = ObservabilitySystem()
