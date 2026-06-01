# Job Bookmark Issues (#16-25)

> Job Bookmarks are Glue's mechanism for **incremental processing** — tracking what data has
> already been processed to avoid reprocessing. When bookmarks fail, you get **data duplication**
> or **data loss** — both catastrophic in production.

---

## Issue #16: Job Bookmark Corruption After Mid-Job Failure

### Severity: P1 | Frequency: Monthly (but catastrophic)

### Symptoms
```
# Scenario: Job fails at 70% completion
# On retry: Job processes 0 records (bookmark advanced past failure point)
# Result: 30% of data permanently lost unless manually backfilled

# CloudWatch Logs:
"Job bookmark: Processing files from timestamp X to Y"
# But files between X and Y were never successfully written to output
```

### Root Cause
```
┌─────────────────────────────────────────────────────────────────────┐
│  BOOKMARK CORRUPTION TIMELINE                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Time ──────────────────────────────────────────────────────▶       │
│                                                                      │
│  T1: Job starts, reads bookmark position = file_100                  │
│  T2: Processes file_101 to file_200 (reads all into memory)         │
│  T3: Writes output for file_101 to file_170                         │
│  T4: ❌ FAILURE (OOM/timeout) at file_171                           │
│  T5: Glue commits bookmark = file_200 (ALREADY ADVANCED!)          │
│                                                                      │
│  T6: Job retries, bookmark says "start at file_201"                 │
│  T7: file_171 to file_200 are NEVER processed = DATA LOSS          │
│                                                                      │
│  Root cause: Bookmark advances based on INPUT read position,        │
│  not OUTPUT write completion.                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Fix
```python
# Fix 1: Use job.commit() ONLY after successful write verification
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ['JOB_NAME'])
glueContext = GlueContext(SparkContext.getOrCreate())
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

try:
    # Process data
    output_df = process_data(input_dyf)
    
    # Write output
    output_df.write.mode("append").parquet("s3://output/")
    
    # VERIFY write succeeded before committing bookmark
    written_count = spark.read.parquet("s3://output/latest_partition/").count()
    if written_count == 0:
        raise Exception("Write verification failed - 0 records written")
    
    # ONLY commit bookmark after verified write
    job.commit()
    
except Exception as e:
    logger.error(f"Job failed: {e}")
    # Do NOT call job.commit() - bookmark stays at previous position
    # Next run will reprocess from last successful position
    raise

# Fix 2: Implement idempotent writes (safe to reprocess)
output_df.write \
    .mode("overwrite") \
    .partitionBy("date", "hour") \
    .parquet("s3://output/")
# Overwrite per-partition means reprocessing is safe

# Fix 3: Use Iceberg MERGE for idempotent output
spark.sql("""
    MERGE INTO output_table t
    USING new_data s
    ON t.id = s.id AND t.event_time = s.event_time
    WHEN NOT MATCHED THEN INSERT *
""")
# Duplicate inserts are safely ignored
```

### Prevention
```python
# Add bookmark health check at job start
def verify_bookmark_consistency(job_name, expected_max_gap_hours=4):
    """Verify bookmark hasn't jumped too far ahead."""
    import boto3
    glue_client = boto3.client('glue')
    
    response = glue_client.get_job_bookmark(JobName=job_name)
    bookmark_ts = response['JobBookmarkEntry']['JobBookmark']
    
    gap_hours = (datetime.now() - parse_bookmark_ts(bookmark_ts)).total_seconds() / 3600
    
    if gap_hours > expected_max_gap_hours:
        alert(f"Bookmark gap: {gap_hours}h. Possible data loss!")
        # Consider resetting bookmark for backfill
```

---

## Issue #17: Job Bookmark Not Advancing (Infinite Reprocessing Loop)

### Severity: P2 | Frequency: Weekly

### Symptoms
```
# Job runs successfully (exit code 0) but processes the SAME data every time
# DPU-hours increasing: same data processed repeatedly = cost waste
# Downstream: duplicate records appearing in output tables

# CloudWatch metrics show:
# glue.driver.aggregate.bytesRead = constant across runs (should decrease)
```

### Root Cause
```
Common causes:
1. job.commit() never called (exception before commit line)
2. Job parameter --job-bookmark-option not set to "job-bookmark-enable"
3. Transformation context not using bookmark-aware read
4. Source path changed (bookmark tracks specific S3 prefix)
5. File modification timestamps reset (S3 copy resets mtime)
```

### Fix
```python
# Verify bookmark is enabled in job parameters:
# --job-bookmark-option = job-bookmark-enable

