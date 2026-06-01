# Problem 7: Customer Data Platform Backfill (Petabyte-Scale)

## The Problem

A company is migrating to a new Customer Data Platform (CDP). The requirement:

- **Backfill 5 years** of customer interaction history (purchases, clicks, support tickets, emails, app events)
- **2PB of historical data** spread across 30+ source systems (Salesforce, Segment, Snowplow, internal DBs, S3 archives)
- **Cannot disrupt production pipelines** — the same cluster runs daily incremental loads
- **Must be idempotent** — any day's backfill can be restarted without creating duplicates
- **Backfill must match incremental output exactly** — same transformation logic, same results
- **Late-arriving data corrections** — some sources retroactively fix records days/weeks later

This is the hardest operational challenge in data engineering: running a multi-week backfill alongside production without breaking either.

## Scale Numbers

| Metric | Value |
|--------|-------|
| History depth | 5 years (1,825 days) |
| Total data | 2 Petabytes |
| Source systems | 30+ |
| Customer records | 500M unique customers |
| Backfill budget | 2 weeks |
| Cluster capacity limit | 30% (production owns the rest) |
| Daily partition size | ~1.1 TB average |
| Peak daily partition | ~4 TB (Black Friday, holidays) |

## Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AIRFLOW SCHEDULER                            │
│                                                                     │
│  ┌──────────────────────┐    ┌──────────────────────────────────┐  │
│  │  Production DAGs     │    │  Backfill DAGs                   │  │
│  │  (priority=1)        │    │  (priority=5, lower = higher)    │  │
│  │  max_active_runs=1   │    │  max_active_runs=5               │  │
│  └──────────┬───────────┘    └──────────────┬───────────────────┘  │
│             │                                │                      │
│             ▼                                ▼                      │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                   POOL: cdp_cluster                       │      │
│  │                   slots=100                               │      │
│  │         production: 70 slots | backfill: 30 slots         │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SPARK CLUSTER                                │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │ Source A    │  │ Source B    │  │ Source C    │  ... (30+)      │
│  │ Extract     │  │ Extract     │  │ Extract     │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                 │                 │                        │
│         ▼                 ▼                 ▼                        │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │              Transform (Unified Customer Model)           │      │
│  └──────────────────────────────┬───────────────────────────┘      │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │     Load: DELETE partition + INSERT (idempotent)           │      │
│  └──────────────────────────────┬───────────────────────────┘      │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │              CDP Data Lake (Iceberg/Delta)                 │      │
│  │              Partitioned by: date / source_system          │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

## Airflow Concepts Taught

### 1. catchup Parameter

```python
# catchup=True: Airflow creates a DagRun for EVERY missed schedule interval
# If start_date is 5 years ago, Airflow creates 1,825 DagRuns
dag = DAG(
    dag_id="cdp_backfill",
    start_date=datetime(2019, 1, 1),
    schedule_interval="@daily",
    catchup=True,  # THIS is how backfill works
    max_active_runs=5,  # Only 5 days processed in parallel
)

# catchup=False: Only creates DagRun for the LATEST interval
# Used for production DAGs that should not re-process history
production_dag = DAG(
    dag_id="cdp_incremental",
    start_date=datetime(2019, 1, 1),
    schedule_interval="@daily",
    catchup=False,  # Skip all historical intervals
    max_active_runs=1,
)
```

**How catchup works internally:**

1. Scheduler sees `start_date=2019-01-01` and `catchup=True`
2. Calculates all intervals from `start_date` to `now`
3. Creates DagRun objects for each interval (respecting `max_active_runs`)
4. Queues them oldest-first by default
5. As each DagRun completes, the next one is triggered

**Why max_active_runs matters for backfill:**

```python
# BAD: No limit — Airflow tries to schedule all 1,825 runs simultaneously
max_active_runs=None  # Scheduler overload, cluster starved

# GOOD: Controlled parallelism
max_active_runs=5  # 5 days at a time, predictable resource usage
```

