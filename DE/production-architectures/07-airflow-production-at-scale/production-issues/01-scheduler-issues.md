# Production Issues 1-15: Scheduler Issues

---

## Issue #1: Scheduler Heartbeat Stops (Scheduler Freeze)

**Symptoms:**
- No new DAG runs created
- Tasks stuck in `scheduled` state indefinitely
- `scheduler_heartbeat` metric flatlines
- UI shows stale data

**Root Cause:**
- Scheduler OOM killed silently (K8s eviction)
- Long GC pause in Python (large object graph)
- Deadlock in metadata DB connection pool
- DAG parsing consuming all CPU (pathological DAG file)

**Detection:**
```promql
# Alert when heartbeat stops for 60s
increase(airflow_scheduler_heartbeat_total[2m]) == 0
```

**Fix:**
```bash
# Immediate: Restart scheduler
kubectl rollout restart deployment/airflow-scheduler -n airflow

# Prevent: HA schedulers (Airflow 2.0+)
# In values.yaml:
scheduler:
  replicas: 3  # Multiple active schedulers
  resources:
    requests:
      memory: "4Gi"
      cpu: "2"
    limits:
      memory: "6Gi"
      cpu: "4"
  livenessProbe:
    initialDelaySeconds: 10
    periodSeconds: 10
    failureThreshold: 5
```

**Production Config:**
```ini
# airflow.cfg
[scheduler]
num_runs = -1                          # Run forever
scheduler_heartbeat_sec = 5            # Heartbeat every 5s
scheduler_health_check_threshold = 30  # Unhealthy after 30s no heartbeat
```

---

## Issue #2: DAG Parsing Takes Too Long (>60 seconds)

**Symptoms:**
- New DAGs don't appear for minutes
- DAG changes not picked up
- Scheduler loop becomes slow
- `dag_processing.total_parse_time` metric exceeds threshold

**Root Cause:**
- Heavy imports at module level (pandas, spark, tensorflow)
- Database queries during DAG parsing (fetching config)
- Too many DAG files (10,000+) with insufficient parsing_processes
- Complex Jinja templating evaluated at parse time

**Detection:**
```promql
airflow_dag_processing_total_parse_time > 60
airflow_dag_processing_last_duration{dag_file="problematic.py"} > 30
```

**Fix:**
```python
# BAD: Heavy import at top level (runs every 30s during parse!)
import pandas as pd
import tensorflow as tf
from my_company.heavy_module import LargeClass

with DAG('my_dag') as dag:
    pass

# GOOD: Lazy imports inside task functions
def my_task_function():
    import pandas as pd  # Only imported when task EXECUTES
    import tensorflow as tf
    # ... actual work

with DAG('my_dag') as dag:
    task = PythonOperator(
        task_id='process',
        python_callable=my_task_function
    )
```

```python
# BAD: Database query during parse time
from airflow.models import Variable
tables = Variable.get('tables', deserialize_json=True)  # DB hit every parse!

for table in tables:
    PythonOperator(task_id=f'process_{table}', ...)

# GOOD: Use environment variables or static config file
import json
import os

config_path = os.path.join(os.path.dirname(__file__), 'config', 'tables.json')
with open(config_path) as f:
    tables = json.load(f)

for table in tables:
    PythonOperator(task_id=f'process_{table}', ...)
```

**Production Config:**
```ini
[scheduler]
min_file_process_interval = 60    # Don't re-parse faster than 60s
parsing_processes = 8             # Parallel DAG file parsers
dag_dir_list_interval = 300       # Scan for NEW files every 5min
```

---

## Issue #3: Scheduler Stuck in Infinite Backfill Loop

**Symptoms:**
- Thousands of DAG runs created unexpectedly
- Scheduler consumed creating runs instead of scheduling tasks
- Older execution_dates being scheduled that shouldn't be

**Root Cause:**
- `catchup=True` (default in older versions) with old `start_date`
- DAG `start_date` changed to an earlier date
- `max_active_runs` not set, allowing unlimited parallel runs

**Fix:**
```python
# ALWAYS set these in production
with DAG(
    'my_dag',
    start_date=datetime(2024, 1, 1),
    catchup=False,                    # Don't create runs for past intervals
    max_active_runs=3,                # Limit concurrent runs
    max_active_tasks=16,              # Limit concurrent tasks across runs
) as dag:
    pass
```

