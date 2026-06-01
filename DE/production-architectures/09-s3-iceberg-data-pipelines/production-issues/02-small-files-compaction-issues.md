# Small Files & Compaction Issues (#16-30)

Issues related to file sizing, small files problem, compaction failures, and merge-on-read
accumulation that cripple performance at scale.

---

## Issue #16: Small Files Explosion from Streaming Writes

**Severity:** P1 - High
**Frequency:** Daily on all streaming-to-Iceberg tables
**Affected Components:** Query performance, S3 costs, planning time
**First seen at:** Every company using Flink/Spark Streaming → Iceberg

### Symptoms
```
- Table has 500K+ files, most under 5MB
- Query that should take 10 seconds takes 10 minutes
- S3 LIST requests cost more than S3 storage
- "Too many open files" errors in query engines
- Planning phase shows "scanning 500K data files"
- Trino/Athena splits per query: 500K+ (should be <1000)
```

### Root Cause
```
Streaming creates small files because of commit frequency:

  Flink checkpoint interval: 60 seconds
  Flink parallelism: 100 tasks
  Each checkpoint = 1 commit to Iceberg
  Each task creates 1 file per commit (for its partition)

  Result per hour:
    60 commits × 100 tasks = 6,000 files/hour
    Average file size: 1MB (60s of data per task)
    
  Per day: 144,000 files
  Per week: 1,008,000 files
  
  Ideal: 128MB files × 1000 files = 128TB queryable in seconds
  Reality: 1MB files × 1,000,000 files = 1TB taking minutes to query

  S3 costs:
    1M files × 1 LIST = 1000 LIST requests × $0.005 = $5/query
    1M files × 1 GET each = 1M GETs × $0.0004/1000 = $400/query(!!!)
```

### Immediate Fix
```sql
-- Emergency compaction (bin-pack small files into larger ones)
CALL prod.system.rewrite_data_files(
  table => 'db.streaming_events',
  strategy => 'binpack',
  options => map(
    'target-file-size-bytes', '134217728',     -- 128MB target
    'min-file-size-bytes', '104857600',        -- 100MB min (don't rewrite if close)
    'max-file-size-bytes', '180388608',        -- 172MB max
    'min-input-files', '5',                    -- At least 5 small files to trigger
    'max-concurrent-file-group-rewrites', '50' -- Parallelism
  )
);
```

### Permanent Fix
```python
# Automated compaction service (runs continuously)
class CompactionService:
    """Runs every 15 minutes, compacts tables that need it."""
    
    def needs_compaction(self, table_name):
        """Check if table has too many small files."""
        stats = spark.sql(f"""
            SELECT 
                COUNT(*) as file_count,
                AVG(file_size_in_bytes) as avg_size,
                SUM(CASE WHEN file_size_in_bytes < 50000000 THEN 1 ELSE 0 END) as small_files
            FROM prod.{table_name}.files
        """).first()
        
        return stats.small_files > 100 or stats.avg_size < 50_000_000  # 50MB threshold
    
    def compact(self, table_name, strategy='binpack'):
        spark.sql(f"""
            CALL prod.system.rewrite_data_files(
                table => '{table_name}',
                strategy => '{strategy}',
                options => map(
                    'target-file-size-bytes', '134217728',
                    'min-file-size-bytes', '67108864',
                    'partial-progress.enabled', 'true',
                    'partial-progress.max-commits', '10'
                )
            )
        """)
```

```properties
# Flink tuning to reduce small files at source
# Increase checkpoint interval (fewer, larger files)
execution.checkpointing.interval = 300000  # 5 minutes instead of 1 minute

# Iceberg Flink sink settings
write.target-file-size-bytes = 134217728
write.distribution-mode = hash  # Concentrate data per partition
```

### Prevention
```
1. Tune streaming commit interval (5 min for most workloads)
2. Use write.distribution-mode=hash (fewer files per commit)
3. Schedule compaction every 15-30 minutes for streaming tables
4. Set table property: write.target-file-size-bytes = 134217728
5. Monitor avg file size metric with alert at <50MB
6. Consider using Iceberg's built-in auto-compaction (if available)
```

### Monitoring
```yaml
- alert: IcebergSmallFilesExplosion
  expr: iceberg_table_avg_file_size_bytes < 50000000 AND iceberg_table_file_count > 1000
  for: 30m
  labels:
    severity: high
  annotations:
    summary: "Table {{ $labels.table }}: avg file size {{ $value | humanize1024 }}, needs compaction"
```

---

## Issue #17: Compaction Job OOM (Out of Memory)

**Severity:** P1 - High
**Frequency:** Weekly when compacting large partitions
**Affected Components:** Compaction service, table health degrades
**First seen at:** Tables with partitions containing 100K+ small files

### Symptoms
```
- Spark compaction job fails: "java.lang.OutOfMemoryError: Java heap space"
- Compaction starts but kills executor after processing 50% of partition
- GC pauses > 60 seconds during compaction
- Executor lost: "Container killed by YARN for exceeding memory limits"
- Compaction never completes for largest partitions
```

