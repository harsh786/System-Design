"""
IMPLEMENTATION: Agent Improvement System
=========================================
Production system for continuously improving agents through:
- Trace collection and storage
- Failure clustering by error type, tool, intent
- Root cause labeling
- A/B variant comparison
- Prompt and tool schema variant testing
- Golden eval set comparison
- Statistical significance testing
- Canary release decision logic
"""

from __future__ import annotations

import json
import math
import random
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ============================================================
# TRACE TYPES
# ============================================================

class TraceOutcome(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    ERROR = "error"


class FailureCategory(Enum):
    WRONG_TOOL = "wrong_tool"
    WRONG_TOOL_ARGS = "wrong_tool_args"
    HALLUCINATION = "hallucination"
    INFINITE_LOOP = "infinite_loop"
    FORMAT_ERROR = "format_error"
    MISSING_CONTEXT = "missing_context"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    GUARDRAIL_BLOCK = "guardrail_block"
    MODEL_REFUSAL = "model_refusal"
    AMBIGUOUS_INPUT = "ambiguous_input"
    UNKNOWN = "unknown"


@dataclass
class TraceStep:
    step_number: int
    reasoning: str
    action_type: str
    tool_name: str | None
    tool_args: dict[str, Any] | None
    observation: str | None
    latency_ms: float
    tokens_used: int
    error: str | None = None


@dataclass
class AgentTrace:
    """Complete record of a single agent execution."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    # Input
    user_input: str = ""
    detected_intent: str = ""
    # Execution
    steps: list[TraceStep] = field(default_factory=list)
    model_id: str = ""
    prompt_version: str = ""
    tool_schema_version: str = ""
    # Outcome
    outcome: TraceOutcome = TraceOutcome.SUCCESS
    final_output: str = ""
    # Metrics
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    num_steps: int = 0
    # Labels (added post-hoc)
    failure_category: FailureCategory | None = None
    root_cause: str = ""
    user_rating: int | None = None  # 1-5
    human_label: str = ""
    # Metadata
    variant_id: str = "control"  # For A/B testing
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# TRACE STORE
# ============================================================

class TraceStore:
    """In-memory trace store. In production: database/data warehouse."""

    def __init__(self):
        self.traces: list[AgentTrace] = []
        self._index_by_outcome: dict[TraceOutcome, list[int]] = defaultdict(list)
        self._index_by_intent: dict[str, list[int]] = defaultdict(list)
        self._index_by_variant: dict[str, list[int]] = defaultdict(list)

    def add(self, trace: AgentTrace) -> None:
        idx = len(self.traces)
        self.traces.append(trace)
        self._index_by_outcome[trace.outcome].append(idx)
        self._index_by_intent[trace.detected_intent].append(idx)
        self._index_by_variant[trace.variant_id].append(idx)

    def get_failures(self) -> list[AgentTrace]:
        return [self.traces[i] for i in self._index_by_outcome.get(TraceOutcome.FAILURE, [])]

    def get_by_variant(self, variant_id: str) -> list[AgentTrace]:
        return [self.traces[i] for i in self._index_by_variant.get(variant_id, [])]

    def get_by_intent(self, intent: str) -> list[AgentTrace]:
        return [self.traces[i] for i in self._index_by_intent.get(intent, [])]

    def get_recent(self, n: int = 100) -> list[AgentTrace]:
        return self.traces[-n:]

    @property
    def total_count(self) -> int:
        return len(self.traces)


# ============================================================
# FAILURE CLUSTERING
# ============================================================

@dataclass
class FailureCluster:
    """A group of similar failures."""
    cluster_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    category: FailureCategory = FailureCategory.UNKNOWN
    description: str = ""
    traces: list[str] = field(default_factory=list)  # trace IDs
    count: int = 0
    # Breakdown
    by_tool: dict[str, int] = field(default_factory=dict)
    by_intent: dict[str, int] = field(default_factory=dict)
    by_step: dict[int, int] = field(default_factory=dict)  # step_number -> count
    # Impact
    avg_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    first_seen: float = 0.0
    last_seen: float = 0.0


class FailureClusterer:
    """Clusters failures by error type, tool, and intent."""

    def cluster(self, traces: list[AgentTrace]) -> list[FailureCluster]:
        """Cluster failed traces into meaningful groups."""
        # Group by failure category
        by_category: dict[FailureCategory, list[AgentTrace]] = defaultdict(list)
        for trace in traces:
            category = trace.failure_category or self._auto_categorize(trace)
            by_category[category].append(trace)

        clusters = []
        for category, category_traces in by_category.items():
            # Sub-cluster by tool (within category)
            by_tool: dict[str, list[AgentTrace]] = defaultdict(list)
            for t in category_traces:
                failing_tool = self._get_failing_tool(t)
                by_tool[failing_tool].append(t)

            for tool_name, tool_traces in by_tool.items():
                cluster = FailureCluster(
                    category=category,
                    description=f"{category.value} in tool '{tool_name}'",
                    traces=[t.trace_id for t in tool_traces],
                    count=len(tool_traces),
                    first_seen=min(t.timestamp for t in tool_traces),
                    last_seen=max(t.timestamp for t in tool_traces),
                    avg_cost_usd=sum(t.total_cost_usd for t in tool_traces) / len(tool_traces),
                    avg_latency_ms=sum(t.total_latency_ms for t in tool_traces) / len(tool_traces),
                )

                # Breakdown by intent
                for t in tool_traces:
                    cluster.by_intent[t.detected_intent] = cluster.by_intent.get(t.detected_intent, 0) + 1
                    cluster.by_tool[tool_name] = cluster.by_tool.get(tool_name, 0) + 1

                clusters.append(cluster)

        # Sort by count (most impactful first)
        clusters.sort(key=lambda c: c.count, reverse=True)
        return clusters

    def _auto_categorize(self, trace: AgentTrace) -> FailureCategory:
        """Heuristic categorization when no human label exists."""
        if trace.outcome == TraceOutcome.TIMEOUT:
            return FailureCategory.TIMEOUT
        if trace.num_steps >= 10:
            return FailureCategory.INFINITE_LOOP

        # Check last step for error patterns
        if trace.steps:
            last_step = trace.steps[-1]
            if last_step.error:
                if "not found" in last_step.error.lower():
                    return FailureCategory.WRONG_TOOL
                if "invalid" in last_step.error.lower() or "schema" in last_step.error.lower():
                    return FailureCategory.WRONG_TOOL_ARGS
                if "timeout" in last_step.error.lower():
                    return FailureCategory.TOOL_ERROR

        return FailureCategory.UNKNOWN

    def _get_failing_tool(self, trace: AgentTrace) -> str:
        """Identify which tool caused the failure."""
        for step in reversed(trace.steps):
            if step.error and step.tool_name:
                return step.tool_name
        # If no tool error, return the last tool used
        for step in reversed(trace.steps):
            if step.tool_name:
                return step.tool_name
        return "__no_tool__"


# ============================================================
# ROOT CAUSE LABELER
# ============================================================

@dataclass
class RootCauseLabel:
    cluster_id: str
    category: FailureCategory
    root_cause: str
    recommended_lever: str  # Which improvement lever to pull
    confidence: float  # 0-1
    evidence: list[str] = field(default_factory=list)


class RootCauseLabeler:
    """Maps failure clusters to root causes and recommended improvement levers."""

    # Mapping: failure category -> (root cause template, recommended lever)
    CAUSE_MAP: dict[FailureCategory, tuple[str, str]] = {
        FailureCategory.WRONG_TOOL: ("Agent selects incorrect tool for intent", "tool_tuning"),
        FailureCategory.WRONG_TOOL_ARGS: ("Agent provides invalid arguments to tool", "tool_tuning"),
        FailureCategory.HALLUCINATION: ("Agent generates unfounded claims", "prompt_tuning"),
        FailureCategory.INFINITE_LOOP: ("Agent fails to terminate reasoning loop", "graph_tuning"),
        FailureCategory.FORMAT_ERROR: ("Agent output doesn't match expected format", "prompt_tuning"),
        FailureCategory.MISSING_CONTEXT: ("Agent lacks necessary information", "retriever_tuning"),
        FailureCategory.TOOL_ERROR: ("External tool/API failure", "graph_tuning"),
        FailureCategory.TIMEOUT: ("Execution exceeds time budget", "model_routing"),
        FailureCategory.GUARDRAIL_BLOCK: ("Valid action blocked by overly strict guardrail", "policy_tuning"),
        FailureCategory.MODEL_REFUSAL: ("Model refuses valid request", "prompt_tuning"),
        FailureCategory.AMBIGUOUS_INPUT: ("User input too ambiguous to process", "prompt_tuning"),
    }

    def label(self, cluster: FailureCluster) -> RootCauseLabel:
        """Generate root cause label for a cluster."""
        cause_template, lever = self.CAUSE_MAP.get(
            cluster.category,
            ("Unknown failure mode", "prompt_tuning")
        )

        # Build evidence from cluster data
        evidence = []
        if cluster.by_tool:
            top_tool = max(cluster.by_tool, key=cluster.by_tool.get)
            evidence.append(f"Most common failing tool: {top_tool} ({cluster.by_tool[top_tool]} occurrences)")
        if cluster.by_intent:
            top_intent = max(cluster.by_intent, key=cluster.by_intent.get)
            evidence.append(f"Most common intent: {top_intent} ({cluster.by_intent[top_intent]} occurrences)")
        evidence.append(f"Total occurrences: {cluster.count}")
        evidence.append(f"Avg cost per failure: ${cluster.avg_cost_usd:.4f}")

        # Confidence based on cluster size and consistency
        confidence = min(0.95, 0.5 + (cluster.count / 100))

        return RootCauseLabel(
            cluster_id=cluster.cluster_id,
            category=cluster.category,
            root_cause=cause_template,
            recommended_lever=lever,
            confidence=confidence,
            evidence=evidence,
        )


# ============================================================
# EVAL SYSTEM
# ============================================================

@dataclass
class EvalCase:
    """A single eval test case."""
    case_id: str
    input_text: str
    expected_output: str | None = None
    expected_tool_calls: list[str] | None = None
    expected_intent: str | None = None
    tags: list[str] = field(default_factory=list)
    difficulty: str = "medium"  # easy, medium, hard


@dataclass
class EvalResult:
    case_id: str
    variant_id: str
    passed: bool
    score: float  # 0-1
    latency_ms: float
    tokens_used: int
    cost_usd: float
    details: dict[str, Any] = field(default_factory=dict)


class GoldenEvalSet:
    """Held-out test set for measuring agent quality."""

    def __init__(self, cases: list[EvalCase] | None = None):
        self.cases = cases or []
        self._by_tag: dict[str, list[EvalCase]] = defaultdict(list)
        for case in self.cases:
            for tag in case.tags:
                self._by_tag[tag].append(case)

    def add_case(self, case: EvalCase) -> None:
        self.cases.append(case)
        for tag in case.tags:
            self._by_tag[tag].append(case)

    def get_by_tag(self, tag: str) -> list[EvalCase]:
        return self._by_tag.get(tag, [])

    def run_eval(
        self,
        agent_fn: Callable[[str], tuple[str, float, int, float]],
        variant_id: str,
        scorer: Callable[[EvalCase, str], float] | None = None,
    ) -> list[EvalResult]:
        """
        Run all eval cases against an agent function.
        agent_fn: input -> (output, latency_ms, tokens, cost_usd)
        scorer: (case, output) -> score (0-1)
        """
        results = []
        for case in self.cases:
            try:
                output, latency, tokens, cost = agent_fn(case.input_text)
                if scorer:
                    score = scorer(case, output)
                elif case.expected_output:
                    score = 1.0 if output.strip() == case.expected_output.strip() else 0.0
                else:
                    score = 1.0  # No expected output = pass if no error

                results.append(EvalResult(
                    case_id=case.case_id,
                    variant_id=variant_id,
                    passed=score >= 0.5,
                    score=score,
                    latency_ms=latency,
                    tokens_used=tokens,
                    cost_usd=cost,
                ))
            except Exception as e:
                results.append(EvalResult(
                    case_id=case.case_id,
                    variant_id=variant_id,
                    passed=False,
                    score=0.0,
                    latency_ms=0,
                    tokens_used=0,
                    cost_usd=0,
                    details={"error": str(e)},
                ))

        return results


# ============================================================
# STATISTICAL SIGNIFICANCE
# ============================================================

class StatisticalTest:
    """Statistical tests for comparing agent variants."""

    @staticmethod
    def proportion_z_test(
        successes_a: int, total_a: int,
        successes_b: int, total_b: int,
        alpha: float = 0.05,
    ) -> dict[str, Any]:
        """
        Two-proportion z-test.
        Tests if variant B is significantly different from variant A.
        """
        if total_a == 0 or total_b == 0:
            return {"significant": False, "reason": "Insufficient data"}

        p_a = successes_a / total_a
        p_b = successes_b / total_b
        p_pool = (successes_a + successes_b) / (total_a + total_b)

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1/total_a + 1/total_b))
        if se == 0:
            return {"significant": False, "reason": "Zero standard error"}

        # Z-score
        z = (p_b - p_a) / se

        # Two-tailed p-value (approximation)
        p_value = 2 * (1 - StatisticalTest._normal_cdf(abs(z)))

        # Critical z for alpha
        z_critical = StatisticalTest._z_critical(alpha)

        return {
            "significant": abs(z) > z_critical,
            "z_score": z,
            "p_value": p_value,
            "p_a": p_a,
            "p_b": p_b,
            "lift": (p_b - p_a) / p_a if p_a > 0 else float("inf"),
            "confidence_level": 1 - alpha,
            "sample_size_a": total_a,
            "sample_size_b": total_b,
        }

    @staticmethod
    def required_sample_size(
        baseline_rate: float,
        minimum_detectable_effect: float,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> int:
        """Calculate required sample size per variant for desired power."""
        z_alpha = StatisticalTest._z_critical(alpha)
        z_beta = StatisticalTest._z_critical(1 - power)  # Approximation

        p1 = baseline_rate
        p2 = baseline_rate + minimum_detectable_effect
        p_avg = (p1 + p2) / 2

        n = ((z_alpha * math.sqrt(2 * p_avg * (1 - p_avg)) +
              z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / \
             (minimum_detectable_effect ** 2)

        return math.ceil(n)

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximation of standard normal CDF."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _z_critical(alpha: float) -> float:
        """Approximate z-critical value for given alpha (two-tailed)."""
        # Common values
        table = {0.01: 2.576, 0.05: 1.96, 0.10: 1.645, 0.20: 1.282}
        return table.get(alpha, 1.96)


# ============================================================
# A/B VARIANT TESTING
# ============================================================

@dataclass
class AgentVariant:
    """A specific configuration of the agent to test."""
    variant_id: str
    description: str
    prompt_version: str
    tool_schema_version: str
    model_id: str
    traffic_percentage: float = 0.0  # 0-100
    metadata: dict[str, Any] = field(default_factory=dict)


class VariantRouter:
    """Routes traffic to agent variants for A/B testing."""

    def __init__(self, variants: list[AgentVariant]):
        self.variants = {v.variant_id: v for v in variants}
        self._validate_traffic()

    def _validate_traffic(self) -> None:
        total = sum(v.traffic_percentage for v in self.variants.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Traffic percentages must sum to 100, got {total}")

    def route(self, request_id: str | None = None) -> AgentVariant:
        """Deterministically route a request to a variant."""
        # Use request_id for deterministic assignment (same user always gets same variant)
        if request_id:
            hash_val = hash(request_id) % 100
        else:
            hash_val = random.randint(0, 99)

        cumulative = 0.0
        for variant in self.variants.values():
            cumulative += variant.traffic_percentage
            if hash_val < cumulative:
                return variant

        # Fallback to last variant
        return list(self.variants.values())[-1]

    def update_traffic(self, variant_id: str, new_percentage: float) -> None:
        """Update traffic allocation for a variant."""
        if variant_id not in self.variants:
            raise ValueError(f"Variant '{variant_id}' not found")
        self.variants[variant_id].traffic_percentage = new_percentage
        self._validate_traffic()


# ============================================================
# CANARY RELEASE DECISION
# ============================================================

class CanaryDecision(Enum):
    PROMOTE = "promote"       # Roll out to 100%
    CONTINUE = "continue"     # Keep testing, need more data
    ROLLBACK = "rollback"     # Revert to control


@dataclass
class CanaryMetrics:
    variant_id: str
    success_rate: float
    avg_latency_ms: float
    avg_cost_usd: float
    total_requests: int
    error_rate: float
    p95_latency_ms: float


class CanaryDecisionEngine:
    """Decides whether to promote, continue, or rollback a canary deployment."""

    def __init__(
        self,
        min_sample_size: int = 100,
        max_latency_regression_pct: float = 20.0,
        max_cost_regression_pct: float = 30.0,
        min_success_rate_improvement: float = 0.0,  # Must not be worse
        significance_alpha: float = 0.05,
    ):
        self.min_sample_size = min_sample_size
        self.max_latency_regression_pct = max_latency_regression_pct
        self.max_cost_regression_pct = max_cost_regression_pct
        self.min_success_rate_improvement = min_success_rate_improvement
        self.significance_alpha = significance_alpha

    def decide(self, control: CanaryMetrics, canary: CanaryMetrics) -> tuple[CanaryDecision, dict[str, Any]]:
        """Make promotion decision based on metrics comparison."""
        reasons: dict[str, Any] = {}

        # 1. Check sample size
        if canary.total_requests < self.min_sample_size:
            reasons["insufficient_data"] = f"Need {self.min_sample_size} requests, have {canary.total_requests}"
            return CanaryDecision.CONTINUE, reasons

        # 2. Check for hard failures (immediate rollback)
        if canary.error_rate > 0.10:  # >10% error rate
            reasons["high_error_rate"] = f"Canary error rate {canary.error_rate:.1%} exceeds 10% threshold"
            return CanaryDecision.ROLLBACK, reasons

        # 3. Check latency regression
        latency_change_pct = ((canary.avg_latency_ms - control.avg_latency_ms) / control.avg_latency_ms) * 100
        if latency_change_pct > self.max_latency_regression_pct:
            reasons["latency_regression"] = f"Latency increased by {latency_change_pct:.1f}% (max: {self.max_latency_regression_pct}%)"
            return CanaryDecision.ROLLBACK, reasons

        # 4. Check cost regression
        cost_change_pct = ((canary.avg_cost_usd - control.avg_cost_usd) / control.avg_cost_usd) * 100 if control.avg_cost_usd > 0 else 0
        if cost_change_pct > self.max_cost_regression_pct:
            reasons["cost_regression"] = f"Cost increased by {cost_change_pct:.1f}% (max: {self.max_cost_regression_pct}%)"
            return CanaryDecision.ROLLBACK, reasons

        # 5. Statistical significance of success rate
        control_successes = int(control.success_rate * control.total_requests)
        canary_successes = int(canary.success_rate * canary.total_requests)

        stat_result = StatisticalTest.proportion_z_test(
            control_successes, control.total_requests,
            canary_successes, canary.total_requests,
            alpha=self.significance_alpha,
        )
        reasons["stat_test"] = stat_result

        # 6. Make decision
        if stat_result["significant"] and stat_result["lift"] > self.min_success_rate_improvement:
            if stat_result["p_b"] >= stat_result["p_a"]:
                reasons["decision_reason"] = "Statistically significant improvement with acceptable latency/cost"
                return CanaryDecision.PROMOTE, reasons
            else:
                reasons["decision_reason"] = "Statistically significant REGRESSION in success rate"
                return CanaryDecision.ROLLBACK, reasons

        if not stat_result["significant"]:
            # Check if we've waited long enough
            if canary.total_requests > self.min_sample_size * 5:
                # Enough data, no significant difference — keep control
                reasons["decision_reason"] = "No significant difference after sufficient data"
                return CanaryDecision.ROLLBACK, reasons
            reasons["decision_reason"] = "Not yet statistically significant, need more data"
            return CanaryDecision.CONTINUE, reasons

        return CanaryDecision.CONTINUE, reasons


# ============================================================
# IMPROVEMENT PIPELINE (Orchestrator)
# ============================================================

class AgentImprovementPipeline:
    """
    End-to-end pipeline:
    Traces → Clustering → Root Cause → Lever Selection → Eval → Canary → Promote
    """

    def __init__(
        self,
        trace_store: TraceStore,
        eval_set: GoldenEvalSet,
        canary_engine: CanaryDecisionEngine | None = None,
    ):
        self.trace_store = trace_store
        self.eval_set = eval_set
        self.clusterer = FailureClusterer()
        self.labeler = RootCauseLabeler()
        self.canary_engine = canary_engine or CanaryDecisionEngine()

    def analyze_failures(self) -> list[tuple[FailureCluster, RootCauseLabel]]:
        """Step 1-3: Collect failures, cluster, and label root causes."""
        failures = self.trace_store.get_failures()
        if not failures:
            return []

        clusters = self.clusterer.cluster(failures)
        results = []
        for cluster in clusters:
            label = self.labeler.label(cluster)
            results.append((cluster, label))

        return results

    def compare_variants(self, variant_a: str, variant_b: str) -> dict[str, Any]:
        """Step 4: Compare two variants on production traces."""
        traces_a = self.trace_store.get_by_variant(variant_a)
        traces_b = self.trace_store.get_by_variant(variant_b)

        if not traces_a or not traces_b:
            return {"error": "Insufficient traces for comparison"}

        # Calculate metrics
        def calc_metrics(traces: list[AgentTrace]) -> dict[str, float]:
            successes = sum(1 for t in traces if t.outcome == TraceOutcome.SUCCESS)
            return {
                "success_rate": successes / len(traces),
                "avg_latency_ms": sum(t.total_latency_ms for t in traces) / len(traces),
                "avg_cost_usd": sum(t.total_cost_usd for t in traces) / len(traces),
                "avg_steps": sum(t.num_steps for t in traces) / len(traces),
                "total_traces": len(traces),
            }

        metrics_a = calc_metrics(traces_a)
        metrics_b = calc_metrics(traces_b)

        # Statistical test
        stat_result = StatisticalTest.proportion_z_test(
            int(metrics_a["success_rate"] * len(traces_a)), len(traces_a),
            int(metrics_b["success_rate"] * len(traces_b)), len(traces_b),
        )

        return {
            "variant_a": {"id": variant_a, **metrics_a},
            "variant_b": {"id": variant_b, **metrics_b},
            "statistical_test": stat_result,
            "recommendation": "promote_b" if stat_result["significant"] and stat_result["lift"] > 0 else "keep_a",
        }

    def run_eval_comparison(
        self,
        agent_fn_a: Callable[[str], tuple[str, float, int, float]],
        agent_fn_b: Callable[[str], tuple[str, float, int, float]],
        variant_a_id: str = "control",
        variant_b_id: str = "candidate",
    ) -> dict[str, Any]:
        """Step 5-6: Run golden eval for both variants and compare."""
        results_a = self.eval_set.run_eval(agent_fn_a, variant_a_id)
        results_b = self.eval_set.run_eval(agent_fn_b, variant_b_id)

        # Aggregate
        def aggregate(results: list[EvalResult]) -> dict[str, float]:
            if not results:
                return {}
            passed = sum(1 for r in results if r.passed)
            return {
                "pass_rate": passed / len(results),
                "avg_score": sum(r.score for r in results) / len(results),
                "avg_latency_ms": sum(r.latency_ms for r in results) / len(results),
                "avg_cost_usd": sum(r.cost_usd for r in results) / len(results),
                "total_cases": len(results),
            }

        agg_a = aggregate(results_a)
        agg_b = aggregate(results_b)

        # Per-case comparison (regression detection)
        regressions = []
        improvements = []
        for ra, rb in zip(results_a, results_b):
            if ra.passed and not rb.passed:
                regressions.append(ra.case_id)
            elif not ra.passed and rb.passed:
                improvements.append(rb.case_id)

        return {
            "variant_a": {"id": variant_a_id, **agg_a},
            "variant_b": {"id": variant_b_id, **agg_b},
            "regressions": regressions,
            "improvements": improvements,
            "net_change": len(improvements) - len(regressions),
            "safe_to_deploy": len(regressions) == 0 and agg_b.get("pass_rate", 0) >= agg_a.get("pass_rate", 0),
        }

    def generate_improvement_report(self) -> str:
        """Generate a human-readable improvement report."""
        analysis = self.analyze_failures()

        lines = [
            "=" * 60,
            "AGENT IMPROVEMENT REPORT",
            "=" * 60,
            f"Total traces: {self.trace_store.total_count}",
            f"Failed traces: {len(self.trace_store.get_failures())}",
            f"Failure rate: {len(self.trace_store.get_failures()) / max(self.trace_store.total_count, 1):.1%}",
            "",
            "TOP FAILURE CLUSTERS:",
            "-" * 40,
        ]

        for i, (cluster, label) in enumerate(analysis[:10], 1):
            lines.append(f"\n{i}. [{cluster.category.value}] {cluster.description}")
            lines.append(f"   Count: {cluster.count} | Avg Cost: ${cluster.avg_cost_usd:.4f}")
            lines.append(f"   Root Cause: {label.root_cause}")
            lines.append(f"   Recommended Lever: {label.recommended_lever}")
            lines.append(f"   Confidence: {label.confidence:.0%}")
            for ev in label.evidence:
                lines.append(f"   • {ev}")

        lines.append(f"\n{'='*60}")
        return "\n".join(lines)


# ============================================================
# EXAMPLE USAGE
# ============================================================

def main():
    """Demonstrate the agent improvement pipeline."""

    # 1. Create trace store with synthetic data
    store = TraceStore()

    # Generate synthetic traces
    intents = ["order_status", "refund", "technical_support", "billing"]
    tools = ["lookup_order", "process_refund", "search_kb", "get_invoice"]

    for i in range(500):
        outcome = random.choices(
            [TraceOutcome.SUCCESS, TraceOutcome.FAILURE, TraceOutcome.TIMEOUT],
            weights=[0.75, 0.20, 0.05],
        )[0]

        intent = random.choice(intents)
        tool = random.choice(tools)
        variant = random.choice(["control", "candidate_v2"])

        trace = AgentTrace(
            user_input=f"Sample input {i} for {intent}",
            detected_intent=intent,
            outcome=outcome,
            model_id="gpt-4o-mini",
            prompt_version="v1.2",
            tool_schema_version="v1.0",
            variant_id=variant,
            total_tokens=random.randint(500, 5000),
            total_latency_ms=random.uniform(200, 5000),
            total_cost_usd=random.uniform(0.001, 0.05),
            num_steps=random.randint(1, 8),
            steps=[
                TraceStep(
                    step_number=1,
                    reasoning="thinking...",
                    action_type="tool_call",
                    tool_name=tool,
                    tool_args={"query": "test"},
                    observation="result" if outcome == TraceOutcome.SUCCESS else None,
                    latency_ms=random.uniform(100, 2000),
                    tokens_used=random.randint(100, 1000),
                    error="Tool not found" if outcome == TraceOutcome.FAILURE and random.random() > 0.5 else None,
                )
            ],
            failure_category=(
                random.choice(list(FailureCategory))
                if outcome == TraceOutcome.FAILURE else None
            ),
        )
        store.add(trace)

    # 2. Run improvement pipeline
    eval_set = GoldenEvalSet(cases=[
        EvalCase(case_id="eval_1", input_text="What is my order status?", expected_intent="order_status", tags=["orders"]),
        EvalCase(case_id="eval_2", input_text="I want a refund", expected_intent="refund", tags=["refunds"]),
        EvalCase(case_id="eval_3", input_text="My app is crashing", expected_intent="technical_support", tags=["support"]),
    ])

    pipeline = AgentImprovementPipeline(
        trace_store=store,
        eval_set=eval_set,
    )

    # 3. Generate report
    report = pipeline.generate_improvement_report()
    print(report)

    # 4. Compare variants
    comparison = pipeline.compare_variants("control", "candidate_v2")
    print(f"\nVARIANT COMPARISON:")
    print(json.dumps(comparison, indent=2, default=str))

    # 5. Canary decision
    control_metrics = CanaryMetrics(
        variant_id="control",
        success_rate=0.78,
        avg_latency_ms=1200,
        avg_cost_usd=0.012,
        total_requests=250,
        error_rate=0.02,
        p95_latency_ms=3500,
    )
    canary_metrics = CanaryMetrics(
        variant_id="candidate_v2",
        success_rate=0.84,
        avg_latency_ms=1100,
        avg_cost_usd=0.014,
        total_requests=250,
        error_rate=0.01,
        p95_latency_ms=3200,
    )

    engine = CanaryDecisionEngine()
    decision, reasons = engine.decide(control_metrics, canary_metrics)
    print(f"\nCANARY DECISION: {decision.value}")
    print(f"Reasons: {json.dumps(reasons, indent=2, default=str)}")


if __name__ == "__main__":
    main()
