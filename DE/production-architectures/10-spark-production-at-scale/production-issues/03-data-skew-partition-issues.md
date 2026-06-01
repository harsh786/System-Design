# Category 3: Data Skew & Partition Issues (Issues 21-30)

> Data skew causes 80% of Spark "straggler" problems. A single skewed partition can make a 10-minute job run for 3 hours.

---

## Issue #21: Join Skew - One Key Has Millions of Records

**Frequency**: Very High  
**Severity**: High - massive stragglers (100x slower tasks)  
**Spark Component**: SortMergeJoinExec, ShuffledHashJoinExec

### Symptoms
```
# Spark UI: one task has 500x more input than others
Task 0: Shuffle Read = 50 MB, Duration = 20s
Task 1: Shuffle Read = 45 MB, Duration = 18s
Task 423: Shuffle Read = 85 GB, Duration = 2.5 hours  ← SKEWED KEY
Task 999: Shuffle Read = 55 MB, Duration = 22s

# The join key causing skew: null, "unknown", popular_merchant_id, etc.
```

### Root Cause
- Null keys: both tables have millions of null values that get joined
- Power-law distribution: top 0.1% of keys have 99% of records
- Data quality: "default" or "unknown" placeholder values
- Fan-out join: one key in left maps to millions in right

### Solution
```python
# Solution 1: AQE Skew Join (Spark 3.0+ - preferred)
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256MB")
# AQE automatically splits skewed partitions and replicates the smaller side

# Solution 2: Handle nulls separately (most common skew cause)
df_left_no_null = df_left.filter(F.col("key").isNotNull())
df_left_null = df_left.filter(F.col("key").isNull())

# Join only non-null keys
result = df_left_no_null.join(df_right, "key", "left")

# Handle nulls separately (no join needed - they won't match anyway for inner join)
# For left join, just add null columns
result_full = result.unionByName(
    df_left_null.withColumn("right_col1", F.lit(None))
)

# Solution 3: Salting for known hot keys
hot_keys = spark.sql("""
    SELECT key, COUNT(*) as cnt 
    FROM left_table 
    GROUP BY key 
    HAVING cnt > 1000000
""").select("key").collect()

hot_key_list = [row.key for row in hot_keys]
SALT_BUCKETS = 100

# Salt the large (left) side
df_left_hot = df_left.filter(F.col("key").isin(hot_key_list))
df_left_hot = df_left_hot.withColumn("salted_key", 
    F.concat(F.col("key"), F.lit("_"), (F.rand() * SALT_BUCKETS).cast("int")))

df_left_normal = df_left.filter(~F.col("key").isin(hot_key_list))

# Explode the small (right) side for hot keys
df_right_hot = df_right.filter(F.col("key").isin(hot_key_list))
df_right_exploded = df_right_hot.crossJoin(
    spark.range(SALT_BUCKETS).withColumnRenamed("id", "salt")
).withColumn("salted_key", F.concat(F.col("key"), F.lit("_"), F.col("salt")))

# Join separately and union
result_normal = df_left_normal.join(df_right, "key")
result_hot = df_left_hot.join(df_right_exploded, "salted_key")
final = result_normal.unionByName(result_hot.drop("salted_key", "salt"))
```

---

## Issue #22: GroupBy Skew - Aggregation on Skewed Keys

**Frequency**: High  
**Severity**: Medium-High  
**Spark Component**: HashAggregateExec, ObjectHashAggregateExec

### Symptoms
```
# One reduce task in aggregation stage takes hours
# groupBy("merchant_id").sum("revenue")
# Top merchant has 500M transactions, average merchant has 1000
```

### Root Cause
- Power-law distribution in groupBy keys
- Single partition must process ALL records for a hot key
- Hash aggregate can't split work within a key

### Solution
```python
# Two-phase aggregation (manual partial + final)
SALT_FACTOR = 50

# Phase 1: Partial aggregate with salt (distributes hot key across 50 tasks)
df_partial = (
    df.withColumn("salt", (F.rand() * SALT_FACTOR).cast("int"))
    .groupBy("merchant_id", "salt")
    .agg(
        F.sum("revenue").alias("partial_revenue"),
        F.count("*").alias("partial_count"),
        F.max("transaction_time").alias("partial_max_time")
    )
)

# Phase 2: Final aggregate (now each key has at most SALT_FACTOR rows)
result = (
    df_partial.groupBy("merchant_id")
    .agg(
        F.sum("partial_revenue").alias("total_revenue"),
        F.sum("partial_count").alias("total_count"),
        F.max("partial_max_time").alias("max_time")
    )
)

# For functions that support partial aggregation natively:
# SUM, COUNT, MIN, MAX → easy to split
# AVG → use SUM/COUNT
# PERCENTILE, MEDIAN → need approximate functions
# approx_percentile handles skew better:
result = df.groupBy("merchant_id").agg(
    F.approx_percentile("revenue", [0.5, 0.95, 0.99]).alias("revenue_percentiles")
)
```

