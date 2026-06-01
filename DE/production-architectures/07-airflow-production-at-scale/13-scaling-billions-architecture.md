# Scaling Airflow for Billions of Transactions

## The Scaling Challenge

Production Airflow deployments processing billions of transactions face extreme operational demands:

| Metric | Target |
|--------|--------|
| Task instances/day | 500,000+ |
| Active DAGs | 2,000+ |
| Concurrent tasks | 800+ |
| Metadata DB queries/sec | 10,000+ |
| Scheduling latency | < 5 seconds |
| DAG parse time (2K DAGs) | < 30 seconds |
| System uptime | 99.95% |

At this scale, every default configuration becomes a bottleneck. The architecture must be intentionally designed for horizontal scaling across all components: schedulers, workers, database, message broker, and DAG parsing infrastructure.

---

## Horizontal Scaling Components

### 1. HA Scheduler (Multiple Active Schedulers)

Since Airflow 2.0, multiple schedulers can run simultaneously using database-level row locking for coordination. Each scheduler picks up work independently, and the DB ensures no duplicate scheduling.

**How Multiple Schedulers Coordinate:**

```
Scheduler-1 ──┐
Scheduler-2 ──┼──→ PostgreSQL (SELECT ... FOR UPDATE SKIP LOCKED) ──→ Task Queue
Scheduler-3 ──┘
```

- Each scheduler locks DAG runs via `FOR UPDATE SKIP LOCKED`
- No leader election needed — all schedulers are active
- Failed scheduler's locks are released automatically via transaction timeout
- Optimal count: **3-5 schedulers** (beyond 5 yields diminishing returns due to DB lock contention)

**Scheduler Performance Parameters:**

| Parameter | Default | At Scale | Effect |
|-----------|---------|----------|--------|
| `min_file_process_interval` | 30s | 60-120s | How often each DAG file is re-parsed |
| `dag_dir_list_interval` | 300s | 120s | How often new DAG files are discovered |
| `parsing_processes` | 2 | 8-16 | Parallel DAG parsing workers per scheduler |
| `max_dagruns_to_create_per_loop` | 10 | 50 | DAG runs created per scheduler loop |
| `max_active_runs_per_dag` | 16 | 32-64 | Concurrent runs of same DAG |
| `scheduler_heartbeat_sec` | 5 | 5 | Keep at 5; lower wastes CPU |
| `schedule_after_task_execution` | True | True | Local task scheduling after execution |
| `max_tis_per_query` | 512 | 256 | Batch size for task state changes |
| `pool_metrics_interval` | 5.0 | 10.0 | Reduce pool metric query frequency |

**Anti-Patterns That Kill Scheduler Performance:**

1. **Too many schedulers** (>5): Lock contention on `dag_run` table exceeds throughput gain
2. **Low `min_file_process_interval`** (<30s): Constant re-parsing starves scheduling loops
3. **Excessive `max_active_runs_per_dag`**: Creates millions of task instances in queued state
4. **Untuned `max_tis_per_query`**: Large batches cause long DB transactions and locks
5. **Running scheduler on same node as workers**: CPU contention degrades scheduling latency

---

### 2. Worker Auto-Scaling

#### KEDA for Celery Workers (Kubernetes)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: airflow-celery-workers
spec:
  scaleTargetRef:
    name: airflow-worker
  minReplicaCount: 5
  maxReplicaCount: 100
  pollingInterval: 10
  cooldownPeriod: 300          # 5 min scale-down grace period
  triggers:
    - type: redis-lists
      metadata:
        address: redis:6379
        listName: default       # Celery queue name
        listLength: "10"        # 1 worker per 10 queued tasks
    - type: redis-lists
      metadata:
        address: redis:6379
        listName: heavy_compute
        listLength: "3"         # More aggressive scaling for heavy queue
```

#### HPA for KubernetesExecutor

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: airflow-scheduler-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: airflow-scheduler
  minReplicas: 3
  maxReplicas: 5
  metrics:
    - type: Pods
      pods:
        metric:
          name: scheduler_tasks_queued
        target:
          type: AverageValue
          averageValue: "200"
```

#### Celery Autoscale Configuration

```ini
[celery]
worker_autoscale = 16,4        # max=16, min=4 concurrent tasks per worker
worker_prefetch_multiplier = 1  # Critical: don't prefetch at scale
worker_max_tasks_per_child = 50 # Restart worker after 50 tasks (memory leak prevention)
```

#### Spot/Preemptible Workers

