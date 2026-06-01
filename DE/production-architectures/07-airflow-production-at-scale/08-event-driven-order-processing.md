# Problem 8: Event-Driven Order Processing (E-Commerce Scale)

## The Problem

An e-commerce platform processes **1M+ orders/hour** during normal operations, spiking to **3M/hour on Black Friday**. The legacy system used time-based scheduling (cron every minute), which created two critical issues:

1. **Wasted resources**: Workers polling for files that don't exist yet, burning 40% of capacity on waiting
2. **Latency**: Even with 1-minute cron, batches sit idle for up to 59 seconds before processing begins
3. **Burst blindness**: During peak, hundreds of batches arrive simultaneously but workers are stuck in sensor loops
4. **Seller partitioning**: 500+ sellers upload at irregular intervals (30s to 5min gaps)
5. **Cost**: Worker slots cost real money - each slot occupied by a waiting sensor is a slot not processing orders

The goal: trigger processing **immediately** when a batch arrives, using near-zero resources while waiting.

## Scale Numbers

| Metric | Normal | Peak (Black Friday) |
|--------|--------|-------------------|
| Orders/hour | 1M | 3M |
| Batch arrival interval | 30s - 5min | 5s - 30s |
| Processing time per batch | 2-10 min | 2-10 min |
| Seller partitions | 500+ | 500+ |
| Worker pool | 200 slots | 200 slots |
| Sensor waste (traditional) | 40% capacity | 80%+ capacity (collapse) |
| With deferrable operators | ~2% capacity | ~5% capacity |

## Architecture Diagram (ASCII)

```
                    ┌─────────────────────────────────────────────────┐
                    │              EVENT-DRIVEN FLOW                   │
                    └─────────────────────────────────────────────────┘

  Sellers upload        S3 Event          Airflow               Workers
  ─────────────     ─────────────     ─────────────         ─────────────
                                                            
  [Seller A] ──┐    ┌───────────┐    ┌─────────────┐      ┌───────────┐
  [Seller B] ──┼──► │  S3 Put   │───►│  Triggerer  │─────►│  Worker   │
  [Seller C] ──┘    │  Events   │    │  (asyncio)  │      │  Pool     │
                    └───────────┘    │             │      │  200 slots│
                                     │  Watches    │      │           │
                    ┌───────────┐    │  1000s of   │      │  Process  │
                    │  SQS /    │───►│  triggers   │      │  orders   │
                    │  SNS      │    │  with 1     │      │  only     │
                    └───────────┘    │  thread     │      └───────────┘
                                     └─────────────┘
                                           │
                                     ┌─────┴─────┐
                                     │ Scheduler │
                                     │ resumes   │
                                     │ task when │
                                     │ triggered │
                                     └───────────┘

  TRADITIONAL (BAD):                 DEFERRABLE (GOOD):
  ┌────────────────┐                 ┌────────────────┐
  │ Worker Slot 1  │ ← WAITING      │ Triggerer      │ ← watches all
  │ Worker Slot 2  │ ← WAITING      │ (1 process)    │
  │ Worker Slot 3  │ ← WAITING      │                │
  │ ...            │                 │ Worker slots   │ ← FREE for
  │ Worker Slot 80 │ ← WAITING      │ all available  │   real work
  │ Worker Slot 81 │ ← PROCESSING   └────────────────┘
  └────────────────┘
  80/200 slots wasted = 40%          0/200 slots wasted
```

## Airflow Concepts Taught

### 1. Deferrable Operators (Game-Changer)

#### The Problem with Traditional Sensors

Traditional sensors occupy a **full worker slot** while waiting. In `mode='poke'`, a sensor runs in a loop:

```python
# BAD: Traditional S3 sensor - occupies a worker slot the entire time
from airflow.sensors.s3_key_sensor import S3KeySensor

# This task takes 1 worker slot and holds it for potentially HOURS
wait_for_batch = S3KeySensor(
    task_id='wait_for_seller_batch',
    bucket_name='orders-incoming',
    bucket_key='seller_123/{{ ds }}/batch_*.parquet',
    poke_interval=30,       # Check every 30 seconds
    timeout=3600,           # Wait up to 1 hour
    mode='poke',            # HOLDS the worker slot
)
# Result: 1 worker slot burned for 1 hour doing NOTHING
# With 500 sellers: 500 slots needed just for waiting = impossible with 200 slots
```

