# Data Quality & Corruption Issues (#81-90)

> Data quality issues are the **most expensive** Glue problems — not in compute cost, but in
> **business impact**. A silent corruption that reaches production reports can invalidate months
> of business decisions, trigger regulatory violations, or cause customer-facing outages.

---

## Issue #81: Silent Data Corruption from Type Coercion

### Severity: P1 | Frequency: Ongoing (undetected for weeks)

### Symptoms
```
# Revenue report shows $0 for 15% of transactions
# Investigation reveals: "amount" column has some values as string "19.99"
# Spark silently coerces non-matching types to NULL
# No error, no warning, no alert → discovered weeks later by finance team

# Impact: $12M in "missing" revenue on executive dashboard
```

### Root Cause
```
Spark's default behavior with type mismatches:
- mode="PERMISSIVE" (default): malformed records → null values, no error
- This means: if schema says INT but data has "abc" → silent null

In JSON/CSV sources without strict schema enforcement:
File 1: {"amount": 19.99}        → correctly read as double
File 2: {"amount": "19.99"}      → NULL if schema is DoubleType!
File 3: {"amount": "N/A"}        → NULL (expected, but same as file 2 bug)

You CAN'T distinguish "intentional null" from "corruption null"
```

### Fix
```python
# Fix 1: Use FAILFAST mode for critical pipelines
df = spark.read \
    .option("mode", "FAILFAST") \
    .schema(explicit_schema) \
    .json("s3://data/transactions/")
# Job FAILS immediately on type mismatch (better than silent corruption)

# Fix 2: Use DROPMALFORMED + count dropped records
df = spark.read \
    .option("mode", "DROPMALFORMED") \
    .option("badRecordsPath", "s3://data-quality/bad-records/") \
    .schema(explicit_schema) \
    .json("s3://data/transactions/")

# Count bad records
bad_count = spark.read.json("s3://data-quality/bad-records/").count()
if bad_count > 0:
    alert(f"QUALITY: {bad_count} malformed records detected")
    if bad_count / total_count > 0.01:  # >1% bad = abort
        raise Exception(f"Too many bad records: {bad_count}/{total_count}")

# Fix 3: Post-write validation
output_df = spark.read.parquet("s3://output/transactions/")
null_amount_count = output_df.filter(F.col("amount").isNull()).count()
source_null_count = source_df.filter(F.col("amount").isNull()).count()

if null_amount_count > source_null_count:
    unexpected_nulls = null_amount_count - source_null_count
    raise Exception(f"Data corruption: {unexpected_nulls} unexpected NULL amounts!")

# Fix 4: Glue Data Quality rules
# DQDL rule: Completeness "amount" >= 0.99
# Ensures at least 99% of records have non-null amount
```

---

## Issue #82: Duplicate Records from Job Retry

### Severity: P1 | Frequency: On every job failure + retry

### Symptoms
```
# Job fails at 70% → retries → reprocesses from beginning
# Output: 100% of data + 70% duplicates = 170% of expected rows
# Downstream: revenue doubled, user counts inflated
# Finance: "Why did revenue jump 70% overnight?"
```

### Fix
```python
# Fix 1: Idempotent writes using MERGE (Iceberg)
spark.sql("""
    MERGE INTO output_table t
    USING new_data s
    ON t.transaction_id = s.transaction_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")
# Safe to retry: duplicates are simply UPDATE (no duplicate inserts)

# Fix 2: Partition-level overwrite (idempotent for partition-aligned data)
df.write \
    .mode("overwrite") \
    .partitionBy("date") \
    .option("partitionOverwriteMode", "dynamic") \
    .parquet("s3://output/")
# Retrying overwrites same partitions → no duplicates

# Fix 3: Deduplication in output
from pyspark.sql.window import Window

window = Window.partitionBy("transaction_id").orderBy(F.col("processing_time").desc())
df_deduped = df.withColumn("rn", F.row_number().over(window)) \
    .filter(F.col("rn") == 1) \
    .drop("rn")

# Fix 4: Transaction ID-based dedup before write
existing_ids = spark.read.parquet("s3://output/").select("transaction_id")
new_data = source_df.join(existing_ids, "transaction_id", "left_anti")
# Only writes records that don't already exist in output
```

