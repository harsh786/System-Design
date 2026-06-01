# S3 + Apache Iceberg Data Pipelines at Production Scale

## Context: Why This Exists

This folder explains **every Apache Iceberg concept** through **10 real production problems** that companies
like Netflix, Apple, LinkedIn, Stripe, Airbnb, and major banks face when building **data lakehouses
processing billions of transactions daily on S3**.

Instead of learning Iceberg in isolation, each problem teaches specific concepts in the context of
real-world data engineering challenges where traditional approaches (Hive, raw Parquet, data warehouses) fail.

---

## What is Apache Iceberg?

### The Problem It Solves

```
BEFORE ICEBERG (Hive/Raw Parquet on S3):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- No ACID transactions → corrupted reads during writes
- No time travel → can't recover from bad writes
- No row-level updates → full partition rewrites for single row change
- Partition coupling → query engine must know partition scheme
- No schema evolution → breaking changes require full rewrite
- No concurrent writes → last writer wins, data loss
- Small files problem → millions of tiny files kill performance
- No delete support → GDPR compliance nearly impossible

AFTER ICEBERG:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ACID transactions with snapshot isolation
- Full time travel (query any historical state)
- Row-level updates/deletes via merge-on-read or copy-on-write
- Hidden partitioning (query engine doesn't need to know)
- Full schema evolution (add/drop/rename/reorder columns)
- Optimistic concurrency (safe concurrent writes)
- Automatic compaction (solve small files)
- Efficient deletes (GDPR in minutes, not days)
```

### History & Adoption

