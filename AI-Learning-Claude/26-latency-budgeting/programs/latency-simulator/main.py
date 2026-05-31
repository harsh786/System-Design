"""
Latency Simulator for AI Pipeline Configurations
Compares different optimization strategies and their impact on user experience.
"""

import random
from dataclasses import dataclass, field


@dataclass
class SimConfig:
    name: str
    description: str
    streaming: bool = False
    cache_hit_rate: float = 0.0
    use_small_model: bool = False
    model_routing: bool = False
    parallel_guardrails: bool = False
    rule_based_guardrails: bool = False
    prefix_caching: bool = False
    skip_reranking: bool = False


@dataclass
class SimResult:
    config_name: str
    actual_total_ms: float
    perceived_latency_ms: float  # What user "feels" (TTFT for streaming)
    ttft_ms: float
    total_generation_ms: float
    retrieval_ms: float
    guardrails_ms: float
    cache_hit: bool
    tokens_generated: int


def simulate_request(config: SimConfig, query_idx: int = 0) -> SimResult:
    """Simulate a single request under given configuration."""
    # Determine if this is a cache hit
    cache_hit = random.random() < config.cache_hit_rate

    if cache_hit:
        # Cache hit: skip LLM, return cached response
        return SimResult(
            config_name=config.name,
            actual_total_ms=35.0,  # network + cache lookup + return
            perceived_latency_ms=35.0,
            ttft_ms=35.0,
            total_generation_ms=0.0,
            retrieval_ms=0.0,
            guardrails_ms=5.0,
            cache_hit=True,
            tokens_generated=0,
        )

    # Infrastructure
    network_ms = random.gauss(30, 5)
    auth_ms = random.gauss(5, 2)

    # Guardrails
    if config.rule_based_guardrails:
        input_guard_ms = random.gauss(3, 1)
        output_guard_ms = random.gauss(3, 1)
    else:
        input_guard_ms = random.gauss(80, 25)
        output_guard_ms = random.gauss(90, 30)

    # Retrieval
    embed_ms = random.gauss(28, 8)
    search_ms = random.gauss(40, 12)
    rerank_ms = 0.0 if config.skip_reranking else random.gauss(70, 20)
    assembly_ms = random.gauss(5, 2)
    retrieval_ms = embed_ms + search_ms + rerank_ms + assembly_ms

    # If parallel guardrails, input guardrails overlap with retrieval
    if config.parallel_guardrails:
        # Guardrail time is "free" (runs parallel with embedding)
        effective_guard_input = max(0, input_guard_ms - embed_ms)
    else:
        effective_guard_input = input_guard_ms

    # LLM
    if config.use_small_model or (config.model_routing and random.random() < 0.6):
        # Small model: faster but shorter responses
        prefill_ms = random.gauss(50, 15)
        tokens = random.randint(15, 40)
        per_token_ms = random.gauss(15, 3)
    else:
        # Large model
        prefill_ms = random.gauss(180, 50)
        if config.prefix_caching:
            prefill_ms *= 0.3  # 70% reduction from prefix caching
        tokens = random.randint(40, 120)
        per_token_ms = random.gauss(30, 5)

    decode_ms = tokens * per_token_ms
    ttft = network_ms/2 + auth_ms + effective_guard_input + retrieval_ms + prefill_ms

    # Total actual latency
    total_ms = ttft + decode_ms + output_guard_ms + network_ms/2

    # Perceived latency
    if config.streaming:
        perceived = ttft  # User sees first token at TTFT
    else:
        perceived = total_ms  # User waits for everything

    guardrails_total = effective_guard_input + output_guard_ms

    return SimResult(
        config_name=config.name,
        actual_total_ms=total_ms,
        perceived_latency_ms=perceived,
        ttft_ms=ttft,
        total_generation_ms=prefill_ms + decode_ms,
        retrieval_ms=retrieval_ms,
        guardrails_ms=guardrails_total,
        cache_hit=False,
        tokens_generated=tokens,
    )


def run_simulation(config: SimConfig, num_requests: int = 50) -> list[SimResult]:
    """Run multiple requests for a configuration."""
    return [simulate_request(config, i) for i in range(num_requests)]


