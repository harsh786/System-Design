# Design Slack - Enterprise Team Communication Platform

## 1. Functional Requirements

### Core Features
- **Workspace Management**: Create/manage workspaces (organizations), invite members, role-based access
- **Channels**: Public channels, private channels, DMs, group DMs, threads
- **Real-time Messaging**: Send/receive messages instantly with typing indicators
- **Message Features**: Edit, delete, reactions, pinning, bookmarking, rich text (markdown)
- **File Sharing**: Upload/share files, images, documents within channels
- **Search**: Full-text search across messages, files, channels within workspace
- **Notifications**: Push, email, in-app notifications with DND/preferences
- **Presence & Status**: Online/offline/away/DND status, custom status
- **Threads**: Reply in threads to keep conversations organized
- **Integrations/Bots**: Slack Apps, webhooks, slash commands, workflow builder
- **Voice/Video Huddles**: Quick audio/video calls within channels

### Admin Features
- Workspace analytics and audit logs
- Compliance exports (eDiscovery)
- Data retention policies per channel
- SSO/SAML integration
- Channel management and archival

---

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% (52 min downtime/year) |
| Message Delivery Latency | < 100ms p50, < 250ms p99 for online users |
| Search Latency | < 200ms p50, < 500ms p99 |
| Consistency | Per-channel message ordering guaranteed |
| Durability | Zero message loss after acknowledgment |
| Multi-device Sync | Messages sync across all devices within 2s |
| Concurrent Connections | Support 10M+ simultaneous WebSocket connections |
| Tenant Isolation | Complete data isolation between workspaces |
| Compliance | SOC2, GDPR, HIPAA (enterprise), data residency |
| Scalability | Handle 50M+ DAU, 500M+ messages/day |

---

## 3. Capacity Estimation

### User Metrics
| Metric | Value |
|---|---|
| Total Registered Users | 300M |
| DAU (Daily Active Users) | 50M |
| MAU (Monthly Active Users) | 150M |
| Concurrent Connections (peak) | 8M |
| Concurrent Connections (avg) | 2M |
| Workspaces | 5M active |
| Avg users per workspace | 60 |

### Message Volume
| Metric | Calculation | Value |
|---|---|---|
| Messages/day | 50M DAU × 10 msgs/user | 500M messages/day |
| Messages/second (avg) | 500M / 86400 | ~5,800 msgs/sec |
| Messages/second (peak 5x) | 5,800 × 5 | ~29,000 msgs/sec |
| File uploads/day | 50M × 0.5 | 25M files/day |

### Storage Estimation
| Data Type | Calculation | Daily | Yearly |
|---|---|---|---|
| Messages | 500M × 2KB avg | 1 TB/day | 365 TB/year |
| File metadata | 25M × 1KB | 25 GB/day | 9 TB/year |
| Files (media) | 25M × 500KB avg | 12.5 TB/day | 4.5 PB/year |
| Search index | ~30% of message data | 300 GB/day | 110 TB/year |
| User/Channel metadata | 300M users × 5KB | 1.5 TB (total) | - |

### Network Bandwidth
| Direction | Calculation | Value |
|---|---|---|
| Ingress (messages) | 29K msgs/sec × 2KB | ~58 MB/s peak |
| Egress (fanout) | 29K × avg 50 recipients × 2KB | ~2.9 GB/s peak |
| File upload ingress | 290 files/sec × 500KB | ~145 MB/s |
| File download egress | 1000 downloads/sec × 500KB | ~500 MB/s |
| WebSocket keepalive | 8M connections × 64B/30s | ~17 MB/s |

### QPS Summary
| API | Average QPS | Peak QPS |
|---|---|---|
| Send message | 5,800 | 29,000 |
| Read messages (channel load) | 50,000 | 250,000 |
| Search | 5,000 | 25,000 |
| Presence updates | 20,000 | 100,000 |
| File upload | 290 | 1,450 |
| Notification delivery | 30,000 | 150,000 |

---

## 4. Data Modeling

### Database Selection Strategy

| Data Store | Technology | Purpose |
|---|---|---|
| User/Workspace metadata | PostgreSQL (CockroachDB for global) | ACID, relational integrity, SSO/billing |
| Messages | Cassandra / ScyllaDB | Append-heavy, partitioned by channel, high write throughput |
| Presence/Sessions | Redis Cluster | TTL-based, ephemeral, sub-ms reads |
| Search Index | Elasticsearch / OpenSearch | Full-text search, facets, relevance |
| File Storage | AWS S3 / GCS | Durable object storage, lifecycle |
| File Metadata | PostgreSQL | Relational, joins with messages |
| Analytics/Audit | ClickHouse | Column-oriented, fast aggregations |
| Event Bus | Apache Kafka | Durable event streaming, replay |
| Cache | Redis Cluster | Hot data, channel membership, unread counts |
| Notifications Queue | Apache Kafka + SQS | Reliable delivery, retry |

### Schema Design

#### PostgreSQL - Users & Workspaces

```sql
-- Workspaces
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan_type VARCHAR(50) DEFAULT 'free', -- free, pro, business, enterprise
    owner_id UUID NOT NULL,
    icon_url TEXT,
    domain VARCHAR(255),
    sso_enabled BOOLEAN DEFAULT FALSE,
    data_retention_days INT DEFAULT 365,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{}'
);
CREATE INDEX idx_workspaces_slug ON workspaces(slug);
CREATE INDEX idx_workspaces_domain ON workspaces(domain);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    timezone VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deactivated_at TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON users(email);

-- Workspace Memberships
CREATE TABLE workspace_members (
    workspace_id UUID REFERENCES workspaces(id),
    user_id UUID REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'member', -- owner, admin, member, guest
    display_name_override VARCHAR(255),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    invited_by UUID,
    status VARCHAR(20) DEFAULT 'active', -- active, deactivated, suspended
    PRIMARY KEY (workspace_id, user_id)
);
CREATE INDEX idx_wm_user ON workspace_members(user_id);

-- Channels
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    name VARCHAR(255),
    type VARCHAR(20) NOT NULL, -- public, private, dm, group_dm
    topic TEXT,
    purpose TEXT,
    created_by UUID NOT NULL,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ,
    retention_policy_days INT
);
CREATE INDEX idx_channels_workspace ON channels(workspace_id, type);
CREATE INDEX idx_channels_workspace_name ON channels(workspace_id, name);

-- Channel Memberships
CREATE TABLE channel_members (
    channel_id UUID REFERENCES channels(id),
    user_id UUID REFERENCES users(id),
    role VARCHAR(20) DEFAULT 'member', -- admin, member
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    last_read_ts TIMESTAMPTZ,
    last_read_message_id UUID,
    muted BOOLEAN DEFAULT FALSE,
    notification_pref VARCHAR(20) DEFAULT 'all', -- all, mentions, nothing
    PRIMARY KEY (channel_id, user_id)
);
CREATE INDEX idx_cm_user ON channel_members(user_id);
CREATE INDEX idx_cm_channel_user ON channel_members(channel_id, user_id);
```