### 2. Backfill CLI & Patterns

```bash
# Basic backfill: process January 2020
airflow dags backfill cdp_unified \
    --start-date 2020-01-01 \
    --end-date 2020-01-31

# Reset and re-run (clears previous state)
airflow dags backfill cdp_unified \
    --start-date 2020-01-01 \
    --end-date 2020-01-31 \
    --reset-dagruns

# Only re-run tasks that failed
airflow dags backfill cdp_unified \
    --start-date 2020-06-15 \
    --end-date 2020-06-15 \
    --rerun-failed-tasks

# Backfill specific task only
airflow dags backfill cdp_unified \
    --start-date 2020-01-01 \
    --end-date 2020-01-31 \
    --task-regex "extract_salesforce"

# Dry run — see what would be scheduled
airflow dags backfill cdp_unified \
    --start-date 2019-01-01 \
    --end-date 2024-01-01 \
    --dry-run
```

**Programmatic backfill via API (Airflow 2.x REST):**

```python
import requests

def trigger_backfill_range(start: str, end: str, batch_size: int = 30):
    """Trigger backfill in monthly batches for manageability."""
    from datetime import date, timedelta
    from dateutil.relativedelta import relativedelta

    current = date.fromisoformat(start)
    end_dt = date.fromisoformat(end)

    while current < end_dt:
        batch_end = min(current + relativedelta(months=1), end_dt)
        resp = requests.post(
            "http://airflow:8080/api/v1/dags/cdp_backfill/dagRuns",
            json={
                "logical_date": current.isoformat(),
                "conf": {
                    "backfill_start": current.isoformat(),
                    "backfill_end": batch_end.isoformat(),
                    "is_backfill": True,
                },
            },
            auth=("admin", "admin"),
        )
        current = batch_end
```

### 3. Idempotency Patterns (The Most Critical Pattern)

Idempotency means: **running the same task twice for the same date produces the same result without duplicates.**

#### Pattern A: DELETE + INSERT (Partition-Level)

```python
def load_partition_idempotent(df, target_table, partition_date, conn):
    """The gold standard for batch idempotency."""
    # Step 1: Delete existing data for this partition
    conn.execute(f"""
        DELETE FROM {target_table}
        WHERE partition_date = '{partition_date}'
        AND source_system = '{source}'
    """)

    # Step 2: Insert fresh data
    df.write.mode("append").insertInto(target_table)

    # Result: Running twice = same output. No duplicates ever.
```

#### Pattern B: MERGE/UPSERT

```sql
-- For systems where DELETE is expensive (large tables, no partitioning)
MERGE INTO cdp.customer_events AS target
USING staging.customer_events_{{ ds }} AS source
ON target.event_id = source.event_id
   AND target.partition_date = '{{ ds }}'
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

#### Pattern C: Spark Partition Overwrite

```python
# Spark's insertInto with overwrite on specific partitions
(
    df.write
    .mode("overwrite")
    .partitionBy("partition_date", "source_system")
    .format("iceberg")
    .option("overwrite-mode", "dynamic")  # Only overwrites partitions present in df
    .save("cdp.customer_events")
)
```

#### Anti-Patterns That Break Idempotency

```python
# BAD: append-only without deduplication
df.write.mode("append").save(target)  # Run twice = double data

# BAD: Using current timestamp as record metadata
df = df.withColumn("loaded_at", current_timestamp())  # Different each run

# BAD: Auto-increment IDs
# Run 1: IDs 1000-2000. Run 2: IDs 2001-3000. Different results!

# BAD: Reading from a stream position that moves
# Kafka offsets consumed once are gone — not repeatable

