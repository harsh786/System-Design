# Redis Database Deep Dive - Architecture, Production, and Real-World Problem Solving

**Purpose:** A practical Redis learning note for system design, production operations, and interview-style problem solving.

**Primary focus:** Redis mental model, data structures, key-value and document modeling, query/search/aggregation, hotspot mitigation, Bloom filters and probabilistic structures, replication, Sentinel, Cluster, CAP tradeoffs, persistence, caching patterns, operational safety, and real-world design recipes.

**Docs checked:** Context7 was used against the official Redis documentation index (`/websites/redis_io`). Official Redis docs were also checked for data types, replication, persistence, eviction, Sentinel, Cluster, latency monitoring, and aggregation. Links are listed at the end.

## 1. Mental Model

Redis is an in-memory data structure server. It can act as:

- A cache.
- A primary key-value database for selected workloads.
- A session store.
- A distributed counter store.
- A rate-limiter backend.
- A queue or stream processor.
- A leaderboard engine.
- A Pub/Sub broker.
- A document database when using Redis JSON and Redis Query Engine.
- A search and vector-search backend when using Redis Search capabilities.
- A probabilistic data-structure engine for Bloom filters, HyperLogLog, Count-Min Sketch, Top-K, and related structures.

The most useful mental model:

```text
Application
  |
Redis client
  |
Connection, pipeline, transaction, Lua/function, or normal command
  |
Redis event loop
  |
In-memory data structure
  |
Optional persistence, replication, eviction, expiration, and clustering
```

Redis is not "just a cache." It is a programmable in-memory data store with data structures as first-class primitives.

The most important design question is:

> Can I model this workload as bounded operations on known keys?

If yes, Redis can be extremely fast and simple. If no, Redis may still help as a cache, index, queue, or derived view, but it should not blindly replace a relational database, document database, search engine, or analytical store.

## 2. What Redis Is Good At

Redis is strongest when requests are:

- Key-based.
- Small and frequent.
- Latency-sensitive.
- Memory-resident.
- Built from atomic data-structure operations.
- Easy to expire or rebuild.
- Naturally denormalized.
- Served by bounded reads and writes.

Common production use cases:

- Login sessions and auth tokens.
- User profile cache.
- Product catalog cache.
- Rate limiting.
- API quota counters.
- Leaderboards.
- Real-time counters.
- Shopping cart state.
- Feature flags and configuration cache.
- Idempotency keys.
- Distributed locks and leases.
- Feed fanout buffers.
- Notification inboxes.
- Message queues with Streams.
- Pub/Sub notifications.
- Cache-aside layer in front of Postgres, MySQL, MongoDB, Cassandra, ScyllaDB, or external APIs.
- Bloom filter for cache penetration protection.
- HyperLogLog for approximate unique visitor counts.
- JSON document store for low-latency operational documents.
- Search over indexed Hash or JSON documents.

Avoid Redis as the primary store when the workload requires:

- Large datasets that cannot fit economically in memory or Redis tiering.
- Complex joins.
- Multi-table relational constraints.
- Long-running analytical scans.
- Arbitrary ad hoc queries over unindexed fields.
- Strong serializable transactions across many keys or shards.
- Strict write durability after every acknowledged write without careful persistence and replication design.
- Cheap historical analytics over very large volumes.
- Unbounded fanout, unbounded set operations, or large-key mutation in the request path.

## 3. Redis Data Model

Redis stores values under keys. The value is not limited to a blob. It can be a rich data structure.

| Data type | Common commands | Real-world use |
|---|---|---|
| String | `GET`, `SET`, `INCR`, `MGET`, `SETEX` | Cache values, counters, locks, feature flags |
| Hash | `HSET`, `HGET`, `HGETALL`, `HINCRBY` | User profile fields, object attributes |
| List | `LPUSH`, `RPUSH`, `LPOP`, `BRPOP` | Simple queues, recent activity lists |
| Set | `SADD`, `SISMEMBER`, `SINTER`, `SUNION` | Membership, tags, dedupe |
| Sorted set | `ZADD`, `ZRANGE`, `ZREVRANK`, `ZINCRBY` | Leaderboards, ranked feeds, time indexes |
| Stream | `XADD`, `XREADGROUP`, `XACK`, `XPENDING` | Durable event streams, consumer groups |
| Bitmap | `SETBIT`, `GETBIT`, `BITCOUNT` | Daily active users, flags, attendance |
| Bitfield | `BITFIELD` | Compact counters and packed numeric state |
| Geospatial | `GEOADD`, `GEOSEARCH` | Nearby drivers, stores, places |
| HyperLogLog | `PFADD`, `PFCOUNT`, `PFMERGE` | Approximate distinct counts |
| JSON | `JSON.SET`, `JSON.GET`, `JSON.NUMINCRBY` | Document-style objects |
| Search index | `FT.CREATE`, `FT.SEARCH`, `FT.AGGREGATE` | Filtering, full-text search, document queries |
| Probabilistic | `BF.ADD`, `BF.EXISTS`, `CMS.INCRBY`, `TOPK.ADD` | Membership, frequency, heavy hitters |
| Time series | `TS.ADD`, `TS.RANGE`, `TS.MRANGE` | Metrics and time-bucketed measurements |

The key design discipline:

```text
Key name = namespace + entity + identifier + optional dimension
Value type = operation you need to perform efficiently
TTL = lifecycle and memory strategy
```

Examples:

```text
session:user:123                 -> String or Hash, TTL
profile:user:123                 -> Hash or JSON
cart:user:123                    -> Hash, TTL
rate:login:ip:10.1.2.3:20260527  -> String counter, TTL
leaderboard:game:chess:daily     -> Sorted set
feed:user:123                    -> Sorted set or List
idempotency:payment:req_abc      -> String, TTL
bf:known_product_ids             -> Bloom filter
stream:orders                    -> Stream
```

## 4. Redis As A Key-Value Store

Redis is a natural key-value store when the application knows the key.

### 4.1 Basic KV Pattern

