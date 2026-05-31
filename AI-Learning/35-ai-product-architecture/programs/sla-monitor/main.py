"""
AI SLA Monitor - Simulates multi-dimensional SLA monitoring for AI systems.

Monitors: availability, latency, quality, safety, and cost SLAs.
Detects breaches with severity levels and triggers automated responses.
Produces a compliance report at the end.

Standard library only. No API keys required.
"""

import random
import time
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
from collections import defaultdict


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class SLADimension(Enum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    QUALITY = "quality"
    SAFETY = "safety"
    COST = "cost"


@dataclass
class SLAThreshold:
    dimension: SLADimension
    target: float
    warning_threshold: float
    critical_threshold: float
    unit: str
    description: str


@dataclass
class SLABreach:
    timestamp: str
    dimension: SLADimension
    severity: Severity
    observed_value: float
    threshold_value: float
    message: str
    automated_response: Optional[str] = None


@dataclass
class RequestMetrics:
    timestamp: str
    latency_ms: float
    quality_score: float
    safety_passed: bool
    cost_usd: float
    success: bool


@dataclass
class SLAReport:
    period_start: str
    period_end: str
    total_requests: int
    breaches: List[SLABreach]
    dimension_scores: Dict[str, float]
    overall_compliance: bool
    automated_actions_taken: List[str]


class SLAMonitor:
    """Multi-dimensional SLA monitor for AI systems."""

    def __init__(self):
        self.thresholds = self._define_thresholds()
        self.breaches: List[SLABreach] = []
        self.metrics: List[RequestMetrics] = []
        self.automated_actions: List[str] = []
        self.window_size = 50  # rolling window for calculations
        self.request_count = 0
        self.failure_count = 0

    def _define_thresholds(self) -> Dict[SLADimension, SLAThreshold]:
        return {
            SLADimension.AVAILABILITY: SLAThreshold(
                dimension=SLADimension.AVAILABILITY,
                target=0.995,
                warning_threshold=0.99,
                critical_threshold=0.95,
                unit="ratio",
                description="Successful responses / total requests",
            ),
            SLADimension.LATENCY: SLAThreshold(
                dimension=SLADimension.LATENCY,
                target=500.0,
                warning_threshold=800.0,
                critical_threshold=2000.0,
                unit="ms (p95)",
                description="95th percentile response latency",
            ),
            SLADimension.QUALITY: SLAThreshold(
                dimension=SLADimension.QUALITY,
                target=0.85,
                warning_threshold=0.75,
                critical_threshold=0.60,
                unit="score (0-1)",
                description="Average response quality score",
            ),
            SLADimension.SAFETY: SLAThreshold(
                dimension=SLADimension.SAFETY,
                target=0.999,
                warning_threshold=0.995,
                critical_threshold=0.99,
                unit="ratio",
                description="Responses passing safety filters",
            ),
            SLADimension.COST: SLAThreshold(
                dimension=SLADimension.COST,
                target=0.05,
                warning_threshold=0.08,
                critical_threshold=0.15,
                unit="USD/request",
                description="Average cost per request",
            ),
        }

    def simulate_request(self, scenario: str = "normal") -> RequestMetrics:
        """Simulate a single AI request with varying quality based on scenario."""
        self.request_count += 1

        if scenario == "normal":
            latency = random.gauss(400, 100)
            quality = random.gauss(0.88, 0.05)
            safety_pass = random.random() > 0.001
            cost = random.gauss(0.04, 0.01)
            success = random.random() > 0.003
        elif scenario == "degraded":
            latency = random.gauss(900, 300)
            quality = random.gauss(0.70, 0.10)
            safety_pass = random.random() > 0.008
            cost = random.gauss(0.07, 0.02)
            success = random.random() > 0.03
        elif scenario == "incident":
            latency = random.gauss(2500, 800)
            quality = random.gauss(0.50, 0.15)
            safety_pass = random.random() > 0.02
            cost = random.gauss(0.12, 0.04)
            success = random.random() > 0.15
        elif scenario == "cost_spike":
            latency = random.gauss(450, 100)
            quality = random.gauss(0.90, 0.04)
            safety_pass = random.random() > 0.001
            cost = random.gauss(0.18, 0.05)
            success = random.random() > 0.005
        else:
            latency = random.gauss(400, 100)
            quality = random.gauss(0.88, 0.05)
            safety_pass = True
            cost = random.gauss(0.04, 0.01)
            success = True

        latency = max(50, latency)
        quality = max(0.0, min(1.0, quality))
        cost = max(0.001, cost)

        if not success:
            self.failure_count += 1

        metric = RequestMetrics(
            timestamp=datetime.now().isoformat(),
            latency_ms=round(latency, 2),
            quality_score=round(quality, 3),
            safety_passed=safety_pass,
            cost_usd=round(cost, 4),
            success=success,
        )
        self.metrics.append(metric)
        return metric

    def check_slas(self) -> List[SLABreach]:
        """Check all SLA dimensions against current metrics."""
        if len(self.metrics) < 10:
            return []

        window = self.metrics[-self.window_size:]
        new_breaches = []

        # Availability check
        availability = sum(1 for m in window if m.success) / len(window)
        breach = self._check_threshold(
            SLADimension.AVAILABILITY, availability, lower_is_worse=True
        )
        if breach:
            new_breaches.append(breach)

        # Latency check (p95)
        latencies = sorted([m.latency_ms for m in window])
        p95_idx = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_idx] if latencies else 0
        breach = self._check_threshold(
            SLADimension.LATENCY, p95_latency, lower_is_worse=False
        )
        if breach:
            new_breaches.append(breach)

        # Quality check
        avg_quality = sum(m.quality_score for m in window) / len(window)
        breach = self._check_threshold(
            SLADimension.QUALITY, avg_quality, lower_is_worse=True
        )
        if breach:
            new_breaches.append(breach)

        # Safety check
        safety_rate = sum(1 for m in window if m.safety_passed) / len(window)
        breach = self._check_threshold(
            SLADimension.SAFETY, safety_rate, lower_is_worse=True
        )
        if breach:
            new_breaches.append(breach)

        # Cost check
        avg_cost = sum(m.cost_usd for m in window) / len(window)
        breach = self._check_threshold(
            SLADimension.COST, avg_cost, lower_is_worse=False
        )
        if breach:
            new_breaches.append(breach)

        self.breaches.extend(new_breaches)
        return new_breaches

    def _check_threshold(
        self, dimension: SLADimension, value: float, lower_is_worse: bool
    ) -> Optional[SLABreach]:
        """Check a value against SLA thresholds."""
        threshold = self.thresholds[dimension]

        if lower_is_worse:
            if value < threshold.critical_threshold:
                severity = Severity.CRITICAL
            elif value < threshold.warning_threshold:
                severity = Severity.WARNING
            else:
                return None
            threshold_val = threshold.warning_threshold
        else:
            if value > threshold.critical_threshold:
                severity = Severity.CRITICAL
            elif value > threshold.warning_threshold:
                severity = Severity.WARNING
            else:
                return None
            threshold_val = threshold.warning_threshold

        return SLABreach(
            timestamp=datetime.now().isoformat(),
            dimension=dimension,
            severity=severity,
            observed_value=round(value, 4),
            threshold_value=threshold_val,
            message=f"{dimension.value} SLA breach: observed={value:.4f}, threshold={threshold_val}",
        )

    def trigger_automated_response(self, breach: SLABreach) -> str:
        """Trigger automated response based on breach severity and dimension."""
        responses = {
            (SLADimension.AVAILABILITY, Severity.CRITICAL): "FAILOVER: Switching to backup model endpoint",
            (SLADimension.AVAILABILITY, Severity.WARNING): "ALERT: Notifying on-call engineer, increasing health check frequency",
            (SLADimension.LATENCY, Severity.CRITICAL): "SCALE: Auto-scaling inference fleet, enabling request queuing",
            (SLADimension.LATENCY, Severity.WARNING): "OPTIMIZE: Switching to smaller model for non-critical requests",
            (SLADimension.QUALITY, Severity.CRITICAL): "ROLLBACK: Reverting to previous model version",
            (SLADimension.QUALITY, Severity.WARNING): "MONITOR: Increasing quality sampling rate to 100%",
            (SLADimension.SAFETY, Severity.CRITICAL): "EMERGENCY: Activating kill-switch, routing to rule-based fallback",
            (SLADimension.SAFETY, Severity.WARNING): "TIGHTEN: Lowering safety filter thresholds",
            (SLADimension.COST, Severity.CRITICAL): "THROTTLE: Enabling aggressive caching, rejecting low-priority requests",
            (SLADimension.COST, Severity.WARNING): "OPTIMIZE: Switching to smaller model, enabling prompt compression",
        }

        key = (breach.dimension, breach.severity)
        response = responses.get(key, f"ALERT: Notifying team about {breach.dimension.value} breach")
        breach.automated_response = response
        self.automated_actions.append(f"[{breach.timestamp}] {response}")
        return response

    def generate_report(self) -> SLAReport:
        """Generate a compliance report for the monitoring period."""
        if not self.metrics:
            return SLAReport(
                period_start="N/A",
                period_end="N/A",
                total_requests=0,
                breaches=[],
                dimension_scores={},
                overall_compliance=True,
                automated_actions_taken=[],
            )

        all_metrics = self.metrics
        availability = sum(1 for m in all_metrics if m.success) / len(all_metrics)
        latencies = sorted([m.latency_ms for m in all_metrics])
        p95_latency = latencies[int(len(latencies) * 0.95)]
        avg_quality = sum(m.quality_score for m in all_metrics) / len(all_metrics)
        safety_rate = sum(1 for m in all_metrics if m.safety_passed) / len(all_metrics)
        avg_cost = sum(m.cost_usd for m in all_metrics) / len(all_metrics)

        dimension_scores = {
            "availability": round(availability, 4),
            "latency_p95_ms": round(p95_latency, 2),
            "quality_avg": round(avg_quality, 4),
            "safety_rate": round(safety_rate, 4),
            "cost_avg_usd": round(avg_cost, 4),
        }

        critical_breaches = [b for b in self.breaches if b.severity == Severity.CRITICAL]
        overall_compliance = len(critical_breaches) == 0

        return SLAReport(
            period_start=all_metrics[0].timestamp,
            period_end=all_metrics[-1].timestamp,
            total_requests=len(all_metrics),
            breaches=self.breaches,
            dimension_scores=dimension_scores,
            overall_compliance=overall_compliance,
            automated_actions_taken=self.automated_actions,
        )


