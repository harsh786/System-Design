# Interview Questions Set 4: Apache Airflow & Orchestration (Q91-120)

---

## Q91: Explain Airflow's architecture. What happens when you trigger a DAG run?

**Answer:**

```
┌──────────────────────────────────────────────────────────────┐
│                    AIRFLOW ARCHITECTURE                        │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │Scheduler │    │ Metadata │    │ Executor │               │
│  │          │    │ Database │    │          │               │
│  │ Parses   │───▶│(Postgres)│◀───│ CeleryEx/│               │
│  │ DAGs     │    │          │    │ K8sExec  │               │
│  │ Schedules│    │ Task     │    │          │               │
│  │ tasks    │    │ Instance │    │ Runs     │               │
│  │          │    │ state    │    │ tasks    │               │
│  └──────────┘    └──────────┘    └──────────┘               │
│       │                               │                      │
│       │          ┌──────────┐         │                      │
│       └─────────▶│  Webserver│◀────────┘                      │
│                  │  (UI)    │                                 │
│                  └──────────┘                                 │
└──────────────────────────────────────────────────────────────┘

DAG Trigger Flow:
1. Scheduler detects DAG is due (cron) or manually triggered
2. Creates DagRun record in metadata DB (state=running)
3. Scheduler evaluates task dependencies in DAG
4. Ready tasks (all upstream done) → TaskInstance created (state=queued)
5. Executor picks up queued tasks
6. Worker executes task, reports success/failure back to DB
7. Scheduler re-evaluates dependencies, queues next tasks
8. When all tasks done → DagRun state=success
```

---

## Q92: Compare Airflow Executors. When would you use each?

**Answer:**

| Executor | How it works | Scale | Use case |
|----------|-------------|-------|----------|
| SequentialExecutor | Single process, one task at a time | 1 task | Dev/testing only |
| LocalExecutor | Multiple processes on scheduler host | 1 machine (32 cores) | Small deployments |
| CeleryExecutor | Distributed workers via message queue (Redis/RabbitMQ) | 100s of workers | Production on VMs |
| KubernetesExecutor | Each task = new K8s pod | Unlimited (K8s) | Cloud-native, isolation |
| CeleryKubernetesExecutor | Celery + K8s for specific tasks | Hybrid | Mix of light + heavy tasks |

**KubernetesExecutor deep dive:**
```yaml
# Each task gets its own pod with specific resources
executor: KubernetesExecutor

# Task-level pod customization:
@task(executor_config={
    "pod_override": k8s.V1Pod(
        spec=k8s.V1PodSpec(
            containers=[k8s.V1Container(
                name="base",
                resources=k8s.V1ResourceRequirements(
                    requests={"memory": "2Gi", "cpu": "1"},
                    limits={"memory": "4Gi", "cpu": "2"}
                ),
                image="my-repo/spark-runner:v2.1"
            )]
        )
    )
})
def heavy_spark_task():
    ...
```

**Trade-offs:**
- CeleryExecutor: Fast task startup (~100ms), fixed workers → resource waste when idle
- KubernetesExecutor: Slow startup (~30-60s pod creation), perfect isolation, scale to zero

---

## Q93: How do you handle task dependencies and data dependencies in Airflow?

**Answer:**

**Task dependencies (execution order):**
```python
# Operator-based
task_a >> task_b >> task_c  # A then B then C
task_a >> [task_b, task_c]  # A then B and C in parallel
[task_b, task_c] >> task_d  # B and C both done before D

# Cross-DAG dependencies
from airflow.sensors.external_task import ExternalTaskSensor
wait_for_upstream = ExternalTaskSensor(
    task_id="wait_for_etl",
    external_dag_id="upstream_etl",
    external_task_id="final_task",
    execution_delta=timedelta(hours=1),  # Check 1h-earlier run
)
```

**Data dependencies (Airflow 2.4+ Datasets):**
```python
# Producer DAG
from airflow.datasets import Dataset

orders_dataset = Dataset("s3://lake/orders/")

@dag(schedule=None)
def produce_orders():
    @task(outlets=[orders_dataset])  # Declares this task produces this dataset
    def process_orders():
        write_to_s3("s3://lake/orders/")

# Consumer DAG (triggered when dataset is updated)
@dag(schedule=[orders_dataset])  # Triggered when orders_dataset is updated
def consume_orders():
    @task
    def analyze_orders():
        read_from_s3("s3://lake/orders/")
```

