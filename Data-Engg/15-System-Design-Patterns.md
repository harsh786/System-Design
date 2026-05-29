# System Design Patterns for Data Engineering - Staff Architect Reference

---

## 1. Change Data Capture (CDC) Patterns

```
PATTERN A: Log-Based CDC (Recommended)
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Database │───▶│ Debezium │───▶│  Kafka   │───▶│  Sink    │
│ (WAL/    │    │ (capture)│    │ (buffer) │    │ (Lake/DW)│
│  binlog) │    │          │    │          │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
Pro: No impact on source, captures all changes, low latency
Con: Database-specific (PG WAL, MySQL binlog, SQL Server CT)

PATTERN B: Query-Based CDC (Polling)
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Database │◀───│  Poller  │───▶│  Target  │
│          │    │ (SELECT  │    │          │
│          │    │  WHERE   │    │          │
│          │    │  updated>│    │          │
│          │    │  last_ts)│    │          │
└──────────┘    └──────────┘    └──────────┘
Pro: Simple, works with any DB, no special permissions
Con: Misses deletes, adds load to source, higher latency, needs timestamp column

PATTERN C: Trigger-Based CDC
Pro: Captures all DML, customizable
Con: Performance impact on source, maintenance burden, tight coupling

PATTERN D: Outbox Pattern (Application-Level CDC)
┌──────────────────────────────────────────────┐
│ Application:                                  │
│   BEGIN TRANSACTION                           │
│     INSERT INTO orders (...);                 │
│     INSERT INTO outbox (topic, key, payload); │
│   COMMIT                                      │
│                                               │
│ Debezium watches outbox table → publishes to  │
│ Kafka → deletes from outbox after confirm     │
└──────────────────────────────────────────────┘
Pro: Guarantees consistency between DB state and published events
Con: Extra table, needs CDC on outbox table

Best practice: Log-based CDC (Debezium) for databases that support it,
Query-based only when log access is unavailable.
```

---

## 2. Medallion Architecture (Bronze/Silver/Gold)

```
┌──────────────────────────────────────────────────────────────────┐
│                    MEDALLION ARCHITECTURE                          │
│                                                                    │
│  BRONZE (Raw):                                                    │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ Purpose: Exact copy of source data (source of truth)    │      │
│  │ Format: Source format preserved (JSON, Avro, CSV)       │      │
│  │ Schema: Inferred or loose (schema-on-read)              │      │
│  │ Quality: No validation (accept everything)              │      │
│  │ Retention: Long (years), immutable append-only          │      │
│  │ Pattern: Append with ingestion timestamp                │      │
│  │ Example: raw.orders_cdc, raw.clickstream_events         │      │
│  └────────────────────────────────────────────────────────┘      │
│                              │ validate, clean, dedup              │
│                              ▼                                    │
│  SILVER (Cleaned):                                               │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ Purpose: Validated, deduplicated, typed data            │      │
│  │ Format: Parquet/Iceberg (optimized columnar)            │      │
│  │ Schema: Enforced (typed columns, constraints)           │      │
│  │ Quality: Validated (nulls, types, ranges, referential)  │      │
│  │ Retention: Medium (months to years)                     │      │
│  │ Pattern: MERGE/upsert from bronze, SCD Type 2           │      │
│  │ Example: cleaned.orders, cleaned.customers              │      │
│  └────────────────────────────────────────────────────────┘      │
│                              │ aggregate, join, model              │
│                              ▼                                    │
│  GOLD (Business):                                                │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ Purpose: Business-level aggregates, ready for consumption│      │
│  │ Format: Optimized for query (star schema, wide tables)   │      │
│  │ Schema: Dimensional model or OBT                         │      │
│  │ Quality: Business rules validated                        │      │
│  │ Retention: Per business requirement                      │      │
│  │ Pattern: Aggregate, join dimensions, compute metrics     │      │
│  │ Example: analytics.fct_orders, analytics.daily_revenue   │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                    │
│  WHO QUERIES EACH LAYER:                                         │
│  Bronze: Data engineers (debugging, replay)                      │
│  Silver: Data scientists, analytics engineers                    │
│  Gold: Business analysts, dashboards, executives                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Event-Driven Architecture Patterns

```
PATTERN A: Event Notification
  Producer publishes lightweight event: {type: "order_created", order_id: "123"}
  Consumer fetches full data from source if needed
  Pro: Small events, loose coupling
  Con: Consumer must call back to source (availability dependency)

