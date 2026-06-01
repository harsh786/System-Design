# ETL/ELT Pipelines for ML

## ETL vs ELT

```
┌─────────────────────────────────────────────────────────────────┐
│  ETL (Extract → Transform → Load)                                │
│  ─────────────────────────────────                               │
│  Source → [Transform in pipeline] → Load to warehouse            │
│  Use when: Data needs cleaning before loading, compliance        │
│                                                                   │
│  ELT (Extract → Load → Transform)                                │
│  ─────────────────────────────────                               │
│  Source → Load raw to warehouse → [Transform in warehouse]       │
│  Use when: Warehouse is powerful (BigQuery, Snowflake), dbt      │
│                                                                   │
│  Modern ML pipelines are mostly ELT:                             │
│  Raw data lake → Transform with Spark/dbt → Feature store        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Architecture Patterns

```
┌───────────────────────────────────────────────────────────────┐
│  Pattern 1: Batch ML Feature Pipeline                          │
│                                                                │
│  Sources ──→ Ingestion ──→ Raw Layer ──→ Transform ──→ Feature│
│  (APIs,DB)   (Airflow)    (S3/GCS)     (Spark/dbt)    Store  │
│                                                                │
│  Pattern 2: Lambda Architecture                                │
│                                                                │
│  Events ──┬──→ Batch Layer (daily) ──→ Serving Layer          │
│           └──→ Speed Layer (real-time) ──┘                    │
│                                                                │
│  Pattern 3: Medallion Architecture (Databricks)                │
│                                                                │
│  Bronze (raw) ──→ Silver (cleaned) ──→ Gold (aggregated)      │
└───────────────────────────────────────────────────────────────┘
```

---

## Apache Airflow

### DAG Example: ML Feature Pipeline

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.utils.dates import days_ago
from datetime import timedelta

default_args = {
    "owner": "ml-team",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": True,
    "email": ["ml-team@company.com"],
}

with DAG(
    dag_id="ml_feature_pipeline",
    default_args=default_args,
    schedule_interval="0 6 * * *",  # Daily at 6am UTC
    start_date=days_ago(1),
    catchup=False,
    tags=["ml", "features"],
    max_active_runs=1,
) as dag:

    # Sensor: Wait for upstream data
    wait_for_events = S3KeySensor(
        task_id="wait_for_events",
        bucket_name="datalake",
        bucket_key="raw/events/dt={{ ds }}/",
        timeout=3600,
        poke_interval=60,
    )

    # Extract: Pull from external APIs
    def extract_user_data(**context):
        execution_date = context["ds"]
        # Pull data, save to S3
        pass

    extract = PythonOperator(
        task_id="extract_user_data",
        python_callable=extract_user_data,
    )

    # Transform: Spark job for features
    compute_features = SparkSubmitOperator(
        task_id="compute_features",
        application="s3://code/feature_engineering.py",
        conf={
            "spark.sql.adaptive.enabled": "true",
            "spark.executor.memory": "8g",
            "spark.executor.instances": "20",
        },
        application_args=["--date", "{{ ds }}"],
    )

    # Validate: Data quality
    def validate_features(**context):
        import great_expectations as gx
        # Run validation suite
        pass

    validate = PythonOperator(
        task_id="validate_features",
        python_callable=validate_features,
    )

    # Load to feature store
    def load_feature_store(**context):
        # Push to Feast/Tecton
        pass

    load = PythonOperator(
        task_id="load_feature_store",
        python_callable=load_feature_store,
    )

    # DAG dependencies
    wait_for_events >> extract >> compute_features >> validate >> load
```

### Airflow Best Practices

| Practice | Why |
|----------|-----|
| Idempotent tasks | Safe retries, backfills |
| Templated dates `{{ ds }}` | Correct data for each run |
| `catchup=False` for real-time | Avoid backlog on deploy |
| Short tasks (< 1hr each) | Easier debugging, retries |
| XComs for small data only | Not a data store |
| Separate DAGs per domain | Independent failures |
| Use sensors sparingly | They hold worker slots |

---

## dbt (Data Build Tool)

### Model Example: User Features

```sql
-- models/features/user_features.sql
{{
  config(
    materialized='incremental',
    unique_key='user_id',
    partition_by={'field': 'computed_date', 'data_type': 'date'},
    cluster_by=['user_id']
  )
}}

WITH user_orders AS (
    SELECT
        user_id,
        COUNT(*) AS total_orders,
        SUM(total_amount) AS lifetime_value,
        AVG(total_amount) AS avg_order_value,
        MAX(order_date) AS last_order_date,
        MIN(order_date) AS first_order_date
    FROM {{ ref('stg_orders') }}
    WHERE status = 'completed'
    {% if is_incremental() %}
      AND order_date >= (SELECT MAX(computed_date) FROM {{ this }}) - INTERVAL '3 days'
    {% endif %}
    GROUP BY user_id
),

user_events AS (
    SELECT
        user_id,
        COUNT(*) AS total_events,
        COUNT(DISTINCT session_id) AS total_sessions,
        SUM(CASE WHEN event_type = 'page_view' THEN 1 ELSE 0 END) AS page_views
    FROM {{ ref('stg_events') }}
    {% if is_incremental() %}
      AND event_date >= (SELECT MAX(computed_date) FROM {{ this }}) - INTERVAL '3 days'
    {% endif %}
    GROUP BY user_id
)

SELECT
    u.user_id,
    CURRENT_DATE AS computed_date,
    COALESCE(o.total_orders, 0) AS total_orders,
    COALESCE(o.lifetime_value, 0) AS lifetime_value,
    COALESCE(o.avg_order_value, 0) AS avg_order_value,
    DATE_DIFF(CURRENT_DATE, o.last_order_date, DAY) AS days_since_last_order,
    COALESCE(e.total_sessions, 0) AS total_sessions,
    COALESCE(e.page_views, 0) AS page_views,
    -- Derived features
    SAFE_DIVIDE(o.lifetime_value, DATE_DIFF(o.last_order_date, o.first_order_date, DAY) + 1) 
        AS daily_spend_rate
FROM {{ ref('stg_users') }} u
LEFT JOIN user_orders o ON u.user_id = o.user_id
LEFT JOIN user_events e ON u.user_id = e.user_id
```

