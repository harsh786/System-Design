# Semantic RAG Implementation

Demonstrates embedding-based retrieval with:
- **Local sentence-transformer embeddings** (no API needed for embeddings)
- **Semantic chunking** based on sentence similarity
- **Metadata filtering** to narrow search scope
- **Relevance threshold** to reject low-confidence results

## Key Differences from Naive RAG

| Feature | Naive RAG | Semantic RAG |
|---------|-----------|--------------|
| Embeddings | OpenAI API | Local (sentence-transformers) |
| Chunking | Fixed-size | Semantic (similarity-based) |
| Filtering | None | Metadata filters |
| Threshold | None | Rejects low-relevance results |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # Only needed for generation (OpenAI)
python main.py
```

Note: Embeddings run locally — no API key needed for the retrieval part.
