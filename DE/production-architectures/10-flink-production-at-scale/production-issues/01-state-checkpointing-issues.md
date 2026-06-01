# State & Checkpointing Issues (#1-14)

> The most critical category of Flink production issues. State and checkpoint failures are the #1 cause of job restarts and data processing delays at scale.

---

## Issue #1: Checkpoint Timeout Due to Backpressure

**Severity**: 🔴 Critical  
**Frequency**: Very High (seen weekly at scale)  
**Impact**: Job restarts, processing gap, potential data reprocessing

### Symptoms
```
WARN  CheckpointCoordinator - Checkpoint 847 expired before completing.
      Failing checkpoint 847 because of timeout.
WARN  CheckpointCoordinator - Checkpoint 847 of job abc123 timed out after 600000ms.
```
- Checkpoint duration steadily increasing over days
- `lastCheckpointDuration` metric > `checkpointing.timeout`
- Backpressure metrics showing > 500ms/sec on downstream operators

### Root Cause
Checkpoint barriers cannot propagate through operators that are backpressured. When a downstream operator is slow:
1. Network buffers fill up
2. Barrier gets stuck behind data in buffers
3. Upstream operators cannot complete their snapshot (barrier alignment)
4. Checkpoint coordinator times out

```
Normal:     [data][barrier][data] → flows freely → checkpoint completes

Backpressured: [data][data][data][data][barrier][data]...[blocked]
                                        ↑ barrier stuck behind buffered data
                                        Checkpoint times out!
```

### Diagnosis
```bash
# Check checkpoint history via REST API
curl http://jobmanager:8081/jobs/<job-id>/checkpoints | jq '.history[-5:]'

# Check which subtasks are blocking
curl http://jobmanager:8081/jobs/<job-id>/checkpoints/detail/<checkpoint-id> | \
  jq '.subtask_stats | to_entries | sort_by(.value.end_to_end_duration) | reverse | .[0:5]'

# Check backpressure on specific task
curl http://jobmanager:8081/jobs/<job-id>/vertices/<vertex-id>/backpressure
```

```promql
# Prometheus: Checkpoint duration trend
flink_jobmanager_job_lastCheckpointDuration{job_name="my-job"} / 1000
# Should be well below timeout (default 600s)

# Barrier alignment time (tells you exactly where barrier is stuck)
flink_taskmanager_job_task_operator_checkpointAlignmentTime
```

### Fix

**Immediate (reduce checkpoint time):**
```yaml
# Increase timeout temporarily
execution.checkpointing.timeout: 1200000  # 20 min

# Reduce checkpoint interval to allow more time between attempts
execution.checkpointing.min-pause: 120000  # 2 min between checkpoints
```

**Proper fix (enable unaligned checkpoints):**
```yaml
# Barriers overtake in-flight data (no alignment needed)
execution.checkpointing.unaligned.enabled: true
execution.checkpointing.aligned-checkpoint-timeout: 60000  # Fallback to unaligned after 60s
```

**Alternative fix (fix the backpressure root cause):**
- Increase sink parallelism
- Add buffering before slow sink
- Optimize slow operator

### Prevention
```yaml
# Production checkpoint config that handles backpressure
execution.checkpointing.interval: 180000          # 3 min
execution.checkpointing.timeout: 900000           # 15 min
execution.checkpointing.min-pause: 120000         # 2 min gap
execution.checkpointing.max-concurrent-checkpoints: 1
execution.checkpointing.unaligned.enabled: true
execution.checkpointing.aligned-checkpoint-timeout: 30000
```

---

## Issue #2: Incremental Checkpoint Size Explosion

**Severity**: 🔴 Critical  
**Frequency**: High (monthly at scale)  
**Impact**: S3 costs spike, checkpoint duration increases, potential timeout

### Symptoms
- `lastCheckpointSize` suddenly jumps from 1GB to 50GB+
- S3 PUT request costs spike 10x
- Checkpoint duration doubles overnight
- Happens after rescaling, state schema change, or RocksDB compaction

### Root Cause
Incremental checkpoints upload only the delta (new SST files since last checkpoint). But certain events cause a "full checkpoint equivalent":

