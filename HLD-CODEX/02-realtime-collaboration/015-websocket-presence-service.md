# Design WebSocket Presence Service

## 1. Functional Requirements

- **Real-time presence tracking**: Online, Offline, Away, Do Not Disturb, Invisible
- **Custom status**: Text + emoji with optional expiration
- **Typing indicators**: Broadcast typing state to conversation participants
- **Last seen**: Timestamp of last activity for offline users
- **Subscription model**: Subscribe to presence of specific users (friends, team members)
- **Multi-device presence**: Aggregate status across devices (most active wins)
- **Heartbeat**: Detect stale connections and auto-transition to offline
- **Bulk presence query**: Get presence of multiple users in one call
- **Presence events**: Push presence changes to subscribers in real-time
- **Activity detection**: Auto-away after inactivity period
- **Privacy controls**: Allow users to hide presence from specific people

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Presence update latency | < 200ms from state change to subscriber notification |
| Heartbeat interval | 30 seconds |
| Stale detection | Offline after 90s without heartbeat |
| Concurrent connections | 100M+ WebSocket connections |
| Presence queries | < 10ms p99 for bulk lookup (100 users) |
| Event throughput | 1M presence change events/second |
| Storage | Ephemeral (no persistence needed, rebuilt on connect) |
| Fan-out | Notify up to 5000 subscribers per user |
| Consistency | Eventual (1-3s lag acceptable for presence) |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| Connected users (peak) | 100M |
| Presence changes/sec (avg) | 200K (status transitions) |
| Presence changes/sec (peak) | 1M (morning login wave) |
| Heartbeats/sec | 100M / 30s = 3.3M heartbeats/sec |
| Typing events/sec | 500K |
| Subscription lookups/sec | 2M |
| Avg subscribers per user | 200 (friends + team) |
| Fan-out events/sec | 200K × 200 = 40M delivery events/sec |
| Memory per user presence | ~200 bytes |
| Total presence memory | 100M × 200B = 20 GB |
| Network (fan-out) | 40M × 100B = 4 GB/s |

## 4. Data Modeling

### Redis Schema (Primary Store)

```
# User presence state (HASH)
presence:{user_id} → {
  status: "online",           # online/away/dnd/invisible/offline
  last_active: 1716672000,    # Unix timestamp
  custom_text: "In a meeting",
  custom_emoji: ":calendar:",
  custom_expiry: 1716675600,  # When custom status expires
  device_desktop: "online",
  device_mobile: "away",
  device_web: "offline"
}
TTL: 90 seconds (refreshed by heartbeat)

# User's connection registry (SET)
connections:{user_id} → {"gw1:conn_abc", "gw2:conn_def"}
TTL: 120 seconds

# Subscription registry - who subscribes to this user's presence (SET)
subscribers:{user_id} → {subscriber_user_id_1, subscriber_user_id_2, ...}

# Reverse: what presences is this user subscribed to (SET)  
subscriptions:{user_id} → {target_user_id_1, target_user_id_2, ...}

# Typing indicator (SORTED SET)
typing:{conversation_id} → ZSET {user_id: timestamp}
# Auto-expire entries older than 6 seconds

# Gateway node registry
gateway:{gateway_id} → {host, port, connections_count, region}
TTL: 60 seconds

# User → Gateway mapping for routing
user_gateway:{user_id} → SET {gateway_id_1, gateway_id_2}
```

### Database Selection

| Store | Technology | Reason |
|---|---|---|
| Presence state | Redis Cluster | Sub-ms reads, TTL, pub/sub |
| Connection routing | Redis Cluster | Ephemeral, co-located with presence |
| Subscription graph | Redis + PostgreSQL | Redis for hot path, PG for persistence |
| Analytics/History | ClickHouse | Time-series presence history |
| Event Bus | Kafka | Durable delivery of presence events to consumers |