```bash
# Emergency: Delete unwanted DAG runs
airflow dags delete <dag_id>  # Nuclear option
# Or selectively:
airflow dags backfill <dag_id> --start-date 2024-01-01 --end-date 2024-01-01 --reset-dagruns --yes
```

**Prevention:**
```ini
[core]
max_active_runs_per_dag = 16         # Global limit
dagrun_timeout = 86400               # Kill runs older than 24h
```

---

## Issue #4: Scheduler Cannot Keep Up (Scheduling Latency >5min)

**Symptoms:**
- Tasks in `scheduled` state for minutes before moving to `queued`
- `dagrun.schedule_delay` growing over time
- Task throughput lower than expected
- Scheduler CPU at 100%

**Root Cause:**
- Too many DAGs for one scheduler to handle
- `max_dagruns_to_create_per_loop` too low
- Heavy database queries (task dependency checks)
- Serialized DAG reads too slow

**Detection:**
```promql
histogram_quantile(0.95, 
  rate(airflow_dagrun_schedule_delay_bucket[5m])
) > 300  # p95 > 5 minutes
```

**Fix:**
```ini
[scheduler]
# Increase scheduler throughput
max_dagruns_to_create_per_loop = 50          # Default is 10
max_dagruns_per_loop_to_schedule = 100       # Default is 20
scheduler_idle_sleep_time = 1                 # Reduce sleep between loops
use_job_schedule = True
max_tis_per_query = 512                       # Batch size for TI queries

# Add more schedulers (Airflow 2.0+)
# Deploy 2-3 scheduler pods
```

**Architecture Fix:**
```
Before: 1 Scheduler → 2000 DAGs → Scheduling latency: 8 minutes

After:  3 Schedulers (HA) → 2000 DAGs → Scheduling latency: 15 seconds
        + parsing_processes = 8 per scheduler
        + max_dagruns_to_create_per_loop = 50
```

---

## Issue #5: DAG Import Errors Silently Break Pipelines

**Symptoms:**
- DAG disappears from UI
- No runs created for a previously working DAG
- Other DAGs in same file also stop running
- No alerts (silent failure!)

**Root Cause:**
- Python syntax error in DAG file
- Dependency not installed on scheduler
- Import of a module that references an unavailable secret/connection
- Library version conflict after deployment

**Detection:**
```promql
airflow_dag_processing_import_errors > 0
```

```bash
# Check import errors
airflow dags list-import-errors

# Test before deploy
python -c "from airflow.models import DagBag; d = DagBag('.'); print(d.import_errors)"
```

**Fix - CI/CD Validation:**
```yaml
# .github/workflows/dag-validation.yml
name: Validate DAGs
on: [pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install apache-airflow==2.7.0
      - run: |
          python -c "
          from airflow.models import DagBag
          bag = DagBag(dag_folder='dags/', include_examples=False)
          if bag.import_errors:
              for file, error in bag.import_errors.items():
                  print(f'ERROR in {file}: {error}')
              exit(1)
          print(f'Successfully loaded {len(bag.dags)} DAGs')
          "
```

---

## Issue #6: Zombie Tasks (Tasks Running but Worker Dead)

**Symptoms:**
- Tasks stuck in `running` state forever
- Worker pod/process is gone but task not marked failed
- No heartbeat from task instance
- Resources consumed by phantom tasks (pool slots)

**Root Cause:**
- Worker OOM killed without graceful shutdown
- Network partition between worker and metadata DB
- Worker node terminated (spot instance reclaim)
- Celery worker killed without proper signal handling

**Detection:**
```promql
rate(airflow_zombie_tasks_killed_total[5m]) > 0
```

**Fix:**
```ini
[scheduler]
# Scheduler checks for zombies at this interval
scheduler_zombie_task_threshold = 300    # 5 minutes: task with no heartbeat = zombie
zombie_detection_interval = 60           # Check every 60 seconds

[core]
# Task must send heartbeat this often
task_heartbeat_sec = 5
killed_task_cleanup_time = 60            # Wait 60s before marking zombie as failed
```

```python
# In DAG: ensure tasks handle SIGTERM gracefully
import signal
import sys

def graceful_shutdown(signum, frame):
    """Clean up resources before being killed."""
    print("Received SIGTERM, cleaning up...")
    # Close connections, flush buffers, save checkpoint
    sys.exit(0)

def my_task(**context):
    signal.signal(signal.SIGTERM, graceful_shutdown)
    # ... long-running work
```

