# Design Considerations: Implementing Iceberg + S3 in Production

## Table of Contents
1. [File Sizing Strategy](#file-sizing-strategy)
2. [Partition Design](#partition-design)
3. [Compaction Strategy Selection](#compaction-strategy-selection)
4. [Catalog Choice](#catalog-choice)
5. [Table Configuration](#table-configuration)
6. [Cost Optimization](#cost-optimization)
7. [Operational Runbooks](#operational-runbooks)
8. [Monitoring and Alerting](#monitoring-and-alerting)
9. [Migration from Hive](#migration-from-hive)
10. [Multi-Tenancy Design](#multi-tenancy-design)

---

## File Sizing Strategy

### Why File Size Matters

```
┌─────────────────────────────────────────────────────────────────┐
│                    FILE SIZE IMPACT MATRIX                        │
├──────────────────┬──────────────────────┬───────────────────────┤
│                  │  Too Small (<32MB)    │  Too Large (>1GB)     │
├──────────────────┼──────────────────────┼───────────────────────┤
│ Metadata         │ Massive manifest     │ Few entries, fast      │
│                  │ files, slow planning │ planning               │
├──────────────────┼──────────────────────┼───────────────────────┤
│ S3 Requests      │ Many LIST/GET calls  │ Few requests, but      │
│                  │ ($0.0004/1000 GET)   │ large transfers        │
├──────────────────┼──────────────────────┼───────────────────────┤
│ Memory           │ Low per-file, but    │ High per-file, may     │
│                  │ many open handles    │ OOM on small nodes     │
├──────────────────┼──────────────────────┼───────────────────────┤
│ Parallelism      │ High (many splits)   │ Low (few splits),      │
│                  │ but overhead kills   │ underutilized cluster  │
├──────────────────┼──────────────────────┼───────────────────────┤
│ Compaction Cost  │ Frequent compaction  │ Rare compaction, but   │
│                  │ needed              │ expensive when it runs │
└──────────────────┴──────────────────────┴───────────────────────┘
```

### Target File Size by Workload

| Workload Type | Target Size | Rationale |
|--------------|-------------|-----------|
| Streaming ingestion (Flink) | 128MB–256MB | Balance latency vs file count |
| Batch ETL (Spark) | 256MB–512MB | Maximize S3 throughput |
| Frequent point lookups | 64MB–128MB | Minimize bytes scanned per query |
| Analytics (full scans) | 512MB–1GB | Fewer S3 requests for large scans |
| CDC / high-update tables | 128MB | MoR delete files stay small |

### Configuration

```sql
-- Write-side: control target file size
ALTER TABLE events SET TBLPROPERTIES (
  'write.target-file-size-bytes' = '268435456',  -- 256MB (streaming)
  'write.parquet.row-group-size-bytes' = '134217728'  -- 128MB row groups
);

-- Compaction: target output file size
ALTER TABLE events SET TBLPROPERTIES (
  'write.target-file-size-bytes' = '536870912'  -- 512MB (batch tables)
);
```

### The Small File Problem in Practice

```
SCENARIO: Flink job writing 1000 events/sec, checkpointing every 60s

Per checkpoint:  ~60K records → ~2MB per file (way too small!)
Per hour:        60 files × 2MB = 120MB total (60 files to scan)
Per day:         1,440 files × 2MB = 2.88GB (1,440 files to scan)
Per month:       43,200 files → manifest file becomes 50MB+

SOLUTION: Increase checkpoint interval OR use compaction

Option A: Checkpoint every 10 min → ~20MB files (still small, need compaction)
Option B: Checkpoint every 60s + compact hourly → 2MB → 256MB files
Option C: Use write.distribution-mode = 'hash' to concentrate writes
```

### File Size Monitoring Query

```sql
-- Find partitions with small file problems
SELECT 
  partition,
  COUNT(*) as file_count,
  AVG(file_size_in_bytes) / 1048576 as avg_mb,
  MIN(file_size_in_bytes) / 1048576 as min_mb,
  SUM(file_size_in_bytes) / 1073741824 as total_gb
FROM prod.events.files
GROUP BY partition
HAVING AVG(file_size_in_bytes) < 67108864  -- < 64MB average
ORDER BY file_count DESC;
```

---

## Partition Design

### Partitioning Decision Framework

```
┌─────────────────────────────────────────────────────────────┐
│              PARTITION DESIGN DECISION TREE                   │
└─────────────────────────────────────────────────────────────┘

Q1: What is your table size?
  < 10GB total → NO PARTITION (full scan is cheap)
  10GB - 1TB  → 1 partition column (usually time)
  > 1TB       → 1-2 partition columns (time + high-value filter)

Q2: What is the cardinality of your partition key?
  < 100 values       → Use identity transform
  100 - 10,000       → Use identity or bucket
  10,000 - 1M        → Use bucket or truncate
  > 1M               → NEVER use as partition key

Q3: How is data queried?
  Always filtered by date → partition by day/hour
  Always filtered by region → partition by region
  Both equally            → partition by day, bucket by region
  Unpredictable           → z-order sort instead of partition

Q4: How is data written?
  Append-only  → time partition (day/hour/month)
  Heavy updates → fewer partitions (reduces rewrite cost for CoW)
  CDC stream   → day partition + sort by primary key
```

### Hidden Partitioning (Iceberg's Killer Feature)

```sql
-- BAD: Hive-style explicit partitioning
-- Users must know partition structure and include filter
CREATE TABLE events_hive (
  event_id BIGINT,
  event_time TIMESTAMP,
  event_date DATE  -- derived column, data duplication!
) PARTITIONED BY (event_date);

-- GOOD: Iceberg hidden partitioning
-- Users query naturally; Iceberg prunes automatically
CREATE TABLE events (
  event_id BIGINT,
  event_time TIMESTAMP,
  user_id BIGINT,
  event_type STRING
) USING iceberg
PARTITIONED BY (
  days(event_time),       -- daily partition from timestamp
  bucket(16, user_id)     -- 16 buckets for user distribution
);

-- This query AUTOMATICALLY prunes partitions:
SELECT * FROM events 
WHERE event_time > '2026-01-01' AND user_id = 42;
-- Iceberg translates: partition_days >= 20454 AND bucket(user_id) = hash(42) % 16
```

### Partition Transform Reference

| Transform | Input | Output | Best For |
|-----------|-------|--------|----------|
| `identity` | `region` | `region=us-east` | Low-cardinality columns |
| `year(ts)` | `2026-05-28 10:30` | `year=2026` | Multi-year archives |
| `month(ts)` | `2026-05-28 10:30` | `month=2026-05` | Monthly reporting |
| `day(ts)` | `2026-05-28 10:30` | `day=2026-05-28` | Daily event tables |
| `hour(ts)` | `2026-05-28 10:30` | `hour=2026-05-28-10` | High-volume streaming |
| `bucket(N, col)` | `user_id=12345` | `bucket=hash%N` | High-cardinality IDs |
| `truncate(L, col)` | `zip='10045'` | `truncate='100'` | String prefixes |

### Partition Evolution (Zero-Downtime Change)

```sql
-- Table started with monthly partitions (low volume in 2024)
CREATE TABLE events PARTITIONED BY (month(event_time));

-- Volume grew 10x in 2025 — switch to daily without rewriting data
ALTER TABLE events ADD PARTITION FIELD day(event_time);
ALTER TABLE events DROP PARTITION FIELD month(event_time);

-- What happens internally:
-- Spec ID 0: month(event_time) → applies to snapshots before change
-- Spec ID 1: day(event_time)   → applies to snapshots after change
-- Old data files retain their month-level partition metadata
-- New data files use day-level partitions
-- Queries spanning both periods correctly prune using both specs
```

### Anti-Patterns

```
❌ OVER-PARTITIONING
   PARTITIONED BY (year, month, day, hour, region, user_type)
   Result: Millions of tiny partitions, each with 1-2 small files
   
❌ HIGH-CARDINALITY IDENTITY
   PARTITIONED BY (identity(user_id))  -- 100M users = 100M partitions
   
❌ PARTITION ON MUTABLE COLUMN
   PARTITIONED BY (identity(status))   -- Status changes = row moves between partitions
   Each UPDATE requires: delete from old partition + insert into new partition
   
✅ CORRECT APPROACH
   PARTITIONED BY (day(event_time), bucket(32, user_id))
   Sort within partitions by (status, created_at) for scan efficiency
```

---

## Compaction Strategy Selection

### Strategy Comparison

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPACTION STRATEGY MATRIX                         │
├───────────────┬──────────────┬───────────────┬─────────────────────┤
│ Strategy      │ CPU Cost     │ Best For       │ Query Benefit       │
├───────────────┼──────────────┼───────────────┼─────────────────────┤
│ Bin-Pack      │ LOW          │ Combining      │ Fewer S3 requests   │
│               │ (read+write) │ small files    │ (~10x fewer files)  │
├───────────────┼──────────────┼───────────────┼─────────────────────┤
│ Sort          │ MEDIUM       │ Range queries  │ Parquet min/max     │
│               │ (shuffle+    │ on one column  │ pruning (skip 90%+  │
│               │  sort+write) │               │ of row groups)      │
├───────────────┼──────────────┼───────────────┼─────────────────────┤
│ Z-Order       │ HIGH         │ Multi-column   │ Clustering on 2-4   │
│               │ (z-value     │ range queries  │ dimensions at once   │
│               │  compute+    │               │ (skip 70-85% of     │
│               │  sort+write) │               │ row groups)          │
└───────────────┴──────────────┴───────────────┴─────────────────────┘
```

### Decision Matrix

```
START
  │
  ├── Problem: Too many small files?
  │     └── YES → BIN-PACK (cheapest, solves file count)
  │
  ├── Problem: Queries scan too much data?
  │     │
  │     ├── Queries filter on ONE column mostly?
  │     │     └── YES → SORT on that column
  │     │
  │     ├── Queries filter on 2-4 columns equally?
  │     │     └── YES → Z-ORDER on those columns
  │     │
  │     └── Queries are unpredictable?
  │           └── Z-ORDER on top 3-4 query predicates
  │
  └── Problem: Both small files AND slow scans?
        └── SORT or Z-ORDER (implicitly does bin-pack too)
```

### Configuration Examples

```sql
-- Bin-Pack: Just fix small files (cheapest)
CALL system.rewrite_data_files(
  table => 'prod.events',
  strategy => 'binpack',
  options => map(
    'target-file-size-bytes', '536870912',       -- 512MB target
    'min-file-size-bytes', '67108864',           -- Skip files > 64MB
    'max-file-size-bytes', '1073741824',         -- Cap at 1GB
    'min-input-files', '5',                      -- Need at least 5 small files
    'partial-progress.enabled', 'true',          -- Commit progress incrementally
    'partial-progress.max-commits', '10'         -- Max 10 intermediate commits
  )
);

-- Sort: Optimize for time-range queries
CALL system.rewrite_data_files(
  table => 'prod.events',
  strategy => 'sort',
  sort_order => 'event_time ASC NULLS LAST, user_id ASC',
  options => map(
    'target-file-size-bytes', '536870912',
    'min-input-files', '5',
    'rewrite-all', 'false'  -- Only rewrite unsorted files
  )
);

-- Z-Order: Multi-dimensional clustering
CALL system.rewrite_data_files(
  table => 'prod.events',
  strategy => 'sort',
  sort_order => 'zorder(event_time, user_id, event_type)',
  options => map(
    'target-file-size-bytes', '536870912',
    'min-input-files', '5'
  )
);
```

### Compaction Scheduling

```
┌─────────────────────────────────────────────────────────────────┐
│              COMPACTION SCHEDULING STRATEGY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  STREAMING TABLES (Flink ingestion):                             │
│    ├── Bin-pack: Every 1 hour (fix checkpoint small files)       │
│    ├── Sort/Z-Order: Every 24 hours (optimize yesterday's data)  │
│    └── Scope: Only compact partitions with age > 1 hour          │
│                                                                   │
│  BATCH TABLES (Daily ETL):                                       │
│    ├── Bin-pack: After each batch write (if needed)              │
│    ├── Sort/Z-Order: Weekly on hot partitions                    │
│    └── Scope: Only compact partitions written today              │
│                                                                   │
│  HISTORICAL TABLES (Rarely written):                             │
│    ├── Sort/Z-Order: Monthly or on-demand                        │
│    └── Scope: Full table rewrite acceptable                      │
│                                                                   │
│  TIMING:                                                         │
│    ├── Run during off-peak hours (2AM-6AM)                       │
│    ├── Never compact during peak query hours                     │
│    └── Stagger across tables to avoid S3 throttling              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Catalog Choice

### Catalog Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CATALOG COMPARISON MATRIX                             │
├────────────────┬──────────────┬─────────────┬──────────┬───────────────────┤
│ Catalog        │ Managed By   │ Multi-Engine│ Branching│ Best For           │
├────────────────┼──────────────┼─────────────┼──────────┼───────────────────┤
│ AWS Glue       │ AWS          │ ✅ Good     │ ❌       │ AWS-native teams   │
│                │              │ (Spark,     │          │ using EMR, Athena, │
│                │              │  Athena,    │          │ Redshift Spectrum  │
│                │              │  Trino)     │          │                    │
├────────────────┼──────────────┼─────────────┼──────────┼───────────────────┤
│ Hive Metastore │ Self-hosted  │ ✅ Broad    │ ❌       │ Existing Hadoop    │
│ (HMS)          │ (MySQL/PG    │ (legacy     │          │ infrastructure,    │
│                │  backend)    │  compatible)│          │ on-prem deployments│
├────────────────┼──────────────┼─────────────┼──────────┼───────────────────┤
│ Nessie         │ Self-hosted  │ ✅ Good     │ ✅ Git-  │ Teams wanting      │
│                │ (lightweight │ (Spark,     │ like     │ data versioning,   │
│                │  Java svc)   │  Flink,     │ branches │ CI/CD for data,    │
│                │              │  Trino)     │          │ multi-table txns   │
├────────────────┼──────────────┼─────────────┼──────────┼───────────────────┤
│ REST Catalog   │ Any impl     │ ✅ Best     │ Depends  │ Multi-cloud,       │
│ (Iceberg spec) │ (Tabular,   │ (standard   │ on impl  │ vendor-neutral,    │
│                │  Polaris,    │  protocol)  │          │ custom access      │
│                │  custom)     │             │          │ control            │
├────────────────┼──────────────┼─────────────┼──────────┼───────────────────┤
│ Unity Catalog  │ Databricks   │ ⚠️ Limited  │ ❌       │ Databricks-first   │
│                │              │ (Databricks │          │ with some external │
│                │              │  focused)   │          │ engine support     │
└────────────────┴──────────────┴─────────────┴──────────┴───────────────────┘
```

### Detailed Tradeoffs

#### AWS Glue Catalog

```
PROS:
  ✅ Zero operational overhead (serverless)
  ✅ Native integration with EMR, Athena, Redshift Spectrum, Lake Formation
  ✅ Fine-grained access control via Lake Formation
  ✅ Cross-account sharing built-in
  ✅ 1M free API calls/month, then $1 per 100K requests

CONS:
  ❌ AWS lock-in (no multi-cloud)
  ❌ 100 databases, 200K tables per account (soft limits, can increase)
  ❌ API throttling under heavy concurrent writes (10 txns/sec per table)
  ❌ No branching or multi-table transactions
  ❌ Schema registry is eventually consistent (rare but possible stale reads)

WHEN TO CHOOSE:
  → AWS-only deployments
  → Teams already using Lake Formation for governance
  → Want zero catalog operations overhead
  → < 50 concurrent writers per table
```

#### Nessie (Project Nessie)

```
PROS:
  ✅ Git-like branching: create branches, merge, cherry-pick for data
  ✅ Multi-table transactions (atomic commits across tables)
  ✅ Tag snapshots for reproducibility ("tag the data used for model v2.3")
  ✅ Lightweight (single Java process, ~200MB RAM for small deployments)
  ✅ Open source (Apache 2.0), no vendor lock-in

CONS:
  ❌ Self-hosted: you manage availability, backups, upgrades
  ❌ Smaller community than Glue/HMS (fewer battle-tested production stories)
  ❌ Backend storage choices (DynamoDB, MongoDB, PostgreSQL, RocksDB) each have tradeoffs
  ❌ Merge conflicts on concurrent branch modifications require resolution

WHEN TO CHOOSE:
  → Data teams wanting CI/CD workflows (test on branch, merge to main)
  → Need atomic multi-table commits (e.g., fact + dimension tables together)
  → Reproducible ML pipelines (tag training data at exact version)
  → Teams comfortable with operating a small Java service

ARCHITECTURE:
  ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
  │ Spark/Flink │────▶│ Nessie Server│────▶│ Backend Store   │
  │ (catalog    │     │ (REST API)   │     │ (DynamoDB/PG/   │
  │  client)    │     │              │     │  MongoDB)        │
  └─────────────┘     └──────────────┘     └─────────────────┘
                            │
                      ┌─────┴─────┐
                      │ Branches: │
                      │  main     │──▶ production tables
                      │  dev      │──▶ development testing
                      │  ml/v2.3  │──▶ frozen training data
                      └───────────┘
```

#### REST Catalog (Iceberg Standard)

```
PROS:
  ✅ Vendor-neutral standard protocol (defined in Iceberg spec)
  ✅ Any engine that speaks Iceberg can use it (maximum portability)
  ✅ Custom access control (implement your own auth layer)
  ✅ Multiple implementations: Apache Polaris, Tabular, custom
  ✅ Server-side retry and conflict resolution possible

CONS:
  ❌ Need to host or buy an implementation
  ❌ Newer standard — some engines have partial support
  ❌ Performance depends on implementation quality
  ❌ No standardized access control (each impl differs)

WHEN TO CHOOSE:
  → Multi-cloud or hybrid deployments
  → Want to avoid vendor lock-in at the catalog layer
  → Need custom authorization logic
  → Building a data platform product
```

### Catalog Configuration Examples

```python
# AWS Glue Catalog (Spark)
spark.conf.set("spark.sql.catalog.prod", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.prod.catalog-impl", 
               "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.catalog.prod.warehouse", "s3://my-warehouse/")
spark.conf.set("spark.sql.catalog.prod.io-impl", 
               "org.apache.iceberg.aws.s3.S3FileIO")

# Nessie Catalog (Spark)
spark.conf.set("spark.sql.catalog.nessie", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.nessie.catalog-impl", 
               "org.apache.iceberg.nessie.NessieCatalog")
spark.conf.set("spark.sql.catalog.nessie.uri", "http://nessie:19120/api/v1")
spark.conf.set("spark.sql.catalog.nessie.ref", "main")
spark.conf.set("spark.sql.catalog.nessie.warehouse", "s3://my-warehouse/")

# REST Catalog (Spark)
spark.conf.set("spark.sql.catalog.rest", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.rest.type", "rest")
spark.conf.set("spark.sql.catalog.rest.uri", "https://catalog.mycompany.com")
spark.conf.set("spark.sql.catalog.rest.token", "${CATALOG_TOKEN}")
spark.conf.set("spark.sql.catalog.rest.warehouse", "s3://my-warehouse/")
```

---

## Table Configuration

### Essential Properties by Workload

```sql
-- ═══════════════════════════════════════════════════════════════
-- STREAMING TABLE (Flink CDC ingestion, high write throughput)
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE prod.events SET TBLPROPERTIES (
  -- Write properties
  'write.format.default' = 'parquet',
  'write.target-file-size-bytes' = '134217728',      -- 128MB (smaller for streaming)
  'write.parquet.compression-codec' = 'zstd',        -- Best compression ratio
  'write.parquet.compression-level' = '3',           -- Balance speed vs ratio
  'write.distribution-mode' = 'hash',                -- Cluster writes by partition
  'write.metadata.compression-codec' = 'gzip',       -- Compress metadata files
  
  -- Update/Delete properties (MoR for streaming updates)
  'write.update.mode' = 'merge-on-read',
  'write.delete.mode' = 'merge-on-read',
  'write.merge.mode' = 'merge-on-read',
  
  -- Snapshot management
  'history.expire.max-snapshot-age-ms' = '259200000', -- 3 days retention
  'history.expire.min-snapshots-to-keep' = '10',
  
  -- Commit retry (important for concurrent Flink writers)
  'commit.retry.num-retries' = '10',
  'commit.retry.min-wait-ms' = '100',
  'commit.retry.max-wait-ms' = '60000'
);

-- ═══════════════════════════════════════════════════════════════
-- BATCH ANALYTICS TABLE (Spark ETL, optimized for read)
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE prod.fact_orders SET TBLPROPERTIES (
  -- Write properties
  'write.format.default' = 'parquet',
  'write.target-file-size-bytes' = '536870912',      -- 512MB (larger for batch)
  'write.parquet.compression-codec' = 'zstd',
  'write.parquet.compression-level' = '6',           -- Higher compression for cold data
  'write.parquet.row-group-size-bytes' = '67108864', -- 64MB row groups
  'write.parquet.page-size-bytes' = '1048576',       -- 1MB pages
  'write.parquet.dict-size-bytes' = '2097152',       -- 2MB dictionary
  'write.distribution-mode' = 'range',               -- Sort-ordered writes
  
  -- Update/Delete properties (CoW for batch — no read penalty)
  'write.update.mode' = 'copy-on-write',
  'write.delete.mode' = 'copy-on-write',
  
  -- Read optimization
  'read.split.target-size' = '268435456',            -- 256MB splits
  'read.parquet.vectorization.enabled' = 'true',
  
  -- Longer retention for analytics
  'history.expire.max-snapshot-age-ms' = '604800000', -- 7 days
  'history.expire.min-snapshots-to-keep' = '5'
);

-- ═══════════════════════════════════════════════════════════════
-- HIGH-UPDATE TABLE (Frequent UPSERTs, compliance deletes)
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE prod.user_profiles SET TBLPROPERTIES (
  'write.format.default' = 'parquet',
  'write.target-file-size-bytes' = '134217728',      -- 128MB
  'write.parquet.compression-codec' = 'zstd',
  'write.distribution-mode' = 'hash',
  
  -- MoR for updates (fast writes, background compaction reconciles)
  'write.update.mode' = 'merge-on-read',
  'write.delete.mode' = 'merge-on-read',
  
  -- Delete file thresholds (trigger compaction when too many delete files)
  'write.delete.distribution-mode' = 'hash',
  
  -- Short retention (updates create many snapshots)
  'history.expire.max-snapshot-age-ms' = '86400000',  -- 1 day
  'history.expire.min-snapshots-to-keep' = '3'
);
```

### Sort Order Configuration

```sql
-- Sort orders improve query performance via Parquet min/max stats
-- Iceberg tracks sort order in metadata — engines use it for pruning

-- Time-series table: sort by time for range queries
ALTER TABLE prod.events WRITE ORDERED BY (
  event_time ASC NULLS LAST,
  user_id ASC NULLS LAST
);

-- Dimension table: sort by primary key for point lookups
ALTER TABLE prod.users WRITE ORDERED BY (
  user_id ASC NULLS LAST
);

-- Multi-use table: z-order for multi-dimensional queries
-- (Z-order is applied during compaction, not during writes)
```

---

## Cost Optimization

### S3 Cost Breakdown for Iceberg

```
┌─────────────────────────────────────────────────────────────────────┐
│                    S3 COST MODEL FOR ICEBERG                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  STORAGE (per GB/month):                                             │
│    S3 Standard:           $0.023/GB                                   │
│    S3 Infrequent Access:  $0.0125/GB  (45% savings)                  │
│    S3 Glacier IR:         $0.004/GB   (83% savings)                  │
│    S3 Glacier Deep:       $0.00099/GB (96% savings)                  │
│                                                                       │
│  REQUESTS (dominant cost for small files!):                           │
│    PUT/POST:  $0.005 per 1,000 requests                              │
│    GET:       $0.0004 per 1,000 requests                             │
│    LIST:      $0.005 per 1,000 requests                              │
│                                                                       │
│  EXAMPLE: 1TB table, 10,000 files (100MB avg)                        │
│    Storage:   1024 GB × $0.023 = $23.55/month                        │
│    Daily scan: 10 LIST + 10,000 GET = $0.005 + $4.00 = $4.005/query  │
│    Daily 10 queries: $40.05/day = $1,201/month                       │
│                                                                       │
│  SAME TABLE, 2,000 files (512MB avg) after compaction:               │
│    Storage:   1024 GB × $0.023 = $23.55/month (same)                 │
│    Daily scan: 10 LIST + 2,000 GET = $0.005 + $0.80 = $0.805/query   │
│    Daily 10 queries: $8.05/day = $241/month                          │
│                                                                       │
│  SAVINGS FROM COMPACTION: $960/month (80% reduction in request cost) │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Cost Optimization Strategies

#### 1. Metadata Overhead Reduction

```sql
-- Problem: Each snapshot adds metadata files to S3
-- A streaming table with 60s checkpoints = 1,440 snapshots/day
-- Each snapshot: 1 metadata file + 1 manifest list + N manifest files

-- Solution: Expire snapshots aggressively for streaming tables
CALL system.expire_snapshots(
  table => 'prod.events',
  older_than => TIMESTAMP '2026-05-27 00:00:00',
  retain_last => 5
);

-- Solution: Rewrite manifest files to reduce their count
CALL system.rewrite_manifests('prod.events');
-- Combines many small manifests into fewer large ones
-- Reduces LIST calls during query planning
```

#### 2. Storage Tiering with S3 Lifecycle

```json
{
  "Rules": [
    {
      "ID": "iceberg-data-tiering",
      "Filter": { "Prefix": "warehouse/prod/events/data/" },
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER_IR"
        },
        {
          "Days": 365,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ]
    },
    {
      "ID": "iceberg-metadata-keep-standard",
      "Filter": { "Prefix": "warehouse/prod/events/metadata/" },
      "Status": "Enabled",
      "Comment": "NEVER tier metadata — must be fast-accessible for queries"
    }
  ]
}
```

**Critical Rule: NEVER apply lifecycle rules to metadata files.** Metadata must remain in S3 Standard for fast query planning. Only tier data files.

#### 3. Partition Pruning ROI

```
SCENARIO: 1TB table, 365 daily partitions

WITHOUT partition pruning (full scan):
  Files to read:    50,000
  GET requests:     50,000 × $0.0004/1000 = $20.00
  Data transferred: 1,024 GB (if no predicate pushdown)

WITH partition pruning (query one day):
  Files to read:    ~137 (50,000 / 365)
  GET requests:     137 × $0.0004/1000 = $0.06
  Data transferred: ~2.8 GB

COST REDUCTION: 99.7% fewer requests per query
```

#### 4. Avoiding Unnecessary Copies

```sql
-- BAD: Full table copy for downstream
CREATE TABLE prod.events_copy AS SELECT * FROM prod.events;
-- Cost: Doubles storage (1TB → 2TB), all data rewritten

-- GOOD: Use Iceberg branches (zero-copy reference)
ALTER TABLE prod.events CREATE BRANCH reporting_freeze
  AS OF VERSION 12345;
-- Cost: Only metadata (few KB), no data copied

-- GOOD: Use views for transformed access
CREATE VIEW prod.events_clean AS
SELECT * FROM prod.events WHERE is_valid = true;
-- Cost: Zero additional storage
```

### Monthly Cost Estimation Template

```
┌──────────────────────────────────────────────────────────┐
│         MONTHLY COST ESTIMATION WORKSHEET                 │
├──────────────────────────────────────────────────────────┤
│                                                            │
│ TABLE: _______________  SIZE: _______ TB                  │
│                                                            │
│ STORAGE:                                                   │
│   Hot data (< 30d):    _____ GB × $0.023  = $________    │
│   Warm data (30-90d):  _____ GB × $0.0125 = $________    │
│   Cold data (90d-1y):  _____ GB × $0.004  = $________    │
│   Archive (> 1y):      _____ GB × $0.001  = $________    │
│   Metadata files:      _____ GB × $0.023  = $________    │
│                                     TOTAL:   $________    │
│                                                            │
│ REQUESTS (per month):                                      │
│   Writes (PUT):   _______ × $5/million   = $________     │
│   Reads (GET):    _______ × $0.40/million = $________    │
│   List (LIST):    _______ × $5/million    = $________    │
│                                     TOTAL:   $________    │
│                                                            │
│ COMPUTE (compaction, maintenance):                         │
│   EMR/Spark hours: ______ × $______/hr    = $________    │
│                                                            │
│ ══════════════════════════════════════════════════════     │
│                            GRAND TOTAL:      $________    │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

---

## Operational Runbooks

### Runbook 1: Compaction Pipeline

```python
"""
Daily Compaction Pipeline
Schedule: 2:00 AM UTC (off-peak)
Duration: ~30-60 minutes for 1TB table
"""

from pyspark.sql import SparkSession
from datetime import datetime, timedelta

spark = SparkSession.builder \
    .config("spark.sql.catalog.prod", "org.apache.iceberg.spark.SparkCatalog") \
    .getOrCreate()

TABLES = [
    {"name": "prod.events", "strategy": "sort", 
     "sort_order": "event_time ASC", "partition_filter": "day >= current_date - 7"},
    {"name": "prod.user_profiles", "strategy": "binpack", 
     "sort_order": None, "partition_filter": None},
    {"name": "prod.orders", "strategy": "sort",
     "sort_order": "zorder(order_date, customer_id)", "partition_filter": "order_date >= current_date - 30"},
]

for table in TABLES:
    print(f"[{datetime.now()}] Compacting {table['name']}...")
    
    # Step 1: Check if compaction is needed
    files_df = spark.sql(f"""
        SELECT COUNT(*) as file_count, 
               AVG(file_size_in_bytes) as avg_size
        FROM {table['name']}.files
        {"WHERE " + table['partition_filter'] if table['partition_filter'] else ""}
    """)
    
    stats = files_df.first()
    if stats.avg_size > 400_000_000:  # > 400MB average = already good
        print(f"  Skipping: avg file size {stats.avg_size/1e6:.0f}MB (healthy)")
        continue
    
    # Step 2: Run compaction
    options = {
        'target-file-size-bytes': '536870912',
        'min-input-files': '5',
        'partial-progress.enabled': 'true',
        'partial-progress.max-commits': '10',
    }
    
    if table['partition_filter']:
        options['filter'] = table['partition_filter']
    
    options_str = ", ".join(f"'{k}', '{v}'" for k, v in options.items())
    
    if table['sort_order']:
        spark.sql(f"""
            CALL system.rewrite_data_files(
                table => '{table['name']}',
                strategy => '{table['strategy']}',
                sort_order => '{table['sort_order']}',
                options => map({options_str})
            )
        """)
    else:
        spark.sql(f"""
            CALL system.rewrite_data_files(
                table => '{table['name']}',
                strategy => '{table['strategy']}',
                options => map({options_str})
            )
        """)
    
    print(f"  Compaction complete for {table['name']}")

# Step 3: Expire old snapshots (after compaction creates new ones)
for table in TABLES:
    expire_ts = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    spark.sql(f"""
        CALL system.expire_snapshots(
            table => '{table['name']}',
            older_than => TIMESTAMP '{expire_ts}',
            retain_last => 5
        )
    """)

# Step 4: Remove orphan files (files not referenced by any snapshot)
for table in TABLES:
    orphan_ts = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    spark.sql(f"""
        CALL system.remove_orphan_files(
            table => '{table['name']}',
            older_than => TIMESTAMP '{orphan_ts}'
        )
    """)

print(f"[{datetime.now()}] All maintenance complete.")
```

### Runbook 2: Emergency Rollback

```sql
-- SCENARIO: Bad data was written to production table
-- GOAL: Rollback to known-good state without data loss

-- Step 1: Identify the good snapshot
SELECT snapshot_id, committed_at, operation, summary
FROM prod.events.snapshots
ORDER BY committed_at DESC
LIMIT 20;

-- Step 2: Verify the snapshot has correct data
SELECT COUNT(*), MIN(event_time), MAX(event_time)
FROM prod.events VERSION AS OF 8834298340283;

-- Step 3: Rollback (sets current snapshot pointer, does NOT delete data)
CALL system.rollback_to_snapshot('prod.events', 8834298340283);

-- Step 4: Verify current state is correct
SELECT COUNT(*), MIN(event_time), MAX(event_time)
FROM prod.events;

-- Step 5: The "bad" snapshots still exist until expired
-- To prevent accidental use, expire them immediately:
CALL system.expire_snapshots(
  table => 'prod.events',
  snapshot_ids => ARRAY(8834298340284, 8834298340285)
);

-- ALTERNATIVE: Cherry-pick rollback (undo ONE bad commit, keep later good ones)
CALL system.rollback_to_snapshot('prod.events', 8834298340283);
-- Then re-apply good changes from snapshots after the bad one
-- (This requires application-level replay logic)
```

### Runbook 3: Schema Migration

```sql
-- SCENARIO: Need to add a column, rename another, and change a type
-- Iceberg handles all of these WITHOUT rewriting data

-- Step 1: Add new column (instant, metadata-only)
ALTER TABLE prod.events ADD COLUMN device_type STRING AFTER user_agent;

-- Step 2: Rename column (instant, metadata-only — tracked by column ID)
ALTER TABLE prod.events RENAME COLUMN user_agent TO raw_user_agent;

-- Step 3: Widen type (instant for int→bigint, metadata-only)
ALTER TABLE prod.events ALTER COLUMN event_count TYPE BIGINT;

-- Step 4: Type promotion (supported promotions):
--   int → bigint
--   float → double
--   decimal(P,S) → decimal(P',S) where P' > P

-- UNSUPPORTED type changes require a migration:
-- string → int, timestamp → date, etc.
-- For these, add new column + backfill + drop old:
ALTER TABLE prod.events ADD COLUMN parsed_amount DECIMAL(10,2);
-- Backfill in Spark:
-- spark.sql("UPDATE prod.events SET parsed_amount = CAST(amount_str AS DECIMAL(10,2))")
ALTER TABLE prod.events DROP COLUMN amount_str;
```

---

## Monitoring and Alerting

### Key Metrics to Track

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ICEBERG HEALTH METRICS                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  FILE HEALTH:                                                         │
│    • files_per_partition:     Target < 500, Alert > 1000             │
│    • avg_file_size_mb:        Target 128-512, Alert < 32 or > 1024   │
│    • total_delete_files:      Target < 100, Alert > 500              │
│    • delete_file_ratio:       Target < 10%, Alert > 30%              │
│                                                                       │
│  METADATA HEALTH:                                                     │
│    • manifest_file_count:     Target < 100, Alert > 500              │
│    • manifest_list_size_mb:   Target < 10, Alert > 50                │
│    • snapshot_count:          Target < 50, Alert > 200               │
│    • metadata_file_size_mb:   Target < 5, Alert > 20                 │
│                                                                       │
│  OPERATIONAL:                                                         │
│    • commit_latency_ms:       Target < 2000, Alert > 10000           │
│    • commit_retry_count:      Target 0, Alert > 5 per commit        │
│    • compaction_duration_min: Target < 60, Alert > 180               │
│    • orphan_files_count:      Target 0, Alert > 100                  │
│                                                                       │
│  QUERY PERFORMANCE:                                                   │
│    • planning_time_ms:        Target < 5000, Alert > 30000           │
│    • files_scanned_ratio:     Target < 20%, Alert > 50%              │
│    • data_scanned_gb:         Monitor trend, alert on 3x spike       │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Monitoring Queries

```sql
-- Dashboard Query 1: Table Health Overview
SELECT 
  'file_count' as metric, COUNT(*)::VARCHAR as value 
  FROM prod.events.files
UNION ALL
SELECT 
  'avg_file_size_mb', ROUND(AVG(file_size_in_bytes)/1048576, 1)::VARCHAR
  FROM prod.events.files
UNION ALL
SELECT
  'total_size_gb', ROUND(SUM(file_size_in_bytes)/1073741824.0, 2)::VARCHAR
  FROM prod.events.files
UNION ALL
SELECT
  'snapshot_count', COUNT(*)::VARCHAR
  FROM prod.events.snapshots
UNION ALL
SELECT
  'manifest_count', COUNT(*)::VARCHAR
  FROM prod.events.manifests;

-- Dashboard Query 2: Partition Skew Detection
SELECT 
  partition,
  COUNT(*) as files,
  SUM(file_size_in_bytes) / 1073741824 as size_gb,
  SUM(record_count) as records
FROM prod.events.files
GROUP BY partition
ORDER BY files DESC
LIMIT 20;

-- Dashboard Query 3: Write Activity (commit rate)
SELECT 
  DATE_TRUNC('hour', committed_at) as hour,
  COUNT(*) as commits,
  SUM(CAST(summary['added-data-files'] AS INT)) as files_added,
  SUM(CAST(summary['added-records'] AS BIGINT)) as records_added
FROM prod.events.snapshots
WHERE committed_at > current_timestamp - INTERVAL '24' HOUR
GROUP BY 1
ORDER BY 1;
```

### Alerting Rules (Prometheus/Datadog Format)

```yaml
# Prometheus alerting rules for Iceberg table health
groups:
  - name: iceberg_table_health
    interval: 5m
    rules:
      - alert: IcebergSmallFileProblem
        expr: iceberg_table_avg_file_size_bytes < 33554432  # < 32MB
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Table {{ $labels.table }} has small file problem"
          description: "Average file size is {{ $value | humanize1024 }}. Run compaction."

      - alert: IcebergTooManyDeleteFiles
        expr: iceberg_table_delete_file_count > 500
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "Table {{ $labels.table }} has excessive delete files"
          description: "{{ $value }} delete files. Read performance degraded. Run compaction immediately."

      - alert: IcebergCommitConflicts
        expr: rate(iceberg_commit_retries_total[5m]) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High commit conflict rate on {{ $labels.table }}"
          description: "{{ $value }} retries/sec. Check for concurrent writers fighting."

      - alert: IcebergSnapshotAccumulation
        expr: iceberg_table_snapshot_count > 200
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Snapshot accumulation on {{ $labels.table }}"
          description: "{{ $value }} snapshots. Expire old snapshots to reduce metadata size."

      - alert: IcebergMetadataTooLarge
        expr: iceberg_table_metadata_size_bytes > 20971520  # > 20MB
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Large metadata file for {{ $labels.table }}"
          description: "Metadata is {{ $value | humanize1024 }}. Query planning will be slow."
```

---

## Migration from Hive

### Migration Strategy Comparison

```
┌─────────────────────────────────────────────────────────────────────┐
│                 HIVE → ICEBERG MIGRATION STRATEGIES                   │
├────────────────────┬─────────────────────────┬──────────────────────┤
│ Strategy           │ Downtime                 │ Best For             │
├────────────────────┼─────────────────────────┼──────────────────────┤
│ In-Place Migration │ Minutes (metadata swap)  │ Tables with existing │
│ (migrate proc)     │                         │ Parquet files on S3  │
├────────────────────┼─────────────────────────┼──────────────────────┤
│ Shadow Migration   │ Zero (dual-write period) │ Critical tables that │
│ (CTAS + cutover)   │                         │ cannot have downtime │
├────────────────────┼─────────────────────────┼──────────────────────┤
│ Incremental        │ Zero (gradual)          │ Very large tables    │
│ (partition-by-     │                         │ (100TB+) where full  │
│  partition)        │                         │ rewrite is too costly│
└────────────────────┴─────────────────────────┴──────────────────────┘
```

### In-Place Migration (Recommended for Parquet tables)

```sql
-- PREREQUISITES:
-- 1. Table must be in Parquet format (not ORC, Avro)
-- 2. Table must be external (not managed)
-- 3. Hive Metastore must be accessible

-- Step 1: Verify table is compatible
DESCRIBE FORMATTED hive_db.events;
-- Check: InputFormat = MapredParquetInputFormat
-- Check: Location = s3://bucket/warehouse/events

-- Step 2: Run in-place migration (Spark)
CALL system.migrate('hive_db.events');

-- What this does:
-- ├── Reads Hive partition metadata
-- ├── Creates Iceberg metadata files pointing to EXISTING Parquet files
-- ├── Registers table in Iceberg catalog
-- └── Does NOT copy or move any data files!

-- Step 3: Verify
SELECT COUNT(*) FROM prod.events;  -- Should match Hive count
SELECT * FROM prod.events.snapshots;  -- Should show initial snapshot

-- Step 4: Add snapshot (captures table as-is for time travel baseline)
-- The migrate procedure already creates an initial snapshot

-- ROLLBACK if needed:
CALL system.rollback_to_snapshot('prod.events', <original_snapshot_id>);
-- Or drop Iceberg metadata and re-register as Hive table
```

### Shadow Migration (Zero-Downtime)

```
┌─────────────────────────────────────────────────────────────────┐
│              SHADOW MIGRATION TIMELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Phase 1: DUAL-WRITE (1-2 weeks)                                 │
│  ┌──────────────┐     ┌─────────────┐                           │
│  │ Write Pipeline│────▶│ Hive Table  │ (primary)                 │
│  │              │────▶│ Iceberg Table│ (shadow, validating)      │
│  └──────────────┘     └─────────────┘                           │
│                                                                   │
│  Phase 2: VALIDATE (3-5 days)                                    │
│  • Row count comparison (daily)                                   │
│  • Sample data diff (daily)                                       │
│  • Query result comparison (key reports)                          │
│  • Performance benchmarking (Iceberg queries)                     │
│                                                                   │
│  Phase 3: CUTOVER (minutes)                                      │
│  ┌──────────────┐     ┌─────────────┐                           │
│  │ Write Pipeline│────▶│ Iceberg Table│ (primary)                │
│  │              │────▶│ Hive Table   │ (shadow, winding down)    │
│  └──────────────┘     └─────────────┘                           │
│  • Switch read queries to Iceberg                                 │
│  • Keep Hive writes for 1 week (rollback safety)                 │
│                                                                   │
│  Phase 4: CLEANUP (after 1 week)                                 │
│  • Stop Hive writes                                               │
│  • Archive Hive table metadata                                    │
│  • Remove dual-write logic                                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Migration Validation Script

```python
"""
Migration Validation: Compare Hive vs Iceberg table contents
Run daily during dual-write phase
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, sum as spark_sum, abs as spark_abs

spark = SparkSession.builder.getOrCreate()

HIVE_TABLE = "hive_db.events"
ICEBERG_TABLE = "prod.events"
PARTITION_COL = "event_date"
TOLERANCE_PERCENT = 0.01  # 0.01% tolerance for eventual consistency

# Test 1: Row count comparison
hive_count = spark.table(HIVE_TABLE).count()
iceberg_count = spark.table(ICEBERG_TABLE).count()
count_diff = abs(hive_count - iceberg_count)
count_pct = count_diff / max(hive_count, 1) * 100

assert count_pct < TOLERANCE_PERCENT, \
    f"Row count mismatch: Hive={hive_count}, Iceberg={iceberg_count}, diff={count_pct:.4f}%"

# Test 2: Per-partition count comparison
hive_parts = spark.table(HIVE_TABLE) \
    .groupBy(PARTITION_COL) \
    .agg(count("*").alias("hive_count"))

iceberg_parts = spark.table(ICEBERG_TABLE) \
    .groupBy(PARTITION_COL) \
    .agg(count("*").alias("iceberg_count"))

comparison = hive_parts.join(iceberg_parts, PARTITION_COL, "full_outer") \
    .withColumn("diff", spark_abs(col("hive_count") - col("iceberg_count")))

mismatches = comparison.filter(col("diff") > 0).collect()
if mismatches:
    for row in mismatches[:10]:
        print(f"  MISMATCH: {row[PARTITION_COL]} → Hive={row.hive_count}, Iceberg={row.iceberg_count}")
    assert False, f"{len(mismatches)} partitions have count mismatches"

# Test 3: Sample data comparison (random 1000 rows)
sample = spark.table(HIVE_TABLE).sample(fraction=0.001).limit(1000)
sample_keys = [row.event_id for row in sample.select("event_id").collect()]

hive_sample = spark.table(HIVE_TABLE).filter(col("event_id").isin(sample_keys))
iceberg_sample = spark.table(ICEBERG_TABLE).filter(col("event_id").isin(sample_keys))

# Compare schemas
assert hive_sample.schema == iceberg_sample.schema, "Schema mismatch!"

# Compare data
diff = hive_sample.exceptAll(iceberg_sample)
assert diff.count() == 0, f"Data mismatch: {diff.count()} rows differ"

print(f"✅ Validation passed: {hive_count} rows, {comparison.count()} partitions match")
```

### Common Migration Pitfalls

```
┌─────────────────────────────────────────────────────────────────┐
│                    MIGRATION PITFALLS                             │
├──────────────────────────────────┬──────────────────────────────┤
│ Pitfall                          │ Solution                      │
├──────────────────────────────────┼──────────────────────────────┤
│ Hive table uses ORC format       │ Must CTAS to Parquet first,  │
│                                  │ then migrate to Iceberg       │
├──────────────────────────────────┼──────────────────────────────┤
│ Hive partition values have       │ Clean up before migration     │
│ special characters (%20, etc)    │ or use CTAS approach          │
├──────────────────────────────────┼──────────────────────────────┤
│ Downstream jobs use Hive DDL     │ Update all consumers before   │
│ (MSCK REPAIR, ADD PARTITION)     │ cutover (Iceberg auto-manages)│
├──────────────────────────────────┼──────────────────────────────┤
│ Hive stats used by optimizer     │ Run ANALYZE TABLE after       │
│                                  │ migration for engine stats    │
├──────────────────────────────────┼──────────────────────────────┤
│ Custom SerDe in Hive             │ Cannot in-place migrate;      │
│                                  │ must CTAS with standard format│
├──────────────────────────────────┼──────────────────────────────┤
│ Bucketed Hive tables             │ Iceberg uses its own bucket   │
│                                  │ transform; re-partition needed│
├──────────────────────────────────┼──────────────────────────────┤
│ Hive ACID tables (managed)       │ Export to external Parquet    │
│                                  │ first, then migrate           │
└──────────────────────────────────┴──────────────────────────────┘
```

---

## Multi-Tenancy Design

### Isolation Strategies

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MULTI-TENANCY MODELS                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  MODEL 1: SEPARATE TABLES (Strongest isolation)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │ tenant_a.   │  │ tenant_b.   │  │ tenant_c.   │                │
│  │ events      │  │ events      │  │ events      │                │
│  └─────────────┘  └─────────────┘  └─────────────┘                │
│  Pros: Full isolation, independent schema evolution                  │
│  Cons: Operational overhead (N tables × maintenance jobs)            │
│  Best for: < 50 tenants, different SLAs per tenant                  │
│                                                                       │
│  MODEL 2: PARTITIONED TABLE (Balance of isolation + simplicity)      │
│  ┌─────────────────────────────────────────────────┐                │
│  │              shared.events                        │                │
│  │  PARTITIONED BY (identity(tenant_id), day(ts))   │                │
│  └─────────────────────────────────────────────────┘                │
│  Pros: Single maintenance pipeline, simple queries                   │
│  Cons: Noisy neighbor risk, shared schema                            │
│  Best for: 50-10,000 tenants, similar workloads                     │
│                                                                       │
│  MODEL 3: SEPARATE NAMESPACES (Catalog-level isolation)              │
│  ┌─────────────────────────────────────────┐                        │
│  │ Catalog                                  │                        │
│  │  ├── namespace: tenant_a                 │                        │
│  │  │     └── events, users, orders         │                        │
│  │  ├── namespace: tenant_b                 │                        │
│  │  │     └── events, users, orders         │                        │
│  │  └── namespace: shared                   │                        │
│  │        └── reference_data                │                        │
│  └─────────────────────────────────────────┘                        │
│  Pros: Logical isolation, per-namespace access control               │
│  Cons: Some catalog overhead per namespace                           │
│  Best for: Multi-team platform, compliance requirements              │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Access Control Patterns

```sql
-- AWS Lake Formation: Column-level and row-level security
-- Grant tenant_a read access to only their partition
GRANT SELECT ON TABLE prod.events 
  TO ROLE tenant_a_reader
  WITH ROW FILTER (tenant_id = 'tenant_a');

-- Nessie: Branch-level isolation
-- Each tenant gets their own branch view
-- Main branch holds the shared truth
ALTER TABLE events CREATE BRANCH tenant_a_view AS OF main;
-- Tenant A only sees their branch (read-only)

-- REST Catalog: Custom authorization in your catalog server
-- Implement per-tenant namespace visibility in your REST catalog middleware
```

---

## Summary: Production Readiness Checklist

```
┌─────────────────────────────────────────────────────────────────┐
│           ICEBERG PRODUCTION READINESS CHECKLIST                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ □ FILE SIZING                                                     │
│   □ Target file size configured (128-512MB per workload)         │
│   □ Small file detection query scheduled                          │
│   □ Compaction pipeline running on schedule                       │
│                                                                   │
│ □ PARTITION DESIGN                                                │
│   □ Partition keys match primary query patterns                   │
│   □ Partition cardinality < 10,000 per table                     │
│   □ Hidden partitioning used (not Hive-style)                    │
│                                                                   │
│ □ CATALOG                                                         │
│   □ Catalog chosen and deployed                                   │
│   □ Access control configured per table/namespace                 │
│   □ Catalog HA tested (failover scenario)                        │
│                                                                   │
│ □ MAINTENANCE                                                     │
│   □ Snapshot expiration scheduled (daily)                         │
│   □ Orphan file removal scheduled (weekly)                        │
│   □ Manifest rewrite scheduled (weekly)                           │
│   □ Compaction scheduled (per-table cadence)                     │
│                                                                   │
│ □ MONITORING                                                      │
│   □ File count and size metrics tracked                           │
│   □ Commit latency and conflict rate tracked                     │
│   □ Query planning time tracked                                   │
│   □ Alerts configured for degradation signals                    │
│                                                                   │
│ □ COST                                                            │
│   □ S3 lifecycle rules on DATA files (not metadata!)             │
│   □ Request cost baseline established                             │
│   □ Monthly cost estimation documented                            │
│                                                                   │
│ □ DISASTER RECOVERY                                               │
│   □ Rollback procedure documented and tested                     │
│   □ Metadata backup strategy (catalog export)                    │
│   □ Cross-region replication for critical tables                 │
│                                                                   │
│ □ MIGRATION (if from Hive)                                       │
│   □ Table format compatibility verified (Parquet)                │
│   □ Validation queries prepared                                   │
│   □ Rollback plan documented                                      │
│   □ Downstream consumers identified and updated                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference: Decision Matrices

### "Which compaction strategy?" Quick Answer

| Your Pain Point | Strategy | Config Key |
|----------------|----------|------------|
| Too many files, queries are slow to plan | Bin-pack | `strategy => 'binpack'` |
| Queries scan too much data (one filter column) | Sort | `sort_order => 'col ASC'` |
| Queries scan too much data (multiple filter columns) | Z-Order | `sort_order => 'zorder(a, b, c)'` |
| Updates create too many delete files (MoR) | Bin-pack (reconciles deletes) | Same as bin-pack |

### "How often should I compact?" Quick Answer

| Table Type | Bin-pack | Sort/Z-Order | Expire Snapshots |
|-----------|----------|--------------|-----------------|
| Streaming (Flink) | Every 1h | Every 24h | Every 6h (keep 5) |
| Batch (daily ETL) | After each write | Weekly | Daily (keep 5) |
| High-update (CDC) | Every 2h | Every 12h | Every 4h (keep 3) |
| Cold/Archive | Monthly | Monthly | Weekly (keep 3) |

### "Which catalog?" Quick Answer

| Your Situation | Catalog | Why |
|---------------|---------|-----|
| AWS-only, want zero ops | AWS Glue | Serverless, Lake Formation integration |
| Need data branching/versioning | Nessie | Git-like branches for data |
| Multi-cloud or vendor-neutral | REST Catalog | Standard protocol, portable |
| Existing Hadoop infrastructure | Hive Metastore | Already deployed, broad compatibility |
| Databricks-first | Unity Catalog | Tight Databricks integration |
