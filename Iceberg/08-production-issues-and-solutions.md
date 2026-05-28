# Production Issues with Apache Iceberg and How to Solve Them

Iceberg solves the raw S3 problems elegantly — but running it at scale introduces its own
operational challenges. These are the issues teams hit in production after the first few months.

---

## Issue 1: Small File Accumulation

### The Problem

```
Streaming pipeline (Flink/Spark Structured Streaming):
  - Commits every 30 seconds
  - Each commit writes 1-10 small Parquet files (1-5 MB each)
  - After 30 days: 2.5 million tiny files

Query performance degrades because:
  - Each file = 1 S3 GET request (network overhead dominates)
  - Parquet metadata per file is disproportionately large
  - Manifest files grow enormous (tracking millions of entries)
  - Query planning scans millions of manifest entries

Symptom: Queries that took 5 seconds now take 3 minutes.
```

### The Solution

```sql
-- Approach 1: Periodic compaction (recommended for most cases)
-- Run as a scheduled job every 1-6 hours

CALL system.rewrite_data_files(
  table => 'db.events',
  strategy => 'binpack',
  options => map(
    'target-file-size-bytes', '536870912',  -- 512 MB target
    'min-file-size-bytes', '67108864',       -- skip files > 64 MB
    'max-file-size-bytes', '1073741824',     -- cap at 1 GB
    'min-input-files', '5',                  -- only compact if 5+ small files
    'partial-progress.enabled', 'true',      -- commit progress incrementally
    'partial-progress.max-commits', '10'     -- avoid one massive commit
  )
);

-- Approach 2: Sort-order compaction (better for range queries)
CALL system.rewrite_data_files(
  table => 'db.events',
  strategy => 'sort',
  sort_order => 'event_date ASC, user_id ASC',
  where => 'event_date >= current_date - interval 7 days'
);
```

### Operational Best Practices

```
┌─────────────────────────────────────────────────────────┐
│  Compaction Strategy Decision Tree                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Is the table write-heavy (streaming)?                  │
│    YES → Run compaction every 1-2 hours                 │
│    NO  → Run compaction daily                           │
│                                                         │
│  Do queries use range filters (date, ID ranges)?        │
│    YES → Use 'sort' strategy on filter columns          │
│    NO  → Use 'binpack' (faster, less resource-heavy)    │
│                                                         │
│  Is the table > 10 TB?                                  │
│    YES → Compact only recent partitions (WHERE clause)  │
│    NO  → Compact entire table                           │
│                                                         │
│  Target file size:                                      │
│    HDFS → 256 MB - 512 MB                               │
│    S3   → 512 MB - 1 GB (fewer S3 GETs = better)       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Issue 2: Metadata and Snapshot Bloat

### The Problem

```
Every commit creates:
  1. A new snapshot (points to manifest list)
  2. A new manifest list file
  3. One or more new manifest files
  4. Updated metadata.json

After 100,000 commits:
  - metadata.json is 500 MB+ (contains ALL snapshot history)
  - Manifest list has thousands of entries
  - Opening the table takes 30+ seconds (just to parse metadata)
  - S3 GET for metadata.json costs real money at scale

Timeline of degradation:
  Day 1:   metadata.json = 5 KB,   table open = 50ms
  Day 30:  metadata.json = 50 MB,  table open = 3s
  Day 90:  metadata.json = 200 MB, table open = 15s
  Day 180: metadata.json = 500 MB, table open = 45s (queries time out)
```

### The Solution

```sql
-- 1. Expire old snapshots (keep only last 5 days)
CALL system.expire_snapshots(
  table => 'db.events',
  older_than => TIMESTAMP '2026-01-10 00:00:00',
  retain_last => 10,        -- always keep at least 10 snapshots
  max_concurrent_deletes => 50  -- throttle S3 delete calls
);

-- 2. Remove orphan files (files not referenced by any snapshot)
CALL system.remove_orphan_files(
  table => 'db.events',
  older_than => TIMESTAMP '2026-01-08 00:00:00',  -- 3-day safety buffer
  dry_run => true  -- ALWAYS dry run first!
);

-- 3. Rewrite manifests to reduce metadata file count
CALL system.rewrite_manifests('db.events');
```

### Configuration to Prevent Bloat

```properties
# Table properties to set at creation time:

