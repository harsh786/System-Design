# WhatsApp / Signal Messenger — System Design

## 1. Functional Requirements

| # | Requirement | Description |
|---|-------------|-------------|
| FR-1 | 1:1 Messaging | Real-time text messaging between two users with E2E encryption |
| FR-2 | Group Messaging | Group chats up to 1024 members with sender-key encryption |
| FR-3 | Media Sharing | Send/receive images, videos, voice notes, documents (up to 2 GB) |
| FR-4 | Delivery & Read Receipts | Double-tick (delivered) and blue-tick (read) acknowledgements |
| FR-5 | Online/Typing Presence | Show last-seen, online status, and typing indicators |
| FR-6 | Multi-Device Sync | Seamless message sync across phone, tablet, desktop, web |
| FR-7 | Offline Message Delivery | Store-and-forward for offline recipients with TTL-based retention |
| FR-8 | Voice & Video Calls | 1:1 and group calls with WebRTC-based media relay |
| FR-9 | End-to-End Encryption | Signal Protocol with X3DH key agreement + Double Ratchet |
| FR-10 | Message Search | Full-text search across local and server-side encrypted index |
| FR-11 | Push Notifications | FCM/APNs push for offline devices with minimal metadata |
| FR-12 | Status/Stories | Ephemeral 24-hour status updates visible to contacts |

## 2. Non-Functional Requirements

| # | Requirement | Target |
|---|-------------|--------|
| NFR-1 | Message Delivery Latency | p50 < 100ms, p99 < 250ms (same region) |
| NFR-2 | Availability | 99.99% uptime (< 52 min downtime/year) |
| NFR-3 | Durability | Zero message loss — messages persisted until acknowledged |
| NFR-4 | Scalability | Support 500M+ DAU, 100B+ messages/day at peak |
| NFR-5 | Security | Forward secrecy, deniable authentication, sealed sender |
| NFR-6 | Multi-Region | Active-active in 5+ regions with < 500ms cross-region sync |
| NFR-7 | Connection Efficiency | Single long-lived connection per device, minimal battery drain |
| NFR-8 | Storage Efficiency | Server stores only encrypted blobs; plaintext never on server |
| NFR-9 | Consistency | Causal ordering within conversations; eventual across devices |
| NFR-10 | Compliance | GDPR right-to-erasure, data residency per jurisdiction |

## 3. Capacity Estimation

### 3.1 User Metrics

| Metric | Value |
|--------|-------|
| Monthly Active Users (MAU) | 2B |
| Daily Active Users (DAU) | 500M |
| Concurrent Connections (peak) | 150M |
| Messages per day | 100B |
| Average messages per user per day | 200 |
| Average group size | 12 members |
| Groups per user | 8 |
| Media messages (% of total) | 25% |

### 3.2 Throughput (QPS/RPS)

| Operation | Calculation | QPS |
|-----------|-------------|-----|
| Message Send | 100B / 86400s | ~1.16M |
| Message Deliver (fanout) | 1.16M × avg 1.5 recipients | ~1.74M |
| Delivery Receipts | 1.74M × 2 (delivered + read) | ~3.48M |
| Presence Updates | 500M × 10 updates/day / 86400 | ~58K |
| WebSocket Connections | 150M concurrent | — |
| Media Uploads | 25B / 86400s | ~290K |
| Push Notifications | ~500K/s peak | ~500K |

### 3.3 Storage Estimation

| Data Type | Calculation | Daily | Yearly |
|-----------|-------------|-------|--------|
| Text Messages | 100B × 0.75 × 200 bytes avg | 15 TB | 5.5 PB |
| Media (encrypted blobs) | 25B × 500 KB avg | 12.5 PB | 4.5 EB |
| Metadata (routing/keys) | 100B × 100 bytes | 10 TB | 3.6 PB |
| Message Queue (in-flight) | 5M × 2 KB | 10 GB | — |
| Key Material | 2B users × 5 devices × 1 KB | 10 TB | — |

### 3.4 Bandwidth Estimation

| Direction | Calculation | Bandwidth |
|-----------|-------------|-----------|
| Inbound (messages) | 1.16M/s × 2 KB avg | ~2.3 GB/s |
| Inbound (media) | 290K/s × 500 KB | ~145 GB/s |
| Outbound (delivery) | 1.74M/s × 2 KB | ~3.5 GB/s |
| Outbound (media downloads) | ~400K/s × 500 KB | ~200 GB/s |
| WebSocket Keepalive | 150M × 40 bytes/30s | ~200 MB/s |

## 4. Data Modeling

### 4.1 Users & Devices (PostgreSQL / CockroachDB)

```sql
CREATE TABLE users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number    VARCHAR(20) UNIQUE NOT NULL,
    display_name    VARCHAR(128),
    avatar_url      TEXT,
    identity_key    BYTEA NOT NULL,          -- Ed25519 public identity key
    signed_prekey   BYTEA NOT NULL,          -- current signed pre-key
    registration_id INTEGER NOT NULL,
    status_text     VARCHAR(256),
    privacy_settings JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE devices (
    device_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id),
    device_name     VARCHAR(128),
    platform        VARCHAR(20) NOT NULL,    -- ios, android, web, desktop
    push_token      TEXT,
    device_key      BYTEA NOT NULL,          -- per-device Signal key
    signed_prekey   BYTEA NOT NULL,
    last_seen_at    TIMESTAMPTZ DEFAULT now(),
    is_primary      BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, device_name)
);

CREATE INDEX idx_devices_user_id ON devices(user_id);
CREATE INDEX idx_devices_push_token ON devices(push_token) WHERE push_token IS NOT NULL;

CREATE TABLE one_time_prekeys (
    prekey_id       BIGSERIAL PRIMARY KEY,
    device_id       UUID NOT NULL REFERENCES devices(device_id),
    key_id          INTEGER NOT NULL,
    public_key      BYTEA NOT NULL,
    is_used         BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(device_id, key_id)
);

CREATE INDEX idx_prekeys_available ON one_time_prekeys(device_id, is_used)
    WHERE is_used = false;
```

### 4.2 Conversations & Memberships (PostgreSQL / CockroachDB)

