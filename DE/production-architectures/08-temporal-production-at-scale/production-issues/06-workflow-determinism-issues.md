# Workflow Design & Determinism Production Issues (#71 - #85)

## Issue #71: Non-Determinism Error from time.Now() in Workflow [CRITICAL]

### Symptoms
- `non-deterministic workflow definition` error after worker restart
- Workflow tasks fail on replay
- Only affects workflows that were mid-execution during restart
- Error: `nondeterminism detected: command does not match`

### Root Cause
Using `time.Now()` directly in workflow code:
- First execution: `time.Now()` returns T1, makes decision based on T1
- Replay: `time.Now()` returns T2 (different!), makes DIFFERENT decision
- Different decision = different commands = non-determinism error

### Impact
- **Business**: All in-flight workflows of this type are stuck
- **System**: Cannot recover without code fix + reset
- **Scale**: Every workflow using the pattern is affected

### Detection
```promql
rate(temporal_workflow_task_execution_failed_total{failure_reason="NonDeterministicError"}[5m]) > 0
```

### Resolution
```go
// WRONG: time.Now() is non-deterministic
func MyWorkflow(ctx workflow.Context) error {
    now := time.Now()  // DIFFERENT on replay!
    if now.Hour() >= 18 {
        // Evening path
    } else {
        // Day path
    }
    return nil
}

// CORRECT: Use workflow.Now() - deterministic, returns replay time
func MyWorkflow(ctx workflow.Context) error {
    now := workflow.Now(ctx)  // Returns original time on replay
    if now.Hour() >= 18 {
        // Evening path - consistent across replays
    } else {
        // Day path
    }
    return nil
}

// Other non-deterministic operations and their safe alternatives:
// WRONG -> CORRECT
// time.Now()           -> workflow.Now(ctx)
// rand.Int()           -> workflow.SideEffect(ctx, func() { return rand.Int() })
// uuid.New()           -> workflow.SideEffect(ctx, func() { return uuid.New() })
// map iteration order  -> sort keys first
// os.Getenv()          -> pass as workflow input or use SideEffect
// goroutine creation   -> workflow.Go(ctx, func())
```

### Prevention
- Linter rule: ban `time.Now`, `rand.*`, `uuid.New` in workflow packages
- Use `go.temporal.io/sdk/contrib/tools/workflowcheck` static analyzer
- Code review checklist: no non-deterministic operations in workflows
- Replay tests that run workflow code against recorded history

---

## Issue #72: Non-Determinism from Map Iteration in Workflow [CRITICAL]

### Symptoms
- Intermittent non-determinism errors (not every replay)
- Error appears randomly, not consistently reproducible
- Affects Go workflows that iterate over maps
- Different workers fail at different points

### Root Cause
Go map iteration order is randomized:
```go
myMap := map[string]Activity{"a": Act1, "b": Act2, "c": Act3}
for key, act := range myMap {
    // Order: could be a,b,c or b,c,a or c,a,b
    // Different order = different activity scheduling order = non-determinism!
    workflow.ExecuteActivity(ctx, act, key)
}
```

### Impact
- **Business**: Random subset of workflows break (depends on map randomization)
- **System**: Hard to diagnose because it's intermittent
- **Scale**: Affects any workflow iterating over maps

### Resolution
```go
// WRONG: Map iteration is non-deterministic
func MyWorkflow(ctx workflow.Context, tasks map[string]TaskConfig) error {
    for name, config := range tasks {  // NON-DETERMINISTIC ORDER!
        workflow.ExecuteActivity(ctx, ProcessTask, name, config).Get(ctx, nil)
    }
    return nil
}

// CORRECT: Sort keys before iteration
func MyWorkflow(ctx workflow.Context, tasks map[string]TaskConfig) error {
    // Sort keys for deterministic order
    keys := make([]string, 0, len(tasks))
    for k := range tasks {
        keys = append(keys, k)
    }
    sort.Strings(keys)
    
    for _, key := range keys {
        config := tasks[key]
        workflow.ExecuteActivity(ctx, ProcessTask, key, config).Get(ctx, nil)
    }
    return nil
}

// ALTERNATIVE: Use slice instead of map
type TaskInput struct {
    Name   string
    Config TaskConfig
}

func MyWorkflow(ctx workflow.Context, tasks []TaskInput) error {
    for _, task := range tasks {  // Slice order is deterministic
        workflow.ExecuteActivity(ctx, ProcessTask, task.Name, task.Config).Get(ctx, nil)
    }
    return nil
}
```

### Prevention
- Static analysis to detect map range in workflow code
- Prefer slices over maps for workflow inputs
- If maps needed, always sort keys before iterating
- Review all existing workflows for map iteration patterns

