# Design a Distributed Cache (Like Redis/Memcached)

## 1. Functional Requirements

- **Key-Value Storage**: Store and retrieve data by string keys with support for multiple data types (String, Hash, List, Set, Sorted Set, Stream)
- **TTL/Expiration**: Set time-to-live on keys; automatic expiry with both lazy and active deletion
- **Eviction Policies**: LRU, LFU, Random, TTL-based eviction when memory is full
- **Atomic Operations**: Increment/decrement, compare-and-swap (CAS), SETNX (set if not exists)
- **Pub/Sub Messaging**: Publish messages to channels; subscribers receive in real-time
- **Transactions**: Multi-command atomic execution (MULTI/EXEC) with optimistic locking (WATCH)
- **Lua Scripting**: Execute server-side scripts atomically (complex operations without round-trips)
- **Data Structures**: Bitmaps, HyperLogLog (cardinality estimation), Geospatial indexes, Streams
- **Persistence**: Optional RDB snapshots and AOF (Append-Only File) for durability
- **Replication**: Master-replica replication for read scaling and high availability
- **Clustering**: Automatic data partitioning across multiple nodes using hash slots
- **Pipeline**: Batch multiple commands in a single network round-trip
- **Scan/Iteration**: Non-blocking cursor-based iteration over keys (no KEYS blocking)
- **Memory Optimization**: Memory-efficient encodings (ziplist, intset, quicklist)
- **Client-Side Caching**: Server-assisted invalidation for client-local caches
- **Access Control**: Authentication, ACLs (per-user command/key restrictions)
- **Cluster Management**: Add/remove nodes, rebalance slots, online resharding

## 2. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| **Availability** | 99.99% with clustering and automatic failover |
| **Latency** | p50 < 0.5ms, p99 < 2ms (single node, local network) |
| **Throughput** | 100K-1M operations/sec per node (depending on command complexity) |
| **Scalability** | Horizontal: 1000+ nodes in a cluster; Vertical: up to 1 TB RAM per node |
| **Durability** | Configurable: none (pure cache), async (AOF every second), sync (fsync every write) |
| **Consistency** | Eventually consistent replicas; strong consistency for single-master writes |
| **Failover** | Automatic master failover within 15 seconds |
| **Memory Efficiency** | < 10% overhead vs raw data size for optimized data structures |
| **Network** | Support 10K+ concurrent client connections per node |
| **Partition Tolerance** | Split-brain protection; minimum quorum for writes during partitions |

## 3. Capacity Estimation

### Assumptions
| Dimension | Value |
|-----------|-------|
| Total data stored | 10 TB across cluster |
| Number of keys | 5 billion |
| Average key size | 50 bytes |
| Average value size | 500 bytes |
| Read:Write ratio | 80:20 |
| Peak operations/sec | 10 million ops/sec (cluster-wide) |
| Number of clients | 50,000 concurrent connections |
| Cluster nodes | 100 masters + 100 replicas |
| Replication factor | 1 master + 1 replica (configurable up to 3) |

### QPS/RPS Calculation
```
Total peak OPS: 10 million ops/sec
Read OPS: 8M/sec (80%)
Write OPS: 2M/sec (20%)
Per-node OPS: 10M / 100 masters = 100K ops/sec per master
Per-node with replica reads: 50K writes + 80K reads = masters handle writes + some reads

Pipeline effectiveness: 10 commands/pipeline × 100K connections = effective 1M logical ops/pipeline batch
```

### Storage Estimation
```
Key storage: 5B keys × 50 bytes = 250 GB (just keys)
Value storage: 5B keys × 500 bytes = 2.5 TB (just values)
Metadata overhead: ~100 bytes/key (TTL, encoding, LRU clock, pointers) = 500 GB
Total per-node: 10 TB / 100 nodes = 100 GB per master node + 30% overhead = 130 GB RAM per node

Hash slot distribution: 16,384 slots / 100 nodes = ~164 slots per node
Keys per slot: 5B / 16,384 = ~305K keys per slot

Replication bandwidth: 2M writes/sec × 600 bytes avg = 1.2 GB/s total replication traffic
Per-replica: 1.2 GB/s / 100 = 12 MB/s per replica (manageable)
```

### Network Bandwidth
```
Client → Cache reads: 8M/sec × 550 bytes (key + value) = 4.4 GB/s = 35.2 Gbps
Client → Cache writes: 2M/sec × 600 bytes = 1.2 GB/s = 9.6 Gbps
Replication traffic: 12 MB/s per node = 1.2 GB/s aggregate
Cluster gossip: negligible (heartbeats every 1s, ~200 bytes)
Per-node network: 44.8 Gbps / 100 nodes = ~450 Mbps per node (fits in 10 GbE)
```

### Infrastructure Sizing
```
Master nodes: 100 × (128 GB RAM, 4-core CPU, 1 TB NVMe SSD for persistence, 10 GbE)
Replica nodes: 100 × (128 GB RAM, 4-core CPU, 1 TB NVMe SSD, 10 GbE)
Sentinel/Coordinator: 3-5 nodes (for cluster management)
Proxy layer (optional): 20 nodes for client connection pooling
Monitoring: 3 Prometheus + Grafana nodes
```

## 4. Data Modeling

### Internal Data Structures

