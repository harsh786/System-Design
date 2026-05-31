# Fine-Tuned Model Evaluation Pipeline
# Compares fine-tuned model vs base model to determine deployment readiness

import json
import random
from dataclasses import dataclass
from collections import defaultdict

random.seed(42)


# =============================================================================
# TEST DATASET
# =============================================================================

TEST_EXAMPLES = [
    {"id": 1, "category": "billing", "query": "How do I cancel?", "expected_format": "steps", "difficulty": "easy"},
    {"id": 2, "category": "billing", "query": "Double charged this month", "expected_format": "acknowledgment+action", "difficulty": "medium"},
    {"id": 3, "category": "billing", "query": "Refund for service outage on 3/15", "expected_format": "acknowledgment+action", "difficulty": "hard"},
    {"id": 4, "category": "technical", "query": "App crashes on file upload", "expected_format": "troubleshooting", "difficulty": "medium"},
    {"id": 5, "category": "technical", "query": "API 500 error with multipart form", "expected_format": "troubleshooting", "difficulty": "hard"},
    {"id": 6, "category": "technical", "query": "How to reset password?", "expected_format": "steps", "difficulty": "easy"},
    {"id": 7, "category": "technical", "query": "Webhook not firing for deleted events", "expected_format": "troubleshooting", "difficulty": "hard"},
    {"id": 8, "category": "general", "query": "What plans do you offer?", "expected_format": "informational", "difficulty": "easy"},
    {"id": 9, "category": "general", "query": "GDPR compliance details", "expected_format": "informational", "difficulty": "medium"},
    {"id": 10, "category": "complaints", "query": "Third outage this week, considering leaving", "expected_format": "empathy+action", "difficulty": "hard"},
    {"id": 11, "category": "complaints", "query": "Your support is too slow", "expected_format": "empathy+action", "difficulty": "medium"},
    {"id": 12, "category": "feature_request", "query": "Need bulk export to CSV", "expected_format": "acknowledgment", "difficulty": "easy"},
    {"id": 13, "category": "billing", "query": "Enterprise pricing for 500 seats", "expected_format": "informational", "difficulty": "medium"},
    {"id": 14, "category": "technical", "query": "SSO SAML integration failing with Azure AD", "expected_format": "troubleshooting", "difficulty": "hard"},
    {"id": 15, "category": "general", "query": "Do you have SOC2 certification?", "expected_format": "informational", "difficulty": "easy"},
    {"id": 16, "category": "complaints", "query": "Lost 2 hours of work due to your bug", "expected_format": "empathy+action", "difficulty": "hard"},
    {"id": 17, "category": "billing", "query": "Can I get a prorated refund?", "expected_format": "acknowledgment+action", "difficulty": "medium"},
    {"id": 18, "category": "technical", "query": "Rate limiting on API - need higher limits", "expected_format": "informational", "difficulty": "medium"},
    {"id": 19, "category": "feature_request", "query": "Dark mode when?", "expected_format": "acknowledgment", "difficulty": "easy"},
    {"id": 20, "category": "general", "query": "Difference between Pro and Enterprise?", "expected_format": "informational", "difficulty": "easy"},
]


# =============================================================================
# SIMULATED MODEL RESPONSES
# =============================================================================

def simulate_base_model_scores(example):
    """Simulate base model performance (decent but inconsistent)."""
    # Base model is good at easy tasks, struggles with format/style
    difficulty_penalty = {"easy": 0, "medium": 0.1, "hard": 0.25}
    category_strength = {"general": 0.85, "technical": 0.75, "billing": 0.70, "complaints": 0.60, "feature_request": 0.80}

    base_score = category_strength.get(example["category"], 0.7)
    base_score -= difficulty_penalty[example["difficulty"]]
    base_score += random.gauss(0, 0.08)

    return {
        "accuracy": min(1.0, max(0.0, base_score + random.gauss(0, 0.05))),
        "format_compliance": min(1.0, max(0.0, 0.65 + random.gauss(0, 0.1))),  # Base model often wrong format
        "style_consistency": min(1.0, max(0.0, 0.60 + random.gauss(0, 0.1))),  # Inconsistent style
        "empathy": min(1.0, max(0.0, 0.55 + random.gauss(0, 0.1))),  # Not great at empathy
        "conciseness": min(1.0, max(0.0, 0.70 + random.gauss(0, 0.08))),
        "latency_ms": max(100, 800 + random.gauss(0, 100)),  # Large model = slow
        "tokens_used": max(50, int(350 + random.gauss(0, 80))),
    }


