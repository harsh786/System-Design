# Service Mesh Design (Istio/Envoy)

## 1. Functional Requirements

### Core Features
- **Sidecar Proxy Injection**: Automatic injection of Envoy proxy alongside every workload
- **mTLS Certificate Management**: Auto-issuance, rotation without connection drop
- **Traffic Routing Rules**: Canary, weighted, mirror, fault injection, header-based
- **Retry & Timeout Policies**: Per-route, per-service configurable with exponential backoff
- **Circuit Breaker**: Per service-pair with configurable thresholds (consecutive errors, ejection time)
- **Rate Limiting**: Local and global rate limiting (token bucket, sliding window)
- **Observability Tap**: L7 metrics, distributed traces, structured access logs

### User Stories
1. Platform engineer defines traffic policy → mesh enforces across all services
2. Service A calls Service B → sidecar handles mTLS, retry, timeout, circuit breaking
3. Deploy canary → route 5% traffic, monitor error rate, auto-promote or rollback
4. New service deploys → sidecar auto-injected, certs issued, joins mesh immediately

---

## 2. Non-Functional Requirements

| Metric | Target |
|--------|--------|
| Availability | 99.999% (data plane), 99.99% (control plane) |
| Added Latency | <1ms p99 per hop (data plane) |
| Scale | 10,000+ services, 100K+ proxy instances |
| Throughput | 1M+ RPS through mesh aggregate |
| Config Propagation | <5s from control plane to all proxies |
| Cert Rotation | Zero-downtime, <24h lifetime certs |
| Memory per sidecar | <50MB base, <150MB under load |

---

## 3. Capacity Estimation

### Traffic Model
```
Services: 10,000
Pods per service (avg): 10 → 100,000 sidecars
RPS per pod (avg): 10 → 1M RPS aggregate
Connections per pod: 50 avg → 5M concurrent connections

Certificate issuance: 100K certs / 24h rotation = ~1.2 certs/sec steady state
                      Burst on deploy: 1000 certs/sec
Config pushes: 100 config changes/min → 100K proxy updates/min (fanout)
```

### Resource Estimation
```
Sidecar Memory: 100K pods × 80MB avg = 8TB total mesh overhead
Sidecar CPU: 100K pods × 0.1 core avg = 10,000 cores overhead
Control Plane: 5 replicas × 16 cores × 64GB = 80 cores, 320GB RAM
Telemetry: 1M RPS × 1KB metric/trace per request = 1GB/s telemetry data
Certificate Storage: 100K certs × 4KB = 400MB (in-memory CA)
```

### xDS Config Size
```
Per-proxy config (CDS+EDS+RDS+LDS):
  - 10K services × 200B per cluster = 2MB CDS
  - 10K services × 10 endpoints × 100B = 10MB EDS
  - Routes: 50K rules × 500B = 25MB RDS
  - Listeners: 100 × 2KB = 200KB LDS
Total per proxy: ~37MB (with delta xDS, incremental: <100KB per push)
```

---

## 4. Data Modeling

### Service Registry Schema
```protobuf
message Service {
  string name = 1;
  string namespace = 2;
  repeated Port ports = 3;
  map<string, string> labels = 4;
  repeated Endpoint endpoints = 5;
  ServicePolicy policy = 6;
}

message Endpoint {
  string address = 1;
  uint32 port = 2;
  HealthStatus health = 3;
  map<string, string> labels = 4;  // zone, region, version
  uint32 weight = 5;
  string locality = 6;  // region/zone/subzone
}

message Port {
  string name = 1;
  uint32 number = 2;
  Protocol protocol = 3;  // HTTP, GRPC, TCP, HTTPS
}
```

