# URL Shortener (TinyURL / Bitly) - Complete System Design

## 1. Functional Requirements

### Core Features
| # | Feature | Description |
|---|---------|-------------|
| F1 | Create Short URL | Given a long URL, generate a unique short URL (7-char Base62 code) |
| F2 | Custom Aliases | Allow users to pick a custom short code (e.g., `sho.rt/summer-sale`) |
| F3 | Redirect | Resolve short URL to original long URL with 301/302/307 redirect |
| F4 | TTL / Expiration | Support time-to-live; expired links return 410 Gone |
| F5 | Batch Creation | Create up to 1000 short URLs in a single API call |
| F6 | Custom Domains | Tenants can bring their own domain (e.g., `go.acme.com`) |
| F7 | Click Analytics | Track clicks per link with geo, device, referrer breakdowns |
| F8 | Link Management | Update destination, pause, delete, restore links |
| F9 | Abuse Prevention | Detect and quarantine phishing/malware links |
| F10 | Preview Mode | Allow users to preview destination without redirecting |

### User Roles
- **Anonymous User**: Can only be redirected (read path)
- **Authenticated User**: Create, manage, and view analytics for their links
- **Admin**: Quarantine, audit, investigate, replay, and policy management

---

## 2. Non-Functional Requirements

| Requirement | Target | Justification |
|-------------|--------|---------------|
| **Availability** | 99.99% (52 min downtime/year) | Revenue-critical redirect path |
| **Redirect Latency** | p50 < 30ms, p99 < 100ms | User experience on every click |
| **Create Latency** | p50 < 100ms, p99 < 300ms | Not on hot path; can tolerate more |
| **Consistency** | Strong for writes, eventual for reads/analytics | No duplicate codes; analytics can lag |
| **Durability** | Zero acknowledged write loss | Link mappings are the core asset |
| **Scalability** | 100x growth without re-architecture | Horizontal scaling at every layer |
| **Security** | Encrypt at rest + transit, abuse detection | Prevent platform misuse |
| **Geo-distribution** | Multi-region read replicas, single-writer per namespace | Low latency globally |

---

## 3. Capacity Estimation

### Traffic Assumptions

```
DAU:                    10M users
MAU:                    80M users
Read:Write ratio:       25:1 (reads dominate - redirect heavy)
```

### QPS Calculations

```
=== WRITE PATH (Create Short URLs) ===
Daily creates:          10M DAU x 0.2 links/user = 2M creates/day
Average QPS:            2,000,000 / 86,400 = ~23 QPS
                        (round up for B2B batch: ~2,000 QPS avg)
Peak QPS:               2,000 x 5 (peak multiplier) = 10,000 QPS
Spike QPS:              2,000 x 10 (flash sale/viral event) = 20,000 QPS

=== READ PATH (Redirects) ===
Daily redirects:        50M redirects/day (5 clicks per link on avg)
Average QPS:            50,000,000 / 86,400 = ~580 QPS
                        (realistic platform: ~50,000 QPS avg)
Peak QPS:               50,000 x 5 = 250,000 QPS
Viral spike:            50,000 x 20 = 1,000,000 QPS (single viral link)
```

### Storage Calculations

```
=== LINK METADATA ===
Record size:            ~1 KB (code + long_url + metadata + indexes)
Total links (5 years):  2M/day x 365 x 5 = 3.65 Billion links
Raw storage:            3.65B x 1 KB = 3.65 TB
With replication (3x):  3.65 TB x 3 = ~11 TB

=== CLICK EVENTS (Analytics) ===
Event size:             ~200 bytes (hashed fields, no PII)
Daily events:           50M redirects/day
Daily event storage:    50M x 200 B = 10 GB/day
Monthly:                10 GB x 30 = 300 GB/month
Yearly (compressed):    300 GB x 12 x 0.3 (compression) = ~1 TB/year

=== CACHE SIZING ===
Hot links (top 20%):    3.65B x 0.002 (active hot) = 7.3M keys
Cache entry:            ~500 bytes (code -> redirect metadata)
Cache memory:           7.3M x 500 B = 3.65 GB
With overhead (2x):     ~8 GB per Redis node
Redis cluster (3 shards, 3 replicas): ~72 GB total
```

### Network Bandwidth

```
=== INBOUND (Creates) ===
Avg request size:       500 bytes
Peak inbound:           10,000 QPS x 500 B = 5 MB/s

=== OUTBOUND (Redirects) ===
Avg response size:      300 bytes (302 + headers + Location)
Peak outbound:          250,000 QPS x 300 B = 75 MB/s
CDN handles:            ~80% of traffic = 60 MB/s offloaded
Origin outbound:        ~15 MB/s
```

### Code Space Analysis

```
Base62 characters:      [a-z, A-Z, 0-9] = 62 chars
Code length = 7:        62^7 = 3,521,614,606,208 (~3.5 trillion codes)
At 2M creates/day:      3.5T / 2M = 4,794 years before exhaustion
Collision probability:  Negligible with range allocation
```

---

## 4. Data Modeling

### Database Choice Justification

| Store | Technology | Justification |
|-------|-----------|---------------|
| Link Metadata (Primary) | **DynamoDB** or **ScyllaDB** | Key-value access pattern `(domain_id, code) -> URL`; massive scale, single-digit ms reads |
| Account/Domain Metadata | **PostgreSQL** | Relational constraints, ACID for billing/auth, moderate scale |
| Cache Layer | **Redis Cluster** | Sub-ms reads, TTL support, pub/sub for invalidation |
| Event Stream | **Apache Kafka** | Durable, ordered, replayable event log |
| Analytics Store | **ClickHouse** | Columnar OLAP, fast aggregations on billions of click events |
| Search/Admin | **OpenSearch** | Full-text search on URLs, tags, owners |
| Object Storage | **S3** | Audit exports, evidence files, backups |

### DynamoDB Schema - Link Mappings (Primary Store)

