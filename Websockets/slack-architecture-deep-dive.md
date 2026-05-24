# Slack Architecture Deep Dive

## Table of Contents
1. [High-Level Architecture](#1-high-level-architecture)
2. [Gateway Server](#2-gateway-server)
3. [Channel Server](#3-channel-server)
4. [Admin Server](#4-admin-server)
5. [Presence Server](#5-presence-server)
6. [How All Servers Work Together](#6-how-all-servers-work-together)
7. [End-to-End Message Flow Examples](#7-end-to-end-message-flow-examples)
8. [Data Storage Layer](#8-data-storage-layer)
9. [Failure Scenarios & Resilience](#9-failure-scenarios--resilience)

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                         │
│   Desktop App    │    Mobile App    │    Web Browser    │    Bot/API         │
└───────┬──────────┴────────┬─────────┴───────┬───────────┴────────┬──────────┘
        │                   │                 │                    │
        ▼                   ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EDGE LAYER (Envoy / Flannel)                         │
│  • TLS termination   • Rate limiting   • Load balancing   • Auth validation  │
└───────┬──────────────────┬──────────────────┬──────────────────┬────────────┘
        │                  │                  │                  │
        ▼                  ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│   GATEWAY    │  │   CHANNEL    │  │    ADMIN     │  │    PRESENCE      │
│   SERVER     │  │   SERVER     │  │    SERVER    │  │    SERVER        │
│              │  │              │  │              │  │                  │
│ • WebSocket  │  │ • Message    │  │ • Workspace  │  │ • Online/Offline │
│   management │  │   routing    │  │   mgmt       │  │ • Away/DND      │
│ • Session    │  │ • Channel    │  │ • Permissions│  │ • Heartbeat     │
│   tracking   │  │   CRUD       │  │ • Billing    │  │ • Status text   │
│ • Event      │  │ • Fan-out    │  │ • User mgmt  │  │ • Typing        │
│   dispatch   │  │ • History    │  │ • Compliance │  │   indicators    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘
       │                 │                  │                   │
       ▼                 ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MESSAGE BUS (Redis Pub/Sub + Kafka)                   │
└───────┬──────────────────┬──────────────────┬──────────────────┬────────────┘
        │                  │                  │                  │
        ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                            │
│  MySQL/Vitess (sharded)  │  Redis (cache/sessions)  │  S3 (files/media)     │
│  Solr/Elasticsearch      │  Memcached               │  Kafka (event log)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Design Principles

| Principle | How Slack Applies It |
|-----------|---------------------|
| Stateless services | Gateway servers hold connections but no business state |
| Workspace sharding | Data partitioned by workspace (team) ID |
| Event-driven | All state changes propagate as events through message bus |
| Graceful degradation | WebSocket → long-polling → REST fallback |
| Eventually consistent | Presence/typing are best-effort, messages are consistent |

---

## 2. Gateway Server

The Gateway Server is the **real-time connection backbone** — it maintains persistent WebSocket connections with every online client.

### Responsibilities

```
┌─────────────────────────────────────────────────────────┐
│                    GATEWAY SERVER                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. WebSocket Lifecycle Management                       │
│     • Accept new connections (upgrade HTTP → WS)         │
│     • Maintain keep-alive (ping/pong every 30s)          │
│     • Handle graceful disconnection                      │
│     • Reconnection with message_id resume                │
│                                                          │
│  2. Session Registry                                     │
│     • Map: user_id → [connection_1, connection_2, ...]   │
│     • A user can have 3-5 simultaneous connections       │
│       (desktop + mobile + web + multiple workspaces)     │
│     • Store session metadata (device, workspace, etc.)   │
│                                                          │
│  3. Event Dispatch (Push to Client)                      │
│     • Subscribe to Redis channels for user's workspaces  │
│     • Filter events per connection (relevance check)     │
│     • Serialize and push events down WebSocket           │
│                                                          │
│  4. Message Ingestion (Receive from Client)              │
│     • Parse incoming WebSocket frames                    │
│     • Validate message structure                         │
│     • Route to appropriate backend service               │
│     • Return acknowledgement to client                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Connection State Machine

```
                    ┌──────────┐
                    │CONNECTING│
                    └────┬─────┘
                         │ WS handshake + auth token
                         ▼
                    ┌──────────┐
              ┌─────│CONNECTED │◄────────────────┐
              │     └────┬─────┘                  │
              │          │                        │
   ping timeout          │ ping/pong OK           │ reconnect with
              │          ▼                        │ last message_id
              │     ┌──────────┐                  │
              │     │  ACTIVE  │──────────────────┘
              │     └────┬─────┘        ▲
              │          │              │
              │    network error     resume
              │          │              │
              ▼          ▼              │
         ┌──────────────────────┐      │
         │    DISCONNECTED      │──────┘
         └──────────┬───────────┘
                    │ max retries exceeded
                    ▼
              ┌──────────┐
              │  CLOSED  │
              └──────────┘
```

### How Gateway Handles Scale

```
┌─────────────────────────────────────────────────────────────────┐
│  Slack runs ~600+ Gateway Server instances                       │
│                                                                  │
│  Each instance handles ~100,000-300,000 concurrent connections   │
│                                                                  │
│  Connection assignment: Consistent hashing on user_id            │
│  (allows same user's connections to land on same gateway         │
│   for efficient local fan-out)                                   │
│                                                                  │
│  Memory per connection: ~50-100 KB                               │
│  (socket buffers + session metadata + subscription state)        │
└─────────────────────────────────────────────────────────────────┘
```

### Gateway ↔ Redis Pub/Sub

```
Gateway subscribes to channels based on the user's workspace memberships:

  Gateway-A subscribes to:
    • workspace:T001 (all events for workspace T001)
    • channel:C001 (specific high-traffic channel)
    • dm:U001_U002 (direct message thread)

When a message arrives on Redis channel "workspace:T001":
  1. Gateway checks which local connections belong to T001
  2. For each connection, checks if user is member of the target channel
  3. Filters out events the user shouldn't see (permissions)
  4. Serializes event as JSON
  5. Pushes down the WebSocket
```

---

## 3. Channel Server

The Channel Server is the **message routing and storage brain** — it handles message persistence, channel membership, and fan-out logic.

### Responsibilities

```
┌─────────────────────────────────────────────────────────┐
│                   CHANNEL SERVER                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Message Processing                                   │
│     • Receive message from Gateway                       │
│     • Validate (user is member of channel, not muted)    │
│     • Persist to MySQL/Vitess                            │
│     • Assign message timestamp (ts) as unique ID         │
│     • Trigger fan-out to all channel members             │
│                                                          │
│  2. Channel Management                                   │
│     • Create/archive/delete channels                     │
│     • Manage channel membership (join/leave/invite)      │
│     • Channel settings (topic, purpose, pinned items)    │
│     • Channel types: public, private, DM, group DM      │
│                                                          │
│  3. Fan-Out Logic                                        │
│     • Determine recipient list for a message             │
│     • Publish event to Redis Pub/Sub                     │
│     • Handle @channel, @here, @everyone mentions         │
│     • Thread reply notifications                         │
│                                                          │
│  4. Message History                                      │
│     • Serve paginated channel history                    │
│     • Search within channel                              │
│     • Edit/delete message operations                     │
│     • File/attachment metadata                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Message Processing Pipeline

```
Client sends message:
  { "type": "message", "channel": "C001", "text": "Hello team!" }

         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: VALIDATION                                               │
│  • Is user authenticated? (JWT/session check)                    │
│  • Is user member of channel C001?                               │
│  • Is channel archived? (reject if yes)                          │
│  • Rate limit check (max messages per minute)                    │
│  • Content validation (length, formatting)                       │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: ENRICHMENT                                               │
│  • Parse mentions (@user, @channel, @here)                       │
│  • Unfurl links (fetch preview metadata)                         │
│  • Process slash commands (/remind, /poll)                       │
│  • Assign message timestamp: ts = "1716547200.000100"            │
│  • Assign workspace-scoped sequence number                       │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: PERSISTENCE                                              │
│  • Write to MySQL (Vitess shard for workspace T001)              │
│    INSERT INTO messages (workspace_id, channel_id, user_id,      │
│                          ts, text, ...) VALUES (...)              │
│  • Update channel's latest_ts                                    │
│  • Update unread counters for all members                        │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: FAN-OUT                                                  │
│  • Get channel membership list (cached in Redis)                 │
│  • Publish to Redis Pub/Sub: channel "workspace:T001"            │
│    {                                                             │
│      "type": "message",                                          │
│      "channel": "C001",                                          │
│      "user": "U001",                                             │
│      "text": "Hello team!",                                      │
│      "ts": "1716547200.000100",                                  │
│      "recipients": ["U002", "U003", "U004", ...]                 │
│    }                                                             │
│  • Gateway servers pick up this event and push to clients        │
└─────────────────────────────────────────────────────────────────┘
```

### Channel Membership Data Model

```
┌──────────────────────────────────────────────────┐
│ Table: channel_members                            │
├──────────────────────────────────────────────────┤
│ workspace_id  │ channel_id  │ user_id  │ role    │
│ T001          │ C001        │ U001     │ admin   │
│ T001          │ C001        │ U002     │ member  │
│ T001          │ C001        │ U003     │ member  │
├──────────────────────────────────────────────────┤
│ + last_read_ts (for unread badge calculation)     │
│ + muted (boolean)                                 │
│ + notification_pref (all/mentions/none)           │
└──────────────────────────────────────────────────┘

Fan-out decision tree:
  if message contains @channel or @here:
    notify ALL members (even muted, except DND)
  elif message contains @U003:
    notify U003 with highlight, others normally
  else:
    notify based on each member's notification_pref
```

---

## 4. Admin Server

The Admin Server handles **workspace management, user administration, permissions, billing, and compliance** — all the non-real-time administrative operations.

### Responsibilities

```
┌─────────────────────────────────────────────────────────┐
│                    ADMIN SERVER                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Workspace (Team) Management                          │
│     • Create/configure workspaces                        │
│     • Workspace settings (name, icon, domain)            │
│     • Enterprise Grid: manage linked workspaces          │
│     • Default channels for new members                   │
│                                                          │
│  2. User Management                                      │
│     • Invite/deactivate users                            │
│     • Role assignment (owner, admin, member, guest)      │
│     • Profile fields configuration                       │
│     • SCIM provisioning (enterprise SSO)                 │
│     • User groups management                             │
│                                                          │
│  3. Permissions & Policies                               │
│     • Who can create channels (public/private)           │
│     • Who can install apps/bots                          │
│     • Message editing/deletion permissions               │
│     • File upload restrictions                           │
│     • Guest access controls                              │
│     • Channel posting permissions                        │
│                                                          │
│  4. Billing & Plans                                      │
│     • Subscription management (Free/Pro/Business+/Grid)  │
│     • Seat count tracking                                │
│     • Feature gates based on plan                        │
│     • Usage analytics                                    │
│                                                          │
│  5. Compliance & Data Governance                         │
│     • Message retention policies                         │
│     • Data export (Discovery API)                        │
│     • DLP (Data Loss Prevention) rules                   │
│     • eDiscovery holds                                   │
│     • Audit logs                                         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Admin Server in the Request Flow

```
Unlike Gateway (WebSocket) and Channel (high-throughput messaging),
Admin Server primarily handles REST API calls:

  POST /api/admin.teams.settings.set
  POST /api/admin.users.invite
  POST /api/admin.conversations.setTeams
  GET  /api/admin.analytics.getFile

These are lower-frequency, higher-latency operations that
don't go through the WebSocket path.
```

### Permission Check Example

```
User U001 tries to post in #announcements (restricted channel):

  1. Client sends message via WebSocket → Gateway → Channel Server
  2. Channel Server calls Admin Server:
     GET /internal/permissions/check
       { user: "U001", channel: "C_ANNOUNCE", action: "post_message" }
  3. Admin Server checks:
     • Channel posting permission policy for #announcements
     • User's role (owner? admin? member?)
     • Channel-specific overrides
  4. Returns: { "allowed": false, "reason": "channel_posting_restricted" }
  5. Channel Server returns error to client via Gateway:
     { "ok": false, "error": "restricted_action", "channel": "C_ANNOUNCE" }
```

### Admin Events That Affect Other Servers

```
Admin action: Deactivate user U005
  │
  ├──► Channel Server:
  │      • Remove U005 from all channels
  │      • Reassign owned channels to workspace admin
  │
  ├──► Gateway Server:
  │      • Force-disconnect all of U005's WebSocket sessions
  │      • Reject any new connection attempts
  │
  ├──► Presence Server:
  │      • Clear U005's presence status
  │      • Notify U005's contacts of status change
  │
  └──► Data Layer:
         • Mark user as deactivated (soft delete)
         • Revoke all OAuth tokens
         • Cancel scheduled messages from U005
```

---

## 5. Presence Server

The Presence Server tracks **who is online, away, DND, or offline** and broadcasts status changes to interested parties.

### Responsibilities

```
┌─────────────────────────────────────────────────────────┐
│                   PRESENCE SERVER                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Status Tracking                                      │
│     • Online (active within last 5 minutes)              │
│     • Away (no activity for 5+ minutes)                  │
│     • DND (Do Not Disturb — manual or scheduled)         │
│     • Offline (no active connections)                    │
│                                                          │
│  2. Heartbeat Processing                                 │
│     • Receive heartbeats from Gateway (every 30s)        │
│     • Detect activity (keystrokes, mouse, focus)         │
│     • Transition: Active → Away after 5 min idle         │
│     • Transition: Away → Active on any activity          │
│                                                          │
│  3. Custom Status                                        │
│     • Status text ("In a meeting", "Lunch break")        │
│     • Status emoji                                       │
│     • Status expiration (auto-clear after X time)        │
│                                                          │
│  4. Typing Indicators                                    │
│     • Track who is typing in which channel               │
│     • Ephemeral — not persisted (TTL: 5 seconds)         │
│     • Fan-out only to members currently viewing channel  │
│                                                          │
│  5. Presence Subscriptions                               │
│     • Clients subscribe to presence of visible users     │
│     • DM sidebar: show online status of recent contacts  │
│     • Channel member list: show who is online            │
│     • Limit subscriptions to prevent N² fan-out          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Presence State Machine

```
                         ┌─────────────────────────┐
                         │                         │
       user activity     │    ┌──────────────┐     │    scheduled DND
      ┌──────────────────┼───►│    ACTIVE    │─────┼──────────────────┐
      │                  │    └──────┬───────┘     │                  │
      │                  │           │             │                  │
      │                  │    5 min idle           │                  │
      │                  │           │             │                  │
      │                  │           ▼             │                  ▼
      │                  │    ┌──────────────┐     │         ┌──────────────┐
      │                  └────│     AWAY     │     │         │     DND      │
      │                       └──────┬───────┘     │         └──────┬───────┘
      │                              │             │                │
      │                   all connections closed    │      DND timer expires
      │                              │             │                │
      │                              ▼             │                ▼
      │                       ┌──────────────┐     │         Back to previous
      └───────────────────────│   OFFLINE    │◄────┘         state (Active/Away)
                              └──────────────┘
```

### How Presence Scales (The Hard Problem)

```
PROBLEM: With 10 million users online, naive presence broadcasting is N²

  If user U001 goes offline:
    • U001 has 500 contacts across 50 channels
    • Naive: notify all 500 contacts = 500 messages
    • 10M users × 500 contacts = 5 BILLION status messages/sec (impossible)

SLACK'S SOLUTION: Subscription-Based Presence

  1. Clients only SUBSCRIBE to presence of users they can SEE:
     • Users in the DM sidebar (last 20 conversations)
     • Users in the currently-open channel member list
     • Typically ~50-200 subscriptions per client

  2. Presence Server maintains reverse index:
     presence_subscribers[U001] = {U002, U003, U007, ...}
     (who cares when U001's status changes)

  3. When U001 goes offline:
     • Look up presence_subscribers[U001] → only 30 users
     • Publish 30 targeted events (not 500)
     • O(subscribers) not O(workspace_size)

  4. Subscription lifecycle:
     • Client opens DM with U005 → subscribe to U005's presence
     • Client closes DM with U005 → unsubscribe after 60s
     • Channel switch → update subscriptions
```

### Presence Data Structure (Redis)

```
# Current presence state
HSET presence:U001 status "active" last_activity 1716547200 device "desktop"

# Custom status
HSET custom_status:U001 text "In a meeting" emoji ":calendar:" expires 1716550800

# Typing indicators (ephemeral, auto-expires)
SETEX typing:C001:U001 5 "1"    # Expires in 5 seconds

# Presence subscriptions (reverse index)
SADD presence_watchers:U001 U002 U003 U007 U015

# DND schedule
HSET dnd:U001 next_start "09:00" next_end "10:00" timezone "America/New_York"
```

---

## 6. How All Servers Work Together

### Architecture Interaction Matrix

```
┌─────────────┬────────────────┬────────────────┬────────────────┬────────────────┐
│  FROM \ TO  │    GATEWAY     │    CHANNEL     │     ADMIN      │   PRESENCE     │
├─────────────┼────────────────┼────────────────┼────────────────┼────────────────┤
│   GATEWAY   │ ─              │ Route messages │ ─              │ Heartbeats,    │
│             │                │ to channel svc │                │ activity signal│
├─────────────┼────────────────┼────────────────┼────────────────┼────────────────┤
│   CHANNEL   │ Fan-out events │ ─              │ Permission     │ ─              │
│             │ via Redis→GW   │                │ checks         │                │
├─────────────┼────────────────┼────────────────┼────────────────┼────────────────┤
│    ADMIN    │ Force-close    │ Update channel │ ─              │ Clear/update   │
│             │ connections    │ membership     │                │ user presence  │
├─────────────┼────────────────┼────────────────┼────────────────┼────────────────┤
│  PRESENCE   │ Push status    │ ─              │ DND schedule   │ ─              │
│             │ events via GW  │                │ from settings  │                │
└─────────────┴────────────────┴────────────────┴────────────────┴────────────────┘
```

### Communication Patterns

```
┌───────────────────────────────────────────────────────────────────────────┐
│ SYNCHRONOUS (gRPC / Internal REST):                                        │
│   • Gateway → Channel Server (send message)                                │
│   • Channel Server → Admin Server (permission check)                       │
│   • Gateway → Presence Server (heartbeat)                                  │
│                                                                            │
│ ASYNCHRONOUS (Redis Pub/Sub):                                              │
│   • Channel Server → Gateway (message fan-out)                             │
│   • Presence Server → Gateway (status change broadcast)                    │
│   • Admin Server → All services (user deactivated event)                   │
│                                                                            │
│ ASYNCHRONOUS (Kafka):                                                      │
│   • All servers → Kafka (audit events, analytics)                          │
│   • Channel Server → Search indexer (index new messages)                   │
│   • Admin Server → Billing (usage events)                                  │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 7. End-to-End Message Flow Examples

### Example 1: Alice sends "Hello!" to #general

```
Timeline:
────────────────────────────────────────────────────────────────────────────

[T+0ms] Alice's desktop client
  │ Sends via WebSocket:
  │ {"type":"message","channel":"C001","text":"Hello!","id":42}
  ▼

[T+2ms] Gateway Server (GW-17)
  │ • Receives WebSocket frame from Alice's connection
  │ • Parses JSON, validates structure
  │ • Looks up Alice's session: workspace=T001, user=U001
  │ • Routes to Channel Server via gRPC
  ▼

[T+5ms] Channel Server (CS-8)
  │ • Validates Alice (U001) is member of #general (C001) ✓
  │ • Checks posting permissions (via cached policy, not Admin call) ✓
  │ • Assigns ts: "1716547200.000100"
  │ • Writes to MySQL/Vitess shard for workspace T001
  │ • Responds to Gateway: { "ok": true, "ts": "1716547200.000100" }
  ▼

[T+12ms] Gateway Server (GW-17)
  │ • Sends ACK back to Alice's WebSocket:
  │   {"ok":true,"reply_to":42,"ts":"1716547200.000100"}
  │   (Alice now knows her message was received)
  ▼

[T+15ms] Channel Server (CS-8) — Fan-out phase
  │ • Fetches #general member list from Redis cache:
  │   [U001(Alice), U002(Bob), U003(Carol), U004(Dave), ...]
  │ • Publishes to Redis Pub/Sub channel "workspace:T001":
  │   {
  │     "type": "message",
  │     "subtype": "channel_message",
  │     "channel": "C001",
  │     "user": "U001",
  │     "text": "Hello!",
  │     "ts": "1716547200.000100",
  │     "team": "T001"
  │   }
  ▼

[T+18ms] All Gateway Servers subscribed to "workspace:T001"
  │ • GW-17 (has Alice, Bob): Push to Bob (skip Alice — she's the sender)
  │ • GW-03 (has Carol): Push to Carol's WebSocket
  │ • GW-42 (has Dave): Push to Dave's WebSocket
  │ • GW-17 also pushes to Alice's MOBILE connection (she's on 2 devices)
  ▼

[T+20-35ms] Bob, Carol, Dave receive message in their clients
  • Desktop shows message in #general
  • Mobile shows push notification (if channel not muted)
  • Unread badge increments

Total end-to-end latency: ~35ms (p50), ~80ms (p95), ~200ms (p99)
```

### Example 2: Bob goes from Active → Away (Presence Flow)

```
Timeline:
────────────────────────────────────────────────────────────────────────────

[T+0s] Bob has been idle for 5 minutes (no keystrokes/mouse)
  │
  ▼

[T+0s] Bob's Client
  │ Sends heartbeat with activity flag:
  │ {"type":"ping","activity":false}
  │ (activity:false means no user interaction since last ping)
  ▼

[T+1ms] Gateway Server (GW-17)
  │ • Responds with pong to keep connection alive
  │ • Forwards activity signal to Presence Server:
  │   gRPC: ReportActivity(user=U002, active=false, timestamp=now)
  ▼

[T+3ms] Presence Server
  │ • Checks current state: U002 was "active"
  │ • Last real activity was 5m03s ago → exceeds threshold
  │ • Transitions: U002 status = "away"
  │ • Updates Redis: HSET presence:U002 status "away"
  │ • Looks up who subscribes to U002's presence:
  │   SMEMBERS presence_watchers:U002 → {U001, U003, U007}
  │ • Publishes presence change to Redis Pub/Sub:
  │   channel: "presence_change"
  │   {
  │     "type": "presence_change",
  │     "user": "U002",
  │     "presence": "away",
  │     "recipients": ["U001", "U003", "U007"]
  │   }
  ▼

[T+6ms] Gateway Servers receive presence event
  │ • GW-17: Alice (U001) has U002 in DM sidebar → push event
  │ • GW-03: Carol (U003) has U002 in DM sidebar → push event
  │ • GW-42: Dave (U004) does NOT subscribe to U002 → skip
  ▼

[T+8ms] Alice and Carol's clients
  • Bob's avatar gains the "away" indicator (hollow circle)
  • No push notification (presence changes are silent)
```

### Example 3: Admin Deactivates User (Cross-Server Coordination)

```
Timeline:
────────────────────────────────────────────────────────────────────────────

[T+0ms] Workspace admin calls REST API:
  POST /api/admin.users.setInactive
  { "user": "U005", "team_id": "T001" }
  │
  ▼

[T+5ms] Admin Server
  │ • Validates caller has admin role ✓
  │ • Marks U005 as deactivated in database
  │ • Revokes all OAuth tokens for U005
  │ • Publishes "user_deactivated" event to Kafka + Redis:
  │   { "type":"user_change", "user":"U005", "active":false, "team":"T001" }
  ▼

[T+10ms] Channel Server (consumes event)
  │ • Removes U005 from all channel membership lists
  │ • For channels owned by U005: transfer ownership to admin
  │ • Cancels any scheduled messages from U005
  │ • Removes U005 from all user groups
  ▼

[T+10ms] Presence Server (consumes event, in parallel)
  │ • Sets U005 status = "offline" (permanent)
  │ • Notifies presence subscribers of U005:
  │   { "type":"presence_change", "user":"U005", "presence":"offline" }
  │ • Removes all presence subscriptions for U005
  ▼

[T+12ms] Gateway Server (consumes event, in parallel)
  │ • Finds all active WebSocket connections for U005
  │ • Sends disconnect frame with reason:
  │   { "type":"goodbye", "reason":"account_deactivated" }
  │ • Closes WebSocket connections
  │ • Adds U005 to connection blacklist (reject future attempts)
  ▼

[T+15ms] Other Gateway Servers push updates:
  • Members of channels that had U005 see:
    { "type":"member_left_channel", "user":"U005", "channel":"C001" }
  • U005's DM contacts see presence go offline

[T+20ms] U005's client receives disconnect, shows "account deactivated" screen
```

### Example 4: Typing Indicator Flow

```
Timeline:
────────────────────────────────────────────────────────────────────────────

[T+0ms] Alice starts typing in #general
  │ Client detects keypress in message input
  │ Sends (throttled to once per 3 seconds):
  │ {"type":"typing","channel":"C001"}
  ▼

[T+2ms] Gateway Server (GW-17)
  │ • Forwards to Presence Server (lightweight, no persistence)
  ▼

[T+4ms] Presence Server
  │ • Sets ephemeral key: SETEX typing:C001:U001 5 "1"
  │ • Publishes to Redis Pub/Sub:
  │   { "type":"user_typing", "channel":"C001", "user":"U001" }
  │ • NOTE: No database write — this is purely in-memory/ephemeral
  ▼

[T+6ms] Gateway Servers
  │ • Only push to users currently VIEWING #general
  │   (not all members — optimization to reduce noise)
  │ • Bob has #general open → sees "Alice is typing..."
  │ • Carol has #random open → does NOT receive typing event
  ▼

[T+5000ms] If Alice stops typing:
  • The SETEX key expires automatically
  • Client-side timeout clears "Alice is typing..." after 5s
  • No explicit "stopped typing" event needed (fire-and-forget)
```

### Example 5: Creating a New Channel (Admin + Channel + Gateway)

```
Timeline:
────────────────────────────────────────────────────────────────────────────

[T+0ms] Alice creates #project-alpha via UI
  │ REST API call (NOT WebSocket — this is a write operation):
  │ POST /api/conversations.create
  │ { "name": "project-alpha", "is_private": false, "team_id": "T001" }
  ▼

[T+5ms] Channel Server
  │ • Checks with Admin Server: Can U001 create public channels?
  │   → Admin checks workspace policy → YES ✓
  │ • Creates channel record in MySQL:
  │   INSERT INTO channels (id, workspace_id, name, creator, created)
  │   VALUES ('C999', 'T001', 'project-alpha', 'U001', NOW())
  │ • Adds Alice as first member and channel admin
  │ • Returns: { "ok": true, "channel": { "id": "C999", ... } }
  ▼

[T+15ms] Channel Server publishes event:
  │ Redis Pub/Sub → "workspace:T001":
  │ { "type": "channel_created", "channel": { "id":"C999", "name":"project-alpha" } }
  ▼

[T+18ms] Gateway Servers
  │ • Push "channel_created" event to ALL connected workspace members
  │ • (Everyone sees the new channel appear in their sidebar)
  ▼

[T+20ms] Alice's client receives:
  • Channel appears in sidebar
  • Auto-navigates to the new channel
  • Channel Server adds default channels bookmarks
```

---

## 8. Data Storage Layer

### Storage Distribution

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA STORAGE ARCHITECTURE                        │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  MySQL / Vitess (Primary Store)                                         │
│  ├── Sharded by workspace_id                                            │
│  ├── Messages table (largest: billions of rows)                         │
│  ├── Channels, Users, Teams tables                                      │
│  ├── Channel membership                                                 │
│  └── Permissions & policies                                             │
│                                                                         │
│  Redis (Hot Data)                                                        │
│  ├── Session store (user → gateway mapping)                             │
│  ├── Presence state (status, last_activity)                             │
│  ├── Channel membership cache                                           │
│  ├── Rate limiting counters                                             │
│  ├── Typing indicators (ephemeral, TTL=5s)                              │
│  └── Pub/Sub message bus (real-time fan-out)                            │
│                                                                         │
│  Kafka (Event Log)                                                       │
│  ├── All messages (durable, ordered)                                    │
│  ├── Audit events (who did what, when)                                  │
│  ├── Analytics events (usage tracking)                                  │
│  └── Cross-service coordination events                                  │
│                                                                         │
│  S3 / Object Storage                                                     │
│  ├── File uploads (images, documents, code snippets)                    │
│  ├── Avatar images                                                       │
│  └── Data exports (compliance)                                           │
│                                                                         │
│  Elasticsearch / Solr                                                    │
│  ├── Message full-text search                                            │
│  ├── File content search                                                 │
│  └── User/channel search                                                 │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

### Sharding Strategy (Vitess)

```
Shard key: workspace_id (team_id)

Why workspace_id?
  • All queries within a workspace are local (no cross-shard joins)
  • Channel members are always in the same workspace
  • Message queries are always workspace-scoped
  • Enterprise Grid: each linked workspace is its own shard

Shard distribution example:
  Shard 1: workspaces T001-T10000
  Shard 2: workspaces T10001-T20000
  ...
  Shard N: workspaces T(N-1)*10000+1 to T(N)*10000

Hot workspace handling:
  • Very large workspaces (>50K users) get dedicated shards
  • Slack, Uber, IBM → each on their own shard cluster
```

---

## 9. Failure Scenarios & Resilience

### What Happens When Each Server Fails

```
┌────────────────────┬──────────────────────────────────────────────────────┐
│ Component Failure   │ Impact & Recovery                                    │
├────────────────────┼──────────────────────────────────────────────────────┤
│ Gateway Server     │ • Clients reconnect to another GW (load balancer)    │
│ crashes            │ • Messages resume from last message_id               │
│                    │ • Brief ~2-5s interruption for affected clients       │
│                    │ • No data loss (state is in Channel Server)           │
├────────────────────┼──────────────────────────────────────────────────────┤
│ Channel Server     │ • Message sending temporarily fails (HTTP 503)       │
│ overloaded         │ • Gateway queues messages or returns error            │
│                    │ • Client shows "Trouble connecting" yellow bar        │
│                    │ • Read path (history) may timeout                     │
├────────────────────┼──────────────────────────────────────────────────────┤
│ Admin Server       │ • Cannot change settings/permissions                  │
│ down               │ • Existing permissions still work (cached)            │
│                    │ • New user invites fail                               │
│                    │ • Messaging continues unaffected                      │
├────────────────────┼──────────────────────────────────────────────────────┤
│ Presence Server    │ • Status indicators freeze/go stale                   │
│ down               │ • Typing indicators stop working                      │
│                    │ • Messages still deliver normally                     │
│                    │ • Least critical — graceful degradation               │
├────────────────────┼──────────────────────────────────────────────────────┤
│ Redis down         │ • Real-time delivery halted (no Pub/Sub)              │
│                    │ • Messages still persist to MySQL                     │
│                    │ • Clients get messages on next reconnect/refresh      │
│                    │ • Redis Sentinel/Cluster provides auto-failover       │
├────────────────────┼──────────────────────────────────────────────────────┤
│ MySQL shard down   │ • Affected workspaces cannot send/load messages       │
│                    │ • Other workspaces unaffected (isolation)             │
│                    │ • Failover to read replica within seconds             │
└────────────────────┴──────────────────────────────────────────────────────┘
```

### Graceful Degradation Hierarchy

```
FULL FUNCTIONALITY
    │
    │ WebSocket disconnects
    ▼
LONG-POLLING FALLBACK
    │ • Client polls every 3-5 seconds
    │ • Higher latency but still real-time-ish
    │
    │ Long-polling fails
    ▼
REST API FALLBACK
    │ • Client periodically fetches channel history
    │ • Manual refresh required
    │ • Send messages via POST (still works)
    │
    │ All connectivity lost
    ▼
OFFLINE MODE
    • Show cached messages from local storage
    • Queue outgoing messages
    • Sync when connection restored
```

---

## Quick Reference: Request Routing

```
Client Action              → Primary Server → Supporting Servers
─────────────────────────────────────────────────────────────────
Send message               → Channel        → Admin (permissions), Gateway (fan-out)
Edit/delete message        → Channel        → Gateway (fan-out edit event)
Create channel             → Channel        → Admin (permission check)
Join/leave channel         → Channel        → Gateway (membership event), Presence
Upload file                → Channel (meta) → S3 (binary), Gateway (notification)
Start typing               → Presence       → Gateway (typing indicator)
Go idle/active             → Presence       → Gateway (status event)
Set custom status          → Presence       → Gateway (status event)
Change workspace settings  → Admin          → Channel (policy update)
Invite user                → Admin          → Channel (add to default channels)
Deactivate user            → Admin          → All (force logout, remove membership)
Search messages            → Search (Solr)  → Channel (permission filter)
Install app/bot            → Admin          → Channel (bot joins channels)
```