### Root Cause
```
Compaction reads N small files → sorts/merges → writes M large files

Memory usage during compaction:
  - File metadata in memory: 100K files × 2KB = 200MB
  - Read buffers: min(100K, parallelism) × 1MB = large
  - Sort buffer (if sort strategy): entire partition data
  - Write buffers: output files being written
  - Parquet column chunks in memory
  
  For a partition with 100K files × 2MB avg = 200GB data:
    sort-compaction: needs entire 200GB in memory (or spill)
    bin-pack: needs only N read buffers + M write buffers
    
  But even bin-pack fails if file GROUP is too large:
    Iceberg groups files by partition → processes group together
    If one partition has 100K files, entire group is one unit
```

### Immediate Fix
```python
# Use partial-progress to commit intermediate results
spark.sql("""
    CALL prod.system.rewrite_data_files(
        table => 'db.large_table',
        strategy => 'binpack',
        options => map(
            'target-file-size-bytes', '134217728',
            'partial-progress.enabled', 'true',
            'partial-progress.max-commits', '100',
            'max-file-group-size-bytes', '10737418240'  -- 10GB per group (limits memory)
        )
    )
""")
```

```bash
# Increase executor memory for compaction jobs
spark-submit \
  --executor-memory 32g \
  --executor-cores 4 \
  --conf spark.executor.memoryOverhead=8g \
  --conf spark.sql.shuffle.partitions=200 \
  compaction_job.py
```

### Permanent Fix
```python
# Smart compaction: process in manageable chunks
def chunked_compaction(table_name, max_group_size_gb=5):
    """Compact table in chunks to avoid OOM."""
    
    # Get partitions sorted by file count (worst first)
    partitions = spark.sql(f"""
        SELECT partition, COUNT(*) as file_count, 
               SUM(file_size_in_bytes) as total_bytes
        FROM prod.{table_name}.files
        GROUP BY partition
        HAVING COUNT(*) > 10
        ORDER BY file_count DESC
    """).collect()
    
    for partition in partitions:
        if partition.total_bytes > max_group_size_gb * 1024**3:
            # Process in chunks using filter
            spark.sql(f"""
                CALL prod.system.rewrite_data_files(
                    table => '{table_name}',
                    strategy => 'binpack',
                    where => "partition_col = '{partition.partition}'",
                    options => map(
                        'partial-progress.enabled', 'true',
                        'partial-progress.max-commits', '10',
                        'max-file-group-size-bytes', '{int(max_group_size_gb * 1024**3)}'
                    )
                )
            """)
```

### Prevention
```
1. Always use partial-progress.enabled=true for compaction
2. Set max-file-group-size-bytes (5-10GB per group)
3. Run compaction frequently (don't let files accumulate)
4. Use bin-pack (not sort) for tables with very large partitions
5. Monitor partition file counts - compact before they get too large
6. Size compaction executors: 4 cores, 32GB RAM, 8GB overhead
```

---

## Issue #18: Compaction Conflicts with Writers (CommitFailedException)

**Severity:** P1 - High
**Frequency:** Daily on tables with concurrent writes + compaction
**Affected Components:** Compaction completion, write latency
**First seen at:** Streaming tables that also run compaction

### Symptoms
```
- Compaction job fails: "CommitFailedException: Commit conflict"
- After retry, compaction conflicts again (infinite loop)
- Table stays un-compacted despite compaction jobs running
- Streaming writers occasionally fail with conflict errors
- Compaction takes 10x longer due to retries
```

### Root Cause
```
Optimistic concurrency conflict during compaction commit:

Timeline:
  T0: Compaction reads snapshot S1 (files: A, B, C, D, E)
  T1: Compaction processes files A, B, C → creates file F
  T2: Streaming writer commits snapshot S2 (adds file G)
  T3: Compaction tries to commit: "remove A,B,C; add F" based on S1
      → CONFLICT: base snapshot changed (S1 → S2)
      → Compaction must verify its changes are still valid
      
  If streaming writer added file G to SAME partition as A,B,C:
    → Compaction's rewrite might miss data in G
    → Commit rejected for safety
    
  Retry: Compaction re-reads S2, re-processes → T4: another write → conflict again
  
  With streaming commits every 60s and compaction taking 5 minutes:
    → Compaction will ALWAYS conflict!
```

### Immediate Fix
```properties
# Increase compaction retry attempts
commit.retry.num-retries = 20
commit.retry.min-wait-ms = 500
commit.retry.max-wait-ms = 120000

# Use partial progress (smaller commits = less likely to conflict)
write.spark.compaction.partial-progress.enabled = true
write.spark.compaction.partial-progress.max-commits = 50
```

### Permanent Fix
```python
# Strategy 1: Compaction uses conflict resolution
# Iceberg allows non-conflicting changes to coexist:
#   - Compaction rewrites files in partition X
#   - Writer adds new files in partition X  
#   - These DON'T conflict (compaction only touches files it read)

# Ensure compaction uses REPLACE file set (not full overwrite):
spark.sql("""
    CALL prod.system.rewrite_data_files(
        table => 'db.streaming_table',
        strategy => 'binpack',
        options => map(
            'partial-progress.enabled', 'true',
            'partial-progress.max-commits', '20',
            'max-file-group-size-bytes', '2147483648',  -- 2GB groups (fast commits)
            'target-file-size-bytes', '134217728'
        )
    )
""")

# Strategy 2: Time-windowed compaction
# Only compact files OLDER than streaming commit window
def time_windowed_compaction(table_name, min_age_minutes=30):
    """Only compact files older than min_age_minutes."""
    cutoff = datetime.now() - timedelta(minutes=min_age_minutes)
    spark.sql(f"""
        CALL prod.system.rewrite_data_files(
            table => '{table_name}',
            strategy => 'binpack',
            where => "file_creation_time < TIMESTAMP '{cutoff.isoformat()}'",
            options => map(
                'partial-progress.enabled', 'true',
                'partial-progress.max-commits', '10'
            )
        )
    """)
```

