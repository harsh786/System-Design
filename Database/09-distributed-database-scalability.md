# Distributed Database & Scalability Problems (Problems 171-185)

## Staff Architect Level - Sharding, Replication, CAP Theorem, Global Scale

---

## Problem 171: Sharding Strategy Selection

**Difficulty:** Expert | **Frequency:** Very High

**Problem:** Your monolithic PostgreSQL has 2TB of data, 50K QPS, and growing 10% monthly. Design a sharding strategy.

### Sharding Approaches:

**1. Hash-Based Sharding (Most Common)**
```
Shard = hash(shard_key) % num_shards

Example: user_id based sharding
shard_id = hash(user_id) % 16  →  16 shards

Pros:
- Even data distribution
- Predictable routing (no lookup needed)
- Simple implementation

Cons:
- Resharding is expensive (all data must move)
- Cross-shard queries are difficult
- Hot users still land on one shard
```

**2. Range-Based Sharding**
```
Shard based on value range:
- Shard 1: user_id 1-1M
- Shard 2: user_id 1M-2M
- Shard 3: user_id 2M-3M

Pros:
- Range queries stay within one shard
- Easy to add new shards (just extend range)
- Logical data locality

Cons:
- Uneven distribution (some ranges hotter)
- Sequential IDs create hotspots on latest shard
```

**3. Directory-Based Sharding**
```sql
-- Lookup table maps entity → shard
CREATE TABLE shard_directory (
    entity_id UUID PRIMARY KEY,
    shard_id INT NOT NULL
);

Pros:
- Maximum flexibility (can rebalance individual entities)
- No constraints on shard key

Cons:
- Extra lookup on every query
- Directory becomes single point of failure
- Must be cached (Redis) for performance
```

**4. Geographic Sharding**
```
- US users → US shard cluster
- EU users → EU shard cluster
- APAC users → APAC shard cluster

Pros:
- Data locality (low latency for users)
- GDPR compliance (data stays in region)
- Natural partition for traffic

Cons:
- Cross-region queries (global reports)
- Users who travel
```

### Shard Key Selection Criteria:

| Criterion | Good Shard Key | Bad Shard Key |
|-----------|---------------|---------------|
| High cardinality | user_id, order_id | status (only 5 values) |
| Even distribution | UUID, hash | sequential ID |
| Query isolation | Matches most WHERE clauses | Requires cross-shard joins |
| Growth pattern | Doesn't create hotspots | timestamp (all writes to latest shard) |

---

## Problem 172: Cross-Shard Query Patterns

**Difficulty:** Expert | **Frequency:** Very High

**Problem:** Data is sharded by user_id, but you need to query by email or order_id.

**Solution 1: Global Secondary Index**
```sql
-- Separate lookup table (can be its own service)
CREATE TABLE email_to_user_shard (
    email VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL,
    shard_id INT NOT NULL
);

-- Flow: Search by email
-- 1. Query email_to_user_shard → get shard_id
-- 2. Query specific shard → get user data
```

**Solution 2: Scatter-Gather**
```
-- When you don't know the shard:
-- 1. Send query to ALL shards in parallel
-- 2. Each shard returns matching results
-- 3. Application merges/sorts results

-- Example: "Find all orders > $1000 in last 24 hours"
-- Must query all shards, merge results, apply global sort/limit

Performance: O(num_shards) latency (parallelized)
Acceptable for: Analytics, admin queries, search
Unacceptable for: User-facing hot path
```

**Solution 3: Dual-Write with Different Shard Key**
```
-- Write order to TWO places:
-- 1. User shard (for "my orders" queries)
-- 2. Order shard (for order_id lookups)

-- Or use CDC to maintain secondary indexes asynchronously
User Service (shard by user_id) → CDC → Order Lookup Service (shard by order_id)
```

**Solution 4: Broadcast Tables (Reference Data)**
```sql
-- Small, rarely-changing tables replicated to ALL shards
-- Examples: countries, currencies, categories, feature flags
-- Every shard has a full copy → JOINs work locally
```

---

## Problem 173: Replication Topologies

**Difficulty:** Hard | **Frequency:** Very High

### Single-Leader (Primary-Replica)
```
[Primary] ──write──► [Replica 1] (sync)
           ──write──► [Replica 2] (async)
           ──write──► [Replica 3] (async)

- All writes go to primary
- Reads distributed across replicas
- Sync replica: Zero data loss (RPO=0) but slower writes
- Async replica: Faster writes but potential data loss on failover
```