```yaml
# Node pool for spot workers
nodeSelector:
  cloud.google.com/gke-spot: "true"
tolerations:
  - key: cloud.google.com/gke-spot
    operator: Equal
    value: "true"
    effect: NoSchedule
```

- Use spot for **non-critical, idempotent** tasks only
- Set `retries=3` and `retry_delay=timedelta(minutes=2)` for spot tasks
- Keep 20-30% on-demand capacity for critical path DAGs
- Cost savings: 60-70% on worker compute

#### Scale-Down Safety

```python
# Custom pre-stop hook to drain worker gracefully
lifecycle:
  preStop:
    exec:
      command:
        - "celery"
        - "-A"
        - "airflow.providers.celery.executors.celery_executor.app"
        - "control"
        - "cancel_consumer"
        - "default"
# terminationGracePeriodSeconds must exceed max task duration
terminationGracePeriodSeconds: 7200  # 2 hours
```

---

### 3. Metadata Database Scaling

#### PostgreSQL Tuning for Airflow Workload

```ini
# postgresql.conf optimized for Airflow (64GB RAM, 16 vCPU instance)

# Memory
shared_buffers = 16GB                    # 25% of RAM
effective_cache_size = 48GB              # 75% of RAM
work_mem = 64MB                          # Per-sort operation
maintenance_work_mem = 2GB               # For VACUUM, CREATE INDEX

# Connections (with PgBouncer in front)
max_connections = 200                    # PgBouncer handles pooling
superuser_reserved_connections = 5

# Write Performance
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB

# Query Planning (SSD-optimized)
random_page_cost = 1.1                   # SSD: nearly sequential speed
effective_io_concurrency = 200           # SSD parallelism
seq_page_cost = 1.0

# Parallelism
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_worker_processes = 16

# Autovacuum (aggressive for high-churn tables)
autovacuum_max_workers = 6
autovacuum_naptime = 15s
autovacuum_vacuum_threshold = 50
autovacuum_vacuum_scale_factor = 0.02    # Vacuum at 2% dead tuples
autovacuum_analyze_threshold = 50
autovacuum_analyze_scale_factor = 0.01
```

#### PgBouncer Configuration

```ini
[databases]
airflow = host=pg-primary port=5432 dbname=airflow

[pgbouncer]
pool_mode = transaction              # Must be transaction mode for Airflow
max_client_conn = 2000
default_pool_size = 50
min_pool_size = 10
reserve_pool_size = 10
reserve_pool_timeout = 3
max_db_connections = 150             # Leave headroom below PG max_connections
server_idle_timeout = 300
server_lifetime = 3600
log_connections = 0
log_disconnections = 0
```

#### Connection Pooling Math

```
Required connections = (num_schedulers × parsing_processes) +
                       (num_workers × worker_concurrency × sql_alchemy_pool_size) +
                       (webserver_workers × sql_alchemy_pool_size) +
                       buffer(20%)

Example:
  3 schedulers × 8 parsing = 24
  50 workers × 16 concurrency × 5 pool = ... (use PgBouncer!)
  4 webserver × 5 pool = 20

PgBouncer multiplexes 2000+ app connections → 150 DB connections
```

#### Read Replicas for Web Server

```ini
# airflow.cfg - route webserver reads to replica
[webserver]
sql_alchemy_conn = postgresql://user:pass@pgbouncer-replica:6432/airflow

[core]
sql_alchemy_conn = postgresql://user:pass@pgbouncer-primary:6432/airflow
```

#### Database Maintenance

```sql
-- Partition task_instance by execution_date (PostgreSQL 12+)
CREATE TABLE task_instance (
    task_id VARCHAR(250),
    dag_id VARCHAR(250),
    run_id VARCHAR(250),
    execution_date TIMESTAMPTZ,
    state VARCHAR(20),
    -- ... other columns
) PARTITION BY RANGE (execution_date);

-- Create monthly partitions
CREATE TABLE task_instance_2024_01 PARTITION OF task_instance
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Archive old partitions (detach + move to cold storage)
ALTER TABLE task_instance DETACH PARTITION task_instance_2023_01;

-- Targeted VACUUM on hot partitions
VACUUM (ANALYZE, VERBOSE) task_instance_2024_06;
```

---

### 4. DAG Parsing Optimization

#### DAG Serialization

DAG serialization (enabled by default since 2.0) stores parsed DAGs in the `serialized_dag` table. The webserver and schedulers read from DB instead of parsing files.

