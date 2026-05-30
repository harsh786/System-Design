"""
Module 12: AI Observability - Dashboard Data Generator

Generates real-time dashboard data, Grafana dashboard JSON,
and alert rule configurations for AI observability.
"""

import json
import time
import random
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta


# =============================================================================
# DASHBOARD DATA MODELS
# =============================================================================

@dataclass
class TimeSeriesPoint:
    timestamp: float
    value: float


@dataclass
class MetricSummary:
    current: float
    p50: float
    p95: float
    p99: float
    trend: str  # "up", "down", "stable"
    change_pct: float


@dataclass
class TenantDashboard:
    tenant_id: str
    request_count: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    feedback_score: float = 0.0
    top_models: dict = field(default_factory=dict)
    top_tools: dict = field(default_factory=dict)


# =============================================================================
# REAL-TIME METRICS AGGREGATOR
# =============================================================================

class DashboardAggregator:
    """
    Aggregates raw metrics into dashboard-ready summaries.
    Maintains sliding windows for real-time percentile computation.
    """

    def __init__(self, window_minutes: int = 60):
        self.window_minutes = window_minutes
        self._latencies: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._costs: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._errors: dict[str, int] = defaultdict(int)
        self._requests: dict[str, int] = defaultdict(int)
        self._feedback: dict[str, list[float]] = defaultdict(list)
        self._token_usage: dict[str, list[tuple[float, int]]] = defaultdict(list)

    def _prune(self, data: list[tuple[float, float]]) -> list[tuple[float, float]]:
        cutoff = time.time() - (self.window_minutes * 60)
        return [(t, v) for t, v in data if t > cutoff]

    def record_request(
        self,
        tenant_id: str,
        latency_s: float,
        cost_usd: float,
        tokens: int,
        is_error: bool = False,
        component_latencies: dict = None,
    ):
        now = time.time()
        self._latencies[tenant_id].append((now, latency_s))
        self._costs[tenant_id].append((now, cost_usd))
        self._token_usage[tenant_id].append((now, tokens))
        self._requests[tenant_id] += 1
        if is_error:
            self._errors[tenant_id] += 1

        # Component breakdown
        if component_latencies:
            for component, lat in component_latencies.items():
                key = f"{tenant_id}::{component}"
                self._latencies[key].append((now, lat))

    def record_feedback(self, tenant_id: str, score: float):
        self._feedback[tenant_id].append(score)

    def get_latency_summary(self, tenant_id: str) -> MetricSummary:
        data = self._prune(self._latencies.get(tenant_id, []))
        if not data:
            return MetricSummary(0, 0, 0, 0, "stable", 0)
        values = sorted([v for _, v in data])
        n = len(values)
        current = values[-1]
        p50 = values[int(n * 0.5)]
        p95 = values[int(n * 0.95)] if n > 20 else values[-1]
        p99 = values[int(n * 0.99)] if n > 100 else values[-1]

        # Trend: compare last 25% vs first 25%
        quarter = max(1, n // 4)
        recent_avg = sum(values[-quarter:]) / quarter
        earlier_avg = sum(values[:quarter]) / quarter
        if earlier_avg > 0:
            change_pct = ((recent_avg - earlier_avg) / earlier_avg) * 100
        else:
            change_pct = 0
        trend = "up" if change_pct > 10 else "down" if change_pct < -10 else "stable"

        return MetricSummary(current, p50, p95, p99, trend, round(change_pct, 1))

    def get_cost_summary(self, tenant_id: str) -> dict:
        data = self._prune(self._costs.get(tenant_id, []))
        if not data:
            return {"total": 0, "hourly_rate": 0, "per_request": 0}
        total = sum(v for _, v in data)
        time_span = (data[-1][0] - data[0][0]) / 3600 if len(data) > 1 else 1
        return {
            "total": round(total, 4),
            "hourly_rate": round(total / max(time_span, 0.01), 4),
            "per_request": round(total / len(data), 6),
            "request_count": len(data),
        }

    def get_error_rate(self, tenant_id: str) -> float:
        total = self._requests.get(tenant_id, 0)
        errors = self._errors.get(tenant_id, 0)
        return round(errors / max(total, 1), 4)

    def get_component_breakdown(self, tenant_id: str) -> dict:
        """Get latency breakdown by component."""
        components = ["retrieval", "rerank", "llm", "tool", "guardrail"]
        breakdown = {}
        for comp in components:
            key = f"{tenant_id}::{comp}"
            data = self._prune(self._latencies.get(key, []))
            if data:
                values = [v for _, v in data]
                breakdown[comp] = {
                    "avg_ms": round(sum(values) / len(values) * 1000, 1),
                    "p95_ms": round(sorted(values)[int(len(values) * 0.95)] * 1000, 1)
                    if len(values) > 20
                    else round(max(values) * 1000, 1),
                    "count": len(values),
                }
        return breakdown

    def get_tenant_dashboard(self, tenant_id: str) -> dict:
        latency = self.get_latency_summary(tenant_id)
        cost = self.get_cost_summary(tenant_id)
        components = self.get_component_breakdown(tenant_id)
        feedback_scores = self._feedback.get(tenant_id, [])

        return {
            "tenant_id": tenant_id,
            "latency": {
                "p50_ms": round(latency.p50 * 1000, 1),
                "p95_ms": round(latency.p95 * 1000, 1),
                "p99_ms": round(latency.p99 * 1000, 1),
                "trend": latency.trend,
                "change_pct": latency.change_pct,
            },
            "cost": cost,
            "error_rate": self.get_error_rate(tenant_id),
            "feedback": {
                "avg_score": round(sum(feedback_scores) / max(len(feedback_scores), 1), 2),
                "count": len(feedback_scores),
                "positive_pct": round(
                    sum(1 for s in feedback_scores if s >= 0.5)
                    / max(len(feedback_scores), 1)
                    * 100,
                    1,
                ),
            },
            "component_breakdown": components,
            "requests_in_window": self._requests.get(tenant_id, 0),
        }


# =============================================================================
# GRAFANA DASHBOARD JSON GENERATOR
# =============================================================================

class GrafanaDashboardGenerator:
    """Generates Grafana dashboard JSON for AI observability."""

    def __init__(self, datasource: str = "Prometheus", namespace: str = "ai_agent"):
        self.datasource = datasource
        self.ns = namespace

    def generate_full_dashboard(self) -> dict:
        """Generate complete Grafana dashboard JSON."""
        return {
            "dashboard": {
                "id": None,
                "uid": "ai-observability-main",
                "title": "AI Agent Observability",
                "tags": ["ai", "observability", "llm"],
                "timezone": "browser",
                "refresh": "10s",
                "time": {"from": "now-1h", "to": "now"},
                "templating": {
                    "list": [
                        self._variable("tenant_id", f"label_values({self.ns}_requests_total, tenant_id)"),
                        self._variable("model", f"label_values({self.ns}_tokens_input_total, model)"),
                    ]
                },
                "panels": self._all_panels(),
            },
            "overwrite": True,
        }

    def _variable(self, name: str, query: str) -> dict:
        return {
            "name": name,
            "type": "query",
            "datasource": self.datasource,
            "query": query,
            "refresh": 2,
            "includeAll": True,
            "multi": True,
        }

    def _all_panels(self) -> list:
        panels = []
        y = 0

        # Row 1: Overview stats
        panels.append(self._stat_panel(
            "Request Rate", f"sum(rate({self.ns}_requests_total[$__rate_interval]))",
            grid_pos={"x": 0, "y": y, "w": 4, "h": 4},
        ))
        panels.append(self._stat_panel(
            "Error Rate", f"sum(rate({self.ns}_errors_total[$__rate_interval])) / sum(rate({self.ns}_requests_total[$__rate_interval])) * 100",
            grid_pos={"x": 4, "y": y, "w": 4, "h": 4}, unit="percent",
        ))
        panels.append(self._stat_panel(
            "Hourly Cost", f"sum({self.ns}_cost_hourly_usd)",
            grid_pos={"x": 8, "y": y, "w": 4, "h": 4}, unit="currencyUSD",
        ))
        panels.append(self._stat_panel(
            "Avg Feedback", f"avg({self.ns}_feedback_score_sum / {self.ns}_feedback_score_count)",
            grid_pos={"x": 12, "y": y, "w": 4, "h": 4},
        ))
        panels.append(self._stat_panel(
            "Cache Hit Rate", f"avg({self.ns}_cache_hit_rate)",
            grid_pos={"x": 16, "y": y, "w": 4, "h": 4}, unit="percentunit",
        ))
        panels.append(self._stat_panel(
            "Active Requests", f"sum({self.ns}_active_requests)",
            grid_pos={"x": 20, "y": y, "w": 4, "h": 4},
        ))
        y += 4

        # Row 2: Latency
        panels.append(self._graph_panel(
            "Request Latency (p50/p95/p99)",
            [
                (f"histogram_quantile(0.5, sum(rate({self.ns}_request_latency_seconds_bucket[$__rate_interval])) by (le))", "p50"),
                (f"histogram_quantile(0.95, sum(rate({self.ns}_request_latency_seconds_bucket[$__rate_interval])) by (le))", "p95"),
                (f"histogram_quantile(0.99, sum(rate({self.ns}_request_latency_seconds_bucket[$__rate_interval])) by (le))", "p99"),
            ],
            grid_pos={"x": 0, "y": y, "w": 12, "h": 8}, unit="s",
        ))
        panels.append(self._graph_panel(
            "Component Latency Breakdown",
            [
                (f"histogram_quantile(0.95, sum(rate({self.ns}_component_latency_seconds_bucket{{component=\"retrieval\"}}[$__rate_interval])) by (le))", "Retrieval p95"),
                (f"histogram_quantile(0.95, sum(rate({self.ns}_component_latency_seconds_bucket{{component=\"rerank\"}}[$__rate_interval])) by (le))", "Rerank p95"),
                (f"histogram_quantile(0.95, sum(rate({self.ns}_component_latency_seconds_bucket{{component=\"llm\"}}[$__rate_interval])) by (le))", "LLM p95"),
                (f"histogram_quantile(0.95, sum(rate({self.ns}_component_latency_seconds_bucket{{component=\"tool\"}}[$__rate_interval])) by (le))", "Tool p95"),
            ],
            grid_pos={"x": 12, "y": y, "w": 12, "h": 8}, unit="s",
        ))
        y += 8

        # Row 3: Cost & Tokens
        panels.append(self._graph_panel(
            "Cost Over Time (by Model)",
            [(f"sum(rate({self.ns}_cost_usd_total[$__rate_interval])) by (model) * 3600", "{{{{model}}}}")],
            grid_pos={"x": 0, "y": y, "w": 12, "h": 8}, unit="currencyUSD",
        ))
        panels.append(self._graph_panel(
            "Tokens Per Request",
            [(f"histogram_quantile(0.95, sum(rate({self.ns}_tokens_per_request_bucket[$__rate_interval])) by (le, model))", "{{{{model}}}} p95")],
            grid_pos={"x": 12, "y": y, "w": 12, "h": 8},
        ))
        y += 8

        # Row 4: Quality & Errors
        panels.append(self._graph_panel(
            "Quality Scores",
            [
                (f"histogram_quantile(0.5, sum(rate({self.ns}_groundedness_score_bucket[$__rate_interval])) by (le))", "Groundedness p50"),
                (f"histogram_quantile(0.5, sum(rate({self.ns}_relevance_score_bucket[$__rate_interval])) by (le))", "Relevance p50"),
            ],
            grid_pos={"x": 0, "y": y, "w": 12, "h": 8},
        ))
        panels.append(self._graph_panel(
            "Error Rate by Type",
            [(f"sum(rate({self.ns}_errors_total[$__rate_interval])) by (error_type)", "{{{{error_type}}}}")],
            grid_pos={"x": 12, "y": y, "w": 12, "h": 8},
        ))
        y += 8

        # Row 5: Tools & Guardrails
        panels.append(self._graph_panel(
            "Tool Call Rate & Errors",
            [
                (f"sum(rate({self.ns}_tool_calls_total{{status=\"success\"}}[$__rate_interval])) by (tool_name)", "{{{{tool_name}}}} success"),
                (f"sum(rate({self.ns}_tool_calls_total{{status=\"error\"}}[$__rate_interval])) by (tool_name)", "{{{{tool_name}}}} error"),
            ],
            grid_pos={"x": 0, "y": y, "w": 12, "h": 8},
        ))
        panels.append(self._graph_panel(
            "Guardrail Decisions",
            [(f"sum(rate({self.ns}_guardrail_decisions_total[$__rate_interval])) by (guardrail_name, decision)", "{{{{guardrail_name}}}} {{{{decision}}}}")],
            grid_pos={"x": 12, "y": y, "w": 12, "h": 8},
        ))
        y += 8

        # Row 6: Per-Tenant
        panels.append(self._graph_panel(
            "Cost by Tenant",
            [(f"sum(rate({self.ns}_cost_usd_total[$__rate_interval])) by (tenant_id) * 3600", "{{{{tenant_id}}}}")],
            grid_pos={"x": 0, "y": y, "w": 12, "h": 8}, unit="currencyUSD",
        ))
        panels.append(self._graph_panel(
            "Request Rate by Tenant",
            [(f"sum(rate({self.ns}_requests_total[$__rate_interval])) by (tenant_id)", "{{{{tenant_id}}}}")],
            grid_pos={"x": 12, "y": y, "w": 12, "h": 8},
        ))

        return panels

    def _stat_panel(self, title: str, expr: str, grid_pos: dict, unit: str = "short") -> dict:
        return {
            "type": "stat",
            "title": title,
            "datasource": self.datasource,
            "gridPos": grid_pos,
            "targets": [{"expr": expr, "refId": "A"}],
            "fieldConfig": {"defaults": {"unit": unit}},
        }

    def _graph_panel(self, title: str, queries: list[tuple], grid_pos: dict, unit: str = "short") -> dict:
        targets = []
        for i, (expr, legend) in enumerate(queries):
            targets.append({
                "expr": expr,
                "legendFormat": legend,
                "refId": chr(65 + i),
            })
        return {
            "type": "timeseries",
            "title": title,
            "datasource": self.datasource,
            "gridPos": grid_pos,
            "targets": targets,
            "fieldConfig": {"defaults": {"unit": unit}},
        }


# =============================================================================
# ALERT RULE CONFIGURATION
# =============================================================================

class AlertRuleGenerator:
    """Generates Prometheus/Grafana alert rules for AI systems."""

    def __init__(self, namespace: str = "ai_agent"):
        self.ns = namespace

    def generate_all_rules(self) -> dict:
        """Generate complete alerting rule configuration."""
        return {
            "groups": [
                {
                    "name": "ai_latency_alerts",
                    "interval": "30s",
                    "rules": [
                        self._rule(
                            "AIHighLatencyWarning",
                            f"histogram_quantile(0.95, sum(rate({self.ns}_request_latency_seconds_bucket[5m])) by (le)) > 5",
                            "warning", "5m",
                            "AI request p95 latency exceeds 5 seconds",
                        ),
                        self._rule(
                            "AIHighLatencyCritical",
                            f"histogram_quantile(0.95, sum(rate({self.ns}_request_latency_seconds_bucket[5m])) by (le)) > 15",
                            "critical", "2m",
                            "AI request p95 latency exceeds 15 seconds",
                        ),
                    ],
                },
                {
                    "name": "ai_error_alerts",
                    "interval": "30s",
                    "rules": [
                        self._rule(
                            "AIHighErrorRate",
                            f"sum(rate({self.ns}_errors_total[5m])) / sum(rate({self.ns}_requests_total[5m])) > 0.05",
                            "warning", "5m",
                            "AI error rate exceeds 5%",
                        ),
                        self._rule(
                            "AIHighErrorRateCritical",
                            f"sum(rate({self.ns}_errors_total[5m])) / sum(rate({self.ns}_requests_total[5m])) > 0.10",
                            "critical", "2m",
                            "AI error rate exceeds 10%",
                        ),
                        self._rule(
                            "AIToolFailureSpike",
                            f"sum(rate({self.ns}_tool_calls_total{{status='error'}}[5m])) / sum(rate({self.ns}_tool_calls_total[5m])) > 0.20",
                            "warning", "5m",
                            "Tool failure rate exceeds 20%",
                        ),
                        self._rule(
                            "AIAgentLoopDetected",
                            f"sum(rate({self.ns}_loops_detected_total[5m])) > 0.1",
                            "warning", "3m",
                            "Agent loops being detected frequently",
                        ),
                    ],
                },
                {
                    "name": "ai_cost_alerts",
                    "interval": "60s",
                    "rules": [
                        self._rule(
                            "AICostSpikeWarning",
                            f"sum({self.ns}_cost_hourly_usd) > 50",
                            "warning", "10m",
                            "Hourly AI cost exceeds $50",
                        ),
                        self._rule(
                            "AICostSpikeCritical",
                            f"sum({self.ns}_cost_hourly_usd) > 150",
                            "critical", "5m",
                            "Hourly AI cost exceeds $150",
                        ),
                        self._rule(
                            "AITenantCostSpike",
                            f"{self.ns}_cost_hourly_usd > 20",
                            "warning", "10m",
                            "Single tenant hourly cost exceeds $20",
                        ),
                    ],
                },
                {
                    "name": "ai_quality_alerts",
                    "interval": "60s",
                    "rules": [
                        self._rule(
                            "AILowGroundedness",
                            f"histogram_quantile(0.5, sum(rate({self.ns}_groundedness_score_bucket[15m])) by (le)) < 0.7",
                            "warning", "15m",
                            "Median groundedness score below 0.7",
                        ),
                        self._rule(
                            "AILowGroundednessCritical",
                            f"histogram_quantile(0.5, sum(rate({self.ns}_groundedness_score_bucket[15m])) by (le)) < 0.5",
                            "critical", "10m",
                            "Median groundedness score below 0.5 - high hallucination risk",
                        ),
                        self._rule(
                            "AIHighSafetyBlockRate",
                            f"sum(rate({self.ns}_guardrail_decisions_total{{decision='block'}}[15m])) / sum(rate({self.ns}_guardrail_decisions_total[15m])) > 0.10",
                            "warning", "15m",
                            "Safety block rate exceeds 10% - possible false positives",
                        ),
                        self._rule(
                            "AILowFeedbackScore",
                            f"avg(rate({self.ns}_feedback_score_sum[1h]) / rate({self.ns}_feedback_score_count[1h])) < 0.5",
                            "warning", "30m",
                            "Average user feedback score below 0.5",
                        ),
                    ],
                },
                {
                    "name": "ai_capacity_alerts",
                    "interval": "30s",
                    "rules": [
                        self._rule(
                            "AIHighConcurrency",
                            f"sum({self.ns}_active_requests) > 100",
                            "warning", "5m",
                            "More than 100 concurrent AI requests",
                        ),
                        self._rule(
                            "AICacheEfficiencyDrop",
                            f"avg({self.ns}_cache_hit_rate) < 0.3",
                            "warning", "15m",
                            "Cache hit rate dropped below 30%",
                        ),
                    ],
                },
            ]
        }

    def _rule(self, name: str, expr: str, severity: str, duration: str, summary: str) -> dict:
        return {
            "alert": name,
            "expr": expr,
            "for": duration,
            "labels": {"severity": severity, "team": "ai-platform"},
            "annotations": {
                "summary": summary,
                "runbook_url": f"https://runbooks.internal/ai/{name}",
            },
        }


# =============================================================================
# EXAMPLE: Generate and export dashboard
# =============================================================================

def export_grafana_dashboard(output_path: str = "grafana-ai-dashboard.json"):
    generator = GrafanaDashboardGenerator()
    dashboard = generator.generate_full_dashboard()
    with open(output_path, "w") as f:
        json.dump(dashboard, f, indent=2)
    print(f"Grafana dashboard exported to {output_path}")
    return dashboard


def export_alert_rules(output_path: str = "prometheus-ai-alerts.yml"):
    generator = AlertRuleGenerator()
    rules = generator.generate_all_rules()

    # Convert to YAML-like format (simplified)
    import yaml  # optional
    try:
        import yaml
        with open(output_path, "w") as f:
            yaml.dump(rules, f, default_flow_style=False)
    except ImportError:
        with open(output_path, "w") as f:
            json.dump(rules, f, indent=2)
    print(f"Alert rules exported to {output_path}")
    return rules


def example_dashboard_data():
    """Simulate dashboard data generation."""
    aggregator = DashboardAggregator()

    # Simulate 100 requests
    for i in range(100):
        tenant = random.choice(["tenant-acme", "tenant-beta", "tenant-gamma"])
        latency = random.gauss(1.5, 0.5)
        cost = random.uniform(0.005, 0.05)
        tokens = random.randint(500, 5000)
        is_error = random.random() < 0.03

        aggregator.record_request(
            tenant_id=tenant,
            latency_s=max(0.1, latency),
            cost_usd=cost,
            tokens=tokens,
            is_error=is_error,
            component_latencies={
                "retrieval": random.uniform(0.05, 0.2),
                "rerank": random.uniform(0.02, 0.08),
                "llm": random.uniform(0.5, 2.0),
                "guardrail": random.uniform(0.01, 0.05),
            },
        )

        if random.random() < 0.3:
            aggregator.record_feedback(tenant, random.choice([0.0, 1.0, 1.0, 1.0]))

    # Get dashboard for each tenant
    for tenant in ["tenant-acme", "tenant-beta", "tenant-gamma"]:
        dashboard = aggregator.get_tenant_dashboard(tenant)
        print(f"\n{'='*50}")
        print(f"Dashboard: {tenant}")
        print(f"{'='*50}")
        print(json.dumps(dashboard, indent=2))


if __name__ == "__main__":
    print("Generating dashboard data...\n")
    example_dashboard_data()

    print("\n\nExporting Grafana dashboard...")
    export_grafana_dashboard("/tmp/grafana-ai-dashboard.json")

    print("\nExporting alert rules...")
    export_alert_rules("/tmp/prometheus-ai-alerts.json")