### Multi-Leader (Active-Active)
```
[Leader 1 (US)] ◄──►  [Leader 2 (EU)]
      │                     │
[Replica 1a]          [Replica 2a]

- Both accept writes
- Asynchronous conflict resolution needed
- Use cases: Multi-region, offline-first apps

Conflict Resolution Strategies:
1. Last-Write-Wins (LWW) — Simple but loses data
2. Custom merge logic — Application-specific
3. CRDTs — Mathematically convergent data types
```

### Leaderless (Dynamo-style)
```
Write to W nodes, Read from R nodes
Quorum: W + R > N (ensures overlap)

Example: N=3, W=2, R=2
- Write succeeds if 2/3 nodes acknowledge
- Read from 2/3 nodes, take most recent version
- Guarantees: If write succeeded, at least one read node has latest

Used by: Cassandra, DynamoDB, Riak
```

---

## Problem 174: CAP Theorem in Practice

**Difficulty:** Expert | **Frequency:** Very High (Architecture interviews)

**CAP Theorem:** In a network partition, you must choose between Consistency and Availability.

**Real-World Trade-offs:**

| System | Choice | Behavior During Partition |
|--------|--------|--------------------------|
| PostgreSQL (single node) | CA | No partition tolerance (single node) |
| PostgreSQL (sync replica) | CP | Writes fail if replica unreachable |
| Cassandra (quorum) | Tunable | CP with W=ALL, AP with W=1 |
| DynamoDB | AP (default) | Eventually consistent reads |
| MongoDB | CP | Primary election, brief unavailability |
| CockroachDB | CP | Unavailable for affected ranges |
| Redis Cluster | AP | Split-brain possible, last-write-wins |

**PACELC Extension (more nuanced):**
```
If Partition:
  Choose Availability or Consistency (PAC)
Else (normal operation):
  Choose Latency or Consistency (ELC)

Examples:
- DynamoDB: PA/EL (Available in partition, Low latency normally)
- CockroachDB: PC/EC (Consistent always, even at cost of latency)
- Cassandra: PA/EL (default) or PC/EC (with strong consistency)
```

---

## Problem 175: Design a Multi-Region Database Architecture

**Difficulty:** Expert | **Frequency:** Very High

**Requirements:** Users in US, EU, APAC. < 50ms read latency. Strong consistency for writes.

**Architecture Option 1: Single Primary + Regional Read Replicas**
```
                 ┌─────────────┐
                 │  Primary    │
                 │  (US-East)  │
                 └──────┬──────┘
                        │ async replication
          ┌─────────────┼─────────────┐
          │             │             │
    ┌─────┴─────┐ ┌─────┴─────┐ ┌────┴──────┐
    │ Replica   │ │ Replica   │ │ Replica   │
    │ (EU-West) │ │ (US-West) │ │ (APAC)    │
    └───────────┘ └───────────┘ └───────────┘

Reads: Local replica (low latency)
Writes: Route to US-East primary (high latency for EU/APAC: ~100-200ms)
Consistency: Eventual for reads, strong for writes
```

**Architecture Option 2: CockroachDB / Spanner (Distributed SQL)**
```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Node Group  │   │ Node Group  │   │ Node Group  │
│ (US-East)   │◄─►│ (EU-West)   │◄─►│ (APAC)      │
│ Leaseholder │   │ Follower    │   │ Follower    │
└─────────────┘   └─────────────┘   └─────────────┘

- Data partitioned by region (leaseholder = primary for that range)
- US data has leaseholder in US → fast US writes
- EU data has leaseholder in EU → fast EU writes
- Raft consensus for consistency
- Global transactions possible but expensive (cross-region)
```

**Architecture Option 3: Per-Region Shards with Global Routing**
```sql
-- User's home region determined at signup
CREATE TABLE users (
    user_id UUID,
    home_region VARCHAR(10),  -- 'us', 'eu', 'apac'
    ...
);

-- Route user to their home region's database
-- Global router (DNS or application-level):
-- user in EU → eu-db.example.com
-- user in US → us-db.example.com

-- Cross-region data: Async replication of aggregated/read-only data
```

---

## Problem 176: Consistent Hashing for Shard Routing

**Difficulty:** Hard | **Frequency:** High

**Problem:** Adding/removing shards with simple modulo `hash(key) % N` causes massive data migration.