---

## Issue #73: Non-Determinism from Goroutines in Workflow [CRITICAL]

### Symptoms
- Workflow tasks fail with non-determinism errors
- Errors correlate with concurrent operations in workflow
- Race conditions between goroutines cause different execution paths
- Workflow progress inconsistent between executions

### Root Cause
Using native Go goroutines (`go func()`) in workflow code:
- Go goroutines are not tracked by Temporal's replay mechanism
- Scheduling order of goroutines is non-deterministic
- Must use `workflow.Go()` which is replay-safe

### Impact
- **Business**: Affected workflows stuck, data inconsistency possible
- **System**: Hard to debug (concurrency issues are timing-dependent)
- **Scale**: Every workflow using native goroutines is affected

### Resolution
```go
// WRONG: Native goroutines in workflow
func MyWorkflow(ctx workflow.Context, items []Item) error {
    results := make(chan Result, len(items))
    
    for _, item := range items {
        go func(i Item) {  // WRONG! Not replay-safe
            result := processItem(i)
            results <- result
        }(item)
    }
    
    // Collect results
    for range items {
        <-results
    }
    return nil
}

// CORRECT: Use workflow.Go() for deterministic concurrency
func MyWorkflow(ctx workflow.Context, items []Item) error {
    // Launch concurrent activities using workflow.Go
    var futures []workflow.Future
    for _, item := range items {
        future := workflow.ExecuteActivity(
            workflow.WithActivityOptions(ctx, actOpts),
            ProcessItem, item,
        )
        futures = append(futures, future)
    }
    
    // Collect results deterministically
    for _, f := range futures {
        var result Result
        if err := f.Get(ctx, &result); err != nil {
            return err
        }
    }
    return nil
}

// If you need coroutine-like behavior:
func MyWorkflow(ctx workflow.Context) error {
    resultCh := workflow.NewChannel(ctx)  // Temporal channel, not Go channel
    
    workflow.Go(ctx, func(gCtx workflow.Context) {
        // This is replay-safe
        var result Result
        workflow.ExecuteActivity(gCtx, DoWork).Get(gCtx, &result)
        resultCh.Send(gCtx, result)
    })
    
    var result Result
    resultCh.Receive(ctx, &result)
    return nil
}
```

### Prevention
- Linter: ban `go func` and `go ` in workflow packages
- Use `workflow.Go()` for concurrency in workflows
- Use `workflow.NewChannel()` instead of Go channels
- Use `workflow.NewSelector()` instead of `select` statement
- All concurrent patterns must use Temporal SDK primitives

---

## Issue #74: Non-Determinism from Library Upgrade [HIGH]

### Symptoms
- Non-determinism errors appear after dependency update
- Worker rolling update triggers errors
- Third-party library changed serialization/behavior
- Errors only on workflows started before the update

### Root Cause
Library update changed behavior used in workflow code:
- JSON library changed field ordering
- Validation library changed error messages (used in branching)
- Protobuf library changed default values
- Logger library changed output (if somehow affecting flow)

### Impact
- **Business**: All in-flight workflows break after library upgrade
- **System**: Must rollback or version all affected workflows
- **Scale**: Entire fleet affected if library is widely used

### Resolution
```go
// Use workflow versioning when library behavior changes
func MyWorkflow(ctx workflow.Context, input Input) error {
    v := workflow.GetVersion(ctx, "json-library-v2", workflow.DefaultVersion, 1)
    
    if v == workflow.DefaultVersion {
        // Old serialization behavior
        result := oldJsonParse(input.Data)
        // ... rest of workflow
    } else {
        // New serialization behavior
        result := newJsonParse(input.Data)
        // ... rest of workflow
    }
    return nil
}

// Better: Isolate library usage in activities (not in workflow code)
// Activities can use any library version - they execute ONCE, not on replay
func ParseDataActivity(ctx context.Context, data []byte) (ParsedData, error) {
    // Library behavior here doesn't matter - activity runs once
    // Result is stored in history
    return json.Unmarshal(data)
}
```

### Prevention
- **Rule**: Never use third-party libraries in workflow code for logic that affects control flow
- All data transformation in activities (not workflows)
- Pin dependency versions in go.mod
- Test workflow replay against production histories before upgrading
- Workflow code should only use Temporal SDK + Go stdlib (minimal dependencies)

---

## Issue #75: Workflow Versioning Accumulation Technical Debt [HIGH]

### Symptoms
- Workflow code has 20+ version checks
- Code is unreadable, impossible to maintain
- New developers can't understand the flow
- Bug fixes require updating all version branches
- Dead code from old versions never cleaned up

