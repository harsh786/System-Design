# Problem 70: Data Pipeline Idempotency Framework

### Problem 70: Data Pipeline Idempotency Framework
```
PATTERN: Same input processed multiple times → same output
IMPLEMENTATION:
  1. Dedup by event_id at ingestion (Bloom filter + DB check)
  2. Overwrite partitions (not append) for batch
  3. Upsert by natural key for incremental
  4. Idempotent aggregations (SUM is NOT idempotent, MAX is)
WHY CRITICAL: Retries are inevitable (network, crashes, restarts)
```
