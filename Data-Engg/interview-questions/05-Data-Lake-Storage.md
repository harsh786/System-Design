# Interview Questions Set 5: Data Lake, Storage Formats & Iceberg/Delta (Q121-150)

---

## Q121: Compare Apache Iceberg, Delta Lake, and Apache Hudi. When would you choose each?

**Answer:**

| Feature | Iceberg | Delta Lake | Hudi |
|---------|---------|-----------|------|
| Developed by | Netflix → Apache | Databricks | Uber → Apache |
| ACID | Yes (snapshot isolation) | Yes (optimistic concurrency) | Yes (MVCC) |
| Schema evolution | Full (add, drop, rename, reorder) | Add, change nullability | Add columns, type promotion |
| Partition evolution | Yes (no rewrite!) | No (must rewrite) | Limited |
| Hidden partitioning | Yes | No | No |
| Time travel | Snapshot-based | Version-based | Timeline-based |
| Engine support | Spark, Flink, Trino, Hive, Dremio | Spark (best), Flink, Trino | Spark, Flink, Hive |
| Merge-on-Read | Yes | No (Copy-on-Write only until 3.0) | Yes (primary design) |
| Streaming | Flink integration | Spark SS native | Yes (TIMELINE) |
| Cloud catalog | REST catalog, AWS Glue, Nessie | Unity Catalog, Hive | Hive metastore |
| Compaction | rewrite_data_files | OPTIMIZE | Built-in (async/sync) |
| Best for | Multi-engine, open ecosystem | Databricks users, Spark-centric | Upsert-heavy, incremental |

**Choose Iceberg when:**
- Multi-engine environment (Spark + Flink + Trino)
- Need partition evolution without data rewrite
- Want vendor-neutral open table format
- Large-scale analytics data lake

**Choose Delta Lake when:**
- Databricks-centric stack
- Team already on Spark ecosystem
- Want simplest Spark integration
- Need Unity Catalog features

**Choose Hudi when:**
- Heavy update/delete workloads (CDC, upserts)
- Need streaming ingestion with low latency
- Uber-like use case (GPS updates, event corrections)

---

## Q122: Explain Iceberg's hidden partitioning. Why is it superior?

**Answer:**

**Problem with Hive-style partitioning:**
```sql
-- User must KNOW the partition structure to query efficiently
-- Partition: year=2024/month=01/day=15
SELECT * FROM orders WHERE year = 2024 AND month = 1 AND day = 15;

-- This DOES NOT use partition pruning (wrong column!):
SELECT * FROM orders WHERE order_date = '2024-01-15';
-- Full table scan! User didn't use partition columns.
```

**Iceberg hidden partitioning:**
```sql
-- Table definition with partition TRANSFORM:
CREATE TABLE orders (
    order_id BIGINT,
    order_date TIMESTAMP,
    amount DECIMAL(10,2)
) PARTITIONED BY (days(order_date));  -- Partition by day of order_date

-- Query uses ACTUAL column (not partition column):
SELECT * FROM orders WHERE order_date = '2024-01-15';
-- Iceberg AUTOMATICALLY applies partition filter!
-- No need to know partition structure.

-- Even range queries work:
SELECT * FROM orders WHERE order_date BETWEEN '2024-01-01' AND '2024-01-31';
-- Automatically prunes to 31 daily partitions.
```

**Partition transforms available:**
| Transform | Description | Example |
|-----------|-------------|---------|
| `identity` | Value as-is | `identity(region)` |
| `year` | Extract year | `year(ts)` → 2024 |
| `month` | Extract month | `month(ts)` → 2024-01 |
| `day` | Extract day | `day(ts)` → 2024-01-15 |
| `hour` | Extract hour | `hour(ts)` → 2024-01-15-08 |
| `bucket(n)` | Hash bucket | `bucket(16, user_id)` |
| `truncate(n)` | Truncate string/int | `truncate(10, zip_code)` |

