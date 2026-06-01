# Data Backfill and Reprocessing Patterns

## Architecture Diagram

```mermaid
graph TB
    subgraph "Trigger"
        BUG[Bug Fix<br/>Logic correction]
        SCHEMA[Schema Change<br/>New columns/transforms]
        SOURCE[Source Correction<br/>Upstream data fix]
        FEATURE[New Feature<br/>Backfill new field]
    end

    subgraph "Backfill Strategies"
        subgraph "Blue-Green"
            PROD_TABLE[Production Table<br/>v1 (serving)]
            SHADOW_TABLE[Shadow Table<br/>v2 (rebuilding)]
            SWAP[Atomic Swap<br/>Rename/pointer change]
        end
        subgraph "Partition-based"
            P1[Partition 2024-01]
            P2[Partition 2024-02]
            P3[Partition 2024-03<br/>Reprocessing...]
            P4[Partition 2024-04]
        end
        subgraph "Shadow Pipeline"
            SHADOW_PIPE[Shadow Pipeline<br/>Parallel execution]
            VALIDATION[Validation Gate<br/>Compare outputs]
            PROMOTE[Promote to Prod]
        end
    end

    subgraph "Safety Controls"
        IDEMPOTENT[Idempotent Writes<br/>Deterministic output]
        VALIDATE[Validation Gates<br/>Row counts, checksums]
        ROLLBACK[Rollback Plan<br/>Previous version available]
        CANARY[Canary Deployment<br/>Partial switchover]
    end

    subgraph "Execution"
        AIRFLOW[Airflow Backfill DAG<br/>Parameterized dates]
        SPARK[Spark Jobs<br/>Partition-aware]
        THROTTLE[Throttling<br/>Don't overwhelm cluster]
    end

    BUG --> SHADOW_PIPE
    SCHEMA --> SHADOW_TABLE
    SOURCE --> P3
    FEATURE --> SHADOW_TABLE

    SHADOW_PIPE --> VALIDATION --> PROMOTE
    SHADOW_TABLE --> SWAP
    P3 --> VALIDATE

    AIRFLOW --> SPARK
    SPARK --> IDEMPOTENT
    VALIDATE --> ROLLBACK
```

## Problem Statement at Scale

Every data platform eventually needs to reprocess historical data:
- **Bug fixes**: Transform logic was wrong for 6 months → recompute all affected data
- **Schema evolution**: New business column needed historically (e.g., customer_segment)
- **Source corrections**: Upstream fixed data for past 3 months
- **New features**: ML model needs 2 years of historical features
- **Compliance**: GDPR deletion requires reprocessing to remove PII

At scale (petabytes, 1000s of tables, 100s of downstream dependencies), naive reprocessing:
- Costs $50K+ in compute for full reprocessing
- Takes days/weeks, blocking production pipelines
- Risks corrupting production tables mid-reprocess
- Breaks downstream consumers during transition

Companies like Netflix, Airbnb, and Uber have built sophisticated backfill systems processing months of data safely.

## Core Principles

### 1. Idempotent Writes

```python
# WRONG: Append-based (rerun = duplicates)
df.write.mode("append").parquet(output_path)

# RIGHT: Partition overwrite (rerun = same result)
df.write \
    .mode("overwrite") \
    .option("replaceWhere", f"dt = '{target_date}'") \
    .format("delta") \
    .save(output_path)

# RIGHT: MERGE with deterministic keys
delta_table.alias("target").merge(
    new_data.alias("source"),
    "target.id = source.id AND target.dt = source.dt"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

# RIGHT: Write to unique path, then atomic swap
output_path = f"s3://warehouse/table/dt={date}/version={version}/"
df.write.mode("overwrite").parquet(output_path)
# Then update metastore to point to new version
```

### 2. Partition-based Reprocessing

```python
def backfill_date_range(start_date, end_date, table_name, transform_fn):
    """Reprocess one partition at a time, safely."""
    current = start_date
    while current <= end_date:
        try:
            # Process single partition
            result = transform_fn(current)
            
            # Validate before committing
            validate_partition(result, table_name, current)
            
            # Atomic partition overwrite
            result.write \
                .mode("overwrite") \
                .option("replaceWhere", f"dt = '{current}'") \
                .format("delta") \
                .save(f"s3://warehouse/{table_name}/")
            
            log_success(table_name, current)
        except ValidationError as e:
            log_failure(table_name, current, e)
            alert_oncall(f"Backfill validation failed: {table_name} {current}")
            break  # Stop backfill, don't process later dates with bad upstream
        
        current += timedelta(days=1)
```

### 3. Blue-Green Tables