```text
SET user:123 '{"name":"Asha","plan":"premium"}' EX 3600
GET user:123
```

Use this when:

- The value is read and written as a whole.
- You do not need to update individual fields often.
- Serialization is handled in the application.
- You want simple cache-aside behavior.

### 4.2 Hash As Object Fields

```text
HSET user:123 name "Asha" plan "premium" city "Bengaluru"
HGET user:123 plan
HINCRBY user:123 login_count 1
```

Use Hashes when:

- You update individual fields.
- You need counters inside an object.
- You want lower write amplification than rewriting one large JSON blob.
- Querying is still key-based.

### 4.3 TTL-Aware KV

```text
SET session:abc user_123 EX 1800
EXPIRE cart:user:123 604800
TTL session:abc
```

TTL is a first-class part of Redis modeling. It solves:

- Session expiration.
- Cache lifecycle.
- Idempotency windows.
- Rate-limit windows.
- Temporary locks.
- Temporary workflow state.

Production rule: every cache-like key should have an explicit TTL unless there is a strong reason not to.

## 5. Redis As A Document Database

Redis can be used as a document database in two main ways:

1. Store documents as JSON strings or Hashes and access by key.
2. Use Redis JSON plus Redis Query Engine to store, update, index, search, filter, and aggregate JSON documents.

### 5.1 JSON Document Example

```text
JSON.SET user:123 $ '{
  "id": "123",
  "name": "Asha",
  "plan": "premium",
  "age": 31,
  "city": "Bengaluru",
  "tags": ["founder", "payments"]
}'

JSON.GET user:123 $.plan
JSON.SET user:123 $.city '"Pune"'
JSON.NUMINCRBY user:123 $.login_count 1
```

Use Redis JSON when:

- Documents are hierarchical.
- You need partial document reads or writes.
- You need to index document fields.
- You need low-latency document access.

Avoid using Redis JSON as a general replacement for MongoDB or Postgres JSONB if:

- The dataset is huge and mostly cold.
- You need complex multi-document transactions.
- You need analytical queries over large history.
- You need mature document lifecycle tooling, schema governance, or archival queries.

### 5.2 Querying JSON Documents

With Redis Query Engine, create an index over JSON paths, then search:

```text
FT.CREATE idx:user ON JSON PREFIX 1 user:
  SCHEMA
    $.name AS name TEXT
    $.plan AS plan TAG
    $.age AS age NUMERIC
    $.city AS city TAG

FT.SEARCH idx:user '@plan:{premium} @age:[25 40] @city:{Bengaluru}'
```

This makes Redis act like a low-latency indexed document store. The important constraint is that indexed search has memory and write-amplification cost. Index only fields you actually query.

## 6. Querying, Filtering, And Aggregation

Redis has three different query styles. Choosing the wrong one is a common production mistake.

### 6.1 Query By Key

This is the fastest path:

```text
GET product:123
HGETALL user:123
ZRANGE leaderboard:daily 0 99 REV WITHSCORES
```

Use when the request can derive the key directly.

### 6.2 Query By Data Structure

You can model a secondary access pattern as a separate Redis structure:

```text
SADD users:city:Bengaluru user:123
SADD users:plan:premium user:123
SINTER users:city:Bengaluru users:plan:premium
```

or:

```text
ZADD orders:by_created_at 1716800000 order:123
ZRANGEBYSCORE orders:by_created_at 1716790000 1716809999
```

Use when:

- The index is simple.
- You can maintain it at write time.
- The result set is bounded.
- You understand memory duplication.

### 6.3 Query By Search Index

Use Redis Query Engine when you need:

- Full-text search.
- Numeric range filters.
- Tag filters.
- Geo filters.
- Vector search.
- Aggregations over indexed Hash or JSON documents.

Example aggregation:

```text
FT.AGGREGATE idx:order '@status:{paid}'
  GROUPBY 1 @city
  REDUCE COUNT 0 AS order_count
  SORTBY 2 @order_count DESC
```

Use this for operational search and dashboards, not unbounded warehouse analytics.

### 6.4 Aggregation Choices

| Need | Redis approach |
|---|---|
| Count exact events in one window | String counter with TTL |
| Count distinct visitors approximately | HyperLogLog |
| Top products by score | Sorted set |
| Heavy hitters in stream | Top-K or Count-Min Sketch |
| Per-city paid order count | Search aggregation or precomputed counters |
| Time-bucketed metrics | TimeSeries or sorted sets |
| Real-time dashboard | Precompute counters and sorted sets |
| Historical analytics | Export to ClickHouse, BigQuery, Snowflake, or lakehouse |

Production rule:

> If a query must scan a large fraction of Redis keys, it probably belongs in a search index, an analytical database, or a precomputed Redis view.

Do not use `KEYS *` in production. Use `SCAN` for incremental iteration, and still treat it as an operational/background task, not a hot request path.

## 7. Internal Architecture

### 7.1 Single-Threaded Command Execution

Redis command execution is primarily single-threaded per server process. This is a feature and a constraint.

Benefits:

- Simple atomic command semantics.
- No heavy lock contention inside command execution.
- Predictable behavior for small operations.
- High throughput per core.

Constraints:

- One slow command can delay other clients.
- Large keys can hurt latency.
- Expensive Lua scripts or functions block the event loop.
- Big set intersections, large sorted-set ranges, and full scans are dangerous in request paths.

Redis versions support additional threading for some I/O work, but the mental model for data mutation should still be: keep operations short, bounded, and event-loop friendly.

### 7.2 Atomic Operations

Single commands are atomic:

```text
INCR rate:user:123:minute:202605271030
ZINCRBY leaderboard:daily 10 user:123
HSET user:123 city Pune
```

For multi-command atomicity, use:

- `MULTI` / `EXEC`.
- `WATCH` for optimistic locking.
- Lua scripts with `EVAL`.
- Redis Functions for server-side logic.

Keep scripts small and deterministic. A script that loops over thousands of elements is a latency incident waiting to happen.

### 7.3 Memory-First Storage

