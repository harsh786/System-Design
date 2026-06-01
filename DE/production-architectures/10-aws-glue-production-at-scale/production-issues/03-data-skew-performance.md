# Data Skew & Performance Issues (#26-40)

> Data skew is the **silent killer** of Glue jobs at scale. A job that processes 1TB in 20 minutes
> can take 8 hours if one partition holds 50% of the data. These issues turn $100 jobs into $2000 jobs.

---

## Issue #26: Single-Key Data Skew (Hot Partition Problem)

### Severity: P2 | Frequency: Daily at >1B records

### Symptoms
```
Spark UI - Stage Summary:
┌─────────┬───────────┬──────────┬─────────────────────────┐
│ Metric  │ Min       │ Median   │ Max                     │
├─────────┼───────────┼──────────┼─────────────────────────┤
│ Duration│ 8s        │ 15s      │ 7,200s (2 hours!)       │
│ Input   │ 45MB      │ 128MB    │ 48GB                    │
│ Records │ 500K      │ 1.2M    │ 850M                    │
└─────────┴───────────┴──────────┴─────────────────────────┘

# 199 tasks finish in 15s, 1 task runs for 2 hours
# Total job time = max task time = 2 hours
```

### Root Cause
```
Power-law distribution in real data:
- E-commerce: "Amazon" merchant has 100x more transactions than average
- Social: Top 0.1% users generate 30% of events  
- IoT: Factory #7 has 100x more sensors than others
- Logs: One microservice generates 80% of log volume

When you groupBy/join on these keys, one partition gets all hot-key data.
```

### Fix
```python
# TECHNIQUE 1: Two-Phase Aggregation (Salting)
# ─────────────────────────────────────────────
SALT_FACTOR = 200  # Split hot keys across 200 partitions

# Phase 1: Partial aggregation with salt
df_salted = df.withColumn("salt", (F.rand() * SALT_FACTOR).cast("int"))
partial_agg = df_salted.groupBy("merchant_id", "salt").agg(
    F.sum("amount").alias("partial_sum"),
    F.count("*").alias("partial_count"),
    F.max("amount").alias("partial_max")
)

# Phase 2: Combine partial results (now evenly distributed)
final_agg = partial_agg.groupBy("merchant_id").agg(
    F.sum("partial_sum").alias("total_amount"),
    F.sum("partial_count").alias("total_count"),
    F.max("partial_max").alias("max_amount")
)

# TECHNIQUE 2: Isolate and Broadcast Hot Keys
# ─────────────────────────────────────────────
# Identify hot keys (pre-computed or from previous run)
hot_keys = ["amazon", "walmart", "target"]  # Top merchants by volume

# Split traffic
df_hot = df.filter(F.col("merchant_id").isin(hot_keys))
df_normal = df.filter(~F.col("merchant_id").isin(hot_keys))

# Hot keys: broadcast the small dimension side
dim_hot = dim_merchants.filter(F.col("merchant_id").isin(hot_keys))
result_hot = df_hot.join(F.broadcast(dim_hot), "merchant_id")

# Normal keys: regular sort-merge join
result_normal = df_normal.join(dim_merchants, "merchant_id")

# Combine
result = result_hot.unionByName(result_normal)

# TECHNIQUE 3: AQE Skew Join (Glue 3.0+, Spark 3.x)
# ─────────────────────────────────────────────────────
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256MB")
# AQE automatically splits skewed partitions at runtime
```

---

## Issue #27: Null Values Causing Massive Skew in Joins

### Severity: P2 | Frequency: Very common (every dataset has nulls)

### Symptoms
```
# Join produces incorrect results AND is extremely slow
# One partition has all null-key records (millions)
# null == null evaluates to UNKNOWN in SQL (not matched), but
# all nulls still go to same hash partition during shuffle
```

### Root Cause
```
Hash(null) → same bucket for ALL null records.
If 20% of records have null join key = 20% of data in one partition.

Additionally: null != null in SQL semantics, so they don't join anyway.
Result: massive partition with records that produce no output.
= Wasted computation + skew.
```