#### Core Hash Table (Main Key Space)
```c
// Global hash table (dictionary)
typedef struct dictEntry {
    void *key;              // SDS (Simple Dynamic String)
    union {
        void *val;          // Pointer to value object
        uint64_t u64;       // For integer values (no allocation)
        int64_t s64;
        double d;
    } v;
    struct dictEntry *next; // Chaining for collision
} dictEntry;

typedef struct dict {
    dictEntry **table;      // Hash table array
    unsigned long size;     // Table size (power of 2)
    unsigned long sizemask; // size - 1 (for modulo via AND)
    unsigned long used;     // Number of entries
} dict;

// Two hash tables for incremental rehashing
typedef struct dictht {
    dict ht[2];             // ht[0] = active, ht[1] = rehashing target
    long rehashidx;         // -1 if not rehashing, else current index
} dictht;
```

#### Value Object Encoding
```c
typedef struct redisObject {
    unsigned type:4;        // STRING, LIST, SET, ZSET, HASH, STREAM
    unsigned encoding:4;    // RAW, INT, EMBSTR, ZIPLIST, SKIPLIST, INTSET, HT, QUICKLIST
    unsigned lru:24;        // LRU clock (or LFU: 8-bit frequency + 16-bit decay time)
    int refcount;           // Reference counting for memory management
    void *ptr;              // Pointer to actual data structure
} robj;

// Encoding selection (memory optimization):
// STRING:
//   - INT: if value fits in long (saves ~40 bytes vs SDS)
//   - EMBSTR: if len <= 44 bytes (single allocation for object + SDS)
//   - RAW: for longer strings (separate allocation)
// LIST:
//   - QUICKLIST: doubly-linked list of ziplists (default)
//   - ZIPLIST: if elements < 128 AND all elements < 64 bytes
// HASH:
//   - ZIPLIST: if fields < 128 AND all values < 64 bytes
//   - HASHTABLE: otherwise (O(1) lookup but more memory)
// SET:
//   - INTSET: if all elements are integers AND count < 512
//   - HASHTABLE: otherwise
// SORTED SET:
//   - ZIPLIST: if elements < 128 AND all < 64 bytes
//   - SKIPLIST + HASHTABLE: otherwise (O(log n) range + O(1) score lookup)
```

#### Hash Slot Mapping (Cluster Mode)
```
Total slots: 16,384 (2^14)
Slot assignment: CRC16(key) mod 16384

Hash tag support: 
  Key "user:{12345}:profile" → CRC16("12345") → ensures co-location
  Only content between first { and first } is hashed

Slot distribution:
  Node A: slots 0-5460 (33%)
  Node B: slots 5461-10922 (33%)
  Node C: slots 10923-16383 (34%)
  
  Migration: move slots between nodes for rebalancing
  During migration: ASK redirect for migrating keys
```

#### Schema for Cluster Metadata (Gossip Protocol)
```c
typedef struct clusterNode {
    char name[40];              // Node ID (SHA-1 hex)
    int flags;                  // MASTER, SLAVE, PFAIL, FAIL, HANDSHAKE
    uint64_t configEpoch;      // Current config epoch for failover
    char ip[46];               // Node IP address
    int port;                  // Client port
    int cport;                 // Cluster bus port
    clusterNode *slaveof;      // Master pointer (if this is a replica)
    unsigned char slots[16384/8]; // Bitmap of owned slots (2 KB)
    int numslots;              // Number of slots owned
    int numslaves;             // Number of replicas
    clusterNode **slaves;      // Array of replica pointers
    mstime_t ping_sent;        // Last ping sent timestamp
    mstime_t pong_received;    // Last pong received timestamp
    mstime_t fail_time;        // Time of FAIL flag set
    mstime_t voted_time;       // Last failover vote time
    mstime_t repl_offset_time;
    long long repl_offset;     // Replication offset
    int orphaned_time;         // Time since master with no replica
} clusterNode;
```

### Persistence Models

#### RDB (Snapshot)
```
Binary format: Magic + version + DB selections + key-value pairs + EOF + checksum
Trigger: BGSAVE (background fork) or SAVE (blocking) or automatic (config-based)

Auto-save configuration:
  save 900 1      # After 900 sec if at least 1 key changed
  save 300 10     # After 300 sec if at least 10 keys changed
  save 60 10000   # After 60 sec if at least 10000 keys changed

COW (Copy-On-Write) via fork():
  - Parent continues serving requests
  - Child writes snapshot to temp file
  - Rename temp → dump.rdb (atomic)
  - Memory overhead: only modified pages duplicated (~10-30% during save)
```

#### AOF (Append-Only File)
```
Format: Redis protocol commands (human-readable)
  *3\r\n$3\r\nSET\r\n$5\r\nhello\r\n$5\r\nworld\r\n

Fsync policies:
  - always: fsync after every write (safest, slowest)
  - everysec: fsync every second (good balance, max 1s data loss)
  - no: let OS decide (fastest, up to 30s data loss)

AOF rewrite (compaction):
  - Background process creates new AOF with current state
  - During rewrite: new commands buffered and appended
  - Atomic rename when complete
  - Reduces AOF size by 50-90% (eliminates expired keys, overwritten values)
```

