# Concurrency & Throttling Issues (#61-70)

> At enterprise scale (100+ jobs), you hit AWS service limits that are invisible in development.
> These issues only appear in production when multiple teams run jobs simultaneously.

---

## Issue #61: Glue API Throttling (StartJobRun Rate Limit)

### Severity: P1 | Frequency: Daily at scale (100+ concurrent jobs)

### Symptoms
```
# Error: ThrottlingException: Rate exceeded
# Airflow/Step Functions reports: "Failed to start Glue job"
# Multiple orchestrated jobs fail simultaneously at scheduled time
# Glue API calls returning HTTP 429

# Typical scenario: 50 jobs all scheduled at midnight UTC
# Orchestrator fires 50 StartJobRun calls in 5 seconds → throttled
```

### Root Cause
```
AWS Glue API rate limits (per account, per region):
┌──────────────────────────────────┬───────────────┐
│ API Call                          │ Default Limit │
├──────────────────────────────────┼───────────────┤
│ StartJobRun                       │ 5/second      │
│ GetJobRun                         │ 10/second     │
│ GetJobRuns                        │ 5/second      │
│ BatchGetJobs                      │ 5/second      │
│ GetTable/GetPartitions            │ 10/second     │
│ CreatePartition/BatchCreatePart.  │ 25/second     │
│ GetDatabase                       │ 10/second     │
└──────────────────────────────────┴───────────────┘

50 jobs at midnight = 50 StartJobRun calls >> 5/second limit
```

### Fix
```python
# Fix 1: Stagger job start times
# Instead of: 50 jobs at 00:00:00
# Use: 50 jobs spread across 00:00:00 to 00:05:00 (6 seconds apart)

# In Airflow:
from datetime import timedelta
import hashlib

def staggered_schedule(dag_id, base_time, max_spread_minutes=5):
    """Deterministic offset based on job name."""
    hash_val = int(hashlib.md5(dag_id.encode()).hexdigest(), 16)
    offset_seconds = hash_val % (max_spread_minutes * 60)
    return base_time + timedelta(seconds=offset_seconds)

# Fix 2: Retry with exponential backoff in orchestrator
import boto3
from botocore.config import Config

config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'  # Adaptive retries for throttling
    }
)
glue = boto3.client('glue', config=config)

# Fix 3: Batch API calls where possible
# Instead of 50 individual GetJobRun calls:
# Use BatchGetJobRuns (fewer API calls)

# Fix 4: Request limit increase via AWS Support
# For production workloads, request increase to:
# StartJobRun: 25/second
# GetJobRun: 50/second
# GetTable: 50/second

# Fix 5: Use Glue Workflows (native orchestration, no external API calls)
# Glue Workflow triggers jobs internally (doesn't count against StartJobRun limit)
```

---

## Issue #62: Concurrent Job Limit Exceeded

### Severity: P1 | Frequency: During peak hours

### Symptoms
```
# Error: ConcurrentRunsExceededException
# OR: Job queued indefinitely (waiting for slot)
# Default: max 200 concurrent job runs per account per region
# During month-end: 50 teams × 5 jobs each = 250 concurrent runs → BLOCKED
```

### Root Cause
```
AWS Glue concurrent execution limits:
- Default: 200 concurrent job runs per account
- Default: 1000 DPUs total per account
- Per-job: MaxConcurrentRuns setting (default: 1)

Hidden constraint: even if you have 200 run quota,
if total DPUs exceed 1000, new jobs WAIT in queue.
```

