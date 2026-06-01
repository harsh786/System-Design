# Network & Connectivity Production Issues (#46 - #55)

## Issue #46: gRPC Deadline Exceeded Cascade [CRITICAL]

### Symptoms
- `DeadlineExceeded` errors across all Temporal operations
- Client-side timeouts propagating through service mesh
- Frontend service responding but slowly (> client deadline)
- Cascading failures: one slow service blocks everything

### Root Cause
gRPC deadline (timeout) set too tight on client side:
- Client deadline: 5s, actual round-trip: 7s under load
- Service mesh (Istio/Envoy) adding latency
- Intermediate proxy timeout < client deadline
- Server processing backlog causing response delay beyond deadline

### Impact
- **Business**: All workflow operations fail simultaneously
- **System**: Retry storms multiply load 3-5x, worsening the problem
- **Scale**: At 50K requests/sec, deadline cascade = 150K-250K retries/sec

### Detection
```promql
# gRPC deadline errors
rate(grpc_client_handled_total{grpc_code="DeadlineExceeded"}[1m]) > 100

# Latency approaching deadline
histogram_quantile(0.99, grpc_client_handling_seconds_bucket) / grpc_client_deadline_seconds > 0.8
```

### Resolution
```go
// WRONG: Tight deadline, no backoff
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
c.SignalWorkflow(ctx, wfID, "", "signal", data)

// CORRECT: Appropriate deadline with retry
clientOptions := client.Options{
    HostPort: "temporal-frontend:7233",
    ConnectionOptions: client.ConnectionOptions{
        DialOptions: []grpc.DialOption{
            grpc.WithDefaultCallOptions(
                grpc.MaxCallRecvMsgSize(64 * 1024 * 1024),  // 64MB max message
            ),
            grpc.WithDefaultServiceConfig(`{
                "methodConfig": [{
                    "name": [{"service": ""}],
                    "timeout": "30s",
                    "retryPolicy": {
                        "maxAttempts": 3,
                        "initialBackoff": "0.5s",
                        "maxBackoff": "5s",
                        "backoffMultiplier": 2.0,
                        "retryableStatusCodes": ["UNAVAILABLE", "RESOURCE_EXHAUSTED"]
                    }
                }]
            }`),
        },
    },
}

// Per-operation deadline strategy
func startWorkflowWithRetry(ctx context.Context, c client.Client, opts client.StartWorkflowOptions, wf interface{}, args ...interface{}) (client.WorkflowRun, error) {
    var run client.WorkflowRun
    var err error
    
    // Exponential backoff retry
    for attempt := 0; attempt < 3; attempt++ {
        opCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
        run, err = c.ExecuteWorkflow(opCtx, opts, wf, args...)
        cancel()
        
        if err == nil {
            return run, nil
        }
        
        if !isRetryable(err) {
            return nil, err
        }
        
        backoff := time.Duration(math.Pow(2, float64(attempt))) * 500 * time.Millisecond
        time.Sleep(backoff)
    }
    return nil, err
}
```

```yaml
# Service mesh configuration (Istio)
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: temporal-frontend
spec:
  host: temporal-frontend
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 1000
        connectTimeout: 10s
      http:
        h2UpgradePolicy: UPGRADE
        maxRequestsPerConnection: 0  # Unlimited for gRPC
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
```

