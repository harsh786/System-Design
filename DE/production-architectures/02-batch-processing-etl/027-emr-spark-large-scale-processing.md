# Large-Scale Data Processing on EMR: Petabyte Batch

## Architecture Diagram

```mermaid
graph TB
    subgraph "EMR Cluster"
        MASTER[Master Node<br/>r5.4xlarge<br/>YARN RM + Spark Driver]
        subgraph "Core Nodes (On-Demand)"
            CORE1[Core 1<br/>r5.4xlarge<br/>HDFS + YARN NM]
            CORE2[Core 2]
            CORE3[Core N<br/>10-20 nodes]
        end
        subgraph "Task Nodes (Spot)"
            TASK1[Task 1<br/>r5.4xlarge]
            TASK2[Task 2]
            TASK3[Task N<br/>30-100 nodes]
        end
    end

    subgraph "Instance Fleets"
        FLEET[Instance Fleet<br/>r5.4xl, r5a.4xl, r5d.4xl<br/>m5.4xl, m5a.4xl]
    end

    subgraph "Storage"
        S3IN[S3 Input<br/>Raw data (50TB/day)]
        S3OUT[S3 Output<br/>Processed data]
        EMRFS[EMRFS<br/>Consistent S3 access]
        HDFS[HDFS<br/>Intermediate/spill]
    end

    subgraph "Spark Application"
        DRIVER[Spark Driver<br/>DAG scheduling]
        EXEC1[Executor 1<br/>5 cores, 32GB]
        EXEC2[Executor 2]
        EXEC3[Executor N<br/>200-500 executors]
    end

    subgraph "Optimization"
        AQE[Adaptive Query Execution]
        DYN[Dynamic Allocation]
        SPEC[Speculative Execution]
        S3C[S3 Committers<br/>EMRFS / Magic]
    end

    subgraph "Monitoring"
        GANGLIA[Ganglia<br/>Cluster metrics]
        SPARK_UI[Spark UI<br/>Job/Stage/Task]
        CW[CloudWatch<br/>EMR metrics]
        HIST[History Server<br/>Post-mortem]
    end

    FLEET --> CORE1
    FLEET --> TASK1
    MASTER --> CORE1
    MASTER --> TASK1
    CORE1 --> HDFS
    S3IN --> EMRFS --> EXEC1
    EXEC1 --> EMRFS --> S3OUT
    DRIVER --> EXEC1
    DRIVER --> EXEC2
    DRIVER --> EXEC3
    AQE --> DRIVER
    DYN --> MASTER
    S3C --> EMRFS
```

## Problem Statement at Scale

Processing 50TB+ daily on EMR involves:
- **Cluster cost optimization**: $50K+/month for large-scale processing; spot savings critical
- **Spot interruptions**: 30-node task fleet losing 5 nodes mid-shuffle
- **S3 consistency**: Eventual consistency causing missing files in output
- **Shuffle explosion**: 10TB+ shuffles overwhelming disk and network
- **Small file problem**: 10M input files with 1MB average degrading performance
- **S3 throttling**: 5,500 GET/s per prefix limit causing task failures
- **Data skew**: One partition 100x larger than others, causing stragglers

Netflix, Spotify, and Airbnb process petabytes daily on EMR with these battle-tested patterns.

## Component Breakdown

### EMR Cluster Configuration

