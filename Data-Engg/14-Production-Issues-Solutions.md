# Production Issues & Solutions - Staff Architect Reference

---

## Kafka Production Issues

### Issue 1: Under-Replicated Partitions (URP)
**Symptoms:** Broker metrics show `UnderReplicatedPartitions > 0`, producer latency increases
**Root Cause:** Follower cannot keep up with leader (disk I/O, network, GC, CPU)
**Solution:**
```bash
# Identify affected partitions
kafka-topics.sh --describe --under-replicated-partitions --bootstrap-server broker:9092

# Check if specific broker is the problem
# If all URPs have same broker as follower → that broker is struggling

# Immediate: Reassign partitions away from struggling broker
kafka-reassign-partitions.sh --execute --reassignment-json-file plan.json

# Long-term: Fix disk I/O (add SSD), increase network bandwidth, tune GC
```
**Prevention:** Monitor `replica.lag.time.max.ms`, disk I/O wait, network throughput per broker

---

### Issue 2: Consumer Group Stuck in Rebalancing
**Symptoms:** Consumer lag growing, group state = "PreparingRebalance" for >5 minutes
**Root Cause:** Consumer member failing heartbeat, max.poll.interval exceeded, or ghost consumer
**Solution:**
```bash
# Check group state
kafka-consumer-groups.sh --describe --group my-group --bootstrap-server broker:9092

# If member stuck: Restart that consumer instance
# If group keeps rebalancing: Check for slow consumer
# Increase timeouts:
max.poll.interval.ms=600000
session.timeout.ms=45000
heartbeat.interval.ms=15000

# Use static membership to prevent rebalances on restart
group.instance.id=consumer-1  # Each instance gets unique ID
```
**Prevention:** Static group membership, cooperative sticky assignor, monitor rebalance frequency

---

### Issue 3: Kafka Disk Full
**Symptoms:** Producer gets `KAFKA_STORAGE_ERROR`, broker stops accepting writes
**Root Cause:** Retention too long, topic over-producing, or compaction blocked
**Solution:**
```bash
# Immediate: Reduce retention on largest topics
kafka-configs.sh --alter --entity-type topics --entity-name big-topic \
  --add-config retention.ms=3600000  # 1 hour temporarily

# Delete old segments manually (if needed)
kafka-delete-records.sh --offset-json-file offsets.json

# Check for compaction backlog (log cleaner threads)
kafka-configs.sh --describe --entity-type brokers --entity-name 0 | grep cleaner
```
**Prevention:** Monitor disk utilization with alerts at 70%/80%/90%, set retention budgets per topic, tiered storage

---

### Issue 4: Uneven Partition Distribution (Hot Partitions)
**Symptoms:** One broker at 90% CPU, others at 20%. One partition with 10x traffic.
**Root Cause:** Poor key distribution (null keys, one dominant key)
**Solution:**
```bash
# Identify hot partitions
kafka-consumer-groups.sh --describe --group cg1
# Check: One partition with much higher lag than others

# If null keys: Messages round-robin but one partition gets more
# If skewed keys: One key dominates (e.g., key="default" for all)

# Fix: Better partition key (user_id instead of null)
# Fix: Custom partitioner that spreads hot keys
# Fix: Increase partitions + rebalance producers
```
**Prevention:** Monitor per-partition throughput, avoid null keys, test key distribution before production

---

### Issue 5: Schema Registry Unavailable
**Symptoms:** Producers/consumers fail with "Subject not found" or connection refused
**Root Cause:** Schema Registry crashed, leader election failed, Kafka _schemas topic unavailable
**Solution:**
```bash
# Check SR health
curl http://schema-registry:8081/subjects

# If SR is down: Restart with correct config
# If _schemas topic corrupted: Restore from backup

# Producer resilience: Cache schemas locally
auto.register.schemas=false  # Only use pre-registered schemas
use.schema.id=<id>  # Hardcode ID as fallback
```
**Prevention:** HA deployment (multiple SR instances), schema caching in producers, circuit breaker

---

## Spark Production Issues

### Issue 6: Shuffle Spill to Disk (Performance Degradation)
**Symptoms:** Tasks slow, "spill" metrics in Spark UI show GBs written to disk
**Root Cause:** Insufficient execution memory for shuffle/sort/join operations
**Solution:**
```properties
# Option 1: More memory per executor
spark.executor.memory=16g

# Option 2: More partitions (less data per task)
spark.sql.shuffle.partitions=500  # Up from 200

# Option 3: Use off-heap for operations
spark.memory.offHeap.enabled=true
spark.memory.offHeap.size=4g

# Option 4: Reduce executor cores (less concurrent tasks competing)
spark.executor.cores=3  # Down from 5
```
**Prevention:** Monitor shuffle spill metrics, right-size partitions based on data volume

