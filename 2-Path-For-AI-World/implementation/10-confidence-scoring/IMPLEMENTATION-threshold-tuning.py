"""
Threshold Tuning System for Confidence Scoring

Optimizes decision thresholds for confidence-driven actions using
precision-recall analysis, cost-sensitive optimization, F-beta scores,
and production monitoring.
"""

import math
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ThresholdConfig:
    """Configuration for a single action threshold."""
    name: str  # e.g., "answer", "caveat", "clarify", "abstain"
    value: float  # Current threshold
    min_value: float = 0.0
    max_value: float = 1.0
    domain: str = "general"


@dataclass
class ThresholdPerformance:
    """Performance metrics at a given threshold."""
    threshold: float
    precision: float
    recall: float
    f1: float
    f_beta: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    accuracy: float
    total_cost: float = 0.0


@dataclass
class CostConfig:
    """Cost configuration for different error types."""
    cost_false_positive: float = 10.0   # Wrong answer given
    cost_false_negative: float = 5.0    # Correct answer withheld (abstained)
    cost_true_positive: float = -1.0    # Reward for correct answer
    cost_true_negative: float = 0.0     # Correctly abstained
    cost_human_review: float = 3.0      # Cost of routing to human


@dataclass
class ThresholdSearchResult:
    """Result of threshold optimization."""
    optimal_threshold: float
    objective_value: float
    objective_name: str
    all_thresholds: list[ThresholdPerformance]
    search_method: str
    domain: str


# =============================================================================
# Precision-Recall Computation
# =============================================================================

class PrecisionRecallComputer:
    """Computes precision-recall curves and related metrics."""

    def compute_curve(self, scores: list[float], labels: list[bool],
                      n_thresholds: int = 100) -> list[ThresholdPerformance]:
        """Compute precision, recall, F1 at multiple thresholds."""
        thresholds = [i / n_thresholds for i in range(n_thresholds + 1)]
        results = []

        for threshold in thresholds:
            perf = self._evaluate_at_threshold(scores, labels, threshold)
            results.append(perf)

        return results

    def _evaluate_at_threshold(self, scores: list[float], labels: list[bool],
                               threshold: float, beta: float = 1.0) -> ThresholdPerformance:
        """Evaluate binary classification at a single threshold."""
        tp = fp = tn = fn = 0

        for score, label in zip(scores, labels):
            predicted_positive = score >= threshold
            if predicted_positive and label:
                tp += 1
            elif predicted_positive and not label:
                fp += 1
            elif not predicted_positive and label:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # F-beta
        beta_sq = beta * beta
        f_beta = ((1 + beta_sq) * precision * recall /
                  (beta_sq * precision + recall)) if (beta_sq * precision + recall) > 0 else 0.0

        accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0.0

        return ThresholdPerformance(
            threshold=threshold,
            precision=precision,
            recall=recall,
            f1=f1,
            f_beta=f_beta,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            accuracy=accuracy,
        )

    def compute_roc_curve(self, scores: list[float], labels: list[bool],
                          n_thresholds: int = 100) -> list[dict]:
        """Compute ROC curve (TPR vs FPR)."""
        thresholds = [i / n_thresholds for i in range(n_thresholds + 1)]
        roc_points = []

        for threshold in thresholds:
            perf = self._evaluate_at_threshold(scores, labels, threshold)
            tpr = perf.true_positives / (perf.true_positives + perf.false_negatives) \
                if (perf.true_positives + perf.false_negatives) > 0 else 0.0
            fpr = perf.false_positives / (perf.false_positives + perf.true_negatives) \
                if (perf.false_positives + perf.true_negatives) > 0 else 0.0
            roc_points.append({"threshold": threshold, "tpr": tpr, "fpr": fpr})

        return roc_points

    def compute_auc(self, scores: list[float], labels: list[bool]) -> float:
        """Compute Area Under ROC Curve using trapezoidal rule."""
        roc = self.compute_roc_curve(scores, labels, n_thresholds=200)
        # Sort by FPR
        roc.sort(key=lambda p: p["fpr"])

        auc = 0.0
        for i in range(1, len(roc)):
            dx = roc[i]["fpr"] - roc[i-1]["fpr"]
            avg_y = (roc[i]["tpr"] + roc[i-1]["tpr"]) / 2
            auc += dx * avg_y

        return auc


