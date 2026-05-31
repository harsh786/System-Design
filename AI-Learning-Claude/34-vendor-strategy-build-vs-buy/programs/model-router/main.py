"""
Multi-Model Orchestration Simulator

Simulates intelligent model routing across multiple LLM providers:
- Multiple models with different cost/quality/latency profiles
- Query complexity classification
- Routing strategies: cost-based, capability-based, cascade
- Fallback chains for reliability
- Cost savings analysis vs single-model approach

Run: python3 main.py
"""

import random
import time
from dataclasses import dataclass, field
from enum import Enum


# ─── Model Definitions ─────────────────────────────────────────────────────────

class ModelTier(Enum):
    CHEAP = "cheap"
    MID = "mid"
    PREMIUM = "premium"
    FRONTIER = "frontier"


@dataclass
class Model:
    name: str
    tier: ModelTier
    cost_per_1k_tokens: float  # output tokens
    avg_latency_ms: int
    quality_score: float  # 0-100 on eval suite
    error_rate: float  # probability of failure
    strengths: list[str] = field(default_factory=list)

    def simulate_response(self, complexity: float) -> dict:
        """Simulate a model response with realistic characteristics."""
        # Simulate failure
        if random.random() < self.error_rate:
            return {"success": False, "error": "provider_error", "latency_ms": 500}

        # Quality depends on query complexity vs model capability
        base_quality = self.quality_score
        # Cheap models degrade more on complex queries
        complexity_penalty = complexity * (100 - base_quality) * 0.3
        actual_quality = max(30, base_quality - complexity_penalty + random.gauss(0, 3))

        # Latency varies
        actual_latency = int(self.avg_latency_ms * random.uniform(0.7, 1.5))

        # Token count simulation (complexity affects length)
        output_tokens = int(150 + complexity * 200 + random.gauss(0, 30))

        return {
            "success": True,
            "quality": round(actual_quality, 1),
            "latency_ms": actual_latency,
            "output_tokens": output_tokens,
            "cost": round(output_tokens * self.cost_per_1k_tokens / 1000, 5),
        }


# Production-realistic model roster
MODELS = {
    "gemini-flash": Model(
        name="gemini-flash",
        tier=ModelTier.CHEAP,
        cost_per_1k_tokens=0.30,
        avg_latency_ms=200,
        quality_score=72,
        error_rate=0.01,
        strengths=["speed", "classification", "simple_qa"],
    ),
    "gpt-4o-mini": Model(
        name="gpt-4o-mini",
        tier=ModelTier.CHEAP,
        cost_per_1k_tokens=0.60,
        avg_latency_ms=350,
        quality_score=78,
        error_rate=0.02,
        strengths=["general", "structured_output", "simple_qa"],
    ),
    "claude-haiku": Model(
        name="claude-haiku",
        tier=ModelTier.MID,
        cost_per_1k_tokens=1.25,
        avg_latency_ms=400,
        quality_score=80,
        error_rate=0.01,
        strengths=["code", "analysis", "general"],
    ),
    "claude-sonnet": Model(
        name="claude-sonnet",
        tier=ModelTier.PREMIUM,
        cost_per_1k_tokens=15.00,
        avg_latency_ms=900,
        quality_score=92,
        error_rate=0.02,
        strengths=["code", "reasoning", "analysis", "complex"],
    ),
    "gpt-4o": Model(
        name="gpt-4o",
        tier=ModelTier.PREMIUM,
        cost_per_1k_tokens=10.00,
        avg_latency_ms=800,
        quality_score=90,
        error_rate=0.03,
        strengths=["creative", "structured_output", "multilingual", "complex"],
    ),
    "o1-preview": Model(
        name="o1-preview",
        tier=ModelTier.FRONTIER,
        cost_per_1k_tokens=60.00,
        avg_latency_ms=5000,
        quality_score=97,
        error_rate=0.05,
        strengths=["reasoning", "math", "complex", "novel_problems"],
    ),
}


# ─── Query Classification ─────────────────────────────────────────────────────

class QueryType(Enum):
    SIMPLE_QA = "simple_qa"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"
    CODE_GENERATION = "code_generation"
    CREATIVE_WRITING = "creative_writing"
    COMPLEX_REASONING = "complex_reasoning"
    STRUCTURED_OUTPUT = "structured_output"


@dataclass
class Query:
    text: str
    query_type: QueryType
    complexity: float  # 0.0 (trivial) to 1.0 (extremely complex)
    quality_threshold: float = 80.0  # minimum acceptable quality