```
Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2017    │ Netflix creates Iceberg to solve Hive table limitations at PB scale
2018    │ Netflix open-sources Iceberg, donated to Apache Incubator
2019    │ Apple adopts Iceberg for all analytics (largest deployment)
        │ LinkedIn begins migration from proprietary format
2020    │ Apache Iceberg graduates to top-level project
        │ AWS announces Iceberg support in Athena, EMR, Glue
2021    │ Databricks adds Iceberg interop (UniForm)
        │ Snowflake adds Iceberg Tables support
        │ Dremio builds Iceberg-native engine
2022    │ Tabular founded by Iceberg creators (Ryan Blue, Dan Weeks)
        │ Google BigQuery adds Iceberg support
        │ Confluent announces Tableflow (Kafka → Iceberg)
2023    │ AWS S3 Tables (managed Iceberg) announced
        │ Iceberg REST Catalog specification finalized
        │ Snowflake acquires Tabular
2024    │ Iceberg becomes de-facto standard for open lakehouse
        │ Apple: 100,000+ Iceberg tables, Exabytes of data
        │ Netflix: Petabytes daily, billions of files
        │ LinkedIn: 100PB+ migrated to Iceberg
2025    │ Iceberg v3 spec discussions (row-lineage, views)
        │ Universal adoption across all major cloud providers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Core Architecture: How Iceberg Works on S3

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        ICEBERG TABLE ARCHITECTURE ON S3                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         CATALOG LAYER                                    │    │
│  │                                                                          │    │
│  │   Points to current metadata location for each table                     │    │
│  │                                                                          │    │
│  │   Options:                                                               │    │
│  │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │    │
│  │   │  AWS Glue    │ │ Hive Meta-   │ │   Nessie     │ │  REST        │  │    │
│  │   │  Data Catalog│ │ store (HMS)  │ │  (Git-like)  │ │  Catalog     │  │    │
│  │   └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │    │
│  │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                   │    │
│  │   │ Snowflake    │ │   Unity      │ │  S3 Tables   │                   │    │
│  │   │ Polaris      │ │  (Databricks)│ │  (AWS Managed│                   │    │
│  │   └──────────────┘ └──────────────┘ └──────────────┘                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                        │                                         │
│                                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      METADATA LAYER (S3)                                 │    │
│  │                                                                          │    │
│  │  s3://bucket/db/table/metadata/                                          │    │
│  │                                                                          │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Metadata File (v3.metadata.json)                                │    │    │
│  │  │  ─────────────────────────────────────────────                   │    │    │
│  │  │  • Table schema (current + all historical)                       │    │    │
│  │  │  • Partition spec (current + all historical)                     │    │    │
│  │  │  • Sort order                                                    │    │    │
│  │  │  • Table properties                                              │    │    │
│  │  │  • Snapshot list (all versions)                                  │    │    │
│  │  │  • Current snapshot pointer                                      │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  │                          │                                               │    │
│  │                          ▼                                               │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Snapshot (snap-12345678.avro)                                   │    │    │
│  │  │  ─────────────────────────────────────────────                   │    │    │
│  │  │  • Snapshot ID                                                   │    │    │
│  │  │  • Parent snapshot ID (forms version chain)                      │    │    │
│  │  │  • Timestamp                                                     │    │    │
│  │  │  • Operation (append/overwrite/delete/replace)                   │    │    │
│  │  │  • Manifest list pointer                                         │    │    │
│  │  │  • Summary (added/deleted rows, files)                           │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  │                          │                                               │    │
│  │                          ▼                                               │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Manifest List (snap-12345678-m0.avro)                           │    │    │
│  │  │  ─────────────────────────────────────────────                   │    │    │
│  │  │  • List of manifest files                                        │    │    │
│  │  │  • Partition summary per manifest (min/max per partition field)   │    │    │
│  │  │  • Added/existing/deleted file counts                            │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  │                          │                                               │    │
│  │                          ▼                                               │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Manifest Files (manifest-xxxxx.avro)                            │    │    │
│  │  │  ─────────────────────────────────────────────                   │    │    │
│  │  │  • List of data files in this manifest                           │    │    │
│  │  │  • Per-file: path, format, record count, file size               │    │    │
│  │  │  • Per-file: column-level min/max/null_count statistics          │    │    │
│  │  │  • Per-file: partition values                                    │    │    │
│  │  │  • Per-file: split offsets                                       │    │    │
│  │  │  • Status: ADDED, EXISTING, DELETED                              │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                        │                                         │
│                                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        DATA LAYER (S3)                                   │    │
│  │                                                                          │    │
│  │  s3://bucket/db/table/data/                                              │    │
│  │                                                                          │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │    │
│  │  │  Parquet     │  │  Parquet     │  │    ORC       │  Data files       │    │
│  │  │  File 1      │  │  File 2      │  │  File 3      │  (any format)     │    │
│  │  │  (128MB)     │  │  (256MB)     │  │  (128MB)     │                   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │    │
│  │                                                                          │    │
│  │  ┌──────────────┐  ┌──────────────┐                                    │    │
│  │  │  Delete      │  │  Delete      │  Position/Equality delete files     │    │
│  │  │  File 1      │  │  File 2      │  (merge-on-read mode)              │    │
│  │  │  (.parquet)  │  │  (.parquet)  │                                    │    │
│  │  └──────────────┘  └──────────────┘                                    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts Deep Dive

### 1. Snapshots & Time Travel

```
Snapshot Chain (Linked List):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  snap-001          snap-002          snap-003          snap-004 (current)
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Initial  │────▶│ Append   │────▶│ Delete   │────▶│ Overwrite│
  │ load     │     │ new data │     │ GDPR     │     │ compacted│
  │ 1M rows  │     │ +500K    │     │ -1000    │     │ same data│
  │ 10 files │     │ +5 files │     │ +1 del   │     │ 3 files  │
  │ t=Jan 1  │     │ t=Jan 2  │     │ t=Jan 3  │     │ t=Jan 4  │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
       │                                                    │
       │  SELECT * FROM table                               │
       │  VERSION AS OF snap-001;     ◄─── Time Travel ───▶ │
       │                                                    │
       │  SELECT * FROM table         ◄─── Current query    │
       └────────────────────────────────────────────────────┘

Key Properties:
  • Each snapshot is IMMUTABLE (never modified after creation)
  • Snapshots reference manifest lists (which reference manifests → data files)
  • Old snapshots can be expired (garbage collected) with configurable retention
  • Concurrent readers always see consistent snapshot (MVCC)