## 5. High-Level Design

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                             CLIENTS                                              │
│    Web (WebSocket)  │  Mobile (MQTT/WebSocket)  │  Desktop (WebSocket)          │
└─────────────────────────────────┬──────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                          EDGE LAYER                                              │
│  ┌─────────┐  ┌──────────┐  ┌─────────────────────────────────────────────┐   │
│  │   DNS   │  │   NLB    │  │         WebSocket Gateway Fleet              │   │
│  │(Latency │  │(TCP L4,  │  │  ┌────────────────────────────────────────┐  │   │
│  │ based)  │  │ sticky)  │  │  │ Gateway Node (handles 500K-1M conns)  │  │   │
│  └─────────┘  └──────────┘  │  │  - TLS termination                    │  │   │
│                               │  │  - Auth validation                    │  │   │
│                               │  │  - Heartbeat management               │  │   │
│                               │  │  - Local subscription cache           │  │   │
│                               │  │  - Event dispatch to connections      │  │   │
│                               │  └────────────────────────────────────────┘  │   │
│                               └─────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                       PRESENCE SERVICES                                          │
│                                                                                  │
│  ┌───────────────────────┐  ┌────────────────────────┐  ┌───────────────────┐  │
│  │  PRESENCE MANAGER     │  │  SUBSCRIPTION MANAGER  │  │  TYPING SERVICE   │  │
│  │  - State transitions  │  │  - Subscribe/unsubscribe│ │  - Broadcast type │  │
│  │  - Heartbeat handler  │  │  - Fan-out calculation │  │  - Auto-expire    │  │
│  │  - Multi-device merge │  │  - Privacy filtering   │  │  - Throttle       │  │
│  │  - Auto-away logic    │  │  - Bulk presence fetch │  │                   │  │
│  └───────────┬───────────┘  └────────────┬───────────┘  └───────────────────┘  │
│              │                             │                                      │
│  ┌───────────▼─────────────────────────────▼─────────────────────────────────┐  │
│  │                    FAN-OUT SERVICE                                          │  │
│  │  - Determine subscribers for presence change                               │  │
│  │  - Batch by gateway node (reduce network calls)                           │  │
│  │  - Priority: friends > team > mutual servers                              │  │
│  │  - Throttle: max 1 update per user per 5 seconds                          │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────┬──────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │  Redis Cluster   │  │   Apache Kafka   │  │      ClickHouse             │  │
│  │  (Presence State)│  │  (Event Stream)  │  │  (Presence Analytics)       │  │
│  │  - 6 masters     │  │  - presence.chg  │  │  - Online hours            │  │
│  │  - 6 replicas    │  │  - typing.events │  │  - Peak times              │  │
│  │  - ~20GB working │  │  - 64 partitions │  │  - User activity patterns  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design - APIs & Protocols

### WebSocket Protocol

```json
// Client → Server: Connect & Authenticate
{"op": "CONNECT", "d": {"token": "jwt...", "device": "desktop", "last_status": "online"}}

// Server → Client: Connected (with initial presence of subscriptions)
{"op": "CONNECTED", "d": {"session_id": "s_123", "heartbeat_interval": 30000, "presences": [{"user_id": "u1", "status": "online"}, ...]}}

// Client → Server: Heartbeat
{"op": "HEARTBEAT", "d": {"seq": 42}}

// Server → Client: Heartbeat ACK
{"op": "HEARTBEAT_ACK", "d": {"seq": 42}}

// Client → Server: Status Change
{"op": "STATUS_UPDATE", "d": {"status": "away", "custom_text": "BRB", "custom_emoji": ":coffee:", "expires_at": 1716675600}}

// Server → Client: Presence Update (pushed)
{"op": "PRESENCE_UPDATE", "d": {"user_id": "u_456", "status": "online", "custom_text": null, "devices": {"desktop": "online", "mobile": "idle"}}}

// Client → Server: Typing Start
{"op": "TYPING_START", "d": {"conversation_id": "conv_789"}}

// Server → Client: Typing Indicator
{"op": "TYPING", "d": {"conversation_id": "conv_789", "user_id": "u_456", "expires_in_ms": 6000}}

// Client → Server: Subscribe to users
{"op": "SUBSCRIBE", "d": {"user_ids": ["u_1", "u_2", "u_3"]}}

// Client → Server: Unsubscribe
{"op": "UNSUBSCRIBE", "d": {"user_ids": ["u_1"]}}
```

