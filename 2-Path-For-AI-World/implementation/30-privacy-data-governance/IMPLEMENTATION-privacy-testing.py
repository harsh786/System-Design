"""
Privacy Testing Suite for AI Systems
======================================
Tests for PII leakage, cross-tenant isolation, memory privacy,
log redaction, prompt exposure, vendor transmission, retention compliance,
and deletion completeness.
"""

import asyncio
import hashlib
import json
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional


# =============================================================================
# TEST FRAMEWORK
# =============================================================================

class TestSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKER = "blocker"


class TestResult(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class PrivacyTestResult:
    test_id: str
    test_name: str
    category: str
    result: TestResult
    severity: TestSeverity
    details: str
    evidence: list[dict] = field(default_factory=list)
    duration_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PrivacyTestSuite:
    suite_name: str
    results: list[PrivacyTestResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.result == TestResult.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.result == TestResult.FAILED)

    @property
    def summary(self) -> dict:
        return {
            "suite": self.suite_name,
            "total": len(self.results),
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.passed / max(len(self.results), 1),
            "critical_failures": [
                r for r in self.results
                if r.result == TestResult.FAILED and r.severity in (TestSeverity.CRITICAL, TestSeverity.BLOCKER)
            ],
        }


class PrivacyTest(ABC):
    """Base class for privacy tests."""

    @property
    @abstractmethod
    def test_name(self) -> str:
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        pass

    @property
    def severity(self) -> TestSeverity:
        return TestSeverity.CRITICAL

    @abstractmethod
    async def execute(self, context: dict) -> PrivacyTestResult:
        pass

    def _result(self, result: TestResult, details: str, evidence: list[dict] = None, duration_ms: float = 0) -> PrivacyTestResult:
        return PrivacyTestResult(
            test_id=str(uuid.uuid4()),
            test_name=self.test_name,
            category=self.category,
            result=result,
            severity=self.severity,
            details=details,
            evidence=evidence or [],
            duration_ms=duration_ms,
        )


# =============================================================================
# PII LEAKAGE DETECTION TESTS
# =============================================================================

class PIILeakageInOutputTest(PrivacyTest):
    """Test that LLM outputs don't leak PII from context."""

    @property
    def test_name(self) -> str:
        return "pii_leakage_in_output"

    @property
    def category(self) -> str:
        return "pii_leakage"

    PII_PATTERNS = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b(?:\d{4}[\s-]?){3}\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
    }

    async def execute(self, context: dict) -> PrivacyTestResult:
        """Check model outputs for PII leakage."""
        start = time.time()
        outputs = context.get("model_outputs", [])
        known_pii = context.get("known_pii_in_context", [])
        leaks = []

        for i, output in enumerate(outputs):
            # Check for known PII values
            for pii_value in known_pii:
                if pii_value in output:
                    leaks.append({
                        "output_index": i,
                        "leaked_value_hash": hashlib.sha256(pii_value.encode()).hexdigest()[:12],
                        "type": "known_pii_echo",
                    })

            # Check for PII patterns in output
            for pii_type, pattern in self.PII_PATTERNS.items():
                matches = re.findall(pattern, output)
                for match in matches:
                    match_str = match if isinstance(match, str) else match[0]
                    if match_str not in context.get("expected_pii_in_output", []):
                        leaks.append({
                            "output_index": i,
                            "pii_type": pii_type,
                            "value_hash": hashlib.sha256(match_str.encode()).hexdigest()[:12],
                            "type": "pattern_match",
                        })

        duration = (time.time() - start) * 1000
        if leaks:
            return self._result(
                TestResult.FAILED,
                f"Found {len(leaks)} PII leakage instances in model outputs",
                evidence=leaks,
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "No PII leakage detected in outputs", duration_ms=duration)


