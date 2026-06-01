# Query Performance & Planning Issues (#59-72)

Issues related to slow queries, planning timeouts, inefficient scans,
and query engine misconfigurations with Iceberg tables.

---

## Issue #59: Query Planning Takes Longer Than Query Execution

**Severity:** P1 - High
**Frequency:** Daily on tables with 100K+ files
**Affected Components:** All query engines (Spark, Trino, Athena)
**First seen at:** Tables with poor manifest organization

### Symptoms
```
- Query total time: 60 seconds. Planning: 55 seconds. Execution: 5 seconds.
- Trino shows "PLANNING" state for minutes before any splits assigned
- Spark "planning" stage dominates DAG visualization
- Adding more executors doesn't help (single-threaded planning)
- Same data in Parquet directory (no Iceberg) plans in 2 seconds
```

### Root Cause
```
Iceberg planning reads metadata in sequence:
  1. Load metadata.json from catalog (1 S3 GET)
  2. Parse snapshot list, find current snapshot
  3. Load manifest list (1 S3 GET) → list of manifests
  4. Load EACH manifest file (N S3 GETs, can be 10K+)
  5. For each manifest entry: check partition filter (skip non-matching)
  6. For remaining entries: check column statistics (min/max pruning)
  7. Generate split plan for matching files
  
  Bottleneck: Step 4 - reading 10K manifest files = 10K S3 GETs
  Each GET: 50-100ms latency = 500-1000 seconds if sequential!
  
  Iceberg parallelizes manifest reads, but still limited by:
  - Number of planning threads
  - S3 GET latency (50ms per request even with parallelism)
  - Memory to hold all manifest entries
  
  With 50K manifests × 100 entries each = 5M data file entries to evaluate
```

### Immediate Fix
```sql
-- Rewrite manifests (reduce count from 50K to 500)
CALL prod.system.rewrite_manifests('db.table');

-- Trino: increase planning parallelism
SET SESSION iceberg.max_planning_threads = 32;

-- Spark: increase metadata read parallelism  
SET spark.sql.iceberg.planning.worker-threads = 32;
```

### Permanent Fix
```properties
# Table properties for manifest management
commit.manifest.target-size-bytes = 8388608   # 8MB manifests (hold ~5K entries)
commit.manifest-merge.enabled = true          # Merge on commit
commit.manifest.min-count-to-merge = 50       # Merge when 50+ manifests

# Planning optimization
read.split.planning-lookback = 10             # Look-back for combining splits
```

```python
# Automated manifest maintenance (prevent planning degradation)
def maintain_manifests(table_name, max_manifests=500):
    current_count = get_manifest_count(table_name)
    if current_count > max_manifests:
        spark.sql(f"CALL prod.system.rewrite_manifests('{table_name}')")
```

---

## Issue #60: Full Table Scan Despite Partition Filter

**Severity:** P1 - High
**Frequency:** When partition transforms are misunderstood
**Affected Components:** Query performance, S3 costs (data scanned)
**First seen at:** Teams using hidden partitioning for first time

### Symptoms
```
- Query with WHERE clause scans ALL partitions
- Athena data scanned: 5TB (expected: 50GB for single day)
- Query plan shows no partition pruning applied
- Same filter works with Hive tables but not Iceberg
- EXPLAIN shows "residual filter" instead of "partition pruning"
```

### Root Cause
```
Hidden partition transforms require MATCHING filter expressions:

  Table partitioned by: days(event_timestamp)
  
  WORKS (partition pruning applied):
    WHERE event_timestamp >= '2024-01-15' AND event_timestamp < '2024-01-16'
    → Iceberg recognizes timestamp range → maps to partition → prunes
    
  DOES NOT WORK (full scan):
    WHERE DATE(event_timestamp) = '2024-01-15'
    → Iceberg sees function call (DATE()), can't map to partition transform
    
    WHERE CAST(event_timestamp AS DATE) = '2024-01-15'
    → Same problem: function wrapping prevents pruning
    
    WHERE event_date = '2024-01-15' (event_date is different column!)
    → Filtering on non-partition column = no partition pruning
    
  Common confusion:
    Partition spec: days(event_timestamp)
    User thinks: WHERE event_date = '...' should work
    Reality: must filter on event_timestamp directly with range predicates

  Engine-specific:
    Trino: better at recognizing transforms → more cases work
    Spark: requires exact match to partition expression
    Athena: depends on engine version (v3 better than v2)
```