### Fix
```python
# Fix 1: Filter nulls BEFORE join
df_with_key = df.filter(F.col("join_key").isNotNull())
df_nulls = df.filter(F.col("join_key").isNull())

# Join only valid keys
joined = df_with_key.join(dim, "join_key")

# Handle nulls separately (default values)
nulls_handled = df_nulls.withColumn("dim_value", F.lit("UNKNOWN"))

# Combine
result = joined.unionByName(nulls_handled, allowMissingColumns=True)

# Fix 2: Replace nulls with random values (if null handling is "skip join")
# Useful when you just want to exclude nulls from join but keep them in output
df = df.withColumn(
    "join_key_safe",
    F.when(F.col("join_key").isNull(), F.concat(F.lit("NULL_"), F.monotonically_increasing_id()))
     .otherwise(F.col("join_key"))
)
# Each null gets unique key → distributed evenly → no match in join → filtered out later
```

---

## Issue #28: Small Files Problem (Millions of Tiny Files)

### Severity: P2 | Frequency: Daily with streaming/event sources

### Symptoms
```
# Glue Crawler takes 4+ hours to catalog new partitions
# Job startup takes 30+ minutes (S3 listing)
# 90% of job time is task scheduling overhead, not computation
# Each file is 1-100KB (ideal: 128MB-1GB)

# S3 metrics:
# Objects in prefix: 5,000,000
# Average object size: 50KB
# ListObjects calls: 50,000/minute (approaching throttle)
```

### Root Cause
```
Sources that create small files:
- Kinesis Firehose with low buffer (60s/1MB minimum)
- Lambda writing per-event files
- Spark streaming with very short micro-batch (10s)
- Kafka Connect with small flush interval
- Multiple small producers writing independently

Impact chain:
Small files → Many S3 LIST calls → S3 throttling →
→ Many Spark tasks → Scheduler overhead → Slow job →
→ High DPU cost → Wasted money
```

### Fix
```python
# IMMEDIATE FIX: groupFiles in Glue read
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="events",
    additional_options={
        "groupFiles": "inPartition",
        "groupSize": "134217728",  # 128MB target per group
        # Groups multiple small files into single partition for processing
    },
    transformation_ctx="grouped_read"
)

# COMPACTION JOB (scheduled daily/hourly):
def compact_small_files(source_path, target_path, target_size_mb=256):
    """Read small files, write optimally-sized files."""
    df = spark.read.parquet(source_path)
    
    # Calculate optimal partition count
    total_size_bytes = sum(
        f.length for f in spark._jvm.org.apache.hadoop.fs.Path(source_path)
            .getFileSystem(spark._jsc.hadoopConfiguration()).listStatus(
                spark._jvm.org.apache.hadoop.fs.Path(source_path))
    )
    target_partitions = max(1, total_size_bytes // (target_size_mb * 1024 * 1024))
    
    # Rewrite with optimal file sizes
    df.coalesce(target_partitions) \
        .write.mode("overwrite") \
        .parquet(target_path)

# ICEBERG AUTO-COMPACTION:
spark.sql("""
    CALL system.rewrite_data_files(
        table => 'db.events',
        options => map(
            'target-file-size-bytes', '268435456',
            'min-file-size-bytes', '67108864',
            'max-file-size-bytes', '536870912'
        )
    )
""")

# PREVENTION: Configure upstream to write larger files
# Kinesis Firehose: buffer_size=128MB, buffer_interval=300s
# Spark Streaming: trigger(processingTime="5 minutes")
```

---

## Issue #29: Shuffle Partition Count Too Low (Default 200)

### Severity: P2 | Frequency: Every job processing >10GB