### Root Cause
Every code change adds a new version branch:
```go
v1 := workflow.GetVersion(ctx, "change-1", ...)
v2 := workflow.GetVersion(ctx, "change-2", ...)
v3 := workflow.GetVersion(ctx, "change-3", ...)
// ... 20 more versions
// Combinatorial explosion of code paths
```

### Impact
- **Business**: Slow development velocity, bugs in version matrix
- **System**: Code complexity leads to more bugs
- **Scale**: Long-lived workflows accumulate more versions over months

### Resolution
```go
// Strategy 1: Version reset via ContinueAsNew
// After all old-version workflows complete, reset min version
func MyWorkflow(ctx workflow.Context, input Input) error {
    // Was:
    // v := workflow.GetVersion(ctx, "change-1", workflow.DefaultVersion, 5)
    
    // After all DefaultVersion-4 workflows are done:
    v := workflow.GetVersion(ctx, "change-1", 5, 5)  // Only version 5 exists now
    
    // Clean single code path
    // ... current logic only
}

// Strategy 2: Force ContinueAsNew to reset all workflows to latest code
func ForceResetWorkflow(ctx workflow.Context, state State) error {
    // On every continue-as-new, workflows use latest code
    // No version branches needed because history resets
    info := workflow.GetInfo(ctx)
    if info.GetCurrentHistoryLength() > 100 || shouldUpgrade(state) {
        return workflow.NewContinueAsNewError(ctx, ForceResetWorkflow, state)
    }
    // ... current version logic
}

// Strategy 3: Workflow type versioning (completely new workflow type)
// Instead of in-workflow versioning, create new workflow type
// Old: OrderWorkflowV1, OrderWorkflowV2
// Route new orders to V2, let V1 workflows drain naturally

// Router at start time:
func startOrder(ctx context.Context, c client.Client, order Order) error {
    wfFunc := OrderWorkflowV3  // Always start latest version
    _, err := c.ExecuteWorkflow(ctx, opts, wfFunc, order)
    return err
}
```

```bash
# Find and count workflows still on old versions
tctl workflow list --query "WorkflowType='OrderWorkflow' AND ExecutionStatus='Running' AND StartTime < '2024-01-01'"
# If count is 0, safe to remove old version branches
```

### Prevention
- ContinueAsNew regularly (resets to latest code on next run)
- Maximum 3-5 active versions per workflow
- Track: "oldest running workflow" per type (when 0 old workflows, clean up)
- Workflow type versioning for major rewrites (OrderV1 -> OrderV2)
- Document version cleanup schedule

---

## Issue #76: Workflow Versioning Conflict Across Workers [HIGH]

### Symptoms
- Different workers running different code versions
- Workflow processed correctly on one worker, fails on another
- Version branches behave differently (code path mismatch)
- Partial deployment causes some workflows to break

### Root Cause
During rolling deployment:
- Worker A has old code (version branch: DefaultVersion)
- Worker B has new code (version branch: version 1)
- Workflow starts on A (DefaultVersion path recorded in history)
- Next workflow task goes to B (tries to replay with version 1 path)
- Different workers have different code = non-determinism

### Impact
- **Business**: Random failures during deployment window
- **System**: Workflow failures proportional to deployment progress
- **Scale**: Any rolling deployment becomes risky

### Resolution
```go
// CORRECT versioning that works during rolling deployment:
func MyWorkflow(ctx workflow.Context) error {
    // This is SAFE during rolling deploy because:
    // - Old worker: GetVersion returns DefaultVersion (minSupported)
    // - New worker: GetVersion returns 1 for NEW workflows, DefaultVersion for EXISTING
    // - Key insight: version is recorded in history on FIRST call
    
    v := workflow.GetVersion(ctx, "add-validation", workflow.DefaultVersion, 1)
    
    if v == workflow.DefaultVersion {
        // Old path (both old and new workers can execute this)
        workflow.ExecuteActivity(ctx, ProcessData, input).Get(ctx, nil)
    } else {
        // New path (only new workers execute this for NEW workflows)
        workflow.ExecuteActivity(ctx, ValidateData, input).Get(ctx, nil)
        workflow.ExecuteActivity(ctx, ProcessData, input).Get(ctx, nil)
    }
    return nil
}

// WRONG: This breaks during rolling deploy
func MyWorkflow(ctx workflow.Context) error {
    // Added new activity WITHOUT versioning
    workflow.ExecuteActivity(ctx, ValidateData, input).Get(ctx, nil)  // NEW!
    workflow.ExecuteActivity(ctx, ProcessData, input).Get(ctx, nil)
    // Old worker doesn't have ValidateData -> non-determinism on replay
}
```

