# Category 1: Memory & OOM Issues (Issues 1-10)

> The most common production killers. OOM accounts for ~40% of all Spark job failures at scale.

---

## Issue #1: Executor OOM During Large Shuffle

**Frequency**: Very High (daily at 10TB+ scale)  
**Severity**: Critical - job failure  
**Spark Component**: Unified Memory Manager, Shuffle Reader

### Symptoms
```
java.lang.OutOfMemoryError: Java heap space
  at org.apache.spark.shuffle.sort.ShuffleExternalSorter
ExecutorLostFailure (executor 5 exited caused by one of the running tasks)
Reason: Container killed by YARN for exceeding memory limits. 16.2 GB of 16 GB physical memory used.
```

### Root Cause
- Shuffle data exceeds execution memory fraction
- Too few partitions → each partition too large to fit in memory
- Memory overhead not accounted for (off-heap, native libs, container overhead)

### Solution
```python
# 1. Increase partitions to reduce per-partition memory pressure
spark.conf.set("spark.sql.shuffle.partitions", "2000")  # Default 200 is too low

# 2. Increase memory overhead for container
# spark.executor.memoryOverhead = max(384MB, 0.10 * spark.executor.memory)
spark.conf.set("spark.executor.memory", "16g")
spark.conf.set("spark.executor.memoryOverhead", "4g")  # 20% of executor memory

# 3. Enable off-heap memory for large shuffles
spark.conf.set("spark.memory.offHeap.enabled", "true")
spark.conf.set("spark.memory.offHeap.size", "8g")

# 4. Let AQE handle partition sizing dynamically
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")
```

### Prevention Checklist
- [ ] Set `spark.sql.shuffle.partitions` = total_shuffle_data / 128MB
- [ ] Always set memoryOverhead to at least 15-20% of executor memory
- [ ] Monitor `jvm.heap.used` / `jvm.heap.max` ratio in Prometheus
- [ ] Alert when ratio > 0.85 sustained for 5 minutes

---

## Issue #2: Driver OOM from collect() or toPandas()

**Frequency**: High (especially from notebook users)  
**Severity**: Critical - kills entire application  
**Spark Component**: Driver, ResultTask

### Symptoms
```
java.lang.OutOfMemoryError: Java heap space
  at org.apache.spark.sql.Dataset.collectFromPlan
Driver stacktrace: ... at df.collect()
```

### Root Cause
- `collect()` brings entire DataFrame to driver memory
- `toPandas()` materializes entire dataset in driver JVM + Python
- Large broadcast variables exceeding driver memory
- Accumulator results from millions of tasks

### Solution
```python
# BAD: Never collect large datasets
# results = df.collect()  # 100M rows → driver OOM

# GOOD: Use take() or limit()
sample = df.take(1000)  # Only fetch 1000 rows
sample_df = df.limit(1000).toPandas()

# GOOD: Write to storage, read separately
df.write.format("parquet").save("s3://bucket/output/")

# GOOD: Use show() for inspection
df.show(20, truncate=False)

# For aggregations, aggregate first then collect
summary = df.groupBy("category").agg(
    F.count("*").alias("cnt"),
    F.sum("amount").alias("total")
)  # Small result set, safe to collect
summary.collect()

# Increase driver memory if truly needed
# spark.driver.memory=8g
# spark.driver.maxResultSize=4g (default 1g)
```

### Prevention Checklist
- [ ] Ban `collect()` in production code via linting rules
- [ ] Set `spark.driver.maxResultSize=2g` as safety net
- [ ] Use `df.count()` before any collect to verify size
- [ ] Replace `toPandas()` with `spark.pandas` API (Pandas on Spark)

---

## Issue #3: Broadcast Join OOM

**Frequency**: Medium-High  
**Severity**: Critical - executor or driver OOM  
**Spark Component**: BroadcastExchangeExec, Driver

### Symptoms
```
org.apache.spark.SparkException: Cannot broadcast the table that is larger than 8GB
# OR
java.lang.OutOfMemoryError: Not enough memory to build and broadcast the table
# OR driver hangs during broadcast
```