### Fix
```python
# Fix 1: Request quota increase
# Service Quotas → AWS Glue → Concurrent job runs → Request increase to 500

# Fix 2: Prioritize critical jobs
# Set job priority via scheduling:
# P1 jobs: 00:00 - 00:30 (exclusive window, no competition)
# P2 jobs: 00:30 - 02:00
# P3 jobs: 02:00+ (fills remaining capacity)

# Fix 3: Right-size DPUs to fit within limits
# Instead of 10 jobs × 100 DPU each = 1000 DPU (at limit!)
# Optimize: 10 jobs × 30 DPU with auto-scaling (300 DPU baseline)

# Fix 4: Job queue with priority management
import boto3
import heapq
from datetime import datetime

class GlueJobQueue:
    """Priority queue for Glue job execution."""
    
    def __init__(self, max_concurrent=150, max_dpu=800):
        self.max_concurrent = max_concurrent
        self.max_dpu = max_dpu
        self.queue = []  # Min-heap (priority, timestamp, job_config)
        self.running = {}  # job_run_id → dpu_count
    
    def submit(self, job_name, priority, dpu_count, args={}):
        heapq.heappush(self.queue, (priority, datetime.now(), {
            'JobName': job_name, 'DPU': dpu_count, 'Arguments': args
        }))
        self._try_launch()
    
    def _try_launch(self):
        glue = boto3.client('glue')
        while self.queue:
            current_runs = len(self.running)
            current_dpu = sum(self.running.values())
            
            _, _, job_config = self.queue[0]  # Peek
            
            if (current_runs < self.max_concurrent and 
                current_dpu + job_config['DPU'] <= self.max_dpu):
                _, _, config = heapq.heappop(self.queue)
                response = glue.start_job_run(
                    JobName=config['JobName'],
                    Arguments=config['Arguments'],
                    NumberOfWorkers=config['DPU']
                )
                self.running[response['JobRunId']] = config['DPU']
            else:
                break  # Can't launch more right now

# Fix 5: Use Flex execution for non-critical jobs (cheaper, but may queue)
# Flex jobs don't count toward standard DPU limit
```

---

## Issue #63: S3 Request Throttling (503 SlowDown)

### Severity: P1 | Frequency: Weekly at PB scale

### Symptoms
```
# Error: AmazonS3Exception: Please reduce your request rate (503 SlowDown)
# Job slows to crawl or fails entirely
# Happens when multiple jobs access same S3 prefix simultaneously

# S3 CloudTrail shows:
# 5600 GET requests/second to prefix "s3://bucket/data/2024/01/" (exceeds 5500 limit)
```

### Root Cause
```
S3 rate limits per PREFIX:
- 5,500 GET/HEAD requests per second per prefix
- 3,500 PUT/COPY/POST/DELETE requests per second per prefix

"Prefix" = any common leading string in object keys.
All objects under s3://bucket/data/ share the "data/" prefix limit.

100 Glue workers × 50 files/sec = 5,000 GET/s (close to limit)
Add concurrent Athena queries + other jobs = EXCEEDED
```

### Fix
```python
# Fix 1: Hash-distribute S3 keys (prevents hot prefix)
# Instead of: s3://bucket/data/2024/01/15/file_001.parquet
# Use:        s3://bucket/data/a7b3/2024/01/15/file_001.parquet
#             s3://bucket/data/c2d1/2024/01/15/file_001.parquet
# 256 hash prefixes → each gets independent 5500 req/s limit
# Total: 256 × 5500 = 1.4M requests/second capacity!

import hashlib
def distributed_s3_path(key, num_buckets=256):
    hash_prefix = hashlib.md5(key.encode()).hexdigest()[:4]
    return f"s3://bucket/data/{hash_prefix}/{key}"

# Fix 2: Request S3 prefix limit increase (for known hot prefixes)
# Contact AWS Support → provide prefix and expected request rate
# S3 auto-scales but takes 15-30 minutes to adapt to new patterns

# Fix 3: Throttle Glue read rate
spark.conf.set("spark.hadoop.fs.s3a.connection.maximum", "50")  # Limit connections
spark.conf.set("spark.hadoop.fs.s3a.threads.max", "20")  # Limit concurrent requests
# Fewer concurrent requests = stay under limit

# Fix 4: Use S3 Inventory instead of LIST for discovery
# Pre-computed file list (CSV/Parquet) → no LIST calls needed
# Glue reads inventory file, then accesses data files directly

# Fix 5: Stagger reads across time
# Job 1 reads prefix A, Job 2 reads prefix B (no contention)
# Schedule jobs accessing same prefix at different times

# Fix 6: Enable S3 request metrics to identify hot prefixes
# CloudWatch → S3 → Request metrics → Filter by prefix
# Identify which prefix is hitting the limit
```

