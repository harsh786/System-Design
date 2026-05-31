# Vector Search Basics

## What This Program Does

Demonstrates fundamental vector search operations using ChromaDB (an embedded vector database) and OpenAI embeddings. You'll see how text gets embedded, stored, and retrieved by semantic similarity.

## Concepts Demonstrated

1. **Embedding text** into vectors using OpenAI's API
2. **Storing vectors** in ChromaDB with metadata
3. **Similarity search** — finding relevant results by meaning, not keywords
4. **Metadata filtering** — combining semantic search with structured filters
5. **Similarity scores** — understanding distance/relevance numbers

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
```

## Running

```bash
python main.py
```

## Expected Output

- A collection of movie descriptions embedded and stored
- Query results showing the most similar movies to various queries
- Comparison of results with and without metadata filters
- Similarity score visualization

## Key Takeaways

- Similar meanings produce close vectors (even with different words)
- Metadata filters let you scope search to subsets
- ChromaDB handles embedding + storage + search in one package