### Traffic Policy Schema
```protobuf
message VirtualService {
  string name = 1;
  repeated string hosts = 2;
  repeated HTTPRoute http = 3;
  repeated TCPRoute tcp = 4;
}

message HTTPRoute {
  repeated HTTPMatchRequest match = 1;
  repeated HTTPRouteDestination route = 2;
  HTTPRetry retries = 3;
  google.protobuf.Duration timeout = 4;
  HTTPFaultInjection fault = 5;
  Mirror mirror = 6;
  CorsPolicy cors = 7;
}

message HTTPRouteDestination {
  Destination destination = 1;
  uint32 weight = 2;  // 0-100 for canary
  Headers headers = 3;
}

message DestinationRule {
  string host = 1;
  TrafficPolicy traffic_policy = 2;
  repeated Subset subsets = 3;
}

message TrafficPolicy {
  ConnectionPool connection_pool = 1;
  OutlierDetection outlier_detection = 2;
  LoadBalancerSettings load_balancer = 3;
  TLSSettings tls = 4;
}

message ConnectionPool {
  TCPSettings tcp = 1;   // max_connections, connect_timeout
  HTTPSettings http = 2; // h2_upgrade, max_requests_per_connection
}

message OutlierDetection {
  uint32 consecutive_errors = 1;       // default: 5
  google.protobuf.Duration interval = 2;  // default: 10s
  google.protobuf.Duration base_ejection_time = 3;  // default: 30s
  uint32 max_ejection_percent = 4;     // default: 10%
  uint32 min_health_percent = 5;       // default: 0 (disabled)
}
```

### Certificate Schema
```protobuf
message WorkloadCertificate {
  string spiffe_id = 1;          // spiffe://cluster.local/ns/default/sa/frontend
  bytes cert_chain = 2;          // leaf + intermediate
  bytes private_key = 3;
  google.protobuf.Timestamp not_before = 4;
  google.protobuf.Timestamp not_after = 5;
  string trust_domain = 6;
  repeated string dns_sans = 7;
}

message CertificateSigningRequest {
  string service_account = 1;
  string namespace = 2;
  bytes csr = 3;
  string node_id = 4;
  WorkloadAttestation attestation = 5;
}

message WorkloadAttestation {
  string pod_name = 1;
  string pod_uid = 2;
  string node_name = 3;
  string service_account_token = 4;  // JWT for validation
}
```

### xDS Protocol Messages
```protobuf
// Discovery Request (proxy → control plane)
message DiscoveryRequest {
  string version_info = 1;
  Node node = 2;
  repeated string resource_names = 3;
  string type_url = 4;
  string response_nonce = 5;
  google.rpc.Status error_detail = 6;
}

// Discovery Response (control plane → proxy)
message DiscoveryResponse {
  string version_info = 1;
  repeated google.protobuf.Any resources = 2;
  string type_url = 3;
  string nonce = 4;
}

// Delta variant for incremental updates
message DeltaDiscoveryRequest {
  Node node = 1;
  string type_url = 2;
  repeated string resource_names_subscribe = 3;
  repeated string resource_names_unsubscribe = 4;
  map<string, string> initial_resource_versions = 5;
  string response_nonce = 6;
  google.rpc.Status error_detail = 7;
}
```

---

## 5. High-Level Design (HLD)

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONTROL PLANE (Istiod)                          │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │  Pilot   │  │  Citadel │  │  Galley  │  │  xDS     │  │ Webhook ││
│  │(Traffic) │  │  (CA)    │  │(Config)  │  │  Server  │  │(Inject) ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘│
│       │              │              │              │              │     │
│  ┌────┴──────────────┴──────────────┴──────────────┴──────────────┘    │
│  │              Unified Config Store (etcd / K8s API)                   │
│  └─────────────────────────────────────────────────────────────────┘   │
└───────────────┬───────────────────────────────────────────┬────────────┘
                │ xDS (gRPC streams)                        │ CSR/Cert
                │                                           │
┌───────────────▼───────────────────────────────────────────▼────────────┐
│                           DATA PLANE                                    │
│                                                                         │
│  ┌─────────────────────┐         ┌─────────────────────┐              │
│  │  Pod A              │         │  Pod B              │              │
│  │ ┌───────┐ ┌───────┐ │  mTLS  │ ┌───────┐ ┌───────┐│              │
│  │ │App    │←│Envoy  │←┼────────┼→│Envoy  │→│App    ││              │
│  │ │Container│Sidecar│ │         │ │Sidecar│ │Container│              │
│  │ └───────┘ └───┬───┘ │         │ └───┬───┘ └───────┘│              │
│  └───────────────┼─────┘         └─────┼───────────────┘              │
│                  │                      │                              │
│  ┌───────────────▼──────────────────────▼───────────────────┐         │
│  │            Telemetry Pipeline                             │         │
│  │  Metrics → Prometheus    Traces → Jaeger/Zipkin          │         │
│  │  Logs → Fluentd → Elasticsearch                          │         │
│  └──────────────────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────────────────┘

                    INGRESS/EGRESS GATEWAYS