**Safe deployment strategy:**
```yaml
# Blue/Green deployment (eliminates rolling update risk)
# 1. Deploy new workers on new task queue (green)
# 2. Route new workflows to green
# 3. Let old workflows drain on blue
# 4. Decommission blue when empty

# OR: Feature flag in workflow
func MyWorkflow(ctx workflow.Context) error {
    v := workflow.GetVersion(ctx, "feature-x", workflow.DefaultVersion, 1)
    if v == 1 {
        // New feature - only for workflows started after full deploy
    }
}
```

### Prevention
- Always use `GetVersion` for ANY workflow code change
- Blue/green deployment for major workflow changes
- Test: deploy new worker, replay old workflow histories
- Never add/remove activities without version guard
- All workers must support both old and new code paths simultaneously

---

## Issue #77: Selector Non-Determinism with Multiple Channels [HIGH]

### Symptoms
- Workflow behavior differs between runs
- `Selector.Select()` picks different branch on replay
- Non-determinism only manifests under specific timing

### Root Cause
When multiple channels are ready simultaneously:
```go
// If both signalCh and timer fire at same time, which wins?
selector.AddReceive(signalCh, signalHandler)
selector.AddFuture(timer, timerHandler)
selector.Select(ctx)  // Which one gets selected first?
```
Temporal SDK handles this deterministically (channels are checked in registration order),
but developers often assume random selection.

### Impact
- **Business**: Logic errors from wrong assumption about selection priority
- **System**: Not a Temporal bug but a developer misunderstanding
- **Scale**: Manifests at high throughput where simultaneous events are common

### Resolution
```go
// UNDERSTAND: Selector checks in ADD ORDER (first added wins if both ready)
func MyWorkflow(ctx workflow.Context) error {
    signalCh := workflow.GetSignalChannel(ctx, "cancel")
    timer := workflow.NewTimer(ctx, 5*time.Minute)
    
    selector := workflow.NewSelector(ctx)
    
    // Priority 1: Check cancel signal first (added first = checked first)
    selector.AddReceive(signalCh, func(ch workflow.ReceiveChannel, more bool) {
        var cancel CancelRequest
        ch.Receive(ctx, &cancel)
        // Handle cancellation
    })
    
    // Priority 2: Timer (only if signal not ready)
    selector.AddFuture(timer, func(f workflow.Future) {
        // Handle timeout
    })
    
    selector.Select(ctx)  // Deterministic: signal checked before timer
    return nil
}

// For explicit priority handling:
func MyWorkflow(ctx workflow.Context) error {
    // Check high-priority channel first (non-blocking)
    var urgentMsg UrgentMessage
    if urgentCh.ReceiveAsync(&urgentMsg) {
        handleUrgent(urgentMsg)
        return nil
    }
    
    // Then do normal selector for other channels
    selector := workflow.NewSelector(ctx)
    selector.AddReceive(normalCh, normalHandler)
    selector.AddFuture(timer, timerHandler)
    selector.Select(ctx)
    return nil
}
```

### Prevention
- Document selector priority order in code comments
- Always add higher-priority channels first to selector
- Use `ReceiveAsync` for explicit priority checking
- Test with simultaneous events (mock concurrent signals + timers)

---

## Issue #78: Activity Retry with Side Effects Causing Duplicates [HIGH]

### Symptoms
- Customer charged twice
- Duplicate notifications sent
- Database records duplicated
- Activity succeeds but response lost -> Temporal retries -> duplicate execution

### Root Cause
Activity completes (side effect happens) but response doesn't reach Temporal:
1. Activity calls payment API: SUCCESS (money deducted)
2. Worker crashes before reporting result to Temporal
3. Temporal retries activity (thinks it never completed)
4. Activity calls payment API again: DUPLICATE charge

### Impact
- **Business**: Double charges, duplicate records, compliance violation
- **System**: Data inconsistency between Temporal state and external systems
- **Scale**: 0.01% activity loss rate × 10M activities/day = 1000 duplicates/day

