# Data Lakes, Apache Iceberg, Delta Lake & Hudi - Staff Architect Deep Dive

## Table of Contents
1. [Data Lake Fundamentals](#1-data-lake-fundamentals)
2. [Apache Iceberg Deep Dive](#2-apache-iceberg-deep-dive)
3. [Delta Lake Deep Dive](#3-delta-lake-deep-dive)
4. [Apache Hudi Deep Dive](#4-apache-hudi-deep-dive)
5. [Comparison: Iceberg vs Delta vs Hudi](#5-comparison)
6. [Lakehouse Architecture](#6-lakehouse-architecture)
7. [Compaction and Optimization](#7-compaction-and-optimization)
8. [Data Governance](#8-data-governance)

---

## 1. Data Lake Fundamentals

### Data Lake vs Warehouse vs Lakehouse

```
┌───────────────┬──────────────────┬──────────────────┬──────────────────┐
│               │ Data Warehouse   │ Data Lake        │ Data Lakehouse   │
├───────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Storage       │ Proprietary      │ Open (S3/GCS)    │ Open (S3/GCS)    │
│ Format        │ Proprietary      │ Open (Parquet)   │ Open (Parquet)   │
│ Schema        │ Schema-on-write  │ Schema-on-read   │ Schema-on-write  │
│ ACID          │ Yes              │ No               │ Yes (Iceberg/    │
│               │                  │                  │ Delta/Hudi)      │
│ Governance    │ Built-in         │ Weak             │ Strong           │
│ Performance   │ Excellent        │ Variable         │ Good-Excellent   │
│ Cost          │ High             │ Low              │ Medium           │
│ ML support    │ Limited          │ Excellent        │ Excellent        │
│ Data types    │ Structured       │ All              │ All              │
│ Engines       │ Proprietary      │ Any              │ Any              │
│ Time travel   │ Limited          │ No               │ Yes              │
│ Examples      │ Redshift, BQ     │ S3 + Parquet     │ S3 + Iceberg     │
└───────────────┴──────────────────┴──────────────────┴──────────────────┘
```

### Medallion Architecture (Bronze/Silver/Gold)

```
┌─────────────────────────────────────────────────────────────────┐
│                 MEDALLION ARCHITECTURE                           │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │  BRONZE  │───▶│  SILVER  │───▶│   GOLD   │                  │
│  │  (Raw)   │    │(Cleansed)│    │ (Curated)│                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
│                                                                  │
│  Bronze:                                                        │
│  - Raw data as-is from sources                                  │
│  - Schema-on-read, minimal transformation                       │
│  - Append-only, retain full history                             │
│  - Data types: JSON, CSV, Avro, Parquet                        │
│                                                                  │
│  Silver:                                                        │
│  - Cleansed, validated, deduplicated                            │
│  - Schema enforced, data types corrected                        │
│  - Joins across sources, SCD applied                            │
│  - Standardized naming and formats                              │
│                                                                  │
│  Gold:                                                          │
│  - Business-level aggregations                                  │
│  - Star schema / OLAP cubes                                     │
│  - KPIs, metrics, features                                      │
│  - Ready for BI dashboards and ML                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Apache Iceberg Deep Dive

### Table Format Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  ICEBERG TABLE STRUCTURE                       │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              CATALOG (Hive / Glue / Nessie)          │     │
│  │  Points to → current metadata file location          │     │
│  └─────────────────────┬───────────────────────────────┘     │
│                         │                                     │
│  ┌─────────────────────▼───────────────────────────────┐     │
│  │          METADATA FILE (metadata/v3.metadata.json)    │     │
│  │                                                       │     │
│  │  - Table schema (current + history)                   │     │
│  │  - Partition spec (current + history)                 │     │
│  │  - Sort order                                         │     │
│  │  - Properties                                         │     │
│  │  - Snapshot list                                      │     │
│  │  - Current snapshot ID                                │     │
│  │  - Snapshot log                                       │     │
│  └─────────────────────┬───────────────────────────────┘     │
│                         │                                     │
│  ┌─────────────────────▼───────────────────────────────┐     │
│  │          SNAPSHOT (snap-123456.avro)                   │     │
│  │                                                       │     │
│  │  - Snapshot ID                                        │     │
│  │  - Parent snapshot ID                                 │     │
│  │  - Timestamp                                          │     │
│  │  - Summary (added-records, deleted-records, etc.)     │     │
│  │  - Manifest list file location                        │     │
│  └─────────────────────┬───────────────────────────────┘     │
│                         │                                     │
│  ┌─────────────────────▼───────────────────────────────┐     │
│  │          MANIFEST LIST (snap-123456-m0.avro)          │     │
│  │                                                       │     │
│  │  List of manifest files:                              │     │
│  │  - Manifest path                                      │     │
│  │  - Partition spec ID                                  │     │
│  │  - Content type (DATA / DELETE)                       │     │
│  │  - Partition summary (min/max per partition field)     │     │
│  │  - Added/existing/deleted file counts                 │     │
│  └─────────────────────┬───────────────────────────────┘     │
│                         │                                     │
│  ┌─────────────────────▼───────────────────────────────┐     │
│  │          MANIFEST FILE (manifest-abc.avro)            │     │
│  │                                                       │     │
│  │  List of data files:                                  │     │
│  │  - File path (s3://bucket/data/...)                   │     │
│  │  - File format (Parquet/ORC/Avro)                     │     │
│  │  - Partition values                                   │     │
│  │  - Record count                                       │     │
│  │  - File size in bytes                                 │     │
│  │  - Column stats (min, max, null count, NaN count)     │     │
│  │  - Split offsets                                      │     │
│  └─────────────────────┬───────────────────────────────┘     │
│                         │                                     │
│  ┌─────────────────────▼───────────────────────────────┐     │
│  │          DATA FILES (Parquet/ORC)                      │     │
│  │  s3://bucket/data/dt=2024-01-15/00001-abc.parquet     │     │
│  │  s3://bucket/data/dt=2024-01-15/00002-def.parquet     │     │
│  └──────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### Snapshot Isolation

```
Time →
Snapshot S1 ──── Snapshot S2 ──── Snapshot S3

Writer A: Reading S1, writes new data
Writer B: Reading S1, writes different data

Result:
  S2 = S1 + Writer A's changes  (if A commits first)
  S3 = S2 + Writer B's changes  (optimistic concurrency)
  
  If B conflicts with A: retry (re-read, re-apply)
  
  Conflict detection:
  - No conflict: Different files added/deleted
  - Conflict: Same file modified by both writers
  
Readers always see consistent snapshot (no dirty reads)
```

### Schema Evolution

```sql
-- Add column (backward compatible)
ALTER TABLE db.events ADD COLUMN browser STRING AFTER user_agent;

-- Rename column
ALTER TABLE db.events RENAME COLUMN browser TO browser_name;

-- Change column type (widening only: int → long, float → double)
ALTER TABLE db.events ALTER COLUMN event_count TYPE BIGINT;

-- Drop column
ALTER TABLE db.events DROP COLUMN deprecated_field;

-- Reorder columns
ALTER TABLE db.events ALTER COLUMN amount AFTER customer_id;

-- All changes tracked in schema history within metadata
-- Old snapshots use old schema, new snapshots use new schema
-- Queries automatically handle schema evolution
```

### Partition Evolution

```sql
-- Start with monthly partitioning
CREATE TABLE events (
    event_id BIGINT,
    event_time TIMESTAMP,
    event_type STRING
) USING iceberg
PARTITIONED BY (months(event_time));

-- Traffic grows, switch to daily (NO DATA REWRITE!)
ALTER TABLE events SET PARTITION SPEC (days(event_time));

-- Further refine: add bucket partition
ALTER TABLE events SET PARTITION SPEC (days(event_time), bucket(16, event_type));

-- Queries automatically handle mixed partition specs:
-- Old data: scanned with monthly pruning
-- New data: scanned with daily + bucket pruning
```

### Hidden Partitioning

```
Traditional Hive partitioning:
  SELECT * FROM events WHERE event_date = '2024-01-15'
  User MUST know partition column and format

Iceberg hidden partitioning:
  PARTITIONED BY (days(event_time))
  
  SELECT * FROM events 
  WHERE event_time >= '2024-01-15' AND event_time < '2024-01-16'
  
  Iceberg automatically:
  1. Derives partition value: days('2024-01-15 10:30:00') = 2024-01-15
  2. Prunes partitions using derived value
  3. User writes natural predicates on source column
  
  No separate partition column needed!

Available transforms:
  years(ts)          → Year partition
  months(ts)         → Month partition  
  days(ts)           → Day partition
  hours(ts)          → Hour partition
  bucket(N, col)     → Hash bucket
  truncate(W, col)   → Truncate string/number
  identity(col)      → Same as Hive-style
```

### Row-Level Deletes

```
COPY-ON-WRITE (CoW):
  Delete record → Rewrite entire data file without deleted rows
  
  Before: file1.parquet [A, B, C, D, E]
  DELETE WHERE id = 'C'
  After:  file2.parquet [A, B, D, E]  (entire file rewritten)
  
  Pros: Fast reads (no delete files to merge)
  Cons: Slow writes (rewrite large files for small deletes)

MERGE-ON-READ (MoR):
  Delete record → Write delete file (marks records as deleted)
  
  Before: file1.parquet [A, B, C, D, E]
  DELETE WHERE id = 'C'
  After:  file1.parquet [A, B, C, D, E]  (unchanged)
          delete-file1.parquet [C is deleted]
  
  Read: Merge data + delete files at query time
  
  Pros: Fast writes (small delete files)
  Cons: Slower reads (must merge), needs compaction

Delete file types:
  POSITION DELETE: File path + row position → exact row identification
  EQUALITY DELETE: Column values → match and delete (more flexible)
```

### Iceberg SQL Operations

```sql
-- Time Travel
SELECT * FROM db.events VERSION AS OF 12345;           -- By snapshot ID
SELECT * FROM db.events TIMESTAMP AS OF '2024-01-15';  -- By timestamp

-- Branching and Tagging
ALTER TABLE db.events CREATE BRANCH audit_branch RETAIN 30 DAYS;
ALTER TABLE db.events CREATE TAG release_v1 AS OF VERSION 12345;

-- Read from branch
SELECT * FROM db.events VERSION AS OF 'audit_branch';

-- Metadata queries
SELECT * FROM db.events.snapshots;
SELECT * FROM db.events.history;
SELECT * FROM db.events.manifests;
SELECT * FROM db.events.files;
SELECT * FROM db.events.partitions;

-- Compaction
CALL catalog.system.rewrite_data_files(
    table => 'db.events',
    strategy => 'sort',
    sort_order => 'event_time ASC NULLS LAST',
    options => map('target-file-size-bytes', '536870912')  -- 512MB
);

-- Expire snapshots (cleanup old metadata)
CALL catalog.system.expire_snapshots(
    table => 'db.events',
    older_than => TIMESTAMP '2024-01-01 00:00:00',
    retain_last => 5
);

-- Remove orphan files
CALL catalog.system.remove_orphan_files(
    table => 'db.events',
    older_than => TIMESTAMP '2024-01-01 00:00:00'
);
```

---

## 3. Delta Lake Deep Dive

### Transaction Log

```
Delta table directory:
s3://bucket/delta-table/
├── _delta_log/                    ← Transaction log
│   ├── 00000000000000000000.json  ← Version 0
│   ├── 00000000000000000001.json  ← Version 1
│   ├── 00000000000000000002.json  ← Version 2
│   ├── ...
│   ├── 00000000000000000010.checkpoint.parquet  ← Checkpoint (every 10)
│   └── _last_checkpoint           ← Points to latest checkpoint
├── part-00000-abc.parquet         ← Data files
├── part-00001-def.parquet
└── ...

Each JSON log entry contains ACTIONS:
{
  "add": {
    "path": "part-00000-abc.parquet",
    "size": 134217728,
    "partitionValues": {"date": "2024-01-15"},
    "modificationTime": 1705305600000,
    "dataChange": true,
    "stats": "{\"numRecords\":1000000,\"minValues\":{\"amount\":0.01},\"maxValues\":{\"amount\":9999.99}}"
  }
}

{
  "remove": {
    "path": "part-00000-old.parquet",
    "deletionTimestamp": 1705305600000,
    "dataChange": true
  }
}

Checkpoint: Parquet file summarizing all actions up to version N
  → Avoids replaying thousands of JSON log files
  → Created every 10 versions by default
```

### Key Delta Lake Operations

```python
from delta.tables import DeltaTable

# MERGE (Upsert) - most common operation
delta_table = DeltaTable.forPath(spark, "s3://bucket/customers")

delta_table.alias("target").merge(
    new_data.alias("source"),
    "target.customer_id = source.customer_id"
).whenMatchedUpdate(
    condition="source.updated_at > target.updated_at",
    set={
        "name": "source.name",
        "email": "source.email",
        "updated_at": "source.updated_at"
    }
).whenNotMatchedInsertAll() \
 .whenNotMatchedBySourceDelete(
    condition="target.is_active = false"  # Delta 2.4+
).execute()

# OPTIMIZE (compact small files)
spark.sql("OPTIMIZE delta.`s3://bucket/events`")
spark.sql("OPTIMIZE delta.`s3://bucket/events` WHERE date >= '2024-01-01'")

# Z-ORDER (co-locate data for faster filters)
spark.sql("""
    OPTIMIZE delta.`s3://bucket/events` 
    ZORDER BY (customer_id, event_type)
""")

# VACUUM (delete old files)
spark.sql("VACUUM delta.`s3://bucket/events` RETAIN 168 HOURS")  # 7 days
# WARNING: Files deleted permanently! Cannot time travel past retention

# Change Data Feed
spark.read.format("delta") \
    .option("readChangeFeed", "true") \
    .option("startingVersion", 5) \
    .option("endingVersion", 10) \
    .load("s3://bucket/customers")
# Returns: _change_type (insert/update_preimage/update_postimage/delete)
#          _commit_version, _commit_timestamp

# Liquid Clustering (Delta 3.0+, replaces partitioning + Z-ordering)
spark.sql("""
    CREATE TABLE events USING delta
    CLUSTER BY (customer_id, event_date)
    AS SELECT * FROM raw_events
""")
# Auto-manages data layout, can change clustering columns without rewrite
```

### Deletion Vectors (Delta 3.0+)

```
Traditional DELETE: Rewrite entire file without deleted rows (CoW)
With Deletion Vectors: Mark deleted rows in a bitmap (MoR)

Before: file1.parquet [row0, row1, row2, row3, row4]
DELETE WHERE id = 'row2'

After (traditional): file1_new.parquet [row0, row1, row3, row4] (full rewrite)

After (deletion vector): 
  file1.parquet [row0, row1, row2, row3, row4]  (unchanged!)
  file1.deletion_vector.bin [0, 0, 1, 0, 0]     (bitmap: row2 deleted)

Read: Apply deletion vector at query time (skip marked rows)

Benefits:
  - 10-100x faster deletes (no file rewrite)
  - Predictable DELETE/UPDATE latency
  - Background compaction merges deletion vectors into data files

Enable:
  delta.enableDeletionVectors = true
```

---

## 4. Apache Hudi Deep Dive

### Table Types

```
COPY-ON-WRITE (CoW):
  Updates rewrite entire file
  Read: Direct Parquet read (fast)
  Write: Slow (full file rewrite)
  Storage: Higher (duplicate data during write)
  Best for: Read-heavy workloads

MERGE-ON-READ (MoR):
  Updates written to log files (Avro)
  Periodically compacted into base Parquet files
  
  File structure:
  ├── base_file.parquet     ← Original data
  ├── .log.1                ← Delta log (updates/inserts)
  ├── .log.2                ← More deltas
  └── (after compaction) →  new_base_file.parquet
  
  Read optimized query: Only base files (stale but fast)
  Snapshot query: Base + log files (fresh but slower)
  Best for: Write-heavy workloads

┌─────────────────┬─────────────────┬─────────────────┐
│                 │ Copy-on-Write   │ Merge-on-Read   │
├─────────────────┼─────────────────┼─────────────────┤
│ Write latency   │ High            │ Low             │
│ Read latency    │ Low             │ Medium          │
│ Update cost     │ High (rewrite)  │ Low (append log)│
│ Read perf       │ Best            │ Needs compaction│
│ Storage         │ Optimized       │ Log overhead    │
│ Compaction      │ Not needed      │ Required        │
│ Query types     │ Snapshot only   │ Snapshot + Read │
│                 │                 │ Optimized       │
└─────────────────┴─────────────────┴─────────────────┘
```

### Hudi Timeline and File Groups

```
TIMELINE: Sequence of actions on the table
  
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ COMMIT   │  │ COMMIT   │  │ COMPACT  │  │ COMMIT   │
  │ 001      │  │ 002      │  │ 003      │  │ 004      │
  │ 10:00    │  │ 10:05    │  │ 10:10    │  │ 10:15    │
  └──────────┘  └──────────┘  └──────────┘  └──────────┘
  
  Actions: commit, deltacommit, compaction, clean, rollback,
           savepoint, restore, indexing

FILE GROUP: Set of file slices for a record group
  
  File Group 1 (records with hash(id) % N = 0):
  ┌────────────────────┐
  │ Slice 001          │  ← base.parquet (commit 001)
  │ Slice 002          │  ← base.parquet + .log (commit 002)
  │ Slice 003          │  ← compacted.parquet (compaction 003)
  │ Slice 004          │  ← compacted.parquet + .log (commit 004)
  └────────────────────┘
```

---

## 5. Comparison

```
┌──────────────────┬──────────────┬──────────────┬──────────────┐
│ Feature          │ Iceberg      │ Delta Lake   │ Hudi         │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ Origin           │ Netflix      │ Databricks   │ Uber         │
│ Governance       │ Apache       │ Linux Found. │ Apache       │
│ ACID             │ Yes          │ Yes          │ Yes          │
│ Time travel      │ Yes          │ Yes          │ Yes          │
│ Schema evolution │ Full         │ Full         │ Full         │
│ Partition evolve │ Yes (unique) │ No (rewrite) │ No           │
│ Hidden partition │ Yes          │ No           │ No           │
│ Row-level delete │ CoW + MoR    │ CoW + DV     │ CoW + MoR   │
│ Branching/Tags   │ Yes          │ No           │ No           │
│ Spark support    │ Excellent    │ Best         │ Good         │
│ Flink support    │ Good         │ Limited      │ Good         │
│ Trino support    │ Excellent    │ Good         │ Good         │
│ Engine agnostic  │ Most         │ Spark-centric│ Spark-centric│
│ Metadata size    │ Scalable     │ JSON log     │ Timeline     │
│ Incremental read │ Snapshots    │ CDF          │ Timeline     │
│ Compaction       │ Manual/auto  │ OPTIMIZE     │ Auto/manual  │
│ Upsert perf      │ Good         │ Good (DV)    │ Best (index) │
│ Community        │ Rapidly grow │ Large        │ Large        │
│ Cloud support    │ Broad        │ Databricks   │ AWS (EMR)    │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ Choose when      │ Multi-engine │ Databricks   │ Heavy upserts│
│                  │ Open standard│ ecosystem    │ Near-real-time│
│                  │ Partition evo│ Simplicity   │ CDC workloads│
└──────────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 6. Lakehouse Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    DATA LAKEHOUSE                                 │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    Query Engines                            │   │
│  │  ┌──────┐  ┌───────┐  ┌──────┐  ┌───────┐  ┌──────────┐ │   │
│  │  │ Spark│  │ Trino │  │ Flink│  │ Dremio│  │ Snowflake│ │   │
│  │  └──────┘  └───────┘  └──────┘  └───────┘  └──────────┘ │   │
│  └────────────────────────┬───────────────────────────────────┘   │
│                           │                                       │
│  ┌────────────────────────▼───────────────────────────────────┐   │
│  │              Table Format (Iceberg / Delta / Hudi)          │   │
│  │  ACID | Time Travel | Schema Evolution | Partition Evolution│   │
│  └────────────────────────┬───────────────────────────────────┘   │
│                           │                                       │
│  ┌────────────────────────▼───────────────────────────────────┐   │
│  │              Catalog (HMS / Glue / Nessie / Unity)          │   │
│  │  Schema registry | Access control | Data lineage           │   │
│  └────────────────────────┬───────────────────────────────────┘   │
│                           │                                       │
│  ┌────────────────────────▼───────────────────────────────────┐   │
│  │              File Format (Parquet / ORC)                     │   │
│  │  Columnar | Compressed | Encoded | Statistics               │   │
│  └────────────────────────┬───────────────────────────────────┘   │
│                           │                                       │
│  ┌────────────────────────▼───────────────────────────────────┐   │
│  │              Object Storage (S3 / GCS / ADLS)               │   │
│  │  Cheap | Durable | Scalable | Decoupled from compute       │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. Compaction and Optimization

### Small File Compaction

```python
# Iceberg compaction
spark.sql("""
    CALL catalog.system.rewrite_data_files(
        table => 'db.events',
        strategy => 'binpack',
        options => map(
            'target-file-size-bytes', '536870912',
            'min-file-size-bytes', '67108864',
            'max-file-size-bytes', '1073741824',
            'min-input-files', '5',
            'max-concurrent-file-group-rewrites', '10'
        )
    )
""")

# Delta Lake OPTIMIZE
spark.sql("OPTIMIZE delta.`s3://lake/events` WHERE date >= '2024-01-01'")

# Hudi compaction (for MoR tables)
# Automatic: hoodie.compact.inline=true
# Manual:
spark.sql("CALL run_compaction(table => 'db.events', op => 'RUN')")
```

### Z-Ordering and Data Clustering

```
Z-ORDER: Interleave bits of multiple columns to co-locate related data

Without Z-order (sorted by col1 only):
  File 1: col1=[1-100],   col2=[random]
  File 2: col1=[101-200], col2=[random]
  
  Query: WHERE col1=50 AND col2=75
  → Must scan entire file (col2 not clustered)

With Z-order (interleaved col1, col2):
  File 1: col1=[1-50],    col2=[1-50]
  File 2: col1=[51-100],  col2=[1-50]
  File 3: col1=[1-50],    col2=[51-100]
  File 4: col1=[51-100],  col2=[51-100]
  
  Query: WHERE col1=50 AND col2=75
  → Skip files 1,2 (col2 max < 75 in files 1,2)
  → Only scan file 3 or 4!

Hilbert Curve (Iceberg): Better multi-dimensional clustering than Z-order
  More uniform data distribution in high dimensions
  
  CALL catalog.system.rewrite_data_files(
    table => 'db.events',
    strategy => 'sort',
    sort_order => 'zorder(customer_id, event_type)'
  )
```

---

## 8. Data Governance

### Fine-Grained Access Control

```sql
-- Column-level security (Iceberg + Trino)
GRANT SELECT ON TABLE db.customers TO ROLE analyst;
REVOKE SELECT(ssn, credit_card) ON TABLE db.customers FROM ROLE analyst;

-- Row-level security (via views)
CREATE VIEW db.customers_filtered AS
SELECT * FROM db.customers
WHERE region = current_user_region();  -- Row filter based on user context

-- Data masking
CREATE VIEW db.customers_masked AS
SELECT 
    customer_id,
    name,
    CONCAT('***-**-', RIGHT(ssn, 4)) AS ssn,  -- Mask SSN
    CONCAT(LEFT(email, 2), '***@***') AS email  -- Mask email
FROM db.customers;
```

### Data Lineage

```
OpenLineage standard:

Job: spark_etl_orders
  Inputs:
    - database: raw.orders (read 1M records)
    - database: raw.customers (read 50K records)
  Outputs:
    - database: curated.order_facts (wrote 1M records)
  
Lineage graph:
  raw.orders ──────┐
                    ├──▶ spark_etl_orders ──▶ curated.order_facts
  raw.customers ───┘

Tools:
  - OpenLineage: Open standard for lineage events
  - Marquez: Metadata service implementing OpenLineage
  - DataHub: LinkedIn's metadata platform
  - Apache Atlas: Hadoop ecosystem governance
  - Amundsen: Lyft's data discovery platform
  - Atlan: Commercial data catalog
```

---

## Production Checklist

```
[ ] Table format: Iceberg (multi-engine) or Delta (Databricks ecosystem)
[ ] Partitioning: Time-based with appropriate granularity
[ ] File size: 128MB - 1GB target (compaction scheduled)
[ ] Compaction: Scheduled (OPTIMIZE / rewrite_data_files)
[ ] Snapshot expiry: Retain 5-10 snapshots, expire older
[ ] Orphan file cleanup: Scheduled (remove_orphan_files)
[ ] Schema evolution: Backward-compatible changes only
[ ] Time travel retention: 7-30 days (balance cost vs utility)
[ ] Catalog: Centralized (Glue/Nessie/Unity) with access control
[ ] Monitoring: Table size, file count, snapshot count, query latency
[ ] Data quality: Validation at each medallion layer
[ ] Governance: Column masking, row filtering, audit logging
[ ] Cost: Storage tiering (S3 lifecycle policies)
[ ] DR: Cross-region replication for critical tables
```
