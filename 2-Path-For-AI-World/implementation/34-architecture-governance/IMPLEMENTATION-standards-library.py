"""
Platform Standards Library

Manages AI platform standards:
- Standard definition and schema
- Categorization and versioning
- Compliance checking automation
- Exception management
- Adoption tracking
- Communication and training
"""

import uuid
import re
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable


# =============================================================================
# ENUMS
# =============================================================================

class StandardCategory(Enum):
    MODEL_USAGE = "model_usage"
    DATA_HANDLING = "data_handling"
    SECURITY = "security"
    OBSERVABILITY = "observability"
    DEPLOYMENT = "deployment"
    EVALUATION = "evaluation"
    COST = "cost"
    AGENT_DESIGN = "agent_design"
    PRIVACY = "privacy"
    DOCUMENTATION = "documentation"

class StandardSeverity(Enum):
    REQUIRED = "required"         # Must comply, blocks deployment
    RECOMMENDED = "recommended"   # Should comply, flagged but doesn't block
    OPTIONAL = "optional"         # Nice to have, informational

class StandardStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"

class ComplianceStatus(Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    EXCEPTION_GRANTED = "exception_granted"
    NOT_APPLICABLE = "not_applicable"
    NOT_ASSESSED = "not_assessed"

class ExceptionStatus(Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class StandardVersion:
    """A version of a standard."""
    version: str
    changes: str
    effective_date: str
    author: str
    breaking: bool = False


@dataclass
class ComplianceCheck:
    """Automated compliance check definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    check_type: str = "automated"  # automated, manual, hybrid
    implementation: str = ""  # Code/query that performs the check
    remediation_guide: str = ""  # How to fix non-compliance
    false_positive_guidance: str = ""


@dataclass
class Standard:
    """A platform standard definition."""
    id: str = ""  # STD-{category}-{number}
    title: str = ""
    category: StandardCategory = StandardCategory.MODEL_USAGE
    severity: StandardSeverity = StandardSeverity.REQUIRED
    status: StandardStatus = StandardStatus.DRAFT

    # Content
    description: str = ""
    rationale: str = ""
    implementation_guide: str = ""
    examples: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)

    # Verification
    compliance_checks: list[ComplianceCheck] = field(default_factory=list)
    verification_method: str = ""  # How compliance is verified

    # Metadata
    author: str = ""
    owner: str = ""  # Team/person responsible for maintaining
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    effective_date: Optional[str] = None
    review_date: Optional[str] = None
    version: str = "1.0"
    versions: list[StandardVersion] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Scope
    applies_to_tiers: list[int] = field(default_factory=lambda: [1, 2, 3])
    applies_to_teams: list[str] = field(default_factory=list)  # Empty = all teams

    # Exceptions
    exception_process: str = ""  # How to request an exception
    max_exception_duration_days: int = 90

    # Related
    related_standards: list[str] = field(default_factory=list)
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None


@dataclass
class StandardException:
    """An exception (bypass) to a standard."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    standard_id: str = ""
    system_id: str = ""
    system_name: str = ""
    requestor: str = ""
    reason: str = ""
    risk_mitigation: str = ""  # What alternative controls are in place
    status: ExceptionStatus = ExceptionStatus.REQUESTED
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    expires_at: Optional[str] = None
    review_notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ComplianceResult:
    """Result of a compliance check for a system."""
    standard_id: str = ""
    system_id: str = ""
    system_name: str = ""
    status: ComplianceStatus = ComplianceStatus.NOT_ASSESSED
    details: str = ""
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    evidence: str = ""
    remediation_needed: str = ""


@dataclass
class AdoptionMetric:
    """Tracks adoption of a standard across the organization."""
    standard_id: str = ""
    total_systems: int = 0
    compliant: int = 0
    non_compliant: int = 0
    exceptions: int = 0
    not_assessed: int = 0
    adoption_rate: float = 0.0
    trend: str = ""  # improving, stable, declining
    measured_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# DEFAULT STANDARDS LIBRARY
# =============================================================================

DEFAULT_STANDARDS: list[dict] = [
    # --- MODEL USAGE ---
    {
        "id": "STD-MDL-001",
        "title": "Approved Model Registry",
        "category": "model_usage",
        "severity": "required",
        "description": "All AI systems must use models from the approved model registry. No unapproved models in production.",
        "rationale": "Ensures security review, license compliance, cost control, and data handling guarantees for all models.",
        "implementation_guide": "Use the platform's model gateway which only routes to approved models. Direct API calls to model providers are blocked by network policy.",
        "examples": ["Use model_gateway.complete(model='gpt-4o', ...) instead of direct OpenAI client"],
        "anti_patterns": ["Direct API calls to model providers bypassing the gateway", "Using models not in registry even in staging"],
        "applies_to_tiers": [1, 2, 3],
    },
    {
        "id": "STD-MDL-002",
        "title": "Model Response Caching",
        "category": "model_usage",
        "severity": "recommended",
        "description": "Implement semantic caching for model responses where deterministic outputs are acceptable.",
        "rationale": "Reduces cost by 20-40% and improves latency for repeated/similar queries.",
        "implementation_guide": "Use the platform's semantic cache layer. Configure TTL based on content freshness requirements.",
        "applies_to_tiers": [1, 2],
    },
    {
        "id": "STD-MDL-003",
        "title": "Model Fallback Configuration",
        "category": "model_usage",
        "severity": "required",
        "description": "All production AI systems must have a fallback model configured for resilience.",
        "rationale": "Model providers have outages. Fallback ensures service continuity.",
        "implementation_guide": "Configure primary and fallback models in the gateway. Fallback triggers on 5xx errors or timeout.",
        "applies_to_tiers": [1, 2],
    },
    # --- SECURITY ---
    {
        "id": "STD-SEC-001",
        "title": "AI Endpoint Authentication",
        "category": "security",
        "severity": "required",
        "description": "All AI system endpoints must require authentication. No anonymous access to AI capabilities.",
        "rationale": "Prevents abuse, enables audit trails, supports rate limiting per identity.",
        "implementation_guide": "Use platform OAuth2/OIDC middleware. All requests must have valid bearer token.",
        "applies_to_tiers": [1, 2, 3],
    },
    {
        "id": "STD-SEC-002",
        "title": "Prompt Injection Mitigation",
        "category": "security",
        "severity": "required",
        "description": "All systems accepting user input that is passed to LLMs must implement prompt injection mitigations.",
        "rationale": "Prompt injection is the #1 AI-specific vulnerability. Defense in depth required.",
        "implementation_guide": "1) Separate system/user prompts clearly. 2) Input sanitization. 3) Output validation. 4) Canary token detection. 5) Instruction hierarchy enforcement.",
        "examples": ["Use platform's PromptGuard middleware for automatic injection detection"],
        "anti_patterns": ["Concatenating user input directly into system prompts", "Trusting model output without validation"],
        "applies_to_tiers": [1, 2, 3],
    },
    {
        "id": "STD-SEC-003",
        "title": "Tool Invocation Audit Logging",
        "category": "security",
        "severity": "required",
        "description": "All tool/function calls made by AI agents must be logged with full context.",
        "rationale": "Enables incident investigation, supports compliance audits, detects anomalous behavior.",
        "implementation_guide": "Use structured logging: {timestamp, agent_id, tool_name, parameters (redacted), result_status, user_context}",
        "applies_to_tiers": [1, 2, 3],
    },
    # --- OBSERVABILITY ---
    {
        "id": "STD-OBS-001",
        "title": "Distributed Tracing for LLM Calls",
        "category": "observability",
        "severity": "required",
        "description": "All LLM interactions must be captured in distributed traces with token counts, latency, and model info.",
        "rationale": "Essential for debugging, performance analysis, and cost attribution.",
        "implementation_guide": "Use OpenTelemetry with the AI semantic conventions. Platform SDK handles this automatically.",
        "applies_to_tiers": [1, 2, 3],
    },
    {
        "id": "STD-OBS-002",
        "title": "Quality Metrics in Production",
        "category": "observability",
        "severity": "required",
        "description": "Production AI systems must track quality metrics (not just operational metrics).",
        "rationale": "Operational health != output quality. Must detect quality degradation.",
        "implementation_guide": "Implement sampling-based evaluation in production. Track: relevance scores, hallucination rates, user satisfaction.",
        "applies_to_tiers": [1, 2],
    },
    # --- EVALUATION ---
    {
        "id": "STD-EVL-001",
        "title": "Evaluation Suite Required",
        "category": "evaluation",
        "severity": "required",
        "description": "Every AI system must have a comprehensive evaluation suite that runs in CI/CD.",
        "rationale": "Cannot deploy safely without knowing if quality meets bar.",
        "implementation_guide": "Minimum: 100 test cases covering happy path, edge cases, adversarial inputs. Must pass before merge.",
        "applies_to_tiers": [1, 2, 3],
    },
    {
        "id": "STD-EVL-002",
        "title": "Regression Threshold Enforcement",
        "category": "evaluation",
        "severity": "required",
        "description": "CI/CD must block deployments that regress eval scores beyond defined threshold.",
        "rationale": "Prevents shipping quality regressions to production.",
        "implementation_guide": "Configure eval gate in pipeline: block if score drops >5% on any metric or >2% overall.",
        "applies_to_tiers": [1, 2],
    },
    # --- DATA HANDLING ---
    {
        "id": "STD-DAT-001",
        "title": "PII Encryption at Rest",
        "category": "data_handling",
        "severity": "required",
        "description": "Any PII stored by AI systems (logs, vector stores, caches) must be encrypted at rest.",
        "rationale": "Regulatory requirement (GDPR, CCPA) and security best practice.",
        "implementation_guide": "Use platform-managed encryption. Vector stores use envelope encryption with customer-managed keys for Tier 1.",
        "applies_to_tiers": [1, 2, 3],
    },
    {
        "id": "STD-DAT-002",
        "title": "Data Retention Policy",
        "category": "data_handling",
        "severity": "required",
        "description": "All AI system data stores must have defined retention policies with automated enforcement.",
        "rationale": "Prevents unbounded data growth, supports right-to-deletion, reduces storage costs.",
        "implementation_guide": "Define retention in system config. Platform enforces TTL. Conversation logs: 90 days. Eval data: 1 year. Audit logs: 7 years.",
        "applies_to_tiers": [1, 2, 3],
    },
    # --- DEPLOYMENT ---
    {
        "id": "STD-DEP-001",
        "title": "Progressive Deployment Required",
        "category": "deployment",
        "severity": "required",
        "description": "AI systems must use progressive deployment (canary/blue-green) for production changes.",
        "rationale": "AI behavior changes are hard to predict. Progressive rollout limits blast radius.",
        "implementation_guide": "Use platform's deployment controller: 1% -> 10% -> 50% -> 100% with automated rollback on metric degradation.",
        "applies_to_tiers": [1, 2],
    },
    {
        "id": "STD-DEP-002",
        "title": "Feature Flags for AI Features",
        "category": "deployment",
        "severity": "recommended",
        "description": "New AI features should be behind feature flags for controlled rollout and instant disable.",
        "rationale": "Enables instant rollback without deployment, supports A/B testing, controls blast radius.",
        "implementation_guide": "Use platform feature flag service. AI features default to off, progressively enabled.",
        "applies_to_tiers": [1, 2, 3],
    },
    # --- AGENT DESIGN ---
    {
        "id": "STD-AGT-001",
        "title": "Agent Conversation Depth Limits",
        "category": "agent_design",
        "severity": "required",
        "description": "AI agents must have configured maximum conversation depth (turns) and cost ceiling.",
        "rationale": "Prevents runaway agent loops, controls costs, ensures eventual termination.",
        "implementation_guide": "Configure max_turns (default: 10) and max_cost_usd (default: $1) per agent invocation. Platform enforces.",
        "applies_to_tiers": [1, 2, 3],
    },
    {
        "id": "STD-AGT-002",
        "title": "Agent Tool Scoping (Least Privilege)",
        "category": "agent_design",
        "severity": "required",
        "description": "Agents must only have access to the minimum set of tools required for their function.",
        "rationale": "Reduces blast radius of compromised/malfunctioning agents.",
        "implementation_guide": "Define tool allowlist per agent. Use platform's capability-based security model.",
        "applies_to_tiers": [1, 2, 3],
    },
    # --- COST ---
    {
        "id": "STD-CST-001",
        "title": "Cost Budget and Alerting",
        "category": "cost",
        "severity": "required",
        "description": "All AI systems must have a defined monthly cost budget with alerts at 50%, 80%, and 100%.",
        "rationale": "AI costs can spike unexpectedly. Early warning prevents budget overruns.",
        "implementation_guide": "Set budget in platform config. Alerts go to team channel and owner. 100% triggers rate limiting.",
        "applies_to_tiers": [1, 2, 3],
    },
]


# =============================================================================
# STANDARDS LIBRARY SERVICE
# =============================================================================

class StandardsLibraryService:
    """Manages the platform standards library."""

    def __init__(self):
        self._standards: dict[str, Standard] = {}
        self._exceptions: dict[str, StandardException] = {}
        self._compliance_results: list[ComplianceResult] = []
        self._load_defaults()

    def _load_defaults(self):
        for std_def in DEFAULT_STANDARDS:
            std = Standard(
                id=std_def["id"],
                title=std_def["title"],
                category=StandardCategory(std_def["category"]),
                severity=StandardSeverity(std_def["severity"]),
                status=StandardStatus.ACTIVE,
                description=std_def["description"],
                rationale=std_def.get("rationale", ""),
                implementation_guide=std_def.get("implementation_guide", ""),
                examples=std_def.get("examples", []),
                anti_patterns=std_def.get("anti_patterns", []),
                applies_to_tiers=std_def.get("applies_to_tiers", [1, 2, 3]),
                effective_date=datetime.utcnow().isoformat(),
            )
            self._standards[std.id] = std

    # -------------------------------------------------------------------------
    # STANDARD CRUD
    # -------------------------------------------------------------------------

    def create_standard(self, standard: Standard) -> Standard:
        if not standard.id:
            cat_prefix = standard.category.value[:3].upper()
            existing = [s for s in self._standards.values() if s.category == standard.category]
            num = len(existing) + 1
            standard.id = f"STD-{cat_prefix}-{num:03d}"
        standard.status = StandardStatus.DRAFT
        self._standards[standard.id] = standard
        return standard

    def activate_standard(self, standard_id: str, effective_date: Optional[str] = None) -> Standard:
        std = self._get_or_raise(standard_id)
        std.status = StandardStatus.ACTIVE
        std.effective_date = effective_date or datetime.utcnow().isoformat()
        std.review_date = (datetime.utcnow() + timedelta(days=180)).isoformat()
        self._standards[standard_id] = std
        return std

    def deprecate_standard(self, standard_id: str, reason: str) -> Standard:
        std = self._get_or_raise(standard_id)
        std.status = StandardStatus.DEPRECATED
        self._standards[standard_id] = std
        return std

    def update_version(self, standard_id: str, changes: str, author: str,
                       breaking: bool = False) -> Standard:
        std = self._get_or_raise(standard_id)
        parts = std.version.split(".")
        if breaking:
            new_version = f"{int(parts[0]) + 1}.0"
        else:
            new_version = f"{parts[0]}.{int(parts[1]) + 1}"
        std.versions.append(StandardVersion(
            version=std.version, changes=changes, effective_date=datetime.utcnow().isoformat(),
            author=author, breaking=breaking
        ))
        std.version = new_version
        self._standards[standard_id] = std
        return std

    # -------------------------------------------------------------------------
    # QUERY
    # -------------------------------------------------------------------------

    def get_standard(self, standard_id: str) -> Standard:
        return self._get_or_raise(standard_id)

    def list_standards(self, category: Optional[StandardCategory] = None,
                       severity: Optional[StandardSeverity] = None,
                       status: Optional[StandardStatus] = None) -> list[Standard]:
        results = list(self._standards.values())
        if category:
            results = [s for s in results if s.category == category]
        if severity:
            results = [s for s in results if s.severity == severity]
        if status:
            results = [s for s in results if s.status == status]
        return sorted(results, key=lambda s: s.id)

    def get_applicable_standards(self, risk_tier: int) -> list[Standard]:
        """Get standards applicable to a given risk tier."""
        return [s for s in self._standards.values()
                if s.status == StandardStatus.ACTIVE and risk_tier in s.applies_to_tiers]

    # -------------------------------------------------------------------------
    # COMPLIANCE CHECKING
    # -------------------------------------------------------------------------

    def check_compliance(self, system_id: str, system_name: str, risk_tier: int,
                         system_config: dict) -> list[ComplianceResult]:
        """Run compliance checks for a system against applicable standards."""
        applicable = self.get_applicable_standards(risk_tier)
        results = []

        for std in applicable:
            # Check if there's an active exception
            exception = self._get_active_exception(std.id, system_id)
            if exception:
                results.append(ComplianceResult(
                    standard_id=std.id, system_id=system_id, system_name=system_name,
                    status=ComplianceStatus.EXCEPTION_GRANTED,
                    details=f"Exception granted until {exception.expires_at}: {exception.reason}",
                ))
                continue

            # Run automated check
            result = self._run_compliance_check(std, system_config)
            result.system_id = system_id
            result.system_name = system_name
            results.append(result)

        self._compliance_results.extend(results)
        return results

    def _run_compliance_check(self, standard: Standard, config: dict) -> ComplianceResult:
        """Run a compliance check. In production, these integrate with real systems."""
        result = ComplianceResult(standard_id=standard.id)

        # Example automated checks based on config
        if standard.id == "STD-MDL-001":
            models = config.get("models", [])
            approved = {"gpt-4o", "gpt-4o-mini", "claude-sonnet-4", "claude-haiku-35"}
            unapproved = [m for m in models if m not in approved]
            if not models:
                result.status = ComplianceStatus.NOT_ASSESSED
                result.details = "No models declared in config"
            elif unapproved:
                result.status = ComplianceStatus.NON_COMPLIANT
                result.details = f"Unapproved models: {unapproved}"
                result.remediation_needed = "Switch to approved models or request exception"
            else:
                result.status = ComplianceStatus.COMPLIANT
                result.details = f"All models approved: {models}"

        elif standard.id == "STD-SEC-001":
            if config.get("auth_enabled", False):
                result.status = ComplianceStatus.COMPLIANT
            else:
                result.status = ComplianceStatus.NON_COMPLIANT
                result.remediation_needed = "Enable authentication middleware"

        elif standard.id == "STD-AGT-001":
            if not config.get("uses_agents", False):
                result.status = ComplianceStatus.NOT_APPLICABLE
            elif config.get("max_turns") and config.get("max_cost_usd"):
                result.status = ComplianceStatus.COMPLIANT
            else:
                result.status = ComplianceStatus.NON_COMPLIANT
                result.remediation_needed = "Configure max_turns and max_cost_usd"

        elif standard.id == "STD-CST-001":
            if config.get("cost_budget") and config.get("cost_alerts"):
                result.status = ComplianceStatus.COMPLIANT
            else:
                result.status = ComplianceStatus.NON_COMPLIANT
                result.remediation_needed = "Define cost budget and configure alerts"

        else:
            # Default: needs manual assessment
            result.status = ComplianceStatus.NOT_ASSESSED
            result.details = "Requires manual verification"

        return result

    # -------------------------------------------------------------------------
    # EXCEPTION MANAGEMENT
    # -------------------------------------------------------------------------

    def request_exception(self, standard_id: str, system_id: str, system_name: str,
                          requestor: str, reason: str, risk_mitigation: str,
                          duration_days: int = 90) -> StandardException:
        """Request an exception to a standard."""
        std = self._get_or_raise(standard_id)
        if duration_days > std.max_exception_duration_days:
            raise ValueError(f"Max exception duration is {std.max_exception_duration_days} days")

        exception = StandardException(
            standard_id=standard_id,
            system_id=system_id,
            system_name=system_name,
            requestor=requestor,
            reason=reason,
            risk_mitigation=risk_mitigation,
            expires_at=(datetime.utcnow() + timedelta(days=duration_days)).isoformat(),
        )
        self._exceptions[exception.id] = exception
        return exception

    def approve_exception(self, exception_id: str, approved_by: str,
                          notes: str = "") -> StandardException:
        exc = self._exceptions.get(exception_id)
        if not exc:
            raise ValueError(f"Exception {exception_id} not found")
        exc.status = ExceptionStatus.APPROVED
        exc.approved_by = approved_by
        exc.approved_at = datetime.utcnow().isoformat()
        exc.review_notes = notes
        return exc

    def reject_exception(self, exception_id: str, rejected_by: str,
                         notes: str = "") -> StandardException:
        exc = self._exceptions.get(exception_id)
        if not exc:
            raise ValueError(f"Exception {exception_id} not found")
        exc.status = ExceptionStatus.REJECTED
        exc.review_notes = notes
        return exc

    def _get_active_exception(self, standard_id: str, system_id: str) -> Optional[StandardException]:
        now = datetime.utcnow()
        for exc in self._exceptions.values():
            if (exc.standard_id == standard_id and exc.system_id == system_id
                and exc.status == ExceptionStatus.APPROVED and exc.expires_at):
                if datetime.fromisoformat(exc.expires_at) > now:
                    return exc
        return None

    # -------------------------------------------------------------------------
    # ADOPTION TRACKING
    # -------------------------------------------------------------------------

    def get_adoption_metrics(self) -> list[AdoptionMetric]:
        """Calculate adoption metrics for all active standards."""
        metrics = []
        # Group compliance results by standard
        standard_results: dict[str, list[ComplianceResult]] = {}
        for result in self._compliance_results:
            standard_results.setdefault(result.standard_id, []).append(result)

        for std_id, results in standard_results.items():
            # Deduplicate by system (latest result per system)
            latest_by_system: dict[str, ComplianceResult] = {}
            for r in results:
                if r.system_id not in latest_by_system or r.checked_at > latest_by_system[r.system_id].checked_at:
                    latest_by_system[r.system_id] = r

            total = len(latest_by_system)
            compliant = sum(1 for r in latest_by_system.values()
                           if r.status in (ComplianceStatus.COMPLIANT, ComplianceStatus.EXCEPTION_GRANTED, ComplianceStatus.NOT_APPLICABLE))
            non_compliant = sum(1 for r in latest_by_system.values() if r.status == ComplianceStatus.NON_COMPLIANT)
            exceptions = sum(1 for r in latest_by_system.values() if r.status == ComplianceStatus.EXCEPTION_GRANTED)
            not_assessed = sum(1 for r in latest_by_system.values() if r.status == ComplianceStatus.NOT_ASSESSED)

            metrics.append(AdoptionMetric(
                standard_id=std_id,
                total_systems=total,
                compliant=compliant,
                non_compliant=non_compliant,
                exceptions=exceptions,
                not_assessed=not_assessed,
                adoption_rate=round(compliant / total * 100, 1) if total > 0 else 0.0,
            ))

        return sorted(metrics, key=lambda m: m.adoption_rate)

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    def export_standards_catalog(self) -> str:
        """Export full standards catalog as markdown."""
        lines = ["# AI Platform Standards Catalog", ""]
        lines.append(f"*Generated: {datetime.utcnow().isoformat()[:10]}*\n")

        by_category: dict[StandardCategory, list[Standard]] = {}
        for std in self._standards.values():
            if std.status == StandardStatus.ACTIVE:
                by_category.setdefault(std.category, []).append(std)

        for category in StandardCategory:
            stds = by_category.get(category, [])
            if not stds:
                continue
            lines.append(f"## {category.value.replace('_', ' ').title()}")
            lines.append("")
            for std in sorted(stds, key=lambda s: s.id):
                severity_badge = {"required": "REQ", "recommended": "REC", "optional": "OPT"}[std.severity.value]
                lines.append(f"### [{severity_badge}] {std.id}: {std.title}")
                lines.append(f"\n{std.description}\n")
                if std.rationale:
                    lines.append(f"**Why**: {std.rationale}\n")
                if std.implementation_guide:
                    lines.append(f"**How**: {std.implementation_guide}\n")
                lines.append(f"*Applies to: Tier {', '.join(map(str, std.applies_to_tiers))} | Version: {std.version}*\n")
                lines.append("---\n")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _get_or_raise(self, standard_id: str) -> Standard:
        std = self._standards.get(standard_id)
        if not std:
            raise ValueError(f"Standard {standard_id} not found")
        return std


# =============================================================================
# DEMONSTRATION
# =============================================================================

def demo():
    print("=" * 70)
    print("PLATFORM STANDARDS LIBRARY - DEMONSTRATION")
    print("=" * 70)

    service = StandardsLibraryService()

    # List standards
    print("\n--- Active Standards ---")
    all_standards = service.list_standards(status=StandardStatus.ACTIVE)
    print(f"  Total active standards: {len(all_standards)}")
    for std in all_standards:
        print(f"  [{std.severity.value:11}] {std.id}: {std.title}")

    # Check compliance for a system
    print("\n--- Compliance Check: Trading Agent ---")
    trading_config = {
        "models": ["gpt-4o", "claude-sonnet-4"],
        "auth_enabled": True,
        "uses_agents": True,
        "max_turns": 5,
        "max_cost_usd": 2.0,
        "cost_budget": 15000,
        "cost_alerts": [50, 80, 100],
    }
    results = service.check_compliance("sys-001", "Trading Agent", 1, trading_config)
    for r in results:
        print(f"  [{r.status.value:20}] {r.standard_id}: {r.details[:60]}")

    # Check compliance for non-compliant system
    print("\n--- Compliance Check: Rogue System ---")
    rogue_config = {
        "models": ["llama-uncensored-7b"],
        "auth_enabled": False,
        "uses_agents": True,
        "cost_budget": None,
        "cost_alerts": None,
    }
    results2 = service.check_compliance("sys-002", "Rogue System", 2, rogue_config)
    non_compliant = [r for r in results2 if r.status == ComplianceStatus.NON_COMPLIANT]
    print(f"  Non-compliant: {len(non_compliant)} standards")
    for r in non_compliant:
        print(f"    {r.standard_id}: {r.remediation_needed}")

    # Request exception
    print("\n--- Exception Request ---")
    exc = service.request_exception(
        standard_id="STD-MDL-001",
        system_id="sys-003",
        system_name="Research Experiment",
        requestor="researcher@company.com",
        reason="Need to evaluate Llama 3.1 405B for potential addition to approved registry",
        risk_mitigation="Isolated environment, no production data, 30-day limit, no customer access",
        duration_days=30,
    )
    print(f"  Exception requested: {exc.id[:8]}... for {exc.standard_id}")
    service.approve_exception(exc.id, "chief_architect@company.com", "Approved for eval only")
    print(f"  Exception approved. Expires: {exc.expires_at[:10]}")

    # Adoption metrics
    print("\n--- Adoption Metrics ---")
    metrics = service.get_adoption_metrics()
    for m in metrics:
        bar = "#" * int(m.adoption_rate / 5)
        print(f"  {m.standard_id}: {m.adoption_rate:5.1f}% ({m.compliant}/{m.total_systems}) {bar}")

    # Export catalog (truncated)
    print("\n--- Standards Catalog (first 30 lines) ---")
    catalog = service.export_standards_catalog()
    for line in catalog.split("\n")[:30]:
        print(f"  {line}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    demo()
