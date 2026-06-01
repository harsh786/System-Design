# Scaling AWS Glue for Billions of Transactions: Performance Tuning & Optimization

## 1. The Problem: Processing 10B Records/Day Within 4-Hour Windows at Minimum Cost

### Business Context

An enterprise financial platform ingests transaction data from 100+ source tables across
multiple regions. The data must be transformed, deduplicated, enriched with dimension
lookups, and landed in an analytics-ready format—all within a 4-hour nightly window.

### Scale Parameters

| Parameter              | Value                    |
|------------------------|--------------------------|
| Daily record volume    | 10 billion records       |
| Processing window      | 4 hours (02:00–06:00)   |
| Monthly budget ceiling | $50,000                  |
| Source tables          | 100+                     |
| Average record size    | 1.2 KB                  |
| Daily raw data volume  | ~12 TB                   |
| Target latency (P99)   | < 4 hours end-to-end    |
| Data freshness SLA     | Analytics ready by 06:30 |

### Constraints

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONSTRAINT TRIANGLE                               │
│                                                                     │
│                         TIME                                        │
│                        ╱    ╲                                       │
│                  4 hours     100+ tables                            │
│                     ╱            ╲                                  │
│                COST ━━━━━━━━━━━━━━ QUALITY                         │
│              $50K/mo              Zero data loss                    │
│                                  Exactly-once semantics             │
└─────────────────────────────────────────────────────────────────────┘
```

Key tensions:
- More workers = faster but more expensive
- Larger workers = handle skew but cost more per DPU-hour
- Flex execution = 60% cheaper but no SLA on start time
- Auto-scaling = elastic but cold-start penalty per scaling event

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 2. AWS Glue Execution Model Deep Dive

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AWS GLUE JOB EXECUTION                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐         ┌──────────────────────────────────────────┐ │
│  │ DRIVER NODE  │         │           EXECUTOR NODES                 │ │
│  │              │         │                                          │ │
│  │  - DAG Plan  │ ──────▶ │  ┌────────┐ ┌────────┐ ┌────────┐     │ │
│  │  - Schedule  │         │  │Exec #1 │ │Exec #2 │ │Exec #N │     │ │
│  │  - Coordinate│         │  │        │ │        │ │        │     │ │
│  │  - Collect   │ ◀────── │  │4 cores │ │4 cores │ │4 cores │     │ │
│  │              │         │  │16GB RAM│ │16GB RAM│ │16GB RAM│     │ │
│  │  1 DPU       │         │  └────────┘ └────────┘ └────────┘     │ │
│  └──────────────┘         │                                          │ │
│                            │  (N-1) DPUs for G.1X workers            │ │
│                            └──────────────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ AUTO-SCALER: Monitors executor utilization every 60 seconds     │   │
│  │ Adds workers if: pending tasks > 2x available slots             │   │
│  │ Removes workers if: idle executors > 30% for 2+ minutes         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### DPU Allocation

1 DPU (Data Processing Unit) = 4 vCPUs + 16 GB RAM + 64 GB disk

The driver always consumes 1 DPU. Remaining DPUs become executor nodes.
For a job configured with 100 G.1X workers: 1 driver + 99 executors.

### Worker Types Comparison

| Worker Type | vCPU | Memory | Disk    | Cost/DPU-hr | Best For                          |
|-------------|------|--------|---------|-------------|-----------------------------------|
| G.1X        | 4    | 16 GB  | 64 GB   | $0.44       | Standard ETL, I/O bound           |
| G.2X        | 8    | 32 GB  | 128 GB  | $0.44       | Memory-heavy joins, aggregations  |
| G.4X        | 16   | 64 GB  | 256 GB  | $0.44       | ML transforms, wide tables        |
| G.8X        | 32   | 128 GB | 512 GB  | $0.44       | Extreme skew, huge broadcasts     |
| Z.2X        | 8    | 64 GB  | 128 GB  | $0.44       | Memory-intensive (2x RAM vs G.2X) |

Note: Cost per DPU-hour is the same. The difference is how many DPUs each worker consumes:
- G.1X = 1 DPU per worker
- G.2X = 2 DPUs per worker
- G.4X = 4 DPUs per worker
- G.8X = 8 DPUs per worker
- Z.2X = 2 DPUs per worker (memory-optimized)

### Standard vs Flex Execution

```
┌─────────────────────────────┬─────────────────────────────────────────┐
│     STANDARD EXECUTION      │          FLEX EXECUTION                 │
├─────────────────────────────┼─────────────────────────────────────────┤
│ Dedicated capacity          │ Spare capacity (spot-like)              │
│ Immediate start             │ May queue up to 20 minutes              │
│ Full SLA on start time      │ No start-time SLA                       │
│ $0.44/DPU-hour              │ $0.29/DPU-hour (34% cheaper)            │
│ Preemption: never           │ Preemption: never (once started)        │
│ Use for: SLA-bound jobs     │ Use for: non-urgent, retry-tolerant     │
└─────────────────────────────┴─────────────────────────────────────────┘
```

### Auto-Scaling Mechanics

```
Timeline of Auto-Scaling Decision:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

