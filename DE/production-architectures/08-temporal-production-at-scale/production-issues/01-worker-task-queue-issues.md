# Worker & Task Queue Production Issues (#1 - #15)

## Issue #1: Schedule-to-Start Latency Explosion [CRITICAL]

### Symptoms
- `temporal_activity_schedule_to_start_latency` spikes from 50ms to 30s+
- Workflow task completions drop dramatically
- SLA breaches across all workflows on affected task queue
- Customer-facing timeouts increase

### Root Cause
Workers cannot keep up with incoming task rate. Common triggers:
- Worker pod OOM kills reduced fleet by 40%
- Upstream traffic spike (flash sale, batch job start)
- Activity execution time increased (downstream dependency slow)
- Worker deployment caused rolling restart, temporarily halving capacity

### Impact
- **Business**: Payment processing delayed, orders stuck, SLA breach
- **System**: Cascading timeouts, retry storms, queue depth grows exponentially
- **Scale**: At 100K+ workflows/min, 30s latency = 3M queued tasks

### Detection
```promql
# Alert: Schedule-to-Start > 5s for 2 minutes
temporal_activity_schedule_to_start_latency_seconds{quantile="0.99"} > 5

# Queue depth growing
rate(temporal_matching_tasks_added_total[5m]) > rate(temporal_matching_tasks_dispatched_total[5m])
```

### Resolution

**Immediate (< 5 min):**
```bash
# 1. Scale workers immediately
kubectl scale deployment temporal-worker-payment --replicas=50

# 2. Check current queue depth
tctl taskqueue describe --task-queue payment-processing-tq

# 3. Verify workers are polling
tctl taskqueue list-partition --task-queue payment-processing-tq
```

**Short-term (< 1 hour):**
```go
// Increase concurrent activity execution on existing workers
workerOptions := worker.Options{
    MaxConcurrentActivityExecutionSize:     500,  // was 200
    MaxConcurrentActivityTaskPollers:        20,   // was 5
    MaxConcurrentWorkflowTaskExecutionSize: 200,  // was 100
    MaxConcurrentWorkflowTaskPollers:        10,   // was 5
}
```

**Long-term:**
```go
// Implement KEDA autoscaler based on schedule-to-start latency
// keda-scaler.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: temporal-worker-scaler
spec:
  scaleTargetRef:
    name: temporal-worker-payment
  minReplicaCount: 10
  maxReplicaCount: 200
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      metricName: schedule_to_start_latency
      query: |
        temporal_activity_schedule_to_start_latency_seconds{
          task_queue="payment-processing-tq",
          quantile="0.95"
        }
      threshold: "2"
```