### Immediate Fix
```sql
-- Instead of:
SELECT * FROM events WHERE DATE(event_timestamp) = '2024-01-15';  -- FULL SCAN!

-- Use:
SELECT * FROM events 
WHERE event_timestamp >= TIMESTAMP '2024-01-15 00:00:00'
  AND event_timestamp < TIMESTAMP '2024-01-16 00:00:00';  -- PARTITION PRUNED!

-- Or: Add explicit partition column for clarity
ALTER TABLE events ADD COLUMN event_date DATE;
-- Then partition by: identity(event_date)
-- Now: WHERE event_date = '2024-01-15' works directly
```

### Prevention
```
- Document partition-pruning-compatible filter patterns per table
- Integration tests that verify EXPLAIN shows partition pruning
- Lint SQL queries: flag function calls on partition columns
- Consider identity() partitioning for simpler filter semantics
- Train team: "always filter with direct comparison on partition source column"
```

---

## Issue #61: Column Statistics Not Used (Min/Max Pruning Disabled)

**Severity:** P2 - Medium
**Frequency:** On tables where column stats aren't properly configured
**Affected Components:** Data file pruning effectiveness
**First seen at:** Tables with disabled or missing column statistics

### Symptoms
```
- Query reads 1000 files when only 10 contain matching data
- EXPLAIN shows "data files: 1000" but actual matching rows from 10 files
- No file-level pruning despite filter on indexed column
- Performance similar whether filtering on high or low selectivity
- Compacted tables still read too many files
```

### Root Cause
```
Iceberg stores per-file column statistics in manifests:
  - min value per column per file
  - max value per column per file
  - null count per column per file
  
  Query: WHERE user_id = 'abc123'
  With stats: File1 (min=a, max=b) → SKIP, File2 (min=abc, max=abd) → READ
  Without stats: must read ALL files
  
  Stats can be missing because:
  1. write.metadata.metrics.default = 'none' (disabled!)
  2. Column has too many distinct values (stats not useful for hash-like)
  3. Old files written before stats were enabled
  4. Nested columns (struct fields) may not have stats
  5. Metrics mode 'counts' collects only null/row count (no min/max)
```

### Permanent Fix
```sql
-- Ensure column statistics are enabled
ALTER TABLE db.events SET TBLPROPERTIES (
  'write.metadata.metrics.default' = 'truncate(16)',  -- Keep first 16 bytes of min/max
  'write.metadata.metrics.column.event_id' = 'full',  -- Full stats for key columns
  'write.metadata.metrics.column.user_id' = 'truncate(36)',  -- UUID length
  'write.metadata.metrics.column.amount' = 'full',
  'write.metadata.metrics.column.large_text_column' = 'counts'  -- Only counts for large strings
);

-- Rewrite files to generate statistics for existing data
CALL prod.system.rewrite_data_files(
  table => 'db.events',
  strategy => 'binpack'
);
```

---

## Issue #62: Predicate Pushdown Not Working with Complex Filters

**Severity:** P2 - Medium
**Frequency:** With OR conditions, nested predicates, UDFs
**Affected Components:** Query performance (excess data scanned)
**First seen at:** Complex analytical queries

### Symptoms
```
- Simple WHERE user_id = X: scans 10 files (good)
- Complex WHERE user_id = X OR status = 'failed': scans ALL files (bad)
- Adding OR conditions kills performance
- Subqueries in WHERE prevent pushdown
- UDF in filter prevents all pruning
```

