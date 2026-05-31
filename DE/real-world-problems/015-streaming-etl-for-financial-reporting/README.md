# Problem 15: Streaming ETL for Financial Reporting

### Problem 15: Streaming ETL for Financial Reporting
```
SCALE: 10M transactions/day, reconciliation across 50 systems
ARCH: Kafka → Flink (joins, enrichment) → Gold tables → Reporting DB
EXACTLY-ONCE: Required (financial data, no duplicates allowed)
AUDIT: Every transformation logged with lineage
```