1. **RocksDB compaction**: Compaction merges SST files → new large files → uploaded as delta
2. **Rescaling**: After parallelism change, key groups are redistributed → new state → full upload
3. **Checkpoint file merging disabled**: Many small SST files accumulate
4. **State schema change**: Forces state migration → rewrite all state

### Diagnosis
```bash
# Check checkpoint sizes over time
curl http://jobmanager:8081/jobs/<job-id>/checkpoints | \
  jq '[.history[] | {id: .id, size: .state_size, duration: .end_to_end_duration}]'

# Check RocksDB compaction stats
# Look in TaskManager logs for:
grep "RocksDB compaction" taskmanager.log | tail -20

# Check number of SST files per state handle
ls -la /tmp/flink-state/*/db/ | wc -l
```

### Fix
```yaml
# Enable checkpoint file merging (Flink 1.16+)
state.backend.rocksdb.checkpoint.transfer.thread.num: 4
execution.checkpointing.file-merging.enabled: true
execution.checkpointing.file-merging.max-file-size: 32mb

# Tune RocksDB to reduce compaction spikes
state.backend.rocksdb.compaction.level.max-size-level-base: 256mb
state.backend.rocksdb.compaction.style: LEVEL
state.backend.rocksdb.thread.num: 4
```

### Prevention
- Monitor `lastCheckpointSize` with alert on 5x sudden increase
- Schedule rescaling during low-traffic windows
- Use changelog state backend for very large state (Flink 1.16+)

---

## Issue #3: Checkpoint Failure - "Could Not Complete Snapshot"

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: Checkpoint chain broken, recovery point becomes stale

### Symptoms
```
ERROR AsyncCheckpointRunnable - Could not complete snapshot 1234 for operator Window(TumblingWindow)
Caused by: java.io.IOException: Could not flush and close the file system output stream to s3://bucket/checkpoints/...
Caused by: com.amazonaws.services.s3.model.AmazonS3Exception: SlowDown (Service: Amazon S3; Status Code: 503)
```

### Root Cause
Multiple potential causes:
1. **S3 throttling**: Too many PUT requests from parallel checkpoint uploads
2. **S3 eventual consistency**: Multipart upload part missing
3. **Network timeout**: Large state + slow upload
4. **Disk full**: Local RocksDB directory ran out of space
5. **State serialization error**: Corrupt or non-serializable object in state

### Diagnosis
```bash
# Check S3 request metrics in CloudWatch
aws cloudwatch get-metric-statistics --namespace AWS/S3 \
  --metric-name 5xxErrors --dimensions Name=BucketName,Value=flink-checkpoints \
  --start-time $(date -d '1 hour ago' --iso-8601) --end-time $(date --iso-8601) \
  --period 60 --statistics Sum

# Check disk space on TaskManager
df -h /tmp/flink-state/

# Check for serialization errors
grep -i "NotSerializableException\|serializ" taskmanager.log | tail -10
```

### Fix
```yaml
# S3 throttling fix: Add retry and reduce concurrency
s3.upload.max.concurrent.uploads: 4          # Default is too high
s3.part.size: 67108864                        # 64MB parts (fewer PUT requests)
s3.entropy.key: _entropy_                     # Spread across S3 prefixes
s3.entropy.length: 4

# Increase upload timeout
fs.s3a.connection.timeout: 300000
fs.s3a.socket-timeout: 300000
fs.s3a.attempts.maximum: 10

# Use S3 entropy key to avoid hot partition
state.checkpoints.dir: s3://bucket/_entropy_/checkpoints/
```

### Prevention
- Use S3 prefix randomization (entropy keys)
- Monitor S3 5xx error rate
- Provision sufficient IOPS for local disk (EBS gp3 with 16K IOPS)
- Set disk space alerts at 80%

---

## Issue #4: Restoring from Checkpoint/Savepoint Fails

**Severity**: 🔴 Critical  
**Frequency**: Medium-High  
**Impact**: Cannot recover job, potential data loss

### Symptoms
```
ERROR Execution - Exception while restoring state from savepoint
Caused by: java.lang.IllegalStateException: Failed to restore operator state
  for operator uid 'my-operator-uid'. Incompatible state schema.

OR

Caused by: org.apache.flink.util.StateMigrationException: 
  The new state serializer cannot be incompatible
```