**XCom (cross-task communication):**
```python
@task
def extract():
    return {"count": 1000, "path": "s3://data/batch-123/"}

@task
def transform(data):
    # data automatically pulled from upstream XCom
    print(f"Processing {data['count']} records from {data['path']}")

# TaskFlow API: Return values automatically pushed/pulled via XCom
data = extract()
transform(data)
```

---

## Q94: How do you handle failures and retries in Airflow?

**Answer:**

```python
@task(
    retries=3,                          # Retry up to 3 times
    retry_delay=timedelta(minutes=5),   # Wait 5 min between retries
    retry_exponential_backoff=True,     # Exponential backoff
    max_retry_delay=timedelta(hours=1), # Cap at 1 hour
    execution_timeout=timedelta(hours=2), # Kill if runs > 2h
    on_failure_callback=alert_slack,    # Alert on final failure
    on_retry_callback=log_retry,        # Log each retry
)
def fragile_task():
    call_external_api()

# SLA monitoring
@dag(
    sla_miss_callback=notify_sla_breach,
)
def critical_pipeline():
    @task(sla=timedelta(hours=1))  # Must complete within 1h of scheduled time
    def must_be_fast():
        ...

# Trigger rules for downstream tasks
from airflow.utils.trigger_rule import TriggerRule

@task(trigger_rule=TriggerRule.ALL_DONE)  # Run even if upstream failed
def cleanup():
    # Always runs: cleanup temp files regardless of pipeline success
    ...

@task(trigger_rule=TriggerRule.ONE_SUCCESS)  # Run if ANY upstream succeeded
def send_report():
    ...

# Available trigger rules:
# ALL_SUCCESS (default), ALL_FAILED, ALL_DONE, ONE_SUCCESS, ONE_FAILED,
# NONE_FAILED, NONE_SKIPPED, ALWAYS
```

---

## Q95: Explain the difference between `schedule_interval`, `start_date`, and `execution_date` in Airflow.

**Answer:**

```
Timeline:
                    start_date     execution_date    actual run
                    2024-01-01     (logical date)    (when scheduler triggers)
                         │              │                  │
  ───────────────────────┼──────────────┼──────────────────┼───────
                         │              │                  │
  schedule: @daily       │   2024-01-01 │       runs at    │
                         │   (covers    │       2024-01-02 │
                         │    Jan 1)    │       00:00 UTC  │

KEY INSIGHT: 
  execution_date (now called "logical_date" in Airflow 2.2+) = 
    START of the data interval, NOT when the task actually runs

  For @daily schedule:
    logical_date = 2024-01-01
    data_interval_start = 2024-01-01 00:00
    data_interval_end = 2024-01-02 00:00
    actual trigger time = 2024-01-02 00:00 (end of interval!)

  WHY? Because you process Jan 1's data AFTER Jan 1 is complete.
```

**Common confusion:**
```python
# "Why does my daily DAG first run 1 day after start_date?"
# Because it processes the PREVIOUS day's data AT the end of the interval

@dag(
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,  # Don't backfill missed runs
)
def my_dag():
    @task
    def process_data(**context):
        # Use data_interval_start/end for data filtering
        start = context["data_interval_start"]  # 2024-01-01 00:00
        end = context["data_interval_end"]      # 2024-01-02 00:00
        
        # Query data for this interval
        query = f"SELECT * FROM orders WHERE created_at >= '{start}' AND created_at < '{end}'"
```

---

## Q96: How do you implement idempotent DAGs in Airflow?

**Answer:**

**Why idempotency matters:** Retries, backfills, and manual reruns should produce the SAME result.

