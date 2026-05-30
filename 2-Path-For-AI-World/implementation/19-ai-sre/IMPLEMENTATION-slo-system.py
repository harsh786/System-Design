"""
AI SRE - SLO Definition and Monitoring System
==============================================
Comprehensive SLO management for AI systems including definition, measurement,
error budget tracking, burn rate alerting, and automated breach response.
"""

import time
import json
import hashlib
import statistics
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SLO DEFINITION SCHEMA
# =============================================================================

class SLOCategory(Enum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    QUALITY = "quality"
    COST = "cost"
    SAFETY = "safety"
    TOOL_SUCCESS = "tool_success"
    ESCALATION = "escalation"


class SLOWindow(Enum):
    ROLLING_1H = "1h"
    ROLLING_6H = "6h"
    ROLLING_24H = "24h"
    ROLLING_7D = "7d"
    ROLLING_28D = "28d"
    CALENDAR_MONTH = "calendar_month"


class BurnRateSeverity(Enum):
    CRITICAL = "critical"    # 14.4x burn rate, 1h window
    HIGH = "high"            # 6x burn rate, 6h window
    MEDIUM = "medium"        # 3x burn rate, 24h window
    LOW = "low"              # 1x burn rate, 72h window


@dataclass
class SLODefinition:
    """Complete SLO definition for an AI system."""
    id: str
    name: str
    description: str
    category: SLOCategory
    target: float  # e.g., 0.999 for 99.9%
    window: SLOWindow
    sli_query: str  # How to compute the SLI
    unit: str  # "ratio", "milliseconds", "dollars", "count"
    
    # Error budget
    error_budget_policy: str  # "standard", "zero_tolerance", "soft"
    
    # Alerting thresholds
    burn_rate_thresholds: dict = field(default_factory=lambda: {
        "critical": {"burn_rate": 14.4, "short_window": "5m", "long_window": "1h"},
        "high": {"burn_rate": 6.0, "short_window": "30m", "long_window": "6h"},
        "medium": {"burn_rate": 3.0, "short_window": "2h", "long_window": "24h"},
        "low": {"burn_rate": 1.0, "short_window": "6h", "long_window": "72h"},
    })
    
    # Metadata
    owner: str = ""
    team: str = ""
    escalation_contact: str = ""
    dashboard_url: str = ""
    runbook_url: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @property
    def error_budget_fraction(self) -> float:
        """Total allowed failure fraction."""
        return 1.0 - self.target
    
    @property
    def error_budget_minutes_per_month(self) -> float:
        """Minutes of downtime allowed per 30-day month."""
        return self.error_budget_fraction * 30 * 24 * 60


# =============================================================================
# SLI COMPUTATION ENGINE
# =============================================================================

@dataclass
class SLIDataPoint:
    timestamp: datetime
    value: float
    good_events: int = 0
    total_events: int = 0
    metadata: dict = field(default_factory=dict)


class SLIComputer:
    """Computes Service Level Indicators from raw metrics."""
    
    def __init__(self):
        self._computers: dict[SLOCategory, Callable] = {
            SLOCategory.AVAILABILITY: self._compute_availability,
            SLOCategory.LATENCY: self._compute_latency,
            SLOCategory.QUALITY: self._compute_quality,
            SLOCategory.COST: self._compute_cost,
            SLOCategory.SAFETY: self._compute_safety,
            SLOCategory.TOOL_SUCCESS: self._compute_tool_success,
            SLOCategory.ESCALATION: self._compute_escalation,
        }
    
    def compute(self, category: SLOCategory, events: list[dict], 
                window_start: datetime, window_end: datetime) -> SLIDataPoint:
        """Compute SLI for given category and time window."""
        computer = self._computers.get(category)
        if not computer:
            raise ValueError(f"No computer for category: {category}")
        return computer(events, window_start, window_end)
    
    def _compute_availability(self, events: list[dict], 
                              start: datetime, end: datetime) -> SLIDataPoint:
        """
        Availability SLI: successful responses / total requests.
        
        A request is "successful" if:
        - HTTP status is 2xx or 4xx (client errors don't count against us)
        - Response was generated (not a timeout or circuit breaker)
        - No internal error occurred
        """
        total = len(events)
        if total == 0:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0)
        
        good = sum(1 for e in events if self._is_available(e))
        
        return SLIDataPoint(
            timestamp=end,
            value=good / total,
            good_events=good,
            total_events=total,
            metadata={
                "error_breakdown": self._error_breakdown(events),
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
            }
        )
    
    def _is_available(self, event: dict) -> bool:
        status = event.get("status_code", 500)
        if 200 <= status < 400:
            return True
        if 400 <= status < 500:
            return True  # Client errors don't count against availability
        return False
    
    def _error_breakdown(self, events: list[dict]) -> dict:
        breakdown = defaultdict(int)
        for e in events:
            status = e.get("status_code", 500)
            if status >= 500:
                error_type = e.get("error_type", "unknown")
                breakdown[error_type] += 1
        return dict(breakdown)
    
    def _compute_latency(self, events: list[dict], 
                         start: datetime, end: datetime) -> SLIDataPoint:
        """
        Latency SLI: fraction of requests under latency threshold.
        
        Uses p95 calculation - what fraction of requests meet the target.
        """
        if not events:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0)
        
        latencies = [e.get("latency_ms", 0) for e in events]
        latencies.sort()
        
        # Compute percentiles
        p50 = self._percentile(latencies, 50)
        p95 = self._percentile(latencies, 95)
        p99 = self._percentile(latencies, 99)
        
        # SLI: fraction of requests under target
        target_ms = events[0].get("latency_target_ms", 3000)  # Default 3s
        good = sum(1 for l in latencies if l <= target_ms)
        total = len(latencies)
        
        return SLIDataPoint(
            timestamp=end,
            value=good / total,
            good_events=good,
            total_events=total,
            metadata={
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99,
                "target_ms": target_ms,
                "max_ms": max(latencies),
                "min_ms": min(latencies),
            }
        )
    
    def _compute_quality(self, events: list[dict], 
                         start: datetime, end: datetime) -> SLIDataPoint:
        """
        Quality SLI: fraction of responses meeting quality criteria.
        
        Quality dimensions:
        - Groundedness: response supported by retrieved context
        - Relevance: response answers the user's question
        - Coherence: response is well-structured and logical
        - Retrieval recall: relevant docs were retrieved
        """
        if not events:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0)
        
        # Only count evaluated responses (sampling)
        evaluated = [e for e in events if "quality_score" in e]
        if not evaluated:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0,
                              metadata={"note": "no_evaluated_events"})
        
        # Quality threshold
        quality_threshold = 0.7  # Score >= 0.7 is "good"
        good = sum(1 for e in evaluated if e["quality_score"] >= quality_threshold)
        total = len(evaluated)
        
        # Breakdown by dimension
        dimension_scores = defaultdict(list)
        for e in evaluated:
            for dim in ["groundedness", "relevance", "coherence", "retrieval_recall"]:
                if dim in e:
                    dimension_scores[dim].append(e[dim])
        
        dimension_averages = {
            dim: statistics.mean(scores) for dim, scores in dimension_scores.items()
        }
        
        return SLIDataPoint(
            timestamp=end,
            value=good / total,
            good_events=good,
            total_events=total,
            metadata={
                "dimension_averages": dimension_averages,
                "sample_size": total,
                "total_requests": len(events),
                "sampling_rate": total / len(events),
            }
        )
    
    def _compute_cost(self, events: list[dict], 
                      start: datetime, end: datetime) -> SLIDataPoint:
        """
        Cost SLI: fraction of requests within cost budget.
        
        Tracks per-request cost and aggregate cost.
        """
        if not events:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0)
        
        costs = [e.get("cost_usd", 0) for e in events]
        per_request_budget = events[0].get("cost_budget_per_request", 0.10)
        
        good = sum(1 for c in costs if c <= per_request_budget)
        total = len(costs)
        
        total_cost = sum(costs)
        daily_budget = events[0].get("daily_budget_usd", 1000.0)
        
        # Time-proportional budget for the window
        window_hours = (end - start).total_seconds() / 3600
        window_budget = daily_budget * (window_hours / 24)
        
        return SLIDataPoint(
            timestamp=end,
            value=good / total,
            good_events=good,
            total_events=total,
            metadata={
                "total_cost_usd": total_cost,
                "window_budget_usd": window_budget,
                "budget_utilization": total_cost / window_budget if window_budget > 0 else 0,
                "mean_cost_per_request": statistics.mean(costs),
                "p95_cost_per_request": self._percentile(sorted(costs), 95),
                "max_cost_per_request": max(costs),
                "cost_breakdown": self._cost_breakdown(events),
            }
        )
    
    def _cost_breakdown(self, events: list[dict]) -> dict:
        breakdown = defaultdict(float)
        for e in events:
            breakdown["input_tokens"] += e.get("input_token_cost", 0)
            breakdown["output_tokens"] += e.get("output_token_cost", 0)
            breakdown["embeddings"] += e.get("embedding_cost", 0)
            breakdown["tool_calls"] += e.get("tool_call_cost", 0)
            breakdown["retrieval"] += e.get("retrieval_cost", 0)
        return dict(breakdown)
    
    def _compute_safety(self, events: list[dict], 
                        start: datetime, end: datetime) -> SLIDataPoint:
        """
        Safety SLI: count of safety violations (target: 0 critical).
        
        Severity levels:
        - critical: Must be zero (data leakage, harmful content, unauthorized actions)
        - high: PII exposure, policy violations
        - medium: Borderline content
        - low: Tone issues
        """
        if not events:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0)
        
        violations = defaultdict(int)
        for e in events:
            if "safety_violation" in e and e["safety_violation"]:
                severity = e.get("safety_severity", "low")
                violations[severity] += 1
        
        critical_count = violations.get("critical", 0)
        total = len(events)
        good = total - sum(violations.values())
        
        # For safety, value is fraction of safe responses
        # But the SLO is really about critical = 0
        return SLIDataPoint(
            timestamp=end,
            value=1.0 if critical_count == 0 else 0.0,
            good_events=good,
            total_events=total,
            metadata={
                "critical_violations": critical_count,
                "high_violations": violations.get("high", 0),
                "medium_violations": violations.get("medium", 0),
                "low_violations": violations.get("low", 0),
                "total_violations": sum(violations.values()),
            }
        )
    
    def _compute_tool_success(self, events: list[dict], 
                              start: datetime, end: datetime) -> SLIDataPoint:
        """Tool Success SLI: successful tool calls / total tool calls."""
        tool_events = [e for e in events if e.get("event_type") == "tool_call"]
        if not tool_events:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0)
        
        good = sum(1 for e in tool_events if e.get("tool_success", False))
        total = len(tool_events)
        
        # Per-tool breakdown
        per_tool = defaultdict(lambda: {"success": 0, "total": 0})
        for e in tool_events:
            tool_name = e.get("tool_name", "unknown")
            per_tool[tool_name]["total"] += 1
            if e.get("tool_success", False):
                per_tool[tool_name]["success"] += 1
        
        per_tool_rates = {
            name: stats["success"] / stats["total"] 
            for name, stats in per_tool.items()
        }
        
        return SLIDataPoint(
            timestamp=end,
            value=good / total,
            good_events=good,
            total_events=total,
            metadata={
                "per_tool_success_rates": per_tool_rates,
                "worst_tool": min(per_tool_rates, key=per_tool_rates.get) if per_tool_rates else None,
                "failure_reasons": self._tool_failure_reasons(tool_events),
            }
        )
    
    def _tool_failure_reasons(self, events: list[dict]) -> dict:
        reasons = defaultdict(int)
        for e in events:
            if not e.get("tool_success", True):
                reason = e.get("failure_reason", "unknown")
                reasons[reason] += 1
        return dict(reasons)
    
    def _compute_escalation(self, events: list[dict], 
                            start: datetime, end: datetime) -> SLIDataPoint:
        """Escalation Quality SLI: appropriate escalations / total escalations."""
        escalation_events = [e for e in events if e.get("event_type") == "escalation"]
        if not escalation_events:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0)
        
        # Only count reviewed escalations
        reviewed = [e for e in escalation_events if "escalation_appropriate" in e]
        if not reviewed:
            return SLIDataPoint(timestamp=end, value=1.0, good_events=0, total_events=0,
                              metadata={"note": "no_reviewed_escalations"})
        
        good = sum(1 for e in reviewed if e["escalation_appropriate"])
        total = len(reviewed)
        
        return SLIDataPoint(
            timestamp=end,
            value=good / total,
            good_events=good,
            total_events=total,
            metadata={
                "total_escalations": len(escalation_events),
                "reviewed_escalations": total,
                "appropriate_rate": good / total,
                "under_escalations": sum(1 for e in events 
                                        if e.get("should_have_escalated", False) 
                                        and e.get("event_type") != "escalation"),
            }
        )
    
    @staticmethod
    def _percentile(sorted_data: list[float], percentile: float) -> float:
        if not sorted_data:
            return 0.0
        index = (percentile / 100) * (len(sorted_data) - 1)
        lower = int(index)
        upper = lower + 1
        if upper >= len(sorted_data):
            return sorted_data[-1]
        weight = index - lower
        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


