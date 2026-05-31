# Architecture 02: Production Batch Lakehouse

## Design Goals

```
WHAT WE'RE BUILDING:
════════════════════
A production-grade batch lakehouse that processes 5-50 TB/day of data
from multiple sources, transforms through medallion layers, and serves
analytics + ML workloads with < 15 minute data freshness.

NON-GOALS:
  • Sub-second latency (use streaming architecture for that)
  • Real-time dashboards (batch = at least micro-batch intervals)
  • OLTP workloads (this is analytical, not transactional)

TARGET SLA:
  • Data freshness: < 15 minutes for critical tables, < 2 hours for others
  • Query latency: P95 < 30 seconds for standard analytics queries
  • Availability: 99.9% (< 8.7 hours downtime/year)
  • Data quality: > 99.5% of records pass validation
  • Recovery time: < 30 minutes (point-in-time restore via table versioning)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PRODUCTION BATCH LAKEHOUSE                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INGESTION LAYER                                                             │
│  ═══════════════                                                             │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Fivetran/    │  │ Debezium     │  │ Custom APIs  │  │ File Drops   │   │
│  │ Airbyte      │  │ (CDC)        │  │ (Python)     │  │ (S3/SFTP)    │   │
│  │              │  │              │  │              │  │              │   │
│  │ SaaS sources │  │ PostgreSQL   │  │ REST/GraphQL │  │ Partner      │   │
│  │ (Salesforce, │  │ MySQL        │  │ Paginated    │  │ data feeds   │   │
│  │  HubSpot,   │  │ MongoDB      │  │ Rate-limited │  │ CSV/Parquet  │   │
│  │  Stripe)    │  │              │  │              │  │              │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                  │                  │                  │           │
│         ▼                  ▼                  ▼                  ▼           │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  LANDING ZONE (S3: s3://lakehouse-landing/)                      │        │
│  │  • Raw files as-is from sources                                  │        │
│  │  • Partitioned by: source/date/batch_id                          │        │
│  │  • Retention: 30 days (debugging + replay)                       │        │
│  │  • Format: Source-native (JSON, CSV, Avro, Parquet)              │        │
│  └──────────────────────────────┬──────────────────────────────────┘        │
│                                  │                                           │
│  STORAGE LAYER                   │                                           │
│  ═════════════                   ▼                                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  BRONZE (S3: s3://lakehouse-bronze/)                             │        │
│  │  Format: Delta Lake (ACID, time travel, schema evolution)        │        │
│  │  Partition: _ingestion_date                                      │        │
│  │  Retention: 1 year (time travel: 30 days)                        │        │
│  │  Purpose: Immutable raw record store                             │        │
│  └──────────────────────────────┬──────────────────────────────────┘        │
│                                  │ Spark/dbt                                 │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  SILVER (S3: s3://lakehouse-silver/)                             │        │
│  │  Format: Delta Lake / Iceberg                                    │        │
│  │  Partition: business_date, entity_type                           │        │
│  │  Z-ORDER: primary business keys                                  │        │
│  │  Retention: 3 years                                              │        │
│  │  Purpose: Validated, deduplicated, conformed                     │        │
│  └──────────────────────────────┬──────────────────────────────────┘        │
│                                  │ dbt                                       │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  GOLD (S3: s3://lakehouse-gold/)                                 │        │
│  │  Format: Delta Lake / Iceberg                                    │        │
│  │  Partition: Optimized per table (date, region, etc.)             │        │
│  │  Purpose: Business metrics, ML features, reporting               │        │
│  └──────────────────────────────┬──────────────────────────────────┘        │
│                                  │                                           │
│  SERVING LAYER                   │                                           │
│  ═════════════                   ▼                                           │
│                                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ Trino/     │  │ ClickHouse │  │ dbt Metrics│  │ Feature    │           │
│  │ Athena     │  │ (OLAP)     │  │ + Cube.dev │  │ Store      │           │
│  │            │  │            │  │            │  │ (Feast)    │           │
│  │ Ad-hoc     │  │ Dashboards │  │ Semantic   │  │ ML serving │           │
│  │ queries    │  │ (sub-sec)  │  │ layer      │  │            │           │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘           │
│                                                                              │
│  ORCHESTRATION                                                               │
│  ═════════════                                                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  Dagster (preferred) or Airflow                                  │        │
│  │                                                                  │        │
│  │  Asset-based DAG:                                                │        │
│  │  [ingest_orders] → [bronze.orders] → [silver.orders]            │        │
│  │                                    → [silver.order_items]        │        │
│  │                     [bronze.customers] → [silver.customers]      │        │
│  │                                                                  │        │
│  │  [silver.orders] + [silver.customers] → [gold.customer_revenue]  │        │
│  │  [silver.orders] + [silver.products]  → [gold.product_metrics]   │        │
│  │                                                                  │        │
│  │  Schedule: Every 15 min (critical), hourly (standard), daily     │        │
│  │  Sensors: Trigger on new file arrival (event-driven)             │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Technology Decisions

```
WHY DELTA LAKE (not Iceberg/Hudi):
═══════════════════════════════════
For Spark-primary shops:
  ✓ Native Spark integration (Databricks backing)
  ✓ MERGE INTO for SCD Type 2 (most mature implementation)
  ✓ Time travel (VERSION AS OF) for debugging
  ✓ OPTIMIZE + ZORDER for query performance
  ✓ Liquid clustering (new, replaces static partitioning)