### Symptoms
```
# Spark default: spark.sql.shuffle.partitions = 200
# For 1TB shuffle: each partition = 5GB → executor OOM
# For 100TB shuffle: each partition = 500GB → definitely OOM

# Spark UI shows:
# Stage with 200 tasks, each processing 5GB+ of shuffle data
# Tasks timing out or OOM
```

### Root Cause
```
Spark's default 200 shuffle partitions was designed for small datasets.
At billion-record scale, you need thousands of partitions.

Rule of thumb: target 128-256MB per shuffle partition.
1TB shuffle ÷ 256MB = 4000 partitions needed
10TB shuffle ÷ 256MB = 40000 partitions needed
```

### Fix
```python
# Fix 1: Set appropriate shuffle partitions
data_size_gb = 1000  # 1TB
target_partition_mb = 256
optimal_partitions = (data_size_gb * 1024) // target_partition_mb
spark.conf.set("spark.sql.shuffle.partitions", str(optimal_partitions))  # 4000

# Fix 2: Use AQE to auto-tune (Glue 3.0+)
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.initialPartitionNum", "8000")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "256MB")
# AQE starts with 8000 partitions, coalesces to optimal at runtime

# Fix 3: Dynamic partition count based on input size
def calculate_shuffle_partitions(input_path, target_mb=256):
    """Dynamically set partitions based on actual data size."""
    import subprocess
    result = subprocess.run(
        ['aws', 's3', 'ls', '--recursive', '--summarize', input_path],
        capture_output=True, text=True
    )
    # Parse total size from output
    total_bytes = parse_s3_size(result.stdout)
    partitions = max(200, total_bytes // (target_mb * 1024 * 1024))
    spark.conf.set("spark.sql.shuffle.partitions", str(partitions))
    logger.info(f"Set shuffle partitions to {partitions} for {total_bytes/1e9:.1f}GB")
```

---

## Issue #30: Cartesian Product from Incorrect Join (Accidental Cross Join)

### Severity: P1 | Frequency: Monthly (developer error)

### Symptoms
```
# Job runs for hours with no progress
# Output size explodes: 1M × 1M = 1 TRILLION rows
# Executors OOM immediately
# Spark UI: single stage with enormous shuffle write

# WARNING in logs (Spark 3.x):
# "Detected implicit cartesian product for INNER join between logical plans"
```

### Root Cause
```
Common causes:
1. Join key has duplicates on BOTH sides (M:N join explosion)
2. Missing join condition (no ON clause → cross join)
3. Wrong column name in join (happens with similarly-named columns)
4. Date range join without bounds (every row matches every row)

Example: orders JOIN order_items ON order_date = item_date
(Should be: ON order_id = order_item_order_id)
If 1M orders share same date, each matches all items on that date.
```

### Fix
```python
# Prevention 1: Enable cross join detection
spark.conf.set("spark.sql.crossJoin.enabled", "false")  # Fail fast
# Will throw AnalysisException if accidental cross join detected

# Prevention 2: Validate join cardinality before joining
def safe_join(left, right, join_key, expected_ratio=10):
    """Validate join won't explode before executing."""
    left_count = left.select(join_key).distinct().count()
    right_count = right.select(join_key).distinct().count()
    left_dupes = left.groupBy(join_key).count().filter("count > 1").count()
    right_dupes = right.groupBy(join_key).count().filter("count > 1").count()
    
    if left_dupes > 0 and right_dupes > 0:
        max_expansion = left.groupBy(join_key).count().agg(F.max("count")).collect()[0][0]
        logger.warning(
            f"M:N join detected! Max key frequency: {max_expansion}. "
            f"Output could be {max_expansion}x input size."
        )
        if max_expansion > expected_ratio:
            raise Exception(f"Join would explode by {max_expansion}x. Aborting.")
    
    return left.join(right, join_key)

# Prevention 3: Add row count checkpoint after joins
result = df1.join(df2, "key")
result_count = result.count()
input_count = df1.count()

if result_count > input_count * 5:  # More than 5x expansion = suspicious
    raise Exception(
        f"Join explosion detected: input={input_count}, output={result_count}. "
        f"Expansion ratio: {result_count/input_count:.1f}x"
    )
```