┌──────────────┐                           ┌──────────────┐
│   Ingress    │  (Envoy-based)            │   Egress     │
│   Gateway    │←── External Traffic       │   Gateway    │──→ External
└──────────────┘                           └──────────────┘
```

### Envoy Proxy Internal Architecture
```
                    Incoming Connection
                           │
                           ▼
                ┌─────────────────────┐
                │     LISTENER        │
                │  (port binding)     │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │   FILTER CHAIN      │
                │  (TLS Inspector →   │
                │   HTTP Conn Mgr →   │
                │   Router)           │
                └──────────┬──────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │HTTP Filters │  │HTTP Filters │  │HTTP Filters │
  │- RBAC      │  │- Rate Limit │  │- Router     │
  │- JWT Auth  │  │- Fault Inj  │  │             │
  │- Lua       │  │- CORS       │  │             │
  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │      CLUSTER        │
                │  (upstream group)   │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │   LOAD BALANCER     │
                │  (Round Robin /     │
                │   Least Req /       │
                │   Ring Hash /       │
                │   Maglev)           │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │    ENDPOINT          │
                │  (connection pool,  │
                │   health check,     │
                │   circuit breaker)  │
                └─────────────────────┘
```

---

## 6. Low-Level Design (LLD) - APIs

### xDS gRPC API
```protobuf
service AggregatedDiscoveryService {
  rpc StreamAggregatedResources(stream DiscoveryRequest) 
    returns (stream DiscoveryResponse);
  rpc DeltaAggregatedResources(stream DeltaDiscoveryRequest)
    returns (stream DeltaDiscoveryResponse);
}

// Type URLs for each xDS variant
// LDS: type.googleapis.com/envoy.config.listener.v3.Listener
// RDS: type.googleapis.com/envoy.config.route.v3.RouteConfiguration
// CDS: type.googleapis.com/envoy.config.cluster.v3.Cluster
// EDS: type.googleapis.com/envoy.config.endpoint.v3.ClusterLoadAssignment
// SDS: type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.Secret
```

### Certificate Signing API (Citadel)
```protobuf
service IstioCertificateService {
  rpc CreateCertificate(IstioCertificateRequest) 
    returns (IstioCertificateResponse);
}

message IstioCertificateRequest {
  bytes csr = 1;
  int64 validity_duration = 2;  // seconds
  map<string, string> metadata = 3;
}

message IstioCertificateResponse {
  repeated string cert_chain = 1;  // [leaf, intermediate, root]
}
```

### Traffic Management API (Kubernetes CRDs)
```yaml
# VirtualService - Route traffic
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews-route
spec:
  hosts:
  - reviews
  http:
  - match:
    - headers:
        end-user:
          exact: jason
    route:
    - destination:
        host: reviews
        subset: v2
      weight: 100
  - route:
    - destination:
        host: reviews
        subset: v1
      weight: 90
    - destination:
        host: reviews
        subset: v2
      weight: 10
    retries:
      attempts: 3
      perTryTimeout: 2s
      retryOn: "5xx,reset,connect-failure"
    timeout: 10s
    fault:
      delay:
        percentage:
          value: 0.1
        fixedDelay: 5s
      abort:
        percentage:
          value: 0.01
        httpStatus: 503
    mirror:
      host: reviews
      subset: v3
    mirrorPercentage:
      value: 5.0
```

```yaml
# DestinationRule - Circuit breaker + connection pool
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews-destination
spec:
  host: reviews
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
        connectTimeout: 30ms
      http:
        h2UpgradePolicy: UPGRADE
        maxRequestsPerConnection: 1000
        maxRetries: 3
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 10s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
      minHealthPercent: 30
    loadBalancer:
      simple: LEAST_REQUEST
      localityLbSetting:
        enabled: true
        failover:
        - from: us-east
          to: us-west
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
```

### Rate Limiting API
```yaml
apiVersion: networking.istio.io/v1alpha1
kind: EnvoyFilter
metadata:
  name: global-ratelimit
spec:
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_INBOUND
      listener:
        filterChain:
          filter:
            name: envoy.filters.network.http_connection_manager
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.ratelimit
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.http.ratelimit.v3.RateLimit
          domain: mesh-ratelimit
          failure_mode_deny: false
          rate_limit_service:
            grpc_service:
              envoy_grpc:
                cluster_name: rate_limit_cluster
            transport_api_version: V3
