# Design Discord - Real-Time Voice, Video & Text Communication Platform

## 1. Functional Requirements

### Core Features
- **Servers (Guilds)**: Create/join servers with categories, channels, roles
- **Text Channels**: Real-time messaging with rich content, embeds, reactions, threads
- **Voice Channels**: Low-latency voice chat with multiple participants (up to 99)
- **Video/Screen Share**: Live video streaming and screen sharing in voice channels
- **Direct Messages**: 1:1 and group DMs (up to 10 people)
- **Roles & Permissions**: Granular permission system (channel-level, role-based)
- **Bots & Integrations**: Bot API, webhooks, slash commands, rich presence
- **Stage Channels**: Speaker/audience model for large events
- **Server Discovery**: Browse and search public servers
- **Nitro/Subscriptions**: Premium features (larger uploads, custom emojis, HD streaming)
- **Friend System**: Add friends, block users, friend activity
- **Rich Presence**: Game activity status, Spotify integration
- **Message Pinning, Reactions, Threads, Embeds**
- **Server Boost**: Community perks through member contributions

### Admin/Moderation Features
- AutoMod (regex-based content filtering)
- Audit logs for all admin actions
- Server insights/analytics
- Verification levels, 2FA requirements
- Timeouts, kicks, bans (with ban appeals)

---

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% for text, 99.95% for voice/video |
| Text Message Latency | < 50ms p50, < 150ms p99 (online delivery) |
| Voice Latency | < 50ms end-to-end (same region), < 150ms cross-region |
| Voice Quality | Opus codec, adaptive bitrate 6-128 kbps |
| Video Latency | < 200ms for screen share, < 500ms for camera |
| Concurrent Voice Users | 10M+ simultaneous voice connections |
| Concurrent Text Users | 150M+ concurrent WebSocket connections |
| Server Size | Support 1M+ member servers |
| Message History | Infinite retention (free tier) |
| File Upload | 8MB free, 50MB Nitro, 100MB Nitro Boost |
| Scalability | 200M+ MAU, 20M+ concurrent users |

---

## 3. Capacity Estimation

### User Metrics
| Metric | Value |
|---|---|
| Registered Users | 600M |
| MAU | 200M |
| DAU | 60M |
| Concurrent Users (peak) | 20M |
| Concurrent Voice Users | 5M |
| Active Servers | 20M |
| Messages/day | 4B |

### QPS & Throughput
| Operation | Average QPS | Peak QPS |
|---|---|---|
| Message send | 46,000 | 230,000 |
| Message read (channel load) | 200,000 | 1,000,000 |
| Voice packet relay | 50M packets/sec | 150M packets/sec |
| Presence updates | 100,000 | 500,000 |
| Typing indicators | 50,000 | 250,000 |
| API calls (total) | 500,000 | 2,500,000 |

### Storage Estimation
| Data Type | Daily Volume | Yearly |
|---|---|---|
| Text messages | 4B × 1KB = 4 TB/day | 1.46 PB/year |
| Voice (not stored) | Real-time relay only | 0 |
| File uploads | 100M × 2MB avg = 200 TB/day | 73 PB/year |
| User/Server metadata | Incremental ~5 GB/day | 1.8 TB/year |
| Audit logs | 500M events × 500B = 250 GB/day | 91 TB/year |

### Network Bandwidth
| Traffic Type | Calculation | Bandwidth |
|---|---|---|
| Message egress (fanout) | 230K msgs/s × 50 avg recipients × 1KB | 11.5 GB/s peak |
| Voice relay | 5M users × 64kbps (Opus) | 40 Gbps |
| Video relay | 500K streams × 2Mbps avg | 1 Tbps |
| File downloads | 50K/s × 2MB | 100 GB/s |
| WebSocket keepalive | 20M × 64B / 30s | 43 MB/s |

---

## 4. Data Modeling

### Database Technology Selection

| Workload | Technology | Rationale |
|---|---|---|
| Messages | Cassandra / ScyllaDB | Append-heavy, partitioned by channel, massive scale |
| User/Server metadata | PostgreSQL (sharded via Vitess) | Relational integrity, ACID for roles/permissions |
| Presence/Sessions | Redis Cluster | Ephemeral, sub-ms reads, TTL |
| Voice routing | Redis + custom routing service | Real-time, low-latency state |
| Search | Elasticsearch | Full-text search, relevance ranking |
| Analytics | ClickHouse | Real-time OLAP, server insights |
| File Storage | Google Cloud Storage / S3 | Durable, CDN-integrated |
| Event Stream | Apache Kafka | Durable log, replay, ordered events |
| Relationships (friends, blocks) | PostgreSQL + Redis cache | Graph queries with caching |
| Rate Limits | Redis (sliding window) | Atomic counters, TTL |