# =============================================================================
# F-Beta Score Optimization
# =============================================================================

class FBetaOptimizer:
    """Optimizes threshold to maximize F-beta score."""

    def __init__(self, beta: float = 1.0):
        """
        Args:
            beta: F-beta parameter.
                  beta > 1 weights recall higher (prefer answering).
                  beta < 1 weights precision higher (prefer accuracy).
        """
        self.beta = beta

    def optimize(self, scores: list[float], labels: list[bool],
                 n_thresholds: int = 200) -> ThresholdSearchResult:
        """Find threshold that maximizes F-beta score."""
        computer = PrecisionRecallComputer()
        best_threshold = 0.5
        best_fbeta = 0.0
        all_results = []

        for i in range(n_thresholds + 1):
            threshold = i / n_thresholds
            perf = computer._evaluate_at_threshold(scores, labels, threshold, self.beta)
            perf.f_beta = self._compute_fbeta(perf.precision, perf.recall)
            all_results.append(perf)

            if perf.f_beta > best_fbeta:
                best_fbeta = perf.f_beta
                best_threshold = threshold

        return ThresholdSearchResult(
            optimal_threshold=best_threshold,
            objective_value=best_fbeta,
            objective_name=f"F_{self.beta:.1f}",
            all_thresholds=all_results,
            search_method="grid_search",
            domain="general",
        )

    def _compute_fbeta(self, precision: float, recall: float) -> float:
        """Compute F-beta score."""
        beta_sq = self.beta * self.beta
        denom = beta_sq * precision + recall
        if denom == 0:
            return 0.0
        return (1 + beta_sq) * precision * recall / denom


# =============================================================================
# Cost-Sensitive Threshold Optimization
# =============================================================================

class CostSensitiveOptimizer:
    """Optimizes threshold to minimize expected cost."""

    def __init__(self, cost_config: CostConfig):
        self.cost_config = cost_config

    def optimize(self, scores: list[float], labels: list[bool],
                 n_thresholds: int = 200) -> ThresholdSearchResult:
        """Find threshold that minimizes total cost."""
        best_threshold = 0.5
        best_cost = float('inf')
        all_results = []

        for i in range(n_thresholds + 1):
            threshold = i / n_thresholds
            cost, perf = self._compute_cost_at_threshold(scores, labels, threshold)
            perf.total_cost = cost
            all_results.append(perf)

            if cost < best_cost:
                best_cost = cost
                best_threshold = threshold

        return ThresholdSearchResult(
            optimal_threshold=best_threshold,
            objective_value=best_cost,
            objective_name="total_cost",
            all_thresholds=all_results,
            search_method="cost_sensitive_grid",
            domain="general",
        )

    def _compute_cost_at_threshold(self, scores: list[float], labels: list[bool],
                                   threshold: float) -> tuple[float, ThresholdPerformance]:
        """Compute total cost at a given threshold."""
        computer = PrecisionRecallComputer()
        perf = computer._evaluate_at_threshold(scores, labels, threshold)

        total_cost = (
            self.cost_config.cost_true_positive * perf.true_positives +
            self.cost_config.cost_false_positive * perf.false_positives +
            self.cost_config.cost_true_negative * perf.true_negatives +
            self.cost_config.cost_false_negative * perf.false_negatives
        )

        return total_cost, perf


# =============================================================================
# Domain-Specific Threshold Discovery
# =============================================================================

