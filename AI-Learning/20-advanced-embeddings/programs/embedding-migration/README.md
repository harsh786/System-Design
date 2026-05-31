# Embedding Model Migration Simulator

Simulates a blue-green embedding model migration with zero downtime,
demonstrating dual-write, background re-embedding, quality comparison,
and atomic switch.

## What This Demonstrates

1. **Blue-green deployment**: old and new collections running in parallel
2. **Dual-write**: new documents indexed in both collections
3. **Background re-embedding**: old documents gradually migrated
4. **Quality comparison**: automated testing before switch
5. **Atomic switch**: instant cutover with rollback capability
6. **Migration report**: cost, time, and quality summary

## Run

```bash
pip install -r requirements.txt
python main.py
```

## No API Keys Required

Uses simulated embeddings to demonstrate the migration workflow.