```sql
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            VARCHAR(10) NOT NULL CHECK (type IN ('direct', 'group')),
    name            VARCHAR(256),
    avatar_url      TEXT,
    creator_id      UUID REFERENCES users(user_id),
    group_key       BYTEA,                   -- sender-key for group E2E
    max_members     INTEGER DEFAULT 1024,
    is_archived     BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE conversation_members (
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
    user_id         UUID NOT NULL REFERENCES users(user_id),
    role            VARCHAR(10) DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    joined_at       TIMESTAMPTZ DEFAULT now(),
    muted_until     TIMESTAMPTZ,
    last_read_msg   UUID,                    -- message_id of last read message
    last_read_at    TIMESTAMPTZ,
    PRIMARY KEY (conversation_id, user_id)
);

CREATE INDEX idx_members_user ON conversation_members(user_id);
CREATE INDEX idx_members_conv ON conversation_members(conversation_id);
```

### 4.3 Messages (Cassandra / ScyllaDB)

```sql
-- Partition by conversation + time bucket for bounded partition sizes
CREATE TABLE messages (
    conversation_id UUID,
    time_bucket     TEXT,                    -- e.g., '2026-05-28' (daily)
    message_id      TIMEUUID,               -- TimeUUID for ordering
    sender_id       UUID,
    message_type    TEXT,                    -- text, image, video, audio, document, system
    encrypted_body  BLOB,                   -- E2E encrypted payload
    media_ref       TEXT,                    -- S3 key for media (encrypted)
    media_size      BIGINT,
    media_mime      TEXT,
    reply_to        UUID,                    -- message_id of quoted message
    forwarded_from  UUID,
    is_edited       BOOLEAN,
    edit_history    LIST<FROZEN<TUPLE<TIMESTAMP, BLOB>>>,
    expires_at      TIMESTAMP,              -- disappearing messages
    server_ts       TIMESTAMP,
    PRIMARY KEY ((conversation_id, time_bucket), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
  AND default_time_to_live = 0
  AND gc_grace_seconds = 864000
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_size': 1,
                    'compaction_window_unit': 'DAYS'};
```

### 4.4 Delivery Receipts (Cassandra / ScyllaDB)

```sql
CREATE TABLE delivery_receipts (
    message_id      UUID,
    recipient_id    UUID,
    device_id       UUID,
    status          TEXT,                    -- sent, delivered, read
    status_ts       TIMESTAMP,
    PRIMARY KEY ((message_id), recipient_id, device_id)
) WITH default_time_to_live = 2592000;      -- 30-day TTL

-- Materialized view for querying by recipient
CREATE MATERIALIZED VIEW receipts_by_recipient AS
    SELECT * FROM delivery_receipts
    WHERE recipient_id IS NOT NULL
    AND message_id IS NOT NULL
    AND device_id IS NOT NULL
    PRIMARY KEY ((recipient_id), message_id, device_id);
```

### 4.5 Presence & Sessions (Redis)

```
# Active session: Hash per user
HSET session:{user_id} device:{device_id} '{"ws_node":"ws-42","connected_at":1716900000}'
EXPIRE session:{user_id} 300    # 5-min heartbeat TTL

# Presence: last-seen timestamp
SET presence:{user_id} 1716900000 EX 86400

# Typing indicator: ephemeral pub/sub
PUBLISH typing:{conversation_id} '{"user_id":"...","action":"start"}'

# Device message queue (offline delivery)
RPUSH mq:{device_id} '{"msg_id":"...","conversation_id":"...","encrypted_body":"..."}'
EXPIRE mq:{device_id} 2592000   # 30-day TTL
```

### 4.6 Indexing & Partitioning Strategy

| Table | Partition Key | Clustering Key | Strategy |
|-------|--------------|----------------|----------|
| messages | (conversation_id, time_bucket) | message_id DESC | Time-bucketed; hot partition ~50K msgs/day |
| delivery_receipts | message_id | recipient_id, device_id | Per-message grouping |
| users | — (PostgreSQL) | — | Hash-sharded by user_id in CockroachDB |
| devices | — | — | Co-located with users shard |
| conversation_members | — | — | Indexed both directions for lookup |

## 5. High-Level Design (HLD)

### 5.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT DEVICES                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                        │
│  │  iOS App │  │ Android  │  │ Desktop  │  │  Web App │                        │
│  │(Signal   │  │  App     │  │  App     │  │(Browser) │                        │
│  │Protocol) │  │          │  │          │  │          │                        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                        │
│       │              │              │              │                              │
└───────┼──────────────┼──────────────┼──────────────┼─────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           EDGE / CONNECTIVITY LAYER                               │
│                                                                                   │
│  ┌─────────────────┐    ┌──────────────────────────────────────┐                │
│  │   CloudFront    │    │          Global Load Balancer         │                │
│  │   (Media CDN)   │    │    (AWS NLB / Envoy / HAProxy)       │                │
│  └────────┬────────┘    └──────────────────┬───────────────────┘                │
│           │                                 │                                     │
│           │              ┌──────────────────┼──────────────────┐                │
│           │              ▼                  ▼                  ▼                 │
│           │    ┌─────────────────┐ ┌───────────────┐ ┌───────────────┐          │
│           │    │ WebSocket GW #1 │ │ WebSocket GW#2│ │ WebSocket GW#N│          │
│           │    │ (150K conns)    │ │ (150K conns)  │ │ (150K conns)  │          │
│           │    └────────┬────────┘ └───────┬───────┘ └───────┬───────┘          │
│           │             │                  │                  │                   │
└───────────┼─────────────┼──────────────────┼──────────────────┼──────────────────┘
            │             │                  │                  │
            │             ▼                  ▼                  ▼
┌───────────┼─────────────────────────────────────────────────────────────────────┐
│           │                    SERVICE MESH (Istio/Linkerd)                       │
│           │                                                                       │
│  ┌────────┴────────┐  ┌─────────────────┐  ┌─────────────────────┐             │
│  │  Media Service  │  │ Session Registry│  │  Connection Router  │             │
│  │                 │  │   (Redis Cluster)│  │                     │             │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘             │
│           │                    │                       │                          │
│  ┌────────┴────────┐  ┌───────┴────────┐  ┌──────────┴──────────┐              │
│  │  Object Store   │  │  Message       │  │   Key Distribution  │              │
│  │  (S3/R2/GCS)   │  │  Service       │  │   Service (KDS)     │              │
│  └─────────────────┘  └───────┬────────┘  └─────────────────────┘              │
│                                │                                                  │
│  ┌─────────────────┐  ┌───────┴────────┐  ┌─────────────────────┐              │
│  │  Notification   │  │ Fanout Workers │  │  Group Management   │              │
│  │  Service        │  │ (Kafka Consumer│  │  Service            │              │
│  │ (FCM/APNs)     │  │  Groups)       │  │                     │              │
│  └─────────────────┘  └───────┬────────┘  └─────────────────────┘              │
│                                │                                                  │
│  ┌─────────────────┐  ┌───────┴────────┐  ┌─────────────────────┐              │
│  │  Presence       │  │  Abuse/Mod     │  │  Sync Service       │              │
│  │  Service        │  │  Service       │  │  (Multi-device)     │              │
│  └─────────────────┘  └────────────────┘  └─────────────────────┘              │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             DATA / STORAGE LAYER                                  │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  ScyllaDB    │  │ CockroachDB  │  │ Redis Cluster│  │   Kafka      │        │
│  │  (Messages)  │  │ (Users/Meta) │  │ (Sessions/   │  │  (Events/    │        │
│  │  Multi-DC    │  │  Multi-Region│  │  Queues)     │  │   Fanout)    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                           │
│  │  S3 / R2     │  │ OpenSearch   │  │ ClickHouse   │                           │
│  │  (Media)     │  │ (Search Idx) │  │ (Analytics)  │                           │
│  └──────────────┘  └──────────────┘  └──────────────┘                           │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Core Service Responsibilities

