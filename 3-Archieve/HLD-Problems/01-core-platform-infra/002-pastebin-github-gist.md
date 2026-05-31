# Design Pastebin / GitHub Gist — Complete System Design

## 1. Problem Statement

Design a web-scale paste/snippet sharing service (like Pastebin or GitHub Gist) that allows users to create, share, and manage text/code snippets with features like syntax highlighting, expiration, versioning, privacy controls, and collaboration.

---

## 2. Functional Requirements

### Core Features
| # | Feature | Description |
|---|---------|-------------|
| F1 | Create Paste | Users create text/code snippets with optional title, language, expiration |
| F2 | Read Paste | Anyone with the URL can read public/unlisted pastes; auth required for private |
| F3 | Raw Content | Serve raw text without HTML rendering |
| F4 | Syntax Highlighting | Server-side highlight for 200+ languages |
| F5 | Expiration/TTL | Auto-delete after configured time (10min, 1hr, 1day, 1week, 1month, never) |
| F6 | Privacy Modes | Public (searchable), Unlisted (URL-only), Private (auth-required) |
| F7 | Edit/Update | Authenticated users edit their own pastes |
| F8 | Delete | Soft-delete with 30-day recovery window |
| F9 | Short URL/Slug | Unique 8-char slug for each paste |
| F10 | User Accounts | Registration, login, paste management dashboard |

### Extended Features
| # | Feature | Description |
|---|---------|-------------|
| F11 | Multi-file Pastes | Gist-style multiple files per paste |
| F12 | Versioning | Full revision history with diffs |
| F13 | Forking | Clone another user's paste to your account |
| F14 | Comments | Threaded comments on pastes |
| F15 | Burn-after-read | Self-destruct after first view |
| F16 | Password Protection | Additional password layer for access |
| F17 | Search | Full-text search across public pastes |
| F18 | Trending/Recent | Discovery feed of popular public pastes |
| F19 | API Access | REST API with OAuth2 and API keys |
| F20 | Embed | Embeddable paste widgets for websites |
| F21 | Content Deduplication | Detect identical content, store once |
| F22 | Spam/Malware Detection | Block malicious content |

---

## 3. Non-Functional Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Availability | Service uptime | 99.95% (≤ 4.38 hours downtime/year) |
| Latency | Read paste (cached) | p50 < 20ms, p99 < 100ms |
| Latency | Read paste (uncached) | p50 < 50ms, p99 < 200ms |
| Latency | Create paste | p50 < 100ms, p99 < 500ms |
| Throughput | Read QPS | 50K avg, 200K peak |
| Throughput | Write QPS | 5K avg, 20K peak |
| Durability | Paste content | 99.999999999% (11 nines, S3-backed) |
| Consistency | Read-after-write | Strong for creator, eventual for others (< 2s) |
| Scalability | Horizontal | Linear scale with traffic, no single-node bottleneck |
| Security | Data at rest | AES-256 encryption |
| Security | Data in transit | TLS 1.3 |
| Compliance | GDPR | Right to deletion, data export within 72 hours |
| Rate Limiting | Anonymous | 10 creates/hour, 100 reads/minute |
| Rate Limiting | Authenticated | 100 creates/hour, 1000 reads/minute |

---

## 4. Capacity Estimation

### Traffic Estimation

```
DAU = 5M users
MAU = 30M users

Read:Write ratio = 10:1

Writes:
- 5M DAU × 2 pastes/day = 10M pastes/day
- QPS_write = 10M / 86400 ≈ 115 writes/sec (avg)
- Peak: 115 × 5 = 575 writes/sec

Reads:
- QPS_read = 115 × 10 = 1,150 reads/sec (avg)
- Peak: 1,150 × 5 = 5,750 reads/sec
- CDN absorbs 70%: origin sees ~1,725 reads/sec peak
```

### Storage Estimation

```
Average paste size = 10 KB (text content)
Metadata per paste = 500 bytes

Daily storage:
- Content: 10M × 10 KB = 100 GB/day
- Metadata: 10M × 500 B = 5 GB/day
- Highlighted HTML: 10M × 15 KB = 150 GB/day (stored in S3)

Monthly: (100 + 5 + 150) × 30 = 7.65 TB/month
Yearly: ~92 TB/year (before dedup)

With deduplication (~30% duplicate): 
- Effective: 92 × 0.7 = ~64 TB/year

5-year projection: ~320 TB total storage
```

### Network Bandwidth Estimation

```
Ingress (writes):
- Peak: 575 × 10 KB = 5.75 MB/s ≈ 46 Mbps

Egress (reads, origin only after CDN):
- Peak: 1,725 × 15 KB (with HTML) = 25.9 MB/s ≈ 207 Mbps
- Total with CDN pass-through: ~1.5 Gbps

CDN Egress:
- 5,750 × 15 KB = 86.25 MB/s ≈ 690 Mbps
```

### Database QPS

```
PostgreSQL (metadata):
- Write: 575/sec peak
- Read: 1,725/sec peak (after cache)
- With Redis cache (90% hit rate): ~172 reads/sec to DB

DynamoDB (slug → paste_id lookup):
- Read: 5,750/sec peak (before cache)
- Write: 575/sec peak

Redis:
- GET/SET: ~10K ops/sec
- Cache hit ratio target: 90%+
```

### Compute Estimation

```
Syntax highlighting (CPU-intensive):
- 575 pastes/sec × 50ms CPU per highlight = 29 vCPUs needed
- With queue batching: 10-15 vCPUs sufficient

API servers:
- 7,500 total requests/sec peak ÷ 2,000 req/sec per instance = 4 instances
- With 3x headroom: 12 ECS tasks (2 vCPU, 4 GB each)
```

---

## 5. Data Modeling

### Database Selection

| Store | Purpose | Justification |
|-------|---------|---------------|
| PostgreSQL (Citus) | Paste metadata, users, comments | ACID transactions, rich queries, shardable |
| Amazon S3 | Paste content blobs | 11-nines durability, cost-effective for large objects |
| Amazon DynamoDB | Slug-to-paste lookup | Single-digit ms latency, auto-scaling |
| Redis Cluster | Hot paste cache, rate limiting, sessions | Sub-ms reads, TTL support |
| Elasticsearch | Full-text search across pastes | Inverted index, language analyzers |
| ClickHouse | Analytics (views, trends) | Columnar, fast aggregation |

### PostgreSQL Schema

