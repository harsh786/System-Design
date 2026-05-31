# Problem 12: Data Quality Pipeline

### Problem 12: Data Quality Pipeline
```
SCALE: 500 tables, 10K quality checks/day
ARCH: dbt tests + Great Expectations + custom Flink checks
Pattern: Circuit breaker (halt pipeline if quality drops below threshold)
ALERTING: Tiered (P1: data loss, P2: freshness, P3: coverage)
```
