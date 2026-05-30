"""
AI Dependency Scanner
======================
Scans, monitors, and enforces policies on AI system dependencies including
models, MCP servers, open-source packages, and third-party services.
"""

import hashlib
import json
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class DependencyType(Enum):
    MODEL = "model"
    MCP_SERVER = "mcp_server"
    OPEN_SOURCE_PACKAGE = "open_source_package"
    DATASET = "dataset"
    API_SERVICE = "api_service"
    PLUGIN = "plugin"
    INFRASTRUCTURE = "infrastructure"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"  # Approved with conditions
    REVOKED = "revoked"


class ScanResult(Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    ERROR = "error"


class ThreatType(Enum):
    TYPOSQUATTING = "typosquatting"
    DEPENDENCY_CONFUSION = "dependency_confusion"
    MALICIOUS_UPDATE = "malicious_update"
    COMPROMISED_MAINTAINER = "compromised_maintainer"
    LICENSE_VIOLATION = "license_violation"
    KNOWN_VULNERABILITY = "known_vulnerability"
    BEHAVIOR_CHANGE = "behavior_change"
    DATA_EXFILTRATION = "data_exfiltration"
    PROMPT_INJECTION_VECTOR = "prompt_injection_vector"
    UNSIGNED_ARTIFACT = "unsigned_artifact"


class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Dependency:
    id: str
    name: str
    dep_type: DependencyType
    version: str
    provider: str
    license: str
    approval_status: ApprovalStatus
    registered_at: datetime
    last_scanned: Optional[datetime] = None
    artifact_hash: Optional[str] = None
    signature_verified: bool = False
    source_url: Optional[str] = None
    description: str = ""
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class ScanFinding:
    id: str
    dependency_id: str
    scan_time: datetime
    threat_type: ThreatType
    risk_level: RiskLevel
    title: str
    description: str
    remediation: str
    auto_fixable: bool = False
    false_positive: bool = False
    acknowledged: bool = False


@dataclass
class ApprovalRequest:
    id: str
    dependency_name: str
    dependency_type: DependencyType
    version: str
    provider: str
    requested_by: str
    requested_at: datetime
    justification: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    conditions: list[str] = field(default_factory=list)
    rejection_reason: Optional[str] = None


@dataclass
class MCPServerRiskProfile:
    server_name: str
    version: str
    capabilities: list[str]  # Tools it provides
    data_access: list[str]   # What data it can access
    network_access: list[str]  # What it connects to
    trust_level: RiskLevel
    sandboxed: bool
    response_validated: bool
    last_audit: Optional[datetime] = None
    known_issues: list[str] = field(default_factory=list)
    risk_score: float = 0.0


@dataclass
class AuditReport:
    id: str
    generated_at: datetime
    scan_period_start: datetime
    scan_period_end: datetime
    total_dependencies: int
    approved_count: int
    pending_count: int
    rejected_count: int
    findings_by_severity: dict[str, int]
    new_findings: list[ScanFinding]
    resolved_findings: list[str]
    overdue_reviews: list[str]
    recommendations: list[str]


# =============================================================================
# Known Vulnerability Database (simulated)
# =============================================================================

class VulnerabilityDatabase:
    """Simulated vulnerability database. In production, integrate with NVD, OSV, etc."""

    def __init__(self):
        self._vulns: dict[str, list[dict]] = {
            "langchain": [
                {"cve": "CVE-2023-XXXXX", "severity": "high",
                 "description": "Arbitrary code execution via prompt injection in agents",
                 "affected_versions": ["<0.0.267"], "fixed_in": "0.0.267"},
            ],
            "llama-index": [
                {"cve": "CVE-2024-XXXXX", "severity": "medium",
                 "description": "SSRF via document loader",
                 "affected_versions": ["<0.9.0"], "fixed_in": "0.9.0"},
            ],
        }

    def check(self, package_name: str, version: str) -> list[dict]:
        """Check if a package version has known vulnerabilities."""
        vulns = self._vulns.get(package_name.lower(), [])
        # Simplified version check
        return [v for v in vulns if self._is_affected(version, v.get("affected_versions", []))]

    def _is_affected(self, version: str, affected_patterns: list[str]) -> bool:
        """Simplified version matching."""
        for pattern in affected_patterns:
            if pattern.startswith("<"):
                target = pattern[1:]
                if version < target:
                    return True
        return False


# =============================================================================
# License Scanner
# =============================================================================

class LicenseScanner:
    """Scans and validates licenses for AI dependencies."""

    # Licenses that are problematic for commercial use
    RESTRICTED_LICENSES = {
        "GPL-3.0", "AGPL-3.0", "SSPL", "CC-BY-NC", "CC-BY-NC-SA",
        "EUPL", "OSL-3.0",
    }

    COPYLEFT_LICENSES = {
        "GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0",
        "MPL-2.0", "EPL-2.0",
    }

    AI_MODEL_LICENSES = {
        "OpenRAIL": {"commercial": True, "restrictions": ["No harmful use"]},
        "Llama-Community": {"commercial": True, "restrictions": ["700M MAU limit"]},
        "Gemma": {"commercial": True, "restrictions": ["Google terms apply"]},
        "CC-BY-4.0": {"commercial": True, "restrictions": ["Attribution required"]},
        "CC-BY-NC-4.0": {"commercial": False, "restrictions": ["Non-commercial only"]},
    }

    def scan_license(self, license_id: str, use_case: str = "commercial") -> dict:
        findings = []
        risk_level = RiskLevel.INFO

        if license_id in self.RESTRICTED_LICENSES:
            findings.append(f"License '{license_id}' is restricted for commercial use")
            risk_level = RiskLevel.HIGH

        if license_id in self.COPYLEFT_LICENSES:
            findings.append(f"License '{license_id}' has copyleft requirements")
            risk_level = max(risk_level, RiskLevel.MEDIUM, key=lambda x: list(RiskLevel).index(x))

        if license_id == "UNKNOWN":
            findings.append("License is unknown - manual review required")
            risk_level = RiskLevel.HIGH

        model_info = self.AI_MODEL_LICENSES.get(license_id)
        if model_info:
            if use_case == "commercial" and not model_info["commercial"]:
                findings.append(f"License does not permit commercial use")
                risk_level = RiskLevel.CRITICAL
            for restriction in model_info.get("restrictions", []):
                findings.append(f"Restriction: {restriction}")

        return {
            "license": license_id,
            "risk_level": risk_level.value,
            "findings": findings,
            "compliant": risk_level in (RiskLevel.INFO, RiskLevel.LOW),
        }


# =============================================================================
# Supply Chain Attack Detector
# =============================================================================

class SupplyChainAttackDetector:
    """Detects potential supply chain attacks on AI dependencies."""

    def __init__(self):
        self._known_packages: dict[str, dict] = {}  # name -> {publisher, first_seen, ...}
        self._behavior_baselines: dict[str, dict] = {}

    def register_known_package(self, name: str, publisher: str, first_seen: datetime) -> None:
        self._known_packages[name] = {
            "publisher": publisher,
            "first_seen": first_seen,
            "verified": True,
        }

    def check_typosquatting(self, package_name: str) -> Optional[ScanFinding]:
        """Check if a package name looks like a typosquat of a known package."""
        for known_name in self._known_packages:
            distance = self._levenshtein_distance(package_name.lower(), known_name.lower())
            if 0 < distance <= 2 and package_name != known_name:
                return ScanFinding(
                    id=f"FINDING-{uuid4().hex[:8]}",
                    dependency_id="",
                    scan_time=datetime.utcnow(),
                    threat_type=ThreatType.TYPOSQUATTING,
                    risk_level=RiskLevel.CRITICAL,
                    title=f"Possible typosquatting: '{package_name}' similar to '{known_name}'",
                    description=f"Package name '{package_name}' is suspiciously similar to "
                               f"known package '{known_name}' (edit distance: {distance})",
                    remediation=f"Verify you intended to use '{package_name}' and not '{known_name}'",
                )
        return None

    def check_dependency_confusion(self, package_name: str, registry: str) -> Optional[ScanFinding]:
        """Check for dependency confusion (internal name published externally)."""
        internal_prefixes = ["internal-", "company-", "private-", "@internal/"]
        for prefix in internal_prefixes:
            if package_name.startswith(prefix) and registry == "public":
                return ScanFinding(
                    id=f"FINDING-{uuid4().hex[:8]}",
                    dependency_id="",
                    scan_time=datetime.utcnow(),
                    threat_type=ThreatType.DEPENDENCY_CONFUSION,
                    risk_level=RiskLevel.CRITICAL,
                    title=f"Dependency confusion risk: '{package_name}' on public registry",
                    description=f"Package with internal-looking name found on public registry",
                    remediation="Verify package source. Use scoped registries for internal packages.",
                )
        return None

    def check_maintainer_change(self, package_name: str, current_publisher: str) -> Optional[ScanFinding]:
        """Detect if package publisher has changed (possible account compromise)."""
        known = self._known_packages.get(package_name)
        if known and known["publisher"] != current_publisher:
            return ScanFinding(
                id=f"FINDING-{uuid4().hex[:8]}",
                dependency_id="",
                scan_time=datetime.utcnow(),
                threat_type=ThreatType.COMPROMISED_MAINTAINER,
                risk_level=RiskLevel.HIGH,
                title=f"Publisher change detected for '{package_name}'",
                description=f"Publisher changed from '{known['publisher']}' to '{current_publisher}'",
                remediation="Verify the publisher change is legitimate before updating.",
            )
        return None

    def check_mcp_server_risk(self, profile: MCPServerRiskProfile) -> list[ScanFinding]:
        """Assess risk of an MCP server."""
        findings = []

        if not profile.sandboxed:
            findings.append(ScanFinding(
                id=f"FINDING-{uuid4().hex[:8]}",
                dependency_id="",
                scan_time=datetime.utcnow(),
                threat_type=ThreatType.DATA_EXFILTRATION,
                risk_level=RiskLevel.HIGH,
                title=f"MCP server '{profile.server_name}' is not sandboxed",
                description="MCP server runs without sandboxing, allowing unrestricted system access",
                remediation="Run MCP server in a sandboxed environment (container, VM, etc.)",
            ))

        if not profile.response_validated:
            findings.append(ScanFinding(
                id=f"FINDING-{uuid4().hex[:8]}",
                dependency_id="",
                scan_time=datetime.utcnow(),
                threat_type=ThreatType.PROMPT_INJECTION_VECTOR,
                risk_level=RiskLevel.HIGH,
                title=f"MCP server '{profile.server_name}' responses not validated",
                description="Responses from MCP server are not validated against schema, "
                           "allowing potential prompt injection via tool results",
                remediation="Implement strict schema validation on all MCP server responses",
            ))

        if profile.network_access and "internet" in profile.network_access:
            findings.append(ScanFinding(
                id=f"FINDING-{uuid4().hex[:8]}",
                dependency_id="",
                scan_time=datetime.utcnow(),
                threat_type=ThreatType.DATA_EXFILTRATION,
                risk_level=RiskLevel.MEDIUM,
                title=f"MCP server '{profile.server_name}' has internet access",
                description="MCP server can reach the internet, creating exfiltration risk",
                remediation="Restrict network access to only required endpoints",
            ))

        if not profile.last_audit or (datetime.utcnow() - profile.last_audit).days > 90:
            findings.append(ScanFinding(
                id=f"FINDING-{uuid4().hex[:8]}",
                dependency_id="",
                scan_time=datetime.utcnow(),
                threat_type=ThreatType.BEHAVIOR_CHANGE,
                risk_level=RiskLevel.MEDIUM,
                title=f"MCP server '{profile.server_name}' audit overdue",
                description="MCP server has not been audited in over 90 days",
                remediation="Schedule security audit of MCP server",
            ))

        return findings

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return SupplyChainAttackDetector._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]


