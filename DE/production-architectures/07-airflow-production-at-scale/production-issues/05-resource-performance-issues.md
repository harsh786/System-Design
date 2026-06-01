# Production Issues 61-75: Resource & Performance Issues

---

## Issue #61: Pool Starvation (Critical Tasks Can't Get Slots)

**Symptoms:**
- High-priority tasks stuck in `queued` for hours
- Low-priority bulk tasks consuming all pool slots
- Critical SLA pipelines delayed by batch workloads
- Pool utilization 100% during peak hours

**Root Cause:**
- All tasks sharing `default_pool` (128 slots)
- No priority differentiation within pools
- Bulk export DAGs consuming 50+ slots simultaneously
- No separate pools for critical vs non-critical workloads

**Fix:**
```python
# Create tiered pool architecture
# Admin → Pools → Create:
# critical_pool:    20 slots (SLA pipelines only)
# standard_pool:   100 slots (regular ETL)
# bulk_pool:        30 slots (exports, reports)
# external_api:     10 slots (rate-limited APIs)

# Critical pipeline gets dedicated pool
critical_task = PythonOperator(
    task_id='regulatory_report',
    pool='critical_pool',
    priority_weight=100,           # Highest priority within pool
    python_callable=generate_report,
)

# Bulk work uses separate pool (can't starve critical)
bulk_task = PythonOperator(
    task_id='export_analytics',
    pool='bulk_pool',
    priority_weight=1,
    python_callable=export_data,
)
```

```bash
# Create pools via CLI
airflow pools set critical_pool 20 "SLA-critical pipelines only"
airflow pools set standard_pool 100 "Standard ETL workloads"
airflow pools set bulk_pool 30 "Batch exports and reports"
airflow pools set warehouse_db 10 "Warehouse connection limit"
```

---

## Issue #62: Memory Leak in Long-Running Workers

**Symptoms:**
- Worker memory usage grows linearly over days
- Eventually OOM killed, then restarts fresh
- Performance degrades before OOM (Python GC pressure)
- Pattern: memory grows 100MB/day without corresponding task growth

**Root Cause:**
- Python memory fragmentation from many allocations/deallocations
- Celery worker processes not recycled
- Global caches in imported libraries growing unbounded
- Hooks not properly closing connections (connection objects accumulate)

**Fix:**
```ini
[celery]
# Recycle worker processes after N tasks
worker_max_tasks_per_child = 100         # Kill and restart after 100 tasks
worker_max_memory_per_child = 4000000    # Kill if exceeds 4GB (kilobytes)

# Autoscale with periodic restart
worker_autoscale = 16,4                  # max,min concurrency
```

```python
# Explicit memory cleanup in tasks
import gc

def memory_intensive_task(**context):
    """Process large data with explicit cleanup."""
    df = pd.read_parquet('s3://bucket/large.parquet')
    result = df.groupby('key').agg(...)
    
    # Write result
    result.to_parquet('s3://bucket/output.parquet')
    
    # Explicit cleanup
    del df
    del result
    gc.collect()  # Force garbage collection
```

```yaml
# K8s: memory limit with restart policy
containers:
- name: worker
  resources:
    requests:
      memory: "4Gi"
    limits:
      memory: "6Gi"      # OOM kill acts as safety net
  # Worker restarts clean = fresh memory state
```

---

## Issue #63: DAG File Processing Consuming All CPU

**Symptoms:**
- Scheduler nodes at 100% CPU
- `parsing_processes` consuming all available cores
- Actual scheduling logic starved of CPU time
- Adding more DAG files makes scheduler slower (not linear)

**Root Cause:**
- `parsing_processes` set higher than available CPU cores
- Complex DAG files requiring heavy computation during parse
- Every `.py` file in DAG folder being parsed (including utils, tests)
- No `.airflowignore` excluding non-DAG files

**Fix:**
```ini
[scheduler]
# Set parsing_processes = 50-75% of available cores
# If scheduler has 8 cores:
parsing_processes = 6                    # Leave 2 cores for scheduling loop

# Don't re-parse too frequently
min_file_process_interval = 60           # Re-parse each file max once per 60s
dag_dir_list_interval = 300              # Scan for NEW files every 5 min
```

```
# .airflowignore (exclude non-DAG files from parsing)
# Place in DAG_FOLDER root

# Test files
tests/
test_*.py
*_test.py

# Utility modules (imported by DAGs but not DAGs themselves)
utils/
helpers/
lib/
common/

# Config files
*.json
*.yaml
*.yml
*.sql
*.csv

# Python cache
__pycache__/
*.pyc

# Documentation
*.md
docs/
```