---

## Issue #31: Slow S3 Listing for Large Partitioned Tables

### Severity: P2 | Frequency: Daily with >10K partitions

### Symptoms
```
# Job spends 30-60 minutes in "Planning" before any tasks run
# CloudWatch shows: very low DPU utilization in first 30 minutes
# S3 ListObjects requests: 100K+ per job start
# Particularly slow with deeply nested partitions:
#   year/month/day/hour/region → 365 × 24 × 10 = 87K partitions
```

### Root Cause
```
Spark's default file listing is sequential and recursive.
For table with 100K partitions:
- Each partition requires ListObjects call
- S3 ListObjects returns max 1000 keys per call
- 100K partitions × serial calls = minutes of listing

Glue Data Catalog has partition metadata but Spark still verifies on S3.
```

### Fix
```python
# Fix 1: Use Glue Data Catalog for partition listing (skip S3 listing)
spark.conf.set("spark.sql.hive.metastorePartitionPruning", "true")
spark.conf.set("spark.sql.hive.filesourcePartitionFilePruning", "true")

# Fix 2: Push down partition predicate to catalog
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="events",
    push_down_predicate="year='2024' AND month='01'",  # Prune at catalog level
    transformation_ctx="ctx"
)
# Only lists S3 files in matching partitions

# Fix 3: Parallel S3 listing
spark.conf.set("spark.sql.sources.parallelPartitionDiscovery.parallelism", "64")
spark.conf.set("spark.hadoop.mapreduce.input.fileinputformat.list-status.num-threads", "64")

# Fix 4: Use Iceberg tables (metadata-based, no S3 listing needed)
# Iceberg stores file list in manifest files
# Reading manifest: 1 S3 GET vs 100K ListObjects
df = spark.read.format("iceberg").load("db.events")
# Partition pruning happens in metadata layer, not S3

# Fix 5: Reduce partition depth
# Instead of: year/month/day/hour (87K+ partitions)
# Use: date_hour (e.g., 2024-01-15-10) → single level, 8760 partitions/year
```

---

## Issue #32: Write Amplification (Excessive S3 PUTs)

### Severity: P3 | Frequency: Common with repartitioned writes

### Symptoms
```
# Writing 1GB of data creates 50K tiny files on S3
# S3 PUT request costs spike ($5/million PUTs)
# Downstream readers slow due to small files

# Cause visible in Spark UI:
# Output tasks: 50,000 (one file per task)
# Average output file size: 20KB
```

### Root Cause
```
Spark writes one file per (partition_column_value × task).
If you have:
- 100 date partitions × 500 shuffle partitions = 50,000 files
- Some partitions get tiny slices: 20KB files

This is the "small files on write" problem.
```

### Fix
```python
# Fix 1: Coalesce before write
output_df.coalesce(100) \
    .write.partitionBy("date") \
    .parquet("s3://output/")
# 100 tasks → max 100 files per date partition

# Fix 2: Repartition by output partition key
output_df.repartition("date") \
    .write.partitionBy("date") \
    .parquet("s3://output/")
# Each date gets its own task → one file per date (might be too large)

# Fix 3: Target specific file size with maxRecordsPerFile
output_df.write \
    .option("maxRecordsPerFile", 1000000) \
    .partitionBy("date") \
    .parquet("s3://output/")
# Splits large partitions into ~1M record files

# Fix 4: Use Iceberg write distribution mode
spark.conf.set("spark.sql.iceberg.distribution-mode", "hash")  # or "range"
# Iceberg optimizes file sizes during write

# Fix 5: Post-write compaction (scheduled job)
# See Issue #28 for compaction job implementation
```

---

## Issue #33: Inefficient Predicate Pushdown (Full Table Scan)

### Severity: P2 | Frequency: Very common (silent performance killer)