### Resolution
```go
// SOLUTION: Idempotency keys in every mutating activity
func ChargePayment(ctx context.Context, input PaymentInput) (PaymentResult, error) {
    // Generate deterministic idempotency key from workflow context
    info := activity.GetInfo(ctx)
    idempotencyKey := fmt.Sprintf("%s-%s-%d",
        info.WorkflowExecution.ID,
        info.ActivityID,
        info.Attempt,  // Include attempt for retry distinction if needed
    )
    
    // Call payment API with idempotency key
    result, err := paymentGateway.Charge(ChargeRequest{
        Amount:         input.Amount,
        IdempotencyKey: idempotencyKey,  // Provider deduplicates
    })
    if err != nil {
        return PaymentResult{}, err
    }
    
    return PaymentResult{TransactionID: result.ID}, nil
}

// For systems that don't support idempotency keys natively:
func InsertRecord(ctx context.Context, record Record) error {
    info := activity.GetInfo(ctx)
    
    // Use upsert with workflow-derived unique key
    uniqueKey := fmt.Sprintf("%s-%s", info.WorkflowExecution.ID, record.ID)
    
    _, err := db.Exec(`
        INSERT INTO records (unique_key, data, workflow_id) 
        VALUES ($1, $2, $3)
        ON CONFLICT (unique_key) DO NOTHING`,  // Idempotent!
        uniqueKey, record.Data, info.WorkflowExecution.ID,
    )
    return err
}

// Activity that checks previous execution
func SendNotification(ctx context.Context, input NotificationInput) error {
    info := activity.GetInfo(ctx)
    
    // Check if already sent (for services without idempotency support)
    sent, err := notificationStore.WasSent(info.WorkflowExecution.ID, input.NotificationID)
    if err != nil {
        return err
    }
    if sent {
        return nil  // Already sent, skip
    }
    
    // Send and record
    err = notificationService.Send(input)
    if err != nil {
        return err
    }
    
    // Record that we sent it (for future retry detection)
    return notificationStore.MarkSent(info.WorkflowExecution.ID, input.NotificationID)
}
```

### Prevention
- **Rule**: Every mutating activity MUST have an idempotency mechanism
- Use `WorkflowExecution.ID + ActivityID` as natural idempotency key
- Prefer APIs that support idempotency keys (Stripe, etc.)
- For databases: upsert/ON CONFLICT DO NOTHING patterns
- For APIs without idempotency: check-before-execute pattern
- Track: "idempotency coverage" as a code quality metric

---

## Issue #79: Workflow Logic Depending on External State [HIGH]

### Symptoms
- Workflow makes different decisions on replay vs original execution
- Feature flags checked in workflow code cause non-determinism
- Database lookup in workflow code returns different value on replay
- Environment variable changes cause workflow divergence

### Root Cause
Workflow code depends on external mutable state:
- Feature flag: ON during execution, OFF during replay (non-determinism!)
- Database query in workflow: data changed between execution and replay
- Environment variable: different on new worker vs old worker
- Config file: updated between execution and replay

### Impact
- **Business**: Workflows behave unpredictably after feature flag changes
- **System**: Non-determinism errors requiring manual intervention
- **Scale**: All workflows using the external state are affected

### Resolution
```go
// WRONG: Feature flag in workflow code
func MyWorkflow(ctx workflow.Context, input Input) error {
    if featureFlags.IsEnabled("new-algorithm") {  // NON-DETERMINISTIC!
        // New path
    } else {
        // Old path
    }
}

// CORRECT Option 1: Check feature flag in activity, pass result to workflow
func MyWorkflow(ctx workflow.Context, input Input) error {
    var config WorkflowConfig
    workflow.ExecuteActivity(ctx, LoadConfig).Get(ctx, &config)  // Recorded in history
    
    if config.UseNewAlgorithm {
        // New path - DETERMINISTIC because config is from history
    } else {
        // Old path
    }
}

// CORRECT Option 2: Use SideEffect for one-time external state capture
func MyWorkflow(ctx workflow.Context, input Input) error {
    var useNewAlgo bool
    encoded := workflow.SideEffect(ctx, func(ctx workflow.Context) interface{} {
        return featureFlags.IsEnabled("new-algorithm")  // Captured once, replayed from history
    })
    encoded.Get(&useNewAlgo)
    
    if useNewAlgo {
        // Deterministic - same value on replay
    }
}

// CORRECT Option 3: Pass config as workflow input
func startWorkflow(ctx context.Context, c client.Client) {
    config := WorkflowConfig{
        UseNewAlgorithm: featureFlags.IsEnabled("new-algorithm"),
        MaxRetries:      getEnvInt("MAX_RETRIES"),
    }
    c.ExecuteWorkflow(ctx, opts, MyWorkflow, config)  // Config fixed at start time
}
```

### Prevention
- **Rule**: No external state reads in workflow code
- Feature flags: pass as workflow input or capture in SideEffect
- Database reads: always through activities
- Config: pass as workflow input at start time
- Static analysis: detect http/db/os calls in workflow packages

---

## Issue #80: ContinueAsNew State Serialization Failure [HIGH]

### Symptoms
- `ContinueAsNew` fails with serialization error
- Workflow stuck at continue-as-new point
- Large state cannot be passed to new run
- Error: `payload size exceeds limit`