### Schema Design

#### PostgreSQL - Users, Servers, Roles

```sql
-- Users
CREATE TABLE users (
    id BIGINT PRIMARY KEY, -- Snowflake ID
    username VARCHAR(32) NOT NULL,
    discriminator CHAR(4) NOT NULL, -- Legacy, moving to unique usernames
    email VARCHAR(255) UNIQUE,
    avatar_hash VARCHAR(64),
    banner_hash VARCHAR(64),
    bio TEXT,
    premium_type SMALLINT DEFAULT 0, -- 0=none, 1=nitro_classic, 2=nitro, 3=nitro_basic
    flags BIGINT DEFAULT 0, -- Bitfield for badges, features
    locale VARCHAR(10),
    mfa_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(username, discriminator)
);
CREATE INDEX idx_users_username ON users(username);

-- Servers (Guilds)
CREATE TABLE guilds (
    id BIGINT PRIMARY KEY, -- Snowflake ID
    name VARCHAR(100) NOT NULL,
    owner_id BIGINT NOT NULL REFERENCES users(id),
    icon_hash VARCHAR(64),
    splash_hash VARCHAR(64),
    banner_hash VARCHAR(64),
    description TEXT,
    region VARCHAR(20), -- deprecated, auto-selected
    verification_level SMALLINT DEFAULT 0,
    default_message_notifications SMALLINT DEFAULT 0,
    explicit_content_filter SMALLINT DEFAULT 0,
    features TEXT[], -- COMMUNITY, DISCOVERABLE, etc.
    premium_tier SMALLINT DEFAULT 0, -- Server boost level
    premium_subscription_count INT DEFAULT 0,
    member_count INT DEFAULT 0,
    max_members INT DEFAULT 500000,
    vanity_url_code VARCHAR(32),
    nsfw_level SMALLINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_guilds_owner ON guilds(owner_id);

-- Channels
CREATE TABLE channels (
    id BIGINT PRIMARY KEY, -- Snowflake ID
    guild_id BIGINT REFERENCES guilds(id),
    parent_id BIGINT REFERENCES channels(id), -- Category parent
    type SMALLINT NOT NULL, -- 0=text, 2=voice, 4=category, 5=announcement, 13=stage, 15=forum
    name VARCHAR(100),
    topic VARCHAR(1024),
    position SMALLINT,
    bitrate INT, -- For voice channels
    user_limit SMALLINT, -- For voice channels
    rate_limit_per_user SMALLINT, -- Slowmode seconds
    nsfw BOOLEAN DEFAULT FALSE,
    last_message_id BIGINT,
    permission_overwrites JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_channels_guild ON channels(guild_id, type);
CREATE INDEX idx_channels_parent ON channels(parent_id);

-- Roles
CREATE TABLE roles (
    id BIGINT PRIMARY KEY, -- Snowflake ID
    guild_id BIGINT NOT NULL REFERENCES guilds(id),
    name VARCHAR(100) NOT NULL,
    color INT DEFAULT 0,
    hoist BOOLEAN DEFAULT FALSE, -- Display separately in member list
    position SMALLINT NOT NULL,
    permissions BIGINT NOT NULL, -- Bitfield
    managed BOOLEAN DEFAULT FALSE, -- Bot role
    mentionable BOOLEAN DEFAULT FALSE,
    icon_hash VARCHAR(64)
);
CREATE INDEX idx_roles_guild ON roles(guild_id);

-- Guild Members
CREATE TABLE guild_members (
    guild_id BIGINT REFERENCES guilds(id),
    user_id BIGINT REFERENCES users(id),
    nick VARCHAR(32),
    roles BIGINT[], -- Array of role IDs
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    premium_since TIMESTAMPTZ, -- Boosting since
    deaf BOOLEAN DEFAULT FALSE,
    mute BOOLEAN DEFAULT FALSE,
    pending BOOLEAN DEFAULT FALSE, -- Membership screening
    communication_disabled_until TIMESTAMPTZ, -- Timeout
    PRIMARY KEY (guild_id, user_id)
);
CREATE INDEX idx_gm_user ON guild_members(user_id);

-- Relationships (Friends/Blocks)
CREATE TABLE relationships (
    user_id BIGINT REFERENCES users(id),
    target_id BIGINT REFERENCES users(id),
    type SMALLINT NOT NULL, -- 1=friend, 2=blocked, 3=incoming_request, 4=outgoing_request
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, target_id)
);
CREATE INDEX idx_rel_target ON relationships(target_id, type);
```

#### Cassandra/ScyllaDB - Messages