```python
# IDEMPOTENT PATTERNS:

# 1. Partition-based overwrite (not append)
@task
def write_daily_data(**context):
    date = context["ds"]  # "2024-01-15"
    df = process_data(date)
    # OVERWRITE partition, not append
    df.write.mode("overwrite").partitionBy("date").save(f"s3://lake/orders/date={date}/")

# 2. MERGE/UPSERT instead of INSERT
@task
def upsert_to_warehouse(**context):
    sql = """
    MERGE INTO orders_dim AS target
    USING staging_orders AS source
    ON target.order_id = source.order_id
    WHEN MATCHED THEN UPDATE SET ...
    WHEN NOT MATCHED THEN INSERT ...
    """
    execute_sql(sql)

# 3. Delete-then-insert pattern
@task
def replace_daily_partition(**context):
    date = context["ds"]
    execute_sql(f"DELETE FROM fct_orders WHERE order_date = '{date}'")
    execute_sql(f"INSERT INTO fct_orders SELECT * FROM staging WHERE order_date = '{date}'")

# 4. Use deterministic file names (not timestamps)
@task
def export_report(**context):
    date = context["ds"]
    filename = f"s3://reports/daily/{date}/summary.parquet"  # Same name on rerun
    # Overwrite = idempotent
```

**Anti-patterns (NOT idempotent):**
```python
# BAD: Append mode → duplicates on rerun
df.write.mode("append").save("s3://lake/orders/")

# BAD: Timestamp in filename → new file on each run
filename = f"report_{datetime.now().isoformat()}.csv"

# BAD: INSERT without dedup → duplicates on retry
execute_sql("INSERT INTO orders SELECT * FROM staging")
```

---

## Q97: How do you test Airflow DAGs?

**Answer:**

```python
# 1. DAG validation test (catches import errors, cycles)
import pytest
from airflow.models import DagBag

def test_dag_integrity():
    dag_bag = DagBag(include_examples=False)
    assert len(dag_bag.import_errors) == 0, f"Import errors: {dag_bag.import_errors}"

def test_dag_has_no_cycles():
    dag_bag = DagBag(include_examples=False)
    for dag_id, dag in dag_bag.dags.items():
        # This will raise if cycle exists
        dag.test_cycle()

def test_dag_schedule():
    dag_bag = DagBag(include_examples=False)
    dag = dag_bag.get_dag("orders_pipeline")
    assert dag.schedule_interval == "@daily"
    assert dag.default_args["retries"] == 3

# 2. Task unit test
from airflow.decorators import task

@task
def transform_orders(raw_data):
    # Business logic
    return [r for r in raw_data if r["amount"] > 0]

def test_transform_orders():
    input_data = [
        {"order_id": "1", "amount": 100},
        {"order_id": "2", "amount": -5},  # Should be filtered
        {"order_id": "3", "amount": 50},
    ]
    result = transform_orders.function(input_data)  # Call underlying function
    assert len(result) == 2
    assert all(r["amount"] > 0 for r in result)

# 3. Integration test with test DAG run
from airflow.utils.state import DagRunState
from airflow.utils.types import DagRunType

def test_dag_run(dag_bag):
    dag = dag_bag.get_dag("orders_pipeline")
    dagrun = dag.create_dagrun(
        state=DagRunState.RUNNING,
        run_type=DagRunType.MANUAL,
        execution_date=datetime(2024, 1, 15),
    )
    # Execute tasks
    task_instance = dagrun.get_task_instance("extract_orders")
    task_instance.run()
    assert task_instance.state == "success"

# 4. DAG run via CLI (local testing)
# airflow dags test orders_pipeline 2024-01-15
# airflow tasks test orders_pipeline extract_orders 2024-01-15
```

---

## Q98: How do you implement dynamic DAG generation in Airflow?

**Answer:**

