"""
Enterprise AI Platform - Experiment & A/B Testing Platform
==========================================================

Infrastructure for safely testing changes to AI systems with traffic splitting,
statistical analysis, guardrails, and promotion workflows.
"""

from __future__ import annotations

import math
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional


# =============================================================================
# ENUMS AND TYPES
# =============================================================================

class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"  # Stopped early due to guardrail violation
    PROMOTED = "promoted"


class TrafficSplitStrategy(str, Enum):
    PERCENTAGE = "percentage"  # Fixed percentage per variant
    CANARY = "canary"  # Small percentage, gradually increase
    MULTI_ARMED_BANDIT = "multi_armed_bandit"  # Adaptive allocation
    USER_BASED = "user_based"  # Consistent per user
    CONTEXT_BASED = "context_based"  # Based on request context


class MetricType(str, Enum):
    CONTINUOUS = "continuous"  # e.g., latency, cost
    BINARY = "binary"  # e.g., success/failure
    CATEGORICAL = "categorical"  # e.g., rating categories
    COUNT = "count"  # e.g., number of tool calls


class MetricDirection(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class GuardrailAction(str, Enum):
    ALERT = "alert"
    PAUSE = "pause"
    STOP = "stop"
    ROLLBACK = "rollback"


# =============================================================================
# EXPERIMENT DEFINITION
# =============================================================================

@dataclass
class ExperimentVariant:
    """A variant in an experiment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    is_control: bool = False
    traffic_percentage: float = 0.0  # 0-100
    config: dict[str, Any] = field(default_factory=dict)
    # Config can contain: model_id, prompt_id, prompt_version, temperature, etc.


@dataclass
class ExperimentMetric:
    """A metric to track during the experiment."""
    name: str = ""
    description: str = ""
    type: MetricType = MetricType.CONTINUOUS
    direction: MetricDirection = MetricDirection.HIGHER_IS_BETTER
    primary: bool = False  # Primary decision metric
    minimum_detectable_effect: float = 0.05  # 5% MDE
    confidence_level: float = 0.95
    minimum_sample_size: int = 100


@dataclass
class ExperimentGuardrail:
    """Safety guardrail for an experiment."""
    name: str = ""
    description: str = ""
    metric_name: str = ""
    threshold: float = 0.0
    comparison: str = "below"  # "below" or "above" threshold triggers
    action: GuardrailAction = GuardrailAction.ALERT
    evaluation_window_minutes: int = 60
    consecutive_violations: int = 3  # Must violate N times before action


@dataclass
class CanaryConfig:
    """Configuration for canary rollout."""
    initial_percentage: float = 5.0
    increment_percentage: float = 10.0
    increment_interval_minutes: int = 60
    max_percentage: float = 50.0
    auto_promote_at: float = 50.0  # Promote to 100% when reaching this
    rollback_on_guardrail: bool = True


@dataclass
class BanditConfig:
    """Configuration for multi-armed bandit."""
    exploration_rate: float = 0.1  # Epsilon for epsilon-greedy
    algorithm: str = "thompson_sampling"  # epsilon_greedy, ucb1, thompson_sampling
    reward_metric: str = ""  # Which metric to optimize
    update_interval_minutes: int = 15
    minimum_samples_per_arm: int = 50


@dataclass
class Experiment:
    """Complete experiment definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    hypothesis: str = ""
    owner_team: str = ""
    owner_email: str = ""
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: list[ExperimentVariant] = field(default_factory=list)
    metrics: list[ExperimentMetric] = field(default_factory=list)
    guardrails: list[ExperimentGuardrail] = field(default_factory=list)
    traffic_strategy: TrafficSplitStrategy = TrafficSplitStrategy.PERCENTAGE
    canary_config: Optional[CanaryConfig] = None
    bandit_config: Optional[BanditConfig] = None
    target_type: str = ""  # prompt, model, agent, config
    target_id: str = ""
    environment: str = "production"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_hours: int = 168  # 1 week default
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    concluded_at: Optional[datetime] = None
    winner_variant_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.status == ExperimentStatus.RUNNING

    @property
    def elapsed_hours(self) -> float:
        if not self.start_time:
            return 0
        end = self.concluded_at or datetime.utcnow()
        return (end - self.start_time).total_seconds() / 3600


# =============================================================================
# METRICS COLLECTION
# =============================================================================

@dataclass
class MetricObservation:
    """A single metric observation for a variant."""
    experiment_id: str = ""
    variant_id: str = ""
    metric_name: str = ""
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates metrics per variant."""

    def __init__(self):
        self._observations: dict[str, list[MetricObservation]] = defaultdict(list)

    def record(self, observation: MetricObservation):
        """Record a metric observation."""
        key = f"{observation.experiment_id}:{observation.variant_id}:{observation.metric_name}"
        self._observations[key].append(observation)

    def get_observations(
        self, experiment_id: str, variant_id: str, metric_name: str,
        since: Optional[datetime] = None
    ) -> list[MetricObservation]:
        """Get observations for a specific variant and metric."""
        key = f"{experiment_id}:{variant_id}:{metric_name}"
        obs = self._observations.get(key, [])
        if since:
            obs = [o for o in obs if o.timestamp >= since]
        return obs

    def get_summary(self, experiment_id: str, variant_id: str, metric_name: str) -> dict[str, Any]:
        """Get statistical summary for a variant's metric."""
        obs = self.get_observations(experiment_id, variant_id, metric_name)
        if not obs:
            return {"count": 0, "mean": 0, "std": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}

        values = sorted([o.value for o in obs])
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / max(n - 1, 1)
        std = math.sqrt(variance)

        return {
            "count": n,
            "mean": round(mean, 6),
            "std": round(std, 6),
            "min": values[0],
            "max": values[-1],
            "p50": values[n // 2],
            "p95": values[int(n * 0.95)],
            "p99": values[int(n * 0.99)],
        }


# =============================================================================
# STATISTICAL SIGNIFICANCE TESTING
# =============================================================================

class StatisticalAnalyzer:
    """Performs statistical significance tests on experiment results."""

    @staticmethod
    def z_test_proportions(
        successes_a: int, total_a: int,
        successes_b: int, total_b: int,
        confidence: float = 0.95
    ) -> dict[str, Any]:
        """Two-proportion z-test for binary metrics."""
        if total_a == 0 or total_b == 0:
            return {"significant": False, "reason": "insufficient_data"}

        p_a = successes_a / total_a
        p_b = successes_b / total_b
        p_pooled = (successes_a + successes_b) / (total_a + total_b)

        se = math.sqrt(p_pooled * (1 - p_pooled) * (1/total_a + 1/total_b))
        if se == 0:
            return {"significant": False, "reason": "zero_variance"}

        z = (p_b - p_a) / se
        # Approximate p-value using normal distribution
        p_value = 2 * (1 - StatisticalAnalyzer._normal_cdf(abs(z)))
        alpha = 1 - confidence

        return {
            "significant": p_value < alpha,
            "p_value": round(p_value, 6),
            "z_statistic": round(z, 4),
            "control_rate": round(p_a, 6),
            "treatment_rate": round(p_b, 6),
            "relative_lift": round((p_b - p_a) / max(p_a, 0.0001), 4),
            "confidence_interval": {
                "lower": round(p_b - p_a - 1.96 * se, 6),
                "upper": round(p_b - p_a + 1.96 * se, 6),
            }
        }

    @staticmethod
    def t_test_means(
        values_a: list[float], values_b: list[float],
        confidence: float = 0.95
    ) -> dict[str, Any]:
        """Welch's t-test for continuous metrics."""
        n_a, n_b = len(values_a), len(values_b)
        if n_a < 2 or n_b < 2:
            return {"significant": False, "reason": "insufficient_data"}

        mean_a = sum(values_a) / n_a
        mean_b = sum(values_b) / n_b
        var_a = sum((x - mean_a) ** 2 for x in values_a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in values_b) / (n_b - 1)

        se = math.sqrt(var_a / n_a + var_b / n_b)
        if se == 0:
            return {"significant": False, "reason": "zero_variance"}

        t = (mean_b - mean_a) / se
        # Welch-Satterthwaite degrees of freedom
        df_num = (var_a / n_a + var_b / n_b) ** 2
        df_den = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
        df = df_num / max(df_den, 1)

        # Approximate p-value (using normal approximation for large df)
        p_value = 2 * (1 - StatisticalAnalyzer._normal_cdf(abs(t)))
        alpha = 1 - confidence

        return {
            "significant": p_value < alpha,
            "p_value": round(p_value, 6),
            "t_statistic": round(t, 4),
            "degrees_of_freedom": round(df, 2),
            "control_mean": round(mean_a, 6),
            "treatment_mean": round(mean_b, 6),
            "relative_lift": round((mean_b - mean_a) / max(abs(mean_a), 0.0001), 4),
            "confidence_interval": {
                "lower": round(mean_b - mean_a - 1.96 * se, 6),
                "upper": round(mean_b - mean_a + 1.96 * se, 6),
            }
        }

    @staticmethod
    def calculate_sample_size(
        baseline_rate: float, mde: float, confidence: float = 0.95, power: float = 0.80
    ) -> int:
        """Calculate required sample size per variant for a proportion test."""
        alpha = 1 - confidence
        z_alpha = StatisticalAnalyzer._normal_ppf(1 - alpha / 2)
        z_beta = StatisticalAnalyzer._normal_ppf(power)
        p1 = baseline_rate
        p2 = baseline_rate * (1 + mde)
        p_bar = (p1 + p2) / 2

        n = ((z_alpha * math.sqrt(2 * p_bar * (1 - p_bar)) +
              z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / max((p2 - p1) ** 2, 0.0001)
        return int(math.ceil(n))

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate standard normal CDF."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _normal_ppf(p: float) -> float:
        """Approximate standard normal inverse CDF (percent point function)."""
        # Rational approximation
        if p <= 0:
            return -float('inf')
        if p >= 1:
            return float('inf')
        if p == 0.5:
            return 0.0
        if p < 0.5:
            return -StatisticalAnalyzer._normal_ppf(1 - p)
        t = math.sqrt(-2 * math.log(1 - p))
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        return t - (c0 + c1 * t + c2 * t**2) / (1 + d1 * t + d2 * t**2 + d3 * t**3)


# =============================================================================
# TRAFFIC SPLITTING
# =============================================================================

class TrafficSplitter:
    """Assigns requests to experiment variants."""

    def __init__(self, metrics_collector: MetricsCollector):
        self._metrics = metrics_collector
        self._canary_state: dict[str, float] = {}  # experiment_id -> current_percentage
        self._bandit_rewards: dict[str, list[float]] = defaultdict(list)

    def assign_variant(
        self, experiment: Experiment, user_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None
    ) -> ExperimentVariant:
        """Assign a request to a variant based on the experiment's strategy."""
        if experiment.traffic_strategy == TrafficSplitStrategy.PERCENTAGE:
            return self._percentage_split(experiment)
        elif experiment.traffic_strategy == TrafficSplitStrategy.USER_BASED:
            return self._user_based_split(experiment, user_id or str(uuid.uuid4()))
        elif experiment.traffic_strategy == TrafficSplitStrategy.CANARY:
            return self._canary_split(experiment)
        elif experiment.traffic_strategy == TrafficSplitStrategy.MULTI_ARMED_BANDIT:
            return self._bandit_split(experiment)
        elif experiment.traffic_strategy == TrafficSplitStrategy.CONTEXT_BASED:
            return self._context_split(experiment, context or {})
        return experiment.variants[0]  # Default to control

    def _percentage_split(self, experiment: Experiment) -> ExperimentVariant:
        """Simple percentage-based random split."""
        rand = random.random() * 100
        cumulative = 0.0
        for variant in experiment.variants:
            cumulative += variant.traffic_percentage
            if rand <= cumulative:
                return variant
        return experiment.variants[-1]

    def _user_based_split(self, experiment: Experiment, user_id: str) -> ExperimentVariant:
        """Consistent assignment based on user ID hash."""
        hash_val = int(hashlib.md5(f"{experiment.id}:{user_id}".encode()).hexdigest(), 16)
        bucket = (hash_val % 10000) / 100.0  # 0-100
        cumulative = 0.0
        for variant in experiment.variants:
            cumulative += variant.traffic_percentage
            if bucket <= cumulative:
                return variant
        return experiment.variants[-1]

    def _canary_split(self, experiment: Experiment) -> ExperimentVariant:
        """Canary split with gradual increase."""
        config = experiment.canary_config or CanaryConfig()
        current_pct = self._canary_state.get(experiment.id, config.initial_percentage)

        # Auto-increment based on time
        if experiment.start_time:
            elapsed_minutes = (datetime.utcnow() - experiment.start_time).total_seconds() / 60
            increments = int(elapsed_minutes / config.increment_interval_minutes)
            current_pct = min(
                config.initial_percentage + increments * config.increment_percentage,
                config.max_percentage
            )
            self._canary_state[experiment.id] = current_pct

        # Assign: treatment gets current_pct, control gets the rest
        if random.random() * 100 < current_pct:
            return next((v for v in experiment.variants if not v.is_control), experiment.variants[-1])
        return next((v for v in experiment.variants if v.is_control), experiment.variants[0])

    def _bandit_split(self, experiment: Experiment) -> ExperimentVariant:
        """Multi-armed bandit allocation (Thompson Sampling)."""
        config = experiment.bandit_config or BanditConfig()

        if config.algorithm == "epsilon_greedy":
            return self._epsilon_greedy(experiment, config)
        elif config.algorithm == "thompson_sampling":
            return self._thompson_sampling(experiment, config)
        elif config.algorithm == "ucb1":
            return self._ucb1(experiment, config)
        return experiment.variants[0]

    def _epsilon_greedy(self, experiment: Experiment, config: BanditConfig) -> ExperimentVariant:
        """Epsilon-greedy selection."""
        if random.random() < config.exploration_rate:
            return random.choice(experiment.variants)
        # Exploit: pick best performing variant
        best_variant = experiment.variants[0]
        best_reward = -float('inf')
        for variant in experiment.variants:
            summary = self._metrics.get_summary(experiment.id, variant.id, config.reward_metric)
            if summary["count"] > 0 and summary["mean"] > best_reward:
                best_reward = summary["mean"]
                best_variant = variant
        return best_variant

    def _thompson_sampling(self, experiment: Experiment, config: BanditConfig) -> ExperimentVariant:
        """Thompson Sampling for binary rewards."""
        best_variant = experiment.variants[0]
        best_sample = -float('inf')
        for variant in experiment.variants:
            summary = self._metrics.get_summary(experiment.id, variant.id, config.reward_metric)
            successes = int(summary["mean"] * summary["count"]) if summary["count"] > 0 else 1
            failures = summary["count"] - successes if summary["count"] > 0 else 1
            # Sample from Beta distribution (approximation)
            sample = random.betavariate(max(successes, 1), max(failures, 1))
            if sample > best_sample:
                best_sample = sample
                best_variant = variant
        return best_variant

    def _ucb1(self, experiment: Experiment, config: BanditConfig) -> ExperimentVariant:
        """Upper Confidence Bound selection."""
        total_samples = sum(
            self._metrics.get_summary(experiment.id, v.id, config.reward_metric)["count"]
            for v in experiment.variants
        )
        if total_samples == 0:
            return random.choice(experiment.variants)

        best_variant = experiment.variants[0]
        best_ucb = -float('inf')
        for variant in experiment.variants:
            summary = self._metrics.get_summary(experiment.id, variant.id, config.reward_metric)
            if summary["count"] == 0:
                return variant  # Explore unvisited arms
            ucb = summary["mean"] + math.sqrt(2 * math.log(total_samples) / summary["count"])
            if ucb > best_ucb:
                best_ucb = ucb
                best_variant = variant
        return best_variant

    def _context_split(self, experiment: Experiment, context: dict[str, Any]) -> ExperimentVariant:
        """Context-based splitting (e.g., by language, region, complexity)."""
        # Use context hash for consistent assignment
        context_str = json.dumps(context, sort_keys=True)
        return self._user_based_split(experiment, context_str)


import hashlib
import json


# =============================================================================
# GUARDRAIL ENGINE
# =============================================================================

class GuardrailEngine:
    """Monitors experiments and enforces safety guardrails."""

    def __init__(self, metrics_collector: MetricsCollector):
        self._metrics = metrics_collector
        self._violation_counts: dict[str, int] = defaultdict(int)
        self._alerts: list[dict[str, Any]] = []

    def check_guardrails(self, experiment: Experiment) -> list[dict[str, Any]]:
        """Check all guardrails for an experiment. Returns list of violations."""
        violations = []
        for guardrail in experiment.guardrails:
            for variant in experiment.variants:
                violation = self._check_single_guardrail(experiment, variant, guardrail)
                if violation:
                    violations.append(violation)
        return violations

    def _check_single_guardrail(
        self, experiment: Experiment, variant: ExperimentVariant, guardrail: ExperimentGuardrail
    ) -> Optional[dict[str, Any]]:
        """Check a single guardrail for a variant."""
        since = datetime.utcnow() - timedelta(minutes=guardrail.evaluation_window_minutes)
        summary = self._metrics.get_summary(experiment.id, variant.id, guardrail.metric_name)

        if summary["count"] == 0:
            return None

        current_value = summary["mean"]
        violated = False

        if guardrail.comparison == "below" and current_value < guardrail.threshold:
            violated = True
        elif guardrail.comparison == "above" and current_value > guardrail.threshold:
            violated = True

        if violated:
            key = f"{experiment.id}:{variant.id}:{guardrail.name}"
            self._violation_counts[key] += 1

            if self._violation_counts[key] >= guardrail.consecutive_violations:
                return {
                    "experiment_id": experiment.id,
                    "variant_id": variant.id,
                    "variant_name": variant.name,
                    "guardrail_name": guardrail.name,
                    "metric_name": guardrail.metric_name,
                    "current_value": current_value,
                    "threshold": guardrail.threshold,
                    "action": guardrail.action.value,
                    "consecutive_violations": self._violation_counts[key],
                    "timestamp": datetime.utcnow().isoformat(),
                }
        else:
            # Reset counter on non-violation
            key = f"{experiment.id}:{variant.id}:{guardrail.name}"
            self._violation_counts[key] = 0

        return None

    def execute_action(self, violation: dict[str, Any], experiment: Experiment) -> str:
        """Execute the guardrail action."""
        action = GuardrailAction(violation["action"])
        if action == GuardrailAction.ALERT:
            self._alerts.append(violation)
            return "alert_sent"
        elif action == GuardrailAction.PAUSE:
            experiment.status = ExperimentStatus.PAUSED
            return "experiment_paused"
        elif action == GuardrailAction.STOP:
            experiment.status = ExperimentStatus.STOPPED
            experiment.concluded_at = datetime.utcnow()
            return "experiment_stopped"
        elif action == GuardrailAction.ROLLBACK:
            experiment.status = ExperimentStatus.STOPPED
            experiment.concluded_at = datetime.utcnow()
            # In production: route all traffic back to control
            return "rolled_back_to_control"
        return "no_action"


# =============================================================================
# EXPERIMENT LIFECYCLE MANAGER
# =============================================================================

class ExperimentPlatform:
    """
    Main experiment platform managing the full lifecycle of experiments.
    """

    def __init__(self):
        self._experiments: dict[str, Experiment] = {}
        self._metrics_collector = MetricsCollector()
        self._traffic_splitter = TrafficSplitter(self._metrics_collector)
        self._guardrail_engine = GuardrailEngine(self._metrics_collector)
        self._statistical_analyzer = StatisticalAnalyzer()

    # -------------------------------------------------------------------------
    # LIFECYCLE MANAGEMENT
    # -------------------------------------------------------------------------

    def create_experiment(self, experiment: Experiment) -> str:
        """Create a new experiment (draft state)."""
        # Validation
        if not experiment.variants:
            raise ValueError("Experiment must have at least 2 variants")
        if len(experiment.variants) < 2:
            raise ValueError("Need at least a control and one treatment variant")
        if not any(v.is_control for v in experiment.variants):
            raise ValueError("Must have exactly one control variant")
        total_traffic = sum(v.traffic_percentage for v in experiment.variants)
        if abs(total_traffic - 100.0) > 0.01:
            raise ValueError(f"Traffic percentages must sum to 100, got {total_traffic}")
        if not experiment.metrics:
            raise ValueError("Must define at least one metric")
        if not any(m.primary for m in experiment.metrics):
            raise ValueError("Must have at least one primary metric")

        self._experiments[experiment.id] = experiment
        return experiment.id

    def start_experiment(self, experiment_id: str) -> bool:
        """Start a draft/scheduled experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")
        if exp.status not in (ExperimentStatus.DRAFT, ExperimentStatus.SCHEDULED):
            raise ValueError(f"Cannot start experiment in {exp.status.value} state")

        exp.status = ExperimentStatus.RUNNING
        exp.start_time = datetime.utcnow()
        exp.end_time = exp.start_time + timedelta(hours=exp.duration_hours)
        exp.updated_at = datetime.utcnow()
        return True

    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause a running experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return False
        exp.status = ExperimentStatus.PAUSED
        exp.updated_at = datetime.utcnow()
        return True

    def resume_experiment(self, experiment_id: str) -> bool:
        """Resume a paused experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.PAUSED:
            return False
        exp.status = ExperimentStatus.RUNNING
        exp.updated_at = datetime.utcnow()
        return True

    def stop_experiment(self, experiment_id: str, reason: str = "") -> bool:
        """Stop an experiment early."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status not in (ExperimentStatus.RUNNING, ExperimentStatus.PAUSED):
            return False
        exp.status = ExperimentStatus.STOPPED
        exp.concluded_at = datetime.utcnow()
        exp.updated_at = datetime.utcnow()
        return True

    def complete_experiment(self, experiment_id: str) -> bool:
        """Mark experiment as completed (duration elapsed)."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return False
        exp.status = ExperimentStatus.COMPLETED
        exp.concluded_at = datetime.utcnow()
        exp.updated_at = datetime.utcnow()
        return True

    # -------------------------------------------------------------------------
    # TRAFFIC ASSIGNMENT
    # -------------------------------------------------------------------------

    def get_variant(
        self, experiment_id: str, user_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None
    ) -> Optional[ExperimentVariant]:
        """Get the variant assignment for a request."""
        exp = self._experiments.get(experiment_id)
        if not exp or not exp.is_active:
            return None
        return self._traffic_splitter.assign_variant(exp, user_id, context)

    # -------------------------------------------------------------------------
    # METRICS
    # -------------------------------------------------------------------------

    def record_metric(
        self, experiment_id: str, variant_id: str, metric_name: str,
        value: float, user_id: Optional[str] = None, metadata: Optional[dict] = None
    ):
        """Record a metric observation."""
        self._metrics_collector.record(MetricObservation(
            experiment_id=experiment_id,
            variant_id=variant_id,
            metric_name=metric_name,
            value=value,
            user_id=user_id,
            metadata=metadata or {},
        ))

    # -------------------------------------------------------------------------
    # ANALYSIS
    # -------------------------------------------------------------------------

    def analyze_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Perform full statistical analysis of an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        control = next((v for v in exp.variants if v.is_control), None)
        if not control:
            raise ValueError("No control variant found")

        results: dict[str, Any] = {
            "experiment_id": experiment_id,
            "status": exp.status.value,
            "elapsed_hours": round(exp.elapsed_hours, 1),
            "variants": {},
            "metrics": {},
            "recommendation": None,
        }

        # Analyze each metric
        for metric in exp.metrics:
            metric_results: dict[str, Any] = {"control": {}, "treatments": {}}
            control_summary = self._metrics_collector.get_summary(experiment_id, control.id, metric.name)
            metric_results["control"] = control_summary

            for variant in exp.variants:
                if variant.is_control:
                    continue
                treatment_summary = self._metrics_collector.get_summary(experiment_id, variant.id, metric.name)
                metric_results["treatments"][variant.name] = treatment_summary

                # Statistical test
                if metric.type == MetricType.BINARY:
                    test_result = self._statistical_analyzer.z_test_proportions(
                        int(control_summary["mean"] * control_summary["count"]),
                        control_summary["count"],
                        int(treatment_summary["mean"] * treatment_summary["count"]),
                        treatment_summary["count"],
                        metric.confidence_level,
                    )
                else:
                    control_obs = self._metrics_collector.get_observations(experiment_id, control.id, metric.name)
                    treatment_obs = self._metrics_collector.get_observations(experiment_id, variant.id, metric.name)
                    test_result = self._statistical_analyzer.t_test_means(
                        [o.value for o in control_obs],
                        [o.value for o in treatment_obs],
                        metric.confidence_level,
                    )
                metric_results["treatments"][variant.name]["significance"] = test_result

            results["metrics"][metric.name] = metric_results

        # Generate recommendation
        results["recommendation"] = self._generate_recommendation(exp, results)
        return results

    def _generate_recommendation(self, experiment: Experiment, results: dict[str, Any]) -> dict[str, Any]:
        """Generate a recommendation based on analysis results."""
        primary_metrics = [m for m in experiment.metrics if m.primary]
        if not primary_metrics:
            return {"action": "inconclusive", "reason": "No primary metric defined"}

        primary = primary_metrics[0]
        metric_data = results["metrics"].get(primary.name, {})
        treatments = metric_data.get("treatments", {})

        best_treatment = None
        best_lift = 0

        for name, data in treatments.items():
            sig = data.get("significance", {})
            if sig.get("significant") and sig.get("relative_lift", 0) > best_lift:
                if primary.direction == MetricDirection.HIGHER_IS_BETTER:
                    if sig["relative_lift"] > 0:
                        best_lift = sig["relative_lift"]
                        best_treatment = name
                else:
                    if sig["relative_lift"] < 0:
                        best_lift = abs(sig["relative_lift"])
                        best_treatment = name

        if best_treatment:
            return {
                "action": "promote",
                "winner": best_treatment,
                "lift": round(best_lift * 100, 2),
                "confidence": primary.confidence_level,
                "reason": f"{best_treatment} shows {round(best_lift * 100, 1)}% improvement on {primary.name}",
            }

        # Check if we have enough data
        control_data = metric_data.get("control", {})
        if control_data.get("count", 0) < primary.minimum_sample_size:
            return {
                "action": "wait",
                "reason": f"Insufficient data. Need {primary.minimum_sample_size} samples, have {control_data.get('count', 0)}",
            }

        return {"action": "no_winner", "reason": "No variant shows statistically significant improvement"}

    # -------------------------------------------------------------------------
    # GUARDRAIL MONITORING
    # -------------------------------------------------------------------------

    def check_guardrails(self, experiment_id: str) -> list[dict[str, Any]]:
        """Check guardrails for an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return []

        violations = self._guardrail_engine.check_guardrails(exp)
        for violation in violations:
            self._guardrail_engine.execute_action(violation, exp)
        return violations

    # -------------------------------------------------------------------------
    # PROMOTION WORKFLOW
    # -------------------------------------------------------------------------

    def promote_winner(self, experiment_id: str, variant_id: str) -> dict[str, Any]:
        """Promote the winning variant to become the new default."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")
        if exp.status not in (ExperimentStatus.COMPLETED, ExperimentStatus.RUNNING):
            raise ValueError(f"Cannot promote from {exp.status.value} state")

        winner = next((v for v in exp.variants if v.id == variant_id), None)
        if not winner:
            raise ValueError(f"Variant {variant_id} not found")

        exp.winner_variant_id = variant_id
        exp.status = ExperimentStatus.PROMOTED
        exp.concluded_at = datetime.utcnow()

        # In production: update the target (prompt, model config, etc.) to use winner's config
        return {
            "experiment_id": experiment_id,
            "promoted_variant": winner.name,
            "config": winner.config,
            "target_type": exp.target_type,
            "target_id": exp.target_id,
            "promoted_at": datetime.utcnow().isoformat(),
            "action_required": f"Update {exp.target_type} '{exp.target_id}' with config: {winner.config}",
        }

    # -------------------------------------------------------------------------
    # REPORTING
    # -------------------------------------------------------------------------

    def generate_report(self, experiment_id: str) -> dict[str, Any]:
        """Generate a comprehensive experiment report."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        analysis = self.analyze_experiment(experiment_id)

        return {
            "experiment": {
                "id": exp.id,
                "name": exp.name,
                "hypothesis": exp.hypothesis,
                "status": exp.status.value,
                "owner": exp.owner_team,
                "duration_hours": round(exp.elapsed_hours, 1),
                "strategy": exp.traffic_strategy.value,
            },
            "variants": [
                {"name": v.name, "is_control": v.is_control, "traffic_pct": v.traffic_percentage}
                for v in exp.variants
            ],
            "analysis": analysis,
            "guardrail_violations": self.check_guardrails(experiment_id),
            "conclusion": analysis.get("recommendation", {}),
            "generated_at": datetime.utcnow().isoformat(),
        }


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def main():
    """Demonstrate experiment platform usage."""
    platform = ExperimentPlatform()

    # Define an experiment: testing a new prompt version
    experiment = Experiment(
        name="Support Classifier V3 vs V2",
        description="Testing if the new classifier prompt improves accuracy",
        hypothesis="V3 prompt with chain-of-thought will improve classification accuracy by >5%",
        owner_team="support-engineering",
        owner_email="support-eng@company.com",
        target_type="prompt",
        target_id="support-classifier",
        traffic_strategy=TrafficSplitStrategy.USER_BASED,
        duration_hours=168,
        variants=[
            ExperimentVariant(
                name="control-v2", is_control=True, traffic_percentage=50.0,
                config={"prompt_version": "2.1.0"}
            ),
            ExperimentVariant(
                name="treatment-v3", is_control=False, traffic_percentage=50.0,
                config={"prompt_version": "3.0.0-rc1"}
            ),
        ],
        metrics=[
            ExperimentMetric(
                name="accuracy", type=MetricType.BINARY,
                direction=MetricDirection.HIGHER_IS_BETTER,
                primary=True, minimum_detectable_effect=0.05,
                minimum_sample_size=200,
            ),
            ExperimentMetric(
                name="latency_ms", type=MetricType.CONTINUOUS,
                direction=MetricDirection.LOWER_IS_BETTER,
                primary=False,
            ),
            ExperimentMetric(
                name="cost_usd", type=MetricType.CONTINUOUS,
                direction=MetricDirection.LOWER_IS_BETTER,
                primary=False,
            ),
        ],
        guardrails=[
            ExperimentGuardrail(
                name="accuracy_floor",
                metric_name="accuracy",
                threshold=0.7,
                comparison="below",
                action=GuardrailAction.STOP,
                consecutive_violations=5,
            ),
            ExperimentGuardrail(
                name="cost_ceiling",
                metric_name="cost_usd",
                threshold=0.05,
                comparison="above",
                action=GuardrailAction.ALERT,
                consecutive_violations=10,
            ),
        ],
    )

    # Create and start
    exp_id = platform.create_experiment(experiment)
    platform.start_experiment(exp_id)
    print(f"Started experiment: {experiment.name} (ID: {exp_id})")

    # Simulate traffic and metrics
    random.seed(42)
    control_id = experiment.variants[0].id
    treatment_id = experiment.variants[1].id

    for i in range(500):
        # Simulate: treatment is 8% better on accuracy
        user_id = f"user-{i}"
        variant = platform.get_variant(exp_id, user_id=user_id)
        if variant:
            if variant.is_control:
                accuracy = 1.0 if random.random() < 0.78 else 0.0
                latency = random.gauss(1200, 200)
                cost = random.gauss(0.003, 0.001)
            else:
                accuracy = 1.0 if random.random() < 0.86 else 0.0
                latency = random.gauss(1400, 250)  # Slightly slower
                cost = random.gauss(0.004, 0.001)  # Slightly more expensive

            platform.record_metric(exp_id, variant.id, "accuracy", accuracy, user_id)
            platform.record_metric(exp_id, variant.id, "latency_ms", latency, user_id)
            platform.record_metric(exp_id, variant.id, "cost_usd", max(0, cost), user_id)

    # Analyze
    report = platform.generate_report(exp_id)
    print(f"\nExperiment Report:")
    print(f"  Status: {report['experiment']['status']}")
    print(f"  Recommendation: {report['conclusion']}")

    # Check if we should promote
    recommendation = report["conclusion"]
    if recommendation.get("action") == "promote":
        winner_name = recommendation["winner"]
        winner_variant = next(v for v in experiment.variants if v.name == winner_name)
        result = platform.promote_winner(exp_id, winner_variant.id)
        print(f"\n  Promoted: {result['promoted_variant']}")
        print(f"  Action: {result['action_required']}")

    # Sample size calculation
    required_n = StatisticalAnalyzer.calculate_sample_size(
        baseline_rate=0.78, mde=0.05, confidence=0.95, power=0.80
    )
    print(f"\n  Required sample size per variant: {required_n}")


if __name__ == "__main__":
    main()
