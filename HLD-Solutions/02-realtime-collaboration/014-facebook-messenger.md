# Design Facebook Messenger - Global-Scale Messaging Platform

## 1. Functional Requirements

### Core Features
- **1:1 Messaging**: Text, images, videos, voice messages, stickers, GIFs
- **Group Chats**: Up to 250 members with admin controls
- **End-to-End Encryption**: Optional (default for personal messages)
- **Message States**: Sent, delivered, read receipts with timestamps
- **Multimedia**: Photo/video sharing, file attachments, voice/video calls
- **Reactions**: React to individual messages with emojis
- **Reply/Forward**: Quote-reply and forward messages
- **Typing Indicators**: Real-time typing status
- **Online/Offline Status**: Presence with last-active timestamps
- **Message Unsend**: Delete messages for everyone (within time limit)
- **Disappearing Messages**: Auto-delete after 24h/7d/custom
- **Cross-Platform Sync**: Seamless experience across devices
- **Chatbots/Business**: Messenger Platform for businesses
- **Payments**: P2P money transfer (in supported regions)
- **Stories Integration**: View and reply to stories

### Administrative Features
- Report/block users
- Spam/abuse detection
- Message requests (non-friends)
- Privacy controls (who can message you)
- Data download/deletion (GDPR compliance)

---

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.999% (5 min downtime/year) |
| Message Delivery Latency | < 100ms p50, < 300ms p99 (online) |
| Offline Delivery | < 5s after recipient comes online |
| Consistency | Per-conversation ordering, exactly-once delivery semantics |
| Durability | Zero acknowledged message loss (11 nines durability) |
| Scale | 2B+ users, 100B+ messages/day |
| Concurrent Connections | 500M+ simultaneous |
| E2E Encryption | Signal Protocol (Double Ratchet) |
| Multi-Device | 5+ devices per user, seamless sync |
| Compliance | GDPR, CCPA, regional data residency |
| Voice/Video | < 200ms call setup, < 100ms audio latency |

---

## 3. Capacity Estimation

### User Metrics
| Metric | Value |
|---|---|
| Total Users | 2.5B |
| MAU | 2B |
| DAU | 1.3B |
| Peak Concurrent | 500M |
| Active Conversations/user/day | 5-10 |
| Avg messages/user/day | 40 |

### Traffic
| Metric | Calculation | Value |
|---|---|---|
| Messages/day | 1.3B × 40 | 52B messages/day |
| Messages/sec (avg) | 52B / 86,400 | 600,000 msg/sec |
| Messages/sec (peak 5x) | 600K × 5 | 3,000,000 msg/sec |
| Media messages/day | 52B × 20% | 10.4B media/day |
| Voice/Video calls/day | 300M calls | 3,500 calls/sec |

### Storage
| Data | Daily | Yearly |
|---|---|---|
| Text messages | 52B × 200B avg | 10.4 TB/day, 3.8 PB/year |
| Media (images/video) | 10.4B × 200KB avg | 2 PB/day, 730 PB/year |
| User metadata | Incremental | ~500 TB total |
| Encryption keys | 2.5B users × 10 keys × 1KB | 25 TB |
| Message indexes | ~30% of text | 3 TB/day |

### Network Bandwidth
| Direction | Calculation | Value |
|---|---|---|
| Message ingress | 3M msg/s × 1KB | 3 GB/s |
| Message egress (delivery) | 3M × 1.5 (groups) × 1KB | 4.5 GB/s |
| Media ingress | 120K/s × 200KB | 24 GB/s |
| Media egress | 500K/s × 200KB | 100 GB/s |
| WebSocket keepalive | 500M × 64B / 30s | 1 GB/s |
| Voice RTP | 50M concurrent × 32kbps | 200 Gbps |

---

## 4. Data Modeling

### Database Technology Selection

