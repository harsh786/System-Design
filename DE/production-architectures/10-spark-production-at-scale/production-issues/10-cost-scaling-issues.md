# Category 10: Cost & Scaling Issues (Issues 91-100)

> At $50K-$500K/month Spark infrastructure costs, even 10% optimization saves six figures annually. Scaling decisions have direct P&L impact.

---

## Issue #91: Over-Provisioned Executors (Paying for Idle Compute)

**Frequency**: Very High  
**Severity**: High - 30-50% waste in most clusters  
**Spark Component**: Resource Allocation, Dynamic Allocation

### Symptoms
```
# Average CPU utilization: 15-25% across cluster
# Executors allocated but most cores idle
# Memory allocated: 80% of cluster total
# Memory USED: 30% of allocated
# Cost: paying for 4x what we actually use
```

### Root Cause
- Fixed allocation based on peak needs (running 24/7 at peak capacity)
- Developers request max resources "just in case"
- No right-sizing feedback loop
- Memory over-allocated to avoid OOM (3x actual need)
- Cores over-allocated (not all tasks are CPU-bound)

### Solution
```python
# 1. Right-size based on actual metrics
# Analyze last 30 days:
# actual_peak_memory = max(executor_memory_used) across all tasks
# actual_cores_used = avg(active_tasks / allocated_cores)

# If peak memory = 6GB but allocated 16GB → reduce to 8GB (with buffer)
spark.conf.set("spark.executor.memory", "8g")  # Was 16g
spark.conf.set("spark.executor.cores", "4")     # Was 8 (tasks not CPU-bound)

# 2. Dynamic allocation with aggressive scale-down
spark.conf.set("spark.dynamicAllocation.enabled", "true")
spark.conf.set("spark.dynamicAllocation.minExecutors", "5")
spark.conf.set("spark.dynamicAllocation.maxExecutors", "200")
spark.conf.set("spark.dynamicAllocation.executorIdleTimeout", "30s")  # Kill idle fast

# 3. Fewer large executors vs many small ones
# BAD: 100 executors × 4 cores × 8GB = 400 cores, 800GB (overhead per executor)
# BETTER: 50 executors × 8 cores × 16GB = 400 cores, 800GB (less overhead)
# JVM overhead, BlockManager, Python daemon PER executor
# Fewer executors = less aggregate overhead

# 4. Time-based scaling (different configs by hour)
# Night (02:00-06:00): heavy batch → maxExecutors=500
# Day (09:00-18:00): adhoc queries → maxExecutors=100
# Evening (18:00-02:00): light maintenance → maxExecutors=50

# 5. Graviton/ARM instances (20% cheaper, same performance for Spark)
# EMR: r6g.4xlarge instead of r5.4xlarge
# K8s: ARM node pool for Spark executors
spark.conf.set("spark.kubernetes.node.selector.cpu-arch", "arm64")
```

---

## Issue #92: Spot Instance Fallback to On-Demand (Silent Cost Explosion)

**Frequency**: Medium-High  
**Severity**: High - 3-5x cost increase  
**Spark Component**: External (EMR, K8s, Cloud Provider)

### Symptoms
```
# Spot capacity unavailable → cluster scales with on-demand
# Monthly bill: $50K expected, $150K actual
# No alert: silent fallback to expensive instances
# Peak hours (9 AM): everyone competing for same instance types
```

### Root Cause
- Single instance type in single AZ → spot capacity exhausted
- No fallback awareness/alerting
- Peak demand periods have no spot availability
- Instance type too popular (r5.4xlarge in us-east-1)

### Solution
```python
# 1. Instance diversification (most impactful)
# EMR Instance Fleet: specify 10+ instance types
# All equivalent for Spark workloads:
instance_types = [
    "r5.4xlarge", "r5a.4xlarge", "r5n.4xlarge",
    "r6i.4xlarge", "r6g.4xlarge",  # Graviton (cheaper)
    "m5.4xlarge", "m5a.4xlarge",   # Less memory but works
    "r5.2xlarge",  # Smaller but more available
]
# EMR picks cheapest available across types

# 2. Multi-AZ deployment
# Spread across 3+ AZs for spot availability
# Spot pricing differs per AZ → more options

# 3. Alert on fallback
# CloudWatch: track on-demand instance count
# Alert: on_demand_instances > 20% of total → investigate

# 4. Max on-demand cap
# EMR: MaximumOnDemandCapacityUnits in managed scaling
# K8s: separate node pools with on-demand limits

# 5. Time-shift workloads to avoid peak competition
# Instead of 9 AM batch (peak spot prices):
# Run at 2 AM (lowest spot prices, highest availability)

# 6. Reserved Instances for baseline
# Baseline (always-on): Reserved Instances (40-60% cheaper than on-demand)
# Burst capacity: Spot (60-90% cheaper)
# Emergency overflow: On-Demand (full price, last resort)
```

