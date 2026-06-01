# Job Lifecycle & Recovery Issues (#96-100)

> These issues cover job submission, cancellation, recovery, and the overall lifecycle management challenges at scale.

---

## Issue #96: Job Stuck in INITIALIZING State

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Job never starts processing, deadline missed

### Symptoms
- Job status: `INITIALIZING` for > 5 minutes
- No TaskManager logs showing operator initialization
- JobManager logs show slot allocation but no task deployment

### Root Cause
1. **State restore taking too long**: Large checkpoint being downloaded from S3
2. **Insufficient resources**: Slots requested but not available
3. **Deadlock in initialization**: Custom operator `open()` blocking
4. **Network issue**: Cannot reach checkpoint storage
5. **Classloader issue**: Class resolution hanging

### Diagnosis
```bash
# Check job status details
curl http://jobmanager:8081/jobs/<job-id> | jq '.state, .timestamps'

# Check if tasks are deployed
curl http://jobmanager:8081/jobs/<job-id>/vertices | jq '.[].tasks'

# Check TaskManager status
curl http://jobmanager:8081/taskmanagers | jq '.taskmanagers[].freeSlots'

# Check for state restore progress in TM logs
grep -i "restore\|loading\|initializ" taskmanager.log | tail -20
```

### Fix
```yaml
# For slow state restore: Increase download threads
state.backend.rocksdb.checkpoint.transfer.thread.num: 8  # More parallel downloads

# For resource issues: Ensure enough TMs
kubernetes.taskmanager.replicas: 50  # Pre-provision

# For initialization timeout
resourcemanager.taskmanager-timeout: 300000  # 5 min TM registration timeout

# For blocking open() - add timeout
```

```java
// Fix blocking open() calls
@Override
public void open(Configuration params) throws Exception {
    // Don't block forever on external connections
    CompletableFuture<Connection> future = CompletableFuture.supplyAsync(() -> {
        return createConnection();
    });
    connection = future.get(30, TimeUnit.SECONDS);  // Timeout!
}
```

### Prevention
- Monitor initialization time metric
- Set timeout in all `open()` calls that connect to external systems
- Pre-provision TaskManagers for faster startup
- Use local recovery to avoid downloading full state from S3

---

## Issue #97: Job Restart Loop (CrashLoopBackOff Equivalent)

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Job never stabilizes, continuous restart, no progress

### Symptoms
```
INFO  Execution - Recovering job [...], attempt #15.
WARN  RestartStrategy - Restarting job for the 15th time.
```
- Job starts, processes briefly, crashes, restarts, repeats
- Restart counter incrementing rapidly
- Each restart from same checkpoint (same failure point)
- Eventually exhausts restart attempts → FAILED state

### Root Cause
1. **Poison pill message**: One record always causes NPE/exception
2. **External system permanently down**: Sink cannot connect, retries exhaust
3. **Resource leak**: Each restart leaks memory until OOM
4. **State corruption**: Checkpoint itself contains bad data
5. **Bug in operator**: Deterministic crash on specific state access

### Diagnosis
```bash
# Check exception from last failure
curl http://jobmanager:8081/jobs/<job-id>/exceptions | jq '.all_exceptions[0]'

# Check if same exception every time
curl http://jobmanager:8081/jobs/<job-id>/exceptions | \
  jq '[.all_exceptions[].exception] | unique'

# Check restart count
curl http://jobmanager:8081/jobs/<job-id> | jq '.state, ."status-counts"'
```

### Fix
```java
// For poison pill: Skip bad records
public class FaultTolerantProcessor extends ProcessFunction<Event, Result> {
    private static final OutputTag<Event> FAILED = new OutputTag<>("failed") {};
    
    @Override
    public void processElement(Event event, Context ctx, Collector<Result> out) {
        try {
            Result result = process(event);
            out.collect(result);
        } catch (Exception e) {
            LOG.error("Failed to process event: {}, skipping", event.getId(), e);
            ctx.output(FAILED, event);  // Route to dead letter queue
            metrics.counter("processing-failures").inc();
        }
    }
}
```

```yaml
# Use failure-rate restart strategy (limit restart frequency)
restart-strategy: failure-rate
restart-strategy.failure-rate.max-failures-per-interval: 10
restart-strategy.failure-rate.failure-rate-interval: 300s  # 10 failures in 5 min → FAIL
restart-strategy.failure-rate.delay: 30s

# Better: Exponential backoff (avoid thundering herd)
restart-strategy: exponential-delay
restart-strategy.exponential-delay.initial-backoff: 5s
restart-strategy.exponential-delay.max-backoff: 300s     # Max 5 min between restarts
restart-strategy.exponential-delay.backoff-multiplier: 2.0
restart-strategy.exponential-delay.reset-backoff-threshold: 600s  # Reset after 10 min stable
restart-strategy.exponential-delay.jitter-factor: 0.1
```

