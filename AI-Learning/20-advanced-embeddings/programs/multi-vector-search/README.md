# Multi-Vector Search (Parent-Child)

Implements hierarchical parent-child multi-vector search, where documents
are embedded at two levels: section summary and individual chunks.

## What This Demonstrates

1. **Flat search**: search all chunks equally (standard approach)
2. **Hierarchical search**: find relevant parents first, then search within children
3. **Comparison**: shows improved precision with hierarchical approach
4. **Score decomposition**: parent relevance + child specificity

## Run

```bash
pip install -r requirements.txt
python main.py
```

## No API Keys Required

Uses simulated embeddings to demonstrate the multi-vector architecture.
