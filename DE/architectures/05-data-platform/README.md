# Complete Data Platform Architecture
# Staff Architect Reference: Building from Zero to Petabyte Scale

---

## Evolution Stages

```
STAGE 1: Startup (0-10 TB)              STAGE 2: Growth (10-100 TB)
─────────────────────────────            ─────────────────────────────
PostgreSQL → dbt → Metabase              Kafka → Spark → Delta Lake → Trino
Cost: $2K/month                          Cost: $20K/month
Team: 1-2 engineers                      Team: 3-5 engineers

STAGE 3: Scale (100TB-1PB)              STAGE 4: Enterprise (1PB+)
─────────────────────────────            ─────────────────────────────
Kafka → Flink + Spark → Iceberg          Data Mesh + Full Platform
→ Pinot + Trino + Redis                  Federated governance
Cost: $80-150K/month                     Cost: $500K+/month
Team: 8-15 engineers                     Team: 30+ engineers
```

---

## Full Platform Stack (Stage 3-4)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     ENTERPRISE DATA PLATFORM                                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ════════════════════════════════════════════════════════════════════════════════  │
│  LAYER 1: DATA SOURCES                                                            │
│  ════════════════════════════════════════════════════════════════════════════════  │
│                                                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ OLTP DBs │ │ SaaS APIs│ │ Event    │ │ Files/   │ │ Partner  │              │
│  │ (MySQL,  │ │ (Salesforce│ │ Streams  │ │ Object   │ │ Data     │             │
│  │  Postgres)│ │  HubSpot) │ │ (Logs,   │ │ Store    │ │ Feeds    │             │
│  │          │ │          │ │  Clicks) │ │ (CSV,JSON)│ │          │              │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘             │
│       │            │            │            │            │                       │
│  ════════════════════════════════════════════════════════════════════════════════  │
│  LAYER 2: INGESTION                                                               │
│  ════════════════════════════════════════════════════════════════════════════════  │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                              │ │
│  │  CDC (Debezium):          Batch (Airbyte):       Stream (Direct):           │ │
│  │  • Read DB WAL/binlog     • Schedule-based       • Kafka producers          │ │
│  │  • Zero source impact     • Full + incremental   • SDK in applications      │ │
│  │  • Real-time (seconds)    • 100+ connectors      • <1ms to Kafka            │ │
│  │  • All CRUD operations    • Hourly/daily         •                           │ │
│  │                                                                              │ │
│  │  ALL → KAFKA (Unified Event Bus)                                             │ │
│  │  • 200+ topics (one per source table/event type)                             │ │
│  │  • Schema Registry (Avro/Protobuf, compatibility enforcement)                │ │
│  │  • 7-day retention + tiered storage to S3                                    │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ════════════════════════════════════════════════════════════════════════════════  │
│  LAYER 3: PROCESSING                                                              │
│  ════════════════════════════════════════════════════════════════════════════════  │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                              │ │
│  │  STREAM (Apache Flink):                                                      │ │
│  │  ├── Event enrichment (join with dimensions)                                 │ │
│  │  ├── Real-time aggregations (windows, sessionization)                        │ │
│  │  ├── CDC apply to lakehouse (streaming MERGE)                                │ │
│  │  ├── Feature computation (ML feature store)                                  │ │
│  │  └── Anomaly detection (real-time quality checks)                            │ │
│  │                                                                              │ │
│  │  BATCH (Apache Spark):                                                       │ │
│  │  ├── Heavy transformations (join 10+ tables)                                 │ │
│  │  ├── ML model training (daily/weekly)                                        │ │
│  │  ├── Historical backfills (reprocess months of data)                         │ │
│  │  ├── Compaction & optimization (OPTIMIZE, Z-ORDER)                           │ │
│  │  └── Complex aggregations (funnel analysis, cohorts)                         │ │
│  │                                                                              │ │
│  │  TRANSFORM (dbt):                                                            │ │
│  │  ├── SQL-based transformations (silver → gold)                               │ │
│  │  ├── Data modeling (star schema, wide tables)                                │ │
│  │  ├── Data quality tests (built-in + custom)                                  │ │
│  │  ├── Documentation (auto-generated from YAML)                                │ │
│  │  └── Lineage (DAG of all dependencies)                                       │ │
│  │                                                                              │ │
│  │  ORCHESTRATION (Airflow/Dagster):                                            │ │
│  │  ├── DAG scheduling (dependencies, retries, alerts)                          │ │
│  │  ├── SLA monitoring (alert if job late)                                      │ │
│  │  ├── Resource management (cluster spin-up/down)                              │ │
│  │  └── Cross-pipeline dependencies                                             │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ════════════════════════════════════════════════════════════════════════════════  │
│  LAYER 4: STORAGE (Lakehouse)                                                     │
│  ════════════════════════════════════════════════════════════════════════════════  │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                              │ │
│  │  OBJECT STORE (S3/GCS/ADLS): Foundation                                      │ │
│  │  └── TABLE FORMAT (Apache Iceberg): ACID + Metadata                          │ │
│  │                                                                              │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐       │ │
│  │  │  BRONZE (Raw Zone)           SILVER (Clean Zone)    GOLD (Biz Zone)     │ │
│  │  │  ─────────────────           ────────────────────   ─────────────────   │ │
│  │  │  • Exact source copy         • Deduplicated          • Star schema       │ │
│  │  │  • Append-only               • Type-conformed         • Aggregated       │ │
│  │  │  • Schema-on-read            • Validated              • KPIs/Metrics     │ │
│  │  │  • Full fidelity             • Standardized           • ML features      │ │
│  │  │                                                                          │ │
│  │  │  Retention: 90 days          Retention: 3 years      Retention: Forever  │ │
│  │  │  Access: Platform team       Access: Data engineers   Access: Analysts   │ │
│  │  └──────────────────────────────────────────────────────────────────┘       │ │
│  │                                                                              │ │
│  │  HOT STORAGE (for real-time serving):                                        │ │
│  │  ├── Redis Cluster: Features, session state, caches (TB-scale)               │ │
│  │  ├── Apache Pinot: Real-time OLAP, dashboards (<100ms)                       │ │
│  │  └── Elasticsearch: Search, logs, observability                              │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ════════════════════════════════════════════════════════════════════════════════  │
│  LAYER 5: SERVING & CONSUMPTION                                                   │
│  ════════════════════════════════════════════════════════════════════════════════  │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                              │ │
│  │  QUERY ENGINES:                                                              │ │
│  │  ├── Trino: Interactive SQL (ad-hoc, exploration, <30s queries)              │ │
│  │  ├── Spark SQL: Heavy analytics (>30s, joins, ML)                            │ │
│  │  ├── DuckDB: Local development (laptop, notebooks)                           │ │
│  │  └── Pinot: Real-time (sub-second, dashboards)                               │ │
│  │                                                                              │ │
│  │  CONSUMERS:                                                                  │ │
│  │  ├── BI Tools: Looker, Tableau, Metabase (dashboards, reports)               │ │
│  │  ├── Notebooks: Jupyter, Databricks (exploration, ML)                        │ │
│  │  ├── ML Platform: Feature Store → Training → Serving                         │ │
│  │  ├── Data APIs: REST/GraphQL (data products for applications)                │ │
│  │  ├── Reverse ETL: Push insights back to operational tools                    │ │
│  │  └── Data Sharing: Iceberg REST catalog (cross-team/org sharing)             │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ════════════════════════════════════════════════════════════════════════════════  │
│  LAYER 6: GOVERNANCE & SECURITY                                                   │
│  ════════════════════════════════════════════════════════════════════════════════  │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                              │ │
│  │  CATALOG: Unity Catalog / DataHub / Amundsen                                 │ │
│  │  ├── Table discovery and documentation                                       │ │
│  │  ├── Column-level lineage (source → transform → output)                     │ │
│  │  ├── Data classification (PII, sensitive, public)                            │ │
│  │  └── Usage tracking (who queries what, popularity)                           │ │
│  │                                                                              │ │
│  │  ACCESS CONTROL:                                                             │ │
│  │  ├── RBAC (roles: analyst, engineer, admin)                                  │ │
│  │  ├── Column masking (PII columns hashed for non-privileged)                  │ │
│  │  ├── Row-level security (users see only their department's data)             │ │
│  │  └── Audit logging (every query recorded for compliance)                     │ │
│  │                                                                              │ │
│  │  DATA QUALITY:                                                               │ │
│  │  ├── Great Expectations (expectation suites per table)                       │ │
│  │  ├── dbt tests (uniqueness, not-null, accepted values)                       │ │
│  │  ├── Anomaly detection (ML-based on freshness, volume, distribution)         │ │
│  │  └── Data contracts (producer guarantees to consumers)                       │ │
│  │                                                                              │ │
│  │  COMPLIANCE:                                                                 │ │
│  │  ├── GDPR: Right to erasure (crypto-shredding pattern)                       │ │
│  │  ├── SOC2: Access audit trail, encryption at rest/transit                    │ │
│  │  ├── HIPAA: PHI isolation, minimum necessary access                          │ │
│  │  └── Retention: Automated lifecycle (archive/delete per policy)              │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ════════════════════════════════════════════════════════════════════════════════  │
│  LAYER 7: OBSERVABILITY & OPERATIONS                                              │
│  ════════════════════════════════════════════════════════════════════════════════  │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                              │ │
│  │  MONITORING:                                                                 │ │
│  │  ├── Infrastructure: Prometheus + Grafana (CPU, memory, disk, network)       │ │
│  │  ├── Pipeline: Custom metrics (throughput, latency, error rate)              │ │
│  │  ├── Data Quality: Freshness, volume, schema drift dashboards                │ │
│  │  └── Cost: Per-team, per-pipeline cost attribution                           │ │
│  │                                                                              │ │
│  │  ALERTING:                                                                   │ │
│  │  ├── P1: Pipeline stopped, data loss → PagerDuty (immediate)                │ │
│  │  ├── P2: SLA breach, high error rate → Slack + PagerDuty (15 min)           │ │
│  │  ├── P3: Quality degradation, cost spike → Slack + Ticket (24h)             │ │
│  │  └── Noise reduction: Alert grouping, correlation, dedup                    │ │
│  │                                                                              │ │
│  │  INCIDENT RESPONSE:                                                          │ │
│  │  ├── Runbooks: Automated recovery for common failures                        │ │
│  │  ├── On-call rotation: 1 primary + 1 secondary, weekly rotation              │ │
│  │  ├── Post-mortems: Blameless, action items tracked to completion             │ │
│  │  └── Chaos testing: Monthly failure injection (Kafka broker, Flink crash)    │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Decision Framework

```
FOR EACH COMPONENT, ASK:
═══════════════════════
1. What problem does it solve?
2. What are the alternatives?
3. Why THIS choice over alternatives?
4. What's the scaling ceiling?
5. What's the failure mode?
6. What's the operational cost (not just $, but team time)?

EXAMPLE: Why Iceberg over Delta Lake?
─────────────────────────────────────
Both solve: ACID on object storage
Iceberg advantages:
  • Better multi-engine support (Trino, Flink, Spark all first-class)
  • Hidden partitioning (users don't need to know partition columns)
  • Partition evolution (change partitioning without rewrite)
  • Open governance (no single vendor control)
Delta advantages:
  • Better Spark integration (same company: Databricks)
  • Larger community (more Stack Overflow answers)
  • Optimize command (Z-ORDER) more mature

Decision: Choose Iceberg if multi-engine, Delta if Databricks-centric.
```

---

## Cost Model (Monthly, Stage 3)

```
┌────────────────────────────────────────────────────────────────┐
│  MONTHLY COST BREAKDOWN (10TB/day ingestion, 1PB total)        │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  COMPUTE:                                                       │
│  ├── Kafka (managed, 15 brokers): $25,000                       │
│  ├── Flink (50 TaskManagers × on-demand): $18,000               │
│  ├── Spark (batch, auto-scaled, spot): $15,000                  │
│  ├── Trino (20 workers, auto-suspend): $8,000                   │
│  ├── Pinot (real-time, 10 nodes): $12,000                       │
│  └── Subtotal: $78,000                                          │
│                                                                 │
│  STORAGE:                                                       │
│  ├── S3 Standard (200TB hot): $4,600                            │
│  ├── S3 IA (800TB warm): $10,000                                │
│  ├── Redis (200GB cluster): $5,000                              │
│  ├── Elasticsearch (5TB): $3,000                                │
│  └── Subtotal: $22,600                                          │
│                                                                 │
│  NETWORKING:                                                    │
│  ├── Data transfer (cross-AZ): $5,000                           │
│  ├── NAT Gateway: $3,000                                        │
│  └── Subtotal: $8,000                                           │
│                                                                 │
│  TOOLS & LICENSES:                                              │
│  ├── Airflow (managed): $2,000                                  │
│  ├── BI Tools (Looker): $5,000                                  │
│  ├── Monitoring (Datadog): $3,000                               │
│  ├── Schema Registry (Confluent): $2,000                        │
│  └── Subtotal: $12,000                                          │
│                                                                 │
│  TOTAL: ~$120,000/month (~$1.4M/year)                           │
│                                                                 │
│  OPTIMIZATION OPPORTUNITIES:                                    │
│  • Spot instances for Spark: -40% compute ($6K savings)         │
│  • S3 lifecycle to Glacier: -30% storage ($3K savings)          │
│  • Auto-suspend Trino off-hours: -50% ($4K savings)             │
│  • Reserved instances (1yr): -30% across board ($25K savings)   │
│  • Optimized: ~$82,000/month (32% reduction)                    │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

