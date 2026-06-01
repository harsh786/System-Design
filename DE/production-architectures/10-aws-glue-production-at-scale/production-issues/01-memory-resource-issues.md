# Memory & Resource Exhaustion Issues (#1-15)

> The #1 category of AWS Glue production failures. At scale (>1TB daily), memory issues
> account for **40% of all job failures**. These are the issues that wake up on-call engineers at 3 AM.

---

## Issue #1: Driver Out-of-Memory (OOM) on Large Shuffle Operations

### Severity: P1 | Frequency: Daily at >10TB scale

### Symptoms
```
ERROR SparkContext: Error initializing SparkContext
java.lang.OutOfMemoryError: Java heap space
    at org.apache.spark.shuffle.sort.ShuffleExternalSorter
    
# OR in CloudWatch Logs:
"Container killed by YARN for exceeding memory limits. 
 10.5 GB of 10 GB physical memory used."
```

### Root Cause
```
┌─────────────────────────────────────────────────────────────────────┐
│  WHY DRIVER OOM HAPPENS                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Driver collects metadata about ALL partitions during shuffle:       │
│                                                                      │
│  ┌─────────┐     shuffle      ┌─────────────────────────────┐      │
│  │Executor │────metadata────▶│  DRIVER (limited memory)     │      │
│  │  1      │                  │                              │      │
│  ├─────────┤                  │  Tracks:                     │      │
│  │Executor │────metadata────▶│  - Partition locations        │      │
│  │  2      │                  │  - Map output sizes          │      │
│  ├─────────┤                  │  - Task completion status    │      │
│  │Executor │────metadata────▶│  - Accumulator values        │      │
│  │  ...    │                  │                              │      │
│  ├─────────┤                  │  With 100K+ partitions:      │      │
│  │Executor │────metadata────▶│  metadata > driver heap      │      │
│  │  200    │                  │                              │      │
│  └─────────┘                  └─────────────────────────────┘      │
│                                                                      │
│  Common triggers:                                                    │
│  - df.collect() on large dataset                                     │
│  - Too many partitions (>100K) creating shuffle metadata overhead    │
│  - Large broadcast variables (>1GB)                                  │
│  - toPandas() on non-trivial datasets                               │
│  - countByKey() on high-cardinality columns                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Debugging Steps
```python
# 1. Check Spark UI → Stages tab → look for stages with >50K tasks
# 2. Check driver memory configuration
print(spark.conf.get("spark.driver.memory"))  # Default: 5g for G.1X

# 3. Look for collect() or toPandas() in code
# Search codebase for:
#   .collect(), .toPandas(), .toLocalIterator()
#   countByKey(), countByValue()

# 4. Check number of partitions before shuffle
print(f"Partitions: {df.rdd.getNumPartitions()}")
```

### Fix
```python
# Option 1: Upgrade worker type for more driver memory
# G.1X: 16GB (driver gets ~5GB)
# G.2X: 32GB (driver gets ~10GB)  ← Use this for shuffles
# G.4X: 64GB (driver gets ~20GB)  ← Use for very large metadata

# Option 2: Reduce partition count before shuffle
df = df.coalesce(2000)  # Reduce from 100K to 2000 partitions

# Option 3: Replace collect() with distributed operations
# BAD:
result = df.collect()  # Pulls ALL data to driver
# GOOD:
df.write.parquet("s3://output/")  # Keep distributed

# Option 4: Use approximate functions instead of exact
# BAD:
df.select(countDistinct("user_id")).collect()
# GOOD:
df.select(approx_count_distinct("user_id")).collect()

# Option 5: Increase driver memory via Glue job parameter
# --conf spark.driver.memory=10g
# (Only available with G.2X or higher)
```

### Prevention
```python
# Add partition count guard in all jobs
def safe_repartition(df, target_partitions=2000):
    current = df.rdd.getNumPartitions()
    if current > target_partitions:
        return df.coalesce(target_partitions)
    return df

# Never use collect() in production - enforce via linting
# Add pre-commit hook to reject .collect() calls
```

---

## Issue #2: Executor OOM on Large Joins (Broadcast Threshold Exceeded)

### Severity: P1 | Frequency: Weekly

### Symptoms
```
ExecutorLostFailure (executor X exited caused by one of the running tasks)
Reason: Container killed by YARN for exceeding memory limits.

