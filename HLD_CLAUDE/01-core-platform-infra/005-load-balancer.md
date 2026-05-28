# System Design: Load Balancer

## 1. Functional Requirements

### Core Routing Capabilities
- **L4 Routing (TCP/UDP)**: Route based on source/destination IP, port, and protocol
- **L7 Routing (HTTP/HTTPS)**: Route based on hostname, path, headers, query parameters
- **Weighted Round-Robin**: Distribute traffic to backends with configurable weights
- **Consistent Hashing**: Ensure client stickiness and minimize connection redistribution during scale-out
- **Canary Deployments**: Route percentage-based traffic to new backend versions
- **A/B Testing**: Route traffic based on user headers, cookies, or request attributes

### Backend Pool Management
- Add/remove/update backends without downtime
- Support graceful drain: accept existing connections but refuse new ones
- Manage multiple backend pools with different routing rules
- Support connection limits per backend
- Support request queuing when backend is overloaded

### Health Check Management
- **Liveness Checks**: TCP connect, HTTP GET with status code validation
- **Readiness Checks**: HTTP endpoint returning 200 when backend accepts traffic
- **Dependency Health Checks**: Verify backend's dependencies (DB, cache, queue) are healthy
- Exponential backoff on repeated failures
- Configurable check intervals (default 10s), timeouts (default 3s), failure thresholds (default 3 consecutive failures)
- Mark backend as unhealthy after threshold, remove from pool, then retry with backoff

### Connection & Request Draining
- **Connection Draining**: Accept existing connections during graceful shutdown, refuse new ones
- **Request Draining**: Complete in-flight requests before tearing down connection
- Configurable drain timeout (default 30s)
- Force close after drain timeout expires
- Automatic drain on backend removal or planned maintenance

### Advanced Routing Features
- **Request Shaping**: Rate limiting, request body inspection, header injection
- **Failover Strategy**: When primary pool unhealthy, failover to backup pool with configurable wait (e.g., 60 seconds)
- **Regional Failover**: Route to nearest healthy region; failover to other regions on all-backends-down
- **Circuit Breaker**: Track error rates per backend; circuit open when >50% errors for 30 seconds
- **Retry Logic**: Automatic retry on idempotent requests with jitter

### Multi-Tenant Support
- Separate routing rules per tenant
- Tenant-level rate limiting and quota enforcement
- Isolated audit logging per tenant
- DDoS protection per tenant

---

## 2. Non-Functional Requirements

### Performance
- **Request Throughput**: 50K requests/second average, 250K peak
- **Latency**: p50 < 10ms, p95 < 50ms, p99 < 150ms (end-to-end through LB)
- **Connection Handling**: Support 10M concurrent connections per LB node
- **Health Check Overhead**: < 1% of total capacity

### Availability & Reliability
- **Uptime**: 99.99% availability (52.5 minutes downtime/year)
- **Graceful Degradation**: Degrade quality (e.g., higher latency) before failing requests
- **Failover Time**: < 10 seconds to detect and failover unhealthy backend
- **Regional Failover**: < 30 seconds to detect all-region failure and failover

### Scalability
- **Horizontal Scale**: Add/remove nodes without traffic loss
- **Replication**: 3 regions × 12-36 nodes per region
- **Connection State**: Semi-stateless (connection affinity not required but preferred)
- **Auto-Scaling**: Scale based on CPU (target 70%), memory (target 80%), connection count

### Operability
- **Configuration Updates**: < 6 seconds propagation to all nodes
- **Zero-Downtime Deployments**: Rolling restart with connection draining
- **Monitoring**: Real-time metrics, dashboards, alerting
- **Debugging**: Distributed tracing, request-level logging, traffic capture

### Security & Compliance
- **Encryption**: TLS 1.3 for data in transit
- **DDoS Protection**: Volume-based, protocol-based, application-based
- **Multi-Tenancy Isolation**: Complete isolation between tenant traffic
- **Audit Logging**: All administrative actions logged with timestamp, user, change
- **Data Retention**: 30 days audit logs, 7 days metrics

---

## 3. Capacity Estimation

### Traffic Modeling
- **Baseline**: 50K requests/second (86 req/ms)
- **Peak**: 250K requests/second (430 req/ms) during campaigns
- **Request Size**: 10 KB average (1 KB to 1 MB range)
- **Response Size**: 50 KB average (cached responses smaller, dynamic responses larger)
- **Bandwidth**: 50K × (10KB + 50KB) = 3 Tbps → 3 Gbps = 375 GB/hour

### LB Node Sizing
- **CPU Cores**: 16 cores per node (assume 1M requests/core/sec)
  - 50K req/s / (1M req/core/s) = 0.05 cores minimum
  - Peak: 250K / (1M) = 0.25 cores
  - Safety factor 4x: target 1-4 cores used per node
  - Allocate 16 cores for headroom during spikes, maintenance

- **Memory**: 64 GB per node
  - 10M connections × 100 bytes = 1 GB for connection state
  - Routing table (500K routes) × 1 KB = 500 MB
  - Cache (L1): 50 GB local cache for hot rules/backends
  - Buffers and overhead: 12.5 GB
  - Total: ~64 GB

- **Network Interface**: 10 Gbps interface
  - Peak: 3 Gbps (well within 10 Gbps)
  - Headroom for bursts and failover traffic

- **Storage**: 500 GB SSD per node
  - Connection state snapshots: 1 GB
  - Metrics and logs (7 days): 100 GB
  - Overhead: 400 GB

### Cluster Sizing
- **Baseline**: 50K req/s ÷ 1400 req/s per node (using 70% CPU target) = 36 nodes
- **Peak Handling**: 250K req/s ÷ 6000 req/s per node (using 20% CPU target) = 42 nodes → auto-scale
- **Redundancy**: 2 spare nodes for maintenance, failures
- **Total**: 36 + 2 = 38 nodes per region
- **Multi-Region**: 3 regions × 38 nodes = 114 nodes globally

### Backend Pool Sizing
- Assume 1000 backends per region
- Average 50 connections per backend = 50K total connections
- Each backend needs 1 GB memory, 100 Mbps bandwidth for state
- ~1000 × 1 GB = 1 TB storage for backend state snapshots

### Storage & Data Volume
- **Control Plane DB (PostgreSQL)**:
  - 1M tenants × 10 KB = 10 GB
  - 1M backend pools × 5 KB = 5 GB
  - 5M routing rules × 2 KB = 10 GB
  - 10M audit logs × 500 bytes = 5 GB
  - Total: ~30 GB, allocated 100 GB with replication = 300 GB across primary + 2 replicas