# Ensure reading through bookmark-aware API:
# WRONG (bypasses bookmarks):
df = spark.read.parquet("s3://bucket/data/")

# RIGHT (uses bookmarks):
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="my_db",
    table_name="my_table",
    transformation_ctx="my_transform_ctx"  # CRITICAL: unique context name
)

# CRITICAL: transformation_ctx must be:
# 1. Unique per read operation in the job
# 2. Consistent across job runs (don't use timestamps/random values)
# 3. Stable if code is refactored

# Ensure job.commit() is always reached:
try:
    process()
    job.commit()
except Exception as e:
    # Still commit if partial processing is acceptable
    # OR don't commit to retry from same position
    logger.error(e)
    raise  # Don't commit on failure
```

---

## Issue #18: Bookmark State Explosion (Millions of File Entries)

### Severity: P2 | Frequency: Monthly at high-volume sources

### Symptoms
```
# Job startup takes 10+ minutes before processing begins
# CloudWatch shows: "Retrieving job bookmark" phase takes 600+ seconds
# Job bookmark state size: >100MB
# GetJobBookmark API calls timing out
```

### Root Cause
```
Job bookmark stores entry for EVERY file ever processed.
At 100K files/day × 365 days = 36.5M entries in bookmark state.

Bookmark state is loaded into driver memory at job start.
Large state → slow start → possible OOM during bookmark load.
```

### Fix
```python
# Fix 1: Reset bookmark periodically and rely on partition filtering
import boto3

def reset_bookmark_with_new_start(job_name, start_date):
    """Reset bookmark and use date partition as starting point."""
    glue_client = boto3.client('glue')
    glue_client.reset_job_bookmark(JobName=job_name)
    
    # Use explicit date filter instead of bookmark for recent data
    # Bookmark will track from this point forward
    
# Fix 2: Use date-partitioned reads instead of bookmarks for large tables
# Instead of bookmark tracking 36M files:
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="events",
    push_down_predicate=f"date >= '{yesterday}'",  # Only read recent
    transformation_ctx="events_read"
)
# Bookmark only tracks files within the predicate window

# Fix 3: Partition source data to reduce bookmark scope
# Organize S3 data as: s3://bucket/data/year=2024/month=01/day=15/
# Glue bookmark only needs to track files in current partition

# Fix 4: Use custom bookmark management for extreme scale
class CustomBookmark:
    """Track processing position in DynamoDB instead of Glue bookmark."""
    def __init__(self, job_name, table_name="etl_bookmarks"):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.job_name = job_name
    
    def get_position(self):
        response = self.table.get_item(Key={'job_name': self.job_name})
        return response.get('Item', {}).get('last_processed_ts')
    
    def update_position(self, new_ts):
        self.table.put_item(Item={
            'job_name': self.job_name,
            'last_processed_ts': new_ts,
            'updated_at': datetime.now().isoformat()
        })
```

---

## Issue #19: Bookmark Incompatibility After Schema Changes

### Severity: P2 | Frequency: On every schema evolution

### Symptoms
```
# After adding/removing columns from source table:
# Job fails with: "Bookmark state incompatible with current schema"
# OR: Job silently skips records that don't match bookmark schema fingerprint
```

### Root Cause
```
Job bookmarks encode schema information. When source schema changes:
- New columns added → bookmark doesn't know about them
- Columns renamed → bookmark references old names
- Partition scheme changed → bookmark tracks old partitions
- Table recreated → bookmark references deleted metadata version
```

### Fix
```python
# Fix 1: Reset bookmark on schema change (deploy script)
import boto3

def deploy_with_bookmark_reset(job_name, schema_version):
    """Reset bookmark when schema version changes."""
    ssm = boto3.client('ssm')
    glue = boto3.client('glue')
    
    # Check if schema version changed
    current = ssm.get_parameter(Name=f'/glue/{job_name}/schema_version')
    if current['Parameter']['Value'] != schema_version:
        glue.reset_job_bookmark(JobName=job_name)
        ssm.put_parameter(
            Name=f'/glue/{job_name}/schema_version',
            Value=schema_version,
            Overwrite=True
        )
        logger.info(f"Bookmark reset for schema change: {schema_version}")

# Fix 2: Use DynamicFrame with schema flexibility
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="table",
    transformation_ctx="ctx"
)
# DynamicFrame handles schema inconsistencies with resolveChoice
dyf = dyf.resolveChoice(specs=[
    ("new_column", "cast:string"),  # Handle new columns gracefully
])

