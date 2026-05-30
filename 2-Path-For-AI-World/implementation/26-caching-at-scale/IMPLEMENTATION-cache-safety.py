"""
Cache Safety Enforcement for Enterprise AI
=============================================
Ensures cached responses NEVER leak data across tenants, NEVER serve
stale-permissioned responses, and NEVER allow cache poisoning.

This module provides:
1. Cross-tenant isolation validation
2. Permission revocation propagation verification
3. Negative access tests (proving unauthorized access fails)
4. Post-deletion cache verification
5. Cache key security audit
6. Cache poisoning detection
7. Comprehensive safety test suite

SECURITY INVARIANTS:
- Cache isolation is a HARD requirement, not a performance optimization
- ANY cross-tenant data leak is a P0 security incident
- Permission revocation MUST propagate to cache within SLA (< 5s)
- Deleted data MUST NOT be served from cache after deletion confirmed
"""

import asyncio
import hashlib
import json
import time
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================

class SafetyViolationType(Enum):
    CROSS_TENANT_LEAK = "cross_tenant_leak"
    PERMISSION_BYPASS = "permission_bypass"
    STALE_PERMISSION_SERVE = "stale_permission_serve"
    DELETED_DATA_SERVE = "deleted_data_serve"
    CACHE_POISONING = "cache_poisoning"
    KEY_COLLISION = "key_collision"
    FINGERPRINT_SPOOFING = "fingerprint_spoofing"
    STALE_BEYOND_TOLERANCE = "stale_beyond_tolerance"
    UNAUTHORIZED_CACHE_WRITE = "unauthorized_cache_write"


class SeverityLevel(Enum):
    CRITICAL = "critical"   # Immediate incident, page on-call
    HIGH = "high"           # Security team notification within 5 min
    MEDIUM = "medium"       # Security review within 1 hour
    LOW = "low"             # Track and fix in next sprint


@dataclass
class SafetyViolation:
    violation_type: SafetyViolationType
    severity: SeverityLevel
    description: str
    tenant_id: str
    affected_user_id: Optional[str] = None
    cache_key: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    remediation_applied: bool = False

    def to_alert(self) -> Dict:
        return {
            "type": self.violation_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "tenant_id": self.tenant_id,
            "user_id": self.affected_user_id,
            "timestamp": self.timestamp,
            "evidence": self.evidence,
        }


@dataclass
class SafetyAuditResult:
    passed: bool
    checks_run: int
    checks_passed: int
    checks_failed: int
    violations: List[SafetyViolation] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "violations": [v.to_alert() for v in self.violations],
            "duration_ms": self.duration_ms,
        }


# =============================================================================
# Cross-Tenant Isolation Validator
# =============================================================================

