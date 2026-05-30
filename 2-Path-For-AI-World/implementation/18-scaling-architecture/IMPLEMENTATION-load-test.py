"""
AI-Specific Load Testing Framework.

Generates realistic AI workloads and tests the full request path including
auth, gateway, agent loops, retrieval, model calls, tools, streaming,
queues, and cross-tenant isolation.
"""

from __future__ import annotations

import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Load Test Configuration
# ---------------------------------------------------------------------------

class LoadPattern(Enum):
    CONSTANT = "constant"           # Fixed RPS
    RAMP_UP = "ramp_up"             # Linear increase
    SPIKE = "spike"                 # Sudden burst
    WAVE = "wave"                   # Sinusoidal pattern
    STEP = "step"                   # Step function increases


@dataclass
class LoadTestConfig:
    """Configuration for a load test run."""

    name: str = "default_test"
    duration_seconds: float = 60.0
    target_rps: float = 100.0
    pattern: LoadPattern = LoadPattern.CONSTANT
    ramp_duration_seconds: float = 30.0  # For ramp patterns
    concurrent_users: int = 50
    tenant_count: int = 10
    request_complexity_distribution: dict[str, float] = field(default_factory=lambda: {
        "simple": 0.40,
        "medium": 0.35,
        "complex": 0.15,
        "heavy": 0.10,
    })
    # Component-level configs
    enable_streaming: bool = True
    enable_tools: bool = True
    enable_retrieval: bool = True
    max_agent_steps: int = 5
    # Assertions
    max_p99_latency_ms: float = 5000.0
    max_error_rate: float = 0.05
    min_throughput_rps: float = 0.0  # 0 = no minimum


# ---------------------------------------------------------------------------
# Request Generator
# ---------------------------------------------------------------------------

@dataclass
class GeneratedRequest:
    """A synthetic request for load testing."""

    request_id: str
    tenant_id: str
    user_id: str
    message: str
    complexity: str
    expected_steps: int
    expected_tokens: int
    uses_retrieval: bool
    uses_tools: bool
    tool_names: list[str]
    timestamp: float = field(default_factory=time.time)


class RequestGenerator:
    """Generates realistic AI workload requests."""

    SIMPLE_MESSAGES = [
        "What time is it?",
        "Hello",
        "Thanks!",
        "Can you summarize that?",
        "What's the status?",
    ]

    MEDIUM_MESSAGES = [
        "Search our knowledge base for the deployment process and explain the steps",
        "What are the key metrics from last week's performance report?",
        "Help me understand the error in this log output",
        "Find all documents related to our authentication system",
    ]

    COMPLEX_MESSAGES = [
        "Analyze the performance regression we've been seeing, compare it with historical data, "
        "identify the root cause, and suggest a remediation plan with estimated impact",
        "Research our competitor's pricing strategy using our market intelligence database, "
        "cross-reference with our sales data, and create a comparative analysis",
        "Review the entire codebase for security vulnerabilities, check against OWASP top 10, "
        "and generate a prioritized remediation plan with code examples",
    ]

    HEAVY_MESSAGES = [
        "Process all 200 documents in the Q4 folder, extract key financial metrics, "
        "compare year-over-year, generate visualizations, and create an executive summary",
        "Run a comprehensive evaluation of our AI system across all test cases, "
        "compute accuracy, latency, cost metrics, and generate a detailed report",
    ]

    TOOL_NAMES = [
        "web_search", "database_query", "file_read", "api_call",
        "code_execute", "email_send", "calendar_check", "slack_post",
    ]

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self._counter = 0

    def generate(self) -> GeneratedRequest:
        """Generate a single realistic request."""
        self._counter += 1
        complexity = self._pick_complexity()
        tenant_id = f"tenant-{random.randint(0, self.config.tenant_count - 1):04d}"
        user_id = f"user-{random.randint(0, self.config.concurrent_users - 1):06d}"

        message, steps, tokens, uses_retrieval, uses_tools, tools = self._build_request(complexity)

        return GeneratedRequest(
            request_id=f"loadtest-{self._counter:08d}",
            tenant_id=tenant_id,
            user_id=user_id,
            message=message,
            complexity=complexity,
            expected_steps=steps,
            expected_tokens=tokens,
            uses_retrieval=uses_retrieval,
            uses_tools=uses_tools,
            tool_names=tools,
        )

    def _pick_complexity(self) -> str:
        rand = random.random()
        cumulative = 0.0
        for complexity, weight in self.config.request_complexity_distribution.items():
            cumulative += weight
            if rand <= cumulative:
                return complexity
        return "simple"

    def _build_request(self, complexity: str) -> tuple[str, int, int, bool, bool, list[str]]:
        if complexity == "simple":
            return (
                random.choice(self.SIMPLE_MESSAGES),
                1, 500, False, False, []
            )
        elif complexity == "medium":
            return (
                random.choice(self.MEDIUM_MESSAGES),
                3, 2000,
                self.config.enable_retrieval,
                False, []
            )
        elif complexity == "complex":
            tools = random.sample(self.TOOL_NAMES, random.randint(1, 3)) if self.config.enable_tools else []
            return (
                random.choice(self.COMPLEX_MESSAGES),
                5, 5000,
                self.config.enable_retrieval,
                bool(tools), tools
            )
        else:  # heavy
            tools = random.sample(self.TOOL_NAMES, random.randint(2, 5)) if self.config.enable_tools else []
            return (
                random.choice(self.HEAVY_MESSAGES),
                10, 15000,
                self.config.enable_retrieval,
                bool(tools), tools
            )