def percentile(values: list[float], pct: int) -> float:
    sorted_vals = sorted(values)
    idx = min(int(len(sorted_vals) * pct / 100), len(sorted_vals) - 1)
    return sorted_vals[idx]


def print_comparison(all_results: dict[str, list[SimResult]], configs: list[SimConfig]):
    """Print comparison table of all configurations."""
    print("\n" + "=" * 110)
    print("LATENCY SIMULATION RESULTS — Comparing Configurations")
    print("=" * 110)

    print(f"\n{'Configuration':<35} {'Perceived P50':>13} {'Perceived P95':>13} {'Actual P50':>11} {'Actual P95':>11} {'Cache Hits':>10}")
    print(f"{'-'*35} {'-'*13} {'-'*13} {'-'*11} {'-'*11} {'-'*10}")

    summary = []
    for config in configs:
        results = all_results[config.name]
        perceived = [r.perceived_latency_ms for r in results]
        actual = [r.actual_total_ms for r in results]
        cache_hits = sum(1 for r in results if r.cache_hit)

        p50_perc = percentile(perceived, 50)
        p95_perc = percentile(perceived, 95)
        p50_act = percentile(actual, 50)
        p95_act = percentile(actual, 95)
        cache_pct = cache_hits / len(results) * 100

        summary.append((config.name, p50_perc, p95_perc, p50_act, p95_act))

        print(f"{config.name:<35} {p50_perc:>10.0f}ms  {p95_perc:>10.0f}ms  {p50_act:>8.0f}ms  {p95_act:>8.0f}ms  {cache_pct:>8.0f}%")

    # Ranking
    print(f"\n{'─' * 110}")
    print("RANKING BY PERCEIVED P95 LATENCY (best → worst):")
    print()
    summary.sort(key=lambda x: x[2])
    baseline_p95 = summary[-1][2]  # worst is baseline

    for rank, (name, p50, p95, _, _) in enumerate(summary, 1):
        improvement = (1 - p95 / baseline_p95) * 100
        bar = "█" * int(p95 / baseline_p95 * 40)
        print(f"  {rank}. {name:<35} P95: {p95:>6.0f}ms  ({improvement:>+5.1f}% vs worst) {bar}")


def print_user_experience(all_results: dict[str, list[SimResult]], configs: list[SimConfig]):
    """Describe what each configuration feels like to the user."""
    print(f"\n{'=' * 110}")
    print("USER EXPERIENCE COMPARISON")
    print("=" * 110)

    for config in configs:
        results = all_results[config.name]
        perceived = [r.perceived_latency_ms for r in results]
        actual = [r.actual_total_ms for r in results]
        p50_perc = percentile(perceived, 50)
        p95_perc = percentile(perceived, 95)
        p50_act = percentile(actual, 50)

        print(f"\n  [{config.name}]")
        print(f"  {config.description}")
        print(f"  Perceived wait: {p50_perc:.0f}ms (P50) | {p95_perc:.0f}ms (P95)")

        # Describe the experience
        if p50_perc < 50:
            feel = "INSTANT — feels like a cached/pre-computed response"
        elif p50_perc < 200:
            feel = "FAST — feels responsive, like a quick web page load"
        elif p50_perc < 500:
            feel = "GOOD — noticeable pause but acceptable for AI"
        elif p50_perc < 1000:
            feel = "OK — user notices waiting, but streaming keeps them engaged"
        elif p50_perc < 2000:
            feel = "SLOW — user is actively waiting, may get impatient"
        else:
            feel = "POOR — user wonders if something is broken"

        print(f"  Feels like: {feel}")