```python
# Pattern 1: Generate tasks dynamically from config
import yaml
from airflow.decorators import dag, task

config = yaml.safe_load(open("/opt/airflow/config/tables.yaml"))
# tables.yaml:
# tables:
#   - name: orders
#     source: postgres
#     schedule: "@hourly"
#   - name: customers  
#     source: mysql
#     schedule: "@daily"

@dag(schedule="@hourly", start_date=datetime(2024, 1, 1))
def dynamic_etl():
    for table in config["tables"]:
        @task(task_id=f"extract_{table['name']}")
        def extract(table_name, source):
            return read_from_source(source, table_name)
        
        @task(task_id=f"load_{table['name']}")
        def load(data, table_name):
            write_to_lake(data, table_name)
        
        data = extract(table["name"], table["source"])
        load(data, table["name"])

dynamic_etl()

# Pattern 2: Dynamic task mapping (Airflow 2.3+)
@dag(schedule="@daily")
def mapped_dag():
    @task
    def get_partitions():
        return ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
    
    @task
    def process_partition(partition_date: str):
        # This task runs ONCE PER partition (mapped dynamically)
        return process_data_for_date(partition_date)
    
    partitions = get_partitions()
    process_partition.expand(partition_date=partitions)  # Fan-out!

# Pattern 3: Generate multiple DAGs from factory
def create_dag(table_name, schedule):
    @dag(dag_id=f"etl_{table_name}", schedule=schedule, start_date=datetime(2024,1,1))
    def etl_dag():
        @task
        def extract():
            return read_table(table_name)
        @task
        def load(data):
            write_to_warehouse(data, table_name)
        load(extract())
    return etl_dag()

# Generate DAGs
for table in ["orders", "customers", "products"]:
    globals()[f"etl_{table}"] = create_dag(table, "@daily")
```

---

## Q99: How do you handle large-scale Airflow deployments (1000+ DAGs)?

**Answer:**

```
SCALING CHALLENGES:
1. Scheduler CPU: Parsing 1000+ DAG files every 30s
2. Database load: Millions of task instance records
3. Worker capacity: 10K+ concurrent tasks
4. UI performance: Rendering large DAGs

SOLUTIONS:

1. SCHEDULER OPTIMIZATION:
```
```python
# airflow.cfg
[scheduler]
min_file_process_interval = 60       # Don't re-parse DAGs every loop
dag_dir_list_interval = 300          # Scan for new DAG files every 5 min
parsing_processes = 4                # Parallel DAG parsing
scheduler_heartbeat_sec = 5
max_dagruns_to_create_per_loop = 10  # Limit concurrent DagRun creation

# Use .airflowignore to skip non-DAG files
# Place DAGs in subdirectories
```

```
2. DATABASE OPTIMIZATION:
   - Use PgBouncer for connection pooling
   - Archive old DagRun/TaskInstance records (keep 30 days)
   - Use read replicas for webserver queries
   - Index optimization for common queries

3. MULTI-SCHEDULER (Airflow 2.0+):
   - Run multiple scheduler instances (HA)
   - Database-level locking ensures no double-scheduling
   - Scale horizontally with more scheduler pods

4. DAG SERIALIZATION:
   - Enable dag_serialization (parse once, store in DB)
   - Webserver reads from DB (doesn't need DAG files)
   - Reduces file system pressure

5. WORKER SCALING:
   - KubernetesExecutor: Pods auto-scale with cluster autoscaler
   - CeleryExecutor: KEDA-based worker scaling on queue depth
   - Task-level resource allocation (heavy vs light tasks)

6. DAG ORGANIZATION:
   - Group related DAGs in subdirectories
   - Use DAG tags for filtering in UI
   - Limit task count per DAG (< 500)
   - Use SubDAGs or TaskGroups for organization
```

---

## Q100: Compare Airflow vs Dagster vs Prefect. When would you choose each?

**Answer:**

| Aspect | Airflow | Dagster | Prefect |
|--------|---------|---------|---------|
| Model | DAG of operators | Software-defined assets | Flow of tasks |
| Core concept | Task dependencies | Data assets + lineage | Pythonic workflows |
| Schedule | Cron-based | Cron + sensors + freshness | Cron + event-based |
| Testing | Harder (global context) | First-class (asset tests) | Easy (pure Python) |
| Data lineage | Add-on (datasets) | Core feature (assets) | Limited |
| Type checking | None | IO Managers + types | Pydantic support |
| Local dev | `airflow standalone` | `dagster dev` | `prefect server` |
| UI | Functional (DAG view) | Asset-centric + lineage | Modern, flow-centric |
| Deployment | Complex (many components) | Simpler (code locations) | Simplest (agent) |
| Maturity | Very mature (2014) | Growing fast (2019) | Mature v2 (2022) |
| Community | Largest | Growing | Medium |
| Cloud offering | MWAA, Astronomer, Composer | Dagster Cloud | Prefect Cloud |