---

## Issue #93: Linear Scaling Failure (Doubling Resources ≠ Halving Time)

**Frequency**: High  
**Severity**: Medium - diminishing returns  
**Spark Component**: Parallelism limits, Amdahl's Law

### Symptoms
```
# 100 executors: job takes 60 min
# 200 executors: job takes 50 min (should be 30 min!)
# 500 executors: job takes 45 min (barely improved!)
# Throwing more resources at the problem doesn't help
```

### Root Cause
- Amdahl's Law: serial portions limit parallel speedup
- Driver bottleneck (single-threaded planning, scheduling)
- Shuffle overhead increases with more executors (N² connections)
- Data skew: bottleneck is one slow partition, not parallelism
- I/O bound: more CPUs can't fix S3 throughput limit

### Solution
```python
# 1. Identify the bottleneck before scaling
# Check Spark UI:
# - Is one task much slower? → Skew (add executors won't help)
# - Is driver busy? → Reduce partition count, simplify plan
# - Is shuffle time dominant? → Reduce shuffle data, broadcast joins
# - Is I/O time dominant? → Columnar format, predicate pushdown

# 2. Fix serial bottlenecks
# Driver-side serial work:
# - Planning/optimization: simplify query, fewer joins
# - Task scheduling: reduce total task count
# - Result collection: avoid collect() on driver

# 3. Optimal executor count formula
# For CPU-bound: executors = total_tasks / (cores_per_executor * 2)
# For I/O-bound: executors = total_data_MB / (S3_bandwidth_per_executor_MBps * target_seconds)
# For shuffle-bound: more executors = MORE network hops = slower!

# 4. Find diminishing returns point
# Benchmark: run same job with 50, 100, 150, 200, 250 executors
# Plot: cost vs time → find the "knee" of the curve
# Usually: 80% of benefit with 40% of resources

# 5. Reduce shuffle dependency (biggest scaling blocker)
# Replace sort-merge join with broadcast join → no N² shuffle
# Pre-bucket tables → no shuffle on join
# Filter early → less data to shuffle

# 6. Parallelize at pipeline level (not executor level)
# Instead of 500 executors for one big job:
# Split into independent sub-jobs → run 5 jobs with 100 executors each
# Pipeline parallelism often scales better than data parallelism
```

---

## Issue #94: S3 Data Transfer Costs (Cross-Region/Cross-AZ)

**Frequency**: Medium  
**Severity**: High - hidden cost ($0.01-$0.09/GB adds up fast)  
**Spark Component**: External (AWS networking)

### Symptoms
```
# Data transfer charges: $30K/month (hidden in AWS bill)
# Cluster in us-east-1a, S3 bucket in us-east-1b → cross-AZ charges
# Reading from different region entirely → $0.09/GB
# Cluster reads same large dataset every day → repeated transfer costs
```

### Root Cause
- S3 bucket in different region from compute (most expensive)
- Cross-AZ data transfer within same region ($0.01/GB each way)
- No caching layer: re-reading same data from S3 repeatedly
- VPC endpoints not configured (traffic going through NAT gateway)

