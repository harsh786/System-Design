# History & State Management Production Issues (#16 - #30)

## Issue #16: Workflow History Size Exceeds 50K Events [CRITICAL]

### Symptoms
- Workflow fails with: `history size exceeds limit`
- Warning at 10K events, hard fail at 50K events (default)
- Workflow replay becomes extremely slow (minutes to replay)
- Worker memory spikes during replay of large histories

### Root Cause
Workflow has been running too long without `ContinueAsNew`:
- Loop-based workflow processing events indefinitely
- Subscription workflows running for months without reset
- Batch workflows processing millions of items in single workflow
- Each signal/activity adds 3-10 events to history

### Impact
- **Business**: Workflow permanently stuck, cannot make progress
- **System**: Workers OOM during replay, other workflows on same worker affected
- **Scale**: At 10M workflows, even 0.1% hitting limit = 10K dead workflows

### Detection
```promql
# History size approaching limit
temporal_workflow_history_size_bytes{quantile="0.99"} > 4000000  # 4MB warning

# Event count nearing limit
temporal_workflow_history_length{quantile="0.99"} > 30000
```

### Resolution
```go
// WRONG: Unbounded loop without continue-as-new
func ProcessEventsWorkflow(ctx workflow.Context, state State) error {
    signalCh := workflow.GetSignalChannel(ctx, "new-event")
    for {
        var event Event
        signalCh.Receive(ctx, &event)
        processEvent(&state, event)  // History grows forever!
    }
}

// CORRECT: Continue-as-new after N events
func ProcessEventsWorkflow(ctx workflow.Context, state State) error {
    signalCh := workflow.GetSignalChannel(ctx, "new-event")
    
    eventsProcessed := 0
    const maxEventsBeforeReset = 1000  // ~5000 history events
    
    for eventsProcessed < maxEventsBeforeReset {
        var event Event
        signalCh.Receive(ctx, &event)
        processEvent(&state, event)
        eventsProcessed++
    }
    
    // Drain any pending signals before continue-as-new
    for {
        var event Event
        ok := signalCh.ReceiveAsync(&event)
        if !ok {
            break
        }
        processEvent(&state, event)
    }
    
    // Continue as new workflow with current state
    return workflow.NewContinueAsNewError(ctx, ProcessEventsWorkflow, state)
}

// Even better: Check history size dynamically
func ProcessEventsWorkflow(ctx workflow.Context, state State) error {
    signalCh := workflow.GetSignalChannel(ctx, "new-event")
    
    for {
        var event Event
        signalCh.Receive(ctx, &event)
        processEvent(&state, event)
        
        // Check if we should continue-as-new
        info := workflow.GetInfo(ctx)
        if info.GetCurrentHistoryLength() > 4000 {
            // Drain pending signals
            for signalCh.ReceiveAsync(&event) {
                processEvent(&state, event)
            }
            return workflow.NewContinueAsNewError(ctx, ProcessEventsWorkflow, state)
        }
    }
}
```

**Recovery for already-stuck workflows:**
```bash
# Reset workflow to a point before it got too large
tctl workflow reset --workflow-id "stuck-workflow" \
  --reason "history too large" \
  --reset-type FirstWorkflowTask

# Or terminate and start fresh with state snapshot
tctl workflow terminate --workflow-id "stuck-workflow"
# Extract last known state from visibility/search attributes
# Start new workflow with that state
```

### Prevention
- **Rule**: Every loop-based workflow MUST have continue-as-new
- Continue-as-new threshold: 2000-5000 events (well before 50K limit)
- Monitor `workflow_history_length` p99 per workflow type
- Lint rule: detect loops without ContinueAsNew check
- Use child workflows for sub-tasks (separate history)

---

## Issue #17: Workflow Replay OOM on Worker [CRITICAL]

### Symptoms
- Worker OOM killed when processing specific workflow
- Memory spike correlates with workflow task for long-history workflow
- Other workflows on same worker disrupted
- Workflow keeps getting dispatched, keeps killing workers

### Root Cause
When a workflow task is dispatched to a new worker (no sticky cache), the entire history
must be replayed. For large histories:
- 10K events with 1KB payloads = 10MB to deserialize
- Replay re-executes all workflow logic sequentially
- Intermediate state held in memory during replay
- Multiple large workflow replays simultaneously = multi-GB memory

### Impact
- **Business**: Specific workflow becomes "poison pill" killing workers
- **System**: Cascading OOM as workflow rotates between workers
- **Scale**: One bad workflow can crash entire worker fleet sequentially

### Detection
```promql
# OOM kills correlating with specific workflow
kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} > 0

# Large workflow task replay time
temporal_workflow_task_replay_latency_seconds{quantile="0.99"} > 30
```

