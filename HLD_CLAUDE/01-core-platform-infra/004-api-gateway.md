# System Design: API Gateway

## 1. Functional Requirements

### Core Responsibilities
- **Request Routing**: Route incoming API requests to appropriate upstream services deterministically based on host, path, method, and version
- **Authentication & Authorization**: Validate credentials at edge; enforce fine-grained policies (tenant, consumer, scope) at service layer
- **Rate Limiting & Throttling**: Apply token bucket or sliding window counters per tenant/consumer/API key/route; return explicit Retry-After headers
- **Traffic Shaping**: Enforce per-tenant quotas, request size limits, concurrent connection limits; implement backpressure handling
- **Canary Deployment**: Route weighted traffic to canary versions; automatic rollback on error/latency/SLO burn
- **Request Versioning**: Support multiple API versions simultaneously; graceful deprecation with client migration windows
- **Observability & Monitoring**: Log all requests with correlation IDs; emit structured metrics (latency, error rate, tenant metrics)
- **API Composition**: Support request aggregation, field masking, response filtering based on consumer permissions

### Request Processing Pipeline
1. Client connects → TLS termination at edge
2. Authentication extraction (API key, OAuth token, mTLS cert)
3. Rate limit check (fast, O(1) decision from local cache)
4. Authorization policy evaluation (tenant scopes, consumer quotas)
5. Request routing (deterministic based on URL + version)
6. Canary traffic split (if active deployment)
7. Upstream service call with timeout + retry logic
8. Response processing (header injection, field masking)
9. Event emission (async, non-blocking)
10. Response sent to client

### Non-Client Features
- **Admin API**: CRUD for routes, consumers, policies, canary deployments (separate control plane)
- **Metrics Export**: Prometheus-compatible metrics endpoint
- **Health Endpoints**: `/health` (process alive), `/ready` (dependencies OK)
- **Configuration Hot-reload**: Pull policy changes without restart; versioned policy blobs

---

## 2. Non-Functional Requirements

### Scale & Performance
- **Request Volume**: 50K QPS average, 250K QPS peak (5x burst multiplier)
- **Latency Targets**:
  - p50: <30ms (hot path, cache hits)
  - p95: <100ms
  - p99: <150ms (includes slow upstream, retries)
- **Availability**: 99.99% (52 minutes downtime/year)
- **Throughput**: 100K concurrent connections (keep-alive)

### Consistency & Durability
- **Policy Consistency**: Strong consistency for policy writes (PostgreSQL); eventual consistency for cache propagation (TTL <5s)
- **Idempotency**: All state mutations idempotent using client-provided idempotency keys (UUID)
- **Event Durability**: Events persisted to Kafka before returning response (transactional outbox)
- **Configuration Freshness**: Policy changes visible within 5 seconds globally

### Resilience
- **Upstream Failures**: Circuit breaker (fail open after 50 consecutive errors in 30s window); fallback to stale cache
- **Dependency Degradation**: If policy service unavailable, use cached policies (deny by default); metrics pipeline non-blocking
- **Regional Failover**: Multi-AZ deployment; load balancer failover <1s

### Security & Compliance
- **Authentication**: OAuth2.0, API keys, mTLS; no plaintext credentials in logs/metrics
- **Authorization**: Attribute-based access control (ABAC) per tenant
- **Encryption**: TLS 1.3 for transit; encryption at rest for sensitive config (env vars via Vault)
- **Audit**: Immutable audit log of all policy changes + data access; searchable by user/IP/resource
- **Compliance**: GDPR data retention (delete consumer data after 30 days); SOC 2 controls

---

## 3. Capacity Estimation

### Traffic Modeling
- **DAU**: 10M daily active users
- **Peak Concurrency**: 250K QPS × 0.2s avg latency = 50K concurrent requests (connections: 50K × 5 keep-alive multiplier = 250K)
- **Request Rate Distribution**: 80% GET (cacheable), 20% POST/PATCH (state changes)
- **Payload Sizes**: 
  - Average request: 2 KB
  - Average response: 8 KB
  - P99 request: 100 KB (file uploads handled separately)

