# Production Issues 46-60: DAG Design & Logic Issues

---

## Issue #46: Non-Idempotent Tasks Causing Duplicate Data

**Symptoms:**
- Retry produces duplicate rows in warehouse
- Manual re-run doubles the data for that partition
- Row counts don't match source after re-processing
- SUM/COUNT metrics inflated after failures

**Root Cause:**
- Tasks use INSERT without first cleaning target partition
- No deduplication logic in write path
- Append-only writes without idempotency key
- Developer unaware that Airflow retries automatically

**Fix:**
```python
# BAD: Append-only (duplicates on retry)
@task
def load_data(date: str):
    df = extract_for_date(date)
    df.to_sql('orders', engine, if_exists='append')  # DUPLICATE on retry!

# GOOD: Delete + Insert (partition-level idempotency)
@task
def load_data(date: str):
    df = extract_for_date(date)
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM orders WHERE order_date = :date"), {"date": date})
        df.to_sql('orders', conn, if_exists='append', index=False)

# GOOD: MERGE/UPSERT (row-level idempotency)
@task
def load_data(date: str):
    df = extract_for_date(date)
    # Spark SQL MERGE
    spark.sql(f"""
        MERGE INTO warehouse.orders AS target
        USING staging.orders AS source
        ON target.order_id = source.order_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

# GOOD: Partition overwrite (Spark/Hive)
@task
def load_data(date: str):
    df = spark.read.parquet(f's3://raw/orders/date={date}/')
    df.write.mode('overwrite').partitionBy('date').saveAsTable('orders')
    # 'overwrite' replaces the specific partition, not entire table
```

---

## Issue #47: XCom Used for Large Data Transfer Between Tasks

**Symptoms:**
- Metadata DB growing rapidly (XCom table GBs)
- Tasks slow due to serialization/deserialization overhead
- Out of memory during XCom push (large DataFrame serialized)
- DB connection timeout during XCom write

**Root Cause:**
- Developers treating XCom as data pipeline (passing DataFrames)
- TaskFlow API makes it "easy" to return large objects
- No guardrails on XCom size
- Misunderstanding: XCom is for metadata, not data

**Fix:**
```python
# BAD: Passing data through XCom
@task
def extract():
    df = pd.read_parquet('s3://bucket/large_file.parquet')  # 500MB
    return df.to_dict()  # Serialized to XCom table → DB bloat!

@task
def transform(data: dict):
    df = pd.DataFrame(data)  # Deserialize 500MB from DB
    return df.to_dict()      # Store AGAIN in XCom!

# GOOD: Pass references, not data
@task
def extract(ds: str) -> str:
    df = pd.read_parquet('s3://bucket/large_file.parquet')
    output_path = f's3://pipeline-staging/{ds}/extracted.parquet'
    df.to_parquet(output_path)
    return output_path  # Only 50 bytes in XCom!

@task
def transform(input_path: str, ds: str) -> str:
    df = pd.read_parquet(input_path)  # Read from S3
    result = df.groupby('customer').sum()
    output_path = f's3://pipeline-staging/{ds}/transformed.parquet'
    result.to_parquet(output_path)
    return output_path

# Usage:
path = extract()
result = transform(path)
```

---

## Issue #48: depends_on_past Causing Pipeline Deadlock

**Symptoms:**
- DAG runs stuck: tasks in "none" state, never scheduled
- Manual clearing of one task doesn't unblock (still depends on yesterday)
- Entire pipeline stopped because one historical run failed
- Backfill impossible without clearing history

**Root Cause:**
- `depends_on_past=True` means task can only run if previous execution_date succeeded
- One failure creates infinite blockage (domino effect)
- Developers set it "for safety" without understanding implications
- Combining with `wait_for_downstream=True` makes it worse

**Fix:**
```python
# BAD: depends_on_past without escape hatch
task = PythonOperator(
    task_id='accumulate_metrics',
    depends_on_past=True,         # If yesterday fails, today NEVER runs
    python_callable=my_func,
)

# GOOD: Use depends_on_past ONLY when genuinely needed (cumulative logic)
# AND always provide a way to break the chain
task = PythonOperator(
    task_id='accumulate_metrics',
    depends_on_past=True,
    retries=5,                     # Give it chances to recover
    python_callable=my_func,
)

# To unblock after failure:
# Option 1: Mark the failed task as success
airflow tasks mark-success <dag_id> <task_id> <execution_date>

# Option 2: Clear the task (triggers re-run of that date)
airflow tasks clear <dag_id> -t <task_id> -s <start_date> -e <end_date>

# BETTER: Redesign to be independent (most pipelines don't need depends_on_past)
# If you need cumulative: read previous state from storage, not from Airflow dependency
```