**Choose Airflow when:**
- Large existing investment in Airflow
- Need massive ecosystem of operators/providers
- Team knows Airflow well
- Complex cross-system orchestration

**Choose Dagster when:**
- Data-centric (thinking in assets, not tasks)
- Want built-in lineage and data quality
- Software engineering best practices (testing, typing)
- Starting fresh with modern stack

**Choose Prefect when:**
- Simple, Pythonic workflows
- Minimal infrastructure overhead
- Hybrid execution (local + cloud)
- Rapid iteration on pipelines

---

## Q101: How do you implement data-aware scheduling in Airflow?

**Answer:**

```python
# Airflow 2.4+ Datasets (data-aware scheduling)

from airflow.datasets import Dataset

# Define datasets
raw_orders = Dataset("s3://raw/orders/")
clean_orders = Dataset("s3://lake/orders_clean/")
daily_revenue = Dataset("s3://warehouse/daily_revenue/")

# PRODUCER: Ingestion DAG
@dag(schedule="@hourly")
def ingest_orders():
    @task(outlets=[raw_orders])  # Declares output dataset
    def extract_from_source():
        data = read_from_postgres()
        write_to_s3("s3://raw/orders/", data)

# CONSUMER 1: Triggered when raw_orders is updated
@dag(schedule=[raw_orders])  # Triggered by dataset update
def clean_orders_dag():
    @task(outlets=[clean_orders])
    def clean_and_validate():
        raw = read_s3("s3://raw/orders/")
        cleaned = clean(raw)
        write_to_s3("s3://lake/orders_clean/", cleaned)

# CONSUMER 2: Triggered when BOTH datasets are updated
@dag(schedule=[clean_orders, Dataset("s3://lake/customers/")])
def build_revenue():
    @task(outlets=[daily_revenue])
    def aggregate_revenue():
        orders = read_s3("s3://lake/orders_clean/")
        revenue = orders.groupby("date").sum("amount")
        write_to_s3("s3://warehouse/daily_revenue/", revenue)
```

---

## Q102: How do you implement deferrable operators for efficiency?

**Answer:**

```python
# Traditional sensor: Occupies a worker slot while waiting (wasteful!)
# Deferrable operator: Frees worker slot, async trigger wakes it up

from airflow.sensors.base import BaseSensorOperator
from airflow.triggers.temporal import TimeDeltaTrigger
from airflow.triggers.base import BaseTrigger, TriggerEvent
import asyncio

# Custom deferrable sensor
class S3KeySensorAsync(BaseSensorOperator):
    def execute(self, context):
        # Check immediately
        if self._check_key_exists():
            return  # Done!
        
        # Defer: Free this worker, trigger will wake me up
        self.defer(
            trigger=S3KeyTrigger(
                bucket="my-bucket",
                key="data/ready_flag",
                poll_interval=60,
            ),
            method_name="execute_complete",
        )
    
    def execute_complete(self, context, event=None):
        # Called when trigger fires
        if event["status"] == "success":
            return  # File found!
        raise AirflowException(f"Trigger failed: {event}")

# Custom trigger (runs in triggerer process, async)
class S3KeyTrigger(BaseTrigger):
    def __init__(self, bucket, key, poll_interval):
        self.bucket = bucket
        self.key = key
        self.poll_interval = poll_interval
    
    def serialize(self):
        return ("my_module.S3KeyTrigger", {
            "bucket": self.bucket,
            "key": self.key,
            "poll_interval": self.poll_interval,
        })
    
    async def run(self):
        while True:
            if await self._check_s3_key():
                yield TriggerEvent({"status": "success", "key": self.key})
                return
            await asyncio.sleep(self.poll_interval)

# Benefits:
# - 1000 waiting sensors = 0 worker slots used (all deferred)
# - Single triggerer process handles all async polling
# - Workers free for actual computation
```

---

## Q103-120: [Additional Airflow & Orchestration Questions - Condensed]

**Q103:** How do you implement CI/CD for Airflow DAGs?
- Git-based DAG deployment (PR → test → merge → sync to DAGs folder)
- DAG integrity tests in CI (import, cycle check, task count)
- Staging environment with production-like data subset

