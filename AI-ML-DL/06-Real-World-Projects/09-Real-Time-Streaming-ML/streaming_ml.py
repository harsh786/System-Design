"""
Project 9: Real-Time Streaming ML Pipeline
===========================================

Simulates a credit card fraud detection system with:
- Real-time data streaming (synthetic transactions)
- Online learning (SGDClassifier with partial_fit)
- Concept drift detection (Page-Hinkley test)
- Sliding window feature engineering
- Real-time anomaly scoring

Educational Purpose:
- Learn online/incremental learning vs batch training
- Understand concept drift and why models degrade over time
- See how sliding window features capture temporal patterns
- Observe model recovery after drift detection

Run: python streaming_ml.py
"""

import logging
import numpy as np
from collections import deque
from dataclasses import dataclass, field
from typing import Generator
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Stream Simulator
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Transaction:
    """A single credit card transaction event."""
    timestamp: int
    amount: float
    merchant_category: int  # 0-9
    hour_of_day: int  # 0-23
    is_international: int  # 0 or 1
    transaction_frequency: float  # transactions in last hour
    is_fraud: int  # label: 0 or 1


def generate_stream(
    n_events: int = 10000,
    drift_point: int = 5000,
    seed: int = 42,
) -> Generator[Transaction, None, None]:
    """
    Generate a synthetic transaction stream with concept drift.
    
    Before drift_point: fraud is characterized by high amounts + international.
    After drift_point: fraud pattern shifts to frequent small transactions (new pattern).
    """
    rng = np.random.RandomState(seed)

    for t in range(n_events):
        hour = rng.randint(0, 24)
        category = rng.randint(0, 10)
        is_international = int(rng.random() < 0.15)
        frequency = rng.exponential(2.0)

        if t < drift_point:
            # Pre-drift fraud pattern: high amount + international + late night
            amount = rng.exponential(50.0)
            fraud_prob = 0.02
            if amount > 200 and is_international and hour > 22:
                fraud_prob = 0.7
            elif amount > 300:
                fraud_prob = 0.4
        else:
            # Post-drift fraud pattern: frequent small transactions (new attack)
            amount = rng.exponential(40.0)
            fraud_prob = 0.03
            if frequency > 5.0 and amount < 30 and category in [2, 7]:
                fraud_prob = 0.75
            elif frequency > 8.0:
                fraud_prob = 0.5

        is_fraud = int(rng.random() < fraud_prob)

        yield Transaction(
            timestamp=t,
            amount=amount,
            merchant_category=category,
            hour_of_day=hour,
            is_international=is_international,
            transaction_frequency=frequency,
            is_fraud=is_fraud,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Feature Engineering (Sliding Window)
# ─────────────────────────────────────────────────────────────────────────────


class SlidingWindowFeatures:
    """Compute features over a sliding window of recent transactions."""

    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.amounts: deque = deque(maxlen=window_size)
        self.frequencies: deque = deque(maxlen=window_size)

    def update_and_extract(self, txn: Transaction) -> np.ndarray:
        """Add transaction to window and extract features."""
        self.amounts.append(txn.amount)
        self.frequencies.append(txn.transaction_frequency)

        # Raw features
        features = [
            txn.amount,
            txn.merchant_category,
            txn.hour_of_day,
            txn.is_international,
            txn.transaction_frequency,
        ]

        # Window-based features
        if len(self.amounts) >= 5:
            amounts_arr = np.array(self.amounts)
            features.extend([
                np.mean(amounts_arr),
                np.std(amounts_arr),
                txn.amount / (np.mean(amounts_arr) + 1e-8),  # ratio to mean
                np.mean(list(self.frequencies)),
                float(txn.amount > np.percentile(amounts_arr, 95)),  # outlier flag
            ])
        else:
            features.extend([txn.amount, 0.0, 1.0, txn.transaction_frequency, 0.0])

        return np.array(features, dtype=np.float64)


# ─────────────────────────────────────────────────────────────────────────────
# Concept Drift Detection (Page-Hinkley Test)
# ─────────────────────────────────────────────────────────────────────────────


class PageHinkleyDetector:
    """
    Page-Hinkley test for concept drift detection.
    Monitors a running sum of deviations from the mean.
    Triggers when the deviation exceeds a threshold.
    """

    def __init__(self, threshold: float = 50.0, delta: float = 0.005):
        self.threshold = threshold
        self.delta = delta
        self.sum: float = 0.0
        self.min_sum: float = float("inf")
        self.count: int = 0
        self.mean: float = 0.0

    def update(self, value: float) -> bool:
        """Update with new value. Returns True if drift detected."""
        self.count += 1
        self.mean += (value - self.mean) / self.count
        self.sum += value - self.mean - self.delta
        self.min_sum = min(self.min_sum, self.sum)

        if self.sum - self.min_sum > self.threshold:
            return True
        return False

    def reset(self) -> None:
        """Reset detector after drift is handled."""
        self.sum = 0.0
        self.min_sum = float("inf")
        self.count = 0
        self.mean = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Online Learning Model
# ─────────────────────────────────────────────────────────────────────────────


class OnlineFraudDetector:
    """Online fraud detection with incremental learning."""

    def __init__(self):
        self.model = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=0.0001,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.is_warm = False
        self._warmup_X: list[np.ndarray] = []
        self._warmup_y: list[int] = []
        self.warmup_size = 100

    def predict(self, features: np.ndarray) -> tuple[int, float]:
        """Predict fraud probability. Returns (prediction, confidence)."""
        if not self.is_warm:
            return 0, 0.5
        X = self.scaler.transform(features.reshape(1, -1))
        pred = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0]
        confidence = float(np.max(proba))
        return int(pred), confidence

    def update(self, features: np.ndarray, label: int) -> None:
        """Incrementally update model with one sample."""
        if not self.is_warm:
            self._warmup_X.append(features)
            self._warmup_y.append(label)
            if len(self._warmup_X) >= self.warmup_size:
                X = np.array(self._warmup_X)
                y = np.array(self._warmup_y)
                self.scaler.fit(X)
                X_scaled = self.scaler.transform(X)
                self.model.fit(X_scaled, y)
                self.is_warm = True
                self._warmup_X.clear()
                self._warmup_y.clear()
            return

        X = self.scaler.transform(features.reshape(1, -1))
        self.model.partial_fit(X, [label])

    def reset(self) -> None:
        """Reset model (used after drift detection)."""
        self.model = SGDClassifier(
            loss="log_loss", penalty="l2", alpha=0.0001, random_state=42
        )
        self.is_warm = False
        self._warmup_X = []
        self._warmup_y = []