# =============================================================================
# ERROR BUDGET CALCULATION AND TRACKING
# =============================================================================

@dataclass
class ErrorBudgetStatus:
    slo_id: str
    window_start: datetime
    window_end: datetime
    total_budget: float  # Total error budget (fraction)
    budget_consumed: float  # Fraction of budget consumed
    budget_remaining: float  # Fraction of budget remaining
    burn_rate: float  # Current burn rate (1.0 = on pace to exhaust exactly at window end)
    projected_exhaustion: Optional[datetime]  # When budget will be exhausted at current rate
    status: str  # "healthy", "warning", "critical", "exhausted"
    
    @property
    def budget_remaining_minutes(self) -> float:
        window_minutes = (self.window_end - self.window_start).total_seconds() / 60
        return self.budget_remaining * self.total_budget * window_minutes


class ErrorBudgetTracker:
    """Tracks error budget consumption over time."""
    
    def __init__(self):
        self._slo_definitions: dict[str, SLODefinition] = {}
        self._sli_history: dict[str, list[SLIDataPoint]] = defaultdict(list)
        self._budget_history: dict[str, list[ErrorBudgetStatus]] = defaultdict(list)
    
    def register_slo(self, slo: SLODefinition):
        self._slo_definitions[slo.id] = slo
        logger.info(f"Registered SLO: {slo.id} ({slo.name})")
    
    def record_sli(self, slo_id: str, data_point: SLIDataPoint):
        """Record an SLI measurement."""
        self._sli_history[slo_id].append(data_point)
        # Trim old history (keep last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        self._sli_history[slo_id] = [
            dp for dp in self._sli_history[slo_id] if dp.timestamp > cutoff
        ]
    
    def compute_budget_status(self, slo_id: str) -> ErrorBudgetStatus:
        """Compute current error budget status for an SLO."""
        slo = self._slo_definitions.get(slo_id)
        if not slo:
            raise ValueError(f"Unknown SLO: {slo_id}")
        
        now = datetime.utcnow()
        window_duration = self._get_window_duration(slo.window)
        window_start = now - window_duration
        
        # Get SLI data points in window
        points = [p for p in self._sli_history.get(slo_id, []) 
                  if p.timestamp >= window_start]
        
        if not points:
            return ErrorBudgetStatus(
                slo_id=slo_id, window_start=window_start, window_end=now,
                total_budget=slo.error_budget_fraction,
                budget_consumed=0.0, budget_remaining=1.0,
                burn_rate=0.0, projected_exhaustion=None, status="healthy"
            )
        
        # Calculate total good/bad events
        total_good = sum(p.good_events for p in points)
        total_events = sum(p.total_events for p in points)
        
        if total_events == 0:
            budget_consumed_fraction = 0.0
        else:
            actual_bad_rate = 1.0 - (total_good / total_events)
            budget_consumed_fraction = min(actual_bad_rate / slo.error_budget_fraction, 1.0) \
                if slo.error_budget_fraction > 0 else (1.0 if actual_bad_rate > 0 else 0.0)
        
        budget_remaining = max(0.0, 1.0 - budget_consumed_fraction)
        
        # Burn rate: how fast are we consuming budget relative to window
        elapsed_fraction = min(1.0, (now - window_start).total_seconds() / window_duration.total_seconds())
        expected_consumption = elapsed_fraction  # Linear expectation
        burn_rate = budget_consumed_fraction / expected_consumption if expected_consumption > 0 else 0.0
        
        # Projected exhaustion
        projected_exhaustion = None
        if burn_rate > 1.0 and budget_remaining > 0:
            remaining_time = window_duration * (budget_remaining / burn_rate)
            projected_exhaustion = now + remaining_time
        
        # Status
        if budget_remaining <= 0:
            status = "exhausted"
        elif burn_rate >= 6.0:
            status = "critical"
        elif burn_rate >= 3.0:
            status = "warning"
        else:
            status = "healthy"
        
        budget_status = ErrorBudgetStatus(
            slo_id=slo_id, window_start=window_start, window_end=now + (window_duration - (now - window_start)),
            total_budget=slo.error_budget_fraction,
            budget_consumed=budget_consumed_fraction,
            budget_remaining=budget_remaining,
            burn_rate=burn_rate,
            projected_exhaustion=projected_exhaustion,
            status=status
        )
        
        self._budget_history[slo_id].append(budget_status)
        return budget_status
    
    def _get_window_duration(self, window: SLOWindow) -> timedelta:
        mapping = {
            SLOWindow.ROLLING_1H: timedelta(hours=1),
            SLOWindow.ROLLING_6H: timedelta(hours=6),
            SLOWindow.ROLLING_24H: timedelta(hours=24),
            SLOWindow.ROLLING_7D: timedelta(days=7),
            SLOWindow.ROLLING_28D: timedelta(days=28),
            SLOWindow.CALENDAR_MONTH: timedelta(days=30),
        }
        return mapping.get(window, timedelta(days=28))