def simulate_finetuned_model_scores(example):
    """Simulate fine-tuned model performance (better format/style, similar accuracy)."""
    difficulty_penalty = {"easy": 0, "medium": 0.05, "hard": 0.15}
    category_strength = {"general": 0.88, "technical": 0.82, "billing": 0.85, "complaints": 0.80, "feature_request": 0.85}

    base_score = category_strength.get(example["category"], 0.8)
    base_score -= difficulty_penalty[example["difficulty"]]
    base_score += random.gauss(0, 0.05)

    return {
        "accuracy": min(1.0, max(0.0, base_score + random.gauss(0, 0.04))),
        "format_compliance": min(1.0, max(0.0, 0.92 + random.gauss(0, 0.05))),  # Much better format
        "style_consistency": min(1.0, max(0.0, 0.90 + random.gauss(0, 0.05))),  # Consistent style
        "empathy": min(1.0, max(0.0, 0.82 + random.gauss(0, 0.06))),  # Trained on empathetic responses
        "conciseness": min(1.0, max(0.0, 0.85 + random.gauss(0, 0.05))),
        "latency_ms": max(50, 200 + random.gauss(0, 30)),  # Smaller model = faster
        "tokens_used": max(30, int(180 + random.gauss(0, 40))),  # More concise
    }


# =============================================================================
# EVALUATION ENGINE
# =============================================================================

@dataclass
class EvalResult:
    example_id: int
    category: str
    difficulty: str
    base_scores: dict
    ft_scores: dict


def run_evaluation(test_set):
    """Run evaluation on both models."""
    results = []
    for example in test_set:
        base_scores = simulate_base_model_scores(example)
        ft_scores = simulate_finetuned_model_scores(example)
        results.append(EvalResult(
            example_id=example["id"],
            category=example["category"],
            difficulty=example["difficulty"],
            base_scores=base_scores,
            ft_scores=ft_scores,
        ))
    return results


def aggregate_metrics(results):
    """Aggregate metrics across all examples."""
    metrics = ["accuracy", "format_compliance", "style_consistency", "empathy", "conciseness"]

    base_agg = {m: [] for m in metrics}
    ft_agg = {m: [] for m in metrics}
    base_latency = []
    ft_latency = []
    base_tokens = []
    ft_tokens = []

    for r in results:
        for m in metrics:
            base_agg[m].append(r.base_scores[m])
            ft_agg[m].append(r.ft_scores[m])
        base_latency.append(r.base_scores["latency_ms"])
        ft_latency.append(r.ft_scores["latency_ms"])
        base_tokens.append(r.base_scores["tokens_used"])
        ft_tokens.append(r.ft_scores["tokens_used"])

    return base_agg, ft_agg, base_latency, ft_latency, base_tokens, ft_tokens


def print_comparison(results):
    """Print detailed comparison report."""
    metrics = ["accuracy", "format_compliance", "style_consistency", "empathy", "conciseness"]
    base_agg, ft_agg, base_lat, ft_lat, base_tok, ft_tok = aggregate_metrics(results)

    print(f"\n{'='*70}")
    print("  EVALUATION RESULTS: Fine-Tuned vs Base Model")
    print(f"{'='*70}")
    print(f"\n  Test set size: {len(results)} examples")

    # Overall metrics
    print(f"\n  {'Metric':<22} {'Base Model':>12} {'Fine-Tuned':>12} {'Δ':>8} {'Winner':>10}")
    print(f"  {'─'*66}")

    for m in metrics:
        base_avg = sum(base_agg[m]) / len(base_agg[m])
        ft_avg = sum(ft_agg[m]) / len(ft_agg[m])
        delta = ft_avg - base_avg
        winner = "FT ✓" if delta > 0.02 else ("Base ✓" if delta < -0.02 else "Tie")
        print(f"  {m:<22} {base_avg:>10.3f}   {ft_avg:>10.3f}   {delta:>+6.3f}   {winner:>8}")

    # Latency and cost
    base_lat_avg = sum(base_lat) / len(base_lat)
    ft_lat_avg = sum(ft_lat) / len(ft_lat)
    base_tok_avg = sum(base_tok) / len(base_tok)
    ft_tok_avg = sum(ft_tok) / len(ft_tok)

    print(f"  {'─'*66}")
    print(f"  {'latency (ms)':<22} {base_lat_avg:>10.0f}   {ft_lat_avg:>10.0f}   {ft_lat_avg-base_lat_avg:>+6.0f}   {'FT ✓':>8}")
    print(f"  {'tokens/response':<22} {base_tok_avg:>10.0f}   {ft_tok_avg:>10.0f}   {ft_tok_avg-base_tok_avg:>+6.0f}   {'FT ✓':>8}")

    # Cost estimate
    base_cost_per_1k = base_tok_avg * 0.00006  # GPT-4 pricing
    ft_cost_per_1k = ft_tok_avg * 0.000002  # Self-hosted 7B
    print(f"\n  Cost per 1K requests:")
    print(f"    Base (GPT-4 API):     ${base_cost_per_1k * 1000:.2f}")
    print(f"    Fine-tuned (7B):      ${ft_cost_per_1k * 1000:.4f}")
    print(f"    Savings:              {(1 - ft_cost_per_1k/base_cost_per_1k)*100:.0f}%")

    return base_agg, ft_agg