### Solution
```python
# 1. Co-locate compute and storage (same region, ideally same AZ)
# EMR: launch cluster in same AZ as S3 bucket
# K8s: node affinity for AZ containing data

# 2. Use S3 VPC endpoints (eliminates NAT Gateway charges)
# VPC Endpoint: free data transfer to S3
# Without endpoint: traffic goes through NAT → $0.045/GB!

# 3. Cache frequently-read datasets
# Alluxio: caches S3 data on compute-attached NVMe
# Spark cache: .persist(StorageLevel.MEMORY_AND_DISK) for reused DataFrames
# Iceberg: metadata caching reduces repeated S3 reads

# 4. Reduce data read (biggest impact)
# Column pruning: read 5 columns instead of 500 → 1/100 data transfer
# Partition pruning: read 1 day instead of 365 → 1/365 data transfer
# Predicate pushdown: filter at storage layer

# 5. Compress data (less bytes transferred)
# ZStd compression: 3x less data transferred from S3
# Parquet columnar: inherently smaller than row-format

# 6. Multi-region strategy (if required)
# Primary: compute + storage co-located in same region
# DR: S3 cross-region replication (one-time cost, not per-read)
# Never: compute in us-east-1 reading from eu-west-1 daily

# Cost math:
# 10TB daily read × $0.09/GB (cross-region) = $900/day = $27K/month!
# Same data, same region: $0 (free within region S3→EC2)
```

---

## Issue #95: Cluster Cold Start Latency

**Frequency**: Medium  
**Severity**: Medium - SLA miss for first job of the day  
**Spark Component**: External (EMR bootstrap, K8s pod scheduling)

### Symptoms
```
# First job of the day takes 20 min to start (cluster provisioning)
# EMR cluster creation: 8-12 minutes
# K8s: pod image pull takes 5+ minutes (large Spark image)
# Executor startup: JVM initialization + class loading = 30-60s each
# Critical morning SLA missed due to cluster cold start
```

### Root Cause
- Cluster created on-demand (no pre-warming)
- Large Docker images not cached on nodes
- JVM cold start (class loading, JIT compilation)
- Dependency download at startup (packages, JARs from S3/Maven)

### Solution
```python
# 1. Keep minimum cluster always running
# EMR: keep core nodes always on (only scale task nodes)
# K8s: maintain warm pool of nodes

# 2. Pre-warm before peak workload
# Schedule: start cluster at 01:00, batch jobs start at 02:00
# Buffer: 1 hour for provisioning before first job

# 3. Pre-cache Docker images on nodes
# K8s DaemonSet that pulls Spark images to all nodes
# Or use Amazon ECR with image cache on instance storage

# 4. Pre-download dependencies
# Bundle all JARs in Docker image (no runtime download)
# Use --jars with local paths (not S3/Maven)
# Bake pip packages into image

# 5. JVM warm-up
# First micro-batch or small warmup job to trigger JIT
# After warmup: subsequent jobs benefit from compiled code

# 6. Cluster pooling (reuse across jobs)
# Databricks: cluster pools (pre-created idle instances)
# EMR: persistent clusters for scheduled workloads
# K8s: keep Spark pods warm between jobs (Spark Connect / Thrift Server)

# Cost: warm pool of 10 nodes × $1/hour × 24h = $240/day
# vs. SLA miss cost: $10K+ per missed deadline
```

---

## Issue #96: Data Growth Outpacing Infrastructure (Boiling Frog)

**Frequency**: Very High  
**Severity**: High - gradual then sudden failure  
**Spark Component**: All (capacity planning failure)

### Symptoms
```
# Job ran fine for 6 months, now OOMs daily
# Same code, same config, but data grew 5x
# "We didn't change anything!" (data volume changed)
# Partition size was 100MB, now 5GB (same partition count)
# SLA: was completing in 2 hours, now takes 6 hours
```

### Root Cause
- Data volume growing 10-30% monthly (organic growth)
- Fixed configuration can't adapt (partition count, memory)
- No capacity planning or growth monitoring
- Threshold-based configs (broadcast limit) hit as data grows

### Solution
```python
# 1. Data-volume-aware configuration
# Calculate config based on actual data size:
input_size_gb = get_table_size_gb("catalog.db.events")
if input_size_gb < 100:
    partitions = 200
elif input_size_gb < 1000:
    partitions = 2000
else:
    partitions = int(input_size_gb / 0.256)  # 256MB per partition

spark.conf.set("spark.sql.shuffle.partitions", str(partitions))

# 2. AQE handles growth automatically (best solution)
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.initialPartitionNum", "10000")
# AQE adapts to actual data size at runtime

# 3. Monitor growth trends
# Weekly report:
growth = spark.sql("""
    SELECT date, SUM(file_size_bytes) / 1e9 as size_gb
    FROM catalog.db.events.files
    GROUP BY date
    ORDER BY date DESC
    LIMIT 90
""")
# If growth_rate > 20%/month: trigger capacity planning review

# 4. Auto-scaling infrastructure
# EMR managed scaling: auto-adds nodes as data grows
# K8s: HPA/VPA for Spark workloads
# Budget: allocate 30% headroom above current needs

# 5. Proactive capacity planning
# Rule: plan for 2x current volume (covers 1 year at 6% monthly growth)
# Review quarterly: actual vs projected growth
# Red flag: any table growing > 50% month-over-month

# 6. Data lifecycle management
# Don't just grow forever! Implement:
# - Retention policies (delete data > 2 years)
# - Aggregation tiers (raw 90 days, hourly 1 year, daily forever)
# - Cold storage tiering (S3 IA, Glacier)
```