### Prevention
```
1. Use partial-progress with small max-commits (faster, less conflict surface)
2. Compact only files older than 2× commit interval (avoids racing with writers)
3. Use separate partitions for streaming hot data vs historical (compact only historical)
4. Implement backoff: if conflict, wait exponentially before retry
5. Consider dedicated compaction time windows (pause streaming, compact, resume)
```

---

## Issue #19: Delete File Accumulation (MoR Read Amplification Crisis)

**Severity:** P1 - High
**Frequency:** Daily on tables with merge-on-read updates/deletes
**Affected Components:** Query performance degrades linearly with delete files
**First seen at:** Tables with frequent updates (user profiles, inventory, pricing)

### Symptoms
```
- Query performance degrades 10x over a week
- Same query Monday: 5 seconds. Friday: 50 seconds.
- Query plan shows "applying 10,000 delete files"
- Read amplification ratio: 50:1 (read 50 delete files per data file)
- After compaction, performance returns to normal briefly
- Memory pressure during queries (holding delete sets in memory)
```

### Root Cause
```
Merge-on-Read accumulates delete files over time:

  Day 1: 100 data files, 0 delete files → Fast reads
  Day 2: 100 data files, 500 delete files → Each read applies 500 deletes
  Day 3: 100 data files, 1000 delete files → Reads 10x slower
  Day 7: 100 data files, 5000 delete files → Reads unusable

  Read process for EACH data file:
    1. Read data file (128MB Parquet)
    2. Read ALL applicable delete files (position deletes for this file)
    3. Filter out deleted rows
    4. Return remaining rows
    
  With 5000 equality delete files:
    Each data file must check against ALL equality deletes
    = O(data_files × delete_files) complexity
    = 100 × 5000 = 500,000 delete-file-reads per query

  Memory: Each delete file loaded into memory as a set/bitmap
    5000 delete files × 10KB avg = 50MB in memory per task
    With 100 tasks: 5GB cluster memory just for delete tracking
```

### Immediate Fix
```sql
-- Compact to merge delete files into data files (removes delete files)
CALL prod.system.rewrite_data_files(
  table => 'db.user_profiles',
  strategy => 'binpack',
  options => map(
    'target-file-size-bytes', '134217728',
    'delete-file-threshold', '3'  -- Rewrite data file if it has 3+ delete files
  )
);
```

### Permanent Fix
```python
# Continuous compaction triggered by delete file ratio
class DeleteFileCompactionPolicy:
    """Trigger compaction when delete files exceed threshold."""
    
    MAX_DELETE_FILES_PER_DATA_FILE = 5
    MAX_TOTAL_DELETE_FILES = 1000
    CHECK_INTERVAL_MINUTES = 15
    
    def check_and_compact(self, table_name):
        stats = spark.sql(f"""
            SELECT 
                COUNT(DISTINCT content) as content_types,
                SUM(CASE WHEN content = 1 THEN 1 ELSE 0 END) as position_deletes,
                SUM(CASE WHEN content = 2 THEN 1 ELSE 0 END) as equality_deletes,
                COUNT(CASE WHEN content = 0 THEN 1 END) as data_files
            FROM prod.{table_name}.all_data_files
        """).first()
        
        total_deletes = stats.position_deletes + stats.equality_deletes
        ratio = total_deletes / max(stats.data_files, 1)
        
        if ratio > self.MAX_DELETE_FILES_PER_DATA_FILE or \
           total_deletes > self.MAX_TOTAL_DELETE_FILES:
            self.run_compaction(table_name)
    
    def run_compaction(self, table_name):
        spark.sql(f"""
            CALL prod.system.rewrite_data_files(
                table => '{table_name}',
                strategy => 'binpack',
                options => map(
                    'delete-file-threshold', '2',
                    'partial-progress.enabled', 'true',
                    'partial-progress.max-commits', '20'
                )
            )
        """)
```

### Prevention
```
1. Schedule compaction based on delete-file ratio (not just file size)
2. For high-update tables: consider copy-on-write (no delete files, but expensive writes)
3. Monitor read amplification ratio (delete_files / data_files)
4. Set delete-file-threshold=3 in compaction config
5. For streaming upserts: compact every 15-30 minutes
6. Consider hybrid: MoR for writes, periodic CoW compaction
```

### Monitoring
```yaml
- alert: IcebergDeleteFileAccumulation
  expr: iceberg_table_delete_file_count / iceberg_table_data_file_count > 5
  for: 15m
  labels:
    severity: high
  annotations:
    summary: "Table {{ $labels.table }} has high delete file ratio: {{ $value }}"
    action: "Run compaction with delete-file-threshold=2"
```

---

## Issue #20: Compaction Rewrites Active Data (Data Temporarily Invisible)

**Severity:** P0 - Critical
**Frequency:** Rare but catastrophic when it happens
**Affected Components:** Query correctness during compaction window
**First seen at:** During aggressive compaction of hot partitions