## 5. High-Level Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION CLIENTS                                 │
│  (Microservices, Web Apps, Background Workers, ML Pipelines)                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CLIENT LIBRARIES / PROXY                               │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │ Smart Client │  │ Connection   │  │ Proxy Layer  │                     │
│  │ (Cluster-    │  │ Pool Manager │  │ (Optional:   │                     │
│  │  aware,      │  │              │  │  Twemproxy/  │                     │
│  │  slot map    │  │ Max: 50K     │  │  Envoy)      │                     │
│  │  cached)     │  │ Per-node: 500│  │              │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│                                                                              │
│  Features: Auto-discovery, slot redirection handling, read-from-replica,    │
│           pipeline support, retry with backoff, circuit breaker             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CACHE CLUSTER                                         │
│                                                                              │
│  Shard 1 (Slots 0-5460)    Shard 2 (Slots 5461-10922)   Shard N (...)     │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐│
│  │  ┌───────────────┐  │  │  ┌───────────────┐  │  │  ┌───────────────┐  ││
│  │  │    MASTER      │  │  │  │    MASTER      │  │  │  │    MASTER      │  ││
│  │  │   Node A       │  │  │  │   Node B       │  │  │  │   Node N       │  ││
│  │  │   128 GB RAM   │  │  │  │   128 GB RAM   │  │  │  │   128 GB RAM   │  ││
│  │  │                 │  │  │  │                 │  │  │  │                 │  ││
│  │  │ ┌─────────────┐│  │  │  │ ┌─────────────┐│  │  │  │ ┌─────────────┐│  ││
│  │  │ │ Event Loop  ││  │  │  │ │ Event Loop  ││  │  │  │ │ Event Loop  ││  ││
│  │  │ │ (Single-    ││  │  │  │ │ (Single-    ││  │  │  │ │ (Single-    ││  ││
│  │  │ │  threaded)  ││  │  │  │ │  threaded)  ││  │  │  │ │  threaded)  ││  ││
│  │  │ ├─────────────┤│  │  │  │ ├─────────────┤│  │  │  │ ├─────────────┤│  ││
│  │  │ │ Hash Table  ││  │  │  │ │ Hash Table  ││  │  │  │ │ Hash Table  ││  ││
│  │  │ │ (Key Space) ││  │  │  │ │ (Key Space) ││  │  │  │ │ (Key Space) ││  ││
│  │  │ ├─────────────┤│  │  │  │ ├─────────────┤│  │  │  │ ├─────────────┤│  ││
│  │  │ │ Expiry Dict ││  │  │  │ │ Expiry Dict ││  │  │  │ │ Expiry Dict ││  ││
│  │  │ ├─────────────┤│  │  │  │ ├─────────────┤│  │  │  │ ├─────────────┤│  ││
│  │  │ │ AOF Buffer  ││  │  │  │ │ AOF Buffer  ││  │  │  │ │ AOF Buffer  ││  ││
│  │  │ └─────────────┘│  │  │  │ └─────────────┘│  │  │  │ └─────────────┘│  ││
│  │  └───────┬─────────┘  │  │  └───────┬─────────┘  │  │  └───────┬─────────┘  ││
│  │          │ Replication │  │          │ Replication │  │          │ Replication ││
│  │          ▼             │  │          ▼             │  │          ▼             ││
│  │  ┌───────────────┐    │  │  ┌───────────────┐    │  │  ┌───────────────┐    ││
│  │  │   REPLICA 1    │    │  │  │   REPLICA 1    │    │  │  │   REPLICA 1    │    ││
│  │  │   Node A'      │    │  │  │   Node B'      │    │  │  │   Node N'      │    ││
│  │  │   (Read-only)  │    │  │  │   (Read-only)  │    │  │  │   (Read-only)  │    ││
│  │  └───────────────┘    │  │  └───────────────┘    │  │  └───────────────┘    ││
│  │  ┌───────────────┐    │  │  ┌───────────────┐    │  │  ┌───────────────┐    ││
│  │  │   REPLICA 2    │    │  │  │   REPLICA 2    │    │  │  │   REPLICA 2    │    ││
│  │  │   (Optional)   │    │  │  │   (Optional)   │    │  │  │   (Optional)   │    ││
│  │  └───────────────┘    │  │  └───────────────┘    │  │  └───────────────┘    ││
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘│
│                                                                              │
│  CLUSTER BUS (TCP port + 10000):                                            │
│  ├── Gossip protocol: PING/PONG every 1s (node health)                     │
│  ├── Failure detection: PFAIL → FAIL (majority agreement)                  │
│  ├── Failover: replica promotion (Raft-like election)                      │
│  ├── Config propagation: slot ownership, epoch updates                     │
│  └── Slot migration: MIGRATE command for online resharding                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         PERSISTENCE LAYER                                     │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │ RDB Snapshot │  │ AOF Log      │  │ Replication  │                     │
│  │              │  │              │  │ Stream       │                     │
│  │ Binary dump  │  │ Command log  │  │              │                     │
│  │ Point-in-time│  │ Continuous   │  │ Master →     │                     │
│  │ COW fork     │  │ Append       │  │ Replica sync │                     │
│  │              │  │ + Rewrite    │  │              │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│                                                                              │
│  Disk: NVMe SSD for AOF write performance (fsync every second)             │
│  Backup: Periodic RDB → S3/GCS for disaster recovery                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    MONITORING & MANAGEMENT                                    │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Prometheus   │  │ Grafana      │  │ Cluster      │  │ Auto-Scaling │  │
│  │ (Metrics)    │  │ (Dashboards) │  │ Manager      │  │ Controller   │  │
│  │              │  │              │  │ (Resharding) │  │              │  │
│  │ redis_export │  │ Cache perf   │  │ Slot balance │  │ Memory-based │  │
│  │ every 10s    │  │ dashboards   │  │ Online migrate│  │ scale-out    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Microservice Patterns

| Pattern | Application |
|---------|-------------|
| **Sharding** | Hash slots partition data across nodes |
| **Master-Replica** | Write to master, read from replicas for scale |
| **Gossip Protocol** | Decentralized failure detection and config propagation |
| **Leader Election** | Raft-like voting for automatic failover |
| **Event Loop (Reactor)** | Single-threaded non-blocking I/O for low latency |
| **Copy-on-Write** | Fork for RDB snapshots without blocking |
| **Proxy** | Optional proxy layer for connection pooling |
| **Sidecar** | Metrics exporter as sidecar |
| **Circuit Breaker** | Client-side circuit breaker for failed nodes |

