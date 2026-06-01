# Operational & Deployment Production Issues (#86 - #100)

## Issue #86: Namespace Rate Limit Exhaustion from Runaway Workflow [CRITICAL]

### Symptoms
- Entire namespace rate-limited: `ResourceExhausted`
- All teams/services sharing the namespace are affected
- One runaway workflow type consuming all available RPS
- Cannot start new workflows or signal existing ones

### Root Cause
A bug in one workflow creates an explosion:
- Infinite loop starting child workflows
- Recursive signal pattern (workflow signals itself)
- Fan-out without bound (start 1M child workflows)
- Activity retry storm (activity always fails, unlimited retries)

### Impact
- **Business**: All applications using the namespace are blocked
- **System**: Namespace completely unusable until runaway is stopped
- **Scale**: One bad workflow can block 1000 other workflows

### Detection
```promql
# Single workflow type consuming disproportionate RPS
topk(1, rate(temporal_service_requests_total{namespace="prod"}[1m]) by (workflow_type)) /
  sum(rate(temporal_service_requests_total{namespace="prod"}[1m])) > 0.8
```

### Resolution
```bash
# 1. Identify the runaway workflow
tctl workflow list --namespace prod \
  --query "ExecutionStatus='Running'" \
  --fields "WorkflowID,WorkflowType,StartTime" | sort -k3 | tail -20

# 2. Terminate the runaway
tctl workflow terminate --namespace prod \
  --workflow-id "runaway-wf-id" \
  --reason "namespace rate limit exhaustion"

# 3. If there are many (batch termination)
tctl workflow terminate-batch --namespace prod \
  --query "WorkflowType='RunawayWorkflow' AND ExecutionStatus='Running'" \
  --reason "batch terminate runaway"

# 4. Increase namespace limit temporarily
# dynamic_config.yaml
frontend.namespaceRPS:
  - value: 50000  # Emergency increase
    constraints:
      namespace: "prod"
```

```go
// Prevention: Bounded child workflow creation
func SafeFanOut(ctx workflow.Context, items []Item) error {
    const maxChildren = 1000
    if len(items) > maxChildren {
        return temporal.NewApplicationError(
            fmt.Sprintf("too many items: %d (max %d)", len(items), maxChildren),
            "TOO_MANY_ITEMS", nil,
        )
    }
    
    for _, item := range items {
        workflow.ExecuteChildWorkflow(ctx, ProcessItem, item)
    }
    return nil
}

// Prevention: Activity retry with maximum attempts
activityOpts := workflow.ActivityOptions{
    RetryPolicy: &temporal.RetryPolicy{
        MaximumAttempts: 10,  // ALWAYS set a maximum
        // Never use MaximumAttempts: 0 (unlimited) in production
    },
}
```

### Prevention
- ALWAYS set `MaximumAttempts` on retry policies
- Bound fan-out (max child workflows per parent)
- Per-workflow-type rate limits
- Separate namespaces for different risk levels
- Monitoring: top workflow types by RPS (detect anomalies)

---

## Issue #87: Temporal Server Version Upgrade Breaking Changes [CRITICAL]

### Symptoms
- Server upgrade causes workflow failures
- API behavior changed (different error codes, different defaults)
- Worker SDK incompatible with new server version
- Visibility queries return different results after upgrade

### Root Cause
- Major version upgrade without reading changelog
- SDK version lag (old SDK with new server)
- Deprecated API removed in new version
- Default configuration values changed

### Impact
- **Business**: Potential data loss, workflow corruption
- **System**: Full or partial outage
- **Scale**: Affects entire cluster

### Resolution
```bash
# Safe upgrade procedure:
# 1. Read release notes for breaking changes
# 2. Upgrade SDK first, test in staging
# 3. Schema migration (if required)
# 4. Upgrade server (rolling, one service at a time)
# 5. Verify in production

# Step-by-step:
# 1. Backup database
pg_dump temporal > backup_before_upgrade.sql

# 2. Run schema migration
temporal-sql-tool update-schema --schema-dir ./schema/postgresql/v96/temporal/versioned

# 3. Upgrade server services one at a time
kubectl set image deployment/temporal-frontend frontend=temporalio/server:1.24.0
# Wait for healthy
kubectl rollout status deployment/temporal-frontend

kubectl set image deployment/temporal-matching matching=temporalio/server:1.24.0
kubectl rollout status deployment/temporal-matching

kubectl set image deployment/temporal-history history=temporalio/server:1.24.0
kubectl rollout status deployment/temporal-history

# 4. Verify
tctl cluster health
tctl namespace list
```