# =============================================================================
# Dependency Registry
# =============================================================================

class DependencyRegistry:
    """Manages approved dependencies and enforces policies."""

    def __init__(self):
        self._dependencies: dict[str, Dependency] = {}
        self._approval_requests: list[ApprovalRequest] = []
        self._scan_findings: list[ScanFinding] = []
        self._vuln_db = VulnerabilityDatabase()
        self._license_scanner = LicenseScanner()
        self._attack_detector = SupplyChainAttackDetector()

    # -------------------------------------------------------------------------
    # Registration and Approval
    # -------------------------------------------------------------------------

    def request_approval(
        self,
        name: str,
        dep_type: DependencyType,
        version: str,
        provider: str,
        requested_by: str,
        justification: str,
    ) -> ApprovalRequest:
        """Submit a new dependency for approval."""
        request = ApprovalRequest(
            id=f"REQ-{uuid4().hex[:8]}",
            dependency_name=name,
            dependency_type=dep_type,
            version=version,
            provider=provider,
            requested_by=requested_by,
            requested_at=datetime.utcnow(),
            justification=justification,
        )
        self._approval_requests.append(request)
        logger.info(f"Approval requested for {name}@{version} by {requested_by}")
        return request

    def approve_dependency(
        self,
        request_id: str,
        reviewed_by: str,
        conditions: Optional[list[str]] = None,
    ) -> Dependency:
        """Approve a dependency request and register it."""
        request = next((r for r in self._approval_requests if r.id == request_id), None)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        request.status = ApprovalStatus.CONDITIONAL if conditions else ApprovalStatus.APPROVED
        request.reviewed_by = reviewed_by
        request.reviewed_at = datetime.utcnow()
        request.conditions = conditions or []

        dep = Dependency(
            id=f"DEP-{uuid4().hex[:8]}",
            name=request.dependency_name,
            dep_type=request.dependency_type,
            version=request.version,
            provider=request.provider,
            license="UNKNOWN",  # To be scanned
            approval_status=request.status,
            registered_at=datetime.utcnow(),
        )
        self._dependencies[dep.id] = dep
        return dep

    def reject_dependency(self, request_id: str, reviewed_by: str, reason: str) -> None:
        request = next((r for r in self._approval_requests if r.id == request_id), None)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        request.status = ApprovalStatus.REJECTED
        request.reviewed_by = reviewed_by
        request.reviewed_at = datetime.utcnow()
        request.rejection_reason = reason

    def is_approved(self, name: str, version: str) -> bool:
        """Check if a specific dependency version is approved."""
        return any(
            d.name == name and d.version == version
            and d.approval_status in (ApprovalStatus.APPROVED, ApprovalStatus.CONDITIONAL)
            for d in self._dependencies.values()
        )

    # -------------------------------------------------------------------------
    # Scanning
    # -------------------------------------------------------------------------

    def scan_all(self) -> list[ScanFinding]:
        """Run comprehensive scan on all registered dependencies."""
        all_findings = []

        for dep in self._dependencies.values():
            findings = self._scan_dependency(dep)
            all_findings.extend(findings)
            dep.last_scanned = datetime.utcnow()

        self._scan_findings.extend(all_findings)
        logger.info(f"Scan complete: {len(all_findings)} findings across {len(self._dependencies)} dependencies")
        return all_findings

    def _scan_dependency(self, dep: Dependency) -> list[ScanFinding]:
        findings = []

        # 1. Vulnerability check
        if dep.dep_type == DependencyType.OPEN_SOURCE_PACKAGE:
            vulns = self._vuln_db.check(dep.name, dep.version)
            for vuln in vulns:
                findings.append(ScanFinding(
                    id=f"FINDING-{uuid4().hex[:8]}",
                    dependency_id=dep.id,
                    scan_time=datetime.utcnow(),
                    threat_type=ThreatType.KNOWN_VULNERABILITY,
                    risk_level=RiskLevel.HIGH if vuln["severity"] == "high" else RiskLevel.MEDIUM,
                    title=f"Known vulnerability in {dep.name}@{dep.version}",
                    description=vuln["description"],
                    remediation=f"Upgrade to {vuln.get('fixed_in', 'latest')}",
                    auto_fixable=True,
                ))

        # 2. License check
        license_result = self._license_scanner.scan_license(dep.license)
        if license_result["risk_level"] in ("critical", "high"):
            for finding_desc in license_result["findings"]:
                findings.append(ScanFinding(
                    id=f"FINDING-{uuid4().hex[:8]}",
                    dependency_id=dep.id,
                    scan_time=datetime.utcnow(),
                    threat_type=ThreatType.LICENSE_VIOLATION,
                    risk_level=RiskLevel(license_result["risk_level"]),
                    title=f"License issue in {dep.name}",
                    description=finding_desc,
                    remediation="Review license compliance with legal team",
                ))

        # 3. Typosquatting check
        typo_finding = self._attack_detector.check_typosquatting(dep.name)
        if typo_finding:
            typo_finding.dependency_id = dep.id
            findings.append(typo_finding)

        # 4. Signature verification
        if not dep.signature_verified:
            findings.append(ScanFinding(
                id=f"FINDING-{uuid4().hex[:8]}",
                dependency_id=dep.id,
                scan_time=datetime.utcnow(),
                threat_type=ThreatType.UNSIGNED_ARTIFACT,
                risk_level=RiskLevel.MEDIUM,
                title=f"Unsigned artifact: {dep.name}@{dep.version}",
                description="Artifact signature has not been verified",
                remediation="Verify artifact signature against provider's public key",
            ))

        # 5. Freshness check
        age_days = (datetime.utcnow() - dep.registered_at).days
        if age_days > 365:
            findings.append(ScanFinding(
                id=f"FINDING-{uuid4().hex[:8]}",
                dependency_id=dep.id,
                scan_time=datetime.utcnow(),
                threat_type=ThreatType.BEHAVIOR_CHANGE,
                risk_level=RiskLevel.LOW,
                title=f"Stale dependency: {dep.name}@{dep.version}",
                description=f"Dependency has not been updated in {age_days} days",
                remediation="Review if newer versions are available and evaluate upgrade",
            ))

        return findings

    def scan_mcp_server(self, profile: MCPServerRiskProfile) -> list[ScanFinding]:
        """Dedicated MCP server risk assessment."""
        findings = self._attack_detector.check_mcp_server_risk(profile)
        self._scan_findings.extend(findings)
        return findings

    # -------------------------------------------------------------------------
    # Enforcement
    # -------------------------------------------------------------------------

    def enforce_registry(self, requested_deps: list[dict]) -> dict:
        """
        Check a list of dependencies against the approved registry.
        Returns violations for any unapproved dependencies.
        """
        violations = []
        approved = []

        for dep_info in requested_deps:
            name = dep_info.get("name")
            version = dep_info.get("version")
            if self.is_approved(name, version):
                approved.append(dep_info)
            else:
                violations.append({
                    "dependency": dep_info,
                    "reason": f"{name}@{version} is not in the approved registry",
                    "action": "Submit approval request before use",
                })

        return {
            "total_checked": len(requested_deps),
            "approved": len(approved),
            "violations": len(violations),
            "violation_details": violations,
            "enforcement_result": "PASS" if not violations else "FAIL",
        }

    # -------------------------------------------------------------------------
    # Freshness Monitoring
    # -------------------------------------------------------------------------

    def check_freshness(self) -> list[dict]:
        """Check all dependencies for staleness."""
        stale = []
        for dep in self._dependencies.values():
            age_days = (datetime.utcnow() - dep.registered_at).days
            scan_age = (datetime.utcnow() - dep.last_scanned).days if dep.last_scanned else None

            status = "fresh"
            if age_days > 365:
                status = "stale"
            elif age_days > 180:
                status = "aging"

            if status != "fresh" or (scan_age and scan_age > 30):
                stale.append({
                    "name": dep.name,
                    "version": dep.version,
                    "type": dep.dep_type.value,
                    "age_days": age_days,
                    "last_scanned_days_ago": scan_age,
                    "status": status,
                })

        return sorted(stale, key=lambda x: x["age_days"], reverse=True)

    # -------------------------------------------------------------------------
    # Audit Report
    # -------------------------------------------------------------------------

    def generate_audit_report(self, period_days: int = 30) -> AuditReport:
        """Generate periodic audit report."""
        period_start = datetime.utcnow() - timedelta(days=period_days)
        period_end = datetime.utcnow()

        deps = list(self._dependencies.values())
        new_findings = [
            f for f in self._scan_findings
            if f.scan_time >= period_start and not f.false_positive
        ]

        findings_by_severity = {}
        for f in new_findings:
            level = f.risk_level.value
            findings_by_severity[level] = findings_by_severity.get(level, 0) + 1

        overdue = []
        for dep in deps:
            if dep.last_scanned and (datetime.utcnow() - dep.last_scanned).days > 30:
                overdue.append(dep.name)
            elif not dep.last_scanned:
                overdue.append(dep.name)

        recommendations = []
        if findings_by_severity.get("critical", 0) > 0:
            recommendations.append("URGENT: Address all critical findings immediately")
        if len(overdue) > 0:
            recommendations.append(f"Schedule scans for {len(overdue)} overdue dependencies")
        pending_requests = [r for r in self._approval_requests if r.status == ApprovalStatus.PENDING]
        if pending_requests:
            recommendations.append(f"Review {len(pending_requests)} pending approval requests")

        return AuditReport(
            id=f"AUDIT-{uuid4().hex[:8]}",
            generated_at=datetime.utcnow(),
            scan_period_start=period_start,
            scan_period_end=period_end,
            total_dependencies=len(deps),
            approved_count=sum(1 for d in deps if d.approval_status == ApprovalStatus.APPROVED),
            pending_count=sum(1 for d in deps if d.approval_status == ApprovalStatus.PENDING),
            rejected_count=len([r for r in self._approval_requests if r.status == ApprovalStatus.REJECTED]),
            findings_by_severity=findings_by_severity,
            new_findings=new_findings,
            resolved_findings=[],
            overdue_reviews=overdue,
            recommendations=recommendations,
        )