#### Cassandra/ScyllaDB - Messages

```sql
-- Messages table (partitioned by channel, ordered by time)
CREATE TABLE messages (
    channel_id UUID,
    message_id TIMEUUID,
    workspace_id UUID,
    sender_id UUID,
    content TEXT,
    message_type VARCHAR, -- text, file, system, bot
    thread_ts TIMEUUID, -- parent message for threads
    edited_at TIMESTAMP,
    deleted_at TIMESTAMP,
    attachments LIST<FROZEN<attachment_type>>,
    reactions MAP<TEXT, FROZEN<SET<UUID>>>, -- emoji -> set of user_ids
    mentions SET<UUID>,
    metadata MAP<TEXT, TEXT>,
    created_at TIMESTAMP,
    PRIMARY KEY ((channel_id), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
  AND default_time_to_live = 0
  AND gc_grace_seconds = 864000;

-- Thread replies
CREATE TABLE thread_messages (
    channel_id UUID,
    parent_message_id TIMEUUID,
    reply_id TIMEUUID,
    sender_id UUID,
    content TEXT,
    attachments LIST<FROZEN<attachment_type>>,
    reactions MAP<TEXT, FROZEN<SET<UUID>>>,
    created_at TIMESTAMP,
    PRIMARY KEY ((channel_id, parent_message_id), reply_id)
) WITH CLUSTERING ORDER BY (reply_id ASC);

-- User message index (for search by user)
CREATE MATERIALIZED VIEW messages_by_user AS
    SELECT * FROM messages
    WHERE sender_id IS NOT NULL AND channel_id IS NOT NULL AND message_id IS NOT NULL
    PRIMARY KEY ((workspace_id, sender_id), message_id)
    WITH CLUSTERING ORDER BY (message_id DESC);
```

#### Redis - Presence & Caching

```
# Presence (Hash per user)
presence:{user_id} -> {status: "online", last_seen: ts, device: "desktop", gateway_id: "gw-1"}
TTL: 60s (refreshed by heartbeat)

# Channel membership cache (Set)
channel_members:{channel_id} -> SET of user_ids
TTL: 300s

# Unread counts (Hash)
unread:{user_id}:{workspace_id} -> {channel_id_1: count, channel_id_2: count}

# Typing indicators (Sorted Set)
typing:{channel_id} -> ZSET {user_id: timestamp}
TTL: 5s auto-expire entries

# User sessions / WebSocket routing
sessions:{user_id} -> SET {gateway_id:connection_id, gateway_id:connection_id}

# Rate limiting (Sliding window)
ratelimit:{user_id}:msg -> count (TTL 60s)
```

### Indexing Strategy

| Table | Index | Purpose |
|---|---|---|
| messages | (channel_id, message_id DESC) | Load channel history |
| messages | (workspace_id, sender_id, message_id DESC) | User's message history |
| thread_messages | (channel_id, parent_message_id, reply_id) | Load thread |
| channels | (workspace_id, type) | List channels in workspace |
| channel_members | (user_id) | List user's channels |
| channel_members | (channel_id, user_id) | Check membership |

---

## 5. High-Level Design (HLD)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Web App  │  │ Desktop  │  │  iOS     │  │ Android  │  │ Bot/Integration  │  │
│  │ (React)  │  │(Electron)│  │  App     │  │  App     │  │   Clients        │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
└───────┼──────────────┼──────────────┼──────────────┼────────────────┼────────────┘
        │              │              │              │                │
        ▼              ▼              ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           EDGE / INFRASTRUCTURE LAYER                             │
│  ┌─────────┐  ┌─────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────────┐  │
│  │Route 53 │→ │CloudFront│→ │  AWS WAF     │→ │    NLB    │→ │ API Gateway  │  │
│  │  (DNS)  │  │  (CDN)   │  │(DDoS/Abuse)  │  │(TCP/WS LB)│  │  (Kong/     │  │
│  │         │  │          │  │              │  │           │  │   Envoy)     │  │
│  └─────────┘  └─────────┘  └──────────────┘  └───────────┘  └──────┬───────┘  │
└──────────────────────────────────────────────────────────────────────┼───────────┘
                                                                       │
        ┌──────────────────────────────────────────────────────────────┤
        │                                                              │
        ▼                                                              ▼
┌───────────────────┐                                    ┌──────────────────────┐
│  WEBSOCKET        │                                    │   REST API           │
│  GATEWAY FLEET    │                                    │   SERVICE FLEET      │
│  ┌─────────────┐  │                                    │  ┌────────────────┐  │
│  │ Connection  │  │                                    │  │ Authentication │  │
│  │ Manager     │  │                                    │  │ Service        │  │
│  ├─────────────┤  │                                    │  ├────────────────┤  │
│  │ Protocol    │  │                                    │  │ Workspace      │  │
│  │ Handler     │  │                                    │  │ Service        │  │
│  ├─────────────┤  │                                    │  ├────────────────┤  │
│  │ Auth/Session│  │                                    │  │ Channel        │  │
│  │ Validator   │  │                                    │  │ Service        │  │
│  └─────────────┘  │                                    │  ├────────────────┤  │
└────────┬──────────┘                                    │  │ User Profile   │  │
         │                                               │  │ Service        │  │
         ▼                                               │  ├────────────────┤  │