---

### Issue 7: Driver OOM on Large Collect
**Symptoms:** `java.lang.OutOfMemoryError: Java heap space` on driver
**Root Cause:** `collect()`, `toPandas()`, or large broadcast variable on driver
**Solution:**
```python
# NEVER collect large datasets to driver
# BAD:
all_data = df.collect()  # Pulls entire dataset to driver memory

# GOOD: Write to storage, read separately
df.write.parquet("s3://output/")

# For broadcast: Check broadcast size
# If > 1GB, it shouldn't be broadcast
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")  # Disable auto-broadcast

# Increase driver memory if genuinely needed
spark.driver.memory=8g
spark.driver.maxResultSize=4g
```
**Prevention:** Code review for `collect()` usage, set `spark.driver.maxResultSize` as safety net

---

### Issue 8: Spark Job Hangs at 99% (Last Few Tasks Slow)
**Symptoms:** 997/1000 tasks complete in 10 min, last 3 tasks running for 2 hours
**Root Cause:** Data skew (few partitions much larger than others)
**Solution:**
```python
# Check Spark UI: Task with 50GB input vs others with 200MB

# Fix 1: Enable AQE skew handling (Spark 3.0+)
spark.sql.adaptive.enabled=true
spark.sql.adaptive.skewJoin.enabled=true

# Fix 2: Enable speculation (run duplicate of slow task)
spark.speculation=true
spark.speculation.multiplier=3  # 3x slower than median → speculate

# Fix 3: Salted join for known skewed keys
# (See Q33 for full salted join implementation)
```
**Prevention:** Profile key distribution before production, enable AQE by default

---

### Issue 9: S3 Consistency Issues with Spark (Stale Reads)
**Symptoms:** Spark job reads 0 files from a path that was just written
**Root Cause:** S3 eventual consistency (legacy, mostly fixed) or file listing cache stale
**Solution:**
```python
# Use S3A committer (magic or staging) instead of default
spark.conf.set("spark.hadoop.fs.s3a.committer.name", "magic")
spark.conf.set("spark.hadoop.fs.s3a.committer.magic.enabled", "true")

# Or: Use Delta Lake / Iceberg (transactional metadata avoids listing issues)
# Iceberg doesn't depend on file listing — reads from metadata

# Flush S3A client cache
spark.conf.set("spark.hadoop.fs.s3a.impl.disable.cache", "true")
```
**Prevention:** Use table formats (Iceberg/Delta) that don't rely on listing, use S3A magic committer

---

### Issue 10: Too Many Small Output Files
**Symptoms:** Spark job produces 10,000 small (1-5MB) files, downstream jobs slow
**Root Cause:** Too many shuffle partitions or each task writes one file
**Solution:**
```python
# Option 1: Coalesce before write
df.coalesce(100).write.parquet("s3://output/")

# Option 2: AQE auto-coalescing
spark.sql.adaptive.coalescePartitions.enabled=true
spark.sql.adaptive.advisoryPartitionSizeInBytes=256m

# Option 3: Repartition by output partition column
df.repartition("date").write.partitionBy("date").parquet("s3://output/")

# Option 4: Post-write compaction (Iceberg/Delta)
spark.sql("OPTIMIZE my_table")
```
**Prevention:** Set target file size, use AQE, schedule regular compaction jobs

---

## Flink Production Issues

### Issue 11: TaskManager OOM / Container Killed
**Symptoms:** `java.lang.OutOfMemoryError` or YARN/K8s kills container
**Root Cause:** State too large for heap, RocksDB block cache misconfigured, off-heap leak
**Solution:**
```yaml
# Switch to RocksDB (off-heap state)
state.backend: rocksdb
state.backend.rocksdb.memory.managed: true

# Increase managed memory for RocksDB
taskmanager.memory.managed.fraction: 0.5

# If container killed: Increase total memory
taskmanager.memory.process.size: 8g

# If heap OOM: Reduce task heap, or fix user code leak
taskmanager.memory.task.heap.size: 2g
```
**Prevention:** Monitor JVM heap, RocksDB memory, container memory usage. Set state TTL.

---