---

## Issue #64: Webserver OOM Under Concurrent Users

**Symptoms:**
- Webserver crashes when 20+ users access UI simultaneously
- Grid view of large DAGs causes OOM
- API calls from CI/CD systems adding to load
- Gunicorn workers exhausted → 502 errors

**Fix:**
```ini
[webserver]
workers = 4                              # Gunicorn workers (2-4× CPU cores)
worker_class = sync                      # 'sync' for most cases, 'gevent' for many connections
web_server_worker_timeout = 120          # Kill slow requests after 2min
worker_refresh_interval = 6000           # Restart workers every 100min (memory cleanup)
worker_refresh_batch_size = 1            # Restart 1 worker at a time (availability)

# Limit what UI can request:
default_dag_run_display_number = 25      # Don't show 500 runs by default
page_size = 100
```

```yaml
# K8s: proper webserver sizing
webserver:
  replicas: 3                            # Multiple instances behind LB
  resources:
    requests:
      memory: "2Gi"
      cpu: "1"
    limits:
      memory: "4Gi"
      cpu: "2"
```

---

## Issue #65: Redis Broker Memory Full (Tasks Dropped)

**Symptoms:**
- Redis returns `OOM command not allowed when used memory > maxmemory`
- Tasks submitted by scheduler never appear on workers
- Celery tasks silently dropped
- Monitoring shows gap between scheduler send and worker receive

**Root Cause:**
- Redis `maxmemory-policy` set to `allkeys-lru` → evicts task messages!
- Task results stored in Redis consuming memory
- Old task results never expired
- Redis not sized for queue depth during peak

**Fix:**
```ini
# Redis configuration for Celery broker
maxmemory 4gb
maxmemory-policy noeviction           # CRITICAL: never evict broker messages!
# noeviction: return errors on write when memory full (alerts you to problem)
# NEVER use allkeys-lru for a message broker!

# Persistence (optional for broker)
save ""                                # Disable RDB snapshots (broker is transient)
appendonly no                          # Disable AOF (celery tasks can be re-queued)
```

```ini
# airflow.cfg: separate Redis for broker vs results
[celery]
broker_url = redis://redis-broker:6379/0          # Dedicated broker Redis
result_backend = db+postgresql://airflow:pass@pgbouncer:6432/airflow  # DB for results (not Redis!)

# OR if using Redis for results, set separate instance with expiry:
# result_backend = redis://redis-results:6379/0
```

```yaml
# Size Redis for peak queue depth
# Formula: max_queued_tasks × avg_message_size × 2 (safety margin)
# 1000 tasks × 4KB per message × 2 = 8MB
# Add overhead for connections and internal structures: 1GB minimum
# Redis ElastiCache: r6g.large (13.07 GB) for production
```

---

## Issue #66: Triggerer Running Out of Async Slots

**Symptoms:**
- Deferrable operators stuck in `deferred` state
- New deferrals rejected
- Triggerer CPU/memory maxed out
- Error: `TriggerRunner: maximum number of triggers reached`

**Root Cause:**
- Single triggerer handling thousands of deferred tasks
- Triggers making blocking calls (not truly async)
- Memory leak in custom triggers
- Too many sensors converted to deferrable without capacity planning

**Fix:**
```yaml
# Scale triggerer horizontally
triggerer:
  replicas: 3                            # Multiple triggerers share load
  resources:
    requests:
      memory: "2Gi"
      cpu: "2"
    limits:
      memory: "4Gi"
      cpu: "4"
```

```ini
[triggerer]
default_capacity = 1000                  # Max triggers per triggerer instance
# With 3 replicas: 3000 total concurrent deferred tasks
```

```python
# Ensure custom triggers are truly async (non-blocking)
# BAD: Blocking call in trigger
class MyTrigger(BaseTrigger):
    async def run(self):
        while True:
            result = requests.get(self.url)  # BLOCKING! Freezes event loop!
            if result.ok:
                yield TriggerEvent(result.json())
            await asyncio.sleep(60)

# GOOD: Async HTTP calls
class MyTrigger(BaseTrigger):
    async def run(self):
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.get(self.url) as response:  # Non-blocking!
                    if response.status == 200:
                        data = await response.json()
                        yield TriggerEvent(data)
                await asyncio.sleep(60)
```

---

## Issue #67: Spot Instance Preemption Killing Tasks