### Root Cause
- Table stats are stale → Spark thinks table is small but it grew
- `spark.sql.autoBroadcastJoinThreshold` set too high
- Broadcast of a post-filter table that's still large
- Compressed size is small but decompressed is huge

### Solution
```python
# 1. Disable auto-broadcast for this query
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")  # Disable

# 2. Or set a safe threshold (default 10MB, production: 50-100MB max)
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "50MB")

# 3. Force sort-merge join when unsure
df_large.join(df_medium.hint("merge"), "key")

# 4. Manually broadcast only verified small tables
from pyspark.sql.functions import broadcast
small_df = spark.read.table("dim_country")  # Known: 200 rows
result = large_df.join(broadcast(small_df), "country_code")

# 5. Increase driver memory for legitimate large broadcasts
# spark.driver.memory=16g
# spark.driver.maxResultSize=8g

# 6. Use AQE to dynamically choose join strategy at runtime
spark.conf.set("spark.sql.adaptive.enabled", "true")
# AQE will convert sort-merge to broadcast if runtime stats show table is small
```

### Prevention Checklist
- [ ] Run `ANALYZE TABLE dim_table COMPUTE STATISTICS` regularly
- [ ] Set autoBroadcastJoinThreshold conservatively (50MB)
- [ ] Monitor broadcast sizes in Spark UI → SQL → Exchange nodes
- [ ] Alert if broadcast exceeds 500MB

---

## Issue #4: GC Overhead Limit Exceeded

**Frequency**: Medium  
**Severity**: High - extreme slowdown or failure  
**Spark Component**: JVM Garbage Collector

### Symptoms
```
java.lang.OutOfMemoryError: GC overhead limit exceeded
# OR from Spark UI:
Task 234 GC time: 45s (out of 60s task time = 75% GC!)
# OR executor heartbeat timeout
```

### Root Cause
- Too many small objects in heap (e.g., Row objects, String objects)
- Cache pressure: cached RDDs + execution memory competing
- Insufficient heap for the working set
- Old gen fills up → frequent full GC → stop-the-world pauses

### Solution
```python
# 1. Switch to G1GC (recommended for Spark)
# In spark-defaults.conf or submit:
spark.conf.set("spark.executor.extraJavaOptions",
    "-XX:+UseG1GC -XX:G1HeapRegionSize=16m "
    "-XX:InitiatingHeapOccupancyPercent=35 "
    "-XX:ConcGCThreads=4 "
    "-XX:+ParallelRefProcEnabled"
)

# 2. Reduce cached data pressure
spark.conf.set("spark.memory.storageFraction", "0.3")  # Default 0.5, give more to execution

# 3. Use Kryo serialization (smaller objects)
spark.conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
spark.conf.set("spark.kryoserializer.buffer.max", "1024m")

# 4. Reduce object creation with columnar operations
# BAD: UDF creating many objects
@udf(StringType())
def bad_udf(row):
    return str(row.field1) + "_" + str(row.field2)  # Creates intermediate strings

# GOOD: Use built-in functions (Tungsten optimized, no GC pressure)
result = df.withColumn("combined", F.concat_ws("_", "field1", "field2"))

# 5. Increase executor memory or reduce parallelism per executor
spark.conf.set("spark.executor.cores", "4")  # Fewer cores = fewer concurrent tasks = less memory pressure
```

### Prevention Checklist
- [ ] Always use G1GC for executors > 8GB heap
- [ ] Monitor GC time ratio (alert if > 10% of task time)
- [ ] Prefer built-in functions over UDFs
- [ ] Set `-verbose:gc -Xloggc:/tmp/gc.log` for debugging

---

## Issue #5: Container Killed by YARN/K8s (Memory Exceeded)

**Frequency**: High  
**Severity**: Critical - silent task failure  
**Spark Component**: External (YARN/Kubernetes)

### Symptoms
```
# YARN:
Container killed by YARN for exceeding memory limits. 
18.5 GB of 16.0 GB physical memory used.

# Kubernetes:
Pod OOMKilled: memory limit exceeded
Exit code: 137 (SIGKILL)
```

### Root Cause
- Off-heap memory not accounted: native libs, Python (PySpark), netty buffers
- Memory overhead too low (default is only 10% or 384MB)
- PySpark: Python worker memory is OUTSIDE JVM heap
- Arrow/Pandas UDF memory is not managed by Spark memory manager

