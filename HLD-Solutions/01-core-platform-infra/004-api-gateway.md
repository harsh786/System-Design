# Design an API Gateway

## 1. Functional Requirements

- **Request Routing**: Route incoming API requests to appropriate backend microservices based on URL path, HTTP method, headers, and query parameters
- **Authentication & Authorization**: Validate JWT tokens, API keys, OAuth2 tokens; enforce RBAC/ABAC policies before forwarding requests
- **Rate Limiting & Throttling**: Enforce per-user, per-tenant, per-IP, per-API-key rate limits using token bucket / sliding window algorithms
- **Request/Response Transformation**: Modify headers, body, query params; protocol translation (REST to gRPC, HTTP/1.1 to HTTP/2)
- **Load Balancing**: Distribute traffic across backend instances using round-robin, weighted, least-connections, or consistent hashing
- **API Versioning**: Support multiple API versions simultaneously with version routing (URL path, header, query param)
- **Canary & Blue-Green Deployments**: Split traffic between versions with weighted routing and automatic rollback on SLO violations
- **Circuit Breaking**: Detect unhealthy backends and stop forwarding traffic; half-open probes to detect recovery
- **Request Validation**: Validate request schema (JSON Schema, OpenAPI spec) before forwarding to backends
- **Caching**: Cache GET responses at the gateway level with configurable TTL and cache invalidation
- **SSL/TLS Termination**: Terminate TLS at the gateway; re-encrypt for backend communication (mTLS)
- **Logging & Audit Trail**: Log every request/response with correlation IDs for tracing
- **API Key Management**: Issue, revoke, rotate API keys; associate with quotas and scopes
- **IP Whitelisting/Blacklisting**: Allow or deny traffic from specific IP ranges
- **Request Deduplication**: Idempotency key support to prevent duplicate mutations
- **WebSocket & SSE Support**: Proxy long-lived connections to backend services
- **Admin APIs**: CRUD for routes, policies, rate limit configs, API keys

## 2. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| **Availability** | 99.99% (52.6 min downtime/year) — gateway is on critical path |
| **Latency** | p50 < 5ms overhead, p99 < 20ms overhead (gateway processing only) |
| **Throughput** | Handle 500K+ RPS per cluster |
| **Scalability** | Horizontal scaling with no single point of failure |
| **Consistency** | Rate limit counters: eventual (best-effort accuracy), Route config: strong consistency |
| **Durability** | Zero config loss; all route/policy changes persisted with audit |
| **Security** | Zero-trust: mTLS between services, encryption at rest, PCI-DSS compliant |
| **Fault Tolerance** | Graceful degradation: if rate limiter down, fail-open with alerts |
| **Observability** | Full distributed tracing, metrics, structured logging |
| **Deployment** | Zero-downtime deploys, canary rollouts for gateway itself |

## 3. Capacity Estimation

### Assumptions
| Dimension | Value |
|-----------|-------|
| DAU (Daily Active Users) | 50 million |
| MAU (Monthly Active Users) | 200 million |
| Avg API calls/user/day | 100 |
| Peak multiplier | 5x average |
| Average request size | 2 KB |
| Average response size | 5 KB |
| Number of registered APIs | 500 |
| Number of backend services | 200 |
| Number of tenants | 10,000 |

### QPS / RPS Calculation
```
Total daily requests = 50M × 100 = 5 billion/day
Average QPS = 5B / 86,400 = ~58,000 QPS
Peak QPS = 58,000 × 5 = 290,000 QPS
Write QPS (config changes) = ~100 QPS (route updates, key rotations)
```

### Storage Estimation
```
Route configs: 500 routes × 10 KB = 5 MB (negligible, fits in memory)
API Keys: 10M keys × 256 bytes = 2.5 GB
Rate limit counters: 50M users × 10 windows × 64 bytes = 32 GB (Redis cluster)
Access logs/day: 5B × 500 bytes = 2.5 TB/day
Audit logs/day: 100 config changes × 2 KB = 200 KB/day
```

### Network Bandwidth Estimation
```
Ingress: 290K RPS × 2 KB = 580 MB/s = 4.64 Gbps (peak)
Egress: 290K RPS × 5 KB = 1.45 GB/s = 11.6 Gbps (peak)
Total bandwidth needed: ~16 Gbps per cluster (peak)
Inter-service (gateway to backend): ~12 Gbps
```

### Infrastructure Sizing
```
Gateway nodes: 290K QPS / 10K QPS per node = 29 nodes (round to 36 for 20% headroom + rolling deploys)
Redis cluster for rate limiting: 6 nodes (3 master + 3 replica), 64 GB each
Config DB (PostgreSQL): 3 nodes (1 primary + 2 read replicas)
Log ingestion: Kafka cluster with 12 brokers
```

## 4. Data Modeling

### Database Choice Rationale
| Data | Store | Why |
|------|-------|-----|
| Route configurations | PostgreSQL | Strong consistency, ACID, complex queries |
| API keys & credentials | PostgreSQL + HashiCorp Vault | Encrypted at rest, rotation support |
| Rate limit counters | Redis Cluster | Sub-ms latency, atomic operations, TTL |
| Access logs | Kafka → ClickHouse | High-volume append, analytical queries |
| Cached responses | Redis / Local LRU | Sub-ms reads, TTL-based eviction |
| Circuit breaker state | In-memory + Redis | Local fast path + cluster-wide sync |
| Session/token cache | Redis | Shared state across gateway nodes |

### Schema Design

#### `routes` table (PostgreSQL)
```sql
CREATE TABLE routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    path_pattern VARCHAR(500) NOT NULL,        -- e.g., /v1/users/{id}
    http_methods TEXT[] NOT NULL,               -- e.g., {GET, POST}
    upstream_service_id UUID NOT NULL REFERENCES services(id),
    upstream_path VARCHAR(500),                 -- rewrite path
    strip_prefix BOOLEAN DEFAULT false,
    priority INT DEFAULT 0,                     -- higher = matched first
    version INT NOT NULL DEFAULT 1,
    auth_policy_id UUID REFERENCES auth_policies(id),
    rate_limit_policy_id UUID REFERENCES rate_limit_policies(id),
    transform_config JSONB,                    -- request/response transforms
    cache_config JSONB,                        -- TTL, vary headers
    circuit_breaker_config JSONB,
    canary_config JSONB,                       -- weight, header match
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID NOT NULL,
    UNIQUE(tenant_id, path_pattern, http_methods)
);

-- Indexes
CREATE INDEX idx_routes_tenant_enabled ON routes(tenant_id, enabled) WHERE enabled = true;
CREATE INDEX idx_routes_path_pattern ON routes USING gin(path_pattern gin_trgm_ops);
CREATE INDEX idx_routes_priority ON routes(priority DESC, created_at);
CREATE INDEX idx_routes_upstream ON routes(upstream_service_id);
```

