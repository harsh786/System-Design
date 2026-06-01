# Cost & Scaling Issues (#71-80)

> AWS Glue costs can spiral from $5K/month to $50K/month without proper governance.
> These issues represent the difference between a well-optimized platform and one that
> hemorrhages money while underperforming.

---

## Issue #71: Auto-Scaling Cold Start Waste (Paying for Idle Workers)

### Severity: P2 | Frequency: Every job run

### Symptoms
```
# Job requests 100 workers with auto-scaling
# Workers 1-100 provision over 3-5 minutes
# First 2 minutes: all workers initializing (0 useful work)
# You pay for all 100 DPU-hours during initialization

# Cost waste: 100 workers × 5 min startup × $0.44/DPU-hour = $3.67 per job start
# × 200 jobs/day = $733/day = $22K/month wasted on cold starts!
```

### Root Cause
```
Glue billing starts when workers are ALLOCATED, not when processing begins.
Worker lifecycle:
[Allocated (billing starts)] → [Container pull] → [Spark init] → [Register] → [First task]
                  ^                                                                    ^
           Billing starts here                                              Useful work starts here
                  └──────── 2-5 minutes of paid idle time ──────────────────────┘
```

### Fix
```python
# Fix 1: Right-size workers (don't over-provision)
# If job finishes in 10 min with 100 workers:
# Try 50 workers → finishes in 18 min (10 min + 8 min less cold start waste)
# Cost: 50 × 18min vs 100 × 15min (with cold start) → 50 workers CHEAPER

# Fix 2: Use number of workers that matches actual parallelism
# If reading 200 partitions: 200 workers make sense
# If reading 20 partitions: 200 workers = 180 workers idle after read phase!
input_partitions = df.rdd.getNumPartitions()
optimal_workers = min(input_partitions // 2, 200)  # 2 partitions per worker
spark.conf.set("spark.dynamicAllocation.maxExecutors", str(optimal_workers))

# Fix 3: Batch small jobs together (amortize cold start)
# Instead of 10 tiny jobs (each with 5-min cold start = 50 min wasted):
# One job that processes all 10 workloads (single 5-min cold start)
def batch_processor(workloads):
    for workload in workloads:
        process(workload)  # Sequential in same job (already warm)

# Fix 4: Use Flex execution for non-urgent jobs (takes capacity from over-provisioned Standard jobs)
# Flex can reuse already-warm capacity → sometimes NO cold start
```

---

## Issue #72: Flex Execution Unpredictable Start Times

### Severity: P2 | Frequency: Common with Flex

### Symptoms
```
# SLA: Data ready by 6:00 AM
# Job submitted at 2:00 AM with Flex execution
# Flex job starts at... 4:30 AM? 5:00 AM? 5:45 AM?? 
# No guaranteed start time with Flex!
# Sometimes meets SLA, sometimes misses by hours
```

### Root Cause
```
Flex execution uses spare capacity (like spot instances).
If no spare capacity available: job WAITS until capacity frees up.
No SLA on start time. Only guarantee: it WILL eventually start.
Typical wait: 0-20 minutes, but can be hours during peak.
```

### Fix
```python
# Fix 1: Use Flex ONLY for non-SLA workloads
# SLA-bound jobs: ALWAYS use Standard execution
# Backfill/historical: Flex (saves 60%, no SLA needed)
# Dev/test: Flex (no urgency)

# Fix 2: Hybrid strategy with fallback
import boto3
import time

def submit_with_flex_fallback(job_name, args, max_flex_wait_minutes=30):
    """Try Flex first, fall back to Standard if too slow."""
    glue = boto3.client('glue')
    
    # Try Flex first (60% cheaper)
    response = glue.start_job_run(
        JobName=job_name,
        Arguments=args,
        ExecutionClass='FLEX'
    )
    run_id = response['JobRunId']
    
    # Wait for Flex to start
    start_time = time.time()
    while True:
        status = glue.get_job_run(JobName=job_name, RunId=run_id)
        state = status['JobRun']['JobRunState']
        
        if state == 'RUNNING':
            return run_id  # Flex started, use it
        
        elapsed = (time.time() - start_time) / 60
        if elapsed > max_flex_wait_minutes:
            # Flex too slow, cancel and use Standard
            glue.batch_stop_job_run(JobName=job_name, JobRunIds=[run_id])
            
            response = glue.start_job_run(
                JobName=job_name,
                Arguments=args,
                ExecutionClass='STANDARD'  # Guaranteed start
            )
            return response['JobRunId']
        
        time.sleep(30)  # Check every 30s

# Fix 3: Submit Flex jobs earlier (buffer for wait time)
# If SLA = 6:00 AM and job takes 2 hours:
# Standard: submit at 4:00 AM (guaranteed start)
# Flex: submit at 1:00 AM (3 hours buffer for wait + processing)
```