Redis serves data from memory. Persistence is for recovery, not for the normal read path.

This means:

- Memory sizing is capacity planning.
- Key count matters.
- Value size matters.
- Fragmentation matters.
- Expiration strategy matters.
- Replication and persistence buffers need headroom.

Do not size Redis as:

```text
dataset size = machine RAM
```

Size it as:

```text
machine RAM
  >= dataset
   + allocator fragmentation
   + replication backlog
   + client buffers
   + AOF/RDB fork copy-on-write headroom
   + OS safety margin
```

## 8. Persistence

Redis provides persistence choices. Choose based on data-loss tolerance and latency requirements.

### 8.1 No Persistence

Use for pure cache:

```text
appendonly no
save ""
```

Benefits:

- Fastest and simplest.
- No disk persistence overhead.

Risk:

- Data is lost on restart.

Use only when Redis can be rebuilt from another system.

### 8.2 RDB Snapshots

RDB creates point-in-time snapshots.

Benefits:

- Compact files.
- Good for backups.
- Faster restart than replaying a huge AOF in many cases.

Risks:

- You can lose writes since the last snapshot.
- Snapshotting uses `fork()`, which can cause latency spikes on large datasets.
- Copy-on-write memory overhead can be high during snapshot.

Good for:

- Cache warm restart.
- Periodic backup.
- Data where losing a few minutes is acceptable.

### 8.3 AOF

AOF logs write commands for replay.

Common fsync policies:

- `appendfsync always`: strongest durability, highest write latency.
- `appendfsync everysec`: common default-style tradeoff, can lose about one second of writes on crash.
- `appendfsync no`: lets OS decide, faster but weaker.

Benefits:

- Better durability than periodic RDB.
- Human-readable command log format in spirit, though rewritten/optimized over time.

Risks:

- Larger files.
- Rewrite overhead.
- Disk latency can affect Redis.

### 8.4 RDB + AOF

Use when Redis is important enough that restart recovery matters and data loss should be minimized. If both are enabled, Redis uses AOF for restart because it is expected to be the most complete.

Production guidance:

- Use no persistence for disposable caches.
- Use AOF every second for many stateful Redis workloads.
- Add RDB for backup and faster baseline recovery.
- Test restore time, not just backup creation.
- Monitor `fork`, AOF rewrite, disk usage, and persistence errors.

## 9. Expiration And Eviction

Expiration and eviction are different.

| Concept | Meaning |
|---|---|
| Expiration | A key has a TTL and becomes logically invalid after time passes. |
| Eviction | Redis removes keys when memory exceeds `maxmemory`. |

### 9.1 Expiration

Use TTL for lifecycle:

```text
SET session:abc user_123 EX 1800
EXPIRE idempotency:payment:req_123 86400
```

Good TTL practice:

- Add jitter to avoid many keys expiring at the same second.
- Use TTLs for all cache entries.
- Keep permanent keys only when you have a deliberate memory plan.

Example TTL jitter:

```text
ttl = base_ttl + random(0, jitter_seconds)
```

### 9.2 Eviction Policies

Redis can evict keys after `maxmemory` is reached.

Common policies:

- `noeviction`: return errors on writes when memory is full.
- `allkeys-lru`: evict approximately least recently used keys from all keys.
- `allkeys-lfu`: evict approximately least frequently used keys from all keys.
- `volatile-lru`: evict LRU keys only among keys with TTL.
- `volatile-ttl`: evict keys with TTL, preferring shorter TTL.
- `allkeys-random`: evict random keys.

Use:

- `allkeys-lfu` for general caches with skewed access.
- `allkeys-lru` for recency-driven caches.
- `volatile-*` only when you are disciplined about TTLs.
- `noeviction` for primary/stateful Redis where silent eviction is unacceptable.

Important production detail: replication and persistence buffers are not counted the same way as dataset memory for eviction decisions. Leave memory headroom.

## 10. Replication

Redis replication is leader-follower.

```text
primary
  |
  +-- replica 1
  +-- replica 2
```

Writes go to the primary. Replicas receive the replication stream and can serve reads if the application accepts stale reads.

Benefits:

- Read scaling for read-heavy workloads.
- Faster failover with Sentinel or Cluster.
- Backup source without stressing primary.
- Disaster recovery building block.

Constraints:

- Replication is asynchronous by default.
- A primary can acknowledge a write before replicas have it.
- Failover can lose recently acknowledged writes.
- Replicas can be stale.
- Writes to replicas are normally not the durable source of truth.

### 10.1 Full And Partial Synchronization

When a replica connects:

- It may perform partial resynchronization if backlog still contains missing replication data.
- It may need full resynchronization if backlog is missing or topology changed too much.

Full sync can be expensive because it transfers the dataset and can trigger persistence-related work.

Production guidance:

- Size replication backlog.
- Avoid network instability.
- Monitor replication lag.
- Do not run all replicas across weak network links without understanding lag.

### 10.2 `WAIT` And Durability

`WAIT` can block until writes are acknowledged by a number of replicas:

```text
SET order:123 paid
WAIT 1 100
```

This reduces the chance of losing writes, but it does not turn Redis replication into a consensus protocol. It is a useful safety improvement, not a full linearizable commit guarantee.

## 11. High Availability With Sentinel

Redis Sentinel provides monitoring and automatic failover for primary-replica deployments.

Sentinel responsibilities:

- Monitor primaries and replicas.
- Detect primary failure.
- Elect a Sentinel leader for failover.
- Promote a replica to primary.
- Reconfigure other replicas.
- Tell clients the current primary.

Typical topology:

```text
app clients
  |
Sentinel-aware Redis client
  |
Sentinel quorum
  |
Redis primary + replicas
```

Important details:

- Sentinel quorum detects failure.
- A majority of Sentinels is needed to authorize failover.
- Clients must be Sentinel-aware or use a proxy/service discovery layer.
- Failover can lose writes because Redis replication is asynchronous.
- Do not disable persistence on the primary with auto-restart when data safety matters; a restarted empty primary can create dangerous failure modes.

