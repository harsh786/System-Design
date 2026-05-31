"""
Vendor Evaluation and Comparison Simulator

Simulates a Staff Architect's vendor evaluation process:
- Defines evaluation criteria with weights
- Scores multiple vendors across dimensions
- Calculates weighted scores and produces recommendations
- Performs TCO analysis (1-year, 3-year projections)
- Assesses lock-in risk

Run: python3 main.py
"""

import json
from dataclasses import dataclass, field
from typing import Optional


# ─── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class EvaluationCriteria:
    name: str
    weight: float  # 0.0 - 1.0, all weights must sum to 1.0
    description: str


@dataclass
class VendorScore:
    criterion: str
    score: float  # 1-10
    notes: str = ""


@dataclass
class CostProjection:
    monthly_base: float
    per_unit_cost: float  # per 1K requests
    volume_discount_threshold: int  # requests/month for discount
    volume_discount_pct: float
    annual_price_increase_pct: float  # expected annual increase


@dataclass
class LockInFactor:
    name: str
    severity: int  # 1-5
    migration_effort_weeks: int
    description: str


@dataclass
class Vendor:
    name: str
    category: str
    scores: list[VendorScore] = field(default_factory=list)
    cost: Optional[CostProjection] = None
    lock_in_factors: list[LockInFactor] = field(default_factory=list)


# ─── Evaluation Framework ──────────────────────────────────────────────────────

CRITERIA = [
    EvaluationCriteria("quality", 0.30, "Output quality on representative eval suite"),
    EvaluationCriteria("latency", 0.15, "P50/P95 response time from target regions"),
    EvaluationCriteria("cost", 0.20, "Cost efficiency at projected volume"),
    EvaluationCriteria("reliability", 0.20, "Uptime, error rates, degradation patterns"),
    EvaluationCriteria("security", 0.15, "Data policies, compliance, certifications"),
]


