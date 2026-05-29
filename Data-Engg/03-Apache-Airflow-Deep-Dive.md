# Apache Airflow - Staff Architect Deep Dive

## Table of Contents
1. [Architecture](#1-architecture)
2. [Executors](#2-executors)
3. [DAG Concepts](#3-dag-concepts)
4. [TaskFlow API](#4-taskflow-api)
5. [Scheduling Internals](#5-scheduling-internals)
6. [Dynamic DAGs](#6-dynamic-dags)
7. [Sensors and Deferrable Operators](#7-sensors-and-deferrable-operators)
8. [Data-Aware Scheduling](#8-data-aware-scheduling)
9. [Testing](#9-testing)
10. [Security](#10-security)
11. [Performance Tuning](#11-performance-tuning)
12. [Production Deployment](#12-production-deployment)
13. [Common Patterns](#13-common-patterns)
14. [Anti-Patterns](#14-anti-patterns)

---

## 1. Architecture

### Component Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       APACHE AIRFLOW                              │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │  Web Server  │   │  Scheduler   │   │  Triggerer   │         │
│  │  (Flask/     │   │              │   │  (Async I/O) │         │
│  │   Gunicorn)  │   │ DAG Parsing  │   │              │         │
│  │              │   │ Task Sched.  │   │ Deferrable   │         │
│  │ UI + REST API│   │ Executor Mgmt│   │ Operators    │         │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘         │
│         │                  │                   │                  │
│  ┌──────▼──────────────────▼───────────────────▼──────────┐      │
│  │                   Metadata Database                     │      │
│  │            (PostgreSQL / MySQL)                         │      │
│  │   DAG runs, Task instances, Variables, Connections,     │      │
│  │   XCom, Pools, SLA misses, Import errors               │      │
│  └────────────────────────┬───────────────────────────────┘      │
│                           │                                       │
│  ┌────────────────────────▼───────────────────────────────┐      │
│  │                     Executor                            │      │
│  │                                                         │      │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐ │      │
│  │  │ Local   │  │ Celery  │  │ K8s     │  │ Celery   │ │      │
│  │  │ Executor│  │ Executor│  │ Executor│  │ K8s Exec │ │      │
│  │  │         │  │         │  │         │  │ (Hybrid) │ │      │
│  │  │ Same    │  │ Celery  │  │ K8s Pod │  │          │ │      │
│  │  │ process │  │ Workers │  │ per task│  │          │ │      │
│  │  └─────────┘  └────┬────┘  └────┬────┘  └──────────┘ │      │
│  └─────────────────────┼───────────┼─────────────────────┘      │
│                        │           │                              │
│              ┌─────────▼─┐   ┌─────▼──────┐                     │
│              │  Worker 1  │   │  K8s Pod   │                     │
│              │  Worker 2  │   │  K8s Pod   │                     │
│              │  Worker N  │   │  K8s Pod   │                     │
│              └───────────┘   └────────────┘                     │
└──────────────────────────────────────────────────────────────────┘
```

### Scheduler Internals

```
Scheduler Loop (simplified):

while True:
    1. Parse DAG files (DagFileProcessor)
       - Scan DAG_FOLDER for .py files
       - Import and extract DAG objects
       - Serialize to DB (DagModel, DagCode)
    
    2. Create DagRuns
       - For each active DAG, check schedule
       - If next run time reached → create DagRun
       - Respect max_active_runs_per_dag
    
    3. Schedule TaskInstances
       - For each DagRun, check task dependencies
       - If all upstream tasks succeeded → mark SCHEDULED
       - Respect pools, priority_weight, queues
    
    4. Execute via Executor
       - Send SCHEDULED tasks to executor
       - Executor marks tasks as QUEUED → RUNNING
       - Monitor task heartbeats
    
    5. Process task results
       - Handle SUCCESS / FAILED / UP_FOR_RETRY
       - Trigger downstream tasks
       - Update DagRun state
    
    Sleep(min_file_process_interval)
```

### Task Instance Lifecycle

```
         ┌──────┐
         │ none │ (not yet created)
         └──┬───┘
            │ Scheduler creates TI
            ▼
       ┌─────────┐
       │scheduled │ (dependencies met)
       └────┬─────┘
            │ Executor picks up
            ▼
       ┌─────────┐
       │ queued   │ (waiting for worker)
       └────┬─────┘
            │ Worker starts execution
            ▼
       ┌─────────┐
       │ running  │ (executing on worker)
       └────┬─────┘
            │
      ┌─────┼──────┐
      ▼     ▼      ▼
┌────────┐ ┌────┐ ┌──────────────┐
│success │ │fail│ │up_for_retry  │──┐
└────────┘ └────┘ └──────────────┘  │
                         ▲           │
                         └───────────┘
                         (retry delay)

Other states: skipped, upstream_failed, up_for_reschedule,
              deferred, removed, restarting
```

---

## 2. Executors

### Executor Comparison

```
┌───────────────┬──────────────┬───────────────┬────────────────────┐
│               │ Local        │ Celery        │ Kubernetes         │
│               │ Executor     │ Executor      │ Executor           │
├───────────────┼──────────────┼───────────────┼────────────────────┤
│ Architecture  │ Subprocesses │ Celery workers│ K8s pods           │
│               │ on scheduler │ via broker    │ per task           │
│ Scalability   │ Single node  │ Multi-node    │ Multi-node + auto  │
│ Isolation     │ Low          │ Medium        │ High (pod per task)│
│ Startup time  │ Instant      │ Fast          │ Slow (pod spin-up) │
│ Dependencies  │ None extra   │ Redis/RabbitMQ│ Kubernetes cluster │
│ Resource mgmt │ OS level     │ Celery        │ K8s resource limits│
│ Best for      │ Dev/small    │ Medium-large  │ Heterogeneous tasks│
│               │              │ homogeneous   │ Multi-tenant       │
│ Fault         │ Scheduler    │ Worker failure│ Pod restart by K8s │
│ tolerance     │ dependency   │ → task retry  │ + task retry       │
└───────────────┴──────────────┴───────────────┴────────────────────┘
```

### CeleryExecutor Architecture

```
┌──────────────┐     ┌──────────────┐
│  Scheduler   │────▶│ Message Broker│
│              │     │ (Redis/      │
└──────────────┘     │  RabbitMQ)   │
                     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Worker 1 │  │ Worker 2 │  │ Worker N │
        │          │  │          │  │          │
        │ default  │  │ default  │  │ heavy    │
        │ queue    │  │ queue    │  │ queue    │
        │          │  │          │  │          │
        │ Concur:8 │  │ Concur:8 │  │ Concur:2 │
        └──────────┘  └──────────┘  └──────────┘
```

```python
# airflow.cfg for CeleryExecutor
[celery]
broker_url = redis://redis:6379/0
result_backend = db+postgresql://airflow:airflow@postgres/airflow
worker_concurrency = 16
worker_autoscale = 16,8  # max,min
default_queue = default

# Route tasks to specific queues
[operators]
default_queue = default
```

### KubernetesExecutor

```python
# airflow.cfg
[kubernetes_executor]
namespace = airflow
worker_container_repository = my-airflow
worker_container_tag = 2.7.0
delete_worker_pods = True
delete_worker_pods_on_failure = False
worker_pods_creation_batch_size = 16

# Per-task K8s configuration via executor_config
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

task = PythonOperator(
    task_id='heavy_computation',
    python_callable=my_func,
    executor_config={
        "pod_override": k8s.V1Pod(
            spec=k8s.V1PodSpec(
                containers=[
                    k8s.V1Container(
                        name="base",
                        resources=k8s.V1ResourceRequirements(
                            requests={"cpu": "2", "memory": "4Gi"},
                            limits={"cpu": "4", "memory": "8Gi",
                                    "nvidia.com/gpu": "1"}
                        ),
                    )
                ],
                node_selector={"node-type": "gpu"},
                tolerations=[
                    k8s.V1Toleration(
                        key="nvidia.com/gpu",
                        operator="Exists",
                        effect="NoSchedule"
                    )
                ]
            )
        )
    }
)
```

---

## 3. DAG Concepts

### Complete DAG Example

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.amazon.aws.operators.s3 import S3CopyObjectOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.utils.trigger_rule import TriggerRule

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email': ['alerts@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=60),
    'execution_timeout': timedelta(hours=2),
    'sla': timedelta(hours=4),
    'pool': 'default_pool',
}

with DAG(
    dag_id='etl_orders_pipeline',
    default_args=default_args,
    description='Daily ETL pipeline for order data',
    schedule='0 6 * * *',          # 6 AM daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=16,
    tags=['etl', 'orders', 'production'],
    doc_md="""## Orders ETL Pipeline
    Processes daily order data from S3 to warehouse.
    """,
    on_failure_callback=slack_alert,
    render_template_as_native_obj=True,
) as dag:
    
    wait_for_data = S3KeySensor(
        task_id='wait_for_data',
        bucket_name='raw-data',
        bucket_key='orders/{{ ds }}/orders.parquet',
        mode='reschedule',          # Don't block worker slot
        poke_interval=300,          # Check every 5 minutes
        timeout=3600,               # Timeout after 1 hour
    )
    
    extract = PythonOperator(
        task_id='extract',
        python_callable=extract_orders,
        op_kwargs={'date': '{{ ds }}'},
    )
    
    validate = PythonOperator(
        task_id='validate',
        python_callable=validate_data,
        op_kwargs={'date': '{{ ds }}'},
    )
    
    branch = BranchPythonOperator(
        task_id='check_quality',
        python_callable=lambda **ctx: 
            'transform' if ctx['ti'].xcom_pull(task_ids='validate') 
            else 'alert_bad_data',
    )
    
    transform = PythonOperator(
        task_id='transform',
        python_callable=transform_orders,
    )
    
    alert_bad_data = PythonOperator(
        task_id='alert_bad_data',
        python_callable=send_alert,
    )
    
    load = PythonOperator(
        task_id='load',
        python_callable=load_to_warehouse,
        pool='warehouse_pool',      # Limited concurrent warehouse writes
    )
    
    cleanup = PythonOperator(
        task_id='cleanup',
        python_callable=cleanup_temp_files,
        trigger_rule=TriggerRule.ALL_DONE,  # Run regardless of upstream
    )
    
    wait_for_data >> extract >> validate >> branch
    branch >> [transform, alert_bad_data]
    transform >> load >> cleanup
    alert_bad_data >> cleanup
```

### XCom (Cross-Communication)

```python
# Pushing XCom
def extract_data(**context):
    data = fetch_from_api()
    record_count = len(data)
    context['ti'].xcom_push(key='record_count', value=record_count)
    return data  # Return value auto-pushed as 'return_value'

# Pulling XCom
def validate_data(**context):
    data = context['ti'].xcom_pull(task_ids='extract', key='return_value')
    count = context['ti'].xcom_pull(task_ids='extract', key='record_count')
    
# Jinja template access
load = BashOperator(
    task_id='load',
    bash_command='echo "Records: {{ ti.xcom_pull(task_ids="extract", key="record_count") }}"'
)

# WARNING: XCom stored in metadata DB - avoid large data!
# Max practical size: ~48KB (Postgres) or ~64KB (MySQL)
# For large data: use S3/GCS paths as XCom values
```

### Connections and Hooks

```python
from airflow.hooks.base import BaseHook
from airflow.models import Connection

# Connection stored in metadata DB (encrypted with Fernet)
# Or via secrets backend (Vault, AWS SSM, etc.)

# Using Connection
conn = BaseHook.get_connection('my_postgres')
print(conn.host, conn.port, conn.schema, conn.login)

# Or via provider-specific Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
hook = PostgresHook(postgres_conn_id='my_postgres')
df = hook.get_pandas_df('SELECT * FROM orders LIMIT 100')
```

---

## 4. TaskFlow API

### TaskFlow with Dynamic Task Mapping

```python
from airflow.decorators import dag, task
from datetime import datetime

@dag(
    schedule='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
)
def etl_with_taskflow():
    
    @task
    def get_partitions(date: str) -> list[str]:
        """Return list of partitions to process"""
        return ['us-east', 'us-west', 'eu-west', 'ap-south']
    
    @task
    def extract(partition: str, date: str) -> dict:
        """Extract data for a single partition"""
        data = fetch_partition_data(partition, date)
        return {'partition': partition, 'records': len(data), 'path': data['path']}
    
    @task
    def transform(extracted: dict) -> dict:
        """Transform extracted data"""
        return process_data(extracted)
    
    @task
    def load(transformed: list[dict]):
        """Load all transformed data"""
        for item in transformed:
            write_to_warehouse(item)
    
    @task
    def notify(results: list[dict]):
        """Send notification with summary"""
        total = sum(r['records'] for r in results)
        send_slack(f"Processed {total} records across {len(results)} partitions")
    
    # Dynamic task mapping!
    date = '{{ ds }}'
    partitions = get_partitions(date=date)
    
    # .expand() creates one task instance per partition
    extracted = extract.expand(partition=partitions).partial(date=date)
    
    # .expand() propagates - one transform per extract
    transformed = transform.expand(extracted=extracted)
    
    # Aggregate results
    load(transformed=transformed)
    notify(results=transformed)

etl_with_taskflow()
```

### Task Groups

```python
from airflow.decorators import task_group

@dag(schedule='@daily', start_date=datetime(2024, 1, 1))
def pipeline_with_groups():
    
    @task_group(group_id='extract')
    def extract_group():
        @task
        def extract_orders():
            return fetch_orders()
        
        @task
        def extract_products():
            return fetch_products()
        
        @task
        def extract_customers():
            return fetch_customers()
        
        return {
            'orders': extract_orders(),
            'products': extract_products(),
            'customers': extract_customers()
        }
    
    @task_group(group_id='transform')
    def transform_group(data):
        @task
        def join_data(orders, products, customers):
            return merge_all(orders, products, customers)
        
        @task
        def calculate_metrics(joined):
            return compute_metrics(joined)
        
        joined = join_data(data['orders'], data['products'], data['customers'])
        return calculate_metrics(joined)
    
    @task
    def load(metrics):
        write_to_warehouse(metrics)
    
    raw_data = extract_group()
    metrics = transform_group(raw_data)
    load(metrics)
```

### Trigger Rules

```python
from airflow.utils.trigger_rule import TriggerRule

# ALL_SUCCESS (default): Run if all parents succeeded
# ALL_FAILED: Run if all parents failed
# ALL_DONE: Run regardless of parent status
# ONE_SUCCESS: Run if at least one parent succeeded
# ONE_FAILED: Run if at least one parent failed
# NONE_FAILED: Run if no parent failed (includes skipped)
# NONE_FAILED_MIN_ONE_SUCCESS: No failures, at least one success
# NONE_SKIPPED: Run if no parent was skipped
# ALWAYS: Always run

cleanup = PythonOperator(
    task_id='cleanup',
    python_callable=cleanup_fn,
    trigger_rule=TriggerRule.ALL_DONE,  # Always cleanup
)

alert = PythonOperator(
    task_id='alert_on_failure',
    python_callable=alert_fn,
    trigger_rule=TriggerRule.ONE_FAILED,  # Alert if ANY task failed
)
```

---

## 5. Scheduling Internals

### DAG Parsing

```
DAG Parsing Flow:

1. DagFileProcessorManager scans DAG_FOLDER
   - Finds all .py files
   - Tracks file modification times (skip unchanged)

2. DagFileProcessor (subprocess per file)
   - Imports the Python file
   - Collects DAG objects from module globals
   - Serializes DAGs to metadata DB
   
3. Scheduler reads serialized DAGs from DB
   - No direct file access during scheduling
   - Faster scheduling, decoupled from parsing

Key configs:
  min_file_process_interval: 30      # Seconds between re-parsing same file
  dag_dir_list_interval: 300         # Seconds between scanning for new files
  parsing_processes: 2               # Max parallel parsing processes
  dagbag_import_timeout: 30          # Timeout for importing a DAG file
```

### Concurrency Controls

```
Hierarchy of concurrency limits:

GLOBAL:
  parallelism = 32                   # Max task instances running globally

PER DAG:
  max_active_tasks_per_dag = 16      # Max running tasks in a single DAG
  max_active_runs_per_dag = 16       # Max active DagRuns per DAG

PER POOL:
  Pool('default_pool', slots=128)    # Max concurrent tasks using this pool
  Pool('warehouse_pool', slots=4)    # Limit warehouse writes

PER TASK:
  max_active_tis_per_dag = None      # Max running instances of this task
                                      # (across DagRuns)

PER DAGRUN:
  max_active_tasks = 16              # DAG-level param per DagRun

Resolution order:
  A task runs only if ALL limits allow:
  parallelism AND pool slots AND max_active_tasks AND ...
```

### Priority Weights

```python
# Tasks with higher priority_weight are scheduled first
task_critical = PythonOperator(
    task_id='critical_task',
    priority_weight=10,               # Higher = more important
    weight_rule='downstream',         # Sum of all downstream weights
)

# weight_rule options:
# 'downstream' (default): priority = sum of downstream task weights
# 'upstream': priority = sum of upstream task weights
# 'absolute': priority = this task's weight only
```

---

## 6. Dynamic DAGs

### DAG Factory Pattern

```python
# dags/dag_factory.py
import yaml
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def create_etl_dag(config):
    dag = DAG(
        dag_id=f"etl_{config['name']}",
        schedule=config['schedule'],
        start_date=datetime(2024, 1, 1),
        tags=config.get('tags', ['etl']),
        default_args={
            'retries': config.get('retries', 3),
            'retry_delay': timedelta(minutes=5),
        }
    )
    
    with dag:
        extract = PythonOperator(
            task_id='extract',
            python_callable=generic_extract,
            op_kwargs={
                'source': config['source'],
                'table': config['table'],
            }
        )
        
        load = PythonOperator(
            task_id='load',
            python_callable=generic_load,
            op_kwargs={
                'destination': config['destination'],
                'table': config['table'],
            }
        )
        
        extract >> load
    
    return dag

# Load configs and generate DAGs
with open('/opt/airflow/config/pipelines.yaml') as f:
    configs = yaml.safe_load(f)

for config in configs:
    globals()[f"etl_{config['name']}"] = create_etl_dag(config)
```

```yaml
# config/pipelines.yaml
- name: orders
  source: postgres_main
  table: orders
  destination: warehouse
  schedule: "0 6 * * *"
  tags: [etl, orders]

- name: products
  source: mysql_catalog
  table: products
  destination: warehouse
  schedule: "0 7 * * *"
  tags: [etl, catalog]
```

---

## 7. Sensors and Deferrable Operators

### Sensor Modes

```python
# POKE MODE: Occupies worker slot while waiting
sensor_poke = S3KeySensor(
    task_id='wait_poke',
    bucket_key='data/{{ ds }}/*.parquet',
    mode='poke',
    poke_interval=60,       # Check every 60s
    timeout=3600,           # Fail after 1 hour
    # Worker slot BLOCKED for entire duration!
)

# RESCHEDULE MODE: Releases worker slot between checks
sensor_reschedule = S3KeySensor(
    task_id='wait_reschedule',
    bucket_key='data/{{ ds }}/*.parquet',
    mode='reschedule',
    poke_interval=300,      # Check every 5 minutes
    timeout=7200,           # Fail after 2 hours
    # Worker slot FREE between pokes!
)
```

### Deferrable Operators

```python
from airflow.triggers.temporal import TimeDeltaTrigger
from airflow.sensors.base import BaseSensorOperator
from airflow.triggers.base import BaseTrigger, TriggerEvent
import asyncio
from typing import Any, AsyncIterator

# Custom Trigger (runs in Triggerer component)
class S3KeyExistsTrigger(BaseTrigger):
    def __init__(self, bucket_name, key, poll_interval=60):
        super().__init__()
        self.bucket_name = bucket_name
        self.key = key
        self.poll_interval = poll_interval
    
    def serialize(self):
        return (
            "mypackage.triggers.S3KeyExistsTrigger",
            {
                "bucket_name": self.bucket_name,
                "key": self.key,
                "poll_interval": self.poll_interval,
            }
        )
    
    async def run(self) -> AsyncIterator[TriggerEvent]:
        while True:
            # Async check (non-blocking)
            exists = await self._check_key_exists()
            if exists:
                yield TriggerEvent({"status": "success", "key": self.key})
                return
            await asyncio.sleep(self.poll_interval)
    
    async def _check_key_exists(self):
        # Use aiobotocore for async S3 access
        session = aiobotocore.get_session()
        async with session.create_client('s3') as client:
            try:
                await client.head_object(Bucket=self.bucket_name, Key=self.key)
                return True
            except client.exceptions.ClientError:
                return False

# Deferrable Sensor using the trigger
class DeferrableS3KeySensor(BaseSensorOperator):
    def __init__(self, bucket_name, key, **kwargs):
        super().__init__(**kwargs)
        self.bucket_name = bucket_name
        self.key = key
    
    def execute(self, context):
        # Initial check
        if self._check_key():
            return
        # Defer to triggerer (free up worker!)
        self.defer(
            trigger=S3KeyExistsTrigger(
                bucket_name=self.bucket_name,
                key=self.key,
                poll_interval=60
            ),
            method_name="execute_complete"
        )
    
    def execute_complete(self, context, event):
        if event["status"] == "success":
            self.log.info(f"Key found: {event['key']}")
        else:
            raise AirflowException(f"Key not found: {self.key}")
```

---

## 8. Data-Aware Scheduling

### Dataset-Driven DAGs

```python
from airflow.datasets import Dataset

# Define datasets
orders_dataset = Dataset("s3://warehouse/orders/")
products_dataset = Dataset("s3://warehouse/products/")

# Producer DAG - updates dataset on completion
@dag(schedule='@daily', start_date=datetime(2024, 1, 1))
def produce_orders():
    @task(outlets=[orders_dataset])  # Marks this task as dataset producer
    def process_orders():
        # Process and write to S3
        write_to_s3('s3://warehouse/orders/')

# Consumer DAG - triggered when datasets are updated
@dag(
    schedule=[orders_dataset, products_dataset],  # Triggered by BOTH datasets
    start_date=datetime(2024, 1, 1),
)
def consume_data():
    @task
    def aggregate():
        # Runs when BOTH orders AND products datasets are updated
        orders = read_s3('s3://warehouse/orders/')
        products = read_s3('s3://warehouse/products/')
        return join_and_aggregate(orders, products)
```

---

## 9. Testing

### DAG Validation Tests

```python
# tests/test_dags.py
import pytest
from airflow.models import DagBag

@pytest.fixture
def dagbag():
    return DagBag(dag_folder='dags/', include_examples=False)

def test_no_import_errors(dagbag):
    """Verify no import errors in any DAG"""
    assert len(dagbag.import_errors) == 0, \
        f"Import errors: {dagbag.import_errors}"

def test_dag_loaded(dagbag):
    """Verify specific DAGs are loaded"""
    assert 'etl_orders_pipeline' in dagbag.dags

def test_dag_structure(dagbag):
    """Verify DAG structure"""
    dag = dagbag.dags['etl_orders_pipeline']
    assert dag.schedule_interval == '0 6 * * *'
    assert len(dag.tasks) == 7
    assert dag.default_args['retries'] == 3

def test_no_cycles(dagbag):
    """Verify no circular dependencies"""
    for dag_id, dag in dagbag.dags.items():
        # This raises if there's a cycle
        dag.topological_sort()

def test_task_dependencies(dagbag):
    """Verify specific task dependencies"""
    dag = dagbag.dags['etl_orders_pipeline']
    extract = dag.get_task('extract')
    transform = dag.get_task('transform')
    assert 'extract' in [t.task_id for t in transform.upstream_list]
```

### Unit Testing Tasks

```python
# tests/test_tasks.py
from unittest.mock import patch, MagicMock
from airflow.models import TaskInstance, DagRun
from airflow.utils.state import DagRunState

def test_extract_task():
    """Test extract task logic"""
    with patch('mypackage.extract.fetch_from_api') as mock_fetch:
        mock_fetch.return_value = [{'id': 1}, {'id': 2}]
        result = extract_orders(date='2024-01-01')
        assert len(result) == 2
        mock_fetch.assert_called_once()

def test_dag_run():
    """Integration test with dag.test()"""
    from airflow.models import DagBag
    dagbag = DagBag()
    dag = dagbag.dags['etl_orders_pipeline']
    dag.test()  # Runs the DAG locally (Airflow 2.5+)
```

---

## 10. Security

### RBAC Model

```
Roles:
  Admin     → Full access
  Op        → Manage DAGs, connections, pools (no code access)
  User      → View and trigger DAGs
  Viewer    → Read-only access
  Public    → No access (disabled by default)

Custom roles:
  Team-specific DAG access via DAG-level permissions
```

### Secrets Backends

```python
# airflow.cfg
[secrets]
backend = airflow.providers.hashicorp.secrets.vault.VaultBackend
backend_kwargs = {
    "connections_path": "connections",
    "variables_path": "variables",
    "url": "https://vault.company.com",
    "auth_type": "kubernetes",
    "kubernetes_role": "airflow"
}

# AWS Systems Manager Parameter Store
backend = airflow.providers.amazon.aws.secrets.systems_manager.SystemsManagerParameterStoreBackend
backend_kwargs = {
    "connections_prefix": "/airflow/connections",
    "variables_prefix": "/airflow/variables",
    "profile_name": "default"
}
```

---

## 11. Performance Tuning

### Scheduler Performance

```ini
# airflow.cfg - Key scheduler tuning parameters

[scheduler]
min_file_process_interval = 30       # Don't re-parse files faster than this
dag_dir_list_interval = 300          # Scan for new files every 5 min
parsing_processes = 4                # Parallel DAG parsing subprocesses
file_parsing_sort_mode = modified_time  # Parse recently modified first
scheduler_idle_sleep_time = 1        # Sleep between scheduling loops
max_tis_per_query = 512              # Batch size for TI queries
schedule_after_task_execution = True  # Immediate scheduling after task done

[core]
parallelism = 64                     # Max running tasks
max_active_tasks_per_dag = 32        # Per DAG limit
max_active_runs_per_dag = 16         # Per DAG concurrent runs
dagbag_import_timeout = 60           # Import timeout per file
dag_file_processor_timeout = 120     # Parsing timeout per file
```

### Database Optimization

```sql
-- Critical indexes for Airflow metadata DB (PostgreSQL)
CREATE INDEX idx_ti_state ON task_instance(state);
CREATE INDEX idx_ti_dag_state ON task_instance(dag_id, state);
CREATE INDEX idx_dr_state ON dag_run(state);
CREATE INDEX idx_dr_dag_date ON dag_run(dag_id, execution_date);

-- Regular maintenance
VACUUM ANALYZE task_instance;
VACUUM ANALYZE dag_run;
VACUUM ANALYZE xcom;

-- Archive old data
DELETE FROM task_instance WHERE execution_date < NOW() - INTERVAL '90 days';
DELETE FROM dag_run WHERE execution_date < NOW() - INTERVAL '90 days';
DELETE FROM xcom WHERE execution_date < NOW() - INTERVAL '30 days';
DELETE FROM log WHERE dttm < NOW() - INTERVAL '30 days';
```

### Reducing DAG Parsing Time

```python
# BAD: Heavy imports at top level (runs every parse cycle)
import pandas as pd
import numpy as np
from heavy_lib import expensive_init

# GOOD: Lazy imports inside task functions
def my_task():
    import pandas as pd
    # Only imported when task actually executes

# BAD: Database queries during DAG parsing
with DAG(...) as dag:
    tables = fetch_table_list()  # Runs every 30 seconds!
    for t in tables:
        PythonOperator(task_id=t, ...)

# GOOD: Use Variables or config files
with DAG(...) as dag:
    tables = Variable.get('table_list', deserialize_json=True)
    for t in tables:
        PythonOperator(task_id=t, ...)
```

---

## 12. Production Deployment

### High Availability

```
┌──────────────────────────────────────────────────────────────┐
│                 HA Airflow Deployment                          │
│                                                               │
│  ┌────────────┐  ┌────────────┐                              │
│  │ Scheduler 1│  │ Scheduler 2│  (Active-Active since 2.0)   │
│  │  (Active)  │  │  (Active)  │  DB-level locking for        │
│  └─────┬──────┘  └─────┬──────┘  coordination                │
│        │                │                                     │
│  ┌─────▼────────────────▼─────┐                              │
│  │    PostgreSQL (Primary)     │                              │
│  │    + Read Replica           │                              │
│  │    + Connection Pooling     │                              │
│  │    (PgBouncer)              │                              │
│  └────────────────────────────┘                              │
│                                                               │
│  ┌────────────┐  ┌────────────┐                              │
│  │ Webserver 1│  │ Webserver 2│  Behind Load Balancer         │
│  └────────────┘  └────────────┘                              │
│                                                               │
│  ┌────────────┐  ┌────────────┐                              │
│  │ Triggerer 1│  │ Triggerer 2│  Multiple triggerer instances│
│  └────────────┘  └────────────┘                              │
│                                                               │
│  ┌────────────────────────────┐                              │
│  │ Redis Sentinel (HA Broker) │                              │
│  └────────────────────────────┘                              │
│                                                               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                       │
│  │Work 1│ │Work 2│ │Work 3│ │Work N│  Auto-scaled           │
│  └──────┘ └──────┘ └──────┘ └──────┘                       │
└──────────────────────────────────────────────────────────────┘
```

### Monitoring

```python
# StatsD metrics emitted by Airflow:
# dagrun.duration.success.<dag_id>
# dagrun.duration.failed.<dag_id>
# ti.finish.<dag_id>.<task_id>.<state>
# scheduler.tasks.running
# scheduler.tasks.starving
# pool.open_slots.<pool_name>
# pool.used_slots.<pool_name>
# dag_processing.total_parse_time

# Prometheus via StatsD-exporter or airflow-exporter
# Key alerts:
# - DAG run duration > SLA
# - Task failure rate > threshold
# - Scheduler heartbeat missing
# - Pool slots exhausted
# - DagBag import errors > 0
```

### Remote Logging

```ini
# airflow.cfg
[logging]
remote_logging = True
remote_log_conn_id = aws_default
remote_base_log_folder = s3://airflow-logs/
encrypt_s3_logs = True

# For GCS
remote_base_log_folder = gs://airflow-logs/
google_key_path = /secrets/gcp-key.json

# For Azure
remote_base_log_folder = wasb://airflow-logs@storageaccount.blob.core.windows.net/
```

---

## 13. Common Patterns

### Idempotent DAGs

```python
# Pattern: Partition overwrite (idempotent writes)
@task
def load_to_warehouse(date: str):
    """Idempotent load - overwrite partition for this date"""
    spark.sql(f"""
        INSERT OVERWRITE TABLE warehouse.orders
        PARTITION (dt = '{date}')
        SELECT * FROM staging.orders
        WHERE dt = '{date}'
    """)

# Pattern: Delete-then-insert
@task
def load_idempotent(date: str):
    hook = PostgresHook('warehouse')
    hook.run(f"DELETE FROM orders WHERE order_date = '{date}'")
    hook.run(f"""
        INSERT INTO orders 
        SELECT * FROM staging_orders 
        WHERE order_date = '{date}'
    """)

# Pattern: MERGE/UPSERT
@task
def upsert_data(date: str):
    spark.sql(f"""
        MERGE INTO warehouse.customers t
        USING staging.customers s ON t.customer_id = s.customer_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
```

### Cross-DAG Dependencies

```python
# Method 1: ExternalTaskSensor
from airflow.sensors.external_task import ExternalTaskSensor

wait_for_upstream = ExternalTaskSensor(
    task_id='wait_for_orders_etl',
    external_dag_id='etl_orders_pipeline',
    external_task_id='load',
    execution_delta=timedelta(hours=0),  # Same execution_date
    mode='reschedule',
    timeout=7200,
)

# Method 2: TriggerDagRunOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

trigger_downstream = TriggerDagRunOperator(
    task_id='trigger_analytics',
    trigger_dag_id='analytics_pipeline',
    conf={'source_date': '{{ ds }}'},
    wait_for_completion=True,
    poke_interval=60,
)

# Method 3: Datasets (Airflow 2.4+) - RECOMMENDED
# See Data-Aware Scheduling section above
```

---

## 14. Anti-Patterns

### 1. Heavy Processing in DAG Files

```python
# BAD: This runs every 30 seconds during parsing!
import pandas as pd
df = pd.read_csv('large_file.csv')
tables = df['table_name'].tolist()

# GOOD: Use Variables or defer to task execution
tables = Variable.get('table_list', deserialize_json=True, default_var=[])
```

### 2. XCom for Large Data

```python
# BAD: Storing large DataFrames in XCom (stored in metadata DB)
@task
def extract():
    return huge_dataframe.to_dict()  # Could be MBs!

# GOOD: Store data in object storage, pass reference
@task
def extract():
    path = 's3://bucket/temp/{{ ds }}/extracted.parquet'
    huge_dataframe.to_parquet(path)
    return path  # Only store the path in XCom

@task
def transform(path: str):
    df = pd.read_parquet(path)
```

### 3. Not Using Pools

```python
# BAD: All tasks hit the database simultaneously
# 50 tasks × 10 queries each = 500 concurrent connections!

# GOOD: Use pools to limit concurrency
# Admin UI → Pools → Create 'warehouse_pool' with 4 slots
load_task = PythonOperator(
    task_id='load',
    pool='warehouse_pool',  # Max 4 concurrent loads
)
```

### 4. Missing Idempotency

```python
# BAD: Appending data on retry → duplicates!
@task
def load(data):
    db.execute("INSERT INTO orders VALUES ...")

# GOOD: Idempotent write
@task
def load(data, date):
    db.execute(f"DELETE FROM orders WHERE date = '{date}'")
    db.execute(f"INSERT INTO orders SELECT ... WHERE date = '{date}'")
```

### 5. Hardcoded Connections

```python
# BAD
import psycopg2
conn = psycopg2.connect(host='prod-db', password='secret123')

# GOOD
hook = PostgresHook(postgres_conn_id='warehouse')
conn = hook.get_conn()
```

---

## Production Checklist

```
[ ] Use appropriate executor (Celery for medium, K8s for large/heterogeneous)
[ ] HA scheduler (multiple instances since 2.0)
[ ] PostgreSQL for metadata DB (not SQLite)
[ ] Connection pooling (PgBouncer) for metadata DB
[ ] Remote logging (S3/GCS) - don't rely on local disk
[ ] Secrets backend (Vault/SSM) - not metadata DB for sensitive connections
[ ] Monitoring: StatsD/Prometheus + alerting on key metrics
[ ] DAG testing in CI/CD (import errors, structure, unit tests)
[ ] Idempotent tasks (safe for retries)
[ ] Sensors in reschedule mode (or deferrable operators)
[ ] Pools for resource-limited sinks (databases, APIs)
[ ] Variables/config for dynamic DAG generation (not DB queries at parse time)
[ ] XCom for metadata only (paths, counts) - not large data
[ ] Catchup=False unless backfill is intended
[ ] SLA monitoring with callbacks
[ ] Regular metadata DB cleanup (old TIs, XComs, logs)
[ ] DAG-level access control with RBAC
```