### Prevention
- ALWAYS wrap processing in try-catch (never let exceptions crash the job)
- Use dead-letter queue pattern for unprocessable records
- Use exponential-delay restart strategy
- Monitor restart frequency (> 3/hour = investigate)

---

## Issue #98: Savepoint Restore with Changed Job Topology

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Cannot upgrade job, blocked on old version

### Symptoms
```
The program topology has changed since the savepoint.
Cannot map operator 'old-operator-uid' to the new program.
```
- New job version has different operators than savepoint
- Operators added, removed, or reordered
- State mapping fails

### Root Cause
When restoring from savepoint, Flink maps state by operator UID:
- Removed operator: State exists in savepoint but no operator to restore to
- Added operator: New operator has no state in savepoint (OK if fresh start)
- Changed UID: Treated as removal + addition (state lost)

### Fix
```bash
# Option 1: Allow non-restored state (skip removed operators)
flink run -s s3://savepoint/path \
  --allowNonRestoredState \
  my-new-job.jar

# Option 2: Use State Processor API to migrate state
# Read old savepoint → transform state → write new savepoint
```

```java
// State Processor API for migration
SavepointReader savepoint = SavepointReader.read(env, "s3://savepoint/path", backend);

// Read state from old operator
DataSet<OldState> oldState = savepoint.readKeyedState(
    "old-operator-uid", new OldStateReaderFunction());

// Transform to new format
DataSet<NewState> newState = oldState.map(old -> migrate(old));

// Write to new savepoint
SavepointWriter.newSavepoint(backend, 128)
    .withOperator("new-operator-uid", new NewStateBootstrapFunction(newState))
    .write("s3://savepoint/migrated");
```

### Prevention
- Document operator UIDs in code (never change them)
- When removing operator: first deploy with `allowNonRestoredState`, take new savepoint
- When renaming UID: use State Processor API to migrate
- Maintain UID mapping document for team

---

## Issue #99: Job Cancellation Hangs (Cannot Cancel)

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Cannot stop job, resources locked, cannot redeploy

### Symptoms
- `flink cancel <job-id>` hangs
- Job status stuck in `CANCELLING`
- TaskManagers not responding to cancel signal
- Cannot reclaim resources for new deployment

### Root Cause
1. **Operator stuck in blocking call**: `invoke()` or `close()` blocking forever
2. **Thread interrupted but not handling interruption**: Ignoring InterruptedException
3. **GC pause**: TM in Full GC, not processing cancel signal
4. **Network partition**: JM cannot reach TM

### Diagnosis
```bash
# Check job state
curl http://jobmanager:8081/jobs/<job-id> | jq '.state'

# Force-cancel (with savepoint) via REST
curl -X PATCH http://jobmanager:8081/jobs/<job-id>?mode=cancel

# Check TaskManager thread dumps for stuck threads
curl http://jobmanager:8081/taskmanagers/<tm-id>/thread-dump
```

### Fix
```bash
# Force stop (without savepoint) - last resort
curl -X PATCH "http://jobmanager:8081/jobs/<job-id>?mode=cancel"

# If that fails: kill TaskManager pods
kubectl delete pod flink-taskmanager-<id> --grace-period=0 --force

# For Kubernetes Operator: delete the FlinkDeployment
kubectl delete flinkdeployment my-job --grace-period=60
```

```java
// Fix stuck operators: handle interruption properly
@Override
public void invoke(Record record, Context ctx) throws Exception {
    try {
        // Check for interruption in long-running operations
        if (Thread.currentThread().isInterrupted()) {
            throw new InterruptedException("Task cancelled");
        }
        blockingOperation(record);
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();  // Restore flag
        throw e;  // Let Flink handle cancellation
    }
}

@Override
public void close() throws Exception {
    // Don't block forever in close()!
    if (connection != null) {
        try {
            connection.close();  // Set timeout on connection
        } catch (Exception e) {
            LOG.warn("Error closing connection", e);
        }
    }
}
```

### Prevention
- Always handle `InterruptedException` in operators
- Set timeouts on all blocking operations (especially in `close()`)
- Monitor cancellation duration (alert if > 60s)
- Use `task.cancellation.timeout: 180000` to auto-kill stuck tasks

```yaml
task.cancellation.interval: 30000      # Check every 30s
task.cancellation.timeout: 180000      # Force-kill after 3 min
task.cancellation.timers.timeout: 10000
```