┌─────────────────────────────────────────────────────── │  │ File Service   │  │
│                    CORE SERVICES LAYER                  │  ├────────────────┤  │
│                                                        │  │ Search Service │  │
│  ┌─────────────────┐  ┌──────────────────┐            │  ├────────────────┤  │
│  │ MESSAGE SERVICE │  │ PRESENCE SERVICE │            │  │ Admin Service  │  │
│  │ - Send message  │  │ - Online/offline │            │  └────────────────┘  │
│  │ - Edit/delete   │  │ - Heartbeats     │            └──────────────────────┘
│  │ - Reactions     │  │ - Status updates │
│  │ - Threads       │  │ - Typing events  │
│  └────────┬────────┘  └────────┬─────────┘
│           │                     │
│  ┌────────┴────────┐  ┌────────┴─────────┐  ┌──────────────────┐
│  │ FANOUT SERVICE  │  │ NOTIFICATION SVC │  │ SEARCH INDEXER   │
│  │ - Channel fanout│  │ - Push (APNs/FCM)│  │ - Async indexing │
│  │ - DM delivery   │  │ - Email          │  │ - Re-indexing    │
│  │ - Bot dispatch  │  │ - In-app badges  │  │ - Query serving  │
│  └────────┬────────┘  │ - Preferences    │  └──────────────────┘
│           │            └──────────────────┘
└───────────┼──────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DATA & EVENT LAYER                                        │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │  Cassandra/  │  │  PostgreSQL  │  │    Redis     │  │    Elasticsearch    │  │
│  │  ScyllaDB    │  │  (Users/WS)  │  │   Cluster    │  │    (Search)         │  │
│  │  (Messages)  │  │              │  │  (Presence/  │  │                     │  │
│  │              │  │              │  │   Cache)     │  │                     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────────────┘  │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │ Apache Kafka │  │   AWS S3     │  │  ClickHouse  │  │   Flink             │  │
│  │ (Event Bus)  │  │  (Files/     │  │ (Analytics)  │  │  (Stream Process)   │  │
│  │              │  │   Media)     │  │              │  │                     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Microservice Patterns Used

| Pattern | Usage |
|---|---|
| **CQRS** | Separate write path (message service → Cassandra) from read path (cache/search) |
| **Event Sourcing** | All messages stored as immutable events in Kafka for replay/audit |
| **Saga Pattern** | Multi-step flows like file upload + message + notification |
| **Outbox Pattern** | Transactional outbox for guaranteed event publishing |
| **API Gateway** | Central auth, rate-limiting, routing |
| **Service Mesh** | mTLS, circuit breaking between services (Istio/Linkerd) |
| **Sidecar** | Envoy proxy for observability, retry, circuit-break |
| **Bulkhead** | Isolate workspace traffic to prevent noisy neighbor |
| **Circuit Breaker** | Prevent cascade failures to search/notification services |
| **Strangler Fig** | Gradual migration path for legacy features |

---

## 6. Low-Level Design (LLD) - APIs & Services

### 6.1 Authentication Service

```
POST /api/v1/auth/login
Request: { "email": "user@corp.com", "password": "***" }
Response: { "access_token": "jwt...", "refresh_token": "rt_...", "expires_in": 3600 }

POST /api/v1/auth/oauth/callback
Request: { "provider": "google", "code": "auth_code", "state": "csrf_token" }
Response: { "access_token": "jwt...", "user": {...} }

POST /api/v1/auth/token/refresh
Request: { "refresh_token": "rt_..." }
Response: { "access_token": "new_jwt...", "expires_in": 3600 }

POST /api/v1/auth/saml/acs  (SAML SSO for Enterprise)
Request: SAMLResponse XML
Response: { "access_token": "jwt...", "workspace_id": "ws_..." }
```

### 6.2 Workspace Service

```
POST /api/v1/workspaces
Request: { "name": "Acme Corp", "slug": "acme-corp" }
Response: { "id": "ws_123", "name": "Acme Corp", "slug": "acme-corp", "created_at": "..." }

GET /api/v1/workspaces/{workspace_id}
Response: { "id": "ws_123", "name": "...", "member_count": 500, "plan": "enterprise", ... }

POST /api/v1/workspaces/{workspace_id}/invite
Request: { "emails": ["a@corp.com"], "role": "member", "channels": ["ch_general"] }
Response: { "invites": [{"email": "a@corp.com", "status": "sent", "invite_id": "inv_..."}] }

GET /api/v1/workspaces/{workspace_id}/members?cursor=xxx&limit=50
Response: { "members": [...], "cursor": "next_cursor", "has_more": true }
```

### 6.3 Channel Service

```
POST /api/v1/workspaces/{ws_id}/channels
Request: { "name": "engineering", "type": "public", "purpose": "Engineering team" }
Response: { "id": "ch_456", "name": "engineering", "type": "public", ... }

GET /api/v1/workspaces/{ws_id}/channels?type=public&cursor=xxx&limit=50
Response: { "channels": [...], "cursor": "...", "has_more": true }

POST /api/v1/channels/{channel_id}/join
Response: { "ok": true, "channel": {...} }

POST /api/v1/channels/{channel_id}/members
Request: { "user_ids": ["u_1", "u_2"] }
Response: { "added": ["u_1", "u_2"], "already_members": [] }

PATCH /api/v1/channels/{channel_id}
Request: { "topic": "Sprint 42 Planning", "expected_version": 5 }
Response: { "id": "ch_456", "topic": "Sprint 42 Planning", "version": 6 }
```

### 6.4 Message Service

```
POST /api/v1/channels/{channel_id}/messages
Idempotency-Key: "uuid-client-generated"
Request: {
    "content": "Hello team! @here check this out",
    "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "..."}}],
    "attachments": [{"file_id": "f_789"}],
    "thread_ts": null,
    "metadata": {"event_type": "deployment", "event_payload": {...}}
}
Response: {
    "id": "msg_abc123",
    "channel_id": "ch_456",
    "sender": {"id": "u_1", "name": "John"},
    "content": "Hello team!...",
    "ts": "1716672000.000100",
    "created_at": "2024-05-25T10:00:00Z"
}

GET /api/v1/channels/{channel_id}/messages?cursor=ts_value&limit=50&direction=backward
Response: {
    "messages": [...],
    "has_more": true,
    "cursor": "1716671900.000050"
}

PATCH /api/v1/channels/{channel_id}/messages/{message_id}
Request: { "content": "Updated message content", "expected_version": 1 }
Response: { "id": "msg_abc123", "content": "Updated...", "edited_at": "...", "version": 2 }

DELETE /api/v1/channels/{channel_id}/messages/{message_id}
Response: { "ok": true, "deleted_at": "..." }

POST /api/v1/channels/{channel_id}/messages/{message_id}/reactions
Request: { "emoji": "thumbsup" }
Response: { "ok": true, "reaction": {"emoji": "thumbsup", "count": 5} }

GET /api/v1/channels/{channel_id}/messages/{message_id}/thread?cursor=xxx&limit=25
Response: { "parent": {...}, "replies": [...], "reply_count": 42, "cursor": "..." }
```