```sql
-- Messages (partitioned by channel, clustered by message_id DESC)
CREATE TABLE messages (
    channel_id BIGINT,
    message_id BIGINT, -- Snowflake ID (encodes timestamp)
    author_id BIGINT,
    content TEXT,
    type SMALLINT, -- 0=default, 1=recipient_add, 7=thread_starter, 19=reply, etc.
    embeds TEXT, -- JSON array of embed objects
    attachments TEXT, -- JSON array of attachment objects
    reactions TEXT, -- JSON map emoji -> [user_ids]
    mention_everyone BOOLEAN,
    mentions SET<BIGINT>, -- Mentioned user IDs
    mention_roles SET<BIGINT>, -- Mentioned role IDs
    pinned BOOLEAN,
    referenced_message_id BIGINT, -- For replies
    thread_id BIGINT, -- If this started a thread
    flags INT DEFAULT 0, -- Bitfield
    edited_timestamp TIMESTAMP,
    components TEXT, -- JSON for buttons/selects
    sticker_ids SET<BIGINT>,
    PRIMARY KEY ((channel_id), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC)
  AND compaction = {'class': 'TimeWindowCompactionStrategy', 'compaction_window_unit': 'DAYS', 'compaction_window_size': 1};
```

#### Redis - Presence, Voice State, Rate Limits

```
# Presence
presence:{user_id} → HASH {status, game_name, game_type, since, client_status_desktop, client_status_mobile, client_status_web}
TTL: 120s (refreshed by heartbeat)

# Voice State
voice_state:{guild_id}:{user_id} → HASH {channel_id, session_id, deaf, mute, self_deaf, self_mute, self_stream, self_video, suppress}
voice_channel:{channel_id} → SET of user_ids

# Guild member count cache
guild_online:{guild_id} → INT (approximation, updated every 30s)

# Rate limiting
ratelimit:{route}:{user_id} → {count, reset_at} (sliding window)

# Session routing (user → gateway nodes)
sessions:{user_id} → SET {shard_id:session_id}

# Typing indicator
typing:{channel_id} → ZSET {user_id: timestamp}
```

### Indexing Strategy

| Table/Store | Index | Access Pattern |
|---|---|---|
| messages | (channel_id, message_id DESC) | Load channel history (most recent first) |
| messages | (channel_id, author_id, message_id DESC) | Messages by user in channel |
| guild_members | (guild_id, user_id) | Check membership |
| guild_members | (user_id) | List user's servers |
| channels | (guild_id, type) | List channels in server |
| roles | (guild_id, position) | Role hierarchy |
| relationships | (user_id, type) | Friend list, block list |

---

## 5. High-Level Design

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                               │
│   Desktop (Electron)  │  iOS  │  Android  │  Web (React)  │  Bot Clients          │
└───────────────┬──────────────────────────────────────────────────────┬────────────┘
                │                                                       │
                ▼                                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          EDGE LAYER                                                │
│  ┌──────────┐  ┌───────────┐  ┌────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ Cloudflare│  │    WAF    │  │Global Load │  │  DDoS       │  │   CDN      │  │
│  │   DNS     │  │(Rules/Bot)│  │ Balancer   │  │  Protection │  │(Files/Img) │  │
│  └──────────┘  └───────────┘  └────────────┘  └─────────────┘  └────────────┘  │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│  GATEWAY SERVICE    │  │  REST API       │  │  VOICE GATEWAY          │
│  (WebSocket)        │  │  SERVICE        │  │  (UDP/WebRTC)           │
│  - Auth/Resume      │  │  - CRUD ops     │  │  - Signaling            │
│  - Event dispatch   │  │  - File upload  │  │  - RTP relay            │
│  - Heartbeat        │  │  - OAuth/Bot    │  │  - Selective Forwarding │
│  - Sharding         │  │                 │  │  - Opus encoding        │
│  (Shard per ~2500   │  │                 │  │                         │
│   guilds)           │  │                 │  │                         │
└────────┬────────────┘  └────────┬────────┘  └────────────┬────────────┘
         │                         │                        │
         ▼                         ▼                        ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         CORE SERVICES LAYER                                       │
