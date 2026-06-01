# Production Issues 31-45: Database & Metadata Issues

---

## Issue #31: Metadata Database Disk Full

**Symptoms:**
- All Airflow components crash simultaneously
- `DiskFull` errors in PostgreSQL logs
- No new task instances can be created
- UI completely unresponsive
- Catastrophic: entire platform halted

**Root Cause:**
- `task_instance` table grows 500K+ rows/day, never cleaned
- `log` table stores task execution logs indefinitely
- `xcom` table bloated with large return values
- WAL (Write-Ahead Log) files not cleaned up (replication lag)
- No alert on disk usage trending toward full

**Detection:**
```promql
# Alert at 80% disk usage
(pg_database_size_bytes{datname="airflow"} / pg_tablespace_size_bytes) > 0.80
```

**Fix:**
```python
# Automated cleanup DAG - MUST HAVE in production
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

with DAG(
    'system_metadata_cleanup',
    schedule='0 2 * * *',             # Daily 2 AM
    catchup=False,
    tags=['system', 'maintenance'],
    max_active_runs=1,
) as dag:
    
    # Clean task instances older than 90 days
    clean_task_instances = BashOperator(
        task_id='clean_task_instances',
        bash_command="""
            airflow db clean \
                --clean-before-timestamp "$(date -d '-90 days' +%Y-%m-%dT00:00:00+00:00)" \
                --tables task_instance,dag_run,task_fail,rendered_task_instance_fields \
                --yes
        """,
    )
    
    # Clean XCom older than 30 days
    clean_xcom = BashOperator(
        task_id='clean_xcom',
        bash_command="""
            airflow db clean \
                --clean-before-timestamp "$(date -d '-30 days' +%Y-%m-%dT00:00:00+00:00)" \
                --tables xcom \
                --yes
        """,
    )
    
    # Clean logs older than 60 days
    clean_logs = BashOperator(
        task_id='clean_logs',
        bash_command="""
            airflow db clean \
                --clean-before-timestamp "$(date -d '-60 days' +%Y-%m-%dT00:00:00+00:00)" \
                --tables log \
                --yes
        """,
    )
    
    # Vacuum and analyze (reclaim disk space)
    vacuum = BashOperator(
        task_id='vacuum_analyze',
        bash_command="""
            PGPASSWORD=${METADATA_DB_PASSWORD} psql \
                -h ${METADATA_DB_HOST} \
                -U ${METADATA_DB_USER} \
                -d airflow \
                -c "VACUUM (VERBOSE, ANALYZE) task_instance; VACUUM (VERBOSE, ANALYZE) dag_run; VACUUM (VERBOSE, ANALYZE) xcom;"
        """,
    )
    
    [clean_task_instances, clean_xcom, clean_logs] >> vacuum
```

```sql
-- Manual emergency: identify largest tables
SELECT schemaname, relname, 
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
       n_live_tup AS row_count
FROM pg_stat_user_tables 
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;

-- Emergency: truncate log table if critical
TRUNCATE TABLE log;  -- Nuclear option, loses audit trail
```

---

## Issue #32: Metadata DB Connection Pool Exhausted

**Symptoms:**
- `QueuePool limit overflow` errors
- `TimeoutError: QueuePool limit of X overflow Y reached`
- Intermittent task failures across all DAGs
- Scheduler and webserver competing for connections

**Root Cause:**
- Connection formula: (schedulers × pool) + (workers × pool) + (webservers × pool) > DB max_connections
- No PgBouncer for connection multiplexing
- Connection leak from unclosed sessions
- Long-running transactions holding connections

**Fix:**
```
# Connection math (WITHOUT PgBouncer):
3 schedulers × 10 = 30
3 webservers × 5  = 15
50 workers × 5    = 250
2 triggerers × 5  = 10
TOTAL: 305 connections needed!

PostgreSQL default max_connections = 100 → FAILURE

# WITH PgBouncer (transaction mode):
PgBouncer handles 500+ client connections
Opens only 30-50 actual DB connections
Multiplexes based on transaction boundaries
```

```ini
# PgBouncer configuration
[databases]
airflow = host=rds-prod.xxx.rds.amazonaws.com port=5432 dbname=airflow

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction              # MUST be transaction for Airflow
max_client_conn = 600
default_pool_size = 30
reserve_pool_size = 10
reserve_pool_timeout = 5
max_db_connections = 50              # Actual connections to PostgreSQL
server_lifetime = 3600
server_idle_timeout = 600
log_connections = 0
log_disconnections = 0
```