# Automatically clean metadata (Spark/Flink will run this on commit)
write.metadata.delete-after-commit.enabled=true
write.metadata.previous-versions-max=100

# Limit snapshot retention
history.expire.max-snapshot-age-ms=432000000  # 5 days
history.expire.min-snapshots-to-keep=10

# Limit metadata.json size
write.metadata.metrics.max-inferred-column-defaults=100
```

### Scheduled Maintenance Job

```
┌─────────────────────────────────────────────────────────┐
│  Recommended Maintenance Schedule                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Every 1-2 hours:  Compaction (streaming tables only)   │
│  Every 6 hours:    expire_snapshots (high-write tables) │
│  Daily:            expire_snapshots (all tables)        │
│  Daily:            rewrite_manifests (if > 1000 files)  │
│  Weekly:           remove_orphan_files (with dry_run)   │
│  Monthly:          Review table sizes and partition     │
│                    strategies                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Issue 3: Orphan Files from Failed Writes

### The Problem

```
What happens during a failed write:

  T0: Spark job starts writing
  T1: Writes data-file-001.parquet to S3  → SUCCESS (file exists in S3)
  T2: Writes data-file-002.parquet to S3  → SUCCESS (file exists in S3)
  T3: Job crashes (OOM, node failure, timeout)
  T4: Commit never happens → metadata never updated

Result:
  - data-file-001.parquet exists in S3 but is NOT referenced by any snapshot
  - data-file-002.parquet exists in S3 but is NOT referenced by any snapshot
  - These are "orphan files" — they cost storage money forever
  - Over time: terabytes of orphan files accumulate

At Netflix scale:
  - ~5% of write jobs fail on any given day
  - Each failure leaves 10-100 orphan files
  - After 1 year: 500 TB of unreferenced orphan data ($$$)
```

### The Solution

```sql
-- Step 1: ALWAYS dry run first to see what would be deleted
CALL system.remove_orphan_files(
  table => 'db.events',
  older_than => TIMESTAMP '2026-01-20 00:00:00',  -- 7-day buffer
  dry_run => true
);
-- Review the output: are these really orphans?

-- Step 2: Actually delete (with safety buffer)
CALL system.remove_orphan_files(
  table => 'db.events',
  older_than => TIMESTAMP '2026-01-20 00:00:00',
  location => 's3://bucket/warehouse/db/events/data',
  max_concurrent_deletes => 100
);
```

### Critical Safety Rules

```
⚠️  DANGER: remove_orphan_files can DELETE VALID DATA if misconfigured

Safety checklist:
  □ older_than is AT LEAST 3 days in the past
    (in-progress jobs may have written files not yet committed)
  □ No long-running write jobs are active on the table
  □ No pending Flink checkpoints reference uncommitted files
  □ You ran dry_run => true first and verified the file list
  □ You have a recent snapshot you can roll back to

Common mistakes:
  ✗ Setting older_than to "now" → deletes files from in-progress jobs
  ✗ Running while Flink is checkpointing → corrupts Flink state
  ✗ Not checking if files belong to a different table at the same path
```

---

## Issue 4: Write Conflicts and Retry Storms

### The Problem

```
Optimistic Concurrency in action:

  Writer A reads metadata v5, starts working
  Writer B reads metadata v5, starts working
  Writer A commits → v5 → v6 (SUCCESS)
  Writer B tries to commit → expects v5, finds v6 → CONFLICT → RETRY
  Writer B re-reads v6, redoes work, tries again

When this goes wrong (many concurrent writers):

  10 writers all read v5 simultaneously
  Writer 1 commits v5 → v6
  Writers 2-10 all conflict, retry
  Writer 2 commits v6 → v7
  Writers 3-10 all conflict, retry AGAIN
  Writer 3 commits v7 → v8
  ...
  Writer 10: retried 9 times, each time redoing ALL its work

Result: exponential compute waste, "retry storms"
Symptoms: Spark jobs that should take 5 min take 2 hours
```

### The Solution

