"""
AgentOps: Monitoring Dashboard System
=======================================
Production-grade monitoring dashboard for AI agents: health metrics,
trajectory visualization, tool usage, cost/latency trends, error analysis,
performance comparison, alerting, and trace drill-down.
"""

import json
import uuid
import time
import statistics
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter, defaultdict
from abc import ABC, abstractmethod


# =============================================================================
# Core Data Models
# =============================================================================

class AgentStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"


@dataclass
class TrajectoryStep:
    """A single step in an agent trajectory."""
    step_index: int
    step_type: str  # llm_call, tool_call, decision, observation
    timestamp: str
    duration_ms: float
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    model: Optional[str] = None
    tool_name: Optional[str] = None
    token_count: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTrace:
    """Complete trace of an agent execution."""
    id: str
    agent_id: str
    agent_version: str
    started_at: str
    completed_at: Optional[str] = None
    status: str = "running"  # running, success, failure, timeout
    steps: list[TrajectoryStep] = field(default_factory=list)
    total_duration_ms: float = 0
    total_cost_usd: float = 0
    total_tokens: dict[str, int] = field(default_factory=dict)
    tools_used: list[str] = field(default_factory=list)
    user_feedback: Optional[dict] = None
    goal: str = ""
    outcome: Optional[str] = None
    error_info: Optional[dict] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMetrics:
    """Aggregated metrics for an agent over a time window."""
    agent_id: str
    window_start: str
    window_end: str
    total_traces: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    avg_duration_ms: float = 0
    p50_duration_ms: float = 0
    p95_duration_ms: float = 0
    p99_duration_ms: float = 0
    avg_steps: float = 0
    avg_cost_usd: float = 0
    total_cost_usd: float = 0
    avg_tokens: float = 0
    tool_usage: dict[str, int] = field(default_factory=dict)
    error_distribution: dict[str, int] = field(default_factory=dict)
    success_rate: float = 0.0