For multi-engine shops (Spark + Trino + Flink):
  → Use Apache Iceberg instead
  ✓ Better multi-engine support
  ✓ Partition evolution (change partitioning without rewrite)
  ✓ Hidden partitioning (users don't need to know partition scheme)
  
WHY DAGSTER (not Airflow):
═══════════════════════════
  ✓ Asset-based (think "tables" not "tasks")
  ✓ Built-in lineage and freshness tracking
  ✓ Software-defined assets = testable, versionable
  ✓ Partitioned assets (native support for date-partitioned tables)
  ✓ Sensors: React to new data (not just cron schedules)
  
  Airflow is fine if: team already knows it, mature deployment, 
  simple task-based workflows.

WHY SPARK (not Snowflake/BigQuery):
═══════════════════════════════════
  Cost: Spark on spot instances = $0.02/vCPU-hour (vs $4/credit Snowflake)
  Control: Custom UDFs, ML integration, complex transforms
  Scale: Handle 50 TB/day without credit explosion
  
  Snowflake wins when: Team is small, transforms are SQL-only, 
  operational complexity is unacceptable.
```

## Capacity Planning

```
SIZING FOR 10 TB/DAY INGESTION:
════════════════════════════════

Storage (S3):
  Bronze: 10 TB/day × 365 days = 3.6 PB/year
    Cost: 3,600 TB × $0.023/GB = $82,800/year (S3 Standard)
    Optimize: Move to S3-IA after 30 days → $0.0125/GB → $55,000/year
    
  Silver: ~7 TB/day (30% reduction from dedup/filter) × 365 = 2.5 PB/year
    Cost: 2,500 TB × $0.023/GB = $57,500/year
    
  Gold: ~500 GB/day (aggregated) × 365 = 180 TB/year
    Cost: 180 TB × $0.023/GB = $4,140/year

  Total Storage: ~$120,000/year

Compute (EMR Spark):
  Bronze → Silver: 10 TB/day, 15 min window
    Cluster: 20 × r5.4xlarge (128 GB RAM, 16 vCPU each)
    Duration: ~45 min per run, 4 runs/hour
    Cost (spot): 20 × $0.40/hr × 4 hrs/day = $32/day = $11,680/year
    
  Silver → Gold: Complex aggregations
    Cluster: 10 × r5.2xlarge
    Duration: ~30 min per run, hourly
    Cost (spot): 10 × $0.20/hr × 12 hrs/day = $24/day = $8,760/year
    
  Compaction jobs (nightly):
    Cluster: 10 × r5.4xlarge, 2 hours
    Cost: 10 × $0.40/hr × 2 hrs = $8/day = $2,920/year
    
  Total Compute: ~$25,000/year

Orchestration (Dagster Cloud):
  Standard plan: ~$500/month = $6,000/year
  OR self-hosted: 3 × m5.xlarge = $4,500/year

Query Engine (Trino for ad-hoc):
  Cluster: 5 × r5.2xlarge (always-on for interactive queries)
  Cost: 5 × $0.504/hr × 24 × 365 = $22,075/year

TOTAL ANNUAL COST: ~$175,000/year for 10 TB/day pipeline
  Storage: $120K (68%)
  Compute: $25K (14%)
  Query: $22K (13%)
  Orchestration: $6K (3%)
  
COMPARE:
  Snowflake (same workload): ~$400,000-600,000/year
  Databricks (managed): ~$250,000-350,000/year
  This architecture: ~$175,000/year (but more operational complexity)
```

## Failure Modes & Recovery

```
┌──────────────────────┬───────────────────────────────┬──────────────────────┐
│ FAILURE              │ IMPACT                         │ RECOVERY             │
├──────────────────────┼───────────────────────────────┼──────────────────────┤
│ Source unavailable   │ Bronze doesn't update          │ Retry with backoff   │
│ (API down)           │ Silver/Gold stale              │ Alert after 3 fails  │
│                      │                                │ Backfill when back   │
├──────────────────────┼───────────────────────────────┼──────────────────────┤
│ Spark job OOM        │ Transform fails mid-way        │ Delta: atomic commit │
│                      │ Partial data NOT written       │ No partial state     │
│                      │ (ACID guarantees)              │ Increase memory,     │
│                      │                                │ repartition, retry   │
├──────────────────────┼───────────────────────────────┼──────────────────────┤
│ Bad data from source │ Bronze has garbage             │ DQ checks block      │
│ (schema break)       │ Silver transform fails         │ promotion to Silver  │
│                      │                                │ Alert data engineer  │
│                      │                                │ Fix + backfill       │
├──────────────────────┼───────────────────────────────┼──────────────────────┤
│ Accidental delete    │ Gold table dropped/corrupted   │ Delta time travel:   │
│ (human error)        │ Dashboard shows no data        │ RESTORE TABLE AS OF  │
│                      │                                │ VERSION <n>          │
│                      │                                │ Recovery: < 5 min    │
├──────────────────────┼───────────────────────────────┼──────────────────────┤
│ S3 outage            │ Everything stops               │ Wait (S3 is 11 9s)  │
│ (extremely rare)     │                                │ Cross-region replica │
│                      │                                │ if truly critical    │
├──────────────────────┼───────────────────────────────┼──────────────────────┤
│ Orchestrator down    │ No new jobs scheduled          │ Dagster HA (k8s)     │
│                      │ Data gets stale                │ Auto-restart, catch  │
│                      │                                │ up missed partitions │
└──────────────────────┴───────────────────────────────┴──────────────────────┘
```

## Operational Runbook

```
DAILY OPERATIONS:
════════════════
  08:00 - Check Dagster: All critical assets green? Freshness OK?
  08:15 - Check data quality dashboard: Anomalies in yesterday's load?
  08:30 - Review compute costs: Any runaway jobs? Spot interruptions?
  
WEEKLY:
  - Run compaction on Bronze/Silver (OPTIMIZE + VACUUM)
  - Review query performance (slow queries → add Z-ORDER or partitions)
  - Check storage growth vs budget
  - Review DLQ: Any recurring data quality issues?

MONTHLY:
  - Capacity planning: Are we trending toward limits?
  - Cost optimization: Unused tables? Over-provisioned clusters?
  - Schema evolution: Any pending source system changes?
  - Disaster recovery test: Can we restore from backup?

ALERTS (PagerDuty):
  P1 (wake up): Critical Gold table > 1 hour stale
  P2 (business hours): Silver job failed 3x
  P3 (next day): Compaction job slow, storage growth unexpected
```