### REST APIs (Fallback/Admin)

```
GET /api/v1/presence?user_ids=u_1,u_2,u_3,...,u_100
Response: {
  "presences": [
    {"user_id": "u_1", "status": "online", "last_active": null, "custom": {...}},
    {"user_id": "u_2", "status": "offline", "last_active": 1716671000, "custom": null}
  ]
}

PUT /api/v1/presence/me
Request: {"status": "dnd", "custom_text": "Focusing", "expires_at": 1716680000}
Response: {"ok": true, "effective_status": "dnd"}

GET /api/v1/presence/me/devices
Response: {"devices": [{"id": "dev_1", "type": "desktop", "status": "online", "last_heartbeat": ...}]}

PUT /api/v1/presence/privacy
Request: {"hidden_from": ["u_blocked_1"], "show_last_seen": true, "show_online_status": true}
Response: {"ok": true}
```

## 7. Deep Dive - Core Components

### 7.1 Heartbeat & Connection Management

```
┌─────────────────────────────────────────────────────────┐
│            HEARTBEAT STATE MACHINE                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  CONNECTED ──(heartbeat received)──→ CONNECTED           │
│      │                                                    │
│      │ (no heartbeat for 30s)                            │
│      ▼                                                    │
│  WARNING ──(heartbeat received)──→ CONNECTED             │
│      │                                                    │
│      │ (no heartbeat for 60s more = 90s total)           │
│      ▼                                                    │
│  DISCONNECTED → cleanup connection → mark OFFLINE         │
│                                                           │
│  Implementation:                                         │
│  - Gateway maintains per-connection timer                 │
│  - Timer wheel data structure (O(1) insert/remove)       │
│  - Batch timeout processing every 1 second               │
│  - On timeout: close socket, remove from Redis,          │
│    publish presence_change event                         │
│                                                           │
│  Zombie Connection Detection:                            │
│  - TCP keepalive: OS level (every 60s)                   │
│  - Application heartbeat: every 30s                      │
│  - If network silently drops: detected within 90s        │
│  - Mobile: background → OS may kill socket               │
│    → push notification to trigger reconnect              │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Multi-Device Presence Resolution

```
Algorithm: Most Active Status Wins

Priority order: ONLINE > DND > AWAY > OFFLINE

Rules:
1. If ANY device is ONLINE → aggregate status = ONLINE
2. If NO device is ONLINE, but any is DND → status = DND
3. If NO device is ONLINE/DND, but any is AWAY → status = AWAY
4. If ALL devices are OFFLINE → status = OFFLINE
5. INVISIBLE: override all, always show as OFFLINE to others

Implementation:
  on_device_status_change(user_id, device_id, new_status):
    # Update device-specific status in Redis
    HSET presence:{user_id} device_{device_id} {new_status}
    
    # Compute aggregate
    all_statuses = HMGET presence:{user_id} device_desktop device_mobile device_web
    aggregate = compute_highest_priority(all_statuses)
    
    old_aggregate = HGET presence:{user_id} status
    if aggregate != old_aggregate:
      HSET presence:{user_id} status {aggregate}
      publish_presence_change(user_id, aggregate)

Edge Cases:
- User sets INVISIBLE: store as INVISIBLE, broadcast OFFLINE
- User sets DND on phone but ONLINE on desktop → show ONLINE
- All devices disconnect within 5s → batch into single OFFLINE event
- Reconnect within 10s → suppress OFFLINE/ONLINE flicker
```

### 7.3 Fan-out Architecture

```
Problem: User goes online → 5000 friends need to know
         200K users going online simultaneously (morning wave)
         = 200K × 200 avg friends = 40M events/second

Solution: Tiered Fan-out with Batching