```json
{
  "Name": "daily-etl-production",
  "ReleaseLabel": "emr-7.0.0",
  "Applications": [
    {"Name": "Spark"},
    {"Name": "Hadoop"},
    {"Name": "Ganglia"}
  ],
  "Instances": {
    "InstanceFleets": [
      {
        "Name": "Master",
        "InstanceFleetType": "MASTER",
        "TargetOnDemandCapacity": 1,
        "InstanceTypeConfigs": [
          {"InstanceType": "r5.4xlarge", "WeightedCapacity": 1}
        ]
      },
      {
        "Name": "Core",
        "InstanceFleetType": "CORE",
        "TargetOnDemandCapacity": 20,
        "InstanceTypeConfigs": [
          {"InstanceType": "r5.4xlarge", "WeightedCapacity": 1, "BidPriceAsPercentageOfOnDemandPrice": 100},
          {"InstanceType": "r5a.4xlarge", "WeightedCapacity": 1},
          {"InstanceType": "r5d.4xlarge", "WeightedCapacity": 1},
          {"InstanceType": "m5.4xlarge", "WeightedCapacity": 1}
        ],
        "LaunchSpecifications": {
          "OnDemandSpecification": {"AllocationStrategy": "lowest-price"}
        }
      },
      {
        "Name": "Task",
        "InstanceFleetType": "TASK",
        "TargetSpotCapacity": 80,
        "TargetOnDemandCapacity": 0,
        "InstanceTypeConfigs": [
          {"InstanceType": "r5.4xlarge", "WeightedCapacity": 1, "BidPriceAsPercentageOfOnDemandPrice": 60},
          {"InstanceType": "r5a.4xlarge", "WeightedCapacity": 1, "BidPriceAsPercentageOfOnDemandPrice": 60},
          {"InstanceType": "r5d.4xlarge", "WeightedCapacity": 1, "BidPriceAsPercentageOfOnDemandPrice": 60},
          {"InstanceType": "m5.4xlarge", "WeightedCapacity": 1, "BidPriceAsPercentageOfOnDemandPrice": 60},
          {"InstanceType": "m5a.4xlarge", "WeightedCapacity": 1, "BidPriceAsPercentageOfOnDemandPrice": 60}
        ],
        "LaunchSpecifications": {
          "SpotSpecification": {
            "TimeoutDurationMinutes": 10,
            "TimeoutAction": "SWITCH_TO_ON_DEMAND",
            "AllocationStrategy": "capacity-optimized"
          }
        }
      }
    ],
    "Ec2SubnetIds": ["subnet-aaa", "subnet-bbb", "subnet-ccc"],
    "KeepJobFlowAliveWhenNoSteps": false
  },
  "ManagedScalingPolicy": {
    "ComputeLimits": {
      "UnitType": "InstanceFleetUnits",
      "MinimumCapacityUnits": 20,
      "MaximumCapacityUnits": 100,
      "MaximumOnDemandCapacityUnits": 20,
      "MaximumCoreCapacityUnits": 20
    }
  }
}
```

### Spark Configuration (50TB Daily Processing)

```properties
# spark-defaults.conf for 100-node cluster (r5.4xlarge: 16 vCPU, 128GB RAM)
spark.master=yarn
spark.submit.deployMode=cluster

# Executor sizing (maximize per-node, 2 executors per r5.4xlarge)
spark.executor.instances=200
spark.executor.cores=7
spark.executor.memory=52g
spark.executor.memoryOverhead=8g
spark.driver.memory=32g
spark.driver.cores=8

# Dynamic allocation
spark.dynamicAllocation.enabled=true
spark.dynamicAllocation.minExecutors=50
spark.dynamicAllocation.maxExecutors=500
spark.dynamicAllocation.executorIdleTimeout=60s
spark.dynamicAllocation.schedulerBacklogTimeout=5s

# Shuffle optimization
spark.sql.shuffle.partitions=2000
spark.sql.adaptive.enabled=true
spark.sql.adaptive.coalescePartitions.enabled=true
spark.sql.adaptive.coalescePartitions.minPartitionSize=64MB
spark.sql.adaptive.skewJoin.enabled=true
spark.sql.adaptive.skewJoin.skewedPartitionFactor=5
spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes=256MB

# Memory management
spark.memory.fraction=0.8
spark.memory.storageFraction=0.3
spark.sql.windowExec.buffer.spill.threshold=4096

# Shuffle service (survives executor loss)
spark.shuffle.service.enabled=true
spark.shuffle.registration.timeout=120s

# S3 optimization
spark.hadoop.fs.s3a.connection.maximum=200
spark.hadoop.fs.s3a.threads.max=100
spark.hadoop.fs.s3a.connection.establish.timeout=5000
spark.hadoop.fs.s3a.experimental.input.fadvise=random
spark.sql.parquet.mergeSchema=false
spark.sql.parquet.filterPushdown=true
spark.sql.hive.metastorePartitionPruning=true

# S3 committer (prevents partial output)
spark.sql.sources.commitProtocolClass=org.apache.spark.internal.io.cloud.PathOutputCommitProtocol
spark.sql.parquet.output.committer.class=org.apache.spark.internal.io.cloud.BindingParquetOutputCommitter
spark.hadoop.mapreduce.outputcommitter.factory.scheme.s3a=org.apache.hadoop.fs.s3a.commit.S3ACommitterFactory
spark.hadoop.fs.s3a.committer.name=magic
spark.hadoop.fs.s3a.committer.magic.enabled=true
```

## Partition Tuning

### Input Partitioning

```python
# Problem: 10M small files (1MB each) = 10M tasks = scheduling overhead
# Solution: Coalesce input splits

# Option 1: Configure split size
spark.conf.set("spark.sql.files.maxPartitionBytes", "256MB")  # Combine small files
spark.conf.set("spark.sql.files.openCostInBytes", "4MB")

# Option 2: Explicit repartition after read
raw_df = spark.read.parquet("s3://raw/events/dt=2024-01-15/")
# If 50,000 small files → coalesce to manageable number
optimized_df = raw_df.coalesce(500)  # 500 partitions for processing

# Option 3: Use Spark's input_file_name for monitoring
from pyspark.sql.functions import input_file_name
df_with_source = raw_df.withColumn("_source", input_file_name())
```