```
Strategy 1: Reduce contention with partitioned commits

  Instead of:
    All writers commit to the same table simultaneously

  Do:
    - Partition writes so each writer targets different partitions
    - Use Iceberg's row-level conflict detection:
      Writers to partition A don't conflict with writers to partition B

  Example:
    Writer 1 → writes only partition event_date='2026-01-15'
    Writer 2 → writes only partition event_date='2026-01-16'
    → No conflict because they touch different partition specs

Strategy 2: Serialization with a write queue

  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
  │ Writer Jobs  │────→│ Queue (SQS)  │────→│ Single Commit│
  │ (parallel)  │     │              │     │   Worker     │
  └─────────────┘     └──────────────┘     └──────────────┘

  - Writers produce data files in parallel (the expensive part)
  - A single commit worker reads from the queue and commits sequentially
  - Zero conflicts because only one process commits at a time
  - Data file production is still fully parallel

Strategy 3: Exponential backoff with jitter

  On conflict:
    retry_delay = min(base_delay * 2^attempt + random_jitter, max_delay)

  Example: base=1s, max=60s
    Attempt 1: wait 1-2s
    Attempt 2: wait 2-4s
    Attempt 3: wait 4-8s
    Attempt 4: wait 8-16s
    Max: 60s

  Table property:
    commit.retry.num-retries=4
    commit.retry.min-wait-ms=1000
    commit.retry.max-wait-ms=60000
```

---

## Issue 5: S3 Rate Limiting and Throttling

### The Problem

```
S3 rate limits per prefix:
  - 5,500 GET/HEAD requests per second per prefix
  - 3,500 PUT/POST/DELETE requests per second per prefix

When Iceberg hits these limits:
  - Large queries that open 5000+ data files simultaneously → GET throttled
  - Compaction that deletes 10,000 files → DELETE throttled
  - Listing for orphan cleanup on deep prefix trees → LIST throttled

S3 returns: HTTP 503 Slow Down

Impact:
  - Queries fail intermittently with "SlowDown" errors
  - Compaction jobs stall or fail
  - Metadata operations time out
```

### The Solution

```
1. Use hash-prefixed object keys (Iceberg does this by default in v2):

   BAD:  s3://bucket/warehouse/db/events/data/2026/01/15/part-00001.parquet
   GOOD: s3://bucket/warehouse/db/events/data/a3f2/2026-01-15/part-00001.parquet

   The random hash prefix distributes files across S3 partitions.
   Iceberg generates ObjectStoreLocationProvider paths that include a hash.

2. Configure write properties:
   
   -- Use the ObjectStore location provider (adds hash prefix)
   ALTER TABLE db.events SET TBLPROPERTIES (
     'write.object-storage.enabled' = 'true',
     'write.data.path' = 's3://bucket/warehouse/db/events/data'
   );

3. Throttle concurrent operations:

   -- Limit parallel file reads during query planning
   spark.sql.sources.parallelPartitionDiscovery.parallelism=64

   -- Limit concurrent S3 deletes during cleanup
   CALL system.expire_snapshots(
     table => 'db.events',
     max_concurrent_deletes => 50  -- don't fire 10,000 deletes at once
   );

4. Use S3 request partitioning:
   
   If all data is under one prefix, request prefix partitioning from AWS:
   - Open a support ticket
   - AWS pre-partitions the prefix for higher throughput
   - No code changes needed

5. Use S3 Express One Zone for metadata:
   
   - Store metadata files in S3 Express (10x lower latency)
   - Store data files in regular S3 (cheaper)
   - Configure Iceberg to use different paths for metadata vs data
```

---

## Issue 6: OOM During Query Planning on Large Tables

### The Problem

```
Query planning process:
  1. Read metadata.json (could be 200 MB)
  2. Parse ALL manifest list entries (could be 50,000 manifests)
  3. Open relevant manifests and check per-file statistics
  4. Build query plan in memory

For a table with 10 million files:
  - Manifest metadata alone: 5-10 GB in memory
  - Spark driver with 4 GB heap → OOM
  - Trino coordinator with 8 GB → OOM on complex queries

Error: java.lang.OutOfMemoryError: Java heap space
  at org.apache.iceberg.ManifestReader.read()
```

### The Solution

