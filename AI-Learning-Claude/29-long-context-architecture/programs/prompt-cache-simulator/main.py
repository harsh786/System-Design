"""
Prompt Cache Simulator
======================
Simulates prompt caching behavior across different workload patterns.
Shows how prefix caching works, cost savings, cache hit/miss patterns,
and ROI at different request volumes.

Run: python3 main.py
No dependencies required.
"""

import dataclasses
import random
from collections import defaultdict

random.seed(42)


@dataclasses.dataclass
class CacheEntry:
    """A cached prefix with metadata."""
    prefix_hash: str
    token_count: int
    created_at: int  # Simulated timestamp
    last_accessed: int
    hit_count: int = 0


@dataclasses.dataclass
class Request:
    """A simulated LLM request."""
    request_id: int
    prefix_tokens: int  # Stable prefix (system prompt + docs)
    variable_tokens: int  # Changing part (query + history)
    prefix_hash: str  # Identifies the prefix content
    timestamp: int


@dataclasses.dataclass
class CostResult:
    """Cost calculation for a single request."""
    request_id: int
    cache_hit: bool
    input_tokens: int
    cached_tokens: int
    uncached_tokens: int
    cost_with_cache: float
    cost_without_cache: float
    savings: float
    latency_reduction_ms: float


class PromptCacheSimulator:
    """Simulates provider-level prompt caching (like Anthropic's)."""
    
    def __init__(
        self,
        cache_ttl: int = 300,  # 5 minutes in seconds
        input_cost_per_m: float = 3.0,  # $/M tokens
        cache_write_surcharge: float = 0.25,  # 25% extra for cache write
        cache_read_discount: float = 0.90,  # 90% cheaper for cache read
        min_cacheable_tokens: int = 2048,
    ):
        self.cache_ttl = cache_ttl
        self.input_cost_per_m = input_cost_per_m
        self.cache_write_surcharge = cache_write_surcharge
        self.cache_read_discount = cache_read_discount
        self.min_cacheable_tokens = min_cacheable_tokens
        self.cache: dict = {}  # prefix_hash -> CacheEntry
        self.metrics = defaultdict(int)
    
    def process_request(self, request: Request) -> CostResult:
        """Process a request, checking cache and calculating costs."""
        total_tokens = request.prefix_tokens + request.variable_tokens
        
        # Check cache
        cache_hit = False
        if request.prefix_hash in self.cache:
            entry = self.cache[request.prefix_hash]
            # Check TTL
            if request.timestamp - entry.last_accessed <= self.cache_ttl:
                cache_hit = True
                entry.last_accessed = request.timestamp
                entry.hit_count += 1
                self.metrics['hits'] += 1
            else:
                # Cache expired
                del self.cache[request.prefix_hash]
                self.metrics['expirations'] += 1
        
        if not cache_hit:
            self.metrics['misses'] += 1
        
        # Calculate cost
        cost_without_cache = total_tokens * self.input_cost_per_m / 1_000_000
        
        if cache_hit:
            # Cached tokens at 90% discount
            cached_cost = request.prefix_tokens * self.input_cost_per_m * (1 - self.cache_read_discount) / 1_000_000
            variable_cost = request.variable_tokens * self.input_cost_per_m / 1_000_000
            cost_with_cache = cached_cost + variable_cost
            latency_reduction = request.prefix_tokens / 1000 * 8  # ~8ms per 1K tokens saved in prefill
        else:
            # Cache miss: pay full price + write surcharge for cacheable prefix
            if request.prefix_tokens >= self.min_cacheable_tokens:
                write_cost = request.prefix_tokens * self.input_cost_per_m * (1 + self.cache_write_surcharge) / 1_000_000
                variable_cost = request.variable_tokens * self.input_cost_per_m / 1_000_000
                cost_with_cache = write_cost + variable_cost
                # Store in cache
                self.cache[request.prefix_hash] = CacheEntry(
                    prefix_hash=request.prefix_hash,
                    token_count=request.prefix_tokens,
                    created_at=request.timestamp,
                    last_accessed=request.timestamp,
                )
            else:
                cost_with_cache = cost_without_cache
            latency_reduction = 0
        
        return CostResult(
            request_id=request.request_id,
            cache_hit=cache_hit,
            input_tokens=total_tokens,
            cached_tokens=request.prefix_tokens if cache_hit else 0,
            uncached_tokens=request.variable_tokens if cache_hit else total_tokens,
            cost_with_cache=cost_with_cache,
            cost_without_cache=cost_without_cache,
            savings=cost_without_cache - cost_with_cache,
            latency_reduction_ms=latency_reduction,
        )


