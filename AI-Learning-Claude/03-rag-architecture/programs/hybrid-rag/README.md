# Hybrid RAG Implementation

Demonstrates combining **BM25 keyword search** with **vector semantic search** using Reciprocal Rank Fusion (RRF) to get the best of both worlds.

## Key Insight

| Query Type | Keyword (BM25) | Semantic (Vector) | Hybrid |
|-----------|---------------|-------------------|--------|
| "ERROR_CODE_5021" | ✅ Exact match | ❌ No semantic meaning | ✅ |
| "how to get money back" | ❌ No word "refund" | ✅ Understands meaning | ✅ |
| "FlowEngine API rate limit" | ✅ Keywords match | ✅ Meaning matches | ✅✅ |

Hybrid search catches what either method alone would miss.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## What You'll See

The program runs each query three ways and compares results:
1. BM25 only (keyword)
2. Vector only (semantic)
3. Hybrid (RRF fusion of both)
