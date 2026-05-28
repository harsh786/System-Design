# Design a Load Balancer

## 1. Functional Requirements

- **Traffic Distribution**: Distribute incoming network traffic across multiple backend servers using configurable algorithms (round-robin, least connections, weighted, IP hash, consistent hashing)
- **Layer 4 (Transport) Load Balancing**: Route TCP/UDP traffic based on IP address and port without inspecting packet contents
- **Layer 7 (Application) Load Balancing**: Route HTTP/HTTPS traffic based on URL path, headers, cookies, query parameters
- **Health Checking**: Actively and passively monitor backend server health; remove unhealthy servers from rotation
- **SSL/TLS Termination**: Offload TLS encryption/decryption at the load balancer; support TLS passthrough mode
- **Session Persistence (Sticky Sessions)**: Route requests from the same client to the same backend using cookies, IP, or custom headers
- **Connection Draining**: Gracefully remove servers from rotation allowing in-flight requests to complete
- **Auto-Scaling Integration**: Dynamically register/deregister backend instances as they scale
- **Global Server Load Balancing (GSLB)**: Distribute traffic across multiple data centers/regions based on latency, geography, or health
- **Rate Limiting**: Protect backends from traffic spikes at the load balancer level
- **WebSocket Support**: Maintain persistent WebSocket connections with proper backend affinity
- **Request Queuing**: Queue requests when all backends are busy instead of immediately failing
- **Circuit Breaking**: Stop forwarding traffic to a backend that is consistently failing
- **Hot Configuration Reload**: Update routing rules, backend pools, and algorithms without dropping connections
- **Access Control Lists (ACLs)**: IP-based allow/deny lists at the LB level
- **Content-Based Routing**: Route to different backend pools based on request attributes (host header, path prefix, method)
- **Admin/Control Plane API**: CRUD for backend pools, health check configs, routing rules, SSL certificates

## 2. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| **Availability** | 99.999% (5.26 min downtime/year) — LB is single most critical infrastructure |
| **Latency Overhead** | L4: < 0.5ms added latency; L7: < 2ms added latency |
| **Throughput** | L4: 10M+ concurrent connections, 40 Gbps per node; L7: 1M+ RPS per cluster |
| **Scalability** | Horizontal scaling with ECMP or DNS for LB tier itself |
| **Failover Time** | < 3 seconds for active-passive failover |
| **Connection Capacity** | 10M+ concurrent TCP connections per node |
| **Packets Per Second** | 20M+ PPS per node (L4) |
| **Zero Downtime** | Config changes, certificate rotation, backend changes without dropping connections |
| **Observability** | Per-backend, per-route metrics with sub-second granularity |
| **Security** | DDoS mitigation, SYN flood protection, slowloris protection |

## 3. Capacity Estimation

### Assumptions
| Dimension | Value |
|-----------|-------|
| Total users served | 500M MAU across all services behind LB |
| Peak concurrent connections | 10 million |
| Peak requests per second | 2 million RPS (L7) |
| Average request size | 2 KB |
| Average response size | 10 KB |
| Backend server pools | 50 pools |
| Servers per pool | 20-500 instances |
| Total backend servers | 5,000 |
| SSL/TLS handshakes/sec | 100,000 new connections/sec |
| Health check frequency | Every 5 seconds per backend |

### QPS/RPS Calculation
```
Peak L7 RPS: 2,000,000 RPS
Average L7 RPS: 500,000 RPS
Peak L4 connections/sec: 500,000 new connections/sec
Peak concurrent connections: 10,000,000
Health check requests/sec: 5,000 backends / 5s = 1,000 health checks/sec
SSL handshakes/sec: 100,000 (RSA-2048: ~1500 per CPU core with hardware acceleration)
```

### Network Bandwidth Estimation
```
Ingress: 2M RPS × 2 KB = 4 GB/s = 32 Gbps (peak)
Egress: 2M RPS × 10 KB = 20 GB/s = 160 Gbps (peak, distributed across multiple LB nodes)
Per LB node (assuming 8 nodes): 32/8 = 4 Gbps ingress, 20 Gbps egress each
Inter-LB heartbeat: negligible (< 1 Mbps)
Total cluster bandwidth: ~200 Gbps
```

### Storage Estimation
```
Configuration data: 50 pools × 500 rules × 2 KB = 50 MB (fits in memory)
SSL certificates: 1,000 certs × 10 KB = 10 MB
Connection tracking table: 10M connections × 128 bytes = 1.28 GB per node
Access logs/day: 2M RPS × 86,400s × 200 bytes = 34.5 TB/day (if logging all)
Metrics time-series: ~100K unique series × 8 bytes × 86,400 points = 69 GB/day
```

### Infrastructure Sizing
```
L4 LB nodes: 4 nodes active + 4 standby (ECMP distribution)
L7 LB nodes: 16 nodes (2M RPS / 125K RPS per node)
Control plane: 3 nodes (etcd/Raft consensus)
Metrics collection: 3 Prometheus/Mimir nodes
Log pipeline: Kafka (6 brokers) → ClickHouse (4 nodes)
```

## 4. Data Modeling

### Database Choice
| Data | Store | Why |
|------|-------|-----|
| Configuration (pools, routes, certs) | etcd / PostgreSQL | Strong consistency, watch/notify for changes |
| Connection tracking | In-memory hash table | Ultra-low latency, per-node state |
| Health status | In-memory + gossip | Real-time per-node awareness |
| Metrics/telemetry | Prometheus TSDB / Mimir | Time-series optimized, PromQL |
| Access logs | Kafka → ClickHouse / S3 | High-volume append, analytical queries |
| SSL/TLS certificates | HashiCorp Vault / KMS | Secure storage, rotation automation |
| Session affinity state | In-memory consistent hash ring | Fast lookup, distributed across nodes |

### Schema Design