T+0s   : Job starts with min workers (e.g., 10)
T+60s  : Scaler evaluates: pending_tasks=500, slots=40 → SCALE UP
T+90s  : New workers provisioning (30-60s warm-up)
T+150s : New workers ready, tasks redistributed
T+300s : Stage completes, next stage fewer tasks → evaluate
T+360s : idle_executors=15/50 (30%) for 2 min → SCALE DOWN
T+420s : Workers gracefully removed after current task completes

Key parameters:
  --enable-auto-scaling true
  --number-of-workers 100        (this becomes MAX workers)
  Minimum workers: ~30% of max   (Glue decides internally)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3. Performance Optimization Techniques

### 3.1 Partition Pruning

**Before**: Full scan of 365-day partitioned table (12 TB)
**After**: Read only 1 day (33 GB) via pushdown predicate

```python
# BAD: Reads all partitions, filters after load
df = glueContext.create_dynamic_frame.from_catalog(
    database="prod", table_name="transactions"
).toDF()
df = df.filter(col("transaction_date") == "2024-01-15")

# GOOD: Pushdown predicate — Glue reads only matching partitions
df = glueContext.create_dynamic_frame.from_catalog(
    database="prod",
    table_name="transactions",
    push_down_predicate="transaction_date='2024-01-15'"
).toDF()
```

Impact: **360x reduction** in data scanned (12 TB → 33 GB)

### 3.2 Column Pruning

**Before**: Read all 200 columns, use 12
**After**: Select only needed columns at read time

```python
# Specify columns in DynamicFrame
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="prod",
    table_name="transactions",
    additional_options={
        "optimizePerformance": True  # Enables column pruning for Parquet
    }
)
# Project immediately
df = dyf.toDF().select("txn_id", "amount", "customer_id", "timestamp",
                        "merchant_id", "category", "status")
```

Impact: **16x less I/O** for Parquet columnar format (12/200 columns)

### 3.3 Predicate Pushdown to Source

```python
# For JDBC sources: push filter to database
df = glueContext.create_dynamic_frame.from_catalog(
    database="prod",
    table_name="jdbc_orders",
    additional_options={
        "hashfield": "order_id",          # Parallel reads
        "hashpartitions": "20",
        "filterPredicate": "order_date >= '2024-01-01'"  # DB-side filter
    }
)
```

### 3.4 Broadcast Join

```python
from pyspark.sql.functions import broadcast

# Dimension table: 500K rows, ~50 MB
merchants_df = spark.read.parquet("s3://data/dim_merchants/")

# Fact table: 2B rows
transactions_df = spark.read.parquet("s3://data/fact_transactions/")

# Force broadcast of small table — avoids shuffle of 2B rows
enriched = transactions_df.join(
    broadcast(merchants_df),
    "merchant_id",
    "left"
)
```

Impact: Eliminates shuffle of 2B records. **5x faster** join.

Threshold: Broadcast tables should be < 500 MB (configurable via
`spark.sql.autoBroadcastJoinThreshold`).

### 3.5 Data Skew Handling (Salting)

```python
import pyspark.sql.functions as F

# Problem: 40% of transactions belong to top 100 merchants
# One executor gets 40% of work during groupBy("merchant_id")

# SOLUTION: Salt the key
SALT_BUCKETS = 20

# Step 1: Add salt to fact table
salted_facts = transactions_df.withColumn(
    "salt", (F.rand() * SALT_BUCKETS).cast("int")
).withColumn(
    "salted_key", F.concat(F.col("merchant_id"), F.lit("_"), F.col("salt"))
)

# Step 2: Explode dimension table with all salt values
salt_df = spark.range(0, SALT_BUCKETS).withColumnRenamed("id", "salt")
salted_dim = merchants_df.crossJoin(salt_df).withColumn(
    "salted_key", F.concat(F.col("merchant_id"), F.lit("_"), F.col("salt"))
)

# Step 3: Join on salted key (evenly distributed)
result = salted_facts.join(broadcast(salted_dim), "salted_key", "inner")

# Step 4: Drop salt columns
result = result.drop("salt", "salted_key")
```

Impact: Reduces max executor time from **45 min to 8 min** (5.6x improvement)

### 3.6 Small Files Problem

```python
# PROBLEM: Source has 500,000 files averaging 2 MB each (1 TB total)
# Spark creates 500K tasks — scheduling overhead dominates

# SOLUTION 1: groupFiles at read time
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="prod",
    table_name="raw_events",
    additional_options={
        "groupFiles": "inPartition",   # Merge files within partition
        "groupSize": "134217728"       # Target 128 MB per group
    }
)
# Result: 500K files → ~8,000 tasks (128 MB each)

# SOLUTION 2: Compact small files as a separate job
compacted = df.repartition(100)  # 1 TB / 100 = 10 GB per partition (too large)
compacted = df.coalesce(1000)    # 1 TB / 1000 = 1 GB per file (good for Parquet)
compacted.write.mode("overwrite").parquet("s3://data/compacted/")
```

