# Vitess - Real World Use Cases & Production Guide

## Table of Contents
- [Core Concepts](#core-concepts)
- [Real-World Use Cases](#real-world-use-cases)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)

---

## Core Concepts

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                             │
│                    (MySQL Protocol Compatible)                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          VTGate (Proxy)                              │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────────┐  │
│  │ Query    │  │ Query        │  │ Vindex    │  │ Connection   │  │
│  │ Parser   │  │ Planner (V3) │  │ Router    │  │ Pooling      │  │
│  └──────────┘  └──────────────┘  └───────────┘  └──────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│   VTTablet (Primary)│ │   VTTablet (Primary)│ │   VTTablet (Primary)│
│   Shard -80       │ │   Shard 80-c0     │ │   Shard c0-       │
│  ┌─────────────┐  │ │  ┌─────────────┐  │ │  ┌─────────────┐  │
│  │  MySQL      │  │ │  │  MySQL      │  │ │  │  MySQL      │  │
│  │  Instance   │  │ │  │  Instance   │  │ │  │  Instance   │  │
│  └─────────────┘  │ │  └─────────────┘  │ │  └─────────────┘  │
│  ┌─────────────┐  │ │  ┌─────────────┐  │ │  ┌─────────────┐  │
│  │  Replica(s) │  │ │  │  Replica(s) │  │ │  │  Replica(s) │  │
│  └─────────────┘  │ │  └─────────────┘  │ │  └─────────────┘  │
└───────────────────┘ └───────────────────┘ └───────────────────┘
              │                 │                  │
              └─────────────────┼─────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Topology Service (etcd/ZK/Consul)                 │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────────┐  │
│  │ Shard Map    │  │ Tablet Health │  │ VSchema (Vindex config) │  │
│  └──────────────┘  └───────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Keyspace and Shard Architecture

A **Keyspace** is the logical database — equivalent to a MySQL schema but distributed across shards.

```
Keyspace: "commerce"
├── Shard: -80     (hash range 0x0000 to 0x7FFF)
│   ├── Primary tablet (read-write)
│   ├── Replica tablet (read-only)
│   └── RDOnly tablet (batch/analytics)
├── Shard: 80-     (hash range 0x8000 to 0xFFFF)
│   ├── Primary tablet
│   ├── Replica tablet
│   └── RDOnly tablet
```

### VTGate — Stateless Query Proxy

- Speaks MySQL protocol (drop-in replacement for apps)
- Parses SQL, resolves sharding via Vindexes
- Rewrites queries for target shards
- Handles scatter-gather for cross-shard queries
- Manages distributed transactions (2PC optional)
- Stateless — horizontally scalable behind a load balancer
- **Overhead**: ~1-2ms per query routing (P50), ~3-5ms (P99)

### VTTablet — Per-MySQL Agent

- One VTTablet per MySQL instance
- Manages query de-duping and connection pooling
- Enforces query blacklists, row limits, query timeouts
- Reports health to topology service
- Manages replication status
- Handles backup/restore operations
- Serves as a "sidecar" for each MySQL

### Vindexes — Sharding Key Functions

| Type | Description | Example |
|------|-------------|---------|
| **Hash** | Consistent hash of column | `xxhash(user_id)` → shard |
| **Numeric** | Direct numeric mapping | `region_id` → shard |
| **Unicode Loose MD5** | String hash | `email` → shard |
| **Lookup (Unique)** | External lookup table | `order_id` → `user_id` → shard |
| **Lookup (Non-unique)** | One-to-many lookup | `email` → multiple `user_id`s |

**VSchema Example:**
```json
{
  "sharded": true,
  "vindexes": {
    "hash": { "type": "hash" },
    "order_lookup": {
      "type": "lookup_unique",
      "params": { "table": "order_lookup", "from": "order_id", "to": "user_id" }
    }
  },
  "tables": {
    "users": {
      "column_vindexes": [
        { "column": "user_id", "name": "hash" }
      ]
    },
    "orders": {
      "column_vindexes": [
        { "column": "user_id", "name": "hash" },
        { "column": "order_id", "name": "order_lookup" }
      ]
    }
  }
}
```

### VReplication — Change Data Capture Engine

- Reads MySQL binlog via VTTablet
- Powers resharding (SplitClone → VReplication streams)
- Enables MoveTables (vertical sharding)
- Materialized views across keyspaces
- Used for Online DDL rollback

### Query Planning (V3 Engine)

```
SQL Query
    │
    ▼
┌──────────┐    ┌───────────┐    ┌──────────────┐    ┌────────────┐
│  Parse   │───▶│  Analyze  │───▶│  Plan (V3)   │───▶│  Execute   │
│  (sqlparser)│ │  (semantic)│   │  (route/join) │   │  (scatter)  │
└──────────┘    └───────────┘    └──────────────┘    └────────────┘
```

Plan types:
- **SelectUnsharded**: Route to unsharded keyspace
- **SelectEqual**: Route to single shard via vindex
- **SelectScatter**: Fan out to all shards, merge results
- **SelectIN**: Route to subset of shards
- **Join**: Nested loop join across shards

---

## Real-World Use Cases

---

### 1. YouTube / Google — The Origin Story

**Context**: YouTube needed to scale MySQL beyond a single machine for video metadata, user data, and view counts serving billions of daily views. Rather than migrating to a NoSQL store, they built Vitess (2011) to keep MySQL semantics while sharding transparently.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   YouTube Application Servers                     │
│              (Video Serving, Comments, Analytics)                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │ MySQL Protocol
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VTGate Cluster (50+ instances)                 │
│         Load-balanced, stateless, geo-distributed                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Keyspace:    │      │ Keyspace:    │      │ Keyspace:    │
│ user_data    │      │ video_meta   │      │ view_counts  │
│              │      │              │      │              │
│ 256 shards   │      │ 512 shards   │      │ 1024 shards  │
│ Key: user_id │      │ Key: video_id│      │ Key: video_id│
│              │      │              │      │              │
│ Primary + 2R │      │ Primary + 3R │      │ Primary + 2R │
└──────────────┘      └──────────────┘      └──────────────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              Topology Service (Borg-internal / ZooKeeper)         │
│    Global cell + per-datacenter local cells                      │
└─────────────────────────────────────────────────────────────────┘
```

#### Sharding Scheme

| Keyspace | Shard Key | Vindex | Shard Count |
|----------|-----------|--------|-------------|
| user_data | user_id | hash (xxhash) | 256 |
| video_meta | video_id | hash | 512 |
| view_counts | video_id | hash | 1024 |

#### Migration Approach

1. Deployed VTTablet as sidecar to existing MySQL instances
2. Introduced VTGate in "passthrough" mode (unsharded keyspace)
3. Defined VSchema and Vindexes for target sharding scheme
4. Used VReplication-based SplitClone to create initial shards
5. Cut over reads first (replica routing), then writes
6. Total migration: ~18 months, zero downtime

#### Query Routing Examples

```sql
-- Direct route (single shard via hash vindex)
SELECT * FROM video_meta WHERE video_id = 'dQw4w9WgXcQ';
-- VTGate: hash('dQw4w9WgXcQ') → shard 3a-3b → single tablet

-- Scatter-gather (no shard key in WHERE)
SELECT COUNT(*) FROM video_meta WHERE upload_date > '2024-01-01';
-- VTGate: fan out to all 512 shards → SUM results

-- Lookup vindex (secondary index)
SELECT * FROM video_meta WHERE channel_id = 12345;
-- VTGate: lookup channel_id → video_ids → hash → target shards
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Total shards | ~1,800+ |
| Peak QPS | 5M+ queries/sec |
| Data volume | Petabytes across keyspaces |
| VTGate instances | 50+ per datacenter |
| Uptime | 99.999% (planned reparenting) |
| Query routing overhead | <2ms P50, <5ms P99 |

---

### 2. Slack Communications — Horizontal Scaling

**Context**: Slack's MySQL infrastructure hit vertical scaling limits with ~100TB+ databases. They migrated to Vitess to enable horizontal sharding without rewriting their application layer or abandoning MySQL transactions.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Slack Application Services                      │
│        (Messaging, Channels, Search Index, Presence)             │
└──────────────────────────────┬──────────────────────────────────┘
                               │ MySQL Protocol (unchanged)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                VTGate Fleet (20+ per region)                      │
│   ┌────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│   │ Query Route│  │ Shard Resolver │  │ Transaction Manager  │  │
│   └────────────┘  └────────────────┘  └──────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
     ┌─────────────────────────┼─────────────────────────┐
     ▼                         ▼                         ▼
┌───────────┐          ┌───────────┐          ┌───────────┐
│ Keyspace: │          │ Keyspace: │          │ Keyspace: │
│ messages  │          │ channels  │          │ workspace │
│           │          │           │          │           │
│ 128 shards│          │ 64 shards │          │ Unsharded │
│ Key:      │          │ Key:      │          │ (single)  │
│ workspace │          │ workspace │          │           │
│ _id       │          │ _id       │          │           │
│           │          │           │          │           │
│ Per shard:│          │ Per shard: │          │ Primary   │
│ 1P + 2R   │          │ 1P + 2R   │          │ + 3R      │
└───────────┘          └───────────┘          └───────────┘
     │                         │                         │
     └─────────────────────────┼─────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Topology Service (etcd cluster)                  │
│              3-node etcd per region, global cell                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Sharding Scheme

| Keyspace | Shard Key | Vindex | Rationale |
|----------|-----------|--------|-----------|
| messages | workspace_id | hash | Co-locate all messages for a workspace |
| channels | workspace_id | hash | Co-locate channels with messages |
| workspace | — (unsharded) | — | Workspace metadata is small |
| files | workspace_id | hash | File metadata co-located |

**Vindex Design:**
```json
{
  "vindexes": {
    "workspace_hash": { "type": "xxhash" },
    "msg_lookup": {
      "type": "lookup_unique",
      "params": {
        "table": "msg_workspace_idx",
        "from": "message_id",
        "to": "workspace_id"
      }
    }
  },
  "tables": {
    "messages": {
      "column_vindexes": [
        { "column": "workspace_id", "name": "workspace_hash" },
        { "column": "message_id", "name": "msg_lookup" }
      ]
    }
  }
}
```

#### Migration Approach

1. **Phase 1 — Shadow**: Deployed VTTablet alongside existing MySQL, VTGate in observation mode
2. **Phase 2 — Read Split**: Routed replica reads through VTGate; compared results
3. **Phase 3 — Write Path**: Switched writes to VTGate (still single shard = unsharded keyspace)
4. **Phase 4 — Reshard**: Used `Reshard` workflow to split into 128 shards
5. **Phase 5 — Cutover**: Switched traffic shard-by-shard, workspace-by-workspace

#### Query Routing Examples

```sql
-- Single-shard (workspace-scoped, most common pattern)
SELECT * FROM messages
WHERE workspace_id = 'T024BE7LD' AND channel_id = 'C1234'
ORDER BY ts DESC LIMIT 50;
-- Route: hash('T024BE7LD') → shard 4a-4c → single tablet

-- Cross-shard (admin query, rare)
SELECT workspace_id, COUNT(*) FROM messages
GROUP BY workspace_id;
-- Route: scatter to all 128 shards → merge + aggregate at VTGate

-- Lookup-based route
SELECT * FROM messages WHERE message_id = '1234567890.123456';
-- Route: lookup message_id → workspace_id → hash → shard
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Total shards | ~250 (messages + channels + files) |
| Peak QPS | 2.5M queries/sec |
| Data volume | 100+ TB |
| Largest workspace | 500K+ users |
| Message throughput | 1B+ messages/day |
| Migration duration | 6 months (zero downtime) |

---

### 3. GitHub Code Platform — Thousands of MySQL Shards

**Context**: GitHub's MySQL infrastructure grew organically to 1,200+ MySQL clusters. They adopted Vitess to bring consistency to shard management, automate failovers, and enable self-service resharding for teams.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  GitHub Application Layer                         │
│   (Rails monolith, Microservices, Git backend, Actions)          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              VTGate Fleet (per-datacenter, 30+ pods)              │
│                  Service mesh integration (GLB)                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
   ┌───────────────┬───────────┼───────────┬───────────────┐
   ▼               ▼           ▼           ▼               ▼
┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
│repos   │  │issues  │  │pulls   │  │actions │  │users   │
│        │  │        │  │        │  │        │  │        │
│512     │  │256     │  │256     │  │128     │  │64      │
│shards  │  │shards  │  │shards  │  │shards  │  │shards  │
│        │  │        │  │        │  │        │  │        │
│Key:    │  │Key:    │  │Key:    │  │Key:    │  │Key:    │
│repo_id │  │repo_id │  │repo_id │  │owner_id│  │user_id │
└────────┘  └────────┘  └────────┘  └────────┘  └────────┘
   │               │           │           │               │
   └───────────────┴───────────┼───────────┴───────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│           Topology: etcd (3-node per DC, 5-node global)          │
└─────────────────────────────────────────────────────────────────┘
```

#### Sharding Scheme

```
repos keyspace:
  Vindex: xxhash(repo_id)
  Shards: 512 (ranges: -0002, 0002-0004, ..., fffe-)

issues keyspace:
  Vindex: xxhash(repo_id)  ← same key as repos for co-location
  Secondary: lookup_unique(issue_number, repo_id → repo_id)

pulls keyspace:
  Vindex: xxhash(repo_id)
  Colocation with issues via shared shard key
```

**Cross-keyspace joins** handled by VTGate scatter + application-level caching.

#### Migration Approach

1. **Inventory**: Catalogued 1,200+ existing MySQL clusters
2. **VTTablet adoption**: Wrapped existing MySQL instances with VTTablet (no data movement)
3. **Topology registration**: Registered all clusters in etcd topology
4. **VTGate rollout**: Incremental per-service, feature-flagged
5. **Resharding**: Used `Reshard` workflow for hot clusters
6. **Automated failover**: Replaced custom scripts with Vitess reparenting

#### Query Routing

```sql
-- Repository lookup (single shard)
SELECT * FROM repositories WHERE repo_id = 123456789;
-- hash(123456789) → shard 0a2c-0a2e

-- Issues for a repo (co-located with repo shard key)
SELECT * FROM issues WHERE repo_id = 123456789 AND state = 'open'
ORDER BY created_at DESC LIMIT 25;
-- Same shard as repo → single tablet read

-- Cross-repo search (scatter)
SELECT repo_id, COUNT(*) as issue_count FROM issues
WHERE state = 'open' GROUP BY repo_id HAVING issue_count > 1000;
-- Scatter to all 256 shards → aggregate at VTGate
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| MySQL clusters managed | 1,200+ |
| Total shards | 1,500+ |
| Peak QPS | 5M+ queries/sec |
| Data volume | 300+ TB |
| Failovers/month (automated) | 50-100 |
| Mean time to reparent | <30 seconds |
| Engineers managing infra | ~15 (down from 50+) |

---

### 4. HubSpot CRM — Multi-Tenant MySQL Scaling

**Context**: HubSpot's CRM serves 100K+ customers (tenants) on shared MySQL infrastructure. Growth required horizontal scaling while maintaining tenant isolation and consistent query performance regardless of tenant size.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   HubSpot CRM Application                        │
│          (Contacts, Deals, Tickets, Marketing Hub)               │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VTGate (12 instances per AZ)                   │
│         ┌─────────────────────────────────────────┐              │
│         │  Tenant-aware routing (portal_id hash)  │              │
│         └─────────────────────────────────────────┘              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Keyspace:    │      │ Keyspace:    │      │ Keyspace:    │
│ contacts     │      │ deals        │      │ activities   │
│              │      │              │      │              │
│ 256 shards   │      │ 128 shards   │      │ 256 shards   │
│ Key:portal_id│      │ Key:portal_id│      │ Key:portal_id│
│              │      │              │      │              │
│ ~4TB/shard   │      │ ~2TB/shard   │      │ ~3TB/shard   │
└──────────────┘      └──────────────┘      └──────────────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    etcd Topology (3-node)                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Tenant → Shard mapping cached at VTGate level             │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

#### Sharding Scheme

```
All keyspaces use portal_id (tenant ID) as shard key.

Vindex: xxhash(portal_id)
  - Ensures even distribution regardless of tenant size
  - All data for one tenant on one shard (single-shard transactions)

Lookup Vindexes:
  - contact_email → portal_id (for cross-tenant dedup)
  - deal_id → portal_id (for direct deal access)

Sequence Tables (unsharded keyspace):
  - contact_id_seq
  - deal_id_seq
  - activity_id_seq
```

#### Migration Approach

1. **Dual-write phase**: Application wrote to both old MySQL and Vitess-managed MySQL
2. **Validation**: Compared reads between both systems for 2 weeks
3. **Read cutover**: Shifted reads to Vitess (by tenant cohort, 5% → 25% → 50% → 100%)
4. **Write cutover**: Shifted writes (same cohort strategy)
5. **Reshard hot tenants**: Large tenants that dominated a shard were isolated via re-sharding with custom vindex ranges

#### Query Routing

```sql
-- Tenant-scoped (99% of queries)
SELECT * FROM contacts
WHERE portal_id = 98765 AND lifecycle_stage = 'customer'
LIMIT 100;
-- Route: hash(98765) → shard a2-a4 → single tablet

-- Cross-tenant admin (rare, internal tooling)
SELECT portal_id, COUNT(*) FROM contacts GROUP BY portal_id;
-- Route: scatter-gather all 256 shards

-- Lookup-based access
SELECT * FROM deals WHERE deal_id = 5551234;
-- Route: lookup deal_id → portal_id → hash → shard
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Tenants (portals) | 100,000+ |
| Total shards | ~640 |
| Peak QPS | 1.2M queries/sec |
| Data volume | 1.5 PB |
| Largest tenant | 50M+ contacts |
| Single-shard query % | 99.2% |
| Query latency P50 | 3ms (app → VTGate → MySQL → back) |
| Query latency P99 | 15ms |

---

### 5. Square/Block Payments — Financial Transaction Processing

**Context**: Square needed to scale their payment processing MySQL while maintaining ACID guarantees, audit trails, and strict consistency requirements mandated by financial regulations. Vitess provided horizontal scaling without sacrificing transactional integrity.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                Square Payment Processing Services                 │
│        (POS, Online Payments, Cash App, Invoices)                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              VTGate (HA pair per AZ, 3 AZs)                      │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  2PC Coordinator for cross-shard transactions             │    │
│  │  Read-after-write consistency enforcement                 │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
     ┌─────────────────────────┼─────────────────────────┐
     ▼                         ▼                         ▼
┌───────────┐          ┌───────────┐          ┌───────────┐
│ Keyspace: │          │ Keyspace: │          │ Keyspace: │
│ payments  │          │ merchants │          │ ledger    │
│           │          │           │          │           │
│ 512 shards│          │ 128 shards│          │ 256 shards│
│ Key:      │          │ Key:      │          │ Key:      │
│ merchant  │          │ merchant  │          │ merchant  │
│ _id       │          │ _id       │          │ _id       │
│           │          │           │          │           │
│ 1P + 3R   │          │ 1P + 2R   │          │ 1P + 3R   │
│ Semi-sync │          │ Semi-sync │          │ Semi-sync │
└───────────┘          └───────────┘          └───────────┘
     │                         │                         │
     └─────────────────────────┼─────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│         Topology: etcd (5-node, cross-AZ, TLS mutual auth)       │
└─────────────────────────────────────────────────────────────────┘
```

#### Sharding Scheme

```
payments keyspace:
  Primary Vindex: xxhash(merchant_id)
  Secondary: lookup_unique(payment_id → merchant_id)
  
  Tables:
    - transactions (merchant_id, payment_id, amount, status, ts)
    - refunds (merchant_id, payment_id, refund_id, amount)
    - settlements (merchant_id, settlement_date, amount)

Sequence tables (unsharded, HA):
  - payment_id_seq (Vitess sequence, no gaps allowed)
  - refund_id_seq

Cross-shard transactions:
  - Transfer between merchants uses Vitess 2PC
  - Atomic: debit merchant_a + credit merchant_b
```

#### Migration Approach

1. **Compliance review**: Validated Vitess 2PC meets PCI-DSS requirements
2. **Shadow cluster**: Ran Vitess cluster receiving replicated binlog (read-only validation)
3. **Canary**: 0.1% of transactions routed through Vitess, reconciled hourly
4. **Incremental rollout**: 1% → 10% → 50% → 100% over 4 months
5. **Resharding**: Started 64 shards, grew to 512 over 18 months using online resharding

#### Query Routing

```sql
-- Payment creation (single-shard, most critical path)
INSERT INTO transactions (merchant_id, payment_id, amount, status)
VALUES ('merch_abc123', 'pay_xyz789', 2500, 'authorized');
-- Route: hash('merch_abc123') → shard 7f-80 → primary tablet

-- Payment lookup by ID (lookup vindex)
SELECT * FROM transactions WHERE payment_id = 'pay_xyz789';
-- Route: lookup pay_xyz789 → merchant_id → hash → shard

-- Daily settlement (single-shard aggregate)
SELECT SUM(amount) FROM transactions
WHERE merchant_id = 'merch_abc123'
  AND status = 'captured'
  AND ts BETWEEN '2024-01-01' AND '2024-01-02';
-- Route: single shard (merchant_id in WHERE)

-- Cross-shard transfer (2PC)
BEGIN;
UPDATE ledger SET balance = balance - 1000
  WHERE merchant_id = 'merch_sender';
UPDATE ledger SET balance = balance + 1000
  WHERE merchant_id = 'merch_receiver';
COMMIT;
-- Route: 2PC across two shards, atomic commit via VTGate coordinator
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Total shards | ~900 |
| Peak QPS | 800K queries/sec |
| Transactions/day | 100M+ |
| Data volume | 200+ TB |
| Write latency P50 | 4ms |
| Write latency P99 | 12ms |
| 2PC overhead | +3-5ms vs single-shard |
| Availability | 99.999% (five nines) |
| RPO | 0 (semi-sync replication) |

---

## Replication

### MySQL Replication Managed by Vitess

```
┌─────────────────── Shard: customers/-80 ───────────────────┐
│                                                             │
│  ┌─────────────────┐       Binlog Stream                   │
│  │  PRIMARY        │─────────────────────┐                 │
│  │  VTTablet       │                     │                 │
│  │  ┌───────────┐  │                     ▼                 │
│  │  │  MySQL    │  │          ┌─────────────────┐          │
│  │  │  (R/W)    │  │          │  REPLICA        │          │
│  │  └───────────┘  │          │  VTTablet       │          │
│  └─────────────────┘          │  ┌───────────┐  │          │
│           │                   │  │  MySQL    │  │          │
│           │ Binlog            │  │  (R/O)    │  │          │
│           │                   │  └───────────┘  │          │
│           ▼                   └─────────────────┘          │
│  ┌─────────────────┐                                       │
│  │  REPLICA 2      │                                       │
│  │  VTTablet       │                                       │
│  │  ┌───────────┐  │                                       │
│  │  │  MySQL    │  │                                       │
│  │  │  (R/O)    │  │                                       │
│  │  └───────────┘  │                                       │
│  └─────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

### Reparenting

**Planned Reparent Shard (PRS):**
```
vtctldclient PlannedReparentShard --keyspace=commerce --shard=-80 \
  --new-primary=zone1-101

Steps:
1. Set old primary to read-only
2. Wait for all replicas to catch up (GTID-based)
3. Promote new primary (set read-write)
4. Point replicas to new primary
5. Update topology service
Duration: 1-3 seconds
```

**Emergency Reparent Shard (ERS):**
```
vtctldclient EmergencyReparentShard --keyspace=commerce --shard=-80

Steps:
1. Detect primary failure (health check timeout)
2. Choose most advanced replica (highest GTID)
3. Promote to primary
4. Reparent remaining replicas
5. Update topology
Duration: 5-15 seconds
Data loss: possible if semi-sync not enabled
```

### Semi-Sync Replication Configuration

```
# VTTablet flags for semi-sync enforcement
--enable_semi_sync=true
--semi_sync_wait_for_replica_count=1

# MySQL variables (managed by VTTablet)
rpl_semi_sync_master_enabled = 1
rpl_semi_sync_master_wait_for_slave_count = 1
rpl_semi_sync_master_timeout = 1000000000  # effectively infinite
rpl_semi_sync_slave_enabled = 1

# Durability policy (set per keyspace)
vtctldclient SetKeyspaceDurabilityPolicy \
  --keyspace=payments --durability-policy=semi_sync
```

**Durability Policies:**
| Policy | Behavior | Use Case |
|--------|----------|----------|
| `none` | Async replication | Dev/test |
| `semi_sync` | Wait for 1 replica ACK | Production (default) |
| `cross_cell` | Wait for ACK from different cell | Disaster recovery |

### VReplication

```
┌──────────────┐         ┌──────────────┐
│  Source      │         │  Target      │
│  VTTablet   │         │  VTTablet    │
│  ┌────────┐ │ binlog  │  ┌────────┐  │
│  │ MySQL  │─┼─────────┼─▶│ MySQL  │  │
│  └────────┘ │ stream  │  └────────┘  │
└──────────────┘         └──────────────┘

VReplication uses:
├── Resharding (split/merge shards)
├── MoveTables (vertical sharding)
├── Materialized Views (cross-keyspace)
├── Online DDL rollback
└── Change Data Capture (CDC)
```

**VReplication Workflow States:**
```
Copying → Running → Lagging(<1s) → Caught Up → Switching Traffic
```

### Cross-Shard Replication Patterns

```
Materialized View Example:
  Source keyspace: orders (sharded by customer_id)
  Target keyspace: merchant_analytics (sharded by merchant_id)

  CREATE MATERIALIZED VIEW merchant_order_summary AS
  SELECT merchant_id, COUNT(*) as order_count, SUM(amount) as revenue
  FROM orders GROUP BY merchant_id;

  # Vitess command
  vtctldclient Materialize --workflow=merchant_summary \
    --source-keyspace=orders --target-keyspace=merchant_analytics \
    --table-settings='[{"target_table":"merchant_order_summary", ...}]'
```

---

## Scalability

### VTGate Query Routing Architecture

```
                    Incoming SQL Query
                           │
                           ▼
                  ┌─────────────────┐
                  │   SQL Parser    │
                  └────────┬────────┘
                           │ AST
                           ▼
                  ┌─────────────────┐
                  │ Semantic Analysis│
                  │ (resolve tables, │
                  │  check VSchema)  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Route Planning │
                  │  (V3 Engine)    │
                  └────────┬────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ Single     │ │ Scatter    │ │ Multi-shard│
     │ Shard      │ │ (all)      │ │ (subset)   │
     │ Route      │ │ Route      │ │ Route      │
     └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
           │               │              │
           ▼               ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ VTTablet   │ │ All        │ │ VTTablets  │
     │ (1 shard)  │ │ VTTablets  │ │ (N shards) │
     └────────────┘ └────────────┘ └────────────┘
           │               │              │
           └───────────────┼──────────────┘
                           ▼
                  ┌─────────────────┐
                  │  Result Merge   │
                  │  (sort, limit,  │
                  │   aggregate)    │
                  └─────────────────┘
```

### Performance: Query Routing Overhead

| Operation | Overhead (vs direct MySQL) |
|-----------|---------------------------|
| Single-shard SELECT | +0.5-1.5ms |
| Single-shard INSERT | +0.5-1.5ms |
| Scatter SELECT (no aggregation) | +2-5ms |
| Scatter SELECT (with ORDER BY/LIMIT) | +5-15ms |
| Cross-shard JOIN | +10-50ms (depends on fan-out) |
| 2PC Transaction | +3-8ms |

### Vindexes Deep Dive

```
┌─────────────────────────────────────────────────────────┐
│                    Vindex Types                           │
├──────────────┬──────────────────────────────────────────┤
│ PRIMARY      │ Determines shard for a row               │
│ (required)   │ Must be Unique, Functional               │
│              │ Examples: hash, xxhash, numeric           │
├──────────────┼──────────────────────────────────────────┤
│ SECONDARY    │ Enables routing without primary key      │
│ (optional)   │ Can be Lookup (stored in separate table) │
│              │ Examples: lookup_unique, lookup           │
├──────────────┼──────────────────────────────────────────┤
│ FUNCTIONAL   │ Computed from column value (no lookup)   │
│              │ Stateless, deterministic                  │
│              │ Examples: hash, xxhash, numeric, unicode  │
├──────────────┼──────────────────────────────────────────┤
│ LOOKUP       │ Uses a backing table to map              │
│              │ column → keyspace_id                     │
│              │ Requires maintenance (auto by Vitess)    │
└──────────────┴──────────────────────────────────────────┘
```

### Horizontal Resharding (Reshard Workflow)

```
Before: 2 shards                 After: 4 shards
┌───────────┬───────────┐       ┌──────┬──────┬──────┬──────┐
│  -80      │  80-      │  ──▶  │ -40  │40-80 │80-c0 │ c0-  │
└───────────┴───────────┘       └──────┴──────┴──────┴──────┘

Workflow Steps:
1. vtctldclient Reshard --workflow=reshard_2to4 \
     --source-shards='-80,80-' \
     --target-shards='-40,40-80,80-c0,c0-' \
     --keyspace=commerce Create

2. VReplication copies data to new shards (online, non-blocking)

3. vtctldclient Reshard ... SwitchTraffic --tablet-types=rdonly,replica

4. vtctldclient Reshard ... SwitchTraffic --tablet-types=primary

5. vtctldclient Reshard ... Complete
   (drops old shards' VReplication streams, cleans up)
```

### Vertical Sharding (MoveTables)

```
Before: Monolithic keyspace        After: Separated keyspaces

┌─────────────────────────┐      ┌──────────────┐  ┌──────────────┐
│  commerce (unsharded)   │      │  commerce    │  │  customer    │
│  ├── products           │ ──▶  │  ├── products│  │  ├── customers│
│  ├── orders             │      │  ├── orders  │  │  └── addresses│
│  ├── customers          │      │  └── ...     │  └──────────────┘
│  └── addresses          │      │              │
└─────────────────────────┘      └──────────────┘

vtctldclient MoveTables --workflow=move_customers \
  --source-keyspace=commerce --target-keyspace=customer \
  --tables='customers,addresses' Create
```

### Sequence Tables (Cross-Shard Auto-Increment)

```sql
-- Unsharded keyspace holds sequence tables
CREATE TABLE user_id_seq (
  id BIGINT NOT NULL,
  next_id BIGINT NOT NULL,
  cache BIGINT NOT NULL,  -- VTTablet caches this many IDs
  PRIMARY KEY (id)
) ENGINE=InnoDB;

-- VSchema configuration
"tables": {
  "users": {
    "auto_increment": {
      "column": "user_id",
      "sequence": "user_id_seq"
    }
  }
}

-- Cache size determines batch allocation
-- cache=1000 → VTTablet requests 1000 IDs at a time
-- Reduces contention on sequence table
```

### Connection Pooling at VTTablet

```
┌────────────────────────────────────────────────────┐
│                    VTTablet                          │
│                                                     │
│  Incoming connections from VTGate                   │
│  (thousands of concurrent queries)                  │
│         │                                           │
│         ▼                                           │
│  ┌──────────────────┐                               │
│  │  Query Consolidator  │  ← dedup identical queries│
│  └─────────┬────────┘                               │
│            ▼                                        │
│  ┌──────────────────┐                               │
│  │  Transaction Pool │  (default: 20 connections)   │
│  │  Query Pool       │  (default: 300 connections)  │
│  │  Stream Pool      │  (default: 200 connections)  │
│  └─────────┬────────┘                               │
│            ▼                                        │
│  ┌──────────────────┐                               │
│  │  MySQL (local)    │                              │
│  └──────────────────┘                               │
└────────────────────────────────────────────────────┘

Flags:
  --queryserver-config-pool-size=300
  --queryserver-config-transaction-cap=20
  --queryserver-config-stream-pool-size=200
  --queryserver-config-query-timeout=30  # seconds
```

### Scatter-Gather Query Execution

```
Query: SELECT name, total FROM orders WHERE amount > 100
       ORDER BY total DESC LIMIT 10;

VTGate execution:
1. Parse + plan → scatter (no shard key in WHERE)
2. Rewrite per-shard: each shard gets ORDER BY total DESC LIMIT 10
3. Send to all N shards in parallel
4. Collect N × 10 rows
5. Merge-sort by total DESC
6. Return top 10 to client

Optimization: push down LIMIT to shards to minimize data transfer
```

---

## Production Setup

### Kubernetes Deployment (Vitess Operator)

```yaml
# vitess-cluster.yaml
apiVersion: planetscale.com/v2
kind: VitessCluster
metadata:
  name: production
spec:
  images:
    vtgate: vitess/lite:18.0
    vttablet: vitess/lite:18.0
    vtctld: vitess/lite:18.0
    mysqld:
      mysql80Compatible: vitess/lite:18.0
  
  cells:
    - name: zone1
      gateway:
        replicas: 3
        resources:
          requests: { cpu: "2", memory: "4Gi" }
  
  keyspaces:
    - name: commerce
      turndownPolicy: Immediate
      partitionings:
        - equal:
            parts: 4
            shardTemplate:
              databaseInitScriptSecret:
                name: commerce-schema
                key: init.sql
              tabletPools:
                - type: replica
                  cell: zone1
                  replicas: 3
                  mysqld:
                    resources:
                      requests: { cpu: "4", memory: "16Gi" }
                  dataVolumeClaimTemplate:
                    accessModes: ["ReadWriteOnce"]
                    resources:
                      requests: { storage: "500Gi" }
                    storageClassName: ssd
```

```
Operator Architecture:
┌──────────────────────────────────────────────────┐
│              Kubernetes Cluster                    │
│                                                   │
│  ┌──────────────┐     ┌────────────────────────┐ │
│  │ Vitess       │     │ VitessCluster CR       │ │
│  │ Operator     │────▶│ (desired state)        │ │
│  └──────────────┘     └────────────────────────┘ │
│         │                                        │
│         ▼ Reconciles                             │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │ vtctld Pod │ │ VTGate Pods│ │ etcd Pods  │   │
│  └────────────┘ └────────────┘ └────────────┘   │
│  ┌────────────────────────────────────────────┐  │
│  │ VTTablet Pods (StatefulSets per shard)     │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │  │
│  │  │-80 P │ │-80 R │ │80- P │ │80- R │     │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘     │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Topology Service Options

| Service | Pros | Cons | Recommended For |
|---------|------|------|-----------------|
| **etcd** | Native K8s, fast, well-tested with Vitess | Requires backup strategy | Production (default) |
| **ZooKeeper** | Battle-tested, strong consistency | JVM overhead, complex ops | Legacy deployments |
| **Consul** | Multi-DC native, service mesh integration | Less tested with Vitess | HashiCorp stack shops |

```
# etcd topology flags (VTGate/VTTablet)
--topo_implementation=etcd2
--topo_global_server_address=etcd-global:2379
--topo_global_root=/vitess/global
```

### Monitoring

```
Prometheus Metrics (key ones):

# VTGate
vtgate_queries_total{keyspace, shard, type}
vtgate_error_counts{keyspace, code}
vtgate_query_latency_bucket{keyspace, type}

# VTTablet  
vttablet_queries_total{table, type}
vttablet_query_latency_bucket
vttablet_transaction_pool_available
vttablet_kills{reason}

# Replication
vttablet_replication_lag_seconds
vttablet_vreplication_seconds_behind_master

# Health
vtctld_tablet_health{keyspace, shard, type, state}

Recommended Alerts:
- replication_lag > 10s
- vttablet_query_error_rate > 1%
- vtgate_error_counts increasing
- transaction_pool_available < 2
```

### Backup and Restore

```
# Built-in backup (VTTablet)
vtctldclient Backup zone1-commerce-80-replica-1

# Backup engines:
--backup_storage_implementation=gcs    # or s3, file
--gcs_backup_storage_bucket=my-vitess-backups
--backup_engine_implementation=builtin  # or xtrabackup

# Automated backup schedule (via cron or operator)
vtctldclient BackupShard --keyspace=commerce --shard=-80

# Restore (automatic on tablet init)
# VTTablet checks for latest backup on startup
# Restores, then catches up via replication

# Point-in-time recovery
vtctldclient RestoreFromBackup --backup-timestamp=2024-01-15T10:00:00Z \
  zone1-commerce-80-replica-2
```

### Schema Management

```
# ApplySchema (online, non-blocking)
vtctldclient ApplySchema --keyspace=commerce \
  --sql="ALTER TABLE orders ADD COLUMN status VARCHAR(20) DEFAULT 'pending'"

# Online DDL strategies
vtctldclient ApplySchema --keyspace=commerce \
  --ddl-strategy="vitess"  \  # or "gh-ost", "pt-osc", "direct"
  --sql="ALTER TABLE users ADD INDEX idx_email(email)"

# Online DDL lifecycle:
# queued → ready → running → complete
# Can cancel, retry, or revert

# VDiff (data integrity verification after resharding)
vtctldclient VDiff --workflow=reshard_2to4 --keyspace=commerce Create
vtctldclient VDiff --workflow=reshard_2to4 --keyspace=commerce Show last

# Schema tracking
vtctldclient GetSchema zone1-commerce-80-primary
vtctldclient ValidateSchemaKeyspace commerce  # ensures all shards match
```

### Online DDL

```
Strategy Comparison:

┌────────────┬──────────────┬───────────────┬──────────────────┐
│ Strategy   │ Blocking?    │ Disk Space    │ Revertible?      │
├────────────┼──────────────┼───────────────┼──────────────────┤
│ vitess     │ No           │ 2x table      │ Yes (instant)    │
│ gh-ost     │ No           │ 2x table      │ No               │
│ pt-osc     │ No           │ 2x table      │ No               │
│ direct     │ Yes (for DDL)│ Minimal       │ No               │
└────────────┴──────────────┴───────────────┴──────────────────┘

# Vitess-native online DDL (recommended)
vtctldclient ApplySchema --keyspace=commerce \
  --ddl-strategy="vitess --postpone-completion" \
  --sql="ALTER TABLE orders ADD COLUMN region VARCHAR(10)"

# Check progress
vtctldclient OnlineDDL commerce show recent

# Complete when ready
vtctldclient OnlineDDL commerce complete <uuid>

# Revert if issues
vtctldclient OnlineDDL commerce revert <uuid>
```

### Upgrade Strategies

```
Rolling Upgrade Path:

1. Upgrade vtctld (control plane, low risk)
2. Upgrade VTTablet replicas (one shard at a time)
3. Planned reparent to upgraded replicas
4. Upgrade old primaries (now replicas)
5. Upgrade VTGate (rolling restart, stateless)

Key Rules:
- VTGate version >= VTTablet version (always)
- One minor version at a time (no skipping)
- Test in staging with production traffic replay
- Vitess supports N-1 compatibility between components

# Example with Kubernetes operator
kubectl patch vitesscluster production --type=merge \
  -p '{"spec":{"images":{"vtgate":"vitess/lite:19.0"}}}'
# Operator handles rolling restart
```

---

## Summary: When to Use Vitess

| Scenario | Vitess Fit |
|----------|-----------|
| MySQL > 1TB needing horizontal scale | Excellent |
| Multi-tenant SaaS on MySQL | Excellent |
| Need MySQL compatibility + sharding | Excellent |
| Already on MySQL, can't rewrite app | Excellent |
| Need < 5ms latency at scale | Good (adds 1-2ms) |
| Cross-shard transactions (heavy) | Acceptable (2PC overhead) |
| Small database (< 100GB) | Overkill |
| Need strong cross-shard joins | Consider alternatives |
| Greenfield with no MySQL requirement | Evaluate CockroachDB/Spanner |
