# WhatsApp Architecture Deep Dive

## Overview

WhatsApp is a real-time messaging platform serving **2+ billion users** with end-to-end encryption, delivering **100+ billion messages per day** with minimal latency. Its architecture prioritizes:

- **Reliability** — messages never lost
- **Low latency** — sub-second delivery
- **Efficiency** — minimal bandwidth and server resources
- **Security** — end-to-end encryption by default

---

## High-Level Architecture

```
┌─────────────┐       ┌──────────────────┐       ┌───────────────────┐
│   Mobile    │◄─────►│   Edge/Gateway   │◄─────►│   Chat Service    │
│   Client    │  TLS  │   (Load Balancer)│       │   (Erlang/Elixir) │
└─────────────┘       └──────────────────┘       └───────────────────┘
                                                          │
                              ┌────────────────────────────┼────────────────────────────┐
                              │                            │                            │
                      ┌───────▼───────┐          ┌────────▼────────┐          ┌────────▼────────┐
                      │  Session/     │          │   Message       │          │   Media         │
                      │  Presence     │          │   Queue/Store   │          │   Service       │
                      │  Service      │          │   (Mnesia/      │          │   (S3/CDN)      │
                      │               │          │    Custom DB)   │          │                 │
                      └───────────────┘          └─────────────────┘          └─────────────────┘
```

---

## Core Components

### 1. Client Layer

**Connection Model:**
- Single persistent TCP/TLS connection from each device to WhatsApp servers
- Uses a custom binary protocol (XMPP-derived, heavily modified) called **Noise Protocol** for handshake
- Connection is maintained via keep-alive pings (every 30-60 seconds)
- On connection drop, client reconnects with exponential backoff

**Client Responsibilities:**
- End-to-end encryption/decryption (Signal Protocol)
- Local SQLite database for message storage
- Message queuing when offline
- Media compression and upload

### 2. Edge/Gateway Layer

**Purpose:** Entry point for all client connections.

**Components:**
- **Load Balancers** — distribute connections across chat servers
- **TLS Termination** — handles encryption at the edge
- **Rate Limiting** — prevents abuse (spam, DDoS)
- **Connection Routing** — maps user → server assignment

**Sticky Sessions:**
- Each user is pinned to a specific chat server for the duration of their session
- If the server goes down, the user is reassigned to another server
- Consistent hashing or a session registry determines assignment

### 3. Chat Service (Core Messaging Engine)

**Technology:** Originally Erlang (FreeBSD + custom Erlang/OTP), chosen for:
- Lightweight processes (millions of concurrent connections per node)
- Fault-tolerant (supervisor trees, "let it crash" philosophy)
- Hot code reloading (deploy without disconnecting users)
- Built-in distributed messaging primitives

**Responsibilities:**
- Maintain persistent connections with clients
- Route messages between users
- Handle presence (online/offline/typing)
- Manage delivery receipts (sent ✓, delivered ✓✓, read 🔵✓✓)

