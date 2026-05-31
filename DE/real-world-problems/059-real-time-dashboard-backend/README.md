# Problem 59: Real-Time Dashboard Backend

### Problem 59: Real-Time Dashboard Backend
```
ARCH: Events → Kafka → Flink (pre-aggregate) → Druid/Pinot → Dashboard
WHY PRE-AGGREGATE: 100K events/sec can't be queried raw in real-time
REFRESH: Dashboard polls every 5 seconds, gets pre-computed metrics
CACHE: Redis between Druid and dashboard for sub-10ms response
```