**Partition evolution (change without rewrite):**
```sql
-- Originally partitioned by month:
ALTER TABLE orders SET PARTITION SPEC (months(order_date));

-- Traffic grew, need daily partitioning. NO REWRITE needed:
ALTER TABLE orders SET PARTITION SPEC (days(order_date));
-- Old data stays monthly, new data written daily.
-- Queries span both seamlessly.
```

---

## Q123: How does Iceberg's metadata layer work? Explain the catalog → metadata → manifest structure.

**Answer:**

```
┌──────────────────────────────────────────────────────────────┐
│                    ICEBERG TABLE STRUCTURE                     │
│                                                               │
│  CATALOG (e.g., Hive Metastore, AWS Glue, REST Catalog)     │
│  └─ Table: db.orders → current metadata file location        │
│                                                               │
│  METADATA FILE (JSON): s3://warehouse/orders/metadata/v3.json│
│  ├── table-uuid                                              │
│  ├── schema (columns, types, field IDs)                      │
│  ├── partition-spec                                          │
│  ├── sort-order                                              │
│  ├── snapshots: [                                            │
│  │     {snapshot-id: 101, manifest-list: "snap-101.avro"},   │
│  │     {snapshot-id: 102, manifest-list: "snap-102.avro"},   │
│  │   ]                                                       │
│  ├── current-snapshot-id: 102                                │
│  └── snapshot-log (history of changes)                       │
│                                                               │
│  MANIFEST LIST (Avro): snap-102.avro                         │
│  ├── manifest-1.avro (partition=2024-01-15, 500 data files)  │
│  ├── manifest-2.avro (partition=2024-01-16, 300 data files)  │
│  └── manifest-3.avro (partition=2024-01-17, 200 data files)  │
│      Each entry has: manifest path, partition range, stats    │
│                                                               │
│  MANIFEST FILE (Avro): manifest-1.avro                       │
│  ├── data-file-1.parquet: {path, partition, record_count,    │
│  │                          column_sizes, value_counts,       │
│  │                          null_counts, lower_bounds,        │
│  │                          upper_bounds}                     │
│  ├── data-file-2.parquet: {...}                              │
│  └── data-file-3.parquet: {...}                              │
│                                                               │
│  DATA FILES (Parquet): Actual data                           │
│  s3://warehouse/orders/data/2024-01-15/part-001.parquet      │
└──────────────────────────────────────────────────────────────┘

Query planning (how pruning works):
1. Read current metadata → find current snapshot
2. Read manifest list → filter manifests by partition range
3. Read relevant manifests → filter data files by column stats
4. Read only matching data files
   → From 10,000 files, may only read 50!
```

---

## Q124: How do you implement time travel queries with Iceberg/Delta?

**Answer:**

```sql
-- ICEBERG TIME TRAVEL:

-- Query a specific snapshot
SELECT * FROM orders VERSION AS OF 12345678;

-- Query at a specific timestamp
SELECT * FROM orders TIMESTAMP AS OF '2024-01-15 10:00:00';

-- View snapshot history
SELECT * FROM orders.snapshots;
-- snapshot_id | committed_at          | operation | summary
-- 100         | 2024-01-15 08:00:00  | append    | added-records=50000
-- 101         | 2024-01-15 09:00:00  | overwrite | ...
-- 102         | 2024-01-15 10:00:00  | delete    | deleted-records=100

-- Rollback to previous snapshot
CALL catalog.system.rollback_to_snapshot('db.orders', 100);

-- Cherry-pick (apply changes from one snapshot to current)
CALL catalog.system.cherrypick_snapshot('db.orders', 101);

-- DELTA LAKE TIME TRAVEL:
-- By version
SELECT * FROM orders VERSION AS OF 5;

-- By timestamp  
SELECT * FROM orders TIMESTAMP AS OF '2024-01-15 10:00:00';

-- View history
DESCRIBE HISTORY orders;

-- Restore
RESTORE TABLE orders TO VERSION AS OF 5;
RESTORE TABLE orders TO TIMESTAMP AS OF '2024-01-15';
```

