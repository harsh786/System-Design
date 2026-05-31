# MySQL (InnoDB) - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [InnoDB Storage Engine Deep Dive](#innodb-storage-engine-deep-dive)
3. [MVCC & Undo Logs](#mvcc--undo-logs)
4. [Indexing & B+Tree Internals](#indexing--btree-internals)
5. [Transactions & Isolation Levels](#transactions--isolation-levels)
6. [Locking Mechanisms](#locking-mechanisms)
7. [Replication Architecture](#replication-architecture)
8. [Partitioning & Sharding](#partitioning--sharding)
9. [Query Optimization](#query-optimization)
10. [Scalability Patterns](#scalability-patterns)
11. [InnoDB Cluster & Group Replication](#innodb-cluster--group-replication)
12. [Performance Tuning](#performance-tuning)
13. [Staff Architect Interview Questions](#staff-architect-interview-questions)
14. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### MySQL Server Architecture
```
Client Connections (TCP/IP, Unix Socket, Named Pipe)
            │
            ▼
┌─────────────────────────────────────────────┐
│          Connection Layer                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Thread    │  │Auth      │  │Connection│  │
│  │Pool      │  │Plugin    │  │Pool      │  │
│  └──────────┘  └──────────┘  └──────────┘  │
├─────────────────────────────────────────────┤
│          SQL Layer                           │
│  ┌───────┐ ┌─────────┐ ┌─────────────────┐ │
│  │Parser │→│Optimizer│→│Execution Engine │ │
│  └───────┘ └─────────┘ └─────────────────┘ │
│  ┌──────────────┐  ┌────────────────────┐  │
│  │Query Cache   │  │Prepared Statements │  │
│  │(removed 8.0) │  │Cache               │  │
│  └──────────────┘  └────────────────────┘  │
├─────────────────────────────────────────────┤
│          Storage Engine Layer (Plugin API)    │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌────────┐ │
│  │InnoDB │ │MyISAM │ │Memory │ │NDB     │ │
│  │       │ │       │ │       │ │Cluster │ │
│  └───────┘ └───────┘ └───────┘ └────────┘ │
└─────────────────────────────────────────────┘
```

### Key Architectural Decisions
- **Thread-per-connection** model (lighter than PG's process-per-connection)
- **Pluggable storage engine** architecture
- **InnoDB as default** (since MySQL 5.5) - ACID compliant
- **Binary log** based replication (statement/row/mixed)
- **Clustered index** (data stored with primary key in InnoDB)
- **Cost-based optimizer** with histograms (MySQL 8.0+)

### Thread Architecture
```
Main threads:
├── Connection threads (one per client)
├── Master thread (background I/O coordination)
├── I/O threads (read/write)
│   ├── Read threads (innodb_read_io_threads = 4)
│   └── Write threads (innodb_write_io_threads = 4)
├── Purge threads (innodb_purge_threads = 4)
├── Page cleaner threads (innodb_page_cleaners = 4)
├── Log writer thread
├── Log flusher thread
├── Checkpoint thread
└── Buffer pool dump/load thread
```

---

## InnoDB Storage Engine Deep Dive

### Buffer Pool Architecture
```
┌─────────────────────────────────────────────┐
│              InnoDB Buffer Pool               │
│  ┌────────────────────────────────────────┐  │
│  │    LRU List (Young + Old sublist)      │  │
│  │  [Young 5/8]  │  [Old 3/8]            │  │
│  │  ←── hot ───  │  ←── cold ───→        │  │
│  └────────────────────────────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Free List │  │Flush List│  │Unzip LRU │  │
│  │(unused)  │  │(dirty)   │  │(compress)│  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                              │
│  Multiple instances: innodb_buffer_pool_instances │
└─────────────────────────────────────────────┘

Page lifecycle:
1. Read from disk → Old sublist (midpoint insertion)
2. Accessed again after innodb_old_blocks_time → Young sublist
3. Modified → Added to Flush List
4. Flushed to disk → Removed from Flush List
5. Not accessed → Ages toward tail → Evicted
```

### Tablespace Architecture
```
System Tablespace (ibdata1):
├── Data Dictionary (before MySQL 8.0)
├── Doublewrite Buffer
├── Change Buffer
├── Undo Logs (before 5.6, configurable since)
└── System transaction metadata

File-per-table (innodb_file_per_table = ON):
├── tablename.ibd - Data + Indexes
└── tablename.cfg - Metadata (transportable tablespaces)

General Tablespaces:
CREATE TABLESPACE ts1 ADD DATAFILE 'ts1.ibd' ENGINE=InnoDB;

Undo Tablespaces (MySQL 8.0+):
├── undo_001 
└── undo_002 (minimum 2, max 127)
```

### Page Structure (16KB default)
```
┌──────────────────────────────────────┐
│ FIL Header (38 bytes)                │
│ - Space ID, Page Number              │
│ - Previous/Next page pointers        │
│ - LSN of last modification           │
│ - Page type                          │
├──────────────────────────────────────┤
│ Page Header (56 bytes)               │
│ - Number of records                  │
│ - Heap top, free space pointer       │
│ - Page direction, n_direction        │
├──────────────────────────────────────┤
│ Infimum Record (smallest)            │
├──────────────────────────────────────┤
│ Supremum Record (largest)            │
├──────────────────────────────────────┤
│ User Records                         │
│ (ordered by primary key)             │
├──────────────────────────────────────┤
│ Free Space                           │
├──────────────────────────────────────┤
│ Page Directory                       │
│ (sparse directory of records)        │
├──────────────────────────────────────┤
│ FIL Trailer (8 bytes)               │
│ - Checksum                           │
└──────────────────────────────────────┘
```

### Doublewrite Buffer
```
Purpose: Prevent partial page writes (torn pages)

Write path:
1. Dirty page in buffer pool
2. Write page to doublewrite buffer (sequential write to ibdata1)
3. fsync doublewrite buffer
4. Write page to actual tablespace location (random I/O)

Recovery:
- If page in tablespace is corrupt → restore from doublewrite buffer
- If doublewrite buffer is corrupt → page in tablespace is still valid (old version)

Performance impact: ~5-10% write overhead
Can disable on ZFS/battery-backed RAID: innodb_doublewrite = OFF
```

### Change Buffer (Insert Buffer)
```
Purpose: Buffer secondary index changes when page not in buffer pool

Applicable to: INSERT, UPDATE, DELETE on non-unique secondary indexes
NOT applicable to: Unique indexes (need uniqueness check = disk read)

Merge triggers:
1. Page is read into buffer pool
2. Background merge thread
3. During crash recovery
4. Buffer reaches max size

innodb_change_buffer_max_size = 25  (% of buffer pool)
innodb_change_buffering = all  (inserts, deletes, purges, changes, all, none)
```

### Adaptive Hash Index (AHI)
```
Purpose: Automatic hash index built on frequently accessed B+Tree pages

How it works:
- Monitors B+Tree page access patterns
- If same page accessed >= 100 times with same prefix
- Builds hash index for O(1) lookups

Configuration:
innodb_adaptive_hash_index = ON  (default)
innodb_adaptive_hash_index_parts = 8  (reduce contention)

When to disable:
- Heavy write workloads (maintenance overhead)
- Many table scans (AHI thrashing)
- Visible contention on btr_search_latch
```

---

## MVCC & Undo Logs

### InnoDB MVCC Implementation
```
Each row has hidden columns:
- DB_TRX_ID (6 bytes): Transaction ID of last modification
- DB_ROLL_PTR (7 bytes): Pointer to undo log record
- DB_ROW_ID (6 bytes): Row ID (if no explicit PK)

Read View (snapshot):
- m_up_limit_id: Lowest active transaction ID (all below are visible)
- m_low_limit_id: Next transaction ID to assign (all >= are invisible)
- m_ids: List of active transaction IDs at snapshot creation
- m_creator_trx_id: Creating transaction's ID

Visibility algorithm:
1. If DB_TRX_ID == m_creator_trx_id → visible (own changes)
2. If DB_TRX_ID < m_up_limit_id → visible (committed before snapshot)
3. If DB_TRX_ID >= m_low_limit_id → not visible (started after snapshot)
4. If DB_TRX_ID in m_ids → not visible (was active at snapshot)
5. Otherwise → visible (committed between up and low limits)
```

### Undo Log Architecture
```
┌─────────────────────────────────────┐
│         Undo Tablespace             │
├─────────────────────────────────────┤
│  Rollback Segment 1                 │
│  ├── Undo Log 1 (INSERT undo)      │
│  ├── Undo Log 2 (UPDATE undo)      │
│  └── ...                            │
│  Rollback Segment 2                 │
│  ├── ...                            │
│  ...                                │
│  Rollback Segment 128 (max)         │
└─────────────────────────────────────┘

INSERT undo: Only needed for rollback (discarded after commit)
UPDATE undo: Needed for MVCC reads + rollback (purged when no reader needs it)

Purge process:
- Background thread removes old undo records
- Only when no active transaction can see old versions
- History list length = pending purge work
```

### Undo Log vs PostgreSQL MVCC
```
PostgreSQL: Old versions stored in heap → VACUUM needed
MySQL/InnoDB: Old versions in undo log → Purge thread cleans automatically

Trade-offs:
PostgreSQL:
  + Rollback is instant (just mark xmax aborted)
  - VACUUM required, table bloat
  - Larger tuple header

InnoDB:
  + No table bloat
  + Automatic purge
  - Rollback must undo changes (can be slow for large transactions)
  - Long transactions cause undo log growth
  - Consistent reads of old data may be slow (chain traversal)
```

---

## Indexing & B+Tree Internals

### Clustered Index (Primary Key)
```
InnoDB ALWAYS has a clustered index:
1. Explicit PRIMARY KEY → clustered index
2. First UNIQUE NOT NULL index → promoted to clustered
3. Neither → hidden GEN_CLUST_INDEX (6-byte row ID)

Clustered Index B+Tree:
         [Internal Node: PK values]
        /           |            \
[Leaf Node]    [Leaf Node]    [Leaf Node]
[PK|Full Row] [PK|Full Row]  [PK|Full Row]

⚠️ All data is stored IN the clustered index leaf pages
⚠️ Secondary indexes store PK value (not physical pointer)
```

### Secondary Index
```
Secondary Index B+Tree:
         [Internal Node: indexed column values]
        /              |               \
[Leaf Node]       [Leaf Node]      [Leaf Node]
[IndexCol|PK]    [IndexCol|PK]    [IndexCol|PK]

Query flow:
1. Search secondary index → Get PK value
2. Search clustered index using PK → Get full row (double lookup!)
   This is called "bookmark lookup" or "clustered index lookup"

When PK is large (e.g., UUID):
- Every secondary index stores the full PK
- Index size bloats significantly
- Better to use auto-increment INT/BIGINT as PK
```

### Covering Index (Index-Only Scan)
```sql
-- Secondary index contains all columns needed by query
CREATE INDEX idx_covering ON orders(user_id, status, total);

-- This query uses index-only scan (no clustered index lookup):
SELECT status, total FROM orders WHERE user_id = 123;

-- "Using index" in EXPLAIN means covering index used
```

### Index Condition Pushdown (ICP)
```sql
-- Without ICP (MySQL < 5.6):
-- Storage engine returns all rows matching leading index column
-- Server layer filters remaining conditions

-- With ICP (MySQL 5.6+):
-- Storage engine evaluates conditions on indexed columns
-- Fewer rows returned to server layer

CREATE INDEX idx_name_age ON users(name, age);
SELECT * FROM users WHERE name LIKE 'John%' AND age > 25;
-- ICP: Engine evaluates both name AND age at index level
```

### Index Types in MySQL
```sql
-- B+Tree (default for InnoDB)
CREATE INDEX idx_btree ON users(email);

-- Full-text index
CREATE FULLTEXT INDEX idx_ft ON articles(title, body);
SELECT * FROM articles WHERE MATCH(title, body) AGAINST('mysql optimization');

-- Spatial index (R-Tree)
CREATE SPATIAL INDEX idx_geo ON locations(point);

-- Descending index (MySQL 8.0+)
CREATE INDEX idx_desc ON orders(created_at DESC, amount ASC);

-- Invisible index (MySQL 8.0+)
ALTER TABLE orders ALTER INDEX idx_old INVISIBLE;
-- Optimizer ignores it, but it's maintained (safe to test drops)

-- Functional index (MySQL 8.0.13+)
CREATE INDEX idx_upper ON users((UPPER(name)));
SELECT * FROM users WHERE UPPER(name) = 'JOHN';

-- Multi-valued index (MySQL 8.0.17+, for JSON arrays)
CREATE INDEX idx_tags ON products((CAST(tags->'$[*]' AS UNSIGNED ARRAY)));
SELECT * FROM products WHERE 42 MEMBER OF(tags->'$[*]');
```

### Index Merge
```sql
-- MySQL can combine multiple indexes on same table
-- Types: intersection (AND), union (OR), sort-union

-- Index merge intersection
SELECT * FROM users WHERE age = 25 AND city = 'NYC';
-- Uses idx_age AND idx_city, intersects results

-- Index merge union
SELECT * FROM users WHERE age = 25 OR city = 'NYC';
-- Uses idx_age UNION idx_city
```

---

## Transactions & Isolation Levels

### MySQL/InnoDB Isolation Levels
```sql
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;  -- Dirty reads possible
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;    
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;   -- Default
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;      -- S locks on all reads
```

### Consistent Read (Non-Locking)
```
READ COMMITTED:
- New Read View created for EACH statement
- Sees latest committed data at statement start

REPEATABLE READ (default):
- Read View created at first read in transaction
- Same snapshot for entire transaction
- PREVENTS phantom reads in InnoDB! (unlike SQL standard)
  This is because InnoDB uses next-key locking for modifications

SERIALIZABLE:
- Converts all plain SELECTs to SELECT ... FOR SHARE
- Full serialization via locking
```

### Gap Locking & Phantom Prevention
```
InnoDB prevents phantoms at REPEATABLE READ using:

Next-Key Lock = Record Lock + Gap Lock

Example with index values: [10, 20, 30]

Record Lock: Lock on specific index record
Gap Lock: Lock on gap between index records
Next-Key Lock: Lock on record + gap before it

Gaps: (-∞,10), (10,20), (20,30), (30,+∞)
Next-Key Locks: (-∞,10], (10,20], (20,30], (30,+∞)

DELETE FROM t WHERE id = 25:
- Locks gap (20, 30) to prevent inserts of id=21..29
- This prevents phantoms without SERIALIZABLE level!
```

### XA Transactions (Distributed)
```sql
XA START 'txn1';
INSERT INTO orders VALUES (1, 'pending');
XA END 'txn1';
XA PREPARE 'txn1';  -- Phase 1: Prepare
XA COMMIT 'txn1';   -- Phase 2: Commit

-- Used by: Application servers, distributed transaction managers
-- Limitation: XA transactions cannot use same connection for multiple XA txns
```

---

## Locking Mechanisms

### InnoDB Lock Types
```
1. Shared Lock (S): Allows concurrent reads
   SELECT * FROM t WHERE id = 1 FOR SHARE;

2. Exclusive Lock (X): Blocks all other locks
   SELECT * FROM t WHERE id = 1 FOR UPDATE;

3. Intention Locks (table-level):
   IS: Transaction intends to set S locks on rows
   IX: Transaction intends to set X locks on rows
   Allows table-level lock checks without scanning all row locks

4. Record Lock: Lock on specific index record

5. Gap Lock: Lock on gap between index records (no other insert allowed)
   Only at REPEATABLE READ or higher

6. Next-Key Lock: Record Lock + Gap Lock (prevents phantoms)

7. Insert Intention Lock: Special gap lock for INSERT
   Multiple inserts into different positions in same gap don't block each other

8. AUTO-INC Lock: Table-level lock for auto-increment
   Modes: 0=traditional, 1=consecutive(default), 2=interleaved
   innodb_autoinc_lock_mode = 2 for high concurrency (safe with row-based replication)
```

### Lock Compatibility Matrix
```
        S    X    IS   IX
S       ✓    ✗    ✓    ✗
X       ✗    ✗    ✗    ✗
IS      ✓    ✗    ✓    ✓
IX      ✗    ✗    ✓    ✓
```

### Deadlock Detection & Handling
```
InnoDB deadlock detection:
- Wait-for graph maintained in real-time
- Instant detection (not periodic like PostgreSQL)
- Victim selection: Transaction with fewest undo log records (cheapest rollback)

innodb_deadlock_detect = ON (default)
  - Overhead at high concurrency (O(n²) in worst case)
  - Consider OFF with innodb_lock_wait_timeout = 2s at extreme concurrency

Show deadlock info:
SHOW ENGINE INNODB STATUS\G  -- Latest deadlock section
Performance_schema.data_locks
Performance_schema.data_lock_waits
```

### Optimistic vs Pessimistic Locking Patterns
```sql
-- Pessimistic: Lock row during read
BEGIN;
SELECT * FROM inventory WHERE item_id = 1 FOR UPDATE;
-- Check quantity, then update
UPDATE inventory SET quantity = quantity - 1 WHERE item_id = 1;
COMMIT;

-- Optimistic: Version-based check
SELECT id, quantity, version FROM inventory WHERE item_id = 1;
-- Application processes...
UPDATE inventory SET quantity = quantity - 1, version = version + 1
WHERE item_id = 1 AND version = :read_version;
-- If affected_rows = 0 → conflict, retry
```

---

## Replication Architecture

### Binary Log (Binlog)
```
Formats:
- STATEMENT: SQL statements logged (smaller, non-deterministic issues)
- ROW: Actual row changes logged (larger, deterministic, default in 8.0)
- MIXED: Statement by default, row for non-deterministic operations

Binlog structure:
mysql-bin.000001
├── Format Description Event
├── Previous GTIDs Event  
├── Transaction Events:
│   ├── GTID Event (UUID:sequence)
│   ├── Query Event (BEGIN)
│   ├── Table Map Event
│   ├── Write/Update/Delete Rows Event
│   └── XID Event (COMMIT)
└── ...
```

### Replication Topologies
```
1. Source → Replica (Classic)
   Source ──→ Replica1
          └─→ Replica2

2. Chain Replication
   Source → Intermediate → Replica
   (Reduces load on source)

3. Multi-Source Replication (MySQL 5.7+)
   Source1 ──┐
   Source2 ──┼──→ Replica
   Source3 ──┘
   (Data aggregation from multiple sources)

4. Circular Replication (Legacy, avoid)
   A → B → C → A

5. Group Replication / InnoDB Cluster (MySQL 5.7.17+)
   [Primary] ←→ [Secondary] ←→ [Secondary]
   (Virtually synchronous, conflict detection)
```

### GTID Replication (Global Transaction Identifiers)
```sql
-- Enable GTID
gtid_mode = ON
enforce_gtid_consistency = ON

-- GTID format: source_uuid:transaction_id
-- e.g., 3E11FA47-71CA-11E1-9E33-C80AA9429562:1-5

-- Advantages:
-- 1. Easy failover (no binlog position tracking)
-- 2. Automatic duplicate detection
-- 3. Simple to verify consistency

-- Check replication status
SELECT * FROM performance_schema.replication_connection_status;
SELECT * FROM performance_schema.replication_applier_status_by_worker;
```

### Semi-Synchronous Replication
```
Source                          Replica
  │  1. Commit locally            │
  │  2. Write binlog              │
  │  3. Send event ───────────→   │
  │                               │  4. Receive & write relay log
  │  6. Ack to client   ←────────│  5. Send ACK
  │                               │  7. Apply (async)

Guarantees:
- At least one replica has received the event
- Does NOT guarantee it's applied
- Timeout fallback to async (rpl_semi_sync_source_timeout)

-- Configuration:
INSTALL PLUGIN rpl_semi_sync_source SONAME 'semisync_source.so';
SET GLOBAL rpl_semi_sync_source_enabled = 1;
SET GLOBAL rpl_semi_sync_source_wait_for_replica_count = 1;
```

### Parallel Replication
```
MySQL 8.0 parallel replication modes:

1. DATABASE (default before 8.0.27):
   - Different databases applied in parallel
   - Limited benefit for single-database workloads

2. LOGICAL_CLOCK (default since 8.0.27):
   - Transactions that committed in same binlog group → parallel
   - Based on writeset dependency tracking
   
3. WRITESET (best performance):
   - Tracks row-level writesets
   - No conflicting writes → parallel
   - replica_parallel_type = LOGICAL_CLOCK
   - binlog_transaction_dependency_tracking = WRITESET

replica_parallel_workers = 16  (match core count)
```

---

## Partitioning & Sharding

### Native Partitioning
```sql
-- Range partitioning
CREATE TABLE orders (
    id BIGINT AUTO_INCREMENT,
    order_date DATE,
    customer_id INT,
    total DECIMAL(10,2),
    PRIMARY KEY (id, order_date)  -- Partition key must be in PK
) PARTITION BY RANGE (YEAR(order_date)) (
    PARTITION p2022 VALUES LESS THAN (2023),
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);

-- List partitioning
CREATE TABLE users (
    id BIGINT,
    region VARCHAR(20),
    name VARCHAR(100),
    PRIMARY KEY (id, region)
) PARTITION BY LIST COLUMNS(region) (
    PARTITION p_us VALUES IN ('us-east', 'us-west'),
    PARTITION p_eu VALUES IN ('eu-west', 'eu-central'),
    PARTITION p_asia VALUES IN ('asia-east', 'asia-south')
);

-- Hash partitioning
CREATE TABLE sessions (
    id BIGINT,
    user_id INT,
    data BLOB,
    PRIMARY KEY (id, user_id)
) PARTITION BY HASH(user_id) PARTITIONS 16;

-- Key partitioning (uses MySQL's internal hash)
CREATE TABLE logs (
    id BIGINT AUTO_INCREMENT,
    message TEXT,
    PRIMARY KEY (id)
) PARTITION BY KEY() PARTITIONS 8;  -- Uses PK
```

### Partition Limitations in MySQL
```
1. All columns in partition expression must be in every unique index
2. Maximum 8192 partitions per table
3. Foreign keys not supported with partitioning
4. FULLTEXT indexes not supported
5. Spatial columns not supported
6. Temporary tables cannot be partitioned
7. No partition-level locking (table-level metadata lock)
```

### Application-Level Sharding
```
Strategies:
1. Hash-based: shard_id = hash(shard_key) % num_shards
2. Range-based: shard_id based on ranges of shard_key
3. Directory-based: Lookup table maps keys to shards
4. Geo-based: Shard by region/data center

Middleware solutions:
- Vitess (YouTube's sharding solution for MySQL)
- ProxySQL (query routing + connection pooling)
- ShardingSphere (Apache)
- MySQL Router (InnoDB Cluster)

Vitess Architecture:
┌─────────┐     ┌────────┐     ┌─────────────┐
│  App    │────→│ VTGate │────→│ VTTablet    │────→ MySQL
│         │     │(proxy) │     │(per-shard   │
│         │     │        │     │ agent)      │
└─────────┘     └────────┘     └─────────────┘
                    │
              ┌─────┴─────┐
              │ Topology  │ (etcd/ZooKeeper)
              │ Service   │
              └───────────┘
```

---

## Query Optimization

### Optimizer Architecture (MySQL 8.0)
```
Query processing pipeline:
1. Parser → AST (Abstract Syntax Tree)
2. Resolver → Resolve names, check permissions
3. Optimizer → Transform + Cost-based optimization
4. Executor → Volcano-style iterator model (8.0+)

Key optimizer features:
- Cost model (server + engine costs in mysql.server_cost, mysql.engine_cost)
- Histograms (ANALYZE TABLE t UPDATE HISTOGRAM ON col WITH 256 BUCKETS)
- Derived table merging
- Subquery optimization (materialization, semi-join)
- Common Table Expression (CTE) optimization
- Window function optimization
```

### EXPLAIN FORMAT=TREE (MySQL 8.0.18+)
```sql
EXPLAIN FORMAT=TREE
SELECT u.name, COUNT(o.id) as order_count
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE u.created_at > '2024-01-01'
GROUP BY u.name
HAVING order_count > 5
ORDER BY order_count DESC
LIMIT 10;

-- Shows actual execution plan as tree
-- Also: EXPLAIN ANALYZE (executes and shows actual timing)
```

### Query Rewrite Patterns
```sql
-- 1. Convert correlated subquery to JOIN
-- Bad:
SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE total > 100);
-- Better (optimizer usually does this):
SELECT DISTINCT u.* FROM users u JOIN orders o ON u.id = o.user_id WHERE o.total > 100;

-- 2. Use derived tables for complex aggregations
SELECT u.*, o.total_spent
FROM users u
JOIN (SELECT user_id, SUM(total) as total_spent FROM orders GROUP BY user_id) o
ON u.id = o.user_id;

-- 3. Avoid functions on indexed columns
-- Bad: SELECT * FROM orders WHERE YEAR(created_at) = 2024;
-- Good: SELECT * FROM orders WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';

-- 4. Batch INSERT
INSERT INTO table VALUES (1,'a'), (2,'b'), (3,'c'), ...; -- Single statement
-- innodb_bulk_load for massive loads
SET GLOBAL innodb_autoinc_lock_mode = 2;
```

### Index Hints & Optimizer Hints
```sql
-- Index hints (legacy)
SELECT * FROM orders USE INDEX (idx_user_date) WHERE user_id = 1;
SELECT * FROM orders FORCE INDEX (idx_user_date) WHERE user_id = 1;
SELECT * FROM orders IGNORE INDEX (idx_user_date) WHERE user_id = 1;

-- Optimizer hints (MySQL 5.7.7+, preferred)
SELECT /*+ BNL(orders) */ ...  -- Block Nested Loop
SELECT /*+ NO_BNL(orders) */ ...
SELECT /*+ HASH_JOIN(t1, t2) */ ...
SELECT /*+ INDEX_MERGE(t1 idx1, idx2) */ ...
SELECT /*+ MRR(t1) */ ...  -- Multi-Range Read
SELECT /*+ JOIN_ORDER(t1, t2, t3) */ ...
SELECT /*+ MAX_EXECUTION_TIME(1000) */ ...  -- ms
SELECT /*+ SET_VAR(optimizer_switch='mrr=on') */ ...
```

---

## Scalability Patterns

### InnoDB Cluster (Native HA)
```
┌─────────────────────────────────────────────┐
│            MySQL InnoDB Cluster              │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Primary  │←→│Secondary │←→│Secondary │  │
│  │ (R/W)   │  │ (R/O)   │  │ (R/O)   │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│        ↑            ↑            ↑          │
│        └────────────┼────────────┘          │
│                     │                        │
│              ┌──────┴──────┐                 │
│              │MySQL Router │                 │
│              │(Proxy/LB)   │                 │
│              └─────────────┘                 │
└─────────────────────────────────────────────┘

Components:
1. Group Replication: Paxos-based consensus
2. MySQL Shell: Cluster management (AdminAPI)
3. MySQL Router: Connection routing

Modes:
- Single-Primary: One writer, automatic failover
- Multi-Primary: All nodes accept writes (conflict detection)
```

### Read Scaling Pattern
```
                    ┌──────────────┐
                    │   ProxySQL   │
                    │  (R/W Split) │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Primary  │ │ Replica1 │ │ Replica2 │
        │ (writes) │ │ (reads)  │ │ (reads)  │
        └──────────┘ └──────────┘ └──────────┘

ProxySQL rules:
- Write queries → Primary (hostgroup 0)
- Read queries → Replicas (hostgroup 1)
- Sticky sessions after write (avoid stale reads)
```

### Vitess for Horizontal Scaling
```
Key concepts:
- Keyspace: Logical database
- Shard: Horizontal partition of a keyspace
- VSchema: Defines sharding scheme
- Vindexes: Sharding functions (hash, region, lookup)

Resharding (zero-downtime):
1. Create target shards
2. Start replication to target shards  
3. SwitchReads: Direct reads to new shards
4. SwitchWrites: Direct writes to new shards
5. Cleanup: Remove old shards

Cross-shard queries:
- Scatter-gather for non-targeted queries
- VTGate handles join decomposition
- Lookup vindexes for efficient routing
```

---

## Performance Tuning

### Critical my.cnf Settings
```ini
[mysqld]
# Buffer Pool (50-80% of RAM)
innodb_buffer_pool_size = 100G
innodb_buffer_pool_instances = 16  # 1 per GB (up to 64)
innodb_buffer_pool_chunk_size = 1G

# Redo Log (larger = fewer checkpoints, longer recovery)
innodb_redo_log_capacity = 10G  # MySQL 8.0.30+
# Pre-8.0.30:
# innodb_log_file_size = 4G
# innodb_log_files_in_group = 2

# I/O Configuration
innodb_io_capacity = 10000       # IOPS for background tasks
innodb_io_capacity_max = 20000   # Max IOPS for flushing
innodb_flush_method = O_DIRECT   # Skip OS cache (Linux)
innodb_flush_neighbors = 0       # Disable for SSD

# Concurrency
innodb_thread_concurrency = 0    # Unlimited (kernel schedules)
innodb_read_io_threads = 16
innodb_write_io_threads = 16
innodb_purge_threads = 4

# Transaction & Locking
innodb_lock_wait_timeout = 10    # seconds
innodb_deadlock_detect = ON
innodb_print_all_deadlocks = ON

# Durability (trade-off: performance vs safety)
innodb_flush_log_at_trx_commit = 1  # 1=full durability, 2=OS cache, 0=every second
sync_binlog = 1                      # Sync binlog at each commit

# Query
join_buffer_size = 256K
sort_buffer_size = 256K
tmp_table_size = 256M
max_heap_table_size = 256M

# Connections
max_connections = 500
thread_cache_size = 100
```

### Performance Schema Queries
```sql
-- Top queries by total latency
SELECT DIGEST_TEXT, COUNT_STAR, 
       AVG_TIMER_WAIT/1000000000 as avg_ms,
       SUM_TIMER_WAIT/1000000000000 as total_sec
FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC LIMIT 10;

-- Table I/O statistics
SELECT OBJECT_NAME, COUNT_READ, COUNT_WRITE,
       SUM_TIMER_READ/1000000000 as read_ms,
       SUM_TIMER_WRITE/1000000000 as write_ms
FROM performance_schema.table_io_waits_summary_by_table
WHERE OBJECT_SCHEMA = 'mydb'
ORDER BY SUM_TIMER_WAIT DESC;

-- Lock waits
SELECT * FROM performance_schema.data_lock_waits;

-- Memory usage
SELECT EVENT_NAME, CURRENT_NUMBER_OF_BYTES_USED/1024/1024 as mb
FROM performance_schema.memory_summary_global_by_event_name
ORDER BY CURRENT_NUMBER_OF_BYTES_USED DESC LIMIT 20;
```

---

## Staff Architect Interview Questions

### Architecture & Design

**Q1: Why does InnoDB use a clustered index, and what are the implications?**
**A:** InnoDB organizes data physically by primary key (clustered B+Tree). Implications:
- Range scans on PK are sequential I/O (extremely fast)
- Secondary indexes store PK value → double lookup needed
- Large PKs (UUID) bloat ALL secondary indexes
- Insert pattern matters: Sequential PKs (auto_increment) = append-only; Random PKs (UUID) = random I/O + page splits
- Best practice: Use auto_increment BIGINT as PK, use UUID as business key in separate unique index

**Q2: Explain the redo log and undo log difference and their roles.**
**A:**
- **Redo log**: Ensures durability. Contains physical changes (page modifications). Used during crash recovery to replay committed but unflushed changes. Write-ahead log. Circular file.
- **Undo log**: Enables MVCC + rollback. Contains logical inverse of operations. Used to construct old versions for consistent reads. Stored in undo tablespace. Purged when no transaction needs old versions.

**Q3: How does Group Replication achieve consensus?**
**A:** Uses Paxos-based protocol (XCom - a variant of Mencius):
1. Transaction executes locally on originator
2. At commit time, writeset (modified PKs) is broadcast to all members
3. All members order transactions identically via total order broadcast
4. Each member independently certifies: checks for conflicting writesets
5. If no conflict → commit. If conflict → originator rolls back
6. Majority agreement required (N/2 + 1 members)
- Limitations: Cross-shard transactions, large transactions, hot rows

**Q4: What is the difference between innodb_flush_log_at_trx_commit values?**
**A:**
- `= 1`: Flush + fsync redo log at each commit. Full ACID. Safest, slowest.
- `= 2`: Flush to OS cache at each commit, fsync every second. Lose up to 1s on OS crash (not MySQL crash).
- `= 0`: Write to log buffer every second. Lose up to 1s on any crash.
- Combined with `sync_binlog`: Both = 1 for full durability in replication.

**Q5: How would you design a MySQL schema for a time-series workload?**
**A:**
```sql
CREATE TABLE metrics (
    metric_id INT,
    timestamp DATETIME(3),
    value DOUBLE,
    tags JSON,
    PRIMARY KEY (metric_id, timestamp)  -- Clustered by metric + time
) ENGINE=InnoDB
PARTITION BY RANGE (TO_DAYS(timestamp)) (
    PARTITION p20240101 VALUES LESS THAN (TO_DAYS('2024-01-02')),
    ...
);
-- Advantages: Sequential writes (append), partition pruning for time ranges
-- Drop old data: ALTER TABLE DROP PARTITION (instant, no DELETE overhead)
-- Consider: Page compression, smaller page size (8K), larger redo log
```

---

## Scenario-Based Questions

### Scenario 1: Replication Lag Spike

**Problem:** Replica lag suddenly increases from 0 to 300 seconds during peak traffic.

**Investigation:**
```sql
-- On replica:
SHOW REPLICA STATUS\G
-- Check: Seconds_Behind_Source, Relay_Log_Space, 
--        Retrieved_Gtid_Set vs Executed_Gtid_Set

-- Check if single-threaded replay is bottleneck:
SELECT * FROM performance_schema.replication_applier_status_by_worker;

-- Check for long-running transactions on replica:
SELECT * FROM information_schema.innodb_trx ORDER BY trx_started;

-- Common causes:
-- 1. Large transaction on source (ALTER TABLE, bulk DELETE)
-- 2. Single-threaded applier bottleneck
-- 3. Disk I/O saturation on replica (lower spec hardware)
-- 4. Table without primary key (full table scan for each row event)
-- 5. Replica running heavy read queries
```

**Solutions:**
1. Enable parallel replication: `replica_parallel_workers = 16`
2. Use WRITESET dependency tracking
3. Ensure all tables have PKs
4. Use multi-threaded applier
5. Upgrade replica hardware to match source
6. Split large transactions on source

### Scenario 2: Deadlock Storm

**Problem:** Application logs show hundreds of deadlocks per minute during flash sale.

**Analysis:**
```sql
-- Check latest deadlock
SHOW ENGINE INNODB STATUS\G

-- Example deadlock pattern:
-- T1: UPDATE inventory SET qty = qty - 1 WHERE item_id = 100;
-- T2: UPDATE inventory SET qty = qty - 1 WHERE item_id = 200;
-- T1: UPDATE inventory SET qty = qty - 1 WHERE item_id = 200; -- waits for T2
-- T2: UPDATE inventory SET qty = qty - 1 WHERE item_id = 100; -- deadlock!

-- Solution 1: Consistent lock ordering
-- Always lock items in ascending item_id order

-- Solution 2: SELECT FOR UPDATE with ordering
BEGIN;
SELECT * FROM inventory WHERE item_id IN (100, 200) 
ORDER BY item_id FOR UPDATE;  -- Lock in consistent order
-- Now update safely
COMMIT;

-- Solution 3: Optimistic locking with retry
UPDATE inventory SET qty = qty - 1, version = version + 1
WHERE item_id = 100 AND qty > 0 AND version = :expected_version;
-- Retry on 0 affected rows

-- Solution 4: Queue-based processing (eliminate contention entirely)
INSERT INTO inventory_changes (item_id, delta, created_at) VALUES (100, -1, NOW());
-- Background worker processes queue and updates inventory
```

### Scenario 3: Online Schema Change on 500GB Table

**Problem:** Need to add a column to a 500GB table with 0 downtime.

**Options:**
```
Option 1: MySQL 8.0 Instant DDL (if supported)
ALTER TABLE orders ADD COLUMN priority INT DEFAULT 0, ALGORITHM=INSTANT;
-- Instant: Only modifies metadata
-- Supported for: Adding columns (last position), adding/dropping virtual columns,
--                renaming columns, modifying ENUM/SET, changing index type

Option 2: pt-online-schema-change (Percona)
pt-online-schema-change --alter "ADD COLUMN priority INT DEFAULT 0" \
  --host=localhost --database=production --table=orders --execute
-- Creates shadow table, copies data via triggers, atomic rename
-- Impact: Some write amplification during copy

Option 3: gh-ost (GitHub)
gh-ost --host=source --database=production --table=orders \
  --alter="ADD COLUMN priority INT DEFAULT 0" \
  --execute --allow-on-master
-- Uses binlog streaming instead of triggers (less intrusive)
-- Controllable: Can pause, throttle, postpone cutover

Option 4: MySQL 8.0 INPLACE
ALTER TABLE orders ADD INDEX idx_new (col1, col2), ALGORITHM=INPLACE, LOCK=NONE;
-- Builds index in background
-- Brief metadata lock at start and end
```

### Scenario 4: Migrating from Single MySQL to Vitess Sharding

**Problem:** Single MySQL reaching capacity limits (100K QPS, 2TB data). Need to shard.

**Migration plan:**
```
Phase 1: Prepare
- Add sharding key column if not present (tenant_id, user_id)
- Ensure all queries include shard key
- Remove cross-shard foreign keys
- Set up Vitess infrastructure (topology service, VTGate, VTTablet)

Phase 2: Unsharded Vitess
- Route all traffic through VTGate to single MySQL
- Verify compatibility (no behavioral changes)
- Set up monitoring for Vitess layer

Phase 3: Vertical Split (optional)
- Move specific tables to separate keyspaces
- Use MoveTables workflow

Phase 4: Horizontal Sharding
- Define VSchema (sharding scheme)
- Use Reshard workflow:
  1. Create target shards
  2. VReplication copies data
  3. Catchup via binlog streaming
  4. SwitchReads (reads go to new shards)
  5. SwitchWrites (writes go to new shards)
  6. Complete: remove old shard

Phase 5: Cleanup
- Remove VReplication streams
- Drop old shard data
- Verify data integrity with VDiff
```

### Scenario 5: MySQL for Financial Transactions

**Requirements:** ACID compliance, audit trail, exactly-once processing, regulatory compliance.

**Architecture:**
```sql
-- Transaction table with idempotency key
CREATE TABLE transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    idempotency_key VARCHAR(64) UNIQUE,  -- Prevents duplicate processing
    account_id BIGINT NOT NULL,
    amount DECIMAL(19,4) NOT NULL,
    type ENUM('credit', 'debit'),
    status ENUM('pending', 'completed', 'failed', 'reversed'),
    created_at TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_account_created (account_id, created_at)
) ENGINE=InnoDB;

-- Double-entry bookkeeping
CREATE TABLE ledger_entries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    transaction_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    entry_type ENUM('debit', 'credit'),
    amount DECIMAL(19,4) NOT NULL,
    balance_after DECIMAL(19,4) NOT NULL,  -- Running balance
    created_at TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id),
    INDEX idx_account_balance (account_id, created_at DESC)
) ENGINE=InnoDB;

-- Transfer procedure
DELIMITER //
CREATE PROCEDURE transfer(
    IN p_from_account BIGINT, 
    IN p_to_account BIGINT, 
    IN p_amount DECIMAL(19,4),
    IN p_idempotency_key VARCHAR(64)
)
BEGIN
    DECLARE v_from_balance DECIMAL(19,4);
    
    -- Start transaction with consistent snapshot
    START TRANSACTION;
    
    -- Lock accounts in consistent order (prevent deadlock)
    SELECT balance INTO v_from_balance 
    FROM accounts WHERE id = LEAST(p_from_account, p_to_account) FOR UPDATE;
    SELECT balance INTO @dummy 
    FROM accounts WHERE id = GREATEST(p_from_account, p_to_account) FOR UPDATE;
    
    -- Check sufficient funds
    IF v_from_balance < p_amount THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient funds';
    END IF;
    
    -- Execute transfer...
    COMMIT;
END //
DELIMITER ;
```

**Configuration for financial workloads:**
```ini
innodb_flush_log_at_trx_commit = 1  # Full durability
sync_binlog = 1                      # Synchronized binlog
innodb_doublewrite = ON              # Prevent torn pages
innodb_checksum_algorithm = crc32    # Data integrity
transaction_isolation = READ-COMMITTED  # Minimize locking
binlog_format = ROW                  # Deterministic replication
```

---

## Key MySQL vs PostgreSQL Differences for Architects

| Aspect | MySQL/InnoDB | PostgreSQL |
|--------|-------------|-----------|
| Storage | Clustered index (PK ordered) | Heap (unordered) |
| MVCC | Undo log (reconstructs old) | In-heap versions |
| Bloat management | Automatic purge | Requires VACUUM |
| Replication | Binlog (logical) | WAL (physical) + Logical |
| Sharding | Vitess, ProxySQL | Citus, FDW |
| Isolation default | REPEATABLE READ | READ COMMITTED |
| Gap locking | Yes (at RR level) | No (uses SSI instead) |
| Connection model | Threads | Processes |
| Extensions | Limited plugins | Rich extensions |
| JSON | JSON type (text) | JSONB (binary, indexed) |
| Parallel query | Limited (8.0+) | Mature (9.6+) |
| Window functions | 8.0+ | Since 8.4 (2009) |
| CTEs | 8.0+ (optimizer aware) | Since 8.4 |
| Hot standby | Replica = read-only | Standby = read-only |
| Online DDL | INSTANT/INPLACE/COPY | Limited (concurrent index) |