### Symptoms
```
- Queries return fewer rows than expected during compaction
- Dashboard shows sudden data drop, recovers after compaction finishes
- Some time-series data "disappears" for 5-10 minutes
- After compaction commit, data reappears
- Race condition: read between compaction delete-old and add-new
```

### Root Cause
```
This is actually NOT a real issue with Iceberg (MVCC prevents it).
But it APPEARS as one when:

1. Non-atomic external tools delete files outside Iceberg:
   - Someone manually deletes "old looking" Parquet files
   - S3 lifecycle policy deletes files that compaction will reference
   
2. Compaction with broken implementation:
   - Custom compaction code that does: DELETE files then ADD new files
   - If crash between DELETE and ADD → data missing from active snapshot
   
3. expire_snapshots during active compaction:
   - Compaction references snapshot S1
   - expire_snapshots deletes S1's exclusive files
   - Compaction reads those files → FileNotFoundException
   - Compaction fails → leaves partial state

Iceberg's built-in compaction is SAFE (atomic commit replaces old with new).
The issue is external tooling or incorrect sequencing.
```

### Immediate Fix
```python
# If data appears missing, check if compaction is mid-flight:
active_ops = spark.sql("""
    SELECT * FROM prod.db.table.metadata_log_entries 
    ORDER BY timestamp DESC LIMIT 10
""")

# If caused by deleted files, rollback to previous snapshot:
spark.sql("""
    CALL prod.system.rollback_to_snapshot(
        table => 'db.table',
        snapshot_id => 123456789  -- Last known good snapshot
    )
""")
```

### Permanent Fix
```
1. NEVER delete S3 files outside of Iceberg (no S3 lifecycle on data/)
2. NEVER run expire_snapshots while compaction is in progress
3. Use only Iceberg's built-in compaction procedures
4. Implement operation ordering: compaction → wait → expire → wait → orphan cleanup
5. Set S3 lifecycle rules ONLY on metadata/ prefix (not data/)
```

### Prevention
```
- S3 bucket policy: deny DeleteObject on data/ prefix from non-Iceberg roles
- Ordering: compact → expire (never concurrent)
- Monitor: row count before/after compaction (should be equal)
- Never use custom file deletion logic
- Integration test: query during compaction returns correct count
```

---

## Issue #21: Z-Order Compaction Taking 10x Longer Than Expected

**Severity:** P2 - Medium
**Frequency:** When switching from bin-pack to z-order strategy
**Affected Components:** Compaction job duration, compute costs
**First seen at:** Teams optimizing for multi-column filter queries

### Symptoms
```
- Bin-pack compaction: 10 minutes. Z-order compaction: 2 hours.
- Compaction job uses 100x more shuffle (network I/O)
- Executor disk fills up during z-order sort
- Cost of compaction job exceeds query savings
- Compaction can't keep up with data arrival rate
```

### Root Cause
```
Z-order requires GLOBAL SORT across all data:

  Bin-pack: 
    Read small files → concatenate → write large files
    No sorting needed. O(n) read + write.
    Shuffle: NONE
    
  Z-order:
    Read ALL files → compute z-order curve → sort ALL data → write
    Global sort required. O(n log n) with full data shuffle.
    Shuffle: ENTIRE DATASET (100TB shuffle for 100TB table!)
    
  For a 10TB partition:
    Bin-pack: read 10TB + write 10TB = 20TB I/O, 10 min
    Z-order: read 10TB + shuffle 10TB + sort + write 10TB = 40TB+ I/O, 2+ hours

  Additional overhead:
    - Z-order curve computation per row
    - Shuffle network bandwidth (10TB across cluster)
    - Spill to disk when memory insufficient for sort
```

### Immediate Fix
```sql
-- Limit z-order to specific partitions (not full table)
CALL prod.system.rewrite_data_files(
  table => 'db.table',
  strategy => 'sort',
  sort_order => 'zorder(col_a, col_b)',
  where => "event_date >= '2024-01-01'",  -- Only recent data
  options => map(
    'target-file-size-bytes', '268435456',  -- 256MB (larger = fewer files)
    'max-file-group-size-bytes', '5368709120',  -- 5GB groups
    'partial-progress.enabled', 'true'
  )
);
```

### Permanent Fix
```
1. Hybrid strategy:
   - Hot data (last 7 days): bin-pack only (fast, frequent)
   - Warm data (7-30 days): z-order once (expensive but worth it)
   - Cold data (30+ days): already z-ordered, skip

2. Z-order only columns that benefit:
   - High-cardinality columns used in filters
   - Max 2-4 columns (more columns = less effective clustering)
   
3. Use SORT ORDER instead of z-order when queries filter on 1-2 columns:
   ALTER TABLE db.table WRITE ORDERED BY col_a, col_b;
   Sorting is cheaper than z-ordering and works better for range queries.

4. Schedule z-order as weekly batch (not continuous):
   - Friday night: z-order past week's data
   - Weekdays: bin-pack only
```

### Prevention
```
- Benchmark z-order benefit before committing (measure query improvement)
- Start with sort-order (simpler, cheaper, often sufficient)
- Z-order only 2-3 columns maximum
- Budget 10x more compute for z-order vs bin-pack
- Don't z-order streaming hot partitions (they'll be rewritten anyway)
```

---

## Issue #22: Compaction Causes Spike in S3 Costs

