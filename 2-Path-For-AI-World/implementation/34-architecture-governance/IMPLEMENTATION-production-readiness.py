"""
Production Readiness Gate System

Comprehensive production readiness assessment for AI systems:
- Multi-category readiness checklist
- Automated evidence collection
- Readiness scoring and gap analysis
- Remediation tracking
- Final approval workflow
- Post-launch review scheduling
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable
from abc import ABC, abstractmethod


# =============================================================================
# ENUMS
# =============================================================================

class ReadinessCategory(Enum):
    USE_CASE = "use_case"
    RISK_GOVERNANCE = "risk_governance"
    DATA = "data"
    MODEL_PROMPT = "model_prompt"
    EVALUATION = "evaluation"
    GUARDRAILS = "guardrails"
    OBSERVABILITY = "observability"
    SECURITY = "security"
    PRIVACY = "privacy"
    COST = "cost"
    DEPLOYMENT = "deployment"
    OPERATIONS = "operations"
    DOCUMENTATION = "documentation"

class CheckStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"
    NOT_APPLICABLE = "not_applicable"

class EvidenceType(Enum):
    AUTOMATED = "automated"    # Collected by system
    MANUAL = "manual"          # Requires human input
    LINK = "link"              # URL to external evidence
    ATTESTATION = "attestation"  # Human attestation

class ReadinessLevel(Enum):
    NOT_READY = "not_ready"       # < 60% passing
    PARTIALLY_READY = "partially_ready"  # 60-85%
    READY = "ready"               # 85-95%
    FULLY_READY = "fully_ready"   # > 95%

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Evidence:
    """Evidence supporting a readiness check."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: EvidenceType = EvidenceType.MANUAL
    description: str = ""
    value: str = ""  # URL, metric value, attestation text
    collected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    collected_by: str = ""  # system or person
    expires_at: Optional[str] = None  # Some evidence has a shelf life


@dataclass
class ReadinessCheck:
    """A single readiness check item."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: ReadinessCategory = ReadinessCategory.USE_CASE
    title: str = ""
    description: str = ""
    required: bool = True  # Required vs recommended
    evidence_type: EvidenceType = EvidenceType.MANUAL
    status: CheckStatus = CheckStatus.NOT_STARTED
    evidence: list[Evidence] = field(default_factory=list)
    notes: str = ""
    weight: float = 1.0  # Relative importance within category
    automated_check_fn: Optional[str] = None  # Function name for automated checks
    waiver_reason: Optional[str] = None
    waiver_approved_by: Optional[str] = None


@dataclass
class RemediationItem:
    """A gap that needs to be fixed before production."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    check_id: str = ""
    title: str = ""
    description: str = ""
    priority: str = "medium"  # critical, high, medium, low
    assignee: str = ""
    status: str = "open"  # open, in_progress, resolved, wont_fix
    due_date: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    resolved_at: Optional[str] = None
    resolution_notes: str = ""


@dataclass
class ReadinessApproval:
    """Approval decision for production readiness."""
    approver: str = ""
    role: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    conditions: list[str] = field(default_factory=list)
    comments: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PostLaunchReview:
    """Scheduled post-launch review."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scheduled_date: str = ""
    review_type: str = ""  # 7-day, 30-day, 90-day
    status: str = "scheduled"  # scheduled, completed, overdue
    findings: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass
class ProductionReadinessAssessment:
    """Complete production readiness assessment for an AI system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_name: str = ""
    system_id: str = ""  # Reference to review board request
    risk_tier: int = 3
    owner: str = ""
    team: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Checks
    checks: list[ReadinessCheck] = field(default_factory=list)

    # Gaps
    remediations: list[RemediationItem] = field(default_factory=list)

    # Scoring
    overall_score: float = 0.0
    category_scores: dict[str, float] = field(default_factory=dict)
    readiness_level: ReadinessLevel = ReadinessLevel.NOT_READY

    # Approval
    approvals: list[ReadinessApproval] = field(default_factory=list)
    final_status: ApprovalStatus = ApprovalStatus.PENDING

    # Post-launch
    launch_date: Optional[str] = None
    post_launch_reviews: list[PostLaunchReview] = field(default_factory=list)


# =============================================================================
# CHECKLIST DEFINITIONS
# =============================================================================

