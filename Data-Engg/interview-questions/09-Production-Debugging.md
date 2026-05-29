# Interview Questions Set 9: Production Debugging & Troubleshooting (Q241-270)

---

## Q241: Your Kafka cluster shows increasing consumer lag on multiple consumer groups simultaneously. Walk through your debugging approach.

**Answer:**

```
STEP 1: Characterize the problem
  - Which consumer groups? All or specific?
  - Which topics/partitions? All or specific?
  - When did lag start increasing? Correlate with events.

STEP 2: Check broker health
  $ kafka-broker-api-versions.sh --bootstrap-server broker:9092
  $ kafka-topics.sh --describe --under-replicated-partitions
  
  Look for:
  - Broker CPU > 80% → capacity issue
  - Disk I/O wait > 20% → slow disk
  - Network saturation → bandwidth limit
  - Under-replicated partitions → broker struggling

STEP 3: Check if problem is producer or consumer side
  - Producer throughput normal? (same rate as before lag started?)
  - If producer spike: Lag increases because input > processing capacity
  - If producer normal: Consumer slowed down (degradation)

STEP 4: Consumer-side diagnosis
  - Check consumer logs for errors/warnings
  - Look for frequent rebalances (group.instance.id not set?)
  - Check max.poll.interval.ms exceeded? (processing too slow)
  - External dependency slow? (DB, API calls from consumer)
  - GC pauses? (check GC logs, heap utilization)

STEP 5: Common root causes
  | Symptom | Cause | Fix |
  |---------|-------|-----|
  | All groups lag | Broker overloaded | Add brokers, reduce retention |
  | One group lags | Consumer issue | Scale consumers, fix slow processing |
  | Sudden spike | Producer burst | Auto-scale consumers, increase capacity |
  | Gradual increase | Growing data volume | Add partitions + consumers |
  | Intermittent | Rebalances | Static membership, cooperative protocol |

STEP 6: Immediate mitigation
  - Scale consumer instances (up to partition count)
  - Increase max.poll.records if processing per record is fast
  - Skip/DLQ problematic messages if one bad message blocks all
  - Temporarily increase consumer resources (CPU/memory)
```

---

## Q242: Your Spark job that normally takes 30 minutes has been running for 3 hours. Diagnose.

**Answer:**

```
STEP 1: Check Spark UI
  - Stages tab: Which stage is stuck?
  - Tasks tab: Are most tasks done with 1-2 stragglers?
  - Storage tab: Is cached data being evicted repeatedly?

STEP 2: Identify the pattern

PATTERN A: One task extremely slow (data skew)
  Spark UI shows: 199/200 tasks complete, 1 running for 2.5 hours
  Task input size: Skewed task = 50GB, others = 250MB
  
  Fix:
  - Enable AQE skew join: spark.sql.adaptive.skewJoin.enabled=true
  - Salt the skewed key
  - Broadcast join if one side is small enough
  - Isolate hot keys (separate processing path)

PATTERN B: All tasks slow (resource contention)
  Spark UI shows: All tasks running slowly, high GC time
  
  Diagnosis:
  - GC time > 10% of task time → memory pressure
  - Spill to disk → insufficient execution memory
  - Shuffle write waiting → network/disk bottleneck
  
  Fix:
  - Increase executor memory
  - Increase shuffle partitions (smaller data per task)
  - Reduce executor cores (less memory competition)

PATTERN C: Tasks queued, not running
  Spark UI shows: 1000 pending tasks, only 10 running
  
  Diagnosis:
  - Not enough executors (dynamic allocation not scaling)
  - YARN/K8s resource limits hit
  - Cluster fully utilized by other jobs
  
  Fix:
  - Check cluster capacity
  - Enable dynamic allocation with appropriate settings
  - Schedule during off-peak or request more resources

PATTERN D: Stages recomputing (shuffle service failure)
  Spark UI shows: Stage re-executed multiple times
  
  Diagnosis:
  - Executor died → shuffle files lost → recomputation
  - Check executor logs for OOM kills
  
  Fix:
  - Enable external shuffle service
  - Increase executor memoryOverhead
  - Checkpoint intermediate results
```

---

## Q243: Your Airflow DAG is stuck in a "running" state but no tasks are executing. What's wrong?

**Answer:**

