"""
LLMOps: Continuous Improvement System
=======================================
Production-grade system for continuous improvement of LLM applications:
trace collection, failure detection, human review, feedback-to-eval pipeline,
A/B experimentation, and automated regression testing.
"""

import hashlib
import json
import uuid
import time
import random
import statistics
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import Counter, defaultdict
from abc import ABC, abstractmethod
import heapq


# =============================================================================
# Core Data Models
# =============================================================================

class TraceStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    ERROR = "error"


class FailureCategory(str, Enum):
    HALLUCINATION = "hallucination"
    SAFETY_VIOLATION = "safety_violation"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    WRONG_ANSWER = "wrong_answer"
    OFF_TOPIC = "off_topic"
    FORMATTING = "formatting"
    INCOMPLETE = "incomplete"
    LOOP = "loop"
    COST_EXCEEDED = "cost_exceeded"
    UNKNOWN = "unknown"


class ReviewPriority(str, Enum):
    CRITICAL = "critical"  # Safety issues
    HIGH = "high"  # User-reported failures
    MEDIUM = "medium"  # Auto-detected quality issues
    LOW = "low"  # Optimization opportunities


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class ProductionTrace:
    """A single production trace (request-response pair with metadata)."""
    id: str
    timestamp: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    model: str
    prompt_version: str
    latency_ms: float
    token_count: dict[str, int]  # input_tokens, output_tokens
    cost_usd: float
    status: TraceStatus
    user_feedback: Optional[dict] = None  # thumbs, rating, correction
    quality_scores: dict[str, float] = field(default_factory=dict)  # judge scores
    metadata: dict[str, Any] = field(default_factory=dict)
    error_info: Optional[dict] = None
    tags: list[str] = field(default_factory=list)


@dataclass
class FailureCluster:
    """A cluster of similar failures."""
    id: str
    category: FailureCategory
    description: str
    trace_ids: list[str]
    count: int
    first_seen: str
    last_seen: str
    impact_score: float  # Computed from frequency * severity
    root_cause: Optional[str] = None
    fix_status: str = "open"  # open, investigating, fixed, wont_fix
    fix_version: Optional[str] = None
    representative_traces: list[str] = field(default_factory=list)


@dataclass
class ReviewItem:
    """An item in the human review queue."""
    id: str
    trace_id: str
    priority: ReviewPriority
    category: str
    created_at: str
    assigned_to: Optional[str] = None
    assigned_at: Optional[str] = None
    status: str = "pending"  # pending, assigned, in_review, completed, skipped
    review_result: Optional[dict] = None
    time_to_review_sec: Optional[float] = None


@dataclass
class Experiment:
    """An A/B experiment comparing two or more variants."""
    id: str
    name: str
    hypothesis: str
    variants: list[dict[str, Any]]  # [{name, prompt_version, model, config}]
    metrics: list[str]  # Primary and guardrail metrics
    traffic_split: dict[str, float]  # variant_name -> percentage
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.DRAFT
    results: dict[str, Any] = field(default_factory=dict)
    min_samples_per_variant: int = 100
    max_duration_hours: int = 168  # 1 week
    created_by: str = ""


@dataclass
class ImprovementCandidate:
    """A candidate improvement to be evaluated and potentially deployed."""
    id: str
    title: str
    description: str
    source: str  # failure_cluster, experiment, human_review, proactive
    source_id: Optional[str] = None
    change_type: str  # prompt, model, config, tool, guardrail
    change_spec: dict[str, Any]  # What exactly to change
    expected_impact: dict[str, float]  # metric -> expected improvement
    priority_score: float
    status: str = "proposed"  # proposed, evaluating, approved, deployed, rejected
    eval_results: Optional[dict] = None
    created_at: str = ""


# =============================================================================
# Production Trace Collector
# =============================================================================