### Issue 12: Backpressure Causing Cascading Delays
**Symptoms:** Latency grows linearly, all operators show high backpressure
**Root Cause:** One operator is bottleneck, upstream buffers fill, propagates to source
**Solution:**
```
# Identify bottleneck (Flink UI):
# Operator with HIGH busy time + LOW backpressure = the CAUSE
# Operators with HIGH backpressure = the VICTIMS

# Fix bottleneck operator:
1. Increase parallelism of that operator only
   env.setParallelism(10)  // global
   slowOperator.setParallelism(20)  // scale this one

2. If external call: Use async I/O
   AsyncDataStream.orderedWait(stream, new AsyncFunction(), 5000, TimeUnit.MS, 100)

3. If state access slow: Tune RocksDB
   state.backend.rocksdb.thread.num: 4
   state.backend.rocksdb.compaction.style: LEVEL
```
**Prevention:** Monitor per-operator metrics, alert on sustained backpressure > 50%

---

### Issue 13: Savepoint Incompatible After Code Change
**Symptoms:** Job fails to restore from savepoint: "State X not found"
**Root Cause:** Operator UID changed or removed (Flink can't map state to new operator)
**Solution:**
```java
// MUST assign stable UIDs to ALL stateful operators BEFORE first deploy
stream.map(...).uid("enrichment-v1")  // NEVER change this UID
      .keyBy(...).uid("keyed-state-v1")
      .addSink(...).uid("sink-v1")

// If UID was missing: State is lost. Must re-bootstrap from source.
// If state schema changed: Use State Processor API to migrate
```
**Prevention:** ALWAYS assign UIDs on first deployment. Code review enforcement.

---

## Airflow Production Issues

### Issue 14: Scheduler Overloaded (DAG Parsing Takes >60s)
**Symptoms:** Tasks not being scheduled on time, scheduler CPU at 100%
**Root Cause:** Too many DAGs, complex DAGs with heavy imports, or top-level code in DAG files
**Solution:**
```python
# 1. Reduce parsing time: Move imports inside functions
# BAD (imports at top level → parsed every 30s):
import heavy_library  # Takes 2s to import

# GOOD (import inside function → only when task runs):
def my_task():
    import heavy_library
    ...

# 2. Increase parsing interval
min_file_process_interval = 60  # Parse each file max once per 60s

# 3. Reduce DAG count with dynamic DAGs
# Instead of 500 DAG files → 1 factory that generates 500 DAGs

# 4. Use .airflowignore for non-DAG Python files
```
**Prevention:** Monitor scheduler parse time per DAG, lint for heavy imports, DAG complexity limits

---

### Issue 15: Deadlock in CeleryExecutor (Pool Full, No Progress)
**Symptoms:** Tasks queued indefinitely, all pool slots occupied by sensors
**Root Cause:** Sensors occupying worker slots while waiting (polling mode)
**Solution:**
```python
# Option 1: Use deferrable sensors (free the slot while waiting)
sensor = S3KeySensor(
    task_id="wait_for_file",
    bucket_name="data",
    bucket_key="ready.flag",
    deferrable=True,  # Frees worker slot, uses triggerer instead
)

# Option 2: Separate pool for sensors
sensor = S3KeySensor(
    task_id="wait",
    pool="sensor_pool",  # Dedicated pool with higher slots
)

# Option 3: Reschedule mode (releases slot between pokes)
sensor = S3KeySensor(
    task_id="wait",
    mode="reschedule",  # Releases slot, re-queued after poke_interval
)
```
**Prevention:** Deferrable operators by default, separate sensor pools, monitor pool utilization

---

## Data Lake Production Issues

### Issue 16: Iceberg Metadata Bloat (Slow Query Planning)
**Symptoms:** Queries take 30s+ just for planning (before processing data)
**Root Cause:** Millions of manifest entries, never-expired snapshots
**Solution:**
```sql
-- Expire old snapshots (keep last 5 days)
CALL catalog.system.expire_snapshots(
    table => 'db.orders',
    older_than => TIMESTAMP '2024-01-10 00:00:00',
    retain_last => 5
);

-- Rewrite manifests (reduce manifest file count)
CALL catalog.system.rewrite_manifests('db.orders');

-- Remove orphan files (files not referenced by any snapshot)
CALL catalog.system.remove_orphan_files(
    table => 'db.orders',
    older_than => TIMESTAMP '2024-01-08 00:00:00'
);
```
**Prevention:** Schedule daily maintenance: expire_snapshots + rewrite_manifests

---

### Issue 17: Delta Lake VACUUM Deleting Active Files
**Symptoms:** Queries fail with "file not found" after VACUUM
**Root Cause:** VACUUM ran with too short retention while long-running queries still referenced old files
**Solution:**
```sql
-- Set safe retention (default 7 days)
VACUUM orders RETAIN 168 HOURS;  -- 7 days

-- Check for active queries before vacuum
-- NEVER set delta.deletedFileRetentionDuration < longest possible query time

-- Safety: delta.logRetentionDuration > delta.deletedFileRetentionDuration
ALTER TABLE orders SET TBLPROPERTIES (
    'delta.deletedFileRetentionDuration' = 'interval 7 days',
    'delta.logRetentionDuration' = 'interval 30 days'
);
```
**Prevention:** Never vacuum with < 7 day retention, schedule vacuum during low-query periods

---

### Issue 18: S3 Rate Limiting (503 SlowDown)
**Symptoms:** Random failures in Spark/Flink reading from S3, "503 Slow Down" errors
**Root Cause:** S3 prefix rate limit: 3,500 PUT/COPY/POST/DELETE or 5,500 GET per prefix per second
**Solution:**
```python
# 1. Randomize S3 key prefixes
# BAD:  s3://bucket/data/2024/01/15/file_001.parquet (all same prefix)
# GOOD: s3://bucket/data/a3f2/2024/01/15/file_001.parquet (hash prefix)

# 2. Increase retry with exponential backoff
spark.conf.set("spark.hadoop.fs.s3a.retry.limit", "20")
spark.conf.set("spark.hadoop.fs.s3a.retry.interval", "500ms")

# 3. Use Iceberg/Delta (reduces LIST calls drastically)
# Iceberg: Reads manifest files instead of LIST operations
# Far fewer S3 calls per query

# 4. Request S3 partition increase from AWS (support ticket)
```
**Prevention:** Use table formats, spread prefixes, monitor S3 error rates

---

## Data Quality Production Issues

### Issue 19: Silent Data Corruption (Wrong Results, No Alerts)
**Symptoms:** Business users report revenue dashboard shows 2x expected value
**Root Cause:** Pipeline applied JOIN that produced duplicates (fan-out not handled)
**Solution:**
```sql
-- Identify duplication
SELECT order_id, COUNT(*) as cnt
FROM fct_orders
GROUP BY order_id
HAVING COUNT(*) > 1;

-- Root cause: JOIN with dim_promotion produced 1:N match
-- Fix: Add DISTINCT or qualify the JOIN condition
-- Add test:
-- dbt test: unique on order_id in fct_orders
```
**Prevention:** Always test uniqueness of primary keys, compare record counts before/after joins, reconcile totals with source

---

### Issue 20: Timezone Mismatch Causing Duplicate/Missing Data
**Symptoms:** Data for 2024-01-15 appears in both Jan 14 and Jan 15 partitions
**Root Cause:** Source sends UTC, pipeline converts to local time inconsistently
**Solution:**
```python
# Standardize: ALL timestamps stored in UTC internally
# Convert to local time ONLY at presentation layer (dashboard/report)

# Pipeline fix:
df = df.withColumn("event_time_utc", 
    to_utc_timestamp(col("event_time"), "America/New_York"))
df = df.withColumn("date_partition", 
    to_date(col("event_time_utc")))  # Partition by UTC date

# dbt test:
# assert no records where timezone conversion would cross date boundary unexpectedly
```
**Prevention:** Convention: Store UTC everywhere, document timezone handling per source

---

## Infrastructure Production Issues

### Issue 21: Kubernetes Pod Scheduling Failures
**Symptoms:** Spark/Flink pods stuck in "Pending" state for minutes
**Root Cause:** Cluster autoscaler too slow, resource quotas hit, node affinity constraints
**Solution:**
```yaml
# 1. Pre-warm node pools (keep minimum nodes ready)
minNodes: 5  # Never scale below 5

# 2. Use pod priority classes
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: data-pipeline-critical
value: 1000000
---
# 3. Overprovisioning (dummy pods that get evicted for real workloads)
# Placeholder pods reserve capacity → real pods can schedule instantly

# 4. Relax constraints
# If using nodeAffinity → switch to preferred instead of required
# If specific instance types → allow multiple types
```
**Prevention:** Cluster autoscaler response time < 2 min, priority classes for critical pipelines

---

### Issue 22: Network Partition Between Services
**Symptoms:** Intermittent failures: Kafka produce timeouts, DB connection resets, S3 403s
**Root Cause:** Network ACL change, DNS resolution failure, cross-AZ latency spike
**Solution:**
```
# Diagnosis:
1. Check connectivity from pod/instance to each dependency
2. Check DNS resolution (nslookup, dig)
3. Check security groups / network ACLs for recent changes
4. Check cross-AZ latency (if services in different AZs)

# Mitigation:
- Circuit breaker: Stop hammering failed dependency
- Retry with backoff: Survive transient network issues
- Health checks: Mark unhealthy pods for restart
- Multi-AZ redundancy: Don't depend on single AZ
```
**Prevention:** Chaos testing (network failures), health checks on all external dependencies, service mesh

---

## Additional Production Issues (23-65) - Quick Reference

| # | System | Issue | Fix |
|---|--------|-------|-----|
| 23 | Kafka | Leader election storm (many partitions) | KRaft mode, controlled.shutdown |
| 24 | Kafka | Log compaction falling behind | Increase cleaner threads, reduce compaction lag |
| 25 | Kafka | Message size too large (> 1MB) | Compress, reference storage, chunking |
| 26 | Kafka | Offset out of range (consumer lost) | auto.offset.reset=earliest, monitor lag |
| 27 | Kafka | Producer buffer full (BufferExhaust) | Increase buffer.memory, slow down producer |
| 28 | Spark | Stage retry due to FetchFailed | External shuffle service, more retries |
| 29 | Spark | Broadcast join OOM | Reduce broadcast threshold, use sort-merge |
| 30 | Spark | Hive metastore timeout | Connection pooling, separate HMS per workload |
| 31 | Spark | Delta MERGE conflict | Retry with backoff, reduce concurrent writers |
| 32 | Spark | Parquet footer read slow (many files) | Compact, use table format metadata |
| 33 | Flink | Watermark stuck (no progress) | Check idle sources, set withIdleness() |
| 34 | Flink | State backend corruption | Restore from checkpoint-1, fix state code |
| 35 | Flink | Job restart loop (fail → restart → fail) | Fix root cause, set restart-strategy limits |
| 36 | Flink | Kafka source offset mismatch | Reset to earliest, check topic deletion |
| 37 | Flink | Memory leak in user code | Profile with JFR, fix closeable resources |
| 38 | Airflow | DAG run stuck in queued state | Check scheduler, clear zombie tasks |
| 39 | Airflow | XCom too large (DB bloat) | Use S3 XCom backend, limit XCom size |
| 40 | Airflow | Connection pool exhausted | PgBouncer, reduce concurrent tasks |
| 41 | Airflow | Tasks not picked up by executor | Check Celery workers/K8s pods available |
| 42 | Airflow | Circular dependency error | Refactor DAG, use datasets instead |
| 43 | Iceberg | Orphan files accumulating | Schedule remove_orphan_files regularly |
| 44 | Iceberg | Concurrent commits conflict | Retry strategy, reduce concurrent writes |
| 45 | Iceberg | Sort order not applied | Verify write.distribution-mode=hash/range |
| 46 | Delta | Checkpoint file too large | Increase checkpoint interval (every 100) |
| 47 | Delta | Streaming + batch conflict | Use WAL for streaming, batch uses overwrite |
| 48 | OLAP | ClickHouse merge backlog | Increase background_pool_size, reduce inserts |
| 49 | OLAP | Druid segment availability delay | Tune segment publish interval, add historicals |
| 50 | OLAP | Snowflake warehouse suspended mid-query | Increase auto_suspend, or keep-alive query |
| 51 | DQ | False positive alerts fatiguing team | Tune thresholds, suppress known patterns |
| 52 | DQ | Data drift undetected for weeks | Add statistical monitoring (PSI, Z-score) |
| 53 | DQ | Source system schema change breaks pipe | Schema registry, contract checks in CI |
| 54 | Infra | Cost spike from runaway query | Budget alerts, auto-kill long queries |
| 55 | Infra | SSL certificate expiry | Auto-rotation (AWS ACM, Let's Encrypt) |
| 56 | Infra | Cross-region latency for global users | Regional read replicas, cache layer |
| 57 | Infra | Spot/preemptible instance interruption | Graceful shutdown handling, checkpointing |
| 58 | Infra | Docker image pull failures | Private registry mirror, pre-pull images |
| 59 | Pipe | Backfill job overwhelming source system | Rate limit, off-hours scheduling |
| 60 | Pipe | Pipeline ordering issue (child before parent) | Explicit dependencies, event-driven |
| 61 | Pipe | Idempotency broken (duplicates on rerun) | Fix to MERGE/overwrite, not append |
| 62 | Pipe | Secret rotation breaks connections | Dynamic secret loading, health checks |
| 63 | Pipe | Daylight saving time boundary errors | Always use UTC internally |
| 64 | Pipe | File format version mismatch | Pin versions, test format compatibility |
| 65 | Pipe | Downstream table bloat from missing retention | Implement lifecycle policies, auto-purge |
