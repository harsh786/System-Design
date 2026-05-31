# Problem 20: Streaming Joins (Order + Payment + Shipment)

### Problem 20: Streaming Joins (Order + Payment + Shipment)
```
SCALE: 3 streams, 50K events/sec each, join within 1-hour window
ARCH: Kafka → Flink (temporal join with watermarks) → Enriched events
WHY FLINK: Best-in-class streaming join support
CHALLENGE: Late data, out-of-order events, state management
```
