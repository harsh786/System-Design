"""
AI Compliance Checking System
==============================
Automated compliance assessment for AI systems against EU AI Act,
NIST AI RMF, and organizational policies. Includes gap analysis,
evidence collection, audit trail, and remediation tracking.
"""

import uuid
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field, asdict


# =============================================================================
# Enumerations
# =============================================================================

class Regulation(Enum):
    EU_AI_ACT = "eu_ai_act"
    NIST_AI_RMF = "nist_ai_rmf"
    ISO_42001 = "iso_42001"
    GDPR = "gdpr"
    ORGANIZATIONAL = "organizational_policy"


class EUAIActRiskCategory(Enum):
    UNACCEPTABLE = "unacceptable"  # Banned
    HIGH = "high"                   # Full compliance regime
    LIMITED = "limited"             # Transparency obligations
    MINIMAL = "minimal"             # No specific requirements
    GPAI = "gpai"                   # General Purpose AI
    GPAI_SYSTEMIC = "gpai_systemic"  # GPAI with systemic risk


class ComplianceStatus(Enum):
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"


class EvidenceType(Enum):
    DOCUMENT = "document"
    TEST_RESULT = "test_result"
    LOG = "log"
    ATTESTATION = "attestation"
    SCREENSHOT = "screenshot"
    AUDIT_REPORT = "audit_report"
    POLICY = "policy"
    CERTIFICATE = "certificate"
    INTERVIEW = "interview"
    METRIC = "metric"


class RemediationPriority(Enum):
    CRITICAL = "critical"  # Must fix before deployment/continued operation
    HIGH = "high"          # Fix within 30 days
    MEDIUM = "medium"      # Fix within 90 days
    LOW = "low"            # Fix within next review cycle


class RemediationStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    ACCEPTED_RISK = "accepted_risk"
    DEFERRED = "deferred"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ComplianceRequirement:
    """A single compliance requirement/control."""
    requirement_id: str = ""
    regulation: str = Regulation.EU_AI_ACT.value
    article: str = ""  # e.g., "Art. 9" for EU AI Act
    title: str = ""
    description: str = ""
    applicability_conditions: list = field(default_factory=list)
    evidence_required: list = field(default_factory=list)
    risk_categories_applicable: list = field(default_factory=list)


@dataclass
class ComplianceEvidence:
    """Evidence supporting compliance with a requirement."""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requirement_id: str = ""
    evidence_type: str = EvidenceType.DOCUMENT.value
    title: str = ""
    description: str = ""
    source: str = ""  # URL, file path, or system reference
    collected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    collected_by: str = ""
    validity_period: Optional[str] = None  # ISO duration or end date
    automated: bool = False  # Was this collected automatically?
    content_hash: str = ""  # For integrity verification
    metadata: dict = field(default_factory=dict)


