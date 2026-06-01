# Category 5: Storage & I/O Issues (Issues 41-50)

> At petabyte scale, storage I/O becomes the dominant bottleneck. S3 throttling, small files, and format misconfigurations silently degrade performance by 10-100x.

---

## Issue #41: S3 Request Throttling (HTTP 503 SlowDown)

**Frequency**: High at scale  
**Severity**: High - job stalls or fails  
**Spark Component**: S3A FileSystem, Hadoop AWS SDK

### Symptoms
```
com.amazonaws.services.s3.model.AmazonS3Exception: 
  Slow Down (Service: Amazon S3; Status Code: 503)
# OR
WARNING S3AFileSystem: S3 request throttled for bucket/prefix
# Job throughput drops from 1GB/s to 10MB/s
# Intermittent task failures with retry storms
```

### Root Cause
- S3 per-prefix limit: 5,500 GET/s and 3,500 PUT/s
- All files share same prefix (e.g., s3://bucket/data/2024/01/01/)
- Too many concurrent list/head operations (partition discovery)
- Spark's speculative execution doubles S3 requests
- Multiple jobs hitting same prefix simultaneously

### Solution
```python
# 1. Distribute data across prefixes (prefix hashing)
# BAD: s3://bucket/data/2024-01-01/file_0001.parquet (all same prefix)
# GOOD: s3://bucket/data/hash=ab/2024-01-01/file.parquet (distributed)

# 2. S3 client retry configuration
spark.conf.set("spark.hadoop.fs.s3a.retry.limit", "20")
spark.conf.set("spark.hadoop.fs.s3a.retry.interval", "500ms")
spark.conf.set("spark.hadoop.fs.s3a.attempts.maximum", "20")
spark.conf.set("spark.hadoop.fs.s3a.connection.maximum", "200")

# 3. Reduce list operations
spark.conf.set("spark.hadoop.fs.s3a.committer.name", "magic")  # Avoid list-based commit
spark.conf.set("spark.sql.sources.parallelPartitionDiscovery.threshold", "32")

# 4. Use S3 Express One Zone for hot data (10x request rate)
# Or request S3 prefix pre-warming from AWS support

# 5. Use Iceberg/Delta metadata for file listing (avoid S3 list)
# Iceberg: reads manifest files (small metadata) instead of listing S3
# This eliminates 99% of S3 LIST calls
spark.read.format("iceberg").load("catalog.db.table")  # No S3 list needed

# 6. Limit concurrent S3 connections per executor
spark.conf.set("spark.hadoop.fs.s3a.connection.maximum", "100")  # Per executor
spark.conf.set("spark.hadoop.fs.s3a.threads.max", "64")

# 7. Disable speculative execution (doubles S3 reads)
spark.conf.set("spark.speculation", "false")  # For I/O-bound jobs
```

---

## Issue #42: Small Files Problem (Millions of Tiny Files)

**Frequency**: Very High  
**Severity**: High - 10-100x slower reads, driver OOM from metadata  
**Spark Component**: InMemoryFileIndex, FileScanRDD

### Symptoms
```
# s3://bucket/table/ contains 5 million files averaging 1MB each
# File listing alone takes 30 minutes
# Driver OOM from storing 5M file paths in memory
# Each task reads one tiny file (1MB) → 5M tasks → massive scheduling overhead
# Downstream queries scan metadata for minutes before reading data
```

### Root Cause
- Streaming writes creating one file per micro-batch per partition
- Over-partitioning: partitionBy("year", "month", "day", "hour", "category")
- Frequent small appends without compaction
- Failed/retried writes leaving partial files
- Default 200 shuffle partitions writing 200 files per write operation

### Solution
```python
# 1. Compact files periodically (Iceberg)
spark.sql("""
    CALL catalog.system.rewrite_data_files(
        table => 'db.events',
        options => map('target-file-size-bytes', '268435456')  -- 256MB
    )
""")

# 2. Compact files (Delta Lake)
spark.sql("OPTIMIZE delta.`s3://bucket/table/` ZORDER BY (date, user_id)")

# 3. Coalesce before writing
df.coalesce(100).write.parquet("s3://output/")  # 100 files instead of 10000

# 4. Use maxRecordsPerFile for even distribution
df.write.option("maxRecordsPerFile", 1000000).parquet("s3://output/")

# 5. For streaming: tune file generation
query = df.writeStream \
    .trigger(processingTime="5 minutes") \  # Larger batches = fewer files
    .option("checkpointLocation", "s3://cp/") \
    .toTable("catalog.db.events")

# Iceberg: automatic file compaction in streaming
spark.conf.set("spark.sql.iceberg.handle-timestamp-without-timezone", "true")

# 6. Merge small input files on read
spark.conf.set("spark.sql.files.maxPartitionBytes", "512MB")  # Merge inputs up to 512MB
spark.conf.set("spark.sql.files.openCostInBytes", "4194304")  # 4MB open cost

# 7. Schedule compaction job (Airflow DAG)
# Run nightly: compact all partitions with avg file size < 100MB
# Target: 256MB-1GB files, < 1000 files per partition
```

---

## Issue #43: Parquet Footer Read Latency (Slow File Opening)

**Frequency**: Medium  
**Severity**: Medium - adds seconds per task for cold reads  
**Spark Component**: ParquetFileReader, VectorizedParquetRecordReader

### Symptoms
```
# Each task spends 2-5 seconds "opening" file before reading data
# With 10000 tasks, this adds 5+ hours of aggregate overhead
# High S3 GET latency for footer reads (end of file)
# FileScanRDD spending most time in "open" phase
```

### Root Cause
- Parquet footer is at END of file → requires separate S3 GET request
- First read: GET file size, then GET last N bytes for footer
- Large footers (many columns, many row groups) slow to parse
- No local caching of footers for repeated access

### Solution
```python
# 1. Enable footer caching
spark.conf.set("spark.sql.parquet.footerCache.enabled", "true")  # If available

# 2. Use Parquet with smaller row groups → smaller footers per split
# Write with: parquet.block.size=128MB (default)

# 3. Prefetch file metadata
spark.conf.set("spark.sql.parquet.enableVectorizedReader", "true")  # Default true
spark.conf.set("spark.sql.parquet.recordLevelFilter.enabled", "true")

# 4. Use Iceberg metadata layer (avoids reading Parquet footers)
# Iceberg stores column stats in manifest files
# Filter pushdown uses manifest stats, not Parquet footer
# Only opens files that pass manifest-level filtering

# 5. Use S3 Select / S3 Byte-Range reads efficiently
spark.conf.set("spark.hadoop.fs.s3a.experimental.input.fadvise", "random")
# "random" mode: uses range GET for each read (good for column pruning)
# "sequential" mode: reads ahead sequentially (good for full file reads)

# 6. Column pruning reduces footer parse time
# Select only needed columns (Spark only reads relevant column chunks)
df.select("user_id", "amount", "timestamp")  # Don't SELECT * with 500 columns

# 7. Use Parquet page index (Spark 3.3+)
# Page-level column index allows skipping pages within row groups
spark.conf.set("spark.sql.parquet.columnIndex.enabled", "true")
```

---

## Issue #44: Write Commit Protocol Failures (OutputCommitter)

**Frequency**: Medium  
**Severity**: Critical - data loss or corruption  
**Spark Component**: HadoopMapReduceCommitProtocol, S3A Committer

### Symptoms
```
org.apache.spark.SparkException: Task failed while writing rows
  Caused by: java.io.IOException: rename failed: s3://bucket/_temporary/0/task_xxx
# OR
Data loss: files visible in _temporary but never promoted to final location
# OR duplicate data: some files written twice during retry
# OR "WARN: FileAlreadyExistsException" during commit
```

### Root Cause
- S3 doesn't support atomic rename (old commit protocol relies on rename)
- Task speculation writes duplicate files
- Driver crash between task commits and job commit
- Race condition in multi-writer scenarios
- _temporary directory cleanup failures

### Solution
```python
# 1. Use S3A Staging Committer (recommended for S3)
spark.conf.set("spark.hadoop.fs.s3a.committer.name", "magic")
spark.conf.set("spark.hadoop.fs.s3a.committer.magic.enabled", "true")
# "magic" committer uses S3 multipart upload (atomic, no rename)

# 2. Or use Iceberg/Delta (built-in atomic commits)
df.writeTo("catalog.db.table").append()
# Iceberg: writes data files, then atomically updates metadata (single atomic op)
# No _temporary directory, no rename, no corruption window

# 3. For Parquet/CSV direct writes: use directory committer
spark.conf.set("spark.sql.sources.commitProtocolClass",
    "org.apache.spark.internal.io.cloud.PathOutputCommitProtocol")
spark.conf.set("spark.hadoop.mapreduce.outputcommitter.factory.scheme.s3a",
    "org.apache.hadoop.fs.s3a.commit.S3ACommitterFactory")

# 4. Disable speculation for write jobs (prevents duplicate writes)
spark.conf.set("spark.speculation", "false")

# 5. Set proper conflict resolution mode
spark.conf.set("spark.hadoop.fs.s3a.committer.staging.conflict-mode", "replace")
# Options: fail, replace, append

# 6. Clean up orphaned _temporary directories (schedule weekly)
import subprocess
# aws s3 rm --recursive s3://bucket/output/_temporary/
```

---

## Issue #45: Data Encoding/Compression Mismatch

**Frequency**: Medium  
**Severity**: Medium - slow reads, excessive storage  
**Spark Component**: ParquetOutputFormat, OrcOutputFormat

### Symptoms
```
# Files stored with gzip (slow decompression) instead of snappy/zstd
# Spark reading LZO files without codec installed → failure
# Stored as uncompressed → 5x storage cost
# Downstream tools can't read zstd-compressed files
# CPU bottleneck on decompression instead of I/O bottleneck
```

### Root Cause
- Default compression not set explicitly (falls through to framework default)
- Mixed compression in same table (different write jobs)
- Codec not available on all nodes
- Using row-level compression (gzip CSV) vs columnar compression (Parquet+snappy)

### Solution
```python
# 1. Set optimal compression for Parquet (Snappy: fast, ZStd: balanced)
spark.conf.set("spark.sql.parquet.compression.codec", "zstd")
# Options: none, uncompressed, snappy, gzip, lzo, brotli, lz4, zstd
# Recommendation:
#   - Hot data (frequent reads): snappy (fast decompress)
#   - Cold data (archival): zstd (best ratio)
#   - Never: gzip for Parquet (slow, no splittable benefit for columnar)

# 2. For ORC format
spark.conf.set("spark.sql.orc.compression.codec", "zstd")

# 3. Shuffle compression (internal)
spark.conf.set("spark.shuffle.compress", "true")
spark.conf.set("spark.io.compression.codec", "lz4")  # Fast for shuffle
# OR zstd for better ratio at slight CPU cost

# 4. Verify compression being used
df = spark.read.parquet("s3://bucket/table/")
# Check file metadata:
spark.sql("DESCRIBE EXTENDED catalog.db.table").show(truncate=False)

# 5. Standardize compression across team
# Write with explicit codec:
df.write \
    .option("compression", "zstd") \
    .parquet("s3://bucket/output/")

# 6. Rewrite legacy files with optimal compression
spark.read.parquet("s3://old_gzip_data/") \
    .write \
    .option("compression", "zstd") \
    .parquet("s3://new_zstd_data/")
```

### Compression Benchmark (1TB TPC-DS)
```
| Codec     | Ratio  | Write Speed | Read Speed | CPU Usage |
|-----------|--------|-------------|------------|-----------|
| none      | 1.0x   | 800 MB/s   | 900 MB/s   | Low       |
| snappy    | 2.5x   | 600 MB/s   | 850 MB/s   | Low       |
| lz4       | 2.3x   | 650 MB/s   | 870 MB/s   | Low       |
| zstd(1)   | 3.2x   | 400 MB/s   | 800 MB/s   | Medium    |
| zstd(3)   | 3.5x   | 300 MB/s   | 780 MB/s   | Medium    |
| gzip      | 3.0x   | 100 MB/s   | 400 MB/s   | High      |
```

---

## Issue #46: Predicate Pushdown Not Working

**Frequency**: High  
**Severity**: High - reading 10-100x more data than needed  
**Spark Component**: DataSourceV2, ParquetFilters, FileSourceScanExec

### Symptoms
```
# Query has WHERE clause but Spark reads all data
# Physical plan shows:
PushedFilters: []  ← EMPTY! No pushdown!
# OR
PushedFilters: [IsNotNull(date)]  ← Only null check, not actual filter!
# Reading 500GB when should read 5GB
```

### Root Cause
- Filter uses UDF (can't push UDFs to storage)
- Complex expressions not supported for pushdown
- Column statistics not available in Parquet files
- Data source doesn't support filter pushdown
- Type mismatch between filter and column type

### Solution
```python
# 1. Use simple predicates that support pushdown
# Supported: =, <, >, <=, >=, IN, IS NULL, IS NOT NULL, AND, OR, NOT
# NOT supported: UDFs, LIKE with leading wildcard, complex expressions

# BAD (no pushdown):
df.filter(my_udf(F.col("status")) == "active")

# GOOD (pushdown works):
df.filter(F.col("status") == "active")
df.filter(F.col("amount").between(100, 1000))
df.filter(F.col("country").isin("US", "UK", "CA"))

# 2. Verify pushdown in plan
df.filter(F.col("date") == "2024-01-01").explain(mode="formatted")
# Look for: PushedFilters: [EqualTo(date, 2024-01-01)]

# 3. Enable Parquet filter pushdown
spark.conf.set("spark.sql.parquet.filterPushdown", "true")  # Default true
spark.conf.set("spark.sql.parquet.recordLevelFilter.enabled", "true")

# 4. Write data sorted by filter columns for better min/max pruning
df.sortWithinPartitions("date", "country").write.parquet(...)
# Parquet stores min/max per row group → better filtering

# 5. For Iceberg: column statistics in manifests enable aggressive pruning
# No action needed - Iceberg automatically tracks min/max/null_count

# 6. Split complex filter into pushable + non-pushable parts
# Instead of: WHERE complex_condition(col) AND col2 = 'X'
# Spark may fail to push col2 filter if combined with non-pushable
# Restructure:
df_filtered = df.filter(F.col("col2") == "X")  # This pushes down
df_final = df_filtered.filter(complex_condition(F.col("col")))  # Applied after read
```

---

## Issue #47: Iceberg Table Maintenance Neglected (Performance Degradation)

**Frequency**: High  
**Severity**: Medium-High - gradual degradation  
**Spark Component**: Iceberg Table, Metadata Layer

### Symptoms
```
# Query getting slower over weeks/months
# Manifest files: 50,000+ (should be < 1000)
# Data files: 5 million (many tiny files from streaming)
# Snapshots: 10,000+ (never expired)
# Metadata.json: 500MB (takes 30s just to parse)
# Planning time: 5 minutes (before any data is read)
```

### Root Cause
- No scheduled maintenance (compaction, snapshot expiry, orphan removal)
- Streaming appends create many small files
- Snapshot retention unlimited (every commit creates new snapshot)
- Manifest rewrite never executed

### Solution
```python
# 1. Expire old snapshots (keep last 7 days)
spark.sql("""
    CALL catalog.system.expire_snapshots(
        table => 'db.events',
        older_than => TIMESTAMP '2024-01-01 00:00:00',
        retain_last => 100
    )
""")

# 2. Compact data files (small files → 256MB targets)
spark.sql("""
    CALL catalog.system.rewrite_data_files(
        table => 'db.events',
        strategy => 'sort',
        sort_order => 'date ASC, user_id ASC',
        options => map(
            'target-file-size-bytes', '268435456',
            'min-file-size-bytes', '67108864',
            'max-file-size-bytes', '536870912',
            'partial-progress.enabled', 'true'
        )
    )
""")

# 3. Rewrite manifests (reduce manifest count)
spark.sql("""
    CALL catalog.system.rewrite_manifests(
        table => 'db.events',
        use_caching => true
    )
""")

# 4. Remove orphan files (leaked from failed writes)
spark.sql("""
    CALL catalog.system.remove_orphan_files(
        table => 'db.events',
        older_than => TIMESTAMP '2024-06-01 00:00:00',
        dry_run => true  -- Preview first!
    )
""")

# 5. Schedule all maintenance (Airflow DAG, daily)
# Order matters: expire → compact → rewrite manifests → remove orphans

# 6. Monitor table health metrics
spark.sql("SELECT * FROM catalog.db.events.metadata_log_entries").show()
spark.sql("SELECT COUNT(*) FROM catalog.db.events.manifests")
spark.sql("SELECT COUNT(*) FROM catalog.db.events.files")
spark.sql("SELECT COUNT(*) FROM catalog.db.events.snapshots")
```

---

## Issue #48: S3 Consistency Issues (Stale Reads)

**Frequency**: Low (mitigated since S3 strong consistency Dec 2020)  
**Severity**: Critical when it happens - data loss/corruption  
**Spark Component**: S3A FileSystem, FileStatusCache

### Symptoms
```
# File just written but read returns old/empty data
# Job B reads table written by Job A but sees old version
# FileNotFoundException for files that were just committed
# Iceberg metadata points to files that "don't exist" (S3 caching)
```

### Root Cause
- S3 provides strong read-after-write consistency since Dec 2020
- BUT: CDN/proxy caches, S3-compatible stores (MinIO, Ceph) may not
- File listing cache in Spark driver (InMemoryFileIndex)
- Iceberg catalog cache not refreshed
- Cross-region replication lag

### Solution
```python
# 1. Disable file status caching for critical paths
spark.conf.set("spark.hadoop.fs.s3a.metadatastore.impl",
    "org.apache.hadoop.fs.s3a.s3guard.NullMetadataStore")

# 2. Force catalog refresh before reading
spark.sql("REFRESH TABLE catalog.db.events")

# 3. For Iceberg: refresh table metadata
spark.sql("CALL catalog.system.refresh('db.events')")

# 4. For concurrent writers: use Iceberg/Delta optimistic locking
# Iceberg uses optimistic concurrency with retry on conflict
# No stale reads because metadata pointer is atomically updated

# 5. Cross-region: wait for replication before reading
import time
time.sleep(5)  # Wait for cross-region replication (crude but effective)

# 6. Validate reads
df = spark.read.parquet("s3://bucket/output/")
if df.count() == 0:
    # Retry with forced refresh
    spark.catalog.refreshTable("output")
    df = spark.read.parquet("s3://bucket/output/")
```

---

## Issue #49: Delta/Iceberg Transaction Conflicts (Concurrent Writes)

**Frequency**: Medium  
**Severity**: High - write failures requiring retry  
**Spark Component**: Iceberg/Delta Commit Protocol

### Symptoms
```
# Iceberg:
org.apache.iceberg.exceptions.CommitFailedException:
  Cannot commit: found conflicting changes in table

# Delta:
io.delta.exceptions.ConcurrentModificationException:
  A concurrent transaction modified the table

# Multiple Spark jobs writing to same table at same time
# Streaming + compaction job conflicting
```

### Root Cause
- Two jobs modify overlapping partitions simultaneously
- Optimistic concurrency detects conflict at commit time
- Compaction job conflicts with streaming append
- Schema evolution + data write happening in parallel

### Solution
```python
# 1. For Iceberg: configure retry on conflict
spark.conf.set("spark.sql.iceberg.commit.retry.num-retries", "10")
spark.conf.set("spark.sql.iceberg.commit.retry.min-wait-ms", "100")
spark.conf.set("spark.sql.iceberg.commit.retry.max-wait-ms", "60000")

# 2. Isolate write targets (different partitions = no conflict)
# Job A writes partition: date=2024-01-01
# Job B writes partition: date=2024-01-02
# No conflict because different files affected

# 3. Use WAP (Write-Audit-Publish) pattern for safe writes
spark.conf.set("spark.wap.id", "write-job-123")
df.writeTo("catalog.db.events").append()
# Then validate, then:
spark.sql("CALL catalog.system.cherrypick_snapshot('db.events', 12345)")

# 4. For streaming + compaction conflicts:
# Option A: Pause streaming during compaction (simple but adds latency)
# Option B: Use Iceberg's partition-level locking (no conflict if different partitions)
# Option C: Schedule compaction on old partitions only (streaming writes to current)

# 5. For Delta: enable auto-retry
spark.conf.set("spark.databricks.delta.commitInfo.enabled", "true")
# Delta retries automatically on conflict for append operations

# 6. Design for conflict avoidance:
# - Streaming: always appends to latest partition
# - Compaction: only touches partitions > 1 hour old
# - Schema changes: run during maintenance window (no concurrent writes)
```

---

## Issue #50: Column Pruning Not Applied (Reading All Columns)

**Frequency**: High  
**Severity**: Medium-High - reading 5-20x more I/O than needed  
**Spark Component**: ColumnPruning (Catalyst rule), FileSourceScanExec

### Symptoms
```
# Table has 500 columns, query needs 5
# But Spark reads all 500 from Parquet (5GB instead of 50MB)
# Plan shows: ReadSchema: struct<col1,col2,...col500>  ← ALL columns!
# Expected: ReadSchema: struct<col1,col2,col3,col4,col5>
```

### Root Cause
- `SELECT *` anywhere in the query chain
- UDF references DataFrame (forces full read)
- Schema inference reads all columns first
- Join/filter on column prevents pruning of that column after use
- Nested struct access not pruned (Spark reads entire struct)

### Solution
```python
# 1. Always select only needed columns EARLY in the pipeline
# BAD:
df = spark.read.parquet("s3://table/")  # All 500 columns loaded
result = df.filter(...).select("col1", "col2")  # Pruning might not reach scan

# GOOD:
df = spark.read.parquet("s3://table/").select("col1", "col2", "filter_col")
result = df.filter(...)

# 2. For nested structs, select specific fields
# BAD (reads entire struct):
df.select("nested_struct")

# GOOD (reads only specific field):
df.select("nested_struct.field1", "nested_struct.field2")
spark.conf.set("spark.sql.optimizer.nestedSchemaPruning.enabled", "true")

# 3. Enable nested schema pruning
spark.conf.set("spark.sql.optimizer.nestedSchemaPruning.enabled", "true")  # Default true in 3.x

# 4. Verify column pruning in plan
df.select("col1", "col2").explain(mode="formatted")
# Check ReadSchema: should show ONLY requested columns

# 5. For UDFs, use Arrow-based pandas UDFs (supports pruning)
@F.pandas_udf("double")
def my_udf(col1: pd.Series) -> pd.Series:
    return col1 * 2
# Only col1 is read from storage

# 6. For tables with 500+ columns: consider vertical partitioning
# Split into: core_columns (frequently accessed), extended_columns (rare)
# Join on key only when extended columns needed
```

---

## Summary: Storage & I/O Decision Tree

```
I/O performance issue
├── Slow reads
│   ├── S3 throttling (503) → Issue #41 (prefix distribution, Iceberg metadata)
│   ├── Millions of small files → Issue #42 (compaction)
│   ├── Parquet footer overhead → Issue #43 (caching, column pruning)
│   ├── No predicate pushdown → Issue #46 (simple filters, sorted data)
│   ├── Reading all columns → Issue #50 (column pruning, nested schema)
│   └── Partition pruning broken → See Category 3
├── Slow/failed writes
│   ├── Commit failures on S3 → Issue #44 (magic committer, Iceberg)
│   ├── Concurrent write conflicts → Issue #49 (retry, partition isolation)
│   └── Wrong compression → Issue #45 (zstd/snappy)
├── Data correctness
│   ├── Stale reads → Issue #48 (refresh, strong consistency)
│   └── Missing files after write → Issue #44 (commit protocol)
└── Gradual degradation
    └── Table getting slower over time → Issue #47 (Iceberg maintenance)
```