```sql
-- Users table
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(40) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100),
    avatar_url      TEXT,
    api_key_hash    VARCHAR(255),
    is_pro          BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_api_key ON users(api_key_hash) WHERE api_key_hash IS NOT NULL;

-- Pastes table (partitioned by created_at month)
CREATE TABLE pastes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            VARCHAR(12) UNIQUE NOT NULL,
    user_id         UUID REFERENCES users(id),
    title           VARCHAR(255),
    description     TEXT,
    visibility      VARCHAR(10) NOT NULL DEFAULT 'unlisted'
                    CHECK (visibility IN ('public', 'unlisted', 'private')),
    expires_at      TIMESTAMPTZ,
    burn_after_read BOOLEAN DEFAULT FALSE,
    password_hash   VARCHAR(255),
    fork_of         UUID REFERENCES pastes(id),
    version         INTEGER DEFAULT 1,
    total_size_bytes BIGINT DEFAULT 0,
    view_count      BIGINT DEFAULT 0,
    is_deleted      BOOLEAN DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE pastes_2026_01 PARTITION OF pastes
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE pastes_2026_02 PARTITION OF pastes
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE UNIQUE INDEX idx_pastes_slug ON pastes(slug);
CREATE INDEX idx_pastes_user_id ON pastes(user_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_pastes_expires_at ON pastes(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_pastes_visibility_created ON pastes(visibility, created_at DESC)
    WHERE visibility = 'public' AND is_deleted = FALSE;
CREATE INDEX idx_pastes_fork_of ON pastes(fork_of) WHERE fork_of IS NOT NULL;

-- Paste files (multi-file support)
CREATE TABLE paste_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paste_id        UUID NOT NULL REFERENCES pastes(id) ON DELETE CASCADE,
    filename        VARCHAR(255) NOT NULL DEFAULT 'untitled.txt',
    language        VARCHAR(50),
    content_hash    VARCHAR(64) NOT NULL,  -- SHA-256 for dedup
    size_bytes      INTEGER NOT NULL,
    sort_order      SMALLINT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_paste_files_paste_id ON paste_files(paste_id);
CREATE INDEX idx_paste_files_content_hash ON paste_files(content_hash);

-- Paste versions (revision history)
CREATE TABLE paste_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paste_id        UUID NOT NULL REFERENCES pastes(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    content_hash    VARCHAR(64) NOT NULL,
    diff_hash       VARCHAR(64),  -- stored unified diff
    message         VARCHAR(500),
    author_id       UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (paste_id, version_number)
);

CREATE INDEX idx_paste_versions_paste ON paste_versions(paste_id, version_number DESC);

-- Comments
CREATE TABLE comments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paste_id        UUID NOT NULL REFERENCES pastes(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id),
    parent_id       UUID REFERENCES comments(id),
    body            TEXT NOT NULL,
    line_number     INTEGER,  -- inline comment on specific line
    is_deleted      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_comments_paste ON comments(paste_id, created_at)
    WHERE is_deleted = FALSE;
```

### Amazon S3 Layout

```
pastebin-content-{region}/
├── raw/
│   └── {content_hash}              # Raw text (deduplicated)
├── highlighted/
│   └── {content_hash}/
│       └── {language}.html         # Pre-rendered HTML
├── diffs/
│   └── {diff_hash}                 # Unified diff between versions
└── thumbnails/
    └── {paste_id}.png              # Code preview image for embeds
```

### DynamoDB Schema (Slug Lookup)

```
Table: paste_slugs
  Partition Key: slug (String)
  Attributes:
    - paste_id (String/UUID)
    - created_at (Number/epoch)
    - expires_at (Number/epoch, with TTL)
    - visibility (String)
    - is_burned (Boolean)

GSI: paste_id-index
  Partition Key: paste_id
  (For reverse lookup: paste_id → slug)
```

### Redis Data Structures

```
# Hot paste cache (serialized metadata + content pointer)
paste:{slug} → Hash {
    paste_id, title, visibility, language,
    content_hash, user_id, created_at, expires_at
}
TTL: 1 hour (extended on access)

# Rate limiting (sliding window)
ratelimit:{ip}:{endpoint} → Sorted Set (timestamps)
TTL: 1 minute

# User session
session:{token} → Hash { user_id, roles, created_at }
TTL: 24 hours

# View counter (buffered writes to DB)
views:{paste_id} → Integer (INCR, flushed every 60s)

# Trending score (sorted set)
trending:pastes → Sorted Set { paste_id → score }
TTL: refreshed every 5 minutes

# Burn-after-read lock
burn:{slug} → "1" (SET NX EX 30)
```

---

## 6. High-Level Design (HLD)

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                      │
│  [Web App]   [CLI Tool]   [API Clients]   [Embed Widgets]               │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ HTTPS
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  EDGE LAYER                                                                │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐                            │
│  │ Route 53 │→ │ CloudFront   │→ │   WAF    │                            │
│  │  (DNS)   │  │   (CDN)      │  │(L7 Rules)│                            │
│  └──────────┘  └──────────────┘  └──────────┘                            │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  LOAD BALANCING LAYER                                                      │
│  ┌─────────────────────────────────────────┐                              │
│  │     Application Load Balancer (ALB)      │                              │
│  │  - Path-based routing                    │                              │
│  │  - Health checks                         │                              │
│  │  - TLS termination                       │                              │
│  └─────────────────────────────────────────┘                              │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  API GATEWAY LAYER                                                         │
│  ┌─────────────────────────────────────────┐                              │
│  │         Kong API Gateway                 │                              │
│  │  - Authentication (JWT/API Key)          │                              │
│  │  - Rate limiting                         │                              │
│  │  - Request/Response transformation       │                              │
│  │  - Circuit breaker                       │                              │
│  └─────────────────────────────────────────┘                              │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  APPLICATION SERVICES (ECS Fargate)                                        │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Paste Write  │  │  Paste Read  │  │   Search     │  │    User      │  │
│  │   Service    │  │   Service    │  │   Service    │  │   Service    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │                  │          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Highlight   │  │  Expiration  │  │   Analytics  │  │   Comment    │  │
│  │   Service    │  │   Service    │  │   Service    │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐                                       │
│  │    Spam      │  │  Notification│                                       │
│  │  Detection   │  │   Service    │                                       │
│  └──────────────┘  └──────────────┘                                       │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  EVENT BUS                                                                 │
│  ┌─────────────────────────────────────────┐                              │
│  │           Apache Kafka                   │                              │
│  │  Topics: paste.created, paste.viewed,    │                              │
│  │  paste.expired, spam.detected,           │                              │
│  │  highlight.completed, analytics.event    │                              │
│  └─────────────────────────────────────────┘                              │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  DATA LAYER                                                                │
│                                                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐  │
│  │PostgreSQL│ │ DynamoDB │ │  Redis   │ │    S3     │ │Elasticsearch │  │
│  │ (Citus)  │ │(Slug Map)│ │ Cluster  │ │ (Content) │ │  (Search)    │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘ └──────────────┘  │
│                                                                            │
│  ┌──────────────┐                                                          │
│  │  ClickHouse  │                                                          │
│  │ (Analytics)  │                                                          │
│  └──────────────┘                                                          │
└───────────────────────────────────────────────────────────────────────────┘
```

### Create Paste Data Flow

```
Client → CloudFront → WAF → ALB → Kong → Paste Write Service
                                              │
                                              ├─ 1. Validate input (size, format)
                                              ├─ 2. Generate slug (Base62, 8 chars)
                                              ├─ 3. Compute content_hash (SHA-256)
                                              ├─ 4. Check dedup (S3 HEAD on content_hash)
                                              ├─ 5. Upload to S3 (if new content)
                                              ├─ 6. Insert metadata → PostgreSQL
                                              ├─ 7. Insert slug mapping → DynamoDB
                                              ├─ 8. Set cache → Redis
                                              ├─ 9. Publish event → Kafka (paste.created)
                                              └─ 10. Return slug URL to client
                                              