Impact: Task scheduling from **12 min overhead to 30 seconds**

### 3.7 Memory Management & GC Tuning

```python
# Job parameters for memory-intensive workloads
conf = SparkConf()
conf.set("spark.executor.memory", "14g")         # For G.1X (16GB total, ~2GB overhead)
conf.set("spark.executor.memoryOverhead", "2g")
conf.set("spark.driver.memory", "14g")
conf.set("spark.memory.fraction", "0.8")          # 80% for execution+storage
conf.set("spark.memory.storageFraction", "0.3")   # 30% of 80% for caching
conf.set("spark.sql.shuffle.partitions", "2000")  # Match parallelism to data volume

# GC Tuning for large heaps (G.4X with 64 GB)
conf.set("spark.executor.extraJavaOptions",
    "-XX:+UseG1GC "
    "-XX:G1HeapRegionSize=16m "
    "-XX:InitiatingHeapOccupancyPercent=35 "
    "-XX:ConcGCThreads=4 "
    "-XX:+ParallelRefProcEnabled"
)
```

Memory layout per G.2X executor (32 GB total):
```
┌─────────────────────────────────────────────────────┐
│  32 GB Total                                        │
├─────────────────────────────────────────────────────┤
│  Reserved (300 MB)                                  │
├─────────────────────────────────────────────────────┤
│  User Memory (20%): 5.7 GB                          │
│   - UDF data structures, RDD metadata              │
├─────────────────────────────────────────────────────┤
│  Execution Memory (shared): ~16 GB                  │
│   - Shuffles, joins, sorts, aggregations           │
├─────────────────────────────────────────────────────┤
│  Storage Memory (shared): ~7 GB                     │
│   - Cached DataFrames, broadcast variables          │
├─────────────────────────────────────────────────────┤
│  Overhead: 3.5 GB                                   │
│   - Off-heap, Python workers, internal buffers     │
└─────────────────────────────────────────────────────┘
```

### 3.8 Shuffle Optimization

```python
# Tune shuffle partitions based on data volume
# Rule of thumb: target 128-256 MB per shuffle partition

data_size_gb = 500  # After filters
target_partition_mb = 200
shuffle_partitions = int((data_size_gb * 1024) / target_partition_mb)
# = 2560 partitions

spark.conf.set("spark.sql.shuffle.partitions", str(shuffle_partitions))

# Enable Adaptive Query Execution (Glue 4.0+)
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256m")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128m")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4. Auto-Scaling Configuration

### When to Enable vs Disable

| Scenario                          | Auto-Scaling | Reason                              |
|-----------------------------------|--------------|-------------------------------------|
| Multi-stage with varying load     | ENABLE       | Scale down between stages saves $$  |
| Single-stage bulk transform       | DISABLE      | Overhead of scaling > benefit        |
| Unpredictable data volumes        | ENABLE       | Handles spikes gracefully           |
| Time-critical SLA job             | DISABLE      | Cold-start penalty on scale-up       |
| Development/testing               | ENABLE       | Cost savings during iteration        |
| Streaming (continuous)            | ENABLE       | Load varies by time of day           |

### Configuration

```python
# Terraform/CloudFormation configuration
job_config = {
    "GlueVersion": "4.0",
    "WorkerType": "G.2X",
    "NumberOfWorkers": 200,          # This is MAX when auto-scaling enabled
    "ExecutionProperty": {
        "MaxConcurrentRuns": 3
    },
    "DefaultArguments": {
        "--enable-auto-scaling": "true",
        "--enable-metrics": "true",
        "--enable-continuous-cloudwatch-log": "true",
        "--conf": "spark.sql.adaptive.enabled=true"
    }
}

# Actual behavior with auto-scaling:
# Min workers: ~60 (Glue determines, roughly 30% of max)
# Max workers: 200
# Scale-up trigger: pending tasks > 2x available parallelism
# Scale-down trigger: >30% idle executors for 2+ minutes
# Scale-up time: 30-90 seconds per batch of workers
```

### Cost Implications

```
Fixed 200 workers × 4 hours = 800 DPU-hours × $0.44 = $352/run

Auto-scaling (observed pattern):
  0-30 min:   60 workers  (ramp up)      =  30 DPU-hours
  30-90 min:  180 workers (peak)          = 180 DPU-hours
  90-150 min: 120 workers (declining)     =  60 DPU-hours
  150-210 min: 60 workers (tail)          =  30 DPU-hours
  Total: 300 DPU-hours × $0.44 = $132/run

Savings: 62% cost reduction with auto-scaling for this workload pattern
```

### Predictive Scaling Pattern

For jobs with known data volume patterns (e.g., month-end spikes):

```python
import boto3
from datetime import datetime