│                                                                                    │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  Guild       │  │  Message      │  │  Voice         │  │  Relationship    │  │
│  │  Service     │  │  Service      │  │  Server        │  │  Service         │  │
│  │ -Members     │  │ -Send/Edit    │  │ -SFU routing   │  │ -Friends         │  │
│  │ -Roles       │  │ -History      │  │ -Codec control │  │ -Blocks          │  │
│  │ -Permissions │  │ -Pins/Threads │  │ -Quality adapt │  │ -DMs             │  │
│  └──────────────┘  └───────────────┘  └────────────────┘  └──────────────────┘  │
│                                                                                    │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  Presence    │  │  Notification │  │  Search        │  │  Moderation      │  │
│  │  Service     │  │  Service      │  │  Service       │  │  Service         │  │
│  │ -Status      │  │ -Push/Badge   │  │ -Messages      │  │ -AutoMod         │  │
│  │ -Activity    │  │ -@mentions    │  │ -Servers       │  │ -Spam filter     │  │
│  │ -Rich Presence│ │ -DM alerts    │  │ -Users         │  │ -Raid detection  │  │
│  └──────────────┘  └───────────────┘  └────────────────┘  └──────────────────┘  │
│                                                                                    │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐                         │
│  │  File/Media  │  │  Bot/App      │  │  Analytics     │                         │
│  │  Service     │  │  Service      │  │  Service       │                         │
│  │ -Upload      │  │ -Interactions │  │ -Server stats  │                         │
│  │ -Process     │  │ -Webhooks     │  │ -Growth metrics│                         │
│  │ -CDN prep    │  │ -Slash cmds   │  │ -Engagement    │                         │
│  └──────────────┘  └───────────────┘  └────────────────┘                         │
└──────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                                 │
│                                                                                    │
│  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ ScyllaDB   │  │ PostgreSQL │  │  Redis   │  │   Kafka    │  │   GCS/S3    │  │
│  │ (Messages) │  │ (Metadata) │  │ Cluster  │  │(Event Bus) │  │  (Files)    │  │
│  └────────────┘  └────────────┘  └──────────┘  └────────────┘  └─────────────┘  │
│                                                                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────────────────────────┐  │
│  │Elasticsearch│ │ ClickHouse │  │  Lavalink / Custom Voice Routing Fabric    │  │
│  │  (Search)  │  │(Analytics) │  │  (Voice media plane)                       │  │
│  └────────────┘  └────────────┘  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Microservice Patterns

| Pattern | Usage in Discord |
|---|---|
| **Gateway Pattern** | WebSocket Gateway shards distribute events to clients |
| **CQRS** | Message writes to ScyllaDB, reads served from cache/replica |
| **Event Sourcing** | Guild events persisted to Kafka for audit/replay |
| **SFU (Selective Forwarding Unit)** | Voice server forwards selected streams |
| **Pub/Sub** | Internal message fanout between gateway shards |
| **Circuit Breaker** | Isolate voice failures from text service |
| **Bulkhead** | Per-guild rate limits prevent noisy neighbor |
| **Sidecar** | Envoy for mTLS, observability, retries |
| **Sharding** | Gateway shards by guild_id, DB shards by channel_id |

---

## 6. Low-Level Design - APIs

### 6.1 Gateway (WebSocket) Protocol

```json
// Client → Server: Identify (after connect)
{
  "op": 2,
  "d": {
    "token": "user_token_here",
    "intents": 32767,
    "properties": {"os": "windows", "browser": "chrome", "device": ""},
    "compress": true,
    "large_threshold": 250,
    "shard": [0, 1]
  }
}

// Server → Client: Ready
{
  "op": 0,
  "s": 1,
  "t": "READY",
  "d": {
    "v": 10,
    "user": {...},
    "guilds": [{...}],
    "session_id": "session_abc",
    "resume_gateway_url": "wss://gateway-resume.discord.gg",
    "relationships": [...],
    "private_channels": [...]
  }
}

// Server → Client: Message Create
{
  "op": 0,
  "s": 42,
  "t": "MESSAGE_CREATE",
  "d": {
    "id": "123456789",
    "channel_id": "987654321",
    "author": {"id": "111", "username": "user", ...},
    "content": "Hello!",
    "timestamp": "2024-05-25T10:00:00Z",
    "embeds": [],
    "attachments": []
  }
}

// Heartbeat
Client → {"op": 1, "d": 42}  // sequence number
Server → {"op": 11, "d": null}  // ACK

// Resume (after disconnect)
Client → {"op": 6, "d": {"token": "...", "session_id": "...", "seq": 42}}
Server → replays missed events, then {"op": 0, "t": "RESUMED", "d": {}}
```

### 6.2 REST API - Messages