### Solution
```python
# 1. Account for total container memory properly
# Total container = spark.executor.memory + spark.executor.memoryOverhead
spark.conf.set("spark.executor.memory", "12g")         # JVM heap
spark.conf.set("spark.executor.memoryOverhead", "4g")  # Off-heap (native + Python + overhead)
# Total: 16g container

# 2. For PySpark with Pandas UDFs, increase overhead significantly
spark.conf.set("spark.executor.memoryOverhead", "6g")  # 30-40% for heavy Python/Arrow
spark.conf.set("spark.executor.pyspark.memory", "4g")  # Dedicated Python memory pool

# 3. For Kubernetes, set resource limits correctly
# pod memory request = spark.executor.memory + spark.executor.memoryOverhead
# spark.kubernetes.executor.request.memory is auto-calculated

# 4. Monitor actual RSS (Resident Set Size)
# In K8s: kubectl top pods | grep spark-executor
# In YARN: check container physical memory via RM UI

# 5. Limit concurrent tasks to reduce peak memory
spark.conf.set("spark.executor.cores", "3")  # Instead of 5, fewer concurrent tasks
spark.conf.set("spark.task.cpus", "1")
```

### Key Formula
```
YARN container memory = spark.executor.memory + spark.executor.memoryOverhead
K8s pod memory limit = spark.executor.memory + spark.executor.memoryOverhead + buffer

Rule of thumb for PySpark:
  memoryOverhead = max(2GB, 0.25 * executor.memory) for Python-heavy workloads
  memoryOverhead = max(1GB, 0.15 * executor.memory) for pure Spark SQL
```

---

## Issue #6: Executor Lost Due to Memory During Aggregation

**Frequency**: Medium-High  
**Severity**: High  
**Spark Component**: HashAggregateExec, TungstenAggregationIterator

### Symptoms
```
WARN TaskSetManager: Lost task 15.0 in stage 3.0 (TID 89) 
  executor 12 exited caused by one of the running tasks
Reason: Container killed for exceeding memory limits
# Happening specifically during groupBy/agg operations
```

### Root Cause
- High-cardinality groupBy creates massive hash maps in memory
- `groupBy("user_id")` with 500M distinct users
- Hash aggregate falls back to sort aggregate but still OOMs
- Multiple aggregations compound memory usage

### Solution
```python
# 1. Force sort-based aggregation (spills to disk instead of OOM)
spark.conf.set("spark.sql.execution.useObjectHashAggregateExec", "false")

# 2. Reduce hash aggregate final threshold
spark.conf.set("spark.sql.objectHashAggregate.sortBased.fallbackThreshold", "128")

# 3. Increase partitions so each partition has fewer groups
spark.conf.set("spark.sql.shuffle.partitions", "4000")

# 4. Two-phase aggregation for high cardinality
# Instead of:
result = df.groupBy("user_id").agg(F.sum("amount"))

# Do partial aggregation with salt:
from pyspark.sql import functions as F

# Phase 1: Partial aggregate with random salt
df_salted = df.withColumn("salt", F.floor(F.rand() * 10))
partial = df_salted.groupBy("user_id", "salt").agg(
    F.sum("amount").alias("partial_sum"),
    F.count("*").alias("partial_count")
)

# Phase 2: Final aggregate (much smaller dataset now)
result = partial.groupBy("user_id").agg(
    F.sum("partial_sum").alias("total_amount"),
    F.sum("partial_count").alias("total_count")
)

# 5. Use approximate functions for analytics
approx_count = df.select(F.approx_count_distinct("user_id", rsd=0.05))
```

---

## Issue #7: Spill to Disk Causing Extreme Slowdown

**Frequency**: Medium  
**Severity**: Medium-High (10-100x slower)  
**Spark Component**: ExternalSorter, UnsafeExternalSorter

### Symptoms
```
# From Spark UI Stage details:
Shuffle Spill (Memory): 50 GB
Shuffle Spill (Disk): 200 GB
# Task taking 30 minutes instead of 30 seconds
# Disk I/O at 100% on executor nodes
```