# =============================================================================
# BURN RATE ALERTING
# =============================================================================

@dataclass
class BurnRateAlert:
    slo_id: str
    severity: BurnRateSeverity
    burn_rate: float
    short_window_burn: float
    long_window_burn: float
    timestamp: datetime
    message: str
    suggested_action: str


class MultiWindowBurnRateAlerter:
    """
    Implements Google's multi-window, multi-burn-rate alerting.
    
    The key insight: a single burn rate threshold produces either too many
    false positives (low threshold) or misses fast burns (high threshold).
    
    Solution: Use multiple windows with different thresholds.
    - Fast burn (14.4x) detected in short window (5min/1h) → page immediately
    - Medium burn (6x) in medium window (30min/6h) → page
    - Slow burn (3x) in long window (2h/24h) → ticket
    - Very slow burn (1x) in very long window (6h/72h) → alert
    """
    
    def __init__(self, sli_computer: SLIComputer, budget_tracker: ErrorBudgetTracker):
        self._sli_computer = sli_computer
        self._budget_tracker = budget_tracker
        self._alert_callbacks: list[Callable[[BurnRateAlert], None]] = []
        self._suppressed_alerts: dict[str, datetime] = {}  # Dedup
        self._alert_history: list[BurnRateAlert] = []
    
    def register_alert_callback(self, callback: Callable[[BurnRateAlert], None]):
        self._alert_callbacks.append(callback)
    
    def evaluate_all_slos(self, events_by_slo: dict[str, list[dict]]) -> list[BurnRateAlert]:
        """Evaluate burn rates for all registered SLOs."""
        alerts = []
        for slo_id, slo in self._budget_tracker._slo_definitions.items():
            events = events_by_slo.get(slo_id, [])
            slo_alerts = self._evaluate_slo(slo, events)
            alerts.extend(slo_alerts)
        return alerts
    
    def _evaluate_slo(self, slo: SLODefinition, events: list[dict]) -> list[BurnRateAlert]:
        """Evaluate multi-window burn rates for a single SLO."""
        alerts = []
        now = datetime.utcnow()
        
        for severity_name, config in slo.burn_rate_thresholds.items():
            threshold = config["burn_rate"]
            short_window = self._parse_duration(config["short_window"])
            long_window = self._parse_duration(config["long_window"])
            
            # Compute burn rate in both windows
            short_burn = self._compute_burn_rate(slo, events, now - short_window, now)
            long_burn = self._compute_burn_rate(slo, events, now - long_window, now)
            
            # Alert fires only if BOTH windows exceed threshold
            if short_burn >= threshold and long_burn >= threshold:
                severity = BurnRateSeverity(severity_name)
                
                # Dedup: don't fire same alert within cooldown
                alert_key = f"{slo.id}:{severity_name}"
                cooldown = timedelta(minutes=15)
                if alert_key in self._suppressed_alerts:
                    if now - self._suppressed_alerts[alert_key] < cooldown:
                        continue
                
                alert = BurnRateAlert(
                    slo_id=slo.id,
                    severity=severity,
                    burn_rate=long_burn,
                    short_window_burn=short_burn,
                    long_window_burn=long_burn,
                    timestamp=now,
                    message=self._format_alert_message(slo, severity, long_burn),
                    suggested_action=self._suggest_action(slo, severity),
                )
                
                alerts.append(alert)
                self._alert_history.append(alert)
                self._suppressed_alerts[alert_key] = now
                
                # Fire callbacks
                for callback in self._alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.error(f"Alert callback failed: {e}")
        
        return alerts
    
    def _compute_burn_rate(self, slo: SLODefinition, events: list[dict],
                           start: datetime, end: datetime) -> float:
        """Compute burn rate for a specific window."""
        window_events = [e for e in events 
                        if start <= datetime.fromisoformat(e.get("timestamp", "2000-01-01")) <= end]
        
        if not window_events:
            return 0.0
        
        # Compute SLI
        sli = self._sli_computer.compute(slo.category, window_events, start, end)
        
        if sli.total_events == 0:
            return 0.0
        
        # Bad event rate
        bad_rate = 1.0 - (sli.good_events / sli.total_events)
        
        # Burn rate = actual bad rate / allowed bad rate
        if slo.error_budget_fraction == 0:
            return float('inf') if bad_rate > 0 else 0.0
        
        return bad_rate / slo.error_budget_fraction
    
    def _format_alert_message(self, slo: SLODefinition, severity: BurnRateSeverity, 
                              burn_rate: float) -> str:
        return (
            f"[{severity.value.upper()}] SLO '{slo.name}' burning error budget at {burn_rate:.1f}x rate. "
            f"At this rate, budget will be exhausted in "
            f"{self._time_to_exhaustion(burn_rate, slo.window):.1f} hours."
        )
    
    def _suggest_action(self, slo: SLODefinition, severity: BurnRateSeverity) -> str:
        actions = {
            BurnRateSeverity.CRITICAL: f"IMMEDIATE: Execute runbook at {slo.runbook_url}. Page on-call.",
            BurnRateSeverity.HIGH: f"URGENT: Investigate {slo.category.value} degradation. Consider rollback.",
            BurnRateSeverity.MEDIUM: f"Investigate: Check recent deployments and provider status.",
            BurnRateSeverity.LOW: f"Monitor: Track burn rate, create ticket if persists.",
        }
        return actions.get(severity, "Investigate.")
    
    def _time_to_exhaustion(self, burn_rate: float, window: SLOWindow) -> float:
        """Hours until budget exhaustion at current burn rate."""
        window_hours = self._get_window_hours(window)
        if burn_rate <= 0:
            return float('inf')
        return window_hours / burn_rate
    
    def _get_window_hours(self, window: SLOWindow) -> float:
        mapping = {
            SLOWindow.ROLLING_1H: 1, SLOWindow.ROLLING_6H: 6,
            SLOWindow.ROLLING_24H: 24, SLOWindow.ROLLING_7D: 168,
            SLOWindow.ROLLING_28D: 672, SLOWindow.CALENDAR_MONTH: 720,
        }
        return mapping.get(window, 672)
    
    def _parse_duration(self, duration_str: str) -> timedelta:
        """Parse duration string like '5m', '1h', '24h', '72h'."""
        value = int(duration_str[:-1])
        unit = duration_str[-1]
        if unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'h':
            return timedelta(hours=value)
        elif unit == 'd':
            return timedelta(days=value)
        return timedelta(hours=value)