# Fix 3: Decouple bookmark from schema
# Use timestamp-based bookmarking instead of file-content-based:
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="table",
    push_down_predicate=f"ingest_timestamp > '{last_successful_ts}'",
    transformation_ctx="timestamp_based_ctx"
)
```

---

## Issue #20: Bookmark Race Condition in Concurrent Job Runs

### Severity: P1 | Frequency: When retry overlaps with scheduled run

### Symptoms
```
# Two instances of same job run simultaneously
# Instance 1: reads bookmark position A, processes A→B
# Instance 2: reads bookmark position A, processes A→B (duplicate!)
# Instance 1 commits: bookmark = B
# Instance 2 commits: bookmark = B (no advancement, but duplicate output)
```

### Root Cause
```
Glue job bookmarks have NO locking mechanism.
If two runs overlap (manual retry + scheduled trigger, or
workflow retry concurrent with new trigger), both read the
same bookmark state.
```

### Fix
```python
# Fix 1: Prevent concurrent execution
# In Glue job properties:
# MaxConcurrentRuns = 1  (CRITICAL for bookmark-based jobs)

# Fix 2: Implement distributed lock
import boto3
from datetime import datetime, timedelta

class GlueLock:
    """DynamoDB-based lock to prevent concurrent bookmark access."""
    def __init__(self, job_name, lock_table="glue_job_locks"):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(lock_table)
        self.job_name = job_name
        self.lock_id = f"{job_name}_{datetime.now().isoformat()}"
    
    def acquire(self, ttl_minutes=60):
        try:
            self.table.put_item(
                Item={
                    'job_name': self.job_name,
                    'lock_id': self.lock_id,
                    'expires': (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat()
                },
                ConditionExpression='attribute_not_exists(job_name) OR expires < :now',
                ExpressionAttributeValues={':now': datetime.now().isoformat()}
            )
            return True
        except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            return False  # Another instance holds the lock
    
    def release(self):
        self.table.delete_item(Key={'job_name': self.job_name})

# Usage:
lock = GlueLock(args['JOB_NAME'])
if not lock.acquire():
    logger.warning("Another instance running. Exiting.")
    sys.exit(0)
try:
    process_data()
    job.commit()
finally:
    lock.release()

# Fix 3: Use idempotent writes to make duplicates harmless
# Write to Iceberg with MERGE (duplicates safely ignored)
```

---

## Issue #21: Bookmark Doesn't Work with Partitioned Source Changes

### Severity: P2 | Frequency: Common with streaming sources

### Symptoms
```
# Source: s3://bucket/events/date=2024-01-15/hour=10/
# New files added to OLD partitions (late-arriving data)
# Bookmark only tracks "new" partitions, misses backfilled files in old partitions
```

### Root Cause
```
Job bookmarks track files by:
1. S3 path prefix (partition path)
2. File modification timestamp

When late-arriving data is written to an old partition with
a CURRENT timestamp, the bookmark MAY miss it because:
- It already "processed" that partition
- Bookmark advancement is partition-ordered
```

### Fix
```python
# Fix 1: Use modification time window instead of bookmark for late data
from datetime import datetime, timedelta

# Always look back N hours for late arrivals
lookback_hours = 6
cutoff = (datetime.now() - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d %H:%M:%S")

dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="events",
    additional_options={
        "boundedFiles": "5000",  # Limit files per run
        "boundedSize": "10737418240",  # 10GB max per run
    },
    push_down_predicate=f"date >= '{two_days_ago}'",  # Window for late data
    transformation_ctx="events_with_lookback"
)

# Fix 2: Combine bookmark with deduplication
# Process with bookmark (catches new data) + 
# periodic backfill job (catches late data in old partitions)

# Main job: bookmark-based (runs every hour)
# Backfill job: full scan of last 48 hours (runs daily, dedup at write)

# Fix 3: Use event notification instead of bookmark
# S3 Event → SQS → Glue job triggered per file
# No bookmark needed - every file triggers processing
```

---

## Issue #22: Bookmark Reset Accidentally Causes Full Reprocessing

### Severity: P1 | Frequency: Human error during incidents

### Symptoms
```
# Someone resets bookmark during troubleshooting
# Next run reprocesses ALL historical data (years of data)
# Job runs for 48+ hours, costs $10K+, overwhelms downstream
# Downstream tables have massive duplicates
```

### Root Cause
```
Bookmark reset (via console or API) removes ALL tracking state.
Next run sees entire S3 path as "new" data.
No guardrail prevents processing petabytes of history.
```

### Fix
```python
# Fix 1: Add safety guard at job start
import boto3
from datetime import datetime, timedelta

def guard_against_full_reprocessing(max_files=100000, max_size_gb=500):
    """Abort if about to process unreasonably large dataset."""
    s3 = boto3.client('s3')
    
    # Count files that would be processed
    paginator = s3.get_paginator('list_objects_v2')
    file_count = 0
    total_size = 0
    
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get('Contents', []):
            file_count += 1
            total_size += obj['Size']
            
            if file_count > max_files:
                raise Exception(
                    f"SAFETY GUARD: Would process {file_count}+ files. "
                    f"Bookmark may have been reset. Manual review required."
                )
    
    size_gb = total_size / (1024**3)
    if size_gb > max_size_gb:
        raise Exception(
            f"SAFETY GUARD: Would process {size_gb:.0f}GB. "
            f"Expected max {max_size_gb}GB. Aborting."
        )

# Fix 2: After bookmark reset, set explicit date boundary
# Reset bookmark BUT add filter to prevent full history scan:
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="events",
    push_down_predicate="date >= '2024-01-01'",  # Limit reprocessing window
    transformation_ctx="ctx"
)