Async consumers:
  paste.created → Highlight Service (render HTML)
  paste.created → Spam Detection Service
  paste.created → Search Indexer (if public)
  paste.created → Analytics Service
```

### Read Paste Data Flow

```
Client → CloudFront (cache check)
          │
          ├─ HIT → Return cached content
          │
          └─ MISS → WAF → ALB → Kong → Paste Read Service
                                            │
                                            ├─ 1. Lookup slug → Redis cache
                                            │     └─ MISS → DynamoDB slug lookup
                                            ├─ 2. Check visibility/auth
                                            ├─ 3. Check burn-after-read (Redis SET NX)
                                            ├─ 4. Check password (if protected)
                                            ├─ 5. Fetch content from S3 (or Redis cache)
                                            ├─ 6. Fetch highlighted HTML (if available)
                                            ├─ 7. Increment view counter (Redis INCR)
                                            ├─ 8. Publish event → Kafka (paste.viewed)
                                            └─ 9. Return response
                                            
If burn_after_read:
  - After successful read, mark as burned in DynamoDB + PostgreSQL
  - Invalidate CDN cache for this slug
```

### Microservice Communication Patterns

| Pattern | Usage |
|---------|-------|
| Synchronous REST | Client ↔ API Gateway ↔ Services (user-facing) |
| gRPC | Service ↔ Service (internal, e.g., Write → Highlight) |
| Event-Driven (Kafka) | Async workflows (highlighting, search indexing, analytics) |
| CQRS | Separate Write Service and Read Service with different data models |
| Saga Pattern | Multi-step operations (fork paste → copy files → update refs) |

---

## 7. Low-Level Design (LLD)

### API Contracts

#### Create Paste

```
POST /v1/pastes
Authorization: Bearer {token} (optional for anonymous)
Content-Type: application/json

Request:
{
    "title": "My Python Script",
    "files": [
        {
            "filename": "main.py",
            "language": "python",
            "content": "def hello():\n    print('Hello, World!')"
        },
        {
            "filename": "utils.py",
            "language": "python",
            "content": "import os\n..."
        }
    ],
    "visibility": "unlisted",        // public | unlisted | private
    "expires_in": "1d",              // 10m | 1h | 1d | 1w | 1m | never
    "burn_after_read": false,
    "password": null                 // optional password protection
}

Response: 201 Created
{
    "data": {
        "id": "a1b2c3d4-...",
        "slug": "xK9mPq2v",
        "url": "https://paste.example.com/xK9mPq2v",
        "raw_url": "https://paste.example.com/xK9mPq2v/raw",
        "title": "My Python Script",
        "visibility": "unlisted",
        "expires_at": "2026-05-29T10:30:00Z",
        "files": [
            {
                "filename": "main.py",
                "language": "python",
                "size_bytes": 42,
                "raw_url": "https://paste.example.com/xK9mPq2v/raw/main.py"
            }
        ],
        "created_at": "2026-05-28T10:30:00Z",
        "owner": {
            "username": "harsh",
            "avatar_url": "https://..."
        }
    }
}

Error: 400 Bad Request
{
    "error": {
        "code": "VALIDATION_FAILED",
        "message": "Content exceeds maximum size",
        "details": [
            { "field": "files[0].content", "issue": "Exceeds 512KB limit" }
        ]
    }
}

Error: 429 Too Many Requests
{
    "error": {
        "code": "RATE_LIMITED",
        "message": "Too many paste creations",
        "retry_after": 3600
    }
}
```

#### Get Paste

```
GET /v1/pastes/{slug}
Authorization: Bearer {token} (required for private pastes)
X-Paste-Password: {password} (for password-protected)

Response: 200 OK
{
    "data": {
        "id": "a1b2c3d4-...",
        "slug": "xK9mPq2v",
        "title": "My Python Script",
        "visibility": "unlisted",
        "expires_at": "2026-05-29T10:30:00Z",
        "files": [
            {
                "filename": "main.py",
                "language": "python",
                "content": "def hello():\n    print('Hello, World!')",
                "highlighted_html": "<pre><code class=\"python\">...</code></pre>",
                "size_bytes": 42
            }
        ],
        "version": 1,
        "view_count": 142,
        "fork_count": 3,
        "is_forked": false,
        "owner": { "username": "harsh" },
        "created_at": "2026-05-28T10:30:00Z",
        "updated_at": "2026-05-28T10:30:00Z"
    }
}

Error: 404 Not Found
{ "error": { "code": "PASTE_NOT_FOUND", "message": "Paste not found or has expired" } }

Error: 410 Gone
{ "error": { "code": "PASTE_BURNED", "message": "This paste was set to burn after reading" } }
```

#### Get Raw Content

```
GET /v1/pastes/{slug}/raw
GET /v1/pastes/{slug}/raw/{filename}

Response: 200 OK
Content-Type: text/plain; charset=utf-8
Content-Disposition: inline

def hello():
    print('Hello, World!')
```

#### Update Paste

```
PATCH /v1/pastes/{slug}
Authorization: Bearer {token}

Request:
{
    "title": "Updated Title",
    "files": [
        {
            "filename": "main.py",
            "content": "def hello():\n    print('Updated!')"
        }
    ],
    "version_message": "Fixed typo in print statement"
}

Response: 200 OK
{
    "data": {
        "slug": "xK9mPq2v",
        "version": 2,
        "updated_at": "2026-05-28T11:00:00Z"
    }
}
```

#### Delete Paste

```
DELETE /v1/pastes/{slug}
Authorization: Bearer {token}

Response: 204 No Content

Error: 403 Forbidden
{ "error": { "code": "NOT_OWNER", "message": "Cannot delete paste you don't own" } }
```

#### List Paste Versions

```
GET /v1/pastes/{slug}/versions?page=1&limit=20

Response: 200 OK
{
    "data": [
        {
            "version": 2,
            "message": "Fixed typo",
            "author": "harsh",
            "created_at": "2026-05-28T11:00:00Z",
            "diff_url": "/v1/pastes/xK9mPq2v/diff/1..2"
        },
        {
            "version": 1,
            "message": "Initial version",
            "author": "harsh",
            "created_at": "2026-05-28T10:30:00Z"
        }
    ],
    "meta": { "page": 1, "per_page": 20, "total": 2 }
}
```

#### Get Diff Between Versions

```
GET /v1/pastes/{slug}/diff/{from_version}..{to_version}

Response: 200 OK
{
    "data": {
        "from_version": 1,
        "to_version": 2,
        "files_changed": 1,
        "additions": 1,
        "deletions": 1,
        "diff": "--- a/main.py\n+++ b/main.py\n@@ -1,2 +1,2 @@\n def hello():\n-    print('Hello, World!')\n+    print('Updated!')\n"
    }
}
```

#### Fork Paste

```
POST /v1/pastes/{slug}/fork
Authorization: Bearer {token}

Response: 201 Created
{
    "data": {
        "slug": "yL8nQr3w",
        "url": "https://paste.example.com/yL8nQr3w",
        "forked_from": "xK9mPq2v"
    }
}
```

#### Search Pastes

```
GET /v1/pastes/search?q=fibonacci&language=python&sort=relevance&page=1&limit=20