- **Redis Cache**:
  - Routing table: 500M entries × 200 bytes = 100 GB
  - Connection state: 100M connections × 500 bytes = 50 GB
  - Health status: 1M backends × 1 KB = 1 GB
  - Rate limit counters: 1M tenants × 5 KB = 5 GB
  - Total: ~156 GB, sharded across 9 Redis nodes (18 GB each)

---

## 4. Data Modeling

### PostgreSQL (Control Plane)

```sql
-- Tenants
CREATE TABLE tenants (
  tenant_id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  tier ENUM('free', 'pro', 'enterprise') NOT NULL,
  rate_limit_rps INT DEFAULT 1000,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tenants_tier ON tenants(tier);

-- Backend Pools
CREATE TABLE backend_pools (
  pool_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  region VARCHAR(50) NOT NULL,
  routing_policy ENUM('round_robin', 'least_conn', 'consistent_hash') DEFAULT 'round_robin',
  health_check_interval_ms INT DEFAULT 10000,
  health_check_timeout_ms INT DEFAULT 3000,
  health_check_failure_threshold INT DEFAULT 3,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, name, region)
);
CREATE INDEX idx_backend_pools_tenant_region ON backend_pools(tenant_id, region);

-- Targets (Individual Backends)
CREATE TABLE targets (
  target_id UUID PRIMARY KEY,
  pool_id UUID NOT NULL REFERENCES backend_pools(pool_id) ON DELETE CASCADE,
  ip_address INET NOT NULL,
  port INT NOT NULL,
  weight INT DEFAULT 100,
  max_connections INT DEFAULT 10000,
  health_status ENUM('healthy', 'unhealthy', 'draining') DEFAULT 'healthy',
  last_health_check TIMESTAMPTZ,
  consecutive_failures INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(pool_id, ip_address, port)
);
CREATE INDEX idx_targets_pool_health ON targets(pool_id, health_status);
CREATE INDEX idx_targets_health_check ON targets(last_health_check);

-- Routing Rules
CREATE TABLE routing_rules (
  rule_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  priority INT NOT NULL,
  match_conditions JSONB NOT NULL,  -- {hostname: "api.example.com", path: "/users/*"}
  target_pool_id UUID REFERENCES backend_pools(pool_id),
  failover_pool_id UUID REFERENCES backend_pools(pool_id),
  canary_pool_id UUID REFERENCES backend_pools(pool_id),
  canary_traffic_percentage INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, name)
);
CREATE INDEX idx_routing_rules_tenant_priority ON routing_rules(tenant_id, priority);

-- Health Check Configuration
CREATE TABLE health_checks (
  check_id UUID PRIMARY KEY,
  pool_id UUID NOT NULL REFERENCES backend_pools(pool_id) ON DELETE CASCADE,
  check_type ENUM('tcp', 'http_get', 'http_post', 'grpc') NOT NULL,
  protocol VARCHAR(20),
  path VARCHAR(500),
  expected_status_codes INT[],
  timeout_ms INT DEFAULT 3000,
  interval_ms INT DEFAULT 10000,
  consecutive_success_threshold INT DEFAULT 1,
  consecutive_failure_threshold INT DEFAULT 3,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(pool_id, check_type)
);
CREATE INDEX idx_health_checks_pool ON health_checks(pool_id);

-- Audit Logs
CREATE TABLE audit_logs (
  log_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  action VARCHAR(100) NOT NULL,  -- 'create_pool', 'add_target', 'update_rule'
  resource_type VARCHAR(100) NOT NULL,  -- 'backend_pool', 'target', 'routing_rule'
  resource_id UUID NOT NULL,
  actor_id UUID NOT NULL,
  change_details JSONB,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_logs_tenant_timestamp ON audit_logs(tenant_id, timestamp);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- Rate Limit State
CREATE TABLE rate_limit_state (
  tenant_id UUID PRIMARY KEY REFERENCES tenants(tenant_id),
  current_tokens INT,
  last_refill TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_rate_limit_state_tenant ON rate_limit_state(tenant_id);
```

### Redis (In-Memory Cache)

```
Routing Table Cache:
  KEY: lb:routing:{tenant_id}:rules
  VALUE: JSON array of {rule_id, priority, conditions, target_pool_id, canary_pool_id}
  TTL: 3600 seconds (1 hour), refreshed on update

Backend Pool Cache:
  KEY: lb:pool:{pool_id}:targets
  VALUE: JSON array of {target_id, ip, port, weight, health_status, max_conn}
  TTL: 60 seconds (refreshed on health check update)

Health Status Cache:
  KEY: lb:health:{target_id}
  VALUE: {status, last_check, consecutive_failures, next_check_time}
  TTL: 30 seconds

Connection State:
  KEY: conn:{connection_id}
  VALUE: {client_ip, backend_target_id, established_at, last_activity}
  TTL: connection timeout (e.g., 300 seconds)

Rate Limit Counters (Token Bucket):
  KEY: ratelimit:{tenant_id}:tokens
  VALUE: current_tokens (float)
  TTL: 3600 seconds (refreshed with token refill)

  KEY: ratelimit:{tenant_id}:last_refill
  VALUE: timestamp
  TTL: 3600 seconds
```

### Indexing Strategy

**PostgreSQL Indexes (covering indexes)**:
1. `idx_backend_pools_tenant_region` - frequent query by tenant + region
2. `idx_targets_pool_health` - frequent query by pool + health status
3. `idx_routing_rules_tenant_priority` - frequent query by tenant + sorted by priority
4. `idx_audit_logs_tenant_timestamp` - audit trail queries by tenant + time range
5. Composite index on `(pool_id, target_id, health_status)` for batch updates
6. Partial index on `targets(pool_id) WHERE health_status != 'healthy'` for unhealthy targets

**Redis Memory Optimization**:
- Use Redis Streams for audit logs (append-only, TTL-based cleanup)
- Use sorted sets for health check scheduling (sorted by next_check_time)
- Use string encoding for hot data (routing rules, backend targets)

---