def print_streaming_demo():
    """Show what streaming looks like vs non-streaming."""
    print(f"\n{'=' * 110}")
    print("STREAMING vs NON-STREAMING VISUALIZATION")
    print("=" * 110)

    print("""
  NON-STREAMING (total latency = 2500ms):
  ┌─────────────────────────────────────────────────────────────────────┐
  │ User clicks send...                                                  │
  │ [waiting.......................................................]    │
  │ [waiting.......................................................]    │
  │ [waiting.......] ← 2500ms passes                                    │
  │                                                                      │
  │ FULL RESPONSE APPEARS AT ONCE:                                       │
  │ "Latency budgeting is the practice of allocating a fixed time       │
  │  budget across all components of a system to ensure end-to-end      │
  │  latency stays within acceptable thresholds..."                     │
  └─────────────────────────────────────────────────────────────────────┘

  STREAMING (TTFT = 250ms, same total = 2500ms):
  ┌─────────────────────────────────────────────────────────────────────┐
  │ User clicks send...                                                  │
  │ [waiting..] ← only 250ms!                                           │
  │                                                                      │
  │ "Latency"           ← user starts reading immediately               │
  │ "Latency budgeting" ← tokens appear ~30ms apart                     │
  │ "Latency budgeting is the practice of"                              │
  │ "Latency budgeting is the practice of allocating a fixed time"      │
  │ "...budget across all components of a system to ensure..."          │
  │                                                                      │
  │ User reads at ~250 WPM. By the time they finish reading, the full   │
  │ response is already generated. They NEVER waited!                    │
  └─────────────────────────────────────────────────────────────────────┘

  PERCEIVED LATENCY COMPARISON:
  • Non-streaming: 2500ms of "dead" waiting
  • Streaming:      250ms of waiting, then active reading
  • Improvement:    90% reduction in perceived wait time
""")


def main():
    random.seed(42)

    print("\n⚡ AI Pipeline Latency Simulator")
    print("   Comparing optimization configurations\n")

    configs = [
        SimConfig(
            name="Baseline (no optimizations)",
            description="Full pipeline, no streaming, no caching, large model always",
            streaming=False,
        ),
        SimConfig(
            name="+ Streaming only",
            description="Same pipeline but stream tokens to user",
            streaming=True,
        ),
        SimConfig(
            name="+ Streaming + Cache (30%)",
            description="Streaming + semantic cache with 30% hit rate",
            streaming=True,
            cache_hit_rate=0.3,
        ),
        SimConfig(
            name="+ Streaming + Model Routing",
            description="Streaming + route simple queries to fast small model",
            streaming=True,
            model_routing=True,
        ),
        SimConfig(
            name="+ Streaming + All Retrieval Opts",
            description="Streaming + parallel guardrails + skip reranking + prefix cache",
            streaming=True,
            parallel_guardrails=True,
            skip_reranking=True,
            prefix_caching=True,
        ),
        SimConfig(
            name="FULL OPTIMIZATION",
            description="Everything: streaming + cache + routing + parallel + rules + prefix",
            streaming=True,
            cache_hit_rate=0.3,
            model_routing=True,
            parallel_guardrails=True,
            rule_based_guardrails=True,
            prefix_caching=True,
            skip_reranking=True,
        ),
    ]

    # Run simulations
    all_results = {}
    for config in configs:
        all_results[config.name] = run_simulation(config, num_requests=50)

    # Print results
    print_comparison(all_results, configs)
    print_user_experience(all_results, configs)
    print_streaming_demo()

    # Final summary
    baseline_results = all_results[configs[0].name]
    optimized_results = all_results[configs[-1].name]

    baseline_p95 = percentile([r.perceived_latency_ms for r in baseline_results], 95)
    optimized_p95 = percentile([r.perceived_latency_ms for r in optimized_results], 95)

    print("=" * 110)
    print("SUMMARY")
    print("=" * 110)
    print(f"""
  Baseline perceived P95:    {baseline_p95:.0f}ms
  Fully optimized P95:       {optimized_p95:.0f}ms
  Improvement:               {(1 - optimized_p95/baseline_p95)*100:.0f}% reduction
  
  Key insights:
  • Streaming alone gives the biggest perceived improvement (~80% reduction)
  • Caching gives ZERO latency for repeat queries (30% of traffic)
  • Model routing helps average case significantly (60% of queries use fast model)
  • Combining all techniques: {(1 - optimized_p95/baseline_p95)*100:.0f}% total perceived latency reduction
  
  The #1 thing to implement: STREAMING
  The #2 thing to implement: CACHING
  The #3 thing to implement: MODEL ROUTING
""")


if __name__ == "__main__":
    main()
