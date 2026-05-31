"""
Statistical Significance Calculator for AI A/B Tests
=====================================================
Calculate sample sizes, p-values, confidence intervals, and power.
"""

import numpy as np
from scipy import stats
from dataclasses import dataclass


@dataclass
class ExperimentScenario:
    name: str
    description: str
    control_rate: float
    treatment_rate: float
    control_n: int
    treatment_n: int
    alpha: float = 0.05
    power: float = 0.80


def calculate_sample_size_proportions(p1: float, p2: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Calculate required sample size per variant for comparing two proportions."""
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)

    numerator = (z_alpha + z_beta) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))
    denominator = (p1 - p2) ** 2

    if denominator == 0:
        return float('inf')

    return int(np.ceil(numerator / denominator))


def calculate_sample_size_continuous(sigma: float, delta: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Calculate required sample size for comparing two means."""
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)

    n = 2 * ((z_alpha + z_beta) ** 2) * (sigma ** 2) / (delta ** 2)
    return int(np.ceil(n))


def compute_significance(control_scores, treatment_scores, alpha=0.05):
    """Compute statistical significance between two groups."""
    n_c = len(control_scores)
    n_t = len(treatment_scores)

    mean_c = np.mean(control_scores)
    mean_t = np.mean(treatment_scores)
    std_c = np.std(control_scores, ddof=1)
    std_t = np.std(treatment_scores, ddof=1)

    # T-test
    t_stat, p_value = stats.ttest_ind(treatment_scores, control_scores)

    # Confidence interval for difference
    diff = mean_t - mean_c
    se = np.sqrt(std_c**2 / n_c + std_t**2 / n_t)
    z = stats.norm.ppf(1 - alpha / 2)
    ci_low = diff - z * se
    ci_high = diff + z * se

    # Effect size (Cohen's d)
    pooled_std = np.sqrt(((n_c - 1) * std_c**2 + (n_t - 1) * std_t**2) / (n_c + n_t - 2))
    cohens_d = diff / pooled_std if pooled_std > 0 else 0

    return {
        "control_mean": mean_c,
        "treatment_mean": mean_t,
        "difference": diff,
        "pct_change": (diff / mean_c * 100) if mean_c != 0 else 0,
        "t_statistic": t_stat,
        "p_value": p_value,
        "significant": p_value < alpha,
        "ci_95": (ci_low, ci_high),
        "cohens_d": cohens_d,
        "se": se,
        "control_n": n_c,
        "treatment_n": n_t,
    }


def samples_still_needed(current_n, required_n):
    """Calculate how many more samples are needed."""
    remaining = required_n - current_n
    return max(0, remaining)


def print_separator(title=""):
    if title:
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print(f"{'=' * 70}")
    else:
        print("-" * 70)