```

### 2. Partitioning (Hidden Partitions & Partition Evolution)

```
TRADITIONAL (Hive) PARTITIONING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Table: events
  Partition: year=2024/month=01/day=15/

  Problem: Query must KNOW the partition layout
  SELECT * FROM events WHERE event_date = '2024-01-15'
  → Engine must translate: year=2024/month=01/day=15/
  → If partition scheme changes, ALL queries break

ICEBERG HIDDEN PARTITIONING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Table: events (partitioned by days(event_timestamp))

  Query: SELECT * FROM events WHERE event_timestamp = '2024-01-15 10:30:00'
  → Iceberg automatically prunes to correct partition
  → Query engine doesn't know/care about physical layout
  → Partition scheme can EVOLVE without rewriting data

PARTITION EVOLUTION (Zero-downtime):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Time 0: Partition by months(event_ts)     [Low volume: monthly partitions]
           │
           ▼ Table grows, monthly partitions too large
  Time 1: ALTER TABLE SET PARTITION SPEC (days(event_ts))
           │
           │  • Old data stays in monthly partitions (NOT rewritten)
           │  • New data goes to daily partitions
           │  • Queries spanning both work transparently
           ▼
  Time 2: ALTER TABLE SET PARTITION SPEC (hours(event_ts))
           │
           │  • Old monthly + daily data untouched
           │  • New data in hourly partitions
           │  • All three coexist in same table
           ▼
  Result: Zero rewrite, zero downtime, transparent to queries

PARTITION TRANSFORMS:
━━━━━━━━━━━━━━━━━━━━
  • identity(col)       → Exact value (e.g., country code)
  • bucket(col, N)      → Hash into N buckets (high cardinality)
  • truncate(col, W)    → Truncate to width W
  • year(ts)            → Extract year
  • month(ts)           → Extract year-month
  • day(ts)             → Extract year-month-day
  • hour(ts)            → Extract year-month-day-hour
  • void(col)           → Unpartitioned (remove partitioning)
```

### 3. Schema Evolution

```
SAFE SCHEMA OPERATIONS (No data rewrite):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─────────────────────────────────────────────────────────────────┐
  │ Operation              │ Impact on Existing Data                 │
  ├─────────────────────────────────────────────────────────────────┤
  │ ADD column             │ None. Old files return NULL for new col │
  │ DROP column            │ None. Old files still have data, hidden │
  │ RENAME column          │ None. Uses internal column IDs          │
  │ REORDER columns        │ None. Position independent              │
  │ WIDEN type (int→long)  │ None. Promotion handled at read time    │
  │ Make required→optional │ None. NULL now allowed                  │
  └─────────────────────────────────────────────────────────────────┘