# =============================================================================
# SLO DASHBOARD DATA GENERATION
# =============================================================================

class SLODashboard:
    """Generates dashboard data for SLO visualization."""
    
    def __init__(self, budget_tracker: ErrorBudgetTracker):
        self._tracker = budget_tracker
    
    def generate_overview(self) -> dict:
        """Generate overview dashboard data for all SLOs."""
        slos = []
        for slo_id, slo_def in self._tracker._slo_definitions.items():
            try:
                status = self._tracker.compute_budget_status(slo_id)
                slos.append({
                    "id": slo_id,
                    "name": slo_def.name,
                    "category": slo_def.category.value,
                    "target": slo_def.target,
                    "current_sli": self._get_current_sli(slo_id),
                    "budget_remaining_pct": status.budget_remaining * 100,
                    "burn_rate": status.burn_rate,
                    "status": status.status,
                    "owner": slo_def.owner,
                    "team": slo_def.team,
                })
            except Exception as e:
                logger.error(f"Error computing dashboard for {slo_id}: {e}")
                slos.append({"id": slo_id, "name": slo_def.name, "status": "error", "error": str(e)})
        
        # Summary
        total = len(slos)
        healthy = sum(1 for s in slos if s.get("status") == "healthy")
        warning = sum(1 for s in slos if s.get("status") == "warning")
        critical = sum(1 for s in slos if s.get("status") in ("critical", "exhausted"))
        
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_slos": total,
                "healthy": healthy,
                "warning": warning,
                "critical": critical,
                "overall_health": "critical" if critical > 0 else "warning" if warning > 0 else "healthy",
            },
            "slos": slos,
        }
    
    def generate_slo_detail(self, slo_id: str) -> dict:
        """Generate detailed dashboard data for a single SLO."""
        slo = self._tracker._slo_definitions.get(slo_id)
        if not slo:
            raise ValueError(f"Unknown SLO: {slo_id}")
        
        status = self._tracker.compute_budget_status(slo_id)
        history = self._tracker._sli_history.get(slo_id, [])
        
        # Time series data
        time_series = [
            {"timestamp": p.timestamp.isoformat(), "value": p.value,
             "good": p.good_events, "total": p.total_events}
            for p in history[-168:]  # Last 168 data points
        ]
        
        # Budget history
        budget_series = [
            {"timestamp": b.window_end.isoformat(), "remaining": b.budget_remaining,
             "burn_rate": b.burn_rate, "status": b.status}
            for b in self._tracker._budget_history.get(slo_id, [])[-168:]
        ]
        
        return {
            "slo": {
                "id": slo.id, "name": slo.name, "description": slo.description,
                "category": slo.category.value, "target": slo.target,
                "window": slo.window.value, "owner": slo.owner, "team": slo.team,
            },
            "current_status": {
                "sli_value": self._get_current_sli(slo_id),
                "budget_remaining_pct": status.budget_remaining * 100,
                "burn_rate": status.burn_rate,
                "status": status.status,
                "projected_exhaustion": status.projected_exhaustion.isoformat() if status.projected_exhaustion else None,
            },
            "time_series": time_series,
            "budget_series": budget_series,
        }
    
    def _get_current_sli(self, slo_id: str) -> Optional[float]:
        history = self._tracker._sli_history.get(slo_id, [])
        return history[-1].value if history else None