# OR
java.lang.OutOfMemoryError: GC overhead limit exceeded
```

### Root Cause
```
Spark auto-broadcasts tables < 10MB (default spark.sql.autoBroadcastJoinThreshold).
When a "small" dimension table grows beyond executor memory unexpectedly:

Week 1: dim_products = 5MB   → auto-broadcast works fine
Week 8: dim_products = 2GB   → broadcast attempt OOMs every executor

This happens because:
- No one monitors dimension table growth
- Auto-broadcast threshold wasn't tuned
- Table stats in Glue Catalog are stale
```

### Fix
```python
# Option 1: Disable auto-broadcast for unpredictable tables
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", -1)

# Option 2: Explicitly control broadcast
from pyspark.sql.functions import broadcast

# Only broadcast if you KNOW it's small
small_dim = spark.read.table("dim_country")  # ~200 rows, always small
result = big_fact.join(broadcast(small_dim), "country_code")

# Option 3: Add size guard
def safe_broadcast_join(large_df, small_df, keys, max_broadcast_mb=500):
    """Only broadcast if dimension fits in memory."""
    size_bytes = spark.catalog.getTable(small_df).sizeInBytes
    size_mb = size_bytes / (1024 * 1024)
    
    if size_mb < max_broadcast_mb:
        return large_df.join(broadcast(small_df), keys)
    else:
        logger.warning(f"Table too large for broadcast: {size_mb}MB")
        return large_df.join(small_df, keys)  # Sort-merge join
```

### Prevention
- Monitor dimension table sizes weekly
- Set explicit broadcast hints instead of relying on auto
- Add Glue Data Quality rule: `RowCount "dim_products" < 10000000`

---

## Issue #3: Executor OOM During GroupBy Aggregation (High Cardinality)

### Severity: P1 | Frequency: Weekly at >5TB scale

### Symptoms
```
Container killed by YARN for exceeding memory limits.
Stage X failed 4 times, most recent: ExecutorLostFailure

# Spark UI shows: specific executors failing repeatedly on same partition
```

### Root Cause
```
GroupBy on high-cardinality column + skewed key distribution:

Example: groupBy("merchant_id").agg(collect_list("transaction"))

merchant_id = "amazon"     → 50M transactions (single partition holds this)
merchant_id = "local_shop" → 10 transactions

The executor handling "amazon" partition receives 50M rows → OOM
```

### Fix
```python
# Option 1: Use G.2X or G.4X workers (more memory per executor)
# G.1X: 16GB per worker → executor gets ~10GB
# G.2X: 32GB per worker → executor gets ~22GB
# G.4X: 64GB per worker → executor gets ~48GB

# Option 2: Salt the skewed key
import pyspark.sql.functions as F

# Add salt to distribute hot keys across partitions
salt_buckets = 100
df_salted = df.withColumn("salt", F.expr(f"CAST(RAND() * {salt_buckets} AS INT)"))

# First aggregation: partial aggregation per salt bucket
partial = df_salted.groupBy("merchant_id", "salt").agg(
    F.sum("amount").alias("partial_sum"),
    F.count("*").alias("partial_count")
)

# Second aggregation: combine salt buckets
final = partial.groupBy("merchant_id").agg(
    F.sum("partial_sum").alias("total_amount"),
    F.sum("partial_count").alias("total_count")
)

# Option 3: Enable Adaptive Query Execution (AQE) - Glue 3.0+
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256MB")
```

---

## Issue #4: GC Overhead Limit Exceeded (Prolonged Full GC)

### Severity: P2 | Frequency: Daily on long-running jobs

### Symptoms
```
java.lang.OutOfMemoryError: GC overhead limit exceeded
# Job runs 10x slower than normal before failing
# Spark UI shows: GC Time > 50% of task time
```

### Root Cause
```
┌─────────────────────────────────────────────────────────────────────┐
│  GC DEATH SPIRAL                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  JVM Heap Usage Over Time:                                           │
│                                                                      │
│  100% ┤                              ████████████ (Full GC every    │
│       │                         ████             few seconds,        │
│   80% ┤                    ████                  reclaiming almost   │
│       │               ████                       nothing)            │
│   60% ┤          ████                                                │
│       │     ████                                                     │
│   40% ┤████                                                          │
│       │                                                              │
│   20% ┤     Normal GC pattern                                        │
│       │     (sawtooth)                                               │
│    0% ┼─────────────────────────────────────────────── Time         │
│       0min        15min        30min        45min                    │
│                                                                      │
│  Cause: Too many objects retained in heap (usually strings from     │
│  reading large text files, or UDF closures capturing data)           │
└─────────────────────────────────────────────────────────────────────┘
```

### Fix
```python
# Option 1: Tune GC settings
# In Glue job parameters:
# --conf spark.driver.extraJavaOptions=-XX:+UseG1GC -XX:G1HeapRegionSize=32m
# --conf spark.executor.extraJavaOptions=-XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=35