**Consistent Hashing Solution:**
```
Hash Ring (0 to 2^32):

     Node A (position 1000)
    /                        \
   /                          \
  Node D (position 8000)    Node B (position 3000)
   \                          /
    \                        /
     Node C (position 5500)

Key "user:123" hashes to position 2500 → lands on Node B (next clockwise)
Key "user:456" hashes to position 6000 → lands on Node D (next clockwise)

Adding Node E at position 4000:
- Only keys between 3000-4000 move (from C to E)
- All other keys stay put!
- ~1/N of data moves instead of (N-1)/N
```

**Virtual Nodes (for even distribution):**
```
Each physical node gets 100-200 virtual positions on ring
- Node A: positions [1000, 1500, 3500, 7200, ...]
- Node B: positions [800, 2300, 4100, 6800, ...]

Benefits:
- Even load distribution despite heterogeneous hardware
- Smooth rebalancing when nodes join/leave
- Can assign more vnodes to beefier machines
```

**Implementation in database routing:**
```python
# Application-level shard router
class ConsistentHashRouter:
    def get_shard(self, key):
        hash_val = md5(key) % RING_SIZE
        # Find next node clockwise on ring
        for node in sorted_ring_positions:
            if node.position >= hash_val:
                return node.shard_id
        return sorted_ring_positions[0].shard_id  # Wrap around
```

---

## Problem 177: Data Migration Strategies (Zero-Downtime)

**Difficulty:** Expert | **Frequency:** Very High

**Strategy 1: Dual-Write Migration**
```
Phase 1: Dual-write to old and new database
Phase 2: Backfill historical data to new database  
Phase 3: Verify consistency (shadow reads)
Phase 4: Switch reads to new database
Phase 5: Stop writes to old database
Phase 6: Decommission old database

Timeline: Days to weeks depending on data size
```

**Strategy 2: CDC-Based Migration (Change Data Capture)**
```
┌──────────┐     ┌─────────┐     ┌──────────┐
│  Old DB  │────►│ Debezium│────►│  New DB  │
│ (source) │ WAL │  (CDC)  │event│ (target) │
└──────────┘     └─────────┘     └──────────┘

1. Start CDC from old DB's WAL/binlog
2. Take consistent snapshot + stream changes
3. New DB catches up to real-time
4. Switch traffic (reads first, then writes)
5. Minimal downtime (seconds for final cutover)
```

**Strategy 3: Expand-Contract (for schema changes)**
```sql
-- Step 1: Expand (add new column, keep old)
ALTER TABLE users ADD COLUMN full_name VARCHAR(255);

-- Step 2: Dual-write (application writes to both)
UPDATE users SET full_name = CONCAT(first_name, ' ', last_name) WHERE full_name IS NULL;

-- Step 3: Migrate readers (switch queries to use new column)
-- Verify all services use full_name

-- Step 4: Contract (remove old columns)
ALTER TABLE users DROP COLUMN first_name, DROP COLUMN last_name;
```

---

## Problem 178: Global Unique ID Generation

**Difficulty:** Hard | **Frequency:** Very High

| Approach | Format | Properties | Used By |
|----------|--------|------------|---------|
| UUID v4 | 128-bit random | Non-sequential, unguessable | General purpose |
| UUID v7 | Timestamp + random | Time-ordered, sortable | Modern standard |
| Snowflake | 64-bit: time+machine+seq | Compact, ordered, unique | Twitter, Discord |
| ULID | 128-bit: time+random | Sortable, URL-safe (base32) | Modern APIs |
| KSUID | 160-bit: time+random | Sortable, collision-resistant | Segment |
| Auto-increment | 64-bit sequential | Compact, ordered | Single-node only |

**Snowflake ID Structure:**
```
┌─────────────────────────────────────────────────────────────────┐
│ 0 │ Timestamp (41 bits, ms) │ Machine ID (10) │ Sequence (12) │
└─────────────────────────────────────────────────────────────────┘

- 41 bits timestamp: ~69 years of ms-precision
- 10 bits machine: 1024 unique machines
- 12 bits sequence: 4096 IDs per ms per machine
- Total: ~4M IDs/second per machine
```