```ini
# airflow.cfg - point ALL components to PgBouncer
[database]
sql_alchemy_conn = postgresql://airflow:pass@pgbouncer-service:6432/airflow
sql_alchemy_pool_enabled = True
sql_alchemy_pool_size = 5            # Small per-process pool (PgBouncer handles multiplexing)
sql_alchemy_max_overflow = 5
sql_alchemy_pool_recycle = 1800      # Recycle connections every 30min
sql_alchemy_pool_pre_ping = True     # Verify connection before use (essential with PgBouncer)
```

---

## Issue #33: Metadata DB Deadlocks During High Throughput

**Symptoms:**
- `deadlock detected` errors in PostgreSQL logs
- Tasks intermittently failing with database errors
- Scheduler retrying operations repeatedly
- Happens during peak scheduling (hundreds of tasks state change simultaneously)

**Root Cause:**
- Multiple schedulers updating same DagRun row
- Task instances state transitions creating lock contention
- Long-running UI queries blocking scheduler writes
- Index scans causing page-level locks

**Fix:**
```sql
-- Check for deadlocks
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

```sql
-- PostgreSQL deadlock prevention settings
ALTER SYSTEM SET deadlock_timeout = '5s';        -- Detect faster
ALTER SYSTEM SET lock_timeout = '30s';           -- Don't wait forever
ALTER SYSTEM SET statement_timeout = '300s';     -- Kill long queries
ALTER SYSTEM SET idle_in_transaction_session_timeout = '300s';
SELECT pg_reload_conf();
```

```ini
# Airflow side: reduce contention
[scheduler]
max_tis_per_query = 128                          # Smaller batches = less lock time
schedule_after_task_execution = False            # Don't immediately re-schedule
```

---

## Issue #34: XCom Table Bloated (GB+ in Size)

**Symptoms:**
- XCom table consuming gigabytes of disk
- Queries on xcom table slow (impacts UI)
- Task result rendering in UI times out
- `airflow db clean` takes hours on xcom table

**Root Cause:**
- Tasks storing large data in XCom (DataFrames, large dicts)
- No automatic XCom cleanup
- XCom stored in metadata DB (not designed for large objects)
- Dynamic task mapping creating thousands of XCom entries per run

**Fix:**
```python
# BAD: Storing large data in XCom
@task
def extract():
    df = pd.read_parquet('s3://bucket/large_file.parquet')
    return df.to_dict()  # Could be 100MB+ in XCom table!

# GOOD: Store in S3, pass reference via XCom
@task
def extract():
    df = pd.read_parquet('s3://bucket/large_file.parquet')
    output_path = f's3://bucket/tmp/{{{{ ds }}}}/extracted.parquet'
    df.to_parquet(output_path)
    return output_path  # Only store the path (< 100 bytes)

@task
def transform(path: str):
    df = pd.read_parquet(path)  # Read from S3
    # ...
```

```python
# Use custom XCom backend for automatic S3 storage
# See Issue #28 for S3XComBackend implementation
```

```ini
# Set max XCom size to prevent accidents
[core]
max_xcom_size = 49344    # ~48KB max (Airflow 2.7+)
# Tasks exceeding this will ERROR instead of bloating DB
```

---

## Issue #35: Metadata DB Slow Queries Blocking Scheduler

**Symptoms:**
- Scheduler loop time > 30 seconds
- UI extremely slow (10+ second page loads)
- `pg_stat_activity` shows long-running queries from Airflow
- Tasks scheduling delayed by minutes

**Root Cause:**
- Missing indexes on frequently queried columns
- Full table scans on `task_instance` (millions of rows)
- UI queries (grid view, gantt chart) competing with scheduler
- No read replica for UI traffic

**Fix:**
```sql
-- Essential indexes for Airflow metadata performance
-- (Most are created by default, verify they exist)