```

---

## 7. Deep Dives

### Deep Dive 1: Data Plane Architecture (Envoy Proxy)

#### Listener → Filter Chain → Cluster Pipeline
```
Connection arrives at port 8080
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ Listener Filter Chain Matching                          │
│                                                         │
│  1. TLS Inspector (SNI detection without terminating)   │
│  2. HTTP Inspector (detect HTTP vs TCP)                 │
│  3. Original Destination (capture original dst IP)      │
│                                                         │
│  Match criteria: destination port, SNI, ALPN,           │
│                  source IP, transport protocol          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ Network Filter Chain                                    │
│                                                         │
│  1. Envoy RBAC Filter (AuthorizationPolicy)             │
│  2. HTTP Connection Manager                             │
│     ├── Codec (HTTP/1.1 or HTTP/2)                     │
│     ├── HTTP Filter Chain:                              │
│     │   ├── envoy.filters.http.jwt_authn              │
│     │   ├── envoy.filters.http.rbac                   │
│     │   ├── envoy.filters.http.fault                  │
│     │   ├── envoy.filters.http.cors                   │
│     │   ├── envoy.filters.http.ratelimit              │
│     │   ├── istio.stats (Wasm/native)                 │
│     │   └── envoy.filters.http.router (terminal)      │
│     └── Route Configuration (from RDS)                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ Route Matching (O(n) with prefix tree optimization)     │
│                                                         │
│  Match: path prefix/exact/regex + headers + query       │
│  Action: route to cluster, redirect, direct_response    │
│                                                         │
│  Weighted routing:                                      │
│    cluster:reviews-v1 weight=90                         │
│    cluster:reviews-v2 weight=10                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ Cluster Manager                                         │
│                                                         │
│  Connection Pool (per upstream host):                   │
│    HTTP/2: single connection, multiplexed streams       │
│    HTTP/1.1: pool of connections (max configurable)     │
│                                                         │
│  Health Checking:                                       │
│    Active: periodic HTTP/gRPC/TCP probes               │
│    Passive: outlier detection (circuit breaker)         │
│                                                         │
│  Load Balancing:                                        │
│    ROUND_ROBIN, LEAST_REQUEST, RING_HASH, MAGLEV,      │
│    RANDOM, CLUSTER_PROVIDED                            │
│                                                         │
│  Locality-aware: prefer same-zone → same-region → any  │
└─────────────────────────────────────────────────────────┘
```

#### Hot Restart Mechanism
```
┌──────────────────────────────────────────────────────┐
│                HOT RESTART SEQUENCE                   │
│                                                      │
│  T=0: New Envoy process starts                       │
│       - Connects to parent via Unix domain socket    │
│       - Requests listener sockets via SCM_RIGHTS     │
│                                                      │
│  T=1: Socket transfer                                │
│       - Parent transfers all listener FDs            │
│       - New process begins accepting connections     │
│       - Both processes serve traffic simultaneously  │
│                                                      │
│  T=2: Drain period starts (configurable, default 45s)│
│       - Parent stops accepting NEW connections       │
│       - Parent continues serving EXISTING connections│
│       - New process handles all new connections      │
│                                                      │
│  T=3: Drain complete                                 │
│       - Parent closes remaining connections          │
│       - Parent process exits                         │
│       - Shared memory stats transferred              │
│                                                      │
│  Result: ZERO dropped connections                    │
└──────────────────────────────────────────────────────┘
```

#### Connection Pooling & HTTP/2 Multiplexing
```cpp
// Envoy connection pool architecture (simplified)
class Http2ConnPool {
  // Single TCP connection with multiplexed streams
  ActiveClient* client_;
  uint32_t max_concurrent_streams_ = 100;
  
  // When stream limit reached → open new connection
  // Connection lifecycle:
  //   1. TCP connect + TLS handshake (amortized over streams)
  //   2. HTTP/2 SETTINGS exchange
  //   3. Multiplex up to max_concurrent_streams
  //   4. GOAWAY when max_requests_per_connection reached
  //   5. Drain existing streams, close connection
};

// Per-host circuit breaker state machine
enum CircuitBreakerState {
  CLOSED,    // normal operation
  HALF_OPEN, // allow one probe request
  OPEN       // reject all requests immediately
};