```ini
[core]
store_serialized_dags = True
min_serialized_dag_update_interval = 30   # Don't re-serialize more than every 30s
min_serialized_dag_fetch_interval = 10    # Webserver cache TTL
```

#### Reducing Import Time

```python
# BAD: Top-level imports of heavy libraries
import pandas as pd
import boto3
from google.cloud import bigquery

# GOOD: Lazy imports inside task callables
def my_task():
    import pandas as pd
    # use pandas here
```

#### .airflowignore Patterns

```
# .airflowignore in DAGs folder
__pycache__
.git
tests/
fixtures/
README.md
*.pyc
helpers/
utils/
# Ignore subdirectories that aren't DAG folders
archive/
deprecated/
```

#### DAG File Organization for Parallel Parsing

```
dags/
├── team_a/          # Each folder parsed by separate process
│   ├── dag_1.py
│   └── dag_2.py
├── team_b/
│   ├── dag_3.py
│   └── dag_4.py
└── team_c/
    ├── dag_5.py
    └── dag_6.py
```

- Distribute DAGs across files evenly (avoid 1 file with 500 DAGs)
- Target: **5-20 DAGs per file** for optimal parsing parallelism
- Keep total file count reasonable (500-1000 files max)

#### Benchmark: Parsing at Scale

| DAG Count | Files | parsing_processes | Parse Time | Strategy |
|-----------|-------|-------------------|------------|----------|
| 100 | 50 | 4 | 3s | Default |
| 1,000 | 200 | 8 | 12s | Optimized imports |
| 5,000 | 500 | 16 | 22s | Lazy imports + .airflowignore |
| 10,000 | 1,000 | 16 | 28s | Full optimization + serialization |

---

### 5. Queue Architecture for Scale

#### Multiple Celery Queues by Workload Type

```python
# Queue definitions
QUEUES = {
    'default': 'Standard tasks, 5-min timeout',
    'heavy_compute': 'ML training, large transforms (4 CPU, 16GB)',
    'io_bound': 'API calls, file transfers (high concurrency)',
    'critical': 'SLA-bound tasks, priority processing',
    'backfill': 'Historical reprocessing, lowest priority',
}

# Task routing
with DAG('critical_pipeline') as dag:
    task = PythonOperator(
        task_id='process_payments',
        queue='critical',
        priority_weight=10,
        python_callable=process_payments,
    )
```

#### Worker Pool Configuration per Queue

```yaml
# Worker deployment per queue
- name: worker-default
  replicas: 20
  args: ["celery", "worker", "-Q", "default", "--autoscale=16,4"]
  resources:
    cpu: 2
    memory: 4Gi

- name: worker-heavy
  replicas: 10
  args: ["celery", "worker", "-Q", "heavy_compute", "--autoscale=4,1"]
  resources:
    cpu: 8
    memory: 32Gi

- name: worker-io
  replicas: 15
  args: ["celery", "worker", "-Q", "io_bound", "--autoscale=32,8"]
  resources:
    cpu: 2
    memory: 2Gi

- name: worker-critical
  replicas: 5
  args: ["celery", "worker", "-Q", "critical", "--autoscale=8,4"]
  resources:
    cpu: 4
    memory: 8Gi
```

#### Priority Queue Configuration

```ini
[celery]
# Weight rule determines priority calculation
weight_rule = downstream  # Tasks with more downstream get higher priority

# Pool slots control concurrency per pool
[pools]
critical_pool = 50          # Reserve 50 slots for critical
default_pool = 200
backfill_pool = 30          # Limit backfill concurrency
```

#### Dead Letter Pattern for Stuck Tasks

```python
from airflow.models import DagRun, TaskInstance
from airflow.utils.state import State
from datetime import timedelta

def detect_stuck_tasks():
    """Move tasks stuck in 'queued' for >30 min to failed state."""
    stuck_threshold = timezone.utcnow() - timedelta(minutes=30)
    stuck_tasks = session.query(TaskInstance).filter(
        TaskInstance.state == State.QUEUED,
        TaskInstance.queued_dttm < stuck_threshold,
    ).all()

    for ti in stuck_tasks:
        ti.state = State.FAILED
        # Push to dead letter topic for investigation
        publish_to_dlq(ti.dag_id, ti.task_id, ti.execution_date)
    session.commit()
```

---

## Performance Tuning

### Scheduler Tuning Matrix