```
POSSIBLE CAUSES:

1. SCHEDULER NOT RUNNING:
   Check: Is scheduler process alive?
   $ airflow scheduler status
   Fix: Restart scheduler, check scheduler logs for errors

2. ALL SLOTS OCCUPIED:
   Check: Pools and concurrency settings
   $ airflow pools list
   - Pool slots = 0 (misconfigured)
   - dag_concurrency/max_active_tasks_per_dag exceeded
   - Deferred operators not freeing slots (need triggerer)
   Fix: Increase pool size, kill stuck tasks, start triggerer

3. TASKS STUCK IN "QUEUED" STATE:
   Check: Executor workers available?
   - CeleryExecutor: Are workers running? Check Flower UI.
   - KubernetesExecutor: Can pods be scheduled? Check K8s events.
   Fix: Scale workers, check K8s resource quotas, check queue

4. DEPENDENCY NOT MET:
   Check: Upstream task in unclear state
   - Task marked as "running" from previous failed attempt
   - ExternalTaskSensor waiting for non-existent upstream run
   Fix: Clear stuck task states, verify sensor parameters

5. DATABASE LOCK:
   Check: Database connections, deadlocks
   - Too many concurrent connections from scheduler
   - Deadlock on task instance table
   Fix: Check PgBouncer, increase connection pool, restart

DEBUGGING COMMANDS:
  $ airflow dags show <dag_id>           # Visualize dependencies
  $ airflow tasks states-for-dag-run <dag_id> <execution_date>
  $ airflow tasks clear <dag_id> -t <task_id>  # Reset stuck task
```

---

## Q244: Your Flink job's checkpoint is failing consistently. Diagnose and fix.

**Answer:**

```
DIAGNOSIS:

1. Check Flink UI → Checkpoints tab:
   - Failed checkpoints count
   - Last successful checkpoint time
   - Failure reason: TIMEOUT / DECLINED / EXPIRED

2. Common failure patterns:

PATTERN A: Checkpoint timeout
  Symptom: "Checkpoint expired before completing"
  Causes:
  - Backpressure → barriers can't propagate
  - Large state → upload to S3 too slow
  - Single slow subtask holding up entire checkpoint
  
  Fix:
  - Enable unaligned checkpoints (barriers skip ahead)
  - Increase checkpoint timeout
  - Enable incremental checkpoints (RocksDB)
  - Fix backpressure root cause

PATTERN B: Checkpoint declined
  Symptom: "Task not ready for checkpoint"
  Causes:
  - Task still recovering from previous failure
  - Task performing blocking operation during checkpoint
  
  Fix:
  - Increase min pause between checkpoints
  - Fix blocking operations (use async I/O)

PATTERN C: State too large
  Symptom: Checkpoint size growing, eventually OOM or timeout
  Causes:
  - State TTL not configured → unbounded growth
  - Keyed state with ever-growing key space
  - Large list/map state per key
  
  Fix:
  - Configure State TTL (expire old entries)
  - Switch to RocksDB backend (offloads to disk)
  - Enable incremental checkpoints
  - Review state access patterns (reduce stored data)

PATTERN D: S3/HDFS write failures
  Symptom: IOException during checkpoint upload
  Causes:
  - S3 rate limiting (too many PUT requests)
  - Network issues
  - Permissions problem
  
  Fix:
  - Increase checkpoint interval (fewer uploads)
  - Use S3 multipart upload settings
  - Check S3 bucket policies and IAM roles

CONFIGURATION FIXES:
  execution.checkpointing.interval: 5min
  execution.checkpointing.timeout: 20min
  execution.checkpointing.min-pause: 30s
  execution.checkpointing.max-concurrent-checkpoints: 1
  execution.checkpointing.unaligned: true
  state.backend: rocksdb
  state.backend.incremental: true
```

---

## Q245: Your data lake query performance suddenly degraded by 10x. What happened?

**Answer:**