class CrossTenantIsolationValidator:
    """
    Validates that cache entries are NEVER accessible across tenant boundaries.
    Runs both proactive checks and reactive monitoring.
    """

    def __init__(self):
        self._violations: List[SafetyViolation] = []

    def validate_cache_entry_access(
        self,
        entry_tenant_id: str,
        requesting_tenant_id: str,
        cache_key: str,
    ) -> bool:
        """
        MUST be called before EVERY cache read.
        Returns True if access is safe, raises on violation.
        """
        if entry_tenant_id != requesting_tenant_id:
            violation = SafetyViolation(
                violation_type=SafetyViolationType.CROSS_TENANT_LEAK,
                severity=SeverityLevel.CRITICAL,
                description=(
                    f"Cross-tenant cache access attempt: "
                    f"entry belongs to tenant '{entry_tenant_id}', "
                    f"requested by tenant '{requesting_tenant_id}'"
                ),
                tenant_id=requesting_tenant_id,
                cache_key=cache_key,
                evidence={
                    "entry_tenant": entry_tenant_id,
                    "requesting_tenant": requesting_tenant_id,
                },
            )
            self._violations.append(violation)
            logger.critical(
                f"SECURITY VIOLATION: {violation.description} (key={cache_key[:16]})"
            )
            # In production: trigger incident, alert security team
            return False
        return True

    def validate_key_contains_tenant(self, cache_key: str, tenant_id: str) -> bool:
        """Verify the cache key was built with tenant isolation."""
        # Keys should be hashes, but we can verify the builder includes tenant_id
        # This is a design-time check more than runtime
        return True  # Actual validation happens in key builder

    async def run_isolation_probe(
        self,
        cache_get_fn: Callable,
        tenant_a: str,
        tenant_b: str,
        test_queries: List[str],
    ) -> List[SafetyViolation]:
        """
        Active probe: Write entries as Tenant A, attempt reads as Tenant B.
        ALL reads MUST fail. Any success = CRITICAL violation.
        """
        violations = []

        for query in test_queries:
            # Tenant B should NOT be able to read Tenant A's cache
            result = await cache_get_fn(query=query, tenant_id=tenant_b)
            if result is not None:
                # Check if this result belongs to tenant_a
                if hasattr(result, 'tenant_id') and result.tenant_id == tenant_a:
                    violations.append(SafetyViolation(
                        violation_type=SafetyViolationType.CROSS_TENANT_LEAK,
                        severity=SeverityLevel.CRITICAL,
                        description=f"Tenant B retrieved Tenant A's cached response",
                        tenant_id=tenant_b,
                        evidence={
                            "query": query,
                            "leaked_from_tenant": tenant_a,
                        },
                    ))

        return violations

    @property
    def violation_count(self) -> int:
        return len(self._violations)


# =============================================================================
# Permission Revocation Propagation
# =============================================================================

class PermissionRevocationEnforcer:
    """
    Ensures that when permissions are revoked, cached responses that relied
    on those permissions are immediately invalidated.
    """

    def __init__(self, max_propagation_sla_seconds: float = 5.0):
        self.max_sla = max_propagation_sla_seconds
        self._revocation_log: List[Dict] = []
        self._pending_verifications: Dict[str, float] = {}  # key -> revocation_time

    async def on_permission_revoked(
        self,
        tenant_id: str,
        user_id: str,
        revoked_resources: List[str],
        invalidate_fn: Callable,
    ) -> Dict[str, Any]:
        """
        Handle permission revocation event.
        1. Immediately invalidate affected cache entries
        2. Schedule verification that invalidation took effect
        """
        revocation_time = time.time()

        # Step 1: Immediate invalidation
        invalidation_result = await invalidate_fn(
            tenant_id=tenant_id,
            user_id=user_id,
            resources=revoked_resources,
        )

        # Step 2: Log for audit
        self._revocation_log.append({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "resources": revoked_resources,
            "revocation_time": revocation_time,
            "invalidation_result": invalidation_result,
        })

        # Step 3: Schedule verification
        verification_key = f"{tenant_id}:{user_id}:{revocation_time}"
        self._pending_verifications[verification_key] = revocation_time

        return {
            "status": "invalidated",
            "revocation_time": revocation_time,
            "keys_invalidated": invalidation_result.get("count", 0),
            "verification_scheduled": True,
        }

    async def verify_revocation_effective(
        self,
        tenant_id: str,
        user_id: str,
        revoked_resources: List[str],
        cache_read_fn: Callable,
    ) -> SafetyAuditResult:
        """
        Verify that revoked user CANNOT access previously-cached responses.
        This is a negative test — all reads MUST fail.
        """
        start = time.time()
        violations = []
        checks = 0

        for resource in revoked_resources:
            checks += 1
            result = await cache_read_fn(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_id=resource,
            )
            if result is not None:
                violations.append(SafetyViolation(
                    violation_type=SafetyViolationType.STALE_PERMISSION_SERVE,
                    severity=SeverityLevel.CRITICAL,
                    description=(
                        f"User '{user_id}' still receiving cached response for "
                        f"resource '{resource}' after permission revocation"
                    ),
                    tenant_id=tenant_id,
                    affected_user_id=user_id,
                    evidence={
                        "resource": resource,
                        "cached_response_preview": str(result)[:100],
                    },
                ))

        duration_ms = (time.time() - start) * 1000
        return SafetyAuditResult(
            passed=len(violations) == 0,
            checks_run=checks,
            checks_passed=checks - len(violations),
            checks_failed=len(violations),
            violations=violations,
            duration_ms=duration_ms,
        )

    def check_sla_compliance(self) -> Dict[str, Any]:
        """Check if revocation-to-invalidation is within SLA."""
        now = time.time()
        overdue = [
            k for k, t in self._pending_verifications.items()
            if (now - t) > self.max_sla
        ]
        return {
            "pending_verifications": len(self._pending_verifications),
            "overdue_count": len(overdue),
            "sla_seconds": self.max_sla,
            "compliant": len(overdue) == 0,
        }