### Root Cause
1. **Missing operator UIDs**: Operators without `.uid()` get auto-generated IDs that change on recompilation
2. **State schema change**: Changed the class structure of state objects without migration
3. **Parallelism mismatch**: Trying to restore with incompatible key group assignment
4. **Corrupted checkpoint**: S3 object deleted or corrupted
5. **Operator removed**: Pipeline topology changed, removed operator that had state

### Diagnosis
```bash
# Check what's in the savepoint
bin/flink savepoint-info s3://bucket/savepoints/savepoint-abc123

# Compare operator UIDs
bin/flink info my-job.jar | grep "uid"

# Try with --allowNonRestoredState to identify which operators fail
bin/flink run -s s3://bucket/savepoints/savepoint-abc123 \
  --allowNonRestoredState my-job.jar
```

### Fix
```java
// ALWAYS set UIDs (the #1 prevention)
stream
    .keyBy(e -> e.getKey())
    .process(new MyProcessor())
    .uid("my-processor-v1")          // ← ALWAYS SET THIS
    .name("My Processor")
    .setParallelism(64);

// For state schema evolution, implement TypeSerializerSnapshot
public class MyStateSerializerSnapshot 
    extends SimpleTypeSerializerSnapshot<MyState> {
    
    @Override
    public TypeSerializerSchemaCompatibility<MyState> 
        resolveSchemaCompatibility(TypeSerializer<MyState> newSerializer) {
        // Handle backward/forward compatibility
        return TypeSerializerSchemaCompatibility.compatibleAfterMigration();
    }
}
```

### Prevention
- **MANDATORY**: Set `.uid("stable-name")` on EVERY stateful operator
- Use TypeSerializerSnapshot for state schema evolution
- Test savepoint restore in CI/CD before deploying
- Keep at least 3 savepoints for rollback
- Never delete savepoints without confirmation restore works

---

## Issue #5: State Size Growing Unbounded (No TTL)

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: Checkpoint size grows forever, eventually OOM or checkpoint timeout

### Symptoms
- `lastCheckpointSize` grows linearly day over day
- RocksDB disk usage growing without bound
- TaskManager eventually OOM or checkpoint takes > 30 min
- MapState or ListState keeps accumulating entries

### Root Cause
Keyed state entries are never cleaned up. Common scenarios:
1. MapState for "user sessions" but sessions never expire
2. ListState accumulating events without upper bound
3. ValueState updated for millions of keys that never appear again
4. Join state holding "left side" forever waiting for match

### Diagnosis
```bash
# Monitor state size growth
curl http://jobmanager:8081/jobs/<job-id>/checkpoints | \
  jq '[.history[] | {id: .id, size_mb: (.state_size/1048576)}]'

# Check key cardinality (approximate)
# In your operator, add a counter metric:
getRuntimeContext().getMetricGroup().gauge("stateKeys", () -> mapState.keys().spliterator().estimateSize());
```

### Fix
```java
// Fix 1: Enable State TTL (most common fix)
StateTtlConfig ttlConfig = StateTtlConfig
    .newBuilder(Time.days(7))                    // Expire after 7 days
    .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
    .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
    .cleanupFullSnapshot()                       // Clean during checkpoint
    .cleanupInRocksdbCompactFilter(1000)         // Clean during compaction
    .build();

ValueStateDescriptor<MyState> descriptor = new ValueStateDescriptor<>("my-state", MyState.class);
descriptor.enableTimeToLive(ttlConfig);
myState = getRuntimeContext().getState(descriptor);

// Fix 2: Manual cleanup with timers
@Override
public void processElement(Event event, Context ctx, Collector<Output> out) {
    // Register cleanup timer
    ctx.timerService().registerProcessingTimeTimer(
        ctx.timerService().currentProcessingTime() + EXPIRY_MS);
    myState.update(event);
}

@Override
public void onTimer(long timestamp, OnTimerContext ctx, Collector<Output> out) {
    myState.clear();  // Explicit cleanup
}

// Fix 3: Bound collection state
if (listState.get().spliterator().estimateSize() > MAX_ENTRIES) {
    // Evict oldest entries
    List<Event> events = new ArrayList<>();
    listState.get().forEach(events::add);
    events = events.subList(events.size() - MAX_ENTRIES, events.size());
    listState.update(events);
}
```