---

## Issue #64: Glue Data Catalog Partition Limit

### Severity: P2 | Frequency: Monthly as tables grow

### Symptoms
```
# Error: "Number of partitions exceeded the limit of 10,000,000"
# OR: GetPartitions call takes 60+ seconds (timeout)
# OR: Crawler takes 8+ hours to process all partitions
# Table with hourly partitions × 5 years = 43,800 partitions per year
```

### Root Cause
```
Glue Data Catalog limits:
- 10,000,000 partitions per table (hard limit)
- GetPartitions: max 1000 per call (pagination required)
- BatchCreatePartition: max 100 per call
- Listing millions of partitions: API throttling

Table with: year/month/day/hour/region partitions:
5 years × 365 × 24 × 10 regions = 438,000 partitions
Not at limit yet, but listing is SLOW.
```

### Fix
```python
# Fix 1: Reduce partition granularity
# Instead of: year/month/day/hour/region (438K partitions)
# Use:        date/region (18,250 partitions) with hour as column
# Query pushdown on date+region, then filter hour in Spark

# Fix 2: Use Iceberg (partition metadata in manifest, not catalog)
# Iceberg: no catalog partition limit (partitions tracked in metadata files)
# Millions of "partitions" stored efficiently in manifest

# Fix 3: Archive old partitions
# Move partitions older than 1 year to separate "archive" table
# Active table: ~8,760 partitions (1 year × 24 hours × 365)
# Archive table: older data (queried rarely)

# Fix 4: Use partition indexes (Glue 2021 feature)
# Reduces GetPartitions latency from O(n) to O(log n)
glue.create_partition_index(
    DatabaseName='db',
    TableName='events',
    PartitionIndex={
        'Keys': ['date', 'region'],
        'IndexName': 'date_region_idx'
    }
)

# Fix 5: Batch partition operations
def batch_create_partitions(database, table, partitions, batch_size=100):
    """Create partitions in batches to avoid throttling."""
    glue = boto3.client('glue')
    for i in range(0, len(partitions), batch_size):
        batch = partitions[i:i+batch_size]
        try:
            glue.batch_create_partition(
                DatabaseName=database,
                TableName=table,
                PartitionInputList=batch
            )
        except glue.exceptions.ThrottlingException:
            time.sleep(2)  # Back off and retry
            glue.batch_create_partition(
                DatabaseName=database, TableName=table, PartitionInputList=batch
            )
```

---

## Issue #65: DPU (Data Processing Unit) Quota Exhaustion

### Severity: P1 | Frequency: During peak load

### Symptoms
```
# Jobs sitting in WAITING state for hours
# No error - just won't start
# AWS Console shows: "Waiting for resources"
# Account has reached max DPU capacity

# Total DPU usage: 20 jobs × 50 DPU = 1000 DPU (default limit)
# New job request: QUEUED until DPU freed
```

### Fix
```python
# Fix 1: Right-size jobs (most jobs over-provisioned)
# Analyze: CloudWatch → Glue Job Metrics → glue.ALL.system.cpuSystemLoad
# If avg CPU < 30%: reduce workers by 50%

# Fix 2: Use Flex execution for non-SLA workloads
# Flex uses spot-like capacity (doesn't count toward standard DPU quota)
# 60% cheaper, but may have start delay

# Fix 3: Stagger execution windows
# Not all 100 jobs need to run simultaneously
# Create execution tiers:
# Tier 1 (SLA): 00:00-01:00 (50 DPU × 10 jobs = 500 DPU)
# Tier 2 (important): 01:00-03:00 (30 DPU × 15 jobs = 450 DPU)  
# Tier 3 (best-effort): 03:00-06:00 (20 DPU × 20 jobs = 400 DPU)
# Peak: 500 DPU (well within 1000 limit)

# Fix 4: Request DPU limit increase
# Service Quotas → AWS Glue → Max DPUs → Request 3000-5000

# Fix 5: Auto-terminate idle jobs
# Monitor: if job outputs 0 records for > 10 minutes, kill it
# Frees DPU for waiting jobs
```