def run_simulation():
    """Run the full SLA monitoring simulation."""
    print("=" * 60)
    print("AI SLA MONITOR - Production Traffic Simulation")
    print("=" * 60)

    monitor = SLAMonitor()
    random.seed(42)

    # Simulation phases
    phases = [
        ("Normal Operations", "normal", 80),
        ("Degraded Performance", "degraded", 40),
        ("Major Incident", "incident", 30),
        ("Cost Spike", "cost_spike", 25),
        ("Recovery", "normal", 50),
    ]

    total_breaches = 0

    for phase_name, scenario, num_requests in phases:
        print(f"\n{'─' * 60}")
        print(f"Phase: {phase_name} ({num_requests} requests)")
        print(f"{'─' * 60}")

        phase_breaches = []
        for i in range(num_requests):
            monitor.simulate_request(scenario)

            # Check SLAs every 10 requests
            if (i + 1) % 10 == 0:
                breaches = monitor.check_slas()
                for breach in breaches:
                    response = monitor.trigger_automated_response(breach)
                    phase_breaches.append(breach)
                    print(f"  [{breach.severity.value.upper()}] {breach.dimension.value}: "
                          f"{breach.observed_value:.4f} (threshold: {breach.threshold_value})")
                    print(f"    → {response}")

        if not phase_breaches:
            print("  ✓ All SLAs within acceptable range")
        total_breaches += len(phase_breaches)

    # Generate and print compliance report
    report = monitor.generate_report()

    print(f"\n{'=' * 60}")
    print("COMPLIANCE REPORT")
    print(f"{'=' * 60}")
    print(f"Period: {report.period_start[:19]} to {report.period_end[:19]}")
    print(f"Total Requests: {report.total_requests}")
    print(f"Overall Compliance: {'PASS ✓' if report.overall_compliance else 'FAIL ✗'}")

    print(f"\nDimension Scores:")
    for dim, score in report.dimension_scores.items():
        threshold = None
        for d, t in monitor.thresholds.items():
            if d.value == dim.replace("_p95_ms", "").replace("_avg", "").replace("_avg_usd", "").replace("_rate", ""):
                threshold = t
                break
        status = "✓" if threshold is None else "✓"
        print(f"  {dim:<20}: {score}")

    print(f"\nTotal Breaches: {len(report.breaches)}")
    severity_counts = defaultdict(int)
    for b in report.breaches:
        severity_counts[b.severity.value] += 1
    for sev, count in sorted(severity_counts.items()):
        print(f"  {sev:<12}: {count}")

    print(f"\nAutomated Actions Taken: {len(report.automated_actions_taken)}")
    for action in report.automated_actions_taken[:10]:
        print(f"  {action}")
    if len(report.automated_actions_taken) > 10:
        print(f"  ... and {len(report.automated_actions_taken) - 10} more")

    print(f"\n{'=' * 60}")
    print("Simulation complete.")


if __name__ == "__main__":
    run_simulation()