### Root Cause
```
Iceberg can only push down CERTAIN predicate patterns:

  SUPPORTED (pushed down to manifests):
    col = value
    col > value, col < value, col >= value, col <= value
    col IN (value1, value2, ...)
    col IS NULL, col IS NOT NULL
    AND combinations of above
    
  NOT SUPPORTED (residual filter, no pruning):
    col1 = value1 OR col2 = value2  (OR across different columns)
    function(col) = value            (function prevents pushdown)
    col LIKE '%pattern%'             (suffix/infix LIKE)
    col IN (subquery)                (subquery must be evaluated first)
    UDF(col) = value                 (opaque function)
    CASE WHEN ... THEN col END       (conditional expression)
    
  Partial pushdown:
    col1 = value1 AND (col2 = value2 OR col2 = value3)
    → col1 filter pushed down, col2 OR applied as residual
```

### Fix
```sql
-- Instead of OR across columns (no pushdown):
SELECT * FROM events WHERE user_id = 'abc' OR status = 'failed';

-- Rewrite as UNION ALL (each branch can push down):
SELECT * FROM events WHERE user_id = 'abc'
UNION ALL
SELECT * FROM events WHERE status = 'failed' AND user_id != 'abc';

-- Instead of function on column:
SELECT * FROM events WHERE YEAR(event_ts) = 2024;

-- Use range predicate:
SELECT * FROM events 
WHERE event_ts >= '2024-01-01' AND event_ts < '2025-01-01';
```

---

## Issue #63: Trino/Athena Coordinator OOM During Large Queries

**Severity:** P1 - High
**Frequency:** On queries touching millions of splits
**Affected Components:** Trino coordinator, query gateway
**First seen at:** Tables with 1M+ files queried without filters

### Symptoms
```
- Trino coordinator crashes: "java.lang.OutOfMemoryError"
- Athena query fails: "EXCEEDED_MEMORY_LIMIT"
- Query works on small table, fails on large table (same structure)
- Only coordinator OOM (workers are fine)
- Reducing query complexity doesn't help
```

### Root Cause
```
Coordinator must hold ALL split metadata in memory during planning:

  Table: 2M data files
  Each split metadata: ~2KB (file path, offset, length, partition info)
  Total: 2M × 2KB = 4GB in coordinator memory
  
  Default Trino coordinator heap: 16-32GB
  With multiple concurrent queries: 4GB × 10 = 40GB → OOM
  
  Planning generates split objects that live in coordinator memory
  until all splits are assigned to workers.
  
  Large unfiltered queries on big tables = coordinator memory bomb
```

### Immediate Fix
```sql
-- Add filters to reduce split count
-- Instead of full table scan:
SELECT * FROM big_table;

-- Add time filter (even if you want all data):
SELECT * FROM big_table WHERE event_date >= '2024-01-01';  -- reduces splits

-- Trino: limit splits per query
SET SESSION max_splits_per_node = 1000;
```

### Permanent Fix
```properties
# Trino coordinator sizing
coordinator.jvm.max-heap-size = 64G

# Split enumeration limits
query.max-splits-per-node = 5000
query.max-stage-count = 200

# Iceberg-specific Trino config (iceberg.properties)
iceberg.max-splits-per-scan = 100000
iceberg.split-manager-threads = 32
```

```
Additional strategies:
1. Compact tables (reduce file count → fewer splits)
2. Use partition pruning aggressively (reduce splits at plan time)
3. Set up query gates: reject queries that would scan >1M files
4. Materialize hot queries as summary tables
5. Scale coordinator memory proportional to largest table size
```

---

## Issue #64: Spark Vectorized Reader Not Used (Row-by-Row Reads)

**Severity:** P2 - Medium
**Frequency:** Misconfiguration or unsupported data types
**Affected Components:** Read throughput (3-5x slower)
**First seen at:** After schema changes that add unsupported types

### Symptoms
```
- Read throughput: 50MB/s (expected: 200MB/s with vectorized)
- Spark physical plan shows "ColumnarToRow" conversion
- CPU utilization high during reads (not I/O bound)
- Same data faster when read as plain Parquet (not through Iceberg)
- Performance regression after adding new columns
```