---

## Issue #83: Data Loss from Overwrite Mode Misuse

### Severity: P1 | Frequency: Rare but catastrophic

### Symptoms
```
# Expected: overwrite today's partition only
# Actual: overwrote ENTIRE table (all dates, all history)
# 3 years of data = GONE

# Code: df.write.mode("overwrite").parquet("s3://output/table/")
# This overwrites the ENTIRE S3 path, not just the partition!
```

### Fix
```python
# NEVER use mode("overwrite") without partitionOverwriteMode!

# BAD (destroys entire table):
df.write.mode("overwrite").parquet("s3://output/table/")

# GOOD (overwrites only affected partitions):
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
df.write \
    .mode("overwrite") \
    .partitionBy("date") \
    .parquet("s3://output/table/")
# Only partitions present in df are overwritten. Others untouched.

# BETTER (use Iceberg for atomic operations):
spark.sql("""
    DELETE FROM output_table WHERE date = '2024-01-15'
""")
df.writeTo("output_table").append()
# Atomic: either both succeed or neither does

# SAFEST: Write to new path, then swap (blue-green):
df.write.parquet("s3://output/table_v2/")
# Verify v2 is correct
# Update Glue Catalog to point to v2
# Keep v1 for 7 days as backup
```

---

## Issue #84: Schema Drift Causing Silent Column Loss

### Severity: P1 | Frequency: When upstream changes schema

### Symptoms
```
# Upstream adds new column "discount_amount" to source
# Glue job reads from Catalog (old schema, no discount_amount)
# New column silently dropped during processing
# Output table missing discount data for 2 weeks before anyone notices
```

### Fix
```python
# Fix 1: Schema drift detection at job start
def detect_schema_drift(database, table_name, expected_columns):
    """Alert on any schema changes since last run."""
    glue = boto3.client('glue')
    table = glue.get_table(DatabaseName=database, Name=table_name)
    current_cols = {c['Name'] for c in table['Table']['StorageDescriptor']['Columns']}
    
    new_columns = current_cols - expected_columns
    missing_columns = expected_columns - current_cols
    
    if new_columns:
        alert(f"Schema drift: NEW columns detected: {new_columns}")
    if missing_columns:
        raise Exception(f"Schema drift: MISSING columns: {missing_columns}")
    
    return current_cols

# Fix 2: Use DynamicFrame (automatically includes all columns)
dyf = glueContext.create_dynamic_frame.from_catalog(database="db", table_name="source")
# DynamicFrame reads ALL columns regardless of catalog schema
# New columns automatically included

# Fix 3: Use schema evolution-aware format (Iceberg)
# Iceberg explicitly tracks schema changes with versioning
# New columns: automatically added to table metadata
# Query engine always reads latest schema

# Fix 4: Automated crawler schedule (detect changes quickly)
# Run crawler every hour on active sources
# Crawler detects new columns, updates catalog
# Alert on catalog schema changes (EventBridge rule)
```

---

## Issue #85: Data Freshness Violation (Stale Data in Output)

### Severity: P2 | Frequency: Daily (SLA monitoring)

### Symptoms
```
# SLA: Dashboard data fresh within 4 hours
# Reality: Data from 8 hours ago still showing as "latest"
# Cause: Upstream delay + Glue job delay + transformation time
# No alerting: nobody noticed until executive meeting

# Freshness chain:
# Source event (T+0) → Kafka → S3 landing (T+20min) → 
# Glue job (scheduled hourly, runs 30min) → Output (T+90min best case)
# If source delays 2h: T+3.5h (still OK)
# If Glue job fails + retry: T+5.5h (SLA BREACHED)
```