## 6. Low-Level Design (LLD)

### Client API (Command Interface)

**String Operations**
```
SET key value [EX seconds] [PX milliseconds] [NX|XX] [GET]
GET key
MGET key1 key2 key3
MSET key1 value1 key2 value2
INCR key
INCRBY key increment
DECRBY key decrement
APPEND key value
STRLEN key
GETRANGE key start end
SETRANGE key offset value
```

**Hash Operations**
```
HSET key field value [field value ...]
HGET key field
HMGET key field1 field2
HGETALL key
HDEL key field [field ...]
HINCRBY key field increment
HEXISTS key field
HLEN key
HSCAN key cursor [MATCH pattern] [COUNT count]
```

**List Operations**
```
LPUSH key value [value ...]
RPUSH key value [value ...]
LPOP key [count]
RPOP key [count]
LRANGE key start stop
LLEN key
LINDEX key index
LINSERT key BEFORE|AFTER pivot element
BLPOP key [key ...] timeout      # Blocking pop
BRPOP key [key ...] timeout
```

**Sorted Set Operations**
```
ZADD key [NX|XX] [GT|LT] [CH] score member [score member ...]
ZRANGE key min max [BYSCORE|BYLEX] [REV] [LIMIT offset count]
ZRANK key member
ZSCORE key member
ZREM key member [member ...]
ZRANGEBYSCORE key min max [WITHSCORES] [LIMIT offset count]
ZCARD key
ZINCRBY key increment member
ZRANGEBYLEX key min max [LIMIT offset count]
```

**Cluster Operations**
```
CLUSTER INFO                     # Cluster state and stats
CLUSTER NODES                    # List all nodes and slots
CLUSTER SLOTS                    # Slot-to-node mapping
CLUSTER ADDSLOTS slot [slot ...] # Assign slots to current node
CLUSTER DELSLOTS slot [slot ...] # Remove slot assignment
CLUSTER SETSLOT slot IMPORTING node-id  # Start importing slot
CLUSTER SETSLOT slot MIGRATING node-id  # Start migrating slot
CLUSTER SETSLOT slot NODE node-id       # Assign slot to node
CLUSTER FAILOVER [FORCE|TAKEOVER]       # Manual failover
CLUSTER REPLICATE node-id               # Make current node replica of node-id
CLUSTER RESET [HARD|SOFT]               # Reset node
```

**Management APIs (REST - for orchestration tools)**
```http
POST /api/v1/clusters
{
    "name": "prod-cache-cluster",
    "nodes": 6,
    "replicas_per_master": 1,
    "memory_per_node_gb": 128,
    "persistence": {"rdb": true, "aof": {"enabled": true, "fsync": "everysec"}},
    "eviction_policy": "allkeys-lfu"
}

POST /api/v1/clusters/{id}/reshard
{
    "source_node": "node-a",
    "target_node": "node-d",
    "slots": [0, 1, 2, 3, 4, 5],
    "timeout_ms": 60000
}

POST /api/v1/clusters/{id}/failover
{
    "node": "node-a-replica",
    "force": false
}

GET /api/v1/clusters/{id}/stats
Response:
{
    "total_keys": 5000000000,
    "total_memory_bytes": 10995116277760,
    "ops_per_sec": 9500000,
    "hit_ratio": 0.97,
    "connected_clients": 48000,
    "nodes": [...]
}
```

### Design Patterns

| Pattern | Implementation |
|---------|---------------|
| **Reactor** | Single event loop (epoll/kqueue) handles all I/O multiplexing |
| **Command** | Each operation is a command object with execute/undo semantics |
| **Strategy** | Eviction policies as interchangeable strategies |
| **Observer** | Pub/Sub, keyspace notifications |
| **Memento** | RDB snapshot as memento of entire state |
| **Flyweight** | Shared integer objects (0-9999 pre-allocated) |
| **Iterator** | SCAN cursor for non-blocking iteration |
| **Template Method** | Command execution template (parse → check → execute → propagate) |
| **Decorator** | Key expiry wraps around normal key access |

### Core Processing Loop (Single-Threaded Event Loop)
```
while (running) {
    // 1. Process time events (cron-like: expiry, stats, replication, cluster health)
    processTimeEvents();
    
    // 2. Poll for I/O events (epoll_wait with timeout)
    numEvents = epollWait(eventLoop, events, timeout);
    
    // 3. Process file events (client commands, replication, cluster bus)
    for (int i = 0; i < numEvents; i++) {
        if (events[i].type == READABLE) {
            readFromClient(events[i].client);
            processCommandsInInputBuffer(events[i].client);
        }
        if (events[i].type == WRITABLE) {
            writeToClient(events[i].client);
        }
    }
    
    // 4. Before-sleep tasks: AOF flush, handle blocked clients, cluster tasks
    beforeSleep();
}
```

## 7. Architecture Components Deep Dive

### 7.1 Event Loop Engine (io_uring/epoll)
```
Modern implementation: io_uring (Linux 5.1+)
  - Shared submission/completion queues between kernel and user space
  - Zero-copy I/O for large values
  - Batched syscalls: submit multiple I/O ops in single syscall
  - Performance: 2x throughput vs epoll for high-connection-count workloads

Fallback: epoll (Linux) / kqueue (macOS/BSD)
  - Level-triggered for reads (simplicity)
  - Edge-triggered for writes (efficiency)
  - Event capacity: 10K+ concurrent connections per event loop

Threading model:
  - Main thread: single event loop for command processing (avoids locks)
  - I/O threads (Redis 6+): offload network read/write to threads
    - Read thread: reads from socket, parses commands into buffer
    - Write thread: writes response buffers to sockets
    - Main thread still executes commands (sequential consistency guaranteed)
  - Background threads: RDB/AOF persistence, lazy deletion of large keys
```