class PIIInPromptConstructionTest(PrivacyTest):
    """Test that prompts don't include unnecessary PII."""

    @property
    def test_name(self) -> str:
        return "pii_in_prompt_construction"

    @property
    def category(self) -> str:
        return "pii_leakage"

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        prompts = context.get("constructed_prompts", [])
        pii_patterns = PIILeakageInOutputTest.PII_PATTERNS
        issues = []

        for i, prompt in enumerate(prompts):
            prompt_pii = {}
            for pii_type, pattern in pii_patterns.items():
                matches = re.findall(pattern, prompt)
                if matches:
                    prompt_pii[pii_type] = len(matches)

            if prompt_pii:
                # Check if this PII is necessary for the task
                task_requires_pii = context.get("task_requires_pii", False)
                if not task_requires_pii:
                    issues.append({
                        "prompt_index": i,
                        "pii_types_found": prompt_pii,
                        "prompt_length": len(prompt),
                    })

        duration = (time.time() - start) * 1000
        if issues:
            return self._result(
                TestResult.FAILED,
                f"Found unnecessary PII in {len(issues)} prompts",
                evidence=issues,
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "Prompts contain only necessary data", duration_ms=duration)


# =============================================================================
# CROSS-TENANT ISOLATION TESTS
# =============================================================================

class CrossTenantDataLeakageTest(PrivacyTest):
    """Test that one tenant's data never appears in another tenant's context."""

    @property
    def test_name(self) -> str:
        return "cross_tenant_data_leakage"

    @property
    def category(self) -> str:
        return "tenant_isolation"

    @property
    def severity(self) -> TestSeverity:
        return TestSeverity.BLOCKER

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        tenants = context.get("tenants", [])
        query_fn = context.get("query_function")  # Function to query system as tenant
        leaks = []

        if not query_fn or len(tenants) < 2:
            return self._result(TestResult.SKIPPED, "Insufficient context for tenant isolation test")

        # For each tenant, query the system and check if other tenants' data appears
        for tenant in tenants:
            other_tenants = [t for t in tenants if t["id"] != tenant["id"]]
            other_data_markers = []
            for other in other_tenants:
                other_data_markers.extend(other.get("unique_markers", []))

            # Query as this tenant
            try:
                results = await query_fn(tenant["id"], tenant.get("test_query", ""))
                result_text = json.dumps(results) if isinstance(results, dict) else str(results)

                for marker in other_data_markers:
                    if marker in result_text:
                        leaks.append({
                            "querying_tenant": tenant["id"],
                            "leaked_marker_hash": hashlib.sha256(marker.encode()).hexdigest()[:12],
                            "context": "Data from another tenant appeared in query results",
                        })
            except Exception as e:
                leaks.append({
                    "querying_tenant": tenant["id"],
                    "error": str(e),
                })

        duration = (time.time() - start) * 1000
        if leaks:
            return self._result(
                TestResult.FAILED,
                f"CRITICAL: Cross-tenant data leakage detected ({len(leaks)} instances)",
                evidence=leaks,
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "Tenant isolation verified", duration_ms=duration)


class CrossTenantVectorSearchTest(PrivacyTest):
    """Test that vector search respects tenant boundaries."""

    @property
    def test_name(self) -> str:
        return "cross_tenant_vector_search"

    @property
    def category(self) -> str:
        return "tenant_isolation"

    @property
    def severity(self) -> TestSeverity:
        return TestSeverity.BLOCKER

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        vector_search_fn = context.get("vector_search_function")
        tenants = context.get("tenants", [])
        leaks = []

        if not vector_search_fn:
            return self._result(TestResult.SKIPPED, "No vector search function provided")

        for tenant in tenants:
            # Search using queries that should match another tenant's documents
            for other_tenant in tenants:
                if other_tenant["id"] == tenant["id"]:
                    continue
                test_queries = other_tenant.get("document_queries", [])
                for query in test_queries:
                    try:
                        results = await vector_search_fn(tenant["id"], query)
                        for result in results:
                            if result.get("tenant_id") != tenant["id"]:
                                leaks.append({
                                    "querying_tenant": tenant["id"],
                                    "result_tenant": result.get("tenant_id"),
                                    "query": query[:50],
                                })
                    except Exception:
                        pass

        duration = (time.time() - start) * 1000
        if leaks:
            return self._result(
                TestResult.FAILED,
                f"Vector search returned cross-tenant results ({len(leaks)} leaks)",
                evidence=leaks,
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "Vector search respects tenant boundaries", duration_ms=duration)


