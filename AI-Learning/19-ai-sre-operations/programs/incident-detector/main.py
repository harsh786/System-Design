"""
AI Incident Detector
Simulates production metric streams and detects AI-specific incidents.
"""

import random
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class Severity(Enum):
    P0 = "P0-CRITICAL"
    P1 = "P1-HIGH"
    P2 = "P2-MEDIUM"
    P3 = "P3-LOW"


class IncidentType(Enum):
    QUALITY_DEGRADATION = "Quality Degradation"
    LATENCY_SPIKE = "Latency Spike"
    COST_ANOMALY = "Cost Anomaly"
    ERROR_BURST = "Error Burst"
    HALLUCINATION_SPIKE = "Hallucination Spike"
    PROVIDER_DEGRADATION = "Provider Degradation"


@dataclass
class Metric:
    timestamp: datetime
    name: str
    value: float
    labels: dict = field(default_factory=dict)


@dataclass
class Alert:
    timestamp: datetime
    incident_type: IncidentType
    severity: Severity
    metric_name: str
    current_value: float
    threshold: float
    context: str
    duration_minutes: int = 0


@dataclass
class Incident:
    id: str
    started: datetime
    detected: datetime
    incident_type: IncidentType
    severity: Severity
    alerts: list = field(default_factory=list)
    resolved: datetime = None
    resolution: str = ""


class MetricGenerator:
    """Generates realistic AI production metrics with injected anomalies."""

    def __init__(self, start_time: datetime):
        self.current_time = start_time
        self.anomaly_schedule = self._create_anomaly_schedule(start_time)

    def _create_anomaly_schedule(self, start: datetime) -> list:
        """Schedule anomalies throughout the simulation."""
        return [
            {
                "start": start + timedelta(minutes=15),
                "end": start + timedelta(minutes=35),
                "type": "quality_degradation",
                "description": "Model provider silently updated weights",
            },
            {
                "start": start + timedelta(minutes=45),
                "end": start + timedelta(minutes=55),
                "type": "latency_spike",
                "description": "Provider experiencing high load",
            },
            {
                "start": start + timedelta(minutes=70),
                "end": start + timedelta(minutes=90),
                "type": "cost_anomaly",
                "description": "Agent stuck in loop burning tokens",
            },
            {
                "start": start + timedelta(minutes=100),
                "end": start + timedelta(minutes=110),
                "type": "error_burst",
                "description": "Provider rate limit hit",
            },
            {
                "start": start + timedelta(minutes=120),
                "end": start + timedelta(minutes=145),
                "type": "hallucination_spike",
                "description": "Vector DB returning stale results",
            },
        ]

    def _get_active_anomaly(self, timestamp: datetime) -> dict | None:
        for anomaly in self.anomaly_schedule:
            if anomaly["start"] <= timestamp <= anomaly["end"]:
                return anomaly
        return None

    def generate_metrics(self, timestamp: datetime) -> list[Metric]:
        """Generate a set of metrics for a given timestamp."""
        anomaly = self._get_active_anomaly(timestamp)
        metrics = []

        # Latency (normal: ~200ms, spike: ~2000ms)
        base_latency = random.gauss(200, 30)
        if anomaly and anomaly["type"] == "latency_spike":
            base_latency = random.gauss(2500, 500)
        metrics.append(Metric(timestamp, "response_latency_p95", max(50, base_latency)))

        # Quality score (normal: ~0.92, degraded: ~0.75)
        base_quality = random.gauss(0.92, 0.02)
        if anomaly and anomaly["type"] == "quality_degradation":
            base_quality = random.gauss(0.76, 0.04)
        metrics.append(Metric(timestamp, "quality_faithfulness", min(1.0, max(0, base_quality))))

        # Cost per request (normal: ~$0.03, anomaly: ~$0.15)
        base_cost = random.gauss(0.03, 0.005)
        if anomaly and anomaly["type"] == "cost_anomaly":
            base_cost = random.gauss(0.18, 0.05)
        metrics.append(Metric(timestamp, "cost_per_request", max(0.001, base_cost)))

        # Error rate (normal: ~1%, burst: ~25%)
        base_error = random.gauss(0.01, 0.005)
        if anomaly and anomaly["type"] == "error_burst":
            base_error = random.gauss(0.25, 0.08)
        metrics.append(Metric(timestamp, "error_rate", min(1.0, max(0, base_error))))

        # Hallucination rate (normal: ~3%, spike: ~15%)
        base_hallucination = random.gauss(0.03, 0.01)
        if anomaly and anomaly["type"] == "hallucination_spike":
            base_hallucination = random.gauss(0.15, 0.04)
        metrics.append(Metric(timestamp, "hallucination_rate", min(1.0, max(0, base_hallucination))))

        # Cache hit rate (normal: ~45%)
        base_cache = random.gauss(0.45, 0.05)
        if anomaly and anomaly["type"] == "cost_anomaly":
            base_cache = random.gauss(0.15, 0.05)  # Cache may be broken
        metrics.append(Metric(timestamp, "cache_hit_rate", min(1.0, max(0, base_cache))))

        return metrics