def get_optimal_workers(table_name: str) -> int:
    """Determine worker count based on data volume signals."""
    s3 = boto3.client("s3")
    
    # Check today's partition size
    response = s3.list_objects_v2(
        Bucket="data-lake",
        Prefix=f"raw/{table_name}/date={datetime.today().strftime('%Y-%m-%d')}/",
    )
    total_bytes = sum(obj["Size"] for obj in response.get("Contents", []))
    total_gb = total_bytes / (1024**3)
    
    # Heuristic: 1 G.2X worker per 5 GB, min 10, max 300
    workers = max(10, min(300, int(total_gb / 5)))
    return workers
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5. Implementation Code — Full Production Job

```python
"""
Production AWS Glue Job: Transaction Processing at Scale
Processes 10B records/day with optimized performance configuration.
"""
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.conf import SparkConf
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# ─────────────────────────────────────────────────────────────────────
# 1. OPTIMAL CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

args = getResolvedOptions(sys.argv, [
    "JOB_NAME", "processing_date", "target_bucket"
])

conf = SparkConf()
# Shuffle optimization
conf.set("spark.sql.shuffle.partitions", "4000")
conf.set("spark.sql.files.maxPartitionBytes", "134217728")  # 128 MB
conf.set("spark.sql.files.openCostInBytes", "8388608")      # 8 MB

# Adaptive Query Execution (Glue 4.0+)
conf.set("spark.sql.adaptive.enabled", "true")
conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256m")
conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "200m")

# Broadcast threshold
conf.set("spark.sql.autoBroadcastJoinThreshold", "500m")  # 500 MB

# Serialization
conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
conf.set("spark.kryoserializer.buffer.max", "512m")

# Memory
conf.set("spark.memory.fraction", "0.8")
conf.set("spark.memory.storageFraction", "0.2")

# S3 optimization
conf.set("spark.hadoop.fs.s3a.connection.maximum", "200")
conf.set("spark.hadoop.fs.s3a.threads.max", "64")
conf.set("spark.hadoop.fs.s3a.multipart.size", "104857600")  # 100 MB parts
conf.set("spark.sql.parquet.mergeSchema", "false")
conf.set("spark.sql.parquet.filterPushdown", "true")

sc = SparkContext(conf=conf)
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

processing_date = args["processing_date"]
target_bucket = args["target_bucket"]

# ─────────────────────────────────────────────────────────────────────
# 2. READ WITH PARTITION PRUNING & SMALL FILE GROUPING
# ─────────────────────────────────────────────────────────────────────

# Main fact table: 10B records in daily partition, ~500K small files
transactions_dyf = glueContext.create_dynamic_frame.from_catalog(
    database="production",
    table_name="raw_transactions",
    push_down_predicate=f"transaction_date='{processing_date}'",
    additional_options={
        "groupFiles": "inPartition",
        "groupSize": "268435456",  # 256 MB groups
        "optimizePerformance": True
    }
)
transactions_df = transactions_dyf.toDF()

print(f"Transactions loaded: {transactions_df.count():,} records")

# ─────────────────────────────────────────────────────────────────────
# 3. DIMENSION TABLES WITH BROADCAST
# ─────────────────────────────────────────────────────────────────────

# Small dimension: 2M merchants, ~200 MB
merchants_df = spark.read.parquet(
    f"s3://{target_bucket}/dimensions/merchants/latest/"
).select("merchant_id", "merchant_name", "category", "region", "risk_score")

# Medium dimension: 50M customers, ~2 GB — too large for broadcast
customers_df = spark.read.parquet(
    f"s3://{target_bucket}/dimensions/customers/latest/"
).select("customer_id", "segment", "lifetime_value", "country")

# ─────────────────────────────────────────────────────────────────────
# 4. HANDLE DATA SKEW FOR CUSTOMER JOIN
# ─────────────────────────────────────────────────────────────────────

# Top 1% of customers generate 30% of transactions (power-law distribution)
# Use AQE skew join (Glue 4.0+ handles this automatically with config above)
# For extreme skew, manual salting:

SALT_FACTOR = 10

# Identify hot keys (>1M transactions per customer)
key_counts = transactions_df.groupBy("customer_id").count()
hot_keys = key_counts.filter(F.col("count") > 1000000).select("customer_id")
hot_key_set = {row.customer_id for row in hot_keys.collect()}

# Broadcast hot keys set
hot_keys_bc = sc.broadcast(hot_key_set)

# Split into hot and cold paths
is_hot = F.udf(lambda cid: cid in hot_keys_bc.value)

hot_txns = transactions_df.filter(is_hot(F.col("customer_id")))
cold_txns = transactions_df.filter(~is_hot(F.col("customer_id")))

# Salt only hot path
hot_txns_salted = hot_txns.withColumn(
    "salt", (F.rand() * SALT_FACTOR).cast("int")
)
customers_exploded = customers_df.crossJoin(
    spark.range(0, SALT_FACTOR).withColumnRenamed("id", "salt")
)

# Join hot path with salted keys
hot_joined = hot_txns_salted.join(
    customers_exploded,
    (hot_txns_salted.customer_id == customers_exploded.customer_id) &
    (hot_txns_salted.salt == customers_exploded.salt),
    "left"
).drop(customers_exploded.customer_id).drop("salt")

# Join cold path normally
cold_joined = cold_txns.join(customers_df, "customer_id", "left")

# Union results
customer_enriched = hot_joined.unionByName(cold_joined, allowMissingColumns=True)

# ─────────────────────────────────────────────────────────────────────
# 5. BROADCAST JOIN FOR SMALL DIMENSION
# ─────────────────────────────────────────────────────────────────────

enriched_df = customer_enriched.join(
    F.broadcast(merchants_df),
    "merchant_id",
    "left"
)

# ─────────────────────────────────────────────────────────────────────
# 6. TRANSFORMATIONS
# ─────────────────────────────────────────────────────────────────────

result_df = enriched_df.withColumn(
    "amount_usd", F.col("amount") * F.col("exchange_rate")
).withColumn(
    "processing_hour", F.hour(F.col("timestamp"))
).withColumn(
    "is_high_value", F.when(F.col("amount_usd") > 10000, True).otherwise(False)
).withColumn(
    "risk_flag", F.when(
        (F.col("risk_score") > 0.8) & (F.col("amount_usd") > 5000), "HIGH"
    ).when(
        F.col("risk_score") > 0.5, "MEDIUM"
    ).otherwise("LOW")
)

# ─────────────────────────────────────────────────────────────────────
# 7. WRITE WITH OPTIMAL PARTITIONING & COMPRESSION
# ─────────────────────────────────────────────────────────────────────

# Target: ~256 MB per output file for optimal downstream read performance
# 33 GB output / 256 MB = ~130 files
output_partitions = 130

result_df.repartition(
    output_partitions,
    "region"  # Physical partition by region for downstream query patterns
).sortWithinPartitions("customer_id", "timestamp") \
 .write \
 .mode("overwrite") \
 .partitionBy("region") \
 .option("compression", "zstd") \
 .option("maxRecordsPerFile", 5000000) \
 .parquet(f"s3://{target_bucket}/processed/transactions/date={processing_date}/")

job.commit()
print(f"Job completed successfully for {processing_date}")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. Benchmarking Results

### Worker Type vs Performance vs Cost

Workload: 2B records, 500 GB Parquet, simple transforms + 1 join

| Worker Type | Workers | DPU-hrs | Duration | Cost    | Throughput    |
|-------------|---------|---------|----------|---------|---------------|
| G.1X        | 100     | 400     | 4.0 hr   | $176    | 500M rec/hr   |
| G.1X        | 200     | 600     | 3.0 hr   | $264    | 667M rec/hr   |
| G.2X        | 50      | 400     | 2.8 hr   | $176    | 714M rec/hr   |
| G.2X        | 100     | 600     | 1.5 hr   | $264    | 1.3B rec/hr   |
| G.4X        | 25      | 400     | 2.5 hr   | $176    | 800M rec/hr   |
| G.4X        | 50      | 600     | 1.3 hr   | $264    | 1.5B rec/hr   |

**Finding**: G.2X with 100 workers is the sweet spot for join-heavy workloads.
G.4X only wins when individual records are very wide (1000+ columns).

### Standard vs Flex Execution

| Metric             | Standard       | Flex           | Delta        |
|--------------------|----------------|----------------|--------------|
| Cost/DPU-hour      | $0.44          | $0.29          | -34%         |
| Start delay (P50)  | < 1 min        | 3 min          | +2 min       |
| Start delay (P99)  | < 2 min        | 18 min         | +16 min      |
| Preemption risk    | None           | None           | Same         |
| Availability       | Always         | 95%+ times     | Slightly less|
| Monthly cost (200 DPU, 4hr/day) | $10,560 | $6,960 | -$3,600/mo |

### Auto-Scaling vs Fixed Capacity

Workload: Multi-stage pipeline (ingest → transform → aggregate → write)

| Config                  | DPU-hours | Duration | Cost  | Efficiency |
|-------------------------|-----------|----------|-------|------------|
| Fixed 200 workers       | 800       | 4.0 hr   | $352  | 45%        |
| Fixed 100 workers       | 600       | 6.0 hr   | $264  | 52%        |
| Auto-scale (max 200)    | 480       | 4.2 hr   | $211  | 72%        |
| Auto-scale (max 300)    | 450       | 3.5 hr   | $198  | 78%        |

**Finding**: Auto-scaling with generous max achieves best cost-efficiency
for multi-stage workloads where each stage has different parallelism needs.

### Compression Codec Comparison

Dataset: 10B records, 12 TB raw, written to Parquet

| Codec    | Write Time | Read Time | File Size | Ratio | CPU Cost |
|----------|------------|-----------|-----------|-------|----------|
| None     | 45 min     | 35 min    | 4.2 TB    | 2.9x  | Low      |
| Snappy   | 50 min     | 38 min    | 2.1 TB    | 5.7x  | Low      |
| ZSTD     | 65 min     | 40 min    | 1.5 TB    | 8.0x  | Medium   |
| GZIP     | 95 min     | 55 min    | 1.4 TB    | 8.6x  | High     |
| LZ4      | 48 min     | 36 min    | 2.3 TB    | 5.2x  | Lowest   |

**Recommendation**: ZSTD for cold/warm data (best ratio), Snappy for hot data
(fast read), LZ4 for intermediate shuffle data.

### Partition Strategy Impact

Query pattern: Filter by date + region, aggregate by customer

| Strategy                          | Query Time | Storage  | Notes            |
|-----------------------------------|------------|----------|------------------|
| No partitioning                   | 45 min     | 2.1 TB   | Full scan        |
| Partition by date                 | 8 min      | 2.1 TB   | 1/365 scan       |
| Partition by date + region        | 2 min      | 2.2 TB   | 1/3650 scan      |
| Partition by date + region + hour | 1.5 min    | 2.8 TB   | Too many parts   |
| Partition by date, bucket by customer | 1.2 min | 2.2 TB  | Best balance     |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7. Cost Optimization Strategies

### Strategy Matrix

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COST OPTIMIZATION LEVERS                          │
├─────────────────────┬──────────────┬────────────────────────────────┤
│ Strategy            │ Savings      │ Trade-off                      │
├─────────────────────┼──────────────┼────────────────────────────────┤
│ Flex execution      │ 34%          │ Start delay up to 20 min       │
│ Auto-scaling        │ 20-40%       │ Slightly longer total duration │
│ Right-size workers  │ 15-30%       │ Requires benchmarking          │
│ Incremental loads   │ 50-90%       │ Complex CDC logic              │
│ Column pruning      │ 10-60%       │ Must know access patterns      │
│ Compression (ZSTD)  │ 15-25%       │ Slightly more CPU              │
│ Job consolidation   │ 10-20%       │ Blast radius increases         │
│ Off-peak scheduling │ 0% (Glue)    │ N/A (no time-of-day pricing)  │
│ Data tiering        │ 30-50%       │ Requires lifecycle policies    │
└─────────────────────┴──────────────┴────────────────────────────────┘
```

