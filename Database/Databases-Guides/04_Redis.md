# Redis - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Structures & Internals](#data-structures--internals)
3. [Memory Management](#memory-management)
4. [Persistence Mechanisms](#persistence-mechanisms)
5. [Replication & High Availability](#replication--high-availability)
6. [Redis Cluster (Sharding)](#redis-cluster-sharding)
7. [Transactions & Scripting](#transactions--scripting)
8. [Pub/Sub & Streams](#pubsub--streams)
9. [Performance Patterns](#performance-patterns)
10. [Use Case Architectures](#use-case-architectures)
11. [Staff Architect Interview Questions](#staff-architect-interview-questions)
12. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Single-Threaded Event Loop
```
┌─────────────────────────────────────────────────┐
│                 Redis Server                      │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         Event Loop (Single Thread)        │    │
│  │                                           │    │
│  │  ┌─────────┐  ┌──────────┐  ┌────────┐  │    │
│  │  │  I/O    │  │ Command  │  │ Timer  │  │    │
│  │  │Multiplex│→ │Execution │→ │Events  │  │    │
│  │  │(epoll)  │  │          │  │        │  │    │
│  │  └─────────┘  └──────────┘  └────────┘  │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         I/O Threads (Redis 6.0+)         │    │
│  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐            │    │
│  │  │ IO │ │ IO │ │ IO │ │ IO │            │    │
│  │  │ T1 │ │ T2 │ │ T3 │ │ T4 │            │    │
│  │  └────┘ └────┘ └────┘ └────┘            │    │
│  │  (Read/Write network I/O only)           │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         Background Threads                │    │
│  │  - Bio close file                         │    │
│  │  - Bio AOF fsync                          │    │
│  │  - Bio lazy free (async key deletion)     │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘

Why single-threaded works:
- All operations are O(1) or O(log N)
- No lock contention
- No context switching overhead
- Bottleneck is network I/O, not CPU
- I/O threading (6.0+) handles network read/write
- Typical throughput: 100K-500K ops/sec per instance
```

### Redis 7.x Architecture Improvements
```
- Multi-threaded I/O (reading and writing to sockets)
- Functions (server-side scripting with library support)
- Sharded Pub/Sub (cluster-aware)
- ACL v2 (command-level permissions + selectors)
- Client-side caching with tracking
- Active defragmentation improvements
- Multi-part AOF files
```

---

## Data Structures & Internals

### Core Data Types & Encodings
```
┌──────────────────┬───────────────────────────────────────┐
│ Data Type        │ Internal Encodings                      │
├──────────────────┼───────────────────────────────────────┤
│ String           │ int (if numeric ≤ LLONG_MAX)           │
│                  │ embstr (≤ 44 bytes, single allocation) │
│                  │ raw (> 44 bytes)                        │
├──────────────────┼───────────────────────────────────────┤
│ List             │ listpack (< 128 elements, < 64 bytes)  │
│                  │ quicklist (linked list of listpacks)    │
├──────────────────┼───────────────────────────────────────┤
│ Hash             │ listpack (< 128 fields, < 64 bytes)    │
│                  │ hashtable (beyond thresholds)           │
├──────────────────┼───────────────────────────────────────┤
│ Set              │ intset (all integers, < 512 elements)   │
│                  │ listpack (< 128 elements, < 64 bytes)  │
│                  │ hashtable (beyond thresholds)           │
├──────────────────┼───────────────────────────────────────┤
│ Sorted Set       │ listpack (< 128 elements, < 64 bytes)  │
│                  │ skiplist + hashtable (beyond)           │
├──────────────────┼───────────────────────────────────────┤
│ Stream           │ Radix tree of listpacks                │
├──────────────────┼───────────────────────────────────────┤
│ HyperLogLog      │ Sparse (< 3KB) or Dense (12KB fixed)  │
├──────────────────┼───────────────────────────────────────┤
│ Bitmap           │ String (SDS) with bit operations       │
├──────────────────┼───────────────────────────────────────┤
│ Geospatial       │ Sorted Set (geohash as score)         │
└──────────────────┴───────────────────────────────────────┘
```

### Skip List (Sorted Set Implementation)
```
Level 4: ─────────────────────────────────────→ [90] → NULL
Level 3: ────────────→ [30] ──────────────────→ [90] → NULL
Level 2: ──→ [10] ──→ [30] ──→ [50] ────────→ [90] → NULL
Level 1: ──→ [10] ──→ [30] ──→ [50] ──→ [70] → [90] → NULL

Properties:
- O(log N) for insert, delete, search
- O(N) for range queries (sequential at bottom level)
- Randomized levels (P=0.25 for promotion)
- Simpler than balanced trees (no rotations)
- Memory: ~34 bytes per element (score + pointer + levels)

Why not balanced tree:
- Range operations are simpler (follow forward pointers)
- Simpler implementation, similar performance
- Lock-free variants exist (important for future)
```

### SDS (Simple Dynamic String)
```c
struct sdshdr {
    uint32_t len;    // Used length
    uint32_t alloc; // Allocated length (excluding header + null term)
    unsigned char flags; // Type (sdshdr5/8/16/32/64)
    char buf[];      // Actual string data
};

// Benefits over C strings:
// - O(1) length retrieval
// - Binary safe (can contain \0)
// - Prevents buffer overflows (checks before appending)
// - Reduces reallocations (pre-allocation strategy)
// - Compatible with C string functions (null terminated)
```

### Dict (Hash Table)
```c
typedef struct dictht {
    dictEntry **table;      // Array of pointers to entries
    unsigned long size;     // Table size (power of 2)
    unsigned long sizemask; // size - 1 (for bit masking)
    unsigned long used;     // Number of entries
} dictht;

typedef struct dict {
    dictht ht[2];           // Two tables for incremental rehashing
    long rehashidx;         // -1 if not rehashing
} dict;

// Incremental rehashing:
// - When load factor > 1 (or > 5 during BGSAVE)
// - Allocate ht[1] = 2 * ht[0].size
// - Move N entries per operation (read/write/timer)
// - All lookups check both tables during rehash
// - When complete: swap ht[0] = ht[1], free old
```

---

## Memory Management

### Memory Allocation
```
Allocator: jemalloc (default), tcmalloc, libc malloc

jemalloc benefits:
- Thread-local caches
- Size classes reduce fragmentation
- Automatic arena management
- Dirty page purging

Memory info:
INFO memory
- used_memory: Total bytes allocated by Redis
- used_memory_rss: Resident set size (actual RAM from OS)
- mem_fragmentation_ratio: RSS / used_memory
  - > 1.5: Excessive fragmentation
  - < 1.0: OS swapping (very bad!)
- mem_allocator: jemalloc-5.x.x
```

### Eviction Policies
```
maxmemory-policy options:

noeviction:     Return error on write when memory limit reached (default)
allkeys-lru:    Evict least recently used keys (any key)
volatile-lru:   Evict LRU keys with TTL set
allkeys-lfu:    Evict least frequently used keys (Redis 4.0+)
volatile-lfu:   Evict LFU keys with TTL set
allkeys-random: Evict random keys
volatile-random: Evict random keys with TTL
volatile-ttl:   Evict keys with nearest expiration

LRU implementation (approximated):
- Not true LRU (too expensive: per-key linked list)
- Samples N random keys (default: maxmemory-samples = 5)
- Evicts the one with oldest access time among samples
- Increasing samples improves approximation quality

LFU implementation (Redis 4.0+):
- Morris counter (probabilistic, 8-bit logarithmic counter)
- Decays over time (lfu-decay-time, default: 1 minute)
- Better than LRU for hot/cold workloads
```

### Memory Optimization Techniques
```
1. Use appropriate encodings:
   - Short strings: embstr (44 bytes single allocation)
   - Small hashes: listpack (compact, sequential)
   - Integer sets: intset (sorted array, no pointers)

2. Hash as memory-efficient key-value store:
   Instead of: SET user:1:name "John", SET user:1:age "30"
   Use: HSET user:1 name "John" age "30"
   Savings: ~75% memory with listpack encoding

3. Shared integers:
   - Redis shares integer objects 0-9999
   - No additional memory for small integer values

4. Key naming: Keep keys short
   "user:{id}:session" vs "u:{id}:s" (saves bytes × millions of keys)

5. Compression: Use client-side compression for large values
   - Snappy/LZ4 before SET, decompress after GET

6. OBJECT ENCODING key: Check current encoding
   OBJECT FREQ key: Check LFU frequency
   MEMORY USAGE key: Check memory used by key
```

---

## Persistence Mechanisms

### RDB (Snapshotting)
```
Process:
1. Redis forks child process (COW - Copy On Write)
2. Child writes entire dataset to temp .rdb file
3. Child replaces old dump.rdb atomically (rename)
4. Parent continues serving requests

Configuration:
save 3600 1        # After 3600 seconds if >= 1 key changed
save 300 100       # After 300 seconds if >= 100 keys changed
save 60 10000      # After 60 seconds if >= 10000 keys changed

Pros:
- Compact single file (perfect for backups)
- Fast restart (direct memory load)
- Fork = background, minimal latency impact

Cons:
- Data loss between snapshots (RPO = save interval)
- Fork overhead with large datasets (COW pages)
- Latency spike during fork on large instances (10-100GB)
```

### AOF (Append Only File)
```
Process:
1. Every write command appended to AOF buffer
2. Buffer synced to disk per fsync policy
3. Background rewrite to compact AOF

fsync policies:
appendfsync always     # Safest: fsync every write (slow, RPO=0)
appendfsync everysec   # Default: fsync every second (RPO≈1s)
appendfsync no         # Fastest: OS decides when to flush (RPO=unknown)

AOF Rewrite (compaction):
- Fork child process
- Child writes minimal command set to recreate current state
- Parent accumulates new commands in rewrite buffer
- Child finishes → parent appends rewrite buffer → swap files

Multi-part AOF (Redis 7.0+):
- Base AOF file + incremental AOF files
- No more rewrite-during-rewrite issues
- Manifest file tracks all parts

Pros:
- Much better durability (up to every write)
- Human-readable format (debugging)
- Background rewrite doesn't block

Cons:
- Larger file size than RDB
- Slower restart (replays all commands)
- Potential bugs in command replay
```

### RDB + AOF Hybrid (Redis 4.0+)
```
aof-use-rdb-preamble yes

AOF rewrite produces:
[RDB binary snapshot][AOF commands since snapshot]

Benefits:
- Fast loading (RDB portion)
- Low data loss (AOF portion)
- Best of both worlds
- Default in Redis 7.0+
```

---

## Replication & High Availability

### Master-Replica Replication
```
┌──────────┐    Full sync (first time)     ┌──────────┐
│  Master  │ ─────────────────────────────→ │ Replica  │
│          │    Partial sync (reconnect)    │          │
│          │ ─────────────────────────────→ │          │
│          │    Replication stream          │          │
│          │ ─────────────────────────────→ │          │
└──────────┘                               └──────────┘

Full synchronization (initial):
1. Replica connects, sends PSYNC ? -1
2. Master starts BGSAVE (RDB snapshot)
3. Master buffers all new writes in replication buffer
4. Master sends RDB to replica
5. Replica loads RDB (flushes old data)
6. Master sends buffered writes
7. Ongoing: Master streams all writes to replica

Partial resynchronization (reconnect):
1. Replica sends PSYNC <repl_id> <offset>
2. Master checks replication backlog buffer
3. If offset still in buffer → send missing commands
4. Otherwise → full resync required

Replication backlog:
- Circular buffer on master
- Default: 1MB (increase for unstable networks)
- repl-backlog-size 256mb
```

### Redis Sentinel (HA)
```
┌─────────────────────────────────────────────────┐
│              Sentinel Cluster (3+ nodes)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Sentinel 1│  │Sentinel 2│  │Sentinel 3│      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │              │              │            │
│       └──────────────┼──────────────┘            │
│                      │ Monitoring                 │
└──────────────────────┼───────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  Master  │  │ Replica1 │  │ Replica2 │
   └──────────┘  └──────────┘  └──────────┘

Failover process:
1. Subjective Down (SDOWN): Single sentinel can't reach master
2. Objective Down (ODOWN): Quorum of sentinels agree master is down
   - quorum: Minimum sentinels needed to agree (typically 2 of 3)
3. Leader election: Sentinels elect a leader (Raft-like)
4. Leader selects best replica:
   - Highest priority (replica-priority)
   - Most replication offset (most data)
   - Smallest run ID (tiebreaker)
5. Promote replica to master
6. Reconfigure other replicas to follow new master
7. Update clients via Sentinel protocol

Client integration:
- Client connects to Sentinel, asks for master address
- Sentinel pushes notifications on topology changes
- Client re-resolves on connection errors

Typical failover time: 5-30 seconds
```

---

## Redis Cluster (Sharding)

### Cluster Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Redis Cluster                          │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Node A (Master) │  │ Node B (Master) │              │
│  │ Slots: 0-5460   │  │ Slots: 5461-10922│             │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │             │
│  │ │ Replica A1  │ │  │ │ Replica B1  │ │             │
│  │ └─────────────┘ │  │ └─────────────┘ │             │
│  └─────────────────┘  └─────────────────┘              │
│                                                          │
│  ┌─────────────────┐                                    │
│  │ Node C (Master) │                                    │
│  │ Slots: 10923-16383│                                  │
│  │ ┌─────────────┐ │                                    │
│  │ │ Replica C1  │ │                                    │
│  │ └─────────────┘ │                                    │
│  └─────────────────┘                                    │
│                                                          │
│  Gossip Protocol: Every node knows every other node      │
│  Heartbeat: Every 1 second to random nodes              │
└─────────────────────────────────────────────────────────┘

Hash Slots: 16384 total slots
Key → Slot: CRC16(key) % 16384
Hash Tags: {user:123}:name → CRC16("user:123") ensures co-location
```

### Cluster Operations
```
Key routing:
1. Client computes: slot = CRC16(key) % 16384
2. Client maintains slot → node mapping (cached)
3. Sends command to correct node

MOVED redirect (slot permanently moved):
Client → Node A: GET key1
Node A → Client: -MOVED 3999 192.168.1.2:6379
Client updates slot mapping, retries to Node B

ASK redirect (slot being migrated):
Client → Node A: GET key1
Node A → Client: -ASK 3999 192.168.1.2:6379
Client sends ASKING + command to Node B (one-time)

Resharding (slot migration):
1. CLUSTER SETSLOT <slot> MIGRATING <dest-node-id> (on source)
2. CLUSTER SETSLOT <slot> IMPORTING <source-node-id> (on dest)
3. CLUSTER GETKEYSINSLOT <slot> <count> (get keys to move)
4. MIGRATE <dest-host> <port> <key> 0 <timeout> (move each key)
5. CLUSTER SETSLOT <slot> NODE <dest-node-id> (finalize on all nodes)
```

### Multi-Key Operations in Cluster
```
Limitation: All keys in a multi-key command must be in same slot

Solutions:
1. Hash Tags: Force same slot
   SET {order:123}:status "pending"
   SET {order:123}:total "99.99"
   MGET {order:123}:status {order:123}:total  # Same slot!

2. Client-side aggregation:
   - Split keys by slot
   - Send parallel commands to each node
   - Aggregate results client-side

3. Lua scripting with hash tags:
   EVAL "return redis.call('MGET', KEYS[1], KEYS[2])" 2 {user}:a {user}:b

Commands NOT supported in cluster:
- KEYS (use SCAN per node)
- Multi-key commands across slots without hash tags
- Database selection (only DB 0)
- Certain blocking commands across nodes
```

### Cluster Failure Detection
```
Failure detection via gossip:
1. Node A pings Node B, no response within cluster-node-timeout
2. Node A marks B as PFAIL (possible failure)
3. Node A gossips PFAIL to other nodes
4. If majority of masters report PFAIL → FAIL status
5. If B is master → replica failover begins

Replica failover:
1. Replica of failed master detects FAIL
2. Replica increments currentEpoch
3. Replica requests votes from other masters
4. Masters vote based on:
   - Replication offset (most data wins)
   - No other vote in same epoch
5. Majority votes → replica promoted
6. New master announces via PONG with new config epoch

Split-brain protection:
- cluster-require-full-coverage: Cluster stops accepting writes if slot uncovered
- Minority partition masters stop accepting writes
- cluster-node-timeout: Balance between fast detection and network glitches
```

---

## Transactions & Scripting

### MULTI/EXEC (Optimistic Transactions)
```
MULTI
SET balance:alice 500
SET balance:bob 300
EXEC
# All commands executed atomically (no interleaving)
# But: No rollback on individual command failure!

WATCH (Optimistic Locking):
WATCH balance:alice
val = GET balance:alice  # 1000
MULTI
SET balance:alice (val - 100)
SET balance:bob (bob + 100)
EXEC  # Returns nil if balance:alice was modified since WATCH
# Retry on nil (compare-and-swap pattern)
```

### Lua Scripting
```lua
-- Atomic rate limiter
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, window)
end

if current > limit then
    return 0  -- Rate limited
else
    return 1  -- Allowed
end

-- Execute:
EVAL "..." 1 "rate:user:123" 100 60

-- Properties:
-- Atomic: No other command runs during script
-- Replicated: Script sent to replicas
-- Deterministic: Same inputs → same outputs (required)
-- Timeout: lua-time-limit 5000 (ms, default)
```

### Redis Functions (Redis 7.0+)
```lua
-- Register a library with functions
#!lua name=mylib

local function my_hset(keys, args)
    local hash = keys[1]
    local time = redis.call('TIME')
    redis.call('HSET', hash, 'updated_at', time[1])
    for i = 1, #args, 2 do
        redis.call('HSET', hash, args[i], args[i+1])
    end
    return redis.call('HGETALL', hash)
end

redis.register_function('my_hset', my_hset)

-- Call:
FCALL my_hset 1 user:123 name "John" age "30"

-- Benefits over EVAL:
-- Persistent (survive restart)
-- Named (no SHA tracking)
-- Library organization
-- Better for operational management
```

---

## Pub/Sub & Streams

### Redis Streams (Kafka-like)
```
Producer:
XADD mystream * sensor_id s1 temperature 22.5 timestamp 1706000000
# Returns: "1706000000000-0" (auto-generated ID)

Consumer Group:
XGROUP CREATE mystream mygroup $ MKSTREAM
# Create consumer group starting from latest

Consumer:
XREADGROUP GROUP mygroup consumer1 COUNT 10 BLOCK 2000 STREAMS mystream >
# Read pending messages, block up to 2000ms

Acknowledge:
XACK mystream mygroup "1706000000000-0"
# Message processed, won't be re-delivered

Claim stale messages:
XAUTOCLAIM mystream mygroup consumer2 3600000 0-0 COUNT 10
# Claim messages idle > 1 hour from dead consumers

Stream structure:
┌────────────────────────────────────────────────────┐
│ Stream: mystream                                    │
│                                                     │
│ Radix Tree (message IDs → entries):                │
│ ├── 1706000000000-0: {sensor_id: s1, temp: 22.5}  │
│ ├── 1706000000001-0: {sensor_id: s2, temp: 23.1}  │
│ └── 1706000000002-0: {sensor_id: s1, temp: 22.8}  │
│                                                     │
│ Consumer Groups:                                    │
│ ├── mygroup (last_delivered: 1706000000002-0)       │
│ │   ├── consumer1: PEL [1706000000000-0]           │
│ │   └── consumer2: PEL [1706000000001-0]           │
│ └── analytics (last_delivered: 1706000000001-0)     │
│     └── worker1: PEL []                             │
└────────────────────────────────────────────────────┘

PEL = Pending Entries List (unacknowledged messages)
```

### Streams vs Kafka Comparison
```
| Feature | Redis Streams | Kafka |
|---------|--------------|-------|
| Persistence | In-memory + AOF/RDB | Disk-first |
| Throughput | ~1M msg/s (single node) | ~1M msg/s (per partition) |
| Retention | Memory-limited (MAXLEN/MINID) | Time/size based (cheap) |
| Consumer groups | Yes | Yes |
| Message replay | Yes (by ID) | Yes (by offset) |
| Ordering | Per-stream (total order) | Per-partition |
| Partitioning | Hash tags in cluster | Native partitions |
| Use case | Real-time, bounded retention | Event sourcing, long retention |
```

---

## Performance Patterns

### Pipelining
```
Without pipelining (RTT per command):
Client: SET a 1 → Server: OK (RTT)
Client: SET b 2 → Server: OK (RTT)
Client: SET c 3 → Server: OK (RTT)
Total: 3 * RTT

With pipelining (batch):
Client: SET a 1\r\nSET b 2\r\nSET c 3 → Server: OK\r\nOK\r\nOK (1 RTT)
Total: 1 * RTT

Impact: 5-10x throughput improvement over high-latency networks
Typical batch size: 50-1000 commands
```

### Client-Side Caching (Redis 6.0+)
```
Tracking mode:
CLIENT TRACKING ON REDIRECT <client-id>

1. Client GETs key → caches locally
2. Redis tracks which client cached which keys
3. When key modified → Redis sends invalidation to client
4. Client evicts from local cache

Modes:
- Default: Server tracks exact keys per client
- Broadcasting: Client subscribes to key prefixes
  CLIENT TRACKING ON BCAST PREFIX user: PREFIX session:
- OPTIN: Only track keys after CLIENT CACHING YES

Benefits:
- Eliminates network round-trip for hot keys
- Sub-microsecond reads from local memory
- Automatic invalidation (consistency)
```

### Connection Pooling Best Practices
```
Pool sizing:
- connections = operations_per_second * avg_latency_seconds
- Typical: 10-50 connections per application instance
- Redis handles 10K+ concurrent connections easily

Multiplexing:
- Use client libraries with multiplexing (Lettuce, ioredis)
- Single connection handles multiple concurrent requests
- Reduces connection overhead

Keep-alive:
- TCP keepalive: tcp-keepalive 300 (seconds)
- Client timeout: timeout 300
- Detect dead connections early
```

---

## Use Case Architectures

### Distributed Rate Limiter
```
Sliding Window Log:
ZADD ratelimit:user:123 <timestamp> <unique_id>
ZREMRANGEBYSCORE ratelimit:user:123 0 <timestamp - window>
count = ZCARD ratelimit:user:123
if count >= limit: REJECT

Sliding Window Counter (memory efficient):
-- Lua script for atomic sliding window
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now .. math.random())
    redis.call('EXPIRE', key, window)
    return 1
end
return 0

Token Bucket (high performance):
local key = KEYS[1]
local rate = tonumber(ARGV[1])        -- tokens per second
local capacity = tonumber(ARGV[2])    -- bucket size
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, capacity / rate * 2)
    return 1
end
return 0
```

### Distributed Lock (Redlock)
```
Single instance lock:
SET lock:resource <unique_value> NX PX 30000
# NX = only if not exists
# PX = expire in 30000ms

Release (Lua for atomicity):
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0

Redlock algorithm (distributed, controversial):
1. Get current time T1
2. Try to acquire lock on N (5) independent Redis instances
3. Lock acquired if:
   - Majority (3+) instances grant lock
   - Total time < lock TTL
4. Effective TTL = initial_TTL - (T2 - T1)
5. If failed: Release lock on all instances

Criticism (Martin Kleppmann):
- Clock drift between nodes
- Process pause (GC) can extend past TTL
- Network delays can cause split decisions
- Use fencing tokens for true safety

Better alternative: Use coordination service (etcd, ZooKeeper) for critical locks
Redis locks: Good for efficiency (avoid thundering herd), not safety
```

### Session Store
```
Session per user:
HSET session:<session_id> user_id 123 role admin ip "1.2.3.4" created_at 1706000000
EXPIRE session:<session_id> 3600

Lookup:
HGETALL session:<session_id>

Benefits:
- Sub-millisecond access
- Automatic TTL-based expiration
- Atomic updates (HSET)
- Scales to millions of concurrent sessions
- Cluster mode: Hash tag {session:abc} for multi-key ops
```

### Leaderboard
```
Real-time leaderboard:
ZADD leaderboard <score> <user_id>
ZINCRBY leaderboard <increment> <user_id>

Top 10:
ZREVRANGE leaderboard 0 9 WITHSCORES

User rank:
ZREVRANK leaderboard <user_id>

Around-me (nearby players):
rank = ZREVRANK leaderboard <user_id>
ZREVRANGE leaderboard (rank-5) (rank+5) WITHSCORES

Multiple leaderboards (composite):
ZADD daily:2024-01-15 <score> <user_id>
ZADD weekly:2024-W03 <score> <user_id>
ZUNIONSTORE monthly:2024-01 2 weekly:2024-W01 weekly:2024-W02

Scale: Sorted set handles 100M+ members efficiently
```

### Caching Patterns
```
Cache-Aside (Lazy Loading):
1. Check cache: GET key
2. If miss: Query database
3. Store in cache: SET key value EX 3600
4. Return value

Write-Through:
1. Write to database
2. Write to cache: SET key value EX 3600
3. Return success

Write-Behind (Write-Back):
1. Write to cache: SET key value
2. Background worker writes to database (batched)
3. Risk: Data loss if Redis crashes before flush

Cache Stampede Prevention:
- Probabilistic early expiration:
  remaining_ttl = TTL(key)
  if remaining_ttl - (random * beta * compute_time) <= 0:
      recompute_and_set()
      
- Mutex lock:
  if not cache_hit:
      if SETNX lock:key 1:
          value = compute()
          SET key value EX 3600
          DEL lock:key
      else:
          wait and retry
```

---

## Staff Architect Interview Questions

**Q1: Redis is single-threaded. How does it achieve 100K+ ops/sec?**
**A:** 
- All data in memory (no disk I/O for reads)
- O(1) and O(log N) data structures (hash tables, skip lists)
- I/O multiplexing (epoll/kqueue) handles thousands of connections
- No context switching or lock contention
- Efficient memory access patterns (cache-friendly)
- Since Redis 6.0: I/O threads for network read/write (still single-threaded for command execution)
- Pipelining eliminates per-command RTT overhead
- Bottleneck is typically network bandwidth, not CPU

**Q2: Compare Redis Cluster vs Redis Sentinel. When to use each?**
**A:**
| Aspect | Sentinel | Cluster |
|--------|----------|---------|
| Purpose | HA (failover) | HA + Sharding |
| Data model | Full dataset on each node | Data partitioned across nodes |
| Scaling | Vertical (single node limit) | Horizontal (add nodes) |
| Multi-key | Full support | Only with hash tags (same slot) |
| Complexity | Simpler | More complex |
| Use when | Data fits in one node | Data exceeds single node |
| Max dataset | ~25-50GB effective | ~100s of GB distributed |

**Q3: How would you handle Redis as a primary data store (not just cache)?**
**A:**
- Enable AOF with `appendfsync everysec` minimum (or `always` for zero-loss)
- Use RDB+AOF hybrid persistence
- Configure replicas with `replica-serve-stale-data no`
- Implement application-level backup (periodic RDB to S3)
- Use Lua scripts for complex atomic operations
- Monitor memory fragmentation and replication lag
- Design for Redis failure (circuit breaker, degraded mode)
- Consider Redis Enterprise for active-active geo-replication

**Q4: Explain the split-brain problem in Redis Sentinel and how to mitigate it.**
**A:**
Split-brain occurs when network partition isolates master from sentinels:
- Sentinels promote replica to new master
- Old master still accepts writes (clients still connected to it)
- Data divergence occurs
- When partition heals, old master becomes replica (loses those writes!)

Mitigation:
```
min-replicas-to-write 1     # Master refuses writes if < 1 replica connected
min-replicas-max-lag 10     # Replica must have acked within 10 seconds
```
This makes the isolated old master reject writes (reduces data loss window).

**Q5: Design a distributed cache warming strategy for a Redis cluster.**
**A:**
1. **Predictive warming**: Analyze access patterns, pre-load expected hot keys
2. **Pipeline-based bulk load**: Use Redis protocol to bulk-insert from backup
3. **Gradual warming**: Route increasing traffic percentage to new instance
4. **Dual-read pattern**: Read from both old cache and new; populate new on miss
5. **Snapshot-based**: Load RDB from replica of old cluster
6. **Priority-based**: Warm most accessed keys first (from access logs)
7. **Key-space notification**: Subscribe to invalidations, repopulate proactively

---

## Scenario-Based Questions

### Scenario 1: Redis Memory Suddenly Full

**Problem:** Production Redis reaches maxmemory, clients getting OOM errors.

**Immediate response:**
```bash
# 1. Check what's using memory
redis-cli INFO memory
redis-cli MEMORY STATS

# 2. Find biggest keys
redis-cli --bigkeys
redis-cli MEMORY USAGE suspicious_key

# 3. Check for memory fragmentation
# mem_fragmentation_ratio > 1.5 means fragmentation issue
# Solution: Enable active defrag
CONFIG SET activedefrag yes

# 4. Quick relief: Increase maxmemory temporarily
CONFIG SET maxmemory 20gb

# 5. Find unexpected key patterns
redis-cli --scan --pattern "debug:*" | head -100
# Delete with UNLINK (async) not DEL (blocking)
redis-cli UNLINK debug:key1 debug:key2

# 6. Check for key explosion (TTL not set)
redis-cli --scan | while read key; do 
    ttl=$(redis-cli TTL "$key")
    if [ "$ttl" -eq "-1" ]; then echo "$key"; fi
done | head -50
```

**Root cause investigation:**
- Missing TTL on cached keys (memory leak)
- Unbounded data structures (lists/streams growing forever)
- Memory fragmentation (many small deletions)
- Suddenly hot workload creating many new keys

### Scenario 2: Design Real-Time Analytics Dashboard

**Requirements:** 100M events/day, sub-second dashboard refresh, 7-day retention.

**Architecture:**
```
Event Sources → Kafka → Stream Processor → Redis

Redis data model:
1. Real-time counters (HyperLogLog for unique counts):
   PFADD page:views:2024-01-15:homepage <user_id>
   PFCOUNT page:views:2024-01-15:homepage  # ~0.81% error

2. Time-series (Sorted Sets):
   ZADD ts:pageviews:homepage <timestamp> <count_in_window>
   ZRANGEBYSCORE ts:pageviews:homepage <start> <end>

3. Top-N (Sorted Sets):
   ZINCRBY top:pages:2024-01-15 1 "/products/widget"
   ZREVRANGE top:pages:2024-01-15 0 9 WITHSCORES

4. Aggregated metrics (Hashes):
   HINCRBY metrics:2024-01-15:13 pageviews 1
   HINCRBY metrics:2024-01-15:13 unique_users 1
   HINCRBYFLOAT metrics:2024-01-15:13 revenue 29.99

5. Bitmap for daily active users:
   SETBIT dau:2024-01-15 <user_id_int> 1
   BITCOUNT dau:2024-01-15

TTL strategy:
- Hourly keys: EXPIRE 25h (overlap for queries)
- Daily keys: EXPIRE 8d
- Use Redis Cluster for capacity (shard by metric prefix)

Estimated memory:
- 100M events × 50 bytes avg = 5GB raw
- With aggregation: ~500MB-1GB in Redis
- HyperLogLog: 12KB per counter (millions of uniques)
```

### Scenario 3: Preventing Cache Stampede (Thundering Herd)

**Problem:** Popular cache key expires, 10K requests simultaneously hit database.

**Solutions:**
```lua
-- Solution 1: Probabilistic Early Expiration (XFetch)
-- Recompute before expiry based on probability
local key = KEYS[1]
local data = redis.call('GET', key)
local ttl = redis.call('TTL', key)
local delta = tonumber(ARGV[1])  -- compute time estimate
local beta = tonumber(ARGV[2])   -- typically 1.0

if data and ttl > 0 then
    -- Probabilistic early recomputation
    local random = math.random()
    local threshold = delta * beta * math.log(random)
    if ttl + threshold > 0 then
        return data  -- Use cached value
    end
end
-- Cache miss or early recompute triggered
return nil  -- Caller should recompute

-- Solution 2: Mutex/Singleflight
local lock_key = "lock:" .. KEYS[1]
local locked = redis.call('SET', lock_key, '1', 'NX', 'PX', '5000')
if locked then
    return nil  -- This caller computes and sets cache
else
    -- Wait and read (other caller is computing)
    return "WAIT"
end

-- Solution 3: Stale-While-Revalidate
-- Store with extra metadata
SET key '{"data":"...","expire":1706003600,"stale":1706007200}'
-- Serve stale data while one request recomputes
```

### Scenario 4: Redis Cluster Rolling Upgrade

**Steps for zero-downtime upgrade (6.x → 7.x):**
```
1. Prerequisites:
   - Ensure cluster is healthy: CLUSTER INFO
   - All nodes in "ok" state
   - No ongoing resharding
   - Replicas fully synced

2. Upgrade replicas first (one at a time):
   a. CLUSTER FAILOVER on replica's master (make it primary if needed, skip)
   b. Stop replica
   c. Upgrade binary
   d. Start with new version
   e. Wait for sync: CLUSTER NODES (verify "connected")
   f. Verify: INFO server (check version)

3. Failover masters to upgraded replicas:
   a. On upgraded replica: CLUSTER FAILOVER
   b. Wait for role change
   c. Now old master is replica (old version)

4. Upgrade remaining nodes (now replicas):
   a. Stop node
   b. Upgrade binary
   c. Start
   d. Verify sync

5. Verification:
   - CLUSTER INFO on all nodes
   - Check all slots covered
   - Test read/write operations
   - Monitor for errors in application logs

6. Rollback plan:
   - Keep old binaries available
   - If issues: CLUSTER FAILOVER back to old-version nodes
   - Redis protocol is backward compatible between minor versions
```

---

## Redis at Scale - Key Metrics to Monitor

```
1. Memory:
   - used_memory vs maxmemory (< 80%)
   - mem_fragmentation_ratio (1.0-1.5 ideal)
   - evicted_keys (should be 0 unless intended)

2. Performance:
   - instantaneous_ops_per_sec
   - latency percentiles (redis-cli --latency-history)
   - slowlog (SLOWLOG GET 10)

3. Connections:
   - connected_clients vs maxclients
   - rejected_connections (should be 0)
   - blocked_clients

4. Persistence:
   - rdb_last_bgsave_status
   - aof_last_bgrewrite_status
   - rdb_last_bgsave_time_sec (long = fork overhead)

5. Replication:
   - master_link_status (up)
   - master_last_io_seconds_ago (< 10)
   - repl_backlog_size vs data volume

6. Cluster:
   - cluster_state (ok)
   - cluster_slots_ok (16384)
   - cluster_known_nodes
```

