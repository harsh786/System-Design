# Problem 1: Payment Reconciliation Pipeline (Stripe-Scale)

## The Problem

Stripe processes **2B+ transactions daily** across multiple payment processors (Visa, Mastercard, AMEX, PayPal, and 11+ others). Each processor sends settlement files at different times—some hourly, some daily, some with unpredictable delays. The reconciliation pipeline must:

- **Match every internal transaction** with the corresponding processor settlement record
- **Flag discrepancies within 4 hours** of file arrival (regulatory/compliance requirement)
- **Detect late or missing files** and trigger escalation to on-call teams
- **Handle retries idempotently**—a re-run must never double-count or lose transactions
- **Scale horizontally**—adding a new processor should not require re-architecting

## Scale Numbers

| Metric | Value |
|--------|-------|
| Transactions/day | 2 Billion |
| Payment processors | 15+ |
| Settlement file size | 500GB – 2TB each |
| Reconciliation SLA | Complete within 4 hours of file arrival |
| Discrepancy tolerance | Zero missed discrepancies |
| File arrival patterns | Hourly (Visa), Daily 2AM UTC (Mastercard), Irregular (PayPal) |
| Concurrent DAG runs | Up to 15 (one per processor) |
| Workers needed | 50-100 Celery workers for peak load |

## Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PAYMENT RECONCILIATION PIPELINE                        │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
  │  Visa    │   │Mastercard│   │   AMEX   │   │  PayPal  │  ... (15+)
  │ SFTP/S3  │   │ SFTP/S3  │   │ SFTP/S3  │   │  API/S3  │
  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
       │               │               │               │
       ▼               ▼               ▼               ▼
  ┌─────────────────────────────────────────────────────────────┐
  │              S3 Landing Zone (Raw Settlement Files)           │
  │         s3://payments-raw/{processor}/{date}/{file}           │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   S3KeySensor (per proc) │  ← mode='reschedule'
                    │   Waits for file arrival │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   validate_file_task     │  ← Check schema, row count
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐
  │ Extract &     │  │ Load Internal │  │ Partition Staging  │
  │ Parse Settle- │  │ Transactions  │  │ Table (DELETE +    │
  │ ment File     │  │ for Window    │  │ INSERT pattern)    │
  └───────┬───────┘  └───────┬───────┘  └───────────────────┘
          │                   │
          └─────────┬─────────┘
                    ▼
       ┌────────────────────────┐
       │   RECONCILE            │  ← Full outer join matching
       │   Match on txn_id,    │
       │   amount, currency     │
       └────────────┬───────────┘
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
  ┌──────────┐ ┌────────┐ ┌────────────┐
  │ Matched  │ │ Unmatch│ │ Discrepan- │
  │ (happy   │ │ -ed    │ │ cies       │
  │  path)   │ │        │ │ (amount    │
  │          │ │        │ │  mismatch) │
  └────┬─────┘ └───┬────┘ └─────┬──────┘
       │            │            │
       ▼            ▼            ▼
  ┌─────────────────────────────────────┐
  │   Load to Data Warehouse            │
  │   (Snowflake/BigQuery/Redshift)     │
  └──────────────────┬──────────────────┘
                     │
          ┌──────────┼──────────┐
          ▼                     ▼
  ┌──────────────┐    ┌──────────────────┐
  │ Alert if     │    │ Update Recon     │
  │ discrepancy  │    │ Coverage Metrics │
  │ > threshold  │    │ (DataDog)        │
  └──────────────┘    └──────────────────┘
```

## Airflow Concepts Taught in This Problem

### 1. DAG Structure & Definition

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.decorators import task

default_args = {
    # --- Retry Configuration ---
    'retries': 3,                          # Retry 3 times before marking failed
    'retry_delay': timedelta(minutes=5),   # Wait 5 min between retries
    'retry_exponential_backoff': True,     # 5m, 10m, 20m instead of 5m, 5m, 5m
    'max_retry_delay': timedelta(minutes=30),  # Cap at 30 min

    # --- Timeouts ---
    'execution_timeout': timedelta(hours=2),   # Kill task if running > 2 hours
    'dagrun_timeout': timedelta(hours=4),      # Entire DAG run must finish in 4h

    # --- Ownership ---
    'owner': 'payments-data-eng',
    'email': ['payments-oncall@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,  # Don't spam on retries, only final failure

    # --- Dependencies ---
    'depends_on_past': False,  # Each run is independent (file-based trigger)
}

dag = DAG(
    dag_id='payment_reconciliation_visa',
    default_args=default_args,
    description='Reconcile Visa settlement files with internal transaction records',
    schedule='0 */1 * * *',          # Every hour (Visa sends hourly files)
    start_date=datetime(2024, 1, 1), # Historical start for backfills
    catchup=False,                   # Don't backfill on deploy—use manual backfill
    max_active_runs=1,               # Only one reconciliation at a time per processor
    max_active_tasks=10,             # Limit parallelism within a run
    tags=['payments', 'reconciliation', 'visa', 'tier-0'],
    doc_md=__doc__,
)
```