| Service | Responsibility | Scaling Model |
|---------|---------------|---------------|
| WebSocket Gateway | Persistent connections, frame relay, heartbeat | Horizontal (1M conns per node with io_uring) |
| Session Registry | Maps user+device → WS node | Redis Cluster (hash-slots) |
| Connection Router | Routes outbound messages to correct WS node | Stateless; reads from session registry |
| Message Service | Validates, persists, publishes messages | Stateless; Kafka producer |
| Fanout Workers | Expands group messages to per-recipient delivery | Kafka consumer group (partition per conv) |
| Key Distribution Service | Manages Signal Protocol key bundles (prekeys, identity keys) | Stateless; backed by CockroachDB |
| Media Service | Upload/download with encryption, transcoding, CDN signing | Stateless; S3 multipart |
| Notification Service | FCM/APNs delivery for offline devices | Rate-limited; priority queues |
| Presence Service | Online/offline/typing ephemeral state | Redis Pub/Sub; lossy by design |
| Sync Service | Multi-device message sync with cursors | Reads from ScyllaDB; cursor in Redis |
| Group Management | CRUD for groups, membership, permissions | Stateless; CockroachDB |
| Abuse/Moderation | Spam detection, rate-limit, report handling | Flink streaming; ML inference |

## 6. Low-Level Design (LLD) — API Design

### 6.1 REST APIs

#### 6.1.1 User Registration

```
POST /api/v1/auth/register
```

**Request:**
```json
{
  "phone_number": "+14155551234",
  "identity_key": "base64_encoded_ed25519_public_key",
  "signed_prekey": {
    "key_id": 1,
    "public_key": "base64_encoded_curve25519_key",
    "signature": "base64_encoded_signature"
  },
  "one_time_prekeys": [
    {"key_id": 100, "public_key": "base64_encoded_key"},
    {"key_id": 101, "public_key": "base64_encoded_key"}
  ],
  "registration_id": 42,
  "device_name": "iPhone 15 Pro",
  "platform": "ios",
  "push_token": "fcm_or_apns_token"
}
```

**Response (201 Created):**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_id": "660e8400-e29b-41d4-a716-446655440001",
  "auth_token": "eyJhbGciOiJFZDI1NTE5...",
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2g...",
  "ws_endpoint": "wss://ws-us-east-1.messenger.io/connect",
  "expires_at": "2026-05-28T12:00:00Z"
}
```

#### 6.1.2 Get Pre-Key Bundle (for initiating E2E session)

```
GET /api/v1/keys/bundle/{user_id}/{device_id}
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
  "identity_key": "base64_encoded_identity_key",
  "signed_prekey": {
    "key_id": 5,
    "public_key": "base64_encoded_key",
    "signature": "base64_encoded_sig"
  },
  "one_time_prekey": {
    "key_id": 142,
    "public_key": "base64_encoded_key"
  },
  "registration_id": 42
}
```

#### 6.1.3 Create Group Conversation

```
POST /api/v1/conversations
Authorization: Bearer {token}
```

**Request:**
```json
{
  "type": "group",
  "name": "Engineering Team",
  "members": [
    {"user_id": "user-uuid-1", "role": "admin"},
    {"user_id": "user-uuid-2", "role": "member"},
    {"user_id": "user-uuid-3", "role": "member"}
  ],
  "settings": {
    "disappearing_messages_ttl": 604800,
    "only_admins_can_send": false,
    "only_admins_can_edit_info": true
  }
}
```

**Response (201 Created):**
```json
{
  "conversation_id": "770e8400-e29b-41d4-a716-446655440002",
  "type": "group",
  "name": "Engineering Team",
  "created_at": "2026-05-28T10:00:00Z",
  "member_count": 3,
  "group_invite_link": "https://msg.io/g/abc123def456",
  "sender_key_distribution": {
    "chain_key": "base64_encoded_chain_key",
    "iteration": 0,
    "signing_key": "base64_encoded_signing_key"
  }
}
```

#### 6.1.4 Upload Media (Pre-signed URL)

```
POST /api/v1/media/upload
Authorization: Bearer {token}
```

**Request:**
```json
{
  "conversation_id": "770e8400-e29b-41d4-a716-446655440002",
  "file_name": "photo.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 2457600,
  "encrypted_hash": "sha256:base64_encoded_hash_of_encrypted_blob"
}
```

**Response (200 OK):**
```json
{
  "media_id": "media-uuid-001",
  "upload_url": "https://media-us-east-1.messenger.io/upload/presigned...",
  "upload_headers": {
    "Content-Type": "application/octet-stream",
    "x-amz-server-side-encryption": "AES256"
  },
  "cdn_url": "https://cdn.messenger.io/media/media-uuid-001",
  "expires_at": "2026-05-28T10:30:00Z"
}
```

#### 6.1.5 Sync Messages (Multi-Device)

```
GET /api/v1/sync/messages?cursor={last_msg_id}&limit=100&device_id={device_id}
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
  "messages": [
    {
      "message_id": "01903d4e-7a3b-7000-8000-000000000001",
      "conversation_id": "770e8400-...",
      "sender_id": "550e8400-...",
      "message_type": "text",
      "encrypted_body": "base64_encrypted_ciphertext",
      "server_ts": "2026-05-28T09:55:00Z"
    }
  ],
  "next_cursor": "01903d4e-7a3b-7000-8000-000000000100",
  "has_more": true,
  "sync_state": "catching_up"
}
```

### 6.2 WebSocket Protocol (Binary Frames)

#### 6.2.1 Connection Handshake

```
Client → Server: CONNECT frame
{
  "type": "connect",
  "auth_token": "eyJhbGci...",
  "device_id": "660e8400-...",
  "protocol_version": 4,
  "last_seen_server_ts": 1716900000000,
  "capabilities": ["e2e_v2", "groups_v3", "calls_v1"]
}