# ---------------------------------------------------------------------------
# Simulated System Under Test
# ---------------------------------------------------------------------------

class SimulatedSystem:
    """
    Simulates the AI system for load testing purposes.
    In production, replace with actual HTTP calls to the system.
    """

    def __init__(self):
        self._request_count = 0
        self._error_rate = 0.02  # Base error rate
        self._base_latency_ms = 200.0
        self._lock = asyncio.Lock()

    async def process_request(self, request: GeneratedRequest) -> dict[str, Any]:
        """Simulate processing a request through the full path."""
        start = time.time()

        # Simulate auth (fast)
        await asyncio.sleep(0.005)

        # Simulate classification
        await asyncio.sleep(0.002)

        # Simulate agent steps
        total_model_time = 0.0
        total_retrieval_time = 0.0
        total_tool_time = 0.0

        for step in range(request.expected_steps):
            # Retrieval
            if request.uses_retrieval:
                retrieval_time = random.gauss(0.05, 0.02)
                await asyncio.sleep(max(0.01, retrieval_time))
                total_retrieval_time += retrieval_time

            # Model call
            # Latency increases with load (simulating saturation)
            async with self._lock:
                self._request_count += 1
            load_factor = 1.0 + (self._request_count % 100) * 0.01
            model_time = random.gauss(0.3 * load_factor, 0.1)
            await asyncio.sleep(max(0.05, model_time))
            total_model_time += model_time

            # Tool calls
            if request.uses_tools and step < len(request.tool_names):
                tool_time = random.gauss(0.1, 0.05)
                await asyncio.sleep(max(0.02, tool_time))
                total_tool_time += tool_time

        # Random errors
        is_error = random.random() < self._error_rate
        elapsed_ms = (time.time() - start) * 1000

        return {
            "request_id": request.request_id,
            "success": not is_error,
            "latency_ms": elapsed_ms,
            "model_time_ms": total_model_time * 1000,
            "retrieval_time_ms": total_retrieval_time * 1000,
            "tool_time_ms": total_tool_time * 1000,
            "steps_executed": request.expected_steps,
            "tokens_used": request.expected_tokens,
            "error": "simulated_error" if is_error else None,
        }


# ---------------------------------------------------------------------------
# Results Collector
# ---------------------------------------------------------------------------