### 7.2 Memory Allocator (jemalloc)
```
Why jemalloc:
  - Reduced fragmentation vs glibc malloc (20-30% less waste)
  - Thread-local caches for allocation-heavy workloads
  - Size classes: minimize internal fragmentation
  - Arena-based: multiple arenas reduce lock contention (multi-threaded I/O)
  
Memory accounting:
  - Track total allocated vs RSS (fragmentation ratio)
  - zmalloc wrapper: prefix each allocation with 8-byte size header
  - Total memory = sum of all zmalloc'd blocks
  - If fragmentation > 1.5x: trigger active defragmentation
  
Active defragmentation (Redis 4+):
  - Background task during idle periods
  - Scan keys, check if current allocation is fragmented
  - If yes: allocate new block, copy data, free old block
  - Rate limited: < 25% CPU per cycle
  - Uses jemalloc allocation profiling to identify fragmented regions
```

### 7.3 Replication Engine
```
Full sync (initial or after disconnect > backlog):
  1. Replica sends PSYNC ? -1 (full sync request)
  2. Master initiates BGSAVE (background RDB)
  3. Master buffers all new writes in replication backlog
  4. RDB complete → stream to replica over TCP
  5. Replica loads RDB into memory
  6. Master streams buffered backlog
  7. Replica now in sync; continuous streaming begins

Partial sync (after brief disconnect):
  1. Replica reconnects, sends PSYNC replication_id offset
  2. Master checks: is offset within backlog?
  3. If yes: stream missing data from backlog → partial resync (fast!)
  4. If no (offset too old): fall back to full sync

Replication backlog:
  - Circular buffer: default 1 MB (should be larger: 256 MB+)
  - Size formula: backlog_size = write_ops/sec × max_acceptable_disconnect_seconds
  - Example: 10K writes/sec × 60s = 600K entries × 100 bytes = 60 MB minimum

WAIT command (synchronous replication):
  WAIT numreplicas timeout
  - Block until N replicas acknowledge the write
  - Provides "at least N replicas have the data" guarantee
  - Useful for critical writes before returning success to client
```

### 7.4 Cluster Consensus & Failover
```
Failure detection (gossip-based):
  1. Node A pings Node B every 1 second (randomized)
  2. If no response within cluster-node-timeout (default 15s):
     Node A marks B as PFAIL (suspected failure)
  3. A shares PFAIL info in gossip messages
  4. When majority of masters agree B is PFAIL:
     B is marked as FAIL (confirmed failure)

Failover election (Raft-inspired):
  1. Replica of failed master detects FAIL state
  2. Replica increments currentEpoch
  3. Replica requests votes from all masters: FAILOVER_AUTH_REQUEST
  4. Masters vote YES if:
     - Haven't voted in this epoch
     - Replica's replication offset is acceptable
  5. Replica collects majority votes (N/2 + 1)
  6. Replica promotes itself to master
  7. Replica broadcasts new config with higher epoch
  8. All nodes update their slot mapping

Split-brain prevention:
  - cluster-require-full-coverage: require all slots covered for writes
  - min-replicas-to-write: master rejects writes if too few replicas are reachable
  - Epoch-based ordering: higher epoch wins in configuration conflicts
```

### 7.5 Hash Slot Migration (Online Resharding)
```
Slot migration from Node A to Node B (no downtime):

1. CLUSTER SETSLOT <slot> MIGRATING <B-id>   (on Node A)
2. CLUSTER SETSLOT <slot> IMPORTING <A-id>   (on Node B)
3. For each key in slot (CLUSTER GETKEYSINSLOT):
   a. MIGRATE <B-host> <B-port> <key> 0 <timeout> COPY REPLACE
   b. Key atomically moved: serialize → send → load → delete source
4. CLUSTER SETSLOT <slot> NODE <B-id>         (on all nodes)

During migration, client handling:
  - Client requests key on Node A:
    - If key exists on A: serve normally
    - If key already migrated: reply ASK <B>
  - Client receives ASK: send ASKING + command to Node B
  - After migration complete: MOVED redirect permanently

Performance:
  - Migration rate: ~10K keys/sec per slot (bounded to not overload)
  - Total time for 1000 slots: varies by data volume
  - Client impact: brief latency spike for individual keys during MIGRATE
  - No data loss: atomic MIGRATE with REPLACE
```

## 8. Deep Dive: Eviction Policies

### 8.1 LRU (Least Recently Used)
```
Approximated LRU (Redis implementation):
  - NOT true LRU (would require doubly-linked list = too much memory)
  - Instead: sample N random keys, evict the one with oldest access time
  - Sample size: configurable (maxmemory-samples, default 5)
  
  Each key stores 24-bit LRU clock (unix seconds, wraps every 194 days)
  On access: update LRU clock to current time
  On eviction: sample 5 keys, compute idle time, evict max idle

  With sample=10: very close to true LRU (< 2% difference)
  Memory overhead: 0 extra bytes (LRU clock is in object header)
```