Use Sentinel when:

- You need HA for a small number of primary-replica Redis instances.
- You do not need automatic sharding.
- Your client stack supports Sentinel.

Use Redis Cluster when:

- You need horizontal sharding across nodes.
- Dataset or throughput exceeds one primary.
- You accept Cluster's hash-slot model and multi-key constraints.

## 12. Redis Cluster

Redis Cluster shards keys across masters using hash slots.

Core ideas:

- There are 16,384 hash slots.
- Each key maps to a slot.
- Each primary owns a subset of slots.
- Replicas can take over if a primary fails.
- Clients should be cluster-aware and follow `MOVED` / `ASK` redirections.

Hash slot:

```text
HASH_SLOT = CRC16(key) mod 16384
```

Example:

```text
user:123:profile     -> some slot
user:456:profile     -> another slot
```

### 12.1 Hash Tags

Hash tags force related keys into the same slot:

```text
user:{123}:profile
user:{123}:cart
user:{123}:settings
```

All keys with `{123}` hash to the same slot. This allows multi-key operations, transactions, and scripts across those keys.

Use hash tags carefully:

- Good: colocate a small group of keys for one user/order/session.
- Bad: put all keys under `{global}` and create one hot slot.

### 12.2 Multi-Key Constraints

Redis Cluster supports multi-key operations only when all keys are in the same hash slot.

This affects:

- `MGET`.
- `SUNION`, `SINTER`.
- `ZUNIONSTORE`.
- `MULTI` / `EXEC`.
- Lua scripts and Redis Functions.

Production design question:

> Which keys must be operated on atomically together?

If the answer is "many unrelated keys," Redis Cluster may not be a good fit for that operation.

## 13. CAP Theorem And Redis

CAP theorem says that during a network partition, a distributed system must choose between consistency and availability.

Redis behavior depends on deployment mode.

### 13.1 Standalone Redis

Standalone Redis is not a distributed database. CAP mostly does not apply inside one process.

Failure mode:

- If the node is reachable, it serves reads/writes.
- If it is down or unreachable, the system is unavailable unless the application has a fallback.

### 13.2 Primary-Replica With Sentinel

Redis primary-replica replication is asynchronous.

During a partition:

- The primary side may accept writes.
- Sentinels on the majority side may promote a replica.
- Old primary writes that did not reach the promoted replica can be lost.

This means Redis Sentinel favors availability and operational failover over strict consistency.

Redis is not CP in the same sense as ZooKeeper, etcd, or a consensus-backed SQL database. It can lose acknowledged writes in certain failover windows.

### 13.3 Redis Cluster

Redis Cluster also uses asynchronous replication. It has availability behavior based on slot ownership, node failure detection, and replica promotion.

Tradeoffs:

- If a primary fails and a replica is promoted, recent writes not replicated can be lost.
- If required slots are unavailable, the cluster may stop serving those slots.
- The system is designed for high throughput and availability, not strict cross-shard serializability.

Practical classification:

```text
Redis standalone: single-node consistency, no distributed CAP choice.
Redis primary-replica: eventually replicated, failover can lose recent writes.
Redis Cluster: sharded, available when slots have healthy owners, async replication.
```

If the business cannot tolerate losing acknowledged writes, use Redis only as a derived/cache layer or combine it with a durable source of truth. For stronger distributed consistency, use a database built around consensus or synchronous quorum writes.

## 14. Hotspot Problem

A Redis hotspot happens when too much traffic targets one key, one hash slot, one shard, one command path, or one large object.

Hotspot types:

| Type | Example | Symptom |
|---|---|---|
| Hot key | `product:iphone:stock` read millions/sec | One node CPU/network spikes |
| Hot slot | Many keys share `{global}` hash tag | One cluster shard overloaded |
| Big key | One set has 50 million members | Slow commands, memory pressure |
| Hot command | `SMEMBERS huge:set` | Event loop stalls |
| Hot expiration | Millions of keys expire at same timestamp | Latency spikes |
| Hot write counter | Global `INCR views:total` | Single-thread bottleneck |

### 14.1 Detecting Hotspots

Use:

- `INFO commandstats`.
- `INFO memory`.
- `SLOWLOG GET`.
- `LATENCY DOCTOR`.
- `redis-cli --bigkeys`.
- `redis-cli --hotkeys` when LFU tracking is enabled.
- Client-side metrics by command and key pattern.
- Node-level CPU, network, memory, and replication lag.
- Cluster slot metrics.

Look for:

- One node much hotter than others.
- One command dominating latency.
- Large values.
- Large collections.
- High output buffer memory.
- Sudden expiration spikes.
- Repeated retries after failover or timeout.

### 14.2 Hot Key Mitigation

#### Read Hot Key

Problem:

```text
GET product:123
```

The key is read so often that one Redis node becomes overloaded.

Solutions:

1. Local in-process cache with short TTL.
2. CDN or edge cache if data is public.
3. Client-side request coalescing so only one request refreshes the key.
4. Replicas for stale-tolerant reads.
5. Duplicate the key across N shards and randomly read one copy.
6. Precompute and push data closer to consumers.

Example replicated copies:

```text
product:123:copy:0
product:123:copy:1
product:123:copy:2
product:123:copy:3
```

Reads choose a random copy. Writes update all copies or update primary and asynchronously fan out.

Tradeoff: duplication improves read throughput but complicates consistency.

#### Write Hot Counter

Problem:

```text
INCR video:999:views
```

All writes hit one key.

Solution: sharded counter.

```text
INCR video:999:views:shard:00
INCR video:999:views:shard:01
...
INCR video:999:views:shard:63
```

Write path:

```text
shard = hash(request_id or user_id) % 64
INCR video:999:views:shard:{shard}
```

Read path:

```text
sum MGET video:999:views:shard:00..63
```

For high read volume, periodically aggregate into:

```text
video:999:views:total
```

Tradeoff: write scalability improves; exact read needs fan-in or background aggregation.