## 5. High-Level Design (HLD)

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUESTS                              │
│  HTTP/HTTPS/TCP traffic from millions of clients globally            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LOAD BALANCER CLUSTER (36-42 nodes)                     │
│                       Data Plane                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Node 1 - Node N (Each Stateless)                             │   │
│  │                                                               │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ 1. Connection Parser (2 cores)                      │    │   │
│  │  │    - Parse TCP/TLS handshake                        │    │   │
│  │  │    - Extract L4 (IP, port) and L7 (host, path)     │    │   │
│  │  │    - Buffer request headers                         │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │           │                                                  │   │
│  │           ▼                                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ 2. Routing Decision Engine (4 cores)               │    │   │
│  │  │    - Look up routing rules from L1 cache           │    │   │
│  │  │    - Match request to pool (round-robin/hash)      │    │   │
│  │  │    - Select target backend                         │    │   │
│  │  │    - Canary: route x% to canary pool              │    │   │
│  │  │    - A/B test: route based on user headers        │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │           │                                                  │   │
│  │           ▼                                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ 3. Health Check Validator (2 cores)                │    │   │
│  │  │    - Check if target is healthy from cache         │    │   │
│  │  │    - If unhealthy, use failover pool               │    │   │
│  │  │    - If all pools unhealthy, return 503            │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │           │                                                  │   │
│  │           ▼                                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ 4. Rate Limiter / Request Shaper (1 core)          │    │   │
│  │  │    - Apply token bucket rate limiting              │    │   │
│  │  │    - Enforce per-tenant quotas                     │    │   │
│  │  │    - Return 429 if limit exceeded                  │    │   │
│  │  │    - Buffer for burst handling                     │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │           │                                                  │   │
│  │           ▼                                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ 5. Request Forwarder (4 cores)                      │    │   │
│  │  │    - Open connection to backend                    │    │   │
│  │  │    - Forward request with correlation ID           │    │   │
│  │  │    - Receive response                              │    │   │
│  │  │    - Handle connection draining (reject new)       │    │   │
│  │  │    - Implement circuit breaker on errors           │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │           │                                                  │   │
│  │           ▼                                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ 6. Event Emission Service (1 core)                 │    │   │
│  │  │    - Emit request metrics to Kafka                 │    │   │
│  │  │    - Push health check results                     │    │   │
│  │  │    - Stream audit logs                             │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │           │                                                  │   │
│  │           ▼                                                  │   │
│  │      Correlation ID: req_{uuid}_{timestamp}                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                               │                                      │
└───────────────────────────────┼──────────────────────────────────────┘
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
        ┌──────────────────┐          ┌──────────────────┐
        │   BACKEND POOL 1 │          │   BACKEND POOL 2 │
        │  (50-200 targets)│          │  (50-200 targets)│
        │  Healthy targets │          │  Healthy targets │
        │  Canary targets  │          │  Failover targets│
        └──────────────────┘          └──────────────────┘
        All requests forwarded and responses returned to client


┌─────────────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE                                     │
│                  (Background Services)                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Admin API Server (4 instances, 8 cores, 16 GB each)          │  │
│  │ - Handle CRUD operations on pools, rules, targets            │  │
│  │ - Validate configuration changes                             │  │
│  │ - Persist to PostgreSQL                                      │  │
│  │ - Publish change events to Kafka                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                          │                                           │
│                          ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Kafka (9 brokers, 3 replicas per topic)                     │  │
│  │ Topics:                                                       │  │
│  │  - config-changes: routing rules, pool updates              │  │
│  │  - health-status: backend health updates                    │  │
│  │  - request-metrics: request rate, latency, errors           │  │
│  │  - audit-logs: all admin actions                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                          │                                           │
│          ┌───────────────┼───────────────┐                          │
│          ▼               ▼               ▼                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ PostgreSQL   │  │    Redis     │  │  etcd/Consul │             │
│  │ (Primary +   │  │  Cluster     │  │  Cluster     │             │
│  │  2 Replicas) │  │  (9 nodes)   │  │ (3 nodes)    │             │
│  │              │  │              │  │              │             │
│  │ Config DB    │  │ Cache Layer  │  │ Service      │             │
│  │ Audit Logs   │  │ State        │  │ Discovery    │             │
│  │ Rate Limits  │  │              │  │              │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow
1. Client sends HTTP request to LB node
2. Connection Parser extracts L4/L7 information
3. Routing Engine looks up rules from local cache + Redis cache + PostgreSQL
4. Health Check Validator confirms selected target is healthy
5. Rate Limiter checks tenant quota
6. Request Forwarder opens connection to backend, sends request
7. Event Emission Service publishes metrics to Kafka
8. Control Plane monitors Kafka stream, updates caches across all nodes
9. Configuration changes propagate within 6 seconds to all 36 nodes

---

## 6. Low-Level Design (LLD)

### gRPC Control Plane API

```protobuf
service LoadBalancerControlPlane {
  // Pool Management
  rpc CreateBackendPool(CreatePoolRequest) returns (PoolResponse);
  rpc UpdateBackendPool(UpdatePoolRequest) returns (PoolResponse);
  rpc DeleteBackendPool(DeletePoolRequest) returns (Empty);
  rpc ListBackendPools(ListPoolsRequest) returns (PoolList);

  // Target Management
  rpc AddTarget(AddTargetRequest) returns (TargetResponse);
  rpc RemoveTarget(RemoveTargetRequest) returns (Empty);
  rpc DrainTarget(DrainTargetRequest) returns (Empty);
  rpc GetTargetHealth(TargetHealthRequest) returns (TargetHealthResponse);

  // Routing Rules
  rpc CreateRoutingRule(CreateRuleRequest) returns (RuleResponse);
  rpc UpdateRoutingRule(UpdateRuleRequest) returns (RuleResponse);
  rpc DeleteRoutingRule(DeleteRuleRequest) returns (Empty);
  rpc ListRoutingRules(ListRulesRequest) returns (RuleList);

  // Health Checks
  rpc SetHealthCheckConfig(HealthCheckConfigRequest) returns (HealthCheckResponse);
  rpc GetHealthCheckStatus(HealthCheckStatusRequest) returns (HealthCheckStatusResponse);

  // Sync Operations (called by LB data plane nodes)
  rpc SyncAllConfigs(SyncRequest) returns (ConfigSnapshot);
  rpc StreamConfigUpdates(StreamRequest) returns (stream ConfigUpdate);
  rpc ReportHealthStatus(HealthReport) returns (Empty);
}

message CreatePoolRequest {
  string tenant_id = 1;
  string pool_name = 2;
  string region = 3;
  RoutingPolicy routing_policy = 4;
  int32 health_check_interval_ms = 5;
  int32 max_connections = 6;
}

message PoolResponse {
  string pool_id = 1;
  string tenant_id = 2;
  string pool_name = 3;
  string region = 4;
  RoutingPolicy routing_policy = 5;
  int64 created_timestamp = 6;
}

message AddTargetRequest {
  string pool_id = 1;
  string ip_address = 2;
  int32 port = 3;
  int32 weight = 4;
  int32 max_connections = 5;
}

message TargetResponse {
  string target_id = 1;
  string pool_id = 2;
  string ip_address = 3;
  int32 port = 4;
  HealthStatus health_status = 5;
}
```