### 8.2 LFU (Least Frequently Used)
```
Approximated LFU (Redis 4.0+):
  Uses 24-bit field: 16 bits for decay time + 8 bits for frequency counter
  
  Frequency counter (logarithmic):
    - Range: 0-255
    - Probabilistic increment: P(increment) = 1 / (counter * lfu_log_factor + 1)
    - At factor=10: counter reaches 100 after ~10M accesses
    - Decays over time: counter decremented based on elapsed minutes
    
  Decay: 
    - Every access: check if decay period elapsed
    - num_periods = (current_minutes - last_access_minutes) / lfu_decay_time
    - counter = max(0, counter - num_periods)
  
  Eviction:
    - Sample N keys
    - Evict one with lowest frequency counter
    - Tiebreaker: oldest access time
    
  Why LFU > LRU for cache:
    - LRU vulnerable to scan pollution (one-time access evicts frequent keys)
    - LFU keeps truly popular items regardless of recent access patterns
```

### 8.3 Cache Stampede Prevention
```
Problem: Popular key expires → many clients simultaneously miss → all fetch from source

Solution 1: Probabilistic early expiration (XFetch)
  TTL_remaining = key_expiry - current_time
  early_expire_probability = exp(-TTL_remaining / (beta * compute_time))
  If random() < early_expire_probability:
    Recompute value in background

Solution 2: Lock-based refresh (SETNX)
  On cache miss:
    lock_acquired = SETNX("lock:" + key, "1", EX=10)
    if lock_acquired:
      value = compute_from_source()
      SET key value EX ttl
      DEL "lock:" + key
    else:
      wait_or_return_stale()

Solution 3: External write-through (application-level)
  - Dedicated refresh service that pre-populates before expiry
  - Subscribe to expiry events: __keyevent@0__:expired
  - Refresh 30s before actual expiry
```

### 8.4 Hot Key Mitigation
```
Problem: Single key receiving >100K reads/sec overwhelms one shard

Detection:
  - Monitor per-key access frequency (OBJECT FREQ key)
  - Track top-K keys using Count-Min Sketch
  - Alert when key exceeds threshold

Mitigation strategies:
1. Local cache (client-side):
   - Cache hot keys in application memory (10s TTL)
   - Server-assisted invalidation: client tracks keys, server notifies on change
   
2. Read replicas:
   - Route hot key reads to all replicas (read scaling)
   - Trade consistency for throughput

3. Key splitting:
   - Split "hot_counter" into "hot_counter:{0..15}"
   - Write: INCR random shard
   - Read: SUM all shards
   - 16x write capacity, slightly stale reads

4. Proxy-level caching:
   - Proxy caches hot keys locally (100ms TTL)
   - Reduces requests reaching cache server by 99% for hottest keys
```

## 9. Component Optimization

### 9.1 Pipeline & Batching
```
Without pipeline:
  Client → SET key1 → Server → OK → Client → SET key2 → Server → OK
  Latency: N × RTT (e.g., 10 commands × 0.5ms = 5ms)

With pipeline:
  Client → [SET key1, SET key2, ..., SET key10] → Server → [OK, OK, ..., OK]
  Latency: 1 × RTT + processing (0.5ms + 0.1ms = 0.6ms for 10 commands)

Optimal pipeline size:
  - Too small: high RTT overhead
  - Too large: memory pressure, blocking other clients
  - Sweet spot: 100-1000 commands per pipeline
  
Implementation:
  - Client queues commands locally
  - Sends as single TCP write (Nagle's algorithm disabled: TCP_NODELAY)
  - Server processes sequentially, buffers responses
  - Returns all responses in single TCP write
```

### 9.2 Memory Optimization Techniques
```
1. Ziplist encoding (small collections):
   - List/Hash/Set with few small elements → linear array
   - Memory: ~60% less than hash table encoding
   - Threshold: hash-max-ziplist-entries=128, hash-max-ziplist-value=64
   - Trade-off: O(n) lookup vs O(1), but N is small so cache-friendly

2. Intset (integer sets):
   - Set of only integers → sorted integer array
   - Binary search: O(log n)
   - Memory: 50% less than hash table
   - Upgrades automatically to 32-bit or 64-bit as needed

3. Shared objects:
   - Integers 0-9999 pre-allocated and shared (refcounted)
   - Saves 8 bytes + object header per shared reference
   - Strings: Redis doesn't share (too many unique values)

4. Embedded strings (EMBSTR):
   - Strings ≤ 44 bytes: single allocation (redisObject + SDS together)
   - vs RAW: two allocations (redisObject + separate SDS)
   - Saves: 1 allocation overhead (~32 bytes with jemalloc)

5. Active memory defragmentation:
   - Enabled: activedefrag yes
   - Trigger: when fragmentation ratio > 1.5
   - Copy values to new allocations, free old ones
   - Non-blocking: runs in event loop idle time
```

### 9.3 Persistence Optimization
```
RDB optimization:
  - Fork uses CoW: only modified pages duplicated
  - With 100GB dataset: ~10-30GB additional memory during BGSAVE
  - Recommendation: keep 30% RAM headroom for BGSAVE
  - Time: 100GB → ~2 min to write (depends on I/O speed)
  - Compression: LZF compression saves 50-70% disk space

AOF optimization:
  - Write buffering: collect commands, write every cycle (1ms)
  - Fsync batching: everysec mode groups fsync calls
  - NVMe SSD: fsync latency ~50μs (vs 5ms for HDD)
  - AOF rewrite: background process, minimal fork overhead
  - Multi-part AOF (Redis 7): base RDB + incremental AOF segments

Mixed persistence (RDB + AOF):
  - Use both: RDB for faster recovery, AOF for durability
  - Recovery order: if AOF exists, use AOF (more complete); else use RDB
  - AOF rewrite produces: RDB preamble + AOF tail
  - Best of both: fast load (RDB binary) + minimal data loss (AOF tail)
```