### Root Cause
State passed to `ContinueAsNew` is too large:
- Accumulated state over long execution (MB of data)
- Includes cached data that should be external
- Serialized state exceeds payload limit (2MB default)
- Circular references in state cause infinite serialization

### Impact
- **Business**: Workflow cannot reset, history grows unbounded
- **System**: Eventually hits 50K event limit
- **Scale**: Any long-running workflow with growing state

### Resolution
```go
// WRONG: Pass entire accumulated state
func MyWorkflow(ctx workflow.Context, state *BigState) error {
    // state grows to 5MB over time
    state.ProcessedItems = append(state.ProcessedItems, newItems...)
    state.AuditLog = append(state.AuditLog, entries...)
    
    return workflow.NewContinueAsNewError(ctx, MyWorkflow, state)  // FAILS: too large
}

// CORRECT: Persist state externally, pass reference
func MyWorkflow(ctx workflow.Context, stateRef StateReference) error {
    // Load minimal state
    var state MinimalState
    workflow.ExecuteActivity(ctx, LoadState, stateRef).Get(ctx, &state)
    
    // Process...
    state.Counter++
    state.LastProcessedID = lastID
    
    // Save full state externally
    var newRef StateReference
    workflow.ExecuteActivity(ctx, SaveState, FullState{
        MinimalState: state,
        ProcessedItems: processedItems,
        AuditLog: auditLog,
    }).Get(ctx, &newRef)
    
    // Continue with just the reference (tiny payload)
    return workflow.NewContinueAsNewError(ctx, MyWorkflow, newRef)
}

type StateReference struct {
    Bucket string `json:"bucket"`
    Key    string `json:"key"`
    Version int   `json:"version"`
}

type MinimalState struct {
    Counter         int    `json:"counter"`
    LastProcessedID string `json:"last_processed_id"`
    Phase           string `json:"phase"`
}
```

### Prevention
- ContinueAsNew payload < 100KB (enforce in code)
- Store full state in S3/database, pass only references
- Design state to be minimal (counters, IDs, phase markers)
- Validate state size before ContinueAsNew
- Prune state regularly (remove completed items)

---

## Issue #81: Signal Handler Registration After Replay Point [MEDIUM]

### Symptoms
- Signals received but handler not invoked
- Workflow appears to ignore specific signals
- Handler works for new workflows but not replayed ones
- Signals delivered but buffered indefinitely

### Root Cause
Signal handler registered conditionally or late in workflow:
- Handler registered after a sleep/activity that hasn't replayed yet
- Conditional registration: handler only added in certain branches
- Signal arrives before handler is registered during replay

### Resolution
```go
// WRONG: Late registration
func MyWorkflow(ctx workflow.Context) error {
    // Do some work first
    workflow.ExecuteActivity(ctx, InitializeData).Get(ctx, nil)
    
    // Register handler AFTER activity (signals before this point are lost!)
    signalCh := workflow.GetSignalChannel(ctx, "update")
    // ...
}

// CORRECT: Register handlers immediately at workflow start
func MyWorkflow(ctx workflow.Context, state State) error {
    // Register ALL signal handlers FIRST, before any activities
    cancelCh := workflow.GetSignalChannel(ctx, "cancel")
    updateCh := workflow.GetSignalChannel(ctx, "update")
    
    // Also set query handlers immediately
    workflow.SetQueryHandler(ctx, "status", func() (Status, error) {
        return state.CurrentStatus, nil
    })
    
    // NOW do activities and processing
    workflow.ExecuteActivity(ctx, InitializeData).Get(ctx, nil)
    
    // Process signals
    selector := workflow.NewSelector(ctx)
    selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
        // Handle cancel
    })
    selector.AddReceive(updateCh, func(ch workflow.ReceiveChannel, more bool) {
        // Handle update
    })
}
```

### Prevention
- **Rule**: Register ALL signal/query/update handlers at workflow start
- Handlers registered before any activity or sleep
- Never conditionally register handlers
- Test: send signal immediately after workflow start, verify received

---

## Issue #82: Activity Return Type Change Breaking Replay [MEDIUM]

### Symptoms
- Non-determinism error mentioning deserialization
- Workflow fails on replay after activity return type changed
- Error: `unable to decode activity result`
- New code can't deserialize old activity results from history

### Root Cause
Activity return type changed in a backward-incompatible way:
```go
// V1: Activity returned string
func GetStatus(ctx context.Context) (string, error) { return "active", nil }

// V2: Activity now returns struct (breaks replay of V1 results!)
func GetStatus(ctx context.Context) (StatusResult, error) { return StatusResult{Status: "active"}, nil }
```

