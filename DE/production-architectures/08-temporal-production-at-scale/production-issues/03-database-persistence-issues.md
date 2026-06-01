# Database & Persistence Production Issues (#31 - #45)

## Issue #31: Cassandra Partition Hotspot [CRITICAL]

### Symptoms
- Specific Cassandra nodes at 100% CPU while others idle
- Read/write latency spikes on specific namespaces
- `temporal_persistence_latency` p99 > 1s intermittently
- Cassandra `ReadTimeout` and `WriteTimeout` exceptions

### Root Cause
Temporal's partition key in Cassandra includes `shard_id` and `namespace_id`.
Hotspots occur when:
- Too few history shards for the workload (default 4, need 512+ at scale)
- One namespace has disproportionate traffic
- Burst of workflow starts all hash to same partition
- Cassandra token range imbalance

### Impact
- **Business**: All workflows on hot partition experience delays
- **System**: Cassandra node failure risk from overload
- **Scale**: At 100K workflows/sec, one hot shard = 25K/sec on one node

### Detection
```promql
# Per-shard latency variance
stddev(temporal_persistence_latency_seconds{operation="CreateWorkflowExecution"}) by (shard_id) > 0.5

# Cassandra node load imbalance
max(cassandra_node_cpu_usage) / avg(cassandra_node_cpu_usage) > 2
```

### Resolution
```yaml
# 1. Increase history shard count (requires cluster restart)
# temporal-server config:
persistence:
  numHistoryShards: 512  # Default is 4, production should be 128-2048

# 2. Cassandra compaction strategy for temporal tables
ALTER TABLE executions WITH compaction = {
  'class': 'LeveledCompactionStrategy',
  'sstable_size_in_mb': 160
};

# 3. Add Cassandra nodes to distribute token ranges
nodetool status  # Check current distribution
nodetool repair  # After adding nodes

# 4. Adjust Cassandra read/write consistency
persistence:
  cassandra:
    consistency: LOCAL_QUORUM  # Balance consistency and availability
    serialConsistency: LOCAL_SERIAL
```

**Shard count selection formula:**
```
Optimal shards = max(
    total_workflows_per_second / 100,  # ~100 TPS per shard
    num_history_pods * 16,             # 16 shards per history pod minimum
    512                                # Minimum for production
)
```

### Prevention
- Start with 512+ shards for any production workload
- Cannot change shard count without data migration (plan ahead)
- Monitor per-shard metrics in Cassandra
- Use `NetworkTopologyStrategy` with RF=3 for multi-DC
- Regular `nodetool repair` for anti-entropy

---

## Issue #32: PostgreSQL Connection Pool Exhaustion [CRITICAL]

### Symptoms
- `connection pool exhausted` errors in Temporal server logs
- All workflow operations fail simultaneously
- Server health check passes but no requests processed
- PgBouncer/connection pooler saturated

### Root Cause
- History service creates many concurrent DB connections
- Each workflow task requires DB read + write
- Connection pool sized for normal load, spike overwhelms it
- Long-running transactions hold connections
- PgBouncer `max_client_conn` too low

### Impact
- **Business**: Complete service outage - no workflows can progress
- **System**: Cascading failure as all services waiting on Temporal
- **Scale**: At 50K workflows/sec, need 1000+ DB connections

### Detection
```promql
# Connection pool utilization
pg_stat_activity_count / pg_settings_max_connections > 0.85

# Connection wait time
temporal_persistence_latency_seconds{operation="*", quantile="0.99"} > 2
  AND temporal_persistence_requests_total rate unchanged
```

### Resolution
```ini
# PgBouncer configuration for Temporal
[databases]
temporal = host=pg-primary port=5432 dbname=temporal pool_size=100
temporal_visibility = host=pg-replica port=5432 dbname=temporal_visibility pool_size=50

[pgbouncer]
max_client_conn = 2000
default_pool_size = 100
reserve_pool_size = 20
reserve_pool_timeout = 3
server_idle_timeout = 300
server_lifetime = 3600
pool_mode = transaction  # CRITICAL: Use transaction mode for Temporal
```

