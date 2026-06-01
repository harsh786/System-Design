# Category 2: Shuffle & Network Issues (Issues 11-20)

> Shuffle is the #1 performance bottleneck in distributed Spark. At 10TB+ scale, shuffle misconfigurations cause 50%+ of performance degradation.

---

## Issue #11: Shuffle Fetch Failed Exception

**Frequency**: Very High  
**Severity**: Critical - stage retry, potential job failure  
**Spark Component**: ShuffleBlockFetcherIterator, External Shuffle Service

### Symptoms
```
org.apache.spark.shuffle.FetchFailedException: 
  Failed to connect to host1:7337
  Connection refused / Connection reset by peer
  
WARN TaskSetManager: Lost task 12.3 in stage 5.0
  FetchFailed(BlockManagerId(3, host2, 7337), shuffleId=2, mapId=45, reduceId=12)

Stage 5 (retry 3) failed: org.apache.spark.shuffle.FetchFailedException
```

### Root Cause
- Executor that produced shuffle data was lost (OOM, preemption, spot termination)
- Network timeout between executors during fetch
- External Shuffle Service (ESS) overloaded or crashed
- Shuffle files corrupted or deleted (disk full, cleanup race)
- Too many concurrent connections saturating network

### Solution
```python
# 1. Enable External Shuffle Service (survive executor loss)
spark.conf.set("spark.shuffle.service.enabled", "true")
spark.conf.set("spark.shuffle.service.port", "7337")

# 2. Increase retry attempts and wait time
spark.conf.set("spark.shuffle.io.maxRetries", "10")       # Default 3
spark.conf.set("spark.shuffle.io.retryWait", "30s")       # Default 5s
spark.conf.set("spark.shuffle.io.connectionTimeout", "240s")

# 3. Increase network timeouts
spark.conf.set("spark.network.timeout", "600s")            # Default 120s
spark.conf.set("spark.shuffle.registration.timeout", "120s")

# 4. Reduce concurrent shuffle connections to avoid overwhelming
spark.conf.set("spark.reducer.maxSizeInFlight", "96m")     # Default 48m
spark.conf.set("spark.shuffle.io.numConnectionsPerPeer", "3")  # Default 1

# 5. Increase stage retry attempts
spark.conf.set("spark.stage.maxConsecutiveAttempts", "10")
spark.conf.set("spark.task.maxFailures", "8")              # Default 4

# 6. For spot instances: enable decommissioning
spark.conf.set("spark.decommission.enabled", "true")
spark.conf.set("spark.storage.decommission.shuffleBlocks.enabled", "true")
spark.conf.set("spark.storage.decommission.shuffleBlocks.maxThreads", "8")
```

### Architecture Fix
```
Before (fragile):
Executor A (produces shuffle) → dies → Executor B can't fetch → FAIL

After (resilient):
Executor A (produces shuffle) → External Shuffle Service stores blocks
Executor A dies → Executor B fetches from ESS → SUCCESS
```

---

## Issue #12: Shuffle Write Overwhelming Local Disk

**Frequency**: Medium-High  
**Severity**: High - disk full → cascading failures  
**Spark Component**: SortShuffleWriter, IndexShuffleBlockResolver

### Symptoms
```
java.io.IOException: No space left on device
  at org.apache.spark.shuffle.sort.SortShuffleWriter
# OR
Executor 7: local dir /mnt/spark/blockmgr-xxx is full
# OR severe I/O wait: CPU idle but tasks not progressing
```

### Root Cause
- Shuffle writes exceed local disk capacity
- Multiple executors sharing same disk
- No disk monitoring / no multi-disk configuration
- Shuffle compression disabled or ineffective

### Solution
```python
# 1. Use multiple local disks (stripe across NVMe)
# spark-defaults.conf:
# spark.local.dir=/mnt/nvme1/spark,/mnt/nvme2/spark,/mnt/nvme3/spark
# Spark round-robins across directories

# 2. Enable and optimize shuffle compression
spark.conf.set("spark.shuffle.compress", "true")
spark.conf.set("spark.shuffle.spill.compress", "true")
spark.conf.set("spark.io.compression.codec", "zstd")
spark.conf.set("spark.io.compression.zstd.level", "1")  # Fast compression

# 3. Reduce shuffle data volume
# Filter early, project only needed columns
df_filtered = df.select("key", "value").filter(F.col("date") == "2024-01-01")
result = df_filtered.groupBy("key").count()  # Much less shuffle data

# 4. Limit executors per node to control disk pressure
# 2 executors per node with 16 cores each (instead of 4 executors with 8 cores)
spark.conf.set("spark.executor.cores", "8")
spark.conf.set("spark.executor.instances", "2")  # per node

# 5. Clean up old shuffle files
spark.conf.set("spark.cleaner.periodicGC.interval", "15min")
spark.conf.set("spark.shuffle.service.removeShuffle", "true")

# 6. Monitor disk usage (Prometheus node_exporter)
# Alert: node_filesystem_avail_bytes{mountpoint="/mnt/spark"} < 20GB
```

