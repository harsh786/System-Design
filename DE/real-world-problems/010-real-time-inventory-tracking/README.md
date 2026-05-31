# Problem 10: Real-Time Inventory Tracking

### Problem 10: Real-Time Inventory Tracking
```
SCALE: 10M SKUs, 1M updates/min (from POS, warehouse, returns)
ARCH: CDC (all stores) → Kafka → Flink (aggregate per SKU) → Redis + Postgres
WHY CDC: Capture every inventory change without app modification
WHY REDIS: <1ms availability check for checkout
CONSISTENCY: Eventual (acceptable: "was available 2 seconds ago")
```
