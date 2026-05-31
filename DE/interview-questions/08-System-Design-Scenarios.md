# Interview Questions Set 8: System Design Scenarios (Q211-240)

---

## Q211: Design a real-time analytics platform that handles 1M events/second with sub-second query latency.

**Answer:**

```
REQUIREMENTS:
- 1M events/sec ingestion
- Sub-second query latency (p99 < 500ms)
- Support: Time-series aggregations, top-N, filtering
- Retention: Hot (7 days real-time), Warm (90 days), Cold (2 years)
- Concurrency: 1000 concurrent dashboard queries

ARCHITECTURE:
┌─────────┐    ┌─────────┐    ┌─────────────────┐    ┌──────────┐
│ Event   │───▶│ Kafka   │───▶│ Flink           │───▶│ Druid /  │
│ Sources │    │ (buffer)│    │ (pre-aggregate) │    │ Pinot    │
│ (1M/s)  │    │         │    │                 │    │ (OLAP)   │
└─────────┘    └─────────┘    └────────┬────────┘    └────┬─────┘
                                       │                    │
                                       │                    ▼
                                       │              ┌──────────┐
                                       └─────────────▶│ Iceberg  │
                                       (raw events)   │ (cold)   │
                                                      └──────────┘

DETAILED DESIGN:

1. INGESTION (Kafka):
   - 50 partitions × 20 MB/s = 1 GB/s raw throughput
   - 10 brokers, 3x replication
   - Tiered storage for 7-day retention
   - Schema Registry (Avro) for schema enforcement

2. STREAM PROCESSING (Flink):
   - Pre-aggregate 1-second tumbling windows:
     {dimension_keys, metric_sum, metric_count, metric_min, metric_max}
   - 1M events/s → ~50K pre-aggregated records/s (20x reduction)
   - Deduplication (exactly-once via checkpoints)
   - Route raw events to Iceberg (append-only, cold storage)

3. SERVING (Apache Druid / Pinot):
   - Ingest pre-aggregated from Kafka (real-time)
   - Segments: 1-hour granularity, auto-published
   - Historical nodes: Serve older segments from deep storage (S3)
   - Broker nodes: Scatter-gather queries, merge results
   - Cluster: 20 historical nodes, 5 real-time, 3 brokers

4. QUERY LAYER:
   - API service with query cache (Redis, 5s TTL)
   - Dashboard queries hit Druid/Pinot directly
   - Ad-hoc queries on cold data → Trino on Iceberg

CAPACITY:
  Kafka: 10 brokers × r5.2xlarge
  Flink: 20 TaskManagers × c5.4xlarge (parallelism=200)
  Druid: 20 historical (r5.4xlarge), 5 middle managers
  Storage: ~3TB/day compressed in Druid, ~10TB/day raw in Iceberg
  
COST: ~$50K/month (AWS)
```

---

## Q212: Design a CDC pipeline that captures changes from 200 PostgreSQL tables and makes them queryable in a data lake within 5 minutes.

**Answer:**