---

## Issue #23: Write Skew - Uneven Output Partitions

**Frequency**: High  
**Severity**: Medium - long tail tasks, uneven file sizes  
**Spark Component**: FileFormatWriter, DataSource V2

### Symptoms
```
# Writing partitioned data:
# /output/date=2024-01-01/ → 1 file, 50GB (hot partition)
# /output/date=2024-01-02/ → 1 file, 100MB
# One write task takes 2 hours, rest take 2 minutes
# Downstream reads of hot partition are slow
```

### Root Cause
- Natural data distribution is skewed (more recent data, popular categories)
- Writing with partitionBy on skewed column
- No repartitioning before write
- Dynamic partition overwrite has to rewrite massive partitions

### Solution
```python
# 1. Repartition before write to balance file sizes
target_file_size_mb = 256
total_size_mb = df.count() * avg_row_size_bytes / 1024 / 1024
num_files = max(1, int(total_size_mb / target_file_size_mb))

df.repartition(num_files).write.parquet("s3://output/")

# 2. Use maxRecordsPerFile to cap file sizes
df.write.option("maxRecordsPerFile", 5000000).partitionBy("date").parquet("s3://output/")

# 3. For partitioned writes, repartition within each partition
df.repartition(200, "date").write.partitionBy("date").parquet("s3://output/")
# Each date partition gets balanced across ~200/num_dates files

# 4. Use Iceberg's automatic file sizing
df.writeTo("catalog.db.table").option("target-file-size-bytes", str(256 * 1024 * 1024)).append()

# 5. Sort within partitions for better compression and read performance
df.sortWithinPartitions("date", "user_id").write.partitionBy("date").parquet("s3://output/")
```

---

## Issue #24: Partition Explosion (Too Many Small Partitions)

**Frequency**: High  
**Severity**: Medium - scheduler overhead, small files  
**Spark Component**: DAGScheduler, TaskScheduler

### Symptoms
```
# 1 million partitions in shuffle stage
# Tasks completing in < 100ms each (scheduling overhead > compute)
# Driver becoming slow managing task metadata
# Output has 1M tiny files (KB each)
# Spark UI: "Skipped stages" everywhere (empty partitions)
```

### Root Cause
- Over-partitioning: `spark.sql.shuffle.partitions` set too high
- Reading from highly partitioned source (e.g., hourly Kafka offsets × partitions)
- Multiple joins creating partition multiplication
- repartition(N) with N >> data size

### Solution
```python
# 1. AQE coalesces empty/small partitions automatically
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.minPartitionSize", "64MB")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "256MB")

# 2. Coalesce before write
df = df.coalesce(100)  # Reduce from 10000 to 100 without shuffle
df.write.parquet("s3://output/")

# 3. Set reasonable initial partition count
# Formula: max(200, total_data_size_MB / 256)
data_size_mb = 50000  # 50GB
partitions = max(200, data_size_mb // 256)  # = 195 → use 200

# 4. For reads: limit input partitions
df = spark.read.option("maxPartitionBytes", "256MB").parquet("s3://input/")
# This merges small input files into larger partitions

# 5. Avoid partition explosion in multi-level joins
# Instead of:
result = a.join(b, "k1").join(c, "k2").join(d, "k3")  # Each join adds partitions

# Coalesce between joins:
ab = a.join(b, "k1").coalesce(500)
abc = ab.join(c, "k2").coalesce(500)
result = abc.join(d, "k3")
```

---

## Issue #25: Partition Pruning Not Working (Full Table Scan)

**Frequency**: High  
**Severity**: High - reading TB instead of GB  
**Spark Component**: Catalyst Optimizer, PartitionPruning

