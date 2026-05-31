"""
Bottleneck Detector for AI Pipeline Latency
Generates simulated traces and identifies optimization targets.
"""

import random
import statistics
from dataclasses import dataclass


@dataclass
class ComponentConfig:
    name: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    budget_ms: float
    optimization_actions: list[str]


def get_components() -> list[ComponentConfig]:
    return [
        ComponentConfig("Auth/Gateway", 5, 12, 25, 10,
                       ["Cache JWT validation", "Use local validation"]),
        ComponentConfig("Input Guardrails", 80, 200, 400, 100,
                       ["Use rule-based for common patterns", "Async for LLM guardrails", "Cache repeated checks"]),
        ComponentConfig("Embedding", 28, 50, 80, 50,
                       ["Cache frequent query embeddings", "Use local model", "Batch requests"]),
        ComponentConfig("Vector Search", 35, 80, 150, 50,
                       ["Reduce ef_search", "Add more replicas", "Pre-filter to reduce search space"]),
        ComponentConfig("Reranking", 65, 130, 200, 100,
                       ["Reduce candidates (20→10)", "Use faster model", "Skip for high-confidence results"]),
        ComponentConfig("Context Assembly", 4, 8, 15, 10,
                       ["Pre-format documents", "Reduce context size"]),
        ComponentConfig("LLM Prefill", 150, 350, 600, 300,
                       ["KV cache / prefix caching", "Reduce prompt length", "Prompt compression"]),
        ComponentConfig("LLM Decode", 1500, 3500, 6000, 2000,
                       ["Set max_tokens", "Use smaller model for simple queries", "Speculative decoding"]),
        ComponentConfig("Output Guardrails", 70, 180, 350, 100,
                       ["Run async (after streaming starts)", "Rule-based for common checks", "Skip for trusted contexts"]),
        ComponentConfig("Network/Serialization", 30, 60, 120, 50,
                       ["Geographic routing", "Connection pooling", "Use protobuf"]),
    ]


def generate_latency_sample(p50: float, p95: float, p99: float) -> float:
    """Generate a realistic latency sample from a log-normal-ish distribution."""
    # Use a weighted random to approximate the distribution
    r = random.random()
    if r < 0.50:
        # Below P50
        return random.uniform(p50 * 0.5, p50)
    elif r < 0.85:
        # P50 to P90-ish
        return random.uniform(p50, p95 * 0.8)
    elif r < 0.95:
        # P90 to P95
        return random.uniform(p95 * 0.8, p95)
    elif r < 0.99:
        # P95 to P99
        return random.uniform(p95, p99)
    else:
        # Above P99 (tail)
        return random.uniform(p99, p99 * 1.5)


def generate_traces(components: list[ComponentConfig], num_traces: int = 100) -> list[dict[str, float]]:
    """Generate simulated request traces."""
    traces = []
    for _ in range(num_traces):
        trace = {}
        for comp in components:
            trace[comp.name] = generate_latency_sample(comp.p50_ms, comp.p95_ms, comp.p99_ms)
        trace["_total"] = sum(v for k, v in trace.items() if not k.startswith("_"))
        traces.append(trace)
    return traces


