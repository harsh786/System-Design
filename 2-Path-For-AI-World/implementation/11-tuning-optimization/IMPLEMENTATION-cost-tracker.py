"""
Comprehensive Cost Tracker
===========================
Tracks, analyzes, and optimizes AI system costs across all dimensions:
- Per-request cost breakdown
- Per-tenant aggregation
- Cost per successful task
- Budget alerts and enforcement
- Forecasting and recommendations
"""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# =============================================================================
# Cost Components
# =============================================================================

class CostComponent(Enum):
    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    EMBEDDING = "embedding"
    RERANKER = "reranker"
    TOOL_EXECUTION = "tool_execution"
    VECTOR_DB = "vector_db"
    INFRASTRUCTURE = "infrastructure"
    HUMAN_REVIEW = "human_review"
    CACHE_COMPUTE = "cache_compute"
    EVALUATION = "evaluation"


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for a single request."""
    request_id: str
    timestamp: float
    tenant_id: str
    model: str
    task_type: str
    success: bool

    # Token costs
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0  # Tokens served from cache (discounted)
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0

    # Retrieval costs
    embedding_tokens: int = 0
    embedding_cost_usd: float = 0.0
    reranker_pairs: int = 0
    reranker_cost_usd: float = 0.0
    vector_db_queries: int = 0
    vector_db_cost_usd: float = 0.0

    # Tool costs
    tool_calls: int = 0
    tool_cost_usd: float = 0.0

    # Other
    infrastructure_cost_usd: float = 0.0
    human_review_cost_usd: float = 0.0
    evaluation_cost_usd: float = 0.0

    # Timing
    latency_ms: float = 0.0
    time_to_first_token_ms: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return (
            self.input_cost_usd + self.output_cost_usd +
            self.embedding_cost_usd + self.reranker_cost_usd +
            self.vector_db_cost_usd + self.tool_cost_usd +
            self.infrastructure_cost_usd + self.human_review_cost_usd +
            self.evaluation_cost_usd
        )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.embedding_tokens

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "model": self.model,
            "task_type": self.task_type,
            "success": self.success,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "breakdown": {
                "input": {"tokens": self.input_tokens, "cost": self.input_cost_usd},
                "output": {"tokens": self.output_tokens, "cost": self.output_cost_usd},
                "cached_tokens": self.cached_tokens,
                "embedding": {"tokens": self.embedding_tokens, "cost": self.embedding_cost_usd},
                "reranker": {"pairs": self.reranker_pairs, "cost": self.reranker_cost_usd},
                "vector_db": {"queries": self.vector_db_queries, "cost": self.vector_db_cost_usd},
                "tools": {"calls": self.tool_calls, "cost": self.tool_cost_usd},
                "infrastructure": self.infrastructure_cost_usd,
                "human_review": self.human_review_cost_usd,
                "evaluation": self.evaluation_cost_usd,
            },
            "latency_ms": self.latency_ms,
        }


# =============================================================================
# Cost Calculator
# =============================================================================

class CostCalculator:
    """Calculates costs based on model pricing."""

    PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00, "cached_input": 1.25},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached_input": 0.075},
        "gpt-4": {"input": 30.00, "output": 60.00, "cached_input": 15.00},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00, "cached_input": 0.30},
        "claude-3-haiku": {"input": 0.25, "output": 1.25, "cached_input": 0.03},
        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
        "text-embedding-3-large": {"input": 0.13, "output": 0.0},
    }

    RERANKER_PRICING = {
        "cohere-rerank-v3": 0.002,  # per 1000 pairs
        "cross-encoder": 0.001,
    }

    def calculate(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        embedding_tokens: int = 0,
        embedding_model: str = "text-embedding-3-small",
        reranker_pairs: int = 0,
        reranker_model: str = "cohere-rerank-v3",
        tool_calls: int = 0,
        tool_cost_per_call: float = 0.001,
    ) -> CostBreakdown:
        """Calculate full cost breakdown."""
        pricing = self.PRICING.get(model, self.PRICING["gpt-4o"])
        embed_pricing = self.PRICING.get(embedding_model, {"input": 0.02, "output": 0.0})

        breakdown = CostBreakdown(
            request_id="",
            timestamp=time.time(),
            tenant_id="",
            model=model,
            task_type="",
            success=True,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            input_cost_usd=((input_tokens - cached_tokens) / 1_000_000 * pricing["input"] +
                           cached_tokens / 1_000_000 * pricing.get("cached_input", pricing["input"] * 0.5)),
            output_cost_usd=output_tokens / 1_000_000 * pricing["output"],
            embedding_tokens=embedding_tokens,
            embedding_cost_usd=embedding_tokens / 1_000_000 * embed_pricing["input"],
            reranker_pairs=reranker_pairs,
            reranker_cost_usd=reranker_pairs / 1000 * self.RERANKER_PRICING.get(reranker_model, 0.002),
            tool_calls=tool_calls,
            tool_cost_usd=tool_calls * tool_cost_per_call,
        )
        return breakdown


# =============================================================================
# Tenant Cost Aggregator
# =============================================================================

@dataclass
class TenantCostSummary:
    """Cost summary for a tenant."""
    tenant_id: str
    period_start: float
    period_end: float
    total_requests: int = 0
    successful_requests: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    cost_by_model: dict = field(default_factory=dict)
    cost_by_component: dict = field(default_factory=dict)
    cost_by_task_type: dict = field(default_factory=dict)
    budget_limit_usd: Optional[float] = None

    @property
    def success_rate(self) -> float:
        return self.successful_requests / max(1, self.total_requests)

    @property
    def cost_per_request(self) -> float:
        return self.total_cost_usd / max(1, self.total_requests)

    @property
    def cost_per_successful_task(self) -> float:
        return self.total_cost_usd / max(1, self.successful_requests)

    @property
    def budget_used_percent(self) -> Optional[float]:
        if self.budget_limit_usd:
            return (self.total_cost_usd / self.budget_limit_usd) * 100
        return None


class TenantCostAggregator:
    """Aggregates costs per tenant with budget management."""

    def __init__(self):
        self.tenant_summaries: dict[str, TenantCostSummary] = {}
        self.tenant_budgets: dict[str, float] = {}  # tenant_id → monthly budget USD
        self.history: list[CostBreakdown] = []

    def set_budget(self, tenant_id: str, monthly_budget_usd: float):
        """Set monthly budget for a tenant."""
        self.tenant_budgets[tenant_id] = monthly_budget_usd

    def record(self, breakdown: CostBreakdown):
        """Record a cost breakdown."""
        self.history.append(breakdown)
        tenant_id = breakdown.tenant_id

        if tenant_id not in self.tenant_summaries:
            self.tenant_summaries[tenant_id] = TenantCostSummary(
                tenant_id=tenant_id,
                period_start=time.time(),
                period_end=time.time(),
                budget_limit_usd=self.tenant_budgets.get(tenant_id),
            )

        summary = self.tenant_summaries[tenant_id]
        summary.total_requests += 1
        if breakdown.success:
            summary.successful_requests += 1
        summary.total_cost_usd += breakdown.total_cost_usd
        summary.total_tokens += breakdown.total_tokens
        summary.period_end = time.time()

        # By model
        summary.cost_by_model[breakdown.model] = (
            summary.cost_by_model.get(breakdown.model, 0) + breakdown.total_cost_usd
        )

        # By component
        components = {
            "input_tokens": breakdown.input_cost_usd,
            "output_tokens": breakdown.output_cost_usd,
            "embedding": breakdown.embedding_cost_usd,
            "reranker": breakdown.reranker_cost_usd,
            "tools": breakdown.tool_cost_usd,
            "infrastructure": breakdown.infrastructure_cost_usd,
        }
        for comp, cost in components.items():
            if cost > 0:
                summary.cost_by_component[comp] = summary.cost_by_component.get(comp, 0) + cost

        # By task type
        if breakdown.task_type:
            summary.cost_by_task_type[breakdown.task_type] = (
                summary.cost_by_task_type.get(breakdown.task_type, 0) + breakdown.total_cost_usd
            )

    def get_summary(self, tenant_id: str) -> Optional[dict]:
        summary = self.tenant_summaries.get(tenant_id)
        if not summary:
            return None
        return {
            "tenant_id": tenant_id,
            "total_requests": summary.total_requests,
            "successful_requests": summary.successful_requests,
            "success_rate": f"{summary.success_rate:.1%}",
            "total_cost_usd": round(summary.total_cost_usd, 4),
            "cost_per_request": round(summary.cost_per_request, 6),
            "cost_per_successful_task": round(summary.cost_per_successful_task, 6),
            "total_tokens": summary.total_tokens,
            "budget_limit_usd": summary.budget_limit_usd,
            "budget_used_percent": f"{summary.budget_used_percent:.1f}%" if summary.budget_used_percent else None,
            "cost_by_model": {k: round(v, 4) for k, v in summary.cost_by_model.items()},
            "cost_by_component": {k: round(v, 4) for k, v in summary.cost_by_component.items()},
            "cost_by_task_type": {k: round(v, 4) for k, v in summary.cost_by_task_type.items()},
        }


# =============================================================================
# Budget Alerts
# =============================================================================

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class BudgetAlert:
    severity: AlertSeverity
    tenant_id: str
    message: str
    current_spend: float
    budget_limit: float
    recommendation: str
    timestamp: float = field(default_factory=time.time)


class BudgetAlertManager:
    """Generates alerts when costs approach or exceed budgets."""

    THRESHOLDS = {
        AlertSeverity.INFO: 0.50,
        AlertSeverity.WARNING: 0.80,
        AlertSeverity.CRITICAL: 0.95,
        AlertSeverity.EMERGENCY: 1.00,
    }

    def __init__(self):
        self.alerts: list[BudgetAlert] = []
        self.alert_callbacks: list[Any] = []
        # Track which alerts we've already fired (avoid spam)
        self._fired: dict[str, set] = defaultdict(set)

    def check(self, tenant_id: str, current_spend: float, budget_limit: float) -> Optional[BudgetAlert]:
        """Check if an alert should fire."""
        if budget_limit <= 0:
            return None

        ratio = current_spend / budget_limit

        for severity, threshold in sorted(self.THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if ratio >= threshold and severity.value not in self._fired[tenant_id]:
                self._fired[tenant_id].add(severity.value)
                alert = BudgetAlert(
                    severity=severity,
                    tenant_id=tenant_id,
                    message=f"Tenant {tenant_id} at {ratio:.0%} of budget (${current_spend:.2f}/${budget_limit:.2f})",
                    current_spend=current_spend,
                    budget_limit=budget_limit,
                    recommendation=self._get_recommendation(severity, ratio),
                )
                self.alerts.append(alert)
                self._notify(alert)
                return alert
        return None

    def _get_recommendation(self, severity: AlertSeverity, ratio: float) -> str:
        recommendations = {
            AlertSeverity.INFO: "Monitor usage trend. No action needed.",
            AlertSeverity.WARNING: "Consider enabling model routing to cheaper models for simple queries.",
            AlertSeverity.CRITICAL: "Switch to degraded mode: smaller model, aggressive caching, shorter responses.",
            AlertSeverity.EMERGENCY: "BLOCK new requests or queue for next billing period. Alert account owner.",
        }
        return recommendations.get(severity, "Monitor")

    def _notify(self, alert: BudgetAlert):
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    def reset_tenant(self, tenant_id: str):
        self._fired[tenant_id] = set()


# =============================================================================
# Cost Forecaster
# =============================================================================

class CostForecaster:
    """Forecasts future costs based on historical patterns."""

    def forecast_daily(self, history: list[CostBreakdown], forecast_days: int = 7) -> dict:
        """Forecast daily costs based on recent history."""
        if not history:
            return {"forecast": [], "confidence": "no_data"}

        # Group by day
        daily_costs: dict[str, float] = defaultdict(float)
        daily_requests: dict[str, int] = defaultdict(int)

        for entry in history:
            day = time.strftime("%Y-%m-%d", time.localtime(entry.timestamp))
            daily_costs[day] += entry.total_cost_usd
            daily_requests[day] += 1

        if len(daily_costs) < 2:
            # Not enough history, use average
            avg_daily = sum(daily_costs.values()) / max(1, len(daily_costs))
            return {
                "forecast": [{"day": f"day_{i+1}", "estimated_cost_usd": round(avg_daily, 2)} for i in range(forecast_days)],
                "confidence": "low",
                "method": "simple_average",
                "avg_daily_cost": round(avg_daily, 2),
            }

        # Simple linear trend
        sorted_days = sorted(daily_costs.keys())
        costs = [daily_costs[d] for d in sorted_days]

        # Moving average of last 7 days
        recent = costs[-7:] if len(costs) >= 7 else costs
        avg = sum(recent) / len(recent)

        # Trend (simple: last vs first)
        if len(recent) >= 3:
            trend = (recent[-1] - recent[0]) / len(recent)
        else:
            trend = 0

        forecast = []
        for i in range(forecast_days):
            estimated = max(0, avg + trend * (i + 1))
            forecast.append({
                "day": f"day_{i+1}",
                "estimated_cost_usd": round(estimated, 2),
            })

        return {
            "forecast": forecast,
            "confidence": "medium" if len(costs) >= 7 else "low",
            "method": "moving_average_with_trend",
            "avg_daily_cost": round(avg, 2),
            "daily_trend": round(trend, 4),
            "projected_monthly": round(avg * 30, 2),
        }

    def forecast_budget_exhaustion(self, tenant_id: str, current_spend: float, budget: float, daily_rate: float) -> dict:
        """Predict when budget will be exhausted."""
        remaining = budget - current_spend
        if daily_rate <= 0:
            return {"days_until_exhaustion": float("inf"), "action": "none"}

        days_remaining = remaining / daily_rate
        return {
            "tenant_id": tenant_id,
            "current_spend_usd": round(current_spend, 2),
            "budget_usd": budget,
            "remaining_usd": round(remaining, 2),
            "daily_rate_usd": round(daily_rate, 2),
            "days_until_exhaustion": round(days_remaining, 1),
            "action": "urgent" if days_remaining < 3 else "monitor" if days_remaining < 7 else "healthy",
        }


# =============================================================================
# Cost Optimization Recommender
# =============================================================================

class CostRecommender:
    """Analyzes cost patterns and recommends optimizations."""

    def analyze(self, history: list[CostBreakdown]) -> list[dict]:
        """Generate optimization recommendations from cost history."""
        if len(history) < 10:
            return [{"recommendation": "Need more data (10+ requests) for analysis"}]

        recommendations = []

        # 1. Check if expensive model is used for simple tasks
        recommendations.extend(self._check_model_overuse(history))

        # 2. Check cache opportunity
        recommendations.extend(self._check_cache_opportunity(history))

        # 3. Check token waste
        recommendations.extend(self._check_token_waste(history))

        # 4. Check success rate
        recommendations.extend(self._check_success_rate(history))

        # Sort by estimated savings
        recommendations.sort(key=lambda r: r.get("estimated_savings_usd", 0), reverse=True)
        return recommendations

    def _check_model_overuse(self, history: list[CostBreakdown]) -> list[dict]:
        """Check if expensive models handle simple tasks."""
        expensive_models = {"gpt-4o", "gpt-4", "claude-3.5-sonnet"}
        expensive_simple = [
            h for h in history
            if h.model in expensive_models and h.output_tokens < 100
        ]

        if len(expensive_simple) > len(history) * 0.3:
            avg_cost = sum(h.total_cost_usd for h in expensive_simple) / len(expensive_simple)
            cheap_cost = avg_cost * 0.1  # Mini model is ~10x cheaper
            savings = (avg_cost - cheap_cost) * len(expensive_simple)
            return [{
                "type": "model_routing",
                "recommendation": f"{len(expensive_simple)} requests ({len(expensive_simple)/len(history)*100:.0f}%) use expensive models for short outputs. Route to smaller model.",
                "estimated_savings_usd": round(savings, 2),
                "priority": "high",
            }]
        return []

    def _check_cache_opportunity(self, history: list[CostBreakdown]) -> list[dict]:
        """Check for repeated similar queries."""
        # Simple dedup check on task types
        task_counts = defaultdict(int)
        task_costs = defaultdict(float)
        for h in history:
            task_counts[h.task_type] += 1
            task_costs[h.task_type] += h.total_cost_usd

        high_repeat_tasks = [(t, c) for t, c in task_counts.items() if c > 5]
        if high_repeat_tasks:
            total_repeat_cost = sum(task_costs[t] for t, _ in high_repeat_tasks)
            potential_savings = total_repeat_cost * 0.4  # Assume 40% cache hit rate
            return [{
                "type": "caching",
                "recommendation": f"High-repeat task types detected. Semantic caching could save ~40% on repeated queries.",
                "estimated_savings_usd": round(potential_savings, 2),
                "priority": "high",
                "details": {t: c for t, c in high_repeat_tasks[:5]},
            }]
        return []

    def _check_token_waste(self, history: list[CostBreakdown]) -> list[dict]:
        """Check for unnecessarily long inputs or outputs."""
        high_input = [h for h in history if h.input_tokens > 4000]
        if len(high_input) > len(history) * 0.5:
            avg_input = sum(h.input_tokens for h in high_input) / len(high_input)
            savings = sum(h.input_cost_usd * 0.4 for h in high_input)  # Assume 40% reduction possible
            return [{
                "type": "token_reduction",
                "recommendation": f"{len(high_input)} requests have >4000 input tokens (avg {avg_input:.0f}). Apply context compression and prompt optimization.",
                "estimated_savings_usd": round(savings, 2),
                "priority": "medium",
            }]
        return []

    def _check_success_rate(self, history: list[CostBreakdown]) -> list[dict]:
        """Check if low success rate is wasting money."""
        failed = [h for h in history if not h.success]
        if len(failed) > len(history) * 0.2:
            wasted = sum(h.total_cost_usd for h in failed)
            return [{
                "type": "quality_improvement",
                "recommendation": f"{len(failed)/len(history)*100:.0f}% failure rate. ${wasted:.2f} spent on failed requests. Fix root cause before optimizing cost.",
                "estimated_savings_usd": round(wasted * 0.5, 2),  # Assume fixing halves failures
                "priority": "critical",
            }]
        return []


# =============================================================================
# Dashboard Data Generator
# =============================================================================

class CostDashboard:
    """Generates dashboard-ready data for cost visualization."""

    def __init__(self, aggregator: TenantCostAggregator, history: list[CostBreakdown]):
        self.aggregator = aggregator
        self.history = history

    def overview(self) -> dict:
        """High-level cost overview."""
        if not self.history:
            return {"status": "no_data"}

        total_cost = sum(h.total_cost_usd for h in self.history)
        total_requests = len(self.history)
        successful = sum(1 for h in self.history if h.success)
        total_tokens = sum(h.total_tokens for h in self.history)

        return {
            "period": {
                "start": time.strftime("%Y-%m-%d", time.localtime(self.history[0].timestamp)),
                "end": time.strftime("%Y-%m-%d", time.localtime(self.history[-1].timestamp)),
            },
            "totals": {
                "cost_usd": round(total_cost, 2),
                "requests": total_requests,
                "successful": successful,
                "tokens": total_tokens,
            },
            "averages": {
                "cost_per_request": round(total_cost / max(1, total_requests), 6),
                "cost_per_successful_task": round(total_cost / max(1, successful), 6),
                "tokens_per_request": total_tokens // max(1, total_requests),
            },
            "rates": {
                "success_rate": f"{successful / max(1, total_requests):.1%}",
                "token_burn_rate_per_hour": self._calc_burn_rate(),
            },
        }

    def cost_by_model(self) -> dict:
        """Cost breakdown by model."""
        by_model = defaultdict(lambda: {"cost": 0.0, "requests": 0, "tokens": 0})
        for h in self.history:
            by_model[h.model]["cost"] += h.total_cost_usd
            by_model[h.model]["requests"] += 1
            by_model[h.model]["tokens"] += h.total_tokens
        return {k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in by_model.items()}

    def cost_by_component(self) -> dict:
        """Cost breakdown by component type."""
        components = defaultdict(float)
        for h in self.history:
            components["input_tokens"] += h.input_cost_usd
            components["output_tokens"] += h.output_cost_usd
            components["embedding"] += h.embedding_cost_usd
            components["reranker"] += h.reranker_cost_usd
            components["tools"] += h.tool_cost_usd
            components["vector_db"] += h.vector_db_cost_usd
            components["infrastructure"] += h.infrastructure_cost_usd
        return {k: round(v, 4) for k, v in sorted(components.items(), key=lambda x: x[1], reverse=True)}

    def top_expensive_tenants(self, n: int = 10) -> list[dict]:
        """Top N most expensive tenants."""
        tenant_costs = defaultdict(float)
        for h in self.history:
            tenant_costs[h.tenant_id] += h.total_cost_usd
        sorted_tenants = sorted(tenant_costs.items(), key=lambda x: x[1], reverse=True)
        return [{"tenant_id": t, "cost_usd": round(c, 4)} for t, c in sorted_tenants[:n]]

    def _calc_burn_rate(self) -> str:
        """Calculate token burn rate per hour."""
        if len(self.history) < 2:
            return "N/A"
        duration_hours = (self.history[-1].timestamp - self.history[0].timestamp) / 3600
        if duration_hours <= 0:
            return "N/A"
        total_tokens = sum(h.total_tokens for h in self.history)
        return f"{total_tokens / duration_hours:.0f} tokens/hour"


# =============================================================================
# Main Cost Tracker
# =============================================================================

class CostTracker:
    """
    Main cost tracking system.
    
    Usage:
        tracker = CostTracker()
        tracker.set_tenant_budget("acme", monthly_budget_usd=100.0)
        
        # After each request:
        breakdown = tracker.record_request(
            request_id="req_123",
            tenant_id="acme",
            model="gpt-4o",
            task_type="customer_support",
            success=True,
            input_tokens=1500,
            output_tokens=300,
            ...
        )
        
        # Get insights:
        tracker.get_dashboard_data()
        tracker.get_recommendations()
    """

    def __init__(self):
        self.calculator = CostCalculator()
        self.aggregator = TenantCostAggregator()
        self.alert_manager = BudgetAlertManager()
        self.forecaster = CostForecaster()
        self.recommender = CostRecommender()
        self.history: list[CostBreakdown] = []

    def set_tenant_budget(self, tenant_id: str, monthly_budget_usd: float):
        """Set monthly budget for a tenant."""
        self.aggregator.set_budget(tenant_id, monthly_budget_usd)

    def record_request(
        self,
        request_id: str,
        tenant_id: str,
        model: str,
        task_type: str,
        success: bool,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        embedding_tokens: int = 0,
        reranker_pairs: int = 0,
        tool_calls: int = 0,
        latency_ms: float = 0,
    ) -> CostBreakdown:
        """Record a request and calculate its cost."""
        breakdown = self.calculator.calculate(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            embedding_tokens=embedding_tokens,
            reranker_pairs=reranker_pairs,
            tool_calls=tool_calls,
        )
        breakdown.request_id = request_id
        breakdown.tenant_id = tenant_id
        breakdown.task_type = task_type
        breakdown.success = success
        breakdown.latency_ms = latency_ms

        self.history.append(breakdown)
        self.aggregator.record(breakdown)

        # Check budget alerts
        summary = self.aggregator.tenant_summaries.get(tenant_id)
        if summary and summary.budget_limit_usd:
            self.alert_manager.check(tenant_id, summary.total_cost_usd, summary.budget_limit_usd)

        return breakdown

    def get_tenant_summary(self, tenant_id: str) -> Optional[dict]:
        return self.aggregator.get_summary(tenant_id)

    def get_dashboard_data(self) -> dict:
        dashboard = CostDashboard(self.aggregator, self.history)
        return {
            "overview": dashboard.overview(),
            "by_model": dashboard.cost_by_model(),
            "by_component": dashboard.cost_by_component(),
            "top_tenants": dashboard.top_expensive_tenants(),
        }

    def get_recommendations(self) -> list[dict]:
        return self.recommender.analyze(self.history)

    def get_forecast(self, days: int = 7) -> dict:
        return self.forecaster.forecast_daily(self.history, days)

    def get_alerts(self) -> list[dict]:
        return [
            {
                "severity": a.severity.value,
                "tenant_id": a.tenant_id,
                "message": a.message,
                "recommendation": a.recommendation,
                "timestamp": a.timestamp,
            }
            for a in self.alert_manager.alerts
        ]


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    tracker = CostTracker()
    tracker.set_tenant_budget("acme", monthly_budget_usd=50.0)
    tracker.set_tenant_budget("beta_corp", monthly_budget_usd=100.0)

    # Simulate requests
    import random
    random.seed(42)

    models = ["gpt-4o", "gpt-4o-mini", "gpt-4o-mini", "gpt-4o-mini"]  # 75% mini
    task_types = ["faq", "support", "billing", "technical"]

    for i in range(50):
        tenant = random.choice(["acme", "beta_corp", "acme"])
        model = random.choice(models)
        task = random.choice(task_types)
        success = random.random() > 0.15  # 85% success rate

        tracker.record_request(
            request_id=f"req_{i:04d}",
            tenant_id=tenant,
            model=model,
            task_type=task,
            success=success,
            input_tokens=random.randint(500, 5000),
            output_tokens=random.randint(50, 800),
            cached_tokens=random.randint(0, 200),
            embedding_tokens=random.randint(50, 200),
            reranker_pairs=random.randint(0, 20),
            tool_calls=random.randint(0, 3),
            latency_ms=random.uniform(200, 3000),
        )

    # Print results
    print("=" * 70)
    print("COST TRACKING DASHBOARD")
    print("=" * 70)

    dashboard = tracker.get_dashboard_data()
    print("\n--- OVERVIEW ---")
    print(json.dumps(dashboard["overview"], indent=2))

    print("\n--- BY MODEL ---")
    print(json.dumps(dashboard["by_model"], indent=2))

    print("\n--- BY COMPONENT ---")
    print(json.dumps(dashboard["by_component"], indent=2))

    print("\n--- TENANT: ACME ---")
    print(json.dumps(tracker.get_tenant_summary("acme"), indent=2))

    print("\n--- RECOMMENDATIONS ---")
    for rec in tracker.get_recommendations():
        print(f"  [{rec.get('priority', 'medium')}] {rec['recommendation']}")
        if rec.get("estimated_savings_usd"):
            print(f"         Est. savings: ${rec['estimated_savings_usd']}")

    print("\n--- FORECAST ---")
    print(json.dumps(tracker.get_forecast(), indent=2))

    print("\n--- ALERTS ---")
    for alert in tracker.get_alerts():
        print(f"  [{alert['severity']}] {alert['message']}")
