"""
Model Card / System Card / Data Card Generator
================================================
Comprehensive documentation generator for AI models, systems, and datasets
following Google Model Cards (Mitchell et al., 2019), System Cards, and
Data Cards (Pushkarna et al., 2022) frameworks.
"""

import uuid
import json
import hashlib
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


# =============================================================================
# Enumerations
# =============================================================================

class CardType(Enum):
    MODEL = "model_card"
    SYSTEM = "system_card"
    DATA = "data_card"


class CardStatus(Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ApprovalDecision(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Model Card Schema
# =============================================================================

@dataclass
class ModelDetails:
    name: str = ""
    version: str = ""
    description: str = ""
    model_type: str = ""  # e.g., "transformer", "CNN", "gradient boosting"
    architecture: str = ""  # e.g., "BERT-base", "ResNet-50"
    framework: str = ""  # e.g., "PyTorch 2.0", "TensorFlow 2.13"
    developer: str = ""
    organization: str = ""
    release_date: str = ""
    license: str = ""
    contact: str = ""
    model_size: str = ""  # e.g., "110M parameters"
    training_compute: str = ""  # e.g., "8x A100 for 72 hours"
    carbon_footprint: str = ""  # e.g., "estimated 50kg CO2eq"
    repository_url: str = ""
    paper_url: str = ""
    parent_model: str = ""  # for fine-tuned models


@dataclass
class IntendedUse:
    primary_uses: list = field(default_factory=list)
    primary_users: list = field(default_factory=list)
    out_of_scope_uses: list = field(default_factory=list)
    deployment_context: str = ""  # "internal", "customer-facing", "research"
    decision_type: str = ""  # "advisory", "automated", "human-in-loop"


@dataclass
class TrainingData:
    description: str = ""
    datasets: list = field(default_factory=list)  # list of dataset references
    size: str = ""  # e.g., "1.2M examples"
    collection_period: str = ""
    preprocessing: list = field(default_factory=list)
    data_augmentation: str = ""
    known_limitations: list = field(default_factory=list)
    sensitive_data_handling: str = ""
    consent_mechanism: str = ""
    data_card_reference: str = ""  # link to associated data card


@dataclass
class EvaluationData:
    description: str = ""
    datasets: list = field(default_factory=list)
    size: str = ""
    selection_rationale: str = ""
    known_limitations: list = field(default_factory=list)


@dataclass
class PerformanceMetric:
    metric_name: str = ""
    value: float = 0.0
    threshold: Optional[float] = None
    confidence_interval: str = ""
    dataset: str = ""
    slice_description: str = ""  # e.g., "age > 65", "female", "english-speaking"
    measurement_date: str = ""


@dataclass
class FairnessAnalysis:
    protected_attributes_evaluated: list = field(default_factory=list)
    fairness_metrics: list = field(default_factory=list)  # list of PerformanceMetric
    fairness_definition: str = ""  # e.g., "demographic parity", "equalized odds"
    disparities_found: list = field(default_factory=list)
    mitigation_applied: str = ""
    residual_concerns: list = field(default_factory=list)


@dataclass
class EthicalConsiderations:
    sensitive_use_cases: list = field(default_factory=list)
    known_risks: list = field(default_factory=list)
    potential_harms: list = field(default_factory=list)
    mitigation_strategies: list = field(default_factory=list)
    human_oversight_requirements: str = ""
    feedback_mechanisms: str = ""
    appeal_process: str = ""


@dataclass
class RobustnessInfo:
    adversarial_testing: str = ""
    stress_testing: str = ""
    distribution_shift_tolerance: str = ""
    known_failure_modes: list = field(default_factory=list)
    degradation_patterns: str = ""


@dataclass
class ModelCard:
    card_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    card_type: str = CardType.MODEL.value
    status: str = CardStatus.DRAFT.value
    version: str = "1.0.0"

    # Core sections
    model_details: ModelDetails = field(default_factory=ModelDetails)
    intended_use: IntendedUse = field(default_factory=IntendedUse)
    training_data: TrainingData = field(default_factory=TrainingData)
    evaluation_data: EvaluationData = field(default_factory=EvaluationData)

    # Performance
    performance_metrics: list = field(default_factory=list)  # list of PerformanceMetric
    disaggregated_metrics: dict = field(default_factory=dict)  # group -> metrics

    # Responsible AI
    fairness_analysis: FairnessAnalysis = field(default_factory=FairnessAnalysis)
    ethical_considerations: EthicalConsiderations = field(default_factory=EthicalConsiderations)
    robustness: RobustnessInfo = field(default_factory=RobustnessInfo)

    # Explainability
    explainability_approach: str = ""
    feature_importance: list = field(default_factory=list)
    explanation_examples: list = field(default_factory=list)

    # Operational
    deployment_requirements: dict = field(default_factory=dict)
    monitoring_plan: str = ""
    update_cadence: str = ""
    deprecation_policy: str = ""

    # Metadata
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    approved_by: str = ""
    approved_at: str = ""
    review_history: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    related_cards: list = field(default_factory=list)


# =============================================================================
# System Card Schema
# =============================================================================

@dataclass
class SystemComponent:
    component_id: str = ""
    name: str = ""
    component_type: str = ""  # "model", "retriever", "guardrail", "orchestrator"
    description: str = ""
    model_card_reference: str = ""
    version: str = ""
    configuration: dict = field(default_factory=dict)


@dataclass
class HumanOversight:
    oversight_level: str = ""  # "in-the-loop", "on-the-loop", "over-the-loop"
    intervention_triggers: list = field(default_factory=list)
    override_mechanism: str = ""
    escalation_path: list = field(default_factory=list)
    oversight_personnel_requirements: str = ""
    response_time_requirements: str = ""


@dataclass
class IncidentHistory:
    total_incidents: int = 0
    incidents: list = field(default_factory=list)  # [{date, type, severity, resolution}]
    lessons_learned: list = field(default_factory=list)
    systemic_improvements: list = field(default_factory=list)


@dataclass
class SystemCard:
    card_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    card_type: str = CardType.SYSTEM.value
    status: str = CardStatus.DRAFT.value
    version: str = "1.0.0"

    # System overview
    system_name: str = ""
    system_description: str = ""
    system_purpose: str = ""
    system_owner: str = ""
    organization: str = ""

    # Architecture
    components: list = field(default_factory=list)  # list of SystemComponent
    data_flows: list = field(default_factory=list)
    integration_points: list = field(default_factory=list)
    infrastructure: dict = field(default_factory=dict)

    # Intended use (same as model card)
    intended_use: IntendedUse = field(default_factory=IntendedUse)

    # Human oversight
    human_oversight: HumanOversight = field(default_factory=HumanOversight)

    # Performance (system-level)
    system_metrics: list = field(default_factory=list)
    sla_commitments: dict = field(default_factory=dict)

    # Safety and security
    safety_measures: list = field(default_factory=list)
    security_controls: list = field(default_factory=list)
    threat_model_reference: str = ""

    # Responsible AI
    fairness_analysis: FairnessAnalysis = field(default_factory=FairnessAnalysis)
    ethical_considerations: EthicalConsiderations = field(default_factory=EthicalConsiderations)

    # Operational
    deployment_context: dict = field(default_factory=dict)
    monitoring_and_alerting: dict = field(default_factory=dict)
    feedback_mechanisms: list = field(default_factory=list)
    incident_history: IncidentHistory = field(default_factory=IncidentHistory)
    downstream_dependencies: list = field(default_factory=list)

    # Compliance
    regulatory_classification: str = ""  # EU AI Act risk level
    compliance_certifications: list = field(default_factory=list)
    audit_history: list = field(default_factory=list)

    # Metadata
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    review_history: list = field(default_factory=list)
    related_cards: list = field(default_factory=list)


# =============================================================================
# Data Card Schema
# =============================================================================

@dataclass
class DataComposition:
    instance_count: int = 0
    feature_count: int = 0
    feature_types: dict = field(default_factory=dict)  # feature_name -> type
    label_distribution: dict = field(default_factory=dict)
    missing_values: dict = field(default_factory=dict)
    temporal_coverage: str = ""
    geographic_coverage: str = ""
    demographic_composition: dict = field(default_factory=dict)
    languages: list = field(default_factory=list)


@dataclass
class CollectionProcess:
    methodology: str = ""
    sources: list = field(default_factory=list)
    collectors: str = ""
    collection_period: str = ""
    sampling_strategy: str = ""
    consent_mechanism: str = ""
    ethical_review: str = ""  # IRB or equivalent
    compensation: str = ""  # for data subjects/annotators


@dataclass
class DataPreprocessing:
    steps: list = field(default_factory=list)  # ordered list of preprocessing steps
    tools_used: list = field(default_factory=list)
    decisions_and_rationale: list = field(default_factory=list)
    data_removed: str = ""  # what was filtered out and why
    transformations: list = field(default_factory=list)


@dataclass
class DataQuality:
    quality_metrics: dict = field(default_factory=dict)
    known_issues: list = field(default_factory=list)
    validation_process: str = ""
    annotation_quality: dict = field(default_factory=dict)  # inter-annotator agreement etc.
    freshness: str = ""
    completeness: str = ""


@dataclass
class SensitiveAttributes:
    attributes_present: list = field(default_factory=list)
    protection_measures: list = field(default_factory=list)
    access_restrictions: str = ""
    anonymization_applied: str = ""
    re_identification_risk: str = ""


@dataclass
class DataCard:
    card_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    card_type: str = CardType.DATA.value
    status: str = CardStatus.DRAFT.value
    version: str = "1.0.0"

    # Overview
    dataset_name: str = ""
    dataset_description: str = ""
    dataset_purpose: str = ""
    creator: str = ""
    organization: str = ""
    license: str = ""
    doi: str = ""
    repository_url: str = ""

    # Composition
    composition: DataComposition = field(default_factory=DataComposition)

    # Collection
    collection_process: CollectionProcess = field(default_factory=CollectionProcess)

    # Preprocessing
    preprocessing: DataPreprocessing = field(default_factory=DataPreprocessing)

    # Quality
    quality: DataQuality = field(default_factory=DataQuality)

    # Sensitive data
    sensitive_attributes: SensitiveAttributes = field(default_factory=SensitiveAttributes)

    # Usage
    intended_uses: list = field(default_factory=list)
    inappropriate_uses: list = field(default_factory=list)
    known_biases: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    recommended_preprocessing: list = field(default_factory=list)

    # Maintenance
    maintainer: str = ""
    update_frequency: str = ""
    retention_policy: str = ""
    deprecation_date: str = ""
    changelog: list = field(default_factory=list)

    # Distribution
    distribution_format: str = ""
    access_mechanism: str = ""
    access_requirements: list = field(default_factory=list)

    # Legal
    privacy_review_status: str = ""
    consent_status: str = ""
    regulatory_compliance: list = field(default_factory=list)
    data_processing_agreement: str = ""

    # Metadata
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    review_history: list = field(default_factory=list)
    related_cards: list = field(default_factory=list)


# =============================================================================
# Card Generator
# =============================================================================

class CardGenerator:
    """Generates model/system/data cards from evaluation results and metadata."""

    def generate_model_card_from_evaluation(
        self,
        model_info: dict,
        evaluation_results: dict,
        fairness_results: Optional[dict] = None,
        robustness_results: Optional[dict] = None,
        created_by: str = "auto-generator",
    ) -> ModelCard:
        """
        Generate a model card from evaluation pipeline results.

        model_info: {name, version, type, architecture, framework, description, ...}
        evaluation_results: {metrics: [{name, value, dataset, slice}], datasets: [...]}
        fairness_results: {protected_attributes, metrics, disparities}
        robustness_results: {adversarial_tests, stress_tests, failure_modes}
        """
        card = ModelCard(created_by=created_by)

        # Populate model details
        card.model_details = ModelDetails(
            name=model_info.get("name", ""),
            version=model_info.get("version", ""),
            description=model_info.get("description", ""),
            model_type=model_info.get("type", ""),
            architecture=model_info.get("architecture", ""),
            framework=model_info.get("framework", ""),
            developer=model_info.get("developer", ""),
            organization=model_info.get("organization", ""),
            release_date=model_info.get("release_date", datetime.utcnow().strftime("%Y-%m-%d")),
            license=model_info.get("license", ""),
            model_size=model_info.get("model_size", ""),
            training_compute=model_info.get("training_compute", ""),
        )

        # Populate performance metrics
        for metric in evaluation_results.get("metrics", []):
            pm = PerformanceMetric(
                metric_name=metric["name"],
                value=metric["value"],
                threshold=metric.get("threshold"),
                confidence_interval=metric.get("ci", ""),
                dataset=metric.get("dataset", ""),
                slice_description=metric.get("slice", "overall"),
                measurement_date=datetime.utcnow().isoformat(),
            )
            card.performance_metrics.append(asdict(pm))

        # Build disaggregated metrics
        for metric in evaluation_results.get("metrics", []):
            slice_key = metric.get("slice", "overall")
            if slice_key != "overall":
                if slice_key not in card.disaggregated_metrics:
                    card.disaggregated_metrics[slice_key] = []
                card.disaggregated_metrics[slice_key].append({
                    "metric": metric["name"],
                    "value": metric["value"],
                })

        # Populate fairness analysis
        if fairness_results:
            card.fairness_analysis = FairnessAnalysis(
                protected_attributes_evaluated=fairness_results.get("protected_attributes", []),
                fairness_definition=fairness_results.get("definition", ""),
                disparities_found=fairness_results.get("disparities", []),
                mitigation_applied=fairness_results.get("mitigation", ""),
                residual_concerns=fairness_results.get("concerns", []),
            )
            for fm in fairness_results.get("metrics", []):
                card.fairness_analysis.fairness_metrics.append(asdict(PerformanceMetric(
                    metric_name=fm["name"],
                    value=fm["value"],
                    slice_description=fm.get("group", ""),
                )))

        # Populate robustness
        if robustness_results:
            card.robustness = RobustnessInfo(
                adversarial_testing=robustness_results.get("adversarial_summary", ""),
                stress_testing=robustness_results.get("stress_summary", ""),
                known_failure_modes=robustness_results.get("failure_modes", []),
                distribution_shift_tolerance=robustness_results.get("shift_tolerance", ""),
            )

        return card

    def generate_system_card(
        self,
        system_info: dict,
        component_cards: list[ModelCard],
        oversight_config: dict,
        created_by: str = "auto-generator",
    ) -> SystemCard:
        """Generate a system card from component model cards and system config."""
        card = SystemCard(
            system_name=system_info.get("name", ""),
            system_description=system_info.get("description", ""),
            system_purpose=system_info.get("purpose", ""),
            system_owner=system_info.get("owner", ""),
            organization=system_info.get("organization", ""),
            created_by=created_by,
        )

        # Add components from model cards
        for mc in component_cards:
            component = SystemComponent(
                component_id=mc.card_id,
                name=mc.model_details.name,
                component_type="model",
                description=mc.model_details.description,
                model_card_reference=mc.card_id,
                version=mc.model_details.version,
            )
            card.components.append(asdict(component))
            card.related_cards.append(mc.card_id)

        # Human oversight
        card.human_oversight = HumanOversight(
            oversight_level=oversight_config.get("level", "on-the-loop"),
            intervention_triggers=oversight_config.get("triggers", []),
            override_mechanism=oversight_config.get("override", ""),
            escalation_path=oversight_config.get("escalation", []),
        )

        return card

    def generate_data_card(
        self,
        dataset_info: dict,
        quality_report: Optional[dict] = None,
        bias_report: Optional[dict] = None,
        created_by: str = "auto-generator",
    ) -> DataCard:
        """Generate a data card from dataset metadata and quality reports."""
        card = DataCard(
            dataset_name=dataset_info.get("name", ""),
            dataset_description=dataset_info.get("description", ""),
            dataset_purpose=dataset_info.get("purpose", ""),
            creator=dataset_info.get("creator", ""),
            organization=dataset_info.get("organization", ""),
            license=dataset_info.get("license", ""),
            created_by=created_by,
        )

        # Composition
        if "composition" in dataset_info:
            comp = dataset_info["composition"]
            card.composition = DataComposition(
                instance_count=comp.get("instance_count", 0),
                feature_count=comp.get("feature_count", 0),
                feature_types=comp.get("feature_types", {}),
                label_distribution=comp.get("label_distribution", {}),
                temporal_coverage=comp.get("temporal_coverage", ""),
                geographic_coverage=comp.get("geographic_coverage", ""),
                demographic_composition=comp.get("demographics", {}),
                languages=comp.get("languages", []),
            )

        # Quality from report
        if quality_report:
            card.quality = DataQuality(
                quality_metrics=quality_report.get("metrics", {}),
                known_issues=quality_report.get("issues", []),
                validation_process=quality_report.get("validation", ""),
                completeness=quality_report.get("completeness", ""),
                freshness=quality_report.get("freshness", ""),
            )

        # Bias information
        if bias_report:
            card.known_biases = bias_report.get("biases", [])
            card.sensitive_attributes = SensitiveAttributes(
                attributes_present=bias_report.get("sensitive_attributes", []),
                protection_measures=bias_report.get("protections", []),
                re_identification_risk=bias_report.get("reidentification_risk", ""),
            )

        return card


# =============================================================================
# Card Version Management
# =============================================================================

class CardVersionManager:
    """Manages versioning and history of cards."""

    def __init__(self):
        self.cards: dict[str, list] = {}  # card_id -> [versions]
        self.current_versions: dict[str, Any] = {}  # card_id -> current card

    def save_version(self, card) -> str:
        """Save a new version of a card."""
        card_id = card.card_id

        if card_id not in self.cards:
            self.cards[card_id] = []

        # Compute content hash for change detection
        card_dict = asdict(card) if hasattr(card, '__dataclass_fields__') else card
        content_hash = hashlib.sha256(json.dumps(card_dict, sort_keys=True, default=str).encode()).hexdigest()[:12]

        version_entry = {
            "version": card.version,
            "content_hash": content_hash,
            "saved_at": datetime.utcnow().isoformat(),
            "saved_by": getattr(card, 'created_by', 'unknown'),
            "status": card.status if isinstance(card.status, str) else card.status.value,
            "snapshot": card_dict,
        }

        self.cards[card_id].append(version_entry)
        self.current_versions[card_id] = card

        return content_hash

    def get_version_history(self, card_id: str) -> list[dict]:
        """Get version history for a card."""
        return [
            {k: v for k, v in entry.items() if k != "snapshot"}
            for entry in self.cards.get(card_id, [])
        ]

    def get_version(self, card_id: str, version: str) -> Optional[dict]:
        """Get a specific version of a card."""
        for entry in self.cards.get(card_id, []):
            if entry["version"] == version:
                return entry["snapshot"]
        return None

    def diff_versions(self, card_id: str, version_a: str, version_b: str) -> dict:
        """Compare two versions of a card."""
        a = self.get_version(card_id, version_a)
        b = self.get_version(card_id, version_b)

        if not a or not b:
            return {"error": "Version not found"}

        changes = {}
        all_keys = set(list(a.keys()) + list(b.keys()))
        for key in all_keys:
            val_a = a.get(key)
            val_b = b.get(key)
            if val_a != val_b:
                changes[key] = {"from": val_a, "to": val_b}

        return changes


# =============================================================================
# Card Review and Approval Workflow
# =============================================================================

@dataclass
class ReviewComment:
    reviewer: str = ""
    section: str = ""  # which section the comment is about
    comment: str = ""
    severity: str = "info"  # "info", "suggestion", "required"
    resolved: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ApprovalRecord:
    approver: str = ""
    decision: str = ApprovalDecision.APPROVED.value
    conditions: list = field(default_factory=list)
    comments: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class CardReviewWorkflow:
    """Manages the review and approval workflow for cards."""

    def __init__(self):
        self.reviews: dict[str, list[ReviewComment]] = {}  # card_id -> comments
        self.approvals: dict[str, list[ApprovalRecord]] = {}  # card_id -> approvals
        self.required_approvers: dict[str, list[str]] = {}  # card_type -> required roles

        # Default approval requirements
        self.required_approvers = {
            CardType.MODEL.value: ["model_owner", "data_steward", "ai_governance"],
            CardType.SYSTEM.value: ["system_owner", "security", "ai_governance", "legal"],
            CardType.DATA.value: ["data_owner", "privacy", "data_steward"],
        }

    def submit_for_review(self, card, submitter: str) -> dict:
        """Submit a card for review."""
        card_id = card.card_id
        card.status = CardStatus.IN_REVIEW.value
        card.updated_at = datetime.utcnow().isoformat()

        self.reviews[card_id] = []
        self.approvals[card_id] = []

        required = self.required_approvers.get(card.card_type, [])

        return {
            "card_id": card_id,
            "submitted_by": submitter,
            "submitted_at": datetime.utcnow().isoformat(),
            "required_approvers": required,
            "status": "in_review",
        }

    def add_review_comment(
        self,
        card_id: str,
        reviewer: str,
        section: str,
        comment: str,
        severity: str = "info",
    ) -> ReviewComment:
        """Add a review comment to a card."""
        rc = ReviewComment(
            reviewer=reviewer,
            section=section,
            comment=comment,
            severity=severity,
        )
        if card_id not in self.reviews:
            self.reviews[card_id] = []
        self.reviews[card_id].append(rc)
        return rc

    def approve(
        self,
        card_id: str,
        approver: str,
        approver_role: str,
        decision: ApprovalDecision,
        comments: str = "",
        conditions: Optional[list] = None,
    ) -> ApprovalRecord:
        """Record an approval decision."""
        record = ApprovalRecord(
            approver=approver,
            decision=decision.value,
            comments=comments,
            conditions=conditions or [],
        )

        if card_id not in self.approvals:
            self.approvals[card_id] = []
        self.approvals[card_id].append(record)

        return record

    def check_approval_status(self, card_id: str, card_type: str) -> dict:
        """Check if all required approvals are obtained."""
        required = self.required_approvers.get(card_type, [])
        approvals = self.approvals.get(card_id, [])

        approved_roles = set()
        rejected = False
        for record in approvals:
            if record.decision == ApprovalDecision.APPROVED.value:
                approved_roles.add(record.approver)
            elif record.decision == ApprovalDecision.REJECTED.value:
                rejected = True

        pending = [r for r in required if r not in approved_roles]
        all_approved = len(pending) == 0 and not rejected

        # Check for unresolved required comments
        unresolved_required = [
            c for c in self.reviews.get(card_id, [])
            if c.severity == "required" and not c.resolved
        ]

        return {
            "card_id": card_id,
            "all_approved": all_approved and not unresolved_required,
            "rejected": rejected,
            "approved_by": list(approved_roles),
            "pending_approvers": pending,
            "unresolved_required_comments": len(unresolved_required),
        }

    def publish(self, card, publisher: str) -> dict:
        """Publish a card (after all approvals)."""
        status = self.check_approval_status(card.card_id, card.card_type)

        if not status["all_approved"]:
            return {
                "success": False,
                "reason": "Not all approvals obtained",
                "details": status,
            }

        card.status = CardStatus.PUBLISHED.value
        card.updated_at = datetime.utcnow().isoformat()

        return {
            "success": True,
            "card_id": card.card_id,
            "published_at": datetime.utcnow().isoformat(),
            "published_by": publisher,
        }


# =============================================================================
# Card Publication API
# =============================================================================

class CardPublicationAPI:
    """API for publishing and retrieving cards."""

    def __init__(self):
        self.published_cards: dict[str, dict] = {}
        self.version_manager = CardVersionManager()
        self.review_workflow = CardReviewWorkflow()
        self.generator = CardGenerator()

    def create_and_publish_model_card(
        self,
        model_info: dict,
        evaluation_results: dict,
        fairness_results: Optional[dict] = None,
        robustness_results: Optional[dict] = None,
        created_by: str = "system",
    ) -> dict:
        """End-to-end: generate, version, and prepare card for review."""
        card = self.generator.generate_model_card_from_evaluation(
            model_info=model_info,
            evaluation_results=evaluation_results,
            fairness_results=fairness_results,
            robustness_results=robustness_results,
            created_by=created_by,
        )

        # Save version
        content_hash = self.version_manager.save_version(card)

        # Submit for review
        review_status = self.review_workflow.submit_for_review(card, created_by)

        return {
            "card_id": card.card_id,
            "content_hash": content_hash,
            "status": "in_review",
            "review_requirements": review_status["required_approvers"],
            "card": asdict(card),
        }

    def get_card(self, card_id: str) -> Optional[dict]:
        """Retrieve a published card."""
        return self.published_cards.get(card_id)

    def list_cards(self, card_type: Optional[str] = None, status: Optional[str] = None) -> list:
        """List cards with optional filters."""
        cards = list(self.published_cards.values())
        if card_type:
            cards = [c for c in cards if c.get("card_type") == card_type]
        if status:
            cards = [c for c in cards if c.get("status") == status]
        return cards

    def export_card_markdown(self, card: ModelCard) -> str:
        """Export a model card as readable markdown."""
        md = []
        md.append(f"# Model Card: {card.model_details.name}")
        md.append(f"\n**Version**: {card.model_details.version}")
        md.append(f"**Status**: {card.status}")
        md.append(f"**Last Updated**: {card.updated_at}")

        md.append("\n## Model Details")
        md.append(f"- **Type**: {card.model_details.model_type}")
        md.append(f"- **Architecture**: {card.model_details.architecture}")
        md.append(f"- **Framework**: {card.model_details.framework}")
        md.append(f"- **Size**: {card.model_details.model_size}")
        md.append(f"- **Developer**: {card.model_details.developer}")
        md.append(f"- **License**: {card.model_details.license}")

        md.append("\n## Intended Use")
        md.append(f"- **Primary Uses**: {', '.join(card.intended_use.primary_uses)}")
        md.append(f"- **Out of Scope**: {', '.join(card.intended_use.out_of_scope_uses)}")

        md.append("\n## Performance Metrics")
        md.append("| Metric | Value | Dataset | Slice |")
        md.append("|--------|-------|---------|-------|")
        for m in card.performance_metrics:
            md.append(f"| {m['metric_name']} | {m['value']:.4f} | {m['dataset']} | {m['slice_description']} |")

        if card.fairness_analysis.disparities_found:
            md.append("\n## Fairness Analysis")
            md.append(f"**Definition**: {card.fairness_analysis.fairness_definition}")
            md.append("\n**Disparities Found**:")
            for d in card.fairness_analysis.disparities_found:
                md.append(f"- {d}")

        md.append("\n## Ethical Considerations")
        if card.ethical_considerations.known_risks:
            md.append("\n**Known Risks**:")
            for r in card.ethical_considerations.known_risks:
                md.append(f"- {r}")

        if card.robustness.known_failure_modes:
            md.append("\n## Known Failure Modes")
            for f in card.robustness.known_failure_modes:
                md.append(f"- {f}")

        return "\n".join(md)


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    api = CardPublicationAPI()

    # Generate a model card from evaluation results
    result = api.create_and_publish_model_card(
        model_info={
            "name": "Customer Churn Predictor",
            "version": "2.1.0",
            "description": "Predicts customer churn probability based on usage patterns and demographics",
            "type": "gradient_boosting",
            "architecture": "XGBoost ensemble (500 trees, max_depth=6)",
            "framework": "XGBoost 1.7.6",
            "developer": "ML Platform Team",
            "organization": "Acme Corp",
            "license": "Internal Use Only",
            "model_size": "50MB serialized",
            "training_compute": "4 vCPU, 16GB RAM, 2 hours",
        },
        evaluation_results={
            "metrics": [
                {"name": "AUC-ROC", "value": 0.89, "dataset": "holdout_q4_2024", "slice": "overall"},
                {"name": "AUC-ROC", "value": 0.91, "dataset": "holdout_q4_2024", "slice": "age_18-35"},
                {"name": "AUC-ROC", "value": 0.85, "dataset": "holdout_q4_2024", "slice": "age_65+"},
                {"name": "Precision@10%", "value": 0.72, "dataset": "holdout_q4_2024", "slice": "overall"},
                {"name": "FPR", "value": 0.08, "dataset": "holdout_q4_2024", "slice": "overall"},
                {"name": "FPR", "value": 0.12, "dataset": "holdout_q4_2024", "slice": "race_black"},
                {"name": "FPR", "value": 0.06, "dataset": "holdout_q4_2024", "slice": "race_white"},
            ],
        },
        fairness_results={
            "protected_attributes": ["race", "gender", "age"],
            "definition": "equalized_odds",
            "metrics": [
                {"name": "demographic_parity_difference", "value": 0.04, "group": "gender"},
                {"name": "equalized_odds_difference", "value": 0.08, "group": "race"},
            ],
            "disparities": [
                "FPR is 2x higher for Black customers vs White customers",
                "Model performance degrades for age 65+ cohort",
            ],
            "mitigation": "Post-processing threshold calibration applied per racial group",
            "concerns": ["Proxy variable correlation with zip code needs further investigation"],
        },
        robustness_results={
            "adversarial_summary": "Tested with feature perturbation (±10%). Model stable for 95% of cases.",
            "stress_summary": "Performance degrades gracefully under 3x normal load.",
            "failure_modes": [
                "Returns high churn probability for new accounts with < 30 days history",
                "Sensitive to missing values in usage_frequency feature",
            ],
            "shift_tolerance": "Monthly retraining recommended; accuracy drops >5% after 60 days without retrain",
        },
        created_by="ml-platform@acme.com",
    )

    print("=== MODEL CARD CREATED ===")
    print(f"Card ID: {result['card_id']}")
    print(f"Status: {result['status']}")
    print(f"Required Approvers: {result['review_requirements']}")

    # Export as markdown
    card = api.generator.generate_model_card_from_evaluation(
        model_info={"name": "Demo", "version": "1.0", "type": "demo", "architecture": "demo",
                    "framework": "demo", "developer": "demo", "license": "MIT", "model_size": "10MB"},
        evaluation_results={"metrics": [
            {"name": "accuracy", "value": 0.95, "dataset": "test", "slice": "overall"},
        ]},
    )
    print("\n=== MARKDOWN EXPORT ===")
    print(api.export_card_markdown(card))
