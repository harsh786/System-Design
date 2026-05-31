# Problem 30: Exactly-Once Processing Across Systems

## Problem 30: Exactly-Once Processing Across Systems

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│         EXACTLY-ONCE END-TO-END ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  THE CHALLENGE:                                                              │
│  Kafka (exactly-once) → Flink (exactly-once) → Database (???)               │
│  Even if each component is exactly-once internally,                          │
│  the END-TO-END might not be without careful design.                         │
│                                                                              │
│  SOLUTION: Transactional Outbox + Idempotent Consumers                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  PRODUCER (Transactional Outbox Pattern)                        │         │
│  │                                                                 │         │
│  │  BEGIN TRANSACTION;                                             │         │
│  │    INSERT INTO orders (...);                                    │         │
│  │    INSERT INTO outbox (event_id, payload, status='pending');    │         │
│  │  COMMIT;                                                        │         │
│  │                                                                 │         │
│  │  Separate process: Poll outbox → Publish to Kafka → Mark sent  │         │
│  │  Result: DB + Kafka always consistent                           │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  KAFKA (Exactly-Once via Transactions)                          │         │
│  │                                                                 │         │
│  │  enable.idempotence=true (dedup at broker)                      │         │
│  │  transactional.id=unique-producer-id                            │         │
│  │  isolation.level=read_committed (consumers see only committed)  │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  FLINK (Exactly-Once via Checkpointing)                         │         │
│  │                                                                 │         │
│  │  Checkpoint Barrier:                                            │         │
│  │  ┌───────────────────────────────────────┐                     │         │
│  │  │  Source → [Barrier] → Process → Sink  │                     │         │
│  │  │                                       │                      │         │
│  │  │  On checkpoint:                       │                      │         │
│  │  │  1. Kafka consumer commits offset     │                      │         │
│  │  │  2. Flink saves operator state        │                      │         │
│  │  │  3. Sink pre-commits (2PC)            │                      │         │
│  │  │                                       │                      │         │
│  │  │  On recovery:                         │                      │         │
│  │  │  1. Restore from last checkpoint      │                      │         │
│  │  │  2. Re-read from committed offset     │                      │         │
│  │  │  3. Sink aborts uncommitted           │                      │         │
│  │  └───────────────────────────────────────┘                     │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  SINK (Idempotent Consumer Pattern)                             │         │
│  │                                                                 │         │
│  │  Option A: Idempotent writes                                    │         │
│  │    INSERT ... ON CONFLICT (event_id) DO NOTHING;                │         │
│  │    (Dedup by unique event_id)                                   │         │
│  │                                                                 │         │
│  │  Option B: Transactional sink (2PC with Flink)                  │         │
│  │    Flink pre-commits → Checkpoint → Flink commits               │         │
│  │    (Only works with 2PC-capable sinks: Kafka, some DBs)         │         │
│  │                                                                 │         │
│  │  Option C: Upsert by natural key                                │         │
│  │    MERGE INTO target USING source ON key = key                  │         │
│  │    (Naturally idempotent: same data → same result)              │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Problems 31-50: Architecture Summaries

### Problem 31: Data Catalog & Discovery Platform
```
ARCH: Crawlers → Metadata Store (Amundsen/DataHub) → Graph DB → Search UI
WHY GRAPH: Data relationships are naturally a graph (lineage, ownership, joins)
SCALE: 50K datasets, 5K users, real-time metadata updates via Kafka
```

### Problem 32: Reverse ETL (Warehouse → Operational Systems)
```
ARCH: Warehouse → Census/Hightouch → CRM, Marketing, Support tools
WHY: Analytics team defines segments in SQL, ops teams need them in tools
SYNC: Incremental (only changed rows), idempotent, rate-limited
```

### Problem 33: Real-Time Anomaly Detection on Metrics
```
ARCH: Metrics → Kafka → Flink (statistical models) → Alert Manager
ALGORITHMS: Z-score, IQR, STL decomposition, Prophet-based
WHY STREAMING: Detect anomalies within 1 minute of occurrence
```

### Problem 34: Data Versioning & Reproducibility (ML)
```
ARCH: DVC + Delta Lake time-travel + MLflow experiment tracking
WHY: Reproduce any model training run with exact data snapshot
CHALLENGE: Petabyte datasets can't be git-versioned
SOLUTION: Version metadata (Delta log), not data files
```

### Problem 35: Cross-Database Federated Queries
```
ARCH: Trino/Presto federation across: MySQL + S3 + Elasticsearch + Redis
WHY TRINO: Single SQL interface to heterogeneous sources
OPTIMIZATION: Pushdown predicates to source, minimize data movement
```

### Problem 36: Streaming CDC to Data Warehouse (Snowflake/BQ)
```
ARCH: Debezium → Kafka → Kafka Connect → Snowflake/BQ
CHALLENGE: Merge (upsert) in warehouse (not just append)
SOLUTION: Snowpipe Streaming + MERGE tasks, or Flink → staging → MERGE
```

