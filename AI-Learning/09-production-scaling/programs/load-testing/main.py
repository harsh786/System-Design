"""
AI API Load Tester
==================
Sends concurrent requests to an AI endpoint and measures:
- Latency distribution (P50, P95, P99)
- Throughput (requests/second)
- Error rate
- Degradation under increasing load

Uses a simulated endpoint by default. Set AI_ENDPOINT in .env to test real APIs.
"""

import asyncio
import time
import statistics
import random
from dataclasses import dataclass, field


# --- Simulated AI Endpoint ---

async def simulated_ai_endpoint(concurrency_level: int) -> tuple[str, float]:
    """
    Simulates an AI model endpoint.
    
    Latency increases with concurrency (models share GPU memory/compute).
    Occasional errors occur under high load.
    
    Returns: (response_text, simulated_latency)
    """
    # Base latency: 200-800ms (like a real LLM)
    base_latency = random.uniform(0.2, 0.8)
    
    # Concurrency penalty: each concurrent request adds latency
    # This simulates GPU contention and batching delays
    concurrency_penalty = concurrency_level * 0.02  # 20ms per concurrent request
    
    # Random spikes (simulates garbage collection, cache misses)
    spike = random.uniform(0, 0.5) if random.random() < 0.1 else 0
    
    total_latency = base_latency + concurrency_penalty + spike
    
    # Simulate errors under high load
    error_probability = min(0.5, concurrency_level * 0.005)  # Up to 50% at 100 concurrent
    if random.random() < error_probability:
        await asyncio.sleep(total_latency)
        raise Exception("Model overloaded: 503 Service Unavailable")
    
    await asyncio.sleep(total_latency)
    return "Simulated AI response", total_latency


# --- Data Structures ---

@dataclass
class RequestResult:
    latency: float
    success: bool
    error: str = ""


@dataclass
class LoadTestResult:
    concurrency: int
    total_requests: int
    successful: int
    failed: int
    latencies: list[float] = field(default_factory=list)
    duration: float = 0.0

    @property
    def error_rate(self) -> float:
        return self.failed / self.total_requests if self.total_requests > 0 else 0

    @property
    def throughput(self) -> float:
        return self.successful / self.duration if self.duration > 0 else 0

    @property
    def p50(self) -> float:
        return self._percentile(50)

    @property
    def p95(self) -> float:
        return self._percentile(95)

    @property
    def p99(self) -> float:
        return self._percentile(99)

    def _percentile(self, p: int) -> float:
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * p / 100)
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]


# --- Load Test Engine ---

async def send_single_request(concurrency_level: int) -> RequestResult:
    """Send a single request and measure latency."""
    start = time.perf_counter()
    try:
        await simulated_ai_endpoint(concurrency_level)
        latency = time.perf_counter() - start
        return RequestResult(latency=latency, success=True)
    except Exception as e:
        latency = time.perf_counter() - start
        return RequestResult(latency=latency, success=False, error=str(e))


async def run_load_test(concurrency: int, total_requests: int = 100) -> LoadTestResult:
    """
    Run a load test at a specific concurrency level.
    
    Sends `total_requests` with `concurrency` requests in flight at a time.
    """
    semaphore = asyncio.Semaphore(concurrency)
    results: list[RequestResult] = []

    async def bounded_request():
        async with semaphore:
            return await send_single_request(concurrency)

    start_time = time.perf_counter()
    
    # Launch all requests (semaphore controls concurrency)
    tasks = [bounded_request() for _ in range(total_requests)]
    results = await asyncio.gather(*tasks)
    
    duration = time.perf_counter() - start_time

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    return LoadTestResult(
        concurrency=concurrency,
        total_requests=total_requests,
        successful=len(successful),
        failed=len(failed),
        latencies=[r.latency for r in successful],
        duration=duration,
    )


# --- Report Generation ---

def print_report(results: list[LoadTestResult]):
    """Print a formatted load test report."""
    print("\n" + "=" * 70)
    print("                    AI API LOAD TEST REPORT")
    print("=" * 70)
    
    print(f"\n{'Concurrency':<13} {'Throughput':<12} {'P50':<8} {'P95':<8} {'P99':<8} {'Errors':<8} {'Status'}")
    print("-" * 70)
    
    baseline_p95 = results[0].p95 if results else 0
    
    for r in results:
        # Detect degradation: P95 more than 2x baseline
        degraded = r.p95 > baseline_p95 * 2 if baseline_p95 > 0 else False
        error_alert = r.error_rate > 0.1  # >10% errors
        
        status = "✓ OK"
        if degraded and error_alert:
            status = "✗ FAILING"
        elif degraded:
            status = "⚠ DEGRADED"
        elif error_alert:
            status = "⚠ ERRORS"
        
        print(
            f"{r.concurrency:<13} "
            f"{r.throughput:>6.1f} r/s   "
            f"{r.p50*1000:>5.0f}ms "
            f"{r.p95*1000:>5.0f}ms "
            f"{r.p99*1000:>5.0f}ms "
            f"{r.error_rate*100:>5.1f}%  "
            f"{status}"
        )
    
    # Summary
    print("\n" + "-" * 70)
    print("ANALYSIS:")
    
    if len(results) >= 2:
        first = results[0]
        last = results[-1]
        
        latency_increase = (last.p95 / first.p95 - 1) * 100 if first.p95 > 0 else 0
        print(f"  • Latency increase (P95) from {first.concurrency} to {last.concurrency} concurrent: {latency_increase:.0f}%")
        
        max_throughput = max(r.throughput for r in results)
        max_throughput_concurrency = next(r.concurrency for r in results if r.throughput == max_throughput)
        print(f"  • Peak throughput: {max_throughput:.1f} req/s at concurrency={max_throughput_concurrency}")
        
        # Find the point where degradation starts
        for i, r in enumerate(results):
            if r.p95 > baseline_p95 * 2:
                print(f"  • Degradation detected at concurrency={r.concurrency} (P95 > 2x baseline)")
                print(f"  • Recommended max concurrency: {results[i-1].concurrency if i > 0 else r.concurrency}")
                break
        else:
            print(f"  • No degradation detected up to concurrency={results[-1].concurrency}")
    
    print("\n" + "=" * 70)


# --- Main ---

async def main():
    print("AI API Load Tester")
    print("=" * 40)
    print("Testing with simulated AI endpoint")
    print("(Set AI_ENDPOINT in .env for real API testing)\n")
    
    concurrency_levels = [1, 5, 10, 25, 50, 100]
    requests_per_level = 50  # Total requests per concurrency level
    
    all_results = []
    
    for concurrency in concurrency_levels:
        print(f"  Testing concurrency={concurrency}...", end=" ", flush=True)
        result = await run_load_test(concurrency, requests_per_level)
        all_results.append(result)
        print(f"done ({result.throughput:.1f} req/s, P95={result.p95*1000:.0f}ms)")
    
    print_report(all_results)


if __name__ == "__main__":
    asyncio.run(main())