PRODUCTION_READINESS_CHECKLIST: dict[ReadinessCategory, list[dict]] = {
    ReadinessCategory.USE_CASE: [
        {"title": "Use case approved by review board", "evidence_type": "link", "required": True},
        {"title": "Business success criteria defined and measurable", "evidence_type": "manual", "required": True},
        {"title": "User acceptance testing completed", "evidence_type": "link", "required": True},
        {"title": "Stakeholder sign-off obtained", "evidence_type": "attestation", "required": True},
    ],
    ReadinessCategory.RISK_GOVERNANCE: [
        {"title": "Risk tier classification documented", "evidence_type": "link", "required": True},
        {"title": "All review gates passed for assigned tier", "evidence_type": "automated", "required": True},
        {"title": "ADR recorded for key architectural decisions", "evidence_type": "link", "required": True},
        {"title": "Regulatory compliance assessment complete", "evidence_type": "manual", "required": True},
        {"title": "Risk acceptance signed by appropriate level", "evidence_type": "attestation", "required": True},
    ],
    ReadinessCategory.DATA: [
        {"title": "All data sources approved and documented", "evidence_type": "link", "required": True},
        {"title": "Data quality metrics meet thresholds", "evidence_type": "automated", "required": True},
        {"title": "Data freshness SLOs defined", "evidence_type": "manual", "required": True},
        {"title": "Data lineage documented end-to-end", "evidence_type": "link", "required": True},
        {"title": "Data backup and recovery tested", "evidence_type": "manual", "required": True},
        {"title": "PII handling verified (encryption, masking)", "evidence_type": "automated", "required": True},
    ],
    ReadinessCategory.MODEL_PROMPT: [
        {"title": "Model approved from registry", "evidence_type": "automated", "required": True},
        {"title": "System prompts version-controlled", "evidence_type": "automated", "required": True},
        {"title": "Prompt injection mitigations tested", "evidence_type": "link", "required": True},
        {"title": "Model fallback strategy defined", "evidence_type": "manual", "required": True},
        {"title": "Token usage within budget projections", "evidence_type": "automated", "required": True},
        {"title": "Response caching strategy implemented", "evidence_type": "manual", "required": False},
    ],
    ReadinessCategory.EVALUATION: [
        {"title": "Evaluation suite covers all critical paths", "evidence_type": "automated", "required": True},
        {"title": "Baseline metrics recorded and versioned", "evidence_type": "automated", "required": True},
        {"title": "Regression threshold defined (auto-block on breach)", "evidence_type": "automated", "required": True},
        {"title": "Adversarial/red-team evaluation completed", "evidence_type": "link", "required": True},
        {"title": "Human evaluation protocol defined", "evidence_type": "manual", "required": True},
        {"title": "Continuous production evaluation configured", "evidence_type": "automated", "required": True},
        {"title": "Bias and fairness evaluation passed", "evidence_type": "link", "required": True},
    ],
    ReadinessCategory.GUARDRAILS: [
        {"title": "Input validation and sanitization active", "evidence_type": "automated", "required": True},
        {"title": "Output filtering configured (PII, harmful content)", "evidence_type": "automated", "required": True},
        {"title": "Rate limiting configured per user/tenant", "evidence_type": "automated", "required": True},
        {"title": "Token/cost limits enforced per request", "evidence_type": "automated", "required": True},
        {"title": "Conversation depth limits for agents", "evidence_type": "automated", "required": True},
        {"title": "Human escalation triggers tested", "evidence_type": "manual", "required": True},
        {"title": "Kill switch mechanism verified", "evidence_type": "manual", "required": True},
    ],
    ReadinessCategory.OBSERVABILITY: [
        {"title": "Distributed tracing configured (all LLM calls)", "evidence_type": "automated", "required": True},
        {"title": "Key metrics dashboards created", "evidence_type": "link", "required": True},
        {"title": "Alerting configured for SLO breaches", "evidence_type": "automated", "required": True},
        {"title": "Token usage and cost tracking active", "evidence_type": "automated", "required": True},
        {"title": "Quality metrics tracked (eval scores in prod)", "evidence_type": "automated", "required": True},
        {"title": "Log retention meets compliance requirements", "evidence_type": "manual", "required": True},
        {"title": "Anomaly detection configured", "evidence_type": "automated", "required": False},
    ],
    ReadinessCategory.SECURITY: [
        {"title": "Authentication configured for all endpoints", "evidence_type": "automated", "required": True},
        {"title": "Authorization (RBAC/ABAC) verified", "evidence_type": "automated", "required": True},
        {"title": "Secrets managed via vault (no hardcoded)", "evidence_type": "automated", "required": True},
        {"title": "Network security (TLS, segmentation)", "evidence_type": "automated", "required": True},
        {"title": "Dependency vulnerability scan passed", "evidence_type": "automated", "required": True},
        {"title": "Penetration testing completed", "evidence_type": "link", "required": True},
        {"title": "Incident response plan documented", "evidence_type": "link", "required": True},
    ],
    ReadinessCategory.PRIVACY: [
        {"title": "Privacy impact assessment complete", "evidence_type": "link", "required": True},
        {"title": "Data minimization verified", "evidence_type": "manual", "required": True},
        {"title": "User consent mechanisms working", "evidence_type": "manual", "required": True},
        {"title": "Data subject rights (access/delete) tested", "evidence_type": "manual", "required": True},
        {"title": "Transparency notice published", "evidence_type": "link", "required": True},
        {"title": "Cross-border transfer compliance", "evidence_type": "manual", "required": True},
    ],
    ReadinessCategory.COST: [
        {"title": "Monthly cost projection documented", "evidence_type": "manual", "required": True},
        {"title": "Budget approved by finance", "evidence_type": "attestation", "required": True},
        {"title": "Cost alerts configured (50%, 80%, 100%)", "evidence_type": "automated", "required": True},
        {"title": "Cost optimization strategy documented", "evidence_type": "manual", "required": False},
        {"title": "Chargeback/showback model defined", "evidence_type": "manual", "required": False},
    ],
    ReadinessCategory.DEPLOYMENT: [
        {"title": "CI/CD pipeline configured and tested", "evidence_type": "automated", "required": True},
        {"title": "Canary/progressive deployment strategy", "evidence_type": "manual", "required": True},
        {"title": "Rollback mechanism tested", "evidence_type": "manual", "required": True},
        {"title": "Feature flags configured", "evidence_type": "automated", "required": True},
        {"title": "Blue/green or shadow deployment ready", "evidence_type": "manual", "required": False},
        {"title": "Load testing completed at 2x expected peak", "evidence_type": "link", "required": True},
    ],
    ReadinessCategory.OPERATIONS: [
        {"title": "SLOs defined (latency, availability, quality)", "evidence_type": "manual", "required": True},
        {"title": "On-call rotation assigned", "evidence_type": "manual", "required": True},
        {"title": "Runbooks for top failure modes written", "evidence_type": "link", "required": True},
        {"title": "Escalation path documented", "evidence_type": "manual", "required": True},
        {"title": "Capacity planning documented", "evidence_type": "manual", "required": True},
        {"title": "Dependency health monitoring active", "evidence_type": "automated", "required": True},
    ],
    ReadinessCategory.DOCUMENTATION: [
        {"title": "Architecture documentation up to date", "evidence_type": "link", "required": True},
        {"title": "API documentation published", "evidence_type": "link", "required": True},
        {"title": "User-facing documentation/help", "evidence_type": "link", "required": True},
        {"title": "Known limitations documented", "evidence_type": "manual", "required": True},
        {"title": "Training materials for support team", "evidence_type": "link", "required": False},
    ],
}