**PostgreSQL UUID v7 (time-ordered UUIDs):**
```sql
-- PostgreSQL 17+ has built-in UUIDv7
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT uuidv7()
);

-- Pre-17: Use extension or custom function
CREATE OR REPLACE FUNCTION uuid_v7() RETURNS UUID AS $$
DECLARE
    unix_ts_ms BIGINT;
    uuid_bytes BYTEA;
BEGIN
    unix_ts_ms = EXTRACT(EPOCH FROM clock_timestamp()) * 1000;
    uuid_bytes = substring(int8send(unix_ts_ms) from 3);  -- 6 bytes timestamp
    uuid_bytes = uuid_bytes || gen_random_bytes(10);  -- 10 bytes random
    -- Set version (7) and variant (RFC 4122)
    uuid_bytes = set_byte(uuid_bytes, 6, (get_byte(uuid_bytes, 6) & x'0F'::int) | x'70'::int);
    uuid_bytes = set_byte(uuid_bytes, 8, (get_byte(uuid_bytes, 8) & x'3F'::int) | x'80'::int);
    RETURN encode(uuid_bytes, 'hex')::uuid;
END;
$$ LANGUAGE plpgsql;
```

**Why UUID v7 > UUID v4 for databases:**
- B-tree inserts are sequential (append to end, no random I/O)
- Natural ordering by creation time
- Better buffer pool efficiency (recent inserts are cached)
- UUID v4 causes random page splits → index fragmentation

---

## Problem 179: Read Replica Lag Handling

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Replica is 500ms behind primary. User updates profile, refreshes, sees old data.

**Solution 1: Write-aware routing**
```python
# After write, route reads to primary for N seconds
class SmartRouter:
    def route_query(self, user_id, query_type):
        if query_type == 'write':
            return PRIMARY
        
        last_write = cache.get(f"last_write:{user_id}")
        if last_write and (now - last_write) < 5_seconds:
            return PRIMARY  # Read from primary shortly after write
        
        return RANDOM_REPLICA
```

**Solution 2: Monotonic reads (session consistency)**
```sql
-- Track the LSN of user's last write
-- Route subsequent reads to a replica that has caught up past that LSN

-- PostgreSQL: Check replica position
SELECT pg_last_wal_replay_lsn();  -- Current position on replica
-- If replay_lsn >= user's write_lsn → safe to read here
```

**Solution 3: Synchronous replica for critical paths**
```sql
-- PostgreSQL: synchronous_standby_names
-- Ensures at least one replica is fully up-to-date
-- All confirmed writes are guaranteed readable from sync replica
```

**Monitoring Replica Lag:**
```sql
-- PostgreSQL
SELECT client_addr, state, 
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes,
       NOW() - reply_time AS lag_time
FROM pg_stat_replication;

-- MySQL
SHOW SLAVE STATUS\G
-- Check: Seconds_Behind_Master
```

---

## Problem 180: Database Connection Routing (Read/Write Splitting)

**Difficulty:** Hard | **Frequency:** Very High

**Architecture:**
```
┌──────────┐     ┌─────────────────┐     ┌─────────────────┐
│   App    │────►│   PgBouncer /   │────►│    Primary      │ (writes)
│ Service  │     │   ProxySQL /    │     └─────────────────┘
│          │     │   HAProxy       │     ┌─────────────────┐
│          │     │                 │────►│   Replica 1     │ (reads)
│          │     │  Read/Write     │     └─────────────────┘
│          │     │  Splitter       │     ┌─────────────────┐
│          │     │                 │────►│   Replica 2     │ (reads)
└──────────┘     └─────────────────┘     └─────────────────┘

Rules:
- BEGIN/INSERT/UPDATE/DELETE → Primary
- SELECT (outside transaction) → Random Replica
- SELECT inside write transaction → Primary
- After recent write by same user → Primary (5s window)
```

**Application-Level Routing (Spring/Java example concept):**
```sql
-- Annotate service methods:
-- @Transactional(readOnly = true)  → route to replica
-- @Transactional(readOnly = false) → route to primary

-- Or use connection pool naming:
-- DataSource "primary" → write pool
-- DataSource "replica" → read pool
```

---

## Problem 181: Event-Driven Data Synchronization

**Difficulty:** Expert | **Frequency:** Very High

**Problem:** Microservices need shared data but can't share databases. How to keep data in sync?

**Pattern: CDC → Event Stream → Materialized View**
```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐
│ Service A│     │ Debezium │     │  Kafka   │     │  Service B   │
│ (Orders) │────►│  (CDC)   │────►│  Topic   │────►│ (Analytics)  │
│          │ WAL │          │     │          │     │  Local copy  │
└──────────┘     └──────────┘     └──────────┘     └──────────────┘

Benefits:
- No coupling between services
- Each service has its own optimized data model
- Eventual consistency (acceptable for most use cases)
- Full event history for replay/recovery
```

