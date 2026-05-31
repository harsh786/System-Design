# Matryoshka Embeddings Demo

Demonstrates Matryoshka embeddings using OpenAI's text-embedding-3-small,
showing how truncated dimensions maintain search quality.

## What This Demonstrates

1. Same text embedded at different dimensions (64, 128, 256, 512, 1536)
2. Search quality comparison at each dimension
3. Storage savings vs quality tradeoff
4. Adaptive retrieval: coarse (128-dim) → precise (1536-dim)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
```

## Run

```bash
python main.py
```

## Requirements

- OpenAI API key (uses text-embedding-3-small)
- Minimal API usage (~20 embedding calls)