```
INVESTIGATION STEPS:

1. COMPARE: What changed?
   - Same query, same data volume, just slower
   - Query plan changed? (Catalyst/optimizer regression)
   - Data layout changed? (small files, partition changes)

2. CHECK METADATA:
   $ spark.sql("DESCRIBE DETAIL my_table")
   - numFiles: Was 500, now 50,000? → SMALL FILES PROBLEM
   - Total size same but file count exploded
   - After many small appends (streaming micro-batches)

3. CHECK PARTITION PRUNING:
   $ spark.sql("EXPLAIN EXTENDED SELECT ...")
   - Partition filters being applied?
   - If schema change removed partition column → full scan

4. COMMON ROOT CAUSES:
   
   A. Small files explosion:
      Pipeline changed from daily batch (100 files) to streaming (10K files/day)
      Fix: Run compaction (OPTIMIZE / rewrite_data_files)
      
   B. Partition evolution confusion:
      New partitioning scheme applied, old queries don't benefit
      Fix: Verify query predicates match new partition spec
      
   C. Statistics stale/missing:
      Table grew 10x but statistics not updated
      Fix: ANALYZE TABLE, recompute column stats
      
   D. Cache invalidation:
      Query result cache expired or storage was compacted
      Fix: Pre-warm cache, or accept first-query penalty
      
   E. Concurrent writers blocking:
      Many concurrent writes creating lock contention
      Fix: Batch writes, reduce write frequency
      
   F. Cloud throttling:
      S3 rate limit hit (3500 PUT/5500 GET per prefix)
      Fix: Randomize prefixes, use more bucket prefixes

5. QUICK FIXES:
   - Run compaction immediately
   - Re-analyze table statistics
   - Check and fix partition pruning
   - Verify no schema drift
```

---

## Q246: Your streaming pipeline is producing duplicate records. Find and fix the root cause.

**Answer:**

```
DUPLICATE SOURCES:

1. PRODUCER DUPLICATES (Kafka):
   Cause: Producer retry after network timeout (message was actually committed)
   Check: enable.idempotence=false in producer config
   Fix: enable.idempotence=true (broker deduplicates by sequence number)

2. CONSUMER REPROCESSING:
   Cause: Consumer crashes after processing but before committing offset
   Check: Are offsets committed AFTER processing? (at-least-once)
   Fix: 
   - Exactly-once: Transactional producer + consumer
   - Idempotent consumer: Dedup on sink side (upsert, dedup key)

3. REBALANCE DUPLICATES:
   Cause: Rebalance revokes partition, uncommitted work reprocessed by new owner
   Check: Frequent rebalances in consumer group logs
   Fix: 
   - Static group membership
   - Cooperative sticky assignor
   - Increase session.timeout.ms

4. SOURCE DUPLICATES:
   Cause: Source system sends same event twice (retry, bug)
   Check: Count distinct event_ids vs total records
   Fix: Deduplication layer:
   
   // Flink dedup:
   SELECT * FROM (
     SELECT *, ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time) as rn
     FROM events
   ) WHERE rn = 1;
   
   // Or: Redis-based dedup
   if (redis.setIfAbsent(eventId, "1", Duration.ofHours(24))) {
       process(event);  // First time
   } else {
       // Duplicate, skip
   }

5. PIPELINE REPLAY:
   Cause: Pipeline restarted from earlier offset (intentional or bug)
   Fix: Ensure sink handles replays idempotently (MERGE/UPSERT)

PREVENTION:
- Always design for at-least-once + idempotent sinks
- Use natural dedup keys (event_id) not synthetic
- Monitor duplicate rate as a quality metric
- Schema: Include event_id and event_time in all events
```

---

## Q247: Your Snowflake warehouse costs increased 3x this month. Diagnose and fix.

**Answer:**