---

## Issue #66: Crawler Concurrent Run Conflicts

### Severity: P2 | Frequency: When crawlers overlap with jobs

### Symptoms
```
# Crawler updates table schema WHILE Glue job is reading it
# Job reads stale/incorrect schema mid-execution
# OR: Crawler and job both try to update partition simultaneously
# Error: "ConditionalCheckFailedException" or version conflict
```

### Fix
```python
# Fix 1: Don't run crawlers and jobs simultaneously on same table
# Schedule: Crawler finishes → Trigger → Job starts
# Glue Workflow:
# Crawler trigger → Wait for SUCCEEDED → Job trigger

# Fix 2: Use event-driven partitions (skip crawler entirely)
# When new data lands: Lambda adds partition via API (no crawler needed)
import boto3

def add_partition(event, context):
    """Lambda triggered by S3 PutObject → adds Glue partition."""
    glue = boto3.client('glue')
    
    # Parse S3 path for partition values
    key = event['Records'][0]['s3']['object']['key']
    # key = "data/date=2024-01-15/hour=10/file.parquet"
    parts = parse_partition_path(key)
    
    glue.create_partition(
        DatabaseName='db',
        TableName='events',
        PartitionInput={
            'Values': [parts['date'], parts['hour']],
            'StorageDescriptor': {
                'Location': f"s3://bucket/data/date={parts['date']}/hour={parts['hour']}/",
                'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                'SerdeInfo': {'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'}
            }
        }
    )

# Fix 3: Use Iceberg (no crawler needed, self-describing metadata)
# Iceberg COMMIT is atomic → no race condition between writers and readers
```

---

## Issue #67: Lake Formation Permission Propagation Delay

### Severity: P2 | Frequency: After permission changes

### Symptoms
```
# Lake Formation permission granted at 10:00 AM
# Job started at 10:01 AM → AccessDeniedException
# Job started at 10:05 AM → WORKS
# Permissions have eventual consistency (~2-5 minutes)
```

### Fix
```python
# Fix 1: Add delay after permission changes before running jobs
import time

def grant_and_wait(database, table, principal, permissions, wait_seconds=300):
    """Grant permission and wait for propagation."""
    lf = boto3.client('lakeformation')
    lf.grant_permissions(
        Principal={'DataLakePrincipal': {'DataLakePrincipalIdentifier': principal}},
        Resource={'Table': {'DatabaseName': database, 'Name': table}},
        Permissions=permissions
    )
    logger.info(f"Permission granted. Waiting {wait_seconds}s for propagation...")
    time.sleep(wait_seconds)

# Fix 2: Retry with backoff on AccessDeniedException
from botocore.exceptions import ClientError

def read_with_permission_retry(database, table, max_retries=5):
    for attempt in range(max_retries):
        try:
            return glueContext.create_dynamic_frame.from_catalog(
                database=database, table_name=table
            )
        except ClientError as e:
            if 'AccessDeniedException' in str(e) and attempt < max_retries - 1:
                wait = 30 * (2 ** attempt)  # 30s, 60s, 120s, 240s
                logger.warning(f"Permission not propagated. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

# Fix 3: Pre-validate permissions before job execution
# Add pre-flight check in orchestrator
```

---

## Issue #68: Spark UI Port Conflicts (Multiple Jobs on Same Cluster)

### Severity: P3 | Frequency: Not applicable to Glue (serverless)
### Note: Included because people migrating from EMR expect this. Glue handles it automatically.

---

## Issue #69: Rate Limiting on Glue GetTable/GetPartitions

### Severity: P2 | Frequency: Daily with many concurrent queries

### Symptoms
```
# Athena + Glue + Spark all calling GetTable simultaneously
# Error: ThrottlingException on GetPartitions
# All services sharing same Glue Catalog → contention
```