**Use cases:**
- Debug data issues: "What did the data look like yesterday before that bad pipeline ran?"
- Audit: Regulatory requirement to show data state at any point
- ML reproducibility: Train model on exact snapshot of data
- Rollback: Undo accidental deletes/overwrites

---

## Q125: How do you handle the small files problem in a data lake?

**Answer:**

**Why small files are bad:**
- File listing overhead (S3 LIST: 1000 files/request, high latency)
- Task scheduling overhead (1 task per file in Spark)
- Metadata overhead (manifest entries, stats per file)
- Poor compression ratio (small files compress less efficiently)
- Read amplification (open/close per file)

**Target:** 128MB - 1GB per file (sweet spot: 256-512MB)

**Solutions:**

```sql
-- 1. ICEBERG: Rewrite data files (compaction)
CALL catalog.system.rewrite_data_files(
    table => 'db.orders',
    options => map(
        'target-file-size-bytes', '536870912',  -- 512MB
        'min-file-size-bytes', '67108864',       -- Skip files > 64MB
        'max-file-size-bytes', '1073741824'      -- Max 1GB
    )
);

-- Schedule as maintenance job:
-- Run hourly/daily based on ingestion frequency

-- 2. DELTA LAKE: OPTIMIZE command
OPTIMIZE orders;  -- Compacts small files
OPTIMIZE orders ZORDER BY (customer_id, order_date);  -- Compact + cluster

-- Auto-optimize:
ALTER TABLE orders SET TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',    -- Combine at write time
    'delta.autoOptimize.autoCompact' = 'true'        -- Background compaction
);

-- 3. HUDI: Built-in compaction (for MoR tables)
hoodie.compact.inline = true
hoodie.compact.inline.max.delta.commits = 5  -- Compact every 5 commits

-- 4. SPARK: Repartition at write time
df.repartition(target_partitions)  -- Even distribution
  .write.mode("append")
  .parquet("s3://lake/orders/")

-- Calculate target partitions:
-- target = total_data_size / target_file_size
-- 50GB / 512MB = ~100 partitions
```

---

## Q126: Compare Parquet vs ORC vs Avro. When to use each?

**Answer:**

| Feature | Parquet | ORC | Avro |
|---------|---------|-----|------|
| Layout | Columnar | Columnar | Row-based |
| Compression | Per-column | Per-stripe | Per-block |
| Schema | Embedded | Embedded | Separate (.avsc) |
| Splittable | Yes | Yes | Yes (block boundaries) |
| Best for | Analytics, DW | Hive ecosystem | Streaming, Kafka, ETL |
| Nested types | Excellent (Dremel) | Good | Good |
| Predicate pushdown | Row group stats | Stripe stats + bloom | No |
| Evolution | Limited (add columns) | Limited | Full (w/ registry) |
| Encoding | Dictionary, RLE, Delta | Dictionary, RLE, Bit-pack | N/A |
| Ecosystem | Spark, Trino, Arrow | Hive, Spark, Presto | Kafka, Spark, Flink |

**Decision matrix:**
- **Analytics/OLAP queries:** Parquet (columnar, excellent with Spark/Trino)
- **Hive-centric workloads:** ORC (tight Hive integration, ACID in Hive)
- **Kafka/streaming:** Avro (schema registry, compact, row-oriented for events)
- **Data exchange:** Avro or Parquet depending on consumer

**Compression comparison (1 TB raw data):**
```
Format + Compression    Compressed Size    Read Speed
Parquet + Snappy        ~200 GB            Fast
Parquet + ZSTD          ~150 GB            Medium
ORC + ZLIB              ~160 GB            Medium
ORC + Snappy            ~210 GB            Fast
Avro + Snappy           ~350 GB            Fast
CSV + GZIP             ~250 GB            Slow (not splittable!)
JSON (raw)             ~1.2 TB            Slow
```