### 9.4 Cluster Communication Optimization
```
Gossip protocol optimization:
  - Each PING/PONG carries info about 1/10 of known nodes (random sample)
  - Full cluster state propagation: O(N log N) messages
  - Message size: ~2KB per PING/PONG (with 100 nodes)
  - Bandwidth: 100 nodes × 1 msg/sec × 2KB = 200 KB/s total gossip traffic

Heartbeat optimization:
  - Send PING to random node every 100ms (across all nodes = 1000/sec cluster-wide)
  - If no PONG within cluster-node-timeout/2: send PING immediately
  - Avoids thundering herd on cluster events

Slot migration optimization:
  - Batch MIGRATE: move multiple keys per MIGRATE command
  - Pipeline MIGRATE commands for throughput
  - Rate limiting: max 1 MB/s per slot migration to avoid I/O contention
  - Lazy migration: optionally migrate on access (key-by-key when requested)
```

### 9.5 Client-Side Caching (Tracking)
```
Server-assisted client caching (Redis 6+):

Protocol:
  CLIENT TRACKING ON REDIRECT <client-id> [BCAST] [PREFIX prefix] [OPTIN] [OPTOUT]

How it works:
1. Client sends: CLIENT TRACKING ON
2. Client sends: GET key1
3. Server stores: key1 is tracked by this client
4. When key1 is modified by any client:
   Server sends invalidation: PUSH > ["invalidate", ["key1"]]
5. Client evicts key1 from local cache
6. Next access: re-fetch from server

Modes:
  - Default: invalidation per key (memory overhead on server)
  - BCAST: invalidation for all keys matching prefix (less server memory)
  - OPTIN: only track keys explicitly opted in
  
Benefits:
  - 90%+ local hit rate for read-heavy workloads
  - Near-zero latency for local hits (no network)
  - Automatic consistency: server pushes invalidations
  
Memory: server tracks ~64 bytes per tracked key per client
Limit: max tracked keys per client (configurable)
```

### 9.6 Sharding & Partitioning
```
Hash slot approach (Redis Cluster):
  Slot = CRC16(key) % 16384
  
Advantages:
  - Fixed number of slots: resharding = moving slots (not rehashing all keys)
  - Hash tags: {user:123}:profile and {user:123}:session → same slot
  - Enables multi-key commands within same slot

Resharding without downtime:
  Phase 1: IMPORTING + MIGRATING flags set on source and target
  Phase 2: Keys moved one-by-one (or batched)
  Phase 3: Slot ownership transferred
  
  Client experience:
    - ASK redirects during migration (temporary)
    - MOVED redirects after completion (permanent, client updates slot map)
    - Latency increase: +1 RTT for migrating keys (ASK → redirect)

Virtual node mapping for even distribution:
  - Each physical node owns multiple slots (not contiguous)
  - On node addition: steal 1/N slots from each existing node
  - Minimal data movement: only moved slots' data transfers
```

## 10. Observability

### 10.1 Metrics
```yaml
# Performance metrics
redis_commands_processed_total                          # Counter
redis_commands_duration_seconds{cmd}                    # Histogram per command type
redis_connected_clients                                # Gauge
redis_blocked_clients                                  # Gauge (BLPOP waiters)
redis_ops_per_sec                                      # Gauge (instantaneous)

# Memory metrics
redis_memory_used_bytes                                # Gauge
redis_memory_used_rss_bytes                            # Gauge (RSS from OS)
redis_memory_fragmentation_ratio                       # Gauge (RSS/used)
redis_memory_max_bytes                                 # Gauge (configured limit)
redis_evicted_keys_total                               # Counter
redis_expired_keys_total                               # Counter
redis_mem_overhead_bytes                               # Gauge (non-data memory)

# Keyspace metrics
redis_db_keys{db}                                      # Gauge per database
redis_db_expires{db}                                   # Gauge (keys with TTL)
redis_keyspace_hits_total                              # Counter
redis_keyspace_misses_total                            # Counter
redis_hit_ratio                                        # Gauge (hits/(hits+misses))

# Replication metrics
redis_connected_slaves                                 # Gauge
redis_replication_offset                               # Gauge (master offset)
redis_slave_repl_offset                                # Gauge (replica offset)
redis_replication_lag_bytes                            # Gauge (master - replica offset)
redis_repl_backlog_size                                # Gauge

# Persistence metrics
redis_rdb_last_save_time                               # Gauge (unix timestamp)
redis_rdb_last_bgsave_duration_sec                     # Gauge
redis_rdb_current_bgsave_duration_sec                  # Gauge
redis_aof_current_rewrite_duration_sec                 # Gauge
redis_aof_last_rewrite_duration_sec                    # Gauge
redis_aof_buffer_length                                # Gauge

# Cluster metrics
redis_cluster_state{state}                             # Gauge (ok/fail)
redis_cluster_slots_assigned                           # Gauge
redis_cluster_slots_ok                                 # Gauge
redis_cluster_known_nodes                              # Gauge
redis_cluster_messages_sent_total{type}                # Counter
redis_cluster_messages_received_total{type}            # Counter

# Network metrics
redis_net_input_bytes_total                            # Counter
redis_net_output_bytes_total                           # Counter
redis_rejected_connections_total                       # Counter
redis_total_connections_received                       # Counter

# Slow log
redis_slowlog_length                                   # Gauge
redis_slowlog_last_duration_microseconds               # Gauge
```