### Fix
```python
# Fix 1: Cache catalog metadata in jobs
# Read table metadata ONCE at job start, reuse throughout:
table_schema = glueContext.get_table("db", "events")
# Don't call get_table() in a loop or per-partition

# Fix 2: Use Glue Data Catalog resource links for isolation
# Create separate catalog databases for different access patterns:
# "db_etl" (for Glue jobs) - lower partition listing frequency
# "db_analytics" (for Athena) - higher read frequency
# Both point to same S3 data via resource links

# Fix 3: Batch partition operations
# Instead of 10000 individual GetPartition calls:
response = glue.get_partitions(
    DatabaseName='db',
    TableName='events',
    Expression="date >= '2024-01-01'",  # Server-side filter
    MaxResults=1000  # Batch
)
# Fewer API calls = less throttling

# Fix 4: Use Iceberg catalog (separate from Glue Catalog API limits)
# Iceberg reads metadata from S3 manifest files
# No GetPartitions API call needed!
```

---

## Issue #70: Worker Startup Timeout (Cold Start at Scale)

### Severity: P2 | Frequency: Every job start

### Symptoms
```
# Job requested 200 workers
# After 10 minutes: only 150 workers available
# Remaining 50 workers: "Waiting for resources"
# Job starts with partial capacity → slower than expected

# Worse case: ALL workers timeout → job fails before processing starts
# Error: "Unable to allocate resources for job within timeout period"
```

### Root Cause
```
Glue worker provisioning:
1. Request capacity from EC2 fleet (serverless, but backed by EC2)
2. Pull and configure Spark container image
3. Initialize Spark executor
4. Register with driver

Each step can fail or timeout:
- EC2 capacity: InsufficientCapacity in AZ
- Container pull: network congestion
- Spark init: large job with many JARs
- Registration: driver overwhelmed by 200 simultaneous registrations
```

### Fix
```python
# Fix 1: Use warm pools (auto-scaling from baseline)
# Set minimum workers (always warm):
# NumberOfWorkers: 50 (always available, instant start)
# MaxCapacity: 200 (scales up to 200 when needed)
# Workers 1-50: instant start
# Workers 51-200: cold start (2-5 minutes)

# Fix 2: Avoid requesting exactly at popular times
# Everyone requests at :00 minutes → capacity contention
# Offset by random seconds

# Fix 3: Use smaller worker types (more available capacity)
# G.4X workers: limited supply in some AZs
# G.1X workers: abundantly available everywhere
# Use G.1X with more workers instead of G.4X with fewer

# Fix 4: Pre-warm with dummy job
# Run a 1-minute job 5 minutes before critical job
# This "warms" the capacity allocation path
# Not guaranteed but helps in practice

# Fix 5: Handle partial capacity gracefully
# Configure job to work with fewer workers (slower but doesn't fail):
spark.conf.set("spark.dynamicAllocation.enabled", "true")
spark.conf.set("spark.dynamicAllocation.minExecutors", "10")  # Start with 10
# Job begins immediately with 10 workers, scales up as more become available
```

---

## Concurrency Best Practices

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONCURRENCY MANAGEMENT AT SCALE                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  API Throttling:                                                     │
│  ✓ Use adaptive retry in all AWS SDK calls                          │
│  ✓ Stagger job start times (hash-based offset)                      │
│  ✓ Batch API calls where possible                                   │
│  ✓ Request limit increases for production accounts                  │
│  ✓ Monitor API call counts in CloudWatch                            │
│                                                                      │
│  Resource Limits:                                                    │
│  ✓ Track DPU usage vs quota (alert at 80%)                         │
│  ✓ Use Flex execution for non-critical workloads                    │
│  ✓ Right-size workers (don't waste DPU on idle jobs)               │
│  ✓ Implement job priority queue                                     │
│                                                                      │
│  S3 Throttling:                                                      │
│  ✓ Hash-distribute S3 prefixes                                      │
│  ✓ Use S3 Inventory instead of LIST                                 │
│  ✓ Limit concurrent connections per job                             │
│  ✓ Monitor S3 request metrics                                       │
│                                                                      │
│  Catalog Contention:                                                 │
│  ✓ Use Iceberg for metadata (bypasses Catalog API limits)           │
│  ✓ Cache catalog metadata in jobs                                   │
│  ✓ Separate crawlers from job execution windows                     │
│  ✓ Use partition indexes for large tables                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
