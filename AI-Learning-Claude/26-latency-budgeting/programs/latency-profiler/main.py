"""
Latency Profiler for AI Pipeline
Profiles each component and displays a waterfall diagram.
"""

import time
import random
from dataclasses import dataclass


@dataclass
class ComponentProfile:
    name: str
    start_ms: float
    duration_ms: float
    category: str

    @property
    def end_ms(self) -> float:
        return self.start_ms + self.duration_ms


def simulate_component(name: str, mean_ms: float, std_ms: float) -> float:
    """Simulate a component with realistic latency (normal distribution)."""
    latency = max(1.0, random.gauss(mean_ms, std_ms))
    time.sleep(latency / 1000.0)
    return latency


def profile_pipeline(num_runs: int = 1) -> list[ComponentProfile]:
    """Profile a full AI pipeline execution."""
    components = [
        ("Network (in)", 20, 5, "infrastructure"),
        ("Auth/Gateway", 5, 2, "infrastructure"),
        ("Input Guardrails", 80, 30, "guardrails"),
        ("Query Classification", 150, 50, "reasoning"),
        ("Embedding Generation", 30, 10, "retrieval"),
        ("Vector Search", 40, 15, "retrieval"),
        ("Reranking", 70, 20, "retrieval"),
        ("Context Assembly", 5, 2, "retrieval"),
        ("LLM Prefill (TTFT)", 180, 60, "llm"),
        ("LLM Decode (tokens)", 1800, 500, "llm"),
        ("Output Guardrails", 90, 30, "guardrails"),
        ("Serialization", 5, 2, "infrastructure"),
        ("Network (out)", 20, 5, "infrastructure"),
    ]

    profiles = []
    elapsed = 0.0

    for name, mean, std, category in components:
        start = elapsed
        # Simulate without actually sleeping (for speed)
        duration = max(1.0, random.gauss(mean, std))
        profiles.append(ComponentProfile(name, start, duration, category))
        elapsed += duration

    return profiles


def print_waterfall(profiles: list[ComponentProfile]):
    """Print a text-based waterfall diagram."""
    total = sum(p.duration_ms for p in profiles)
    max_bar_width = 50
    max_name_len = max(len(p.name) for p in profiles)

    # Category colors (ANSI)
    colors = {
        "infrastructure": "\033[36m",  # cyan
        "guardrails": "\033[33m",      # yellow
        "retrieval": "\033[32m",       # green
        "reasoning": "\033[35m",       # magenta
        "llm": "\033[31m",            # red
    }
    reset = "\033[0m"

    print("\n" + "=" * 80)
    print("LATENCY PROFILER — AI Pipeline Waterfall")
    print("=" * 80)
    print()
    print(f"{'Component':<{max_name_len}}  {'Duration':>8}  {'%':>5}  {'Waterfall'}")
    print(f"{'-' * max_name_len}  {'-' * 8}  {'-' * 5}  {'-' * max_bar_width}")

    cumulative = 0.0
    for p in profiles:
        pct = (p.duration_ms / total) * 100
        bar_width = int((p.duration_ms / total) * max_bar_width)
        offset = int((cumulative / total) * max_bar_width)

        color = colors.get(p.category, "")
        bar = " " * offset + color + "█" * max(1, bar_width) + reset

        print(f"{p.name:<{max_name_len}}  {p.duration_ms:>7.1f}ms  {pct:>4.1f}%  {bar}")
        cumulative += p.duration_ms

    print(f"{'-' * max_name_len}  {'-' * 8}  {'-' * 5}  {'-' * max_bar_width}")
    print(f"{'TOTAL':<{max_name_len}}  {total:>7.1f}ms  100.0%")