### Flex Execution Tier Assignment

```python
# Job classification for Standard vs Flex
JOB_TIERS = {
    "tier1_sla": {
        "execution_class": "STANDARD",
        "description": "Must complete by 06:00, feeds real-time dashboards",
        "jobs": ["txn_processing", "fraud_scoring", "balance_updates"]
    },
    "tier2_important": {
        "execution_class": "STANDARD",
        "description": "Should complete by 08:00, feeds morning reports",
        "jobs": ["daily_aggregates", "customer_metrics"]
    },
    "tier3_batch": {
        "execution_class": "FLEX",
        "description": "Complete within 24 hours, historical reprocessing",
        "jobs": ["backfill_*", "ml_training_features", "archive_compaction"]
    }
}
# Tier 3 saves: 100 DPU × 4hr × 30 days × ($0.44-$0.29) = $1,800/month
```

### Incremental Processing vs Full Scan

```python
# Full scan approach: Read all 12 TB daily
# Cost: 200 workers × 4 hours = $352/day = $10,560/month

# Incremental approach: Read only new/changed data (CDC)
def get_incremental_data(table, last_watermark):
    return glueContext.create_dynamic_frame.from_catalog(
        database="prod",
        table_name=table,
        push_down_predicate=f"modified_at > '{last_watermark}'"
    )

# Typical daily change rate: 5-10% of total data
# Cost: 200 workers × 0.5 hours = $44/day = $1,320/month
# Savings: 87%
```

