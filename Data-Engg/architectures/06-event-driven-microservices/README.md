# Event-Driven Microservices Data Architecture

## Complete Pattern: CDC + Event Sourcing + CQRS + Saga + DLQ

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│              EVENT-DRIVEN MICROSERVICES DATA ARCHITECTURE                          │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  CORE PRINCIPLE: Events are first-class citizens. Services communicate            │
│  through events, not direct calls. Data consistency through eventual consistency. │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ SERVICE MESH (30 Microservices)                                             │  │
│  │                                                                             │  │
│  │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │  │
│  │ │ Order   │ │ Payment │ │Inventory│ │Shipping │ │ Notify  │             │  │
│  │ │ Service │ │ Service │ │ Service │ │ Service │ │ Service │             │  │
│  │ │         │ │         │ │         │ │         │ │         │             │  │
│  │ │ Postgres│ │ Postgres│ │ Redis + │ │ MongoDB │ │ (no DB) │             │  │
│  │ │ + Outbox│ │ + Outbox│ │ Postgres│ │         │ │         │             │  │
│  │ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘            │  │
│  │      │           │           │           │           │                   │  │
│  │  ┌───▼───────────▼───────────▼───────────▼───────────▼───────────────┐  │  │
│  │  │                    KAFKA (Event Backbone)                           │  │  │
│  │  │                                                                    │  │  │
│  │  │  Domain Event Topics:                                              │  │  │
│  │  │  • orders.created    • payments.captured    • inventory.reserved   │  │  │
│  │  │  • orders.cancelled  • payments.refunded    • inventory.released   │  │  │
│  │  │  • orders.completed  • payments.failed      • shipments.dispatched │  │  │
│  │  │                                                                    │  │  │
│  │  │  Infrastructure Topics:                                            │  │  │
│  │  │  • dead-letter-queue  • audit-log  • saga-state                    │  │  │
│  │  │                                                                    │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  PATTERNS IN ACTION:                                                              │
│                                                                                   │
│  1. TRANSACTIONAL OUTBOX (Reliable Event Publishing)                              │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Problem: How to update DB AND publish event atomically?                    │  │
│  │  Wrong: Update DB then publish (if publish fails → inconsistent)            │  │
│  │  Wrong: Publish then update DB (if DB fails → event without state)          │  │
│  │                                                                             │  │
│  │  Solution: Outbox Pattern                                                   │  │
│  │  BEGIN TRANSACTION;                                                         │  │
│  │    INSERT INTO orders (id, ...) VALUES (...);                               │  │
│  │    INSERT INTO outbox (id, topic, payload) VALUES (..., 'orders.created', ...);│
│  │  COMMIT;                                                                    │  │
│  │                                                                             │  │
│  │  Then: CDC (Debezium) reads outbox table → publishes to Kafka               │  │
│  │  Result: DB + Kafka always consistent (same transaction)                    │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  2. SAGA PATTERN (Distributed Transactions)                                       │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Order Fulfillment Saga:                                                    │  │
│  │                                                                             │  │
│  │  [Order Created] → [Payment Captured] → [Inventory Reserved] → [Shipped]   │  │
│  │       ↓ fail           ↓ fail                ↓ fail                         │  │
│  │  [Mark Failed]    [Refund Payment]    [Release Inventory]                   │  │
│  │                   [Notify Customer]   [Refund Payment]                      │  │
│  │                                       [Notify Customer]                     │  │
│  │                                                                             │  │
│  │  Each step: Publish event → Next service reacts → Publish result            │  │
│  │  Compensation: On failure, publish compensating events in reverse            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  3. DEAD LETTER QUEUE (Error Handling)                                            │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Normal: Event → Consumer → Process → ACK                                   │  │
│  │  Error:  Event → Consumer → FAIL → Retry (3x) → DLQ                        │  │
│  │                                                                             │  │
│  │  DLQ Processing:                                                            │  │
│  │  • Dashboard shows failed events (count, types, patterns)                   │  │
│  │  • On-call investigates root cause                                          │  │
│  │  • Fix deployed → Replay DLQ → Events reprocessed                           │  │
│  │  • If unfixable → Manual resolution + record in audit log                   │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  4. ANALYTICS CONSUMER (Unified View)                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Consumes ALL domain events → Builds unified data model                     │  │
│  │                                                                             │  │
│  │  [All Events] → Flink → Bronze (raw events, Iceberg)                        │  │
│  │                       → Silver (joined, enriched)                            │  │
│  │                       → Gold (business metrics, star schema)                 │  │
│  │                       → Pinot (real-time dashboards)                         │  │
│  │                                                                             │  │
│  │  WHY SEPARATE ANALYTICS CONSUMER:                                           │  │
│  │  • Services own their data → analytics needs cross-domain view              │  │
│  │  • No coupling between services (analytics is just another consumer)        │  │
│  │  • Can rebuild entire analytics layer by replaying events                   │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

```
Q: Why Kafka and not RabbitMQ/SQS?
A: • Replay capability (new services can catch up from history)
   • Ordering guarantees (per partition key = per entity)
   • Multi-consumer (analytics + saga + notifications = same events)
   • Throughput (millions/sec vs thousands for RabbitMQ)
   • Retention (events ARE the source of truth, not just transport)

Q: Why Outbox pattern and not dual-write?
A: • Dual-write: Write to DB AND Kafka separately
   • Problem: What if Kafka publish fails after DB commit?
   • Outbox: Single DB transaction, CDC publishes reliably
   • Guarantee: DB state and events are ALWAYS consistent

Q: Why eventually consistent and not distributed transactions (2PC)?
A: • 2PC: All services must be available simultaneously (fragile)
   • 2PC: Holds locks across services (performance killer)
   • Eventual: Each service processes independently (resilient)
   • Eventual: Higher availability (CAP theorem: we choose AP over CP)
   • Trade-off: Business must tolerate seconds of inconsistency

Q: Why separate DBs per service and not shared database?
A: • Independence: Each service deploys/scales independently
   • Technology choice: Orders=Postgres, Inventory=Redis, etc.
   • Failure isolation: One DB down doesn't affect others
   • Team autonomy: Team owns their schema, no cross-team coordination
```