### Prevention
```yaml
# RocksDB compaction-based TTL cleanup (production config)
state.backend.rocksdb.compaction.filter.cleanup-strategy: ROCKSDB_COMPACTION_FILTER
state.backend.rocksdb.compaction.filter.query-frequency: 1000
```
- ALWAYS configure TTL for any MapState or ListState
- Set alerts on checkpoint size growth rate (> 10% per day = problem)
- Review state cardinality during code review

---

## Issue #6: RocksDB Write Stall / Slowdown

**Severity**: 🟡 Warning  
**Frequency**: Medium-High  
**Impact**: Processing throughput drops, latency spikes, potential checkpoint timeout

### Symptoms
```
WARN  RocksDB - Write stall: L0 file count exceeded soft_pending_compaction_bytes_limit
```
- Periodic latency spikes (every few minutes)
- Throughput drops to 0 for several seconds
- RocksDB compaction pending bytes metric spikes
- Happens more under high write load

### Root Cause
RocksDB has write stalls when:
1. L0 files exceed `level0_slowdown_writes_trigger` (20 files) → write slowed
2. L0 files exceed `level0_stop_writes_trigger` (36 files) → write stopped
3. Pending compaction bytes exceed soft/hard limits
4. MemTable count exceeds limit (waiting for flush)

This happens when write speed > compaction speed.

### Diagnosis
```bash
# Check RocksDB stats in TM logs
grep "Write stall\|compaction\|Level-0" taskmanager.log | tail -20

# Monitor via metrics (if configured)
# flink_taskmanager_job_task_operator_rocksdb_compaction_pending
# flink_taskmanager_job_task_operator_rocksdb_num_running_compactions
```

### Fix
```yaml
# Increase compaction threads
state.backend.rocksdb.thread.num: 8              # Default is 2, increase for SSD

# Increase write buffer to absorb bursts
state.backend.rocksdb.writebuffer.size: 256mb     # Default 64MB
state.backend.rocksdb.writebuffer.count: 5        # Default 2

# Increase L0 triggers (trade read perf for write stability)
state.backend.rocksdb.compaction.level.use-dynamic-size: true

# Use faster compaction
state.backend.rocksdb.compaction.style: UNIVERSAL  # Better for write-heavy
```

### Prevention
- Use SSDs (NVMe) for state directory — never spinning disk
- Provision dedicated EBS volumes for state (io2 or gp3 with high IOPS)
- Monitor `rocksdb.compaction.pending` and alert at > 1GB

---

## Issue #7: Checkpoint File Count Explosion on S3

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: S3 LIST API costs explode, checkpoint cleanup slow, cost overrun

### Symptoms
- S3 bill spikes due to LIST/GET requests
- Millions of small files in checkpoint directory
- Checkpoint cleanup takes > 30 minutes
- AWS billing shows unexpected S3 charges ($10K+ for small files)

### Root Cause
Each incremental checkpoint creates new SST files on S3. With:
- 200 parallelism × 5 state operators × 10 SST files = 10,000 files per checkpoint
- 1 checkpoint every 2 minutes = 7,200,000 files/day
- Retained 3 checkpoints = still growing due to shared file references

S3 charges per LIST request ($0.005/1000) add up with millions of files.

### Diagnosis
```bash
# Count objects in checkpoint directory
aws s3 ls s3://bucket/checkpoints/ --recursive | wc -l

# Check directory size
aws s3 ls s3://bucket/checkpoints/ --recursive --summarize | tail -2

# Check how many checkpoints are retained but not cleaned
curl http://jobmanager:8081/jobs/<job-id>/checkpoints | jq '.counts'
```

### Fix
```yaml
# 1. Enable file merging (Flink 1.16+)
execution.checkpointing.file-merging.enabled: true
execution.checkpointing.file-merging.max-file-size: 32mb

# 2. Reduce retained checkpoints
state.checkpoints.num-retained: 2

# 3. Use entropy keys to spread S3 load
state.checkpoints.dir: s3://bucket/_entropy_/checkpoints/

# 4. Enable S3 lifecycle to clean orphans
# S3 lifecycle rule: delete incomplete multipart uploads after 1 day
# S3 lifecycle rule: delete objects with prefix "checkpoints/" older than 7 days
```