class AnomalyDetector:
    """Detects anomalies using threshold-based and trend-based methods."""

    def __init__(self):
        self.thresholds = {
            "response_latency_p95": {"warn": 500, "critical": 1500},
            "quality_faithfulness": {"warn": 0.88, "critical": 0.82},  # below = bad
            "cost_per_request": {"warn": 0.08, "critical": 0.12},
            "error_rate": {"warn": 0.05, "critical": 0.15},
            "hallucination_rate": {"warn": 0.08, "critical": 0.12},
            "cache_hit_rate": {"warn": 0.30, "critical": 0.20},  # below = bad
        }
        self.history: dict[str, list[float]] = {}
        self.sustained_violations: dict[str, int] = {}
        self.alert_cooldown: dict[str, datetime] = {}
        self.min_sustained_count = 3  # Need 3 consecutive violations

    def check_metrics(self, metrics: list[Metric]) -> list[Alert]:
        """Check metrics against thresholds and trends."""
        alerts = []

        for metric in metrics:
            # Track history
            if metric.name not in self.history:
                self.history[metric.name] = []
            self.history[metric.name].append(metric.value)
            if len(self.history[metric.name]) > 60:
                self.history[metric.name] = self.history[metric.name][-60:]

            # Threshold check
            alert = self._check_threshold(metric)
            if alert:
                alerts.append(alert)

        return alerts

    def _check_threshold(self, metric: Metric) -> Alert | None:
        """Check if metric violates threshold."""
        if metric.name not in self.thresholds:
            return None

        thresholds = self.thresholds[metric.name]
        violated = False
        severity = None

        # For metrics where LOWER is bad (quality, cache hit rate)
        if metric.name in ("quality_faithfulness", "cache_hit_rate"):
            if metric.value < thresholds["critical"]:
                violated = True
                severity = Severity.P1
            elif metric.value < thresholds["warn"]:
                violated = True
                severity = Severity.P2
        else:
            # For metrics where HIGHER is bad
            if metric.value > thresholds["critical"]:
                violated = True
                severity = Severity.P1
            elif metric.value > thresholds["warn"]:
                violated = True
                severity = Severity.P2

        if violated:
            # Track sustained violations
            self.sustained_violations[metric.name] = self.sustained_violations.get(metric.name, 0) + 1

            if self.sustained_violations[metric.name] >= self.min_sustained_count:
                # Check cooldown
                cooldown = self.alert_cooldown.get(metric.name)
                if cooldown and metric.timestamp < cooldown:
                    return None

                self.alert_cooldown[metric.name] = metric.timestamp + timedelta(minutes=5)

                incident_type = self._map_metric_to_incident(metric.name)
                context = self._build_context(metric)

                return Alert(
                    timestamp=metric.timestamp,
                    incident_type=incident_type,
                    severity=severity,
                    metric_name=metric.name,
                    current_value=metric.value,
                    threshold=thresholds["critical" if severity == Severity.P1 else "warn"],
                    context=context,
                    duration_minutes=self.sustained_violations[metric.name],
                )
        else:
            self.sustained_violations[metric.name] = 0

        return None

    def _map_metric_to_incident(self, metric_name: str) -> IncidentType:
        mapping = {
            "response_latency_p95": IncidentType.LATENCY_SPIKE,
            "quality_faithfulness": IncidentType.QUALITY_DEGRADATION,
            "cost_per_request": IncidentType.COST_ANOMALY,
            "error_rate": IncidentType.ERROR_BURST,
            "hallucination_rate": IncidentType.HALLUCINATION_SPIKE,
            "cache_hit_rate": IncidentType.COST_ANOMALY,
        }
        return mapping.get(metric_name, IncidentType.QUALITY_DEGRADATION)

    def _build_context(self, metric: Metric) -> str:
        history = self.history.get(metric.name, [])
        if len(history) < 5:
            return f"Metric {metric.name} = {metric.value:.4f}"

        recent_avg = sum(history[-5:]) / 5
        baseline_avg = sum(history[:10]) / min(10, len(history[:10])) if len(history) > 10 else recent_avg
        trend = "rising" if recent_avg > baseline_avg else "falling"

        return (
            f"Current: {metric.value:.4f} | "
            f"Recent avg: {recent_avg:.4f} | "
            f"Baseline: {baseline_avg:.4f} | "
            f"Trend: {trend}"
        )