```
Table: link_mappings
-------------------------------------------------------------
Partition Key:  domain_id (String)    -- e.g., "dom_01abc"
Sort Key:       code (String)         -- e.g., "aZ81kLm"

Attributes:
  link_id           String    -- Unique ID: "lnk_01J..."
  long_url          String    -- Encrypted destination URL
  long_url_hash     String    -- SHA-256 for dedup lookup
  owner_id          String    -- User/tenant who created
  tenant_id         String    -- Multi-tenant isolation
  redirect_type     Number    -- 301, 302, or 307
  status            String    -- ACTIVE|EXPIRED|QUARANTINED|DELETED|PENDING_SCAN
  expires_at        Number    -- Unix epoch (0 = never)
  version           Number    -- Optimistic concurrency
  tags              List<S>   -- User-defined tags
  created_at        Number    -- Unix epoch ms
  updated_at        Number    -- Unix epoch ms

GSI-1 (Owner Index):
  Partition Key:  owner_id
  Sort Key:       created_at
  Projects:       link_id, domain_id, code, status, long_url_hash

GSI-2 (Expiry Index):
  Partition Key:  status
  Sort Key:       expires_at
  Projects:       domain_id, code, link_id
  (Used by expiry worker to find ACTIVE links past TTL)

GSI-3 (URL Hash Index):
  Partition Key:  long_url_hash
  Sort Key:       domain_id
  Projects:       code, owner_id, status
  (Optional: detect duplicate URLs for same owner)
```

### PostgreSQL Schema - Accounts & Domains

```sql
-- Users / Accounts
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    role            VARCHAR(20) NOT NULL DEFAULT 'member',
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);

-- Tenants (Multi-tenancy)
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    plan            VARCHAR(50) NOT NULL DEFAULT 'free',
    rate_limit_qps  INTEGER NOT NULL DEFAULT 100,
    max_links       BIGINT NOT NULL DEFAULT 10000,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Custom Domains
CREATE TABLE custom_domains (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    hostname            VARCHAR(255) NOT NULL UNIQUE,
    tls_status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    verification_token  VARCHAR(255) NOT NULL,
    verified_at         TIMESTAMPTZ,
    home_region         VARCHAR(20) NOT NULL DEFAULT 'us-east-1',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_domains_tenant ON custom_domains(tenant_id);
CREATE UNIQUE INDEX idx_domains_hostname ON custom_domains(hostname);

-- Idempotency Keys
CREATE TABLE idempotency_keys (
    scope           VARCHAR(100) NOT NULL,   -- tenant_id or user_id
    idempotency_key VARCHAR(255) NOT NULL,
    request_hash    VARCHAR(64) NOT NULL,    -- SHA-256 of request body
    response_json   JSONB,
    state           VARCHAR(20) NOT NULL DEFAULT 'reserved',
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scope, idempotency_key)
);

CREATE INDEX idx_idem_expires ON idempotency_keys(expires_at)
    WHERE state = 'reserved';

-- Code Range Allocations (for Snowflake-style allocation)
CREATE TABLE code_allocations (
    allocator_id    VARCHAR(100) NOT NULL,   -- service instance ID
    domain_id       VARCHAR(100) NOT NULL,
    range_start     BIGINT NOT NULL,
    range_end       BIGINT NOT NULL,
    next_value      BIGINT NOT NULL,
    state           VARCHAR(20) NOT NULL DEFAULT 'active',
    leased_until    TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (allocator_id, domain_id)
);

-- Audit Log (Append-only)
CREATE TABLE audit_log (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id        VARCHAR(100) NOT NULL,
    actor_type      VARCHAR(20) NOT NULL,    -- user, admin, system
    action          VARCHAR(100) NOT NULL,   -- link.created, link.quarantined
    resource_type   VARCHAR(50) NOT NULL,
    resource_id     VARCHAR(100) NOT NULL,
    reason          TEXT,
    before_state    JSONB,
    after_state     JSONB,
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Partition monthly
CREATE TABLE audit_log_2026_01 PARTITION OF audit_log
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE audit_log_2026_02 PARTITION OF audit_log
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE INDEX idx_audit_resource ON audit_log(resource_id, created_at);
CREATE INDEX idx_audit_actor ON audit_log(actor_id, created_at);

-- Abuse Reports
CREATE TABLE abuse_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    link_id         VARCHAR(100) NOT NULL,
    reporter_id     VARCHAR(100),
    reason          VARCHAR(100) NOT NULL,
    evidence_ref    VARCHAR(255),
    state           VARCHAR(20) NOT NULL DEFAULT 'open',
    decided_by      VARCHAR(100),
    decision        VARCHAR(20),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at      TIMESTAMPTZ
);

CREATE INDEX idx_abuse_link ON abuse_reports(link_id);
CREATE INDEX idx_abuse_state ON abuse_reports(state, created_at);
```

### ClickHouse Schema - Click Analytics

```sql
CREATE TABLE click_events (
    event_id        String,
    domain_id       String,
    code            String,
    link_id         String,
    owner_id        String,
    tenant_id       String,
    clicked_at      DateTime64(3),
    country         LowCardinality(String),
    region          LowCardinality(String),
    city            String,
    device_type     LowCardinality(String),   -- mobile, desktop, tablet
    os              LowCardinality(String),
    browser         LowCardinality(String),
    referrer_domain LowCardinality(String),
    ip_prefix_hash  String,                    -- hashed /24 prefix
    user_agent_hash String,
    cache_status    LowCardinality(String),    -- edge_hit, redis_hit, db_hit
    is_bot          UInt8
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(clicked_at)
ORDER BY (tenant_id, domain_id, code, clicked_at)
TTL clicked_at + INTERVAL 2 YEAR
SETTINGS index_granularity = 8192;

-- Materialized view for hourly rollups
CREATE MATERIALIZED VIEW click_hourly_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (tenant_id, domain_id, code, hour, country, device_type)
AS SELECT
    tenant_id,
    domain_id,
    code,
    toStartOfHour(clicked_at) AS hour,
    country,
    device_type,
    count() AS click_count,
    uniqExact(ip_prefix_hash) AS unique_visitors
FROM click_events
GROUP BY tenant_id, domain_id, code, hour, country, device_type;
```

### Partitioning & Sharding Strategy

```
DynamoDB Link Mappings:
  - Partition Key: domain_id (even distribution across custom domains)
  - Sort Key: code (allows range queries within a domain)
  - Auto-scaling: On-demand capacity or provisioned with auto-scale
  - Global Tables: Multi-region replication for DR

PostgreSQL:
  - Horizontal: Partition audit_log by month (time-series)
  - Vertical: Separate schemas for auth, billing, abuse
  - Read replicas: 2 per region for read-heavy admin queries

ClickHouse:
  - Partition: Monthly by clicked_at
  - Sharding: By tenant_id hash (ReplicatedMergeTree)
  - Replication: 2 replicas per shard

Redis:
  - Hash slots: 16384 slots across 6 nodes (3 primary + 3 replica)
  - Key pattern: "{domain_id}:{code}" -> ensures co-location
```

