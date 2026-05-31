# Index Benchmarking

## What This Program Does

Generates synthetic vectors at different scales (1K, 10K, 100K) and benchmarks search performance to demonstrate how latency grows with dataset size and the impact of approximate nearest neighbor search.

## Concepts Demonstrated

1. **Latency vs scale** — how search time grows with more vectors
2. **Brute-force vs ANN** — speed difference and recall tradeoff
3. **Batch insert performance** — throughput at different scales
4. **Recall accuracy** — what percentage of true nearest neighbors ANN finds

## Setup

```bash
pip install -r requirements.txt
```

No API keys needed — uses synthetic random vectors.

## Running

```bash
python main.py
```

Note: The 100K benchmark may take 1-2 minutes to insert vectors.

## Key Takeaways

- Brute-force is fast at 1K but unacceptable at 100K+
- ANN (HNSW) maintains sub-10ms latency regardless of scale
- Recall is typically 95-99% — you rarely miss truly relevant results
- Insert throughput degrades as the index grows
