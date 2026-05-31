"""
Experiment Results Analyzer
============================
Analyzes A/B test results, performs statistical tests, checks guardrails,
and makes ship/no-ship recommendations.
"""

import numpy as np
from scipy import stats
from dataclasses import dataclass


@dataclass
class MetricResult:
    name: str
    control_values: np.ndarray
    treatment_values: np.ndarray
    direction: str  # "higher_is_better" or "lower_is_better"
    threshold: float = None  # guardrail threshold
    is_primary: bool = False
    is_binary: bool = False


def analyze_continuous_metric(metric: MetricResult, alpha=0.05) -> dict:
    """Analyze a continuous metric using t-test."""
    c = metric.control_values
    t = metric.treatment_values

    mean_c, mean_t = np.mean(c), np.mean(t)
    std_c, std_t = np.std(c, ddof=1), np.std(t, ddof=1)

    # T-test
    t_stat, p_value = stats.ttest_ind(t, c)

    # Mann-Whitney U (non-parametric alternative)
    u_stat, p_value_mw = stats.mannwhitneyu(t, c, alternative='two-sided')

    # Confidence interval
    diff = mean_t - mean_c
    se = np.sqrt(std_c**2 / len(c) + std_t**2 / len(t))
    z = stats.norm.ppf(1 - alpha / 2)
    ci = (diff - z * se, diff + z * se)

    # Determine if improvement or degradation
    if metric.direction == "higher_is_better":
        improved = diff > 0
        pct_change = diff / mean_c * 100 if mean_c != 0 else 0
    else:
        improved = diff < 0
        pct_change = -diff / mean_c * 100 if mean_c != 0 else 0

    # Guardrail check
    guardrail_ok = True
    if metric.threshold is not None:
        if metric.direction == "lower_is_better":
            guardrail_ok = mean_t <= metric.threshold
        else:
            guardrail_ok = mean_t >= metric.threshold

    return {
        "name": metric.name,
        "control_mean": mean_c,
        "treatment_mean": mean_t,
        "difference": diff,
        "pct_change": pct_change,
        "improved": improved,
        "p_value_ttest": p_value,
        "p_value_mannwhitney": p_value_mw,
        "significant": p_value < alpha,
        "ci_95": ci,
        "guardrail_ok": guardrail_ok,
        "is_primary": metric.is_primary,
    }


def analyze_binary_metric(metric: MetricResult, alpha=0.05) -> dict:
    """Analyze a binary metric using chi-squared test."""
    c = metric.control_values
    t = metric.treatment_values

    # Proportions
    p_c = np.mean(c)
    p_t = np.mean(t)
    n_c = len(c)
    n_t = len(t)

    # Chi-squared test (2x2 contingency table)
    success_c = int(np.sum(c))
    fail_c = n_c - success_c
    success_t = int(np.sum(t))
    fail_t = n_t - success_t

    table = np.array([[success_c, fail_c], [success_t, fail_t]])
    chi2, p_value, dof, expected = stats.chi2_contingency(table)

    # Confidence interval for difference in proportions
    diff = p_t - p_c
    se = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    z = stats.norm.ppf(1 - alpha / 2)
    ci = (diff - z * se, diff + z * se)

    if metric.direction == "higher_is_better":
        improved = diff > 0
        pct_change = diff / p_c * 100 if p_c != 0 else 0
    else:
        improved = diff < 0
        pct_change = -diff / p_c * 100 if p_c != 0 else 0

    guardrail_ok = True
    if metric.threshold is not None:
        if metric.direction == "lower_is_better":
            guardrail_ok = p_t <= metric.threshold
        else:
            guardrail_ok = p_t >= metric.threshold

    return {
        "name": metric.name,
        "control_rate": p_c,
        "treatment_rate": p_t,
        "difference": diff,
        "pct_change": pct_change,
        "improved": improved,
        "p_value": p_value,
        "chi2": chi2,
        "significant": p_value < alpha,
        "ci_95": ci,
        "guardrail_ok": guardrail_ok,
        "is_primary": metric.is_primary,
    }