---

## 5. High-Level Design (HLD)

### Architecture Diagram

```
                           +-------------------+
                           |   DNS (Route53)   |
                           |   Global Traffic  |
                           +--------+----------+
                                    |
                           +--------v----------+
                           |   CDN (CloudFront)|
                           |   Edge Caching    |
                           |   WAF/Bot Detect  |
                           +--------+----------+
                                    |
                    +---------------+---------------+
                    |                               |
           +-------v-------+               +-------v-------+
           | API Gateway   |               | Edge Worker   |
           | (Management)  |               | (Redirect)    |
           | Auth + Quota  |               | Cache-first   |
           +-------+-------+               +-------+-------+
                   |                               |
        +----------+----------+                    |
        |                     |                    |
+-------v-------+    +-------v-------+    +-------v-------+
| Link Mgmt     |    | Analytics     |    | Redirect      |
| Service       |    | Service       |    | Service       |
| (Create/CRUD) |    | (Query)       |    | (Resolve)     |
+-------+-------+    +-------+-------+    +-------+-------+
        |                     |                    |
        |              +------v------+      +------v------+
        |              | ClickHouse  |      | Redis       |
        |              | (OLAP)      |      | Cluster     |
        |              +-------------+      +------+------+
        |                                          |
+-------v---------+                         +------v------+
| Code Allocator  |                         | DynamoDB    |
| Service         |                         | (Link Store)|
+-----------------+                         +-------------+
        |
+-------v---------+         +------------------+
| PostgreSQL      |         | Kafka Cluster    |
| (Accounts/Auth) |         | (Event Bus)      |
+-----------------+         +--------+---------+
                                     |
                    +----------------+----------------+
                    |                |                |
           +-------v---+    +-------v---+    +-------v---+
           | Click      |    | Abuse     |    | Cache     |
           | Analytics  |    | Scanner   |    | Warmer    |
           | Consumer   |    | Worker    |    | Worker    |
           +-----------+    +-----------+    +-----------+
```

### Service Decomposition

| Service | Pattern | Responsibility |
|---------|---------|---------------|
| **Link Management Service** | CQRS (Command) | Create, update, delete links; idempotency; outbox events |
| **Redirect Service** | CQRS (Query) | Resolve codes; cache-first; emit click events async |
| **Code Allocator Service** | Singleton per region | Lease numeric ranges; Base62 encode; zero-collision |
| **Analytics Service** | Query/Read model | Serve pre-aggregated click data from ClickHouse |
| **Abuse Scanner Worker** | Event-driven | Consume scan requests; check URL reputation; quarantine |
| **Cache Warmer Worker** | Event-driven | Detect hot links; proactively warm Redis/CDN |
| **Expiry Worker** | Scheduled | Mark expired links; invalidate caches |
| **Reconciliation Worker** | Scheduled | Compare stores; detect drift; self-heal |

### Data Flow - Create Path

```
1. Client -> API Gateway (auth, rate limit, validate)
2. API Gateway -> Link Management Service
3. Link Mgmt -> Check idempotency store (PostgreSQL)
4. Link Mgmt -> URL Normalizer (canonicalize URL)
5. Link Mgmt -> Safety Precheck (block obvious abuse)
6. Link Mgmt -> Code Allocator (get unique code)
7. Link Mgmt -> DynamoDB (conditional put: domain_id + code)
8. Link Mgmt -> PostgreSQL (save idempotency result)
9. Link Mgmt -> Kafka (publish link.created event via outbox)
10. Link Mgmt -> Return 201 to client
```

### Data Flow - Redirect Path

```
1. Client -> CDN Edge (check cache)
2. CDN miss -> Redirect Service
3. Redirect Service -> Local LRU Cache (check)
4. Local miss -> Redis Cluster (check)
5. Redis miss -> DynamoDB (lookup domain_id + code)
6. Validate: status=ACTIVE, expires_at > now, not quarantined
7. Return 302 + Location header
8. Async: Emit click event to Kafka (fire-and-forget with buffer)
```

### Outbox Pattern for Event Publishing

```
Transaction boundary (atomic):
  1. Write link_mappings to DynamoDB
  2. Write outbox_events to DynamoDB (same table or separate)

Outbox Relay (async):
  3. CDC/Polling reads uncommitted outbox events
  4. Publishes to Kafka topic
  5. Marks outbox event as published
```

---

## 6. Low-Level Design (LLD)

### API Endpoints - Complete Contracts

#### POST /v1/short-links (Create Short URL)

**Request:**
```http
POST /v1/short-links HTTP/1.1
Host: api.sho.rt
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json
X-Request-ID: req_01H8MZXYZ

{
  "long_url": "https://example.com/products/123?ref=summer&utm_source=twitter",
  "custom_alias": null,
  "domain": "sho.rt",
  "expires_at": "2026-12-31T23:59:59Z",
  "redirect_type": 302,
  "tags": ["campaign", "summer-2026"]
}
```

**Success Response (201):**
```http
HTTP/1.1 201 Created
Content-Type: application/json
X-Request-ID: req_01H8MZXYZ
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 599
X-RateLimit-Reset: 1716854400

{
  "data": {
    "id": "lnk_01J8ABC123DEF456",
    "code": "aZ81kLm",
    "short_url": "https://sho.rt/aZ81kLm",
    "long_url": "https://example.com/products/123?ref=summer&utm_source=twitter",
    "domain": "sho.rt",
    "redirect_type": 302,
    "status": "ACTIVE",
    "expires_at": "2026-12-31T23:59:59Z",
    "tags": ["campaign", "summer-2026"],
    "version": 1,
    "created_at": "2026-05-28T10:15:30Z",
    "updated_at": "2026-05-28T10:15:30Z"
  },
  "meta": {
    "request_id": "req_01H8MZXYZ"
  }
}
```

**Error Responses:**

