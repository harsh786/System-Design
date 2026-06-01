# Scaling & Performance Production Issues (#56 - #70)

## Issue #56: Thundering Herd on Worker Fleet Restart [CRITICAL]

### Symptoms
- All workers reconnect simultaneously after outage/deployment
- 10K+ workflow tasks dispatched in < 1 second
- Database write spike overwhelms persistence layer
- Frontend rate limiting kicks in, rejecting legitimate requests
- Cascade: OOM -> restart -> herd -> OOM

### Root Cause
After a fleet-wide restart (deployment, node failure, etc.):
- All workers reconnect and poll simultaneously
- Temporal server dispatches all pending tasks at once
- Workers process all pending workflow tasks (replaying histories)
- Massive concurrent DB reads (history replay) + writes (activity scheduling)
- Memory spike from concurrent replays

### Impact
- **Business**: Extended outage beyond initial trigger
- **System**: Can turn 2-minute outage into 30-minute recovery
- **Scale**: 1000 workers × 200 concurrent workflows = 200K simultaneous replays

### Detection
```promql
# Connection surge
rate(temporal_frontend_connections_total[1m]) > 500

# CPU/memory spike after restart
container_cpu_usage_seconds_total{container="temporal-history"} > limits * 0.9

# Dispatch rate spike
rate(temporal_matching_tasks_dispatched_total[10s]) > 10000
```

### Resolution
```go
// Worker-side: Staggered startup with jitter
func main() {
    // Add random jitter to startup (0-30 seconds)
    startupJitter := time.Duration(rand.Intn(30000)) * time.Millisecond
    time.Sleep(startupJitter)
    
    // Ramp up concurrency gradually
    w := worker.New(c, "my-task-queue", worker.Options{
        // Start with low concurrency, ramp up
        MaxConcurrentWorkflowTaskExecutionSize: 50,   // Start low
        MaxConcurrentActivityExecutionSize:     100,  // Start low
    })
    
    // After warmup period, increase concurrency
    go func() {
        time.Sleep(60 * time.Second)  // 1 minute warmup
        // Note: Can't change options dynamically, but can control at application level
    }()
    
    w.Run(worker.InterruptCh())
}
```

```yaml
# Kubernetes: Staggered rollout
spec:
  strategy:
    rollingUpdate:
      maxSurge: 10%          # Only 10% of pods start at once
      maxUnavailable: 10%
  template:
    spec:
      initContainers:
      - name: startup-delay
        image: busybox
        command: ['sh', '-c', 'sleep $((RANDOM % 30))']  # Random 0-30s delay
```

```yaml
# Server-side: Rate limit dispatch after restart
# dynamic_config.yaml
matching.maxTaskDispatchRate:
  - value: 1000  # Limit how fast tasks are dispatched (ramp up manually)
    constraints: {}

# After recovery, increase:
# matching.maxTaskDispatchRate: 10000
```

### Prevention
- Rolling deployments with maxSurge: 10%
- Startup jitter in workers (random sleep before polling)
- Server-side dispatch rate limiting during recovery
- Horizontal Pod Autoscaler with scale-up rate limiting
- Database provisioned for 3x normal load (handles burst)

---

## Issue #57: History Shard Rebalancing Storm [CRITICAL]

### Symptoms
- Workflow latency spikes when history pods scale up/down
- `shard_controller_lost_shard` events in logs
- Brief period where no owner for some shards
- Transfer tasks stall during rebalancing

### Root Cause
When history service pods change (scale event, pod restart):
- Shards must be redistributed across available pods
- During redistribution, shards briefly have no owner
- Workflows on those shards cannot make progress
- If many pods change at once, many shards affected simultaneously

### Impact
- **Business**: 1-30 second stall for affected workflows
- **System**: Transfer tasks and timer tasks delayed
- **Scale**: 512 shards across 8 pods -> losing 1 pod = 64 shards rebalancing

### Detection
```promql
# Shard ownership changes
rate(temporal_history_shard_controller_events_total{event="shard_closed"}[5m]) > 10

# Shards without owner
temporal_history_shards_owned < temporal_total_shards / temporal_history_pods
```

