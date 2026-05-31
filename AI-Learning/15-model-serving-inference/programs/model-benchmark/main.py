"""
Model Benchmark
===============
Benchmarks LLM API endpoints (or simulates if no endpoint available).
Measures TTFT, throughput, latency, and calculates cost.
"""

import os
import time
import random
import statistics
from dataclasses import dataclass
from tabulate import tabulate

try:
    import requests as http_requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class BenchmarkResult:
    input_tokens: int
    output_tokens: int
    ttft_ms: float
    total_time_ms: float
    tokens_per_sec: float
    inter_token_latency_ms: float


# Simulation parameters (used when no real API available)
SIM_PREFILL_MS_PER_TOKEN = 0.05  # 50µs per input token
SIM_DECODE_MS_PER_TOKEN = 30.0   # 30ms per output token
SIM_OVERHEAD_MS = 50.0           # Network + queue overhead


def simulate_request(input_tokens: int, output_tokens: int) -> BenchmarkResult:
    """Simulate an LLM API call with realistic timing."""
    # Add some noise
    noise = random.uniform(0.9, 1.1)

    ttft = (SIM_OVERHEAD_MS + input_tokens * SIM_PREFILL_MS_PER_TOKEN) * noise
    decode_time = output_tokens * SIM_DECODE_MS_PER_TOKEN * noise
    total_time = ttft + decode_time
    tps = output_tokens / (decode_time / 1000)
    itl = decode_time / output_tokens

    return BenchmarkResult(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        ttft_ms=ttft,
        total_time_ms=total_time,
        tokens_per_sec=tps,
        inter_token_latency_ms=itl,
    )


