# PostgreSQL - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Storage Engine & Internals](#storage-engine--internals)
3. [MVCC Deep Dive](#mvcc-deep-dive)
4. [Indexing Strategies](#indexing-strategies)
5. [Transactions & Isolation Levels](#transactions--isolation-levels)
6. [Locking Mechanisms](#locking-mechanisms)
7. [Partitioning](#partitioning)
8. [Replication & High Availability](#replication--high-availability)
9. [Scalability Patterns](#scalability-patterns)
10. [Query Optimization](#query-optimization)
11. [Connection Management](#connection-management)
12. [Data Modeling](#data-modeling)
13. [Advanced Features](#advanced-features)
14. [Monitoring & Observability](#monitoring--observability)
15. [Staff Architect Interview Questions](#staff-architect-interview-questions)
16. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Process Architecture
```
Client Connection
       │
       ▼
┌─────────────────┐
│   Postmaster    │  (Main daemon - forks worker processes)
│   (PID 1)      │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Backend│ │Backend│ │BGWriter│ │WAL     │ │Auto-   │
│Process│ │Process│ │        │ │Writer  │ │vacuum  │
└───────┘ └───────┘ └────────┘ └────────┘ └────────┘
    │         │          │          │          │
    └─────────┴──────────┴──────────┴──────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
     ┌──────────────┐     ┌──────────────┐
     │ Shared Memory│     │  Disk (WAL,  │
     │ (Buffer Pool,│     │  Data Files, │
     │  WAL Buffers)│     │  Indexes)    │
     └──────────────┘     └──────────────┘
```

### Key Architectural Decisions
- **Process-per-connection model** (not thread-based like MySQL)
- **Shared-nothing architecture** within a single node
- **Write-Ahead Logging (WAL)** for durability
- **MVCC** for concurrency without read locks
- **Extensible type system** and operator overloading
- **Cost-based query optimizer** with genetic algorithm for complex joins

### Memory Architecture
```
Shared Memory:
├── Shared Buffers (shared_buffers) - Page cache
├── WAL Buffers (wal_buffers) - WAL write buffer
├── CLOG Buffers - Transaction commit status
├── Lock Table - All lock information
└── Proc Array - Backend process info

Per-Process Memory:
├── work_mem - Sort/hash operations per query
├── maintenance_work_mem - VACUUM, CREATE INDEX
├── temp_buffers - Temporary table access
└── effective_cache_size - Planner hint (not allocation)
```

---

## Storage Engine & Internals

### Heap Storage (Default)
```
Tablespace
└── Database Directory
    └── Relation Files (tables/indexes)
        ├── Main fork (data) - filenode
        ├── FSM fork (free space map) - filenode_fsm
        ├── VM fork (visibility map) - filenode_vm
        └── Init fork (unlogged tables) - filenode_init
```

### Page Layout (8KB default)
```
┌─────────────────────────────────┐
│ Page Header (24 bytes)          │
├─────────────────────────────────┤
│ Item Pointers (Line Pointers)   │  ← Array of (offset, length, flags)
│ [ItemId1][ItemId2]...[ItemIdN]  │
├─────────────────────────────────┤
│                                 │
│         Free Space              │
│                                 │
├─────────────────────────────────┤
│ Tuple N (HeapTupleHeader+Data)  │
│ ...                             │
│ Tuple 2                         │
│ Tuple 1                         │
└─────────────────────────────────┘
```

### HeapTupleHeader (23 bytes minimum)
```c
typedef struct HeapTupleHeaderData {
    TransactionId t_xmin;    // Insert XID
    TransactionId t_xmax;    // Delete/Update XID
    CommandId     t_cid;     // Command ID within transaction
    ItemPointerData t_ctid;  // Current TID (self-referencing or new version)
    uint16        t_infomask;  // Various flag bits
    uint16        t_infomask2; // More flags + number of attributes
    uint8         t_hoff;    // Offset to user data
    // bits8 t_bits[] - null bitmap (variable length)
} HeapTupleHeaderData;
```

### TOAST (The Oversized-Attribute Storage Technique)
- Handles values > 2KB (1/4 of page size)
- Strategies: PLAIN, EXTENDED (compress then external), EXTERNAL, MAIN
- Compression: pglz (default) or lz4 (PG14+)
- External storage in separate TOAST table

### Tuple Visibility
```
Tuple is visible to transaction T if:
1. t_xmin is committed AND t_xmin < T's snapshot
2. t_xmax is either:
   - Invalid (not deleted)
   - Aborted (delete was rolled back)
   - Not yet committed
   - Committed but after T's snapshot
```

---

## MVCC Deep Dive

### How MVCC Works in PostgreSQL
Unlike Oracle (undo segments) or MySQL/InnoDB (rollback segment), PostgreSQL stores ALL versions in the heap itself.

```
UPDATE row SET value = 'new':

Before:
Page: [...| Tuple v1 (xmin=100, xmax=0) |...]

After:
Page: [...| Tuple v1 (xmin=100, xmax=200) | Tuple v2 (xmin=200, xmax=0) |...]
                                              ↑ new version
```

### Snapshot Isolation Implementation
```
Snapshot contains:
- xmin: Lowest active XID at snapshot time
- xmax: First unassigned XID at snapshot time  
- xip_list: List of active XIDs at snapshot time

Visibility rule:
- XID < xmin → committed (visible)
- XID >= xmax → in-progress or future (not visible)
- XID in xip_list → in-progress (not visible)
- Otherwise → committed (visible, check CLOG)
```

### CLOG (Commit Log) / pg_xact
```
2 bits per transaction:
- 00: IN_PROGRESS
- 01: COMMITTED
- 10: ABORTED
- 11: SUB_COMMITTED (subtransaction)

Storage: 8KB pages, each holding status for 4 * 8192 = 32768 transactions
```

### Vacuum Process
```
Standard VACUUM:
1. Scan heap pages
2. Find dead tuples (not visible to any active transaction)
3. Remove index entries pointing to dead tuples
4. Mark heap space as reusable in FSM
5. Update visibility map
6. Truncate trailing empty pages (if possible)

VACUUM FULL:
1. Lock table exclusively
2. Rewrite entire table (new physical file)
3. Rebuild all indexes
4. Reclaim space to OS
```

### Transaction ID Wraparound
```
XID is 32-bit unsigned integer (4 billion values)
- "The past" = 2 billion XIDs before current
- "The future" = 2 billion XIDs after current

Prevention:
- VACUUM freezes old tuples (sets t_infomask FROZEN bit)
- autovacuum_freeze_max_age (default: 200M) triggers aggressive vacuum
- Failsafe: DB shuts down at 40M XIDs remaining
```

---

## Indexing Strategies

### B-Tree Index (Default)
```sql
CREATE INDEX idx_users_email ON users(email);
-- Multi-column
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at DESC);
-- Partial
CREATE INDEX idx_active_users ON users(email) WHERE active = true;
-- Covering (Index-Only Scans)
CREATE INDEX idx_orders_covering ON orders(user_id) INCLUDE (total, status);
```

**B-Tree Internal Structure:**
```
                    [Meta Page]
                        │
              ┌─────────┴─────────┐
              ▼                    ▼
         [Root Page]          (if exists)
         [10 | 20 | 30]
        /    |     |    \
       ▼     ▼     ▼     ▼
    [Leaf]  [Leaf] [Leaf] [Leaf]
    1-9    10-19  20-29   30+
    →next   →next  →next
```

### Hash Index
```sql
CREATE INDEX idx_hash ON users USING hash(id);
-- Only equality (=) lookups
-- WAL-logged since PG10
-- Smaller than B-Tree for equality-only workloads
```

### GiST (Generalized Search Tree)
```sql
-- Range types
CREATE INDEX idx_reservation_during ON reservations USING gist(during);
-- Geometric types
CREATE INDEX idx_geo ON locations USING gist(point);
-- Full-text search
CREATE INDEX idx_fts ON documents USING gist(to_tsvector('english', content));
-- Exclusion constraints
ALTER TABLE reservations ADD CONSTRAINT no_overlap
  EXCLUDE USING gist (room WITH =, during WITH &&);
```

### GIN (Generalized Inverted Index)
```sql
-- JSONB
CREATE INDEX idx_jsonb ON events USING gin(payload jsonb_path_ops);
-- Full-text search
CREATE INDEX idx_fts ON documents USING gin(to_tsvector('english', content));
-- Arrays
CREATE INDEX idx_tags ON posts USING gin(tags);
-- Trigram (pg_trgm)
CREATE INDEX idx_trgm ON users USING gin(name gin_trgm_ops);
```

**GIN Structure:**
```
Entry Tree (B-Tree of keys):
    "apple" → Posting List/Tree [1, 5, 23, 89]
    "banana" → Posting List [2, 7]
    "cherry" → Posting Tree (if > 128 items)
                    [Root]
                   /      \
              [1-100]    [101-500]
```

### BRIN (Block Range Index)
```sql
-- Perfect for naturally ordered data (timestamps, sequential IDs)
CREATE INDEX idx_brin_created ON events USING brin(created_at)
  WITH (pages_per_range = 32);
-- Extremely small index size (e.g., 100KB for 100GB table)
```

**BRIN Structure:**
```
Block Range 1 (pages 0-127):   min=2024-01-01, max=2024-01-05
Block Range 2 (pages 128-255): min=2024-01-05, max=2024-01-10
Block Range 3 (pages 256-383): min=2024-01-10, max=2024-01-15
```

### SP-GiST (Space-Partitioned GiST)
```sql
-- IP addresses (inet type)
CREATE INDEX idx_ip ON connections USING spgist(client_ip);
-- Text (radix tree)
CREATE INDEX idx_url ON pages USING spgist(url text_ops);
```

### Bloom Index (bloom extension)
```sql
CREATE EXTENSION bloom;
CREATE INDEX idx_bloom ON table USING bloom(col1, col2, col3)
  WITH (length=80, col1=2, col2=2, col3=4);
-- Signature-based, supports any combination of column equality checks
```

### Index Selection Decision Matrix
| Use Case | Index Type | Why |
|----------|-----------|-----|
| Equality + Range | B-Tree | Universal, ordered |
| Equality only | Hash | Smaller, O(1) |
| Geometric/Range overlap | GiST | Supports complex operators |
| Contains/Intersection | GIN | Inverted index |
| Time-series data | BRIN | Tiny index, huge table |
| Multi-column loose queries | Bloom | Any column combo |

---

## Transactions & Isolation Levels

### PostgreSQL Isolation Levels
```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;      -- Default
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
-- Note: READ UNCOMMITTED = READ COMMITTED in PostgreSQL (no dirty reads ever)
```

### Anomalies Prevention Matrix
| Anomaly | Read Committed | Repeatable Read | Serializable |
|---------|---------------|-----------------|--------------|
| Dirty Read | ✗ Prevented | ✗ Prevented | ✗ Prevented |
| Non-Repeatable Read | ✓ Possible | ✗ Prevented | ✗ Prevented |
| Phantom Read | ✓ Possible | ✗ Prevented | ✗ Prevented |
| Serialization Anomaly | ✓ Possible | ✓ Possible | ✗ Prevented |
| Write Skew | ✓ Possible | ✓ Possible | ✗ Prevented |

### Serializable Snapshot Isolation (SSI)
```
PostgreSQL uses SSI (not S2PL) for SERIALIZABLE level:

1. Tracks rw-dependencies (read-write conflicts) between transactions
2. Detects "dangerous structures" (cycles in dependency graph)
3. Aborts one transaction to break the cycle

Key structures:
- SIREAD locks (predicate locks that don't block)
- RW-conflict tracking
- Transaction dependency graph

Example - Write Skew:
T1: SELECT sum(amount) FROM accounts WHERE owner='Alice'; -- reads $1000
T2: SELECT sum(amount) FROM accounts WHERE owner='Alice'; -- reads $1000
T1: UPDATE accounts SET amount = amount - 600 WHERE id = 1; -- OK, $400 remains
T2: UPDATE accounts SET amount = amount - 600 WHERE id = 2; -- SSI detects, aborts T2
```

### Savepoints and Subtransactions
```sql
BEGIN;
INSERT INTO orders VALUES (1, 'pending');
SAVEPOINT sp1;
INSERT INTO order_items VALUES (1, 1, 'widget');  -- might fail
ROLLBACK TO SAVEPOINT sp1;  -- undo just this
INSERT INTO order_items VALUES (1, 2, 'gadget');  -- try alternative
COMMIT;

-- Warning: Subtransactions have overhead
-- Each SAVEPOINT = sub-XID tracked in pg_subtrans
-- Max 64 sub-XIDs cached per backend (overflow to disk)
```

### Two-Phase Commit (2PC)
```sql
-- Distributed transactions
BEGIN;
-- ... operations ...
PREPARE TRANSACTION 'txn_id_123';
-- Later:
COMMIT PREPARED 'txn_id_123';
-- Or:
ROLLBACK PREPARED 'txn_id_123';

-- Caution: Prepared transactions hold locks and prevent VACUUM
```

---

## Locking Mechanisms

### Lock Hierarchy
```
1. Table-Level Locks (8 modes):
   ACCESS SHARE          ← SELECT
   ROW SHARE             ← SELECT FOR UPDATE/SHARE
   ROW EXCLUSIVE         ← INSERT/UPDATE/DELETE
   SHARE UPDATE EXCLUSIVE ← VACUUM, CREATE INDEX CONCURRENTLY
   SHARE                 ← CREATE INDEX
   SHARE ROW EXCLUSIVE   ← CREATE TRIGGER, some ALTER TABLE
   EXCLUSIVE             ← REFRESH MATERIALIZED VIEW CONCURRENTLY
   ACCESS EXCLUSIVE      ← DROP TABLE, TRUNCATE, VACUUM FULL, ALTER TABLE

2. Row-Level Locks (4 modes):
   FOR KEY SHARE         ← Referenced by FK check
   FOR SHARE             ← SELECT FOR SHARE
   FOR NO KEY UPDATE     ← UPDATE (non-key columns)
   FOR UPDATE            ← SELECT FOR UPDATE, DELETE, UPDATE (key columns)

3. Advisory Locks:
   pg_advisory_lock(key)           -- Session-level, blocking
   pg_try_advisory_lock(key)       -- Non-blocking
   pg_advisory_xact_lock(key)      -- Transaction-level
```

### Lock Compatibility Matrix (Table Level)
```
               AS   RS   RE  SUE   S   SRE   E   AE
ACCESS SHARE    ✓    ✓    ✓    ✓   ✓    ✓    ✓    ✗
ROW SHARE       ✓    ✓    ✓    ✓   ✓    ✓    ✗    ✗
ROW EXCLUSIVE   ✓    ✓    ✓    ✓   ✗    ✗    ✗    ✗
SHARE UPD EXC   ✓    ✓    ✓    ✗   ✗    ✗    ✗    ✗
SHARE           ✓    ✓    ✗    ✗   ✓    ✗    ✗    ✗
SHARE ROW EXC   ✓    ✓    ✗    ✗   ✗    ✗    ✗    ✗
EXCLUSIVE       ✓    ✗    ✗    ✗   ✗    ✗    ✗    ✗
ACCESS EXCL     ✗    ✗    ✗    ✗   ✗    ✗    ✗    ✗
```

### Deadlock Detection
```
- Deadlock detector runs every deadlock_timeout (default 1s)
- Builds wait-for graph
- Cancels one transaction (youngest by default)
- Only checks after deadlock_timeout to avoid overhead

Prevention strategies:
1. Lock resources in consistent order
2. Use NOWAIT or lock_timeout
3. Use advisory locks for application-level coordination
4. Keep transactions short
```

### Lightweight Locks (LWLocks)
```
Internal locks for shared memory structures:
- Buffer content locks (shared/exclusive)
- WAL insertion locks
- CLOG buffer locks
- Proc array lock
- Not directly visible to users
- Visible in pg_stat_activity.wait_event
```

---

## Partitioning

### Declarative Partitioning (PG10+)
```sql
-- Range Partitioning
CREATE TABLE measurements (
    id bigserial,
    created_at timestamptz NOT NULL,
    device_id int,
    value float
) PARTITION BY RANGE (created_at);

CREATE TABLE measurements_2024_q1 PARTITION OF measurements
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE measurements_2024_q2 PARTITION OF measurements
    FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');

-- List Partitioning
CREATE TABLE orders (
    id bigserial,
    region text,
    amount decimal
) PARTITION BY LIST (region);

CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('us-east', 'us-west');
CREATE TABLE orders_eu PARTITION OF orders FOR VALUES IN ('eu-west', 'eu-central');

-- Hash Partitioning
CREATE TABLE events (
    id bigserial,
    user_id int,
    data jsonb
) PARTITION BY HASH (user_id);

CREATE TABLE events_0 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE events_1 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE events_2 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE events_3 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 3);

-- Multi-level (sub-partitioning)
CREATE TABLE logs (
    id bigserial,
    created_at timestamptz,
    region text,
    message text
) PARTITION BY RANGE (created_at);

CREATE TABLE logs_2024 PARTITION OF logs
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01')
    PARTITION BY LIST (region);
```

### Partition Pruning
```sql
-- Static pruning (at plan time)
EXPLAIN SELECT * FROM measurements WHERE created_at = '2024-02-15';
-- Only scans measurements_2024_q1

-- Dynamic pruning (at execution time, PG11+)
PREPARE q AS SELECT * FROM measurements WHERE created_at = $1;
EXECUTE q('2024-02-15');

-- Enable: SET enable_partition_pruning = on; (default)
```

### Partition Management Best Practices
```sql
-- Attach/detach partitions without locking entire table
ALTER TABLE measurements DETACH PARTITION measurements_2023_q1 CONCURRENTLY;

-- Default partition for unmatched rows
CREATE TABLE measurements_default PARTITION OF measurements DEFAULT;

-- Auto-create partitions (use pg_partman extension)
CREATE EXTENSION pg_partman;
SELECT partman.create_parent(
    p_parent_table := 'public.measurements',
    p_control := 'created_at',
    p_type := 'native',
    p_interval := 'monthly'
);
```

---

## Replication & High Availability

### Streaming Replication
```
Primary                          Standby
┌──────────┐    WAL Stream    ┌──────────┐
│ WAL      │ ──────────────→  │ WAL      │
│ Sender   │                  │ Receiver │
│          │                  │          │
│ Heap     │                  │ Heap     │
│ Data     │                  │ Data     │
└──────────┘                  └──────────┘

Modes:
- Asynchronous (default): Primary doesn't wait
- Synchronous: Primary waits for standby confirmation
  - remote_write: WAL received by OS
  - on: WAL flushed to disk
  - remote_apply: WAL applied (visible to queries)
```

### Configuration
```
# Primary (postgresql.conf)
wal_level = replica          # or logical
max_wal_senders = 10
synchronous_standby_names = 'FIRST 1 (standby1, standby2)'
synchronous_commit = on      # remote_apply for read-your-writes

# Standby (postgresql.conf)
primary_conninfo = 'host=primary port=5432 user=replicator'
hot_standby = on             # Allow read queries on standby
```

### Logical Replication (PG10+)
```sql
-- Publisher
CREATE PUBLICATION my_pub FOR TABLE users, orders;
-- Or all tables:
CREATE PUBLICATION my_pub FOR ALL TABLES;

-- Subscriber
CREATE SUBSCRIPTION my_sub
    CONNECTION 'host=publisher dbname=mydb'
    PUBLICATION my_pub;

-- Use cases:
-- 1. Selective replication (specific tables/columns PG15+)
-- 2. Cross-version replication
-- 3. Multi-master (with conflict resolution)
-- 4. Data integration (replicate to different schema)
```

### High Availability Solutions
```
1. Patroni (Recommended for production)
   - Uses DCS (etcd/ZooKeeper/Consul) for leader election
   - Automatic failover with fencing
   - REST API for management
   
2. pg_auto_failover
   - Built by Citus team
   - Monitor node orchestrates failover
   - Simpler than Patroni

3. Stolon
   - Kubernetes-native
   - Uses etcd/Consul for DCS

4. repmgr
   - SSH-based failover
   - Less robust than DCS-based solutions
```

### Logical Decoding & Change Data Capture (CDC)
```sql
-- Create replication slot
SELECT pg_create_logical_replication_slot('my_slot', 'pgoutput');

-- Read changes
SELECT * FROM pg_logical_slot_get_changes('my_slot', NULL, NULL);

-- External CDC tools:
-- Debezium (Kafka Connect)
-- pglogical
-- wal2json
```

---

## Scalability Patterns

### Vertical Scaling Limits
```
Practical limits for a single PostgreSQL instance:
- ~10TB data (beyond this, operational complexity increases)
- ~10K connections (with pgbouncer)
- ~500K TPS (simple key-value operations)
- ~100K TPS (complex transactions)

Bottlenecks:
- Single-writer architecture (WAL is serialized)
- Process-per-connection memory overhead (~10MB each)
- VACUUM overhead at scale
- Lock contention on hot rows
```

### Horizontal Read Scaling
```
┌─────────┐    Writes    ┌──────────┐
│  App    │ ───────────→ │ Primary  │
│ Server  │              └────┬─────┘
│         │                   │ Streaming
│         │    Reads     ┌────┴─────┐
│         │ ←──────────→ │ Replicas │
└─────────┘              │ (N)      │
                         └──────────┘

Load balancing options:
- Application-level routing
- PgBouncer + HAProxy
- Pgpool-II
- AWS RDS Read Replicas
```

### Write Scaling (Sharding)
```
Option 1: Citus (Distributed PostgreSQL)
┌─────────────┐
│ Coordinator │ ← Query routing, distributed planning
└──────┬──────┘
       │
┌──────┼──────┬──────────┐
▼      ▼      ▼          ▼
[Worker1] [Worker2] [Worker3] [Worker4]
  Shard1    Shard2    Shard3    Shard4

Option 2: Application-level sharding
- Consistent hashing on shard key
- Cross-shard queries at application level

Option 3: Foreign Data Wrappers (FDW)
- postgres_fdw for cross-node queries
- High latency for joins
```

### Connection Pooling
```
PgBouncer modes:
- Session pooling: 1:1 mapping per session
- Transaction pooling: Connection returned after each transaction
- Statement pooling: Connection returned after each statement

Optimal configuration:
- Pool size = (num_cores * 2) + effective_spindle_count
- Typically 20-50 connections per PostgreSQL instance
- PgBouncer can handle 10K+ client connections → 50 backend connections

# pgbouncer.ini
[databases]
mydb = host=127.0.0.1 port=5432 dbname=mydb

[pgbouncer]
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 50
reserve_pool_size = 10
```

---

## Query Optimization

### EXPLAIN ANALYZE Deep Dive
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.name, count(o.id)
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE u.created_at > '2024-01-01'
GROUP BY u.name
ORDER BY count(o.id) DESC
LIMIT 10;

-- Key metrics to watch:
-- actual time: First row..Last row (ms)
-- rows: Estimated vs actual (row estimation errors)
-- Buffers: shared hit (cache) vs shared read (disk)
-- Sort Method: quicksort (memory) vs external merge (disk)
```

### Join Strategies
```
1. Nested Loop Join: O(N*M)
   - Best for: Small outer + indexed inner
   - With index: O(N * log(M))

2. Hash Join: O(N+M)
   - Best for: Large tables, equality joins
   - Needs memory (work_mem)
   - Falls back to disk if exceeds work_mem (batched)

3. Merge Join: O(N*log(N) + M*log(M))
   - Best for: Pre-sorted data (index scan)
   - Good for: Large datasets already ordered

4. Parallel Hash Join (PG11+)
   - Shared hash table across workers
```

### Statistics & Planner
```sql
-- Column statistics
ALTER TABLE users ALTER COLUMN status SET STATISTICS 1000; -- default 100
ANALYZE users;

-- Extended statistics (PG10+)
CREATE STATISTICS stats_city_zip ON city, zip_code FROM addresses;
-- Types: ndistinct, dependencies, mcv (PG12+)

-- Planner hints (via pg_hint_plan extension)
/*+ SeqScan(users) HashJoin(users orders) Leading(users orders) */
SELECT * FROM users JOIN orders ON users.id = orders.user_id;
```

### Common Performance Anti-Patterns
```sql
-- 1. N+1 queries → Use JOINs or batch fetching
-- 2. SELECT * → Select only needed columns
-- 3. Missing indexes on FK columns
-- 4. Over-indexing (slows writes, bloats storage)
-- 5. Large IN lists → Use VALUES or temp table
-- 6. OFFSET for pagination → Use keyset/cursor pagination:
SELECT * FROM posts WHERE id > :last_seen_id ORDER BY id LIMIT 20;
-- 7. Not using covering indexes (unnecessary heap access)
-- 8. Implicit type casting preventing index use
```

---

## Connection Management

### Process-per-Connection Impact
```
Each connection costs:
- ~10MB RSS memory (default settings)
- 1 OS process (context switching overhead)
- Proc array slot
- Snapshot bookkeeping

At 1000 connections:
- 10GB RAM just for connections
- Lock contention in proc array
- Context switching dominates CPU

Solution: Connection pooler between app and DB
App (10K connections) → PgBouncer (50 backend connections) → PostgreSQL
```

### Idle Connection Problems
```
Idle connections still:
- Hold memory (snapshots, cached plans)
- Prevent VACUUM from cleaning old tuples
- Count toward max_connections
- May hold open transactions (blocking VACUUM)

Detection:
SELECT pid, state, query_start, state_change
FROM pg_stat_activity
WHERE state = 'idle'
AND state_change < now() - interval '5 minutes';

Prevention:
- idle_in_transaction_session_timeout = '30s'
- idle_session_timeout = '10min' (PG14+)
```

---

## Data Modeling

### Normalization vs Denormalization
```sql
-- Normalized (3NF) - Ideal for OLTP
CREATE TABLE users (id serial PRIMARY KEY, name text, email text);
CREATE TABLE addresses (id serial PRIMARY KEY, user_id int REFERENCES users, 
                        street text, city text, zip text);

-- Denormalized with JSONB - Flexible schema
CREATE TABLE users (
    id serial PRIMARY KEY,
    name text,
    email text,
    addresses jsonb DEFAULT '[]'
);
-- When to denormalize:
-- 1. Read-heavy workloads
-- 2. Avoid expensive JOINs
-- 3. Rarely updated nested data
-- 4. Variable/sparse attributes
```

### JSONB Patterns
```sql
-- Efficient JSONB queries with GIN index
CREATE INDEX idx_events_payload ON events USING gin(payload jsonb_path_ops);
-- jsonb_path_ops: Only supports @> (containment)
-- Default ops: Supports @>, ?, ?|, ?&, but larger index

-- JSONB operators
SELECT * FROM events WHERE payload @> '{"type": "click"}';
SELECT * FROM events WHERE payload->>'user_id' = '123';
SELECT * FROM events WHERE payload ? 'error';

-- JSONB path queries (PG12+)
SELECT * FROM events 
WHERE jsonb_path_exists(payload, '$.items[*] ? (@.price > 100)');
```

### Temporal Data Patterns
```sql
-- Bi-temporal table (system + application time)
CREATE TABLE contracts (
    id int,
    data jsonb,
    valid_from timestamptz,
    valid_to timestamptz,
    sys_from timestamptz DEFAULT now(),
    sys_to timestamptz DEFAULT 'infinity',
    EXCLUDE USING gist (id WITH =, tstzrange(valid_from, valid_to) WITH &&)
);

-- Temporal queries with range types
SELECT * FROM contracts 
WHERE id = 1 
AND tstzrange(valid_from, valid_to) @> now()
AND tstzrange(sys_from, sys_to) @> now();
```

### Array and HStore Patterns
```sql
-- Arrays for ordered collections
CREATE TABLE posts (
    id serial PRIMARY KEY,
    title text,
    tags text[] DEFAULT '{}'
);
CREATE INDEX idx_posts_tags ON posts USING gin(tags);
SELECT * FROM posts WHERE tags @> ARRAY['postgresql'];

-- HStore for flat key-value
CREATE EXTENSION hstore;
CREATE TABLE products (
    id serial PRIMARY KEY,
    name text,
    attributes hstore
);
SELECT * FROM products WHERE attributes -> 'color' = 'red';
```

---

## Advanced Features

### Table Inheritance
```sql
CREATE TABLE audit_log (
    id bigserial PRIMARY KEY,
    table_name text,
    operation text,
    old_data jsonb,
    new_data jsonb,
    changed_at timestamptz DEFAULT now()
);
-- Used internally for partitioning (legacy method)
```

### Generated Columns & Expressions
```sql
CREATE TABLE products (
    id serial PRIMARY KEY,
    price_cents int,
    quantity int,
    total_cents int GENERATED ALWAYS AS (price_cents * quantity) STORED,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', name || ' ' || description)
    ) STORED
);
```

### Custom Types & Domains
```sql
-- Composite types
CREATE TYPE address AS (street text, city text, zip text, country text);

-- Domains with constraints
CREATE DOMAIN email AS text CHECK (VALUE ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+$');
CREATE DOMAIN positive_int AS int CHECK (VALUE > 0);

-- Enums
CREATE TYPE order_status AS ENUM ('pending', 'processing', 'shipped', 'delivered');
-- Warning: Adding values is easy, removing is hard (requires migration)
```

### Extensions Ecosystem
```sql
-- Essential extensions for production
CREATE EXTENSION pg_stat_statements;  -- Query performance tracking
CREATE EXTENSION pg_trgm;              -- Fuzzy text search
CREATE EXTENSION btree_gist;           -- GiST for scalar types (exclusion constraints)
CREATE EXTENSION uuid-ossp;            -- UUID generation
CREATE EXTENSION pgcrypto;             -- Encryption functions
CREATE EXTENSION postgis;              -- Geospatial
CREATE EXTENSION timescaledb;          -- Time-series
CREATE EXTENSION pg_partman;           -- Partition management
CREATE EXTENSION pg_hint_plan;         -- Query hints
CREATE EXTENSION hypopg;               -- Hypothetical indexes
```

---

## Monitoring & Observability

### Critical Views
```sql
-- Active queries
SELECT pid, state, wait_event_type, wait_event, query, 
       now() - query_start as duration
FROM pg_stat_activity WHERE state != 'idle';

-- Table statistics
SELECT relname, seq_scan, idx_scan, n_tup_ins, n_tup_upd, n_tup_del,
       n_dead_tup, last_vacuum, last_autovacuum
FROM pg_stat_user_tables ORDER BY n_dead_tup DESC;

-- Index usage
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes ORDER BY idx_scan;

-- Cache hit ratio (should be > 99%)
SELECT sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
FROM pg_statio_user_tables;

-- Replication lag
SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn,
       pg_wal_lsn_diff(sent_lsn, replay_lsn) as replay_lag_bytes
FROM pg_stat_replication;
```

### pg_stat_statements
```sql
-- Top queries by total time
SELECT query, calls, total_exec_time, mean_exec_time,
       rows, shared_blks_hit, shared_blks_read
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 20;

-- Queries with worst cache hit ratio
SELECT query, shared_blks_hit::float / 
       (shared_blks_hit + shared_blks_read) as hit_ratio
FROM pg_stat_statements
WHERE shared_blks_read > 100
ORDER BY hit_ratio LIMIT 20;
```

---

## Staff Architect Interview Questions

### Architecture & Internals

**Q1: Explain PostgreSQL's MVCC implementation and how it differs from Oracle/MySQL.**
**A:** PostgreSQL stores all tuple versions directly in the heap table (no separate undo log). Each tuple has xmin (creating transaction) and xmax (deleting transaction). Visibility is determined by comparing these XIDs against the reading transaction's snapshot. Oracle uses undo segments to reconstruct old versions, MySQL/InnoDB uses a rollback segment with undo logs. PostgreSQL's approach:
- Pros: No undo tablespace management, reads never block writes
- Cons: Table bloat (dead tuples), need for VACUUM, larger tuple header overhead (23 bytes minimum)

**Q2: What is the impact of long-running transactions on PostgreSQL?**
**A:** Long-running transactions prevent VACUUM from cleaning dead tuples created after the transaction started (because they might still be visible to it). This causes:
- Table bloat (dead tuples accumulate)
- Index bloat (dead index entries remain)
- Transaction ID wraparound risk increases
- Increased I/O for sequential scans (scanning dead tuples)
- Replication slots can retain WAL, filling disk

**Q3: How does PostgreSQL's cost-based optimizer work?**
**A:** The optimizer estimates costs using:
- `seq_page_cost` (1.0), `random_page_cost` (4.0), `cpu_tuple_cost`, `cpu_index_tuple_cost`
- Table statistics (pg_statistic): row count, distinct values, most common values (MCV), histogram bounds, correlation
- For joins with > `geqo_threshold` (12) tables, uses Genetic Query Optimization (GEQO)
- Costs are in arbitrary units representing disk page fetches
- Considers parallel query costs and partial index paths

**Q4: Explain the WAL (Write-Ahead Log) mechanism in detail.**
**A:** WAL ensures durability through:
1. Before any data page modification, the change is first written to WAL buffer
2. WAL buffer is flushed to disk (WAL segment files) at commit
3. Data pages (dirty buffers) are written lazily by background writer/checkpointer
4. Recovery replays WAL from last checkpoint forward
- WAL segments: 16MB files (configurable with --wal-segsize)
- Full-page writes: First modification after checkpoint writes entire page to WAL (prevents torn pages)
- Checkpoint: Ensures all dirty buffers through a certain LSN are written to disk

**Q5: How does HOT (Heap-Only Tuples) optimization work?**
**A:** When an UPDATE doesn't modify any indexed columns and the new version fits on the same page:
- New tuple is placed on same page as old
- No index entry created for new version
- Old index entry points to old tuple, which chains to new via t_ctid
- Significantly reduces index bloat and I/O
- Mini-vacuum can reclaim old HOT chains within a page without full VACUUM

### Scalability & Performance

**Q6: Design a strategy for scaling PostgreSQL to handle 1M TPS.**
**A:** 
1. **Connection pooling**: PgBouncer in transaction mode (reduce from 10K app connections to 50 backend)
2. **Read replicas**: 5-10 streaming replicas for read traffic (80% of queries)
3. **Sharding**: Citus extension or application-level sharding by tenant_id
4. **Caching layer**: Redis/Memcached for hot data (reduce load by 70-80%)
5. **Partitioning**: Time-based partitioning for large tables (fast partition pruning)
6. **Hardware**: NVMe SSDs, 256GB+ RAM (fit working set in shared_buffers)
7. **Query optimization**: Prepared statements, covering indexes, avoid JOINs on hot path
8. **Async operations**: Use LISTEN/NOTIFY, batch writes, queued processing

**Q7: How would you handle a table with 10 billion rows?**
**A:**
1. **Partition by time** (range) + possibly by tenant (list): Enables parallel processing and partition pruning
2. **BRIN indexes** on timestamp columns (tiny index for huge table)
3. **Columnar storage** (cstore_fdw or Citus columnar) for analytics
4. **Archival strategy**: Move old partitions to cheaper storage, detach old partitions
5. **Parallel query**: Set `max_parallel_workers_per_gather` appropriately
6. **Materialized views** for common aggregations
7. **Consider TimescaleDB** for time-series specific optimizations (compression, continuous aggregates)

### Replication & HA

**Q8: Design a multi-region PostgreSQL deployment with <100ms write latency.**
**A:**
- **Architecture**: Primary in primary region, async replicas in other regions
- **For writes**: Route to primary region (can't avoid network latency for strong consistency)
- **For reads**: Local replicas with eventual consistency (typical lag: 10-50ms)
- **For strong reads**: Use synchronous_commit = remote_apply on critical paths
- **Conflict resolution**: Use logical replication with BDR (Bi-Directional Replication) for multi-master, with last-writer-wins or custom conflict resolution
- **Alternative**: CockroachDB or Spanner for true multi-region writes with serializable isolation

**Q9: Explain the trade-offs between synchronous and asynchronous replication.**
**A:**
| Aspect | Synchronous | Asynchronous |
|--------|------------|--------------|
| Durability | No data loss on failover | Potential data loss (RPO > 0) |
| Latency | Higher (network RTT added) | Lower |
| Throughput | Lower (limited by network) | Higher |
| Availability | Lower (standby failure blocks writes) | Higher |

Best practice: `synchronous_standby_names = 'ANY 1 (s1, s2, s3)'` — quorum-based for availability without sacrificing durability.

---

## Scenario-Based Questions

### Scenario 1: Mysterious Slow Queries

**Problem:** Application response time increased from 50ms to 5s overnight. No code changes deployed.

**Investigation approach:**
```sql
-- 1. Check for long-running transactions blocking VACUUM
SELECT pid, xact_start, state, query FROM pg_stat_activity 
WHERE state != 'idle' ORDER BY xact_start;

-- 2. Check table bloat (dead tuples)
SELECT relname, n_dead_tup, n_live_tup, 
       n_dead_tup::float / (n_live_tup + 1) as dead_ratio
FROM pg_stat_user_tables WHERE n_dead_tup > 10000 ORDER BY dead_ratio DESC;

-- 3. Check for missing index (seq scans on large tables)
SELECT relname, seq_scan, seq_tup_read, idx_scan
FROM pg_stat_user_tables WHERE seq_scan > 100 ORDER BY seq_tup_read DESC;

-- 4. Check pg_stat_statements for query plan changes
SELECT query, mean_exec_time, calls FROM pg_stat_statements 
ORDER BY mean_exec_time DESC LIMIT 10;

-- 5. Check if autovacuum is running/blocked
SELECT * FROM pg_stat_progress_vacuum;
```

**Root cause examples:**
- Statistics became stale after large data load → `ANALYZE`
- Table bloat due to stuck autovacuum → Kill blocking transaction, run VACUUM
- Index corruption → `REINDEX CONCURRENTLY`
- Disk filled up, temp files on slow storage

### Scenario 2: Connection Exhaustion

**Problem:** Application throws "FATAL: too many connections" during peak traffic.

**Solution architecture:**
```
Application Pods (100 pods × 10 connections = 1000)
         │
         ▼
    PgBouncer (transaction mode)
    - max_client_conn = 5000
    - default_pool_size = 30
    - reserve_pool_size = 10
    - server_idle_timeout = 600
         │
         ▼
    PostgreSQL (max_connections = 100)
    - 30 for app queries
    - 10 reserve
    - 5 for superuser
    - 5 for monitoring
    - 5 for replication
    - 45 buffer
```

### Scenario 3: Data Migration with Zero Downtime

**Problem:** Migrate a 2TB database to new schema without downtime.

**Approach:**
```
Phase 1: Dual-write
- Add new columns/tables alongside old
- Application writes to both old and new structures
- Backfill historical data in batches (chunked by ID ranges)

Phase 2: Shadow reads
- Read from new structure, compare with old
- Fix any inconsistencies

Phase 3: Cutover
- Switch reads to new structure
- Keep dual-write for rollback safety

Phase 4: Cleanup
- Remove old structure
- Drop dual-write code

Tools:
- pg_logical for replication-based migration
- pgloader for bulk data movement
- gh-ost pattern adapted for PostgreSQL
```

### Scenario 4: XID Wraparound Emergency

**Problem:** Alerts show database approaching XID wraparound (200M XIDs remaining).

**Emergency response:**
```sql
-- 1. Identify oldest frozen XID
SELECT datname, age(datfrozenxid) FROM pg_database ORDER BY age DESC;

-- 2. Find tables needing vacuum
SELECT relname, age(relfrozenxid) FROM pg_class 
WHERE relkind = 'r' ORDER BY age(relfrozenxid) DESC LIMIT 20;

-- 3. Run aggressive vacuum
VACUUM FREEZE verbose largest_table;

-- 4. If vacuum is stuck, find blocking queries
SELECT * FROM pg_locks WHERE NOT granted;

-- 5. Temporary relief: increase autovacuum workers
ALTER SYSTEM SET autovacuum_max_workers = 6;
ALTER SYSTEM SET autovacuum_freeze_max_age = 100000000;
SELECT pg_reload_conf();

-- Prevention:
-- - Monitor age(datfrozenxid) < 500M
-- - Tune autovacuum for large tables
-- - Never disable autovacuum
-- - Kill idle-in-transaction sessions
```

### Scenario 5: Designing a Multi-Tenant SaaS Database

**Requirements:** 10K tenants, largest tenant has 100M rows, smallest has 1K rows.

**Architecture decision:**
```
Option A: Shared table with tenant_id (chosen for <1000 tenants)
├── Simple operations
├── Connection pooling works
├── Row-level security for isolation
└── Challenge: Noisy neighbor, migrations affect all

Option B: Schema per tenant (chosen for 100-10K tenants)
├── Good isolation
├── Independent migrations possible
├── pg_dump per tenant for backup
└── Challenge: Connection pooling, schema cache bloat

Option C: Database per tenant (chosen for <100 enterprise tenants)
├── Complete isolation
├── Independent scaling
├── Easy compliance (data residency)
└── Challenge: Operational overhead, resource waste

Recommended hybrid:
- Shared tables with hash partitioning by tenant_id
- Row-level security policies
- Citus for distributed execution
- Separate connection pools per tier (free/pro/enterprise)
```

```sql
-- Row-Level Security implementation
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::int);
    
-- Set per-request
SET app.current_tenant = '42';
SELECT * FROM orders; -- Only sees tenant 42's orders
```

### Scenario 6: Handling Hot Rows (Counter Pattern)

**Problem:** Single row updated 100K times/second (like a viral post's view counter).

**Solutions:**
```sql
-- Solution 1: Distributed counter table
CREATE TABLE post_view_counts (
    post_id bigint,
    bucket_id int,  -- 0-99
    count bigint DEFAULT 0,
    PRIMARY KEY (post_id, bucket_id)
);

-- Write: Random bucket (distributes lock contention)
UPDATE post_view_counts 
SET count = count + 1 
WHERE post_id = :id AND bucket_id = (random()*99)::int;

-- Read: Sum all buckets
SELECT sum(count) FROM post_view_counts WHERE post_id = :id;

-- Solution 2: Append-only with periodic rollup
CREATE TABLE post_views_raw (
    post_id bigint,
    viewed_at timestamptz DEFAULT now()
) PARTITION BY RANGE (viewed_at);

-- Background job aggregates periodically
INSERT INTO post_view_counts (post_id, count)
SELECT post_id, count(*) FROM post_views_raw 
WHERE viewed_at > :last_aggregation
GROUP BY post_id
ON CONFLICT (post_id) DO UPDATE SET count = post_view_counts.count + EXCLUDED.count;

-- Solution 3: Redis as write buffer, periodic flush to PG
-- (Highest throughput, eventual consistency)
```

---

## Performance Tuning Cheatsheet

### Critical postgresql.conf Settings
```ini
# Memory
shared_buffers = '25% of RAM'          # e.g., 64GB for 256GB server
effective_cache_size = '75% of RAM'     # Hint for planner
work_mem = '50MB'                       # Per sort/hash operation
maintenance_work_mem = '2GB'            # VACUUM, CREATE INDEX
huge_pages = try                        # Reduce TLB misses

# WAL
wal_buffers = '64MB'
wal_compression = on                    # PG15+: lz4
max_wal_size = '10GB'                   # Before forced checkpoint
min_wal_size = '1GB'
checkpoint_completion_target = 0.9

# Query Planning
random_page_cost = 1.1                  # For SSD (default 4.0 for HDD)
effective_io_concurrency = 200          # For SSD
default_statistics_target = 500         # More accurate plans

# Parallelism
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4
parallel_tuple_cost = 0.001
parallel_setup_cost = 100

# Autovacuum
autovacuum_max_workers = 4
autovacuum_naptime = '10s'
autovacuum_vacuum_scale_factor = 0.01   # More aggressive than default 0.2
autovacuum_analyze_scale_factor = 0.005
autovacuum_vacuum_cost_delay = '2ms'    # Faster vacuum
```

---

## Key Differences: PostgreSQL vs Others

| Feature | PostgreSQL | MySQL/InnoDB | Oracle |
|---------|-----------|-------------|--------|
| MVCC Storage | In-heap (all versions) | Undo log (rollback segment) | Undo tablespace |
| Cleanup | VACUUM required | Purge thread (automatic) | Automatic |
| Replication | Logical + Physical | Binlog-based | Data Guard + GoldenGate |
| Partitioning | Declarative (native) | Native (range/list/hash) | Advanced (interval, reference) |
| JSON | JSONB (binary, indexed) | JSON (text-based) | JSON (BLOB-based) |
| Extensions | Rich ecosystem | Limited (UDF/plugins) | Cartridges |
| Max DB Size | Unlimited | 64TB (InnoDB) | Unlimited |
| Concurrency | SSI (serializable) | Gap locks + MVCC | Read consistency |
| Process Model | Process-per-conn | Thread-per-conn | Process + threads |