---

## Issue #100: Split-Brain Recovery - Duplicate Processing After Network Partition

**Severity**: 🔴 Critical  
**Frequency**: Rare (but catastrophic)  
**Impact**: Duplicate records in sink, financial discrepancies, data integrity violation

### Symptoms
- After network partition recovery, duplicate records appear
- Two instances of job were briefly running simultaneously
- Consumer group shows double partition assignment
- Sink database shows duplicate keys with different values

### Root Cause
During network partition:
1. JM loses contact with some TMs
2. JM triggers failover → restarts tasks on other TMs
3. Original TMs are still alive (just network-isolated)
4. Both old and new tasks process same data briefly
5. Network heals → duplicates in sink

This is a fundamental distributed systems problem. Flink's fencing tokens help but aren't perfect with async sinks.

### Fix
```java
// Solution 1: Idempotent sinks (best defense against duplicates)
public class IdempotentDatabaseSink extends RichSinkFunction<Record> {
    @Override
    public void invoke(Record record, Context ctx) {
        // Upsert with deterministic key
        String idempotencyKey = record.getEventId() + "_" + record.getCheckpointId();
        
        // INSERT ON CONFLICT UPDATE (idempotent)
        db.execute(
            "INSERT INTO results (id, value, updated_at) VALUES (?, ?, ?) " +
            "ON CONFLICT (id) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
            idempotencyKey, record.getValue(), record.getTimestamp());
    }
}

// Solution 2: Fencing with epoch-based writes
public class FencedSink extends RichSinkFunction<Record> {
    private long currentEpoch;
    
    @Override
    public void open(Configuration params) {
        // Get current attempt number (epoch) from runtime context
        currentEpoch = getRuntimeContext().getAttemptNumber();
        // Register fence in external system
        db.execute("INSERT INTO fences (job_id, epoch) VALUES (?, ?) " +
                  "ON CONFLICT DO UPDATE SET epoch = GREATEST(epoch, ?)",
                  JOB_ID, currentEpoch, currentEpoch);
    }
    
    @Override
    public void invoke(Record record, Context ctx) {
        // Write with epoch - only latest epoch's writes are valid
        db.execute("INSERT INTO results (id, value, epoch) VALUES (?, ?, ?) " +
                  "WHERE ? >= (SELECT epoch FROM fences WHERE job_id = ?)",
                  record.getId(), record.getValue(), currentEpoch, currentEpoch, JOB_ID);
    }
}
```

```yaml
# Reduce split-brain window
heartbeat.timeout: 30000             # Detect failure faster (default 50s)
heartbeat.interval: 5000             # More frequent heartbeats
jobmanager.execution.failover-strategy: region  # Only restart affected region

# Kubernetes fencing (stronger than ZooKeeper)
high-availability.type: kubernetes
kubernetes.leader-election.lease-duration: 15s
kubernetes.leader-election.renew-deadline: 10s
```

### Prevention
- **Primary defense**: Make ALL sinks idempotent (upsert, not insert)
- Use Kubernetes-based HA (better fencing than ZooKeeper)
- Shorten heartbeat timeout to minimize split-brain window
- Add epoch/fencing to external system writes
- Monitor for duplicate detection in downstream systems
- For financial systems: implement reconciliation pipeline that detects duplicates

---

## Summary: The 5 Most Critical Patterns Across All 100 Issues

### Pattern 1: Always Handle Failure Gracefully
Issues #1, #46, #97 — Never let a single bad record crash your job.
```java
try { process(record); } 
catch (Exception e) { routeToDeadLetter(record, e); }
```

### Pattern 2: Bound Everything
Issues #5, #20, #59, #60 — Every state, buffer, and resource must have limits.
```java
// TTL for state, max size for buffers, timeout for operations
descriptor.enableTimeToLive(ttlConfig);
```

### Pattern 3: Make Sinks Idempotent
Issues #57, #91, #95, #100 — Exactly-once is hard; idempotent sinks make it achievable.
```sql
INSERT ... ON CONFLICT DO UPDATE  -- Always safe to retry
```

### Pattern 4: Monitor Before It Breaks
Issues #1, #15, #41, #54 — Every critical metric should have a WARNING alert before it becomes CRITICAL.
```yaml
# Alert at 70% of limit, not at 100%
alert: lag > 70% of SLA threshold
```

### Pattern 5: Test Recovery, Not Just Happy Path
Issues #4, #70, #98 — Your job will crash. Test that it recovers correctly.
```bash
# CI/CD must include: savepoint → stop → upgrade → restore → verify
```