#### How Deferrable Operators Work

The deferrable pattern has three phases:

1. **Execute**: Task starts on a worker, sets up the trigger, then **releases the worker slot**
2. **Defer**: Task is suspended. The Triggerer watches for the event using asyncio (no worker needed)
3. **Resume**: When the event fires, the task is rescheduled on a worker to complete

```python
# GOOD: Deferrable sensor - uses NO worker slot while waiting
from airflow.sensors.base import BaseSensorOperator
from airflow.triggers.base import BaseTrigger, TriggerEvent
from airflow.utils.context import Context
import asyncio
from typing import Any, AsyncIterator
from datetime import timedelta


class S3BatchTrigger(BaseTrigger):
    """
    Async trigger that watches S3 for new order batches.
    Runs inside the Triggerer process (asyncio event loop).
    Uses ZERO worker slots.
    """

    def __init__(self, bucket: str, prefix: str, aws_conn_id: str = 'aws_default'):
        super().__init__()
        self.bucket = bucket
        self.prefix = prefix
        self.aws_conn_id = aws_conn_id

    def serialize(self) -> tuple[str, dict[str, Any]]:
        """Serialize trigger for storage in metadata DB (survives restarts)."""
        return (
            "dags.triggers.s3_batch_trigger.S3BatchTrigger",
            {
                "bucket": self.bucket,
                "prefix": self.prefix,
                "aws_conn_id": self.aws_conn_id,
            },
        )

    async def run(self) -> AsyncIterator[TriggerEvent]:
        """
        Main async loop - runs in the Triggerer's asyncio event loop.
        Yields a TriggerEvent when the condition is met.
        """
        import aiobotocore.session

        session = aiobotocore.session.get_session()
        async with session.create_client('s3') as client:
            while True:
                response = await client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=self.prefix,
                    MaxKeys=1,
                )
                if response.get('KeyCount', 0) > 0:
                    # Found files! Fire the trigger event
                    files = [obj['Key'] for obj in response['Contents']]
                    yield TriggerEvent({"status": "success", "files": files})
                    return  # Trigger is done

                # No files yet - sleep and retry (non-blocking async sleep)
                await asyncio.sleep(10)


class DeferrableS3BatchSensor(BaseSensorOperator):
    """
    Sensor that defers to the Triggerer instead of occupying a worker slot.
    
    Flow:
    1. execute() runs on a worker for ~100ms
    2. Calls self.defer() - releases the worker slot immediately
    3. Triggerer watches S3 asynchronously
    4. When file appears, execute_complete() runs on a worker for ~100ms
    
    Total worker time: ~200ms instead of potentially hours.
    """

    def __init__(self, bucket: str, prefix: str, aws_conn_id: str = 'aws_default', **kwargs):
        super().__init__(**kwargs)
        self.bucket = bucket
        self.prefix = prefix
        self.aws_conn_id = aws_conn_id

    def execute(self, context: Context):
        """
        Called first on a worker. Immediately defers to Triggerer.
        Worker slot is released after this returns.
        """
        # Quick check - maybe the file is already there
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook
        hook = S3Hook(aws_conn_id=self.aws_conn_id)
        keys = hook.list_keys(bucket_name=self.bucket, prefix=self.prefix, max_items=1)
        
        if keys:
            # Already there, no need to defer
            return {"files": keys}

        # Not there yet - defer to Triggerer (releases worker slot)
        self.defer(
            trigger=S3BatchTrigger(
                bucket=self.bucket,
                prefix=self.prefix,
                aws_conn_id=self.aws_conn_id,
            ),
            method_name="execute_complete",
            timeout=timedelta(hours=2),
        )

    def execute_complete(self, context: Context, event: dict[str, Any]):
        """
        Called when the Trigger fires. Runs on a worker again (briefly).
        """
        if event["status"] != "success":
            raise Exception(f"Trigger failed: {event}")
        self.log.info(f"Batch arrived: {event['files']}")
        return event["files"]
```

#### Resource Savings