### Root Cause
```
Spark's vectorized Parquet reader operates on columnar batches (fast).
Falls back to row-by-row reader when:

  1. Complex types: MAP, ARRAY, STRUCT → no vectorized support (older Spark)
  2. Decimal with precision >18 → falls back
  3. Timestamp with timezone → implementation-dependent
  4. Delete files present (MoR) → falls back to row-level for delete application
  5. Schema evolution active (reading old files with new schema) → some cases fallback
  
  Vectorized: reads 4096 rows at once in columnar format → SIMD/cache friendly
  Row-by-row: reads 1 row at a time → 5-10x slower
  
  With delete files (MoR):
    Must apply deletes row-by-row (check each row against delete set)
    Vectorized batch invalidated → entire read falls back
```

### Fix
```properties
# Force vectorized reader (Spark 3.3+)
spark.sql.iceberg.vectorization.enabled = true

# For tables with delete files: compact to eliminate deletes
# Then vectorized reader works again
CALL prod.system.rewrite_data_files(
  table => 'db.table',
  options => map('delete-file-threshold', '1')
);

# Spark settings for vectorized Parquet
spark.sql.parquet.enableVectorizedReader = true
spark.sql.inMemoryColumnarStorage.batchSize = 4096
```

---

## Issue #65: Time Travel Queries Increasingly Slow Over Time

**Severity:** P2 - Medium
**Frequency:** As tables age and accumulate history
**Affected Components:** Audit queries, historical analysis
**First seen at:** Tables with 1000+ snapshots

### Symptoms
```
- Query current snapshot: 5 seconds
- Query snapshot from 1 month ago: 2 minutes
- Query snapshot from 6 months ago: 10 minutes
- Historical query performance degrades linearly with age
- Same data volume but older = slower
```

### Root Cause
```
Time travel to old snapshot requires loading OLD manifests:

  Current snapshot (snap-1000):
    → Reads manifest list v1000 → points to 100 optimized manifests
    → These manifests point to compacted, well-organized files
    
  Old snapshot (snap-100):
    → Reads manifest list v100 → points to 5000 old manifests (pre-compaction!)
    → These manifests point to thousands of small files (pre-compaction state)
    → Old manifests may reference files that still exist but are suboptimal
    
  The old snapshot sees the table AS IT WAS:
    - Small files (before compaction)
    - Many manifests (before rewrite)
    - Poor statistics (before optimization)
    
  You're querying the table in its HISTORICAL (unoptimized) state!
  All maintenance improvements only apply to NEW snapshots.
```

### Fix
```sql
-- For audit/compliance: create optimized snapshots before expiring old ones
-- Tag important historical points AFTER compaction:
CALL prod.system.rewrite_data_files(table => 'db.table', strategy => 'binpack');
ALTER TABLE db.table CREATE TAG `audit-2024-q1` AS OF VERSION 1234;

-- Now time travel to tag (which references optimized state):
SELECT * FROM db.table VERSION AS OF 'audit-2024-q1';
```

```
Strategy:
1. Create periodic "optimized checkpoints" (tags after compaction)
2. Use tags for audit queries (not raw snapshots)
3. For regulatory: export snapshot to separate table (always optimized)
4. Accept: very old snapshots will be slow (that's the tradeoff)
```

---

## Issue #66: Athena Query Timeout on Large Iceberg Tables

**Severity:** P1 - High
**Frequency:** On tables >1TB with complex queries
**Affected Components:** Athena serverless queries
**First seen at:** After migrating from Hive to Iceberg on Athena

### Symptoms
```
- Athena query timeout (30 minute limit)
- "Query exhausted resources at this scale factor"
- Simple queries work, JOINs or aggregations timeout
- Same query in Trino/Spark succeeds (just takes 10 min)
- Athena engine v3 works better than v2 for Iceberg
```

### Root Cause
```
Athena limitations with Iceberg:

  1. Fixed timeout: 30 minutes max query runtime
  2. Memory limits: per-query memory cap (not configurable)
  3. Limited parallelism: cannot scale like EMR Spark
  4. Planning overhead: Athena's Iceberg support less optimized than native Trino
  5. No caching: every query re-reads all metadata from S3
  
  Athena works well for:
    - Queries touching <100GB of data
    - Simple filters with good partition pruning
    - SELECT on pre-aggregated tables
    
  Athena struggles with:
    - Full table scans on TB+ tables
    - Complex JOINs across large tables
    - Queries requiring millions of files
```

