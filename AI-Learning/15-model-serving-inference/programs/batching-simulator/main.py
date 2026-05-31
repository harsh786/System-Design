"""
Batching Simulator
==================
Simulates different batching strategies and compares their performance.
"""

import random
import time
from dataclasses import dataclass, field
from tabulate import tabulate


@dataclass
class Request:
    id: int
    input_tokens: int
    output_tokens: int
    arrival_time: float
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def latency(self) -> float:
        return self.end_time - self.arrival_time

    @property
    def time_to_first_token(self) -> float:
        return self.start_time - self.arrival_time


# Simulation parameters
PREFILL_TIME_PER_TOKEN = 0.00005  # 50µs per token (parallel, fast)
DECODE_TIME_PER_TOKEN_BASE = 0.030  # 30ms per token (sequential, slow)
GPU_UTILIZATION_SINGLE = 0.15  # 15% for single request decode
MAX_BATCH_SIZE = 32


def generate_requests(num_requests: int, arrival_rate: float = 10.0) -> list[Request]:
    """Generate random requests with Poisson arrival."""
    random.seed(42)
    requests = []
    current_time = 0.0
    for i in range(num_requests):
        current_time += random.expovariate(arrival_rate)
        input_tokens = random.randint(50, 2000)
        output_tokens = random.randint(20, 500)
        requests.append(Request(id=i, input_tokens=input_tokens, output_tokens=output_tokens, arrival_time=current_time))
    return requests


def simulate_no_batching(requests: list[Request]) -> dict:
    """Process one request at a time."""
    current_time = 0.0
    total_tokens = 0

    for req in requests:
        current_time = max(current_time, req.arrival_time)
        req.start_time = current_time + req.input_tokens * PREFILL_TIME_PER_TOKEN
        decode_time = req.output_tokens * DECODE_TIME_PER_TOKEN_BASE
        req.end_time = req.start_time + decode_time
        current_time = req.end_time
        total_tokens += req.output_tokens

    total_time = requests[-1].end_time - requests[0].arrival_time
    return {
        "strategy": "No Batching",
        "throughput": total_tokens / total_time,
        "avg_latency": sum(r.latency for r in requests) / len(requests),
        "p99_latency": sorted(r.latency for r in requests)[int(len(requests) * 0.99)],
        "avg_ttft": sum(r.time_to_first_token for r in requests) / len(requests),
        "gpu_utilization": GPU_UTILIZATION_SINGLE * 100,
        "total_time": total_time,
    }


def simulate_static_batching(requests: list[Request], batch_size: int = 8) -> dict:
    """Process requests in fixed-size batches."""
    current_time = 0.0
    total_tokens = 0

    for i in range(0, len(requests), batch_size):
        batch = requests[i:i + batch_size]
        current_time = max(current_time, batch[-1].arrival_time)

        # Prefill all in batch (parallel)
        max_input = max(r.input_tokens for r in batch)
        prefill_time = max_input * PREFILL_TIME_PER_TOKEN

        for req in batch:
            req.start_time = current_time + prefill_time

        # Decode: wait for longest output in batch
        max_output = max(r.output_tokens for r in batch)
        # Batched decode is faster per-token (amortize weight reads)
        decode_time_per_tok = DECODE_TIME_PER_TOKEN_BASE / (1 + 0.3 * len(batch))
        decode_time = max_output * decode_time_per_tok

        for req in batch:
            req.end_time = req.start_time + decode_time  # all wait for longest
            total_tokens += req.output_tokens

        current_time = batch[0].end_time

    total_time = requests[-1].end_time - requests[0].arrival_time
    gpu_util = min(90, GPU_UTILIZATION_SINGLE * 100 * batch_size * 0.6)
    return {
        "strategy": f"Static Batch ({batch_size})",
        "throughput": total_tokens / total_time,
        "avg_latency": sum(r.latency for r in requests) / len(requests),
        "p99_latency": sorted(r.latency for r in requests)[int(len(requests) * 0.99)],
        "avg_ttft": sum(r.time_to_first_token for r in requests) / len(requests),
        "gpu_utilization": gpu_util,
        "total_time": total_time,
    }


