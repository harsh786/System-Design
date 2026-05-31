# Embedding Model Comparison

## What This Program Does

Compares two embedding models — OpenAI's `text-embedding-3-small` (cloud API) and `all-MiniLM-L6-v2` (local, open-source) — on the same set of sentences to show how different models produce different similarity rankings.

## Concepts Demonstrated

1. **Model differences** — same text, different similarity rankings
2. **Dimension comparison** — 1536d (OpenAI) vs 384d (MiniLM)
3. **Speed comparison** — API latency vs local inference
4. **Agreement/disagreement** — where models align and diverge
5. **Dimension reduction impact** — truncating OpenAI embeddings

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
```

Note: First run will download the sentence-transformers model (~80MB).

## Running

```bash
python main.py
```

## Key Takeaways

- Different models rank similarity differently (especially for nuanced pairs)
- Local models are faster per-call but lower quality
- OpenAI's Matryoshka embeddings allow dimension truncation with graceful degradation
