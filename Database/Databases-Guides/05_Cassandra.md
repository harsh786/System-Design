# Apache Cassandra - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Model & CQL](#data-model--cql)
3. [Storage Engine (LSM Tree)](#storage-engine-lsm-tree)
4. [Consistency & Replication](#consistency--replication)
5. [Partitioning & Token Ring](#partitioning--token-ring)
6. [Compaction Strategies](#compaction-strategies)
7. [Read & Write Paths](#read--write-paths)
8. [Performance Tuning](#performance-tuning)
9. [Anti-Patterns & Best Practices](#anti-patterns--best-practices)
10. [Staff Architect Interview Questions](#staff-architect-interview-questions)
11. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Peer-to-Peer Architecture (No Master)
```
┌─────────────────────────────────────────────────────┐
│                 Cassandra Cluster                     │
│                                                       │
│    ┌────┐     ┌────┐     ┌────┐     ┌────┐         │
│    │Node│←───→│Node│←───→│Node│←───→│Node│         │
│    │ A  │     │ B  │     │ C  │     │ D  │         │
│    └────┘     └────┘     └────┘     └────┘         │
│      ↑          ↑          ↑          ↑             │
│      └──────────┴──────────┴──────────┘             │
│                  Gossip Protocol                      │
│                                                       │
│  Every node is equal (no master/slave)               │
│  Any node can handle any request (coordinator)       │
│  Token ring determines data placement                │
└─────────────────────────────────────────────────────┘

Key properties:
- Masterless: No single point of failure
- Peer-to-peer: All nodes equivalent
- Always writable: AP system (CAP theorem)
- Linear scalability: Add nodes for proportional capacity
- Multi-datacenter: Native cross-DC replication
```

### Gossip Protocol
```
Every second, each node:
1. Picks 1-3 random nodes
2. Sends its gossip state
3. Receives their gossip state
4. Merges state (latest timestamp wins)

State information:
- Node status (UP/DOWN)
- Token ranges owned
- Schema version
- Load information
- Data center/rack placement

Failure detection (Phi Accrual):
- Not binary (up/down) but probabilistic
- phi_convict_threshold = 8 (default)
- Accounts for network latency variance
- Higher phi = slower detection but fewer false positives
```

### Data Distribution (Token Ring)
```
Token Ring (Murmur3 hash: -2^63 to 2^63-1):

        Token 0
          │
     D────┼────A
    /     │     \
   /      │      \
  D       │       A    ← Each node owns a token range
   \      │      /     ← Data placed based on partition key hash
    \     │     /
     C────┼────B
          │
     Token 2^63

With vnodes (virtual nodes):
- Each physical node owns 128-256 vnodes (token ranges)
- Better load distribution
- Faster rebalancing when nodes join/leave
- num_tokens = 256 (default in modern Cassandra)
```

---

## Data Model & CQL

### Primary Key Structure
```sql
CREATE TABLE user_events (
    user_id UUID,
    event_time TIMESTAMP,
    event_type TEXT,
    data TEXT,
    PRIMARY KEY ((user_id), event_time, event_type)
);
-- ((user_id)) = Partition Key (determines which node stores data)
-- event_time, event_type = Clustering Columns (sort order within partition)

-- Compound partition key (for high-cardinality distribution):
CREATE TABLE sensor_data (
    sensor_id TEXT,
    date TEXT,          -- "2024-01-15"
    reading_time TIMESTAMP,
    value DOUBLE,
    PRIMARY KEY ((sensor_id, date), reading_time)
) WITH CLUSTERING ORDER BY (reading_time DESC);
-- Partition = one sensor's data for one day
-- Prevents unbounded partitions (one partition per day)
```

### Data Modeling Principles
```
Cassandra data modeling is QUERY-DRIVEN (not entity-driven):

1. Start with queries (access patterns)
2. Design tables to serve each query
3. Denormalize aggressively (no JOINs!)
4. One table per query pattern

Example: Social media application
Queries:
- Q1: Get user's timeline (latest posts)
- Q2: Get posts by a specific user
- Q3: Get followers of a user
- Q4: Get who a user follows

Tables:
-- Q1: Timeline (fan-out on write)
CREATE TABLE timeline (
    user_id UUID,
    post_time TIMESTAMP,
    post_id UUID,
    author_id UUID,
    content TEXT,
    PRIMARY KEY ((user_id), post_time)
) WITH CLUSTERING ORDER BY (post_time DESC);

-- Q2: User posts
CREATE TABLE user_posts (
    author_id UUID,
    post_time TIMESTAMP,
    post_id UUID,
    content TEXT,
    PRIMARY KEY ((author_id), post_time)
) WITH CLUSTERING ORDER BY (post_time DESC);

-- Q3: Followers
CREATE TABLE followers (
    user_id UUID,
    follower_id UUID,
    followed_at TIMESTAMP,
    PRIMARY KEY ((user_id), follower_id)
);

-- Q4: Following
CREATE TABLE following (
    user_id UUID,
    followed_id UUID,
    followed_at TIMESTAMP,
    PRIMARY KEY ((user_id), followed_id)
);
```

### Collections & UDTs
```sql
-- Collections
CREATE TABLE users (
    id UUID PRIMARY KEY,
    name TEXT,
    emails SET<TEXT>,           -- Unique, unordered
    phone_numbers LIST<TEXT>,   -- Ordered, allows duplicates
    attributes MAP<TEXT, TEXT>  -- Key-value pairs
);

-- User-Defined Types
CREATE TYPE address (
    street TEXT,
    city TEXT,
    zip TEXT,
    country TEXT
);

CREATE TABLE companies (
    id UUID PRIMARY KEY,
    name TEXT,
    headquarters FROZEN<address>,
    offices LIST<FROZEN<address>>
);

-- FROZEN: Serialized as blob (entire value must be overwritten)
-- Non-frozen: Individual field updates possible (higher overhead)
```

### Materialized Views
```sql
CREATE MATERIALIZED VIEW user_by_email AS
    SELECT * FROM users
    WHERE email IS NOT NULL
    PRIMARY KEY (email, user_id);

-- Limitations:
-- - Only one new column in partition key
-- - Must include all PK columns from base table
-- - Cannot include non-PK columns as new PK columns (beyond one)
-- - Performance overhead (async updates, potential inconsistency)
-- - Recommendation: Prefer manual denormalization over MVs in production
```

---

## Storage Engine (LSM Tree)

### Write Path (LSM - Log-Structured Merge Tree)
```
Write Request
     │
     ▼
┌──────────┐
│ Commit   │ ← Sequential write (append-only)
│ Log      │   Durability: survives crash
└────┬─────┘
     │
     ▼
┌──────────┐
│ Memtable │ ← In-memory sorted structure (Red-Black Tree / Skip List)
│ (Active) │   Fast writes: O(log N)
└────┬─────┘
     │ When full (memtable_flush_writers)
     ▼
┌──────────┐
│ SSTable  │ ← Immutable sorted file on disk
│ (Disk)   │   Never modified, only compacted
└──────────┘

SSTable (Sorted String Table) structure:
┌─────────────────────────────────────────┐
│ Data Blocks (sorted partition keys)      │
├─────────────────────────────────────────┤
│ Index (partition key → offset)           │
├─────────────────────────────────────────┤
│ Summary (sampled index entries)          │
├─────────────────────────────────────────┤
│ Bloom Filter (key membership test)       │
├─────────────────────────────────────────┤
│ Compression Info                         │
├─────────────────────────────────────────┤
│ Statistics                               │
├─────────────────────────────────────────┤
│ TOC (Table of Contents)                 │
└─────────────────────────────────────────┘
```

### Read Path
```
Read Request
     │
     ▼
┌──────────────┐
│ Bloom Filter │ ← Quick "definitely not here" check (per SSTable)
│ Check        │   False positive rate: ~1% (configurable)
└──────┬───────┘
       │ (might be here)
       ▼
┌──────────────┐
│ Partition    │ ← Key cache / partition index summary
│ Index        │   Locate partition in SSTable
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Read from:   │
│ 1. Memtable  │ ← Check active + flushing memtables
│ 2. Row Cache │ ← (Optional) cached rows
│ 3. SSTables  │ ← Merge results from multiple SSTables
│              │   (newest timestamp wins)
└──────────────┘

Read amplification:
- Worst case: Read from ALL SSTables (mitigated by Bloom filters)
- Compaction reduces number of SSTables → improves read performance
```

---

## Consistency & Replication

### Tunable Consistency
```
Replication Factor (RF) = Number of copies

Consistency Level (CL) determines how many replicas must respond:

Write CL:
- ANY:    At least one node (including hints) — weakest
- ONE:    One replica
- TWO:    Two replicas
- THREE:  Three replicas
- QUORUM: ⌊RF/2⌋ + 1 replicas
- LOCAL_QUORUM: Quorum in local DC
- EACH_QUORUM: Quorum in each DC
- ALL:    All replicas — strongest

Read CL:
- ONE:    One replica (fastest)
- QUORUM: ⌊RF/2⌋ + 1 replicas
- LOCAL_QUORUM: Quorum in local DC
- ALL:    All replicas (slowest, strongest)

Strong consistency formula:
R + W > RF (read + write quorum > replication factor)
Example: RF=3, W=QUORUM(2), R=QUORUM(2) → 2+2=4 > 3 ✓

Eventual consistency:
R + W ≤ RF
Example: RF=3, W=ONE(1), R=ONE(1) → 1+1=2 ≤ 3 (eventual)
```

### Multi-Datacenter Replication
```
                DC1 (US-East)              DC2 (EU-West)
            ┌─────────────────┐      ┌─────────────────┐
            │  ┌───┐  ┌───┐  │      │  ┌───┐  ┌───┐  │
            │  │N1 │  │N2 │  │      │  │N4 │  │N5 │  │
            │  └───┘  └───┘  │      │  └───┘  └───┘  │
            │       ┌───┐    │      │       ┌───┐    │
            │       │N3 │    │      │       │N6 │    │
            │       └───┘    │      │       └───┘    │
            └─────────────────┘      └─────────────────┘
                    │                         ↑
                    └─── Async replication ───┘

Keyspace replication:
CREATE KEYSPACE myapp WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'us-east': 3,    -- 3 replicas in US-East
    'eu-west': 3     -- 3 replicas in EU-West
};

LOCAL_QUORUM:
- Write acknowledged when quorum achieved in LOCAL DC
- Remote DC replicated asynchronously
- Best for: Low latency with strong local consistency
- Risk: Cross-DC inconsistency window (typically ms to seconds)
```

### Conflict Resolution
```
Last Write Wins (LWW):
- Each cell has a timestamp
- Higher timestamp always wins
- Client clocks must be synchronized (NTP)
- No vector clocks (simpler, but clock skew can cause issues)

Conflict scenarios:
1. Concurrent writes to same cell:
   - Client A writes X at T=100
   - Client B writes Y at T=101
   - Y wins (higher timestamp)
   - If T=same: Larger value wins (byte comparison)

2. Delete + Write race:
   - Delete creates tombstone at T=100
   - Write at T=99 is invisible (tombstone wins)
   - Write at T=101 resurrects data

Tombstones:
- Deletes don't physically remove data immediately
- Tombstone marker with timestamp
- gc_grace_seconds (default 10 days) before physical removal
- Accumulating tombstones = read performance degradation
```

### Lightweight Transactions (LWT - Paxos)
```sql
-- Compare-And-Set (IF clause)
INSERT INTO users (id, email, name)
VALUES (uuid(), 'john@example.com', 'John')
IF NOT EXISTS;  -- Only inserts if email doesn't exist

UPDATE accounts SET balance = 900
WHERE user_id = :id
IF balance = 1000;  -- Only updates if current balance matches

-- Under the hood: 4-round Paxos protocol
-- 1. Prepare (promise)
-- 2. Read current value
-- 3. Propose new value
-- 4. Commit

-- Performance: ~4x slower than regular write (4 network round-trips)
-- Use sparingly: Not designed for high-contention workloads

-- Batching LWTs (same partition only):
BEGIN BATCH
    INSERT INTO users (id, email) VALUES (:id, :email) IF NOT EXISTS;
    INSERT INTO user_by_email (email, id) VALUES (:email, :id) IF NOT EXISTS;
APPLY BATCH;
```

---

## Compaction Strategies

### Size-Tiered Compaction (STCS) - Default
```
Strategy: Merge SSTables of similar size

Trigger: When 4+ SSTables of similar size exist

       [1MB] [1MB] [1MB] [1MB]  ← 4 small SSTables
              │
              ▼
            [4MB]                 ← Merged into 1 medium SSTable

       [4MB] [4MB] [4MB] [4MB]  ← 4 medium SSTables
              │
              ▼
           [16MB]                ← Merged into 1 large SSTable

Pros:
- Good for write-heavy workloads
- Minimal write amplification

Cons:
- Temporary 2x space usage during compaction
- Read amplification (many SSTables to check)
- Not great for time-series (wide partitions)
- Space amplification (old data in multiple SSTables)
```

### Leveled Compaction (LCS)
```
Strategy: Organize SSTables into levels of increasing size

L0: [SSTable] [SSTable]  (flushed from memtable, 160MB)
     │
     ▼ compact into L1
L1: [160MB total, 10 SSTables of 16MB, non-overlapping keys]
     │
     ▼ compact into L2
L2: [1.6GB total, 100 SSTables of 16MB, non-overlapping keys]
     │
     ▼
L3: [16GB total, 1000 SSTables of 16MB, non-overlapping keys]

Pros:
- Low read amplification (1-2 SSTables per read)
- Low space amplification (10% overhead)
- Better for read-heavy workloads

Cons:
- Higher write amplification (rewrite data multiple times)
- More I/O from compaction
- Not ideal for write-heavy workloads
```

### Time-Window Compaction (TWCS)
```
Strategy: Group SSTables by time window, compact within windows

Window 1 (Jan 1-7):  [SS1] [SS2] [SS3] → compact → [SSW1]
Window 2 (Jan 8-14): [SS4] [SS5] [SS6] → compact → [SSW2]
Window 3 (Jan 15-21): [SS7] [SS8] (in progress, not yet compacted)

Pros:
- Perfect for time-series data
- Old windows compact once (minimal write amplification)
- Easy TTL: Drop entire SSTable when window expires
- No tombstone issues (data ages out naturally)

Cons:
- Terrible for out-of-order writes
- Updates/deletes to old data create tombstones in current window
- Only works if data is written roughly in time order

Configuration:
ALTER TABLE sensor_data WITH compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': '1'
};
```

---

## Read & Write Paths

### Detailed Write Path
```
Client
  │
  ▼
Coordinator Node (any node in cluster)
  │
  ├──→ Determine replica nodes (token ring + replication)
  │
  ├──→ Send write to all RF replicas simultaneously
  │
  ▼
Each Replica:
  1. Append to Commit Log (sequential I/O, durable)
  2. Write to Memtable (in-memory, sorted)
  3. Acknowledge to coordinator
  │
  ▼ (when memtable full)
  4. Flush memtable → SSTable (background)
  5. Delete commit log segment (if all data flushed)

Coordinator waits for CL acknowledgments:
  - QUORUM: Wait for ⌊RF/2⌋ + 1 responses
  - Respond to client with success/failure

Hinted Handoff (if replica is down):
  - Coordinator stores hint (write for down node)
  - When node recovers, hints are delivered
  - Hints stored for max_hint_window_in_ms (3 hours default)
  - NOT a replacement for repair!
```

### Detailed Read Path
```
Client
  │
  ▼
Coordinator Node
  │
  ├──→ Determine replica nodes
  │
  ├──→ Based on CL, send read to required nodes
  │    (e.g., QUORUM = 2 of 3 replicas)
  │
  ▼
Read Repair (background, if digests mismatch):
  - Fast node returns full data
  - Other nodes return digest (hash of data)
  - If digests differ → coordinator fetches full data from all
  - Most recent timestamp wins → repair sent to stale replicas

Speculative Retry:
  - If first replica is slow, retry to another
  - Reduces tail latency (p99)
  - speculative_retry = '99percentile' (or 'Xms')

Within each replica node:
  1. Check memtable(s) - active + flushing
  2. Check row cache (if enabled)
  3. For each SSTable:
     a. Check Bloom filter (skip if "definitely not here")
     b. Check partition key cache
     c. Read partition index → find data offset
     d. Read data from disk
  4. Merge all results (latest timestamp wins per cell)
  5. Return merged result
```

---

## Performance Tuning

### Key Configuration
```yaml
# cassandra.yaml critical settings:

# Memory
memtable_heap_space_in_mb: 2048     # Memory for memtables (default 1/4 heap)
memtable_offheap_space_in_mb: 2048  # Off-heap memtables
key_cache_size_in_mb: 100           # Partition key → SSTable offset cache
row_cache_size_in_mb: 0             # Row cache (usually disable)

# Compaction
concurrent_compactors: 2            # Parallel compaction threads
compaction_throughput_mb_per_sec: 64 # Throttle compaction I/O

# Reads
read_request_timeout_in_ms: 5000
range_request_timeout_in_ms: 10000
concurrent_reads: 32                # = 16 × number_of_drives

# Writes
write_request_timeout_in_ms: 2000
concurrent_writes: 32               # = 8 × number_of_cores
commitlog_sync: periodic            # batch for IOPS-limited
commitlog_sync_period_in_ms: 10000

# JVM (jvm.options)
-Xms16G                            # Min heap (= max for production)
-Xmx16G                            # Max heap (usually 16-31GB)
-Xmn4G                             # Young gen (1/4 to 1/2 of heap)
# GC: G1GC (Java 11+) or CMS (Java 8)
```

### Performance Anti-Patterns
```
1. Large partitions (> 100MB):
   → Add bucketing to partition key (date, bucket_id)

2. Too many tombstones:
   → Use TWCS for time-series
   → Avoid DELETE-heavy workloads
   → Run repairs before gc_grace_seconds

3. Secondary indexes on high-cardinality columns:
   → Use materialized views or denormalized tables

4. SELECT * with no partition key:
   → Always include partition key in WHERE clause
   → Full table scans are cluster-wide scatter operations

5. Unbounded queries (no LIMIT):
   → Always use LIMIT or paging

6. Using Cassandra for small datasets (< 100GB):
   → Overhead not justified; use PostgreSQL/MySQL

7. ALLOW FILTERING:
   → Almost always indicates bad data model
   → Redesign table for the query pattern

8. Batch statements across partitions:
   → Unlogged batch for multiple partitions (just convenience, no atomicity)
   → Logged batch only for same partition (atomic)
```

---

## Staff Architect Interview Questions

**Q1: Explain how Cassandra achieves both high availability and tunable consistency.**
**A:** Cassandra separates availability from consistency through:
- **Replication**: Data copied to RF nodes across cluster
- **Tunable CL**: Each read/write specifies how many replicas must respond
- **No master**: Any node can coordinate any request
- **Hinted handoff**: Writes buffered for temporarily unavailable nodes
- **Read repair**: Stale replicas updated on read
- **Anti-entropy repair**: Periodic full data comparison (Merkle trees)

This allows the same cluster to serve different workloads:
- Time-series ingestion: CL=ONE (speed, eventual consistency OK)
- User authentication: CL=LOCAL_QUORUM (strong consistency needed)
- Cross-DC replication: CL=EACH_QUORUM (global consistency)

**Q2: How would you model a messaging system in Cassandra?**
**A:**
```sql
-- Messages table (one partition per conversation per day)
CREATE TABLE messages (
    conversation_id UUID,
    day TEXT,              -- Bucketing to limit partition size
    message_time TIMEUUID,
    sender_id UUID,
    content TEXT,
    PRIMARY KEY ((conversation_id, day), message_time)
) WITH CLUSTERING ORDER BY (message_time DESC);

-- User's conversations (sorted by latest activity)
CREATE TABLE user_conversations (
    user_id UUID,
    last_activity TIMESTAMP,
    conversation_id UUID,
    last_message_preview TEXT,
    PRIMARY KEY ((user_id), last_activity, conversation_id)
) WITH CLUSTERING ORDER BY (last_activity DESC);

-- Unread counts
CREATE TABLE unread_counts (
    user_id UUID,
    conversation_id UUID,
    count COUNTER,
    PRIMARY KEY ((user_id), conversation_id)
);
```

**Q3: What happens during a node failure and recovery?**
**A:**
1. **Detection**: Gossip protocol detects node down (phi accrual detector)
2. **During downtime**:
   - Writes to other replicas succeed (if CL satisfied)
   - Hints stored on coordinator (max 3 hours)
   - Reads served by remaining replicas
3. **Recovery**:
   - Node starts, reads commit log (redo unflushed memtables)
   - Receives stored hints from other nodes
   - Anti-entropy repair should run to catch anything beyond hint window
4. **If prolonged outage (> hint window)**:
   - Manual `nodetool repair` required
   - Without repair: Possible data inconsistency until gc_grace_seconds

**Q4: Compare STCS vs LCS vs TWCS. When to use each?**
**A:**
| Strategy | Best For | Write Amp | Read Amp | Space Amp |
|----------|----------|-----------|----------|-----------|
| STCS | Write-heavy, general | Low | High | High (2x) |
| LCS | Read-heavy, updates | High | Low | Low (10%) |
| TWCS | Time-series, TTL | Low | Low (per window) | Low |

Decision criteria:
- **STCS**: Default. Good for write-heavy with infrequent reads
- **LCS**: When reads dominate and you need predictable latency
- **TWCS**: Time-ordered data with TTL (IoT, logs, metrics)
- Never use TWCS with updates/deletes to old data

**Q5: How do you handle large-scale data repairs?**
**A:**
- **Full repair**: `nodetool repair` - Compares all data via Merkle trees
- **Incremental repair**: Only repairs data since last repair (faster)
- **Sub-range repair**: Repair specific token ranges (parallelizable)
- **Schedule**: Regular repairs within gc_grace_seconds (default 10 days)
- **Tools**: Cassandra Reaper (scheduling, monitoring, safe parallelism)

Best practices:
- Run repair at least once within gc_grace_seconds
- Use sub-range repair for large clusters (parallelism)
- Schedule during low-traffic periods
- Monitor repair progress (slow repairs indicate problems)

---

## Scenario-Based Questions

### Scenario 1: Hotspot Detection and Resolution

**Problem:** One node at 90% CPU while others at 30%. Write latency spiking.

**Diagnosis:**
```bash
# Check token distribution
nodetool ring

# Check per-table partition sizes
nodetool tablehistograms keyspace.table

# Check if specific partitions are large
nodetool toppartitions keyspace.table 1000

# Common causes:
# 1. Poor partition key choice (low cardinality)
# 2. Time-based partition key → all writes to latest partition
# 3. Celebrity/viral content (one partition gets all traffic)
```

**Solutions:**
```
1. Compound partition key (add bucketing):
   Old: PRIMARY KEY (user_id, time)  -- Celebrity user = hot partition
   New: PRIMARY KEY ((user_id, bucket), time)
   bucket = hash(time) % 10 or random(1-10)

2. Application-level routing:
   - Detect hot partitions
   - Spread reads across replicas (CL=ONE)
   - Write to different bucket on each request

3. If vnodes are unbalanced:
   - Check num_tokens setting
   - Consider bootstrap new nodes
   - Use allocate_tokens_for_keyspace (4.0+)
```

### Scenario 2: Tombstone Accumulation Crisis

**Problem:** Read latency degrades over time. Queries timing out. Logs show "Read X live rows and Y tombstones."

**Root cause:** Delete-heavy workload creating millions of tombstones.

**Resolution:**
```bash
# Check tombstone counts per read
nodetool tablestats keyspace.table
# Look for: "Average tombstones per slice"

# Force compaction to remove tombstones (only if gc_grace_seconds passed)
nodetool compact keyspace table

# If tombstones are too new (within gc_grace_seconds):
# Option 1: Reduce gc_grace_seconds (risk: zombie data if repair not current)
ALTER TABLE table WITH gc_grace_seconds = 86400;  # 1 day (ensure repair runs daily!)

# Option 2: Redesign data model
# Instead of DELETE, use TTL:
INSERT INTO events (...) VALUES (...) USING TTL 604800;
# Data disappears after 7 days without explicit tombstones

# Option 3: Use TWCS (tombstones drop when entire SSTable expires)
ALTER TABLE table WITH compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': '1'
};
```

### Scenario 3: Multi-DC Failover Strategy

**Setup:** 3 DCs (US-East, EU-West, Asia-Pacific), RF=3 per DC.

**Failover scenarios:**
```
Scenario A: Single node failure
- Automatic: Remaining 2 replicas in DC serve requests
- LOCAL_QUORUM still achievable (2 of 3)
- Hinted handoff handles short outages
- Repair for extended outages

Scenario B: Full DC failure
- Clients route to alternative DC
- LOCAL_QUORUM still achievable in remaining DCs
- Data consistency depends on replication lag at failure time
- Recovery: DC comes back, run repair from surviving DCs

Scenario C: Network partition (DC isolated)
- Isolated DC can still serve LOCAL_QUORUM (if 2+ nodes)
- Writes in isolated DC may conflict with other DCs
- Resolution: Last-write-wins on reconnection
- Mitigation: Application detects partition, routes to other DC

Application-level failover:
- DNS-based routing (change DC priority)
- Load balancer health checks per DC
- Client retry policy with DC awareness
- Cassandra driver: DCAwareRoundRobinPolicy
  - Primary DC for all queries
  - Failover to remote DC if local unavailable
```

### Scenario 4: Migrating from RDBMS to Cassandra

**Approach:**
```
1. Identify access patterns (not entities!):
   SELECT * FROM orders WHERE customer_id = ? ORDER BY date DESC LIMIT 20
   SELECT * FROM orders WHERE order_id = ?
   SELECT * FROM orders WHERE status = 'pending' AND region = 'US'

2. Create query-specific tables:
   orders_by_customer (partition: customer_id, clustering: date DESC)
   orders_by_id (partition: order_id)
   orders_by_status_region (partition: (status, region), clustering: date DESC)

3. Handle consistency requirements:
   - Strict: Use LWT for unique constraints (limited scale)
   - Eventual: Accept eventual consistency, design for it
   - External: Use Kafka for cross-table consistency

4. Migration process:
   a. Dual-write (app writes to both RDBMS and Cassandra)
   b. Backfill Cassandra from RDBMS (bulk load with sstableloader)
   c. Validate data consistency
   d. Shadow-read from Cassandra (compare with RDBMS)
   e. Cut over reads to Cassandra
   f. Cut over writes (remove RDBMS from write path)
   g. Decommission RDBMS

5. What NOT to bring:
   - JOINs → Denormalize
   - Foreign keys → Application-level integrity
   - Aggregations → Pre-compute or use Spark
   - Ad-hoc queries → Use Cassandra for known patterns only
```