**Q104:** How do you handle secrets in Airflow?
- Secrets backend: AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager
- `connections` and `variables` stored in secrets backend, not DB
- Environment variables for config, secrets backend for credentials

**Q105:** Explain TaskGroups vs SubDAGs.
- SubDAGs (deprecated): Separate DAG, separate scheduler, deadlock-prone
- TaskGroups: Visual grouping only, same DAG, no overhead, recommended

**Q106:** How do you handle backfilling?
- `airflow dags backfill -s 2024-01-01 -e 2024-01-31 my_dag`
- Requires idempotent tasks (rerunning must be safe)
- Use `catchup=True` for automatic backfill on DAG creation

**Q107:** How do you implement conditional branching?
```python
@task.branch
def decide_path(**context):
    if context["ds_nodash"] == "20240101":
        return "new_year_special"
    return "normal_processing"
```

**Q108:** How do you handle time zones in Airflow?
- Internal: Always UTC
- `start_date` and `schedule` in UTC
- Use `pendulum` for timezone-aware datetimes in task logic

**Q109:** What is the Airflow Timetable API?
- Custom scheduling logic (business days, market hours, irregular schedules)
- Replaces simple cron expressions for complex schedules

**Q110:** How do you implement alerting for DAG failures?
```python
def slack_alert(context):
    msg = f"Task {context['task_instance'].task_id} failed in {context['dag'].dag_id}"
    send_slack(msg)

default_args = {"on_failure_callback": slack_alert}
```

**Q111:** How do you handle resource contention between DAGs?
- Pools: Limit concurrent tasks accessing same resource (`Pool("db_pool", 5)`)
- Priority weights: Higher priority tasks scheduled first
- Concurrency limits: `max_active_runs_per_dag`, `max_active_tasks_per_dag`

**Q112:** Explain Airflow's XCom limitations and alternatives.
- XCom stored in metadata DB (default max 48KB in MySQL)
- For large data: Store in S3, pass path via XCom
- Custom XCom backend for large payloads (S3XComBackend)

**Q113:** How do you implement data lineage tracking with Airflow?
- OpenLineage integration (captures lineage metadata per task)
- Datasets API (explicit input/output declarations)
- Marquez or DataHub integration for lineage visualization

**Q114:** How do you debug a slow DAG?
- Check scheduler logs: Is DAG parsing slow? (parse time > 30s)
- Check task duration: Which tasks are bottleneck?
- Check pool/slot availability: Tasks queued but not running?
- Check database: Slow queries from large XCom/metadata?

**Q115:** How do you migrate from Airflow 1.x to 2.x?
- TaskFlow API migration (PythonOperator → @task decorator)
- DAG serialization requirement
- Provider packages (separate from core)
- Executor config changes (K8s executor pod spec)

**Q116:** How do you handle DAG versioning?
- Git tags for DAG releases
- DAG version attribute for tracking
- Blue/green deployment for zero-downtime updates
- Keep backward compatibility for running DagRuns

**Q117:** What are Airflow Datasets limitations?
- No partition-level granularity (whole dataset or nothing)
- No conditional scheduling on dataset content
- Cross-DAG only (not within same DAG)
- No external event integration (only Airflow producers)

**Q118:** How do you implement cost management for Airflow on cloud?
- KubernetesExecutor: Right-size pods per task, spot instances for workers
- Auto-scaling: Scale workers down during off-hours
- Task-level resource tagging for cost attribution
- Shared infrastructure with namespace isolation

**Q119:** How do you handle exactly-once processing in Airflow?
- Airflow does NOT guarantee exactly-once execution (at-least-once with retries)
- Make tasks idempotent (MERGE, overwrite partitions, dedup on write)
- Use external checkpointing for long-running tasks

**Q120:** Design a production Airflow deployment for 500 DAGs, 10K tasks/day.
```
Architecture:
- 3 schedulers (HA, database-level locking)
- KubernetesExecutor (auto-scaling pods)
- PostgreSQL 14 (RDS Multi-AZ) + PgBouncer
- Redis (trigger queue for CeleryKubernetesExecutor)
- S3 for logs (remote logging)
- GitSync sidecar for DAG deployment
- Prometheus + Grafana for monitoring
- Namespace isolation per team
```