### 6.5 Presence Service

```
# WebSocket Events (not REST)
→ Client sends: {"type": "presence_change", "status": "online"}
← Server sends: {"type": "presence_update", "user_id": "u_1", "status": "online"}

→ Client sends: {"type": "typing", "channel_id": "ch_456"}
← Server broadcasts to channel: {"type": "user_typing", "user_id": "u_1", "channel_id": "ch_456"}

→ Client sends: {"type": "ping"} (every 30s)
← Server responds: {"type": "pong"}

# REST for bulk queries
GET /api/v1/presence/users?ids=u_1,u_2,u_3
Response: { "users": [{"id": "u_1", "status": "online", "last_active": "..."}] }

PUT /api/v1/users/{user_id}/status
Request: { "status_text": "In a meeting", "status_emoji": ":calendar:", "expiration": "2024-05-25T11:00:00Z" }
Response: { "ok": true }
```

### 6.6 File Service

```
POST /api/v1/files/upload-url
Request: { "filename": "report.pdf", "size": 5242880, "content_type": "application/pdf", "channel_id": "ch_456" }
Response: {
    "file_id": "f_789",
    "upload_url": "https://s3.../presigned-url",
    "expires_at": "2024-05-25T10:15:00Z"
}

POST /api/v1/files/{file_id}/complete
Request: { "channel_id": "ch_456", "title": "Q4 Report" }
Response: { "file": {"id": "f_789", "url": "https://cdn.../files/f_789", "thumbnail_url": "..."} }

GET /api/v1/files/{file_id}
Response: { "id": "f_789", "name": "report.pdf", "size": 5242880, "download_url": "...", "preview_url": "..." }
```

### 6.7 Search Service

```
GET /api/v1/workspaces/{ws_id}/search?q=deployment+error&from=u_1&in=ch_456&after=2024-01-01&cursor=xxx&limit=20
Response: {
    "results": [
        {
            "type": "message",
            "channel": {"id": "ch_456", "name": "engineering"},
            "message": {"id": "msg_...", "content": "...", "highlight": "...deployment <mark>error</mark>..."},
            "sender": {"id": "u_1", "name": "John"},
            "ts": "..."
        }
    ],
    "total_count": 142,
    "cursor": "...",
    "has_more": true
}
```

### 6.8 Notification Service

```
PUT /api/v1/users/{user_id}/notification-preferences
Request: {
    "desktop": {"enabled": true, "sound": true},
    "mobile": {"enabled": true, "quiet_hours": {"start": "22:00", "end": "08:00", "timezone": "US/Pacific"}},
    "email": {"frequency": "hourly_digest"},
    "channel_overrides": {"ch_456": "mentions_only"}
}
Response: { "ok": true }

GET /api/v1/users/{user_id}/notifications?cursor=xxx&limit=50
Response: { "notifications": [...], "unread_count": 12, "cursor": "..." }

POST /api/v1/users/{user_id}/notifications/mark-read
Request: { "notification_ids": ["n_1", "n_2"] }
Response: { "ok": true }
```

### Design Patterns Used

| Pattern | Where Used |
|---|---|
| **Repository Pattern** | Data access abstraction for messages, users, channels |
| **Command Pattern** | Message operations (send, edit, delete, react) |
| **Observer Pattern** | WebSocket event broadcasting to subscribers |
| **Strategy Pattern** | Notification delivery (push, email, webhook) |
| **Factory Pattern** | Message block creation (text, file, bot, system) |
| **Decorator Pattern** | Message enrichment pipeline (mentions, links, previews) |
| **State Pattern** | Channel lifecycle (active → archived → deleted) |
| **Mediator Pattern** | Fanout service coordinating between producers and consumers |

---

## 7. Architecture Components - Deep Dive

### 7.1 DNS & Traffic Management (Route 53)

```
┌─────────────────────────────────────────┐
│           Route 53 Configuration         │
├─────────────────────────────────────────┤
│ slack.example.com → CloudFront           │
│ ws.slack.example.com → NLB (WebSocket)   │
│ api.slack.example.com → ALB (REST)       │
│ files.slack.example.com → CloudFront/S3  │
├─────────────────────────────────────────┤
│ Routing Policy: Latency-based routing    │
│ Failover: Active-passive multi-region    │
│ Health Checks: /health on each endpoint  │
└─────────────────────────────────────────┘
```

- **Latency-based routing**: Route users to nearest region
- **Failover**: Automatic DNS failover on health check failure
- **Weighted routing**: Canary deployments (5% traffic to new version)

### 7.2 CDN (CloudFront)

- **Static assets**: JS, CSS, images served from edge (TTL: 1 year with cache-busting)
- **File downloads**: Signed URLs with 1-hour expiry
- **Image thumbnails**: Lambda@Edge for on-the-fly resizing
- **WebSocket**: Not through CDN (direct to NLB)
- **Cache invalidation**: Event-driven invalidation on file update/delete

### 7.3 WAF (AWS WAF / Cloudflare)

```
Rules:
- Rate limit: 1000 req/min per IP, 100 req/min per user for mutations
- Bot detection: Challenge suspicious automated traffic
- Geo-blocking: Comply with sanctions/embargoes
- SQL injection / XSS: OWASP Top 10 ruleset
- Request size: Max 16MB for file uploads, 64KB for messages
- WebSocket: Max frame size 64KB, connection rate limit per IP
```

### 7.4 Load Balancer

**NLB (Network Load Balancer) - WebSocket Traffic:**
- Layer 4 TCP passthrough for WebSocket connections
- Sticky sessions (source IP affinity) for connection persistence
- Health checks on TCP port + custom /ws/health
- Cross-zone load balancing enabled

**ALB (Application Load Balancer) - REST API Traffic:**
- Layer 7 HTTP routing
- Path-based routing: /api/v1/messages → message-service, /api/v1/search → search-service
- Health checks: HTTP 200 on /health
- Connection draining: 30s for graceful shutdown

### 7.5 API Gateway (Kong / Envoy)