```
POST /api/v10/channels/{channel_id}/messages
Headers: Authorization: Bot/Bearer token
Request: {
  "content": "Hello @everyone!",
  "embeds": [{"title": "Link", "url": "https://...", "color": 5814783}],
  "message_reference": {"message_id": "12345"}, // Reply
  "components": [{"type": 1, "components": [{"type": 2, "label": "Click", "style": 1, "custom_id": "btn_1"}]}],
  "attachments": [{"id": 0, "filename": "image.png", "description": "A cool image"}],
  "flags": 0
}
Response (201): {
  "id": "9876543210",
  "type": 0,
  "channel_id": "...",
  "author": {...},
  "content": "Hello @everyone!",
  "timestamp": "2024-05-25T10:00:00.000000+00:00",
  "edited_timestamp": null,
  "embeds": [...],
  "attachments": [...],
  "reactions": [],
  "pinned": false
}

GET /api/v10/channels/{channel_id}/messages?limit=50&before=message_id
Response (200): [array of message objects]

PATCH /api/v10/channels/{channel_id}/messages/{message_id}
Request: {"content": "Edited message"}
Response (200): {updated message object}

DELETE /api/v10/channels/{channel_id}/messages/{message_id}
Response: 204 No Content

PUT /api/v10/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me
Response: 204 No Content

DELETE /api/v10/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me
Response: 204 No Content
```

### 6.3 REST API - Voice

```
// Join voice channel (via Gateway event)
Client → Gateway: {"op": 4, "d": {"guild_id": "...", "channel_id": "...", "self_mute": false, "self_deaf": false}}

// Server responds with voice server info
Server → Client: {"t": "VOICE_SERVER_UPDATE", "d": {"token": "voice_token", "guild_id": "...", "endpoint": "us-west-1.voice.discord.gg"}}

// Client connects to voice WebSocket
Client → Voice WS: {"op": 0, "d": {"server_id": "...", "user_id": "...", "session_id": "...", "token": "voice_token"}}

// Voice WS responds with UDP info
Voice WS → Client: {"op": 2, "d": {"ssrc": 12345, "ip": "1.2.3.4", "port": 50000, "modes": ["xsalsa20_poly1305"]}}

// Client sends voice data via UDP (encrypted with libsodium)
// RTP header + encrypted Opus audio frame
```

### 6.4 REST API - Guilds

```
POST /api/v10/guilds
Request: {"name": "My Server", "icon": "data:image/png;base64,...", "channels": [...], "roles": [...]}
Response (201): {guild object}

GET /api/v10/guilds/{guild_id}
Response (200): {full guild object with channels, roles, emojis}

PATCH /api/v10/guilds/{guild_id}
Request: {"name": "New Name", "verification_level": 2}
Response (200): {updated guild}

GET /api/v10/guilds/{guild_id}/members?limit=1000&after=user_id
Response (200): [array of member objects]

PUT /api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}
Response: 204 No Content

PATCH /api/v10/guilds/{guild_id}/members/{user_id}
Request: {"nick": "Nickname", "roles": ["role_id_1"], "communication_disabled_until": "2024-05-25T11:00:00Z"}
Response (200): {updated member}
```

### Design Patterns

| Pattern | Implementation |
|---|---|
| **Snowflake IDs** | 64-bit IDs encoding timestamp + worker + sequence (ordering without DB) |
| **Permission Bitfield** | 53-bit integer for all permissions (fast bitwise checks) |
| **Intent-based Filtering** | Clients declare which events they want (reduces bandwidth) |
| **Gateway Sharding** | Each shard handles ~2500 guilds (client-side sharding for bots) |
| **ETF (External Term Format)** | Binary encoding option for gateway events (vs JSON) |
| **Zlib Compression** | Transport-level compression for gateway WebSocket |
| **Lazy Loading** | Large guild members loaded on demand, not at connect |

---

## 7. Architecture Components Deep Dive

### 7.1 DNS & CDN (Cloudflare)

- Discord uses Cloudflare for DDoS protection, DNS, and CDN
- `discord.com` → Cloudflare → Origin servers
- `cdn.discordapp.com` → Cloudflare CDN → GCS buckets
- `media.discordapp.net` → Image proxy (resize, format conversion)
- Voice: Direct UDP to voice servers (bypasses Cloudflare for latency)
- Anycast DNS for global latency-based routing

### 7.2 Voice Architecture (SFU - Selective Forwarding Unit)

```
┌───────────────────────────────────────────────────────────────┐
│                    VOICE ARCHITECTURE                           │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  Client A ──UDP──→ ┌─────────────────┐ ──UDP──→ Client B       │
│  Client C ──UDP──→ │  VOICE SERVER   │ ──UDP──→ Client D       │
│                     │  (SFU Node)     │                         │
│                     │                 │                         │
│                     │ - Receives all  │                         │
│                     │   audio streams │                         │
│                     │ - Selectively   │                         │
│                     │   forwards to   │                         │
│                     │   each client   │                         │
│                     │ - Handles:      │                         │
│                     │   · Mixing      │                         │
│                     │   · Muting      │                         │
│                     │   · Priority    │                         │
│                     │     speaker     │                         │
│                     │   · Encryption  │                         │
│                     └─────────────────┘                         │
│                                                                 │
│  Protocol Stack:                                               │
│  - Signaling: WebSocket (voice gateway)                        │
│  - Media: UDP + RTP + Opus (audio) / VP8/H.264 (video)        │
│  - Encryption: xsalsa20_poly1305 (libsodium)                  │
│  - RTCP: Receiver reports for quality adaptation               │
│                                                                 │
│  Scaling:                                                       │
│  - One voice server per voice channel                          │
│  - Allocated from pool in nearest region                       │
│  - Capacity: ~2000 concurrent users per server node            │
│  - Auto-scale based on voice channel occupancy                 │
│                                                                 │
│  Regions: us-west, us-east, us-central, eu-west, eu-central,  │
│           singapore, sydney, brazil, japan, india, south-africa │
└───────────────────────────────────────────────────────────────┘
```