---

## Issue #73: Worker Type Over-Provisioning (Using G.4X for Simple ETL)

### Severity: P3 | Frequency: Very common (inertia)

### Symptoms
```
# Job using G.4X workers (64GB RAM, 16 vCPU per worker)
# CloudWatch shows: avg CPU = 15%, avg memory = 20%
# Job is I/O bound (reading/writing S3), not compute bound
# Paying 4x more than necessary!

# G.4X cost: $0.44/DPU-hour × 4 DPU/worker = $1.76/worker-hour
# G.1X cost: $0.44/DPU-hour × 1 DPU/worker = $0.44/worker-hour
# 4x cost for same job that doesn't need the resources!
```

### Root Cause
```
Developers default to largest worker type "to be safe."
Most ETL workloads are I/O bound (S3 read/write), not memory bound.
Only memory-intensive operations need G.2X+:
- Large broadcast joins (>10GB dimension)
- Window functions on large partitions
- Graph computations
- ML model training
```

### Fix
```python
# Decision matrix for worker type:
"""
┌──────────────┬───────────────────────────────────────────────────┐
│ Worker Type  │ When to Use                                       │
├──────────────┼───────────────────────────────────────────────────┤
│ G.1X (16GB)  │ Simple ETL, S3→S3, filtering, basic transforms    │
│              │ Most jobs should START here                        │
├──────────────┼───────────────────────────────────────────────────┤
│ G.2X (32GB)  │ Joins with medium dimensions, aggregations,       │
│              │ moderate shuffle operations                         │
├──────────────┼───────────────────────────────────────────────────┤
│ G.4X (64GB)  │ Large broadcast joins, ML features,               │
│              │ complex window functions, graph processing          │
├──────────────┼───────────────────────────────────────────────────┤
│ G.8X (128GB) │ Extremely large shuffle, in-memory analytics,     │
│              │ model training. RARELY needed.                      │
├──────────────┼───────────────────────────────────────────────────┤
│ Z.2X (32GB)  │ Glue Ray jobs (Python-based ML, pandas)           │
└──────────────┴───────────────────────────────────────────────────┘
"""

# Optimization process:
# 1. Start with G.1X
# 2. If OOM → try G.2X
# 3. If still OOM → optimize code first (skew, UDFs, caching)
# 4. Only use G.4X if justified by specific bottleneck

# Automated right-sizing:
def recommend_worker_type(job_name, last_n_runs=5):
    """Analyze past runs to recommend optimal worker type."""
    cw = boto3.client('cloudwatch')
    
    # Get max memory usage from last N runs
    response = cw.get_metric_statistics(
        Namespace='Glue',
        MetricName='glue.ALL.jvm.heap.usage',
        Dimensions=[{'Name': 'JobName', 'Value': job_name}],
        Period=300, Statistics=['Maximum'],
        StartTime=datetime.now() - timedelta(days=7),
        EndTime=datetime.now()
    )
    
    max_heap_pct = max(dp['Maximum'] for dp in response['Datapoints'])
    
    if max_heap_pct < 40:
        return "G.1X (current type over-provisioned)"
    elif max_heap_pct < 70:
        return "G.2X (good fit)"
    elif max_heap_pct < 90:
        return "G.4X (memory-intensive workload)"
    else:
        return "G.8X or optimize code (near OOM)"
```

---

## Issue #74: Unnecessary Data Re-reads (No Intermediate Caching)

### Severity: P2 | Frequency: Common in multi-output jobs

### Symptoms
```
# Job reads same 5TB dataset THREE times:
# 1. Read → transform → output A
# 2. Read → transform → output B (SAME source re-read!)
# 3. Read → transform → output C (SAME source re-read AGAIN!)
# 
# S3 bytes read: 15TB (should be 5TB)
# Cost: 3x DPU time for redundant reads
```