### Storage Estimation (Annual)
- **Route Configurations**: 10K routes × 5 KB = 50 MB
- **Consumer Policies**: 1M consumers × 10 KB policy blob = 10 GB
- **Audit Log**: 250K QPS × 365 days × 86400 sec × 1 KB per log entry = ~8 PB (with 90-day retention: 2 TB hot, 6 TB cold)
- **Metrics**: Prometheus retention 15 days, ClickHouse retention 90 days: ~500 GB

### Network Bandwidth (Peak)
- **Ingress**: 250K QPS × 2 KB avg = 500 MB/s
- **Egress**: 250K QPS × 8 KB avg = 2 GB/s
- **Cross-AZ replication**: +100 MB/s per AZ (3 AZs)
- **CDN**: Cache 80% of GET responses; reduce origin egress to ~400 MB/s

### Cache Memory
- **Redis Cluster (hot-path counters)**: 
  - Rate limit state: 1M consumers × 100 bytes = 100 MB
  - Config cache: 1M routes × 5 KB = 5 GB
  - Total: ~6 GB with replication = 18 GB (3 replicas)
- **Local in-process cache** (L1): ~1 GB per gateway instance for recent route configs

### Compute Resources (Kubernetes)
- **Gateway Pods**: 50 pods (4 CPU, 8 GB memory each; 10:1 overcommit) = 200 CPU, 400 GB
- **Data-plane Service**: 30 pods (8 CPU, 16 GB)
- **Control-plane API**: 10 pods (2 CPU, 4 GB) 
- **Total**: ~400 CPU cores, ~800 GB RAM across 3 AZs

---

## 4. Data Modeling

### Core Tables (PostgreSQL)

**routes** (source of truth)
```
id (UUID PK)
tenant_id (UUID FK)
path_pattern (varchar) — regex or exact match
http_method (enum: GET, POST, etc)
upstream_url (varchar)
auth_policy_id (UUID FK) — reference to policies table
rate_policy_id (UUID FK)
canary_deployment_id (UUID FK, nullable)
api_version (int) — version of this route definition
state (enum: CREATED, ACTIVE, PAUSED, ARCHIVED, DELETED)
created_at (timestamp)
updated_at (timestamp)
deleted_at (timestamp, nullable) — soft delete

INDEXES:
- (tenant_id, path_pattern, http_method) — routing lookup
- (state, updated_at) — for change detection
- (created_at) — for audit trails
```

**consumers**
```
id (UUID PK)
tenant_id (UUID FK)
name (varchar)
quota_requests_per_minute (int)
quota_requests_per_day (long)
enabled (bool)
metadata (jsonb) — custom tenant attributes
created_at, updated_at, deleted_at
```

**api_keys**
```
id (UUID PK)
consumer_id (UUID FK)
key_hash (varchar, unique) — bcrypt hash of key
expires_at (timestamp)
scopes (text[]) — array of scope strings
created_at
```

**policies** (immutable, versioned)
```
id (UUID PK)
tenant_id (UUID FK)
policy_type (enum: auth, rate_limit, canary)
version (int)
body (jsonb) — policy definition (algorithm, thresholds, rules)
active (bool)
created_at

INDEXES:
- (tenant_id, policy_type, active) — for policy lookup
```

**canary_deployments**
```
id (UUID PK)
route_id (UUID FK)
upstream_canary_url (varchar)
canary_weight_percent (int, 0-100)
state (enum: RUNNING, PAUSED, ROLLED_BACK, COMPLETED)
error_rate_threshold (float, %) — rollback if exceeded
latency_p99_threshold_ms (int) — rollback if p99 > threshold
created_at, completed_at
```

**audit_log** (immutable append-only)
```
id (UUID PK)
timestamp (timestamp)
user_id (UUID)
action (varchar) — 'create_route', 'update_policy', etc
resource_id (UUID)
old_value (jsonb)
new_value (jsonb)
ip_address (inet)
request_id (UUID)

INDEXES:
- (timestamp, resource_id) — time-range audit queries
- (user_id, timestamp) — user activity queries
```