---

## Issue #49: Sensor Blocking Worker Slots for Hours

**Symptoms:**
- 80% of worker slots occupied by sensors doing nothing
- Actual processing tasks queued for hours
- `pool.open_slots` = 0 even though no real work happening
- Worker CPU idle but no task throughput

**Root Cause:**
- Sensors using `mode='poke'` (default) occupy a worker slot while waiting
- S3KeySensor waiting 8 hours for a file, blocking one slot entire time
- 50 sensors × 1 slot = 50 workers doing nothing
- Sensor `poke_interval=60` means 99% idle time consuming 100% of a slot

**Fix:**
```python
# BAD: poke mode (occupies worker slot while sleeping)
wait_for_file = S3KeySensor(
    task_id='wait_for_data',
    bucket_name='raw-data',
    bucket_key='orders/{{ ds }}/data.parquet',
    mode='poke',                    # BLOCKS worker slot for hours!
    poke_interval=300,
    timeout=28800,                  # 8 hours of a worker slot wasted
)

# GOOD: reschedule mode (releases slot between checks)
wait_for_file = S3KeySensor(
    task_id='wait_for_data',
    bucket_name='raw-data',
    bucket_key='orders/{{ ds }}/data.parquet',
    mode='reschedule',              # Releases slot, re-queued later
    poke_interval=300,
    timeout=28800,
)

# BEST: Deferrable operator (truly async, no slot used)
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensorAsync

wait_for_file = S3KeySensorAsync(
    task_id='wait_for_data',
    bucket_name='raw-data',
    bucket_key='orders/{{ ds }}/data.parquet',
    poke_interval=300,
    # No worker slot used AT ALL - handled by Triggerer
)
```

**Impact Calculation:**
```
Before (poke mode):
  20 sensors × 8 hours avg wait = 160 worker-slot-hours/day wasted
  At $0.50/worker-slot-hour = $80/day = $2,400/month wasted

After (deferrable):
  0 worker slots used for sensors
  1 Triggerer handles ALL sensors (asyncio)
  Savings: $2,400/month + freed 20 slots for actual work
```

---

## Issue #50: Dynamic Task Mapping Producing Too Many Tasks

**Symptoms:**
- DAG creates 100,000+ mapped task instances
- UI crashes trying to render the DAG
- Scheduler takes minutes to process this single DAG
- Database overwhelmed with task instance records

**Root Cause:**
- `.expand()` over a very large list without batching
- Source data determines task count with no upper bound
- No guardrails on mapped task count

**Fix:**
```python
# BAD: Mapping over unbounded list
@task
def get_items():
    return list(range(100000))  # 100K tasks!

@task
def process_item(item):
    pass

items = get_items()
process_item.expand(item=items)  # 100K task instances → DB meltdown

# GOOD: Batch items to control parallelism
@task
def get_batches(batch_size: int = 1000):
    all_items = list(range(100000))
    return [all_items[i:i+batch_size] for i in range(0, len(all_items), batch_size)]
    # Returns 100 batches instead of 100K items

@task
def process_batch(batch: list):
    for item in batch:
        process_item(item)

batches = get_batches()
process_batch.expand(batch=batches)  # Only 100 mapped tasks!
```

```ini
# Global safety limit
[core]
max_map_length = 1024               # Maximum mapped task instances per operator
# Default: 1024. Set lower if needed.
```

---

## Issue #51: Circular Dependencies Not Detected Until Runtime

**Symptoms:**
- DAG file imports successfully but fails during execution
- Error: `Cycle detected in DAG`
- Only happens with dynamic DAG generation (loops creating edges)
- Hard to debug in complex DAGs with 200+ tasks

**Fix:**
```python
# Always validate DAG structure in tests
import pytest
from airflow.models import DagBag

def test_no_cycles():
    """Ensure no DAG has circular dependencies."""
    bag = DagBag(dag_folder='dags/', include_examples=False)
    for dag_id, dag in bag.dags.items():
        # This will raise if cycle exists
        assert dag.topological_sort(), f"Cycle detected in {dag_id}"

def test_all_dags_load():
    """All DAG files parse without error."""
    bag = DagBag(dag_folder='dags/', include_examples=False)
    assert len(bag.import_errors) == 0, f"Import errors: {bag.import_errors}"
```

