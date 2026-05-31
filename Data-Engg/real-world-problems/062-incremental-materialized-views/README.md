# Problem 62: Incremental Materialized Views

### Problem 62: Incremental Materialized Views
```
PATTERN: Instead of recomputing entire view, apply DELTA
EXAMPLE: SUM(revenue) → new row arrives → just add to existing sum
WHY: Full recomputation of 1TB table takes hours; increment takes seconds
FLINK SQL: Continuous queries ARE incremental materialized views
LIMITATION: Not all aggregations are incrementally computable (e.g., MEDIAN)
```