```
Traditional (500 sellers, mode='poke'):
  - Worker slots used for waiting: 500
  - Worker slots available: 200
  - Result: IMPOSSIBLE - queue backs up, processing stops

Traditional (500 sellers, mode='reschedule'):
  - Worker slots used per check cycle: 500 (briefly)
  - Scheduler load: 500 reschedules every 30s = 1000/min
  - Result: Works but heavy scheduler pressure

Deferrable (500 sellers):
  - Worker slots used for waiting: 0
  - Triggerer async tasks: 500 (single process handles all)
  - Worker slots 100% available for processing
  - Result: Full capacity for actual work
```

### 2. Triggerer Component

The Triggerer is a separate Airflow component (like scheduler, webserver, worker):

```
┌──────────────────────────────────────────────────┐
│                 TRIGGERER PROCESS                  │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │          asyncio Event Loop                   │ │
│  │                                               │ │
│  │  [Trigger 1] ─── watching S3 seller_001      │ │
│  │  [Trigger 2] ─── watching S3 seller_002      │ │
│  │  [Trigger 3] ─── watching SQS queue          │ │
│  │  [Trigger 4] ─── watching S3 seller_003      │ │
│  │  ...                                          │ │
│  │  [Trigger 2000] ─── watching HTTP endpoint   │ │
│  │                                               │ │
│  │  All running concurrently in ONE process      │ │
│  │  using cooperative multitasking (async/await) │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  Memory: ~500MB for 2000 triggers                 │
│  CPU: minimal (mostly waiting on I/O)             │
└──────────────────────────────────────────────────┘
```

**Configuration (airflow.cfg):**

```ini
[triggerer]
# Number of triggers a single Triggerer can run concurrently
default_capacity = 1000

# How often to check for new triggers to pick up
job_heartbeat_sec = 5

# HA: run multiple triggerer instances
# They coordinate via the metadata DB (no leader election needed)
```

**Scaling Triggerers:**

```bash
# Run multiple triggerer instances for HA and capacity
# Each picks up triggers from the DB automatically
airflow triggerer --capacity 1000  # Instance 1
airflow triggerer --capacity 1000  # Instance 2

# Total capacity: 2000 concurrent deferred tasks
# For our 500-seller case: 1 triggerer is plenty
```

### 3. mode='poke' vs mode='reschedule' vs Deferrable

```python
# ============================================
# COMPARISON: Three approaches to waiting
# ============================================

# --- mode='poke' (WORST for production) ---
# Worker slot: OCCUPIED entire time
# Memory: Worker process running
# Scheduler: No extra load
# Use when: Dev/testing only, or wait < 30 seconds
sensor_poke = S3KeySensor(
    task_id='wait_poke',
    bucket_name='orders',
    bucket_key='batch_*.parquet',
    poke_interval=30,
    mode='poke',  # Blocks worker slot
)

# --- mode='reschedule' (ACCEPTABLE) ---
# Worker slot: Used briefly each check, then released
# Memory: Worker freed between checks
# Scheduler: Extra load (reschedule events)
# Use when: Deferrable not available, moderate concurrency
sensor_reschedule = S3KeySensor(
    task_id='wait_reschedule',
    bucket_name='orders',
    bucket_key='batch_*.parquet',
    poke_interval=60,         # Check every 60s
    mode='reschedule',        # Releases slot between checks
)

# --- Deferrable (BEST) ---
# Worker slot: Used only for start + finish (~200ms total)
# Memory: Only async coroutine in Triggerer
# Scheduler: Minimal load
# Use when: Always in production (if operator supports it)
sensor_deferrable = S3KeySensorAsync(
    task_id='wait_deferrable',
    bucket_name='orders',
    bucket_key='batch_*.parquet',
    deferrable=True,          # Use deferrable mode
)
```

**Migration path:**

```python
# Step 1: You have this (BAD)
S3KeySensor(mode='poke', poke_interval=30)

# Step 2: Quick win - switch to reschedule
S3KeySensor(mode='reschedule', poke_interval=60)
# Savings: slots freed between checks

# Step 3: Best - switch to deferrable (requires Triggerer running)
S3KeySensor(deferrable=True)
# Savings: zero worker slots used while waiting
# Note: Airflow 2.6+ has deferrable=True param on many built-in sensors
```

### 4. Event-Driven DAGs (Beyond Cron)

#### Dataset-Triggered DAGs