### Permanent Fix
```
1. Pre-aggregate for Athena:
   - Create summary/materialized tables for common queries
   - Athena queries summary (small) not raw (large)
   
2. Optimize table for Athena:
   - Compact to fewer, larger files (less planning overhead)
   - Use partition pruning aggressively
   - Pre-compute derived columns (avoid runtime computation)
   
3. Use Athena engine v3 (better Iceberg support):
   - workgroup settings: engine version = Athena engine version 3
   
4. For complex queries: use Trino/Spark instead:
   - Route complex queries to EMR/Trino cluster
   - Athena for simple, ad-hoc queries only
```

---

## Issue #67: Row-Level Filter Pushdown Not Reaching Parquet Row Groups

**Severity:** P2 - Medium
**Frequency:** When row-group-level pruning isn't configured
**Affected Components:** I/O reduction within files
**First seen at:** Large files (256MB+) with poor internal statistics

### Symptoms
```
- File-level pruning works (reads 10 files instead of 1000)
- But still reads entire 256MB file for 100 matching rows
- Row-group statistics not used for intra-file filtering
- Parquet footer shows no min/max per row group
- Read amplification within files: read 256MB, return 1KB
```

### Root Cause
```
Two levels of statistics:

  Level 1: Iceberg manifest (file-level min/max)
    → Prunes which FILES to read ✓ (usually working)
    
  Level 2: Parquet row-group statistics (within-file min/max)
    → Prunes which ROW GROUPS to read within a file ✗ (often not working)
    
  Parquet file with 256MB and 8 row groups (32MB each):
    Row group 1: user_id [a-d]
    Row group 2: user_id [e-h]
    ...
    Row group 8: user_id [u-z]
    
    Query: WHERE user_id = 'a123'
    With row-group stats: read only row group 1 (32MB)
    Without: read entire file (256MB) → 8x overhead
    
  Row-group stats missing when:
    - Writer doesn't enable Parquet statistics
    - Data not sorted within file (stats useless if overlapping)
    - String columns with truncated stats (can't prune)
    - Writer uses old Parquet library
```

### Fix
```properties
# Enable Parquet statistics writing
write.parquet.row-group-size-bytes = 33554432  # 32MB row groups
write.parquet.page-row-limit = 20000
spark.sql.parquet.filterPushdown = true
spark.sql.parquet.enableVectorizedReader = true

# SORT data within files for effective row-group pruning
ALTER TABLE db.table WRITE ORDERED BY user_id;
```

---

## Issue #68: JOIN Performance Degradation (Broadcast vs Shuffle)

**Severity:** P2 - Medium
**Frequency:** JOINs between Iceberg tables
**Affected Components:** Query latency for JOIN queries
**First seen at:** Star schema queries joining fact + dimensions

### Symptoms
```
- JOIN takes 10 minutes (dimension lookup should be instant)
- Spark chooses shuffle-hash-join instead of broadcast
- Small dimension table (100MB) not broadcasted
- Query plan shows "SortMergeJoin" for all JOINs
- AQE (Adaptive Query Execution) not kicking in for Iceberg
```

### Root Cause
```
Iceberg tables may not report accurate size statistics:

  Spark broadcast threshold: 10MB (default)
  
  Hive table: metastore knows exact table size → broadcasts small tables
  Iceberg table: size may not be reported to Spark optimizer
    → Spark assumes large table → uses shuffle join (expensive)
    
  Also: Iceberg's table size includes ALL snapshots (not just current)
  Reported size: 500MB (includes historical data)
  Actual current size: 50MB (could be broadcasted!)
  
  AQE limitation:
    AQE can convert to broadcast AFTER shuffle starts
    But initial plan was already shuffle → partial optimization only
```

### Fix
```python
# Force broadcast for known small tables
from pyspark.sql.functions import broadcast

result = fact_df.join(
    broadcast(dim_df),  # Force broadcast
    "customer_id"
)

# Or set broadcast threshold higher
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "100MB")

# Or use table stats hint
spark.sql("""
    SELECT /*+ BROADCAST(dim) */ f.*, d.name
    FROM fact f JOIN dim d ON f.dim_id = d.id
""")
```

---