def generate_workload_single_prefix(n_requests: int = 100) -> list:
    """
    Workload 1: Single system prompt shared across all requests.
    (e.g., customer support bot with fixed knowledge base)
    High cache hit rate expected.
    """
    prefix_hash = "system_prompt_v1"
    prefix_tokens = 50000  # 50K token system prompt + knowledge base
    
    requests = []
    for i in range(n_requests):
        requests.append(Request(
            request_id=i,
            prefix_tokens=prefix_tokens,
            variable_tokens=random.randint(200, 2000),
            prefix_hash=prefix_hash,
            timestamp=i * 3,  # One request every 3 seconds
        ))
    return requests


def generate_workload_multi_session(n_requests: int = 100) -> list:
    """
    Workload 2: Multiple concurrent sessions, each with different context.
    (e.g., coding assistant with per-repo contexts)
    Medium cache hit rate - each session benefits, but many distinct prefixes.
    """
    n_sessions = 10
    session_prefixes = [f"session_{i}_repo_context" for i in range(n_sessions)]
    
    requests = []
    for i in range(n_requests):
        session = random.randint(0, n_sessions - 1)
        requests.append(Request(
            request_id=i,
            prefix_tokens=random.randint(30000, 100000),  # Varying repo sizes
            variable_tokens=random.randint(500, 3000),
            prefix_hash=session_prefixes[session],
            timestamp=i * 2,
        ))
    return requests


def generate_workload_diverse(n_requests: int = 100) -> list:
    """
    Workload 3: Highly diverse requests with unique contexts.
    (e.g., one-off document analysis with different docs each time)
    Low cache hit rate - each request has unique prefix.
    """
    requests = []
    for i in range(n_requests):
        # 80% unique prefixes, 20% repeat (same user asking follow-ups)
        if random.random() < 0.8:
            prefix_hash = f"unique_doc_{i}"
        else:
            prefix_hash = f"repeated_doc_{i % 5}"
        
        requests.append(Request(
            request_id=i,
            prefix_tokens=random.randint(20000, 200000),
            variable_tokens=random.randint(300, 1500),
            prefix_hash=prefix_hash,
            timestamp=i * 5,
        ))
    return requests


def generate_workload_bursty(n_requests: int = 100) -> list:
    """
    Workload 4: Bursty traffic with gaps > TTL between bursts.
    Tests cache expiration impact.
    """
    requests = []
    prefix_hash = "shared_prefix"
    
    for i in range(n_requests):
        # Every 20 requests, simulate a 10-minute gap (cache expires)
        if i % 20 == 0 and i > 0:
            base_time = i * 2 + 600  # 600s gap (> 300s TTL)
        else:
            base_time = i * 2
        
        requests.append(Request(
            request_id=i,
            prefix_tokens=80000,
            variable_tokens=random.randint(300, 1000),
            prefix_hash=prefix_hash,
            timestamp=base_time,
        ))
    return requests


def run_simulation(name: str, requests: list, simulator: PromptCacheSimulator) -> list:
    """Run a workload through the simulator and return results."""
    results = []
    for req in requests:
        result = simulator.process_request(req)
        results.append(result)
    return results