# GOOD: Deterministic surrogate keys
df = df.withColumn(
    "event_sk",
    sha2(concat_ws("|", col("event_id"), col("source"), col("event_date")), 256)
)
```

#### Testing Idempotency

```python
def test_idempotency(dag_id, execution_date):
    """Run a task twice and verify identical output."""
    # Run 1
    run_task(dag_id, "load_customers", execution_date)
    result_1 = query(f"SELECT COUNT(*), SUM(checksum) FROM target WHERE date='{execution_date}'")

    # Run 2 (same date)
    run_task(dag_id, "load_customers", execution_date)
    result_2 = query(f"SELECT COUNT(*), SUM(checksum) FROM target WHERE date='{execution_date}'")

    assert result_1 == result_2, "IDEMPOTENCY BROKEN"
```

### 4. execution_date Deep Dive

```python
# CRITICAL CONCEPT:
# execution_date = the START of the data interval, NOT when the task runs
#
# A daily DAG scheduled for 2024-01-15:
#   execution_date = 2024-01-15T00:00:00  (start of interval)
#   data_interval_end = 2024-01-16T00:00:00  (end of interval)
#   Actual run time: 2024-01-16T00:05:00  (after interval closes)

def extract_source_data(**context):
    # CORRECT: Use data interval to define what data to pull
    start = context["data_interval_start"]  # 2024-01-15 00:00:00
    end = context["data_interval_end"]      # 2024-01-16 00:00:00

    query = f"""
        SELECT * FROM source_events
        WHERE event_time >= '{start}'
          AND event_time < '{end}'
    """
    # This extracts exactly one day of data, regardless of when the task runs

    # WRONG: Using "today" or current time
    # today = datetime.now()  # NEVER DO THIS — breaks backfill!

# Template variables available:
#   {{ ds }}              -> "2024-01-15" (execution_date as YYYY-MM-DD)
#   {{ ds_nodash }}       -> "20240115"
#   {{ data_interval_start }} -> datetime object
#   {{ data_interval_end }}   -> datetime object
#   {{ prev_ds }}         -> "2024-01-14"
#   {{ next_ds }}         -> "2024-01-16"
```

**Common mistakes:**

```python
# MISTAKE 1: Filtering by "today" instead of execution_date
# This means backfill for 2019-01-01 would pull today's data!
query = f"SELECT * FROM events WHERE date = CURRENT_DATE"  # WRONG

# MISTAKE 2: Confusing execution_date with run time
# Task runs on Jan 16, but execution_date is Jan 15
# The task should process Jan 15's data, not Jan 16's

# MISTAKE 3: Off-by-one on interval boundaries
# Daily DAG for Jan 15: process events WHERE time >= Jan15 AND time < Jan16
# NOT: time >= Jan15 AND time <= Jan15 (misses 23:00:00 - 23:59:59)
```

### 5. depends_on_past & Concurrency Control

```python
# depends_on_past=True: A task won't run for date D unless it succeeded for date D-1
# USE CASE: Cumulative metrics, running totals, SCD Type 2

cumulative_task = PythonOperator(
    task_id="compute_running_totals",
    python_callable=compute_running_totals,
    depends_on_past=True,  # Must process days in order
)

# USE CASE where depends_on_past=False (DEFAULT):
# Independent daily partitions — Jan 15 doesn't need Jan 14's result
independent_task = PythonOperator(
    task_id="extract_daily_events",
    python_callable=extract_events,
    depends_on_past=False,  # Can process any day independently
)
```

**Combining controls for backfill:**

```python
from airflow import DAG
from airflow.operators.python import PythonOperator

dag = DAG(
    dag_id="cdp_backfill",
    schedule_interval="@daily",
    start_date=datetime(2019, 1, 1),
    catchup=True,
    max_active_runs=5,      # 5 days in parallel
    concurrency=20,         # Max 20 tasks across all active runs
    dagrun_timeout=timedelta(hours=6),  # Kill stuck runs
)

extract = PythonOperator(
    task_id="extract",
    pool="backfill_pool",   # Pool with 30 slots (30% cluster)
    pool_slots=2,           # Each extract uses 2 pool slots
    priority_weight=5,      # Lower priority than production (weight=1 = higher)
    depends_on_past=False,  # Days are independent
    dag=dag,
)
```

### 6. Partition-Level Replay

```bash
# Clear a specific task for a specific date (re-run just that)
airflow tasks clear cdp_backfill \
    --start-date 2020-03-15 \
    --end-date 2020-03-15 \
    --task-regex "load_to_cdp"