def make_recommendation(results: list) -> dict:
    """Make ship/no-ship recommendation based on all metric results."""
    primary = [r for r in results if r["is_primary"]][0]
    guardrails = [r for r in results if not r["is_primary"]]

    guardrails_ok = all(g["guardrail_ok"] for g in guardrails)
    guardrails_degraded = [g["name"] for g in guardrails if not g["guardrail_ok"]]

    if not primary["significant"]:
        return {
            "decision": "DON'T SHIP",
            "confidence": "HIGH",
            "reason": "Primary metric did not reach statistical significance",
            "details": f"p-value = {primary.get('p_value_ttest', primary.get('p_value', 0)):.4f} (need < 0.05)",
        }

    if not primary["improved"]:
        return {
            "decision": "DON'T SHIP",
            "confidence": "HIGH",
            "reason": "Treatment is significantly WORSE on primary metric",
            "details": f"Change: {primary['pct_change']:+.1f}%",
        }

    if not guardrails_ok:
        return {
            "decision": "INVESTIGATE",
            "confidence": "MEDIUM",
            "reason": f"Primary improved but guardrails degraded: {guardrails_degraded}",
            "details": "Review if quality gain justifies guardrail degradation",
        }

    return {
        "decision": "SHIP",
        "confidence": "HIGH",
        "reason": "Primary metric significantly improved, all guardrails healthy",
        "details": f"Improvement: {primary['pct_change']:+.1f}%, all guardrails within thresholds",
    }


def draw_text_chart(label, control_val, treatment_val, width=40):
    """Draw a simple text-based comparison chart."""
    max_val = max(control_val, treatment_val, 0.01)
    c_bar = int(control_val / max_val * width)
    t_bar = int(treatment_val / max_val * width)

    print(f"    {label}:")
    print(f"      Control:   [{'█' * c_bar}{'░' * (width - c_bar)}] {control_val:.4f}")
    print(f"      Treatment: [{'█' * t_bar}{'░' * (width - t_bar)}] {treatment_val:.4f}")


def print_separator(title=""):
    if title:
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print(f"{'=' * 70}")
    else:
        print("-" * 60)


def run_experiment_analysis(experiment_name, metrics, description=""):
    """Run full analysis on an experiment."""
    print_separator(f"EXPERIMENT: {experiment_name}")
    if description:
        print(f"  {description}\n")

    results = []
    for metric in metrics:
        if metric.is_binary:
            result = analyze_binary_metric(metric)
        else:
            result = analyze_continuous_metric(metric)
        results.append(result)

    # Print results table
    print(f"  {'Metric':<20} {'Control':<10} {'Treatment':<10} {'Change':<10} {'P-value':<10} {'Status'}")
    print(f"  {'-'*75}")

    for r in results:
        c_val = r.get("control_mean", r.get("control_rate", 0))
        t_val = r.get("treatment_mean", r.get("treatment_rate", 0))
        p_val = r.get("p_value_ttest", r.get("p_value", 0))
        sig = "SIG" if r["significant"] else "n.s."
        guardrail = "✅" if r["guardrail_ok"] else "❌"
        primary = " [PRIMARY]" if r["is_primary"] else ""
        print(f"  {r['name']:<20} {c_val:<10.4f} {t_val:<10.4f} {r['pct_change']:>+7.1f}%  {p_val:<10.4f} {sig} {guardrail}{primary}")

    # Visual comparison
    print(f"\n  Visual Comparison:")
    for r in results:
        c_val = r.get("control_mean", r.get("control_rate", 0))
        t_val = r.get("treatment_mean", r.get("treatment_rate", 0))
        draw_text_chart(r["name"], c_val, t_val)

    # Confidence intervals
    print(f"\n  Confidence Intervals (95%):")
    for r in results:
        ci = r["ci_95"]
        contains_zero = ci[0] <= 0 <= ci[1]
        marker = " (contains 0 — not significant)" if contains_zero else ""
        print(f"    {r['name']:<20} [{ci[0]:+.4f}, {ci[1]:+.4f}]{marker}")

    # Recommendation
    rec = make_recommendation(results)
    print(f"\n  {'─'*60}")
    print(f"  RECOMMENDATION: {rec['decision']}")
    print(f"  Confidence: {rec['confidence']}")
    print(f"  Reason: {rec['reason']}")
    print(f"  Details: {rec['details']}")
    print(f"  {'─'*60}")

    return rec


