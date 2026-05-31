# Problem 14: CDC-Based Data Warehouse Sync

### Problem 14: CDC-Based Data Warehouse Sync
```
SCALE: 200 source tables, 5-minute freshness SLA
ARCH: Debezium → Kafka → Flink → Iceberg (lakehouse)
WHY NOT full-load: 200 tables × full scan = DB overload
MERGE strategy: Upsert by PK, soft-delete tracking
```