# =============================================================================
# PRODUCTION READINESS SERVICE
# =============================================================================

class ProductionReadinessService:
    """Manages production readiness assessments."""

    def __init__(self):
        self._assessments: dict[str, ProductionReadinessAssessment] = {}

    # -------------------------------------------------------------------------
    # CREATION
    # -------------------------------------------------------------------------

    def create_assessment(self, system_name: str, system_id: str, risk_tier: int,
                          owner: str, team: str) -> ProductionReadinessAssessment:
        """Create a new production readiness assessment with full checklist."""
        assessment = ProductionReadinessAssessment(
            system_name=system_name,
            system_id=system_id,
            risk_tier=risk_tier,
            owner=owner,
            team=team,
        )

        # Generate checks from checklist
        for category, items in PRODUCTION_READINESS_CHECKLIST.items():
            for item_def in items:
                # Skip optional items for low-risk
                if risk_tier == 3 and not item_def.get("required", True):
                    continue
                check = ReadinessCheck(
                    category=category,
                    title=item_def["title"],
                    evidence_type=EvidenceType(item_def["evidence_type"]),
                    required=item_def.get("required", True),
                )
                assessment.checks.append(check)

        self._assessments[assessment.id] = assessment
        return assessment

    # -------------------------------------------------------------------------
    # EVIDENCE COLLECTION
    # -------------------------------------------------------------------------

    def submit_evidence(self, assessment_id: str, check_id: str,
                        evidence: Evidence) -> ProductionReadinessAssessment:
        """Submit evidence for a readiness check."""
        assessment = self._get_or_raise(assessment_id)
        check = self._find_check(assessment, check_id)
        check.evidence.append(evidence)
        check.status = CheckStatus.IN_PROGRESS
        self._recalculate_scores(assessment)
        return assessment

    def mark_check(self, assessment_id: str, check_id: str, status: CheckStatus,
                   notes: str = "") -> ProductionReadinessAssessment:
        """Mark a check as passed/failed/waived."""
        assessment = self._get_or_raise(assessment_id)
        check = self._find_check(assessment, check_id)
        check.status = status
        if notes:
            check.notes = notes
        self._recalculate_scores(assessment)
        return assessment

    def waive_check(self, assessment_id: str, check_id: str, reason: str,
                    approved_by: str) -> ProductionReadinessAssessment:
        """Waive a check with documented reason and approval."""
        assessment = self._get_or_raise(assessment_id)
        check = self._find_check(assessment, check_id)
        check.status = CheckStatus.WAIVED
        check.waiver_reason = reason
        check.waiver_approved_by = approved_by
        self._recalculate_scores(assessment)
        return assessment

    def run_automated_checks(self, assessment_id: str) -> dict[str, str]:
        """Run all automated checks and collect evidence.
        In production, this would call actual verification systems."""
        assessment = self._get_or_raise(assessment_id)
        results = {}

        for check in assessment.checks:
            if check.evidence_type != EvidenceType.AUTOMATED:
                continue

            # Simulate automated checks
            result = self._simulate_automated_check(check)
            check.status = CheckStatus.PASSED if result["passed"] else CheckStatus.FAILED
            check.evidence.append(Evidence(
                type=EvidenceType.AUTOMATED,
                description=f"Automated check: {check.title}",
                value=result["details"],
                collected_by="system",
            ))
            results[check.id] = result["details"]

        self._recalculate_scores(assessment)
        return results

    def _simulate_automated_check(self, check: ReadinessCheck) -> dict:
        """Simulate an automated check. Replace with real integrations."""
        # In production: query monitoring systems, scan configs, verify deployments
        return {
            "passed": True,  # Simulated pass
            "details": f"[SIMULATED] Check '{check.title}' passed automated verification",
        }

    # -------------------------------------------------------------------------
    # SCORING & GAP ANALYSIS
    # -------------------------------------------------------------------------

    def _recalculate_scores(self, assessment: ProductionReadinessAssessment) -> None:
        """Recalculate readiness scores."""
        category_checks: dict[str, list[ReadinessCheck]] = {}
        for check in assessment.checks:
            cat = check.category.value
            category_checks.setdefault(cat, []).append(check)

        total_weight = 0.0
        total_score = 0.0

        for cat, checks in category_checks.items():
            cat_weight = sum(c.weight for c in checks if c.required)
            cat_score = sum(
                c.weight for c in checks
                if c.status in (CheckStatus.PASSED, CheckStatus.WAIVED, CheckStatus.NOT_APPLICABLE)
            )
            if cat_weight > 0:
                assessment.category_scores[cat] = round(cat_score / cat_weight * 100, 1)
            total_weight += cat_weight
            total_score += cat_score

        assessment.overall_score = round(total_score / total_weight * 100, 1) if total_weight > 0 else 0.0

        # Determine readiness level
        if assessment.overall_score >= 95:
            assessment.readiness_level = ReadinessLevel.FULLY_READY
        elif assessment.overall_score >= 85:
            assessment.readiness_level = ReadinessLevel.READY
        elif assessment.overall_score >= 60:
            assessment.readiness_level = ReadinessLevel.PARTIALLY_READY
        else:
            assessment.readiness_level = ReadinessLevel.NOT_READY

    def get_gaps(self, assessment_id: str) -> list[dict]:
        """Identify all gaps (failed or not-started required checks)."""
        assessment = self._get_or_raise(assessment_id)
        gaps = []
        for check in assessment.checks:
            if check.required and check.status in (CheckStatus.NOT_STARTED, CheckStatus.FAILED):
                gaps.append({
                    "check_id": check.id,
                    "category": check.category.value,
                    "title": check.title,
                    "status": check.status.value,
                    "evidence_type": check.evidence_type.value,
                    "priority": "critical" if check.category in (
                        ReadinessCategory.SECURITY, ReadinessCategory.GUARDRAILS
                    ) else "high",
                })
        return sorted(gaps, key=lambda g: {"critical": 0, "high": 1, "medium": 2}[g["priority"]])

    # -------------------------------------------------------------------------
    # REMEDIATION
    # -------------------------------------------------------------------------

    def create_remediation(self, assessment_id: str, check_id: str,
                           title: str, assignee: str, due_date: str,
                           priority: str = "medium") -> RemediationItem:
        """Create a remediation item for a gap."""
        assessment = self._get_or_raise(assessment_id)
        item = RemediationItem(
            check_id=check_id,
            title=title,
            assignee=assignee,
            priority=priority,
            due_date=due_date,
        )
        assessment.remediations.append(item)
        self._assessments[assessment_id] = assessment
        return item

    def resolve_remediation(self, assessment_id: str, remediation_id: str,
                            notes: str) -> RemediationItem:
        """Mark a remediation as resolved."""
        assessment = self._get_or_raise(assessment_id)
        for item in assessment.remediations:
            if item.id == remediation_id:
                item.status = "resolved"
                item.resolved_at = datetime.utcnow().isoformat()
                item.resolution_notes = notes
                self._assessments[assessment_id] = assessment
                return item
        raise ValueError(f"Remediation {remediation_id} not found")

    # -------------------------------------------------------------------------
    # APPROVAL
    # -------------------------------------------------------------------------

    def submit_approval(self, assessment_id: str, approval: ReadinessApproval) -> ProductionReadinessAssessment:
        """Submit an approval decision."""
        assessment = self._get_or_raise(assessment_id)

        # Validate: no critical gaps if approving
        if approval.status == ApprovalStatus.APPROVED:
            gaps = self.get_gaps(assessment_id)
            critical_gaps = [g for g in gaps if g["priority"] == "critical"]
            if critical_gaps:
                raise ValueError(f"Cannot approve with {len(critical_gaps)} critical gaps")

        assessment.approvals.append(approval)

        # Check if all required approvals are in
        approved_count = sum(1 for a in assessment.approvals if a.status == ApprovalStatus.APPROVED)
        required_approvals = 2 if assessment.risk_tier <= 2 else 1

        if approved_count >= required_approvals:
            assessment.final_status = ApprovalStatus.APPROVED
            assessment.launch_date = datetime.utcnow().isoformat()
            self._schedule_post_launch_reviews(assessment)

        self._assessments[assessment_id] = assessment
        return assessment

    def _schedule_post_launch_reviews(self, assessment: ProductionReadinessAssessment) -> None:
        """Schedule post-launch reviews at 7, 30, and 90 days."""
        launch = datetime.utcnow()
        for days, review_type in [(7, "7-day"), (30, "30-day"), (90, "90-day")]:
            assessment.post_launch_reviews.append(PostLaunchReview(
                scheduled_date=(launch + timedelta(days=days)).isoformat(),
                review_type=review_type,
            ))

    # -------------------------------------------------------------------------
    # REPORTING
    # -------------------------------------------------------------------------

    def get_summary(self, assessment_id: str) -> dict:
        """Get assessment summary."""
        assessment = self._get_or_raise(assessment_id)
        total = len(assessment.checks)
        passed = sum(1 for c in assessment.checks if c.status == CheckStatus.PASSED)
        failed = sum(1 for c in assessment.checks if c.status == CheckStatus.FAILED)
        pending = sum(1 for c in assessment.checks if c.status == CheckStatus.NOT_STARTED)
        waived = sum(1 for c in assessment.checks if c.status == CheckStatus.WAIVED)

        return {
            "system_name": assessment.system_name,
            "risk_tier": assessment.risk_tier,
            "overall_score": assessment.overall_score,
            "readiness_level": assessment.readiness_level.value,
            "checks": {"total": total, "passed": passed, "failed": failed, "pending": pending, "waived": waived},
            "category_scores": assessment.category_scores,
            "open_remediations": sum(1 for r in assessment.remediations if r.status == "open"),
            "final_status": assessment.final_status.value,
            "gaps_count": len(self.get_gaps(assessment_id)),
        }

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _get_or_raise(self, assessment_id: str) -> ProductionReadinessAssessment:
        assessment = self._assessments.get(assessment_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")
        return assessment

    def _find_check(self, assessment: ProductionReadinessAssessment, check_id: str) -> ReadinessCheck:
        for check in assessment.checks:
            if check.id == check_id:
                return check
        raise ValueError(f"Check {check_id} not found")


# =============================================================================
# DEMONSTRATION
# =============================================================================

def demo():
    print("=" * 70)
    print("PRODUCTION READINESS GATE - DEMONSTRATION")
    print("=" * 70)

    service = ProductionReadinessService()

    # Create assessment for a Tier 2 system
    print("\n--- Creating assessment for Customer Support Chatbot (Tier 2) ---")
    assessment = service.create_assessment(
        system_name="Customer Support AI Assistant",
        system_id="review-12345",
        risk_tier=2,
        owner="support_manager@company.com",
        team="Customer Success",
    )

    summary = service.get_summary(assessment.id)
    print(f"  Total checks: {summary['checks']['total']}")
    print(f"  Score: {summary['overall_score']}%")
    print(f"  Readiness: {summary['readiness_level']}")

    # Run automated checks
    print("\n--- Running automated checks ---")
    results = service.run_automated_checks(assessment.id)
    print(f"  Automated checks run: {len(results)}")

    summary = service.get_summary(assessment.id)
    print(f"  Score after automated: {summary['overall_score']}%")
    print(f"  Readiness: {summary['readiness_level']}")

    # Mark some manual checks as passed
    print("\n--- Marking manual checks ---")
    manual_checks = [c for c in assessment.checks
                     if c.evidence_type != EvidenceType.AUTOMATED and c.status == CheckStatus.NOT_STARTED]
    for check in manual_checks[:15]:
        service.mark_check(assessment.id, check.id, CheckStatus.PASSED, "Verified by team")

    summary = service.get_summary(assessment.id)
    print(f"  Score: {summary['overall_score']}%")
    print(f"  Readiness: {summary['readiness_level']}")

    # Identify gaps
    print("\n--- Gap Analysis ---")
    gaps = service.get_gaps(assessment.id)
    print(f"  Total gaps: {len(gaps)}")
    for gap in gaps[:5]:
        print(f"    [{gap['priority']:>8}] {gap['category']}: {gap['title']}")

    # Create remediation for a gap
    if gaps:
        print("\n--- Creating remediation ---")
        rem = service.create_remediation(
            assessment.id,
            gaps[0]["check_id"],
            title=f"Fix: {gaps[0]['title']}",
            assignee="engineer@company.com",
            due_date=(datetime.utcnow() + timedelta(days=3)).isoformat(),
            priority=gaps[0]["priority"],
        )
        print(f"  Created: {rem.title} -> {rem.assignee}")

    # Mark remaining checks to get to ready
    print("\n--- Completing remaining checks ---")
    remaining = [c for c in assessment.checks if c.status == CheckStatus.NOT_STARTED]
    for check in remaining:
        service.mark_check(assessment.id, check.id, CheckStatus.PASSED)

    summary = service.get_summary(assessment.id)
    print(f"  Final score: {summary['overall_score']}%")
    print(f"  Readiness: {summary['readiness_level']}")

    # Approve
    print("\n--- Approval ---")
    service.submit_approval(assessment.id, ReadinessApproval(
        approver="chief_architect@company.com",
        role="Chief AI Architect",
        status=ApprovalStatus.APPROVED,
        comments="All checks pass. Approved for production.",
    ))
    service.submit_approval(assessment.id, ReadinessApproval(
        approver="eng_director@company.com",
        role="Engineering Director",
        status=ApprovalStatus.APPROVED,
        comments="Business justification strong. Go.",
    ))

    final = service.get_summary(assessment.id)
    print(f"  Final status: {final['final_status']}")
    print(f"  Post-launch reviews scheduled: {len(assessment.post_launch_reviews)}")
    for review in assessment.post_launch_reviews:
        print(f"    {review.review_type}: {review.scheduled_date[:10]}")

    # Category breakdown
    print("\n--- Category Scores ---")
    for cat, score in sorted(final["category_scores"].items()):
        bar = "#" * int(score / 5)
        print(f"  {cat:20s}: {score:5.1f}% {bar}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    demo()