# Option 2: Increase off-heap memory
spark.conf.set("spark.memory.offHeap.enabled", "true")
spark.conf.set("spark.memory.offHeap.size", "4g")

# Option 3: Reduce object retention
# BAD: Creating strings in UDF
@udf(StringType())
def parse_json(json_str):
    import json
    data = json.loads(json_str)  # Creates many intermediate objects
    return data.get("field")

# GOOD: Use built-in functions (no JVM object overhead)
from pyspark.sql.functions import get_json_object
df = df.withColumn("field", get_json_object("json_col", "$.field"))

# Option 4: Process in smaller batches
# Instead of processing 30 days at once, process day-by-day
for day in date_range:
    process_single_day(day)  # Smaller working set
```

---

## Issue #5: Executor OOM on Skewed Partitions After Shuffle

### Severity: P1 | Frequency: Weekly

### Symptoms
```
# Some tasks complete in 10 seconds, one task runs for 2 hours then OOMs
# Spark UI → Stages → shows 1 task with 100x more data than others

Task Metrics:
  Task 0: Input Size: 50MB,   Duration: 12s
  Task 1: Input Size: 45MB,   Duration: 11s
  Task 2: Input Size: 48GB,   Duration: 7200s → FAILED (OOM)
  Task 3: Input Size: 52MB,   Duration: 13s
```

### Root Cause
```
Hash-based partitioning sends all records with same key to same partition.
If one key has disproportionate data (e.g., null values, default values,
test accounts), that partition exceeds executor memory.

Common skew sources at scale:
- null values in join key (all nulls go to partition 0)
- Default/unknown values ("UNKNOWN", "N/A", "0")
- Power-law distributions (1% of users generate 50% of events)
- Bot/spam traffic (single IP generates millions of events)
```

### Fix
```python
# Fix 1: Filter nulls before join (handle separately)
df_with_keys = df.filter(F.col("join_key").isNotNull())
df_null_keys = df.filter(F.col("join_key").isNull())

# Process non-null normally
result = df_with_keys.join(dim_table, "join_key")
# Handle nulls separately (they can't join anyway)
result_null = df_null_keys.withColumn("dim_value", F.lit("UNKNOWN"))

final = result.unionByName(result_null)

# Fix 2: Adaptive Query Execution (Glue 3.0+)
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")

# Fix 3: Salted join for known skewed keys
skewed_keys = ["amazon", "walmart", "null"]  # Known hot keys

# Split into skewed and non-skewed
df_skewed = df.filter(F.col("merchant_id").isin(skewed_keys))
df_normal = df.filter(~F.col("merchant_id").isin(skewed_keys))

# Salt the skewed portion
df_skewed_salted = df_skewed.withColumn(
    "join_key_salted",
    F.concat(F.col("merchant_id"), F.lit("_"), (F.rand() * 10).cast("int"))
)
# Explode dim table for skewed keys
dim_exploded = dim.filter(F.col("merchant_id").isin(skewed_keys)).crossJoin(
    spark.range(10).withColumnRenamed("id", "salt")
).withColumn(
    "join_key_salted",
    F.concat(F.col("merchant_id"), F.lit("_"), F.col("salt"))
)