---

## Issue #97: Multi-Cluster Coordination Failures

**Frequency**: Medium  
**Severity**: High - data inconsistency between clusters  
**Spark Component**: External (cross-cluster orchestration)

### Symptoms
```
# Job A on Cluster 1 writes to Table X
# Job B on Cluster 2 reads Table X → gets stale data
# Two clusters compact same Iceberg table → conflict
# Cross-cluster job dependencies not properly sequenced
# Metadata inconsistency between clusters sharing same catalog
```

### Root Cause
- No shared coordination layer between clusters
- Catalog cache not synchronized
- Multiple writers to same table from different clusters
- No dependency DAG across clusters
- Event-based triggering not implemented

### Solution
```python
# 1. Shared metastore/catalog (source of truth)
# Use: AWS Glue Catalog, Hive Metastore, Unity Catalog
# All clusters point to same catalog → consistent view
# Iceberg: REST catalog provides consistent snapshots

# 2. Table-level locking for writes
# Only ONE writer per table at a time
# Iceberg optimistic concurrency handles this:
# Writer retries on conflict (automatic)

# 3. Cross-cluster dependency management
# Use Airflow with cross-DAG sensors:
# Cluster 1 DAG → writes success marker
# Cluster 2 DAG → waits for success marker

from airflow.sensors.external_task import ExternalTaskSensor

wait_for_upstream = ExternalTaskSensor(
    task_id="wait_for_cluster1_job",
    external_dag_id="cluster1_daily_etl",
    external_task_id="write_output",
    timeout=7200,
)

# 4. Event-driven coordination
# Cluster 1: writes data → publishes SNS/EventBridge event
# Cluster 2: triggered by event → reads fresh data
# No polling, no timing dependencies

# 5. Read isolation with Iceberg snapshots
# Cluster 2: reads specific snapshot (consistent point-in-time)
spark.read.option("snapshot-id", "12345").format("iceberg").load("table")
# Not affected by Cluster 1's ongoing writes

# 6. Dedicated clusters by function
# Cluster 1: ingestion/ETL (writes only)
# Cluster 2: analytics/reporting (reads only)
# No write conflicts by design
```

---

## Issue #98: Inefficient Data Format Migration

**Frequency**: Low (but very expensive when it happens)  
**Severity**: Medium - massive one-time cost  
**Spark Component**: DataFrameWriter, FileFormat conversion

### Symptoms
```
# Migrating 500TB from CSV → Parquet → Iceberg
# Migration job runs for 3 days and costs $50K
# Downstream consumers must switch simultaneously
# Migration fails midway → partial state, must restart
# Performance during migration: both old and new formats served
```

### Root Cause
- Large-scale data migration is expensive (read + transform + write)
- All-or-nothing migration is risky
- No incremental migration strategy
- Consumers can't gradually switch

