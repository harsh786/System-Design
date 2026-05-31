"""
A/B Testing Framework for AI Systems
=====================================
Complete experiment lifecycle: design → launch → collect → analyze → decide
"""

import hashlib
import random
import numpy as np
from scipy import stats
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VariantConfig:
    name: str
    weight: int  # percentage (0-100)
    config: dict = field(default_factory=dict)


@dataclass
class ExperimentConfig:
    experiment_id: str
    name: str
    hypothesis: str
    variants: list
    primary_metric: str
    guardrail_metrics: list
    min_sample_size: int = 350
    max_duration_days: int = 14
    significance_level: float = 0.05


@dataclass
class Observation:
    request_id: str
    variant: str
    user_id: str
    metrics: dict


class ABTestingFramework:
    """Full A/B testing framework for AI experiments."""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.observations: dict = {v.name: [] for v in config.variants}
        self.status = "configured"

    def assign_variant(self, user_id: str) -> str:
        """Deterministically assign user to variant using hash."""
        hash_input = f"{user_id}:{self.config.experiment_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100

        cumulative = 0
        for variant in self.config.variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return variant.name
        return self.config.variants[-1].name

    def record_observation(self, obs: Observation):
        """Record an observation for a variant."""
        self.observations[obs.variant].append(obs)

    def get_sample_sizes(self) -> dict:
        """Get current sample sizes per variant."""
        return {name: len(obs) for name, obs in self.observations.items()}

    def check_significance(self) -> dict:
        """Check if primary metric shows statistical significance."""
        variant_names = list(self.observations.keys())
        if len(variant_names) < 2:
            return {"significant": False, "reason": "Need at least 2 variants"}

        control_name = variant_names[0]
        treatment_name = variant_names[1]

        control_scores = [
            o.metrics[self.config.primary_metric]
            for o in self.observations[control_name]
        ]
        treatment_scores = [
            o.metrics[self.config.primary_metric]
            for o in self.observations[treatment_name]
        ]

        if len(control_scores) < 20 or len(treatment_scores) < 20:
            return {"significant": False, "reason": "Insufficient samples (< 20)"}

        # Two-sample t-test
        t_stat, p_value = stats.ttest_ind(treatment_scores, control_scores)

        control_mean = np.mean(control_scores)
        treatment_mean = np.mean(treatment_scores)
        diff = treatment_mean - control_mean

        # Confidence interval for the difference
        se = np.sqrt(np.var(control_scores) / len(control_scores) +
                     np.var(treatment_scores) / len(treatment_scores))
        ci_low = diff - 1.96 * se
        ci_high = diff + 1.96 * se

        return {
            "significant": p_value < self.config.significance_level,
            "p_value": p_value,
            "control_mean": control_mean,
            "treatment_mean": treatment_mean,
            "difference": diff,
            "ci_95": (ci_low, ci_high),
            "control_n": len(control_scores),
            "treatment_n": len(treatment_scores),
        }

    def check_guardrails(self) -> list:
        """Check all guardrail metrics for degradation."""
        results = []
        variant_names = list(self.observations.keys())
        control_name = variant_names[0]
        treatment_name = variant_names[1]

        for metric in self.config.guardrail_metrics:
            control_vals = [
                o.metrics[metric] for o in self.observations[control_name]
                if metric in o.metrics
            ]
            treatment_vals = [
                o.metrics[metric] for o in self.observations[treatment_name]
                if metric in o.metrics
            ]

            if not control_vals or not treatment_vals:
                continue

            control_mean = np.mean(control_vals)
            treatment_mean = np.mean(treatment_vals)
            pct_change = (treatment_mean - control_mean) / control_mean * 100

            # For latency/cost/error: increase is bad
            degraded = pct_change > 10  # More than 10% worse

            results.append({
                "metric": metric,
                "control_mean": control_mean,
                "treatment_mean": treatment_mean,
                "pct_change": pct_change,
                "degraded": degraded,
            })

        return results

    def make_decision(self) -> dict:
        """Make ship/no-ship decision based on all evidence."""
        sig_result = self.check_significance()
        guardrail_results = self.check_guardrails()

        any_guardrail_degraded = any(g["degraded"] for g in guardrail_results)

        if not sig_result["significant"]:
            decision = "DON'T SHIP"
            reason = f"Primary metric not significant (p={sig_result.get('p_value', 'N/A'):.4f})"
        elif sig_result.get("difference", 0) < 0:
            decision = "DON'T SHIP"
            reason = "Treatment is WORSE than control"
        elif any_guardrail_degraded:
            decision = "INVESTIGATE"
            degraded = [g["metric"] for g in guardrail_results if g["degraded"]]
            reason = f"Primary improved but guardrails degraded: {degraded}"
        else:
            decision = "SHIP"
            reason = "Primary metric improved, all guardrails healthy"

        return {
            "decision": decision,
            "reason": reason,
            "primary_result": sig_result,
            "guardrail_results": guardrail_results,
        }


