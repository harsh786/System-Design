# Problem 94: Streaming Data Warehouse (Materialize/RisingWave)

### Problem 94: Streaming Data Warehouse (Materialize/RisingWave)
```
CONCEPT: SQL materialized views that update automatically as data changes
ARCH: Kafka → Materialize/RisingWave → Always-fresh query results
WHY: No ETL needed! Define view, it stays updated in real-time
LIMITATION: Complex joins = large state, expensive to maintain
BEST FOR: Operational analytics (dashboards that need second-freshness)
```