### Shuffle Partitioning

```python
# Rule of thumb: shuffle partitions = 2-3x executor cores for large data
# 200 executors x 7 cores = 1400 cores → 2000-4000 shuffle partitions

spark.conf.set("spark.sql.shuffle.partitions", "2000")

# With AQE (adaptive): start high, Spark coalesces automatically
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.shuffle.partitions", "5000")  # Start high
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.minPartitionSize", "64MB")
# AQE will reduce 5000 → actual needed based on data volume
```

### Output Partitioning

```python
# Target: 256MB-1GB output files for downstream tools
total_output_bytes = 5 * 1024**4  # 5TB output
target_file_bytes = 512 * 1024**2  # 512MB per file
output_partitions = total_output_bytes // target_file_bytes  # ~10,000 files

result_df.repartition(10000) \
    .write.mode("overwrite") \
    .parquet("s3://curated/events/dt=2024-01-15/")
```

## Shuffle Optimization

### Dealing with Data Skew

```python
# Detect skew: one partition has 100GB while others have 1GB
# AQE handles this automatically with Spark 3.0+

# Manual approach for extreme skew:
# Salt the skewed key
from pyspark.sql.functions import concat, lit, rand, floor

# Add salt to skewed join key
SALT_BUCKETS = 20
skewed_df = large_df.withColumn("salted_key", 
    concat(F.col("join_key"), lit("_"), (floor(rand() * SALT_BUCKETS)).cast("string"))
)

# Explode the small side to match all salts
from pyspark.sql.functions import explode, array
small_exploded = small_df.withColumn("salted_key",
    explode(array([concat(F.col("join_key"), lit(f"_{i}")) for i in range(SALT_BUCKETS)]))
)

# Join on salted key (evenly distributed)
result = skewed_df.join(small_exploded, "salted_key")
```

### Broadcast Join Optimization

```python
# Auto-broadcast threshold
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "100MB")

# Force broadcast for known-small tables
from pyspark.sql.functions import broadcast
result = large_df.join(broadcast(small_dim_df), "key")
# Eliminates shuffle entirely for the small side
```

## S3 Committers

### Problem: Output Consistency

```
Without proper committer:
1. Task writes to temp location in S3
2. Task completes → renames to final location
3. S3 rename = COPY + DELETE (not atomic!)
4. If driver crashes between step 2 and 3 → partial output
5. If multiple attempts → duplicate data
```

### EMRFS S3-optimized Committer

```properties
# EMR-specific optimized committer
spark.sql.parquet.output.committer.class=com.amazon.emr.committer.EmrOptimizedSparkSqlParquetOutputCommitter
spark.sql.hive.convertInsertingPartitionedTable=false

# Benefits:
# - No rename operations (direct write to final path)
# - Multipart upload with commit
# - Consistent output guaranteed
# - 50% faster write operations
```

### Magic Committer (S3A)

```properties
# Open-source alternative
spark.hadoop.fs.s3a.committer.name=magic
spark.hadoop.fs.s3a.committer.magic.enabled=true

# How it works:
# 1. Tasks write to __magic/ directory with multipart uploads
# 2. Uploads are NOT completed (pending)
# 3. On task commit → complete the multipart uploads
# 4. On task abort → abort multipart uploads
# Result: atomic output appearance
```

## Spill Management

```properties
# When shuffle data exceeds memory → spill to disk
# Configure local storage for spill (use NVMe if available)

# For r5d instances (NVMe local storage):
spark.local.dir=/mnt/nvme0,/mnt/nvme1

# For EBS-backed instances:
spark.local.dir=/mnt/ebs1,/mnt/ebs2

# Spill thresholds
spark.shuffle.spill.numElementsForceSpillThreshold=100000000
spark.memory.fraction=0.8
spark.memory.storageFraction=0.3

# Monitor spill in Spark UI:
# Stage details → "Shuffle Spill (Memory)" and "Shuffle Spill (Disk)"
# If Disk spill >> Memory: need more executor memory or more partitions
```

## Scaling Strategies

### Managed Scaling (EMR 5.30+)

```json
{
  "ManagedScalingPolicy": {
    "ComputeLimits": {
      "UnitType": "InstanceFleetUnits",
      "MinimumCapacityUnits": 20,
      "MaximumCapacityUnits": 150,
      "MaximumOnDemandCapacityUnits": 20,
      "MaximumCoreCapacityUnits": 20
    }
  }
}
// EMR monitors YARN metrics and scales task fleet automatically
// Scale-up: <60s when pending containers detected
// Scale-down: Graceful decommission after idle timeout
```