---

## Issue #7: Scheduler Failover Gap (Split-Brain with HA Schedulers)

**Symptoms:**
- Duplicate DAG runs created
- Same task instance scheduled twice
- Database deadlocks during scheduler coordination

**Root Cause:**
- Multiple schedulers race on DagRun creation
- Database lock timeout too short
- Network latency between scheduler and DB

**Fix:**
```ini
[scheduler]
# Database-level row locking prevents double-scheduling
# Ensure DB supports SELECT FOR UPDATE SKIP LOCKED (PostgreSQL 9.5+)

# Tune lock timeout
[database]
sql_alchemy_pool_size = 5
sql_alchemy_max_overflow = 10
sql_alchemy_pool_recycle = 1800
sql_alchemy_pool_pre_ping = True    # Test connections before use
```

```sql
-- Verify PostgreSQL supports skip locked
SHOW server_version;  -- Must be >= 9.5

-- Monitor lock contention
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_locks blocking_locks 
  ON blocking_locks.locktype = blocked_locks.locktype
WHERE NOT blocked_locks.granted;
```

---

## Issue #8: DAG File Processor Memory Leak

**Symptoms:**
- Scheduler memory grows continuously over hours/days
- Eventually OOM killed
- Parse time degrades as memory fills
- Happens more with dynamic DAGs

**Root Cause:**
- DAG file processor doesn't release memory between parse cycles
- Global state accumulated in DAG files (caches, connections)
- Python circular references preventing GC
- Large number of task instances in `TaskInstance` model cache

**Fix:**
```ini
[scheduler]
# Kill and restart DAG processor after N runs to release memory
num_runs = 1000                              # Restart processor after 1000 parse loops
parsing_cleanup_interval = 60                 # Force cleanup every 60s

# Or set process recycling
dag_file_processor_timeout = 180              # Kill slow parser after 3 min
```

```python
# Avoid global state in DAG files
# BAD
_cache = {}  # This grows forever, never cleared between parses

def get_config(key):
    if key not in _cache:
        _cache[key] = expensive_lookup(key)
    return _cache[key]

# GOOD: No module-level mutable state
def get_config(key):
    """Fetch fresh every time - parse only happens every 60s anyway."""
    return Variable.get(key, deserialize_json=True)
```

---

## Issue #9: Scheduler Database Connection Exhaustion

**Symptoms:**
- `OperationalError: too many connections for role "airflow"`
- Scheduler can't create new DagRuns
- Other components (webserver, workers) also lose DB access
- Cascading failure across all Airflow components

**Root Cause:**
- Each scheduler + webserver + worker opens connection pool
- Formula: (schedulers × pool_size) + (workers × pool_size) + (webserver × pool_size)
- No PgBouncer for connection multiplexing
- Connection leaks from crashed workers

**Fix:**
```
Connection Math:
  3 schedulers × 10 pool = 30
  5 webservers × 5 pool  = 25
  50 workers × 2 pool    = 100
  TOTAL = 155 connections needed

  PostgreSQL max_connections = 200 (default)
  Available after system processes = ~180
  
  With PgBouncer (transaction mode):
  PgBouncer → 20 actual DB connections, serves 500+ clients
```

```ini
# PgBouncer config (pgbouncer.ini)
[databases]
airflow = host=rds-endpoint port=5432 dbname=airflow

[pgbouncer]
listen_port = 6432
listen_addr = 0.0.0.0
auth_type = md5
pool_mode = transaction          # CRITICAL: transaction mode for Airflow
max_client_conn = 500            # Total clients allowed
default_pool_size = 20           # Actual DB connections per database
reserve_pool_size = 5            # Emergency connections
reserve_pool_timeout = 3
server_lifetime = 3600
server_idle_timeout = 600
```

```ini
# airflow.cfg - point to PgBouncer
[database]
sql_alchemy_conn = postgresql://airflow:pass@pgbouncer:6432/airflow
sql_alchemy_pool_enabled = True
sql_alchemy_pool_size = 5               # Per-process pool (small because PgBouncer handles it)
sql_alchemy_max_overflow = 10
sql_alchemy_pool_pre_ping = True        # Essential with PgBouncer
```

---

## Issue #10: Scheduler Performance Degradation Over Time

