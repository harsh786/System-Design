"""
AI Bill of Materials (AI-BOM) System
=====================================
Tracks all AI components, their versions, licenses, risks, and relationships.
Production-grade implementation for managing AI supply chain inventory.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# Core Enums and Types
# =============================================================================

class ComponentType(Enum):
    MODEL_PROVIDER = "model_provider"
    EMBEDDING_MODEL = "embedding_model"
    RERANKER = "reranker"
    VECTOR_DATABASE = "vector_database"
    PROMPT_TEMPLATE = "prompt_template"
    TOOL_SCHEMA = "tool_schema"
    MCP_SERVER = "mcp_server"
    A2A_AGENT = "a2a_agent"
    DATASET = "dataset"
    FINE_TUNED_MODEL = "fine_tuned_model"
    THIRD_PARTY_API = "third_party_api"
    OPEN_SOURCE_PACKAGE = "open_source_package"
    PLUGIN = "plugin"
    CLOUD_INFRASTRUCTURE = "cloud_infrastructure"


class RiskTier(Enum):
    CRITICAL = "critical"  # System cannot function without this
    HIGH = "high"          # Significant impact if unavailable
    MEDIUM = "medium"      # Degraded service without this
    LOW = "low"            # Minimal impact


class LicenseType(Enum):
    PROPRIETARY = "proprietary"
    APACHE_2 = "apache-2.0"
    MIT = "mit"
    GPL_3 = "gpl-3.0"
    LGPL = "lgpl"
    BSL = "bsl"
    CC_BY = "cc-by-4.0"
    CC_BY_SA = "cc-by-sa-4.0"
    CC_BY_NC = "cc-by-nc-4.0"
    OPENRAIL = "openrail"
    LLAMA_COMMUNITY = "llama-community"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class ComponentStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUNSET = "sunset"


class VulnerabilitySeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ComponentVersion:
    version: str
    registered_at: datetime
    registered_by: str
    change_reason: str
    artifact_hash: Optional[str] = None
    signature: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Vulnerability:
    id: str
    severity: VulnerabilitySeverity
    description: str
    discovered_at: datetime
    cve_id: Optional[str] = None
    remediation: Optional[str] = None
    affected_versions: list[str] = field(default_factory=list)
    is_resolved: bool = False


@dataclass
class LicenseInfo:
    license_type: LicenseType
    allows_commercial: bool
    requires_attribution: bool
    allows_modification: bool
    allows_distribution: bool
    restrictions: list[str] = field(default_factory=list)
    license_url: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None


@dataclass
class DependencyRelation:
    source_id: str
    target_id: str
    relation_type: str  # "depends_on", "embeds", "calls", "trains_on"
    is_required: bool = True
    description: str = ""


@dataclass
class BOMComponent:
    """Core unit in the AI Bill of Materials."""
    id: str
    name: str
    component_type: ComponentType
    provider: str
    current_version: str
    risk_tier: RiskTier
    status: ComponentStatus
    license_info: LicenseInfo
    owner_team: str
    owner_contact: str
    escalation_path: str
    deployment_region: str
    description: str = ""
    versions: list[ComponentVersion] = field(default_factory=list)
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_reviewed: Optional[datetime] = None
    next_review_due: Optional[datetime] = None
    exit_plan: Optional[str] = None
    fallback_component_id: Optional[str] = None

    @property
    def risk_score(self) -> float:
        """Calculate composite risk score (0-100)."""
        score = 0.0
        # Base risk from tier
        tier_scores = {RiskTier.CRITICAL: 40, RiskTier.HIGH: 30, RiskTier.MEDIUM: 20, RiskTier.LOW: 10}
        score += tier_scores.get(self.risk_tier, 10)
        # Vulnerability risk
        active_vulns = [v for v in self.vulnerabilities if not v.is_resolved]
        for v in active_vulns:
            vuln_scores = {
                VulnerabilitySeverity.CRITICAL: 25,
                VulnerabilitySeverity.HIGH: 15,
                VulnerabilitySeverity.MEDIUM: 8,
                VulnerabilitySeverity.LOW: 3,
                VulnerabilitySeverity.INFORMATIONAL: 1,
            }
            score += vuln_scores.get(v.severity, 0)
        # License risk
        if self.license_info.license_type == LicenseType.UNKNOWN:
            score += 15
        if not self.license_info.allows_commercial:
            score += 20
        # Staleness risk
        if self.last_reviewed:
            days_since_review = (datetime.utcnow() - self.last_reviewed).days
            if days_since_review > 180:
                score += 10
            if days_since_review > 365:
                score += 10
        # No exit plan
        if not self.exit_plan and self.risk_tier in (RiskTier.CRITICAL, RiskTier.HIGH):
            score += 10
        # No fallback
        if not self.fallback_component_id and self.risk_tier == RiskTier.CRITICAL:
            score += 15
        return min(score, 100.0)


# =============================================================================
# BOM Storage Interface
# =============================================================================

class BOMStore(ABC):
    @abstractmethod
    def save_component(self, component: BOMComponent) -> None: ...
    @abstractmethod
    def get_component(self, component_id: str) -> Optional[BOMComponent]: ...
    @abstractmethod
    def list_components(self, filters: Optional[dict] = None) -> list[BOMComponent]: ...
    @abstractmethod
    def save_relation(self, relation: DependencyRelation) -> None: ...
    @abstractmethod
    def get_relations(self, component_id: str) -> list[DependencyRelation]: ...
    @abstractmethod
    def get_bom_snapshot(self) -> dict: ...


class InMemoryBOMStore(BOMStore):
    """In-memory implementation for demonstration. Replace with DB in production."""

    def __init__(self):
        self._components: dict[str, BOMComponent] = {}
        self._relations: list[DependencyRelation] = []
        self._history: list[dict] = []

    def save_component(self, component: BOMComponent) -> None:
        self._components[component.id] = component
        self._history.append({
            "action": "save_component",
            "component_id": component.id,
            "timestamp": datetime.utcnow().isoformat(),
            "version": component.current_version,
        })

    def get_component(self, component_id: str) -> Optional[BOMComponent]:
        return self._components.get(component_id)

    def list_components(self, filters: Optional[dict] = None) -> list[BOMComponent]:
        components = list(self._components.values())
        if not filters:
            return components
        if "component_type" in filters:
            components = [c for c in components if c.component_type == filters["component_type"]]
        if "risk_tier" in filters:
            components = [c for c in components if c.risk_tier == filters["risk_tier"]]
        if "status" in filters:
            components = [c for c in components if c.status == filters["status"]]
        if "provider" in filters:
            components = [c for c in components if c.provider == filters["provider"]]
        return components

    def save_relation(self, relation: DependencyRelation) -> None:
        self._relations.append(relation)

    def get_relations(self, component_id: str) -> list[DependencyRelation]:
        return [r for r in self._relations if r.source_id == component_id or r.target_id == component_id]

    def get_bom_snapshot(self) -> dict:
        return {
            "snapshot_time": datetime.utcnow().isoformat(),
            "total_components": len(self._components),
            "components": {cid: asdict(c) for cid, c in self._components.items()},
            "relations": [asdict(r) for r in self._relations],
        }


# =============================================================================
# AI-BOM Manager
# =============================================================================

class AIBillOfMaterials:
    """
    Central management system for AI Bill of Materials.
    Handles registration, tracking, risk scoring, and compliance.
    """

    def __init__(self, store: BOMStore):
        self.store = store
        self._change_listeners: list[callable] = []
        self._license_compatibility: dict[tuple, bool] = self._build_license_matrix()

    def _build_license_matrix(self) -> dict[tuple, bool]:
        """Define which licenses are compatible with commercial use."""
        compatible_pairs = {}
        commercial_ok = {LicenseType.APACHE_2, LicenseType.MIT, LicenseType.CC_BY, LicenseType.OPENRAIL}
        for lt in LicenseType:
            compatible_pairs[(lt, "commercial")] = lt in commercial_ok or lt == LicenseType.PROPRIETARY
        return compatible_pairs

    # -------------------------------------------------------------------------
    # Component Registration
    # -------------------------------------------------------------------------

    def register_component(
        self,
        name: str,
        component_type: ComponentType,
        provider: str,
        version: str,
        risk_tier: RiskTier,
        license_info: LicenseInfo,
        owner_team: str,
        owner_contact: str,
        escalation_path: str,
        deployment_region: str,
        registered_by: str,
        description: str = "",
        metadata: Optional[dict] = None,
        artifact_hash: Optional[str] = None,
    ) -> BOMComponent:
        """Register a new component in the AI-BOM."""
        component_id = f"{component_type.value}:{provider}:{name}:{version}"
        component_id_hash = hashlib.sha256(component_id.encode()).hexdigest()[:16]

        initial_version = ComponentVersion(
            version=version,
            registered_at=datetime.utcnow(),
            registered_by=registered_by,
            change_reason="Initial registration",
            artifact_hash=artifact_hash,
        )

        component = BOMComponent(
            id=component_id_hash,
            name=name,
            component_type=component_type,
            provider=provider,
            current_version=version,
            risk_tier=risk_tier,
            status=ComponentStatus.PENDING_REVIEW,
            license_info=license_info,
            owner_team=owner_team,
            owner_contact=owner_contact,
            escalation_path=escalation_path,
            deployment_region=deployment_region,
            description=description,
            versions=[initial_version],
            metadata=metadata or {},
            next_review_due=datetime.utcnow() + timedelta(days=90),
        )

        self.store.save_component(component)
        self._notify_change("component_registered", component)
        logger.info(f"Registered component: {name} ({component_type.value}) from {provider}")
        return component

    def update_component_version(
        self,
        component_id: str,
        new_version: str,
        updated_by: str,
        change_reason: str,
        artifact_hash: Optional[str] = None,
    ) -> BOMComponent:
        """Update a component to a new version."""
        component = self.store.get_component(component_id)
        if not component:
            raise ValueError(f"Component {component_id} not found")

        version_entry = ComponentVersion(
            version=new_version,
            registered_at=datetime.utcnow(),
            registered_by=updated_by,
            change_reason=change_reason,
            artifact_hash=artifact_hash,
        )
        component.versions.append(version_entry)
        component.current_version = new_version
        component.last_reviewed = datetime.utcnow()
        component.next_review_due = datetime.utcnow() + timedelta(days=90)

        self.store.save_component(component)
        self._notify_change("version_updated", component)
        logger.info(f"Updated {component.name} to version {new_version}")
        return component

    # -------------------------------------------------------------------------
    # Dependency Graph
    # -------------------------------------------------------------------------

    def add_dependency(
        self,
        source_id: str,
        target_id: str,
        relation_type: str = "depends_on",
        is_required: bool = True,
        description: str = "",
    ) -> DependencyRelation:
        """Register a dependency relationship between components."""
        relation = DependencyRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            is_required=is_required,
            description=description,
        )
        self.store.save_relation(relation)
        return relation

    def get_dependency_graph(self) -> dict:
        """Generate full dependency graph for visualization."""
        components = self.store.list_components()
        nodes = []
        edges = []

        for comp in components:
            nodes.append({
                "id": comp.id,
                "label": f"{comp.name} ({comp.provider})",
                "type": comp.component_type.value,
                "risk_tier": comp.risk_tier.value,
                "risk_score": comp.risk_score,
            })
            relations = self.store.get_relations(comp.id)
            for rel in relations:
                if rel.source_id == comp.id:
                    edges.append({
                        "source": rel.source_id,
                        "target": rel.target_id,
                        "type": rel.relation_type,
                        "required": rel.is_required,
                    })

        return {"nodes": nodes, "edges": edges}

    def get_blast_radius(self, component_id: str) -> list[str]:
        """Find all components that depend on the given component (transitively)."""
        affected = set()
        to_check = [component_id]
        all_components = self.store.list_components()

        while to_check:
            current = to_check.pop()
            for comp in all_components:
                relations = self.store.get_relations(comp.id)
                for rel in relations:
                    if rel.target_id == current and comp.id not in affected:
                        affected.add(comp.id)
                        to_check.append(comp.id)

        return list(affected)

    # -------------------------------------------------------------------------
    # Risk Scoring
    # -------------------------------------------------------------------------

    def get_risk_report(self) -> dict:
        """Generate comprehensive risk report across all components."""
        components = self.store.list_components()
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_components": len(components),
            "risk_summary": {
                "critical_risk": [],
                "high_risk": [],
                "medium_risk": [],
                "low_risk": [],
            },
            "overdue_reviews": [],
            "missing_exit_plans": [],
            "license_issues": [],
            "active_vulnerabilities": [],
            "overall_risk_score": 0.0,
        }

        total_score = 0.0
        for comp in components:
            score = comp.risk_score
            total_score += score

            entry = {"id": comp.id, "name": comp.name, "provider": comp.provider, "score": score}

            if score >= 70:
                report["risk_summary"]["critical_risk"].append(entry)
            elif score >= 50:
                report["risk_summary"]["high_risk"].append(entry)
            elif score >= 30:
                report["risk_summary"]["medium_risk"].append(entry)
            else:
                report["risk_summary"]["low_risk"].append(entry)

            # Overdue reviews
            if comp.next_review_due and comp.next_review_due < datetime.utcnow():
                report["overdue_reviews"].append(entry)

            # Missing exit plans
            if not comp.exit_plan and comp.risk_tier in (RiskTier.CRITICAL, RiskTier.HIGH):
                report["missing_exit_plans"].append(entry)

            # License issues
            if not comp.license_info.allows_commercial:
                report["license_issues"].append({
                    **entry,
                    "issue": "Does not allow commercial use",
                    "license": comp.license_info.license_type.value,
                })

            # Active vulnerabilities
            active_vulns = [v for v in comp.vulnerabilities if not v.is_resolved]
            for vuln in active_vulns:
                report["active_vulnerabilities"].append({
                    "component": comp.name,
                    "vulnerability_id": vuln.id,
                    "severity": vuln.severity.value,
                    "description": vuln.description,
                })

        report["overall_risk_score"] = total_score / len(components) if components else 0
        return report

    # -------------------------------------------------------------------------
    # License Compliance
    # -------------------------------------------------------------------------

    def check_license_compliance(self, use_case: str = "commercial") -> dict:
        """Check all components for license compliance with intended use."""
        components = self.store.list_components()
        issues = []
        compliant = []

        for comp in components:
            lic = comp.license_info
            is_compliant = True
            reasons = []

            if use_case == "commercial" and not lic.allows_commercial:
                is_compliant = False
                reasons.append(f"License {lic.license_type.value} does not allow commercial use")

            if lic.license_type == LicenseType.UNKNOWN:
                is_compliant = False
                reasons.append("License is unknown - requires review")

            if lic.license_type == LicenseType.GPL_3:
                is_compliant = False
                reasons.append("GPL-3.0 may impose copyleft requirements on your system")

            if lic.requires_attribution and "attribution" not in comp.metadata.get("compliance_actions", []):
                reasons.append("Attribution required but not documented as provided")

            if is_compliant:
                compliant.append(comp.name)
            else:
                issues.append({
                    "component": comp.name,
                    "provider": comp.provider,
                    "license": lic.license_type.value,
                    "issues": reasons,
                })

        return {
            "use_case": use_case,
            "total_components": len(components),
            "compliant_count": len(compliant),
            "issue_count": len(issues),
            "issues": issues,
            "compliant": compliant,
        }

    # -------------------------------------------------------------------------
    # Vulnerability Management
    # -------------------------------------------------------------------------

    def report_vulnerability(
        self,
        component_id: str,
        severity: VulnerabilitySeverity,
        description: str,
        cve_id: Optional[str] = None,
        affected_versions: Optional[list[str]] = None,
        remediation: Optional[str] = None,
    ) -> Vulnerability:
        """Report a vulnerability against a component."""
        component = self.store.get_component(component_id)
        if not component:
            raise ValueError(f"Component {component_id} not found")

        vuln = Vulnerability(
            id=f"VULN-{uuid4().hex[:8]}",
            severity=severity,
            description=description,
            discovered_at=datetime.utcnow(),
            cve_id=cve_id,
            remediation=remediation,
            affected_versions=affected_versions or [component.current_version],
        )
        component.vulnerabilities.append(vuln)
        self.store.save_component(component)
        self._notify_change("vulnerability_reported", component)

        if severity in (VulnerabilitySeverity.CRITICAL, VulnerabilitySeverity.HIGH):
            logger.critical(
                f"HIGH/CRITICAL vulnerability in {component.name}: {description}"
            )

        return vuln

    # -------------------------------------------------------------------------
    # BOM Export (SPDX / CycloneDX-style)
    # -------------------------------------------------------------------------

    def export_spdx(self) -> dict:
        """Export BOM in SPDX-like format for AI components."""
        components = self.store.list_components()
        return {
            "spdxVersion": "SPDX-2.3-AI-Extension",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": "AI-BOM-Export",
            "documentNamespace": f"https://ai-bom.example.com/{uuid4().hex}",
            "creationInfo": {
                "created": datetime.utcnow().isoformat(),
                "creators": ["Tool: AI-BOM-Manager"],
            },
            "packages": [
                {
                    "SPDXID": f"SPDXRef-{comp.id}",
                    "name": comp.name,
                    "versionInfo": comp.current_version,
                    "supplier": f"Organization: {comp.provider}",
                    "downloadLocation": comp.metadata.get("download_url", "NOASSERTION"),
                    "licenseConcluded": comp.license_info.license_type.value,
                    "copyrightText": "NOASSERTION",
                    "externalRefs": [
                        {
                            "referenceCategory": "AI-COMPONENT",
                            "referenceType": comp.component_type.value,
                            "referenceLocator": f"{comp.provider}/{comp.name}@{comp.current_version}",
                        }
                    ],
                    "annotations": [
                        {"annotationType": "RISK_TIER", "comment": comp.risk_tier.value},
                        {"annotationType": "RISK_SCORE", "comment": str(comp.risk_score)},
                    ],
                }
                for comp in components
            ],
        }

    def export_cyclonedx(self) -> dict:
        """Export BOM in CycloneDX-style format adapted for AI components."""
        components = self.store.list_components()
        all_relations = []
        for comp in components:
            all_relations.extend(self.store.get_relations(comp.id))

        # Deduplicate relations
        seen_relations = set()
        unique_relations = []
        for rel in all_relations:
            key = (rel.source_id, rel.target_id, rel.relation_type)
            if key not in seen_relations:
                seen_relations.add(key)
                unique_relations.append(rel)

        return {
            "bomFormat": "CycloneDX-AI",
            "specVersion": "1.5-AI",
            "version": 1,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "tools": [{"name": "AI-BOM-Manager", "version": "1.0.0"}],
            },
            "components": [
                {
                    "type": comp.component_type.value,
                    "bom-ref": comp.id,
                    "name": comp.name,
                    "version": comp.current_version,
                    "supplier": {"name": comp.provider},
                    "licenses": [{"license": {"id": comp.license_info.license_type.value}}],
                    "properties": [
                        {"name": "ai:risk-tier", "value": comp.risk_tier.value},
                        {"name": "ai:risk-score", "value": str(comp.risk_score)},
                        {"name": "ai:owner-team", "value": comp.owner_team},
                        {"name": "ai:deployment-region", "value": comp.deployment_region},
                        {"name": "ai:status", "value": comp.status.value},
                    ],
                }
                for comp in components
            ],
            "dependencies": [
                {"ref": rel.source_id, "dependsOn": [rel.target_id]}
                for rel in unique_relations
            ],
            "vulnerabilities": [
                {
                    "id": vuln.id,
                    "source": {"name": comp.name},
                    "ratings": [{"severity": vuln.severity.value}],
                    "description": vuln.description,
                    "recommendation": vuln.remediation or "No remediation documented",
                    "affects": [{"ref": comp.id, "versions": vuln.affected_versions}],
                }
                for comp in components
                for vuln in comp.vulnerabilities
                if not vuln.is_resolved
            ],
        }

    # -------------------------------------------------------------------------
    # BOM Comparison
    # -------------------------------------------------------------------------

    def compare_bom_snapshots(self, old_snapshot: dict, new_snapshot: dict) -> dict:
        """Compare two BOM snapshots to identify changes."""
        old_components = old_snapshot.get("components", {})
        new_components = new_snapshot.get("components", {})

        old_ids = set(old_components.keys())
        new_ids = set(new_components.keys())

        added = new_ids - old_ids
        removed = old_ids - new_ids
        common = old_ids & new_ids

        version_changes = []
        risk_changes = []

        for cid in common:
            old_c = old_components[cid]
            new_c = new_components[cid]
            if old_c.get("current_version") != new_c.get("current_version"):
                version_changes.append({
                    "component_id": cid,
                    "name": new_c.get("name"),
                    "old_version": old_c.get("current_version"),
                    "new_version": new_c.get("current_version"),
                })
            old_score = old_c.get("risk_score", 0)
            new_score = new_c.get("risk_score", 0)
            if abs(old_score - new_score) > 5:
                risk_changes.append({
                    "component_id": cid,
                    "name": new_c.get("name"),
                    "old_score": old_score,
                    "new_score": new_score,
                    "delta": new_score - old_score,
                })

        return {
            "comparison_time": datetime.utcnow().isoformat(),
            "added_components": list(added),
            "removed_components": list(removed),
            "version_changes": version_changes,
            "risk_score_changes": risk_changes,
            "total_changes": len(added) + len(removed) + len(version_changes),
        }

    # -------------------------------------------------------------------------
    # Change Notification
    # -------------------------------------------------------------------------

    def on_change(self, listener: callable) -> None:
        """Register a listener for BOM changes."""
        self._change_listeners.append(listener)

    def _notify_change(self, event_type: str, component: BOMComponent) -> None:
        for listener in self._change_listeners:
            try:
                listener(event_type, component)
            except Exception as e:
                logger.error(f"Change listener error: {e}")


# =============================================================================
# Example Usage
# =============================================================================

def demo():
    """Demonstrate AI-BOM system capabilities."""
    store = InMemoryBOMStore()
    bom = AIBillOfMaterials(store)

    # Register change listener
    bom.on_change(lambda event, comp: print(f"  [EVENT] {event}: {comp.name}"))

    print("=" * 60)
    print("AI Bill of Materials - Demo")
    print("=" * 60)

    # Register model provider
    gpt4 = bom.register_component(
        name="gpt-4-turbo",
        component_type=ComponentType.MODEL_PROVIDER,
        provider="OpenAI",
        version="gpt-4-turbo-2024-04-09",
        risk_tier=RiskTier.CRITICAL,
        license_info=LicenseInfo(
            license_type=LicenseType.PROPRIETARY,
            allows_commercial=True,
            requires_attribution=False,
            allows_modification=False,
            allows_distribution=False,
            restrictions=["No model weight access", "Subject to usage policies"],
        ),
        owner_team="AI Platform",
        owner_contact="ai-platform@company.com",
        escalation_path="ai-platform@company.com -> VP Engineering",
        deployment_region="us-east-1",
        registered_by="admin@company.com",
        description="Primary LLM for production inference",
        metadata={"cost_per_1k_input": 0.01, "cost_per_1k_output": 0.03},
    )

    # Register embedding model
    embeddings = bom.register_component(
        name="text-embedding-3-large",
        component_type=ComponentType.EMBEDDING_MODEL,
        provider="OpenAI",
        version="text-embedding-3-large-2024-01",
        risk_tier=RiskTier.CRITICAL,
        license_info=LicenseInfo(
            license_type=LicenseType.PROPRIETARY,
            allows_commercial=True,
            requires_attribution=False,
            allows_modification=False,
            allows_distribution=False,
        ),
        owner_team="AI Platform",
        owner_contact="ai-platform@company.com",
        escalation_path="ai-platform@company.com -> VP Engineering",
        deployment_region="us-east-1",
        registered_by="admin@company.com",
        description="Embedding model for RAG pipeline",
        metadata={"dimensions": 3072, "max_tokens": 8191},
    )

    # Register vector DB
    vectordb = bom.register_component(
        name="pinecone-prod",
        component_type=ComponentType.VECTOR_DATABASE,
        provider="Pinecone",
        version="2024.04",
        risk_tier=RiskTier.CRITICAL,
        license_info=LicenseInfo(
            license_type=LicenseType.PROPRIETARY,
            allows_commercial=True,
            requires_attribution=False,
            allows_modification=False,
            allows_distribution=False,
        ),
        owner_team="Data Platform",
        owner_contact="data-platform@company.com",
        escalation_path="data-platform@company.com -> CTO",
        deployment_region="us-east-1",
        registered_by="admin@company.com",
        description="Vector store for production RAG",
        metadata={"index_type": "serverless", "metric": "cosine"},
    )

    # Register MCP server
    mcp = bom.register_component(
        name="github-mcp-server",
        component_type=ComponentType.MCP_SERVER,
        provider="GitHub",
        version="1.2.0",
        risk_tier=RiskTier.HIGH,
        license_info=LicenseInfo(
            license_type=LicenseType.MIT,
            allows_commercial=True,
            requires_attribution=True,
            allows_modification=True,
            allows_distribution=True,
        ),
        owner_team="Developer Tools",
        owner_contact="devtools@company.com",
        escalation_path="devtools@company.com -> Engineering Manager",
        deployment_region="us-east-1",
        registered_by="admin@company.com",
        description="MCP server for GitHub integration",
    )

    # Add dependencies
    bom.add_dependency(vectordb.id, embeddings.id, "depends_on", True, "Vectors generated by embedding model")
    bom.add_dependency(gpt4.id, mcp.id, "calls", False, "LLM uses MCP tools")

    # Report a vulnerability
    bom.report_vulnerability(
        component_id=mcp.id,
        severity=VulnerabilitySeverity.MEDIUM,
        description="MCP server does not validate response schema strictly",
        remediation="Upgrade to version 1.3.0 which adds strict schema validation",
    )

    # Generate reports
    print("\n--- Risk Report ---")
    risk_report = bom.get_risk_report()
    print(f"Overall Risk Score: {risk_report['overall_risk_score']:.1f}")
    print(f"Critical Risk Components: {len(risk_report['risk_summary']['critical_risk'])}")
    print(f"Active Vulnerabilities: {len(risk_report['active_vulnerabilities'])}")
    print(f"Missing Exit Plans: {len(risk_report['missing_exit_plans'])}")

    print("\n--- License Compliance ---")
    compliance = bom.check_license_compliance("commercial")
    print(f"Compliant: {compliance['compliant_count']}/{compliance['total_components']}")
    for issue in compliance["issues"]:
        print(f"  ISSUE: {issue['component']} - {issue['issues']}")

    print("\n--- Dependency Graph ---")
    graph = bom.get_dependency_graph()
    print(f"Nodes: {len(graph['nodes'])}, Edges: {len(graph['edges'])}")

    print("\n--- Blast Radius (if Pinecone goes down) ---")
    affected = bom.get_blast_radius(vectordb.id)
    print(f"Affected components: {len(affected)}")

    print("\n--- CycloneDX Export (summary) ---")
    cdx = bom.export_cyclonedx()
    print(f"Components exported: {len(cdx['components'])}")
    print(f"Vulnerabilities: {len(cdx['vulnerabilities'])}")

    print("\n[Done]")


if __name__ == "__main__":
    demo()