HOW IT WORKS - Column IDs:
━━━━━━━━━━━━━━━━━━━━━━━━━━

  Schema v1:                    Schema v2 (renamed + added):
  ┌────┬────────┬─────────┐    ┌────┬────────────┬─────────┐
  │ ID │ Name   │ Type    │    │ ID │ Name       │ Type    │
  ├────┼────────┼─────────┤    ├────┼────────────┼─────────┤
  │ 1  │ user_id│ long    │    │ 1  │ customer_id│ long    │  ← Renamed (same ID!)
  │ 2  │ name   │ string  │    │ 2  │ name       │ string  │
  │ 3  │ age    │ int     │    │ 3  │ age        │ long    │  ← Widened int→long
  │    │        │         │    │ 4  │ email      │ string  │  ← New column
  └────┴────────┴─────────┘    └────┴────────────┴─────────┘

  Old data files: Written with schema v1 (columns 1,2,3)
  New data files: Written with schema v2 (columns 1,2,3,4)
  Reading old files with schema v2:
    → Column 1 maps to "customer_id" (by ID, not name)
    → Column 3 (int) promoted to long at read time
    → Column 4 returns NULL (doesn't exist in old file)
```

### 4. Write Modes: Copy-on-Write vs Merge-on-Read

```
COPY-ON-WRITE (CoW):
━━━━━━━━━━━━━━━━━━━━
  Update: SET status='cancelled' WHERE order_id = 12345

  ┌──────────────────┐         ┌──────────────────┐
  │ Original File    │         │ New File          │
  │ (1M rows)        │  ──▶    │ (1M rows)         │
  │                  │         │ row 12345 updated │
  │ 128MB Parquet    │         │ 128MB Parquet     │
  └──────────────────┘         └──────────────────┘
        │                              │
        └─ Marked as DELETED ──────────└─ Marked as ADDED
           in new snapshot                in new snapshot

  Pros: Fast reads (no merge needed), simple
  Cons: Expensive writes (rewrite entire file for 1 row)
  Best for: Read-heavy workloads, infrequent updates

MERGE-ON-READ (MoR):
━━━━━━━━━━━━━━━━━━━━
  Update: SET status='cancelled' WHERE order_id = 12345

  ┌──────────────────┐    ┌──────────────────┐
  │ Original File    │    │ Delete File       │
  │ (1M rows)        │    │ (1 row)           │
  │ row 12345 exists │    │ position: 54321   │
  │ 128MB Parquet    │    │ 1KB Parquet       │
  └──────────────────┘    └──────────────────┘
                           + 
                          ┌──────────────────┐
                          │ Insert File       │
                          │ (1 row)           │
                          │ new row 12345     │
                          │ 1KB Parquet       │
                          └──────────────────┘

  At read time: Original file - Delete file + Insert file = Result

  Pros: Fast writes (tiny delta files), efficient for frequent updates
  Cons: Slower reads (must merge), needs compaction
  Best for: Write-heavy workloads, streaming upserts, CDC

DELETE FILE TYPES:
━━━━━━━━━━━━━━━━━━
  Position Deletes: "Delete row at position 54321 in file X"
    → Faster to apply (direct offset)
    → Generated by: UPDATE, DELETE with known file positions

  Equality Deletes: "Delete all rows where user_id = 12345"
    → More flexible (don't need to know positions)
    → Slower to apply (must scan and filter)
    → Generated by: streaming deletes, CDC
```

### 5. Catalog & Metadata Management

```
CATALOG COMPARISON:
━━━━━━━━━━━━━━━━━━━

┌──────────────┬───────────────┬───────────────┬───────────────┬───────────────┐
│ Feature      │ AWS Glue      │ Hive MS       │ Nessie        │ REST Catalog  │
├──────────────┼───────────────┼───────────────┼───────────────┼───────────────┤
│ Managed      │ Serverless    │ Self-hosted   │ Self-hosted   │ Any impl      │
│ Locking      │ DynamoDB      │ DB-level      │ Git-like      │ Server-side   │
│ Multi-engine │ ✓ (AWS)       │ ✓             │ ✓             │ ✓ (standard)  │
│ Branching    │ ✗             │ ✗             │ ✓ (Git model) │ Impl-specific │
│ Access ctrl  │ IAM/LakeForm  │ Ranger        │ Built-in      │ Impl-specific │
│ Versioning   │ ✗             │ ✗             │ ✓ (commits)   │ Impl-specific │
│ Cost         │ Per-request   │ Infra cost    │ Infra cost    │ Varies        │
│ Best for     │ AWS-native    │ On-prem/EMR   │ Data-as-code  │ Multi-cloud   │
└──────────────┴───────────────┴───────────────┴───────────────┴───────────────┘

NESSIE (Git-for-Data):
━━━━━━━━━━━━━━━━━━━━━━
  main ──────────────●──────────────●──────────────● (production)
                     │              ▲
                     │              │ merge
                     ▼              │
  feature/new-etl ──●──────●──────● (development branch)
                           │
                           ▼
                    Run tests against branch
                    without affecting production

  • Branch: isolated copy of catalog state (not data!)
  • Commit: atomic multi-table update
  • Merge: promote changes to production
  • Tag: named point-in-time reference
```

### 6. Maintenance Operations

```
COMPACTION (Rewrite Data Files):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Before compaction:                After compaction:
  ┌─────┐ ┌─────┐ ┌─────┐        ┌──────────────────────┐
  │ 5MB │ │ 2MB │ │ 8MB │        │       128MB          │
  └─────┘ └─────┘ └─────┘        │    (optimally sized) │
  ┌─────┐ ┌─────┐ ┌─────┐        └──────────────────────┘
  │ 1MB │ │ 3MB │ │ 7MB │        ┌──────────────────────┐
  └─────┘ └─────┘ └─────┘        │       128MB          │
  ┌─────┐ ┌─────┐                │    (optimally sized) │
  │ 4MB │ │ 6MB │                 └──────────────────────┘
  └─────┘ └─────┘
  
  8 small files (36MB total)       2 optimal files (256MB total)
  8 S3 LIST + GET operations       2 S3 GET operations
  Poor predicate pushdown          Excellent predicate pushdown

  Strategies:
  • bin-pack: Combine small files (default, fast)
  • sort: Rewrite with sort order (better for range queries)
  • z-order: Multi-dimensional clustering (better for multi-column filters)

EXPIRE SNAPSHOTS:
━━━━━━━━━━━━━━━━━
  Keep last 7 days of snapshots, expire older ones:
  
  snap-001 ─── snap-002 ─── snap-003 ─── ... ─── snap-100
  │ (30 days ago)           │ (5 days ago)        │ (current)
  │                         │                     │
  └── EXPIRE (delete)       └── KEEP              └── KEEP
  
  What gets deleted:
  • Snapshot metadata files (not data files still referenced!)
  • Manifest lists only referenced by expired snapshots
  • Data files only referenced by expired snapshots
  • Orphan files (data files not referenced by any snapshot)

REWRITE MANIFESTS:
━━━━━━━━━━━━━━━━━━
  Merge small manifests, rewrite for better partition pruning:
  
  Before: 1000 manifest files (1 per commit)
  After:  10 manifest files (optimally grouped by partition)
  
  Impact: Faster planning time (fewer S3 reads for metadata)

REMOVE ORPHAN FILES:
━━━━━━━━━━━━━━━━━━━━
  Find and delete files in data/ not referenced by any metadata:
  
  Causes of orphan files:
  • Failed writes that created files but didn't commit
  • Compaction that created new files, but old references expired
  • Manual file deletions that left dangling references
```

---

## The 10 Real Production Problems

| # | Problem | Company Scale | Iceberg Concepts Covered |
|---|---------|--------------|--------------------------|
| 1 | Financial Transaction History & Audit Trail | Stripe-scale: 2B txns/day | Snapshots, time travel, append-only, expire snapshots, metadata |
| 2 | Real-Time Fraud Detection Feature Store | Banking: 10B events/day | Merge-on-read, upserts, Flink+Iceberg, low-latency reads |
| 3 | E-Commerce Recommendation System | Netflix/Amazon: 500M users | Partitioning, compaction, Spark batch, feature engineering |
| 4 | ML Model Training Data Versioning | AI Company: PBs of training data | Branching (Nessie), tags, reproducibility, schema evolution |
| 5 | GDPR/CCPA - Right to Be Forgotten | Any regulated: PB-scale deletes | Row-level deletes, equality deletes, rewrite, compliance |
| 6 | CDC Slowly Changing Dimensions (SCD2) | Enterprise: 500M customer records | MERGE INTO, copy-on-write, Debezium+Spark, history tracking |
| 7 | Streaming Upserts - Unified Pipeline | Uber-scale: 1M events/sec | Flink sink, MoR, compaction, exactly-once, deduplication |
| 8 | Multi-Source Aggregation + Schema Evolution | Enterprise: 200+ sources | Schema evolution, union-by-name, partition evolution |
| 9 | Cost-Optimized Lakehouse for BI | Large Enterprise: $10M+/yr savings | Partition pruning, predicate pushdown, Z-order, caching |
| 10 | Cross-Region Data Mesh + Catalog Federation | Global: 50+ teams, multi-cloud | REST catalog, Nessie, access control, data contracts |

---

## Production Operations (Files 11-14)

| # | Topic | What It Covers |
|---|-------|----------------|
| 11 | Production Deployment | Terraform, Kubernetes, CI/CD, catalog setup, IAM |
| 12 | Monitoring & Alerting | Table health metrics, compaction monitoring, cost tracking |
| 13 | Scaling for Billions | File sizing, manifest optimization, concurrent writers |
| 14 | Disaster Recovery | Snapshot restore, cross-region replication, corruption recovery |

---

## Technology Stack & Query Engines

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ICEBERG ECOSYSTEM & INTEGRATIONS                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  WRITE ENGINES:                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ Apache Spark │ │ Apache Flink │ │  AWS Glue    │ │   Trino      │           │
│  │ (batch+str)  │ │ (streaming)  │ │ (serverless) │ │ (CTAS/INSERT)│           │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                            │
│  │  Kafka       │ │   dbt        │ │  Hudi/Delta  │                            │
│  │  Connect     │ │ (transform)  │ │  (interop)   │                            │
│  └──────────────┘ └──────────────┘ └──────────────┘                            │
│                                                                                  │
│  QUERY ENGINES:                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ AWS Athena   │ │  Trino/      │ │  Snowflake   │ │  Dremio      │           │
│  │ (serverless) │ │  Presto      │ │              │ │  (Iceberg-   │           │
│  │              │ │              │ │              │ │   native)    │           │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │  Spark SQL   │ │ Google BQ    │ │  StarRocks   │ │  ClickHouse  │           │
│  │              │ │              │ │              │ │              │           │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                                  │
│  ORCHESTRATION:                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ Apache       │ │  Dagster     │ │  Prefect     │ │  Temporal    │           │
│  │ Airflow      │ │              │ │              │ │              │           │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                                  │
│  STORAGE:                                                                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │  AWS S3      │ │  GCS         │ │  Azure ADLS  │ │  MinIO       │           │
│  │              │ │              │ │              │ │  (on-prem)   │           │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                                  │
│  CATALOGS:                                                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │  AWS Glue    │ │  Nessie      │ │  REST Catalog│ │  Polaris     │           │
│  │  Data Catalog│ │              │ │  (standard)  │ │  (Snowflake) │           │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Production Architecture: Billions Scale

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                   PRODUCTION S3 + ICEBERG - BILLIONS SCALE ARCHITECTURE              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────┐     │
│  │                         INGESTION LAYER                                     │     │
│  │                                                                             │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │     │
│  │  │  Kafka      │  │  Debezium   │  │  API Events │  │  File Drops │      │     │
│  │  │  (1M msg/s) │  │  (CDC)      │  │  (REST)     │  │  (S3/SFTP)  │      │     │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │     │
│  │         │                │                │                │               │     │
│  │         ▼                ▼                ▼                ▼               │     │
│  │  ┌─────────────────────────────────────────────────────────────────┐      │     │
│  │  │              FLINK STREAMING JOBS (Real-time)                     │      │     │
│  │  │  • Exactly-once Iceberg sink                                     │      │     │
│  │  │  • Merge-on-read upserts                                         │      │     │
│  │  │  • Deduplication (within window)                                  │      │     │
│  │  │  • Schema validation + dead letter routing                        │      │     │
│  │  │  • Checkpointing every 60s = commit interval                     │      │     │
│  │  └─────────────────────────────────────────────────────────────────┘      │     │
│  └────────────────────────────────────────────────────────────────────────────┘     │
│                                        │                                             │
│                                        ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐     │
│  │                         STORAGE LAYER (S3)                                  │     │
│  │                                                                             │     │
│  │  ┌───────────────────────────────────────────────────────────────────┐    │     │
│  │  │                    BRONZE (Raw/Landing)                             │    │     │
│  │  │  • Iceberg tables with append-only mode                            │    │     │
│  │  │  • Schema: raw event schema, no transformation                     │    │     │
│  │  │  • Retention: 90 days snapshots, 7 years data                      │    │     │
│  │  │  • Partition: hours(ingest_timestamp)                               │    │     │
│  │  └───────────────────────────────────────────────────────────────────┘    │     │
│  │                                        │                                   │     │
│  │                                        ▼                                   │     │
│  │  ┌───────────────────────────────────────────────────────────────────┐    │     │
│  │  │                    SILVER (Cleaned/Conformed)                       │    │     │
│  │  │  • Iceberg tables with MERGE support                               │    │     │
│  │  │  • Schema: standardized, deduplicated, validated                   │    │     │
│  │  │  • Retention: 30 days snapshots                                    │    │     │
│  │  │  • Partition: days(event_date), bucket(entity_id, 256)             │    │     │
│  │  └───────────────────────────────────────────────────────────────────┘    │     │
│  │                                        │                                   │     │
│  │                                        ▼                                   │     │
│  │  ┌───────────────────────────────────────────────────────────────────┐    │     │
│  │  │                    GOLD (Business/Aggregated)                       │    │     │
│  │  │  • Iceberg tables with materialized aggregations                   │    │     │
│  │  │  • Schema: business entities, KPIs, features                       │    │     │
│  │  │  • Retention: 7 days snapshots                                     │    │     │
│  │  │  • Partition: identity(business_unit), days(report_date)           │    │     │
│  │  └───────────────────────────────────────────────────────────────────┘    │     │
│  └────────────────────────────────────────────────────────────────────────────┘     │
│                                        │                                             │
│                                        ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐     │
│  │                       PROCESSING LAYER                                      │     │
│  │                                                                             │     │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │     │
│  │  │  SPARK (EMR/K8s) │  │  dbt + Spark     │  │  AIRFLOW         │         │     │
│  │  │  • Bronze→Silver │  │  • Silver→Gold   │  │  • Orchestration │         │     │
│  │  │  • Compaction    │  │  • Aggregations  │  │  • Scheduling    │         │     │
│  │  │  • MERGE INTO    │  │  • Business logic│  │  • Dependencies  │         │     │
│  │  │  • Deduplication │  │  • Incremental   │  │  • SLA monitoring│         │     │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘         │     │
│  └────────────────────────────────────────────────────────────────────────────┘     │
│                                        │                                             │
│                                        ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐     │
│  │                        QUERY / SERVING LAYER                                │     │
│  │                                                                             │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │     │
│  │  │  Athena     │  │  Trino      │  │  Snowflake  │  │  StarRocks  │      │     │
│  │  │  (ad-hoc)   │  │  (federated)│  │  (BI)       │  │  (real-time)│      │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │     │
│  │                                                                             │     │
│  │  Consumers: Dashboards, ML Pipelines, APIs, Data Science Notebooks         │     │
│  └────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────┐     │
│  │                      MAINTENANCE / OPERATIONS                               │     │
│  │                                                                             │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │     │
│  │  │ Compaction  │  │  Snapshot   │  │  Orphan     │  │  Manifest   │      │     │
│  │  │ Service     │  │  Expiry     │  │  Cleanup    │  │  Rewrite    │      │     │
│  │  │ (scheduled) │  │  (daily)    │  │  (weekly)   │  │  (weekly)   │      │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │     │
│  │                                                                             │     │
│  │  ┌─────────────────────────────────────────────────────────────────┐      │     │
│  │  │  MONITORING: Prometheus + Grafana + PagerDuty                    │      │     │
│  │  │  • Table size growth, file counts, snapshot count                │      │     │
│  │  │  • Commit latency, conflict rate, compaction lag                 │      │     │
│  │  │  • S3 costs, request counts, data scanned                        │      │     │
│  │  └─────────────────────────────────────────────────────────────────┘      │     │
│  └────────────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## When to Use Iceberg vs Alternatives

| Dimension | Apache Iceberg | Delta Lake | Apache Hudi | Raw Parquet |
|-----------|---------------|------------|-------------|-------------|
| **Governance** | Apache Foundation (vendor-neutral) | Databricks (open-sourced) | Apache Foundation | N/A |
| **Engine lock-in** | None (works with all) | Best with Databricks | Best with AWS/Hudi ecosystem | Any |
| **ACID** | ✓ (snapshot isolation) | ✓ (serializable) | ✓ (snapshot) | ✗ |
| **Time travel** | ✓ (snapshot-based) | ✓ (version-based) | ✓ (timeline) | ✗ |
| **Schema evolution** | Full (ID-based) | Basic (name-based) | Limited | ✗ |
| **Partition evolution** | ✓ (hidden, evolve) | ✗ (must rewrite) | ✗ (must rewrite) | ✗ |
| **Row-level deletes** | ✓ (CoW + MoR) | ✓ (CoW + DV) | ✓ (MoR native) | ✗ |
| **Streaming** | ✓ (Flink native) | ✓ (Spark native) | ✓ (designed for) | ✗ |
| **Catalog standard** | REST Catalog spec | Unity Catalog | N/A | N/A |
| **Multi-engine** | Best (Spark/Flink/Trino/Athena/BQ/Snowflake) | Good | Limited | N/A |
| **Community** | Largest (Netflix/Apple/LinkedIn) | Databricks-led | Uber-led | N/A |
| **Best for** | Multi-engine lakehouse | Databricks shops | Streaming-first CDC | Simple analytics |

---

## Quick Start: Production Table Creation

```sql
-- Create namespace (database)
CREATE NAMESPACE IF NOT EXISTS production.financial;

-- Create Iceberg table with all production settings
CREATE TABLE production.financial.transactions (
    transaction_id      STRING,
    account_id          BIGINT,
    amount              DECIMAL(18,2),
    currency            STRING,
    transaction_type    STRING,
    status              STRING,
    merchant_category   STRING,
    country_code        STRING,
    created_at          TIMESTAMP,
    updated_at          TIMESTAMP,
    metadata            MAP<STRING, STRING>
)
USING iceberg
PARTITIONED BY (days(created_at), bucket(16, account_id))
TBLPROPERTIES (
    'format-version' = '2',                          -- Enable row-level deletes
    'write.format.default' = 'parquet',              -- Parquet data files
    'write.parquet.compression-codec' = 'zstd',      -- Best compression ratio
    'write.target-file-size-bytes' = '134217728',    -- 128MB target files
    'write.metadata.delete-after-commit.enabled' = 'true',
    'write.metadata.previous-versions-max' = '100',
    'read.split.target-size' = '134217728',          -- 128MB read splits
    'write.delete.mode' = 'merge-on-read',           -- MoR for deletes
    'write.update.mode' = 'merge-on-read',           -- MoR for updates
    'write.merge.mode' = 'merge-on-read',            -- MoR for merges
    'commit.retry.num-retries' = '10',               -- Optimistic concurrency retries
    'commit.retry.min-wait-ms' = '100',
    'history.expire.max-snapshot-age-ms' = '604800000', -- 7 days
    'write.distribution-mode' = 'hash'               -- Distribute by partition
);
```

---

## File Navigation

| File | Content |
|------|---------|
| `00-overview.md` | This file - concepts, architecture, ecosystem |
| `01-financial-transaction-audit.md` | Time travel, audit, append-only at Stripe scale |
| `02-fraud-detection-feature-store.md` | Real-time features, Flink+Iceberg, MoR |
| `03-recommendation-system-pipeline.md` | User behavior, batch features, compaction |
| `04-ml-training-data-versioning.md` | Nessie branching, reproducibility, tags |
| `05-gdpr-right-to-be-forgotten.md` | Row-level deletes, compliance workflows |
| `06-cdc-slowly-changing-dimensions.md` | MERGE INTO, SCD Type 2, Debezium |
| `07-streaming-upserts-unified.md` | Flink sink, exactly-once, deduplication |
| `08-multi-source-schema-evolution.md` | Schema evolution, partition evolution |
| `09-cost-optimized-lakehouse-bi.md` | Query optimization, Z-order, caching |
| `10-cross-region-data-mesh.md` | Catalog federation, data contracts, multi-cloud |
| `11-production-deployment.md` | Terraform, K8s, CI/CD, IAM, catalog setup |
| `12-monitoring-alerting.md` | Metrics, dashboards, alerts, cost tracking |
| `13-scaling-billions-performance.md` | File sizing, concurrency, manifest tuning |
| `14-disaster-recovery-reliability.md` | Snapshot restore, replication, corruption |