# Clear all tasks for a date range
airflow tasks clear cdp_backfill \
    --start-date 2020-03-01 \
    --end-date 2020-03-31

# Mark a task as success (skip it)
airflow tasks set-state cdp_backfill load_to_cdp 2020-03-15 --state success

# Run a single task instance (testing)
airflow tasks test cdp_backfill extract_salesforce 2020-03-15
```

## Production Implementation

```python
"""
CDP Backfill DAG — Production Implementation
Processes 5 years of customer interaction history idempotently.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.models import Variable
from airflow.utils.trigger_rule import TriggerRule

# ─── Configuration ───────────────────────────────────────────────────────────

SOURCE_SYSTEMS = [
    {"name": "salesforce", "type": "api", "throttle_rps": 50},
    {"name": "segment", "type": "s3", "throttle_rps": None},
    {"name": "snowplow", "type": "s3", "throttle_rps": None},
    {"name": "zendesk", "type": "api", "throttle_rps": 200},
    {"name": "internal_postgres", "type": "db", "throttle_rps": None},
    {"name": "app_events", "type": "kafka_archive", "throttle_rps": None},
    # ... 24 more sources
]

BACKFILL_POOL = "cdp_backfill_pool"  # 30 slots = 30% cluster
PRODUCTION_POOL = "cdp_production_pool"  # 70 slots

default_args = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(hours=1),
    "execution_timeout": timedelta(hours=4),
    "on_failure_callback": notify_backfill_failure,
    "pool": BACKFILL_POOL,
}

dag = DAG(
    dag_id="cdp_customer_backfill",
    default_args=default_args,
    description="Backfill 5 years of customer data to CDP",
    schedule_interval="@daily",
    start_date=datetime(2019, 1, 1),
    end_date=datetime(2024, 1, 1),  # Stop after backfill window
    catchup=True,
    max_active_runs=5,
    concurrency=15,
    tags=["cdp", "backfill", "petabyte"],
)


# ─── Check if backfill is paused (manual control) ────────────────────────────

def check_backfill_enabled(**context):
    """Allow operators to pause backfill without unpausing the DAG."""
    is_enabled = Variable.get("cdp_backfill_enabled", default_var="true")
    if is_enabled.lower() != "true":
        raise AirflowSkipException("Backfill paused via Variable")

    # Check cluster load — yield to production if cluster is hot
    cluster_util = get_cluster_utilization()
    if cluster_util > 0.80:
        raise AirflowSkipException(
            f"Cluster at {cluster_util:.0%}, skipping backfill run"
        )

check_enabled = PythonOperator(
    task_id="check_backfill_enabled",
    python_callable=check_backfill_enabled,
    dag=dag,
)


# ─── Extract from each source system ─────────────────────────────────────────

def extract_source(source_config, **context):
    """Extract one day of data from a source system, idempotently."""
    ds = context["ds"]
    start = context["data_interval_start"]
    end = context["data_interval_end"]
    source = source_config["name"]

    staging_path = f"s3://cdp-staging/{source}/date={ds}/"

    # Idempotent: overwrite staging partition
    if source_config["type"] == "api":
        extract_from_api(
            source=source,
            start_time=start,
            end_time=end,
            output_path=staging_path,
            throttle_rps=source_config["throttle_rps"],
            is_backfill=True,  # Use historical endpoint if available
        )
    elif source_config["type"] == "s3":
        # Historical data already in S3, just register the path
        extract_from_s3_archive(
            source=source,
            date=ds,
            output_path=staging_path,
        )
    elif source_config["type"] == "db":
        extract_from_database(
            source=source,
            start_time=start,
            end_time=end,
            output_path=staging_path,
        )

    # Write manifest for downstream verification
    write_manifest(staging_path, source, ds)
    return staging_path


extract_tasks = []
for src in SOURCE_SYSTEMS:
    task = PythonOperator(
        task_id=f"extract_{src['name']}",
        python_callable=extract_source,
        op_kwargs={"source_config": src},
        pool_slots=1,
        dag=dag,
    )
    check_enabled >> task
    extract_tasks.append(task)


# ─── Transform: Unified Customer Model ───────────────────────────────────────

transform = SparkSubmitOperator(
    task_id="transform_unified_model",
    application="s3://cdp-code/spark/transform_customer_events.py",
    application_args=[
        "--date", "{{ ds }}",
        "--sources", ",".join(s["name"] for s in SOURCE_SYSTEMS),
        "--staging-path", "s3://cdp-staging/",
        "--output-path", "s3://cdp-transformed/date={{ ds }}/",
        "--mode", "backfill",
    ],
    conf={
        "spark.sql.shuffle.partitions": "2000",
        "spark.executor.memory": "8g",
        "spark.executor.cores": "4",
        "spark.dynamicAllocation.enabled": "true",
        "spark.dynamicAllocation.maxExecutors": "50",  # Capped for backfill
    },
    pool_slots=5,  # Transform is heavier
    dag=dag,
)

for t in extract_tasks:
    t >> transform


# ─── Load: Idempotent Partition Write ─────────────────────────────────────────

def load_to_cdp(**context):
    """
    DELETE + INSERT pattern for idempotent partition loading.
    This is the core idempotency guarantee.
    """
    ds = context["ds"]
    spark = get_spark_session("cdp_backfill_load")

    # Read transformed data
    df = spark.read.parquet(f"s3://cdp-transformed/date={ds}/")

    # IDEMPOTENT LOAD: Delete then insert
    # Using Iceberg's overwrite with filter (atomic operation)
    df.writeTo("cdp_catalog.customer_events") \
        .overwritePartitions()  # Atomically replaces partition

    # Verification: count check
    loaded_count = spark.sql(f"""
        SELECT COUNT(*) FROM cdp_catalog.customer_events
        WHERE partition_date = '{ds}'
    """).collect()[0][0]

    expected_count = df.count()
    if loaded_count != expected_count:
        raise ValueError(
            f"Load verification failed: loaded={loaded_count}, expected={expected_count}"
        )

    # Log progress
    context["ti"].xcom_push(key="loaded_records", value=loaded_count)

load = PythonOperator(
    task_id="load_to_cdp",
    python_callable=load_to_cdp,
    pool_slots=3,
    dag=dag,
)

transform >> load


# ─── Verify: Compare with expected output ────────────────────────────────────

def verify_backfill_output(**context):
    """
    Compare backfill output against known checksums or row counts.
    Catches logic drift between backfill and incremental pipelines.
    """
    ds = context["ds"]
    spark = get_spark_session("cdp_verify")

    # Check 1: Row count within expected range
    count = spark.sql(f"""
        SELECT COUNT(*) FROM cdp_catalog.customer_events
        WHERE partition_date = '{ds}'
    """).collect()[0][0]

    # Historical baseline: avg records per day with 50% tolerance
    baseline = get_baseline_count(ds)
    if baseline and abs(count - baseline) / baseline > 0.5:
        raise ValueError(
            f"Date {ds}: count={count}, baseline={baseline}, "
            f"deviation={abs(count-baseline)/baseline:.0%}"
        )

    # Check 2: No null customer_ids (data quality)
    nulls = spark.sql(f"""
        SELECT COUNT(*) FROM cdp_catalog.customer_events
        WHERE partition_date = '{ds}' AND customer_id IS NULL
    """).collect()[0][0]

    if nulls > 0:
        raise ValueError(f"Found {nulls} null customer_ids for {ds}")

    # Check 3: No duplicate event_ids within partition
    dupes = spark.sql(f"""
        SELECT COUNT(*) - COUNT(DISTINCT event_id)
        FROM cdp_catalog.customer_events
        WHERE partition_date = '{ds}'
    """).collect()[0][0]

    if dupes > 0:
        raise ValueError(f"Found {dupes} duplicate events for {ds}")

verify = PythonOperator(
    task_id="verify_output",
    python_callable=verify_backfill_output,
    pool_slots=1,
    dag=dag,
)

load >> verify


# ─── Progress Tracking ────────────────────────────────────────────────────────

def update_progress(**context):
    """Track overall backfill progress for dashboards."""
    ds = context["ds"]
    total_days = (datetime(2024, 1, 1) - datetime(2019, 1, 1)).days
    completed_day = (datetime.fromisoformat(ds) - datetime(2019, 1, 1)).days

    progress_pct = (completed_day / total_days) * 100
    records_loaded = context["ti"].xcom_pull(
        task_ids="load_to_cdp", key="loaded_records"
    )

    # Update progress table
    update_backfill_progress(
        dag_id="cdp_customer_backfill",
        date=ds,
        progress_pct=progress_pct,
        records=records_loaded,
        status="complete",
    )

progress = PythonOperator(
    task_id="update_progress",
    python_callable=update_progress,
    pool_slots=1,
    trigger_rule=TriggerRule.ALL_SUCCESS,
    dag=dag,
)

verify >> progress


# ─── Late-Arriving Data Handler ──────────────────────────────────────────────

def handle_late_arrivals(**context):
    """
    Some sources have corrections that arrive days/weeks late.
    Re-process affected partitions after the initial backfill pass.
    """
    ds = context["ds"]

    # Check if this date has corrections that arrived after initial load
    corrections = get_corrections_for_date(ds)
    if not corrections:
        raise AirflowSkipException(f"No corrections for {ds}")

    # Re-extract only the corrected sources
    for correction in corrections:
        re_extract(
            source=correction["source"],
            date=ds,
            correction_timestamp=correction["detected_at"],
        )

    # Re-run transform and load (idempotent, so safe)
    return "reprocess_needed"

late_data = PythonOperator(
    task_id="handle_late_arrivals",
    python_callable=handle_late_arrivals,
    pool_slots=1,
    dag=dag,
)

progress >> late_data
```

## Production Handling

### Source System Goes Down During Backfill

```python
# Built into retry logic — retries with exponential backoff
# If source is down for extended period:

def extract_with_circuit_breaker(source, **context):
    """Skip source if it's been down too long, mark for retry later."""
    health = check_source_health(source)

    if health == "down" and source_down_duration(source) > timedelta(hours=2):
        # Mark this date+source for later retry
        mark_for_retry(source, context["ds"])
        raise AirflowSkipException(
            f"{source} down for 2+ hours, will retry later"
        )

    return extract_source(source, **context)