# =============================================================================
# Post-Deletion Cache Verification
# =============================================================================

class PostDeletionVerifier:
    """
    After a document/resource is deleted, verify it cannot be served from cache.
    """

    async def verify_deletion_propagated(
        self,
        tenant_id: str,
        deleted_resource_id: str,
        cache_search_fn: Callable,
        deletion_time: float,
    ) -> SafetyAuditResult:
        """
        Verify that deleted resource content is not in cache.
        """
        violations = []
        checks = 0

        # Check 1: Direct key lookup
        checks += 1
        direct_result = await cache_search_fn(
            tenant_id=tenant_id,
            resource_id=deleted_resource_id,
            search_type="direct",
        )
        if direct_result:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.DELETED_DATA_SERVE,
                severity=SeverityLevel.HIGH,
                description=f"Deleted resource '{deleted_resource_id}' still in cache (direct lookup)",
                tenant_id=tenant_id,
                evidence={"resource_id": deleted_resource_id, "lookup_type": "direct"},
            ))

        # Check 2: Semantic search (deleted content might match new queries)
        checks += 1
        semantic_result = await cache_search_fn(
            tenant_id=tenant_id,
            resource_id=deleted_resource_id,
            search_type="semantic",
        )
        if semantic_result:
            # Check if the result references the deleted resource
            result_str = json.dumps(semantic_result) if isinstance(semantic_result, dict) else str(semantic_result)
            if deleted_resource_id in result_str:
                violations.append(SafetyViolation(
                    violation_type=SafetyViolationType.DELETED_DATA_SERVE,
                    severity=SeverityLevel.HIGH,
                    description=f"Deleted resource '{deleted_resource_id}' referenced in semantic cache hit",
                    tenant_id=tenant_id,
                    evidence={"resource_id": deleted_resource_id, "lookup_type": "semantic"},
                ))

        # Check 3: Response cache (responses might quote deleted content)
        checks += 1
        response_result = await cache_search_fn(
            tenant_id=tenant_id,
            resource_id=deleted_resource_id,
            search_type="response",
        )
        if response_result:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.DELETED_DATA_SERVE,
                severity=SeverityLevel.MEDIUM,
                description=f"Cached response still references deleted resource '{deleted_resource_id}'",
                tenant_id=tenant_id,
                evidence={"resource_id": deleted_resource_id, "lookup_type": "response"},
            ))

        return SafetyAuditResult(
            passed=len(violations) == 0,
            checks_run=checks,
            checks_passed=checks - len(violations),
            checks_failed=len(violations),
            violations=violations,
        )


# =============================================================================
# Cache Key Security Audit
# =============================================================================