### Impact
- **Business**: In-flight workflows that already ran V1 can't replay
- **System**: Requires workflow reset or version branching
- **Scale**: All workflows that executed the activity before the change

### Resolution
```go
// SAFE: Add fields (backward compatible with JSON)
// V1
type Result struct {
    Status string `json:"status"`
}

// V2 (backward compatible - new fields are optional)
type Result struct {
    Status    string `json:"status"`
    Details   string `json:"details,omitempty"`   // New field, optional
    UpdatedAt int64  `json:"updated_at,omitempty"` // New field, optional
}

// UNSAFE: Rename fields, change types, remove fields
// These break deserialization of old history

// If you must change incompatibly, use workflow versioning:
func MyWorkflow(ctx workflow.Context) error {
    v := workflow.GetVersion(ctx, "status-result-v2", workflow.DefaultVersion, 1)
    
    if v == workflow.DefaultVersion {
        var result string  // Old type
        workflow.ExecuteActivity(ctx, GetStatusV1).Get(ctx, &result)
    } else {
        var result StatusResult  // New type
        workflow.ExecuteActivity(ctx, GetStatusV2).Get(ctx, &result)
    }
}
```

### Prevention
- Activity return types: only ADD fields (never remove or rename)
- Use `json:"...,omitempty"` for new optional fields
- For breaking changes: new activity name + workflow versioning
- Integration test: deserialize old payloads with new types
- Document: activity return type contract is immutable

---

## Issue #83: Workflow Code Calling External Service Directly [MEDIUM]

### Symptoms
- Workflow non-determinism errors
- Workflow task takes unexpectedly long
- External service called during replay (unnecessary load)
- Different results on replay cause divergence

### Root Cause
Developer called external service directly in workflow code instead of through activity:
```go
func MyWorkflow(ctx workflow.Context) error {
    // WRONG: This runs on EVERY replay!
    resp, _ := http.Get("https://api.example.com/status")
    // On replay: response may be different, causing non-determinism
}
```

### Impact
- **Business**: External service called N times (once per replay, not once total)
- **System**: Non-determinism risk + unnecessary external load
- **Scale**: If workflow replays 100 times, external service hit 100 times

### Resolution
```go
// WRONG: Direct external call in workflow
func MyWorkflow(ctx workflow.Context) error {
    resp, _ := http.Get("https://api.example.com/data")  // Called on every replay!
    body, _ := io.ReadAll(resp.Body)
    
    if string(body) == "active" {
        // This branch may differ on replay if API returns different result
    }
}

// CORRECT: All external calls through activities
func MyWorkflow(ctx workflow.Context) error {
    var status string
    err := workflow.ExecuteActivity(ctx, CheckExternalStatus).Get(ctx, &status)
    if err != nil {
        return err
    }
    
    if status == "active" {
        // Deterministic - status is from history, not live API
    }
}

func CheckExternalStatus(ctx context.Context) (string, error) {
    resp, err := http.Get("https://api.example.com/data")
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()
    body, _ := io.ReadAll(resp.Body)
    return string(body), nil
}
```

### Prevention
- Linter rule: ban `net/http`, `database/sql`, `os.File` in workflow packages
- Code review: NO I/O in workflow code
- Package structure: separate `workflows/` and `activities/` packages
- Import restrictions on workflow package (only Temporal SDK + Go stdlib safe packages)

---

## Issue #84: Update Handler Validation Race Condition [MEDIUM]

### Symptoms
- Update accepted but shouldn't have been (validator passed incorrectly)
- State mutation applied in wrong order
- Concurrent updates creating inconsistent state
- Validator sees stale state during rapid updates

### Root Cause
Multiple updates arriving simultaneously:
- Update 1: validator checks state, passes
- Update 2: validator checks state, passes (sees same pre-update-1 state)
- Both mutations applied - may conflict

Temporal processes updates sequentially per workflow, but the validator
runs at proposal time (before the update is committed to history).