def print_workload_report(name: str, description: str, results: list, simulator: PromptCacheSimulator):
    """Print analysis for a workload."""
    print(f"\n{'─' * 70}")
    print(f"  WORKLOAD: {name}")
    print(f"  {description}")
    print(f"{'─' * 70}")
    
    total_requests = len(results)
    cache_hits = sum(1 for r in results if r.cache_hit)
    hit_rate = cache_hits / total_requests * 100
    
    total_cost_with = sum(r.cost_with_cache for r in results)
    total_cost_without = sum(r.cost_without_cache for r in results)
    total_savings = total_cost_without - total_cost_with
    savings_pct = (total_savings / total_cost_without * 100) if total_cost_without > 0 else 0
    
    avg_latency_saved = sum(r.latency_reduction_ms for r in results) / total_requests
    
    print(f"\n  Requests:        {total_requests}")
    print(f"  Cache Hit Rate:  {hit_rate:.1f}%")
    print(f"  Cost (no cache): ${total_cost_without:.4f}")
    print(f"  Cost (cached):   ${total_cost_with:.4f}")
    print(f"  Savings:         ${total_savings:.4f} ({savings_pct:.1f}%)")
    print(f"  Avg Latency Saved: {avg_latency_saved:.0f}ms per request")
    
    # Show first few requests to illustrate cache behavior
    print(f"\n  First 8 requests (showing cache warm-up):")
    print(f"  {'#':<4} {'Hit?':<6} {'Cached':>8} {'Total':>8} {'Cost':>10} {'Saved':>10}")
    for r in results[:8]:
        hit_str = "HIT" if r.cache_hit else "MISS"
        print(f"  {r.request_id:<4} {hit_str:<6} {r.cached_tokens:>7,} {r.input_tokens:>7,} ${r.cost_with_cache:>8.5f} ${r.savings:>8.5f}")


def print_roi_analysis():
    """Show ROI at different request volumes."""
    print("\n" + "=" * 70)
    print("ROI ANALYSIS: When Does Caching Pay Off?")
    print("=" * 70)
    
    # Parameters
    prefix_size = 50000  # 50K token stable prefix
    variable_size = 1000  # 1K variable tokens
    cost_per_m = 3.0
    cache_write_extra = 0.25
    cache_read_discount = 0.90
    
    # Cost per request without cache
    cost_no_cache = (prefix_size + variable_size) * cost_per_m / 1_000_000
    
    # Cost for first request (cache write)
    cost_first = prefix_size * cost_per_m * (1 + cache_write_extra) / 1_000_000 + variable_size * cost_per_m / 1_000_000
    
    # Cost for subsequent (cache hit)
    cost_cached = prefix_size * cost_per_m * (1 - cache_read_discount) / 1_000_000 + variable_size * cost_per_m / 1_000_000
    
    print(f"\n  Prefix size: {prefix_size:,} tokens")
    print(f"  Variable size: {variable_size:,} tokens")
    print(f"  Cost per request (no cache): ${cost_no_cache:.5f}")
    print(f"  Cost first request (cache write): ${cost_first:.5f}")
    print(f"  Cost subsequent (cache hit): ${cost_cached:.5f}")
    print(f"  Per-request savings after warm-up: ${cost_no_cache - cost_cached:.5f} ({(1 - cost_cached/cost_no_cache)*100:.1f}%)")
    
    # Break-even: after how many requests does caching pay for itself?
    write_overhead = cost_first - cost_no_cache
    per_request_savings = cost_no_cache - cost_cached
    breakeven = write_overhead / per_request_savings if per_request_savings > 0 else float('inf')
    
    print(f"\n  Cache write overhead: ${write_overhead:.5f}")
    print(f"  Break-even after: {breakeven:.1f} requests")
    
    print(f"\n  {'Requests':<12} {'No Cache':>12} {'With Cache':>12} {'Savings':>12} {'Savings %':>10}")
    print(f"  {'─' * 58}")
    for n in [1, 2, 5, 10, 50, 100, 1000, 10000]:
        no_cache_total = n * cost_no_cache
        # First request pays write cost, rest are cache hits (assuming within TTL)
        with_cache_total = cost_first + (n - 1) * cost_cached if n > 0 else 0
        savings = no_cache_total - with_cache_total
        savings_pct = savings / no_cache_total * 100 if no_cache_total > 0 else 0
        print(f"  {n:<12} ${no_cache_total:>10.4f} ${with_cache_total:>10.4f} ${savings:>10.4f} {savings_pct:>9.1f}%")