#### `backend_pools` (etcd/PostgreSQL)
```sql
CREATE TABLE backend_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    algorithm VARCHAR(50) NOT NULL DEFAULT 'round_robin',
    -- Algorithms: round_robin, least_connections, weighted_round_robin,
    -- ip_hash, consistent_hash, random, least_response_time
    health_check_config JSONB NOT NULL DEFAULT '{
        "protocol": "HTTP",
        "path": "/health",
        "interval_ms": 5000,
        "timeout_ms": 3000,
        "healthy_threshold": 3,
        "unhealthy_threshold": 2,
        "expected_status": [200]
    }',
    session_persistence JSONB, -- {"type": "cookie", "cookie_name": "SERVERID", "ttl": 3600}
    connection_limits JSONB DEFAULT '{
        "max_connections_per_backend": 1000,
        "max_pending_requests": 500,
        "connection_timeout_ms": 5000,
        "idle_timeout_ms": 60000
    }',
    circuit_breaker_config JSONB DEFAULT '{
        "consecutive_failures": 5,
        "interval_ms": 30000,
        "base_ejection_time_ms": 30000,
        "max_ejection_percent": 50
    }',
    retry_policy JSONB DEFAULT '{
        "num_retries": 2,
        "retry_on": ["5xx", "connect-failure", "refused-stream"],
        "per_try_timeout_ms": 5000
    }',
    version INT NOT NULL DEFAULT 1,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pools_name ON backend_pools(name);
CREATE INDEX idx_pools_enabled ON backend_pools(enabled) WHERE enabled = true;
```

#### `backends` (etcd/PostgreSQL)
```sql
CREATE TABLE backends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id UUID NOT NULL REFERENCES backend_pools(id) ON DELETE CASCADE,
    address VARCHAR(255) NOT NULL,          -- IP:port or hostname:port
    weight INT DEFAULT 100,                 -- For weighted algorithms (1-1000)
    max_connections INT DEFAULT 0,          -- 0 = unlimited
    priority INT DEFAULT 0,                 -- For priority-based failover
    metadata JSONB,                         -- {"zone": "us-east-1a", "version": "v2.1"}
    tls_enabled BOOLEAN DEFAULT false,
    health_status VARCHAR(20) DEFAULT 'unknown', -- healthy, unhealthy, draining, unknown
    last_health_check_at TIMESTAMPTZ,
    drain_started_at TIMESTAMPTZ,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pool_id, address)
);

CREATE INDEX idx_backends_pool ON backends(pool_id, enabled, health_status);
CREATE INDEX idx_backends_health ON backends(health_status, last_health_check_at);
CREATE INDEX idx_backends_draining ON backends(drain_started_at) WHERE drain_started_at IS NOT NULL;
```

#### `routing_rules` (etcd/PostgreSQL)
```sql
CREATE TABLE routing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listener_id UUID NOT NULL REFERENCES listeners(id),
    priority INT NOT NULL DEFAULT 0,
    match_config JSONB NOT NULL,
    -- Example: {"host": "api.example.com", "path_prefix": "/v1/users", 
    --           "headers": {"X-Canary": "true"}, "methods": ["GET","POST"]}
    action_config JSONB NOT NULL,
    -- Example: {"type": "forward", "pool_id": "uuid", "weight_groups": [
    --   {"pool_id": "uuid-v1", "weight": 90}, {"pool_id": "uuid-v2", "weight": 10}
    -- ]}
    rate_limit_config JSONB,
    -- Example: {"requests_per_second": 1000, "burst": 2000, "scope": "per_source_ip"}
    request_transform JSONB,
    response_transform JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rules_listener_priority ON routing_rules(listener_id, priority DESC) WHERE enabled = true;
```

#### `listeners` (etcd/PostgreSQL)
```sql
CREATE TABLE listeners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    bind_address VARCHAR(50) NOT NULL DEFAULT '0.0.0.0',
    port INT NOT NULL,
    protocol VARCHAR(10) NOT NULL,          -- TCP, HTTP, HTTPS, UDP, gRPC
    tls_config JSONB,                       -- {"cert_id": "uuid", "min_version": "1.2", "ciphers": [...]}
    http2_enabled BOOLEAN DEFAULT true,
    proxy_protocol_enabled BOOLEAN DEFAULT false,
    max_connections INT DEFAULT 100000,
    idle_timeout_ms INT DEFAULT 60000,
    request_timeout_ms INT DEFAULT 30000,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(bind_address, port)
);
```

#### `ssl_certificates` (Vault/PostgreSQL)
```sql
CREATE TABLE ssl_certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(500) NOT NULL,
    cert_pem TEXT NOT NULL,                 -- In production, store in Vault
    key_ref VARCHAR(255) NOT NULL,          -- Reference to Vault secret
    chain_pem TEXT,
    issuer VARCHAR(255),
    not_before TIMESTAMPTZ NOT NULL,
    not_after TIMESTAMPTZ NOT NULL,
    auto_renew BOOLEAN DEFAULT true,
    san_domains TEXT[],                     -- Subject Alternative Names
    fingerprint VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_certs_domain ON ssl_certificates(domain);
CREATE INDEX idx_certs_expiry ON ssl_certificates(not_after) WHERE auto_renew = true;
```

#### Connection Tracking (In-Memory Data Structure)
```c
// Per-node in-memory connection table
struct connection_entry {
    uint64_t conn_id;           // Unique connection identifier
    uint32_t client_ip;         // Source IP
    uint16_t client_port;       // Source port
    uint32_t backend_ip;        // Selected backend IP
    uint16_t backend_port;      // Backend port
    uint8_t  state;             // SYN_SENT, ESTABLISHED, FIN_WAIT, CLOSED
    uint64_t bytes_in;          // Bytes received from client
    uint64_t bytes_out;         // Bytes sent to client
    uint64_t created_at;        // Connection creation timestamp (ns)
    uint64_t last_activity;     // Last packet timestamp (ns)
    uint32_t pool_id_hash;      // Hash of pool for quick lookup
    uint16_t flags;             // WebSocket, HTTP/2, keep-alive flags
};
// Hash table: key = (client_ip, client_port, backend_ip, backend_port)
// Size: 10M entries × 64 bytes = 640 MB per node
```