```python
from airflow.datasets import Dataset
from airflow.decorators import dag, task
from datetime import datetime

# Define datasets
orders_raw = Dataset("s3://orders-incoming/raw/")
orders_validated = Dataset("s3://orders-processed/validated/")

# DAG 1: Ingestion - triggered by schedule OR API
@dag(
    schedule="*/5 * * * *",  # Fallback: check every 5 min
    start_date=datetime(2024, 1, 1),
    catchup=False,
)
def ingest_orders():
    @task(outlets=[orders_raw])  # Declares it produces this dataset
    def pull_from_sellers():
        """Pull new order batches from seller uploads."""
        # ... processing logic ...
        pass

    pull_from_sellers()


# DAG 2: Validation - triggered AUTOMATICALLY when orders_raw is updated
@dag(
    schedule=[orders_raw],  # Triggered by dataset, NOT cron
    start_date=datetime(2024, 1, 1),
    catchup=False,
)
def validate_orders():
    @task(outlets=[orders_validated])
    def validate_batch():
        """Runs immediately when ingest_orders completes."""
        pass

    validate_batch()


# DAG 3: Fulfillment - triggered when validation completes
@dag(
    schedule=[orders_validated],
    start_date=datetime(2024, 1, 1),
    catchup=False,
)
def fulfill_orders():
    @task
    def send_to_warehouse():
        pass

    send_to_warehouse()
```

#### API-Triggered DAGs

```python
# Trigger a DAG run via REST API (from external system)
# POST /api/v1/dags/process_order_batch/dagRuns

# Example: Lambda triggers Airflow when S3 upload completes
import requests

def lambda_handler(event, context):
    """AWS Lambda triggered by S3 PutObject event."""
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    response = requests.post(
        "https://airflow.internal/api/v1/dags/process_order_batch/dagRuns",
        headers={"Authorization": "Bearer <token>"},
        json={
            "conf": {
                "bucket": bucket,
                "key": key,
                "seller_id": key.split('/')[1],
            },
            "logical_date": datetime.utcnow().isoformat() + "Z",
        },
    )
    return {"statusCode": response.status_code}
```

### 5. Async Patterns in Airflow

#### Writing Async Triggers

```python
import asyncio
from typing import Any, AsyncIterator
from airflow.triggers.base import BaseTrigger, TriggerEvent


class SQSOrderBatchTrigger(BaseTrigger):
    """
    Watches an SQS queue for order batch notifications.
    Fully async - runs in the Triggerer's event loop.
    """

    def __init__(self, queue_url: str, aws_conn_id: str = 'aws_default',
                 max_messages: int = 10, wait_seconds: int = 20):
        super().__init__()
        self.queue_url = queue_url
        self.aws_conn_id = aws_conn_id
        self.max_messages = max_messages
        self.wait_seconds = wait_seconds

    def serialize(self) -> tuple[str, dict[str, Any]]:
        return (
            "dags.triggers.sqs_trigger.SQSOrderBatchTrigger",
            {
                "queue_url": self.queue_url,
                "aws_conn_id": self.aws_conn_id,
                "max_messages": self.max_messages,
                "wait_seconds": self.wait_seconds,
            },
        )

    async def run(self) -> AsyncIterator[TriggerEvent]:
        """
        Long-poll SQS asynchronously. SQS long-polling is perfect
        for async triggers - the server holds the connection until
        messages arrive (up to 20 seconds), no busy-waiting.
        """
        import aiobotocore.session

        session = aiobotocore.session.get_session()
        async with session.create_client('sqs') as client:
            while True:
                try:
                    response = await client.receive_message(
                        QueueUrl=self.queue_url,
                        MaxNumberOfMessages=self.max_messages,
                        WaitTimeSeconds=self.wait_seconds,  # Long poll
                    )
                    messages = response.get('Messages', [])
                    if messages:
                        # Got messages - fire trigger
                        batch_info = [
                            {
                                "body": msg['Body'],
                                "receipt_handle": msg['ReceiptHandle'],
                            }
                            for msg in messages
                        ]
                        yield TriggerEvent({
                            "status": "success",
                            "messages": batch_info,
                        })
                        return
                    # No messages - loop continues (long-poll handles the wait)
                except Exception as e:
                    yield TriggerEvent({"status": "error", "message": str(e)})
                    return


class SQSBatchTriggerWithBackoff(BaseTrigger):
    """
    Enhanced trigger with exponential backoff on errors.
    Production-grade error handling in async context.
    """

    def __init__(self, queue_url: str, aws_conn_id: str = 'aws_default'):
        super().__init__()
        self.queue_url = queue_url
        self.aws_conn_id = aws_conn_id

    def serialize(self) -> tuple[str, dict[str, Any]]:
        return (
            "dags.triggers.sqs_trigger.SQSBatchTriggerWithBackoff",
            {"queue_url": self.queue_url, "aws_conn_id": self.aws_conn_id},
        )

    async def run(self) -> AsyncIterator[TriggerEvent]:
        import aiobotocore.session

        session = aiobotocore.session.get_session()
        backoff = 1
        max_backoff = 60

        while True:
            try:
                async with session.create_client('sqs') as client:
                    response = await client.receive_message(
                        QueueUrl=self.queue_url,
                        MaxNumberOfMessages=10,
                        WaitTimeSeconds=20,
                    )
                    messages = response.get('Messages', [])
                    if messages:
                        yield TriggerEvent({"status": "success", "messages": messages})
                        return
                    backoff = 1  # Reset on successful poll (even if no messages)

            except asyncio.CancelledError:
                # Task was cancelled (timeout or DAG deleted) - clean exit
                raise
            except Exception as e:
                # Transient error - back off and retry
                self.log.warning(f"SQS poll error (retrying in {backoff}s): {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
```