# =============================================================================
# MEMORY PRIVACY TESTS
# =============================================================================

class MemoryPrivacyTest(PrivacyTest):
    """Test that memory system respects privacy boundaries."""

    @property
    def test_name(self) -> str:
        return "memory_privacy_isolation"

    @property
    def category(self) -> str:
        return "memory_privacy"

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        memory_query_fn = context.get("memory_query_function")
        users = context.get("test_users", [])
        violations = []

        if not memory_query_fn:
            return self._result(TestResult.SKIPPED, "No memory query function provided")

        for user in users:
            # Query memories as this user
            memories = await memory_query_fn(user["id"])

            # Check that no other user's private data appears
            for other_user in users:
                if other_user["id"] == user["id"]:
                    continue
                private_markers = other_user.get("private_markers", [])
                for marker in private_markers:
                    memory_text = json.dumps(memories)
                    if marker in memory_text:
                        violations.append({
                            "querying_user": user["id"],
                            "exposed_user": other_user["id"],
                            "marker_hash": hashlib.sha256(marker.encode()).hexdigest()[:12],
                        })

        duration = (time.time() - start) * 1000
        if violations:
            return self._result(
                TestResult.FAILED,
                f"Memory privacy violated: {len(violations)} cross-user leaks",
                evidence=violations,
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "Memory system respects user boundaries", duration_ms=duration)


class MemoryDeletionVerificationTest(PrivacyTest):
    """Test that deleted memories are actually gone."""

    @property
    def test_name(self) -> str:
        return "memory_deletion_verification"

    @property
    def category(self) -> str:
        return "memory_privacy"

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        memory_store_fn = context.get("memory_store_function")
        memory_query_fn = context.get("memory_query_function")
        memory_delete_fn = context.get("memory_delete_function")

        if not all([memory_store_fn, memory_query_fn, memory_delete_fn]):
            return self._result(TestResult.SKIPPED, "Memory functions not provided")

        test_user = f"test-user-{uuid.uuid4().hex[:8]}"
        test_memory = f"Secret information: {uuid.uuid4().hex}"

        # Store a memory
        await memory_store_fn(test_user, test_memory)

        # Verify it exists
        memories_before = await memory_query_fn(test_user)
        if test_memory not in json.dumps(memories_before):
            return self._result(TestResult.ERROR, "Failed to store test memory")

        # Delete the memory
        await memory_delete_fn(test_user)

        # Verify it's gone
        memories_after = await memory_query_fn(test_user)
        duration = (time.time() - start) * 1000

        if test_memory in json.dumps(memories_after):
            return self._result(
                TestResult.FAILED,
                "Deleted memory still accessible after deletion",
                evidence=[{"user": test_user, "memory_still_present": True}],
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "Memory deletion verified", duration_ms=duration)


# =============================================================================
# LOG REDACTION TESTS
# =============================================================================

class LogRedactionTest(PrivacyTest):
    """Test that logs properly redact PII."""

    @property
    def test_name(self) -> str:
        return "log_redaction_verification"

    @property
    def category(self) -> str:
        return "log_privacy"

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        log_entries = context.get("log_entries", [])
        known_pii = context.get("known_pii_values", [])
        pii_patterns = PIILeakageInOutputTest.PII_PATTERNS
        violations = []

        for i, entry in enumerate(log_entries):
            entry_text = json.dumps(entry) if isinstance(entry, dict) else str(entry)

            # Check for known PII values
            for pii_value in known_pii:
                if pii_value in entry_text:
                    violations.append({
                        "entry_index": i,
                        "type": "known_pii_in_log",
                        "pii_hash": hashlib.sha256(pii_value.encode()).hexdigest()[:12],
                    })

            # Check for PII patterns (excluding redaction markers like [EMAIL])
            for pii_type, pattern in pii_patterns.items():
                matches = re.findall(pattern, entry_text)
                for match in matches:
                    match_str = match if isinstance(match, str) else match[0]
                    # Skip if it's inside a redaction marker
                    if f"[{pii_type.upper()}]" not in entry_text:
                        violations.append({
                            "entry_index": i,
                            "type": "unredacted_pii_pattern",
                            "pii_type": pii_type,
                        })

        duration = (time.time() - start) * 1000
        if violations:
            return self._result(
                TestResult.FAILED,
                f"Found {len(violations)} unredacted PII instances in logs",
                evidence=violations[:20],  # Limit evidence
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "All logs properly redacted", duration_ms=duration)