class TraceCollector:
    """Collects and stores production traces with sampling."""

    def __init__(self, sample_rate: float = 1.0, max_buffer_size: int = 10000):
        self.sample_rate = sample_rate
        self.max_buffer_size = max_buffer_size
        self.traces: list[ProductionTrace] = []
        self.trace_index: dict[str, int] = {}  # trace_id -> index
        self.stats = {
            "total_collected": 0,
            "total_sampled_out": 0,
            "total_failures": 0,
        }

    def collect(self, trace: ProductionTrace) -> bool:
        """Collect a trace. Returns True if stored, False if sampled out."""
        # Always collect failures regardless of sample rate
        if trace.status == TraceStatus.SUCCESS and random.random() > self.sample_rate:
            self.stats["total_sampled_out"] += 1
            return False

        if len(self.traces) >= self.max_buffer_size:
            self._evict_oldest()

        self.trace_index[trace.id] = len(self.traces)
        self.traces.append(trace)
        self.stats["total_collected"] += 1
        if trace.status != TraceStatus.SUCCESS:
            self.stats["total_failures"] += 1
        return True

    def get_trace(self, trace_id: str) -> Optional[ProductionTrace]:
        idx = self.trace_index.get(trace_id)
        return self.traces[idx] if idx is not None else None

    def query_traces(
        self,
        status: Optional[TraceStatus] = None,
        since: Optional[str] = None,
        limit: int = 100,
        tags: Optional[list[str]] = None,
    ) -> list[ProductionTrace]:
        """Query traces with filters."""
        results = []
        for trace in reversed(self.traces):
            if status and trace.status != status:
                continue
            if since and trace.timestamp < since:
                break
            if tags and not set(tags).issubset(set(trace.tags)):
                continue
            results.append(trace)
            if len(results) >= limit:
                break
        return results

    def get_failure_traces(self, limit: int = 100) -> list[ProductionTrace]:
        """Get recent failure traces."""
        return self.query_traces(status=TraceStatus.FAILURE, limit=limit)

    def _evict_oldest(self):
        """Remove oldest successful traces to make room."""
        # Keep all failures, evict oldest successes
        new_traces = []
        new_index = {}
        for trace in self.traces:
            if trace.status != TraceStatus.SUCCESS or len(new_traces) < self.max_buffer_size * 0.8:
                new_index[trace.id] = len(new_traces)
                new_traces.append(trace)
        self.traces = new_traces
        self.trace_index = new_index


# =============================================================================
# Failure Detection and Clustering
# =============================================================================

class FailureDetector:
    """Detects and classifies failures from production traces."""

    def __init__(self):
        self.rules: list[Callable[[ProductionTrace], Optional[FailureCategory]]] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """Register default failure detection rules."""
        self.rules.append(self._detect_timeout)
        self.rules.append(self._detect_error)
        self.rules.append(self._detect_low_quality)
        self.rules.append(self._detect_safety)
        self.rules.append(self._detect_cost_exceeded)

    def detect(self, trace: ProductionTrace) -> Optional[FailureCategory]:
        """Detect failure category for a trace."""
        for rule in self.rules:
            category = rule(trace)
            if category:
                return category
        if trace.status != TraceStatus.SUCCESS:
            return FailureCategory.UNKNOWN
        return None

    def _detect_timeout(self, trace: ProductionTrace) -> Optional[FailureCategory]:
        if trace.status == TraceStatus.TIMEOUT or trace.latency_ms > 30000:
            return FailureCategory.TIMEOUT
        return None

    def _detect_error(self, trace: ProductionTrace) -> Optional[FailureCategory]:
        if trace.status == TraceStatus.ERROR:
            if trace.error_info and "tool" in str(trace.error_info.get("type", "")):
                return FailureCategory.TOOL_ERROR
        return None

    def _detect_low_quality(self, trace: ProductionTrace) -> Optional[FailureCategory]:
        quality = trace.quality_scores.get("overall", 1.0)
        if quality < 0.3:
            if trace.quality_scores.get("relevance", 1.0) < 0.3:
                return FailureCategory.OFF_TOPIC
            if trace.quality_scores.get("correctness", 1.0) < 0.3:
                return FailureCategory.HALLUCINATION
            return FailureCategory.WRONG_ANSWER
        return None

    def _detect_safety(self, trace: ProductionTrace) -> Optional[FailureCategory]:
        if trace.quality_scores.get("safety", 1.0) < 0.5:
            return FailureCategory.SAFETY_VIOLATION
        return None

    def _detect_cost_exceeded(self, trace: ProductionTrace) -> Optional[FailureCategory]:
        if trace.cost_usd > 1.0:  # Configurable threshold
            return FailureCategory.COST_EXCEEDED
        return None

    def add_rule(self, rule: Callable[[ProductionTrace], Optional[FailureCategory]]):
        self.rules.append(rule)