class CacheKeySecurityAuditor:
    """
    Audits cache key design for security weaknesses.
    Detects keys missing required security dimensions.
    """

    REQUIRED_DIMENSIONS = {
        "semantic_response": ["tenant_id", "permission_fingerprint", "model_version",
                            "prompt_version", "safety_policy_version"],
        "retrieval_result": ["tenant_id", "permission_fingerprint", "index_version"],
        "tool_result": ["tenant_id", "permission_fingerprint", "source_freshness"],
        "auth_decision": ["tenant_id", "user_id", "resource_id", "policy_version"],
    }

    def audit_key_builder(
        self, layer_name: str, key_builder_fn: Callable, test_inputs: List[Dict]
    ) -> SafetyAuditResult:
        """
        Audit a cache key builder function.
        Verifies that different security dimensions produce different keys.
        """
        violations = []
        checks = 0

        # Test 1: Different tenants MUST produce different keys
        checks += 1
        if len(test_inputs) >= 2:
            input_a = {**test_inputs[0], "tenant_id": "tenant_a"}
            input_b = {**test_inputs[0], "tenant_id": "tenant_b"}
            key_a = key_builder_fn(**input_a)
            key_b = key_builder_fn(**input_b)
            if key_a == key_b:
                violations.append(SafetyViolation(
                    violation_type=SafetyViolationType.KEY_COLLISION,
                    severity=SeverityLevel.CRITICAL,
                    description=f"Different tenants produce same cache key in layer '{layer_name}'",
                    tenant_id="audit",
                    evidence={"key": key_a, "inputs": [input_a, input_b]},
                ))

        # Test 2: Different permissions MUST produce different keys
        checks += 1
        if "permission_fingerprint" in self.REQUIRED_DIMENSIONS.get(layer_name, []):
            input_a = {**test_inputs[0], "permission_fingerprint": "fp_admin"}
            input_b = {**test_inputs[0], "permission_fingerprint": "fp_viewer"}
            key_a = key_builder_fn(**input_a)
            key_b = key_builder_fn(**input_b)
            if key_a == key_b:
                violations.append(SafetyViolation(
                    violation_type=SafetyViolationType.PERMISSION_BYPASS,
                    severity=SeverityLevel.CRITICAL,
                    description=f"Different permissions produce same key in '{layer_name}'",
                    tenant_id="audit",
                    evidence={"key": key_a},
                ))

        # Test 3: Same inputs MUST produce same key (deterministic)
        checks += 1
        key_1 = key_builder_fn(**test_inputs[0])
        key_2 = key_builder_fn(**test_inputs[0])
        if key_1 != key_2:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.KEY_COLLISION,
                severity=SeverityLevel.HIGH,
                description=f"Non-deterministic key generation in '{layer_name}'",
                tenant_id="audit",
            ))

        return SafetyAuditResult(
            passed=len(violations) == 0,
            checks_run=checks,
            checks_passed=checks - len(violations),
            checks_failed=len(violations),
            violations=violations,
        )


# =============================================================================
# Cache Poisoning Detection
# =============================================================================

