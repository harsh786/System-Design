# Pattern 17: Streaming Joins

## Types of Streaming Joins

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STREAMING JOIN TYPES                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. STREAM-STREAM JOIN (Window Join)                                         │
│  ─────────────────────────────────────                                       │
│  Join two event streams within a time window.                                │
│                                                                              │
│  Example: Join clicks with purchases within 30 minutes                       │
│  SELECT c.user_id, c.page, p.amount                                          │
│  FROM clicks c JOIN purchases p                                              │
│  ON c.user_id = p.user_id                                                    │
│  AND p.event_time BETWEEN c.event_time AND c.event_time + INTERVAL '30 MIN'  │
│                                                                              │
│  HOW IT WORKS:                                                               │
│  • Buffer both streams in state (RocksDB)                                    │
│  • For each new event, check other stream's buffer for matches               │
│  • Emit match when found                                                     │
│  • Expire old events from buffer (based on window)                           │
│                                                                              │
│  STATE SIZE: |left_stream| × window_size + |right_stream| × window_size      │
│  CHALLENGE: Large windows = huge state = expensive                           │
│                                                                              │
│  2. STREAM-TABLE JOIN (Enrichment/Lookup)                                    │
│  ─────────────────────────────────────────                                   │
│  Enrich a stream with latest values from a slowly-changing dimension.        │
│                                                                              │
│  Example: Enrich orders with latest customer info                            │
│  SELECT o.*, c.name, c.tier                                                  │
│  FROM orders o                                                               │
│  JOIN customers c  -- CDC stream, compacted to latest per key                │
│  ON o.customer_id = c.customer_id                                            │
│                                                                              │
│  HOW IT WORKS:                                                               │
│  • Customers stream materialized as a lookup table (KTable)                  │
│  • Each order event: lookup customer by key in local state                   │
│  • Always uses LATEST value (no window needed)                               │
│                                                                              │
│  STATE SIZE: |unique_keys| × record_size (just the table)                    │
│  ADVANTAGE: Fast lookup (<1ms), small state                                  │
│                                                                              │
│  3. TEMPORAL JOIN (Point-in-Time)                                            │
│  ─────────────────────────────────                                           │
│  Join with the dimension value that was valid AT THE TIME of the event.      │
│                                                                              │
│  Example: Order at 10:00 → use customer tier VALID at 10:00                  │
│  (Even if customer upgraded to Gold at 10:05, order sees Silver)             │
│                                                                              │
│  SELECT o.*, c.tier                                                          │
│  FROM orders o                                                               │
│  JOIN customers FOR SYSTEM_TIME AS OF o.order_time c                         │
│  ON o.customer_id = c.customer_id                                            │
│                                                                              │
│  WHY: Prevents "future data leakage" in ML features                          │
│  HOW: Maintain versioned state (keep history of changes per key)             │
│  STATE: Larger (all versions within retention window)                        │
│                                                                              │
│  4. INTERVAL JOIN                                                            │
│  ──────────────────                                                          │
│  Like stream-stream but with asymmetric time bounds.                         │
│                                                                              │
│  SELECT o.*, p.*                                                             │
│  FROM orders o JOIN payments p                                               │
│  ON o.order_id = p.order_id                                                  │
│  AND p.time BETWEEN o.time AND o.time + INTERVAL '1 HOUR'                    │
│                                                                              │
│  Payment must arrive within 1 hour AFTER order (not before).                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Scalability Considerations

```
STREAM-STREAM JOIN STATE MANAGEMENT:
────────────────────────────────────

Problem: Join clicks (1M/sec) with purchases (100K/sec) within 30 min
State needed: 30min × 1M/sec × 1KB = 1.8 TB (clicks side alone!)

Solutions:
1. Reduce window: 30min → 5min (business acceptable? 80% of purchases within 5min)
2. Pre-filter: Only keep clicks on product pages (reduce 10x)
3. Partition state: Hash by user_id → 200 parallel operators, each 9GB
4. RocksDB: Spills to SSD (not all in memory)
5. TTL cleanup: Aggressive expiry of matched/expired events

REAL-WORLD SIZING:
  Flink cluster for above: 50 TaskManagers × 32GB RAM × 500GB SSD each
  Total: 1.6TB RAM + 25TB SSD
  Cost: ~$50K/month on AWS (r5.2xlarge instances)
```