PATTERN B: Event-Carried State Transfer
  Producer publishes FULL entity state: {type: "order_created", order: {id, items, total,...}}
  Consumer has all needed data in the event
  Pro: No callbacks needed, consumer fully decoupled
  Con: Larger events, potential data staleness

PATTERN C: Event Sourcing
  Store ALL events, derive current state by replay
  Events are immutable facts (never delete/update)
  Pro: Full audit trail, can rebuild any state, temporal queries
  Con: Complexity, replay performance, schema evolution across history

PATTERN D: CQRS (Command Query Responsibility Segregation)
  ┌──────────┐         ┌──────────┐         ┌──────────┐
  │ Commands │────────▶│  Event   │────────▶│  Read    │
  │ (writes) │         │  Store   │         │  Model   │
  │          │         │ (Kafka)  │         │ (DB/Cache)│
  └──────────┘         └──────────┘         └──────────┘
       │                                         ▲
       │                                         │
  Write model optimized    Projections build     Queries go here
  for consistency          read-optimized views  (fast, denormalized)
  
  Pro: Write and read sides optimized independently
  Con: Eventual consistency between write and read, complexity
```

---

## 4. Idempotency Patterns

```
WHY: Pipelines WILL be retried. Idempotency ensures retries are safe.

PATTERN A: Overwrite Partition
  Write mode: OVERWRITE for target partition
  Same input → same output (overwrite = idempotent)
  df.write.mode("overwrite").partitionBy("date").save(path)

PATTERN B: Upsert (MERGE)
  MERGE INTO target USING source ON key_match
  WHEN MATCHED THEN UPDATE
  WHEN NOT MATCHED THEN INSERT
  Replay same data → same result (no duplicates)

PATTERN C: Delete-Insert
  DELETE FROM target WHERE date = '2024-01-15';
  INSERT INTO target SELECT * FROM staging WHERE date = '2024-01-15';
  Must be in same transaction!

PATTERN D: Deterministic File Names
  Output: s3://output/{date}/{batch_id}.parquet
  Re-execution with same batch_id → overwrites same file
  Not: s3://output/{uuid}.parquet (creates new file each time!)

PATTERN E: Deduplication on Write
  Assign unique event_id at source
  Target table: UNIQUE constraint or dedup logic on event_id
  INSERT ... ON CONFLICT (event_id) DO NOTHING;

ANTI-PATTERNS (NOT idempotent):
  ✗ INSERT without dedup key (appends duplicates on retry)
  ✗ UUID-based filenames (new file per run)
  ✗ Append mode without event_id dedup
  ✗ Auto-increment IDs for correlation (different IDs on retry)
```

---

## 5. Schema Evolution Patterns

```
PATTERN A: Schema Registry (Kafka/Avro)
  - Central registry of schemas per topic
  - Compatibility checks before publish (BACKWARD, FORWARD, FULL)
  - Producers register schema, get ID
  - Consumers deserialize with correct schema version

PATTERN B: Schema-on-Read (Data Lake)
  - Store raw data as-is (no schema enforcement on write)
  - Apply schema at query time
  - Pro: Never reject data (accept everything)
  - Con: Quality issues discovered late, harder to optimize

PATTERN C: Schema-on-Write (Data Warehouse)
  - Enforce schema at write time (reject non-conforming data)
  - Pro: Data always clean, optimized storage
  - Con: Must handle schema changes explicitly (ALTER TABLE)