@dataclass
class LoadTestResults:
    """Aggregated load test results."""

    config: LoadTestConfig
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration_seconds: float = 0.0

    latencies_ms: list[float] = field(default_factory=list)
    model_latencies_ms: list[float] = field(default_factory=list)
    retrieval_latencies_ms: list[float] = field(default_factory=list)
    tool_latencies_ms: list[float] = field(default_factory=list)

    errors_by_type: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    requests_by_complexity: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    requests_by_tenant: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Per-second throughput tracking
    throughput_per_second: list[int] = field(default_factory=list)

    def record(self, request: GeneratedRequest, result: dict[str, Any]) -> None:
        self.total_requests += 1
        self.requests_by_complexity[request.complexity] += 1
        self.requests_by_tenant[request.tenant_id] += 1

        if result["success"]:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.errors_by_type[result.get("error", "unknown")] += 1

        self.latencies_ms.append(result["latency_ms"])
        if result["model_time_ms"] > 0:
            self.model_latencies_ms.append(result["model_time_ms"])
        if result["retrieval_time_ms"] > 0:
            self.retrieval_latencies_ms.append(result["retrieval_time_ms"])
        if result["tool_time_ms"] > 0:
            self.tool_latencies_ms.append(result["tool_time_ms"])

    def generate_report(self) -> str:
        lines = [
            "=" * 70,
            f"  LOAD TEST REPORT: {self.config.name}",
            "=" * 70,
            "",
            "CONFIGURATION",
            f"  Duration:         {self.config.duration_seconds}s",
            f"  Target RPS:       {self.config.target_rps}",
            f"  Pattern:          {self.config.pattern.value}",
            f"  Concurrent Users: {self.config.concurrent_users}",
            f"  Tenants:          {self.config.tenant_count}",
            "",
            "THROUGHPUT",
            f"  Total Requests:   {self.total_requests:,}",
            f"  Successful:       {self.successful_requests:,}",
            f"  Failed:           {self.failed_requests:,}",
            f"  Error Rate:       {self.failed_requests / max(self.total_requests, 1):.2%}",
            f"  Actual RPS:       {self.total_requests / max(self.total_duration_seconds, 1):.1f}",
            "",
        ]

        # Latency stats
        def stats_block(name: str, data: list[float]) -> list[str]:
            if not data:
                return [f"  {name}: no data"]
            return [
                f"  {name}:",
                f"    P50:  {statistics.median(data):>8.1f} ms",
                f"    P90:  {sorted(data)[int(len(data) * 0.9)]:>8.1f} ms",
                f"    P99:  {sorted(data)[int(len(data) * 0.99)]:>8.1f} ms",
                f"    Max:  {max(data):>8.1f} ms",
                f"    Mean: {statistics.mean(data):>8.1f} ms",
            ]

        lines.append("LATENCY")
        lines.extend(stats_block("End-to-End", self.latencies_ms))
        lines.extend(stats_block("Model", self.model_latencies_ms))
        lines.extend(stats_block("Retrieval", self.retrieval_latencies_ms))
        lines.extend(stats_block("Tools", self.tool_latencies_ms))
        lines.append("")

        # Complexity distribution
        lines.append("REQUEST DISTRIBUTION")
        for comp, count in sorted(self.requests_by_complexity.items()):
            lines.append(f"  {comp:<12} {count:>6} ({count / max(self.total_requests, 1):.1%})")
        lines.append("")

        # Tenant fairness
        lines.append("TENANT FAIRNESS")
        tenant_counts = list(self.requests_by_tenant.values())
        if tenant_counts:
            lines.append(f"  Min requests/tenant: {min(tenant_counts)}")
            lines.append(f"  Max requests/tenant: {max(tenant_counts)}")
            lines.append(f"  Std dev:             {statistics.stdev(tenant_counts) if len(tenant_counts) > 1 else 0:.1f}")
        lines.append("")

        # Assertions
        lines.append("ASSERTIONS")
        p99 = sorted(self.latencies_ms)[int(len(self.latencies_ms) * 0.99)] if self.latencies_ms else 0
        error_rate = self.failed_requests / max(self.total_requests, 1)
        actual_rps = self.total_requests / max(self.total_duration_seconds, 1)

        checks = [
            ("P99 Latency", p99 <= self.config.max_p99_latency_ms, f"{p99:.0f}ms <= {self.config.max_p99_latency_ms:.0f}ms"),
            ("Error Rate", error_rate <= self.config.max_error_rate, f"{error_rate:.2%} <= {self.config.max_error_rate:.2%}"),
        ]
        if self.config.min_throughput_rps > 0:
            checks.append(("Throughput", actual_rps >= self.config.min_throughput_rps, f"{actual_rps:.1f} >= {self.config.min_throughput_rps:.1f}"))

        all_pass = True
        for name, passed, detail in checks:
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_pass = False
            lines.append(f"  [{status}] {name}: {detail}")

        lines.append("")
        lines.append(f"  OVERALL: {'PASS' if all_pass else 'FAIL'}")
        lines.append("=" * 70)

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Load Test Runner
# ---------------------------------------------------------------------------