---

## Q127: How do you implement a data lakehouse architecture?

**Answer:**

```
┌──────────────────────────────────────────────────────────────────┐
│                    DATA LAKEHOUSE                                  │
│                                                                    │
│  Key principle: Combine Data Lake (cheap storage, open formats)   │
│  with Data Warehouse (ACID, schema enforcement, performance)      │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              MEDALLION ARCHITECTURE                        │    │
│  │                                                           │    │
│  │  BRONZE (Raw)          SILVER (Cleaned)    GOLD (Business)│    │
│  │  ┌─────────────┐     ┌─────────────┐     ┌────────────┐ │    │
│  │  │ Raw ingestion│────▶│ Validated   │────▶│ Aggregated │ │    │
│  │  │ Append-only  │     │ Deduplicated│     │ Business   │ │    │
│  │  │ Full history │     │ Standardized│     │ metrics    │ │    │
│  │  │ Any format   │     │ Typed schema│     │ Curated    │ │    │
│  │  └─────────────┘     └─────────────┘     └────────────┘ │    │
│  │                                                           │    │
│  │  Storage: S3/ADLS/GCS (open, cheap, durable)             │    │
│  │  Format: Parquet + Iceberg/Delta metadata                 │    │
│  │  Provides: ACID, time travel, schema enforcement          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  QUERY ENGINES (compute separated from storage):                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Spark (batch)  │ Flink (stream)  │ Trino (interactive)   │    │
│  │ dbt (transform)│ Flink SQL       │ DuckDB (local)        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  vs Traditional:                                                  │
│  Data Lake: No ACID, no schema enforcement, "data swamp" risk    │
│  Data Warehouse: Expensive, proprietary, limited format support   │
│  Lakehouse: Best of both (ACID on open formats, cheap storage)    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Q128: How do you implement row-level deletes in Iceberg? Compare copy-on-write vs merge-on-read.

**Answer:**

**Copy-on-Write (CoW):**
```
DELETE FROM orders WHERE order_id = 'abc123';

Process:
1. Find data file(s) containing order 'abc123'
2. Read entire file(s)
3. Write NEW file(s) with row removed
4. Update metadata: remove old file reference, add new file reference
5. Old file marked for deletion (retained for time travel)

Trade-offs:
+ Fast reads (no merge needed at query time)
- Slow writes (rewrite entire files for 1 row delete)
- Write amplification (delete 1 row → rewrite 500MB file)
```

**Merge-on-Read (MoR):**
```
DELETE FROM orders WHERE order_id = 'abc123';

Process:
1. Write DELETE FILE: {file: "data-001.parquet", row: 42}
   (just records WHICH rows to delete)
2. At read time: Read data file + merge with delete file
   → Skip deleted rows during scan
3. Periodic compaction: Merge deletes into data files (becomes CoW)

Trade-offs:
+ Fast writes (just write small delete file)
- Slower reads (must merge at query time)
- Compaction needed to maintain read performance
```

**Iceberg v2 supports both:**
```sql
-- Set per table:
ALTER TABLE orders SET TBLPROPERTIES (
    'write.delete.mode' = 'merge-on-read',  -- or 'copy-on-write'
    'write.update.mode' = 'merge-on-read',
    'write.merge.mode' = 'merge-on-read'
);
```

**When to use which:**
- CoW: Read-heavy workloads, few deletes/updates
- MoR: Write-heavy, frequent updates (CDC), can tolerate slight read overhead

---

## Q129: How do you implement data lake security and access control?

**Answer:**

```
MULTI-LAYER SECURITY:

Layer 1: Storage-level (S3/ADLS IAM)
  - Bucket policies: Restrict access by team/service
  - IAM roles: Fine-grained per-service access
  - Encryption: SSE-S3, SSE-KMS, client-side