### Root Cause
- Execution memory insufficient for sort/join/aggregation
- Storage memory (cached RDDs) hogging unified memory pool
- Single partition too large for available execution memory
- Insufficient local disk space for spill files

### Solution
```python
# 1. Give more memory to execution vs storage
spark.conf.set("spark.memory.storageFraction", "0.2")  # Cache less, execute more

# 2. Increase partitions to reduce per-partition size
spark.conf.set("spark.sql.shuffle.partitions", "4000")

# 3. Use off-heap to expand execution capacity
spark.conf.set("spark.memory.offHeap.enabled", "true")
spark.conf.set("spark.memory.offHeap.size", "8g")

# 4. Unpersist cached data before heavy operations
df_cached.unpersist()
heavy_join_result = df1.join(df2, "key")

# 5. Ensure fast local disks for spill (NVMe SSDs)
# In spark-defaults.conf:
# spark.local.dir=/mnt/nvme1/spark,/mnt/nvme2/spark

# 6. Monitor spill ratio
# Alert if: Spill(Disk) / Spill(Memory) > 2x consistently
# This means data is being written to disk multiple times (re-spill)

# 7. Use compression for spill
spark.conf.set("spark.shuffle.spill.compress", "true")
spark.conf.set("spark.io.compression.codec", "zstd")  # Better ratio than lz4
```

---

## Issue #8: Python Worker OOM (PySpark UDFs)

**Frequency**: Medium-High  
**Severity**: High  
**Spark Component**: PythonRunner, Arrow

### Symptoms
```
Caused by: org.apache.spark.api.python.PythonException: 
  MemoryError: Unable to allocate 4.2 GiB for an array
# OR
python worker exited unexpectedly (crashed)
# OR
Connection to Python worker lost
```

### Root Cause
- Python UDFs run in separate Python processes OUTSIDE JVM memory management
- Pandas UDFs load entire partition into Python memory as Arrow batches
- Memory-intensive Python libraries (numpy, pandas) allocating large arrays
- No backpressure between JVM and Python worker

### Solution
```python
# 1. Limit Arrow batch size sent to Python
spark.conf.set("spark.sql.execution.arrow.maxRecordsPerBatch", "5000")  # Default 10000

# 2. Allocate dedicated Python memory
spark.conf.set("spark.executor.pyspark.memory", "4g")

# 3. Repartition before Pandas UDF to limit partition size
df = df.repartition(2000)  # Smaller partitions = less memory per Python call

@F.pandas_udf("double")
def safe_udf(series: pd.Series) -> pd.Series:
    # Process in chunks if needed
    return series.apply(lambda x: x * 2)

# 4. Prefer vectorized (Arrow) UDFs over row-at-a-time
# Arrow UDF: ~10x faster, BUT uses more memory per batch
# Control batch size to balance speed vs memory

# 5. Use mapInPandas for complex operations with memory control
def process_partition(iterator):
    for batch_df in iterator:
        # Process small batches
        yield batch_df.assign(result=batch_df['value'] * 2)

result = df.mapInPandas(process_partition, schema=output_schema)

# 6. Avoid large objects in UDF closures
# BAD: Large model loaded per task
model = load_large_model()  # 2GB model in closure

# GOOD: Load model once per partition
def predict_partition(iterator):
    model = load_large_model()  # Load once
    for batch in iterator:
        yield model.predict(batch)
```

---

## Issue #9: Memory Leak in Long-Running Streaming Jobs

**Frequency**: Medium  
**Severity**: High (gradual degradation → crash)  
**Spark Component**: StateStore, IncrementalExecution

### Symptoms
```
# Over hours/days:
Executor memory slowly climbing from 60% → 70% → 80% → 95% → OOM
# State store memory growing unbounded
# Old objects not being GC'd
# Eventually: executor heartbeat timeout → executor lost
```

### Root Cause
- State not being expired (no watermark or TTL configured)
- Accumulators/broadcast variables not cleaned up across batches
- IncrementalExecution plan cache growing without bounds
- Class loader leaks from repeated UDF/JAR loading
- RocksDB state backend not compacting