```
1. Increase driver/coordinator memory (short-term fix):

   # Spark
   spark.driver.memory=16g
   spark.driver.memoryOverhead=4g

   # Trino
   query.max-memory-per-node=16GB

2. Reduce manifest count with rewrite_manifests (real fix):

   CALL system.rewrite_manifests('db.events');
   -- Combines many small manifests into fewer large ones
   -- 50,000 manifests → 500 manifests
   -- Dramatically reduces planning memory

3. Use manifest filtering effectively:

   -- Ensure partition spec matches your common query patterns
   -- If you always filter by date, partition by date
   -- Iceberg skips entire manifests based on partition bounds

4. Configure manifest size limits:

   ALTER TABLE db.events SET TBLPROPERTIES (
     'commit.manifest.target-size-bytes' = '8388608',  -- 8 MB per manifest
     'commit.manifest-merge.enabled' = 'true'          -- auto-merge small manifests
   );

5. Use metadata caching:

   # Spark conf
   spark.sql.catalog.my_catalog.cache-enabled=true
   spark.sql.catalog.my_catalog.cache.expiration-interval-ms=300000

   # Avoids re-reading metadata.json on every query
```

---

## Issue 7: Slow Compaction Blocking Writers

### The Problem

```
Compaction runs as a normal Iceberg commit:
  1. Reads small files A, B, C, D, E
  2. Writes new large file F
  3. Commits: {remove: [A,B,C,D,E], add: [F]}

If compaction takes 2 hours on a large partition:
  - Other writers that touch the same partition conflict
  - They must retry after compaction finishes
  - During compaction, write latency spikes

Additionally:
  - If compaction fails halfway, it retries from scratch (wasted compute)
  - Large compaction jobs hold significant memory (reading many files)
```

### The Solution

```
1. Use partial-progress commits (break large compaction into chunks):

   CALL system.rewrite_data_files(
     table => 'db.events',
     options => map(
       'partial-progress.enabled', 'true',
       'partial-progress.max-commits', '20',  -- commit every N file groups
       'max-file-group-size-bytes', '10737418240'  -- 10 GB per group
     )
   );

   Instead of one 2-hour commit, you get 20 small commits over 2 hours.
   Each commit is independent — if compaction fails at commit 15,
   the first 14 are already done.

2. Scope compaction to avoid writer conflicts:

   -- Only compact partitions that are NOT being actively written
   CALL system.rewrite_data_files(
     table => 'db.events',
     where => 'event_date < current_date - interval 1 day'
     -- Active streaming writes go to today's partition
     -- Compaction only touches yesterday and older
   );

3. Time-box compaction to off-peak hours:

   ┌────────────────────────────────────────────────────────┐
   │ 00:00-06:00: Heavy compaction (batch window)           │
   │ 06:00-23:59: Light compaction (only critical tables)   │
   │                                                        │
   │ Never compact a partition while it's being written to  │
   └────────────────────────────────────────────────────────┘

4. Use separate clusters for compaction:

   - Dedicated Spark cluster for maintenance jobs
   - Production cluster handles queries and streaming writes
   - Maintenance cluster handles compaction, snapshot expiry, orphan cleanup
   - They don't compete for the same resources
```

---

## Issue 8: Snapshot Expiry vs Time Travel Retention

### The Problem

```
Tension:
  - Data engineers want 30-day time travel for debugging
  - Finance team needs quarterly snapshots for auditing
  - Storage costs grow linearly with snapshot retention
  - More snapshots = more metadata = slower planning

Real scenario:
  Table: 10 TB of data, 100 commits/day
  30-day retention: 3,000 snapshots, metadata = 500 MB
  Storage overhead: old data files kept alive by old snapshots = +4 TB

  Cost: $92/month extra in S3 storage just for time travel
  Plus: query planning is 10x slower due to metadata size
```

### The Solution

```
1. Tiered snapshot retention:

   -- Keep hourly snapshots for 2 days (debugging)
   -- Keep daily snapshots for 30 days (operational recovery)
   -- Keep monthly snapshots for 1 year (audit compliance)

   Implementation:
   Step 1: Set default retention to 2 days
     history.expire.max-snapshot-age-ms=172800000  # 2 days

   Step 2: Tag important snapshots before expiry
     ALTER TABLE db.events CREATE TAG `daily_2026_01_15`
       AS OF VERSION 12345;
     ALTER TABLE db.events CREATE TAG `monthly_2026_01`
       AS OF VERSION 12300;

   Step 3: Tags survive snapshot expiry
     -- After expire_snapshots runs, tagged snapshots are preserved
     -- Query tagged snapshots:
     SELECT * FROM db.events VERSION AS OF 'monthly_2026_01';

2. Archive old data files to cheaper storage:

   -- Use S3 Intelligent-Tiering or Glacier for files only referenced
   -- by tagged/audit snapshots
   -- Iceberg doesn't care about S3 storage class — it just does GET

3. Separate hot and cold tables:

   -- Hot table: last 7 days, aggressive snapshot expiry
   -- Cold table: older data, minimal snapshots, compressed
   -- Queries use UNION ALL across both when needed
```