# =============================================================================
# Demo
# =============================================================================

def demo():
    print("=" * 60)
    print("AI Dependency Scanner - Demo")
    print("=" * 60)

    registry = DependencyRegistry()

    # Register known packages for typosquatting detection
    registry._attack_detector.register_known_package("langchain", "LangChain Inc", datetime(2022, 10, 1))
    registry._attack_detector.register_known_package("llama-index", "LlamaIndex", datetime(2022, 11, 1))
    registry._attack_detector.register_known_package("openai", "OpenAI", datetime(2020, 6, 1))

    # Submit approval requests
    print("\n--- Approval Workflow ---")
    req1 = registry.request_approval(
        name="langchain",
        dep_type=DependencyType.OPEN_SOURCE_PACKAGE,
        version="0.1.0",
        provider="LangChain Inc",
        requested_by="dev@company.com",
        justification="Needed for RAG pipeline orchestration",
    )
    print(f"Request submitted: {req1.id}")

    req2 = registry.request_approval(
        name="langchaln",  # Typosquat!
        dep_type=DependencyType.OPEN_SOURCE_PACKAGE,
        version="0.1.0",
        provider="Unknown",
        requested_by="dev@company.com",
        justification="Testing",
    )

    # Approve first, reject second
    dep1 = registry.approve_dependency(req1.id, "security@company.com", ["Pin to exact version"])
    dep1.license = "MIT"
    print(f"Approved: {dep1.name}@{dep1.version}")

    registry.reject_dependency(req2.id, "security@company.com", "Suspected typosquat of 'langchain'")
    print(f"Rejected: {req2.dependency_name} (typosquat)")

    # Add more dependencies for scanning
    dep_openai = registry.approve_dependency(
        registry.request_approval("openai", DependencyType.OPEN_SOURCE_PACKAGE, "1.12.0", "OpenAI",
                                  "dev@company.com", "OpenAI SDK").id,
        "security@company.com"
    )
    dep_openai.license = "Apache-2.0"
    dep_openai.signature_verified = True

    # Run scan
    print("\n--- Running Scan ---")
    findings = registry.scan_all()
    print(f"Total findings: {len(findings)}")
    for f in findings:
        print(f"  [{f.risk_level.value.upper()}] {f.title}")
        print(f"    Remediation: {f.remediation}")

    # MCP Server assessment
    print("\n--- MCP Server Risk Assessment ---")
    mcp_findings = registry.scan_mcp_server(MCPServerRiskProfile(
        server_name="code-executor-mcp",
        version="2.0.0",
        capabilities=["execute_code", "read_file", "write_file"],
        data_access=["filesystem", "environment_variables"],
        network_access=["internet"],
        trust_level=RiskLevel.HIGH,
        sandboxed=False,
        response_validated=False,
        last_audit=datetime.utcnow() - timedelta(days=120),
    ))
    print(f"MCP findings: {len(mcp_findings)}")
    for f in mcp_findings:
        print(f"  [{f.risk_level.value.upper()}] {f.title}")

    # Registry enforcement
    print("\n--- Registry Enforcement ---")
    enforcement = registry.enforce_registry([
        {"name": "langchain", "version": "0.1.0"},
        {"name": "openai", "version": "1.12.0"},
        {"name": "unknown-package", "version": "0.0.1"},
    ])
    print(f"Result: {enforcement['enforcement_result']}")
    print(f"Approved: {enforcement['approved']}, Violations: {enforcement['violations']}")
    for v in enforcement["violation_details"]:
        print(f"  VIOLATION: {v['reason']}")

    # Audit report
    print("\n--- Audit Report ---")
    report = registry.generate_audit_report()
    print(f"Total dependencies: {report.total_dependencies}")
    print(f"Findings by severity: {report.findings_by_severity}")
    print(f"Overdue reviews: {report.overdue_reviews}")
    for rec in report.recommendations:
        print(f"  -> {rec}")

    print("\n[Done]")


if __name__ == "__main__":
    demo()