#### Hot Slot In Cluster

Problem:

```text
cart:{global}:user:1
cart:{global}:user:2
cart:{global}:user:3
```

All keys share the same hash tag and land on one slot.

Fix:

```text
cart:{user:1}
cart:{user:2}
cart:{user:3}
```

or no hash tag unless multi-key operations need it.

#### Big Key

Problem:

```text
SMEMBERS followers:celebrity_user
```

One key holds too many members.

Solutions:

- Split by bucket: `followers:user:123:bucket:00`.
- Use sorted sets by time buckets.
- Page with `SSCAN` / `ZSCAN` instead of returning everything.
- Store relationship edges in a durable database and cache pages.
- Precompute top/recent subsets only.

Production rule:

> Never fetch or mutate an unbounded collection in a user request path.

### 14.3 Cache Stampede And Hot Misses

Cache stampede happens when many clients miss the same key and all rebuild it.

Solutions:

- TTL jitter.
- Soft TTL plus background refresh.
- Single-flight request coalescing.
- Lock around rebuild with timeout.
- Serve stale value while refresh happens.
- Prewarm critical keys.

Example soft TTL value:

```json
{
  "data": "...",
  "soft_expire_at": 1716800000,
  "hard_expire_at": 1716800300
}
```

If soft expired, one worker refreshes. Others keep serving stale until hard expiry.

## 15. Bloom Filters And Probabilistic Structures

### 15.1 Bloom Filter Mental Model

A Bloom filter answers:

> Have I probably seen this item before?

It can return:

- Definitely not present.
- Probably present.

It has:

- False positives.
- No false negatives, assuming the filter is used correctly and not corrupted.

This is useful when checking a slow or expensive source.

### 15.2 Cache Penetration Problem

Problem:

Attackers or normal traffic request many missing IDs:

```text
GET product:invalid_999999
```

Redis misses. Database misses. The database gets overloaded by non-existent keys.

Solution:

1. Add all valid product IDs to a Bloom filter.
2. On request, check Bloom filter first.
3. If Bloom says "not present," reject without hitting DB.
4. If Bloom says "probably present," check Redis cache or DB.

Flow:

```text
request product_id
  |
BF.EXISTS bf:product_ids product_id
  |
  +-- no  -> return 404 / reject
  |
  +-- yes -> GET cache
              |
              +-- hit  -> return
              +-- miss -> read DB, cache result
```

Example commands:

```text
BF.RESERVE bf:product_ids 0.001 10000000
BF.ADD bf:product_ids product_123
BF.EXISTS bf:product_ids product_123
```

Tradeoffs:

- Lower DB load for invalid IDs.
- Some false positives still reach Redis/DB.
- You must size expected capacity and error rate.
- Standard Bloom filters do not support deletion safely.

If you need deletion, consider Cuckoo filters or rebuilding the Bloom filter periodically from the source of truth.

### 15.3 Other Probabilistic Structures

| Structure | Question answered | Use case |
|---|---|---|
| Bloom filter | Is item probably present? | Cache penetration, dedupe precheck |
| Cuckoo filter | Is item probably present, with delete support? | Dynamic membership |
| HyperLogLog | How many unique items approximately? | DAU, unique IPs |
| Count-Min Sketch | How frequent is this item approximately? | Event frequency, abuse detection |
| Top-K | What are the likely most frequent items? | Trending products, hot keys |
| t-digest | What are approximate percentiles? | Latency, price, metric distribution |

Use probabilistic structures when exactness is expensive and approximate answers are acceptable.

## 16. Real-World Problem Solving Patterns

### 16.1 Cache-Aside

Most common Redis pattern.

```text
read request
  |
GET cache key
  |
hit -> return
miss -> read DB -> SET cache with TTL -> return
```

Pros:

- Simple.
- DB remains source of truth.
- Redis failures can fall back to DB if load allows.

Cons:

- Cache miss latency.
- Stampede risk.
- Stale data until TTL or invalidation.

Use for:

- Product details.
- User profile summaries.
- Feature config.
- API responses.

### 16.2 Write-Through

```text
write request
  |
write DB
  |
write Redis
  |
return
```

Pros:

- Cache is updated immediately.

Cons:

- Write latency increases.
- Partial failure handling is required.

Use when reads must see fresh data soon after writes.

### 16.3 Write-Behind

```text
write Redis
  |
return
  |
async flush to DB
```

Pros:

- Very low write latency.
- Good for high-throughput buffering.

Cons:

- Data loss risk if Redis fails before flush.
- Requires replay, idempotency, and backpressure.

Use carefully for metrics, logs, and non-critical high-volume events. Do not use casually for payments or orders.

### 16.4 Rate Limiter

Fixed window:

```text
key = rate:login:user:123:202605271030
INCR key
EXPIRE key 60
```

Allow if count <= limit.

Sliding window with sorted set:

```text
ZREMRANGEBYSCORE rate:user:123 0 now-window
ZADD rate:user:123 now request_id
ZCARD rate:user:123
EXPIRE rate:user:123 window
```

Use Lua to make the sliding-window operations atomic.

Tradeoffs:

- Fixed window is simple but can burst at boundaries.
- Sliding window is smoother but costs more memory and CPU.
- Token bucket is often best for APIs with steady refill.

### 16.5 Leaderboard

Use sorted set:

```text
ZINCRBY leaderboard:daily 25 user:123
ZREVRANGE leaderboard:daily 0 99 WITHSCORES
ZREVRANK leaderboard:daily user:123
```

For multiple leaderboards:

```text
leaderboard:game:chess:daily:20260527
leaderboard:game:chess:weekly:2026w22
leaderboard:game:chess:alltime
```

Production concerns:

- TTL old daily boards.
- Limit read page size.
- Avoid rebuilding huge boards in the request path.
- Use background jobs for rollups.

### 16.6 Session Store

```text
SET session:token_abc user_123 EX 1800
```

or:

```text
HSET session:token_abc user_id 123 ip 10.0.0.1 created_at 1716800000
EXPIRE session:token_abc 1800
```