### Resolution
```go
// 1. Limit workflow cache to prevent memory explosion
workerOptions := worker.Options{
    MaxConcurrentWorkflowTaskExecutionSize: 50,  // Reduce concurrent replays
}

// 2. Isolate potentially large workflows on dedicated workers
largeWorkflowWorker := worker.New(c, "large-workflows-tq", worker.Options{
    MaxConcurrentWorkflowTaskExecutionSize: 5,   // Very few concurrent
})

// 3. Use continue-as-new to keep histories small (prevention)

// 4. Minimize payload sizes - use references
// WRONG
func MyWorkflow(ctx workflow.Context, data []byte) error {  // 10MB payload in history!
    return nil
}

// CORRECT
func MyWorkflow(ctx workflow.Context, dataRef DataReference) error {
    // Activity fetches actual data, keeps it out of history
    var data []byte
    workflow.ExecuteActivity(ctx, FetchData, dataRef).Get(ctx, &data)
    return nil
}

type DataReference struct {
    Bucket string
    Key    string
}
```

**Emergency: Stop the poison pill workflow:**
```bash
# Terminate the offending workflow
tctl workflow terminate --workflow-id "poison-pill-wf-id" --reason "OOM killer"

# Or if you need to keep it, reset to reduce history
tctl workflow reset --workflow-id "poison-pill-wf-id" \
  --reset-type LastWorkflowTask \
  --reason "reduce history for OOM fix"
```

### Prevention
- Hard memory limit with `GOMEMLIMIT`
- Separate workers for potentially large workflows
- Continue-as-new at 2000 events (not 50K)
- Payload size limits in data converter
- Monitor replay latency per workflow type

---

## Issue #18: Signal Loss During Continue-As-New [HIGH]

### Symptoms
- Signals sent during continue-as-new transition are lost
- Workflow restarts without processing queued signals
- Business events missing (payments, order updates)
- Intermittent - only during the brief transition window

### Root Cause
When a workflow executes `ContinueAsNew`, there's a brief window where:
1. Old run closes
2. New run starts

Signals sent between step 1 and step 2 may be lost because:
- Signal targets old run ID (already closed)
- New run hasn't started yet
- No buffer between runs for in-flight signals

### Impact
- **Business**: Lost payment notifications, order status updates missed
- **System**: Data inconsistency between Temporal state and external systems
- **Scale**: At high signal rate, every continue-as-new has a loss window

### Detection
```promql
# Signals sent to completed workflows
rate(temporal_signal_workflow_execution_failed_total{failure="not_found"}[5m]) > 0
```

### Resolution
```go
// CORRECT: Drain all pending signals before continue-as-new
func MyWorkflow(ctx workflow.Context, state State) error {
    signalCh := workflow.GetSignalChannel(ctx, "my-signal")
    
    for {
        // Normal processing
        var signal Signal
        signalCh.Receive(ctx, &signal)
        processSignal(&state, signal)
        
        // Check if should continue-as-new
        if shouldContinueAsNew(ctx) {
            // CRITICAL: Drain all buffered signals first
            for {
                ok := signalCh.ReceiveAsync(&signal)
                if !ok {
                    break
                }
                processSignal(&state, signal)
            }
            
            // Now safe to continue-as-new
            return workflow.NewContinueAsNewError(ctx, MyWorkflow, state)
        }
    }
}

// For senders: Use SignalWithStart to handle the race
func sendSignalSafely(ctx context.Context, c client.Client, workflowID string, signal Signal) error {
    // SignalWithStart will:
    // - Signal existing workflow if running
    // - Start new workflow with signal if not running (handles continue-as-new gap)
    _, err := c.SignalWithStartWorkflow(ctx,
        workflowID,
        "my-signal",
        signal,
        client.StartWorkflowOptions{
            ID:        workflowID,
            TaskQueue: "my-task-queue",
        },
        MyWorkflow,
        initialState,
    )
    return err
}
```