**Handling Out-of-Order Events:**
```sql
-- Consumer maintains watermark
CREATE TABLE sync_state (
    source VARCHAR(100) PRIMARY KEY,
    last_processed_offset BIGINT NOT NULL,
    last_processed_at TIMESTAMP
);

-- Idempotent event processing:
-- Use event's unique ID + version to detect duplicates/out-of-order
CREATE TABLE local_orders (
    order_id UUID PRIMARY KEY,
    data JSONB NOT NULL,
    source_version BIGINT NOT NULL,  -- Only accept higher versions
    updated_at TIMESTAMP
);

-- Upsert only if newer version:
INSERT INTO local_orders (order_id, data, source_version, updated_at)
VALUES (@id, @data, @version, NOW())
ON CONFLICT (order_id) DO UPDATE
SET data = EXCLUDED.data, source_version = EXCLUDED.source_version, updated_at = NOW()
WHERE local_orders.source_version < EXCLUDED.source_version;
```

---

## Problem 182: Database as a Distributed System — Consensus Protocols

**Difficulty:** Expert | **Frequency:** High (Deep architecture interviews)

**Raft Consensus (used by CockroachDB, TiDB, etcd):**
```
Key concepts:
1. Leader Election: One node elected leader via majority vote
2. Log Replication: Leader sends log entries to followers
3. Safety: Committed entry = replicated to majority
4. Membership Change: Can add/remove nodes safely

Timeline of a write:
1. Client sends write to Leader
2. Leader appends to local log
3. Leader sends AppendEntries RPC to all followers
4. Majority acknowledge → Leader commits entry
5. Leader responds to client "success"
6. Followers apply committed entries

Availability: Tolerates (N-1)/2 failures (3 nodes → 1 failure, 5 nodes → 2 failures)
```

**Paxos (used by Google Spanner):**
```
More complex than Raft but equivalent in theory.
Multi-Paxos optimizes for consecutive proposals by same leader.
Spanner adds TrueTime (GPS + atomic clocks) for global ordering.
```

---

## Problem 183: Handling Database Failover

**Difficulty:** Hard | **Frequency:** Very High

**Automated Failover Components:**
```
┌───────────────┐
│   Patroni /   │  (Cluster Manager)
│   pg_auto_    │
│   failover    │
└───────┬───────┘
        │ monitors health
        │
┌───────┴───────┐     ┌─────────────────┐
│   Primary     │────►│   Sync Replica  │ (promotion candidate)
│   (active)    │     │   (standby)     │
└───────────────┘     └─────────────────┘
        │
        │ async
        ▼
┌─────────────────┐
│  Async Replica  │ (read-only, may lose some data)
└─────────────────┘
```

**Failover Decision Matrix:**

| Scenario | Action | Data Loss Risk |
|----------|--------|----------------|
| Primary crash, sync replica up-to-date | Promote sync replica | None (RPO=0) |
| Primary crash, only async replicas | Promote most advanced async | Possible (RPO>0) |
| Network partition (split brain) | Fencing (STONITH) primary | None if fenced correctly |
| Cascading failure | Circuit breaker, degrade gracefully | Depends |

**Split Brain Prevention:**
```
STONITH: "Shoot The Other Node In The Head"
- When promoting new primary, ENSURE old primary is dead
- Methods: IPMI power off, cloud API terminate instance, watchdog timer
- Without STONITH: Two primaries accept writes → data corruption
```

---

## Problem 184: Multi-Tenancy Database Patterns

**Difficulty:** Hard | **Frequency:** Very High (SaaS)

**Pattern 1: Shared Database, Shared Schema (Row-level isolation)**
```sql
-- All tenants in same table, filtered by tenant_id
CREATE TABLE orders (
    order_id UUID,
    tenant_id UUID NOT NULL,  -- Every table has this
    ...
    PRIMARY KEY (tenant_id, order_id)  -- Tenant-first for partition affinity
);

-- Row-Level Security (PostgreSQL)
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Set tenant context per request:
SET app.current_tenant = 'tenant-123-uuid';
-- All queries automatically filtered — can't access other tenants' data
```

**Pattern 2: Shared Database, Separate Schemas**
```sql
-- Each tenant gets own schema
CREATE SCHEMA tenant_acme;
CREATE TABLE tenant_acme.orders (...);

CREATE SCHEMA tenant_globex;
CREATE TABLE tenant_globex.orders (...);

-- Set search_path per connection:
SET search_path TO tenant_acme, public;
```