#### `services` table (PostgreSQL)
```sql
CREATE TABLE services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    health_check_path VARCHAR(255) DEFAULT '/health',
    health_check_interval_ms INT DEFAULT 10000,
    timeout_ms INT DEFAULT 30000,
    retry_count INT DEFAULT 3,
    retry_backoff_ms INT DEFAULT 100,
    load_balance_strategy VARCHAR(50) DEFAULT 'round_robin',  -- round_robin, least_conn, consistent_hash
    max_connections INT DEFAULT 1000,
    tls_enabled BOOLEAN DEFAULT true,
    mtls_cert_ref VARCHAR(255),
    metadata JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_services_tenant ON services(tenant_id, enabled);
```

#### `api_keys` table (PostgreSQL)
```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    key_hash VARCHAR(64) NOT NULL UNIQUE,     -- SHA-256 of the key
    key_prefix VARCHAR(8) NOT NULL,           -- First 8 chars for identification
    name VARCHAR(255),
    scopes TEXT[],                            -- e.g., {read:users, write:orders}
    rate_limit_tier VARCHAR(50) DEFAULT 'standard',
    allowed_ips INET[],
    allowed_origins TEXT[],
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    request_count BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID NOT NULL
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash) WHERE revoked_at IS NULL;
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id, created_at DESC);
CREATE INDEX idx_api_keys_expiry ON api_keys(expires_at) WHERE expires_at IS NOT NULL AND revoked_at IS NULL;
```

#### `rate_limit_policies` table (PostgreSQL)
```sql
CREATE TABLE rate_limit_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    algorithm VARCHAR(50) NOT NULL,          -- token_bucket, sliding_window, fixed_window, leaky_bucket
    requests_per_second INT,
    requests_per_minute INT,
    requests_per_hour INT,
    requests_per_day INT,
    burst_size INT,
    scope VARCHAR(50) NOT NULL,              -- per_user, per_ip, per_api_key, per_tenant, global
    response_headers BOOLEAN DEFAULT true,   -- X-RateLimit-* headers
    retry_after BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rate_policies_tenant ON rate_limit_policies(tenant_id);
```

