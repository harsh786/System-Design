"""
Latency Budget Allocator for AI Pipelines
Allocates time budgets and performs what-if analysis.
"""

from dataclasses import dataclass


@dataclass
class Component:
    name: str
    category: str
    min_latency_ms: float      # Cannot go below this
    typical_latency_ms: float  # Expected P50
    max_latency_ms: float      # P99 expectation
    is_required: bool          # Can it be skipped?
    is_parallelizable: bool    # Can run parallel with something else?
    optimization_potential: str # low/medium/high


def get_default_components() -> list[Component]:
    """Default AI pipeline components with latency characteristics."""
    return [
        Component("Network (round-trip)", "infrastructure", 10, 40, 100, True, False, "medium"),
        Component("Auth/Gateway", "infrastructure", 2, 8, 20, True, False, "low"),
        Component("Input Guardrails", "guardrails", 1, 80, 300, True, True, "high"),
        Component("Embedding", "retrieval", 5, 30, 60, True, False, "medium"),
        Component("Vector Search", "retrieval", 5, 40, 100, True, False, "medium"),
        Component("Reranking", "retrieval", 0, 70, 150, False, False, "high"),
        Component("Context Assembly", "retrieval", 2, 5, 15, True, False, "low"),
        Component("LLM Generation", "llm", 200, 1800, 4000, True, False, "medium"),
        Component("Output Guardrails", "guardrails", 1, 90, 300, True, True, "high"),
        Component("Serialization", "infrastructure", 2, 5, 15, True, False, "low"),
    ]


def allocate_budget(total_budget_ms: float, components: list[Component]) -> dict[str, float]:
    """
    Allocate budget proportionally based on typical latency,
    ensuring minimum constraints are met.
    """
    # Start with minimum allocations
    allocation = {c.name: c.min_latency_ms for c in components}
    remaining = total_budget_ms - sum(allocation.values())

    # Distribute remaining proportionally to typical - min
    extra_needed = {c.name: c.typical_latency_ms - c.min_latency_ms for c in components}
    total_extra = sum(extra_needed.values())

    if total_extra > 0:
        for c in components:
            share = (extra_needed[c.name] / total_extra) * remaining
            allocation[c.name] += share

    return allocation


def print_allocation_table(total_budget_ms: float, components: list[Component], allocation: dict[str, float]):
    """Print the budget allocation table."""
    print("\n" + "=" * 90)
    print(f"LATENCY BUDGET ALLOCATION — Total Budget: {total_budget_ms:.0f}ms")
    print("=" * 90)
    print()
    print(f"{'Component':<25} {'Budget':>8} {'Typical':>8} {'Slack':>8} {'Status':>12} {'Category':<15}")
    print(f"{'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*12} {'-'*15}")

    total_allocated = 0
    over_count = 0
    for c in components:
        budget = allocation[c.name]
        slack = budget - c.typical_latency_ms
        status = "OK" if slack >= 0 else "OVER"
        if slack < 0:
            over_count += 1
        slack_str = f"+{slack:.0f}ms" if slack >= 0 else f"{slack:.0f}ms"
        print(f"{c.name:<25} {budget:>7.0f}ms {c.typical_latency_ms:>7.0f}ms {slack_str:>8} {status:>12} {c.category:<15}")
        total_allocated += budget

    print(f"{'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*12}")
    overall_slack = total_budget_ms - sum(c.typical_latency_ms for c in components)
    print(f"{'TOTAL':<25} {total_allocated:>7.0f}ms {sum(c.typical_latency_ms for c in components):>7.0f}ms {overall_slack:>+7.0f}ms")
    print()

    if overall_slack < 0:
        print(f"  ⚠️  OVER BUDGET by {-overall_slack:.0f}ms! Must optimize.")
    else:
        print(f"  ✓ Within budget with {overall_slack:.0f}ms slack ({overall_slack/total_budget_ms*100:.1f}% buffer)")