class DomainThresholdDiscovery:
    """Discovers optimal thresholds per domain."""

    DOMAIN_PRESETS = {
        "medical": {"beta": 0.3, "cost_fp": 50.0, "cost_fn": 5.0, "min_precision": 0.95},
        "financial": {"beta": 0.5, "cost_fp": 30.0, "cost_fn": 8.0, "min_precision": 0.90},
        "legal": {"beta": 0.4, "cost_fp": 40.0, "cost_fn": 6.0, "min_precision": 0.92},
        "general": {"beta": 1.0, "cost_fp": 10.0, "cost_fn": 5.0, "min_precision": 0.80},
        "creative": {"beta": 2.0, "cost_fp": 3.0, "cost_fn": 10.0, "min_precision": 0.60},
    }

    def discover(self, domain: str, scores: list[float], labels: list[bool]) -> dict:
        """Discover optimal thresholds for a domain."""
        preset = self.DOMAIN_PRESETS.get(domain, self.DOMAIN_PRESETS["general"])

        # F-beta optimization
        fbeta_opt = FBetaOptimizer(beta=preset["beta"])
        fbeta_result = fbeta_opt.optimize(scores, labels)

        # Cost-sensitive optimization
        cost_config = CostConfig(
            cost_false_positive=preset["cost_fp"],
            cost_false_negative=preset["cost_fn"],
        )
        cost_opt = CostSensitiveOptimizer(cost_config)
        cost_result = cost_opt.optimize(scores, labels)

        # Precision-constrained (find highest recall with precision >= min)
        precision_constrained = self._find_precision_constrained(
            scores, labels, preset["min_precision"]
        )

        # Multi-threshold discovery for action levels
        action_thresholds = self._discover_action_thresholds(scores, labels, preset)

        return {
            "domain": domain,
            "fbeta_threshold": fbeta_result.optimal_threshold,
            "fbeta_score": fbeta_result.objective_value,
            "cost_optimal_threshold": cost_result.optimal_threshold,
            "cost_optimal_value": cost_result.objective_value,
            "precision_constrained_threshold": precision_constrained,
            "action_thresholds": action_thresholds,
            "preset": preset,
        }

    def _find_precision_constrained(self, scores: list[float], labels: list[bool],
                                    min_precision: float) -> float:
        """Find lowest threshold that achieves minimum precision."""
        computer = PrecisionRecallComputer()
        curve = computer.compute_curve(scores, labels, n_thresholds=200)

        # Find lowest threshold with precision >= min
        valid = [p for p in curve if p.precision >= min_precision and p.recall > 0]
        if valid:
            # Lowest threshold that meets precision constraint = highest recall
            return min(p.threshold for p in valid)
        return 0.95  # Very conservative fallback

    def _discover_action_thresholds(self, scores: list[float], labels: list[bool],
                                    preset: dict) -> dict:
        """Discover thresholds for each action level (answer, caveat, clarify, abstain)."""
        computer = PrecisionRecallComputer()
        curve = computer.compute_curve(scores, labels, n_thresholds=200)

        # Answer threshold: where precision >= min_precision
        answer_candidates = [p for p in curve if p.precision >= preset["min_precision"]]
        answer_threshold = min(p.threshold for p in answer_candidates) if answer_candidates else 0.90

        # Caveat threshold: where precision >= 0.7 * min_precision
        caveat_min = preset["min_precision"] * 0.7
        caveat_candidates = [p for p in curve if p.precision >= caveat_min]
        caveat_threshold = min(p.threshold for p in caveat_candidates) if caveat_candidates else 0.70

        # Clarify threshold: where precision >= 0.5 * min_precision
        clarify_min = preset["min_precision"] * 0.5
        clarify_candidates = [p for p in curve if p.precision >= clarify_min]
        clarify_threshold = min(p.threshold for p in clarify_candidates) if clarify_candidates else 0.50

        return {
            "answer": answer_threshold,
            "caveat": caveat_threshold,
            "clarify": clarify_threshold,
            "abstain": clarify_threshold * 0.6,
        }


# =============================================================================
# Multi-Class Threshold Tuning
# =============================================================================