### CAP Theorem Analysis
- **Consistency Focus**: Policy/config writes require strong consistency (PostgreSQL); rate limit counters use eventual consistency (Redis)
- **Partition Handling**: If control plane unavailable, gateway uses cached policies (AP mode); new routes not deployed until service restores
- **Regional Choice**: Within-AZ: CP (strong). Cross-AZ: AP (eventual, TTL <5s)

### Sharding Strategy
- **Shard Key**: `tenant_id` — all routes/policies for tenant colocated
- **Shard Manager**: Consul-based tenant → shard mapping; watch-based updates
- **Rebalancing**: Lazy — when adding shard, gradually shift ~10% of tenants/week
- **Hot Tenant Mitigation**: Replicate top 1% tenants across 3 shards; load-balance client requests

---

## 5. High-Level Design

### Component Architecture
```
┌─────────────────────────────────────────────────────────────┐
│  Client (Web, Mobile, SDK)                                  │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼────────────────────────────────┐
│  Edge Layer (CloudFront / Akamai)                           │
│  - TLS termination & cert pinning                           │
│  - DDoS mitigation (rate limit IPs)                         │
│  - Geographic routing (nearest PoP)                         │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  API Gateway (Kubernetes, 3 AZs)                            │
│  - Authentication (verify API key / OAuth token)            │
│  - Rate limit decision (Redis lookup)                       │
│  - Route lookup (in-process LRU cache)                      │
│  - Canary traffic split (weighted routing)                  │
│  - Request transformation (add correlation ID, headers)     │
└──┬──────────────────────────┬──────────────────────────────┬┘
   │                          │                              │
   ▼                          ▼                              ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Auth Service │    │ Business Logic   │    │ Analytics Service│
│ (mTLS, JWT)  │    │ (Orders, Users)  │    │ (Track events)   │
└──────────────┘    └──────────────────┘    └──────────────────┘
   │                          │                              │
   └──────────────┬───────────┴──────────────┬───────────────┘
                  │                          │
        ┌─────────▼──────────┐      ┌────────▼──────────┐
        │  PostgreSQL (Hot)  │      │ Kafka (Events)    │
        │  - Routes config   │      │ - Policy changes  │
        │  - Consumers       │      │ - Rate limit logs │
        │  - Audit log       │      │ - Metrics events  │
        └────────────────────┘      └────────┬──────────┘
                                             │
                                   ┌─────────▼──────────┐
                                   │ ClickHouse (Cold)  │
                                   │ - Analytics (30d)  │
                                   │ - Audit trails     │
                                   └────────────────────┘

        ┌──────────────────────────────────────┐
        │  Redis Cluster (Hot Cache)           │
        │  - Rate limit counters (~6GB)        │
        │  - Config cache (versioned, TTL 5m)  │
        │  - Session cache (OAuth tokens)      │
        └──────────────────────────────────────┘
```

### Control Plane (Admin API)
```
┌─ POST /admin/routes
├─ PUT /admin/routes/{id}
├─ DELETE /admin/routes/{id}
├─ POST /admin/canary-deployments
├─ PATCH /admin/canary-deployments/{id}/rollback
├─ GET /admin/policies
└─ POST /admin/policies
```

### Async Event Pipeline
- Events emitted to Kafka (transactional outbox in PostgreSQL write transaction)
- Consumers: Metrics aggregator, audit indexer, change notification service, analytics warehouse

---

## 6. Low-Level Design

### Public API (REST)

**Authentication Verification** (called by gateway, not client-facing)
```
POST /internal/auth/verify
{
  "api_key": "sk_live_...",
  "scopes_required": ["read:orders", "write:payments"],
  "tenant_hint": "acme-corp"
}

Response 200:
{
  "consumer_id": "uuid",
  "tenant_id": "uuid",
  "scopes": ["read:orders", "write:payments"],
  "quota_remaining": 4950,
  "cache_ttl_seconds": 300
}

Response 401: { "error": "invalid_key" }
Response 429: { "error": "quota_exceeded", "retry_after_seconds": 45 }
```