Response: 200 OK
{
    "data": [
        {
            "slug": "xK9mPq2v",
            "title": "Fibonacci Sequence",
            "language": "python",
            "snippet": "...def fibonacci(n):\n    if n <= 1...",
            "owner": "harsh",
            "created_at": "2026-05-28T10:30:00Z",
            "view_count": 342
        }
    ],
    "meta": { "page": 1, "total": 47, "took_ms": 12 }
}
```

#### Trending Pastes

```
GET /v1/pastes/trending?period=24h&language=all&limit=20

Response: 200 OK
{
    "data": [
        {
            "slug": "abc123",
            "title": "Quick Sort in Rust",
            "language": "rust",
            "view_count": 5420,
            "fork_count": 89,
            "score": 9847.2
        }
    ]
}
```

### Internal gRPC Definitions

```protobuf
service HighlightService {
    rpc HighlightContent (HighlightRequest) returns (HighlightResponse);
    rpc DetectLanguage (DetectRequest) returns (DetectResponse);
    rpc BatchHighlight (stream HighlightRequest) returns (stream HighlightResponse);
}

message HighlightRequest {
    string content_hash = 1;
    string language = 2;
    string theme = 3;  // "dark" | "light"
}

message HighlightResponse {
    string content_hash = 1;
    string html = 2;
    string detected_language = 3;
    int32 line_count = 4;
}

service SpamDetectionService {
    rpc CheckContent (SpamCheckRequest) returns (SpamCheckResponse);
}

message SpamCheckRequest {
    string paste_id = 1;
    string content = 2;
    string user_id = 3;
    string ip_address = 4;
}

message SpamCheckResponse {
    bool is_spam = 1;
    float confidence = 2;
    repeated string reasons = 3;
    string action = 4;  // "allow" | "flag" | "block"
}
```

### Design Patterns Used

| Pattern | Where | Why |
|---------|-------|-----|
| Content-Addressable Storage | S3 content storage | Deduplication via SHA-256 hash |
| CQRS | Write Service / Read Service split | Different scaling and optimization needs |
| Repository Pattern | Data access layer | Abstract DB details from business logic |
| Strategy Pattern | Slug generation | Swap algorithm (Base62, NanoID, Snowflake) |
| Observer/Pub-Sub | Kafka events | Decouple write path from async processing |
| Circuit Breaker | External service calls | Prevent cascade failures |
| Bulkhead | Service isolation | Limit blast radius of failures |
| Decorator | Caching layer | Transparent cache wrap around data access |

### Slug Generation Algorithm

```python
import hashlib
import secrets
import string

BASE62_CHARS = string.ascii_letters + string.digits  # a-zA-Z0-9
SLUG_LENGTH = 8

def generate_slug(content: str, attempt: int = 0) -> str:
    """
    Generate unique 8-char Base62 slug.
    Uses content hash + random salt to avoid collision.
    
    Collision probability: 62^8 = 218 trillion combinations
    With 10B pastes: collision chance ≈ 0.005%
    """
    salt = secrets.token_bytes(8)
    hash_input = f"{content}{salt}{attempt}".encode()
    hash_bytes = hashlib.sha256(hash_input).digest()
    
    # Convert first 6 bytes to Base62
    num = int.from_bytes(hash_bytes[:6], 'big')
    slug = []
    for _ in range(SLUG_LENGTH):
        slug.append(BASE62_CHARS[num % 62])
        num //= 62
    
    return ''.join(slug)

def create_slug_with_retry(content: str, max_retries: int = 5) -> str:
    """Retry on collision (check DynamoDB for existence)."""
    for attempt in range(max_retries):
        slug = generate_slug(content, attempt)
        if not slug_exists_in_dynamodb(slug):
            return slug
    raise SlugCollisionError("Failed to generate unique slug")
```

---

## 8. Architecture Components Deep Dive

### Route 53 (DNS)

```
Configuration:
- Latency-based routing to nearest regional ALB
- Health checks every 10 seconds on /health endpoints
- Automatic failover to secondary region on 3 consecutive failures
- DNSSEC enabled for domain security

Records:
  paste.example.com → ALIAS → CloudFront distribution
  api.paste.example.com → ALIAS → ALB (regional)
  *.paste.example.com → CNAME → paste.example.com