**Why `max_active_runs=1`?** If the hourly run at 2:00 is still processing when 3:00 triggers, we don't want overlapping reconciliations writing to the same partition. This prevents race conditions.

**Why `catchup=False`?** On deployment, we don't want Airflow to schedule runs for every missed interval. Backfills are done intentionally via `airflow dags backfill`.

### 2. Scheduling Deep Dive

#### Cron Expressions for Different Processors

```python
# Visa: hourly files
VISA_SCHEDULE = '0 */1 * * *'  # Every hour at :00

# Mastercard: daily file arrives ~2AM UTC
MASTERCARD_SCHEDULE = '30 2 * * *'  # 2:30 AM (30 min buffer after expected arrival)

# AMEX: twice daily
AMEX_SCHEDULE = '0 6,18 * * *'  # 6AM and 6PM UTC

# PayPal: irregular — use sensor-only pattern (externally triggered)
PAYPAL_SCHEDULE = None  # Triggered by external event (Lambda → Airflow API)
```

#### execution_date vs logical_date vs data_interval

This is the **most misunderstood concept in Airflow**:

```python
# For a DAG scheduled at '0 */1 * * *' (hourly):
# If current time is 2024-03-15 15:30 UTC, the RUNNING dag run has:
#
#   logical_date (execution_date) = 2024-03-15T14:00:00+00:00
#   data_interval_start            = 2024-03-15T14:00:00+00:00
#   data_interval_end              = 2024-03-15T15:00:00+00:00
#
# The run at 15:00 processes data from the 14:00-15:00 window!

# BAD: Using "now" to determine which data to process
@task
def bad_extract():
    """WRONG: This breaks on backfills and retries."""
    from datetime import datetime
    current_hour = datetime.utcnow().strftime('%Y-%m-%d/%H')
    file_path = f's3://raw/visa/{current_hour}/settlement.csv'
    # On retry at 16:45, this would look for the 16:00 file, not 14:00!

# GOOD: Using template variables
@task
def good_extract(**context):
    """CORRECT: Uses the logical data interval."""
    ds = context['ds']  # '2024-03-15'
    data_interval_start = context['data_interval_start']  # datetime object
    hour = data_interval_start.strftime('%H')
    file_path = f's3://raw/visa/{ds}/{hour}/settlement.csv'
    # Always processes the correct hour, even on retry or backfill
```

#### Custom Timetable for Irregular Schedules

```python
from airflow.timetables.base import DagRunInfo, DataInterval, TimeRestriction, Timetable
from pendulum import DateTime, Duration, instance

class ProcessorFileTimetable(Timetable):
    """Custom timetable that triggers based on known processor schedules.
    
    PayPal sends files at irregular times. We define expected windows
    and trigger when the file actually arrives (via dataset or API trigger).
    """

    def __init__(self, expected_windows: list[tuple[int, int]]):
        # e.g., [(2, 4), (14, 16)] means files expected between 2-4AM and 2-4PM
        self.expected_windows = expected_windows

    def next_dagrun_info(self, *, last_automated_data_interval, restriction):
        # Implementation for custom scheduling logic
        ...
```

### 3. Retry Strategy & Fault Tolerance