def generate_production_queries(n: int) -> list[Query]:
    """Generate realistic production query distribution."""
    queries = []
    # Real-world distribution: most queries are simple
    distribution = [
        (QueryType.SIMPLE_QA, 0.30, (0.1, 0.3)),
        (QueryType.CLASSIFICATION, 0.20, (0.1, 0.2)),
        (QueryType.SUMMARIZATION, 0.15, (0.2, 0.5)),
        (QueryType.STRUCTURED_OUTPUT, 0.10, (0.2, 0.4)),
        (QueryType.CODE_GENERATION, 0.10, (0.4, 0.8)),
        (QueryType.CREATIVE_WRITING, 0.08, (0.3, 0.6)),
        (QueryType.COMPLEX_REASONING, 0.07, (0.7, 1.0)),
    ]

    for query_type, proportion, (min_c, max_c) in distribution:
        count = int(n * proportion)
        for _ in range(count):
            complexity = random.uniform(min_c, max_c)
            queries.append(Query(
                text=f"[{query_type.value}] complexity={complexity:.2f}",
                query_type=query_type,
                complexity=complexity,
                quality_threshold=75 if complexity < 0.4 else 85,
            ))

    random.shuffle(queries)
    return queries[:n]


# ─── Routing Strategies ────────────────────────────────────────────────────────

class RoutingStrategy:
    """Base class for routing strategies."""

    def select_model(self, query: Query) -> str:
        raise NotImplementedError