### 7.3 Gateway Sharding Model

```
┌────────────────────────────────────────────────────────────────┐
│                   GATEWAY SHARDING                               │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  shard_id = (guild_id >> 22) % num_shards                       │
│                                                                  │
│  Each Shard Handles:                                            │
│  - ~2500 guilds                                                 │
│  - All members of those guilds                                  │
│  - Events for those guilds (messages, presence, etc.)           │
│                                                                  │
│  Gateway Fleet:                                                  │
│  - Stateless WebSocket servers behind NLB                       │
│  - Client connects, identifies, gets assigned to shard          │
│  - Bot clients: manage own shards (shard [0, total])            │
│  - Regular clients: single shard (all their guilds)             │
│                                                                  │
│  Internal Pub/Sub:                                               │
│  - Guild events published to Kafka topic (partitioned by guild) │
│  - Gateway nodes subscribe to relevant guild partitions         │
│  - Or: Redis Pub/Sub for low-latency intra-cluster fanout      │
│                                                                  │
│  Session Resume:                                                 │
│  - session_id stored in Redis with sequence number              │
│  - On reconnect: replay missed events from buffer               │
│  - Buffer: last 5 minutes of events per session (Redis list)    │
│  - If buffer expired: full re-identify (READY event)            │
└────────────────────────────────────────────────────────────────┘
```

---

## 8. Deep Dive - Critical Services

### 8.1 Message Fanout for Large Servers

**Problem**: A 1M-member server with 100K online users. Message in #general must reach all.

**Solution: Layered Fanout**
```
Tier 1: Message Service → Kafka (partition by channel_id)
Tier 2: Fanout Workers → Determine online members (Redis presence lookup)
Tier 3: Group by gateway shard → Send batch to each gateway node
Tier 4: Gateway node → Deliver to all connected clients subscribed to that channel

Optimization:
- Lazy guilds: Large servers marked as "lazy" - members loaded on demand
- Guild subscriptions: Client explicitly subscribes to channels it has open
- Suppress events: Don't send MESSAGE_CREATE for channels not visible to client
- Compression: zlib-stream compresses repeated patterns in events
- Intents: Bot clients filter to only receive needed event types
```

### 8.2 Permission Calculation

```
Permission Resolution Order:
1. @everyone role permissions (base)
2. Role permissions (OR all role permissions together)
3. Channel permission overwrites for @everyone
4. Channel permission overwrites for member's roles (OR)
5. Channel permission overwrites for specific member

Final permissions = computed_permissions & ~denied_permissions

Bitfield (53 bits):
CREATE_INSTANT_INVITE = 1 << 0
KICK_MEMBERS = 1 << 1
BAN_MEMBERS = 1 << 2
ADMINISTRATOR = 1 << 3  // Bypasses all checks
MANAGE_CHANNELS = 1 << 4
...
SEND_MESSAGES = 1 << 11
...

Caching:
- Computed permissions cached in Redis per (guild_id, channel_id, user_id)
- Invalidated on role change, overwrite change, or member role update
- Hot path: check cache before computing (99% hit rate)
```

### 8.3 Presence at Scale

```
Challenge: 200M users, need to show online status to friends/guild members

Strategy:
- Don't broadcast presence to entire guild (too expensive for large guilds)
- Presence visible to: friends + small guilds (< 1000 members)
- Large guilds: presence only for members with active chat open (lazy members)
- Guild online count: approximated, updated every 30s

Implementation:
1. Client connects → update Redis presence key (TTL 120s)
2. Heartbeat every 45s → refresh TTL
3. Presence change → publish to Kafka (presence.updates topic)
4. Fanout worker → determine subscribers (friends + small guild members)
5. Send PRESENCE_UPDATE event to subscriber gateway shards
6. Large guilds: only send presence for members in sidebar request
```

---

## 9. Component Optimization

### 9.1 Kafka Configuration