class MultiClassThresholdTuner:
    """
    Tunes thresholds for multi-class confidence scenarios where actions
    form an ordered hierarchy: answer > caveat > clarify > abstain.
    """

    def __init__(self):
        self.action_order = ["answer", "caveat", "clarify", "abstain"]

    def tune(self, scores: list[float], labels: list[bool],
             target_rates: dict = None) -> dict:
        """
        Tune multiple thresholds simultaneously.
        
        Args:
            target_rates: Desired rate for each action, e.g.,
                         {"answer": 0.60, "caveat": 0.20, "clarify": 0.15, "abstain": 0.05}
        """
        if target_rates is None:
            target_rates = {"answer": 0.55, "caveat": 0.25, "clarify": 0.15, "abstain": 0.05}

        sorted_scores = sorted(scores, reverse=True)
        n = len(sorted_scores)

        # Compute thresholds from target rates (quantile-based)
        cumulative = 0.0
        thresholds = {}
        for action in self.action_order[:-1]:  # No threshold for abstain (it's the rest)
            cumulative += target_rates.get(action, 0.25)
            idx = min(int(cumulative * n), n - 1)
            thresholds[action] = sorted_scores[idx] if idx < n else 0.0

        # Validate monotonicity
        prev = 1.0
        for action in self.action_order[:-1]:
            thresholds[action] = min(prev, thresholds[action])
            prev = thresholds[action]

        # Evaluate quality at each threshold
        metrics = self._evaluate_multi_threshold(scores, labels, thresholds)

        return {
            "thresholds": thresholds,
            "metrics": metrics,
            "target_rates": target_rates,
            "actual_rates": self._compute_actual_rates(scores, thresholds),
        }

    def _evaluate_multi_threshold(self, scores: list[float], labels: list[bool],
                                  thresholds: dict) -> dict:
        """Evaluate accuracy within each action band."""
        bands = defaultdict(lambda: {"correct": 0, "total": 0})

        for score, label in zip(scores, labels):
            action = self._classify_action(score, thresholds)
            bands[action]["total"] += 1
            if label:
                bands[action]["correct"] += 1

        metrics = {}
        for action, data in bands.items():
            metrics[action] = {
                "accuracy": data["correct"] / data["total"] if data["total"] > 0 else 0.0,
                "count": data["total"],
                "fraction": data["total"] / len(scores),
            }
        return metrics

    def _classify_action(self, score: float, thresholds: dict) -> str:
        """Classify a score into an action based on thresholds."""
        if score >= thresholds.get("answer", 0.85):
            return "answer"
        elif score >= thresholds.get("caveat", 0.60):
            return "caveat"
        elif score >= thresholds.get("clarify", 0.35):
            return "clarify"
        return "abstain"

    def _compute_actual_rates(self, scores: list[float], thresholds: dict) -> dict:
        """Compute actual rate of each action."""
        counts = defaultdict(int)
        for score in scores:
            action = self._classify_action(score, thresholds)
            counts[action] += 1
        n = len(scores)
        return {action: count / n for action, count in counts.items()}


# =============================================================================
# Threshold Stability Analysis
# =============================================================================

class ThresholdStabilityAnalyzer:
    """Analyzes how stable optimal thresholds are across data subsets."""

    def __init__(self, n_bootstrap: int = 100):
        self.n_bootstrap = n_bootstrap

    def analyze(self, scores: list[float], labels: list[bool],
                optimizer_fn=None, beta: float = 1.0) -> dict:
        """
        Bootstrap analysis of threshold stability.
        
        Returns distribution of optimal thresholds across resampled datasets.
        """
        if optimizer_fn is None:
            optimizer_fn = lambda s, l: FBetaOptimizer(beta).optimize(s, l).optimal_threshold

        n = len(scores)
        threshold_samples = []

        for _ in range(self.n_bootstrap):
            # Bootstrap resample
            indices = [random.randint(0, n - 1) for _ in range(n)]
            boot_scores = [scores[i] for i in indices]
            boot_labels = [labels[i] for i in indices]

            threshold = optimizer_fn(boot_scores, boot_labels)
            threshold_samples.append(threshold)

        threshold_samples.sort()
        mean_t = sum(threshold_samples) / len(threshold_samples)
        std_t = (sum((t - mean_t)**2 for t in threshold_samples) / len(threshold_samples)) ** 0.5

        return {
            "mean_threshold": mean_t,
            "std_threshold": std_t,
            "ci_95_lower": threshold_samples[int(0.025 * self.n_bootstrap)],
            "ci_95_upper": threshold_samples[int(0.975 * self.n_bootstrap)],
            "cv": std_t / mean_t if mean_t > 0 else float('inf'),
            "is_stable": std_t < 0.05,  # Threshold is stable if std < 5%
            "n_bootstrap": self.n_bootstrap,
            "all_samples": threshold_samples,
        }


# =============================================================================
# Production Threshold Monitor
# =============================================================================

