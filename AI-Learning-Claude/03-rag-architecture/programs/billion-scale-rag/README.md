# Billion-Scale RAG Simulator

## What This Demonstrates

This program simulates the challenges of scaling Retrieval-Augmented Generation (RAG) to millions/billions of records and shows how to solve them.

### Key Concepts

1. **Naive Retrieval** - Brute-force search across ALL documents. Works fine at 1K docs, fails at 1M+.

2. **Hierarchical Retrieval** - Two-stage approach:
   - Stage 1 (Coarse): Route query to relevant topic/shard (fast, eliminates 90%+ of docs)
   - Stage 2 (Fine): Search within the relevant shard only
   - Stage 3 (Rerank): Re-score top results for precision

3. **Semantic Caching** - Cache semantically similar queries to avoid redundant searches. If someone asked "What is the refund policy?" 5 minutes ago, a new query "How do I get a refund?" should hit the cache.

4. **Sharding Strategy** - Split documents by topic/domain into independent shards. Route queries to relevant shard(s) only. Searching 1 shard out of 10 is ~10x faster.

### Performance Impact (Simulated)

| Strategy | Latency | Cost |
|----------|---------|------|
| Naive (brute force) | ~500ms | High |
| Hierarchical | ~80ms | Medium |
| Cached + Hierarchical | ~5ms (hit) | Low |

## Running

```bash
pip install -r requirements.txt
python main.py
```

Note: This program uses simulated embeddings (numpy random vectors) so it does NOT require an OpenAI API key to run. The `.env.example` is provided for extending with real embeddings.

## Learning Outcomes

- Understand why naive RAG breaks at scale
- Learn the hierarchical retrieval pattern used by production systems
- See how semantic caching dramatically reduces costs
- Understand sharding strategies for distributed RAG