```
DIAGNOSIS APPROACH:

1. CHECK QUERY HISTORY:
   SELECT 
     user_name,
     warehouse_name,
     SUM(credits_used) as total_credits,
     COUNT(*) as query_count,
     AVG(bytes_scanned) as avg_scan
   FROM snowflake.account_usage.query_history
   WHERE start_time > DATEADD(month, -1, CURRENT_TIMESTAMP())
   GROUP BY 1, 2
   ORDER BY total_credits DESC
   LIMIT 20;

2. CHECK WAREHOUSE UTILIZATION:
   SELECT 
     warehouse_name,
     SUM(credits_used) as credits,
     AVG(avg_running) as avg_queries_running,
     AVG(queued_load) as avg_queued
   FROM snowflake.account_usage.warehouse_metering_history
   WHERE start_time > DATEADD(month, -1, CURRENT_TIMESTAMP())
   GROUP BY 1
   ORDER BY credits DESC;

3. COMMON COST CULPRITS:

   A. Warehouse not suspending:
      Auto-suspend set to 3600s (1 hour) → runs idle
      Fix: Set auto_suspend = 60 (1 minute) for analytics WH

   B. Runaway queries:
      One user running full table scan repeatedly
      Fix: Set STATEMENT_TIMEOUT_IN_SECONDS = 300 per warehouse
      
   C. Excessive clustering:
      Automatic reclustering running continuously on large table
      Fix: Review cluster keys, consider dropping on low-value tables
      
   D. Unnecessary full scans:
      Queries not using partition pruning (missing WHERE clause on date)
      Fix: Educate users, add cluster keys, use resource monitors
      
   E. Oversized warehouse:
      4XL warehouse for simple queries that would run fine on Small
      Fix: Right-size warehouses, use multi-cluster auto-scale
      
   F. Too many warehouses running:
      Dev warehouses left running 24/7
      Fix: Auto-suspend aggressively, schedule suspend/resume

4. IMMEDIATE ACTIONS:
   - Set resource monitors with budget alerts
   - Review and reduce auto-suspend timers
   - Kill runaway queries (> 30 min for analytics)
   - Implement query tagging for cost attribution
   - Right-size warehouses based on actual utilization
```

---

## Q248: Your data pipeline shows data freshness SLA breach — data is 4 hours stale. Triage it.

**Answer:**

```
INCIDENT RESPONSE:

1. ASSESS IMPACT (2 minutes):
   - Which tables are stale?
   - Which dashboards/reports affected?
   - Is this customer-facing or internal?
   - Severity: SEV1 (revenue impact) or SEV2 (internal analytics)

2. CHECK PIPELINE STATUS (5 minutes):
   - Airflow: Is DAG running? Which task failed/stuck?
   - Spark job: Running but slow? Failed? Not triggered?
   - Source system: Is source available?

3. TRACE UPSTREAM (10 minutes):
   Stale table → upstream pipeline → source system
   
   Lineage trace:
   analytics.fct_orders (4h stale)
     ← staging.orders (4h stale)
       ← raw.orders_cdc (4h stale)
         ← Kafka topic: cdc.orders (4h lag!)
           ← Debezium connector (FAILED at 08:00 AM!)

4. ROOT CAUSE:
   Debezium connector died due to:
   - Replication slot dropped (WAL retention exceeded)
   - Source DB schema change broke connector
   - OOM on Kafka Connect worker
   - Network partition to source DB

5. RESOLUTION:
   - Restart connector (if simple failure)
   - If slot dropped: Re-snapshot (takes hours for large tables)
   - If schema change: Update connector config, restart
   - Notify stakeholders with ETA

6. COMMUNICATION:
   Minute 0: "Investigating data freshness issue"
   Minute 15: "Root cause identified: CDC connector failure since 08:00"
   Minute 30: "Fix applied, pipeline recovering, ETA: 2 hours to catch up"
   Resolution: "Full recovery at 14:00, postmortem scheduled"
```

---

## Q249-270: [Production Debugging - Condensed]

**Q249:** Flink job OOM after running fine for weeks.
- Root cause: State growing without TTL (new keys accumulating)
- Fix: Add StateTTL, identify keys not cleaned up
- Prevention: Monitor state size metrics, alert on growth rate

**Q250:** Spark job succeeds but produces empty output.
- Common causes: Filter too aggressive (empty after filter), source empty, wrong path
- Debug: Check counts at each stage, verify source data availability
- Prevention: Quality check (assert output count > 0) in pipeline

**Q251:** Kafka producer getting TimeoutException intermittently.
- Causes: Broker overloaded, network issues, batch.size too large
- Debug: Check broker CPU/disk, network metrics, producer logs
- Fix: Increase request.timeout.ms, reduce batch.size, add brokers

**Q252:** Delta Lake MERGE operation taking 10x longer than usual.
- Causes: Target table bloated (small files), source data skewed
- Debug: Check file count, partition sizes, join condition selectivity
- Fix: Run OPTIMIZE, improve MERGE condition, z-order

**Q253:** Airflow tasks randomly fail with "Zombie detected" errors.
- Causes: Worker died mid-task, heartbeat missed, scheduler assumes dead
- Debug: Check worker logs, resource utilization, heartbeat settings
- Fix: Increase scheduler_zombie_task_threshold, fix OOM on workers