## 5. High-Level Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INTERNET / CLIENTS                               │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                  │
                    ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GLOBAL LOAD BALANCING (GSLB / DNS)                         │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  Route 53    │  │  CloudFlare  │  │  Anycast     │                     │
│  │  (Latency)   │  │  (GeoDNS)    │  │  (BGP)       │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│                                                                              │
│  Decision factors: Latency, Geography, Health, Capacity, Cost               │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│   Region: US-East   │ │   Region: EU-West   │ │   Region: AP-South  │
└──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LAYER 4 LOAD BALANCER TIER                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              ECMP Router / BGP Anycast                                │   │
│  │   Distributes traffic across L4 LB nodes using equal-cost paths      │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│       ┌──────────┬──────────┬─────┴────┬──────────┐                       │
│       ▼          ▼          ▼          ▼          ▼                       │
│  ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐               │
│  │ L4 LB   ││ L4 LB   ││ L4 LB   ││ L4 LB   ││ L4 LB   │ (Active)    │
│  │ Node 1  ││ Node 2  ││ Node 3  ││ Node 4  ││ Node N  │               │
│  │ (DPDK)  ││ (DPDK)  ││ (DPDK)  ││ (DPDK)  ││ (DPDK)  │               │
│  └────┬────┘└────┬────┘└────┬────┘└────┬────┘└────┬────┘               │
│       │          │          │          │          │                       │
│  ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐               │
│  │ L4 LB   ││ L4 LB   ││ L4 LB   ││ L4 LB   ││ L4 LB   │ (Standby)   │
│  │ Standby ││ Standby ││ Standby ││ Standby ││ Standby │               │
│  └─────────┘└─────────┘└─────────┘└─────────┘└─────────┘               │
│                                                                              │
│  Technology: DPDK/XDP for kernel bypass, Direct Server Return (DSR)         │
│  Failover: VRRP/keepalived, connection state sync between active/standby    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LAYER 7 LOAD BALANCER TIER                                 │
│                                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │
│  │ L7 LB   │ │ L7 LB   │ │ L7 LB   │ │ L7 LB   │ │ L7 LB   │ │  ...   │ │
│  │ Node 1  │ │ Node 2  │ │ Node 3  │ │ Node 4  │ │ Node N  │ │ ×16    │ │
│  │         │ │         │ │         │ │         │ │         │ │        │ │
│  │┌───────┐│ │┌───────┐│ │┌───────┐│ │┌───────┐│ │┌───────┐│ │        │ │
│  ││ TLS   ││ ││ TLS   ││ ││ TLS   ││ ││ TLS   ││ ││ TLS   ││ │        │ │
│  ││ Engine││ ││ Engine││ ││ Engine││ ││ Engine││ ││ Engine││ │        │ │
│  │├───────┤│ │├───────┤│ │├───────┤│ │├───────┤│ │├───────┤│ │        │ │
│  ││ Route ││ ││ Route ││ ││ Route ││ ││ Route ││ ││ Route ││ │        │ │
│  ││ Match ││ ││ Match ││ ││ Match ││ ││ Match ││ ││ Match ││ │        │ │
│  │├───────┤│ │├───────┤│ │├───────┤│ │├───────┤│ │├───────┤│ │        │ │
│  ││Health ││ ││Health ││ ││Health ││ ││Health ││ ││Health ││ │        │ │
│  ││Check  ││ ││Check  ││ ││Check  ││ ││Check  ││ ││Check  ││ │        │ │
│  │├───────┤│ │├───────┤│ │├───────┤│ │├───────┤│ │├───────┤│ │        │ │
│  ││Metrics││ ││Metrics││ ││Metrics││ ││Metrics││ ││Metrics││ │        │ │
│  │└───────┘│ │└───────┘│ │└───────┘│ │└───────┘│ │└───────┘│ │        │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────────┘ │
│                                                                              │
│  Technology: Envoy/NGINX/HAProxy, HTTP/2, gRPC, WebSocket                   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND SERVER POOLS                                  │
│                                                                              │
│  Pool: user-service          Pool: order-service        Pool: payment-svc   │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐   ┌───┐ ┌───┐ ┌───┐ ┌───┐  ┌───┐ ┌───┐ ┌───┐ │
│  │S1 │ │S2 │ │S3 │ │...│   │S1 │ │S2 │ │S3 │ │...│  │S1 │ │S2 │ │...│ │
│  └───┘ └───┘ └───┘ └───┘   └───┘ └───┘ └───┘ └───┘  └───┘ └───┘ └───┘ │
│  Weight: 3   2    2    1    Weight: 1   1    1    1                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONTROL PLANE                                         │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Config API  │  │  etcd/Raft   │  │  Service     │  │  Certificate │  │
│  │  (REST/gRPC) │  │  (Consensus) │  │  Discovery   │  │  Manager     │  │
│  │              │  │              │  │  (Consul/k8s)│  │  (ACME/Vault)│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  Metrics     │  │  Log         │  │  Alerting    │                     │
│  │  Collector   │  │  Aggregator  │  │  Engine      │                     │
│  │  (Prometheus)│  │  (Vector)    │  │  (AlertMgr)  │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Microservice Patterns

| Pattern | Usage |
|---------|-------|
| **ECMP (Equal-Cost Multi-Path)** | Distribute across L4 LB nodes without a single point of failure |
| **Direct Server Return (DSR)** | Response bypasses LB (L4), reducing LB bandwidth load by 10x |
| **Consistent Hashing** | Minimize backend remapping when servers are added/removed |
| **Active-Passive Failover** | VRRP pairs for L4 HA; connection state mirroring |
| **Sidecar** | Health check agent as sidecar on each LB node |
| **Observer/Pub-Sub** | Config changes propagated via etcd watches to all nodes |
| **Service Discovery** | Auto-register backends from Kubernetes/Consul |
| **xDS Protocol** | Envoy's discovery service protocol for dynamic config |

## 6. Low-Level Design (LLD)

### Control Plane APIs