**Severity:** P2 - Medium
**Frequency:** After enabling aggressive compaction
**Affected Components:** AWS bill (S3 request costs)
**First seen at:** Companies with aggressive compaction on many tables

### Symptoms
```
- S3 bill doubles after enabling compaction
- PUT requests spike 10x during compaction windows
- S3 transfer costs unexpected (reading + writing all data)
- Monthly S3 costs: $50K → $100K after compaction rollout
- GET requests from compaction reads exceed query reads
```

### Root Cause
```
Compaction reads ALL input files + writes ALL output files:

  Compacting 1000 files × 5MB = 5GB:
    Reads: 1000 GET requests + 5GB transfer
    Writes: 40 PUT requests (128MB target) + 5GB transfer
    
  At scale (1000 tables × daily compaction):
    Reads: 1M GET requests/day = $0.40/day per table
    Writes: 40K PUT requests/day = $0.20/day per table
    Transfer: 5TB read + 5TB write = ...
    
  Plus: old files still stored until expire_snapshots runs
    During compaction window: 2× storage (old + new files)
    
  S3 request pricing (us-east-1):
    PUT/POST: $0.005 per 1,000
    GET: $0.0004 per 1,000
    Storage: $0.023/GB/month
    
  For 1PB deployment with 50% daily compaction:
    500TB reads + 500TB writes = massive request costs
```

### Immediate Fix
```python
# Reduce compaction frequency (compact less often, larger batches)
# Instead of every 15 min, compact every 6 hours with larger groups

spark.sql("""
    CALL prod.system.rewrite_data_files(
        table => 'db.table',
        strategy => 'binpack',
        options => map(
            'min-file-size-bytes', '52428800',    -- Only rewrite files <50MB
            'min-input-files', '20',              -- Need at least 20 small files
            'max-file-group-size-bytes', '53687091200'  -- 50GB per group (batch bigger)
        )
    )
""")
```

### Permanent Fix
```
1. Smart compaction triggers (don't compact unless needed):
   - min-input-files=10 (don't compact if only 3 small files)
   - min-file-size-bytes threshold (don't rewrite files close to target)
   
2. Use S3 Express One Zone for hot tables ($0.0016/1000 GETs vs $0.0004)
   Not cheaper per request, but 10x lower latency = faster compaction
   
3. Compact during off-peak hours (use spot instances, 70% cheaper)

4. Tiered compaction:
   - Tier 1 (streaming hot): compact every 30 min (small batches)
   - Tier 2 (daily batch): compact once daily
   - Tier 3 (historical): compact weekly

5. Set higher min-file-size threshold to skip "almost right" files:
   min-file-size-bytes = 104857600 (100MB) with target 128MB
   → Only rewrites files <100MB, skips 100-128MB files
```

---

## Issue #23: File Size Variance (Some Files 1KB, Others 2GB)

**Severity:** P2 - Medium
**Frequency:** Common with skewed data distributions
**Affected Components:** Query parallelism, task duration variance
**First seen at:** Tables with data skew (popular products, hot keys)

### Symptoms
```
- Spark tasks: 90% finish in 10 seconds, 10% take 30 minutes
- Query timeout for tasks processing 2GB files
- Some files are 500 bytes (empty partitions with 1 row)
- Massive skew in partition sizes (partition A: 500GB, partition B: 100KB)
- OOM on executors processing oversized files
```

### Root Cause
```
Data skew causes uneven file distribution:

  Partition by (country):
    US: 500M rows → 200 × 128MB files = 25.6GB ✓
    Bhutan: 50 rows → 1 × 500 bytes = tiny file ✗
    
  Partition by day + hour:
    2024-01-15T10:00 (peak): 50M rows → 100 × 128MB files
    2024-01-15T03:00 (off-peak): 500 rows → 1 × 5KB file
    
  Streaming with uneven key distribution:
    Key A (hot): 1M events/min → large files
    Key B (cold): 1 event/hour → tiny files
    
  Combined: file size ranges from 500 bytes to 2GB in same table
  
  Impact on queries:
    - 2GB file assigned to one task → 30 min processing
    - 500 byte file assigned to one task → <1 second
    - Query latency = slowest task = 30 min (straggler problem)
```

### Immediate Fix
```sql
-- Use split-target-size to break large files into smaller reads
SET spark.sql.files.maxPartitionBytes = 134217728;  -- 128MB max per task

-- Compaction with size bounds
CALL prod.system.rewrite_data_files(
  table => 'db.skewed_table',
  strategy => 'binpack',
  options => map(
    'target-file-size-bytes', '134217728',    -- 128MB target
    'max-file-size-bytes', '268435456',       -- 256MB max (prevents oversized)
    'min-file-size-bytes', '67108864'         -- 64MB min (prevents tiny)
  )
);
```

### Permanent Fix
```
1. Write distribution mode to distribute skewed data:
   ALTER TABLE db.table SET TBLPROPERTIES (
     'write.distribution-mode' = 'hash'  -- Spreads data across writers evenly
   );

2. Adaptive partition strategy:
   - High-cardinality skewed: bucket(N, key) instead of identity(key)
   - Time-series: use hours() not days() for high-volume tables
   
3. Writer-side file size management:
   write.target-file-size-bytes = 134217728
   write.parquet.row-group-size-bytes = 134217728

4. Spark adaptive query execution for read-side:
   spark.sql.adaptive.enabled = true
   spark.sql.adaptive.coalescePartitions.enabled = true
```