Production concerns:

- Use TLS and ACLs.
- Do not store secrets unnecessarily.
- Rotate session tokens.
- Keep TTL aligned with security policy.
- Use `noeviction` or isolate sessions from volatile cache keys.

### 16.7 Distributed Lock

Basic single-instance lock:

```text
SET lock:order:123 request_abc NX PX 30000
```

Release safely with a Lua script that deletes only if value matches.

Important:

- A lock needs a unique token.
- It must have an expiry.
- Work must finish before expiry or support renewal.
- Redis locks are leases, not magic correctness.
- For strict distributed coordination, use a consensus system such as etcd or ZooKeeper.

Use Redis locks for practical coordination where occasional lease expiry edge cases are handled safely by idempotent operations.

### 16.8 Queue And Stream Processing

Simple queue:

```text
LPUSH queue:emails job_json
BRPOP queue:emails 5
```

Better durable stream:

```text
XADD stream:orders * order_id 123 status paid
XGROUP CREATE stream:orders group:billing $ MKSTREAM
XREADGROUP GROUP group:billing consumer-1 COUNT 10 BLOCK 5000 STREAMS stream:orders >
XACK stream:orders group:billing message_id
```

Use Streams when you need:

- Consumer groups.
- Pending message tracking.
- Replay.
- Multiple consumers.
- Better operational visibility than lists.

Use Kafka/Pulsar when you need:

- Very large retention.
- Partitioned event log as core infrastructure.
- Stronger ecosystem for stream processing.
- High-volume event pipelines beyond Redis memory budget.

### 16.9 URL Shortener With Redis

Redis can accelerate short-code redirects:

```text
GET short:abc123 -> https://example.com/long/path
```

Recommended architecture:

```text
client
  |
redirect service
  |
Redis cache
  |
primary DB for mappings
```

Hotspot handling:

- Popular short URLs become hot keys.
- Use local cache for top URLs.
- Use Redis replicas for reads if stale mapping is acceptable.
- Duplicate extremely hot mappings across shards.
- Keep DB as source of truth.

### 16.10 Inventory Reservation

Redis can coordinate short-lived reservations:

```text
HINCRBY inventory:sku:123 available -1
SET reservation:order:999 sku:123 EX 900
```

Use Lua to atomically check availability and decrement.

Production warning:

- Redis can be a fast reservation layer.
- A durable order/inventory database should reconcile final truth.
- Expired reservations need a compensating job or stream event.

## 17. Operations Redis Solves

| Operation/problem | Redis solution |
|---|---|
| Fast lookup | `GET`, `MGET`, Hash, JSON |
| Atomic counter | `INCR`, `HINCRBY`, `ZINCRBY` |
| Expiring state | TTL, `EXPIRE`, `SET EX` |
| Dedupe | Set, Bloom filter |
| Ranking | Sorted set |
| Queue | List or Stream |
| Pub/Sub | `PUBLISH`, `SUBSCRIBE` |
| Event stream | Streams and consumer groups |
| Rate limiting | Counters, sorted sets, Lua |
| Membership | Set, Bloom/Cuckoo |
| Approx unique count | HyperLogLog |
| Heavy hitters | Top-K, Count-Min Sketch |
| Document lookup | JSON |
| Document search | Redis Query Engine |
| Aggregation | Sorted sets, counters, `FT.AGGREGATE`, TimeSeries |
| Lock/lease | `SET NX PX` plus safe release |
| Idempotency | `SET key value NX EX` |

## 18. Transactions, Lua, And Functions

Redis provides several correctness tools.

### 18.1 `MULTI` / `EXEC`

Commands are queued and then executed sequentially.

```text
MULTI
INCR account:123:version
HSET account:123 balance 500
EXEC
```

Use for simple atomic batches on one Redis node.

### 18.2 `WATCH`

Optimistic locking:

```text
WATCH account:123
GET account:123
MULTI
SET account:123 updated_value
EXEC
```

If the watched key changed, `EXEC` fails.

### 18.3 Lua Scripts

Lua is useful for atomic read-modify-write logic:

- Rate limiting.
- Check-and-set.
- Safe lock release.
- Inventory decrement.
- Multi-step validation.

Production rules:

- Keep scripts bounded.
- Pass keys explicitly.
- Avoid scanning large collections.
- In Cluster, all script keys must be in the same slot.

### 18.4 Redis Functions

Redis Functions package server-side logic better than ad hoc scripts. Use them when logic is reused and should be deployed deliberately.

## 19. Pros And Cons

### 19.1 Pros

- Very low latency for memory-resident data.
- Rich data structures.
- Atomic single-command operations.
- Simple protocol and mature clients.
- TTL and expiration built in.
- Useful as cache, database, queue, stream, search, and probabilistic engine.
- Good ecosystem and operational knowledge.
- Replication, Sentinel, and Cluster options.
- Persistence options for recovery.
- Lua/functions enable atomic server-side workflows.

### 19.2 Cons

- Memory cost can be high.
- Single-threaded command execution means slow commands hurt everyone on that node.
- Asynchronous replication can lose acknowledged writes during failover.
- Cluster multi-key operations require same hash slot.
- Not a relational database.
- Not ideal for unbounded analytics.
- Persistence can cause latency and memory pressure through fork/copy-on-write.
- Big keys are dangerous.
- Poor TTL/eviction policy can cause data loss or outages.
- Search indexes and JSON add memory/write overhead.
- Operationally easy to start, but easy to misuse at scale.

## 20. Production Readiness Checklist

### 20.1 Data Modeling

- Define every access pattern.
- Choose data type by operation, not by habit.
- Design key names consistently.
- Avoid unbounded keys.
- Avoid unbounded command results.
- Add TTLs to cache-like keys.
- Separate critical state from disposable cache data.
- Decide whether Redis is source of truth or derived state.

### 20.2 Memory

