# Naive RAG Implementation

A complete, minimal RAG pipeline demonstrating the core flow:
**Documents → Chunk → Embed → Store → Query → Retrieve → Generate**

## What This Demonstrates

- Fixed-size chunking with overlap
- OpenAI embeddings stored in ChromaDB
- Simple top-K retrieval
- Answer generation with citations
- Timing at every step

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```

## Architecture

```
Query → Embed → ChromaDB Search (Top-3) → Stuff into Prompt → GPT-4 → Answer + Citations
```

## Key Limitation

This is the simplest possible RAG. It has no:
- Reranking (retrieved chunks may not be the best)
- Hybrid search (misses keyword matches)
- Quality checks (no relevance threshold)

These limitations are addressed in the other programs.