class FailureClusterer:
    """Clusters similar failures for batch resolution."""

    def __init__(self):
        self.clusters: dict[str, FailureCluster] = {}

    def add_failure(self, trace: ProductionTrace, category: FailureCategory):
        """Add a failure to the appropriate cluster."""
        cluster_key = self._compute_cluster_key(trace, category)

        if cluster_key not in self.clusters:
            self.clusters[cluster_key] = FailureCluster(
                id=cluster_key,
                category=category,
                description=self._generate_description(trace, category),
                trace_ids=[],
                count=0,
                first_seen=trace.timestamp,
                last_seen=trace.timestamp,
                impact_score=0,
                representative_traces=[],
            )

        cluster = self.clusters[cluster_key]
        cluster.trace_ids.append(trace.id)
        cluster.count += 1
        cluster.last_seen = trace.timestamp
        cluster.impact_score = self._compute_impact(cluster)

        # Keep representative traces (max 5)
        if len(cluster.representative_traces) < 5:
            cluster.representative_traces.append(trace.id)

    def get_top_clusters(self, limit: int = 10, status: str = "open") -> list[FailureCluster]:
        """Get top failure clusters by impact score."""
        clusters = [c for c in self.clusters.values() if c.fix_status == status]
        return sorted(clusters, key=lambda c: c.impact_score, reverse=True)[:limit]

    def get_cluster(self, cluster_id: str) -> Optional[FailureCluster]:
        return self.clusters.get(cluster_id)

    def mark_fixed(self, cluster_id: str, fix_version: str):
        cluster = self.clusters.get(cluster_id)
        if cluster:
            cluster.fix_status = "fixed"
            cluster.fix_version = fix_version

    def _compute_cluster_key(self, trace: ProductionTrace, category: FailureCategory) -> str:
        """Compute a cluster key based on failure signature."""
        # Cluster by category + prompt_version + error pattern
        signature = f"{category.value}:{trace.prompt_version}"
        if trace.error_info:
            signature += f":{trace.error_info.get('type', 'unknown')}"
        return hashlib.md5(signature.encode()).hexdigest()[:12]

    def _generate_description(self, trace: ProductionTrace, category: FailureCategory) -> str:
        return f"{category.value} failures in prompt {trace.prompt_version}"

    def _compute_impact(self, cluster: FailureCluster) -> float:
        """Impact = frequency * severity * recency."""
        severity_map = {
            FailureCategory.SAFETY_VIOLATION: 10.0,
            FailureCategory.HALLUCINATION: 8.0,
            FailureCategory.WRONG_ANSWER: 6.0,
            FailureCategory.TOOL_ERROR: 5.0,
            FailureCategory.TIMEOUT: 4.0,
            FailureCategory.OFF_TOPIC: 3.0,
            FailureCategory.COST_EXCEEDED: 3.0,
            FailureCategory.LOOP: 7.0,
            FailureCategory.INCOMPLETE: 4.0,
            FailureCategory.FORMATTING: 2.0,
            FailureCategory.UNKNOWN: 1.0,
        }
        severity = severity_map.get(cluster.category, 1.0)
        frequency = min(cluster.count / 10.0, 10.0)  # Cap at 10x
        return frequency * severity


# =============================================================================
# Human Review Queue
# =============================================================================

