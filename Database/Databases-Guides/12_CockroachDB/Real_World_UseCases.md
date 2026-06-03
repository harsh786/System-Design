# CockroachDB - Real World Use Cases & Production Guide

## Table of Contents
- [Core Concepts](#core-concepts)
- [Use Case 1: DoorDash Order Management](#use-case-1-doordash-order-management)
- [Use Case 2: Netflix Account Data](#use-case-2-netflix-account-data)
- [Use Case 3: Bose IoT Platform](#use-case-3-bose-iot-platform)
- [Use Case 4: Loom Video Platform](#use-case-4-loom-video-platform)
- [Use Case 5: Hard Rock Digital Sports Betting](#use-case-5-hard-rock-digital-sports-betting)
- [Replication Deep Dive](#replication-deep-dive)
- [Scalability](#scalability)
- [Production Setup](#production-setup)

---

## Core Concepts

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        SQL Layer                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Parser  │→ │ Planner  │→ │Optimizer │→ │DistSQL   │       │
│  │          │  │          │  │(CBO)     │  │Execution │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
├─────────────────────────────────────────────────────────────────┤
│                   Transaction Layer                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Serializable Snapshot Isolation (SSI)                    │   │
│  │  • Parallel Commits  • Transaction Pipelining             │   │
│  │  • Write Intents     • Transaction Record                 │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                   Distribution Layer                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Range-based Sharding (512MB default split size)          │   │
│  │  • Leaseholder routing  • Range descriptor cache          │   │
│  │  • Raft consensus       • Range merging/splitting         │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                   Storage Layer (Pebble)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  MVCC Key-Value Store                                     │   │
│  │  • LSM Tree (Pebble - Go-native RocksDB replacement)      │   │
│  │  • Hybrid Logical Clocks (HLC) for timestamps             │   │
│  │  • Intent resolution  • Garbage collection                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Raft Consensus Within Ranges

Every range (unit of data, ~512MB) forms its own Raft group:

```
              Range [/orders/1000 - /orders/2000]
    ┌─────────────────────────────────────────────────┐
    │                                                   │
    │   Node 1 (us-east)     Node 3 (us-west)         │
    │   ┌─────────────┐      ┌─────────────┐          │
    │   │   Replica    │      │   Replica    │          │
    │   │  (Leader +   │      │  (Follower)  │          │
    │   │  Leaseholder)│      │              │          │
    │   └──────┬───────┘      └──────▲───────┘          │
    │          │    Raft Log          │                  │
    │          │    AppendEntries     │                  │
    │          ├──────────────────────┘                  │
    │          │                                         │
    │          │         Node 2 (us-central)            │
    │          │         ┌─────────────┐                │
    │          └────────►│   Replica    │                │
    │                    │  (Follower)  │                │
    │                    └─────────────┘                │
    │                                                   │
    │   Write: Leader → quorum (2/3) → commit           │
    │   Read:  Leaseholder serves directly              │
    └─────────────────────────────────────────────────┘
```

### MVCC with Hybrid Logical Clocks (HLC)

```
HLC Timestamp = (Physical Time, Logical Counter)

Key: /orders/1234
┌────────────────────────────────────────────────────┐
│ Version @ HLC(1686000003.0, 2)  → {status: "done"} │
│ Version @ HLC(1686000002.0, 0)  → {status: "active"}│
│ Version @ HLC(1686000001.0, 0)  → {status: "new"}  │
└────────────────────────────────────────────────────┘

• Physical clock synchronized via NTP (max offset: 500ms default)
• Logical counter breaks ties when physical clocks equal
• Uncertainty interval: [timestamp - max_offset, timestamp]
  - If read encounters value in uncertainty window → restart txn
• Closed timestamps: declares no more writes below timestamp
  → enables consistent follower reads
```

### Serializable Snapshot Isolation (SSI)

```
Transaction Flow:
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  BEGIN (Serializable)                                         │
│    │                                                          │
│    ├─► Acquire timestamp (HLC)                                │
│    │                                                          │
│    ├─► Read: check for write intents (conflicts)              │
│    │         if intent found → push or wait                   │
│    │                                                          │
│    ├─► Write: lay down "write intent" (provisional value)     │
│    │          intent = MVCC value + pointer to txn record      │
│    │                                                          │
│    ├─► COMMIT (Parallel Commits Protocol):                    │
│    │     1. Write txn record as STAGING                       │
│    │     2. Write intents in parallel                         │
│    │     3. If all intents succeed → txn implicitly committed │
│    │     4. Asynchronously resolve intents → COMMITTED        │
│    │                                                          │
│  END                                                          │
└─────────────────────────────────────────────────────────────┘

Conflict Resolution:
• Write-Write: Second writer pushes first's timestamp or waits
• Write-Read:  Writer must have timestamp > reader's
• Read-Write:  If write timestamp < read timestamp → retry txn
```

### Distributed Transactions: Parallel Commits

```
Traditional 2PC:                    CockroachDB Parallel Commits:

Client                              Client
  │                                   │
  ├─► Coordinator                     ├─► Coordinator
  │     │                             │     │
  │     ├─► Prepare(A) ──┐            │     ├─► Write Intent(A) ─┐
  │     ├─► Prepare(B) ──┤ Sequential │     ├─► Write Intent(B) ─┤ Parallel
  │     │                 │            │     ├─► Txn STAGING ─────┤
  │     │◄── All OK ─────┘            │     │                    │
  │     │                             │     │◄── All OK ─────────┘
  │     ├─► Commit(A) ───┐            │     │
  │     ├─► Commit(B) ───┤            │     │  Transaction is now
  │     │                 │            │     │  implicitly committed!
  │     │◄── Done ────────┘            │     │
  │◄────┘                             │◄────┘  (intents resolved async)
  │                                   │
  Latency: 2 RTT                      Latency: 1 RTT (write path)
```

### CockroachDB vs Google Spanner

| Feature | CockroachDB | Google Spanner |
|---------|-------------|----------------|
| Clock sync | NTP (software, ~500ms offset) | TrueTime (GPS + atomic clocks, <7ms) |
| Consistency | Serializable (SSI) | External consistency (linearizable) |
| Uncertainty handling | Restart txn if in window | Wait out uncertainty (commit-wait) |
| Deployment | Self-hosted or Cloud | GCP only |
| SQL compatibility | PostgreSQL wire protocol | Custom SQL + gRPC |
| Licensing | BSL / Enterprise | Proprietary |
| Read latency (local) | <2ms | <5ms |
| Write latency (quorum) | ~10-50ms (cross-AZ) | ~10-20ms (TrueTime advantage) |
| Multi-region write | ~100-300ms | ~50-100ms (commit-wait shorter) |

---

## Use Case 1: DoorDash Order Management

### Problem
DoorDash processes millions of orders daily across multiple US regions. Required: strong consistency for order state transitions, multi-region availability for <99.999% uptime, and low-latency reads from any region.

### Why CockroachDB
- **Serializable isolation**: Order state machine (placed → accepted → picked_up → delivered) must never have race conditions
- **Multi-region**: Orders served locally; survive full region failure
- **Horizontal scaling**: Handle 10x traffic spikes during peak hours (Super Bowl, etc.)

### Scale Numbers
- ~1M+ orders/day, 100K+ concurrent orders
- 3 regions (us-east, us-central, us-west)
- 9 nodes (3 per region), ~50TB total data
- p99 read latency: <10ms (local), p99 write: <100ms (cross-region)

### Architecture

```
                         DoorDash Order System
┌──────────────────────────────────────────────────────────────────┐
│                                                                    │
│   us-east-1                us-central-1           us-west-2       │
│  ┌──────────┐            ┌──────────┐          ┌──────────┐     │
│  │ Node 1   │            │ Node 4   │          │ Node 7   │     │
│  │ Node 2   │            │ Node 5   │          │ Node 8   │     │
│  │ Node 3   │            │ Node 6   │          │ Node 9   │     │
│  └────┬─────┘            └────┬─────┘          └────┬─────┘     │
│       │                       │                      │            │
│       └───────────────────────┼──────────────────────┘            │
│                               │                                    │
│              Range: orders[1-1000]                                 │
│       ┌───────────────────────┼──────────────────────┐            │
│       │                       │                      │            │
│  ┌────▼────┐           ┌─────▼────┐          ┌─────▼────┐       │
│  │Replica 1│           │Replica 2 │          │Replica 3 │       │
│  │(Lease-  │◄─Raft────►│(Follower)│◄─Raft──►│(Follower)│       │
│  │ holder) │           │          │          │          │       │
│  └─────────┘           └──────────┘          └──────────┘       │
│                                                                    │
│  Leaseholder preference: region of order's delivery zone           │
│  REGIONAL BY ROW: orders pinned to their delivery region           │
└──────────────────────────────────────────────────────────────────┘
```

### SQL Schema

```sql
-- Multi-region database setup
ALTER DATABASE doordash PRIMARY REGION "us-east1";
ALTER DATABASE doordash ADD REGION "us-central1";
ALTER DATABASE doordash ADD REGION "us-west2";
ALTER DATABASE doordash SURVIVE REGION FAILURE;

-- Orders table: REGIONAL BY ROW pins data to delivery region
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    customer_id UUID NOT NULL,
    dasher_id UUID,
    store_id UUID NOT NULL,
    status STRING NOT NULL DEFAULT 'placed'
        CHECK (status IN ('placed','accepted','preparing','picked_up','delivering','delivered','cancelled')),
    total_cents INT NOT NULL,
    items JSONB NOT NULL,
    placed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    estimated_delivery TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    
    INDEX idx_customer_orders (customer_id, placed_at DESC),
    INDEX idx_dasher_active (dasher_id, status) WHERE status IN ('accepted','picked_up','delivering'),
    INDEX idx_store_orders (store_id, placed_at DESC)
) LOCALITY REGIONAL BY ROW;

-- Order state transitions (audit log)
CREATE TABLE order_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    order_id UUID NOT NULL REFERENCES orders(order_id),
    from_status STRING,
    to_status STRING NOT NULL,
    actor_type STRING NOT NULL, -- 'system', 'dasher', 'customer', 'store'
    actor_id UUID,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    INDEX idx_order_events (order_id, created_at)
) LOCALITY REGIONAL BY ROW;

-- Active dashers: always read locally for dispatch
CREATE TABLE dasher_locations (
    dasher_id UUID PRIMARY KEY,
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    lat DECIMAL(9,6) NOT NULL,
    lng DECIMAL(9,6) NOT NULL,
    status STRING NOT NULL DEFAULT 'available',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    INDEX idx_geo (region, lat, lng) WHERE status = 'available'
) LOCALITY REGIONAL BY ROW;
```

### Multi-Region Configuration

```sql
-- Ensure leaseholders are co-located with consumers
ALTER TABLE orders SET (
    schema_locked = true  -- prevent online schema change interference
);

-- Zone config for additional control
ALTER PARTITION "us-east1" OF INDEX orders@primary
    CONFIGURE ZONE USING
    num_replicas = 5,
    lease_preferences = '[[+region=us-east1]]',
    constraints = '{+region=us-east1: 2, +region=us-central1: 2, +region=us-west2: 1}';
```

---

## Use Case 2: Netflix Account Data

### Problem
Netflix needed to migrate billing/account data from Cassandra. Cassandra's eventual consistency caused issues: duplicate charges, incorrect plan states, and race conditions during concurrent account modifications.

### Why CockroachDB
- **Serializable transactions**: No more double-charges or stale plan reads
- **PostgreSQL compatibility**: Existing tooling, ORMs, migration paths
- **Multi-region with strong consistency**: Account updates visible globally within milliseconds
- **Online schema changes**: Evolve billing schemas without downtime

### Scale Numbers
- 250M+ subscriber accounts globally
- 5 regions (us-east, us-west, eu-west, ap-southeast, sa-east)
- 45+ nodes, ~200TB account/billing data
- p99 read: <5ms (local), p99 write: <150ms (global consistency)
- 50K+ transactions/second steady state

### Architecture

```
                      Netflix Account Service
┌────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐         │
│  │us-east  │    │us-west  │    │eu-west  │    │ap-south │         │
│  │(9 nodes)│    │(9 nodes)│    │(9 nodes)│    │(9 nodes)│         │
│  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘         │
│       │              │              │              │                 │
│       └──────────────┴──────────────┴──────────────┘                │
│                              │                                       │
│                 GLOBAL TABLE: plans, pricing                         │
│                 (cached reads from any region, <2ms)                 │
│                                                                      │
│                 REGIONAL BY ROW: accounts, billing                   │
│                 (pinned to subscriber's home region)                 │
│                                                                      │
│   Account 'user_eu_123':                                            │
│   ┌─────────────────────────────────────────────┐                   │
│   │  Leaseholder: eu-west (home region)          │                   │
│   │  Replicas: eu-west(2), us-east(1), us-west(1)│                  │
│   │  Read from eu-west: 2ms                      │                   │
│   │  Write (quorum eu-west + us-east): ~80ms     │                   │
│   └─────────────────────────────────────────────┘                   │
│                                                                      │
│   Plan 'premium_4k' (GLOBAL):                                       │
│   ┌─────────────────────────────────────────────┐                   │
│   │  Non-voting replicas in ALL regions           │                   │
│   │  Read from any region: <2ms (stale by ~4.8s) │                   │
│   │  Write: coordinator commits to home region    │                   │
│   └─────────────────────────────────────────────┘                   │
└────────────────────────────────────────────────────────────────────┘
```

### SQL Schema

```sql
ALTER DATABASE netflix_accounts PRIMARY REGION "us-east1";
ALTER DATABASE netflix_accounts ADD REGION "us-west2";
ALTER DATABASE netflix_accounts ADD REGION "eu-west1";
ALTER DATABASE netflix_accounts ADD REGION "ap-southeast1";
ALTER DATABASE netflix_accounts SURVIVE REGION FAILURE;

-- GLOBAL: plans rarely change, read from anywhere instantly
CREATE TABLE plans (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name STRING NOT NULL UNIQUE,
    max_streams INT NOT NULL,
    max_resolution STRING NOT NULL,
    monthly_price_cents INT NOT NULL,
    annual_price_cents INT,
    features JSONB,
    active BOOL NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
) LOCALITY GLOBAL;

-- REGIONAL BY ROW: account pinned to user's home region
CREATE TABLE accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    email STRING NOT NULL UNIQUE,
    plan_id UUID NOT NULL REFERENCES plans(plan_id),
    status STRING NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','paused','cancelled','suspended')),
    payment_method_id UUID,
    billing_cycle_day INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    INDEX idx_email (email)
) LOCALITY REGIONAL BY ROW;

CREATE TABLE billing_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    account_id UUID NOT NULL REFERENCES accounts(account_id),
    event_type STRING NOT NULL, -- 'charge', 'refund', 'plan_change', 'payment_failed'
    amount_cents INT,
    currency STRING DEFAULT 'USD',
    plan_id UUID REFERENCES plans(plan_id),
    payment_processor_ref STRING,
    status STRING NOT NULL DEFAULT 'pending',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    INDEX idx_account_billing (account_id, created_at DESC)
) LOCALITY REGIONAL BY ROW;

-- Idempotency table to prevent double-charges
CREATE TABLE billing_idempotency (
    idempotency_key STRING PRIMARY KEY,
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    account_id UUID NOT NULL,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '24 hours',
    
    INDEX idx_expiry (expires_at) WHERE expires_at < now()
) LOCALITY REGIONAL BY ROW;
```

### Preventing Double-Charges (Serializable)

```sql
-- This is safe under Serializable isolation: no phantom reads
BEGIN;
    -- Check idempotency (SELECT FOR UPDATE unnecessary - Serializable handles it)
    SELECT result FROM billing_idempotency
    WHERE idempotency_key = 'charge_2024_01_user123';
    
    -- If no result, proceed with charge
    INSERT INTO billing_events (account_id, event_type, amount_cents, status)
    VALUES ('user123-uuid', 'charge', 1599, 'completed');
    
    INSERT INTO billing_idempotency (idempotency_key, account_id, result)
    VALUES ('charge_2024_01_user123', 'user123-uuid', '{"status":"ok"}');
COMMIT;
-- Under Serializable: if two concurrent transactions attempt this,
-- one will be retried automatically (40001 error → client retry)
```

---

## Use Case 3: Bose IoT Platform

### Problem
Bose manages millions of connected devices (headphones, speakers, soundbars) worldwide. Devices need firmware updates, configuration sync, and telemetry collection. Data must be stored near the device's region for low-latency communication while maintaining global visibility for analytics.

### Why CockroachDB
- **Geo-partitioning**: Device data pinned to device's region (GDPR compliance + low latency)
- **REGIONAL BY ROW**: Automatic data placement based on device location
- **Horizontal scale**: Add nodes as device fleet grows
- **SQL**: Familiar interface for analytics and reporting teams

### Scale Numbers
- 20M+ connected devices worldwide
- 4 regions (us-east, eu-west, ap-northeast, ap-southeast)
- 24 nodes (6 per region), ~80TB telemetry + device state
- Device heartbeat: <5ms read latency (regional)
- Firmware rollout: 100K devices/hour per region

### Architecture

```
                         Bose IoT Platform
┌──────────────────────────────────────────────────────────────────┐
│                                                                    │
│  Device Fleet                                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐         ┌──────┐ ┌──────┐           │
│  │EU Dev│ │EU Dev│ │EU Dev│  ...     │US Dev│ │AP Dev│           │
│  └──┬───┘ └──┬───┘ └──┬───┘         └──┬───┘ └──┬───┘           │
│     │        │        │                 │        │                 │
│     └────────┴────────┘                 │        │                 │
│              │                          │        │                 │
│     ┌────────▼─────────┐      ┌────────▼───┐ ┌──▼──────────┐    │
│     │ eu-west Gateway  │      │us-east GW  │ │ap-northeast │    │
│     │ (IoT Hub)        │      │            │ │   GW        │    │
│     └────────┬─────────┘      └────────┬───┘ └──┬──────────┘    │
│              │                          │        │                 │
│     ┌────────▼─────────┐      ┌────────▼───┐ ┌──▼──────────┐    │
│     │ CRDB eu-west     │      │CRDB us-east│ │CRDB ap-north│    │
│     │ (6 nodes)        │      │(6 nodes)   │ │(6 nodes)    │    │
│     │                  │      │            │ │             │    │
│     │ Leaseholder for  │      │Leaseholder │ │Leaseholder  │    │
│     │ EU devices HERE  │      │for US devs │ │for AP devs  │    │
│     └──────────────────┘      └────────────┘ └─────────────┘    │
│                                                                    │
│     Range: devices[EU-*]                                          │
│     ┌────────────────────────────────────────┐                    │
│     │ Leaseholder: eu-west (pinned)          │                    │
│     │ Replica 2:   us-east                   │                    │
│     │ Replica 3:   ap-northeast              │                    │
│     │ GDPR: EU data never leaves EU primary  │                    │
│     └────────────────────────────────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

### SQL Schema

```sql
ALTER DATABASE bose_iot PRIMARY REGION "us-east1";
ALTER DATABASE bose_iot ADD REGION "eu-west1";
ALTER DATABASE bose_iot ADD REGION "ap-northeast1";
ALTER DATABASE bose_iot ADD REGION "ap-southeast1";
ALTER DATABASE bose_iot SURVIVE REGION FAILURE;

CREATE TABLE devices (
    device_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL,
    serial_number STRING NOT NULL UNIQUE,
    product_model STRING NOT NULL,
    firmware_version STRING NOT NULL,
    owner_id UUID,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ,
    config JSONB NOT NULL DEFAULT '{}',
    status STRING NOT NULL DEFAULT 'active',
    
    INDEX idx_model_firmware (product_model, firmware_version),
    INDEX idx_owner (owner_id)
) LOCALITY REGIONAL BY ROW;

CREATE TABLE device_telemetry (
    device_id UUID NOT NULL,
    region crdb_internal_region NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    metric_type STRING NOT NULL,
    value_numeric DECIMAL,
    value_json JSONB,
    
    PRIMARY KEY (device_id, ts DESC),
    INDEX idx_metric_type (metric_type, ts DESC)
) LOCALITY REGIONAL BY ROW;

-- Firmware catalog: read globally, written by eng team
CREATE TABLE firmware_catalog (
    firmware_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_model STRING NOT NULL,
    version STRING NOT NULL,
    release_channel STRING NOT NULL DEFAULT 'stable',
    download_url STRING NOT NULL,
    checksum_sha256 STRING NOT NULL,
    release_notes STRING,
    released_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE (product_model, version)
) LOCALITY GLOBAL;

-- Firmware rollout tracking (regional - managed per-region)
CREATE TABLE firmware_rollouts (
    rollout_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    firmware_id UUID NOT NULL REFERENCES firmware_catalog(firmware_id),
    target_percentage INT NOT NULL DEFAULT 0,
    status STRING NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    INDEX idx_active_rollouts (status, region) WHERE status = 'in_progress'
) LOCALITY REGIONAL BY ROW;
```

### GDPR Compliance with Geo-Partitioning

```sql
-- Constrain EU data to EU region only (GDPR Article 44+)
ALTER PARTITION "eu-west1" OF INDEX devices@primary
    CONFIGURE ZONE USING
    constraints = '{+region=eu-west1: 3}',
    num_replicas = 3;

-- EU telemetry stays in EU
ALTER PARTITION "eu-west1" OF INDEX device_telemetry@primary
    CONFIGURE ZONE USING
    constraints = '{+region=eu-west1: 3}',
    num_replicas = 3;
```

---

## Use Case 4: Loom Video Platform

### Problem
Loom manages workspaces, video metadata, sharing permissions, and viewer analytics. Users collaborate across time zones; video links must resolve instantly worldwide. Workspace membership changes must be immediately consistent (remove user → instant loss of access).

### Why CockroachDB
- **Strong consistency for access control**: Permission revocation is immediate, not eventually consistent
- **Multi-region reads**: Video metadata served locally for instant playback start
- **GLOBAL tables**: Workspace/permission data readable from everywhere
- **CDC**: Stream events to search index, analytics pipeline

### Scale Numbers
- 25M+ registered users, 200M+ videos
- 3 regions (us-east, us-west, eu-west)
- 18 nodes, ~60TB metadata + analytics
- Video page load metadata: <5ms (p99)
- 100K+ concurrent video views

### Architecture

```
                         Loom Video Platform
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  Browser/App                                                      │
│     │                                                             │
│     ▼                                                             │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  API Gateway (per-region)                                 │    │
│  │  us-east / us-west / eu-west                              │    │
│  └──────────┬──────────────────────────────────┬────────────┘    │
│             │                                  │                  │
│    ┌────────▼─────────┐            ┌───────────▼──────────┐     │
│    │ Video Service     │            │ Workspace Service     │     │
│    │ (metadata, views) │            │ (teams, permissions)  │     │
│    └────────┬─────────┘            └───────────┬──────────┘     │
│             │                                  │                  │
│    ┌────────▼──────────────────────────────────▼──────────┐     │
│    │              CockroachDB Cluster                       │     │
│    │                                                       │     │
│    │  REGIONAL BY ROW: videos, view_events                 │     │
│    │  ┌─────────────────────────────────────────────────┐  │     │
│    │  │ Video 'abc' (creator in us-east):                │  │     │
│    │  │   Leaseholder → us-east, replicas in all 3      │  │     │
│    │  │   Read from us-east: 1ms                        │  │     │
│    │  │   Read from eu-west (follower read): 3ms        │  │     │
│    │  └─────────────────────────────────────────────────┘  │     │
│    │                                                       │     │
│    │  GLOBAL: workspaces, workspace_members, permissions   │     │
│    │  ┌─────────────────────────────────────────────────┐  │     │
│    │  │ Non-voting replicas everywhere                   │  │     │
│    │  │ Read from ANY region: <2ms                      │  │     │
│    │  │ Write: ~200ms (commits in home, replicates)     │  │     │
│    │  └─────────────────────────────────────────────────┘  │     │
│    └───────────────────────────────────────────────────────┘     │
│             │                                                     │
│             │ CDC Changefeeds                                     │
│             ▼                                                     │
│    ┌────────────────┐  ┌────────────────┐                        │
│    │ Kafka → Search │  │ Kafka → Analytcs│                       │
│    │ (Elasticsearch)│  │ (ClickHouse)   │                        │
│    └────────────────┘  └────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

### SQL Schema

```sql
ALTER DATABASE loom PRIMARY REGION "us-east1";
ALTER DATABASE loom ADD REGION "us-west2";
ALTER DATABASE loom ADD REGION "eu-west1";
ALTER DATABASE loom SURVIVE REGION FAILURE;

-- GLOBAL: workspace info readable everywhere instantly
CREATE TABLE workspaces (
    workspace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name STRING NOT NULL,
    slug STRING NOT NULL UNIQUE,
    plan STRING NOT NULL DEFAULT 'free',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
) LOCALITY GLOBAL;

CREATE TABLE workspace_members (
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id),
    user_id UUID NOT NULL,
    role STRING NOT NULL DEFAULT 'member' CHECK (role IN ('owner','admin','member','guest')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
) LOCALITY GLOBAL;

-- REGIONAL BY ROW: video metadata near creator
CREATE TABLE videos (
    video_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id),
    creator_id UUID NOT NULL,
    title STRING NOT NULL,
    description STRING,
    duration_ms INT,
    storage_url STRING NOT NULL,
    thumbnail_url STRING,
    visibility STRING NOT NULL DEFAULT 'workspace'
        CHECK (visibility IN ('private','workspace','link','public')),
    view_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    INDEX idx_workspace_videos (workspace_id, created_at DESC),
    INDEX idx_creator (creator_id, created_at DESC)
) LOCALITY REGIONAL BY ROW;

-- View events: regional, for analytics
CREATE TABLE view_events (
    event_id UUID DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    video_id UUID NOT NULL,
    viewer_id UUID,
    watched_ms INT NOT NULL DEFAULT 0,
    completed BOOL NOT NULL DEFAULT false,
    viewer_ip INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    PRIMARY KEY (region, event_id),
    INDEX idx_video_views (video_id, created_at DESC)
) LOCALITY REGIONAL BY ROW;

-- CDC changefeed for search indexing
CREATE CHANGEFEED FOR TABLE videos, workspaces
    INTO 'kafka://kafka-cluster:9092'
    WITH updated, resolved='10s',
         format=json,
         diff;
```

---

## Use Case 5: Hard Rock Digital Sports Betting

### Problem
Sports betting requires real-time bet placement with strong guarantees: no double-bet, accurate odds at time of placement, immediate balance deduction, and regulatory compliance (per-state licensing in US). Bets must settle within milliseconds of game events.

### Why CockroachDB
- **Serializable isolation**: Absolutely critical - a user cannot bet more than their balance, odds cannot be stale
- **Low-latency transactions**: Bet placement under 50ms local
- **Geo-partitioning**: State-specific data stays in regulated jurisdictions
- **Horizontal scaling**: Handle 100x spikes during major events (Super Bowl, World Cup)

### Scale Numbers
- 5M+ active bettors, 500K+ concurrent during peak events
- Peak: 50K bets/second during Super Bowl
- 3 regions (us-east, us-central, us-west)
- 27 nodes, ~30TB
- Bet placement p99: <50ms, settlement p99: <100ms

### Architecture

```
                    Hard Rock Digital - Sports Betting
┌──────────────────────────────────────────────────────────────────┐
│                                                                    │
│  Mobile/Web Client                                                 │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────────────────────────────────────────────┐      │
│  │  API Gateway + Rate Limiting + Geo-routing              │      │
│  └──────────┬──────────────────────────┬───────────────────┘      │
│             │                          │                           │
│  ┌──────────▼──────────┐   ┌──────────▼──────────────┐           │
│  │  Bet Placement       │   │  Odds Engine (in-memory) │           │
│  │  Service             │   │  (Redis + Kafka feed)    │           │
│  └──────────┬──────────┘   └──────────┬──────────────┘           │
│             │                          │                           │
│  ┌──────────▼──────────────────────────▼──────────────────┐      │
│  │              CockroachDB Cluster                         │      │
│  │                                                         │      │
│  │  Bet Placement Transaction (Serializable):              │      │
│  │  ┌───────────────────────────────────────────────────┐  │      │
│  │  │ 1. SELECT balance FROM wallets WHERE user_id=X    │  │      │
│  │  │    FOR UPDATE                                     │  │      │
│  │  │ 2. Verify: balance >= stake_amount                │  │      │
│  │  │ 3. SELECT odds FROM live_odds WHERE event_id=Y    │  │      │
│  │  │    (verify odds haven't moved beyond threshold)   │  │      │
│  │  │ 4. INSERT INTO bets (...)                         │  │      │
│  │  │ 5. UPDATE wallets SET balance = balance - stake   │  │      │
│  │  │ 6. INSERT INTO transactions (debit record)        │  │      │
│  │  │ COMMIT (parallel commits → 1 RTT)                 │  │      │
│  │  └───────────────────────────────────────────────────┘  │      │
│  │                                                         │      │
│  │  Range Layout:                                          │      │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐          │      │
│  │  │wallets     │ │bets (hot)  │ │live_odds   │          │      │
│  │  │range per   │ │range per   │ │range per   │          │      │
│  │  │10K users   │ │event       │ │sport       │          │      │
│  │  │(load-split)│ │(load-split)│ │(load-split)│          │      │
│  │  └────────────┘ └────────────┘ └────────────┘          │      │
│  └─────────────────────────────────────────────────────────┘      │
│                                                                    │
│  Settlement Pipeline:                                              │
│  Game Event → Kafka → Settlement Service → CRDB (batch update)    │
│  UPDATE bets SET status='won', payout=X WHERE event_id=Y          │
│  UPDATE wallets SET balance = balance + payout                     │
└──────────────────────────────────────────────────────────────────┘
```

### SQL Schema

```sql
ALTER DATABASE hardrock PRIMARY REGION "us-east1";
ALTER DATABASE hardrock ADD REGION "us-central1";
ALTER DATABASE hardrock ADD REGION "us-west2";
ALTER DATABASE hardrock SURVIVE REGION FAILURE;

-- Wallets: most contended table, careful range design
CREATE TABLE wallets (
    user_id UUID PRIMARY KEY,
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    balance_cents BIGINT NOT NULL DEFAULT 0 CHECK (balance_cents >= 0),
    bonus_cents BIGINT NOT NULL DEFAULT 0,
    currency STRING NOT NULL DEFAULT 'USD',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INT NOT NULL DEFAULT 1  -- optimistic locking fallback
) LOCALITY REGIONAL BY ROW;

-- Bets: high-write table, partitioned by region
CREATE TABLE bets (
    bet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    user_id UUID NOT NULL,
    event_id UUID NOT NULL,
    market_id UUID NOT NULL,
    selection STRING NOT NULL,
    odds_decimal DECIMAL(10,4) NOT NULL,
    stake_cents BIGINT NOT NULL CHECK (stake_cents > 0),
    potential_payout_cents BIGINT NOT NULL,
    status STRING NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','won','lost','void','cashed_out')),
    placed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    settled_at TIMESTAMPTZ,
    
    INDEX idx_user_bets (user_id, placed_at DESC),
    INDEX idx_event_bets (event_id, status),
    INDEX idx_settlement (status, event_id) WHERE status = 'open'
) LOCALITY REGIONAL BY ROW;

-- Live odds: frequently updated, GLOBAL for instant reads
CREATE TABLE live_odds (
    event_id UUID NOT NULL,
    market_id UUID NOT NULL,
    selection STRING NOT NULL,
    odds_decimal DECIMAL(10,4) NOT NULL,
    suspended BOOL NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, market_id, selection)
) LOCALITY GLOBAL;

-- Transaction ledger (immutable audit trail)
CREATE TABLE transactions (
    txn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region crdb_internal_region NOT NULL DEFAULT gateway_region()::crdb_internal_region,
    user_id UUID NOT NULL,
    type STRING NOT NULL CHECK (type IN ('deposit','withdrawal','bet_stake','bet_payout','bonus','void')),
    amount_cents BIGINT NOT NULL,
    balance_after_cents BIGINT NOT NULL,
    reference_id UUID,  -- bet_id, deposit_id, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    INDEX idx_user_txns (user_id, created_at DESC)
) LOCALITY REGIONAL BY ROW;

-- Bet placement with guaranteed consistency
-- This entire block is atomic under Serializable isolation
CREATE OR REPLACE FUNCTION place_bet(
    p_user_id UUID,
    p_event_id UUID,
    p_market_id UUID,
    p_selection STRING,
    p_stake_cents BIGINT
) RETURNS UUID AS $$
DECLARE
    v_balance BIGINT;
    v_odds DECIMAL(10,4);
    v_suspended BOOL;
    v_payout BIGINT;
    v_bet_id UUID;
BEGIN
    -- Lock wallet row
    SELECT balance_cents INTO v_balance
    FROM wallets WHERE user_id = p_user_id FOR UPDATE;
    
    IF v_balance < p_stake_cents THEN
        RAISE EXCEPTION 'insufficient_balance';
    END IF;
    
    -- Check odds (GLOBAL table - instant read)
    SELECT odds_decimal, suspended INTO v_odds, v_suspended
    FROM live_odds
    WHERE event_id = p_event_id AND market_id = p_market_id AND selection = p_selection;
    
    IF v_suspended THEN
        RAISE EXCEPTION 'market_suspended';
    END IF;
    
    v_payout := (p_stake_cents * v_odds)::BIGINT;
    
    -- Place bet
    INSERT INTO bets (user_id, event_id, market_id, selection, odds_decimal,
                      stake_cents, potential_payout_cents)
    VALUES (p_user_id, p_event_id, p_market_id, p_selection, v_odds,
            p_stake_cents, v_payout)
    RETURNING bet_id INTO v_bet_id;
    
    -- Deduct balance
    UPDATE wallets SET balance_cents = balance_cents - p_stake_cents,
                       updated_at = now()
    WHERE user_id = p_user_id;
    
    -- Record transaction
    INSERT INTO transactions (user_id, type, amount_cents, balance_after_cents, reference_id)
    VALUES (p_user_id, 'bet_stake', -p_stake_cents, v_balance - p_stake_cents, v_bet_id);
    
    RETURN v_bet_id;
END;
$$ LANGUAGE PLpgSQL;
```

---

## Replication Deep Dive

### Raft Consensus for Every Range

```
Write Path (through Raft):
┌──────────────────────────────────────────────────────────────────┐
│                                                                    │
│  Client                                                            │
│    │                                                               │
│    │ SQL: INSERT INTO orders VALUES (...)                          │
│    ▼                                                               │
│  Gateway Node (any node)                                           │
│    │                                                               │
│    │ Route to leaseholder of target range                          │
│    ▼                                                               │
│  Leaseholder (= Raft Leader)                                       │
│    │                                                               │
│    ├──► 1. Propose entry to Raft log                               │
│    │                                                               │
│    ├──► 2. Send AppendEntries RPC to followers (parallel)          │
│    │       ┌──────────────────────────────────────┐                │
│    │       │  Follower 1: receives, persists,     │                │
│    │       │              sends ACK               │                │
│    │       │  Follower 2: receives, persists,     │                │
│    │       │              sends ACK               │                │
│    │       └──────────────────────────────────────┘                │
│    │                                                               │
│    ├──► 3. Quorum achieved (2/3 ACKs including leader)             │
│    │                                                               │
│    ├──► 4. Commit entry, apply to state machine (Pebble)           │
│    │                                                               │
│    └──► 5. Respond to client: SUCCESS                              │
│                                                                    │
│  Latency breakdown (same region, 3 AZs):                          │
│    Propose + persist on leader: ~0.5ms                             │
│    Network RTT to follower:    ~1-2ms (cross-AZ)                   │
│    Follower persist + ACK:     ~0.5ms                              │
│    Total:                      ~2-4ms                              │
│                                                                    │
│  Cross-region quorum:                                              │
│    Network RTT:                ~30-80ms                             │
│    Total:                      ~40-100ms                           │
└──────────────────────────────────────────────────────────────────┘

Read Path (Leaseholder Serves):
┌──────────────────────────────────────────────────────────────────┐
│  Client → Gateway → Leaseholder → Read from Pebble → Respond     │
│                                                                    │
│  No Raft consensus needed for reads!                               │
│  Lease guarantees: only leaseholder can serve reads                │
│  Lease duration: 9 seconds (renewed at 2/3 = 6s)                  │
│                                                                    │
│  Latency: <1ms if gateway = leaseholder node                      │
│           ~1-3ms cross-AZ hop to leaseholder                       │
│           ~30-80ms cross-region hop (unless follower reads)        │
└──────────────────────────────────────────────────────────────────┘
```

### Leaseholder Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Leaseholder Properties:                                         │
│                                                                   │
│  • One leaseholder per range (always)                            │
│  • Co-located with Raft leader (usually, not guaranteed)         │
│  • Serves ALL reads for the range                                │
│  • Proposes ALL writes for the range                             │
│  • Holds a time-based lease (epoch-based in CRDB)                │
│  • Lease transfers: ~10ms (cheap, happens during rebalancing)    │
│                                                                   │
│  Leaseholder Preferences:                                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ ALTER TABLE orders CONFIGURE ZONE USING                     │ │
│  │   lease_preferences = '[[+region=us-east1]]';               │ │
│  │                                                             │ │
│  │ Effect: system moves leaseholder to us-east1 node           │ │
│  │         reads from us-east1 are LOCAL (~1ms)                │ │
│  │         reads from other regions cross-region (~50ms)       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  REGIONAL BY ROW automates this per-row:                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Row with region='us-east1' → leaseholder in us-east1        │ │
│  │ Row with region='eu-west1' → leaseholder in eu-west1        │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Region Topology Patterns

```
┌─────────────────────────────────────────────────────────────────┐
│  Pattern 1: SURVIVE ZONE FAILURE (default)                       │
│  ─────────────────────────────────────────                       │
│  Replicas: 3 (one per AZ within a region)                       │
│  Quorum: 2/3                                                     │
│  Survives: 1 AZ failure                                          │
│  Write latency: ~2-4ms (intra-region)                            │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │  AZ-a    │  │  AZ-b    │  │  AZ-c    │                       │
│  │(Replica) │  │(Replica) │  │(Replica) │                       │
│  │Leaseholdr│  │Follower  │  │Follower  │                       │
│  └──────────┘  └──────────┘  └──────────┘                       │
│       us-east-1 region                                            │
├─────────────────────────────────────────────────────────────────┤
│  Pattern 2: SURVIVE REGION FAILURE                               │
│  ─────────────────────────────────────────                       │
│  Replicas: 5 (spread across 3+ regions)                          │
│  Quorum: 3/5                                                     │
│  Survives: 1 entire region failure                               │
│  Write latency: ~50-150ms (cross-region quorum)                  │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │us-east   │  │us-central│  │us-west   │                       │
│  │(2 repls) │  │(2 repls) │  │(1 repl)  │                       │
│  │Leaseholdr│  │Followers │  │Follower  │                       │
│  └──────────┘  └──────────┘  └──────────┘                       │
│                                                                   │
│  Quorum must span 2 regions → cross-region RTT required          │
├─────────────────────────────────────────────────────────────────┤
│  Pattern 3: GLOBAL Tables                                        │
│  ─────────────────────────────────────────                       │
│  Non-voting replicas in every region                             │
│  Reads: local (<2ms from any region)                             │
│  Writes: home region only (~200ms for global propagation)        │
│  Use for: reference data, configs, rarely-changing data          │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │us-east   │  │eu-west   │  │ap-south  │                       │
│  │(Voting   │  │(Non-vote │  │(Non-vote │                       │
│  │ Leaseh.) │  │ Replica) │  │ Replica) │                       │
│  └──────────┘  └──────────┘  └──────────┘                       │
│                                                                   │
│  Reads use closed timestamps: guaranteed consistent              │
│  but may be up to ~4.8s stale (closed_timestamp interval)        │
└─────────────────────────────────────────────────────────────────┘
```

### Follower Reads

```sql
-- Bounded staleness: read from closest replica (follower or leaseholder)
-- Guaranteed to be no more than 4.8s stale
SELECT * FROM orders
    AS OF SYSTEM TIME follower_read_timestamp()
    WHERE order_id = 'abc-123';

-- Exact staleness: useful for analytics
SELECT count(*) FROM view_events
    AS OF SYSTEM TIME '-10s'
    WHERE video_id = 'xyz';

-- Latency comparison:
-- Strong read (must go to leaseholder):
--   Same region:  ~2ms
--   Cross-region: ~50-100ms
--
-- Follower read (nearest replica):
--   Always local: ~2ms (regardless of leaseholder location)
```

### Non-Voting Replicas

```
Voting vs Non-Voting Replicas:
┌────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Voting Replicas (participate in Raft quorum):                  │
│  • Can become leader/leaseholder                                │
│  • Required for write quorum                                    │
│  • Affect write latency (quorum must be achieved)               │
│                                                                  │
│  Non-Voting Replicas (receive Raft log, don't vote):            │
│  • Cannot become leader                                         │
│  • Do NOT affect write latency                                  │
│  • CAN serve follower reads                                     │
│  • Used by GLOBAL tables for fast local reads                   │
│  • Used for async replication to distant regions                │
│                                                                  │
│  Example: Table with home region us-east, readers in ap-south   │
│                                                                  │
│  us-east:    [Voting] [Voting] [Voting]  ← quorum here (~4ms)  │
│  eu-west:    [Non-Voting]                ← follower reads (~2ms)│
│  ap-south:   [Non-Voting]                ← follower reads (~2ms)│
│                                                                  │
│  Write: still fast (quorum in us-east only)                     │
│  Read:  fast everywhere (non-voting replicas serve locally)     │
└────────────────────────────────────────────────────────────────┘
```

---

## Scalability

### Range-Based Sharding

```
Automatic Range Splitting:
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  Table: orders (100GB)                                           │
│                                                                   │
│  Automatic split at 512MB → ~200 ranges                          │
│                                                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐     ┌─────────┐          │
│  │Range 1  │ │Range 2  │ │Range 3  │ ... │Range 200│          │
│  │[A - D)  │ │[D - G)  │ │[G - K)  │     │[X - Z]  │          │
│  │512MB    │ │512MB    │ │512MB    │     │312MB    │          │
│  │Node 1   │ │Node 4   │ │Node 2   │     │Node 7   │          │
│  └─────────┘ └─────────┘ └─────────┘     └─────────┘          │
│                                                                   │
│  Split triggers:                                                  │
│  • Size-based: range exceeds 512MB (configurable)                │
│  • Load-based: range exceeds QPS threshold                       │
│  • Manual: ALTER TABLE ... SPLIT AT (value)                      │
│                                                                   │
│  Merge triggers:                                                  │
│  • Both adjacent ranges < 128MB (512MB * 0.25)                   │
│  • Both ranges have low QPS                                      │
│                                                                   │
│  Rebalancing:                                                    │
│  • Replicas moved between nodes to equalize disk/CPU/QPS         │
│  • Lease transfers to balance read load                          │
│  • Constraint-aware: respects locality and zone configs          │
└─────────────────────────────────────────────────────────────────┘
```

### Distributed SQL Query Execution (DistSQL)

```
Query: SELECT region, count(*) FROM orders WHERE status='active' GROUP BY region

┌──────────────────────────────────────────────────────────────────┐
│  Gateway Node (receives query)                                    │
│     │                                                             │
│     ▼                                                             │
│  Optimizer: creates physical plan, pushes computation to data     │
│     │                                                             │
│     ├─────────────────────┬─────────────────────┐                 │
│     ▼                     ▼                     ▼                 │
│  ┌──────────┐      ┌──────────┐          ┌──────────┐           │
│  │ Node 1   │      │ Node 4   │          │ Node 7   │           │
│  │ TableRdr │      │ TableRdr │          │ TableRdr │           │
│  │ Filter   │      │ Filter   │          │ Filter   │           │
│  │ status=  │      │ status=  │          │ status=  │           │
│  │ 'active' │      │ 'active' │          │ 'active' │           │
│  │ LocalAgg │      │ LocalAgg │          │ LocalAgg │           │
│  └────┬─────┘      └────┬─────┘          └────┬─────┘           │
│       │                  │                     │                  │
│       └──────────────────┼─────────────────────┘                  │
│                          ▼                                        │
│                   ┌──────────┐                                    │
│                   │ Gateway  │                                    │
│                   │ FinalAgg │                                    │
│                   │ Response │                                    │
│                   └──────────┘                                    │
│                                                                    │
│  Key insight: filter + partial aggregation pushed to each node    │
│  Only aggregated results flow over network (minimal data movement)│
└──────────────────────────────────────────────────────────────────┘
```

### Multi-Region Data Patterns

```
┌─────────────────────────────────────────────────────────────────┐
│  1. REGIONAL BY ROW                                              │
│     ─────────────────                                            │
│     Each row has a `region` column controlling placement         │
│     Leaseholder co-located with data's region                    │
│     Best for: user data, orders, anything with regional affinity │
│                                                                   │
│     Write: ~4ms (local quorum) or ~100ms (region survival)       │
│     Read:  ~2ms (local leaseholder)                              │
│                                                                   │
│  2. REGIONAL BY TABLE                                            │
│     ──────────────────                                           │
│     Entire table pinned to one region                            │
│     Best for: tables accessed primarily from one region          │
│                                                                   │
│     Write: ~4ms (from home region)                               │
│     Read:  ~2ms (from home), ~80ms (cross-region)                │
│                                                                   │
│  3. GLOBAL                                                       │
│     ──────                                                       │
│     Non-voting replicas everywhere, reads from any region        │
│     Best for: reference data, configs, lookup tables             │
│                                                                   │
│     Write: ~200ms (must propagate closed timestamp)              │
│     Read:  ~2ms (from any region, uses closed timestamps)        │
└─────────────────────────────────────────────────────────────────┘
```

### Change Data Capture (CDC)

```sql
-- Enterprise changefeed to Kafka
CREATE CHANGEFEED FOR TABLE orders, bets
    INTO 'kafka://broker1:9092,broker2:9092'
    WITH updated,
         resolved = '10s',
         format = avro,
         confluent_schema_registry = 'http://schema-registry:8081',
         min_checkpoint_frequency = '30s';

-- Core changefeed (free) to cloud storage
CREATE CHANGEFEED FOR TABLE orders
    INTO 's3://my-bucket/cdc?AUTH=implicit'
    WITH resolved = '1m',
         format = json;

-- Webhook sink
CREATE CHANGEFEED FOR TABLE orders
    INTO 'webhook-https://my-service.com/cdc'
    WITH updated, diff;
```

---

## Production Setup

### Node Sizing and Topology

```
Recommended per-node sizing:
┌────────────────────────────────────────────────────────────┐
│  Workload      │ vCPUs │ RAM    │ Storage       │ Nodes   │
│────────────────┼───────┼────────┼───────────────┼─────────│
│  Light         │ 4     │ 16 GB  │ 200 GB SSD    │ 3       │
│  Standard      │ 8     │ 32 GB  │ 500 GB SSD    │ 3-9     │
│  Heavy OLTP    │ 16    │ 64 GB  │ 1 TB NVMe     │ 9-27    │
│  Multi-region  │ 16    │ 64 GB  │ 1 TB NVMe     │ 9+ (3/r)│
└────────────────────────────────────────────────────────────┘

Rules of thumb:
• RAM: 4 GB per vCPU minimum
• Storage: 5-10x RAM, NVMe preferred
• Minimum 3 nodes (1 per AZ for zone survival)
• Minimum 9 nodes for region survival (3 regions × 3 nodes)
• Never exceed 10TB per node
• Plan for 50% headroom (peak load)
```

### Locality Flags

```bash
# Start nodes with locality hierarchy
cockroach start \
  --locality=region=us-east1,zone=us-east1-b,rack=rack-42 \
  --store=path=/data/cockroach \
  --advertise-addr=node1.example.com:26257 \
  --join=node1:26257,node2:26257,node3:26257 \
  --cache=.25 \
  --max-sql-memory=.25

# Locality hierarchy (most general → most specific):
# region → zone → rack → node
# Used for: replica placement, leaseholder preferences, DistSQL locality
```

### Monitoring

```
┌─────────────────────────────────────────────────────────────────┐
│  DB Console (built-in):                                          │
│  • http://node:8080                                              │
│  • Cluster health, range distribution, slow queries              │
│  • Statement statistics, transaction contention                  │
│  • Hot ranges, replication status                                │
│                                                                   │
│  Prometheus Integration:                                         │
│  • Endpoint: http://node:8080/_status/vars                       │
│  • Key metrics:                                                  │
│    - cr_node_sql_query_count (QPS)                               │
│    - cr_node_sql_service_latency_p99                             │
│    - cr_store_range_count                                        │
│    - cr_store_livebytes (data size)                              │
│    - cr_node_txn_restarts (contention signal)                    │
│    - cr_store_raft_leader_not_leaseholder_count                  │
│    - cr_admission_admitted (admission control)                   │
│                                                                   │
│  Alerting (critical):                                            │
│  • Node down > 5 minutes                                         │
│  • Liveness expiration approaching                               │
│  • Raft log behind > 1000 entries                                │
│  • Txn restart rate > 5%                                         │
│  • Storage utilization > 70%                                     │
│  • Certificate expiry < 30 days                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Backup and Restore

```sql
-- Full cluster backup (enterprise)
BACKUP INTO 's3://backups/cluster?AUTH=implicit'
    WITH revision_history;

-- Incremental backup (builds on latest full)
BACKUP INTO LATEST IN 's3://backups/cluster?AUTH=implicit'
    WITH revision_history;

-- Scheduled backups
CREATE SCHEDULE daily_backup FOR BACKUP INTO
    's3://backups/cluster?AUTH=implicit'
    WITH revision_history
    RECURRING '@daily'
    FULL BACKUP '@weekly'
    WITH SCHEDULE OPTIONS first_run = 'now';

-- Point-in-time restore
RESTORE FROM LATEST IN 's3://backups/cluster?AUTH=implicit'
    AS OF SYSTEM TIME '2024-01-15 10:30:00';

-- Table-level restore
RESTORE TABLE orders FROM LATEST IN 's3://backups/cluster?AUTH=implicit'
    WITH into_db = 'recovery_db';
```

### Online Schema Changes

```sql
-- All schema changes are online (no locks, no downtime)
-- CockroachDB uses a multi-version schema change protocol

-- Add column (instant, backfill happens async)
ALTER TABLE orders ADD COLUMN priority INT DEFAULT 0;

-- Add index (built online, no read/write blocking)
CREATE INDEX CONCURRENTLY idx_priority ON orders(priority DESC)
    WHERE status = 'active';

-- Monitor schema change progress
SELECT * FROM [SHOW JOBS] WHERE job_type = 'SCHEMA CHANGE';
```

### SQL Optimization

```sql
-- EXPLAIN ANALYZE: actual execution stats
EXPLAIN ANALYZE SELECT * FROM orders
    WHERE customer_id = 'uuid-here' AND status = 'active'
    ORDER BY placed_at DESC LIMIT 10;

-- Key things to look for:
-- • Full table scans (missing index)
-- • Cross-range lookups (consider index covering)
-- • Network hops (DistSQL sending data between nodes)
-- • Contention time (lock waits)

-- Statement diagnostics bundle
EXPLAIN ANALYZE (DEBUG) SELECT ...;
-- Downloads a bundle with: opt plan, DistSQL plan, trace, stats

-- Index recommendations
SELECT * FROM [SHOW INDEX RECOMMENDATIONS] WHERE table_name = 'orders';

-- Contention analysis
SELECT * FROM crdb_internal.cluster_contention_events
    ORDER BY count DESC LIMIT 20;
```

---

## Latency Reference Table

| Operation | Same AZ | Cross-AZ | Cross-Region |
|-----------|---------|----------|--------------|
| Strong read (leaseholder local) | <1ms | 1-3ms | 50-100ms |
| Follower read | <1ms | 1-3ms | 1-3ms |
| GLOBAL table read | <2ms | <2ms | <2ms |
| Write (zone survival) | 1-2ms | 2-5ms | N/A |
| Write (region survival) | N/A | N/A | 50-150ms |
| GLOBAL table write | N/A | N/A | 150-300ms |
| Distributed txn (2 ranges, local) | 3-8ms | 5-15ms | 100-300ms |
| Lease transfer | ~10ms | ~10ms | ~10ms |
| Range split | ~100ms | ~100ms | ~100ms |
| Snapshot (rebalance 512MB range) | 1-5s | 2-10s | 10-60s |