**Symptoms:**
- Tasks fail unpredictably with `SIGTERM` or pod eviction
- Happens more during peak hours (spot price spikes)
- Long-running tasks (>1h) affected most
- Cost savings from spot offset by re-execution costs

**Root Cause:**
- Worker nodes using spot/preemptible instances for cost savings
- Cloud provider reclaims instances with 2-minute warning
- Tasks don't handle graceful shutdown
- No checkpointing for long-running jobs

**Fix:**
```python
# 1. Implement checkpointing for long tasks
def long_running_etl(**context):
    """ETL with checkpoint/resume for spot tolerance."""
    checkpoint_path = f's3://checkpoints/{context["run_id"]}/{context["task_id"]}.json'
    
    # Resume from checkpoint if exists
    last_batch = load_checkpoint(checkpoint_path) or 0
    
    for batch_num in range(last_batch, total_batches):
        process_batch(batch_num)
        
        # Checkpoint every 10 batches
        if batch_num % 10 == 0:
            save_checkpoint(checkpoint_path, batch_num)
    
    # Cleanup checkpoint on success
    delete_checkpoint(checkpoint_path)
```

```yaml
# 2. Use mixed node pools: on-demand for critical, spot for bulk
# Helm values:
workers:
  # Critical queue on on-demand nodes
  - name: critical-workers
    replicas: 10
    queues: "critical,priority"
    nodeSelector:
      node-lifecycle: on-demand
  
  # Bulk queue on spot nodes (cheaper, interruptible OK)
  - name: bulk-workers
    replicas: 30
    queues: "default,bulk"
    nodeSelector:
      node-lifecycle: spot
    tolerations:
    - key: "spot"
      operator: "Equal"
      value: "true"
      effect: "NoSchedule"
```

```python
# 3. Route tasks based on duration and criticality
critical_task = PythonOperator(
    task_id='regulatory_report',
    queue='critical',              # Runs on on-demand nodes
)

bulk_task = PythonOperator(
    task_id='analytics_export',
    queue='bulk',                  # Runs on spot nodes (OK to retry)
    retries=3,                     # Retry if preempted
)
```

---

## Issue #68: Network Timeout Between Components (Worker ↔ DB)

**Symptoms:**
- Intermittent `OperationalError: connection timed out`
- Tasks fail sporadically with network errors
- More frequent during peak hours (network saturation)
- Cross-AZ communication adding latency

**Fix:**
```ini
# airflow.cfg - network resilience
[database]
sql_alchemy_connect_args = {
    "connect_timeout": 10,
    "options": "-c statement_timeout=300000",
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5
}
sql_alchemy_pool_pre_ping = True         # Detect dead connections
sql_alchemy_pool_recycle = 1800          # Refresh connections every 30min
```

```yaml
# K8s: Ensure workers and DB are in same AZ (or tolerate cross-AZ)
# Use topology constraints:
spec:
  topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        component: worker
```

---

## Issue #69: CPU Throttling on K8s Worker Pods

**Symptoms:**
- Tasks taking 3-5x longer than expected
- `container_cpu_cfs_throttled_seconds_total` metric high
- Pod CPU usage shows 100% at limit
- Same task runs fast locally but slow in Airflow

**Root Cause:**
- CPU limit set too low for burst workloads
- CFS (Completely Fair Scheduler) throttling kicks in
- Pod requests low (scheduled on busy node) but needs burst
- Data processing tasks are CPU-bound

**Fix:**
```yaml
# Option 1: Remove CPU limit (allow burstable)
containers:
- name: worker
  resources:
    requests:
      cpu: "2"        # Guaranteed CPU
      memory: "4Gi"
    limits:
      # cpu: "4"      # REMOVE CPU limit - allow bursting
      memory: "8Gi"   # Keep memory limit (OOM protection)

# Option 2: Set higher limit with proper request
containers:
- name: worker
  resources:
    requests:
      cpu: "2"
    limits:
      cpu: "8"        # 4x burst allowed
      memory: "8Gi"
```

```python
# Option 3: Route CPU-intensive tasks to dedicated node pool
cpu_intensive_task = PythonOperator(
    task_id='heavy_computation',
    queue='compute_intensive',
    executor_config={
        "pod_override": k8s.V1Pod(
            spec=k8s.V1PodSpec(
                containers=[k8s.V1Container(
                    name="base",
                    resources=k8s.V1ResourceRequirements(
                        requests={"cpu": "8", "memory": "16Gi"},
                        limits={"cpu": "16", "memory": "32Gi"}
                    )
                )],
                nodeSelector={"node-type": "compute-optimized"}  # c5.4xlarge
            )
        )
    }
)
```