---

## Issue #52: Trigger Rule Misunderstanding (all_success vs none_failed)

**Symptoms:**
- End-of-DAG notification task never fires after branches
- Tasks skipped when they should run
- Cleanup tasks don't execute after partial failures
- DAG shows "success" but critical tasks were skipped

**Root Cause:**
- Default `trigger_rule='all_success'` requires ALL upstream tasks to SUCCEED
- After branching, non-selected branch tasks are `skipped`
- `skipped` ≠ `success`, so downstream with `all_success` also gets skipped
- Developers expect "just run this at the end no matter what"

**Fix:**
```python
from airflow.utils.trigger_rule import TriggerRule

# After branching - use none_failed_min_one_success
join_task = EmptyOperator(
    task_id='join_after_branch',
    trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    # Runs if: no upstream FAILED + at least one SUCCEEDED
    # Skipped upstreams are OK!
)

# For cleanup that MUST always run:
cleanup = PythonOperator(
    task_id='cleanup_temp_files',
    trigger_rule=TriggerRule.ALL_DONE,      # Run regardless of upstream state
    python_callable=cleanup_function,
)

# For notification after partial success:
notify = PythonOperator(
    task_id='send_notification',
    trigger_rule=TriggerRule.NONE_FAILED,   # Run if nothing FAILED (skipped OK)
    python_callable=send_email,
)

# Trigger Rule reference:
# all_success        → all upstream SUCCEEDED (default)
# all_failed         → all upstream FAILED
# all_done           → all upstream completed (any state)
# one_success        → at least one upstream SUCCEEDED
# one_failed         → at least one upstream FAILED
# none_failed        → no upstream FAILED (skipped OK)
# none_skipped       → no upstream SKIPPED
# none_failed_min_one_success → none failed + at least one succeeded
# always             → always run (even if no upstream)
```

---

## Issue #53: Template Variables Not Rendering (Jinja Issues)

**Symptoms:**
- Task receives literal string `{{ ds }}` instead of date
- SQL query contains unrendered template placeholders
- Works in one operator but not another
- Parameters passed as strings not rendering

**Root Cause:**
- PythonOperator: templates render in `op_args`, `op_kwargs`, `templates_dict` only
- Python function body strings are NOT templates (just Python strings)
- Custom operator missing `template_fields` declaration
- `render_template_as_native_obj` not set (everything is string)

**Fix:**
```python
# BAD: Template in python_callable body (NOT rendered!)
def my_func():
    date = "{{ ds }}"  # This is just a literal string!
    query = f"SELECT * FROM table WHERE date = '{date}'"
    # Executes: SELECT * FROM table WHERE date = '{{ ds }}'  ← BROKEN

# GOOD: Pass via op_kwargs (templates ARE rendered here)
def my_func(date, **context):
    query = f"SELECT * FROM table WHERE date = '{date}'"
    # Executes: SELECT * FROM table WHERE date = '2024-06-01'

task = PythonOperator(
    task_id='my_task',
    python_callable=my_func,
    op_kwargs={'date': '{{ ds }}'},  # Rendered before calling function
)

# GOOD: Use context directly
def my_func(**context):
    date = context['ds']  # Already resolved
    date2 = context['data_interval_start'].strftime('%Y-%m-%d')

# GOOD: For native Python objects (not just strings)
with DAG('my_dag', render_template_as_native_obj=True):
    # {{ [1,2,3] }} renders as actual list, not string "[1, 2, 3]"
    pass
```

---

## Issue #54: SubDAG Deadlock (Legacy Pattern)

**Symptoms:**
- SubDAG tasks stuck in running state
- Parent DAG waiting for SubDAG, SubDAG waiting for pool slot
- Complete deadlock: neither can proceed
- All pool slots consumed

**Root Cause:**
- SubDAGs are DEPRECATED for good reason
- SubDAG uses its own executor/pool, competing with parent
- If parent holds last pool slot waiting for SubDAG, and SubDAG needs a slot = deadlock

