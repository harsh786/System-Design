# Consent Manager

Demonstrates a consent management system that controls what AI operations are allowed based on user consent.

## What It Shows

1. Three users with different consent levels
2. Operations blocked when consent not given
3. Consent withdrawal triggers cascade effects
4. Full consent audit log

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Users

- **User A (Alice)**: Full consent — storage, RAG, training
- **User B (Bob)**: Partial consent — storage, RAG, NO training
- **User C (Carol)**: Minimal consent — storage only