### 10.2 Alerting
```yaml
# Critical
- alert: CacheDown
  expr: up{job="redis"} == 0
  for: 10s
  severity: critical

- alert: MemoryExhausted
  expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.95
  for: 2m
  severity: critical
  description: "Cache memory > 95%, evictions imminent"

- alert: ReplicationBroken
  expr: redis_connected_slaves == 0 AND redis_instance_role == "master"
  for: 1m
  severity: critical

- alert: ClusterStateNotOK
  expr: redis_cluster_state != 1
  for: 30s
  severity: critical

# Warning
- alert: HighEvictionRate
  expr: rate(redis_evicted_keys_total[5m]) > 1000
  for: 5m
  severity: warning

- alert: ReplicationLag
  expr: redis_replication_lag_bytes > 10485760
  for: 2m
  severity: warning
  description: "Replication lag > 10MB"

- alert: HighFragmentation
  expr: redis_memory_fragmentation_ratio > 1.5
  for: 30m
  severity: warning

- alert: LowHitRatio
  expr: redis_hit_ratio < 0.8
  for: 10m
  severity: warning
  description: "Cache hit ratio below 80%"

- alert: SlowlogGrowing
  expr: redis_slowlog_length > 100
  for: 5m
  severity: warning
```

### 10.3 Dashboards
```
Dashboard 1: Cache Performance
- OPS/sec (reads vs writes)
- Hit ratio trend
- p50/p95/p99 latency
- Command breakdown (top-N commands)
- Connected clients

Dashboard 2: Memory Health
- Memory usage vs max
- Fragmentation ratio
- Eviction rate
- Key count trend
- Expired keys rate

Dashboard 3: Cluster Health
- Cluster state
- Slot distribution map
- Replication lag per replica
- Gossip message rate
- Failover events

Dashboard 4: Persistence
- RDB save status and timing
- AOF size and rewrite frequency
- Fork memory overhead
- Disk I/O during persistence
```

## 11. Considerations and Assumptions

### Assumptions
1. **In-memory first**: All active data fits in RAM; disk is for persistence and recovery only
2. **Network locality**: Clients and cache nodes in same data center (< 1ms RTT)
3. **Key distribution**: Relatively uniform key access (no extreme hotspots, handled separately)
4. **Workload**: Mixed read/write (80/20 to 95/5); read-heavy benefits most from caching
5. **Data size**: Most values < 10 KB; large values (> 1 MB) are exceptions handled with streaming
6. **Consistency**: Accept eventually consistent replicas; strong consistency only on master
7. **Failure budget**: Can tolerate brief unavailability (< 15s) during failover

### Design Decisions

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Threading | Single-threaded core + I/O threads | Full multi-threading | Simplicity, no locking, predictable latency |
| Sharding | Hash slots (16,384) | Consistent hashing | Fixed slots enable fine-grained migration without rehashing |
| Replication | Async with WAIT option | Synchronous replication | Performance by default; WAIT for critical writes |
| Persistence | RDB + AOF hybrid | WAL only | Fast recovery (RDB) + low data loss (AOF) |
| Memory allocator | jemalloc | tcmalloc/glibc | Best fragmentation behavior for key-value workloads |
| Protocol | RESP3 (Redis protocol) | gRPC/HTTP | Minimal overhead, pipelining, streaming support |
| Eviction | LFU (default) | LRU | Better cache behavior (resists scans) |
| Cluster consensus | Gossip + epoch voting | Raft | Simpler, eventually consistent metadata (faster) |

### Trade-offs

| Trade-off | Benefit | Cost |
|-----------|---------|------|
| Single-threaded execution | Zero-lock simplicity, predictable latency | Can't use all CPU cores for one command |
| In-memory only | Sub-millisecond latency | Expensive (RAM cost), data loss risk |
| Async replication | High write throughput | Possible data loss on master failure |
| Hash slots (not keys) | Online resharding without full rehash | Multi-key commands restricted to same slot |
| Approximate LRU/LFU | Zero memory overhead | Slightly suboptimal eviction decisions |
| Fork for RDB | Non-blocking snapshots | CoW memory spike (up to 2x during save) |
| Eventually consistent cluster metadata | Fast convergence | Brief confusion during failover |

### Failure Modes & Recovery

| Failure | Impact | Recovery |
|---------|--------|----------|
| Master node crash | Writes unavailable for ~15s | Automatic failover: replica promoted |
| Network partition | Split-brain risk | min-replicas-to-write prevents stale writes |
| OOM (Out of Memory) | Evictions or write failures | Scale out (add nodes) or increase maxmemory |
| Slow disk (AOF fsync) | Latency spikes | Move to NVMe SSD; or disable fsync (accept risk) |
| Replication backlog overflow | Full resync required | Increase backlog size; faster reconnection |
| Corrupt RDB/AOF | Recovery failure | Backup from S3; use replica as source |
| Hot key | Single node overload | Client-side cache, key splitting, read replicas |
| Large key (100MB+) | Blocks event loop during delete | UNLINK (async delete), avoid large keys |
| Cluster slot migration stuck | Inconsistent routing | Timeout + manual SETSLOT reset |

### Security Considerations
```
1. Authentication: requirepass + ACLs (Redis 6+)
2. Network: bind to internal IP, no public exposure
3. Encryption: TLS for client connections (Redis 6+)
4. ACLs: per-user command/key restrictions
   - user api-service +get +set ~cache:* on >password
   - user admin +@all ~* on >admin-password
5. No dangerous commands in production: rename CONFIG, FLUSHALL, KEYS, DEBUG
6. Protected mode: reject connections from non-localhost without auth
7. Key naming: namespace by tenant to prevent cross-access
8. Audit: log all admin commands and AUTH failures
```