# Fix 3: Restrict bookmark reset access
# IAM policy - deny ResetJobBookmark except from CI/CD role with approval
{
    "Effect": "Deny",
    "Action": "glue:ResetJobBookmark",
    "Resource": "arn:aws:glue:*:*:job/production-*",
    "Condition": {
        "StringNotEquals": {
            "aws:PrincipalTag/role": "glue-admin"
        }
    }
}
```

---

## Issue #23: Bookmark Inconsistency Across Job Versions (Deploy Gap)

### Severity: P2 | Frequency: On every deployment

### Symptoms
```
# Deploy new version of Glue job code
# New version processes data differently (new columns, new logic)
# Bookmark says "already processed file X" but new logic never saw it
# New logic's output is incomplete for the transition period
```

### Root Cause
```
Timeline:
1. Job v1 processes files up to timestamp T1 (bookmark at T1)
2. Deploy v2 (changes output schema, adds columns)
3. Job v2 starts at T1 (bookmark position)
4. Files processed by v1 are NOT reprocessed by v2
5. Output has gap: files before T1 have old schema, after T1 have new

If downstream expects new columns for ALL data → broken queries
```

### Fix
```python
# Fix 1: Blue-green deployment with overlap
# Deploy v2 as NEW job (different name = different bookmark)
# Run v2 alongside v1 for overlap period
# v2 processes from T1 - 24h (overlap window)
# After v2 catches up, disable v1

# Fix 2: Backfill job after deployment
def post_deploy_backfill(job_name, backfill_days=7):
    """Run backfill after deploying new version."""
    glue = boto3.client('glue')
    
    # Start backfill run with explicit date range
    glue.start_job_run(
        JobName=job_name,
        Arguments={
            '--backfill_start': (datetime.now() - timedelta(days=backfill_days)).isoformat(),
            '--backfill_end': datetime.now().isoformat(),
            '--job-bookmark-option': 'job-bookmark-disable'  # Ignore bookmark for backfill
        }
    )

# Fix 3: Version-aware output paths
# Write to: s3://output/v2/date=2024-01-15/
# Downstream reads union of v1 and v2 during migration
# After backfill complete, switch to v2 only
```

---

## Issue #24: Bookmark Fails with Custom Data Sources (Non-S3)

### Severity: P2 | Frequency: Common with JDBC/Kafka sources

### Symptoms
```
# JDBC source: bookmark doesn't track which rows were processed
# Kafka source: bookmark doesn't track consumer offsets correctly
# DynamoDB source: bookmark doesn't handle scan position
# API source: no bookmark support at all
```

### Root Cause
```
Glue bookmarks work best with S3 (file-based tracking).
For other sources, bookmark behavior varies:
- JDBC: tracks based on specified bookmark key column
- Kafka: limited offset tracking (prefer Kafka's own offset management)
- DynamoDB: no native bookmark support
- Custom connectors: bookmark must be manually implemented
```

### Fix
```python
# Fix for JDBC: Use bookmark key column
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="jdbc_table",
    additional_options={
        "jobBookmarkKeys": ["updated_at"],  # Column to track position
        "jobBookmarkKeysSortOrder": "asc"   # Process oldest first
    },
    transformation_ctx="jdbc_incremental"
)