---

## Issue #24: Compaction Doesn't Run on Specific Partitions

**Severity:** P2 - Medium
**Frequency:** After partition evolution or with complex partition specs
**Affected Components:** Performance for un-compacted partitions
**First seen at:** Tables that evolved partition spec

### Symptoms
```
- Some partitions have 10,000 small files, others have proper 128MB files
- Compaction "completes successfully" but specific partitions unchanged
- New partition spec data is compacted, old partition spec data is not
- Compaction with WHERE clause doesn't match expected partitions
- Files in "orphaned" partition scheme never get compacted
```

### Root Cause
```
After partition evolution:

  Old spec: monthly(event_ts) → partitions like event_ts_month=2024-01
  New spec: daily(event_ts) → partitions like event_ts_day=2024-01-15

  Compaction with WHERE clause:
    where => "event_ts_day = '2024-01-15'"
    → Only matches NEW spec partitions
    → Old monthly partitions completely ignored
    
  Or: compaction groups by partition spec
    → Groups old-spec and new-spec separately
    → Small groups in old spec don't meet min-input-files threshold
    
  Result: old partitions accumulate small files forever
```

### Immediate Fix
```sql
-- Compact without WHERE clause (processes all partitions)
CALL prod.system.rewrite_data_files(
  table => 'db.evolved_table',
  strategy => 'binpack',
  options => map(
    'min-input-files', '2',  -- Lower threshold to catch small groups
    'partial-progress.enabled', 'true'
  )
);

-- Or explicitly target old partition spec files:
-- Rewrite old-spec data to conform to new partition spec
CALL prod.system.rewrite_data_files(
  table => 'db.evolved_table',
  strategy => 'sort',
  sort_order => 'event_ts',  -- Sort by time to align with new daily spec
  where => "event_ts < '2024-01-01'"  -- Target old data
);
```

### Permanent Fix
```
1. After partition evolution, schedule one-time full rewrite of historical data
2. Lower min-input-files threshold for tables with partition evolution
3. Use partition-independent compaction (no WHERE clause)
4. Monitor per-partition file counts to detect un-compacted pockets
5. Consider full rewrite to new partition spec for consistency
```

---

## Issue #25: Target File Size Not Achieved (Files Always Smaller Than Target)

**Severity:** P3 - Low
**Frequency:** Common misconfiguration
**Affected Components:** File count higher than optimal
**First seen at:** Tables with wide schemas or high compression

### Symptoms
```
- Target: 128MB, actual files: 30-50MB consistently
- File count 3-4x higher than expected
- Compaction runs but doesn't reduce file count significantly
- write.target-file-size-bytes set but seemingly ignored
```

### Root Cause
```
Multiple factors cause actual size to differ from target:

1. Row group alignment:
   Target = 128MB, row-group-size = 128MB
   If data doesn't fill a row group exactly → smaller file
   
2. Parquet overhead:
   Target applies to RAW data size, not Parquet file size
   With ZSTD compression: 4:1 ratio
   128MB target → files are 128MB of raw data → 32MB on disk after compression
   
3. Partition boundaries:
   Writer creates new file per partition
   If partition has 100MB of data and target is 128MB
   → Creates 100MB file (can't borrow from other partitions)
   
4. Spark task boundaries:
   Each task creates its own file
   If data per task < target → small file

5. Streaming checkpoint:
   File closed on checkpoint regardless of size
```

### Fix
```properties
# Adjust target based on compression ratio
# If compression ratio is 4:1 and you want 128MB on disk:
write.target-file-size-bytes = 536870912  # 512MB raw → ~128MB after ZSTD

# Or measure actual compression and adjust:
# Actual avg file = 35MB with target 128MB → ratio ~3.7:1
# For 128MB on disk: 128 × 3.7 = 473MB
write.target-file-size-bytes = 473956352

# Align row group with target:
write.parquet.row-group-size-bytes = 134217728  # Same as target
```

---

## Issue #26: Compaction Rewrite Doubles Storage Temporarily

**Severity:** P2 - Medium
**Frequency:** Every compaction run
**Affected Components:** S3 storage costs, storage quotas
**First seen at:** Large tables where compaction = significant storage event

### Symptoms
```
- S3 storage spikes 2x during compaction
- Storage quota exceeded alerts during compaction
- S3 costs fluctuate ±50% depending on compaction timing
- After compaction: storage drops but not to pre-compaction level
```

### Root Cause
```
Compaction lifecycle:

  T0: Table = 10TB (1000 files)
  T1: Compaction starts → reads files, writes new optimized files
  T2: Compaction creates new files → Table = 20TB (1000 old + 80 new)
  T3: Compaction commits → old files are logically "deleted" (dereferenced)
  T4: expire_snapshots → old snapshot removed, but files NOT deleted
  T5: remove_orphan_files → old files actually deleted from S3
  
  Between T2 and T5: DOUBLE storage
  
  If expire runs daily and compaction runs hourly:
    → New files accumulate for 24 hours before cleanup
    → Peak storage: significantly more than baseline
    
  With multiple compaction runs per day on same data:
    → Even worse (each run creates a new copy before previous is cleaned)
```