### Symptoms
```
# Job reads 10TB but only needs 100GB (100x over-read)
# S3 bytes read: 10TB (expected: 100GB)
# Partition pruning not working
# Parquet row group filtering not working
```

### Root Cause
```
Predicate pushdown fails silently when:
1. Filter uses UDF (not pushable)
2. Filter on derived column (computed after read)
3. Column type mismatch (string partition filtered as int)
4. Complex expression (OR with different partition columns)
5. Filter applied AFTER join (too late for source pruning)
```

### Fix
```python
# BAD: UDF prevents pushdown
@udf(BooleanType())
def is_recent(date_str):
    return date_str >= "2024-01-01"

df = spark.read.parquet("s3://data/").filter(is_recent("date"))
# Full table scan! UDF is opaque to optimizer.

# GOOD: Native expression enables pushdown
df = spark.read.parquet("s3://data/").filter(F.col("date") >= "2024-01-01")
# Pushed to Parquet reader → only reads matching row groups

# BAD: Filter after join (reads everything first)
df = spark.read.parquet("s3://huge_table/")
dim = spark.read.parquet("s3://dim/")
result = df.join(dim, "key").filter(F.col("date") >= "2024-01-01")

# GOOD: Filter before join (prunes early)
df = spark.read.parquet("s3://huge_table/").filter(F.col("date") >= "2024-01-01")
dim = spark.read.parquet("s3://dim/")
result = df.join(dim, "key")

# Verify pushdown is working:
df.filter(F.col("date") >= "2024-01-01").explain(True)
# Look for "PushedFilters" in physical plan:
# PushedFilters: [GreaterThanOrEqual(date, 2024-01-01)]
```

---

## Issue #34: Excessive Shuffle Due to Unnecessary Repartitioning

### Severity: P2 | Frequency: Common developer mistake

### Symptoms
```
# Spark UI shows: massive shuffle write/read between stages
# Shuffle write: 5TB (entire dataset reshuffled)
# Network I/O spikes during shuffle phases
# Job takes 3x longer than expected
```

### Root Cause
```python
# Developer adds repartition "for performance" without understanding cost:
df = spark.read.parquet("s3://data/")  # Already 2000 partitions
df = df.repartition(2000)  # FULL SHUFFLE of entire dataset for no reason!
df = df.repartition("date")  # Another full shuffle!
result = df.groupBy("date").agg(F.sum("amount"))  # Yet another shuffle!
# Total: 3 shuffles when 1 would suffice
```

### Fix
```python
# Rule: Never repartition unless you have a specific reason
# Let Spark's optimizer handle partitioning

# If you DO need to repartition for write optimization, do it LAST:
result = df.groupBy("date").agg(F.sum("amount"))
result.repartition("date").write.partitionBy("date").parquet("s3://output/")
# Only 1 shuffle (groupBy) + 1 repartition (for optimal write)

# Use coalesce (no shuffle) instead of repartition when reducing partitions:
df.coalesce(100)  # No shuffle - just combines partitions
df.repartition(100)  # Full shuffle - expensive!

# Avoid redundant shuffles in groupBy chains:
# BAD: Two shuffles
agg1 = df.groupBy("key1").agg(F.sum("v1").alias("s1"))  # Shuffle 1
agg2 = df.groupBy("key1").agg(F.sum("v2").alias("s2"))  # Shuffle 2
result = agg1.join(agg2, "key1")  # Shuffle 3!

# GOOD: Single shuffle
result = df.groupBy("key1").agg(
    F.sum("v1").alias("s1"),
    F.sum("v2").alias("s2")
)  # Only 1 shuffle
```

---

## Issue #35: Slow Job Due to Non-Splittable Compression (gzip)

### Severity: P2 | Frequency: Common with external data sources

### Symptoms
```
# Reading 100 × 1GB gzip files
# Only 100 tasks created (1 per file, non-splittable)
# Each task reads 1GB sequentially - no parallelism within file
# With 200 workers, 100 are idle!

# Spark UI: 100 tasks, each taking 5 minutes
# Total time: 5 minutes (100 parallel tasks, but only 100 not 2000)
```