**Q254:** ClickHouse query slows down after data migration.
- Causes: Wrong ORDER BY (data not sorted optimally), missing skipping indexes
- Debug: Check query EXPLAIN, examine part statistics
- Fix: Re-order primary key, add bloom filter index, optimize table

**Q255:** Iceberg table has 1M manifest entries causing slow planning.
- Causes: Too many small commits (micro-batching without compaction)
- Fix: rewrite_manifests procedure, increase commit batch size
- Prevention: Configure manifest target size, regular maintenance

**Q256:** Pipeline passes quality checks but business users report wrong numbers.
- Causes: Logic error (quality checks test wrong things), timezone issue, double-counting
- Debug: Manual SQL validation, trace specific records end-to-end
- Fix: Add business-logic tests, reconcile with source system totals

**Q257:** Flink job starts failing after Kafka partition count increase.
- Causes: Savepoint incompatible with new partition count, key group redistribution
- Fix: Take new savepoint after Kafka change, adjust max parallelism
- Prevention: Set max-parallelism high upfront, use Kafka consumer regex

**Q258:** Snowflake Snowpipe ingestion silently dropping records.
- Causes: File format mismatch, schema drift in source, file already processed
- Debug: Check COPY_HISTORY, validate file format, check notification queue
- Fix: Fix format, add error handling (ON_ERROR=CONTINUE + check errors)

**Q259:** Spark Structured Streaming query keeps restarting with OOM.
- Causes: State store growing (watermark not advancing), too many keys
- Debug: Check state store size in checkpoint, watermark progress
- Fix: Add/fix watermark, drop old state, increase driver/executor memory

**Q260:** Multiple data pipelines fail at same time every day.
- Causes: Resource contention (all pipelines scheduled at midnight), source maintenance window
- Fix: Stagger schedules, implement resource pools/queues, add retry with backoff

**Q261:** CDC pipeline losing events during PostgreSQL failover.
- Causes: Replication slot not replicated to standby, WAL gap
- Fix: Use pg_replication_slots on new primary, re-snapshot if slot lost
- Prevention: Use Patroni with slot replication, monitor slot lag

**Q262:** dbt model producing different results in dev vs prod.
- Causes: Different source data, different variable values, stale dev environment
- Fix: Pin source data versions, use dbt vars consistently, refresh dev data

**Q263:** Kafka Connect connector in FAILED state, won't restart.
- Debug: Check connector status API, worker logs, offset storage
- Common: Serialization error, source unreachable, connector bug
- Fix: Fix config, restart task (`POST /connectors/{name}/tasks/{id}/restart`)

**Q264:** Data lake query returns different results than source system.
- Causes: Pipeline lag, incorrect join logic, handling of NULLs/defaults
- Debug: Point-in-time comparison (query both at same snapshot)
- Fix: Reconciliation query, fix transform logic, add automated cross-checks

**Q265:** Elasticsearch cluster goes RED (unassigned shards).
- Causes: Disk watermark exceeded, node failure, too many shards
- Fix: Free disk space, increase watermark, reduce replicas temporarily
- Prevention: Monitor disk, implement ILM, limit shard count

**Q266:** Airflow worker running out of disk due to log files.
- Causes: Tasks producing excessive stdout, log rotation not configured
- Fix: Implement remote logging (S3), configure log rotation, limit task output

**Q267:** Flink job latency gradually increasing over days.
- Causes: RocksDB compaction falling behind, state growing, GC pressure
- Debug: Check RocksDB metrics, compaction stats, GC time
- Fix: Tune RocksDB (block cache, write buffer), add state TTL

**Q268:** Spark on K8s pods randomly evicted.
- Causes: Memory exceeds pod limits (off-heap), node pressure, spot interruption
- Fix: Increase memory overhead, use pod disruption budgets, handle graceful shutdown

**Q269:** BigQuery slot contention causing query queueing.
- Causes: Flat-rate reservation too small for concurrent workload
- Fix: Autoscaler edition (flex slots), optimize queries (reduce slots needed), stagger

**Q270:** Data pipeline works in test but fails with real data.
- Causes: Edge cases (nulls, special chars, Unicode), volume (OOM at scale), data skew
- Fix: Test with production-like data samples, load test, handle all edge cases
- Prevention: Property-based testing, production data sampling for test
