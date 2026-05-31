"""
Confidence Calibrator Simulator
================================
Demonstrates confidence calibration for AI systems: raw overconfident
scores → calibrated probabilities → optimal escalation thresholds.

Run: python3 main.py
"""

import random
import math
from dataclasses import dataclass
from typing import List, Tuple
from collections import defaultdict
import statistics


@dataclass
class Prediction:
    id: int
    raw_confidence: float
    calibrated_confidence: float
    predicted_label: int
    true_label: int
    category: str


def generate_overconfident_predictions(n=2000):
    """Generate predictions from a typically overconfident model."""
    predictions = []
    categories = ["standard", "medical", "financial", "content"]

    for i in range(n):
        category = random.choice(categories)

        # Models are typically overconfident: push scores toward extremes
        raw = random.random()
        # Apply overconfidence transformation
        if raw > 0.5:
            raw_confidence = 0.5 + (raw - 0.5) ** 0.6 * 0.5 / (0.5 ** 0.6)
        else:
            raw_confidence = 0.5 - (0.5 - raw) ** 0.6 * 0.5 / (0.5 ** 0.6)

        raw_confidence = max(0.01, min(0.99, raw_confidence))

        # True accuracy is LOWER than stated confidence (overconfident)
        # P(correct) ≈ raw_confidence^0.7 (compression toward 0.5)
        true_prob = 0.5 + (raw_confidence - 0.5) * 0.7
        true_label = 1 if random.random() < 0.5 else 0
        predicted_label = true_label if random.random() < true_prob else (1 - true_label)

        predictions.append(Prediction(
            id=i,
            raw_confidence=raw_confidence,
            calibrated_confidence=raw_confidence,  # Will be updated
            predicted_label=predicted_label,
            true_label=true_label,
            category=category,
        ))

    return predictions


def compute_ece(predictions, n_bins=10):
    """Compute Expected Calibration Error."""
    bins = defaultdict(list)

    for pred in predictions:
        bin_idx = min(int(pred.calibrated_confidence * n_bins), n_bins - 1)
        correct = 1 if pred.predicted_label == pred.true_label else 0
        bins[bin_idx].append((pred.calibrated_confidence, correct))

    ece = 0.0
    bin_details = []

    for bin_idx in range(n_bins):
        if bin_idx not in bins or not bins[bin_idx]:
            bin_details.append((bin_idx, 0, 0, 0, 0))
            continue

        items = bins[bin_idx]
        avg_confidence = statistics.mean(conf for conf, _ in items)
        avg_accuracy = statistics.mean(correct for _, correct in items)
        count = len(items)
        gap = abs(avg_confidence - avg_accuracy)

        ece += (count / len(predictions)) * gap
        bin_details.append((bin_idx, avg_confidence, avg_accuracy, count, gap))

    return ece, bin_details


def temperature_scaling(predictions, val_predictions):
    """Find optimal temperature using validation set."""
    # Search for best temperature
    best_t = 1.0
    best_nll = float('inf')

    for t_int in range(20, 500, 5):  # T from 0.2 to 5.0
        t = t_int / 100.0
        nll = 0.0

        for pred in val_predictions:
            # Convert confidence to logit, scale, convert back
            conf = pred.raw_confidence
            conf = max(0.01, min(0.99, conf))
            logit = math.log(conf / (1 - conf))
            scaled_logit = logit / t
            scaled_conf = 1.0 / (1.0 + math.exp(-scaled_logit))

            correct = 1 if pred.predicted_label == pred.true_label else 0
            if correct:
                nll -= math.log(max(scaled_conf, 1e-10))
            else:
                nll -= math.log(max(1 - scaled_conf, 1e-10))

        if nll < best_nll:
            best_nll = nll
            best_t = t

    # Apply best temperature to all predictions
    for pred in predictions:
        conf = pred.raw_confidence
        conf = max(0.01, min(0.99, conf))
        logit = math.log(conf / (1 - conf))
        scaled_logit = logit / best_t
        pred.calibrated_confidence = 1.0 / (1.0 + math.exp(-scaled_logit))

    return best_t


def print_reliability_diagram(bin_details, title="Reliability Diagram"):
    """Print ASCII reliability diagram."""
    print(f"\n  {title}")
    print("  " + "-" * 55)

    height = 10
    width = 10  # number of bins

    # Header
    print(f"  Actual")
    print(f"  Accuracy")

    for row in range(height, -1, -1):
        level = row / height
        line = f"  {level:.1f} |"

        for bin_idx in range(width):
            _, avg_conf, avg_acc, count, _ = bin_details[bin_idx] if bin_idx < len(bin_details) else (0, 0, 0, 0, 0)

            if count == 0:
                line += "     "
            else:
                # Bar for accuracy
                bar_height = avg_acc
                if abs(bar_height - level) < 0.05:
                    line += "  #  "
                elif bar_height > level and bar_height - 0.1 <= level:
                    line += "  #  "
                else:
                    # Diagonal reference line
                    if abs(level - (bin_idx + 0.5) / width) < 0.06:
                        line += "  .  "
                    else:
                        line += "     "

        line += "|"
        print(line)

    print(f"      +{'-----' * width}+")
    print(f"       {'0.0-0.1  0.2  0.3  0.4  0.5  0.6  0.7  0.8  0.9  1.0'}")
    print(f"       {'Predicted Confidence':^50}")
    print(f"       (# = actual accuracy, . = perfect calibration diagonal)")