### Fix
```python
# Fix 1: Freshness watermark in output
df = df.withColumn("_processing_time", F.current_timestamp())
df = df.withColumn("_source_max_event_time", F.max("event_time").over(Window.partitionBy()))

# Write watermark metadata
watermark_df = spark.createDataFrame([{
    "table": "output_table",
    "max_event_time": max_event_time,
    "processing_time": datetime.now().isoformat(),
    "freshness_seconds": (datetime.now() - max_event_time).total_seconds()
}])
watermark_df.write.mode("overwrite").json("s3://metadata/freshness/output_table/")

# Fix 2: Alert on freshness violation
def check_freshness(table_path, max_age_hours=4):
    """Check if output data is fresh enough."""
    latest_partition = get_latest_partition(table_path)
    age_hours = (datetime.now() - latest_partition_time).total_seconds() / 3600
    
    if age_hours > max_age_hours:
        page_oncall(
            f"FRESHNESS SLA BREACH: {table_path} is {age_hours:.1f}h stale "
            f"(SLA: {max_age_hours}h)"
        )

# Fix 3: Glue Data Quality rule
# DQDL: Freshness "event_time" <= 4 hours
# Automatically fails quality check if data too old
```

---

## Issue #86: Incorrect Aggregation Due to Duplicate Source Records

### Severity: P2 | Frequency: Common with at-least-once delivery

### Symptoms
```
# Revenue aggregation: SUM(amount) WHERE date = '2024-01-15'
# Expected: $1,000,000
# Actual: $1,050,000 (5% inflated)
# Cause: 5% of source records are duplicates (Kafka at-least-once delivery)
```

### Fix
```python
# Fix 1: Deduplicate at ingestion (first Glue job in pipeline)
from pyspark.sql.window import Window

# Keep latest version of each record
dedup_window = Window.partitionBy("event_id").orderBy(F.col("kafka_timestamp").desc())
df_deduped = df.withColumn("rn", F.row_number().over(dedup_window)) \
    .filter(F.col("rn") == 1) \
    .drop("rn")

# Fix 2: Use MERGE for idempotent ingestion
spark.sql("""
    MERGE INTO clean_events t
    USING raw_events s
    ON t.event_id = s.event_id
    WHEN MATCHED AND s.kafka_timestamp > t.kafka_timestamp
        THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")

# Fix 3: Bloom filter for fast dedup check
from pyspark.sql.functions import xxhash64

# Build bloom filter from existing data
existing_hashes = spark.read.parquet("s3://output/") \
    .select(xxhash64("event_id").alias("hash")) \
    .distinct()

# Filter new data against bloom filter (approximate but fast)
new_data_hashed = source_df.withColumn("hash", xxhash64("event_id"))
truly_new = new_data_hashed.join(existing_hashes, "hash", "left_anti")

# Fix 4: Design for idempotent aggregation
# Use COUNT(DISTINCT event_id) instead of COUNT(*)
# Use SUM with dedup: SUM(amount) WHERE row_number() = 1 per event_id
```

---

## Issue #87: Corrupt Parquet Files from Incomplete Writes

### Severity: P1 | Frequency: On job failure during write phase

### Symptoms
```
# Error on next read: "Could not read footer for file: s3://output/part-00042.parquet"
# OR: "Not a Parquet file" (truncated file)
# OR: File size = 0 bytes (empty file from failed write)

# Happens when job fails DURING write phase (OOM, timeout, spot termination)
```