**Pattern 3: Separate Database per Tenant**
```
tenant_acme_db → Dedicated PostgreSQL instance
tenant_globex_db → Dedicated PostgreSQL instance

Pros: Complete isolation, easy to scale/migrate individual tenants
Cons: Operational overhead, can't easily query across tenants
Best for: Enterprise customers with strict compliance requirements
```

**Comparison:**

| Pattern | Isolation | Cost | Scalability | Operations |
|---------|-----------|------|-------------|------------|
| Shared schema + RLS | Logical | Lowest | Challenging at scale | Simplest |
| Schema per tenant | Schema-level | Low | Moderate | Moderate |
| DB per tenant | Complete | Highest | Best per-tenant | Complex |

---

## Problem 185: Designing for 99.99% Availability (52 min downtime/year)

**Difficulty:** Expert | **Frequency:** Very High

**Architecture Requirements:**
```
99.99% = 52 minutes downtime per year
99.999% = 5 minutes downtime per year

Components needed:
1. No single point of failure
2. Automated failover (< 30 seconds)
3. Rolling upgrades (zero-downtime deploys)
4. Multi-AZ / Multi-region
5. Chaos testing (regularly kill components)
```

**Database Layer for 99.99%:**
```
┌─────────────────────────────────────────────────────────────┐
│                        Region 1 (Primary)                    │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐           │
│  │ Primary  │────►│  Sync    │     │  Async   │           │
│  │  (AZ-1)  │     │ Replica  │     │ Replica  │           │
│  │          │     │  (AZ-2)  │     │  (AZ-3)  │           │
│  └──────────┘     └──────────┘     └──────────┘           │
│       │                                                      │
│       │ Patroni/Stolon manages failover (< 10s)             │
└───────┼──────────────────────────────────────────────────────┘
        │ async cross-region replication
        ▼
┌─────────────────────────────────────────────────────────────┐
│                     Region 2 (DR)                             │
│  ┌──────────┐     ┌──────────┐                              │
│  │ Standby  │     │  Async   │                              │
│  │ Primary  │     │ Replica  │  ← Promoted if Region 1 dies │
│  └──────────┘     └──────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

**Zero-Downtime Schema Migrations:**
```sql
-- NEVER do this in production:
ALTER TABLE orders ADD COLUMN email VARCHAR(255) NOT NULL;
-- Locks table for duration of rewrite (minutes on large tables)

-- Instead, multi-step safe migration:
-- Step 1: Add nullable column (instant, no rewrite)
ALTER TABLE orders ADD COLUMN email VARCHAR(255);

-- Step 2: Backfill in batches (no lock)
UPDATE orders SET email = (SELECT email FROM users WHERE users.id = orders.user_id)
WHERE order_id BETWEEN @batch_start AND @batch_end;

-- Step 3: Add NOT NULL constraint with CHECK (PostgreSQL 12+, no lock)
ALTER TABLE orders ADD CONSTRAINT orders_email_not_null CHECK (email IS NOT NULL) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT orders_email_not_null;

-- Step 4: Set column NOT NULL (instant after validated constraint)
ALTER TABLE orders ALTER COLUMN email SET NOT NULL;
```

**Connection Draining for Zero-Downtime Failover:**
```
1. Mark old primary as read-only: ALTER SYSTEM SET default_transaction_read_only = on;
2. Wait for in-flight transactions to complete (grace period: 30s)
3. Promote new primary
4. Update DNS/routing to new primary
5. Application reconnects automatically (connection pool retry)
6. Total downtime visible to users: 0-5 seconds
```

---

## Distributed Database Decision Framework

```
┌─────────────────────────────────────────────────────┐
│ Is strong consistency required?                      │
├──────────Yes─────────────────────No─────────────────┤
│                                  │                   │
│ Need global distribution?        │ Cassandra/DynamoDB│
├──Yes──────────────No─────────────│ (AP, eventual)   │
│                   │              │                   │
│ CockroachDB/      │ PostgreSQL   │                   │
│ Spanner/YugaByte  │ + replicas   │                   │
│ (distributed SQL) │              │                   │
│                   │              │                   │
│ Need < 10ms       │              │                   │
│ write latency?    │              │                   │
│ → Not possible    │              │                   │
│   globally        │              │                   │
└─────────────────────────────────────────────────────┘
```