### Health Check Protocols

**TCP Liveness Check** (Connection only, no application logic):
```
1. LB initiates TCP connection to backend:port
2. If SYN-ACK received within 3s: healthy
3. If timeout or RST: unhealthy
4. Mark as unhealthy after 3 consecutive failures
5. Retry with exponential backoff: 10s, 20s, 40s, 80s
```

**HTTP Readiness Check** (Application-level):
```
1. LB sends: GET /health HTTP/1.1
2. Expects: HTTP 200 within 3s
3. If 503, 502, or timeout: mark unhealthy
4. If 200 for 1 consecutive check after being unhealthy: mark healthy
5. Retry interval: 10s when healthy, 5s exponential backoff when unhealthy
```

**Dependency Health Check** (Deep dependency checks):
```
1. LB sends: GET /health/dependencies HTTP/1.1
2. Expects: {status: "healthy", dependencies: {db: "ok", cache: "ok", queue: "ok"}}
3. If any dependency "failing": mark backend as unhealthy
4. Only route to backend if all dependencies healthy
```

### Routing Decision Algorithm

```
function selectBackend(request, tenant_id, routingRules) {
  // 1. Load routing rules from L1 cache (in-process)
  rules = L1_CACHE.get("routing_rules:" + tenant_id) ?? loadFromRedis()
  
  // 2. Find matching rule by priority (sorted)
  matchedRule = null
  for rule in rules.sorted_by_priority {
    if matchesConditions(request, rule.match_conditions) {
      matchedRule = rule
      break
    }
  }
  
  if not matchedRule {
    return error(404, "No matching routing rule")
  }
  
  // 3. Select pool (primary or canary)
  pool = matchedRule.target_pool
  if random() < matchedRule.canary_traffic_percentage / 100 {
    pool = matchedRule.canary_pool
  }
  
  // 4. Get healthy targets from pool
  targets = L1_CACHE.get("targets:" + pool.id) ?? loadFromRedis()
  healthyTargets = [t for t in targets if t.health_status == "healthy"]
  
  if empty(healthyTargets) {
    // Failover to backup pool
    if matchedRule.failover_pool_id {
      targets = loadPoolTargets(matchedRule.failover_pool_id)
      healthyTargets = [t for t in targets if t.health_status == "healthy"]
    }
    
    if empty(healthyTargets) {
      return error(503, "All backends unhealthy")
    }
  }
  
  // 5. Select target using routing policy (consistent hash for canary)
  target = selectByPolicy(healthyTargets, matchedRule.routing_policy, request)
  
  // 6. Check connection count
  if target.current_connections >= target.max_connections {
    // Try next target in queue
    target = findAvailableTarget(healthyTargets, request)
  }
  
  return target
}

function selectByPolicy(targets, policy, request) {
  if policy == "round_robin" {
    return targets[atomic_increment() % len(targets)]
  }
  else if policy == "least_conn" {
    return min(targets, key=t => t.current_connections)
  }
  else if policy == "consistent_hash" {
    hash_value = hash(request.client_ip, request.session_id)
    return targets[hash_value % len(targets)]
  }
}
```

### Connection Draining Algorithm

```
function drainTarget(target_id, timeout_seconds) {
  target = getTarget(target_id)
  
  // 1. Set target state to DRAINING
  target.health_status = "DRAINING"
  publishEvent("target_draining", target_id)
  
  // 2. Stop assigning new connections to this target
  // (remove from healthy targets list in all LB nodes)
  broadcastConfigUpdate("remove_from_pool", target_id)
  wait(100ms)  // Allow time for all nodes to sync
  
  // 3. Wait for existing connections to close gracefully
  start_time = now()
  while target.current_connections > 0 and (now() - start_time) < timeout_seconds {
    wait(100ms)
  }
  
  // 4. After timeout, force close any remaining connections
  if target.current_connections > 0 {
    forceClose(target_id)
  }
  
  // 5. Remove target from pool
  target.deleted = true
  publishEvent("target_removed", target_id)
}
```

---

## 7. Architecture Components

### Data Plane Components (Per LB Node)

| Component | Cores | Memory | Threads | Purpose |
|-----------|-------|--------|---------|---------|
| Connection Parser | 2 | 2 GB | 64 | Parse TCP/TLS handshakes, extract L7 headers |
| Routing Engine | 4 | 10 GB | 128 | Rule matching, pool selection, traffic splitting |
| Health Check Validator | 2 | 1 GB | 32 | Validate target health from cache, apply fallback |
| Rate Limiter | 1 | 500 MB | 16 | Token bucket enforcement, quota checks |
| Request Forwarder | 4 | 20 GB | 128 | Connect to backend, forward request, handle draining |
| Event Emitter | 1 | 500 MB | 16 | Publish metrics to Kafka, stream audit logs |
| **Total** | **14** | **34 GB** | **384** | - |
| **Overhead** | **2** | **30 GB** | **- ** | OS, shared buffers, monitoring agent |
| **Allocated** | **16** | **64 GB** | **- ** | - |

### Control Plane Components

| Component | Instances | vCPU/Instance | Memory/Instance | Purpose |
|-----------|-----------|---------------|-----------------|---------|
| Admin API Server | 4 | 8 | 16 GB | Handle configuration CRUD, publish events |
| Kafka Broker | 9 | 8 | 32 GB | Distribute config changes, collect metrics |
| PostgreSQL Primary | 1 | 16 | 64 GB | Store pools, rules, audit logs (write) |
| PostgreSQL Replica | 2 | 16 | 64 GB | Read replicas, failover candidates |
| Redis Cluster | 9 | 4 | 18 GB | Cache routing rules, health status, rate limits |
| etcd/Consul | 3 | 4 | 8 GB | Service discovery, leader election |

### Memory Breakdown (Per LB Node)

| Component | Allocation |
|-----------|-----------|
| L1 Cache (routing rules, backends) | 25 GB |
| Connection state table | 8 GB |
| Request buffers (1000 concurrent × 100 KB) | 100 MB |
| Health check cache | 200 MB |
| Rate limit counters | 500 MB |
| OS and system overhead | 30 GB |
| **Total** | **64 GB** |