Server → Client: CONNECTED frame
{
  "type": "connected",
  "session_id": "sess-uuid-001",
  "server_ts": 1716900001000,
  "pending_messages": 42,
  "heartbeat_interval_ms": 30000
}
```

#### 6.2.2 Send Message

```
Client → Server: MESSAGE frame
{
  "type": "message",
  "id": "client-generated-uuid",
  "conversation_id": "770e8400-...",
  "content": {
    "type": "ciphertext",
    "body": "base64_encoded_signal_protocol_message",
    "registration_id": 42,
    "device_id": 1
  },
  "timestamp": 1716900005000
}

Server → Client: ACK frame
{
  "type": "ack",
  "id": "client-generated-uuid",
  "server_id": "01903d4e-7a3b-...",
  "server_ts": 1716900005050,
  "status": "accepted"
}
```

#### 6.2.3 Receive Message

```
Server → Client: DELIVER frame
{
  "type": "deliver",
  "message_id": "01903d4e-7a3b-...",
  "conversation_id": "770e8400-...",
  "sender_id": "550e8400-...",
  "content": {
    "type": "prekey_signal_message",
    "body": "base64_encoded_ciphertext",
    "registration_id": 55
  },
  "server_ts": 1716900005050
}

Client → Server: RECEIPT frame
{
  "type": "receipt",
  "message_id": "01903d4e-7a3b-...",
  "status": "delivered",
  "timestamp": 1716900005100
}
```

### 6.3 gRPC Service Definitions (Internal)

```protobuf
syntax = "proto3";
package messenger.internal;

service MessageRouter {
  // Route a message to recipient device(s)
  rpc RouteMessage(RouteRequest) returns (RouteResponse);
  // Batch deliver to multiple recipients (group fanout)
  rpc FanoutMessage(FanoutRequest) returns (FanoutResponse);
  // Retrieve pending messages for a device
  rpc DrainQueue(DrainRequest) returns (stream EncryptedEnvelope);
}

message RouteRequest {
  string message_id = 1;
  string sender_id = 2;
  string conversation_id = 3;
  repeated RecipientEnvelope envelopes = 4;
  int64 server_timestamp = 5;
  MessagePriority priority = 6;
}

message RecipientEnvelope {
  string recipient_id = 1;
  string device_id = 2;
  bytes encrypted_payload = 3;
  ContentType content_type = 4;
}

message RouteResponse {
  map<string, DeliveryStatus> delivery_results = 1;
  int64 server_timestamp = 2;
}

enum DeliveryStatus {
  DELIVERED_ONLINE = 0;
  QUEUED_OFFLINE = 1;
  PUSH_SENT = 2;
  DEVICE_STALE = 3;
  FAILED = 4;
}

enum MessagePriority {
  NORMAL = 0;
  HIGH = 1;      // calls, urgent
  LOW = 2;       // typing, presence
}

enum ContentType {
  TEXT = 0;
  MEDIA = 1;
  RECEIPT = 2;
  KEY_EXCHANGE = 3;
  GROUP_UPDATE = 4;
  CALL_SIGNAL = 5;
}

service KeyDistribution {
  rpc GetPreKeyBundle(PreKeyBundleRequest) returns (PreKeyBundleResponse);
  rpc ReplenishPreKeys(ReplenishRequest) returns (ReplenishResponse);
  rpc RotateSignedPreKey(RotateRequest) returns (RotateResponse);
}

message PreKeyBundleRequest {
  string target_user_id = 1;
  string target_device_id = 2;
  string requester_id = 3;
}

message PreKeyBundleResponse {
  bytes identity_key = 1;
  SignedPreKey signed_prekey = 2;
  OneTimePreKey one_time_prekey = 3;
  int32 registration_id = 4;
}

message SignedPreKey {
  int32 key_id = 1;
  bytes public_key = 2;
  bytes signature = 3;
}

message OneTimePreKey {
  int32 key_id = 1;
  bytes public_key = 2;
}
```

### 6.4 Kafka Event Contracts

```json
// Topic: messenger.messages.incoming
{
  "event_type": "message.received",
  "event_id": "evt-uuid-001",
  "timestamp": "2026-05-28T10:00:05.050Z",
  "payload": {
    "message_id": "01903d4e-7a3b-...",
    "conversation_id": "770e8400-...",
    "sender_id": "550e8400-...",
    "message_type": "text",
    "encrypted_size_bytes": 256,
    "recipient_count": 5,
    "is_group": true
  },
  "metadata": {
    "region": "us-east-1",
    "ws_node": "ws-gateway-042",
    "trace_id": "trace-abc-123"
  }
}

// Topic: messenger.messages.fanout
{
  "event_type": "message.route",
  "event_id": "evt-uuid-002",
  "timestamp": "2026-05-28T10:00:05.060Z",
  "payload": {
    "message_id": "01903d4e-7a3b-...",
    "recipient_id": "user-uuid-2",
    "device_id": "device-uuid-5",
    "encrypted_payload": "base64...",
    "delivery_attempt": 1,
    "ws_node_hint": "ws-gateway-017"
  }
}

