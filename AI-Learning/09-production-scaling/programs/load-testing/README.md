# AI API Load Tester

A load testing tool for AI API endpoints that measures latency distribution, throughput, and error rates under varying concurrency levels.

## What This Demonstrates

- **Concurrent request handling:** How AI endpoints behave under load
- **Latency percentiles:** P50, P95, P99 — the metrics that matter
- **Degradation detection:** Identifying when an endpoint starts struggling
- **Capacity planning:** Understanding your system's limits

## How It Works

1. Sends configurable concurrent requests to an AI endpoint (simulated by default)
2. Measures response time for each request
3. Calculates latency percentiles (P50, P95, P99)
4. Detects performance degradation as concurrency increases
5. Outputs a comprehensive load test report

## Running

```bash
pip install -r requirements.txt
python main.py
```

## Key Concepts

- **P50 (median):** Half of requests are faster than this
- **P95:** 95% of requests are faster — this is what most users experience
- **P99:** Only 1% of requests are slower — this catches tail latency issues
- **Throughput:** Requests successfully completed per second
- **Degradation:** When P95 latency increases >2x from baseline, the system is struggling
