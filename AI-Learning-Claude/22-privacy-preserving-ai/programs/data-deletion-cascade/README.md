# Data Deletion Cascade

Simulates the full GDPR "right to erasure" deletion cascade across an AI system.

## What It Shows

1. Creates a simulated AI system with: documents, chunks, vectors, cache, memory, logs
2. User requests deletion
3. Shows the complete cascade: find → delete → verify
4. Proves post-deletion search returns nothing
5. Prints deletion audit trail with timing

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Key Insight

Deletion in AI systems touches 8+ subsystems. Without proper tracking (document → chunk → vector ID mapping), deletion is impossible.
