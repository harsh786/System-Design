# Problem 74: Cross-Region Event Streaming

### Problem 74: Cross-Region Event Streaming
```
ARCH: Local Kafka → MirrorMaker 2 → Remote Kafka (active-active)
CHALLENGE: Exactly-once across regions (CAP theorem: pick 2 of 3)
SOLUTION: Eventual consistency + conflict resolution (LWW / vector clocks)
LATENCY: 50-200ms inter-region (acceptable for async replication)
USE CASE: Multi-region active-active for disaster recovery
```