```python
def blue_green_backfill(table_name, transform_fn, date_range):
    """Full table rebuild with zero-downtime swap."""
    
    shadow_table = f"{table_name}_v2"
    prod_table = table_name
    
    # Step 1: Build shadow table (full reprocessing)
    for date in date_range:
        result = transform_fn(date)
        result.write.format("delta").mode("append") \
            .partitionBy("dt") \
            .save(f"s3://warehouse/{shadow_table}/")
    
    # Step 2: Validate shadow matches expectations
    validate_full_table(shadow_table, prod_table)
    
    # Step 3: Atomic swap
    spark.sql(f"ALTER TABLE {prod_table} RENAME TO {table_name}_deprecated")
    spark.sql(f"ALTER TABLE {shadow_table} RENAME TO {prod_table}")
    
    # Step 4: Keep deprecated for rollback (7 days)
    schedule_cleanup(f"{table_name}_deprecated", days=7)
```

## Backfill Patterns

### Pattern 1: Airflow Backfill DAG

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Param
from datetime import datetime, timedelta

with DAG(
    'backfill_orders_pipeline',
    schedule_interval=None,  # Manual trigger only
    params={
        'start_date': Param('2024-01-01', type='string', description='Start date (inclusive)'),
        'end_date': Param('2024-03-31', type='string', description='End date (inclusive)'),
        'parallelism': Param(5, type='integer', description='Concurrent partitions'),
        'dry_run': Param(False, type='boolean', description='Validate only, no write'),
        'table': Param('fact_orders', type='string'),
    },
    max_active_runs=1,
    tags=['backfill', 'manual'],
    doc_md="## Backfill Pipeline\nReprocesses historical partitions safely.",
) as dag:

    @task
    def generate_partitions(**context):
        params = context['params']
        start = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end = datetime.strptime(params['end_date'], '%Y-%m-%d')
        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        return dates

    @task(max_active_tis_per_dag=5)  # Throttle concurrency
    def process_partition(date: str, **context):
        params = context['params']
        # Run Spark job for single partition
        spark_submit(
            job="backfill_transform",
            args={
                "date": date,
                "table": params['table'],
                "dry_run": params['dry_run'],
            }
        )

    @task
    def validate_backfill(**context):
        """Final validation after all partitions processed."""
        params = context['params']
        run_full_validation(
            table=params['table'],
            start_date=params['start_date'],
            end_date=params['end_date']
        )

    dates = generate_partitions()
    processed = process_partition.expand(date=dates)
    processed >> validate_backfill()
```

### Pattern 2: Shadow Pipeline

```python
def run_shadow_pipeline(pipeline_name, date_range):
    """
    Run new pipeline version alongside production.
    Compare outputs before switching.
    """
    
    for date in date_range:
        # Run BOTH old and new logic
        prod_output = run_production_pipeline(date)
        shadow_output = run_new_pipeline(date)
        
        # Compare outputs
        comparison = compare_datasets(prod_output, shadow_output)
        
        log_comparison(pipeline_name, date, comparison)
        
        if comparison.row_count_diff_pct > 5:
            alert(f"Shadow pipeline row count differs by {comparison.row_count_diff_pct}%")
        
        if comparison.value_diff_pct > 1:
            alert(f"Shadow pipeline values differ by {comparison.value_diff_pct}%")
    
    # After shadow period (e.g., 7 days), promote if all checks pass
    if all_shadow_checks_passed(pipeline_name):
        promote_shadow_to_production(pipeline_name)

def compare_datasets(prod_df, shadow_df):
    """Compare two DataFrames for equivalence."""
    return ComparisonResult(
        row_count_diff_pct=abs(prod_df.count() - shadow_df.count()) / prod_df.count() * 100,
        schema_match=prod_df.schema == shadow_df.schema,
        value_diff_pct=compute_value_differences(prod_df, shadow_df),
        null_diff=compare_null_rates(prod_df, shadow_df),
    )
```

### Pattern 3: Versioned Tables with Canary

```python
def canary_backfill(table_name, new_version, date_range, canary_pct=10):
    """
    Gradually shift traffic from old to new version.
    """
    
    # Step 1: Build new version fully
    build_table_version(table_name, new_version, date_range)
    
    # Step 2: Create unified view with canary logic
    spark.sql(f"""
        CREATE OR REPLACE VIEW {table_name}_unified AS
        SELECT * FROM {table_name}_v{new_version}
        WHERE HASH(primary_key) % 100 < {canary_pct}  -- {canary_pct}% from new
        UNION ALL
        SELECT * FROM {table_name}_v{new_version - 1}
        WHERE HASH(primary_key) % 100 >= {canary_pct}  -- Rest from old
    """)
    
    # Step 3: Monitor metrics on canary segment
    # If metrics are good after 24-48 hours, increase canary_pct
    # Eventually set to 100% (full cutover)
    
    # Step 4: Full cutover
    spark.sql(f"""
        CREATE OR REPLACE VIEW {table_name}_unified AS
        SELECT * FROM {table_name}_v{new_version}
    """)
