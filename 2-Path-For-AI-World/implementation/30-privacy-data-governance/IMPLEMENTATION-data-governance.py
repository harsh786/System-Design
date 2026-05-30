"""
Data Governance for AI Systems
================================
Data catalog, quality rules, contracts, access policies, retention,
lineage, freshness monitoring, ownership, and governance reporting.
"""

import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

# =============================================================================
# DATA CATALOG
# =============================================================================

class DataDomain(Enum):
    CUSTOMER = "customer"
    CONVERSATION = "conversation"
    MODEL = "model"
    ANALYTICS = "analytics"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"


class DataFormat(Enum):
    STRUCTURED = "structured"      # SQL tables, JSON with schema
    SEMI_STRUCTURED = "semi"       # Logs, variable JSON
    UNSTRUCTURED = "unstructured"  # Documents, images
    VECTOR = "vector"              # Embeddings
    TIME_SERIES = "time_series"    # Metrics, events


@dataclass
class DataAsset:
    """A registered data asset in the catalog."""
    asset_id: str
    name: str
    description: str
    domain: DataDomain
    format: DataFormat
    owner: str                                # Team or individual
    steward: str                              # Data steward responsible
    location: str                             # System/database/table
    schema: Optional[dict] = None             # Schema definition
    sensitivity: str = "internal"             # public/internal/confidential/restricted
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    retention_days: Optional[int] = None
    freshness_sla_hours: Optional[int] = None
    quality_rules: list[str] = field(default_factory=list)  # rule IDs
    upstream_assets: list[str] = field(default_factory=list)
    downstream_assets: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DataCatalog:
    """Central registry of all data assets."""

    def __init__(self):
        self._assets: dict[str, DataAsset] = {}
        self._search_index: dict[str, list[str]] = {}  # tag -> asset_ids

    def register_asset(self, asset: DataAsset) -> str:
        """Register a new data asset."""
        self._assets[asset.asset_id] = asset
        for tag in asset.tags:
            if tag not in self._search_index:
                self._search_index[tag] = []
            self._search_index[tag].append(asset.asset_id)
        return asset.asset_id

    def get_asset(self, asset_id: str) -> Optional[DataAsset]:
        return self._assets.get(asset_id)

    def search(
        self,
        domain: Optional[DataDomain] = None,
        owner: Optional[str] = None,
        sensitivity: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[DataAsset]:
        """Search catalog with filters."""
        results = list(self._assets.values())
        if domain:
            results = [a for a in results if a.domain == domain]
        if owner:
            results = [a for a in results if a.owner == owner]
        if sensitivity:
            results = [a for a in results if a.sensitivity == sensitivity]
        if tags:
            results = [a for a in results if any(t in a.tags for t in tags)]
        return results

    def get_lineage(self, asset_id: str, direction: str = "both") -> dict:
        """Get data lineage for an asset."""
        asset = self._assets.get(asset_id)
        if not asset:
            return {}

        result = {"asset_id": asset_id, "name": asset.name}
        if direction in ("upstream", "both"):
            result["upstream"] = self._trace_lineage(asset_id, "upstream")
        if direction in ("downstream", "both"):
            result["downstream"] = self._trace_lineage(asset_id, "downstream")
        return result

    def _trace_lineage(self, asset_id: str, direction: str, visited: Optional[set] = None) -> list:
        if visited is None:
            visited = set()
        if asset_id in visited:
            return []
        visited.add(asset_id)

        asset = self._assets.get(asset_id)
        if not asset:
            return []

        links = asset.upstream_assets if direction == "upstream" else asset.downstream_assets
        lineage = []
        for linked_id in links:
            linked = self._assets.get(linked_id)
            if linked:
                lineage.append({
                    "asset_id": linked_id,
                    "name": linked.name,
                    "children": self._trace_lineage(linked_id, direction, visited),
                })
        return lineage

    def get_impact_analysis(self, asset_id: str) -> dict:
        """What downstream assets are affected if this asset changes/breaks?"""
        downstream = self._trace_lineage(asset_id, "downstream")
        all_affected = self._flatten_lineage(downstream)
        return {
            "source_asset": asset_id,
            "affected_assets": all_affected,
            "affected_count": len(all_affected),
        }

    def _flatten_lineage(self, lineage: list) -> list[str]:
        result = []
        for item in lineage:
            result.append(item["asset_id"])
            result.extend(self._flatten_lineage(item.get("children", [])))
        return result


# =============================================================================
# DATA QUALITY
# =============================================================================

class QualityDimension(Enum):
    COMPLETENESS = "completeness"    # No missing values
    ACCURACY = "accuracy"            # Values are correct
    CONSISTENCY = "consistency"      # Values match across systems
    TIMELINESS = "timeliness"        # Data is up to date
    UNIQUENESS = "uniqueness"        # No duplicates
    VALIDITY = "validity"            # Values conform to rules


@dataclass
class QualityRule:
    rule_id: str
    name: str
    description: str
    dimension: QualityDimension
    asset_id: str
    check_fn: Optional[Callable] = None  # Function that returns (pass: bool, details: str)
    threshold: float = 1.0               # Minimum pass rate (0-1)
    severity: str = "warning"            # "info", "warning", "critical"
    enabled: bool = True


@dataclass
class QualityCheckResult:
    rule_id: str
    asset_id: str
    passed: bool
    score: float          # 0-1
    details: str
    checked_at: datetime
    records_checked: int = 0
    records_failed: int = 0


class DataQualityEngine:
    """Monitors and enforces data quality rules."""

    def __init__(self):
        self._rules: dict[str, QualityRule] = {}
        self._history: list[QualityCheckResult] = []

    def add_rule(self, rule: QualityRule):
        self._rules[rule.rule_id] = rule

    def check_asset(self, asset_id: str, data: list[dict]) -> list[QualityCheckResult]:
        """Run all quality rules for an asset against provided data."""
        results = []
        rules = [r for r in self._rules.values() if r.asset_id == asset_id and r.enabled]

        for rule in rules:
            result = self._execute_rule(rule, data)
            results.append(result)
            self._history.append(result)

        return results

    def _execute_rule(self, rule: QualityRule, data: list[dict]) -> QualityCheckResult:
        """Execute a single quality rule."""
        if rule.check_fn:
            try:
                passed, details = rule.check_fn(data)
                score = 1.0 if passed else 0.0
            except Exception as e:
                passed, details, score = False, f"Rule execution error: {e}", 0.0
        else:
            # Built-in checks based on dimension
            passed, score, details = self._builtin_check(rule, data)

        return QualityCheckResult(
            rule_id=rule.rule_id,
            asset_id=rule.asset_id,
            passed=passed and score >= rule.threshold,
            score=score,
            details=details,
            checked_at=datetime.utcnow(),
            records_checked=len(data),
            records_failed=int(len(data) * (1 - score)),
        )

    def _builtin_check(self, rule: QualityRule, data: list[dict]) -> tuple[bool, float, str]:
        """Built-in quality checks."""
        if not data:
            return True, 1.0, "No data to check"

        match rule.dimension:
            case QualityDimension.COMPLETENESS:
                # Check for None/empty values across all fields
                total_fields = len(data) * len(data[0]) if data else 0
                null_fields = sum(
                    1 for row in data for v in row.values()
                    if v is None or v == ""
                )
                score = 1 - (null_fields / max(total_fields, 1))
                return score >= rule.threshold, score, f"{null_fields}/{total_fields} null fields"

            case QualityDimension.UNIQUENESS:
                # Check for duplicate records
                unique = len({json.dumps(row, sort_keys=True, default=str) for row in data})
                score = unique / max(len(data), 1)
                dupes = len(data) - unique
                return score >= rule.threshold, score, f"{dupes} duplicate records"

            case _:
                return True, 1.0, "No built-in check for this dimension"

    def get_quality_report(self, asset_id: Optional[str] = None) -> dict:
        """Generate quality report."""
        relevant = self._history
        if asset_id:
            relevant = [r for r in relevant if r.asset_id == asset_id]

        if not relevant:
            return {"status": "no_data", "checks_run": 0}

        latest_by_rule = {}
        for result in relevant:
            latest_by_rule[result.rule_id] = result

        passed = sum(1 for r in latest_by_rule.values() if r.passed)
        total = len(latest_by_rule)

        return {
            "asset_id": asset_id,
            "total_rules": total,
            "rules_passing": passed,
            "rules_failing": total - passed,
            "overall_score": passed / max(total, 1),
            "details": [
                {
                    "rule_id": r.rule_id,
                    "passed": r.passed,
                    "score": r.score,
                    "details": r.details,
                    "checked_at": r.checked_at.isoformat(),
                }
                for r in latest_by_rule.values()
            ],
        }


# =============================================================================
# DATA CONTRACTS
# =============================================================================

@dataclass
class DataContract:
    """Agreement between data producer and consumer."""
    contract_id: str
    name: str
    producer: str               # Team/service producing data
    consumer: str               # Team/service consuming data
    asset_id: str               # Data asset covered
    schema: dict                # Expected schema
    quality_slas: dict          # Quality guarantees
    freshness_sla_hours: int    # Max age of data
    retention_days: int         # How long data is available
    purpose: str                # Why consumer needs this data
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    status: str = "active"      # active, expired, violated


class DataContractRegistry:
    """Manages data contracts between teams."""

    def __init__(self):
        self._contracts: dict[str, DataContract] = {}
        self._violations: list[dict] = []

    def create_contract(self, contract: DataContract) -> str:
        self._contracts[contract.contract_id] = contract
        return contract.contract_id

    def validate_against_contract(
        self, contract_id: str, data: list[dict], metadata: dict
    ) -> dict:
        """Validate data against its contract."""
        contract = self._contracts.get(contract_id)
        if not contract:
            return {"valid": False, "error": "Contract not found"}

        violations = []

        # Schema validation
        if contract.schema:
            required_fields = contract.schema.get("required", [])
            for row in data[:100]:  # Sample check
                for field_name in required_fields:
                    if field_name not in row:
                        violations.append(f"Missing required field: {field_name}")
                        break

        # Freshness check
        data_age_hours = metadata.get("data_age_hours", 0)
        if data_age_hours > contract.freshness_sla_hours:
            violations.append(
                f"Data too stale: {data_age_hours}h > {contract.freshness_sla_hours}h SLA"
            )

        # Quality SLA check
        for dimension, threshold in contract.quality_slas.items():
            actual = metadata.get(f"quality_{dimension}", 1.0)
            if actual < threshold:
                violations.append(
                    f"Quality SLA violated: {dimension} = {actual:.2f} < {threshold}"
                )

        if violations:
            self._violations.append({
                "contract_id": contract_id,
                "timestamp": datetime.utcnow().isoformat(),
                "violations": violations,
            })

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "contract": contract.name,
        }

    def get_contracts_for_asset(self, asset_id: str) -> list[DataContract]:
        return [c for c in self._contracts.values() if c.asset_id == asset_id]