// Topic: messenger.receipts
{
  "event_type": "receipt.delivered",
  "event_id": "evt-uuid-003",
  "timestamp": "2026-05-28T10:00:05.100Z",
  "payload": {
    "message_id": "01903d4e-7a3b-...",
    "recipient_id": "user-uuid-2",
    "device_id": "device-uuid-5",
    "status": "delivered"
  }
}
```

## 7. Architecture Components

### 7.1 Edge & Connectivity

| Component | Technology | Purpose |
|-----------|------------|---------|
| DNS | Route 53 / Cloudflare | Latency-based routing to nearest region |
| CDN | CloudFront / Cloudflare R2 | Media distribution with signed URLs |
| WAF | AWS WAF / Cloudflare | Rate-limit, bot protection, geo-blocking |
| TCP Load Balancer | AWS NLB | Layer-4 LB for WebSocket (no HTTP overhead) |
| TLS Termination | Envoy (per-node) | Noise Protocol or TLS 1.3 with certificate pinning |
| WebSocket Gateway | Custom Rust service | io_uring for 500K+ conns/node, epoll fallback |

### 7.2 Application Services

| Service | Language | Framework | Notes |
|---------|----------|-----------|-------|
| Message Service | Go | stdlib + gRPC | High-throughput; Kafka producer |
| Fanout Workers | Go | Sarama (Kafka consumer) | Partition-parallel processing |
| Key Distribution | Rust | Tonic (gRPC) | Cryptographic operations; constant-time |
| Media Service | Go | stdlib + S3 SDK | Multipart upload/download |
| Notification Service | Java | Spring Boot | FCM/APNs SDK integration |
| Presence Service | Go | Redis client | Ephemeral pub/sub |
| Sync Service | Go | gRPC streaming | Cursor-based sync from ScyllaDB |
| Group Management | Go | stdlib + CockroachDB | ACID membership operations |
| Abuse/Moderation | Python | Flink + ML models | Streaming anomaly detection |

### 7.3 Data Stores

| Store | Technology | Use Case | Replication |
|-------|------------|----------|-------------|
| Message Store | ScyllaDB (6-node per DC) | Message persistence | RF=3, LOCAL_QUORUM |
| User/Meta Store | CockroachDB (9-node) | Users, conversations, keys | Multi-region Raft |
| Session/Queue | Redis Cluster (30 shards) | Sessions, offline queues, presence | 1 replica per shard |
| Event Bus | Kafka (Confluent) | Message routing, receipts, analytics | RF=3, ISR=2 |
| Object Store | S3 (cross-region repl) | Encrypted media blobs | Cross-region repl |
| Search Index | OpenSearch | Encrypted metadata search | 3-node cluster |
| Analytics | ClickHouse | Metrics aggregation, reporting | ReplicatedMergeTree |
| Feature Flags | LaunchDarkly | Gradual rollouts | — |

## 8. Deep Dives

### 8.1 End-to-End Encryption (Signal Protocol)

#### X3DH Key Agreement (Session Initialization)

```
┌─────────┐                              ┌─────────┐
│  Alice  │                              │   Bob   │
│ (sender)│                              │(receiver)│
└────┬────┘                              └────┬────┘
     │                                        │
     │  1. Fetch Bob's pre-key bundle         │
     │        (IKb, SPKb, OPKb)               │
     │ ◄──────────────────────────────────────│
     │                                        │
     │  2. Generate ephemeral key EKa         │
     │                                        │
     │  3. Compute shared secrets:            │
     │     DH1 = DH(IKa, SPKb)              │
     │     DH2 = DH(EKa, IKb)               │
     │     DH3 = DH(EKa, SPKb)              │
     │     DH4 = DH(EKa, OPKb)  [optional]  │
     │                                        │
     │  4. SK = KDF(DH1 || DH2 || DH3 || DH4)│
     │                                        │
     │  5. Initialize Double Ratchet with SK  │
     │                                        │
     │  6. Send PreKeySignalMessage           │
     │     (IKa, EKa, OPK_id, ciphertext)    │
     │────────────────────────────────────────►│
     │                                        │
     │                 7. Bob derives same SK  │
     │                    Initializes ratchet  │
     │                                        │
```

#### Double Ratchet Algorithm

```
Each message exchange ratchets forward:

Sending Chain:                    Receiving Chain:
  Root Key (RK)                     Root Key (RK)
       │                                 │
       ▼                                 ▼
  Chain Key (CK_s) ──► KDF ──► Message Key (MK_s)
       │                            │
       ▼                            ▼
  Next CK_s                    Encrypt(plaintext, MK_s) = ciphertext

DH Ratchet Step (on each reply):
  New DH pair generated
  New Root Key derived: RK' = KDF(RK, DH(my_new, their_current))
  New Chain Key starts from RK'
  
  → Forward secrecy: compromising current keys doesn't reveal past messages
  → Post-compromise security: after ratchet step, attacker loses access
```

#### Group Messaging (Sender Keys)

```
For groups, we use Sender Key Distribution Message (SKDM):

1. Alice creates a Sender Key for group G:
   - chain_key (random 32 bytes)
   - signing_key (Ed25519 keypair)

2. Alice encrypts SKDM with each member's pairwise session:
   - SKDM contains: chain_key, signing_key_public, iteration=0

3. When Alice sends to group:
   - Derive message_key = HMAC-SHA256(chain_key, iteration)
   - Encrypt message with AES-256-CBC(message_key, plaintext)
   - Sign with signing_key
   - Single ciphertext sent to server

4. Server fans out same ciphertext to all members
   - Each member derives message_key from their copy of Alice's chain_key
   - Verify signature against Alice's signing_key_public

Advantages over pairwise:
  - O(1) encryption for sender (vs O(N) pairwise)
  - Single blob stored on server (vs N copies)
  
Trade-off:
  - Member removal requires new sender key from ALL remaining members
  - No post-compromise security without periodic re-key
```

### 8.2 WebSocket Gateway Deep Dive

#### Connection Management Architecture

```rust
// Simplified WebSocket Gateway (Rust with io_uring)
struct WsGateway {
    connections: DashMap<DeviceId, ConnectionHandle>,
    session_registry: RedisCluster,
    message_bus: KafkaProducer,
    metrics: PrometheusMetrics,
}

struct ConnectionHandle {
    device_id: DeviceId,
    user_id: UserId,
    tx: mpsc::Sender<Frame>,         // outbound channel
    connected_at: Instant,
    last_heartbeat: AtomicU64,
    encryption_state: NoiseState,     // Noise_IK protocol state
}