```

## Validation Gates

```python
class BackfillValidator:
    """Validate backfilled data before promoting to production."""
    
    def __init__(self, table_name, date):
        self.table_name = table_name
        self.date = date
        self.checks = []
    
    def check_row_count(self, min_rows=None, max_deviation_pct=20):
        """Compare row count to historical average."""
        current = get_row_count(self.table_name, self.date)
        historical_avg = get_historical_avg_row_count(self.table_name, lookback_days=30)
        
        deviation = abs(current - historical_avg) / historical_avg * 100
        passed = deviation <= max_deviation_pct
        
        if min_rows and current < min_rows:
            passed = False
        
        self.checks.append(("row_count", passed, f"deviation={deviation:.1f}%"))
        return self
    
    def check_null_rates(self, columns, max_null_pct=5):
        """Ensure critical columns aren't mostly null."""
        for col in columns:
            null_pct = get_null_percentage(self.table_name, self.date, col)
            passed = null_pct <= max_null_pct
            self.checks.append((f"null_rate_{col}", passed, f"{null_pct:.1f}%"))
        return self
    
    def check_value_distribution(self, column, expected_values):
        """Verify enum/category columns have expected values."""
        actual = get_distinct_values(self.table_name, self.date, column)
        unexpected = actual - set(expected_values)
        passed = len(unexpected) == 0
        self.checks.append((f"values_{column}", passed, f"unexpected={unexpected}"))
        return self
    
    def check_referential_integrity(self, fk_column, parent_table, parent_key):
        """Ensure foreign keys reference valid parents."""
        orphan_count = count_orphan_records(
            self.table_name, self.date, fk_column, parent_table, parent_key
        )
        passed = orphan_count == 0
        self.checks.append(("referential_integrity", passed, f"orphans={orphan_count}"))
        return self
    
    def check_monotonic_metrics(self, metric_column, direction="increasing"):
        """Ensure cumulative metrics don't decrease."""
        prev_value = get_metric_value(self.table_name, self.date - timedelta(days=1), metric_column)
        curr_value = get_metric_value(self.table_name, self.date, metric_column)
        
        if direction == "increasing":
            passed = curr_value >= prev_value * 0.9  # Allow 10% decrease
        else:
            passed = True
        
        self.checks.append((f"monotonic_{metric_column}", passed, f"prev={prev_value}, curr={curr_value}"))
        return self
    
    def validate(self):
        """Run all checks and return result."""
        failures = [(name, msg) for name, passed, msg in self.checks if not passed]
        if failures:
            raise ValidationError(f"Backfill validation failed: {failures}")
        return True

# Usage
BackfillValidator("fact_orders", date="2024-01-15") \
    .check_row_count(min_rows=100000) \
    .check_null_rates(["order_id", "customer_id", "amount"]) \
    .check_value_distribution("status", ["pending", "completed", "cancelled"]) \
    .check_referential_integrity("customer_id", "dim_customers", "customer_id") \
    .validate()
```

## Throttling and Resource Management

```python
# Prevent backfill from overwhelming production cluster

class BackfillThrottler:
    def __init__(self, max_concurrent=5, max_cluster_utilization=0.6):
        self.max_concurrent = max_concurrent
        self.max_utilization = max_cluster_utilization
    
    def should_proceed(self):
        """Check if we can launch another backfill job."""
        current_util = get_cluster_utilization()  # YARN/Spark metrics
        current_jobs = get_running_backfill_jobs()
        
        if current_jobs >= self.max_concurrent:
            return False, "Max concurrent jobs reached"
        if current_util > self.max_utilization:
            return False, f"Cluster at {current_util*100}% utilization"
        return True, "OK"
    
    def wait_for_slot(self, timeout_minutes=30):
        """Block until a slot is available."""
        start = time.time()
        while time.time() - start < timeout_minutes * 60:
            can_proceed, reason = self.should_proceed()
            if can_proceed:
                return True
            time.sleep(30)
        raise TimeoutError("Backfill throttle timeout")
```

## Scaling Strategies

### Parallel Partition Processing

| Date Range | Partitions | Parallelism | Duration | Cost |
|-----------|-----------|-------------|----------|------|
| 1 month | 30 | 5 concurrent | 6 hours | $180 |
| 3 months | 90 | 10 concurrent | 9 hours | $540 |
| 1 year | 365 | 10 concurrent | 36 hours | $2,200 |
| 2 years | 730 | 20 concurrent | 36 hours | $4,400 |

### Priority-based Scheduling

```python
# Backfill recent data first (more business impact)
# Then work backwards chronologically