### Monthly Budget Breakdown (Optimized)

```
Target: $50,000/month budget

Tier 1 (Standard, daily, SLA):
  5 jobs × 100 G.2X workers × 2 hr × 30 days × $0.44 = $13,200

Tier 2 (Standard, daily, important):
  10 jobs × 50 G.1X workers × 1.5 hr × 30 days × $0.44 = $9,900

Tier 3 (Flex, weekly, batch):
  20 jobs × 80 G.1X workers × 3 hr × 4 weeks × $0.29 = $5,568

Development & testing:
  Ad-hoc × ~$2,000

Total: ~$30,668/month (39% under budget)

Unoptimized estimate: $85,000/month
Savings from optimization: 64%
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8. Common Performance Anti-Patterns

### Anti-Pattern 1: collect() on Large Datasets

```python
# BAD: Pulls entire dataset to driver memory — OOM crash
all_data = df.collect()  # 10B rows → driver dies
for row in all_data:
    process(row)

# GOOD: Use distributed operations
result = df.groupBy("category").agg(F.sum("amount").alias("total"))
result.write.parquet("s3://output/")
```

### Anti-Pattern 2: Python UDFs Instead of Built-in Functions

```python
# BAD: Python UDF — serializes data to Python, 10-100x slower
from pyspark.sql.types import StringType

@udf(StringType())
def classify_amount(amount):
    if amount > 10000: return "high"
    elif amount > 1000: return "medium"
    else: return "low"

df = df.withColumn("tier", classify_amount(col("amount")))