---

## 8. Deep Dive

### Request Flow (Timeline Analysis)

**Scenario**: Client sends HTTP request to LB, LB routes to backend, backend processes, response returned.

```
T+0ms: Client sends SYN to LB
T+0.5ms: LB SYN-ACK, client ACK (connection established)
T+1ms: Client sends HTTP GET request (headers received)

T+1.5ms: Connection Parser receives request
         - Parse TCP/TLS headers: <100 μs
         - Extract HTTP headers (hostname, path): <500 μs
         - Total: <600 μs

T+2.1ms: Routing Engine (begins)
         - L1 cache lookup (in-process hashmap): <1 μs
         - Match rules against request: <1 ms (typically 10-100 rules checked)
         - Select pool and target: <100 μs
         - Check health status from L1 cache: <10 μs
         - Consistent hash if needed: <50 μs
         - Total: <2 ms

T+4.1ms: Health Check Validator
         - Check if target healthy in L1 cache: <10 μs (hit rate 99.9%)
         - If miss, check Redis (L2): <1 ms
         - Apply fallback if unhealthy: <100 μs
         - Total: <10 μs (average, with caching)

T+4.12ms: Rate Limiter
          - Atomic increment token bucket counter: <10 μs
          - Check if within quota: <5 μs
          - Total: <20 μs

T+4.14ms: Request Forwarder
          - Lookup backend connection pool: <10 μs
          - Get available connection from pool: <20 μs (or create new: <500 μs)
          - Send HTTP request to backend: <1 ms (network latency to backend)
          - Total: ~2 ms (assuming backend is in same datacenter)

T+6.14ms: Backend receives request
          - Process and generate response: ~150 ms (assumption: typical application)

T+156.14ms: Backend sends response back

T+157.14ms: LB receives response from backend
            - Event Emitter publishes to Kafka: <100 μs (async, doesn't block response)
            - Total: <100 μs

T+157.24ms: LB forwards response to client
            - Copy response to client: <1 ms
            - Total: <1 ms

T+158.24ms: Client receives complete response
            - Client-perceived latency: ~158 ms
            - LB-introduced latency: ~8 ms (0.5% overhead)

T+159ms: Connection either kept alive for next request (HTTP/1.1 Keep-Alive)
         or closed (HTTP/1.0 or explicit Close)
```

**Latency Breakdown**:
- L4 processing (parsing, routing): 2.1 ms
- Health checks: 0.02 ms (cached)
- Rate limiting: 0.02 ms
- Backend forwarding: 2 ms
- Backend processing: ~150 ms (application dependent)
- Response forwarding: 1 ms
- **Total LB latency**: ~5.14 ms (excluding backend processing)
- **With p99 backend latency (200ms)**: ~205 ms total

---

### Health Check Loop (Detailed Mechanics)

**Initial State**: Target added to pool, starts in HEALTHY state.

```
Time: T+0
Event: Target added to pool (ip: 10.0.0.5, port: 8080)
Action: Schedule health check immediately

Time: T+0
Event: Health check executed
  - TCP connect to 10.0.0.5:8080: success
  - HTTP GET /health: returns 200 OK
  - Dependency check: {db: ok, cache: ok}
Result: target.health_status = HEALTHY
Result: target.consecutive_failures = 0
Action: Schedule next check in 10 seconds

Time: T+10s
Event: Health check executed
  - TCP connect: success
  - HTTP GET /health: returns 200 OK
  - Dependency check: {db: ok, cache: ok}
Result: target.health_status = HEALTHY
Action: Schedule next check in 10 seconds

Time: T+20s
Event: Backend service crashes
Event: Health check executed
  - TCP connect to 10.0.0.5:8080: timeout (3 second timeout)
Result: target.health_status = still HEALTHY
Result: target.consecutive_failures = 1
Action: Schedule next check in 5 seconds (exponential backoff: 10s → 5s)

Time: T+25s
Event: Health check executed
  - TCP connect: timeout
Result: target.consecutive_failures = 2
Action: Schedule next check in 5 seconds

Time: T+30s
Event: Health check executed (3rd consecutive failure)
  - TCP connect: timeout
Result: target.consecutive_failures = 3 (exceeds threshold of 3)
Result: target.health_status = UNHEALTHY
Action: Publish "health_status_changed" event to Kafka
Action: All LB nodes receive event, remove from healthy_targets list
Action: Schedule next check in 10 seconds (shorter interval to detect recovery faster)

Time: T+40s
Event: Backend service restarts
Event: Health check executed
  - TCP connect to 10.0.0.5:8080: success
  - HTTP GET /health: returns 200 OK
  - Dependency check: {db: ok, cache: ok}
Result: target.consecutive_failures = 0 (only 1 successful check needed)
Result: target.health_status = HEALTHY
Action: Publish "health_status_changed" event to Kafka
Action: All LB nodes receive event, add back to healthy_targets list
Action: Schedule next check in 10 seconds (normal interval)

Time: T+50s, T+60s, T+70s, ...
Event: Healthy checks continue every 10 seconds
Result: target.health_status = HEALTHY
```

**Optimization**: During HEALTHY state, checks are less frequent (10s), but during UNHEALTHY or transitional states, checks accelerate (1-5s backoff).

---

### Configuration Update Propagation

**Scenario**: Admin creates new routing rule, all LB nodes must be aware within 6 seconds.