| Scale | min_file_process_interval | parsing_processes | max_dagruns_to_create_per_loop | max_tis_per_query | Schedulers |
|-------|---------------------------|-------------------|-------------------------------|-------------------|------------|
| Small (<100 DAGs) | 30s | 2 | 10 | 512 | 1 |
| Medium (100-500) | 60s | 4 | 20 | 512 | 2 |
| Large (500-2K) | 90s | 8 | 50 | 256 | 3 |
| XL (2K-5K) | 120s | 16 | 50 | 128 | 4 |
| XXL (5K+) | 180s | 16 | 100 | 64 | 5 |

### Database Query Optimization

#### Identifying Slow Queries

```sql
-- Enable pg_stat_statements
CREATE EXTENSION pg_stat_statements;

-- Top 10 slowest queries by total time
SELECT
    calls,
    round(total_exec_time::numeric, 2) as total_ms,
    round(mean_exec_time::numeric, 2) as mean_ms,
    round((100 * total_exec_time / sum(total_exec_time) OVER())::numeric, 2) as pct,
    substring(query, 1, 100) as query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

#### Critical Indexes for task_instance

```sql
-- These indexes are essential at scale (some beyond Airflow defaults)
CREATE INDEX idx_ti_state_queued ON task_instance(state)
    WHERE state IN ('queued', 'scheduled', 'running');

CREATE INDEX idx_ti_dag_run ON task_instance(dag_id, run_id, state);

CREATE INDEX idx_ti_pool_state ON task_instance(pool, state)
    WHERE state IN ('queued', 'scheduled', 'running');

CREATE INDEX idx_dag_run_state ON dag_run(state, dag_id)
    WHERE state = 'running';

-- Partial index for scheduler hot path
CREATE INDEX idx_ti_schedulable ON task_instance(dag_id, task_id, run_id)
    WHERE state = 'scheduled';
```

#### Archiving Old Task Instances

```python
# DAG to archive task instances older than 90 days
archive_query = """
    INSERT INTO task_instance_archive
    SELECT * FROM task_instance
    WHERE execution_date < NOW() - INTERVAL '90 days'
    AND state IN ('success', 'failed', 'skipped');

    DELETE FROM task_instance
    WHERE execution_date < NOW() - INTERVAL '90 days'
    AND state IN ('success', 'failed', 'skipped');
"""
```

### Task Execution Optimization

| Optimization | Before | After | Impact |
|-------------|--------|-------|--------|
| Lazy imports | 2.1s task startup | 0.3s startup | -86% overhead |
| Disable XCom for large tasks | 500ms serialization | 0ms | -500ms/task |
| Template rendering cache | 150ms/task | 20ms/task | -87% |
| Warm worker pool | 5s cold start | 0.1s | -98% |
| Task batching (mapped tasks) | 1000 individual tasks | 50 mapped batches | -95% scheduling overhead |

---

## Capacity Planning

### Sizing Formulas

```python
# Workers needed
workers = (tasks_per_day * avg_task_duration_sec) / (86400 * utilization_target * concurrency_per_worker)

# Example: 500K tasks/day, 30s avg, 70% utilization, 16 concurrency
workers = (500000 * 30) / (86400 * 0.70 * 16) = 15.5 → 20 workers (with buffer)

# Database IOPS
db_iops = task_instances_per_sec * 12  # ~12 DB operations per task lifecycle
# 500K/day = 5.8/sec → 70 sustained IOPS minimum (burst to 500+ during peaks)

# Redis memory for Celery broker
redis_memory_mb = max_queued_tasks * 2KB  # ~2KB per serialized task message
# 10,000 queued tasks = 20MB (Redis is rarely the bottleneck)