-- task_instance performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ti_state_dag ON task_instance(state, dag_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ti_pool_state ON task_instance(pool, state);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ti_dag_run ON task_instance(dag_id, run_id, task_id);

-- dag_run performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dr_dag_state ON dag_run(dag_id, state);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dr_execution_date ON dag_run(dag_id, execution_date);

-- xcom cleanup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_xcom_dag_run ON xcom(dag_id, run_id);
```

```ini
# Use read replica for webserver (Airflow 2.7+)
[webserver]
# Point webserver to read replica for non-write queries
session_backend = database

[database]
# Primary for scheduler/workers
sql_alchemy_conn = postgresql://airflow:pass@pgbouncer:6432/airflow

# If supported: separate webserver DB connection (via custom config)
```

```sql
-- Identify slow queries
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
WHERE query LIKE '%task_instance%'
ORDER BY mean_time DESC
LIMIT 10;
```

---

## Issue #36: Database Migration Failure During Airflow Upgrade

**Symptoms:**
- `airflow db upgrade` fails mid-migration
- Airflow stuck in broken state (can't start, can't rollback)
- Schema partially migrated
- Alembic version table shows incomplete state

**Root Cause:**
- Large table migration timing out
- Concurrent access during migration (should be maintenance window)
- Insufficient disk space for ALTER TABLE operations
- Foreign key constraints blocking column changes

**Fix:**
```bash
# ALWAYS before upgrade:
# 1. Take full database backup
pg_dump -h $DB_HOST -U $DB_USER airflow > airflow_backup_$(date +%Y%m%d).sql

# 2. Check current Alembic state
airflow db check-migrations

# 3. Run migration with extended timeout
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql://..."
airflow db upgrade --to-version 2.7.0

# If migration fails mid-way:
# 4. Check Alembic version
psql -h $DB_HOST -d airflow -c "SELECT * FROM alembic_version;"

# 5. If stuck, manually fix alembic_version to last successful migration
# Then re-run: airflow db upgrade
```

```bash
# Safe upgrade procedure:
#!/bin/bash
set -e

echo "1. Pausing all DAGs..."
airflow dags pause --all

echo "2. Waiting for running tasks to complete..."
while [ $(airflow tasks list-running | wc -l) -gt 0 ]; do
    echo "Tasks still running, waiting..."
    sleep 30
done

echo "3. Backing up database..."
pg_dump -Fc -h $DB_HOST -U airflow airflow > backup_$(date +%Y%m%d_%H%M%S).dump

echo "4. Running database migration..."
airflow db upgrade

echo "5. Verifying migration..."
airflow db check-migrations

echo "6. Restarting Airflow components..."
kubectl rollout restart deployment -l app=airflow -n airflow

echo "7. Unpausing DAGs..."
airflow dags unpause --all

echo "Migration complete!"
```

---

## Issue #37: Task Instance Table Partition Needed

**Symptoms:**
- `task_instance` table has 100M+ rows
- Queries on recent data scan entire table
- Index maintenance takes hours
- VACUUM runs taking 30+ minutes

**Root Cause:**
- No partitioning strategy on task_instance table
- All historical data in same table as active data
- PostgreSQL autovacuum can't keep up with dead tuples

**Fix:**
```sql
-- Partition task_instance by month (PostgreSQL 12+)
-- WARNING: This requires downtime and data migration!

-- Step 1: Create new partitioned table
CREATE TABLE task_instance_partitioned (
    LIKE task_instance INCLUDING ALL
) PARTITION BY RANGE (start_date);

-- Step 2: Create partitions
CREATE TABLE task_instance_y2024m01 PARTITION OF task_instance_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE task_instance_y2024m02 PARTITION OF task_instance_partitioned
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... create for each month

-- Step 3: Create default partition for unexpected dates
CREATE TABLE task_instance_default PARTITION OF task_instance_partitioned DEFAULT;

-- Step 4: Migrate data (during maintenance window)
INSERT INTO task_instance_partitioned SELECT * FROM task_instance;

-- Step 5: Swap tables
ALTER TABLE task_instance RENAME TO task_instance_old;
ALTER TABLE task_instance_partitioned RENAME TO task_instance;

-- Step 6: Auto-create future partitions
-- Use pg_partman extension or a scheduled job
```

---

## Issue #38: DAG Serialization Cache Stale

**Symptoms:**
- UI shows old DAG structure
- Workers executing with outdated task definitions
- Schedule changes not taking effect
- Appears random: sometimes works, sometimes stale

**Root Cause:**
- `min_serialized_dag_update_interval` too long
- Serialized DAGs in DB not refreshed
- Worker caching serialized DAG longer than scheduler updates
- Multiple scheduler instances updating at different rates

**Fix:**
```ini
[core]
store_serialized_dags = True                    # Required for scale
min_serialized_dag_update_interval = 30         # Update DB every 30s
min_serialized_dag_fetch_interval = 10          # Workers fetch every 10s
compress_serialized_dags = True                 # Reduce DB storage

[scheduler]
min_file_process_interval = 30                  # Re-parse files every 30s
# These two should be aligned:
# parse interval >= serialization update interval
```

---

## Issue #39: Rendered Template Fields Table Growing Unbounded

**Symptoms:**
- `rendered_task_instance_fields` table consuming 50%+ of DB disk
- DB backup taking longer and longer
- Not cleaned by standard maintenance

**Root Cause:**
- Every task instance stores its rendered Jinja templates
- At 500K task instances/day, this accumulates fast
- Useful for debugging but needs cleanup

**Fix:**
```ini
[core]
max_num_rendered_ti_fields_per_task = 30     # Keep only last 30 renders per task
# Default is 0 (unlimited!)
```

```python
# Add to cleanup DAG:
clean_rendered = BashOperator(
    task_id='clean_rendered_fields',
    bash_command="""
        airflow db clean \
            --clean-before-timestamp "$(date -d '-30 days' +%Y-%m-%dT00:00:00+00:00)" \
            --tables rendered_task_instance_fields \
            --yes
    """,
)
```

---

## Issue #40: Database Failover Causes All Tasks to Fail

**Symptoms:**
- RDS failover event (Multi-AZ)
- All running tasks fail with `OperationalError: connection reset`
- Scheduler stops for 30-60 seconds
- Some tasks need manual re-run after recovery

**Root Cause:**
- RDS failover drops all existing TCP connections
- PgBouncer/SQLAlchemy don't detect dropped connections immediately
- Task mid-execution loses ability to update state
- Worker heartbeat fails → zombie detection → task killed

**Fix:**
```ini
[database]
sql_alchemy_pool_pre_ping = True         # Test connection before use (CRITICAL)
sql_alchemy_pool_recycle = 300           # Recycle connections every 5 min
sql_alchemy_connect_args = {"connect_timeout": 10, "options": "-c statement_timeout=300000"}
```

```ini
# PgBouncer: detect dead connections faster
[pgbouncer]
server_check_delay = 5                   # Check server health every 5s
server_check_query = SELECT 1
server_connect_timeout = 5
server_login_retry = 3
tcp_keepalive = 1
tcp_keepidle = 30
tcp_keepintvl = 10
tcp_keepcnt = 3
```

```python
# Tasks: implement checkpoint/resume for long operations
def long_running_task(**context):
    """Task that can resume after DB failover."""
    checkpoint_key = f"{context['dag'].dag_id}_{context['ts']}_checkpoint"
    
    # Check for existing checkpoint
    last_processed = Variable.get(checkpoint_key, default_var=0, deserialize_json=True)
    
    for batch_num in range(last_processed, total_batches):
        process_batch(batch_num)
        # Save checkpoint every 100 batches
        if batch_num % 100 == 0:
            Variable.set(checkpoint_key, batch_num, serialize_json=True)
    
    # Cleanup checkpoint on success
    Variable.delete(checkpoint_key)
```

---

## Issue #41: XCom Deserialization Failures After Python Upgrade

**Symptoms:**
- Tasks failing with `pickle.UnpicklingError`
- XCom values from before upgrade unreadable
- Custom objects stored in XCom can't be deserialized
- Cascading failures in DAGs relying on historical XCom

**Root Cause:**
- XCom default serialization uses pickle (Python version specific)
- Python 3.9 → 3.11 changes pickle protocol
- Custom classes stored in XCom may have changed
- JSON vs Pickle serialization mismatch

**Fix:**
```ini
# Force JSON serialization (safe across Python versions)
[core]
enable_xcom_pickling = False             # Use JSON only (recommended)
# Tasks must return JSON-serializable values (str, int, dict, list)
```

```python
# BAD: Storing custom objects
@task
def extract():
    return MyCustomClass(data=results)  # Pickle-dependent!

# GOOD: Store JSON-serializable data
@task
def extract():
    return {"data": results, "count": len(results), "timestamp": str(datetime.now())}
```

---

## Issue #42: Variable/Connection Encryption Key Lost

**Symptoms:**
- All Variable.get() calls return garbled data
- Connections show encrypted values in UI
- `InvalidFernetToken` errors everywhere
- After key rotation or environment rebuild

**Root Cause:**
- FERNET_KEY changed or lost between environments
- Secret encrypted with old key, decrypted with new key
- Key stored in environment variable that got rotated
- Multi-environment setup with different keys

**Fix:**
```bash
# Fernet key management
# Generate new key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Key rotation (keep old key for decryption):
# AIRFLOW__CORE__FERNET_KEY = "new_key,old_key"  # Comma-separated: first for encrypt, rest for decrypt
export AIRFLOW__CORE__FERNET_KEY="newkey123==,oldkey456=="

# After rotation, re-encrypt all values with new key:
airflow rotate-fernet-key
```

```yaml
# Store Fernet key in Kubernetes secret (never in values.yaml)
apiVersion: v1
kind: Secret
metadata:
  name: airflow-fernet-key
  namespace: airflow
type: Opaque
data:
  fernet-key: <base64-encoded-key>
---
# Reference in Helm values:
fernetKeySecretName: airflow-fernet-key
```

---

## Issue #43: Metadata DB Replication Lag Causing Stale Reads

**Symptoms:**
- UI shows task as "running" but it completed minutes ago
- Webserver reads from replica that's behind primary
- Scheduler decisions based on stale state
- Task dependencies incorrectly evaluated

**Root Cause:**
- Read replica used for UI has replication lag > 5 seconds
- Heavy write load causing replica to fall behind
- Network issues between primary and replica
- Replica under-provisioned (can't apply WAL fast enough)

**Fix:**
```sql
-- Monitor replication lag
SELECT client_addr, state, 
       pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn) AS sent_lag_bytes,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag_bytes