### Root Cause
```
Gzip files cannot be split - must be read from beginning to end.
One gzip file = one Spark partition = one task.
100 gzip files = max 100-way parallelism regardless of cluster size.

Splittable formats: Snappy, LZO, ZSTD, bzip2 (with index)
Non-splittable: gzip, deflate
```

### Fix
```python
# Fix 1: Convert to splittable format on ingestion
# First job: gzip → snappy parquet (one-time conversion)
df = spark.read.csv("s3://landing/data/*.gz")
df.write.option("compression", "snappy").parquet("s3://processed/data/")

# Fix 2: If you must read gzip, repartition immediately after
df = spark.read.csv("s3://data/*.gz")  # 100 partitions (limited)
df = df.repartition(2000)  # Redistribute for downstream parallelism
# Note: still limited to 100-way parallelism for the READ phase

# Fix 3: Split large gzip files before processing
# Use Lambda/Step Functions to split 1GB gzip into 10 × 100MB
# Then Glue can read with 1000-way parallelism

# Fix 4: Use Glue's groupFiles (doesn't help with gzip but helps with many small gzip)
# groupFiles helps when you have 1M × 1KB gzip files (opposite problem)

# BEST PRACTICE: Always use Snappy or ZSTD for data lake files
df.write \
    .option("compression", "zstd") \
    .parquet("s3://output/")
# ZSTD: better compression than Snappy, still splittable
```

---

## Issue #36: Stage Barrier Causing Sequential Execution

### Severity: P3 | Frequency: Common in complex DAGs

### Symptoms
```
# Pipeline has 5 stages but they execute sequentially
# Cluster is 50% idle during most of the job
# Total time = sum of all stages (not max of parallel paths)
```

### Root Cause
```
Spark executes stages sequentially when:
1. Stage B depends on full output of Stage A (shuffle dependency)
2. All actions are chained linearly (no parallel branches)
3. Persist/cache forces materialization before next stage

In Glue: single-threaded job script with sequential operations
can't leverage cluster parallelism across independent computations.
```

### Fix
```python
# Fix 1: Use parallel DataFrame operations where possible
from concurrent.futures import ThreadPoolExecutor

def process_table(table_name):
    df = spark.read.table(table_name)
    return df.groupBy("key").agg(F.sum("value"))

# Process independent tables in parallel threads
tables = ["table_a", "table_b", "table_c", "table_d"]
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_table, tables))

# Join results
final = results[0]
for r in results[1:]:
    final = final.join(r, "key", "outer")

# Fix 2: Split into multiple Glue jobs running in parallel via Workflow
# Job A and Job B have no dependency → run concurrently
# Job C depends on A and B → trigger after both complete
```

---

## Issue #37: Slow Writes Due to S3 Consistency Check Overhead

### Severity: P3 | Frequency: Common with many output partitions

### Symptoms
```
# Write phase takes 10x longer than expected
# S3 HEAD requests spike after write completes
# Job logs show: "Listing files in output location for verification"
# _SUCCESS file creation takes minutes
```

### Root Cause
```
Spark's FileOutputCommitter verifies all written files exist after write.
With 10K output files across 1000 partitions:
- 10K HEAD requests for verification
- 10K rename operations (temp → final path)
- _SUCCESS marker file creation

S3's eventual consistency (historical) and list consistency delays.
Note: S3 now has strong consistency, but Spark's committer still does verification.
```