---

## Issue #13: Shuffle Data Skew (One Reduce Task Takes 100x Longer)

**Frequency**: Very High  
**Severity**: High - massive stragglers  
**Spark Component**: ShuffleExchangeExec, AQE SkewJoin

### Symptoms
```
# From Spark UI - Stage Summary:
Duration (max): 45 min
Duration (median): 30 sec
Duration (min): 10 sec
# One or few tasks have 100x more shuffle read than others

# Shuffle Read Size distribution:
Task 0: 50 MB
Task 1: 55 MB
Task 423: 85 GB  ← SKEWED!
Task 999: 60 MB
```

### Root Cause
- Hot keys: one key has millions of records (e.g., null, "unknown", popular user)
- Temporal skew: most data in recent partition
- Join skew: one side has key explosion
- groupBy with power-law distribution (Zipf)

### Solution
```python
# 1. Enable AQE skew handling (Spark 3.0+)
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256MB")

# 2. Salting technique for joins
import pyspark.sql.functions as F

salt_factor = 10

# Salt the skewed (large) side
df_large_salted = df_large.withColumn("salt", F.floor(F.rand() * salt_factor))
df_large_salted = df_large_salted.withColumn(
    "join_key", F.concat(F.col("key"), F.lit("_"), F.col("salt"))
)

# Explode the small side to match all salts
df_small_exploded = df_small.crossJoin(
    spark.range(salt_factor).withColumnRenamed("id", "salt")
).withColumn("join_key", F.concat(F.col("key"), F.lit("_"), F.col("salt")))

# Join on salted key (evenly distributed)
result = df_large_salted.join(df_small_exploded, "join_key")

# 3. Isolate and handle hot keys separately
hot_keys = ["null", "unknown", "N/A"]

df_hot = df.filter(F.col("key").isin(hot_keys))
df_normal = df.filter(~F.col("key").isin(hot_keys))

# Process separately and union
result_normal = df_normal.join(dim, "key")
result_hot = df_hot.crossJoin(dim.filter(F.col("key").isin(hot_keys)))
result = result_normal.unionAll(result_hot)

# 4. Repartition by composite key to spread hot keys
df = df.repartition(2000, F.col("key"), F.col("sub_key"))
```

---

## Issue #14: Network Bandwidth Saturation During Shuffle

**Frequency**: Medium  
**Severity**: High - all jobs slow simultaneously  
**Spark Component**: NettyBlockTransferService, TransportClient

### Symptoms
```
# All tasks show high "Shuffle Read Blocked Time"
# Network utilization at 100% (10Gbps saturated)
# Multiple jobs competing for network bandwidth
# Tasks timing out waiting for shuffle data
```

### Root Cause
- All-to-all shuffle pattern across the cluster
- Multiple jobs running large shuffles concurrently
- Insufficient network bandwidth for data volume
- No network isolation between shuffle and other traffic

### Solution
```python
# 1. Reduce shuffle data volume (most impactful)
# Push down filters and projections before shuffle
df = df.select("key", "value")  # Only shuffle needed columns
df = df.filter(F.col("date") >= "2024-01-01")  # Filter before join

# 2. Use broadcast join to eliminate shuffle entirely
from pyspark.sql.functions import broadcast
# If one side < 1GB, broadcast it
result = large_df.join(broadcast(small_df), "key")

# 3. Enable compression to reduce network bytes
spark.conf.set("spark.shuffle.compress", "true")
spark.conf.set("spark.io.compression.codec", "zstd")

# 4. Reduce concurrent shuffle fetch to avoid saturation
spark.conf.set("spark.reducer.maxSizeInFlight", "48m")  # Reduce from 96m
spark.conf.set("spark.shuffle.io.numConnectionsPerPeer", "1")

# 5. Co-locate shuffle data (bucket tables)
# Pre-bucket both tables on join key → NO SHUFFLE needed
df.write.bucketBy(1000, "key").sortBy("key").saveAsTable("bucketed_table")

# 6. Cluster topology awareness
spark.conf.set("spark.locality.wait", "10s")  # Try rack-local before any
spark.conf.set("spark.locality.wait.rack", "5s")

# 7. Network-level: separate shuffle traffic
# Use dedicated NICs or VLANs for shuffle traffic
# AWS: Use placement groups for co-located instances
```

