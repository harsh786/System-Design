# WebSockets — Deep Dive for System Design

## Table of Contents
1. [What Are WebSockets](#what-are-websockets)
2. [WebSocket Protocol Internals](#websocket-protocol-internals)
3. [Load Balancing WebSockets](#load-balancing-websockets)
4. [Retry Mechanisms & Non-Functional Requirements](#retry-mechanisms--non-functional-requirements)
5. [The Thundering Herd Problem](#the-thundering-herd-problem)
6. [Real-World: How Slack Uses WebSockets](#real-world-how-slack-uses-websockets)
7. [Real-World: How Discord Uses WebSockets](#real-world-how-discord-uses-websockets)
8. [Design Patterns & Best Practices](#design-patterns--best-practices)

---

## What Are WebSockets

### The Problem WebSockets Solve

Traditional HTTP follows a **request-response** model:
- Client sends a request
- Server sends a response
- Connection closes (or stays idle in HTTP/1.1 keep-alive)

For real-time applications (chat, gaming, live dashboards), this model forces **polling**:

```
Client: "Any new messages?" → Server: "No"
Client: "Any new messages?" → Server: "No"
Client: "Any new messages?" → Server: "Yes, here's one"
```

This wastes bandwidth, adds latency, and doesn't scale.

### What WebSockets Actually Are

WebSocket is a **full-duplex, persistent communication protocol** over a single TCP connection. Once established:

- Either side can send data at any time
- No request-response overhead per message
- Connection stays open until explicitly closed
- Operates over port 80 (ws://) or 443 (wss://)

```
┌──────────┐                          ┌──────────┐
│  Client  │◄────── Full Duplex ──────►│  Server  │
│          │   (both can send/recv     │          │
│          │    at any time)           │          │
└──────────┘                          └──────────┘
```

### WebSocket vs Alternatives

| Feature | HTTP Polling | Long Polling | SSE | WebSocket |
|---------|-------------|--------------|-----|-----------|
| Direction | Client → Server | Client → Server | Server → Client | Bidirectional |
| Latency | High (poll interval) | Medium | Low | Lowest |
| Connection overhead | Per request | Per timeout | Single | Single |
| Server push | No | Simulated | Yes | Yes |
| Binary data | Yes | Yes | No (text only) | Yes |
| Use case | Simple APIs | Notifications | Live feeds | Chat, gaming |

---

## WebSocket Protocol Internals

### The Handshake (Upgrade Request)

WebSocket connections begin as a standard HTTP request with an **upgrade**:

```http
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Origin: http://example.com
```

Server responds:

```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

After this handshake, the TCP connection is **repurposed** — no more HTTP frames, only WebSocket frames.

### Connection Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│                    CONNECTION LIFECYCLE                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. TCP Handshake (SYN → SYN-ACK → ACK)               │
│  2. TLS Handshake (if wss://)                          │
│  3. HTTP Upgrade Request                                │
│  4. Server accepts → 101 Switching Protocols            │
│  5. ═══ WebSocket frames flow bidirectionally ═══       │
│  6. Either side sends Close frame                       │
│  7. Other side acknowledges Close                       │
│  8. TCP connection terminates                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Frame Structure

WebSocket data is sent in **frames**:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+-------------------------------+
|     Extended payload length continued, if payload len == 127  |
+-------------------------------+-------------------------------+
|                               | Masking-key, if MASK set to 1 |
+-------------------------------+-------------------------------+
|          Masking-key (continued)        |   Payload Data      |
+---------------------------------------+----------------------+
|                     Payload Data continued ...                |
+--------------------------------------------------------------+
```

**Key opcodes:**
- `0x1` — Text frame
- `0x2` — Binary frame
- `0x8` — Connection close
- `0x9` — Ping
- `0xA` — Pong

### Heartbeat (Ping/Pong)

WebSocket has built-in keep-alive:
- Server sends **Ping** frame
- Client must respond with **Pong** frame
- If no Pong received within timeout → connection is dead → close & reconnect

```
Server ──── Ping ────► Client
Server ◄─── Pong ───── Client    (connection alive)

Server ──── Ping ────► Client
Server     (timeout)              (connection dead, close it)
```

---

## Load Balancing WebSockets

### The Challenge

WebSocket connections are **long-lived and stateful**. This breaks traditional load balancing:

- Round-robin sends the upgrade request to Server A, but subsequent frames need to reach Server A too
- Unlike HTTP (stateless per request), you can't route each message independently
- Connections can last hours or days

### Strategy 1: Sticky Sessions (Session Affinity)

Route all traffic from a client to the same backend server.

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │  (L4 or L7)     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼───┐    ┌────▼───┐    ┌────▼───┐
         │Server A│    │Server B│    │Server C│
         │(User 1)│    │(User 2)│    │(User 3)│
         └────────┘    └────────┘    └────────┘
```

**Implementation:**
- **IP hash**: Hash client IP → consistent server mapping
- **Cookie-based**: Set a cookie during handshake that identifies the backend
- **Connection ID**: Use WebSocket connection ID for routing

**Pros:**
- Simple to implement
- No cross-server communication needed for single connections

**Cons:**
- Uneven load distribution (power users create hot spots)
- Server failure loses all connections on that node
- Cannot scale down gracefully

### Strategy 2: Layer 4 (TCP) Load Balancing

Route at the TCP level — once a connection is established, all packets go to the same server.

```
Client ──TCP──► LB ──TCP──► Backend
         (persistent connection maintained)
```

**How it works:**
- LB tracks the TCP connection (source IP:port → destination)
- All frames on that connection route to the same backend
- No need to understand WebSocket protocol

**Used by:** AWS NLB, HAProxy (TCP mode), NGINX stream

**Pros:**
- Very fast (no protocol parsing)
- Handles any TCP-based protocol

**Cons:**
- Cannot make routing decisions based on WebSocket content
- No path-based routing
- Cannot inject headers or modify frames

### Strategy 3: Layer 7 (Application) Load Balancing

Understand the HTTP upgrade and route intelligently.

```
Client ──HTTP Upgrade──► LB ──reads path/headers──► Backend
         (LB makes routing decision during handshake)
```

**How it works:**
- LB terminates TLS
- Inspects the HTTP upgrade request (path, headers, cookies)
- Routes to appropriate backend
- Then proxies WebSocket frames transparently

**Used by:** AWS ALB, NGINX (proxy_pass with upgrade), Envoy, Traefik

**Pros:**
- Path-based routing (`/chat` → chat servers, `/notifications` → notification servers)
- Can inject/modify headers during handshake
- Health-check aware routing

**Cons:**
- Higher latency than L4
- More complex configuration
- Must handle WebSocket timeout settings properly

### Strategy 4: Consistent Hashing

Map clients to servers using a hash ring — minimizes redistribution when servers are added/removed.

```
           Server A
          /        \
    Server D ──── Hash Ring ──── Server B
          \        /
           Server C

  hash(user_id) → position on ring → nearest server clockwise
```

**Key property:** When Server B is removed, only users mapped to B get redistributed (to C). Users on A, C, D are unaffected.

**Used for:** Chat rooms, game lobbies, pub/sub channel routing

### Strategy 5: Connection-Aware Load Balancing (Pub/Sub Backend)

Decouple the WebSocket connection from the business logic:

```
┌──────────┐     ┌──────────┐     ┌─────────────┐     ┌──────────────┐
│  Client  │────►│  Gateway │────►│  Message    │────►│  Business    │
│          │◄────│  Server  │◄────│  Broker     │◄────│  Logic       │
└──────────┘     └──────────┘     │(Redis/Kafka)│     └──────────────┘
                                  └─────────────┘
```

**How it works:**
- Gateway servers only handle WebSocket connections (stateless handlers)
- A message broker (Redis Pub/Sub, Kafka, NATS) delivers messages to the correct gateway
- Business logic publishes to a channel; the gateway subscribed to that channel delivers to the client
- Any gateway can serve any client

**This is how Slack and Discord work at scale.** More details in their sections below.

---

## Retry Mechanisms & Non-Functional Requirements

### Reconnection Strategy

When a WebSocket connection drops, the client must reconnect. Naive reconnection causes problems:

```
❌ Bad: Immediate retry in a loop
   disconnect → connect → disconnect → connect → ... (hammers server)

✅ Good: Exponential backoff with jitter
   disconnect → wait 1s → connect
   fail → wait 2s + random(0-1s) → connect
   fail → wait 4s + random(0-2s) → connect
   fail → wait 8s + random(0-4s) → connect
   (cap at 30-60 seconds)
```

### Exponential Backoff with Jitter

```python
# Pseudocode for reconnection
def calculate_backoff(attempt):
    base_delay = 1.0  # seconds
    max_delay = 60.0  # cap
    
    # Exponential: 1, 2, 4, 8, 16, 32, 60, 60...
    delay = min(base_delay * (2 ** attempt), max_delay)
    
    # Full jitter: randomize between 0 and calculated delay
    jitter = random.uniform(0, delay)
    
    return jitter

# Connection loop
attempt = 0
while not connected:
    try:
        connect()
        attempt = 0  # reset on success
    except ConnectionFailed:
        wait(calculate_backoff(attempt))
        attempt += 1
```

### Types of Jitter

| Strategy | Formula | Use Case |
|----------|---------|----------|
| Full Jitter | `random(0, delay)` | General purpose, best spread |
| Equal Jitter | `delay/2 + random(0, delay/2)` | Ensures minimum wait |
| Decorrelated Jitter | `min(cap, random(base, prev_delay * 3))` | Good for correlated failures |

### Non-Functional Requirements for WebSocket Systems

#### 1. Reliability
- **At-least-once delivery**: Assign message IDs; client ACKs each message; server resends unacked
- **Ordering guarantee**: Sequence numbers per channel; client buffers and reorders if needed
- **Durable connections**: Auto-reconnect with state recovery

#### 2. Message Delivery After Reconnection

```
┌──────────────────────────────────────────────────┐
│           MESSAGE RECOVERY FLOW                   │
├──────────────────────────────────────────────────┤
│                                                  │
│  1. Client disconnects (last_seq = 42)           │
│  2. Server buffers messages 43, 44, 45           │
│  3. Client reconnects, sends: resume(seq=42)     │
│  4. Server replays messages 43, 44, 45           │
│  5. Normal flow continues from seq 46            │
│                                                  │
│  If buffer expired (>5 min):                     │
│  → Server sends FULL_SYNC                        │
│  → Client fetches via REST API                   │
│                                                  │
└──────────────────────────────────────────────────┘
```

#### 3. Scalability
- **Horizontal scaling**: Add more gateway servers behind load balancer
- **Connection limits**: Each server handles 50K-500K connections (OS tuning required)
- **Backpressure**: If client is slow to consume, buffer up to N messages then drop/disconnect

#### 4. Availability
- **Graceful degradation**: Fall back to long-polling if WebSocket fails
- **Multi-region**: Connect to nearest region; failover to another on outage
- **Health checks**: Regular ping/pong to detect dead connections quickly

#### 5. Security
- **Authentication**: Validate token during HTTP upgrade (not after)
- **Rate limiting**: Limit messages per second per connection
- **Payload validation**: Validate frame size and content before processing
- **Origin checking**: Verify Origin header during handshake

#### 6. Observability
- **Metrics**: Connection count, message rate, latency, error rate
- **Tracing**: Correlation ID per message for distributed tracing
- **Alerting**: Alert on connection spike/drop, message queue depth

---

## The Thundering Herd Problem

### What Is It?

When many clients simultaneously attempt to reconnect or request resources, overwhelming the server:

```
        Server goes down briefly
                  │
                  ▼
    ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐
    │ C1│ │ C2│ │ C3│ │ C4│ │ C5│  ... 100,000 clients
    └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘
      │     │     │     │     │
      └─────┴─────┴─────┴─────┘
                  │
                  ▼ ALL reconnect at once!
           ┌───────────┐
           │  Server   │ ← OVERLOADED → crash again
           └───────────┘
```

This creates a cascading failure loop: server recovers → gets slammed → crashes again.

### When Does Thundering Herd Happen with WebSockets?

1. **Server restart/deploy**: All connections on that server drop simultaneously
2. **Network blip**: All clients in a region lose connection at the same time
3. **Load balancer failover**: Traffic shifts to remaining servers
4. **DNS TTL expiry**: Many clients resolve and reconnect simultaneously
5. **Cache stampede**: Cache expires → all connections request fresh data

### Solution 1: Exponential Backoff with Jitter (Client-Side)

Already covered above. The **jitter** is the key ingredient — it spreads reconnection attempts over time.

```
Without jitter:    ████████████ (all at 1s, 2s, 4s...)
With full jitter:  █ ░ █░ █ ░█░ █░█ (spread randomly)
```

### Solution 2: Server-Initiated Backoff

Server tells clients when to reconnect:

```json
// Server sends before closing connection:
{
  "type": "disconnect",
  "reason": "server_restart",
  "retry_after": 5000,          // base delay in ms
  "retry_jitter": 10000         // add random 0-10s
}
```

Clients respect `retry_after + random(0, retry_jitter)`.

### Solution 3: Connection Rate Limiting (Server-Side)

Limit how many new connections the server accepts per second:

```
┌─────────────────────────────────────────────┐
│          ADMISSION CONTROL                   │
├─────────────────────────────────────────────┤
│                                             │
│  Max new connections: 1000/sec              │
│  Current connections: 50,000                │
│  Queue size: 5000 pending                   │
│                                             │
│  If queue full:                             │
│    → Return 503 + Retry-After header        │
│    → Client backs off and retries           │
│                                             │
└─────────────────────────────────────────────┘
```

### Solution 4: Rolling Deploys / Connection Draining

During deployments, don't kill all connections at once:

```
Deploy Strategy (for 4 servers):

Time 0:  [A: serving] [B: serving] [C: serving] [D: serving]
Time 1:  [A: draining] [B: serving] [C: serving] [D: serving]
           └── sends "reconnect in 0-30s" to 25% of clients
Time 2:  [A: new version] [B: draining] [C: serving] [D: serving]
Time 3:  [A: new version] [B: new version] [C: draining] [D: serving]
Time 4:  [A: new version] [B: new version] [C: new version] [D: draining]
Time 5:  All on new version, no thundering herd
```

### Solution 5: Token Bucket for Reconnection

Server issues reconnection tokens that control the rate:

```python
# Server-side token bucket
class ReconnectionThrottler:
    def __init__(self, rate=1000, capacity=5000):
        self.tokens = capacity
        self.rate = rate  # tokens per second
        self.capacity = capacity
    
    def allow_connection(self):
        self.refill()
        if self.tokens > 0:
            self.tokens -= 1
            return True  # accept connection
        return False  # return 503 Retry-After
```

### Solution 6: Staggered Reconnection Windows

Assign each client a reconnection "slot" based on their ID:

```
slot = hash(client_id) % reconnection_window_seconds

# If window is 60 seconds:
# Client A (hash=15) → reconnect at T+15s
# Client B (hash=42) → reconnect at T+42s
# Client C (hash=3)  → reconnect at T+3s
```

This deterministically spreads load without needing coordination.

---

## Real-World: How Slack Uses WebSockets

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      SLACK ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌────────────────┐    ┌──────────────────┐   │
│  │  Slack   │    │   Edge/CDN     │    │  WebSocket       │   │
│  │  Client  │───►│   (Envoy)      │───►│  Gateway         │   │
│  │  (App)   │    │                │    │  Servers         │   │
│  └──────────┘    └────────────────┘    └────────┬─────────┘   │
│                                                  │              │
│                                    ┌─────────────┼───────────┐ │
│                                    │             │           │ │
│                              ┌─────▼────┐  ┌────▼─────┐     │ │
│                              │  Channel │  │  Message  │     │ │
│                              │  Service │  │  Service  │     │ │
│                              └─────┬────┘  └────┬─────┘     │ │
│                                    │            │            │ │
│                              ┌─────▼────────────▼─────┐     │ │
│                              │     Message Store       │     │ │
│                              │   (MySQL + Vitess)      │     │ │
│                              └────────────────────────┘     │ │
│                                                             │ │
│                              ┌────────────────────────┐     │ │
│                              │    Redis Pub/Sub       │     │ │
│                              │  (message fan-out)     │     │ │
│                              └────────────────────────┘     │ │
│                                                              │ │
└─────────────────────────────────────────────────────────────────┘
```

### How Slack Handles WebSocket Connections

1. **Connection establishment**: Client connects via `wss://wss-primary.slack.com`
2. **Authentication**: OAuth token validated during HTTP upgrade
3. **Channel subscriptions**: After connect, client sends list of channels to subscribe to
4. **Message delivery**: When a message is posted:
   - Message Service persists to MySQL (sharded via Vitess)
   - Publishes to Redis Pub/Sub channel
   - All gateway servers subscribed to that channel receive it
   - Each gateway delivers to connected clients in that Slack channel

### Slack's RTM (Real-Time Messaging) API Flow

```
1. Client calls POST /api/rtm.connect (REST)
   → Server returns: { url: "wss://wss-primary.slack.com/link/?ticket=..." }
   
2. Client opens WebSocket to that URL
   → Server sends: { type: "hello", connection_info: {...} }

3. Bidirectional messaging begins:
   Client → Server: { type: "message", channel: "C123", text: "Hello" }
   Server → Client: { type: "message", channel: "C123", user: "U456", text: "Hi" }

4. Ping/Pong every 30 seconds to keep alive
```

### Slack's Scale Numbers (approximate)
- **Millions** of concurrent WebSocket connections
- **Hundreds** of gateway servers
- Messages delivered in **< 200ms** (p99)
- Uses **Flannel** (their edge proxy layer) for connection management
- Falls back to long-polling for restricted networks

### Slack's Reconnection Approach
- Client tracks `message_id` of last received message
- On reconnect, sends `resume` with last known `message_id`
- Server replays missed messages from a short-term buffer
- If too many missed (>5 min gap), server sends a "please refetch via REST" signal
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s with jitter

### Key Design Decisions by Slack
- **Gateway servers are stateless** — only hold open TCP connections
- **Redis Pub/Sub for fan-out** — each channel is a Redis pub/sub channel
- **Sharded by workspace** — each workspace's data lives on specific MySQL shards
- **Graceful degradation** — if WebSocket fails, client falls back to polling `/api/conversations.history`

---

## Real-World: How Discord Uses WebSockets

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     DISCORD ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌────────────────┐    ┌──────────────────┐   │
│  │ Discord  │    │   Cloudflare   │    │  Gateway         │   │
│  │  Client  │───►│   (Edge)       │───►│  (Elixir)        │   │
│  │          │    │                │    │                  │   │
│  └──────────┘    └────────────────┘    └────────┬─────────┘   │
│                                                  │              │
│                                    ┌─────────────┼───────────┐ │
│                                    │             │           │ │
│                              ┌─────▼────┐  ┌────▼─────┐     │ │
│                              │  Guild   │  │  Session │     │ │
│                              │  Process │  │  Process │     │ │
│                              │ (Elixir) │  │ (Elixir) │     │ │
│                              └─────┬────┘  └──────────┘     │ │
│                                    │                         │ │
│                              ┌─────▼────────────────────┐   │ │
│                              │   Cassandra / ScyllaDB   │   │ │
│                              │   (Message Storage)      │   │ │
│                              └──────────────────────────┘   │ │
│                                                              │ │
│                              ┌──────────────────────────┐   │ │
│                              │   Pub/Sub Ring           │   │ │
│                              │   (Elixir distributed)   │   │ │
│                              └──────────────────────────┘   │ │
│                                                              │ │
└─────────────────────────────────────────────────────────────────┘
```

### Why Discord Chose Elixir/Erlang

Discord's gateway is written in **Elixir** (runs on the BEAM VM):
- Each WebSocket connection is a lightweight Erlang **process** (~2KB memory)
- Can handle **millions of processes** per node
- Built-in fault tolerance (supervisor trees)
- Hot code reloading (deploy without dropping connections)
- Distributed by nature (Erlang clustering)

### Discord Gateway Protocol

```
1. Client connects to wss://gateway.discord.gg/?v=10&encoding=json

2. Server sends HELLO with heartbeat_interval:
   { op: 10, d: { heartbeat_interval: 41250 } }

3. Client sends IDENTIFY:
   { op: 2, d: { token: "...", intents: 513, ... } }

4. Server sends READY:
   { op: 0, t: "READY", d: { session_id: "...", resume_gateway_url: "...", ... } }

5. Heartbeat loop (client sends every 41.25s):
   Client: { op: 1, d: 251 }  (sequence number)
   Server: { op: 11 }         (heartbeat ACK)

6. Events flow:
   Server → Client: { op: 0, s: 252, t: "MESSAGE_CREATE", d: {...} }
```

### Discord's Gateway Opcodes

| Opcode | Name | Direction | Purpose |
|--------|------|-----------|---------|
| 0 | Dispatch | Server→Client | Event (MESSAGE_CREATE, etc.) |
| 1 | Heartbeat | Both | Keep-alive ping |
| 2 | Identify | Client→Server | Initial authentication |
| 6 | Resume | Client→Server | Reconnect and replay missed events |
| 7 | Reconnect | Server→Client | Server asks client to reconnect |
| 9 | Invalid Session | Server→Client | Session expired, re-identify |
| 10 | Hello | Server→Client | First message, contains heartbeat interval |
| 11 | Heartbeat ACK | Server→Client | Acknowledges heartbeat |

### Discord's Reconnection & Resume Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISCORD RESUME FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Normal flow:                                                   │
│    Client receives events with sequence numbers (s: 1, 2, 3...)│
│    Client tracks last sequence number received                  │
│                                                                 │
│  On disconnect:                                                 │
│    1. Connect to resume_gateway_url (from READY event)         │
│    2. Send RESUME: { op: 6, d: { token, session_id, seq: 3 }} │
│    3. Server replays events 4, 5, 6... that were missed        │
│    4. Normal flow continues                                     │
│                                                                 │
│  If resume fails (session expired, >5 min):                    │
│    1. Server sends Invalid Session (op: 9)                     │
│    2. Client must re-IDENTIFY (full reconnection)              │
│    3. Fresh READY event, new session                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### How Discord Handles Guilds (Servers) at Scale

Each Discord guild (server) is an **Elixir GenServer process**:

```
┌─────────────────────────────────────┐
│  Guild Process (e.g., Guild #12345) │
├─────────────────────────────────────┤
│  State:                             │
│    - Member list (cached)           │
│    - Channel permissions            │
│    - Voice states                   │
│    - Presence data                  │
│                                     │
│  Responsibilities:                  │
│    - Permission checks              │
│    - Fan-out messages to members    │
│    - Rate limiting per channel      │
│    - Maintain consistency           │
└─────────────────────────────────────┘
```

For large guilds (100K+ members), Discord uses **lazy loading**:
- Only send presence updates for visible members
- Guild member list is paginated
- Messages are only sent to users who have the channel "open"

### Discord's Scale Numbers
- **19+ million** concurrent WebSocket connections (2023 data)
- **Millions** of guilds with real-time message delivery
- **~46 million messages** sent per day at peak
- **< 100ms** message delivery latency (typical)
- Each Elixir node handles **hundreds of thousands** of connections
- Uses **consistent hashing** to map guilds to nodes

### Discord's Thundering Herd Mitigation
- **Opcode 7 (Reconnect)** with random delays: server tells different clients different retry times
- **Resume URL isolation**: separate gateway URL for resume vs fresh connections
- **Rate limiting IDENTIFY**: max 1 identify per 5 seconds per connection
- **Session management**: sessions survive brief disconnects (buffered for ~2 minutes)
- **Erlang supervision trees**: individual process crashes don't bring down the node

### Key Design Decisions by Discord
- **Elixir/BEAM** for the gateway — lightweight processes, natural distribution
- **ScyllaDB** for messages — handles write-heavy workload at scale
- **Guild-per-process model** — natural isolation and fault tolerance
- **Intents system** — clients declare which events they want (reduces bandwidth)
- **Zlib compression** — gateway supports compressed payloads for mobile
- **ETF encoding** — binary format option instead of JSON (faster parsing)

---

## Design Patterns & Best Practices

### Pattern 1: Gateway + Worker Separation

```
┌──────────┐      ┌───────────┐      ┌──────────────┐
│  Client  │◄────►│  Gateway  │◄────►│   Workers    │
│          │  WS  │  (dumb    │ Queue│  (business   │
│          │      │   proxy)  │      │   logic)     │
└──────────┘      └───────────┘      └──────────────┘
```

**Why:** Gateway servers are expensive (hold connections). Keep them simple. Push logic to stateless workers that can scale independently.

### Pattern 2: Event-Driven Fan-Out

```
Producer → Message Broker → Consumers (Gateway servers)
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 Gateway A   Gateway B   Gateway C
 (Users 1-3) (Users 4-6) (Users 7-9)
```

**Why:** Decouples message production from delivery. Any service can publish; gateways handle delivery.

### Pattern 3: Connection State Machine

```
┌─────────────┐    connect     ┌──────────────┐
│ DISCONNECTED│───────────────►│ CONNECTING   │
└──────────▲──┘                └───────┬──────┘
           │                           │ success
           │ max retries               ▼
           │ exceeded         ┌──────────────┐
           │                  │  CONNECTED   │◄── heartbeat OK
           │                  └───────┬──────┘
           │                          │ connection lost
           │                          ▼
           │                 ┌──────────────┐
           └─────────────────│ RECONNECTING │──── backoff + jitter
                             └──────────────┘
```

### Pattern 4: Presence System

For showing "user is online/typing/idle":

```
1. Client sends presence update via WebSocket
2. Gateway publishes to presence service
3. Presence service:
   - Updates in-memory state (Redis/CRDT)
   - Fans out to all members' gateways who are subscribed
   - Batches updates (don't send every keystroke)
4. Optimization: Only propagate to users who can "see" the user
```

### Pattern 5: Message Ordering Guarantees

```
Problem: Multiple gateway servers might deliver messages out of order.

Solution: Sequence numbers per channel.

Channel #general:
  msg_1 (seq: 1) → "Hello"
  msg_2 (seq: 2) → "World"
  msg_3 (seq: 3) → "!"

Client receives: seq 1, seq 3, seq 2
Client reorders: seq 1, seq 2, seq 3 → "Hello World !"
Client detects gap: if seq 4 missing for >2s → request via REST
```

### Production Checklist

```
□ Implement exponential backoff with full jitter on client
□ Add heartbeat (ping/pong) with configurable interval
□ Implement connection state machine with clear transitions
□ Add message sequence numbers for ordering
□ Support resume/replay for brief disconnections
□ Fall back to REST polling if WebSocket unavailable
□ Rate-limit incoming messages per connection
□ Set maximum payload size per frame
□ Monitor: connection count, message rate, error rate, latency
□ Load test: simulate thundering herd, measure recovery time
□ Graceful shutdown: drain connections before server stops
□ Compress payloads for mobile clients (zlib/permessage-deflate)
□ Authenticate during HTTP upgrade, not after
□ Use TLS (wss://) in production always
□ Implement backpressure: drop/buffer if client is slow
```

---

## Summary: Comparison Table

| Aspect | Slack | Discord |
|--------|-------|---------|
| Gateway language | Java/Go | Elixir (BEAM) |
| Message store | MySQL (Vitess sharding) | Cassandra/ScyllaDB |
| Fan-out mechanism | Redis Pub/Sub | Erlang distributed processes |
| Connection model | Stateless gateways + broker | Process-per-connection (lightweight) |
| Reconnection | Resume with message_id | Resume with session_id + sequence |
| Thundering herd | Jitter + rate limiting | Opcode 7 + session buffering |
| Compression | Optional | Zlib + ETF encoding option |
| Fallback | Long-polling | None (WebSocket required) |
| Scale unit | Workspace (sharded) | Guild (process isolation) |

---

## Key Takeaways

1. **WebSockets enable real-time bidirectional communication** — essential for chat, gaming, collaborative editing.

2. **Load balancing requires session affinity or pub/sub decoupling** — you can't round-robin individual messages.

3. **Exponential backoff with jitter is non-negotiable** — without it, reconnection storms will crash your system.

4. **The thundering herd problem has multiple solutions** — jitter (client), rate limiting (server), rolling deploys (ops), staggered slots (hybrid).

5. **At scale, separate gateway (connection) from logic (processing)** — gateways are stateless proxies; business logic lives elsewhere.

6. **Both Slack and Discord use pub/sub patterns** — Redis for Slack, Erlang distribution for Discord. The principle is the same: decouple producers from consumers.

7. **Resume/replay is critical** — brief disconnects should be invisible to users. Buffer a few minutes of events server-side.

8. **Choose your language wisely** — Elixir/Erlang excels at massive concurrent connections; Go/Java work with explicit connection management.