def print_calibration_table(bin_details, title):
    """Print detailed calibration table."""
    print(f"\n  {title}")
    print(f"  {'Bin':<12} {'Avg Conf':<10} {'Avg Acc':<10} {'Count':<8} {'Gap':<8} {'Status'}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*12}")

    for bin_idx, avg_conf, avg_acc, count, gap in bin_details:
        if count == 0:
            continue
        status = "OK" if gap < 0.05 else ("WARN" if gap < 0.10 else "BAD")
        conf_range = f"[{bin_idx/10:.1f}-{(bin_idx+1)/10:.1f})"
        print(f"  {conf_range:<12} {avg_conf:<10.3f} {avg_acc:<10.3f} {count:<8} {gap:<8.3f} {status}")


def find_optimal_threshold(predictions, error_cost, review_cost):
    """Find threshold that minimizes total cost."""
    best_threshold = 0.5
    best_cost = float('inf')
    results = []

    for t_int in range(50, 99):
        threshold = t_int / 100.0

        auto_items = [p for p in predictions if p.calibrated_confidence >= threshold]
        review_items = [p for p in predictions if p.calibrated_confidence < threshold]

        if not auto_items:
            continue

        # Error rate on auto-approved items
        auto_errors = sum(1 for p in auto_items if p.predicted_label != p.true_label)
        auto_error_rate = auto_errors / len(auto_items) if auto_items else 0

        auto_rate = len(auto_items) / len(predictions)
        review_rate = len(review_items) / len(predictions)

        # Total cost per item
        total_cost = (auto_rate * auto_error_rate * error_cost +
                      review_rate * review_cost)

        results.append((threshold, auto_rate, auto_error_rate, review_rate, total_cost))

        if total_cost < best_cost:
            best_cost = total_cost
            best_threshold = threshold

    return best_threshold, results


def demonstrate_threshold_optimization(predictions):
    """Show how optimal threshold varies by risk level."""
    print("\n" + "=" * 65)
    print("      THRESHOLD OPTIMIZATION BY RISK LEVEL")
    print("=" * 65)

    scenarios = [
        ("Low Risk (recommendations)", 1.0, 0.50),
        ("Medium Risk (content mod)", 10.0, 2.00),
        ("High Risk (medical)", 100.0, 5.00),
        ("Critical (financial)", 500.0, 10.00),
    ]

    print(f"\n  {'Scenario':<30} {'Error Cost':<12} {'Review Cost':<12} {'Optimal Thr':<12} {'Auto Rate'}")
    print(f"  {'-'*30} {'-'*12} {'-'*12} {'-'*12} {'-'*10}")

    for name, error_cost, review_cost in scenarios:
        threshold, results = find_optimal_threshold(predictions, error_cost, review_cost)

        # Find auto rate at optimal threshold
        auto_rate = 0
        for t, ar, _, _, _ in results:
            if abs(t - threshold) < 0.01:
                auto_rate = ar
                break

        print(f"  {name:<30} ${error_cost:<11.0f} ${review_cost:<11.2f} {threshold:<12.2f} {auto_rate*100:.1f}%")

    print(f"\n  Insight: Higher error cost → higher threshold → more human review")
    print(f"  The optimal threshold balances error cost vs review cost")