**Create Backend Pool**
```http
POST /api/v1/pools
Authorization: Bearer <token>
Idempotency-Key: <uuid>

Request:
{
    "name": "user-service-prod",
    "algorithm": "least_connections",
    "health_check": {
        "protocol": "HTTP",
        "path": "/healthz",
        "interval_ms": 5000,
        "timeout_ms": 2000,
        "healthy_threshold": 2,
        "unhealthy_threshold": 3,
        "expected_codes": [200, 204]
    },
    "session_persistence": {
        "type": "cookie",
        "cookie_name": "SRVID",
        "ttl_seconds": 3600
    },
    "circuit_breaker": {
        "consecutive_5xx": 5,
        "interval_seconds": 30,
        "base_ejection_time_seconds": 30,
        "max_ejection_percent": 50
    },
    "connection_pool": {
        "max_connections_per_host": 1024,
        "max_pending_requests": 512,
        "max_retries": 3,
        "connect_timeout_ms": 5000,
        "idle_timeout_ms": 300000
    }
}

Response: 201 Created
{
    "id": "pool_8f3a2b1c",
    "name": "user-service-prod",
    "algorithm": "least_connections",
    "backend_count": 0,
    "healthy_count": 0,
    "version": 1,
    "created_at": "2024-01-15T10:00:00Z"
}
```

**Register Backend**
```http
POST /api/v1/pools/{pool_id}/backends
Authorization: Bearer <token>

Request:
{
    "address": "10.0.1.15:8080",
    "weight": 100,
    "priority": 0,
    "metadata": {
        "zone": "us-east-1a",
        "instance_id": "i-0abc123def",
        "version": "v2.3.1"
    },
    "max_connections": 500
}

Response: 201 Created
{
    "id": "backend_9d4e5f6a",
    "pool_id": "pool_8f3a2b1c",
    "address": "10.0.1.15:8080",
    "weight": 100,
    "health_status": "unknown",
    "created_at": "2024-01-15T10:05:00Z"
}
```

**Create Routing Rule**
```http
POST /api/v1/listeners/{listener_id}/rules
Authorization: Bearer <token>

Request:
{
    "priority": 100,
    "match": {
        "hosts": ["api.example.com"],
        "path_prefix": "/v2/orders",
        "methods": ["GET", "POST", "PUT"],
        "headers": {
            "X-Api-Version": "2"
        }
    },
    "action": {
        "type": "weighted_forward",
        "targets": [
            {"pool_id": "pool_orders_v2", "weight": 90},
            {"pool_id": "pool_orders_v3_canary", "weight": 10}
        ]
    },
    "rate_limit": {
        "requests_per_second": 10000,
        "burst_size": 20000,
        "scope": "per_rule"
    },
    "request_headers_to_add": {
        "X-Forwarded-By": "lb-cluster-1"
    },
    "response_headers_to_add": {
        "X-Backend-Pool": "{pool_name}"
    },
    "timeout_ms": 30000,
    "idle_timeout_ms": 3600000
}

Response: 201 Created
{
    "id": "rule_abc123",
    "listener_id": "listener_443",
    "priority": 100,
    "enabled": true,
    "version": 1,
    "created_at": "2024-01-15T10:10:00Z"
}
```

**Drain Backend (Graceful Removal)**
```http
POST /api/v1/pools/{pool_id}/backends/{backend_id}/drain
Authorization: Bearer <token>

Request:
{
    "drain_timeout_seconds": 300,
    "reason": "scheduled_maintenance"
}

Response: 202 Accepted
{
    "id": "backend_9d4e5f6a",
    "health_status": "draining",
    "active_connections": 45,
    "drain_started_at": "2024-01-15T11:00:00Z",
    "drain_deadline": "2024-01-15T11:05:00Z"
}
```

**Get Pool Status**
```http
GET /api/v1/pools/{pool_id}/status

Response: 200 OK
{
    "pool_id": "pool_8f3a2b1c",
    "name": "user-service-prod",
    "total_backends": 20,
    "healthy_backends": 18,
    "unhealthy_backends": 1,
    "draining_backends": 1,
    "active_connections": 15234,
    "requests_per_second": 45000,
    "average_response_time_ms": 12,
    "p99_response_time_ms": 85,
    "error_rate": 0.001,
    "backends": [
        {
            "id": "backend_9d4e5f6a",
            "address": "10.0.1.15:8080",
            "status": "healthy",
            "active_connections": 762,
            "weight_effective": 100,
            "response_time_avg_ms": 11,
            "requests_total": 1234567,
            "errors_total": 123
        }
    ]
}
```

### Internal gRPC APIs

```protobuf
syntax = "proto3";
package loadbalancer.v1;

// xDS-compatible discovery service
service ListenerDiscoveryService {
    rpc StreamListeners(DiscoveryRequest) returns (stream DiscoveryResponse);
    rpc FetchListeners(DiscoveryRequest) returns (DiscoveryResponse);
}

service RouteDiscoveryService {
    rpc StreamRoutes(DiscoveryRequest) returns (stream DiscoveryResponse);
    rpc FetchRoutes(DiscoveryRequest) returns (DiscoveryResponse);
}

service ClusterDiscoveryService {
    rpc StreamClusters(DiscoveryRequest) returns (stream DiscoveryResponse);
    rpc FetchClusters(DiscoveryRequest) returns (DiscoveryResponse);
}

service EndpointDiscoveryService {
    rpc StreamEndpoints(DiscoveryRequest) returns (stream DiscoveryResponse);
    rpc FetchEndpoints(DiscoveryRequest) returns (DiscoveryResponse);
}

// Health check service
service HealthService {
    rpc ReportHealth(HealthReport) returns (HealthAck);
    rpc GetClusterHealth(ClusterHealthRequest) returns (ClusterHealthResponse);
}
```

### Design Patterns

| Pattern | Implementation |
|---------|---------------|
| **Strategy Pattern** | Load balancing algorithms (RoundRobin, LeastConn, ConsistentHash implement same interface) |
| **Observer Pattern** | Config watchers notify LB nodes of changes via etcd watch streams |
| **State Pattern** | Backend health states (Healthy → Unhealthy → Draining) with defined transitions |
| **Chain of Responsibility** | Request processing pipeline (TLS → Route → RateLimit → Forward) |
| **Flyweight** | Connection reuse via HTTP/2 multiplexing and connection pooling |
| **Template Method** | Health check base with HTTP/TCP/gRPC specializations |
| **Proxy Pattern** | Core LB functionality — transparent proxying |
| **Memento** | Connection state snapshots for failover synchronization |