---

## Issue #15: External Shuffle Service Crashes Under Load

**Frequency**: Medium  
**Severity**: Critical - affects all executors on that node  
**Spark Component**: ExternalShuffleService (ESS)

### Symptoms
```
ERROR ExternalShuffleBlockHandler: Error opening block
java.io.FileNotFoundException: /mnt/spark/blockmgr-xxx/shuffle_2_45_0.data
# OR
Connection refused to shuffle service on host7:7337
# OR ESS process OOM
```

### Root Cause
- ESS process has fixed memory but serves all executors on the node
- File descriptor exhaustion (too many open shuffle files)
- ESS OOM when tracking too many blocks
- Disk failures underneath ESS

### Solution
```python
# 1. Increase ESS memory (in spark-env.sh on each node)
# SPARK_DAEMON_MEMORY=4g  (default is usually 1g)

# 2. Increase file descriptor limits
# /etc/security/limits.conf:
# spark soft nofile 1000000
# spark hard nofile 1000000

# 3. ESS configuration
spark.conf.set("spark.shuffle.service.port", "7337")
spark.conf.set("spark.shuffle.service.index.cache.size", "200m")

# 4. Enable shuffle block decommissioning (Spark 3.1+)
spark.conf.set("spark.decommission.enabled", "true")
spark.conf.set("spark.storage.decommission.shuffleBlocks.enabled", "true")

# 5. Kubernetes: Use separate shuffle service pods
# Deploy shuffle service as DaemonSet with dedicated resources:
# resources:
#   requests:
#     memory: "4Gi"
#     cpu: "2"
#   limits:
#     memory: "6Gi"

# 6. Monitor ESS health
# - Track open file descriptors: ls /proc/<ESS_PID>/fd | wc -l
# - Track memory: RSS of shuffle service process
# - Track disk I/O: iostat for shuffle directories
```

---

## Issue #16: Shuffle Hash Join Falls Back to Sort Merge (Unexpected Slowdown)

**Frequency**: Medium  
**Severity**: Medium - performance regression  
**Spark Component**: Catalyst Optimizer, JoinSelection

### Symptoms
```
# Expected: BroadcastHashJoin (fast, no shuffle)
# Got: SortMergeJoin (full shuffle of both sides)
# Query went from 2 minutes to 45 minutes overnight
# No code changes, but table grew past broadcast threshold
```

### Root Cause
- Table grew past `autoBroadcastJoinThreshold` (default 10MB)
- Table statistics are stale (not reflecting recent data loads)
- After filter pushdown, optimizer can't determine actual size
- CBO disabled or stats not collected

### Solution
```python
# 1. Update table statistics regularly
spark.sql("ANALYZE TABLE large_table COMPUTE STATISTICS")
spark.sql("ANALYZE TABLE large_table COMPUTE STATISTICS FOR ALL COLUMNS")

# 2. Use AQE for runtime join strategy selection
spark.conf.set("spark.sql.adaptive.enabled", "true")
# AQE will convert SortMergeJoin → BroadcastHashJoin at runtime
# if one side is actually small after filters

# 3. Force join strategy with hints
result = df_large.join(df_small.hint("broadcast"), "key")  # Force broadcast
result = df_large.join(df_medium.hint("merge"), "key")     # Force sort-merge
result = df_large.join(df_medium.hint("shuffle_hash"), "key")  # Force shuffle-hash

# 4. Adjust thresholds
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "100MB")  # Increase for larger dims

# 5. Check plan before execution
result.explain(mode="formatted")
# Look for: BroadcastHashJoin vs SortMergeJoin vs ShuffledHashJoin

# 6. For CI/CD: assert join strategy in tests
plan = result._jdf.queryExecution().executedPlan().toString()
assert "BroadcastHashJoin" in plan, f"Expected broadcast join but got: {plan}"
```

---

## Issue #17: Shuffle Partition Count Misconfiguration