# Scheduler CPU cores
scheduler_cores = (num_dags * parse_frequency_per_min) / (parsing_processes * 60)
# 2000 DAGs parsed every 2 min = 2000/120 = 16.7 parses/sec → 16 parsing_processes
```

### Growth Planning

| Component | Scale Trigger | Action | Cost/Unit |
|-----------|--------------|--------|-----------|
| Workers | Queue depth > 100 for 5min | Add 5 workers | ~$150/mo per worker |
| Scheduler | Scheduling latency > 10s | Add scheduler (up to 5) | ~$200/mo |
| Database CPU | CPU > 70% sustained | Upgrade instance class | ~$500/mo per step |
| Database IOPS | IOPS > 80% provisioned | Increase IOPS or upgrade | ~$0.10/IOPS/mo |
| PgBouncer | Connection wait > 100ms | Add PgBouncer instance | ~$50/mo |
| Redis | Memory > 70% | Upgrade instance | ~$100/mo per step |

### Leading Indicators of Capacity Issues

1. **Scheduling latency creeping above 5s** → Scheduler overloaded
2. **Queue depth growing monotonically** → Workers can't keep up
3. **DB connection wait time > 50ms** → Pool exhaustion
4. **DAG parse time increasing** → Too many DAGs or heavy imports
5. **Task start_date - queued_dttm > 60s** → Worker starvation

---

## Benchmarks

### Before vs After Tuning

| Metric | 100 DAGs (default) | 1K DAGs (tuned) | 10K DAGs (fully optimized) |
|--------|--------------------|-----------------|-----------------------------|
| Scheduling latency | 2s | 4s | 8s → 3s after tuning |
| DAG parse time | 5s | 45s → 15s | 300s → 28s |
| Max task throughput/min | 200 | 800 | 3,000 |
| DB queries/sec (peak) | 500 | 3,000 | 12,000 |
| Concurrent tasks | 32 | 200 | 800+ |
| Webserver response time | 200ms | 800ms → 300ms | 5s → 400ms (read replica) |

### Scheduling Latency by Configuration

| Configuration | Latency (p50) | Latency (p99) |
|--------------|---------------|---------------|
| 1 scheduler, defaults | 3.2s | 15s |
| 3 schedulers, defaults | 1.8s | 8s |
| 3 schedulers, tuned | 1.1s | 4s |
| 5 schedulers, tuned + DB optimized | 0.8s | 2.5s |

### Throughput Limits by Component

| Component | Bottleneck At | Resolution |
|-----------|--------------|------------|
| Single scheduler | ~150 tasks/min scheduled | Add schedulers |
| PostgreSQL (db.r5.xlarge) | ~5,000 queries/sec | Upgrade to r5.2xlarge |
| Redis (r6g.large) | ~50,000 msgs/sec | Rarely the limit |
| Single Celery worker (16 concurrency) | ~32 tasks/min (30s avg) | Add workers |
| PgBouncer (single) | ~5,000 connections | Add instances |

---

## Anti-Patterns at Scale

### Top 10 Things That Break Airflow at Scale

| # | Anti-Pattern | Impact | Fix |
|---|-------------|--------|-----|
| 1 | Heavy imports at DAG file top level | Parse time 10x+ slower | Lazy imports inside callables |
| 2 | Storing large data in XCom | DB bloat, OOM on serialization | Use external storage (S3/GCS), pass references |
| 3 | Too many tasks per DAG (>500) | UI unusable, scheduling slow | Split into sub-DAGs or use mapped tasks |
| 4 | No connection pooling (PgBouncer) | DB connection exhaustion | Always use PgBouncer in transaction mode |
| 5 | `depends_on_past=True` everywhere | Cascading failures block pipelines | Use explicit sensors or data checks |
| 6 | Synchronous external API calls in DAG parse | Parse hangs if API is slow | Never call external services during parse |
| 7 | Single large DAG file with all DAGs | Parsing serialized, can't parallelize | One file per DAG or small groups |
| 8 | Not cleaning metadata DB | Tables grow to billions of rows | Partition + archive after 90 days |
| 9 | `catchup=True` on high-frequency DAGs | Creates millions of backfill runs | Disable catchup, use explicit backfill DAGs |
| 10 | Running webserver and scheduler together | Resource contention, crashes | Separate deployments with dedicated resources |

---

## Production Configuration Reference

```ini
# airflow.cfg — Tuned for billions-scale processing
# Target: 500K+ tasks/day, 2000+ DAGs, 800+ concurrent tasks

#==============================================================================
# CORE
#==============================================================================
[core]
executor = CeleryExecutor
# For KubernetesExecutor at scale, use CeleryKubernetesExecutor
# executor = CeleryKubernetesExecutor

parallelism = 1024                         # Global max concurrent tasks
max_active_tasks_per_dag = 64              # Per-DAG concurrency
max_active_runs_per_dag = 32               # Concurrent runs of same DAG
dags_are_paused_at_creation = True         # Don't auto-run new DAGs
dagbag_import_timeout = 60                 # Kill slow DAG imports
dag_file_processor_timeout = 120           # Kill stuck file processors
store_serialized_dags = True
min_serialized_dag_update_interval = 30
min_serialized_dag_fetch_interval = 10