# Join separately and union
result_skewed = df_skewed_salted.join(dim_exploded, "join_key_salted")
result_normal = df_normal.join(dim, "merchant_id")
final = result_skewed.unionByName(result_normal, allowMissingColumns=True)
```

---

## Issue #6: Disk Space Exhaustion on Workers (Shuffle Spill)

### Severity: P2 | Frequency: Weekly on large joins

### Symptoms
```
java.io.IOException: No space left on device
# OR
org.apache.spark.SparkException: Job aborted due to stage failure:
  Task X failed: java.io.IOException: Failed to create local dir in /tmp/spark

# Spark UI shows: Shuffle Spill (Disk) in GB
```

### Root Cause
```
When data doesn't fit in executor memory during shuffle, Spark spills to disk.
Glue workers have limited local disk:
  G.1X: 64GB local NVMe
  G.2X: 128GB local NVMe
  G.4X: 256GB local NVMe

Large shuffle (e.g., sort-merge join on 10TB) can exhaust local disk.
```

### Fix
```python
# Option 1: Upgrade worker type for more local disk
# G.1X → G.2X doubles local storage

# Option 2: Reduce shuffle size with pre-filtering
# Filter BEFORE join, not after
df_filtered = df.filter(F.col("date") >= "2024-01-01")  # Reduce volume first
result = df_filtered.join(dim, "key")

# Option 3: Use broadcast join to eliminate shuffle entirely
result = large_df.join(broadcast(small_dim), "key")  # No shuffle!

# Option 4: Enable S3 shuffle plugin (Glue 4.0+)
# Spills to S3 instead of local disk (unlimited space, slightly slower)
spark.conf.set("spark.shuffle.storage.path", "s3://bucket/shuffle-data/")
spark.conf.set("spark.hadoop.fs.s3a.fast.upload", "true")

# Option 5: Increase partitions to reduce per-partition size
spark.conf.set("spark.sql.shuffle.partitions", "4000")  # Default: 200
```

---

## Issue #7: Memory Leak in Long-Running Streaming Glue Jobs

### Severity: P2 | Frequency: Gradual (kills job after hours/days)

### Symptoms
```
# Job starts fine, memory usage gradually increases over hours
# Eventually OOM after 6-12 hours of running
# Heap dump shows accumulation of:
#   - Broadcast variables not unpersisted
#   - Cached DataFrames not released
#   - UDF closure objects
```

### Root Cause
```
Glue Streaming ETL jobs run continuously. Memory leaks that are
invisible in batch (job ends, memory freed) become fatal in streaming:

1. Broadcast variables refreshed but old ones not unpersisted
2. Checkpointing metadata accumulates
3. State store growth in stateful operations
4. Python UDF memory not released (PySpark worker leak)
```

### Fix
```python
# Fix 1: Explicitly unpersist broadcast variables after refresh
old_broadcast = spark.sparkContext.broadcast(old_lookup)
# ... use old_broadcast ...
old_broadcast.unpersist()  # CRITICAL: free memory
new_broadcast = spark.sparkContext.broadcast(new_lookup)

# Fix 2: Configure state store cleanup for streaming
spark.conf.set("spark.sql.streaming.stateStore.maintenanceInterval", "60s")
spark.conf.set("spark.sql.streaming.stateStore.minDeltasForSnapshot", "10")

# Fix 3: Bound state with watermark
df_with_watermark = df \
    .withWatermark("event_time", "1 hour") \
    .groupBy(window("event_time", "10 minutes"), "user_id") \
    .count()
# State older than watermark is automatically cleaned

# Fix 4: Restart streaming job periodically (defensive)
# Schedule Glue Streaming job with maxRetries and use
# external scheduler to restart every 6 hours
```

---

## Issue #8: Python Worker OOM (PySpark UDF Memory Explosion)

### Severity: P2 | Frequency: Common with Python UDFs

### Symptoms
```
Py4JNetworkError: Answer from Java side is empty
# OR
Python worker exited unexpectedly (crashed)
# OR
WARN PythonRunner: Incomplete task

