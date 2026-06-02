# YugabyteDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [DocDB Storage Engine](#docdb-storage-engine)
3. [Raft Consensus & Replication](#raft-consensus--replication)
4. [YSQL (PostgreSQL-compatible) API](#ysql-api)
5. [YCQL (Cassandra-compatible) API](#ycql-api)
6. [Sharding & Data Distribution](#sharding--data-distribution)
7. [Distributed Transactions](#distributed-transactions)
8. [Multi-Region Deployments](#multi-region-deployments)
9. [High Availability & Fault Tolerance](#high-availability--fault-tolerance)
10. [Performance & Tuning](#performance--tuning)
11. [Production Deployment Patterns](#production-deployment-patterns)
12. [Security](#security)
13. [Use Case Architectures](#use-case-architectures)
14. [Staff Architect Interview Questions](#staff-architect-interview-questions)
15. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is YugabyteDB?
```
YugabyteDB is a high-performance distributed SQL database designed for
global, internet-scale applications. Inspired by Google Spanner, it provides
strong consistency, horizontal scalability, and PostgreSQL compatibility.

Key characteristics:
- PostgreSQL-compatible (wire protocol, SQL syntax, extensions)
- Distributed SQL with automatic sharding
- Strong consistency (Raft consensus per tablet)
- Horizontal scaling (add nodes to scale)
- Multi-region with synchronous replication
- Hybrid Logical Clock (HLC) for global ordering
- Built on DocDB (enhanced RocksDB per tablet)
- Supports both SQL (YSQL) and NoSQL (YCQL) APIs

NOT designed for:
- Single-node deployments (minimum 3 nodes for HA)
- HTAP (heavy analytics - use dedicated OLAP)
- Ultra-low latency (< 1ms) for single-region simple reads
- Very small datasets where distribution overhead isn't justified
- Legacy stored procedures requiring full PG procedural extensions

Comparison:
┌────────────────────┬────────────┬──────────────┬──────────────┬────────────┐
│                    │ YugabyteDB │ CockroachDB  │ TiDB         │ Spanner    │
├────────────────────┼────────────┼──────────────┼──────────────┼────────────┤
│ SQL Compatibility  │ PostgreSQL │ PostgreSQL   │ MySQL        │ Custom SQL │
│ Consensus          │ Raft/tablet│ Raft/range   │ Raft/region  │ Paxos      │
│ Clock              │ HLC        │ HLC          │ TSO/PD       │ TrueTime   │
│ Storage Engine     │ DocDB(RocksDB)│ Pebble     │ TiKV(RocksDB)│ Colossus  │
│ Sharding           │ Hash+Range │ Range        │ Range        │ Range      │
│ NoSQL API          │ YCQL(CQL)  │ No           │ No           │ No         │
│ Multi-region       │ Sync + Async│ Sync        │ Async+Sync   │ Sync       │
│ Geo-partitioning   │ Yes        │ Yes          │ Limited      │ Yes        │
│ Open Source        │ Yes (Apache)│ BSL→Apache  │ Apache       │ No (GCP)   │
│ Managed Service    │ Aeon       │ Cockroach Cloud│ TiDB Cloud │ GCP only   │
└────────────────────┴────────────┴──────────────┴──────────────┴────────────┘
```

### Full Cluster Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    YUGABYTEDB CLUSTER ARCHITECTURE                            │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    YB-MASTER (Cluster Metadata)                        │   │
│  │                                                                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ YB-Master 1  │  │ YB-Master 2  │  │ YB-Master 3  │               │   │
│  │  │ (LEADER)     │  │ (FOLLOWER)   │  │ (FOLLOWER)   │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                                                                       │   │
│  │  Responsibilities:                                                    │   │
│  │  - Catalog manager (table metadata, schema)                          │   │
│  │  - Tablet directory (which TServer hosts which tablet)               │   │
│  │  - Cluster coordination (node membership)                            │   │
│  │  - Load balancing (tablet leader distribution)                       │   │
│  │  - DDL operations (CREATE/ALTER/DROP TABLE)                          │   │
│  │  - Raft consensus for its own metadata                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    YB-TSERVER (Data Layer)                             │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │  YB-TServer 1                                                │    │   │
│  │  │                                                               │    │   │
│  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │    │   │
│  │  │  │ Tablet A   │ │ Tablet B   │ │ Tablet C   │              │    │   │
│  │  │  │ (LEADER)   │ │ (FOLLOWER) │ │ (LEADER)   │              │    │   │
│  │  │  │            │ │            │ │            │              │    │   │
│  │  │  │ ┌────────┐ │ │ ┌────────┐ │ │ ┌────────┐ │              │    │   │
│  │  │  │ │DocDB   │ │ │ │DocDB   │ │ │ │DocDB   │ │              │    │   │
│  │  │  │ │(RocksDB│ │ │ │(RocksDB│ │ │ │(RocksDB│ │              │    │   │
│  │  │  │ │ + Raft)│ │ │ │ + Raft)│ │ │ │ + Raft)│ │              │    │   │
│  │  │  │ └────────┘ │ │ └────────┘ │ │ └────────┘ │              │    │   │
│  │  │  └────────────┘ └────────────┘ └────────────┘              │    │   │
│  │  │                                                               │    │   │
│  │  │  ┌─────────────────────────────────────────────────────┐    │    │   │
│  │  │  │ YSQL Layer (PostgreSQL query engine)                  │    │    │   │
│  │  │  │ - PG query parser, analyzer, optimizer                │    │    │   │
│  │  │  │ - Distributed execution coordinator                   │    │    │   │
│  │  │  │ - Transaction manager                                 │    │    │   │
│  │  │  └─────────────────────────────────────────────────────┘    │    │   │
│  │  │                                                               │    │   │
│  │  │  ┌─────────────────────────────────────────────────────┐    │    │   │
│  │  │  │ YCQL Layer (Cassandra query engine)                   │    │    │   │
│  │  │  │ - CQL parser                                          │    │    │   │
│  │  │  │ - Partition routing                                   │    │    │   │
│  │  │  └─────────────────────────────────────────────────────┘    │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                       │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                         │   │
│  │  │  YB-TServer 2    │  │  YB-TServer 3    │  (similar structure)    │   │
│  │  └──────────────────┘  └──────────────────┘                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Key architectural decisions:                                                │
│  - Every TServer has both YSQL + YCQL endpoints                            │
│  - Tablets are the unit of data distribution (like Spanner splits)          │
│  - Each tablet is a Raft group (leader + 2 followers across TServers)      │
│  - Client connects to ANY TServer (query routed internally)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## DocDB Storage Engine

### DocDB Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DOCDB STORAGE ENGINE (per tablet)                          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  TABLET (unit of sharding + replication)                              │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │  RAFT CONSENSUS LAYER                                        │    │   │
│  │  │  - Replicates WAL entries to peers                           │    │   │
│  │  │  - Leader lease (read serving without round-trip)            │    │   │
│  │  │  - Log entries → applied to local RocksDB                   │    │   │
│  │  └────────────────────────────┬────────────────────────────────┘    │   │
│  │                                │ apply                              │   │
│  │  ┌────────────────────────────▼────────────────────────────────┐    │   │
│  │  │  DOCDB KEY-VALUE LAYER                                       │    │   │
│  │  │                                                               │    │   │
│  │  │  Two RocksDB instances per tablet:                           │    │   │
│  │  │                                                               │    │   │
│  │  │  ┌────────────────────────────────────────────────────────┐  │    │   │
│  │  │  │  REGULAR DB (committed data)                            │  │    │   │
│  │  │  │  - Final committed values                               │  │    │   │
│  │  │  │  - Key format: DocKey + SubDocKey + HybridTimestamp     │  │    │   │
│  │  │  │  - Sorted by key (RocksDB LSM tree)                    │  │    │   │
│  │  │  │  - Compaction removes old MVCC versions                 │  │    │   │
│  │  │  └────────────────────────────────────────────────────────┘  │    │   │
│  │  │                                                               │    │   │
│  │  │  ┌────────────────────────────────────────────────────────┐  │    │   │
│  │  │  │  INTENTS DB (provisional/uncommitted data)              │  │    │   │
│  │  │  │  - Write intents for in-progress transactions           │  │    │   │
│  │  │  │  - Maps: key → transaction_id + provisional_value      │  │    │   │
│  │  │  │  - Cleaned up on commit (moved to Regular DB)          │  │    │   │
│  │  │  │  - Cleaned up on abort (deleted)                        │  │    │   │
│  │  │  └────────────────────────────────────────────────────────┘  │    │   │
│  │  │                                                               │    │   │
│  │  │  Key encoding (YSQL example):                                 │    │   │
│  │  │  table_id | primary_key_col1 | primary_key_col2 |            │    │   │
│  │  │  column_id | hybrid_timestamp → value                        │    │   │
│  │  │                                                               │    │   │
│  │  │  Hybrid Logical Clock (HLC):                                  │    │   │
│  │  │  - Combines physical time + logical counter                   │    │   │
│  │  │  - Physical: wall clock (microsecond resolution)             │    │   │
│  │  │  - Logical: counter for same-microsecond ordering            │    │   │
│  │  │  - Guarantees: if event A causes B, HLC(A) < HLC(B)         │    │   │
│  │  │  - Max clock skew tolerance: 500ms (configurable)            │    │   │
│  │  └────────────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Distributed Transactions

### Two-Phase Commit
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED TRANSACTION (2PC)                              │
│                                                                              │
│  Transaction: Transfer $100 from Account A (Tablet 1) to Account B (Tab 2) │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Step 1: BEGIN TRANSACTION                                            │   │
│  │                                                                       │   │
│  │ Client → TServer (any) → assigns transaction_id + start_time (HLC)  │   │
│  │ Transaction status tablet tracks this txn's state                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Step 2: WRITE INTENTS (provisional records)                          │   │
│  │                                                                       │   │
│  │  Tablet 1 (Account A):                                               │   │
│  │  IntentsDB: {key=AccountA, txn=T1, value=balance-100}               │   │
│  │  (Raft replicated to tablet 1 peers)                                 │   │
│  │                                                                       │   │
│  │  Tablet 2 (Account B):                                               │   │
│  │  IntentsDB: {key=AccountB, txn=T1, value=balance+100}               │   │
│  │  (Raft replicated to tablet 2 peers)                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Step 3: COMMIT (2PC)                                                  │   │
│  │                                                                       │   │
│  │  Phase 1 (Prepare): Not needed - intents already durable             │   │
│  │                                                                       │   │
│  │  Phase 2 (Commit):                                                    │   │
│  │  - Write commit record to transaction status tablet                  │   │
│  │  - Commit time = current HLC (determines MVCC visibility)           │   │
│  │  - Single Raft write = atomic commit decision                        │   │
│  │                                                                       │   │
│  │  Async cleanup:                                                       │   │
│  │  - Move intents to Regular DB (with commit timestamp)                │   │
│  │  - Delete from IntentsDB                                              │   │
│  │  - This is asynchronous (reads check txn status if intent found)    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Conflict resolution:                                                        │
│  - Read encounters an intent from another txn T2:                           │
│    1. Check T2's status (committed? aborted? pending?)                     │
│    2. If T2 committed: read committed value                                 │
│    3. If T2 aborted: ignore intent                                          │
│    4. If T2 pending: wait or abort T2 (if older priority wins)             │
│                                                                              │
│  Isolation levels:                                                           │
│  - Snapshot Isolation (default): Read from consistent snapshot              │
│  - Serializable: Detects read-write conflicts (SSI)                         │
│  - Read Committed: Each statement sees latest committed data                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Region Deployments

### Deployment Topologies
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-REGION TOPOLOGIES                                    │
│                                                                              │
│  1. SYNCHRONOUS MULTI-REGION (RF=3 across 3 regions):                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  ┌──────────┐       ┌──────────┐       ┌──────────┐               │   │
│  │  │ Region A │       │ Region B │       │ Region C │               │   │
│  │  │ (Leader) │◄─Raft─►│(Follower)│◄─Raft─►│(Follower)│               │   │
│  │  │  TServer │       │  TServer │       │  TServer │               │   │
│  │  └──────────┘       └──────────┘       └──────────┘               │   │
│  │                                                                       │   │
│  │  Write latency: 2× inter-region RTT (leader→quorum)                 │   │
│  │  Read latency: Local (leader lease serves reads locally)             │   │
│  │  Availability: Survives 1 region failure                             │   │
│  │  Use case: Global apps needing strong consistency                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  2. GEO-PARTITIONING (data pinned to regions):                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  US data: Leader + Followers in US regions only                      │   │
│  │  EU data: Leader + Followers in EU regions only                      │   │
│  │  APAC data: Leader + Followers in APAC regions only                 │   │
│  │                                                                       │   │
│  │  CREATE TABLESPACE us_east WITH (replica_placement =                 │   │
│  │    '{"num_replicas":3, "placement_blocks":[                         │   │
│  │      {"cloud":"aws","region":"us-east-1","zone":"a","min_replicas":1},│  │
│  │      {"cloud":"aws","region":"us-east-1","zone":"b","min_replicas":1},│  │
│  │      {"cloud":"aws","region":"us-east-2","zone":"a","min_replicas":1} │  │
│  │    ]}');                                                              │   │
│  │                                                                       │   │
│  │  CREATE TABLE users (..., region TEXT) PARTITION BY LIST (region);   │   │
│  │  CREATE TABLE users_us PARTITION OF users FOR VALUES IN ('US')      │   │
│  │    TABLESPACE us_east;                                               │   │
│  │                                                                       │   │
│  │  Write latency: Low (within region)                                  │   │
│  │  Data residency: Enforced (GDPR compliance)                          │   │
│  │  Use case: Data sovereignty, regulatory compliance                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  3. xCLUSTER (Asynchronous Replication):                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  ┌──────────────┐         async          ┌──────────────┐           │   │
│  │  │  Primary      │ ────────────────────▶  │  Standby      │           │   │
│  │  │  Cluster      │                        │  Cluster      │           │   │
│  │  │  (US-East)    │                        │  (EU-West)    │           │   │
│  │  └──────────────┘                        └──────────────┘           │   │
│  │                                                                       │   │
│  │  Write latency: Local (no cross-region wait)                         │   │
│  │  Replication lag: Seconds (async)                                    │   │
│  │  Use case: DR, read replicas in other regions                        │   │
│  │  Modes: unidirectional or bidirectional (active-active)             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  4. READ REPLICAS:                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Primary cluster (RF=3, US) + Read replica cluster (EU)              │   │
│  │  - Read replicas receive async Raft log updates                     │   │
│  │  - Serve reads locally (slightly stale)                              │   │
│  │  - Cannot serve writes                                               │   │
│  │  - Reduce read latency for remote users                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sharding & Data Distribution

### Hash vs Range Sharding
```
┌─────────────────────────────────────────────────────────────────┐
│                    SHARDING STRATEGIES                            │
│                                                                   │
│  HASH SHARDING (default for YSQL):                              │
│  - Primary key hashed → 2-byte hash → tablet assignment         │
│  - Even distribution regardless of data pattern                  │
│  - Good for: Point lookups, random access patterns              │
│  - Bad for: Range scans on primary key                           │
│                                                                   │
│  Example: CREATE TABLE orders (id INT, ...) SPLIT INTO 8 TABLETS;│
│  Row with id=42: hash(42)=0xA3F1 → tablet 5 (of 8)            │
│                                                                   │
│  RANGE SHARDING:                                                 │
│  - Rows ordered by primary key across tablets                    │
│  - Good for: Range scans, ordered access                         │
│  - Bad for: Sequential inserts (hot tablet at the end)          │
│                                                                   │
│  Example: CREATE TABLE events (ts TIMESTAMP, ...)               │
│    SPLIT AT VALUES (('2024-01-01'), ('2024-04-01'), ('2024-07-01'));│
│                                                                   │
│  COLOCATED TABLES:                                               │
│  - Multiple small tables share a single tablet                   │
│  - Reduces tablet count for many-small-table databases          │
│  - JOINs between colocated tables are local (fast)              │
│  - CREATE DATABASE mydb WITH COLOCATION = true;                 │
│                                                                   │
│  Tablet splitting:                                               │
│  - Automatic when tablet exceeds threshold (default: varies)    │
│  - Manual: ALTER TABLE ... SPLIT AT VALUES (...)                │
│  - Pre-split at CREATE TABLE time for known patterns            │
│                                                                   │
│  Default: 1 tablet per TServer per table                        │
│  Recommended: Create with SPLIT INTO N TABLETS where            │
│  N = num_tservers × tablets_per_tserver (e.g., 3 × 2 = 6)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Performance & Tuning

### Key Optimizations
```
Connection pooling:
- YugabyteDB uses 1 PG backend per connection (like PostgreSQL)
- Use connection pooler: PgBouncer or Odyssey
- Recommended: 10-20 connections per TServer core
- Use YugabyteDB Smart Driver (topology-aware load balancing)

Colocation for small tables:
- Eliminate per-table tablet overhead
- JOINs between colocated tables avoid network round-trips
- Best for: Reference data, config tables, lookup tables

Batch operations:
- Use multi-row INSERT: INSERT INTO t VALUES (1,..),(2,..),(3,..);
- Use COPY for bulk loading
- Batch size: 100-500 rows per statement

Index strategies:
- Primary key: Hash by default (point lookups)
  CREATE TABLE t (id INT PRIMARY KEY);  -- hash-sharded
  
- Range primary key (for range scans):
  CREATE TABLE t (id INT, PRIMARY KEY (id ASC));
  
- Secondary indexes: Hash or range
  CREATE INDEX idx ON t (col) SPLIT INTO 4 TABLETS;
  
- Covering indexes (avoid table lookup):
  CREATE INDEX idx ON t (col) INCLUDE (other_col);
  
- Partial indexes:
  CREATE INDEX idx ON t (col) WHERE status = 'active';

Performance targets (per TServer, 8 cores, 32GB RAM):
┌────────────────────────────────────────────────────────┐
│ Operation          │ Throughput    │ Latency (p99)     │
├────────────────────┼──────────────┼───────────────────┤
│ Point read         │ 20K ops/sec  │ 2-5 ms            │
│ Point write        │ 10K ops/sec  │ 5-10 ms           │
│ Range scan (100 rows)│ 5K ops/sec │ 10-20 ms          │
│ Cross-shard txn    │ 3K txns/sec  │ 15-30 ms          │
└────────────────────┴──────────────┴───────────────────┘
```

---

## Production Deployment Patterns

### Sizing & Configuration
```
┌───────────────────────────────────────────────────────────────────────────┐
│ Workload           │ TServers │ CPU/TS │ RAM/TS │ Disk/TS │ RF          │
├────────────────────┼──────────┼────────┼────────┼─────────┼─────────────┤
│ Dev/Test           │ 3        │ 4      │ 16 GB  │ 100 GB  │ 3           │
│ Small Prod         │ 3-5      │ 8      │ 32 GB  │ 500 GB  │ 3           │
│ Medium Prod        │ 5-9      │ 16     │ 64 GB  │ 1 TB    │ 3           │
│ Large Prod         │ 9-15     │ 32     │ 128 GB │ 2 TB    │ 3           │
│ Multi-region       │ 3+ per   │ 16+    │ 64 GB+ │ 1 TB+   │ 3 (across  │
│                    │ region   │        │        │         │  regions)   │
└────────────────────┴──────────┴────────┴────────┴─────────┴─────────────┘

Key configurations (yb-tserver flags):
  --tserver_flags="
    rocksdb_compact_flush_rate_limit_bytes_per_sec=256000000,
    rocksdb_universal_compaction_size_ratio=20,
    yb_num_shards_per_tserver=2,
    ysql_num_shards_per_tserver=2,
    enable_automatic_tablet_splitting=true,
    tablet_split_low_phase_shard_count_per_node=8,
    tablet_split_high_phase_shard_count_per_node=24
  "

Backup & PITR (Point-in-Time Recovery):
  - Distributed snapshots (consistent across all tablets)
  - Stored in: S3, GCS, Azure Blob, NFS
  - PITR: Restore to any point within retention window
  - Retention: configurable (default varies by plan)
  - RPO: Seconds (with PITR), backup interval otherwise
  - RTO: Minutes (restore snapshot + replay WAL)
```

---

## Staff Architect Interview Questions

### Q1: How does YugabyteDB's HLC differ from Spanner's TrueTime?
```
Answer:
┌─────────────────────┬────────────────────────────┬──────────────────────────┐
│ Aspect              │ YugabyteDB (HLC)           │ Spanner (TrueTime)       │
├─────────────────────┼────────────────────────────┼──────────────────────────┤
│ Clock source        │ NTP (software)             │ GPS + atomic (hardware)  │
│ Uncertainty window  │ ~500ms (configurable)      │ ~7ms (tight bound)       │
│ Write behavior      │ No wait needed             │ Commit-wait (wait out    │
│                     │ (optimistic)               │  uncertainty window)     │
│ Trade-off           │ Higher parallelism         │ External consistency     │
│                     │ (no waiting)               │ (provably ordered)       │
│ Conflict handling   │ Detect + resolve at read   │ Avoid via waiting        │
│ Availability        │ Works on any hardware      │ Requires special HW      │
│ Clock skew impact   │ Possible read restart      │ Handled by wait          │
└─────────────────────┴────────────────────────────┴──────────────────────────┘

YugabyteDB approach:
- Assigns HLC timestamps to all operations
- If read encounters a value with future timestamp (due to clock skew):
  → Read restart: Retry read with updated timestamp
- Maximum clock skew: transactions with timestamps > max_skew apart
  will always be correctly ordered
- Practical impact: Very rare read restarts in well-configured clusters
```

### Q2: Explain the intent mechanism in distributed transactions
```
Answer:
Intents are provisional (uncommitted) records in the IntentsDB:

Purpose:
- Lock mechanism (prevents conflicting concurrent writes)
- Durability of uncommitted writes (replicated via Raft)
- Visibility control (other transactions can see intent exists)

Lifecycle:
1. Transaction writes → creates intent in IntentsDB
2. Intent contains: key, value, transaction_id, isolation_level
3. On COMMIT: intents moved to RegularDB with commit timestamp
4. On ABORT: intents deleted from IntentsDB

Conflict detection:
- Write-write: Second writer sees intent → checks txn status → waits or aborts
- Read-write (Serializable): Reader records read at HLC time → if concurrent
  write commits before read's txn → read's txn must restart

Advantages over traditional 2PC:
- No prepare phase needed (intents are already durable)
- Single Raft write for commit decision (fast)
- Readers not blocked (check txn status table)
- Deadlock detection via distributed wait-for graph
```

### Q3: When to use YSQL vs YCQL?
```
Answer:
Use YSQL (PostgreSQL API) when:
- Need full SQL (JOINs, subqueries, CTEs, window functions)
- Need distributed transactions (cross-tablet ACID)
- Need PostgreSQL compatibility (existing apps, ORMs)
- Need secondary indexes
- Complex queries with optimizer benefits
- Need foreign keys and constraints
- Typical: SaaS applications, financial systems

Use YCQL (Cassandra API) when:
- Need ultra-low latency (simpler query planning)
- Workload is primarily key-value / wide-column
- Don't need JOINs or complex SQL
- Need TTL on data natively
- Existing Cassandra applications migrating
- IoT / time-series with simple access patterns
- Need lightweight transactions (IF NOT EXISTS)
- Typical: IoT platforms, messaging, session stores

Performance difference:
- YCQL: ~1ms point reads (simpler code path)
- YSQL: ~2-3ms point reads (PG query engine overhead)
- For complex queries: YSQL wins (optimizer, JOINs)
```

### Q4-Q10: Additional Questions
```
Q4: How does tablet splitting work?
- Automatic: When tablet size exceeds threshold
- Phases: low (initial split to N tablets/node), high (full splitting)
- Process:
  1. Leader tablet detects split condition
  2. Reports to YB-Master
  3. Master approves and records split in catalog
  4. Tablet splits into two (new key range boundary)
  5. Child tablets inherit parent's Raft group temporarily
  6. New Raft groups formed for children
  7. Parent tablet eventually garbage collected
- Zero downtime: Reads/writes continue during split

Q5: How does follower reads work?
- Follower reads allow reading from non-leader tablet replicas
- Must specify staleness tolerance (e.g., "read data up to 10s old")
- Follower checks: "Is my data fresh enough for this request?"
- If yes: Serve locally (no leader round-trip)
- If no: Wait for replication to catch up or redirect to leader
- Use case: Reduce read latency in multi-region (read from local follower)
- Config: SET yb_read_from_followers = true; SET yb_follower_read_staleness_ms = 10000;

Q6: What is leader lease and why does it matter?
- Leader lease: Raft leader holds a time-bounded lease
- During lease: Leader can serve reads without consensus round-trip
- Without lease: Every read requires majority confirmation (slow)
- Lease duration: Typically 2 seconds
- On leader failure: New leader waits for old lease to expire
- Guarantees: No stale reads from old leader after new leader elected
- Impact: Reads from leader are fast (local), writes still need consensus

Q7: How does YugabyteDB handle node failure?
1. Detection: Master and peers detect via heartbeat timeout (15s default)
2. Leader re-election: Raft groups with leader on failed node elect new leader
3. Under-replicated tablets: Master identifies tablets below RF
4. Re-replication: New replica created on surviving nodes
5. Timeline:
   - Read/write available: Within seconds (leader re-election)
   - Full RF restored: Minutes (data re-replication)
6. No data loss if semi-sync configured properly

Q8: Explain colocated tables and when to use them
- Colocated tables share a single tablet
- Default: Each table gets its own set of tablets
- Colocated: Multiple tables in one tablet group
- Benefits:
  - JOINs between colocated tables are local (fast)
  - Fewer tablets (less overhead for small tables)
  - Lower resource usage for many-table databases
- When to use:
  - Database has 50+ small tables (< 1GB each)
  - Frequent JOINs between these tables
  - Multi-tenant with many small databases
- When NOT to use:
  - Large tables that need independent scaling
  - Tables with very different access patterns

Q9: How to handle schema migrations in YugabyteDB?
- DDL operations are online (non-blocking)
- ADD COLUMN: Instant (metadata change only)
- CREATE INDEX: Built in background (backfill)
  - CREATE INDEX CONCURRENTLY (recommended)
  - Backfill happens while reads/writes continue
- DROP COLUMN: Instant (metadata, data cleaned up later)
- Complex migrations: Use tools like Flyway/Liquibase
- Gotcha: Distributed DDL needs all nodes healthy

Q10: Compare YugabyteDB vs CockroachDB for a new project
- PostgreSQL compatibility: Both support PG wire protocol
  YugabyteDB: More complete PG compatibility (extensions, functions)
  CockroachDB: Growing but some PG features missing
- Sharding: YugabyteDB (hash default), CockroachDB (range only)
  Hash better for uniform distribution
  Range better for range scans
- Multi-region: Both support, similar capabilities
- NoSQL: Only YugabyteDB has YCQL (Cassandra API)
- License: YugabyteDB (Apache 2.0), CockroachDB (BSL → Apache after 3 years)
- Operational maturity: Both production-ready
- Choose YugabyteDB: Need PG extensions, want hash sharding, need NoSQL API
- Choose CockroachDB: Prefer range sharding, simpler architecture, good docs
```

---

## Scenario-Based Questions

### Scenario 1: Migrating from PostgreSQL to YugabyteDB
```
Migration strategy:

Phase 1 - Assessment (1 week):
  - Schema compatibility: Check PG extensions used
  - Query patterns: Identify potential distribution key
  - Data volume: Plan tablet count and sharding
  - Test unsupported features (if any)

Phase 2 - Schema migration:
  - Use ysql_dump or manual DDL
  - Choose sharding key for each table
  - Decide: hash vs range vs colocated
  - Create tables with appropriate SPLIT INTO

Phase 3 - Data migration:
  - Option A: ysql_dump (pg_dump compatible) + ysql restore
  - Option B: COPY FROM for bulk loading
  - Option C: YugabyteDB Voyager (recommended tool)
  - Option D: DMS / CDC for zero-downtime migration

Phase 4 - Application testing:
  - Run application against YugabyteDB
  - Profile query performance
  - Tune: Add indexes, adjust tablet count, colocation
  - Handle: Distributed latency (2-5ms vs PG 0.5ms for simple queries)

Phase 5 - Cutover:
  - Final data sync
  - Switch application connection string
  - Monitor for errors

Key gotchas:
- Distributed latency overhead for simple queries
- SERIAL/sequences may have gaps (distributed generation)
- Some PG extensions not supported
- Large IN clauses less efficient (distributed fan-out)
```

### Scenario 2: Designing a global e-commerce platform
```
Architecture:
- Geo-partitioning: Users table by region
- Orders: Hash-sharded by user_id (co-located with user data)
- Products: Read replicas globally (catalog rarely changes)
- Inventory: Regional leaders (avoid cross-region locks for stock)

Topology:
- US: 3 TServers (us-east-1a, us-east-1b, us-west-2a)
- EU: 3 TServers (eu-west-1a, eu-west-1b, eu-central-1a)
- APAC: 3 TServers (ap-south-1a, ap-south-1b, ap-southeast-1a)

Tablespace configuration:
- users_us → US tablespace (RF=3, all in US)
- users_eu → EU tablespace (RF=3, all in EU)
- products → Global (RF=3, spread across regions, read replicas everywhere)
- orders → Same region as user (follow user's tablespace)
- inventory → Per-region (leader in region, local latency for stock checks)

Result:
- User operations: Local latency (< 5ms)
- Cross-region reads (product catalog): Via read replicas (< 10ms)
- Data sovereignty: EU user data stays in EU
- Availability: Survives single region failure per data set
```

### Scenario 3: Performance degradation after 6 months
```
Common causes:
1. Tablet count too low (hot tablets):
   - Initial split insufficient for grown data
   - Fix: Enable automatic tablet splitting or manual split

2. Compaction backlog:
   - RocksDB SST files accumulating
   - Fix: Tune compaction rate limits, schedule off-peak

3. Transaction conflicts:
   - High contention on same rows
   - Fix: Redesign schema, reduce transaction scope

4. Bloated intents:
   - Long-running transactions leaving many intents
   - Fix: Set transaction timeout, fix application code

5. Connection exhaustion:
   - Too many connections per TServer
   - Fix: Add PgBouncer, reduce connection count

Monitoring to set up:
- Tablet count per TServer (should be roughly equal)
- RocksDB SST file count and size
- Transaction conflict rate
- Intent count (should be low)
- RPC latency between components
```

### Scenario 4: Supporting 100K TPS globally
```
Architecture:
- 5 regions, 3 TServers per region = 15 TServers
- Geo-partitioned by user region (most transactions are local)
- Hash sharding: 24 tablets per TServer × 15 = 360 tablets
- RF=3 within each region (local consistency)
- xCluster between regions for DR

Per-region capacity:
- 3 TServers × 32 cores = 96 cores
- Expected: 20K TPS per region (local transactions)
- Peak handling: Scale to 5 TServers per region

Key design decisions:
- Minimize cross-region transactions (< 5% of total)
- Use follower reads for non-critical reads
- Connection pooling: PgBouncer (100 connections per TServer)
- Batch writes where possible
- Pre-split tables for known access patterns
```

### Scenario 5: Handling clock skew issues
```
Symptoms:
- Occasional "Transaction restart" errors
- Read requests taking longer than expected
- Inconsistent reads (very rare, during skew)

Diagnosis:
- Check NTP sync: ntpstat on all nodes
- Monitor: yb_node_clock_skew metric
- Check: max_clock_skew_usec flag (default: 500000 = 500ms)

Solutions:
1. Immediate: Fix NTP sync on affected nodes
   - Use chrony (better than ntpd for cloud)
   - Multiple NTP sources
   - Monitor clock offset

2. Configuration:
   - --max_clock_skew_usec=500000 (default)
   - Tighter: 250000 (better consistency, stricter NTP requirement)
   - If clock skew exceeds max: TServer refuses to start

3. Application handling:
   - Retry on "Transaction restart" errors
   - Smart driver handles retries automatically
   - Set appropriate statement timeouts

4. Infrastructure:
   - Use AWS/GCP time sync services (< 1ms accuracy)
   - Dedicated NTP servers for database nodes
   - Alert if clock offset > 100ms
```
