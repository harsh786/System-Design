# MySQL - Real World Use Cases & Production Guide

## Table of Contents
1. [Use Case 1: Facebook TAO](#use-case-1-facebook-tao)
2. [Use Case 2: GitHub Repository Storage](#use-case-2-github-repository-storage)
3. [Use Case 3: Shopify E-commerce](#use-case-3-shopify-e-commerce)
4. [Use Case 4: Airbnb Booking System](#use-case-4-airbnb-booking-system)
5. [Use Case 5: Uber Schemaless](#use-case-5-uber-schemaless)
6. [Replication Deep Dive](#replication-deep-dive)
7. [Scalability Patterns](#scalability-patterns)
8. [Production Setup](#production-setup)
9. [Core Concepts](#core-concepts)

---

## Use Case 1: Facebook TAO

### Why MySQL?
- Proven at extreme scale (billions of reads/sec with caching layer)
- InnoDB clustered index eliminates secondary lookups for primary key
- Row-based replication efficient for their workload
- Operational expertise built over a decade

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│            Facebook TAO (The Associations and Objects)               │
└─────────────────────────────────────────────────────────────────────┘

Read Path (99.8% cache hit rate):
┌────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Client │───▶│  TAO Leader  │───▶│  TAO Cache   │───▶│    MySQL     │
│        │    │  (routing)   │    │  (memcache)  │    │   (source)   │
└────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                       │ miss              │
                                       └───────────────────┘

Multi-Region Architecture:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   Region A (Primary)              Region B (Replica)                │
│   ┌─────────────────┐            ┌─────────────────┐               │
│   │  TAO Leader     │            │  TAO Follower   │               │
│   │  Cache Cluster  │            │  Cache Cluster  │               │
│   │  (read/write)   │            │  (read-only)    │               │
│   └────────┬────────┘            └────────┬────────┘               │
│            │                              │                         │
│   ┌────────▼────────┐            ┌────────▼────────┐               │
│   │  MySQL Primary  │───WAL────▶│  MySQL Replica  │               │
│   │  (InnoDB)       │  async    │  (InnoDB)       │               │
│   └─────────────────┘            └─────────────────┘               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Data Model (Objects and Associations):
┌────────────────────────────────┐
│ Objects (nodes):               │
│   User(id=1, name="Alice")     │
│   Post(id=100, text="Hello")   │
│   Photo(id=200, url="...")     │
└────────────────────────────────┘
         │
         │  Associations (edges):
         ▼
┌────────────────────────────────┐
│ AUTHORED: User:1 → Post:100   │
│ LIKES:    User:1 → Post:200   │
│ FRIEND:   User:1 ↔ User:2    │
└────────────────────────────────┘
```

### Schema Design

```sql
-- Objects table (one per shard)
CREATE TABLE objects (
    id          BIGINT UNSIGNED NOT NULL,
    type        INT UNSIGNED NOT NULL,
    version     INT UNSIGNED NOT NULL DEFAULT 1,
    data        MEDIUMBLOB NOT NULL,          -- serialized object data
    updated_at  INT UNSIGNED NOT NULL,        -- unix timestamp
    PRIMARY KEY (id)
) ENGINE=InnoDB;

-- Associations table (directed edges in the social graph)
CREATE TABLE associations (
    id1         BIGINT UNSIGNED NOT NULL,     -- source object
    assoc_type  INT UNSIGNED NOT NULL,        -- relationship type
    id2         BIGINT UNSIGNED NOT NULL,     -- target object
    time_col    INT UNSIGNED NOT NULL,        -- for time-ordered retrieval
    data        MEDIUMBLOB,                   -- edge metadata
    version     INT UNSIGNED NOT NULL DEFAULT 1,
    PRIMARY KEY (id1, assoc_type, id2),
    KEY idx_time (id1, assoc_type, time_col DESC)
) ENGINE=InnoDB;

-- Association counts (denormalized for fast count queries)
CREATE TABLE assoc_counts (
    id          BIGINT UNSIGNED NOT NULL,
    assoc_type  INT UNSIGNED NOT NULL,
    count       INT UNSIGNED NOT NULL DEFAULT 0,
    updated_at  INT UNSIGNED NOT NULL,
    PRIMARY KEY (id, assoc_type)
) ENGINE=InnoDB;
```

### Scale Numbers
- **Billions of reads/second** (mostly served from cache)
- **Millions of writes/second** to MySQL
- **~1000s of MySQL shards** (sharded by object_id % N)
- **99.8% cache hit rate** at TAO layer
- **Cross-datacenter replication lag**: < 1 second typical

---

## Use Case 2: GitHub Repository Storage

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                 GitHub's MySQL + Vitess Architecture                 │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌─────────────────────────────────┐
│  Rails   │───▶│   ProxySQL   │───▶│        Vitess Cluster           │
│  App     │    │  (routing)   │    │                                 │
└──────────┘    └──────────────┘    │  ┌───────────┐ ┌───────────┐   │
                                    │  │  VTGate   │ │  VTGate   │   │
                                    │  │ (router)  │ │ (router)  │   │
                                    │  └─────┬─────┘ └─────┬─────┘   │
                                    │        │             │          │
                                    │  ┌─────┴─────────────┴─────┐   │
                                    │  │       VTTablet           │   │
                                    │  │    (shard managers)      │   │
                                    │  └───────────┬─────────────┘   │
                                    │              │                  │
                                    │  ┌───────────┼───────────┐     │
                                    │  │           │           │     │
                                    │  ▼           ▼           ▼     │
                                    │ ┌────┐    ┌────┐    ┌────┐    │
                                    │ │ S1 │    │ S2 │    │ S3 │    │
                                    │ │MySQL│    │MySQL│    │MySQL│    │
                                    │ │P+R │    │P+R │    │P+R │    │
                                    │ └────┘    └────┘    └────┘    │
                                    └─────────────────────────────────┘

Shard Topology:
┌────────────────────────────────────────────────────────────┐
│  Functional Sharding (by table/feature):                    │
│                                                            │
│  Cluster 1: repositories, issues, pull_requests            │
│  Cluster 2: users, organizations, teams                    │
│  Cluster 3: notifications, events                          │
│  Cluster 4: actions (CI/CD workflows, runs)                │
│                                                            │
│  Within each cluster: horizontal sharding by repo_id/org_id│
└────────────────────────────────────────────────────────────┘

Online Schema Migration (gh-ost):
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Original Table│────▶│  Ghost Table  │────▶│  Rename Swap  │
│               │copy │ (new schema)  │     │               │
│               │ +   │               │     │ Original→_old │
│               │binlog│              │     │ Ghost→Original│
└───────────────┘     └───────────────┘     └───────────────┘
```

### Key Design Decisions
- **gh-ost**: GitHub's own online schema change tool (reads binlog, no triggers)
- **Vitess adoption**: For horizontal scaling beyond single MySQL limits
- **ProxySQL**: Connection pooling and read/write splitting
- **Functional sharding first**: Separate clusters by domain before horizontal

### Scale Numbers
- **200M+ repositories**
- **100M+ developers**
- **~1200 MySQL hosts** (across clusters)
- **Peak**: millions of queries/second
- **gh-ost migrations**: zero-downtime schema changes on multi-TB tables

---

## Use Case 3: Shopify E-commerce

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│               Shopify's Pod Architecture (MySQL)                     │
└─────────────────────────────────────────────────────────────────────┘

Each "Pod" = isolated MySQL cluster for a set of shops:

┌────────────────────────────────────────────────────────────────┐
│  Pod 1 (Shops 1-10000)        Pod 2 (Shops 10001-20000)       │
│  ┌────────────────────┐      ┌────────────────────┐           │
│  │  MySQL Primary     │      │  MySQL Primary     │           │
│  │  ├── Replica 1     │      │  ├── Replica 1     │           │
│  │  ├── Replica 2     │      │  ├── Replica 2     │           │
│  │  └── Replica 3     │      │  └── Replica 3     │           │
│  │                    │      │                    │           │
│  │  Tables:           │      │  Tables:           │           │
│  │  - shops           │      │  - shops           │           │
│  │  - orders          │      │  - orders          │           │
│  │  - products        │      │  - products        │           │
│  │  - customers       │      │  - customers       │           │
│  │  - inventory       │      │  - inventory       │           │
│  └────────────────────┘      └────────────────────┘           │
└────────────────────────────────────────────────────────────────┘

Routing:
┌────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐
│Request │──▶│ Shop Router  │──▶│ Pod Lookup   │──▶│  Target  │
│(shop_id)│  │              │   │ (Redis/Cache)│   │  Pod DB  │
└────────┘   └──────────────┘   └──────────────┘   └──────────┘

Black Friday Architecture (Flash Sales):
┌────────────┐    ┌──────────────┐    ┌────────────────────┐
│  CDN Edge  │───▶│  Job Queue   │───▶│  MySQL (orders)    │
│  (cached   │    │  (Redis +    │    │  Serialized writes │
│   catalog) │    │   Kafka)     │    │  via queue         │
└────────────┘    └──────────────┘    └────────────────────┘
```

### Schema Design

```sql
-- Multi-tenant with shop_id in every table
CREATE TABLE orders (
    id              BIGINT UNSIGNED AUTO_INCREMENT,
    shop_id         BIGINT UNSIGNED NOT NULL,
    customer_id     BIGINT UNSIGNED NOT NULL,
    order_number    INT UNSIGNED NOT NULL,
    financial_status ENUM('pending','paid','refunded','voided') NOT NULL,
    fulfillment_status ENUM('unfulfilled','partial','fulfilled') DEFAULT 'unfulfilled',
    total_price     DECIMAL(10,2) NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'USD',
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_shop_order (shop_id, order_number),
    KEY idx_shop_customer (shop_id, customer_id, created_at DESC),
    KEY idx_shop_status (shop_id, financial_status, created_at DESC)
) ENGINE=InnoDB
  ROW_FORMAT=DYNAMIC
  PARTITION BY HASH(shop_id) PARTITIONS 64;

-- Inventory (hot table during flash sales)
CREATE TABLE inventory_levels (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    shop_id         BIGINT UNSIGNED NOT NULL,
    variant_id      BIGINT UNSIGNED NOT NULL,
    location_id     BIGINT UNSIGNED NOT NULL,
    available       INT NOT NULL DEFAULT 0,
    reserved        INT NOT NULL DEFAULT 0,
    committed       INT NOT NULL DEFAULT 0,
    updated_at      DATETIME NOT NULL,
    UNIQUE KEY uk_variant_location (shop_id, variant_id, location_id)
) ENGINE=InnoDB;
```

### Scale Handling
- **Millions of merchants**, Black Friday peak: **$7.5B+ in sales**
- **Pod-based sharding**: Each pod handles ~10K shops
- **Shop migration**: Can move shops between pods for rebalancing
- **Read replicas**: 3-4 per primary, reads routed by query type
- **Queue-based writes**: During flash sales, orders go through Redis queue

---

## Use Case 4: Airbnb Booking System

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              Airbnb Booking (Double-Booking Prevention)              │
└─────────────────────────────────────────────────────────────────────┘

Booking Flow:
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Guest   │───▶│  Booking     │───▶│  Availability │───▶│   Payment    │
│  Client  │    │  Service     │    │  Service      │    │   Service    │
└──────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                       │                    │                    │
                       │                    ▼                    │
                       │            ┌──────────────┐            │
                       │            │   MySQL      │            │
                       │            │ (calendar/   │            │
                       │            │  availability)│           │
                       │            └──────────────┘            │
                       │                                        │
                       ▼                                        ▼
                ┌──────────────┐                    ┌──────────────┐
                │   MySQL      │                    │   Stripe/    │
                │ (bookings)   │                    │   Payment DB │
                └──────────────┘                    └──────────────┘

Double-Booking Prevention (Pessimistic Locking):
┌─────────────────────────────────────────────────────────────────────┐
│  BEGIN;                                                              │
│                                                                      │
│  -- Acquire row-level lock on calendar dates                        │
│  SELECT * FROM calendar_dates                                        │
│  WHERE listing_id = 123                                              │
│    AND date BETWEEN '2024-03-01' AND '2024-03-05'                   │
│    AND available = TRUE                                               │
│  FOR UPDATE;  -- locks these rows, other txns must wait             │
│                                                                      │
│  -- If all dates available, mark as booked                          │
│  UPDATE calendar_dates SET available = FALSE, booking_id = 456      │
│  WHERE listing_id = 123                                              │
│    AND date BETWEEN '2024-03-01' AND '2024-03-05';                  │
│                                                                      │
│  -- Insert booking record                                            │
│  INSERT INTO bookings (id, listing_id, guest_id, check_in, ...)    │
│  VALUES (456, 123, 789, '2024-03-01', ...);                        │
│                                                                      │
│  COMMIT;                                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Schema Design

```sql
CREATE TABLE listings (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    host_id         BIGINT UNSIGNED NOT NULL,
    title           VARCHAR(500) NOT NULL,
    property_type   ENUM('entire_place','private_room','shared_room') NOT NULL,
    price_per_night DECIMAL(10,2) NOT NULL,
    currency        CHAR(3) DEFAULT 'USD',
    max_guests      TINYINT UNSIGNED NOT NULL,
    city_id         INT UNSIGNED NOT NULL,
    latitude        DECIMAL(10,7),
    longitude       DECIMAL(10,7),
    INDEX idx_city_price (city_id, price_per_night),
    INDEX idx_host (host_id)
) ENGINE=InnoDB;

CREATE TABLE calendar_dates (
    listing_id      BIGINT UNSIGNED NOT NULL,
    date            DATE NOT NULL,
    available       BOOLEAN NOT NULL DEFAULT TRUE,
    price           DECIMAL(10,2),
    min_nights      TINYINT UNSIGNED DEFAULT 1,
    booking_id      BIGINT UNSIGNED NULL,
    PRIMARY KEY (listing_id, date),
    INDEX idx_available (listing_id, available, date)
) ENGINE=InnoDB;

CREATE TABLE bookings (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    listing_id      BIGINT UNSIGNED NOT NULL,
    guest_id        BIGINT UNSIGNED NOT NULL,
    check_in        DATE NOT NULL,
    check_out       DATE NOT NULL,
    total_price     DECIMAL(10,2) NOT NULL,
    status          ENUM('pending','confirmed','cancelled','completed') NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_listing_dates (listing_id, check_in, check_out),
    INDEX idx_guest (guest_id, status)
) ENGINE=InnoDB;
```

---

## Use Case 5: Uber Schemaless

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│           Uber's Schemaless (MySQL as Storage Engine)                │
└─────────────────────────────────────────────────────────────────────┘

Why MySQL (not PostgreSQL):
- InnoDB clustered index: row data stored with PK (no heap fetch)
- Row-based replication: lower bandwidth than PG's WAL
- Better write performance for their UPDATE-heavy workload
- Buffered writes via change buffer

Schemaless Architecture:
┌──────────┐    ┌──────────────┐    ┌─────────────────────────────────┐
│  Trip    │───▶│  Schemaless  │───▶│      MySQL Cluster (sharded)    │
│  Service │    │  Gateway     │    │                                 │
└──────────┘    └──────────────┘    │  Shard 1    Shard 2    Shard N  │
                     │              │  ┌──────┐  ┌──────┐  ┌──────┐  │
                     │              │  │MySQL │  │MySQL │  │MySQL │  │
                     │              │  │P + R │  │P + R │  │P + R │  │
                     │              │  └──────┘  └──────┘  └──────┘  │
                     ▼              └─────────────────────────────────┘
              ┌──────────────┐
              │   Cell-based  │
              │   Routing     │
              └──────────────┘

Data Model (append-only cells):
┌──────────────────────────────────────────────────────────────────┐
│  Row Key (UUID)  │  Column Name  │  Ref Key (version)  │  Blob  │
├──────────────────┼───────────────┼─────────────────────┼────────┤
│  trip_uuid_123   │  "base"       │  1609459200         │ {...}  │
│  trip_uuid_123   │  "base"       │  1609459260         │ {...}  │
│  trip_uuid_123   │  "fare"       │  1609459300         │ {...}  │
└──────────────────┴───────────────┴─────────────────────┴────────┘
```

### Schema Design

```sql
-- Schemaless storage table (per shard)
CREATE TABLE cells (
    row_key     VARBINARY(36) NOT NULL,       -- UUID
    column_name VARBINARY(255) NOT NULL,       -- logical column
    ref_key     BIGINT NOT NULL,               -- version/timestamp
    body        MEDIUMBLOB NOT NULL,           -- JSON blob
    created_at  BIGINT NOT NULL,
    PRIMARY KEY (row_key, column_name, ref_key DESC)
) ENGINE=InnoDB
  ROW_FORMAT=COMPRESSED
  KEY_BLOCK_SIZE=8;

-- Secondary index table (for queries by non-PK fields)
CREATE TABLE index_trip_by_rider (
    rider_id    VARBINARY(36) NOT NULL,
    created_at  BIGINT NOT NULL,
    row_key     VARBINARY(36) NOT NULL,
    PRIMARY KEY (rider_id, created_at DESC, row_key)
) ENGINE=InnoDB;
```

### Scale Numbers
- **Tens of millions of trips/day**
- **Hundreds of MySQL shards**
- **Append-only model** eliminates UPDATE write amplification
- **Column-based versioning** provides time-travel queries

---

## Replication Deep Dive

### Asynchronous Replication

```
┌─────────────────────────────────────────────────────────────────────┐
│                MySQL Async Replication Flow                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐                              ┌──────────────┐
│   PRIMARY    │                              │   REPLICA    │
│              │                              │              │
│ Transaction  │                              │              │
│    ↓         │                              │              │
│ Binary Log   │    Binary Log Events         │ I/O Thread   │
│ (binlog)     │─────────────────────────────▶│    ↓         │
│              │    (async, no wait)          │ Relay Log    │
│ COMMIT ──────│──▶ ACK to client            │    ↓         │
│              │    (immediately)             │ SQL Thread   │
│              │                              │    ↓         │
│              │                              │ Apply events │
└──────────────┘                              └──────────────┘

Timeline:
T0: Primary commits (client gets OK)
T1: Binlog event sent to replica (T1 > T0, gap = replication lag)
T2: Replica applies event

Risk: If primary crashes between T0 and T1, data is LOST
```

### Semi-Synchronous Replication

```
┌─────────────────────────────────────────────────────────────────────┐
│              Semi-Synchronous Replication                            │
└─────────────────────────────────────────────────────────────────────┘

┌────────┐  BEGIN  ┌─────────┐  Binlog  ┌──────────┐  ACK  ┌─────────┐
│ Client │───────▶│ Primary │────────▶│  Replica  │──────▶│ Primary │
└────────┘        └─────────┘         │(relay log)│       └────┬────┘
                       │              └──────────┘            │
                       │                                      │
                       │◀─────────── COMMIT OK ───────────────┘
                       │
                       ▼
                  Client gets OK
                  (after at least 1 replica ACKs)

Settings:
  rpl_semi_sync_source_wait_for_replica_count = 1
  rpl_semi_sync_source_timeout = 10000  (fallback to async after 10s)

Guarantee: Transaction exists on at least 2 nodes before client gets OK
Trade-off: +1 network RTT latency per commit (~0.5-2ms same DC)
```

### Group Replication (InnoDB Cluster)

```
┌─────────────────────────────────────────────────────────────────────┐
│              MySQL Group Replication / InnoDB Cluster                │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────┐
                    │      Group Communication    │
                    │      (Paxos-based)          │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
       ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
       │   Node 1    │     │   Node 2    │     │   Node 3    │
       │  (Primary)  │     │ (Secondary) │     │ (Secondary) │
       │             │     │             │     │             │
       │  R/W        │     │  R/O        │     │  R/O        │
       │             │     │             │     │             │
       │  InnoDB     │     │  InnoDB     │     │  InnoDB     │
       └─────────────┘     └─────────────┘     └─────────────┘

Write Flow:
1. Write arrives at Primary
2. Primary proposes to group (Paxos consensus)
3. Majority (2/3) certifies no conflict
4. Transaction applied on all nodes
5. Client gets COMMIT OK

Failover:
1. Primary node crashes
2. Group detects via heartbeat (5s default)
3. Remaining nodes elect new primary (lowest server_uuid)
4. MySQL Router redirects connections
5. Automatic failover: ~5-30 seconds

InnoDB Cluster = Group Replication + MySQL Shell + MySQL Router
```

### GTID-Based Replication

```
GTID Format: server_uuid:transaction_number
Example: 3E11FA47-71CA-11E1-9E33-C80AA9429562:1-1000

Advantages:
┌─────────────────────────────────────────────────────┐
│  Without GTID:                                       │
│  CHANGE MASTER TO MASTER_LOG_FILE='binlog.000003',  │
│                   MASTER_LOG_POS=4;                  │
│  (position-based, error-prone on failover)          │
│                                                      │
│  With GTID:                                          │
│  CHANGE MASTER TO MASTER_AUTO_POSITION=1;           │
│  (automatic position discovery)                     │
│                                                      │
│  Benefits:                                           │
│  - Automatic failover positioning                   │
│  - Easy topology changes (replica promotion)        │
│  - No duplicate transactions                         │
│  - Simple point-in-time recovery                    │
└─────────────────────────────────────────────────────┘
```

---

## Scalability Patterns

### Vitess Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Vitess Scaling Architecture                       │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────────────────────────────────────────┐
│  App     │───▶│                    VTGate                         │
│  Server  │    │  (Stateless query router, connection pooling)    │
└──────────┘    └─────────────────────┬────────────────────────────┘
                                      │
                      ┌───────────────┼───────────────┐
                      │               │               │
                      ▼               ▼               ▼
               ┌────────────┐  ┌────────────┐  ┌────────────┐
               │  VTTablet  │  │  VTTablet  │  │  VTTablet  │
               │  (Shard -80)│  │(Shard 80-c0)│ │(Shard c0-) │
               │  Primary   │  │  Primary   │  │  Primary   │
               │  + Replica │  │  + Replica │  │  + Replica │
               └──────┬─────┘  └──────┬─────┘  └──────┬─────┘
                      │               │               │
                      ▼               ▼               ▼
               ┌────────────┐  ┌────────────┐  ┌────────────┐
               │   MySQL    │  │   MySQL    │  │   MySQL    │
               │  Instance  │  │  Instance  │  │  Instance  │
               └────────────┘  └────────────┘  └────────────┘

Topology Service (etcd/ZK/Consul):
- Stores shard map, tablet locations, schema
- VTGate reads topology for routing decisions

Key Features:
- Transparent horizontal sharding
- Online resharding (split/merge shards)
- Connection pooling (1000s of app connections → few MySQL connections)
- Query rewriting and scatter-gather
```

### Read/Write Splitting with ProxySQL

```
┌─────────────────────────────────────────────────────────────────────┐
│                 ProxySQL Read/Write Splitting                        │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐
│  App     │──── writes (INSERT/UPDATE/DELETE) ────┐
│  Server  │                                       │
│          │──── reads (SELECT) ───┐               │
└──────────┘                       │               │
                                   │               │
                          ┌────────▼────────┐      │
                          │    ProxySQL     │      │
                          │                 │      │
                          │  HG 10 (write): │◀─────┘
                          │    → Primary    │
                          │                 │
                          │  HG 20 (read):  │
                          │    → Replica 1  │
                          │    → Replica 2  │
                          │    → Replica 3  │
                          │                 │
                          │  Query Rules:   │
                          │  ^SELECT → HG20 │
                          │  else   → HG10  │
                          └─────────────────┘

ProxySQL Configuration:
- max_replication_lag = 1 (seconds, remove lagging replicas from pool)
- weight-based load balancing across replicas
- query caching for repeated identical queries
- connection multiplexing
```

---

## Production Setup

### InnoDB Configuration

```ini
# my.cnf - Production InnoDB Settings

[mysqld]
# Buffer Pool (most important setting)
innodb_buffer_pool_size = 100G          # 70-80% of RAM for dedicated DB
innodb_buffer_pool_instances = 16       # reduce mutex contention
innodb_buffer_pool_dump_at_shutdown = ON
innodb_buffer_pool_load_at_startup = ON # warm cache on restart

# Redo Log (write performance)
innodb_log_file_size = 4G               # larger = fewer checkpoints
innodb_log_files_in_group = 2
innodb_log_buffer_size = 64M
innodb_flush_log_at_trx_commit = 1      # 1=ACID, 2=1sec durability, 0=fastest

# I/O
innodb_io_capacity = 10000              # SSD IOPS capacity
innodb_io_capacity_max = 20000
innodb_flush_method = O_DIRECT          # bypass OS cache
innodb_read_io_threads = 16
innodb_write_io_threads = 16

# Concurrency
innodb_thread_concurrency = 0           # let InnoDB manage
innodb_purge_threads = 4

# Doublewrite (data integrity)
innodb_doublewrite = ON                 # DO NOT disable

# Binary Logging
log_bin = mysql-bin
binlog_format = ROW                     # required for replication safety
sync_binlog = 1                         # ACID with innodb_flush_log_at_trx_commit=1
gtid_mode = ON
enforce_gtid_consistency = ON
binlog_expire_logs_days = 7
```

### Online Schema Changes

```
┌─────────────────────────────────────────────────────────────────────┐
│                gh-ost (GitHub Online Schema Translator)              │
└─────────────────────────────────────────────────────────────────────┘

Process:
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│ 1. Create   │───▶│ 2. Copy rows │───▶│ 3. Tail binlog  │
│ ghost table │    │ in chunks    │    │ for DML changes  │
│ (new schema)│    │ (throttled)  │    │ during copy      │
└─────────────┘    └──────────────┘    └─────────────────┘
                                              │
                                              ▼
                                       ┌─────────────────┐
                                       │ 4. Cut-over     │
                                       │ (atomic rename) │
                                       │ ~50ms downtime  │
                                       └─────────────────┘

Command:
gh-ost \
  --host=primary \
  --database=mydb \
  --table=orders \
  --alter="ADD COLUMN tracking_number VARCHAR(100)" \
  --chunk-size=1000 \
  --max-load=Threads_running=25 \
  --critical-load=Threads_running=100 \
  --execute

vs pt-online-schema-change (uses triggers, more overhead)
vs MySQL 8.0 instant DDL (limited operations: ADD COLUMN at end, etc.)
```

---

## Core Concepts

### InnoDB Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    InnoDB Storage Engine Architecture                │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │           Buffer Pool (RAM)          │
                    │                                     │
                    │  ┌──────────┐  ┌──────────────┐    │
                    │  │Data Pages│  │ Index Pages  │    │
                    │  └──────────┘  └──────────────┘    │
                    │  ┌──────────┐  ┌──────────────┐    │
                    │  │Undo Pages│  │ Change Buffer│    │
                    │  └──────────┘  └──────────────┘    │
                    │  ┌──────────┐  ┌──────────────┐    │
                    │  │Lock Info │  │Adaptive Hash │    │
                    │  └──────────┘  │   Index      │    │
                    │                └──────────────┘    │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────┬┴────────────────────┐
                    │                 │                     │
                    ▼                 ▼                     ▼
           ┌──────────────┐  ┌──────────────┐    ┌──────────────┐
           │  Redo Log    │  │ Doublewrite  │    │  Tablespace  │
           │  (ib_logfile)│  │   Buffer     │    │  (.ibd files)│
           │              │  │              │    │              │
           │  WAL for     │  │ Crash-safe   │    │  B+Tree data │
           │  crash       │  │ page writes  │    │  + indexes   │
           │  recovery    │  │              │    │              │
           └──────────────┘  └──────────────┘    └──────────────┘
                                      │                    ▲
                                      └────────────────────┘
                                      (pages written through doublewrite first)

Write Path:
1. Modify page in buffer pool (dirty page)
2. Write redo log entry (sequential, fast)
3. Return COMMIT to client
4. Background: flush dirty pages to tablespace (via doublewrite)
```

### Clustered Index vs Secondary Index

```
┌─────────────────────────────────────────────────────────────────────┐
│            InnoDB Index Architecture                                 │
└─────────────────────────────────────────────────────────────────────┘

Clustered Index (Primary Key):
┌─────────────────────────────────────────────────┐
│  B+Tree leaf nodes contain FULL ROW DATA        │
│                                                  │
│       [Internal Node: PK values]                │
│           /        |        \                   │
│     [Leaf]      [Leaf]      [Leaf]              │
│     PK=1        PK=5        PK=10              │
│     Row Data    Row Data    Row Data            │
│     (name,age)  (name,age)  (name,age)         │
└─────────────────────────────────────────────────┘

Secondary Index:
┌─────────────────────────────────────────────────┐
│  B+Tree leaf nodes contain PK value (pointer)   │
│                                                  │
│       [Internal Node: indexed column values]    │
│           /        |        \                   │
│     [Leaf]      [Leaf]      [Leaf]              │
│     email=a@    email=b@    email=c@            │
│     → PK=5     → PK=1      → PK=10            │
│                                                  │
│  To get full row: lookup PK in clustered index  │
│  (This is called a "bookmark lookup")           │
└─────────────────────────────────────────────────┘

Performance Implication:
- PK lookup: 1 B+Tree traversal → row data
- Secondary index lookup: 2 B+Tree traversals (secondary → PK → row)
- Covering index: if all columns in query are in index, skip PK lookup

Why This Matters for Uber's Migration FROM PostgreSQL:
- PostgreSQL heap: all indexes point to heap (ctid), no double lookup
- BUT: UPDATE in PG creates new tuple → ALL indexes must be updated
- InnoDB: UPDATE in place → only affected indexes updated
- For tables with 20+ indexes and frequent UPDATEs: InnoDB wins
```

### Lock Types

```
┌─────────────────────────────────────────────────────────────────────┐
│                    InnoDB Lock Types                                 │
└─────────────────────────────────────────────────────────────────────┘

1. Record Lock: Locks a single index record
   SELECT * FROM t WHERE id = 5 FOR UPDATE;
   → Locks only the record with id=5

2. Gap Lock: Locks the gap between index records
   SELECT * FROM t WHERE id BETWEEN 5 AND 10 FOR UPDATE;
   → Locks gap (5, 10) - prevents inserts in this range
   → Only in REPEATABLE READ (default)

3. Next-Key Lock: Record Lock + Gap Lock before it
   → Prevents phantom reads in REPEATABLE READ
   → Locks: (previous_record, current_record]

4. Intention Locks: Table-level locks indicating row-level intent
   → IS (Intention Shared): "I intend to read-lock some rows"
   → IX (Intention Exclusive): "I intend to write-lock some rows"

Example Deadlock:
┌─────────────────────────────────┬─────────────────────────────────┐
│ Transaction A                   │ Transaction B                   │
├─────────────────────────────────┼─────────────────────────────────┤
│ UPDATE t SET x=1 WHERE id=1;   │                                 │
│ (locks id=1)                    │                                 │
│                                 │ UPDATE t SET x=2 WHERE id=2;   │
│                                 │ (locks id=2)                    │
│ UPDATE t SET x=1 WHERE id=2;   │                                 │
│ (waits for B's lock on id=2)   │                                 │
│                                 │ UPDATE t SET x=2 WHERE id=1;   │
│                                 │ (waits for A's lock on id=1)   │
│                                 │ → DEADLOCK DETECTED             │
│                                 │ → B rolled back (victim)        │
│ (proceeds)                      │                                 │
└─────────────────────────────────┴─────────────────────────────────┘

InnoDB detects deadlocks via wait-for graph (cycle detection).
Victim selection: transaction with fewest undo log records.
```
