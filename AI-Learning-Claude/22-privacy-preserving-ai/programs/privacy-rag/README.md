# Privacy-Preserving RAG

Demonstrates RAG that detects and removes PII before embedding, then optionally re-hydrates for authorized users.

## What It Shows

1. Ingests documents containing PII (names, emails, SSNs, phone numbers)
2. Detects PII using regex + pattern matching
3. Anonymizes documents before creating embeddings
4. Searches using anonymized text (PII never in vector space)
5. Compares: standard RAG (leaks PII) vs privacy RAG (PII protected)
6. Shows re-hydration for authorized users only

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Key Concepts

- PII detection at ingestion time
- Consistent pseudonymization across documents
- Encrypted PII mapping for authorized re-hydration
- Search quality comparison with/without anonymization
