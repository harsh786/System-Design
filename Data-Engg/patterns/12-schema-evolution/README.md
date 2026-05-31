# Pattern 12: Schema Evolution

## The Problem

```
Day 1: Schema v1 → {order_id, amount, status}
Day 30: Need to add "discount" field → Schema v2
Day 60: Need to rename "amount" → "total_amount" → Schema v3

CHALLENGE: You have 60 days of data in v1 format.
           Consumers expect v1 format.
           How do you evolve WITHOUT breaking everything?
```

## Schema Evolution Strategies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCHEMA EVOLUTION RULES (Schema Registry)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  BACKWARD COMPATIBLE (new reader, old data):                                 │
│  ───────────────────────────────────────────                                 │
│  ✓ Add optional field (with default value)                                   │
│  ✓ Remove field (old data has it, new reader ignores it)                     │
│  ✓ Widen type (int → long, float → double)                                  │
│  ✗ Add required field (old data doesn't have it!)                            │
│  ✗ Narrow type (long → int, may overflow)                                    │
│  ✗ Rename field (old data has old name)                                      │
│                                                                              │
│  FORWARD COMPATIBLE (old reader, new data):                                  │
│  ──────────────────────────────────────────                                  │
│  ✓ Add field (old reader ignores unknown fields)                             │
│  ✓ Remove optional field (old reader uses default)                           │
│  ✗ Remove required field (old reader expects it!)                            │
│  ✗ Change type (old reader can't parse new type)                             │
│                                                                              │
│  FULL COMPATIBLE (both directions):                                          │
│  ──────────────────────────────────                                          │
│  ✓ Add optional field with default                                           │
│  ✗ Almost everything else                                                    │
│                                                                              │
│  BEST PRACTICE: Use BACKWARD compatibility                                   │
│  Reason: New code deploys first, then starts reading old + new data          │
│  This is the most common real-world upgrade path                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Schema Registry (Confluent / AWS Glue)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HOW SCHEMA REGISTRY WORKS                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PRODUCER:                                                                   │
│  1. Serialize message with schema                                            │
│  2. Register schema with registry (gets schema_id)                           │
│  3. Prepend schema_id to message bytes                                       │
│  4. Publish to Kafka: [schema_id | serialized_data]                          │
│                                                                              │
│  CONSUMER:                                                                   │
│  1. Read message from Kafka                                                  │
│  2. Extract schema_id from first bytes                                       │
│  3. Fetch schema from registry (cached)                                      │
│  4. Deserialize data using fetched schema                                    │
│  5. Apply reader schema (project, type-promote)                              │
│                                                                              │
│  COMPATIBILITY CHECK:                                                        │
│  • On schema registration, registry checks compatibility                     │
│  • If incompatible → REJECTED (HTTP 409)                                     │
│  • Producer can't deploy breaking schema                                     │
│  • Enforced at infrastructure level (not just convention)                     │
│                                                                              │
│  FORMATS:                                                                    │
│  • Avro: Schema embedded, excellent evolution, compact binary                │
│  • Protobuf: External .proto files, fast parsing, gRPC native                │
│  • JSON Schema: Human-readable, larger size, weaker evolution                │
│                                                                              │
│  RECOMMENDATION: Avro for data pipelines, Protobuf for service-to-service    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Safe Migration Strategy

```
SCENARIO: Rename "amount" to "total_amount"

This is a BREAKING CHANGE in any compatibility mode.
But business needs it. How?

SAFE MIGRATION (3-phase):
═════════════════════════

Phase 1: Add new field (backward compatible)
  Schema: {order_id, amount, total_amount}  // Both fields present
  Writer: Writes to BOTH fields
  Reader: Reads "total_amount" (falls back to "amount" if null)
  Duration: Deploy to all consumers (1-2 weeks)

Phase 2: Stop writing old field
  Schema: {order_id, amount(deprecated), total_amount}
  Writer: Only writes "total_amount"
  Reader: Reads "total_amount" (old data still has "amount")
  Duration: Wait until all old data expires (retention period)

Phase 3: Remove old field (forward compatible if consumers updated)
  Schema: {order_id, total_amount}
  Writer: Only "total_amount"
  Reader: Only "total_amount"
  Duration: Permanent

TOTAL MIGRATION TIME: retention_period + 2 deploy cycles
For 7-day retention: ~3 weeks total
```