| Workload | Technology | Rationale |
|---|---|---|
| Messages | Custom storage (similar to MyRocks/RocksDB on MySQL) | Facebook's custom solution - LSM-tree optimized for write-heavy |
| Conversation metadata | TAO (Facebook's graph store) | Social graph optimized |
| User data | TAO / MySQL (sharded) | ACID for profile, settings |
| Presence | Custom in-memory service | Billions of users, ephemeral |
| Media | Haystack / f4 (Facebook's blob store) | Optimized for write-once read-many |
| Encryption keys | Dedicated secure store (HSM-backed) | Security critical |
| Search | Custom inverted index | Message search at scale |
| Analytics | Scuba / Presto / Hive | Real-time + batch analytics |
| Event Bus | Custom (similar to Kafka) | Wormhole - Facebook's internal CDC |

### Schema Design (Generalized for interview)

```sql
-- Users (sharded by user_id)
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    phone VARCHAR(20),
    avatar_url TEXT,
    locale VARCHAR(10),
    e2e_identity_key BYTEA, -- Public key for E2E
    created_at BIGINT, -- Unix timestamp
    last_active_at BIGINT,
    settings JSONB
);

-- Conversations (sharded by conversation_id)
CREATE TABLE conversations (
    conversation_id BIGINT PRIMARY KEY,
    type ENUM('ONE_TO_ONE', 'GROUP', 'BUSINESS'),
    name VARCHAR(100), -- For groups
    creator_id BIGINT,
    photo_url TEXT,
    encryption_enabled BOOLEAN DEFAULT TRUE,
    disappearing_mode ENUM('OFF', '24H', '7D'),
    created_at BIGINT,
    updated_at BIGINT,
    last_message_id BIGINT,
    last_message_at BIGINT
);

-- Conversation Participants
CREATE TABLE conversation_participants (
    conversation_id BIGINT,
    user_id BIGINT,
    role ENUM('ADMIN', 'MEMBER'),
    nickname VARCHAR(50),
    muted_until BIGINT, -- 0 = not muted
    joined_at BIGINT,
    last_read_message_id BIGINT,
    last_read_at BIGINT,
    PRIMARY KEY (conversation_id, user_id)
);
-- Secondary index: (user_id, last_message_at DESC) for inbox list

-- Messages (sharded by conversation_id)
CREATE TABLE messages (
    conversation_id BIGINT,
    message_id BIGINT, -- Snowflake: timestamp + sequence
    sender_id BIGINT,
    type ENUM('TEXT', 'IMAGE', 'VIDEO', 'AUDIO', 'FILE', 'STICKER', 'LOCATION', 'CONTACT', 'SYSTEM'),
    content BLOB, -- Encrypted payload
    reply_to_message_id BIGINT,
    forwarded_from BIGINT,
    reactions JSONB, -- {"emoji": [user_ids]}
    delivery_status JSONB, -- {"user_id": "DELIVERED/READ", ...}
    expires_at BIGINT, -- For disappearing messages
    deleted_at BIGINT,
    created_at BIGINT,
    PRIMARY KEY (conversation_id, message_id)
) ENGINE=RocksDB; -- LSM-tree for write optimization

-- Media Attachments
CREATE TABLE media_attachments (
    media_id BIGINT PRIMARY KEY,
    message_id BIGINT,
    conversation_id BIGINT,
    type ENUM('IMAGE', 'VIDEO', 'AUDIO', 'FILE'),
    mime_type VARCHAR(100),
    size_bytes BIGINT,
    blob_key VARCHAR(255), -- Reference to blob storage
    thumbnail_key VARCHAR(255),
    width INT,
    height INT,
    duration_ms INT, -- For audio/video
    encryption_key BYTEA, -- Per-attachment encryption key
    created_at BIGINT
);

-- E2E Encryption Key Bundles (Signal Protocol)
CREATE TABLE key_bundles (
    user_id BIGINT,
    device_id INT,
    identity_key BYTEA, -- Long-term identity
    signed_prekey BYTEA, -- Signed pre-key (rotates monthly)
    signed_prekey_signature BYTEA,
    one_time_prekeys BYTEA[], -- One-time pre-keys (consumed on first message)
    uploaded_at BIGINT,
    PRIMARY KEY (user_id, device_id)
);

-- Delivery Receipts
CREATE TABLE delivery_receipts (
    conversation_id BIGINT,
    message_id BIGINT,
    user_id BIGINT,
    status ENUM('SENT', 'DELIVERED', 'READ'),
    timestamp BIGINT,
    PRIMARY KEY (conversation_id, message_id, user_id)
);
```

### Indexing Strategy

| Index | Purpose |
|---|---|
| messages(conversation_id, message_id DESC) | Load conversation history |
| conversation_participants(user_id, last_message_at DESC) | User's inbox sorted by recency |
| messages(conversation_id, sender_id, message_id DESC) | Search by sender |
| media_attachments(conversation_id, type, created_at DESC) | Media gallery per conversation |
| delivery_receipts(user_id, status, timestamp DESC) | Pending deliveries |

---

## 5. High-Level Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                 CLIENTS                                               │
│  iOS App │ Android App │ Web (React) │ Messenger Lite │ Business API │ Desktop        │
└─────────────────────────────────────────┬───────────────────────────────────────────┘
                                          │
┌─────────────────────────────────────────▼───────────────────────────────────────────┐
│                              EDGE LAYER                                               │
│  ┌────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐ ┌──────────────────────┐   │
│  │  DNS   │ │ Edge POP │ │   WAF/    │ │ TLS Term +   │ │  Connection          │   │
│  │(Global)│ │ (PoP in  │ │  DDoS     │ │ Certificate  │ │  Router (MQTT/WS)    │   │
│  │        │ │ 80+ loc) │ │  Protect  │ │  Pinning     │ │                      │   │
│  └────────┘ └──────────┘ └───────────┘ └──────────────┘ └──────────────────────┘   │
└─────────────────────────────────────────┬───────────────────────────────────────────┘
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
┌───────────────────────┐  ┌──────────────────────┐  ┌────────────────────────────┐
│  CHAT SERVICE         │  │  PRESENCE SERVICE     │  │  MEDIA SERVICE             │
│  ┌─────────────────┐  │  │  - Online/Offline    │  │  - Upload/Download         │
│  │ Message Router  │  │  │  - Last Active       │  │  - Transcoding             │
│  │ - Route to conv │  │  │  - Active Now        │  │  - Thumbnail generation    │
│  │ - Ordering      │  │  │  - Typing indicator  │  │  - CDN integration         │
│  ├─────────────────┤  │  │  - Custom status     │  │  - Virus scanning          │
│  │ Message Store   │  │  └──────────────────────┘  │  - Encryption              │
│  │ - Persist       │  │                             └────────────────────────────┘
│  │ - Replicate     │  │  ┌──────────────────────┐  
│  ├─────────────────┤  │  │  DELIVERY SERVICE    │  ┌────────────────────────────┐
│  │ Sync Engine     │  │  │  - Push to online    │  │  NOTIFICATION SERVICE      │
│  │ - Multi-device  │  │  │  - Queue for offline │  │  - Push (APNs/FCM)         │
│  │ - Cursor-based  │  │  │  - Delivery receipts │  │  - SMS fallback            │
│  │ - Catch-up      │  │  │  - Read receipts     │  │  - Email digest            │
│  └─────────────────┘  │  │  - Retry logic       │  │  - In-app badge            │
└───────────────────────┘  └──────────────────────┘  └────────────────────────────┘

┌───────────────────────┐  ┌──────────────────────┐  ┌────────────────────────────┐
│  ENCRYPTION SERVICE   │  │  CALL SERVICE        │  │  SEARCH SERVICE            │
│  - Key exchange       │  │  - Signaling (SIP/WS)│  │  - Message search          │
│  - Signal Protocol    │  │  - TURN/STUN servers │  │  - Contact search          │
│  - Key bundle mgmt    │  │  - SFU for group     │  │  - Conversation search     │
│  - Device management  │  │  - Recording (opt)   │  │  - Encrypted index         │
│  - Key transparency   │  │  - Call history      │  │                            │
└───────────────────────┘  └──────────────────────┘  └────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                            │
│  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ │
│  │  Messages   │ │  TAO     │ │  Redis   │ │  Kafka  │ │Haystack/ │ │ Presto │ │
│  │  (MyRocks)  │ │(Graph DB)│ │(Presence)│ │(Events) │ │ f4(Blob) │ │(OLAP)  │ │
│  └─────────────┘ └──────────┘ └──────────┘ └─────────┘ └──────────┘ └────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions
- **MQTT Protocol** (mobile): Lightweight, battery-efficient, persistent connections
- **WebSocket** (web): Full-duplex for desktop/web clients
- **Signal Protocol**: Industry-standard E2E encryption
- **Multi-device sync**: Sender encrypts for each recipient device separately
- **Push model**: Messages pushed immediately to online users
- **Offline queue**: Messages queued and delivered on reconnect

---

## 6. Low-Level Design - APIs

### 6.1 Connection/Auth

```
# MQTT Connect (Mobile - battery optimized)
CONNECT packet:
  - Client ID: user_id:device_id
  - Token: OAuth2 access token
  - Clean Session: false (resume subscriptions)
  - Keep Alive: 60 seconds (mobile), 30 seconds (web)

# WebSocket Connect (Web/Desktop)
GET /ws/chat?token=xxx&device_id=yyy
Upgrade: websocket

# Response: Connection established, sync begins
{
  "type": "connected",
  "session_id": "sess_abc",
  "sync_cursor": "cursor_123",
  "server_time": 1716672000000
}
```

### 6.2 Message APIs

```
POST /api/v1/conversations/{conv_id}/messages
Idempotency-Key: "client-uuid"
Request: {
  "client_msg_id": "local_abc_123",
  "type": "TEXT",
  "encrypted_payload": "base64_encrypted_content",
  "sender_key": "base64_sender_key",
  "reply_to": "msg_456",
  "disappearing_duration": null
}
Response (201): {
  "message_id": "msg_789",
  "conversation_id": "conv_123",
  "timestamp": 1716672000123,
  "status": "SENT"
}

GET /api/v1/conversations/{conv_id}/messages?before=msg_id&limit=30
Response: {
  "messages": [...],
  "has_more": true,
  "cursor": "msg_start_id"
}

DELETE /api/v1/conversations/{conv_id}/messages/{msg_id}
Request: {"for": "EVERYONE"} // or "ME"
Response: {"ok": true, "deleted_at": 1716672100000}

POST /api/v1/conversations/{conv_id}/messages/{msg_id}/reactions
Request: {"emoji": "heart"}
Response: {"ok": true}

POST /api/v1/conversations/{conv_id}/read-receipt
Request: {"last_read_message_id": "msg_789"}
Response: {"ok": true}
```

### 6.3 Conversation APIs

```
POST /api/v1/conversations
Request: {
  "type": "GROUP",
  "participants": ["user_1", "user_2", "user_3"],
  "name": "Weekend Plans",
  "encryption": true
}
Response: {
  "conversation_id": "conv_new_123",
  "type": "GROUP",
  "participants": [...],
  "created_at": 1716672000000
}

GET /api/v1/conversations?cursor=xxx&limit=20
Response: {
  "conversations": [
    {
      "id": "conv_123",
      "type": "ONE_TO_ONE",
      "last_message": {...},
      "unread_count": 3,
      "participants": [...],
      "updated_at": 1716672000000
    }
  ],
  "cursor": "next_cursor"
}

PUT /api/v1/conversations/{conv_id}/mute
Request: {"until": 1716758400000} // or "forever"
Response: {"ok": true}
```

### 6.4 Presence & Typing

```
# Real-time events (pushed via MQTT/WebSocket)
→ Client: {"type": "typing_start", "conversation_id": "conv_123"}
← Server broadcast: {"type": "typing", "conversation_id": "conv_123", "user_id": "u_1", "expires": 5000}

← Server push: {"type": "presence_update", "user_id": "u_2", "status": "ACTIVE", "last_active": 1716672000000}

# REST fallback
GET /api/v1/presence?user_ids=u_1,u_2,u_3
Response: {"users": [{"id": "u_1", "status": "ACTIVE", "last_active": ...}]}
```

### 6.5 Voice/Video Call APIs

```
POST /api/v1/calls/initiate
Request: {
  "conversation_id": "conv_123",
  "type": "VIDEO",
  "participants": ["u_1", "u_2"]
}
Response: {
  "call_id": "call_abc",
  "signaling_url": "wss://calls.messenger.com/signal",
  "turn_servers": [
    {"url": "turn:turn1.messenger.com:443", "credential": "...", "ttl": 86400}
  ],
  "ice_servers": [...]
}

POST /api/v1/calls/{call_id}/answer
Request: {"sdp": "v=0\r\n..."}
Response: {"sdp": "v=0\r\n...", "status": "CONNECTED"}

POST /api/v1/calls/{call_id}/end
Response: {"duration_seconds": 342, "ended_at": 1716672342000}
```

---

## 7. Architecture Components

### 7.1 Connection Layer (MQTT + WebSocket)

```
┌─────────────────────────────────────────────────────────┐
│          CONNECTION INFRASTRUCTURE                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Mobile (MQTT):                                          │
│  - Lightweight binary protocol                           │
│  - QoS 1: at-least-once delivery with dedup             │
│  - Persistent sessions: broker remembers subscriptions   │
│  - Small packet overhead (2 bytes min)                   │
│  - Background push via OS push (APNs/FCM) when killed   │
│                                                           │
│  Web/Desktop (WebSocket):                                │
│  - Full-duplex JSON or Protobuf frames                   │
│  - Auto-reconnect with exponential backoff               │
│  - Delta sync on reconnect                               │
│                                                           │
│  Connection Routers (per region):                        │
│  - 1000+ connection servers per region                   │
│  - Each handles ~500K connections                        │
│  - Stateless (session state in Redis)                    │
│  - NLB with source-IP affinity                           │
│  - Graceful drain on deploy (GOAWAY + 60s wait)          │
│                                                           │
│  Resource per connection:                                 │
│  - MQTT: ~1KB memory per idle connection                 │
│  - WebSocket: ~4KB with zlib context                     │
│  - 500M connections × 2KB avg = 1 TB total               │
│  - Distributed across thousands of nodes                 │
└─────────────────────────────────────────────────────────┘
```

### 7.2 End-to-End Encryption (Signal Protocol)

```
┌─────────────────────────────────────────────────────────┐
│          E2E ENCRYPTION ARCHITECTURE                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Key Exchange (X3DH - Extended Triple Diffie-Hellman):   │
│  1. Alice fetches Bob's key bundle from server           │
│  2. Key bundle: Identity Key + Signed Pre-Key            │
│     + One-Time Pre-Key                                   │
│  3. Alice computes shared secret using ECDH              │
│  4. Derives initial chain key for Double Ratchet         │
│                                                           │
│  Double Ratchet Algorithm:                               │
│  - Symmetric-key ratchet: chain key → message keys       │
│  - DH ratchet: new ephemeral keys per message turn       │
│  - Forward secrecy: past messages can't be decrypted     │
│  - Future secrecy: key compromises heal                  │
│                                                           │
│  Multi-Device:                                            │
│  - Each device has its own identity key pair             │
│  - Sender encrypts message N times (once per recipient   │
│    device)                                                │
│  - Server stores N encrypted copies                      │
│  - Sender Key optimization for groups:                   │
│    · One encryption for all group members                │
│    · Distribute sender key to each member's devices      │
│                                                           │
│  Key Transparency:                                        │
│  - Append-only log of identity key changes               │
│  - Users can verify each other's keys                    │
│  - Detects MITM attacks from compromised servers         │
│                                                           │
│  Server's Role:                                           │
│  - Store/relay encrypted blobs (cannot read content)     │
│  - Store public key bundles                              │
│  - Route messages to correct devices                     │
│  - CANNOT: decrypt messages, forge keys                  │
└─────────────────────────────────────────────────────────┘
```

### 7.3 Delivery Guarantee System

```
Message Delivery States:
  PENDING → SENT → DELIVERED → READ

Flow:
1. Client sends message → Server ACKs → status: SENT (single checkmark)
2. Server pushes to recipient → Recipient device ACKs → status: DELIVERED (double checkmark)
3. Recipient opens conversation → Read receipt sent → status: READ (blue checkmark)

Offline Delivery:
- Message stored in per-user delivery queue
- When user connects: sync from last cursor
- Push notification triggers app wake → connect → sync
- Messages ordered by server timestamp within conversation

Exactly-Once Delivery:
- Client generates idempotency ID (UUID)
- Server deduplicates based on (sender_id, conversation_id, idempotency_id)
- Dedup window: 7 days (covers retries after crashes)
- Client retries with same ID on network failure

Multi-Device Sync:
- Each device maintains its own sync cursor
- On connect: pull all messages after cursor
- Cursor = last_message_id successfully processed
- Server keeps message history for sync (30+ days)
```

---

## 8. Deep Dive - Core Services

### 8.1 Message Ordering

```
Problem: In distributed system, messages from different senders may arrive out of order

Solution: Per-Conversation Ordering
- Each conversation has a monotonic sequence counter
- Server assigns sequence number on receipt (not client timestamp)
- Within conversation: strict ordering by sequence number
- Across conversations: no ordering guarantee needed

Implementation:
- Sequence counter per conversation in Redis (INCR atomic)
- If Redis unavailable: fallback to server timestamp (Snowflake)
- Client displays messages sorted by server-assigned sequence
- Late arrivals: insert at correct position, UI updates

Group Message Ordering:
- All messages in a group go through single logical sequencer
- Sequencer partitioned by conversation_id
- Consistent hashing ensures same conversation always hits same sequencer
- High availability: sequencer state replicated, failover in <1s
```

### 8.2 Offline Message Queue

```
Architecture:
┌──────────────────────────────────────────────────┐
│         OFFLINE DELIVERY SYSTEM                    │
├──────────────────────────────────────────────────┤
│                                                    │
│  When recipient offline:                          │
│  1. Message written to conversation store         │
│  2. Notification queued (push + badge update)     │
│  3. Per-user "pending sync" pointer updated       │
│                                                    │
│  When recipient comes online:                     │
│  1. Connection established                        │
│  2. Client sends last sync cursor                 │
│  3. Server streams all messages after cursor      │
│  4. Delivery receipts sent back for each          │
│  5. Cursor updated to latest                      │
│                                                    │
│  Storage:                                          │
│  - Messages stored in conversation table          │
│  - No separate offline queue needed               │
│  - Sync = read conversation from cursor to HEAD   │
│  - Efficient: messages already ordered in store   │
│                                                    │
│  Push Notification:                                │
│  - iOS: APNs with content-available (background)  │
│  - Android: FCM high-priority + data message      │
│  - Web: Web Push API                              │
│  - Collapse key: per-conversation (replace old)   │
│  - Budget: respect OS push limits                 │
└──────────────────────────────────────────────────┘
```

### 8.3 Group Chat Optimization

```
Challenges at Scale (250-member groups):
1. Fanout: each message → 249 deliveries
2. Read receipts: 250 receipts per message
3. Typing: could spam 249 users constantly
4. Media: large attachments × 250 copies

Solutions:
- Typing indicators: throttle to 1 per 5s per user per conversation
- Read receipts: batch (send every 5s, not per message)
- Media: single copy in blob store, shared key for decryption
- Sender Key (Signal): single encryption for group (vs N encryptions)
- Fanout: parallel delivery to all online members' connection servers
- Large groups: only deliver to users who have conversation open + push to rest

Read Receipts Optimization:
- Don't send individual receipts for each message
- Send: "user_X read up to message_id_Y" (single receipt covers all previous)
- Store: only latest read position per user per conversation
- Display: show "seen by 5" aggregate, not individual per-message
```

---

## 9. Component Optimization

### 9.1 Kafka / Event Bus

```
Topics:
  messenger.messages.created       - key: conversation_id, 2048 partitions
  messenger.messages.deleted       - key: conversation_id, 512 partitions
  messenger.delivery.receipts      - key: recipient_user_id, 1024 partitions
  messenger.presence.updates       - key: user_id, 512 partitions
  messenger.notifications.pending  - key: user_id, 1024 partitions
  messenger.calls.events           - key: call_id, 256 partitions
  messenger.encryption.key_changes - key: user_id, 128 partitions
  messenger.analytics.events       - key: user_id, 4096 partitions

Config:
  - Replication factor: 3 (cross-AZ)
  - Min ISR: 2
  - Message retention: 7 days (hot), then tier to S3
  - Max message size: 1MB (for media metadata)
  - Compression: lz4 (best throughput/compression trade-off)
```

### 9.2 Caching

```
Multi-Layer Cache:
┌─────────────────────────────────────────────────────────┐
│ L1: On-device cache (SQLite)                             │
│   - All recent conversations and messages                │
│   - Decrypted content (encrypted at rest on device)      │
│   - Offline-first: UI reads from local, syncs in bg      │
├─────────────────────────────────────────────────────────┤
│ L2: CDN Edge Cache                                       │
│   - Profile photos, stickers, GIF packs                  │
│   - Static media (after first upload)                    │
│   - TTL: 24h for avatars, 1yr for stickers              │
├─────────────────────────────────────────────────────────┤
│ L3: Regional Cache (Memcached/Redis)                     │
│   - Conversation metadata: last_message, unread_count    │
│   - User presence status                                 │
│   - Active conversation sessions                         │
│   - Permission/block lists                               │
│   - Encryption key bundles                               │
│   - TTL: 5-60 minutes depending on data type            │
├─────────────────────────────────────────────────────────┤
│ L4: Database (source of truth)                           │
│   - All messages, conversations, relationships           │
│   - Encryption keys and device registrations             │
│   - Used on cache miss only                              │
└─────────────────────────────────────────────────────────┘

Cache Invalidation:
- Write-through for conversation metadata
- Event-driven invalidation via Kafka consumers
- TTL-based for presence (auto-expire)
- On-device: server push invalidation events via MQTT
```

### 9.3 Database Sharding

```
Sharding Strategy:
┌─────────────────────────────────────────────────────────┐
│ Messages: Sharded by conversation_id                     │
│ - Hash(conversation_id) % num_shards                    │
│ - All messages in a conversation on same shard          │
│ - Enables efficient conversation history queries        │
│ - 16,384 logical shards → mapped to physical nodes     │
│                                                          │
│ Users: Sharded by user_id                                │
│ - User profile, settings, devices on same shard         │
│ - Conversation list: stored on user's shard             │
│   (denormalized for fast inbox loading)                 │
│                                                          │
│ Cross-shard Operations:                                  │
│ - Sending message: write to conversation shard          │
│ - Updating inbox: async update to each participant's    │
│   user shard (eventual consistency OK for inbox order)  │
│                                                          │
│ Replication:                                             │
│ - 3 replicas per shard (cross-AZ)                       │
│ - Sync replication for writes (2/3 quorum)             │
│ - Read from any replica for non-critical reads          │
│ - Cross-region async replication for DR                 │
│                                                          │
│ Hot Shard Mitigation:                                    │
│ - Celebrity/viral conversations: detected by QPS         │
│ - Auto-split: move to dedicated shard pool               │
│ - Read replicas: additional replicas for read-heavy     │
└─────────────────────────────────────────────────────────┘
```

### 9.4 Media Pipeline

```
Upload Flow:
1. Client requests upload URL (pre-signed)
2. Client uploads directly to blob store (Haystack/S3)
3. Upload service validates (size, type, virus scan)
4. Generate thumbnails/previews
5. For E2E: media encrypted client-side before upload
6. Return media_id + CDN URL to client
7. Client sends message with media_id reference

Optimization:
- Progressive JPEG: load blurry → sharp
- Adaptive quality: based on network speed
- Video: HLS/DASH transcoding to multiple bitrates
- Audio messages: Opus codec, 16kbps mono
- Deduplication: content-hash based dedup for non-E2E
- CDN: serve from nearest edge POP
- Lazy loading: thumbnails inline, full media on tap
```

### 9.5 Push Notification Optimization

```
Challenges:
- 1.3B DAU × 40 msgs/day = 52B potential notifications/day
- Most should NOT send push (user is online, conversation open)

Optimization Strategy:
1. Suppress if user is online AND has conversation open
2. Suppress if user sent message in last 30s (they're active)
3. Collapse: one push per conversation (not per message)
4. Batch: wait 2s before sending push (catch rapid messages)
5. Quiet hours: respect user's sleep schedule
6. Mention priority: @mention notifications always go through
7. Muted conversations: no push, just badge count update

iOS-specific:
- Use APNs priority 5 (power-efficient) for non-urgent
- Use APNs priority 10 (immediate) for calls/mentions
- Notification grouping by conversation (threadId)
- Content-available for background sync (silent push)

Android-specific:
- FCM data messages (app handles display)
- Notification channels: calls > messages > groups
- Direct reply from notification shade
```

---

## 10. Observability

### 10.1 Key Metrics

```yaml
# Delivery Metrics (most critical)
messenger_message_e2e_latency_seconds{type="text|media", p50|p95|p99}
messenger_message_delivery_success_rate
messenger_message_delivery_failure_total{reason="offline|error|blocked"}
messenger_offline_delivery_latency_seconds{quantile}
messenger_message_loss_rate  # Should be 0

# Connection Metrics
messenger_connections_active{protocol="mqtt|websocket", region}
messenger_connection_duration_seconds{protocol, quantile}
messenger_reconnection_rate{reason="network|server_restart|error"}
messenger_connection_errors_total{type}

# Encryption Metrics
messenger_key_bundle_fetch_total{result="success|empty|error"}
messenger_encryption_failures_total{stage="encrypt|decrypt|key_exchange"}
messenger_prekey_pool_remaining{user_id_bucket}

# Call Metrics
messenger_call_setup_latency_seconds{type="voice|video", quantile}
messenger_call_quality_mos{region}
messenger_call_drop_rate{reason}

# Infrastructure
messenger_db_write_latency{shard, quantile}
messenger_cache_hit_rate{layer="l2|l3"}
messenger_kafka_consumer_lag{topic, group}
messenger_push_delivery_rate{platform="ios|android|web"}
```

### 10.2 Alerting

```yaml
Critical (Page immediately):
- Message loss detected (delivery_success_rate < 99.99%)
- E2E latency p99 > 5s for more than 2 minutes
- Connection count drop > 10% in 1 minute (regional outage)
- Encryption key exchange failures > 1% (potential attack)
- Database shard unreachable for > 30s

High (Page within 5 min):
- Push notification delivery rate < 95%
- Kafka consumer lag > 5M messages
- Voice call setup failure rate > 5%
- Cache hit rate < 80%

Warning (Ticket):
- Storage growth exceeding capacity plan
- Slow queries > 1% of total
- Certificate expiry within 7 days
- API error rate > 0.5% any endpoint
```

### 10.3 Distributed Tracing

```
Trace: message_send_e2e
[Client] encrypt message (local, 2ms)
  → [Connection Server] receive frame (0.5ms)
  → [Message Router] route to conversation shard (1ms)
  → [Message Service] validate + store (5ms)
    → [Dedup Check] Redis lookup (0.5ms)
    → [Sequence Assign] Redis INCR (0.3ms)
    → [DB Write] MyRocks persist (3ms)
    → [Kafka Publish] event (1ms)
  → [Delivery Service] fan out (3ms async)
    → [Presence Check] is recipient online? (0.5ms)
    → [Push to Connection] recipient's server (1ms)
  → [Recipient Client] receive + decrypt (local, 2ms)

Total: ~15ms sender to recipient (both online, same region)
```

---

## 11. Considerations & Assumptions

### Key Assumptions
1. 60% of messages are 1:1, 35% small groups (<10), 5% large groups
2. 70% of messages delivered while recipient is online
3. Average 3.2 devices per user (phone, laptop, tablet)
4. Media in 20% of messages; 80% are text-only
5. E2E encryption enabled by default for all personal conversations
6. Multi-region deployment: US, EU, APAC, LATAM (data residency)

### Key Trade-offs

| Decision | Chosen | Alternative | Rationale |
|---|---|---|---|
| MQTT for mobile | Battery efficient, lightweight | WebSocket | Mobile devices need minimal overhead |
| Signal Protocol E2E | Industry standard, proven | Custom encryption | Trust, auditability, open-source |
| MyRocks (LSM) for messages | Write-optimized, compression | B-tree (InnoDB) | Append-heavy workload, space efficiency |
| Server-assigned ordering | Simpler, consistent | Vector clocks | Good enough for chat, simpler to reason about |
| Per-conversation sharding | Co-located history | Per-user sharding | Most queries are within a conversation |
| Push over pull | Low latency delivery | Polling | Real-time experience essential |

### Data Residency & Compliance
- EU users' data stored in EU data centers (GDPR)
- Messages encrypted at rest + in transit
- Data deletion: complete erasure within 90 days of request
- Law enforcement: cannot comply for E2E content (by design)
- Metadata: retained for safety/abuse (IP, timestamps, who messaged whom)
- Audit trail: all access to user data logged and reviewable

### Failure Modes & Recovery

| Failure | Impact | Recovery |
|---|---|---|
| Connection server crash | ~500K users disconnected | Auto-reconnect in <5s, sync from cursor |
| Message DB shard down | Conversations on that shard unavailable | Promote replica in <30s, no data loss |
| Redis cluster failure | Presence stale, higher DB load | Fallback to DB, degraded presence |
| Kafka partition leader loss | Event processing delayed | New leader elected in <10s, consumers resume |
| Regional outage | Users in region can't connect | DNS failover to nearest region in <60s |
| Push provider outage (APNs) | iOS push delayed | Queue and retry, SMS fallback for critical |
| Key server failure | New E2E sessions can't start | Cached keys work for existing sessions |

### Security Measures
- Certificate pinning on mobile apps
- Token rotation every 24 hours
- Device verification for suspicious logins
- Rate limiting: 200 messages/minute per user
- Spam detection ML models on metadata (not content for E2E)
- Child safety: hash-matching on non-E2E media (PhotoDNA)
- Account takeover protection: challenge on new device