```yaml
Services:
  - name: auth-service
    routes: ["/api/v1/auth/*"]
    plugins: [rate-limit, cors, request-size-limit]
    
  - name: message-service
    routes: ["/api/v1/channels/*/messages*"]
    plugins: [jwt-auth, rate-limit, idempotency, request-transform]
    
  - name: search-service
    routes: ["/api/v1/*/search*"]
    plugins: [jwt-auth, rate-limit, response-cache(30s)]
    
  - name: file-service
    routes: ["/api/v1/files/*"]
    plugins: [jwt-auth, rate-limit, request-size-limit(16MB)]

Global Plugins:
  - correlation-id (X-Request-ID)
  - prometheus metrics
  - opentelemetry tracing
  - response-transformer (add security headers)
```

---

## 8. Deep Dive - Core Services

### 8.1 WebSocket Gateway Fleet

**Purpose**: Manage millions of persistent WebSocket connections, authenticate, route messages.

**Architecture:**
```
┌─────────────────────────────────────────────────┐
│           WebSocket Gateway Node                  │
├─────────────────────────────────────────────────┤
│ ┌──────────────┐  ┌──────────────────────────┐  │
│ │ Connection   │  │ Protocol Handler         │  │
│ │ Manager      │  │ - JSON/Protobuf framing  │  │
│ │ - Accept     │  │ - Message routing        │  │
│ │ - Heartbeat  │  │ - Ack/Nack handling      │  │
│ │ - Cleanup    │  │ - Compression (permessage)│  │
│ └──────────────┘  └──────────────────────────┘  │
│ ┌──────────────┐  ┌──────────────────────────┐  │
│ │ Auth Module  │  │ Subscription Registry    │  │
│ │ - JWT verify │  │ - Channel subscriptions  │  │
│ │ - Token      │  │ - User → connections     │  │
│ │   refresh    │  │ - Local pub/sub          │  │
│ └──────────────┘  └──────────────────────────┘  │
├─────────────────────────────────────────────────┤
│ Memory: ~2KB per connection                      │
│ Connections per node: 100K-500K                  │
│ Nodes needed for 8M peak: 20-80 nodes           │
└─────────────────────────────────────────────────┘
```

**Connection Lifecycle:**
1. Client initiates WebSocket upgrade with JWT in query param or header
2. Gateway validates JWT, extracts user_id and workspace_id
3. Registers connection in local registry + Redis (user → gateway mapping)
4. Subscribes to user's channels via internal pub/sub
5. Heartbeat every 30s; 3 missed heartbeats → connection closed
6. On disconnect: cleanup local state, update Redis, notify presence service

**Scaling Strategy:**
- Stateless gateway nodes behind NLB
- Connection state is ephemeral (Redis tracks user→gateway mapping)
- Horizontal scaling: add more gateway nodes
- Each node handles 100K-500K connections (depending on message rate)
- Use consistent hashing for channel-to-gateway affinity (optional optimization)

### 8.2 Message Service (Core Write Path)

**Message Send Flow:**
```
Client → WebSocket GW → Message Service → Cassandra (write)
                                        → Kafka (publish event)
                                        → Redis (update unread count)
                                        
Kafka → Fanout Service → WebSocket GW (deliver to online recipients)
                       → Notification Service (push to offline)
                       → Search Indexer (index for search)
```

**Detailed Steps:**
1. Client sends message via WebSocket with client-generated idempotency key
2. Gateway forwards to Message Service via gRPC
3. Message Service:
   - Validates content (size, rate limit, permissions)
   - Checks idempotency key (Redis: dedup within 5 min window)
   - Generates server timestamp (Snowflake ID for ordering)
   - Extracts mentions (@user, @here, @channel)
   - Writes to Cassandra (message table)
   - Publishes `message.sent` event to Kafka (outbox pattern)
   - Increments unread counters in Redis for all channel members
   - Returns ACK to sender via WebSocket

**Ordering Guarantee:**
- Messages within a channel are ordered by Snowflake timestamp
- Kafka partition key = channel_id (ensures per-channel ordering)
- No global ordering across channels (unnecessary)

### 8.3 Fanout Service

**Challenge**: A message in a 10,000-member channel must be delivered to all online members.

**Strategy: Hybrid Push/Pull**
```
Small channels (< 100 members): Push to all members' connections
Large channels (100-10K members): Push to online members only
Very large channels (> 10K): Pull-based (lazy load on client open)
```

**Implementation:**
1. Consume `message.sent` events from Kafka (partitioned by channel_id)
2. Lookup channel membership from Redis cache
3. For each member:
   - Check if online (presence in Redis)
   - If online: find their gateway node(s) from session registry
   - Send to gateway via internal gRPC/Redis Pub-Sub
4. Gateway delivers to client WebSocket connection
5. For offline members: queue notification event

**Fanout Optimization for Large Channels:**
- Batch deliveries: group recipients by gateway node
- Fan-out workers: parallelize across multiple worker instances
- Priority lanes: DMs and mentions get priority over channel messages
- Backpressure: if a gateway is overwhelmed, buffer and retry

### 8.4 Presence Service

**Architecture:**
```
┌──────────────────────────────────────────┐
│          Presence Service                  │
├──────────────────────────────────────────┤
│ Source of Truth: Redis Cluster             │
│                                            │
│ presence:{user_id} = {                     │
│   status: "online|away|dnd|offline",       │
│   last_active: timestamp,                  │
│   devices: ["desktop", "mobile"],          │
│   custom_status: {text, emoji, expiry}     │
│ }                                          │
│ TTL: 60 seconds (refreshed by heartbeat)   │
├──────────────────────────────────────────┤
│ Subscription Model:                        │
│ - Each user subscribes to workspace roster │
│ - Presence changes fan out to subscribers  │
│ - Batch presence queries for channel view  │
│ - Throttle: max 1 update per user per 5s   │
└──────────────────────────────────────────┘
```

**Presence State Machine:**
```
ONLINE → (no heartbeat 60s) → AWAY → (no heartbeat 300s) → OFFLINE
ONLINE → (user sets DND) → DND → (schedule ends) → ONLINE
OFFLINE → (WebSocket connects) → ONLINE
```

### 8.5 Search Service