// Thresholds checked:
// - max_connections (TCP level)
// - max_pending_requests (queued)
// - max_requests (active, HTTP/2)
// - max_retries (concurrent retries)
```

### Deep Dive 2: Control Plane (xDS Protocol)

#### xDS Protocol Flow
```
┌─────────────────────────────────────────────────────────┐
│              xDS PROTOCOL STATE MACHINE                  │
│                                                         │
│  Proxy starts → sends DiscoveryRequest:                 │
│    version_info: ""  (initial, want everything)         │
│    resource_names: [] (wildcard for LDS/CDS)            │
│                                                         │
│  Control Plane responds → DiscoveryResponse:            │
│    version_info: "v1"                                   │
│    resources: [all matching resources]                   │
│    nonce: "abc123"                                      │
│                                                         │
│  Proxy ACKs → DiscoveryRequest:                         │
│    version_info: "v1"  (accepted version)               │
│    response_nonce: "abc123"                             │
│                                                         │
│  Proxy NACKs → DiscoveryRequest:                        │
│    version_info: "v0"  (keep old version)               │
│    response_nonce: "abc123"                             │
│    error_detail: {code: INVALID, message: "bad route"}  │
│                                                         │
│  Config update → new DiscoveryResponse pushed:          │
│    version_info: "v2"                                   │
│    nonce: "def456"                                      │
└─────────────────────────────────────────────────────────┘
```

#### xDS Ordering & Dependencies
```
    LDS (Listeners)
     │
     ▼
    RDS (Routes)     ← referenced by LDS
     │
     ▼
    CDS (Clusters)   ← referenced by RDS
     │
     ▼
    EDS (Endpoints)  ← referenced by CDS
     │
     ▼
    SDS (Secrets)    ← referenced by LDS/CDS for TLS

Push order (to avoid dangling references):
  1. CDS/EDS first (ensure upstream clusters exist)
  2. Then LDS/RDS (routes can now reference valid clusters)
  
With ADS (Aggregated Discovery Service):
  - Single gRPC stream for all types
  - Server controls ordering
  - Prevents inconsistent intermediate states
```

#### Config Push Rate Limiting
```python
class ConfigPushThrottler:
    def __init__(self):
        self.push_interval = 100  # ms, minimum between pushes
        self.max_concurrent_pushes = 100
        self.debounce_after = 100  # ms, wait for batch
        self.debounce_max = 500    # ms, max wait time
        
    def on_config_change(self, event):
        """Debounce rapid config changes."""
        self.pending_events.append(event)
        
        if not self.timer_running:
            self.timer_running = True
            schedule(self.push_interval, self.process_batch)
    
    def process_batch(self):
        """Merge all pending events and push."""
        merged = merge_config_events(self.pending_events)
        self.pending_events.clear()
        
        # Determine affected proxies
        affected_proxies = compute_affected(merged)
        
        # Push with concurrency limit
        for batch in chunk(affected_proxies, self.max_concurrent_pushes):
            parallel_push(batch, merged.config)
            
    def validate_before_push(self, config):
        """Validate config won't break proxies."""
        errors = []
        for listener in config.listeners:
            if not validate_filter_chain(listener):
                errors.append(f"Invalid filter chain: {listener.name}")
        for route in config.routes:
            if not validate_cluster_refs(route, config.clusters):
                errors.append(f"Dangling cluster ref in: {route.name}")
        return errors
```

#### Eventual Consistency Handling
```
Scenario: Config update propagating across 100K proxies

T=0s:   Config change committed
T=0.1s: Pilot computes affected proxies (10K of 100K)
T=0.2s: Start pushing to first batch (100 concurrent)
T=2s:   50% of proxies updated
T=5s:   99% of proxies updated  
T=10s:  100% (including slow/reconnecting proxies)

During propagation window:
  - Proxy A has new config, Proxy B has old
  - Traffic A→B works (B still serves, just old routing)
  - New service only routable from updated proxies
  
  Mitigation: warmup period before routing traffic to new versions
```

### Deep Dive 3: mTLS and Identity (SPIFFE)

#### SPIFFE Identity Framework
```
SPIFFE ID format: spiffe://<trust-domain>/<workload-path>

Examples:
  spiffe://cluster.local/ns/production/sa/payment-service
  spiffe://cluster.local/ns/staging/sa/frontend