class SingleModelStrategy(RoutingStrategy):
    """Baseline: always use the same model."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    def select_model(self, query: Query) -> str:
        return self.model_name


class CostBasedStrategy(RoutingStrategy):
    """Route based on complexity → cost tier."""

    def select_model(self, query: Query) -> str:
        if query.complexity < 0.3:
            return "gemini-flash"
        elif query.complexity < 0.5:
            return "gpt-4o-mini"
        elif query.complexity < 0.7:
            return "claude-haiku"
        elif query.complexity < 0.9:
            return "claude-sonnet"
        else:
            return "o1-preview"


class CapabilityBasedStrategy(RoutingStrategy):
    """Route based on query type → model strengths."""

    ROUTING_TABLE = {
        QueryType.SIMPLE_QA: "gemini-flash",
        QueryType.CLASSIFICATION: "gemini-flash",
        QueryType.SUMMARIZATION: "gpt-4o-mini",
        QueryType.STRUCTURED_OUTPUT: "gpt-4o",
        QueryType.CODE_GENERATION: "claude-sonnet",
        QueryType.CREATIVE_WRITING: "gpt-4o",
        QueryType.COMPLEX_REASONING: "claude-sonnet",
    }

    def select_model(self, query: Query) -> str:
        return self.ROUTING_TABLE.get(query.query_type, "claude-sonnet")


class CascadeStrategy(RoutingStrategy):
    """Try cheap model first, escalate if quality is low."""

    CASCADE_CHAIN = ["gemini-flash", "gpt-4o-mini", "claude-sonnet", "o1-preview"]
    QUALITY_THRESHOLD = 78.0

    def select_model(self, query: Query) -> str:
        # Returns starting model; actual cascade happens in router
        if query.complexity < 0.3:
            return "gemini-flash"
        elif query.complexity < 0.6:
            return "gpt-4o-mini"
        else:
            return "claude-haiku"


# ─── Router Engine ─────────────────────────────────────────────────────────────

@dataclass
class RoutingResult:
    query: Query
    model_used: str
    response: dict
    attempts: int = 1
    total_cost: float = 0.0
    total_latency_ms: int = 0
    escalated: bool = False
    fell_back: bool = False


class ModelRouter:
    """Orchestrates multi-model routing with fallback and cascade."""

    FALLBACK_CHAIN = {
        "claude-sonnet": ["gpt-4o", "claude-haiku", "gpt-4o-mini"],
        "gpt-4o": ["claude-sonnet", "claude-haiku", "gpt-4o-mini"],
        "claude-haiku": ["gpt-4o-mini", "gemini-flash"],
        "gpt-4o-mini": ["gemini-flash", "claude-haiku"],
        "gemini-flash": ["gpt-4o-mini", "claude-haiku"],
        "o1-preview": ["claude-sonnet", "gpt-4o"],
    }

    def __init__(self, strategy: RoutingStrategy, enable_cascade: bool = False):
        self.strategy = strategy
        self.enable_cascade = enable_cascade
        self.results: list[RoutingResult] = []

    def route(self, query: Query) -> RoutingResult:
        """Route a query to the optimal model with fallback."""
        primary_model = self.strategy.select_model(query)
        result = self._try_model(primary_model, query)

        total_cost = result["cost"] if result["success"] else 0
        total_latency = result["latency_ms"]
        attempts = 1
        escalated = False
        fell_back = False

        # If primary fails, try fallback chain
        if not result["success"]:
            fell_back = True
            for fallback in self.FALLBACK_CHAIN.get(primary_model, []):
                attempts += 1
                result = self._try_model(fallback, query)
                total_latency += result["latency_ms"]
                if result["success"]:
                    total_cost += result["cost"]
                    primary_model = fallback
                    break

        # Cascade: if quality is too low, escalate
        elif self.enable_cascade and result["success"]:
            if result["quality"] < query.quality_threshold:
                # Escalate to a better model
                escalation_map = {
                    "gemini-flash": "gpt-4o-mini",
                    "gpt-4o-mini": "claude-haiku",
                    "claude-haiku": "claude-sonnet",
                    "claude-sonnet": "o1-preview",
                }
                next_model = escalation_map.get(primary_model)
                if next_model:
                    escalated = True
                    attempts += 1
                    better_result = self._try_model(next_model, query)
                    total_latency += better_result["latency_ms"]
                    if better_result["success"] and better_result["quality"] > result["quality"]:
                        total_cost += better_result["cost"]
                        result = better_result
                        primary_model = next_model
                    else:
                        total_cost += better_result.get("cost", 0)

        routing_result = RoutingResult(
            query=query,
            model_used=primary_model,
            response=result,
            attempts=attempts,
            total_cost=total_cost,
            total_latency_ms=total_latency,
            escalated=escalated,
            fell_back=fell_back,
        )
        self.results.append(routing_result)
        return routing_result

    def _try_model(self, model_name: str, query: Query) -> dict:
        """Try a specific model."""
        model = MODELS[model_name]
        return model.simulate_response(query.complexity)


# ─── Analytics ─────────────────────────────────────────────────────────────────

def analyze_results(results: list[RoutingResult], strategy_name: str) -> dict:
    """Analyze routing results and produce metrics."""
    successful = [r for r in results if r.response.get("success")]
    failed = [r for r in results if not r.response.get("success")]

    total_cost = sum(r.total_cost for r in results)
    avg_quality = (
        sum(r.response["quality"] for r in successful) / len(successful)
        if successful else 0
    )
    avg_latency = (
        sum(r.total_latency_ms for r in results) / len(results) if results else 0
    )

    # Per-model breakdown
    model_stats: dict = {}
    for r in results:
        model = r.model_used
        if model not in model_stats:
            model_stats[model] = {"count": 0, "cost": 0, "quality_sum": 0}
        model_stats[model]["count"] += 1
        model_stats[model]["cost"] += r.total_cost
        if r.response.get("success"):
            model_stats[model]["quality_sum"] += r.response["quality"]

    escalation_count = sum(1 for r in results if r.escalated)
    fallback_count = sum(1 for r in results if r.fell_back)

    return {
        "strategy": strategy_name,
        "total_queries": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "total_cost": round(total_cost, 4),
        "avg_cost_per_query": round(total_cost / len(results), 6) if results else 0,
        "avg_quality": round(avg_quality, 1),
        "avg_latency_ms": round(avg_latency),
        "escalations": escalation_count,
        "fallbacks": fallback_count,
        "model_distribution": model_stats,
    }


def print_report(analytics: dict) -> None:
    """Print formatted analytics report."""
    print(f"\n{'─' * 70}")
    print(f"  Strategy: {analytics['strategy']}")
    print(f"{'─' * 70}")
    print(f"  Queries: {analytics['total_queries']} | "
          f"Success: {analytics['successful']} | "
          f"Failed: {analytics['failed']}")
    print(f"  Total Cost: ${analytics['total_cost']:.4f} | "
          f"Avg/Query: ${analytics['avg_cost_per_query']:.6f}")
    print(f"  Avg Quality: {analytics['avg_quality']:.1f}/100 | "
          f"Avg Latency: {analytics['avg_latency_ms']}ms")
    print(f"  Escalations: {analytics['escalations']} | "
          f"Fallbacks: {analytics['fallbacks']}")

    print(f"\n  Model Distribution:")
    print(f"  {'Model':<20} {'Queries':>8} {'%':>7} {'Cost':>10} {'Avg Quality':>12}")
    print(f"  {'-' * 60}")
    total_q = analytics["total_queries"]
    for model, stats in sorted(
        analytics["model_distribution"].items(),
        key=lambda x: x[1]["count"],
        reverse=True,
    ):
        pct = stats["count"] / total_q * 100
        avg_q = stats["quality_sum"] / stats["count"] if stats["count"] > 0 else 0
        print(
            f"  {model:<20} {stats['count']:>8} {pct:>6.1f}% "
            f"${stats['cost']:>8.4f} {avg_q:>10.1f}"
        )


# ─── Main Simulation ──────────────────────────────────────────────────────────

def main():
    random.seed(42)  # Reproducible results

    print("=" * 70)
    print("  MULTI-MODEL ORCHESTRATION SIMULATOR")
    print("  Staff Architect: Model Routing Analysis")
    print("=" * 70)

    # Generate production-like queries
    NUM_QUERIES = 1000
    queries = generate_production_queries(NUM_QUERIES)

    print(f"\n  Generated {NUM_QUERIES} production-like queries")
    print(f"  Query type distribution:")
    type_counts: dict = {}
    for q in queries:
        type_counts[q.query_type.value] = type_counts.get(q.query_type.value, 0) + 1
    for qt, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {qt:<25} {count:>4} ({count/NUM_QUERIES*100:.0f}%)")

    # Strategy 1: Baseline (always use premium model)
    print("\n\n" + "=" * 70)
    print("  STRATEGY COMPARISON")
    print("=" * 70)

    strategies = [
        ("Baseline: Always Claude Sonnet", SingleModelStrategy("claude-sonnet"), False),
        ("Baseline: Always GPT-4o", SingleModelStrategy("gpt-4o"), False),
        ("Cost-Based Routing", CostBasedStrategy(), False),
        ("Capability-Based Routing", CapabilityBasedStrategy(), False),
        ("Cascade (try cheap first)", CostBasedStrategy(), True),
    ]

    all_analytics = []
    for name, strategy, cascade in strategies:
        router = ModelRouter(strategy, enable_cascade=cascade)
        for query in queries:
            router.route(query)
        analytics = analyze_results(router.results, name)
        all_analytics.append(analytics)
        print_report(analytics)

    # Comparison summary
    print("\n\n" + "=" * 70)
    print("  COST-QUALITY COMPARISON SUMMARY")
    print("=" * 70)
    print(f"\n  {'Strategy':<35} {'Cost':>10} {'Quality':>9} {'Latency':>9} {'Savings':>9}")
    print(f"  {'-' * 72}")

    baseline_cost = all_analytics[0]["total_cost"]
    for a in all_analytics:
        savings = (1 - a["total_cost"] / baseline_cost) * 100 if baseline_cost > 0 else 0
        print(
            f"  {a['strategy']:<35} "
            f"${a['total_cost']:>8.3f} "
            f"{a['avg_quality']:>7.1f} "
            f"{a['avg_latency_ms']:>7}ms "
            f"{savings:>7.1f}%"
        )

    # Key insights
    print(f"\n\n{'─' * 70}")
    print("  KEY INSIGHTS FOR STAFF ARCHITECTS")
    print(f"{'─' * 70}")

    best_cost = min(all_analytics, key=lambda a: a["total_cost"])
    best_quality = max(all_analytics, key=lambda a: a["avg_quality"])

    print(f"""
  1. COST WINNER: {best_cost['strategy']}
     - ${best_cost['total_cost']:.4f} total for {NUM_QUERIES} queries
     - {(1 - best_cost['total_cost']/baseline_cost)*100:.0f}% cheaper than always using premium model

  2. QUALITY WINNER: {best_quality['strategy']}
     - {best_quality['avg_quality']:.1f}/100 average quality
     - Best output when quality is non-negotiable

  3. BEST VALUE (quality per dollar):
     - Cascade strategy provides near-premium quality at fraction of cost
     - Most queries are simple enough for cheap models
     - Only escalate when cheap model would produce poor results

  4. PRODUCTION RECOMMENDATIONS:
     - Start with cost-based routing (immediate 50-70% savings)
     - Add cascade for quality-sensitive paths
     - Monitor per-model quality scores weekly
     - Review routing rules monthly as models improve

  5. FALLBACK CHAINS ARE CRITICAL:
     - Without fallbacks, provider outages = your outage
     - With fallbacks, transparency to users during incidents
     - Test failover monthly (chaos engineering for AI)
""")

    # Monthly cost projection
    print(f"{'─' * 70}")
    print("  MONTHLY COST PROJECTION (at 500K queries/month)")
    print(f"{'─' * 70}")
    scale_factor = 500_000 / NUM_QUERIES
    print(f"\n  {'Strategy':<35} {'Monthly Cost':>14} {'Annual Cost':>14}")
    print(f"  {'-' * 63}")
    for a in all_analytics:
        monthly = a["total_cost"] * scale_factor
        annual = monthly * 12
        print(f"  {a['strategy']:<35} ${monthly:>11,.0f} ${annual:>11,.0f}")

    print(f"\n  Annual savings of intelligent routing vs single premium model:")
    for a in all_analytics[2:]:  # Skip baselines
        monthly = a["total_cost"] * scale_factor
        baseline_monthly = baseline_cost * scale_factor
        annual_savings = (baseline_monthly - monthly) * 12
        print(f"    {a['strategy']:<35} saves ${annual_savings:>10,.0f}/year")

    print("\n" + "=" * 70)
    print("  END OF SIMULATION")
    print("=" * 70)


if __name__ == "__main__":
    main()