# =============================================================================
# SLO REVIEW REPORTING
# =============================================================================

class SLOReviewReport:
    """Generates periodic SLO review reports."""
    
    def __init__(self, budget_tracker: ErrorBudgetTracker):
        self._tracker = budget_tracker
    
    def generate_weekly_report(self) -> dict:
        """Generate weekly SLO review report."""
        now = datetime.utcnow()
        week_start = now - timedelta(days=7)
        
        report = {
            "report_type": "weekly_slo_review",
            "period": {"start": week_start.isoformat(), "end": now.isoformat()},
            "generated_at": now.isoformat(),
            "slos": [],
            "recommendations": [],
            "action_items": [],
        }
        
        for slo_id, slo_def in self._tracker._slo_definitions.items():
            # Get data points from last week
            history = [p for p in self._tracker._sli_history.get(slo_id, [])
                      if p.timestamp >= week_start]
            
            if not history:
                continue
            
            # Compute weekly stats
            values = [p.value for p in history]
            total_good = sum(p.good_events for p in history)
            total_events = sum(p.total_events for p in history)
            
            weekly_sli = total_good / total_events if total_events > 0 else 1.0
            met_target = weekly_sli >= slo_def.target
            
            slo_report = {
                "slo_id": slo_id,
                "name": slo_def.name,
                "target": slo_def.target,
                "achieved": weekly_sli,
                "met_target": met_target,
                "total_events": total_events,
                "good_events": total_good,
                "bad_events": total_events - total_good,
                "min_sli": min(values),
                "max_sli": max(values),
                "trend": self._compute_trend(values),
            }
            report["slos"].append(slo_report)
            
            # Generate recommendations
            if not met_target:
                report["recommendations"].append({
                    "slo": slo_def.name,
                    "issue": f"SLO missed: {weekly_sli:.4f} < {slo_def.target}",
                    "suggestion": f"Review incidents, consider relaxing target or investing in reliability.",
                })
            elif weekly_sli > slo_def.target + slo_def.error_budget_fraction * 0.5:
                report["recommendations"].append({
                    "slo": slo_def.name,
                    "issue": f"SLO significantly over-met: {weekly_sli:.4f} >> {slo_def.target}",
                    "suggestion": "Consider tightening target or redirecting reliability investment.",
                })
        
        return report
    
    def _compute_trend(self, values: list[float]) -> str:
        """Compute trend direction from a time series."""
        if len(values) < 2:
            return "stable"
        midpoint = len(values) // 2
        first_half_avg = statistics.mean(values[:midpoint])
        second_half_avg = statistics.mean(values[midpoint:])
        diff = second_half_avg - first_half_avg
        if diff > 0.01:
            return "improving"
        elif diff < -0.01:
            return "degrading"
        return "stable"