### Fix
```python
# Run maintenance in correct order, immediately after compaction:
def full_maintenance_cycle(table_name):
    # Step 1: Compact
    spark.sql(f"""
        CALL prod.system.rewrite_data_files(table => '{table_name}', strategy => 'binpack')
    """)
    
    # Step 2: Immediately expire old snapshots
    spark.sql(f"""
        CALL prod.system.expire_snapshots(
            table => '{table_name}',
            older_than => current_timestamp() - INTERVAL 1 HOUR,
            retain_last => 3
        )
    """)
    
    # Step 3: Remove orphan files
    spark.sql(f"""
        CALL prod.system.remove_orphan_files(
            table => '{table_name}',
            older_than => current_timestamp() - INTERVAL 2 HOURS
        )
    """)
```

---

## Issue #27: Sort-Order Compaction Negated by Subsequent Appends

**Severity:** P2 - Medium
**Frequency:** After sort-compaction on tables with ongoing writes
**Affected Components:** Query performance (clustering lost)
**First seen at:** Tables where sorted data gets mixed with unsorted appends

### Symptoms
```
- After z-order/sort compaction: queries fast (2 seconds)
- After 1 day of appends: queries slow again (20 seconds)
- File statistics show poor clustering after new writes
- Predicate pushdown effectiveness drops from 99% to 60%
- Sort benefit disappears within hours
```

### Root Cause
```
Sorted compaction creates perfectly clustered files:

  After sort(user_id): 
    File 1: user_id [1-10000]
    File 2: user_id [10001-20000]
    File 3: user_id [20001-30000]
    
  Query WHERE user_id = 5000 → prunes to File 1 only ✓

  After 1 day of unsorted streaming appends:
    File 1: user_id [1-10000] (sorted, old)
    File 2: user_id [10001-20000] (sorted, old)
    File 100: user_id [1-500000] (unsorted, new, ALL user_ids!)
    File 101: user_id [1-500000] (unsorted, new, ALL user_ids!)
    
  Query WHERE user_id = 5000:
    → File 1 (pruned correctly) + File 100, 101 (can't prune - overlapping ranges!)
    → Must read ALL new files ✗

  Sort benefit is proportional to: sorted_files / total_files
  With streaming: new unsorted files constantly dilute the clustering
```

### Permanent Fix
```properties
# Set write-time sort order (new files are ALREADY sorted)
ALTER TABLE db.table WRITE ORDERED BY user_id;

# Now streaming writes will also sort within each file
# Not as good as global sort, but maintains per-file clustering

# Combine with regular re-sorting compaction:
# Schedule sort-compaction weekly on new data only
```

```python
# Incremental sort: only sort recent un-sorted data
def incremental_sort_compaction(table_name, days_back=7):
    spark.sql(f"""
        CALL prod.system.rewrite_data_files(
            table => '{table_name}',
            strategy => 'sort',
            sort_order => 'user_id, event_ts',
            where => "event_date >= current_date() - INTERVAL {days_back} DAYS",
            options => map(
                'target-file-size-bytes', '268435456',
                'partial-progress.enabled', 'true'
            )
        )
    """)
```

---

## Issue #28: Compaction Service Crashes Affect Active Queries

**Severity:** P1 - High
**Frequency:** When compaction and query share compute resources
**Affected Components:** Query latency, SLA breaches
**First seen at:** Shared EMR/Spark clusters running both workloads

### Symptoms
```
- Dashboard queries spike to 5 minutes during compaction windows
- BI users report "slow queries" every morning at 6 AM (compaction time)
- Executor memory pressure causes spilling during queries
- YARN/K8s shows resource contention between compaction and query pods
- Compaction job consumes all available shuffle slots
```

### Root Cause
```
Compaction is resource-intensive:
  - CPU: reading + decompressing + recompressing Parquet
  - Memory: holding file buffers, sort buffers
  - Disk: spill during sort, temporary files
  - Network: shuffle for sort-compaction
  - S3: high request rate (reads + writes)
  
When sharing cluster with queries:
  - Compaction grabs executor slots → fewer for queries
  - Compaction shuffle fills network → queries wait for network
  - S3 throttling from compaction affects query reads
  - JVM GC pressure from compaction memory affects co-located queries
```

### Permanent Fix
```
1. Isolate compaction compute from query compute:
   - Dedicated compaction cluster (separate EMR/K8s namespace)
   - Resource quotas (compaction limited to 30% of cluster)
   - Kubernetes: separate node pools for compaction vs serving

2. Schedule compaction during off-peak:
   - Off-peak: 2 AM - 6 AM (before dashboard users arrive)
   - Use spot instances for compaction (70% cheaper)
   
3. Resource limits in Spark:
```

```python
# Compaction job with resource limits
compaction_spark = SparkSession.builder \
    .config("spark.dynamicAllocation.maxExecutors", "20") \
    .config("spark.executor.memory", "8g") \
    .config("spark.executor.cores", "2") \
    .config("spark.scheduler.mode", "FAIR") \
    .config("spark.scheduler.pool", "compaction") \
    .getOrCreate()
```

```yaml
# Kubernetes: separate namespace with resource quotas
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compaction-quota
  namespace: iceberg-compaction
spec:
  hard:
    requests.cpu: "40"
    requests.memory: "160Gi"
    limits.cpu: "80"
    limits.memory: "320Gi"
```

---

## Issue #29: Equality Delete Files Never Getting Compacted

**Severity:** P1 - High
**Frequency:** On tables using streaming equality deletes
**Affected Components:** Read performance degrades permanently
**First seen at:** Tables with Flink streaming deletes/updates