```

### CloudFront (CDN)

```
Distribution Configuration:
- Origins:
  - ALB (dynamic API requests): /v1/*
  - S3 (raw content): /raw/*
  - S3 (static assets): /static/*

- Cache Behaviors:
  - /v1/pastes/{slug} (GET): Cache 60s for public, no-cache for private
  - /v1/pastes/{slug}/raw: Cache 300s, vary by Accept-Encoding
  - /static/*: Cache 1 year (immutable, versioned filenames)
  - Default: Forward to ALB, no caching

- Edge Functions (Lambda@Edge):
  - Viewer Request: Add request ID, validate origin
  - Origin Request: Auth token forwarding, slug normalization
  - Origin Response: Add security headers, CORS

- Error Pages:
  - 404 → custom /404.html (cached 60s)
  - 503 → custom /maintenance.html
```

### WAF (Web Application Firewall)

```
Rule Groups:
1. AWS Managed Rules:
   - AWSManagedRulesCommonRuleSet (XSS, path traversal)
   - AWSManagedRulesSQLiRuleSet (SQL injection)
   - AWSManagedRulesKnownBadInputsRuleSet

2. Custom Rules:
   - Rate limit: 1000 requests/5min per IP (read)
   - Rate limit: 50 requests/5min per IP (write)
   - Block requests with body > 512KB
   - Block user agents matching known scrapers
   - GeoBlock sanctioned countries (OFAC list)
   - Block if >5 failed auth attempts in 1 minute

3. Bot Control:
   - Allow verified search engine bots
   - Challenge suspicious automated traffic
   - Block credential stuffing patterns
```

### Application Load Balancer (ALB)

```
Configuration:
- Listeners:
  - HTTPS:443 → Target groups (TLS 1.3, cipher suite AEAD)
  - HTTP:80 → Redirect to HTTPS:443

- Target Groups:
  - paste-write-tg: /v1/pastes (POST, PATCH, DELETE)
  - paste-read-tg: /v1/pastes (GET)
  - search-tg: /v1/pastes/search, /v1/pastes/trending
  - user-tg: /v1/users/*
  - health-tg: /health, /ready

- Health Checks:
  - Path: /health
  - Interval: 15s
  - Healthy threshold: 2
  - Unhealthy threshold: 3
  - Timeout: 5s

- Sticky Sessions: Disabled (services are stateless)
- Cross-zone: Enabled
- Idle timeout: 60s
- Deregistration delay: 30s
```

### Kong API Gateway

```yaml
# Kong Configuration
services:
  - name: paste-write
    url: http://paste-write.internal:8080
    routes:
      - paths: ["/v1/pastes"]
        methods: ["POST", "PATCH", "DELETE"]
    plugins:
      - name: jwt
        config:
          claims_to_verify: ["exp"]
      - name: rate-limiting
        config:
          minute: 100
          policy: redis
          redis_host: redis.internal
      - name: request-size-limiting
        config:
          allowed_payload_size: 512  # KB

  - name: paste-read
    url: http://paste-read.internal:8080
    routes:
      - paths: ["/v1/pastes"]
        methods: ["GET"]
    plugins:
      - name: rate-limiting
        config:
          minute: 1000
      - name: response-transformer
        config:
          add:
            headers:
              - "Cache-Control: public, max-age=60"

  - name: search
    url: http://search.internal:8080
    routes:
      - paths: ["/v1/pastes/search", "/v1/pastes/trending"]
    plugins:
      - name: rate-limiting
        config:
          minute: 300

# Global Plugins
plugins:
  - name: correlation-id
    config:
      header_name: X-Request-ID
      generator: uuid
  - name: prometheus
  - name: opentelemetry
    config:
      endpoint: http://otel-collector:4318/v1/traces
```

### ECS Fargate (Compute)

```
Service Definitions:
┌────────────────────┬───────┬────────┬──────────┬──────────────┐
│ Service            │ vCPU  │ Memory │ Min/Max  │ Scaling      │
├────────────────────┼───────┼────────┼──────────┼──────────────┤
│ paste-write        │ 2     │ 4 GB   │ 3/20     │ CPU > 60%    │
│ paste-read         │ 2     │ 4 GB   │ 5/50     │ CPU > 50%    │
│ highlight-worker   │ 4     │ 8 GB   │ 2/15     │ Queue depth  │
│ search-service     │ 2     │ 4 GB   │ 2/10     │ CPU > 60%    │
│ expiration-worker  │ 1     │ 2 GB   │ 1/3      │ Fixed        │
│ spam-detector      │ 2     │ 4 GB   │ 2/8      │ Queue depth  │
│ analytics-worker   │ 1     │ 2 GB   │ 2/5      │ Queue depth  │
│ user-service       │ 1     │ 2 GB   │ 2/8      │ CPU > 60%    │
└────────────────────┴───────┴────────┴──────────┴──────────────┘
```

### Database Layer Configuration

```
PostgreSQL (Citus - Distributed):
- Coordinator: 1 node (r6g.xlarge)
- Workers: 4 nodes (r6g.2xlarge), expandable
- Shard key: user_id (for pastes, paste_files)
- Reference tables: languages, expiration_options
- Replication: Streaming with 2 read replicas
- Connection pooling: PgBouncer (max 200 connections per worker)
- WAL archival: S3 with 30-day retention

DynamoDB:
- Table: paste_slugs
- Capacity mode: On-demand (auto-scaling)
- Global tables: us-east-1, eu-west-1, ap-southeast-1
- Point-in-time recovery: Enabled
- TTL attribute: expires_at (auto-delete expired pastes)

Redis Cluster:
- Nodes: 6 (3 primary + 3 replica)
- Instance: r6g.xlarge (13 GB memory each)
- Total memory: ~78 GB
- Eviction policy: allkeys-lru
- Persistence: AOF (appendfsync everysec)
- Cluster mode: Enabled (16384 hash slots)
```

---

## 9. Deep Dive of Each Component/Service

### Paste Write Service

```
Responsibilities:
- Validate input (size, format, allowed languages)
- Generate unique slug
- Compute content hash (SHA-256)
- Upload content to S3 (with dedup check)
- Store metadata in PostgreSQL
- Store slug mapping in DynamoDB
- Warm Redis cache
- Emit paste.created event to Kafka

Flow:
1. Receive POST request with paste data
2. Validate: size ≤ 512KB per file, ≤ 10 files per paste, ≤ 100 total pastes/hour
3. For each file:
   a. Compute SHA-256 hash of content
   b. S3 HEAD to check if content_hash already exists (dedup)
   c. If not exists: S3 PUT raw/{content_hash}
4. Generate 8-char Base62 slug (retry on collision)
5. DynamoDB PutItem (slug → paste_id) with condition: attribute_not_exists(slug)
6. PostgreSQL INSERT paste metadata + paste_files records
7. Redis SET paste:{slug} with TTL 3600s
8. Kafka produce: paste.created { paste_id, slug, user_id, files[], visibility }
9. Return 201 with paste URL

Error Handling:
- S3 upload failure → Retry 3x with exponential backoff → 500 error
- DynamoDB collision → Regenerate slug (up to 5 attempts) → 500 error
- PostgreSQL failure → Compensate: delete DynamoDB entry, delete S3 → 500 error
```

### Paste Read Service

```
Responsibilities:
- Resolve slug to paste metadata
- Enforce visibility/auth/password checks
- Handle burn-after-read semantics
- Serve content from cache or S3
- Increment view counters (async)

Flow:
1. Receive GET request for slug
2. Redis GET paste:{slug}
   └─ MISS → DynamoDB GetItem(slug) → populate Redis cache
3. Check visibility:
   - public/unlisted: allow
   - private: verify JWT token matches owner
4. Check password (if set):
   - Compare bcrypt hash of X-Paste-Password header
5. Check burn_after_read:
   - Redis SET NX burn:{slug} (atomic lock)
   - If already burned: return 410 Gone
   - After response sent: mark deleted in DynamoDB + PostgreSQL
6. Fetch content:
   - Redis GET content:{content_hash} → S3 GET raw/{content_hash}
7. Fetch highlighted HTML (if available):
   - S3 GET highlighted/{content_hash}/{language}.html
   - If not yet highlighted: return raw with language hint for client-side highlight
8. Redis INCR views:{paste_id} (batched flush to DB every 60s)
9. Kafka produce: paste.viewed { paste_id, viewer_ip_hash, timestamp }
10. Return 200 with paste data
```

### Syntax Highlighting Service

```
Responsibilities:
- Consume paste.created events from Kafka
- Detect language if not specified
- Generate highlighted HTML using tree-sitter / Pygments
- Store result in S3
- Update paste metadata with language detection result

Technology: tree-sitter (fast, incremental parsing) + custom themes

Flow:
1. Consume from Kafka topic: paste.created
2. Download raw content from S3
3. If language not specified:
   - Use linguist/guesslang for detection
   - Fallback: file extension → MIME type mapping
4. Parse with tree-sitter grammar for detected language
5. Apply syntax theme (both dark/light variants)
6. Generate HTML: <pre><code class="hljs {lang}">...</code></pre>
7. Upload to S3: highlighted/{content_hash}/{language}.html
8. Kafka produce: highlight.completed { paste_id, language, line_count }

Performance:
- Average highlight time: 20-50ms per file
- Maximum content size for highlight: 1MB
- Timeout: 5 seconds (skip large files)
- Supported languages: 200+ (tree-sitter grammars)
```

### Expiration Service

```
Responsibilities:
- Delete expired pastes on schedule
- Cascade: remove S3 content (if no other references), DynamoDB entry, Redis cache
- Respect dedup: only delete S3 if content_hash reference count = 0

Implementation:
1. DynamoDB TTL auto-deletes slug entries (built-in)
2. Cron worker (every 5 minutes):
   - Query PostgreSQL: SELECT * FROM pastes WHERE expires_at < NOW() AND is_deleted = FALSE LIMIT 1000
   - For each expired paste:
     a. Soft-delete in PostgreSQL (is_deleted = TRUE, deleted_at = NOW())
     b. Delete from Redis cache
     c. Invalidate CDN (CloudFront invalidation API)
     d. Check if content_hash is used by other pastes
     e. If orphaned: schedule S3 deletion (after 24h grace period)
     f. Kafka produce: paste.expired { paste_id, user_id }

3. Hard-delete worker (daily):
   - Query: pastes WHERE is_deleted = TRUE AND deleted_at < NOW() - INTERVAL '30 days'
   - Permanently remove from PostgreSQL
   - Remove orphaned S3 objects

Cleanup Rate: ~100K pastes/day expired (at scale)
```

### Spam Detection Service

```
Responsibilities:
- Analyze paste content for spam/malware/sensitive data
- Score pastes and take action (allow, flag, block)
- Learn from flagged content (feedback loop)

Detection Layers:
1. URL Analysis:
   - Extract all URLs from content
   - Check against blacklist (Google Safe Browsing API)
   - Check domain reputation
   
2. Content Analysis:
   - Regex patterns for known spam (crypto scams, phishing templates)
   - ML model: trained on labeled spam/ham pastes
   - Sensitive data detection (API keys, passwords, credit cards)
   
3. Behavioral Signals:
   - Paste creation rate from IP
   - Account age vs paste volume
   - Content entropy (very low = repeated spam)
   - Similar content posted across multiple accounts

Actions:
- Score 0.0-0.3: Allow (normal content)
- Score 0.3-0.7: Flag for human review, paste stays public
- Score 0.7-1.0: Block immediately, notify user, restrict account

Flow:
1. Consume paste.created event
2. Run all detection layers in parallel
3. Aggregate scores with weighted average
4. If blocked: update paste visibility to 'hidden' in PostgreSQL
5. Kafka produce: spam.detected { paste_id, score, reasons[], action }
```

### Search Service

```
Responsibilities:
- Index public pastes for full-text search
- Support language-filtered search
- Provide trending/popular pastes feed

Elasticsearch Index Mapping:
{
    "pastes": {
        "mappings": {
            "properties": {
                "slug": { "type": "keyword" },
                "title": { "type": "text", "analyzer": "standard" },
                "content": { "type": "text", "analyzer": "code_analyzer" },
                "language": { "type": "keyword" },
                "tags": { "type": "keyword" },
                "username": { "type": "keyword" },
                "created_at": { "type": "date" },
                "view_count": { "type": "integer" },
                "fork_count": { "type": "integer" }
            }
        },
        "settings": {
            "analysis": {
                "analyzer": {
                    "code_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "camelcase_split"]
                    }
                }
            }
        }
    }
}

Indexing Flow:
1. Consume paste.created event (only visibility = public)
2. Fetch content from S3
3. Index into Elasticsearch with metadata
4. On paste.deleted: remove from index

Trending Algorithm:
score = (views_24h × 1.0) + (forks_24h × 5.0) + (recency_boost)
recency_boost = max(0, 1.0 - (hours_since_creation / 48))
```

---

## 10. Component Optimization

### Kafka Configuration

```
Topics:
┌─────────────────────┬────────────┬──────────┬───────────┬────────────┐
│ Topic               │ Partitions │ Replicas │ Retention │ Consumers  │
├─────────────────────┼────────────┼──────────┼───────────┼────────────┤
│ paste.created       │ 12         │ 3        │ 7 days    │ 4 services │
│ paste.viewed        │ 6          │ 2        │ 3 days    │ 2 services │
│ paste.expired       │ 3          │ 2        │ 1 day     │ 1 service  │
│ highlight.completed │ 6          │ 2        │ 1 day     │ 1 service  │
│ spam.detected       │ 3          │ 3        │ 30 days   │ 2 services │
│ analytics.event     │ 12         │ 2        │ 7 days    │ 1 service  │
└─────────────────────┴────────────┴──────────┴───────────┴────────────┘

Partitioning Strategy:
- paste.created: partition by hash(user_id) for ordering per user
- paste.viewed: partition by hash(paste_id) for per-paste ordering
- analytics.event: partition by hash(event_type) for parallel consumption

Producer Config:
  acks: all (for paste.created — must not lose)
  acks: 1 (for paste.viewed — acceptable loss)
  batch.size: 16KB
  linger.ms: 5
  compression.type: lz4

Consumer Config:
  enable.auto.commit: false (manual commit after processing)
  max.poll.records: 500
  session.timeout.ms: 30000
```

### Multi-Layer Caching Strategy

```
Layer 1: CDN (CloudFront)
├── Public paste HTML: TTL 60s
├── Raw content: TTL 300s
├── Static assets: TTL 1 year
└── Hit rate target: 70% of reads

Layer 2: Redis Cluster
├── Paste metadata: TTL 3600s (extended on access)
├── Hot content (<100KB): TTL 1800s
├── User session: TTL 86400s
├── Rate limit counters: TTL 60s
└── Hit rate target: 90% of origin reads

Layer 3: DynamoDB DAX (optional)
├── Slug lookups: microsecond latency
└── Eventually consistent reads

Layer 4: S3 (origin)
├── All content (source of truth)
├── 11-nines durability
└── Cross-region replication for DR
```

### Cache Invalidation Strategy

```
On paste update:
1. Redis DEL paste:{slug}
2. Redis DEL content:{old_content_hash}
3. CloudFront invalidation: /v1/pastes/{slug}*

On paste delete:
1. Redis DEL paste:{slug}
2. Redis DEL content:{content_hash}
3. DynamoDB DeleteItem (or set TTL to now)
4. CloudFront invalidation: /v1/pastes/{slug}*

On burn-after-read:
1. Redis SET burn:{slug} "1" NX EX 30 (atomic)
2. If SET succeeded → serve content → then invalidate all layers
3. If SET failed → return 410 (already burned)

Cache warming:
- On paste creation: proactively SET in Redis
- On trending calculation: pre-warm top 100 pastes
```

### Database Partitioning and Sharding

```
PostgreSQL Partitioning (Time-based):
- Table: pastes
- Partition by: RANGE(created_at), monthly
- Benefit: Efficient expiration queries, archival of old partitions
- Maintenance: pg_partman auto-creates future partitions

Citus Sharding (Hash-based):
- Shard key: user_id
- Distribution: 64 shards across 4 worker nodes
- Benefit: User queries (my pastes) hit single shard
- Cross-shard: slug lookups use DynamoDB (avoid scatter-gather)

DynamoDB Partitioning (Automatic):
- Partition key: slug (high cardinality, even distribution)
- Hot partition prevention: slug is random (Base62 hash)
- Adaptive capacity: auto-redistributes on hot keys

Index Strategy:
- B-tree: slug (unique lookup), user_id (user's pastes), expires_at (cleanup)
- GIN: content search (pg_trgm for trigram matching)
- BRIN: created_at (range scans on time-partitioned data)
```

### WebSocket / SSE for Real-time Features

```
Use Case: Live collaborative editing (Gist-style)

Architecture:
Client ←→ WebSocket ←→ Collaboration Service ←→ Redis Pub/Sub

Implementation:
- WebSocket connection per active editor
- CRDT (Conflict-free Replicated Data Types) for concurrent edits
- Redis Pub/Sub for broadcasting changes across instances
- Operational Transform as fallback

SSE Use Cases:
- Live view count updates on trending page
- Notification stream for paste comments
- Build status for CI-integrated pastes

Connection Management:
- Max connections per instance: 10K WebSocket
- Heartbeat interval: 30s
- Idle disconnect: 5 minutes
- Sticky sessions via ALB for WebSocket upgrades
```

### S3 Storage Optimization

```
Storage Classes:
┌──────────────────┬────────────────┬───────────────────────────────┐
│ Content Age      │ Storage Class  │ Rationale                     │
├──────────────────┼────────────────┼───────────────────────────────┤
│ 0-30 days       │ S3 Standard    │ Frequently accessed            │
│ 30-90 days      │ S3 IA          │ Less frequent, but instant     │
│ 90-365 days     │ S3 Glacier IR  │ Rare access, still instant     │
│ 365+ days       │ S3 Glacier DA  │ Archival (restore in 12 hours) │
└──────────────────┴────────────────┴───────────────────────────────┘

Lifecycle Policy:
- Transition to IA after 30 days (if paste not accessed in 14 days)
- Transition to Glacier IR after 90 days
- Delete after paste hard-deletion (30 days post soft-delete)
- Abort incomplete multipart uploads after 7 days

Cost Optimization:
- Deduplication saves ~30% storage
- S3 Intelligent Tiering for uncertain access patterns
- Compression (gzip for content > 1KB) saves ~60% for code
- Total monthly S3 cost at 100TB: ~$2,300/month (blended tiers)
```

### Elasticsearch Optimization

```
Index Design:
- Shards: 5 primary + 1 replica (for ~50M documents)
- Refresh interval: 5s (near real-time, not instant)
- Merge policy: tiered (optimal for mixed workloads)

Query Optimization:
- Use bool queries with filter context for non-scoring clauses
- Apply language filter as keyword (not analyzed)
- Limit result fields with _source filtering
- Use search_after for deep pagination (not offset)

Index Lifecycle Management (ILM):
- Hot phase: 7 days (all shards on fast SSD nodes)
- Warm phase: 30 days (merge to 1 shard, force merge)
- Cold phase: 90 days (searchable snapshots)
- Delete phase: 365 days (remove from index)

Memory:
- Heap: 50% of RAM, max 31GB (compressed OOPs)
- Fielddata circuit breaker: 40% of heap
- OS cache for remaining 50% (Lucene segments)
```

### ClickHouse Analytics

```
Schema:
CREATE TABLE paste_events (
    event_id        UUID,
    event_type      LowCardinality(String),  -- 'view', 'create', 'fork', 'delete'
    paste_id        UUID,
    user_id         Nullable(UUID),
    ip_hash         FixedString(16),
    country_code    LowCardinality(FixedString(2)),
    language        LowCardinality(String),
    referrer_domain LowCardinality(String),
    user_agent      String,
    created_at      DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (event_type, paste_id, created_at)
TTL created_at + INTERVAL 1 YEAR;

Materialized Views:
- Hourly view counts per paste (for trending)
- Daily active users per country
- Language distribution over time
- Top referrer domains

Query Examples:
-- Trending pastes (last 24h)
SELECT paste_id, count() as views
FROM paste_events
WHERE event_type = 'view'
  AND created_at > now() - INTERVAL 24 HOUR
GROUP BY paste_id
ORDER BY views DESC
LIMIT 100;
```

---

## 11. Observability

### SLI/SLO Definitions

| Service | SLI | SLO | Measurement |
|---------|-----|-----|-------------|
| Paste Read | Availability | 99.95% | Successful responses / total requests |
| Paste Read | Latency | p99 < 200ms | Response time distribution |
| Paste Write | Availability | 99.9% | Successful creates / total attempts |
| Paste Write | Latency | p99 < 500ms | Response time distribution |
| Paste Write | Durability | 99.999% | Pastes retrievable after creation |
| Search | Availability | 99.9% | Successful queries / total queries |
| Search | Freshness | < 30s | Time from creation to searchable |
| Highlight | Completion | 99% | Highlighted within 60s of creation |

### Prometheus Metrics

```
# API metrics
http_requests_total{service, method, endpoint, status_code}
http_request_duration_seconds{service, method, endpoint, quantile}
http_request_size_bytes{service, method, endpoint}
http_response_size_bytes{service, method, endpoint}

# Business metrics
pastes_created_total{visibility, language, has_expiration}
pastes_viewed_total{cache_hit, visibility}
pastes_expired_total{reason}  // ttl, burned, deleted
paste_content_bytes{quantile}
active_pastes_gauge{visibility}
slug_collisions_total{}

# Infrastructure metrics
s3_operations_total{operation, bucket, status}
s3_operation_duration_seconds{operation, bucket, quantile}
dynamodb_operations_total{table, operation, status}
dynamodb_consumed_capacity{table, operation}
redis_commands_total{command, status}
redis_memory_used_bytes{}
kafka_consumer_lag{topic, consumer_group}
kafka_produce_total{topic, status}
pg_connections_active{database, state}
pg_query_duration_seconds{query_type, quantile}

# Cache metrics
cache_hits_total{layer}       // cdn, redis, dax
cache_misses_total{layer}
cache_hit_ratio{layer}
cache_evictions_total{layer, reason}
```

### OpenTelemetry Distributed Tracing

```
Trace Structure (Create Paste):

Span: POST /v1/pastes (API Gateway)
  ├── Span: auth.validate_token (Kong JWT plugin)
  ├── Span: rate_limit.check (Kong rate limiter)
  └── Span: paste_write.create (Paste Write Service)
       ├── Span: validate.input
       ├── Span: slug.generate
       │    └── Span: dynamodb.condition_check
       ├── Span: content.hash (SHA-256 compute)
       ├── Span: s3.head_object (dedup check)
       ├── Span: s3.put_object (upload content)
       ├── Span: pg.insert (paste metadata)
       ├── Span: dynamodb.put_item (slug mapping)
       ├── Span: redis.set (cache warm)
       └── Span: kafka.produce (paste.created event)

Sampling Strategy:
- 100% sampling for errors (status >= 500)
- 100% sampling for slow requests (> 1s)
- 10% sampling for normal traffic
- 1% sampling for health checks

Trace Context Propagation:
- W3C Trace Context headers (traceparent, tracestate)
- Baggage: user_id, paste_id, request_id
```

### Alerting Rules

```yaml
# Critical (P1 - pages on-call)
- alert: PasteReadLatencyHigh
  expr: histogram_quantile(0.99, http_request_duration_seconds{service="paste-read"}) > 0.5
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Paste read p99 latency > 500ms for 5 minutes"
    runbook: "https://runbooks.internal/paste-read-latency"

- alert: PasteWriteErrorRateHigh
  expr: rate(http_requests_total{service="paste-write", status_code=~"5.."}[5m]) / rate(http_requests_total{service="paste-write"}[5m]) > 0.01
  for: 3m
  labels:
    severity: critical
  annotations:
    summary: "Paste write error rate > 1%"

- alert: S3UploadFailures
  expr: rate(s3_operations_total{operation="PutObject", status="error"}[5m]) > 0
  for: 2m
  labels:
    severity: critical

# Warning (P2 - Slack notification)
- alert: KafkaConsumerLag
  expr: kafka_consumer_lag{consumer_group="highlight-service"} > 10000
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Highlight service falling behind by {{ $value }} messages"

- alert: CacheHitRateLow
  expr: cache_hit_ratio{layer="redis"} < 0.8
  for: 15m
  labels:
    severity: warning

- alert: DatabaseConnectionPoolExhaustion
  expr: pg_connections_active / pg_connections_max > 0.8
  for: 5m
  labels:
    severity: warning

- alert: DiskSpaceLow
  expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.2
  for: 10m
  labels:
    severity: warning
```

### Grafana Dashboards

```
Dashboard: Paste Service Overview
┌─────────────────────────────────────────────────────────────────┐
│  Request Rate          │  Error Rate           │  Latency p50/99│
│  [line chart: 24h]     │  [line chart: 24h]    │  [line: 24h]   │
├─────────────────────────────────────────────────────────────────┤
│  Pastes Created/min    │  Active Pastes        │  Storage Used  │
│  [counter + sparkline] │  [gauge: by type]     │  [bar: by tier]│
├─────────────────────────────────────────────────────────────────┤
│  Cache Hit Rates       │  Kafka Consumer Lag   │  DB Connections│
│  [multi-line: layers]  │  [bar: by topic]      │  [gauge: pool] │
├─────────────────────────────────────────────────────────────────┤
│  Top Languages         │  Visibility Split     │  Expiry Profile│
│  [pie chart]           │  [donut chart]        │  [histogram]   │
└─────────────────────────────────────────────────────────────────┘

Dashboard: Infrastructure Health
- ECS task count and CPU/memory per service
- S3 request latency and error rate
- DynamoDB consumed capacity vs provisioned
- Redis memory, connections, hit rate
- PostgreSQL query duration, active connections, replication lag
```

### Structured Logging

```json
{
    "timestamp": "2026-05-28T10:30:00.123Z",
    "level": "INFO",
    "service": "paste-write",
    "instance_id": "i-abc123",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7",
    "request_id": "req-uuid-here",
    "user_id": "user-uuid-here",
    "event": "paste.created",
    "paste_id": "paste-uuid-here",
    "slug": "xK9mPq2v",
    "visibility": "unlisted",
    "file_count": 2,
    "total_size_bytes": 4567,
    "content_deduplicated": true,
    "duration_ms": 87,
    "s3_duration_ms": 34,
    "pg_duration_ms": 12,
    "dynamo_duration_ms": 8
}
```

---

## 12. Considerations and Assumptions

### Security Considerations

| Concern | Mitigation |
|---------|------------|
| Content injection (XSS) | HTML-escape all content; syntax highlight in sandbox |
| Sensitive data leaks | Automated scanning for API keys, passwords, PII |
| Brute-force slug enumeration | Rate limiting + non-sequential slugs (62^8 space) |
| DDoS on popular pastes | CDN caching + WAF rate limiting + auto-scaling |
| Data exfiltration | Audit logs, anomaly detection on bulk downloads |
| Password-protected paste bypass | bcrypt hashing, timing-safe comparison |
| Token theft | Short-lived JWTs (15min), secure refresh token rotation |

### Scalability Assumptions

```
Current Design Supports:
- 100M+ total pastes stored
- 50K read QPS peak (with CDN absorption)
- 20K write QPS peak
- 500 TB total content storage
- 30M MAU

Horizontal Scaling Levers:
1. Read replicas for PostgreSQL (add more read capacity)
2. Redis cluster expansion (add shards for memory)
3. ECS auto-scaling (CPU/queue-depth based)
4. DynamoDB on-demand (automatic partition splitting)
5. S3 unlimited (no capacity planning needed)
6. Kafka partition increase (more parallelism)
7. Elasticsearch shard splitting (reindex)
```

### Cost Estimation (Monthly at Scale)

```
┌──────────────────────────┬──────────────┬───────────────────────────┐
│ Component                │ Monthly Cost │ Notes                     │
├──────────────────────────┼──────────────┼───────────────────────────┤
│ ECS Fargate (all services)│ $4,200      │ ~50 tasks average         │
│ PostgreSQL (Citus)       │ $3,600      │ 1 coord + 4 workers       │
│ DynamoDB                 │ $1,800      │ On-demand, 100M items     │
│ Redis Cluster            │ $2,400      │ 6 nodes r6g.xlarge        │
│ S3 Storage (100TB)       │ $2,300      │ Blended tiers             │
│ S3 Requests              │ $500        │ GET/PUT operations        │
│ CloudFront               │ $3,000      │ 500TB egress/month        │
│ Kafka (MSK)              │ $2,000      │ 3 brokers m5.large        │
│ Elasticsearch            │ $2,500      │ 3 nodes, 500GB data       │
│ ClickHouse               │ $800        │ 2 nodes for analytics     │
│ ALB                      │ $500        │ LCU-based pricing         │
│ WAF                      │ $400        │ Rules + request charges   │
│ Route 53                 │ $50         │ Hosted zone + queries     │
│ Monitoring (Datadog)     │ $1,500      │ APM + logs + metrics      │
│ Misc (KMS, VPC, NAT)    │ $600        │ Networking + encryption   │
├──────────────────────────┼──────────────┼───────────────────────────┤
│ TOTAL                    │ ~$26,150/mo  │ At 30M MAU scale         │
└──────────────────────────┴──────────────┴───────────────────────────┘
```

### Key Trade-offs

| Decision | Trade-off |
|----------|-----------|
| DynamoDB for slug lookup vs PostgreSQL | +Latency, +Scale, -Cost efficiency for small scale |
| S3 for content vs PostgreSQL BYTEA | +Durability, +Scale, -Extra hop, -Complexity |
| Eventual consistency for reads | +Performance, +Availability, -Immediate visibility |
| Async highlighting | +Write latency reduction, -Brief window without highlights |
| Soft delete with 30-day window | +Recovery, +Audit, -Storage cost, -Query complexity |
| Content dedup via SHA-256 | +Storage savings, -Compute cost, -Can't modify stored content |
| CQRS (separate read/write services) | +Independent scaling, -Eventual consistency, -More services |

### Failure Modes and Mitigations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| S3 outage | Cannot read/write content | Multi-region replication; serve from Redis cache |
| PostgreSQL down | Cannot create/lookup pastes | Read replica promotion; DynamoDB as fallback for reads |
| Redis cluster failure | Cache miss storm | Circuit breaker; graceful degradation to DB |
| Kafka down | Async processing stops | Highlight on-demand; queue to SQS as dead letter |
| DynamoDB throttle | Slug lookups fail | Auto-scaling + burst capacity; Redis as L1 cache |
| CloudFront origin failure | CDN cache expires | Stale-while-revalidate; origin shield |
| Highlight service backlog | Pastes show raw text | Client-side highlight.js fallback; priority queue |

### Future Enhancements

1. **Real-time Collaboration**: WebSocket-based concurrent editing (like Google Docs)
2. **AI Features**: Auto-generate titles, suggest related pastes, code completion
3. **CI/CD Integration**: Run tests on paste content, show pass/fail badges
4. **Custom Domains**: Allow Pro users to host pastes on their domain
5. **Encryption at Client**: End-to-end encrypted pastes (server sees ciphertext only)
6. **GraphQL API**: Flexible querying for frontend apps
7. **Paste Collections**: Group related pastes into projects/notebooks
8. **Export Formats**: PDF, image (carbon.now.sh style), EPUB for documentation pastes