## Issue #69: Metadata Column Queries Scanning All Data

**Severity:** P2 - Medium
**Frequency:** When querying _file, _pos, _partition metadata columns
**Affected Components:** Metadata-only queries performance
**First seen at:** Debugging and monitoring queries

### Symptoms
```
- SELECT _file, COUNT(*) GROUP BY _file → scans all data
- Querying _partition values reads data files (not just manifests)
- Monitoring queries (file counts, partition stats) are expensive
- Expected: metadata query = fast. Reality: as slow as full scan
```

### Root Cause
```
Iceberg metadata columns:
  _file: file path (available in manifests without reading data)
  _pos: row position (requires reading data)
  _partition: partition values (available in manifests)
  _spec_id: partition spec ID
  
  However: not all engines optimize metadata-only queries.
  
  Trino: CAN answer _file and _partition from manifests alone (fast)
  Spark: MAY still open data files depending on query structure
  Athena: Often reads data files for metadata columns
  
  Query: SELECT DISTINCT _partition FROM table
  Optimal: read manifests only (partition values stored there)
  Actual: depends on engine optimization level
```

### Fix
```sql
-- Use system tables instead of metadata columns for monitoring:
-- These are metadata-only (never read data files):

-- File information:
SELECT * FROM prod.db.table.files;

-- Partition information:  
SELECT * FROM prod.db.table.partitions;

-- Snapshot history:
SELECT * FROM prod.db.table.snapshots;

-- Manifest information:
SELECT * FROM prod.db.table.manifests;

-- These are always fast (metadata-only reads)
```

---

## Issue #70: Query Cache Invalidation Storm After Compaction

**Severity:** P2 - Medium
**Frequency:** After every compaction commit
**Affected Components:** Query engine caches, dashboard latency
**First seen at:** Trino deployments with metadata caching

### Symptoms
```
- After compaction: all cached query results invalidated
- Dashboard queries spike (all cache misses)
- Trino "cold start" every time compaction runs
- Query latency: 1s (cached) → 30s (cache miss after compaction)
- Compaction every 15 min = cache never warm
```

### Root Cause
```
Compaction creates a new snapshot (new metadata):

  Before compaction: Snapshot v100 (queries cached against v100)
  After compaction: Snapshot v101 (same data, different files)
  
  Query cache key includes snapshot ID or metadata location.
  New snapshot = ALL caches invalidated (even though data unchanged!)
  
  This is correct behavior (snapshot changed) but operationally painful.
  Compaction doesn't change DATA but changes FILE LAYOUT.
  Cached results are still valid but cache doesn't know that.
```

### Permanent Fix
```
1. Compaction-aware caching:
   - Cache key = hash of query + table schema + partition filter
   - NOT snapshot ID (snapshot changes on compaction but data doesn't)
   - Custom cache invalidation: only invalidate on DATA changes
   
2. Separate read snapshot from compaction:
   - Pin read snapshot for dashboards (explicit version)
   - Compaction creates new snapshot but reads stay on old
   - Periodically advance read snapshot (controlled cache invalidation)
   
3. Warm cache after compaction:
   - Compaction completes → trigger cache warming queries
   - Pre-populate cache with common dashboard queries
   
4. Reduce compaction frequency during peak query hours:
   - Compact during off-peak (2 AM - 6 AM)
   - Peak hours: no compaction = stable cache
```

---

## Issue #71: Partition Filter Required But Not Enforced (Cost Explosion)

**Severity:** P1 - High
**Frequency:** When ad-hoc users query without filters
**Affected Components:** Athena/Trino costs, S3 costs
**First seen at:** Self-service analytics environments

### Symptoms
```
- Athena bill: $50K/month (expected: $5K)
- Users running: SELECT * FROM events (no WHERE clause)
- Single query scans 50TB of data (costs $250 on Athena)
- No guardrails preventing full table scans
- Education doesn't work (users forget/don't care about filters)
```

### Root Cause
```
Iceberg tables allow unrestricted queries:
  - No enforced partition filter requirement
  - Users can scan entire table history
  - ad-hoc tools (notebooks, BI) often omit filters
  - Athena pricing: $5/TB scanned = expensive full scans
```