**Rate Limit Decision**
```
POST /internal/rate-limit/check
{
  "consumer_id": "uuid",
  "policy_id": "uuid",
  "request_count": 1
}

Response 200:
{
  "allowed": true,
  "remaining": 4999,
  "reset_at": "2026-05-29T12:00:00Z"
}

Response 429:
{
  "allowed": false,
  "retry_after_seconds": 45,
  "reset_at": "2026-05-29T12:00:00Z"
}
```

**Route Lookup** (cached in-process)
```
POST /internal/routes/resolve
{
  "tenant_id": "uuid",
  "method": "GET",
  "path": "/api/users/123",
  "version": 2
}

Response 200:
{
  "route_id": "uuid",
  "upstream_url": "http://users-service:8080",
  "auth_policy": {...},
  "rate_policy": {...},
  "canary": {
    "weight_percent": 10,
    "upstream_url": "http://users-service-canary:8080"
  }
}
```

### Internal Service API (gRPC, low-latency)

**RateLimiter Service**
```protobuf
service RateLimiter {
  rpc CheckAndAdjust(CheckRequest) returns (CheckResponse) {}
  rpc GetQuota(QuotaRequest) returns (QuotaResponse) {}
  rpc ResetCounter(ResetRequest) returns (google.protobuf.Empty) {}
}

message CheckRequest {
  string consumer_id = 1;
  string policy_id = 2;
  int32 request_count = 3;
  string idempotency_key = 4;
}

message CheckResponse {
  bool allowed = 1;
  int32 remaining = 2;
  int64 reset_at_unix = 3;
  int32 retry_after_seconds = 4;
}
```

### Design Patterns Applied
1. **Circuit Breaker** (upstream failures): Fail open after 50 errors in 30s; gradual recovery with test traffic
2. **Bulkhead** (resource isolation): Separate thread pools per tenant, separate connection pools
3. **Cache-Aside**: Rate limit checks read from Redis; misses fallback to PostgreSQL + write-back
4. **Transactional Outbox**: Write route change + outbox event in single PostgreSQL transaction; async Kafka producer reads outbox
5. **Idempotency**: Store idempotency key + response in Redis (TTL 24h); duplicate requests return cached response
6. **Versioned State Machine**: Routes: CREATED → ACTIVE → PAUSED → ARCHIVED → DELETED (no direct transitions except PAUSED ↔ ACTIVE)

---

## 7. Architecture Components

### API Gateway Pod (Stateless)
- **TLS Listener**: Accept HTTPS, extract SNI for certificate selection
- **Authentication Module**: Parse API key from header; verify signature; check revocation list (cached)
- **Rate Limiter**: O(1) Redis lookup; local sliding window backup if Redis unavailable
- **Router**: In-process LRU cache (10K routes, 5 MB); O(1) hash lookup + regex match for dynamic segments
- **Canary Splitter**: Hash(consumer_id) % 100 < canary_weight → route to canary upstream
- **Upstream Client**: HTTP/1.1 connection pooling; TCP_KEEPALIVE; timeouts (connect 2s, read 30s, write 5s)
- **Metrics Emitter**: Non-blocking async to local Prometheus push gateway (or OpenTelemetry collector)
- **Event Publisher**: Batches events to Kafka (max batch 10 events, flush every 100ms)

**Pod Spec**:
- CPU: 4 cores, memory 8 GB
- Replicas: 50 (auto-scale: 20-100 on 70% CPU usage)
- Ready probe: /ready endpoint returns 200 after dependencies connected
- Liveness probe: /health endpoint (always 200 if process alive)