**Architecture:**
```
┌─────────────────────────────────────────────┐
│             Search Architecture              │
├─────────────────────────────────────────────┤
│                                              │
│  Messages → Kafka → Search Indexer → ES     │
│                                              │
│  ES Cluster:                                 │
│  - Index per workspace (multi-tenant)        │
│  - Or shared index with workspace_id filter  │
│  - Sharding: 5 primary + 1 replica per index │
│                                              │
│  Index Schema:                               │
│  {                                           │
│    workspace_id, channel_id, message_id,     │
│    sender_id, content (analyzed),            │
│    timestamp, mentions[], channel_type,      │
│    has_attachment, file_names[]               │
│  }                                           │
│                                              │
│  Query Features:                             │
│  - Full-text search with highlighting        │
│  - Filters: from, in, has, before, after     │
│  - Autocomplete on channel/user names        │
│  - Relevance scoring (recency + match)       │
└─────────────────────────────────────────────┘
```

**Indexing Pipeline:**
1. Search Indexer consumes from Kafka `message.*` topic
2. Enriches message with channel name, sender name
3. Bulk indexes into Elasticsearch (batch of 500 or every 1s)
4. Handles message edits (update doc) and deletes (soft delete)
5. Lag monitoring: alert if indexing > 30s behind

### 8.6 Notification Service

**Multi-channel delivery:**
```
┌──────────────────────────────────────────────────┐
│           Notification Pipeline                    │
├──────────────────────────────────────────────────┤
│                                                    │
│  Event → Preference Check → Channel Router         │
│              │                    │                 │
│              │         ┌──────────┼──────────┐     │
│              │         ▼          ▼          ▼     │
│              │     ┌──────┐  ┌───────┐  ┌──────┐  │
│              │     │ Push │  │ Email │  │ In-  │  │
│              │     │(APNs/│  │(SES/  │  │ App  │  │
│              │     │ FCM) │  │SendGr)│  │Badge │  │
│              │     └──────┘  └───────┘  └──────┘  │
│              │                                     │
│  Suppression Rules:                                │
│  - DND mode active → suppress push                 │
│  - User online in channel → skip notification      │
│  - Channel muted → skip unless @mention            │
│  - Quiet hours → batch into digest                 │
│  - Rate limit: max 10 push/min per user            │
└──────────────────────────────────────────────────┘
```

---

## 9. Component Optimization & Advanced Patterns

### 9.1 Async Processing with Kafka

**Topic Design:**
```
Topics:
  slack.messages.sent          - partition by channel_id (ordering per channel)
  slack.messages.updated       - partition by channel_id
  slack.messages.deleted       - partition by channel_id
  slack.presence.changes       - partition by user_id
  slack.notifications.pending  - partition by user_id
  slack.files.uploaded         - partition by workspace_id
  slack.search.index           - partition by workspace_id
  slack.analytics.events       - partition by workspace_id
  slack.audit.log              - partition by workspace_id

Configuration:
  - Messages topic: 128 partitions, retention 7 days, replication factor 3
  - Notifications: 64 partitions, retention 3 days
  - Analytics: 256 partitions, retention 30 days (cold → S3/Iceberg)
  - Audit: unlimited retention (compliance), tiered to S3

Consumer Groups:
  - fanout-service-group (messages.sent → deliver to online users)
  - notification-service-group (messages.sent → push notifications)
  - search-indexer-group (messages.* → Elasticsearch)
  - analytics-pipeline-group (all events → ClickHouse/S3)
  - audit-archiver-group (audit → S3/Glacier for compliance)
```

### 9.2 Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Layer Caching                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  L1: Application-level local cache (Caffeine/Guava)          │
│      - User sessions, JWT verification results               │
│      - Channel membership for hot channels                   │
│      - TTL: 30s, size: 10K entries per node                  │
│                                                               │
│  L2: Redis Cluster (distributed cache)                       │
│      - Channel membership: SET per channel (TTL 5 min)       │
│      - Recent messages: last 50 per channel (TTL 10 min)     │
│      - Unread counts: HASH per user (TTL none, event-driven) │
│      - User profiles: STRING per user (TTL 1 hour)           │
│      - Rate limit counters: sliding window (TTL 60s)         │
│      - Presence data: HASH per user (TTL 60s heartbeat)      │
│                                                               │
│  L3: CDN Cache (CloudFront)                                  │
│      - Static assets, file thumbnails, user avatars          │
│      - TTL: 1 year (immutable URLs with content hash)        │
│                                                               │
│  Cache Invalidation:                                         │
│      - Event-driven: Kafka consumer updates Redis on change  │
│      - TTL-based: short TTL for frequently changing data     │
│      - Write-through: update cache on write path             │
│      - Stampede protection: probabilistic early expiration   │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 WebSocket Optimization

```
Connection Optimization:
- Per-message deflate compression (permessage-deflate extension)
- Binary protocol (Protocol Buffers) for internal events, JSON for client
- Batching: aggregate multiple small events into single frame (every 50ms)
- Selective subscriptions: client subscribes only to visible channels
- Lazy loading: historical messages loaded via REST, not pushed via WS

Scaling:
- Each gateway node: 100K-500K connections
- Memory per connection: ~2KB (buffers + metadata)
- Epoll/kqueue for event-driven I/O (not thread-per-connection)
- Graceful shutdown: send GOAWAY, drain connections over 30s
- Connection migration: on node restart, clients reconnect to new node

Reliability:
- Client reconnection with exponential backoff (1s, 2s, 4s... max 30s)
- Sync cursor: on reconnect, client sends last received event_id
- Gap detection: client requests missed messages via REST API
- Server-side buffering: 60s of messages buffered for fast reconnect
```

### 9.4 Database Optimization

**Cassandra/ScyllaDB Tuning:**
```
- Partition size target: < 100MB (avoid large partitions for busy channels)
- Solution: composite partition key (channel_id, time_bucket)
  - time_bucket = message_ts / (24 * 3600) → daily buckets
  - Allows efficient time-range queries within a day
  
- Compaction strategy: TimeWindowCompactionStrategy (TWCS)
  - Optimized for time-series-like message data
  - Reduces read amplification for recent messages

- Read optimization:
  - Speculative retry at p99 latency percentile
  - Token-aware routing (client knows partition locations)
  - Row cache for frequently accessed recent messages

- Write optimization:
  - Consistency level: LOCAL_QUORUM for writes (2/3 nodes)
  - Consistency level: LOCAL_ONE for reads (with anti-entropy repair)
  - Unlogged batches for multi-row writes within same partition
```