# Fix for Kafka: Use Kafka's own offset management
# Don't rely on Glue bookmarks for Kafka - use checkpointing
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "broker:9092") \
    .option("subscribe", "topic") \
    .option("startingOffsets", "earliest") \
    .option("checkpointLocation", "s3://checkpoints/kafka-job/") \
    .load()
# Checkpoints handle offset tracking, not bookmarks

# Fix for DynamoDB: Custom high-water mark
class DynamoDBBookmark:
    """Custom bookmark for DynamoDB scan jobs."""
    def __init__(self, job_name):
        self.ssm = boto3.client('ssm')
        self.param_name = f'/glue/bookmarks/{job_name}/dynamo_position'
    
    def get_last_processed(self):
        try:
            return self.ssm.get_parameter(Name=self.param_name)['Parameter']['Value']
        except:
            return "1970-01-01T00:00:00Z"
    
    def update(self, new_position):
        self.ssm.put_parameter(Name=self.param_name, Value=new_position, Overwrite=True)

# Usage:
bookmark = DynamoDBBookmark(args['JOB_NAME'])
last_ts = bookmark.get_last_processed()

# Query DynamoDB for records after bookmark position
# Process...
bookmark.update(max_processed_timestamp)
```

---

## Issue #25: Job Bookmark and Auto-Scaling Interaction Bug

### Severity: P3 | Frequency: Intermittent with auto-scaling enabled

### Symptoms
```
# With auto-scaling enabled:
# Some files processed twice (minor duplicates in output)
# Bookmark position inconsistent after scale-down event
# Job succeeds but output count doesn't match input count
```

### Root Cause
```
When auto-scaling removes executors mid-job:
1. Executor processing file X is terminated
2. Task for file X is re-scheduled on remaining executor
3. If output was partially written before termination...
4. Re-execution writes again = duplicate output
5. Bookmark advances past file X (counted as processed)

This is rare but happens during aggressive scale-down.
```

### Fix
```python
# Fix 1: Use speculative execution settings
spark.conf.set("spark.speculation", "false")  # Disable speculation with bookmarks
# Speculation can cause duplicate processing

# Fix 2: Write output atomically per batch
# Instead of streaming writes, buffer and commit:
def atomic_write(df, output_path, partition_cols):
    """Write atomically - all or nothing per batch."""
    temp_path = f"{output_path}/_temp_{uuid4()}"
    
    # Write to temp location
    df.write.partitionBy(partition_cols).parquet(temp_path)
    
    # Atomic rename (S3 doesn't support rename, use Iceberg instead)
    # For S3: use Iceberg MERGE for atomicity
    
# Fix 3: Use Iceberg for exactly-once output semantics
# Iceberg commits are atomic - partial writes are invisible
df.writeTo("catalog.db.output_table") \
    .option("merge-schema", "true") \
    .append()
# If task retries, Iceberg commit either succeeds fully or not at all

# Fix 4: Set conservative auto-scaling
# --conf spark.dynamicAllocation.enabled=true
# --conf spark.dynamicAllocation.executorIdleTimeout=120s  # Wait longer before removing
# --conf spark.dynamicAllocation.cachedExecutorIdleTimeout=300s
```

---

## Bookmark Best Practices Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│  JOB BOOKMARK PRODUCTION CHECKLIST                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ✓ Always set MaxConcurrentRuns = 1 for bookmark jobs               │
│  ✓ Use unique, stable transformation_ctx per read operation          │
│  ✓ Call job.commit() ONLY after verified successful write            │
│  ✓ Implement safety guard against full reprocessing                  │
│  ✓ Make output writes idempotent (MERGE/overwrite per partition)     │
│  ✓ Monitor bookmark state size monthly                               │
│  ✓ Test bookmark behavior with schema changes before deploying      │
│  ✓ Use date predicates as defense-in-depth alongside bookmarks      │
│  ✓ Restrict ResetJobBookmark to admin role only                      │
│  ✓ Have backfill procedure documented for bookmark failures          │
│  ✓ For non-S3 sources, implement custom bookmark management         │
│  ✓ After deploys, validate bookmark position vs expected             │
│                                                                      │
│  When NOT to use bookmarks:                                          │
│  ✗ Kafka sources (use Spark checkpointing)                          │
│  ✗ Full-refresh jobs (no incremental logic)                          │
│  ✗ Complex multi-source jobs (custom tracking better)                │
│  ✗ Sources with mutable files (bookmark tracks immutable files)      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