class ThresholdMonitor:
    """Monitors threshold performance in production and alerts on degradation."""

    def __init__(self, thresholds: dict, alert_callback=None):
        """
        Args:
            thresholds: Current production thresholds {"answer": 0.85, ...}
            alert_callback: Function to call when degradation detected
        """
        self.thresholds = thresholds
        self.alert_callback = alert_callback or (lambda msg: logger.warning(msg))
        self.window: list[dict] = []
        self.window_size = 1000
        self.baseline_metrics: Optional[dict] = None
        self.alerts: list[dict] = []

    def record(self, confidence_score: float, was_correct: bool, action_taken: str):
        """Record a production observation."""
        self.window.append({
            "score": confidence_score,
            "correct": was_correct,
            "action": action_taken,
            "timestamp": time.time(),
        })
        if len(self.window) > self.window_size * 2:
            self.window = self.window[-self.window_size:]

        # Periodic check
        if len(self.window) % 100 == 0:
            self._check_performance()

    def set_baseline(self, metrics: dict):
        """Set baseline performance metrics for comparison."""
        self.baseline_metrics = metrics

    def _check_performance(self):
        """Check if current performance has degraded."""
        if len(self.window) < 200:
            return

        recent = self.window[-500:]
        metrics = self._compute_metrics(recent)

        if self.baseline_metrics:
            self._compare_to_baseline(metrics)

        # Check absolute thresholds
        if metrics.get("answer_precision", 1.0) < 0.75:
            self._raise_alert(
                "CRITICAL: Answer precision dropped below 75%",
                metrics
            )

        # Check action distribution shift
        answer_rate = metrics.get("answer_rate", 0)
        if answer_rate < 0.2:
            self._raise_alert(
                f"WARNING: Answer rate very low ({answer_rate:.1%}), system may be too conservative",
                metrics
            )
        elif answer_rate > 0.9:
            self._raise_alert(
                f"WARNING: Answer rate very high ({answer_rate:.1%}), system may be too aggressive",
                metrics
            )

    def _compute_metrics(self, observations: list[dict]) -> dict:
        """Compute performance metrics from observations."""
        n = len(observations)
        by_action = defaultdict(list)
        for obs in observations:
            by_action[obs["action"]].append(obs["correct"])

        metrics = {}
        for action, outcomes in by_action.items():
            metrics[f"{action}_precision"] = sum(outcomes) / len(outcomes) if outcomes else 0
            metrics[f"{action}_count"] = len(outcomes)
            metrics[f"{action}_rate"] = len(outcomes) / n

        # Overall
        metrics["overall_accuracy"] = sum(o["correct"] for o in observations) / n
        metrics["answer_rate"] = metrics.get("answer_rate", 0)
        metrics["abstain_rate"] = metrics.get("abstain_rate", 0)

        return metrics

    def _compare_to_baseline(self, current: dict):
        """Compare current metrics to baseline."""
        for key, baseline_value in self.baseline_metrics.items():
            if key.endswith("_precision") and key in current:
                drop = baseline_value - current[key]
                if drop > 0.10:  # 10% precision drop
                    self._raise_alert(
                        f"DEGRADATION: {key} dropped by {drop:.1%} from baseline",
                        {"current": current[key], "baseline": baseline_value}
                    )

    def _raise_alert(self, message: str, context: dict):
        """Raise a performance alert."""
        alert = {
            "message": message,
            "context": context,
            "timestamp": time.time(),
        }
        self.alerts.append(alert)
        self.alert_callback(message)

    def get_status(self) -> dict:
        """Get current monitoring status."""
        metrics = self._compute_metrics(self.window[-500:]) if len(self.window) >= 200 else {}
        return {
            "window_size": len(self.window),
            "current_thresholds": self.thresholds,
            "current_metrics": metrics,
            "recent_alerts": self.alerts[-5:],
            "alert_count": len(self.alerts),
        }


# =============================================================================
# Threshold Recommendation Engine
# =============================================================================