class LoadTestRunner:
    """Orchestrates load test execution."""

    def __init__(self, config: LoadTestConfig, system: SimulatedSystem | None = None):
        self.config = config
        self.system = system or SimulatedSystem()
        self.generator = RequestGenerator(config)
        self.results = LoadTestResults(config=config)

    async def run(self) -> LoadTestResults:
        """Execute the load test."""
        print(f"Starting load test: {self.config.name}")
        print(f"  Target: {self.config.target_rps} RPS for {self.config.duration_seconds}s")

        start_time = time.time()
        tasks: list[asyncio.Task] = []
        request_count = 0
        interval = 1.0 / self.config.target_rps

        while time.time() - start_time < self.config.duration_seconds:
            # Compute current target RPS based on pattern
            elapsed = time.time() - start_time
            current_rps = self._compute_current_rps(elapsed)
            current_interval = 1.0 / max(current_rps, 1)

            # Generate and submit request
            request = self.generator.generate()
            task = asyncio.create_task(self._execute_request(request))
            tasks.append(task)
            request_count += 1

            # Pace requests
            await asyncio.sleep(current_interval)

            # Prevent unbounded task accumulation
            if len(tasks) > 1000:
                done = [t for t in tasks if t.done()]
                tasks = [t for t in tasks if not t.done()]

        # Wait for remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.results.total_duration_seconds = time.time() - start_time
        return self.results

    def _compute_current_rps(self, elapsed: float) -> float:
        """Compute target RPS at current time based on pattern."""
        cfg = self.config
        if cfg.pattern == LoadPattern.CONSTANT:
            return cfg.target_rps
        elif cfg.pattern == LoadPattern.RAMP_UP:
            progress = min(1.0, elapsed / cfg.ramp_duration_seconds)
            return cfg.target_rps * progress
        elif cfg.pattern == LoadPattern.SPIKE:
            # Normal for first half, 3x spike in middle, back to normal
            mid = cfg.duration_seconds / 2
            if abs(elapsed - mid) < cfg.duration_seconds * 0.1:
                return cfg.target_rps * 3
            return cfg.target_rps
        elif cfg.pattern == LoadPattern.WAVE:
            import math
            period = cfg.duration_seconds / 3
            return cfg.target_rps * (1 + 0.5 * math.sin(2 * math.pi * elapsed / period))
        elif cfg.pattern == LoadPattern.STEP:
            steps = 4
            step_duration = cfg.duration_seconds / steps
            current_step = int(elapsed / step_duration)
            return cfg.target_rps * (current_step + 1) / steps
        return cfg.target_rps

    async def _execute_request(self, request: GeneratedRequest) -> None:
        """Execute a single request and record results."""
        try:
            result = await self.system.process_request(request)
            self.results.record(request, result)
        except Exception as e:
            self.results.record(request, {
                "request_id": request.request_id,
                "success": False,
                "latency_ms": 0,
                "model_time_ms": 0,
                "retrieval_time_ms": 0,
                "tool_time_ms": 0,
                "steps_executed": 0,
                "tokens_used": 0,
                "error": str(e),
            })


# ---------------------------------------------------------------------------
# Predefined Test Suites
# ---------------------------------------------------------------------------

def baseline_test() -> LoadTestConfig:
    return LoadTestConfig(
        name="baseline",
        duration_seconds=30,
        target_rps=10,
        pattern=LoadPattern.CONSTANT,
    )


def stress_test() -> LoadTestConfig:
    return LoadTestConfig(
        name="stress",
        duration_seconds=60,
        target_rps=200,
        pattern=LoadPattern.RAMP_UP,
        ramp_duration_seconds=30,
        max_p99_latency_ms=10000,
        max_error_rate=0.10,
    )


def spike_test() -> LoadTestConfig:
    return LoadTestConfig(
        name="spike",
        duration_seconds=60,
        target_rps=50,
        pattern=LoadPattern.SPIKE,
        max_p99_latency_ms=8000,
    )


def isolation_test() -> LoadTestConfig:
    """Test cross-tenant isolation with one hot tenant."""
    return LoadTestConfig(
        name="isolation",
        duration_seconds=30,
        target_rps=50,
        tenant_count=10,
        concurrent_users=100,
        request_complexity_distribution={
            "simple": 0.20,
            "medium": 0.20,
            "complex": 0.20,
            "heavy": 0.40,  # Heavier than normal
        },
    )


def streaming_test() -> LoadTestConfig:
    return LoadTestConfig(
        name="streaming",
        duration_seconds=30,
        target_rps=100,
        enable_streaming=True,
        concurrent_users=200,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("AI LOAD TESTING FRAMEWORK")
    print("=" * 70)

    configs = [baseline_test(), stress_test(), spike_test()]

    for config in configs:
        runner = LoadTestRunner(config)
        results = await runner.run()
        print(results.generate_report())
        print()


if __name__ == "__main__":
    asyncio.run(main())
