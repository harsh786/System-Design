"""
AI Risk Register System
========================
Comprehensive risk identification, assessment, mitigation, and monitoring
for AI systems following NIST AI RMF and ISO 31000 principles.
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# =============================================================================
# Enumerations
# =============================================================================

class RiskCategory(Enum):
    MODEL = "model"
    DATA = "data"
    SECURITY = "security"
    OPERATIONAL = "operational"
    ETHICAL = "ethical"
    LEGAL = "legal"
    REPUTATIONAL = "reputational"
    ENVIRONMENTAL = "environmental"


class RiskSubCategory(Enum):
    # Model
    ACCURACY_DEGRADATION = "accuracy_degradation"
    BIAS_AMPLIFICATION = "bias_amplification"
    HALLUCINATION = "hallucination"
    ADVERSARIAL_VULNERABILITY = "adversarial_vulnerability"
    MODEL_DRIFT = "model_drift"
    OVERFITTING = "overfitting"
    # Data
    DATA_POISONING = "data_poisoning"
    PRIVACY_VIOLATION = "privacy_violation"
    CONSENT_ISSUES = "consent_issues"
    DATA_QUALITY = "data_quality"
    REPRESENTATIVENESS = "representativeness"
    DATA_LEAKAGE = "data_leakage"
    # Security
    PROMPT_INJECTION = "prompt_injection"
    MODEL_THEFT = "model_theft"
    DATA_EXFILTRATION = "data_exfiltration"
    SUPPLY_CHAIN = "supply_chain"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    # Operational
    SYSTEM_OUTAGE = "system_outage"
    SCALING_FAILURE = "scaling_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    MISUSE = "misuse"
    # Ethical
    DISCRIMINATION = "discrimination"
    TRANSPARENCY_FAILURE = "transparency_failure"
    AUTONOMY_VIOLATION = "autonomy_violation"
    ENVIRONMENTAL_HARM = "environmental_harm"
    # Legal
    REGULATORY_VIOLATION = "regulatory_violation"
    IP_INFRINGEMENT = "ip_infringement"
    LIABILITY_EXPOSURE = "liability_exposure"
    CONTRACTUAL_BREACH = "contractual_breach"


class Likelihood(Enum):
    RARE = 1           # < 5% probability in 12 months
    UNLIKELY = 2      # 5-20%
    POSSIBLE = 3      # 20-50%
    LIKELY = 4        # 50-80%
    ALMOST_CERTAIN = 5  # > 80%


class Impact(Enum):
    NEGLIGIBLE = 1    # Minor inconvenience, easily corrected
    MINOR = 2         # Limited harm to small group, short duration
    MODERATE = 3      # Significant harm to individuals or moderate business impact
    MAJOR = 4         # Serious harm to many, significant legal/financial consequences
    CRITICAL = 5      # Catastrophic, existential threat, irreversible


class RiskRating(Enum):
    LOW = "low"           # Score 1-4
    MEDIUM = "medium"     # Score 5-9
    HIGH = "high"         # Score 10-15
    CRITICAL = "critical" # Score 16-25


class RiskStatus(Enum):
    IDENTIFIED = "identified"
    ASSESSING = "assessing"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    ACCEPTED = "accepted"
    CLOSED = "closed"
    ESCALATED = "escalated"


class MitigationStrategy(Enum):
    AVOID = "avoid"       # Don't proceed with the activity
    MITIGATE = "mitigate" # Reduce likelihood or impact
    TRANSFER = "transfer" # Insurance, contractual allocation
    ACCEPT = "accept"     # Acknowledge and monitor


class MitigationStatus(Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    INEFFECTIVE = "ineffective"


class ReviewDecision(Enum):
    MAINTAIN = "maintain"           # Keep current assessment
    UPGRADE = "upgrade"             # Increase risk rating
    DOWNGRADE = "downgrade"         # Decrease risk rating
    CLOSE = "close"                 # Risk no longer applicable
    ESCALATE = "escalate"           # Requires senior attention
    ADDITIONAL_MITIGATION = "additional_mitigation"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class MitigationAction:
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    owner: str = ""
    strategy: MitigationStrategy = MitigationStrategy.MITIGATE
    status: MitigationStatus = MitigationStatus.PLANNED
    target_date: Optional[str] = None
    completion_date: Optional[str] = None
    effectiveness_score: Optional[float] = None  # 0-1
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RiskAssessment:
    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assessor: str = ""
    assessment_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    likelihood: Likelihood = Likelihood.POSSIBLE
    impact: Impact = Impact.MODERATE
    rationale: str = ""
    evidence: list = field(default_factory=list)
    confidence_level: float = 0.5  # 0-1, how confident in assessment

    @property
    def risk_score(self) -> int:
        return self.likelihood.value * self.impact.value

    @property
    def risk_rating(self) -> RiskRating:
        score = self.risk_score
        if score <= 4:
            return RiskRating.LOW
        elif score <= 9:
            return RiskRating.MEDIUM
        elif score <= 15:
            return RiskRating.HIGH
        else:
            return RiskRating.CRITICAL


@dataclass
class RiskReview:
    review_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reviewer: str = ""
    review_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    previous_rating: Optional[str] = None
    new_rating: Optional[str] = None
    decision: ReviewDecision = ReviewDecision.MAINTAIN
    comments: str = ""
    next_review_date: Optional[str] = None
    action_items: list = field(default_factory=list)


@dataclass
class RiskAlert:
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    risk_id: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    trigger: str = ""
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None


@dataclass
class RiskEntry:
    """Core risk register entry."""
    risk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    category: RiskCategory = RiskCategory.MODEL
    sub_category: Optional[RiskSubCategory] = None
    ai_system_id: str = ""
    ai_system_name: str = ""
    status: RiskStatus = RiskStatus.IDENTIFIED

    # Stakeholder information
    risk_owner: str = ""
    identified_by: str = ""
    affected_stakeholders: list = field(default_factory=list)

    # Assessment history
    assessments: list = field(default_factory=list)

    # Current assessment (latest)
    current_likelihood: Likelihood = Likelihood.POSSIBLE
    current_impact: Impact = Impact.MODERATE

    # Inherent risk (before controls)
    inherent_likelihood: Likelihood = Likelihood.POSSIBLE
    inherent_impact: Impact = Impact.MODERATE

    # Residual risk (after controls)
    residual_likelihood: Optional[Likelihood] = None
    residual_impact: Optional[Impact] = None

    # Target risk (acceptable level)
    target_likelihood: Optional[Likelihood] = None
    target_impact: Optional[Impact] = None

    # Mitigation
    mitigation_actions: list = field(default_factory=list)

    # Reviews
    reviews: list = field(default_factory=list)
    next_review_date: Optional[str] = None
    review_frequency_days: int = 90

    # Metadata
    tags: list = field(default_factory=list)
    related_risks: list = field(default_factory=list)
    regulatory_references: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    closed_at: Optional[str] = None

    @property
    def current_risk_score(self) -> int:
        return self.current_likelihood.value * self.current_impact.value

    @property
    def current_risk_rating(self) -> RiskRating:
        score = self.current_risk_score
        if score <= 4:
            return RiskRating.LOW
        elif score <= 9:
            return RiskRating.MEDIUM
        elif score <= 15:
            return RiskRating.HIGH
        return RiskRating.CRITICAL

    @property
    def inherent_risk_score(self) -> int:
        return self.inherent_likelihood.value * self.inherent_impact.value

    @property
    def residual_risk_score(self) -> Optional[int]:
        if self.residual_likelihood and self.residual_impact:
            return self.residual_likelihood.value * self.residual_impact.value
        return None

    @property
    def is_overdue_review(self) -> bool:
        if not self.next_review_date:
            return False
        return datetime.utcnow().isoformat() > self.next_review_date


# =============================================================================
# Risk Identification Framework
# =============================================================================

class RiskIdentificationFramework:
    """Systematic approach to identifying AI risks."""

    # Predefined risk scenarios by category for guided identification
    RISK_SCENARIOS = {
        RiskCategory.MODEL: [
            {
                "scenario": "Model accuracy drops below acceptable threshold in production",
                "sub_category": RiskSubCategory.ACCURACY_DEGRADATION,
                "typical_causes": ["data drift", "concept drift", "distribution shift"],
                "typical_impact": "Incorrect decisions affecting users",
                "detection_methods": ["performance monitoring", "A/B testing", "user feedback"],
            },
            {
                "scenario": "Model produces biased outputs for protected groups",
                "sub_category": RiskSubCategory.BIAS_AMPLIFICATION,
                "typical_causes": ["biased training data", "proxy variables", "feedback loops"],
                "typical_impact": "Discrimination, regulatory action, reputational damage",
                "detection_methods": ["fairness metrics", "disaggregated evaluation", "audits"],
            },
            {
                "scenario": "LLM generates factually incorrect information presented as truth",
                "sub_category": RiskSubCategory.HALLUCINATION,
                "typical_causes": ["knowledge gaps", "overconfident generation", "prompt ambiguity"],
                "typical_impact": "Misinformation, user harm, liability",
                "detection_methods": ["fact-checking systems", "confidence scoring", "user reports"],
            },
            {
                "scenario": "Adversarial inputs cause model to produce dangerous outputs",
                "sub_category": RiskSubCategory.ADVERSARIAL_VULNERABILITY,
                "typical_causes": ["lack of robustness", "unbounded inputs", "no input validation"],
                "typical_impact": "Safety violations, system compromise",
                "detection_methods": ["red-teaming", "adversarial testing", "anomaly detection"],
            },
        ],
        RiskCategory.DATA: [
            {
                "scenario": "Training data contains personally identifiable information without consent",
                "sub_category": RiskSubCategory.PRIVACY_VIOLATION,
                "typical_causes": ["insufficient data review", "scraping without consent", "data linkage"],
                "typical_impact": "GDPR fines, lawsuits, trust erosion",
                "detection_methods": ["PII scanning", "consent audits", "data lineage review"],
            },
            {
                "scenario": "Malicious data injected into training pipeline",
                "sub_category": RiskSubCategory.DATA_POISONING,
                "typical_causes": ["compromised data source", "insider threat", "supply chain attack"],
                "typical_impact": "Backdoor behavior, degraded performance, safety violations",
                "detection_methods": ["data validation", "anomaly detection", "provenance verification"],
            },
        ],
        RiskCategory.SECURITY: [
            {
                "scenario": "Prompt injection bypasses safety controls",
                "sub_category": RiskSubCategory.PROMPT_INJECTION,
                "typical_causes": ["insufficient input sanitization", "reliance on prompt-only controls"],
                "typical_impact": "Unauthorized actions, data disclosure, system misuse",
                "detection_methods": ["injection testing", "output monitoring", "canary tokens"],
            },
        ],
        RiskCategory.ETHICAL: [
            {
                "scenario": "AI system makes decisions users cannot understand or contest",
                "sub_category": RiskSubCategory.TRANSPARENCY_FAILURE,
                "typical_causes": ["black-box models", "no explanation system", "complex pipelines"],
                "typical_impact": "Loss of trust, regulatory non-compliance, harm without recourse",
                "detection_methods": ["explainability audits", "user testing", "contestability review"],
            },
        ],
        RiskCategory.LEGAL: [
            {
                "scenario": "AI system classified as high-risk under EU AI Act without compliance",
                "sub_category": RiskSubCategory.REGULATORY_VIOLATION,
                "typical_causes": ["misclassification", "delayed compliance", "scope change"],
                "typical_impact": "Fines up to 35M EUR or 7% global turnover, market withdrawal",
                "detection_methods": ["compliance assessment", "regulatory monitoring", "legal review"],
            },
        ],
    }

    def get_risk_scenarios(self, category: Optional[RiskCategory] = None) -> list:
        """Get predefined risk scenarios for guided identification."""
        if category:
            return self.RISK_SCENARIOS.get(category, [])
        all_scenarios = []
        for scenarios in self.RISK_SCENARIOS.values():
            all_scenarios.extend(scenarios)
        return all_scenarios

    def assess_system_risks(self, system_profile: dict) -> list[dict]:
        """
        Given an AI system profile, identify applicable risks.

        system_profile should contain:
        - system_type: "classification", "generation", "recommendation", etc.
        - data_sources: list of data source types
        - deployment_context: "internal", "customer-facing", "critical-infrastructure"
        - affected_populations: list of population types
        - regulatory_context: list of applicable regulations
        - autonomy_level: "advisory", "semi-autonomous", "autonomous"
        """
        applicable_risks = []

        # All AI systems have model risks
        for scenario in self.RISK_SCENARIOS[RiskCategory.MODEL]:
            risk = {**scenario, "applicability": "high"}
            applicable_risks.append(risk)

        # Generative systems have higher hallucination/injection risk
        if system_profile.get("system_type") in ["generation", "conversational", "summarization"]:
            for scenario in self.RISK_SCENARIOS[RiskCategory.SECURITY]:
                risk = {**scenario, "applicability": "high"}
                applicable_risks.append(risk)

        # Customer-facing systems have higher ethical/legal risk
        if system_profile.get("deployment_context") == "customer-facing":
            for scenario in self.RISK_SCENARIOS[RiskCategory.ETHICAL]:
                risk = {**scenario, "applicability": "high"}
                applicable_risks.append(risk)

        # Systems with personal data have privacy risks
        if any("personal" in ds.lower() for ds in system_profile.get("data_sources", [])):
            for scenario in self.RISK_SCENARIOS[RiskCategory.DATA]:
                if scenario["sub_category"] == RiskSubCategory.PRIVACY_VIOLATION:
                    risk = {**scenario, "applicability": "high"}
                    applicable_risks.append(risk)

        # Regulatory context
        if "eu_ai_act" in system_profile.get("regulatory_context", []):
            for scenario in self.RISK_SCENARIOS[RiskCategory.LEGAL]:
                risk = {**scenario, "applicability": "high"}
                applicable_risks.append(risk)

        return applicable_risks


# =============================================================================
# Risk Register
# =============================================================================

class AIRiskRegister:
    """Central AI Risk Register managing all risk entries."""

    def __init__(self, storage_backend=None):
        self.risks: dict[str, RiskEntry] = {}
        self.alerts: list[RiskAlert] = []
        self.identification_framework = RiskIdentificationFramework()
        self._alert_handlers: list = []
        self._storage = storage_backend

    # -------------------------------------------------------------------------
    # Risk CRUD
    # -------------------------------------------------------------------------

    def register_risk(
        self,
        title: str,
        description: str,
        category: RiskCategory,
        ai_system_id: str,
        ai_system_name: str,
        risk_owner: str,
        identified_by: str,
        likelihood: Likelihood = Likelihood.POSSIBLE,
        impact: Impact = Impact.MODERATE,
        sub_category: Optional[RiskSubCategory] = None,
        affected_stakeholders: Optional[list] = None,
        regulatory_references: Optional[list] = None,
        tags: Optional[list] = None,
    ) -> RiskEntry:
        """Register a new risk in the register."""
        risk = RiskEntry(
            title=title,
            description=description,
            category=category,
            sub_category=sub_category,
            ai_system_id=ai_system_id,
            ai_system_name=ai_system_name,
            risk_owner=risk_owner,
            identified_by=identified_by,
            current_likelihood=likelihood,
            current_impact=impact,
            inherent_likelihood=likelihood,
            inherent_impact=impact,
            affected_stakeholders=affected_stakeholders or [],
            regulatory_references=regulatory_references or [],
            tags=tags or [],
            status=RiskStatus.IDENTIFIED,
        )

        # Set initial review date
        risk.next_review_date = (
            datetime.utcnow() + timedelta(days=risk.review_frequency_days)
        ).isoformat()

        # Create initial assessment
        initial_assessment = RiskAssessment(
            assessor=identified_by,
            likelihood=likelihood,
            impact=impact,
            rationale="Initial risk identification",
        )
        risk.assessments.append(asdict(initial_assessment))

        self.risks[risk.risk_id] = risk
        logger.info(f"Risk registered: {risk.risk_id} - {title} [{risk.current_risk_rating.value}]")

        # Check if immediate alert needed
        if risk.current_risk_rating in (RiskRating.HIGH, RiskRating.CRITICAL):
            self._raise_alert(
                risk_id=risk.risk_id,
                severity=AlertSeverity.HIGH if risk.current_risk_rating == RiskRating.HIGH else AlertSeverity.CRITICAL,
                trigger="new_high_risk",
                message=f"New {risk.current_risk_rating.value} risk registered: {title}",
            )

        return risk

    def update_risk(self, risk_id: str, **updates) -> RiskEntry:
        """Update risk entry fields."""
        risk = self.risks.get(risk_id)
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        for key, value in updates.items():
            if hasattr(risk, key):
                setattr(risk, key, value)

        risk.updated_at = datetime.utcnow().isoformat()
        return risk

    def close_risk(self, risk_id: str, reason: str, closed_by: str) -> RiskEntry:
        """Close a risk (no longer applicable)."""
        risk = self.risks.get(risk_id)
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        risk.status = RiskStatus.CLOSED
        risk.closed_at = datetime.utcnow().isoformat()
        risk.updated_at = datetime.utcnow().isoformat()

        # Add closing review
        review = RiskReview(
            reviewer=closed_by,
            decision=ReviewDecision.CLOSE,
            comments=reason,
        )
        risk.reviews.append(asdict(review))

        logger.info(f"Risk closed: {risk_id} - {reason}")
        return risk

    # -------------------------------------------------------------------------
    # Risk Assessment
    # -------------------------------------------------------------------------

    def assess_risk(
        self,
        risk_id: str,
        assessor: str,
        likelihood: Likelihood,
        impact: Impact,
        rationale: str,
        evidence: Optional[list] = None,
        confidence_level: float = 0.7,
    ) -> RiskAssessment:
        """Perform a risk assessment (re-assessment)."""
        risk = self.risks.get(risk_id)
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        previous_rating = risk.current_risk_rating

        assessment = RiskAssessment(
            assessor=assessor,
            likelihood=likelihood,
            impact=impact,
            rationale=rationale,
            evidence=evidence or [],
            confidence_level=confidence_level,
        )

        risk.assessments.append(asdict(assessment))
        risk.current_likelihood = likelihood
        risk.current_impact = impact
        risk.status = RiskStatus.ASSESSING
        risk.updated_at = datetime.utcnow().isoformat()

        # Alert on rating increase
        new_rating = risk.current_risk_rating
        if new_rating.value != previous_rating.value:
            rating_order = [RiskRating.LOW, RiskRating.MEDIUM, RiskRating.HIGH, RiskRating.CRITICAL]
            if rating_order.index(new_rating) > rating_order.index(previous_rating):
                self._raise_alert(
                    risk_id=risk_id,
                    severity=AlertSeverity.HIGH,
                    trigger="risk_rating_increased",
                    message=f"Risk rating increased from {previous_rating.value} to {new_rating.value}: {risk.title}",
                )

        return assessment

    def set_residual_risk(
        self,
        risk_id: str,
        likelihood: Likelihood,
        impact: Impact,
    ) -> RiskEntry:
        """Set residual risk after controls are applied."""
        risk = self.risks.get(risk_id)
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        risk.residual_likelihood = likelihood
        risk.residual_impact = impact
        risk.updated_at = datetime.utcnow().isoformat()
        return risk

    # -------------------------------------------------------------------------
    # Mitigation Management
    # -------------------------------------------------------------------------

    def add_mitigation(
        self,
        risk_id: str,
        description: str,
        owner: str,
        strategy: MitigationStrategy,
        target_date: str,
    ) -> MitigationAction:
        """Add a mitigation action to a risk."""
        risk = self.risks.get(risk_id)
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        action = MitigationAction(
            description=description,
            owner=owner,
            strategy=strategy,
            target_date=target_date,
        )

        risk.mitigation_actions.append(asdict(action))
        risk.status = RiskStatus.MITIGATING
        risk.updated_at = datetime.utcnow().isoformat()

        logger.info(f"Mitigation added to risk {risk_id}: {description}")
        return action

    def update_mitigation_status(
        self,
        risk_id: str,
        action_id: str,
        status: MitigationStatus,
        effectiveness_score: Optional[float] = None,
        notes: str = "",
    ) -> None:
        """Update the status of a mitigation action."""
        risk = self.risks.get(risk_id)
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        for action in risk.mitigation_actions:
            if action["action_id"] == action_id:
                action["status"] = status.value
                action["updated_at"] = datetime.utcnow().isoformat()
                if effectiveness_score is not None:
                    action["effectiveness_score"] = effectiveness_score
                if notes:
                    action["notes"] = notes
                if status == MitigationStatus.COMPLETED:
                    action["completion_date"] = datetime.utcnow().isoformat()
                break

        # Check if all mitigations complete -> move to monitoring
        all_complete = all(
            a["status"] in (MitigationStatus.COMPLETED.value, MitigationStatus.VERIFIED.value)
            for a in risk.mitigation_actions
        )
        if all_complete and risk.mitigation_actions:
            risk.status = RiskStatus.MONITORING

        risk.updated_at = datetime.utcnow().isoformat()

    # -------------------------------------------------------------------------
    # Risk Review
    # -------------------------------------------------------------------------

    def review_risk(
        self,
        risk_id: str,
        reviewer: str,
        decision: ReviewDecision,
        comments: str,
        new_likelihood: Optional[Likelihood] = None,
        new_impact: Optional[Impact] = None,
        action_items: Optional[list] = None,
    ) -> RiskReview:
        """Conduct a risk review."""
        risk = self.risks.get(risk_id)
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        previous_rating = risk.current_risk_rating.value

        review = RiskReview(
            reviewer=reviewer,
            previous_rating=previous_rating,
            decision=decision,
            comments=comments,
            action_items=action_items or [],
        )

        # Apply rating changes
        if decision == ReviewDecision.CLOSE:
            risk.status = RiskStatus.CLOSED
            risk.closed_at = datetime.utcnow().isoformat()
        elif decision == ReviewDecision.ESCALATE:
            risk.status = RiskStatus.ESCALATED
            self._raise_alert(
                risk_id=risk_id,
                severity=AlertSeverity.CRITICAL,
                trigger="risk_escalated",
                message=f"Risk escalated by {reviewer}: {risk.title}",
            )

        if new_likelihood:
            risk.current_likelihood = new_likelihood
        if new_impact:
            risk.current_impact = new_impact

        review.new_rating = risk.current_risk_rating.value

        # Set next review date
        risk.next_review_date = (
            datetime.utcnow() + timedelta(days=risk.review_frequency_days)
        ).isoformat()
        review.next_review_date = risk.next_review_date

        risk.reviews.append(asdict(review))
        risk.updated_at = datetime.utcnow().isoformat()

        logger.info(f"Risk reviewed: {risk_id} - Decision: {decision.value}")
        return review

    def get_overdue_reviews(self) -> list[RiskEntry]:
        """Get risks with overdue reviews."""
        now = datetime.utcnow().isoformat()
        return [
            risk for risk in self.risks.values()
            if risk.status not in (RiskStatus.CLOSED,)
            and risk.next_review_date
            and risk.next_review_date < now
        ]

    # -------------------------------------------------------------------------
    # Monitoring and Alerting
    # -------------------------------------------------------------------------

    def _raise_alert(self, risk_id: str, severity: AlertSeverity, trigger: str, message: str):
        """Raise a risk alert."""
        alert = RiskAlert(
            risk_id=risk_id,
            severity=severity,
            trigger=trigger,
            message=message,
        )
        self.alerts.append(alert)
        logger.warning(f"RISK ALERT [{severity.value}]: {message}")

        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

        return alert

    def register_alert_handler(self, handler):
        """Register a callback for risk alerts."""
        self._alert_handlers.append(handler)

    def check_monitoring_triggers(self) -> list[RiskAlert]:
        """Run periodic monitoring checks and raise alerts as needed."""
        new_alerts = []

        for risk in self.risks.values():
            if risk.status == RiskStatus.CLOSED:
                continue

            # Check overdue reviews
            if risk.is_overdue_review:
                alert = self._raise_alert(
                    risk_id=risk.risk_id,
                    severity=AlertSeverity.WARNING,
                    trigger="overdue_review",
                    message=f"Risk review overdue: {risk.title}",
                )
                new_alerts.append(alert)

            # Check overdue mitigations
            now = datetime.utcnow().isoformat()
            for action in risk.mitigation_actions:
                if (action["status"] in (MitigationStatus.PLANNED.value, MitigationStatus.IN_PROGRESS.value)
                        and action.get("target_date") and action["target_date"] < now):
                    alert = self._raise_alert(
                        risk_id=risk.risk_id,
                        severity=AlertSeverity.WARNING,
                        trigger="overdue_mitigation",
                        message=f"Mitigation overdue for risk '{risk.title}': {action['description']}",
                    )
                    new_alerts.append(alert)

            # Check critical/high risks without active mitigation
            if risk.current_risk_rating in (RiskRating.HIGH, RiskRating.CRITICAL):
                active_mitigations = [
                    a for a in risk.mitigation_actions
                    if a["status"] in (MitigationStatus.PLANNED.value, MitigationStatus.IN_PROGRESS.value)
                ]
                if not active_mitigations and risk.status != RiskStatus.ACCEPTED:
                    alert = self._raise_alert(
                        risk_id=risk.risk_id,
                        severity=AlertSeverity.HIGH,
                        trigger="unmitigated_high_risk",
                        message=f"High/critical risk without active mitigation: {risk.title}",
                    )
                    new_alerts.append(alert)

        return new_alerts

    # -------------------------------------------------------------------------
    # Reporting and Analytics
    # -------------------------------------------------------------------------

    def get_dashboard_data(self) -> dict:
        """Generate dashboard summary data."""
        active_risks = [r for r in self.risks.values() if r.status != RiskStatus.CLOSED]

        rating_distribution = {rating.value: 0 for rating in RiskRating}
        category_distribution = {cat.value: 0 for cat in RiskCategory}
        status_distribution = {status.value: 0 for status in RiskStatus}

        for risk in active_risks:
            rating_distribution[risk.current_risk_rating.value] += 1
            category_distribution[risk.category.value] += 1
            status_distribution[risk.status.value] += 1

        overdue_reviews = self.get_overdue_reviews()

        # Top risks by score
        top_risks = sorted(active_risks, key=lambda r: r.current_risk_score, reverse=True)[:10]

        return {
            "summary": {
                "total_active_risks": len(active_risks),
                "critical_risks": rating_distribution["critical"],
                "high_risks": rating_distribution["high"],
                "overdue_reviews": len(overdue_reviews),
                "unacknowledged_alerts": len([a for a in self.alerts if not a.acknowledged]),
            },
            "rating_distribution": rating_distribution,
            "category_distribution": category_distribution,
            "status_distribution": status_distribution,
            "top_risks": [
                {
                    "risk_id": r.risk_id,
                    "title": r.title,
                    "category": r.category.value,
                    "rating": r.current_risk_rating.value,
                    "score": r.current_risk_score,
                    "owner": r.risk_owner,
                }
                for r in top_risks
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_risk_trends(self, days: int = 90) -> dict:
        """Analyze risk trends over time based on assessment history."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        trends = {
            "period_days": days,
            "new_risks": 0,
            "closed_risks": 0,
            "escalated_risks": 0,
            "rating_changes": [],
            "category_trend": {cat.value: {"added": 0, "closed": 0} for cat in RiskCategory},
        }

        for risk in self.risks.values():
            if risk.created_at >= cutoff:
                trends["new_risks"] += 1
                trends["category_trend"][risk.category.value]["added"] += 1

            if risk.closed_at and risk.closed_at >= cutoff:
                trends["closed_risks"] += 1
                trends["category_trend"][risk.category.value]["closed"] += 1

            if risk.status == RiskStatus.ESCALATED:
                for review in risk.reviews:
                    if (review.get("decision") == ReviewDecision.ESCALATE.value
                            and review.get("review_date", "") >= cutoff):
                        trends["escalated_risks"] += 1

            # Track rating changes from reviews
            for review in risk.reviews:
                if (review.get("review_date", "") >= cutoff
                        and review.get("previous_rating") != review.get("new_rating")):
                    trends["rating_changes"].append({
                        "risk_id": risk.risk_id,
                        "title": risk.title,
                        "from": review["previous_rating"],
                        "to": review["new_rating"],
                        "date": review["review_date"],
                    })

        return trends

    def generate_risk_report(self, format: str = "summary") -> dict:
        """Generate a structured risk report."""
        dashboard = self.get_dashboard_data()
        trends = self.get_risk_trends()

        report = {
            "report_type": "ai_risk_register",
            "generated_at": datetime.utcnow().isoformat(),
            "executive_summary": {
                "total_active_risks": dashboard["summary"]["total_active_risks"],
                "critical_and_high": dashboard["summary"]["critical_risks"] + dashboard["summary"]["high_risks"],
                "risk_trend": "increasing" if trends["new_risks"] > trends["closed_risks"] else "decreasing",
                "key_concerns": [],
            },
            "dashboard": dashboard,
            "trends": trends,
            "recommendations": [],
        }

        # Generate recommendations
        if dashboard["summary"]["critical_risks"] > 0:
            report["recommendations"].append(
                "URGENT: Critical risks require immediate board-level attention and mitigation."
            )
        if dashboard["summary"]["overdue_reviews"] > 3:
            report["recommendations"].append(
                "Multiple risk reviews are overdue. Schedule dedicated risk review session."
            )
        if trends["escalated_risks"] > 2:
            report["recommendations"].append(
                "Rising escalations indicate systemic governance gaps. Review risk management processes."
            )

        return report

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def export_register(self) -> dict:
        """Export entire register as JSON-serializable dict."""
        return {
            "risks": {
                rid: {
                    **asdict(risk),
                    "category": risk.category.value,
                    "sub_category": risk.sub_category.value if risk.sub_category else None,
                    "status": risk.status.value,
                    "current_likelihood": risk.current_likelihood.value,
                    "current_impact": risk.current_impact.value,
                    "inherent_likelihood": risk.inherent_likelihood.value,
                    "inherent_impact": risk.inherent_impact.value,
                    "residual_likelihood": risk.residual_likelihood.value if risk.residual_likelihood else None,
                    "residual_impact": risk.residual_impact.value if risk.residual_impact else None,
                    "target_likelihood": risk.target_likelihood.value if risk.target_likelihood else None,
                    "target_impact": risk.target_impact.value if risk.target_impact else None,
                    "current_risk_score": risk.current_risk_score,
                    "current_risk_rating": risk.current_risk_rating.value,
                }
                for rid, risk in self.risks.items()
            },
            "alerts": [asdict(a) for a in self.alerts],
            "exported_at": datetime.utcnow().isoformat(),
        }


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    register = AIRiskRegister()

    # Register risks
    risk1 = register.register_risk(
        title="Customer churn model exhibits racial bias",
        description="Preliminary analysis shows the churn prediction model has significantly "
                    "different false positive rates across racial demographics, potentially "
                    "leading to discriminatory retention offers.",
        category=RiskCategory.ETHICAL,
        sub_category=RiskSubCategory.DISCRIMINATION,
        ai_system_id="sys-churn-001",
        ai_system_name="Customer Churn Predictor",
        risk_owner="jane.smith@company.com",
        identified_by="fairness-audit-q4",
        likelihood=Likelihood.LIKELY,
        impact=Impact.MAJOR,
        affected_stakeholders=["customers", "regulators", "legal"],
        regulatory_references=["EU AI Act Art. 10", "ECOA"],
        tags=["fairness", "high-priority", "customer-facing"],
    )

    # Add mitigation
    register.add_mitigation(
        risk_id=risk1.risk_id,
        description="Retrain model with bias-aware objective function and balanced dataset",
        owner="ml-team@company.com",
        strategy=MitigationStrategy.MITIGATE,
        target_date=(datetime.utcnow() + timedelta(days=30)).isoformat(),
    )

    register.add_mitigation(
        risk_id=risk1.risk_id,
        description="Implement post-processing fairness calibration on model outputs",
        owner="ml-team@company.com",
        strategy=MitigationStrategy.MITIGATE,
        target_date=(datetime.utcnow() + timedelta(days=14)).isoformat(),
    )

    # Register another risk
    risk2 = register.register_risk(
        title="LLM chatbot susceptible to prompt injection",
        description="Customer-facing chatbot can be manipulated via indirect prompt injection "
                    "through user-uploaded documents, potentially revealing system prompts "
                    "or executing unauthorized actions.",
        category=RiskCategory.SECURITY,
        sub_category=RiskSubCategory.PROMPT_INJECTION,
        ai_system_id="sys-chatbot-002",
        ai_system_name="Customer Support Chatbot",
        risk_owner="security-team@company.com",
        identified_by="red-team-exercise-2024",
        likelihood=Likelihood.LIKELY,
        impact=Impact.MODERATE,
        tags=["security", "llm", "customer-facing"],
    )

    # Review a risk
    register.review_risk(
        risk_id=risk2.risk_id,
        reviewer="ciso@company.com",
        decision=ReviewDecision.ADDITIONAL_MITIGATION,
        comments="Need to implement input sanitization and output filtering before next release.",
        action_items=["Implement input guardrails", "Add output content filter", "Schedule pen test"],
    )

    # Generate reports
    dashboard = register.get_dashboard_data()
    print("\n=== RISK DASHBOARD ===")
    print(json.dumps(dashboard["summary"], indent=2))

    report = register.generate_risk_report()
    print("\n=== RISK REPORT ===")
    print(json.dumps(report["executive_summary"], indent=2))
    print("\nRecommendations:")
    for rec in report["recommendations"]:
        print(f"  - {rec}")

    # Run monitoring checks
    alerts = register.check_monitoring_triggers()
    print(f"\n=== MONITORING: {len(alerts)} new alerts ===")