def percentile(values: list[float], pct: int) -> float:
    """Calculate percentile."""
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * pct / 100)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def analyze_bottlenecks(components: list[ComponentConfig], traces: list[dict[str, float]]):
    """Analyze traces to find bottlenecks."""
    print("\n" + "=" * 95)
    print(f"BOTTLENECK ANALYSIS REPORT — {len(traces)} traces analyzed")
    print("=" * 95)

    # Overall latency distribution
    totals = [t["_total"] for t in traces]
    print(f"\n{'OVERALL LATENCY DISTRIBUTION':}")
    print(f"  P50:  {percentile(totals, 50):>7.0f}ms")
    print(f"  P75:  {percentile(totals, 75):>7.0f}ms")
    print(f"  P90:  {percentile(totals, 90):>7.0f}ms")
    print(f"  P95:  {percentile(totals, 95):>7.0f}ms")
    print(f"  P99:  {percentile(totals, 99):>7.0f}ms")
    print(f"  Max:  {max(totals):>7.0f}ms")
    print(f"  SLO (3000ms P95): {'✓ MET' if percentile(totals, 95) <= 3000 else '✗ VIOLATED'}")

    # Per-component percentiles
    print(f"\n{'─' * 95}")
    print(f"{'PER-COMPONENT LATENCY PERCENTILES':}")
    print(f"\n{'Component':<22} {'P50':>7} {'P95':>7} {'P99':>7} {'Budget':>7} {'P95 Status':>12} {'% of P95 Total':>14}")
    print(f"{'-'*22} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*12} {'-'*14}")

    p95_total = percentile(totals, 95)
    component_contributions = []

    for comp in components:
        values = [t[comp.name] for t in traces]
        p50 = percentile(values, 50)
        p95 = percentile(values, 95)
        p99 = percentile(values, 99)
        status = "OK" if p95 <= comp.budget_ms else "OVER"
        contribution = p95 / p95_total * 100

        component_contributions.append((comp, p95, contribution))

        print(f"{comp.name:<22} {p50:>6.0f}ms {p95:>6.0f}ms {p99:>6.0f}ms {comp.budget_ms:>6.0f}ms {status:>12} {contribution:>13.1f}%")

    # Rank by contribution to P95
    print(f"\n{'─' * 95}")
    print("BOTTLENECK RANKING (by contribution to P95 latency):")
    print()

    component_contributions.sort(key=lambda x: -x[1])
    cumulative = 0.0

    for rank, (comp, p95_val, contrib) in enumerate(component_contributions, 1):
        cumulative += contrib
        bar_width = int(contrib / 2)
        bar = "█" * bar_width
        marker = ""
        if rank == 1:
            marker = " ← #1 BOTTLENECK"
        elif cumulative <= 85 and cumulative + contrib > 85:
            marker = " ← 80% mark"

        print(f"  {rank:>2}. {comp.name:<22} {p95_val:>6.0f}ms ({contrib:>5.1f}%) {bar}{marker}")

    # Recommendations
    print(f"\n{'─' * 95}")
    print("OPTIMIZATION RECOMMENDATIONS (priority order):")
    print()

    for rank, (comp, p95_val, contrib) in enumerate(component_contributions[:5], 1):
        over_budget = p95_val - comp.budget_ms
        potential_savings = over_budget if over_budget > 0 else p95_val * 0.3

        print(f"  Priority #{rank}: {comp.name}")
        print(f"    Current P95: {p95_val:.0f}ms | Budget: {comp.budget_ms:.0f}ms | Over by: {max(0, over_budget):.0f}ms")
        print(f"    Potential savings: {potential_savings:.0f}ms ({potential_savings/p95_total*100:.1f}% of total)")
        print(f"    Actions:")
        for action in comp.optimization_actions:
            print(f"      • {action}")
        print()

    # Correlation analysis: which component most correlates with slow requests?
    print(f"{'─' * 95}")
    print("TAIL LATENCY CORRELATION (which component causes slow requests?):")
    print()

    # Get the slowest 5% of traces
    sorted_traces = sorted(traces, key=lambda t: t["_total"])
    slow_traces = sorted_traces[int(len(sorted_traces) * 0.95):]
    fast_traces = sorted_traces[:int(len(sorted_traces) * 0.50)]

    print(f"  Comparing slowest 5% of requests vs fastest 50%:")
    print(f"  {'Component':<22} {'Fast avg':>9} {'Slow avg':>9} {'Ratio':>7} {'Cause?':>7}")
    print(f"  {'-'*22} {'-'*9} {'-'*9} {'-'*7} {'-'*7}")

    ratios = []
    for comp in components:
        fast_avg = statistics.mean(t[comp.name] for t in fast_traces)
        slow_avg = statistics.mean(t[comp.name] for t in slow_traces)
        ratio = slow_avg / fast_avg if fast_avg > 0 else 0
        is_cause = "YES" if ratio > 2.5 else ("maybe" if ratio > 1.8 else "")
        ratios.append((comp.name, ratio))
        print(f"  {comp.name:<22} {fast_avg:>8.0f}ms {slow_avg:>8.0f}ms {ratio:>6.1f}x {is_cause:>7}")

    print()
    top_cause = max(ratios, key=lambda x: x[1])
    print(f"  → Primary tail latency driver: {top_cause[0]} ({top_cause[1]:.1f}x slower in tail)")
    print(f"    This component's variance most explains why some requests are slow.")


def main():
    random.seed(42)

    print("\n🔍 AI Pipeline Bottleneck Detector")
    print("   Generating and analyzing 100 simulated request traces\n")

    components = get_components()
    traces = generate_traces(components, num_traces=100)

    analyze_bottlenecks(components, traces)

    # Summary
    totals = [t["_total"] for t in traces]
    p95 = percentile(totals, 95)
    print("\n" + "=" * 95)
    print("EXECUTIVE SUMMARY")
    print("=" * 95)
    print(f"""
  Current P95 latency: {p95:.0f}ms (SLO: 3000ms) {'— MEETING SLO' if p95 <= 3000 else '— SLO VIOLATED'}
  
  Top 3 actions to reduce P95 latency:
  1. Reduce LLM decode time (set max_tokens, use model routing)
  2. Apply prefix caching to reduce LLM prefill time
  3. Replace LLM guardrails with rule-based checks
  
  Expected improvement if all 3 applied: ~40-50% P95 reduction
""")


if __name__ == "__main__":
    main()