FROM pg_stat_replication;
```

```promql
# Alert on replication lag
pg_replication_lag_seconds > 5
```

```ini
# Solution: Scheduler and workers MUST use primary
# Only webserver can use read replica (for non-critical UI reads)
[database]
sql_alchemy_conn = postgresql://airflow:pass@primary:5432/airflow

# Webserver can optionally use replica for heavy queries
# (Requires custom configuration or proxy-based routing)
```

---

## Issue #44: Metadata DB CPU Spikes During DAG Grid View

**Symptoms:**
- Opening DAG Grid View in UI causes DB CPU to spike 100%
- Other users experience slowness
- Scheduler scheduling latency increases
- Timeout errors for the requesting user

**Root Cause:**
- Grid View queries ALL task instances for the DAG (potentially millions)
- Complex JOINs across task_instance, dag_run, rendered_task_instance_fields
- No pagination in older Airflow versions
- Missing composite index for the specific query pattern

**Fix:**
```ini
# Limit UI query scope
[webserver]
default_dag_run_display_number = 25     # Show only last 25 runs (default: 25)
page_size = 100                         # Pagination limit
```

```sql
-- Create index specifically for Grid View queries
CREATE INDEX CONCURRENTLY idx_ti_grid_view 
ON task_instance(dag_id, run_id, task_id, state, start_date, end_date);
```

```yaml
# Separate read replica for webserver
# Route webserver DB traffic to replica using PgBouncer routing
# Primary handles scheduler/worker writes
# Replica handles webserver reads
```

---

## Issue #45: Database Backup Restore Causes Duplicate DAG Runs

**Symptoms:**
- After restoring from backup, scheduler creates duplicate DagRuns
- Tasks executed twice (dangerous for non-idempotent tasks)
- Duplicate data written to warehouse

**Root Cause:**
- Backup was taken at time T, restore puts DB at state T
- Scheduler starts and sees "missing" DagRuns between T and now
- With catchup=True, all missed intervals get created
- Even with catchup=False, the current interval gets a new run

**Fix:**
```bash
# After database restore procedure:
#!/bin/bash