### dbt Tests

```yaml
# models/features/schema.yml
version: 2
models:
  - name: user_features
    description: "ML features per user, computed daily"
    columns:
      - name: user_id
        tests:
          - unique
          - not_null
      - name: lifetime_value
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1000000
      - name: total_orders
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
```

---

## Data Quality: Great Expectations

```python
import great_expectations as gx

context = gx.get_context()

# Define expectations
validator = context.sources.pandas_default.read_parquet(
    "s3://datalake/features/user_features/"
)

validator.expect_column_values_to_not_be_null("user_id")
validator.expect_column_values_to_be_between("lifetime_value", min_value=0)
validator.expect_column_values_to_be_unique("user_id")
validator.expect_table_row_count_to_be_between(min_value=100000, max_value=10000000)

# Column distribution drift detection
validator.expect_column_mean_to_be_between("avg_order_value", min_value=20, max_value=200)
validator.expect_column_proportion_of_unique_values_to_be_between(
    "country", min_value=0.001, max_value=0.01
)

results = validator.validate()
if not results.success:
    raise ValueError(f"Data quality check failed: {results}")
```

---

## Idempotency Patterns

```python
# Pattern 1: Overwrite partition
df.write.mode("overwrite").partitionBy("date").parquet(output_path)
# Re-running same date just overwrites → same result

# Pattern 2: MERGE/upsert with Delta Lake
delta_table.alias("t").merge(
    new_data.alias("s"), "t.id = s.id"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

# Pattern 3: Tombstone + insert
# DELETE WHERE date = execution_date; INSERT new data for that date
```

---

## Error Handling and Retry

```python
# Exponential backoff with jitter
import time, random

def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)

# Dead letter queue pattern
def process_record(record):
    try:
        transform(record)
    except Exception as e:
        send_to_dlq(record, error=str(e))  # Don't block pipeline
```

---

## Modern Alternatives: Prefect & Dagster

```python
# Prefect example
from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1), retries=3)
def extract_data(date: str):
    return pull_from_source(date)

@task
def transform_features(raw_data):
    return compute_features(raw_data)

@flow(name="ml-feature-pipeline")
def feature_pipeline(date: str):
    raw = extract_data(date)
    features = transform_features(raw)
    validate(features)
    load_to_store(features)
```

---

## Monitoring & Alerting

```
┌────────────────────────────────────────────────────────┐
│  Pipeline Health Metrics to Monitor:                    │
├────────────────────────────────────────────────────────┤
│  • SLA: Did pipeline finish on time?                   │
│  • Data freshness: When was last successful run?       │
│  • Row counts: Unexpected drops/spikes?                │
│  • Schema changes: New/dropped columns?                │
│  • Null rates: Sudden increase in NULLs?              │
│  • Distribution drift: Mean/std deviation changes?     │
│  • Processing time: Getting slower over time?          │
└────────────────────────────────────────────────────────┘
```

---

## Interview Questions

1. **ETL vs ELT - when do you use each?**
   - ETL: Sensitive data needing masking before load, legacy systems. ELT: Cloud warehouses with compute power, exploratory analytics.

2. **How do you ensure pipeline idempotency?**
   - Partition overwrite, MERGE upserts, deterministic outputs for same inputs, no append-only without dedup.

3. **What happens when an Airflow task fails mid-pipeline?**
   - Downstream tasks skipped. Fix issue, clear failed task, it re-runs from that point (if idempotent).

4. **How does dbt's incremental materialization work?**
   - Only processes new/changed rows using `is_incremental()` filter. Needs unique_key for merge logic.

5. **What's the medallion architecture?**
   - Bronze (raw), Silver (cleaned/conformed), Gold (business-level aggregates). Progressive quality refinement.

6. **How do you handle schema evolution in pipelines?**
   - Schema registry, backward-compatible changes, versioned tables, Delta Lake schema evolution.

7. **What's exactly-once processing and why is it hard?**
   - Each record processed exactly once despite failures. Hard because retries can cause duplicates; need idempotent writes or transactions.

8. **How do you backfill a pipeline for historical data?**
   - Parameterize by date, enable catchup, process partitions independently, validate each.

9. **What data quality checks would you add to an ML pipeline?**
   - Null rates, value ranges, row counts, distribution stats, schema validation, freshness, uniqueness.

10. **How do you handle late-arriving data in batch pipelines?**
    - Reprocess N-day lookback window, use watermarks, SLA-based cutoffs with reconciliation jobs.
