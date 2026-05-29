# CockroachDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Distributed SQL & Raft Consensus](#distributed-sql--raft-consensus)
3. [Transaction Model (Serializable)](#transaction-model-serializable)
4. [Storage Engine (Pebble)](#storage-engine-pebble)
5. [Multi-Region & Geo-Partitioning](#multi-region--geo-partitioning)
6. [Scalability & Performance](#scalability--performance)
7. [Staff Architect Interview Questions](#staff-architect-interview-questions)
8. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Layered Architecture
```
┌─────────────────────────────────────────────────┐
│                   SQL Layer                       │
│  SQL Parser → Optimizer → DistSQL Execution      │
│  PostgreSQL wire protocol compatible             │
├─────────────────────────────────────────────────┤
│              Transaction Layer                    │
│  Serializable isolation (SSI)                    │
│  Multi-version concurrency control               │
│  Parallel commits (since 20.1)                   │
├─────────────────────────────────────────────────┤
│              Distribution Layer                   │
│  Range-based sharding (automatic)                │
│  Raft consensus per range                        │
│  Lease-based reads (leaseholder)                 │
├─────────────────────────────────────────────────┤
│              Replication Layer                    │
│  Synchronous replication via Raft                │
│  Automatic rebalancing                           │
├─────────────────────────────────────────────────┤
│              Storage Layer (Pebble)              │
│  LSM-based key-value store                       │
│  MVCC with timestamps                           │
└─────────────────────────────────────────────────┘
```

### Key-Value Model
```
All SQL data maps to ordered key-value pairs:

Table: users (id INT PRIMARY KEY, name STRING, email STRING)
Row: (id=1, name="Alice", email="alice@ex.com")

KV representation:
Key: /Table/users/1/name → Value: "Alice"
Key: /Table/users/1/email → Value: "alice@ex.com"

Index entry:
Key: /Table/users/idx_email/"alice@ex.com"/1 → Value: (empty)

All keys are globally ordered → enables range-based sharding
```

### Range-Based Distribution
```
All data split into ~512MB ranges:
Range 1: [/Min, /Table/users/1000)     → Node A (leaseholder)
Range 2: [/Table/users/1000, /Table/users/5000) → Node B (leaseholder)
Range 3: [/Table/users/5000, /Table/orders/100) → Node C (leaseholder)

Each range:
- Has 3+ replicas (RF=3 default)
- Uses Raft for consensus
- One replica is leaseholder (serves reads)
- One replica is Raft leader (coordinates writes)
- Usually leaseholder = Raft leader (co-located for efficiency)

Automatic operations:
- Split: When range exceeds 512MB → split into two ranges
- Merge: When adjacent ranges too small → merge
- Rebalance: Move replicas for even distribution
- Up-replicate: Add replicas when under-replicated
```

---

## Distributed SQL & Raft Consensus

### Raft Consensus (per Range)
```
Write path for INSERT INTO users VALUES (1, 'Alice'):
1. Client → Gateway node (any node)
2. Gateway determines range for key /Table/users/1
3. Request forwarded to leaseholder of that range
4. Leaseholder (= Raft leader) proposes write to Raft group
5. Raft: Leader sends AppendEntries to followers
6. Majority acknowledge → entry committed
7. Apply to local Pebble storage
8. Return success to client

Read path (leaseholder read):
1. Client → Gateway → Leaseholder
2. Leaseholder serves read locally (no consensus needed)
3. Lease prevents stale reads (lease has expiration)

Follower reads (AS OF SYSTEM TIME):
- Read from any replica (historical data)
- Lower latency in multi-region deployments
- Consistent to a point in time (not real-time)
```

### DistSQL (Distributed SQL Execution)
```
For queries spanning multiple ranges:
SELECT region, COUNT(*) FROM orders GROUP BY region;

Execution plan:
Gateway Node:
└── Final aggregation
    ├── Node A: Scan local ranges, partial GROUP BY
    ├── Node B: Scan local ranges, partial GROUP BY
    └── Node C: Scan local ranges, partial GROUP BY

- Pushes computation to data (like map-reduce)
- Minimizes data transfer between nodes
- Parallel execution across nodes
```

---

## Transaction Model (Serializable)

### Serializable Snapshot Isolation (SSI)
```
CockroachDB provides SERIALIZABLE by default (strongest guarantee):
- Prevents all anomalies (dirty reads, phantoms, write skew)
- Uses MVCC + timestamp ordering + read/write conflict detection

Transaction lifecycle:
1. BEGIN → Assign provisional commit timestamp
2. Read: Check for write intents from other txns
3. Write: Create "write intent" (provisional write)
4. COMMIT:
   a. Write transaction record
   b. Resolve write intents (make them permanent)
   c. Parallel commit optimization (since 20.1)

Write intents:
- Like locks but stored in data (MVCC layer)
- Other transactions encountering intent must:
  a. Check transaction record
  b. If committed → resolve intent, read value
  c. If aborted → ignore intent
  d. If pending → wait or push timestamp

Timestamp ordering:
- Each transaction has a read timestamp and write timestamp
- If conflict detected → transaction may be restarted with new timestamp
- Avoids blocking in most cases (optimistic approach)
```

### Parallel Commits
```
Traditional 2PC:
1. Staging writes (intents)
2. Commit transaction record (synchronous, remote)
3. Resolve intents (async cleanup)
Latency: 2 round-trips minimum

Parallel Commits (CockroachDB optimization):
1. Stage writes + commit record in PARALLEL
2. Transaction considered committed when all writes staged
3. Transaction record updated asynchronously
Latency: 1 round-trip for most transactions!

Impact: 50% latency reduction for cross-range transactions
```

---

## Multi-Region & Geo-Partitioning

### Locality-Aware Patterns
```sql
-- 1. REGIONAL BY ROW (each row pinned to a region)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name STRING,
    email STRING,
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region
) LOCALITY REGIONAL BY ROW;

-- Result: Each row's replicas placed in its region
-- Local reads/writes for region-local data
-- Cross-region access still works (higher latency)

-- 2. REGIONAL TABLE (entire table in one region)
ALTER TABLE config SET LOCALITY REGIONAL BY TABLE IN "us-east1";
-- All replicas in us-east1 (fast local access, slow remote)

-- 3. GLOBAL TABLE (replicas everywhere, reads from anywhere)
ALTER TABLE countries SET LOCALITY GLOBAL;
-- Read from any region (stale-read optimization)
-- Writes go to leaseholder (one region, then replicated)
-- Best for: Reference data that rarely changes

-- 4. Zone configs for custom placement
ALTER TABLE orders CONFIGURE ZONE USING
    num_replicas = 5,
    constraints = '{+region=us-east1: 2, +region=us-west1: 2, +region=eu-west1: 1}',
    lease_preferences = '[[+region=us-east1]]';
```

### Multi-Region Architecture
```
┌──────────────────────────────────────────────────────┐
│              CockroachDB Multi-Region                  │
│                                                        │
│   US-East1           US-West1          EU-West1       │
│  ┌────────┐         ┌────────┐        ┌────────┐    │
│  │ Node 1 │         │ Node 3 │        │ Node 5 │    │
│  │ Node 2 │         │ Node 4 │        │ Node 6 │    │
│  └────────┘         └────────┘        └────────┘    │
│                                                        │
│  REGIONAL BY ROW (latency-optimized):                │
│  US user → data replicated in US-East1               │
│  EU user → data replicated in EU-West1               │
│  Cross-region read: ~50-100ms extra latency          │
│  Local read: <5ms                                    │
│                                                        │
│  GLOBAL table: Reads from closest replica             │
│  Write latency: Cross-region consensus (~100-200ms)  │
└──────────────────────────────────────────────────────┘
```

---

## Storage Engine (Pebble)

### Pebble (Go-based LSM)
```
CockroachDB's custom storage engine (replaced RocksDB):
- Written in Go (same as CockroachDB)
- LSM-tree architecture (levels L0-L6)
- MVCC: Multiple versions per key (timestamp suffixed)
- Block-based compression (Snappy/ZSTD)
- Bloom filters for point lookups
- Range tombstones for efficient bulk deletes

Key format:
/Table/ID/IndexID/KeyColumns/ColumnFamily/Timestamp

MVCC versions:
Key: /Table/users/1/name @ t=100ns → "Alice"
Key: /Table/users/1/name @ t=200ns → "Alice Smith"  (update)
Key: /Table/users/1/name @ t=300ns → (deletion tombstone)

GC: Old versions cleaned when no active transaction needs them
```

---

## Staff Architect Interview Questions

**Q1: How does CockroachDB provide serializable isolation without significant performance penalty?**
**A:** CockroachDB uses optimistic concurrency with timestamp ordering:
- Transactions proceed without locks (write intents mark provisional writes)
- Conflicts detected at commit time (not during execution)
- Timestamp pushes resolve many conflicts without restart
- Read refreshes: If read timestamp can be advanced without conflict, transaction continues
- Result: Most transactions commit without retry (~1-5% retry rate under contention)
- Parallel commits reduce latency to 1 round-trip for most transactions

**Q2: Compare CockroachDB with Google Spanner.**
**A:**
| Aspect | CockroachDB | Google Spanner |
|--------|-------------|---------------|
| Clock | Hybrid Logical Clock (HLC) | TrueTime (atomic clocks + GPS) |
| Read latency | Leaseholder read (local) | Strong reads wait for TrueTime uncertainty |
| Open source | Yes (BSL license) | No (GCP managed only) |
| Deployment | Self-hosted or CockroachDB Cloud | GCP only |
| Consistency | Serializable (SSI) | External consistency (linearizable) |
| SQL compatibility | PostgreSQL wire protocol | Google SQL dialect |

Key difference: TrueTime gives Spanner true real-time ordering. CockroachDB uses HLC which provides causal ordering (slightly weaker but practical for most use cases).

**Q3: When would you NOT use CockroachDB?**
**A:**
- Pure analytics/OLAP (ClickHouse, BigQuery better)
- Single-region, single-node needs (PostgreSQL simpler, faster)
- Key-value with sub-ms latency (Redis, Aerospike better)
- Very high write throughput on single key (hot key problem with Raft)
- Time-series at massive scale (TimescaleDB, InfluxDB better)
- Budget constraints (3-node minimum, operational complexity)

---

## Scenario-Based Questions

### Scenario 1: Global Payment System

**Requirements:** ACID transactions globally, <200ms P99, multi-region compliance.

```sql
-- Database setup
CREATE DATABASE payments PRIMARY REGION "us-east1"
    REGIONS "us-west1", "eu-west1", "ap-southeast1";

-- Transactions table (pinned to origin region)
CREATE TABLE transactions (
    id UUID DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    amount DECIMAL(19,4) NOT NULL,
    currency STRING(3) NOT NULL,
    status STRING NOT NULL DEFAULT 'pending',
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (region, id)
) LOCALITY REGIONAL BY ROW;

-- Account balances (REGIONAL BY ROW for locality)
CREATE TABLE accounts (
    id UUID DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    balance DECIMAL(19,4) NOT NULL DEFAULT 0,
    region crdb_internal_region NOT NULL,
    PRIMARY KEY (region, id)
) LOCALITY REGIONAL BY ROW;

-- Transfer (serializable, same-region = fast)
BEGIN;
UPDATE accounts SET balance = balance - 100.00 WHERE user_id = :from AND region = 'us-east1';
UPDATE accounts SET balance = balance + 100.00 WHERE user_id = :to AND region = 'us-east1';
INSERT INTO transactions (user_id, amount, currency) VALUES (:from, -100.00, 'USD');
INSERT INTO transactions (user_id, amount, currency) VALUES (:to, 100.00, 'USD');
COMMIT;

-- Cross-region transfer (higher latency, still serializable):
-- ~200-300ms due to cross-region Raft consensus
-- Consider: Saga pattern or async reconciliation for cross-region
```

### Scenario 2: Migrating from PostgreSQL to CockroachDB

**Approach:**
```
1. Compatibility assessment:
   - CockroachDB supports PostgreSQL wire protocol
   - Most SQL features compatible (sequences, CTEs, window functions)
   - NOT supported: Some PL/pgSQL, extensions (PostGIS partial), advisory locks
   - Behavioral differences: Serializable default, implicit transactions

2. Schema migration:
   - Export PG schema → Adjust for CockroachDB
   - Add REGIONAL BY ROW for multi-region tables
   - Consider column families for wide tables
   - Replace SERIAL with UUID or UNIQUE ROWID()

3. Data migration:
   - IMPORT INTO (CSV/Parquet from cloud storage) - fastest
   - pg_dump → cockroach sql (for small datasets)
   - CDC pipeline: PG → Kafka → CockroachDB (for live migration)

4. Application changes:
   - Add retry logic for serializable retry errors (40001)
   - Remove explicit locking (FOR UPDATE still works but less needed)
   - Adjust connection pooling (CockroachDB handles more connections)
   - Test under load (different performance characteristics)

5. Cutover:
   - Dual-write period
   - Validate data consistency
   - Switch reads
   - Switch writes
   - Monitor for transaction retries and latency
```

