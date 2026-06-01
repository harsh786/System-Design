"""
Model Monitoring & Drift Detection
====================================
Monitors model performance and detects data/concept drift.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DriftResult:
    """Result of a drift detection test."""
    feature: str
    statistic: float
    p_value: float
    is_drift: bool
    method: str


class DataDriftDetector:
    """Detect data drift using statistical tests."""

    def __init__(self, reference_data: pd.DataFrame, significance: float = 0.05):
        self.reference = reference_data
        self.significance = significance
        self.reference_stats = self._compute_stats(reference_data)

    def _compute_stats(self, data: pd.DataFrame) -> Dict[str, Dict]:
        stats_dict = {}
        for col in data.columns:
            stats_dict[col] = {
                "mean": data[col].mean(),
                "std": data[col].std(),
                "min": data[col].min(),
                "max": data[col].max(),
                "q25": data[col].quantile(0.25),
                "q75": data[col].quantile(0.75),
            }
        return stats_dict

    def detect_drift(self, current_data: pd.DataFrame) -> List[DriftResult]:
        """Run KS test for each feature."""
        results = []
        for col in self.reference.columns:
            if col not in current_data.columns:
                continue
            ks_stat, p_value = stats.ks_2samp(self.reference[col].values, current_data[col].values)
            results.append(DriftResult(
                feature=col,
                statistic=ks_stat,
                p_value=p_value,
                is_drift=p_value < self.significance,
                method="Kolmogorov-Smirnov",
            ))
        return results


class PerformanceMonitor:
    """Track model performance over time."""

    def __init__(self, threshold_mae: float = 0.8, window_size: int = 100):
        self.threshold_mae = threshold_mae
        self.window_size = window_size
        self.predictions: List[float] = []
        self.actuals: List[float] = []
        self.mae_history: List[float] = []

    def log_prediction(self, predicted: float, actual: float) -> None:
        self.predictions.append(predicted)
        self.actuals.append(actual)

        if len(self.predictions) >= self.window_size:
            window_preds = self.predictions[-self.window_size:]
            window_actuals = self.actuals[-self.window_size:]
            mae = np.mean(np.abs(np.array(window_preds) - np.array(window_actuals)))
            self.mae_history.append(mae)

    def check_performance_degradation(self) -> Tuple[bool, float]:
        """Check if performance has degraded beyond threshold."""
        if len(self.mae_history) < 2:
            return False, 0.0
        current_mae = self.mae_history[-1]
        is_degraded = current_mae > self.threshold_mae
        return is_degraded, current_mae


def main() -> None:
    """Run monitoring simulation."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         MODEL MONITORING & DRIFT DETECTION              ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Load data and simulate reference vs production
    data = fetch_california_housing(as_frame=True)
    df = data.data

    reference, production = train_test_split(df, test_size=0.3, random_state=42)

    # Simulate drift by shifting some features
    drifted_production = production.copy()
    drifted_production["MedInc"] = drifted_production["MedInc"] * 1.5 + 2  # Income inflation
    drifted_production["HouseAge"] = drifted_production["HouseAge"] + 10    # Aging

    # --- Data Drift Detection ---
    print("\n" + "=" * 50)
    print("DATA DRIFT DETECTION (KS Test)")
    print("=" * 50)

    detector = DataDriftDetector(reference)

    # No drift scenario
    print("\n--- Scenario 1: No drift (same distribution) ---")
    results = detector.detect_drift(production)
    print(f"\n{'Feature':<15} {'KS Stat':>8} {'p-value':>10} {'Drift?':>8}")
    print("-" * 43)
    for r in results:
        print(f"{r.feature:<15} {r.statistic:>8.4f} {r.p_value:>10.4f} {'YES' if r.is_drift else 'no':>8}")

    drift_count = sum(1 for r in results if r.is_drift)
    print(f"\nDrift detected in {drift_count}/{len(results)} features")

    # Drift scenario
    print("\n--- Scenario 2: Simulated drift (shifted features) ---")
    results = detector.detect_drift(drifted_production)
    print(f"\n{'Feature':<15} {'KS Stat':>8} {'p-value':>10} {'Drift?':>8}")
    print("-" * 43)
    for r in results:
        marker = " ⚠️" if r.is_drift else ""
        print(f"{r.feature:<15} {r.statistic:>8.4f} {r.p_value:>10.6f} {'YES' if r.is_drift else 'no':>8}{marker}")

    drift_count = sum(1 for r in results if r.is_drift)
    print(f"\n⚠️  Drift detected in {drift_count}/{len(results)} features!")

    # --- Performance Monitoring ---
    print("\n" + "=" * 50)
    print("PERFORMANCE MONITORING")
    print("=" * 50)

    monitor = PerformanceMonitor(threshold_mae=0.6, window_size=50)

    # Simulate predictions (good performance then degradation)
    np.random.seed(42)
    actuals = np.random.uniform(1, 5, 200)

    for i, actual in enumerate(actuals):
        if i < 100:
            noise = np.random.normal(0, 0.3)  # Good predictions
        else:
            noise = np.random.normal(0.5, 0.8)  # Degraded predictions
        predicted = actual + noise
        monitor.log_prediction(predicted, actual)

    print(f"\nMAE over time (windows of 50):")
    for i, mae in enumerate(monitor.mae_history):
        bar = "█" * int(mae * 20)
        status = " ⚠️ ALERT" if mae > monitor.threshold_mae else ""
        print(f"  Window {i+1:2d}: MAE={mae:.4f} {bar}{status}")

    is_degraded, current_mae = monitor.check_performance_degradation()
    if is_degraded:
        print(f"\n⚠️  Performance degradation detected! Current MAE: {current_mae:.4f} > threshold {monitor.threshold_mae}")
        print("   Action: Consider retraining the model with recent data.")
    else:
        print(f"\n✓ Performance within acceptable bounds (MAE: {current_mae:.4f})")

    print("\n✅ Monitoring complete!")


if __name__ == "__main__":
    main()