**Symptoms:**
- Scheduling latency slowly increases week over week
- Scheduler loop time grows from 2s to 30s+
- Database queries become slower
- More and more tasks in `scheduled` state

**Root Cause:**
- `task_instance` table grows unbounded (millions of rows)
- `dag_run` table accumulates historical runs
- `xcom` table bloated with task outputs
- Missing database indexes on query patterns
- No regular VACUUM on PostgreSQL

**Fix:**
```bash
# Airflow 2.x: built-in cleanup
airflow db clean --clean-before-timestamp "2024-01-01" --tables dag_run,task_instance,log,xcom,task_fail

# Schedule this as a DAG!
```

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

with DAG(
    'maintenance_db_cleanup',
    schedule='0 3 * * SUN',  # Weekly Sunday 3 AM
    catchup=False,
) as dag:
    
    cleanup_old_data = BashOperator(
        task_id='cleanup_metadata',
        bash_command="""
            airflow db clean \
                --clean-before-timestamp "$(date -d '-90 days' +%Y-%m-%d)" \
                --tables dag_run,task_instance,log,xcom,task_fail,rendered_task_instance_fields \
                --yes
        """,
    )
    
    vacuum_db = BashOperator(
        task_id='vacuum_analyze',
        bash_command="""
            PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d airflow -c "
                VACUUM ANALYZE task_instance;
                VACUUM ANALYZE dag_run;
                VACUUM ANALYZE xcom;
                VACUUM ANALYZE log;
            "
        """,
    )
    
    cleanup_old_data >> vacuum_db
```

---

## Issue #11: Scheduler Ignores DAG Timeout (dagrun_timeout Not Working)

**Symptoms:**
- DAG runs exceeding expected duration never get failed
- `dagrun_timeout` parameter seems ignored
- Resources tied up in stale runs

**Root Cause:**
- `dagrun_timeout` only applies to **scheduled** runs, not manually triggered
- Timer starts at `execution_date`, not actual start time
- Misunderstanding: `dagrun_timeout` ≠ individual task timeout

**Fix:**
```python
with DAG(
    'my_dag',
    dagrun_timeout=timedelta(hours=6),          # Kills entire run after 6h
    # This applies to the DagRun not individual tasks
) as dag:
    
    # For individual task timeout:
    task = PythonOperator(
        task_id='heavy_task',
        execution_timeout=timedelta(hours=2),    # THIS is per-task timeout
        python_callable=my_function,
    )
```

```python
# Custom solution: watchdog DAG that kills stale runs
from airflow.models import DagRun
from airflow.utils.state import State

def kill_stale_runs(**context):
    """Kill any DagRun running longer than threshold."""
    from airflow.utils.session import provide_session
    from datetime import datetime, timedelta
    
    @provide_session
    def _kill(session=None):
        threshold = datetime.utcnow() - timedelta(hours=8)
        stale_runs = session.query(DagRun).filter(
            DagRun.state == State.RUNNING,
            DagRun.start_date < threshold
        ).all()
        
        for run in stale_runs:
            run.set_state(State.FAILED)
            print(f"Killed stale run: {run.dag_id} / {run.run_id}")
    
    _kill()
```

---

## Issue #12: DAG Serialization Mismatch (Scheduler vs Worker See Different DAGs)

**Symptoms:**
- Worker executes old version of task code
- Task parameters don't match what's shown in UI
- Import errors on workers but not scheduler
- Inconsistent behavior between runs

**Root Cause:**
- GitSync out of sync between scheduler and worker pods
- DAG serialization cache stale
- Workers have different Python packages than scheduler
- Docker image version mismatch between components

**Fix:**
```yaml
# Ensure ALL components use same Git revision
# In Helm values.yaml:
dags:
  gitSync:
    enabled: true
    repo: git@github.com:company/airflow-dags.git
    branch: main
    rev: HEAD
    depth: 1
    maxFailures: 3
    subPath: "dags"
    wait: 30                    # Sync every 30 seconds
    # ALL pods (scheduler, worker, webserver) get same sidecar