### Permanent Fix
```sql
-- Trino: enforce partition filter
-- In Trino's iceberg.properties:
-- iceberg.require-filters-on-partition-columns = true

-- Or use Trino resource groups to limit scan:
-- Max data scanned per query = 100GB
-- Reject queries exceeding limit
```

```python
# Query gateway/proxy that rejects filterless queries:
class IcebergQueryGateway:
    REQUIRE_FILTER_TABLES = ['events', 'transactions', 'user_actions']
    MAX_SCAN_TB = 1  # Maximum 1TB per query
    
    def validate_query(self, sql, table_name):
        if table_name in self.REQUIRE_FILTER_TABLES:
            if not self.has_partition_filter(sql, table_name):
                raise QueryRejectedException(
                    f"Query on {table_name} requires partition filter. "
                    f"Add WHERE event_date >= ... to your query."
                )
```

---

## Issue #72: Read Amplification from Excessive Schema Evolution

**Severity:** P2 - Medium
**Frequency:** Tables with 50+ schema versions
**Affected Components:** Read performance, memory usage
**First seen at:** Tables that evolve schema weekly

### Symptoms
```
- Reading table requires loading 50+ schema versions
- Type promotion (int→long) causes extra computation per row
- New columns return NULL for 90% of files (wasteful projection)
- Reader memory higher than expected (multiple schema objects)
- Performance regression proportional to number of schema changes
```

### Root Cause
```
Each schema version in metadata must be available for reading old files:

  Schema v1: {user_id: int, name: string}           (files from 2022)
  Schema v2: {user_id: long, name: string}          (type promotion)
  Schema v3: {user_id: long, name: string, email: string}
  ...
  Schema v50: {user_id: long, name: string, email: string, ... 50 columns}
  
  Reading file written with v1 using schema v50:
    - Map column IDs: v1.user_id(id=1) → v50.user_id(id=1)
    - Type promote: int → long (computation per row)
    - Fill NULLs: 48 new columns all NULL for this file
    - Project: requested columns only
    
  With 50 schema versions across 100K files:
    Reader must determine which schema applies to each file
    Apply appropriate projection/promotion for each file batch
    Memory: hold schema mapping for each variant
```

### Fix
```
1. Periodic full rewrite (migrates all files to current schema):
   CALL prod.system.rewrite_data_files(table => 'db.table', strategy => 'binpack');
   
   After rewrite: all files are in latest schema
   → No more type promotion at read time
   → No more NULL fills for new columns
   → Faster reads

2. Batch schema changes (evolve less frequently):
   - Instead of 50 changes over 2 years: batch into quarterly releases
   - Each release: evolve schema + compact all data to new schema
   
3. Monitor schema version count:
   - Alert when schema versions > 20
   - Trigger full rewrite to consolidate
```

---

## Summary: Query Performance & Planning Issues

| # | Issue | Severity | Key Fix |
|---|-------|----------|---------|
| 59 | Planning slower than execution | P1 | rewrite_manifests + planning threads |
| 60 | Full scan despite partition filter | P1 | Use range predicates on partition source column |
| 61 | Column statistics not used | P2 | Enable metrics + rewrite files |
| 62 | Complex predicates not pushed down | P2 | Rewrite as AND/UNION patterns |
| 63 | Coordinator OOM on large queries | P1 | Compact + coordinator memory + limits |
| 64 | Vectorized reader not used | P2 | Compact to remove delete files |
| 65 | Time travel queries slow | P2 | Create optimized tags for audit |
| 66 | Athena timeout | P1 | Pre-aggregate + engine v3 |
| 67 | Row-group pruning not working | P2 | WRITE ORDERED BY + stats enabled |
| 68 | JOIN broadcast not triggered | P2 | Explicit broadcast hint + threshold |
| 69 | Metadata column queries slow | P2 | Use system tables (.files, .partitions) |
| 70 | Cache invalidation after compaction | P2 | Compaction-aware cache + off-peak schedule |
| 71 | Full scan cost explosion | P1 | Query gateway + enforced filters |
| 72 | Schema evolution read amplification | P2 | Periodic full rewrite |