```

### Pause/Resume Backfill

```python
# Method 1: Airflow Variable (checked at start of each run)
# Set Variable "cdp_backfill_enabled" = "false" in UI

# Method 2: Pause the DAG (stops new runs, running tasks complete)
# airflow dags pause cdp_customer_backfill

# Method 3: Reduce max_active_runs dynamically
# Variable: "cdp_backfill_max_runs" checked by a sensor
```

### Priority: Production vs Backfill

```python
# Pools enforce hard resource limits:
# Production pool: 70 slots (always available)
# Backfill pool: 30 slots (ceiling for backfill)

# Priority weight: lower number = runs first when slots are contested
# Production tasks: priority_weight=1
# Backfill tasks: priority_weight=10

# Dynamic throttling: backfill yields when cluster is busy
def adaptive_pool_slots(**context):
    """Reduce backfill concurrency during peak production hours."""
    hour = datetime.now().hour
    if 8 <= hour <= 12:  # Morning production peak
        return 1  # Minimal backfill
    return 3  # Normal backfill speed
```

### Handling Schema Changes Over 5 Years

```python
def transform_with_schema_evolution(df, source, date, **context):
    """Handle schema changes across 5 years of history."""
    ds = context["ds"]

    # Schema registry tracks schema versions by date
    schema_version = get_schema_version(source, ds)

    if source == "salesforce" and ds < "2021-06-01":
        # Before June 2021, customer_id was called account_id
        df = df.withColumnRenamed("account_id", "customer_id")

    if source == "segment" and ds < "2022-03-15":
        # Event schema v1 had flat structure, v2 is nested
        df = flatten_legacy_segment_events(df)

    if source == "app_events" and ds < "2020-09-01":
        # Missing field added later — backfill with default
        if "device_type" not in df.columns:
            df = df.withColumn("device_type", lit("unknown"))

    # Always cast to canonical schema at the end
    return cast_to_canonical_schema(df, CANONICAL_SCHEMA_V3)