def print_category_breakdown(results):
    """Show per-category performance."""
    print(f"\n{'='*70}")
    print("  PER-CATEGORY BREAKDOWN")
    print(f"{'='*70}")

    categories = defaultdict(lambda: {"base": [], "ft": []})
    for r in results:
        # Overall score = average of all quality metrics
        base_avg = sum(r.base_scores[m] for m in ["accuracy", "format_compliance", "style_consistency"]) / 3
        ft_avg = sum(r.ft_scores[m] for m in ["accuracy", "format_compliance", "style_consistency"]) / 3
        categories[r.category]["base"].append(base_avg)
        categories[r.category]["ft"].append(ft_avg)

    print(f"\n  {'Category':<18} {'Base':>8} {'FT':>8} {'Improvement':>12} {'Bar'}")
    print(f"  {'─'*60}")

    for cat in sorted(categories.keys()):
        base_avg = sum(categories[cat]["base"]) / len(categories[cat]["base"])
        ft_avg = sum(categories[cat]["ft"]) / len(categories[cat]["ft"])
        improvement = (ft_avg - base_avg) / base_avg * 100
        bar = "█" * int(abs(improvement))
        direction = "+" if improvement > 0 else "-"
        print(f"  {cat:<18} {base_avg:>6.3f}   {ft_avg:>6.3f}   {direction}{abs(improvement):>9.1f}%   {bar}")


def print_difficulty_breakdown(results):
    """Show performance by difficulty."""
    print(f"\n{'='*70}")
    print("  PER-DIFFICULTY BREAKDOWN")
    print(f"{'='*70}")

    difficulties = defaultdict(lambda: {"base": [], "ft": []})
    for r in results:
        base_acc = r.base_scores["accuracy"]
        ft_acc = r.ft_scores["accuracy"]
        difficulties[r.difficulty]["base"].append(base_acc)
        difficulties[r.difficulty]["ft"].append(ft_acc)

    print(f"\n  {'Difficulty':<12} {'Base Accuracy':>14} {'FT Accuracy':>13} {'Δ':>8}")
    print(f"  {'─'*50}")

    for diff in ["easy", "medium", "hard"]:
        if diff in difficulties:
            base_avg = sum(difficulties[diff]["base"]) / len(difficulties[diff]["base"])
            ft_avg = sum(difficulties[diff]["ft"]) / len(difficulties[diff]["ft"])
            delta = ft_avg - base_avg
            print(f"  {diff:<12} {base_avg:>12.3f}   {ft_avg:>11.3f}   {delta:>+6.3f}")


def print_regression_analysis(results):
    """Identify where fine-tuned model is WORSE."""
    print(f"\n{'='*70}")
    print("  REGRESSION ANALYSIS (Where FT is worse)")
    print(f"{'='*70}")

    regressions = []
    for r in results:
        for metric in ["accuracy", "format_compliance", "style_consistency"]:
            if r.ft_scores[metric] < r.base_scores[metric] - 0.1:  # >10% worse
                regressions.append({
                    "example_id": r.example_id,
                    "category": r.category,
                    "metric": metric,
                    "base": r.base_scores[metric],
                    "ft": r.ft_scores[metric],
                    "delta": r.ft_scores[metric] - r.base_scores[metric],
                })

    if regressions:
        print(f"\n  Found {len(regressions)} regressions (FT > 10% worse than base):")
        print(f"  {'ID':>4} {'Category':<15} {'Metric':<20} {'Base':>6} {'FT':>6} {'Δ':>7}")
        print(f"  {'─'*60}")
        for reg in regressions[:10]:
            print(f"  {reg['example_id']:>4} {reg['category']:<15} {reg['metric']:<20} "
                  f"{reg['base']:>5.3f} {reg['ft']:>5.3f} {reg['delta']:>+6.3f}")
        if len(regressions) > 10:
            print(f"  ... and {len(regressions) - 10} more")
    else:
        print(f"\n  ✓ No significant regressions found!")

    print(f"\n  Regression rate: {len(regressions)}/{len(results)*3} metric-example pairs "
          f"({len(regressions)/(len(results)*3)*100:.1f}%)")
    return regressions