### Problem 37: Time-Series Forecasting Pipeline
```
ARCH: Historical → Feature Engineering (Spark) → Model Training → Serving
MODELS: Prophet, DeepAR, N-BEATS, Temporal Fusion Transformer
SCALE: 1M time series (one per SKU), retrain weekly
SERVING: Pre-compute forecasts, store in Redis for instant lookup
```

### Problem 38: Data Contracts Between Teams
```
ARCH: Schema Registry + Contract tests + CI/CD validation
FORMAT: Protobuf/Avro with compatibility rules (backward/forward)
ENFORCEMENT: Producer can't deploy incompatible schema changes
NOTIFICATION: Consumers alerted of upcoming breaking changes
```

### Problem 39: Backfill & Reprocessing Framework
```
ARCH: Idempotent jobs + partition-level reprocessing + validation
PATTERN: Write to staging → validate → atomic swap to production
WHY IDEMPOTENT: Reprocessing same data must give same result
SCALE: Backfill 1 year of data = replay 365 daily partitions
```

### Problem 40: Real-Time User Session Analysis
```
ARCH: Click events → Kafka → Flink (session windows) → Analytics
SESSION WINDOW: Gap-based (30 min inactivity = new session)
METRICS: Duration, pages viewed, conversion, bounce rate
REAL-TIME: Show "active users now" dashboard updated every 5 seconds
```

### Problem 41: Data Pipeline Orchestration (Beyond Airflow)
```
MODERN: Dagster (asset-based) vs Prefect (dynamic) vs Airflow (DAG)
WHY DAGSTER: Software-defined assets, better testing, observability
WHY STILL AIRFLOW: Mature, huge community, battle-tested at scale
HYBRID: Airflow orchestrates, Spark/Flink executes
```

### Problem 42: Schema Registry & Evolution Management
```
ARCH: Confluent Schema Registry + compatibility modes
MODES: BACKWARD (new reader, old data) / FORWARD (old reader, new data)
ENFORCEMENT: Kafka rejects messages failing schema validation
MIGRATION: Dual-write during schema transition period
```

### Problem 43: Data Lakehouse Performance Tuning
```
TECHNIQUES:
  • Z-ORDER clustering (multi-column co-location)
  • File compaction (merge small files → target 256MB)
  • Bloom filter indexes (point lookups)
  • Data skipping (column statistics in manifest)
  • Partition pruning (date-based partitioning)
RESULT: 10-100x query speedup for analytical workloads
```

### Problem 44: Streaming Deduplication at Scale
```
ARCH: Kafka → Flink (dedup by event_id) → Clean stream
CHALLENGE: State grows unbounded (remember all seen IDs)
SOLUTIONS:
  • Bloom filter (probabilistic, false positives ok for some cases)
  • Time-bounded dedup (only dedup within 1-hour window)
  • RocksDB state with TTL (auto-expire old IDs)
```

### Problem 45: Multi-Cloud Data Platform
```
ARCH: Abstract storage (Iceberg) + compute (Spark/Flink) across AWS + GCP
WHY ICEBERG: Same table readable from AWS EMR and GCP Dataproc
REPLICATION: Cross-cloud via Kafka MirrorMaker or storage-level sync
CHALLENGE: Egress costs, latency, consistency
```

### Problem 46: PII Detection & Tokenization Pipeline
```
ARCH: Data → NER model (detect PII) → Tokenize/Hash → Store
DETECTION: Names, emails, SSN, phone, address (NLP + regex)
TOKENIZATION: Format-preserving encryption (FPE) for testing
GDPR: Right to erasure = delete token mapping = data "forgotten"
```

### Problem 47: Cost Optimization for Data Platform
```
STRATEGIES:
  • Storage tiering (hot → warm → cold → archive)
  • Compute right-sizing (auto-scale, spot instances)
  • Query optimization (materialized views, caching)
  • Data lifecycle (TTL, auto-archive)
METRICS: $/GB stored, $/query, $/pipeline run
TARGET: 40-60% reduction from naive approach
```

### Problem 48: Streaming Graph Analytics
```
ARCH: Events → Kafka → Flink → Graph DB (Neo4j/Neptune)
USE CASE: Fraud rings, social network analysis, knowledge graphs
WHY STREAMING: Detect emerging patterns in real-time
CHALLENGE: Graph updates are expensive (rebalancing, index updates)
```

### Problem 49: Data Warehouse Automation (Auto-Modeling)
```
ARCH: Source metadata → Auto-generate star schema → dbt models → Tests
TOOLS: dbt + custom generators + Great Expectations
APPROACH: Convention over configuration (naming = relationships)
OUTPUT: 80% automated, 20% manual for complex business logic
```

### Problem 50: Disaster Recovery for Data Pipelines
```
ARCH: Multi-AZ primary + cross-region standby + S3 cross-region replication
RPO: <1 hour (data loss tolerance)
RTO: <4 hours (recovery time)
STRATEGY: Active-passive with automated failover
TESTING: Monthly DR drills (actually fail over and back)
```