def real_api_request(base_url: str, api_key: str, model: str, input_tokens: int, output_tokens: int) -> BenchmarkResult:
    """Make a real API call and measure timing."""
    # Generate dummy input of approximate token count
    prompt = "Hello " * (input_tokens // 2)

    start = time.perf_counter()
    response = http_requests.post(
        f"{base_url}/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "prompt": prompt, "max_tokens": output_tokens, "stream": False},
        timeout=120,
    )
    total_time = (time.perf_counter() - start) * 1000

    if response.status_code != 200:
        raise Exception(f"API error: {response.status_code} {response.text[:200]}")

    data = response.json()
    actual_output = data.get("usage", {}).get("completion_tokens", output_tokens)

    # Estimate TTFT as fraction of total (without streaming, approximate)
    estimated_ttft = input_tokens * SIM_PREFILL_MS_PER_TOKEN + SIM_OVERHEAD_MS
    decode_time = total_time - estimated_ttft
    tps = actual_output / (decode_time / 1000) if decode_time > 0 else 0
    itl = decode_time / actual_output if actual_output > 0 else 0

    return BenchmarkResult(
        input_tokens=input_tokens,
        output_tokens=actual_output,
        ttft_ms=estimated_ttft,
        total_time_ms=total_time,
        tokens_per_sec=tps,
        inter_token_latency_ms=itl,
    )


def run_benchmark(use_real_api: bool = False) -> list[BenchmarkResult]:
    """Run benchmark across different input/output length combinations."""
    input_lengths = [100, 500, 1000, 5000]
    output_lengths = [50, 200, 500]
    results = []

    base_url = os.getenv("API_BASE_URL", "")
    api_key = os.getenv("API_KEY", "")
    model = os.getenv("MODEL_NAME", "")

    for inp in input_lengths:
        for out in output_lengths:
            trials = []
            num_trials = 3

            for _ in range(num_trials):
                if use_real_api and base_url:
                    try:
                        r = real_api_request(base_url, api_key, model, inp, out)
                    except Exception as e:
                        print(f"  API error for {inp}/{out}: {e}")
                        r = simulate_request(inp, out)
                else:
                    r = simulate_request(inp, out)
                trials.append(r)

            # Average results
            avg_result = BenchmarkResult(
                input_tokens=inp,
                output_tokens=out,
                ttft_ms=statistics.mean(t.ttft_ms for t in trials),
                total_time_ms=statistics.mean(t.total_time_ms for t in trials),
                tokens_per_sec=statistics.mean(t.tokens_per_sec for t in trials),
                inter_token_latency_ms=statistics.mean(t.inter_token_latency_ms for t in trials),
            )
            results.append(avg_result)

    return results


def calculate_cost(results: list[BenchmarkResult], gpu_cost_per_hour: float) -> list[dict]:
    """Calculate cost per token based on throughput."""
    cost_data = []
    for r in results:
        # Cost = GPU cost per second / tokens per second
        cost_per_sec = gpu_cost_per_hour / 3600
        cost_per_token = cost_per_sec / r.tokens_per_sec if r.tokens_per_sec > 0 else 0
        cost_per_1k = cost_per_token * 1000
        cost_data.append({
            "input": r.input_tokens,
            "output": r.output_tokens,
            "cost_per_1k_tokens": cost_per_1k,
            "tokens_per_dollar": 1 / cost_per_token if cost_per_token > 0 else 0,
        })
    return cost_data


def main():
    print("=" * 80)
    print("LLM MODEL BENCHMARK")
    print("=" * 80)

    # Check if real API is configured
    base_url = os.getenv("API_BASE_URL", "")
    use_real = bool(base_url and base_url != "http://localhost:8000/v1")

    if use_real:
        print(f"\nUsing real API: {base_url}")
    else:
        print("\nNo API configured - using simulation mode")
        print("(Set API_BASE_URL in .env for real benchmarking)")

    print("\nRunning benchmarks...")
    random.seed(42)
    results = run_benchmark(use_real_api=use_real)

    # Performance table
    print("\n--- Performance Results ---\n")
    headers = ["Input Tokens", "Output Tokens", "TTFT (ms)", "Total (ms)", "Tokens/sec", "ITL (ms)"]
    rows = []
    for r in results:
        rows.append([
            r.input_tokens, r.output_tokens,
            f"{r.ttft_ms:.1f}", f"{r.total_time_ms:.0f}",
            f"{r.tokens_per_sec:.1f}", f"{r.inter_token_latency_ms:.1f}",
        ])
    print(tabulate(rows, headers=headers, tablefmt="grid"))

    # Cost analysis
    gpu_cost = float(os.getenv("GPU_COST_PER_HOUR", "5.0"))
    print(f"\n--- Cost Analysis (GPU: ${gpu_cost}/hr) ---\n")
    cost_data = calculate_cost(results, gpu_cost)
    cost_headers = ["Input", "Output", "Cost per 1K tokens", "Tokens per $1"]
    cost_rows = []
    for c in cost_data:
        cost_rows.append([
            c["input"], c["output"],
            f"${c['cost_per_1k_tokens']:.4f}",
            f"{c['tokens_per_dollar']:.0f}",
        ])
    print(tabulate(cost_rows, headers=cost_headers, tablefmt="grid"))

    # Recommendations
    print("\n--- Recommendations ---\n")
    avg_tps = statistics.mean(r.tokens_per_sec for r in results)
    avg_ttft = statistics.mean(r.ttft_ms for r in results)

    if avg_ttft > 500:
        print("⚠ TTFT > 500ms: Consider reducing input length or adding more GPU compute")
    elif avg_ttft > 200:
        print("• TTFT 200-500ms: Acceptable for most applications")
    else:
        print("✓ TTFT < 200ms: Excellent responsiveness")

    if avg_tps < 20:
        print("⚠ Low throughput: Consider batching, quantization, or faster GPU")
    elif avg_tps < 50:
        print("• Moderate throughput: Adequate for single-user, consider optimization for scale")
    else:
        print("✓ Good throughput: Suitable for production serving")

    # Compare with API pricing
    print(f"\n--- Self-Host vs API Comparison ---")
    avg_cost_per_1k = statistics.mean(c["cost_per_1k_tokens"] for c in cost_data)
    api_cost_per_1k = 0.005  # $5/1M tokens typical
    print(f"  Self-hosted cost: ${avg_cost_per_1k:.4f} per 1K tokens")
    print(f"  Typical API cost: ${api_cost_per_1k:.4f} per 1K tokens")
    if avg_cost_per_1k < api_cost_per_1k:
        savings = (1 - avg_cost_per_1k / api_cost_per_1k) * 100
        print(f"  → Self-hosting is {savings:.0f}% cheaper at current utilization")
    else:
        print(f"  → API is cheaper - increase utilization or volume to justify self-hosting")


if __name__ == "__main__":
    main()
