# Semantic Caching Layer for AI

A demonstration of exact-match and semantic caching for AI API calls, showing how caching dramatically reduces cost and latency.

## What This Demonstrates

- **Exact-match cache:** Same question → instant cached response
- **Semantic cache:** Similar questions → cached response (using embedding similarity)
- **Cost savings:** How much money caching saves at scale
- **Latency improvement:** Milliseconds vs seconds

## How It Works

1. Queries are first checked against an exact-match cache (hash lookup)
2. On miss, the query is embedded and compared against cached embeddings (cosine similarity)
3. If similarity exceeds threshold (default 0.92), return cached response
4. On full miss, call the LLM and store result in both caches

## Running

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```

## Configuration

- `SIMILARITY_THRESHOLD`: How similar queries must be for semantic cache hit (0.0-1.0)
- Higher threshold = fewer false hits but lower hit rate
- Lower threshold = more hits but risk of returning wrong answers

## Key Insight

In production, 20-50% of queries to an AI system are semantically equivalent. Caching these saves thousands of dollars monthly.