### Prevention
- Read release notes COMPLETELY before upgrading
- Upgrade in staging with production-like load for 1 week
- SDK version should be compatible with target server version
- Never skip major versions (upgrade incrementally: 1.22 -> 1.23 -> 1.24)
- Database backup before every upgrade
- Rollback plan documented and tested

---

## Issue #88: Dynamic Configuration Hot-Reload Failure [HIGH]

### Symptoms
- Configuration changes not taking effect
- Old rate limits still enforced
- Server requires restart for config changes
- Inconsistent config across pods (some reloaded, some didn't)

### Root Cause
- Dynamic config file not mounted properly in Kubernetes
- ConfigMap update not propagating to pods
- File watcher not detecting changes
- Config validation failure (silent rejection of invalid config)

### Impact
- **Business**: Cannot adjust limits during incidents without restart
- **System**: Manual pod restarts needed for config changes
- **Scale**: In multi-pod deployment, inconsistent config between pods

### Detection
```bash
# Check if dynamic config is loaded
curl -s http://temporal-frontend:6933/debug/config | jq .

# Check config file timestamp
kubectl exec temporal-frontend-0 -- stat /etc/temporal/dynamic_config.yaml
```

### Resolution
```yaml
# Kubernetes: ConfigMap with proper mount
apiVersion: v1
kind: ConfigMap
metadata:
  name: temporal-dynamic-config
  namespace: temporal
data:
  dynamic_config.yaml: |
    frontend.namespaceRPS:
      - value: 10000
        constraints:
          namespace: "production"
    history.transferTaskMaxPollerCount:
      - value: 4

---
# Deployment mount with subPath (enables hot reload)
spec:
  containers:
  - name: temporal-server
    volumeMounts:
    - name: dynamic-config
      mountPath: /etc/temporal/dynamic_config
      # Do NOT use subPath - it prevents ConfigMap live updates
  volumes:
  - name: dynamic-config
    configMap:
      name: temporal-dynamic-config

# Server config reference
dynamicConfigClient:
  filepath: /etc/temporal/dynamic_config/dynamic_config.yaml
  pollInterval: 10s  # Check for changes every 10s
```

```bash
# Force config reload without restart
# Update ConfigMap
kubectl create configmap temporal-dynamic-config \
  --from-file=dynamic_config.yaml=./new_config.yaml \
  --dry-run=client -o yaml | kubectl apply -f -

# ConfigMap propagation takes up to 60s (kubelet sync period)
# Verify reload:
kubectl exec temporal-frontend-0 -- cat /etc/temporal/dynamic_config/dynamic_config.yaml
```

### Prevention
- Never use `subPath` for ConfigMap mounts (prevents live updates)
- Set `pollInterval` to 10s for reasonable detection time
- Validate config syntax before applying
- Monitor config load events in server logs
- Test config changes in staging before production

---

## Issue #89: Worker Deployment with Incompatible Changes [HIGH]

### Symptoms
- After deployment, some workflows fail, others work
- `activity type not registered` errors for old activity names
- Workflow versioning conflicts between old and new workers
- Partial functionality during rolling update

### Root Cause
Deployment introduces incompatible changes:
- Activity renamed without maintaining old name
- Workflow function signature changed
- Task queue renamed
- New required activity not registered on all workers

### Impact
- **Business**: Workflow failures during deployment window
- **System**: Partial availability
- **Scale**: Proportional to number of affected in-flight workflows

### Resolution
```go
// Safe activity rename: support both old and new names
func main() {
    w := worker.New(c, "my-task-queue", opts)
    
    // Register new name
    w.RegisterActivity(NewActivityName)
    
    // Keep old name as alias (for in-flight workflows)
    w.RegisterActivityWithOptions(NewActivityName, activity.RegisterOptions{
        Name: "OldActivityName",  // Alias for old references in history
    })
}

// Safe workflow signature change: maintain backward compatibility
// V1: func MyWorkflow(ctx workflow.Context, input string) error
// V2: func MyWorkflow(ctx workflow.Context, input InputStruct) error

// Bridge: Accept both
func MyWorkflow(ctx workflow.Context, input interface{}) error {
    var parsedInput InputStruct
    switch v := input.(type) {
    case string:
        parsedInput = InputStruct{LegacyField: v}  // Convert old format
    case InputStruct:
        parsedInput = v
    default:
        // Try JSON unmarshal
        data, _ := json.Marshal(input)
        json.Unmarshal(data, &parsedInput)
    }
    // ... workflow logic using parsedInput
}
```

**Safe deployment checklist:**
```bash
# 1. Before deployment: check for in-flight workflows
tctl workflow list --query "ExecutionStatus='Running' AND WorkflowType='AffectedWorkflow'" --count

# 2. Deploy with backward compatibility
# - Keep old activity names as aliases
# - Use workflow versioning for logic changes
# - Don't rename task queues

# 3. After deployment: verify no errors
kubectl logs -l app=temporal-worker --since=5m | grep -i "not registered\|error\|panic"

# 4. After all old workflows complete: remove aliases
```

### Prevention
- Never rename activities/workflows without aliases
- Deploy backward-compatible code first, then evolve
- Track in-flight workflow types before deploying changes
- Canary deployment: deploy to 1 worker, monitor errors
- Integration test: new worker replays old workflow histories

---

## Issue #90: Temporal Admin Operations Accidentally Affecting Production [HIGH]

### Symptoms
- Workflows terminated that shouldn't have been
- Namespace configuration changed unexpectedly
- Batch operations wider than intended
- "Fat finger" mistakes with tctl/temporal CLI

### Root Cause
- tctl commands executed against wrong environment
- Batch terminate query too broad
- No confirmation for destructive operations
- Production credentials available on developer machines

### Impact
- **Business**: Irreversible data loss, workflows cannot be recovered
- **System**: Production state corrupted
- **Scale**: Batch operations can affect millions of workflows instantly

### Resolution
```bash
# Prevention: Environment-aware CLI configuration
# ~/.temporal/environments/production.yaml
address: temporal-prod.internal:7233
namespace: production
tls:
  certPath: /certs/prod-client.crt
  keyPath: /certs/prod-client.key

# ~/.temporal/environments/staging.yaml
address: temporal-staging.internal:7233
namespace: staging

# Always specify environment explicitly
temporal workflow list --env production --query "..."
temporal workflow terminate --env production --workflow-id "specific-id"

# NEVER use batch terminate without DRY RUN first
# Step 1: Count affected
temporal workflow count --env production --query "WorkflowType='Batch' AND StartTime < '2024-01-01'"
# Result: 5000 workflows

# Step 2: Sample affected (verify query)
temporal workflow list --env production --query "WorkflowType='Batch' AND StartTime < '2024-01-01'" --limit 10

# Step 3: Only then batch terminate
temporal workflow terminate --env production \
  --query "WorkflowType='Batch' AND StartTime < '2024-01-01'" \
  --reason "cleanup old batch workflows"
```

```yaml
# RBAC: Restrict destructive operations
# Temporal Cloud or self-hosted with authorization plugin
apiVersion: auth.temporal.io/v1
kind: AuthorizationPolicy
metadata:
  name: restrict-production
spec:
  rules:
  - namespace: production
    operations: [TerminateWorkflow, ResetWorkflow, DeleteNamespace]
    allowedRoles: [admin, oncall]
    requireApproval: true  # Two-person rule
```

### Prevention
- Separate credentials for prod vs staging (different cert/key)
- CLI defaults to staging (must explicitly specify `--env production`)
- Batch operations require confirmation + count preview
- RBAC on destructive operations (terminate, reset, delete)
- Audit logging for all admin operations
- Two-person rule for batch operations in production

---

## Issue #91: Temporal Server OOM During Shard Movement [CRITICAL]

### Symptoms
- History service pod OOM killed
- Shard rebalancing triggers memory spike
- Multiple pods fail in cascade (shard redistributes to remaining pods)
- Cluster instability for several minutes after any pod change

### Root Cause
When shard ownership changes:
- New owner must load shard state into memory
- Loading many shards simultaneously = memory spike
- If pod receiving shards is already near memory limit -> OOM
- OOM causes shard to move again -> another pod gets it -> cascade

### Impact
- **Business**: Multi-minute workflow processing stall
- **System**: Cascading OOM across history pods
- **Scale**: More shards = larger spike during rebalancing

### Detection
```promql
# Memory spike during shard acquisition
deriv(container_memory_working_set_bytes{container="temporal-history"}[1m]) > 500000000  # 500MB/min

# OOM kills
kube_pod_container_status_last_terminated_reason{reason="OOMKilled", container="temporal-history"} > 0
```

### Resolution
```yaml
# 1. Increase history pod memory limits
resources:
  requests:
    memory: 8Gi
  limits:
    memory: 12Gi  # 50% headroom for shard loading spikes

# 2. Limit concurrent shard acquisition
# dynamic_config.yaml
history.shardControllerMaxShardAcquisitions:
  - value: 4  # Only acquire 4 shards at a time (not all at once)

history.shardControllerMaxShardAcquisitionsPerHost:
  - value: 2  # Max 2 shards loading simultaneously per pod

# 3. More pods = fewer shards per pod = smaller spike
# 512 shards / 16 pods = 32 shards per pod (manageable)
# vs 512 shards / 4 pods = 128 shards per pod (dangerous)

# 4. Pod anti-affinity (spread across nodes)
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchLabels:
          app: temporal-history
      topologyKey: kubernetes.io/hostname
```

### Prevention
- History pod memory = 2x (shards_per_pod × average_shard_memory_footprint)
- Limit concurrent shard acquisitions
- More history pods (fewer shards per pod)
- PodDisruptionBudget preventing simultaneous terminations
- Node anti-affinity (one history pod per node)

---

## Issue #92: Workflow Search/List Performance in UI [HIGH]

### Symptoms
- Temporal Web UI extremely slow to load
- Listing workflows takes 30s+
- UI timeout on large namespaces
- Team productivity impacted (can't find/debug workflows)

### Root Cause
- Elasticsearch under-provisioned for query volume
- UI querying without time filter (scanning all history)
- Too many open workflows (millions) making listing slow
- Custom search attribute queries not indexed properly

### Detection
```promql
# UI query latency
temporal_frontend_request_latency_seconds{operation="ListWorkflowExecutions", quantile="0.99"} > 10
```

### Resolution
```yaml
# 1. Elasticsearch optimization
# Index settings for temporal-visibility
PUT temporal-visibility/_settings
{
  "index": {
    "number_of_replicas": 1,
    "refresh_interval": "5s",
    "max_result_window": 10000
  }
}

# 2. Add time-based default to UI queries
# Always include time filter in visibility queries
query: "StartTime > '2024-01-01' AND ExecutionStatus='Running'"

# 3. Separate Elasticsearch cluster for visibility (not shared)
# Dedicated hot nodes for recent data
```

```go
// API pattern: always include time bounds
func listRecentWorkflows(c client.Client, wfType string) {
    oneWeekAgo := time.Now().AddDate(0, 0, -7).Format(time.RFC3339)
    query := fmt.Sprintf(
        "WorkflowType='%s' AND StartTime > '%s' AND ExecutionStatus='Running'",
        wfType, oneWeekAgo,
    )
    
    resp, _ := c.ListWorkflow(ctx, &workflowservice.ListWorkflowExecutionsRequest{
        Query:    query,
        PageSize: 20,  // Don't fetch all
    })
}
```

### Prevention
- Time-bounded queries (always include StartTime/CloseTime filter)
- Pagination (never query all workflows at once)
- Dedicated Elasticsearch cluster for Temporal visibility
- ILM: move old indices to warm/cold nodes
- Pre-built views for common queries (saved searches)

---

## Issue #93: Namespace Deletion Cascade [HIGH]

### Symptoms
- Namespace accidentally deleted
- All workflows in namespace gone
- Cannot recreate namespace with same name (retention period)
- Business-critical workflows lost

### Root Cause
- Accidental `tctl namespace delete` on production
- Automation script targeting wrong namespace
- Insufficient RBAC on namespace management
- No confirmation required for delete

### Detection
- Post-incident: namespace no longer exists
- Monitoring gap: workflows stop reporting metrics

### Resolution
```bash
# THERE IS NO UNDO for namespace deletion
# The namespace enters a retention period and is eventually purged

# If caught within retention period:
# Contact Temporal support (Cloud) or check if data is still in database

# Self-hosted: Data may still be in database if retention hasn't expired
# Query directly:
psql -h pg-primary -U temporal -d temporal \
  -c "SELECT * FROM namespaces WHERE name = 'deleted-namespace';"

# If archival was enabled, workflow histories are in S3:
aws s3 ls s3://temporal-archival/production/
```

**Prevention (most important):**
```yaml
# 1. RBAC - only platform admins can delete namespaces
# 2. Confirmation with namespace name typing
# 3. Soft-delete with 7-day retention
# 4. Alerting on any namespace deletion

# Kubernetes RBAC for tctl access
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: temporal-readonly
rules:
- apiGroups: [""]
  resources: ["pods/exec"]
  verbs: ["create"]
  # Only read operations via exec into admin pod
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: temporal-admin
rules:
- apiGroups: [""]
  resources: ["pods/exec"]
  verbs: ["create"]
  # Full access - restricted to SRE team
```

### Prevention
- RBAC: separate read-only vs admin access
- Namespace deletion requires approval from 2 people
- Alert on any namespace delete/update operation
- Regular backups of namespace configuration
- Archival enabled (workflows survive namespace deletion)
- Never give production admin access to developers

---

## Issue #94: Clock Skew Between Temporal Components [MEDIUM]

### Symptoms
- Timer tasks fire at wrong time
- Workflow timeout incorrect (too early/late)
- History events have timestamps out of order
- Lease renewal failures between services

### Root Cause
- NTP not configured on Kubernetes nodes
- Container clock drift
- VM suspend/resume causing time jump
- Different nodes in different time zones

### Impact
- **Business**: Timers inaccurate, SLA monitoring wrong
- **System**: Lease management failures, split-brain potential
- **Scale**: Small skew (< 1s) tolerable, large skew (> 5s) causes failures

### Detection
```promql
# Clock skew between components
abs(temporal_server_clock_skew_seconds) > 2

# NTP offset
node_ntp_offset_seconds > 1
```

### Resolution
```yaml
# 1. Kubernetes: chrony DaemonSet for NTP sync
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: chrony
spec:
  template:
    spec:
      hostPID: true
      containers:
      - name: chrony
        image: cturra/ntp
        securityContext:
          capabilities:
            add: [SYS_TIME]

# 2. Node configuration (all nodes)
# /etc/chrony/chrony.conf
server time.google.com iburst
server time.aws.com iburst
makestep 1 3  # Step clock if off by > 1s, first 3 adjustments
rtcsync

# 3. Kubernetes node requirement
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: ntp-synced
            operator: In
            values: ["true"]
```

### Prevention
- NTP/chrony on all Kubernetes nodes
- Monitor clock skew between nodes (alert > 1s)
- Use cloud provider's time service (AWS: time.aws.com, GCP: time.google.com)
- Regular verification of time sync status
- Never suspend/resume VMs running Temporal without time sync check

---

## Issue #95: Archival Pipeline Failure Causing Data Loss [MEDIUM]

### Symptoms
- Completed workflow histories not appearing in archival store
- Archival backlog growing
- S3 write failures in archival worker logs
- Compliance reporting missing historical workflows

### Root Cause
- Archival S3 bucket permissions incorrect
- Archival worker not scaling with completion rate
- S3 rate limiting (5500 PUT/sec per prefix)
- Serialization failures for specific workflow types

### Detection
```promql
# Archival backlog
temporal_archival_task_pending > 1000

# Archival failures
rate(temporal_archival_task_failures_total[5m]) > 0
```

### Resolution
```yaml
# 1. Fix S3 permissions
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
    "Resource": [
      "arn:aws:s3:::temporal-archival-prod",
      "arn:aws:s3:::temporal-archival-prod/*"
    ]
  }]
}

# 2. S3 prefix distribution to avoid rate limits
archival:
  history:
    URI: "s3://temporal-archival-prod/history"
    # Use namespace/date prefix for distribution
    # s3://temporal-archival-prod/history/{namespace}/{yyyy}/{mm}/{dd}/{workflow-id}

# 3. Scale archival workers
# dynamic_config.yaml
worker.ArchiverConcurrency:
  - value: 50  # Parallel archival operations
worker.ArchiverRateLimiter:
  - value: 1000  # Max 1000 archival/sec
```

### Prevention
- Test archival pipeline end-to-end regularly
- Monitor archival backlog as SLA metric
- S3 prefix distribution for high-volume namespaces
- Verify archived data can be read back (round-trip test)
- Separate bucket per namespace for isolation

---

## Issue #96: Worker Deployment Without Integration Testing [MEDIUM]

### Symptoms
- Workers deployed with bugs that only manifest at runtime
- Activity implementations that compile but fail at runtime
- Missing database migrations for new activities
- Dependencies not available in production environment

### Root Cause
- Unit tests pass but integration tests skipped
- No staging environment matching production
- Tests don't exercise Temporal SDK interactions
- Activities mock external services that behave differently in production

### Resolution
```go
// Integration test with real Temporal (using TestServer)
func TestOrderWorkflowIntegration(t *testing.T) {
    // Start test Temporal server
    ts := testsuite.NewTestServer()
    defer ts.Stop()
    
    c := ts.Client()
    
    // Register real implementations (not mocks)
    w := worker.New(c, "test-task-queue", worker.Options{})
    w.RegisterWorkflow(OrderWorkflow)
    w.RegisterActivity(&OrderActivities{
        db:     testDB,        // Test database
        client: testHTTPClient, // Test HTTP client
    })
    go w.Run(worker.InterruptCh())
    
    // Execute workflow end-to-end
    run, err := c.ExecuteWorkflow(context.Background(), client.StartWorkflowOptions{
        TaskQueue: "test-task-queue",
    }, OrderWorkflow, OrderInput{
        OrderID: "test-123",
        Items:   []Item{{ID: "item-1", Qty: 2}},
    })
    require.NoError(t, err)
    
    var result OrderResult
    err = run.Get(context.Background(), &result)
    require.NoError(t, err)
    assert.Equal(t, "COMPLETED", result.Status)
}

// Replay test for determinism
func TestOrderWorkflowReplay(t *testing.T) {
    replayer := worker.NewWorkflowReplayer()
    replayer.RegisterWorkflow(OrderWorkflow)
    
    // Replay against saved production histories
    files, _ := filepath.Glob("testdata/order_histories/*.json")
    for _, f := range files {
        err := replayer.ReplayWorkflowHistoryFromJSONFile(nil, f)
        require.NoError(t, err, "Replay failed for: %s", f)
    }
}
```

```yaml
# CI pipeline stages
stages:
  - lint          # workflowcheck, go vet
  - unit-test     # Fast, mocked
  - integration   # TestServer, real activities
  - replay-test   # Replay production histories
  - staging       # Deploy to staging, run E2E
  - production    # Canary then full rollout
```

### Prevention
- Integration tests with Temporal TestServer mandatory
- Replay tests with production histories in CI
- Staging environment running same version
- Canary deployment: 1 worker first, monitor errors
- Smoke test after each production deployment

---

## Issue #97: tctl/CLI Command Hanging in Production [MEDIUM]

### Symptoms
- `tctl workflow list` hangs indefinitely
- `tctl namespace describe` times out
- Admin operations unresponsive
- Cannot diagnose issues during incidents

### Root Cause
- tctl using wrong endpoint (pointing to unresponsive server)
- TLS misconfiguration on CLI
- Server overloaded, admin requests deprioritized
- gRPC connection timeout too high

### Resolution
```bash
# 1. Set explicit timeout
TEMPORAL_CLI_TIMEOUT=10s tctl workflow list --namespace prod --query "..." --limit 5

# 2. Check connectivity
grpcurl -plaintext temporal-frontend:7233 list
# or
grpcurl -cacert ca.crt -cert client.crt -key client.key temporal-frontend:7233 list

# 3. Use correct endpoint
export TEMPORAL_CLI_ADDRESS="temporal-frontend.temporal.svc.cluster.local:7233"
export TEMPORAL_CLI_NAMESPACE="production"
export TEMPORAL_CLI_TLS_CERT="/certs/client.crt"
export TEMPORAL_CLI_TLS_KEY="/certs/client.key"

# 4. Direct pod access (bypass LB if LB is the issue)
kubectl port-forward svc/temporal-frontend 7233:7233 -n temporal &
tctl --address localhost:7233 cluster health
```

### Prevention
- CLI configuration file with all environments
- Explicit timeout on all CLI operations
- Health check script for Temporal reachability
- kubectl port-forward as fallback procedure
- Document troubleshooting runbook

---

## Issue #98: Incorrect Retry Policy Leading to Exponential Resource Usage [MEDIUM]

### Symptoms
- Downstream services overwhelmed by retries
- Activity retries increasing exponentially
- Resources consumed by retrying activities
- Cost spike from cloud API calls (each retry = billable call)

### Root Cause
- `BackoffCoefficient` too high (default 2.0 with no max interval)
- `MaximumInterval` not set (backoff can reach hours)
- No `MaximumAttempts` (unlimited retries forever)
- Retrying non-retryable errors (invalid input retried 1000 times)

### Resolution
```go
// WRONG: Dangerous retry policy
policy := &temporal.RetryPolicy{
    InitialInterval: 1 * time.Second,
    BackoffCoefficient: 2.0,
    // No MaximumInterval -> backoff grows forever (1s, 2s, 4s, 8s... 1 hour... 1 day)
    // No MaximumAttempts -> retries forever
    // No NonRetryableErrorTypes -> retries EVERYTHING
}

// CORRECT: Production-safe retry policy
policy := &temporal.RetryPolicy{
    InitialInterval:    1 * time.Second,
    BackoffCoefficient: 2.0,
    MaximumInterval:    60 * time.Second,   // Cap backoff at 1 minute
    MaximumAttempts:    10,                   // Max 10 retries total
    NonRetryableErrorTypes: []string{
        "InvalidInputError",      // Don't retry bad input
        "NotFoundError",          // Don't retry missing resources
        "PermissionDeniedError",  // Don't retry auth failures
        "ValidationError",        // Don't retry validation failures
    },
}

// Use custom error types to control retry behavior
func MyActivity(ctx context.Context, input Input) error {
    result, err := externalAPI.Call(input)
    if err != nil {
        if isClientError(err) {  // 4xx
            // Don't retry client errors
            return temporal.NewNonRetryableApplicationError(
                "client error: "+err.Error(),
                "ClientError",
                err,
            )
        }
        // Retry server errors (5xx, timeout)
        return err
    }
    return nil
}
```

### Prevention
- **Always** set `MaximumAttempts` (never unlimited in production)
- **Always** set `MaximumInterval` (cap exponential backoff)
- Define `NonRetryableErrorTypes` for each activity
- Review retry policies during code review
- Monitor total retry count per activity type
- Cost alerting for billable API calls

---

## Issue #99: Observability Gap During Temporal Server Issues [MEDIUM]

### Symptoms
- Cannot determine if Temporal server is the bottleneck
- Workflow latency high but unclear which component is slow
- Missing correlation between server metrics and application metrics
- Incident diagnosis takes hours instead of minutes

### Root Cause
- Temporal server metrics not collected/dashboarded
- Application metrics not correlated with Temporal metrics
- Distributed tracing not configured across worker -> server -> database
- Log aggregation not including Temporal server logs

### Resolution
```yaml
# Complete observability stack for Temporal
# 1. Prometheus ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: temporal-server
spec:
  selector:
    matchLabels:
      app: temporal
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics

# 2. Key dashboards (Grafana)
# Dashboard 1: Cluster Health
#   - Frontend request rate & error rate
#   - History shard ownership
#   - Matching sync match rate
#   - Database latency
#
# Dashboard 2: Workflow Performance  
#   - Schedule-to-start latency per task queue
#   - Workflow execution latency per type
#   - Activity execution latency per type
#   - Failure rates
#
# Dashboard 3: Worker Fleet
#   - Worker count per task queue
#   - Slot utilization
#   - Memory/CPU per worker
#   - Connection health
#
# Dashboard 4: Business Metrics
#   - Workflows started/completed per type
#   - Active workflow count
#   - SLA compliance
```

```go
// OpenTelemetry integration for end-to-end tracing
import (
    "go.temporal.io/sdk/contrib/opentelemetry"
    "go.opentelemetry.io/otel"
)

func newTracingInterceptor() (client.Options, error) {
    // Create OpenTelemetry interceptor
    tracingInterceptor, err := opentelemetry.NewTracingInterceptor(opentelemetry.TracerOptions{})
    if err != nil {
        return client.Options{}, err
    }
    
    return client.Options{
        Interceptors: []interceptor.ClientInterceptor{tracingInterceptor},
    }, nil
}

// Worker-side tracing
workerOptions := worker.Options{
    Interceptors: []interceptor.WorkerInterceptor{
        opentelemetry.NewTracingInterceptor(opentelemetry.TracerOptions{}),
    },
}
```

### Prevention
- Prometheus scraping for all Temporal components (day one)
- Grafana dashboards for all 4 perspectives (cluster, workflow, worker, business)
- OpenTelemetry tracing across client -> server -> activity
- Structured logging with correlation IDs (workflow_id, run_id)
- Runbooks for each alert with diagnosis steps
- Monthly observability review (are alerts still relevant?)

---

## Issue #100: Cost Explosion from Uncontrolled Workflow Growth [MEDIUM]

### Symptoms
- Cloud infrastructure costs doubling monthly
- Database storage growing 100GB+ per day
- Worker fleet growing without bound
- Elasticsearch cluster maxed out

### Root Cause
- Workflows starting faster than completing (net growth)
- No retention policy (keeping everything forever)
- No cleanup of abandoned/stuck workflows
- History sizes growing unbounded (no ContinueAsNew)
- Large payloads in every activity (storage bloat)

### Impact
- **Business**: Infrastructure cost unsustainable
- **System**: Performance degrades as data grows
- **Scale**: Linear cost growth without linear business value

### Detection
```promql
# Net workflow growth (more starts than completions)
rate(temporal_workflow_started_total[24h]) - rate(temporal_workflow_completed_total[24h]) > 0

# Storage growth
deriv(pg_database_size_bytes[24h]) > 10000000000  # 10GB/day
```

### Resolution
```yaml
# 1. Retention policies
tctl namespace update --namespace production --retention 7d
tctl namespace update --namespace batch --retention 3d
tctl namespace update --namespace development --retention 1d

# 2. Archival (move to cheap storage)
archival:
  history:
    state: enabled
    URI: "s3://temporal-archive/history"  # S3 = $0.023/GB vs RDS = $0.115/GB

# 3. Cleanup stuck workflows
# Scheduled job to terminate workflows stuck > 7 days
temporal workflow terminate --query "ExecutionStatus='Running' AND StartTime < '7_days_ago'" \
  --reason "auto-cleanup: stuck workflow"
```

```go
// Cost tracking: tag workflows with cost attribution
func startWorkflowWithCostTracking(c client.Client, team string, input Input) {
    opts := client.StartWorkflowOptions{
        SearchAttributes: map[string]interface{}{
            "Team":        team,
            "CostCenter":  getCostCenter(team),
            "Environment": "production",
        },
    }
    c.ExecuteWorkflow(ctx, opts, MyWorkflow, input)
}

// Monthly cost report query
// SELECT Team, COUNT(*) as workflows, SUM(history_size) as total_storage
// FROM visibility WHERE StartTime > '2024-01-01'
// GROUP BY Team ORDER BY total_storage DESC
```

**Cost optimization strategies:**
```
1. Retention: 7d for prod, 3d for batch, 1d for dev (saves 80% storage)
2. Archival to S3: 5x cheaper than RDS for historical data
3. Payload optimization: references instead of data (10x smaller)
4. ContinueAsNew: keeps histories small (90% reduction in replay cost)
5. Local Activities: 50% fewer DB writes for short operations
6. Cleanup automation: terminate stuck workflows (prevents unbounded growth)
7. Right-sizing: auto-scale down during off-hours (40% compute savings)
```

### Prevention
- Retention policy from day one (not after 1TB of data)
- Cost dashboards per team/namespace
- Budget alerts at 80% of threshold
- Monthly cost review meeting
- Design review: estimate storage per workflow type before launching

---

## Summary: Operational & Deployment Issue Prevention Checklist

```
□ MaximumAttempts on ALL retry policies (never unlimited)
□ Per-workflow-type rate limits to prevent runaway workflows
□ Safe upgrade procedure documented and tested
□ Dynamic config without subPath mount (enables live reload)
□ Backward-compatible activity/workflow changes (aliases)
□ CLI environment separation (staging default, prod explicit)
□ RBAC on destructive operations (terminate, delete)
□ NTP sync on all nodes (alert on > 1s skew)
□ Archival enabled and tested (round-trip verification)
□ Integration + replay tests mandatory in CI
□ Prometheus + Grafana + tracing from day one
□ Retention policies per namespace
□ Cost tracking via search attributes
□ Cleanup automation for stuck workflows
□ Two-person rule for batch operations in production
```

---

## Grand Summary: All 100 Issues at a Glance

### By Severity
- **Critical (30)**: Issues that cause complete outage or data loss
- **High (43)**: Significant degradation requiring immediate attention
- **Medium (27)**: Partial impact with workarounds available

### Top Prevention Measures (covers 80% of issues):
1. **ContinueAsNew** at < 5000 events (prevents #16, #17, #19, #65, #80)
2. **Workflow versioning** for all code changes (prevents #22, #71-76)
3. **Idempotency keys** on all mutating activities (prevents #78)
4. **Separate task queues** by execution profile (prevents #7, #9, #60)
5. **KEDA autoscaling** on schedule-to-start (prevents #1, #56, #63)
6. **Replay tests in CI** (prevents #71-85 determinism issues)
7. **PodDisruptionBudget** on all services (prevents #57, #91)
8. **Database monitoring** (persistence latency, connection pool) (prevents #31-45)
9. **Namespace isolation** (separate batch from real-time) (prevents #62, #86)
10. **Retention + archival** from day one (prevents #34, #100)
