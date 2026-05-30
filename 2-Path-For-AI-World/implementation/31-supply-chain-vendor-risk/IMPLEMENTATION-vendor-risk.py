"""
Vendor Risk Management System
===============================
Comprehensive vendor assessment, monitoring, and risk management for AI providers.
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class VendorCategory(Enum):
    MODEL_PROVIDER = "model_provider"
    EMBEDDING_PROVIDER = "embedding_provider"
    VECTOR_DB = "vector_database"
    MCP_SERVER = "mcp_server"
    SAAS_API = "saas_api"
    CLOUD_INFRA = "cloud_infrastructure"
    DATA_PROVIDER = "data_provider"
    TOOLING = "tooling"


class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class OutageImpact(Enum):
    TOTAL = "total"           # System completely down
    SEVERE = "severe"         # Major features unavailable
    DEGRADED = "degraded"     # Reduced quality/speed
    MINOR = "minor"           # Barely noticeable
    NONE = "none"             # No impact (redundancy handled it)


class ContractStatus(Enum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    UNDER_NEGOTIATION = "under_negotiation"
    TERMINATED = "terminated"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SLAMetrics:
    """Service Level Agreement metrics for a vendor."""
    uptime_target: float  # e.g., 99.9
    latency_p50_target_ms: float
    latency_p99_target_ms: float
    throughput_target_rps: float
    error_rate_target: float  # e.g., 0.001 = 0.1%
    # Actuals
    uptime_actual: float = 99.9
    latency_p50_actual_ms: float = 0.0
    latency_p99_actual_ms: float = 0.0
    throughput_actual_rps: float = 0.0
    error_rate_actual: float = 0.0
    measurement_period_days: int = 30

    @property
    def is_meeting_sla(self) -> bool:
        return (
            self.uptime_actual >= self.uptime_target
            and self.latency_p99_actual_ms <= self.latency_p99_target_ms
            and self.error_rate_actual <= self.error_rate_target
        )

    @property
    def sla_score(self) -> float:
        """Score from 0-100 based on SLA adherence."""
        scores = []
        scores.append(min(100, (self.uptime_actual / self.uptime_target) * 100))
        if self.latency_p99_actual_ms > 0:
            scores.append(min(100, (self.latency_p99_target_ms / self.latency_p99_actual_ms) * 100))
        if self.error_rate_actual > 0:
            scores.append(min(100, (self.error_rate_target / self.error_rate_actual) * 100))
        else:
            scores.append(100)
        return statistics.mean(scores) if scores else 0


@dataclass
class OutageRecord:
    id: str
    vendor_id: str
    started_at: datetime
    resolved_at: Optional[datetime]
    duration_minutes: Optional[float]
    impact: OutageImpact
    affected_services: list[str]
    root_cause: str = ""
    vendor_communication_quality: int = 5  # 1-10
    post_mortem_received: bool = False
    lessons_learned: str = ""


@dataclass
class BehaviorDriftEvent:
    """Detected change in vendor model/API behavior without version change."""
    id: str
    vendor_id: str
    detected_at: datetime
    metric_name: str  # e.g., "output_length", "refusal_rate", "latency"
    baseline_value: float
    current_value: float
    deviation_pct: float
    severity: RiskLevel
    description: str
    confirmed: bool = False
    vendor_acknowledged: bool = False


@dataclass
class CostRecord:
    vendor_id: str
    period: str  # "2024-01", "2024-02", etc.
    amount_usd: float
    units_consumed: float
    unit_type: str  # "tokens", "queries", "requests", "storage_gb"
    cost_per_unit: float


@dataclass
class VendorContract:
    vendor_id: str
    contract_id: str
    start_date: datetime
    end_date: datetime
    auto_renews: bool
    notice_period_days: int
    monthly_commitment_usd: float
    data_processing_agreement: bool
    data_residency_clause: bool
    exit_clause: bool
    sla_credits: bool
    status: ContractStatus = ContractStatus.ACTIVE


@dataclass
class ExitPlan:
    vendor_id: str
    alternative_vendors: list[str]
    migration_time_estimate_days: int
    data_export_format: str
    data_export_tested: bool
    estimated_migration_cost_usd: float
    capability_gaps_during_migration: list[str]
    last_tested: Optional[datetime] = None
    runbook_url: Optional[str] = None


@dataclass
class AssessmentQuestion:
    id: str
    category: str
    question: str
    weight: float  # How much this affects overall score
    answer: Optional[str] = None
    score: Optional[int] = None  # 1-5


@dataclass
class Vendor:
    id: str
    name: str
    category: VendorCategory
    description: str
    primary_contact: str
    website: str
    sla_metrics: SLAMetrics
    contract: Optional[VendorContract] = None
    exit_plan: Optional[ExitPlan] = None
    outages: list[OutageRecord] = field(default_factory=list)
    drift_events: list[BehaviorDriftEvent] = field(default_factory=list)
    cost_history: list[CostRecord] = field(default_factory=list)
    assessment_scores: dict[str, float] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_assessed: Optional[datetime] = None


# =============================================================================
# Vendor Assessment Framework
# =============================================================================

class VendorAssessment:
    """Questionnaire-based vendor risk assessment."""

    def __init__(self):
        self.questions = self._build_questionnaire()

    def _build_questionnaire(self) -> list[AssessmentQuestion]:
        return [
            # Security
            AssessmentQuestion("sec-1", "security", "Does the vendor have SOC2 Type II certification?", 3.0),
            AssessmentQuestion("sec-2", "security", "Does the vendor encrypt data at rest and in transit?", 3.0),
            AssessmentQuestion("sec-3", "security", "Does the vendor have a vulnerability disclosure program?", 2.0),
            AssessmentQuestion("sec-4", "security", "Does the vendor provide audit logs?", 2.0),
            AssessmentQuestion("sec-5", "security", "Does the vendor support SSO/SAML?", 1.5),
            AssessmentQuestion("sec-6", "security", "Does the vendor train on customer data? (lower is better if yes)", 3.0),
            # Reliability
            AssessmentQuestion("rel-1", "reliability", "What is the vendor's historical uptime? (99.9%+ = 5)", 3.0),
            AssessmentQuestion("rel-2", "reliability", "Does the vendor provide a public status page?", 1.5),
            AssessmentQuestion("rel-3", "reliability", "Does the vendor have multi-region deployment?", 2.5),
            AssessmentQuestion("rel-4", "reliability", "What is the vendor's RTO/RPO commitment?", 2.0),
            AssessmentQuestion("rel-5", "reliability", "Does the vendor have a disaster recovery plan?", 2.5),
            # Data Privacy
            AssessmentQuestion("prv-1", "privacy", "Does the vendor offer data residency options?", 2.5),
            AssessmentQuestion("prv-2", "privacy", "Does the vendor have a DPA (Data Processing Agreement)?", 3.0),
            AssessmentQuestion("prv-3", "privacy", "Can data be deleted on request (right to erasure)?", 2.5),
            AssessmentQuestion("prv-4", "privacy", "Does the vendor comply with GDPR/CCPA?", 3.0),
            # Business Viability
            AssessmentQuestion("biz-1", "business", "How long has the vendor been operating? (5+ years = 5)", 2.0),
            AssessmentQuestion("biz-2", "business", "Is the vendor profitable or well-funded?", 2.5),
            AssessmentQuestion("biz-3", "business", "Does the vendor have enterprise customers?", 1.5),
            AssessmentQuestion("biz-4", "business", "Is there vendor lock-in risk? (lower lock-in = higher score)", 3.0),
            # Operational
            AssessmentQuestion("ops-1", "operational", "Quality of documentation (comprehensive = 5)", 1.5),
            AssessmentQuestion("ops-2", "operational", "Quality of support (responsive = 5)", 2.0),
            AssessmentQuestion("ops-3", "operational", "Frequency of breaking changes (rare = 5)", 2.5),
            AssessmentQuestion("ops-4", "operational", "Deprecation notice period (6+ months = 5)", 2.0),
            AssessmentQuestion("ops-5", "operational", "API versioning quality (excellent = 5)", 2.0),
        ]

    def score_assessment(self, answers: dict[str, int]) -> dict:
        """Score a completed assessment. answers = {question_id: score(1-5)}."""
        category_scores = {}
        total_weighted = 0.0
        total_weight = 0.0

        for q in self.questions:
            if q.id in answers:
                score = answers[q.id]
                q.score = score
                weighted = score * q.weight
                total_weighted += weighted
                total_weight += q.weight * 5  # Max possible

                if q.category not in category_scores:
                    category_scores[q.category] = {"weighted_sum": 0, "max_possible": 0}
                category_scores[q.category]["weighted_sum"] += weighted
                category_scores[q.category]["max_possible"] += q.weight * 5

        overall_score = (total_weighted / total_weight * 100) if total_weight > 0 else 0

        category_pcts = {
            cat: (vals["weighted_sum"] / vals["max_possible"] * 100) if vals["max_possible"] > 0 else 0
            for cat, vals in category_scores.items()
        }

        risk_level = RiskLevel.MINIMAL
        if overall_score < 40:
            risk_level = RiskLevel.CRITICAL
        elif overall_score < 55:
            risk_level = RiskLevel.HIGH
        elif overall_score < 70:
            risk_level = RiskLevel.MEDIUM
        elif overall_score < 85:
            risk_level = RiskLevel.LOW

        return {
            "overall_score": overall_score,
            "risk_level": risk_level.value,
            "category_scores": category_pcts,
            "weakest_category": min(category_pcts, key=category_pcts.get) if category_pcts else None,
            "recommendations": self._generate_recommendations(category_pcts),
        }

    def _generate_recommendations(self, category_scores: dict[str, float]) -> list[str]:
        recs = []
        if category_scores.get("security", 100) < 60:
            recs.append("URGENT: Security posture is weak. Require SOC2 or equivalent before proceeding.")
        if category_scores.get("privacy", 100) < 60:
            recs.append("URGENT: Data privacy controls insufficient. Ensure DPA is in place.")
        if category_scores.get("reliability", 100) < 60:
            recs.append("HIGH: Reliability concerns. Implement fallback provider immediately.")
        if category_scores.get("business", 100) < 60:
            recs.append("MEDIUM: Business viability concerns. Monitor closely, prepare exit plan.")
        if category_scores.get("operational", 100) < 60:
            recs.append("MEDIUM: Operational maturity is low. Budget for additional integration work.")
        return recs


# =============================================================================
# Behavior Drift Detection
# =============================================================================

class BehaviorDriftDetector:
    """Detects changes in vendor model/API behavior over time."""

    def __init__(self, baseline_window_days: int = 7, alert_threshold_pct: float = 15.0):
        self.baseline_window_days = baseline_window_days
        self.alert_threshold_pct = alert_threshold_pct
        self._metrics: dict[str, list[tuple[datetime, float]]] = {}  # vendor:metric -> [(ts, value)]

    def record_metric(self, vendor_id: str, metric_name: str, value: float) -> None:
        key = f"{vendor_id}:{metric_name}"
        if key not in self._metrics:
            self._metrics[key] = []
        self._metrics[key].append((datetime.utcnow(), value))
        # Keep last 90 days
        cutoff = datetime.utcnow() - timedelta(days=90)
        self._metrics[key] = [(ts, v) for ts, v in self._metrics[key] if ts > cutoff]

    def check_for_drift(self, vendor_id: str, metric_name: str) -> Optional[BehaviorDriftEvent]:
        """Compare recent values against baseline to detect drift."""
        key = f"{vendor_id}:{metric_name}"
        data = self._metrics.get(key, [])
        if len(data) < 10:
            return None

        now = datetime.utcnow()
        baseline_start = now - timedelta(days=self.baseline_window_days + 7)
        baseline_end = now - timedelta(days=7)
        recent_start = now - timedelta(days=1)

        baseline_values = [v for ts, v in data if baseline_start <= ts <= baseline_end]
        recent_values = [v for ts, v in data if ts >= recent_start]

        if not baseline_values or not recent_values:
            return None

        baseline_mean = statistics.mean(baseline_values)
        recent_mean = statistics.mean(recent_values)

        if baseline_mean == 0:
            return None

        deviation_pct = abs(recent_mean - baseline_mean) / baseline_mean * 100

        if deviation_pct > self.alert_threshold_pct:
            severity = RiskLevel.LOW
            if deviation_pct > 50:
                severity = RiskLevel.CRITICAL
            elif deviation_pct > 30:
                severity = RiskLevel.HIGH
            elif deviation_pct > 20:
                severity = RiskLevel.MEDIUM

            return BehaviorDriftEvent(
                id=f"DRIFT-{uuid4().hex[:8]}",
                vendor_id=vendor_id,
                detected_at=now,
                metric_name=metric_name,
                baseline_value=baseline_mean,
                current_value=recent_mean,
                deviation_pct=deviation_pct,
                severity=severity,
                description=f"{metric_name} deviated {deviation_pct:.1f}% from baseline "
                           f"(baseline={baseline_mean:.2f}, current={recent_mean:.2f})",
            )
        return None

    def check_all_metrics(self, vendor_id: str) -> list[BehaviorDriftEvent]:
        """Check all tracked metrics for a vendor."""
        events = []
        prefix = f"{vendor_id}:"
        metrics = [key.split(":", 1)[1] for key in self._metrics if key.startswith(prefix)]
        for metric in metrics:
            event = self.check_for_drift(vendor_id, metric)
            if event:
                events.append(event)
        return events


# =============================================================================
# Vendor Risk Manager
# =============================================================================

class VendorRiskManager:
    """Central vendor risk management system."""

    def __init__(self):
        self._vendors: dict[str, Vendor] = {}
        self._assessment = VendorAssessment()
        self._drift_detector = BehaviorDriftDetector()

    # -------------------------------------------------------------------------
    # Vendor Management
    # -------------------------------------------------------------------------

    def register_vendor(
        self,
        name: str,
        category: VendorCategory,
        description: str,
        primary_contact: str,
        website: str,
        sla_metrics: SLAMetrics,
    ) -> Vendor:
        vendor_id = f"vendor-{uuid4().hex[:8]}"
        vendor = Vendor(
            id=vendor_id,
            name=name,
            category=category,
            description=description,
            primary_contact=primary_contact,
            website=website,
            sla_metrics=sla_metrics,
        )
        self._vendors[vendor_id] = vendor
        logger.info(f"Registered vendor: {name} ({category.value})")
        return vendor

    def get_vendor(self, vendor_id: str) -> Optional[Vendor]:
        return self._vendors.get(vendor_id)

    # -------------------------------------------------------------------------
    # Assessment
    # -------------------------------------------------------------------------

    def assess_vendor(self, vendor_id: str, answers: dict[str, int]) -> dict:
        """Run vendor assessment questionnaire."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        result = self._assessment.score_assessment(answers)
        vendor.assessment_scores = result["category_scores"]
        vendor.last_assessed = datetime.utcnow()
        return result

    def get_assessment_questions(self) -> list[dict]:
        return [
            {"id": q.id, "category": q.category, "question": q.question, "weight": q.weight}
            for q in self._assessment.questions
        ]

    # -------------------------------------------------------------------------
    # SLA Monitoring
    # -------------------------------------------------------------------------

    def update_sla_metrics(self, vendor_id: str, metrics: dict) -> SLAMetrics:
        """Update actual SLA metrics for a vendor."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        sla = vendor.sla_metrics
        for key, value in metrics.items():
            if hasattr(sla, key):
                setattr(sla, key, value)

        if not sla.is_meeting_sla:
            logger.warning(f"Vendor {vendor.name} is NOT meeting SLA! Score: {sla.sla_score:.1f}")

        return sla

    def get_sla_dashboard(self) -> list[dict]:
        """Get SLA status for all vendors."""
        dashboard = []
        for vendor in self._vendors.values():
            dashboard.append({
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "category": vendor.category.value,
                "sla_score": vendor.sla_metrics.sla_score,
                "meeting_sla": vendor.sla_metrics.is_meeting_sla,
                "uptime": vendor.sla_metrics.uptime_actual,
                "p99_latency_ms": vendor.sla_metrics.latency_p99_actual_ms,
                "error_rate": vendor.sla_metrics.error_rate_actual,
            })
        return sorted(dashboard, key=lambda x: x["sla_score"])

    # -------------------------------------------------------------------------
    # Outage Tracking
    # -------------------------------------------------------------------------

    def record_outage(
        self,
        vendor_id: str,
        impact: OutageImpact,
        affected_services: list[str],
        started_at: Optional[datetime] = None,
        root_cause: str = "",
    ) -> OutageRecord:
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        outage = OutageRecord(
            id=f"OUT-{uuid4().hex[:8]}",
            vendor_id=vendor_id,
            started_at=started_at or datetime.utcnow(),
            resolved_at=None,
            duration_minutes=None,
            impact=impact,
            affected_services=affected_services,
            root_cause=root_cause,
        )
        vendor.outages.append(outage)
        logger.warning(f"Outage recorded for {vendor.name}: impact={impact.value}")
        return outage

    def resolve_outage(self, vendor_id: str, outage_id: str, root_cause: str = "") -> OutageRecord:
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        for outage in vendor.outages:
            if outage.id == outage_id:
                outage.resolved_at = datetime.utcnow()
                outage.duration_minutes = (outage.resolved_at - outage.started_at).total_seconds() / 60
                if root_cause:
                    outage.root_cause = root_cause
                return outage
        raise ValueError(f"Outage {outage_id} not found")

    def get_outage_analysis(self, vendor_id: str) -> dict:
        """Analyze outage history for a vendor."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        outages = vendor.outages
        if not outages:
            return {"vendor": vendor.name, "total_outages": 0, "message": "No outages recorded"}

        resolved = [o for o in outages if o.resolved_at]
        durations = [o.duration_minutes for o in resolved if o.duration_minutes]

        return {
            "vendor": vendor.name,
            "total_outages": len(outages),
            "active_outages": len([o for o in outages if not o.resolved_at]),
            "avg_duration_minutes": statistics.mean(durations) if durations else 0,
            "max_duration_minutes": max(durations) if durations else 0,
            "total_downtime_minutes": sum(durations) if durations else 0,
            "impact_distribution": {
                impact.value: len([o for o in outages if o.impact == impact])
                for impact in OutageImpact
            },
            "mttr_minutes": statistics.mean(durations) if durations else None,
        }

    # -------------------------------------------------------------------------
    # Behavior Drift
    # -------------------------------------------------------------------------

    def record_behavior_metric(self, vendor_id: str, metric_name: str, value: float) -> None:
        self._drift_detector.record_metric(vendor_id, metric_name, value)

    def check_behavior_drift(self, vendor_id: str) -> list[BehaviorDriftEvent]:
        events = self._drift_detector.check_all_metrics(vendor_id)
        vendor = self._vendors.get(vendor_id)
        if vendor:
            vendor.drift_events.extend(events)
        return events

    # -------------------------------------------------------------------------
    # Cost Monitoring
    # -------------------------------------------------------------------------

    def record_cost(self, vendor_id: str, period: str, amount_usd: float,
                    units_consumed: float, unit_type: str) -> CostRecord:
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        record = CostRecord(
            vendor_id=vendor_id,
            period=period,
            amount_usd=amount_usd,
            units_consumed=units_consumed,
            unit_type=unit_type,
            cost_per_unit=amount_usd / units_consumed if units_consumed > 0 else 0,
        )
        vendor.cost_history.append(record)
        return record

    def get_cost_trend(self, vendor_id: str) -> dict:
        vendor = self._vendors.get(vendor_id)
        if not vendor or not vendor.cost_history:
            return {"vendor_id": vendor_id, "message": "No cost data"}

        history = sorted(vendor.cost_history, key=lambda c: c.period)
        amounts = [c.amount_usd for c in history]
        trend = "stable"
        if len(amounts) >= 3:
            recent_avg = statistics.mean(amounts[-3:])
            older_avg = statistics.mean(amounts[:-3]) if len(amounts) > 3 else amounts[0]
            if recent_avg > older_avg * 1.2:
                trend = "increasing"
            elif recent_avg < older_avg * 0.8:
                trend = "decreasing"

        return {
            "vendor": vendor.name,
            "total_spend_usd": sum(amounts),
            "avg_monthly_usd": statistics.mean(amounts),
            "max_monthly_usd": max(amounts),
            "trend": trend,
            "periods": len(history),
            "latest_cost_per_unit": history[-1].cost_per_unit if history else 0,
        }

    # -------------------------------------------------------------------------
    # Exit Planning
    # -------------------------------------------------------------------------

    def set_exit_plan(self, vendor_id: str, exit_plan: ExitPlan) -> None:
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")
        vendor.exit_plan = exit_plan

    def evaluate_exit_readiness(self, vendor_id: str) -> dict:
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")

        if not vendor.exit_plan:
            return {"vendor": vendor.name, "ready": False, "reason": "No exit plan defined"}

        plan = vendor.exit_plan
        issues = []
        if not plan.data_export_tested:
            issues.append("Data export has not been tested")
        if not plan.alternative_vendors:
            issues.append("No alternative vendors identified")
        if plan.last_tested and (datetime.utcnow() - plan.last_tested).days > 180:
            issues.append("Exit plan not tested in over 6 months")
        if not plan.runbook_url:
            issues.append("No migration runbook documented")

        return {
            "vendor": vendor.name,
            "ready": len(issues) == 0,
            "issues": issues,
            "migration_time_days": plan.migration_time_estimate_days,
            "migration_cost_usd": plan.estimated_migration_cost_usd,
            "capability_gaps": plan.capability_gaps_during_migration,
            "alternatives": plan.alternative_vendors,
        }

    # -------------------------------------------------------------------------
    # Health Dashboard
    # -------------------------------------------------------------------------

    def get_vendor_health_dashboard(self) -> dict:
        """Comprehensive health view across all vendors."""
        vendors = list(self._vendors.values())
        dashboard = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_vendors": len(vendors),
            "vendors_meeting_sla": sum(1 for v in vendors if v.sla_metrics.is_meeting_sla),
            "active_outages": sum(1 for v in vendors for o in v.outages if not o.resolved_at),
            "vendors_without_exit_plan": sum(1 for v in vendors if not v.exit_plan),
            "total_monthly_spend_usd": sum(
                v.cost_history[-1].amount_usd for v in vendors if v.cost_history
            ),
            "risk_breakdown": {},
            "vendor_details": [],
        }

        for vendor in vendors:
            # Calculate overall vendor risk
            risk_score = self._calculate_vendor_risk_score(vendor)
            risk_level = self._score_to_risk_level(risk_score)

            if risk_level.value not in dashboard["risk_breakdown"]:
                dashboard["risk_breakdown"][risk_level.value] = 0
            dashboard["risk_breakdown"][risk_level.value] += 1

            dashboard["vendor_details"].append({
                "id": vendor.id,
                "name": vendor.name,
                "category": vendor.category.value,
                "risk_score": risk_score,
                "risk_level": risk_level.value,
                "sla_score": vendor.sla_metrics.sla_score,
                "meeting_sla": vendor.sla_metrics.is_meeting_sla,
                "active_outages": len([o for o in vendor.outages if not o.resolved_at]),
                "drift_events_30d": len([
                    d for d in vendor.drift_events
                    if d.detected_at > datetime.utcnow() - timedelta(days=30)
                ]),
                "has_exit_plan": vendor.exit_plan is not None,
                "last_assessed": vendor.last_assessed.isoformat() if vendor.last_assessed else None,
            })

        dashboard["vendor_details"].sort(key=lambda x: x["risk_score"], reverse=True)
        return dashboard

    def _calculate_vendor_risk_score(self, vendor: Vendor) -> float:
        score = 0.0
        # SLA performance (0-30 points)
        sla_score = vendor.sla_metrics.sla_score
        score += max(0, 30 - (sla_score * 0.3))
        # Outage history (0-25 points)
        recent_outages = [o for o in vendor.outages
                         if o.started_at > datetime.utcnow() - timedelta(days=90)]
        score += min(25, len(recent_outages) * 8)
        # Behavior drift (0-20 points)
        recent_drift = [d for d in vendor.drift_events
                       if d.detected_at > datetime.utcnow() - timedelta(days=30)]
        score += min(20, len(recent_drift) * 7)
        # No exit plan (0-15 points)
        if not vendor.exit_plan:
            score += 15
        # Assessment staleness (0-10 points)
        if not vendor.last_assessed:
            score += 10
        elif (datetime.utcnow() - vendor.last_assessed).days > 180:
            score += 5
        return min(score, 100.0)

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        if score >= 70:
            return RiskLevel.CRITICAL
        elif score >= 50:
            return RiskLevel.HIGH
        elif score >= 30:
            return RiskLevel.MEDIUM
        elif score >= 15:
            return RiskLevel.LOW
        return RiskLevel.MINIMAL

    # -------------------------------------------------------------------------
    # Alternative Vendor Evaluation
    # -------------------------------------------------------------------------

    def compare_vendors(self, vendor_ids: list[str]) -> dict:
        """Compare multiple vendors side by side."""
        vendors = [self._vendors[vid] for vid in vendor_ids if vid in self._vendors]
        if len(vendors) < 2:
            return {"error": "Need at least 2 vendors to compare"}

        return {
            "comparison": [
                {
                    "name": v.name,
                    "category": v.category.value,
                    "sla_score": v.sla_metrics.sla_score,
                    "risk_score": self._calculate_vendor_risk_score(v),
                    "total_outages_90d": len([
                        o for o in v.outages
                        if o.started_at > datetime.utcnow() - timedelta(days=90)
                    ]),
                    "avg_monthly_cost": (
                        statistics.mean([c.amount_usd for c in v.cost_history])
                        if v.cost_history else 0
                    ),
                    "has_exit_plan": v.exit_plan is not None,
                    "drift_events_30d": len([
                        d for d in v.drift_events
                        if d.detected_at > datetime.utcnow() - timedelta(days=30)
                    ]),
                }
                for v in vendors
            ]
        }