### Prevention
- Always drain signals before `ContinueAsNew`
- Senders use `SignalWithStart` instead of plain `Signal`
- External systems use Temporal as source of truth (pull from query, don't rely on push)
- Idempotency in signal processing (handle duplicates from retry)

---

## Issue #19: Large Payload Serialization Bottleneck [HIGH]

### Symptoms
- Activity execution time dominated by serialization (not business logic)
- Network bandwidth saturated between worker and Temporal server
- `temporal_persistence_latency` high for history writes
- Workflow task completion slow (large history to read)

### Root Cause
Every activity input/output is stored in workflow history. Large payloads:
- 1MB activity result × 1000 activities = 1GB history
- Every workflow task requires reading entire history
- JSON serialization of complex objects is CPU-intensive
- Database writes slow with large event payloads

### Impact
- **Business**: Slow workflow progress, high latency
- **System**: Database storage bloat, network congestion
- **Scale**: 1M workflows × 10MB each = 10TB database

### Detection
```promql
# Payload size
temporal_workflow_history_size_bytes{quantile="0.99"} > 10000000  # 10MB

# Serialization time
temporal_activity_execution_latency_seconds - temporal_activity_business_logic_seconds > 1
```

### Resolution
```go
// WRONG: Large data directly in workflow
func MyWorkflow(ctx workflow.Context) error {
    var largeResult []byte  // 10MB response stored in history!
    workflow.ExecuteActivity(ctx, FetchAllData).Get(ctx, &largeResult)
    
    workflow.ExecuteActivity(ctx, ProcessData, largeResult).Get(ctx, nil)  // 10MB input!
    return nil
}

// CORRECT: Pass references, not data
func MyWorkflow(ctx workflow.Context) error {
    var dataRef DataReference  // Just a pointer (S3 bucket + key) - 100 bytes
    workflow.ExecuteActivity(ctx, FetchAndStoreData).Get(ctx, &dataRef)
    
    workflow.ExecuteActivity(ctx, ProcessFromReference, dataRef).Get(ctx, nil)
    return nil
}

// Activity stores data externally, returns reference
func FetchAndStoreData(ctx context.Context) (DataReference, error) {
    data, err := fetchLargeData()  // 10MB
    if err != nil {
        return DataReference{}, err
    }
    
    // Store in S3/blob, return reference
    ref := DataReference{
        Bucket: "workflow-data",
        Key:    fmt.Sprintf("data/%s/%s", activity.GetInfo(ctx).WorkflowExecution.ID, uuid.New()),
    }
    err = s3Client.PutObject(ref.Bucket, ref.Key, data)
    return ref, err
}

// Custom data converter with compression
type CompressedDataConverter struct {
    parent converter.DataConverter
}

func (c *CompressedDataConverter) ToPayload(value interface{}) (*commonpb.Payload, error) {
    payload, err := c.parent.ToPayload(value)
    if err != nil {
        return nil, err
    }
    
    // Compress payloads > 1KB
    if len(payload.Data) > 1024 {
        compressed := snappy.Encode(nil, payload.Data)
        payload.Data = compressed
        payload.Metadata["encoding"] = []byte("snappy")
    }
    return payload, nil
}
```

### Prevention
- **Rule**: No payload > 100KB in workflow history
- Use blob storage (S3, GCS) for large data, pass references
- Custom data converter with compression (snappy/zstd)
- Payload size alert at 1MB
- Proto instead of JSON for serialization (2-10x smaller)

---

## Issue #20: Child Workflow Failure Propagation Storm [HIGH]

### Symptoms
- Parent workflow fails because one child failed
- 1000 child workflows started, 1 fails -> all 999 others cancelled
- Massive cancellation cascade through workflow tree
- Resources wasted on already-completed work

### Root Cause
Default `ChildWorkflowOptions.ParentClosePolicy` is `TERMINATE`:
- When parent fails/cancels, ALL children are terminated
- When any child fails with default error handling, parent fails -> siblings terminated
- Fan-out of 1000 children: one failure kills everything

### Impact
- **Business**: 99.9% successful work discarded because of 0.1% failure
- **System**: Cancellation storm generates thousands of events
- **Scale**: Deep workflow trees: one leaf failure cascades up entire tree

### Detection
```promql
# Mass cancellation events
rate(temporal_workflow_canceled_total[5m]) > 100

# Child workflow failure causing parent failure
rate(temporal_workflow_failed_total{has_children="true"}[5m]) > 0
```

### Resolution
```go
// WRONG: Default behavior - one child failure kills parent
func ParentWorkflow(ctx workflow.Context, items []Item) error {
    var futures []workflow.ChildWorkflowFuture
    for _, item := range items {
        future := workflow.ExecuteChildWorkflow(ctx, ProcessItem, item)
        futures = append(futures, future)
    }
    
    // One failure here fails the parent -> cancels all other children
    for _, f := range futures {
        if err := f.Get(ctx, nil); err != nil {
            return err  // WRONG: kills all siblings
        }
    }
    return nil
}

// CORRECT: Isolate child failures, handle gracefully
func ParentWorkflow(ctx workflow.Context, items []Item) error {
    childOpts := workflow.ChildWorkflowOptions{
        // Don't kill children if parent closes
        ParentClosePolicy: enums.PARENT_CLOSE_POLICY_ABANDON,
        
        RetryPolicy: &temporal.RetryPolicy{
            MaximumAttempts: 3,
        },
    }
    childCtx := workflow.WithChildOptions(ctx, childOpts)
    
    var futures []workflow.ChildWorkflowFuture
    var results []Result
    var failures []FailedItem
    
    // Fan-out
    for _, item := range items {
        future := workflow.ExecuteChildWorkflow(childCtx, ProcessItem, item)
        futures = append(futures, future)
    }
    
    // Collect results, tolerating individual failures
    for i, f := range futures {
        var result Result
        if err := f.Get(ctx, &result); err != nil {
            // Log failure but continue
            failures = append(failures, FailedItem{
                Item:  items[i],
                Error: err.Error(),
            })
            continue  // Don't kill parent!
        }
        results = append(results, result)
    }
    
    // Handle failures separately
    if len(failures) > 0 {
        if float64(len(failures))/float64(len(items)) > 0.1 {
            // > 10% failure rate - escalate
            return fmt.Errorf("batch failure: %d/%d items failed", len(failures), len(items))
        }
        // Process failures (DLQ, retry, alert)
        workflow.ExecuteActivity(ctx, HandleFailedItems, failures).Get(ctx, nil)
    }
    
    return nil
}
```

### Prevention
- Always set `ParentClosePolicy` explicitly
- Never let one child failure kill parent (collect errors, decide at end)
- Set failure threshold (e.g., > 10% failure = overall failure)
- Use `PARENT_CLOSE_POLICY_ABANDON` for independent children
- Monitor child failure rates separately from parent

---

## Issue #21: Query Handler Blocking Workflow Progress [HIGH]

### Symptoms
- Workflow progress stalls when queries are frequent
- Workflow task latency spikes correlate with query traffic
- Query timeouts while workflow is busy
- Mutual interference between queries and execution

### Root Cause
Queries execute on the workflow worker thread:
- Query handlers share the same goroutine as workflow execution
- Long-running query (complex state computation) blocks workflow progress
- High query QPS can starve workflow task processing
- Worker must replay history before answering query (on non-sticky worker)

### Impact
- **Business**: Workflow progress delayed, query consumers get timeouts
- **System**: Worker thread contention between queries and execution
- **Scale**: Customer support tool querying 1000s of workflows/min

### Detection
```promql
# Query latency elevated
temporal_workflow_query_latency_seconds{quantile="0.99"} > 5

# Workflow task latency correlates with query rate
correlation(temporal_workflow_task_execution_latency_seconds, temporal_workflow_query_rate)
```

### Resolution
```go
// WRONG: Expensive query handler
func MyWorkflow(ctx workflow.Context) error {
    var state ComplexState
    
    // Query handler does expensive computation
    workflow.SetQueryHandler(ctx, "get-analytics", func() (Analytics, error) {
        // EXPENSIVE: computes on every query call
        return computeAnalytics(state)  // Takes 500ms
    })
    
    // ... workflow logic
}

// CORRECT: Pre-compute query results, keep handler fast
func MyWorkflow(ctx workflow.Context) error {
    var state ComplexState
    var cachedAnalytics Analytics  // Pre-computed
    
    // Query handler just returns cached value (< 1ms)
    workflow.SetQueryHandler(ctx, "get-analytics", func() (Analytics, error) {
        return cachedAnalytics, nil  // Instant return
    })
    
    // Update cached analytics when state changes
    updateAnalytics := func() {
        cachedAnalytics = computeAnalytics(state)
    }
    
    signalCh := workflow.GetSignalChannel(ctx, "event")
    for {
        var event Event
        signalCh.Receive(ctx, &event)
        processEvent(&state, event)
        updateAnalytics()  // Maintain cache incrementally
    }
}

// For heavy queries, use Search Attributes instead
func MyWorkflow(ctx workflow.Context) error {
    // Update search attributes (visible without replay)
    workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
        "OrderStatus": "PROCESSING",
        "TotalAmount": 1500.00,
        "ItemCount":   5,
    })
    // Queries can use visibility API (no workflow replay needed)
}
```

### Prevention
- Query handlers should be O(1) - return cached state
- Use Search Attributes for frequently queried data (no replay needed)
- Rate limit queries per workflow
- Separate query-heavy workflows to dedicated workers
- Use Update handlers for state mutations (new in Temporal)

---

## Issue #22: Workflow State Corruption from Non-Determinism [CRITICAL]

### Symptoms
- `non-deterministic workflow` error in worker logs
- Workflow stuck after code deployment
- Replay produces different commands than original execution
- `Nondeterminism detected: historyEvent does not match command`

### Root Cause
Workflow code changed in a way that produces different execution path on replay:
- Activity order changed
- Conditional logic modified
- New activity added before existing ones
- Timer duration changed
- Third-party library update changed behavior

### Impact
- **Business**: Workflow permanently stuck, cannot make progress without intervention
- **System**: Worker logs flooded with nondeterminism errors
- **Scale**: Every in-flight workflow using the changed code is affected

### Detection
```promql
# Non-determinism errors
rate(temporal_workflow_task_execution_failed_total{failure_reason="NonDeterministicError"}[5m]) > 0
```

### Resolution
```go
// Use workflow versioning to handle code changes
func MyWorkflow(ctx workflow.Context, input Input) error {
    // Version 1 behavior (original)
    v := workflow.GetVersion(ctx, "change-1", workflow.DefaultVersion, 1)
    
    if v == workflow.DefaultVersion {
        // Old code path (for in-flight workflows started before this deploy)
        workflow.ExecuteActivity(ctx, OldActivity, input).Get(ctx, nil)
    } else {
        // New code path (for newly started workflows)
        workflow.ExecuteActivity(ctx, NewValidation, input).Get(ctx, nil)
        workflow.ExecuteActivity(ctx, NewActivity, input).Get(ctx, nil)
    }
    
    // Common code continues here
    workflow.ExecuteActivity(ctx, FinalStep, input).Get(ctx, nil)
    return nil
}

// After all old workflows complete, remove old branch:
func MyWorkflow(ctx workflow.Context, input Input) error {
    workflow.GetVersion(ctx, "change-1", 1, 1)  // Min=1, no more DefaultVersion
    
    workflow.ExecuteActivity(ctx, NewValidation, input).Get(ctx, nil)
    workflow.ExecuteActivity(ctx, NewActivity, input).Get(ctx, nil)
    workflow.ExecuteActivity(ctx, FinalStep, input).Get(ctx, nil)
    return nil
}
```

**Emergency recovery:**
```bash
# Find all affected workflows
tctl workflow list --query "WorkflowType='MyWorkflow' AND ExecutionStatus='Running'"

# Option 1: Reset to before the breaking change
tctl workflow reset-batch --query "WorkflowType='MyWorkflow' AND ExecutionStatus='Running'" \
  --reset-type LastWorkflowTask --reason "non-determinism fix"

# Option 2: Rollback the worker deployment
kubectl rollout undo deployment/temporal-worker
```

### Prevention
- ALWAYS use `workflow.GetVersion()` when changing workflow logic
- Replay tests in CI (replay production histories against new code)
- Canary deployment: deploy new worker, monitor for non-determinism errors
- Never change: activity order, timer durations, conditional logic without versioning

---

## Issue #23: Search Attribute Payload Size Limit [MEDIUM]

### Symptoms
- `UpsertSearchAttributes` fails silently or with error
- Visibility queries return stale data
- Search attributes not updated despite workflow making progress
- Elasticsearch rejects documents

### Root Cause
- Individual search attribute value exceeds max size (2KB for keyword, 40KB for text)
- Total search attributes per workflow exceeds limit
- Elasticsearch field mapping conflict (text vs keyword)
- Too many unique search attribute keys (index explosion)

### Detection
```promql
# Visibility write failures
rate(temporal_visibility_persistence_errors_total[5m]) > 0

# Elasticsearch indexing errors
elasticsearch_indexing_failed_total > 0
```

### Resolution
```go
// WRONG: Large values in search attributes
workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
    "FullOrderJSON": string(largeJSON),  // 50KB - too large!
    "AllItemNames":  strings.Join(thousandItems, ","),  // Exceeds limit
})

// CORRECT: Summary data only
workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
    "OrderStatus":  "PROCESSING",
    "CustomerID":   "cust-123",
    "TotalAmount":  1500.00,
    "ItemCount":    len(items),
    "Region":       "us-east-1",
    "Priority":     "HIGH",
    "ErrorMessage": truncate(errMsg, 200),  // Truncate to safe size
})

func truncate(s string, maxLen int) string {
    if len(s) <= maxLen {
        return s
    }
    return s[:maxLen] + "..."
}
```

### Prevention
- Search attributes for QUERYING, not data storage
- Maximum 20-30 search attributes per workflow type
- Monitor Elasticsearch index size and field count
- Use custom field types appropriately (Keyword for exact match, Int for ranges)
- Document search attribute schema per workflow type

---

## Issue #24: Timer Drift in Long-Running Workflows [MEDIUM]

### Symptoms
- Scheduled actions fire at slightly wrong times
- Billing cycles drift by minutes/hours over months
- Timer-based SLAs trigger incorrectly
- Time-sensitive workflows behave inconsistently across replays

### Root Cause
Temporal timers are durable but have characteristics:
- Timer resolution is not sub-second precise
- Timer fires are based on server clock, not workflow clock
- During replay, timers are resolved from history (exact match)
- Server-side timer batch processing introduces small delays

### Detection
```promql
# Timer fire accuracy
histogram_quantile(0.99, temporal_timer_fire_latency_seconds_bucket) > 5
```

### Resolution
```go
// WRONG: Relying on exact timer precision
func BillingWorkflow(ctx workflow.Context) error {
    // Don't assume timer fires at exact millisecond
    workflow.Sleep(ctx, 24*time.Hour)  // May fire slightly late
    chargeCustomer()  // Billing time might drift
}

// CORRECT: Use absolute timestamps for precision
func BillingWorkflow(ctx workflow.Context, state BillingState) error {
    now := workflow.Now(ctx)
    nextBillingTime := computeNextBillingTime(state.LastBilledAt)
    sleepDuration := nextBillingTime.Sub(now)
    
    if sleepDuration > 0 {
        workflow.Sleep(ctx, sleepDuration)
    }
    
    // Use server time for the actual billing timestamp (not timer fire time)
    var billingResult BillingResult
    workflow.ExecuteActivity(ctx, ChargeBilling, state).Get(ctx, &billingResult)
    
    // Next cycle uses the actual billing time, not timer fire time
    state.LastBilledAt = billingResult.BilledAt
    return workflow.NewContinueAsNewError(ctx, BillingWorkflow, state)
}

// For cron-like precision, use Temporal Schedules (server-side)
// tctl schedule create --schedule-id "daily-billing" \
//   --interval "24h" --workflow-type "BillingWorkflow"
```

### Prevention
- Don't rely on timer firing at exact millisecond
- Use `workflow.Now(ctx)` for deterministic time in workflows
- For cron precision, use Temporal Schedules feature
- Store absolute timestamps, compute relative durations
- Tolerance windows for time-sensitive operations

---

## Issue #25: Workflow Update Rejection Under Load [HIGH]

### Symptoms
- `workflow.Update` calls return timeout or rejection
- Workflow state not mutated despite successful-looking calls
- Update validators reject valid requests intermittently
- Update throughput lower than expected

### Root Cause
Updates (new feature) require workflow to process an update task:
- Workflow must be on a worker to accept updates
- If workflow is replaying or processing another task, update queues
- Update validator runs synchronously on workflow goroutine
- High update rate can overwhelm single workflow

### Detection
```promql
# Update rejection rate
rate(temporal_workflow_update_rejected_total[5m]) > 10

# Update latency
temporal_workflow_update_latency_seconds{quantile="0.99"} > 10
```

### Resolution
```go
// Register update handler with fast validator
func MyWorkflow(ctx workflow.Context, state *State) error {
    // Update handler with validation
    err := workflow.SetUpdateHandlerWithOptions(ctx, "modify-order",
        func(ctx workflow.Context, modification Modification) (Result, error) {
            // Execute the mutation
            return applyModification(state, modification)
        },
        workflow.UpdateHandlerOptions{
            Validator: func(ctx workflow.Context, modification Modification) error {
                // FAST validation only - no I/O, no heavy computation
                if modification.Amount < 0 {
                    return fmt.Errorf("invalid amount")
                }
                if state.Status == "COMPLETED" {
                    return fmt.Errorf("cannot modify completed order")
                }
                return nil  // Accept the update
            },
        },
    )
    
    // ... rest of workflow
}

// For high-throughput mutations, batch updates via signals instead
func HighThroughputWorkflow(ctx workflow.Context, state *State) error {
    updateCh := workflow.GetSignalChannel(ctx, "batch-update")
    ticker := workflow.NewTicker(ctx, 100*time.Millisecond)
    
    for {
        select {
        case <-ticker.C:
            // Process all queued updates in batch
            var updates []Update
            for updateCh.ReceiveAsync(&update) {
                updates = append(updates, update)
            }
            if len(updates) > 0 {
                applyBatchUpdates(state, updates)
            }
        }
    }
}
```

### Prevention
- Update validators must be fast (< 1ms)
- For high-throughput, prefer signals over updates
- One update at a time per workflow (natural serialization)
- Monitor update rejection rate and latency

---

## Issue #26: Workflow Cancellation Not Propagating [HIGH]

### Symptoms
- Cancelled workflow continues executing activities
- Resources not released after cancellation
- Downstream services still being called
- Compensation logic never runs

### Root Cause
Cancellation in Temporal is cooperative:
- Workflow must check for cancellation explicitly
- Activities don't automatically stop on workflow cancellation
- `ctx.Err()` must be checked in activities
- Long-running activities without heartbeat ignore cancellation

### Detection
```promql
# Workflows cancelled but activities still running
temporal_workflow_canceled_total > 0
  AND temporal_activity_execution_active{workflow_status="canceled"} > 0
```

### Resolution
```go
// WRONG: Ignores cancellation
func MyWorkflow(ctx workflow.Context) error {
    workflow.ExecuteActivity(ctx, Step1).Get(ctx, nil)
    workflow.ExecuteActivity(ctx, Step2).Get(ctx, nil)  // Runs even if cancelled!
    workflow.ExecuteActivity(ctx, Step3).Get(ctx, nil)
    return nil
}

// CORRECT: Handle cancellation with cleanup
func MyWorkflow(ctx workflow.Context) error {
    // Set up deferred cancellation handler
    defer func() {
        if ctx.Err() == workflow.ErrCanceled {
            // Create new context for cleanup (original is cancelled)
            cleanupCtx, _ := workflow.NewDisconnectedContext(ctx)
            workflow.ExecuteActivity(cleanupCtx, ReleaseResources).Get(cleanupCtx, nil)
            workflow.ExecuteActivity(cleanupCtx, NotifyCancellation).Get(cleanupCtx, nil)
        }
    }()
    
    // Main workflow logic
    err := workflow.ExecuteActivity(ctx, Step1).Get(ctx, nil)
    if err != nil {
        return err  // Returns ErrCanceled if cancelled
    }
    
    err = workflow.ExecuteActivity(ctx, Step2).Get(ctx, nil)
    if err != nil {
        return err
    }
    
    return nil
}

// Activity that respects cancellation
func LongRunningActivity(ctx context.Context, input Input) error {
    for i := 0; i < len(input.Items); i++ {
        // Check cancellation regularly
        select {
        case <-ctx.Done():
            // Clean up partial work
            return ctx.Err()
        default:
        }
        
        processItem(input.Items[i])
        activity.RecordHeartbeat(ctx, i)
    }
    return nil
}
```

### Prevention
- Always handle `workflow.ErrCanceled` in workflow code
- Use `NewDisconnectedContext` for cleanup activities
- Activities MUST check `ctx.Done()` in loops
- HeartbeatTimeout enables cancellation detection (no heartbeat = no cancellation)
- Test cancellation paths explicitly

---

## Issue #27: Visibility Query Performance Degradation [MEDIUM]

### Symptoms
- `ListWorkflow` API calls timeout
- Elasticsearch query latency > 10s
- Dashboard/UI loading slowly
- Visibility queries returning stale results

### Root Cause
- Too many open workflows creating large index
- Complex query patterns (wildcard, regex) on large datasets
- Elasticsearch cluster under-provisioned
- Missing index optimization (no ILM, no rollover)

### Detection
```promql
# Visibility query latency
temporal_visibility_persistence_latency_seconds{operation="ListWorkflows", quantile="0.99"} > 5

# Elasticsearch query rate
elasticsearch_query_rate > elasticsearch_query_capacity * 0.8
```

### Resolution
```yaml
# Elasticsearch Index Lifecycle Management
PUT _ilm/policy/temporal-visibility-policy
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "7d"
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 }
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

```go
// Efficient visibility queries
// WRONG: Expensive wildcard query
workflows, _ := c.ListWorkflow(ctx, &workflowservice.ListWorkflowExecutionsRequest{
    Query: `WorkflowType = 'Order%'`,  // Wildcard - full scan
})

// CORRECT: Exact match with indexed fields
workflows, _ := c.ListWorkflow(ctx, &workflowservice.ListWorkflowExecutionsRequest{
    Query: `WorkflowType = 'OrderWorkflow' AND CustomStringField = 'customer-123' AND CloseTime > '2024-01-01'`,
})
```

### Prevention
- Index Lifecycle Management on Elasticsearch
- Limit open workflow queries to recent time ranges
- Use exact match on indexed fields (avoid wildcards)
- Separate hot/warm/cold indices
- Monitor Elasticsearch cluster health

---

## Issue #28: Memo Size Causing Slow Workflow Start [MEDIUM]

### Symptoms
- `StartWorkflow` API latency high (> 1s)
- Large memo attached to workflow start
- Database write latency elevated
- Workflow list/describe operations slow

### Root Cause
Memos are stored with the workflow execution record:
- Large memos (> 100KB) slow down persistence writes
- Memo is returned in every List/Describe call
- No compression on memo by default
- Memo stored in both execution table and visibility

### Detection
```promql
# Start workflow latency
temporal_frontend_request_latency_seconds{operation="StartWorkflowExecution", quantile="0.99"} > 1
```

### Resolution
```go
// WRONG: Large memo
_, err := c.ExecuteWorkflow(ctx, client.StartWorkflowOptions{
    Memo: map[string]interface{}{
        "full_request": largeJSON,      // 500KB memo!
        "all_items":    thousandItems,
    },
})

// CORRECT: Minimal memo, data in activity/storage
_, err := c.ExecuteWorkflow(ctx, client.StartWorkflowOptions{
    Memo: map[string]interface{}{
        "request_id":  "req-123",       // Reference only
        "customer":    "cust-456",
        "item_count":  len(items),
        "initiated_by": "api-gateway",
    },
})
```

### Prevention
- Memo < 10KB (metadata only, not data)
- Use Search Attributes for queryable fields
- Store large context in activity (S3/database), pass reference
- Monitor memo sizes per workflow type

---

## Issue #29: Workflow Execution Already Started Conflict [MEDIUM]

### Symptoms
- `WorkflowExecutionAlreadyStarted` error on start attempts
- Clients retry starting workflows that are already running
- Duplicate workflow detection working but confusing
- Race conditions between check-and-start

### Root Cause
Temporal enforces unique workflow IDs within a namespace:
- If workflow "order-123" is already running, starting another "order-123" fails
- Common in event-driven systems where multiple events trigger same workflow
- `WorkflowIDReusePolicy` controls behavior after completion
- `WorkflowIDConflictPolicy` controls behavior while running (new)

### Detection
```promql
# Already started errors
rate(temporal_frontend_request_errors_total{error_type="WorkflowExecutionAlreadyStarted"}[5m]) > 10
```

### Resolution
```go
// Option 1: Use SignalWithStart for idempotent start-or-signal
_, err := c.SignalWithStartWorkflow(ctx,
    "order-" + orderID,  // Workflow ID
    "new-event",         // Signal name
    eventData,           // Signal payload
    client.StartWorkflowOptions{
        ID:                    "order-" + orderID,
        TaskQueue:             "orders-tq",
        WorkflowIDReusePolicy: enums.WORKFLOW_ID_REUSE_POLICY_ALLOW_DUPLICATE,
    },
    OrderWorkflow,
    initialState,
)
// This will signal existing workflow OR start new one - never fails with AlreadyStarted

// Option 2: Handle the error gracefully
_, err := c.ExecuteWorkflow(ctx, options, MyWorkflow, input)
if err != nil {
    var alreadyStarted *serviceerror.WorkflowExecutionAlreadyStarted
    if errors.As(err, &alreadyStarted) {
        // Workflow already running - signal it instead
        err = c.SignalWorkflow(ctx, workflowID, "", "new-input", input)
        return err
    }
    return err
}

// Option 3: WorkflowIDConflictPolicy (Temporal 1.24+)
_, err := c.ExecuteWorkflow(ctx, client.StartWorkflowOptions{
    ID:                       "order-" + orderID,
    WorkflowIDConflictPolicy: enums.WORKFLOW_ID_CONFLICT_POLICY_USE_EXISTING,
    // USE_EXISTING: return handle to existing workflow
    // TERMINATE_EXISTING: kill old, start new
    // FAIL: error (default)
}, MyWorkflow, input)
```

### Prevention
- Design workflow IDs carefully (entity-based: "order-{id}", "user-{id}")
- Use `SignalWithStart` for event-driven patterns
- Document ID conflict policy per workflow type
- Handle `AlreadyStarted` error in all callers

---

## Issue #30: Activity Result Caching Inconsistency [MEDIUM]

### Symptoms
- Same activity returns different results on replay
- Non-determinism errors from activity result mismatch
- Occurs when activity has side effects that change over time
- Replay uses cached result but expectation changed

### Root Cause
This is actually CORRECT behavior - Temporal replays the RECORDED result.
The issue is developer confusion:
- Activity executed once, result stored in history
- On replay, stored result is used (activity NOT re-executed)
- Developer expects "fresh" data but gets historical result
- Leads to logic errors if workflow makes decisions on stale replayed data

### Detection
Not a metric issue - this is a design pattern issue. Detected via:
- Business logic producing wrong results after worker restart
- QA finding inconsistencies in replayed workflows

### Resolution
```go
// Understanding: Activities are executed ONCE, result is durable
func MyWorkflow(ctx workflow.Context) error {
    // This activity executes ONCE. On replay, cached result used.
    var price float64
    workflow.ExecuteActivity(ctx, GetCurrentPrice).Get(ctx, &price)
    
    // If you need FRESH data, use a new activity call (new history event)
    // The price above is the price AT THE TIME the activity first ran
    
    // For time-sensitive decisions, make the activity return a timestamp
    var priceData PriceData  // {Price: 100.0, AsOf: "2024-01-01T00:00:00Z"}
    workflow.ExecuteActivity(ctx, GetPriceWithTimestamp).Get(ctx, &priceData)
    
    // Check if price is still valid
    if workflow.Now(ctx).Sub(priceData.AsOf) > 5*time.Minute {
        // Price too old, fetch again (new history event)
        workflow.ExecuteActivity(ctx, GetPriceWithTimestamp).Get(ctx, &priceData)
    }
    
    return nil
}

// Side Effect for non-deterministic values needed in workflow
func MyWorkflow(ctx workflow.Context) error {
    // SideEffect executes once, replays from history (like activity but no task)
    encodedRandom := workflow.SideEffect(ctx, func(ctx workflow.Context) interface{} {
        return rand.Float64()
    })
    
    var random float64
    encodedRandom.Get(&random)
    // 'random' is consistent across replays
    
    return nil
}
```

### Prevention
- Document that activity results are IMMUTABLE once recorded
- Use SideEffect for non-deterministic values in workflow logic
- Include timestamps in activity results for staleness detection
- Design workflows assuming any activity result may be from the past
- Never put current-time-sensitive logic after an activity without fresh data

---

## Summary: History & State Issue Prevention Checklist

```
□ Every loop-based workflow has ContinueAsNew at < 5000 events
□ Payload sizes < 100KB (use external storage for large data)
□ Drain signals before ContinueAsNew
□ Use SignalWithStart for signal senders (handle ContinueAsNew gap)
□ Query handlers are O(1) - return pre-computed cached state
□ Use Search Attributes for frequently queried data
□ Always use workflow.GetVersion() for code changes
□ Replay tests in CI against production histories
□ Child workflows use explicit ParentClosePolicy
□ Handle workflow.ErrCanceled with cleanup (DisconnectedContext)
□ Memo < 10KB, Search Attributes for queryable fields
□ Visibility queries use exact match, time-bounded
□ Activity results understood as immutable/historical
□ Timer precision tolerance in time-sensitive operations
□ Monitor: history_length, history_size, replay_latency, non-determinism errors
```