def simulate_continuous_batching(requests: list[Request], max_batch: int = 32) -> dict:
    """Continuous batching - requests enter/exit independently."""
    current_time = 0.0
    total_tokens = 0
    active: list[dict] = []  # {request, tokens_remaining}
    queue = list(requests)
    completed = []

    # Simulate iteration by iteration
    while queue or active:
        # Add new requests from queue (up to max_batch)
        while queue and len(active) < max_batch:
            req = queue[0]
            if req.arrival_time <= current_time:
                queue.pop(0)
                # Prefill (fast, parallel with decode)
                prefill_time = req.input_tokens * PREFILL_TIME_PER_TOKEN * 0.5  # overlapped
                req.start_time = current_time + prefill_time
                active.append({"request": req, "remaining": req.output_tokens})
            else:
                break

        if not active:
            if queue:
                current_time = queue[0].arrival_time
            continue

        # One decode step for all active requests
        batch_size_now = len(active)
        step_time = DECODE_TIME_PER_TOKEN_BASE / (1 + 0.4 * batch_size_now)
        current_time += step_time

        # Decrement tokens for all active
        finished = []
        for item in active:
            item["remaining"] -= 1
            total_tokens += 1
            if item["remaining"] <= 0:
                item["request"].end_time = current_time
                completed.append(item["request"])
                finished.append(item)

        for f in finished:
            active.remove(f)

    total_time = max(r.end_time for r in requests) - requests[0].arrival_time
    gpu_util = min(90, GPU_UTILIZATION_SINGLE * 100 * max_batch * 0.8)
    return {
        "strategy": f"Continuous Batch ({max_batch})",
        "throughput": total_tokens / total_time,
        "avg_latency": sum(r.latency for r in requests) / len(requests),
        "p99_latency": sorted(r.latency for r in requests)[int(len(requests) * 0.99)],
        "avg_ttft": sum(r.time_to_first_token for r in requests) / len(requests),
        "gpu_utilization": gpu_util,
        "total_time": total_time,
    }


def main():
    print("=" * 80)
    print("BATCHING STRATEGY SIMULATOR")
    print("=" * 80)

    num_requests = 100
    arrival_rate = 5.0  # requests per second

    print(f"\nSimulating {num_requests} requests at {arrival_rate} req/sec arrival rate")
    print(f"Input tokens: 50-2000 (random), Output tokens: 20-500 (random)\n")

    # Generate requests (fresh copy for each simulation)
    results = []

    reqs = generate_requests(num_requests, arrival_rate)
    results.append(simulate_no_batching(reqs))

    reqs = generate_requests(num_requests, arrival_rate)
    results.append(simulate_static_batching(reqs, batch_size=8))

    reqs = generate_requests(num_requests, arrival_rate)
    results.append(simulate_static_batching(reqs, batch_size=32))

    reqs = generate_requests(num_requests, arrival_rate)
    results.append(simulate_continuous_batching(reqs, max_batch=32))

    # Print comparison
    headers = ["Strategy", "Throughput (tok/s)", "Avg Latency (s)", "P99 Latency (s)", "Avg TTFT (s)", "GPU Util %"]
    rows = []
    for r in results:
        rows.append([
            r["strategy"],
            f"{r['throughput']:.1f}",
            f"{r['avg_latency']:.2f}",
            f"{r['p99_latency']:.2f}",
            f"{r['avg_ttft']:.3f}",
            f"{r['gpu_utilization']:.0f}%",
        ])

    print(tabulate(rows, headers=headers, tablefmt="grid"))

    # Speedup comparison
    baseline = results[0]["throughput"]
    print("\n--- Throughput Speedup vs No Batching ---")
    for r in results:
        speedup = r["throughput"] / baseline
        bar = "█" * int(speedup * 5)
        print(f"  {r['strategy']:<25} {speedup:>5.1f}x  {bar}")

    print("\n--- Key Insight ---")
    print("Continuous batching achieves highest throughput AND lowest latency")
    print("because requests enter/exit independently - no waiting for batch completion.")


if __name__ == "__main__":
    main()