### Prevention
- Enable file merging from the start
- Set S3 lifecycle rules for automatic cleanup
- Monitor S3 object count and costs daily
- Use larger RocksDB write buffers (fewer, larger SST files)

---

## Issue #8: Split Brain After JobManager Failover

**Severity**: 🔴 Critical  
**Frequency**: Low-Medium  
**Impact**: Two instances of same job running, duplicate processing, data corruption

### Symptoms
- Two JobManagers both think they're the leader
- Two sets of TaskManagers processing the same data
- Duplicate writes to sinks
- Kafka consumer group shows double the expected partitions assigned

### Root Cause
ZooKeeper session timeout too long or network partition:
1. Active JM becomes unreachable (GC pause, network issue)
2. ZK session hasn't expired yet (timeout too long)
3. Standby JM elected as new leader
4. Original JM recovers, still thinks it's leader
5. Both JMs start managing the same job

### Diagnosis
```bash
# Check ZooKeeper leader election
echo "get /flink/leader/rest_server_lock" | bin/zkCli.sh

# Check both JMs
curl http://jm1:8081/overview
curl http://jm2:8081/overview

# Check Kafka consumer group for duplicate assignments
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group flink-my-job
```

### Fix
```yaml
# Shorter ZK session timeout (detect failure faster)
high-availability.zookeeper.client.session-timeout: 15000  # 15s (default 60s)
high-availability.zookeeper.client.connection-timeout: 15000

# Fencer mechanism (Flink 1.15+ with K8s HA)
high-availability.type: kubernetes
kubernetes.leader-election.lease-duration: 15s
kubernetes.leader-election.renew-deadline: 10s
kubernetes.leader-election.retry-period: 3s
```

### Prevention
- Use Kubernetes-based HA (stronger fencing than ZooKeeper)
- Set `high-availability.jobmanager.port` to unique value per JM
- Enable fencing tokens for JobManager identification
- Monitor leader election events

---

## Issue #9: Savepoint Takes Too Long / Blocks Processing

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Processing stalls during savepoint, latency spike, missed SLAs

### Symptoms
- Savepoint takes 30+ minutes for large state
- Processing throughput drops to 0 during savepoint
- Latency spikes coincide with savepoint triggers
- Savepoint size is full state (not incremental)

### Root Cause
Savepoints are always FULL snapshots (not incremental like checkpoints):
- They serialize ALL state to a canonical format
- With 1TB RocksDB state, this means reading and uploading 1TB
- Uses aligned barriers (blocks processing during alignment)
- Cannot use unaligned checkpoints for savepoints

### Diagnosis
```bash
# Check savepoint progress
curl http://jobmanager:8081/jobs/<job-id>/savepoints/<trigger-id>

# Monitor savepoint size vs checkpoint size
# Savepoint should be ≈ total state size
# Checkpoint should be << total state size (incremental)
```

### Fix
```java
// Option 1: Use native (non-canonical) savepoint format (Flink 1.15+)
// Faster but only compatible with same state backend
env.getCheckpointConfig().setSavepointFormatType(SavepointFormatType.NATIVE);

// Option 2: Take checkpoint and promote to savepoint
// Use RETAIN_ON_CANCELLATION + stop-with-checkpoint
```

```bash
# Stop with checkpoint (faster than savepoint for large state)
curl -X POST http://jobmanager:8081/jobs/<job-id>/stop \
  -H "Content-Type: application/json" \
  -d '{"drain": false, "targetDirectory": "s3://bucket/savepoints/"}'
```

### Prevention
- Use native savepoint format for internal upgrades
- Schedule savepoints during low-traffic windows
- Pre-warm: trigger a checkpoint right before savepoint (reduces delta)
- For very large state (>1TB), use stop-with-checkpoint instead

---

## Issue #10: Checkpoint Coordinator Overloaded

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Checkpoints delayed, checkpoint interval becomes irregular

