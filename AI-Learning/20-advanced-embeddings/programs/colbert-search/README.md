# ColBERT-Style Multi-Vector Search

Simulates ColBERT's late interaction scoring mechanism to demonstrate
how token-level vectors improve search quality over single-vector approaches.

## What This Demonstrates

1. **Single-vector search**: one embedding per document (standard approach)
2. **ColBERT MaxSim scoring**: one embedding per token, sum of max similarities
3. **Side-by-side comparison**: cases where ColBERT wins (exact phrases, partial matches)

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Key Concepts

- **MaxSim**: For each query token, find its maximum similarity with any document token
- **Late Interaction**: Query and document encoded independently, interact at search time
- **Token-level matching**: Individual words contribute independently to the score