### Fix
```python
# Fix 1: Read once, branch for multiple outputs
df = spark.read.parquet("s3://huge-table/")  # Read once

# Write to intermediate (checkpoint)
df.write.parquet("s3://temp/checkpoint/")
df = spark.read.parquet("s3://temp/checkpoint/")  # Reuse materialized

# Multiple outputs from same materialized data
output_a = df.filter(F.col("type") == "A").groupBy("key").agg(...)
output_b = df.filter(F.col("type") == "B").groupBy("key").agg(...)
output_c = df.select("key", "value").distinct()

output_a.write.parquet("s3://output_a/")
output_b.write.parquet("s3://output_b/")
output_c.write.parquet("s3://output_c/")

# Fix 2: Persist in memory (if dataset fits)
df = spark.read.parquet("s3://data/").persist(StorageLevel.MEMORY_AND_DISK)
# All subsequent operations read from cache, not S3
# Remember to unpersist when done!
df.unpersist()

# Fix 3: Split into separate jobs with shared staging
# Job 1: Read + Transform → write to staging S3
# Job 2: Read staging → output A (fast, small read)
# Job 3: Read staging → output B (fast, small read)
```

---

## Issue #75: Glue Development Endpoint Cost Leak

### Severity: P3 | Frequency: Constant (forgotten endpoints)

### Symptoms
```
# Monthly bill: $2000 for "Glue Development Endpoints"
# No one is using them (created 6 months ago, forgotten)
# Dev endpoint running 24/7: $0.44/DPU-hour × 5 DPU × 720 hours = $1,584/month
# Per UNUSED endpoint!
```

### Fix
```python
# Fix 1: Auto-terminate idle endpoints (Lambda)
import boto3

def cleanup_idle_endpoints(event, context):
    """Lambda: runs daily, terminates endpoints idle > 4 hours."""
    glue = boto3.client('glue')
    endpoints = glue.get_dev_endpoints()['DevEndpoints']
    
    for ep in endpoints:
        last_used = ep.get('LastModifiedTimestamp', ep['CreatedTimestamp'])
        idle_hours = (datetime.now() - last_used).total_seconds() / 3600
        
        if idle_hours > 4:
            glue.delete_dev_endpoint(EndpointName=ep['EndpointName'])
            notify(f"Terminated idle endpoint: {ep['EndpointName']} (idle {idle_hours:.0f}h)")

# Fix 2: Use Glue Interactive Sessions instead (auto-terminate after idle)
# Interactive Sessions: auto-stop after --idle-timeout (default: 2880s = 48min)
# Cost: only pay while session is active

# Fix 3: Use Glue Studio Notebooks (managed, auto-terminate)
# No long-running endpoint needed

# Fix 4: Budget alert
# CloudWatch Billing Alarm on AWS Glue > $X/month
# Catches forgotten resources early
```

---

## Issue #76: Inefficient Partition Strategy (Over/Under-Partitioned Output)

### Severity: P2 | Frequency: Design-time decision that haunts forever

### Symptoms
```
# Over-partitioned: 100K partitions with 1MB each (small files problem)
# Under-partitioned: 10 partitions with 100GB each (slow queries)

# Query pattern: "WHERE date = '2024-01-15' AND region = 'us-east-1'"
# Partitioned by: date only
# Result: reads all regions for that date (10x over-read)
```

### Fix
```python
# GUIDELINES for partition strategy:
"""
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITION SIZING RULES OF THUMB                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Target per partition:  128MB - 1GB compressed Parquet               │
│  Target total partitions: < 10,000 for Hive, unlimited for Iceberg  │
│                                                                      │
│  Formula: Partitions = Daily_Data_Size / Target_Partition_Size       │
│  Example: 500GB/day ÷ 256MB = 2000 partitions/day (OK for Hive)    │
│                                                                      │
│  Partition by columns that:                                          │
│  ✓ Appear in WHERE clauses of 80%+ of queries                       │
│  ✓ Have bounded cardinality (date, region, not user_id)             │
│  ✓ Are relatively uniform in distribution                            │
│  ✓ Align with data lifecycle (delete by date partition)              │
│                                                                      │
│  DO NOT partition by:                                                 │
│  ✗ High-cardinality columns (user_id → millions of partitions)      │
│  ✗ Skewed columns (90% in one value → one huge partition)           │
│  ✗ Columns not used in queries (wasted overhead)                    │
└─────────────────────────────────────────────────────────────────────┘
"""

# Fix: Use Iceberg hidden partitioning (change without rewrite)
spark.sql("""
    CREATE TABLE db.events (
        event_id STRING,
        event_time TIMESTAMP,
        region STRING,
        data STRING
    ) USING iceberg
    PARTITIONED BY (days(event_time), region)
""")
# Can later change to hours(event_time) WITHOUT rewriting data!
spark.sql("ALTER TABLE db.events SET PARTITION SPEC (hours(event_time), region)")
```

