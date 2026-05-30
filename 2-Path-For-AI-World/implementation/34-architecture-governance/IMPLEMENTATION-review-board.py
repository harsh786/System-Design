"""
AI Architecture Review Board System

Manages the full lifecycle of architecture reviews for AI systems:
- Intake and risk tiering
- Reviewer assignment
- Checklist generation per risk tier
- Review workflow (submit -> review -> approve/reject)
- Decision recording as ADRs
- Standards compliance checking
- Escalation management
"""

import uuid
import json
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional
from abc import ABC, abstractmethod


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class RiskTier(Enum):
    PROHIBITED = 0  # Tier 0 - Rejected at intake
    CRITICAL = 1    # Tier 1 - Full board review
    MEDIUM = 2      # Tier 2 - Partial board review
    LOW = 3         # Tier 3 - Automated/self-service

class ReviewStatus(Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    TRIAGED = "triaged"
    IN_REVIEW = "in_review"
    PENDING_DISCUSSION = "pending_discussion"
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"

class ReviewerRole(Enum):
    CHIEF_AI_ARCHITECT = "chief_ai_architect"
    AI_SAFETY_LEAD = "ai_safety_lead"
    DATA_GOVERNANCE_LEAD = "data_governance_lead"
    SECURITY_ARCHITECT = "security_architect"
    ML_ENGINEERING_LEAD = "ml_engineering_lead"
    PRODUCT_REPRESENTATIVE = "product_representative"
    LEGAL_COMPLIANCE = "legal_compliance"
    PLATFORM_ENGINEERING = "platform_engineering"
    DOMAIN_EXPERT = "domain_expert"

class RiskDimension(Enum):
    AUTONOMY = "autonomy"
    DATA_SENSITIVITY = "data_sensitivity"
    HARM_POTENTIAL = "harm_potential"
    AUDIENCE = "audience"
    REVERSIBILITY = "reversibility"

RISK_WEIGHTS = {
    RiskDimension.AUTONOMY: 0.25,
    RiskDimension.DATA_SENSITIVITY: 0.20,
    RiskDimension.HARM_POTENTIAL: 0.25,
    RiskDimension.AUDIENCE: 0.15,
    RiskDimension.REVERSIBILITY: 0.15,
}

# Tier thresholds based on weighted score (max=5.0)
TIER_THRESHOLDS = {
    RiskTier.LOW: (1.0, 1.8),
    RiskTier.MEDIUM: (1.8, 3.4),
    RiskTier.CRITICAL: (3.4, 5.0),
}

# Reviewers required per tier
TIER_REVIEWER_REQUIREMENTS = {
    RiskTier.CRITICAL: [
        ReviewerRole.CHIEF_AI_ARCHITECT,
        ReviewerRole.AI_SAFETY_LEAD,
        ReviewerRole.DATA_GOVERNANCE_LEAD,
        ReviewerRole.SECURITY_ARCHITECT,
        ReviewerRole.ML_ENGINEERING_LEAD,
        ReviewerRole.LEGAL_COMPLIANCE,
        ReviewerRole.PLATFORM_ENGINEERING,
    ],
    RiskTier.MEDIUM: [
        ReviewerRole.CHIEF_AI_ARCHITECT,
        ReviewerRole.SECURITY_ARCHITECT,
        ReviewerRole.ML_ENGINEERING_LEAD,
    ],
    RiskTier.LOW: [],  # Automated review only
}

REVIEW_SLA_DAYS = {
    RiskTier.CRITICAL: 10,
    RiskTier.MEDIUM: 5,
    RiskTier.LOW: 1,
}


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class RiskAssessment:
    """Risk scoring for a use case."""
    autonomy: int  # 1-5
    data_sensitivity: int  # 1-5
    harm_potential: int  # 1-5
    audience: int  # 1-5
    reversibility: int  # 1-5
    justifications: dict[str, str] = field(default_factory=dict)

    def weighted_score(self) -> float:
        scores = {
            RiskDimension.AUTONOMY: self.autonomy,
            RiskDimension.DATA_SENSITIVITY: self.data_sensitivity,
            RiskDimension.HARM_POTENTIAL: self.harm_potential,
            RiskDimension.AUDIENCE: self.audience,
            RiskDimension.REVERSIBILITY: self.reversibility,
        }
        return sum(scores[dim] * RISK_WEIGHTS[dim] for dim in RiskDimension)

    def compute_tier(self) -> RiskTier:
        score = self.weighted_score()
        for tier, (low, high) in TIER_THRESHOLDS.items():
            if low <= score < high:
                return tier
        return RiskTier.CRITICAL  # Default to highest if out of range


@dataclass
class UseCaseIntake:
    """Structured intake form for AI use case proposals."""
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    submitter: str = ""
    team: str = ""
    submitted_at: Optional[str] = None

    # Business Context
    problem_statement: str = ""
    target_users: str = ""
    user_type: str = ""  # internal / external / both
    expected_impact: str = ""
    failure_consequences: str = ""
    human_in_loop_strategy: str = ""

    # Technical Scope
    ai_capabilities_needed: list[str] = field(default_factory=list)
    models_considered: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    expected_scale: dict = field(default_factory=dict)
    integrations: list[str] = field(default_factory=list)
    tools_required: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    a2a_interactions: list[str] = field(default_factory=list)

    # Risk Indicators
    involves_pii: bool = False
    involves_sensitive_data: bool = False
    can_cause_financial_harm: bool = False
    can_cause_safety_harm: bool = False
    can_cause_legal_harm: bool = False
    is_customer_facing: bool = False
    involves_autonomous_actions: bool = False
    involves_a2a: bool = False
    regulatory_domains: list[str] = field(default_factory=list)

    # Success Criteria
    measurable_outcomes: list[str] = field(default_factory=list)
    evaluation_metrics: list[str] = field(default_factory=list)
    slo_targets: dict = field(default_factory=dict)
    rollback_strategy: str = ""


@dataclass
class ReviewComment:
    """A comment from a reviewer."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reviewer_id: str = ""
    reviewer_role: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    section: str = ""  # Which checklist section
    comment: str = ""
    severity: str = "info"  # info, concern, blocker
    resolved: bool = False


@dataclass
class ReviewDecision:
    """Final decision on a review."""
    status: ReviewStatus = ReviewStatus.DRAFT
    decided_by: str = ""
    decided_at: Optional[str] = None
    conditions: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    adr_id: Optional[str] = None
    next_review_date: Optional[str] = None


@dataclass
class ReviewRequest:
    """Complete review request with all metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intake: UseCaseIntake = field(default_factory=UseCaseIntake)
    risk_assessment: Optional[RiskAssessment] = None
    risk_tier: Optional[RiskTier] = None
    status: ReviewStatus = ReviewStatus.DRAFT
    assigned_reviewers: list[str] = field(default_factory=list)
    checklist: dict = field(default_factory=dict)
    comments: list[ReviewComment] = field(default_factory=list)
    decision: Optional[ReviewDecision] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sla_deadline: Optional[str] = None
    escalated: bool = False
    escalation_reason: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.risk_tier:
            data["risk_tier"] = self.risk_tier.value
        data["status"] = self.status.value
        return data


# =============================================================================
# CHECKLIST GENERATION
# =============================================================================

class ChecklistGenerator:
    """Generates review checklists based on risk tier and use case characteristics."""

    BASE_CHECKLIST = {
        "use_case": [
            "Business justification is clear and measurable",
            "Target users are identified",
            "Success criteria are defined and measurable",
            "Failure mode analysis is complete",
        ],
        "data": [
            "All data sources identified",
            "Data quality assessment complete",
            "Data lineage documented",
        ],
        "architecture": [
            "System design documented",
            "Model selection justified",
            "Scalability addressed",
        ],
        "evaluation": [
            "Evaluation suite exists",
            "Baseline metrics established",
            "Regression criteria defined",
        ],
        "security": [
            "Authentication/authorization defined",
            "Secrets management plan",
            "Logging configured",
        ],
        "operations": [
            "SLOs defined",
            "Rollback plan documented",
            "On-call assigned",
        ],
    }

    TIER_1_ADDITIONS = {
        "use_case": [
            "Human-in-the-loop strategy validated by safety team",
            "Regulatory compliance assessment complete",
            "Legal sign-off obtained",
            "Executive sponsor identified",
        ],
        "data": [
            "DPIA (Data Protection Impact Assessment) complete",
            "Cross-border data transfer assessment",
            "Data retention and deletion procedures verified",
            "Consent mechanisms validated",
            "Bias audit on training/RAG data complete",
        ],
        "architecture": [
            "Full ADR recorded",
            "Agent interaction patterns reviewed (A2A trust boundaries)",
            "Kill switch mechanism verified",
            "Cascade failure analysis complete",
            "Cost ceiling enforced at platform level",
        ],
        "evaluation": [
            "Adversarial evaluation complete (red team)",
            "Bias and fairness evaluation across protected groups",
            "Human evaluation protocol defined and staffed",
            "Continuous evaluation pipeline in production",
            "Edge case coverage verified",
        ],
        "security": [
            "Full threat model (STRIDE + AI-specific threats)",
            "Penetration testing complete",
            "Prompt injection testing complete",
            "Supply chain security audit",
            "Model poisoning risk assessment",
            "Incident response runbook (AI-specific)",
        ],
        "privacy": [
            "DPIA approved by DPO",
            "Transparency notice drafted",
            "Automated decision-making disclosure (Art. 22 GDPR)",
            "Right to explanation mechanism",
            "Data subject access request handling verified",
        ],
        "operations": [
            "Load testing at 2x expected peak",
            "Disaster recovery tested",
            "Runbooks for all identified failure modes",
            "Escalation procedures documented",
            "Post-launch review scheduled (30/60/90 days)",
            "Cost monitoring and alerting configured",
        ],
    }

    TIER_2_ADDITIONS = {
        "use_case": [
            "Human oversight mechanism defined",
            "Regulatory exposure documented",
        ],
        "data": [
            "Privacy classification complete",
            "Data minimization verified",
            "Consent coverage confirmed",
        ],
        "architecture": [
            "Integration patterns approved",
            "Tool blast radius documented",
        ],
        "evaluation": [
            "Adversarial test cases included",
            "Continuous eval sampling plan",
        ],
        "security": [
            "Threat model (lightweight)",
            "Prompt injection mitigations",
            "Access control review",
        ],
        "operations": [
            "Load testing at expected peak",
            "Runbooks for top 5 failure modes",
            "Cost budget approved",
        ],
    }

    @classmethod
    def generate(cls, tier: RiskTier, intake: UseCaseIntake) -> dict[str, list[dict]]:
        """Generate a checklist tailored to the risk tier and use case."""
        checklist = {}

        # Start with base checklist
        for section, items in cls.BASE_CHECKLIST.items():
            checklist[section] = [{"item": item, "status": "pending", "evidence": None, "reviewer": None}
                                  for item in items]

        # Add tier-specific items
        additions = {}
        if tier == RiskTier.CRITICAL:
            additions = cls.TIER_1_ADDITIONS
        elif tier == RiskTier.MEDIUM:
            additions = cls.TIER_2_ADDITIONS

        for section, items in additions.items():
            if section not in checklist:
                checklist[section] = []
            checklist[section].extend(
                [{"item": item, "status": "pending", "evidence": None, "reviewer": None}
                 for item in items]
            )

        # Add conditional items based on intake
        if intake.involves_a2a or intake.involves_autonomous_actions:
            checklist.setdefault("agent_safety", []).extend([
                {"item": "Agent trust boundaries defined", "status": "pending", "evidence": None, "reviewer": None},
                {"item": "Conversation depth limits set", "status": "pending", "evidence": None, "reviewer": None},
                {"item": "Cost caps per agent chain configured", "status": "pending", "evidence": None, "reviewer": None},
                {"item": "Human escalation triggers defined", "status": "pending", "evidence": None, "reviewer": None},
                {"item": "Emergency shutdown tested", "status": "pending", "evidence": None, "reviewer": None},
            ])

        if intake.mcp_servers:
            checklist.setdefault("mcp_security", []).extend([
                {"item": "MCP transport security (mTLS/OAuth)", "status": "pending", "evidence": None, "reviewer": None},
                {"item": "MCP capability scoping (minimal privileges)", "status": "pending", "evidence": None, "reviewer": None},
                {"item": "MCP input validation (schema enforcement)", "status": "pending", "evidence": None, "reviewer": None},
                {"item": "MCP resource limits configured", "status": "pending", "evidence": None, "reviewer": None},
            ])

        return checklist


# =============================================================================
# RISK CLASSIFICATION ENGINE
# =============================================================================

class RiskClassifier:
    """Classifies risk tier based on intake form and risk assessment."""

    # Automatic escalation rules (override scoring)
    PROHIBITED_INDICATORS = [
        "autonomous_weapons",
        "social_scoring",
        "mass_surveillance",
        "manipulation_vulnerable",
    ]

    AUTOMATIC_TIER_1_INDICATORS = [
        "involves_a2a",
        "can_cause_safety_harm",
    ]

    @classmethod
    def classify(cls, intake: UseCaseIntake, assessment: RiskAssessment) -> RiskTier:
        """Classify risk tier with automatic escalation rules."""

        # Check for prohibited use cases
        for indicator in cls.PROHIBITED_INDICATORS:
            if indicator in intake.problem_statement.lower():
                return RiskTier.PROHIBITED

        # Check for automatic Tier 1 escalation
        if intake.involves_a2a and intake.involves_autonomous_actions:
            return RiskTier.CRITICAL
        if intake.can_cause_safety_harm:
            return RiskTier.CRITICAL

        # Score-based classification
        tier = assessment.compute_tier()

        # Regulatory domains force minimum Tier 2
        if intake.regulatory_domains and tier == RiskTier.LOW:
            return RiskTier.MEDIUM

        return tier

    @classmethod
    def suggest_assessment(cls, intake: UseCaseIntake) -> RiskAssessment:
        """Suggest risk scores based on intake form indicators."""
        autonomy = 1
        if intake.involves_autonomous_actions:
            autonomy = 5
        elif not intake.human_in_loop_strategy:
            autonomy = 3

        data_sensitivity = 1
        if intake.involves_sensitive_data:
            data_sensitivity = 5
        elif intake.involves_pii:
            data_sensitivity = 3

        harm_potential = 1
        if intake.can_cause_safety_harm:
            harm_potential = 5
        elif intake.can_cause_financial_harm or intake.can_cause_legal_harm:
            harm_potential = 4
        elif intake.is_customer_facing:
            harm_potential = 2

        audience = 1
        if intake.user_type == "external":
            audience = 5
        elif intake.user_type == "both":
            audience = 4
        elif intake.user_type == "internal":
            audience = 2

        reversibility = 1
        if intake.involves_autonomous_actions:
            reversibility = 4
        if intake.can_cause_safety_harm:
            reversibility = 5

        return RiskAssessment(
            autonomy=autonomy,
            data_sensitivity=data_sensitivity,
            harm_potential=harm_potential,
            audience=audience,
            reversibility=reversibility,
            justifications={
                "autonomy": f"Score {autonomy}: Based on autonomous_actions={intake.involves_autonomous_actions}",
                "data_sensitivity": f"Score {data_sensitivity}: PII={intake.involves_pii}, sensitive={intake.involves_sensitive_data}",
                "harm_potential": f"Score {harm_potential}: safety={intake.can_cause_safety_harm}, financial={intake.can_cause_financial_harm}",
                "audience": f"Score {audience}: user_type={intake.user_type}",
                "reversibility": f"Score {reversibility}: autonomous={intake.involves_autonomous_actions}",
            }
        )


# =============================================================================
# STANDARDS COMPLIANCE CHECKER
# =============================================================================

@dataclass
class Standard:
    id: str
    title: str
    category: str
    severity: str  # required, recommended, optional
    check_fn: str  # Name of the check function
    description: str = ""


class ComplianceChecker:
    """Checks review requests against platform standards."""

    def __init__(self):
        self.standards: list[Standard] = self._load_default_standards()

    def _load_default_standards(self) -> list[Standard]:
        return [
            Standard("STD-SEC-001", "All AI endpoints require authentication", "security", "required", "check_auth"),
            Standard("STD-SEC-002", "Prompt injection mitigations required", "security", "required", "check_prompt_injection"),
            Standard("STD-OBS-001", "Distributed tracing required", "observability", "required", "check_tracing"),
            Standard("STD-OBS-002", "Token usage metrics required", "observability", "required", "check_token_metrics"),
            Standard("STD-EVL-001", "Evaluation suite required before production", "evaluation", "required", "check_eval_suite"),
            Standard("STD-EVL-002", "Regression threshold defined", "evaluation", "required", "check_regression_threshold"),
            Standard("STD-MDL-001", "Only approved models may be used", "model_usage", "required", "check_approved_models"),
            Standard("STD-MDL-002", "Model responses must be cached where appropriate", "model_usage", "recommended", "check_caching"),
            Standard("STD-DAT-001", "PII must be encrypted at rest", "data_handling", "required", "check_pii_encryption"),
            Standard("STD-DAT-002", "Data retention policy defined", "data_handling", "required", "check_retention"),
            Standard("STD-DEP-001", "Canary deployment required for Tier 1-2", "deployment", "required", "check_canary"),
            Standard("STD-DEP-002", "Feature flags for all new AI features", "deployment", "recommended", "check_feature_flags"),
            Standard("STD-CST-001", "Cost budget and alerts configured", "cost", "required", "check_cost_budget"),
            Standard("STD-AGT-001", "Agent tool invocations must be logged", "agent_design", "required", "check_tool_logging"),
            Standard("STD-AGT-002", "Agent conversation depth limits", "agent_design", "required", "check_depth_limits"),
        ]

    def check_compliance(self, review: ReviewRequest) -> list[dict]:
        """Run all applicable standards checks against a review request."""
        results = []
        for standard in self.standards:
            result = self._run_check(standard, review)
            results.append({
                "standard_id": standard.id,
                "title": standard.title,
                "severity": standard.severity,
                "status": result["status"],  # pass, fail, not_applicable, needs_review
                "details": result.get("details", ""),
            })
        return results

    def _run_check(self, standard: Standard, review: ReviewRequest) -> dict:
        """Run a single compliance check. In production, these would be actual automated checks."""
        intake = review.intake

        # Example automated checks based on intake data
        if standard.check_fn == "check_approved_models":
            approved = {"gpt-4o", "gpt-4o-mini", "claude-sonnet-4", "claude-haiku-35"}
            unapproved = [m for m in intake.models_considered if m.lower() not in approved]
            if unapproved:
                return {"status": "fail", "details": f"Unapproved models: {unapproved}"}
            if not intake.models_considered:
                return {"status": "needs_review", "details": "No models specified"}
            return {"status": "pass"}

        if standard.check_fn == "check_pii_encryption":
            if not intake.involves_pii:
                return {"status": "not_applicable"}
            return {"status": "needs_review", "details": "Manual verification required for PII encryption"}

        if standard.check_fn == "check_depth_limits":
            if not intake.involves_a2a and not intake.involves_autonomous_actions:
                return {"status": "not_applicable"}
            return {"status": "needs_review", "details": "Verify agent depth limits are configured"}

        if standard.check_fn == "check_canary":
            if review.risk_tier == RiskTier.LOW:
                return {"status": "not_applicable"}
            return {"status": "needs_review", "details": "Verify canary deployment strategy"}

        # Default: needs manual review
        return {"status": "needs_review", "details": "Automated check not implemented"}


# =============================================================================
# REVIEW BOARD SERVICE
# =============================================================================

class ReviewBoardStore(ABC):
    """Abstract storage for review board data."""

    @abstractmethod
    def save_review(self, review: ReviewRequest) -> None: ...

    @abstractmethod
    def get_review(self, review_id: str) -> Optional[ReviewRequest]: ...

    @abstractmethod
    def list_reviews(self, status: Optional[ReviewStatus] = None) -> list[ReviewRequest]: ...

    @abstractmethod
    def search_reviews(self, query: str) -> list[ReviewRequest]: ...


class InMemoryReviewStore(ReviewBoardStore):
    """In-memory implementation for demonstration."""

    def __init__(self):
        self._reviews: dict[str, ReviewRequest] = {}

    def save_review(self, review: ReviewRequest) -> None:
        review.updated_at = datetime.utcnow().isoformat()
        self._reviews[review.id] = review

    def get_review(self, review_id: str) -> Optional[ReviewRequest]:
        return self._reviews.get(review_id)

    def list_reviews(self, status: Optional[ReviewStatus] = None) -> list[ReviewRequest]:
        reviews = list(self._reviews.values())
        if status:
            reviews = [r for r in reviews if r.status == status]
        return sorted(reviews, key=lambda r: r.created_at, reverse=True)

    def search_reviews(self, query: str) -> list[ReviewRequest]:
        query_lower = query.lower()
        results = []
        for review in self._reviews.values():
            if (query_lower in review.intake.title.lower() or
                query_lower in review.intake.problem_statement.lower() or
                query_lower in review.intake.team.lower()):
                results.append(review)
        return results


class ReviewBoardService:
    """
    Main service orchestrating the AI Architecture Review Board process.
    """

    def __init__(self, store: Optional[ReviewBoardStore] = None):
        self.store = store or InMemoryReviewStore()
        self.compliance_checker = ComplianceChecker()
        self._reviewer_pool: dict[ReviewerRole, list[str]] = {}

    def register_reviewer(self, role: ReviewerRole, reviewer_id: str) -> None:
        """Register a reviewer for a given role."""
        self._reviewer_pool.setdefault(role, []).append(reviewer_id)

    # -------------------------------------------------------------------------
    # INTAKE
    # -------------------------------------------------------------------------

    def submit_intake(self, intake: UseCaseIntake) -> ReviewRequest:
        """Submit a new use-case intake form, creating a review request."""
        intake.submitted_at = datetime.utcnow().isoformat()

        review = ReviewRequest(
            intake=intake,
            status=ReviewStatus.SUBMITTED,
        )
        self.store.save_review(review)
        return review

    # -------------------------------------------------------------------------
    # TRIAGE & RISK CLASSIFICATION
    # -------------------------------------------------------------------------

    def triage_review(self, review_id: str, override_tier: Optional[RiskTier] = None) -> ReviewRequest:
        """Triage a submitted review: classify risk, assign reviewers, generate checklist."""
        review = self.store.get_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        if review.status != ReviewStatus.SUBMITTED:
            raise ValueError(f"Review must be in SUBMITTED state, got {review.status}")

        # Risk assessment
        assessment = RiskClassifier.suggest_assessment(review.intake)
        review.risk_assessment = assessment

        # Risk tier
        tier = override_tier or RiskClassifier.classify(review.intake, assessment)
        review.risk_tier = tier

        # Handle prohibited
        if tier == RiskTier.PROHIBITED:
            review.status = ReviewStatus.REJECTED
            review.decision = ReviewDecision(
                status=ReviewStatus.REJECTED,
                decided_by="system",
                decided_at=datetime.utcnow().isoformat(),
                rejection_reasons=["Use case classified as PROHIBITED per organizational policy"],
            )
            self.store.save_review(review)
            return review

        # Assign reviewers
        required_roles = TIER_REVIEWER_REQUIREMENTS.get(tier, [])
        for role in required_roles:
            reviewers = self._reviewer_pool.get(role, [])
            if reviewers:
                # Simple round-robin; production would consider workload
                review.assigned_reviewers.append(reviewers[0])

        # Generate checklist
        review.checklist = ChecklistGenerator.generate(tier, review.intake)

        # Set SLA
        sla_days = REVIEW_SLA_DAYS.get(tier, 5)
        review.sla_deadline = (datetime.utcnow() + timedelta(days=sla_days)).isoformat()

        # Low-risk: auto-approve if compliance passes
        if tier == RiskTier.LOW:
            compliance_results = self.compliance_checker.check_compliance(review)
            failures = [r for r in compliance_results if r["status"] == "fail"]
            if not failures:
                review.status = ReviewStatus.APPROVED
                review.decision = ReviewDecision(
                    status=ReviewStatus.APPROVED,
                    decided_by="automated",
                    decided_at=datetime.utcnow().isoformat(),
                )
            else:
                review.status = ReviewStatus.TRIAGED
        else:
            review.status = ReviewStatus.TRIAGED

        self.store.save_review(review)
        return review

    # -------------------------------------------------------------------------
    # REVIEW WORKFLOW
    # -------------------------------------------------------------------------

    def start_review(self, review_id: str) -> ReviewRequest:
        """Move review from triaged to in-review."""
        review = self.store.get_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        review.status = ReviewStatus.IN_REVIEW
        self.store.save_review(review)
        return review

    def add_comment(self, review_id: str, comment: ReviewComment) -> ReviewRequest:
        """Add a reviewer comment to the review."""
        review = self.store.get_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        review.comments.append(comment)
        self.store.save_review(review)
        return review

    def update_checklist_item(self, review_id: str, section: str, item_index: int,
                              status: str, evidence: Optional[str] = None,
                              reviewer: Optional[str] = None) -> ReviewRequest:
        """Update a checklist item status."""
        review = self.store.get_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        if section in review.checklist and item_index < len(review.checklist[section]):
            review.checklist[section][item_index]["status"] = status
            if evidence:
                review.checklist[section][item_index]["evidence"] = evidence
            if reviewer:
                review.checklist[section][item_index]["reviewer"] = reviewer
        self.store.save_review(review)
        return review

    def make_decision(self, review_id: str, decision: ReviewDecision) -> ReviewRequest:
        """Record the final decision on a review."""
        review = self.store.get_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Validate: all blocker comments must be resolved
        unresolved_blockers = [c for c in review.comments
                               if c.severity == "blocker" and not c.resolved]
        if unresolved_blockers and decision.status == ReviewStatus.APPROVED:
            raise ValueError(f"Cannot approve with {len(unresolved_blockers)} unresolved blockers")

        review.decision = decision
        review.status = decision.status
        decision.decided_at = datetime.utcnow().isoformat()
        self.store.save_review(review)
        return review

    # -------------------------------------------------------------------------
    # ESCALATION
    # -------------------------------------------------------------------------

    def escalate(self, review_id: str, reason: str) -> ReviewRequest:
        """Escalate a review (e.g., SLA breach, disagreement among reviewers)."""
        review = self.store.get_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        review.escalated = True
        review.escalation_reason = reason

        # Add chief architect if not already assigned
        chief_reviewers = self._reviewer_pool.get(ReviewerRole.CHIEF_AI_ARCHITECT, [])
        for r in chief_reviewers:
            if r not in review.assigned_reviewers:
                review.assigned_reviewers.append(r)

        self.store.save_review(review)
        return review

    def check_sla_breaches(self) -> list[ReviewRequest]:
        """Find reviews that have breached their SLA."""
        now = datetime.utcnow()
        breached = []
        active_statuses = {ReviewStatus.TRIAGED, ReviewStatus.IN_REVIEW, ReviewStatus.PENDING_DISCUSSION}
        for review in self.store.list_reviews():
            if review.status in active_statuses and review.sla_deadline:
                deadline = datetime.fromisoformat(review.sla_deadline)
                if now > deadline and not review.escalated:
                    self.escalate(review.id, f"SLA breach: deadline was {review.sla_deadline}")
                    breached.append(review)
        return breached

    # -------------------------------------------------------------------------
    # COMPLIANCE & SEARCH
    # -------------------------------------------------------------------------

    def run_compliance_check(self, review_id: str) -> list[dict]:
        """Run standards compliance checks against a review."""
        review = self.store.get_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        return self.compliance_checker.check_compliance(review)

    def search(self, query: str) -> list[ReviewRequest]:
        """Search review history."""
        return self.store.search_reviews(query)

    def get_review_summary(self, review_id: str) -> dict:
        """Get a summary of a review's current state."""
        review = self.store.get_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Checklist progress
        total_items = sum(len(items) for items in review.checklist.values())
        completed_items = sum(
            1 for items in review.checklist.values()
            for item in items if item["status"] in ("pass", "not_applicable")
        )

        return {
            "id": review.id,
            "title": review.intake.title,
            "status": review.status.value,
            "risk_tier": review.risk_tier.value if review.risk_tier else None,
            "risk_score": review.risk_assessment.weighted_score() if review.risk_assessment else None,
            "checklist_progress": f"{completed_items}/{total_items}",
            "comments_count": len(review.comments),
            "blockers": len([c for c in review.comments if c.severity == "blocker" and not c.resolved]),
            "assigned_reviewers": len(review.assigned_reviewers),
            "sla_deadline": review.sla_deadline,
            "escalated": review.escalated,
        }


# =============================================================================
# DEMONSTRATION
# =============================================================================

def demo():
    """Demonstrate the review board system."""
    print("=" * 70)
    print("AI ARCHITECTURE REVIEW BOARD - DEMONSTRATION")
    print("=" * 70)

    # Initialize service
    service = ReviewBoardService()
    service.register_reviewer(ReviewerRole.CHIEF_AI_ARCHITECT, "alice@company.com")
    service.register_reviewer(ReviewerRole.SECURITY_ARCHITECT, "bob@company.com")
    service.register_reviewer(ReviewerRole.ML_ENGINEERING_LEAD, "carol@company.com")
    service.register_reviewer(ReviewerRole.AI_SAFETY_LEAD, "dave@company.com")
    service.register_reviewer(ReviewerRole.DATA_GOVERNANCE_LEAD, "eve@company.com")
    service.register_reviewer(ReviewerRole.LEGAL_COMPLIANCE, "frank@company.com")
    service.register_reviewer(ReviewerRole.PLATFORM_ENGINEERING, "grace@company.com")

    # --- Example 1: High-risk autonomous agent ---
    print("\n--- Example 1: Autonomous Trading Agent (Expected: Tier 1) ---")
    intake1 = UseCaseIntake(
        title="Autonomous Trading Signal Agent",
        submitter="trader_team_lead",
        team="Quantitative Trading",
        problem_statement="Automated analysis and execution of trading signals using AI agents",
        target_users="Trading desk",
        user_type="internal",
        expected_impact="Reduce signal-to-trade latency by 80%",
        failure_consequences="Significant financial loss, regulatory exposure",
        human_in_loop_strategy="Human approval for trades > $1M",
        ai_capabilities_needed=["generation", "classification", "agent"],
        models_considered=["gpt-4o", "claude-sonnet-4"],
        involves_autonomous_actions=True,
        involves_a2a=True,
        can_cause_financial_harm=True,
        regulatory_domains=["SEC", "FINRA"],
        tools_required=["market_data_api", "order_execution", "risk_calculator"],
    )

    review1 = service.submit_intake(intake1)
    review1 = service.triage_review(review1.id)
    summary1 = service.get_review_summary(review1.id)
    print(f"  Title: {summary1['title']}")
    print(f"  Risk Tier: {summary1['risk_tier']} (1=Critical)")
    print(f"  Risk Score: {summary1['risk_score']:.2f}")
    print(f"  Status: {summary1['status']}")
    print(f"  Checklist Items: {summary1['checklist_progress']}")
    print(f"  Assigned Reviewers: {summary1['assigned_reviewers']}")

    # --- Example 2: Low-risk internal tool ---
    print("\n--- Example 2: Internal Doc Summarizer (Expected: Tier 3) ---")
    intake2 = UseCaseIntake(
        title="Internal Documentation Summarizer",
        submitter="devex_engineer",
        team="Developer Experience",
        problem_statement="Summarize internal wiki pages for quick consumption",
        target_users="All engineers",
        user_type="internal",
        expected_impact="Save 30 min/day per engineer on documentation reading",
        failure_consequences="Minor: engineer reads wrong summary, goes to source",
        human_in_loop_strategy="Summaries always link to source for verification",
        ai_capabilities_needed=["generation"],
        models_considered=["gpt-4o-mini"],
        involves_pii=False,
        is_customer_facing=False,
    )

    review2 = service.submit_intake(intake2)
    review2 = service.triage_review(review2.id)
    summary2 = service.get_review_summary(review2.id)
    print(f"  Title: {summary2['title']}")
    print(f"  Risk Tier: {summary2['risk_tier']} (3=Low)")
    print(f"  Risk Score: {summary2['risk_score']:.2f}")
    print(f"  Status: {summary2['status']}")

    # --- Example 3: Medium-risk customer chatbot ---
    print("\n--- Example 3: Customer Support Chatbot (Expected: Tier 2) ---")
    intake3 = UseCaseIntake(
        title="Customer Support AI Assistant",
        submitter="support_manager",
        team="Customer Success",
        problem_statement="AI chatbot to handle L1 customer queries",
        target_users="External customers",
        user_type="external",
        expected_impact="Reduce support ticket volume by 40%",
        failure_consequences="Customer frustration, brand damage, potential data leak",
        human_in_loop_strategy="Escalate to human after 2 failed attempts or on sensitive topics",
        ai_capabilities_needed=["generation", "classification", "extraction"],
        models_considered=["gpt-4o"],
        involves_pii=True,
        is_customer_facing=True,
        can_cause_financial_harm=False,
    )

    review3 = service.submit_intake(intake3)
    review3 = service.triage_review(review3.id)
    summary3 = service.get_review_summary(review3.id)
    print(f"  Title: {summary3['title']}")
    print(f"  Risk Tier: {summary3['risk_tier']} (2=Medium)")
    print(f"  Risk Score: {summary3['risk_score']:.2f}")
    print(f"  Status: {summary3['status']}")
    print(f"  Checklist Items: {summary3['checklist_progress']}")

    # --- Compliance check ---
    print("\n--- Compliance Check for Trading Agent ---")
    compliance = service.run_compliance_check(review1.id)
    for result in compliance[:5]:
        print(f"  [{result['status']:>12}] {result['standard_id']}: {result['title']}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    demo()