```
Time: T+0
Event: Admin posts new routing rule via gRPC
  POST /api/routing-rules
  {
    tenant_id: "acme-corp",
    rule_name: "api-v2-canary",
    priority: 10,
    match_conditions: {hostname: "api.acme.com", path: "/api/v2/*"},
    target_pool_id: "pool-prod-v1",
    canary_pool_id: "pool-canary-v2",
    canary_traffic_percentage: 5
  }

Time: T+0
Event: Admin API Server receives request
Action: Validate rule syntax, tenant permissions
Action: Insert into PostgreSQL: INSERT INTO routing_rules (...)
Result: New rule created with rule_id = "rule_12345"
Action: Publish to Kafka topic "config-changes":
  {
    event_type: "rule_created",
    rule_id: "rule_12345",
    tenant_id: "acme-corp",
    timestamp: T+0,
    change: {...full rule details...}
  }

Time: T+50ms
Event: Kafka broker receives message, replicates to 3 brokers
Action: Commit to Kafka log

Time: T+100ms
Event: Kafka consumer in each LB node receives message
Action: Update L1 cache for tenant "acme-corp"
  OLD: L1_CACHE["routing_rules:acme-corp"] = [rule_1, rule_2, ..., rule_10]
  NEW: L1_CACHE["routing_rules:acme-corp"] = [rule_1, rule_2, ..., rule_10, rule_12345]
Action: Also update Redis L2 cache (async)

Time: T+100ms (after update)
Event: New request arrives from client
Request: GET /api/v2/users HTTP/1.1, Host: api.acme.com

Time: T+101ms
Event: Routing Engine looks up rules for "acme-corp"
Action: Check L1 cache (now contains the new rule)
Result: Routing engine finds both old and new rules
Result: New rule has priority 10, old rules have lower/higher priority
Action: Routing rule matching determines which rule to use
Result: If request matches new rule (hostname + path), route to canary_pool_id
Result: 5% of matching traffic goes to canary_pool_v2, 95% to prod_pool_v1

Time: T+6 seconds
Event: Redis async cache update completes (if needed for failover scenarios)

ALL 36 LB NODES have been updated within T+100ms
MAXIMUM PROPAGATION TIME: ~6 seconds (for edge cases like network delays)
TYPICAL PROPAGATION: <100ms
```

---

## 9. Optimization Strategies

### Multi-Level Caching Strategy

**L1 Cache (Local Memory, In-Process)**
```
Location: Each LB node's RAM
Storage: HashMap, concurrent hashmap
Contents: Routing rules, backend targets, health status
Hit Latency: <100 microseconds
Hit Rate: 99.99%

Refresh Strategy:
  - Kafka consumer updates on change
  - TTL: 1 hour (but refreshed on change)
  - Size: ~25 GB per node

Example:
  L1_CACHE["routing_rules:tenant_acme"] = [
    {rule_id: 1, priority: 100, conditions: {}, target_pool: "prod"},
    {rule_id: 2, priority: 10, conditions: {path: "/api/v2/*"}, target_pool: "v2"},
  ]
```

**L2 Cache (Redis, In-Memory Distributed)**
```
Location: Redis cluster (9 nodes)
Storage: String keys, JSON values
Contents: Same as L1, shared across all nodes
Hit Latency: <1 millisecond (network round-trip)
Hit Rate: 99% (mostly for cold-start after node deployment)

Refresh Strategy:
  - Kafka consumer updates via Redis MSET
  - TTL: 1 hour, refreshed on change
  - Cluster size: 18 GB per node × 9 = 162 GB total

Example Redis operation:
  MSET routing_rules:tenant_acme '{"rule_1": {...}, "rule_2": {...}}'
       health_status:target_123 '{"status": "healthy", "timestamp": T}'
       rate_limit:tenant_acme:tokens '250'
```

**L3 Cache (PostgreSQL, Persistent)**
```
Location: PostgreSQL primary (with replicas)
Storage: Tables with indexes
Contents: Single source of truth for all configuration
Hit Latency: <10 milliseconds (connection pool + query)
Hit Rate: <1% (only for initialization or emergency fallback)

Fallback Scenario:
  if L1_CACHE miss and L2_CACHE miss:
    SELECT rules FROM routing_rules WHERE tenant_id = ? ORDER BY priority
    // Result is returned to caller
    // Async: populate L1 and L2 caches
```

**Cache Invalidation Strategy**:
- Event-driven: Kafka publishes changes to all nodes
- Time-based: 1-hour TTL (but rarely reached due to event-driven updates)
- Write-through: Update L1 → Kafka → L2 → L3 (all synchronized)
- Consistency: Strong consistency within 100ms for critical data

### Connection Pooling Optimization

```
Connection Pool per Backend:
  - Backend target: 10.0.0.5:8080
  - Pool size: 100 connections (pre-warmed)
  - Max connections: 1000 (allow expansion under load)
  - Keep-alive timeout: 300 seconds
  - Connection reuse: 95% of requests reuse existing connection
  - Effect: Saves TCP handshake (50ms) on 95% of requests

Pooling Implementation:
  backend_pool = ConnectionPool(
    host="10.0.0.5",
    port=8080,
    min_size=100,
    max_size=1000,
    keep_alive_ms=300000
  )
  
  connection = backend_pool.acquire()  // <1ms if available, <50ms if new
  try {
    response = connection.send(request)
  } finally {
    backend_pool.release(connection)  // Return to pool for reuse
  }
```

### Token Bucket Rate Limiting with Local Buffering

**Goal**: Enforce per-tenant rate limit of 1000 req/s while minimizing Redis calls.

```
Local Buffering Algorithm:
  - Each LB node maintains local token bucket (in RAM)
  - Tokens = 1000 (capacity)
  - Refill rate = 1000 tokens / 1000ms = 1 token per millisecond
  - Burst allowance = 5000 tokens (5-second burst window)

Request Processing:
  1. Check local bucket: if tokens > 0
       - Decrement token
       - Allow request
       - No Redis call needed (fast path)
       - Local fast path: <10 microseconds
       - Hit rate: ~95%

  2. Bucket depleted (tokens <= 0)
       - Send token refill to Redis
       - Redis response: 1000 tokens refilled
       - Decrement one token
       - Allow request
       - Redis call path: <1 millisecond
       - Hit rate: ~5%

Benefit:
  - Peak traffic: 250K req/s across 36 nodes = 7K req/s per node
  - Without local buffering: 7K Redis calls/s per node × 36 nodes = 252K Redis ops/s
  - With local buffering: ~350 Redis refill calls/s per node × 36 nodes = 12.6K Redis ops/s
  - Reduction: 95% fewer Redis calls (20x improvement)
  - Throughput: Can handle burst up to 1000 + 5000 = 6000 req/s per tenant during spikes

Implementation:
  class TokenBucket:
    def __init__(self, rate, burst):
      self.rate = rate  // 1000 req/s
      self.burst = burst  // 5000 tokens
      self.tokens = burst
      self.last_refill = now()
      self.redis = redis_client()
    
    def allow_request(self):
      now = time.now()
      elapsed = now - self.last_refill
      refilled = elapsed * self.rate / 1000  // tokens refilled
      self.tokens = min(self.burst, self.tokens + refilled)
      self.last_refill = now
      
      if self.tokens > 0:
        self.tokens -= 1
        return True  // fast path (no Redis)
      else:
        // Slow path: refill from Redis
        redis_response = self.redis.incr("tokens:" + tenant_id)
        if redis_response > 0:
          self.tokens = redis_response - 1
          self.last_refill = now
          return True
        else:
          return False  // Rate limit exceeded
```

