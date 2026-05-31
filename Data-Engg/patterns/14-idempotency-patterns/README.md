# Pattern 14: Idempotency in Data Pipelines

## Definition
An operation is idempotent if applying it multiple times produces the same result
as applying it once. Critical for fault tolerance (retries are inevitable).

## Why Idempotency is Non-Negotiable

```
REALITY: In distributed systems, EVERY operation might be executed more than once.
─────────────────────────────────────────────────────────────────────────────

Scenarios that cause re-execution:
1. Network timeout → producer retries → duplicate message
2. Consumer crashes → rebalance → re-reads from last committed offset
3. Checkpoint fails → Flink restores → re-processes events
4. Pipeline retry → Airflow retries task → data written twice
5. Deploy bug → fix → rerun pipeline → data processed again

If your pipeline is NOT idempotent:
• Duplicate charges (billing)
• Double-counted revenue (analytics)
• Excess inventory decrement (e-commerce)
• Duplicate notifications (user experience)
```

## Idempotency Patterns

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  IDEMPOTENCY PATTERNS                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. NATURAL KEY UPSERT                                                       │
│  ─────────────────────                                                       │
│  INSERT INTO orders (order_id, amount, status)                               │
│  VALUES ('ORD-123', 99.99, 'placed')                                         │
│  ON CONFLICT (order_id) DO UPDATE SET                                        │
│    amount = EXCLUDED.amount,                                                 │
│    status = EXCLUDED.status;                                                 │
│                                                                              │
│  WHY: Same order processed twice → same row, not duplicate                   │
│  WHEN: Have a natural unique key (order_id, event_id, etc.)                  │
│                                                                              │
│  2. PARTITION OVERWRITE                                                      │
│  ──────────────────────                                                      │
│  -- Batch pipeline: overwrite entire day's partition                          │
│  INSERT OVERWRITE TABLE revenue PARTITION (date='2024-01-15')                 │
│  SELECT ... FROM events WHERE date = '2024-01-15';                           │
│                                                                              │
│  WHY: Rerun same day → replaces previous result (not adds to it)             │
│  WHEN: Batch pipelines that process whole partitions                         │
│                                                                              │
│  3. DEDUPLICATION BY EVENT_ID                                                │
│  ────────────────────────────                                                │
│  -- In Flink or consumer application                                         │
│  if event_id in seen_events:                                                 │
│      skip()  # Already processed                                             │
│  else:                                                                       │
│      process(event)                                                          │
│      seen_events.add(event_id)                                               │
│                                                                              │
│  WHY: Explicitly skip duplicates                                             │
│  CHALLENGE: Maintaining "seen" set at scale (use Bloom filter + TTL)         │
│                                                                              │
│  4. DETERMINISTIC OUTPUT PATH                                                │
│  ────────────────────────────                                                │
│  -- File output named by input, not by time                                  │
│  output_path = f"s3://lake/output/date={date}/batch={batch_id}.parquet"      │
│                                                                              │
│  WHY: Same batch rerun → overwrites same file (not creates new one)          │
│  WHEN: Batch ETL writing to object storage                                   │
│                                                                              │
│  5. CONDITIONAL WRITE (Compare-and-Swap)                                     │
│  ────────────────────────────────────────                                    │
│  UPDATE inventory SET quantity = quantity - 1                                 │
│  WHERE product_id = 'P1' AND version = 5;                                    │
│  -- Only succeeds if version matches (optimistic locking)                    │
│                                                                              │
│  WHY: Prevents double-decrement even with retries                            │
│  WHEN: Counters, balances, quantities (inherently non-idempotent)            │
│                                                                              │
│  6. IDEMPOTENCY KEY (API Pattern)                                            │
│  ────────────────────────────────                                            │
│  POST /api/payment                                                           │
│  Header: Idempotency-Key: "pay_abc123"                                       │
│  Body: {"amount": 99.99, "to": "merchant"}                                   │
│                                                                              │
│  Server: Check if "pay_abc123" already processed                             │
│  If yes: Return cached response (no re-processing)                           │
│  If no: Process, store result keyed by "pay_abc123", return                  │
│                                                                              │
│  WHY: Client can safely retry without double-payment                         │
│  USED BY: Stripe, PayPal, all payment processors                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Which Operations ARE Idempotent?

```
NATURALLY IDEMPOTENT (safe to repeat):
  • SET balance = 1000 (same result regardless of repeats)
  • INSERT ON CONFLICT UPDATE (upsert)
  • OVERWRITE partition (replaces, doesn't append)
  • DELETE WHERE condition (deleting twice = still deleted)
  • MAX, MIN, LAST_VALUE aggregations

NOT IDEMPOTENT (dangerous to repeat):
  • INSERT (creates duplicates)
  • UPDATE balance = balance + 100 (accumulates!)
  • SUM, COUNT (double-counts on replay)
  • APPEND to file (duplicates data)
  • Sending notifications (double-email)

MAKING NON-IDEMPOTENT OPERATIONS SAFE:
  • INSERT → INSERT ON CONFLICT DO NOTHING (skip duplicates)
  • balance + 100 → Conditional: IF NOT already_applied(event_id)
  • SUM/COUNT → Dedup input first, then aggregate
  • APPEND → Overwrite partition instead
  • Notifications → Dedup by (user, event_id) before sending
```