```
ARCHITECTURE:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│PostgreSQL│───▶│ Debezium │───▶│  Kafka   │───▶│  Flink   │───▶ Iceberg
│ (source) │    │ (CDC)    │    │ (buffer) │    │ (upsert) │    (lake)
│ 200 tbls │    │          │    │ 200 topic│    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘

DETAILED DESIGN:

1. SOURCE (PostgreSQL):
   - Logical replication (pgoutput plugin)
   - Replication slot per Debezium connector
   - Publication for all 200 tables
   - WAL retention: 12 hours (safety buffer)

2. CAPTURE (Debezium on Kafka Connect):
   - 4 Kafka Connect workers (distributed mode)
   - 1 connector for all 200 tables (single replication slot)
   - Initial snapshot: parallel, consistent
   - Heartbeat: every 30s (prevent WAL bloat on idle tables)
   - Config:
     {
       "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
       "slot.name": "debezium_cdc",
       "publication.name": "cdc_publication",
       "table.include.list": "public.*",
       "snapshot.mode": "initial",
       "tombstones.on.delete": true,
       "transforms": "route",
       "transforms.route.type": "io.debezium.transforms.ByLogicalTableRouter"
     }

3. BUFFER (Kafka):
   - 200 topics (one per table): cdc.public.{table_name}
   - Retention: 72 hours (replay buffer)
   - Compacted topics (keep latest per key for re-bootstrapping)
   - Schema Registry for CDC event schemas

4. PROCESSING (Flink):
   - Per-table Flink SQL jobs (or multi-table with UNION):
     INSERT INTO iceberg.db.orders
     SELECT * FROM kafka_cdc_orders;
   - Upsert mode (primary key based MERGE)
   - Checkpoint interval: 60s (= max data latency)
   - 50 TaskManagers handling all 200 tables

5. SERVING (Iceberg on S3):
   - Each table as Iceberg table (MoR mode for frequent updates)
   - Compaction job: Every 4 hours (merge delete files)
   - Partition: date column where applicable
   - Query engines: Trino (interactive), Spark (batch analytics)

LATENCY BREAKDOWN:
  WAL → Debezium: ~1s
  Debezium → Kafka: ~1s  
  Kafka → Flink: ~1s
  Flink processing + checkpoint: ~60s
  Total: ~65s (well within 5-minute SLA)

MONITORING:
  - Replication slot lag (bytes)
  - Kafka consumer lag per topic
  - Flink checkpoint duration
  - Iceberg snapshot freshness per table
  - Alert: Any table > 5 min stale
```

---

## Q213: Design a feature store for a real-time ML platform serving 100K predictions/second.

**Answer:**

```
┌──────────────────────────────────────────────────────────────────┐
│                    FEATURE STORE ARCHITECTURE                      │
│                                                                    │
│  OFFLINE STORE (batch features for training):                     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Spark/dbt → compute features → Iceberg/Delta Lake         │    │
│  │                                                           │    │
│  │ Features: user_lifetime_value, avg_order_30d,             │    │
│  │           category_affinity_scores, churn_risk_score      │    │
│  │                                                           │    │
│  │ Point-in-time correct retrieval:                          │    │
│  │   Get features AS OF training timestamp (no data leakage) │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ONLINE STORE (real-time serving for inference):                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Redis Cluster (primary) / DynamoDB (fallback)             │    │
│  │                                                           │    │
│  │ Key: entity_type:entity_id → latest feature vector        │    │
│  │ Example: user:123 → {ltv: 5000, avg_order: 85.5, ...}    │    │
│  │                                                           │    │
│  │ Latency: p99 < 5ms (Redis), p99 < 10ms (DynamoDB)        │    │
│  │ Throughput: 100K reads/sec                                │    │
│  │                                                           │    │
│  │ Materialization: Offline → Online (batch sync every 1h)    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  STREAMING FEATURES (real-time computation):                     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Kafka → Flink → Redis (direct write to online store)      │    │
│  │                                                           │    │
│  │ Features computed in real-time:                            │    │
│  │ - Session click count (last 5 min)                        │    │
│  │ - Cart value (current session)                            │    │
│  │ - Pages viewed (current session)                          │    │
│  │ - Last purchase time (event-driven update)                │    │
│  │                                                           │    │
│  │ Flink stateful computation → push to Redis                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  SERVING API:                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ GET /features?entity=user&id=123&features=ltv,churn_risk  │    │
│  │                                                           │    │
│  │ Response: {"user:123": {"ltv": 5000, "churn_risk": 0.2}}  │    │
│  │                                                           │    │
│  │ Batch endpoint:                                           │    │
│  │ POST /features/batch (up to 1000 entities per request)    │    │
│  │                                                           │    │
│  │ Multi-source merge: batch features (Redis) + streaming    │    │
│  │ features (Redis) merged at serving time                   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  Tools: Feast, Tecton, Hopsworks, Custom (Redis + Flink + Spark)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Q214: Design a data platform for GDPR compliance (right to deletion, data portability, consent management).

**Answer:**

```
REQUIREMENTS:
- Right to erasure (Article 17): Delete user's data within 30 days
- Data portability (Article 20): Export user's data in machine-readable format
- Consent management: Track and enforce consent per purpose
- Data minimization: Only collect what's needed
- Breach notification: Detect and report within 72 hours