### Prevention
- HPA/KEDA autoscaling on schedule-to-start latency
- Pre-scale before known traffic events
- Set `ScheduleToStartTimeout` on activities to fail fast vs wait forever
- Multiple task queues with priority (don't let batch starve real-time)

---

## Issue #2: Worker Deadlock Detection Timeout [CRITICAL]

### Symptoms
- Worker logs: `Potential deadlock detected. workflow goroutine didn't yield for over 1s`
- Workflow tasks repeatedly fail and retry
- Same workflow tasks keep appearing on task queue
- Worker CPU appears idle despite high task queue depth

### Root Cause
Workflow code is executing a blocking/long operation that doesn't yield to the Temporal SDK:
- Synchronous HTTP call in workflow code (WRONG - should be activity)
- CPU-intensive computation (JSON parsing 100MB payload in workflow)
- Mutex lock contention in workflow code
- Infinite loop without timer/sleep

### Impact
- **Business**: Affected workflows stuck, cannot make progress
- **System**: Worker goroutine slots consumed, other workflows starved
- **Scale**: One bad workflow type can block entire worker

### Detection
```promql
# Deadlock detection events
increase(temporal_worker_task_slots_used{worker_type="WorkflowWorker"}[5m]) == 0
  AND temporal_workflow_task_schedule_to_start_latency_seconds > 0
```

### Resolution
```go
// WRONG - This causes deadlock
func MyWorkflow(ctx workflow.Context, input Input) error {
    // NEVER do this in workflow code
    resp, err := http.Get("https://api.example.com/data")  // BLOCKS!
    result := heavyComputation(input.LargePayload)          // CPU BOUND!
    mu.Lock()                                               // CONTENTION!
    
    return nil
}

// CORRECT - Move to activity
func MyWorkflow(ctx workflow.Context, input Input) error {
    var result ComputeResult
    err := workflow.ExecuteActivity(ctx, ComputeActivity, input).Get(ctx, &result)
    if err != nil {
        return err
    }
    return nil
}

// For unavoidable CPU work in workflow, use workflow.Go for concurrent work
func MyWorkflow(ctx workflow.Context, input Input) error {
    // Break up work with yields
    for i, chunk := range input.Chunks {
        // Process chunk
        processChunk(chunk)
        
        // Yield every N iterations to avoid deadlock detection
        if i%100 == 0 {
            _ = workflow.Sleep(ctx, 0) // Yields without actually sleeping
        }
    }
    return nil
}
```

### Prevention
- Code review rule: NO I/O, NO network, NO blocking in workflow code
- Static analysis to detect `http.`, `net.`, `os.` in workflow packages
- Set `DeadlockDetectionTimeout` appropriately (default 1s)
- Load testing with realistic payloads

---

## Issue #3: Sticky Queue Stale Worker Problem [HIGH]

### Symptoms
- Some workflows experience 10-30s delays for workflow tasks
- `StickyScheduleToStartTimeout` fires frequently
- Workflow latency is bimodal (fast for most, slow for some)
- Issue correlates with worker deployments/restarts

### Root Cause
Temporal uses "sticky execution" to cache workflow state on the worker that last processed it.
When that worker dies/restarts, tasks wait on the sticky queue until timeout, then fall back to
normal queue. During rolling deployments, many workflows' sticky queues point to dead workers.

### Impact
- **Business**: 5-30s latency spike for affected workflows during deployments
- **System**: Wasted timeout waiting for dead sticky workers
- **Scale**: At 10M concurrent workflows, rolling 100 workers = 100K affected workflows

### Detection
```promql
# Sticky cache miss rate spike
rate(temporal_sticky_cache_miss_total[5m]) > 100

# Elevated workflow task latency during deployments
temporal_workflow_task_schedule_to_start_latency_seconds{sticky="true", quantile="0.99"} > 10
```

### Resolution
```go
// Reduce sticky timeout to fail fast to normal queue
workerOptions := worker.Options{
    StickyScheduleToStartTimeout: 5 * time.Second,  // Default is 5s, reduce to 2s for fast failover
}

// For zero-downtime deployments, drain sticky cache before shutdown
func gracefulShutdown(w worker.Worker) {
    // Stop accepting new tasks
    w.Stop()
    
    // Wait for in-flight tasks to complete
    // Sticky cache automatically invalidates on worker stop
}
```

**Deployment strategy to minimize impact:**
```yaml
# Kubernetes rolling update with proper settings
spec:
  strategy:
    rollingUpdate:
      maxSurge: 50%        # Bring up new pods before killing old
      maxUnavailable: 25%  # Limit concurrent terminations
  template:
    spec:
      terminationGracePeriodSeconds: 120  # Allow in-flight to complete
      containers:
      - name: temporal-worker
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 30"]  # Drain period
```

### Prevention
- `StickyScheduleToStartTimeout` = 2-5s (not too high)
- Blue/green deployments instead of rolling (instant cutover)
- Pre-warm new workers before draining old ones
- Monitor sticky cache hit rate as deployment health signal

---

## Issue #4: Task Queue Partition Imbalance [HIGH]

### Symptoms
- Some workers are idle while others are overloaded
- Uneven CPU/memory across worker pods
- Some task queue partitions have high depth, others empty
- `temporal_matching_tasks_added_total` varies wildly across partitions

### Root Cause
Task queues are partitioned (default 4 partitions). Workers poll specific partitions.
If partition assignment is uneven or task routing is skewed:
- Hash-based routing creates hotspots
- Some partitions have more workers polling than others
- Task forwarding between partitions has additional latency

### Impact
- **Business**: Inconsistent latency (some workflows fast, some slow)
- **System**: Under-utilization of fleet, one partition becomes bottleneck
- **Scale**: At 1000+ workers, imbalance wastes 20-40% of capacity

### Detection
```promql
# Per-partition depth comparison
stddev(temporal_matching_tasks_pending{task_queue="my-queue"}) by (partition) > 
  avg(temporal_matching_tasks_pending{task_queue="my-queue"}) * 0.5
```

### Resolution
```go
// Server-side: Increase partition count for high-throughput queues
// dynamic_config.yaml
matching.numTaskqueueWritePartitions:
  - value: 16  # Increase from default 4
    constraints:
      taskQueueName: "payment-processing-tq"

matching.numTaskqueueReadPartitions:
  - value: 16
    constraints:
      taskQueueName: "payment-processing-tq"

// Worker-side: Increase pollers to cover more partitions
workerOptions := worker.Options{
    MaxConcurrentActivityTaskPollers: 20,  // More pollers = better partition coverage
}
```

### Prevention
- Set partition count proportional to worker count (rule: partitions = workers / 5)
- Monitor per-partition metrics
- Use consistent task queue naming (avoid dynamic queue names that fragment)
- Regular rebalancing during maintenance windows

---

## Issue #5: Worker Memory Leak from Workflow Cache [HIGH]

### Symptoms
- Worker memory grows steadily over hours/days
- Eventually triggers OOM kill
- GC pressure increases, latency spikes before OOM
- Memory growth correlates with unique workflow types processed

### Root Cause
Temporal workers cache workflow state in memory for sticky execution. If:
- Cache size is too large for available memory
- Workflows have large local state (big variables, large arrays)
- High cardinality of workflow types exhausts cache
- Memory not released due to Go runtime behavior (heap not returned to OS)

### Impact
- **Business**: Worker OOM causes all in-flight tasks to timeout and retry
- **System**: Repeated OOM cycles cause instability
- **Scale**: At 100K+ concurrent workflows per worker, cache = multi-GB

### Detection
```promql
# Memory growth rate
deriv(container_memory_working_set_bytes{container="temporal-worker"}[1h]) > 100000000

# Cache size
temporal_sticky_cache_size > 5000
```

### Resolution
```go
// Limit workflow cache size
workerOptions := worker.Options{
    // Limit cached workflows (default is 600)
    StickyScheduleToStartTimeout: 5 * time.Second,
}

// Use workflow.WithWorkflowOptions to set cache hints
// In worker creation:
w := worker.New(c, "my-task-queue", worker.Options{
    // Reduce cache pressure
    MaxConcurrentWorkflowTaskExecutionSize: 100,
    
    // Enable workflow state eviction
    WorkflowPanicPolicy: worker.BlockWorkflow,
})

// For large-state workflows, minimize cached state
func MyWorkflow(ctx workflow.Context, input Input) error {
    // DON'T keep large data in workflow variables
    // var allRecords []Record  // BAD - stays in cache
    
    // DO pass large data through activities
    var summary Summary
    err := workflow.ExecuteActivity(ctx, ProcessAndSummarize, input.DataRef).Get(ctx, &summary)
    return err
}
```

**Memory limit with graceful handling:**
```yaml
containers:
- name: temporal-worker
  resources:
    limits:
      memory: 4Gi
    requests:
      memory: 2Gi
  env:
  - name: GOMEMLIMIT
    value: "3500MiB"  # 87.5% of limit - lets GC be aggressive before OOM
  - name: GOGC
    value: "50"       # More aggressive GC (default 100)
```

### Prevention
- Set `GOMEMLIMIT` to 85-90% of container memory limit
- Monitor cache size vs available memory ratio
- Minimize workflow state (use references, not copies)
- Regular worker restarts (every 24h) as safety net

---

## Issue #6: Activity Timeout Misconfiguration Cascade [HIGH]

### Symptoms
- Activities succeed on downstream service but Temporal marks them failed
- Duplicate activity executions (retries of already-completed work)
- `ScheduleToCloseTimeout` fires before activity completes
- Downstream services see 2x-5x expected traffic

### Root Cause
Timeout hierarchy misconfigured:
- `StartToCloseTimeout` < actual execution time (activity killed while running)
- `HeartbeatTimeout` too short for legitimate processing gaps
- `ScheduleToCloseTimeout` doesn't account for retries
- No timeout set at all (defaults to workflow timeout = hours)

### Impact
- **Business**: Duplicate charges, double bookings, inconsistent state
- **System**: Retry storms multiply load on downstream services
- **Scale**: 1M activities/hour with 5% timeout = 50K unnecessary retries/hour

### Detection
```promql
# Activity timeout rate
rate(temporal_activity_execution_failed_total{failure_reason="timeout"}[5m]) > 10

# Duplicate activity execution (same idempotency key)
rate(activity_duplicate_execution_total[5m]) > 0
```

### Resolution
```go
// WRONG: No clear timeout strategy
activityOptions := workflow.ActivityOptions{
    StartToCloseTimeout: 30 * time.Second,  // What if it legitimately takes 60s?
}

// CORRECT: Layered timeout strategy
activityOptions := workflow.ActivityOptions{
    // How long a single attempt can run
    StartToCloseTimeout: 2 * time.Minute,
    
    // Total time including all retries
    ScheduleToCloseTimeout: 10 * time.Minute,
    
    // Detect stuck activities (must heartbeat every 30s)
    HeartbeatTimeout: 30 * time.Second,
    
    // Don't wait forever for a worker to pick it up
    ScheduleToStartTimeout: 1 * time.Minute,
    
    RetryPolicy: &temporal.RetryPolicy{
        InitialInterval:    1 * time.Second,
        BackoffCoefficient: 2.0,
        MaximumInterval:    30 * time.Second,
        MaximumAttempts:    5,
        NonRetryableErrorTypes: []string{
            "InvalidInputError",
            "InsufficientFundsError",
        },
    },
}

// Activity with proper heartbeating
func ProcessLargeFile(ctx context.Context, fileRef string) error {
    // Record heartbeat with progress
    for i, chunk := range chunks {
        processChunk(chunk)
        
        // Heartbeat with progress details (resumable on retry)
        activity.RecordHeartbeat(ctx, HeartbeatProgress{
            ChunksProcessed: i + 1,
            TotalChunks:     len(chunks),
            LastChunkID:     chunk.ID,
        })
        
        // Check if cancelled
        if ctx.Err() != nil {
            return ctx.Err()
        }
    }
    return nil
}

// Resume from heartbeat on retry
func ProcessLargeFile(ctx context.Context, fileRef string) error {
    // Get last heartbeat details (for retry resume)
    var progress HeartbeatProgress
    if activity.HasHeartbeatDetails(ctx) {
        if err := activity.GetHeartbeatDetails(ctx, &progress); err == nil {
            // Resume from where we left off
            chunks = chunks[progress.ChunksProcessed:]
        }
    }
    // ... continue processing
}
```

### Prevention
- Document timeout strategy per activity type
- `StartToCloseTimeout` = 2x p99 execution time
- `HeartbeatTimeout` = 3x heartbeat interval
- Always set `ScheduleToStartTimeout` (detect worker unavailability)
- Idempotency keys on all mutating activities

---

## Issue #7: Task Queue Starvation from Long-Running Activities [HIGH]

### Symptoms
- Short activities on same task queue delayed by minutes
- Worker activity slots fully consumed
- `MaxConcurrentActivityExecutionSize` reached
- Mix of 5s and 5min activities on same queue

### Root Cause
Long-running activities (file processing, ML inference, report generation) consume all worker
slots, preventing short activities (validation, notification) from executing.

### Impact
- **Business**: Quick operations (send email, validate input) blocked behind slow operations
- **System**: Head-of-line blocking, underutilized CPU on workers
- **Scale**: 100 slots, 100 long activities = zero capacity for anything else

### Detection
```promql
# Worker slots saturated
temporal_worker_task_slots_used{worker_type="ActivityWorker"} / 
  temporal_worker_task_slots_available{worker_type="ActivityWorker"} > 0.95
```

### Resolution
```go
// WRONG: Everything on one queue
w := worker.New(c, "default-task-queue", worker.Options{
    MaxConcurrentActivityExecutionSize: 100,
})
w.RegisterActivity(QuickValidation)     // 50ms
w.RegisterActivity(ProcessLargeFile)    // 5 minutes
w.RegisterActivity(SendEmail)           // 200ms
w.RegisterActivity(TrainMLModel)        // 30 minutes

// CORRECT: Separate queues by execution profile
// Fast worker - high concurrency, short timeout
fastWorker := worker.New(c, "fast-activities-tq", worker.Options{
    MaxConcurrentActivityExecutionSize: 500,
    MaxConcurrentActivityTaskPollers:   20,
})
fastWorker.RegisterActivity(QuickValidation)
fastWorker.RegisterActivity(SendEmail)

// Slow worker - low concurrency, long timeout, heartbeat
slowWorker := worker.New(c, "slow-activities-tq", worker.Options{
    MaxConcurrentActivityExecutionSize: 10,  // Few slots, each runs long
    MaxConcurrentActivityTaskPollers:   5,
})
slowWorker.RegisterActivity(ProcessLargeFile)
slowWorker.RegisterActivity(TrainMLModel)

// In workflow, route to appropriate queue
func MyWorkflow(ctx workflow.Context, input Input) error {
    // Fast activity - different queue
    fastCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
        TaskQueue:           "fast-activities-tq",
        StartToCloseTimeout: 5 * time.Second,
    })
    
    // Slow activity - different queue
    slowCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
        TaskQueue:           "slow-activities-tq",
        StartToCloseTimeout: 30 * time.Minute,
        HeartbeatTimeout:    1 * time.Minute,
    })
    
    err := workflow.ExecuteActivity(fastCtx, QuickValidation, input).Get(ctx, nil)
    err = workflow.ExecuteActivity(slowCtx, ProcessLargeFile, input.FileRef).Get(ctx, nil)
    return err
}
```

### Prevention
- Categorize activities: fast (< 1s), medium (1s-60s), slow (> 60s)
- Dedicated task queues per category
- Different worker scaling strategies per queue
- Monitor slot utilization per queue

---

## Issue #8: Worker Graceful Shutdown Timeout [MEDIUM]

### Symptoms
- Activities interrupted mid-execution during deployments
- Kubernetes sends SIGKILL after `terminationGracePeriodSeconds`
- `context.Canceled` errors in activity logs
- Incomplete work requiring retry on new worker

### Root Cause
Worker shutdown doesn't complete before Kubernetes kills the pod:
- `terminationGracePeriodSeconds` (default 30s) < longest running activity
- Worker.Stop() waits for in-flight activities but pod killed first
- PreStop hook not configured or too short

### Impact
- **Business**: Partial work lost, activities must fully retry
- **System**: Retry amplification, potential duplicate side effects
- **Scale**: Rolling 100 workers with 50 activities each = 5000 interrupted activities

### Detection
```promql
# Pod terminations with SIGKILL
kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} == 0
  AND kube_pod_container_status_terminated == 1

# Activity retries during deployment window
increase(temporal_activity_execution_failed_total{failure_reason="canceled"}[10m]) during deployment
```

### Resolution
```go
// Worker with proper graceful shutdown
func main() {
    c, _ := client.Dial(client.Options{})
    defer c.Close()
    
    w := worker.New(c, "my-task-queue", worker.Options{
        // Allow activities to complete on shutdown
        WorkerStopTimeout: 2 * time.Minute,
    })
    
    // Register workflows and activities
    w.RegisterWorkflow(MyWorkflow)
    w.RegisterActivity(MyActivity)
    
    // Handle shutdown signals
    sigCh := make(chan os.Signal, 1)
    signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
    
    // Start worker
    go func() {
        if err := w.Run(worker.InterruptCh()); err != nil {
            log.Fatal(err)
        }
    }()
    
    // Wait for termination signal
    <-sigCh
    log.Info("Received shutdown signal, draining...")
    
    // Worker.Stop() will:
    // 1. Stop polling for new tasks
    // 2. Wait for in-flight activities to complete
    // 3. Return when all done or WorkerStopTimeout hit
    w.Stop()
    log.Info("Worker shutdown complete")
}
```

```yaml
# Kubernetes deployment
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 300  # 5 min - longer than longest activity
      containers:
      - name: temporal-worker
        lifecycle:
          preStop:
            exec:
              # Give time for load balancer to deregister
              command: ["/bin/sh", "-c", "sleep 10"]
```

### Prevention
- `terminationGracePeriodSeconds` > max activity `StartToCloseTimeout`
- Heartbeating activities can be interrupted safely (resume from heartbeat)
- PreStop hook for LB deregistration
- Monitor shutdown duration as deployment metric

---

## Issue #9: Activity Semaphore Exhaustion [MEDIUM]

### Symptoms
- Activities queued internally in worker (not reaching execution)
- Worker memory grows (queued activities buffered)
- Schedule-to-start is fine but start-to-close appears delayed
- Worker appears healthy but throughput is low

### Root Cause
Activity semaphore (concurrency limiter) is full. Activities are dequeued from Temporal
but waiting internally for a slot. This happens when:
- `MaxConcurrentActivityExecutionSize` is too low for the throughput
- Long-running activities hold slots preventing new ones
- Activity rate limiter (`WorkerActivitiesPerSecond`) too restrictive

### Detection
```promql
# Internal queue building up
temporal_worker_task_slots_used == temporal_worker_task_slots_available

# Activity start lag (time between worker receiving and starting execution)
histogram_quantile(0.99, temporal_activity_execution_latency_seconds_bucket) - 
  histogram_quantile(0.99, temporal_activity_schedule_to_start_latency_seconds_bucket) > 5
```

### Resolution
```go
// Tune concurrency limits based on activity profile
workerOptions := worker.Options{
    // For I/O-bound activities (network calls, DB queries)
    MaxConcurrentActivityExecutionSize: 1000,  // High concurrency OK
    
    // For CPU-bound activities (computation, encoding)
    // MaxConcurrentActivityExecutionSize: runtime.NumCPU() * 2,
    
    // Rate limit to protect downstream
    WorkerActivitiesPerSecond: 500,  // Max 500 activities/sec per worker
    
    // Per-activity-type rate limiting
    TaskQueueActivitiesPerSecond: 2000,  // Across all workers on this queue
}

// For mixed workloads, use separate workers
ioWorker := worker.New(c, "io-activities", worker.Options{
    MaxConcurrentActivityExecutionSize: 1000,
})

cpuWorker := worker.New(c, "cpu-activities", worker.Options{
    MaxConcurrentActivityExecutionSize: runtime.NumCPU(),
})
```

### Prevention
- Profile activities: categorize as CPU-bound vs I/O-bound
- Set concurrency based on bottleneck (CPU cores for CPU-bound, connection pool for I/O)
- Monitor `task_slots_used` / `task_slots_available` ratio
- Implement activity-level circuit breakers

---

## Issue #10: Poller Count Insufficient for Partition Count [MEDIUM]

### Symptoms
- Some task queue partitions never polled
- Uneven work distribution across workers
- Adding workers doesn't improve throughput
- Some tasks wait despite available worker capacity

### Root Cause
Each poller long-polls ONE partition. If partitions > pollers per worker:
- Worker with 5 pollers on 16-partition queue: only covers 5/16 partitions
- Matching service forwards tasks between partitions (adds latency)
- Some partitions have zero pollers (tasks wait for forwarding)

### Detection
```promql
# Tasks forwarded (indicates poller/partition mismatch)
rate(temporal_matching_forward_tasks_total[5m]) > 100
```

### Resolution
```go
// Rule: pollers per worker >= partition count / worker count
// 16 partitions, 8 workers -> minimum 2 pollers per worker (but more is better)

workerOptions := worker.Options{
    // Activity pollers
    MaxConcurrentActivityTaskPollers: 10,  // Cover more partitions
    
    // Workflow task pollers
    MaxConcurrentWorkflowTaskPollers: 5,
}

// Server-side: adjust partition count to match fleet
// dynamic_config.yaml
matching.numTaskqueueWritePartitions:
  - value: 8  # = number of workers for small fleet
    constraints:
      taskQueueName: "my-queue"
```

### Prevention
- Formula: `pollers_per_worker = max(partitions / workers * 2, 5)`
- Keep partition count reasonable (4-32 typical)
- Monitor forwarding rate as a signal of mismatch
- Increase pollers rather than partitions when possible

---

## Issue #11: Worker Can't Connect After Temporal Server Restart [HIGH]

### Symptoms
- Workers log: `failed to poll for workflow task: connection refused`
- All workers disconnect simultaneously
- Workers don't reconnect automatically
- Frontend service showing 0 connected workers

### Root Cause
- Temporal server restart breaks all gRPC connections
- Workers using non-resilient connection settings
- No exponential backoff on reconnection
- DNS cache pointing to old server pod IPs
- Load balancer health check lag

### Detection
```promql
# Worker connection drops
temporal_frontend_client_connections == 0

# Poll failures spike
rate(temporal_worker_poll_failures_total[1m]) > 10
```

### Resolution
```go
// Resilient client connection with proper dial options
import (
    "google.golang.org/grpc"
    "google.golang.org/grpc/keepalive"
)

clientOptions := client.Options{
    HostPort: "temporal-frontend.temporal.svc.cluster.local:7233",
    ConnectionOptions: client.ConnectionOptions{
        // Enable keepalive to detect dead connections
        DialOptions: []grpc.DialOption{
            grpc.WithKeepaliveParams(keepalive.ClientParameters{
                Time:                10 * time.Second,  // Ping every 10s
                Timeout:             5 * time.Second,   // Wait 5s for pong
                PermitWithoutStream: true,              // Ping even when no active RPCs
            }),
            // Automatic reconnection
            grpc.WithDefaultServiceConfig(`{
                "methodConfig": [{
                    "name": [{"service": ""}],
                    "retryPolicy": {
                        "maxAttempts": 5,
                        "initialBackoff": "0.1s",
                        "maxBackoff": "10s",
                        "backoffMultiplier": 2,
                        "retryableStatusCodes": ["UNAVAILABLE"]
                    }
                }]
            }`),
        },
    },
}

c, err := client.Dial(clientOptions)
```

### Prevention
- gRPC keepalive on all worker connections
- Kubernetes headless service for direct pod connections
- Client-side retry with exponential backoff
- Health check endpoint on workers to verify Temporal connectivity
- DNS TTL low (5s) for service discovery

---

## Issue #12: Workflow Task Processing Panic [HIGH]

### Symptoms
- Worker logs: `panic recovered` in workflow task processor
- Workflow stuck - tasks dispatched but never completed
- Same workflow fails repeatedly
- Worker stays alive but affected workflow makes no progress

### Root Cause
Bug in workflow code causes panic during replay:
- Nil pointer dereference on deserialized data
- Array index out of bounds
- Type assertion failure on legacy data
- Panic in interceptor/middleware

### Detection
```promql
# Workflow task failures
rate(temporal_workflow_task_execution_failed_total[5m]) > 0

# Same workflow stuck (repeated task dispatches without completion)
temporal_workflow_task_schedule_to_start_latency_seconds{workflow_type="MyWorkflow"} > 30
```

### Resolution
```go
// Worker panic policy configuration
workerOptions := worker.Options{
    // FailWorkflow - terminates the workflow with error (recommended for prod)
    WorkflowPanicPolicy: worker.FailWorkflow,
    
    // BlockWorkflow - keeps retrying (useful for debugging, dangerous in prod)
    // WorkflowPanicPolicy: worker.BlockWorkflow,
}

// Defensive workflow code
func MyWorkflow(ctx workflow.Context, input *Input) error {
    // Guard against nil input (can happen with serialization issues)
    if input == nil {
        return temporal.NewApplicationError("nil input", "INVALID_INPUT", nil)
    }
    
    // Guard type assertions
    if val, ok := result.(ExpectedType); ok {
        // use val
    } else {
        return temporal.NewApplicationError("unexpected type", "TYPE_ERROR", nil)
    }
    
    // Guard array access
    if len(input.Items) > idx {
        item := input.Items[idx]
        // use item
    }
    
    return nil
}
```

**Recovery for stuck workflows:**
```bash
# Option 1: Reset workflow to before the problematic event
tctl workflow reset --workflow-id "my-workflow-id" \
  --reason "panic fix deployed" \
  --reset-type LastWorkflowTask

# Option 2: Terminate and restart
tctl workflow terminate --workflow-id "my-workflow-id" --reason "unrecoverable panic"
# Start new workflow with same input
```

### Prevention
- `WorkflowPanicPolicy: worker.FailWorkflow` in production
- Comprehensive nil checks in workflow code
- Integration tests that replay production histories
- Canary deployment with replay testing

---

## Issue #13: Task Queue Rate Limiting Mismatch [MEDIUM]

### Symptoms
- `TaskQueueActivitiesPerSecond` limit hit but workers have capacity
- Activities throttled at task queue level, not worker level
- Throughput capped below hardware capability
- Rate limit errors in matching service logs

### Root Cause
- `TaskQueueActivitiesPerSecond` set too low (applies across ALL workers)
- Confusion between `WorkerActivitiesPerSecond` (per worker) and `TaskQueueActivitiesPerSecond` (global)
- Dynamic config override reducing allowed rate
- Rate limiter doesn't account for recently scaled workers

### Detection
```promql
# Rate limiting in effect
rate(temporal_matching_tasks_rate_limited_total[5m]) > 0
```

### Resolution
```go
// Per-worker rate limit (each worker can do 100/sec)
workerOptions := worker.Options{
    WorkerActivitiesPerSecond: 100,  // Per individual worker
    
    // Global task queue rate limit (across all workers combined)
    TaskQueueActivitiesPerSecond: 5000,  // 50 workers * 100/worker
}

// Dynamic config on server side
// dynamic_config.yaml
matching.taskQueueRPS:
  - value: 10000
    constraints:
      taskQueueName: "high-throughput-tq"

// If rate limiting is to protect downstream, use application-level instead
func MyActivity(ctx context.Context, input Input) error {
    // Rate limit at application level with more control
    if err := rateLimiter.Wait(ctx); err != nil {
        return err
    }
    return callDownstream(input)
}
```

### Prevention
- Understand the difference: worker-level vs queue-level rate limits
- Queue-level limit = sum of all workers' capacity (or use for downstream protection)
- Monitor `tasks_rate_limited` metric
- Document rate limit strategy per task queue

---

## Issue #14: Worker Registration Mismatch [MEDIUM]

### Symptoms
- `workflow "MyWorkflow" is not registered` error in server logs
- Activities fail with `activity type "MyActivity" not registered`
- Some workers can process tasks, others reject them
- Issue appears after partial deployment

### Root Cause
- New workflow/activity deployed to some workers but not all
- Worker polls task queue but doesn't have the handler registered
- Typo in activity/workflow name (Go is case-sensitive)
- Workflow renamed but old workers still running

### Detection
```promql
# Registration errors
rate(temporal_workflow_task_execution_failed_total{failure_reason="unregistered"}[5m]) > 0
```

### Resolution
```go
// Verify registration at startup
func main() {
    w := worker.New(c, "my-task-queue", workerOptions)
    
    // Register ALL workflows this worker should handle
    w.RegisterWorkflow(OrderWorkflow)
    w.RegisterWorkflow(PaymentWorkflow)
    w.RegisterWorkflowWithOptions(LegacyWorkflow, workflow.RegisterOptions{
        Name: "OldWorkflowName",  // Handle renamed workflows
    })
    
    // Register ALL activities
    activities := &MyActivities{db: db, client: httpClient}
    w.RegisterActivity(activities)  // Registers all methods
    
    // Verify at startup with a simple task queue describe
    resp, err := c.DescribeTaskQueue(ctx, "my-task-queue", enums.TASK_QUEUE_TYPE_WORKFLOW)
    if err != nil {
        log.Fatal("Cannot verify task queue registration", err)
    }
    log.Info("Worker registered, pollers:", len(resp.Pollers))
    
    w.Run(worker.InterruptCh())
}

// Use build-time verification
//go:generate temporal-verify-registration ./...
```

### Prevention
- All workers for a task queue MUST register the same set of types
- Integration test: start worker, verify all registrations
- Deployment: ensure 100% rollout before starting new workflow types
- Use `RegisterWorkflowWithOptions` for name aliases during migrations

---

## Issue #15: Concurrent Workflow Execution Limit Per Worker [MEDIUM]

### Symptoms
- Worker processing workflow tasks slower than expected
- `MaxConcurrentWorkflowTaskExecutionSize` consistently hit
- Workflow task latency increases linearly with load
- Adding more workflows doesn't improve throughput per worker

### Root Cause
`MaxConcurrentWorkflowTaskExecutionSize` limits how many workflow tasks a single worker
processes simultaneously. This is needed because workflow task processing:
- Requires CPU (replay/re-execute deterministic code)
- Holds workflow state in memory
- Blocks goroutines during replay

If limit is too low: underutilized worker. Too high: OOM or excessive CPU.

### Detection
```promql
# Workflow task concurrency at limit
temporal_worker_task_slots_used{worker_type="WorkflowWorker"} >= 
  temporal_worker_task_slots_available{worker_type="WorkflowWorker"}
```

### Resolution
```go
// Size based on workflow complexity
workerOptions := worker.Options{
    // Simple workflows (< 100 events history): higher concurrency
    MaxConcurrentWorkflowTaskExecutionSize: 500,
    
    // Complex workflows (1000+ events): lower concurrency (replay is CPU-intensive)
    // MaxConcurrentWorkflowTaskExecutionSize: 50,
    
    // Dedicated workflow workers vs activity workers
    // Workflow worker: high workflow concurrency, zero activities
    // Activity worker: zero workflows, high activity concurrency
}

// Best practice: separate workflow and activity workers
workflowWorker := worker.New(c, "my-task-queue", worker.Options{
    MaxConcurrentWorkflowTaskExecutionSize: 200,
    MaxConcurrentActivityExecutionSize:     0,   // No activities on this worker
    DisableWorkflowWorker:                  false,
})

activityWorker := worker.New(c, "my-task-queue", worker.Options{
    MaxConcurrentWorkflowTaskExecutionSize: 0,   // No workflows on this worker
    MaxConcurrentActivityExecutionSize:     500,
    DisableWorkflowWorker:                  true,
})
```

### Prevention
- Profile workflow replay time (history size -> replay CPU)
- Separate workflow workers from activity workers for isolation
- `MaxConcurrentWorkflowTaskExecutionSize` = available_memory / avg_workflow_state_size
- Monitor and adjust based on actual utilization

---

## Summary: Worker & Task Queue Issue Prevention Checklist

```
□ HPA/KEDA autoscaling on schedule-to-start latency
□ Separate task queues: fast activities, slow activities, workflows
□ Worker graceful shutdown timeout > longest activity
□ Sticky timeout 2-5 seconds (not default 5s if deploying often)
□ Poller count >= partitions / workers * 2
□ gRPC keepalive on all worker connections
□ WorkflowPanicPolicy: FailWorkflow in production
□ Rate limits documented: per-worker vs per-queue
□ All workers register identical workflow/activity sets
□ Memory limits with GOMEMLIMIT at 85% of container limit
□ Activity timeout hierarchy: Start-to-Close < Schedule-to-Close
□ Heartbeat timeout on any activity > 30 seconds
□ Separate workflow workers from activity workers at scale
□ Monitor: slots used, latency, error rate, cache size
□ Deployment strategy: maxSurge 50%, proper terminationGracePeriod
```