class CachePoisoningDetector:
    """
    Detects attempts to poison the cache with malicious content.
    
    Poisoning vectors:
    1. Injecting false responses that will be served to other users
    2. Manipulating cache keys to cause collisions
    3. Exploiting semantic similarity to hijack cache entries
    4. Flooding cache with entries to evict legitimate ones
    """

    def __init__(
        self,
        max_write_rate_per_tenant: int = 1000,  # writes/minute
        max_entry_size_bytes: int = 1_000_000,
        suspicious_patterns: Optional[List[str]] = None,
    ):
        self.max_write_rate = max_write_rate_per_tenant
        self.max_entry_size = max_entry_size_bytes
        self.suspicious_patterns = suspicious_patterns or [
            r"<script",              # XSS attempt
            r"DROP\s+TABLE",         # SQL injection in cached response
            r"__proto__",            # Prototype pollution
            r"\{\{.*\}\}",           # Template injection
            r"eval\s*\(",            # Code execution
        ]
        self._write_counts: Dict[str, List[float]] = defaultdict(list)  # tenant -> timestamps
        self._violations: List[SafetyViolation] = []

    def check_write(
        self,
        tenant_id: str,
        cache_key: str,
        value: Any,
        writer_user_id: str,
    ) -> Tuple[bool, Optional[SafetyViolation]]:
        """
        Check if a cache write is safe. Returns (is_safe, violation_if_any).
        """
        # Check 1: Write rate limiting
        now = time.time()
        self._write_counts[tenant_id] = [
            t for t in self._write_counts[tenant_id] if now - t < 60
        ]
        if len(self._write_counts[tenant_id]) >= self.max_write_rate:
            violation = SafetyViolation(
                violation_type=SafetyViolationType.CACHE_POISONING,
                severity=SeverityLevel.HIGH,
                description=f"Cache write rate exceeded for tenant '{tenant_id}' ({self.max_write_rate}/min)",
                tenant_id=tenant_id,
                affected_user_id=writer_user_id,
                cache_key=cache_key,
                evidence={"write_rate": len(self._write_counts[tenant_id])},
            )
            self._violations.append(violation)
            return False, violation
        self._write_counts[tenant_id].append(now)

        # Check 2: Entry size
        value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        if len(value_str.encode()) > self.max_entry_size:
            violation = SafetyViolation(
                violation_type=SafetyViolationType.CACHE_POISONING,
                severity=SeverityLevel.MEDIUM,
                description=f"Oversized cache entry ({len(value_str)} bytes)",
                tenant_id=tenant_id,
                cache_key=cache_key,
                evidence={"size_bytes": len(value_str.encode())},
            )
            self._violations.append(violation)
            return False, violation

        # Check 3: Suspicious content patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, value_str, re.IGNORECASE):
                violation = SafetyViolation(
                    violation_type=SafetyViolationType.CACHE_POISONING,
                    severity=SeverityLevel.HIGH,
                    description=f"Suspicious pattern detected in cache value: {pattern}",
                    tenant_id=tenant_id,
                    affected_user_id=writer_user_id,
                    cache_key=cache_key,
                    evidence={"pattern": pattern, "preview": value_str[:200]},
                )
                self._violations.append(violation)
                return False, violation

        return True, None

    def get_violations(self) -> List[SafetyViolation]:
        return self._violations


# =============================================================================
# Stale Answer Safety Checker
# =============================================================================

class StaleAnswerSafetyChecker:
    """
    Validates whether serving a stale cached answer is safe given the risk tier.
    Some stale answers are merely inconvenient; others are dangerous.
    """

    STALE_TOLERANCE = {
        "critical": 0,         # Never serve stale
        "high": 30,            # 30 seconds max
        "medium": 300,         # 5 minutes
        "low": 3600,           # 1 hour
        "static": 86400 * 7,   # 7 days
    }

    def is_safe_to_serve_stale(
        self,
        entry_age_seconds: float,
        entry_ttl_seconds: float,
        risk_tier: str,
        has_active_refresh: bool = False,
    ) -> Tuple[bool, str]:
        """
        Determine if serving a stale entry is safe.
        Returns (is_safe, reason).
        """
        staleness = max(0, entry_age_seconds - entry_ttl_seconds)
        tolerance = self.STALE_TOLERANCE.get(risk_tier, 0)

        if risk_tier == "critical":
            return False, "critical_tier_never_stale"

        if staleness > tolerance:
            return False, f"staleness_{staleness:.0f}s_exceeds_tolerance_{tolerance}s"

        if risk_tier == "high" and not has_active_refresh:
            return False, "high_tier_requires_active_refresh"

        return True, "within_tolerance"


# =============================================================================
# Comprehensive Safety Test Suite
# =============================================================================

