# Problem 16: Real-Time Geospatial Pipeline

### Problem 16: Real-Time Geospatial Pipeline
```
SCALE: 10M location updates/min (ride-sharing)
ARCH: GPS → Kafka → Flink (geofencing, ETA) → Redis (live positions)
WHY REDIS GEO: O(log n) radius queries, sorted sets
PARTITIONING: By geographic grid (H3 hexagonal)
```