### Symptoms
```
# Query filters on partition column but Spark reads ALL partitions
# From plan:
FileScan parquet [*] Batched: true, Pushed Filters: [], Partition Filters: []
# Expected: PartitionFilters: [date = 2024-01-01]
# Reading 365 days instead of 1 day (365x more I/O)
```

### Root Cause
- Filter uses function on partition column: `WHERE year(date) = 2024`
- Type mismatch: partition is STRING but filter uses INT
- Filter applied AFTER join (pushed past exchange)
- Subquery filter not pushed down
- Column statistics not available for DPP

### Solution
```python
# 1. Filter directly on partition column (no functions)
# BAD: Spark can't prune
df.filter(F.year("date_col") == 2024)  # Function wraps partition column!

# GOOD: Direct comparison on partition column
df.filter(F.col("date") == "2024-01-01")
df.filter(F.col("date").between("2024-01-01", "2024-01-31"))

# 2. Ensure type matches
# BAD: partition is string "20240101" but filter uses date type
df.filter(F.col("date_partition") == F.to_date(F.lit("2024-01-01")))

# GOOD: Compare same types
df.filter(F.col("date_partition") == "20240101")

# 3. Enable Dynamic Partition Pruning (DPP) for join-based filters
spark.conf.set("spark.sql.optimizer.dynamicPartitionPruning.enabled", "true")
spark.conf.set("spark.sql.optimizer.dynamicPartitionPruning.useStats", "true")
spark.conf.set("spark.sql.optimizer.dynamicPartitionPruning.fallbackFilterRatio", "0.5")

# DPP example: filter derived from small dimension table
# SELECT * FROM fact_table f JOIN dim_date d ON f.date = d.date WHERE d.quarter = 'Q1'
# DPP will first scan dim_date, get Q1 dates, then prune fact_table partitions

# 4. Verify partition pruning is working
df.filter(F.col("date") == "2024-01-01").explain(mode="formatted")
# Check for: PartitionFilters: [isnotnull(date), (date = 2024-01-01)]

# 5. For Iceberg: use hidden partitioning
# Iceberg automatically handles partition transforms
# No need to worry about function-on-partition issues
# CREATE TABLE t (event_time TIMESTAMP, ...) PARTITIONED BY (days(event_time))
```

---

## Issue #26: Dynamic Partition Pruning (DPP) Not Triggering

**Frequency**: Medium  
**Severity**: High - missing optimization  
**Spark Component**: DynamicPruningExpression, Catalyst

### Symptoms
```
# Star schema query (fact + dimension):
SELECT f.* FROM fact f JOIN dim_date d ON f.date_key = d.date_key WHERE d.year = 2024
# Expected: Only scan fact partitions for 2024
# Actual: Full fact table scan (5TB instead of 500GB)
```

### Root Cause
- DPP disabled in configuration
- Dimension table too large (exceeds `reusedBroadcastExchangeThreshold`)
- Join type doesn't support DPP (only inner/left-semi for fact side)
- Partition column in fact table not matching join key
- Statistics missing for dimension table

### Solution
```python
# 1. Enable DPP (usually on by default in Spark 3.x)
spark.conf.set("spark.sql.optimizer.dynamicPartitionPruning.enabled", "true")
spark.conf.set("spark.sql.optimizer.dynamicPartitionPruning.reuseBroadcastOnly", "false")

# 2. Ensure dimension table fits in broadcast
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "100MB")
# If dim is 50MB, it can be broadcast → enables DPP subquery

# 3. Collect statistics on dimension table
spark.sql("ANALYZE TABLE dim_date COMPUTE STATISTICS")
spark.sql("ANALYZE TABLE dim_date COMPUTE STATISTICS FOR COLUMNS date_key, year")

# 4. Verify DPP in query plan
df.explain(mode="formatted")
# Look for: DynamicPruningExpression in PartitionFilters

# 5. Structure query to help DPP
# GOOD: Direct join on partition key
fact.join(dim.filter("year = 2024"), fact.date_key == dim.date_key)

# 6. For non-broadcast dims, allow subquery DPP
spark.conf.set("spark.sql.optimizer.dynamicPartitionPruning.reuseBroadcastOnly", "false")
# This enables DPP even when dimension is too large to broadcast
# (creates a subquery filter instead)
```

---

## Issue #27: Repartition vs Coalesce Confusion

**Frequency**: Very High (code review finding)  
**Severity**: Medium - unnecessary shuffles or OOM  
**Spark Component**: ShuffleExchangeExec, CoalesceExec