### Solution
```python
# 1. ALWAYS set watermarks for stateful operations
df_with_watermark = df.withWatermark("event_time", "1 hour")
# This tells Spark to drop state older than watermark

# 2. Use state TTL for mapGroupsWithState
from pyspark.sql.streaming import GroupStateTimeout

def update_state(key, values, state):
    if state.hasTimedOut:
        state.remove()  # Clean up expired state
        return []
    state.setTimeoutDuration("30 minutes")  # Auto-expire after 30 min
    # ... process values ...

# 3. Monitor state store size
# Check streaming query progress:
query.lastProgress["stateOperators"][0]["numRowsTotal"]
# Alert if growing > 10% per hour without corresponding input growth

# 4. Configure RocksDB compaction
spark.conf.set("spark.sql.streaming.stateStore.providerClass",
    "org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider")
spark.conf.set("spark.sql.streaming.stateStore.rocksdb.compactOnCommit", "true")

# 5. Periodic restart strategy (pragmatic for long-running jobs)
# Schedule weekly graceful restart from checkpoint
# This clears any accumulated memory leaks

# 6. Clear accumulator references
# In streaming foreachBatch:
def process_batch(batch_df, batch_id):
    # Process
    batch_df.unpersist()  # Explicitly free
    spark.sparkContext._jsc.sc().cleaner().doCleanupAccumulator()  # Force cleanup
```

---

## Issue #10: Metaspace OOM (Class Loading Exhaustion)

**Frequency**: Low-Medium  
**Severity**: Critical - unrecoverable without restart  
**Spark Component**: JVM ClassLoader, Codegen

### Symptoms
```
java.lang.OutOfMemoryError: Metaspace
  at java.lang.ClassLoader.defineClass
# OR
java.lang.OutOfMemoryError: Compressed class space
# Usually happens after many hours of running diverse queries
```

### Root Cause
- Whole-stage codegen creates new classes for each query plan
- Long-running applications with thousands of different query plans
- Dynamic class loading from UDF JARs never unloaded
- Spark REPL (notebooks) accumulating class definitions
- Thrift server with many concurrent users

### Solution
```python
# 1. Increase metaspace size
spark.conf.set("spark.executor.extraJavaOptions",
    "-XX:MaxMetaspaceSize=512m -XX:MetaspaceSize=256m")
spark.conf.set("spark.driver.extraJavaOptions",
    "-XX:MaxMetaspaceSize=1g -XX:MetaspaceSize=512m")

# 2. Disable whole-stage codegen for long-running apps (trade-off: slower queries)
spark.conf.set("spark.sql.codegen.wholeStage", "false")  # Last resort

# 3. Limit codegen cache
spark.conf.set("spark.sql.codegen.cache.maxEntries", "100")

# 4. Enable class unloading
spark.conf.set("spark.executor.extraJavaOptions",
    "-XX:+CMSClassUnloadingEnabled -XX:+UseG1GC "
    "-XX:+ClassUnloadingWithConcurrentMark")

# 5. For Thrift Server / long-running: periodic executor refresh
spark.conf.set("spark.dynamicAllocation.executorIdleTimeout", "300s")
spark.conf.set("spark.dynamicAllocation.cachedExecutorIdleTimeout", "600s")
# This cycles out old executors with bloated metaspace

# 6. Monitor metaspace
# JMX: java.lang:type=MemoryPool,name=Metaspace → Usage
# Alert if Usage > 80% of MaxMetaspaceSize
```

---

## Summary: Memory Issue Decision Tree

```
Job fails with OOM
├── Where does it fail?
│   ├── Driver → Issue #2 (collect) or #3 (broadcast)
│   ├── Executor during shuffle → Issue #1
│   ├── Executor during agg → Issue #6
│   ├── Container killed (YARN/K8s) → Issue #5
│   └── Python worker crash → Issue #8
├── When does it fail?
│   ├── Immediately → Issue #3 (broadcast too large)
│   ├── During specific stage → Issue #1, #6, #7
│   ├── After hours (streaming) → Issue #9
│   └── After days (long-running app) → Issue #10
└── What metric is high?
    ├── GC time > 10% → Issue #4
    ├── Shuffle spill → Issue #7
    ├── State store size growing → Issue #9
    └── Metaspace growing → Issue #10
```