```
Topics:
  discord.messages          - 512 partitions, key=channel_id, retention=7d
  discord.guild.events      - 256 partitions, key=guild_id, retention=30d
  discord.presence          - 128 partitions, key=user_id, retention=1h
  discord.voice.events      - 64 partitions, key=guild_id, retention=1d
  discord.notifications     - 128 partitions, key=user_id, retention=3d
  discord.audit.log         - 256 partitions, key=guild_id, retention=90d
  discord.analytics         - 512 partitions, key=guild_id, retention=30d → S3

Consumer Groups:
  gateway-fanout    (messages → gateway shards for online delivery)
  notification-svc  (messages → push notifications for offline)
  search-indexer    (messages → Elasticsearch)
  analytics-sink    (all events → ClickHouse)
  audit-archiver    (audit → S3/Iceberg for long-term)
  moderation-ml     (messages → ML models for content safety)
```

### 9.2 ScyllaDB Optimization

```
- Partition key: channel_id (all messages in a channel on same partition)
- Problem: Very active channels create hot partitions
- Solution: Time-bucketed partitioning
  - partition_key = (channel_id, bucket) where bucket = msg_id >> 40
  - Each bucket covers ~1 day of messages
  - Recent bucket is hot, old buckets are cold (compacted)

- Read optimization:
  - Prepared statements (avoid query parsing overhead)
  - Token-aware routing (bypass coordinator)
  - Speculative retry at p95 latency
  - Local quorum reads for recent, ONE for old messages

- Write optimization:
  - LOCAL_QUORUM writes (strong consistency within region)
  - Batched reactions updates (collect for 100ms, batch write)
  - Separate reactions/pins from message content (different update frequency)
```

### 9.3 WebSocket Compression

```
Strategy:
- zlib-stream: Shared compression context across all messages on connection
  - Compresses repeated JSON keys (type, channel_id, etc.) to ~20% of original
  - 75-80% bandwidth reduction for typical event streams
  
- ETF (External Term Format): Binary Erlang format
  - 10-20% smaller than JSON for gateway events
  - Used by bot libraries for performance

- Selective events via Intents:
  - GUILDS (1 << 0): guild create/update/delete, channel events
  - GUILD_MEMBERS (1 << 1): member add/remove/update (privileged)
  - GUILD_MESSAGES (1 << 9): message events in guild channels
  - DIRECT_MESSAGES (1 << 12): message events in DMs
  - Not subscribing = events not sent = massive bandwidth savings

Memory per connection:
  - JSON + zlib: ~15KB (zlib context) + 4KB (buffers) = ~19KB
  - ETF + zlib: ~15KB + 2KB = ~17KB
  - 20M connections × 19KB = 380 GB total gateway memory
```

### 9.4 Caching Architecture

```
L1 - Process-local cache (each service node):
  - Permission computations: LRU 50K entries, TTL 30s
  - Channel info: LRU 100K entries, TTL 60s
  - User tokens: LRU 200K entries, TTL 5min

L2 - Redis Cluster (shared):
  - Guild metadata: ~50M guilds × 2KB = 100 GB
  - Channel membership: SET per channel, TTL 5min
  - Presence: 20M online users × 200B = 4 GB
  - Unread state: per-user per-channel last_read_id
  - Rate limit counters: sliding window per user per route
  - Session routing: user → gateway shard mapping

L3 - CDN (Cloudflare):
  - User avatars, guild icons, emoji, stickers
  - File attachments (after virus scan)
  - Static assets (JS, CSS, images)
  
Cache Invalidation:
  - Event-driven: Kafka events trigger Redis DEL/UPDATE
  - TTL-based: Short TTLs for frequently changing data
  - Versioned: Include version in cache key, bump on write
```

### 9.5 Database Sharding

```
PostgreSQL (via Vitess/Citus):
  - Shard key: guild_id for guild-related tables
  - Reference tables: users (replicated to all shards)
  - Cross-shard queries: user's guild list (fan-out to all shards, merge)
  - Shard count: 256 shards (can split further)
  - Routing: hash(guild_id) % 256

ScyllaDB:
  - Built-in consistent hashing (vnodes)
  - Token range: -2^63 to 2^63
  - Replication: RF=3 within region, async cross-region
  - Topology: 3 datacenters, 9+ nodes each

Redis Cluster:
  - 16384 hash slots
  - 6 masters + 6 replicas (minimum)
  - Key design: {guild_id} hash tag for co-located data
  - Separate clusters for: presence, cache, rate-limits
```

---

## 10. Observability

### 10.1 Metrics (Prometheus + Grafana)