**Frequency**: Very High (most common tuning issue)  
**Severity**: Medium-High  
**Spark Component**: ShuffleExchangeExec, AQE

### Symptoms
```
# Too few partitions (200 default):
- Each task processes 50GB → OOM or very slow
- 200 tasks but 2000 cores sitting idle
- Individual tasks take 30+ minutes

# Too many partitions (over-partitioned):
- 100,000 tasks each processing 1MB
- Scheduling overhead dominates (1ms data, 100ms scheduling)
- Thousands of small output files
- Driver OOM tracking 100K tasks
```

### Root Cause
- Default `spark.sql.shuffle.partitions=200` is almost never correct
- Static setting can't adapt to varying data volumes
- Different stages need different partition counts

### Solution
```python
# BEST: Use AQE (Spark 3.0+) for automatic sizing
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.initialPartitionNum", "4000")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")
# Start with many partitions, AQE coalesces to target size

# Manual calculation formula:
# shuffle_partitions = total_shuffle_data_size / target_partition_size
# Target: 128MB-256MB per partition
# Example: 2TB shuffle → 2000000MB / 128MB = ~16000 partitions

# For different stages, override per-query:
spark.conf.set("spark.sql.shuffle.partitions", "2000")
heavy_join = df1.join(df2, "key")  # Uses 2000 partitions

spark.conf.set("spark.sql.shuffle.partitions", "200")
light_agg = small_df.groupBy("key").count()  # Uses 200 partitions

# With AQE, just set high initial and let it optimize:
spark.conf.set("spark.sql.adaptive.coalescePartitions.initialPartitionNum", "8000")
spark.conf.set("spark.sql.adaptive.coalescePartitions.minPartitionSize", "64MB")
```

---

## Issue #18: Shuffle Service Port Conflicts in Multi-Tenant Clusters

**Frequency**: Low-Medium  
**Severity**: Medium - jobs fail to start or hang  
**Spark Component**: ExternalShuffleService, Configuration

### Symptoms
```
ERROR Utils: Failed to bind to port 7337
java.net.BindException: Address already in use
# OR
Multiple Spark versions competing for same shuffle service
# OR executors from app A reading shuffle from app B (data corruption!)
```

### Root Cause
- Multiple Spark applications using same shuffle service port
- Different Spark versions with incompatible shuffle protocols
- Docker/K8s port mapping conflicts
- Shuffle service not started or wrong version

### Solution
```python
# 1. Use unique ports per Spark version/cluster
spark.conf.set("spark.shuffle.service.port", "7337")  # Spark 3.x
# Other cluster uses 7338 for Spark 2.x

# 2. In Kubernetes: each app gets its own shuffle service via DaemonSet
# Label-based selection:
# spark.kubernetes.executor.label.spark-version=3.4
# DaemonSet selector matches version labels

# 3. Verify shuffle service compatibility
spark.conf.set("spark.shuffle.service.fetch.rdd.enabled", "true")
spark.conf.set("spark.shuffle.registration.timeout", "60s")
spark.conf.set("spark.shuffle.registration.maxAttempts", "5")

# 4. For multi-version clusters: run separate shuffle services
# Port 7337: Spark 3.3 apps
# Port 7338: Spark 3.4 apps (protocol changes)
# Port 7339: Spark 3.5 apps

# 5. Health check shuffle service before job starts
# Pre-submit hook:
# nc -z $SHUFFLE_HOST $SHUFFLE_PORT || { echo "ESS not running!"; exit 1; }
```

---

## Issue #19: Shuffle Read Timeout During Large Stages

**Frequency**: Medium  
**Severity**: High - task/stage failure  
**Spark Component**: ShuffleBlockFetcherIterator, RetryingBlockFetcher

### Symptoms
```
org.apache.spark.shuffle.FetchFailedException: 
  java.util.concurrent.TimeoutException: 
  Timeout waiting response from host:port after 120000 ms
# Happens specifically on large stages (10000+ tasks)
# Shuffle service is alive but response is slow
```

### Root Cause
- Shuffle service overwhelmed with concurrent requests
- Network congestion during large all-to-all shuffle
- GC pause on source executor during fetch
- Slow disk I/O reading shuffle blocks

