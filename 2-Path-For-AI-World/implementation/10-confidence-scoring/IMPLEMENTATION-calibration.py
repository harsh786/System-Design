"""
Calibration System for Confidence Scores

Implements Platt scaling, isotonic regression, temperature scaling,
calibration metrics (ECE, Brier score), reliability diagrams, and
automated recalibration with drift detection.
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
class CalibrationDataPoint:
    """A single calibration data point: predicted confidence + actual outcome."""
    predicted_score: float  # Raw composite confidence [0, 1]
    actual_outcome: bool  # Was the answer correct?
    timestamp: float = field(default_factory=time.time)
    query_hash: str = ""
    domain: str = "general"
    metadata: dict = field(default_factory=dict)


@dataclass
class CalibrationMetrics:
    """Calibration quality metrics."""
    brier_score: float
    expected_calibration_error: float
    maximum_calibration_error: float
    mean_confidence: float
    mean_accuracy: float
    overconfidence_ratio: float  # Fraction of bins where confidence > accuracy
    n_samples: int
    reliability_bins: list  # For reliability diagram
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# Platt Scaling
# =============================================================================

class PlattScaling:
    """
    Platt scaling: fits a logistic regression on raw scores to produce
    calibrated probabilities.
    
    P(correct | score) = sigmoid(a * score + b)
    
    Parameters a, b are learned via maximum likelihood on validation data.
    """

    def __init__(self):
        self.a: float = 1.0  # Scale
        self.b: float = 0.0  # Shift
        self.fitted: bool = False

    def fit(self, scores: list[float], outcomes: list[bool],
            lr: float = 0.01, max_iter: int = 10000, tol: float = 1e-7):
        """
        Fit Platt scaling parameters using gradient descent on negative log-likelihood.
        
        Uses the improved Platt method with target probabilities to avoid overfitting:
        - t+ = (N+ + 1) / (N+ + 2) for positive examples
        - t- = 1 / (N- + 2) for negative examples
        """
        n = len(scores)
        if n < 10:
            logger.warning("Too few samples for Platt scaling (need >= 10)")
            return

        # Compute Platt targets (avoids 0/1 targets)
        n_pos = sum(outcomes)
        n_neg = n - n_pos
        t_pos = (n_pos + 1) / (n_pos + 2)
        t_neg = 1.0 / (n_neg + 2)
        targets = [t_pos if o else t_neg for o in outcomes]

        # Gradient descent on NLL
        a, b = 0.0, 0.0  # Start from identity-ish
        prev_loss = float('inf')

        for iteration in range(max_iter):
            # Forward pass
            loss = 0.0
            grad_a = 0.0
            grad_b = 0.0

            for i in range(n):
                z = a * scores[i] + b
                p = self._sigmoid(z)
                # Clamp to avoid log(0)
                p = max(1e-10, min(1 - 1e-10, p))
                t = targets[i]

                loss += -(t * math.log(p) + (1 - t) * math.log(1 - p))
                grad_a += (p - t) * scores[i]
                grad_b += (p - t)

            loss /= n
            grad_a /= n
            grad_b /= n

            # Update
            a -= lr * grad_a
            b -= lr * grad_b

            # Convergence check
            if abs(prev_loss - loss) < tol:
                logger.info(f"Platt scaling converged at iteration {iteration}")
                break
            prev_loss = loss

        self.a = a
        self.b = b
        self.fitted = True
        logger.info(f"Platt scaling fitted: a={a:.4f}, b={b:.4f}")

    def calibrate(self, raw_score: float) -> float:
        """Apply Platt scaling to a raw score."""
        if not self.fitted:
            return raw_score
        z = self.a * raw_score + self.b
        return self._sigmoid(z)

    def _sigmoid(self, z: float) -> float:
        """Numerically stable sigmoid."""
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        else:
            ez = math.exp(z)
            return ez / (1.0 + ez)

    def __call__(self, score: float) -> float:
        return self.calibrate(score)


# =============================================================================
# Isotonic Regression
# =============================================================================

class IsotonicRegression:
    """
    Isotonic regression for calibration using the Pool Adjacent Violators (PAV) algorithm.
    
    Fits a monotonically non-decreasing step function that minimizes
    squared error between predicted and actual outcomes.
    """

    def __init__(self):
        self.thresholds: list[float] = []  # Score boundaries
        self.values: list[float] = []  # Calibrated values for each segment
        self.fitted: bool = False

    def fit(self, scores: list[float], outcomes: list[bool]):
        """Fit isotonic regression using PAV algorithm."""
        n = len(scores)
        if n < 20:
            logger.warning("Too few samples for isotonic regression (need >= 20)")
            return

        # Sort by score
        pairs = sorted(zip(scores, [float(o) for o in outcomes]))
        sorted_scores = [p[0] for p in pairs]
        sorted_outcomes = [p[1] for p in pairs]

        # Pool Adjacent Violators
        blocks = [[sorted_outcomes[i]] for i in range(n)]
        block_scores = [[sorted_scores[i]] for i in range(n)]

        # Merge adjacent blocks that violate monotonicity
        i = 0
        while i < len(blocks) - 1:
            mean_current = sum(blocks[i]) / len(blocks[i])
            mean_next = sum(blocks[i + 1]) / len(blocks[i + 1])

            if mean_current > mean_next:
                # Merge blocks
                blocks[i] = blocks[i] + blocks[i + 1]
                block_scores[i] = block_scores[i] + block_scores[i + 1]
                blocks.pop(i + 1)
                block_scores.pop(i + 1)
                # Go back to check previous block
                if i > 0:
                    i -= 1
            else:
                i += 1

        # Extract thresholds and values
        self.thresholds = []
        self.values = []
        for block, bscores in zip(blocks, block_scores):
            mean_value = sum(block) / len(block)
            min_score = min(bscores)
            max_score = max(bscores)
            self.thresholds.append((min_score, max_score))
            self.values.append(mean_value)

        self.fitted = True
        logger.info(f"Isotonic regression fitted with {len(self.values)} segments")

    def calibrate(self, raw_score: float) -> float:
        """Apply isotonic regression calibration."""
        if not self.fitted:
            return raw_score

        # Find the appropriate segment
        for i, (low, high) in enumerate(self.thresholds):
            if raw_score <= high:
                return self.values[i]

        # Above all thresholds
        return self.values[-1] if self.values else raw_score

    def __call__(self, score: float) -> float:
        return self.calibrate(score)


# =============================================================================
# Temperature Scaling
# =============================================================================

class TemperatureScaling:
    """
    Temperature scaling for LLM logits.
    
    Divides logits by temperature T before softmax to adjust confidence.
    T > 1: reduces overconfidence (softer distribution)
    T < 1: increases confidence (sharper distribution)
    """

    def __init__(self):
        self.temperature: float = 1.0
        self.fitted: bool = False

    def fit(self, logits_list: list[list[float]], labels: list[int],
            lr: float = 0.01, max_iter: int = 1000, tol: float = 1e-6):
        """
        Fit temperature parameter to minimize negative log-likelihood on validation set.
        
        Args:
            logits_list: List of logit vectors (one per sample)
            labels: Correct class index for each sample
        """
        n = len(logits_list)
        if n < 10:
            logger.warning("Too few samples for temperature scaling")
            return

        T = 1.0
        prev_loss = float('inf')

        for iteration in range(max_iter):
            loss = 0.0
            grad = 0.0

            for i in range(n):
                logits = logits_list[i]
                label = labels[i]

                # Softmax with temperature
                scaled = [l / T for l in logits]
                max_l = max(scaled)
                exps = [math.exp(l - max_l) for l in scaled]
                sum_exps = sum(exps)
                probs = [e / sum_exps for e in exps]

                # NLL
                p_correct = max(1e-10, probs[label])
                loss += -math.log(p_correct)

                # Gradient of NLL w.r.t. T
                # d/dT = (1/T^2) * (logits[label] - sum(probs * logits))
                expected_logit = sum(p * l for p, l in zip(probs, logits))
                grad += (1.0 / (T * T)) * (expected_logit - logits[label])

            loss /= n
            grad /= n

            # Update T (must stay positive)
            T = max(0.01, T - lr * grad)

            if abs(prev_loss - loss) < tol:
                logger.info(f"Temperature scaling converged at iteration {iteration}")
                break
            prev_loss = loss

        self.temperature = T
        self.fitted = True
        logger.info(f"Temperature scaling fitted: T={T:.4f}")

    def calibrate_logits(self, logits: list[float]) -> list[float]:
        """Apply temperature scaling to logits and return probabilities."""
        scaled = [l / self.temperature for l in logits]
        max_l = max(scaled)
        exps = [math.exp(l - max_l) for l in scaled]
        sum_exps = sum(exps)
        return [e / sum_exps for e in exps]

    def calibrate_confidence(self, confidence: float) -> float:
        """
        Apply temperature-like scaling to a single confidence score.
        Maps confidence through a power function parameterized by T.
        """
        if not self.fitted:
            return confidence
        # For single scores: use power scaling as analog
        # confidence^(1/T) when T > 1 reduces confidence
        if confidence <= 0 or confidence >= 1:
            return confidence
        return confidence ** (1.0 / self.temperature)


# =============================================================================
# Calibration Metrics
# =============================================================================

class CalibrationEvaluator:
    """Computes calibration quality metrics."""

    def __init__(self, n_bins: int = 10):
        self.n_bins = n_bins

    def evaluate(self, predictions: list[float], outcomes: list[bool]) -> CalibrationMetrics:
        """Compute all calibration metrics."""
        n = len(predictions)
        if n == 0:
            raise ValueError("No data for calibration evaluation")

        brier = self._brier_score(predictions, outcomes)
        bins = self._compute_bins(predictions, outcomes)
        ece = self._ece_from_bins(bins, n)
        mce = self._mce_from_bins(bins)

        mean_conf = sum(predictions) / n
        mean_acc = sum(outcomes) / n
        overconf = sum(1 for b in bins if b["avg_confidence"] > b["accuracy"] and b["count"] > 0)
        overconf_ratio = overconf / max(1, sum(1 for b in bins if b["count"] > 0))

        return CalibrationMetrics(
            brier_score=brier,
            expected_calibration_error=ece,
            maximum_calibration_error=mce,
            mean_confidence=mean_conf,
            mean_accuracy=mean_acc,
            overconfidence_ratio=overconf_ratio,
            n_samples=n,
            reliability_bins=bins,
        )

    def _brier_score(self, predictions: list[float], outcomes: list[bool]) -> float:
        """Brier score: mean squared error between predicted prob and outcome."""
        n = len(predictions)
        return sum((p - (1.0 if o else 0.0)) ** 2 for p, o in zip(predictions, outcomes)) / n

    def _compute_bins(self, predictions: list[float], outcomes: list[bool]) -> list[dict]:
        """Bin predictions and compute per-bin statistics."""
        bins = [{"predictions": [], "outcomes": []} for _ in range(self.n_bins)]

        for pred, outcome in zip(predictions, outcomes):
            bin_idx = min(int(pred * self.n_bins), self.n_bins - 1)
            bins[bin_idx]["predictions"].append(pred)
            bins[bin_idx]["outcomes"].append(outcome)

        result = []
        for i, b in enumerate(bins):
            count = len(b["predictions"])
            if count > 0:
                avg_conf = sum(b["predictions"]) / count
                accuracy = sum(b["outcomes"]) / count
                cal_error = abs(accuracy - avg_conf)
            else:
                avg_conf = (i + 0.5) / self.n_bins
                accuracy = 0.0
                cal_error = 0.0

            result.append({
                "bin_lower": i / self.n_bins,
                "bin_upper": (i + 1) / self.n_bins,
                "avg_confidence": avg_conf,
                "accuracy": accuracy,
                "calibration_error": cal_error,
                "count": count,
            })

        return result

    def _ece_from_bins(self, bins: list[dict], n: int) -> float:
        """Expected Calibration Error from pre-computed bins."""
        if n == 0:
            return 0.0
        return sum(b["count"] / n * b["calibration_error"] for b in bins)

    def _mce_from_bins(self, bins: list[dict]) -> float:
        """Maximum Calibration Error."""
        errors = [b["calibration_error"] for b in bins if b["count"] > 0]
        return max(errors) if errors else 0.0

    def generate_reliability_diagram_data(self, predictions: list[float],
                                          outcomes: list[bool]) -> dict:
        """Generate data for plotting a reliability diagram."""
        bins = self._compute_bins(predictions, outcomes)
        return {
            "bin_centers": [(b["bin_lower"] + b["bin_upper"]) / 2 for b in bins],
            "accuracies": [b["accuracy"] for b in bins],
            "confidences": [b["avg_confidence"] for b in bins],
            "counts": [b["count"] for b in bins],
            "perfect_calibration": [(b["bin_lower"] + b["bin_upper"]) / 2 for b in bins],
            "ece": self._ece_from_bins(bins, sum(b["count"] for b in bins)),
        }


# =============================================================================
# Calibration Drift Detection
# =============================================================================

class CalibrationDriftDetector:
    """Monitors calibration quality over time and detects drift."""

    def __init__(self, window_size: int = 500, ece_threshold: float = 0.05,
                 check_interval: int = 100):
        self.window_size = window_size
        self.ece_threshold = ece_threshold
        self.check_interval = check_interval
        self.buffer: list[CalibrationDataPoint] = []
        self.baseline_ece: Optional[float] = None
        self.evaluator = CalibrationEvaluator()
        self.drift_history: list[dict] = []
        self._counter = 0

    def add_observation(self, data_point: CalibrationDataPoint) -> Optional[dict]:
        """Add observation and check for drift. Returns alert dict if drift detected."""
        self.buffer.append(data_point)
        if len(self.buffer) > self.window_size * 2:
            self.buffer = self.buffer[-self.window_size:]

        self._counter += 1
        if self._counter % self.check_interval == 0:
            return self._check_drift()
        return None

    def set_baseline(self, predictions: list[float], outcomes: list[bool]):
        """Set baseline calibration from initial deployment data."""
        metrics = self.evaluator.evaluate(predictions, outcomes)
        self.baseline_ece = metrics.expected_calibration_error
        logger.info(f"Calibration baseline set: ECE={self.baseline_ece:.4f}")

    def _check_drift(self) -> Optional[dict]:
        """Check if current calibration has drifted from baseline."""
        if len(self.buffer) < self.window_size:
            return None

        recent = self.buffer[-self.window_size:]
        predictions = [dp.predicted_score for dp in recent]
        outcomes = [dp.actual_outcome for dp in recent]

        current_metrics = self.evaluator.evaluate(predictions, outcomes)
        current_ece = current_metrics.expected_calibration_error

        drift_detected = False
        if self.baseline_ece is not None:
            drift = current_ece - self.baseline_ece
            if drift > self.ece_threshold:
                drift_detected = True
        elif current_ece > self.ece_threshold:
            drift_detected = True

        result = {
            "timestamp": time.time(),
            "current_ece": current_ece,
            "baseline_ece": self.baseline_ece,
            "drift_detected": drift_detected,
            "brier_score": current_metrics.brier_score,
            "n_samples": len(recent),
        }

        self.drift_history.append(result)

        if drift_detected:
            logger.warning(
                f"CALIBRATION DRIFT DETECTED: ECE={current_ece:.4f} "
                f"(baseline={self.baseline_ece:.4f})"
            )

        return result if drift_detected else None


# =============================================================================
# Automated Recalibration
# =============================================================================

class AutoRecalibrator:
    """
    Automatically recalibrates the confidence scoring system when drift is detected.
    Supports multiple calibration methods and cross-validation.
    """

    def __init__(self, min_samples: int = 200, cv_folds: int = 5):
        self.min_samples = min_samples
        self.cv_folds = cv_folds
        self.calibration_history: list[dict] = []

    def recalibrate(self, data: list[CalibrationDataPoint],
                    method: str = "auto") -> dict:
        """
        Recalibrate using the specified method.
        
        Args:
            data: Calibration data points
            method: "platt", "isotonic", or "auto" (best of both via CV)
        
        Returns:
            Dict with calibrator object and evaluation metrics
        """
        if len(data) < self.min_samples:
            logger.warning(f"Insufficient data for recalibration ({len(data)} < {self.min_samples})")
            return {"success": False, "reason": "insufficient_data"}

        predictions = [dp.predicted_score for dp in data]
        outcomes = [dp.actual_outcome for dp in data]

        if method == "auto":
            return self._auto_select(predictions, outcomes)
        elif method == "platt":
            return self._fit_platt(predictions, outcomes)
        elif method == "isotonic":
            return self._fit_isotonic(predictions, outcomes)
        else:
            raise ValueError(f"Unknown method: {method}")

    def _auto_select(self, predictions: list[float], outcomes: list[bool]) -> dict:
        """Select best calibration method via cross-validation."""
        platt_scores = self._cross_validate(predictions, outcomes, "platt")
        isotonic_scores = self._cross_validate(predictions, outcomes, "isotonic")

        platt_ece = sum(platt_scores) / len(platt_scores)
        isotonic_ece = sum(isotonic_scores) / len(isotonic_scores)

        best_method = "platt" if platt_ece <= isotonic_ece else "isotonic"
        logger.info(f"Auto-selected {best_method} (Platt ECE={platt_ece:.4f}, Isotonic ECE={isotonic_ece:.4f})")

        if best_method == "platt":
            result = self._fit_platt(predictions, outcomes)
        else:
            result = self._fit_isotonic(predictions, outcomes)

        result["comparison"] = {
            "platt_cv_ece": platt_ece,
            "isotonic_cv_ece": isotonic_ece,
            "selected": best_method,
        }
        return result

    def _cross_validate(self, predictions: list[float], outcomes: list[bool],
                        method: str) -> list[float]:
        """K-fold cross-validation for calibration method."""
        n = len(predictions)
        indices = list(range(n))
        random.shuffle(indices)
        fold_size = n // self.cv_folds

        ece_scores = []
        evaluator = CalibrationEvaluator()

        for fold in range(self.cv_folds):
            val_start = fold * fold_size
            val_end = val_start + fold_size
            val_idx = set(indices[val_start:val_end])
            train_idx = [i for i in range(n) if i not in val_idx]

            train_pred = [predictions[i] for i in train_idx]
            train_out = [outcomes[i] for i in train_idx]
            val_pred = [predictions[i] for i in val_idx]
            val_out = [outcomes[i] for i in val_idx]

            if method == "platt":
                calibrator = PlattScaling()
                calibrator.fit(train_pred, train_out)
            else:
                calibrator = IsotonicRegression()
                calibrator.fit(train_pred, train_out)

            calibrated_val = [calibrator(p) for p in val_pred]
            metrics = evaluator.evaluate(calibrated_val, val_out)
            ece_scores.append(metrics.expected_calibration_error)

        return ece_scores

    def _fit_platt(self, predictions: list[float], outcomes: list[bool]) -> dict:
        """Fit Platt scaling on full dataset."""
        calibrator = PlattScaling()
        calibrator.fit(predictions, outcomes)

        calibrated = [calibrator(p) for p in predictions]
        evaluator = CalibrationEvaluator()
        metrics = evaluator.evaluate(calibrated, outcomes)

        result = {
            "success": True,
            "method": "platt",
            "calibrator": calibrator,
            "metrics": metrics,
            "parameters": {"a": calibrator.a, "b": calibrator.b},
        }
        self.calibration_history.append({
            "timestamp": time.time(),
            "method": "platt",
            "ece_before": evaluator.evaluate(predictions, outcomes).expected_calibration_error,
            "ece_after": metrics.expected_calibration_error,
        })
        return result

    def _fit_isotonic(self, predictions: list[float], outcomes: list[bool]) -> dict:
        """Fit isotonic regression on full dataset."""
        calibrator = IsotonicRegression()
        calibrator.fit(predictions, outcomes)

        calibrated = [calibrator(p) for p in predictions]
        evaluator = CalibrationEvaluator()
        metrics = evaluator.evaluate(calibrated, outcomes)

        result = {
            "success": True,
            "method": "isotonic",
            "calibrator": calibrator,
            "metrics": metrics,
            "parameters": {"n_segments": len(calibrator.values)},
        }
        self.calibration_history.append({
            "timestamp": time.time(),
            "method": "isotonic",
            "ece_before": evaluator.evaluate(predictions, outcomes).expected_calibration_error,
            "ece_after": metrics.expected_calibration_error,
        })
        return result


# =============================================================================
# Production Calibration Pipeline
# =============================================================================

class CalibrationPipeline:
    """
    End-to-end calibration pipeline for production use.
    
    Collects data, monitors drift, triggers recalibration, and swaps calibrators.
    """

    def __init__(self, initial_calibrator=None, drift_threshold: float = 0.05,
                 recalibration_min_samples: int = 500):
        self.current_calibrator = initial_calibrator or (lambda x: x)
        self.drift_detector = CalibrationDriftDetector(ece_threshold=drift_threshold)
        self.recalibrator = AutoRecalibrator(min_samples=recalibration_min_samples)
        self.data_buffer: list[CalibrationDataPoint] = []
        self.max_buffer_size = 10000
        self.recalibration_count = 0

    def calibrate(self, raw_score: float) -> float:
        """Apply current calibration to a raw score."""
        return self.current_calibrator(raw_score)

    def record_outcome(self, raw_score: float, was_correct: bool,
                       query_hash: str = "", domain: str = "general"):
        """Record a prediction outcome for calibration monitoring."""
        dp = CalibrationDataPoint(
            predicted_score=self.current_calibrator(raw_score),
            actual_outcome=was_correct,
            query_hash=query_hash,
            domain=domain,
        )
        self.data_buffer.append(dp)
        if len(self.data_buffer) > self.max_buffer_size:
            self.data_buffer = self.data_buffer[-self.max_buffer_size // 2:]

        # Check for drift
        alert = self.drift_detector.add_observation(dp)
        if alert and alert.get("drift_detected"):
            self._trigger_recalibration()

    def _trigger_recalibration(self):
        """Trigger automatic recalibration."""
        logger.info("Triggering automatic recalibration...")
        result = self.recalibrator.recalibrate(self.data_buffer, method="auto")

        if result.get("success"):
            self.current_calibrator = result["calibrator"]
            self.recalibration_count += 1
            logger.info(
                f"Recalibration #{self.recalibration_count} complete. "
                f"Method: {result['method']}, ECE: {result['metrics'].expected_calibration_error:.4f}"
            )

            # Update baseline
            predictions = [dp.predicted_score for dp in self.data_buffer[-500:]]
            outcomes = [dp.actual_outcome for dp in self.data_buffer[-500:]]
            self.drift_detector.set_baseline(
                [self.current_calibrator(p) for p in predictions], outcomes
            )

    def get_status(self) -> dict:
        """Get current calibration pipeline status."""
        return {
            "buffer_size": len(self.data_buffer),
            "recalibration_count": self.recalibration_count,
            "drift_history": self.drift_detector.drift_history[-10:],
            "calibrator_type": type(self.current_calibrator).__name__,
        }


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Simulate production calibration workflow
    random.seed(42)

    # Generate synthetic calibration data
    # Simulate an overconfident system (predictions higher than actual accuracy)
    data = []
    for _ in range(1000):
        # Raw score tends to be higher than actual correctness
        raw_score = random.betavariate(3, 2)  # Skewed toward high confidence
        # Actual correctness correlates but with noise and overconfidence
        noise = random.gauss(0, 0.15)
        true_prob = max(0, min(1, raw_score * 0.7 + noise))
        outcome = random.random() < true_prob
        data.append(CalibrationDataPoint(
            predicted_score=raw_score,
            actual_outcome=outcome,
        ))

    predictions = [dp.predicted_score for dp in data]
    outcomes = [dp.actual_outcome for dp in data]

    # Evaluate before calibration
    evaluator = CalibrationEvaluator()
    before = evaluator.evaluate(predictions, outcomes)
    print(f"Before calibration:")
    print(f"  Brier Score: {before.brier_score:.4f}")
    print(f"  ECE: {before.expected_calibration_error:.4f}")
    print(f"  MCE: {before.maximum_calibration_error:.4f}")
    print(f"  Overconfidence ratio: {before.overconfidence_ratio:.2f}")

    # Fit Platt scaling
    platt = PlattScaling()
    platt.fit(predictions, outcomes)
    platt_calibrated = [platt(p) for p in predictions]
    after_platt = evaluator.evaluate(platt_calibrated, outcomes)
    print(f"\nAfter Platt scaling:")
    print(f"  Brier Score: {after_platt.brier_score:.4f}")
    print(f"  ECE: {after_platt.expected_calibration_error:.4f}")
    print(f"  Parameters: a={platt.a:.4f}, b={platt.b:.4f}")

    # Fit isotonic regression
    isotonic = IsotonicRegression()
    isotonic.fit(predictions, outcomes)
    iso_calibrated = [isotonic(p) for p in predictions]
    after_iso = evaluator.evaluate(iso_calibrated, outcomes)
    print(f"\nAfter isotonic regression:")
    print(f"  Brier Score: {after_iso.brier_score:.4f}")
    print(f"  ECE: {after_iso.expected_calibration_error:.4f}")
    print(f"  Segments: {len(isotonic.values)}")

    # Auto-select best
    recalibrator = AutoRecalibrator()
    result = recalibrator.recalibrate(data, method="auto")
    print(f"\nAuto-selected method: {result.get('method', 'N/A')}")
    if result.get("comparison"):
        print(f"  Platt CV ECE: {result['comparison']['platt_cv_ece']:.4f}")
        print(f"  Isotonic CV ECE: {result['comparison']['isotonic_cv_ece']:.4f}")

    # Reliability diagram data
    diagram = evaluator.generate_reliability_diagram_data(predictions, outcomes)
    print(f"\nReliability diagram (before calibration):")
    for center, acc, conf, count in zip(
        diagram["bin_centers"], diagram["accuracies"],
        diagram["confidences"], diagram["counts"]
    ):
        bar = "█" * int(count / 20)
        gap = "+" if conf > acc else "-" if conf < acc else "="
        print(f"  [{center:.1f}] acc={acc:.2f} conf={conf:.2f} {gap} n={count:3d} {bar}")
