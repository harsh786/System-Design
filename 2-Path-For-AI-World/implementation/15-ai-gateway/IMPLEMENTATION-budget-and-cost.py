"""
Budget Enforcement & Cost Management System for AI Gateway.

Handles per-tenant budget allocation, real-time cost computation,
anomaly detection, forecasting, and cost optimization recommendations.
"""

import asyncio
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class BudgetPeriod(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class EnforcementAction(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    THROTTLE = "throttle"       # Downgrade to cheaper model
    QUEUE = "queue"             # Queue for next period
    REJECT = "reject"          # Hard reject


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class BudgetConfig:
    """Budget configuration for a tenant/project/user."""
    tenant_id: str
    # Limits
    monthly_limit_usd: float = 1000.0
    daily_limit_usd: float = 50.0
    hourly_limit_usd: float = 10.0
    per_request_limit_usd: float = 5.0
    # Token limits
    monthly_token_limit: Optional[int] = None
    daily_token_limit: Optional[int] = None
    # Alert thresholds (percentage of limit)
    warn_threshold: float = 0.7
    critical_threshold: float = 0.9
    # Enforcement
    enforcement_action: EnforcementAction = EnforcementAction.REJECT
    allow_overage: bool = False
    overage_limit_pct: float = 0.1  # Allow 10% overage
    # Priority override
    allow_critical_override: bool = True  # Allow critical priority to bypass
    # Model restrictions when throttled
    throttle_to_models: List[str] = field(default_factory=lambda: ["gpt-4o-mini", "claude-3-5-haiku"])


@dataclass
class CostRecord:
    """A single cost record for a request."""
    request_id: str
    tenant_id: str
    user_id: str
    project_id: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    timestamp: float
    # Attribution
    feature: Optional[str] = None
    endpoint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetStatus:
    """Current budget status for a tenant."""
    tenant_id: str
    period: BudgetPeriod
    limit: float
    spent: float
    remaining: float
    usage_pct: float
    enforcement_action: EnforcementAction
    alert_level: Optional[AlertSeverity] = None
    forecast_end_of_period: Optional[float] = None


@dataclass
class BudgetAlert:
    """Budget alert notification."""
    tenant_id: str
    severity: AlertSeverity
    message: str
    current_spend: float
    limit: float
    period: BudgetPeriod
    timestamp: float = field(default_factory=time.time)


@dataclass
class CostAnomaly:
    """Detected cost anomaly."""
    tenant_id: str
    anomaly_type: str  # "spike", "unusual_model", "unusual_time", "velocity"
    description: str
    expected_value: float
    actual_value: float
    deviation_factor: float
    timestamp: float = field(default_factory=time.time)


# ============================================================================
# Pricing Engine
# ============================================================================

class PricingEngine:
    """Manages model pricing and computes costs."""

    def __init__(self):
        # Price per 1K tokens (input, output)
        self._pricing: Dict[str, Tuple[float, float]] = {
            "gpt-4o": (0.0025, 0.01),
            "gpt-4o-mini": (0.00015, 0.0006),
            "gpt-4-turbo": (0.01, 0.03),
            "gpt-3.5-turbo": (0.0005, 0.0015),
            "claude-3-5-sonnet": (0.003, 0.015),
            "claude-3-5-haiku": (0.0008, 0.004),
            "claude-3-opus": (0.015, 0.075),
            "gemini-1.5-pro": (0.00125, 0.005),
            "gemini-1.5-flash": (0.000075, 0.0003),
            "llama-3-70b": (0.0, 0.0),  # Self-hosted (compute cost separate)
            "llama-3-8b": (0.0, 0.0),
        }
        # Cached token discount (some providers charge less for cached prompts)
        self._cache_discount: Dict[str, float] = {
            "claude-3-5-sonnet": 0.9,  # 90% discount on cached input tokens
            "claude-3-5-haiku": 0.9,
            "gpt-4o": 0.5,  # 50% discount
        }

    def compute_cost(self, model: str, input_tokens: int, output_tokens: int,
                     cached_tokens: int = 0) -> Tuple[float, float, float]:
        """Compute cost breakdown. Returns (input_cost, output_cost, total_cost)."""
        pricing = self._pricing.get(model, (0.001, 0.002))
        input_price, output_price = pricing

        # Apply cache discount
        billable_input = input_tokens - cached_tokens
        cache_discount = self._cache_discount.get(model, 1.0)
        cached_cost = (cached_tokens / 1000) * input_price * (1 - cache_discount)
        regular_input_cost = (billable_input / 1000) * input_price
        input_cost = regular_input_cost + cached_cost

        output_cost = (output_tokens / 1000) * output_price
        return input_cost, output_cost, input_cost + output_cost

    def estimate_max_cost(self, model: str, input_tokens: int, max_output_tokens: int) -> float:
        """Estimate maximum possible cost for budget pre-check."""
        _, _, total = self.compute_cost(model, input_tokens, max_output_tokens)
        return total

    def update_pricing(self, model: str, input_per_1k: float, output_per_1k: float):
        self._pricing[model] = (input_per_1k, output_per_1k)

    def get_cheapest_model(self, models: List[str], estimated_tokens: int) -> str:
        """Get cheapest model from a list for given token count."""
        costs = []
        for model in models:
            _, _, total = self.compute_cost(model, estimated_tokens, estimated_tokens // 2)
            costs.append((model, total))
        costs.sort(key=lambda x: x[1])
        return costs[0][0] if costs else models[0]


# ============================================================================
# Budget Store
# ============================================================================

class BudgetStore:
    """In-memory budget tracking (use Redis/DB in production)."""

    def __init__(self):
        self._configs: Dict[str, BudgetConfig] = {}
        # Spend tracking by period
        self._hourly_spend: Dict[str, Dict[int, float]] = defaultdict(dict)  # tenant -> {hour_key -> spend}
        self._daily_spend: Dict[str, Dict[int, float]] = defaultdict(dict)
        self._monthly_spend: Dict[str, Dict[int, float]] = defaultdict(dict)
        # Token tracking
        self._daily_tokens: Dict[str, Dict[int, int]] = defaultdict(dict)
        self._monthly_tokens: Dict[str, Dict[int, int]] = defaultdict(dict)
        # Cost records
        self._records: List[CostRecord] = []
        self._lock = asyncio.Lock()

    def set_config(self, config: BudgetConfig):
        self._configs[config.tenant_id] = config

    def get_config(self, tenant_id: str) -> BudgetConfig:
        return self._configs.get(tenant_id, BudgetConfig(tenant_id=tenant_id))

    def _hour_key(self) -> int:
        return int(time.time() // 3600)

    def _day_key(self) -> int:
        return int(time.time() // 86400)

    def _month_key(self) -> int:
        import datetime
        now = datetime.datetime.utcnow()
        return now.year * 100 + now.month

    async def record_cost(self, record: CostRecord):
        async with self._lock:
            hour = self._hour_key()
            day = self._day_key()
            month = self._month_key()

            self._hourly_spend[record.tenant_id][hour] = \
                self._hourly_spend[record.tenant_id].get(hour, 0) + record.total_cost
            self._daily_spend[record.tenant_id][day] = \
                self._daily_spend[record.tenant_id].get(day, 0) + record.total_cost
            self._monthly_spend[record.tenant_id][month] = \
                self._monthly_spend[record.tenant_id].get(month, 0) + record.total_cost

            total_tokens = record.input_tokens + record.output_tokens
            self._daily_tokens[record.tenant_id][day] = \
                self._daily_tokens[record.tenant_id].get(day, 0) + total_tokens
            self._monthly_tokens[record.tenant_id][month] = \
                self._monthly_tokens[record.tenant_id].get(month, 0) + total_tokens

            self._records.append(record)
            # Keep last 100K records in memory
            if len(self._records) > 100000:
                self._records = self._records[-50000:]

    def get_current_spend(self, tenant_id: str, period: BudgetPeriod) -> float:
        if period == BudgetPeriod.HOURLY:
            return self._hourly_spend[tenant_id].get(self._hour_key(), 0)
        elif period == BudgetPeriod.DAILY:
            return self._daily_spend[tenant_id].get(self._day_key(), 0)
        elif period == BudgetPeriod.MONTHLY:
            return self._monthly_spend[tenant_id].get(self._month_key(), 0)
        return 0.0

    def get_current_tokens(self, tenant_id: str, period: BudgetPeriod) -> int:
        if period == BudgetPeriod.DAILY:
            return self._daily_tokens[tenant_id].get(self._day_key(), 0)
        elif period == BudgetPeriod.MONTHLY:
            return self._monthly_tokens[tenant_id].get(self._month_key(), 0)
        return 0

    def get_spend_history(self, tenant_id: str, period: BudgetPeriod, lookback: int = 30) -> List[float]:
        """Get historical spend for anomaly detection."""
        if period == BudgetPeriod.DAILY:
            today = self._day_key()
            return [
                self._daily_spend[tenant_id].get(today - i, 0)
                for i in range(lookback, 0, -1)
            ]
        elif period == BudgetPeriod.HOURLY:
            current_hour = self._hour_key()
            return [
                self._hourly_spend[tenant_id].get(current_hour - i, 0)
                for i in range(lookback, 0, -1)
            ]
        return []

    def get_records_for_tenant(self, tenant_id: str, since: float) -> List[CostRecord]:
        return [r for r in self._records if r.tenant_id == tenant_id and r.timestamp >= since]


# ============================================================================
# Budget Enforcer
# ============================================================================

class BudgetEnforcer:
    """Enforces budget limits and determines actions."""

    def __init__(self, store: BudgetStore, pricing: PricingEngine):
        self._store = store
        self._pricing = pricing
        self._alert_callbacks: List[Callable[[BudgetAlert], Any]] = []

    def add_alert_callback(self, callback: Callable[[BudgetAlert], Any]):
        self._alert_callbacks.append(callback)

    async def check_budget(
        self, tenant_id: str, model: str, estimated_input_tokens: int,
        max_output_tokens: int, priority: str = "normal"
    ) -> Tuple[EnforcementAction, Optional[str], Optional[str]]:
        """
        Check if request is within budget.
        Returns: (action, message, suggested_model)
        - action: what to do
        - message: human-readable explanation
        - suggested_model: alternative model if throttled
        """
        config = self._store.get_config(tenant_id)
        estimated_cost = self._pricing.estimate_max_cost(model, estimated_input_tokens, max_output_tokens)

        # Critical priority override
        if priority == "critical" and config.allow_critical_override:
            return EnforcementAction.ALLOW, None, None

        # Per-request limit
        if estimated_cost > config.per_request_limit_usd:
            return (
                EnforcementAction.REJECT,
                f"Estimated cost ${estimated_cost:.4f} exceeds per-request limit ${config.per_request_limit_usd:.2f}",
                self._get_cheaper_model(config, estimated_input_tokens)
            )

        # Check each period
        checks = [
            (BudgetPeriod.HOURLY, config.hourly_limit_usd),
            (BudgetPeriod.DAILY, config.daily_limit_usd),
            (BudgetPeriod.MONTHLY, config.monthly_limit_usd),
        ]

        for period, limit in checks:
            current_spend = self._store.get_current_spend(tenant_id, period)
            projected = current_spend + estimated_cost
            usage_pct = projected / limit if limit > 0 else 0

            # Check alerts
            if usage_pct >= config.critical_threshold:
                await self._emit_alert(BudgetAlert(
                    tenant_id=tenant_id,
                    severity=AlertSeverity.CRITICAL,
                    message=f"{period.value} budget at {usage_pct:.0%}",
                    current_spend=current_spend,
                    limit=limit,
                    period=period,
                ))
            elif usage_pct >= config.warn_threshold:
                await self._emit_alert(BudgetAlert(
                    tenant_id=tenant_id,
                    severity=AlertSeverity.WARNING,
                    message=f"{period.value} budget at {usage_pct:.0%}",
                    current_spend=current_spend,
                    limit=limit,
                    period=period,
                ))

            # Enforce limits
            if projected > limit:
                overage_allowed = limit * (1 + config.overage_limit_pct) if config.allow_overage else limit
                if projected > overage_allowed:
                    if config.enforcement_action == EnforcementAction.THROTTLE:
                        suggested = self._get_cheaper_model(config, estimated_input_tokens)
                        return (
                            EnforcementAction.THROTTLE,
                            f"{period.value} budget exceeded: ${current_spend:.2f}/${limit:.2f}. Throttling to cheaper model.",
                            suggested
                        )
                    elif config.enforcement_action == EnforcementAction.QUEUE:
                        return (
                            EnforcementAction.QUEUE,
                            f"{period.value} budget exceeded. Request queued for next period.",
                            None
                        )
                    else:
                        return (
                            EnforcementAction.REJECT,
                            f"{period.value} budget exceeded: ${current_spend:.2f}/${limit:.2f}",
                            None
                        )

        # Token limits
        if config.daily_token_limit:
            daily_tokens = self._store.get_current_tokens(tenant_id, BudgetPeriod.DAILY)
            if daily_tokens + estimated_input_tokens + max_output_tokens > config.daily_token_limit:
                return (
                    EnforcementAction.REJECT,
                    f"Daily token limit exceeded: {daily_tokens}/{config.daily_token_limit}",
                    None
                )

        return EnforcementAction.ALLOW, None, None

    def _get_cheaper_model(self, config: BudgetConfig, estimated_tokens: int) -> Optional[str]:
        if config.throttle_to_models:
            return self._pricing.get_cheapest_model(config.throttle_to_models, estimated_tokens)
        return None

    async def _emit_alert(self, alert: BudgetAlert):
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def get_budget_status(self, tenant_id: str) -> List[BudgetStatus]:
        """Get current budget status across all periods."""
        config = self._store.get_config(tenant_id)
        statuses = []

        for period, limit in [
            (BudgetPeriod.HOURLY, config.hourly_limit_usd),
            (BudgetPeriod.DAILY, config.daily_limit_usd),
            (BudgetPeriod.MONTHLY, config.monthly_limit_usd),
        ]:
            spent = self._store.get_current_spend(tenant_id, period)
            usage_pct = spent / limit if limit > 0 else 0
            remaining = max(0, limit - spent)

            alert_level = None
            if usage_pct >= config.critical_threshold:
                alert_level = AlertSeverity.CRITICAL
            elif usage_pct >= config.warn_threshold:
                alert_level = AlertSeverity.WARNING

            statuses.append(BudgetStatus(
                tenant_id=tenant_id,
                period=period,
                limit=limit,
                spent=spent,
                remaining=remaining,
                usage_pct=usage_pct,
                enforcement_action=config.enforcement_action,
                alert_level=alert_level,
            ))

        return statuses


# ============================================================================
# Cost Anomaly Detector
# ============================================================================

class CostAnomalyDetector:
    """Detects unusual spending patterns using statistical methods."""

    def __init__(self, store: BudgetStore, z_score_threshold: float = 3.0):
        self._store = store
        self._z_threshold = z_score_threshold
        self._alert_callbacks: List[Callable[[CostAnomaly], Any]] = []

    def add_alert_callback(self, callback: Callable[[CostAnomaly], Any]):
        self._alert_callbacks.append(callback)

    async def check_for_anomalies(self, tenant_id: str, current_cost: float) -> List[CostAnomaly]:
        """Check if current spending is anomalous."""
        anomalies = []

        # Hourly spend spike detection
        hourly_history = self._store.get_spend_history(tenant_id, BudgetPeriod.HOURLY, 24)
        anomaly = self._detect_spike(tenant_id, hourly_history, current_cost, "hourly_spike")
        if anomaly:
            anomalies.append(anomaly)

        # Daily velocity check
        daily_history = self._store.get_spend_history(tenant_id, BudgetPeriod.DAILY, 30)
        anomaly = self._detect_spike(tenant_id, daily_history, current_cost, "daily_velocity")
        if anomaly:
            anomalies.append(anomaly)

        # Emit alerts
        for anomaly in anomalies:
            for callback in self._alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(anomaly)
                    else:
                        callback(anomaly)
                except Exception as e:
                    logger.error(f"Anomaly callback error: {e}")

        return anomalies

    def _detect_spike(self, tenant_id: str, history: List[float],
                      current: float, anomaly_type: str) -> Optional[CostAnomaly]:
        """Detect if current value is a statistical outlier."""
        if len(history) < 5:
            return None

        # Filter out zeros for meaningful statistics
        non_zero = [v for v in history if v > 0]
        if len(non_zero) < 3:
            return None

        mean = sum(non_zero) / len(non_zero)
        if mean == 0:
            return None

        variance = sum((x - mean) ** 2 for x in non_zero) / len(non_zero)
        std = math.sqrt(variance) if variance > 0 else mean * 0.1

        if std == 0:
            return None

        z_score = (current - mean) / std

        if z_score > self._z_threshold:
            return CostAnomaly(
                tenant_id=tenant_id,
                anomaly_type=anomaly_type,
                description=f"Spending {z_score:.1f} standard deviations above normal",
                expected_value=mean,
                actual_value=current,
                deviation_factor=z_score,
            )
        return None


# ============================================================================
# Budget Forecaster
# ============================================================================

class BudgetForecaster:
    """Forecasts end-of-period spend based on current trajectory."""

    def __init__(self, store: BudgetStore):
        self._store = store

    def forecast_monthly_spend(self, tenant_id: str) -> Dict[str, Any]:
        """Forecast monthly spend based on daily run rate."""
        import datetime
        now = datetime.datetime.utcnow()
        days_elapsed = now.day
        days_in_month = 30  # Simplified

        daily_history = self._store.get_spend_history(tenant_id, BudgetPeriod.DAILY, days_elapsed)
        if not daily_history:
            return {"forecast": 0, "confidence": "low"}

        # Simple linear extrapolation
        total_so_far = sum(daily_history)
        daily_avg = total_so_far / max(1, len([d for d in daily_history if d > 0]))
        remaining_days = days_in_month - days_elapsed

        # Weighted average (recent days weighted more)
        if len(daily_history) >= 7:
            recent_avg = sum(daily_history[-7:]) / 7
            overall_avg = daily_avg
            weighted_avg = recent_avg * 0.7 + overall_avg * 0.3
        else:
            weighted_avg = daily_avg

        forecast = total_so_far + (weighted_avg * remaining_days)

        # Confidence based on data points and variance
        variance = sum((d - daily_avg) ** 2 for d in daily_history if d > 0) / max(1, len(daily_history))
        cv = math.sqrt(variance) / daily_avg if daily_avg > 0 else 1.0

        confidence = "high" if cv < 0.3 else ("medium" if cv < 0.7 else "low")

        config = self._store.get_config(tenant_id)
        return {
            "forecast_total": round(forecast, 2),
            "daily_run_rate": round(weighted_avg, 2),
            "days_remaining": remaining_days,
            "spent_so_far": round(total_so_far, 2),
            "monthly_limit": config.monthly_limit_usd,
            "projected_usage_pct": round(forecast / config.monthly_limit_usd * 100, 1) if config.monthly_limit_usd > 0 else 0,
            "confidence": confidence,
            "will_exceed_budget": forecast > config.monthly_limit_usd,
            "estimated_exceed_date": self._estimate_exceed_date(
                total_so_far, weighted_avg, config.monthly_limit_usd, days_elapsed
            ),
        }

    def _estimate_exceed_date(self, current_spend: float, daily_rate: float,
                              limit: float, current_day: int) -> Optional[int]:
        """Estimate which day of month budget will be exceeded."""
        if daily_rate <= 0 or current_spend >= limit:
            return current_day
        remaining_budget = limit - current_spend
        days_until_exceeded = remaining_budget / daily_rate
        exceed_day = current_day + int(days_until_exceeded)
        return exceed_day if exceed_day <= 31 else None


# ============================================================================
# Cost Allocation Reporter
# ============================================================================

class CostAllocationReporter:
    """Generate cost allocation reports by various dimensions."""

    def __init__(self, store: BudgetStore):
        self._store = store

    def generate_report(self, tenant_id: str, since: float) -> Dict[str, Any]:
        """Generate comprehensive cost allocation report."""
        records = self._store.get_records_for_tenant(tenant_id, since)
        if not records:
            return {"total_cost": 0, "total_requests": 0}

        # Aggregate by dimensions
        by_model: Dict[str, float] = defaultdict(float)
        by_user: Dict[str, float] = defaultdict(float)
        by_project: Dict[str, float] = defaultdict(float)
        by_feature: Dict[str, float] = defaultdict(float)
        by_provider: Dict[str, float] = defaultdict(float)

        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0

        for r in records:
            total_cost += r.total_cost
            total_input_tokens += r.input_tokens
            total_output_tokens += r.output_tokens
            by_model[r.model] += r.total_cost
            by_user[r.user_id] += r.total_cost
            by_project[r.project_id] += r.total_cost
            by_feature[r.feature or "unknown"] += r.total_cost
            by_provider[r.provider] += r.total_cost

        return {
            "period_start": since,
            "period_end": time.time(),
            "total_cost": round(total_cost, 4),
            "total_requests": len(records),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "avg_cost_per_request": round(total_cost / len(records), 6),
            "breakdown": {
                "by_model": dict(sorted(by_model.items(), key=lambda x: x[1], reverse=True)),
                "by_user": dict(sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:20]),
                "by_project": dict(sorted(by_project.items(), key=lambda x: x[1], reverse=True)),
                "by_feature": dict(sorted(by_feature.items(), key=lambda x: x[1], reverse=True)),
                "by_provider": dict(sorted(by_provider.items(), key=lambda x: x[1], reverse=True)),
            },
        }


# ============================================================================
# Cost Optimizer
# ============================================================================

class CostOptimizer:
    """Provides cost optimization recommendations."""

    def __init__(self, store: BudgetStore, pricing: PricingEngine):
        self._store = store
        self._pricing = pricing

    def get_recommendations(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Generate cost optimization recommendations."""
        records = self._store.get_records_for_tenant(tenant_id, time.time() - 86400 * 7)
        if not records:
            return []

        recommendations = []

        # 1. Model downgrade opportunities
        expensive_model_usage = defaultdict(list)
        for r in records:
            if r.model in ["gpt-4o", "claude-3-5-sonnet", "claude-3-opus"]:
                expensive_model_usage[r.model].append(r)

        for model, usages in expensive_model_usage.items():
            # Check if requests are mostly short (could use cheaper model)
            short_requests = [u for u in usages if u.input_tokens < 500 and u.output_tokens < 200]
            if len(short_requests) > len(usages) * 0.5:
                total_cost = sum(u.total_cost for u in short_requests)
                savings = total_cost * 0.8  # Estimate 80% savings with mini model
                recommendations.append({
                    "type": "model_downgrade",
                    "priority": "high" if savings > 10 else "medium",
                    "description": f"{len(short_requests)} requests to {model} could use a cheaper model (short context)",
                    "estimated_savings_usd": round(savings, 2),
                    "suggested_action": f"Route requests with <500 input tokens to gpt-4o-mini or claude-3-5-haiku",
                })

        # 2. Caching opportunities
        # Look for repeated similar prompts
        prompt_hashes: Dict[str, int] = defaultdict(int)
        for r in records:
            # Simple dedup check
            key = f"{r.model}:{r.input_tokens}"
            prompt_hashes[key] += 1

        repeated = {k: v for k, v in prompt_hashes.items() if v > 5}
        if repeated:
            potential_cache_hits = sum(v - 1 for v in repeated.values())
            avg_cost = sum(r.total_cost for r in records) / len(records)
            savings = potential_cache_hits * avg_cost
            recommendations.append({
                "type": "caching",
                "priority": "high" if savings > 5 else "medium",
                "description": f"~{potential_cache_hits} requests could be served from cache",
                "estimated_savings_usd": round(savings, 2),
                "suggested_action": "Enable semantic caching with temperature=0 for deterministic queries",
            })

        # 3. Token optimization
        high_token_requests = [r for r in records if r.output_tokens > 2000]
        if high_token_requests:
            wasted = sum(r.output_tokens - 1000 for r in high_token_requests if r.output_tokens > 1000)
            potential_savings = (wasted / 1000) * 0.01  # Rough estimate
            if potential_savings > 1:
                recommendations.append({
                    "type": "token_optimization",
                    "priority": "medium",
                    "description": f"{len(high_token_requests)} requests generating >2K output tokens",
                    "estimated_savings_usd": round(potential_savings, 2),
                    "suggested_action": "Review max_tokens settings; consider if shorter responses suffice",
                })

        return sorted(recommendations, key=lambda r: r["estimated_savings_usd"], reverse=True)


# ============================================================================
# Main Budget Manager (Facade)
# ============================================================================

class BudgetManager:
    """
    Main facade for all budget and cost management functionality.
    """

    def __init__(self):
        self.pricing = PricingEngine()
        self.store = BudgetStore()
        self.enforcer = BudgetEnforcer(self.store, self.pricing)
        self.anomaly_detector = CostAnomalyDetector(self.store)
        self.forecaster = BudgetForecaster(self.store)
        self.reporter = CostAllocationReporter(self.store)
        self.optimizer = CostOptimizer(self.store, self.pricing)

    def configure_tenant(self, config: BudgetConfig):
        """Set budget configuration for a tenant."""
        self.store.set_config(config)

    async def pre_request_check(
        self, tenant_id: str, model: str,
        estimated_input_tokens: int, max_output_tokens: int,
        priority: str = "normal"
    ) -> Tuple[EnforcementAction, Optional[str], Optional[str]]:
        """
        Pre-request budget check. Call before sending to provider.
        Returns: (action, message, suggested_model)
        """
        return await self.enforcer.check_budget(
            tenant_id, model, estimated_input_tokens, max_output_tokens, priority
        )

    async def record_usage(
        self, tenant_id: str, user_id: str, project_id: str,
        model: str, provider: str,
        input_tokens: int, output_tokens: int,
        feature: Optional[str] = None, request_id: str = "",
        cached_tokens: int = 0
    ):
        """Record usage after successful request."""
        input_cost, output_cost, total_cost = self.pricing.compute_cost(
            model, input_tokens, output_tokens, cached_tokens
        )

        record = CostRecord(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            timestamp=time.time(),
            feature=feature,
        )
        await self.store.record_cost(record)

        # Check for anomalies asynchronously
        asyncio.create_task(self.anomaly_detector.check_for_anomalies(tenant_id, total_cost))

    def get_status(self, tenant_id: str) -> List[BudgetStatus]:
        """Get current budget status."""
        return self.enforcer.get_budget_status(tenant_id)

    def get_forecast(self, tenant_id: str) -> Dict[str, Any]:
        """Get spend forecast."""
        return self.forecaster.forecast_monthly_spend(tenant_id)

    def get_report(self, tenant_id: str, days: int = 7) -> Dict[str, Any]:
        """Get cost allocation report."""
        since = time.time() - (days * 86400)
        return self.reporter.generate_report(tenant_id, since)

    def get_recommendations(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get cost optimization recommendations."""
        return self.optimizer.get_recommendations(tenant_id)


# ============================================================================
# Usage Example
# ============================================================================

async def main():
    manager = BudgetManager()

    # Configure tenant budget
    manager.configure_tenant(BudgetConfig(
        tenant_id="tenant-acme",
        monthly_limit_usd=500.0,
        daily_limit_usd=25.0,
        hourly_limit_usd=5.0,
        per_request_limit_usd=2.0,
        enforcement_action=EnforcementAction.THROTTLE,
        throttle_to_models=["gpt-4o-mini", "claude-3-5-haiku"],
    ))

    # Pre-request check
    action, message, suggested = await manager.pre_request_check(
        tenant_id="tenant-acme",
        model="gpt-4o",
        estimated_input_tokens=5000,
        max_output_tokens=2000,
    )
    print(f"Action: {action.value}, Message: {message}, Suggested: {suggested}")

    # Record usage
    await manager.record_usage(
        tenant_id="tenant-acme",
        user_id="user-1",
        project_id="proj-chatbot",
        model="gpt-4o",
        provider="openai",
        input_tokens=5000,
        output_tokens=1500,
        feature="customer_support",
        request_id="req-001",
    )

    # Get status
    statuses = manager.get_status("tenant-acme")
    for s in statuses:
        print(f"{s.period.value}: ${s.spent:.4f} / ${s.limit:.2f} ({s.usage_pct:.1%})")

    # Get forecast
    forecast = manager.get_forecast("tenant-acme")
    print(f"Monthly forecast: ${forecast['forecast_total']}")

    # Get recommendations
    recs = manager.get_recommendations("tenant-acme")
    for r in recs:
        print(f"[{r['priority']}] {r['description']} - Save ~${r['estimated_savings_usd']}")


if __name__ == "__main__":
    asyncio.run(main())