### Solution
```python
# 1. Increase timeouts (immediate fix)
spark.conf.set("spark.network.timeout", "800s")
spark.conf.set("spark.shuffle.io.connectionTimeout", "300s")
spark.conf.set("spark.shuffle.io.maxRetries", "10")
spark.conf.set("spark.shuffle.io.retryWait", "60s")

# 2. Limit concurrent fetch requests to reduce contention
spark.conf.set("spark.reducer.maxSizeInFlight", "48m")
spark.conf.set("spark.reducer.maxReqsInFlight", "5")  # Default Int.MAX

# 3. Enable batch fetch for smaller blocks
spark.conf.set("spark.shuffle.io.preferDirectBufs", "true")
spark.conf.set("spark.maxRemoteBlockSizeFetchToMem", "200m")

# 4. Use push-based shuffle (Spark 3.2+, LinkedIn's Magnet)
spark.conf.set("spark.shuffle.push.enabled", "true")
spark.conf.set("spark.shuffle.push.maxBlockSizeToPush", "64m")
spark.conf.set("spark.shuffle.push.maxBlockBatchSize", "8m")
# Merges shuffle blocks at destination → fewer fetch requests

# 5. Stagger shuffle reads with jitter
spark.conf.set("spark.shuffle.io.backLog", "128")  # Connection backlog
spark.conf.set("spark.shuffle.io.serverThreads", "8")  # More server threads
```

---

## Issue #20: Excessive Shuffle Data from Unnecessary Repartition

**Frequency**: High  
**Severity**: Medium - wasted resources  
**Spark Component**: Exchange (ShuffleExchangeExec)

### Symptoms
```
# From query plan:
Exchange hashpartitioning(key#1, 200)  ← UNNECESSARY!
+- Exchange hashpartitioning(key#1, 200)  ← Already partitioned by key!

# Spark UI shows redundant shuffle stage
# Stage N: Shuffle Write 500GB → Stage N+1: Shuffle Write 500GB (same data!)
```

### Root Cause
- Redundant `repartition()` calls in code
- Catalyst doesn't eliminate redundant exchanges with different partition counts
- Reading bucketed table but not leveraging bucketing
- Unnecessary repartition before write

### Solution
```python
# 1. Avoid unnecessary repartitions
# BAD:
df = df.repartition("key")      # Shuffle!
result = df.join(other, "key")  # Another shuffle!

# GOOD: Let the join do its own partitioning
result = df.join(other, "key")  # Single shuffle

# 2. Use coalesce instead of repartition to REDUCE partitions (no shuffle)
# BAD:
df.repartition(100)  # Full shuffle to 100 partitions!

# GOOD:
df.coalesce(100)  # No shuffle, just combines partitions (if reducing)

# 3. Leverage bucketing to avoid shuffle in joins
# Write both tables bucketed by join key:
df1.write.bucketBy(500, "key").sortBy("key").saveAsTable("t1_bucketed")
df2.write.bucketBy(500, "key").sortBy("key").saveAsTable("t2_bucketed")

# Join without shuffle!
spark.conf.set("spark.sql.sources.bucketing.enabled", "true")
spark.conf.set("spark.sql.sources.bucketing.autoBucketedScan.enabled", "true")
result = spark.table("t1_bucketed").join(spark.table("t2_bucketed"), "key")

# 4. Check plan for unnecessary exchanges
df.explain(mode="formatted")
# Look for consecutive Exchange nodes with same partition key

# 5. AQE can coalesce partitions post-shuffle
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
```

---

## Summary: Shuffle Issue Decision Tree

```
Shuffle-related problem
├── Job fails with FetchFailedException
│   ├── "Connection refused" → Issue #11 (executor lost, ESS down)
│   ├── "Timeout" → Issue #19 (network congestion, slow I/O)
│   └── "FileNotFoundException" → Issue #15 (ESS crash, disk full)
├── Job is slow but doesn't fail
│   ├── One task takes 100x longer → Issue #13 (data skew)
│   ├── All tasks slow equally → Issue #14 (network saturation)
│   ├── "Disk full" errors → Issue #12 (local disk exhaustion)
│   └── Query plan changed → Issue #16 (join strategy regression)
├── Configuration issues
│   ├── Too few/many partitions → Issue #17
│   ├── Port conflicts → Issue #18
│   └── Unnecessary shuffle stages → Issue #20
└── Quick wins
    ├── Enable AQE → Fixes #13, #16, #17
    ├── Enable ESS → Fixes #11
    ├── Broadcast small tables → Eliminates shuffle for #14
    └── Bucket tables → Eliminates shuffle for #20
```