### Symptoms
- Gap between checkpoints is much larger than configured interval
- JobManager CPU at 100%
- Checkpoint acknowledgment processing slow
- Many pending confirmations in checkpoint coordinator

### Root Cause
With high parallelism (1000+ subtasks), the checkpoint coordinator must:
1. Track state handles from every subtask
2. Process ACKs (potentially thousands per checkpoint)
3. Manage shared state references
4. Coordinate with external systems (ZK/S3)

Single-threaded coordinator becomes bottleneck.

### Diagnosis
```bash
# Check JM thread dump for checkpoint coordinator
jstack <jm-pid> | grep -A 20 "CheckpointCoordinator"

# Check time between checkpoints
curl http://jobmanager:8081/jobs/<job-id>/checkpoints | \
  jq '[.history[] | {id, trigger_timestamp}] | [.[0].trigger_timestamp - .[1].trigger_timestamp]'
```

### Fix
```yaml
# Increase JM resources
jobmanager.memory.process.size: 8192m
jobmanager.memory.jvm-metaspace.size: 512m

# Reduce checkpoint frequency for very large jobs
execution.checkpointing.interval: 300000  # 5 min for 1000+ parallelism

# Reduce concurrent operators being tracked
# Use slot sharing to combine operators
```

### Prevention
- Scale JM resources with parallelism (rule: 4GB for < 500 subtasks, 8GB for < 2000, 16GB for > 2000)
- Don't set checkpoint interval too aggressively for large jobs
- Monitor JM CPU and GC time

---

## Issue #11: State Backend Corruption After Unclean Shutdown

**Severity**: 🔴 Critical  
**Frequency**: Low  
**Impact**: Job cannot start, state unrecoverable without backup

### Symptoms
```
ERROR RocksDBStateBackend - Failed to initialize RocksDB
Caused by: org.rocksdb.RocksDBException: Corruption: block checksum mismatch
```
- Happens after node crash, power failure, or kill -9
- RocksDB WAL (Write-Ahead Log) corrupted
- Cannot restore from local state

### Root Cause
RocksDB WAL on local disk was not flushed before crash. The in-memory MemTable changes are lost and WAL is partially written.

### Diagnosis
```bash
# Check RocksDB integrity
# (requires RocksDB tools installed)
ldb --db=/tmp/flink-state/job-id/db checkconsistency

# Check if local recovery was enabled
grep "state.backend.local-recovery" flink-conf.yaml
```

### Fix
```bash
# Option 1: Delete local state, restore from S3 checkpoint
rm -rf /tmp/flink-state/
# Job will restore from last good checkpoint on S3

# Option 2: If local recovery was enabled with corruption
# Disable local recovery temporarily and restart
```

```yaml
# Force restore from remote checkpoint
state.backend.local-recovery: false  # Temporarily disable
# After successful start, re-enable:
# state.backend.local-recovery: true
```

### Prevention
```yaml
# Use reliable local storage
state.backend.rocksdb.localdir: /mnt/nvme/flink-state  # Dedicated NVMe

# Enable WAL sync (slower but safer)
state.backend.rocksdb.write-batch-size: 2mb

# Always have remote checkpoints as backup
state.backend.local-recovery: true
state.checkpoints.dir: s3://bucket/checkpoints  # Remote backup always exists
```

---

## Issue #12: Checkpoint Subsumed - "Discarding Checkpoint Because a More Recent Checkpoint Was Completed"

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Wasted resources (checkpoint work thrown away), inconsistent recovery points

### Symptoms
```
INFO CheckpointCoordinator - Discarding checkpoint 5 because a more recent checkpoint 6 was completed.
```
- Frequent subsuming means checkpoints are overlapping
- Wasted upload bandwidth and compute

### Root Cause
Checkpoint N+1 completes before checkpoint N (out of order):
- Checkpoint N started first but hit a slow subtask
- Checkpoint N+1 started after min-pause and completed faster
- Checkpoint N is now outdated (subsumed)

### Diagnosis
```bash
# Check checkpoint timing overlap
curl http://jobmanager:8081/jobs/<job-id>/checkpoints | \
  jq '.history[] | {id, trigger_timestamp, end_to_end_duration}'
```

