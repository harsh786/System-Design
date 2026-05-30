"""
Architecture Decision Records (ADR) System for AI

Comprehensive ADR management system:
- ADR schema with AI-specific fields
- Creation, review, approval workflows
- Search, discovery, and linking
- Supersession management
- Template library
- Export and documentation generation
"""

import uuid
import re
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional
from abc import ABC, abstractmethod


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class ADRStatus(Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"

class ADRCategory(Enum):
    MODEL_SELECTION = "model_selection"
    DATA_ARCHITECTURE = "data_architecture"
    SECURITY = "security"
    AGENT_DESIGN = "agent_design"
    EVALUATION = "evaluation"
    DEPLOYMENT = "deployment"
    OBSERVABILITY = "observability"
    COST_OPTIMIZATION = "cost_optimization"
    PRIVACY = "privacy"
    INTEGRATION = "integration"
    PLATFORM = "platform"
    GOVERNANCE = "governance"

class ImpactLevel(Enum):
    LOW = "low"           # Single team/service
    MEDIUM = "medium"     # Multiple teams
    HIGH = "high"         # Organization-wide
    CRITICAL = "critical" # External/regulatory impact


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ADROption:
    """An option considered in the decision."""
    name: str
    description: str
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    estimated_effort: str = ""
    estimated_cost: str = ""
    risk_level: str = ""
    chosen: bool = False


@dataclass
class ADRConsequence:
    """A consequence of the decision."""
    description: str
    type: str = "neutral"  # positive, negative, neutral
    mitigation: str = ""   # For negative consequences
    metrics: list[str] = field(default_factory=list)  # How to measure this consequence


@dataclass
class ADRReview:
    """A review comment on an ADR."""
    reviewer_id: str
    reviewer_name: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    verdict: str = "comment"  # approve, request_changes, comment
    comments: str = ""
    sections_reviewed: list[str] = field(default_factory=list)


@dataclass
class ADRLink:
    """A link between ADRs."""
    target_adr_id: str
    relationship: str  # supersedes, superseded_by, related_to, depends_on, conflicts_with
    description: str = ""


@dataclass
class ArchitectureDecisionRecord:
    """Complete ADR document."""
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    number: int = 0  # Sequential ADR number
    title: str = ""
    slug: str = ""   # URL-friendly identifier

    # Metadata
    status: ADRStatus = ADRStatus.DRAFT
    category: ADRCategory = ADRCategory.PLATFORM
    impact_level: ImpactLevel = ImpactLevel.LOW
    author: str = ""
    owner: str = ""  # Who maintains this decision
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    decided_at: Optional[str] = None
    review_date: Optional[str] = None  # When to revisit this decision
    tags: list[str] = field(default_factory=list)

    # Core Content
    context: str = ""          # What problem are we solving?
    drivers: list[str] = field(default_factory=list)  # Key decision drivers
    options: list[ADROption] = field(default_factory=list)
    decision: str = ""         # What we decided
    rationale: str = ""        # Why we chose this option
    consequences: list[ADRConsequence] = field(default_factory=list)

    # AI-Specific Fields
    affected_models: list[str] = field(default_factory=list)
    affected_data_sources: list[str] = field(default_factory=list)
    affected_tools: list[str] = field(default_factory=list)
    risk_tier_impact: str = ""  # How this affects risk tiering
    compliance_impact: list[str] = field(default_factory=list)  # Standards affected

    # Relationships
    links: list[ADRLink] = field(default_factory=list)
    related_review_ids: list[str] = field(default_factory=list)  # Review board request IDs

    # Review
    reviews: list[ADRReview] = field(default_factory=list)
    approvers: list[str] = field(default_factory=list)  # Who approved
    required_approvers: list[str] = field(default_factory=list)  # Who must approve

    def to_markdown(self) -> str:
        """Export ADR as Markdown document."""
        lines = []
        lines.append(f"# ADR-{self.number:04d}: {self.title}")
        lines.append("")
        lines.append(f"**Status**: {self.status.value}")
        lines.append(f"**Category**: {self.category.value}")
        lines.append(f"**Impact**: {self.impact_level.value}")
        lines.append(f"**Author**: {self.author}")
        lines.append(f"**Date**: {self.created_at[:10]}")
        if self.review_date:
            lines.append(f"**Review By**: {self.review_date[:10]}")
        if self.tags:
            lines.append(f"**Tags**: {', '.join(self.tags)}")
        lines.append("")

        # Links
        if self.links:
            lines.append("## Related Decisions")
            for link in self.links:
                lines.append(f"- **{link.relationship}**: ADR `{link.target_adr_id}` — {link.description}")
            lines.append("")

        # Context
        lines.append("## Context")
        lines.append(self.context)
        lines.append("")

        # Drivers
        if self.drivers:
            lines.append("## Decision Drivers")
            for driver in self.drivers:
                lines.append(f"- {driver}")
            lines.append("")

        # Options
        lines.append("## Options Considered")
        for i, opt in enumerate(self.options, 1):
            chosen_mark = " ✓ (chosen)" if opt.chosen else ""
            lines.append(f"### Option {i}: {opt.name}{chosen_mark}")
            lines.append(opt.description)
            if opt.pros:
                lines.append("**Pros:**")
                for pro in opt.pros:
                    lines.append(f"- {pro}")
            if opt.cons:
                lines.append("**Cons:**")
                for con in opt.cons:
                    lines.append(f"- {con}")
            if opt.estimated_effort:
                lines.append(f"**Effort**: {opt.estimated_effort}")
            lines.append("")

        # Decision
        lines.append("## Decision")
        lines.append(self.decision)
        lines.append("")
        if self.rationale:
            lines.append("## Rationale")
            lines.append(self.rationale)
            lines.append("")

        # Consequences
        if self.consequences:
            lines.append("## Consequences")
            for cons in self.consequences:
                icon = {"positive": "+", "negative": "-", "neutral": "~"}[cons.type]
                lines.append(f"- [{icon}] {cons.description}")
                if cons.mitigation:
                    lines.append(f"  - Mitigation: {cons.mitigation}")
            lines.append("")

        # AI-Specific
        ai_sections = []
        if self.affected_models:
            ai_sections.append(f"**Affected Models**: {', '.join(self.affected_models)}")
        if self.affected_tools:
            ai_sections.append(f"**Affected Tools**: {', '.join(self.affected_tools)}")
        if self.compliance_impact:
            ai_sections.append(f"**Compliance Impact**: {', '.join(self.compliance_impact)}")
        if ai_sections:
            lines.append("## AI System Impact")
            lines.extend(ai_sections)
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# ADR TEMPLATES
# =============================================================================

class ADRTemplateLibrary:
    """Pre-built templates for common AI architecture decisions."""

    TEMPLATES = {
        "model_selection": {
            "title_pattern": "Select {model_type} model for {use_case}",
            "context_template": (
                "We need to select a {model_type} model for {use_case}. "
                "Key requirements include: {requirements}. "
                "The system will handle approximately {scale} requests per day."
            ),
            "drivers": [
                "Accuracy/quality requirements",
                "Latency requirements (p50, p99)",
                "Cost per request at expected scale",
                "Data privacy requirements (can data leave org?)",
                "Model availability and redundancy",
                "Fine-tuning capability needs",
            ],
            "consequence_areas": [
                "Cost impact",
                "Vendor lock-in",
                "Performance characteristics",
                "Data residency",
                "Maintenance burden",
            ],
            "category": ADRCategory.MODEL_SELECTION,
        },
        "agent_architecture": {
            "title_pattern": "Agent architecture for {use_case}",
            "context_template": (
                "We are building an AI agent system for {use_case}. "
                "The agent needs to {capabilities}. "
                "Key constraints: {constraints}."
            ),
            "drivers": [
                "Autonomy level required",
                "Tool access scope and blast radius",
                "Human-in-the-loop requirements",
                "Multi-agent coordination needs",
                "Error recovery and rollback capability",
                "Cost and latency budgets",
            ],
            "consequence_areas": [
                "Safety implications",
                "Operational complexity",
                "Cost at scale",
                "User trust",
                "Debugging/observability",
            ],
            "category": ADRCategory.AGENT_DESIGN,
        },
        "data_pipeline": {
            "title_pattern": "Data pipeline for {data_type} in {system}",
            "context_template": (
                "We need to ingest and process {data_type} for use in {system}. "
                "Data volume: {volume}. Freshness requirement: {freshness}. "
                "Privacy classification: {privacy_class}."
            ),
            "drivers": [
                "Data freshness requirements",
                "Volume and scalability",
                "Privacy and compliance requirements",
                "Data quality guarantees",
                "Cost of processing and storage",
                "Lineage and auditability",
            ],
            "consequence_areas": [
                "Operational cost",
                "Data quality",
                "Compliance posture",
                "System complexity",
                "Recovery time",
            ],
            "category": ADRCategory.DATA_ARCHITECTURE,
        },
        "evaluation_strategy": {
            "title_pattern": "Evaluation strategy for {system}",
            "context_template": (
                "We need to define how {system} will be evaluated for quality, safety, and regression. "
                "The system serves {audience} with {criticality} criticality."
            ),
            "drivers": [
                "Quality dimensions to measure",
                "Speed of feedback loop",
                "Cost of evaluation",
                "Human evaluation feasibility",
                "Regression detection sensitivity",
                "Production evaluation needs",
            ],
            "consequence_areas": [
                "Confidence in deployments",
                "Speed of iteration",
                "Cost of evaluation infrastructure",
                "False positive/negative rates",
                "Team workload",
            ],
            "category": ADRCategory.EVALUATION,
        },
        "security_pattern": {
            "title_pattern": "Security pattern for {concern} in {system}",
            "context_template": (
                "We need to address {concern} in {system}. "
                "Threat model identifies: {threats}. "
                "Regulatory requirements: {regulations}."
            ),
            "drivers": [
                "Threat severity and likelihood",
                "Regulatory requirements",
                "User experience impact",
                "Implementation complexity",
                "Operational overhead",
                "Defense in depth considerations",
            ],
            "consequence_areas": [
                "Security posture improvement",
                "User experience impact",
                "Operational complexity",
                "Cost",
                "Compliance coverage",
            ],
            "category": ADRCategory.SECURITY,
        },
    }

    @classmethod
    def list_templates(cls) -> list[str]:
        return list(cls.TEMPLATES.keys())

    @classmethod
    def get_template(cls, template_name: str) -> Optional[dict]:
        return cls.TEMPLATES.get(template_name)

    @classmethod
    def create_from_template(cls, template_name: str, params: dict) -> ArchitectureDecisionRecord:
        """Create an ADR pre-populated from a template."""
        template = cls.TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")

        title = template["title_pattern"].format(**{k: params.get(k, f"[{k}]") for k in
                                                     re.findall(r'\{(\w+)\}', template["title_pattern"])})
        context = template["context_template"].format(**{k: params.get(k, f"[{k}]") for k in
                                                         re.findall(r'\{(\w+)\}', template["context_template"])})

        adr = ArchitectureDecisionRecord(
            title=title,
            context=context,
            drivers=template["drivers"],
            category=template["category"],
            tags=[template_name],
        )
        return adr


# =============================================================================
# ADR STORE
# =============================================================================

class ADRStore(ABC):
    @abstractmethod
    def save(self, adr: ArchitectureDecisionRecord) -> None: ...
    @abstractmethod
    def get(self, adr_id: str) -> Optional[ArchitectureDecisionRecord]: ...
    @abstractmethod
    def get_by_number(self, number: int) -> Optional[ArchitectureDecisionRecord]: ...
    @abstractmethod
    def list_all(self, status: Optional[ADRStatus] = None, category: Optional[ADRCategory] = None) -> list[ArchitectureDecisionRecord]: ...
    @abstractmethod
    def search(self, query: str) -> list[ArchitectureDecisionRecord]: ...
    @abstractmethod
    def next_number(self) -> int: ...


class InMemoryADRStore(ADRStore):
    def __init__(self):
        self._adrs: dict[str, ArchitectureDecisionRecord] = {}
        self._counter = 0

    def save(self, adr: ArchitectureDecisionRecord) -> None:
        adr.updated_at = datetime.utcnow().isoformat()
        self._adrs[adr.id] = adr

    def get(self, adr_id: str) -> Optional[ArchitectureDecisionRecord]:
        return self._adrs.get(adr_id)

    def get_by_number(self, number: int) -> Optional[ArchitectureDecisionRecord]:
        for adr in self._adrs.values():
            if adr.number == number:
                return adr
        return None

    def list_all(self, status: Optional[ADRStatus] = None, category: Optional[ADRCategory] = None) -> list[ArchitectureDecisionRecord]:
        results = list(self._adrs.values())
        if status:
            results = [a for a in results if a.status == status]
        if category:
            results = [a for a in results if a.category == category]
        return sorted(results, key=lambda a: a.number)

    def search(self, query: str) -> list[ArchitectureDecisionRecord]:
        q = query.lower()
        results = []
        for adr in self._adrs.values():
            searchable = f"{adr.title} {adr.context} {adr.decision} {' '.join(adr.tags)}".lower()
            if q in searchable:
                results.append(adr)
        return results

    def next_number(self) -> int:
        self._counter += 1
        return self._counter


# =============================================================================
# ADR SERVICE
# =============================================================================

class ADRService:
    """Main service for managing Architecture Decision Records."""

    def __init__(self, store: Optional[ADRStore] = None):
        self.store = store or InMemoryADRStore()

    # -------------------------------------------------------------------------
    # CREATION
    # -------------------------------------------------------------------------

    def create_adr(self, title: str, author: str, category: ADRCategory,
                   context: str = "", impact: ImpactLevel = ImpactLevel.LOW,
                   tags: Optional[list[str]] = None) -> ArchitectureDecisionRecord:
        """Create a new ADR in draft status."""
        adr = ArchitectureDecisionRecord(
            number=self.store.next_number(),
            title=title,
            slug=self._slugify(title),
            author=author,
            owner=author,
            category=category,
            impact_level=impact,
            context=context,
            tags=tags or [],
        )
        self.store.save(adr)
        return adr

    def create_from_template(self, template_name: str, params: dict,
                             author: str) -> ArchitectureDecisionRecord:
        """Create ADR from a template."""
        adr = ADRTemplateLibrary.create_from_template(template_name, params)
        adr.number = self.store.next_number()
        adr.slug = self._slugify(adr.title)
        adr.author = author
        adr.owner = author
        self.store.save(adr)
        return adr

    # -------------------------------------------------------------------------
    # EDITING
    # -------------------------------------------------------------------------

    def add_option(self, adr_id: str, option: ADROption) -> ArchitectureDecisionRecord:
        adr = self._get_or_raise(adr_id)
        adr.options.append(option)
        self.store.save(adr)
        return adr

    def set_decision(self, adr_id: str, decision: str, rationale: str,
                     chosen_option_index: int) -> ArchitectureDecisionRecord:
        adr = self._get_or_raise(adr_id)
        adr.decision = decision
        adr.rationale = rationale
        if 0 <= chosen_option_index < len(adr.options):
            for i, opt in enumerate(adr.options):
                opt.chosen = (i == chosen_option_index)
        self.store.save(adr)
        return adr

    def add_consequence(self, adr_id: str, consequence: ADRConsequence) -> ArchitectureDecisionRecord:
        adr = self._get_or_raise(adr_id)
        adr.consequences.append(consequence)
        self.store.save(adr)
        return adr

    # -------------------------------------------------------------------------
    # LIFECYCLE
    # -------------------------------------------------------------------------

    def propose(self, adr_id: str, required_approvers: list[str]) -> ArchitectureDecisionRecord:
        """Move ADR from draft to proposed (ready for review)."""
        adr = self._get_or_raise(adr_id)
        if not adr.context or not adr.options or not adr.decision:
            raise ValueError("ADR must have context, options, and decision before proposing")
        adr.status = ADRStatus.PROPOSED
        adr.required_approvers = required_approvers
        self.store.save(adr)
        return adr

    def submit_review(self, adr_id: str, review: ADRReview) -> ArchitectureDecisionRecord:
        """Submit a review on an ADR."""
        adr = self._get_or_raise(adr_id)
        adr.reviews.append(review)
        if review.verdict == "approve" and review.reviewer_id not in adr.approvers:
            adr.approvers.append(review.reviewer_id)
        adr.status = ADRStatus.IN_REVIEW
        self.store.save(adr)
        return adr

    def accept(self, adr_id: str) -> ArchitectureDecisionRecord:
        """Accept an ADR (all required approvers must have approved)."""
        adr = self._get_or_raise(adr_id)
        missing = [a for a in adr.required_approvers if a not in adr.approvers]
        if missing:
            raise ValueError(f"Missing approvals from: {missing}")
        adr.status = ADRStatus.ACCEPTED
        adr.decided_at = datetime.utcnow().isoformat()
        # Set review date 6 months out by default
        adr.review_date = (datetime.utcnow() + timedelta(days=180)).isoformat()
        self.store.save(adr)
        return adr

    def deprecate(self, adr_id: str, reason: str) -> ArchitectureDecisionRecord:
        """Deprecate an ADR (no longer relevant)."""
        adr = self._get_or_raise(adr_id)
        adr.status = ADRStatus.DEPRECATED
        adr.consequences.append(ADRConsequence(
            description=f"Deprecated: {reason}",
            type="neutral"
        ))
        self.store.save(adr)
        return adr

    def supersede(self, old_adr_id: str, new_adr_id: str) -> tuple[ArchitectureDecisionRecord, ArchitectureDecisionRecord]:
        """Mark an ADR as superseded by a new one."""
        old_adr = self._get_or_raise(old_adr_id)
        new_adr = self._get_or_raise(new_adr_id)

        old_adr.status = ADRStatus.SUPERSEDED
        old_adr.links.append(ADRLink(
            target_adr_id=new_adr_id,
            relationship="superseded_by",
            description=f"Superseded by ADR-{new_adr.number:04d}: {new_adr.title}"
        ))

        new_adr.links.append(ADRLink(
            target_adr_id=old_adr_id,
            relationship="supersedes",
            description=f"Supersedes ADR-{old_adr.number:04d}: {old_adr.title}"
        ))

        self.store.save(old_adr)
        self.store.save(new_adr)
        return old_adr, new_adr

    # -------------------------------------------------------------------------
    # LINKING
    # -------------------------------------------------------------------------

    def link_adrs(self, adr_id: str, target_id: str, relationship: str,
                  description: str = "") -> ArchitectureDecisionRecord:
        """Create a bidirectional link between ADRs."""
        adr = self._get_or_raise(adr_id)
        target = self._get_or_raise(target_id)

        inverse_relationships = {
            "depends_on": "depended_on_by",
            "depended_on_by": "depends_on",
            "related_to": "related_to",
            "conflicts_with": "conflicts_with",
        }

        adr.links.append(ADRLink(target_adr_id=target_id, relationship=relationship, description=description))
        inverse = inverse_relationships.get(relationship, "related_to")
        target.links.append(ADRLink(target_adr_id=adr_id, relationship=inverse, description=description))

        self.store.save(adr)
        self.store.save(target)
        return adr

    # -------------------------------------------------------------------------
    # SEARCH & DISCOVERY
    # -------------------------------------------------------------------------

    def search(self, query: str) -> list[ArchitectureDecisionRecord]:
        return self.store.search(query)

    def list_by_category(self, category: ADRCategory) -> list[ArchitectureDecisionRecord]:
        return self.store.list_all(category=category)

    def list_active(self) -> list[ArchitectureDecisionRecord]:
        return self.store.list_all(status=ADRStatus.ACCEPTED)

    def list_needing_review(self) -> list[ArchitectureDecisionRecord]:
        """Find ADRs past their review date."""
        now = datetime.utcnow()
        results = []
        for adr in self.store.list_all(status=ADRStatus.ACCEPTED):
            if adr.review_date:
                review_date = datetime.fromisoformat(adr.review_date)
                if now > review_date:
                    results.append(adr)
        return results

    def get_decision_graph(self, adr_id: str, depth: int = 2) -> dict:
        """Get the graph of related decisions."""
        visited = set()
        graph = {"nodes": [], "edges": []}

        def traverse(current_id: str, current_depth: int):
            if current_id in visited or current_depth > depth:
                return
            visited.add(current_id)
            adr = self.store.get(current_id)
            if not adr:
                return
            graph["nodes"].append({
                "id": adr.id,
                "number": adr.number,
                "title": adr.title,
                "status": adr.status.value,
            })
            for link in adr.links:
                graph["edges"].append({
                    "source": current_id,
                    "target": link.target_adr_id,
                    "relationship": link.relationship,
                })
                traverse(link.target_adr_id, current_depth + 1)

        traverse(adr_id, 0)
        return graph

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    def export_markdown(self, adr_id: str) -> str:
        """Export single ADR as markdown."""
        adr = self._get_or_raise(adr_id)
        return adr.to_markdown()

    def export_index(self) -> str:
        """Generate an index of all ADRs."""
        lines = ["# Architecture Decision Records Index", ""]
        lines.append("| # | Title | Status | Category | Impact | Date |")
        lines.append("|---|-------|--------|----------|--------|------|")
        for adr in self.store.list_all():
            lines.append(
                f"| {adr.number:04d} | {adr.title} | {adr.status.value} | "
                f"{adr.category.value} | {adr.impact_level.value} | {adr.created_at[:10]} |"
            )
        return "\n".join(lines)

    def export_all_markdown(self) -> dict[str, str]:
        """Export all ADRs as a dict of filename -> markdown content."""
        exports = {}
        for adr in self.store.list_all():
            filename = f"ADR-{adr.number:04d}-{adr.slug}.md"
            exports[filename] = adr.to_markdown()
        exports["INDEX.md"] = self.export_index()
        return exports

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _get_or_raise(self, adr_id: str) -> ArchitectureDecisionRecord:
        adr = self.store.get(adr_id)
        if not adr:
            raise ValueError(f"ADR {adr_id} not found")
        return adr

    @staticmethod
    def _slugify(text: str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug[:60]


# =============================================================================
# DEMONSTRATION
# =============================================================================

def demo():
    print("=" * 70)
    print("ADR SYSTEM - DEMONSTRATION")
    print("=" * 70)

    service = ADRService()

    # Create ADR from template
    print("\n--- Creating ADR from 'model_selection' template ---")
    adr1 = service.create_from_template(
        "model_selection",
        {
            "model_type": "LLM",
            "use_case": "customer support chatbot",
            "requirements": "low latency, high accuracy on support queries, PII handling",
            "scale": "50,000",
        },
        author="alice@company.com"
    )

    # Add options
    service.add_option(adr1.id, ADROption(
        name="GPT-4o",
        description="OpenAI's flagship model via API",
        pros=["Highest accuracy", "Strong instruction following", "Good at multi-turn"],
        cons=["Higher cost ($5/1M input tokens)", "Data sent to OpenAI", "Rate limits"],
        estimated_cost="$15,000/month at 50k req/day",
    ))
    service.add_option(adr1.id, ADROption(
        name="Claude Sonnet 4",
        description="Anthropic's balanced model",
        pros=["Strong safety guardrails", "Good accuracy", "Competitive pricing"],
        cons=["Slightly lower throughput", "Newer, less battle-tested at scale"],
        estimated_cost="$12,000/month at 50k req/day",
    ))
    service.add_option(adr1.id, ADROption(
        name="Self-hosted Llama 3.1 70B",
        description="Meta's open model hosted on internal infrastructure",
        pros=["No data leaves org", "No per-token cost", "Full control"],
        cons=["High infra cost", "Operational burden", "Lower accuracy than GPT-4o"],
        estimated_cost="$25,000/month (GPU infrastructure)",
    ))

    # Make decision
    service.set_decision(
        adr1.id,
        decision="Use GPT-4o via Azure OpenAI Service for the customer support chatbot",
        rationale="Azure OpenAI provides GPT-4o with enterprise data protection guarantees. "
                  "Data stays within our Azure tenant. Accuracy requirements are best met by GPT-4o. "
                  "Cost is acceptable given the business impact of 40% ticket deflection.",
        chosen_option_index=0
    )

    service.add_consequence(adr1.id, ADRConsequence(
        description="Monthly AI cost of ~$15k added to support team budget",
        type="negative",
        mitigation="Implement response caching for common queries (est. 30% cost reduction)",
    ))
    service.add_consequence(adr1.id, ADRConsequence(
        description="40% reduction in L1 support tickets",
        type="positive",
    ))

    # Propose and review
    service.propose(adr1.id, required_approvers=["bob@company.com", "carol@company.com"])

    service.submit_review(adr1.id, ADRReview(
        reviewer_id="bob@company.com",
        reviewer_name="Bob (Security)",
        verdict="approve",
        comments="Azure OpenAI meets our data residency requirements. Approved.",
    ))
    service.submit_review(adr1.id, ADRReview(
        reviewer_id="carol@company.com",
        reviewer_name="Carol (ML Engineering)",
        verdict="approve",
        comments="GPT-4o is the right choice for this accuracy requirement. Consider fallback to 4o-mini for simple queries.",
    ))

    service.accept(adr1.id)

    # Create a second ADR
    print("\n--- Creating second ADR (agent architecture) ---")
    adr2 = service.create_from_template(
        "agent_architecture",
        {
            "use_case": "automated incident response",
            "capabilities": "diagnose incidents, suggest remediation, execute approved runbooks",
            "constraints": "must have human approval for destructive actions, max 5 tool calls per chain",
        },
        author="dave@company.com"
    )
    service.add_option(adr2.id, ADROption(
        name="Single agent with tool access",
        description="One agent with access to all diagnostic and remediation tools",
        pros=["Simple architecture", "Low latency"],
        cons=["Large blast radius", "Hard to scope permissions"],
    ))
    service.add_option(adr2.id, ADROption(
        name="Multi-agent with supervisor",
        description="Specialist agents (diagnostic, remediation) coordinated by supervisor",
        pros=["Scoped permissions per agent", "Clear responsibility boundaries"],
        cons=["Higher complexity", "More latency", "Coordination overhead"],
    ))
    service.set_decision(
        adr2.id,
        decision="Use multi-agent architecture with supervisor pattern",
        rationale="The blast radius of incident response tooling requires strict permission scoping.",
        chosen_option_index=1
    )
    service.propose(adr2.id, required_approvers=["alice@company.com"])
    service.submit_review(adr2.id, ADRReview(
        reviewer_id="alice@company.com", reviewer_name="Alice (Chief Architect)",
        verdict="approve", comments="Agreed. Supervisor pattern is correct for this risk level."
    ))
    service.accept(adr2.id)

    # Link ADRs
    service.link_adrs(adr1.id, adr2.id, "related_to", "Both serve customer-facing automation")

    # Export
    print("\n--- ADR Index ---")
    print(service.export_index())

    print("\n--- ADR-0001 Markdown Export (truncated) ---")
    md = service.export_markdown(adr1.id)
    print(md[:1500] + "\n...")

    # Decision graph
    print("\n--- Decision Graph from ADR-0001 ---")
    graph = service.get_decision_graph(adr1.id)
    print(f"  Nodes: {len(graph['nodes'])}")
    for edge in graph["edges"]:
        print(f"  Edge: {edge['relationship']}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    demo()