```

```ini
# Force re-read from DB rather than local file
[core]
store_serialized_dags = True           # Store DAGs in DB (required for scale)
min_serialized_dag_update_interval = 30  # Refresh every 30s
min_serialized_dag_fetch_interval = 10   # Workers fetch from DB
```

---

## Issue #13: Scheduler Creating Runs for Paused DAGs

**Symptoms:**
- Paused DAGs still creating DagRuns
- DagRuns created but tasks immediately skipped
- Wasted scheduler cycles

**Root Cause:**
- Race condition between pause action and scheduler loop
- Scheduler already queued the DagRun creation before pause
- Bug in older Airflow versions (pre-2.5)

**Fix:**
```ini
[scheduler]
use_job_schedule = True          # Respect is_paused flag in scheduling loop
```

```bash
# Clear unwanted runs for paused DAG
airflow dags pause my_dag_id
airflow dags delete my_dag_id    # Remove all runs
# Or selectively:
airflow tasks clear my_dag_id -s 2024-06-01 -e 2024-06-02
```

---

## Issue #14: DAG Processor Timeout on Complex DAGs

**Symptoms:**
- Specific DAG never appears in UI
- `dag_file_processor_timeout` errors in scheduler logs
- Complex DAG file with 500+ tasks takes too long to parse

**Root Cause:**
- DAG file has O(n²) or worse complexity in task creation
- Circular imports taking seconds to resolve
- Dynamic DAG generation doing expensive computation

**Fix:**
```ini
[scheduler]
dag_file_processor_timeout = 120        # Increase from default 50s
dagbag_import_timeout = 60              # Per-file import timeout
```

```python
# BAD: O(n²) task dependency setting
tasks = [PythonOperator(task_id=f'task_{i}', ...) for i in range(500)]
for i in range(len(tasks)):
    for j in range(i+1, len(tasks)):
        tasks[i] >> tasks[j]  # Creates n*(n-1)/2 edges!

# GOOD: Linear chain or fan-out/fan-in
tasks = [PythonOperator(task_id=f'task_{i}', ...) for i in range(500)]
# Chain: t1 >> t2 >> t3 ... (linear)
from airflow.models.baseoperator import chain
chain(*tasks)

# Or fan-out/fan-in pattern
start >> tasks >> end  # Parallel execution
```

---

## Issue #15: Scheduler Not Respecting Priority Weight

**Symptoms:**
- High priority tasks not scheduled before low priority ones
- `priority_weight` seems to have no effect
- Critical pipelines starved by bulk pipelines

**Root Cause:**
- Priority only applies WITHIN the same pool
- Different pools have independent queues
- `weight_rule` not set correctly
- All tasks have same default priority (1)

**Fix:**
```python
# Priority ONLY works within same pool
critical_task = PythonOperator(
    task_id='critical_report',
    priority_weight=100,            # Higher = more priority
    weight_rule='absolute',         # Don't inherit from downstream
    pool='shared_pool',             # MUST be same pool as other tasks
    queue='priority',               # Route to dedicated priority queue
    python_callable=critical_function,
)

bulk_task = PythonOperator(
    task_id='bulk_export',
    priority_weight=1,              # Low priority
    pool='shared_pool',             # Same pool!
    queue='default',
    python_callable=bulk_function,
)
```

```python
# weight_rule options:
# 'downstream' (default): weight = sum of all downstream weights
# 'upstream': weight = sum of all upstream weights  
# 'absolute': weight = just this task's priority_weight

# For critical pipelines, set at DAG level:
with DAG('critical_pipeline',
         default_args={'priority_weight': 50, 'weight_rule': 'absolute'}
) as dag:
    pass
```

---

## Summary: Scheduler Issue Prevention Checklist

```
[ ] Deploy 2-3 HA schedulers (never single scheduler in prod)
[ ] Set parsing_processes = 2× CPU cores per scheduler
[ ] Set min_file_process_interval >= 60 seconds
[ ] Use PgBouncer for metadata DB connections
[ ] Schedule weekly metadata DB cleanup DAG
[ ] CI/CD validates DAG imports before deploy
[ ] Monitor: heartbeat, parse_time, import_errors, schedule_delay
[ ] Set dagrun_timeout AND execution_timeout on all DAGs
[ ] Use catchup=False unless explicitly needed
[ ] Avoid heavy imports at DAG file top level
[ ] Keep module-level DAG code lightweight (<1s parse time)
[ ] Set max_active_runs to prevent backfill storms
[ ] Configure zombie detection threshold appropriately
[ ] Use proper weight_rule for priority scheduling
[ ] Regular PostgreSQL VACUUM ANALYZE on metadata tables
```