ARCHITECTURE:
┌──────────────────────────────────────────────────────────────────┐
│                    GDPR-COMPLIANT DATA PLATFORM                    │
│                                                                    │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ CONSENT SERVICE                                        │      │
│  │ - Stores user consent per purpose (marketing, analytics)│      │
│  │ - API: check_consent(user_id, purpose) → bool           │      │
│  │ - Event: consent_changed → propagate to all systems     │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                    │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ PII REGISTRY (Data Catalog)                            │      │
│  │ - Catalog of ALL tables containing PII                  │      │
│  │ - Column-level PII classification                       │      │
│  │ - Lineage: Where does PII flow?                         │      │
│  │ - Retention policies per table                          │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                    │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ DELETION SERVICE                                       │      │
│  │                                                        │      │
│  │ Request received (user_id=123)                         │      │
│  │   1. Query PII Registry: Which tables have user 123?   │      │
│  │   2. For each table:                                   │      │
│  │      - Iceberg: DELETE FROM table WHERE user_id = 123  │      │
│  │      - Kafka: Produce tombstone (key=user_123, val=null)│      │
│  │      - Redis: DEL user:123                             │      │
│  │      - Search: Delete document from Elasticsearch      │      │
│  │   3. Verify deletion across all systems                │      │
│  │   4. Log completion for compliance audit               │      │
│  │   5. Respond to user within 30 days                    │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                    │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ DATA EXPORT SERVICE (Portability)                      │      │
│  │                                                        │      │
│  │ Request: Export all data for user_id=123               │      │
│  │   1. Query all tables in PII Registry for user 123     │      │
│  │   2. Extract user's records from each table            │      │
│  │   3. Package as JSON/CSV in standard format            │      │
│  │   4. Encrypt and deliver to user                       │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                    │
│  PSEUDONYMIZATION STRATEGY:                                      │
│  - Raw PII stored in ONE place (identity service)                │
│  - Analytics systems use pseudonymized IDs                       │
│  - Mapping: real_user_id → pseudo_id (encrypted mapping table)   │
│  - Deletion: Delete mapping → pseudo_id becomes meaningless      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Q215: Design a cost-efficient data pipeline that processes 100TB daily for an e-commerce company.

**Answer:**