┌─────────────────────────────────────────────────────────┐
│              FAN-OUT PIPELINE                             │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Step 1: Throttle                                        │
│  - Max 1 presence broadcast per user per 5s              │
│  - Coalesce rapid state changes (online→away→online)     │
│  - If status unchanged after throttle window: suppress   │
│                                                           │
│  Step 2: Determine Subscribers                           │
│  - Read subscribers:{user_id} from Redis                 │
│  - Filter by privacy settings                            │
│  - Filter by online subscribers only (no point pushing   │
│    to offline users)                                      │
│                                                           │
│  Step 3: Group by Gateway                                │
│  - Look up user_gateway:{subscriber_id} for each         │
│  - Group: {gateway_1: [sub_1, sub_4], gateway_2: [...]} │
│  - Reduces N individual calls to M gateway calls         │
│                                                           │
│  Step 4: Batch Deliver                                   │
│  - Send single RPC to each gateway with batch of updates │
│  - Gateway delivers to individual connections locally    │
│  - If gateway unreachable: retry once, then drop         │
│    (presence is ephemeral, missed update is OK)          │
│                                                           │
│  Optimization for Large Fan-out:                         │
│  - Celebrities (>10K subscribers): use Kafka topic       │
│  - Gateway nodes subscribe to celebrity topics           │
│  - No per-subscriber routing needed                      │
└─────────────────────────────────────────────────────────┘
```

### 7.4 Subscription Management

```
When to subscribe/unsubscribe:
- User opens app → subscribe to all friends + workspace members
- User opens DM → subscribe to that user specifically
- User closes app → unsubscribe all (connection cleanup)
- User unfriends → remove subscription

Storage:
- Hot path (Redis): bidirectional subscription graph
- Cold path (PostgreSQL): friend/team relationships (source of truth)
- On connection: load subscriptions from PG into Redis

Memory Optimization:
- Only maintain subscriptions for ONLINE users
- When user goes offline: remove from Redis subscriber sets
- Reduces Redis memory from (all users) to (online users only)
- 100M online × 200 subscriptions × 16B (user_id) = 320 GB
  → Too much! Need optimization:

Optimization - Shared Subscriptions:
- Users in same workspace share presence of all workspace members
- Instead of per-user subscription: workspace-level subscription
- Gateway subscribes to workspace presence channel
- Broadcast to all workspace members on that gateway
- Reduces unique subscriptions by 80%
```

## 8. Component Optimization

### 8.1 Redis Cluster Configuration

```
Cluster Topology:
- 6 master nodes (3 AZs × 2 nodes)
- 6 replica nodes (1 replica per master)
- 16384 hash slots distributed evenly
- Each node: 64GB RAM, 20GB used for presence

Key Distribution:
- presence:{user_id} → consistent hashing ensures even distribution
- Use {user_id} hash tag to co-locate user's presence + connections

Memory Optimization:
- Use Redis Hash for presence (ziplist encoding for small hashes)
- Each presence entry: ~200 bytes
- 100M entries × 200B = 20GB (fits in cluster)
- TTL on all keys: auto-cleanup of dead connections

Performance:
- Pipeline heartbeat renewals (batch 1000 per pipeline)
- Use EVALSHA (Lua scripts) for atomic multi-key operations
- Read from replicas for bulk presence queries
- Write to master for state updates
```

### 8.2 WebSocket Gateway Optimization

```
Per-Node Capacity:
- Epoll-based event loop (Linux) / kqueue (macOS)
- Single-threaded event loop + thread pool for CPU-heavy work
- Target: 500K-1M connections per node
- Memory: 2KB per connection × 1M = 2GB + overhead = ~8GB per node

Connection Handling:
- Compression: permessage-deflate (saves 60-70% bandwidth)
- Binary frames: Protocol Buffers for internal events
- Batching: aggregate multiple events into single frame (50ms window)
- Backpressure: if client can't keep up, drop old presence events
- Idle timeout: close connections with no activity for 5 minutes
  (mobile clients should send heartbeat)

Graceful Shutdown:
1. Stop accepting new connections
2. Send GOAWAY frame to all clients
3. Wait 30s for clients to reconnect to other nodes
4. Force-close remaining connections
5. Clean up Redis entries for orphaned sessions
```

### 8.3 Kafka for Presence Events

```
Topics:
  presence.state_changes    - 32 partitions, key=user_id
  presence.typing           - 16 partitions, key=conversation_id
  presence.analytics        - 64 partitions, key=user_id
  presence.heartbeats       - 8 partitions (internal metrics only)