# =============================================================================
# SLO BREACH RESPONSE AUTOMATION
# =============================================================================

@dataclass
class BreachResponse:
    action: str
    executed: bool
    timestamp: datetime
    result: str
    rollback_action: Optional[str] = None


class SLOBreachResponder:
    """Automated response to SLO breaches based on category and severity."""
    
    def __init__(self):
        self._response_policies: dict[str, list[dict]] = {}
        self._response_history: list[BreachResponse] = []
        self._dry_run: bool = False
    
    def register_policy(self, slo_id: str, responses: list[dict]):
        """
        Register automated response policy for an SLO.
        
        Each response dict:
        {
            "condition": "budget_remaining < 0.2",
            "actions": ["switch_to_fallback_model", "alert_on_call"],
            "cooldown_minutes": 30,
            "requires_approval": False,
        }
        """
        self._response_policies[slo_id] = responses
    
    def evaluate_and_respond(self, slo_id: str, budget_status: ErrorBudgetStatus) -> list[BreachResponse]:
        """Evaluate policies and execute automated responses."""
        policies = self._response_policies.get(slo_id, [])
        responses = []
        
        for policy in policies:
            if self._condition_met(policy["condition"], budget_status):
                for action in policy["actions"]:
                    response = self._execute_action(action, slo_id, budget_status)
                    responses.append(response)
                    self._response_history.append(response)
        
        return responses
    
    def _condition_met(self, condition: str, status: ErrorBudgetStatus) -> bool:
        """Evaluate a condition against budget status."""
        # Simple condition evaluator
        context = {
            "budget_remaining": status.budget_remaining,
            "burn_rate": status.burn_rate,
            "status": status.status,
            "budget_consumed": status.budget_consumed,
        }
        try:
            return eval(condition, {"__builtins__": {}}, context)
        except Exception:
            return False
    
    def _execute_action(self, action: str, slo_id: str, 
                        status: ErrorBudgetStatus) -> BreachResponse:
        """Execute an automated response action."""
        action_handlers = {
            "switch_to_fallback_model": self._switch_fallback_model,
            "alert_on_call": self._alert_on_call,
            "reduce_traffic": self._reduce_traffic,
            "enable_aggressive_caching": self._enable_caching,
            "rollback_last_deployment": self._rollback_deployment,
            "freeze_deployments": self._freeze_deployments,
            "lower_max_steps": self._lower_max_steps,
            "enable_human_approval": self._enable_human_approval,
        }
        
        handler = action_handlers.get(action)
        if not handler:
            return BreachResponse(
                action=action, executed=False,
                timestamp=datetime.utcnow(),
                result=f"Unknown action: {action}"
            )
        
        if self._dry_run:
            return BreachResponse(
                action=action, executed=False,
                timestamp=datetime.utcnow(),
                result=f"DRY RUN: Would execute {action}"
            )
        
        try:
            result = handler(slo_id, status)
            return BreachResponse(
                action=action, executed=True,
                timestamp=datetime.utcnow(), result=result
            )
        except Exception as e:
            return BreachResponse(
                action=action, executed=False,
                timestamp=datetime.utcnow(),
                result=f"FAILED: {str(e)}"
            )
    
    def _switch_fallback_model(self, slo_id: str, status: ErrorBudgetStatus) -> str:
        logger.warning(f"Switching to fallback model due to SLO breach: {slo_id}")
        # In production: update model routing config
        return "Switched to fallback model"
    
    def _alert_on_call(self, slo_id: str, status: ErrorBudgetStatus) -> str:
        logger.critical(f"PAGING ON-CALL: SLO {slo_id} breach, burn rate {status.burn_rate:.1f}x")
        return f"On-call alerted for {slo_id}"
    
    def _reduce_traffic(self, slo_id: str, status: ErrorBudgetStatus) -> str:
        logger.warning(f"Enabling traffic shedding for SLO: {slo_id}")
        return "Traffic reduced by 50%"
    
    def _enable_caching(self, slo_id: str, status: ErrorBudgetStatus) -> str:
        logger.info(f"Enabling aggressive caching for SLO: {slo_id}")
        return "Aggressive caching enabled"
    
    def _rollback_deployment(self, slo_id: str, status: ErrorBudgetStatus) -> str:
        logger.warning(f"Rolling back last deployment for SLO: {slo_id}")
        return "Last deployment rolled back"
    
    def _freeze_deployments(self, slo_id: str, status: ErrorBudgetStatus) -> str:
        logger.warning(f"Freezing all deployments due to SLO: {slo_id}")
        return "Deployments frozen"
    
    def _lower_max_steps(self, slo_id: str, status: ErrorBudgetStatus) -> str:
        logger.warning(f"Lowering max agent steps for SLO: {slo_id}")
        return "Max steps reduced from 20 to 5"
    
    def _enable_human_approval(self, slo_id: str, status: ErrorBudgetStatus) -> str:
        logger.warning(f"Enabling human approval for all write actions: {slo_id}")
        return "Human approval enabled for write actions"