#### `auth_policies` table (PostgreSQL)
```sql
CREATE TABLE auth_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    auth_type VARCHAR(50) NOT NULL,          -- jwt, api_key, oauth2, mtls, basic
    jwt_issuer VARCHAR(500),
    jwt_audience VARCHAR(500),
    jwks_url VARCHAR(500),
    required_scopes TEXT[],
    required_roles TEXT[],
    allow_anonymous BOOLEAN DEFAULT false,
    cache_ttl_seconds INT DEFAULT 300,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `access_logs` table (ClickHouse)
```sql
CREATE TABLE access_logs (
    request_id UUID,
    timestamp DateTime64(3),
    tenant_id UUID,
    user_id Nullable(UUID),
    api_key_id Nullable(UUID),
    method LowCardinality(String),
    path String,
    route_id UUID,
    upstream_service String,
    status_code UInt16,
    request_size UInt32,
    response_size UInt32,
    latency_ms UInt32,
    gateway_latency_ms UInt16,
    upstream_latency_ms UInt32,
    client_ip IPv4,
    user_agent String,
    rate_limited Boolean DEFAULT false,
    cache_hit Boolean DEFAULT false,
    circuit_broken Boolean DEFAULT false,
    error_code Nullable(String),
    trace_id String,
    region LowCardinality(String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (tenant_id, timestamp, request_id)
TTL timestamp + INTERVAL 90 DAY;

-- Materialized views for real-time analytics
CREATE MATERIALIZED VIEW access_logs_per_minute
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMMDD(minute)
ORDER BY (tenant_id, route_id, minute, status_code)
AS SELECT
    tenant_id,
    route_id,
    toStartOfMinute(timestamp) AS minute,
    status_code,
    count() AS request_count,
    sum(latency_ms) AS total_latency,
    max(latency_ms) AS max_latency
FROM access_logs
GROUP BY tenant_id, route_id, minute, status_code;
```

#### Redis Data Structures (Rate Limiting)
```
# Sliding Window Counter
Key: rate:{tenant_id}:{user_id}:{window_start}
Type: HASH
Fields: count, first_request_ts
TTL: window_size * 2

# Token Bucket
Key: bucket:{tenant_id}:{api_key_id}
Type: HASH
Fields: tokens, last_refill_ts
TTL: 3600s

# Circuit Breaker State
Key: circuit:{service_id}:{instance_id}
Type: HASH
Fields: state(closed/open/half_open), failure_count, last_failure_ts, last_success_ts
TTL: 300s

# Route Config Cache
Key: routes:{tenant_id}:compiled
Type: STRING (serialized trie/radix tree)
TTL: 60s (short, strong consistency needed)
```

## 5. High-Level Design (HLD)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                              │
│   (Web Apps, Mobile Apps, IoT Devices, Partner APIs, Internal Services)          │
└──────────────────────────────────┬───────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DNS (Route 53 / CloudFlare)                               │
│   - Geo-based routing, Latency-based routing, Health checks, Failover           │
└──────────────────────────────────┬───────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CDN (CloudFront / Fastly)                                 │
│   - Static response caching, DDoS absorption, Edge compute (Lambda@Edge)        │
│   - TLS termination at edge, Geo-blocking, Bot detection                        │
└──────────────────────────────────┬───────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       WAF (AWS WAF / Cloudflare WAF)                              │
│   - SQL injection protection, XSS prevention, OWASP Top 10                      │
│   - IP reputation filtering, Geo-fencing, Request size limits                   │
│   - Custom rules, Bot management, Rate limiting (L7)                            │
└──────────────────────────────────┬───────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    NETWORK LOAD BALANCER (NLB - Layer 4)                          │
│   - TCP/TLS passthrough, Ultra-low latency, Static IPs                          │
│   - Cross-AZ distribution, Health checks                                        │
└──────────────────────────────────┬───────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY CLUSTER                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ Gateway  │ │ Gateway  │ │ Gateway  │ │ Gateway  │ │ Gateway  │  ...×36      │
│  │ Node 1   │ │ Node 2   │ │ Node 3   │ │ Node 4   │ │ Node N   │             │
│  │          │ │          │ │          │ │          │ │          │             │
│  │┌────────┐│ │┌────────┐│ │┌────────┐│ │┌────────┐│ │┌────────┐│             │
│  ││Plugin  ││ ││Plugin  ││ ││Plugin  ││ ││Plugin  ││ ││Plugin  ││             │
│  ││Chain   ││ ││Chain   ││ ││Chain   ││ ││Chain   ││ ││Chain   ││             │
│  │└────────┘│ │└────────┘│ │└────────┘│ │└────────┘│ │└────────┘│             │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘             │
└──────────────────────────────────┬───────────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Control Plane  │   │   Data Plane    │   │   Async Plane   │
│                 │   │   (Hot Path)    │   │                 │
│ • Config CRUD   │   │ • Route match   │   │ • Log shipping  │
│ • Policy mgmt   │   │ • Auth verify   │   │ • Analytics     │
│ • Key rotation  │   │ • Rate limit    │   │ • Alerting      │
│ • Health checks │   │ • Transform     │   │ • Audit trail   │
│ • Canary mgmt   │   │ • Proxy request │   │ • Reconcile     │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                      │
         ▼                     ▼                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          DATA STORES                                          │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ PostgreSQL   │  │ Redis Cluster│  │    Kafka     │  │  ClickHouse  │   │
│  │ (Config DB)  │  │ (Rate Limit) │  │ (Event Log)  │  │ (Analytics)  │   │
│  │              │  │              │  │              │  │              │   │
│  │ • Routes     │  │ • Counters   │  │ • Access logs│  │ • Dashboards │   │
│  │ • Policies   │  │ • Token cache│  │ • Audit evts │  │ • Reports    │   │
│  │ • API keys   │  │ • Circuit brk│  │ • Config chg │  │ • Anomalies  │   │
│  │ • Tenants    │  │ • Session    │  │ • Alerts     │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐                                        │
│  │ Vault/KMS    │  │ S3/Object    │                                        │
│  │ (Secrets)    │  │ Storage      │                                        │
│  │              │  │              │                                        │
│  │ • TLS certs  │  │ • Log archive│                                        │
│  │ • Signing key│  │ • Backups    │                                        │
│  │ • Enc keys   │  │ • Exports    │                                        │
│  └──────────────┘  └──────────────┘                                        │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      BACKEND MICROSERVICES                                     │
│                                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │ User    │  │ Order   │  │ Payment │  │ Search  │  │ Notif.  │  ...     │
│  │ Service │  │ Service │  │ Service │  │ Service │  │ Service │         │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Gateway Node Internal Architecture (Plugin Chain Pattern)

```
┌────────────────────────────────────────────────────────────────┐
│                     GATEWAY NODE                                │
│                                                                │
│  Incoming Request                                              │
│       │                                                        │
│       ▼                                                        │
│  ┌──────────────────────────────────────────────┐             │
│  │         REQUEST PLUGIN CHAIN                   │             │
│  │                                                │             │
│  │  1. IP Filter Plugin                          │             │
│  │  2. TLS/mTLS Verification Plugin              │             │
│  │  3. Request ID & Trace Context Plugin         │             │
│  │  4. Rate Limit Plugin (pre-auth)              │             │
│  │  5. Authentication Plugin (JWT/API Key)       │             │
│  │  6. Authorization Plugin (RBAC/ABAC)          │             │
│  │  7. Rate Limit Plugin (post-auth, per-user)   │             │
│  │  8. Request Validation Plugin (schema)        │             │
│  │  9. Request Transform Plugin                  │             │
│  │  10. Cache Lookup Plugin                      │             │
│  │  11. Circuit Breaker Check Plugin             │             │
│  │  12. Load Balancer Plugin                     │             │
│  │  13. Retry Plugin                             │             │
│  └──────────────────────┬───────────────────────┘             │
│                         │                                      │
│                         ▼                                      │
│  ┌──────────────────────────────────────────────┐             │
│  │         UPSTREAM PROXY                         │             │
│  │  • Connection pooling (per-service)           │             │
│  │  • HTTP/2 multiplexing                        │             │
│  │  • Timeout enforcement                        │             │
│  │  • Request forwarding                         │             │
│  └──────────────────────┬───────────────────────┘             │
│                         │                                      │
│                         ▼                                      │
│  ┌──────────────────────────────────────────────┐             │
│  │         RESPONSE PLUGIN CHAIN                  │             │
│  │                                                │             │
│  │  1. Response Transform Plugin                 │             │
│  │  2. Cache Store Plugin                        │             │
│  │  3. Circuit Breaker Update Plugin             │             │
│  │  4. Rate Limit Headers Plugin                 │             │
│  │  5. CORS Plugin                               │             │
│  │  6. Compression Plugin (gzip/brotli)          │             │
│  │  7. Access Log Plugin                         │             │
│  │  8. Metrics Plugin                            │             │
│  └──────────────────────┬───────────────────────┘             │
│                         │                                      │
│                         ▼                                      │
│  Response to Client                                            │
└────────────────────────────────────────────────────────────────┘
```

### Microservice Patterns Used

| Pattern | Application |
|---------|-------------|
| **Chain of Responsibility** | Plugin chain for request/response processing |
| **Sidecar** | Gateway deployed as sidecar or centralized cluster |
| **Circuit Breaker** | Protect backends from cascade failures |
| **Bulkhead** | Isolate tenant traffic, separate connection pools per service |
| **Retry with Backoff** | Exponential backoff with jitter for transient failures |
| **CQRS** | Separate control plane (writes) from data plane (reads) |
| **Event Sourcing** | All config changes as immutable events for audit |
| **Strangler Fig** | Gradually migrate routes from monolith to microservices |
| **Ambassador** | Gateway as ambassador for external-facing API traffic |

## 6. Low-Level Design (LLD)

### API Specifications

#### Control Plane APIs (Admin)

**Create Route**
```http
POST /admin/v1/routes
Authorization: Bearer <admin_token>
Idempotency-Key: <uuid>
Content-Type: application/json

Request:
{
    "name": "user-service-get-profile",
    "path_pattern": "/v1/users/{user_id}",
    "http_methods": ["GET"],
    "upstream_service_id": "svc_user_001",
    "upstream_path": "/internal/users/{user_id}",
    "strip_prefix": false,
    "priority": 10,
    "auth_policy_id": "auth_jwt_standard",
    "rate_limit_policy_id": "rl_standard_user",
    "cache_config": {
        "enabled": true,
        "ttl_seconds": 60,
        "vary_headers": ["Authorization"],
        "cache_control": "private, max-age=60"
    },
    "circuit_breaker_config": {
        "failure_threshold": 5,
        "recovery_timeout_ms": 30000,
        "half_open_requests": 3
    },
    "transform_config": {
        "request": {
            "add_headers": {"X-Request-Source": "api-gateway"},
            "remove_headers": ["X-Internal-Only"]
        },
        "response": {
            "add_headers": {"X-Served-By": "gateway-cluster-1"},
            "remove_fields": ["internal_id", "debug_info"]
        }
    }
}

Response: 201 Created
{
    "id": "route_abc123",
    "name": "user-service-get-profile",
    "path_pattern": "/v1/users/{user_id}",
    "version": 1,
    "enabled": true,
    "created_at": "2024-01-15T10:30:00Z",
    "effective_at": "2024-01-15T10:30:05Z"
}
```

**Update Route (with optimistic locking)**
```http
PATCH /admin/v1/routes/{route_id}
Authorization: Bearer <admin_token>
Idempotency-Key: <uuid>
If-Match: "version:3"

Request:
{
    "rate_limit_policy_id": "rl_premium_user",
    "cache_config": {
        "ttl_seconds": 120
    }
}

Response: 200 OK
{
    "id": "route_abc123",
    "version": 4,
    "updated_at": "2024-01-15T11:00:00Z",
    "propagation_status": "propagating",
    "propagation_eta_ms": 5000
}
```

**List Routes**
```http
GET /admin/v1/routes?tenant_id=t_001&enabled=true&cursor=eyJ...&limit=50&sort=priority:desc
Authorization: Bearer <admin_token>

Response: 200 OK
{
    "data": [...],
    "pagination": {
        "cursor": "eyJ...",
        "has_more": true,
        "total_count": 234
    }
}
```

**Create API Key**
```http
POST /admin/v1/api-keys
Authorization: Bearer <admin_token>
Idempotency-Key: <uuid>

Request:
{
    "name": "partner-integration-prod",
    "scopes": ["read:users", "write:orders"],
    "rate_limit_tier": "premium",
    "allowed_ips": ["10.0.0.0/8", "192.168.1.0/24"],
    "expires_at": "2025-01-15T00:00:00Z"
}

Response: 201 Created
{
    "id": "key_xyz789",
    "key": "gw_live_ak_7f8g9h0j1k2l3m4n5o6p",  // Only shown once
    "key_prefix": "gw_live_",
    "name": "partner-integration-prod",
    "created_at": "2024-01-15T10:30:00Z"
}
```

**Configure Rate Limit Policy**
```http
POST /admin/v1/rate-limit-policies
Authorization: Bearer <admin_token>

Request:
{
    "name": "premium-tier",
    "algorithm": "sliding_window",
    "limits": [
        {"window": "second", "max_requests": 100},
        {"window": "minute", "max_requests": 5000},
        {"window": "hour", "max_requests": 100000},
        {"window": "day", "max_requests": 1000000}
    ],
    "scope": "per_api_key",
    "burst_size": 200,
    "response_headers": true
}

Response: 201 Created
{
    "id": "rl_premium_001",
    "name": "premium-tier",
    "created_at": "2024-01-15T10:30:00Z"
}
```

#### Data Plane APIs (Runtime)

**Proxied Request Flow**
```http
GET /v1/users/usr_12345
Authorization: Bearer <jwt_token>
X-Request-ID: req_abc123
X-Idempotency-Key: idem_456

Gateway Processing:
1. Route matching → route_abc123
2. Auth validation → JWT verified, user_id extracted
3. Rate limit check → 45/100 requests in window
4. Cache check → MISS
5. Circuit breaker → CLOSED (healthy)
6. Transform → Add X-User-ID header
7. Proxy → upstream user-service:8080/internal/users/usr_12345

Response from upstream: 200 OK
Gateway adds headers:
X-Request-ID: req_abc123
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 55
X-RateLimit-Reset: 1705312260
X-Cache: MISS
X-Gateway-Latency: 3ms

Response: 200 OK
{
    "id": "usr_12345",
    "name": "John Doe",
    "email": "john@example.com"
}
```

**Rate Limited Response**
```http
GET /v1/users/usr_12345
Authorization: Bearer <jwt_token>

Response: 429 Too Many Requests
Retry-After: 12
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705312260

{
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Rate limit exceeded. Please retry after 12 seconds.",
        "retry_after_seconds": 12,
        "limit": 100,
        "window": "minute"
    }
}
```

**Circuit Breaker Open Response**
```http
GET /v1/orders/ord_789
Authorization: Bearer <jwt_token>

Response: 503 Service Unavailable
Retry-After: 30

{
    "error": {
        "code": "SERVICE_UNAVAILABLE",
        "message": "Order service is temporarily unavailable. Please retry later.",
        "retry_after_seconds": 30,
        "fallback_available": false
    }
}
```

#### Internal gRPC APIs (Service-to-Service)

```protobuf
syntax = "proto3";
package gateway.v1;

service GatewayControlPlane {
    // Route Management
    rpc CreateRoute(CreateRouteRequest) returns (Route);
    rpc UpdateRoute(UpdateRouteRequest) returns (Route);
    rpc DeleteRoute(DeleteRouteRequest) returns (Empty);
    rpc GetRoute(GetRouteRequest) returns (Route);
    rpc ListRoutes(ListRoutesRequest) returns (ListRoutesResponse);

    // Config Propagation
    rpc GetRouteConfig(GetRouteConfigRequest) returns (RouteConfig);
    rpc WatchRouteChanges(WatchRequest) returns (stream RouteChangeEvent);

    // Health & Status
    rpc GetServiceHealth(GetServiceHealthRequest) returns (ServiceHealth);
    rpc GetGatewayStatus(Empty) returns (GatewayStatus);
}

service RateLimitService {
    rpc CheckRateLimit(RateLimitRequest) returns (RateLimitResponse);
    rpc GetRateLimitStatus(RateLimitStatusRequest) returns (RateLimitStatus);
}

service AuthService {
    rpc ValidateToken(ValidateTokenRequest) returns (ValidateTokenResponse);
    rpc IntrospectToken(IntrospectRequest) returns (TokenInfo);
}
```

### Design Patterns Used

| Pattern | Where Applied |
|---------|--------------|
| **Chain of Responsibility** | Plugin chain — each plugin decides to proceed or short-circuit |
| **Strategy** | Load balancing algorithms, rate limiting algorithms |
| **Observer** | Config change propagation to all gateway nodes |
| **Proxy** | Core proxy functionality |
| **Decorator** | Adding headers, transforming payloads |
| **Factory** | Creating plugin instances based on route config |
| **Singleton** | Connection pool manager, config cache |
| **Template Method** | Base plugin class with hooks |
| **Builder** | Complex route configuration building |
| **State** | Circuit breaker states (Closed → Open → Half-Open) |

### Core Class Design

```
┌─────────────────────────────────────────────┐
│              GatewayServer                    │
├─────────────────────────────────────────────┤
│ - pluginRegistry: PluginRegistry             │
│ - routeTable: RouteTable                     │
│ - configWatcher: ConfigWatcher               │
│ - metricsCollector: MetricsCollector         │
├─────────────────────────────────────────────┤
│ + handleRequest(ctx, req): Response          │
│ + reloadConfig(): void                       │
│ + healthCheck(): HealthStatus                │
└─────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│              RouteTable                       │
├─────────────────────────────────────────────┤
│ - radixTree: RadixTree<Route>                │
│ - version: int                               │
├─────────────────────────────────────────────┤
│ + match(method, path, headers): RouteMatch   │
│ + reload(config: RouteConfig): void          │
│ + getVersion(): int                          │
└─────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│         PluginChainExecutor                  │
├─────────────────────────────────────────────┤
│ - requestPlugins: List<Plugin>               │
│ - responsePlugins: List<Plugin>              │
├─────────────────────────────────────────────┤
│ + executeRequest(ctx): PluginResult          │
│ + executeResponse(ctx): PluginResult         │
└─────────────────────────────────────────────┘
```

## 7. Architecture Components Deep Dive

### 7.1 Route 53 (DNS Layer)
- **Latency-based routing**: Direct users to nearest gateway cluster
- **Health checks**: Monitor gateway cluster health, failover on region failure
- **Weighted routing**: Enable gradual traffic migration between clusters
- **Geolocation routing**: Comply with data residency requirements
- **Failover**: Active-passive setup with automated DNS failover (TTL: 60s)

### 7.2 CDN (CloudFront)
- **Edge caching**: Cache GET responses for public APIs (product listings, static config)
- **Lambda@Edge**: Run lightweight auth validation, bot detection at edge
- **Origin shield**: Reduce origin load by consolidating cache misses
- **DDoS protection**: AWS Shield Advanced integration
- **Custom error pages**: Branded error responses for 4xx/5xx

### 7.3 WAF (Web Application Firewall)
- **Managed rule groups**: OWASP Top 10, SQL injection, XSS
- **Rate limiting rules**: 10,000 requests/5min per IP (coarse, before gateway)
- **IP reputation lists**: Block known malicious IPs
- **Geo-blocking**: Restrict access from sanctioned countries
- **Request inspection**: Body size limits (10MB), header count limits
- **Bot control**: Detect and challenge automated traffic
- **Custom rules**: Tenant-specific blocking rules

### 7.4 Network Load Balancer
- **Layer 4 (TCP)**: Minimal latency overhead (<1ms)
- **Cross-AZ**: Distribute across all AZs equally
- **Static IPs**: Stable IPs for partner whitelisting
- **Connection draining**: 300s deregistration delay for graceful shutdown
- **Health checks**: TCP health checks every 10s, 3 failures = unhealthy
- **Target groups**: Gateway nodes registered via auto-scaling group

### 7.5 API Gateway Cluster (Custom-Built)

#### Technology Choice: Go + NGINX/Envoy hybrid
- **Go**: High-performance, low-GC-pause processing
- **Envoy proxy**: L7 proxy with native gRPC, HTTP/2, circuit breaking
- **Event loop**: epoll-based non-blocking I/O for maximum connections

#### Key Internal Components:

**Route Matcher (Radix Tree)**
```
Time complexity: O(path_length) for matching
Space: O(number_of_routes × avg_path_length)
Supports: Exact, prefix, regex, parameterized paths
Priority: Higher priority routes matched first
```

**Connection Pool Manager**
```
Per-service pools: Max 1000 connections per upstream
Keep-alive: Reuse HTTP/2 multiplexed connections
Idle timeout: 90s
Health-aware: Remove unhealthy instances from pool
```

**Plugin Execution Engine**
```
Sync plugins: Execute in order, short-circuit on failure
Async plugins (logging, metrics): Fire-and-forget, non-blocking
Plugin isolation: Each plugin has timeout (50ms max)
```

### 7.6 Control Plane Service
- **Separate deployment** from data plane — control plane outage doesn't affect routing
- **Config versioning**: Every change creates new version, allows instant rollback
- **Propagation**: Push config to gateway nodes via gRPC streaming / etcd watches
- **Consistency**: Linearizable reads for config; all nodes converge within 5s
- **Audit log**: Every admin action logged with actor, timestamp, diff

### 7.7 Data Stores

**PostgreSQL (Config Store)**
- 3-node cluster: 1 primary + 2 sync replicas
- Connection pooling: PgBouncer (transaction mode)
- Automated failover: Patroni + etcd
- Backup: WAL archiving to S3, PITR up to 7 days

**Redis Cluster (Rate Limiting & Cache)**
- 6 nodes: 3 masters + 3 replicas
- Hash slots: 16,384 distributed across masters
- Persistence: RDB snapshots every 5min + AOF
- Eviction: `allkeys-lru` for cache, `noeviction` for counters
- Cluster mode: Automatic failover within 15s

**Kafka (Event Log)**
- 12 brokers, 3 AZs
- Topics: `access-logs` (100 partitions), `config-changes` (10 partitions), `alerts` (20 partitions)
- Retention: 7 days for access logs, 90 days for config changes
- Replication factor: 3, min.insync.replicas: 2

## 8. Deep Dive of Each Component Service

### 8.1 Rate Limiter Service (Deep Dive)

#### Algorithm: Sliding Window Log + Token Bucket Hybrid

**Sliding Window Counter** (for per-minute/hour limits):
```
Algorithm:
1. Current window weight = count_current_window
2. Previous window weight = count_previous_window × (1 - elapsed_time/window_size)
3. Estimated count = current + previous_weighted
4. If estimated > limit → DENY

Redis Lua Script (atomic operation):
EVAL "
    local key = KEYS[1]
    local window = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local window_start = now - (now % window)
    local prev_start = window_start - window

    local current = tonumber(redis.call('GET', key..':'..window_start) or '0')
    local previous = tonumber(redis.call('GET', key..':'..prev_start) or '0')
    local elapsed = now - window_start
    local weight = 1 - (elapsed / window)
    local estimated = current + (previous * weight)

    if estimated >= limit then
        return {0, limit - math.floor(estimated), window_start + window - now}
    end

    redis.call('INCR', key..':'..window_start)
    redis.call('EXPIRE', key..':'..window_start, window * 2)
    return {1, limit - math.floor(estimated) - 1, 0}
" 1 rate:{tenant}:{user} 60 100 {current_timestamp}
```

**Token Bucket** (for burst control):
```
State per key: {tokens: float, last_refill: timestamp}
On request:
  1. elapsed = now - last_refill
  2. tokens = min(max_tokens, tokens + elapsed × refill_rate)
  3. if tokens >= 1: tokens -= 1, ALLOW
  4. else: DENY, retry_after = (1 - tokens) / refill_rate
```

#### Distributed Rate Limiting Challenges:
- **Inconsistency across nodes**: Use Redis as single source of truth
- **Redis latency**: Local counter with periodic sync (slightly over-allow)
- **Redis failure**: Fail-open with local token bucket, alert immediately
- **Race conditions**: Lua scripts for atomicity

### 8.2 Authentication Plugin (Deep Dive)

#### JWT Validation Flow:
```
1. Extract token from Authorization header (Bearer scheme)
2. Decode header (no verification) to get `kid` (key ID) and `alg`
3. Look up public key from JWKS cache (keyed by issuer + kid)
4. If cache miss → fetch JWKS from issuer's endpoint (with circuit breaker)
5. Verify signature (RS256/ES256)
6. Validate claims:
   - exp: not expired (with 30s clock skew tolerance)
   - nbf: not before
   - iss: matches configured issuer
   - aud: matches configured audience
   - custom claims per route policy
7. Extract identity: user_id, tenant_id, roles, scopes
8. Attach to request context for downstream plugins
```

#### JWKS Caching Strategy:
```
- Cache TTL: 5 minutes (short to handle key rotation)
- Background refresh: Every 4 minutes (before expiry)
- Fallback: On verification failure, force-refresh JWKS (max once per minute)
- Multiple issuers: Separate cache per issuer
- Memory: ~10KB per issuer (typical JWKS size)
```

### 8.3 Circuit Breaker (Deep Dive)

#### State Machine:
```
CLOSED (normal) ──[failure_count >= threshold]──> OPEN (blocking)
     ^                                               │
     │                                               │
     │                                      [timeout expires]
     │                                               │
     │                                               ▼
     └─────[success_count >= threshold]────── HALF_OPEN (probing)
     └─────[failure in probe]──────────────── OPEN (reset timer)
```

#### Configuration per service:
```json
{
    "failure_threshold": 5,           // failures in window to trip
    "failure_window_ms": 60000,       // rolling window for counting
    "recovery_timeout_ms": 30000,     // time in OPEN before probing
    "half_open_max_requests": 3,      // probes allowed in HALF_OPEN
    "success_threshold": 2,           // successes to close from HALF_OPEN
    "failure_status_codes": [500, 502, 503, 504],
    "timeout_as_failure": true,
    "slow_call_threshold_ms": 5000,
    "slow_call_rate_threshold": 0.5
}
```

### 8.4 Route Matching Engine (Deep Dive)

#### Data Structure: Compressed Radix Tree (Patricia Trie)

```
Route table compilation:
  /v1/users/{id}         → Route A (priority: 10)
  /v1/users/{id}/orders  → Route B (priority: 10)
  /v1/users/search       → Route C (priority: 20, exact match wins)
  /v1/orders/*           → Route D (wildcard catch-all)
  /v2/users/{id}         → Route E (version 2)

Compiled tree:
  root
  ├── /v1/
  │   ├── users/
  │   │   ├── search [Route C, exact] ← higher priority
  │   │   └── {id} [Route A, param]
  │   │       └── /orders [Route B]
  │   └── orders/
  │       └── * [Route D, wildcard]
  └── /v2/
      └── users/
          └── {id} [Route E]

Match priority:
1. Exact match > parameterized > wildcard
2. Within same type: higher priority value wins
3. Longer path prefix wins
```

#### Hot reload without downtime:
```
1. Compile new route table in background
2. Atomic pointer swap (Go: atomic.Value)
3. Old table garbage collected after in-flight requests complete
4. Zero-allocation on hot path (pre-compiled regex, pre-computed hashes)
```

### 8.5 Request/Response Transformation (Deep Dive)

```
Transformation types:
1. Header manipulation: add/remove/rename/rewrite headers
2. Path rewriting: strip prefix, add prefix, regex replace
3. Query param manipulation: add/remove/rename
4. Body transformation: JSON field filtering, renaming, restructuring
5. Protocol translation: REST → gRPC (using proto descriptors)

Performance considerations:
- Header transforms: zero-copy where possible
- Body transforms: streaming JSON parser for large bodies
- Lazy parsing: only parse body if transform config exists for route
- Template engine: pre-compiled Go templates for dynamic values
```

### 8.6 Canary Deployment Manager (Deep Dive)

```
Canary routing decision:
1. Check canary config for matched route
2. Determine canary eligibility:
   - Header match: X-Canary: true → always canary
   - User segment: hash(user_id) % 100 < canary_weight
   - Gradual rollout: 1% → 5% → 25% → 50% → 100%
3. Route to canary upstream
4. Track canary metrics separately
5. Auto-rollback if error rate > baseline + threshold

Canary health gate:
- Compare canary vs baseline: error rate, p99 latency, success rate
- If canary degrades > 10% vs baseline → auto rollback
- Minimum observation window: 5 minutes
- Minimum request count: 1000 before making decision
```

## 9. Component Optimization & Advanced Processing

### 9.1 Caching Strategy

#### Multi-Level Cache:
```
Level 1: In-process LRU cache (per gateway node)
  - Capacity: 1 GB per node
  - TTL: 30-60 seconds (short, for consistency)
  - Hit ratio target: 30-40% (only hottest keys)
  - Eviction: LRU with size-aware eviction

Level 2: Distributed Redis cache
  - Capacity: 100 GB cluster
  - TTL: Route-configured (60s-3600s)
  - Hit ratio target: 60-70%
  - Eviction: allkeys-lru

Level 3: CDN edge cache
  - For public, cacheable responses
  - TTL: Route-configured with s-maxage
  - Purge API for invalidation
```

#### Cache Invalidation Patterns:
```
1. TTL-based: Short TTLs (30-300s) for most data
2. Event-driven: Kafka consumer invalidates on data change events
3. Explicit purge: Admin API to purge specific cache keys
4. Stale-while-revalidate: Serve stale, refresh in background
5. Versioned keys: Include version in cache key, new version = new key

Cache stampede prevention:
- Request coalescing: Single inflight request per cache key (singleflight)
- Probabilistic early expiration: Refresh before TTL with probability
- Lock-based refresh: Distributed lock, one node refreshes, others wait
```

### 9.2 Async Processing with Kafka

#### Event Topics & Processing:

```
Topic: gateway.access-logs (100 partitions)
├── Partition key: tenant_id (even distribution)
├── Schema: Avro with Schema Registry
├── Retention: 7 days
├── Consumers:
│   ├── ClickHouse sink connector (analytics)
│   ├── Anomaly detection (Flink job)
│   ├── S3 archiver (long-term storage)
│   └── Real-time dashboard (Kafka Streams)

Topic: gateway.config-changes (10 partitions)
├── Partition key: route_id
├── Compacted topic (latest state per key)
├── Retention: forever (compacted)
├── Consumers:
│   ├── Gateway nodes (config reload)
│   ├── Audit service
│   └── Compliance exporter

Topic: gateway.rate-limit-events (50 partitions)
├── Partition key: tenant_id
├── Events: rate_limit_hit, quota_exceeded
├── Consumers:
│   ├── Alerting service
│   ├── Billing/usage metering
│   └── Abuse detection (Flink)

Topic: gateway.circuit-breaker-events (20 partitions)
├── Events: circuit_opened, circuit_closed, half_open
├── Consumers:
│   ├── Incident management (PagerDuty)
│   ├── Dashboard updates
│   └── Auto-scaling triggers
```

### 9.3 Stream Processing with Apache Flink

```
Flink Jobs:
1. Real-time Anomaly Detection:
   - Input: access-logs stream
   - Window: Tumbling 1-minute window
   - Logic: Compare current error rate vs 24h baseline
   - Output: anomaly-alerts topic → PagerDuty

2. DDoS Detection:
   - Input: access-logs stream
   - Window: Sliding 10-second window
   - Logic: Count requests per IP, detect sudden spikes
   - Output: Block list update → WAF API

3. Usage Metering:
   - Input: access-logs stream
   - Window: Tumbling 1-hour window
   - Aggregation: Count requests per tenant per API per hour
   - Output: usage-metrics → Billing service

4. Real-time API Analytics:
   - Input: access-logs stream
   - Window: Tumbling 1-minute window
   - Metrics: RPS, error rate, p50/p95/p99 latency per route
   - Output: Pinot/ClickHouse for dashboard queries
```

### 9.4 WebSocket & Server-Sent Events Support

```
WebSocket proxying:
1. Client initiates WebSocket upgrade via gateway
2. Gateway validates auth (same as HTTP)
3. Rate limit check (connection-level, not message-level)
4. Upgrade connection, proxy to backend WebSocket service
5. Maintain bidirectional pipe with:
   - Idle timeout: 300s (configurable)
   - Max message size: 1MB
   - Ping/pong heartbeats: every 30s
   - Connection registry for graceful shutdown

SSE (Server-Sent Events):
1. Client opens SSE connection via GET with Accept: text/event-stream
2. Gateway authenticates and routes to SSE backend
3. Keep-alive: gateway sends comment lines every 15s
4. Automatic reconnection with Last-Event-ID header
5. Backpressure: buffer 100 events, then drop oldest

Long Polling:
1. Client sends request with timeout parameter
2. Gateway holds connection open (max 30s)
3. Backend responds when data available or timeout
4. Gateway enforces max hold time to prevent resource exhaustion
```

### 9.5 Database Optimization

#### PostgreSQL Optimizations:
```sql
-- Partitioning: partition api_keys by tenant for large deployments
CREATE TABLE api_keys_partitioned (LIKE api_keys)
PARTITION BY HASH (tenant_id);
CREATE TABLE api_keys_p0 PARTITION OF api_keys_partitioned FOR VALUES WITH (MODULUS 16, REMAINDER 0);
-- ... 16 partitions

-- Partial indexes for hot queries
CREATE INDEX idx_active_routes ON routes(tenant_id, priority DESC)
    WHERE enabled = true AND archived_at IS NULL;

-- Covering index to avoid table lookups
CREATE INDEX idx_api_key_lookup ON api_keys(key_hash)
    INCLUDE (tenant_id, scopes, rate_limit_tier, expires_at, revoked_at)
    WHERE revoked_at IS NULL;

-- Connection pooling: PgBouncer config
[pgbouncer]
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 50
min_pool_size = 10
reserve_pool_size = 10
reserve_pool_timeout = 3
```

#### Redis Optimizations:
```
# Pipeline rate limit checks (batch multiple keys)
MULTI
  EVALSHA <sliding_window_sha> 1 rate:t1:u1 60 100 {ts}
  EVALSHA <sliding_window_sha> 1 rate:t1:u1 3600 5000 {ts}
EXEC

# Use Redis Cluster hash tags for co-located keys
rate:{tenant_123}:user_456:minute  → same slot
rate:{tenant_123}:user_456:hour    → same slot

# Memory optimization
- Use Redis hashes for small objects (ziplist encoding)
- Key expiry for automatic cleanup
- Avoid storing full response bodies (use references)
```

#### Sharding Strategy:
```
Config DB (PostgreSQL):
- Shard by tenant_id for multi-tenant deployments
- Each shard handles ~1000 tenants
- Cross-shard queries via application-level fanout

Redis (Rate Limiting):
- Redis Cluster with 16384 hash slots
- Key design: rate:{tenant_id}:{identifier}:{window}
- Hash tag ensures same tenant's keys land on same shard
- Resharding: online slot migration without downtime

ClickHouse (Analytics):
- Partition by date (toYYYYMMDD)
- Order by (tenant_id, timestamp) for fast tenant queries
- Distributed table across 6 shards × 2 replicas
- TTL: 90 days hot, then move to S3 (cold storage)
```

### 9.6 Big Data Pipeline (Analytics)

```
┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────────┐
│  Kafka   │───>│  Flink   │───>│  ClickHouse  │───>│  Grafana/    │
│ (raw     │    │ (process)│    │  (OLAP)      │    │  Superset    │
│  events) │    │          │    │              │    │  (dashboard) │
└──────────┘    └──────────┘    └──────────────┘    └──────────────┘
      │                               │
      ▼                               ▼
┌──────────┐                   ┌──────────────┐
│  S3      │                   │  Apache      │
│ (archive)│                   │  Iceberg     │
│ Parquet  │                   │ (data lake)  │
└──────────┘                   └──────────────┘

Data flow:
1. Gateway emits access log events to Kafka (Avro format)
2. Flink enriches with tenant metadata, geo-IP, device info
3. ClickHouse ingests for real-time queries (< 1s for last hour)
4. S3 stores Parquet files for historical analysis (Iceberg tables)
5. Pinot serves pre-aggregated time-series for dashboards
6. Trino/Athena for ad-hoc queries across S3 data lake
```

### 9.7 Connection Pooling & HTTP/2 Multiplexing

```
Upstream connection management:
- HTTP/2 to backends: single connection, 100 concurrent streams
- Connection pool per (service, instance): max 100 connections
- Pool warming: pre-establish min 10 connections on startup
- Idle timeout: 90s (matches backend keep-alive)
- Health-aware: remove connections to unhealthy instances
- DNS refresh: re-resolve every 30s for dynamic backends (Kubernetes)

Client-facing:
- HTTP/2 with server push for common resources
- Connection limit per client IP: 100 concurrent
- Request pipeline depth: 10 per connection
- Keep-alive timeout: 120s
```

## 10. Observability

### 10.1 Metrics (Prometheus/Mimir)

```yaml
# Gateway-level metrics
gateway_requests_total{method, route, status, tenant}              # Counter
gateway_request_duration_seconds{method, route, tenant}            # Histogram (p50, p95, p99)
gateway_request_size_bytes{method, route}                          # Histogram
gateway_response_size_bytes{method, route, status}                 # Histogram
gateway_active_connections{protocol}                               # Gauge
gateway_upstream_requests_total{service, instance, status}         # Counter
gateway_upstream_duration_seconds{service}                         # Histogram

# Rate limiting metrics
gateway_rate_limit_total{tenant, decision}                         # Counter (allowed/denied)
gateway_rate_limit_remaining{tenant, policy}                       # Gauge
gateway_rate_limit_latency_seconds                                 # Histogram

# Circuit breaker metrics
gateway_circuit_breaker_state{service}                             # Gauge (0=closed, 1=open, 2=half_open)
gateway_circuit_breaker_transitions_total{service, from, to}       # Counter

# Cache metrics
gateway_cache_hits_total{level, route}                             # Counter
gateway_cache_misses_total{level, route}                           # Counter
gateway_cache_evictions_total{level}                               # Counter
gateway_cache_size_bytes{level}                                    # Gauge

# Auth metrics
gateway_auth_decisions_total{method, decision}                     # Counter
gateway_auth_latency_seconds{method}                               # Histogram
gateway_token_validation_errors_total{reason}                      # Counter

# System metrics
gateway_goroutines                                                 # Gauge
gateway_memory_bytes{type}                                         # Gauge
gateway_gc_duration_seconds                                        # Histogram
gateway_config_version                                             # Gauge
gateway_config_reload_total{status}                                # Counter
```

### 10.2 Distributed Tracing (Jaeger/Tempo)

```
Trace propagation:
- W3C TraceContext headers (traceparent, tracestate)
- B3 headers for backward compatibility
- Gateway generates trace if not present

Spans created by gateway:
1. gateway.request (root span for gateway processing)
   ├── gateway.auth (authentication/authorization)
   ├── gateway.rate_limit (rate limit check)
   ├── gateway.cache_lookup (cache check)
   ├── gateway.transform (request transformation)
   ├── gateway.upstream (proxy to backend)
   │   ├── dns.resolve (if needed)
   │   ├── tcp.connect (connection establishment)
   │   └── http.request (actual request)
   ├── gateway.response_transform
   └── gateway.logging (async, non-blocking)

Span attributes:
- gateway.route_id, gateway.tenant_id, gateway.node_id
- http.method, http.url, http.status_code
- upstream.service, upstream.instance, upstream.latency_ms
- rate_limit.remaining, cache.hit, circuit_breaker.state
```

### 10.3 Structured Logging (ELK/Loki)

```json
{
    "timestamp": "2024-01-15T10:30:00.123Z",
    "level": "INFO",
    "service": "api-gateway",
    "node_id": "gw-node-03",
    "trace_id": "abc123def456",
    "span_id": "789ghi",
    "request_id": "req_xyz789",
    "event": "request_completed",
    "tenant_id": "t_001",
    "user_id": "u_12345",
    "method": "GET",
    "path": "/v1/users/u_12345",
    "route_id": "route_abc",
    "upstream_service": "user-service",
    "upstream_instance": "10.0.1.5:8080",
    "status": 200,
    "gateway_latency_ms": 3,
    "upstream_latency_ms": 45,
    "total_latency_ms": 48,
    "request_size": 256,
    "response_size": 1024,
    "cache_hit": false,
    "rate_limit_remaining": 55,
    "client_ip": "203.0.113.42",
    "user_agent": "Mozilla/5.0...",
    "region": "us-east-1",
    "az": "us-east-1a"
}
```

### 10.4 Alerting Rules

```yaml
# Critical alerts (page on-call)
- alert: GatewayHighErrorRate
  expr: rate(gateway_requests_total{status=~"5.."}[5m]) / rate(gateway_requests_total[5m]) > 0.01
  for: 2m
  severity: critical
  annotations: "Gateway error rate > 1% for 2 minutes"

- alert: GatewayHighLatency
  expr: histogram_quantile(0.99, gateway_request_duration_seconds) > 0.150
  for: 3m
  severity: critical
  annotations: "Gateway p99 latency > 150ms"

- alert: CircuitBreakerOpen
  expr: gateway_circuit_breaker_state == 1
  for: 1m
  severity: warning
  annotations: "Circuit breaker open for {{ $labels.service }}"

- alert: RateLimitExhaustion
  expr: gateway_rate_limit_remaining < 10
  for: 5m
  severity: warning
  annotations: "Rate limit nearly exhausted for {{ $labels.tenant }}"

# Capacity alerts
- alert: GatewayHighCPU
  expr: process_cpu_seconds_total > 0.8
  for: 5m
  severity: warning

- alert: RedisHighMemory
  expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
  for: 10m
  severity: warning
```

### 10.5 Dashboards

```
Dashboard 1: Gateway Overview
- Total RPS (real-time)
- Error rate by status code (4xx, 5xx)
- p50/p95/p99 latency
- Active connections
- Cache hit ratio
- Top 10 routes by traffic

Dashboard 2: Per-Tenant View
- RPS per tenant
- Rate limit utilization
- Error budget remaining
- Top APIs by usage
- Quota consumption trend

Dashboard 3: Upstream Health
- Per-service error rate
- Per-service latency
- Circuit breaker states
- Connection pool utilization
- Retry rates

Dashboard 4: Security
- Auth failures by type
- Rate limit denials
- IP blacklist hits
- WAF blocks
- Suspicious traffic patterns

Dashboard 5: Infrastructure
- Node CPU/memory/network
- Redis cluster health
- Kafka consumer lag
- Config propagation latency
- GC pauses
```

## 11. Considerations and Assumptions

### Assumptions
1. **Cloud-native deployment**: Running on AWS/GCP/Azure with managed services available
2. **Microservices architecture**: Backend services are independently deployable
3. **Multi-tenant**: Single gateway cluster serves multiple tenants with isolation
4. **HTTP-first**: Primary protocol is HTTP/1.1 and HTTP/2; gRPC secondary
5. **Regional deployment**: Initially single region, designed for multi-region expansion
6. **Team size**: Dedicated platform team of 5-8 engineers owns the gateway
7. **No legacy**: Greenfield implementation, no migration constraints
8. **Budget**: Can afford managed services (Redis, Kafka, PostgreSQL managed)

### Key Design Decisions & Rationale

| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| Custom vs Off-shelf | Custom (Go + Envoy) | Kong/Apigee/AWS API GW | Full control, performance, no vendor lock-in at scale |
| Rate limit store | Redis Cluster | In-memory + gossip | Accuracy across nodes, proven at scale |
| Config propagation | gRPC streaming + etcd watch | Polling | Sub-second propagation, reduced load |
| Log storage | ClickHouse | Elasticsearch | Better compression, faster analytical queries |
| Protocol | HTTP/2 to backends | HTTP/1.1 | Multiplexing reduces connection overhead |
| Auth | JWT (stateless) | Session-based | Horizontally scalable, no session store needed |

### Trade-offs Accepted

1. **Latency vs Security**: Full plugin chain adds ~5ms; acceptable for security benefits
2. **Consistency vs Availability (rate limiting)**: Accept slight over-counting for availability; never block due to rate limiter failure
3. **Memory vs Latency**: Keep route table + common responses in memory (higher cost, lower latency)
4. **Complexity vs Flexibility**: Plugin architecture is complex but allows adding features without core changes
5. **Operational cost vs Features**: Running Kafka + ClickHouse + Redis is expensive but necessary for observability

### Failure Modes & Mitigation

| Scenario | Behavior | Recovery |
|----------|----------|----------|
| Redis cluster down | Fail-open (allow all, log), use local counters | Auto-reconnect, alert, manual failover if needed |
| Config DB down | Serve from cached config (last known good) | Patroni auto-failover, restore from PITR |
| Kafka down | Buffer logs locally (disk), drop after 100MB | Reconnect automatically, replay from buffer |
| Backend service down | Circuit breaker opens, return 503 | Half-open probes detect recovery |
| Gateway node crash | NLB removes from target group in 10s | Auto-scaling replaces instance |
| Bad config push | Canary node validates first, rollback if errors | Version pinning, instant rollback API |
| DNS failure | Cached DNS records (TTL), multi-provider DNS | Automatic failover to secondary DNS |

### Security Considerations
- **Zero-trust**: Every hop is authenticated (mTLS between services)
- **Secret rotation**: API keys, TLS certs, DB passwords rotated automatically
- **PCI compliance**: Gateway never stores raw card data; only routes to PCI-scoped services
- **DDoS layers**: CDN → WAF → NLB → Gateway (progressive protection)
- **Audit trail**: Every admin action, config change, and policy decision logged immutably

### Future Evolution
1. **Multi-region**: Deploy gateway clusters in 3+ regions with global routing
2. **GraphQL support**: Add GraphQL-specific plugins (query complexity, depth limiting)
3. **Service mesh integration**: Gateway as north-south traffic, Envoy sidecars for east-west
4. **AI-powered**: ML-based anomaly detection for auto-blocking and traffic shaping
5. **Developer portal**: Self-service API key management, documentation, sandbox environments