## Production Implementation

### Complete Order Processing DAG

```python
"""
Event-Driven Order Processing Pipeline
=======================================
Processes 1M+ orders/hour with zero wasted worker capacity.

Architecture:
- S3 event → SQS → Triggerer (deferrable sensor) → Worker (process)
- No cron scheduling - purely event-driven
- Burst handling via pools and priority weights
"""

from airflow.decorators import dag, task
from airflow.models import Pool
from airflow.operators.python import PythonOperator
from airflow.datasets import Dataset
from datetime import datetime, timedelta
from typing import Any

# Custom imports
from dags.triggers.s3_batch_trigger import S3BatchTrigger
from dags.sensors.deferrable_s3 import DeferrableS3BatchSensor


# --- Pool Configuration (set via CLI or API) ---
# airflow pools set order_processing 50 "Limit concurrent order processing"
# airflow pools set high_priority_orders 20 "Reserved for priority sellers"


@dag(
    dag_id="event_driven_order_processing",
    schedule=None,  # No cron - triggered by API or dataset
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=100,  # Allow many concurrent runs (one per batch)
    tags=["orders", "event-driven", "production"],
    default_args={
        "retries": 3,
        "retry_delay": timedelta(seconds=30),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    },
)
def event_driven_order_processing():

    @task(pool="order_processing")
    def validate_batch(batch_info: dict) -> dict:
        """Validate order batch schema and business rules."""
        import pyarrow.parquet as pq
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook

        hook = S3Hook()
        bucket = batch_info["bucket"]
        key = batch_info["key"]

        # Download and validate
        local_path = hook.download_file(key=key, bucket_name=bucket)
        table = pq.read_table(local_path)

        # Validation
        invalid_rows = []
        for i, row in enumerate(table.to_pydict()["order_id"]):
            if row is None:
                invalid_rows.append(i)

        return {
            "key": key,
            "total_orders": len(table),
            "valid_orders": len(table) - len(invalid_rows),
            "invalid_count": len(invalid_rows),
            "seller_id": batch_info.get("seller_id"),
        }

    @task(pool="order_processing")
    def enrich_orders(validation_result: dict) -> dict:
        """Enrich orders with product catalog and customer data."""
        # ... enrichment logic ...
        return {
            **validation_result,
            "enriched": True,
            "enrichment_timestamp": datetime.utcnow().isoformat(),
        }

    @task(pool="order_processing", priority_weight=5)
    def process_payments(enriched_data: dict) -> dict:
        """Process payments - higher priority (weight=5)."""
        # ... payment processing ...
        return {**enriched_data, "payments_processed": True}

    @task(
        pool="order_processing",
        outlets=[Dataset("s3://orders-processed/fulfilled/")],
    )
    def write_to_fulfillment(processed_data: dict) -> None:
        """Write processed orders to fulfillment system."""
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook
        import json

        hook = S3Hook()
        output_key = f"fulfilled/{processed_data['seller_id']}/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.json"
        hook.load_string(
            string_data=json.dumps(processed_data),
            key=output_key,
            bucket_name="orders-processed",
        )

    # Pipeline: validate → enrich → process payments → fulfill
    batch_info = "{{ dag_run.conf }}"  # Passed via API trigger
    validated = validate_batch(batch_info=batch_info)
    enriched = enrich_orders(validation_result=validated)
    paid = process_payments(enriched_data=enriched)
    write_to_fulfillment(processed_data=paid)


event_driven_order_processing()


# ============================================
# WATCHER DAG: Uses deferrable sensor to watch for batches
# and triggers the processing DAG via API
# ============================================

@dag(
    dag_id="order_batch_watcher",
    schedule="@continuous",  # Restarts immediately after completion
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["orders", "watcher", "deferrable"],
)
def order_batch_watcher():
    """
    Continuously watches for new order batches using deferrable sensor.
    Uses ZERO worker slots while waiting (deferred to Triggerer).
    When a batch arrives, triggers the processing DAG.
    """

    wait_for_batch = DeferrableS3BatchSensor(
        task_id="wait_for_new_batch",
        bucket="orders-incoming",
        prefix="pending/",
        aws_conn_id="aws_default",
        # Deferrable - releases worker slot immediately
    )

    @task
    def trigger_processing(files: list[str]):
        """Trigger processing DAG for each discovered batch."""
        from airflow.api.client.local_client import Client

        client = Client(None, None)
        for file_key in files:
            seller_id = file_key.split('/')[1]
            client.trigger_dag(
                dag_id="event_driven_order_processing",
                conf={
                    "bucket": "orders-incoming",
                    "key": file_key,
                    "seller_id": seller_id,
                },
            )

    @task
    def move_to_processing(files: list[str]):
        """Move files from pending/ to processing/ to avoid re-triggering."""
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook

        hook = S3Hook()
        for key in files:
            new_key = key.replace("pending/", "processing/", 1)
            hook.copy_object(
                source_bucket_key=key,
                dest_bucket_key=new_key,
                source_bucket_name="orders-incoming",
                dest_bucket_name="orders-incoming",
            )
            hook.delete_objects(bucket="orders-incoming", keys=[key])

    batch_files = wait_for_batch
    trigger_processing(files=batch_files)
    move_to_processing(files=batch_files)


order_batch_watcher()
```