Trust Domain: cluster.local (one per mesh, can federate)

Identity Document: X.509-SVID
  - X.509 certificate with SPIFFE ID in SAN (URI)
  - Short-lived (default: 24h in Istio)
  - Automatically rotated before expiry

Trust Bundle: Set of root CAs for a trust domain
  - Used to validate peer certificates
  - Federated trust bundles for cross-mesh communication
```

#### Certificate Issuance Flow
```
┌────────────┐      ┌──────────────┐      ┌──────────────┐
│  Envoy     │      │  Pilot-Agent │      │   Istiod     │
│  (Proxy)   │      │  (Node Agent)│      │   (CA)       │
└─────┬──────┘      └──────┬───────┘      └──────┬───────┘
      │                     │                     │
      │ 1. Need cert for    │                     │
      │    SPIFFE ID        │                     │
      │────────────────────>│                     │
      │                     │                     │
      │                     │ 2. Generate key pair│
      │                     │    Create CSR       │
      │                     │                     │
      │                     │ 3. CSR + JWT token  │
      │                     │    (ServiceAccount) │
      │                     │────────────────────>│
      │                     │                     │
      │                     │              4. Validate JWT
      │                     │                 against K8s API
      │                     │              5. Verify pod identity
      │                     │                 (UID, SA, NS)
      │                     │              6. Sign cert with
      │                     │                 intermediate CA
      │                     │                     │
      │                     │ 7. Signed cert chain│
      │                     │<────────────────────│
      │                     │                     │
      │ 8. Cert + Key via   │                     │
      │    SDS (Secret      │                     │
      │    Discovery)       │                     │
      │<────────────────────│                     │
      │                     │                     │
      │ 9. Use cert for mTLS│                     │
      │                     │                     │
```

#### Certificate Rotation Without Connection Drop
```
Algorithm: Graceful cert rotation

1. Monitor cert expiry (rotate at 80% of lifetime)
   - Cert lifetime: 24h → rotate at ~19h

2. Request new certificate (same flow as initial issuance)

3. Update SDS secret (new cert pushed to Envoy)
   - Envoy receives new cert via SDS stream
   - Does NOT tear down existing connections

4. New connections use new cert immediately
   - TLS handshake uses latest cert from SDS

5. Existing connections continue with old cert
   - HTTP/2 connections may live for hours
   - Old cert remains valid until expiry

6. Both old and new cert are valid simultaneously
   - Peers accept both (same CA chain)
   - No window of invalid certificate

Corner case: CA key rotation
   - New root CA added to trust bundle FIRST
   - Wait for propagation (all proxies trust new CA)
   - Then start issuing certs from new CA
   - Remove old CA from trust bundle after all old certs expire
```

#### Workload Identity Attestation
```yaml
# Multi-signal attestation for workload identity
attestation_signals:
  kubernetes:
    - service_account_token:  # JWT with pod claims
        audience: "istio-ca"
        expiry: 3600s
    - pod_metadata:
        uid: "pod-uid-12345"
        namespace: "production"
        service_account: "payment-service"
    - node_attestation:
        node_name: "worker-node-7"
        # Validates pod is actually running on claimed node
        
  platform_specific:
    - aws_instance_identity_document  # For VMs on AWS
    - gcp_metadata_token              # For VMs on GCP
    
  security_policies:
    - require_bound_token: true       # No legacy tokens
    - token_audience_check: "istio-ca"
    - max_token_age: 3600s
    - require_same_node: true         # Token from same node
```

---

## 8. Component Optimization

### Envoy Performance Tuning
```yaml
# Production Envoy bootstrap config
admin:
  access_log_path: /dev/null
  address:
    socket_address: { address: 127.0.0.1, port_value: 15000 }

node:
  id: sidecar~10.0.0.5~payment-v1-abc~production.svc.cluster.local
  cluster: payment.production

static_resources:
  clusters:
  - name: xds_cluster
    type: STRICT_DNS
    http2_protocol_options: {}
    load_assignment:
      cluster_name: xds_cluster
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address: { address: istiod.istio-system, port_value: 15012 }
    transport_socket:
      name: envoy.transport_sockets.tls
      typed_config:
        "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext
        sni: istiod.istio-system.svc