# =============================================================================
# DATA ACCESS POLICIES
# =============================================================================

class AccessLevel(Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass
class AccessPolicy:
    policy_id: str
    asset_id: str
    principal: str          # user, role, or service
    principal_type: str     # "user", "role", "service"
    access_level: AccessLevel
    purpose: str            # Why access is needed
    conditions: dict = field(default_factory=dict)  # Time-based, IP-based, etc.
    expires_at: Optional[datetime] = None
    granted_by: str = ""
    granted_at: datetime = field(default_factory=datetime.utcnow)


class DataAccessManager:
    """Manages and enforces data access policies."""

    def __init__(self):
        self._policies: list[AccessPolicy] = []
        self._access_log: list[dict] = []

    def grant_access(self, policy: AccessPolicy):
        self._policies.append(policy)

    def check_access(
        self,
        asset_id: str,
        principal: str,
        requested_level: AccessLevel,
        purpose: str,
        context: Optional[dict] = None,
    ) -> bool:
        """Check if access is allowed."""
        now = datetime.utcnow()
        allowed = False

        for policy in self._policies:
            if policy.asset_id != asset_id:
                continue
            if policy.principal != principal:
                continue
            if policy.expires_at and now > policy.expires_at:
                continue
            if policy.access_level.value >= requested_level.value or policy.access_level == AccessLevel.ADMIN:
                # Check conditions
                if self._check_conditions(policy.conditions, context):
                    allowed = True
                    break

        # Log access attempt
        self._access_log.append({
            "timestamp": now.isoformat(),
            "asset_id": asset_id,
            "principal": principal,
            "requested_level": requested_level.value,
            "purpose": purpose,
            "allowed": allowed,
        })

        return allowed

    def _check_conditions(self, conditions: dict, context: Optional[dict]) -> bool:
        """Evaluate access conditions."""
        if not conditions:
            return True
        if not context:
            return False

        # Time-based condition
        if "allowed_hours" in conditions:
            current_hour = datetime.utcnow().hour
            start, end = conditions["allowed_hours"]
            if not (start <= current_hour <= end):
                return False

        # Environment condition
        if "allowed_environments" in conditions:
            env = context.get("environment", "")
            if env not in conditions["allowed_environments"]:
                return False

        return True

    def revoke_access(self, principal: str, asset_id: str):
        """Revoke all access for a principal to an asset."""
        self._policies = [
            p for p in self._policies
            if not (p.principal == principal and p.asset_id == asset_id)
        ]

    def get_access_report(self, asset_id: str) -> dict:
        """Who has access to this asset?"""
        policies = [p for p in self._policies if p.asset_id == asset_id]
        return {
            "asset_id": asset_id,
            "total_grants": len(policies),
            "by_level": {
                level.value: [p.principal for p in policies if p.access_level == level]
                for level in AccessLevel
            },
            "expired": [
                p.principal for p in policies
                if p.expires_at and datetime.utcnow() > p.expires_at
            ],
        }


# =============================================================================
# DATA RETENTION ENFORCEMENT
# =============================================================================

@dataclass
class RetentionPolicy:
    policy_id: str
    asset_id: str
    retention_days: int
    action: str = "delete"  # "delete", "archive", "anonymize"
    exceptions: list[str] = field(default_factory=list)  # legal holds, etc.


class RetentionManager:
    """Enforces data retention policies."""

    def __init__(self):
        self._policies: dict[str, RetentionPolicy] = {}
        self._enforcement_log: list[dict] = []

    def set_policy(self, policy: RetentionPolicy):
        self._policies[policy.policy_id] = policy

    def check_compliance(self, asset_id: str, oldest_record_date: datetime) -> dict:
        """Check if an asset is compliant with its retention policy."""
        policies = [p for p in self._policies.values() if p.asset_id == asset_id]
        if not policies:
            return {"compliant": True, "note": "No retention policy defined"}

        policy = policies[0]
        max_age = timedelta(days=policy.retention_days)
        actual_age = datetime.utcnow() - oldest_record_date
        compliant = actual_age <= max_age

        return {
            "compliant": compliant,
            "policy_days": policy.retention_days,
            "actual_age_days": actual_age.days,
            "action_needed": policy.action if not compliant else None,
            "overdue_by_days": max(0, actual_age.days - policy.retention_days),
        }

    def get_enforcement_actions(self) -> list[dict]:
        """Get all pending enforcement actions."""
        # In real implementation: query each asset for records past retention
        return self._enforcement_log


# =============================================================================
# DATA FRESHNESS MONITORING
# =============================================================================

@dataclass
class FreshnessCheck:
    asset_id: str
    last_updated: datetime
    sla_hours: int
    is_fresh: bool
    staleness_hours: float


class FreshnessMonitor:
    """Monitors data freshness against SLAs."""

    def __init__(self):
        self._slas: dict[str, int] = {}  # asset_id -> max_hours
        self._last_update: dict[str, datetime] = {}

    def set_sla(self, asset_id: str, max_hours: int):
        self._slas[asset_id] = max_hours

    def record_update(self, asset_id: str):
        self._last_update[asset_id] = datetime.utcnow()

    def check_freshness(self, asset_id: str) -> Optional[FreshnessCheck]:
        if asset_id not in self._slas:
            return None

        last_update = self._last_update.get(asset_id)
        if not last_update:
            return FreshnessCheck(
                asset_id=asset_id,
                last_updated=datetime.min,
                sla_hours=self._slas[asset_id],
                is_fresh=False,
                staleness_hours=float("inf"),
            )

        age = datetime.utcnow() - last_update
        staleness_hours = age.total_seconds() / 3600

        return FreshnessCheck(
            asset_id=asset_id,
            last_updated=last_update,
            sla_hours=self._slas[asset_id],
            is_fresh=staleness_hours <= self._slas[asset_id],
            staleness_hours=round(staleness_hours, 2),
        )

    def get_stale_assets(self) -> list[FreshnessCheck]:
        """Get all assets that are stale."""
        stale = []
        for asset_id in self._slas:
            check = self.check_freshness(asset_id)
            if check and not check.is_fresh:
                stale.append(check)
        return stale


# =============================================================================
# GOVERNANCE REPORTING
# =============================================================================

class GovernanceReporter:
    """Generates governance reports and dashboards."""

    def __init__(
        self,
        catalog: DataCatalog,
        quality_engine: DataQualityEngine,
        access_manager: DataAccessManager,
        freshness_monitor: FreshnessMonitor,
        retention_manager: RetentionManager,
    ):
        self._catalog = catalog
        self._quality = quality_engine
        self._access = access_manager
        self._freshness = freshness_monitor
        self._retention = retention_manager

    def generate_executive_report(self) -> dict:
        """High-level governance health report."""
        all_assets = self._catalog.search()

        # Ownership coverage
        owned = [a for a in all_assets if a.owner]
        unowned = [a for a in all_assets if not a.owner]

        # Quality summary
        quality_reports = [self._quality.get_quality_report(a.asset_id) for a in all_assets]
        quality_passing = [r for r in quality_reports if r.get("overall_score", 0) >= 0.9]

        # Freshness
        stale = self._freshness.get_stale_assets()

        return {
            "report_date": datetime.utcnow().isoformat(),
            "total_assets": len(all_assets),
            "ownership": {
                "owned": len(owned),
                "unowned": len(unowned),
                "coverage_pct": len(owned) / max(len(all_assets), 1) * 100,
            },
            "quality": {
                "assets_checked": len(quality_reports),
                "assets_healthy": len(quality_passing),
                "health_pct": len(quality_passing) / max(len(quality_reports), 1) * 100,
            },
            "freshness": {
                "stale_assets": len(stale),
                "stale_asset_ids": [s.asset_id for s in stale],
            },
            "sensitivity_distribution": {
                level: len([a for a in all_assets if a.sensitivity == level])
                for level in ["public", "internal", "confidential", "restricted"]
            },
            "domain_distribution": {
                domain.value: len([a for a in all_assets if a.domain == domain])
                for domain in DataDomain
            },
        }

    def generate_compliance_report(self) -> dict:
        """Compliance-focused report."""
        all_assets = self._catalog.search()

        # Retention compliance
        no_retention = [a for a in all_assets if not a.retention_days]

        # Sensitivity without proper controls
        high_sensitivity = [
            a for a in all_assets
            if a.sensitivity in ("confidential", "restricted")
        ]

        return {
            "report_date": datetime.utcnow().isoformat(),
            "retention": {
                "assets_without_policy": len(no_retention),
                "asset_ids": [a.asset_id for a in no_retention[:10]],
            },
            "high_sensitivity_assets": {
                "count": len(high_sensitivity),
                "assets": [
                    {"id": a.asset_id, "name": a.name, "sensitivity": a.sensitivity}
                    for a in high_sensitivity
                ],
            },
        }


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def main():
    """Demonstrate data governance capabilities."""
    print("=" * 70)
    print("DATA GOVERNANCE DEMONSTRATION")
    print("=" * 70)

    # 1. Data Catalog
    print("\n--- DATA CATALOG ---")
    catalog = DataCatalog()

    conversations_asset = DataAsset(
        asset_id="asset-conversations",
        name="User Conversations",
        description="All user chat conversations with AI assistant",
        domain=DataDomain.CONVERSATION,
        format=DataFormat.SEMI_STRUCTURED,
        owner="ai-platform-team",
        steward="jane.smith",
        location="postgres://prod/conversations",
        sensitivity="confidential",
        tags=["pii", "user-generated", "chat"],
        retention_days=365,
        freshness_sla_hours=1,
        downstream_assets=["asset-embeddings", "asset-analytics"],
    )
    catalog.register_asset(conversations_asset)

    embeddings_asset = DataAsset(
        asset_id="asset-embeddings",
        name="Conversation Embeddings",
        description="Vector embeddings of conversation content",
        domain=DataDomain.CONVERSATION,
        format=DataFormat.VECTOR,
        owner="ai-platform-team",
        steward="jane.smith",
        location="pinecone://prod/conv-index",
        sensitivity="confidential",
        tags=["derived", "vector", "pii-derived"],
        retention_days=365,
        upstream_assets=["asset-conversations"],
    )
    catalog.register_asset(embeddings_asset)

    print(f"Registered {len(catalog.search())} assets")
    lineage = catalog.get_lineage("asset-conversations")
    print(f"Lineage for conversations: {json.dumps(lineage, indent=2, default=str)}")

    # 2. Data Quality
    print("\n--- DATA QUALITY ---")
    quality = DataQualityEngine()

    quality.add_rule(QualityRule(
        rule_id="conv-completeness",
        name="Conversation Completeness",
        description="All conversations must have user_id and content",
        dimension=QualityDimension.COMPLETENESS,
        asset_id="asset-conversations",
        threshold=0.99,
        severity="critical",
    ))

    sample_data = [
        {"user_id": "u1", "content": "hello", "timestamp": "2024-01-01"},
        {"user_id": "u2", "content": "", "timestamp": "2024-01-02"},
        {"user_id": None, "content": "test", "timestamp": "2024-01-03"},
    ]
    results = quality.check_asset("asset-conversations", sample_data)
    for r in results:
        print(f"  Rule '{r.rule_id}': {'PASS' if r.passed else 'FAIL'} (score: {r.score:.2f})")

    # 3. Data Contracts
    print("\n--- DATA CONTRACTS ---")
    contracts = DataContractRegistry()

    contract = DataContract(
        contract_id="contract-conv-analytics",
        name="Conversations → Analytics Pipeline",
        producer="ai-platform-team",
        consumer="analytics-team",
        asset_id="asset-conversations",
        schema={"required": ["user_id", "content", "timestamp"]},
        quality_slas={"completeness": 0.99},
        freshness_sla_hours=2,
        retention_days=90,
        purpose="Aggregate usage analytics (anonymized)",
    )
    contracts.create_contract(contract)

    validation = contracts.validate_against_contract(
        "contract-conv-analytics",
        sample_data,
        {"data_age_hours": 1, "quality_completeness": 0.85},
    )
    print(f"  Contract valid: {validation['valid']}")
    for v in validation.get("violations", []):
        print(f"    Violation: {v}")

    # 4. Access Policies
    print("\n--- ACCESS POLICIES ---")
    access = DataAccessManager()

    access.grant_access(AccessPolicy(
        policy_id="pol-1",
        asset_id="asset-conversations",
        principal="ai-platform-team",
        principal_type="role",
        access_level=AccessLevel.ADMIN,
        purpose="System operation",
    ))
    access.grant_access(AccessPolicy(
        policy_id="pol-2",
        asset_id="asset-conversations",
        principal="analytics-team",
        principal_type="role",
        access_level=AccessLevel.READ,
        purpose="Analytics processing",
        conditions={"allowed_environments": ["production"]},
    ))

    can_read = access.check_access(
        "asset-conversations", "analytics-team", AccessLevel.READ,
        "analytics", {"environment": "production"},
    )
    can_write = access.check_access(
        "asset-conversations", "analytics-team", AccessLevel.WRITE,
        "analytics", {"environment": "production"},
    )
    print(f"  Analytics read access: {can_read}")
    print(f"  Analytics write access: {can_write}")

    # 5. Freshness Monitoring
    print("\n--- FRESHNESS MONITORING ---")
    freshness = FreshnessMonitor()
    freshness.set_sla("asset-conversations", max_hours=1)
    freshness.record_update("asset-conversations")

    check = freshness.check_freshness("asset-conversations")
    print(f"  Asset fresh: {check.is_fresh} (staleness: {check.staleness_hours}h)")

    # 6. Governance Report
    print("\n--- GOVERNANCE REPORT ---")
    retention = RetentionManager()
    reporter = GovernanceReporter(catalog, quality, access, freshness, retention)
    report = reporter.generate_executive_report()
    print(f"  Total assets: {report['total_assets']}")
    print(f"  Ownership coverage: {report['ownership']['coverage_pct']}%")
    print(f"  Quality health: {report['quality']['health_pct']}%")
    print(f"  Stale assets: {report['freshness']['stale_assets']}")


if __name__ == "__main__":
    main()