### Solution
```python
# 1. Incremental migration (partition by partition)
# Migrate one partition at a time (days, months):
partitions_to_migrate = spark.sql("""
    SELECT DISTINCT date FROM old_table 
    WHERE date < '2024-01-01' 
    ORDER BY date DESC
""").collect()

for row in partitions_to_migrate:
    date = row.date
    # Migrate single partition
    spark.read.csv(f"s3://old/{date}/") \
        .write.format("iceberg") \
        .mode("append") \
        .save("catalog.db.new_table")
    # Validate
    assert_counts_match(f"s3://old/{date}/", f"catalog.db.new_table", date)
    # Checkpoint progress
    mark_migrated(date)

# 2. Dual-write during migration
# New data: written to BOTH old and new format
# Old data: migrated incrementally in background
# Consumers: gradually switch to new format

# 3. View abstraction for consumers
spark.sql("""
    CREATE VIEW unified_view AS
    SELECT * FROM new_iceberg_table
    UNION ALL
    SELECT * FROM old_csv_table WHERE date < '2023-06-01'
""")
# Consumers query view → transparent migration

# 4. Cost optimization for migration
# Use Spot instances for migration (interruptible is fine)
# Run during off-peak (night/weekend)
# Parallelize: migrate independent partitions simultaneously

# 5. Validation framework
def validate_migration(old_path, new_table, partition_filter):
    old_count = spark.read.csv(old_path).filter(partition_filter).count()
    new_count = spark.read.format("iceberg").load(new_table).filter(partition_filter).count()
    assert old_count == new_count, f"Count mismatch: {old_count} vs {new_count}"
    
    # Column-level validation
    old_stats = spark.read.csv(old_path).filter(partition_filter).agg(
        F.sum("amount"), F.avg("amount"), F.min("date"), F.max("date")
    ).first()
    new_stats = spark.read.format("iceberg").load(new_table).filter(partition_filter).agg(
        F.sum("amount"), F.avg("amount"), F.min("date"), F.max("date")
    ).first()
    assert old_stats == new_stats, "Aggregate mismatch!"
```

---

## Issue #99: Auto-Scaling Oscillation (Thrashing)

**Frequency**: Medium  
**Severity**: Medium - waste + instability  
**Spark Component**: Dynamic Allocation, External Auto-scaler

### Symptoms
```
# Cluster scales up to 200 nodes → job enters shuffle phase → nodes idle
# Auto-scaler removes nodes → next stage needs them → scales up again
# Constant scale-up/scale-down every 5 minutes
# Executor churn: launch → idle → remove → relaunch
# Shuffle data lost when scaled-down nodes removed
```

### Root Cause
- Scale-down too aggressive (removes executors with shuffle data)
- Batch jobs have alternating compute-heavy and shuffle-heavy phases
- Cooldown period too short
- External auto-scaler doesn't understand Spark workload patterns

### Solution
```python
# 1. Longer idle timeout (prevent premature removal)
spark.conf.set("spark.dynamicAllocation.executorIdleTimeout", "120s")  # 2 min (not 30s)
spark.conf.set("spark.dynamicAllocation.cachedExecutorIdleTimeout", "600s")  # 10 min for cached

# 2. External Shuffle Service (survive executor removal)
spark.conf.set("spark.shuffle.service.enabled", "true")
# Now removing executors doesn't lose shuffle data

# 3. Set minimum executors as floor (don't scale to zero between stages)
spark.conf.set("spark.dynamicAllocation.minExecutors", "50")
# Keep 50 executors always → no cold start for next stage

# 4. Scale-down cooldown for cluster autoscaler
# K8s Cluster Autoscaler:
# --scale-down-delay-after-add=10m
# --scale-down-unneeded-time=10m
# EMR: managed scaling has built-in cooldown

# 5. Right-size for the ENTIRE job, not per-stage
# If job has 10 stages with varying parallelism:
# Allocate for average need, let AQE handle partition sizing
# Don't: oscillate between 50 and 500 executors

# 6. Graceful decommission (scale down without data loss)
spark.conf.set("spark.decommission.enabled", "true")
spark.conf.set("spark.storage.decommission.shuffleBlocks.enabled", "true")
# Migrates shuffle data before executor removal
```

---

## Issue #100: Total Cost of Ownership Visibility (TCO)

**Frequency**: Very High (organizational problem)  
**Severity**: High - can't make informed decisions  
**Spark Component**: External (cost management)

### Symptoms
```
# "How much does this pipeline cost?" → "I don't know"
# Can't compare: should we use Spark or Glue or Athena?
# Can't justify: is the cost worth the value delivered?
# No showback/chargeback to teams
# Optimization efforts have no measurable ROI
```

### Root Cause
- Cloud costs split across multiple services (EC2, S3, network, EMR markup)
- No tagging strategy → can't attribute costs to pipelines
- Shared infrastructure costs not allocated
- No unit economics (cost per GB processed, cost per record)