@dataclass
class ComplianceCheckResult:
    """Result of checking a single requirement."""
    check_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requirement_id: str = ""
    system_id: str = ""
    status: str = ComplianceStatus.NOT_ASSESSED.value
    score: float = 0.0  # 0-1 compliance score
    evidence: list = field(default_factory=list)  # list of ComplianceEvidence
    gaps: list = field(default_factory=list)  # identified gaps
    notes: str = ""
    assessed_by: str = ""
    assessed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RemediationItem:
    """A remediation action to address a compliance gap."""
    remediation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    gap_description: str = ""
    requirement_id: str = ""
    system_id: str = ""
    priority: str = RemediationPriority.MEDIUM.value
    status: str = RemediationStatus.OPEN.value
    owner: str = ""
    target_date: str = ""
    completion_date: Optional[str] = None
    action_plan: str = ""
    verification_criteria: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AuditTrailEntry:
    """Immutable audit trail entry."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    action: str = ""  # "assessment_started", "evidence_collected", "status_changed", etc.
    actor: str = ""
    system_id: str = ""
    details: dict = field(default_factory=dict)
    previous_state: Optional[dict] = None
    new_state: Optional[dict] = None


# =============================================================================
# EU AI Act Risk Categorization Engine
# =============================================================================

class EUAIActClassifier:
    """Classifies AI systems according to EU AI Act risk categories."""

    # Annex III: High-risk AI systems
    HIGH_RISK_AREAS = {
        "biometric_identification": {
            "description": "Remote biometric identification systems",
            "examples": ["facial recognition", "fingerprint matching", "voice identification"],
        },
        "critical_infrastructure": {
            "description": "Safety components of critical infrastructure",
            "examples": ["power grid management", "water treatment", "traffic management"],
        },
        "education": {
            "description": "AI in education and vocational training",
            "examples": ["admission decisions", "grading", "learning assessment", "proctoring"],
        },
        "employment": {
            "description": "AI in employment, worker management",
            "examples": ["CV screening", "hiring decisions", "promotion", "termination", "task allocation"],
        },
        "essential_services": {
            "description": "Access to essential private/public services",
            "examples": ["credit scoring", "insurance pricing", "social benefits", "emergency services"],
        },
        "law_enforcement": {
            "description": "AI in law enforcement",
            "examples": ["risk assessment", "polygraph", "evidence evaluation", "crime prediction"],
        },
        "migration": {
            "description": "AI in migration, asylum, border control",
            "examples": ["visa assessment", "asylum claims", "border surveillance", "risk screening"],
        },
        "justice": {
            "description": "AI in administration of justice",
            "examples": ["sentencing support", "case outcome prediction", "legal research AI"],
        },
    }

    # Prohibited practices (Article 5)
    PROHIBITED_PRACTICES = [
        "subliminal_manipulation",
        "exploitation_of_vulnerabilities",
        "social_scoring_by_government",
        "real_time_biometric_public_spaces",  # with limited exceptions
        "untargeted_facial_image_scraping",
        "emotion_recognition_workplace_education",
        "biometric_categorization_sensitive_attributes",
    ]

    def classify_system(self, system_profile: dict) -> dict:
        """
        Classify an AI system under EU AI Act.

        system_profile should contain:
        - use_case: description of what the system does
        - domain: area of application
        - affected_rights: fundamental rights potentially affected
        - autonomy_level: "advisory", "semi-autonomous", "fully_autonomous"
        - scale: number of affected individuals
        - data_types: types of data processed
        - decision_types: types of decisions made/supported
        - is_gpai: whether it's a general-purpose AI model
        - training_compute_flops: for GPAI systemic risk threshold
        """
        result = {
            "system_profile": system_profile,
            "classification": None,
            "rationale": [],
            "applicable_requirements": [],
            "assessed_at": datetime.utcnow().isoformat(),
        }

        # Check prohibited first
        if self._check_prohibited(system_profile):
            result["classification"] = EUAIActRiskCategory.UNACCEPTABLE.value
            result["rationale"].append("System falls under prohibited AI practices (Art. 5)")
            return result

        # Check GPAI
        if system_profile.get("is_gpai"):
            compute = system_profile.get("training_compute_flops", 0)
            if compute >= 10**25:
                result["classification"] = EUAIActRiskCategory.GPAI_SYSTEMIC.value
                result["rationale"].append(f"GPAI with systemic risk (>{10**25} FLOPs training compute)")
            else:
                result["classification"] = EUAIActRiskCategory.GPAI.value
                result["rationale"].append("General-Purpose AI model")
            return result

        # Check high-risk (Annex III)
        high_risk_match = self._check_high_risk(system_profile)
        if high_risk_match:
            result["classification"] = EUAIActRiskCategory.HIGH.value
            result["rationale"].append(f"High-risk: matches Annex III area '{high_risk_match}'")
            result["applicable_requirements"] = self._get_high_risk_requirements()
            return result

        # Check limited risk (transparency obligations)
        if self._check_limited_risk(system_profile):
            result["classification"] = EUAIActRiskCategory.LIMITED.value
            result["rationale"].append("Limited risk: transparency obligations apply")
            result["applicable_requirements"] = self._get_limited_risk_requirements()
            return result

        # Default: minimal risk
        result["classification"] = EUAIActRiskCategory.MINIMAL.value
        result["rationale"].append("Minimal risk: no specific requirements (voluntary codes apply)")
        return result

    def _check_prohibited(self, profile: dict) -> bool:
        """Check if system falls under prohibited practices."""
        use_case = profile.get("use_case", "").lower()
        domain = profile.get("domain", "").lower()

        prohibited_signals = [
            "social scoring" in use_case and "government" in domain,
            "subliminal" in use_case and "manipulation" in use_case,
            "exploit" in use_case and "vulnerab" in use_case,
            profile.get("real_time_biometric") and profile.get("public_spaces"),
        ]
        return any(prohibited_signals)

    def _check_high_risk(self, profile: dict) -> Optional[str]:
        """Check if system matches Annex III high-risk areas."""
        domain = profile.get("domain", "").lower()
        use_case = profile.get("use_case", "").lower()
        decision_types = [d.lower() for d in profile.get("decision_types", [])]

        for area, info in self.HIGH_RISK_AREAS.items():
            examples = [e.lower() for e in info["examples"]]
            if any(ex in use_case or ex in domain for ex in examples):
                return area
            if any(ex in dt for ex in examples for dt in decision_types):
                return area

        return None

    def _check_limited_risk(self, profile: dict) -> bool:
        """Check if limited risk (transparency) obligations apply."""
        limited_signals = [
            "chatbot" in profile.get("use_case", "").lower(),
            "deepfake" in profile.get("use_case", "").lower(),
            "emotion_recognition" in profile.get("use_case", "").lower(),
            profile.get("generates_synthetic_content"),
            profile.get("interacts_with_humans"),
        ]
        return any(limited_signals)

    def _get_high_risk_requirements(self) -> list[dict]:
        """Get EU AI Act requirements for high-risk systems."""
        return [
            {"id": "EUAI-HR-01", "article": "Art. 9", "title": "Risk Management System",
             "description": "Establish, implement, document and maintain a risk management system"},
            {"id": "EUAI-HR-02", "article": "Art. 10", "title": "Data Governance",
             "description": "Training, validation and testing datasets shall meet quality criteria"},
            {"id": "EUAI-HR-03", "article": "Art. 11", "title": "Technical Documentation",
             "description": "Draw up technical documentation before system is placed on market"},
            {"id": "EUAI-HR-04", "article": "Art. 12", "title": "Record-Keeping",
             "description": "Enable automatic recording of events (logs) during operation"},
            {"id": "EUAI-HR-05", "article": "Art. 13", "title": "Transparency and Information",
             "description": "Designed to ensure operation is sufficiently transparent to deployers"},
            {"id": "EUAI-HR-06", "article": "Art. 14", "title": "Human Oversight",
             "description": "Designed to be effectively overseen by natural persons"},
            {"id": "EUAI-HR-07", "article": "Art. 15", "title": "Accuracy, Robustness, Cybersecurity",
             "description": "Achieve appropriate level of accuracy, robustness and cybersecurity"},
            {"id": "EUAI-HR-08", "article": "Art. 17", "title": "Quality Management System",
             "description": "Put a quality management system in place"},
            {"id": "EUAI-HR-09", "article": "Art. 9(8)", "title": "Testing and Validation",
             "description": "Testing shall be performed at appropriate times throughout development"},
            {"id": "EUAI-HR-10", "article": "Art. 13(3)", "title": "User Instructions",
             "description": "Accompanied by instructions for use including capabilities and limitations"},
        ]

    def _get_limited_risk_requirements(self) -> list[dict]:
        """Get EU AI Act requirements for limited risk systems."""
        return [
            {"id": "EUAI-LR-01", "article": "Art. 50(1)", "title": "AI Interaction Disclosure",
             "description": "Inform persons they are interacting with an AI system"},
            {"id": "EUAI-LR-02", "article": "Art. 50(2)", "title": "Synthetic Content Marking",
             "description": "Mark AI-generated content in machine-readable format"},
            {"id": "EUAI-LR-03", "article": "Art. 50(3)", "title": "Deepfake Disclosure",
             "description": "Disclose that content has been artificially generated or manipulated"},
        ]


# =============================================================================
# Compliance Checklist Engine
# =============================================================================

class ComplianceChecklistEngine:
    """Manages compliance checklists and executes checks."""

    def __init__(self):
        self.requirements: dict[str, ComplianceRequirement] = {}
        self.check_results: dict[str, list[ComplianceCheckResult]] = {}  # system_id -> results
        self.audit_trail: list[AuditTrailEntry] = []
        self._load_default_requirements()

    def _load_default_requirements(self):
        """Load built-in compliance requirements."""
        # EU AI Act High-Risk requirements
        eu_requirements = [
            ComplianceRequirement(
                requirement_id="EUAI-HR-01",
                regulation=Regulation.EU_AI_ACT.value,
                article="Art. 9",
                title="Risk Management System",
                description="A risk management system shall be established, implemented, documented "
                            "and maintained as a continuous iterative process throughout the AI lifecycle.",
                risk_categories_applicable=[EUAIActRiskCategory.HIGH.value],
                evidence_required=[
                    "Risk management policy document",
                    "Risk register with identified risks",
                    "Risk assessment methodology",
                    "Evidence of periodic risk review",
                    "Residual risk acceptance documentation",
                ],
            ),
            ComplianceRequirement(
                requirement_id="EUAI-HR-02",
                regulation=Regulation.EU_AI_ACT.value,
                article="Art. 10",
                title="Data Governance",
                description="Training, validation and testing data sets shall be subject to data "
                            "governance and management practices covering design choices, data collection, "
                            "relevant data preparation, formulation of assumptions, prior assessment of "
                            "availability/suitability/bias.",
                risk_categories_applicable=[EUAIActRiskCategory.HIGH.value],
                evidence_required=[
                    "Data governance policy",
                    "Data card / dataset documentation",
                    "Bias analysis report",
                    "Data quality metrics",
                    "Representativeness assessment",
                    "Consent/legal basis documentation",
                ],
            ),
            ComplianceRequirement(
                requirement_id="EUAI-HR-03",
                regulation=Regulation.EU_AI_ACT.value,
                article="Art. 11",
                title="Technical Documentation",
                description="Technical documentation shall be drawn up before the system is placed "
                            "on the market and kept up to date.",
                risk_categories_applicable=[EUAIActRiskCategory.HIGH.value],
                evidence_required=[
                    "System description and architecture",
                    "Model card",
                    "Development process documentation",
                    "Validation and testing results",
                    "Monitoring plan",
                ],
            ),
            ComplianceRequirement(
                requirement_id="EUAI-HR-04",
                regulation=Regulation.EU_AI_ACT.value,
                article="Art. 12",
                title="Record-Keeping / Logging",
                description="High-risk AI systems shall technically allow for automatic recording "
                            "of events (logs) over the lifetime of the system.",
                risk_categories_applicable=[EUAIActRiskCategory.HIGH.value],
                evidence_required=[
                    "Logging architecture documentation",
                    "Sample log records demonstrating capability",
                    "Log retention policy",
                    "Evidence of tamper-proof storage",
                    "Log access controls documentation",
                ],
            ),
            ComplianceRequirement(
                requirement_id="EUAI-HR-05",
                regulation=Regulation.EU_AI_ACT.value,
                article="Art. 13",
                title="Transparency",
                description="High-risk AI systems shall be designed and developed in such a way "
                            "to ensure that their operation is sufficiently transparent to enable "
                            "deployers to interpret the system's output and use it appropriately.",
                risk_categories_applicable=[EUAIActRiskCategory.HIGH.value],
                evidence_required=[
                    "User-facing documentation / instructions",
                    "Explanation of capabilities and limitations",
                    "Information about accuracy levels",
                    "Known circumstances of misuse risk",
                    "Human oversight instructions",
                ],
            ),
            ComplianceRequirement(
                requirement_id="EUAI-HR-06",
                regulation=Regulation.EU_AI_ACT.value,
                article="Art. 14",
                title="Human Oversight",
                description="High-risk AI systems shall be designed to be effectively overseen "
                            "by natural persons during the period of use.",
                risk_categories_applicable=[EUAIActRiskCategory.HIGH.value],
                evidence_required=[
                    "Human oversight design documentation",
                    "Override mechanism specification",
                    "Oversight personnel training records",
                    "Evidence of meaningful oversight (not rubber-stamping)",
                    "Intervention trigger documentation",
                ],
            ),
            ComplianceRequirement(
                requirement_id="EUAI-HR-07",
                regulation=Regulation.EU_AI_ACT.value,
                article="Art. 15",
                title="Accuracy, Robustness and Cybersecurity",
                description="High-risk AI systems shall be designed and developed in such a way "
                            "that they achieve an appropriate level of accuracy, robustness and "
                            "cybersecurity.",
                risk_categories_applicable=[EUAIActRiskCategory.HIGH.value],
                evidence_required=[
                    "Accuracy metrics and benchmarks",
                    "Robustness testing results (adversarial, stress)",
                    "Security assessment / penetration test results",
                    "Resilience measures documentation",
                    "Fallback mechanisms",
                ],
            ),
        ]

        for req in eu_requirements:
            self.requirements[req.requirement_id] = req

    def assess_compliance(
        self,
        system_id: str,
        risk_category: str,
        evidence_map: dict[str, list[ComplianceEvidence]],
        assessor: str,
    ) -> dict:
        """
        Assess compliance for a system against applicable requirements.

        evidence_map: requirement_id -> list of evidence items
        """
        self._log_audit("assessment_started", assessor, system_id, {"risk_category": risk_category})

        applicable_reqs = [
            req for req in self.requirements.values()
            if risk_category in req.risk_categories_applicable
        ]

        results = []
        for req in applicable_reqs:
            evidence = evidence_map.get(req.requirement_id, [])

            # Assess compliance based on evidence completeness
            check = self._evaluate_requirement(req, evidence, system_id, assessor)
            results.append(check)

        self.check_results[system_id] = results

        # Calculate overall compliance
        total = len(results)
        compliant = sum(1 for r in results if r.status == ComplianceStatus.COMPLIANT.value)
        partial = sum(1 for r in results if r.status == ComplianceStatus.PARTIALLY_COMPLIANT.value)
        non_compliant = sum(1 for r in results if r.status == ComplianceStatus.NON_COMPLIANT.value)

        overall_score = compliant / total if total > 0 else 0

        summary = {
            "system_id": system_id,
            "risk_category": risk_category,
            "assessed_at": datetime.utcnow().isoformat(),
            "assessor": assessor,
            "total_requirements": total,
            "compliant": compliant,
            "partially_compliant": partial,
            "non_compliant": non_compliant,
            "overall_score": round(overall_score, 2),
            "overall_status": (
                ComplianceStatus.COMPLIANT.value if non_compliant == 0 and partial == 0
                else ComplianceStatus.PARTIALLY_COMPLIANT.value if non_compliant == 0
                else ComplianceStatus.NON_COMPLIANT.value
            ),
            "results": [asdict(r) for r in results],
        }

        self._log_audit("assessment_completed", assessor, system_id, {
            "overall_status": summary["overall_status"],
            "score": summary["overall_score"],
        })

        return summary

    def _evaluate_requirement(
        self,
        requirement: ComplianceRequirement,
        evidence: list[ComplianceEvidence],
        system_id: str,
        assessor: str,
    ) -> ComplianceCheckResult:
        """Evaluate compliance for a single requirement."""
        required_evidence = requirement.evidence_required
        provided_evidence_titles = [e.title.lower() for e in evidence]

        # Simple coverage check: what percentage of required evidence is provided
        covered = 0
        gaps = []
        for req_ev in required_evidence:
            # Fuzzy match: check if any provided evidence relates to required
            matched = any(
                req_ev.lower().split()[0] in title or title in req_ev.lower()
                for title in provided_evidence_titles
            )
            if matched:
                covered += 1
            else:
                gaps.append(f"Missing evidence: {req_ev}")

        coverage = covered / len(required_evidence) if required_evidence else 1.0

        # Determine status
        if coverage >= 0.9:
            status = ComplianceStatus.COMPLIANT.value
        elif coverage >= 0.5:
            status = ComplianceStatus.PARTIALLY_COMPLIANT.value
        else:
            status = ComplianceStatus.NON_COMPLIANT.value

        return ComplianceCheckResult(
            requirement_id=requirement.requirement_id,
            system_id=system_id,
            status=status,
            score=round(coverage, 2),
            evidence=[asdict(e) for e in evidence],
            gaps=gaps,
            assessed_by=assessor,
        )

    # -------------------------------------------------------------------------
    # Gap Analysis
    # -------------------------------------------------------------------------

    def gap_analysis(self, system_id: str) -> dict:
        """Perform gap analysis between current state and full compliance."""
        results = self.check_results.get(system_id, [])
        if not results:
            return {"error": "No assessment found for this system"}

        gaps = []
        for result in results:
            if result.status != ComplianceStatus.COMPLIANT.value:
                req = self.requirements.get(result.requirement_id)
                gaps.append({
                    "requirement_id": result.requirement_id,
                    "requirement_title": req.title if req else "",
                    "article": req.article if req else "",
                    "current_status": result.status,
                    "compliance_score": result.score,
                    "gaps_identified": result.gaps,
                    "priority": (
                        RemediationPriority.CRITICAL.value if result.score < 0.3
                        else RemediationPriority.HIGH.value if result.score < 0.5
                        else RemediationPriority.MEDIUM.value
                    ),
                    "effort_estimate": self._estimate_remediation_effort(result),
                })

        return {
            "system_id": system_id,
            "analysis_date": datetime.utcnow().isoformat(),
            "total_gaps": len(gaps),
            "critical_gaps": sum(1 for g in gaps if g["priority"] == RemediationPriority.CRITICAL.value),
            "high_gaps": sum(1 for g in gaps if g["priority"] == RemediationPriority.HIGH.value),
            "gaps": gaps,
            "estimated_total_effort_days": sum(g["effort_estimate"] for g in gaps),
        }

    def _estimate_remediation_effort(self, result: ComplianceCheckResult) -> int:
        """Rough effort estimate in person-days based on gap severity."""
        gap_count = len(result.gaps)
        if result.score < 0.3:
            return gap_count * 10  # Major work needed per gap
        elif result.score < 0.5:
            return gap_count * 5
        elif result.score < 0.9:
            return gap_count * 2
        return 0

    # -------------------------------------------------------------------------
    # Compliance Reporting
    # -------------------------------------------------------------------------

    def generate_compliance_report(self, system_id: str) -> dict:
        """Generate a comprehensive compliance report."""
        results = self.check_results.get(system_id, [])
        gap_analysis = self.gap_analysis(system_id)

        report = {
            "report_id": str(uuid.uuid4()),
            "report_type": "compliance_assessment",
            "system_id": system_id,
            "generated_at": datetime.utcnow().isoformat(),
            "executive_summary": {
                "overall_status": self._overall_status(results),
                "requirements_assessed": len(results),
                "compliant": sum(1 for r in results if r.status == ComplianceStatus.COMPLIANT.value),
                "non_compliant": sum(1 for r in results if r.status == ComplianceStatus.NON_COMPLIANT.value),
                "key_findings": [],
            },
            "detailed_results": [asdict(r) for r in results],
            "gap_analysis": gap_analysis,
            "remediation_roadmap": self._generate_remediation_roadmap(gap_analysis),
            "audit_trail": [
                asdict(e) for e in self.audit_trail
                if e.system_id == system_id
            ][-50:],  # Last 50 entries
        }

        # Key findings
        for result in results:
            if result.status == ComplianceStatus.NON_COMPLIANT.value:
                req = self.requirements.get(result.requirement_id)
                report["executive_summary"]["key_findings"].append(
                    f"NON-COMPLIANT: {req.title if req else result.requirement_id} ({req.article if req else ''})"
                )

        return report

    def _overall_status(self, results: list) -> str:
        non_compliant = any(r.status == ComplianceStatus.NON_COMPLIANT.value for r in results)
        partial = any(r.status == ComplianceStatus.PARTIALLY_COMPLIANT.value for r in results)
        if non_compliant:
            return ComplianceStatus.NON_COMPLIANT.value
        if partial:
            return ComplianceStatus.PARTIALLY_COMPLIANT.value
        return ComplianceStatus.COMPLIANT.value

    def _generate_remediation_roadmap(self, gap_analysis: dict) -> list[dict]:
        """Generate prioritized remediation roadmap from gap analysis."""
        roadmap = []
        for gap in gap_analysis.get("gaps", []):
            roadmap.append({
                "requirement": gap["requirement_title"],
                "priority": gap["priority"],
                "effort_days": gap["effort_estimate"],
                "actions": [f"Address: {g}" for g in gap["gaps_identified"]],
                "suggested_deadline": (
                    datetime.utcnow() + timedelta(days=30 if gap["priority"] == "critical"
                                                   else 60 if gap["priority"] == "high"
                                                   else 90)
                ).strftime("%Y-%m-%d"),
            })

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        roadmap.sort(key=lambda x: priority_order.get(x["priority"], 99))
        return roadmap

    # -------------------------------------------------------------------------
    # Remediation Tracking
    # -------------------------------------------------------------------------

    def create_remediation(
        self,
        system_id: str,
        requirement_id: str,
        gap_description: str,
        owner: str,
        priority: RemediationPriority,
        action_plan: str,
        target_date: str,
        verification_criteria: str = "",
    ) -> RemediationItem:
        """Create a remediation item for a compliance gap."""
        item = RemediationItem(
            gap_description=gap_description,
            requirement_id=requirement_id,
            system_id=system_id,
            priority=priority.value,
            owner=owner,
            target_date=target_date,
            action_plan=action_plan,
            verification_criteria=verification_criteria,
        )

        self._log_audit("remediation_created", owner, system_id, {
            "remediation_id": item.remediation_id,
            "requirement": requirement_id,
            "priority": priority.value,
        })

        return item

    # -------------------------------------------------------------------------
    # Audit Trail
    # -------------------------------------------------------------------------

    def _log_audit(self, action: str, actor: str, system_id: str, details: dict,
                   previous_state: dict = None, new_state: dict = None):
        """Add an immutable audit trail entry."""
        entry = AuditTrailEntry(
            action=action,
            actor=actor,
            system_id=system_id,
            details=details,
            previous_state=previous_state,
            new_state=new_state,
        )
        self.audit_trail.append(entry)

    def get_audit_trail(self, system_id: Optional[str] = None, since: Optional[str] = None) -> list:
        """Retrieve audit trail entries."""
        entries = self.audit_trail
        if system_id:
            entries = [e for e in entries if e.system_id == system_id]
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        return [asdict(e) for e in entries]


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # 1. Classify a system
    classifier = EUAIActClassifier()

    system_profile = {
        "use_case": "Automated CV screening and candidate ranking for job applications",
        "domain": "employment",
        "affected_rights": ["non-discrimination", "dignity", "fair trial"],
        "autonomy_level": "semi-autonomous",
        "scale": 50000,  # applications per year
        "data_types": ["personal_data", "sensitive_data"],
        "decision_types": ["hiring decisions", "CV screening"],
        "is_gpai": False,
        "interacts_with_humans": True,
    }

    classification = classifier.classify_system(system_profile)
    print("=== EU AI ACT CLASSIFICATION ===")
    print(f"Category: {classification['classification']}")
    print(f"Rationale: {classification['rationale']}")
    print(f"Requirements: {len(classification.get('applicable_requirements', []))}")

    # 2. Run compliance assessment
    engine = ComplianceChecklistEngine()

    # Simulate evidence collection
    evidence_map = {
        "EUAI-HR-01": [
            ComplianceEvidence(
                requirement_id="EUAI-HR-01",
                evidence_type=EvidenceType.DOCUMENT.value,
                title="Risk management policy document",
                description="AI Risk Management Policy v2.0",
                source="/docs/policies/ai-risk-management.pdf",
                collected_by="governance-team",
            ),
            ComplianceEvidence(
                requirement_id="EUAI-HR-01",
                evidence_type=EvidenceType.DOCUMENT.value,
                title="Risk register",
                description="Active risk register for CV screening system",
                source="/systems/cv-screener/risk-register.json",
                collected_by="governance-team",
                automated=True,
            ),
        ],
        "EUAI-HR-06": [
            ComplianceEvidence(
                requirement_id="EUAI-HR-06",
                evidence_type=EvidenceType.DOCUMENT.value,
                title="Human oversight design",
                description="HITL process for candidate rejection decisions",
                source="/docs/cv-screener/human-oversight.pdf",
                collected_by="product-team",
            ),
        ],
    }

    assessment = engine.assess_compliance(
        system_id="sys-cv-screener-001",
        risk_category=EUAIActRiskCategory.HIGH.value,
        evidence_map=evidence_map,
        assessor="compliance-officer@company.com",
    )

    print("\n=== COMPLIANCE ASSESSMENT ===")
    print(f"Overall Status: {assessment['overall_status']}")
    print(f"Score: {assessment['overall_score']}")
    print(f"Compliant: {assessment['compliant']}/{assessment['total_requirements']}")

    # 3. Gap analysis
    gaps = engine.gap_analysis("sys-cv-screener-001")
    print(f"\n=== GAP ANALYSIS ===")
    print(f"Total gaps: {gaps['total_gaps']}")
    print(f"Critical: {gaps['critical_gaps']}, High: {gaps['high_gaps']}")
    print(f"Estimated effort: {gaps['estimated_total_effort_days']} person-days")

    # 4. Generate report
    report = engine.generate_compliance_report("sys-cv-screener-001")
    print(f"\n=== COMPLIANCE REPORT ===")
    print(f"Key Findings:")
    for finding in report["executive_summary"]["key_findings"]:
        print(f"  - {finding}")
    print(f"\nRemediation Roadmap ({len(report['remediation_roadmap'])} items):")
    for item in report["remediation_roadmap"][:3]:
        print(f"  [{item['priority']}] {item['requirement']} - due {item['suggested_deadline']}")