### Resolution
```yaml
# 1. Pod Disruption Budget - limit concurrent disruptions
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: temporal-history-pdb
spec:
  minAvailable: 80%  # At least 80% must be running
  selector:
    matchLabels:
      app: temporal-history

# 2. Graceful shard handoff (server config)
# dynamic_config.yaml
history.shardControllerShutdownTimeout:
  - value: 30s  # Allow time for graceful shard transfer

history.shardControllerAcquireShardTimeout:
  - value: 10s
```

```go
// Pre-stop hook for graceful shard release
// The Temporal history service handles this internally, but ensure:
// 1. terminationGracePeriodSeconds > shardControllerShutdownTimeout
// 2. PreStop hook gives time for shard release before SIGTERM
```

### Prevention
- PodDisruptionBudget: minAvailable 80%
- More shards than pods (allows gradual rebalancing)
- Scale in small increments (1-2 pods at a time)
- Monitor shard ownership during scaling events
- Rolling updates with sufficient wait between pods

---

## Issue #58: Workflow Start Rate Throttled by Frontend [HIGH]

### Symptoms
- `StartWorkflow` latency increasing linearly
- p99 start latency > 5s during peak
- Frontend CPU at 100%
- Rate limiting before database or matching is stressed

### Root Cause
Frontend service is the bottleneck:
- Request parsing and validation
- Payload size validation
- Namespace quota checking
- History size estimation
- All CPU-bound on frontend pods

### Impact
- **Business**: New workflow starts delayed, queue building up
- **System**: Frontend becomes bottleneck before backend
- **Scale**: At 50K starts/sec, need 10+ frontend pods

### Detection
```promql
# Frontend CPU saturation
rate(container_cpu_usage_seconds_total{container="temporal-frontend"}[1m]) / 
  container_spec_cpu_quota > 0.9

# Start latency
temporal_frontend_request_latency_seconds{operation="StartWorkflowExecution", quantile="0.99"} > 2
```

### Resolution
```yaml
# Scale frontend independently
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: temporal-frontend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: temporal-frontend
  minReplicas: 6
  maxReplicas: 30
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60  # Scale before saturation
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Percent
        value: 50  # Scale up aggressively
        periodSeconds: 30
```

```yaml
# dynamic_config.yaml - Frontend tuning
frontend.maxConcurrentRequestsPerInstance:
  - value: 2000
    constraints: {}

frontend.maxPayloadSize:
  - value: 2097152  # 2MB max payload (reduce from 4MB if possible)
    constraints: {}
```

### Prevention
- HPA on frontend with 60% CPU target
- Multiple frontend pods behind L4 load balancer
- Client-side batching (start fewer, larger workflows)
- Separate frontend pools for different clients (priority)
- Monitor frontend CPU as primary scaling signal

---

## Issue #59: Matching Service Sync Match Rate Drops [HIGH]

### Symptoms
- Schedule-to-start latency increases from 5ms to 500ms
- Matching service CPU is fine but latency is high
- `sync_match_rate` drops from 90% to 30%
- Workers are polling but tasks go through async path