### Solution
```python
# 1. Comprehensive tagging for all resources
# Tags: team, pipeline, environment, cost-center
# Apply to: EMR clusters, K8s pods, S3 paths, IAM roles

# 2. Calculate unit costs per pipeline
class CostCalculator:
    def __init__(self, spark):
        self.spark = spark
    
    def compute_job_cost(self, app_id):
        """Calculate total cost of a Spark job."""
        metrics = self.spark.sql(f"""
            SELECT 
                SUM(executor_hours) as total_executor_hours,
                SUM(data_read_gb) as total_data_read_gb,
                SUM(data_written_gb) as total_data_written_gb,
                MAX(wall_clock_hours) as elapsed_hours
            FROM job_metrics
            WHERE app_id = '{app_id}'
        """).first()
        
        # Cost components:
        compute_cost = metrics.total_executor_hours * 1.2  # $/executor-hour (EMR)
        storage_read_cost = metrics.total_data_read_gb * 0.004  # S3 GET requests
        storage_write_cost = metrics.total_data_written_gb * 0.005  # S3 PUT requests
        network_cost = (metrics.total_data_read_gb + metrics.total_data_written_gb) * 0.0  # Same region = free
        
        total = compute_cost + storage_read_cost + storage_write_cost + network_cost
        
        return {
            "total_cost": round(total, 2),
            "cost_per_gb": round(total / metrics.total_data_read_gb, 4),
            "compute_pct": round(compute_cost / total * 100, 1),
            "breakdown": {
                "compute": round(compute_cost, 2),
                "storage_io": round(storage_read_cost + storage_write_cost, 2),
                "network": round(network_cost, 2),
            }
        }

# 3. Cost comparison dashboard
# Pipeline A: Spark ETL → $5/TB processed
# Pipeline B: Glue Job → $8/TB processed (serverless premium)
# Pipeline C: Athena → $3/TB (but limited to SQL, no streaming)

# 4. Unit economics targets
# Set per-team SLAs:
# - Cost per GB processed: < $2
# - Cost per million records: < $0.50
# - Monthly budget: $50K ± 10%
# Alert on violations

# 5. Optimization ROI tracking
# Before optimization: 500 executor-hours/day × $1.2/hr = $600/day
# After optimization: 200 executor-hours/day × $1.2/hr = $240/day
# Savings: $360/day × 365 = $131K/year

# 6. Monthly cost review
# Top 10 most expensive pipelines
# Top 10 fastest-growing pipelines (predict future cost)
# Recommendations: right-size, compress, partition prune, cache
```

---

## Summary: Cost & Scaling Decision Tree

```
Cost/scaling concern
├── Paying too much?
│   ├── Low utilization → Issue #91 (right-size executors)
│   ├── On-demand when spot available → Issue #92 (diversification)
│   ├── Data transfer charges → Issue #94 (co-locate, VPC endpoint)
│   ├── No cost visibility → Issue #100 (tagging, unit economics)
│   └── Migration costs → Issue #98 (incremental, off-peak)
├── Not scaling well?
│   ├── More resources ≠ faster → Issue #93 (find bottleneck, Amdahl's law)
│   ├── Data growing faster than budget → Issue #96 (adaptive config, lifecycle)
│   └── Auto-scaling thrashing → Issue #99 (cooldown, ESS, minimum floor)
├── Infrastructure overhead?
│   ├── Cold start delays → Issue #95 (pre-warm, cluster pooling)
│   └── Multi-cluster coordination → Issue #97 (shared catalog, events)
└── Quick wins (typical 30-50% savings)
    ├── Graviton/ARM instances → 20% cheaper
    ├── Spot instances → 60-90% cheaper (with retry logic)
    ├── Column pruning → 5-20x less I/O
    ├── Partition pruning → 10-365x less data scanned
    └── Dynamic allocation → only pay for what you use
```

---

## Master Issue Index: All 100 Issues

| # | Issue | Category | Severity |
|---|-------|----------|----------|
| 1-10 | Memory & OOM | Memory | Critical |
| 11-20 | Shuffle & Network | Performance | High |
| 21-30 | Data Skew & Partitions | Performance | High |
| 31-40 | Streaming | Correctness/Perf | Critical |
| 41-50 | Storage & I/O | Performance | High |
| 51-60 | Query Optimization | Performance | Medium-High |
| 61-70 | Cluster & Resources | Operations | High |
| 71-80 | Data Quality | Correctness | Critical |
| 81-90 | Deployment & Ops | Reliability | High |
| 91-100 | Cost & Scaling | Business | High |
