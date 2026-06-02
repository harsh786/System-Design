# Vitess - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Sharding Architecture](#sharding-architecture)
4. [Query Routing & Planning](#query-routing--planning)
5. [VSchema & Vindexes](#vschema--vindexes)
6. [Resharding (MoveTables & Reshard)](#resharding)
7. [VReplication](#vreplication)
8. [High Availability & Failover](#high-availability--failover)
9. [Online Schema Changes](#online-schema-changes)
10. [Performance & Query Optimization](#performance--query-optimization)
11. [Production Deployment Patterns](#production-deployment-patterns)
12. [Security & Multi-tenancy](#security--multi-tenancy)
13. [Use Case Architectures](#use-case-architectures)
14. [Staff Architect Interview Questions](#staff-architect-interview-questions)
15. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is Vitess?
```
Vitess is a database clustering system for horizontal scaling of MySQL.
Originally developed at YouTube (Google), it powers some of the world's
largest MySQL deployments. It is a CNCF graduated project.

Key characteristics:
- Horizontal sharding of MySQL (transparent to application)
- MySQL protocol compatible (drop-in replacement)
- Connection pooling (protects MySQL from overload)
- Query routing and rewriting
- Online resharding without downtime
- Automated failover
- Online schema migrations
- Designed for Kubernetes-native deployment

NOT designed for:
- Non-MySQL databases
- Complex cross-shard transactions (limited support)
- Full ANSI SQL compatibility (some queries unsupported)
- Workloads that don't need sharding (< 1TB)
- Real-time analytics (use ClickHouse/Druid)

Comparison:
┌────────────────────┬────────────┬──────────────┬──────────────┬────────────┐
│                    │ Vitess     │ CockroachDB  │ TiDB         │ PlanetScale│
├────────────────────┼────────────┼──────────────┼──────────────┼────────────┤
│ Underlying DB      │ MySQL      │ Custom       │ TiKV         │ Vitess     │
│ Protocol           │ MySQL      │ PostgreSQL   │ MySQL        │ MySQL      │
│ Sharding           │ Application│ Automatic    │ Automatic    │ Automatic  │
│                    │ -defined   │ (range)      │ (range/hash) │ -defined   │
│ Transactions       │ Single-shard│ Distributed │ Distributed  │ Single-shard│
│ Consistency        │ Per-shard  │ Serializable │ Snapshot Iso │ Per-shard  │
│ Schema changes     │ Online DDL │ Online       │ Online       │ Branching  │
│ Connection pool    │ Built-in   │ N/A          │ N/A          │ Built-in   │
│ Failover           │ Automated  │ Automatic    │ Automatic    │ Automated  │
│ Maturity           │ 10+ years  │ 6+ years     │ 6+ years     │ 3+ years   │
│ Used by            │ YouTube,   │ Many         │ PingCAP      │ Many       │
│                    │ Slack,     │ startups     │ clients      │ startups   │
│                    │ GitHub     │              │              │            │
│ Operational        │ Complex    │ Moderate     │ Moderate     │ Managed    │
└────────────────────┴────────────┴──────────────┴──────────────┴────────────┘
```

### Full Vitess Cluster Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       VITESS CLUSTER ARCHITECTURE                             │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       APPLICATION LAYER                               │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │   │
│  │  │ App Pod 1│  │ App Pod 2│  │ App Pod 3│  │ MySQL CLI/Tools  │    │   │
│  │  │(MySQL drv)│  │(MySQL drv)│  │(MySQL drv)│  │ (any MySQL tool) │    │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘    │   │
│  │       └──────────────┴─────────────┴──────────────────┘              │   │
│  │                         │ MySQL Protocol                              │   │
│  └─────────────────────────┼────────────────────────────────────────────┘   │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       VTGATE (Query Router / Proxy)                    │   │
│  │                                                                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │  VTGate 1    │  │  VTGate 2    │  │  VTGate 3    │               │   │
│  │  │              │  │              │  │              │               │   │
│  │  │ - MySQL proto│  │ - MySQL proto│  │ - MySQL proto│               │   │
│  │  │ - Parse SQL  │  │ - Parse SQL  │  │ - Parse SQL  │               │   │
│  │  │ - Plan route │  │ - Plan route │  │ - Plan route │               │   │
│  │  │ - VSchema    │  │ - VSchema    │  │ - VSchema    │               │   │
│  │  │ - Conn pool  │  │ - Conn pool  │  │ - Conn pool  │               │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │   │
│  │         │                  │                  │                        │   │
│  └─────────┼──────────────────┼──────────────────┼────────────────────────┘   │
│            │                  │                  │                            │
│            ▼                  ▼                  ▼                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       VTTABLET (Tablet Managers)                       │   │
│  │                                                                       │   │
│  │  Keyspace: "commerce"                                                │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │  Shard: "-80" (first half of keyspace)                          │  │   │
│  │  │                                                                  │  │   │
│  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │  │   │
│  │  │  │ VTTablet (PRIMARY)│  │VTTablet (REPLICA)│  │VTTablet(RDONLY)│ │  │   │
│  │  │  │                   │  │                  │  │              │ │  │   │
│  │  │  │  ┌─────────────┐ │  │ ┌──────────────┐│  │┌────────────┐│ │  │   │
│  │  │  │  │ MySQL 8.0   │ │  │ │ MySQL 8.0    ││  ││ MySQL 8.0  ││ │  │   │
│  │  │  │  │ (read/write)│ │  │ │ (read-only   ││  ││ (analytics ││ │  │   │
│  │  │  │  │             │ │  │ │  replica)    ││  ││  batch)    ││ │  │   │
│  │  │  │  └─────────────┘ │  │ └──────────────┘│  │└────────────┘│ │  │   │
│  │  │  └──────────────────┘  └──────────────────┘  └──────────────┘ │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │  Shard: "80-" (second half of keyspace)                         │  │   │
│  │  │  (same structure: PRIMARY + REPLICA + RDONLY)                   │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       CONTROL PLANE                                    │   │
│  │                                                                       │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │  VTCtld           │  │  VTOrc            │  │  Topology Service│   │   │
│  │  │  (admin server)   │  │  (orchestrator)   │  │  (etcd)          │   │   │
│  │  │                   │  │                   │  │                  │   │   │
│  │  │ - vtctldclient    │  │ - Auto failover   │  │ - Keyspace info  │   │   │
│  │  │ - Workflow mgmt   │  │ - Health checks   │  │ - Shard info     │   │   │
│  │  │ - Schema mgmt     │  │ - Reparenting     │  │ - Tablet info    │   │   │
│  │  │ - Backup/Restore  │  │ - Topology repair │  │ - Routing rules  │   │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sharding Architecture

### Vindexes (Virtual Indexes for Sharding)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VITESS SHARDING WITH VINDEXES                              │
│                                                                              │
│  Keyspace: "commerce" (2 shards: "-80", "80-")                             │
│                                                                              │
│  Table: orders                                                               │
│  Primary Vindex: hash(customer_id) → determines shard                       │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  INSERT INTO orders (id, customer_id, amount) VALUES (1, 100, 50.00) │  │
│  │                                                                        │  │
│  │  Step 1: VTGate looks up VSchema for "orders" table                   │  │
│  │  Step 2: Primary vindex = hash(customer_id)                           │  │
│  │  Step 3: hash(100) = 0x4F... → falls in shard "-80"                  │  │
│  │  Step 4: Route INSERT to shard "-80" PRIMARY tablet                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Vindex types:                                                               │
│  ┌───────────────────┬────────────────────────────────────────────────────┐ │
│  │ Type              │ Description                                         │ │
│  ├───────────────────┼────────────────────────────────────────────────────┤ │
│  │ hash              │ MD5 hash → distribute evenly across shards         │ │
│  │ xxhash            │ xxHash (faster than MD5)                           │ │
│  │ consistent_lookup │ Lookup table mapping value → keyspace_id           │ │
│  │ unicode_loose_md5 │ Case-insensitive hash                             │ │
│  │ numeric           │ Use numeric value directly as keyspace_id         │ │
│  │ binary_md5        │ MD5 of binary value                               │ │
│  │ reverse_bits      │ Reverse bits of integer (spread sequential)       │ │
│  │ region_experimental│ Geographic region-based routing                   │ │
│  └───────────────────┴────────────────────────────────────────────────────┘ │
│                                                                              │
│  Vindex categories:                                                          │
│  - PRIMARY (unique): One per table, determines shard ownership              │
│  - SECONDARY: Additional routing hints (lookup tables)                      │
│  - FUNCTIONAL: Computes keyspace_id from column value directly              │
│  - LOOKUP: Maintains a separate table for the mapping                       │
│                                                                              │
│  Example with lookup vindex (query by email):                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SELECT * FROM users WHERE email = 'alice@example.com'               │   │
│  │                                                                       │   │
│  │  Without lookup: Scatter query to ALL shards (expensive)             │   │
│  │  With lookup vindex on email:                                        │   │
│  │    1. Query lookup table: email → user_id → keyspace_id             │   │
│  │    2. Route to specific shard only (efficient)                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Query Routing & Planning

### VTGate Query Planning
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    QUERY ROUTING DECISIONS                                    │
│                                                                              │
│  Query types and routing:                                                    │
│                                                                              │
│  1. SINGLE-SHARD (optimal):                                                 │
│     SELECT * FROM orders WHERE customer_id = 100                            │
│     → hash(100) → shard "-80" → send to one tablet                         │
│                                                                              │
│  2. SCATTER (expensive):                                                     │
│     SELECT * FROM orders WHERE amount > 100                                 │
│     → No vindex column in WHERE → must query ALL shards                    │
│     → Merge results at VTGate                                               │
│                                                                              │
│  3. SCATTER-AGGREGATE:                                                       │
│     SELECT COUNT(*) FROM orders WHERE status = 'shipped'                    │
│     → Scatter to all shards → SUM the partial counts at VTGate            │
│                                                                              │
│  4. CROSS-SHARD JOIN (limited):                                             │
│     SELECT o.*, c.name FROM orders o JOIN customers c ON o.cust_id=c.id    │
│     → If same vindex column: co-located join (single shard)                │
│     → If different: scatter one side, lookup the other                      │
│                                                                              │
│  5. VINDEXED LOOKUP:                                                         │
│     SELECT * FROM users WHERE email = 'alice@example.com'                   │
│     → Lookup vindex: email → keyspace_id → specific shard                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  QUERY PLANNING FLOW                                                  │   │
│  │                                                                       │   │
│  │  SQL Input                                                            │   │
│  │    │                                                                  │   │
│  │    ▼                                                                  │   │
│  │  [Parse] → AST                                                       │   │
│  │    │                                                                  │   │
│  │    ▼                                                                  │   │
│  │  [Analyze] → resolve tables, check VSchema                           │   │
│  │    │                                                                  │   │
│  │    ▼                                                                  │   │
│  │  [Plan] → determine routing (single/scatter/join strategy)           │   │
│  │    │                                                                  │   │
│  │    ├── Single shard plan → send to 1 tablet                          │   │
│  │    ├── Scatter plan → fan-out to all shards, merge                   │   │
│  │    ├── Join plan → nested loop or hash join across shards            │   │
│  │    └── Subquery plan → execute subquery first, use result            │   │
│  │                                                                       │   │
│  │  [Execute] → send to VTTablets → collect results                     │   │
│  │    │                                                                  │   │
│  │    ▼                                                                  │   │
│  │  [Return] → merged result to client                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Resharding

### Online Resharding Workflow
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RESHARDING WORKFLOW (2 shards → 4 shards)                  │
│                                                                              │
│  Before: Keyspace "commerce" has 2 shards: ["-80", "80-"]                  │
│  After:  Keyspace "commerce" has 4 shards: ["-40","40-80","80-c0","c0-"]   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Phase 1: CREATE TARGET SHARDS                                        │   │
│  │                                                                       │   │
│  │ - Provision new MySQL instances for target shards                    │   │
│  │ - VTTablets start for -40, 40-80, 80-c0, c0-                       │   │
│  │ - Apply schema to new shards                                         │   │
│  │ - Source shards still serving ALL traffic                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Phase 2: VREPLICATION (copy + stream)                                │   │
│  │                                                                       │   │
│  │  Source: "-80" ──VStream──▶ Target: "-40" (rows with keyspace_id<40)│   │
│  │  Source: "-80" ──VStream──▶ Target: "40-80" (rows with 40≤kid<80)   │   │
│  │  Source: "80-" ──VStream──▶ Target: "80-c0" (rows with 80≤kid<c0)  │   │
│  │  Source: "80-" ──VStream──▶ Target: "c0-" (rows with kid≥c0)       │   │
│  │                                                                       │   │
│  │  Steps:                                                               │   │
│  │  1. Full copy of existing data (bulk phase)                          │   │
│  │  2. Streaming replication of ongoing changes (catch-up phase)        │   │
│  │  3. Target shards are replica-level consistent with source          │   │
│  │                                                                       │   │
│  │  During this phase: Source shards still serving ALL traffic          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Phase 3: CUT-OVER (switch traffic)                                   │   │
│  │                                                                       │   │
│  │  vtctldclient SwitchTraffic --tablet_types=rdonly                    │   │
│  │  vtctldclient SwitchTraffic --tablet_types=replica                   │   │
│  │  vtctldclient SwitchTraffic --tablet_types=primary                   │   │
│  │                                                                       │   │
│  │  Primary cut-over (brief write pause):                               │   │
│  │  1. Stop writes on source shards                                     │   │
│  │  2. Wait for VReplication to catch up (milliseconds)                 │   │
│  │  3. Update routing rules (serve from target shards)                  │   │
│  │  4. Resume writes on target shards                                   │   │
│  │                                                                       │   │
│  │  Downtime: < 1 second (only during primary cut-over)                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Phase 4: CLEANUP                                                      │   │
│  │                                                                       │   │
│  │  vtctldclient Complete                                                │   │
│  │  - Drop VReplication streams                                          │   │
│  │  - Remove old shards from topology                                   │   │
│  │  - Decommission old tablets                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ROLLBACK possible until Complete step:                                     │
│  vtctldclient ReverseTraffic → sends traffic back to source shards         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## High Availability & Failover

### VTOrc Automated Failover
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VTORS FAILOVER ARCHITECTURE                                │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  VTOrc (Vitess Orchestrator)                                          │   │
│  │                                                                       │   │
│  │  - Monitors MySQL replication topology per shard                     │   │
│  │  - Detects primary failure (health check failures)                   │   │
│  │  - Performs automated reparenting (failover)                         │   │
│  │  - Updates topology service with new primary                        │   │
│  │  - Coordinates with VTGate for traffic routing                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Normal operation:                                                           │
│  ┌────────────────────────────────────────────────────┐                     │
│  │  Shard "-80":                                       │                     │
│  │  PRIMARY (zone-a) ──repl──▶ REPLICA (zone-b)      │                     │
│  │                    ──repl──▶ REPLICA (zone-c)      │                     │
│  │                    ──repl──▶ RDONLY (zone-a)       │                     │
│  └────────────────────────────────────────────────────┘                     │
│                                                                              │
│  Failover scenario (PRIMARY crashes):                                       │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ 1. VTOrc detects PRIMARY unresponsive (3 failed health checks)      │    │
│  │ 2. VTOrc selects best REPLICA for promotion:                        │    │
│  │    - Most caught up (lowest replication lag)                         │    │
│  │    - Same datacenter preferred                                       │    │
│  │    - Designated candidate (if configured)                           │    │
│  │ 3. EmergencyReparentShard:                                          │    │
│  │    a. Stop replication on all replicas                              │    │
│  │    b. Wait for selected replica to apply pending transactions       │    │
│  │    c. Promote replica to new PRIMARY                                │    │
│  │    d. Point other replicas to new PRIMARY                           │    │
│  │    e. Update topology service                                       │    │
│  │ 4. VTGate detects topology change → routes writes to new PRIMARY   │    │
│  │                                                                      │    │
│  │ Failover time: 5-30 seconds (depending on replication lag)          │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Semi-synchronous replication:                                               │
│  - PRIMARY waits for at least 1 REPLICA to ACK before committing           │
│  - Prevents data loss during failover                                       │
│  - Config: rpl_semi_sync_source_wait_for_replica_count = 1                 │
│  - Trade-off: Slightly higher write latency (network round-trip)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Online Schema Changes

### OnlineDDL Strategies
```
DDL strategies available:

1. vitess (built-in, recommended):
   - Uses VReplication internally
   - Creates shadow table with new schema
   - Streams data from original to shadow
   - Atomic cut-over
   - Supports: ADD/DROP COLUMN, ADD INDEX, MODIFY COLUMN

2. gh-ost (GitHub Online Schema Change):
   - External tool integrated into Vitess
   - Binary log streaming approach
   - Minimal locking
   - Pausable and throttle-aware

3. pt-osc (Percona pt-online-schema-change):
   - Trigger-based approach
   - Well-tested, mature
   - Higher load during migration

Usage:
  SET @@ddl_strategy='vitess';
  ALTER TABLE orders ADD COLUMN priority INT DEFAULT 0;
  
  -- Check progress
  SHOW VITESS_MIGRATIONS LIKE 'uuid';
  
  -- Declarative DDL (desired state, Vitess figures out migration)
  SET @@ddl_strategy='vitess --declarative';
  CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    customer_id BIGINT,
    amount DECIMAL(10,2),
    priority INT DEFAULT 0,   ← new column
    INDEX idx_cust (customer_id)
  );

Benefits over traditional DDL:
- No table lock during ALTER
- Can be paused/resumed/cancelled
- Supports large tables (TBs)
- Revertible (within retention window)
- Throttle-aware (backs off under load)
```

---

## Performance & Query Optimization

### Connection Pooling
```
Vitess provides connection pooling at VTTablet level:

Problem without Vitess:
  10,000 app connections × 4 shards = 40,000 MySQL connections
  MySQL cannot handle 40K connections efficiently

With Vitess:
  10,000 app connections → VTGate → VTTablet pool → 300 MySQL connections
  
  VTTablet pools:
  - Transaction pool: for open transactions (limited size)
  - OLTP pool: for single queries outside transactions
  - OLAP pool: for long-running queries (separate limits)

┌─────────────────────────────────────────────────────────────────┐
│                CONNECTION POOLING                                 │
│                                                                   │
│  Apps (10,000 connections)                                       │
│       │                                                          │
│       ▼                                                          │
│  VTGate (stateless, scales horizontally)                        │
│       │                                                          │
│       ▼                                                          │
│  VTTablet connection pools:                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Transaction Pool:  50 connections (for active txns)      │    │
│  │ Query Pool:       300 connections (for single queries)   │    │
│  │ OLAP Pool:         10 connections (for long queries)     │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  MySQL (handles only 360 connections instead of 10,000)          │
└─────────────────────────────────────────────────────────────────┘

Query consolidation:
  If 100 identical SELECTs arrive simultaneously:
  - VTTablet sends 1 query to MySQL
  - Returns same result to all 100 waiters
  - Massive reduction in MySQL load for hot queries
```

---

## Production Deployment Patterns

### Kubernetes Deployment
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              PRODUCTION KUBERNETES DEPLOYMENT                                 │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Namespace: vitess                                                     │   │
│  │                                                                       │   │
│  │ ┌─────────────────────────────────────────────────────────────────┐  │   │
│  │ │ Deployment: vtgate (3+ replicas, stateless)                      │  │   │
│  │ │ Resources: 4 CPU, 8GB RAM per pod                                │  │   │
│  │ │ Service: LoadBalancer (MySQL port 3306)                          │  │   │
│  │ │ HPA: Scale on CPU utilization                                    │  │   │
│  │ └─────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │ ┌─────────────────────────────────────────────────────────────────┐  │   │
│  │ │ StatefulSet: vttablet-commerce-x-80-primary (1 replica)         │  │   │
│  │ │ Resources: 8 CPU, 32GB RAM, 500GB SSD PVC                       │  │   │
│  │ │ Containers: [vttablet, mysqld] (sidecar pattern)                │  │   │
│  │ └─────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │ ┌─────────────────────────────────────────────────────────────────┐  │   │
│  │ │ StatefulSet: vttablet-commerce-x-80-replica (2 replicas)        │  │   │
│  │ │ Resources: 8 CPU, 32GB RAM, 500GB SSD PVC                       │  │   │
│  │ └─────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │ ┌─────────────────────────────────────────────────────────────────┐  │   │
│  │ │ Deployment: vtctld (1 replica)                                   │  │   │
│  │ │ Deployment: vtorc (1 replica, runs per cell/shard)              │  │   │
│  │ │ StatefulSet: etcd (3 replicas for topology)                     │  │   │
│  │ └─────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │ Vitess Operator manages all of the above via CRDs:                   │   │
│  │ - VitessCluster                                                       │   │
│  │ - VitessKeyspace                                                      │   │
│  │ - VitessShard                                                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Sizing per shard:                                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Data Size  │ Tablets/shard │ MySQL RAM │ Disk │ Max QPS/shard        │  │
│  ├────────────┼───────────────┼───────────┼──────┼──────────────────────┤  │
│  │ < 100 GB   │ 3 (1P+2R)    │ 16 GB     │ 200GB│ 10K reads, 5K writes│  │
│  │ 100-500 GB │ 3 (1P+2R)    │ 32 GB     │ 1 TB │ 20K reads, 10K write│  │
│  │ 500GB-1TB  │ 5 (1P+3R+1RO)│ 64 GB     │ 2 TB │ 50K reads, 20K write│  │
│  └────────────┴───────────────┴───────────┴──────┴──────────────────────┘  │
│                                                                              │
│  Recommended: Keep each shard < 250GB for operational agility               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: How does Vitess handle cross-shard queries?
```
Answer:
Cross-shard query handling depends on query type:

1. Scatter queries (no vindex in WHERE):
   - VTGate sends query to ALL shards
   - Collects results, merges at VTGate
   - Supports: ORDER BY, LIMIT, aggregations
   - Limitation: Memory-bound at VTGate for large results

2. Cross-shard JOINs:
   - Co-located join: If both tables use same vindex column → single shard
   - Lookup join: Query one side, use result to route other side
   - Scatter join: Last resort (expensive, memory-intensive)

3. Cross-shard transactions:
   - 2PC (two-phase commit) available but not default
   - Default: single-shard transactions only
   - Multi-shard writes: best-effort (application must handle partial)
   - Recommendation: Design schema to keep transactions single-shard

4. Aggregations:
   - SUM, COUNT: scatter to all shards, sum partial results
   - AVG: scatter (get sum + count), compute at VTGate
   - DISTINCT: scatter, deduplicate at VTGate
   - GROUP BY: partial GROUP BY per shard, merge at VTGate
```

### Q2: Compare Vitess resharding vs CockroachDB automatic range splitting
```
Answer:
┌──────────────────────┬────────────────────────────┬──────────────────────────┐
│ Aspect               │ Vitess                     │ CockroachDB              │
├──────────────────────┼────────────────────────────┼──────────────────────────┤
│ Trigger              │ Operator-initiated         │ Automatic (size-based)   │
│ Granularity          │ Keyspace ranges            │ Individual ranges (64MB) │
│ Data movement        │ VReplication (streaming)   │ Raft learner + snapshot  │
│ Downtime             │ <1s (primary cut-over)     │ Zero (range lease transfer)│
│ Rollback             │ Yes (ReverseTraffic)       │ Automatic (merge ranges) │
│ Complexity           │ Multi-step workflow        │ Transparent              │
│ Customization        │ Full control over sharding │ Limited (just range keys)│
│ Operational          │ More complex, more control │ Simpler, less control    │
└──────────────────────┴────────────────────────────┴──────────────────────────┘

Vitess advantage: Full control over data distribution strategy
CockroachDB advantage: Zero operational overhead for resharding
```

### Q3: How does VTGate connection pooling protect MySQL?
```
Answer:
Without Vitess: N app instances × M connections = N×M MySQL connections
With Vitess: N app instances → VTGate → VTTablet pool → P MySQL connections

Key mechanisms:
1. Connection multiplexing: Many app connections share few MySQL connections
2. Transaction pool: Limited size prevents runaway transactions
3. Query timeout: Kills long-running queries automatically
4. Query consolidation: Identical concurrent queries merged into one
5. Buffer management: During failover, buffers writes briefly

Production impact:
- Without: 5000 app pods × 10 connections = 50,000 MySQL connections (impossible)
- With: 5000 app pods → VTGate → 300 MySQL connections per shard (manageable)

MySQL typically maxes out at 2000-5000 connections before degrading.
Vitess makes this a non-issue even with 100K+ app connections.
```

### Q4-Q10: Additional Questions
```
Q4: When would you NOT choose Vitess?
- Dataset < 500GB (overkill, just use MySQL)
- Need distributed transactions (use CockroachDB/TiDB)
- PostgreSQL stack (Vitess is MySQL-only)
- Simple read scaling only (use MySQL read replicas)
- Full SQL compatibility required (some queries unsupported)
- Small team without K8s expertise (operational complexity)

Q5: How does VReplication work internally?
- Uses MySQL binlog (change data capture)
- VStream API: gRPC streaming of row changes
- Filter: Only relevant rows for target shard
- Transform: Applies vindex to determine target
- Apply: Writes to target MySQL instance
- Checkpoint: Tracks GTID position for resumability
- Used by: Reshard, MoveTables, Materialize, OnlineDDL

Q6: Explain the VSchema and its role
- VSchema = sharding schema definition (JSON/YAML)
- Defines: tables, vindexes, routing rules
- Tells VTGate how to route queries
- Types: sharded keyspace (with vindexes) or unsharded
- Sequence tables: auto-increment across shards
- Reference tables: small tables copied to all shards

Q7: How to handle auto-increment IDs in sharded Vitess?
- MySQL AUTO_INCREMENT doesn't work across shards
- Solution: Vitess Sequences
  - Dedicated unsharded table for sequence generation
  - Each shard pre-fetches a batch of IDs (e.g., 1000 at a time)
  - Gaps possible but unique guaranteed
  - Performance: Batch fetching minimizes round-trips

Q8: What is the recommended shard count strategy?
- Start with power-of-2 shards (2, 4, 8, 16...)
- Each shard should be 50-250GB (sweet spot)
- Allows binary resharding (split each shard in half)
- Over-sharding creates operational overhead
- Under-sharding means more complex resharding later
- Rule of thumb: total_data_size / 200GB = number_of_shards

Q9: How does Vitess handle schema drift between shards?
- OnlineDDL applies schema changes consistently
- vtctldclient ApplySchema --sql="ALTER TABLE..."
- Applied to all shards of a keyspace simultaneously
- Progress tracked per shard
- If one shard fails: DDL paused, can retry
- SchemaChange controller ensures all shards converge

Q10: Describe Vitess backup/restore strategy
- VTBackup: Dedicated backup process
- Types: full backup (xtrabackup or mysqldump) + incremental (binlog)
- Storage: S3, GCS, Azure Blob, Ceph
- Restore: Create new tablet from backup, catch up via replication
- Point-in-time recovery: Restore backup + replay binlogs to timestamp
- Automated: Periodic backups scheduled via CronJob in K8s
```

---

## Scenario-Based Questions

### Scenario 1: Migrating monolithic MySQL to Vitess
```
Migration strategy (zero-downtime):

Phase 1 - Unsharded Vitess (2 weeks):
  - Deploy Vitess in front of existing MySQL
  - Single unsharded keyspace pointing to existing DB
  - VTGate proxies all traffic (no sharding yet)
  - Validate: All queries work through Vitess
  - Benefit: Connection pooling, monitoring immediately

Phase 2 - MoveTables to Vitess-managed MySQL (1 week):
  - Provision new MySQL instances managed by VTTablet
  - Use MoveTables to copy data with VReplication
  - Switch traffic to Vitess-managed tablets
  - Now Vitess fully controls the MySQL instances

Phase 3 - Introduce sharding (2-4 weeks):
  - Design VSchema (identify sharding key)
  - Create sharded keyspace
  - Use Reshard workflow to split into 2+ shards
  - Validate query routing
  - Iterate: 2 → 4 → 8 shards as needed

Key risks:
- Unsupported queries (test with vtexplain tool)
- Cross-shard transactions (redesign application)
- Sequence migration (replace AUTO_INCREMENT)
- Application-level retry logic for transient errors
```

### Scenario 2: One shard is much larger than others (data skew)
```
Causes:
- Vindex distributes unevenly (bad hash for data pattern)
- One customer dominates (multi-tenant with large tenant)
- Time-based skew (recent data concentrated)

Solutions:
1. Reshard the hot shard only:
   - Split "-80" into "-40" and "40-80"
   - Other shards unchanged
   - Targeted, minimal disruption

2. Custom vindex:
   - Move large tenant to dedicated shard
   - region_experimental or custom functional vindex
   - Route specific values to specific shards

3. Shard isolation for large tenants:
   - MoveTables: Move large tenant's data to separate keyspace
   - Per-tenant routing rules
   - Independent scaling

Monitoring:
- Track per-shard: disk usage, QPS, replication lag
- Alert on >2x average shard size
- Use vtctldclient GetTablets to audit distribution
```

### Scenario 3: VTGate query latency p99 degraded
```
Diagnosis:
1. Check VTGate metrics: scatter query ratio
   - High scatter ratio = queries not using vindexes efficiently
   - Fix: Add lookup vindexes or redesign queries

2. Check VTTablet pool utilization:
   - Transaction pool full = holding transactions too long
   - Fix: Reduce transaction duration in application

3. Check MySQL slow query log (per shard):
   - Missing indexes on shard-local queries
   - Fix: Add indexes via OnlineDDL

4. Check VReplication lag (if resharding):
   - Background data movement stealing I/O
   - Fix: Throttle VReplication

5. Check network between VTGate and VTTablet:
   - Cross-zone latency
   - Fix: Deploy VTGate in same zone as tablets

Optimization:
- Add covering indexes for common scatter queries
- Use lookup vindexes to convert scatter → single-shard
- Cache hot data at application level
- Use RDONLY tablets for analytics queries (don't pollute PRIMARY)
```

### Scenario 4: Failover taking too long (30+ seconds)
```
Root cause analysis:
1. Semi-sync replication lag:
   - Replica fell behind → needs to apply transactions before promotion
   - Fix: Ensure at least one replica is always caught up

2. VTOrc detection delay:
   - Health check interval too long
   - Fix: Reduce health_check_interval (default: 5s)

3. Topology update propagation:
   - etcd watch delay to VTGate
   - Fix: Ensure etcd is healthy, VTGate watch connected

4. VTGate buffer timeout:
   - Buffer fills up during failover
   - Fix: Increase buffer size and timeout for critical shards

Target architecture for fast failover:
- Semi-sync: Ensure at least 1 replica is in sync
- VTOrc health check: 2 second interval
- VTGate buffer: 30 seconds (covers failover window)
- Result: Failover in 5-10 seconds with zero client errors
```

### Scenario 5: Supporting 1 million QPS across sharded Vitess
```
Architecture:
- Keyspace shards: 32 (each handles ~30K QPS)
- Tablets per shard: 1 PRIMARY + 4 REPLICA + 1 RDONLY
- VTGate instances: 20 (stateless, HPA-scaled)
- Total MySQL instances: 32 × 6 = 192

Hardware per shard PRIMARY:
- 16 CPU, 64GB RAM, 1TB NVMe SSD
- InnoDB buffer pool: 48GB

Traffic routing:
- Reads: Distributed across REPLICA tablets (80% of traffic)
- Writes: PRIMARY only (20% of traffic)
- Analytics: RDONLY tablets (batch/reporting queries)

VTGate configuration:
- 20 pods, 8 CPU each
- Connection limit per VTGate: 10,000
- Total capacity: 200,000 concurrent connections

Key optimizations:
- Query consolidation: Reduces MySQL QPS by 3-5x for hot queries
- Prepared statements: Reduces parse overhead
- Read-after-write consistency: Use PRIMARY for read-your-writes
- Buffer pool warming: Pre-warm after failover
```