---

## Issue #77: Unbounded Job Duration (No Timeout Protection)

### Severity: P1 | Frequency: Monthly (runaway jobs)

### Symptoms
```
# Job normally takes 30 minutes
# Today: still running after 8 hours (stuck on one skewed partition)
# Cost: 8 hours × 100 workers × $0.44/DPU = $352 for ONE stuck job
# No automatic timeout → runs until manual intervention or 48-hour max
```

### Fix
```python
# Fix 1: Set job timeout in Glue configuration
# Timeout parameter (minutes):
# Set to 2x normal duration: if job normally takes 30 min → timeout = 60 min
{
    "Timeout": 60,  # Minutes
    "MaxRetries": 1
}

# Fix 2: Implement internal timeout per stage
import signal

class JobTimeout:
    def __init__(self, max_seconds):
        self.max_seconds = max_seconds
        self.start_time = time.time()
    
    def check(self, stage_name):
        elapsed = time.time() - self.start_time
        if elapsed > self.max_seconds:
            raise TimeoutError(
                f"Job exceeded timeout ({self.max_seconds}s) during stage: {stage_name}. "
                f"Elapsed: {elapsed:.0f}s"
            )

timeout = JobTimeout(max_seconds=1800)  # 30 min

# Check at each major stage:
df = read_source()
timeout.check("read")

df_transformed = transform(df)
timeout.check("transform")

write_output(df_transformed)
timeout.check("write")

# Fix 3: Set Spark task-level timeout
spark.conf.set("spark.network.timeout", "300s")  # Kill stuck tasks after 5min
spark.conf.set("spark.task.maxFailures", "4")  # Retry failed tasks 4 times then fail job

# Fix 4: Alert on long-running jobs
# CloudWatch Alarm: Glue Job Duration > 2 × Expected → Page on-call
```

---

## Issue #78: Cost Explosion from Unintended Full Table Scan

### Severity: P1 | Frequency: Monthly (code bugs)

### Symptoms
```
# Normal daily cost: $200 (processing 1 day of data)
# Today: $15,000 bill (processed 3 YEARS of data!)
# Developer forgot to add date filter after bookmark reset
# Entire historical dataset reprocessed
```

### Fix
```python
# Fix 1: Cost guard at job start (see Issue #22)
def cost_guard(source_path, max_scan_gb=500):
    """Abort if about to scan more data than expected."""
    # Estimate scan size from partition count or file listing
    file_count = count_files(source_path)
    estimated_gb = file_count * 0.128  # Assume 128MB avg file
    
    if estimated_gb > max_scan_gb:
        raise Exception(
            f"COST GUARD: Would scan ~{estimated_gb:.0f}GB "
            f"(max allowed: {max_scan_gb}GB). "
            f"Possible missing filter. Aborting."
        )

# Fix 2: Budget alerts per job
# Tag jobs with cost center:
# --conf spark.glue.COST_CENTER=fraud-team
# CloudWatch Budget: Alert when "fraud-team" tagged resources exceed $X/day

# Fix 3: Max DPU-hours per job run
# Calculate: expected_duration × expected_workers = max DPU-hours
# If exceeded → automatic kill (via Lambda monitoring)

# Fix 4: Mandatory date predicates (enforce via code review + CI)
def require_date_filter(df, table_name):
    """Verify DataFrame has date predicate applied."""
    plan = df._jdf.queryExecution().executedPlan().toString()
    if "date" not in plan.lower() and "partition" not in plan.lower():
        raise Exception(
            f"SAFETY: No date filter detected on {table_name}. "
            f"Full table scan not allowed. Add .filter(F.col('date') >= ...)"
        )
```

---

## Issue #79: DPU Under-Utilization (Paying for Idle Compute)

### Severity: P2 | Frequency: Constant

### Symptoms
```
# Job allocated: 100 workers
# CloudWatch metrics:
#   CPU utilization: avg 12%, max 35%
#   Memory utilization: avg 15%, max 25%
# Job is I/O bound (waiting for S3), not compute bound
# Paying for 100 × $0.44/DPU-hour but only USING 15% of capacity
```

