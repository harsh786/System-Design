# Problem 36: Streaming CDC to Data Warehouse (Snowflake/BQ)

### Problem 36: Streaming CDC to Data Warehouse (Snowflake/BQ)
```
ARCH: Debezium → Kafka → Kafka Connect → Snowflake/BQ
CHALLENGE: Merge (upsert) in warehouse (not just append)
SOLUTION: Snowpipe Streaming + MERGE tasks, or Flink → staging → MERGE
```