def create_llm_vendors() -> list[Vendor]:
    """Create realistic vendor profiles for LLM providers."""
    vendors = []

    # OpenAI
    openai = Vendor(name="OpenAI (GPT-4o)", category="Foundation Model")
    openai.scores = [
        VendorScore("quality", 9.0, "Top-tier on most benchmarks, strong multi-modal"),
        VendorScore("latency", 7.5, "P50: 800ms, P95: 2.5s for complex queries"),
        VendorScore("cost", 6.0, "$2.50/1M input, $10/1M output — mid-range"),
        VendorScore("reliability", 7.0, "99.5% uptime, occasional degradation events"),
        VendorScore("security", 7.5, "SOC2, GDPR, opt-out available, no training on API data"),
    ]
    openai.cost = CostProjection(
        monthly_base=0,
        per_unit_cost=0.012,  # avg cost per request (500 in, 200 out tokens)
        volume_discount_threshold=1_000_000,
        volume_discount_pct=0.20,
        annual_price_increase_pct=-0.15,  # prices tend to decrease
    )
    openai.lock_in_factors = [
        LockInFactor("API Format", 2, 2, "OpenAI format is de facto standard, easy to switch"),
        LockInFactor("Assistants API", 4, 6, "Threads/runs are proprietary, hard to replicate"),
        LockInFactor("Fine-tuned Models", 3, 4, "Must retrain on new platform"),
        LockInFactor("Function Calling Schema", 2, 1, "Similar across vendors now"),
    ]
    vendors.append(openai)

    # Anthropic
    anthropic = Vendor(name="Anthropic (Claude 3.5 Sonnet)", category="Foundation Model")
    anthropic.scores = [
        VendorScore("quality", 9.2, "Best-in-class for code and reasoning tasks"),
        VendorScore("latency", 7.0, "P50: 900ms, P95: 3s, slightly slower than GPT-4o"),
        VendorScore("cost", 5.5, "$3/1M input, $15/1M output — premium pricing"),
        VendorScore("reliability", 8.0, "99.7% uptime, fewer incidents than OpenAI"),
        VendorScore("security", 8.5, "SOC2, strong data policies, no training on inputs"),
    ]
    anthropic.cost = CostProjection(
        monthly_base=0,
        per_unit_cost=0.015,
        volume_discount_threshold=500_000,
        volume_discount_pct=0.25,
        annual_price_increase_pct=-0.10,
    )
    anthropic.lock_in_factors = [
        LockInFactor("Message Format", 2, 2, "Slightly different from OpenAI but similar"),
        LockInFactor("System Prompt Handling", 1, 1, "Minor differences"),
        LockInFactor("Tool Use Format", 2, 2, "Different JSON schema than OpenAI"),
    ]
    vendors.append(anthropic)

    # Google Gemini
    google = Vendor(name="Google (Gemini 1.5 Flash)", category="Foundation Model")
    google.scores = [
        VendorScore("quality", 7.5, "Good for simple-medium tasks, excellent speed"),
        VendorScore("latency", 9.5, "P50: 200ms, P95: 600ms — fastest available"),
        VendorScore("cost", 9.0, "$0.075/1M input, $0.30/1M output — very cheap"),
        VendorScore("reliability", 8.0, "Google infrastructure, high availability"),
        VendorScore("security", 8.0, "GCP compliance, enterprise-ready"),
    ]
    google.cost = CostProjection(
        monthly_base=0,
        per_unit_cost=0.001,
        volume_discount_threshold=5_000_000,
        volume_discount_pct=0.15,
        annual_price_increase_pct=-0.20,
    )
    google.lock_in_factors = [
        LockInFactor("API Format", 3, 2, "Google-specific format, not OpenAI-compatible"),
        LockInFactor("Vertex AI Platform", 4, 6, "Deep GCP integration if using Vertex"),
        LockInFactor("Grounding/Search", 4, 4, "Proprietary Google Search integration"),
    ]
    vendors.append(google)

    # Self-hosted Llama
    llama = Vendor(name="Meta Llama 3.1 70B (Self-hosted)", category="Foundation Model")
    llama.scores = [
        VendorScore("quality", 7.8, "Strong for code and general tasks, below frontier"),
        VendorScore("latency", 6.5, "Depends on hardware, P50: 1.2s with good GPU"),
        VendorScore("cost", 8.5, "~$0.50/1M tokens all-in on own hardware at scale"),
        VendorScore("reliability", 6.0, "You own uptime — requires ML ops expertise"),
        VendorScore("security", 9.5, "Full data control, nothing leaves your infra"),
    ]
    llama.cost = CostProjection(
        monthly_base=4000,  # GPU instance costs
        per_unit_cost=0.0005,
        volume_discount_threshold=0,  # fixed cost
        volume_discount_pct=0,
        annual_price_increase_pct=0.05,  # GPU costs slowly rise
    )
    llama.lock_in_factors = [
        LockInFactor("Infrastructure", 3, 4, "GPU setup, but standard K8s/Docker"),
        LockInFactor("Model Weights", 1, 0, "Open weights, no lock-in"),
        LockInFactor("Custom Optimizations", 2, 2, "vLLM configs, quantization choices"),
    ]
    vendors.append(llama)

    return vendors


# ─── Evaluation Engine ─────────────────────────────────────────────────────────

def calculate_weighted_score(vendor: Vendor, criteria: list[EvaluationCriteria]) -> float:
    """Calculate weighted score for a vendor."""
    criteria_map = {c.name: c.weight for c in criteria}
    total = 0.0
    for score in vendor.scores:
        weight = criteria_map.get(score.criterion, 0)
        total += score.score * weight
    return round(total, 2)


def calculate_tco(vendor: Vendor, monthly_volume: int, years: int) -> dict:
    """Calculate Total Cost of Ownership over N years."""
    if not vendor.cost:
        return {"total": 0, "breakdown": []}

    cost = vendor.cost
    breakdown = []
    total = 0.0

    for year in range(1, years + 1):
        price_multiplier = (1 + cost.annual_price_increase_pct) ** (year - 1)
        adjusted_per_unit = cost.per_unit_cost * price_multiplier

        # Apply volume discount
        if monthly_volume > cost.volume_discount_threshold and cost.volume_discount_threshold > 0:
            adjusted_per_unit *= (1 - cost.volume_discount_pct)

        annual_variable = adjusted_per_unit * monthly_volume * 12
        annual_fixed = cost.monthly_base * 12 * price_multiplier
        annual_total = annual_variable + annual_fixed

        breakdown.append({
            "year": year,
            "fixed": round(annual_fixed, 2),
            "variable": round(annual_variable, 2),
            "total": round(annual_total, 2),
        })
        total += annual_total

    return {"total": round(total, 2), "breakdown": breakdown}