### Fix
```python
# Fix 1: Reduce workers (fewer workers, higher utilization)
# If CPU avg = 12% with 100 workers:
# Theoretical: 12 workers at 100% CPU would do same work
# Practical: 20-30 workers (accounting for I/O overlap)
# Try: 30 workers, verify job completes within SLA

# Fix 2: Increase parallelism per worker (more tasks per executor)
spark.conf.set("spark.task.cpus", "1")  # Default (1 task per core)
# For I/O-bound tasks: can run more tasks per core
spark.conf.set("spark.executor.cores", "8")  # Use all 4 vCPU per G.1X
# 100 workers × 4 cores = 400 concurrent tasks

# Fix 3: Use smaller worker type with more workers
# Instead of: 50 × G.2X (50 × 2 DPU = 100 DPU)
# Try: 100 × G.1X (100 × 1 DPU = 100 DPU, same cost but better I/O parallelism)
# More workers = more parallel S3 connections = faster I/O

# Fix 4: Identify I/O bottleneck and fix it
# If S3 read is bottleneck: increase file size (fewer large files, less overhead)
# If S3 write is bottleneck: reduce output partitions
# If JDBC is bottleneck: increase numPartitions for JDBC read
```

---

## Issue #80: No Cost Attribution (Can't Bill Teams for Their Usage)

### Severity: P3 | Frequency: Organizational challenge

### Symptoms
```
# Monthly Glue bill: $85,000
# CFO asks: "Which team is responsible for this?"
# Answer: "We don't know" (no tagging, no attribution)
# Result: no accountability, no optimization incentive
```

### Fix
```python
# Fix 1: Tag every Glue job with cost allocation tags
# Required tags:
# - team: "fraud-detection"
# - environment: "production"  
# - cost-center: "CC-4567"
# - project: "transaction-scoring"

# In CDK:
glue.CfnJob(self, "FraudJob",
    name="fraud-feature-pipeline",
    tags={
        "team": "fraud-detection",
        "environment": "production",
        "cost-center": "CC-4567"
    }
)

# Fix 2: Cost Explorer report by tag
# AWS Cost Explorer → Group by Tag → "team"
# Shows: fraud-detection: $12K, recommendations: $8K, etc.

# Fix 3: Automated cost report per team
import boto3

def generate_team_cost_report():
    """Weekly cost report broken down by team."""
    ce = boto3.client('ce')
    
    response = ce.get_cost_and_usage(
        TimePeriod={'Start': last_week, 'End': today},
        Granularity='DAILY',
        Filter={
            'Dimensions': {'Key': 'SERVICE', 'Values': ['AWS Glue']}
        },
        GroupBy=[{'Type': 'TAG', 'Key': 'team'}]
    )
    
    for group in response['ResultsByTime'][0]['Groups']:
        team = group['Keys'][0]
        cost = group['Metrics']['UnblendedCost']['Amount']
        send_report(team, cost)

# Fix 4: Set per-team budget with alerts
# AWS Budgets: 
# - Fraud team: $15K/month Glue budget
# - Alert at 80% ($12K)
# - Action at 100%: notify VP + throttle non-critical jobs
```

---

## Cost Optimization Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│  COST OPTIMIZATION PLAYBOOK                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Quick Wins (implement immediately):                                 │
│  1. Right-size worker types (most jobs work fine with G.1X)    -40% │
│  2. Use Flex for non-SLA jobs                                  -60% │
│  3. Add job timeout protection                             prevent  │
│  4. Remove unused dev endpoints                            -$1.5K   │
│  5. Tag everything for attribution                         insight  │
│                                                                      │
│  Medium-term (1-2 weeks):                                            │
│  6. Implement cost guards (prevent full-table scans)       prevent  │
│  7. Optimize partition strategy                            -20-50%  │
│  8. Batch small jobs together (amortize cold start)        -15%    │
│  9. Add intermediate caching for multi-output jobs          -30%    │
│  10. Implement auto-scaling tuning                          -20%    │
│                                                                      │
│  Long-term (1-3 months):                                             │
│  11. Migrate to Iceberg (better pruning, less scan)        -30-50% │
│  12. Implement job priority queue with DPU budget          control  │
│  13. Reserved capacity (if consistent usage)               -30%    │
│                                                                      │
│  Expected total savings: 40-70% of current Glue spend               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