# ─────────────────────────────────────────────────────────────────────────────
# Metrics Tracker
# ─────────────────────────────────────────────────────────────────────────────


class MetricsTracker:
    """Track rolling classification metrics."""

    def __init__(self, window: int = 100):
        self.window = window
        self.predictions: deque = deque(maxlen=window)
        self.labels: deque = deque(maxlen=window)

    def update(self, pred: int, label: int) -> None:
        self.predictions.append(pred)
        self.labels.append(label)

    def accuracy(self) -> float:
        if not self.predictions:
            return 0.0
        return sum(p == l for p, l in zip(self.predictions, self.labels)) / len(self.predictions)

    def precision(self) -> float:
        tp = sum(p == 1 and l == 1 for p, l in zip(self.predictions, self.labels))
        fp = sum(p == 1 and l == 0 for p, l in zip(self.predictions, self.labels))
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0

    def recall(self) -> float:
        tp = sum(p == 1 and l == 1 for p, l in zip(self.predictions, self.labels))
        fn = sum(p == 0 and l == 1 for p, l in zip(self.predictions, self.labels))
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0

    def fraud_rate(self) -> float:
        if not self.labels:
            return 0.0
        return sum(self.labels) / len(self.labels)


# ─────────────────────────────────────────────────────────────────────────────
# Main Pipeline
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the streaming ML pipeline."""
    print("=" * 60)
    print("   REAL-TIME STREAMING ML - Credit Card Fraud Detection")
    print("=" * 60)

    # Configuration
    n_events = 10000
    drift_point = 5000
    report_interval = 500

    print(f"\n[CONFIG] Stream: {n_events} events | Drift injection at event {drift_point}")
    print("[CONFIG] Model: SGDClassifier (online learning with partial_fit)")
    print("[CONFIG] Drift detector: Page-Hinkley (threshold=50)")

    # Initialize components
    feature_engine = SlidingWindowFeatures(window_size=50)
    model = OnlineFraudDetector()
    drift_detector = PageHinkleyDetector(threshold=50.0, delta=0.005)
    metrics = MetricsTracker(window=200)

    # Recent data buffer for retraining after drift
    recent_X: deque = deque(maxlen=200)
    recent_y: deque = deque(maxlen=200)

    drift_events: list[int] = []

    print(f"\n[STREAM] Processing events...")
    print("─" * 60)

    for txn in generate_stream(n_events=n_events, drift_point=drift_point):
        # Step 1: Feature extraction
        features = feature_engine.update_and_extract(txn)

        # Step 2: Predict
        pred, confidence = model.predict(features)

        # Step 3: Update metrics (using true label as ground truth)
        metrics.update(pred, txn.is_fraud)

        # Step 4: Online model update
        model.update(features, txn.is_fraud)
        recent_X.append(features)
        recent_y.append(txn.is_fraud)

        # Step 5: Drift detection (monitor error rate)
        error = float(pred != txn.is_fraud)
        drift_detected = drift_detector.update(error)

        if drift_detected and model.is_warm:
            print(f"\n  ⚠ [DRIFT ALERT] Concept drift detected at t={txn.timestamp}!")
            print(f"    Rolling accuracy dropped to {metrics.accuracy():.3f}")
            print(f"    Resetting model and retraining on recent window...")
            drift_events.append(txn.timestamp)
            drift_detector.reset()
            model.reset()
            # Retrain on recent data
            for x, y in zip(recent_X, recent_y):
                model.update(x, y)
            print(f"    Model retrained on {len(recent_X)} recent samples.\n")

        # Step 6: Periodic reporting
        if txn.timestamp > 0 and txn.timestamp % report_interval == 0 and model.is_warm:
            print(
                f"  t={txn.timestamp:<6}| Acc: {metrics.accuracy():.3f} | "
                f"Prec: {metrics.precision():.2f} | Recall: {metrics.recall():.2f} | "
                f"Fraud rate: {metrics.fraud_rate()*100:.1f}%"
            )

    # Summary
    print("\n" + "─" * 60)
    print("[SUMMARY]")
    print(f"  Total events processed: {n_events}")
    print(f"  Drift events detected: {len(drift_events)}")
    if drift_events:
        print(f"  Drift timestamps: {drift_events}")
    print(f"  Final rolling accuracy: {metrics.accuracy():.3f}")
    print(f"  Final precision: {metrics.precision():.3f}")
    print(f"  Final recall: {metrics.recall():.3f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