### Core Algorithm Implementations

#### Consistent Hashing with Virtual Nodes
```
Ring structure:
- 150 virtual nodes per physical backend
- SHA-256 hash for uniform distribution
- Binary search O(log n) for ring lookup
- Bounded load variant: max 1.25× average load per node

On backend add:
  1. Generate 150 hash points for new backend
  2. Insert into sorted ring
  3. Migrate only affected range of connections

On backend remove:
  1. Remove 150 hash points
  2. Next clockwise node absorbs traffic
  3. Only 1/N fraction of traffic remaps (N = number of backends)
```

#### Least Connections with Weighted Priority
```
Selection algorithm:
  1. Filter: only healthy backends
  2. Score: active_connections / weight
  3. Select: backend with lowest score
  4. Tiebreaker: random among equal scores
  5. Slow-start: new backends ramp up weight linearly over 30s

Connection counting:
  - Atomic increment on connection start
  - Atomic decrement on connection end
  - Per-node local counters (no shared state needed for L7)
```

## 7. Architecture Components Deep Dive

### 7.1 DNS / Global Server Load Balancing (GSLB)
```
Route 53 configuration:
- Latency-based routing records for each region
- Health checks on regional LB VIPs (every 10s)
- Failover records: primary region → secondary region
- TTL: 60 seconds (balance between freshness and DNS amplification)
- Weighted records for gradual region migration

Anycast BGP (for DDoS resilience):
- Same IP announced from multiple PoPs
- Closest PoP handles traffic (BGP shortest path)
- On PoP failure, BGP withdrawal → traffic shifts automatically
- Used by major CDNs: 1.1.1.1 (Cloudflare), 8.8.8.8 (Google)
```

### 7.2 Layer 4 Load Balancer (Deep Dive)
```
Technology: Linux kernel XDP/eBPF + DPDK for kernel bypass

Packet flow (DSR mode):
1. Client → Router (ECMP) → L4 LB node
2. L4 LB: hash(src_ip, src_port, dst_ip, dst_port) → select backend
3. L4 LB: rewrite destination MAC to backend MAC (L2 DSR)
   OR: encapsulate in IP-in-IP tunnel to backend (L3 DSR)
4. Backend processes request
5. Backend responds DIRECTLY to client (bypasses LB!)
   - Source IP is VIP (configured as loopback on backend)
   
Advantages of DSR:
- LB only handles inbound traffic (typically 10x less than outbound)
- LB bandwidth requirement reduced by 90%
- Lower latency (one fewer hop on response path)
- Supports any response size without LB bottleneck

Connection tracking:
- Consistent hash ensures same flow → same backend
- No per-connection state needed if hash is deterministic
- For stateful failover: conntrack sync between active/standby pair

Performance (per node):
- Throughput: 40 Gbps line rate
- Packets/sec: 20M PPS
- Latency added: < 100 microseconds
- Connections: 10M+ concurrent (conntrack table)
```

### 7.3 Layer 7 Load Balancer (Deep Dive)
```
Technology: Envoy Proxy / Custom Go implementation

Request processing pipeline:
1. Accept TCP connection from L4 tier
2. TLS handshake (if HTTPS):
   - SNI-based certificate selection
   - OCSP stapling for revocation check
   - Session ticket reuse (avoid full handshake)
3. HTTP parsing (HTTP/1.1 or HTTP/2 frame decoding)
4. Route matching (host → path → headers → method)
5. Apply request plugins:
   - Rate limiting
   - Authentication extraction
   - Request header manipulation
6. Backend selection (algorithm + health + circuit breaker)
7. Upstream connection (from connection pool)
8. Forward request, stream response back
9. Apply response plugins:
   - Header manipulation
   - Compression
10. Access logging (async, buffered)
11. Metrics emission (in-memory counters, scraped by Prometheus)

Connection pooling to backends:
- HTTP/1.1: pool of keep-alive connections per backend
- HTTP/2: single connection with 100 concurrent streams
- Idle timeout: 5 minutes
- Pool warm-up: pre-connect on backend registration
```

### 7.4 Health Checking Engine
```
Types of health checks:

1. Active health checks (LB → Backend):
   - HTTP: GET /healthz, expect 200
   - TCP: successful connection establishment
   - gRPC: grpc.health.v1.Health/Check
   - Custom script: execute command, check exit code
   
2. Passive health checks (observe traffic):
   - Track 5xx responses from backend
   - Track connection timeouts
   - Track connection resets
   - Combined with active for faster detection

Health state machine:
  UNKNOWN → HEALTHY (healthy_threshold consecutive successes)
  HEALTHY → UNHEALTHY (unhealthy_threshold consecutive failures)
  UNHEALTHY → HEALTHY (healthy_threshold consecutive successes)
  ANY → DRAINING (manual drain command)
  DRAINING → REMOVED (after drain_timeout or 0 active connections)

Panic mode:
  If > 50% backends unhealthy → keep routing to all (even unhealthy)
  Prevents total outage when health check itself is broken
  Alert immediately when panic mode activates
```

### 7.5 TLS Engine
```
TLS termination details:
- OpenSSL / BoringSSL with hardware AES-NI
- TLS 1.2 minimum, prefer TLS 1.3
- Certificate selection: SNI-based (multiple certs per listener)
- ECDHE key exchange: forward secrecy
- Session tickets: shared across LB nodes (encrypted ticket key rotation every 12h)
- OCSP stapling: pre-fetched, cached, reduces client-side latency
- 0-RTT (TLS 1.3): enabled for idempotent requests only (replay risk)

Performance:
- RSA-2048 handshakes: ~1,500/sec per core (without hardware)
- ECDSA P-256 handshakes: ~10,000/sec per core
- Resumed sessions (ticket): ~50,000/sec per core
- With hardware acceleration (Intel QAT): 10x throughput

Certificate management:
- Auto-renewal via ACME/Let's Encrypt (30 days before expiry)
- Hot-reload: new cert loaded without dropping connections
- Wildcard certificates for dynamic subdomains
- Fallback/default certificate for unknown SNI
```