### Prevention
- Client deadline = 3x p99 server response time
- gRPC retry policy with exponential backoff
- Service mesh timeouts > client deadlines
- Circuit breaker before retry (don't retry if server is down)
- Monitor deadline utilization (actual_latency / deadline_timeout)

---

## Issue #47: Worker Connection Reset During Long Poll [HIGH]

### Symptoms
- Workers periodically lose connection to Temporal frontend
- `connection reset by peer` in worker logs
- Workers reconnect but miss tasks during disconnect
- Correlates with load balancer idle timeout

### Root Cause
Workers use long-poll gRPC calls (60s+ duration):
- AWS ALB idle timeout: 60s (default) kills long-poll connections
- NAT gateway timeout: 350s (varies by cloud)
- Kubernetes service proxy timeout
- Intermediate proxy doesn't understand gRPC streaming

### Impact
- **Business**: Brief processing gaps during reconnection
- **System**: Worker appears disconnected, tasks accumulate
- **Scale**: Affects all workers simultaneously if LB timeout synchronized

### Detection
```promql
# Connection resets
rate(grpc_client_connection_errors_total{error="reset"}[5m]) > 1

# Poll gaps (no tasks processed for > 60s)
time() - temporal_worker_last_task_processed_timestamp > 60
```

### Resolution
```go
// gRPC keepalive to prevent connection idle timeout
clientOptions := client.Options{
    ConnectionOptions: client.ConnectionOptions{
        DialOptions: []grpc.DialOption{
            grpc.WithKeepaliveParams(keepalive.ClientParameters{
                Time:                20 * time.Second,  // Ping every 20s (< LB idle timeout)
                Timeout:             10 * time.Second,
                PermitWithoutStream: true,
            }),
        },
    },
}
```

```yaml
# AWS ALB: Increase idle timeout
resource "aws_lb" "temporal" {
  idle_timeout = 300  # 5 minutes (was 60s default)
}

# Or use NLB (Layer 4) which handles gRPC better
resource "aws_lb" "temporal" {
  load_balancer_type = "network"  # NLB, not ALB
}

# Kubernetes Ingress for gRPC
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/grpc-backend: "true"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
```

### Prevention
- gRPC keepalive interval < load balancer idle timeout
- Use NLB (Layer 4) instead of ALB (Layer 7) for gRPC
- Direct pod-to-pod communication where possible (skip LB)
- Monitor connection resets as reliability metric

---

## Issue #48: mTLS Certificate Expiry [CRITICAL]

### Symptoms
- All worker connections fail simultaneously
- `TLS handshake error: certificate has expired`
- New workers can't connect
- Existing workers disconnect within minutes of expiry

### Root Cause
- TLS certificates expired (forgotten renewal)
- cert-manager misconfigured (renewal failed silently)
- Root CA expired (all derived certs invalid)
- Clock skew making valid certs appear expired

### Impact
- **Business**: Complete outage - no workflows can execute
- **System**: Zero connectivity between all components
- **Scale**: Affects entire cluster simultaneously

### Detection
```promql
# Certificate expiry approaching
(certmanager_certificate_expiration_timestamp_seconds - time()) / 86400 < 7

# TLS errors
rate(grpc_server_tls_errors_total[1m]) > 0
```

### Resolution
```bash
# Emergency: Generate temporary certs
# 1. Generate new CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 365 -key ca.key -out ca.crt -subj "/CN=Temporal CA"

# 2. Generate server cert
openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr -subj "/CN=temporal-frontend"
openssl x509 -req -days 30 -in server.csr -CA ca.crt -CAkey ca.key -out server.crt

# 3. Generate client cert (for workers)
openssl genrsa -out client.key 4096
openssl req -new -key client.key -out client.csr -subj "/CN=temporal-worker"
openssl x509 -req -days 30 -in client.csr -CA ca.crt -CAkey ca.key -out client.crt

# 4. Update secrets and restart
kubectl create secret tls temporal-server-tls --cert=server.crt --key=server.key --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret tls temporal-client-tls --cert=client.crt --key=client.key --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment/temporal-frontend deployment/temporal-history
```

```yaml
# cert-manager automation (prevention)
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: temporal-server-cert
spec:
  secretName: temporal-server-tls
  duration: 8760h    # 1 year
  renewBefore: 720h  # Renew 30 days before expiry
  issuerRef:
    name: temporal-ca-issuer
    kind: ClusterIssuer
  dnsNames:
  - temporal-frontend
  - temporal-frontend.temporal.svc.cluster.local
  - "*.temporal.svc.cluster.local"
```

### Prevention
- cert-manager with auto-renewal
- Alert at 30 days before expiry (P3), 7 days (P2), 1 day (P1)
- Separate monitoring for CA expiry (longer lived, harder to renew)
- Certificate rotation testing in staging monthly
- NTP synchronization (clock skew can cause false expiry)

---

## Issue #49: DNS Resolution Failures [HIGH]

### Symptoms
- Workers intermittently fail to connect: `no such host`
- Connection errors correlate with DNS cache TTL expiry
- Partial failures (some workers connect, others don't)
- Issue resolves after pod restart (new DNS lookup)

### Root Cause
- Kubernetes DNS (CoreDNS) overwhelmed
- ndots:5 default causes 5 DNS lookups per resolution attempt
- DNS cache (NodeLocal DNSCache) not deployed
- CoreDNS pods OOM or evicted
- DNS record update during deployment (service IP change)

### Impact
- **Business**: Intermittent connectivity = intermittent workflow failures
- **System**: Hard to diagnose (looks like random failures)
- **Scale**: At 5000 workers, DNS queries = 5000 * 5 ndots * 2 (A+AAAA) = 50K queries/sec

### Detection
```promql
# DNS failures
rate(coredns_dns_requests_total{rcode="SERVFAIL"}[5m]) > 10

# DNS latency
coredns_dns_request_duration_seconds{quantile="0.99"} > 0.1
```

### Resolution
```yaml
# 1. Deploy NodeLocal DNSCache
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-local-dns
spec:
  template:
    spec:
      containers:
      - name: node-cache
        image: registry.k8s.io/dns/k8s-dns-node-cache:1.22.23

# 2. Reduce ndots for Temporal pods
spec:
  dnsConfig:
    options:
    - name: ndots
      value: "2"  # Default is 5, reduces unnecessary lookups
    - name: timeout
      value: "2"
    - name: attempts
      value: "3"

# 3. Use FQDN in worker config to avoid search path lookups
clientOptions := client.Options{
    HostPort: "temporal-frontend.temporal.svc.cluster.local:7233",  # FQDN
    // NOT: "temporal-frontend:7233"  (triggers ndots search)
}
```

### Prevention
- NodeLocal DNSCache on all nodes
- FQDN for all service references (append `.svc.cluster.local`)
- Reduce ndots to 2 for Temporal pods
- Scale CoreDNS based on cluster size
- Monitor DNS failure rate

---

## Issue #50: Network Partition Between History and Matching [HIGH]

### Symptoms
- Tasks created but not dispatched to workers
- Workflows stuck after activity scheduling
- History service healthy, Matching service healthy, but no work flowing
- Internal ring membership inconsistent

### Root Cause
Temporal services communicate via internal gRPC calls:
- History tells Matching to dispatch a task
- If network partitioned between them, tasks don't flow
- Membership ring (Ringpop/hashring) splits into two groups
- Each group thinks it owns all shards

### Impact
- **Business**: All workflows stuck, no progress
- **System**: Split-brain potential, duplicate task dispatching after recovery
- **Scale**: Entire cluster affected if core service partition

### Detection
```promql
# Membership ring size mismatch
temporal_membership_ring_size{service="history"} != temporal_membership_ring_size{service="matching"}

# Transfer task backlog growing (history can't reach matching)
rate(temporal_transfer_task_pending_count[5m]) > 100
```

### Resolution
```bash
# 1. Identify the partition
kubectl exec -it temporal-history-0 -- wget -qO- http://localhost:6935/members
kubectl exec -it temporal-matching-0 -- wget -qO- http://localhost:6939/members

# 2. Verify network connectivity
kubectl exec -it temporal-history-0 -- nc -zv temporal-matching 6939

# 3. If network issue, check NetworkPolicy
kubectl get networkpolicy -n temporal

# 4. Restart affected pods to rejoin ring
kubectl delete pod temporal-history-0  # Forces rejoin
kubectl delete pod temporal-matching-0

# 5. Verify ring convergence
kubectl exec -it temporal-history-0 -- wget -qO- http://localhost:6935/members | jq '.members | length'
```

```yaml
# Prevention: NetworkPolicy allowing inter-service communication
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-internal
  namespace: temporal
spec:
  podSelector:
    matchLabels:
      app: temporal
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: temporal
    ports:
    - port: 6933  # Frontend gRPC
    - port: 6934  # Frontend membership
    - port: 6935  # History membership
    - port: 6936  # History gRPC
    - port: 6937  # Matching gRPC
    - port: 6939  # Matching membership
```

### Prevention
- Pod anti-affinity (spread across AZs but not too far)
- Network Policy explicitly allowing inter-service traffic
- Membership ring health monitoring
- Regular network connectivity testing between services
- Redundant network paths between AZs

---

## Issue #51: Frontend Rate Limiting False Positives [HIGH]

### Symptoms
- `ResourceExhausted: namespace rate limit exceeded` despite low traffic
- Legitimate requests rejected
- Single burst triggers sustained rate limiting
- Workers idle due to frontend rejection

### Root Cause
- Namespace RPS limit set too low for burst patterns
- Rate limiter doesn't account for legitimate spikes
- Per-frontend-pod rate limiting (not global) causes uneven enforcement
- Token bucket empty after initial burst, slow refill

### Detection
```promql
# Rate limit rejections
rate(temporal_service_errors_total{error_code="ResourceExhausted"}[1m]) > 10

# Actual RPS vs limit
rate(temporal_service_requests_total{namespace="production"}[1m]) /
  temporal_namespace_rps_limit{namespace="production"} > 0.9
```

### Resolution
```yaml
# 1. Increase namespace rate limits
# dynamic_config.yaml
frontend.namespaceRPS:
  - value: 10000  # Increase from default
    constraints:
      namespace: "production"

frontend.namespaceBurstRatio:
  - value: 2.0  # Allow 2x burst (10000 sustained, 20000 burst)
    constraints:
      namespace: "production"

# 2. Global rate limit (not per-frontend-pod)
frontend.globalNamespaceRPS:
  - value: 50000  # Global across all frontend pods
    constraints:
      namespace: "production"

# 3. Per-instance vs global rate limiting
frontend.perInstanceNamespaceRPS:
  - value: 5000  # Per frontend pod
    constraints: {}
```

```go
// Client-side: Handle rate limiting gracefully
func startWithRateLimit(ctx context.Context, c client.Client, opts client.StartWorkflowOptions) error {
    for attempt := 0; attempt < 5; attempt++ {
        _, err := c.ExecuteWorkflow(ctx, opts, MyWorkflow, input)
        if err == nil {
            return nil
        }
        
        var resourceExhausted *serviceerror.ResourceExhausted
        if errors.As(err, &resourceExhausted) {
            // Backoff on rate limit
            backoff := time.Duration(math.Pow(2, float64(attempt))) * 100 * time.Millisecond
            time.Sleep(backoff)
            continue
        }
        return err  // Non-retryable error
    }
    return fmt.Errorf("rate limited after 5 attempts")
}
```

### Prevention
- Set rate limits at 2x expected peak (headroom for bursts)
- Use `globalNamespaceRPS` for multi-pod frontends
- Client-side rate limiting (don't hit server limits)
- Monitor rate limit rejections as capacity signal
- Separate namespaces for different SLA tiers

---

## Issue #52: Cross-Region Latency for Global Workflows [MEDIUM]

### Symptoms
- Workflow operations take 100-300ms (vs expected 10-50ms)
- Workers in Asia hitting Temporal cluster in US
- Performance degrades with geographic distance
- Inconsistent latency (varies by worker location)

### Root Cause
- Single Temporal cluster serving global workers
- Cross-region gRPC round-trips (30-150ms per hop)
- Each workflow task = multiple round-trips
- History reads require cross-region DB access

### Impact
- **Business**: Slow workflows in remote regions
- **System**: Overall throughput limited by latency
- **Scale**: Global deployment with 100ms base latency = 300ms per workflow step

### Detection
```promql
# Latency by worker region
temporal_activity_schedule_to_start_latency_seconds{worker_region="ap-southeast-1"} >
  temporal_activity_schedule_to_start_latency_seconds{worker_region="us-east-1"} * 3
```

### Resolution
```yaml
# Multi-cluster deployment with regional affinity
# Cluster 1: us-east-1 (primary for US workflows)
# Cluster 2: eu-west-1 (primary for EU workflows)
# Cluster 3: ap-southeast-1 (primary for APAC workflows)

# Cross-cluster replication for failover
clusterMetadata:
  enableGlobalNamespace: true
  currentClusterName: us-east-1
  clusterInformation:
    us-east-1:
      enabled: true
      initialFailoverVersion: 1
      rpcAddress: temporal-us.internal:7233
    eu-west-1:
      enabled: true
      initialFailoverVersion: 2
      rpcAddress: temporal-eu.internal:7233
    ap-southeast-1:
      enabled: true
      initialFailoverVersion: 3
      rpcAddress: temporal-apac.internal:7233
```

```go
// Route workflow to nearest cluster
func startWorkflowNearUser(ctx context.Context, userRegion string, input Input) error {
    cluster := selectNearestCluster(userRegion)
    c := getClientForCluster(cluster)
    
    _, err := c.ExecuteWorkflow(ctx, client.StartWorkflowOptions{
        TaskQueue: fmt.Sprintf("processing-%s-tq", cluster),
    }, ProcessingWorkflow, input)
    return err
}

func selectNearestCluster(region string) string {
    regionMap := map[string]string{
        "us-east-1": "us-cluster",
        "eu-west-1": "eu-cluster",
        "ap-southeast-1": "apac-cluster",
    }
    return regionMap[region]
}
```

### Prevention
- Multi-cluster deployment for global workloads
- Workers co-located with their Temporal cluster
- Region-aware task queue routing
- Accept higher latency for cross-region operations (consistency cost)
- Global namespaces only for workflows that NEED global access

---

## Issue #53: Service Mesh Sidecar Injection Breaking gRPC [MEDIUM]

### Symptoms
- Temporal services fail to communicate after Istio/Linkerd injection
- HTTP/2 connection issues between Temporal pods
- Worker connections timeout through sidecar
- mTLS double-encryption (Temporal TLS + mesh TLS) causing overhead

### Root Cause
- Service mesh sidecars intercept gRPC traffic
- Improper protocol detection (HTTP/1.1 vs HTTP/2)
- Sidecar resource limits too low for Temporal traffic
- mTLS termination at sidecar conflicts with Temporal's mTLS
- Long-poll gRPC streams terminated by sidecar timeout

### Detection
```promql
# Sidecar errors
rate(envoy_cluster_upstream_rq_timeout[5m]) > 0
rate(envoy_cluster_upstream_cx_connect_fail[5m]) > 0
```

### Resolution
```yaml
# Option 1: Disable sidecar for Temporal internal communication
apiVersion: apps/v1
kind: Deployment
metadata:
  name: temporal-history
spec:
  template:
    metadata:
      annotations:
        # Exclude Temporal internal ports from mesh
        traffic.sidecar.istio.io/excludeInboundPorts: "6935,6936"
        traffic.sidecar.istio.io/excludeOutboundPorts: "6935,6936,6937,6939"

# Option 2: Configure sidecar for gRPC
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: temporal-internal
spec:
  host: "*.temporal.svc.cluster.local"
  trafficPolicy:
    connectionPool:
      http:
        h2UpgradePolicy: UPGRADE  # Force HTTP/2 for gRPC
    tls:
      mode: DISABLE  # Temporal handles its own mTLS

# Option 3: Port-level protocol declaration
apiVersion: v1
kind: Service
metadata:
  name: temporal-frontend
spec:
  ports:
  - name: grpc-frontend  # "grpc-" prefix tells Istio it's gRPC
    port: 7233
    protocol: TCP
```

### Prevention
- Declare ports with `grpc-` prefix for service mesh auto-detection
- Disable mesh mTLS for Temporal if Temporal uses its own mTLS
- Configure adequate sidecar resources for Temporal traffic volume
- Test mesh compatibility in staging before production
- Consider excluding Temporal namespace from mesh entirely

---

## Issue #54: Worker Health Check False Negatives [MEDIUM]

### Symptoms
- Kubernetes kills healthy worker pods (liveness probe fail)
- Worker processing tasks but fails HTTP health check
- Pods cycle between Running and Terminating
- Activity execution interrupted by pod restart

### Root Cause
- Liveness probe checking wrong endpoint or port
- Worker busy processing long activity, can't respond to health check
- Probe timeout too short (default 1s)
- Goroutine in worker blocked, HTTP handler starved
- Liveness probe path not implemented in worker

### Detection
```promql
# Pod restart due to liveness failure
rate(kube_pod_container_status_restarts_total{container="temporal-worker"}[1h]) > 2
```

### Resolution
```go
// Proper health check implementation
func main() {
    // Start health check server on separate goroutine
    go func() {
        mux := http.NewServeMux()
        
        // Liveness: Is the process alive? (simple check)
        mux.HandleFunc("/health/live", func(w http.ResponseWriter, r *http.Request) {
            w.WriteHeader(http.StatusOK)
            w.Write([]byte("ok"))
        })
        
        // Readiness: Can the worker process tasks?
        mux.HandleFunc("/health/ready", func(w http.ResponseWriter, r *http.Request) {
            // Check if worker is connected to Temporal
            if !workerIsConnected() {
                w.WriteHeader(http.StatusServiceUnavailable)
                return
            }
            w.WriteHeader(http.StatusOK)
        })
        
        http.ListenAndServe(":8080", mux)
    }()
    
    // Start Temporal worker
    w := worker.New(c, "task-queue", workerOptions)
    w.Run(worker.InterruptCh())
}
```

```yaml
# Kubernetes probe configuration
spec:
  containers:
  - name: temporal-worker
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8080
      initialDelaySeconds: 30
      periodSeconds: 30
      timeoutSeconds: 5       # Allow 5s for response
      failureThreshold: 3     # Fail 3 times before kill
    readinessProbe:
      httpGet:
        path: /health/ready
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 10
      timeoutSeconds: 3
      failureThreshold: 2
    startupProbe:
      httpGet:
        path: /health/live
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 12    # 60s startup allowed
```

### Prevention
- Separate liveness (process alive) from readiness (can serve traffic)
- Health check on dedicated HTTP handler (not sharing with activity processing)
- Generous liveness timeout (5s) and failure threshold (3)
- Startup probe for slow-starting workers
- Never let activity execution block health check response

---

## Issue #55: Load Balancer Draining During Worker Shutdown [MEDIUM]

### Symptoms
- New tasks dispatched to shutting-down workers
- Activities accepted but then immediately cancelled
- Connection refused errors during rolling update
- Brief spike in activity failures during deployment

### Root Cause
- Load balancer health check interval > 0 (takes time to detect shutdown)
- PreStop hook not draining connections
- Worker accepts gRPC connection but about to die
- Kubernetes endpoint removal race condition

### Detection
```promql
# Activity cancellation spike during deployment
rate(temporal_activity_execution_failed_total{failure_reason="canceled"}[5m]) > 5
  AND kube_deployment_spec_replicas != kube_deployment_status_available_replicas
```

### Resolution
```yaml
# Proper shutdown sequence
spec:
  terminationGracePeriodSeconds: 120
  containers:
  - name: temporal-worker
    lifecycle:
      preStop:
        exec:
          command:
          - /bin/sh
          - -c
          - |
            # 1. Stop accepting new connections (mark unready)
            touch /tmp/shutdown
            # 2. Wait for LB to drain (health check interval + propagation)
            sleep 15
            # 3. Worker.Stop() handles graceful activity completion
            # (SIGTERM will be sent after preStop completes)
```

```go
// Worker monitors shutdown file
func main() {
    // Readiness probe checks this file
    mux.HandleFunc("/health/ready", func(w http.ResponseWriter, r *http.Request) {
        if _, err := os.Stat("/tmp/shutdown"); err == nil {
            w.WriteHeader(http.StatusServiceUnavailable)  // Tell LB to stop sending
            return
        }
        w.WriteHeader(http.StatusOK)
    })
}
```

### Prevention
- PreStop hook: sleep > health check interval
- Readiness probe separate from liveness
- `terminationGracePeriodSeconds` > preStop sleep + max activity duration
- PodDisruptionBudget to limit concurrent terminations
- Monitor activity cancellations during deployments

---

## Summary: Network & Connectivity Issue Prevention Checklist

```
□ gRPC client deadline = 3x p99 server latency
□ Exponential backoff retry on DeadlineExceeded and Unavailable
□ gRPC keepalive interval < load balancer idle timeout
□ NLB (Layer 4) preferred over ALB for gRPC
□ cert-manager with auto-renewal and 30-day expiry alert
□ NodeLocal DNSCache + FQDN for service references
□ NetworkPolicy explicitly allowing Temporal inter-service traffic
□ Namespace rate limits at 2x expected peak
□ Multi-cluster for global deployments (< 100ms latency)
□ Service mesh excluded or properly configured for gRPC
□ Health check: separate liveness/readiness, generous timeouts
□ PreStop hook: sleep > health check interval for clean drain
□ PodDisruptionBudget on all Temporal deployments
□ Monitor: gRPC errors, connection resets, DNS failures, TLS expiry
□ Regular chaos testing: network partition, cert rotation, LB failover
```