def what_if_analysis(total_budget_ms: float, components: list[Component]):
    """Show what-if scenarios."""
    print("\n" + "=" * 90)
    print("WHAT-IF ANALYSIS")
    print("=" * 90)

    scenarios = [
        {
            "name": "Remove reranking (skip for simple queries)",
            "changes": {"Reranking": 0},
            "tradeoff": "Quality may decrease for complex queries",
        },
        {
            "name": "Rule-based guardrails only (no LLM guardrails)",
            "changes": {"Input Guardrails": 5, "Output Guardrails": 5},
            "tradeoff": "May miss nuanced safety issues",
        },
        {
            "name": "Use smaller/faster LLM (GPT-3.5 instead of GPT-4)",
            "changes": {"LLM Generation": 600},
            "tradeoff": "Lower quality for complex queries",
        },
        {
            "name": "Add semantic caching (30% hit rate)",
            "changes": {"LLM Generation": 1260},  # 0.7 * 1800 + 0.3 * 0
            "tradeoff": "Stale answers possible, cache infrastructure cost",
        },
        {
            "name": "Parallelize guardrails with embedding",
            "changes": {"Input Guardrails": 0},  # Hidden behind embedding time
            "tradeoff": "More complex orchestration",
        },
        {
            "name": "ALL optimizations combined",
            "changes": {
                "Input Guardrails": 5,
                "Output Guardrails": 5,
                "Reranking": 0,
                "LLM Generation": 600,
            },
            "tradeoff": "Lower quality, less safety, needs fallback strategy",
        },
    ]

    baseline_total = sum(c.typical_latency_ms for c in components)
    print(f"\nBaseline total (typical): {baseline_total:.0f}ms")
    print(f"Budget: {total_budget_ms:.0f}ms")
    print(f"Baseline slack: {total_budget_ms - baseline_total:+.0f}ms")
    print()

    for scenario in scenarios:
        modified_total = 0
        for c in components:
            if c.name in scenario["changes"]:
                modified_total += scenario["changes"][c.name]
            else:
                modified_total += c.typical_latency_ms

        savings = baseline_total - modified_total
        new_slack = total_budget_ms - modified_total
        status = "✓ WITHIN" if new_slack >= 0 else "✗ OVER"

        print(f"  Scenario: {scenario['name']}")
        print(f"    New total: {modified_total:.0f}ms (saves {savings:.0f}ms)")
        print(f"    Slack: {new_slack:+.0f}ms [{status}]")
        print(f"    Tradeoff: {scenario['tradeoff']}")
        print()


def budget_for_different_slos(components: list[Component]):
    """Show how budget allocation changes for different SLOs."""
    print("\n" + "=" * 90)
    print("BUDGET ALLOCATION FOR DIFFERENT SLOs")
    print("=" * 90)
    print()

    slos = [
        ("Code completion", 500),
        ("Voice assistant", 1500),
        ("Chat assistant", 3000),
        ("Search + summary", 5000),
        ("Background task", 10000),
    ]

    typical_total = sum(c.typical_latency_ms for c in components)

    print(f"{'Use Case':<20} {'SLO':>6} {'Typical':>8} {'Feasible?':>10} {'Action Needed'}")
    print(f"{'-'*20} {'-'*6} {'-'*8} {'-'*10} {'-'*40}")

    for name, slo in slos:
        feasible = "Yes" if typical_total <= slo else "No"
        if typical_total <= slo:
            action = f"OK — {slo - typical_total:.0f}ms slack"
        elif typical_total <= slo * 1.5:
            action = "Need: smaller model + skip reranking"
        elif typical_total <= slo * 3:
            action = "Need: aggressive caching + tiny model + no guardrails"
        else:
            action = "Impossible without fundamentally different architecture"

        print(f"{name:<20} {slo:>5}ms {typical_total:>7.0f}ms {feasible:>10} {action}")


def main():
    total_budget_ms = 3000.0
    components = get_default_components()

    print("\n📊 AI Pipeline Latency Budget Allocator")
    print("   Analyzing budget allocation for a RAG pipeline\n")

    # Allocate budget
    allocation = allocate_budget(total_budget_ms, components)
    print_allocation_table(total_budget_ms, components, allocation)

    # What-if analysis
    what_if_analysis(total_budget_ms, components)

    # Different SLOs
    budget_for_different_slos(components)

    # Critical path analysis
    print("\n" + "=" * 90)
    print("CRITICAL PATH ANALYSIS")
    print("=" * 90)
    print()
    print("Sequential (critical path) components:")
    sequential = [c for c in components if not c.is_parallelizable]
    seq_total = sum(c.typical_latency_ms for c in sequential)
    for c in sequential:
        pct = c.typical_latency_ms / seq_total * 100
        print(f"  {c.name:<25} {c.typical_latency_ms:>6.0f}ms ({pct:.1f}%)")
    print(f"  {'─'*25} {'─'*6}")
    print(f"  {'Critical path total':<25} {seq_total:>6.0f}ms")
    print()

    parallelizable = [c for c in components if c.is_parallelizable]
    if parallelizable:
        par_max = max(c.typical_latency_ms for c in parallelizable)
        par_sum = sum(c.typical_latency_ms for c in parallelizable)
        print(f"Parallelizable components (overlap with critical path):")
        for c in parallelizable:
            print(f"  {c.name:<25} {c.typical_latency_ms:>6.0f}ms")
        print(f"\n  If parallelized: adds only {par_max:.0f}ms (vs {par_sum:.0f}ms sequential)")
        print(f"  Savings from parallelization: {par_sum - par_max:.0f}ms")
        print(f"\n  Minimum possible latency (critical path): {seq_total:.0f}ms")


if __name__ == "__main__":
    main()