```python
from airflow.models import TaskInstance
import requests

def on_retry_callback(context: dict):
    """Alert on retry — but don't page yet (that's on_failure)."""
    ti: TaskInstance = context['ti']
    try_number = context['ti'].try_number
    
    requests.post(
        'https://hooks.slack.com/services/XXX',
        json={
            'channel': '#payments-alerts',
            'text': (
                f":warning: *Retry {try_number}/3* | "
                f"Task `{ti.task_id}` in `{ti.dag_id}` | "
                f"Run: {context['logical_date']} | "
                f"Exception: {context.get('exception', 'unknown')}"
            )
        }
    )

def on_failure_callback(context: dict):
    """All retries exhausted — page on-call."""
    ti: TaskInstance = context['ti']
    
    # PagerDuty escalation
    requests.post(
        'https://events.pagerduty.com/v2/enqueue',
        json={
            'routing_key': 'PAYMENTS_RECON_PD_KEY',
            'event_action': 'trigger',
            'payload': {
                'summary': f'Payment Recon FAILED: {ti.task_id} for {context["ds"]}',
                'severity': 'critical',
                'source': f'airflow:{ti.dag_id}',
                'custom_details': {
                    'logical_date': str(context['logical_date']),
                    'task_id': ti.task_id,
                    'log_url': ti.log_url,
                }
            }
        }
    )

# Per-task retry override for flaky external dependencies
file_sensor_retries = {
    'retries': 12,                          # Wait longer for file arrival
    'retry_delay': timedelta(minutes=15),   # Check every 15 min
    'execution_timeout': timedelta(hours=6), # File can be up to 6h late
}

reconciliation_retries = {
    'retries': 2,                           # Logic errors won't fix themselves
    'retry_delay': timedelta(minutes=2),
    'execution_timeout': timedelta(hours=2),
}
```

**When to retry vs when to fail:**

| Scenario | Retry? | Why |
|----------|--------|-----|
| S3 file not yet available | Yes (many times) | File may be late |
| Network timeout to warehouse | Yes (3x) | Transient |
| Schema validation failure | No | Data issue, needs human |
| Reconciliation logic error | Yes (1x) | Could be transient lock | 
| Out of memory | No | Needs resource tuning |

### 4. Idempotency at Scale

Payment reconciliation **MUST** be idempotent. A re-run should produce the exact same result without duplicating or losing data.

#### BAD: Append-only (causes duplicates on retry)

```python
# BAD: If this task retries, it appends the same data again
@task
def bad_load_results(reconciled_data):
    spark.sql("""
        INSERT INTO reconciliation_results
        SELECT * FROM staging_reconciled
    """)
    # Retry = duplicate rows!
```

#### GOOD: DELETE + INSERT (partition replacement)

```python
@task
def good_load_results(**context):
    """Idempotent load using partition replacement."""
    ds = context['ds']
    processor = 'visa'
    hour = context['data_interval_start'].strftime('%H')
    
    partition_key = f"{ds}/{processor}/{hour}"
    
    # Step 1: Delete existing results for this partition
    spark.sql(f"""
        DELETE FROM reconciliation_results
        WHERE partition_key = '{partition_key}'
    """)
    
    # Step 2: Insert fresh results
    spark.sql(f"""
        INSERT INTO reconciliation_results
        SELECT *, '{partition_key}' as partition_key
        FROM staging_reconciled
        WHERE processing_date = '{ds}' AND processor = '{processor}' AND hour = '{hour}'
    """)
    # Safe to retry: delete+insert is idempotent
```

#### GOOD: MERGE/UPSERT Pattern

```python
@task
def merge_reconciliation_results(**context):
    """Idempotent using MERGE — preferred for warehouses that support it."""
    ds = context['ds']
    
    spark.sql(f"""
        MERGE INTO reconciliation_results AS target
        USING staging_reconciled AS source
        ON target.transaction_id = source.transaction_id
           AND target.processor = source.processor
           AND target.settlement_date = '{ds}'
        WHEN MATCHED THEN UPDATE SET
            match_status = source.match_status,
            discrepancy_amount = source.discrepancy_amount,
            updated_at = current_timestamp()
        WHEN NOT MATCHED THEN INSERT (
            transaction_id, processor, settlement_date,
            match_status, discrepancy_amount, created_at
        ) VALUES (
            source.transaction_id, source.processor, '{ds}',
            source.match_status, source.discrepancy_amount, current_timestamp()
        )
    """)
```

### 5. execution_date and Logical Date