### Fix
```python
# Fix 1: Use Iceberg (atomic commits - incomplete writes invisible)
df.writeTo("db.output_table").append()
# If write fails: no commit → no corrupt files visible to readers
# Orphan files cleaned up by Iceberg maintenance

# Fix 2: Write to temp location + atomic swap
import uuid
temp_path = f"s3://output/_temp/{uuid.uuid4()}/"
final_path = "s3://output/data/"

# Write to temp
df.write.parquet(temp_path)

# Verify temp is valid (can be read back)
verify_df = spark.read.parquet(temp_path)
assert verify_df.count() > 0

# Copy temp to final (S3 copy is atomic per file)
# Then update Glue Catalog to point to new location
# Then delete old data

# Fix 3: S3 output committer (prevents partial files)
spark.conf.set(
    "spark.sql.sources.commitProtocolClass",
    "org.apache.spark.sql.execution.datasources.SQLHadoopMapReduceCommitProtocol"
)
spark.conf.set("spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version", "2")

# Fix 4: Clean up corrupt files before read
def clean_corrupt_files(path):
    """Remove zero-byte and corrupt parquet files."""
    import boto3
    s3 = boto3.client('s3')
    
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            if obj['Size'] == 0:  # Zero-byte file
                s3.delete_object(Bucket=bucket, Key=obj['Key'])
                logger.warning(f"Deleted corrupt file: {obj['Key']}")
```

---

## Issue #88: Incorrect JOIN Results from Key Collision

### Severity: P1 | Frequency: Rare but devastating

### Symptoms
```
# Customer "John Smith" (ID=12345) getting transactions from "Jane Doe" (ID=12345)
# Wait - same ID for different customers? YES.
# Source systems use different ID schemes:
# System A: customer_id = sequential INT (12345)
# System B: customer_id = hash-based UUID ("12345..." ← coincidence!)
# JOIN matches wrong records → customer data mixed → privacy violation + wrong analytics
```

### Fix
```python
# Fix 1: Namespace all IDs with source system
df_system_a = df_a.withColumn("customer_key", F.concat(F.lit("SYS_A_"), F.col("customer_id")))
df_system_b = df_b.withColumn("customer_key", F.concat(F.lit("SYS_B_"), F.col("customer_id")))

# Join on namespaced key (no collisions)
result = df_system_a.join(df_system_b, "customer_key")

# Fix 2: Use composite keys for cross-system joins
# Join on: (source_system, customer_id) instead of just customer_id
result = df_a.join(df_b,
    (df_a.source_system == df_b.source_system) & 
    (df_a.customer_id == df_b.customer_id)
)

# Fix 3: Master Data Management (MDM) layer
# Resolve identities BEFORE join:
# customer_id (source) → golden_customer_id (MDM)
mdm_mapping = spark.read.table("mdm.customer_xref")
df_a_resolved = df_a.join(mdm_mapping, 
    (df_a.customer_id == mdm_mapping.source_id) & 
    (mdm_mapping.source_system == "SYS_A")
)

# Fix 4: Validate join cardinality post-join
pre_count = df_a.count()
post_count = result.count()
if post_count > pre_count * 1.1:  # >10% expansion
    raise Exception(f"Suspicious join expansion: {pre_count} → {post_count}")
```

---

## Issue #89: Timezone-Induced Data Duplication in Daily Aggregations

### Severity: P2 | Frequency: Every timezone boundary

### Symptoms
```
# Daily revenue report for Jan 15: $10.5M
# Same report computed at different time: $10.2M (different!)
# 3% discrepancy: events near midnight assigned to wrong day
# Depending on WHEN the job runs, different events fall in "today"
```

### Fix
```python
# Fix 1: ALWAYS aggregate in UTC, convert at display layer
# All events stored as UTC timestamps
# Aggregate on UTC date boundaries:
df_daily = df.withColumn("date_utc", F.to_date("event_time_utc")) \
    .groupBy("date_utc") \
    .agg(F.sum("amount").alias("revenue"))

# For local-time reporting: convert AFTER aggregation
# "Show me Jan 15 PST revenue" =
# UTC: Jan 15 08:00:00 to Jan 16 08:00:00 (PST = UTC-8)
df_pst = df.filter(
    (F.col("event_time_utc") >= "2024-01-15 08:00:00") &
    (F.col("event_time_utc") < "2024-01-16 08:00:00")
).agg(F.sum("amount"))

# Fix 2: Use event_time for aggregation, not processing_time
# BAD: groupBy(F.to_date("processing_time"))  ← varies by when job runs
# GOOD: groupBy(F.to_date("event_time"))  ← deterministic

# Fix 3: Ensure aggregation window is closed before running
# Don't aggregate "today" until tomorrow (ensures all events arrived)
yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
df = df.filter(F.col("date_utc") == yesterday)  # Only process completed days
```