# GOOD: Native Spark expression — runs in JVM, vectorized
df = df.withColumn("tier",
    F.when(F.col("amount") > 10000, "high")
     .when(F.col("amount") > 1000, "medium")
     .otherwise("low")
)
# 50x faster for this operation
```

### Anti-Pattern 3: Wrong Partition Column Choice

```python
# BAD: Partition by high-cardinality column
df.write.partitionBy("transaction_id").parquet(...)  # 10B partitions!

# BAD: Partition by skewed column
df.write.partitionBy("merchant_id").parquet(...)  # One partition = 40% of data

# GOOD: Partition by date (bounded cardinality, even distribution)
df.write.partitionBy("transaction_date", "region").parquet(...)
# ~3,650 partitions/year (365 days × 10 regions), each roughly equal
```

### Anti-Pattern 4: Unbounded Shuffles

```python
# BAD: Default 200 shuffle partitions for 500 GB dataset
# Each partition = 2.5 GB → executor OOM
spark.conf.get("spark.sql.shuffle.partitions")  # "200" (default!)

df.groupBy("customer_id").agg(...)  # Shuffles 500 GB into 200 partitions

# GOOD: Size partitions to 128-256 MB
spark.conf.set("spark.sql.shuffle.partitions", "2500")  # 500GB/200MB = 2500
```

### Anti-Pattern 5: Cross-Joins (Cartesian Products)

```python
# BAD: Accidental cross-join from missing join condition
result = df_a.join(df_b)  # 1M × 1M = 1 TRILLION rows

# BAD: Disguised cross-join
result = df_a.join(df_b, df_a.col1 != df_b.col1)  # Non-equi without bound

# GOOD: Always use equi-join conditions
result = df_a.join(df_b, df_a.key == df_b.key, "inner")
```

### Anti-Pattern 6: Too Many Small Jobs

```python
# BAD: 100 separate Glue jobs for 100 tables, each with 10 workers
# Cold-start overhead: 100 × 2 min = 200 min wasted
# Total DPU overhead: 100 × 1 driver DPU = 100 DPUs just for drivers

# GOOD: Consolidate related tables into fewer jobs with internal parallelism
from concurrent.futures import ThreadPoolExecutor

tables = ["table_1", "table_2", ..., "table_100"]

def process_table(table_name):
    df = spark.read.parquet(f"s3://raw/{table_name}/date={processing_date}/")
    transformed = transform(df)
    transformed.write.parquet(f"s3://processed/{table_name}/date={processing_date}/")

# Process 10 tables concurrently within one Glue job
with ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(process_table, tables)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9. Production Tuning Playbook

### Step-by-Step Optimization Workflow

```
┌──────────────────────────────────────────────────────────────────┐
│              PERFORMANCE TUNING DECISION TREE                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. PROFILE → Spark UI / CloudWatch Metrics                      │
│       │                                                          │
│       ▼                                                          │
│  2. IDENTIFY BOTTLENECK                                          │
│       │                                                          │
│       ├─── Shuffle heavy? ──→ Reduce partitions, broadcast,     │
│       │                        bucketing, AQE                    │
│       │                                                          │
│       ├─── I/O bound? ────→ Column prune, partition prune,      │
│       │                      groupFiles, compression             │
│       │                                                          │
│       ├─── Compute bound? ─→ More workers, larger worker type,  │
│       │                       eliminate UDFs                      │
│       │                                                          │
│       ├─── Memory (GC)? ──→ G.2X/Z.2X workers, tune GC,        │
│       │                      reduce cache, fewer partitions      │
│       │                                                          │
│       └─── Skew? ─────────→ Salting, AQE skew join,            │
│                              repartition by hash                  │
│                                                                  │
│  3. APPLY FIX (one change at a time)                             │
│       │                                                          │
│       ▼                                                          │
│  4. VERIFY (compare Spark UI stage times)                        │
│       │                                                          │
│       ▼                                                          │
│  5. DOCUMENT (update job parameters, commit to IaC)              │
└──────────────────────────────────────────────────────────────────┘
```

### Key Spark UI Metrics to Monitor

| Metric                        | Healthy Range    | Action if Exceeded        |
|-------------------------------|------------------|---------------------------|
| GC time / task time           | < 10%            | Increase memory or workers|
| Shuffle read/write            | < 2x input size  | Reduce shuffle partitions |
| Task duration skew (max/median)| < 3x            | Salt keys or AQE          |
| Spill to disk                 | 0 bytes          | More memory per executor  |
| Peak execution memory         | < 70% of alloc   | Right-sized               |
| Scheduler delay               | < 100ms          | Fewer tasks or more slots |

### Optimization Checklist