### Symptoms
```
# Using repartition(N) when coalesce(N) would avoid shuffle:
Exchange hashpartitioning(none, 100)  ← Full shuffle for no reason!
# 2TB of data shuffled just to reduce partition count

# OR using coalesce when repartition is needed:
# Coalesce(100) from 10000 → some partitions get 100 original partitions merged
# Result: massively uneven partition sizes (one partition has 50GB, another 500MB)
```

### Root Cause
- `coalesce(N)` reduces partitions WITHOUT shuffle (merges adjacent partitions)
- `repartition(N)` does FULL SHUFFLE (redistributes data evenly)
- Developers default to `repartition` for everything

### Decision Matrix
```python
# RULE: Use coalesce when REDUCING partition count
# RULE: Use repartition when INCREASING or need EVEN distribution

# Scenario 1: Reduce 10000 → 100 partitions for file write
df.coalesce(100).write.parquet(...)  # ✅ No shuffle, just merge

# Scenario 2: Need even distribution for downstream join
df.repartition(100, "key").join(...)  # ✅ Shuffle needed for co-location

# Scenario 3: Input has 100 partitions but they're skewed
# coalesce won't help (it just merges, doesn't rebalance)
df.repartition(100)  # ✅ Full shuffle to rebalance

# Scenario 4: Reduce partitions but data is already skewed
# coalesce makes skew WORSE (merges small into large)
df.repartition(100)  # ✅ Redistribute evenly

# Scenario 5: Reduce for write AND need specific partitioning
df.repartition(100, "date").write.partitionBy("date").parquet(...)  # ✅

# NEVER do this:
df.coalesce(1000)  # coalesce can only REDUCE, not increase!
# This silently does nothing if current partitions < 1000
```

---

## Issue #28: Iceberg/Delta Hidden Partitioning Not Leveraged

**Frequency**: Medium  
**Severity**: High - reading 10-100x more data  
**Spark Component**: Iceberg/Delta Source, Partition Pruning

### Symptoms
```
# Table partitioned by days(event_time) in Iceberg
# Query: WHERE event_time > '2024-01-01 00:00:00'
# But Spark still scans all partitions because it doesn't understand the transform
# OR old Hive-style partition columns not aligned with query predicates
```

### Root Cause
- Iceberg hidden partitioning requires partition spec awareness
- Old partition layout (e.g., year/month/day columns) vs new timestamp filter
- Partition evolution changed layout but old files still use old spec
- Filter not pushed to scan level

### Solution
```python
# 1. For Iceberg: use proper filter syntax
# Iceberg handles partition transforms automatically:
# Table: PARTITIONED BY (days(event_time))
# This just works:
spark.read.format("iceberg").load("catalog.db.events") \
    .filter("event_time >= '2024-01-01' AND event_time < '2024-02-01'")
# Iceberg translates to: partition_days >= 19723 AND partition_days < 19754

# 2. Verify with Iceberg metrics:
spark.sql("SELECT * FROM catalog.db.events.files").show()
# Check: only files from target partitions are listed

# 3. For Hive-style partitioning, align filters with partition columns
# Table partitioned by: year, month, day (STRING columns)
# BAD: Spark can't derive partition values from timestamp comparison
df.filter(F.col("event_timestamp") > "2024-01-01")  # No pruning!

# GOOD: Filter on actual partition columns
df.filter((F.col("year") == "2024") & (F.col("month") == "01"))

# 4. After partition evolution, run rewrite to migrate old data
spark.sql("""
    CALL catalog.system.rewrite_data_files(
        table => 'db.events',
        where => 'event_time < current_date() - INTERVAL 90 DAYS'
    )
""")

# 5. Use EXPLAIN to verify partition pruning
spark.sql("EXPLAIN SELECT * FROM events WHERE event_time = '2024-01-15'").show(truncate=False)
```

---

## Issue #29: Uneven Input Splits from Object Storage

**Frequency**: Medium-High  
**Severity**: Medium  
**Spark Component**: FilePartition, InMemoryFileIndex

### Symptoms
```
# Input partitions wildly uneven:
# Partition 0: 5 files, 2.5GB total
# Partition 1: 1 file, 50MB
# Partition 2: 1 file, 5GB (one huge file, can't split mid-row for JSON)
# Tasks have 100x different durations based on input size
```