### Health Check Optimization with Exponential Backoff

```
Health Check Frequency Optimization:

State: HEALTHY
  - Check interval: 10 seconds (monitoring for failures)
  - Backoff: None
  - Rationale: Infrequent checks during stable state

State: UNHEALTHY
  - Check interval: 1 second (detect recovery quickly)
  - Backoff progression: 1s, 2s, 4s, 8s, 16s, 30s (cap at 30s)
  - Rationale: After N consecutive failures, increase interval to reduce load

State: TRANSITIONING (e.g., draining)
  - Check interval: 2 seconds (monitor active connections)
  - Backoff: None during drain window

Effect:
  - 36 LB nodes × 1000 backends = 36K health checks per interval
  - HEALTHY: 36K / 10s = 3.6K checks/s (minimal load)
  - UNHEALTHY (after 3 failures): 36K / 30s = 1.2K checks/s (if exponential backoff at max)
  - Peak: 36K / 1s = 36K checks/s (only during active failures, temporary)

Total Health Check Load:
  - Network: 36K checks × 100 bytes = 3.6 Mbps (0.036% of 10 Gbps)
  - CPU: Negligible (2 cores dedicated, <10% utilized)
  - Memory: Minimal (status cache <1 GB)
```

---

## 10. Observability

### Service Level Indicators (SLIs)

| SLI | Target | Calculation |
|-----|--------|-------------|
| **Request Success Rate** | >99.9% | (successful_requests / total_requests) |
| **P99 Latency** | <150ms | percentile(latency, 99) |
| **Availability** | >99.99% | (uptime_seconds / total_seconds) |
| **Error Rate** | <0.1% | (error_requests / total_requests) |

### Service Level Objectives (SLOs)

```
1. Request Success Rate >= 99.9%
   - Error Budget: 0.1% = 52.5 minutes/year
   - Monthly Budget: ~4.4 minutes/month
   - Weekly Budget: ~1 minute/week
   - Alert Threshold: >0.15% error rate for >5 minutes → P2 (Slack)
                     >0.5% error rate for >1 minute → P1 (Page)

2. P99 Latency <= 150ms
   - Measurement: Latency at 99th percentile (excludes top 1% outliers)
   - Alert Threshold: >200ms for >10 minutes → P2
                      >300ms for >1 minute → P1

3. Availability >= 99.99%
   - Downtime Budget: 52.5 minutes/year
   - Measured: (Successful responses + Client errors) / Total requests
   - Exclude: Client errors (4xx), expected failures
   - Alert Threshold: <99.99% for >1 hour → P1 (immediate page)

4. Error Rate <= 0.1%
   - Includes: 5xx errors, connection timeouts, backend unavailable
   - Excludes: 4xx client errors (invalid requests)
   - Alert Threshold: >0.5% for >5 minutes → P2
                      >1% for >1 minute → P1
```

### Key Metrics

**Request Metrics**:
```
lb_requests_total{tenant, region, status_code, backend_pool}
lb_request_duration_seconds{le, tenant, region}
lb_request_body_size_bytes{tenant}
lb_response_body_size_bytes{tenant}
```

**Backend Health**:
```
lb_backend_health_status{pool_id, target_id, check_type}  // 1 = healthy, 0 = unhealthy
lb_backend_response_time_seconds{pool_id}
lb_backend_active_connections{pool_id, target_id}
lb_backend_connection_errors_total{pool_id, target_id}
```

**Rate Limiting**:
```
lb_rate_limit_requests_allowed_total{tenant}
lb_rate_limit_requests_rejected_total{tenant}
lb_rate_limit_current_tokens{tenant}
```

**Connection Metrics**:
```
lb_active_connections_total{}
lb_connections_created_total{}
lb_connections_closed_total{}
lb_connection_pool_size{backend_id}
lb_connection_wait_time_seconds{}
```

**Routing Metrics**:
```
lb_routing_rule_matches_total{rule_id, tenant}
lb_canary_traffic_percentage{rule_id}
lb_failover_events_total{pool_id}
```

**Resource Metrics**:
```
lb_cpu_usage_percent{}
lb_memory_usage_bytes{}
lb_network_rx_bytes_total{interface}
lb_network_tx_bytes_total{interface}
```

### Grafana Dashboards

**Dashboard 1: Overview**
```
Panels:
  - Request rate (req/s): 50K baseline, 250K peak
  - Request success rate: >99.9% target (red line at 99.9%)
  - P99 latency: <150ms target (red line at 150ms)
  - Active backends: healthy vs unhealthy count
  - Error rate breakdown: 5xx, timeouts, connection resets
  - Regional distribution: traffic per region
  - Top 10 tenants: by request count
  - LB node count: active vs spare
```

**Dashboard 2: Backend Pool Deep Dive**
```
Panels:
  - Pool health status: traffic distribution across backends
  - Backend response times: p50, p95, p99
  - Active connections per backend
  - Connection errors over time
  - Drain progress: connections remaining during graceful shutdown
  - Failover events: when and why
  - Canary traffic: percentage routed to canary pool
```

**Dashboard 3: Rate Limiting**
```
Panels:
  - Requests allowed vs rejected
  - Rate limit rejection rate by tenant
  - Token bucket status: current tokens vs capacity
  - Tenant quota utilization
  - Burst handling: peak burst vs baseline
```

**Dashboard 4: Health Checks**
```
Panels:
  - Health check success rate
  - Check interval distribution (healthy vs unhealthy)
  - Time to detect failures: failure → marked unhealthy
  - Time to recovery: recovery → marked healthy
  - Dependency health status: DB, cache, queue
```

### Alert Rules

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| HighErrorRate | error_rate > 1% for 1m | P1 | Page on-call |
| HighLatency | p99_latency > 300ms for 1m | P1 | Page on-call |
| AllBackendsDown | healthy_backends == 0 for 30s | P1 | Page on-call |
| LowAvailability | availability < 99.99% for 1h | P1 | Page on-call |
| HighErrorRate2 | error_rate > 0.5% for 5m | P2 | Slack alert |
| HighLatency2 | p99_latency > 200ms for 10m | P2 | Slack alert |
| LowBackendCount | healthy_backends < 5 for 5m | P2 | Slack alert |
| HighMemoryUsage | memory_usage > 90% for 5m | P3 | Ticket |
| HighCPUUsage | cpu_usage > 85% for 10m | P3 | Ticket |