**Fix:**
```python
# REMOVE ALL SubDAGs. Use TaskGroups instead.

# BAD (deprecated, causes deadlocks):
from airflow.operators.subdag import SubDagOperator  # DON'T USE!

# GOOD: TaskGroup (visual grouping, no separate executor)
from airflow.utils.task_group import TaskGroup

with DAG('main_pipeline') as dag:
    with TaskGroup('extract_group') as extract:
        task1 = PythonOperator(task_id='extract_orders', ...)
        task2 = PythonOperator(task_id='extract_customers', ...)
        task1 >> task2
    
    with TaskGroup('transform_group') as transform:
        task3 = PythonOperator(task_id='transform_data', ...)
    
    extract >> transform  # Clean dependency between groups
```

---

## Issue #55: DAG with 1000+ Tasks Takes Minutes to Render in UI

**Symptoms:**
- Opening DAG in Grid/Graph view times out
- Browser becomes unresponsive
- Webserver CPU spikes when users view large DAGs
- Multiple users viewing same DAG = webserver crash

**Fix:**
```python
# 1. Use TaskGroups to reduce visual complexity
with TaskGroup('region_processing', prefix_group_id=True) as region_group:
    for region in regions:  # 50 regions
        with TaskGroup(f'region_{region}') as sub_group:
            extract = PythonOperator(task_id='extract', ...)
            transform = PythonOperator(task_id='transform', ...)
            load = PythonOperator(task_id='load', ...)
            extract >> transform >> load
# UI shows collapsed groups instead of 150 individual tasks

# 2. Split into multiple DAGs connected by Datasets
# Instead of 1 DAG with 1000 tasks:
# DAG A (100 tasks) → produces Dataset → DAG B (100 tasks) → ...
```

---

## Issue #56: Catchup=True Overwhelming System After Extended Downtime

**Symptoms:**
- Airflow was down for 3 days, comes back up
- Scheduler immediately creates 72 DagRuns (24/day × 3 days) for hourly DAG
- Workers overwhelmed, everything queued
- Priority pipelines can't get slots

**Fix:**
```python
# Prevention: Always set max_active_runs
with DAG(
    'hourly_pipeline',
    schedule='@hourly',
    catchup=True,                  # Need historical backfill
    max_active_runs=3,             # Only 3 concurrent runs!
    max_active_tasks=16,           # Limit total concurrent tasks across runs
) as dag:
    pass
```

```ini
# Global safety net
[core]
max_active_runs_per_dag = 16           # Global maximum
max_active_tasks_per_dag = 32
```

---

## Issue #57: Task Fails But DAG Shows Success

**Symptoms:**
- DAG run marked "success" but individual task failed
- Alerting based on DAG state misses failures
- Downstream DAGs triggered thinking everything succeeded

**Root Cause:**
- Task has `trigger_rule=TriggerRule.ALL_DONE` or similar
- Task failure callback marks something else
- BranchOperator skips the failed path (task never ran)
- DAG-level success based on leaf task, which succeeded despite internal failure

**Fix:**
```python
# Monitor at TASK level, not just DAG level
default_args = {
    'on_failure_callback': task_failure_alert,  # Alert on ANY task failure
}

# Also set DAG-level callback
with DAG('my_dag', on_failure_callback=dag_failure_alert) as dag:
    pass

# For critical checks: explicit failure propagation
@task
def validate_results(ds: str):
    """Fail the DAG if validation doesn't pass."""
    if not data_quality_check(ds):
        raise AirflowFailException("Data quality check failed!")  # Marks task as FAILED, no retry
```

---

## Issue #58: Race Condition in Cross-DAG Dependencies (ExternalTaskSensor)

**Symptoms:**
- ExternalTaskSensor times out even though upstream DAG completed
- Sensor checks wrong execution_date
- Works on some days, fails on others
- Different schedules between DAGs cause mismatch

**Root Cause:**
- `execution_delta` calculated incorrectly
- Upstream and downstream DAGs have different schedules
- DST (Daylight Saving Time) shifts execution_dates
- Sensor defaults to `execution_date` but upstream uses `data_interval_end`