### Fix
```python
# Fix 1: Use EMRFS S3-optimized committer (available in Glue 3.0+)
spark.conf.set("spark.sql.sources.commitProtocolClass",
    "org.apache.spark.sql.execution.datasources.SQLHadoopMapReduceCommitProtocol")
spark.conf.set("spark.sql.parquet.output.committer.class",
    "org.apache.spark.sql.execution.datasources.InMemoryFileIndex")

# Fix 2: Use Iceberg (no output committer overhead)
# Iceberg writes files directly and commits atomically via metadata update
df.writeTo("db.output_table").append()

# Fix 3: Reduce output partition count
df.coalesce(200).write.parquet("s3://output/")
# Fewer files = fewer verification calls = faster commit

# Fix 4: Disable output verification (risky but faster)
spark.conf.set("spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version", "2")
# Version 2 skips task-level commit (faster but less safe on failure)
```

---

## Issue #38: Window Function Performance on Large Partitions

### Severity: P2 | Frequency: Common in feature engineering

### Symptoms
```
# Window function with PARTITION BY user_id ORDER BY event_time
# One user has 50M events → single task processes 50M rows sequentially
# Window frame computation: O(n²) for unbounded preceding
# Task takes hours while others finish in seconds
```

### Root Cause
```python
# This innocent-looking window:
window = Window.partitionBy("user_id").orderBy("event_time")
df = df.withColumn("running_total", F.sum("amount").over(window))

# For user with 50M events: sorts 50M rows, computes running sum
# All 50M rows must be on SAME executor (window partition = physical partition)
# Time complexity: O(n log n) sort + O(n) computation
# Memory: all 50M rows in memory simultaneously
```

### Fix
```python
# Fix 1: Add secondary partition to limit window size
# Instead of window over ALL user events:
window = Window.partitionBy("user_id", "date").orderBy("event_time")
# Each day processed independently - max window size bounded

# Fix 2: Use bounded window frame
window = Window.partitionBy("user_id") \
    .orderBy("event_time") \
    .rowsBetween(-1000, 0)  # Only last 1000 rows, not unbounded
df = df.withColumn("recent_avg", F.avg("amount").over(window))

# Fix 3: Pre-aggregate before window
# Instead of window over raw events (50M rows/user):
daily_agg = df.groupBy("user_id", "date").agg(F.sum("amount").alias("daily_total"))
# Now window over daily aggregates (365 rows/user max):
window = Window.partitionBy("user_id").orderBy("date")
result = daily_agg.withColumn("running_total", F.sum("daily_total").over(window))

# Fix 4: Use larger worker type for window operations
# G.4X gives 48GB per executor - can hold larger windows in memory
```

---

## Issue #39: Inefficient DataFrame Operations Chain (No Predicate Pushdown)

### Severity: P3 | Frequency: Very common (developer awareness)

### Symptoms
```
# Job reads 10TB, filters to 100GB, then processes
# But reads the full 10TB first!
# Expected: filter pushed to source → only 100GB read
# Actual: all 10TB read, then filtered in memory
```

### Root Cause
```python
# Order of operations matters for pushdown:

# BAD: Operation between read and filter breaks pushdown
df = spark.read.parquet("s3://data/")
df = df.withColumn("year", F.year("timestamp"))  # Adds derived column
df = df.filter(F.col("year") == 2024)  # Filter on derived column - NOT pushed!
# Reads all data, computes year, then filters

# BAD: Filter on joined column can't push to source
df1 = spark.read.parquet("s3://big_table/")
df2 = spark.read.parquet("s3://small_table/")
result = df1.join(df2, "key")
result = result.filter(F.col("big_table_date") >= "2024-01-01")
# Filter applied after join - big_table fully scanned
```

### Fix
```python
# GOOD: Filter FIRST, on source columns
df = spark.read.parquet("s3://data/") \
    .filter(F.col("date") >= "2024-01-01")  # Pushed to Parquet reader!
# Only reads Parquet row groups where date >= 2024-01-01

# GOOD: Use partition columns for filtering (zero-cost)
# Table partitioned by date → filter eliminates entire directories
df = spark.read.parquet("s3://data/") \
    .filter(F.col("date") == "2024-01-15")
# Only lists and reads s3://data/date=2024-01-15/

# GOOD: Filter before join
df1 = spark.read.parquet("s3://big_table/") \
    .filter(F.col("date") >= "2024-01-01")  # Prune early!
df2 = spark.read.parquet("s3://small_table/")
result = df1.join(df2, "key")

# Verify pushdown with explain:
df.filter(F.col("date") >= "2024-01-01").explain("formatted")
# Check for: PushedFilters: [IsNotNull(date), GreaterThanOrEqual(date,2024-01-01)]
```