### Fix
```yaml
# Ensure checkpoints don't overlap
execution.checkpointing.max-concurrent-checkpoints: 1  # Only 1 at a time
execution.checkpointing.min-pause: 120000              # 2 min gap between end of one and start of next
```

### Prevention
- `max-concurrent-checkpoints: 1` should be the default for production
- Set `min-pause` > expected checkpoint duration
- Monitor average checkpoint duration to tune interval

---

## Issue #13: Incremental Checkpoint - Shared State File Cleanup Race Condition

**Severity**: 🔴 Critical  
**Frequency**: Low-Medium  
**Impact**: Checkpoint restore fails because shared SST files were deleted

### Symptoms
```
ERROR StreamTaskStateInitializerImpl - Failed to restore state
Caused by: java.io.FileNotFoundException: s3://bucket/checkpoints/.../shared/sst-0001
```
- Happens after checkpoint cleanup
- One checkpoint's shared files were still referenced by another

### Root Cause
Incremental checkpoints share SST files between checkpoints. When checkpoint N is cleaned up, it may delete shared files still needed by checkpoint N+1:
- Race condition in reference counting
- S3 eventual consistency (DELETE visible before GET returns 404)
- Bug in older Flink versions (fixed in 1.14.3+)

### Diagnosis
```bash
# Check if file exists on S3
aws s3 ls s3://bucket/checkpoints/.../shared/sst-0001

# Check retained checkpoints and their shared references
curl http://jobmanager:8081/jobs/<job-id>/checkpoints | \
  jq '.latest.completed.external_path'
```

### Fix
```yaml
# Retain more checkpoints (reduces chance of shared file deletion)
state.checkpoints.num-retained: 5

# Use changelog state backend (Flink 1.16+) which avoids shared file issues
state.changelog.enabled: true
state.changelog.storage: filesystem
state.changelog.storage.filesystem.base-path: s3://bucket/changelog/
```

### Prevention
- Upgrade to Flink 1.17+ (improved shared state management)
- Retain 3-5 checkpoints (not just 1)
- Use changelog state backend for critical jobs
- Monitor for FileNotFoundException in TM logs

---

## Issue #14: Checkpoint Decline - "TaskManager Not Responding"

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Checkpoint fails, recovery point stale

### Symptoms
```
WARN CheckpointCoordinator - Decline checkpoint 99 by task [...] of job [...].
Reason: The TaskManager is not responding.
```
- One specific TM consistently blocks checkpoints
- Other TMs complete their part quickly
- The "slow" TM might be GC-pausing or overloaded

### Root Cause
1. **GC pause**: Full GC on TaskManager freezes all threads including checkpoint
2. **Network partition**: JM cannot reach TM for barrier injection
3. **TM overloaded**: CPU at 100%, cannot process checkpoint barrier in time
4. **Disk I/O saturation**: RocksDB snapshot blocked on slow disk

### Diagnosis
```bash
# Check GC logs for the specific TM
grep "Full GC\|GC pause" taskmanager-<tm-id>.log | tail -10

# Check TM connectivity
curl http://taskmanager:port/metrics

# Check I/O wait
iostat -x 1 5  # On the specific TM node
```

### Fix
```yaml
# GC tuning (use G1GC with appropriate settings)
env.java.opts.taskmanager: >-
  -XX:+UseG1GC
  -XX:MaxGCPauseMillis=100
  -XX:G1HeapRegionSize=32m
  -XX:+ParallelRefProcEnabled
  -XX:+ExplicitGCInvokesConcurrent
  -Xlog:gc*:file=/opt/flink/log/gc.log:time,uptime:filecount=5,filesize=100m

# Reduce heap pressure (offload to managed memory)
taskmanager.memory.task.heap.size: 2048m      # Keep heap small
taskmanager.memory.managed.fraction: 0.5       # Generous managed memory
```

### Prevention
- Keep task heap small (< 4GB) to minimize GC pause
- Use G1GC with `-XX:MaxGCPauseMillis=100`
- Provision fast local disk (NVMe) for state directory
- Set network timeout appropriately:
```yaml
heartbeat.timeout: 180000
heartbeat.interval: 10000
```