Consumer Groups:
  fanout-workers:    consume state_changes → deliver to subscribers
  analytics-sink:    consume all → write to ClickHouse
  audit-workers:     consume state_changes → compliance log

Why Kafka for fan-out (vs direct):
  - Decouples presence change from delivery (async)
  - Replay: if fan-out worker crashes, replay from offset
  - Multiple consumers: analytics, audit, external integrations
  - Backpressure: consumer lag visible, auto-scale workers
```

### 8.4 Handling the "Thundering Herd" (Morning Login Wave)

```
Problem: 9 AM in a timezone → millions of users come online simultaneously
  - 10M users × login over 30 min = 5,500 logins/sec
  - Each triggers presence change + fan-out
  - Spike in Redis writes + event generation

Mitigations:
1. Jittered startup:
   - Client adds random 0-5s delay before connecting
   - Spreads load over time window

2. Batched presence updates:
   - Aggregate presence changes in 1-second windows
   - Single bulk event: "these 500 users came online"
   - Subscribers get batch update instead of 500 individual events

3. Lazy presence delivery:
   - Don't push to users who haven't opened the app yet
   - Deliver presence state on-demand when user opens friend list
   - Reduces fan-out by 80% (most subscribers are idle)

4. Auto-scaling:
   - Pre-scale gateway fleet before known peak hours
   - Redis cluster scales reads via replicas
   - Kafka consumer group auto-scales on lag
```

## 9. Observability

### Metrics

```yaml
# Connection metrics
presence_ws_connections_total{gateway, region}
presence_ws_connection_duration_seconds{quantile}
presence_ws_messages_received_total{type="heartbeat|status|typing|subscribe"}
presence_ws_messages_sent_total{type="presence_update|typing|heartbeat_ack"}

# Presence state metrics  
presence_status_transitions_total{from, to}
presence_online_users_gauge{region}
presence_heartbeat_timeout_total
presence_stale_connections_cleaned_total

# Fan-out metrics
presence_fanout_latency_seconds{quantile}
presence_fanout_batch_size{quantile}
presence_fanout_dropped_total{reason="throttle|offline_subscriber|gateway_down"}
presence_subscribers_per_user{quantile}

# Infrastructure
redis_operations_total{command, result}
redis_latency_seconds{command, quantile}
kafka_consumer_lag{topic, group}
gateway_memory_usage_bytes{node}
gateway_cpu_usage_percent{node}
```

### Alerts

```yaml
Critical:
- presence_online_users_gauge drops > 20% in 5 min (mass disconnect)
- redis latency p99 > 10ms (presence queries failing)
- gateway connection acceptance rate < 90% (overloaded)

Warning:
- heartbeat timeout rate > 5% (network issues)
- fanout latency p99 > 1s (subscribers getting stale data)
- kafka consumer lag > 100K (fan-out falling behind)
```

## 10. Considerations & Assumptions

### Key Assumptions
- Presence is inherently eventually consistent (2-3s lag acceptable)
- Missed presence events are not catastrophic (UI will catch up)
- Mobile clients may have unreliable connections (frequent reconnects)
- 80% of users have < 500 subscribers (friends + workspace)
- Presence data is ephemeral (rebuilds from connected state on restart)

### Privacy Model
- User can set visibility: Everyone, Friends Only, Nobody
- Invisible mode: server knows real status, broadcasts "offline"
- Last Seen: optional per-user privacy setting
- Typing: only visible to conversation participants
- Block: blocked users never see your presence

### Trade-offs

| Choice | Benefit | Cost |
|---|---|---|
| Redis for state | Ultra-low latency reads | Limited to memory, rebuild on failure |
| Eventual consistency | Scalability, availability | 1-3s stale presence possible |
| WebSocket over polling | Real-time, low overhead | Stateful, harder to scale |
| Throttled fan-out | Reduces storm during peaks | Presence updates delayed up to 5s |
| Ephemeral design | No persistence overhead | State lost on full cluster restart |