### Control-Plane API Pod
- REST server for CRUD operations (routes, consumers, policies)
- PostgreSQL client with connection pooling (pool size: 50)
- Policy compiler: Parse policy DSL, type-check, generate optimized bytecode
- Change broadcaster: On policy update, publish versioned event to Kafka; watch-based cache invalidation

**Pod Spec**:
- CPU: 2 cores, memory 4 GB
- Replicas: 10 (scale-down during off-hours)

### Redis Cluster (Data Layer)
- **Topology**: 6 nodes (3 primary, 3 replica) across 3 AZs; each node 2 GB memory
- **Key patterns**:
  - `rate_limit:${consumer_id}` → JSON counter state (TTL 1 hour)
  - `route_config:v${version}` → Serialized route object (TTL 5 min)
  - `api_key_hash:${hash}` → Consumer mapping (TTL 24h)
- **Eviction**: LRU; remove oldest keys if memory threshold (90%) hit

### PostgreSQL Database
- **Topology**: 1 primary + 2 synchronous replicas (cross-AZ)
- **Backup**: Continuous WAL archival to S3; point-in-time recovery to any second in last 30 days
- **Failover**: Patroni-managed; promote replica if primary unhealthy (manual approval required)
- **Connection Pooling**: PgBouncer (pool size: 200); separate pool per service (read-only vs read-write)

### Kafka Cluster
- **Topics**:
  - `routes.v1`: Schema = RouteCreated | RouteUpdated | RouteDeleted (retention: 7 days)
  - `rate_limits.v1`: Retention 24h, partitioned by consumer_id
  - `events.v1`: All events, retention 30 days
- **Partitioning**: 48 partitions per topic (load balance across 3 AZs); replication factor 3
- **Consumer Groups**: 
  - `metrics-aggregator` (offset auto-committed every 10s)
  - `audit-indexer` (commit on successful index write)
  - `change-notifier` (exactly-once semantics via transactional writes)

### ClickHouse (Analytics)
- **MergeTree Engine**: Partitioned by date; allows fast time-range scans
- **Tables**:
  - `rate_limit_events_daily`: Aggregated events (insert rate: 5K inserts/sec)
  - `audit_log_daily`: Raw audit trail (retention: 90 days)
- **Replication**: 2 replicas per AZ; Keeper coordination for consensus
- **Query Access**: Read-only credentials in application; no root access

---

## 8. Deep Dive: Each Component

### Component 1: Authentication Layer
**Challenge**: Verify credentials fast (O(1) latency) while supporting revocation (cache invalidation).