---

## Issue #70: Disk Pressure on Worker Nodes (Logs, Temp Files)

**Symptoms:**
- Worker pods evicted due to disk pressure
- Node enters `DiskPressure` condition
- Task logs filling local disk before remote upload
- Temporary files from data processing not cleaned

**Fix:**
```yaml
# 1. Use emptyDir with size limit for temp files
volumes:
- name: temp-storage
  emptyDir:
    sizeLimit: 10Gi          # Prevent unbounded growth
containers:
- name: worker
  volumeMounts:
  - name: temp-storage
    mountPath: /tmp/airflow
```

```python
# 2. Clean up temp files in task code
import tempfile
import os

def process_with_cleanup(**context):
    """Always clean up temporary files."""
    temp_dir = tempfile.mkdtemp(prefix='airflow_')
    try:
        # Use temp_dir for processing
        output_file = os.path.join(temp_dir, 'output.parquet')
        process_data(output_file)
        upload_to_s3(output_file)
    finally:
        # ALWAYS cleanup, even on failure
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
```

```ini
# 3. Log rotation and remote logging
[logging]
remote_logging = True
remote_base_log_folder = s3://airflow-logs/
# Local logs cleaned after upload:
[logging]
base_log_folder = /opt/airflow/logs
# Set up logrotate or cron to clean old local logs
```

---

## Issue #71: Webserver API Rate Limiting Not Configured

**Symptoms:**
- CI/CD pipeline making 1000s of API calls per minute
- Webserver overwhelmed, UI users can't access
- Memory spikes from serializing large API responses
- No protection against runaway scripts

**Fix:**
```ini
[api]
maximum_page_limit = 100                 # Max results per API call
```

```yaml
# Rate limiting via Ingress (nginx)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: airflow-webserver
  annotations:
    nginx.ingress.kubernetes.io/limit-rps: "50"           # 50 req/sec
    nginx.ingress.kubernetes.io/limit-connections: "20"    # 20 concurrent
    nginx.ingress.kubernetes.io/limit-burst-multiplier: "5"
spec:
  rules:
  - host: airflow.internal.com
    http:
      paths:
      - path: /api/
        pathType: Prefix
        backend:
          service:
            name: airflow-webserver
            port:
              number: 8080
```

---

## Issue #72: Inefficient DAG Causing Unnecessary Task Executions

**Symptoms:**
- DAG runs tasks that produce no output (no data for that partition)
- Thousands of "empty" task executions per day
- Wasted compute and pool slots
- Monitoring noise from tasks that do nothing

**Fix:**
```python
# Use ShortCircuitOperator to skip when no work needed
from airflow.operators.python import ShortCircuitOperator

def check_data_exists(ds: str) -> bool:
    """Return False to skip all downstream tasks."""
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook
    hook = S3Hook()
    return hook.check_for_key(f'raw-data/orders/{ds}/', bucket_name='data-lake')

check = ShortCircuitOperator(
    task_id='check_data_exists',
    python_callable=check_data_exists,
    op_kwargs={'ds': '{{ ds }}'},
)

# All downstream tasks skip if check returns False
check >> extract >> transform >> load
```

---

## Issue #73: Task Duration Variance (Same Task 5min One Day, 2h Next)

**Symptoms:**
- SLA breaches due to unpredictable task duration
- Capacity planning impossible with high variance
- Same logical task: 5 min on Monday, 2 hours on Friday

**Root Cause:**
- Data volume varies by day (weekend vs weekday, month-end spike)
- External system performance varies (shared database load)
- No resource isolation (noisy neighbor on same node)
- Network latency variations (cross-region data transfer)

**Fix:**
```python
# 1. Dynamic timeout based on expected data volume
def get_timeout(ds: str) -> timedelta:
    """Estimate timeout based on data volume indicators."""
    day_of_week = datetime.strptime(ds, '%Y-%m-%d').weekday()
    if day_of_week == 0:  # Monday (biggest backlog from weekend)
        return timedelta(hours=4)
    elif ds.endswith(('28', '29', '30', '31')):  # Month-end
        return timedelta(hours=6)
    return timedelta(hours=2)

# 2. Alert on duration anomaly (not just absolute threshold)
def duration_check_callback(context):
    """Alert if duration is 2x the 7-day average."""
    ti = context['task_instance']
    current_duration = (ti.end_date - ti.start_date).total_seconds()
    avg_duration = get_historical_avg_duration(ti.dag_id, ti.task_id, days=7)
    
    if current_duration > avg_duration * 2:
        send_alert(f"Task {ti.task_id} took {current_duration}s (avg: {avg_duration}s)")
```