# Job doesn't show JVM OOM - the Python process silently dies
```

### Root Cause
```
┌─────────────────────────────────────────────────────────────────────┐
│  PySpark Memory Architecture                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  JVM Process (Executor)         Python Worker Process               │
│  ┌──────────────────────┐      ┌──────────────────────┐            │
│  │  Spark Executor      │      │  Python UDF          │            │
│  │  (managed memory)    │      │  (UNMANAGED memory)  │            │
│  │                      │◀────▶│                      │            │
│  │  Heap: 10GB          │ pipe │  - No memory limit   │            │
│  │  Off-heap: 2GB       │      │  - No GC control     │            │
│  │                      │      │  - Grows unbounded    │            │
│  │  Monitored by YARN   │      │  NOT monitored       │            │
│  └──────────────────────┘      └──────────────────────┘            │
│                                                                      │
│  If Python worker allocates 20GB (e.g., loading model in UDF),     │
│  YARN kills the container but Spark doesn't know why.               │
└─────────────────────────────────────────────────────────────────────┘
```

### Fix
```python
# Fix 1: Replace Python UDFs with built-in Spark functions
# BAD (Python UDF - data serialized to Python, processed, sent back):
@udf(StringType())
def extract_domain(email):
    return email.split("@")[1] if "@" in email else None

# GOOD (Native Spark - runs in JVM, 10-100x faster, no memory leak):
from pyspark.sql.functions import split, element_at
df = df.withColumn("domain", element_at(split("email", "@"), 2))

# Fix 2: Use Pandas UDFs (vectorized, bounded batches)
from pyspark.sql.functions import pandas_udf
import pandas as pd

@pandas_udf(StringType())
def extract_domain_vectorized(emails: pd.Series) -> pd.Series:
    return emails.str.split("@").str[1]

# Processes in batches of ~10K rows (bounded memory)
df = df.withColumn("domain", extract_domain_vectorized("email"))

# Fix 3: Limit Python worker memory
spark.conf.set("spark.python.worker.memory", "2g")  # Kill if exceeds 2GB
spark.conf.set("spark.python.worker.reuse", "true")  # Reuse workers

# Fix 4: For ML model loading in UDFs
# BAD: Load model inside UDF (loaded per-row!)
@udf
def predict(features):
    model = load_model("s3://...")  # Loaded millions of times!
    return model.predict(features)

# GOOD: Load model once per executor using mapPartitions
def predict_partition(iterator):
    model = load_model("s3://...")  # Load once per partition
    for row in iterator:
        yield Row(prediction=model.predict(row.features))

df.rdd.mapPartitions(predict_partition).toDF()
```

---

## Issue #9: Container Memory Limit Exceeded (YARN Overhead)

### Severity: P2 | Frequency: Common with off-heap operations

### Symptoms
```
Container killed by YARN for exceeding memory limits.
X GB of Y GB physical memory used. Consider boosting
spark.executor.memoryOverhead.
```

### Root Cause
```
YARN monitors TOTAL process memory (heap + off-heap + overhead).
Default overhead = max(384MB, 0.1 * executorMemory)

Operations that use off-heap memory:
- Netty buffers (shuffle data transfer)
- Python worker processes
- JNI native libraries
- Direct ByteBuffers
- Memory-mapped files
```

### Fix
```python
# Increase memory overhead
# For G.2X workers (32GB total, default executor memory ~22GB):
spark.conf.set("spark.executor.memoryOverhead", "4g")  # Default: ~2.2GB

# For Python-heavy workloads (UDFs, pandas):
spark.conf.set("spark.executor.memoryOverhead", "6g")
spark.conf.set("spark.executor.pyspark.memory", "2g")  # Python specifically

# For shuffle-heavy workloads:
spark.conf.set("spark.executor.memoryOverhead", "5g")
spark.conf.set("spark.shuffle.io.maxRetries", "10")
```

---

## Issue #10: Metaspace OOM (Too Many Classes Loaded)

### Severity: P3 | Frequency: Rare but fatal

### Symptoms
```
java.lang.OutOfMemoryError: Metaspace
# Happens after many iterations of Spark SQL query compilation
```

### Root Cause
```
Spark compiles SQL/DataFrame operations into Java bytecode.
Each unique query plan generates new classes. In loops or
dynamic query generation, Metaspace fills up.

Common trigger: Generating 1000+ dynamic queries in a loop
(e.g., processing each partition with a unique filter expression)
```

### Fix
```python
# Option 1: Increase Metaspace
# --conf spark.driver.extraJavaOptions=-XX:MaxMetaspaceSize=1g