impl WsGateway {
    async fn handle_connection(&self, stream: TcpStream) {
        // 1. TLS handshake (certificate pinning)
        let tls_stream = self.tls_acceptor.accept(stream).await?;
        
        // 2. WebSocket upgrade
        let ws_stream = tokio_tungstenite::accept(tls_stream).await?;
        
        // 3. Authentication frame (first frame must be CONNECT)
        let connect_frame = ws_stream.next().await?;
        let (user_id, device_id) = self.authenticate(connect_frame)?;
        
        // 4. Register in session registry
        self.session_registry.register(user_id, device_id, self.node_id).await;
        
        // 5. Create connection handle
        let (tx, rx) = mpsc::channel(1024);
        let handle = ConnectionHandle::new(user_id, device_id, tx);
        self.connections.insert(device_id, handle);
        
        // 6. Drain offline queue
        self.drain_offline_queue(device_id, &tx).await;
        
        // 7. Split into read/write loops
        let (ws_write, ws_read) = ws_stream.split();
        tokio::join!(
            self.read_loop(ws_read, user_id, device_id),
            self.write_loop(ws_write, rx),
            self.heartbeat_loop(device_id),
        );
        
        // 8. Cleanup on disconnect
        self.connections.remove(&device_id);
        self.session_registry.unregister(user_id, device_id).await;
    }
}
```

#### Connection Scaling Strategy

| Strategy | Detail |
|----------|--------|
| Connections per node | 500K (Rust + io_uring, 64 GB RAM, 16 cores) |
| Total fleet size | 300 nodes for 150M concurrent connections |
| Connection draining | Graceful: signal GOAWAY, wait 30s, then force close |
| Auto-scaling | Scale on connection count (threshold: 400K/node) |
| Sticky routing | Hash(device_id) → consistent hash ring → node |
| Failover | Client reconnects with exponential backoff (1s, 2s, 4s...) |
| Keepalive | Client sends PING every 30s; server expects within 90s |

### 8.3 Offline Message Delivery

#### Store-and-Forward Pipeline

```
┌──────────┐     ┌────────────┐     ┌──────────────┐     ┌──────────┐
│  Sender  │────►│  Message   │────►│   Fanout     │────►│  Router  │
│          │     │  Service   │     │   Workers    │     │          │
└──────────┘     └────────────┘     └──────────────┘     └────┬─────┘
                                                               │
                                              ┌────────────────┼─────────────────┐
                                              │                │                  │
                                              ▼                ▼                  ▼
                                    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                                    │  Online?     │  │  Offline?    │  │  Stale?      │
                                    │  → WS push   │  │  → Queue     │  │  → Push notif│
                                    └──────────────┘  └──────────────┘  └──────────────┘
                                                             │
                                                             ▼
                                                    ┌──────────────┐
                                                    │  Redis Queue │
                                                    │  (per-device)│
                                                    │  TTL: 30 days│
                                                    └──────┬───────┘
                                                           │
                                                    On reconnect:
                                                           │
                                                           ▼
                                                    ┌──────────────┐
                                                    │  Drain Queue │
                                                    │  → Deliver   │
                                                    │  → ACK+remove│
                                                    └──────────────┘
```

#### Offline Queue Implementation

```
Per-device queue in Redis:
  Key: mq:{device_id}
  Type: Sorted Set (score = server_timestamp)
  
  ZADD mq:{device_id} 1716900005 "{\"msg_id\":\"...\",\"conv_id\":\"...\",\"payload\":\"...\"}"
  
On reconnect:
  1. ZRANGEBYSCORE mq:{device_id} {last_sync_ts} +inf LIMIT 0 100
  2. Deliver batch via WebSocket
  3. Client ACKs each message
  4. ZREM mq:{device_id} {acked_messages}
  
Overflow protection:
  - Max queue size: 10,000 messages per device
  - ZREMRANGEBYRANK mq:{device_id} 0 -10001  (trim oldest)
  - Beyond limit: send push notification "You have new messages"

Cross-region:
  - If user is in region B but message arrives in region A:
  - Publish to Kafka topic "messenger.cross-region.{region_b}"
  - Region B consumer delivers or queues locally
```

### 8.4 Multi-Device Sync

#### Sync Architecture

```
Device A (primary)              Server                    Device B (secondary)
     │                            │                            │
     │  Send message              │                            │
     │  (encrypted for each       │                            │
     │   recipient device)        │                            │
     │ ──────────────────────────►│                            │
     │                            │  Also encrypt for          │
     │                            │  own other devices         │
     │                            │ ──────────────────────────►│
     │                            │                            │
     │                            │  Sync cursor update        │
     │                            │◄────────────────────────── │
     │                            │                            │

Sync Protocol:
  1. Each device maintains a sync_cursor (last processed server_ts)
  2. On connect, device sends cursor to Sync Service
  3. Sync Service queries ScyllaDB: messages WHERE server_ts > cursor
  4. Streams missed messages to device
  5. Device ACKs, cursor advances
  
Self-message encryption:
  - When Alice sends a message, she also encrypts it for her other devices
  - Uses pairwise sessions between her own devices
  - Ensures all devices can decrypt conversation history
```

### 8.5 Media Pipeline

```
┌────────┐    ┌──────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Client │    │  Media   │    │   S3    │    │  CDN    │    │Recipient│
│        │    │ Service  │    │         │    │         │    │         │
└───┬────┘    └────┬─────┘    └────┬────┘    └────┬────┘    └────┬────┘
    │              │               │              │              │
    │ 1. Request   │               │              │              │
    │    upload URL│               │              │              │
    │─────────────►│               │              │              │
    │              │               │              │              │
    │ 2. Pre-signed│               │              │              │
    │    URL       │               │              │              │
    │◄─────────────│               │              │              │
    │              │               │              │              │
    │ 3. Client encrypts file locally (AES-256-CBC)             │
    │    - Random file key K                                     │
    │    - Encrypt: E = AES(K, plaintext_file)                  │
    │    - HMAC: H = HMAC-SHA256(K, E)                          │
    │              │               │              │              │
    │ 4. Upload encrypted blob     │              │              │
    │──────────────────────────────►│              │              │
    │              │               │              │              │
    │ 5. Send message with media reference + encrypted key       │
    │    (key K encrypted in Signal message to each recipient)   │
    │─────────────►│               │              │              │
    │              │               │              │              │
    │              │  6. Notify recipient with media ref          │
    │              │──────────────────────────────────────────────►│
    │              │               │              │              │
    │              │               │  7. Recipient downloads      │
    │              │               │◄─────────────────────────────│
    │              │               │              │              │
    │              │               │  8. CDN serves encrypted blob│
    │              │               │──────────────►│──────────────►│
    │              │               │              │              │
    │              │               │              │  9. Decrypt   │
    │              │               │              │     with K    │
```

### 8.6 Receipt Delivery

```
Message lifecycle:
  ✓  (single tick)  = Server received message
  ✓✓ (double tick)  = All recipient devices ACK'd delivery
  ✓✓ (blue ticks)   = Recipient opened conversation (read receipt)

Implementation:
  1. Sender sends message → Server ACKs with single tick
  2. Each recipient device ACKs delivery → Fanout worker aggregates
  3. When ALL devices of recipient ACK → emit "delivered" event to sender
  4. Recipient opens conversation → client sends "read" receipt
  5. Read receipt forwarded to sender → blue ticks displayed

Optimization:
  - Receipts are fire-and-forget (UDP semantics over WebSocket)
  - Batch receipts: aggregate multiple reads into one frame every 500ms
  - Delivered receipts are per-device; read receipts are per-user
  - Privacy: user can disable read receipts (bilateral — they also can't see others')