def demonstrate_drift_detection(predictions):
    """Simulate calibration drift over time."""
    print("\n" + "=" * 65)
    print("      CALIBRATION DRIFT DETECTION")
    print("=" * 65)

    print(f"\n  Simulating weekly calibration monitoring...")
    print(f"\n  {'Week':<8} {'ECE':<8} {'Auto Rate':<12} {'Error Rate':<12} {'Status'}")
    print(f"  {'-'*8} {'-'*8} {'-'*12} {'-'*12} {'-'*12}")

    for week in range(1, 9):
        # Simulate drift: predictions become less calibrated over time
        drifted = []
        drift_factor = 1.0 + (week - 1) * 0.03  # Increasing drift

        for pred in predictions[:250]:  # Weekly sample
            new_pred = Prediction(
                id=pred.id,
                raw_confidence=pred.raw_confidence,
                calibrated_confidence=min(0.99, pred.calibrated_confidence * drift_factor),
                predicted_label=pred.predicted_label,
                true_label=pred.true_label,
                category=pred.category,
            )
            # Also accuracy degrades slightly
            if random.random() < (week - 1) * 0.02:
                new_pred.true_label = 1 - new_pred.true_label
            drifted.append(new_pred)

        ece, _ = compute_ece(drifted)
        auto = sum(1 for p in drifted if p.calibrated_confidence >= 0.85) / len(drifted)
        auto_items = [p for p in drifted if p.calibrated_confidence >= 0.85]
        errors = sum(1 for p in auto_items if p.predicted_label != p.true_label) / max(len(auto_items), 1)

        status = "OK" if ece < 0.05 else ("WARN" if ece < 0.08 else "RECALIBRATE")
        print(f"  W{week:<7} {ece:<8.3f} {auto*100:<12.1f}% {errors*100:<12.1f}% {status}")

    print(f"\n  Action: Recalibrate when ECE exceeds 0.08 or error rate spikes")


def main():
    print("=" * 65)
    print("         CONFIDENCE CALIBRATOR SIMULATOR")
    print("         From Overconfident Scores to Calibrated Probabilities")
    print("=" * 65)

    random.seed(42)

    # Generate predictions
    print("\n  Generating 2000 predictions from overconfident model...")
    all_predictions = generate_overconfident_predictions(n=2000)

    # Split into calibration set and test set
    random.shuffle(all_predictions)
    val_set = all_predictions[:500]
    test_set = all_predictions[500:]

    # Step 1: Measure calibration BEFORE
    print("\n" + "=" * 65)
    print("      BEFORE CALIBRATION (Raw Model Scores)")
    print("=" * 65)

    ece_before, bins_before = compute_ece(test_set)
    print(f"\n  ECE (Expected Calibration Error): {ece_before:.4f}")
    interpretation = "Good" if ece_before < 0.05 else ("Acceptable" if ece_before < 0.10 else "Poor - needs calibration")
    print(f"  Interpretation: {interpretation}")

    print_calibration_table(bins_before, "Before Calibration (binned confidence vs accuracy):")

    # Step 2: Apply temperature scaling
    print("\n" + "=" * 65)
    print("      APPLYING TEMPERATURE SCALING")
    print("=" * 65)

    # Also calibrate val set for finding temperature, then apply to test
    optimal_t = temperature_scaling(test_set, val_set)
    print(f"\n  Optimal temperature: T = {optimal_t:.2f}")
    if optimal_t > 1.0:
        print(f"  T > 1 means model was overconfident (scores pushed toward 0.5)")
    else:
        print(f"  T < 1 means model was underconfident (scores pushed toward extremes)")

    # Show effect on sample predictions
    print(f"\n  Sample predictions before/after calibration:")
    print(f"  {'Raw Confidence':<16} {'Calibrated':<12} {'Correct?':<10} {'Change'}")
    print(f"  {'-'*16} {'-'*12} {'-'*10} {'-'*10}")
    for pred in test_set[:8]:
        correct = "Yes" if pred.predicted_label == pred.true_label else "No"
        change = pred.calibrated_confidence - pred.raw_confidence
        print(f"  {pred.raw_confidence:<16.3f} {pred.calibrated_confidence:<12.3f} {correct:<10} {change:+.3f}")

    # Step 3: Measure calibration AFTER
    print("\n" + "=" * 65)
    print("      AFTER CALIBRATION")
    print("=" * 65)

    ece_after, bins_after = compute_ece(test_set)
    print(f"\n  ECE (Expected Calibration Error): {ece_after:.4f}")
    improvement = (ece_before - ece_after) / ece_before * 100
    print(f"  Improvement: {improvement:.1f}% reduction in calibration error")

    print_calibration_table(bins_after, "After Calibration (binned confidence vs accuracy):")

    # Step 4: Threshold optimization
    demonstrate_threshold_optimization(test_set)

    # Step 5: Drift detection
    demonstrate_drift_detection(test_set)

    # Summary
    print("\n" + "=" * 65)
    print("      SUMMARY")
    print("=" * 65)
    print(f"""
  Before Calibration:
    ECE: {ece_before:.4f} ({"overconfident" if optimal_t > 1 else "underconfident"})
    
  After Temperature Scaling (T={optimal_t:.2f}):
    ECE: {ece_after:.4f} ({improvement:.0f}% improvement)
    
  Key Insights:
    1. Raw model scores are NOT reliable probabilities
    2. Temperature scaling is simple (1 parameter) and effective
    3. Calibration enables meaningful confidence thresholds
    4. Higher-risk decisions need higher confidence thresholds
    5. Monitor ECE weekly - recalibrate when drift detected
    6. Different categories may need different thresholds
    """)


if __name__ == "__main__":
    main()