# Option 2: Avoid dynamic query generation in loops
# BAD:
for partition_val in partition_values:  # 10K iterations
    spark.sql(f"SELECT * FROM table WHERE part = '{partition_val}'")
    # Each generates a new compiled class!

# GOOD: Single query with IN clause or parameterized
df = spark.read.table("table").filter(
    F.col("part").isin(partition_values)  # Single compiled plan
)
```

---

## Issue #11: S3 Read OOM (Reading Too Many Small Files Simultaneously)

### Severity: P2 | Frequency: Daily with event-driven pipelines

### Symptoms
```
# Job starts, rapidly consumes all memory, OOM within minutes
# S3 metrics show: 500K+ GET requests in first 60 seconds
# Each file is 1-100KB (small files problem)
```

### Root Cause
```
Default Spark behavior: 1 partition per file.
500K small files = 500K partitions = 500K concurrent tasks attempted.
Each task has overhead (~2MB metadata), so 500K × 2MB = 1TB metadata alone.
```

### Fix
```python
# Fix 1: Use Glue's groupFiles option (CRITICAL for small files)
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="table",
    additional_options={
        "groupFiles": "inPartition",     # Group files within each partition
        "groupSize": "134217728"         # 128MB per group (target partition size)
    }
)

# Fix 2: Coalesce before processing
df = spark.read.parquet("s3://bucket/path/")
df = df.coalesce(200)  # Merge 500K partitions into 200

# Fix 3: Enable S3 listing optimization
spark.conf.set("spark.hadoop.mapreduce.input.fileinputformat.list-status.num-threads", "50")
spark.conf.set("spark.sql.files.maxPartitionBytes", "134217728")  # 128MB
spark.conf.set("spark.sql.files.openCostInBytes", "4194304")  # 4MB
```

---

## Issue #12: Executor Memory Fragmentation After Multiple Stages

### Severity: P3 | Frequency: Common in complex pipelines

### Symptoms
```
# Job progressively slows down across stages
# GC time increases with each stage
# Memory usage appears normal but effective available memory decreases
# Tasks that took 10s in Stage 1 take 60s in Stage 5
```

### Root Cause
```
JVM memory fragmentation after many allocate/free cycles.
Long-lived objects (cached data, shuffle buffers) create
"holes" in heap that can't be used for new allocations.
```

### Fix
```python
# Fix 1: Checkpoint between stages (forces GC and clean state)
df_stage1 = process_stage1(raw_df)
df_stage1.write.parquet("s3://staging/checkpoint1/")
df_stage1 = spark.read.parquet("s3://staging/checkpoint1/")  # Fresh read

# Fix 2: Use G1GC with smaller regions
# --conf spark.executor.extraJavaOptions=-XX:+UseG1GC -XX:G1HeapRegionSize=16m

# Fix 3: Split into multiple Glue jobs (each gets fresh memory)
# Job 1: Raw → Cleaned (write to S3)
# Job 2: Cleaned → Aggregated (read from S3, fresh executors)
# Job 3: Aggregated → Output (read from S3, fresh executors)
```

---

## Issue #13: Memory Exhaustion from Unbounded Cache/Persist

### Severity: P2 | Frequency: Common

### Symptoms
```
# First few iterations work, then OOM
# spark.storage.memoryUsed grows monotonically
# Spark UI → Storage tab shows multiple cached DataFrames
```

### Root Cause
```
Developers cache DataFrames for "performance" but never unpersist.
Each cache consumes executor memory permanently.
After 5-6 cached DataFrames, no memory left for computation.
```

### Fix
```python
# BAD: Cache without cleanup
df1 = spark.read.parquet("s3://data1/").cache()
df2 = spark.read.parquet("s3://data2/").cache()
result = df1.join(df2, "key")
df3 = spark.read.parquet("s3://data3/").cache()  # OOM here!

# GOOD: Explicit cache management
df1 = spark.read.parquet("s3://data1/").cache()
df2 = spark.read.parquet("s3://data2/").cache()
result = df1.join(df2, "key")
result.write.parquet("s3://output/")  # Materialize

df1.unpersist()  # Free immediately after use
df2.unpersist()