class TracePrivacyTest(PrivacyTest):
    """Test that observability traces don't expose PII."""

    @property
    def test_name(self) -> str:
        return "trace_privacy_verification"

    @property
    def category(self) -> str:
        return "log_privacy"

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        traces = context.get("trace_spans", [])
        violations = []
        pii_patterns = PIILeakageInOutputTest.PII_PATTERNS

        for i, span in enumerate(traces):
            # Check span attributes for PII
            attributes = span.get("attributes", {})
            for key, value in attributes.items():
                if isinstance(value, str):
                    for pii_type, pattern in pii_patterns.items():
                        if re.search(pattern, value):
                            violations.append({
                                "span_index": i,
                                "attribute_key": key,
                                "pii_type": pii_type,
                            })

            # Check span events
            for event in span.get("events", []):
                event_text = json.dumps(event)
                for pii_type, pattern in pii_patterns.items():
                    if re.search(pattern, event_text):
                        violations.append({
                            "span_index": i,
                            "event": event.get("name"),
                            "pii_type": pii_type,
                        })

        duration = (time.time() - start) * 1000
        if violations:
            return self._result(
                TestResult.FAILED,
                f"Found PII in {len(violations)} trace attributes/events",
                evidence=violations[:20],
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "Traces are PII-free", duration_ms=duration)


# =============================================================================
# VENDOR DATA TRANSMISSION TESTS
# =============================================================================

class VendorDataTransmissionTest(PrivacyTest):
    """Test that data sent to vendors is properly minimized and redacted."""

    @property
    def test_name(self) -> str:
        return "vendor_data_transmission"

    @property
    def category(self) -> str:
        return "vendor_privacy"

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        vendor_requests = context.get("captured_vendor_requests", [])
        disallowed_data_types = context.get("disallowed_vendor_data", ["ssn", "credit_card"])
        pii_patterns = PIILeakageInOutputTest.PII_PATTERNS
        violations = []

        for i, request in enumerate(vendor_requests):
            request_text = json.dumps(request) if isinstance(request, dict) else str(request)

            for data_type in disallowed_data_types:
                if data_type in pii_patterns:
                    matches = re.findall(pii_patterns[data_type], request_text)
                    if matches:
                        violations.append({
                            "request_index": i,
                            "vendor": request.get("vendor", "unknown"),
                            "data_type": data_type,
                            "match_count": len(matches),
                        })

        duration = (time.time() - start) * 1000
        if violations:
            return self._result(
                TestResult.FAILED,
                f"Disallowed data sent to vendors in {len(violations)} requests",
                evidence=violations,
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "Vendor data transmission is compliant", duration_ms=duration)


# =============================================================================
# RETENTION POLICY TESTS
# =============================================================================

class RetentionComplianceTest(PrivacyTest):
    """Test that data is deleted according to retention policies."""

    @property
    def test_name(self) -> str:
        return "retention_policy_compliance"

    @property
    def category(self) -> str:
        return "retention"

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        policies = context.get("retention_policies", {})  # {data_type: retention_days}
        data_ages = context.get("data_ages", {})  # {data_type: oldest_record_age_days}
        violations = []

        for data_type, max_days in policies.items():
            actual_age = data_ages.get(data_type, 0)
            if actual_age > max_days:
                violations.append({
                    "data_type": data_type,
                    "policy_days": max_days,
                    "actual_age_days": actual_age,
                    "overdue_days": actual_age - max_days,
                })

        duration = (time.time() - start) * 1000
        if violations:
            return self._result(
                TestResult.FAILED,
                f"Retention policy violated for {len(violations)} data types",
                evidence=violations,
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "All retention policies compliant", duration_ms=duration)