def simulate_experiment():
    """Simulate a complete A/B test experiment."""
    print("=" * 70)
    print("A/B TESTING FRAMEWORK FOR AI SYSTEMS")
    print("=" * 70)

    # Define experiment
    config = ExperimentConfig(
        experiment_id="exp_001_prompt_v4",
        name="Prompt V4 vs V3 - Faithfulness",
        hypothesis="Prompt V4 increases faithfulness by 5% (0.85 → 0.90)",
        variants=[
            VariantConfig("control", 50, {"prompt_version": "v3"}),
            VariantConfig("treatment", 50, {"prompt_version": "v4"}),
        ],
        primary_metric="faithfulness",
        guardrail_metrics=["latency", "cost", "error_rate"],
        min_sample_size=350,
    )

    framework = ABTestingFramework(config)

    print(f"\n📋 Experiment: {config.name}")
    print(f"   Hypothesis: {config.hypothesis}")
    print(f"   Variants: {[v.name for v in config.variants]}")
    print(f"   Primary metric: {config.primary_metric}")
    print(f"   Min sample size: {config.min_sample_size} per variant")

    # Simulate traffic
    print("\n" + "-" * 70)
    print("PHASE: Simulating traffic and collecting observations...")
    print("-" * 70)

    np.random.seed(42)
    num_requests = 800

    for i in range(num_requests):
        user_id = f"user_{random.randint(1, 200)}"
        variant = framework.assign_variant(user_id)

        # Simulate metrics based on variant
        if variant == "control":
            faithfulness = np.random.normal(0.85, 0.08)
            latency = np.random.exponential(1.1)
            cost = np.random.normal(0.030, 0.005)
        else:  # treatment
            faithfulness = np.random.normal(0.90, 0.07)  # Better!
            latency = np.random.exponential(1.3)  # Slightly slower
            cost = np.random.normal(0.035, 0.005)  # Slightly more expensive

        error_rate = 1 if random.random() < 0.005 else 0

        obs = Observation(
            request_id=f"req_{i:04d}",
            variant=variant,
            user_id=user_id,
            metrics={
                "faithfulness": max(0, min(1, faithfulness)),
                "latency": max(0.1, latency),
                "cost": max(0.01, cost),
                "error_rate": error_rate,
            },
        )
        framework.record_observation(obs)

    # Show sample sizes
    sizes = framework.get_sample_sizes()
    print(f"\n   Samples collected:")
    for name, n in sizes.items():
        print(f"     {name}: {n} observations")

    # Sequential checks
    print("\n" + "-" * 70)
    print("PHASE: Checking statistical significance...")
    print("-" * 70)

    result = framework.check_significance()
    print(f"\n   Primary metric ({config.primary_metric}):")
    print(f"     Control mean:   {result['control_mean']:.4f}")
    print(f"     Treatment mean: {result['treatment_mean']:.4f}")
    print(f"     Difference:     {result['difference']:+.4f}")
    print(f"     95% CI:         [{result['ci_95'][0]:+.4f}, {result['ci_95'][1]:+.4f}]")
    print(f"     P-value:        {result['p_value']:.6f}")
    print(f"     Significant:    {'YES' if result['significant'] else 'NO'}")

    # Check guardrails
    print("\n" + "-" * 70)
    print("PHASE: Checking guardrail metrics...")
    print("-" * 70)

    guardrails = framework.check_guardrails()
    for g in guardrails:
        status = "DEGRADED" if g["degraded"] else "OK"
        symbol = "❌" if g["degraded"] else "✅"
        print(f"\n   {symbol} {g['metric']}:")
        print(f"     Control: {g['control_mean']:.4f}")
        print(f"     Treatment: {g['treatment_mean']:.4f}")
        print(f"     Change: {g['pct_change']:+.1f}% [{status}]")

    # Make decision
    print("\n" + "=" * 70)
    print("DECISION")
    print("=" * 70)

    decision = framework.make_decision()
    print(f"\n   Decision: {decision['decision']}")
    print(f"   Reason:   {decision['reason']}")

    if decision["decision"] == "SHIP":
        print("\n   ✅ Recommendation: Roll treatment to 100% of traffic")
        print("   Next steps:")
        print("     1. Remove experiment code")
        print("     2. Monitor for 2 weeks post-ship")
        print("     3. Document learnings")
    elif decision["decision"] == "INVESTIGATE":
        print("\n   ⚠️  Recommendation: Review tradeoffs before deciding")
        print("   Questions to answer:")
        print("     - Is the quality gain worth the guardrail degradation?")
        print("     - Can we optimize treatment to reduce degradation?")
    else:
        print("\n   ❌ Recommendation: Discard treatment, iterate on hypothesis")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    simulate_experiment()