### Root Cause
- S3/GCS files have widely varying sizes (1KB to 10GB)
- Non-splittable formats (gzip JSON, gzip CSV) create 1 task per file
- `maxPartitionBytes` not tuned for your file size distribution
- Small files problem: 100K tiny files = 100K tasks with scheduling overhead

### Solution
```python
# 1. Control input partition sizing
spark.conf.set("spark.sql.files.maxPartitionBytes", "256MB")  # Max per partition
spark.conf.set("spark.sql.files.openCostInBytes", "4MB")      # Penalty for opening file

# 2. Use splittable formats (Parquet, ORC, uncompressed CSV/JSON)
# Parquet files are splittable at row-group boundaries (128MB default)
# gzip files are NOT splittable → one task per file

# 3. Merge small files on read
spark.conf.set("spark.sql.files.minPartitionNum", "1")  # Allow merging

# 4. For unsplittable files, repartition immediately after read
df = spark.read.json("s3://bucket/gzipped/*.json.gz")  # 10000 small files = 10000 tasks
df = df.repartition(200)  # Redistribute evenly, then proceed

# 5. Pre-process: compact small files into optimal sizes (offline job)
# Target: 256MB-1GB Parquet files with snappy compression
small_files = spark.read.parquet("s3://input/raw/")
small_files.repartition(100).write.parquet("s3://input/compacted/")

# 6. Use Iceberg's file scan planning
# Iceberg groups small files into splits automatically
# Configure: read.split.target-size = 268435456 (256MB)
```

---

## Issue #30: Data Locality Ignored in Cloud Deployments

**Frequency**: Medium  
**Severity**: Low-Medium (latency impact)  
**Spark Component**: TaskSchedulerImpl, TaskSetManager

### Symptoms
```
# All tasks showing locality level: ANY
# No PROCESS_LOCAL or NODE_LOCAL tasks
# On-prem: tasks scheduled on nodes far from HDFS blocks
# Cloud: irrelevant (S3/GCS has no locality) but wait settings waste time
```

### Root Cause
- Cloud storage (S3/GCS/ADLS) has no data locality concept
- Spark still waits for locality timeout before scheduling remotely
- Old Hadoop-era settings wasting time waiting for locality that won't come
- Compute and storage fully disaggregated

### Solution
```python
# For cloud deployments (S3/GCS/ADLS): disable locality wait entirely
spark.conf.set("spark.locality.wait", "0s")  # Don't wait for locality
spark.conf.set("spark.locality.wait.node", "0s")
spark.conf.set("spark.locality.wait.rack", "0s")
spark.conf.set("spark.locality.wait.process", "0s")

# This eliminates unnecessary delay at task scheduling
# Tasks start immediately on any available executor

# For on-prem HDFS: tune locality waits
spark.conf.set("spark.locality.wait", "5s")       # Wait 5s for node-local
spark.conf.set("spark.locality.wait.node", "3s")   # Then try rack-local
spark.conf.set("spark.locality.wait.rack", "2s")   # Then any

# For hybrid (cache layer like Alluxio):
spark.conf.set("spark.locality.wait", "3s")  # Some benefit from caching layer
# Alluxio provides locality by caching S3 data on compute nodes

# Verify locality in Spark UI:
# Stages → Task tab → "Locality Level" column
# PROCESS_LOCAL: data in same executor (cached)
# NODE_LOCAL: data on same node (HDFS/Alluxio)
# RACK_LOCAL: same rack
# ANY: no locality (all S3 reads)
```

---

## Summary: Data Skew & Partition Decision Tree

```
Performance problem suspected
├── Is one task much slower than others?
│   ├── Yes, during JOIN → Issue #21 (join skew)
│   ├── Yes, during GROUP BY → Issue #22 (aggregation skew)
│   └── Yes, during WRITE → Issue #23 (write skew)
├── Are there too many tasks/partitions?
│   ├── Millions of tiny tasks → Issue #24 (partition explosion)
│   ├── Input files have varying sizes → Issue #29 (uneven splits)
│   └── Using repartition incorrectly → Issue #27 (repartition vs coalesce)
├── Reading too much data?
│   ├── Partition filter not applied → Issue #25 (pruning broken)
│   ├── DPP not triggering → Issue #26 (dynamic pruning)
│   └── Iceberg partition not leveraged → Issue #28 (hidden partitioning)
└── Scheduling delays?
    └── Tasks waiting for locality → Issue #30 (locality in cloud)
```