Layer 2: Table-level (Catalog)
  - Iceberg REST Catalog: Role-based table access
  - AWS Lake Formation: Column-level, row-level security
  - Unity Catalog: Attribute-based access control
  
Layer 3: Column-level masking
  - Sensitive columns masked for unauthorized users
  - PII columns: Dynamic masking at query time
  
Layer 4: Row-level filtering
  - Users only see their region's data
  - Applied transparently at catalog level

Example (AWS Lake Formation):
  Permissions:
    data-analyst-role:
      - Table: orders → SELECT (all columns except credit_card)
      - Row filter: region = 'US'
    
    data-engineer-role:
      - Table: orders → ALL (including PII)
      - No row filter

  Column masking:
    credit_card → CASE WHEN current_role = 'pii_reader' 
                       THEN credit_card 
                       ELSE 'XXXX-XXXX-XXXX-' || RIGHT(credit_card, 4) END
```

---

## Q130: How do you implement incremental reads from an Iceberg table?

**Answer:**

```python
# Iceberg incremental reads: Only read files added since last snapshot

# Spark: Incremental scan between snapshots
df = spark.read.format("iceberg") \
    .option("start-snapshot-id", "12345") \
    .option("end-snapshot-id", "12350") \
    .load("catalog.db.orders")
# Returns ONLY rows added between these snapshots

# Flink: Streaming read from Iceberg (continuous incremental)
CREATE TABLE orders_stream WITH (
    'connector' = 'iceberg',
    'catalog-name' = 'my_catalog',
    'catalog-type' = 'hive',
    'streaming' = 'true',
    'monitor-interval' = '10s'  -- Check for new snapshots every 10s
);

SELECT * FROM orders_stream;
-- Continuously reads new data as snapshots are committed