# =============================================================================
# DELETION COMPLETENESS TESTS
# =============================================================================

class DeletionCompletenessTest(PrivacyTest):
    """Test that deletion requests result in complete data removal."""

    @property
    def test_name(self) -> str:
        return "deletion_completeness"

    @property
    def category(self) -> str:
        return "deletion"

    @property
    def severity(self) -> TestSeverity:
        return TestSeverity.BLOCKER

    async def execute(self, context: dict) -> PrivacyTestResult:
        start = time.time()
        deleted_user_id = context.get("deleted_user_id")
        search_functions = context.get("search_functions", {})  # {system: search_fn}
        residual_data = []

        if not deleted_user_id:
            return self._result(TestResult.SKIPPED, "No deleted user ID provided")

        for system_name, search_fn in search_functions.items():
            try:
                results = await search_fn(deleted_user_id)
                if results:
                    residual_data.append({
                        "system": system_name,
                        "items_found": len(results) if isinstance(results, list) else 1,
                    })
            except Exception as e:
                residual_data.append({
                    "system": system_name,
                    "error": str(e),
                })

        duration = (time.time() - start) * 1000
        if residual_data:
            return self._result(
                TestResult.FAILED,
                f"Deleted user data found in {len(residual_data)} systems",
                evidence=residual_data,
                duration_ms=duration,
            )
        return self._result(TestResult.PASSED, "Deletion is complete across all systems", duration_ms=duration)


# =============================================================================
# PRIVACY REGRESSION TEST RUNNER
# =============================================================================