```python
# The mental model:
#
# Schedule: hourly
# 
# Time:    00:00    01:00    02:00    03:00
#            |--------|--------|--------|
#            |  Run 1 |  Run 2 |  Run 3 |
#            |        |        |        |
# Run 1:    logical_date=00:00, processes data [00:00, 01:00)
#           Actually STARTS running at 01:00 (after interval completes)
#
# Run 2:    logical_date=01:00, processes data [01:00, 02:00)
#           Actually STARTS running at 02:00

# Template variables available in tasks:
# {{ ds }}                    → '2024-03-15'
# {{ ds_nodash }}             → '20240315'
# {{ logical_date }}          → DateTime object
# {{ data_interval_start }}   → Start of data window
# {{ data_interval_end }}     → End of data window
# {{ ts }}                    → ISO timestamp of logical_date
# {{ execution_date }}        → DEPRECATED alias for logical_date

# Backfill example:
# $ airflow dags backfill payment_reconciliation_visa \
#     --start-date 2024-03-01 --end-date 2024-03-10
#
# This creates 240 DAG runs (10 days × 24 hours), each with correct
# data_interval_start/end. Tasks use these to fetch the right files.
```

---

## Production Implementation (Full Code)

```python
"""
Payment Reconciliation DAG — Visa Processor
============================================

Reconciles Visa settlement files against internal transaction records.
Runs hourly. SLA: complete within 4 hours of file arrival.

Owner: payments-data-eng
Escalation: #payments-oncall → PagerDuty (payments-recon)
"""

from datetime import datetime, timedelta
from typing import Any

from airflow import DAG
from airflow.decorators import task, task_group
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.exceptions import AirflowSkipException
from airflow.models import Variable
import logging

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

PROCESSOR = 'visa'
S3_BUCKET = 'payments-settlement-files'
S3_PREFIX_TEMPLATE = '{processor}/{ds}/{hour}/'
WAREHOUSE_SCHEMA = 'reconciliation'
DISCREPANCY_THRESHOLD_USD = 0.01  # Flag any mismatch > 1 cent
COVERAGE_THRESHOLD_PCT = 99.5     # Alert if < 99.5% transactions matched

# ─── Callbacks ───────────────────────────────────────────────────────────────

def on_retry_callback(context: dict):
    ti = context['ti']
    logger.warning(
        f"Retry {ti.try_number} for {ti.task_id} | "
        f"DAG: {ti.dag_id} | Date: {context['ds']}"
    )

def on_failure_callback(context: dict):
    ti = context['ti']
    # PagerDuty integration
    import requests
    requests.post(
        'https://events.pagerduty.com/v2/enqueue',
        json={
            'routing_key': Variable.get('pagerduty_recon_key'),
            'event_action': 'trigger',
            'payload': {
                'summary': f'[CRITICAL] Recon failed: {ti.task_id} for {context["ds"]}',
                'severity': 'critical',
                'source': f'airflow:{ti.dag_id}',
            }
        },
        timeout=10
    )

def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """Called when DAG misses its SLA."""
    import requests
    requests.post(
        'https://hooks.slack.com/services/XXX',
        json={
            'text': f":rotating_light: SLA MISS: {dag.dag_id} | "
                    f"Tasks: {[t.task_id for t in task_list]}"
        },
        timeout=10
    )

# ─── Default Args ────────────────────────────────────────────────────────────

default_args = {
    'owner': 'payments-data-eng',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=30),
    'execution_timeout': timedelta(hours=2),
    'on_retry_callback': on_retry_callback,
    'on_failure_callback': on_failure_callback,
    'email': ['payments-oncall@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

# ─── DAG Definition ──────────────────────────────────────────────────────────

with DAG(
    dag_id=f'payment_reconciliation_{PROCESSOR}',
    default_args=default_args,
    description=f'Reconcile {PROCESSOR} settlement files with internal records',
    schedule='0 */1 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=8,
    sla_miss_callback=sla_miss_callback,
    tags=['payments', 'reconciliation', PROCESSOR, 'tier-0'],
    doc_md=__doc__,
) as dag:

    # ─── Sensor: Wait for Settlement File ────────────────────────────────────

    wait_for_file = S3KeySensor(
        task_id='wait_for_settlement_file',
        bucket_name=S3_BUCKET,
        bucket_key=(
            f'{PROCESSOR}/{{{{ ds }}}}/{{{{ data_interval_start.strftime("%H") }}}}/'
            f'settlement_*.csv'
        ),
        wildcard_match=True,
        aws_conn_id='aws_payments',
        mode='reschedule',        # FREE UP WORKER SLOT while waiting
        poke_interval=300,        # Check every 5 minutes
        timeout=6 * 3600,         # Wait up to 6 hours for file
        soft_fail=False,          # Hard fail if file never arrives
        exponential_backoff=True,
    )
    # mode='reschedule' vs mode='poke':
    # - 'poke': holds the worker slot, sleeping between checks (wastes resources)
    # - 'reschedule': releases worker, gets rescheduled (correct for long waits)

    # ─── Validate File ───────────────────────────────────────────────────────

    @task(retries=1, retry_delay=timedelta(minutes=1))
    def validate_settlement_file(**context) -> dict:
        """Validate file schema, row count, and checksums."""
        ds = context['ds']
        hour = context['data_interval_start'].strftime('%H')
        
        s3_hook = S3Hook(aws_conn_id='aws_payments')
        prefix = f'{PROCESSOR}/{ds}/{hour}/'
        keys = s3_hook.list_keys(bucket_name=S3_BUCKET, prefix=prefix)
        
        if not keys:
            raise FileNotFoundError(f"No files found at {prefix}")
        
        file_key = keys[0]
        metadata = s3_hook.head_object(key=file_key, bucket_name=S3_BUCKET)
        
        file_size_gb = metadata['ContentLength'] / (1024**3)
        logger.info(f"Settlement file: {file_key} | Size: {file_size_gb:.2f} GB")
        
        if file_size_gb < 0.1:  # Suspiciously small
            raise ValueError(
                f"File too small ({file_size_gb:.2f} GB). "
                f"Expected > 0.1 GB for {PROCESSOR}. Possible truncation."
            )
        
        return {
            'file_key': file_key,
            'file_size_gb': file_size_gb,
            'processor': PROCESSOR,
            'date': ds,
            'hour': hour,
        }

    # ─── Extract & Parse ─────────────────────────────────────────────────────

    @task(execution_timeout=timedelta(hours=1))
    def extract_settlement_data(file_info: dict, **context) -> str:
        """Parse settlement file and load to staging table."""
        from pyspark.sql import SparkSession
        
        spark = SparkSession.builder.getOrCreate()
        
        file_path = f"s3a://{S3_BUCKET}/{file_info['file_key']}"
        
        # Read with explicit schema (never infer on production data)
        settlement_df = spark.read.csv(
            file_path,
            header=True,
            schema="""
                transaction_id STRING,
                amount DECIMAL(18,2),
                currency STRING,
                merchant_id STRING,
                settlement_date DATE,
                processor_ref STRING,
                status STRING
            """,
        )
        
        row_count = settlement_df.count()
        logger.info(f"Parsed {row_count:,} settlement records from {file_info['file_key']}")
        
        # Write to staging (overwrite partition for idempotency)
        partition_key = f"{file_info['date']}/{file_info['hour']}"
        staging_table = f"{WAREHOUSE_SCHEMA}.stg_settlement_{PROCESSOR}"
        
        settlement_df.write.mode('overwrite').partitionBy(
            'settlement_date'
        ).saveAsTable(staging_table)
        
        return staging_table

    # ─── Load Internal Transactions ──────────────────────────────────────────

    @task(execution_timeout=timedelta(hours=1))
    def load_internal_transactions(**context) -> str:
        """Load internal transaction records for the reconciliation window."""
        from pyspark.sql import SparkSession
        
        spark = SparkSession.builder.getOrCreate()
        ds = context['ds']
        hour = context['data_interval_start'].strftime('%H')
        
        # Query internal transactions for this window
        # Add buffer: look at transactions from -2h to +1h around settlement window
        internal_df = spark.sql(f"""
            SELECT 
                transaction_id,
                amount,
                currency,
                merchant_id,
                processor_ref,
                created_at,
                status
            FROM payments.transactions
            WHERE DATE(created_at) = '{ds}'
              AND HOUR(created_at) BETWEEN {int(hour)} - 2 AND {int(hour)} + 1
              AND processor = '{PROCESSOR}'
        """)
        
        row_count = internal_df.count()
        logger.info(f"Loaded {row_count:,} internal transactions for {ds} hour {hour}")
        
        staging_table = f"{WAREHOUSE_SCHEMA}.stg_internal_{PROCESSOR}"
        internal_df.write.mode('overwrite').saveAsTable(staging_table)
        
        return staging_table

    # ─── Reconciliation ──────────────────────────────────────────────────────

    @task(execution_timeout=timedelta(hours=2), retries=2)
    def reconcile_transactions(
        settlement_table: str,
        internal_table: str,
        **context
    ) -> dict:
        """Core reconciliation: match settlement records against internal."""
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
        
        spark = SparkSession.builder.getOrCreate()
        ds = context['ds']
        hour = context['data_interval_start'].strftime('%H')
        partition_key = f"{ds}/{PROCESSOR}/{hour}"
        
        # Full outer join — find matched, unmatched, and discrepancies
        result = spark.sql(f"""
            WITH reconciled AS (
                SELECT
                    COALESCE(s.transaction_id, i.transaction_id) AS transaction_id,
                    s.amount AS settlement_amount,
                    i.amount AS internal_amount,
                    s.currency AS settlement_currency,
                    i.currency AS internal_currency,
                    CASE
                        WHEN s.transaction_id IS NULL THEN 'MISSING_IN_SETTLEMENT'
                        WHEN i.transaction_id IS NULL THEN 'MISSING_IN_INTERNAL'
                        WHEN ABS(s.amount - i.amount) > {DISCREPANCY_THRESHOLD_USD}
                            THEN 'AMOUNT_MISMATCH'
                        WHEN s.currency != i.currency THEN 'CURRENCY_MISMATCH'
                        ELSE 'MATCHED'
                    END AS match_status,
                    ABS(COALESCE(s.amount, 0) - COALESCE(i.amount, 0)) 
                        AS discrepancy_amount
                FROM {settlement_table} s
                FULL OUTER JOIN {internal_table} i
                    ON s.transaction_id = i.transaction_id
            )
            SELECT * FROM reconciled
        """)
        
        # Idempotent write: DELETE then INSERT
        spark.sql(f"""
            DELETE FROM {WAREHOUSE_SCHEMA}.reconciliation_results
            WHERE partition_key = '{partition_key}'
        """)
        
        result.withColumn('partition_key', F.lit(partition_key)) \
              .withColumn('reconciled_at', F.current_timestamp()) \
              .write.mode('append') \
              .insertInto(f'{WAREHOUSE_SCHEMA}.reconciliation_results')
        
        # Compute stats
        stats = result.groupBy('match_status').count().collect()
        stats_dict = {row['match_status']: row['count'] for row in stats}
        
        total = sum(stats_dict.values())
        matched = stats_dict.get('MATCHED', 0)
        coverage_pct = (matched / total * 100) if total > 0 else 0
        
        logger.info(f"Reconciliation complete: {stats_dict}")
        logger.info(f"Coverage: {coverage_pct:.2f}%")
        
        return {
            'stats': stats_dict,
            'total': total,
            'matched': matched,
            'coverage_pct': coverage_pct,
            'partition_key': partition_key,
        }

    # ─── Discrepancy Alerting ────────────────────────────────────────────────

    @task
    def check_discrepancies(recon_result: dict, **context):
        """Alert if discrepancies exceed threshold."""
        stats = recon_result['stats']
        coverage = recon_result['coverage_pct']
        
        discrepancies = (
            stats.get('AMOUNT_MISMATCH', 0) +
            stats.get('MISSING_IN_SETTLEMENT', 0) +
            stats.get('MISSING_IN_INTERNAL', 0) +
            stats.get('CURRENCY_MISMATCH', 0)
        )
        
        if coverage < COVERAGE_THRESHOLD_PCT:
            raise ValueError(
                f"Coverage {coverage:.2f}% below threshold {COVERAGE_THRESHOLD_PCT}%. "
                f"Discrepancies: {discrepancies:,} out of {recon_result['total']:,}"
            )
        
        if discrepancies > 0:
            logger.warning(f"Found {discrepancies:,} discrepancies (within tolerance)")
            # Post to monitoring but don't fail
            import requests
            requests.post(
                'https://hooks.slack.com/services/XXX',
                json={
                    'text': (
                        f":mag: *Recon Discrepancies* | {PROCESSOR} | {context['ds']} "
                        f"H{context['data_interval_start'].strftime('%H')}\n"
                        f"• Matched: {recon_result['matched']:,}\n"
                        f"• Discrepancies: {discrepancies:,}\n"
                        f"• Coverage: {coverage:.2f}%"
                    )
                },
                timeout=10
            )

    # ─── Publish Metrics ─────────────────────────────────────────────────────

    @task
    def publish_metrics(recon_result: dict, **context):
        """Push reconciliation metrics to DataDog."""
        from datadog import statsd
        
        tags = [f'processor:{PROCESSOR}', f'date:{context["ds"]}']
        
        statsd.gauge('recon.coverage_pct', recon_result['coverage_pct'], tags=tags)
        statsd.gauge('recon.total_transactions', recon_result['total'], tags=tags)
        statsd.gauge('recon.matched', recon_result['matched'], tags=tags)
        
        for status, count in recon_result['stats'].items():
            statsd.gauge(f'recon.status.{status.lower()}', count, tags=tags)

    # ─── DAG Wiring ──────────────────────────────────────────────────────────

    file_info = validate_settlement_file()
    settlement_table = extract_settlement_data(file_info)
    internal_table = load_internal_transactions()
    
    recon_result = reconcile_transactions(settlement_table, internal_table)
    
    check_discrepancies(recon_result)
    publish_metrics(recon_result)
    
    # Dependency chain
    wait_for_file >> file_info
```