---

## Issue 9: Catalog Availability and Single Points of Failure

### The Problem

```
The catalog is the entry point to every Iceberg table:
  Query → Catalog → "Where is metadata.json?" → Read table

If the catalog is down:
  - NO queries can run (can't find metadata location)
  - NO writes can commit (can't update metadata pointer)
  - ENTIRE data platform is offline

Common catalog failures:
  - Hive Metastore (HMS): MySQL backend goes down, connection pool exhausted
  - AWS Glue: AWS service degradation, API throttling
  - Nessie: Single-instance deployment crashes
  - REST catalog: Service unavailable, load balancer timeout
```

### The Solution

```
1. Choose a highly-available catalog:

   ┌──────────────────────────────────────────────────────────┐
   │ Catalog         │ HA Strategy            │ Risk Level    │
   ├──────────────────────────────────────────────────────────┤
   │ AWS Glue        │ Managed by AWS         │ Low (SLA)     │
   │ Hive Metastore  │ Multi-instance + MySQL │ Medium        │
   │                 │   replication          │               │
   │ Nessie          │ Stateless + DB backend │ Medium        │
   │ REST Catalog    │ Multi-instance + LB    │ Depends       │
   │ Hadoop Catalog  │ None (HDFS only)       │ High          │
   └──────────────────────────────────────────────────────────┘

2. For Hive Metastore HA:

   - Run 3+ HMS instances behind a load balancer
   - Backend: Aurora MySQL with Multi-AZ (auto failover)
   - Connection pooling: HikariCP with health checks
   - Monitor: connection count, query latency, lock contention

3. Cache catalog lookups:

   # Spark conf — cache table metadata for 5 minutes
   spark.sql.catalog.my_catalog.cache-enabled=true
   spark.sql.catalog.my_catalog.cache.expiration-interval-ms=300000

   # If catalog is briefly unavailable, cached metadata still works for reads
   # Writers still need catalog access for commits

4. Fallback strategy:

   -- If using REST catalog, configure a fallback:
   spark.sql.catalog.my_catalog.uri=https://primary-catalog.internal
   spark.sql.catalog.my_catalog.uri.fallback=https://secondary-catalog.internal

5. Monitor catalog health:

   Alerts to set:
     - Catalog response time p99 > 500ms
     - Catalog error rate > 1%
     - Catalog connection pool utilization > 80%
     - Any table commit taking > 30 seconds
```

---

## Issue 10: Migration Pitfalls (Hive → Iceberg)

### The Problem

```
Migrating existing Hive/raw Parquet tables to Iceberg:

  Attempt 1: "In-place migrate" (convert existing table)
    CALL system.migrate('hive_db.large_table');
    
    What happens:
      - Iceberg scans ALL existing files to build manifests
      - For a 50 TB table with 500,000 files: takes 2-4 hours
      - During migration: table is UNAVAILABLE for reads/writes
      - If it fails midway: table is in an inconsistent state
      
  Attempt 2: "CTAS" (Create Table As Select)
    CREATE TABLE iceberg_db.large_table AS SELECT * FROM hive_db.large_table;
    
    What happens:
      - Reads entire 50 TB table and rewrites it
      - Takes 6-12 hours, costs $$$ in compute
      - You now have 100 TB stored (old + new) until you drop the old table
      - Risk: data drift during the copy window

  Common migration failures:
    - OOM building manifest for 500K files
    - Partition values with special characters break manifest parsing
    - Timestamps in different zones cause silent data corruption
    - Downstream jobs break because table location changed
```

### The Solution