### Resolution
```go
// Updates are processed one at a time per workflow (natural serialization)
// The "race condition" is actually in the application's expectation

func MyWorkflow(ctx workflow.Context, state *OrderState) error {
    err := workflow.SetUpdateHandlerWithOptions(ctx, "modify-quantity",
        func(ctx workflow.Context, mod QuantityModification) (OrderState, error) {
            // This handler executes SEQUENTIALLY (one at a time)
            // Previous update's state changes are visible here
            
            // Apply modification
            state.Items[mod.ItemID].Quantity = mod.NewQuantity
            state.UpdatedAt = workflow.Now(ctx)
            
            // Recalculate totals
            state.Total = calculateTotal(state.Items)
            
            return *state, nil
        },
        workflow.UpdateHandlerOptions{
            Validator: func(ctx workflow.Context, mod QuantityModification) error {
                // Validator also runs sequentially per workflow
                // But might run BEFORE previous update's handler completes
                // (validation is at request time, handler is at execution time)
                
                if _, exists := state.Items[mod.ItemID]; !exists {
                    return fmt.Errorf("item %s not found", mod.ItemID)
                }
                if mod.NewQuantity < 0 {
                    return fmt.Errorf("quantity must be >= 0")
                }
                // Don't validate complex state consistency here
                // Do it in the handler where state is guaranteed current
                return nil
            },
        },
    )
    // ...
}
```

### Prevention
- Validators: only check input validity (format, ranges)
- Handlers: check state consistency (business rules)
- Accept that validator may see slightly stale state
- Design mutations to be commutative where possible
- Use versioned state (optimistic concurrency) for complex validations

---

## Issue #85: Workflow Testing Not Catching Determinism Issues [MEDIUM]

### Symptoms
- Tests pass but production breaks with non-determinism
- Unit tests don't replay workflows
- Integration tests only run forward, never replay
- Issues only found after deployment

### Root Cause
- Tests only run workflow forward (never from history)
- Mock activities always return same value (don't test replay variance)
- No replay testing against production histories
- WorkflowTestSuite doesn't exercise all code paths on replay

### Resolution
```go
// 1. Replay test using real production histories
func TestReplayFromHistory(t *testing.T) {
    replayer := worker.NewWorkflowReplayer()
    replayer.RegisterWorkflow(MyWorkflow)
    
    // Download production history
    history := downloadWorkflowHistory("production-wf-id-123")
    
    err := replayer.ReplayWorkflowHistory(nil, history)
    require.NoError(t, err, "Replay should not produce non-determinism error")
}

// 2. Replay test using saved history files
func TestReplayFromFile(t *testing.T) {
    replayer := worker.NewWorkflowReplayer()
    replayer.RegisterWorkflow(MyWorkflow)
    
    // Test against all saved histories
    histories, _ := filepath.Glob("testdata/histories/*.json")
    for _, h := range histories {
        err := replayer.ReplayWorkflowHistoryFromJSONFile(nil, h)
        require.NoError(t, err, "Replay failed for: %s", h)
    }
}

// 3. Save production histories for testing
func saveHistoryForTesting(c client.Client, workflowID string) {
    iter := c.GetWorkflowHistory(ctx, workflowID, "", false, enums.HISTORY_EVENT_FILTER_TYPE_ALL_EVENT)
    
    var events []*historypb.HistoryEvent
    for iter.HasNext() {
        event, _ := iter.Next()
        events = append(events, event)
    }
    
    // Save to testdata/
    data, _ := json.MarshalIndent(events, "", "  ")
    os.WriteFile(fmt.Sprintf("testdata/histories/%s.json", workflowID), data, 0644)
}

// 4. CI pipeline: download N random production histories, replay against new code
// .github/workflows/replay-test.yml:
// - step: Download 100 random workflow histories from production
// - step: Run replay tests against new code
// - step: If any fail -> block deployment
```

```go
// 5. Static analysis for determinism
// go install go.temporal.io/sdk/contrib/tools/workflowcheck@latest
// workflowcheck ./...
// Detects: time.Now(), rand.*, http.*, os.*, direct channel operations
```

### Prevention
- Replay tests mandatory in CI before merge
- Save production histories regularly to testdata
- Static analysis (workflowcheck) in pre-commit hook
- Every code change: replay 100 production histories
- Integration test that runs workflow forward, stops, replays from history

---

## Summary: Workflow Design & Determinism Issue Prevention Checklist

```
□ Ban in workflow code: time.Now, rand.*, uuid.New, http.*, os.*, sql.*
□ Use workflow.Now(ctx), workflow.SideEffect, activities for non-deterministic ops
□ Sort map keys before iteration in workflow code
□ Use workflow.Go() not native goroutines
□ Use workflow.NewChannel() not Go channels
□ Use workflow.NewSelector() not select statement
□ workflow.GetVersion() for EVERY code change in workflow
□ Activity return types: only ADD fields, never remove/rename
□ Feature flags: pass as input or capture in SideEffect
□ ContinueAsNew state < 100KB (store full state externally)
□ Register ALL signal/query/update handlers at workflow start
□ Idempotency keys on all mutating activities
□ Replay tests in CI with production histories
□ workflowcheck static analyzer in pre-commit
□ Maximum 3-5 active versions per workflow (clean up old ones)
```