# Performance tuning
overload_manager:
  refresh_interval: 0.25s
  resource_monitors:
  - name: envoy.resource_monitors.fixed_heap
    typed_config:
      "@type": type.googleapis.com/envoy.extensions.resource_monitors.fixed_heap.v3.FixedHeapConfig
      max_heap_size_bytes: 134217728  # 128MB
  actions:
  - name: envoy.overload_actions.shrink_heap
    triggers:
    - name: envoy.resource_monitors.fixed_heap
      threshold: { value: 0.9 }
  - name: envoy.overload_actions.stop_accepting_connections
    triggers:
    - name: envoy.resource_monitors.fixed_heap
      threshold: { value: 0.95 }
```

### Latency Optimization
```
Techniques to achieve <1ms added latency:

1. Connection pooling + HTTP/2 multiplexing
   - Amortize TLS handshake across thousands of requests
   - Zero connection setup time for subsequent requests

2. Filter chain optimization
   - Order filters by likelihood of short-circuit
   - RBAC deny before expensive operations
   - Use native C++ filters over Wasm where possible
   
3. Memory allocation
   - Arena allocation for request lifetime objects
   - Pool common buffer sizes (4KB, 16KB, 64KB)
   - Zero-copy forwarding where possible

4. Threading model
   - Worker threads pinned to cores (no context switching)
   - Thread-local storage for caches
   - Lock-free stats collection

5. Config optimization
   - Minimize route table size (merge overlapping routes)
   - Use EDS with locality hints (avoid cross-zone)
   - Pre-warm connections on config update

Measured breakdown per request (p50):
  TLS termination (existing conn): 0μs (reused)
  Filter chain traversal: 50μs
  Route matching: 10μs
  Load balancing: 5μs
  Connection pool checkout: 5μs
  Total added: ~70μs p50, ~300μs p99, <1ms p99.9
```

### Memory Optimization for Large Meshes
```
Problem: 10K services × 10 endpoints = 100K entries per proxy

Solution: Sidecar scoping
  - Only push configs relevant to this service's dependencies
  - Reduces config from 37MB to ~500KB per proxy
  
Implementation:
  apiVersion: networking.istio.io/v1beta1
  kind: Sidecar
  metadata:
    name: payment-sidecar
    namespace: production
  spec:
    egress:
    - hosts:
      - "./orders.production.svc.cluster.local"
      - "./inventory.production.svc.cluster.local"
      - "istio-system/*"
      
Result:
  Before scoping: 80MB per proxy, 8TB total
  After scoping:  15MB per proxy, 1.5TB total (81% reduction)
```

---

## 9. Observability

### Metrics (Prometheus)
```
# Standard Istio metrics (collected by Envoy + istio stats filter)

# Request metrics
istio_requests_total{
  reporter="source|destination",
  source_workload, destination_workload,
  source_namespace, destination_namespace,
  request_protocol="http|grpc|tcp",
  response_code, response_flags,
  connection_security_policy="mutual_tls|none"
}

istio_request_duration_milliseconds{...}  # histogram
istio_request_bytes{...}                  # histogram
istio_response_bytes{...}                 # histogram

# TCP metrics
istio_tcp_connections_opened_total{...}
istio_tcp_connections_closed_total{...}
istio_tcp_sent_bytes_total{...}
istio_tcp_received_bytes_total{...}

# Control plane metrics
pilot_xds_pushes{type="cds|eds|lds|rds"}
pilot_proxy_convergence_time{...}  # time from config change to proxy update
pilot_conflict_inbound_listener{...}
pilot_xds_push_errors{...}
citadel_server_csr_count{...}
citadel_server_success_cert_issuance_count{...}

# Alerting rules
groups:
- name: mesh-health
  rules:
  - alert: HighErrorRate
    expr: |
      sum(rate(istio_requests_total{response_code=~"5.."}[5m])) by (destination_workload)
      / sum(rate(istio_requests_total[5m])) by (destination_workload)
      > 0.05
    for: 2m
  - alert: HighLatency
    expr: |
      histogram_quantile(0.99, sum(rate(istio_request_duration_milliseconds_bucket[5m])) 
      by (le, destination_workload)) > 1000
    for: 5m
  - alert: CircuitBreakerOpen
    expr: |
      envoy_cluster_circuit_breakers_default_cx_open > 0
    for: 1m
```

### Distributed Tracing
```
Trace propagation headers (B3 / W3C TraceContext):
  traceparent: 00-<trace-id>-<span-id>-<flags>
  