class HumanReviewQueue:
    """Priority-based queue for human review of production outputs."""

    def __init__(self):
        self.items: list[ReviewItem] = []
        self.completed: list[ReviewItem] = []
        self.reviewers: dict[str, dict] = {}  # reviewer_id -> stats

    def add_item(self, trace_id: str, priority: ReviewPriority, category: str) -> ReviewItem:
        """Add an item to the review queue."""
        item = ReviewItem(
            id=str(uuid.uuid4()),
            trace_id=trace_id,
            priority=priority,
            category=category,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.items.append(item)
        return item

    def assign_next(self, reviewer_id: str) -> Optional[ReviewItem]:
        """Assign the highest-priority unassigned item to a reviewer."""
        priority_order = [ReviewPriority.CRITICAL, ReviewPriority.HIGH,
                         ReviewPriority.MEDIUM, ReviewPriority.LOW]

        for priority in priority_order:
            for item in self.items:
                if item.status == "pending" and item.priority == priority:
                    item.status = "assigned"
                    item.assigned_to = reviewer_id
                    item.assigned_at = datetime.now(timezone.utc).isoformat()
                    return item
        return None

    def complete_review(self, item_id: str, result: dict):
        """Complete a review with the result."""
        for item in self.items:
            if item.id == item_id:
                item.status = "completed"
                item.review_result = result
                if item.assigned_at:
                    assigned_time = datetime.fromisoformat(item.assigned_at)
                    item.time_to_review_sec = (datetime.now(timezone.utc) - assigned_time).total_seconds()
                self.completed.append(item)
                self.items.remove(item)

                # Update reviewer stats
                if item.assigned_to:
                    if item.assigned_to not in self.reviewers:
                        self.reviewers[item.assigned_to] = {"completed": 0, "total_time": 0}
                    self.reviewers[item.assigned_to]["completed"] += 1
                    self.reviewers[item.assigned_to]["total_time"] += item.time_to_review_sec or 0
                return
        raise ValueError(f"Review item '{item_id}' not found")

    def get_queue_stats(self) -> dict:
        """Get current queue statistics."""
        by_priority = Counter(item.priority.value for item in self.items)
        by_status = Counter(item.status for item in self.items)
        return {
            "total_pending": len(self.items),
            "total_completed": len(self.completed),
            "by_priority": dict(by_priority),
            "by_status": dict(by_status),
            "avg_review_time_sec": (
                statistics.mean(i.time_to_review_sec for i in self.completed if i.time_to_review_sec)
                if self.completed else 0
            ),
        }


# =============================================================================
# Feedback-to-Eval Pipeline
# =============================================================================

class FeedbackToEvalPipeline:
    """Converts human review feedback into evaluation examples."""

    def __init__(self):
        self.eval_examples: list[dict] = []
        self.conversion_rules: dict[str, Callable] = {}

    def register_rule(self, review_category: str, converter: Callable):
        """Register a conversion rule for a review category."""
        self.conversion_rules[review_category] = converter

    def process_review(self, review_item: ReviewItem, trace: ProductionTrace) -> Optional[dict]:
        """Convert a completed review into an eval example."""
        if not review_item.review_result:
            return None

        # Use custom converter if available
        converter = self.conversion_rules.get(review_item.category)
        if converter:
            example = converter(review_item, trace)
        else:
            example = self._default_conversion(review_item, trace)

        if example:
            self.eval_examples.append(example)
        return example

    def _default_conversion(self, review_item: ReviewItem, trace: ProductionTrace) -> dict:
        """Default conversion: create eval example from review."""
        result = review_item.review_result
        return {
            "id": str(uuid.uuid4()),
            "input": trace.input_data,
            "expected_output": result.get("corrected_output", trace.output_data),
            "category": review_item.category,
            "quality_label": result.get("quality_label", "unknown"),
            "source": "human_review",
            "source_trace_id": trace.id,
            "source_review_id": review_item.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_new_eval_examples(self, since: Optional[str] = None) -> list[dict]:
        """Get eval examples created since a timestamp."""
        if not since:
            return self.eval_examples
        return [e for e in self.eval_examples if e.get("created_at", "") >= since]


# =============================================================================
# A/B Experiment Management
# =============================================================================

class ExperimentManager:
    """Manages A/B experiments for LLM improvements."""

    def __init__(self):
        self.experiments: dict[str, Experiment] = {}
        self.assignments: dict[str, str] = {}  # request_hash -> variant_name
        self.variant_metrics: dict[str, dict[str, list[float]]] = {}  # exp_id -> variant -> metric -> values

    def create_experiment(
        self,
        name: str,
        hypothesis: str,
        variants: list[dict],
        metrics: list[str],
        traffic_split: dict[str, float],
        min_samples: int = 100,
        max_duration_hours: int = 168,
    ) -> Experiment:
        """Create a new experiment."""
        assert abs(sum(traffic_split.values()) - 1.0) < 0.01, "Traffic split must sum to 1.0"

        experiment = Experiment(
            id=str(uuid.uuid4()),
            name=name,
            hypothesis=hypothesis,
            variants=variants,
            metrics=metrics,
            traffic_split=traffic_split,
            min_samples_per_variant=min_samples,
            max_duration_hours=max_duration_hours,
            created_by="system",
        )
        self.experiments[experiment.id] = experiment
        self.variant_metrics[experiment.id] = {v["name"]: defaultdict(list) for v in variants}
        return experiment

    def start_experiment(self, experiment_id: str):
        """Start an experiment."""
        exp = self.experiments[experiment_id]
        exp.status = ExperimentStatus.RUNNING
        exp.start_time = datetime.now(timezone.utc).isoformat()

    def assign_variant(self, experiment_id: str, request_id: str) -> str:
        """Assign a request to a variant (deterministic)."""
        exp = self.experiments[experiment_id]
        if exp.status != ExperimentStatus.RUNNING:
            raise ValueError(f"Experiment not running: {exp.status}")

        # Deterministic assignment based on request hash
        hash_val = int(hashlib.md5(f"{experiment_id}:{request_id}".encode()).hexdigest(), 16) % 10000
        cumulative = 0
        for variant in exp.variants:
            cumulative += exp.traffic_split[variant["name"]] * 10000
            if hash_val < cumulative:
                self.assignments[request_id] = variant["name"]
                return variant["name"]

        # Fallback to last variant
        return exp.variants[-1]["name"]

    def record_metric(self, experiment_id: str, variant_name: str, metric_name: str, value: float):
        """Record a metric value for a variant."""
        self.variant_metrics[experiment_id][variant_name][metric_name].append(value)

    def get_results(self, experiment_id: str) -> dict:
        """Get current experiment results with statistical analysis."""
        exp = self.experiments[experiment_id]
        results = {}

        for metric in exp.metrics:
            metric_results = {}
            for variant in exp.variants:
                values = self.variant_metrics[experiment_id][variant["name"]][metric]
                if values:
                    metric_results[variant["name"]] = {
                        "mean": statistics.mean(values),
                        "std": statistics.stdev(values) if len(values) > 1 else 0,
                        "count": len(values),
                        "ci_95": self._confidence_interval(values),
                    }
            results[metric] = metric_results

        # Determine winner for each metric
        for metric, metric_results in results.items():
            if len(metric_results) >= 2:
                sorted_variants = sorted(metric_results.items(), key=lambda x: x[1]["mean"], reverse=True)
                results[metric]["_winner"] = sorted_variants[0][0]
                results[metric]["_significant"] = self._is_significant(
                    metric_results.get(sorted_variants[0][0], {}).get("mean", 0),
                    metric_results.get(sorted_variants[1][0], {}).get("mean", 0),
                    metric_results.get(sorted_variants[0][0], {}).get("count", 0),
                )

        return results

    def complete_experiment(self, experiment_id: str, decision: str = ""):
        """Complete an experiment with a decision."""
        exp = self.experiments[experiment_id]
        exp.status = ExperimentStatus.COMPLETED
        exp.end_time = datetime.now(timezone.utc).isoformat()
        exp.results = self.get_results(experiment_id)
        exp.results["_decision"] = decision

    def _confidence_interval(self, values: list[float], confidence: float = 0.95) -> tuple[float, float]:
        """Compute bootstrap confidence interval."""
        if len(values) < 2:
            return (values[0], values[0]) if values else (0, 0)
        n_bootstrap = 1000
        means = []
        for _ in range(n_bootstrap):
            sample = random.choices(values, k=len(values))
            means.append(statistics.mean(sample))
        means.sort()
        lower_idx = int((1 - confidence) / 2 * n_bootstrap)
        upper_idx = int((1 + confidence) / 2 * n_bootstrap)
        return (means[lower_idx], means[upper_idx])

    def _is_significant(self, mean1: float, mean2: float, n: int, threshold: float = 0.05) -> bool:
        """Simple significance check (would use proper test in production)."""
        if n < 30:
            return False
        # Rough heuristic: difference > 2 * standard error
        effect_size = abs(mean1 - mean2)
        return effect_size > threshold


# =============================================================================
# Improvement Candidate Ranking
# =============================================================================

class ImprovementRanker:
    """Ranks improvement candidates by expected impact and feasibility."""

    def __init__(self):
        self.candidates: list[ImprovementCandidate] = []

    def add_candidate(
        self,
        title: str,
        description: str,
        source: str,
        change_type: str,
        change_spec: dict,
        expected_impact: dict[str, float],
        source_id: Optional[str] = None,
    ) -> ImprovementCandidate:
        """Add a new improvement candidate."""
        candidate = ImprovementCandidate(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            source=source,
            source_id=source_id,
            change_type=change_type,
            change_spec=change_spec,
            expected_impact=expected_impact,
            priority_score=self._compute_priority(expected_impact, change_type),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.candidates.append(candidate)
        return candidate

    def get_ranked_candidates(self, status: str = "proposed", limit: int = 10) -> list[ImprovementCandidate]:
        """Get candidates ranked by priority."""
        filtered = [c for c in self.candidates if c.status == status]
        return sorted(filtered, key=lambda c: c.priority_score, reverse=True)[:limit]

    def approve(self, candidate_id: str):
        for c in self.candidates:
            if c.id == candidate_id:
                c.status = "approved"
                return

    def reject(self, candidate_id: str, reason: str = ""):
        for c in self.candidates:
            if c.id == candidate_id:
                c.status = "rejected"
                return

    def _compute_priority(self, expected_impact: dict[str, float], change_type: str) -> float:
        """Priority = impact * confidence / effort."""
        # Higher impact = higher priority
        total_impact = sum(expected_impact.values())
        # Lower effort types get priority boost
        effort_multiplier = {
            "prompt": 1.5,    # Easy to change
            "config": 1.3,
            "guardrail": 1.2,
            "tool": 0.8,     # More effort
            "model": 0.6,    # Most effort
        }
        return total_impact * effort_multiplier.get(change_type, 1.0)


# =============================================================================
# Regression Testing
# =============================================================================

class RegressionTestRunner:
    """Runs regression tests against eval datasets."""

    def __init__(self):
        self.test_suites: dict[str, list[dict]] = {}  # suite_name -> test cases
        self.results_history: list[dict] = []

    def register_suite(self, name: str, test_cases: list[dict]):
        """Register a regression test suite."""
        self.test_suites[name] = test_cases

    def run_suite(self, name: str, eval_fn: Callable[[dict], dict]) -> dict:
        """Run a test suite and return results."""
        suite = self.test_suites.get(name)
        if not suite:
            raise ValueError(f"Test suite '{name}' not found")

        results = {
            "suite": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(suite),
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "failures": [],
        }

        for case in suite:
            try:
                result = eval_fn(case)
                if result.get("passed", False):
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    results["failures"].append({
                        "case_id": case.get("id"),
                        "expected": case.get("expected"),
                        "actual": result.get("output"),
                        "scores": result.get("scores", {}),
                    })
            except Exception as e:
                results["errors"] += 1
                results["failures"].append({
                    "case_id": case.get("id"),
                    "error": str(e),
                })

        results["pass_rate"] = results["passed"] / max(results["total"], 1)
        self.results_history.append(results)
        return results

    def check_regression(self, current_results: dict, threshold: float = 0.95) -> dict:
        """Check if current results represent a regression from historical baseline."""
        if not self.results_history:
            return {"regression": False, "reason": "No baseline"}

        baseline_rate = statistics.mean(r["pass_rate"] for r in self.results_history[-5:])
        current_rate = current_results["pass_rate"]

        return {
            "regression": current_rate < baseline_rate * threshold,
            "baseline_rate": baseline_rate,
            "current_rate": current_rate,
            "delta": current_rate - baseline_rate,
            "threshold": threshold,
        }


# =============================================================================
# Continuous Improvement Orchestrator
# =============================================================================

class ContinuousImprovementSystem:
    """
    Orchestrates the full continuous improvement loop.
    
    Pipeline:
    1. Collect production traces
    2. Detect and cluster failures
    3. Route to human review
    4. Convert feedback to eval examples
    5. Generate improvement candidates
    6. Evaluate candidates
    7. Run regression tests
    8. Deploy improvements
    9. Monitor impact
    """

    def __init__(self):
        self.trace_collector = TraceCollector(sample_rate=0.1)
        self.failure_detector = FailureDetector()
        self.failure_clusterer = FailureClusterer()
        self.review_queue = HumanReviewQueue()
        self.feedback_pipeline = FeedbackToEvalPipeline()
        self.experiment_manager = ExperimentManager()
        self.improvement_ranker = ImprovementRanker()
        self.regression_runner = RegressionTestRunner()
        self.metrics: dict[str, list[float]] = defaultdict(list)
        self.deployment_log: list[dict] = []

    def ingest_trace(self, trace: ProductionTrace):
        """Main entry point: ingest a production trace."""
        # Step 1: Collect
        self.trace_collector.collect(trace)

        # Step 2: Detect failures
        failure_category = self.failure_detector.detect(trace)
        if failure_category:
            self.failure_clusterer.add_failure(trace, failure_category)

            # Step 3: Route critical failures to review
            priority = self._failure_to_priority(failure_category)
            if priority in [ReviewPriority.CRITICAL, ReviewPriority.HIGH]:
                self.review_queue.add_item(trace.id, priority, failure_category.value)

        # Track metrics
        self.metrics["latency_ms"].append(trace.latency_ms)
        self.metrics["cost_usd"].append(trace.cost_usd)
        if trace.quality_scores:
            for metric, value in trace.quality_scores.items():
                self.metrics[f"quality_{metric}"].append(value)

    def process_reviews(self) -> list[dict]:
        """Process completed reviews into eval examples."""
        new_examples = []
        for item in list(self.review_queue.completed):
            trace = self.trace_collector.get_trace(item.trace_id)
            if trace:
                example = self.feedback_pipeline.process_review(item, trace)
                if example:
                    new_examples.append(example)
        return new_examples

    def generate_improvement_candidates(self) -> list[ImprovementCandidate]:
        """Generate improvement candidates from failure clusters."""
        candidates = []
        for cluster in self.failure_clusterer.get_top_clusters(limit=5):
            candidate = self.improvement_ranker.add_candidate(
                title=f"Fix: {cluster.description}",
                description=f"Address {cluster.count} failures of type {cluster.category.value}",
                source="failure_cluster",
                source_id=cluster.id,
                change_type="prompt",  # Default to prompt change
                change_spec={"cluster_id": cluster.id, "category": cluster.category.value},
                expected_impact={"failure_rate": -cluster.impact_score / 100.0},
            )
            candidates.append(candidate)
        return candidates

    def run_improvement_cycle(self) -> dict:
        """Run one complete improvement cycle."""
        cycle_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traces_collected": self.trace_collector.stats["total_collected"],
            "failures_detected": self.trace_collector.stats["total_failures"],
            "top_clusters": len(self.failure_clusterer.get_top_clusters()),
            "review_queue_size": len(self.review_queue.items),
            "new_eval_examples": len(self.process_reviews()),
            "improvement_candidates": len(self.generate_improvement_candidates()),
        }
        return cycle_result

    def get_health_summary(self) -> dict:
        """Get overall system health summary."""
        recent_latencies = self.metrics["latency_ms"][-100:]
        recent_costs = self.metrics["cost_usd"][-100:]
        recent_quality = self.metrics.get("quality_overall", [])[-100:]

        return {
            "traces_collected": self.trace_collector.stats["total_collected"],
            "failure_rate": (
                self.trace_collector.stats["total_failures"] /
                max(self.trace_collector.stats["total_collected"], 1)
            ),
            "avg_latency_ms": statistics.mean(recent_latencies) if recent_latencies else 0,
            "p99_latency_ms": sorted(recent_latencies)[int(len(recent_latencies) * 0.99)] if recent_latencies else 0,
            "avg_cost_usd": statistics.mean(recent_costs) if recent_costs else 0,
            "avg_quality": statistics.mean(recent_quality) if recent_quality else None,
            "open_clusters": len(self.failure_clusterer.get_top_clusters(status="open")),
            "review_queue_depth": len(self.review_queue.items),
            "pending_improvements": len(self.improvement_ranker.get_ranked_candidates()),
        }

    def _failure_to_priority(self, category: FailureCategory) -> ReviewPriority:
        priority_map = {
            FailureCategory.SAFETY_VIOLATION: ReviewPriority.CRITICAL,
            FailureCategory.HALLUCINATION: ReviewPriority.HIGH,
            FailureCategory.WRONG_ANSWER: ReviewPriority.HIGH,
            FailureCategory.TOOL_ERROR: ReviewPriority.MEDIUM,
            FailureCategory.TIMEOUT: ReviewPriority.LOW,
            FailureCategory.OFF_TOPIC: ReviewPriority.MEDIUM,
            FailureCategory.COST_EXCEEDED: ReviewPriority.LOW,
        }
        return priority_map.get(category, ReviewPriority.LOW)


# =============================================================================
# Usage Example
# =============================================================================

def main():
    """Demonstrate the continuous improvement system."""
    system = ContinuousImprovementSystem()

    # Simulate production traces
    print("=== Ingesting Production Traces ===")
    for i in range(100):
        status = TraceStatus.SUCCESS
        quality = random.uniform(0.5, 1.0)
        error_info = None

        # 15% failure rate
        if random.random() < 0.15:
            status = random.choice([TraceStatus.FAILURE, TraceStatus.ERROR, TraceStatus.TIMEOUT])
            quality = random.uniform(0.0, 0.4)
            if status == TraceStatus.ERROR:
                error_info = {"type": "tool_execution_error", "message": "API timeout"}

        trace = ProductionTrace(
            id=f"trace-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_data={"query": f"User query #{i}", "category": random.choice(["billing", "tech", "general"])},
            output_data={"response": f"Response #{i}"},
            model="gpt-4",
            prompt_version="v2.3",
            latency_ms=random.uniform(200, 5000),
            token_count={"input_tokens": random.randint(100, 500), "output_tokens": random.randint(50, 300)},
            cost_usd=random.uniform(0.01, 0.1),
            status=status,
            quality_scores={"overall": quality, "safety": random.uniform(0.8, 1.0), "relevance": quality},
            error_info=error_info,
        )
        system.ingest_trace(trace)

    # Health summary
    print("\n=== Health Summary ===")
    health = system.get_health_summary()
    for key, value in health.items():
        print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")

    # Top failure clusters
    print("\n=== Top Failure Clusters ===")
    for cluster in system.failure_clusterer.get_top_clusters(limit=5):
        print(f"  [{cluster.category.value}] {cluster.description} "
              f"(count={cluster.count}, impact={cluster.impact_score:.1f})")

    # Generate improvements
    print("\n=== Improvement Candidates ===")
    candidates = system.generate_improvement_candidates()
    for c in candidates[:5]:
        print(f"  [{c.priority_score:.1f}] {c.title} ({c.change_type})")

    # Run improvement cycle
    print("\n=== Improvement Cycle ===")
    cycle = system.run_improvement_cycle()
    for key, value in cycle.items():
        print(f"  {key}: {value}")

    # Simulate A/B experiment
    print("\n=== A/B Experiment ===")
    exp = system.experiment_manager.create_experiment(
        name="Improved prompt v2.4",
        hypothesis="Adding examples will improve quality by 10%",
        variants=[
            {"name": "control", "prompt_version": "v2.3"},
            {"name": "treatment", "prompt_version": "v2.4"},
        ],
        metrics=["quality_score", "latency_ms"],
        traffic_split={"control": 0.5, "treatment": 0.5},
    )
    system.experiment_manager.start_experiment(exp.id)

    # Simulate experiment data
    for i in range(200):
        variant = system.experiment_manager.assign_variant(exp.id, f"req-{i}")
        quality = random.gauss(0.75, 0.1) if variant == "control" else random.gauss(0.82, 0.1)
        latency = random.gauss(1000, 200) if variant == "control" else random.gauss(1100, 200)
        system.experiment_manager.record_metric(exp.id, variant, "quality_score", quality)
        system.experiment_manager.record_metric(exp.id, variant, "latency_ms", latency)

    results = system.experiment_manager.get_results(exp.id)
    print(f"  Experiment: {exp.name}")
    for metric, data in results.items():
        if not metric.startswith("_"):
            print(f"  {metric}:")
            for variant, stats in data.items():
                if not variant.startswith("_"):
                    print(f"    {variant}: mean={stats['mean']:.3f} (n={stats['count']})")


if __name__ == "__main__":
    main()