echo "1. Restore database from backup..."
pg_restore -h $DB_HOST -U airflow -d airflow backup.dump

echo "2. CRITICAL: Pause all DAGs before starting scheduler"
# Start webserver only (not scheduler)
kubectl scale deployment airflow-scheduler --replicas=0 -n airflow
kubectl scale deployment airflow-webserver --replicas=1 -n airflow

echo "3. Verify state and pause DAGs via API..."
curl -X PATCH "http://airflow:8080/api/v1/dags" \
  -H "Content-Type: application/json" \
  -d '{"is_paused": true}'

echo "4. Start scheduler..."
kubectl scale deployment airflow-scheduler --replicas=3 -n airflow

echo "5. Manually review and unpause DAGs one by one..."
# Verify each DAG's last run state matches expectations
```

---

## Summary: Database Issue Prevention Checklist

```
[ ] Deploy PgBouncer in transaction mode (MANDATORY at scale)
[ ] Schedule daily metadata cleanup DAG
[ ] Set max_num_rendered_ti_fields_per_task = 30
[ ] Enable sql_alchemy_pool_pre_ping = True
[ ] Configure automated RDS snapshots (every 6h)
[ ] Monitor table sizes and disk usage with alerts at 70%
[ ] Run VACUUM ANALYZE weekly on large tables
[ ] Create essential indexes for task_instance queries
[ ] Use JSON XCom serialization (enable_xcom_pickling = False)
[ ] Store Fernet key in secrets management (K8s Secret / Vault)
[ ] Plan for table partitioning when task_instance > 50M rows
[ ] Use read replicas for webserver traffic
[ ] Set statement_timeout and idle_in_transaction_session_timeout
[ ] Test database failover procedure quarterly
[ ] Never store large data in XCom (use S3 paths instead)
```