def print_invalidation_scenarios():
    """Demonstrate cache invalidation impact."""
    print("\n" + "=" * 70)
    print("CACHE INVALIDATION SCENARIOS")
    print("=" * 70)
    
    scenarios = [
        ("Static knowledge base", "Never changes", 0, 100),
        ("Daily-updated docs", "Rebuild cache once/day", 1, 100),
        ("Hourly-updated docs", "Cache miss every hour (~12 misses/day)", 12, 100),
        ("Per-request unique context", "No caching possible", 100, 100),
    ]
    
    prefix_tokens = 50000
    cost_per_m = 3.0
    cost_no_cache = prefix_tokens * cost_per_m / 1_000_000
    cost_cached = prefix_tokens * cost_per_m * 0.10 / 1_000_000
    cost_write = prefix_tokens * cost_per_m * 1.25 / 1_000_000
    
    print(f"\n  {'Scenario':<30} {'Misses/100':<12} {'Effective Savings':>18}")
    print(f"  {'─' * 62}")
    
    for name, desc, misses, total in scenarios:
        hits = total - misses
        total_cost = misses * cost_write + hits * cost_cached
        baseline = total * cost_no_cache
        savings = (1 - total_cost / baseline) * 100
        print(f"  {name:<30} {misses:<12} {savings:>17.1f}%")
        print(f"    ({desc})")


def main():
    print("=" * 70)
    print("PROMPT CACHE SIMULATOR")
    print("=" * 70)
    print("\nSimulates LLM prompt caching behavior across different workload patterns.")
    print("Models Anthropic-style caching: 25% write surcharge, 90% read discount, 5min TTL.\n")
    
    # Run 4 workload patterns
    workloads = [
        ("Single Shared Prefix", "Customer support bot - same system prompt for all users",
         generate_workload_single_prefix),
        ("Multi-Session", "Coding assistant - 10 concurrent sessions with different repo contexts",
         generate_workload_multi_session),
        ("Diverse Requests", "Document analysis - mostly unique documents per request",
         generate_workload_diverse),
        ("Bursty Traffic", "Same prefix but traffic gaps exceed cache TTL (5min)",
         generate_workload_bursty),
    ]
    
    for name, desc, gen_fn in workloads:
        simulator = PromptCacheSimulator()
        requests = gen_fn(n_requests=100)
        results = run_simulation(name, requests, simulator)
        print_workload_report(name, desc, results, simulator)
    
    # ROI analysis
    print_roi_analysis()
    
    # Invalidation scenarios
    print_invalidation_scenarios()
    
    # Key insights
    print("\n" + "=" * 70)
    print("KEY ARCHITECTURAL INSIGHTS")
    print("=" * 70)
    print("""
  1. Caching breaks even after just 1-2 requests for the same prefix.
     The 25% write surcharge is trivial compared to 90% read discount.

  2. Cache TTL (5 minutes) means low-traffic workloads may not benefit.
     Design for cache-friendly access patterns (batch similar requests).

  3. Structure prompts with stable content FIRST, variable content LAST.
     Only the prefix (from start) can be cached - any change invalidates.

  4. Multi-tenant systems benefit most: shared system prompt + docs cached
     once, used by all users. Per-user context goes in the variable suffix.

  5. Monitor cache hit rate in production. Below 50%, re-evaluate whether
     your workload is cache-friendly or if you need architectural changes.

  6. For bursty workloads, consider "keep-alive" requests to prevent
     cache expiration during quiet periods (cost: one cheap request/5min).
    """)


if __name__ == "__main__":
    main()
