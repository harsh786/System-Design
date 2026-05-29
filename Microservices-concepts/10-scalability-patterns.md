# Scalability Patterns for Microservices

## Table of Contents
- [Horizontal Scaling](#horizontal-scaling)
- [Vertical Scaling](#vertical-scaling)
- [Caching Patterns](#caching-patterns)
- [Database Scaling](#database-scaling)
- [Async Processing](#async-processing)
- [Content Delivery](#content-delivery)
- [Advanced Scaling](#advanced-scaling)

---

## Horizontal Scaling

### 1. Stateless Service Design

**Problem:** Stateful services can't be easily replicated because each instance holds unique session data.

**Solution:** Move all state outside the service. Each request contains all information needed, or state is in external stores.

**Architecture:**
```
    STATEFUL (Bad):                    STATELESS (Good):
    
    ┌─────────┐                        ┌─────────┐
    │ Client   │                        │ Client   │
    └────┬────┘                        └────┬────┘
         │                                  │
         ▼                                  ▼
    ┌─────────┐                        ┌─────────────┐
    │Instance 1│ ← session stuck       │Load Balancer │
    │[session] │                        └──┬───┬───┬──┘
    └─────────┘                           │   │   │
                                          ▼   ▼   ▼
                                    ┌───┐ ┌───┐ ┌───┐
                                    │ 1 │ │ 2 │ │ 3 │ ← any can serve
                                    └─┬─┘ └─┬─┘ └─┬─┘
                                      └─────┼─────┘
                                            ▼
                                    ┌──────────────┐
                                    │ Redis/DB     │
                                    │ (External    │
                                    │  State)      │
                                    └──────────────┘
```

**Implementation:**
- Store sessions in Redis/Memcached
- Use JWT tokens (stateless auth)
- Store uploads in object storage (S3)
- Use external cache for computed results
- No local file system dependencies

**Trade-offs:**
- (+) Infinitely horizontally scalable
- (+) Any instance can handle any request
- (+) Simple load balancing
- (-) External state store becomes critical dependency
- (-) Network latency for state access
- (-) More complex initial design

---

### 2. Session Externalization

**Problem:** HTTP sessions stored in-memory prevent scaling and cause data loss on restart.

**Solution:** Store sessions in distributed cache (Redis, Memcached) or encode in tokens (JWT).

**Architecture:**
```
    ┌────────┐    ┌────────┐    ┌────────┐
    │ Pod 1   │    │ Pod 2   │    │ Pod 3   │
    └───┬────┘    └───┬────┘    └───┬────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
                      ▼
              ┌──────────────┐
              │  Redis Cluster │
              │  (Session Store)│
              │               │
              │  Key: sess:abc │
              │  Val: {userId, │
              │       cart,    │
              │       prefs}   │
              │  TTL: 30min    │
              └──────────────┘
```

**Options:**
| Approach | Latency | Scalability | Complexity |
|----------|---------|-------------|-----------|
| Redis sessions | ~1ms | High | Low |
| JWT (stateless) | 0 (no lookup) | Infinite | Medium (revocation hard) |
| Sticky sessions | 0 | Limited | Low |
| Database sessions | ~5ms | Medium | Low |

---

### 3. Shared-Nothing Architecture

**Problem:** Shared resources create bottlenecks and single points of failure.

**Solution:** Each node/service has its own compute, storage, and memory. No shared state between nodes.

**Architecture:**
```
    Shared-Everything:              Shared-Nothing:
    
    ┌───┐ ┌───┐ ┌───┐             ┌───────┐ ┌───────┐ ┌───────┐
    │ A │ │ B │ │ C │             │ A+DB1 │ │ B+DB2 │ │ C+DB3 │
    └─┬─┘ └─┬─┘ └─┬─┘             └───────┘ └───────┘ └───────┘
      │     │     │                    │         │         │
      └─────┼─────┘                    │ (coordinate via messaging)
            ▼                          └─────────┼─────────┘
    ┌──────────────┐                             ▼
    │ Shared DB     │               ┌──────────────────────┐
    │ (bottleneck)  │               │  Message Broker       │
    └──────────────┘               └──────────────────────┘
```

**Examples:** Kafka partitions, Cassandra nodes, microservices with own databases.

**Trade-offs:**
- (+) Linear scalability
- (+) No single point of contention
- (+) Fault isolation
- (-) Cross-node queries expensive
- (-) Data consistency challenges (eventual consistency)
- (-) More complex operations (joins across nodes)

---

### 4. Auto-scaling Strategies

**Architecture:**
```
    ┌─────────────────────────────────────────────┐
    │             Auto-scaling Controller           │
    │                                              │
    │  Metrics Source → Decision Engine → Action    │
    └──────┬───────────────────────────────┬──────┘
           │                               │
           ▼                               ▼
    ┌──────────────┐               ┌──────────────┐
    │  Prometheus   │               │  Scale Up/    │
    │  CloudWatch   │               │  Scale Down   │
    │  Custom       │               │  Pods/Nodes   │
    └──────────────┘               └──────────────┘
```

| Strategy | Metric | Best For | Lag |
|----------|--------|----------|-----|
| CPU-based | CPU utilization | Compute-intensive | Medium |
| Memory-based | Memory usage | Memory-intensive | Medium |
| Request-based | RPS, latency | Web services | Low |
| Queue-based | Queue depth | Async workers | Low |
| Custom metric | Business KPI | Domain-specific | Varies |
| Predictive | Historical patterns | Known traffic patterns | None (proactive) |
| Schedule-based | Time/cron | Predictable peaks | None |

**Predictive scaling example:**
```
    Traffic Pattern (daily):
    
    Requests │        ╭──────╮
             │       ╱        ╲
             │      ╱          ╲
             │─────╱            ╲─────
             │
             └──────────────────────── Time
             0:00  8:00  12:00  20:00
    
    Predictive: Scale UP at 7:30 (before traffic)
    Reactive:   Scale UP at 8:15 (after overload detected)
```

---

### 5. Load Balancing Algorithms

**Architecture:**
```
    ┌──────────────────────────────────┐
    │          Load Balancer            │
    │                                   │
    │  Algorithm: [configurable]        │
    │                                   │
    └──┬─────┬─────┬─────┬─────┬──────┘
       │     │     │     │     │
       ▼     ▼     ▼     ▼     ▼
    ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐
    │ S1│ │ S2│ │ S3│ │ S4│ │ S5│
    └───┘ └───┘ └───┘ └───┘ └───┘
```

| Algorithm | How It Works | Best For |
|-----------|-------------|----------|
| Round Robin | Sequential rotation | Equal-capacity servers |
| Weighted Round Robin | Proportional to weight | Mixed-capacity servers |
| Least Connections | Route to least busy | Varying request duration |
| Weighted Least Conn | Combines weight + connections | Production default |
| IP Hash | Hash client IP to server | Session affinity (no external state) |
| Consistent Hashing | Hash ring with virtual nodes | Caching layers, minimal redistribution |
| Random | Random server selection | Simple, surprisingly effective |
| Least Response Time | Route to fastest responder | Latency-sensitive |

**Consistent Hashing Detail:**
```
    Hash Ring (0 to 2^32):
    
              Node A (pos: 100)
                 ╱
        ────────●──────────
       ╱                    ╲
      ╱    Request hash:150  ╲
     │     → goes to Node B    │
     │         (next clockwise)│
      ╲                    ╱
       ╲    Node B (pos:200) ╱
        ────────●──────────
                 ╲
              Node C (pos: 300)
    
    Virtual nodes: Each physical node gets 100-200 positions
    on the ring for even distribution.
```

---

## Vertical Scaling

### When to Scale Up vs Scale Out

| Factor | Scale Up (Vertical) | Scale Out (Horizontal) |
|--------|---------------------|----------------------|
| Complexity | Low | High (distributed systems) |
| Cost curve | Exponential at high end | Linear |
| Limit | Hardware ceiling | Theoretically unlimited |
| Downtime | Usually required | Zero (rolling) |
| Data consistency | Easy (single node) | Hard (CAP theorem) |
| Best for | Databases, legacy apps | Stateless services |

### Resource Optimization

**JVM Tuning for Microservices:**
```
# Container-aware JVM settings (Java 11+)
JAVA_OPTS="-XX:+UseContainerSupport \
           -XX:MaxRAMPercentage=75.0 \
           -XX:InitialRAMPercentage=50.0 \
           -XX:+UseG1GC \
           -XX:MaxGCPauseMillis=200 \
           -XX:+UseStringDeduplication \
           -Xss256k"

# For GraalVM native image (fast startup):
# Startup: 50ms vs 2-5s for JVM
# Memory: 50MB vs 200-500MB
```

**Container Resource Management:**
```yaml
resources:
  requests:          # Scheduler guarantee
    cpu: "250m"      # 0.25 CPU cores
    memory: "256Mi"
  limits:            # Hard ceiling
    cpu: "1000m"     # 1 CPU core (throttled beyond)
    memory: "512Mi"  # OOMKilled beyond this

# Rule of thumb:
# requests = average usage
# limits = 2-4x requests (for bursts)
# memory limit = memory request (avoid OOM surprises)
```

---

## Caching Patterns

### 1. Cache-Aside (Lazy Loading)

**Problem:** Database reads are slow and repeated for the same data.

**Solution:** Application checks cache first; on miss, reads from DB and populates cache.

**Architecture:**
```
    ┌──────────┐
    │Application│
    └────┬─────┘
         │
    1. GET key ──────► ┌───────┐
    2. Cache MISS ◄──── │ Cache  │
    3. Query DB ──────► │(Redis) │
    4. SET key ───────► └───────┘
    5. Return data      
         │
         ▼
    ┌──────────┐
    │ Database  │
    └──────────┘
```

```python
def get_user(user_id):
    # 1. Check cache
    cached = redis.get(f"user:{user_id}")
    if cached:
        return deserialize(cached)
    
    # 2. Cache miss - query DB
    user = db.query("SELECT * FROM users WHERE id = ?", user_id)
    
    # 3. Populate cache
    redis.setex(f"user:{user_id}", TTL_SECONDS, serialize(user))
    
    return user
```

**Trade-offs:**
- (+) Only caches data that's actually requested
- (+) Cache failure doesn't break the system (fallback to DB)
- (+) Simple to implement
- (-) Cache miss = 3 round trips (check cache, query DB, set cache)
- (-) Data can be stale (until TTL expires)
- (-) Cold cache problem after restart

---

### 2. Read-Through Cache

**Problem:** Application manages cache population logic, creating duplication.

**Solution:** Cache itself loads data from DB on miss. Application only talks to cache.

**Architecture:**
```
    ┌──────────┐       ┌───────────────┐       ┌──────────┐
    │Application│──────►│  Cache         │──────►│ Database  │
    │           │◄──────│  (Read-Through)│◄──────│           │
    └──────────┘       │               │       └──────────┘
                        │  On MISS:     │
                        │  1. Load from DB│
                        │  2. Store in   │
                        │     cache      │
                        │  3. Return     │
                        └───────────────┘
```

**Trade-offs:**
- (+) Simpler application code
- (+) Consistent caching logic
- (-) Cache library/provider must support data loading
- (-) First request always slow (cache miss)

---

### 3. Write-Through Cache

**Problem:** Cache and DB can get out of sync after writes.

**Solution:** Write to cache and DB synchronously. Cache is always up-to-date.

**Architecture:**
```
    ┌──────────┐       ┌───────────────┐       ┌──────────┐
    │Application│──────►│  Cache         │──────►│ Database  │
    │  WRITE    │       │(Write-Through) │       │           │
    └──────────┘       │               │       └──────────┘
                        │  1. Write cache│
                        │  2. Write DB   │
                        │  3. Ack to app │
                        └───────────────┘
```

**Trade-offs:**
- (+) Cache always consistent with DB
- (+) No stale reads after writes
- (-) Higher write latency (2 writes synchronous)
- (-) Cache fills with data that may never be read
- (-) Not useful alone (combine with read-through)

---

### 4. Write-Behind (Write-Back) Cache

**Problem:** Write-through doubles write latency.

**Solution:** Write to cache immediately, asynchronously flush to DB in batches.

**Architecture:**
```
    ┌──────────┐       ┌───────────────┐       ┌──────────┐
    │Application│──────►│  Cache         │ ─ ─ ─►│ Database  │
    │  WRITE    │◄──────│  (Write-Back)  │       │           │
    │  (fast!)  │  ack  │               │       └──────────┘
    └──────────┘       │  Async batch   │
                        │  flush every   │
                        │  100ms or 100  │
                        │  writes        │
                        └───────────────┘
```

**Trade-offs:**
- (+) Very fast writes (cache speed)
- (+) Batch writes reduce DB load
- (+) Absorbs write spikes
- (-) **Data loss risk** if cache crashes before flush
- (-) Complex failure handling
- (-) Eventual consistency

**Benchmarks:** Write latency: ~1ms (cache) vs ~10-50ms (DB). 10-50x improvement.

---

### 5. Refresh-Ahead Cache

**Problem:** Cache misses cause latency spikes when TTL expires.

**Solution:** Proactively refresh cache entries before they expire.

```
    Timeline:
    
    ├─────────────────────────────────────────────► Time
    │                                              │
    │  Set cache     Refresh trigger    TTL expire │
    │  (TTL=60s)     (at 80% = 48s)    (60s)     │
    │     │               │                │      │
    │     ▼               ▼                ▼      │
    │  [FRESH]         [REFRESH]        [EXPIRED] │
    │                  async reload                 │
    │                  in background                │
```

**Trade-offs:**
- (+) No cache miss latency for hot keys
- (+) Always-fresh data for frequent reads
- (-) Wastes resources refreshing rarely-accessed data
- (-) More complex implementation

---

### 6. Cache Invalidation Strategies

| Strategy | How | Consistency | Complexity |
|----------|-----|-------------|-----------|
| TTL-based | Expire after N seconds | Eventual (bounded) | Low |
| Event-based | Invalidate on write event | Near real-time | Medium |
| Versioned | Cache key includes version | Immediate | Medium |
| Pub/Sub | Broadcast invalidation | Near real-time | High |

**Event-based invalidation:**
```
    ┌──────────┐  write   ┌──────────┐  event    ┌───────┐
    │ Service A │────────►│ Database  │─────────►│ Kafka  │
    └──────────┘          └──────────┘          └───┬───┘
                                                     │
                                            ┌────────┴────────┐
                                            ▼                 ▼
                                    ┌──────────┐      ┌──────────┐
                                    │ Service B │      │ Service C │
                                    │ (invalidate│      │(invalidate│
                                    │  cache)   │      │  cache)   │
                                    └──────────┘      └──────────┘
```

---

### 7. Distributed Caching

```
    ┌──────────────────────────────────────────────────┐
    │              Redis Cluster                         │
    │                                                   │
    │  ┌─────────┐   ┌─────────┐   ┌─────────┐       │
    │  │ Shard 0  │   │ Shard 1  │   │ Shard 2  │       │
    │  │ slots    │   │ slots    │   │ slots    │       │
    │  │ 0-5460   │   │ 5461-    │   │ 10923-   │       │
    │  │          │   │ 10922    │   │ 16383    │       │
    │  │ Master   │   │ Master   │   │ Master   │       │
    │  │  + Replica│   │  + Replica│   │  + Replica│       │
    │  └─────────┘   └─────────┘   └─────────┘       │
    │                                                   │
    │  16384 hash slots distributed across shards      │
    │  Key → CRC16(key) % 16384 → shard               │
    └──────────────────────────────────────────────────┘
```

| Solution | Type | Consistency | Performance |
|----------|------|-------------|-------------|
| Redis Cluster | Distributed, sharded | Eventual | ~0.5ms per op |
| Memcached | Distributed, simple | None (client-side) | ~0.3ms per op |
| Hazelcast | Embedded + distributed | Strong (configurable) | ~0.1ms (embedded) |

---

### 8. Multi-Level Caching

```
    ┌──────────────────────────────────────────────┐
    │  Request Flow                                 │
    │                                               │
    │  Client ──► CDN (L3) ──► App Server          │
    │              │                │                │
    │         Cache HIT?       L1: In-process       │
    │         (static assets)  (Caffeine/Guava)     │
    │              │           ~100μs, 100MB        │
    │              │                │                │
    │              │           Cache MISS?           │
    │              │                │                │
    │              │           L2: Distributed       │
    │              │           (Redis Cluster)       │
    │              │           ~1ms, 100GB          │
    │              │                │                │
    │              │           Cache MISS?           │
    │              │                │                │
    │              │           L3: CDN Edge          │
    │              │           ~5-50ms, PB scale    │
    │              │                │                │
    │              │           Origin (DB)           │
    │              │           ~10-100ms            │
    └──────────────────────────────────────────────┘
```

**Implementation:**
- L1: Caffeine (JVM), node-cache (Node.js) — fastest, smallest
- L2: Redis Cluster — shared across instances
- L3: CloudFront/Cloudflare — geographically distributed

---

### 9. Cache Stampede Prevention

**Problem:** When a hot key expires, hundreds of concurrent requests all miss cache and hit DB simultaneously.

**Architecture:**
```
    Cache key expires:
    
    Without protection:          With locking:
    
    Req1 → MISS → DB query      Req1 → MISS → LOCK → DB query
    Req2 → MISS → DB query      Req2 → MISS → wait...
    Req3 → MISS → DB query      Req3 → MISS → wait...
    Req4 → MISS → DB query      Req1 → SET cache → UNLOCK
    ...100 more → DB overload   Req2 → Cache HIT
                                 Req3 → Cache HIT
```

**Solutions:**

1. **Locking (Mutex):**
```python
def get_with_lock(key):
    value = cache.get(key)
    if value:
        return value
    
    lock = cache.set(f"lock:{key}", "1", nx=True, ex=5)
    if lock:
        value = db.query(key)
        cache.set(key, value, ex=TTL)
        cache.delete(f"lock:{key}")
        return value
    else:
        time.sleep(0.05)  # Wait and retry
        return get_with_lock(key)
```

2. **Probabilistic Early Refresh:**
```python
# Refresh before expiry with probability increasing as TTL approaches
def should_refresh(ttl_remaining, total_ttl):
    # Higher probability as we approach expiry
    return random() < (1 - ttl_remaining / total_ttl) * 0.1
```

3. **Background refresh:** Dedicated thread refreshes hot keys before expiry.

---

### 10. Cache Warming Strategies

**Problem:** Cold cache after deployment/restart causes latency spikes.

**Solutions:**
- **Pre-load on startup:** Query top-N popular items
- **Replicate from peer:** Copy cache from healthy instance
- **Gradual traffic shift:** Don't send 100% traffic to new instance immediately
- **Read-ahead:** Predict and preload based on access patterns

---

## Database Scaling

### 1. Read Replicas

**Problem:** Single database can't handle read + write load.

**Solution:** Replicate data to read-only replicas. Route reads to replicas, writes to primary.

**Architecture:**
```
    ┌──────────────┐
    │  Application  │
    └──┬───────┬───┘
       │       │
    Writes   Reads
       │       │
       ▼       ▼
    ┌──────┐  ┌────────────────────────────┐
    │Primary│  │       Read Replicas         │
    │(Write)│  │                             │
    │       │──┤  ┌────────┐ ┌────────┐    │
    │       │  │  │Replica1│ │Replica2│    │
    │       │  │  └────────┘ └────────┘    │
    └──────┘  └────────────────────────────┘
         │              ▲
         │  Async       │
         │  Replication │
         └──────────────┘
         (lag: 10-100ms)
```

**Trade-offs:**
- (+) Linear read scaling
- (+) Read replicas can be in different regions
- (-) Replication lag (stale reads)
- (-) Write still bottlenecked at primary
- (-) Need read-after-write consistency handling

**Benchmarks:** Typical replication lag: 10-100ms (async), 2-5ms (semi-sync)

---

### 2. Sharding Strategies

**Problem:** Single database can't hold all data or handle all writes.

**Solution:** Partition data across multiple database instances.

```
    ┌─────────────────────────────────────────────────────┐
    │                  Sharding Router                      │
    │           (application or proxy layer)               │
    └──────┬──────────┬──────────┬──────────┬─────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
    ┌──────────┐┌──────────┐┌──────────┐┌──────────┐
    │ Shard 0   ││ Shard 1   ││ Shard 2   ││ Shard 3   │
    │ Users A-F ││ Users G-M ││ Users N-S ││ Users T-Z │
    └──────────┘└──────────┘└──────────┘└──────────┘
```

| Strategy | Method | Pros | Cons |
|----------|--------|------|------|
| Hash-based | hash(key) % N | Even distribution | Resharding is painful |
| Range-based | key ranges (A-F, G-M) | Range queries easy | Hot spots possible |
| Geographic | Region-based | Low latency per region | Cross-region queries hard |
| Directory | Lookup table | Flexible | Lookup table is SPOF |

---

### 3. Consistent Hashing (with Virtual Nodes)

**Problem:** Simple hash(key) % N requires remapping everything when N changes.

**Solution:** Map both keys and nodes to a ring. Key goes to next clockwise node. Adding/removing a node only affects neighbors.

**Architecture:**
```
    Hash Ring (2^32 positions):
    
                    0
                    │
            ┌───────┼───────┐
           ╱        │        ╲
          ╱    N1-v1●         ╲
         │          │     N2-v1●
         │    key1 ──► N2-v1   │
     N3-v2●                    │
         │     N1-v2●          │
         │          │    N3-v1●│
          ╲         │        ╱
           ╲   N2-v2●       ╱
            └───────┼───────┘
                    │
    
    Physical Node 1 → Virtual: N1-v1, N1-v2, N1-v3... (150 vnodes)
    Physical Node 2 → Virtual: N2-v1, N2-v2, N2-v3... (150 vnodes)
    
    Adding Node 4: Only ~1/N of keys move (not all keys!)
```

**Implementation:**
```python
import hashlib
from sortedcontainers import SortedList

class ConsistentHash:
    def __init__(self, nodes, virtual_nodes=150):
        self.ring = SortedList()
        self.node_map = {}
        for node in nodes:
            for i in range(virtual_nodes):
                key = self._hash(f"{node}:{i}")
                self.ring.add(key)
                self.node_map[key] = node
    
    def get_node(self, key):
        h = self._hash(key)
        idx = self.ring.bisect_left(h) % len(self.ring)
        return self.node_map[self.ring[idx]]
    
    def _hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
```

**Trade-offs:**
- (+) Adding/removing node only moves 1/N keys
- (+) Virtual nodes ensure even distribution
- (+) Used by: Cassandra, DynamoDB, Memcached
- (-) More complex than simple modulo
- (-) Replication strategy needed for fault tolerance

---

### 4. Database Connection Pooling

**Problem:** Creating database connections is expensive (~20-50ms). Under load, connection limits are hit.

**Solution:** Maintain a pool of reusable connections.

**Architecture:**
```
    Without pooling:                 With pooling:
    
    Request → new conn → DB         Request → pool.get() → DB
    Request → new conn → DB         Request → pool.get() → DB
    Request → new conn → DB         Request → pool.get() → DB
    ...                              ...
    1000 requests = 1000 conns       1000 requests = 20 conns
    (DB max_connections exceeded!)   (reused efficiently)
```

| Pool | Language | Key Settings |
|------|----------|--------------|
| HikariCP | Java | `maximumPoolSize=10`, `minimumIdle=5` |
| PgBouncer | Postgres proxy | `pool_mode=transaction`, `max_client_conn=1000` |
| ProxySQL | MySQL proxy | Connection multiplexing |
| pgx pool | Go | `MaxConns=25` |

**Sizing formula:**
```
pool_size = (core_count * 2) + effective_spindle_count
# For SSD: pool_size = core_count * 2 + 1
# Typically: 10-30 connections per service instance
```

---

### 5. Materialized Views

**Problem:** Complex queries (joins, aggregations) are slow and repeated.

**Solution:** Pre-compute and store query results. Refresh periodically or on change.

```sql
-- PostgreSQL
CREATE MATERIALIZED VIEW order_summary AS
SELECT 
    customer_id,
    COUNT(*) as total_orders,
    SUM(amount) as total_spent,
    MAX(created_at) as last_order
FROM orders
GROUP BY customer_id;

-- Refresh
REFRESH MATERIALIZED VIEW CONCURRENTLY order_summary;
```

**Trade-offs:**
- (+) Read performance: O(1) lookup vs O(n) aggregation
- (+) Reduces load on source tables
- (-) Storage cost (duplicate data)
- (-) Staleness (refresh lag)
- (-) Write amplification

---

### 6. Denormalization Strategies

**Problem:** Normalized data requires joins → slow reads at scale.

**Solution:** Duplicate data to avoid joins. Accept write complexity for read performance.

```
    Normalized:                    Denormalized:
    
    orders                         orders
    ├── order_id                   ├── order_id
    ├── customer_id ──┐            ├── customer_id
    └── amount        │            ├── customer_name  (duplicated)
                      │            ├── customer_email (duplicated)
    customers    ◄────┘            └── amount
    ├── customer_id
    ├── name                       No JOIN needed for order display!
    └── email
```

**When to denormalize:**
- Read:Write ratio > 10:1
- Joins are in hot path
- Acceptable eventual consistency
- Microservice can't join across service boundaries

---

## Async Processing

### 1. Work Queue Pattern

**Problem:** Synchronous processing blocks the caller and can't handle spikes.

**Solution:** Enqueue work, return immediately, process asynchronously.

**Architecture:**
```
    ┌────────┐  enqueue  ┌─────────────┐  dequeue  ┌──────────┐
    │Producer │──────────►│  Work Queue  │──────────►│ Worker(s) │
    │(API)    │  (fast)   │  (RabbitMQ/  │  (async)  │           │
    │         │◄──── 202  │   SQS/Redis) │           │ Process   │
    └────────┘ Accepted   └─────────────┘           └──────────┘
```

**Benchmarks:** API latency: 5ms (enqueue) vs 2000ms (synchronous processing)

---

### 2. Priority Queue

**Problem:** Not all work items are equal priority.

**Solution:** Multiple queues or priority-aware consumers.

```
    ┌────────────────────────────────────┐
    │         Priority Router             │
    └──┬──────────┬──────────┬───────────┘
       │          │          │
       ▼          ▼          ▼
    ┌──────┐  ┌──────┐  ┌──────┐
    │ HIGH  │  │MEDIUM│  │ LOW   │
    │ Queue │  │Queue │  │ Queue │
    │(paid) │  │      │  │(free) │
    └──┬───┘  └──┬───┘  └──┬───┘
       │          │          │
       ▼          ▼          ▼
    5 workers  3 workers  1 worker
```

---

### 3. Competing Consumers

**Problem:** Single consumer can't keep up with queue depth.

**Solution:** Multiple consumers pull from the same queue. Work is distributed automatically.

```
    ┌─────────────────┐
    │    Queue          │
    │  [m1][m2][m3]... │
    └──┬────┬────┬─────┘
       │    │    │
       ▼    ▼    ▼
    ┌────┐┌────┐┌────┐
    │ C1  ││ C2  ││ C3  │   ← Each message delivered to ONE consumer
    └────┘└────┘└────┘
    
    Scaling: Add more consumers to increase throughput
    Kafka: Partitions = max parallelism
```

---

### 4. Fan-out / Fan-in

**Problem:** Single task needs multiple parallel sub-tasks, then aggregation.

**Architecture:**
```
    Fan-out:                           Fan-in:
    
    ┌────────┐                         ┌────────────┐
    │  Task   │                         │ Aggregator  │
    └────┬───┘                         └──────┬─────┘
         │                                    ▲
    ┌────┼────┐                         ┌─────┼─────┐
    │    │    │                         │     │     │
    ▼    ▼    ▼                         │     │     │
  ┌──┐ ┌──┐ ┌──┐                     ┌──┐ ┌──┐ ┌──┐
  │W1│ │W2│ │W3│ ──── process ────►  │R1│ │R2│ │R3│
  └──┘ └──┘ └──┘                     └──┘ └──┘ └──┘
    
    Example: Image processing
    Fan-out: Split into tiles → process in parallel
    Fan-in: Combine results → return final image
```

---

### 5. Stream Processing

**Problem:** Batch processing has high latency. Need real-time data processing.

**Solution:** Process events continuously as they arrive.

```
    ┌──────────┐     ┌──────────────┐     ┌──────────────┐
    │  Events   │────►│ Stream        │────►│  Output       │
    │  (Kafka)  │     │ Processor     │     │  (DB/Kafka/   │
    │           │     │ (Flink/KS)    │     │   Alert)      │
    └──────────┘     │               │     └──────────────┘
                      │  Operations:  │
                      │  - Filter     │
                      │  - Map        │
                      │  - Aggregate  │
                      │  - Window     │
                      │  - Join       │
                      └──────────────┘
```

| Tool | Latency | Throughput | Complexity |
|------|---------|-----------|-----------|
| Kafka Streams | ms | High | Low (library) |
| Apache Flink | ms | Very High | Medium (cluster) |
| Spark Streaming | seconds | Very High | Medium |
| AWS Kinesis | ms | High | Low (managed) |

---

## Content Delivery

> For a comprehensive CDN deep dive, see [CDN Deep Dive Guide](../CDN/)

### 1. CDN Architecture & Strategies

```
    Without CDN:                     With CDN:
    
    User (Tokyo) ──────────────►    User (Tokyo) ──► Edge (Tokyo)
    │         3000km                │              50km
    │                               │         Cache HIT? → Return
    └──► Origin (US-East)           │         Cache MISS?
         200ms latency                    └──► Origin (US-East)
                                              Set in edge cache
                                         
    Latency: 200ms → 20ms (10x improvement)
```

**CDN Architecture (Points of Presence):**
```
                    ┌─────────────────────────────────────────┐
                    │            CDN Control Plane              │
                    │  (Config propagation, health checks,      │
                    │   certificate management, analytics)      │
                    └──────────────────┬──────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
    ┌────▼─────┐                 ┌─────▼────┐                 ┌─────▼────┐
    │  PoP #1   │                │  PoP #2   │                │  PoP #3   │
    │ (Tokyo)   │                │ (Mumbai)  │                │ (London)  │
    │           │                │           │                │           │
    │ ┌───────┐ │                │ ┌───────┐ │                │ ┌───────┐ │
    │ │Edge   │ │                │ │Edge   │ │                │ │Edge   │ │
    │ │Servers│ │                │ │Servers│ │                │ │Servers│ │
    │ └───┬───┘ │                │ └───┬───┘ │                │ └───┬───┘ │
    │     │     │                │     │     │                │     │     │
    │ ┌───▼───┐ │                │ ┌───▼───┐ │                │ ┌───▼───┐ │
    │ │Cache  │ │                │ │Cache  │ │                │ │Cache  │ │
    │ │(SSD)  │ │                │ │(SSD)  │ │                │ │(SSD)  │ │
    │ └───────┘ │                │ └───────┘ │                │ └───────┘ │
    └─────┬─────┘                └─────┬─────┘                └─────┬─────┘
          │                            │                            │
          │         ┌──────────────────┼────────────────────┐       │
          └────────►│         Origin Shield                  │◄──────┘
                    │   (Regional mid-tier cache)             │
                    └──────────────────┬─────────────────────┘
                                       │
                    ┌──────────────────▼─────────────────────┐
                    │           Origin Server(s)              │
                    │   (S3, ALB, API Gateway, Custom)        │
                    └────────────────────────────────────────┘
```

**Routing Mechanisms:**
| Method | How it Works | Latency | Accuracy |
|--------|-------------|---------|----------|
| **Anycast** | Same IP announced from multiple PoPs, BGP routes to nearest | Lowest | Network-level |
| **GeoDNS** | DNS resolves to nearest PoP IP based on client IP geolocation | Low | IP-based |
| **Latency-based** | DNS resolves based on measured latency probes | Low | Most accurate |
| **Geoproximity** | Weighted distance + bias | Low | Configurable |

**Caching Strategies:**
| Content Type | TTL | Invalidation | Cache-Control Header |
|---|---|---|---|
| Static assets (JS/CSS/images) | 1 year | Cache busting (hash in filename) | `public, max-age=31536000, immutable` |
| HTML pages | 5-60 min | Purge on deploy | `public, max-age=300, s-maxage=3600` |
| API responses | 5-60s | `stale-while-revalidate` | `public, max-age=10, stale-while-revalidate=60` |
| Personalized content | 0 (no cache) | Edge compute | `private, no-store` or edge-personalized |
| Video/Media | 1 day-1 week | Versioned URLs | `public, max-age=604800` |

**Cache Invalidation Approaches:**
```
1. TTL-based: Content expires after time-to-live
   └── Simple but stale data during TTL window

2. Purge/Invalidation API: Explicitly remove from cache
   └── CloudFront: CreateInvalidation API (up to 3000 paths)
   └── Cloudflare: Purge by URL, tag, prefix, or everything

3. Cache Tags: Tag content, purge by tag
   └── "Purge all product-images" → removes all tagged content

4. Versioned URLs: /v2/styles.css or /styles.abc123.css
   └── Never stale, old versions naturally expire

5. stale-while-revalidate: Serve stale, refresh async
   └── Best UX: instant response + freshness in background
```

**Edge Computing (Compute at CDN Edge):**
```
    Traditional:                    Edge Compute:
    
    User ──► CDN ──► Origin         User ──► CDN Edge ──► (compute here!)
                     (compute)                    │
                     (200ms RTT)                  ├── A/B testing
                                                 ├── Geo-personalization
                                                 ├── Auth token validation
                                                 ├── URL rewriting
                                                 ├── Image optimization
                                                 └── API response assembly
```

| Platform | Runtime | Cold Start | Memory | Use Case |
|----------|---------|-----------|--------|----------|
| Cloudflare Workers | V8 Isolates | 0ms | 128MB | API logic, auth, routing |
| AWS Lambda@Edge | Node.js/Python | ~50ms | 128MB-10GB | Request/response manipulation |
| AWS CloudFront Functions | JS (limited) | <1ms | 2MB | Lightweight transforms |
| Fastly Compute | Wasm | <1ms | Varies | High-performance edge apps |
| Vercel Edge Functions | V8 | 0ms | 128MB | Next.js middleware, API |

**CDN Provider Comparison:**
| Feature | CloudFront | Cloudflare | Akamai | Fastly |
|---------|-----------|-----------|--------|--------|
| PoPs | 450+ | 300+ | 4000+ | 90+ |
| Edge Compute | Lambda@Edge + CF Functions | Workers | EdgeWorkers | Compute@Edge (Wasm) |
| DDoS Protection | AWS Shield | Built-in (unmetered) | Kona | Built-in |
| Instant Purge | ~60s (or instant with tags) | ~30s global | <5s | <150ms |
| WebSocket Support | Yes | Yes | Yes | Yes |
| Video Streaming | MediaStore + CF | Stream | Adaptive Media | Yes |
| Pricing Model | Per-request + transfer | Flat (unlimited bandwidth) | Contract | Per-request |
| Best For | AWS ecosystem | Developer simplicity | Enterprise scale | Real-time purge |

**CDN in Microservices Architecture:**
```
    ┌────────────────────────────────────────────────────────────┐
    │  Client (Browser/Mobile)                                   │
    └──────────────────────────┬─────────────────────────────────┘
                               │
    ┌──────────────────────────▼─────────────────────────────────┐
    │  CDN Layer                                                  │
    │  ├── Static assets (JS, CSS, images, fonts)                │
    │  ├── Pre-rendered HTML (SSG pages)                          │
    │  ├── API response caching (GET /products, /catalog)        │
    │  └── Edge functions (auth, A/B tests, geo-routing)         │
    └──────────────────────────┬─────────────────────────────────┘
                               │ Cache MISS only
    ┌──────────────────────────▼─────────────────────────────────┐
    │  API Gateway / Load Balancer                               │
    └──────────────────────────┬─────────────────────────────────┘
                               │
    ┌──────────────────────────▼─────────────────────────────────┐
    │  Microservices (Product, Order, User, etc.)                │
    └────────────────────────────────────────────────────────────┘
    
    Cache hit ratio target: >90% for static, >60% for API responses
    Origin offload: 70-95% of requests never reach your services
```

**Key Metrics to Monitor:**
- **Cache Hit Ratio (CHR):** Target >90% overall
- **Origin Offload:** % of requests served from edge
- **Time to First Byte (TTFB):** <50ms from edge
- **Purge Propagation Time:** Time for invalidation to reach all PoPs
- **Error Rate at Edge:** 5xx responses from origin
- **Bandwidth Savings:** TB served from cache vs origin

---

### 2. Pagination Patterns

| Pattern | Method | Pros | Cons |
|---------|--------|------|------|
| Offset | `?page=3&size=20` | Simple, jump to page | Slow for large offsets, inconsistent with inserts |
| Cursor | `?cursor=abc123&size=20` | Consistent, performant | Can't jump to page |
| Keyset | `?after_id=500&size=20` | Fast (index scan) | Only forward/backward |

**Cursor-based (recommended for APIs):**
```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTAwfQ==",
    "has_more": true
  }
}
```

**Keyset (best performance):**
```sql
-- Instead of: SELECT * FROM orders OFFSET 10000 LIMIT 20
-- Use:
SELECT * FROM orders 
WHERE id > :last_seen_id 
ORDER BY id 
LIMIT 20;
-- Uses index, O(1) regardless of page depth
```

---

### 3. API Response Compression

```
    Client                          Server
    │                               │
    │  Accept-Encoding: gzip, br    │
    │──────────────────────────────►│
    │                               │
    │  Content-Encoding: br         │
    │  (Brotli compressed)          │
    │◄──────────────────────────────│
    │                               │
    
    Compression ratios (JSON):
    - gzip:   60-70% reduction
    - Brotli: 70-80% reduction (slower compression, faster decompression)
    - zstd:   65-75% reduction (fastest)
```

---

## Advanced Scaling

### 1. Cell-Based Architecture

**Problem:** Monolithic infrastructure means one failure affects all users.

**Solution:** Partition infrastructure into independent cells. Each cell serves a subset of users.

**Architecture:**
```
    ┌─────────────────────────────────────────────────┐
    │              Cell Router                          │
    │  (Maps user/tenant to cell)                      │
    └──────┬──────────┬──────────┬────────────────────┘
           │          │          │
           ▼          ▼          ▼
    ┌──────────┐┌──────────┐┌──────────┐
    │  Cell 1   ││  Cell 2   ││  Cell 3   │
    │           ││           ││           │
    │ Users 1-1M││Users 1M-2M││Users 2M-3M│
    │           ││           ││           │
    │ ┌───────┐││ ┌───────┐││ ┌───────┐│
    │ │Compute ││││Compute ││││Compute ││
    │ │Cache   ││││Cache   ││││Cache   ││
    │ │DB      ││││DB      ││││DB      ││
    │ │Queue   ││││Queue   ││││Queue   ││
    │ └───────┘││ └───────┘││ └───────┘│
    └──────────┘└──────────┘└──────────┘
    
    Blast radius: 1 cell failure = 1/N users affected
    Used by: AWS (availability zones), Slack, Azure
```

**Trade-offs:**
- (+) Fault isolation (blast radius = 1 cell)
- (+) Independent scaling per cell
- (+) Can test changes on single cell
- (-) Cross-cell communication expensive
- (-) Operational complexity (N deployments)
- (-) Cell sizing and rebalancing

---

### 2. Multi-Region Deployment

**Architecture:**
```
    ┌────────────────────────────────────────────┐
    │           Global Load Balancer              │
    │     (Route53 / CloudFlare / Akamai)        │
    │     Latency-based / Geo routing            │
    └────┬──────────────┬──────────────┬─────────┘
         │              │              │
         ▼              ▼              ▼
    ┌─────────┐   ┌─────────┐   ┌─────────┐
    │US-East   │   │EU-West   │   │AP-South  │
    │          │   │          │   │          │
    │ Services │   │ Services │   │ Services │
    │ Cache    │   │ Cache    │   │ Cache    │
    │ DB(write)│   │DB(replica)│   │DB(replica)│
    └─────────┘   └─────────┘   └─────────┘
         │              │              │
         └──────────────┼──────────────┘
                        │
              Cross-region replication
              (async, 50-200ms lag)
```

**Patterns:**
- **Active-Passive:** One region handles writes, others are read replicas
- **Active-Active:** All regions handle writes (conflict resolution needed)
- **Follow-the-sun:** Traffic shifts with time zones

---

### 3. Geo-Routing and Latency-Based Routing

```
    User Location → DNS Query → Route to nearest region
    
    User in Tokyo:
    ├── ap-northeast-1: 5ms    ← SELECTED
    ├── us-east-1: 150ms
    └── eu-west-1: 250ms
    
    Strategies:
    - GeoDNS: Route by geographic location
    - Latency-based: Route by measured latency
    - Failover: Route to backup if primary unhealthy
    - Weighted: Distribute by percentage (canary)
```

---

### 4. Connection Multiplexing

**Problem:** Each microservice-to-microservice call creates TCP connections. At scale: millions of connections.

**Solution:** Multiplex many logical requests over fewer physical connections.

```
    Without multiplexing:           With multiplexing (HTTP/2, gRPC):
    
    Request 1 → [TCP conn 1]       Request 1 ─┐
    Request 2 → [TCP conn 2]       Request 2 ─┤─── [Single TCP conn]
    Request 3 → [TCP conn 3]       Request 3 ─┤    (multiplexed streams)
    ...                             Request N ─┘
    1000 req = 1000 connections     1000 req = 1-10 connections
```

**gRPC:** Built-in HTTP/2 multiplexing. Single connection handles thousands of concurrent RPCs.

---

### 5. gRPC Streaming for High Throughput

```
    Unary:              Server Streaming:      Bidirectional:
    
    Client──req──►Srv   Client──req──►Srv     Client◄──────►Server
    Client◄──res──Srv   Client◄──res1──Srv    Stream in both
                        Client◄──res2──Srv    directions
                        Client◄──res3──Srv    simultaneously
    
    Use cases:
    - Server stream: Real-time feed, large result sets
    - Client stream: File upload, telemetry
    - Bidirectional: Chat, gaming, live collaboration
```

**Benchmarks:** gRPC vs REST:
- Serialization: 5-10x faster (protobuf vs JSON)
- Payload size: 3-5x smaller
- Latency: 2-3x lower (HTTP/2, binary, multiplexing)

---

### 6. Reactive / Non-blocking I/O

**Problem:** Thread-per-request model wastes resources waiting for I/O.

**Solution:** Non-blocking I/O with event loop. One thread handles thousands of concurrent requests.

**Architecture:**
```
    Thread-per-request:              Reactive (Event Loop):
    
    Thread 1: [████░░░░████]         Thread 1: [████████████████]
    Thread 2: [████░░░░████]           (no idle waiting)
    Thread 3: [████░░░░████]         
    ...200 threads                   Event Loop:
    (░ = waiting for I/O)            ┌─────────────────────┐
    (█ = actual work)                │ Req1 → DB call      │
                                     │ Req2 → HTTP call    │
    200 threads × 1MB stack          │ Req1 ← DB response  │
    = 200MB just for stacks          │ Req3 → Cache call   │
                                     │ Req2 ← HTTP response│
                                     └─────────────────────┘
                                     2-4 threads, handles 10K+ concurrent
```

| Framework | Language | Model |
|-----------|----------|-------|
| Project Reactor / WebFlux | Java | Reactive Streams |
| Vert.x | Java/Kotlin | Event Loop |
| RxJava | Java | Observable |
| Node.js | JavaScript | Event Loop |
| Netty | Java | NIO |
| Go (goroutines) | Go | Green threads + scheduler |

**Benchmarks:**
- Tomcat (thread-per-request): ~200 concurrent connections per instance
- WebFlux (reactive): ~10,000+ concurrent connections per instance
- Memory: 200MB vs 50MB for same throughput

---

### 7. Backpressure in Reactive Systems

**Problem:** Fast producer overwhelms slow consumer → OOM, crashes, data loss.

**Solution:** Consumer signals capacity to producer. Producer slows down or buffers.

**Architecture:**
```
    Without backpressure:            With backpressure:
    
    Producer: 10K msg/s              Producer: 10K msg/s
         │                                │
         ▼                                ▼
    Consumer: 1K msg/s               Consumer: 1K msg/s
    Buffer grows → OOM!              Signal: "I can take 1000"
                                     Producer: slows to 1K msg/s
                                     OR: buffers with overflow strategy
```

**Strategies:**
| Strategy | Behavior | Use Case |
|----------|----------|----------|
| Buffer | Queue excess, bounded | Burst absorption |
| Drop | Discard excess | Metrics, telemetry |
| Latest | Keep only newest | UI updates |
| Error | Signal failure | Critical data |
| Rate limit | Throttle producer | API gateways |

**Reactive Streams spec:**
```java
// Publisher produces items
// Subscriber requests N items (backpressure signal)
subscriber.onSubscribe(subscription);
subscription.request(100); // "I can handle 100 items"
// Publisher sends at most 100 items
// Subscriber requests more when ready
```

---

## Summary: Scaling Decision Matrix

| Bottleneck | First Try | Then Try | Advanced |
|-----------|-----------|----------|----------|
| CPU | HPA (scale out) | Optimize code, async | Reactive I/O |
| Memory | VPA, optimize | Distributed cache | Stream processing |
| Database reads | Read replicas + cache | Materialized views | CQRS |
| Database writes | Connection pooling | Sharding | Event sourcing |
| Network | gRPC, compression | CDN, edge | Multi-region |
| Single service | Horizontal scale | Decompose | Cell architecture |
| Cold start | Cache warming | Predictive scaling | Keep-alive |
| Queue backup | Competing consumers | Priority queues | KEDA autoscale |

---

## Key Numbers to Remember

| Metric | Value |
|--------|-------|
| Redis GET | ~0.5ms |
| Database query (indexed) | ~1-5ms |
| Database query (full scan) | ~100-1000ms |
| Cross-AZ network | ~1-2ms |
| Cross-region network | ~50-200ms |
| HTTP connection setup | ~20-50ms |
| gRPC (reused conn) | ~1-5ms |
| CDN cache hit | ~5-20ms |
| SSD random read | ~0.1ms |
| HDD random read | ~10ms |
| 1GB network transfer (10Gbps) | ~1s |
| Kafka produce | ~2-5ms |
| Kafka consume (batched) | ~1ms per message |