# =============================================================================
# Demo
# =============================================================================

def demo():
    print("=" * 60)
    print("Vendor Risk Management - Demo")
    print("=" * 60)

    mgr = VendorRiskManager()

    # Register vendors
    openai = mgr.register_vendor(
        name="OpenAI",
        category=VendorCategory.MODEL_PROVIDER,
        description="Primary LLM and embedding provider",
        primary_contact="enterprise@openai.com",
        website="https://openai.com",
        sla_metrics=SLAMetrics(
            uptime_target=99.9,
            latency_p50_target_ms=500,
            latency_p99_target_ms=2000,
            throughput_target_rps=100,
            error_rate_target=0.01,
            uptime_actual=99.85,
            latency_p50_actual_ms=450,
            latency_p99_actual_ms=2200,
            error_rate_actual=0.008,
        ),
    )

    pinecone = mgr.register_vendor(
        name="Pinecone",
        category=VendorCategory.VECTOR_DB,
        description="Vector database for RAG",
        primary_contact="support@pinecone.io",
        website="https://pinecone.io",
        sla_metrics=SLAMetrics(
            uptime_target=99.95,
            latency_p50_target_ms=50,
            latency_p99_target_ms=200,
            throughput_target_rps=500,
            error_rate_target=0.001,
            uptime_actual=99.97,
            latency_p50_actual_ms=35,
            latency_p99_actual_ms=150,
            error_rate_actual=0.0005,
        ),
    )

    # Assess OpenAI
    print("\n--- Vendor Assessment: OpenAI ---")
    assessment = mgr.assess_vendor(openai.id, {
        "sec-1": 5, "sec-2": 5, "sec-3": 4, "sec-4": 4, "sec-5": 5, "sec-6": 3,
        "rel-1": 4, "rel-2": 5, "rel-3": 4, "rel-4": 3, "rel-5": 4,
        "prv-1": 3, "prv-2": 4, "prv-3": 3, "prv-4": 4,
        "biz-1": 3, "biz-2": 5, "biz-3": 5, "biz-4": 2,
        "ops-1": 4, "ops-2": 3, "ops-3": 3, "ops-4": 2, "ops-5": 4,
    })
    print(f"Overall Score: {assessment['overall_score']:.1f}%")
    print(f"Risk Level: {assessment['risk_level']}")
    print(f"Weakest: {assessment['weakest_category']}")
    for rec in assessment["recommendations"]:
        print(f"  -> {rec}")

    # Record outage
    outage = mgr.record_outage(
        openai.id, OutageImpact.DEGRADED,
        ["chat-completion", "embeddings"],
        root_cause="Rate limiting incident",
    )
    mgr.resolve_outage(openai.id, outage.id, "Provider resolved rate limiting issue")

    # Record costs
    mgr.record_cost(openai.id, "2024-01", 12000, 400_000_000, "tokens")
    mgr.record_cost(openai.id, "2024-02", 14500, 500_000_000, "tokens")
    mgr.record_cost(openai.id, "2024-03", 18000, 600_000_000, "tokens")

    # Set exit plan
    mgr.set_exit_plan(openai.id, ExitPlan(
        vendor_id=openai.id,
        alternative_vendors=["Anthropic", "Google Gemini", "Local Llama"],
        migration_time_estimate_days=14,
        data_export_format="N/A (stateless API)",
        data_export_tested=True,
        estimated_migration_cost_usd=50000,
        capability_gaps_during_migration=["Function calling quality may differ", "GPT-4V equivalent needed"],
        last_tested=datetime.utcnow() - timedelta(days=45),
        runbook_url="https://wiki.internal/runbooks/openai-exit",
    ))

    # Dashboard
    print("\n--- Vendor Health Dashboard ---")
    dashboard = mgr.get_vendor_health_dashboard()
    print(f"Total Vendors: {dashboard['total_vendors']}")
    print(f"Meeting SLA: {dashboard['vendors_meeting_sla']}/{dashboard['total_vendors']}")
    print(f"Active Outages: {dashboard['active_outages']}")
    for v in dashboard["vendor_details"]:
        print(f"  {v['name']}: risk={v['risk_score']:.0f}, sla={v['sla_score']:.0f}, "
              f"level={v['risk_level']}")

    # Exit readiness
    print("\n--- Exit Readiness: OpenAI ---")
    readiness = mgr.evaluate_exit_readiness(openai.id)
    print(f"Ready: {readiness['ready']}")
    print(f"Migration time: {readiness['migration_time_days']} days")
    print(f"Cost: ${readiness['migration_cost_usd']:,.0f}")
    if readiness["issues"]:
        for issue in readiness["issues"]:
            print(f"  Issue: {issue}")

    print("\n[Done]")


if __name__ == "__main__":
    demo()