### Multi-step Pipeline on Single Cluster

```python
# Submit multiple steps to maximize cluster utilization
steps = [
    {
        "Name": "Step 1 - Extract Orders",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": ["spark-submit", "--deploy-mode", "cluster",
                     "--conf", "spark.dynamicAllocation.maxExecutors=200",
                     "s3://code/extract_orders.py", "--date", "2024-01-15"]
        },
        "ActionOnFailure": "CONTINUE"
    },
    {
        "Name": "Step 2 - Extract Customers",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": ["spark-submit", "--deploy-mode", "cluster",
                     "s3://code/extract_customers.py", "--date", "2024-01-15"]
        },
        "ActionOnFailure": "CONTINUE"
    },
    {
        "Name": "Step 3 - Join and Aggregate (depends on 1+2)",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": ["spark-submit", "--deploy-mode", "cluster",
                     "--conf", "spark.dynamicAllocation.maxExecutors=400",
                     "s3://code/aggregate.py", "--date", "2024-01-15"]
        },
        "ActionOnFailure": "TERMINATE_CLUSTER"
    }
]
```

## Failure Handling

### Spot Interruption Handling

```properties
# Core nodes = On-Demand (store HDFS shuffle data)
# Task nodes = Spot (compute only, shuffle via external shuffle service)

# External shuffle service on core nodes survives task node loss
spark.shuffle.service.enabled=true

# Decommissioning timeout for graceful spot removal
yarn.resourcemanager.nodemanager-graceful-decommission-timeout-secs=3600

# Node labels to separate critical vs spot workloads
spark.yarn.executor.nodeLabelExpression=TASK  # Executors on task fleet
# Driver always on core/master nodes
```

### S3 Throttling Mitigation

```python
# S3 limit: 5,500 GET/s and 3,500 PUT/s per prefix

# Strategy 1: Distribute across prefixes (hash-based layout)
# Bad:  s3://bucket/events/dt=2024-01-15/  (all files under one prefix)
# Good: s3://bucket/events/h=0a/dt=2024-01-15/
#        s3://bucket/events/h=0b/dt=2024-01-15/
#        ... (16+ prefixes)

# Strategy 2: S3 request retries
spark.conf.set("spark.hadoop.fs.s3a.retry.limit", "20")
spark.conf.set("spark.hadoop.fs.s3a.retry.interval", "500ms")

# Strategy 3: Rate limiting reads
spark.conf.set("spark.hadoop.fs.s3a.connection.maximum", "100")  # Per-node limit
```

## Cost Optimization

### Cost Model (50TB Daily Processing)

| Component | Configuration | Monthly Cost |
|-----------|--------------|-------------|
| Master (On-Demand) | 1x r5.4xlarge, 8hr/day | $490 |
| Core (On-Demand) | 20x r5.4xlarge, 8hr/day | $9,800 |
| Task (Spot, 60% discount) | 80x r5.4xlarge, 6hr/day | $11,800 |
| EBS (Core HDFS) | 20x 1TB gp3 | $1,600 |
| S3 storage (input+output) | 50TB processed/day | $1,150 |
| S3 requests | ~500M requests/mo | $250 |
| **Monthly Total** | | **~$25,090** |

### vs. On-Demand Only

| Configuration | Monthly Cost | Savings |
|--------------|-------------|---------|
| All On-Demand (100 nodes, 8hr) | $49,000 | Baseline |
| Core OD + Task Spot | $25,000 | 49% |
| + Managed Scaling (avg 60 nodes) | $18,000 | 63% |
| + Reserved core nodes | $14,000 | 71% |

## Real-World Companies

| Company | Scale | Configuration |
|---------|-------|--------------|
| Netflix | 1.5PB/day | 1000s of EMR clusters, auto-scaled |
| Spotify | 100s of TB/day | EMR + managed scaling |
| Airbnb | 50TB/day | EMR with custom scheduler |
| Yelp | Multi-TB | EMR Spark for ETL + ML |
| Samsung | 100TB+ | EMR for IoT data processing |
| Expedia | PB-scale | Large EMR fleets for travel data |

## Anti-Patterns

1. **All Spot for core nodes** - Losing HDFS means losing shuffle data = full restart
2. **Single AZ deployment** - Capacity crunch in one AZ means no spot instances
3. **Too few shuffle partitions** - OOM on large shuffles; use AQE
4. **Ignoring S3 committers** - Partial/duplicate output on failures
5. **Not using instance fleets** - Single instance type = higher spot interruption
6. **Oversized executors** - GC pauses with 100GB+ heaps; keep < 64GB
7. **No monitoring of skew** - One task taking 10x longer than others = wasted cluster time