**Solution**:
1. API key arrives in `Authorization: Bearer sk_live_...` header
2. Hash key → Redis lookup (TTL 24h): `api_key_hash:${blake3_hash} → consumer_id`
3. If miss, query PostgreSQL `api_keys` table; cache result
4. Verify expiration time; if expired, respond 401 (don't cache)
5. For OAuth: Exchange token with OAuth provider (cached, TTL 15 min); fallback to local in-memory JWK cache

**Failure Modes**:
- Redis unavailable: Query PostgreSQL directly (latency +30ms)
- OAuth provider down: Use cached tokens up to max age
- Key revoked but cached: Max staleness 24 hours; users can clear cache manually via admin API

### Component 2: Rate Limiter
**Challenge**: Apply per-tenant quotas fairly; survive brief Redis downtime.

**Algorithm**: Token Bucket with distributed state
1. Per-consumer counter in Redis: `{ tokens: N, last_refill_at: T }`
2. On request: 
   - If tokens > 0: decrement, allow
   - Else: check refill (if time passed since last_refill, add `(now - last_refill) / refill_rate` tokens)
   - If tokens still 0: deny + Retry-After header
3. Local backup: If Redis unavailable, use local in-process sliding-window counter (last 60 seconds); overly permissive (fallback)

**Optimization**:
- Batch updates: Collect 100 requests, then single Redis INCR
- Pipelining: Send 10 Redis commands in one batch → 10x throughput

### Component 3: Route Lookup & Canary Routing
**Challenge**: Route millions of requests fast; support versioned routes and gradual canary traffic shifts.

**Solution**:
1. In-process LRU cache (10K routes, updated every 5 seconds from Redis)
2. Hash lookup: `(tenant_id, method, path) → RouteConfig`
3. For dynamic paths (`/users/{id}`), store regex; compile to finite automaton
4. Canary routing: 
   - Compute hash(consumer_id) % 100
   - If hash < canary_weight_percent: route to canary upstream
   - Track success/error rates independently for canary vs stable
   - Auto-rollback if canary error_rate > threshold for 2 consecutive 1-minute windows

### Component 4: Observability Integration
**Challenge**: Emit metrics without blocking requests; aggregate before sending.

**Solution**:
1. Per-request: Capture latency, status, tenant_id, upstream_url
2. Batch async (100 events or 100ms): Send to local Prometheus push gateway
3. Metrics exported:
   - `gateway_requests_total{tenant, method, status}` (counter)
   - `gateway_request_latency_seconds{tenant, upstream}` (histogram: p50, p95, p99)
   - `gateway_upstream_errors_total{upstream, error_type}` (counter)
   - `gateway_rate_limit_rejections_total{tenant, policy_id}` (counter)
4. Correlation ID: Generate UUID at gateway; inject into upstream requests; log in every service

---

## 9. Optimization Strategies

### Caching Strategy (Multi-Layer)

**L1 Cache** (In-Process, Gateway Pod)
- Route configs: LRU 10K entries; invalidate on Kafka change events
- Policy blobs: Only active policies; evict on version increment
- TTL: 5 minutes hard expiry + watch-based invalidation

**L2 Cache** (Redis)
- Hot routes (top 1000): JSON serialized; TTL 5 min
- Rate limit state: Live counters; TTL 1 hour (reset on overflow)
- Session/auth: API key hash → consumer mapping; TTL 24h

**L3 Cache** (CDN)
- Cacheable GET responses (80% of traffic): Cache for 5 min at edge; include ETag for revalidation
- Public routes (docs, assets): Cache for 1 day
- Invalidate via Cache-Control: no-cache on config changes

### Queue Patterns

**Rate Limit Backpressure**: 
- If upstream latency spikes, queue requests in memory (max 1000); return 503 if queue full
- Shed lowest-priority traffic (batch jobs) before dropping interactive users

**Event Publishing**:
- Local in-memory queue (max 10K events); batch to Kafka every 100ms or 1K events
- If Kafka unavailable, queue to disk (fallback durability); resume on recovery

### Database Optimization

**Write Path Optimization**:
- Route creation: Single PostgreSQL insert → transactional outbox write → commit
- Async: Kafka consumer publishes event; all services watch Kafka (avoid database polling)
- Batch updates: Policy compiler generates bytecode; publish once to Kafka (not per-route)

**Read Path Optimization**:
- Route lookup: In-process cache (O(1)); no database hit
- Config fetch on startup: Bulk load from `SELECT ... WHERE state='ACTIVE'` (avoid N+1 queries)
- Pagination for audit logs: Cursor-based (seek to timestamp); never use OFFSET

**Index Strategy**:
- (tenant_id, path_pattern, http_method): Used 100% of time for route lookups
- (state, updated_at): Used for change detection (Kafka consumers poll)
- (created_at): For audit queries and data lifecycle operations

### Async Patterns

**Transactional Outbox**:
```sql
BEGIN;
  INSERT INTO routes (...) VALUES (...);
  INSERT INTO outbox (event_type, payload) VALUES ('route.created.v1', ...);
COMMIT;

-- Async consumer polls outbox, publishes to Kafka, deletes row on success
```

**Change Data Capture (CDC)**:
- PostgreSQL → Kafka: Debezium captures WAL changes; consumers receive real-time policy updates
- Faster than polling (TTL 5 min resets on each poll)

---

## 10. Observability

### Service Level Indicators (SLIs)

**Availability**: % of requests returning non-5xx response
- Target: 99.99% (52 min downtime/year)
- Measured per tenant, per endpoint, per AZ
- Exclude intentional rejections (401, 403, 429)

**Latency**: Request duration (p50, p95, p99)
- p50: <30ms (cache hits, local zone)
- p99: <150ms (includes slow upstreams, retries, cross-AZ)
- Measured per tenant, upstream service

**Correctness**: % of requests routed to intended upstream
- Validate 1% of traffic post-routing (sample, verify matches intended route)
- Alert if correctness drops below 99.95%

**Freshness**: Policy changes visible to all gateway instances
- Sample: Update policy; measure time until 100% of gateways return new behavior
- Target: <5 seconds (p95)

### Service Level Objectives (SLOs)

**Availability SLO**: 99.99% (per day, rolling 30-day window)
- Error budget: 52 minutes / month
- Alert if burn rate > 50 minutes consumed in < 1 hour

**Latency SLO**: p99 < 150ms (per service, rolling hour)
- Alert if p99 exceeds 150ms for 5 consecutive minutes

**Correctness SLO**: 100% (zero tolerance for routing errors)
- Alert immediately on any correctness failure

### Metrics & Dashboards

**Prometheus Metrics**
```
gateway_requests_total{tenant, method, status, upstream} 
gateway_request_latency_seconds{tenant, endpoint, percentile}
gateway_rate_limit_hits_total{tenant, policy_id}
gateway_canary_traffic_routed_total{route_id, canary_id}
gateway_upstream_errors_total{upstream, error_type}
gateway_cache_hits_total{cache_layer} — L1, L2, L3
gateway_kafka_lag_bytes{consumer_group}
redis_memory_usage_bytes{instance}
postgres_connections_active{pool_name}
```

**Grafana Dashboards**
- **System Overview**: QPS, error rate, p99 latency, availability per AZ
- **Per-Tenant Dashboard**: Requests, errors, rate-limit rejections, quota remaining
- **Canary Deployment**: Traffic split, error rate comparison, p99 latency delta
- **Operational**: Pod CPU/memory, database connections, cache hit rates, Kafka lag

### Alerting Rules

```
ALERT GatewayHighErrorRate
  IF rate(gateway_requests_total{status=~"5.."}[5m]) > 0.01
  FOR 1m
  → Page on-call (P1, critical)

ALERT GatewayHighLatency
  IF histogram_quantile(0.99, gateway_request_latency_seconds) > 0.15
  FOR 5m
  → Send to Slack #alerts (P2)

ALERT RateLimiterCacheMiss
  IF rate(gateway_cache_hits_total{cache_layer="L2"}[5m]) / rate(gateway_cache_total[5m]) < 0.95
  FOR 10m
  → Page on-call (P2)

ALERT KafkaConsumerLag
  IF kafka_lag_bytes{consumer_group="metrics-aggregator"} > 1000000000
  FOR 10m
  → Slack #alerts (P3)
```

### Structured Logging

```json
{
  "timestamp": "2026-05-29T12:34:56.123Z",
  "level": "INFO",
  "service": "gateway",
  "request_id": "req_abc123",
  "correlation_id": "corr_xyz789",
  "tenant_id": "acme-corp",
  "consumer_id": "consumer_123",
  "method": "GET",
  "path": "/api/users/123",
  "upstream_service": "users-service",
  "status_code": 200,
  "latency_ms": 42,
  "rate_limit_remaining": 4950,
  "canary_routed": false,
  "upstream_error": null
}
```

---

## 11. Considerations & Assumptions

### Trade-offs

**Strong vs Eventual Consistency**
- Policy writes: Strong (PostgreSQL) to avoid inconsistent state across tenants
- Rate limit counters: Eventual (Redis) to achieve <5ms latency; acceptable to occasionally allow burst over quota

**Latency vs Durability**
- Metrics: Async fire-and-forget (non-blocking); tolerate occasional loss (rebuild from Prometheus scrape)
- Events: Sync write to Kafka inside transaction (guarantee delivery); block request if Kafka unavailable (fail-safe)

**Complexity vs Feature Coverage**
- Versioned policies: Complex (requires state machine, multi-version caching) but enables zero-downtime updates
- Canary deployments: Complex state tracking but eliminates manual rollback decisions

### Failure Modes & Mitigations

| Failure | Impact | Mitigation |
|---------|--------|-----------|
| Redis cluster down | Requests allowed without rate limit | Fall back to PostgreSQL + local sliding-window |
| PostgreSQL primary down | New routes can't deploy; config reads fail | Use replicas for read (accept replication lag); fail-open on auth |
| Kafka unavailable | Events lost; dashboards won't update | Queue events locally; retry on recovery; fallback alerting via metrics |
| Canary version crashes | 10% of traffic errors | Auto-rollback after 50 consecutive errors; alert on-call |
| TLS cert expiration | HTTPS connections fail | Cert manager auto-renewal; alert 14 days before expiry |
| Upstream service timeout | Request blocked after 30s timeout | Circuit breaker; return cached response if available |

### Security & Compliance

**Authentication**:
- Require API key expiration (max 1 year)
- Rotate keys quarterly; old keys disabled after 2-week grace period
- Credential never logged; only hashes in audit trail

**Authorization**:
- All mutations require admin role (scoped to own tenant)
- Fine-grained scopes: `read:routes`, `write:policies`, `admin:canary`
- Deny by default; allowlist scopes

**Encryption**:
- Transit: TLS 1.3 mandatory; certificate pinning for critical endpoints
- At-rest: PostgreSQL encryption via pgcrypto; Redis encrypted (Vault-managed keys)
- Audit logs: Immutable; append-only access

**Data Retention**:
- Consumer data: Delete after 30 days (GDPR right to be forgotten)
- Audit logs: Retain 90 days (compliance), then archive to cold storage (S3 Glacier)
- Rate limit logs: Delete after 24 hours (not PII, only counters)

**Compliance**:
- SOC 2: Annual audit; all write access logged + reviewed monthly
- GDPR: Data residency in EU regions; cross-border transfer encrypted + documented
- HIPAA: Data encryption, access controls, audit trails for healthcare tenants

### Deployment & Operations

**Blue/Green Releases**:
- Deploy new gateway version to 5% of instances → monitor error rate/latency for 10 min
- If stable, roll out to 100% over 30 min (10% increments, 5 min between)
- Auto-rollback if error rate > 1% or p99 > 200ms

**Feature Flags**:
- New algorithm (different rate limit strategy): Flag `new_rate_limiter_enabled=false`
- Gradual rollout: false → 1% → 10% → 100% (hold 24h between stages)
- Emergency kill switch: `kill_switch_rate_limiter=true` reverts to backup algorithm

**Configuration Hot-Reload**:
- Policy updates: No restart required; gRPC watch-based update to cache
- Route changes: Published to Kafka; all instances reload within 5 seconds

### Cost Modeling

**Compute** (annual): 
- 50 gateway pods × 12 months × 730 hours × (4 CPU × $0.04/CPU-hour + 8 GB × $0.005/GB-hour) = ~$700K

**Storage** (annual):
- PostgreSQL: 100 GB × $0.10/GB-month × 12 = $120K
- ClickHouse (analytics): 500 GB × $0.05/GB-month × 12 = $30K

**Network** (annual, egress):
- 400 MB/s average × 86400 sec × 365 days × $0.12/GB = ~$1.3M (AWS egress costs)

**Cache** (Redis, annual):
- 18 GB (with replicas) × $0.30/GB-hour × 730 = ~$4K

**Total Annual**: ~$2.15M (85% network, 33% compute)

### Assumptions

1. Upstream services respond within 30 seconds; else timeout and retry
2. 20% of traffic is rate-limited; 80% passes through
3. Rate limit policies don't change more than 1K times/day
4. Tenant-to-shard mapping stable; reshuffling <1% of tenants/month
5. PostgreSQL replication latency <100ms across AZs
6. Canary traffic split <20% (production stability prioritized)