```yaml
# Gateway Metrics
discord_gateway_connections_total{shard, status="connected|disconnected"}
discord_gateway_events_dispatched_total{event_type}
discord_gateway_event_latency_seconds{event_type, quantile}
discord_gateway_identify_total{status="success|fail|rate_limited"}
discord_gateway_resume_total{status="success|fail"}

# Message Metrics
discord_messages_sent_total{channel_type="text|dm|thread"}
discord_message_delivery_latency_seconds{quantile}
discord_message_fanout_size{quantile}
discord_messages_edited_total
discord_messages_deleted_total

# Voice Metrics
discord_voice_connections_active{region}
discord_voice_packet_loss_ratio{region, quantile}
discord_voice_latency_ms{region, quantile}
discord_voice_quality_score{region} # MOS score estimate
discord_voice_server_utilization{region}

# Infrastructure
scylladb_write_latency_p99{keyspace, table}
scylladb_read_latency_p99{keyspace, table}
redis_memory_used_bytes{cluster}
redis_commands_processed_total{cluster, command}
kafka_consumer_lag{topic, group}
elasticsearch_indexing_rate{index}
```

### 10.2 Distributed Tracing

```
Example Trace: Message Send
[Gateway] receive WS frame (0.1ms)
  → [Auth] validate token (0.5ms)
  → [Rate Limiter] check limits (0.2ms)
  → [Message Service] process (5ms)
    → [Permission] check send permission (0.5ms, cached)
    → [AutoMod] content scan (2ms)
    → [ScyllaDB] write message (3ms)
    → [Kafka] publish event (1ms)
  → [Gateway] send ACK to sender (0.1ms)
  
[Fanout Worker] consume event (async, +5ms)
  → [Redis] get channel subscribers (0.5ms)
  → [Redis] get online members (0.5ms)
  → [Gateway nodes] batch deliver (2ms)
    → [Gateway] dispatch to connections (0.1ms)

Total sender-perceived: ~8ms
Total delivery to online recipients: ~15ms
```

### 10.3 Alerting

```yaml
Critical (Page):
- Gateway connection drop > 5% in 1 minute
- Message delivery failure rate > 0.1%
- Voice server capacity > 90% in any region
- ScyllaDB write latency p99 > 100ms
- Kafka consumer lag > 1M events

Warning (Ticket):
- Search index lag > 5 minutes
- Redis memory > 80% capacity
- Gateway resume failure rate > 5%
- Voice packet loss > 2% in any region
- Error rate > 0.5% on any API endpoint

Business Metrics:
- Concurrent users trending down week-over-week
- Message volume anomaly (sudden spike = potential raid)
- Voice connection failures by region
- Bot API error rate by application
```

---

## 11. Considerations & Assumptions

### Key Assumptions
1. Read-heavy system: 20:1 read to write ratio for messages
2. Voice is real-time relay, not recorded (no storage needed)
3. Most guilds are small (< 100 members); few are very large (> 100K)
4. Geographic distribution: 40% NA, 30% EU, 20% APAC, 10% other
5. Bot traffic: ~30% of all API calls come from bots
6. Peak hours: 6PM-12AM local time per region (staggered globally)

### Key Trade-offs

| Decision | Chosen | Trade-off |
|---|---|---|
| ScyllaDB for messages | High write throughput, partition tolerance | Weaker consistency, no joins, no transactions |
| SFU over MCU for voice | Lower server compute (no mixing) | Higher client bandwidth (receives multiple streams) |
| Client-side sharding | Simpler server, scales with bots | Client complexity, resharding is painful |
| Eventual consistency for presence | Scalability, low latency | Users may see stale status for seconds |
| Snowflake IDs | Sortable, encode timestamp, no DB sequence | Fixed to 69 years of timestamps, worker coordination |
| No E2E encryption (default) | Server-side search, moderation, compliance | Privacy trade-off (mitigated by at-rest encryption) |

### Failure Handling

| Scenario | Recovery |
|---|---|
| Gateway node crash | Clients auto-reconnect + resume; events buffered in Redis 5min |
| Voice server crash | Clients detect via heartbeat timeout, reconnect to new server |
| ScyllaDB partition | LOCAL_QUORUM ensures 2/3 replicas; repair after recovery |
| Redis cluster partition | Degraded presence/cache; fall back to DB reads |
| Kafka broker loss | ISR replication (RF=3); consumers resume from committed offset |
| Full region outage | DNS failover to secondary region; cross-region ScyllaDB replicas |

### Security
- Token-based auth (rotating tokens, OAuth2 for bots)
- Voice encryption: xsalsa20_poly1305 per-connection key
- Rate limiting: per-user, per-route, per-guild, per-bot
- Anti-raid: detect mass joins, auto-enable verification
- Content scanning: PhotoDNA for CSAM, ML for spam/gore
- IP reputation: block known bad actors at edge
- DDoS: Cloudflare + internal rate limits + voice server protection