### 7.6 Control Plane
```
Architecture: 3-node etcd cluster + Config API service

Config propagation:
1. Admin makes change via API
2. API validates and writes to etcd (strong consistency)
3. Each LB node watches etcd keys
4. On change event:
   a. Download new config snapshot
   b. Validate locally (syntax, references)
   c. Hot-swap in-memory config (atomic pointer swap)
   d. Old config GC'd after in-flight requests complete
5. Propagation time: < 5 seconds to all nodes

Rollback:
- etcd maintains revision history
- Rollback API: restore to any previous revision
- Canary mode: apply change to 1 node first, validate, then roll out

Service discovery integration:
- Kubernetes: watch Endpoints/EndpointSlice resources
- Consul: watch service catalog changes
- Auto-register: new pods → new backends in pool
- Auto-deregister: terminated pods removed from pool
```

## 8. Deep Dive: Load Balancing Algorithms

### 8.1 Round Robin
```
State: single atomic counter per pool
Selection: backends[counter.IncrementAndGet() % len(backends)]
Complexity: O(1)
Pros: Simple, even distribution over time
Cons: Ignores backend load, slow backends get same traffic
```

### 8.2 Weighted Round Robin
```
Algorithm (smooth weighted round robin):
  For each selection:
    1. current_weight[i] += effective_weight[i] for all backends
    2. selected = backend with max current_weight
    3. current_weight[selected] -= total_weight
    
Example: A(5), B(1), C(1) — total=7
  Round 1: A=5, B=1, C=1 → select A → A=-2, B=1, C=1
  Round 2: A=3, B=2, C=2 → select A → A=-4, B=2, C=2
  Round 3: A=1, B=3, C=3 → select B → A=1, B=-4, C=3
  Sequence: A,A,B,A,C,A,A (smooth distribution, no bursts to A)
```

### 8.3 Least Connections
```
Selection:
  min(active_connections[i] / weight[i]) for all healthy backends
  Tiebreaker: random

Implementation:
  - Atomic counter per backend (increment on new connection, decrement on close)
  - O(n) scan or priority queue O(log n) for large pools
  - Power of 2 random choices: pick 2 random backends, choose less loaded
    - Reduces scan to O(1) with near-optimal distribution
```

### 8.4 Consistent Hashing (Detailed)
```
Implementation: Jump consistent hash OR Ketama ring

Ketama ring:
  - 150 points per backend on [0, 2^32) ring
  - Point = MD5(backend_address + "#" + replica_index)
  - Lookup: hash(request_key) → binary search ring → find next clockwise point
  - Bounded load extension:
    - Each node has capacity = ceil(avg_load × 1.25)
    - If selected node at capacity, move clockwise to next available

Request key selection:
  - Session affinity: hash(client_ip) or hash(cookie_value)
  - Cache affinity: hash(url_path) — ensures same backend serves same URLs
  - Custom: hash(header_value) — e.g., hash(X-Tenant-ID)
```

### 8.5 Least Response Time
```
Algorithm:
  score[i] = active_connections[i] × avg_response_time_ms[i]
  selected = argmin(score[i])

Response time tracking:
  - Exponentially Weighted Moving Average (EWMA)
  - alpha = 0.3 (recent history weighted more)
  - new_avg = alpha × latest_time + (1 - alpha) × old_avg
  - Decay: if no requests for 30s, gradually reset to baseline
```

### 8.6 Maglev Hashing (Google's approach)
```
Lookup table: fixed size (prime number, e.g., 65537)
Each backend generates a permutation of table indices
Populate table greedily: backends take turns claiming indices

Advantages over ring-based:
- O(1) lookup (direct table index)
- Better load distribution (bounded imbalance)
- Faster rebuild on change (O(M×N) where M=table_size, N=backends)

Used when: very high PPS (millions), need deterministic O(1) lookup
```

## 9. Component Optimization

### 9.1 Kernel Bypass (DPDK/XDP)
```
Traditional path: NIC → kernel network stack → user space → kernel → NIC
DPDK path:       NIC → user space (poll mode driver) → NIC

Benefits:
- Zero copy: no data movement between kernel and user space
- Poll mode: no interrupt overhead (busy-polling)
- Batch processing: handle multiple packets per loop iteration
- Huge pages: reduced TLB misses for large connection tables

Performance improvement: 10-20x packets per second vs kernel networking
Use case: L4 load balancing where every microsecond counts
```

### 9.2 Connection Pooling Optimization
```
HTTP/2 multiplexing:
- Single TCP connection carries 100+ concurrent streams
- Head-of-line blocking eliminated at HTTP level
- Reduces connection establishment overhead by 100x
- Flow control per stream and per connection

Pool sizing formula:
  max_pool_size = peak_concurrent_requests / max_streams_per_connection
  Example: 50,000 concurrent requests / 100 streams = 500 connections per backend

Warm connection pool:
- On backend registration: immediately establish min_connections
- Background keepalive pings every 30s
- On connection error: immediate reconnect (don't wait for request)
```

### 9.3 Async Processing
```
Request logging (Kafka):
- Batch access logs in memory (64KB buffer or 100ms flush)
- Async write to Kafka (no backpressure on request path)
- If Kafka unavailable: local disk buffer, replay later
- Topic partitioning: by hash(listener_id) for ordering

Health check execution (async workers):
- Dedicated goroutine pool for health checks
- Non-blocking: health check results don't block traffic routing
- Stagger checks: avoid thundering herd of simultaneous checks
- Jitter: random delay 0-interval_ms to spread load

Metrics collection:
- In-memory atomic counters (zero allocation on hot path)
- Background scrape by Prometheus every 15s
- Histogram bucketing: pre-computed percentiles
```