**Scale:**
- ~2 million connections per server (Erlang's strength)
- Horizontally scaled across thousands of nodes
- Each node handles both sender and receiver if co-located

### 4. Message Queue / Store

**Offline Message Queue:**
- When recipient is offline, messages are stored in a **transient queue**
- Queue is per-user, ordered by timestamp
- Messages are delivered in order when recipient reconnects
- Messages are deleted from server after delivery (forward secrecy design)

**Storage Characteristics:**
- Messages are NOT stored permanently on WhatsApp servers
- Only queued until delivered (typically seconds to hours)
- Uses Mnesia (Erlang's distributed database) or custom storage
- For group messages: fan-out on write or fan-out on read depending on group size

### 5. Session & Presence Service

**Presence Tracking:**
```
User A comes online → Server updates presence store
                   → Notifies User B (if B has A in contacts and is online)
                   → Shows "online" / "last seen" in B's UI
```

**Implementation:**
- Distributed in-memory store (like Redis cluster or custom Mnesia tables)
- Presence is eventually consistent (small delay acceptable)
- "Last seen" is persisted, "online" is ephemeral
- Typing indicators are purely transient (never stored)

### 6. Media Service

**Upload Flow:**
1. Client encrypts media locally (AES-256-CBC with random key)
2. Client uploads encrypted blob to media server (HTTP)
3. Server returns a media URL (CDN-backed)
4. Client sends message with: media URL + encryption key + SHA256 hash
5. Recipient downloads from CDN, decrypts locally

**Why this design:**
- Server never sees plaintext media (E2E encryption)
- CDN handles heavy bandwidth (images, videos)
- Message payload stays small (just a URL + key)
- Media can be re-downloaded without re-uploading

---

## Message Flow (Detailed)

### One-to-One Message Delivery

```
Sender                    WhatsApp Server              Receiver
  │                            │                          │
  │─── 1. Send Message ───────►│                          │
  │    (encrypted payload)     │                          │
  │                            │── 2. Store in queue ──►  │
  │◄── 3. Server ACK ─────────│   (if offline)           │
  │    (single tick ✓)         │                          │
  │                            │                          │
  │                            │◄── 4. Receiver online ───│
  │                            │                          │
  │                            │── 5. Push message ──────►│
  │                            │                          │
  │                            │◄── 6. Delivery ACK ──────│
  │◄── 7. Delivery receipt ────│                          │
  │    (double tick ✓✓)        │                          │
  │                            │                          │
  │                            │◄── 8. Read receipt ──────│
  │◄── 9. Read notification ───│    (user opened chat)    │
  │    (blue ticks)            │                          │
```

**Key Points:**
- Server ACK means "server received it" (first tick)
- Delivery ACK means "recipient's device received it" (second tick)
- Read receipt is optional (user can disable)
- Message is deleted from server after delivery ACK

### Group Message Delivery

**Small Groups (≤256 members):**
- **Fan-out on write**: Server creates a copy for each group member
- Each copy is queued independently
- Delivered independently (some members may be offline)

**Large Groups / Broadcast Lists:**
- **Fan-out on read**: Store one copy, each member reads from shared store
- More storage-efficient but higher read latency
- Used for communities/channels (1024+ members)

```
Sender ──► Server ──► Queue[User1] ──► User1 (online, delivered immediately)
                  ──► Queue[User2] ──► User2 (offline, queued)
                  ──► Queue[User3] ──► User3 (online, delivered immediately)
                  ──► Queue[User4] ──► User4 (offline, queued)
```

---

## End-to-End Encryption (Signal Protocol)

### Key Concepts

| Component | Purpose |
|-----------|---------|
| Identity Key Pair | Long-term key, identifies the user |
| Signed Pre-Key | Medium-term key, rotated periodically |
| One-Time Pre-Keys | Single-use keys for initial session setup |
| Session Key (Ratchet) | Derived per-message, provides forward secrecy |

### Session Setup (X3DH - Extended Triple Diffie-Hellman)

```
Alice wants to message Bob (first time):

1. Alice fetches Bob's key bundle from server:
   - Bob's Identity Key (IKb)
   - Bob's Signed Pre-Key (SPKb)
   - One of Bob's One-Time Pre-Keys (OPKb)

2. Alice performs X3DH:
   - DH1 = DH(IKa, SPKb)
   - DH2 = DH(EKa, IKb)
   - DH3 = DH(EKa, SPKb)
   - DH4 = DH(EKa, OPKb)  [if available]
   - Master Secret = KDF(DH1 || DH2 || DH3 || DH4)

3. Alice uses Master Secret to derive initial session keys
4. All subsequent messages use Double Ratchet for key evolution
```

### Double Ratchet Algorithm

- Every message uses a **unique encryption key**
- Keys are derived by "ratcheting" forward (hash chain)
- Even if one key is compromised, past/future messages remain secure
- Combines symmetric ratchet (fast) with DH ratchet (new entropy)

### Group Encryption

- Uses **Sender Keys** (each member has a unique sender key)
- Sender encrypts once with their sender key
- Each member can decrypt using the sender's public key
- More efficient than pairwise encryption for groups

---

## Infrastructure & Scaling

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Erlang/OTP (core), C++ (media processing) |
| OS | FreeBSD (custom-tuned for millions of connections) |
| Database | Mnesia (distributed), custom storage |
| Queue | Custom (Erlang-native message passing) |
| Media Storage | S3-compatible object store + CDN |
| Push Notifications | APNs (iOS), FCM (Android) |
| Protocol | Custom binary (Noise Protocol Framework) |

### Scaling Strategy

**Vertical Scaling (per server):**
- FreeBSD tuned for 2M+ concurrent connections per node
- Erlang processes are ~300 bytes each (millions per node)
- Custom kernel parameters for file descriptors, network buffers

**Horizontal Scaling:**
- Consistent hashing maps users to server clusters
- Stateless message routing (any server can route to any other)
- Geographic distribution (data centers per region)

**Data Partitioning:**
- Users partitioned by phone number hash
- Each partition handled by a cluster of servers
- Replication factor of 3 for durability

### Reliability Patterns

1. **Write-Ahead Log**: Messages written to disk before ACK
2. **Replication**: Multi-DC replication for disaster recovery
3. **Supervisor Trees**: Erlang's OTP supervises all processes, auto-restarts on crash
4. **Queue Persistence**: Offline message queues survive server restarts
5. **Idempotent Delivery**: Message IDs prevent duplicate delivery

---

## Push Notifications

When the app is in background/killed:

```
1. Server detects recipient has no active connection
2. Server enqueues message AND sends push notification
3. Push notification via APNs/FCM wakes the app
4. App reconnects → server delivers queued messages
5. App shows notification with message preview (decrypted locally)
```

**Optimization:**
- Push payload is minimal (just "you have a new message")
- Actual message content delivered over the persistent connection
- This preserves E2E encryption (push services can't read content)

---

## Multi-Device Architecture (WhatsApp Web/Desktop)

### Original Design (Phone-Centric)
- Phone was the primary device, always required
- WhatsApp Web was a mirror — messages relayed through phone
- If phone went offline, Web couldn't send/receive

### Current Design (Multi-Device, 2021+)
- Each device has its own identity key pair
- Messages are encrypted separately for each device
- Server fans out to all linked devices independently
- No phone connection required for other devices

```
Sender encrypts message for:
  ├── Recipient's Phone (Key A)
  ├── Recipient's Desktop (Key B)
  ├── Recipient's Web (Key C)
  └── Recipient's Tablet (Key D)

Each device decrypts independently with its own key.
```

**Challenge:** Key management grows linearly with devices × contacts.

---

## Status/Stories Architecture

- Stored in a distributed object store (not queued like messages)
- TTL of 24 hours (auto-deleted after expiry)
- Fan-out on read (viewer fetches from contacts' status feeds)
- Encrypted per-viewer (selective sharing uses recipient-specific keys)
- Media compressed and stored on CDN

---

## Voice/Video Calls Architecture

**Signaling:**
- Uses the existing persistent connection for call setup (SDP exchange)
- ICE candidate exchange through WhatsApp servers

**Media Transport:**
- Peer-to-peer (P2P) when possible (STUN to discover public IP)
- TURN relay when P2P fails (symmetric NAT, firewalls)
- End-to-end encrypted (SRTP with Signal-derived keys)

**Codec Selection:**
- Opus for audio (adaptive bitrate)
- VP8/H.264 for video
- Adaptive quality based on network conditions

```
Call Flow:
1. Caller sends OFFER (SDP) → Server → Callee
2. Callee sends ANSWER (SDP) → Server → Caller
3. ICE connectivity checks (STUN/TURN)
4. Direct P2P media stream established (or via TURN relay)
5. End-to-end encrypted audio/video
```

---

## Key Design Decisions & Trade-offs

| Decision | Rationale |
|----------|-----------|
| Erlang/FreeBSD | Millions of concurrent connections with minimal resources |
| Custom protocol (not HTTP) | Lower overhead, persistent connections, binary efficiency |
| No message persistence | Privacy-first, less storage cost, simpler compliance |
| Fan-out on write (small groups) | Lower read latency, simpler client logic |
| E2E encryption always on | User trust, regulatory compliance, reduced liability |
| Phone number as identity | Low friction signup, built-in contact discovery |
| Single persistent connection | Battery efficiency, instant delivery, presence tracking |

---

## Capacity Estimation (Back of Envelope)

```
Users:              2 billion
Daily Active Users: 500 million
Messages/day:       100 billion
Messages/second:    ~1.15 million

Average message size: 100 bytes (text) → 100 billion * 100B = 10 TB/day (text only)
Media messages:       ~15% of messages → CDN handles ~50 PB/day

Connections:
  - 500M concurrent connections
  - ~2M connections per server
  - ~250 chat servers minimum (likely 1000+ for redundancy)

Storage:
  - Transient only (messages deleted after delivery)
  - Peak queue: ~50 billion undelivered messages
  - At 100 bytes avg: ~5 TB peak queue storage
```

---

## Comparison with Other Messaging Systems

| Feature | WhatsApp | Telegram | Signal | iMessage |
|---------|----------|----------|--------|----------|
| Protocol | Custom (Noise) | MTProto | Signal Protocol | APNs + iMessage |
| E2E Encryption | Always (Signal) | Opt-in (Secret Chats) | Always (Signal) | Always (custom) |
| Message Storage | Transient | Cloud (permanent) | Transient | iCloud (optional) |
| Server Technology | Erlang | C++ | Java/Rust | Objective-C/Swift |
| Multi-device | Independent keys | Cloud sync | Independent keys | Apple ecosystem |
| Max Group Size | 1024 | 200,000 | 1000 | Unlimited |

---

## Summary

WhatsApp's architecture is a masterclass in:
1. **Connection efficiency** — millions of persistent connections via Erlang
2. **Privacy by design** — E2E encryption, no message storage
3. **Reliable delivery** — queue-based offline handling with delivery guarantees
4. **Minimal infrastructure** — famously ran with ~50 engineers for 900M users
5. **Protocol efficiency** — custom binary protocol over TCP for mobile optimization