# Use case: CDC pipeline
# Write CDC events to Iceberg → Downstream reads incrementally
# No need for Kafka in between (Iceberg as streaming source)
```

---

## Q131-150: [Storage & Data Lake Questions - Condensed]

**Q131:** How do you implement data retention policies in a data lake?
- Iceberg: Expire snapshots (`expire_snapshots` procedure), remove orphan files
- Delta: `VACUUM` command (removes files older than retention)
- Tiering: Move cold partitions to cheaper storage class (S3 IA, Glacier)

**Q132:** How does Z-ordering work and when should you use it?
- Z-order curve maps multi-dimensional data to single dimension while preserving locality
- Use when queries filter on multiple columns simultaneously (vs partitioning for single column)
- Best for medium-cardinality columns (100-10K distinct values)

**Q133:** Explain catalog management for Iceberg tables.
- Hive Metastore: Traditional, widely supported
- AWS Glue Catalog: Serverless, AWS-native
- REST Catalog: Vendor-neutral, flexible (Tabular, Gravitino)
- Nessie: Git-like branching for data (branch/merge tables)

**Q134:** How do you handle schema conflicts in a multi-writer scenario?
- Iceberg: Optimistic concurrency, retry on conflict
- Delta: `commitInfo` tracks writers, conflict resolution via retry
- Pattern: Write to staging, MERGE into target (serialize conflicts)

**Q135:** Compare ZSTD vs Snappy vs LZ4 compression.
- Snappy: Fastest decompress, moderate ratio (default for hot data)
- ZSTD: Best ratio, configurable levels, good decompress speed (cold data)
- LZ4: Fastest overall, lowest ratio (real-time/streaming)

**Q136:** How do you implement data quality gates in a data lake pipeline?
- Write to staging → validate → promote to production table
- Iceberg branch: Write to branch, validate, fast-forward merge

**Q137:** Explain Iceberg's sort orders and their performance impact.
- Sort within data files by specified columns
- Improves predicate pushdown (tighter min/max per file)
- Trade-off: Slower writes (must sort), faster reads

**Q138:** How do you handle concurrent reads and writes in a data lake?
- Iceberg: Snapshot isolation (readers never blocked, see consistent snapshot)
- Delta: Optimistic concurrency control (write conflicts detected at commit)
- Both: MVCC-style (readers see committed state, writers don't block readers)

**Q139:** Design a data lake migration from Hive tables to Iceberg.
- In-place migration: `CALL catalog.system.migrate('db.table')` — converts metadata only
- Shadow migration: Create Iceberg table, dual-write, validate, switch readers
- Considerations: Partition spec, sort order, statistics rebuild

**Q140:** How do you implement data lake governance with Nessie?
- Git-like catalog: Branch tables for ETL, merge when validated
- `CREATE BRANCH etl_branch AT main` → Write to branch → `MERGE BRANCH etl_branch INTO main`
- Enables: Preview data changes, rollback, audit trail

**Q141:** Explain Iceberg's manifest caching and its performance impact.
- Manifest files cached in executor memory (avoid re-reading from S3)
- Controlled by `spark.sql.catalog.*.cache-enabled=true`
- Critical for short-running queries (avoid S3 latency per query)

**Q142:** How do you handle late-arriving data in a partitioned data lake?
- Iceberg: Write to correct partition regardless of arrival time (no partition immutability)
- Delta: MERGE into historical partition (overwrite mode)
- Pattern: Allow writes to last N days of partitions, expire older

**Q143:** What is Iceberg's position delete vs equality delete?
- Position delete: File path + row position (faster read, larger delete files)
- Equality delete: Column values to match (smaller delete files, slower read merge)
- Position delete used by CoW rewrites; equality delete by streaming upserts

**Q144:** How do you optimize Iceberg table for read performance?
- Sort order on frequently filtered columns
- Proper partitioning (avoid too many/few partitions)
- Regular compaction (merge small files)
- Rewrite manifests for balanced distribution
- Use hidden partitioning for query transparency

**Q145:** Design a multi-region data lake with Iceberg.
- Catalog replication across regions
- Data replicated via S3 Cross-Region Replication
- Conflict resolution: Single-writer per region + async replication
- Or: Primary region writes, secondary regions read-only

**Q146:** How do you handle data lake cost optimization on cloud?
- Storage tiering: Hot (Standard) → Warm (IA) → Cold (Glacier)
- Expire old snapshots (metadata cleanup)
- Compact small files (reduce LIST/GET API calls)
- Compress with ZSTD (40-60% size reduction vs uncompressed)
- Partition pruning (reduce data scanned per query)

**Q147:** Explain the difference between external tables and managed tables in Iceberg.
- Managed: Catalog owns data lifecycle (DROP TABLE deletes data)
- External: Catalog only tracks metadata (DROP TABLE keeps data)
- Use external for shared data, managed for pipeline-owned data

**Q148:** How do you implement slowly changing dimensions with Iceberg MERGE?
```sql
MERGE INTO dim_customers t
USING staging_customers s
ON t.customer_id = s.customer_id AND t.is_current = true
WHEN MATCHED AND (t.name != s.name OR t.tier != s.tier) THEN
    UPDATE SET is_current = false, valid_to = current_timestamp()
WHEN NOT MATCHED THEN
    INSERT (customer_id, name, tier, valid_from, valid_to, is_current)
    VALUES (s.customer_id, s.name, s.tier, current_timestamp(), '9999-12-31', true);
```

**Q149:** How do you benchmark and measure data lake query performance?
- Metrics: Query latency (p50, p99), data scanned, files read, planning time
- Tools: Spark UI (stages, tasks, I/O), Trino EXPLAIN ANALYZE
- Benchmarks: TPC-DS adapted for lakehouse format

**Q150:** Design a streaming ingestion pipeline from Kafka to Iceberg with exactly-once.
- Flink + Iceberg Sink: Flink checkpoints = Iceberg snapshots (atomic)
- Each checkpoint commits a new Iceberg snapshot
- On failure: Restore from checkpoint, uncommitted files cleaned by GC
- Alternative: Kafka Connect + Iceberg Sink Connector