```

## 9. Optimization

### 9.1 Caching Strategy

| Cache Layer | What | TTL | Invalidation |
|-------------|------|-----|-------------|
| Client-side (SQLite) | Messages, contacts, keys | Permanent | Sync cursor advancement |
| CDN (CloudFront) | Media blobs | 30 days | Immutable (content-addressed) |
| Redis L1 | Session registry (user→node) | 5 min | On disconnect event |
| Redis L2 | Pre-key bundles (hot users) | 1 hour | On key rotation |
| Redis L3 | Group membership lists | 10 min | On membership change |
| Application | Conversation metadata | 5 min | Event-driven invalidation |

### 9.2 Connection Efficiency

```
Battery Optimization:
  - Adaptive heartbeat: 30s on WiFi, 60s on cellular, 180s on battery saver
  - Message batching: coalesce multiple outbound frames within 50ms window
  - Binary protocol: Protobuf frames (60% smaller than JSON)
  - Connection resumption: session tickets allow skip of full handshake
  - Push-only mode: after 5 min idle, close WS, rely on FCM/APNs push to wake

Bandwidth Optimization:
  - Delta sync: only fetch messages since last cursor, not full history
  - Thumbnail preview: 10 KB blur-hash in message; full media lazy-loaded
  - Compression: zstd compression on WebSocket frames (40% reduction)
  - Progressive media: JPEG progressive scan, HLS for video
```

### 9.3 Database Optimization

```
ScyllaDB Tuning:
  - Time-bucketed partitions: cap partition size at 100 MB (daily buckets)
  - Prepared statements: avoid parsing overhead (30% throughput gain)
  - Token-aware routing: client routes directly to owning node
  - Speculative retries: send to 2nd replica after 5ms (p99 improvement)
  - Compaction: TimeWindowCompactionStrategy aligned with bucket TTL
  - Bloom filter: fp_chance=0.01 for messages table (memory vs disk trade-off)

CockroachDB Tuning:
  - Locality-aware placement: user data pinned to home region
  - Follower reads: read from nearest replica for non-critical reads
  - Column families: separate hot columns (presence) from cold (identity_key)
  - Zone configs: pin system ranges to SSD, archive to HDD tier

Redis Optimization:
  - Pipeline commands: batch 10-50 operations per round-trip
  - Lua scripts for atomic operations (check-and-set patterns)
  - Memory policy: allkeys-lru for presence, noeviction for queues
  - Cluster topology: 30 masters, 30 replicas across 3 AZs
```

### 9.4 Async Processing

```
Kafka Topic Design:
  - messenger.messages.incoming     (partitions: 256, key: conversation_id)
  - messenger.messages.fanout       (partitions: 512, key: recipient_id)  
  - messenger.receipts              (partitions: 128, key: message_id)
  - messenger.presence              (partitions: 64, key: user_id, compact)
  - messenger.analytics             (partitions: 32, key: none)

Consumer Group Strategy:
  - Fanout workers: 512 consumers (1:1 with partitions) for max parallelism
  - Receipt aggregator: 32 consumers with windowed aggregation
  - Analytics pipeline: 8 consumers feeding ClickHouse

Backpressure Handling:
  - If consumer lag > 100K messages: scale up consumer group
  - If lag > 1M: activate priority queue (deliver recent messages first)
  - Dead letter queue for messages that fail 3x delivery attempts
```

## 10. Observability

### 10.1 Key Metrics (Prometheus)

```yaml
# Message delivery latency (sender → recipient device)
messenger_message_delivery_duration_seconds:
  type: histogram
  labels: [region, message_type, conversation_type]
  buckets: [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]

# WebSocket connection count per node
messenger_ws_connections_active:
  type: gauge
  labels: [node_id, region, platform]

# Message throughput
messenger_messages_processed_total:
  type: counter
  labels: [operation, status, region]
  # operation: send, deliver, fanout, receipt

# Offline queue depth
messenger_offline_queue_depth:
  type: gauge
  labels: [region, priority]

# Pre-key availability (critical for E2E)
messenger_prekeys_available:
  type: gauge
  labels: [user_bucket]
  # Alert if any user drops below 10 prekeys

# Kafka consumer lag
messenger_kafka_consumer_lag:
  type: gauge
  labels: [topic, consumer_group, partition]

# Encryption errors (session corruption)
messenger_encryption_errors_total:
  type: counter
  labels: [error_type, platform]
  # error_type: session_not_found, mac_mismatch, invalid_prekey

# Media upload/download performance
messenger_media_operation_duration_seconds:
  type: histogram
  labels: [operation, media_type, region]
  buckets: [0.1, 0.5, 1.0, 5.0, 10.0, 30.0]
```

### 10.2 Distributed Tracing (OpenTelemetry)

```
Trace: message_send_e2e
├─ Span: client.encrypt (client-side, not reported to server)
├─ Span: ws_gateway.receive_frame
│   └─ Attribute: frame_size_bytes, device_id
├─ Span: message_service.validate
│   └─ Attribute: conversation_type, member_count
├─ Span: message_service.persist (ScyllaDB write)
│   └─ Attribute: partition_key, write_latency_ms
├─ Span: kafka.produce (messenger.messages.incoming)
│   └─ Attribute: partition, offset
├─ Span: fanout_worker.expand
│   └─ Attribute: recipient_count, online_count, offline_count
├─ Span: connection_router.deliver (per recipient)
│   ├─ Span: redis.lookup_session
│   ├─ Span: ws_gateway.push_frame
│   └─ Attribute: delivery_status
└─ Span: notification_service.push (if offline)
    └─ Attribute: push_provider, push_latency_ms
```

### 10.3 Alerting Rules

```yaml
groups:
  - name: messenger_critical
    rules:
      - alert: MessageDeliveryLatencyHigh
        expr: |
          histogram_quantile(0.99,
            rate(messenger_message_delivery_duration_seconds_bucket[5m])
          ) > 0.5
        for: 3m
        labels:
          severity: critical
          team: messaging
        annotations:
          summary: "p99 message delivery > 500ms"
          runbook: "https://runbooks.internal/messenger/delivery-latency"

      - alert: WebSocketConnectionsDroppingFast
        expr: |
          rate(messenger_ws_connections_active[5m]) < -10000
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Losing >10K WS connections/min — possible node failure"

      - alert: PreKeyExhaustionRisk
        expr: |
          messenger_prekeys_available < 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Users with < 10 prekeys — new sessions will fail"
          action: "Trigger prekey replenishment push to affected devices"

      - alert: KafkaFanoutLagCritical
        expr: |
          messenger_kafka_consumer_lag{topic="messenger.messages.fanout"} > 500000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Fanout lag > 500K — messages delayed"
          action: "Scale fanout consumer group"

      - alert: OfflineQueueOverflow
        expr: |
          messenger_offline_queue_depth > 5000000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Offline queue growing — check push notification delivery"

      - alert: EncryptionErrorSpike
        expr: |
          rate(messenger_encryption_errors_total[5m]) > 100
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "E2E encryption errors spiking — possible key corruption"
          action: "Check recent client deploys; may need session reset flow"