---

## 11. Considerations & Assumptions

### Assumptions

1. **Network Reliability**: Assume <1% packet loss in WAN, <0.1% within datacenter
2. **Synchronized Clocks**: All nodes within 100ms skew (NTP)
3. **Semi-Stateless Backends**: Backends can be replaced; no local session storage
4. **Sufficient Tenant Isolation**: Noisy neighbor issues are acceptable but minimized
5. **Reliable Kafka**: Kafka brokers persist events; replication factor >= 3
6. **Lazy Consistency**: Configuration changes acceptable with 6-second propagation delay
7. **Graceful Shutdown**: Backends support connection draining (honor SIGTERM)
8. **Health Check Endpoints**: All backends expose /health and /health/dependencies endpoints

### Trade-Offs and Decisions

| Decision | Choice | Trade-Off | Reasoning |
|----------|--------|-----------|-----------|
| **Consistency Model** | Eventual (6s) | vs. Strong Consistency | Configuration is read-only for most operations; 6s delay acceptable for routing rule changes; strong consistency would require distributed consensus (2-3x latency) |
| **Caching Strategy** | Multi-level (L1, L2, L3) | vs. Direct DB | Reduces PostgreSQL load by 99%; adds cache invalidation complexity but manageable via Kafka events |
| **Rate Limiting** | Local token bucket + Redis refill | vs. Centralized Redis | Local buffering reduces Redis load by 95%; small inaccuracy acceptable (overages < 1%) |
| **Health Check Frequency** | Adaptive (10s healthy, 1-30s unhealthy) | vs. Fixed 10s | Adaptive reduces check load during stable state; increases check frequency during failures for faster recovery |
| **Connection Draining** | 30-second timeout + force close | vs. Unbounded wait | Force close prevents zombie connections; 30s allows most requests to complete |
| **Regional Failover** | 60-second wait before failover | vs. Immediate failover | 60s wait avoids unnecessary failovers during transient network issues; can be reduced to 10s in geo-replicated setups |
| **Routing Rule Priority** | Numeric priority (1-1000) | vs. First-match | Numeric priority allows reordering without code changes; slightly more complex matching logic |
| **Canary Deployment** | Percentage-based (1-100%) | vs. User-based | Percentage-based simpler and more predictable; user-based would require session affinity |

### Failure Modes and Recovery

| Failure Mode | Impact | Detection | Recovery | Time |
|--------------|--------|-----------|----------|------|
| **Single LB Node Crash** | ~2-3% traffic loss (36 nodes, 1 fails) | Health check: node health score drops | Auto-scale: new node provisioned in existing region | <2 min |
| **All Backends in Pool Unhealthy** | Complete service unavailability for that pool | Health checks + SLI monitoring | Failover to backup pool; alert on-call | <10s |
| **Config Sync Failure** | New rules not propagated to all nodes | Kafka lag monitoring; rule age metric | Manual rollback via API; re-push config | <1 min |
| **Cascading Health Check Failures** | False positives marking healthy backends unhealthy | Health check success rate, error correlation | Exponential backoff prevents excessive retries; increase check interval | <2 min |
| **Split-Brain (LB cluster split)** | Some nodes see different config | Kafka offset monitoring, config version mismatch | Prevent via etcd/Consul quorum; eventual consistency wins | < 6s |
| **Redis Cache Unavailable** | Latency spike (fallback to PostgreSQL: <10ms) | Cache hit rate drops, query latency increases | Redis cluster failover to replica | <5s |
| **PostgreSQL Failover** | Brief unavailability during promotion | Replication lag, failover signal | Automatic promotion of standby; DNS update | <30s |
| **DDoS Attack (Volumetric)** | Request rate > 250K peak capacity | Rate limit rejection rate spikes | Auto-scale LB nodes; upstream WAF activation; BGP blackhole | <5 min |

### Security Considerations

| Threat | Mitigation |
|--------|-----------|
| **DDoS Volumetric** | Rate limiting per tenant; BGP blackhole upstream; AWS Shield |
| **Request Smuggling (HTTP)** | Strict HTTP/1.1 parsing; disable pipelining; HTTP/2 default |
| **MITM/Man-in-the-Middle** | TLS 1.3 enforced; certificate pinning for backend connections |
| **Config Injection** | Validate all inputs; schema validation via Zod/Pydantic; sanitize Kafka events |
| **Cross-Tenant Data Leak** | Strict tenant ID validation on all routes; connection isolation; audit logging |
| **Unauthorized Admin API** | OAuth 2.0 + RBAC; API key rotation; rate limiting on admin endpoints |
| **Backend Credential Exposure** | Store backend IPs in etcd/Consul (not source code); rotate every 90 days |

### Compliance & Cost Optimization

| Aspect | Strategy |
|--------|----------|
| **Data Retention** | 30-day audit log retention; 7-day metrics retention; compress older logs to S3 |
| **Multi-Tenancy Isolation** | Per-tenant rate limits; isolated database schemas; audit trail per tenant |
| **Cost Optimization** | Reserved instances for 80% of baseline traffic; spot instances for 20% spike capacity; auto-scale down during off-peak |
| **Regional Redundancy** | 3 regions; 36 nodes per region = 114 nodes total; costs ~$2M/year (compute-heavy) |
| **Disaster Recovery** | RPO (Recovery Point Objective): 1 minute (Kafka replication); RTO: 5 minutes (standby activation) |

### Deployment Patterns

**Blue-Green Deployment** (LB version upgrade):
1. Deploy new version to "green" cluster (parallel to "blue")
2. Health checks on green cluster
3. Route 1% traffic to green for canary
4. Monitor error rate; if <0.1%, increase to 10%
5. Continue ramping to 100% over 10 minutes
6. Drain blue cluster; mark as spare

**Rolling Restart** (Config change):
1. Remove node 1 from pool (drain connections)
2. Restart node 1; reattach to pool
3. Repeat for nodes 2-36, one per minute
4. Total time: 36 minutes for full restart

**Regional Failover** (Entire region down):
1. Detect all LB nodes in region unhealthy
2. Wait 60 seconds (prevent flapping)
3. Activate DNS failover to another region
4. Traffic automatically reroutes
5. Backend pools in failover region absorb traffic (auto-scale if needed)
6. Investigate root cause
7. Once recovered, gradually migrate traffic back (gradual to avoid re-congestion)

