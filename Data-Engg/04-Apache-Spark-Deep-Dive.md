# Apache Spark - Staff Architect Deep Dive

## Table of Contents
1. [Architecture](#1-architecture)
2. [RDD Internals](#2-rdd-internals)
3. [Spark SQL and Catalyst Optimizer](#3-spark-sql-and-catalyst-optimizer)
4. [Adaptive Query Execution](#4-adaptive-query-execution)
5. [Shuffle Mechanism](#5-shuffle-mechanism)
6. [Memory Management](#6-memory-management)
7. [Joins Deep Dive](#7-joins-deep-dive)
8. [Structured Streaming](#8-structured-streaming)
9. [Data Skew Solutions](#9-data-skew-solutions)
10. [Performance Tuning](#10-performance-tuning)
11. [Spark on Kubernetes](#11-spark-on-kubernetes)
12. [Delta Lake Integration](#12-delta-lake-integration)
13. [Common Production Issues](#13-common-production-issues)

---

## 1. Architecture

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      SPARK APPLICATION                            │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐        │
│  │                    DRIVER PROCESS                      │        │
│  │                                                        │        │
│  │  ┌──────────────┐  ┌────────────────┐                │        │
│  │  │ SparkContext  │  │  SparkSession  │                │        │
│  │  │ (legacy)      │  │  (unified)     │                │        │
│  │  └──────┬───────┘  └───────┬────────┘                │        │
│  │         │                   │                          │        │
│  │  ┌──────▼───────────────────▼────────┐                │        │
│  │  │          DAGScheduler              │                │        │
│  │  │  - Builds DAG of stages            │                │        │
│  │  │  - Splits at shuffle boundaries    │                │        │
│  │  │  - Submits stages as TaskSets      │                │        │
│  │  └──────────────┬────────────────────┘                │        │
│  │                 │                                      │        │
│  │  ┌──────────────▼────────────────────┐                │        │
│  │  │          TaskScheduler             │                │        │
│  │  │  - Assigns tasks to executors      │                │        │
│  │  │  - Handles task failures/retries   │                │        │
│  │  │  - Locality-aware scheduling       │                │        │
│  │  └──────────────┬────────────────────┘                │        │
│  │                 │                                      │        │
│  │  ┌──────────────▼────────────────────┐                │        │
│  │  │        SchedulerBackend            │                │        │
│  │  │  (StandaloneSchedulerBackend /     │                │        │
│  │  │   YarnSchedulerBackend /           │                │        │
│  │  │   K8sSchedulerBackend)             │                │        │
│  │  └──────────────────────────────────┘                │        │
│  └──────────────────────────────────────────────────────┘        │
│                              │                                    │
│           ┌──────────────────┼──────────────────┐                │
│           ▼                  ▼                  ▼                │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │  Executor 0  │   │  Executor 1  │   │  Executor N  │        │
│  │              │   │              │   │              │        │
│  │ ┌──────────┐ │   │ ┌──────────┐ │   │ ┌──────────┐ │        │
│  │ │  Task    │ │   │ │  Task    │ │   │ │  Task    │ │        │
│  │ │  Thread  │ │   │ │  Thread  │ │   │ │  Thread  │ │        │
│  │ │  Pool    │ │   │ │  Pool    │ │   │ │  Pool    │ │        │
│  │ └──────────┘ │   │ └──────────┘ │   │ └──────────┘ │        │
│  │ ┌──────────┐ │   │ ┌──────────┐ │   │ ┌──────────┐ │        │
│  │ │  Block   │ │   │ │  Block   │ │   │ │  Block   │ │        │
│  │ │  Manager │ │   │ │  Manager │ │   │ │  Manager │ │        │
│  │ └──────────┘ │   │ └──────────┘ │   │ └──────────┘ │        │
│  └──────────────┘   └──────────────┘   └──────────────┘        │
└──────────────────────────────────────────────────────────────────┘
```

### Job → Stage → Task Breakdown

```
User Code:
  rdd.filter(...).groupByKey().mapValues(...).saveAsTextFile(...)

DAGScheduler creates:
  Job 0 (triggered by saveAsTextFile - an action)
  ├── Stage 0 (ShuffleMapStage)
  │   ├── filter (narrow dependency)
  │   └── groupByKey - MAP side (shuffle write)
  │   └── Tasks: [Task0(P0), Task1(P1), Task2(P2), ...]
  │
  └── Stage 1 (ResultStage)
      ├── groupByKey - REDUCE side (shuffle read)
      ├── mapValues (narrow dependency)
      └── saveAsTextFile
      └── Tasks: [Task0(P0), Task1(P1), ...]

Stage boundary = shuffle (wide dependency)
```

---

## 2. RDD Internals

### Dependencies

```
NARROW Dependencies (no shuffle, pipelined):
  map, filter, flatMap, union, mapPartitions
  
  Parent Partition → Child Partition (1:1 or N:1)
  
  P0 ────► P0'
  P1 ────► P1'
  P2 ────► P2'

WIDE Dependencies (shuffle required):
  groupByKey, reduceByKey, join, repartition
  
  Parent Partitions → ALL Child Partitions
  
  P0 ──┬──► P0'
  P1 ──┼──► P1'
  P2 ──┘──► P2'
```

### Persistence Levels

```python
from pyspark import StorageLevel

# Storage levels comparison:
# ┌────────────────────────┬────────┬──────┬──────────┬──────────┬───────────┐
# │ Level                  │ Memory │ Disk │ Ser.     │ Replicas │ Off-Heap  │
# ├────────────────────────┼────────┼──────┼──────────┼──────────┼───────────┤
# │ MEMORY_ONLY            │ Yes    │ No   │ No       │ 1        │ No        │
# │ MEMORY_AND_DISK        │ Yes    │ Yes  │ No       │ 1        │ No        │
# │ MEMORY_ONLY_SER        │ Yes    │ No   │ Yes      │ 1        │ No        │
# │ MEMORY_AND_DISK_SER    │ Yes    │ Yes  │ Yes      │ 1        │ No        │
# │ DISK_ONLY              │ No     │ Yes  │ Yes      │ 1        │ No        │
# │ MEMORY_ONLY_2          │ Yes    │ No   │ No       │ 2        │ No        │
# │ OFF_HEAP               │ No     │ No   │ Yes      │ 1        │ Yes       │
# └────────────────────────┴────────┴──────┴──────────┴──────────┴───────────┘

# Best practices:
df.cache()      # = MEMORY_AND_DISK (DataFrames default)
df.persist(StorageLevel.MEMORY_AND_DISK_SER)  # For memory pressure
df.unpersist()  # Free memory when done!
```

### Checkpointing vs Caching

```python
# Caching: Stores computed data in memory/disk
#          Lineage preserved (can recompute if lost)
#          Fast but uses resources
df.cache()

# Checkpointing: Writes to reliable storage (HDFS/S3)
#                Truncates lineage (breaks long chains)
#                Slower but prevents StackOverflow from deep lineage
sc.setCheckpointDir("s3://spark-checkpoints/")
rdd.checkpoint()  # Must call before action!
rdd.count()       # Triggers checkpoint

# Use checkpointing when:
# - Lineage is very long (iterative algorithms)
# - Recovery from cache loss would be too expensive
# - Graph has many branches (lineage grows exponentially)
```

---

## 3. Spark SQL and Catalyst Optimizer

### Catalyst Pipeline

```
User Code (SQL / DataFrame API)
         │
         ▼
┌──────────────────┐
│ 1. PARSING        │  SQL string → Unresolved Logical Plan
│    (ANTLR)        │  DataFrame API → Unresolved Logical Plan
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. ANALYSIS       │  Resolve columns, tables, functions
│    (Catalog)      │  Type checking, schema validation
│                    │  Unresolved → Resolved Logical Plan
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. LOGICAL        │  Apply optimization rules:
│    OPTIMIZATION   │  - Predicate pushdown
│                    │  - Column pruning
│                    │  - Constant folding
│                    │  - Boolean simplification
│                    │  - Null propagation
│                    │  - Join reordering (CBO)
│                    │  Optimized Logical Plan
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. PHYSICAL       │  Generate candidate physical plans
│    PLANNING       │  Choose join strategies (BHJ, SMJ, SHJ)
│                    │  Select sort algorithms
│                    │  Cost-based selection
│                    │  Selected Physical Plan
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. CODE           │  Whole-stage code generation
│    GENERATION     │  Vectorized execution
│    (Tungsten)     │  Generated Java code
└──────────────────┘
```

### Key Optimization Rules

```python
# 1. PREDICATE PUSHDOWN
# Before:
df.join(orders, "id").filter(col("date") > "2024-01-01")
# After optimization:
# Filter pushed before join → less data shuffled

# 2. COLUMN PRUNING
# Before:
df.select("name", "age").filter(col("age") > 30)
# After: Only reads "name" and "age" columns from source (Parquet)

# 3. CONSTANT FOLDING
# Before:
df.filter(col("x") > 1 + 2)
# After:
df.filter(col("x") > 3)  # Computed at planning time

# 4. PARTITION PRUNING
# Table partitioned by date:
spark.sql("SELECT * FROM events WHERE date = '2024-01-15'")
# Only reads partition files for 2024-01-15

# View the plan:
df.explain(True)  # Shows all 4 plan stages
df.explain("cost")  # Shows cost-based optimization info
```

### Cost-Based Optimization (CBO)

```sql
-- Collect statistics for CBO
ANALYZE TABLE orders COMPUTE STATISTICS;
ANALYZE TABLE orders COMPUTE STATISTICS FOR COLUMNS customer_id, amount, order_date;

-- CBO uses stats for:
-- 1. Join reordering (smaller table first)
-- 2. Join strategy selection (broadcast vs shuffle)
-- 3. Aggregate strategy selection
-- 4. Filter selectivity estimation
```

```python
# Enable CBO (enabled by default in Spark 3.x)
spark.conf.set("spark.sql.cbo.enabled", "true")
spark.conf.set("spark.sql.cbo.joinReorder.enabled", "true")
spark.conf.set("spark.sql.cbo.joinReorder.dp.star.filter", "true")

# View stats
spark.sql("DESCRIBE EXTENDED orders").show()
```

### Tungsten Engine

```
Tungsten Optimizations:

1. BINARY FORMAT (off-heap):
   Instead of Java objects (high GC overhead):
   ┌──────────────────────────────┐
   │ Object Header (16 bytes)     │
   │ String pointer (8 bytes)     │  ← Java Object (wasteful)
   │ int field (4 bytes + padding)│
   │ ...                          │
   └──────────────────────────────┘
   
   Tungsten binary format:
   ┌──────────────────┐
   │ [null bitmap]    │  ← Compact binary (no GC pressure)
   │ [field1: 4 bytes]│
   │ [offset to str]  │
   │ [str bytes]      │
   └──────────────────┘

2. WHOLE-STAGE CODE GENERATION:
   Instead of volcano-model iteration (virtual function calls per row):
   
   Volcano:  Scan.next() → Filter.next() → Project.next() → ...
             (virtual dispatch per row, poor CPU cache usage)
   
   Whole-stage codegen:
   while (scan.hasNext()) {
       Row row = scan.next();
       if (row.getInt(0) > 10) {     // Filter inlined
           output(row.getInt(0));     // Project inlined
       }
   }
   // Single tight loop, CPU cache friendly, no virtual dispatch
   
3. CACHE-AWARE COMPUTATION:
   Sort and hash operations designed for CPU cache line sizes
   Reduces L1/L2 cache misses significantly
```

---

## 4. Adaptive Query Execution (AQE)

### Overview (Spark 3.0+)

```
Traditional:  Plan → Execute (no changes during execution)
AQE:          Plan → Execute Stage → Re-optimize → Execute Next Stage → ...

AQE optimizations happen at STAGE BOUNDARIES (after shuffle):

Stage 0 ─── shuffle ──► [AQE Re-optimize] ──► Stage 1 ─── shuffle ──► ...
                         │
                         ├─ Coalesce partitions?
                         ├─ Switch join strategy?
                         └─ Handle skew?
```

### Dynamic Partition Coalescing

```python
# Problem: spark.sql.shuffle.partitions = 200 (default)
# But only 10 partitions have data → 190 empty tasks!

# AQE solution: Automatically coalesce small partitions
spark.conf.set("spark.sql.adaptive.enabled", "true")  # Default true since 3.2
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.minPartitionSize", "1m")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "64m")

# Before AQE: 200 partitions, 190 empty, 10 with data
# After AQE:  ~10 properly sized partitions
```

### Dynamic Join Strategy Switch

```python
# Problem: CBO estimates table at 20GB → plans Sort-Merge Join
# But after filter, actual data is only 5MB → should use Broadcast Join!

# AQE: After executing the filter stage, sees actual size
# Switches from Sort-Merge Join to Broadcast Hash Join at runtime

spark.conf.set("spark.sql.adaptive.autoBroadcastJoinThreshold", "10m")

# Before AQE: SortMergeJoin (planned based on table stats)
# After AQE:  BroadcastHashJoin (based on actual post-filter size)
```

### Skew Join Optimization

```python
# Problem: 99% of data goes to 1 partition (key "NULL" or hot user)
# That partition takes 100x longer than others

# AQE skew detection:
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256m")

# Detection: partition is skewed if:
#   size > median_partition_size * skewedPartitionFactor
#   AND size > skewedPartitionThresholdInBytes

# Solution: AQE splits the skewed partition into smaller sub-partitions
# and replicates the corresponding partition from the other side of the join

# Before: Partition 5 has 10GB, all others have 100MB
#   Task 5: Join(P5_left[10GB], P5_right[100MB]) → 30 minutes
#
# After AQE: Split P5_left into 10 sub-partitions
#   Task 5a: Join(P5a_left[1GB], P5_right[100MB]) → 3 minutes
#   Task 5b: Join(P5b_left[1GB], P5_right[100MB]) → 3 minutes
#   ...
```

---

## 5. Shuffle Mechanism

### Shuffle Architecture

```
MAP SIDE (Shuffle Write):
┌──────────────────────────────────────┐
│           Executor                    │
│                                       │
│  Task ──► Sort ──► Partition ──► Write│
│                                       │
│  Output files per task:               │
│  shuffle_0_0_0.data  (partition 0)    │
│  shuffle_0_0_0.index                  │
│                                       │
│  Sort-based shuffle (default):        │
│  Single file with all partitions      │
│  Index file for partition boundaries  │
└──────────────────────────────────────┘

REDUCE SIDE (Shuffle Read):
┌──────────────────────────────────────┐
│           Executor                    │
│                                       │
│  Fetch blocks from ALL map tasks      │
│  for THIS reduce partition            │
│                                       │
│  ┌─────────────────────────────┐     │
│  │  Fetch from Executor 0, P2  │     │
│  │  Fetch from Executor 1, P2  │     │
│  │  Fetch from Executor 2, P2  │     │
│  │         ...                  │     │
│  └─────────────────────────────┘     │
│                                       │
│  Sort/merge fetched data              │
│  Apply reduce function                │
└──────────────────────────────────────┘
```

### Shuffle Spill

```
When shuffle data exceeds execution memory:

1. Sort in-memory buffer fills up
2. Spill sorted data to disk (spill file)
3. Continue sorting next batch in memory
4. Repeat until all data processed
5. Merge all spill files (merge-sort)

Monitoring:
  - spark.executor.memoryOverhead
  - Shuffle Spill (Memory) in Spark UI
  - Shuffle Spill (Disk) in Spark UI

If Spill(Disk) >> 0:
  - Increase spark.executor.memory
  - Increase spark.memory.fraction
  - Reduce spark.sql.shuffle.partitions (smaller per-partition data)
  - Use more executors with less data each
```

### External Shuffle Service

```
Without ESS:
  Executor dies → shuffle files lost → recompute map stage!

With ESS:
  Shuffle files served by NodeManager process
  Executor can be released → files still available
  Required for dynamic allocation

# Enable:
spark.shuffle.service.enabled=true
spark.dynamicAllocation.enabled=true
```

---

## 6. Memory Management

### Unified Memory Model (Spark 1.6+)

```
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTOR MEMORY                           │
│                                                              │
│  Total: spark.executor.memory (e.g., 4GB)                   │
│                                                              │
│  ┌────────────────────────────────────────────┐             │
│  │         Spark Memory (fraction: 0.6)        │ = 2.4GB    │
│  │         spark.memory.fraction               │             │
│  │                                              │             │
│  │  ┌──────────────────┐ ┌──────────────────┐  │             │
│  │  │  Storage Memory  │ │ Execution Memory │  │             │
│  │  │  (fraction: 0.5) │ │ (fraction: 0.5)  │  │             │
│  │  │  = 1.2GB         │ │ = 1.2GB          │  │             │
│  │  │                  │ │                  │  │             │
│  │  │ Cached RDDs      │ │ Shuffles, joins  │  │             │
│  │  │ Broadcast vars   │ │ sorts, aggs      │  │             │
│  │  │ Unroll memory    │ │                  │  │             │
│  │  │                  │◄├─ Can borrow ──▶│  │             │
│  │  └──────────────────┘ └──────────────────┘  │             │
│  └────────────────────────────────────────────┘             │
│                                                              │
│  ┌────────────────────────────────────────────┐             │
│  │       User Memory (1 - fraction: 0.4)       │ = 1.6GB    │
│  │  - User data structures                     │             │
│  │  - Spark internal metadata                   │             │
│  │  - Reserved: 300MB (fixed)                   │             │
│  └────────────────────────────────────────────┘             │
│                                                              │
│  ┌────────────────────────────────────────────┐             │
│  │       Off-Heap Memory (optional)            │             │
│  │  spark.memory.offHeap.enabled=true          │             │
│  │  spark.memory.offHeap.size=2g               │             │
│  └────────────────────────────────────────────┘             │
│                                                              │
│  ┌────────────────────────────────────────────┐             │
│  │       Overhead Memory                       │             │
│  │  spark.executor.memoryOverhead              │             │
│  │  = max(384MB, 0.1 × executor.memory)        │             │
│  │  For: JVM overhead, native libs, PySpark    │             │
│  └────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────┘

Dynamic borrowing:
  - Execution can borrow from Storage (evict cached data)
  - Storage can borrow from Execution (only if execution is not using it)
  - Execution has priority (cannot be evicted by storage)
```

### Memory Calculation Formula

```
Total Container Memory (YARN/K8s):
  = spark.executor.memory 
    + spark.executor.memoryOverhead
    + spark.memory.offHeap.size (if enabled)
    + spark.executor.pyspark.memory (if PySpark)

Example:
  spark.executor.memory = 4g
  spark.executor.memoryOverhead = max(384m, 4g * 0.1) = 410m
  spark.memory.offHeap.size = 0
  
  Container request = 4g + 410m ≈ 4.4GB

Spark Memory = (4g - 300MB) * 0.6 = 2.22GB
  Storage = 2.22GB * 0.5 = 1.11GB
  Execution = 2.22GB * 0.5 = 1.11GB
User Memory = (4g - 300MB) * 0.4 = 1.48GB
Reserved = 300MB
```

---

## 7. Joins Deep Dive

### Join Strategy Decision Tree

```
                    ┌──────────────┐
                    │  Join Query   │
                    └──────┬───────┘
                           │
                  ┌────────▼────────┐
                  │ Either side <    │
              Yes │ broadcast       │ No
                  │ threshold?      │
                  │ (10MB default)  │
                  └───┬────────┬───┘
                      │        │
                 ┌────▼───┐    │
                 │Broadcast│    │
                 │Hash Join│    │
                 │(BHJ)    │    │
                 └─────────┘    │
                           ┌────▼──────────┐
                           │ Join keys      │
                       Yes │ sortable?      │ No
                           │               │
                           └───┬───────┬───┘
                               │       │
                          ┌────▼───┐   │
                          │Sort    │   │
                          │Merge   │   │
                          │Join    │   │
                          │(SMJ)   │   │
                          └────────┘   │
                                  ┌────▼──────┐
                                  │Broadcast  │
                                  │Nested Loop│
                                  │Join (BNLJ)│
                                  └───────────┘
```

### Join Types Explained

```python
# 1. BROADCAST HASH JOIN (BHJ) - Fastest for small tables
#    Small table broadcast to all executors, hash table built in memory
#    No shuffle required!
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "10485760")  # 10MB

# Force broadcast
from pyspark.sql.functions import broadcast
result = large_df.join(broadcast(small_df), "key")

# 2. SORT-MERGE JOIN (SMJ) - Default for large tables
#    Both tables shuffled by join key, sorted, then merged
#    Requires shuffle but handles large tables
#    O(n log n) per partition

# 3. SHUFFLE HASH JOIN (SHJ)
#    Both tables shuffled by join key, smaller side builds hash table
#    Better than SMJ when one side is much smaller (but > broadcast threshold)
spark.conf.set("spark.sql.join.preferSortMergeJoin", "false")  # Enable SHJ

# 4. BROADCAST NESTED LOOP JOIN (BNLJ)
#    For non-equi joins (theta joins, cross joins)
#    Broadcasts smaller side, nested loop iteration
#    O(n*m) - very expensive!

# 5. CARTESIAN JOIN
#    Full cross product - use with extreme caution
#    Only when no join condition specified
```

### Reading Explain Plans

```python
# Example explain plan
df1.join(df2, "customer_id").explain(True)

# Output:
# == Physical Plan ==
# *(2) BroadcastHashJoin [customer_id#0], [customer_id#10], Inner, BuildRight
# :- *(2) Project [customer_id#0, order_amount#1]
# :  +- *(2) Filter isnotnull(customer_id#0)
# :     +- *(2) FileScan parquet [customer_id#0, order_amount#1]
# +- BroadcastExchange HashedRelationBroadcastMode(List(input[0, string, true]))
#    +- *(1) Project [customer_id#10, customer_name#11]
#       +- *(1) Filter isnotnull(customer_id#10)
#          +- *(1) FileScan parquet [customer_id#10, customer_name#11]

# Key indicators:
# *(n) = Whole-stage codegen boundary n
# BroadcastExchange = Broadcasting data
# ShuffleExchange = Shuffle happening (expensive!)
# FileScan = Reading from storage (check pruned columns/partitions)
```

---

## 8. Structured Streaming

### Architecture

```
Micro-batch execution:

Time ──────────────────────────────────────────────────▶

Source:  ═══batch0═══╤═══batch1═══╤═══batch2═══╤═══
                     │            │            │
Trigger: ────────────┤────────────┤────────────┤────
                     │            │            │
Process: ┌──────────┐│┌──────────┐│┌──────────┐│
         │Spark Job 0│││Spark Job 1│││Spark Job 2││
         │(batch 0)  │││(batch 1)  │││(batch 2)  ││
         └──────────┘│└──────────┘│└──────────┘│
                     │            │            │
Sink:    ────write───┤────write───┤────write───┤────
```

### Streaming Queries

```python
from pyspark.sql.functions import window, col, count, sum as spark_sum

# Read from Kafka
df = (spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "kafka:9092")
    .option("subscribe", "events")
    .option("startingOffsets", "earliest")
    .option("maxOffsetsPerTrigger", 100000)
    .load()
    .selectExpr("CAST(key AS STRING)", "CAST(value AS STRING)",
                "timestamp", "topic", "partition", "offset")
)

# Parse JSON events
from pyspark.sql.types import StructType, StringType, DoubleType, TimestampType
schema = StructType() \
    .add("event_type", StringType()) \
    .add("user_id", StringType()) \
    .add("amount", DoubleType()) \
    .add("event_time", TimestampType())

events = df.select(
    from_json(col("value"), schema).alias("data")
).select("data.*")

# Windowed aggregation with watermark
result = (events
    .withWatermark("event_time", "10 minutes")  # Late data tolerance
    .groupBy(
        window(col("event_time"), "5 minutes", "1 minute"),  # Sliding window
        col("event_type")
    )
    .agg(
        count("*").alias("event_count"),
        spark_sum("amount").alias("total_amount")
    )
)

# Write to console (for debugging)
query = (result.writeStream
    .outputMode("update")           # update, append, complete
    .format("console")
    .trigger(processingTime="30 seconds")
    .option("checkpointLocation", "s3://checkpoints/events/")
    .start()
)

# TRIGGERS:
# processingTime="10 seconds"  - Micro-batch every 10s
# once=True                     - Single batch (Spark 3.3: use availableNow)
# availableNow=True             - Process all available, then stop
# continuous="1 second"         - Continuous processing (experimental)
```

### Output Modes

```
APPEND (default):
  Only new rows output (no updates to previously output rows)
  Use with: window aggregations WITH watermark, map/filter

COMPLETE:
  Entire result table output every trigger
  Use with: aggregations (all results re-emitted)
  Memory concern: stores entire result

UPDATE:
  Only changed rows output
  Use with: aggregations (only updated aggregates emitted)
  Most efficient for streaming aggregations
```

### Stream-Stream Joins

```python
# Stream-Stream join with watermarks
impressions = (spark.readStream.format("kafka")
    .option("subscribe", "impressions").load()
    .withWatermark("impression_time", "2 hours"))

clicks = (spark.readStream.format("kafka")
    .option("subscribe", "clicks").load()
    .withWatermark("click_time", "3 hours"))

# Inner join with time constraint
joined = impressions.join(
    clicks,
    expr("""
        impressions.ad_id = clicks.ad_id AND
        click_time >= impression_time AND
        click_time <= impression_time + interval 1 hour
    """),
    "inner"
)

# Left outer join (Spark 2.4+)
# Watermark required to know when to output null matches
left_joined = impressions.join(
    clicks,
    expr("""
        impressions.ad_id = clicks.ad_id AND
        click_time >= impression_time AND
        click_time <= impression_time + interval 1 hour
    """),
    "leftOuter"
)
```

### foreachBatch Pattern

```python
def write_to_multiple_sinks(batch_df, batch_id):
    """Write each micro-batch to multiple sinks"""
    # Cache to avoid recomputation
    batch_df.persist()
    
    # Write to Delta Lake
    batch_df.write.format("delta").mode("append").save("s3://lake/events")
    
    # Write aggregates to Postgres
    agg_df = batch_df.groupBy("event_type").count()
    agg_df.write.jdbc(url="jdbc:postgresql://...", table="event_counts",
                       mode="append", properties={"driver": "org.postgresql.Driver"})
    
    # Write alerts to Kafka
    alerts = batch_df.filter(col("severity") == "CRITICAL")
    alerts.selectExpr("CAST(event_id AS STRING) AS key", 
                       "to_json(struct(*)) AS value") \
        .write.format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:9092") \
        .option("topic", "alerts") \
        .save()
    
    batch_df.unpersist()

query = (events.writeStream
    .foreachBatch(write_to_multiple_sinks)
    .option("checkpointLocation", "s3://checkpoints/multi-sink/")
    .trigger(processingTime="1 minute")
    .start()
)
```

---

## 9. Data Skew Solutions

### Diagnosing Skew

```
Spark UI indicators:
1. Task Duration: One task takes 100x longer than median
2. Shuffle Read Size: One partition much larger than others
3. GC Time: Skewed task has excessive GC

Stage Summary:
┌──────────┬─────────┬─────────┬──────────┬──────────┐
│ Metric   │ Min     │ Median  │ Max      │ Skew?    │
├──────────┼─────────┼─────────┼──────────┼──────────┤
│ Duration │ 5s      │ 8s      │ 45min    │ YES!     │
│ Read     │ 10MB    │ 50MB    │ 15GB     │ YES!     │
│ Records  │ 100K    │ 500K    │ 50M      │ YES!     │
└──────────┴─────────┴─────────┴──────────┴──────────┘
```

### Solution 1: Salting

```python
import pyspark.sql.functions as F
from pyspark.sql.functions import col, lit, concat, rand, floor

NUM_SALT_BUCKETS = 10

# Salt the skewed (left) side
salted_orders = orders.withColumn(
    "salt", floor(rand() * NUM_SALT_BUCKETS).cast("string")
).withColumn(
    "salted_key", concat(col("customer_id"), lit("_"), col("salt"))
)

# Explode the non-skewed (right) side  
from pyspark.sql.functions import explode, array
salt_values = [lit(str(i)) for i in range(NUM_SALT_BUCKETS)]

exploded_customers = customers.withColumn(
    "salt", explode(array(*salt_values))
).withColumn(
    "salted_key", concat(col("customer_id"), lit("_"), col("salt"))
)

# Join on salted key (distributes skewed key across NUM_SALT_BUCKETS partitions)
result = salted_orders.join(
    exploded_customers,
    "salted_key",
    "inner"
).drop("salt", "salted_key")
```

### Solution 2: Isolate and Broadcast Skewed Keys

```python
# Step 1: Identify skewed keys
skewed_keys = (orders.groupBy("customer_id")
    .count()
    .filter(col("count") > 1000000)
    .select("customer_id")
    .collect())
skewed_key_list = [row.customer_id for row in skewed_keys]

# Step 2: Split into skewed and non-skewed
orders_skewed = orders.filter(col("customer_id").isin(skewed_key_list))
orders_normal = orders.filter(~col("customer_id").isin(skewed_key_list))
customers_skewed = customers.filter(col("customer_id").isin(skewed_key_list))
customers_normal = customers.filter(~col("customer_id").isin(skewed_key_list))

# Step 3: Broadcast join for skewed, regular join for normal
result_skewed = orders_skewed.join(broadcast(customers_skewed), "customer_id")
result_normal = orders_normal.join(customers_normal, "customer_id")

# Step 4: Union results
result = result_skewed.union(result_normal)
```

### Solution 3: Two-Phase Aggregation

```python
# Problem: groupBy on skewed key causes one reducer to process all data

# Phase 1: Pre-aggregate with salt (distributes load)
pre_agg = (orders
    .withColumn("salt", (rand() * 100).cast("int"))
    .groupBy("customer_id", "salt")
    .agg(spark_sum("amount").alias("partial_sum"),
         count("*").alias("partial_count"))
)

# Phase 2: Final aggregation (remove salt, combine partials)
final_agg = (pre_agg
    .groupBy("customer_id")
    .agg(spark_sum("partial_sum").alias("total_amount"),
         spark_sum("partial_count").alias("total_count"))
)
```

---

## 10. Performance Tuning

### Key Configuration Parameters

```python
# Executor sizing
spark.executor.memory = "8g"
spark.executor.cores = 4              # 4-5 cores per executor is optimal
spark.executor.instances = 20
spark.executor.memoryOverhead = "1g"  # For PySpark, increase this

# Shuffle tuning
spark.sql.shuffle.partitions = 200     # Default, tune based on data size
spark.shuffle.compress = True
spark.shuffle.spill.compress = True

# Serialization
spark.serializer = "org.apache.spark.serializer.KryoSerializer"
spark.kryoserializer.buffer.max = "1024m"

# Dynamic allocation
spark.dynamicAllocation.enabled = True
spark.dynamicAllocation.minExecutors = 5
spark.dynamicAllocation.maxExecutors = 100
spark.dynamicAllocation.executorIdleTimeout = "60s"
spark.dynamicAllocation.schedulerBacklogTimeout = "1s"

# AQE (Spark 3.0+)
spark.sql.adaptive.enabled = True
spark.sql.adaptive.coalescePartitions.enabled = True
spark.sql.adaptive.skewJoin.enabled = True

# File output
spark.sql.files.maxRecordsPerFile = 1000000  # Prevent huge files
spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version = 2
```

### Locality Levels

```
Locality levels (best to worst):
1. PROCESS_LOCAL - Data in same JVM (cached)
2. NODE_LOCAL    - Data on same node (local disk)
3. NO_PREF       - No locality preference
4. RACK_LOCAL    - Data in same rack
5. ANY           - Data anywhere in cluster

Spark waits spark.locality.wait (3s default) before degrading locality.
Tuning:
  spark.locality.wait = "3s"
  spark.locality.wait.process = "3s"
  spark.locality.wait.node = "3s"
  spark.locality.wait.rack = "3s"

# Reduce wait for faster scheduling at cost of locality
# Increase wait when data locality matters (HDFS reads)
```

### Partition Tuning Rules

```
Rule of thumb for spark.sql.shuffle.partitions:

Target partition size: 100MB - 200MB

partitions = total_shuffle_data / target_partition_size

Example:
  Total shuffle data: 100GB
  Target partition: 128MB
  Partitions = 100GB / 128MB ≈ 800

For spark.sql.files.maxPartitionBytes (reading files):
  Default: 128MB
  Smaller = more parallelism, more overhead
  Larger = less parallelism, less overhead

For output file count:
  df.repartition(N).write.parquet(...)  # Exactly N files
  df.coalesce(N).write.parquet(...)     # At most N files (no shuffle!)
```

---

## 11. Spark on Kubernetes

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   KUBERNETES CLUSTER                       │
│                                                           │
│  ┌────────────────────────────────────────┐               │
│  │           Driver Pod                    │               │
│  │  ┌──────────────────────────────┐      │               │
│  │  │  Spark Driver                 │      │               │
│  │  │  - SparkContext               │      │               │
│  │  │  - DAGScheduler               │      │               │
│  │  │  - K8sSchedulerBackend        │      │               │
│  │  └──────────────────────────────┘      │               │
│  └─────────────────┬──────────────────────┘               │
│                    │ Creates executor pods                  │
│        ┌───────────┼───────────┐                          │
│        ▼           ▼           ▼                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│  │Executor 0│ │Executor 1│ │Executor N│                 │
│  │  Pod     │ │  Pod     │ │  Pod     │                 │
│  │          │ │          │ │          │                 │
│  │ Resources│ │ Resources│ │ Resources│                 │
│  │ CPU: 4   │ │ CPU: 4   │ │ CPU: 4   │                 │
│  │ Mem: 8Gi │ │ Mem: 8Gi │ │ Mem: 8Gi │                 │
│  └──────────┘ └──────────┘ └──────────┘                 │
│                                                           │
│  ┌──────────────────────────────────────────┐            │
│  │  External Shuffle Service (DaemonSet)     │            │
│  │  For dynamic allocation                   │            │
│  └──────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────┘
```

### Spark Submit on Kubernetes

```bash
spark-submit \
  --master k8s://https://k8s-api-server:6443 \
  --deploy-mode cluster \
  --name spark-etl-job \
  --conf spark.kubernetes.container.image=spark-app:latest \
  --conf spark.kubernetes.namespace=spark-jobs \
  --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark \
  --conf spark.executor.instances=10 \
  --conf spark.executor.memory=8g \
  --conf spark.executor.cores=4 \
  --conf spark.driver.memory=4g \
  --conf spark.kubernetes.executor.request.cores=4 \
  --conf spark.kubernetes.executor.limit.cores=4 \
  --conf spark.kubernetes.node.selector.node-type=compute \
  --conf spark.kubernetes.executor.podTemplateFile=executor-template.yaml \
  local:///opt/spark/app/etl_job.py
```

---

## 12. Delta Lake Integration

### ACID Transactions

```python
# Create Delta table
df.write.format("delta").save("s3://lake/orders")

# MERGE (Upsert)
from delta.tables import DeltaTable

delta_table = DeltaTable.forPath(spark, "s3://lake/orders")

delta_table.alias("target").merge(
    updates_df.alias("source"),
    "target.order_id = source.order_id"
).whenMatchedUpdateAll() \
 .whenNotMatchedInsertAll() \
 .execute()

# Time Travel
df_v1 = spark.read.format("delta") \
    .option("versionAsOf", 5) \
    .load("s3://lake/orders")

df_timestamp = spark.read.format("delta") \
    .option("timestampAsOf", "2024-01-15T10:00:00") \
    .load("s3://lake/orders")

# Z-Ordering (co-locate related data for faster reads)
delta_table.optimize().executeZOrderBy("customer_id", "order_date")

# VACUUM (clean up old files)
delta_table.vacuum(168)  # Delete files older than 168 hours (7 days)

# Change Data Feed
spark.read.format("delta") \
    .option("readChangeFeed", "true") \
    .option("startingVersion", 10) \
    .load("s3://lake/orders")
# Returns: _change_type (insert/update_preimage/update_postimage/delete)
```

### Liquid Clustering (Delta 3.0+)

```python
# Replace partitioning and Z-ordering with liquid clustering
# Automatically manages data layout

# Create table with liquid clustering
(df.write.format("delta")
    .clusterBy("customer_id", "order_date")
    .save("s3://lake/orders_clustered"))

# Trigger optimization
spark.sql("OPTIMIZE delta.`s3://lake/orders_clustered`")

# Advantages over Z-ordering:
# - No need to manually choose partition columns
# - Can change clustering columns without rewriting
# - Incremental clustering (only new data)
# - Better for evolving query patterns
```

---

## 13. Common Production Issues

### 1. Executor OOM

```
Symptoms: java.lang.OutOfMemoryError: Java heap space
          ExecutorLostFailure (executor X exited caused by one of the running tasks)

Common causes and fixes:

Cause 1: Data skew in join/groupBy
  Fix: Salting, AQE skew join, broadcast join

Cause 2: collect() or toPandas() with large data
  Fix: Never collect() in production; use take(N) or write to storage

Cause 3: Broadcast variable too large
  Fix: Reduce autoBroadcastJoinThreshold, use SMJ instead

Cause 4: Too many cores per executor
  Fix: Reduce spark.executor.cores (each core needs memory for tasks)

Cause 5: Large records (e.g., base64 images in JSON)
  Fix: Filter/process before shuffle, increase memory

General tuning:
  spark.executor.memory = "8g"       # Increase
  spark.executor.memoryOverhead = "2g"  # Increase for PySpark
  spark.memory.fraction = 0.6         # Increase if more needed for execution
  spark.sql.shuffle.partitions = 400   # More partitions = less per partition
```

### 2. Small Files Problem

```
Cause: Many tasks writing many small files
  200 partitions × 10 executors = 2000 files per write!

Solutions:

1. Repartition/Coalesce before write:
   df.coalesce(10).write.parquet("output/")   # No shuffle
   df.repartition(10).write.parquet("output/") # With shuffle (better distribution)

2. maxRecordsPerFile:
   df.write.option("maxRecordsPerFile", 1000000).parquet("output/")

3. AQE coalescing:
   spark.sql.adaptive.coalescePartitions.enabled = true

4. Delta Lake OPTIMIZE:
   spark.sql("OPTIMIZE delta.`s3://lake/table`")

5. Post-write compaction job:
   Scheduled job that reads small files + rewrites as larger files
```

### 3. GC Tuning

```bash
# Recommended GC settings for Spark
spark.executor.extraJavaOptions="-XX:+UseG1GC \
  -XX:InitiatingHeapOccupancyPercent=35 \
  -XX:G1HeapRegionSize=16M \
  -XX:ConcGCThreads=4 \
  -XX:ParallelGCThreads=8 \
  -XX:+ParallelRefProcEnabled \
  -XX:+UnlockDiagnosticVMOptions \
  -XX:+G1SummarizeConcMark"

# If GC time > 10% of task time:
# 1. Reduce executor heap (more executors, less memory each)
# 2. Use Kryo serialization (smaller objects)
# 3. Use off-heap memory
# 4. Increase spark.memory.fraction (less user memory, less GC)
```

### 4. FetchFailedException

```
Cause: Shuffle read failure - shuffle file unavailable on remote executor
  org.apache.spark.shuffle.FetchFailedException

Common causes:
1. Executor OOM during shuffle write → incomplete shuffle files
2. Executor preempted (YARN/K8s) → shuffle files lost
3. Network issues between executors
4. Disk full on executor node

Fixes:
1. Enable external shuffle service:
   spark.shuffle.service.enabled=true

2. Increase retries:
   spark.shuffle.io.maxRetries=10
   spark.shuffle.io.retryWait=30s

3. Increase memory to prevent OOM during shuffle:
   spark.executor.memory=12g

4. Reduce data per partition:
   spark.sql.shuffle.partitions=400
```

---

## Production Checklist

```
[ ] Serializer: Kryo (spark.serializer=org.apache.spark.serializer.KryoSerializer)
[ ] AQE enabled (spark.sql.adaptive.enabled=true)
[ ] Dynamic allocation configured (min/max executors)
[ ] External shuffle service for dynamic allocation
[ ] Executor sizing: 4-5 cores, 8-16GB memory per executor
[ ] shuffle.partitions tuned (not default 200)
[ ] Checkpoint location for streaming (reliable storage)
[ ] Watermarks for streaming aggregations
[ ] Data skew handling (AQE or manual salting)
[ ] GC tuning (G1GC with appropriate settings)
[ ] File output size control (coalesce/repartition/maxRecordsPerFile)
[ ] Monitoring: Spark UI, Spark History Server, metrics sink
[ ] Delta Lake: scheduled OPTIMIZE and VACUUM
[ ] Error handling: retry logic, dead letter for bad records
```