---

## Issue #90: Data Lineage Loss (Can't Trace Errors Back to Source)

### Severity: P2 | Frequency: On every debugging session

### Symptoms
```
# Dashboard shows wrong number
# Question: "Which source record caused this wrong output?"
# Answer: ¯\_(ツ)_/¯ (no lineage tracking)
# Debugging time: 2 days to trace manually through 5 pipeline stages
```

### Fix
```python
# Fix 1: Add lineage columns to every transformation
df = df.withColumn("_source_file", F.input_file_name())
df = df.withColumn("_source_system", F.lit("order_service"))
df = df.withColumn("_pipeline_version", F.lit("v2.3.1"))
df = df.withColumn("_processed_at", F.current_timestamp())
df = df.withColumn("_job_run_id", F.lit(args['JOB_RUN_ID']))

# Fix 2: Use OpenLineage integration
# Glue emits lineage events to OpenLineage-compatible server
# Track: which jobs read/wrote which tables, when, with what code version

# Fix 3: Record transformation metadata per batch
lineage_record = {
    "job_name": args['JOB_NAME'],
    "run_id": args['JOB_RUN_ID'],
    "input_tables": ["raw.events", "dim.customers"],
    "output_tables": ["clean.events"],
    "input_record_count": input_count,
    "output_record_count": output_count,
    "filters_applied": ["date >= 2024-01-15", "status != 'CANCELLED'"],
    "transformations": ["dedup by event_id", "join with customers", "aggregate by date"],
    "code_version": "git:abc123",
    "started_at": job_start_time,
    "completed_at": datetime.now().isoformat()
}
# Write to lineage table
spark.createDataFrame([lineage_record]).write.mode("append").json("s3://lineage/runs/")

# Fix 4: Enable Glue job lineage (built-in)
# In Glue job properties: Enable "Generate job lineage"
# Automatically tracks inputs → outputs in Glue Catalog metadata
```

---

## Data Quality Prevention Framework

```
┌─────────────────────────────────────────────────────────────────────┐
│  DATA QUALITY LAYERS (Defense in Depth)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Layer 1: INGESTION GATE                                             │
│  ├── Schema validation (FAILFAST mode)                               │
│  ├── Type enforcement (explicit schema, not inferred)                │
│  ├── Bad records quarantine (badRecordsPath)                         │
│  └── Source freshness check (is data recent enough?)                 │
│                                                                      │
│  Layer 2: TRANSFORMATION VALIDATION                                  │
│  ├── Row count assertions (input vs output within tolerance)         │
│  ├── Null rate monitoring (detect unexpected nulls)                  │
│  ├── Key uniqueness validation (no unintended duplicates)           │
│  ├── Referential integrity (FK exists in dimension)                  │
│  └── Value range checks (amount > 0, date in reasonable range)       │
│                                                                      │
│  Layer 3: OUTPUT QUALITY (DQDL)                                      │
│  ├── Completeness: all required columns non-null                     │
│  ├── Uniqueness: primary key unique                                  │
│  ├── Freshness: data within expected age                             │
│  ├── Validity: values in expected domain                             │
│  └── Consistency: cross-table checks match                           │
│                                                                      │
│  Layer 4: OBSERVABILITY                                              │
│  ├── Lineage tracking (source → output tracing)                     │
│  ├── Anomaly detection (statistical deviation from normal)           │
│  ├── Freshness monitoring (SLA tracking)                            │
│  └── Schema drift alerting (unexpected changes)                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