# Database connection
sql_alchemy_conn = postgresql+psycopg2://airflow:pass@pgbouncer:6432/airflow
sql_alchemy_pool_enabled = True
sql_alchemy_pool_size = 10
sql_alchemy_max_overflow = 20
sql_alchemy_pool_recycle = 3600
sql_alchemy_pool_pre_ping = True

#==============================================================================
# SCHEDULER
#==============================================================================
[scheduler]
num_runs = -1                              # Run forever
min_file_process_interval = 90             # Re-parse each file every 90s
dag_dir_list_interval = 120                # Discover new files every 2 min
parsing_processes = 12                     # Parallel file parsers
max_dagruns_to_create_per_loop = 50
max_tis_per_query = 128                    # Smaller batches = shorter locks
scheduler_heartbeat_sec = 5
orphaned_tasks_check_interval = 300
schedule_after_task_execution = True
scheduler_health_check_threshold = 60
parsing_cleanup_interval = 120
file_parsing_sort_mode = modified_time     # Parse recently modified first

#==============================================================================
# CELERY
#==============================================================================
[celery]
broker_url = redis://:password@redis-cluster:6379/0
result_backend = db+postgresql://airflow:pass@pgbouncer:6432/airflow
worker_concurrency = 16
worker_prefetch_multiplier = 1             # Critical: prevents task hoarding
worker_max_tasks_per_child = 100           # Prevent memory leaks
worker_autoscale = 16,4
broker_transport_options = {"visibility_timeout": 21600, "fan_out_prefix": true}
task_acks_late = True                      # Re-queue if worker dies
task_reject_on_worker_lost = True
operation_timeout = 10.0

#==============================================================================
# CELERY BROKER TRANSPORT OPTIONS (Redis)
#==============================================================================
[celery_broker_transport_options]
visibility_timeout = 21600                 # 6 hours (must exceed longest task)
socket_timeout = 30
socket_connect_timeout = 30
retry_on_timeout = True

#==============================================================================
# WEBSERVER
#==============================================================================
[webserver]
workers = 4
worker_class = gevent
web_server_worker_timeout = 120
default_ui_timezone = UTC
page_size = 50                             # Limit UI queries
# Point to read replica for UI queries
# sql_alchemy_conn = postgresql://airflow:pass@pgbouncer-replica:6432/airflow

#==============================================================================
# LOGGING
#==============================================================================
[logging]
remote_logging = True
remote_log_conn_id = aws_default
remote_base_log_folder = s3://airflow-logs/production/
encrypt_s3_logs = True
logging_level = INFO
fab_logging_level = WARNING

#==============================================================================
# METRICS
#==============================================================================
[metrics]
statsd_on = True
statsd_host = statsd-exporter
statsd_port = 9125
statsd_prefix = airflow
metrics_use_pattern_match = True

#==============================================================================
# KUBERNETES (if using CeleryKubernetesExecutor)
#==============================================================================
[kubernetes_executor]
namespace = airflow
delete_worker_pods = True
delete_worker_pods_on_failure = False       # Keep for debugging
worker_pods_creation_batch_size = 20        # Don't overwhelm API server
multi_namespace_mode = False

#==============================================================================
# SMART SENSOR (deprecated in 2.7+, use deferrable operators instead)
#==============================================================================
# Use deferrable operators to reduce worker slot usage for waiting tasks
# Example: TimeSensorAsync, S3KeySensorAsync, etc.

#==============================================================================
# TRIGGERER (for deferrable operators)
#==============================================================================
[triggerer]
default_capacity = 1000                    # Triggers per triggerer instance
# Run 3+ triggerer instances for HA
```

---

## Summary: Scaling Checklist

```
□ Deploy 3-5 active schedulers behind shared DB
□ Configure PgBouncer in transaction mode (max 150 DB connections)
□ Set parsing_processes = CPU cores on scheduler nodes
□ Enable DAG serialization with 30s+ update interval
□ Use KEDA/HPA for worker autoscaling with 5-min cooldown
□ Partition task_instance table by month
□ Archive metadata older than 90 days
□ Implement multiple queues by workload type
□ Use deferrable operators for all sensor/wait tasks
□ Set worker_prefetch_multiplier = 1
□ Monitor scheduling latency, queue depth, DB connections
□ Use read replicas for webserver queries
□ Enable remote logging (S3/GCS) — never local disk
□ Set up pg_stat_statements for query analysis
□ Create partial indexes on task_instance for hot queries
□ Test with 2x expected load before production cutover
```