---

## Production Handling

### What happens when a processor file is late?

```python
# The S3KeySensor with mode='reschedule' handles this:
# - Checks every 5 minutes (poke_interval=300)
# - Releases worker slot between checks
# - Times out after 6 hours (timeout=6*3600)
# - On timeout: task FAILS → on_failure_callback → PagerDuty page

# For known delayed processors, use a separate "file_sla_monitor" DAG:
# This DAG runs on a schedule and checks if expected files have arrived.
# If not, it alerts BEFORE the reconciliation DAG even triggers.
```

### What happens when reconciliation fails mid-way?

The DELETE + INSERT pattern ensures safety:

1. **If extract fails**: No data in staging → no impact on results table
2. **If reconciliation fails after DELETE but before INSERT**: Next retry will DELETE (no-op since already empty) then INSERT fresh
3. **If metrics publishing fails**: Reconciliation data is already persisted → retry only publishes metrics

### Handling partial failures (some processors reconciled, others not)

```python
# Each processor has its own DAG. Failures are isolated.
# A cross-processor "coverage monitor" DAG checks overall health:

@task
def check_overall_coverage(**context):
    """Runs every 4 hours — checks all processors reconciled."""
    ds = context['ds']
    
    results = spark.sql(f"""
        SELECT 
            processor,
            MAX(reconciled_at) as last_recon,
            COUNT(DISTINCT hour) as hours_covered
        FROM reconciliation.reconciliation_results
        WHERE date = '{ds}'
        GROUP BY processor
    """).collect()
    
    expected_processors = Variable.get('active_processors', deserialize_json=True)
    
    covered = {row['processor'] for row in results}
    missing = set(expected_processors) - covered
    
    if missing:
        raise ValueError(f"Processors not yet reconciled for {ds}: {missing}")
```