**PostgreSQL Optimization:**
```sql
-- Partition workspace_members by workspace_id for large workspaces
CREATE TABLE workspace_members (
    ...
) PARTITION BY HASH (workspace_id);

-- Connection pooling: PgBouncer (transaction mode)
-- Read replicas for read-heavy queries (channel list, user profiles)
-- Vacuum tuning: autovacuum_scale_factor = 0.01 for high-write tables

-- Efficient unread count query
CREATE INDEX idx_cm_unread ON channel_members(user_id, last_read_message_id)
WHERE last_read_message_id IS NOT NULL;
```

### 9.5 Sharding & Partitioning Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                   Sharding Strategy                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Messages (Cassandra):                                       │
│  - Partition key: (channel_id, time_bucket)                  │
│  - Clustering key: message_id DESC                           │
│  - Allows time-range queries per channel                     │
│  - Auto-sharding by Cassandra's consistent hashing           │
│                                                               │
│  Users/Workspaces (PostgreSQL):                              │
│  - Shard by workspace_id (Citus/Vitess)                      │
│  - Range: 0-N shards, consistent hashing with virtual nodes  │
│  - Cross-shard: user lookup by email (reference table)       │
│                                                               │
│  Redis:                                                       │
│  - Redis Cluster: 16384 hash slots                           │
│  - Key design ensures related data on same shard             │
│  - {channel_id} hash tag for channel-related keys            │
│                                                               │
│  Elasticsearch:                                              │
│  - Index per workspace (< 10K msgs/day) OR                   │
│  - Shared index with routing by workspace_id                 │
│  - Time-based indices for old data (monthly rollover)        │
│  - ILM: hot → warm → cold → delete lifecycle                │
│                                                               │
│  Kafka:                                                       │
│  - Partition by channel_id for message ordering              │
│  - 128+ partitions for parallelism                           │
│  - Consumer group rebalancing on scale up/down               │
└─────────────────────────────────────────────────────────────┘
```

### 9.6 Stream Processing (Apache Flink)

```
Use Cases:
1. Real-time abuse detection:
   - Sliding window: messages per user per minute
   - Pattern detection: repeated content, link spam
   - Action: rate-limit or shadow-ban

2. Unread count aggregation:
   - Sessionized computation of unread per channel per user
   - Emit to Redis for fast serving

3. Workspace analytics:
   - Messages per channel per hour
   - Active users per workspace
   - Peak usage patterns

4. Mention graph:
   - Who mentions whom (for notification priority)
   - Channel activity heatmaps

Flink Job Example:
  Source: Kafka (slack.messages.sent)
  → KeyBy(channel_id)
  → Window(TumblingEventTime, 1 minute)
  → Aggregate(count messages, unique senders)
  → Sink: ClickHouse (analytics) + Redis (if threshold exceeded → alert)
```

### 9.7 Data Lake & Analytics (S3 + Iceberg + ClickHouse)

```
┌──────────────────────────────────────────────────────────────┐
│              Analytics Data Pipeline                           │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Kafka → Flink → S3 (Apache Iceberg format)                  │
│                    └→ ClickHouse (for real-time queries)       │
│                                                                │
│  Iceberg Tables:                                              │
│  - messages_raw: all message events (partitioned by date/ws)  │
│  - user_activity: DAU/WAU/MAU computations                    │
│  - channel_metrics: messages, reactions, files per channel    │
│  - audit_log: all admin actions (immutable, compliance)       │
│                                                                │
│  ClickHouse Tables:                                           │
│  - workspace_analytics: real-time dashboards for admins       │
│  - message_volume: time-series message counts                 │
│  - search_analytics: query patterns, zero-result queries      │
│                                                                │
│  Retention:                                                    │
│  - Hot (ClickHouse): 90 days                                  │
│  - Warm (S3 Standard): 1 year                                 │
│  - Cold (S3 Glacier): 7 years (compliance)                    │
└──────────────────────────────────────────────────────────────┘
```

### 9.8 Server-Sent Events & Long Polling (Fallback)

```
Fallback Strategy (when WebSocket unavailable):
1. Primary: WebSocket (bidirectional, low latency)
2. Fallback 1: Server-Sent Events (SSE) for read + REST for write
3. Fallback 2: Long polling (corporate firewalls blocking WS/SSE)

Long Polling Implementation:
  GET /api/v1/channels/{id}/poll?last_event_id=xxx&timeout=30s
  - Server holds connection up to 30s
  - Returns immediately if new messages exist
  - Returns empty with 304 if timeout reached
  - Client immediately reconnects after response

SSE Implementation:
  GET /api/v1/events/stream
  Accept: text/event-stream
  
  data: {"type": "message", "channel_id": "ch_456", "message": {...}}
  data: {"type": "typing", "channel_id": "ch_456", "user_id": "u_1"}
  data: {"type": "presence", "user_id": "u_2", "status": "away"}
```

---

## 10. Observability

### 10.1 Metrics (Prometheus + Grafana)

```yaml
# Key SLIs
- slack_message_delivery_latency_seconds{quantile="0.50|0.95|0.99"}
- slack_message_send_total{status="success|failure", channel_type="dm|public|private"}
- slack_websocket_connections_active{gateway_id, region}
- slack_websocket_connection_duration_seconds
- slack_api_request_duration_seconds{service, endpoint, status_code}
- slack_api_request_total{service, endpoint, method, status_code}
- slack_kafka_consumer_lag{topic, consumer_group}
- slack_notification_delivery_total{channel="push|email|inapp", status="success|failure"}
- slack_search_query_duration_seconds{quantile}
- slack_unread_count_staleness_seconds
- slack_file_upload_size_bytes
- slack_presence_update_latency_seconds