- Set `maxmemory`.
- Choose `maxmemory-policy`.
- Leave headroom for replicas, AOF, clients, and fork copy-on-write.
- Track fragmentation ratio.
- Track big keys.
- Use `MEMORY USAGE` for suspicious keys.
- Avoid storing huge serialized blobs when partial updates are needed.

### 20.3 Persistence And Backup

- Decide no persistence vs RDB vs AOF vs both.
- Test restart recovery.
- Test backup restore.
- Monitor AOF rewrite and RDB save failures.
- Put persistence on reliable disk.
- Keep backups outside the Redis node.

### 20.4 High Availability

- Use replicas for HA.
- Use Sentinel or Cluster for failover.
- Run enough Sentinel instances for majority decisions.
- Test failover with clients.
- Monitor replication lag.
- Decide read-from-replica stale-read policy.
- Document expected data-loss window.

### 20.5 Security

- Bind Redis to private networks.
- Use TLS where supported/required.
- Use ACL users and least privilege.
- Disable dangerous commands or restrict admin access.
- Do not expose Redis directly to the internet.
- Rotate credentials.
- Log admin operations.
- Encrypt backups where required.

### 20.6 Clients

- Use a mature Redis client.
- Configure timeouts.
- Configure bounded retries.
- Use connection pooling carefully.
- Use pipelining for batches.
- Avoid huge pipelines that create output buffer pressure.
- Make retry behavior idempotent.
- Use cluster-aware clients for Redis Cluster.
- Use Sentinel-aware clients for Sentinel deployments.

### 20.7 Observability

Monitor:

- CPU per Redis node.
- Memory used and fragmentation.
- Evicted keys.
- Expired keys.
- Hit/miss ratio.
- Command latency.
- Slow log.
- Big keys.
- Hot keys.
- Connected clients.
- Blocked clients.
- Client output buffers.
- Replication lag.
- AOF/RDB status.
- Network throughput.
- Cluster slot balance.

Useful commands:

```text
INFO
INFO memory
INFO commandstats
SLOWLOG GET
LATENCY DOCTOR
MEMORY USAGE key
CLIENT LIST
SCAN
redis-cli --bigkeys
redis-cli --hotkeys
```

Use `MONITOR` only with caution because it is expensive on busy production servers.

### 20.8 Operations

- Run load tests with production-like key distributions.
- Test hot-key behavior.
- Test failover.
- Test resharding.
- Test backup restore.
- Test cold restart time.
- Keep runbooks for memory full, failover, slowlog spike, replication lag, and hot key incidents.
- Pin Redis and client versions deliberately.
- Review command complexity before adding new request-path commands.

## 21. Common Anti-Patterns

### 21.1 Using `KEYS *` In Production

`KEYS` scans the whole keyspace and can block Redis. Use `SCAN` for operational iteration.

### 21.2 Storing Huge Objects

One 100 MB value can block network, memory allocation, replication, and persistence paths. Split or redesign.

### 21.3 Unbounded Collections

Bad:

```text
LPUSH user:123:events every_event_forever
LRANGE user:123:events 0 -1
```

Better:

```text
LPUSH user:123:events recent_event
LTRIM user:123:events 0 999
```

### 21.4 No TTL On Cache Keys

Cache keys without TTL become accidental primary data and eventually create memory incidents.

### 21.5 Mixed Critical And Disposable Data

Do not put sessions, locks, cache, metrics, and critical workflow state in one Redis instance with one eviction policy unless you have explicitly modeled failure behavior.

### 21.6 Treating Redis Failover As Lossless

Redis failover can lose recent writes with asynchronous replication. If that is unacceptable, Redis should not be the only source of truth.

### 21.7 Overusing Distributed Locks

Locks are often a symptom of missing idempotency or poor workflow design. Use locks only with timeouts, unique tokens, safe release, and business-level idempotency.

## 22. Real Production Design Examples

### 22.1 E-Commerce Product Page

Needs:

- Product details.
- Price.
- Inventory hint.
- Reviews summary.
- Personalized recommendations.

Redis model:

```text
product:123:summary          -> JSON or String, TTL
product:123:price            -> String/Hash, short TTL
inventory:sku:123:available  -> String counter or Hash
reviews:product:123:summary  -> Hash
reco:user:456                -> Sorted set
```

Hotspot handling:

- Local cache for top products.
- TTL jitter.
- Request coalescing on cache miss.
- Sharded inventory counters if write-heavy.
- Source of truth remains product/inventory DB.

### 22.2 Login Rate Limiting

Keys:

```text
rate:login:ip:10.0.0.1:minute:202605271030
rate:login:user:123:minute:202605271030
```

Algorithm:

1. Increment IP counter.
2. Increment user counter.
3. Set TTL if new.
4. Block if either crosses threshold.

Use Lua for atomicity.

Production details:

- Use different limits for IP, account, subnet, and device.
- Add allowlists for trusted internal systems.
- Emit metrics for blocked requests.
- Do not rely only on Redis; log to durable storage for abuse analysis.

### 22.3 Real-Time Feed

Fanout-on-write:

```text
ZADD feed:user:target timestamp post_id
```

Pros:

- Fast read.

Cons:

- Celebrity users create huge fanout.

Hybrid design:

- Fanout normal users on write.
- For celebrity users, pull their posts at read time.
- Cache merged feed pages in Redis.

Redis structures:

```text
feed:user:123                 -> sorted set of post IDs
posts:author:celebrity:recent -> sorted set
feedpage:user:123:cursor:x    -> cached JSON page, TTL
```

### 22.4 Payment Idempotency

Problem: client retries can create duplicate charges.

Redis pattern:

```text
SET idempotency:payment:req_abc processing NX EX 86400
```

If set succeeds, process payment. Store final result:

```text
SET idempotency:payment:req_abc '{"status":"success","payment_id":"pay_123"}' EX 86400
```

Production warning:

- Redis can speed idempotency checks.
- Payment result must be stored in durable database.
- If Redis loses the key, DB uniqueness constraints must still prevent duplicates.

### 22.5 API Gateway Quotas

Use token bucket:

```text
quota:tenant:abc
```