### Worker Slot Savings Calculation

```python
"""
Resource comparison: Traditional vs Deferrable
"""

# --- Traditional mode='poke' ---
sellers = 500
poke_interval_sec = 30
avg_wait_time_min = 15  # Average time until batch arrives
worker_slots_total = 200

# Each seller needs 1 dedicated slot while waiting
slots_for_waiting = sellers  # 500 slots needed
# But we only have 200! System cannot function.

# --- Traditional mode='reschedule' ---
# Each sensor occupies a slot for ~5 seconds per check
check_duration_sec = 5
checks_per_minute = 60 / poke_interval_sec  # 2 checks/min per seller
total_checks_per_minute = sellers * checks_per_minute  # 1000 checks/min
slots_occupied_avg = total_checks_per_minute * check_duration_sec / 60  # ~83 slots
# 83/200 = 41.5% of capacity used for checking
# Plus scheduler must handle 1000 reschedule events per minute

# --- Deferrable ---
# Triggerer handles all 500 sensors in 1 process
triggerer_memory_mb = 500  # ~1MB per trigger coroutine
worker_slots_for_waiting = 0  # ZERO
worker_slots_for_processing = 200  # ALL available
# Processing throughput: 200 concurrent batch processors
# vs 117 with reschedule, vs 0 with poke (system fails)
```

## Production Handling

### Black Friday Burst Scenario