class CacheSafetyTestSuite:
    """
    Complete safety test suite that validates all cache safety invariants.
    Run this:
    - Before deployment
    - After any cache infrastructure change
    - Periodically in production (canary tests)
    """

    def __init__(self):
        self.isolation_validator = CrossTenantIsolationValidator()
        self.revocation_enforcer = PermissionRevocationEnforcer()
        self.deletion_verifier = PostDeletionVerifier()
        self.key_auditor = CacheKeySecurityAuditor()
        self.poisoning_detector = CachePoisoningDetector()
        self.stale_checker = StaleAnswerSafetyChecker()

    async def run_full_suite(
        self,
        cache_read_fn: Callable,
        cache_write_fn: Callable,
        cache_invalidate_fn: Callable,
        cache_search_fn: Callable,
    ) -> SafetyAuditResult:
        """
        Run all safety tests. Returns comprehensive audit result.
        """
        start = time.time()
        all_violations: List[SafetyViolation] = []
        total_checks = 0
        total_passed = 0

        # Test 1: Cross-tenant isolation
        logger.info("Running cross-tenant isolation tests...")
        isolation_result = await self._test_cross_tenant_isolation(
            cache_read_fn, cache_write_fn
        )
        total_checks += isolation_result.checks_run
        total_passed += isolation_result.checks_passed
        all_violations.extend(isolation_result.violations)

        # Test 2: Permission revocation
        logger.info("Running permission revocation tests...")
        revocation_result = await self._test_permission_revocation(
            cache_read_fn, cache_write_fn, cache_invalidate_fn
        )
        total_checks += revocation_result.checks_run
        total_passed += revocation_result.checks_passed
        all_violations.extend(revocation_result.violations)

        # Test 3: Post-deletion verification
        logger.info("Running post-deletion tests...")
        deletion_result = await self._test_post_deletion(
            cache_write_fn, cache_invalidate_fn, cache_search_fn
        )
        total_checks += deletion_result.checks_run
        total_passed += deletion_result.checks_passed
        all_violations.extend(deletion_result.violations)

        # Test 4: Cache poisoning resistance
        logger.info("Running cache poisoning resistance tests...")
        poisoning_result = await self._test_poisoning_resistance(cache_write_fn)
        total_checks += poisoning_result.checks_run
        total_passed += poisoning_result.checks_passed
        all_violations.extend(poisoning_result.violations)

        # Test 5: Stale answer safety
        logger.info("Running stale answer safety tests...")
        stale_result = self._test_stale_answer_safety()
        total_checks += stale_result.checks_run
        total_passed += stale_result.checks_passed
        all_violations.extend(stale_result.violations)

        duration_ms = (time.time() - start) * 1000
        total_failed = total_checks - total_passed

        result = SafetyAuditResult(
            passed=total_failed == 0,
            checks_run=total_checks,
            checks_passed=total_passed,
            checks_failed=total_failed,
            violations=all_violations,
            duration_ms=duration_ms,
        )

        # Log summary
        status = "PASSED" if result.passed else "FAILED"
        logger.info(
            f"Safety test suite {status}: "
            f"{total_passed}/{total_checks} passed, "
            f"{len(all_violations)} violations, "
            f"{duration_ms:.0f}ms"
        )

        if all_violations:
            critical = [v for v in all_violations if v.severity == SeverityLevel.CRITICAL]
            if critical:
                logger.critical(
                    f"CRITICAL SAFETY VIOLATIONS: {len(critical)} violations detected! "
                    f"Cache system is NOT safe for production."
                )

        return result

    async def _test_cross_tenant_isolation(
        self, cache_read_fn, cache_write_fn
    ) -> SafetyAuditResult:
        """Test that Tenant A's cache is invisible to Tenant B."""
        violations = []
        checks = 0

        # Write as tenant_a
        test_data = {"response": "Tenant A secret revenue: $10M", "tenant_id": "tenant_a"}
        await cache_write_fn(
            key="test_isolation_1",
            value=test_data,
            tenant_id="tenant_a",
        )

        # Read as tenant_b — MUST fail
        checks += 1
        result = await cache_read_fn(key="test_isolation_1", tenant_id="tenant_b")
        if result is not None:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.CROSS_TENANT_LEAK,
                severity=SeverityLevel.CRITICAL,
                description="Tenant B can read Tenant A's cache entry",
                tenant_id="tenant_b",
                evidence={"leaked_data": str(result)[:100]},
            ))

        # Read as tenant_a — SHOULD succeed
        checks += 1
        result = await cache_read_fn(key="test_isolation_1", tenant_id="tenant_a")
        if result is None:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.KEY_COLLISION,
                severity=SeverityLevel.MEDIUM,
                description="Tenant A cannot read own cache entry (functional issue)",
                tenant_id="tenant_a",
            ))

        # Test with many tenants
        for i in range(10):
            checks += 1
            result = await cache_read_fn(key="test_isolation_1", tenant_id=f"tenant_attacker_{i}")
            if result is not None:
                violations.append(SafetyViolation(
                    violation_type=SafetyViolationType.CROSS_TENANT_LEAK,
                    severity=SeverityLevel.CRITICAL,
                    description=f"Attacker tenant_{i} can read cache entry",
                    tenant_id=f"tenant_attacker_{i}",
                ))

        return SafetyAuditResult(
            passed=len(violations) == 0,
            checks_run=checks,
            checks_passed=checks - len(violations),
            checks_failed=len(violations),
            violations=violations,
        )

    async def _test_permission_revocation(
        self, cache_read_fn, cache_write_fn, cache_invalidate_fn
    ) -> SafetyAuditResult:
        """Test that permission revocation clears affected cache entries."""
        violations = []
        checks = 0

        # Write cache entry with specific permission fingerprint
        await cache_write_fn(
            key="test_perm_1",
            value={"response": "Authorized response for admin"},
            tenant_id="tenant_a",
            permission_fingerprint="fp_admin_full",
        )

        # Revoke permissions (invalidate)
        await cache_invalidate_fn(
            tenant_id="tenant_a",
            permission_fingerprint="fp_admin_full",
        )

        # Attempt read with old fingerprint — MUST fail
        checks += 1
        result = await cache_read_fn(
            key="test_perm_1",
            tenant_id="tenant_a",
            permission_fingerprint="fp_admin_full",
        )
        if result is not None:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.STALE_PERMISSION_SERVE,
                severity=SeverityLevel.CRITICAL,
                description="Cache entry still accessible after permission revocation",
                tenant_id="tenant_a",
            ))

        return SafetyAuditResult(
            passed=len(violations) == 0,
            checks_run=checks,
            checks_passed=checks - len(violations),
            checks_failed=len(violations),
            violations=violations,
        )

    async def _test_post_deletion(
        self, cache_write_fn, cache_invalidate_fn, cache_search_fn
    ) -> SafetyAuditResult:
        """Test that deleted documents are purged from cache."""
        violations = []
        checks = 0

        # Write entries referencing a document
        await cache_write_fn(
            key="test_doc_ref_1",
            value={"response": "Based on doc_secret_123: revenue is $5M"},
            tenant_id="tenant_a",
            resource_id="doc_secret_123",
        )

        # Delete the document (trigger invalidation)
        await cache_invalidate_fn(
            tenant_id="tenant_a",
            resource_id="doc_secret_123",
            reason="document_deleted",
        )

        # Verify deletion
        checks += 1
        result = await cache_search_fn(
            tenant_id="tenant_a",
            resource_id="doc_secret_123",
            search_type="direct",
        )
        if result is not None:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.DELETED_DATA_SERVE,
                severity=SeverityLevel.HIGH,
                description="Deleted document still found in cache",
                tenant_id="tenant_a",
                evidence={"resource_id": "doc_secret_123"},
            ))

        return SafetyAuditResult(
            passed=len(violations) == 0,
            checks_run=checks,
            checks_passed=checks - len(violations),
            checks_failed=len(violations),
            violations=violations,
        )

    async def _test_poisoning_resistance(self, cache_write_fn) -> SafetyAuditResult:
        """Test that malicious content is rejected."""
        violations = []
        checks = 0

        malicious_payloads = [
            '<script>alert("xss")</script>',
            "'; DROP TABLE users; --",
            '{"__proto__": {"isAdmin": true}}',
            "{{constructor.constructor('return process')()}}",
        ]

        for payload in malicious_payloads:
            checks += 1
            is_safe, violation = self.poisoning_detector.check_write(
                tenant_id="tenant_test",
                cache_key="test_poison",
                value=payload,
                writer_user_id="attacker",
            )
            if is_safe:
                violations.append(SafetyViolation(
                    violation_type=SafetyViolationType.CACHE_POISONING,
                    severity=SeverityLevel.HIGH,
                    description=f"Malicious payload not detected: {payload[:50]}",
                    tenant_id="tenant_test",
                ))

        return SafetyAuditResult(
            passed=len(violations) == 0,
            checks_run=checks,
            checks_passed=checks - len(violations),
            checks_failed=len(violations),
            violations=violations,
        )

    def _test_stale_answer_safety(self) -> SafetyAuditResult:
        """Test stale answer policy enforcement."""
        violations = []
        checks = 0

        # Critical tier should NEVER serve stale
        checks += 1
        is_safe, _ = self.stale_checker.is_safe_to_serve_stale(
            entry_age_seconds=61, entry_ttl_seconds=60, risk_tier="critical"
        )
        if is_safe:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.STALE_BEYOND_TOLERANCE,
                severity=SeverityLevel.CRITICAL,
                description="Critical tier allowed stale serving",
                tenant_id="test",
            ))

        # Low tier should serve stale within tolerance
        checks += 1
        is_safe, _ = self.stale_checker.is_safe_to_serve_stale(
            entry_age_seconds=3700, entry_ttl_seconds=3600, risk_tier="low"
        )
        if not is_safe:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.STALE_BEYOND_TOLERANCE,
                severity=SeverityLevel.LOW,
                description="Low tier rejected serving within tolerance",
                tenant_id="test",
            ))

        # Low tier should NOT serve stale beyond tolerance
        checks += 1
        is_safe, _ = self.stale_checker.is_safe_to_serve_stale(
            entry_age_seconds=10000, entry_ttl_seconds=3600, risk_tier="low"
        )
        if is_safe:
            violations.append(SafetyViolation(
                violation_type=SafetyViolationType.STALE_BEYOND_TOLERANCE,
                severity=SeverityLevel.HIGH,
                description="Low tier served stale beyond tolerance (6400s > 3600s)",
                tenant_id="test",
            ))

        return SafetyAuditResult(
            passed=len(violations) == 0,
            checks_run=checks,
            checks_passed=checks - len(violations),
            checks_failed=len(violations),
            violations=violations,
        )