**Fix:**
```python
# BAD: Fragile execution_delta calculation
sensor = ExternalTaskSensor(
    task_id='wait_for_upstream',
    external_dag_id='upstream_dag',
    external_task_id='final_task',
    execution_delta=timedelta(hours=1),  # Breaks with schedule changes!
)

# GOOD: Use execution_date_fn for precise control
def get_upstream_execution_date(logical_date, **kwargs):
    """Map this DAG's logical_date to upstream's."""
    # If upstream runs daily at midnight and we run daily at 6 AM:
    return logical_date.replace(hour=0, minute=0, second=0)

sensor = ExternalTaskSensor(
    task_id='wait_for_upstream',
    external_dag_id='upstream_dag',
    external_task_id='final_task',
    execution_date_fn=get_upstream_execution_date,
    mode='reschedule',
    timeout=7200,
)

# BEST: Use Datasets (Airflow 2.4+) - no execution_date alignment needed
from airflow.datasets import Dataset
orders_dataset = Dataset('s3://bucket/orders/')

# Upstream produces:
@task(outlets=[orders_dataset])
def produce_orders():
    write_to_s3()

# Downstream consumes (triggered automatically when dataset updated):
with DAG('downstream', schedule=[orders_dataset]):
    pass
```

---

## Issue #59: Dynamic DAGs Duplicating DAG IDs

**Symptoms:**
- Error: `DagIdConflict: DAG with id 'X' already exists`
- DAGs disappearing and reappearing
- Wrong DAG running under a given ID
- Race condition between DAG file processors

**Root Cause:**
- Multiple DAG files generating DAGs with same ID pattern
- Dynamic generation not using deterministic IDs
- Copy-paste of DAG factory without changing ID prefix

**Fix:**
```python
# GOOD: Deterministic, unique DAG IDs
def create_tenant_dag(tenant_config: dict) -> DAG:
    """Factory with guaranteed unique IDs."""
    dag_id = f"tenant_{tenant_config['id']}_{tenant_config['pipeline']}"
    # ID is deterministic: same input always produces same ID
    
    with DAG(dag_id=dag_id, ...) as dag:
        pass
    return dag

# Each DAG file should create DAGs for a specific partition
# File: dags/tenants_a_m.py → tenants A through M
# File: dags/tenants_n_z.py → tenants N through Z
# Never overlap!
```

---

## Issue #60: Task Retry Storm Overwhelming External Systems

**Symptoms:**
- External API returns 429 (rate limited) 
- All retry attempts happen simultaneously across parallel tasks
- Retry causes more failures causing more retries (positive feedback loop)
- External system completely overwhelmed

**Fix:**
```python
# Use exponential backoff with jitter
default_args = {
    'retries': 5,
    'retry_delay': timedelta(minutes=2),
    'retry_exponential_backoff': True,      # Exponential: 2, 4, 8, 16, 32 min
    'max_retry_delay': timedelta(minutes=60),
}

# Combine with Pool to limit concurrent retries
task = PythonOperator(
    task_id='call_external_api',
    pool='external_api_pool',              # Max 3 concurrent calls
    pool_slots=1,
    retries=5,
    retry_delay=timedelta(minutes=5),
    retry_exponential_backoff=True,
    python_callable=call_api,
)
```

```python
# Custom retry logic with circuit breaker
from tenacity import retry, stop_after_attempt, wait_exponential, CircuitBreaker

breaker = CircuitBreaker(fail_max=5, reset_timeout=300)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
)
@breaker
def call_external_api():
    response = requests.get('https://api.external.com/data')
    response.raise_for_status()
    return response.json()
```

---

## Summary: DAG Design Issue Prevention Checklist

```
[ ] ALL tasks MUST be idempotent (DELETE+INSERT or MERGE/UPSERT)
[ ] XCom stores metadata only (paths, counts, flags) - never data
[ ] Never use depends_on_past unless genuinely needed for accumulation
[ ] All sensors use mode='reschedule' or deferrable operators
[ ] max_map_length set globally, batching for large dynamic tasks
[ ] No SubDAGs - use TaskGroups exclusively
[ ] Trigger rules explicitly set after branches (none_failed_min_one_success)
[ ] Template variables passed via op_kwargs, not in function body
[ ] Cross-DAG deps use Datasets (preferred) or execution_date_fn
[ ] retry_exponential_backoff=True for external system calls
[ ] max_active_runs set on every DAG
[ ] DAG structure validated in CI/CD (cycles, imports, naming)
[ ] TaskGroups for DAGs > 50 tasks
[ ] on_failure_callback set on both tasks and DAGs
[ ] catchup=False unless explicitly needed (and then set max_active_runs)
```