### Root Cause
Temporal Matching service tries to "sync match" (directly hand task to polling worker).
When sync match fails, task goes to persistence (async path, slower):
- Burst of tasks overwhelms available pollers
- Workers already processing, no idle poller available
- Task queue partitions uneven (some have pollers, some don't)
- Poller long-poll timeout expired before task arrived

### Impact
- **Business**: 10-100x latency increase for task dispatch
- **System**: More database writes (async path persists tasks)
- **Scale**: Going from 90% sync match to 30% = 60% more DB writes + latency

### Detection
```promql
# Sync match rate
temporal_matching_sync_match_rate < 0.7

# Async dispatch increase
rate(temporal_matching_tasks_added_to_persistence_total[5m]) / 
  rate(temporal_matching_tasks_added_total[5m]) > 0.3
```

### Resolution
```go
// Increase worker pollers to maximize sync match opportunity
workerOptions := worker.Options{
    MaxConcurrentActivityTaskPollers: 20,   // More pollers = higher sync match
    MaxConcurrentWorkflowTaskPollers: 10,
}

// Ensure workers have idle slots for sync match
// MaxConcurrentActivityExecutionSize should be HIGHER than typical concurrent load
// So there are always idle slots for sync dispatch
workerOptions := worker.Options{
    MaxConcurrentActivityExecutionSize: 500,  // Headroom for sync match
    MaxConcurrentActivityTaskPollers:   20,
}
```

```yaml
# Server-side tuning
# dynamic_config.yaml
matching.syncMatchWaitDuration:
  - value: 200ms  # Wait up to 200ms for sync match before async
    constraints: {}

matching.maxTaskqueueIdleTime:
  - value: 5m  # Keep task queue loaded in memory longer
    constraints: {}
```

### Prevention
- More pollers per worker (each poller = sync match opportunity)
- Worker slots > average load (headroom for immediate dispatch)
- Monitor sync match rate as performance indicator
- More workers (even if underutilized) = higher sync match rate
- Adjust `syncMatchWaitDuration` based on workload profile

---

## Issue #60: Workflow Task Processing Contention on Sticky Worker [HIGH]

### Symptoms
- Specific workflows repeatedly slow on same worker
- Worker processing workflows unevenly (some fast, some queued)
- Sticky cache hit rate high but workflow task latency variable
- One large workflow blocks others cached on same worker

### Root Cause
Sticky execution means workflow tasks go to specific worker:
- Worker caches N workflows
- All cached workflows compete for `MaxConcurrentWorkflowTaskExecutionSize` slots
- One workflow replaying large history blocks slot for others
- Worker becomes hotspot if caching high-value/frequent workflows

### Impact
- **Business**: Inconsistent latency for specific workflows
- **System**: Head-of-line blocking on worker
- **Scale**: 1000 workflows cached on one worker, 100 slots = 10x oversubscribed

### Detection
```promql
# Per-worker workflow task queue depth
temporal_worker_task_slots_used{worker_type="WorkflowWorker"} / 
  temporal_worker_task_slots_available{worker_type="WorkflowWorker"} > 0.9
  
# Sticky execution with high latency variance
stddev(temporal_workflow_task_execution_latency_seconds) by (worker) > 
  avg(temporal_workflow_task_execution_latency_seconds) by (worker)
```

### Resolution
```go
// Reduce sticky cache (less contention per worker)
workerOptions := worker.Options{
    // Fewer cached workflows = less contention
    StickyScheduleToStartTimeout: 3 * time.Second,  // Fall back to normal queue faster
}

// For high-value workflows, dedicate task queue + workers
// VIP workflows get their own task queue with dedicated fleet
vipWorker := worker.New(c, "vip-workflows-tq", worker.Options{
    MaxConcurrentWorkflowTaskExecutionSize: 50,  // Fewer but more important
})
```

### Prevention
- Separate high-frequency workflows to dedicated task queues
- Lower `StickyScheduleToStartTimeout` for consistent latency
- More workers = fewer workflows per worker cache
- Monitor per-worker slot utilization

---

## Issue #61: Activity Goroutine Leak [HIGH]

### Symptoms
- Worker goroutine count growing unbounded
- Worker memory growing steadily
- `runtime.NumGoroutine()` increasing 100+/hour
- Eventually worker becomes unresponsive or OOM

### Root Cause
Activity implementation leaks goroutines:
- Spawning goroutines without cleanup on context cancellation
- HTTP client without timeout (goroutine waits forever)
- Channel operations without select/timeout
- Third-party library spawning background goroutines

### Impact
- **Business**: Worker degradation, eventual OOM and task loss
- **System**: Resources consumed by leaked goroutines
- **Scale**: Thousands of leaked goroutines per day per worker

### Detection
```promql
# Goroutine count growing
deriv(go_goroutines{job="temporal-worker"}[1h]) > 10

# Memory growing (goroutine stacks)
deriv(go_memstats_stack_inuse_bytes{job="temporal-worker"}[1h]) > 1000000
```

### Resolution
```go
// WRONG: Goroutine leak in activity
func MyActivity(ctx context.Context, input Input) error {
    // This goroutine leaks if activity is cancelled!
    go func() {
        result := expensiveComputation(input)  // No context, runs forever
        sendResult(result)
    }()
    
    // HTTP client without timeout
    resp, _ := http.Get("https://slow-service.com/api")  // Blocks forever
    
    return nil
}

// CORRECT: Context-aware goroutines
func MyActivity(ctx context.Context, input Input) error {
    // Goroutine respects context
    resultCh := make(chan Result, 1)
    go func() {
        select {
        case <-ctx.Done():
            return  // Clean exit on cancellation
        case resultCh <- expensiveComputation(ctx, input):
        }
    }()
    
    select {
    case result := <-resultCh:
        return sendResult(result)
    case <-ctx.Done():
        return ctx.Err()
    }
}

// HTTP client with context
func CallAPI(ctx context.Context, url string) ([]byte, error) {
    req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
    client := &http.Client{Timeout: 30 * time.Second}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    return io.ReadAll(resp.Body)
}
```

```go
// Goroutine leak detection in tests
func TestNoGoroutineLeak(t *testing.T) {
    before := runtime.NumGoroutine()
    
    // Run activity
    runMyActivity(context.Background(), input)
    
    // Allow time for cleanup
    time.Sleep(100 * time.Millisecond)
    runtime.GC()
    
    after := runtime.NumGoroutine()
    if after > before+1 {
        t.Errorf("goroutine leak: before=%d, after=%d", before, after)
    }
}
```

### Prevention
- All goroutines in activities MUST respect `ctx.Done()`
- HTTP clients MUST have timeout or use context
- goleak library in tests to detect leaks
- Monitor goroutine count as worker health metric
- Code review rule: every `go func()` must have cancellation path

---

## Issue #62: Namespace Quota Exhaustion [HIGH]

### Symptoms
- `ResourceExhausted: namespace RPS limit exceeded for all APIs`
- All operations on specific namespace fail
- Other namespaces unaffected
- Happens during batch operations or runaway workflows

### Root Cause
- Namespace-level quotas set too low
- Runaway workflow creating thousands of child workflows
- Batch backfill starting too many workflows simultaneously
- Signal storm (external system sending thousands of signals/sec)

### Impact
- **Business**: Entire application namespace blocked
- **System**: All workflows in namespace cannot progress
- **Scale**: One bad actor can starve entire namespace

### Detection
```promql
# Namespace-level rate limiting
rate(temporal_service_errors_total{error_code="ResourceExhausted", namespace="production"}[1m]) > 0
```

### Resolution
```yaml
# 1. Increase namespace limits
# dynamic_config.yaml
frontend.namespaceRPS:
  - value: 20000  # Increase limit
    constraints:
      namespace: "production"

# 2. Separate noisy workflows to their own namespace
# Move batch workflows to "batch-processing" namespace
# Keep real-time workflows in "production" namespace

# 3. Per-workflow-type limits (prevent one type from starving others)
frontend.maxWorkflowStartRPS:
  - value: 1000
    constraints:
      namespace: "production"
      workflowType: "batch-import"  # Limit this specific type
```

```go
// Client-side: Rate-limited workflow starter for batch operations
type BatchStarter struct {
    client  client.Client
    limiter *rate.Limiter
}

func (b *BatchStarter) StartBatch(ctx context.Context, items []Item) error {
    for _, item := range items {
        // Rate limit: 500 starts/sec to stay within namespace quota
        if err := b.limiter.Wait(ctx); err != nil {
            return err
        }
        _, err := b.client.ExecuteWorkflow(ctx, opts, ProcessItem, item)
        if err != nil {
            return err
        }
    }
    return nil
}
```

### Prevention
- Separate namespaces for different workload profiles
- Client-side rate limiting for batch operations
- Per-workflow-type quotas (prevent one type from starving)
- Monitor namespace quota utilization
- Alert at 80% of quota (pre-emptive scaling)

---

## Issue #63: Worker Auto-Scaling Lag [HIGH]

### Symptoms
- Schedule-to-start latency spikes before autoscaler reacts
- 3-5 minute delay between load increase and worker scale-up
- By the time new workers are ready, spike has passed
- Metric-based scaling too slow for sudden spikes

### Detection
```promql
# Scale lag: latency spike precedes scale event
temporal_activity_schedule_to_start_latency_seconds{quantile="0.99"} > 5
  AND kube_deployment_spec_replicas{deployment="temporal-worker"} == kube_deployment_status_replicas
```

### Resolution
```yaml
# KEDA scaler with aggressive scale-up
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: temporal-worker-scaler
spec:
  scaleTargetRef:
    name: temporal-worker
  minReplicaCount: 20      # Never go below 20
  maxReplicaCount: 500
  cooldownPeriod: 30       # Quick cooldown
  pollingInterval: 5       # Check every 5 seconds (aggressive)
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 0  # Scale up immediately
          policies:
          - type: Percent
            value: 100     # Double capacity per 15s
            periodSeconds: 15
          - type: Pods
            value: 50      # Or add 50 pods per 15s
            periodSeconds: 15
          selectPolicy: Max
        scaleDown:
          stabilizationWindowSeconds: 300  # Wait 5min before scale down
          policies:
          - type: Percent
            value: 10      # Scale down slowly (10% per minute)
            periodSeconds: 60
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      metricName: temporal_schedule_to_start
      query: |
        max(temporal_activity_schedule_to_start_latency_seconds{
          task_queue="payment-tq", quantile="0.95"
        })
      threshold: "2"  # Scale at 2s schedule-to-start
```

```go
// Predictive scaling: pre-scale based on known patterns
// CronJob that scales workers before predicted traffic
func predictiveScale(hour int, dayOfWeek int) int {
    // Based on historical patterns
    if dayOfWeek == 5 && hour >= 18 {  // Friday evening = flash sale
        return 200  // Pre-scale to 200 workers
    }
    if hour >= 9 && hour <= 17 {  // Business hours
        return 100
    }
    return 30  // Off-hours
}
```

### Prevention
- Aggressive scale-up (double capacity per 15s window)
- Conservative scale-down (10% per minute, 5-min stabilization)
- Pre-scale for predictable events (cron-based)
- Maintain buffer capacity (minReplicas = 2x minimum needed)
- Scale on leading indicators (queue depth) not lagging (latency)

---

## Issue #64: Hot Workflow Causing Shard Hotspot [MEDIUM]

### Symptoms
- Single workflow receiving 1000s of signals/sec
- One history shard at 100% capacity
- Other workflows on same shard degraded
- Temporal server shows uneven shard load

### Root Cause
One "mega workflow" receiving extreme signal/query traffic:
- Fan-in pattern: 10K producers signaling one coordinator workflow
- Popular order tracked by many consumers (query spam)
- Event aggregation workflow receiving all events
- Shard assigned to this workflow becomes hotspot

### Impact
- **Business**: Hot workflow slow + all neighbors on same shard slow
- **System**: Shard becomes bottleneck, cannot distribute further
- **Scale**: One hot shard out of 512 = 0.2% of capacity serving 50% of traffic

### Detection
```promql
# Per-shard operation rate imbalance
max(temporal_history_shard_operations_total) / avg(temporal_history_shard_operations_total) > 10
```

### Resolution
```go
// Pattern: Distribute hot workflow across multiple IDs
// WRONG: Single coordinator receiving all signals
func Coordinator(ctx workflow.Context, state State) error {
    ch := workflow.GetSignalChannel(ctx, "event")
    for {
        ch.Receive(ctx, &event)  // 10K signals/sec on one workflow!
    }
}

// CORRECT: Partition across N coordinator workflows
func sendEvent(ctx context.Context, c client.Client, event Event) error {
    // Distribute across 100 coordinator workflows (different shards)
    partition := hash(event.Key) % 100
    workflowID := fmt.Sprintf("coordinator-%d", partition)
    
    return c.SignalWorkflow(ctx, workflowID, "", "event", event)
}

// Each partition coordinator handles 1/100th of traffic
func PartitionedCoordinator(ctx workflow.Context, partition int, state State) error {
    ch := workflow.GetSignalChannel(ctx, "event")
    for i := 0; i < 1000; i++ {  // Process 1000 events then continue-as-new
        var event Event
        ch.Receive(ctx, &event)
        processEvent(&state, event)
    }
    return workflow.NewContinueAsNewError(ctx, PartitionedCoordinator, partition, state)
}

// Aggregator workflow collects from partitions periodically
func Aggregator(ctx workflow.Context) error {
    for {
        workflow.Sleep(ctx, 10*time.Second)
        // Query all partition coordinators for their state
        for i := 0; i < 100; i++ {
            // Use query to get state without adding history events
        }
    }
}
```

### Prevention
- No single workflow should receive > 100 signals/sec
- Partition hot workflows by key space
- Use query batching (periodic aggregation, not per-event)
- Monitor per-shard operation rates
- Design: multiple workflow IDs for fan-in patterns

---

## Issue #65: Memory Pressure from Large Workflow Payloads [MEDIUM]

### Symptoms
- Worker memory usage 3-5x expected
- GC pressure causing latency spikes
- Memory doesn't decrease after workflow completion
- Heap profile shows large byte slices from deserialization

### Root Cause
- Workflow inputs/outputs stored in history, loaded on replay
- Large activity results cached in workflow memory
- Go garbage collector holding large allocations
- Custom data converter creating memory copies

### Detection
```promql
# Memory vs expected
container_memory_working_set_bytes / container_spec_memory_limit > 0.8

# GC pressure
go_gc_duration_seconds{quantile="0.99"} > 0.1
```

### Resolution
```go
// 1. Custom data converter with pooled buffers
type PooledConverter struct {
    pool sync.Pool
}

func (c *PooledConverter) init() {
    c.pool = sync.Pool{
        New: func() interface{} {
            return make([]byte, 0, 4096)
        },
    }
}

// 2. Minimize retained references in workflow state
func MyWorkflow(ctx workflow.Context) error {
    // DON'T hold large data
    // var allResults []LargeResult  // BAD

    // DO process and discard
    for _, batch := range batches {
        var result LargeResult
        workflow.ExecuteActivity(ctx, ProcessBatch, batch).Get(ctx, &result)
        
        // Extract only what's needed, let result be GC'd
        summary := result.Summary()
        _ = result // Allow GC
        
        // Store minimal state
        processedBatches = append(processedBatches, summary)
    }
    return nil
}

// 3. GOGC and GOMEMLIMIT tuning
// env vars in deployment:
// GOGC=50 (more aggressive GC)
// GOMEMLIMIT=3500MiB (for 4Gi container)
```

### Prevention
- Never store large data in workflow variables
- Process large activity results immediately, keep only summaries
- `GOMEMLIMIT` at 85% of container limit
- `GOGC=50` for more aggressive garbage collection
- Use data references (S3 keys) instead of data in workflows

---

## Issue #66: Task Queue Dispatch Imbalance Across Partitions [MEDIUM]

### Symptoms
- Some workers consistently busier than others
- Per-worker throughput varies 3-5x
- Adding workers doesn't proportionally increase throughput
- Task queue describe shows uneven partition assignment

### Detection
```promql
# Throughput variance across workers
stddev(rate(temporal_activity_execution_total[5m])) by (worker_id) / 
  avg(rate(temporal_activity_execution_total[5m])) > 0.5
```

### Resolution
```yaml
# Increase partition count for better distribution
# dynamic_config.yaml
matching.numTaskqueueWritePartitions:
  - value: 32  # More partitions = better distribution
    constraints:
      taskQueueName: "payment-tq"
matching.numTaskqueueReadPartitions:
  - value: 32
    constraints:
      taskQueueName: "payment-tq"

# Forwarding ratio (how often tasks forward between partitions)
matching.forwarderMaxOutstandingPolls:
  - value: 10
    constraints: {}
matching.forwarderMaxRatePerSecond:
  - value: 100
    constraints: {}
```

### Prevention
- Partition count = workers / 5 (minimum 4, maximum 64)
- More pollers per worker for better partition coverage
- Monitor per-partition dispatch rates
- Regular rebalancing during low-traffic periods

---

## Issue #67: Workflow Execution Timeout Causing Silent Failures [MEDIUM]

### Symptoms
- Workflows terminated after hours/days without clear error
- `WorkflowExecutionTimedOut` events in workflow history
- No activity failure, no explicit error - just timeout
- Long-running workflows dying unexpectedly

### Root Cause
- `WorkflowExecutionTimeout` set too low for workflow's natural duration
- Default timeout (infinite) changed in namespace config
- Timer-based workflows sleeping longer than overall timeout
- Workflow stuck (waiting for signal that never comes) + execution timeout

### Detection
```promql
# Workflow execution timeouts
rate(temporal_workflow_execution_timed_out_total[5m]) > 0
```

### Resolution
```go
// Set appropriate execution timeout at start
opts := client.StartWorkflowOptions{
    ID:                       "order-" + orderID,
    TaskQueue:                "orders-tq",
    WorkflowExecutionTimeout: 90 * 24 * time.Hour,  // 90 days for international orders
    WorkflowRunTimeout:       24 * time.Hour,         // Single run: 24h max (then ContinueAsNew)
    WorkflowTaskTimeout:      30 * time.Second,       // Each decision: 30s max
}

// For infinite workflows (subscriptions), use ContinueAsNew before run timeout
func SubscriptionWorkflow(ctx workflow.Context, state State) error {
    // Run for max 30 days, then continue-as-new
    timer := workflow.NewTimer(ctx, 30*24*time.Hour)
    signalCh := workflow.GetSignalChannel(ctx, "event")
    
    for {
        selector := workflow.NewSelector(ctx)
        
        selector.AddReceive(signalCh, func(ch workflow.ReceiveChannel, more bool) {
            var event Event
            ch.Receive(ctx, &event)
            processEvent(&state, event)
        })
        
        selector.AddFuture(timer, func(f workflow.Future) {
            // Timer fired - continue as new
        })
        
        selector.Select(ctx)
        
        if isTimerFired(timer) {
            return workflow.NewContinueAsNewError(ctx, SubscriptionWorkflow, state)
        }
    }
}
```

### Prevention
- Set `WorkflowExecutionTimeout` explicitly on all workflows
- `WorkflowRunTimeout` < `WorkflowExecutionTimeout` (single run vs total)
- ContinueAsNew before run timeout for long-lived workflows
- Monitor timeout events per workflow type
- Alert on any `WorkflowExecutionTimedOut` in production

---

## Issue #68: Excessive Workflow Task Retries [MEDIUM]

### Symptoms
- Same workflow task dispatched and failed repeatedly
- Worker logs show workflow task failures but workflow still "Running"
- History shows repeated `WorkflowTaskFailed` events
- Workflow stuck in retry loop without terminating

### Root Cause
- Workflow code consistently panics or returns error
- Non-determinism errors causing repeated replay failure
- Bug in interceptor/middleware causing workflow task failure
- WorkflowPanicPolicy is `BlockWorkflow` (retries forever)

### Detection
```promql
# Workflow task retry rate
rate(temporal_workflow_task_execution_failed_total[5m]) > 10

# Same workflow retrying repeatedly
temporal_workflow_task_consecutive_failures > 5
```

### Resolution
```go
// Set FailWorkflow policy to stop infinite retries
workerOptions := worker.Options{
    WorkflowPanicPolicy: worker.FailWorkflow,  // Terminate instead of retry forever
}

// Add workflow task error handler
workerOptions.OnFatalError = func(err error) {
    log.Error("Fatal workflow task error", "error", err)
    metrics.Counter("workflow_task_fatal_error").Inc()
    // Alert on-call
}
```

```bash
# For already-stuck workflows, reset or terminate
tctl workflow list --query "WorkflowType='BrokenWorkflow' AND ExecutionStatus='Running'"

# Reset to before the problematic task
tctl workflow reset --workflow-id "stuck-wf-id" --reset-type LastWorkflowTask

# Or terminate if unrecoverable
tctl workflow terminate --workflow-id "stuck-wf-id" --reason "infinite retry loop"
```

### Prevention
- `WorkflowPanicPolicy: FailWorkflow` always in production
- Monitor workflow task failure rate
- Alert if same workflow fails > 5 consecutive tasks
- Replay testing in CI catches most issues before production
- Automated reset for workflows stuck > N hours

---

## Issue #69: Search Attribute Index Hot Spotting [MEDIUM]

### Symptoms
- Elasticsearch write rejections on specific shards
- Visibility write latency spikes
- Some search attribute updates succeed, others fail
- ES index has hot shards

### Detection
```promql
# ES write rejections
elasticsearch_thread_pool_rejected{name="write"} > 0

# Shard-level write rate imbalance
max(elasticsearch_index_shard_docs_count) / avg(elasticsearch_index_shard_docs_count) > 3
```

### Resolution
```json
// Increase shard count for high-volume indices
PUT temporal-visibility-v2/_settings
{
  "index": {
    "number_of_shards": 12,  // More shards for better write distribution
    "routing": {
      "allocation.total_shards_per_node": 2  // Spread across nodes
    }
  }
}

// Use custom routing to distribute writes
// (Temporal handles this internally, but for custom indices)
```

### Prevention
- 1 shard per 30-50GB of expected data
- Write-heavy: more shards for parallelism
- ILM with rollover to keep shards manageable
- Dedicated hot nodes for current-day index
- Monitor per-shard write rates

---

## Issue #70: Cross-Cluster Replication Lag [MEDIUM]

### Symptoms
- Workflows in secondary cluster behind primary
- Failover shows data loss (events not replicated)
- Replication task backlog growing
- `temporal_replication_latency` increasing

### Root Cause
- Network bandwidth between clusters saturated
- Replication worker overwhelmed
- Large payloads slowing replication
- Target cluster persistence slower than source

### Detection
```promql
# Replication lag
temporal_replication_latency_seconds > 30

# Replication task backlog
temporal_replication_task_pending_count > 10000
```

### Resolution
```yaml
# 1. Scale replication workers
# dynamic_config.yaml
history.replicationTaskProcessorMaxPollInterval:
  - value: 50ms
history.replicationTaskMaxPollerCount:
  - value: 8

# 2. Increase cross-cluster bandwidth
# Use AWS VPC peering or Transit Gateway for lower latency

# 3. Prioritize replication for critical namespaces
history.replicationTaskBatchSize:
  - value: 100  # Larger batches for throughput
```

### Prevention
- Monitor replication lag continuously
- Alert if lag > 30s (potential data loss on failover)
- Dedicated network link between clusters
- Replication batch tuning for throughput
- Regular failover testing to validate lag

---

## Summary: Scaling & Performance Issue Prevention Checklist

```
□ Staggered worker startup (random jitter 0-30s)
□ PodDisruptionBudget on history service (minAvailable 80%)
□ Frontend HPA with 60% CPU target
□ KEDA/HPA on workers with schedule-to-start trigger
□ Aggressive scale-up (100%/15s), conservative scale-down (10%/60s)
□ Partition hot workflows across multiple IDs
□ No single workflow > 100 signals/sec
□ Activity goroutines must respect context cancellation
□ GOMEMLIMIT at 85% of container limit, GOGC=50
□ Per-namespace quotas with 2x headroom
□ Separate namespaces for batch vs real-time workloads
□ Predictive scaling for known traffic patterns
□ Monitor: sync match rate, shard balance, replication lag
□ WorkflowPanicPolicy: FailWorkflow (no infinite retries)
□ Workflow timeouts explicitly set on all workflow types
```