### Symptoms
```
- Equality delete files accumulate without bound
- Compaction runs but equality deletes remain
- rewrite_data_files doesn't remove equality delete files
- Position delete files are merged but equality deletes persist
- Query performance still slow after compaction
```

### Root Cause
```
Equality deletes are HARDER to compact than position deletes:

  Position delete: "Delete row at position 54321 in file X.parquet"
    → Compaction reads file X, skips position 54321, writes new file
    → Position delete file can be removed (merged into data file)
    
  Equality delete: "Delete all rows where user_id = 'abc123'"
    → Applies to ALL data files (not just one specific file)
    → Compaction must check EVERY data file for matching rows
    → Even after compaction, new files might later match this delete
    
  Problem: Standard rewrite_data_files may not process equality deletes properly
  
  The equality delete "user_id = 'abc123'" applies to:
    - All EXISTING data files (compaction handles)
    - All FUTURE data files (can't be removed until no future file will match!)
    
  Iceberg tracks: equality delete applies to files with sequence_number <= delete's seq
  Once all such files are rewritten, equality delete can be GC'd
  But if old files aren't compacted, the equality delete persists
```

### Fix
```sql
-- Must rewrite ALL data files that the equality delete applies to
-- Use sequence number filtering:
CALL prod.system.rewrite_data_files(
  table => 'db.table',
  strategy => 'binpack',
  options => map(
    'delete-file-threshold', '1',  -- Process files with ANY delete files
    'partial-progress.enabled', 'true',
    'partial-progress.max-commits', '50'
  )
);

-- After ALL applicable data files are rewritten:
-- Expire old snapshots (equality deletes become orphans and get cleaned)
CALL prod.system.expire_snapshots(
  table => 'db.table',
  older_than => current_timestamp() - INTERVAL 1 HOUR,
  retain_last => 2
);
```

### Prevention
```
1. Prefer position deletes over equality deletes when possible
2. For streaming updates: use UPSERT mode (creates position deletes)
3. If equality deletes needed: compact aggressively (all affected files)
4. Monitor equality delete count separately from position deletes
5. Consider switching high-update tables to copy-on-write mode
```

---

## Issue #30: Compaction Creates Files That Immediately Need Re-compaction

**Severity:** P3 - Low (but wastes resources)
**Frequency:** With misconfigured size thresholds
**Affected Components:** Compute costs, compaction efficiency
**First seen at:** Tables with overlapping compaction schedules

### Symptoms
```
- Compaction runs every 15 min, same files being rewritten every cycle
- S3 PUT count growing linearly (compaction loop)
- Compaction metrics show: "files rewritten: 100" every run but file count unchanged
- Newly compacted files are 90MB (under 100MB min threshold) → recompacted again
```

### Root Cause
```
Misconfigured thresholds create infinite compaction loop:

  Config:
    target-file-size-bytes = 128MB
    min-file-size-bytes = 100MB (files under this get rewritten)
    
  Scenario:
    3 files × 50MB = 150MB data
    Compaction: merges into 1 file × 150MB? No - splits because >128MB target
    Result: 1 file × 128MB + 1 file × 22MB
    Next run: 22MB file < 100MB threshold → triggers compaction again!
    
  Or: Compaction creates file at exactly 128MB, but Parquet overhead
      makes actual file 115MB after row-group alignment
      → 115MB < min threshold → rewritten again → same size → infinite loop
```

### Fix
```properties
# Set wider tolerance band
write.target-file-size-bytes = 134217728       # 128MB target
write.spark.compaction.min-file-size-bytes = 52428800   # 50MB min (not 100MB)
write.spark.compaction.max-file-size-bytes = 268435456  # 256MB max

# Rule: min should be < 50% of target to avoid ping-pong
# Good: target=128MB, min=50MB (file must be <50MB to trigger rewrite)
# Bad: target=128MB, min=100MB (common files in 100-128MB range get churned)
```

---

## Summary: Small Files & Compaction Issues

| # | Issue | Severity | Key Fix |
|---|-------|----------|---------|
| 16 | Small files from streaming | P1 | Continuous compaction + larger commit interval |
| 17 | Compaction OOM | P1 | partial-progress + max-file-group-size |
| 18 | Compaction conflicts with writers | P1 | Time-windowed + partial progress |
| 19 | Delete file accumulation (MoR) | P1 | delete-file-threshold compaction |
| 20 | Data invisible during compaction | P0 | Use built-in procedures only |
| 21 | Z-order taking too long | P2 | Hybrid strategy + incremental |
| 22 | Compaction S3 cost spike | P2 | Efficient triggers + immediate cleanup |
| 23 | File size variance (skew) | P2 | write.distribution-mode=hash |
| 24 | Compaction misses evolved partitions | P2 | No WHERE clause + lower thresholds |
| 25 | Target file size not achieved | P3 | Account for compression ratio |
| 26 | Double storage during compaction | P2 | Immediate expire after compact |
| 27 | Sort order negated by appends | P2 | WRITE ORDERED BY + incremental sort |
| 28 | Compaction starves queries | P1 | Isolated compute + resource quotas |
| 29 | Equality deletes never cleaned | P1 | Full rewrite + aggressive expire |
| 30 | Infinite compaction loop | P3 | Wider min/max tolerance band |