```
COST DRIVERS:
- Compute: Processing 100TB/day
- Storage: Raw + processed data
- Network: Cross-region/service data transfer
- Tooling: Orchestration, monitoring, catalog

ARCHITECTURE (Cost-Optimized):
┌──────────────────────────────────────────────────────────────────┐
│  INGESTION (Continuous):                                          │
│  Sources → Kafka (MSK Serverless) → S3 (raw, Parquet+ZSTD)      │
│  Cost: MSK Serverless $0.10/GB in + $0.05/GB out ≈ $15K/month   │
│                                                                    │
│  PROCESSING (Batch, 4x daily):                                   │
│  Spark on EMR Serverless (auto-scale, scale-to-zero)             │
│  - Graviton instances (20% cheaper)                               │
│  - Spot instances for workers (70% savings)                       │
│  - Process 25TB per run × 4 runs/day                             │
│  Cost: ~$8K/month (spot Graviton)                                │
│                                                                    │
│  STORAGE:                                                         │
│  - Raw (Bronze): S3 Standard (30 days) → S3 IA (90 days) → Glacier│
│  - Processed (Silver/Gold): S3 Standard with lifecycle            │
│  - Format: Iceberg + Parquet + ZSTD (70% compression)            │
│  - 100TB/day × 30 days × 0.3 (compressed) = 900TB active         │
│  Cost: 900TB × $0.023/GB ≈ $21K/month (Standard)                │
│         + cold storage ≈ $5K/month                                │
│                                                                    │
│  WAREHOUSE (Analytics):                                          │
│  - Snowflake or BigQuery for Gold layer queries                  │
│  - Only load aggregated Gold data (~5TB)                         │
│  - Trino on Iceberg for ad-hoc on raw (no warehouse cost)        │
│  Cost: ~$10K/month (Snowflake credits)                           │
│                                                                    │
│  TOTAL: ~$60K/month for 100TB/day                                │
│                                                                    │
│  OPTIMIZATION LEVERS:                                            │
│  1. ZSTD compression: 70% reduction → less storage + less I/O    │
│  2. Spot/Preemptible: 70% compute savings                        │
│  3. Scale-to-zero: No idle resources                             │
│  4. Lifecycle policies: Auto-tier cold data                      │
│  5. Columnar + partition pruning: 10x less data scanned          │
│  6. Incremental processing: Don't reprocess unchanged data       │
│  7. Iceberg compaction: Fewer files = fewer API calls ($$$)      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Q216: Design a data quality monitoring system that detects issues within 15 minutes.

**Answer:**
- Lightweight monitors on critical tables (freshness, volume, schema)
- Statistical anomaly detection (rolling window baselines)
- Tiered alerting: P1 (PagerDuty), P2 (Slack), P3 (Dashboard)
- Auto-remediation for known issues (restart pipeline, trigger backfill)

## Q217: Design a multi-region data replication strategy for a global company.
- Active-active in 3 regions with conflict resolution
- Event sourcing (no conflicts, events are immutable)
- Regional data sovereignty (PII stays in region)
- Global aggregates via async fan-in

## Q218: Design a streaming ETL pipeline for IoT data (1M devices, 10 events/device/second).
- Kafka (10M events/s) → Flink (windowed aggregation) → ClickHouse (query)
- Device-level downsampling (raw → 1-min → 5-min → 1-hour)
- Edge pre-processing (reduce data before cloud)
- Hot/cold tiering based on device activity

## Q219: Design a data lineage and impact analysis system.
- Automated lineage capture (OpenLineage spec) from Spark, Airflow, dbt
- Graph database backend (Neo4j / Neptune) for relationship traversal
- Impact analysis API: "What downstream breaks if column X changes?"
- Automated PR checks: Detect lineage-breaking changes in CI

## Q220: Design a self-healing data pipeline.
- Automatic retry with exponential backoff
- Circuit breaker for external dependencies
- Auto-scaling based on input volume (KEDA on K8s)
- Automatic data validation and quarantine (bad data → DLQ, good data → proceed)
- Runbook automation: Common failures → automated fixes

## Q221-240: [Additional System Design Scenarios - Key Points]

**Q221:** Design a real-time recommendation system data pipeline.
- Batch features (Spark → Feature Store) + Streaming features (Flink → Redis)
- Model serving: Pre-computed for top users, real-time for long tail
- A/B testing infrastructure for recommendation algorithms

**Q222:** Design a log analytics platform (10TB logs/day, search within 30s).
- OpenSearch/Elasticsearch for hot data (7 days)
- S3 + Athena for cold (cost-efficient ad-hoc search)
- Kafka → Flink (parse, enrich, route by severity) → OpenSearch/S3

**Q223:** Design a data platform migration from on-prem Hadoop to cloud.
- Phase 1: Lift-and-shift (EMR/Dataproc)
- Phase 2: Modernize (Iceberg, serverless Spark)
- Phase 3: Cloud-native (managed services, pay-per-query)
- Dual-run validation throughout migration

**Q224:** Design a fraud detection pipeline (1ms latency for blocking).
- Two-tier: Fast path (rules engine, 1ms) + Slow path (ML model, 100ms)
- Fast path catches 80% of known fraud patterns
- Slow path catches sophisticated fraud, feeds back to rules

**Q225:** Design a data mesh implementation for a 500-person engineering org.
- Platform team: Self-serve infrastructure (templates, automation)
- Domain teams: Own their data products (dbt projects per domain)
- Data contracts between domains
- Federated governance (naming standards, quality requirements)

**Q226:** Design a data pipeline for regulatory reporting (SOX compliance).
- Full audit trail (who changed what, when)
- Immutable storage (cannot modify after submission)
- Dual-control (separate preparer and approver)
- Reconciliation (source-to-report tie-out)

**Q227:** Design a real-time personalization engine.
- User context (current page, time, device) → Feature store → Model → Response
- Pre-computed segments (batch) + real-time signals (streaming)
- Content pre-fetch (prepare top recommendations ahead of time)

**Q228:** Design a data lake with multi-tenant isolation.
- Namespace isolation (per-tenant schemas/databases)
- Resource quotas (prevent noisy neighbor)
- Row-level security for shared tables
- Cost attribution per tenant

**Q229:** Design a streaming anomaly detection system.
- Statistical: Running Z-score, CUSUM, Seasonal decomposition
- ML: Online learning (River/MOA), windowed models
- Multi-signal correlation (alert suppression for known cascades)

**Q230:** Design a data pipeline for ML model training at scale.
- Feature engineering pipeline (Spark → Feature Store → Iceberg)
- Training pipeline (Airflow → distributed training on GPUs)
- Data versioning (DVC or Iceberg snapshots for reproducibility)
- Point-in-time correctness (avoid look-ahead bias)

**Q231:** Design a change data capture system for a legacy mainframe.
- Log-based CDC for DB2/IMS (Attunity/HVR/Qlik)
- File-based CDC for flat files (delta detection)
- API-based extraction for COBOL services
- Staging in Kafka → Data lake

**Q232:** Design a real-time data warehouse (streaming + batch merged).
- Kappa: All data through streaming pipeline into lakehouse
- Compaction merges streaming micro-batches into optimized files
- Materialized views for common aggregations
- Late data handled via MERGE/upsert

**Q233:** Design a metadata-driven ETL framework.
- Config (YAML/JSON) describes: source, target, transformations
- Code generator creates pipeline from config
- Generic operators parameterized by metadata
- Schema-driven (auto-adapt to source schema changes)

**Q234:** Design a data platform observability stack.
- Pipeline metrics: Duration, success rate, data freshness
- Infrastructure metrics: Cluster utilization, costs
- Data quality metrics: Scores, anomalies, SLA compliance
- Unified dashboard with drill-down from high-level to specific table

**Q235:** Design a streaming join system for enriching events with slowly-changing reference data.
- Broadcast join for small reference data (<1GB)
- Temporal join for versioned reference data
- Cache-aside pattern (Redis lookup, TTL refresh)
- Trade-off: Freshness vs latency vs cost

**Q236:** Design a data pipeline testing strategy.
- Unit tests: Transform function logic (mocked data)
- Integration tests: End-to-end with test data (testcontainers)
- Contract tests: Schema compatibility, quality rules
- Performance tests: Process realistic volumes, measure latency
- Chaos tests: Kill components, verify recovery

**Q237:** Design a cost allocation system for a shared data platform.
- Tag all resources by team/project/domain
- Metering: Queries (bytes scanned), storage (TB stored), compute (hours)
- Showback/chargeback reports per team
- Optimization recommendations per team

**Q238:** Design a system to handle data backfills at scale (reprocess 1 year of data).
- Idempotent pipeline (overwrite partitions)
- Parallel by partition (date-based fan-out)
- Throttled to not impact production (off-peak, resource limits)
- Validation: Old output vs new output comparison

**Q239:** Design a unified batch + streaming processing framework.
- Apache Beam / Dataflow: Write once, run batch or streaming
- Or: Flink with bounded sources for batch
- Shared transformation library (Python/Scala)
- Configuration determines mode (batch window vs streaming)

**Q240:** Design a data platform for a startup scaling from 0 to 100M events/day.
- Phase 1 (0-1M/day): Simple (Fivetran → BigQuery → dbt → Looker)
- Phase 2 (1-10M/day): Add Kafka, introduce streaming, Airflow
- Phase 3 (10-100M/day): Flink, Iceberg, dedicated platform team
- Key: Don't over-engineer early, but design for evolution