```
Strategy 1: In-place migration (best for small-medium tables < 5 TB)

  -- Step 1: Stop all writers
  -- Step 2: Migrate
  CALL system.migrate('hive_db.events');
  -- Step 3: Verify
  SELECT count(*) FROM iceberg_db.events;
  -- Step 4: Update downstream consumers to point to new table
  -- Step 5: Resume writers (now using Iceberg-aware writer)

Strategy 2: Shadow migration (best for large tables)

  -- Phase 1: Create Iceberg table, dual-write new data to both
  CREATE TABLE iceberg_db.events LIKE hive_db.events;
  -- Configure pipeline to write to BOTH tables

  -- Phase 2: Backfill historical data (partition by partition)
  INSERT INTO iceberg_db.events
  SELECT * FROM hive_db.events
  WHERE event_date BETWEEN '2025-01-01' AND '2025-03-31';
  -- Repeat for each quarter, verify counts match

  -- Phase 3: Validate
  -- Run queries against both tables, compare results

  -- Phase 4: Cut over
  -- Point consumers to Iceberg table
  -- Stop dual-write
  -- Archive Hive table

Strategy 3: Snapshot export (for tables with complex types)

  -- Export Hive table as Iceberg snapshot
  CALL system.snapshot('hive_db.events', 'iceberg_db.events');
  -- This is like migrate but creates a NEW table (doesn't modify original)
  -- Original Hive table remains available throughout

Migration Checklist:
  □ Verify schema compatibility (type mapping Hive → Iceberg)
  □ Check for NULL partition values (Iceberg handles differently)
  □ Validate timestamp timezone handling
  □ Test downstream queries against the Iceberg table BEFORE cutover
  □ Have a rollback plan (keep Hive table for 7 days after migration)
  □ Monitor query performance before and after (should improve)
  □ Update catalog references in all consuming applications
```

---

## Issue 11: Delete Performance with Copy-on-Write

### The Problem

```
Copy-on-Write DELETE:
  DELETE FROM events WHERE user_id = 12345;

  What actually happens:
    1. Find all data files containing user 12345
       → Could be 500 files across 3 years of data
    2. For EACH file:
       - Read the entire file (256 MB)
       - Filter out rows for user 12345 (maybe 3 rows)
       - Write a NEW file with the remaining rows (255.99 MB)
    3. Commit: remove 500 old files, add 500 new files

  Cost of one GDPR delete request:
    - Read: 500 × 256 MB = 125 GB of reads
    - Write: 500 × 256 MB = 125 GB of writes
    - Time: 30-60 minutes
    - S3 cost: ~$3-5 per delete request

  At scale: 1000 GDPR requests/month = $3,000-5,000/month just for deletes
```

### The Solution

```
1. Use Merge-on-Read (v2 format) instead of Copy-on-Write:

   ALTER TABLE events SET TBLPROPERTIES (
     'write.delete.mode' = 'merge-on-read',
     'write.update.mode' = 'merge-on-read'
   );

   How MoR works:
     DELETE FROM events WHERE user_id = 12345;
     → Write a small "delete file" listing the positions to skip
     → Original data files are UNTOUCHED
     → Reads apply the delete file as a filter

   Delete cost: write a 1 KB file (microseconds, essentially free)

   Trade-off:
     - Writes are instant (just a delete file)
     - Reads are slightly slower (must check delete files)
     - Over time, many delete files degrade read performance
     - Solution: periodic compaction applies the deletes permanently

2. Batch GDPR deletes:

   -- Instead of deleting one user at a time:
   -- Collect all delete requests for the day
   -- Apply them in one batch operation

   DELETE FROM events
   WHERE user_id IN (12345, 67890, 11111, 22222, ...);
   -- One commit instead of 1000 commits

3. Partition-aware deletes:

   -- If you know which partitions contain the user:
   DELETE FROM events
   WHERE user_id = 12345
   AND event_date BETWEEN '2025-01-01' AND '2026-01-27';
   -- Iceberg only opens files in those partitions
   -- Much faster than scanning the entire table
```

---

## Issue 12: Flink Checkpoint and Iceberg Commit Alignment

### The Problem

```
Flink writes to Iceberg with exactly-once semantics:
  - Files are written during processing
  - Commit happens ONLY on Flink checkpoint

If checkpoint interval is too long:
  ┌─────────────────────────────────────────────────────────┐
  │ Checkpoint interval: 10 minutes                         │
  │                                                         │
  │ T0:  Flink starts writing files                         │
  │ T5:  5 minutes of uncommitted data accumulates          │
  │ T9:  Almost 10 minutes of data buffered                 │
  │ T10: Checkpoint triggers → Iceberg commit               │
  │                                                         │
  │ If Flink crashes at T9:                                 │
  │   - 9 minutes of data is LOST (not committed)           │
  │   - Orphan files remain in S3                           │
  │   - Recovery replays from last checkpoint (T0)           │
  │                                                         │
  │ If checkpoint takes too long:                           │
  │   - Backpressure builds up                              │
  │   - Flink's pipeline stalls                             │
  │   - Downstream consumers see data delay                 │
  └─────────────────────────────────────────────────────────┘

If checkpoint interval is too short:
  - Too many small files (Issue #1)
  - Too many snapshots (Issue #2)
  - High commit contention (Issue #4)
```