# Even better: Use checkpoint to S3 instead of cache
df1 = spark.read.parquet("s3://data1/")
df1.write.parquet("s3://temp/df1/")  # Checkpoint to S3
df1 = spark.read.parquet("s3://temp/df1/")  # No memory cost
```

---

## Issue #14: Insufficient Memory for Iceberg Manifest File Processing

### Severity: P2 | Frequency: Growing (more Iceberg adoption)

### Symptoms
```
# OOM when reading large Iceberg tables (>100K data files)
# Driver OOM during planning phase (before any tasks run)
# Error in Iceberg table metadata processing
```

### Root Cause
```
Iceberg tables with many files have large manifest lists.
Table with 100K files → manifest metadata ~500MB loaded into driver.
Tables that haven't been compacted grow manifests unboundedly.
```

### Fix
```python
# Fix 1: Compact table manifests regularly
spark.sql("""
    CALL system.rewrite_manifests('db.table')
""")

# Fix 2: Increase driver memory for Iceberg metadata
# Use G.2X or G.4X for jobs reading large Iceberg tables

# Fix 3: Use partition pruning to reduce manifest scanning
# Read only needed partitions
df = spark.read.format("iceberg") \
    .load("db.table") \
    .filter("date >= '2024-01-01'")  # Prunes manifest scan

# Fix 4: Set manifest target size during writes
spark.conf.set("spark.sql.iceberg.handle-timestamp-without-timezone", "true")
spark.conf.set("spark.sql.catalog.glue.io.manifest.target-size-bytes", "8388608")  # 8MB
```

---

## Issue #15: Memory Pressure from Large Schema Metadata (Wide Tables)

### Severity: P3 | Frequency: Common in ML pipelines

### Symptoms
```
# Slow job startup (5-10 minutes before first task runs)
# High driver memory usage during planning
# Tables with 5000+ columns
```

### Root Cause
```
Tables with thousands of columns (common in feature stores):
- Schema metadata: ~1KB per column × 5000 = 5MB per table read
- Query planning: O(n²) for some operations on wide tables
- Catalyst optimizer struggles with 5000-column plans
- DynamicFrame resolveChoice on 5000 columns = very slow
```

### Fix
```python
# Fix 1: Select only needed columns early
# BAD: Read all 5000 columns then filter
df = spark.read.table("feature_store")  # 5000 columns
df = df.select("user_id", "feature_1", "feature_2")

# GOOD: Pushdown column selection
df = spark.read.table("feature_store").select("user_id", "feature_1", "feature_2")
# Only reads 3 columns from Parquet (column pruning)

# Fix 2: Split wide tables into column families
# Instead of one 5000-column table:
# - user_features_demographic (50 cols)
# - user_features_behavioral (200 cols)
# - user_features_transactional (300 cols)
# Join only what you need

# Fix 3: Disable unnecessary optimizations for wide tables
spark.conf.set("spark.sql.optimizer.maxIterations", "50")  # Default: 100
spark.conf.set("spark.sql.optimizer.inSetConversionThreshold", "10")
```

---

## Summary: Memory Issue Decision Tree

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MEMORY ISSUE DIAGNOSIS                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  OOM Error?                                                          │
│  ├── Driver OOM?                                                     │
│  │   ├── During shuffle? → Issue #1 (reduce partitions)             │
│  │   ├── During broadcast? → Issue #2 (disable auto-broadcast)      │
│  │   ├── During Iceberg planning? → Issue #14 (compact manifests)   │
│  │   └── During collect()? → Issue #1 (remove collect)              │
│  │                                                                   │
│  ├── Executor OOM?                                                   │
│  │   ├── Single task with huge data? → Issue #5 (skew/salting)      │
│  │   ├── All executors at once? → Issue #2 (broadcast too large)    │
│  │   ├── After long runtime? → Issue #7 (memory leak)               │
│  │   ├── With Python UDFs? → Issue #8 (use built-in functions)      │
│  │   └── YARN overhead error? → Issue #9 (increase overhead)        │
│  │                                                                   │
│  ├── Disk full?                                                      │
│  │   └── Shuffle spill exhausted local disk → Issue #6              │
│  │                                                                   │
│  └── Gradual degradation?                                            │
│      ├── GC overhead limit? → Issue #4 (GC tuning)                  │
│      ├── Getting slower per stage? → Issue #12 (checkpoint)         │
│      └── Storage tab shows many caches? → Issue #13 (unpersist)     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
