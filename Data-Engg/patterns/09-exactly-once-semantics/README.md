# Pattern 09: Exactly-Once Processing Semantics

## The Three Delivery Guarantees

```
AT-MOST-ONCE:  Fire and forget. May lose messages.
               Fast, but unreliable.
               Use case: Telemetry, non-critical logs

AT-LEAST-ONCE: Retry until ACK. May duplicate messages.
               Reliable, but needs dedup downstream.
               Use case: Most event processing (with idempotent consumers)

EXACTLY-ONCE:  Each message processed exactly once.
               Holy grail, but expensive and complex.
               Use case: Financial transactions, billing, inventory counts
```

## How Exactly-Once Works (End-to-End)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXACTLY-ONCE: Source → Kafka → Flink → Sink                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  KAFKA PRODUCER (Idempotent + Transactional):                                │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  enable.idempotence = true                                      │         │
│  │  → Broker deduplicates by (producer_id, sequence_number)        │         │
│  │  → Network retry won't cause duplicate write                    │         │
│  │                                                                 │         │
│  │  transactional.id = "order-producer-1"                          │         │
│  │  → Atomic multi-partition writes                                │         │
│  │  → Either ALL messages committed, or NONE                       │         │
│  │  → Consumer with isolation.level=read_committed sees only       │         │
│  │    committed data                                               │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  FLINK PROCESSING (Checkpoint Barrier):                                      │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                                                                 │         │
│  │  Chandy-Lamport Algorithm (distributed snapshots):              │         │
│  │                                                                 │         │
│  │  Source ──► Operator A ──► Operator B ──► Sink                  │         │
│  │    ↓           ↓              ↓            ↓                    │         │
│  │  [barrier]  [barrier]     [barrier]    [barrier]                │         │
│  │                                                                 │         │
│  │  On checkpoint trigger (every 60s):                             │         │
│  │  1. Source emits barrier (special marker in stream)             │         │
│  │  2. Each operator, on receiving barrier:                        │         │
│  │     a. Stops processing                                         │         │
│  │     b. Snapshots its state to durable storage (S3)              │         │
│  │     c. Forwards barrier downstream                              │         │
│  │     d. Resumes processing                                       │         │
│  │  3. Sink: Pre-commits output (but doesn't finalize)             │         │
│  │  4. All operators checkpointed → coordinator commits            │         │
│  │  5. Sink: Finalizes output (2PC commit phase)                   │         │
│  │                                                                 │         │
│  │  On failure:                                                    │         │
│  │  1. Restore all operators from last SUCCESSFUL checkpoint       │         │
│  │  2. Source re-reads from Kafka offset saved in checkpoint       │         │
│  │  3. Sink: Aborts any uncommitted output                         │         │
│  │  4. Processing resumes from consistent state                    │         │
│  │  → Result: No duplicates, no data loss                          │         │
│  │                                                                 │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  SINK (Two-Phase Commit OR Idempotent):                                      │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                                                                 │         │
│  │  Option A: 2PC Sink (Kafka, some databases):                    │         │
│  │  • Pre-commit: Write to staging/transaction                     │         │
│  │  • Commit: Finalize when checkpoint completes                   │         │
│  │  • Abort: Rollback if checkpoint fails                          │         │
│  │  • Guarantees: TRUE exactly-once                                │         │
│  │                                                                 │         │
│  │  Option B: Idempotent Sink (most databases):                    │         │
│  │  • Write with unique key (event_id)                             │         │
│  │  • ON CONFLICT DO NOTHING / UPSERT                              │         │
│  │  • Replay is safe (same data → same result)                     │         │
│  │  • Guarantees: Effectively exactly-once                         │         │
│  │                                                                 │         │
│  │  Option C: Transactional sink with offset tracking:             │         │
│  │  • Store Kafka offset IN the same DB transaction as data        │         │
│  │  • On restart: Read last committed offset from DB               │         │
│  │  • Resume from that offset (skip already-written data)          │         │
│  │  • Guarantees: TRUE exactly-once                                │         │
│  │                                                                 │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Performance Impact

```
EXACTLY-ONCE COST:
──────────────────
• Kafka idempotent producer: ~3% throughput reduction (sequence tracking)
• Kafka transactions: ~20% latency increase (2PC with coordinator)
• Flink checkpointing: Back-pressure during checkpoint (pauses ~100ms)
• 2PC sinks: Double write (staging + final)

WHEN IT'S WORTH IT:
• Financial: $1 duplicate charge = angry customer + refund cost
• Inventory: 1 duplicate decrement = oversell = cancelled orders
• Billing: $0.01 extra × 1M users = $10K/day error

WHEN IT'S NOT WORTH IT:
• Metrics/counters: ±0.001% accuracy is fine
• Log aggregation: Duplicate log line doesn't matter
• Recommendations: Slightly wrong score is acceptable
```