```
□ Enable AQE (spark.sql.adaptive.enabled=true)
□ Set shuffle partitions = data_size_mb / 200
□ Enable groupFiles for small file sources
□ Use push_down_predicate for partition pruning
□ Broadcast dimension tables < 500 MB
□ Use ZSTD compression for output
□ Avoid Python UDFs (use native expressions)
□ Set maxRecordsPerFile to prevent huge output files
□ Enable auto-scaling for variable workloads
□ Sort within partitions for downstream predicate pushdown
□ Use Glue 4.0+ for AQE and latest Spark optimizations
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 10. Real Benchmark Case Studies

### Case Study 1: High-Volume Simple Transforms (10B Records)

**Workload**: Read 10B transaction records (12 TB Parquet), apply 5 column
transformations, filter invalid records (2%), write partitioned output.

| Configuration                    | Before       | After        | Improvement |
|----------------------------------|--------------|--------------|-------------|
| Worker type                      | G.1X × 200   | G.1X × 150   | -25% cost   |
| Shuffle partitions               | 200 (default)| 4000          | -60% time   |
| File grouping                    | Disabled     | 256 MB groups | -40% time   |
| Compression                      | Snappy       | ZSTD          | -30% storage|
| Auto-scaling                     | Disabled     | Enabled       | -35% cost   |
| **Total duration**               | **6.5 hours**| **2.1 hours** | **3.1x**    |
| **Total cost**                   | **$572**     | **$185**      | **3.1x**    |

Key insight: The default 200 shuffle partitions created 60 GB partitions that
spilled to disk. Increasing to 4000 eliminated all spill. File grouping reduced
task scheduling overhead from 15 min to 20 seconds.

### Case Study 2: Complex Joins with Skew (1B × 500M)

**Workload**: Join 1B fact records with 500M dimension records on customer_id.
Top 0.1% of customers have 50% of transactions (extreme skew).

| Configuration                    | Before       | After        | Improvement |
|----------------------------------|--------------|--------------|-------------|
| Worker type                      | G.2X × 100   | G.2X × 80    | -20% cost   |
| Join strategy                    | Sort-merge   | Salted + AQE | -75% time   |
| Skew handling                    | None         | Salt factor=20| -80% skew   |
| Broadcast threshold              | 10 MB        | 500 MB       | -50% shuffle|
| AQE skew join                    | Disabled     | Enabled       | Auto-split  |
| **Total duration**               | **4.2 hours**| **55 min**   | **4.6x**    |
| **Total cost**                   | **$370**     | **$103**     | **3.6x**    |
| **Max executor time**            | 3.8 hours    | 52 min       | Even distrib|

Key insight: Without skew handling, one executor processed 500M records while
others processed 5M each. The slowest executor determined total job time.
AQE + salting distributed work evenly across all executors.

### Case Study 3: ML Feature Computation (Wide Tables, 1000+ Columns)

**Workload**: Compute 1,200 features from 800M customer records. Features include
window functions (rolling 30/60/90 day), cross-joins for feature interactions,
and heavy aggregations.

| Configuration                    | Before       | After        | Improvement |
|----------------------------------|--------------|--------------|-------------|
| Worker type                      | G.2X × 150   | G.4X × 60    | Better mem  |
| Computation strategy             | Single pass  | Staged (3)   | -40% memory |
| Window functions                 | 1200 at once | Batches of 50| No OOM      |
| Intermediate caching             | None         | Disk persist  | -60% recomp |
| Output format                    | Parquet      | Parquet+ZSTD | -45% size   |
| GC tuning                        | Default      | G1GC tuned   | -30% GC     |
| **Total duration**               | **OOM fail** | **2.8 hours** | Runs!       |
| **Total cost**                   | N/A (failed) | **$295**     | Achievable  |
| **Peak memory/executor**         | >64 GB (OOM) | 48 GB        | Within limit|

Key insight: Wide tables with 1000+ columns exhaust executor memory during
shuffles. Splitting into 3 stages (base features → window features → interactions)
with disk-level caching between stages keeps memory bounded. G.4X workers provide
the 64 GB needed for wide-row shuffles.

```python
# Staged feature computation pattern
base_features = compute_base_features(df)  # 400 columns
base_features.persist(StorageLevel.DISK_ONLY)
base_features.count()  # Force materialization

window_features = compute_window_features(base_features)  # +400 columns
window_features.persist(StorageLevel.DISK_ONLY)
window_features.count()

interaction_features = compute_interactions(window_features)  # +400 columns
interaction_features.write.parquet(output_path)

# Unpersist in reverse order
window_features.unpersist()
base_features.unpersist()
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Summary: Key Takeaways

1. **Default Spark settings are wrong for Glue at scale** — always tune shuffle
   partitions, enable AQE, and configure memory explicitly.

2. **Data skew is the #1 performance killer** — identify it early via Spark UI
   task duration distribution, fix with AQE or salting.

3. **Small files waste 20-40% of job time** on scheduling overhead — use groupFiles
   or run compaction jobs.

4. **Flex execution saves 34%** with minimal risk for non-SLA workloads.

5. **Auto-scaling + right-sized workers** together deliver 50-70% cost savings
   versus fixed over-provisioned clusters.

6. **Profile before optimizing** — the bottleneck is rarely where you think it is.
   Always check Spark UI stage breakdown first.

7. **Incremental processing** (CDC) is the single largest cost optimization,
   reducing data volumes by 90%+ for most workloads.