### 9.4 Database Indexing & Partitioning
```
etcd key structure (hierarchical):
  /lb/pools/{pool_id}/config          → pool configuration
  /lb/pools/{pool_id}/backends/{id}    → backend entry
  /lb/listeners/{id}/config            → listener configuration
  /lb/listeners/{id}/rules/{priority}  → routing rules
  /lb/certs/{domain}                   → SSL certificates

Benefits:
- Prefix watch: watch /lb/pools/{pool_id}/ → get all changes for a pool
- Range queries: list all backends for a pool efficiently
- Revision-based consistency: snapshot reads at specific revision

ClickHouse (for access logs):
  PARTITION BY toYYYYMMDD(timestamp)
  ORDER BY (pool_id, backend_id, timestamp)
  TTL timestamp + INTERVAL 30 DAY
  
  ReplicatedMergeTree for HA
  Distributed table for cross-shard queries
```

### 9.5 Zero-Downtime Configuration Reload
```
Hot reload mechanism (atomic config swap):

1. Current state: version N serving traffic
2. New config arrives via etcd watch
3. Background goroutine:
   a. Parse and validate new config
   b. Build new route table (radix tree)
   c. Build new backend pool state
   d. Atomic pointer swap: atomic.StorePointer(&activeConfig, newConfig)
4. In-flight requests complete with old config (reference held)
5. Old config garbage collected

Key properties:
- Zero dropped connections
- Zero increased latency during reload
- Validation before activation (bad config → reject, keep old)
- Instant rollback: swap pointer back to previous version
```

### 9.6 SSL Session Caching (Distributed)
```
Challenge: client may hit different LB node on reconnect, lose session

Solution 1: Shared session ticket keys
  - All LB nodes share encryption key for session tickets
  - Key rotation every 12 hours (keep previous 2 keys for decrypt)
  - Distribution via etcd/Vault (encrypted at rest)

Solution 2: External session cache (Redis)
  - Session ID → session state mapping in Redis
  - TTL: 1 hour
  - Only for TLS 1.2 (TLS 1.3 uses tickets exclusively)
  
Performance impact:
  - Full handshake: 2 RTT, ~5ms CPU
  - Resumed (ticket): 1 RTT, ~0.1ms CPU
  - Session reuse rate target: > 80%
```

### 9.7 DDoS Mitigation at LB Level
```
SYN flood protection:
  - SYN cookies: stateless SYN-ACK, validate on ACK
  - No connection state until 3-way handshake completes
  - Capacity: 10M+ SYN/sec with SYN cookies

Slowloris protection:
  - Request header timeout: 10s
  - Request body timeout: 30s
  - Max headers: 100
  - Max header size: 8KB
  - Close slow connections aggressively

Amplification protection:
  - Rate limit new connections per source IP: 100/sec
  - Connection limit per source IP: 1000
  - Geographic rate limiting: per country limits during attack
  
Auto-mitigation pipeline:
  1. Flink job detects traffic anomaly (10x spike from IP range)
  2. Publishes to mitigation topic
  3. LB nodes subscribe, add temporary block rules
  4. Auto-expire after 30 minutes, re-evaluate
```

## 10. Observability

### 10.1 Metrics (Prometheus/Grafana)
```yaml
# Traffic metrics
lb_connections_active{listener, protocol}                    # Gauge
lb_connections_total{listener, protocol, result}            # Counter
lb_requests_total{listener, pool, backend, method, status}  # Counter
lb_request_duration_seconds{listener, pool, method}         # Histogram
lb_request_size_bytes{listener}                             # Histogram
lb_response_size_bytes{listener, pool}                      # Histogram
lb_bandwidth_bytes{direction, listener}                     # Counter

# Backend health
lb_backend_health{pool, backend, status}                    # Gauge (0=unhealthy, 1=healthy)
lb_backend_active_connections{pool, backend}                # Gauge
lb_backend_requests_total{pool, backend, status}            # Counter
lb_backend_response_time_seconds{pool, backend}             # Histogram
lb_backend_circuit_breaker_state{pool, backend}             # Gauge

# Pool metrics
lb_pool_healthy_backends{pool}                              # Gauge
lb_pool_total_backends{pool}                                # Gauge
lb_pool_pending_requests{pool}                              # Gauge
lb_pool_overflow_total{pool}                                # Counter (queue full)

# TLS metrics
lb_tls_handshakes_total{version, cipher, resumed}           # Counter
lb_tls_handshake_duration_seconds{version}                  # Histogram
lb_tls_cert_expiry_seconds{domain}                          # Gauge
lb_tls_errors_total{type}                                   # Counter

# System metrics
lb_config_version                                           # Gauge
lb_config_reload_total{status}                              # Counter
lb_config_reload_duration_seconds                           # Histogram
lb_memory_bytes{type}                                       # Gauge
lb_connection_table_size                                    # Gauge
lb_goroutines                                               # Gauge
```

### 10.2 Distributed Tracing
```
Trace headers propagation:
- Incoming: extract traceparent, tracestate (W3C) or X-B3-* (Zipkin)
- If absent: generate new trace ID at LB
- Add span: lb_route_match, lb_backend_selection, lb_upstream_request
- Forward: inject trace headers to upstream request

Span attributes:
- lb.node_id, lb.listener, lb.pool, lb.backend
- lb.algorithm, lb.retry_count, lb.circuit_breaker_state
- upstream.address, upstream.latency_ms
- tls.version, tls.cipher, tls.resumed

Sampling:
- 100% for errors (5xx, timeouts)
- 1% for successful requests
- Adaptive: increase sampling when error rate rises
```