class PrivacyTestRunner:
    """Runs the complete privacy test suite."""

    def __init__(self):
        self._tests: list[PrivacyTest] = []
        self._suites: list[PrivacyTestSuite] = []

    def register_test(self, test: PrivacyTest):
        self._tests.append(test)

    def register_default_tests(self):
        """Register all default privacy tests."""
        self._tests = [
            PIILeakageInOutputTest(),
            PIIInPromptConstructionTest(),
            CrossTenantDataLeakageTest(),
            CrossTenantVectorSearchTest(),
            MemoryPrivacyTest(),
            MemoryDeletionVerificationTest(),
            LogRedactionTest(),
            TracePrivacyTest(),
            VendorDataTransmissionTest(),
            RetentionComplianceTest(),
            DeletionCompletenessTest(),
        ]

    async def run_all(self, context: dict) -> PrivacyTestSuite:
        """Run all registered tests."""
        suite = PrivacyTestSuite(
            suite_name="privacy_regression",
            started_at=datetime.utcnow(),
        )

        for test in self._tests:
            try:
                result = await test.execute(context)
                suite.results.append(result)
            except Exception as e:
                suite.results.append(PrivacyTestResult(
                    test_id=str(uuid.uuid4()),
                    test_name=test.test_name,
                    category=test.category,
                    result=TestResult.ERROR,
                    severity=test.severity,
                    details=f"Test execution error: {e}",
                ))

        suite.completed_at = datetime.utcnow()
        self._suites.append(suite)
        return suite

    async def run_category(self, category: str, context: dict) -> PrivacyTestSuite:
        """Run tests for a specific category."""
        suite = PrivacyTestSuite(
            suite_name=f"privacy_{category}",
            started_at=datetime.utcnow(),
        )

        tests = [t for t in self._tests if t.category == category]
        for test in tests:
            try:
                result = await test.execute(context)
                suite.results.append(result)
            except Exception as e:
                suite.results.append(PrivacyTestResult(
                    test_id=str(uuid.uuid4()),
                    test_name=test.test_name,
                    category=test.category,
                    result=TestResult.ERROR,
                    severity=test.severity,
                    details=f"Test execution error: {e}",
                ))

        suite.completed_at = datetime.utcnow()
        return suite

    def generate_report(self, suite: PrivacyTestSuite) -> str:
        """Generate human-readable test report."""
        lines = [
            f"Privacy Test Report: {suite.suite_name}",
            f"{'=' * 60}",
            f"Run at: {suite.started_at}",
            f"Duration: {(suite.completed_at - suite.started_at).total_seconds():.1f}s" if suite.completed_at else "",
            f"",
            f"Results: {suite.passed} passed, {suite.failed} failed, "
            f"{sum(1 for r in suite.results if r.result == TestResult.SKIPPED)} skipped",
            f"Pass rate: {suite.passed / max(len(suite.results), 1) * 100:.1f}%",
            f"",
        ]

        # Group by category
        categories = {}
        for result in suite.results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)

        for category, results in sorted(categories.items()):
            lines.append(f"\n[{category}]")
            for result in results:
                icon = "PASS" if result.result == TestResult.PASSED else "FAIL" if result.result == TestResult.FAILED else "SKIP"
                lines.append(f"  [{icon}] {result.test_name}: {result.details[:80]}")
                if result.result == TestResult.FAILED and result.evidence:
                    for ev in result.evidence[:3]:
                        lines.append(f"        Evidence: {json.dumps(ev)[:100]}")

        # Critical failures summary
        critical = [r for r in suite.results if r.result == TestResult.FAILED and r.severity in (TestSeverity.CRITICAL, TestSeverity.BLOCKER)]
        if critical:
            lines.append(f"\n{'!' * 60}")
            lines.append(f"CRITICAL FAILURES ({len(critical)}):")
            for r in critical:
                lines.append(f"  [{r.severity.value.upper()}] {r.test_name}")
            lines.append(f"{'!' * 60}")

        return "\n".join(lines)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def main():
    """Demonstrate privacy testing."""
    print("=" * 70)
    print("PRIVACY TEST SUITE DEMONSTRATION")
    print("=" * 70)

    runner = PrivacyTestRunner()
    runner.register_default_tests()

    # Create test context
    context = {
        # PII leakage test data
        "model_outputs": [
            "Your account balance is $5,432.10. Is there anything else I can help with?",
            "I found the document you uploaded. Here's a summary...",
            "Based on your history, here's my recommendation.",
        ],
        "known_pii_in_context": ["john.doe@example.com", "123-45-6789"],
        "constructed_prompts": [
            "User asks about their balance. User email: john.doe@example.com",
            "Summarize the following document for the user.",
        ],

        # Log test data
        "log_entries": [
            {"level": "info", "message": "Request processed", "user": "user-123"},
            {"level": "info", "message": "Email sent to [EMAIL]", "user": "user-123"},
            {"level": "error", "message": "Failed for user john.doe@example.com"},
        ],
        "known_pii_values": ["john.doe@example.com", "123-45-6789"],

        # Trace test data
        "trace_spans": [
            {"name": "llm_call", "attributes": {"model": "gpt-4", "tokens": 500}, "events": []},
            {"name": "db_query", "attributes": {"query": "SELECT * FROM users"}, "events": []},
        ],

        # Vendor test data
        "captured_vendor_requests": [
            {"vendor": "openai", "body": {"messages": [{"content": "What is machine learning?"}]}},
        ],
        "disallowed_vendor_data": ["ssn", "credit_card"],

        # Retention test data
        "retention_policies": {"conversations": 365, "logs": 90, "traces": 30},
        "data_ages": {"conversations": 200, "logs": 45, "traces": 35},
    }

    # Run all tests
    suite = await runner.run_all(context)

    # Print report
    report = runner.generate_report(suite)
    print(report)

    # Print summary
    print(f"\n\nSummary: {json.dumps(suite.summary, indent=2, default=str)}")


if __name__ == "__main__":
    asyncio.run(main())