---

## Issue #40: Auto-Scaling Thrashing (Scale Up/Down Oscillation)

### Severity: P3 | Frequency: Common with variable workloads

### Symptoms
```
# Job alternates between phases:
# Phase 1 (heavy): needs 100 workers → scale up
# Phase 2 (light): needs 10 workers → scale down
# Phase 3 (heavy again): needs 100 → scale up again
# Each scale event: 2-3 minute delay for new workers to join
# Total wasted time: 20+ minutes of scaling overhead
```

### Root Cause
```
Auto-scaling reacts to current load, not predicted load.
Multi-stage jobs have variable resource needs:
- Read phase: I/O bound (few workers sufficient)
- Shuffle phase: compute bound (many workers needed)
- Write phase: I/O bound (few workers sufficient)

Auto-scaling sees low utilization during I/O → removes workers →
next stage needs them → requests back → cold start delay.
```

### Fix
```python
# Fix 1: Disable auto-scaling for predictable workloads
# Set fixed NumberOfWorkers in job definition
# Better: slight over-provision than scaling overhead

# Fix 2: Set aggressive scaling parameters
spark.conf.set("spark.dynamicAllocation.executorIdleTimeout", "300s")  # Wait 5 min before removing
spark.conf.set("spark.dynamicAllocation.schedulerBacklogTimeout", "5s")  # Scale up quickly
spark.conf.set("spark.dynamicAllocation.sustainedSchedulerBacklogTimeout", "5s")
spark.conf.set("spark.dynamicAllocation.executorAllocationRatio", "0.5")

# Fix 3: Set minimum workers floor
# In Glue job config:
# NumberOfWorkers = 50 (minimum)
# MaxCapacity = 200 (maximum)
# This ensures at least 50 workers always available

# Fix 4: Split job into stages with different resource profiles
# Job 1 (read + transform): 20 workers G.1X (I/O bound)
# Job 2 (heavy computation): 200 workers G.2X (compute bound)
# Job 3 (write): 20 workers G.1X (I/O bound)
# Each job right-sized, no scaling needed
```

---

## Performance Issue Decision Tree

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE DIAGNOSIS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Job slow?                                                           │
│  ├── One task much slower than others?                               │
│  │   ├── Skewed key? → Issue #26 (salting)                          │
│  │   ├── Null values? → Issue #27 (filter nulls)                    │
│  │   └── Window function? → Issue #38 (bound window)               │
│  │                                                                   │
│  ├── ALL tasks slow?                                                 │
│  │   ├── Too few partitions? → Issue #29 (increase shuffle parts)   │
│  │   ├── Full table scan? → Issue #33 (predicate pushdown)          │
│  │   ├── Gzip files? → Issue #35 (convert to snappy/zstd)          │
│  │   └── Too many shuffles? → Issue #34 (combine operations)       │
│  │                                                                   │
│  ├── Job produces too much data?                                     │
│  │   ├── Cartesian product? → Issue #30 (validate join)             │
│  │   └── Write amplification? → Issue #32 (coalesce before write)   │
│  │                                                                   │
│  ├── Job startup slow?                                               │
│  │   ├── Millions of small files? → Issue #28 (groupFiles)          │
│  │   ├── Too many partitions to list? → Issue #31 (catalog prune)   │
│  │   └── Auto-scaling cold start? → Issue #40 (fixed workers)       │
│  │                                                                   │
│  └── Intermittently slow?                                            │
│      ├── Scaling thrashing? → Issue #40 (min workers)               │
│      └── S3 throttling? → See Issue #63                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