### Monitoring Reconciliation Coverage

Key metrics to track (DataDog/Grafana):

- `recon.coverage_pct` per processor per hour — alert if < 99.5%
- `recon.latency_seconds` — time from file arrival to reconciliation complete
- `recon.file_arrival_delay` — how late the file was vs expected
- `recon.dag_run_duration` — total DAG run time (alert if approaching 4h SLA)

---

## Key Takeaways

- **`mode='reschedule'`** on sensors: never hold a worker slot while waiting for external events
- **`max_active_runs=1`**: prevent overlapping runs that write to the same partitions
- **`catchup=False`** + manual backfill: control when historical processing happens
- **`execution_date`/`logical_date`** represents the DATA interval, not when the task runs — this is critical for backfills and retries
- **Idempotency via DELETE + INSERT**: any task can be safely retried without duplicating data
- **Exponential backoff on retries**: `retry_exponential_backoff=True` prevents thundering herd on transient failures
- **Separate failure callbacks by severity**: `on_retry_callback` → Slack warning; `on_failure_callback` → PagerDuty page
- **Per-task timeout overrides**: sensors need long timeouts; compute tasks need short ones
- **One DAG per processor**: isolate failures, scale independently, deploy independently
- **Template variables (`{{ ds }}`, `{{ data_interval_start }}`)**: always use these instead of `datetime.now()` — they make backfills and retries work correctly
- **SLA miss callbacks**: detect when the entire pipeline is running late, independent of individual task failures