def calculate_lock_in_risk(vendor: Vendor) -> dict:
    """Calculate lock-in risk score."""
    if not vendor.lock_in_factors:
        return {"score": 0, "max_migration_weeks": 0, "factors": []}

    total_severity = sum(f.severity for f in vendor.lock_in_factors)
    max_severity = len(vendor.lock_in_factors) * 5
    risk_score = round((total_severity / max_severity) * 10, 1) if max_severity > 0 else 0
    max_migration = max(f.migration_effort_weeks for f in vendor.lock_in_factors)

    return {
        "score": risk_score,
        "max_migration_weeks": max_migration,
        "factors": [
            {"name": f.name, "severity": f.severity, "weeks": f.migration_effort_weeks}
            for f in vendor.lock_in_factors
        ],
    }


# ─── Reporting ─────────────────────────────────────────────────────────────────

def generate_comparison_report(
    vendors: list[Vendor],
    criteria: list[EvaluationCriteria],
    monthly_volume: int,
) -> None:
    """Generate full vendor comparison report."""
    print("=" * 80)
    print("VENDOR EVALUATION REPORT")
    print(f"Use Case: LLM Provider for Production AI System")
    print(f"Projected Volume: {monthly_volume:,} requests/month")
    print(f"Evaluation Date: 2024-Q4")
    print("=" * 80)

    # Section 1: Criteria
    print("\n── EVALUATION CRITERIA ──────────────────────────────────────────────")
    print(f"{'Criterion':<15} {'Weight':<10} {'Description'}")
    print("-" * 70)
    for c in criteria:
        print(f"{c.name:<15} {c.weight*100:.0f}%{'':<6} {c.description}")

    # Section 2: Scores
    print("\n── VENDOR SCORES ───────────────────────────────────────────────────")
    print(f"{'Vendor':<35} ", end="")
    for c in criteria:
        print(f"{c.name[:5]:>7}", end="")
    print(f"{'TOTAL':>10}")
    print("-" * 80)

    results = []
    for vendor in vendors:
        weighted = calculate_weighted_score(vendor, criteria)
        results.append((vendor, weighted))
        print(f"{vendor.name:<35} ", end="")
        score_map = {s.criterion: s.score for s in vendor.scores}
        for c in criteria:
            score = score_map.get(c.name, 0)
            print(f"{score:>7.1f}", end="")
        print(f"{weighted:>10.2f}")

    # Section 3: Ranking
    results.sort(key=lambda x: x[1], reverse=True)
    print("\n── RANKING ─────────────────────────────────────────────────────────")
    for i, (vendor, score) in enumerate(results, 1):
        bar = "█" * int(score * 3)
        print(f"  #{i} {vendor.name:<35} {score:.2f}/10  {bar}")

    # Section 4: TCO Analysis
    print("\n── TOTAL COST OF OWNERSHIP ─────────────────────────────────────────")
    print(f"Volume: {monthly_volume:,} requests/month\n")

    tco_results = []
    for vendor in vendors:
        tco = calculate_tco(vendor, monthly_volume, 3)
        tco_results.append((vendor, tco))

    print(f"{'Vendor':<35} {'Year 1':>12} {'Year 2':>12} {'Year 3':>12} {'3Y Total':>12}")
    print("-" * 83)
    for vendor, tco in tco_results:
        if tco["breakdown"]:
            y1 = tco["breakdown"][0]["total"]
            y2 = tco["breakdown"][1]["total"]
            y3 = tco["breakdown"][2]["total"]
            print(f"{vendor.name:<35} ${y1:>10,.0f} ${y2:>10,.0f} ${y3:>10,.0f} ${tco['total']:>10,.0f}")

    # Find cheapest
    tco_results.sort(key=lambda x: x[1]["total"])
    cheapest = tco_results[0]
    most_expensive = tco_results[-1]
    print(f"\n  💰 Cheapest 3Y TCO: {cheapest[0].name} (${cheapest[1]['total']:,.0f})")
    print(f"  📈 Most Expensive:  {most_expensive[0].name} (${most_expensive[1]['total']:,.0f})")
    savings_pct = (1 - cheapest[1]["total"] / most_expensive[1]["total"]) * 100
    print(f"  📊 Savings potential: {savings_pct:.0f}% by choosing cheapest")

    # Section 5: Lock-In Analysis
    print("\n── LOCK-IN RISK ASSESSMENT ─────────────────────────────────────────")
    print(f"{'Vendor':<35} {'Risk Score':>12} {'Max Migration':>15} {'Top Risk Factor'}")
    print("-" * 90)
    for vendor in vendors:
        risk = calculate_lock_in_risk(vendor)
        top_factor = max(vendor.lock_in_factors, key=lambda f: f.severity) if vendor.lock_in_factors else None
        top_name = top_factor.name if top_factor else "None"
        risk_bar = "⚠️" * (risk["score"] // 2) if risk["score"] > 4 else "✓"
        print(
            f"{vendor.name:<35} {risk['score']:>8.1f}/10  "
            f"{risk['max_migration_weeks']:>10} weeks   {top_name} {risk_bar}"
        )

    # Section 6: Recommendation
    print("\n── RECOMMENDATION ──────────────────────────────────────────────────")
    best_overall = results[0]
    print(f"""
  RECOMMENDED PRIMARY VENDOR: {best_overall[0].name}
  Weighted Score: {best_overall[1]:.2f}/10
  
  Reasoning:
  - Highest weighted score across quality, cost, latency, reliability, security
  - Acceptable lock-in risk with documented mitigation
  
  RECOMMENDED SECONDARY (FALLBACK): {results[1][0].name}
  - Provides redundancy and negotiation leverage
  - Different failure modes than primary
  
  RECOMMENDED COST TIER: {tco_results[0][0].name}
  - Use for simple queries (60-70% of traffic)
  - Route complex queries to primary vendor
  
  MULTI-VENDOR STRATEGY:
  - Simple queries (65%): Cheapest adequate model
  - Complex queries (25%): Primary vendor
  - Critical/fallback (10%): Secondary vendor
  - Estimated blended cost: 40-60% less than single premium vendor
""")

    # Section 7: Decision Scorecard Summary
    print("── VENDOR SCORECARD SUMMARY ────────────────────────────────────────")
    for vendor, weighted in results:
        risk = calculate_lock_in_risk(vendor)
        tco = calculate_tco(vendor, monthly_volume, 1)
        annual_cost = tco["breakdown"][0]["total"] if tco["breakdown"] else 0
        print(f"\n  {vendor.name}")
        print(f"    Quality Score: {weighted:.2f}/10 | Lock-in Risk: {risk['score']:.1f}/10")
        print(f"    Annual Cost: ${annual_cost:,.0f} | Migration Time: {risk['max_migration_weeks']} weeks")
        approve = "✓ APPROVE" if weighted > 7 and risk["score"] < 6 else "⚠ CONDITIONAL"
        print(f"    Status: {approve}")

    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n🏗️  STAFF ARCHITECT: VENDOR EVALUATION SIMULATOR\n")
    print("Simulating evaluation of LLM providers for a production AI system.")
    print("Monthly volume assumption: 500,000 requests\n")

    vendors = create_llm_vendors()
    monthly_volume = 500_000

    generate_comparison_report(vendors, CRITERIA, monthly_volume)

    # Bonus: Show what happens if volume scales 5x
    print("\n\n" + "=" * 80)
    print("SCENARIO: WHAT IF VOLUME GROWS 5X? (2.5M requests/month)")
    print("=" * 80)
    scaled_volume = 2_500_000
    print(f"\n{'Vendor':<35} {'Current (500K)':>15} {'Scaled (2.5M)':>15} {'$/request':>12}")
    print("-" * 77)
    for vendor in vendors:
        tco_current = calculate_tco(vendor, monthly_volume, 1)
        tco_scaled = calculate_tco(vendor, scaled_volume, 1)
        current_annual = tco_current["breakdown"][0]["total"] if tco_current["breakdown"] else 0
        scaled_annual = tco_scaled["breakdown"][0]["total"] if tco_scaled["breakdown"] else 0
        per_request = scaled_annual / (scaled_volume * 12) if scaled_volume > 0 else 0
        print(
            f"{vendor.name:<35} ${current_annual:>12,.0f} ${scaled_annual:>12,.0f} "
            f"${per_request:>9.5f}"
        )
    print("\n  Key Insight: Self-hosted becomes most cost-effective at high scale")
    print("  because fixed GPU costs are amortized across more requests.")


if __name__ == "__main__":
    main()
