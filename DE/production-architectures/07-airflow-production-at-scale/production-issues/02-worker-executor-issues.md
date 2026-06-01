# Production Issues 16-30: Worker & Executor Issues

---

## Issue #16: Celery Workers Not Picking Up Tasks

**Symptoms:**
- Tasks stuck in `queued` state
- `executor.queued_tasks` growing but `executor.running_tasks` = 0
- Workers appear online in Flower but idle
- Queue backlog increasing

**Root Cause:**
- Workers listening on wrong queue (task routed to queue worker doesn't consume)
- Redis broker connection dropped silently
- Worker concurrency exhausted (all slots busy with stuck tasks)
- Celery serialization mismatch between scheduler and worker

**Detection:**
```promql
airflow_executor_queued_tasks > 100 and airflow_executor_running_tasks < 5
```

**Fix:**
```bash
# Check which queues workers are listening to
celery -A airflow.executors.celery_executor.app inspect active_queues

# Check active tasks on workers
celery -A airflow.executors.celery_executor.app inspect active

# Restart workers (K8s)
kubectl rollout restart deployment/airflow-worker -n airflow
```

```ini
# airflow.cfg - ensure queue alignment
[operators]
default_queue = default

[celery]
broker_url = redis://redis-cluster:6379/0
worker_concurrency = 16
```

```python
# DAG-level: route to correct queue
task = PythonOperator(
    task_id='heavy_task',
    queue='heavy',          # Must match worker's -Q flag
    python_callable=my_func,
)
```

---

## Issue #17: Worker OOM Killed During Task Execution

**Symptoms:**
- Task stuck in `running` then becomes zombie
- K8s pod evicted with `OOMKilled` status
- Worker logs stop abruptly (no error message)
- Pattern: large data processing tasks consistently fail

**Root Cause:**
- Task loading entire dataset into memory (pandas read_csv without chunks)
- Memory leak in long-running worker processing multiple tasks
- Container memory limit too low for workload
- Python memory fragmentation over time

**Fix:**
```python
# BAD: Loading 50GB CSV into memory
def process_data():
    df = pd.read_csv('s3://bucket/huge_file.csv')  # 50GB → OOM
    return df.groupby('customer_id').sum()

# GOOD: Chunked processing
def process_data():
    result = None
    for chunk in pd.read_csv('s3://bucket/huge_file.csv', chunksize=100000):
        partial = chunk.groupby('customer_id').sum()
        result = partial if result is None else result.add(partial, fill_value=0)
    return result

# BETTER: Use Spark/distributed processing for large data
def process_data():
    """Submit to Spark instead of in-process."""
    from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
    # Let Spark handle the memory management
```

```yaml
# K8s: Set appropriate memory limits per queue
# Workers for heavy queue need more memory
worker:
  resources:
    requests:
      memory: "8Gi"
    limits:
      memory: "12Gi"    # 50% headroom above request
```

---

## Issue #18: KubernetesExecutor Pod Launch Timeout

**Symptoms:**
- Tasks stuck in `queued` for 5+ minutes
- Pods in `Pending` state
- `kubernetes_executor.pod_launch_errors` metric increasing
- Error: `Pod took too long to start`

**Root Cause:**
- Cluster autoscaler hasn't provisioned new nodes yet
- Image pull taking too long (large images, no caching)
- Resource requests exceed available node capacity
- Node selectors/tolerations too restrictive (no matching nodes)
- PersistentVolumeClaim pending (EBS volume in wrong AZ)

**Fix:**
```yaml
# 1. Pre-pull images on nodes using DaemonSet
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: airflow-image-prepull
spec:
  selector:
    matchLabels:
      app: image-prepull
  template:
    spec:
      initContainers:
      - name: prepull
        image: your-airflow-image:latest
        command: ['sh', '-c', 'echo Image pulled']
      containers:
      - name: pause
        image: k8s.gcr.io/pause:3.9
```

```ini
# airflow.cfg - increase timeout
[kubernetes_executor]
worker_pods_creation_batch_size = 16
worker_pods_pending_timeout = 300         # Wait 5 min before giving up
worker_pods_pending_timeout_check_interval = 30
delete_worker_pods = True
delete_worker_pods_on_failure = False      # Keep failed pods for debugging
```

```python
# Use smaller, optimized images
# Dockerfile multi-stage build
FROM python:3.11-slim AS base
# Only install what this specific DAG needs
RUN pip install --no-cache-dir apache-airflow==2.7.0 pandas pyarrow
# Don't include: tensorflow, scipy, etc. unless needed
```

---

## Issue #19: Celery Worker Autoscale Not Working Properly

**Symptoms:**
- Workers don't scale up during peak hours
- Workers don't scale down during off-hours (wasting $$)
- KEDA/HPA metrics not triggering correctly
- Burst workloads overwhelming fixed worker pool

**Root Cause:**
- HPA metrics (CPU) don't reflect Airflow queue depth
- KEDA trigger using wrong metric/threshold
- Scale-up takes 3-5 minutes (too slow for burst)
- Scale-down killing workers with running tasks

**Fix:**
```yaml
# KEDA ScaledObject - scale on Celery queue depth
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: airflow-worker-scaler
  namespace: airflow
spec:
  scaleTargetRef:
    name: airflow-worker
  pollingInterval: 15
  cooldownPeriod: 300              # Wait 5 min before scaling down
  minReplicaCount: 5               # Never go below 5
  maxReplicaCount: 100
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 600   # 10 min stabilization
          policies:
          - type: Pods
            value: 2                         # Scale down max 2 pods at a time
            periodSeconds: 120
        scaleUp:
          stabilizationWindowSeconds: 0      # Scale up immediately
          policies:
          - type: Pods
            value: 10                        # Scale up 10 pods at a time
            periodSeconds: 60
  triggers:
  - type: redis
    metadata:
      address: redis-cluster:6379
      listName: default                      # Celery queue name
      listLength: "5"                        # Scale up when 5+ tasks waiting
      activationListLength: "1"
```

```yaml
# Graceful termination - don't kill running tasks
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 7200    # 2 hours to finish current task
      containers:
      - name: worker
        lifecycle:
          preStop:
            exec:
              command:
              - "sh"
              - "-c"
              - "celery -A airflow.executors.celery_executor.app control cancel_consumer default && sleep 5"
              # Stop consuming new tasks, finish current ones
```

---

## Issue #20: Task Stuck in Running State After Worker Restart

**Symptoms:**
- After deployment/restart, tasks show `running` but no process executing
- Task will remain `running` until zombie detection kicks in (5+ minutes)
- Pool slots consumed by ghost tasks
- Manual intervention needed to clear

**Root Cause:**
- Worker killed without sending task failure signal
- `SIGKILL` (OOM or force kill) bypasses cleanup
- Celery acks task before execution starts (at_most_once default)
- No graceful shutdown hook configured

**Fix:**
```ini
[celery]
# Task acknowledgement AFTER execution (at-least-once)
task_acks_late = True              # Don't ack until task completes
worker_prefetch_multiplier = 1     # Only prefetch 1 task at a time

# Combined with zombie detection:
[scheduler]
scheduler_zombie_task_threshold = 120   # 2 minutes (reduce from default 5 min)
```

```bash
# Manual cleanup: mark stuck tasks as failed
airflow tasks clear <dag_id> -t <task_id> -s <start_date> -e <end_date>

# Or via API:
curl -X PATCH "http://airflow:8080/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}" \
  -H "Content-Type: application/json" \
  -d '{"new_state": "failed"}'
```

---

## Issue #21: KubernetesExecutor Pods Accumulating (Not Cleaned Up)

**Symptoms:**
- Hundreds of `Completed` or `Error` pods in namespace
- kubectl get pods shows thousands of entries
- etcd performance degradation from too many pod objects
- Node disk filling with container logs

**Root Cause:**
- `delete_worker_pods = False` or cleanup failing
- Failed pods not deleted (for debugging) but never cleaned
- Finalizers blocking pod deletion
- RBAC: Airflow service account lacks pod delete permission

**Fix:**
```ini
[kubernetes_executor]
delete_worker_pods = True              # Delete successful pods
delete_worker_pods_on_failure = False   # Keep failed for debugging (but clean later!)
```

```yaml
# CronJob to clean stale pods
apiVersion: batch/v1
kind: CronJob
metadata:
  name: cleanup-airflow-pods
  namespace: airflow
spec:
  schedule: "0 */6 * * *"    # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: airflow-cleanup
          containers:
          - name: cleanup
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - |
              # Delete completed pods older than 1 hour
              kubectl get pods -n airflow -l component=worker \
                --field-selector=status.phase=Succeeded \
                -o jsonpath='{.items[?(@.status.startTime)].metadata.name}' | \
                xargs -r kubectl delete pod -n airflow

              # Delete failed pods older than 24 hours
              kubectl get pods -n airflow -l component=worker \
                --field-selector=status.phase=Failed \
                -o json | \
                jq -r '.items[] | select(.status.startTime | fromdateiso8601 < (now - 86400)) | .metadata.name' | \
                xargs -r kubectl delete pod -n airflow
          restartPolicy: OnFailure
```

---

## Issue #22: Celery Flower Shows Workers Offline

**Symptoms:**
- Flower dashboard shows workers as offline
- Tasks still executing (workers are actually alive)
- Misleading monitoring alerts
- Flower consuming excessive memory

**Root Cause:**
- Flower uses separate connection to broker (may lose it)
- Worker event broadcasting disabled or rate-limited
- Redis pub/sub channel full
- Flower pod itself is resource-starved

**Fix:**
```ini
[celery]
worker_enable_remote_control = True     # Allow flower to query workers
```

```bash
# Restart Flower with proper settings
celery -A airflow.executors.celery_executor.app flower \
  --broker=redis://redis:6379/0 \
  --port=5555 \
  --persistent=True \
  --db=/tmp/flower.db \
  --max_tasks=10000              # Limit task history in memory
```

**Better Alternative: Skip Flower, use Prometheus metrics directly**
```yaml
# Flower is nice but unreliable at scale
# Instead: rely on StatsD metrics + Grafana
# Worker health = tasks completing + heartbeat present
```

---

## Issue #23: Task Execution Timeout Not Killing Task

**Symptoms:**
- Task runs beyond `execution_timeout` but doesn't get killed
- Process continues consuming resources
- Timeout appears to be ignored

**Root Cause:**
- Task is blocked in a C-extension call (NumPy, database driver)
- Python's signal-based timeout doesn't work in threads
- Subprocess spawned by task not killed when parent times out
- On Windows/some executors, SIGALRM not available

**Fix:**
```python
# execution_timeout uses SIGALRM - only works in main thread on Unix
task = PythonOperator(
    task_id='risky_task',
    execution_timeout=timedelta(hours=1),    # Signal-based timeout
    python_callable=my_func,
)

# For tasks that spawn subprocesses:
import subprocess
import os
import signal

def my_func():
    """Run subprocess with proper timeout and cleanup."""
    proc = subprocess.Popen(['spark-submit', '--master', 'yarn', 'job.py'],
                           preexec_fn=os.setsid)  # New process group
    try:
        proc.wait(timeout=3600)  # 1 hour
    except subprocess.TimeoutExpired:
        # Kill entire process group (including child processes)
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=30)
        if proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        raise
```

---

## Issue #24: CeleryExecutor Task Result Backend Overflow

**Symptoms:**
- Redis memory usage growing unbounded
- Workers slowing down writing results
- `ResultBackendError` exceptions
- Old task results never cleaned up

**Root Cause:**
- Default: Celery stores task results in Redis indefinitely
- Each task result consumes memory
- At 500K tasks/day, results accumulate fast
- result_expires not configured

**Fix:**
```ini
[celery]
# Use database as result backend (not Redis)
result_backend = db+postgresql://airflow:pass@pgbouncer:6432/airflow

# OR if using Redis, set expiry:
result_backend = redis://redis:6379/1
result_expires = 86400              # Delete results after 24 hours
```

```python
# Alternative: disable result backend entirely (if you don't need celery results)
# Airflow uses its own metadata DB for task state, not Celery results
# airflow.cfg:
[celery]
result_backend = db+postgresql://airflow:pass@pgbouncer:6432/airflow
# This stores in Airflow's own DB which gets cleaned by db clean command
```

---

## Issue #25: Worker Cannot Access Remote Resources (IAM/Network)

**Symptoms:**
- Task fails with `AccessDenied` or `ConnectionRefused`
- Works fine when tested locally
- Intermittent failures (works sometimes, fails other times)
- Different behavior between Celery worker and K8s worker pods

**Root Cause:**
- Worker pods don't have correct IAM role/service account
- Network policies blocking egress from worker namespace
- Security groups too restrictive for worker subnets
- Temporary credentials expired (STS token refresh issue)

**Fix:**
```yaml
# K8s: Proper IAM role for workers (AWS IRSA)
apiVersion: v1
kind: ServiceAccount
metadata:
  name: airflow-worker
  namespace: airflow
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/airflow-worker-role
---
# The IAM role must have permissions for ALL data sources workers access
# S3, Redshift, Glue, SQS, etc.
```

```yaml
# Network policy: allow worker egress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: airflow-worker-egress
  namespace: airflow
spec:
  podSelector:
    matchLabels:
      component: worker
  policyTypes:
  - Egress
  egress:
  - to: []    # Allow all egress (restrictive version below)
  # OR restrict to specific CIDRs:
  - to:
    - ipBlock:
        cidr: 10.0.0.0/8        # Internal services
    - ipBlock:
        cidr: 0.0.0.0/0         # External (S3, APIs)
        except:
        - 169.254.169.254/32    # Block metadata endpoint (use IRSA instead)
```

---

## Issue #26: Task Log Not Available in UI (Remote Logging Failure)

**Symptoms:**
- Click on task logs → "Log not found" or empty
- Logs exist on worker but not in S3/GCS
- Intermittent: some task logs available, others not
- After worker pod deleted, logs permanently lost

**Root Cause:**
- Remote logging not configured (logs only on local disk)
- Worker pod terminated before flushing logs to S3
- S3/GCS permissions incorrect for log writing
- Log upload timeout for large log files

**Fix:**
```ini
[logging]
remote_logging = True
remote_log_conn_id = aws_default
remote_base_log_folder = s3://airflow-logs/task-logs
encrypt_s3_logs = False
logging_level = INFO

# Ensure logs are flushed frequently
[logging]
log_fetch_timeout_sec = 5
log_auto_tailing_offset = 30
```

```python
# Custom logging configuration for guaranteed delivery
import logging
from airflow.utils.log.s3_task_handler import S3TaskHandler

# Ensure task handler flushes on close
LOGGING_CONFIG = {
    'handlers': {
        's3_task': {
            'class': 'airflow.utils.log.s3_task_handler.S3TaskHandler',
            'formatter': 'airflow',
            'base_log_folder': '/opt/airflow/logs',
            's3_log_folder': 's3://airflow-logs/task-logs',
        }
    }
}
```

```yaml
# Worker termination grace period must allow log flush
spec:
  terminationGracePeriodSeconds: 120   # 2 min to flush logs
  containers:
  - name: worker
    lifecycle:
      preStop:
        exec:
          command: ["sh", "-c", "sleep 30"]  # Allow log flush
```

---

## Issue #27: CeleryExecutor Broker Connection Storms (Thundering Herd)

**Symptoms:**
- All workers lose Redis connection simultaneously
- After Redis recovery, all workers reconnect at once → Redis overloaded
- Connection refused errors cycle repeatedly
- Tasks fail in waves

**Root Cause:**
- Redis failover causes all connections to drop
- All workers retry with same backoff → thundering herd
- No jitter in reconnection logic
- broker_connection_retry_on_startup without jitter

**Fix:**
```ini
[celery]
broker_connection_retry_on_startup = True
broker_connection_max_retries = 10
broker_connection_retry = True

# Connection pool settings
broker_pool_limit = 10
broker_transport_options = {"visibility_timeout": 21600, "socket_timeout": 5, "retry_on_timeout": true}
```

```python
# Custom celery config with jitter
# In airflow_local_settings.py or celery_config.py
import random

CELERY_CONFIG = {
    'broker_transport_options': {
        'visibility_timeout': 21600,
        'socket_timeout': 5,
        'socket_connect_timeout': 5,
        'retry_on_timeout': True,
    },
    'broker_connection_retry': True,
    'broker_connection_max_retries': None,  # Retry forever
    'broker_connection_retry_on_startup': True,
    # Exponential backoff with jitter
    'retry_backoff': True,
    'retry_backoff_max': 600,
    'retry_jitter': True,           # Add random jitter to prevent thundering herd
}
```

---

## Issue #28: KubernetesExecutor XCom Sidecar Failure

**Symptoms:**
- XCom push from K8s executor task fails silently
- Downstream tasks get `None` from xcom_pull
- Error: `Unable to retrieve xcom from task pod`
- Sidecar container crash loop

**Root Cause:**
- XCom sidecar container OOM (task wrote too much to XCom)
- Sidecar webserver not ready before task completes (race condition)
- Network policy blocking localhost communication
- XCom data too large for metadata DB

**Fix:**
```python
# Use custom XCom backend for K8s executor (S3-based)
# airflow.cfg:
[core]
xcom_backend = custom_xcom.S3XComBackend

# custom_xcom.py
from airflow.models.xcom import BaseXCom
import json, boto3

class S3XComBackend(BaseXCom):
    """Store XCom values in S3 if larger than 48KB."""
    
    PREFIX = "s3://airflow-xcom/"
    THRESHOLD = 48000  # 48KB
    
    @staticmethod
    def serialize_value(value, *, key=None, task_id=None, dag_id=None, run_id=None, map_index=-1):
        serialized = json.dumps(value)
        if len(serialized) < S3XComBackend.THRESHOLD:
            return BaseXCom.serialize_value(value)
        # Store in S3, return reference
        s3_key = f"{dag_id}/{run_id}/{task_id}/{key or 'return_value'}"
        boto3.client('s3').put_object(
            Bucket='airflow-xcom', Key=s3_key, Body=serialized
        )
        return BaseXCom.serialize_value({'__s3_ref': s3_key})
    
    @staticmethod
    def deserialize_value(result):
        val = BaseXCom.deserialize_value(result)
        if isinstance(val, dict) and '__s3_ref' in val:
            obj = boto3.client('s3').get_object(Bucket='airflow-xcom', Key=val['__s3_ref'])
            return json.loads(obj['Body'].read())
        return val
```

---

## Issue #29: Workers Competing for Same Database Connections

**Symptoms:**
- `connection pool exhausted` errors from hooks
- Tasks failing intermittently with database timeouts
- One DAG's tasks starve another DAG's database access
- Peak hours: connection failures spike

**Root Cause:**
- All tasks use same connection pool via hooks
- No isolation between DAGs for external DB access
- Hook opens connection per task, never explicitly closes
- Pool per worker process, but many tasks share process

**Fix:**
```python
# Use Airflow Pools to limit concurrent DB access
task = PythonOperator(
    task_id='query_warehouse',
    pool='warehouse_pool',        # Max 10 concurrent tasks hitting warehouse
    pool_slots=1,                 # Each task takes 1 slot
    python_callable=query_func,
)
```

```python
# Proper connection handling in tasks
from airflow.providers.postgres.hooks.postgres import PostgresHook

def query_func(**context):
    hook = PostgresHook(postgres_conn_id='warehouse')
    # Use context manager for guaranteed cleanup
    with hook.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM large_table WHERE date = %s", [context['ds']])
            results = cur.fetchall()
    # Connection returned to pool here
    return results
```

```ini
# Hook-level connection pool settings
# In Airflow connection "Extra" JSON field:
{
    "cursor": "dictcursor",
    "connect_timeout": 10,
    "keepalives": 1,
    "keepalives_idle": 30
}
```

---

## Issue #30: Executor Mismatch Between Environments (Dev vs Prod)

**Symptoms:**
- DAGs work in dev (LocalExecutor) but fail in prod (CeleryExecutor/K8sExecutor)
- File paths that exist on scheduler don't exist on workers
- Module imports succeed locally but fail on workers
- Environment variables missing on workers

**Root Cause:**
- LocalExecutor runs task in scheduler process (shares filesystem, env)
- CeleryExecutor runs on separate worker machines
- KubernetesExecutor runs in isolated pods with potentially different images
- Dev doesn't replicate production executor behavior

**Fix:**
```python
# 1. Never use local file paths (they won't exist on workers)
# BAD:
def read_data():
    return pd.read_csv('/home/user/data/file.csv')

# GOOD:
def read_data():
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook
    hook = S3Hook(aws_conn_id='aws_default')
    file = hook.download_file(key='data/file.csv', bucket_name='my-bucket')
    return pd.read_csv(file)
```

```yaml
# 2. Dev environment should use same executor class
# docker-compose.dev.yml should use CeleryExecutor:
x-airflow-common:
  environment:
    AIRFLOW__CORE__EXECUTOR: CeleryExecutor
    # NOT LocalExecutor
```

```python
# 3. Use executor_config to specify exact environment per task
task = PythonOperator(
    task_id='my_task',
    python_callable=my_func,
    executor_config={
        "pod_override": k8s.V1Pod(
            spec=k8s.V1PodSpec(
                containers=[k8s.V1Container(
                    name="base",
                    env=[
                        k8s.V1EnvVar(name="DB_HOST", value="prod-db"),
                        k8s.V1EnvVar(name="API_KEY", 
                                     valueFrom=k8s.V1EnvVarSource(
                                         secretKeyRef=k8s.V1SecretKeySelector(
                                             name="api-secrets", key="key")))
                    ]
                )]
            )
        )
    }
)
```

---

## Summary: Worker/Executor Issue Prevention Checklist

```
[ ] Use task_acks_late=True (at-least-once delivery)
[ ] Set worker_prefetch_multiplier=1 (don't buffer tasks)
[ ] Configure KEDA for queue-based autoscaling with proper cooldown
[ ] Set terminationGracePeriodSeconds > max task duration
[ ] Use proper IAM roles (IRSA/Workload Identity) for workers
[ ] Configure remote logging BEFORE deploying workers
[ ] Use S3-based XCom backend for KubernetesExecutor
[ ] Set execution_timeout on ALL tasks
[ ] Use Pools for external database connection limiting
[ ] Clean up completed K8s pods with CronJob
[ ] Pre-pull images on worker nodes
[ ] Match dev executor to prod executor type
[ ] Configure worker memory 50% above expected peak usage
[ ] Set zombie detection threshold to 2 minutes
[ ] Use result_backend with expiry or DB-backed
```