class ThresholdRecommender:
    """Provides threshold recommendations based on multiple optimization criteria."""

    def recommend(self, scores: list[float], labels: list[bool],
                  domain: str = "general") -> dict:
        """Generate comprehensive threshold recommendations."""
        # Run all optimizers
        domain_discovery = DomainThresholdDiscovery()
        domain_result = domain_discovery.discover(domain, scores, labels)

        # Stability analysis
        stability = ThresholdStabilityAnalyzer(n_bootstrap=50)
        stability_result = stability.analyze(scores, labels)

        # Multi-class tuning
        multi_tuner = MultiClassThresholdTuner()
        multi_result = multi_tuner.tune(scores, labels)

        # AUC for overall quality assessment
        pr_computer = PrecisionRecallComputer()
        auc = pr_computer.compute_auc(scores, labels)

        return {
            "domain": domain,
            "recommended_thresholds": domain_result["action_thresholds"],
            "fbeta_optimal": domain_result["fbeta_threshold"],
            "cost_optimal": domain_result["cost_optimal_threshold"],
            "stability": {
                "is_stable": stability_result["is_stable"],
                "std": stability_result["std_threshold"],
                "ci_95": (stability_result["ci_95_lower"], stability_result["ci_95_upper"]),
            },
            "multi_class": multi_result,
            "auc_roc": auc,
            "quality_assessment": self._assess_quality(auc, stability_result),
        }

    def _assess_quality(self, auc: float, stability: dict) -> str:
        """Assess overall quality of the confidence scoring system."""
        if auc >= 0.9 and stability["is_stable"]:
            return "EXCELLENT: High discrimination and stable thresholds"
        elif auc >= 0.8:
            return "GOOD: Adequate discrimination, consider more calibration data"
        elif auc >= 0.7:
            return "FAIR: Moderate discrimination, review signal quality"
        else:
            return "POOR: Low discrimination, confidence signals need improvement"


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    random.seed(42)

    # Generate synthetic data: scores and ground truth correctness
    n_samples = 2000
    scores = []
    labels = []
    for _ in range(n_samples):
        score = random.betavariate(2.5, 2)
        # Higher scores correlate with correctness, but imperfectly
        p_correct = 0.3 + 0.6 * score + random.gauss(0, 0.1)
        p_correct = max(0, min(1, p_correct))
        correct = random.random() < p_correct
        scores.append(score)
        labels.append(correct)

    print("=" * 60)
    print("THRESHOLD TUNING ANALYSIS")
    print("=" * 60)

    # 1. Precision-Recall Curve
    pr = PrecisionRecallComputer()
    auc = pr.compute_auc(scores, labels)
    print(f"\nROC-AUC: {auc:.4f}")

    # 2. F1 optimization
    f1_opt = FBetaOptimizer(beta=1.0)
    f1_result = f1_opt.optimize(scores, labels)
    print(f"\nF1-optimal threshold: {f1_result.optimal_threshold:.3f} (F1={f1_result.objective_value:.3f})")

    # 3. Precision-focused (medical)
    f03_opt = FBetaOptimizer(beta=0.3)
    f03_result = f03_opt.optimize(scores, labels)
    print(f"F0.3-optimal (precision-focused): {f03_result.optimal_threshold:.3f}")

    # 4. Recall-focused (customer service)
    f2_opt = FBetaOptimizer(beta=2.0)
    f2_result = f2_opt.optimize(scores, labels)
    print(f"F2-optimal (recall-focused): {f2_result.optimal_threshold:.3f}")

    # 5. Cost-sensitive
    cost_cfg = CostConfig(cost_false_positive=20.0, cost_false_negative=5.0)
    cost_opt = CostSensitiveOptimizer(cost_cfg)
    cost_result = cost_opt.optimize(scores, labels)
    print(f"\nCost-optimal threshold: {cost_result.optimal_threshold:.3f} (cost={cost_result.objective_value:.1f})")

    # 6. Domain-specific discovery
    print("\n--- Domain-Specific Thresholds ---")
    discovery = DomainThresholdDiscovery()
    for domain in ["medical", "financial", "legal", "general", "creative"]:
        result = discovery.discover(domain, scores, labels)
        thresholds = result["action_thresholds"]
        print(f"  {domain:12s}: answer={thresholds['answer']:.2f} caveat={thresholds['caveat']:.2f} "
              f"clarify={thresholds['clarify']:.2f} abstain={thresholds['abstain']:.2f}")

    # 7. Stability analysis
    print("\n--- Threshold Stability ---")
    analyzer = ThresholdStabilityAnalyzer(n_bootstrap=50)
    stability = analyzer.analyze(scores, labels)
    print(f"  Mean threshold: {stability['mean_threshold']:.3f} ± {stability['std_threshold']:.3f}")
    print(f"  95% CI: [{stability['ci_95_lower']:.3f}, {stability['ci_95_upper']:.3f}]")
    print(f"  Stable: {stability['is_stable']}")

    # 8. Full recommendation
    print("\n--- Recommendation ---")
    recommender = ThresholdRecommender()
    rec = recommender.recommend(scores, labels, domain="general")
    print(f"  Quality: {rec['quality_assessment']}")
    print(f"  Recommended: {rec['recommended_thresholds']}")