Envoy automatically:
  1. Extracts trace context from incoming request
  2. Creates span for proxy processing
  3. Propagates context to upstream request
  4. Reports span to collector (Jaeger/Zipkin/OTLP)

Span attributes added by mesh:
  - upstream_cluster
  - route_name  
  - response_flags (UO=upstream overflow, UF=upstream failure)
  - peer.address
  - istio.mesh_id
  - istio.canonical_service
```

### Access Logging
```json
{
  "start_time": "2024-01-15T10:30:00.000Z",
  "method": "POST",
  "path": "/api/v1/payment",
  "protocol": "HTTP/2",
  "response_code": 200,
  "response_flags": "-",
  "bytes_received": 256,
  "bytes_sent": 128,
  "duration": 45,
  "upstream_service_time": 42,
  "x_forwarded_for": "10.0.0.1",
  "user_agent": "grpc-go/1.50",
  "upstream_host": "10.0.1.5:8080",
  "upstream_cluster": "outbound|8080|v2|orders.production.svc.cluster.local",
  "upstream_transport_failure_reason": "",
  "route_name": "orders-v2-route",
  "downstream_peer_cert_uri": "spiffe://cluster.local/ns/production/sa/payment",
  "upstream_peer_cert_uri": "spiffe://cluster.local/ns/production/sa/orders"
}
```

---

## 10. Failure Scenarios & Mitigations

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| Control plane crash | No new config pushes; data plane continues with last-known-good | Multi-replica istiod; proxies cache config on disk |
| Certificate expiry | mTLS fails, connections rejected | Rotate at 80% lifetime; alert at 90%; fallback to permissive mode |
| xDS push storm | Proxy CPU spike during mass update | Rate-limit pushes; debounce; incremental delta xDS |
| Sidecar OOM | Pod crash, request drops | Set resource limits; sidecar scoping; circuit breaker |
| Split brain (network partition) | Inconsistent routing across partitions | Stale config is safe (old routes still work); eventual consistency |
| Envoy bug/crash | Sidecar restarts, brief connection drop | Hot restart; connection draining; readiness probes |
| CA compromise | All mesh identity compromised | Key rotation procedure; certificate revocation via CRL/OCSP |
| Config validation failure | Bad config rejected by control plane | Admission webhook; dry-run mode; canary config push |

### Failure Response Flags (Envoy)
```
DC: Downstream connection termination
UF: Upstream connection failure  
UO: Upstream overflow (circuit breaker)
NR: No route configured
URX: Upstream retry limit exceeded
UT: Upstream request timeout
LR: Connection local reset
RL: Rate limited
UAEX: Unauthorized external service
```

---

## 11. Considerations & Trade-offs

### Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sidecar vs ambient mesh | Sidecar per pod | Full L7 control per workload; ambient (ztunnel) for L4-only workloads |
| xDS protocol | Delta ADS | Reduces bandwidth; single stream simplifies ordering |
| Cert lifetime | 24 hours | Balance between security (short) and CA load (long) |
| Config store | Kubernetes CRDs | Native K8s integration; etcd as backend; kubectl compatible |
| Telemetry collection | In-proxy (native) | Lower latency than mixer; Wasm for custom |

### When NOT to Use Service Mesh
- Fewer than 10 services (overhead not justified)
- Latency-critical paths where even 100μs matters
- Non-HTTP/gRPC workloads (limited L7 features)
- Teams without platform engineering capacity to operate

### Evolution Path
```
Level 0: No mesh (direct service-to-service)
Level 1: mTLS only (security baseline)
Level 2: + Observability (metrics, traces)
Level 3: + Traffic management (canary, retries)
Level 4: + Policy (rate limiting, RBAC)
Level 5: + Multi-cluster/multi-mesh federation
```

### Production Checklist
- [ ] Sidecar resource limits configured per workload tier
- [ ] Sidecar scoping enabled (egress only to dependencies)
- [ ] mTLS in STRICT mode (not PERMISSIVE)
- [ ] Outlier detection on all services
- [ ] Retry budgets set (avoid retry amplification)
- [ ] Canary deployment for control plane upgrades
- [ ] Config validation webhook enabled
- [ ] Telemetry pipeline sized for mesh traffic volume
- [ ] Cert rotation alerts configured
- [ ] Graceful degradation tested (control plane outage)