```

### Data Corrections After Backfill Complete

```python
# Separate DAG for post-backfill corrections
correction_dag = DAG(
    dag_id="cdp_backfill_corrections",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 2),  # Starts after backfill completes
    catchup=False,
)

def process_corrections(**context):
    """
    After backfill completes, sources may still send corrections
    for historical dates. Process them as they arrive.
    """
    # Query correction log for unprocessed corrections
    corrections = query("""
        SELECT source, partition_date, correction_type
        FROM cdp_corrections_log
        WHERE processed = false
        ORDER BY partition_date
        LIMIT 100
    """)

    for corr in corrections:
        # Re-run the same idempotent pipeline for affected date
        trigger_dag_run(
            dag_id="cdp_customer_backfill",
            execution_date=corr["partition_date"],
            conf={"correction_mode": True, "source": corr["source"]},
        )
        mark_correction_processing(corr)
```

### Monitoring Backfill Progress

```python
# Dashboard query: overall progress
"""
SELECT
    COUNT(CASE WHEN state = 'success' THEN 1 END) as completed_days,
    COUNT(*) as total_days,
    ROUND(100.0 * COUNT(CASE WHEN state = 'success' THEN 1 END) / COUNT(*), 1) as pct,
    SUM(records_loaded) as total_records,
    AVG(duration_seconds) as avg_duration_per_day,
    -- Estimated completion
    (COUNT(*) - COUNT(CASE WHEN state = 'success' THEN 1 END))
        * AVG(duration_seconds) / (5 * 3600) as estimated_hours_remaining
FROM backfill_progress
WHERE dag_id = 'cdp_customer_backfill';
"""