```

### 10.4 Dashboards

| Dashboard | Panels |
|-----------|--------|
| Real-time Overview | Messages/sec, active connections, delivery latency p50/p95/p99, error rate |
| Connection Health | Connections per node, connect/disconnect rates, handshake failures, heartbeat timeouts |
| Message Pipeline | Kafka throughput, consumer lag per topic, fanout expansion factor, DLQ depth |
| Encryption Health | Pre-key inventory, session establishment rate, encryption errors by type, key rotation events |
| Media Pipeline | Upload/download throughput, S3 latency, CDN hit ratio, transcoding queue depth |
| Regional | Per-region message volume, cross-region latency, failover status |

## 11. Considerations & Assumptions

### 11.1 Trade-Off Analysis

| Decision | Option A | Option B | Choice | Rationale |
|----------|----------|----------|--------|-----------|
| Message Store | Cassandra | ScyllaDB | **ScyllaDB** | Lower tail latency (no GC), compatible CQL, better utilization |
| Metadata Store | PostgreSQL | CockroachDB | **CockroachDB** | Multi-region ACID without manual sharding; Raft consensus |
| Protocol | JSON over WS | Binary Protobuf over WS | **Binary** | 60% bandwidth reduction; critical at 100B+ msgs/day |
| Group Encryption | Pairwise per-member | Sender Keys | **Sender Keys** | O(1) sender cost; trade-off: re-key on member removal |
| Offline Storage | Database | Redis Sorted Sets | **Redis** | Sub-ms drain latency; acceptable durability with AOF |
| Media Encryption | Server-side | Client-side E2E | **Client-side** | Zero-knowledge server; compliance friendly |
| Presence | Strong consistency | Eventual (lossy) | **Eventual** | Presence is advisory; save resources |
| Message Ordering | Total order | Causal per-conversation | **Causal** | Total order is too expensive at scale; causal sufficient |

### 11.2 Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Server compromise | Zero-knowledge: server never sees plaintext; only encrypted blobs |
| Key compromise | Forward secrecy via Double Ratchet; past messages safe |
| Replay attacks | TimeUUID message IDs + per-session counter + MAC |
| Traffic analysis | Sealed sender: server doesn't know who sent (optional) |
| Device theft | Local database encrypted with device passcode/biometric |
| MITM | Certificate pinning + safety number verification |
| Metadata leakage | Minimal server-side metadata; encrypted sender in envelope |
| Abuse/spam | Rate limiting, ML-based detection on encrypted metadata patterns |

### 11.3 Failure Modes & Recovery

| Failure | Impact | Recovery |
|---------|--------|----------|
| WS Gateway node dies | 500K connections dropped | Clients reconnect (consistent hash → new node); drain queue |
| ScyllaDB node failure | Reads/writes degrade | RF=3 → tolerate 1 failure; replace + repair |
| Redis shard failure | Offline queues lost | Replica promotes; some messages re-queued from Kafka |
| Kafka broker failure | Message pipeline stalls | ISR=2 → leader election; consumer rebalance |
| CockroachDB region failure | User metadata unavailable | Raft failover to other regions (< 10s) |
| CDN outage | Media unavailable | Fallback to direct S3 signed URL (slower) |
| Push provider (FCM) outage | Offline users not notified | Retry queue with exponential backoff; dual-provider |

### 11.4 Deployment Strategy

```
Multi-Region Active-Active:
  - 5 primary regions: us-east-1, eu-west-1, ap-southeast-1, ap-northeast-1, sa-east-1
  - Users homed to nearest region (DNS latency-based routing)
  - Cross-region message routing via Kafka MirrorMaker 2
  - CockroachDB spans all regions with regional leaseholders

Rolling Deployment:
  1. Canary: 1% traffic (single WS gateway node)
  2. Regional: one full region (25% traffic)
  3. Global: remaining regions
  4. Monitoring: 15-min bake time between stages
  5. Rollback: instant via load balancer drain + old image

Blue-Green for Breaking Changes:
  - Protocol version negotiation in CONNECT frame
  - Old clients continue on v3 gateway fleet
  - New clients upgrade to v4 gateway fleet
  - Sunset v3 after 99% adoption (typically 30 days)
```

### 11.5 Cost Model (Monthly Estimate at 500M DAU)

| Component | Specification | Monthly Cost |
|-----------|--------------|-------------|
| WS Gateway Fleet | 300 × c6gn.8xlarge (32 vCPU, 64 GB) | ~$800K |
| ScyllaDB Cluster | 18 × i3en.6xlarge (24 vCPU, 192 GB, 15 TB NVMe) × 3 DCs | ~$1.2M |
| CockroachDB | 27 × m6i.4xlarge (16 vCPU, 64 GB) × 3 regions | ~$250K |
| Redis Cluster | 60 × r6g.4xlarge (16 vCPU, 128 GB) | ~$400K |
| Kafka (Confluent) | 24 × m6i.8xlarge per region × 5 regions | ~$600K |
| S3 Storage | ~5 EB total with lifecycle policies | ~$2M |
| CDN (CloudFront) | ~200 GB/s sustained egress | ~$1.5M |
| Compute (Services) | ~500 × m6i.2xlarge across services | ~$400K |
| Network Transfer | Cross-AZ + cross-region | ~$500K |
| **Total** | | **~$7.6M/month** |

### 11.6 Assumptions

1. Client-side encryption is non-negotiable; server never holds plaintext
2. Users accept ~1s message delay for cross-region delivery
3. 30-day message retention on server (offline queue); clients store full history locally
4. Group size capped at 1024 to bound sender-key distribution cost
5. Media stored indefinitely (lifecycle to Glacier after 90 days)
6. Voice/video calls use separate TURN/STUN infrastructure (not covered in detail)
7. Phone number is primary identity (no username-only accounts)
8. Push notification payload is metadata-only (no message content)
9. Disappearing messages enforced client-side (server deletes after TTL)
10. Read receipts are opt-in (bilateral: disabling hides others' receipts too)