```yaml
# Temporal server persistence config
persistence:
  defaultStore: postgres-default
  visibilityStore: postgres-visibility
  datastores:
    postgres-default:
      sql:
        pluginName: postgres
        databaseName: temporal
        connectAddr: pgbouncer:6432
        maxConns: 100
        maxIdleConns: 20
        maxConnLifetime: 1h
        connectTimeout: 10s
    postgres-visibility:
      sql:
        pluginName: postgres
        databaseName: temporal_visibility
        connectAddr: pgbouncer-visibility:6432
        maxConns: 50
        maxIdleConns: 10
```

```sql
-- PostgreSQL tuning for Temporal workload
ALTER SYSTEM SET max_connections = 500;
ALTER SYSTEM SET shared_buffers = '8GB';          -- 25% of RAM
ALTER SYSTEM SET effective_cache_size = '24GB';   -- 75% of RAM  
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM SET maintenance_work_mem = '2GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '64MB';
ALTER SYSTEM SET random_page_cost = 1.1;          -- For SSD storage
ALTER SYSTEM SET effective_io_concurrency = 200;   -- For SSD storage
ALTER SYSTEM SET idle_in_transaction_session_timeout = '30s';
```

### Prevention
- PgBouncer in `transaction` mode (required for Temporal's connection patterns)
- Connection pool monitoring with alerts at 80% utilization
- Separate pools for execution store vs visibility store
- Read replicas for visibility queries
- Auto-scaling connection pool (or PgBouncer) based on load

---

## Issue #33: Database Deadlocks on Workflow Operations [HIGH]

### Symptoms
- `deadlock detected` errors in PostgreSQL/MySQL logs
- Workflow operations fail intermittently
- Retry succeeds (deadlock resolved by DB)
- Elevated error rate during high concurrency

### Root Cause
Temporal's persistence layer performs multi-row updates:
- Workflow update + task creation in same transaction
- Two workflows signaling each other simultaneously
- Timer tasks and workflow tasks competing for same rows
- Visibility updates conflicting with execution updates

### Impact
- **Business**: Intermittent failures, 1-5% error rate under load
- **System**: Retry amplification, slight latency increase
- **Scale**: Deadlock rate increases non-linearly with concurrency

### Detection
```promql
# Deadlock rate
rate(temporal_persistence_errors_total{error_type="deadlock"}[5m]) > 1

# PostgreSQL deadlock count
pg_stat_database_deadlocks > 0
```

### Resolution
```sql
-- PostgreSQL: Reduce deadlock likelihood
ALTER SYSTEM SET deadlock_timeout = '500ms';  -- Detect faster (default 1s)
ALTER SYSTEM SET lock_timeout = '5s';         -- Don't wait forever

-- Ensure proper indexes reduce lock scope
CREATE INDEX CONCURRENTLY idx_executions_namespace_wfid 
  ON executions(namespace_id, workflow_id) 
  WHERE close_status IS NULL;

CREATE INDEX CONCURRENTLY idx_timer_tasks_visibility_ts 
  ON timer_tasks(visibility_timestamp) 
  WHERE task_type = 'timer';
```

```yaml
# Temporal server retry configuration for deadlocks
persistence:
  sql:
    maxRetries: 3              # Retry deadlocked operations
    retryInitialInterval: 50ms
    retryMaxInterval: 500ms
```

### Prevention
- Use Cassandra instead of PostgreSQL at extreme scale (no deadlocks, eventual consistency)
- Proper indexing to minimize lock scope
- Temporal server handles deadlock retries internally
- Monitor deadlock rate as capacity signal (increasing = need more shards)
- Consider CockroachDB for serializable isolation without traditional deadlocks

---

## Issue #34: Database Storage Growth Unbounded [HIGH]

### Symptoms
- Disk usage growing 10-50GB/day
- Database performance degrading as tables grow
- Completed workflow histories consuming most storage
- Query performance on large tables declining

### Root Cause
- Workflow execution histories not being cleaned up
- Retention period too long (default: 30 days, but storing 1M workflows/day = 30M records)
- Visibility records not archived
- Large payloads stored inline (not in blob storage)
- Dead workflows (terminated but not archived) accumulating

### Impact
- **Business**: Increasing infrastructure cost, performance degradation
- **System**: Database backup times increase, replica lag grows
- **Scale**: 10M workflows/day × 10KB avg × 30 days = 3TB

### Detection
```promql
# Storage growth rate
deriv(pg_database_size_bytes{datname="temporal"}[24h]) > 10000000000  # 10GB/day

# Table bloat
pg_stat_user_tables_n_dead_tup{relname="executions"} > 1000000
```

### Resolution
```yaml
# 1. Configure namespace retention (most important)
# Per namespace retention period
tctl namespace update --namespace production \
  --retention 7d  # Reduce from 30d to 7d for high-volume

tctl namespace update --namespace batch-jobs \
  --retention 3d  # Batch jobs: keep only 3 days

# 2. Enable archival for compliance (move to cheap storage)
archival:
  history:
    state: enabled
    enableRead: true
    URI: "s3://temporal-archival-prod/history"
  visibility:
    state: enabled
    enableRead: true
    URI: "s3://temporal-archival-prod/visibility"

# 3. Temporal server dynamic config
history.workflowExecutionRetentionTimeDays:
  - value: 7
    constraints:
      namespace: "default"
  - value: 3
    constraints:
      namespace: "batch-processing"
```

```sql
-- PostgreSQL maintenance
-- 1. Partition tables by time
CREATE TABLE executions_2024_q1 PARTITION OF executions
  FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');

-- 2. Aggressive autovacuum for high-churn tables
ALTER TABLE executions SET (
  autovacuum_vacuum_scale_factor = 0.01,    -- vacuum at 1% dead tuples
  autovacuum_analyze_scale_factor = 0.005,
  autovacuum_vacuum_cost_delay = 2
);

-- 3. Drop old partitions instead of DELETE (instant)
DROP TABLE executions_2023_q4;
```

### Prevention
- Set retention per namespace based on compliance needs
- Enable archival to S3/GCS for long-term storage (cheap, queryable)
- Partition execution tables by close_time
- Monitor storage growth rate and project capacity
- Regular VACUUM FULL during maintenance windows

---

## Issue #35: Visibility Store (Elasticsearch) Index Explosion [HIGH]

### Symptoms
- Elasticsearch cluster yellow/red status
- Shard count exceeds recommended limits
- Index creation failures
- Visibility queries timeout

### Root Cause
- One index per day without ILM (365 indices/year)
- Custom search attributes creating too many field mappings
- Index not rolling over (single growing index)
- Shard size > 50GB (recommended max)

### Impact
- **Business**: Cannot search/list workflows, dashboards broken
- **System**: Elasticsearch cluster degraded, high CPU/memory
- **Scale**: 1M workflows/day × 365 days = 365M documents

### Detection
```promql
# Cluster health
elasticsearch_cluster_health_status{color="red"} == 1

# Shard count
elasticsearch_cluster_health_number_of_shards > 1000
```

### Resolution
```json
// 1. Index template with ILM
PUT _index_template/temporal-visibility
{
  "index_patterns": ["temporal-visibility-*"],
  "template": {
    "settings": {
      "number_of_shards": 6,
      "number_of_replicas": 1,
      "index.lifecycle.name": "temporal-ilm-policy",
      "index.lifecycle.rollover_alias": "temporal-visibility",
      "index.mapping.total_fields.limit": 200,
      "index.refresh_interval": "5s"
    },
    "mappings": {
      "properties": {
        "WorkflowID": { "type": "keyword" },
        "WorkflowType": { "type": "keyword" },
        "StartTime": { "type": "date" },
        "CloseTime": { "type": "date" },
        "ExecutionStatus": { "type": "keyword" },
        "NamespaceID": { "type": "keyword" }
      }
    }
  }
}

// 2. ILM Policy
PUT _ilm/policy/temporal-ilm-policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "30GB",
            "max_age": "1d"
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "3d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "freeze": {},
          "set_priority": { "priority": 0 }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

### Prevention
- ILM policy from day one
- Limit custom search attributes (< 50 per namespace)
- Monitor shard count and size
- Use time-based indices with rollover
- Separate hot/warm/cold nodes in ES cluster

---

## Issue #36: Database Connection Pool Starvation During Spikes [CRITICAL]

### Symptoms
- Temporal frontend returns `ResourceExhausted` errors
- All history nodes report DB connection timeouts
- Matching service cannot dispatch tasks
- Complete cluster freeze during traffic spike

### Root Cause
Traffic spike exceeds connection pool capacity:
- Black Friday: 10x normal traffic
- Batch job start: 1M workflow starts in 1 minute
- All services competing for limited DB connections
- No backpressure - requests queue in memory until OOM

### Impact
- **Business**: Complete outage during critical business period
- **System**: May require full cluster restart to recover
- **Scale**: Normal: 5K workflows/sec, Spike: 50K/sec -> 10x connections needed

### Detection
```promql
# Connection wait time
temporal_persistence_latency_seconds{operation="AcquireConnection"} > 1

# Pool exhaustion
temporal_persistence_active_connections / temporal_persistence_max_connections > 0.95
```

### Resolution
```go
// Server-side: Connection pool with backpressure
// dynamic_config.yaml
frontend.rps:
  - value: 10000  # Hard cap on requests/sec to frontend
    constraints: {}

history.rps:
  - value: 5000   # Per-host history service RPS limit
    constraints: {}

// Client-side: Rate limit workflow starts
type RateLimitedStarter struct {
    client    client.Client
    limiter   *rate.Limiter
}

func (r *RateLimitedStarter) StartWorkflow(ctx context.Context, opts client.StartWorkflowOptions, wf interface{}, args ...interface{}) (client.WorkflowRun, error) {
    if err := r.limiter.Wait(ctx); err != nil {
        return nil, fmt.Errorf("rate limited: %w", err)
    }
    return r.client.ExecuteWorkflow(ctx, opts, wf, args...)
}

// Use token bucket: 5000 starts/sec with burst of 10000
starter := &RateLimitedStarter{
    client:  c,
    limiter: rate.NewLimiter(5000, 10000),
}
```

```yaml
# Pre-scale for known events
# CronJob to scale before Black Friday
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pre-scale-temporal
spec:
  schedule: "0 0 25 11 *"  # Nov 25 midnight
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: scaler
            command:
            - /bin/sh
            - -c
            - |
              kubectl scale deployment temporal-history --replicas=24
              kubectl scale deployment temporal-matching --replicas=16
              kubectl scale deployment temporal-frontend --replicas=12
              kubectl scale deployment temporal-worker-payment --replicas=100
```

### Prevention
- Rate limiting at frontend service (protect DB)
- Auto-scaling with aggressive scale-up policy
- Pre-scale for known traffic events
- Queue bursts in Kafka/SQS before Temporal (absorb spike)
- Connection pool monitoring with auto-scaling trigger

---

## Issue #37: Database Replication Lag Causing Stale Reads [HIGH]

### Symptoms
- Workflows report state inconsistencies
- Visibility queries show stale status
- Signal sent but workflow doesn't receive it
- "Workflow not found" immediately after creation

### Root Cause
When using read replicas for visibility:
- Write goes to primary
- Read goes to replica
- Lag between primary and replica = stale reads
- During high write load, lag can be seconds to minutes

### Impact
- **Business**: Customer sees wrong order status, support confusion
- **System**: Application logic makes wrong decisions on stale data
- **Scale**: At high write rates, lag increases non-linearly

### Detection
```promql
# Replication lag
pg_replication_lag_seconds > 5

# Stale read rate (application-level)
rate(temporal_visibility_stale_reads_total[5m]) > 10
```

### Resolution
```yaml
# 1. Route time-sensitive reads to primary
persistence:
  defaultStore: postgres-primary
  visibilityStore: postgres-replica  # Slight staleness OK for listing
  
  datastores:
    postgres-primary:
      sql:
        connectAddr: pg-primary:5432
    postgres-replica:
      sql:
        connectAddr: pg-replica:5432

# 2. For critical reads, use primary
# Temporal supports this via API:
# DescribeWorkflowExecution always reads from primary (execution store)
# ListWorkflowExecutions reads from visibility store (can be replica)
```

```go
// Application pattern: verify on primary if replica result is suspicious
func getWorkflowStatus(ctx context.Context, c client.Client, wfID string) (string, error) {
    // DescribeWorkflowExecution reads from primary (always fresh)
    desc, err := c.DescribeWorkflowExecution(ctx, wfID, "")
    if err != nil {
        return "", err
    }
    return desc.WorkflowExecutionInfo.Status.String(), nil
}
```

### Prevention
- Use `DescribeWorkflowExecution` for real-time status (reads primary)
- Accept eventual consistency for `ListWorkflowExecutions`
- Monitor replication lag with alerts
- Synchronous replication for critical namespaces (at cost of write latency)
- Application-level compensation for stale reads

---

## Issue #38: Cassandra Tombstone Accumulation [HIGH]

### Symptoms
- Cassandra read latency steadily increasing
- `TombstoneOverwhelmingException` in Cassandra logs
- Full GC pauses on Cassandra nodes
- Read timeout on specific partitions

### Root Cause
Temporal deletes completed workflow data after retention period.
Cassandra handles deletes as tombstones:
- Tombstones accumulate until compaction (gc_grace_seconds)
- Reads must scan through tombstones
- Partitions with many completed workflows = many tombstones
- Default `gc_grace_seconds` = 10 days (tombstones persist 10 days)

### Impact
- **Business**: Slow workflow operations, potential timeouts
- **System**: Cassandra stability at risk, heap pressure
- **Scale**: 1M workflow completions/day × 10 day gc_grace = 10M tombstones

### Detection
```bash
# Check tombstone count per read
nodetool cfstats temporal.executions | grep "tombstones"

# Monitor via JMX
cassandra_table_tombstones_scanned_per_read > 1000
```

### Resolution
```sql
-- Reduce gc_grace_seconds (only safe with repair running)
ALTER TABLE temporal.executions 
  WITH gc_grace_seconds = 86400;  -- 1 day (was 10 days)
  -- ONLY if running nodetool repair every < 24 hours

-- Use TimeWindowCompaction for timer/task tables
ALTER TABLE temporal.timer_tasks WITH compaction = {
  'class': 'TimeWindowCompactionStrategy',
  'compaction_window_unit': 'HOURS',
  'compaction_window_size': 1
};

-- Regular manual compaction on affected tables
nodetool compact temporal executions
```

```yaml
# Cassandra configuration tuning
# cassandra.yaml
tombstone_warn_threshold: 1000
tombstone_failure_threshold: 100000  # Fail reads with too many tombstones
gc_grace_seconds: 86400  # Reduce if repair runs frequently
compaction_throughput_mb_per_sec: 64  # Increase compaction speed
```

### Prevention
- Run `nodetool repair` at least weekly
- Reduce `gc_grace_seconds` with frequent repairs
- LeveledCompaction for execution tables
- TimeWindowCompaction for task/timer tables
- Monitor tombstone counts per read

---

## Issue #39: Database Schema Migration Failure [HIGH]

### Symptoms
- Temporal server fails to start after upgrade
- Schema version mismatch errors
- `SchemaVersionMismatch: expected X, got Y`
- Half-applied migration (partial columns/indexes)

### Root Cause
- Schema migration interrupted (pod killed during migration)
- Manual migration not run before server upgrade
- Multiple servers competing to run migration
- Incompatible schema for new Temporal version

### Impact
- **Business**: Complete outage during upgrade
- **System**: Cluster cannot start until schema fixed
- **Scale**: Affects entire cluster, all namespaces

### Detection
```bash
# Check current schema version
temporal-sql-tool --database temporal version

# Compare with expected
temporal-sql-tool --database temporal validate
```

### Resolution
```bash
# 1. Check current schema version
temporal-sql-tool \
  --plugin postgres \
  --endpoint pg-primary:5432 \
  --database temporal \
  --user temporal \
  --password $DB_PASSWORD \
  version

# 2. Run migration manually
temporal-sql-tool \
  --plugin postgres \
  --endpoint pg-primary:5432 \
  --database temporal \
  --user temporal \
  --password $DB_PASSWORD \
  update-schema --schema-dir ./schema/postgresql/v96/temporal/versioned

# 3. For visibility store
temporal-sql-tool \
  --plugin postgres \
  --endpoint pg-primary:5432 \
  --database temporal_visibility \
  --user temporal \
  --password $DB_PASSWORD \
  update-schema --schema-dir ./schema/postgresql/v96/visibility/versioned

# 4. If migration is stuck/partial, check schema_update_history table
psql -h pg-primary -U temporal -d temporal \
  -c "SELECT * FROM schema_update_history ORDER BY update_time DESC LIMIT 5;"
```

### Prevention
- Always run schema migration BEFORE server upgrade
- Use init containers to run migration:
```yaml
initContainers:
- name: schema-migration
  image: temporalio/admin-tools:1.24
  command: ['temporal-sql-tool', 'update-schema', '--schema-dir', '/etc/temporal/schema/postgresql/v96/temporal/versioned']
```
- Backup database before any migration
- Test migrations in staging with production data volume
- Schema migration lock (only one instance runs migration)

---

## Issue #40: Transfer Task Queue Backlog [HIGH]

### Symptoms
- `temporal_transfer_task_latency` growing steadily
- Workflow completions delayed despite activities completing
- Gap between activity completion and next workflow task
- History service transfer task processor falling behind

### Root Cause
Transfer tasks are internal tasks that move work between services:
- Activity complete -> transfer task -> schedule next workflow task
- Timer fires -> transfer task -> dispatch workflow task
- Transfer task processor is single-threaded per shard
- If processor is slow, all workflows on that shard are delayed

### Impact
- **Business**: Hidden latency between steps (workflow looks stuck between activities)
- **System**: Internal queue growth, memory pressure on history service
- **Scale**: Each shard processes transfers sequentially -> shard count = parallelism

### Detection
```promql
# Transfer task latency (time from creation to processing)
temporal_transfer_task_latency_seconds{quantile="0.99"} > 5

# Transfer task backlog
temporal_transfer_task_pending_count > 1000
```

### Resolution
```yaml
# 1. Increase transfer task processing rate
# dynamic_config.yaml
history.transferTaskMaxPollerCount:
  - value: 4  # Default 2, increase for high-throughput

history.transferProcessorMaxPollInterval:
  - value: 50ms  # Poll more frequently

history.transferProcessorUpdateAckInterval:
  - value: 100ms

# 2. Increase history shard count (more parallelism)
# numHistoryShards: 1024  # More shards = more parallel transfer processing

# 3. Scale history service
# More history pods = shards distributed across more processors
kubectl scale deployment temporal-history --replicas=12
```

### Prevention
- Adequate history shard count from the start
- Monitor transfer task latency as leading indicator
- Scale history service based on transfer task backlog
- Separate monitoring for transfer vs timer vs replication tasks

---

## Issue #41: Database Backup Impacts Production Performance [MEDIUM]

### Symptoms
- Performance degradation during backup window
- Latency spikes correlating with backup schedule
- Replication lag increases during backup
- Lock contention during pg_dump

### Root Cause
- `pg_dump` acquires `ACCESS SHARE` locks (blocks DDL, not DML, but increases checkpoint pressure)
- Cassandra snapshots cause I/O spike (hard link creation + flush)
- Backup process competes for disk I/O
- Large databases mean long backup windows

### Impact
- **Business**: Degraded performance during backup (scheduled, but still impactful)
- **System**: Extended backup windows risk overlapping with next cycle
- **Scale**: 1TB database = 30-60 min backup = long degradation window

### Detection
```promql
# Backup-correlated latency
temporal_persistence_latency_seconds{quantile="0.99"} > 0.5
  AND time() > backup_start_timestamp
  AND time() < backup_end_timestamp
```

### Resolution
```bash
# PostgreSQL: Use pg_basebackup on replica (not primary)
pg_basebackup -h pg-replica -U replication -D /backups/$(date +%Y%m%d) \
  --checkpoint=fast --wal-method=stream

# Or use barman for continuous archiving (no impact)
barman backup pg-primary --wait

# Cassandra: Incremental snapshots
nodetool snapshot temporal -t daily-$(date +%Y%m%d) --skip-flush

# Better: Use storage-level snapshots (EBS, persistent disk)
aws ec2 create-snapshot --volume-id vol-xxx --description "temporal-db-daily"
```

### Prevention
- Backup from replica, never primary
- Use storage-level snapshots (instant, no I/O impact)
- WAL archiving + base backup for point-in-time recovery
- Schedule backups during lowest traffic period
- Monitor backup duration and alert if exceeding window

---

## Issue #42: Timer Task Processing Delay [MEDIUM]

### Symptoms
- `workflow.Sleep()` and timer-based operations delayed
- Scheduled activities fire late
- `temporal_timer_task_latency` increasing
- Timer resolution degrading from seconds to minutes

### Root Cause
Timer tasks are processed by history service in batches:
- Timer task processor has a poll interval
- Under heavy load, timer processing deprioritized
- Shard with many timers fires slower (sequential processing)
- Clock skew between servers affects timer accuracy

### Detection
```promql
# Timer task processing delay
temporal_timer_task_latency_seconds{quantile="0.99"} > 10

# Timer task backlog
temporal_timer_task_pending_count > 5000
```

### Resolution
```yaml
# Tune timer task processor
# dynamic_config.yaml
history.timerTaskMaxPollerCount:
  - value: 4  # Increase parallel timer processing

history.timerProcessorMaxPollInterval:
  - value: 50ms  # More frequent polling

history.timerProcessorUpdateAckInterval:
  - value: 100ms

# For time-sensitive workflows, dedicate a namespace with its own shards
# ensuring timer processing isn't starved by other workloads
```

### Prevention
- Monitor timer task latency per shard
- Scale history service for high-timer workloads
- Use `ScheduleToStartTimeout` as backup for timer-based SLAs
- NTP synchronization across all servers (critical for timers)

---

## Issue #43: Database Write Amplification [MEDIUM]

### Symptoms
- Disk I/O much higher than expected for workflow volume
- Write latency increasing over time
- SSD endurance burning faster than expected
- Cassandra compaction falling behind

### Root Cause
Each workflow event generates multiple database writes:
- Execution record update
- History event append
- Transfer task creation
- Timer task creation (if applicable)
- Visibility record update
- Replication task (if multi-cluster)

A single activity = ~10 database writes. 1M activities/hour = 10M writes/hour.

### Detection
```promql
# Write amplification ratio
rate(disk_written_bytes_total[5m]) / rate(temporal_persistence_requests_total[5m]) > 10000

# Cassandra compaction pending
cassandra_compaction_pending_tasks > 50
```

### Resolution
```yaml
# 1. Batch writes (Temporal server config)
history.transferProcessorUpdateAckInterval:
  - value: 200ms  # Batch acknowledgments

# 2. Use Local Activities for short operations (no persistence overhead)
```

```go
// Local Activities: No separate task, no persistence for scheduling
func MyWorkflow(ctx workflow.Context) error {
    localOpts := workflow.LocalActivityOptions{
        ScheduleToCloseTimeout: 5 * time.Second,
    }
    localCtx := workflow.WithLocalActivityOptions(ctx, localOpts)
    
    // This doesn't create ActivityTaskScheduled/Started/Completed events
    // Much less DB write amplification
    var result string
    workflow.ExecuteLocalActivity(localCtx, QuickValidation, input).Get(ctx, &result)
    
    return nil
}
```

### Prevention
- Use Local Activities for operations < 10s that don't need separate retry/timeout
- Monitor write amplification ratio
- SSD with high endurance (enterprise grade)
- Proper compaction strategy to reduce write amplification in Cassandra

---

## Issue #44: Cross-Datacenter Persistence Latency [MEDIUM]

### Symptoms
- Persistence latency 50-100ms (vs expected 5-10ms)
- Network round-trips adding to every workflow operation
- Performance varies by time of day (routing changes)
- Geographically distributed team sees different performance

### Root Cause
- Database in different AZ/region than Temporal server
- Network latency between compute and storage
- Cross-AZ traffic adding 1-5ms per round-trip
- Each workflow operation = 3-5 DB round-trips = 15-25ms added

### Detection
```promql
# Network latency to DB
temporal_persistence_latency_seconds{quantile="0.50"} > 0.020  # 20ms median is too high
```

### Resolution
```yaml
# 1. Co-locate Temporal server with database (same AZ)
# Kubernetes node affinity
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: topology.kubernetes.io/zone
            operator: In
            values:
            - us-east-1a  # Same AZ as RDS

# 2. Use regional endpoints for multi-region
# temporal-history in us-east-1a -> RDS primary in us-east-1a
# temporal-history in eu-west-1a -> RDS primary in eu-west-1a

# 3. Connection pooling to reduce connection setup overhead
persistence:
  sql:
    maxConns: 200         # Reuse connections
    maxIdleConns: 50      # Keep warm connections
    maxConnLifetime: 30m  # Don't reconnect too often
```

### Prevention
- Same-AZ deployment for Temporal server and database
- Multi-region: each region has its own Temporal cluster + DB
- Monitor network latency between services
- Use connection pooling aggressively

---

## Issue #45: Visibility Store Inconsistency with Execution Store [MEDIUM]

### Symptoms
- `ListWorkflow` shows workflow as `Running` but `DescribeWorkflow` shows `Completed`
- Search attributes stale (not reflecting latest workflow state)
- Workflow appears in listing after deletion
- Count queries return wrong numbers

### Root Cause
Execution store and visibility store are updated asynchronously:
- Workflow completes -> execution store updated immediately
- Visibility store updated via async transfer task
- Under load, visibility update can lag seconds to minutes
- Elasticsearch refresh interval adds additional delay (default 1s)

### Impact
- **Business**: Dashboards show wrong counts, operators confused
- **System**: Monitoring based on visibility queries shows stale data
- **Scale**: At high throughput, lag can be minutes

### Detection
```promql
# Visibility lag
temporal_visibility_persistence_latency_seconds{quantile="0.99"} > 5

# Mismatch detection (application-level)
rate(temporal_visibility_mismatch_total[5m]) > 0
```

### Resolution
```go
// Application pattern: trust DescribeWorkflow for real-time, ListWorkflow for queries
func getAccurateStatus(ctx context.Context, c client.Client, wfID string) (Status, error) {
    // For real-time status: always use Describe (reads execution store)
    desc, err := c.DescribeWorkflowExecution(ctx, wfID, "")
    if err != nil {
        return Status{}, err
    }
    return extractStatus(desc), nil
}

func searchWorkflows(ctx context.Context, c client.Client, query string) ([]Status, error) {
    // For batch queries: use List (reads visibility, may be slightly stale)
    resp, err := c.ListWorkflow(ctx, &workflowservice.ListWorkflowExecutionsRequest{
        Query: query,
    })
    // Accept slight staleness for listing operations
    return extractStatuses(resp), err
}
```

```yaml
# Elasticsearch: Reduce refresh interval for faster visibility
index.refresh_interval: 1s  # Default is fine for most cases
# For near-real-time: 500ms (at cost of more I/O)
```

### Prevention
- Document: visibility is eventually consistent with execution
- Use `DescribeWorkflow` for real-time single-workflow queries
- Use `ListWorkflow` for batch/search operations (accept staleness)
- Monitor visibility lag as a health metric
- Don't build critical business logic on visibility queries

---

## Summary: Database & Persistence Issue Prevention Checklist

```
□ History shard count: 512+ for production (cannot change later easily)
□ PgBouncer in transaction mode with proper pool sizing
□ Connection pool monitoring with alert at 80% utilization
□ Retention period per namespace (3-30 days based on needs)
□ Archival enabled to S3/GCS for compliance
□ Elasticsearch ILM policy from day one
□ Database partitioned by time (for PostgreSQL)
□ Regular Cassandra repair (weekly) and compaction monitoring
□ Schema migration in init container (before server start)
□ Backup from replica, not primary
□ Same-AZ deployment for server and database
□ Separate execution store from visibility store monitoring
□ Transfer task and timer task latency monitoring
□ Use Local Activities to reduce write amplification
□ Pre-scale database for known traffic events
```