Fields:

```text
tokens
last_refill_at
```

Lua script:

1. Refill based on elapsed time.
2. If tokens >= request cost, decrement and allow.
3. Else reject with retry-after.

Production:

- Put tenant-level limits and endpoint-level limits.
- Use local fallback for Redis outage.
- Decide fail-open vs fail-closed per API.

## 23. Redis Vs Other Databases

| Need | Redis fit | Better primary choice |
|---|---|---|
| Low-latency cache | Excellent | Redis |
| Sessions | Excellent | Redis, with HA |
| Leaderboard | Excellent | Redis sorted set |
| Durable financial ledger | Poor as sole DB | Postgres, ledger DB |
| Full-text operational search | Good with indexes | Redis Search, OpenSearch |
| Large historical analytics | Poor | ClickHouse, BigQuery, Snowflake |
| Complex relational queries | Poor | Postgres/MySQL |
| Massive write-heavy wide-column access | Sometimes cache/helper | Cassandra/ScyllaDB |
| Document lookup/query | Good for hot operational docs | MongoDB/Postgres JSONB for broader doc workloads |
| Event streaming backbone | Good for smaller operational streams | Kafka/Pulsar for large event platforms |

## 24. Interview-Style Discussion Session

### Q1. What is Redis?

Redis is an in-memory data structure store. It is commonly used as a cache, but it can also serve as a key-value database, document store, stream processor, Pub/Sub broker, search engine, rate limiter, and probabilistic data structure server.

### Q2. Why is Redis fast?

Redis keeps data in memory, uses efficient data structures, executes commands atomically in a mostly single-threaded event loop, avoids disk on the normal read path, and provides simple O(1), O(log N), or bounded operations for common workloads.

### Q3. Is Redis a database or cache?

It can be both. Whether it is safe as a database depends on durability, replication, failover, data-loss tolerance, backup, and whether the workload fits Redis data structures.

### Q4. How do you solve a Redis hotspot?

First identify whether it is a hot key, hot slot, big key, hot command, or expiration storm. Then use local caching, request coalescing, sharded counters, key splitting, read replicas, duplicate hot keys, TTL jitter, bounded reads, or data-model redesign.

### Q5. How does Redis replication work?

Redis uses primary-replica replication. Writes go to the primary and are streamed to replicas asynchronously by default. Replicas can serve reads, but they may be stale. Failover can lose writes that were acknowledged by the primary but not replicated.

### Q6. How does Redis maintain CAP?

Redis does not provide strict CP semantics in its common primary-replica or Cluster modes. It favors low latency and availability, with asynchronous replication. During partitions and failover, recent acknowledged writes can be lost. Use Redis as a cache/derived store or add a durable source of truth when strict consistency is required.

### Q7. What is Redis Cluster?

Redis Cluster partitions the keyspace into 16,384 hash slots distributed across primary nodes. Replicas provide failover. Cluster-aware clients route requests to the right node and handle redirects.

### Q8. How do multi-key operations work in Cluster?

Multi-key operations require all keys to be in the same hash slot. Hash tags like `{user:123}` can force related keys into one slot, but overusing one tag can create a hot slot.

### Q9. What is a Bloom filter and why use it with Redis?

A Bloom filter checks whether an item is definitely absent or probably present. In Redis, it is useful for cache penetration protection, dedupe prechecks, and large membership checks where exact sets would use too much memory.

### Q10. How do you aggregate in Redis?

Use the structure that matches the aggregation:

- Counters for simple counts.
- Sorted sets for ranks and top lists.
- HyperLogLog for approximate unique counts.
- Count-Min Sketch or Top-K for frequency/heavy hitters.
- TimeSeries for metric rollups.
- `FT.AGGREGATE` for indexed Hash/JSON document aggregation.
- External OLAP systems for large historical analytics.

### Q11. How do you filter/query in Redis?

For direct lookups, query by key. For simple secondary access, maintain sets or sorted sets as indexes. For richer filtering, create Redis Search indexes on Hash or JSON documents and use `FT.SEARCH` or `FT.AGGREGATE`.

### Q12. What are the biggest Redis production risks?

The biggest risks are memory exhaustion, wrong eviction policy, no TTL discipline, big keys, slow commands, hot keys, persistence/fork latency, replication lag, failover data loss, unsafe client retries, and treating Redis as a strongly consistent database when it is not.

## 25. Quick Design Rules

1. Model by access pattern.
2. Keep request-path operations bounded.
3. Avoid big keys.
4. Add TTLs to cache keys.
5. Use `SCAN`, not `KEYS`, for iteration.
6. Use sorted sets for ranking and time-ordered indexes.
7. Use Streams for durable-ish queues and consumer groups.
8. Use Bloom filters for cache penetration.
9. Use HyperLogLog for approximate unique counts.
10. Use Query Engine for indexed document search, not full keyspace scans.
11. Use Cluster for horizontal scale, but design around hash slots.
12. Use Sentinel or Cluster for HA, but document data-loss windows.
13. Use `noeviction` for critical state unless eviction is acceptable.
14. Keep Redis behind private networking with ACL/TLS.
15. Test failover, restore, and hot-key scenarios before production.

## 26. References

- Redis docs home: https://redis.io/docs/latest/
- Redis data types: https://redis.io/docs/latest/develop/data-types/
- Redis replication: https://redis.io/docs/latest/operate/oss_and_stack/management/replication/
- Redis persistence: https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- Redis key eviction: https://redis.io/docs/latest/develop/reference/eviction/
- Redis Sentinel: https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/
- Redis Cluster specification: https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/
- Scale with Redis Cluster: https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/
- Redis latency monitoring: https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency-monitor/
- Redis aggregation syntax: https://redis.io/docs/latest/develop/ai/search-and-query/advanced-concepts/aggregations-syntax/
- Redis Query Engine aggregation command: https://redis.io/docs/latest/commands/ft.aggregate/
- Redis probabilistic data types: https://redis.io/docs/latest/develop/data-types/probabilistic/