### The Solution

```
Recommended configuration:

  # Flink checkpoint settings
  execution.checkpointing.interval: 60s        # 1 minute
  execution.checkpointing.timeout: 120s         # 2 minute timeout
  execution.checkpointing.min-pause: 30s        # wait between checkpoints

  # Iceberg sink settings
  write.target-file-size-bytes: 536870912       # 512 MB target files
  write.parquet.row-group-size-bytes: 134217728 # 128 MB row groups

Balance:
  ┌───────────────────────────────────────────────────┐
  │ Interval  │ Data loss risk │ File size │ Commits  │
  ├───────────────────────────────────────────────────┤
  │ 10s       │ Very low       │ Tiny      │ Too many │
  │ 30s       │ Low            │ Small     │ High     │
  │ 60s  ★    │ Acceptable     │ Medium    │ Good     │
  │ 5min      │ Moderate       │ Large     │ Low      │
  │ 10min     │ High           │ Very large│ Minimal  │
  └───────────────────────────────────────────────────┘

  ★ = Sweet spot for most use cases

Additional settings:
  # Group files before commit to reduce small file problem
  sink.committer.operator.chaining: true

  # Use shared commit coordinator for multiple sinks
  # (avoids commit conflicts when multiple Flink jobs write to same table)
```

---

## Production Monitoring Dashboard

### Key Metrics to Track

```
┌─────────────────────────────────────────────────────────────────┐
│                     Iceberg Health Dashboard                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TABLE HEALTH                                                   │
│  ────────────                                                   │
│  • Total file count per table           (alert if > 100,000)   │
│  • Average file size                    (alert if < 32 MB)     │
│  • Snapshot count                       (alert if > 1,000)     │
│  • Metadata.json size                   (alert if > 100 MB)    │
│  • Manifest count                       (alert if > 5,000)     │
│  • Orphan file count (estimated)        (alert if growing)     │
│                                                                 │
│  WRITE PERFORMANCE                                              │
│  ─────────────────                                              │
│  • Commit latency (p50, p95, p99)       (alert if p99 > 30s)  │
│  • Commit conflict rate                 (alert if > 5%)        │
│  • Commit retry count                   (alert if > 3/min)     │
│  • Files written per commit             (track trend)          │
│                                                                 │
│  READ PERFORMANCE                                               │
│  ────────────────                                               │
│  • Query planning time                  (alert if > 10s)       │
│  • Files scanned vs files pruned        (pruning efficiency)   │
│  • S3 GET request count per query       (cost indicator)       │
│  • Data scanned per query               (cost indicator)       │
│                                                                 │
│  MAINTENANCE                                                    │
│  ───────────                                                    │
│  • Last compaction run time             (alert if > 24h ago)   │
│  • Last snapshot expiry run time        (alert if > 48h ago)   │
│  • Compaction job success rate          (alert if < 95%)       │
│  • Storage growth rate                  (capacity planning)    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary: Production Readiness Checklist

```
Before going to production with Iceberg:

□ Compaction pipeline configured and tested
□ Snapshot expiry scheduled (daily minimum)
□ Orphan file cleanup scheduled (weekly with dry_run)
□ Manifest rewrite scheduled (if > 1000 manifests)
□ Catalog HA verified (failover tested)
□ Monitoring dashboard with alerting
□ Writer conflict mitigation strategy chosen
□ Delete strategy chosen (CoW vs MoR)
□ Backup/rollback procedure documented
□ S3 rate limit mitigation in place
□ Driver/coordinator memory sized for metadata
□ Flink checkpoint interval tuned (if streaming)
□ Migration plan tested (if migrating from Hive)
□ Team trained on Iceberg maintenance procedures
□ On-call runbook with common failure scenarios
```
