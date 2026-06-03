# PostgreSQL - Real World Use Cases & Production Guide

## Table of Contents
1. [Use Case 1: Stripe Payment Processing](#use-case-1-stripe-payment-processing)
2. [Use Case 2: Instagram Social Graph](#use-case-2-instagram-social-graph)
3. [Use Case 3: GitLab Repository Metadata](#use-case-3-gitlab-repository-metadata)
4. [Use Case 4: Notion Workspace Data](#use-case-4-notion-workspace-data)
5. [Use Case 5: Uber Trip Data (Pre-Migration)](#use-case-5-uber-trip-data)
6. [Replication Deep Dive](#replication-deep-dive)
7. [Scalability Patterns](#scalability-patterns)
8. [Production Setup](#production-setup)
9. [Core Concepts](#core-concepts)

---

## Use Case 1: Stripe Payment Processing

### Why PostgreSQL?
- ACID guarantees for financial transactions (money can't disappear)
- Strong consistency for payment state machines
- Rich data types (JSONB for metadata, arrays for tags)
- Mature ecosystem for auditing and compliance

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Stripe Payment Flow                          │
└─────────────────────────────────────────────────────────────────────┘

  Customer ──▶ API Gateway ──▶ Payment Service ──▶ PostgreSQL Primary
                                    │                      │
                                    │              ┌───────┴───────┐
                                    │              │               │
                                    ▼              ▼               ▼
                              Idempotency     Sync Replica    Sync Replica
                              Check (Redis)    (Same AZ)     (Cross AZ)
                                    │
                                    ▼
                            ┌──────────────┐
                            │  Card Network │
                            │  (Visa/MC)    │
                            └──────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │ Webhook/Event │
                            │   (Kafka)     │
                            └──────────────┘

Write Path (Payment Creation):
┌──────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│  Client  │───▶│   PgBouncer  │───▶│  PG Primary     │───▶│  WAL Shipped │
│  Request │    │  (Pool: 500) │    │  (fsync=on)     │    │  to Replicas │
└──────────┘    └──────────────┘    └─────────────────┘    └──────────────┘

Read Path (Payment Status):
┌──────────┐    ┌──────────────┐    ┌─────────────────┐
│  Client  │───▶│   PgBouncer  │───▶│  Read Replica   │
│  Query   │    │  (read pool) │    │  (lag < 100ms)  │
└──────────┘    └──────────────┘    └─────────────────┘
```

### Schema Design

```sql
-- Core payments table (partitioned by created_at month)
CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    amount          BIGINT NOT NULL,              -- cents to avoid floating point
    currency        VARCHAR(3) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    customer_id     UUID NOT NULL REFERENCES customers(id),
    merchant_id     UUID NOT NULL REFERENCES merchants(id),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_status CHECK (status IN ('pending','processing','succeeded','failed','refunded'))
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE payments_2024_01 PARTITION OF payments
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Payment state transitions (audit trail)
CREATE TABLE payment_events (
    id          BIGSERIAL,
    payment_id  UUID NOT NULL,
    from_status VARCHAR(20),
    to_status   VARCHAR(20) NOT NULL,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (created_at, id)
) PARTITION BY RANGE (created_at);

-- Indexes for common access patterns
CREATE INDEX idx_payments_customer ON payments (customer_id, created_at DESC);
CREATE INDEX idx_payments_merchant ON payments (merchant_id, created_at DESC);
CREATE INDEX idx_payments_status ON payments (status) WHERE status IN ('pending', 'processing');
CREATE INDEX idx_payments_idempotency ON payments (idempotency_key);
```

### Query Patterns

```sql
-- Create payment (with idempotency)
INSERT INTO payments (idempotency_key, amount, currency, customer_id, merchant_id, metadata)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (idempotency_key) DO NOTHING
RETURNING *;

-- Update payment status (optimistic locking)
UPDATE payments 
SET status = $1, updated_at = NOW()
WHERE id = $2 AND status = $3
RETURNING *;

-- Get merchant revenue (uses partition pruning)
SELECT DATE_TRUNC('day', created_at) AS day,
       SUM(amount) AS total_amount,
       COUNT(*) AS transaction_count
FROM payments
WHERE merchant_id = $1
  AND created_at >= $2 AND created_at < $3
  AND status = 'succeeded'
GROUP BY 1 ORDER BY 1;
```

### Scale Handling
- **Throughput**: ~50,000 TPS per primary node with connection pooling
- **Sharding**: By merchant_id using Citus for horizontal scaling
- **Connection Pooling**: PgBouncer in transaction mode (6,000 clients → 500 PG connections)
- **Partitioning**: Monthly partitions, auto-created via pg_partman

### Production Config
```ini
# postgresql.conf for payment workload
shared_buffers = 32GB                 # 25% of 128GB RAM
effective_cache_size = 96GB           # 75% of RAM
work_mem = 256MB
maintenance_work_mem = 2GB
wal_level = replica
synchronous_commit = on               # CRITICAL for payments
synchronous_standby_names = 'ANY 1 (replica1, replica2)'
max_connections = 500
max_wal_size = 8GB
checkpoint_completion_target = 0.9
random_page_cost = 1.1                # SSD
effective_io_concurrency = 200        # SSD
```

---

## Use Case 2: Instagram Social Graph

### Why PostgreSQL?
- Handles complex relational queries (followers, following, mutual friends)
- Efficient for graph-like traversals with proper indexing
- JSONB for flexible post metadata
- Sharding via custom middleware (later Vitess-inspired)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Instagram Data Architecture                       │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────┐
                    │   Application Layer   │
                    │   (Django/Python)     │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Routing Layer       │
                    │   (Shard Router)      │
                    │   user_id % N_shards  │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   PG Shard 1    │  │   PG Shard 2    │  │   PG Shard 3    │
│  (users 0-999)  │  │ (users 1K-1999) │  │ (users 2K-2999) │
│                 │  │                 │  │                 │
│  Primary        │  │  Primary        │  │  Primary        │
│    ├─Replica 1  │  │    ├─Replica 1  │  │    ├─Replica 1  │
│    └─Replica 2  │  │    └─Replica 2  │  │    └─Replica 2  │
└─────────────────┘  └─────────────────┘  └─────────────────┘

Feed Generation:
┌──────┐    ┌───────────┐    ┌──────────┐    ┌──────────────┐
│ User │───▶│ Feed Svc  │───▶│ Memcached│───▶│ PG (fanout   │
│      │    │           │    │ (L1 Cache)│   │  on read)    │
└──────┘    └───────────┘    └──────────┘    └──────────────┘

Like Counter:
┌──────┐    ┌───────────┐    ┌──────────┐    ┌──────────────┐
│ Like │───▶│ Like Svc  │───▶│  Redis   │───▶│ PG (async    │
│ Tap  │    │           │    │ (counter)│    │  persist)    │
└──────┘    └───────────┘    └──────────┘    └──────────────┘
```

### Schema Design

```sql
-- Users table (sharded by user_id)
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    username    VARCHAR(30) UNIQUE NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    bio         TEXT,
    avatar_url  VARCHAR(500),
    is_private  BOOLEAN DEFAULT FALSE,
    follower_count  INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    post_count      INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Follows (sharded by follower_id for "who do I follow?" queries)
CREATE TABLE follows (
    follower_id BIGINT NOT NULL,
    following_id BIGINT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id)
);
CREATE INDEX idx_follows_following ON follows (following_id, follower_id);

-- Posts (sharded by user_id)
CREATE TABLE posts (
    id          BIGSERIAL,
    user_id     BIGINT NOT NULL,
    media_url   VARCHAR(500) NOT NULL,
    caption     TEXT,
    location    JSONB,
    like_count  INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, id)
);
CREATE INDEX idx_posts_created ON posts (user_id, created_at DESC);

-- Likes (sharded by post owner's user_id)
CREATE TABLE likes (
    user_id     BIGINT NOT NULL,
    post_id     BIGINT NOT NULL,
    post_owner_id BIGINT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (post_owner_id, post_id, user_id)
);
```

### Scale Numbers
- **2B+ users**, **500M+ daily active**
- **~12,000 PostgreSQL shards** (as of public talks)
- **Shard key**: user_id % num_shards
- **Each shard**: Primary + 2 replicas, ~500GB data
- **Read:Write ratio**: 100:1

---

## Use Case 3: GitLab Repository Metadata

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     GitLab Database Architecture                     │
└─────────────────────────────────────────────────────────────────────┘

┌────────────┐     ┌──────────────┐     ┌─────────────────────────────┐
│  Rails App │────▶│   PgBouncer  │────▶│     PostgreSQL Primary       │
│  (Puma)    │     │  (per-node)  │     │     (Main Database)          │
└────────────┘     └──────────────┘     │                             │
                                        │  Tables: projects, users,    │
                                        │  merge_requests, issues,     │
                                        │  pipelines, ci_builds...     │
                                        └──────────────┬──────────────┘
                                                       │
                                    ┌──────────────────┼──────────────────┐
                                    │                  │                  │
                                    ▼                  ▼                  ▼
                             ┌────────────┐    ┌────────────┐    ┌────────────┐
                             │  Replica 1 │    │  Replica 2 │    │  Replica 3 │
                             │  (API read)│    │ (Sidekiq)  │    │ (CI reads) │
                             └────────────┘    └────────────┘    └────────────┘

Database Decomposition (GitLab's approach):
┌──────────────────────────────────────────────────────┐
│                   Main Database                       │
│  (projects, users, namespaces, merge_requests)       │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│                   CI Database                         │
│  (ci_builds, ci_pipelines, ci_stages, ci_runners)    │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│               Embedding Database                      │
│  (vertex_embeddings for AI features)                  │
└──────────────────────────────────────────────────────┘

Patroni HA Setup:
┌─────────┐   ┌─────────┐   ┌─────────┐
│  etcd1  │   │  etcd2  │   │  etcd3  │
└────┬────┘   └────┬────┘   └────┬────┘
     └──────────────┼──────────────┘
                    │
     ┌──────────────┼──────────────┐
     ▼              ▼              ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│Patroni 1│   │Patroni 2│   │Patroni 3│
│(Primary)│   │(Replica) │   │(Replica) │
└─────────┘   └─────────┘   └─────────┘
```

### Key Design Decisions
- **Database decomposition**: Split CI tables into separate DB cluster (largest tables)
- **Loose foreign keys**: Rails-level FK tracking instead of DB-level for CI DB split
- **Background migrations**: Long-running data migrations that don't block deploys
- **Partitioned tables**: `ci_builds` partitioned by `partition_id`

### Scale Numbers
- **~6TB primary database** (GitLab.com)
- **~500 tables** in main database
- **Peak**: ~15,000 TPS
- **Largest table**: `ci_builds` (billions of rows, partitioned)

---

## Use Case 4: Notion Workspace Data

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Notion's Block-Based Storage                      │
└─────────────────────────────────────────────────────────────────────┘

Data Model: Everything is a Block
┌─────────────────────────────────────────────┐
│  Workspace                                   │
│  └── Page (Block type: page)                 │
│      ├── Heading (Block type: heading)       │
│      ├── Paragraph (Block type: text)        │
│      ├── Table (Block type: collection)      │
│      │   ├── Row 1 (Block type: row)         │
│      │   └── Row 2 (Block type: row)         │
│      └── Subpage (Block type: page)          │
│          └── ... (recursive)                 │
└─────────────────────────────────────────────┘

Architecture:
┌──────────┐    ┌──────────────┐    ┌────────────────────────────────┐
│  Client  │───▶│  API Server  │───▶│       PostgreSQL (Sharded)      │
│  (React) │    │  (Node.js)   │    │                                │
└──────────┘    └──────────────┘    │  Shard Key: workspace_id       │
      ▲                │            │                                │
      │                ▼            │  ┌────────────────────────┐    │
      │         ┌────────────┐     │  │ blocks                  │    │
      │         │  Redis     │     │  │ ├── id (UUID)           │    │
      │         │  (Cache +  │     │  │ ├── workspace_id        │    │
      └─────────│  Pub/Sub)  │     │  │ ├── parent_id           │    │
   Real-time    └────────────┘     │  │ ├── type                │    │
   updates via                     │  │ ├── properties (JSONB)  │    │
   WebSocket                       │  │ ├── content (JSONB)     │    │
                                   │  │ └── alive (soft delete) │    │
                                   │  └────────────────────────┘    │
                                   └────────────────────────────────┘

Write Path (User types in a block):
┌────────┐   ┌────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐
│ Client │──▶│Websock │──▶│ OT/CRDT  │──▶│  Write  │──▶│  PG      │
│ Input  │   │ Server │   │  Merge   │   │  Queue  │   │ Primary  │
└────────┘   └────────┘   └──────────┘   └─────────┘   └──────────┘
                                                              │
                                                              ▼
                                                        ┌──────────┐
                                                        │ Broadcast│
                                                        │ to other │
                                                        │ clients  │
                                                        └──────────┘
```

### Schema Design

```sql
-- Blocks table (core of Notion's data model)
CREATE TABLE blocks (
    id              UUID NOT NULL,
    workspace_id    UUID NOT NULL,
    parent_id       UUID,
    type            VARCHAR(50) NOT NULL,
    properties      JSONB DEFAULT '{}',   -- title, checked, color, etc.
    content         JSONB DEFAULT '{}',   -- rich text content
    format          JSONB DEFAULT '{}',   -- display formatting
    child_ids       UUID[] DEFAULT '{}',  -- ordered children
    alive           BOOLEAN DEFAULT TRUE,
    version         INTEGER DEFAULT 1,
    created_by      UUID NOT NULL,
    last_edited_by  UUID NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (workspace_id, id)
);

-- Efficient tree traversal
CREATE INDEX idx_blocks_parent ON blocks (workspace_id, parent_id) WHERE alive = TRUE;
CREATE INDEX idx_blocks_type ON blocks (workspace_id, type) WHERE alive = TRUE;
-- GIN index for JSONB property searches
CREATE INDEX idx_blocks_properties ON blocks USING GIN (properties jsonb_path_ops);

-- Permissions (workspace-level sharding)
CREATE TABLE permissions (
    block_id        UUID NOT NULL,
    workspace_id    UUID NOT NULL,
    user_id         UUID,
    role            VARCHAR(20) NOT NULL, -- 'editor', 'viewer', 'commenter'
    PRIMARY KEY (workspace_id, block_id, user_id)
);
```

### Scale Numbers
- **~30M+ users**, billions of blocks
- Sharded by workspace_id
- Aggressive use of JSONB for schema flexibility
- Version column for OT conflict resolution

---

## Use Case 5: Uber Trip Data

### Why They Used PostgreSQL (and why they moved away)

```
┌─────────────────────────────────────────────────────────────────────┐
│              Uber's PostgreSQL Pain Points                           │
└─────────────────────────────────────────────────────────────────────┘

Original Architecture:
┌────────────┐    ┌─────────────────┐    ┌─────────────────────────┐
│  Trip Svc  │───▶│   PostgreSQL    │───▶│  Write amplification    │
│            │    │   (9.2 era)     │    │  from MVCC updates      │
└────────────┘    └─────────────────┘    └─────────────────────────┘

Problems at Scale:
┌─────────────────────────────────────────────────────────────────┐
│ 1. Write Amplification:                                          │
│    UPDATE → new tuple + old tuple (dead) + index updates         │
│    With 20 indexes: 1 UPDATE = 21 physical writes               │
│                                                                  │
│ 2. Replication: Page-level WAL shipping                          │
│    ┌────────┐ WAL (full pages) ┌─────────┐                      │
│    │Primary │─────────────────▶│ Replica │  (huge bandwidth)    │
│    └────────┘                  └─────────┘                      │
│                                                                  │
│ 3. Table Bloat:                                                  │
│    VACUUM couldn't keep up with update rate                      │
│    Tables grew 10x logical size                                  │
│                                                                  │
│ 4. Upgrade Path:                                                 │
│    pg_upgrade required downtime                                   │
│    Logical replication immature in 9.x                           │
└─────────────────────────────────────────────────────────────────┘

Lesson: PostgreSQL MVCC + many indexes + high update rate = problem
Solution: Moved to MySQL (InnoDB) - clustered index, row-based replication
```

### What Made It Work Initially

```sql
-- Trip table structure
CREATE TABLE trips (
    id              UUID PRIMARY KEY,
    rider_id        UUID NOT NULL,
    driver_id       UUID,
    status          VARCHAR(20) NOT NULL,
    pickup_location POINT,
    dropoff_location POINT,
    fare_amount     BIGINT,
    surge_multiplier DECIMAL(3,2),
    city_id         INTEGER NOT NULL,
    requested_at    TIMESTAMPTZ NOT NULL,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

-- Indexes that caused write amplification
CREATE INDEX idx_trips_rider ON trips (rider_id, requested_at DESC);
CREATE INDEX idx_trips_driver ON trips (driver_id, requested_at DESC);
CREATE INDEX idx_trips_status ON trips (status, city_id);
CREATE INDEX idx_trips_city_time ON trips (city_id, requested_at DESC);
CREATE INDEX idx_trips_geo ON trips USING GIST (pickup_location);
```

### Key Takeaway
PostgreSQL is excellent for transactional workloads but struggles with:
- Very high UPDATE rates (100K+ updates/sec) on tables with many indexes
- The combination of MVCC tuple versioning + heap storage + multiple indexes

---

## Replication Deep Dive

### Streaming Replication (Physical)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Streaming Replication Flow                         │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐           ┌──────────────────────┐
│      PRIMARY         │           │      REPLICA         │
│                      │           │                      │
│  Client ──▶ Backend  │           │                      │
│         │            │           │                      │
│         ▼            │           │                      │
│  ┌────────────┐      │   WAL    │  ┌────────────┐      │
│  │ WAL Buffer │──────│─────────▶│──│ WAL Recv   │      │
│  └────────────┘      │  Stream  │  └─────┬──────┘      │
│         │            │           │        │             │
│         ▼            │           │        ▼             │
│  ┌────────────┐      │           │  ┌────────────┐     │
│  │ WAL Files  │      │           │  │ WAL Files  │     │
│  │ (pg_wal/)  │      │           │  │ (applied)  │     │
│  └────────────┘      │           │  └─────┬──────┘     │
│         │            │           │        │             │
│         ▼            │           │        ▼             │
│  ┌────────────┐      │           │  ┌────────────┐     │
│  │ Data Files │      │           │  │ Data Files │     │
│  └────────────┘      │           │  │ (replayed) │     │
│                      │           │  └────────────┘     │
└──────────────────────┘           └──────────────────────┘

Synchronous Replication:
┌────────┐  INSERT  ┌─────────┐  WAL  ┌─────────┐  ACK  ┌─────────┐
│ Client │────────▶│ Primary │──────▶│ Replica │──────▶│ Primary │──▶ COMMIT OK
└────────┘         └─────────┘       └─────────┘       └─────────┘
                                                            │
  synchronous_commit = on                                   │
  synchronous_standby_names = 'replica1'                    │
                                                            ▼
                                              ┌─────────────────────┐
                                              │ Guarantees: no data  │
                                              │ loss on primary fail │
                                              └─────────────────────┘

Asynchronous Replication:
┌────────┐  INSERT  ┌─────────┐  COMMIT OK  ┌────────┐
│ Client │────────▶│ Primary │────────────▶│ Client │
└────────┘         └─────────┘             └────────┘
                        │
                        │ WAL (async, may lag)
                        ▼
                   ┌─────────┐
                   │ Replica │  ← may lose last few transactions on failover
                   └─────────┘
```

### Logical Replication

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Logical Replication                               │
└─────────────────────────────────────────────────────────────────────┘

Publisher (Source):                    Subscriber (Target):
┌────────────────────┐               ┌────────────────────┐
│ wal_level=logical  │               │                    │
│                    │               │                    │
│ Publication:       │   Decoded     │  Subscription:     │
│ CREATE PUBLICATION │───changes────▶│  CREATE SUBSCRIPTION│
│   pub FOR TABLE    │   (INSERT,   │    sub CONNECTION   │
│   orders, users;   │    UPDATE,   │    '...' PUBLICATION│
│                    │    DELETE)    │    pub;             │
│ WAL → Decode →     │               │                    │
│ Logical stream     │               │  Apply worker      │
└────────────────────┘               └────────────────────┘

Use Cases:
- Zero-downtime major version upgrades
- Selective table replication
- Cross-version replication
- Data integration (PG → analytics DB)
- Multi-master (with conflict resolution)
```

### Patroni High Availability

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Patroni HA Architecture                          │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │   DCS (etcd/ZK/     │
                    │   Consul) Cluster   │
                    │                     │
                    │  Holds leader lock  │
                    │  + cluster state    │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
     ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
     │  Patroni 1  │   │  Patroni 2  │   │  Patroni 3  │
     │  (Leader)   │   │  (Replica)  │   │  (Replica)  │
     │             │   │             │   │             │
     │  PostgreSQL │   │  PostgreSQL │   │  PostgreSQL │
     │  (Primary)  │   │  (Standby)  │   │  (Standby)  │
     └─────────────┘   └─────────────┘   └─────────────┘
            │                  ▲                  ▲
            │     Streaming Replication          │
            └──────────────────┴──────────────────┘

Failover Flow:
1. Patroni leader stops heartbeating DCS
2. DCS lock expires (TTL: 30s default)
3. Remaining Patronis race for leader lock
4. Winner promotes its PostgreSQL to primary
5. Loser reconfigures as replica of new primary
6. HAProxy/PgBouncer detects topology change
7. New writes go to new primary

Typical Failover Time: 10-30 seconds
```

---

## Scalability Patterns

### Vertical vs Horizontal Scaling

```
┌─────────────────────────────────────────────────────────────────────┐
│              PostgreSQL Scaling Decision Tree                        │
└─────────────────────────────────────────────────────────────────────┘

                    ┌────────────────────┐
                    │  Need more capacity │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │ Read-heavy or       │
                    │ Write-heavy?        │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │                               │
    ┌─────────▼─────────┐          ┌─────────▼─────────┐
    │   Read-Heavy      │          │   Write-Heavy     │
    │   (90%+ reads)    │          │   (or both)       │
    └─────────┬─────────┘          └─────────┬─────────┘
              │                               │
              ▼                               ▼
    ┌───────────────────┐         ┌───────────────────┐
    │ Add Read Replicas │         │ Need > 100K TPS?  │
    │ (up to ~5-10)     │         └─────────┬─────────┘
    │                   │                   │
    │ + Connection Pool │         ┌─────────┼─────────┐
    │ + Caching layer   │         │                   │
    └───────────────────┘         ▼                   ▼
                         ┌──────────────┐   ┌──────────────┐
                         │  Partition   │   │   Shard      │
                         │  (single     │   │   (Citus /   │
                         │   node)      │   │   app-level) │
                         └──────────────┘   └──────────────┘
```

### Citus Distributed PostgreSQL

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Citus Sharding Architecture                       │
└─────────────────────────────────────────────────────────────────────┘

                    ┌────────────────────────┐
                    │    Coordinator Node     │
                    │  (Query router/planner) │
                    │                        │
                    │  - Parses SQL          │
                    │  - Creates distributed │
                    │    query plan          │
                    │  - Routes to shards    │
                    │  - Aggregates results  │
                    └───────────┬────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│   Worker Node 1   │ │   Worker Node 2   │ │   Worker Node 3   │
│                   │ │                   │ │                   │
│ Shards:           │ │ Shards:           │ │ Shards:           │
│ orders_102008     │ │ orders_102010     │ │ orders_102012     │
│ orders_102009     │ │ orders_102011     │ │ orders_102013     │
│ customers_102008  │ │ customers_102010  │ │ customers_102012  │
│ customers_102009  │ │ customers_102011  │ │ customers_102013  │
│                   │ │                   │ │                   │
│ (+ replicas)      │ │ (+ replicas)      │ │ (+ replicas)      │
└───────────────────┘ └───────────────────┘ └───────────────────┘

Distribution: SELECT create_distributed_table('orders', 'customer_id');
Co-location:  orders + customers co-located by customer_id for fast JOINs
```

### Connection Pooling Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  PgBouncer Connection Pooling                        │
└─────────────────────────────────────────────────────────────────────┘

  App Servers (100s of instances, 10 connections each = 1000s of connections)
  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
  │App 1│ │App 2│ │App 3│ │App 4│ │App 5│ │App 6│ │App 7│ │App 8│
  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘
     │        │       │       │       │       │       │       │
     └────────┴───────┴───────┴───────┴───────┴───────┴───────┘
                                    │
                                    ▼
                    ┌────────────────────────────┐
                    │         PgBouncer          │
                    │                            │
                    │  Mode: transaction         │
                    │  Max client conn: 10000    │
                    │  Default pool size: 100    │
                    │  Reserve pool: 20          │
                    │                            │
                    │  10,000 clients → 100 PG   │
                    │  connections (100x reduce) │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │     PostgreSQL Primary     │
                    │     max_connections = 200  │
                    │                            │
                    │  100 from PgBouncer        │
                    │  50 for admin/monitoring   │
                    │  50 reserve                │
                    └────────────────────────────┘
```

### PostgreSQL Limits & When to Scale Out

| Metric | Practical Limit | Warning Signs |
|--------|----------------|---------------|
| Table size | 1-2 TB (manageable) | VACUUM takes hours, index rebuilds timeout |
| Connections | 500-1000 (with pooling 10K+) | Context switching, memory per connection |
| Write TPS | 50-100K (SSD, tuned) | WAL write becomes bottleneck |
| Read TPS | 200K+ (with replicas) | CPU saturation |
| Database size | 5-10 TB | Backup/restore time unacceptable |
| Indexes per table | 10-15 practical max | Write amplification, VACUUM slowness |

---

## Production Setup

### Hardware Recommendations

```
┌─────────────────────────────────────────────────────────────────────┐
│              Production Hardware Sizing                              │
└─────────────────────────────────────────────────────────────────────┘

Small (< 100GB data, < 5K TPS):
├── CPU: 8 cores
├── RAM: 32 GB (shared_buffers=8GB)
├── Storage: 500GB NVMe SSD
└── Network: 10 Gbps

Medium (100GB-1TB data, 5K-50K TPS):
├── CPU: 32 cores
├── RAM: 128 GB (shared_buffers=32GB)
├── Storage: 2TB NVMe SSD (RAID10 or cloud io2)
└── Network: 25 Gbps

Large (1TB+ data, 50K+ TPS):
├── CPU: 64-128 cores
├── RAM: 256-512 GB (shared_buffers=64-128GB)
├── Storage: 4-8TB NVMe SSD array
└── Network: 100 Gbps

Key Rules:
- shared_buffers = 25% of RAM
- effective_cache_size = 75% of RAM
- WAL on separate disk from data (if possible)
- OS: Linux (ext4 or XFS), vm.swappiness=1
```

### Backup Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Backup Architecture                               │
└─────────────────────────────────────────────────────────────────────┘

Continuous Archiving + PITR:
┌──────────┐    WAL Archive    ┌──────────────┐
│ Primary  │──────────────────▶│  S3 / GCS    │
│          │   (every 60s or   │  (WAL files) │
│          │    16MB segment)  │              │
└──────────┘                   └──────────────┘
      │
      │  pg_basebackup (weekly full)
      ▼
┌──────────────┐
│  S3 / GCS    │
│  (base       │
│   backups)   │
└──────────────┘

Recovery:
1. Restore latest base backup
2. Replay WAL files up to target time
3. RPO: seconds (WAL archive frequency)
4. RTO: minutes to hours (depends on data size)

Tools:
- pgBackRest (recommended): parallel backup/restore, encryption, retention
- WAL-G: simpler, cloud-native
- Barman: by EDB, feature-rich
```

### Monitoring Stack

```
┌──────────────────────────────────────────────────────────────────┐
│                    Monitoring Architecture                         │
└──────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌───────────────┐    ┌───────────────┐
│  PostgreSQL  │───▶│  postgres_    │───▶│  Prometheus   │
│              │    │  exporter     │    │               │
│ pg_stat_*    │    │  (port 9187)  │    │  (scrape     │
│ views        │    └───────────────┘    │   15s)       │
└──────────────┘                         └───────┬───────┘
                                                 │
                                                 ▼
                                         ┌───────────────┐
                                         │   Grafana     │
                                         │               │
                                         │  Dashboards:  │
                                         │  - TPS        │
                                         │  - Cache hit  │
                                         │  - Repl lag   │
                                         │  - Dead tuples│
                                         │  - Lock waits │
                                         │  - Disk I/O   │
                                         └───────────────┘

Key Metrics to Alert On:
- Cache hit ratio < 99%
- Replication lag > 1s
- Dead tuples / live tuples > 20%
- Active connections > 80% of max
- Transaction wraparound approaching (2^31 - current xid)
- Long-running transactions > 5 minutes
- Lock wait time > 5 seconds
```

---

## Core Concepts

### MVCC (Multi-Version Concurrency Control)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MVCC Internals                                │
└─────────────────────────────────────────────────────────────────────┘

Tuple Header (23 bytes):
┌──────────┬──────────┬──────────┬──────────┬─────────┐
│  t_xmin  │  t_xmax  │  t_cid   │  t_ctid  │  flags  │
│ (insert  │ (delete/ │ (command │ (current │         │
│  txn id) │  update) │    id)   │  version)│         │
└──────────┴──────────┴──────────┴──────────┴─────────┘

Example: UPDATE operation creates new tuple version:

Before UPDATE (Txn 100: INSERT):
┌────────────────────────────────────────────┐
│ Tuple V1: xmin=100, xmax=0, data="Alice"  │  ← visible to all
└────────────────────────────────────────────┘

After UPDATE (Txn 200: UPDATE name='Bob'):
┌────────────────────────────────────────────┐
│ Tuple V1: xmin=100, xmax=200, data="Alice"│  ← dead (but visible to
└────────────────────────────────────────────┘    txns started before 200)
┌────────────────────────────────────────────┐
│ Tuple V2: xmin=200, xmax=0, data="Bob"    │  ← current version
└────────────────────────────────────────────┘

Visibility Check (for reading Txn 150, snapshot xmin=100, xmax=201):
  Is tuple visible?
  1. xmin committed AND xmin < snapshot_xmax? → tuple "exists"
  2. xmax == 0 OR xmax not committed OR xmax >= snapshot_xmax? → not deleted yet
  → Tuple V1 visible (xmin=100 < 201, xmax=200 but txn 200 not in snapshot)
```

### WAL (Write-Ahead Logging)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WAL Write Flow                                    │
└─────────────────────────────────────────────────────────────────────┘

Transaction Commit Path:
┌────────┐   ┌────────────┐   ┌────────────┐   ┌──────────┐   ┌──────┐
│ Client │──▶│ Modify     │──▶│ Write WAL  │──▶│  fsync   │──▶│COMMIT│
│ INSERT │   │ Buffer Pool│   │ Buffer     │   │ WAL to   │   │  OK  │
└────────┘   │ (in memory)│   │            │   │ disk     │   └──────┘
             └────────────┘   └────────────┘   └──────────┘
                   │                                   │
                   │ (dirty pages)                     │
                   ▼                                   ▼
             ┌────────────┐                    ┌──────────────┐
             │ Background │                    │  WAL Files   │
             │ Writer /   │                    │  (16MB segs) │
             │ Checkpoint │                    │  pg_wal/     │
             │            │                    └──────────────┘
             │ Writes dirty│
             │ pages to    │
             │ data files  │
             └────────────┘

Crash Recovery:
1. Start from last checkpoint
2. Replay WAL forward from checkpoint LSN
3. All committed transactions restored
4. Uncommitted transactions rolled back

WAL Levels:
- minimal:  Crash recovery only
- replica:  + Streaming replication (default)
- logical:  + Logical decoding/replication
```

### Index Types Comparison

```
┌────────────┬─────────────────────────┬───────────────────────────────┐
│ Index Type │ Best For                │ Example                       │
├────────────┼─────────────────────────┼───────────────────────────────┤
│ B-tree     │ Equality, range,        │ WHERE id = 5                  │
│ (default)  │ sorting, LIKE 'abc%'    │ WHERE age BETWEEN 20 AND 30   │
├────────────┼─────────────────────────┼───────────────────────────────┤
│ Hash       │ Equality only           │ WHERE email = 'x@y.com'       │
│            │ (smaller than B-tree)   │ (not range queries)           │
├────────────┼─────────────────────────┼───────────────────────────────┤
│ GiST       │ Geometric, full-text,   │ WHERE location <@ box         │
│            │ range types, nearest    │ ORDER BY point <-> target     │
├────────────┼─────────────────────────┼───────────────────────────────┤
│ SP-GiST    │ Non-balanced structures │ Phone numbers (trie)          │
│            │ (quad-tree, radix tree) │ IP addresses                  │
├────────────┼─────────────────────────┼───────────────────────────────┤
│ GIN        │ Multiple values per row │ JSONB containment @>          │
│            │ (arrays, JSONB, FTS)    │ Full-text search @@           │
├────────────┼─────────────────────────┼───────────────────────────────┤
│ BRIN       │ Physically ordered data │ WHERE timestamp > '2024-01-01'│
│            │ (tiny index, huge table)│ (append-only time-series)     │
└────────────┴─────────────────────────┴───────────────────────────────┘
```

### Transaction Isolation Levels

```
┌──────────────────┬──────────────┬──────────────┬──────────────────┐
│ Isolation Level  │ Dirty Read   │ Non-Repeatable│ Phantom Read    │
│                  │              │ Read          │                  │
├──────────────────┼──────────────┼──────────────┼──────────────────┤
│ Read Uncommitted │ Not possible │ Possible     │ Possible         │
│ (= Read Committ │ (PG prevents)│              │                  │
│  ed in PG)      │              │              │                  │
├──────────────────┼──────────────┼──────────────┼──────────────────┤
│ Read Committed   │ No           │ Possible     │ Possible         │
│ (PG default)     │              │              │                  │
├──────────────────┼──────────────┼──────────────┼──────────────────┤
│ Repeatable Read  │ No           │ No           │ No (PG uses SSI) │
│                  │              │              │                  │
├──────────────────┼──────────────┼──────────────┼──────────────────┤
│ Serializable     │ No           │ No           │ No               │
│ (SSI-based)      │              │              │ (serialization   │
│                  │              │              │  errors possible)│
└──────────────────┴──────────────┴──────────────┴──────────────────┘

Note: PostgreSQL's Repeatable Read already prevents phantoms (unlike MySQL).
      Serializable adds detection of write skew anomalies.
```

### Vacuum & Autovacuum

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VACUUM Process                                    │
└─────────────────────────────────────────────────────────────────────┘

Why VACUUM is needed:
┌──────────────────────────────────────┐
│ Table with dead tuples after UPDATEs │
│                                      │
│ [Live][Dead][Live][Dead][Dead][Live]  │
│                                      │
│ Dead tuples waste space + slow scans │
└──────────────────────────────────────┘

VACUUM (regular):
┌──────────────────────────────────────┐
│ Marks dead tuple space as reusable   │
│ Does NOT return space to OS          │
│                                      │
│ [Live][Free][Live][Free][Free][Live]  │
│         ↑            ↑    ↑          │
│     Can be reused for new inserts    │
└──────────────────────────────────────┘

VACUUM FULL:
┌──────────────────────────────────────┐
│ Rewrites entire table compactly      │
│ Returns space to OS                  │
│ REQUIRES EXCLUSIVE LOCK (downtime!)  │
│                                      │
│ [Live][Live][Live]                   │
│ (table is smaller on disk)           │
└──────────────────────────────────────┘

Autovacuum Triggers:
- autovacuum_vacuum_threshold = 50 (min dead tuples)
- autovacuum_vacuum_scale_factor = 0.2 (20% of table)
- Trigger: dead_tuples > threshold + scale_factor * table_size
- For 1M row table: triggers at 50 + 0.2 * 1,000,000 = 200,050 dead tuples

Production Tuning (high-traffic):
  autovacuum_vacuum_scale_factor = 0.01  (1% instead of 20%)
  autovacuum_vacuum_cost_delay = 2ms     (faster vacuum)
  autovacuum_max_workers = 6             (more parallel workers)
```