def main():
    print_separator("EXPERIMENT RESULTS ANALYZER")
    print("  Analyzes multi-metric A/B test results and makes recommendations\n")

    np.random.seed(42)
    n = 400  # samples per variant

    # ==========================================
    # Experiment 1: Clear Win
    # ==========================================
    metrics_1 = [
        MetricResult("faithfulness", np.random.normal(0.84, 0.10, n),
                     np.random.normal(0.90, 0.09, n),
                     "higher_is_better", is_primary=True),
        MetricResult("latency_p95", np.random.exponential(1.1, n),
                     np.random.exponential(1.2, n),
                     "lower_is_better", threshold=2.0),
        MetricResult("cost", np.random.normal(0.030, 0.005, n),
                     np.random.normal(0.033, 0.005, n),
                     "lower_is_better", threshold=0.05),
        MetricResult("error_rate", np.random.binomial(1, 0.005, n).astype(float),
                     np.random.binomial(1, 0.006, n).astype(float),
                     "lower_is_better", threshold=0.02, is_binary=True),
    ]
    run_experiment_analysis("Prompt V4 vs V3", metrics_1,
                           "Hypothesis: V4 increases faithfulness by 5%")

    # ==========================================
    # Experiment 2: Guardrail Violation
    # ==========================================
    metrics_2 = [
        MetricResult("accuracy", np.random.normal(0.82, 0.12, n),
                     np.random.normal(0.88, 0.10, n),
                     "higher_is_better", is_primary=True),
        MetricResult("latency_p95", np.random.exponential(1.0, n),
                     np.random.exponential(2.5, n),  # Much slower!
                     "lower_is_better", threshold=2.0),
        MetricResult("cost", np.random.normal(0.03, 0.005, n),
                     np.random.normal(0.06, 0.01, n),  # 2x cost!
                     "lower_is_better", threshold=0.05),
    ]
    run_experiment_analysis("GPT-4 vs GPT-3.5 Turbo (upgrading)", metrics_2,
                           "Hypothesis: GPT-4 improves accuracy (but at what cost?)")

    # ==========================================
    # Experiment 3: No Effect
    # ==========================================
    metrics_3 = [
        MetricResult("quality_score", np.random.normal(0.85, 0.11, n),
                     np.random.normal(0.855, 0.11, n),
                     "higher_is_better", is_primary=True),
        MetricResult("latency_p95", np.random.exponential(1.1, n),
                     np.random.exponential(1.1, n),
                     "lower_is_better", threshold=2.0),
    ]
    run_experiment_analysis("Temperature 0.7 vs 0.5", metrics_3,
                           "Hypothesis: Lower temperature improves quality")

    # ==========================================
    # Experiment 4: Treatment is Worse
    # ==========================================
    metrics_4 = [
        MetricResult("task_completion", np.random.binomial(1, 0.75, n).astype(float),
                     np.random.binomial(1, 0.65, n).astype(float),
                     "higher_is_better", is_primary=True, is_binary=True),
        MetricResult("latency_p95", np.random.exponential(1.5, n),
                     np.random.exponential(0.8, n),
                     "lower_is_better", threshold=2.0),
    ]
    run_experiment_analysis("Planner-Executor vs ReAct Agent", metrics_4,
                           "Hypothesis: Planner-executor completes more tasks")

    # ==========================================
    # Summary
    # ==========================================
    print_separator("ANALYSIS COMPLETE")
    print("""
  Summary of Decisions:
  ┌────────────────────────────────────────┬──────────────┐
  │ Experiment                             │ Decision     │
  ├────────────────────────────────────────┼──────────────┤
  │ Prompt V4 vs V3                        │ SHIP         │
  │ GPT-4 vs GPT-3.5 (upgrade)            │ INVESTIGATE  │
  │ Temperature 0.7 vs 0.5                 │ DON'T SHIP   │
  │ Planner-Executor vs ReAct             │ DON'T SHIP   │
  └────────────────────────────────────────┴──────────────┘

  Key insight: Only 1 out of 4 experiments resulted in a clear ship decision.
  This is NORMAL. Most experiments don't produce clear wins.
  That's why we test instead of just deploying!
    """)


if __name__ == "__main__":
    main()