def print_bottleneck_analysis(profiles: list[ComponentProfile]):
    """Identify and report bottlenecks."""
    total = sum(p.duration_ms for p in profiles)
    sorted_profiles = sorted(profiles, key=lambda p: p.duration_ms, reverse=True)

    print("\n" + "=" * 80)
    print("BOTTLENECK ANALYSIS")
    print("=" * 80)
    print()
    print("Components ranked by latency contribution:")
    print()

    cumulative_pct = 0.0
    for i, p in enumerate(sorted_profiles, 1):
        pct = (p.duration_ms / total) * 100
        cumulative_pct += pct
        marker = " ← BOTTLENECK" if i == 1 else ""
        marker = marker or (" ← 80% cumulative" if cumulative_pct >= 80 and cumulative_pct - pct < 80 else "")
        print(f"  {i:>2}. {p.name:<25} {p.duration_ms:>7.1f}ms ({pct:>5.1f}%) [cum: {cumulative_pct:>5.1f}%]{marker}")

    print()
    print(f"Top bottleneck: {sorted_profiles[0].name} ({sorted_profiles[0].duration_ms:.1f}ms)")
    print(f"  → This single component is {sorted_profiles[0].duration_ms/total*100:.1f}% of total latency")
    print(f"  → Reducing it by 50% saves {sorted_profiles[0].duration_ms/2:.0f}ms")

    # Category breakdown
    print("\n" + "-" * 40)
    print("Category breakdown:")
    categories = {}
    for p in profiles:
        categories.setdefault(p.category, 0.0)
        categories[p.category] += p.duration_ms

    for cat, dur in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat:<15} {dur:>7.1f}ms ({dur/total*100:>5.1f}%)")


def print_budget_check(profiles: list[ComponentProfile]):
    """Check against budget allocations."""
    budgets = {
        "Network (in)": 30,
        "Auth/Gateway": 10,
        "Input Guardrails": 100,
        "Query Classification": 200,
        "Embedding Generation": 50,
        "Vector Search": 50,
        "Reranking": 100,
        "Context Assembly": 10,
        "LLM Prefill (TTFT)": 300,
        "LLM Decode (tokens)": 2000,
        "Output Guardrails": 100,
        "Serialization": 10,
        "Network (out)": 30,
    }

    print("\n" + "=" * 80)
    print("BUDGET COMPLIANCE CHECK (SLO: 3000ms)")
    print("=" * 80)
    print()
    print(f"{'Component':<25} {'Actual':>8} {'Budget':>8} {'Status':>10}")
    print(f"{'-'*25} {'-'*8} {'-'*8} {'-'*10}")

    violations = 0
    for p in profiles:
        budget = budgets.get(p.name, 999999)
        status = "✓ OK" if p.duration_ms <= budget else "✗ OVER"
        if p.duration_ms > budget:
            violations += 1
        print(f"{p.name:<25} {p.duration_ms:>7.1f}ms {budget:>7}ms {status:>10}")

    total = sum(p.duration_ms for p in profiles)
    total_budget = 3000
    total_status = "✓ WITHIN SLO" if total <= total_budget else "✗ EXCEEDS SLO"
    print(f"{'-'*25} {'-'*8} {'-'*8} {'-'*10}")
    print(f"{'TOTAL':<25} {total:>7.1f}ms {total_budget:>7}ms {total_status:>10}")
    print(f"\nBudget violations: {violations}/{len(profiles)} components")


def main():
    random.seed(42)

    print("\n🔬 Running AI Pipeline Latency Profiler...")
    print("   Simulating a single RAG request with all components\n")

    profiles = profile_pipeline()

    print_waterfall(profiles)
    print_bottleneck_analysis(profiles)
    print_budget_check(profiles)

    # Run multiple times to show variability
    print("\n" + "=" * 80)
    print("VARIABILITY ANALYSIS (10 runs)")
    print("=" * 80)
    print()

    all_totals = []
    component_times = {}
    for _ in range(10):
        run = profile_pipeline()
        total = sum(p.duration_ms for p in run)
        all_totals.append(total)
        for p in run:
            component_times.setdefault(p.name, []).append(p.duration_ms)

    all_totals.sort()
    print(f"  P50 total latency: {all_totals[4]:.0f}ms")
    print(f"  P90 total latency: {all_totals[8]:.0f}ms")
    print(f"  P95 (max of 10):   {all_totals[9]:.0f}ms")
    print(f"  Range:             {all_totals[0]:.0f}ms — {all_totals[9]:.0f}ms")
    print(f"  Variability:       ±{(all_totals[9]-all_totals[0])/2:.0f}ms")

    print("\n  Most variable components:")
    variability = []
    for name, times in component_times.items():
        spread = max(times) - min(times)
        variability.append((name, spread))
    variability.sort(key=lambda x: -x[1])
    for name, spread in variability[:5]:
        print(f"    {name:<25} spread: {spread:.1f}ms")


if __name__ == "__main__":
    main()