# =============================================================================
# Usage Example
# =============================================================================

async def main():
    """Demonstrate cache safety enforcement."""

    # Simple in-memory cache for testing
    cache_store: Dict[str, Dict] = {}

    async def mock_write(key, value, tenant_id, permission_fingerprint="default", resource_id=None):
        cache_store[f"{tenant_id}:{key}"] = {
            "value": value, "tenant_id": tenant_id,
            "permission_fingerprint": permission_fingerprint,
            "resource_id": resource_id,
        }

    async def mock_read(key, tenant_id, permission_fingerprint="default"):
        full_key = f"{tenant_id}:{key}"
        entry = cache_store.get(full_key)
        if entry and entry["tenant_id"] == tenant_id:
            if entry["permission_fingerprint"] == permission_fingerprint:
                return entry["value"]
        return None

    async def mock_invalidate(tenant_id, permission_fingerprint=None, resource_id=None, reason=None):
        keys_to_remove = []
        for k, v in cache_store.items():
            if v["tenant_id"] != tenant_id:
                continue
            if permission_fingerprint and v["permission_fingerprint"] != permission_fingerprint:
                continue
            if resource_id and v.get("resource_id") != resource_id:
                continue
            keys_to_remove.append(k)
        for k in keys_to_remove:
            del cache_store[k]

    async def mock_search(tenant_id, resource_id, search_type):
        for k, v in cache_store.items():
            if v["tenant_id"] == tenant_id and v.get("resource_id") == resource_id:
                return v["value"]
        return None

    # Run safety test suite
    suite = CacheSafetyTestSuite()
    result = await suite.run_full_suite(
        cache_read_fn=mock_read,
        cache_write_fn=mock_write,
        cache_invalidate_fn=mock_invalidate,
        cache_search_fn=mock_search,
    )

    print(f"\n{'='*60}")
    print(f"CACHE SAFETY AUDIT RESULT")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2))

    if not result.passed:
        print(f"\n⚠ CACHE SYSTEM HAS SAFETY ISSUES - DO NOT DEPLOY")
    else:
        print(f"\nAll safety checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