class IncidentTimeline:
    """Tracks and displays the incident timeline."""

    def __init__(self):
        self.incidents: list[Incident] = []
        self.alerts: list[Alert] = []
        self.incident_counter = 0

    def add_alert(self, alert: Alert):
        self.alerts.append(alert)

    def process_alerts(self):
        """Group alerts into incidents."""
        # Group by incident type within time windows
        grouped = {}
        for alert in self.alerts:
            key = alert.incident_type.value
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(alert)

        for incident_type, alerts in grouped.items():
            if alerts:
                self.incident_counter += 1
                incident = Incident(
                    id=f"INC-{self.incident_counter:04d}",
                    started=alerts[0].timestamp - timedelta(minutes=alerts[0].duration_minutes),
                    detected=alerts[0].timestamp,
                    incident_type=alerts[0].incident_type,
                    severity=min(alerts, key=lambda a: list(Severity).index(a.severity)).severity,
                    alerts=alerts,
                )
                self.incidents.append(incident)

    def display(self):
        """Display the full incident timeline."""
        print("=" * 70)
        print("  AI INCIDENT DETECTION REPORT")
        print("=" * 70)
        print()

        self.process_alerts()

        if not self.incidents:
            print("  No incidents detected during monitoring period.")
            return

        print(f"  Monitoring Period: {self.alerts[0].timestamp.strftime('%H:%M')} - "
              f"{self.alerts[-1].timestamp.strftime('%H:%M')}")
        print(f"  Total Alerts: {len(self.alerts)}")
        print(f"  Incidents Identified: {len(self.incidents)}")
        print()

        # Timeline
        print("  INCIDENT TIMELINE")
        print(f"  {'─' * 60}")

        for incident in sorted(self.incidents, key=lambda i: i.detected):
            print()
            print(f"  [{incident.detected.strftime('%H:%M')}] {incident.severity.value} - "
                  f"{incident.incident_type.value}")
            print(f"  ID: {incident.id}")
            print(f"  Detection delay: {(incident.detected - incident.started).seconds // 60} min")
            print(f"  Alerts in this incident: {len(incident.alerts)}")

            # Show first alert detail
            first_alert = incident.alerts[0]
            print(f"  Trigger: {first_alert.metric_name}")
            print(f"  Context: {first_alert.context}")
            print(f"  Threshold: {first_alert.threshold}")
            print()
            print(f"  {'·' * 50}")

        # Summary
        print()
        print(f"  {'─' * 60}")
        print("  SUMMARY BY SEVERITY")
        print()
        for sev in Severity:
            count = sum(1 for i in self.incidents if i.severity == sev)
            if count > 0:
                print(f"    {sev.value}: {count} incident(s)")

        # Detection performance
        print()
        print(f"  {'─' * 60}")
        print("  DETECTION PERFORMANCE")
        print()
        delays = [(i.detected - i.started).seconds // 60 for i in self.incidents]
        if delays:
            print(f"    Avg detection delay: {sum(delays) / len(delays):.1f} minutes")
            print(f"    Max detection delay: {max(delays)} minutes")
            print(f"    Min detection delay: {min(delays)} minutes")

        print()
        print("=" * 70)


def main():
    """Run the incident detection simulation."""
    print()
    print("  Starting AI Incident Detection Simulation...")
    print("  Generating 2.5 hours of production metrics with injected anomalies...")
    print()

    start_time = datetime(2024, 12, 15, 9, 0, 0)
    generator = MetricGenerator(start_time)
    detector = AnomalyDetector()
    timeline = IncidentTimeline()

    # Simulate 150 minutes of metrics (1 metric set per minute)
    current_time = start_time
    total_minutes = 150

    print(f"  {'Time':<8} {'Latency':>10} {'Quality':>10} {'Cost':>10} "
          f"{'Errors':>10} {'Halluc':>10} {'Cache':>10} {'Alert'}")
    print(f"  {'─' * 78}")

    for minute in range(total_minutes):
        current_time = start_time + timedelta(minutes=minute)
        metrics = generator.generate_metrics(current_time)

        # Detect anomalies
        alerts = detector.check_metrics(metrics)

        # Print metric line (every 5 minutes or if alert)
        if minute % 5 == 0 or alerts:
            values = {m.name: m.value for m in metrics}
            alert_str = ""
            if alerts:
                alert_str = f" ⚠ {alerts[0].incident_type.value}"

            print(
                f"  {current_time.strftime('%H:%M'):<8} "
                f"{values.get('response_latency_p95', 0):>8.0f}ms "
                f"{values.get('quality_faithfulness', 0):>9.3f} "
                f"${values.get('cost_per_request', 0):>8.4f} "
                f"{values.get('error_rate', 0):>9.1%} "
                f"{values.get('hallucination_rate', 0):>9.1%} "
                f"{values.get('cache_hit_rate', 0):>9.1%}"
                f"{alert_str}"
            )

        for alert in alerts:
            timeline.add_alert(alert)

    print()
    timeline.display()


if __name__ == "__main__":
    main()