---

## Issue #74: Connection Pool Leak in Custom Operators

**Symptoms:**
- `too many connections` errors after hours of operation
- Connections accumulate over time
- Database shows idle connections from Airflow workers
- Restarting workers temporarily fixes the issue

**Root Cause:**
- Custom operators/hooks not properly closing connections
- Exception paths skipping connection cleanup
- Using raw `psycopg2.connect()` instead of Airflow hooks
- Hook.get_conn() called multiple times without close

**Fix:**
```python
# BAD: Connection leak
class MyOperator(BaseOperator):
    def execute(self, context):
        import psycopg2
        conn = psycopg2.connect(host='db', dbname='mydb')  # No close!
        cur = conn.cursor()
        cur.execute("SELECT ...")
        results = cur.fetchall()
        # conn never closed! Leaked!
        return results

# GOOD: Proper connection management
class MyOperator(BaseOperator):
    def execute(self, context):
        hook = PostgresHook(postgres_conn_id=self.conn_id)
        # Context manager ensures cleanup
        with hook.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
                return cur.fetchall()
        # Connection returned to pool here

# ALSO GOOD: try/finally pattern
class MyOperator(BaseOperator):
    def execute(self, context):
        hook = PostgresHook(postgres_conn_id=self.conn_id)
        conn = hook.get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT ...")
            return cur.fetchall()
        finally:
            conn.close()  # ALWAYS close, even on exception
```

---

## Issue #75: Auto-Scaling Too Slow for Burst Workloads

**Symptoms:**
- Daily 6 AM pipeline burst: 500 tasks queued simultaneously
- Autoscaler takes 5-10 minutes to spin up workers
- By the time workers are ready, SLA is already at risk
- Morning burst pattern is predictable but not pre-scaled

**Fix:**
```yaml
# 1. Scheduled scaling (pre-warm for known peaks)
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: airflow-worker-scheduled
spec:
  scaleTargetRef:
    name: airflow-worker
  triggers:
  # Base: scale on queue depth
  - type: redis
    metadata:
      listName: default
      listLength: "5"
  # Pre-warm: scale up before known peak
  - type: cron
    metadata:
      timezone: America/New_York
      start: "50 5 * * *"          # Scale up at 5:50 AM (before 6 AM burst)
      end: "0 9 * * *"            # Scale down at 9 AM
      desiredReplicas: "50"        # Pre-warm 50 workers
```

```yaml
# 2. Cluster autoscaler warm pool (AWS)
# Maintain minimum number of nodes ready for instant scheduling
apiVersion: autoscaling.k8s.io/v1
kind: ClusterAutoscaler
spec:
  nodeGroups:
  - name: airflow-workers
    minSize: 10                    # Always keep 10 nodes warm
    maxSize: 100
    # Spot with on-demand fallback
    instanceTypes: ["m5.2xlarge", "m5a.2xlarge"]
```

```python
# 3. Stagger task start times to smooth burst
import random

for i, table in enumerate(tables):
    PythonOperator(
        task_id=f'process_{table}',
        python_callable=process_table,
        # Stagger start: don't all start at exact same second
        execution_timeout=timedelta(hours=2),
    )
# Use max_active_tasks at DAG level to limit concurrent:
# max_active_tasks=50 → only 50 of 500 tasks run simultaneously
```

---

## Summary: Resource & Performance Issue Prevention Checklist

```
[ ] Tiered pool architecture (critical/standard/bulk/api)
[ ] Worker memory recycling (worker_max_tasks_per_child=100)
[ ] .airflowignore excluding non-DAG files
[ ] Webserver: multiple replicas behind LB, proper worker count
[ ] Redis broker: noeviction policy, separate from result backend
[ ] Triggerer: 2-3 replicas with 1000 capacity each
[ ] Spot instances only for non-critical queues with retries
[ ] TCP keepalives on all database connections
[ ] CPU limits removed or generous (prevent throttling)
[ ] Temp file cleanup in finally blocks
[ ] API rate limiting on webserver ingress
[ ] ShortCircuitOperator for conditional execution
[ ] Duration anomaly detection (2x average = alert)
[ ] Connection management via hooks with context managers
[ ] Pre-warming workers before known peak hours
```