def main():
    print_separator("STATISTICAL SIGNIFICANCE CALCULATOR FOR AI A/B TESTS")

    # ==========================================
    # Part 1: Sample Size Calculator
    # ==========================================
    print_separator("PART 1: Sample Size Requirements")

    print("\n  How many samples do you need per variant?")
    print("  (For detecting different effect sizes at alpha=0.05, power=0.80)\n")

    scenarios_table = [
        (0.85, 0.86, "1% improvement"),
        (0.85, 0.87, "2% improvement"),
        (0.85, 0.90, "5% improvement"),
        (0.85, 0.95, "10% improvement"),
        (0.80, 0.95, "15% improvement"),
    ]

    print(f"  {'Effect':<20} {'Baseline':<10} {'Target':<10} {'N per variant':<15} {'Total N':<10}")
    print(f"  {'-'*65}")

    for p1, p2, label in scenarios_table:
        n = calculate_sample_size_proportions(p1, p2)
        print(f"  {label:<20} {p1:<10.2f} {p2:<10.2f} {n:<15,} {2*n:<10,}")

    # Continuous metrics
    print(f"\n  For continuous metrics (scores 0-1, std=0.15):\n")
    print(f"  {'Effect Size':<20} {'N per variant':<15} {'At 200 req/day':<20}")
    print(f"  {'-'*55}")

    for delta in [0.01, 0.02, 0.05, 0.10]:
        n = calculate_sample_size_continuous(sigma=0.15, delta=delta)
        days = n / 100  # 50/50 split of 200/day
        print(f"  {delta:<20.2f} {n:<15,} {days:.1f} days")

    # ==========================================
    # Part 2: Five Example Scenarios
    # ==========================================
    print_separator("PART 2: Example Experiment Scenarios")

    np.random.seed(42)

    scenarios = [
        ExperimentScenario(
            name="Scenario 1: Clear Winner (Large Effect)",
            description="Prompt V4 dramatically improves faithfulness",
            control_rate=0.82, treatment_rate=0.91,
            control_n=200, treatment_n=200,
        ),
        ExperimentScenario(
            name="Scenario 2: Small Effect, Insufficient Samples",
            description="RAG improvement is real but small, not enough data yet",
            control_rate=0.85, treatment_rate=0.87,
            control_n=100, treatment_n=100,
        ),
        ExperimentScenario(
            name="Scenario 3: No Real Difference",
            description="Temperature change has no effect on quality",
            control_rate=0.85, treatment_rate=0.85,
            control_n=400, treatment_n=400,
        ),
        ExperimentScenario(
            name="Scenario 4: Treatment is Worse",
            description="New agent architecture degrades performance",
            control_rate=0.88, treatment_rate=0.83,
            control_n=300, treatment_n=300,
        ),
        ExperimentScenario(
            name="Scenario 5: Borderline (Needs More Data)",
            description="Model switch shows promise but p-value is marginal",
            control_rate=0.84, treatment_rate=0.88,
            control_n=150, treatment_n=150,
        ),
    ]

    for scenario in scenarios:
        print(f"\n  {scenario.name}")
        print(f"  {scenario.description}")
        print(f"  {'-' * 60}")

        # Simulate data
        control_scores = np.random.normal(scenario.control_rate, 0.12, scenario.control_n)
        control_scores = np.clip(control_scores, 0, 1)
        treatment_scores = np.random.normal(scenario.treatment_rate, 0.12, scenario.treatment_n)
        treatment_scores = np.clip(treatment_scores, 0, 1)

        result = compute_significance(control_scores, treatment_scores)

        # Required sample size for this effect
        effect = abs(scenario.treatment_rate - scenario.control_rate)
        if effect > 0:
            required_n = calculate_sample_size_continuous(sigma=0.12, delta=effect)
        else:
            required_n = float('inf')

        print(f"    Control:   n={result['control_n']}, mean={result['control_mean']:.4f}")
        print(f"    Treatment: n={result['treatment_n']}, mean={result['treatment_mean']:.4f}")
        print(f"    Difference: {result['difference']:+.4f} ({result['pct_change']:+.1f}%)")
        print(f"    95% CI:     [{result['ci_95'][0]:+.4f}, {result['ci_95'][1]:+.4f}]")
        print(f"    P-value:    {result['p_value']:.6f}")
        print(f"    Cohen's d:  {result['cohens_d']:.3f}")
        print(f"    Significant: {'YES ✅' if result['significant'] else 'NO ❌'}")

        if effect > 0 and required_n != float('inf'):
            current_n = min(scenario.control_n, scenario.treatment_n)
            needed = samples_still_needed(current_n, required_n)
            print(f"\n    Required samples per variant: {required_n}")
            print(f"    Current samples: {current_n}")
            if needed > 0:
                print(f"    ⏳ Need {needed} more samples per variant to reach significance")
                print(f"       At 100 samples/day/variant: ~{needed/100:.1f} more days")
            else:
                print(f"    ✅ Have sufficient samples")

        # Decision
        print(f"\n    DECISION: ", end="")
        if not result['significant']:
            if effect > 0 and required_n != float('inf'):
                needed = samples_still_needed(min(scenario.control_n, scenario.treatment_n), required_n)
                if needed > 0:
                    print("CONTINUE COLLECTING (not enough data yet)")
                else:
                    print("NO SIGNIFICANT DIFFERENCE (may be no real effect)")
            else:
                print("NO SIGNIFICANT DIFFERENCE")
        elif result['difference'] > 0:
            print("TREATMENT WINS — consider shipping")
        else:
            print("TREATMENT IS WORSE — do not ship")

    # ==========================================
    # Part 3: Power Analysis
    # ==========================================
    print_separator("PART 3: Power Analysis")

    print("\n  If you can only collect 200 samples per variant,")
    print("  what's the minimum effect you can reliably detect?\n")

    print(f"  {'Samples/variant':<18} {'Min Detectable Effect':<25} {'As % of baseline 0.85'}")
    print(f"  {'-'*63}")

    for n in [50, 100, 200, 500, 1000, 2000]:
        # MDE = (z_alpha + z_beta) * sqrt(2 * sigma^2 / n)
        z_alpha = stats.norm.ppf(0.975)
        z_beta = stats.norm.ppf(0.80)
        sigma = 0.12
        mde = (z_alpha + z_beta) * np.sqrt(2 * sigma**2 / n)
        pct = mde / 0.85 * 100
        print(f"  {n:<18} {mde:<25.4f} {pct:.1f}%")

    print("\n  Key insight: With 200 samples, you can only detect effects > 3.5%")
    print("  Smaller improvements require much more data!")

    print_separator("SUMMARY")
    print("""
  Key takeaways:
  1. Small effects (1-2%) need thousands of samples — expensive for AI
  2. Always calculate required sample size BEFORE launching
  3. If p > 0.05 but you have few samples, CONTINUE (don't conclude "no effect")
  4. Confidence intervals tell you the range of plausible true effects
  5. Cohen's d > 0.2 = small effect, > 0.5 = medium, > 0.8 = large
    """)


if __name__ == "__main__":
    main()