PATTERN D: Dual Schema (Bridge)
  - Write raw (schema-on-read) to Bronze
  - Enforce schema (schema-on-write) at Silver promotion
  - Best of both: Never lose data + quality guarantee

PATTERN E: Table Format Evolution (Iceberg/Delta)
  - ADD COLUMN: Always safe (new column, old data has NULL)
  - DROP COLUMN: Mark as deleted in metadata (data remains in files)
  - RENAME: Update metadata only (column ID-based, not name-based in Iceberg)
  - TYPE PROMOTION: int → long, float → double (widen only)
  - REORDER: Update column ordering in metadata

BREAKING CHANGES HANDLING:
  - Option 1: New topic/table version (orders_v2)
  - Option 2: Dual-write during transition period
  - Option 3: Adapter layer (transform old schema to new at read)
```

---

## 6. Backpressure & Flow Control Patterns

```
PATTERN A: Pull-Based (Kafka consumers)
  Consumer pulls at its own pace
  Backpressure = consumer lag (growing lag indicates slow consumer)
  No data loss, no explicit flow control needed
  Monitoring: Consumer lag metrics

PATTERN B: Credit-Based (Flink)
  Downstream announces available buffer credits to upstream
  Upstream can only send if credits available
  Automatic propagation through operator chain
  No data loss, no buffering overflow

PATTERN C: Rate Limiting (API sources)
  Token bucket or leaky bucket at source reader
  Prevents overwhelming source system
  Pattern: RATE_LIMIT → BUFFER → PROCESS

PATTERN D: Spillable Buffer (Spark)
  In-memory buffer → spill to disk when full
  Processing continues (slower with disk I/O)
  Configurable memory fraction before spill

PATTERN E: Pause/Resume (Kafka consumer)
  consumer.pause(partitions)   // Stop fetching
  consumer.resume(partitions)  // Resume when ready
  Application-level flow control
  Use: When downstream buffer is full

