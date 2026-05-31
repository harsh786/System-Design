# Problem 44: Streaming Deduplication at Scale

### Problem 44: Streaming Deduplication at Scale
```
ARCH: Kafka → Flink (dedup by event_id) → Clean stream
CHALLENGE: State grows unbounded (remember all seen IDs)
SOLUTIONS:
  • Bloom filter (probabilistic, false positives ok for some cases)
  • Time-bounded dedup (only dedup within 1-hour window)
  • RocksDB state with TTL (auto-expire old IDs)
```