# Alert: Backfill falling behind schedule
def check_backfill_pace(**context):
    days_elapsed = (datetime.now() - datetime(2024, 1, 1)).days  # Since backfill started
    days_processed = get_completed_backfill_days()
    required_pace = 1825 / 14  # Must finish in 14 days = 130 days/day

    actual_pace = days_processed / max(days_elapsed, 1)
    if actual_pace < required_pace * 0.8:
        alert_oncall(
            f"Backfill behind schedule: {actual_pace:.0f}/day vs required {required_pace:.0f}/day"
        )
```

## Key Takeaways

1. **catchup=True + max_active_runs** is the fundamental backfill mechanism in Airflow — it generates DagRuns for all missed intervals with controlled parallelism.

2. **Idempotency is non-negotiable.** DELETE + INSERT (or partition overwrite) ensures any day can be re-run safely. Test this explicitly.

3. **execution_date is the data interval start**, not when the task runs. All data filtering must use `data_interval_start`/`data_interval_end`, never `datetime.now()`.

4. **Pools enforce hard resource limits** between production and backfill. Production gets priority; backfill uses whatever is left.

5. **Schema evolution over 5 years is inevitable.** Build transformation logic that handles schema versions based on the date being processed.

6. **Progress tracking and pace monitoring** are essential for multi-week backfills. Know your required pace and alert when falling behind.

7. **Design for pause/resume.** Backfills will be interrupted (cluster issues, source outages, production emergencies). Idempotency makes resume trivial.

8. **Same DAG logic for backfill and incremental** prevents drift. The only difference should be resource allocation and concurrency settings, not transformation logic.
