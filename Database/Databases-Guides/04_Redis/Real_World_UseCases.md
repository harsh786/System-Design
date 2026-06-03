# Redis - Real World Use Cases & Production Guide

## Table of Contents
1. [Use Case 1: Twitter Timeline Cache](#use-case-1-twitter-timeline-cache)
2. [Use Case 2: Snapchat Rate Limiting](#use-case-2-snapchat-rate-limiting)
3. [Use Case 3: Slack Online Presence](#use-case-3-slack-online-presence)
4. [Use Case 4: Stripe Idempotency Keys](#use-case-4-stripe-idempotency-keys)
5. [Use Case 5: Pinterest Feed Generation](#use-case-5-pinterest-feed-generation)
6. [Replication Deep Dive](#replication-deep-dive)
7. [Scalability Patterns](#scalability-patterns)
8. [Production Setup](#production-setup)
9. [Core Concepts](#core-concepts)

---

## Use Case 1: Twitter Timeline Cache

### Why Redis?
- Sub-millisecond reads for timeline retrieval
- Sorted Sets for time-ordered feed items
- Lists for push-based fan-out
- Memory-efficient for hot data

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│            Twitter Home Timeline (Fan-out-on-Write)                  │
└─────────────────────────────────────────────────────────────────────┘

When User Posts a Tweet:
┌──────────┐    ┌──────────────┐    ┌─────────────────────────────────┐
│  Author  │───▶│  Tweet Svc   │───▶│  Fan-out Service                │
│  tweets  │    │  (write to   │    │                                  │
└──────────┘    │   MySQL)     │    │  For each follower:             │
                └──────────────┘    │    LPUSH timeline:{follower_id} │
                                    │    tweet_id                       │
                                    │    LTRIM timeline:{follower_id}  │
                                    │    0 799  (keep last 800)        │
                                    └─────────────────────────────────┘
                                              │
                                    ┌─────────┼─────────┐
                                    │         │         │
                                    ▼         ▼         ▼
                              ┌──────────┐ ┌──────────┐ ┌──────────┐
                              │ Redis 1  │ │ Redis 2  │ │ Redis 3  │
                              │ (users   │ │ (users   │ │ (users   │
                              │  A-F)    │ │  G-N)    │ │  O-Z)    │
                              └──────────┘ └──────────┘ └──────────┘

When User Opens Timeline:
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Reader  │───▶│  Timeline    │───▶│    Redis     │───▶│  Tweet Hydra │
│  Client  │    │  Service     │    │  LRANGE 0 20 │    │  (get full   │
└──────────┘    └──────────────┘    └──────────────┘    │  tweet data) │
                                                        └──────────────┘

Data Structure Choice:
┌────────────────────────────────────────────────────────────────┐
│  Key: timeline:{user_id}                                        │
│  Type: List (for simple chronological)                          │
│        OR Sorted Set (for ranked/algorithmic feed)              │
│                                                                  │
│  List approach:                                                   │
│    LPUSH timeline:user123 tweet_id_789                          │
│    LRANGE timeline:user123 0 19  → latest 20 tweets            │
│                                                                  │
│  Sorted Set approach (algorithmic ranking):                      │
│    ZADD timeline:user123 <score> tweet_id_789                   │
│    ZREVRANGE timeline:user123 0 19                              │
│    Score = timestamp * relevance_factor                          │
└────────────────────────────────────────────────────────────────┘

Celebrity Problem (fan-out-on-read hybrid):
┌────────────────────────────────────────────────────────────────┐
│  User with 50M followers → don't fan-out on write (too slow)   │
│                                                                  │
│  Solution: Hybrid approach                                       │
│  - Normal users (< 10K followers): fan-out-on-write            │
│  - Celebrities (> 10K followers): fan-out-on-read              │
│                                                                  │
│  Timeline read = Redis cached timeline + merge celebrity tweets │
└────────────────────────────────────────────────────────────────┘
```

### Scale Numbers
- **~500M tweets/day** at peak
- **~300K reads/sec** for timeline
- **Redis memory**: Each timeline ~800 tweet IDs * 8 bytes = 6.4KB per user
- **Active users**: 200M * 6.4KB = ~1.3TB total (across cluster)

---

## Use Case 2: Snapchat Rate Limiting

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              Snapchat API Rate Limiting with Redis                   │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Client  │───▶│  API Gateway │───▶│    Redis     │───▶│  Backend     │
│  (App)   │    │  (NGINX/     │    │  (rate check)│    │  Service     │
└──────────┘    │   Envoy)     │    └──────────────┘    └──────────────┘
                └──────────────┘          │
                       │                  │ OVER LIMIT?
                       │                  ▼
                       │           ┌──────────────┐
                       └──────────▶│  429 Too     │
                                   │  Many Reqs   │
                                   └──────────────┘

Sliding Window Rate Limiter (Lua Script):
┌─────────────────────────────────────────────────────────────────────┐
│  -- Sliding window log algorithm (precise but memory-heavy)         │
│  local key = KEYS[1]                                                 │
│  local window = tonumber(ARGV[1])  -- window size in ms             │
│  local limit = tonumber(ARGV[2])   -- max requests                  │
│  local now = tonumber(ARGV[3])     -- current timestamp ms          │
│                                                                      │
│  -- Remove entries outside window                                    │
│  redis.call('ZREMRANGEBYSCORE', key, 0, now - window)               │
│                                                                      │
│  -- Count current requests in window                                 │
│  local count = redis.call('ZCARD', key)                             │
│                                                                      │
│  if count < limit then                                               │
│    redis.call('ZADD', key, now, now .. math.random())               │
│    redis.call('PEXPIRE', key, window)                               │
│    return 1  -- allowed                                              │
│  end                                                                 │
│  return 0  -- rate limited                                           │
└─────────────────────────────────────────────────────────────────────┘

Fixed Window Counter (simpler, less precise):
┌─────────────────────────────────────────────────────────────────────┐
│  Key: rate:{user_id}:{window_timestamp}                             │
│  Example: rate:user123:1709312400                                   │
│                                                                      │
│  INCR rate:user123:1709312400                                       │
│  EXPIRE rate:user123:1709312400 60  (auto-cleanup)                  │
│                                                                      │
│  If count > limit → reject                                          │
│                                                                      │
│  Edge case: request at 0:59 and 1:01 both pass                     │
│  (boundary problem, solved by sliding window)                       │
└─────────────────────────────────────────────────────────────────────┘

Token Bucket (Redis + Lua):
┌─────────────────────────────────────────────────────────────────────┐
│  Key: bucket:{user_id}                                               │
│  Hash fields: tokens, last_refill_time                              │
│                                                                      │
│  Algorithm:                                                          │
│  1. Calculate tokens to add since last_refill                       │
│  2. Cap at max_tokens (bucket capacity)                             │
│  3. If tokens >= cost → allow, subtract cost                        │
│  4. Else → reject, return retry-after                               │
│                                                                      │
│  Advantages: allows bursts up to bucket capacity                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Scale Numbers
- **750M+ daily active users**
- **Billions of API calls/day**
- **Redis latency**: < 0.1ms for rate check (local replica)
- **Multi-tier limits**: per-user, per-IP, per-endpoint, global

---

## Use Case 3: Slack Online Presence

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│           Slack - Real-time Presence System                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐  WebSocket  ┌──────────────┐    ┌──────────────────────────┐
│  Client  │◀═══════════▶│  Connection  │───▶│         Redis            │
│  (Slack  │  heartbeat  │  Gateway     │    │                          │
│   App)   │  every 30s  │  (Edge)      │    │  Per-User Presence:      │
└──────────┘             └──────────────┘    │  HSET presence:user123   │
                                │            │    status "active"        │
                                │            │    last_seen 1709312400  │
                                │            │    device "desktop"       │
                                ▼            │                          │
                         ┌──────────────┐    │  Workspace Members Set:  │
                         │  Pub/Sub     │    │  SADD workspace:T123:    │
                         │  (presence   │    │    online user123        │
                         │   changes)   │    │    user456 user789       │
                         └──────────────┘    │                          │
                                │            │  Typed Status:            │
                                ▼            │  SET typing:channel:C1   │
                         ┌──────────────┐    │    user123               │
                         │  All other   │    │  EXPIRE 5s               │
                         │  connected   │    └──────────────────────────┘
                         │  clients in  │
                         │  workspace   │
                         └──────────────┘

Presence State Machine:
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  ┌────────┐  heartbeat  ┌────────┐  no heartbeat  ┌────────┐ │
│  │ ACTIVE │◀═══════════▶│  IDLE  │──────(5min)───▶│  AWAY  │ │
│  └────┬───┘             └────────┘                └────┬───┘ │
│       │                                                │      │
│       │ disconnect (30s timeout)                       │      │
│       └────────────────────┬──────────────────────────┘      │
│                            ▼                                  │
│                      ┌──────────┐                             │
│                      │ OFFLINE  │                             │
│                      └──────────┘                             │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Redis Data Model:
┌────────────────────────────────────────────────────────────────┐
│  1. Per-user hash (O(1) lookup):                               │
│     HSET user:presence:{user_id}                               │
│       status "active"                                          │
│       ts 1709312400                                            │
│       ws_id "T0123"                                            │
│     EXPIRE user:presence:{user_id} 120  (2min TTL)            │
│                                                                │
│  2. Workspace online set (who's online in this workspace):    │
│     SADD ws:online:{workspace_id} user_id_1 user_id_2 ...    │
│     SCARD ws:online:{workspace_id}  → "24 members online"    │
│                                                                │
│  3. Channel presence (Redis Pub/Sub for real-time):           │
│     PUBLISH channel:presence:{channel_id}                     │
│       '{"user":"U123","status":"active"}'                     │
│                                                                │
│  4. Typing indicators (short TTL):                            │
│     SETEX typing:{channel_id}:{user_id} 5 "1"                │
│     (auto-expires in 5 seconds)                               │
└────────────────────────────────────────────────────────────────┘
```

### Scale Numbers
- **20M+ concurrent connections** at peak
- **~3M presence updates/second**
- **Redis memory**: ~200 bytes per user * 20M = ~4GB per workspace cluster
- **P99 presence propagation**: < 500ms

---

## Use Case 4: Stripe Idempotency Keys

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│          Stripe - Idempotency & Distributed Locking                 │
└─────────────────────────────────────────────────────────────────────┘

Request Flow:
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Client  │───▶│  API Server  │───▶│    Redis     │───▶│  Process     │
│ (retry)  │    │              │    │  (check key) │    │  Payment     │
└──────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                       │                    │
                       │         ┌──────────┴──────────┐
                       │         │  Key exists?         │
                       │         │                      │
                       │         │  YES → return cached │
                       │         │        response      │
                       │         │                      │
                       │         │  NO  → set key with  │
                       │         │        lock + TTL    │
                       │         │        process req   │
                       │         │        store result  │
                       │         └─────────────────────┘
                       │
                       ▼

Redis Commands:
┌─────────────────────────────────────────────────────────────────────┐
│  -- Idempotency check + lock acquisition (atomic via Lua)           │
│                                                                      │
│  local key = "idempotency:" .. ARGV[1]  -- idempotency key         │
│  local lock_key = key .. ":lock"                                    │
│  local ttl = 86400  -- 24 hours                                     │
│                                                                      │
│  -- Check if already processed                                       │
│  local result = redis.call('GET', key)                              │
│  if result then                                                      │
│    return result  -- return cached response                         │
│  end                                                                 │
│                                                                      │
│  -- Try to acquire lock (prevent concurrent processing)             │
│  local locked = redis.call('SET', lock_key, ARGV[2],               │
│                            'NX', 'EX', 30)                          │
│  if not locked then                                                  │
│    return "LOCKED"  -- another request is processing this          │
│  end                                                                 │
│                                                                      │
│  return "PROCEED"  -- safe to process                               │
└─────────────────────────────────────────────────────────────────────┘

Distributed Lock (Redlock Algorithm):
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  5 Independent Redis Instances:                                      │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐               │
│  │Redis 1│ │Redis 2│ │Redis 3│ │Redis 4│ │Redis 5│               │
│  └───────┘ └───────┘ └───────┘ └───────┘ └───────┘               │
│       │        │        │         │        │                        │
│       ▼        ▼        ▼         ▼        ▼                        │
│   SET key val NX EX 30 (attempt on all 5)                          │
│                                                                      │
│   Lock acquired if: majority (3/5) succeed                          │
│                     AND total time < lock TTL                        │
│                                                                      │
│   Fencing token: monotonically increasing value                     │
│   to prevent stale locks from causing issues                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 5: Pinterest Feed Generation

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│          Pinterest - Smart Feed & Real-time Ranking                  │
└─────────────────────────────────────────────────────────────────────┘

Feed Generation Pipeline:
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Candidate   │───▶│   Ranking    │───▶│   Redis      │
│  Generation  │    │   Model      │    │  (cached     │
│  (1000 pins) │    │  (score each)│    │   top 200)   │
└──────────────┘    └──────────────┘    └──────────────┘
       │                                       │
       │                                       ▼
       │                              ┌──────────────┐
       │                              │  User opens  │
       │                              │  app → read  │
       │                              │  from Redis  │
       │                              └──────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────────────┐
│  Redis Data Structures Used:                                    │
│                                                                  │
│  1. Feed Cache (Sorted Set):                                    │
│     ZADD feed:{user_id} <relevance_score> pin_id               │
│     ZREVRANGE feed:{user_id} 0 19 WITHSCORES                   │
│     TTL: 24 hours (re-generated daily)                         │
│                                                                  │
│  2. Pin Engagement Counters (Hash):                             │
│     HINCRBY pin:{pin_id}:stats saves 1                         │
│     HINCRBY pin:{pin_id}:stats clicks 1                        │
│     HINCRBY pin:{pin_id}:stats impressions 1                   │
│                                                                  │
│  3. User Interest Vector (Hash):                                │
│     HSET user:{user_id}:interests                               │
│       "cooking" "0.85"                                          │
│       "travel" "0.72"                                           │
│       "diy" "0.45"                                              │
│                                                                  │
│  4. Bloom Filter (dedup - already seen):                        │
│     BF.ADD seen:{user_id} pin_id                               │
│     BF.EXISTS seen:{user_id} pin_id  → don't show again        │
│                                                                  │
│  5. Recently Viewed (List + TTL):                               │
│     LPUSH recent:{user_id} pin_id                               │
│     LTRIM recent:{user_id} 0 99                                 │
└────────────────────────────────────────────────────────────────┘

Real-time Signals:
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  User saves  │───▶│  Redis Pub/  │───▶│  Ranking Svc │
│  a pin       │    │  Sub / Stream│    │  (boost      │
└──────────────┘    └──────────────┘    │   similar)   │
                                        └──────────────┘
```

---

## Replication Deep Dive

### Master-Replica Replication

```
┌─────────────────────────────────────────────────────────────────────┐
│                Redis Replication Flow                                │
└─────────────────────────────────────────────────────────────────────┘

Initial Sync (Full Resynchronization):
┌──────────────┐                              ┌──────────────┐
│    MASTER    │                              │   REPLICA    │
│              │   1. PSYNC ? -1              │              │
│              │◀─────────────────────────────│              │
│              │                              │              │
│  2. BGSAVE  │   3. Send RDB snapshot       │              │
│  (fork)     │─────────────────────────────▶│  4. Load RDB │
│              │                              │              │
│  5. Buffer  │   6. Send buffered commands  │              │
│  commands   │─────────────────────────────▶│  7. Apply    │
│  during     │                              │              │
│  BGSAVE     │   8. Continuous stream       │              │
│              │─────────────────────────────▶│  (real-time) │
└──────────────┘                              └──────────────┘

Partial Resynchronization (after brief disconnect):
┌──────────────┐                              ┌──────────────┐
│    MASTER    │                              │   REPLICA    │
│              │  PSYNC <repl_id> <offset>    │              │
│              │◀─────────────────────────────│ (I was at    │
│              │                              │  offset 1000)│
│ Replication  │  +CONTINUE                  │              │
│ Backlog     │─────────────────────────────▶│              │
│ (1MB ring   │  Send commands from          │              │
│  buffer)    │  offset 1000 onward          │              │
│              │─────────────────────────────▶│ (catch up)   │
└──────────────┘                              └──────────────┘

Replication Backlog:
┌─────────────────────────────────────────────────────────────────────┐
│  Ring buffer on master (repl-backlog-size, default 1MB)             │
│  Stores recent write commands for partial resync                    │
│                                                                      │
│  If replica disconnects longer than backlog can cover → FULL RESYNC │
│  Production: set repl-backlog-size = 512mb (for large datasets)     │
└─────────────────────────────────────────────────────────────────────┘
```

### Redis Sentinel

```
┌─────────────────────────────────────────────────────────────────────┐
│                Redis Sentinel Architecture                           │
└─────────────────────────────────────────────────────────────────────┘

             ┌────────────┐  ┌────────────┐  ┌────────────┐
             │ Sentinel 1 │  │ Sentinel 2 │  │ Sentinel 3 │
             │ (monitor)  │  │ (monitor)  │  │ (monitor)  │
             └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
                   │               │               │
                   │  Ping every   │               │
                   │  1 second     │               │
                   └───────────────┼───────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
             ┌────────────┐ ┌────────────┐ ┌────────────┐
             │   MASTER   │ │  REPLICA 1 │ │  REPLICA 2 │
             │ (port 6379)│ │ (port 6380)│ │ (port 6381)│
             └────────────┘ └────────────┘ └────────────┘

Failover Process:
1. Sentinel detects master down (subjective down - SDOWN)
   → Master doesn't respond to PING for down-after-milliseconds (30s default)

2. Quorum agreement (objective down - ODOWN)
   → Multiple sentinels agree master is down (quorum: 2 of 3)

3. Sentinel leader election
   → One sentinel elected to perform failover (Raft-like)

4. Replica promotion
   → Best replica selected (priority, replication offset, runid)
   → SLAVEOF NO ONE on chosen replica

5. Reconfiguration
   → Other replicas: REPLICAOF new_master
   → Old master (when back): configured as replica

6. Client notification
   → Sentinels publish +switch-master event
   → Clients reconnect to new master

Timing: ~30 seconds total (configurable)
- Detection: down-after-milliseconds (30s)
- Election + promotion: 1-5s
- Total: 31-35s typical
```

### Redis Cluster Replication

```
┌─────────────────────────────────────────────────────────────────────┐
│            Redis Cluster with Replicas                               │
└─────────────────────────────────────────────────────────────────────┘

Hash Slots: 0-16383 distributed across masters

┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Master A (slots 0-5460)     Master B (slots 5461-10922)        │
│  ┌─────────────────┐        ┌─────────────────┐                │
│  │    Master A     │        │    Master B     │                │
│  │   (writes +    │        │   (writes +    │                │
│  │    reads)      │        │    reads)      │                │
│  └────────┬────────┘        └────────┬────────┘                │
│           │                          │                          │
│     ┌─────┴─────┐             ┌─────┴─────┐                   │
│     ▼           ▼             ▼           ▼                    │
│  ┌────────┐ ┌────────┐    ┌────────┐ ┌────────┐              │
│  │Replica │ │Replica │    │Replica │ │Replica │              │
│  │  A1    │ │  A2    │    │  B1    │ │  B2    │              │
│  └────────┘ └────────┘    └────────┘ └────────┘              │
│                                                                  │
│  Master C (slots 10923-16383)                                   │
│  ┌─────────────────┐                                            │
│  │    Master C     │                                            │
│  └────────┬────────┘                                            │
│     ┌─────┴─────┐                                              │
│     ▼           ▼                                               │
│  ┌────────┐ ┌────────┐                                         │
│  │Replica │ │Replica │                                         │
│  │  C1    │ │  C2    │                                         │
│  └────────┘ └────────┘                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Cluster Failover:
1. Replicas detect master failure (cluster-node-timeout: 15s)
2. Replica with most data starts election
3. Other masters vote (majority needed)
4. Winning replica promoted, takes over slots
5. Cluster resumes (~15-30s total)

MOVED/ASK Redirects:
- Client sends command to wrong node
- Node responds: MOVED 3999 127.0.0.1:6380
- Client updates slot map and retries
```

---

## Scalability Patterns

### Redis Cluster Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                Redis Cluster Internals                               │
└─────────────────────────────────────────────────────────────────────┘

Slot Calculation:
  HASH_SLOT = CRC16(key) mod 16384

  Key: "user:1000" → CRC16("user:1000") = 12345 → slot 12345
  → Routed to master owning slot 12345

Hash Tags (force keys to same slot):
  {user:1000}.profile  → CRC16("user:1000") → same slot
  {user:1000}.settings → CRC16("user:1000") → same slot
  Enables multi-key operations (MGET, Lua scripts, transactions)

Gossip Protocol:
┌──────────────────────────────────────────────────────────────────┐
│  Every node sends PING to random nodes every second              │
│                                                                  │
│  PING/PONG message contains:                                     │
│  - Node ID, IP, port, flags                                     │
│  - Slots served by this node                                    │
│  - Master/replica relationships                                  │
│  - Epoch (version) for conflict resolution                      │
│                                                                  │
│  Failure detection: if node doesn't PONG within                 │
│  cluster-node-timeout → marked as PFAIL                         │
│  If majority agrees → FAIL (triggers failover)                  │
└──────────────────────────────────────────────────────────────────┘
```

### Memory Optimization

```
┌─────────────────────────────────────────────────────────────────────┐
│              Redis Memory Optimization                               │
└─────────────────────────────────────────────────────────────────────┘

Encoding Types (automatic based on size):
┌──────────────┬────────────────────┬────────────────────────────────┐
│ Data Type    │ Small (compact)    │ Large (standard)               │
├──────────────┼────────────────────┼────────────────────────────────┤
│ String       │ int (if numeric)   │ raw/embstr                     │
│              │ embstr (≤44 bytes) │                                │
├──────────────┼────────────────────┼────────────────────────────────┤
│ List         │ listpack (≤128     │ quicklist                      │
│              │  entries, ≤64B ea) │ (linked list of ziplists)      │
├──────────────┼────────────────────┼────────────────────────────────┤
│ Hash         │ listpack (≤128     │ hashtable                      │
│              │  fields, ≤64B ea)  │                                │
├──────────────┼────────────────────┼────────────────────────────────┤
│ Set          │ intset (all ints,  │ hashtable                      │
│              │  ≤512 members)     │                                │
├──────────────┼────────────────────┼────────────────────────────────┤
│ Sorted Set   │ listpack (≤128     │ skiplist + hashtable           │
│              │  members, ≤64B ea) │                                │
└──────────────┴────────────────────┴────────────────────────────────┘

Memory Saving Tips:
1. Use hashes for small objects (hash-max-listpack-entries 128)
   Instead of: SET user:1:name "Alice", SET user:1:age "30"
   Use:        HSET user:1 name "Alice" age "30"
   Savings: ~10x less memory for many small objects

2. Use short key names: "u:1000:s" instead of "user:1000:session"

3. Use integers where possible (int encoding = 0 extra bytes)

4. Compress values client-side (snappy/lz4 for strings > 100 bytes)

5. Use Redis Streams instead of Lists for event logs (more compact)
```

---

## Production Setup

### Persistence Options

```
┌─────────────────────────────────────────────────────────────────────┐
│              Redis Persistence Comparison                            │
└─────────────────────────────────────────────────────────────────────┘

RDB (Snapshotting):
┌──────────────────────────────────────────────────────────────────┐
│  BGSAVE: fork() → child writes point-in-time snapshot to disk    │
│                                                                  │
│  Timeline:                                                       │
│  ──────────────────────────────────────────────▶                │
│  │                    │                    │                      │
│  ▼ BGSAVE            ▼ dump.rdb written   ▼ BGSAVE              │
│  T=0                 T=30s                T=300s                 │
│                                                                  │
│  ┌─────────────────────────────────────────────┐                │
│  │ Pros: Compact, fast restart, low perf impact│                │
│  │ Cons: Data loss up to save interval         │                │
│  │ Config: save 900 1  (900s if 1+ key change)│                │
│  │         save 300 10                         │                │
│  │         save 60 10000                       │                │
│  └─────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘

AOF (Append-Only File):
┌──────────────────────────────────────────────────────────────────┐
│  Every write command appended to AOF file                        │
│                                                                  │
│  Fsync policies:                                                 │
│  - always:    fsync every command (slowest, safest)             │
│  - everysec:  fsync every second (default, good balance)       │
│  - no:        OS decides when to flush (fastest, risky)        │
│                                                                  │
│  AOF Rewrite (compaction):                                       │
│  ┌─────────┐    ┌───────────────────┐    ┌─────────┐           │
│  │ AOF 5GB │───▶│ BGREWRITEAOF     │───▶│ AOF 1GB │           │
│  │ (many   │    │ (reconstruct from │    │(compact)│           │
│  │  cmds)  │    │  current state)   │    │         │           │
│  └─────────┘    └───────────────────┘    └─────────┘           │
│                                                                  │
│  ┌─────────────────────────────────────────────┐                │
│  │ Pros: Minimal data loss (1 second max)      │                │
│  │ Cons: Larger files, slower restart          │                │
│  │ Config: appendonly yes                      │                │
│  │         appendfsync everysec                │                │
│  └─────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘

Hybrid (RDB + AOF) - Recommended for Production:
┌──────────────────────────────────────────────────────────────────┐
│  aof-use-rdb-preamble yes (Redis 4.0+)                          │
│                                                                  │
│  AOF file = RDB snapshot + AOF tail                             │
│  Fast restart (load RDB) + minimal data loss (replay AOF tail) │
│                                                                  │
│  Best of both worlds                                             │
└──────────────────────────────────────────────────────────────────┘
```

### Eviction Policies

```
┌─────────────────────────────────────────────────────────────────────┐
│              Redis Eviction Policies                                 │
└─────────────────────────────────────────────────────────────────────┘

maxmemory 64gb
maxmemory-policy <policy>

┌─────────────────────┬────────────────────────────────────────────────┐
│ Policy              │ Description                                     │
├─────────────────────┼────────────────────────────────────────────────┤
│ noeviction          │ Return error on writes (default)               │
│                     │ Use for: persistent data stores                │
├─────────────────────┼────────────────────────────────────────────────┤
│ allkeys-lru         │ Evict least recently used key                  │
│                     │ Use for: general cache                         │
├─────────────────────┼────────────────────────────────────────────────┤
│ allkeys-lfu         │ Evict least frequently used (Redis 4.0+)      │
│                     │ Use for: frequency-based caching               │
├─────────────────────┼────────────────────────────────────────────────┤
│ volatile-lru        │ Evict LRU among keys WITH expire set          │
│                     │ Use for: mix of cache + persistent keys        │
├─────────────────────┼────────────────────────────────────────────────┤
│ volatile-lfu        │ Evict LFU among keys WITH expire set          │
│                     │ Use for: frequency-based among expiring keys   │
├─────────────────────┼────────────────────────────────────────────────┤
│ volatile-ttl        │ Evict keys with shortest TTL remaining         │
│                     │ Use for: time-sensitive data                    │
├─────────────────────┼────────────────────────────────────────────────┤
│ allkeys-random      │ Evict random key                               │
│                     │ Use for: uniform access patterns               │
└─────────────────────┴────────────────────────────────────────────────┘

Production Recommendation:
- Cache workload: allkeys-lfu (best hit rate)
- Mixed workload: volatile-lru (protect non-expiring keys)
- Session store: volatile-ttl (expire oldest sessions first)
```

---

## Core Concepts

### Single-Threaded Event Loop

```
┌─────────────────────────────────────────────────────────────────────┐
│              Redis Event Loop (Single Thread)                        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Main Thread                                │
│                                                              │
│    ┌──────────────────────────────────────────────────┐     │
│    │              Event Loop (ae.c)                    │     │
│    │                                                  │     │
│    │  ┌────────────────────────────────────────────┐ │     │
│    │  │ 1. epoll_wait() / kqueue()                 │ │     │
│    │  │    (wait for I/O events)                   │ │     │
│    │  └────────────────────────────────────────────┘ │     │
│    │                    │                             │     │
│    │                    ▼                             │     │
│    │  ┌────────────────────────────────────────────┐ │     │
│    │  │ 2. Process all ready file events           │ │     │
│    │  │    - Read client commands                  │ │     │
│    │  │    - Execute commands                      │ │     │
│    │  │    - Write responses                       │ │     │
│    │  └────────────────────────────────────────────┘ │     │
│    │                    │                             │     │
│    │                    ▼                             │     │
│    │  ┌────────────────────────────────────────────┐ │     │
│    │  │ 3. Process time events                     │ │     │
│    │  │    - Server cron (1ms)                     │ │     │
│    │  │    - Active expiration                     │ │     │
│    │  │    - Cluster cron                          │ │     │
│    │  └────────────────────────────────────────────┘ │     │
│    │                    │                             │     │
│    │                    └──── loop ─────────────────┘│     │
│    └──────────────────────────────────────────────────┘     │
│                                                              │
│  I/O Threads (Redis 6.0+):                                  │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                          │
│  │ IO 1│ │ IO 2│ │ IO 3│ │ IO 4│  (read/write sockets)    │
│  └─────┘ └─────┘ └─────┘ └─────┘  (command execution      │
│                                      still single-threaded) │
└─────────────────────────────────────────────────────────────┘

Why Single-Threaded Works:
- All operations are O(1) or O(log N) → microseconds each
- No lock contention
- No context switching overhead
- Bottleneck is network I/O, not CPU (solved by I/O threads in 6.0+)

Performance:
- Single thread: ~100,000-200,000 ops/sec
- With I/O threads (6.0+): ~500,000-1,000,000 ops/sec
- With pipelining: ~1,000,000+ ops/sec
- Latency: ~0.1ms (same machine), ~0.5ms (network)
```

### Redis Data Structures Internals

```
┌─────────────────────────────────────────────────────────────────────┐
│              Redis Internal Data Structures                          │
└─────────────────────────────────────────────────────────────────────┘

Skip List (used for Sorted Sets):
┌─────────────────────────────────────────────────────────────────┐
│ Level 3: HEAD ─────────────────────────────────────▶ 50 ──▶ NIL│
│ Level 2: HEAD ──────────▶ 20 ──────────▶ 40 ──────▶ 50 ──▶ NIL│
│ Level 1: HEAD ──▶ 10 ──▶ 20 ──▶ 30 ──▶ 40 ──▶ 50 ──▶ NIL    │
│                                                                  │
│ O(log N) search, insert, delete                                 │
│ Simpler than balanced trees, same complexity                    │
│ Probabilistic balancing (coin flip for level promotion)         │
└─────────────────────────────────────────────────────────────────┘

Quicklist (used for Lists):
┌─────────────────────────────────────────────────────────────────┐
│ Doubly-linked list of ziplists (compressed arrays)              │
│                                                                  │
│ ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│ │ ziplist  │◀──▶│ ziplist  │◀──▶│ ziplist  │                  │
│ │ [a,b,c]  │    │ [d,e,f]  │    │ [g,h,i]  │                  │
│ └──────────┘    └──────────┘    └──────────┘                  │
│                                                                  │
│ Each ziplist: contiguous memory, cache-friendly                 │
│ list-max-ziplist-size: -2 (8KB per ziplist)                    │
│ list-compress-depth: 1 (compress all but head/tail)            │
└─────────────────────────────────────────────────────────────────┘

SDS (Simple Dynamic String):
┌─────────────────────────────────────────────────────────────────┐
│ struct sdshdr {                                                   │
│   uint32_t len;    // used length                               │
│   uint32_t alloc;  // allocated space                           │
│   char flags;      // type (sdshdr5/8/16/32/64)                │
│   char buf[];      // actual string data                        │
│ }                                                                │
│                                                                  │
│ vs C string: O(1) length, binary-safe, no buffer overflow       │
│ Space pre-allocation: < 1MB → double, >= 1MB → +1MB            │
└─────────────────────────────────────────────────────────────────┘
```

### Pub/Sub vs Streams

```
┌─────────────────────────────────────────────────────────────────────┐
│              Pub/Sub vs Redis Streams                                │
└─────────────────────────────────────────────────────────────────────┘

Pub/Sub (fire-and-forget):
┌──────────┐  PUBLISH ch msg  ┌─────────┐  deliver  ┌──────────┐
│Publisher │────────────────▶│  Redis  │─────────▶│Subscriber│
└──────────┘                  └─────────┘          └──────────┘
                                                   ┌──────────┐
                                          ────────▶│Subscriber│
                                                   └──────────┘
- No persistence (missed if subscriber offline)
- No consumer groups
- No acknowledgment
- Use for: real-time notifications, chat, presence

Streams (persistent, acknowledgeable):
┌──────────┐  XADD stream * k v  ┌────────────────────────────┐
│Producer  │────────────────────▶│  Redis Stream              │
└──────────┘                     │  ┌───┐┌───┐┌───┐┌───┐┌───┐│
                                 │  │ 1 ││ 2 ││ 3 ││ 4 ││ 5 ││
                                 │  └───┘└───┘└───┘└───┘└───┘│
                                 └─────────────┬──────────────┘
                                               │
                              ┌─────────────────┼─────────────────┐
                              │                 │                 │
                              ▼                 ▼                 ▼
                       ┌────────────┐   ┌────────────┐   ┌────────────┐
                       │Consumer A  │   │Consumer B  │   │Consumer C  │
                       │(Group: g1) │   │(Group: g1) │   │(Group: g2) │
                       │reads 1,3,5 │   │reads 2,4   │   │reads 1-5   │
                       └────────────┘   └────────────┘   └────────────┘

- Persistent (survives restarts)
- Consumer groups (parallel processing with load balancing)
- Acknowledgment (XACK) - at-least-once delivery
- Replay from any point (XRANGE)
- Use for: event sourcing, task queues, logs, Kafka-like patterns
```