```python
"""
Black Friday: 3M orders/hour = 50,000 orders/minute
Batches arrive every 5 seconds instead of every 30s-5min
"""

# Problem: 200 worker slots, batches arriving faster than processing
# Solution: Pools + Priority + Backpressure

from airflow.models import Variable


@dag(
    dag_id="burst_aware_order_processing",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=500,  # Allow high concurrency during burst
    default_args={
        "pool": "order_processing",  # Pool limits actual concurrency
    },
)
def burst_aware_processing():
    """
    Handles burst by:
    1. Pool limits concurrent processing (prevents overload)
    2. Priority weights ensure critical orders go first
    3. Queued tasks wait in scheduler (not on workers)
    4. Backpressure: watcher slows down when queue is deep
    """

    @task(priority_weight=10)  # Higher = processed sooner
    def process_priority_seller(batch_info: dict):
        """Priority sellers (top revenue) get processed first."""
        pass

    @task(priority_weight=1)  # Lower priority
    def process_standard_seller(batch_info: dict):
        """Standard sellers processed after priority ones."""
        pass

    # Dynamic routing based on seller tier
    @task
    def route_batch(batch_info: dict):
        seller_id = batch_info["seller_id"]
        priority_sellers = Variable.get("priority_sellers", deserialize_json=True)
        if seller_id in priority_sellers:
            return "priority"
        return "standard"

    route_batch(batch_info="{{ dag_run.conf }}")


# --- Backpressure in the watcher ---
@task
def trigger_with_backpressure(files: list[str]):
    """Check queue depth before triggering more work."""
    from airflow.models import DagRun
    from airflow.utils.state import DagRunState
    from airflow.utils.session import provide_session
    import time

    @provide_session
    def get_queued_runs(session=None):
        return session.query(DagRun).filter(
            DagRun.dag_id == "event_driven_order_processing",
            DagRun.state == DagRunState.RUNNING,
        ).count()

    queued = get_queued_runs()
    max_queued = 200  # Backpressure threshold

    if queued > max_queued:
        # Too many running - slow down
        time.sleep(30)  # Simple backpressure

    # Proceed with triggering
    # ...
```

### Triggerer Failure Handling

```python
"""
What happens when the Triggerer crashes?

1. Deferred tasks remain in 'deferred' state in the DB
2. When Triggerer restarts, it picks up all deferred triggers
3. Triggers re-serialize from DB and resume watching
4. No data loss - triggers are persistent

For HA: run 2+ Triggerer instances. They share the load
via the metadata DB (no split-brain issues).
"""

# Helm values for Triggerer HA (Kubernetes deployment)
# helm_values.yaml:
"""
triggerer:
  replicas: 2           # HA: 2 triggerer instances
  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "1000m"
  args:
    - "triggerer"
    - "--capacity"
    - "1000"            # Each instance handles up to 1000 triggers
  livenessProbe:
    exec:
      command:
        - "airflow"
        - "jobs"
        - "check"
        - "--job-type"
        - "TriggererJob"
    initialDelaySeconds: 30
    periodSeconds: 30
"""
```

### Auto-Scaling Based on Pending Tasks

```python
"""
KEDA (Kubernetes Event-Driven Autoscaling) configuration
to scale workers based on pending task count.
"""

# keda-scaledobject.yaml
"""
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: airflow-worker-scaler
spec:
  scaleTargetRef:
    name: airflow-worker
  minReplicaCount: 5
  maxReplicaCount: 50
  triggers:
    - type: postgresql
      metadata:
        connectionFromEnv: AIRFLOW_DB_URL
        query: >
          SELECT COUNT(*) FROM task_instance 
          WHERE state = 'queued' 
          AND queue = 'default'
        targetQueryValue: "10"  # Scale up when >10 tasks queued per worker
        activationTargetQueryValue: "5"
"""
```

## Key Takeaways

| Concept | Key Insight |
|---------|-------------|
| **Deferrable Operators** | Release worker slots while waiting. 1 Triggerer replaces hundreds of blocked workers. |
| **Triggerer** | asyncio event loop. Handles thousands of concurrent watches in a single process. |
| **mode comparison** | poke=blocks slot, reschedule=overhead, deferrable=best. Always use deferrable in production. |
| **Event-driven DAGs** | Datasets, API triggers, and continuous schedules eliminate cron polling. |
| **Burst handling** | Pools cap concurrency, priority weights order the queue, backpressure slows intake. |
| **Triggerer HA** | Multiple instances share load via DB. Triggers persist across restarts. |
| **Cost math** | 500 sensors with poke = system failure. With deferrable = 0 worker slots used. |

**Decision framework:**
- Wait < 30 seconds → `mode='poke'` is fine
- Wait minutes to hours, < 50 concurrent → `mode='reschedule'`
- Wait minutes to hours, 50+ concurrent → **deferrable (always)**
- External event should start processing → API trigger or Dataset trigger
- Need zero-latency reaction → S3 Event → SQS → Deferrable SQS Trigger