### 10.3 Logging
```json
{
    "timestamp": "2024-01-15T10:30:00.123456Z",
    "level": "info",
    "component": "l7_lb",
    "node_id": "lb-node-05",
    "event": "request_complete",
    "trace_id": "abc123",
    "connection_id": "conn_789",
    "client": {
        "ip": "203.0.113.42",
        "port": 54321,
        "tls_version": "TLSv1.3",
        "tls_cipher": "TLS_AES_128_GCM_SHA256",
        "h2_stream_id": 13
    },
    "request": {
        "method": "POST",
        "host": "api.example.com",
        "path": "/v1/orders",
        "size_bytes": 1256,
        "duration_ms": 0.8
    },
    "routing": {
        "listener": "https_443",
        "rule_id": "rule_abc123",
        "pool": "order-service-prod",
        "algorithm": "least_connections"
    },
    "upstream": {
        "address": "10.0.1.15:8080",
        "attempt": 1,
        "connect_time_ms": 0.3,
        "response_time_ms": 45,
        "status": 201,
        "response_size_bytes": 512
    },
    "total_duration_ms": 46.1
}
```

### 10.4 Alerting
```yaml
# Critical (page immediately)
- alert: LBNodeDown
  expr: up{job="load-balancer"} == 0
  for: 30s
  severity: critical

- alert: AllBackendsUnhealthy
  expr: lb_pool_healthy_backends == 0
  for: 10s
  severity: critical
  
- alert: HighErrorRate
  expr: rate(lb_requests_total{status=~"5.."}[1m]) / rate(lb_requests_total[1m]) > 0.05
  for: 1m
  severity: critical

- alert: ConnectionTableNearFull
  expr: lb_connection_table_size / lb_connection_table_max > 0.9
  for: 2m
  severity: critical

# Warning
- alert: BackendUnhealthy
  expr: lb_backend_health == 0
  for: 1m
  severity: warning

- alert: HighLatency
  expr: histogram_quantile(0.99, lb_request_duration_seconds) > 1
  for: 3m
  severity: warning

- alert: CertExpiryApproaching
  expr: lb_tls_cert_expiry_seconds < 7 * 24 * 3600
  for: 1h
  severity: warning

- alert: CircuitBreakerOpen
  expr: lb_backend_circuit_breaker_state == 1
  for: 30s
  severity: warning
```

### 10.5 Dashboards
```
Dashboard 1: LB Overview
- Total RPS across all listeners
- Active connections gauge
- Error rate (4xx vs 5xx)
- p50/p95/p99 latency
- Bandwidth in/out
- TLS handshake rate

Dashboard 2: Backend Pool Health
- Healthy vs unhealthy backends per pool
- Per-backend connection count
- Per-backend response time heatmap
- Circuit breaker states
- Connection pool utilization

Dashboard 3: Traffic Distribution
- RPS per backend (ensure even distribution)
- Request distribution by weight
- Canary traffic split visualization
- Geographic traffic distribution

Dashboard 4: Capacity Planning
- Connection table utilization trend
- CPU/memory per LB node
- Bandwidth utilization vs capacity
- SSL handshake rate vs capacity
- Projection: days until capacity
```

## 11. Considerations and Assumptions

### Key Assumptions
1. **Cloud/bare-metal hybrid**: Designed to work in both environments (cloud NLB + custom L7, or fully custom)
2. **East-West + North-South**: Primary focus on North-South (ingress) traffic; service mesh handles East-West
3. **Stateless L7 nodes**: Any L7 node can serve any request (no local session state critical for correctness)
4. **Backend auto-scaling**: Backends scale independently; LB adapts via service discovery
5. **Hardware**: Modern servers with 40Gbps NICs, AES-NI, multiple CPU cores
6. **Network**: Dedicated network for LB tier, separate from application traffic

### Design Decisions

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| L4 technology | DPDK/XDP | IPVS/iptables | 10x better PPS performance |
| L7 technology | Envoy | NGINX/HAProxy | xDS protocol, gRPC native, better observability |
| Config store | etcd | ZooKeeper/Consul | Better watch semantics, proven at scale (Kubernetes uses it) |
| L4 mode | DSR | Full proxy (SNAT) | 90% bandwidth reduction at LB |
| Failover | ECMP + VRRP | Single VIP | Eliminates single LB bottleneck |
| Health check | Active + Passive | Active only | Faster detection (passive catches in-band errors) |

### Trade-offs

| Trade-off | Chosen Side | Cost |
|-----------|-------------|------|
| Latency vs Features | L4 raw speed, L7 rich features | Need two tiers (complexity) |
| DSR vs Full Proxy | DSR (L4 bandwidth savings) | Cannot modify responses at L4, client sees real backend IP |
| Consistent Hashing vs Round Robin | Consistent hashing for stateful | Uneven distribution possible with few backends |
| Stateless LB vs Session State | Stateless (scale freely) | Need external state for sticky sessions (cookie) |
| TLS at LB vs TLS passthrough | Terminate at LB (inspect traffic) | LB becomes security boundary, must protect keys |

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Single LB node failure | 1/N traffic temporarily disrupted | ECMP redistributes in < 3s; connection retry |
| All backends unhealthy | Service unavailable | Panic mode: route to "unhealthy" anyway + alert |
| Config corruption | Misrouted traffic | Validate before apply; instant rollback |
| DDoS attack | Saturation | L4 SYN cookies, rate limiting, upstream CDN/WAF |
| Certificate expiry | TLS errors for all clients | Auto-renewal 30 days early; monitoring alert at 7 days |
| Network partition (LB ↔ backends) | False unhealthy detection | Multiple health check paths; panic mode threshold |
| etcd cluster failure | No config updates (existing config still works) | LB operates with cached config; etcd HA (3+ nodes) |

### Capacity Planning
```
When to add LB nodes:
- Connection table > 70% full
- CPU > 70% sustained
- Bandwidth > 80% of NIC capacity
- p99 latency increasing trend
- Adding new backend pools/services

Growth formula:
  Required L4 nodes = peak_PPS / PPS_per_node × 1.5 (headroom)
  Required L7 nodes = peak_RPS / RPS_per_node × 1.5 (headroom)
  
  Review quarterly; auto-scale L7 tier based on metrics
```

### Security Considerations
- LB nodes run in isolated network segment (DMZ)
- No SSH access to LB nodes in production (immutable infrastructure)
- Control plane API requires mTLS + RBAC
- Certificate private keys never leave HSM/KMS
- Rate limiting at LB prevents single client from exhausting backend capacity
- Audit log for all configuration changes
- Periodic penetration testing of LB infrastructure