```json
// 400 Bad Request - Invalid URL
{
  "error": {
    "code": "INVALID_URL",
    "message": "The provided URL is not valid",
    "details": [
      {"field": "long_url", "issue": "URL scheme must be http or https"}
    ]
  },
  "meta": {"request_id": "req_01H8MZXYZ"}
}

// 409 Conflict - Custom alias already exists
{
  "error": {
    "code": "ALIAS_CONFLICT",
    "message": "The custom alias 'summer-sale' is already in use on domain 'sho.rt'",
    "details": [
      {"field": "custom_alias", "issue": "Alias already exists for this domain"}
    ]
  },
  "meta": {"request_id": "req_01H8MZXYZ"}
}

// 422 Unprocessable - URL blocked by safety policy
{
  "error": {
    "code": "URL_BLOCKED",
    "message": "The destination URL was blocked by our safety policy",
    "details": [
      {"field": "long_url", "issue": "Domain is on the known-malware blocklist"}
    ]
  },
  "meta": {"request_id": "req_01H8MZXYZ"}
}

// 429 Too Many Requests
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 30 seconds.",
    "details": []
  },
  "meta": {
    "request_id": "req_01H8MZXYZ",
    "retry_after": 30
  }
}
```

#### GET /{code} (Redirect)

**Request:**
```http
GET /aZ81kLm HTTP/1.1
Host: sho.rt
User-Agent: Mozilla/5.0...
Referer: https://twitter.com/post/123
Accept: text/html
```

**Success Response (302):**
```http
HTTP/1.1 302 Found
Location: https://example.com/products/123?ref=summer&utm_source=twitter
Cache-Control: public, max-age=300, stale-while-revalidate=60
X-Request-ID: req_02K9PQR456
```

**Error Responses:**
```http
// 404 - Code not found
HTTP/1.1 404 Not Found
Content-Type: application/json
{"error": {"code": "NOT_FOUND", "message": "Short URL not found"}}

// 410 - Expired or deleted
HTTP/1.1 410 Gone
Content-Type: application/json
{"error": {"code": "LINK_EXPIRED", "message": "This short URL has expired"}}

// 451 - Quarantined (abuse)
HTTP/1.1 451 Unavailable For Legal Reasons
Content-Type: application/json
{"error": {"code": "LINK_BLOCKED", "message": "This link has been blocked for safety reasons"}}
```

#### POST /v1/short-links:batch (Batch Create)

**Request:**
```http
POST /v1/short-links:batch HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Idempotency-Key: batch_550e8400-e29b
Content-Type: application/json

{
  "links": [
    {"long_url": "https://example.com/page-a", "tags": ["batch-1"]},
    {"long_url": "https://example.com/page-b", "custom_alias": "promo-b"},
    {"long_url": "https://example.com/page-c", "expires_at": "2026-06-30T00:00:00Z"}
  ],
  "defaults": {
    "domain": "sho.rt",
    "redirect_type": 302
  }
}
```

**Response (207 Multi-Status):**
```json
{
  "data": {
    "results": [
      {"index": 0, "status": 201, "link": {"id": "lnk_01...", "code": "Xk92mPq", "short_url": "https://sho.rt/Xk92mPq"}},
      {"index": 1, "status": 409, "error": {"code": "ALIAS_CONFLICT", "message": "Alias 'promo-b' already exists"}},
      {"index": 2, "status": 201, "link": {"id": "lnk_02...", "code": "Rn47tWs", "short_url": "https://sho.rt/Rn47tWs"}}
    ],
    "summary": {"total": 3, "succeeded": 2, "failed": 1}
  },
  "meta": {"request_id": "req_03L1STU789"}
}
```

#### PATCH /v1/short-links/{code} (Update Link)

**Request:**
```http
PATCH /v1/short-links/aZ81kLm HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Idempotency-Key: upd_660f9500-f39c
Content-Type: application/json

{
  "expected_version": 1,
  "long_url": "https://example.com/new-destination",
  "expires_at": "2027-01-01T00:00:00Z",
  "tags": ["campaign", "winter-2027"]
}
```

**Response (200):**
```json
{
  "data": {
    "id": "lnk_01J8ABC123DEF456",
    "code": "aZ81kLm",
    "short_url": "https://sho.rt/aZ81kLm",
    "long_url": "https://example.com/new-destination",
    "status": "ACTIVE",
    "version": 2,
    "updated_at": "2026-05-28T14:30:00Z"
  },
  "meta": {"request_id": "req_04M2VWX012"}
}
```

#### GET /v1/short-links/{code}/analytics (Click Analytics)

**Request:**
```http
GET /v1/short-links/aZ81kLm/analytics?from=2026-05-01&to=2026-05-28&group_by=country,device_type&granularity=day HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

**Response (200):**
```json
{
  "data": {
    "link_id": "lnk_01J8ABC123DEF456",
    "code": "aZ81kLm",
    "period": {"from": "2026-05-01T00:00:00Z", "to": "2026-05-28T23:59:59Z"},
    "total_clicks": 145023,
    "unique_visitors": 98412,
    "timeseries": [
      {"date": "2026-05-01", "clicks": 5200, "unique": 3800},
      {"date": "2026-05-02", "clicks": 4800, "unique": 3500}
    ],
    "breakdowns": {
      "country": [
        {"value": "US", "clicks": 52000, "percentage": 35.8},
        {"value": "IN", "clicks": 28000, "percentage": 19.3},
        {"value": "GB", "clicks": 15000, "percentage": 10.3}
      ],
      "device_type": [
        {"value": "mobile", "clicks": 87000, "percentage": 60.0},
        {"value": "desktop", "clicks": 52000, "percentage": 35.8},
        {"value": "tablet", "clicks": 6023, "percentage": 4.2}
      ]
    }
  },
  "meta": {"request_id": "req_05N3YZA345", "freshness": "2026-05-28T10:00:00Z"}
}
```

### Design Patterns Used

| Pattern | Where Applied | Purpose |
|---------|--------------|---------|
| **Strategy** | Code Allocator (Snowflake vs Random vs Custom) | Pluggable code generation algorithms |
| **Factory** | Short Link creation (generated vs custom alias) | Different creation flows for different inputs |
| **Observer** | Event publishing (outbox -> Kafka -> consumers) | Decouple side effects from core write |
| **Circuit Breaker** | Redis, DynamoDB, external safety APIs | Prevent cascade failures |
| **Command/Query Separation (CQRS)** | Write via Link Mgmt, Read via Redirect Service | Optimize independently |
| **Decorator** | Cache layers (Local -> Redis -> DB) | Transparent cache chain |
| **Template Method** | Safety evaluation pipeline | Extensible safety checks |
| **Singleton** | Code range lease per instance | Prevent double allocation |

---

## 7. Architecture Components

### Full Infrastructure Layout

```
Internet
    |
    v
