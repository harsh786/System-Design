# TiDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Storage Engine (TiKV)](#storage-engine-tikv)
3. [Distributed SQL](#distributed-sql)
4. [HTAP (TiFlash)](#htap-tiflash)
5. [Transactions & Consistency](#transactions--consistency)
6. [Scalability & Operations](#scalability--operations)
7. [Staff Architect Interview Questions](#staff-architect-interview-questions)
8. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### TiDB Architecture
```
┌─────────────────────────────────────────────────────────┐
│                      TiDB Cluster                        │
│                                                          │
│  SQL Layer (Stateless):                                  │
│  ┌──────┐  ┌──────┐  ┌──────┐                          │
│  │ TiDB │  │ TiDB │  │ TiDB │  Parse, optimize, execute│
│  │Server│  │Server│  │Server│  MySQL protocol compatible│
│  └──┬───┘  └──┬───┘  └──┬───┘                          │
│     │         │         │                                │
│     └─────────┼─────────┘                                │
│               │                                          │
│  Storage Layer:                                          │
│  ┌────────────┼─────────────────────────────────┐       │
│  │ TiKV (Row Store)      │ TiFlash (Column Store)│       │
│  │ ┌────┐┌────┐┌────┐   │ ┌─────┐┌─────┐       │       │
│  │ │Node││Node││Node│   │ │Node ││Node │       │       │
│  │ │ 1  ││ 2  ││ 3  │   │ │  1  ││  2  │       │       │
│  │ └────┘└────┘└────┘   │ └─────┘└─────┘       │       │
│  │ (Raft consensus)      │ (Raft learner)        │       │
│  └────────────────────────────────────────────────┘       │
│                                                          │
│  Placement Driver (PD):                                  │
│  ┌────┐  ┌────┐  ┌────┐                                │
│  │ PD │  │ PD │  │ PD │  Metadata, scheduling, TSO     │
│  └────┘  └────┘  └────┘                                │
└─────────────────────────────────────────────────────────┘

Key properties:
- MySQL compatible (wire protocol + syntax)
- Horizontal scaling for BOTH compute and storage
- ACID transactions (distributed, Percolator-based)
- HTAP: Row store (OLTP) + Column store (OLAP) in one system
- Online DDL (non-blocking schema changes)
```

### Component Roles
```
TiDB Server (SQL layer):
- Stateless, horizontally scalable
- SQL parsing, optimization, execution
- Distributed execution planning
- Connection management (MySQL protocol)

TiKV (Storage, row-oriented):
- Distributed key-value store
- Raft consensus (per Region)
- MVCC with Percolator transaction model
- RocksDB as local storage engine
- Region-based sharding (96MB default)

TiFlash (Storage, column-oriented):
- Columnar replica of TiKV data
- Raft learner (async replication from TiKV)
- Vectorized execution for analytics
- MPP (Massively Parallel Processing) support

PD (Placement Driver):
- Cluster metadata management
- Timestamp Oracle (TSO) for global timestamps
- Region scheduling and load balancing
- Data placement rules
```

---

## Storage Engine (TiKV)

### Region-Based Sharding
```
All data in TiKV divided into Regions:
- Default Region size: 96MB
- Each Region = contiguous range of keys
- Each Region replicated via Raft (3 replicas default)

Region lifecycle:
- Split: Region exceeds 96MB → split into two
- Merge: Adjacent small Regions → merge
- Move: PD schedules Region moves for balance

Key encoding:
Table row:    t{tableID}_r{rowID} → row data
Table index:  t{tableID}_i{indexID}_{indexValues} → rowID

Example:
Table users (id=1, name="Alice"):
Key: t1_r1 → {id: 1, name: "Alice"}
Index on name: t1_i1_Alice → 1 (points to row)
```

### Raft Consensus (per Region)
```
Each Region has its own Raft group:
- 1 Leader + 2 Followers (RF=3)
- Leader handles reads and writes
- Writes: Leader proposes → majority ACK → commit
- Leader lease: Serves reads without consensus (lease-based reads)

Multi-Raft:
- Thousands of Regions per TiKV node
- Each Region independently elects leader
- Enables parallelism (different Regions on different leaders)
- PD ensures leaders distributed evenly across nodes
```

---

## HTAP (TiFlash)

### Hybrid Transactional/Analytical Processing
```
┌────────────────────────────────────────┐
│ Same cluster, same data, two engines:  │
│                                         │
│ OLTP queries → TiKV (row store)        │
│ OLAP queries → TiFlash (column store)  │
│                                         │
│ TiDB optimizer decides automatically:  │
│ - Point lookups → TiKV                 │
│ - Range scans → TiKV or TiFlash       │
│ - Aggregations → TiFlash              │
│ - Joins (large) → TiFlash MPP         │
└────────────────────────────────────────┘

TiFlash replication:
1. TiKV Leader applies Raft log
2. TiFlash (Raft Learner) receives same log
3. TiFlash converts row data to columnar format
4. Consistency: Reads from TiFlash use snapshot isolation
   (same MVCC timestamps as TiKV)

Typical lag: <1 second from TiKV to TiFlash
```

### MPP (Massively Parallel Processing)
```sql
-- Complex analytics automatically uses MPP via TiFlash:
SELECT region, product_category, SUM(revenue), COUNT(DISTINCT user_id)
FROM orders o
JOIN products p ON o.product_id = p.id
WHERE o.created_at >= '2024-01-01'
GROUP BY region, product_category
ORDER BY SUM(revenue) DESC;

-- TiDB optimizer detects:
-- 1. Large scan + aggregation → route to TiFlash
-- 2. Shuffles data between TiFlash nodes (MPP exchange)
-- 3. Parallel hash join across nodes
-- 4. Parallel aggregation
-- 5. Final merge at TiDB server

-- Result: Complex analytics in seconds, not minutes
-- All while OLTP continues on TiKV (no interference!)
```

---

## Transactions & Consistency

### Percolator Transaction Model
```
Based on Google Percolator (optimistic 2PC):

Transaction lifecycle:
1. Begin: Get start_ts from PD (TSO)
2. Execute: Buffer writes locally
3. Prewrite: Write locks + data to all keys (first phase)
   - Choose a "primary key" (lock)
   - Write intent (lock + data) to primary and secondary keys
4. Commit: Commit primary key (second phase)
   - Write commit record for primary at commit_ts
   - Async: Resolve secondary locks (point to committed primary)
5. Cleanup: Background cleanup of resolved locks

MVCC versions:
Key "user:1" @ ts=100 → {name: "Alice"}
Key "user:1" @ ts=200 → {name: "Alice Smith"} (updated)
Key "user:1" @ ts=300 → (delete)

Read at ts=150: Returns {name: "Alice"} (ts=100 version)
Read at ts=250: Returns {name: "Alice Smith"} (ts=200 version)
```

### Isolation Levels
```sql
-- Snapshot Isolation (default, called "REPEATABLE READ" in MySQL mode)
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
-- Reads see consistent snapshot at start_ts
-- Prevents: Dirty reads, non-repeatable reads, phantoms
-- Allows: Write skew (unlike true serializable)

-- Read Committed
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
-- Each statement sees latest committed data
-- Lower consistency, better performance under contention

-- Pessimistic transactions (default since TiDB 3.0.8):
-- Acquires locks during execution (not just at commit)
-- Better for high-contention workloads
-- Similar behavior to MySQL/InnoDB
BEGIN PESSIMISTIC;

-- Optimistic transactions:
BEGIN OPTIMISTIC;
-- Buffers writes, checks conflicts at commit
-- Better for low-contention, read-heavy workloads
-- Higher retry rate under contention
```

---

## Scalability & Operations

### Online DDL (Non-Blocking Schema Changes)
```sql
-- TiDB supports online schema changes (no table locks):
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
ALTER TABLE orders ADD INDEX idx_customer (customer_id);

-- Multi-schema change (parallel DDL, TiDB 6.2+):
ALTER TABLE users ADD COLUMN phone VARCHAR(20), ADD INDEX idx_email (email);

-- How it works:
-- 1. Schema change registered in PD
-- 2. All TiDB servers transition through schema states
--    (absent → delete-only → write-only → public)
-- 3. Each state ensures backward compatibility
-- 4. No long-running table locks

-- Caution for large tables:
-- Index creation backfills data (may increase I/O)
-- Use: ALTER TABLE ... ADD INDEX ... /* /*!90000 WITH (TIDB_BACKGROUND) */
```

### Scaling Operations
```bash
# Scale out TiKV (add storage nodes):
tiup cluster scale-out cluster-name scale-out.yaml

# Scale out TiDB (add SQL nodes):
# Add more TiDB servers behind load balancer
# Stateless: Just deploy and connect

# Scale out TiFlash (add columnar nodes):
# PD automatically rebalances Regions to new nodes

# Typical scaling scenarios:
# - Write throughput limited → Add TiKV nodes
# - Query concurrency limited → Add TiDB servers
# - Analytics too slow → Add TiFlash nodes
# - All → Scale everything proportionally
```

---

## Staff Architect Interview Questions

**Q1: How does TiDB compare to CockroachDB?**
**A:**
| Aspect | TiDB | CockroachDB |
|--------|------|-------------|
| Protocol | MySQL compatible | PostgreSQL compatible |
| HTAP | Native (TiFlash) | Limited (no built-in columnar) |
| Transaction | Percolator (optimistic/pessimistic) | SSI (serializable) |
| Storage | RocksDB (TiKV) + columnar (TiFlash) | Pebble (single engine) |
| Sharding | Region-based (96MB) | Range-based (512MB) |
| Consensus | Multi-Raft per Region | Raft per Range |
| Clock | Centralized TSO (PD) | Hybrid Logical Clock |
| Geo-distribution | Placement rules | Native multi-region |

Key difference: TiDB excels in HTAP (analytics + OLTP together). CockroachDB excels in multi-region geo-distribution.

**Q2: When would you choose TiDB?**
**A:**
- MySQL migration without application changes (wire-compatible)
- Need both OLTP and OLAP on same data (real-time analytics)
- Scale beyond single MySQL (>10TB, >100K TPS)
- Want horizontal scaling with MySQL compatibility
- Replace complex ETL pipelines (TiFlash provides real-time analytics)
- High write throughput with strong consistency

**Q3: Explain the TSO (Timestamp Oracle) and its implications.**
**A:** PD provides globally unique, monotonically increasing timestamps via TSO:
- Every transaction gets start_ts and commit_ts from TSO
- Enables snapshot isolation and MVCC across distributed nodes
- Single point of timestamp generation (PD leader)
- Performance: ~1M timestamps/second (batched allocation)
- Limitation: Cross-region deployments have TSO latency overhead
- Mitigation: Batch timestamp allocation, local TSO (in development)

---

## Scenario-Based Questions

### Scenario 1: Real-Time Analytics on Operational Data
```
Before TiDB: MySQL (OLTP) → ETL → Data Warehouse (OLAP)
- 4-6 hour delay for analytics
- Complex ETL pipelines to maintain
- Data inconsistency between systems

After TiDB:
- TiKV handles OLTP workload (point queries, transactions)
- TiFlash (Raft Learner) gets real-time columnar copy
- Analytics queries route to TiFlash (sub-second to seconds)
- Same MVCC timestamp → consistent snapshot across both engines
- Zero ETL latency, single source of truth

Architecture:
App → TiDB (OLTP) → TiKV
                    └→ TiFlash (async, <1s lag)
BI Tool → TiDB (OLAP) → TiFlash (MPP execution)
```

### Scenario 2: MySQL Sharding Migration to TiDB
```
Current state: 
- 16 MySQL shards (ProxySQL routing)
- Complex sharding logic in application
- Cross-shard queries impossible
- Resharding = months of work

Migration to TiDB:
1. Set up TiDB cluster (3 TiDB + 3 TiKV + 3 PD minimum)
2. Use TiDB Data Migration (DM) tool:
   - Reads MySQL binlog from all 16 shards
   - Merges into single TiDB table
   - Handles conflicts (table/schema merging)
3. Dual-write period (validate consistency)
4. Switch reads to TiDB
5. Switch writes to TiDB
6. Decommission MySQL shards + ProxySQL

Benefits:
- No more application sharding logic
- Cross-shard queries work naturally (distributed SQL)
- Easy scaling (add nodes, not resharding)
- Online DDL (no maintenance windows)
- Built-in analytics (TiFlash)
```