PATTERN F: Circuit Breaker (External dependencies)
  CLOSED → normal operation
  OPEN → fail fast (don't call broken dependency)
  HALF-OPEN → try one request, if success → CLOSED
  
  Prevents: Retry storms, cascading failures
  Implementation: Resilience4j, Hystrix-like pattern
```

---

## 7. Data Pipeline Testing Patterns

```
TESTING PYRAMID FOR DATA PIPELINES:

        /\
       /  \   E2E Integration Tests
      / 10 \  (Full pipeline, real data subset)
     /______\
    /        \  Component Tests
   /   30%    \  (Single pipeline stage, mocked I/O)
  /____________\
 /              \  Unit Tests
/     60%        \  (Transform functions, business logic)
/________________\

UNIT TESTS:
  def test_calculate_revenue():
      input = [{"amount": 100, "tax": 10, "discount": 5}]
      result = calculate_revenue(input)
      assert result == [{"revenue": 105}]  # amount + tax - discount

COMPONENT TESTS:
  def test_silver_pipeline(spark_session):
      # Create test input DataFrame
      input_df = spark.createDataFrame([...])
      # Run pipeline stage
      output_df = silver_transform(input_df)
      # Assert output
      assert output_df.count() == expected_count
      assert output_df.filter(col("order_id").isNull()).count() == 0

INTEGRATION TESTS:
  @pytest.fixture
  def test_environment():
      kafka = KafkaContainer()
      postgres = PostgresContainer()
      yield {"kafka": kafka, "postgres": postgres}
      kafka.stop(); postgres.stop()
  
  def test_end_to_end(test_environment):
      produce_test_events(test_environment["kafka"])
      trigger_pipeline()
      results = query_target(test_environment["postgres"])
      assert_expected_results(results)

DATA QUALITY TESTS (dbt):
  - unique: Primary key uniqueness
  - not_null: Required fields present
  - accepted_values: Enum validation
  - relationships: Foreign key integrity
  - custom: Business logic assertions
```

---

## 8. Observability Patterns

```
THREE PILLARS OF DATA PIPELINE OBSERVABILITY:

1. METRICS (Quantitative, time-series):
┌──────────────────────────────────────────┐
│ Pipeline metrics:                        │
│ - Processing duration (p50, p95, p99)    │
│ - Records processed per minute           │
│ - Error rate (failed/total)              │
│ - Data freshness (time since last update)│
│ - Consumer lag (Kafka)                   │
│                                          │
│ Infrastructure metrics:                  │
│ - CPU, memory, disk I/O                  │
│ - Network throughput                     │
│ - Container restarts                     │
│                                          │
│ Data quality metrics:                    │
│ - Null rates per column                  │
│ - Row counts per table per day           │
│ - Schema change count                    │
│ - Quality score per table                │
└──────────────────────────────────────────┘

2. LOGS (Discrete events):
┌──────────────────────────────────────────┐
│ Structured logging:                      │
│ {"timestamp": "...",                     │
│  "level": "ERROR",                       │
│  "pipeline": "orders_etl",              │
│  "task": "transform",                    │
│  "message": "Schema mismatch",          │
│  "details": {"expected": "INT",         │
│              "got": "STRING",            │
│              "column": "amount"}}        │
│                                          │
│ Key principles:                          │
│ - Always structured (JSON)               │
│ - Include correlation ID (trace request) │
│ - Include pipeline/task context          │
│ - Appropriate level (don't log PII!)     │
└──────────────────────────────────────────┘

3. TRACES (Distributed request flow):
┌──────────────────────────────────────────┐
│ OpenTelemetry trace across pipeline:     │
│                                          │
│ Span: ingest (5s)                        │
│   └─ Span: kafka_produce (200ms)        │
│ Span: transform (30s)                    │
│   ├─ Span: read_source (5s)             │
│   ├─ Span: apply_rules (20s)            │
│   └─ Span: write_target (5s)            │
│ Span: quality_check (10s)               │
│                                          │
│ Enables: Where is time spent?            │
│ Which stage is the bottleneck?           │
└──────────────────────────────────────────┘

ALERTING STRATEGY:
  Severity 1: Revenue-impacting, customer-facing → PagerDuty
  Severity 2: SLA breach, data freshness → Slack + ticket
  Severity 3: Quality warnings, performance degradation → Dashboard
  Severity 4: Informational → Log only
  
  Rule: Every alert MUST have a runbook attached.
  Rule: If alert doesn't require action → remove it (reduce noise).
```

---

## 9. Data Mesh Implementation Patterns

```
SELF-SERVE DATA PLATFORM:
┌──────────────────────────────────────────────────────────────┐
│ Platform provides:                                            │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ Pipeline Templates    │ "Create new CDC pipeline in  │    │
│ │ (Cookiecutter/Copier) │  5 min with this template"   │    │
│ ├───────────────────────┼──────────────────────────────┤    │
│ │ Data Quality Framework│ "Add these tests to your     │    │
│ │ (GE / dbt macros)     │  model with one line"        │    │
│ ├───────────────────────┼──────────────────────────────┤    │
│ │ Deployment Automation │ "Push to main → deployed     │    │
│ │ (GitOps / CI/CD)      │  to production automatically"│    │
│ ├───────────────────────┼──────────────────────────────┤    │
│ │ Catalog + Discovery   │ "Find any dataset, see       │    │
│ │ (DataHub / OpenMeta)  │  schema, owner, lineage"     │    │
│ ├───────────────────────┼──────────────────────────────┤    │
│ │ Access Management     │ "Request access, auto-granted│    │
│ │ (Self-serve RBAC)     │  based on team + data class" │    │
│ └───────────────────────┴──────────────────────────────┘    │
│                                                               │
│ Domain teams use platform to:                                │
│ - Build their own pipelines (from templates)                 │
│ - Publish data products (register in catalog)                │
│ - Define quality contracts (standard framework)              │
│ - Serve consumers (standard interfaces)                      │
└──────────────────────────────────────────────────────────────┘

DATA PRODUCT SPEC:
  name: orders-daily-aggregates
  owner: commerce-team
  domain: commerce
  tier: tier-1 (business-critical)
  sla:
    freshness: 30 minutes
    availability: 99.9%
  schema: (versioned, documented)
  quality: (tested, scored)
  access: (discoverable, requestable)
  lineage: (tracked, visualized)
```

---

## 10. Exactly-Once Processing Patterns

```
END-TO-END EXACTLY-ONCE:
Requires: Replayable source + Deterministic processing + Idempotent sink

PATTERN A: Transactional (Kafka EOS)
  Producer: beginTransaction → produce → commitTransaction
  Consumer: read_committed isolation
  Scope: Within Kafka ecosystem only

PATTERN B: Checkpoint + Idempotent Sink (Flink)
  Checkpoint captures: Source offsets + Operator state
  On failure: Replay from checkpoint offsets
  Sink must handle replayed data idempotently (upsert, dedup)

PATTERN C: Write-Ahead Log (Generic)
  1. Write intended changes to WAL (durable)
  2. Apply changes to target
  3. If crash after WAL, before apply: Replay WAL on recovery
  4. If crash after apply: WAL already committed, skip on recovery

PATTERN D: Two-Phase Commit (Distributed)
  Phase 1 (Prepare): All participants prepare (pre-commit)
  Phase 2 (Commit): Coordinator says commit → all commit
  If any fails: Coordinator says abort → all rollback
  Used by: Flink Kafka sink, distributed databases

PRACTICAL EXACTLY-ONCE PATTERNS:
┌──────────────────────────────────────────────────────────────┐
│ Source: Kafka (replayable by offset)                         │
│ Processing: Flink (checkpointed state)                       │
│ Sink options:                                                │
│                                                               │
│ A) Kafka sink (2PC):                                         │
│    Flink pre-commits Kafka transaction during checkpoint     │
│    Commits on checkpoint complete                            │
│                                                               │
│ B) Database sink (idempotent):                               │
│    UPSERT by primary key → replay produces same result       │
│    Or: Store offset in same DB transaction as data           │
│                                                               │
│ C) File sink (deterministic naming):                         │
│    File name includes checkpoint ID                          │
│    Re-execution overwrites same file (idempotent)            │
│                                                               │
│ D) Iceberg sink (atomic commits):                            │
│    Flink checkpoint = Iceberg snapshot                        │
│    Uncommitted files cleaned on failure                       │
│    Only committed snapshots visible to readers               │
└──────────────────────────────────────────────────────────────┘
```

---

## 11. Cost Optimization Patterns

```
┌──────────────────────────────────────────────────────────────┐
│            DATA PLATFORM COST OPTIMIZATION                    │
│                                                               │
│  COMPUTE:                                                    │
│  - Spot/Preemptible instances (60-90% savings)               │
│  - Auto-scaling to zero (serverless: EMR Serverless, etc.)   │
│  - Right-sizing (don't over-provision)                       │
│  - Graviton/ARM instances (20% cheaper, same perf)           │
│  - Reserved capacity for baseline load (30-40% savings)      │
│                                                               │
│  STORAGE:                                                    │
│  - Lifecycle policies (Standard → IA → Glacier → Delete)     │
│  - Compression (ZSTD: 40-70% reduction)                      │
│  - Columnar formats (Parquet: only read needed columns)      │
│  - Deduplication (don't store same data multiple times)       │
│  - Retention policies (delete what you don't need)           │
│                                                               │
│  PROCESSING:                                                 │
│  - Incremental processing (don't recompute unchanged)        │
│  - Predicate pushdown (read less data)                       │
│  - Materialized views (precompute expensive aggregations)    │
│  - Partition pruning (skip irrelevant partitions)            │
│  - Approximate algorithms (HLL instead of exact distinct)    │
│                                                               │
│  NETWORK:                                                    │
│  - Same-region data movement (avoid cross-region fees)       │
│  - Compression before transfer                               │
│  - VPC endpoints (avoid NAT gateway charges)                 │
│  - Batch transfers (reduce per-request overhead)             │
│                                                               │
│  GOVERNANCE:                                                 │
│  - Cost attribution (tag everything by team/project)         │
│  - Budget alerts (catch runaway costs early)                 │
│  - Anomaly detection on cost (alert on 2x daily spend)       │
│  - Quarterly optimization reviews                            │
│  - Showback/chargeback to create cost awareness              │
└──────────────────────────────────────────────────────────────┘
```

---

## 12. Disaster Recovery Patterns

```
RPO (Recovery Point Objective): Max acceptable data loss (time)
RTO (Recovery Time Objective): Max acceptable downtime

TIER 1 (RPO=0, RTO<1h): Revenue-critical pipelines
  - Multi-AZ active-active
  - Synchronous replication
  - Automated failover
  - Hot standby

TIER 2 (RPO<1h, RTO<4h): Business-critical analytics
  - Cross-region async replication
  - Automated failover with manual verification
  - Warm standby

TIER 3 (RPO<24h, RTO<24h): Non-critical reports
  - Daily backups to another region
  - Manual recovery from backup
  - Cold standby

DR PATTERNS FOR DATA PLATFORMS:
┌──────────────────────────────────────────────┐
│ Kafka:                                       │
│  - MirrorMaker 2 to DR cluster (async)       │
│  - Stretch cluster for RPO=0 (sync, needs    │
│    low-latency cross-DC link)                │
│                                              │
│ Data Lake (S3/Iceberg):                      │
│  - S3 Cross-Region Replication (async)       │
│  - Iceberg: Metadata + data both replicated  │
│  - RPO depends on replication lag            │
│                                              │
│ Warehouse (Snowflake):                       │
│  - Failover/failback (cross-region)          │
│  - Replication: Database replicated to DR    │
│  - RPO: Minutes (async replication lag)      │
│                                              │
│ Airflow:                                     │
│  - Metadata DB: Multi-AZ RDS (automatic)    │
│  - DAGs: Git (always recoverable)            │
│  - Logs: Remote logging to S3 (durable)      │
│  - RTO: Time to spin up new Airflow instance │
└──────────────────────────────────────────────┘
```

---

## Summary: Pattern Selection Guide

```
┌─────────────────────────────────┬────────────────────────────────┐
│ REQUIREMENT                     │ PATTERN                        │
├─────────────────────────────────┼────────────────────────────────┤
│ Capture DB changes              │ Log-based CDC (Debezium)       │
│ Reliable event publishing       │ Outbox pattern                 │
│ Organize data lake              │ Medallion (Bronze/Silver/Gold) │
│ Decouple services               │ Event-driven (Kafka)           │
│ Safe pipeline retries           │ Idempotency patterns           │
│ Handle schema changes           │ Schema Registry + Evolution    │
│ Real-time + historical          │ Kappa / Lakehouse              │
│ Control data flow               │ Backpressure (pull-based)      │
│ No duplicates end-to-end        │ Exactly-once (checkpoint+idem) │
│ Test pipelines                  │ Testing pyramid (unit→E2E)     │
│ Monitor pipelines               │ 3 pillars (metrics/logs/traces)│
│ Scale organization              │ Data Mesh (self-serve platform)│
│ Reduce costs                    │ Tiering + incremental + spot   │
│ Survive failures                │ DR tiers (RPO/RTO based)       │
│ Multi-team data ownership       │ Data contracts + mesh          │
└─────────────────────────────────┴────────────────────────────────┘
```