def prioritized_backfill(start_date, end_date):
    """Process most recent dates first."""
    dates = []
    current = end_date
    while current >= start_date:
        dates.append(current)
        current -= timedelta(days=1)
    
    # Recent dates get higher priority in Airflow
    for i, date in enumerate(dates):
        priority = 100 - i  # Higher priority for recent
        submit_backfill_task(date, priority_weight=priority)
```

## Failure Handling

### Checkpoint and Resume

```python
def backfill_with_checkpoints(table, start_date, end_date):
    """Resume backfill from last successful checkpoint."""
    
    # Check for existing checkpoint
    checkpoint = load_checkpoint(table)
    if checkpoint:
        resume_date = checkpoint['last_successful_date'] + timedelta(days=1)
        print(f"Resuming from {resume_date} (previously completed to {checkpoint['last_successful_date']})")
    else:
        resume_date = start_date
    
    current = resume_date
    while current <= end_date:
        try:
            process_partition(table, current)
            save_checkpoint(table, current)  # Persist progress
            current += timedelta(days=1)
        except Exception as e:
            save_checkpoint(table, current - timedelta(days=1), status="failed", error=str(e))
            raise
```

### Rollback Strategy

```python
def safe_backfill_with_rollback(table, date_range):
    """Keep previous version available for instant rollback."""
    
    # Option 1: Delta Lake time travel
    pre_backfill_version = get_current_version(table)
    
    try:
        run_backfill(table, date_range)
        validate_backfill(table, date_range)
    except (BackfillError, ValidationError):
        # Instant rollback via Delta time travel
        spark.sql(f"RESTORE TABLE {table} TO VERSION AS OF {pre_backfill_version}")
        raise
    
    # Option 2: For non-Delta tables, snapshot before backfill
    # CREATE TABLE table_backup_20240115 AS SELECT * FROM table
    # ... run backfill ...
    # If failed: DROP TABLE table; ALTER TABLE table_backup RENAME TO table;
```

## Cost Optimization

### Cost Model for Backfill Scenarios

| Scenario | Data Volume | Cluster | Duration | Cost |
|----------|-------------|---------|----------|------|
| Bug fix (1 table, 30 days) | 500GB | 20x r5.4xl | 3 hours | $72 |
| Schema change (10 tables, 90 days) | 5TB | 50x r5.4xl | 8 hours | $480 |
| Full rebuild (100 tables, 1 year) | 50TB | 100x r5.4xl | 48 hours | $14,400 |
| New feature (1 table, 2 years) | 10TB | 50x r5.4xl | 12 hours | $720 |

### Cost Reduction

1. **Spot instances for backfill** - Non-urgent, can tolerate interruptions (70% savings)
2. **Off-peak scheduling** - Run during nights/weekends when cluster is idle
3. **Incremental approach** - Only reprocess affected partitions, not entire table
4. **Columnar output** - Parquet/ORC reduces downstream reprocessing scope
5. **Skip unchanged data** - If only one column's logic changed, use Delta MERGE on that column

## Real-World Companies

| Company | Pattern | Scale |
|---------|---------|-------|
| Netflix | Blue-green tables | PB-scale, daily backfills |
| Airbnb | Partition-based + Airflow | 50TB+ backfills monthly |
| Uber | Shadow pipelines | Verify before cutover |
| Spotify | Versioned datasets | Immutable data, version pointers |
| LinkedIn | Incremental + validation gates | Billions of records |
| Stripe | Idempotent + checksums | Financial data accuracy critical |

## Decision Matrix

| Scenario | Recommended Pattern | Reason |
|----------|-------------------|--------|
| Logic fix, small table (< 1TB) | Full rebuild (blue-green) | Fast, simple, safe |
| Logic fix, large table (> 10TB) | Partition-based reprocessing | Incremental progress, lower cost |
| New pipeline version | Shadow pipeline + comparison | Validate before committing |
| Urgent hotfix | Partition overwrite, recent first | Prioritize business impact |
| Source data correction | Targeted partition reprocess | Only affected dates |
| GDPR deletion | Targeted rewrite | Minimize blast radius |
| ML feature backfill | Blue-green + canary | Don't disrupt existing consumers |

## Anti-Patterns

1. **No validation gates** - Backfill silently produces wrong data, discovered weeks later
2. **Processing in chronological order** - Recent data has more business value; work backwards
3. **No throttling** - Backfill saturates cluster, kills production pipelines
4. **Append mode for backfill** - Creates duplicates; always use overwrite/merge
5. **No checkpointing** - 48-hour backfill fails at hour 40; must restart from scratch
6. **Changing production in-place** - No rollback path if backfill is wrong
7. **No downstream notification** - Consumers use stale cached data; cache invalidation needed
8. **Single giant job** - One OOM kills everything; partition into independent units