# Infrastructure Metrics
- cassandra_write_latency_p99{keyspace, table}
- redis_memory_usage_bytes{cluster}
- redis_hit_rate{cluster}
- elasticsearch_indexing_rate{index}
- elasticsearch_search_latency_p99
- kafka_broker_partition_count
- kafka_topic_messages_in_per_sec
```

### 10.2 Logging (Structured JSON → ELK/Loki)

```json
{
  "timestamp": "2024-05-25T10:00:00.123Z",
  "level": "INFO",
  "service": "message-service",
  "trace_id": "abc123def456",
  "span_id": "span_789",
  "request_id": "req_xyz",
  "user_id": "u_1",
  "workspace_id": "ws_123",
  "channel_id": "ch_456",
  "action": "message.send",
  "duration_ms": 45,
  "status": "success",
  "message_size_bytes": 256,
  "fanout_count": 50
}
```

### 10.3 Distributed Tracing (Jaeger / OpenTelemetry)

```
Trace: message.send
├── Span: api-gateway.authenticate (2ms)
├── Span: message-service.validate (5ms)
├── Span: message-service.dedup-check (3ms) → Redis
├── Span: message-service.persist (15ms) → Cassandra
├── Span: message-service.publish-event (8ms) → Kafka
├── Span: fanout-service.expand (25ms)
│   ├── Span: fanout.lookup-members (5ms) → Redis
│   ├── Span: fanout.batch-deliver (18ms) → Gateway gRPC
│   └── Span: fanout.queue-offline (2ms) → Kafka
└── Span: notification-service.process (50ms async)
    ├── Span: notification.check-preferences (5ms)
    └── Span: notification.send-push (45ms) → APNs/FCM
```

### 10.4 Alerting Rules

```yaml
# Critical Alerts (Page on-call)
- alert: MessageDeliveryLatencyHigh
  expr: histogram_quantile(0.99, slack_message_delivery_latency_seconds) > 1.0
  for: 2m
  severity: critical

- alert: WebSocketConnectionDrop
  expr: rate(slack_websocket_connections_active[5m]) < -10000
  for: 1m
  severity: critical

- alert: KafkaConsumerLagHigh
  expr: slack_kafka_consumer_lag > 100000
  for: 5m
  severity: critical

- alert: MessageLossDetected
  expr: slack_messages_published_total - slack_messages_delivered_total > 1000
  for: 3m
  severity: critical

# Warning Alerts (Ticket)
- alert: SearchIndexLag
  expr: slack_search_index_lag_seconds > 60
  for: 10m
  severity: warning

- alert: CacheHitRateLow
  expr: redis_hit_rate < 0.85
  for: 15m
  severity: warning

- alert: ErrorRateElevated
  expr: rate(slack_api_request_total{status_code=~"5.."}[5m]) / rate(slack_api_request_total[5m]) > 0.01
  for: 5m
  severity: warning
```

### 10.5 SLO Dashboard

| SLI | SLO Target | Measurement |
|---|---|---|
| Message delivery success | 99.99% | Messages ACKed / Messages sent |
| API availability | 99.99% | Non-5xx responses / Total requests |
| Message delivery p99 latency | < 250ms | End-to-end send to display |
| Search availability | 99.9% | Successful queries / Total queries |
| Search p95 latency | < 500ms | Query to results returned |
| WebSocket uptime | 99.99% | Connected seconds / Total seconds |
| File upload success rate | 99.9% | Successful uploads / Attempted |
| Notification delivery | 99.5% | Delivered / Sent (push) |

---

## 11. Considerations & Assumptions

### Key Assumptions
1. **Scale**: System designed for Slack-scale (50M DAU), can be simplified for smaller deployments
2. **Cloud**: AWS-primary deployment (adaptable to GCP/Azure)
3. **Region**: Multi-region active-passive (active-active for enterprise tier)
4. **Message size**: Average 2KB with max 40KB (including blocks/formatting)
5. **Channel size**: 99% of channels have < 1000 members; 0.1% have > 10K
6. **Read/Write ratio**: 10:1 (users read far more than they write)
7. **Real-time priority**: DMs > mentions > channel messages > bots

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Message store | Cassandra over PostgreSQL | Append-heavy workload, natural time-series partitioning, horizontal scaling |
| Real-time transport | WebSocket over SSE | Bidirectional (typing, reactions), lower overhead |
| Event bus | Kafka over RabbitMQ | Durability, replay capability, ordered partitions |
| Search | Elasticsearch over PostgreSQL FTS | Better relevance, scaling, faceted search |
| Cache | Redis Cluster over Memcached | Data structures (sets, sorted sets, hashes), pub/sub |
| Presence | Redis TTL over dedicated DB | Ephemeral data, sub-ms latency, automatic expiry |
| File storage | S3 + pre-signed URLs | Decouple from app servers, CDN-friendly |

### Trade-offs

| Trade-off | Chosen | Alternative | When to switch |
|---|---|---|---|
| Consistency model | Eventual for messages, strong for membership | Strong everywhere | When regulatory requires strict ordering proof |
| Fanout strategy | Push for small channels, pull for large | Always push | If average channel size drops significantly |
| Multi-tenancy | Shared infrastructure, logical isolation | Physical isolation | Enterprise customers with compliance needs |
| Search freshness | 5-30s lag acceptable | Real-time search | If search is primary discovery mechanism |
| Message retention | Configurable per workspace | Infinite retention | Storage cost vs compliance requirements |

### Failure Scenarios & Mitigations

| Failure | Impact | Mitigation |
|---|---|---|
| Cassandra node down | Degraded write (still quorum) | Multi-AZ, RF=3, automatic repair |
| Redis cluster partition | Presence/cache stale | Fallback to DB, graceful degradation |
| Kafka broker down | Event processing delayed | RF=3, ISR monitoring, auto-failover |
| WebSocket gateway crash | Connections dropped | Client auto-reconnect, session buffer |
| Elasticsearch down | Search unavailable | Circuit breaker, "search temporarily unavailable" |
| S3 outage | File upload/download fails | Multi-region replication, retry queue |
| Full region outage | Complete service disruption | DNS failover to DR region (RPO < 1min, RTO < 5min) |

### Security Considerations
- End-to-end encryption for DMs (optional enterprise feature)
- Data at rest: AES-256 encryption (per-workspace keys via KMS)
- Data in transit: TLS 1.3 everywhere
- Token rotation: Access tokens expire in 1 hour, refresh tokens in 30 days
- Audit logging: All admin actions, data exports, permission changes
- DLP (Data Loss Prevention): Scan outgoing messages for sensitive patterns
- SOC2 Type II compliance for enterprise customers
- GDPR: Right to deletion, data portability, consent management

### Cost Optimization
- Cassandra: Use tiered storage (SSD for hot, HDD for cold partitions)
- S3: Intelligent-Tiering for files (auto-moves to cheaper tiers)
- Reserved instances for baseline capacity, spot for batch processing
- Kafka: Tiered storage (offload old segments to S3)
- CDN: Cache-control headers to maximize edge cache hits
- Elasticsearch: ILM policies (hot→warm→cold→delete)
- Compute: Auto-scaling based on WebSocket connections and message QPS