@dataclass
class Alert:
    """A monitoring alert."""
    id: str
    agent_id: str
    severity: AlertSeverity
    title: str
    description: str
    metric_name: str
    metric_value: float
    threshold: float
    fired_at: str
    resolved_at: Optional[str] = None
    status: AlertStatus = AlertStatus.FIRING
    acknowledged_by: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Configuration for an alert rule."""
    id: str
    name: str
    agent_id: str  # "*" for all agents
    metric_name: str
    condition: str  # gt, lt, gte, lte, eq
    threshold: float
    severity: AlertSeverity
    window_minutes: int = 5
    min_occurrences: int = 1
    cooldown_minutes: int = 15
    enabled: bool = True
    last_fired: Optional[str] = None


# =============================================================================
# Trace Store
# =============================================================================

class TraceStore:
    """Storage for agent traces with querying capabilities."""

    def __init__(self, max_traces: int = 50000):
        self.traces: list[AgentTrace] = []
        self.index_by_agent: dict[str, list[int]] = defaultdict(list)
        self.max_traces = max_traces

    def store(self, trace: AgentTrace):
        idx = len(self.traces)
        self.traces.append(trace)
        self.index_by_agent[trace.agent_id].append(idx)
        if len(self.traces) > self.max_traces:
            self._compact()

    def get_trace(self, trace_id: str) -> Optional[AgentTrace]:
        for t in self.traces:
            if t.id == trace_id:
                return t
        return None

    def query(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
    ) -> list[AgentTrace]:
        results = []
        for trace in reversed(self.traces):
            if agent_id and trace.agent_id != agent_id:
                continue
            if status and trace.status != status:
                continue
            if since and trace.started_at < since:
                break
            if until and trace.started_at > until:
                continue
            results.append(trace)
            if len(results) >= limit:
                break
        return results

    def _compact(self):
        """Remove oldest traces beyond limit."""
        self.traces = self.traces[-self.max_traces:]
        self.index_by_agent.clear()
        for i, t in enumerate(self.traces):
            self.index_by_agent[t.agent_id].append(i)


# =============================================================================
# Metrics Aggregator
# =============================================================================

class MetricsAggregator:
    """Aggregates trace data into time-windowed metrics."""

    def __init__(self, trace_store: TraceStore):
        self.trace_store = trace_store

    def compute_metrics(
        self, agent_id: str, window_start: str, window_end: str
    ) -> AgentMetrics:
        """Compute aggregated metrics for an agent in a time window."""
        traces = self.trace_store.query(agent_id=agent_id, since=window_start, until=window_end, limit=10000)

        if not traces:
            return AgentMetrics(agent_id=agent_id, window_start=window_start, window_end=window_end)

        durations = [t.total_duration_ms for t in traces if t.total_duration_ms > 0]
        costs = [t.total_cost_usd for t in traces]
        step_counts = [len(t.steps) for t in traces]
        tool_usage = Counter()
        error_dist = Counter()

        success_count = sum(1 for t in traces if t.status == "success")
        failure_count = sum(1 for t in traces if t.status == "failure")
        timeout_count = sum(1 for t in traces if t.status == "timeout")

        for trace in traces:
            for tool in trace.tools_used:
                tool_usage[tool] += 1
            if trace.error_info:
                error_dist[trace.error_info.get("type", "unknown")] += 1

        sorted_durations = sorted(durations) if durations else [0]

        return AgentMetrics(
            agent_id=agent_id,
            window_start=window_start,
            window_end=window_end,
            total_traces=len(traces),
            success_count=success_count,
            failure_count=failure_count,
            timeout_count=timeout_count,
            avg_duration_ms=statistics.mean(durations) if durations else 0,
            p50_duration_ms=sorted_durations[len(sorted_durations) // 2],
            p95_duration_ms=sorted_durations[int(len(sorted_durations) * 0.95)],
            p99_duration_ms=sorted_durations[int(len(sorted_durations) * 0.99)],
            avg_steps=statistics.mean(step_counts) if step_counts else 0,
            avg_cost_usd=statistics.mean(costs) if costs else 0,
            total_cost_usd=sum(costs),
            avg_tokens=statistics.mean(
                sum(t.total_tokens.values()) for t in traces
            ) if traces else 0,
            tool_usage=dict(tool_usage.most_common(20)),
            error_distribution=dict(error_dist.most_common(10)),
            success_rate=success_count / max(len(traces), 1),
        )

    def compute_trends(self, agent_id: str, periods: int = 24, period_hours: int = 1) -> list[AgentMetrics]:
        """Compute metrics for multiple consecutive time windows."""
        now = datetime.now(timezone.utc)
        trends = []
        for i in range(periods - 1, -1, -1):
            window_end = now - timedelta(hours=i)
            window_start = window_end - timedelta(hours=period_hours)
            metrics = self.compute_metrics(
                agent_id,
                window_start.isoformat(),
                window_end.isoformat()
            )
            trends.append(metrics)
        return trends


# =============================================================================
# Trajectory Visualizer
# =============================================================================

class TrajectoryVisualizer:
    """Generates trajectory visualizations for agent traces."""

    @staticmethod
    def to_timeline(trace: AgentTrace) -> list[dict]:
        """Convert a trace to a timeline format."""
        timeline = []
        for step in trace.steps:
            timeline.append({
                "index": step.step_index,
                "type": step.step_type,
                "tool": step.tool_name,
                "duration_ms": step.duration_ms,
                "cost_usd": step.cost_usd,
                "has_error": step.error is not None,
                "timestamp": step.timestamp,
            })
        return timeline

    @staticmethod
    def to_graph(trace: AgentTrace) -> dict:
        """Convert a trace to a graph format (nodes + edges)."""
        nodes = []
        edges = []

        for i, step in enumerate(trace.steps):
            nodes.append({
                "id": f"step_{i}",
                "label": step.tool_name or step.step_type,
                "type": step.step_type,
                "duration_ms": step.duration_ms,
                "error": step.error,
            })
            if i > 0:
                edges.append({
                    "from": f"step_{i-1}",
                    "to": f"step_{i}",
                    "label": f"{step.duration_ms:.0f}ms",
                })

        return {"nodes": nodes, "edges": edges, "total_steps": len(nodes)}

    @staticmethod
    def to_ascii(trace: AgentTrace, max_width: int = 80) -> str:
        """Generate ASCII visualization of a trajectory."""
        lines = [
            f"Trace: {trace.id}",
            f"Agent: {trace.agent_id} ({trace.agent_version})",
            f"Status: {trace.status} | Duration: {trace.total_duration_ms:.0f}ms | Cost: ${trace.total_cost_usd:.4f}",
            "=" * max_width,
        ]

        for step in trace.steps:
            icon = {"llm_call": "🧠", "tool_call": "🔧", "decision": "🔀", "observation": "👁"}.get(
                step.step_type, "•"
            )
            error_mark = " ❌" if step.error else ""
            line = f"  {step.step_index:2d}. [{icon}] {step.step_type}"
            if step.tool_name:
                line += f" → {step.tool_name}"
            line += f" ({step.duration_ms:.0f}ms, ${step.cost_usd:.4f}){error_mark}"
            lines.append(line)

        lines.append("=" * max_width)
        return "\n".join(lines)

    @staticmethod
    def compare_trajectories(traces: list[AgentTrace]) -> dict:
        """Compare multiple trajectories for the same goal."""
        return {
            "traces": len(traces),
            "avg_steps": statistics.mean(len(t.steps) for t in traces),
            "avg_duration": statistics.mean(t.total_duration_ms for t in traces),
            "avg_cost": statistics.mean(t.total_cost_usd for t in traces),
            "success_rate": sum(1 for t in traces if t.status == "success") / max(len(traces), 1),
            "common_tools": Counter(
                tool for t in traces for tool in t.tools_used
            ).most_common(10),
            "failure_steps": Counter(
                s.tool_name or s.step_type
                for t in traces for s in t.steps if s.error
            ).most_common(5),
        }


# =============================================================================
# Alert Engine
# =============================================================================

class AlertEngine:
    """Manages alert rules and fires alerts based on metrics."""

    def __init__(self):
        self.rules: list[AlertRule] = []
        self.active_alerts: list[Alert] = []
        self.alert_history: list[Alert] = []
        self.notification_handlers: list[Callable[[Alert], None]] = []

    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def add_notification_handler(self, handler: Callable[[Alert], None]):
        self.notification_handlers.append(handler)

    def evaluate(self, metrics: AgentMetrics):
        """Evaluate all rules against current metrics."""
        for rule in self.rules:
            if not rule.enabled:
                continue
            if rule.agent_id != "*" and rule.agent_id != metrics.agent_id:
                continue

            # Check cooldown
            if rule.last_fired:
                cooldown_end = datetime.fromisoformat(rule.last_fired) + timedelta(minutes=rule.cooldown_minutes)
                if datetime.now(timezone.utc) < cooldown_end:
                    continue

            metric_value = self._get_metric_value(metrics, rule.metric_name)
            if metric_value is None:
                continue

            if self._check_condition(metric_value, rule.condition, rule.threshold):
                self._fire_alert(rule, metrics.agent_id, metric_value)

    def acknowledge_alert(self, alert_id: str, user: str):
        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_by = user
                return

    def resolve_alert(self, alert_id: str):
        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now(timezone.utc).isoformat()
                self.alert_history.append(alert)
                self.active_alerts.remove(alert)
                return

    def get_active_alerts(self, agent_id: Optional[str] = None) -> list[Alert]:
        if agent_id:
            return [a for a in self.active_alerts if a.agent_id == agent_id]
        return self.active_alerts

    def _fire_alert(self, rule: AlertRule, agent_id: str, metric_value: float):
        alert = Alert(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            severity=rule.severity,
            title=f"{rule.name}: {rule.metric_name} {rule.condition} {rule.threshold}",
            description=f"Metric {rule.metric_name} = {metric_value:.4f} (threshold: {rule.threshold})",
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold=rule.threshold,
            fired_at=datetime.now(timezone.utc).isoformat(),
        )
        self.active_alerts.append(alert)
        rule.last_fired = alert.fired_at

        for handler in self.notification_handlers:
            try:
                handler(alert)
            except Exception:
                pass

    def _get_metric_value(self, metrics: AgentMetrics, metric_name: str) -> Optional[float]:
        mapping = {
            "success_rate": metrics.success_rate,
            "avg_duration_ms": metrics.avg_duration_ms,
            "p99_duration_ms": metrics.p99_duration_ms,
            "avg_cost_usd": metrics.avg_cost_usd,
            "total_cost_usd": metrics.total_cost_usd,
            "failure_count": float(metrics.failure_count),
            "timeout_count": float(metrics.timeout_count),
            "avg_steps": metrics.avg_steps,
        }
        return mapping.get(metric_name)

    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        ops = {"gt": value > threshold, "lt": value < threshold,
               "gte": value >= threshold, "lte": value <= threshold, "eq": value == threshold}
        return ops.get(condition, False)


# =============================================================================
# Agent Performance Comparator
# =============================================================================

class AgentComparator:
    """Compares performance across agent versions or configurations."""

    def __init__(self, aggregator: MetricsAggregator):
        self.aggregator = aggregator

    def compare(self, agent_ids: list[str], window_start: str, window_end: str) -> dict:
        """Compare metrics across multiple agents/versions."""
        comparison = {}
        for agent_id in agent_ids:
            metrics = self.aggregator.compute_metrics(agent_id, window_start, window_end)
            comparison[agent_id] = {
                "success_rate": metrics.success_rate,
                "avg_duration_ms": metrics.avg_duration_ms,
                "p95_duration_ms": metrics.p95_duration_ms,
                "avg_cost_usd": metrics.avg_cost_usd,
                "avg_steps": metrics.avg_steps,
                "total_traces": metrics.total_traces,
                "top_tools": list(metrics.tool_usage.keys())[:5],
                "top_errors": list(metrics.error_distribution.keys())[:3],
            }

        # Determine best performer per metric
        if len(comparison) > 1:
            comparison["_best"] = {
                "success_rate": max(comparison.keys() - {"_best"}, key=lambda a: comparison[a]["success_rate"]),
                "latency": min(comparison.keys() - {"_best"}, key=lambda a: comparison[a]["avg_duration_ms"]),
                "cost": min(comparison.keys() - {"_best"}, key=lambda a: comparison[a]["avg_cost_usd"]),
            }

        return comparison


# =============================================================================
# Dashboard Controller
# =============================================================================

class AgentOpsDashboard:
    """
    Main dashboard controller aggregating all monitoring capabilities.
    
    Provides:
    - Agent health overview
    - Trajectory visualization and drill-down
    - Tool usage analytics
    - Cost and latency trends
    - Error analysis
    - Performance comparison
    - Alerting
    """

    def __init__(self):
        self.trace_store = TraceStore()
        self.aggregator = MetricsAggregator(self.trace_store)
        self.visualizer = TrajectoryVisualizer()
        self.alert_engine = AlertEngine()
        self.comparator = AgentComparator(self.aggregator)
        self.registered_agents: dict[str, dict] = {}

        # Setup default alert rules
        self._setup_default_alerts()

    def register_agent(self, agent_id: str, version: str, metadata: dict = None):
        """Register an agent for monitoring."""
        self.registered_agents[agent_id] = {
            "version": version,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

    def ingest_trace(self, trace: AgentTrace):
        """Ingest a completed agent trace."""
        self.trace_store.store(trace)

        # Evaluate alerts
        now = datetime.now(timezone.utc)
        metrics = self.aggregator.compute_metrics(
            trace.agent_id,
            (now - timedelta(minutes=5)).isoformat(),
            now.isoformat()
        )
        self.alert_engine.evaluate(metrics)

    # -------------------------------------------------------------------------
    # Dashboard Views
    # -------------------------------------------------------------------------

    def get_health_overview(self) -> dict:
        """Get health overview for all registered agents."""
        now = datetime.now(timezone.utc)
        window_start = (now - timedelta(hours=1)).isoformat()
        window_end = now.isoformat()

        overview = {}
        for agent_id, info in self.registered_agents.items():
            metrics = self.aggregator.compute_metrics(agent_id, window_start, window_end)
            status = self._compute_health_status(metrics)
            overview[agent_id] = {
                "status": status.value,
                "version": info["version"],
                "success_rate": metrics.success_rate,
                "avg_latency_ms": metrics.avg_duration_ms,
                "total_traces_1h": metrics.total_traces,
                "total_cost_1h": metrics.total_cost_usd,
                "active_alerts": len(self.alert_engine.get_active_alerts(agent_id)),
            }
        return overview

    def get_trajectory_view(self, trace_id: str) -> dict:
        """Get detailed trajectory view for drill-down."""
        trace = self.trace_store.get_trace(trace_id)
        if not trace:
            return {"error": "Trace not found"}

        return {
            "summary": {
                "id": trace.id,
                "agent": trace.agent_id,
                "version": trace.agent_version,
                "status": trace.status,
                "duration_ms": trace.total_duration_ms,
                "cost_usd": trace.total_cost_usd,
                "steps": len(trace.steps),
                "goal": trace.goal,
                "outcome": trace.outcome,
            },
            "timeline": self.visualizer.to_timeline(trace),
            "graph": self.visualizer.to_graph(trace),
            "ascii": self.visualizer.to_ascii(trace),
            "tools_used": trace.tools_used,
            "errors": [s.error for s in trace.steps if s.error],
            "user_feedback": trace.user_feedback,
        }

    def get_tool_analytics(self, agent_id: str, hours: int = 24) -> dict:
        """Get tool usage analytics."""
        now = datetime.now(timezone.utc)
        traces = self.trace_store.query(
            agent_id=agent_id,
            since=(now - timedelta(hours=hours)).isoformat(),
            limit=5000
        )

        tool_stats = defaultdict(lambda: {"calls": 0, "errors": 0, "total_duration_ms": 0, "durations": []})

        for trace in traces:
            for step in trace.steps:
                if step.step_type == "tool_call" and step.tool_name:
                    stats = tool_stats[step.tool_name]
                    stats["calls"] += 1
                    stats["total_duration_ms"] += step.duration_ms
                    stats["durations"].append(step.duration_ms)
                    if step.error:
                        stats["errors"] += 1

        # Compute aggregates
        result = {}
        for tool, stats in tool_stats.items():
            result[tool] = {
                "total_calls": stats["calls"],
                "error_rate": stats["errors"] / max(stats["calls"], 1),
                "avg_duration_ms": stats["total_duration_ms"] / max(stats["calls"], 1),
                "p95_duration_ms": sorted(stats["durations"])[int(len(stats["durations"]) * 0.95)] if stats["durations"] else 0,
            }

        return dict(sorted(result.items(), key=lambda x: x[1]["total_calls"], reverse=True))

    def get_cost_trends(self, agent_id: str, periods: int = 24, period_hours: int = 1) -> list[dict]:
        """Get cost and latency trends over time."""
        trends = self.aggregator.compute_trends(agent_id, periods, period_hours)
        return [
            {
                "window_start": m.window_start,
                "total_cost_usd": m.total_cost_usd,
                "avg_cost_usd": m.avg_cost_usd,
                "avg_duration_ms": m.avg_duration_ms,
                "p95_duration_ms": m.p95_duration_ms,
                "total_traces": m.total_traces,
                "success_rate": m.success_rate,
            }
            for m in trends
        ]

    def get_error_analysis(self, agent_id: str, hours: int = 24) -> dict:
        """Analyze errors for an agent."""
        now = datetime.now(timezone.utc)
        traces = self.trace_store.query(
            agent_id=agent_id,
            status="failure",
            since=(now - timedelta(hours=hours)).isoformat(),
            limit=1000,
        )

        error_types = Counter()
        error_tools = Counter()
        error_steps = Counter()
        error_examples = []

        for trace in traces:
            if trace.error_info:
                error_types[trace.error_info.get("type", "unknown")] += 1
            for step in trace.steps:
                if step.error:
                    if step.tool_name:
                        error_tools[step.tool_name] += 1
                    error_steps[step.step_index] += 1

            if len(error_examples) < 10:
                error_examples.append({
                    "trace_id": trace.id,
                    "error": trace.error_info,
                    "steps": len(trace.steps),
                    "duration_ms": trace.total_duration_ms,
                })

        return {
            "total_failures": len(traces),
            "error_type_distribution": dict(error_types.most_common(10)),
            "failing_tools": dict(error_tools.most_common(10)),
            "failure_step_distribution": dict(error_steps.most_common(10)),
            "recent_examples": error_examples,
        }

    def compare_agents(self, agent_ids: list[str], hours: int = 24) -> dict:
        """Compare performance across agents."""
        now = datetime.now(timezone.utc)
        return self.comparator.compare(
            agent_ids,
            (now - timedelta(hours=hours)).isoformat(),
            now.isoformat()
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _compute_health_status(self, metrics: AgentMetrics) -> AgentStatus:
        if metrics.total_traces == 0:
            return AgentStatus.OFFLINE
        if metrics.success_rate >= 0.95 and metrics.p99_duration_ms < 10000:
            return AgentStatus.HEALTHY
        if metrics.success_rate >= 0.8:
            return AgentStatus.DEGRADED
        return AgentStatus.UNHEALTHY

    def _setup_default_alerts(self):
        self.alert_engine.add_rule(AlertRule(
            id="low-success-rate", name="Low Success Rate", agent_id="*",
            metric_name="success_rate", condition="lt", threshold=0.8,
            severity=AlertSeverity.ERROR, window_minutes=5
        ))
        self.alert_engine.add_rule(AlertRule(
            id="high-latency", name="High P99 Latency", agent_id="*",
            metric_name="p99_duration_ms", condition="gt", threshold=30000,
            severity=AlertSeverity.WARNING, window_minutes=5
        ))
        self.alert_engine.add_rule(AlertRule(
            id="high-cost", name="High Cost", agent_id="*",
            metric_name="total_cost_usd", condition="gt", threshold=100.0,
            severity=AlertSeverity.WARNING, window_minutes=60
        ))


# =============================================================================
# Usage Example
# =============================================================================

def main():
    """Demonstrate the AgentOps dashboard."""
    dashboard = AgentOpsDashboard()

    # Register agents
    dashboard.register_agent("support-agent", "v2.3", {"team": "support"})
    dashboard.register_agent("research-agent", "v1.1", {"team": "research"})

    # Simulate traces
    tools = ["search_kb", "query_db", "send_email", "create_ticket", "lookup_user"]

    for i in range(200):
        agent_id = "support-agent" if i % 3 != 0 else "research-agent"
        num_steps = random.randint(2, 8)
        status = "success" if random.random() < 0.85 else random.choice(["failure", "timeout"])
        total_duration = 0
        total_cost = 0
        steps = []
        used_tools = []

        for j in range(num_steps):
            step_type = random.choice(["llm_call", "tool_call", "tool_call", "observation"])
            tool_name = random.choice(tools) if step_type == "tool_call" else None
            duration = random.uniform(100, 3000)
            cost = random.uniform(0.001, 0.02)
            error = None
            if status == "failure" and j == num_steps - 1:
                error = f"Tool {tool_name} returned error: timeout"

            steps.append(TrajectoryStep(
                step_index=j,
                step_type=step_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_ms=duration,
                input_data={"query": f"step {j} input"},
                output_data={"result": f"step {j} output"},
                tool_name=tool_name,
                cost_usd=cost,
                error=error,
            ))
            total_duration += duration
            total_cost += cost
            if tool_name:
                used_tools.append(tool_name)

        trace = AgentTrace(
            id=f"trace-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            agent_version=dashboard.registered_agents[agent_id]["version"],
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            status=status,
            steps=steps,
            total_duration_ms=total_duration,
            total_cost_usd=total_cost,
            total_tokens={"input": random.randint(500, 2000), "output": random.randint(200, 1000)},
            tools_used=list(set(used_tools)),
            goal=f"Handle user request #{i}",
            error_info={"type": "tool_timeout", "tool": tools[0]} if status == "failure" else None,
        )
        dashboard.ingest_trace(trace)

    # Dashboard views
    print("=== Agent Health Overview ===")
    overview = dashboard.get_health_overview()
    for agent_id, health in overview.items():
        print(f"  {agent_id}: {health['status']} "
              f"(success={health['success_rate']:.1%}, "
              f"latency={health['avg_latency_ms']:.0f}ms, "
              f"cost=${health['total_cost_1h']:.2f})")

    print("\n=== Tool Analytics (support-agent) ===")
    tool_analytics = dashboard.get_tool_analytics("support-agent")
    for tool, stats in list(tool_analytics.items())[:5]:
        print(f"  {tool}: {stats['total_calls']} calls, "
              f"err_rate={stats['error_rate']:.1%}, "
              f"avg={stats['avg_duration_ms']:.0f}ms")

    print("\n=== Error Analysis (support-agent) ===")
    errors = dashboard.get_error_analysis("support-agent")
    print(f"  Total failures: {errors['total_failures']}")
    print(f"  Error types: {errors['error_type_distribution']}")
    print(f"  Failing tools: {errors['failing_tools']}")

    print("\n=== Agent Comparison ===")
    comparison = dashboard.compare_agents(["support-agent", "research-agent"])
    for agent_id, stats in comparison.items():
        if not agent_id.startswith("_"):
            print(f"  {agent_id}: success={stats['success_rate']:.1%}, "
                  f"latency={stats['avg_duration_ms']:.0f}ms, "
                  f"cost=${stats['avg_cost_usd']:.4f}")

    print("\n=== Active Alerts ===")
    alerts = dashboard.alert_engine.get_active_alerts()
    for alert in alerts:
        print(f"  [{alert.severity.value}] {alert.title} (agent: {alert.agent_id})")

    # Drill-down into a trace
    print("\n=== Trajectory Drill-Down (latest trace) ===")
    latest_traces = dashboard.trace_store.query(agent_id="support-agent", limit=1)
    if latest_traces:
        view = dashboard.get_trajectory_view(latest_traces[0].id)
        print(view["ascii"])


if __name__ == "__main__":
    main()