def deployment_recommendation(results, regressions):
    """Generate final deployment recommendation."""
    print(f"\n{'='*70}")
    print("  DEPLOYMENT RECOMMENDATION")
    print(f"{'='*70}")

    metrics = ["accuracy", "format_compliance", "style_consistency", "empathy", "conciseness"]
    improvements = []
    for m in metrics:
        base_vals = [r.base_scores[m] for r in results]
        ft_vals = [r.ft_scores[m] for r in results]
        base_avg = sum(base_vals) / len(base_vals)
        ft_avg = sum(ft_vals) / len(ft_vals)
        improvements.append((ft_avg - base_avg) / base_avg * 100)

    avg_improvement = sum(improvements) / len(improvements)
    regression_rate = len(regressions) / (len(results) * len(metrics))

    # Scoring
    score = 0
    reasons = []

    if avg_improvement > 10:
        score += 3
        reasons.append(f"✓ Strong average improvement: {avg_improvement:.1f}%")
    elif avg_improvement > 5:
        score += 2
        reasons.append(f"✓ Moderate improvement: {avg_improvement:.1f}%")
    elif avg_improvement > 0:
        score += 1
        reasons.append(f"~ Marginal improvement: {avg_improvement:.1f}%")
    else:
        reasons.append(f"✗ No improvement: {avg_improvement:.1f}%")

    if regression_rate < 0.05:
        score += 2
        reasons.append(f"✓ Low regression rate: {regression_rate*100:.1f}%")
    elif regression_rate < 0.15:
        score += 1
        reasons.append(f"~ Moderate regression rate: {regression_rate*100:.1f}%")
    else:
        reasons.append(f"✗ High regression rate: {regression_rate*100:.1f}%")

    # Latency improvement
    base_lat = sum(r.base_scores["latency_ms"] for r in results) / len(results)
    ft_lat = sum(r.ft_scores["latency_ms"] for r in results) / len(results)
    if ft_lat < base_lat * 0.5:
        score += 2
        reasons.append(f"✓ Major latency improvement: {base_lat:.0f}ms → {ft_lat:.0f}ms")
    elif ft_lat < base_lat:
        score += 1
        reasons.append(f"✓ Latency improvement: {base_lat:.0f}ms → {ft_lat:.0f}ms")

    print(f"\n  Evaluation Factors:")
    for reason in reasons:
        print(f"    {reason}")

    print(f"\n  Confidence Score: {score}/7")
    print(f"\n  ┌─────────────────────────────────────────┐")
    if score >= 5:
        print(f"  │  RECOMMENDATION: ✓ DEPLOY              │")
        print(f"  │  Fine-tuned model is clearly better.    │")
        print(f"  │  Proceed with canary deployment.        │")
    elif score >= 3:
        print(f"  │  RECOMMENDATION: ~ CAUTIOUS DEPLOY     │")
        print(f"  │  Improvement exists but modest.          │")
        print(f"  │  Deploy with careful monitoring.        │")
    else:
        print(f"  │  RECOMMENDATION: ✗ DO NOT DEPLOY       │")
        print(f"  │  Insufficient improvement over base.    │")
        print(f"  │  Iterate on data/training.             │")
    print(f"  └─────────────────────────────────────────┘")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("  FINE-TUNED MODEL EVALUATION PIPELINE")
    print("=" * 70)
    print(f"\n  Comparing: Base Model (GPT-4) vs Fine-Tuned (Llama 7B + LoRA)")
    print(f"  Test set: {len(TEST_EXAMPLES)} examples across 5 categories")

    # Run evaluation
    results = run_evaluation(TEST_EXAMPLES)

    # Print all reports
    print_comparison(results)
    print_category_breakdown(results)
    print_difficulty_breakdown(results)
    regressions = print_regression_analysis(results)
    deployment_recommendation(results, regressions)

    # Save results
    output = {
        "summary": {
            "test_size": len(results),
            "regressions": len(regressions),
        },
        "per_example": [
            {
                "id": r.example_id,
                "category": r.category,
                "difficulty": r.difficulty,
                "base_accuracy": r.base_scores["accuracy"],
                "ft_accuracy": r.ft_scores["accuracy"],
            }
            for r in results
        ]
    }

    with open("evaluation_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved to: evaluation_results.json")


if __name__ == "__main__":
    main()