+---+-------------------------------------------+
| Route53 (DNS)                                  |
| - Latency-based routing                       |
| - Health checks on CDN origins                |
| - Failover to secondary region                |
+---+-------------------------------------------+
    |
    v
+---+-------------------------------------------+
| CloudFront CDN                                 |
| - Edge locations: 400+ globally               |
| - Cache redirect responses (max-age=300)      |
| - Lambda@Edge for redirect logic              |
| - Origin Shield for origin protection         |
+---+-------------------------------------------+
    |
    v
+---+-------------------------------------------+
| AWS WAF + Shield                               |
| - Rate limiting per IP (1000 req/min)         |
| - SQL injection, XSS protection              |
| - Bot detection (CAPTCHA challenge)           |
| - Geo-blocking for compliance                 |
| - DDoS protection (Shield Advanced)          |
+---+-------------------------------------------+
    |
    v
+---+-------------------------------------------+
| Application Load Balancer (ALB)                |
| - Path-based routing:                         |
|   /{code}         -> Redirect Target Group    |
|   /v1/*           -> Management Target Group  |
|   /health         -> Health check endpoint    |
| - TLS termination (ACM certificates)         |
| - Connection draining (30s)                   |
| - Cross-zone load balancing                   |
+---+-------------------------------------------+
    |
    +-------------------+-------------------+
    |                                       |
    v                                       v
+---+---------------+           +-----------+---+
| API Gateway       |           | Redirect      |
| (Kong / AWS APIGW)|           | Service       |
| - JWT validation  |           | (ECS Fargate) |
| - Rate limiting   |           | - Stateless   |
| - Request logging |           | - Auto-scale  |
| - Schema validate |           | - 3 AZs       |
+---+---------------+           +-----------+---+
    |                                       |
    v                                       v
+---+---------------+           +-----------+---+
| Link Management   |           | Redis Cluster |
| Service           |           | (ElastiCache) |
| (ECS Fargate)     |           | - 3 shards    |
| - 3 AZs           |           | - 3 replicas  |
| - Auto-scale      |           | - Multi-AZ    |
+---+---------------+           +---------------+
    |
    v
+---+---------------+
| DynamoDB          |
| (Link Mappings)   |
| - On-demand       |
| - Global Tables   |
| - Encryption      |
| - PITR backup     |
+-------------------+

+-------------------+    +-------------------+
| PostgreSQL (RDS)  |    | Kafka (MSK)       |
| - Multi-AZ        |    | - 3 brokers       |
| - Read replicas   |    | - Replication: 3  |
| - Auto-backup     |    | - Retention: 7d   |
+-------------------+    +-------------------+

+-------------------+    +-------------------+
| ClickHouse        |    | OpenSearch        |
| (Analytics)       |    | (Admin Search)    |
| - 3 shards        |    | - 3 nodes         |
| - 2 replicas/shard|    | - Fine-grained    |
+-------------------+    +-------------------+

+-------------------+
| S3 (Object Store) |
| - Audit exports   |
| - Evidence files  |
| - DB backups      |
| - Event archives  |
+-------------------+
```

---

## 8. Deep Dive of Each Component/Service

### 8.1 Redirect Service (Hot Path - Most Critical)

**Responsibility:** Resolve `(domain_id, code)` to destination URL with minimal latency.

**Internal Architecture:**
```
Request -> Extract domain + code from Host + path
        -> Local LRU Cache (Caffeine, 10K entries, 60s TTL)
        -> Redis Cluster (hash slot by domain:code)
        -> DynamoDB GetItem (domain_id, code)
        -> Validate (status, expires_at, quarantine)
        -> Return 302 + Location
        -> Fire-and-forget: buffer click event -> Kafka
```

**Key Design Decisions:**
- Stateless service, horizontally scalable
- Local cache: Caffeine LRU, 10K entries, 60s soft TTL, 300s hard TTL
- No database writes on redirect path
- Click events buffered in-memory (max 1000 or 5s flush interval)
- Circuit breaker on Redis (fallback directly to DynamoDB)
- Circuit breaker on DynamoDB (serve stale from cache if available)

**Failure Modes:**
| Failure | Impact | Mitigation |
|---------|--------|------------|
| Redis down | +5ms latency (direct DB) | Circuit breaker, local cache covers hot links |
| DynamoDB down | Cannot resolve cache-miss links | Serve stale from Redis/local; CDN cache stays warm |
| Kafka down | Click events lost | In-memory buffer, write to local disk, replay later |
| Service crash | Requests fail on that instance | ALB health check removes in 10s; others handle traffic |

**Scaling:**
- 250K QPS peak / 2000 QPS per instance = 125 instances minimum
- Auto-scale on CPU (target 60%) and request count
- Each instance: 2 vCPU, 4 GB RAM (Fargate)

---

### 8.2 Link Management Service (Write Path)

**Responsibility:** CRUD operations on short links with idempotency and event publishing.

**Internal Architecture:**
```
Request -> Validate JWT + extract tenant/user
        -> Check idempotency store (PostgreSQL)
        -> Normalize URL (strip tracking params if configured, lowercase host)
        -> Safety precheck (blocklist check, < 50ms)
        -> IF custom_alias: validate chars, length, reserved words
        -> IF generated: call Code Allocator for next code
        -> DynamoDB conditional PutItem (fails if key exists)
        -> IF conflict on generated code: retry (max 3 attempts)
        -> IF conflict on custom alias: return 409
        -> Save idempotency result (PostgreSQL)
        -> Write outbox event (DynamoDB stream or separate table)
        -> Return 201 + link object
```

**Idempotency Implementation:**
```
1. Hash request body (SHA-256)
2. Check idempotency_keys table:
   - Key exists + same hash -> return stored response (200)
   - Key exists + different hash -> return 409 (conflict)
   - Key not found -> reserve key, proceed with creation
3. After success: store response in idempotency_keys
4. Keys expire after 24 hours
```

---

### 8.3 Code Allocator Service

**Responsibility:** Generate unique short codes with zero collisions.

**Strategy: Range-Based Allocation (Primary)**
```
1. Service instance starts up
2. Requests a range from code_allocations table:
   - Lease: range_start=1000000, range_end=1099999 (100K codes)
   - Lease duration: 5 minutes (heartbeat to extend)
3. For each create request:
   - next_value++ (atomic local counter)
   - Base62 encode the number
   - Return 7-char code
4. When range exhausted (or 80% used):
   - Pre-fetch next range asynchronously
5. On instance shutdown:
   - Release remaining range back to pool
```

**Base62 Encoding:**
```
Alphabet: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
Number 1000000 -> Base62 -> "4c92" (4 chars)
Number 3521614606208 -> Base62 -> "zzzzzzz" (7 chars max)

function base62Encode(num: bigint): string {
  const chars = "0123456789ABCDEF...z";
  let result = "";
  while (num > 0) {
    result = chars[num % 62n] + result;
    num = num / 62n;
  }
  return result.padStart(7, '0');
}
```

**Why Not Random?**
- Random 7-char Base62: collision probability grows with corpus size
- At 3.65B links: collision on any single attempt = 3.65B / 3.5T = 0.1%
- With range allocation: zero collisions guaranteed (monotonic + unique ranges)

---

### 8.4 Analytics Pipeline

**Architecture:**
```
Redirect Service -> Kafka topic: "click-events" (partitioned by code hash)
                         |
                   +-----v-----+
                   | Flink Job  |
                   | (Stream)   |
                   +-----+-----+
                         |
              +----------+----------+
              |                     |
        +-----v-----+        +-----v-----+
        | ClickHouse |        | Redis     |
        | (Raw +     |        | (Real-time|
        |  Rollups)  |        |  counters)|
        +------------+        +-----------+
```

**Flink Processing:**
- Window: Tumbling 1-minute windows
- Operations: Count clicks, unique visitors (HyperLogLog), group by dimensions
- Output: Write to ClickHouse (batch inserts every 10s) + Redis (real-time counters)
- Late data: Allowed lateness of 5 minutes with watermarks

---

### 8.5 Abuse Scanner Worker

**Pipeline:**
```
1. Consume "scan-requests" topic from Kafka
2. For each URL:
   a. Check Google Safe Browsing API
   b. Check internal blocklist (known phishing domains)
   c. Check URL reputation score (domain age, TLS, etc.)
   d. Run heuristic checks (suspicious patterns, homoglyphs)
3. Score: 0-100 (0 = safe, 100 = definite malware)
4. IF score > 80: Quarantine immediately
   - Update link status to QUARANTINED in DynamoDB
   - Publish "link.quarantined" event
   - Invalidate CDN + Redis cache
5. IF score 50-80: Flag for human review
6. IF score < 50: Mark as safe, set status ACTIVE
```

---

## 9. Component Optimization

### 9.1 Caching Strategy (Multi-Tier)

```
Tier 1: CDN Edge Cache (CloudFront)
  - TTL: 300 seconds (5 minutes)
  - Stale-while-revalidate: 60 seconds
  - Cache key: Host + Path (domain + code)
  - Hit ratio target: 80% of all redirect traffic
  - Invalidation: CloudFront API on link update/delete/quarantine

Tier 2: Redis Cluster (ElastiCache)
  - TTL: 3600 seconds (1 hour) with jitter (+/- 10%)
  - Data: Serialized redirect metadata (status, destination, redirect_type, expires_at)
  - Hit ratio target: 95% of CDN-miss traffic
  - Eviction: allkeys-lru
  - Anti-stampede: Request coalescing with single-flight pattern

Tier 3: Local In-Process Cache (Caffeine)
  - TTL: 60 seconds
  - Max entries: 10,000 (most recently used)
  - Hit ratio target: 30-40% of requests to this instance
  - Zero network cost
```

**Cache Invalidation Flow:**
```
Link updated/deleted/quarantined
  -> Publish event to Kafka topic "cache-invalidation"
  -> Cache Invalidation Worker:
     1. Delete from Redis: DEL "{domain_id}:{code}"
     2. CloudFront invalidation: POST /2020-05-31/distribution/{id}/invalidation
     3. Publish to Redis Pub/Sub channel for local cache eviction
  -> Each Redirect Service instance subscribes to Pub/Sub
     -> Evicts from local Caffeine cache
```

### 9.2 Async Processing (Kafka Topics)

```
Topic: short-links.events (6 partitions, replication=3, retention=7d)
  - Key: link_id
  - Events: created, updated, expired, quarantined, deleted
  - Consumers: Search indexer, Analytics, Cache warmer, Audit

Topic: click-events (12 partitions, replication=3, retention=3d)
  - Key: domain_id:code (ensures ordering per link)
  - Events: redirects.clicked.v1
  - Consumers: Analytics pipeline (Flink), Hot-link detector

Topic: scan-requests (3 partitions, replication=3, retention=1d)
  - Key: link_id
  - Events: abuse.scan_requested.v1
  - Consumers: Abuse scanner workers

Topic: cache-invalidation (3 partitions, replication=3, retention=1h)
  - Key: domain_id:code
  - Events: cache.invalidate.v1
  - Consumers: Cache invalidation workers
```

### 9.3 Database Optimization

**DynamoDB Optimizations:**
```
1. On-Demand Capacity: Auto-scales with traffic, no capacity planning
2. DAX (DynamoDB Accelerator): In-memory cache for repeated reads
   - Cluster: 3 nodes, r5.large
   - Reduces read latency from ~5ms to <1ms
   - Useful for link metadata that changes rarely
3. Global Tables: us-east-1 (primary), eu-west-1 (DR read)
4. TTL attribute: Set on expired links for auto-deletion after 90 days
5. Point-in-Time Recovery: Enabled (35-day retention)
```

**ClickHouse Optimizations:**
```
1. Partition by month: Queries for recent data skip old partitions
2. ORDER BY (tenant_id, domain_id, code, clicked_at):
   Optimizes the most common query pattern
3. LowCardinality for enum-like columns: 10x compression
4. Materialized views for hourly/daily rollups: Pre-computed aggregates
5. TTL: Auto-drop raw events after 2 years, keep rollups for 5 years
6. Async inserts: Batch 10K events per insert for throughput
```

### 9.4 Hot-Link Detection & Mitigation

```
Problem: A single viral link gets 1M clicks/minute

Solution:
1. Stream Processing (Flink):
   - Sliding window: 1 minute, slide every 10 seconds
   - Count clicks per (domain_id, code) in window
   - IF count > 10,000 in 1 min -> emit "hot-link" event

2. Cache Warmer:
   - On hot-link event: Ensure link is in all Redis replicas
   - Push to CDN edge cache with extended TTL (30 min)
   - Set local cache TTL to 5 minutes (longer than normal)

3. Request Coalescing:
   - For the same code, only one DynamoDB read at a time
   - Other concurrent requests wait for the first to complete
   - Prevents thundering herd on cache expiry

4. Rate Limiting per Code:
   - If abuse detected: progressive rate limiting
   - Legitimate viral: serve from cache, no rate limit on reads
```

---

## 10. Observability

### 10.1 Metrics (Prometheus / CloudWatch)

```yaml
# RED Metrics for Redirect Service
redirect_requests_total{domain, status_code, cache_tier}
redirect_request_duration_seconds{domain, quantile}  # p50, p95, p99
redirect_errors_total{domain, error_type}

# RED Metrics for Link Management Service
link_create_requests_total{domain, status_code}
link_create_duration_seconds{quantile}
link_update_requests_total{status_code}
code_allocation_duration_seconds{strategy, quantile}

# Cache Metrics
cache_hit_ratio{tier}  # cdn, redis, local
cache_evictions_total{tier}
cache_invalidations_total{reason}

# Infrastructure Metrics
kafka_consumer_lag{topic, consumer_group}
dynamodb_read_capacity_consumed{table}
dynamodb_write_capacity_consumed{table}
redis_memory_usage_bytes{node}
redis_connected_clients{node}

# Business Metrics
links_created_total{tenant, domain}
redirects_served_total{domain, country}
links_expired_total{}
links_quarantined_total{reason}
hot_links_detected_total{}
```

### 10.2 Structured Logging

```json
{
  "timestamp": "2026-05-28T10:15:30.123Z",
  "level": "INFO",
  "service": "redirect-service",
  "instance_id": "i-0abc123def",
  "request_id": "req_01H8MZXYZ",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "message": "Redirect resolved",
  "domain_id": "dom_01abc",
  "code": "aZ81kLm",
  "cache_tier": "redis",
  "status": "ACTIVE",
  "duration_ms": 12,
  "country": "US"
}
```

### 10.3 Distributed Tracing (OpenTelemetry)

```
Trace: Create Short Link
  |
  +-- Span: API Gateway (auth + rate limit)           [2ms]
  |
  +-- Span: Link Management Service                   [45ms]
       |
       +-- Span: Check idempotency (PostgreSQL)       [3ms]
       +-- Span: Normalize URL                        [1ms]
       +-- Span: Safety precheck (blocklist)          [5ms]
       +-- Span: Allocate code (Code Allocator)       [2ms]
       +-- Span: DynamoDB conditional put             [8ms]
       +-- Span: Save idempotency result              [3ms]
       +-- Span: Write outbox event                   [5ms]

Trace: Redirect
  |
  +-- Span: CDN Edge (cache miss)                     [1ms]
  |
  +-- Span: Redirect Service                          [15ms]
       |
       +-- Span: Local cache lookup (miss)            [0.1ms]
       +-- Span: Redis GET (hit)                      [2ms]
       +-- Span: Validate status + TTL                [0.1ms]
       +-- Span: Emit click event (async)             [0.5ms]
```

### 10.4 SLIs/SLOs

| SLI | Measurement | SLO Target | Alert Threshold |
|-----|-------------|------------|-----------------|
| Redirect Availability | Successful 3xx / (Total - 4xx client errors) | 99.99% | < 99.95% over 5 min |
| Redirect Latency p99 | Time from request to 3xx response | < 100ms | > 150ms over 5 min |
| Create Availability | Successful 2xx / (Total - 4xx client errors) | 99.9% | < 99.5% over 5 min |
| Create Latency p99 | Time from request to 201 response | < 300ms | > 500ms over 5 min |
| Data Freshness | Time from link update to cache invalidation | < 10 seconds | > 30 seconds |
| Analytics Freshness | Time from click to queryable in dashboard | < 5 minutes | > 15 minutes |
| Zero Wrong Redirects | Links redirecting to wrong destination | 0 | Any occurrence = P1 |
| Zero Duplicate Codes | Same (domain, code) pointing to different URLs | 0 | Any occurrence = P1 |

### 10.5 Alerting Rules

```yaml
# P1 - Pages on-call immediately
- alert: RedirectAvailabilityBreach
  expr: |
    1 - (sum(rate(redirect_requests_total{status_code=~"3.."}[5m]))
    / sum(rate(redirect_requests_total{status_code!~"4.."}[5m]))) > 0.0005
  for: 5m
  labels: {severity: p1}
  annotations:
    runbook: "https://wiki/runbooks/redirect-availability"

- alert: RedirectLatencyP99High
  expr: histogram_quantile(0.99, rate(redirect_request_duration_seconds_bucket[5m])) > 0.15
  for: 5m
  labels: {severity: p1}

- alert: DuplicateCodeDetected
  expr: duplicate_code_events_total > 0
  for: 0m
  labels: {severity: p1}

# P2 - Slack alert, investigate within 1 hour
- alert: KafkaConsumerLagHigh
  expr: kafka_consumer_lag{consumer_group="click-analytics"} > 1000000
  for: 15m
  labels: {severity: p2}

- alert: CacheHitRatioLow
  expr: cache_hit_ratio{tier="redis"} < 0.85
  for: 15m
  labels: {severity: p2}

- alert: CodeAllocationPoolLow
  expr: code_allocation_remaining_percentage < 20
  for: 5m
  labels: {severity: p2}
```

### 10.6 Dashboard Layout

```
=== Redirect Service Dashboard ===
Row 1: [Request Rate] [Error Rate] [p50/p95/p99 Latency] [Availability %]
Row 2: [Cache Hit by Tier] [DynamoDB Read Latency] [Redis Latency] [Hot Links Count]
Row 3: [Top Domains by Traffic] [Top Codes by Traffic] [Geographic Distribution]
Row 4: [Instance Count] [CPU Utilization] [Memory Usage] [Network I/O]

=== Link Management Dashboard ===
Row 1: [Create Rate] [Error Rate] [Latency] [Conflict Rate]
Row 2: [Code Allocation Pool] [Idempotency Hit Rate] [Safety Block Rate]
Row 3: [Links by Status Pie] [Expiry Queue Depth] [Active Links Growth]

=== Analytics Pipeline Dashboard ===
Row 1: [Kafka Lag] [Flink Throughput] [ClickHouse Insert Rate]
Row 2: [Event Processing Latency] [DLQ Depth] [Consumer Restarts]
```

---

## 11. Considerations & Assumptions

### 11.1 Trade-offs Made

| Decision | Chosen Option | Alternative | Reasoning |
|----------|---------------|-------------|-----------|
| Code generation | Range-based + Base62 | Random + retry | Zero collisions, predictable perf, easier debugging |
| Primary DB | DynamoDB | PostgreSQL | 50K QPS reads need KV-style access; relational not needed for redirect |
| Redirect type | 302 (default) | 301 | 301 cached by browsers permanently; prevents analytics and destination changes |
| Analytics | Async via Kafka | Synchronous write | Never block redirects for analytics; click loss is acceptable |
| Multi-region | Active-Passive | Active-Active | Simpler consistency; home-region write avoids conflicts |
| Cache invalidation | Event-driven | TTL-only | Quarantined/deleted links must stop redirecting within seconds |

### 11.2 Security Considerations

```
1. URL Validation:
   - Block javascript:, data:, ftp:// schemes
   - Block private IP ranges (10.x, 192.168.x, 127.x)
   - Block internal hostnames
   - Limit URL length to 2048 characters

2. Rate Limiting:
   - Anonymous: 0 creates, unlimited redirects
   - Free tier: 100 creates/day, no custom domains
   - Pro tier: 10,000 creates/day, custom domains
   - Enterprise: Custom limits

3. Authentication:
   - JWT with RS256 (asymmetric, no shared secret)
   - Token expiry: 15 min access, 7 day refresh
   - API keys for programmatic access (scoped, rotatable)

4. Data Protection:
   - Long URLs encrypted at rest (AES-256-GCM)
   - PII never logged (IP hashed, user-agent hashed)
   - GDPR: Right to deletion (cascade delete all link data)
   - SOC2: Audit trail for all admin actions

5. Abuse Prevention:
   - CAPTCHA on anonymous create (if ever enabled)
   - Velocity checks: Max 10 links/min per IP
   - Domain reputation checks on creation
   - Automatic quarantine for confirmed malware
```

### 11.3 Future Scalability

```
Current design handles:
  - 50K QPS redirects (250K peak)
  - 2K QPS creates (10K peak)
  - 3.65B total links over 5 years

To scale to 10x (500K avg QPS):
  1. Add more CDN edge locations (reduce origin traffic)
  2. Scale Redis cluster (add shards)
  3. DynamoDB auto-scales natively (on-demand)
  4. Add Redirect Service instances (stateless)
  5. Kafka: Add partitions (from 12 to 48)

To scale to 100x (5M avg QPS):
  1. Lambda@Edge for redirects (true edge compute)
  2. DynamoDB Global Tables for multi-region reads
  3. Dedicated clusters per large tenant
  4. Tiered storage: Hot (DynamoDB) / Warm (S3) for old links
  5. Code length increase from 7 to 8 chars (62^8 = 218T codes)
```

### 11.4 Cost Analysis (Monthly Estimate at Baseline Scale)

```
=== COMPUTE ===
Redirect Service (125 instances x 2vCPU x 4GB):   $15,000
Link Management (20 instances):                     $3,000
Workers (analytics, abuse, cache, expiry):          $2,000
Subtotal:                                           $20,000

=== DATABASES ===
DynamoDB (50K RCU, 2K WCU avg, on-demand):         $25,000
PostgreSQL RDS (db.r6g.xlarge, Multi-AZ):           $2,000
Redis ElastiCache (6 nodes, r6g.large):             $3,600
ClickHouse (3 nodes, dedicated):                    $5,000
Subtotal:                                           $35,600

=== MESSAGING & STREAMING ===
Kafka MSK (3 brokers, kafka.m5.large):              $2,500
Flink (2 KPU):                                     $1,000
Subtotal:                                           $3,500

=== NETWORKING ===
CloudFront (50TB egress/month):                     $4,250
ALB:                                                $500
NAT Gateway:                                        $1,000
Subtotal:                                           $5,750

=== STORAGE ===
S3 (analytics archives, backups):                   $500
OpenSearch (admin/search):                          $2,000
Subtotal:                                           $2,500

=== OBSERVABILITY ===
CloudWatch / Datadog:                               $3,000
Subtotal:                                           $3,000

=== TOTAL MONTHLY ===                               ~$70,350
=== TOTAL ANNUAL ===                                ~$844,200

Cost per redirect: $70,350 / 1.5B redirects = $0.000047 (< $0.05 per 1000)
Cost per link created: $70,350 / 60M creates = $0.0012
```

### 11.5 Assumptions

1. **Read-heavy workload**: 25:1 read-to-write ratio (redirects dominate)
2. **Short codes never reused**: Deleted codes are retired permanently
3. **Single writer per code namespace**: Home-region routing avoids conflicts
4. **Analytics can lag**: Up to 5 minutes delay is acceptable for dashboards
5. **Clicks are not deduplicated**: Same user clicking twice = 2 click events
6. **Custom domains limited**: Max 10 custom domains per tenant
7. **Link metadata is small**: Avg 1KB per link (URL + metadata)
8. **Cloud-native deployment**: AWS as primary cloud provider
9. **No real-time collaboration**: Link editing is single-user at a time
10. **English-only codes**: Base62 alphabet only (no unicode in short codes)

---

## Summary: Interview Talking Points

### 5-Minute Whiteboard Structure

**Minute 1:** Scope and constraints
- Clarify: read-heavy (25:1), 50K QPS redirects, 2K QPS creates
- Non-goals: UI design, billing system, SSO

**Minute 2-3:** Architecture diagram
- Draw: CDN -> ALB -> Redirect Service -> Redis -> DynamoDB
- Draw: API GW -> Link Mgmt Service -> Code Allocator -> DynamoDB
- Draw: Kafka -> Analytics Pipeline -> ClickHouse

**Minute 4:** Critical flow walkthrough
- Walk the redirect path: CDN cache -> local -> Redis -> DB -> 302
- Walk code generation: Range allocation -> Base62 -> conditional put
- Emphasize: idempotency, zero collisions, async analytics

**Minute 5:** Trade-offs and closing
- Why 302 over 301 (analytics + mutability)
- Why range allocation over random (zero collisions)
- Why DynamoDB over PostgreSQL for links (scale + access pattern)
- SLO: 99.99% availability, p99 < 100ms for redirects