# =============================================================================
# COMPLETE SLO SYSTEM ORCHESTRATOR
# =============================================================================

class AISLOSystem:
    """
    Complete SLO management system for AI applications.
    
    Integrates SLI computation, error budget tracking, burn rate alerting,
    dashboard generation, and automated breach response.
    """
    
    def __init__(self, dry_run: bool = False):
        self.sli_computer = SLIComputer()
        self.budget_tracker = ErrorBudgetTracker()
        self.alerter = MultiWindowBurnRateAlerter(self.sli_computer, self.budget_tracker)
        self.dashboard = SLODashboard(self.budget_tracker)
        self.review_reporter = SLOReviewReport(self.budget_tracker)
        self.breach_responder = SLOBreachResponder()
        self.breach_responder._dry_run = dry_run
        self._running = False
        self._eval_interval_seconds = 60
    
    def define_ai_slos(self):
        """Define standard AI system SLOs."""
        slos = [
            SLODefinition(
                id="availability", name="AI System Availability",
                description="Fraction of requests that complete successfully",
                category=SLOCategory.AVAILABILITY, target=0.999,
                window=SLOWindow.ROLLING_28D, sli_query="successful/total",
                unit="ratio", error_budget_policy="standard",
                owner="platform-team", team="ai-platform",
            ),
            SLODefinition(
                id="latency_rag", name="RAG Query Latency",
                description="P95 latency for RAG queries under 3 seconds",
                category=SLOCategory.LATENCY, target=0.95,
                window=SLOWindow.ROLLING_28D, sli_query="p95(latency) < 3000ms",
                unit="ratio", error_budget_policy="standard",
                owner="platform-team", team="ai-platform",
            ),
            SLODefinition(
                id="groundedness", name="Response Groundedness",
                description="Fraction of responses that are grounded in source material",
                category=SLOCategory.QUALITY, target=0.85,
                window=SLOWindow.ROLLING_7D, sli_query="grounded/evaluated",
                unit="ratio", error_budget_policy="standard",
                owner="ml-team", team="ai-quality",
            ),
            SLODefinition(
                id="cost", name="Cost Per Request",
                description="Fraction of requests within cost budget",
                category=SLOCategory.COST, target=0.95,
                window=SLOWindow.ROLLING_7D, sli_query="within_budget/total",
                unit="ratio", error_budget_policy="soft",
                owner="platform-team", team="ai-platform",
            ),
            SLODefinition(
                id="safety", name="Safety - Zero Critical Violations",
                description="No critical safety violations in production",
                category=SLOCategory.SAFETY, target=1.0,
                window=SLOWindow.ROLLING_28D, sli_query="critical_violations == 0",
                unit="ratio", error_budget_policy="zero_tolerance",
                owner="trust-safety", team="ai-safety",
            ),
            SLODefinition(
                id="tool_success", name="Tool Call Success Rate",
                description="Fraction of tool calls that succeed",
                category=SLOCategory.TOOL_SUCCESS, target=0.95,
                window=SLOWindow.ROLLING_7D, sli_query="successful_calls/total_calls",
                unit="ratio", error_budget_policy="standard",
                owner="platform-team", team="ai-platform",
            ),
            SLODefinition(
                id="escalation_quality", name="Escalation Quality",
                description="Fraction of escalations that are appropriate",
                category=SLOCategory.ESCALATION, target=0.90,
                window=SLOWindow.ROLLING_28D, sli_query="appropriate/total_escalations",
                unit="ratio", error_budget_policy="standard",
                owner="ops-team", team="ai-ops",
            ),
        ]
        
        for slo in slos:
            self.budget_tracker.register_slo(slo)
        
        # Register breach response policies
        self.breach_responder.register_policy("availability", [
            {"condition": "burn_rate >= 14.4", "actions": ["alert_on_call", "switch_to_fallback_model"], "cooldown_minutes": 15, "requires_approval": False},
            {"condition": "burn_rate >= 6.0", "actions": ["alert_on_call"], "cooldown_minutes": 30, "requires_approval": False},
            {"condition": "budget_remaining < 0.1", "actions": ["freeze_deployments"], "cooldown_minutes": 60, "requires_approval": True},
        ])
        self.breach_responder.register_policy("cost", [
            {"condition": "burn_rate >= 6.0", "actions": ["enable_aggressive_caching", "lower_max_steps"], "cooldown_minutes": 30, "requires_approval": False},
            {"condition": "budget_remaining < 0.2", "actions": ["reduce_traffic", "alert_on_call"], "cooldown_minutes": 60, "requires_approval": False},
        ])
        self.breach_responder.register_policy("safety", [
            {"condition": "budget_remaining < 1.0", "actions": ["alert_on_call", "enable_human_approval", "freeze_deployments"], "cooldown_minutes": 5, "requires_approval": False},
        ])
        
        return slos
    
    def ingest_events(self, events: list[dict]):
        """Ingest raw events and compute SLIs."""
        now = datetime.utcnow()
        window_start = now - timedelta(hours=1)
        
        # Group events by SLO category
        for slo_id, slo_def in self.budget_tracker._slo_definitions.items():
            # Filter events relevant to this SLO
            relevant_events = self._filter_events_for_slo(events, slo_def)
            if not relevant_events:
                continue
            
            # Compute SLI
            sli = self.sli_computer.compute(slo_def.category, relevant_events, window_start, now)
            
            # Record
            self.budget_tracker.record_sli(slo_id, sli)
        
        # Evaluate alerts
        events_by_slo = {
            slo_id: self._filter_events_for_slo(events, slo_def)
            for slo_id, slo_def in self.budget_tracker._slo_definitions.items()
        }
        alerts = self.alerter.evaluate_all_slos(events_by_slo)
        
        # Execute breach responses
        for slo_id in self.budget_tracker._slo_definitions:
            status = self.budget_tracker.compute_budget_status(slo_id)
            self.breach_responder.evaluate_and_respond(slo_id, status)
        
        return alerts
    
    def _filter_events_for_slo(self, events: list[dict], slo: SLODefinition) -> list[dict]:
        """Filter events relevant to a specific SLO."""
        category_filters = {
            SLOCategory.AVAILABILITY: lambda e: e.get("event_type") in ("request", "response"),
            SLOCategory.LATENCY: lambda e: "latency_ms" in e,
            SLOCategory.QUALITY: lambda e: "quality_score" in e or e.get("event_type") == "response",
            SLOCategory.COST: lambda e: "cost_usd" in e,
            SLOCategory.SAFETY: lambda e: True,  # All events checked for safety
            SLOCategory.TOOL_SUCCESS: lambda e: e.get("event_type") == "tool_call",
            SLOCategory.ESCALATION: lambda e: e.get("event_type") == "escalation",
        }
        filter_fn = category_filters.get(slo.category, lambda e: True)
        return [e for e in events if filter_fn(e)]
    
    def get_status(self) -> dict:
        """Get complete system status."""
        return self.dashboard.generate_overview()


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize SLO system
    system = AISLOSystem(dry_run=True)
    slos = system.define_ai_slos()
    
    print(f"Defined {len(slos)} SLOs:")
    for slo in slos:
        print(f"  - {slo.name}: target={slo.target}, budget={slo.error_budget_fraction:.4f}")
    
    # Simulate events
    import random
    now = datetime.utcnow()
    events = []
    for i in range(1000):
        event = {
            "event_type": "response",
            "timestamp": (now - timedelta(minutes=random.randint(0, 60))).isoformat(),
            "status_code": random.choices([200, 500], weights=[99, 1])[0],
            "latency_ms": random.gauss(1500, 500),
            "cost_usd": random.gauss(0.05, 0.02),
            "quality_score": random.gauss(0.85, 0.1) if random.random() < 0.1 else None,
            "safety_violation": random.random() < 0.001,
            "safety_severity": "low",
        }
        # Remove None quality scores
        if event["quality_score"] is None:
            del event["quality_score"]
        events.append(event)
    
    # Add some tool call events
    for i in range(200):
        events.append({
            "event_type": "tool_call",
            "timestamp": (now - timedelta(minutes=random.randint(0, 60))).isoformat(),
            "tool_name": random.choice(["search", "calculator", "database", "email"]),
            "tool_success": random.random() < 0.96,
            "failure_reason": random.choice(["timeout", "permission_denied", "invalid_params"]) if random.random() < 0.04 else None,
        })
    
    # Ingest and evaluate
    alerts = system.ingest_events(events)
    
    print(f"\nAlerts fired: {len(alerts)}")
    for alert in alerts:
        print(f"  [{alert.severity.value}] {alert.message}")
    
    # Generate dashboard
    overview = system.get_status()
    print(f"\nSystem Health: {overview['summary']['overall_health']}")
    print(f"  Healthy: {overview['summary']['healthy']}")
    print(f"  Warning: {overview['summary']['warning']}")
    print(f"  Critical: {overview['summary']['critical']}")
