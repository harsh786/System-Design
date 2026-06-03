# TiDB - Real World Use Cases & Production Guide

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Use Case 1: Banking HTAP](#use-case-1-pingcaps-banking-customers)
- [Use Case 2: BookMyShow](#use-case-2-bookmyshow-india)
- [Use Case 3: Zhihu](#use-case-3-zhihu-chinas-quora)
- [Use Case 4: PayPay](#use-case-4-japans-paypay)
- [Use Case 5: Square/Block](#use-case-5-squareblock-payments)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)
- [Core Concepts](#core-concepts)

---

## Architecture Overview

```
                         ┌─────────────────────────────────────────────────────┐
                         │                   Application Layer                  │
                         └────────────┬──────────────┬──────────────┬──────────┘
                                      │              │              │
                              MySQL Protocol    MySQL Protocol   MySQL Protocol
                                      │              │              │
                         ┌────────────▼──┐    ┌──────▼───────┐  ┌──▼────────────┐
                         │  TiDB Server  │    │ TiDB Server  │  │  TiDB Server  │
                         │  (Stateless)  │    │ (Stateless)  │  │  (Stateless)  │
                         │  SQL Parser   │    │ SQL Parser   │  │  SQL Parser   │
                         │  Optimizer    │    │ Optimizer    │  │  Optimizer    │
                         │  Executor     │    │ Executor     │  │  Executor     │
                         └───────┬───────┘    └──────┬───────┘  └───────┬───────┘
                                 │                   │                   │
                    ┌────────────┼───────────────────┼───────────────────┼────────┐
                    │            │        PD Cluster (Placement Driver)  │        │
                    │   ┌────────▼────────┐  ┌───────▼───────┐  ┌───────▼─────┐  │
                    │   │   PD Leader     │  │  PD Follower  │  │ PD Follower │  │
                    │   │  - TSO Oracle   │  │               │  │             │  │
                    │   │  - Scheduler    │  │               │  │             │  │
                    │   │  - Meta Store   │  │               │  │             │  │
                    │   └────────┬────────┘  └───────────────┘  └─────────────┘  │
                    └────────────┼────────────────────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────────────┐
          │                      │                              │
   ┌──────▼──────┐      ┌───────▼──────┐              ┌────────▼─────┐
   │  TiKV Node  │      │  TiKV Node   │              │  TiKV Node   │
   │  (Row Store)│      │  (Row Store) │              │  (Row Store) │
   │  RocksDB    │      │  RocksDB     │              │  RocksDB     │
   │  Raft Group │      │  Raft Group  │              │  Raft Group  │
   └──────┬──────┘      └───────┬──────┘              └────────┬─────┘
          │                      │                              │
          │         Raft Learner Replication                    │
          │              ┌───────▼──────┐                       │
          │              │   TiFlash    │                       │
          │              │ (Columnar)   │                       │
          │              │  Analytics   │                       │
          │              └──────────────┘                       │
          └─────────────────────────────────────────────────────┘
```

**Component Roles:**
| Component | Role | State |
|-----------|------|-------|
| TiDB Server | SQL layer, parsing, optimization, execution | Stateless |
| PD (Placement Driver) | Cluster metadata, TSO, scheduling | Raft-based |
| TiKV | Distributed KV store, row-based, Raft consensus | Stateful |
| TiFlash | Columnar analytics engine, Raft learner | Stateful |

---

## Use Case 1: PingCAP's Banking Customers

### Context
Major Chinese banks (Bank of Beijing, WeBank, China UnionPay) use TiDB for real-time HTAP - running analytics queries on live transactional data without ETL pipelines.

### Why TiDB
- **MySQL compatible** - minimal application changes from existing MySQL/Oracle stacks
- **HTAP** - real-time analytics on transactional data (TiFlash columnar + TiKV row store)
- **Strong consistency** - distributed transactions with snapshot isolation (required for banking)
- **Regulatory compliance** - on-premise deployment, multi-DC disaster recovery

### Architecture

```
   ┌───────────────────────────────────────────────────────────────┐
   │                     Banking Applications                       │
   │  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
   │  │ Core     │  │ Anti-Fraud   │  │ Real-Time Risk          │ │
   │  │ Banking  │  │ Detection    │  │ Analytics Dashboard     │ │
   │  └────┬─────┘  └──────┬───────┘  └───────────┬─────────────┘ │
   └───────┼────────────────┼──────────────────────┼───────────────┘
           │ OLTP           │ OLTP                  │ OLAP
           │                │                       │
   ┌───────▼────────────────▼───────┐    ┌─────────▼──────────────┐
   │       TiDB SQL Layer           │    │   TiDB SQL Layer       │
   │   (Transaction Processing)     │    │   (Analytics Queries)  │
   └───────┬────────────────────────┘    └─────────┬──────────────┘
           │                                       │
           │  Row-based reads/writes               │ Columnar reads
           │                                       │
   ┌───────▼───────────────────┐        ┌─────────▼──────────────┐
   │        TiKV Cluster       │───────▶│      TiFlash Cluster   │
   │   (Row Store, Raft)       │ Raft   │   (Columnar Replica)   │
   │   3 replicas per region   │Learner │   Real-time sync       │
   │                           │        │   < 1s lag             │
   └───────────────────────────┘        └────────────────────────┘
```

### Schema Design

```sql
-- Core banking account table
CREATE TABLE accounts (
    account_id BIGINT NOT NULL AUTO_RANDOM,
    customer_id BIGINT NOT NULL,
    account_type ENUM('SAVINGS', 'CHECKING', 'LOAN', 'CREDIT') NOT NULL,
    balance DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    currency CHAR(3) NOT NULL DEFAULT 'CNY',
    status ENUM('ACTIVE', 'FROZEN', 'CLOSED') NOT NULL DEFAULT 'ACTIVE',
    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (account_id),
    INDEX idx_customer (customer_id),
    INDEX idx_status_type (status, account_type)
) ENGINE=InnoDB;

-- Transaction journal (append-heavy, sharded by time)
CREATE TABLE transactions (
    tx_id BIGINT NOT NULL AUTO_RANDOM,
    from_account BIGINT NOT NULL,
    to_account BIGINT NOT NULL,
    amount DECIMAL(18, 2) NOT NULL,
    tx_type ENUM('TRANSFER', 'DEPOSIT', 'WITHDRAWAL', 'PAYMENT') NOT NULL,
    status ENUM('PENDING', 'COMPLETED', 'FAILED', 'REVERSED') NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    reference_no VARCHAR(64) NOT NULL,
    PRIMARY KEY (tx_id),
    INDEX idx_from_account_time (from_account, created_at),
    INDEX idx_to_account_time (to_account, created_at),
    UNIQUE INDEX idx_reference (reference_no)
) ENGINE=InnoDB
PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
    PARTITION p202401 VALUES LESS THAN (UNIX_TIMESTAMP('2024-02-01')),
    PARTITION p202402 VALUES LESS THAN (UNIX_TIMESTAMP('2024-03-01')),
    PARTITION p202403 VALUES LESS THAN (UNIX_TIMESTAMP('2024-04-01'))
);

-- Anti-fraud rules and scoring (queried by TiFlash for real-time analytics)
CREATE TABLE fraud_events (
    event_id BIGINT NOT NULL AUTO_RANDOM,
    account_id BIGINT NOT NULL,
    risk_score DECIMAL(5, 2) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    details JSON,
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id),
    INDEX idx_account_time (account_id, detected_at)
) ENGINE=InnoDB;

-- Enable TiFlash replica for analytics tables
ALTER TABLE transactions SET TIFLASH REPLICA 2;
ALTER TABLE fraud_events SET TIFLASH REPLICA 2;
```

### Migration Path from MySQL
1. **Assessment** - Use TiDB Data Migration (DM) to analyze schema compatibility
2. **Schema migration** - Direct DDL import (99% MySQL compatible)
3. **Full data migration** - TiDB Lightning for bulk import (1TB+ per hour)
4. **Incremental sync** - DM binlog replication (MySQL -> TiDB real-time sync)
5. **Validation** - Sync-diff-inspector to verify data consistency
6. **Cutover** - Switch application connections (same MySQL protocol)

### Scale Numbers
- **Bank of Beijing**: 100+ TiDB nodes, 100TB+ data, millions of daily transactions
- **WeBank**: Handles 100M+ accounts, sub-10ms P99 for OLTP queries
- **Query performance**: OLTP P99 < 10ms, OLAP aggregations reduced from hours to seconds
- **Availability**: Multi-DC deployment with RPO=0, RTO < 30s

---

## Use Case 2: BookMyShow (India)

### Context
India's largest entertainment ticketing platform handling flash sales for movies, concerts, and sporting events. Extreme burst traffic patterns (10x normal within seconds of ticket drops).

### Why TiDB
- **MySQL compatible** - existing application code works unchanged
- **Horizontal scaling** - handle flash sale bursts without pre-sharding
- **Strong consistency** - no double-booking of seats
- **Auto-scaling** - TiDB servers (stateless) can scale out in seconds

### Architecture

```
   ┌──────────────────────────────────────────────────────────────────┐
   │                        Users (10M+ concurrent)                    │
   └──────────────────────────────┬───────────────────────────────────┘
                                  │
                          ┌───────▼───────┐
                          │   CDN + WAF   │
                          └───────┬───────┘
                                  │
                          ┌───────▼───────┐
                          │ Load Balancer │
                          │  (HAProxy)    │
                          └───┬───┬───┬───┘
                              │   │   │
              ┌───────────────┤   │   ├───────────────┐
              │               │   │   │               │
       ┌──────▼──────┐ ┌─────▼───▼─┐ │        ┌──────▼──────┐
       │ Booking     │ │ Inventory │ │        │ Analytics  │
       │ Service     │ │ Service   │ │        │ Service    │
       └──────┬──────┘ └─────┬─────┘ │        └──────┬──────┘
              │               │       │               │
              │ MySQL Protocol│       │               │ MySQL Protocol
              │               │       │               │
   ┌──────────▼───────────────▼───────▼──┐    ┌──────▼───────────────┐
   │         TiDB Cluster (OLTP)          │    │   TiDB (OLAP)       │
   │  ┌────────┐ ┌────────┐ ┌────────┐   │    │   Reads from        │
   │  │TiDB x6 │ │ PD x3  │ │TiKV x9│   │    │   TiFlash replicas  │
   │  └────────┘ └────────┘ └────────┘   │    └──────┬──────────────┘
   └──────────────────────┬───────────────┘           │
                          │                           │
                          │    ┌───────────────────────┘
                          │    │
                   ┌──────▼────▼─────┐
                   │   TiFlash x3    │
                   │ (Columnar OLAP) │
                   └─────────────────┘
```

### Schema Design

```sql
-- Events catalog
CREATE TABLE events (
    event_id BIGINT NOT NULL AUTO_RANDOM,
    title VARCHAR(255) NOT NULL,
    venue_id BIGINT NOT NULL,
    event_date DATETIME NOT NULL,
    category ENUM('MOVIE', 'CONCERT', 'SPORTS', 'COMEDY', 'THEATRE') NOT NULL,
    total_seats INT NOT NULL,
    available_seats INT NOT NULL,
    status ENUM('UPCOMING', 'BOOKING_OPEN', 'SOLD_OUT', 'COMPLETED', 'CANCELLED'),
    sale_start_time DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id),
    INDEX idx_category_date (category, event_date),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- Seat inventory with optimistic locking
CREATE TABLE seats (
    seat_id BIGINT NOT NULL AUTO_RANDOM,
    event_id BIGINT NOT NULL,
    section VARCHAR(10) NOT NULL,
    row_num VARCHAR(5) NOT NULL,
    seat_num INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    status ENUM('AVAILABLE', 'LOCKED', 'BOOKED', 'BLOCKED') NOT NULL DEFAULT 'AVAILABLE',
    locked_by BIGINT NULL,
    locked_until TIMESTAMP NULL,
    version INT NOT NULL DEFAULT 0,  -- optimistic lock
    PRIMARY KEY (seat_id),
    UNIQUE INDEX idx_event_seat (event_id, section, row_num, seat_num),
    INDEX idx_event_status (event_id, status)
) ENGINE=InnoDB;

-- Bookings
CREATE TABLE bookings (
    booking_id BIGINT NOT NULL AUTO_RANDOM,
    user_id BIGINT NOT NULL,
    event_id BIGINT NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'REFUNDED') NOT NULL,
    payment_id VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP NULL,
    PRIMARY KEY (booking_id),
    INDEX idx_user_events (user_id, created_at DESC),
    INDEX idx_event_status (event_id, status)
) ENGINE=InnoDB;

-- Booking items (seats in a booking)
CREATE TABLE booking_items (
    item_id BIGINT NOT NULL AUTO_RANDOM,
    booking_id BIGINT NOT NULL,
    seat_id BIGINT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (item_id),
    INDEX idx_booking (booking_id),
    UNIQUE INDEX idx_seat (seat_id)
) ENGINE=InnoDB;

-- Flash sale seat locking (optimistic concurrency)
-- Application uses: UPDATE seats SET status='LOCKED', locked_by=?, locked_until=?,
--                   version=version+1 WHERE seat_id=? AND status='AVAILABLE' AND version=?
```

### Migration Path from MySQL
1. **Schema export** - `mysqldump --no-data` -> import directly to TiDB
2. **Data sync** - TiDB DM full + incremental replication
3. **Read traffic shift** - Route read queries to TiDB (shadow reads)
4. **Write traffic shift** - Dual-write period, then full cutover
5. **Remove sharding middleware** - No more application-level sharding logic

### Scale Numbers
- **Peak QPS**: 500K+ queries/second during flash sales (IPL cricket, new movie releases)
- **Cluster size**: 6 TiDB + 9 TiKV + 3 PD + 3 TiFlash nodes
- **Data volume**: 5TB+ booking data
- **Latency**: P99 < 25ms for seat availability checks during peak
- **Burst handling**: 10x traffic spike absorbed without pre-provisioning

---

## Use Case 3: Zhihu (China's Quora)

### Context
Zhihu is China's largest Q&A platform with 100M+ users. They migrated from a heavily sharded MySQL architecture (hundreds of MySQL instances) to TiDB to eliminate operational complexity.

### Why TiDB
- **Eliminate sharding** - no more application-level shard routing
- **Cross-shard queries** - JOIN across previously sharded tables
- **Online DDL** - schema changes without downtime on massive tables
- **MySQL compatible** - minimal code changes to migrate

### Architecture

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │                     Zhihu Application Services                       │
   │  ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────────┐  │
   │  │ Feed    │  │ Question │  │ Messaging  │  │ Recommendation   │  │
   │  │ Service │  │ Service  │  │ Service    │  │ Service          │  │
   │  └────┬────┘  └─────┬────┘  └─────┬──────┘  └────────┬─────────┘  │
   └───────┼──────────────┼─────────────┼──────────────────┼────────────┘
           │              │             │                   │
           └──────────────┼─────────────┼───────────────────┘
                          │             │
                   ┌──────▼─────────────▼──────┐
                   │     MySQL Proxy / LB       │
                   └──────┬─────────────┬──────┘
                          │             │
           ┌──────────────▼──┐    ┌─────▼──────────────┐
           │  TiDB Cluster A │    │  TiDB Cluster B    │
           │  (User/Content) │    │  (Messaging/Feed)  │
           │                 │    │                    │
           │  TiDB x8       │    │  TiDB x6           │
           │  TiKV x12      │    │  TiKV x9           │
           │  PD x3         │    │  PD x3             │
           │  TiFlash x4    │    │  TiFlash x3        │
           └─────────────────┘    └────────────────────┘

   BEFORE (eliminated):
   ┌────────────────────────────────────────────────────────────┐
   │  200+ MySQL instances with custom sharding middleware       │
   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  ...  ┌──────┐     │
   │  │Shard1│ │Shard2│ │Shard3│ │Shard4│       │Shard200│    │
   │  └──────┘ └──────┘ └──────┘ └──────┘       └──────┘      │
   └────────────────────────────────────────────────────────────┘
```

### Schema Design

```sql
-- Questions table (previously sharded by question_id % 64)
CREATE TABLE questions (
    question_id BIGINT NOT NULL AUTO_RANDOM,
    author_id BIGINT NOT NULL,
    title VARCHAR(500) NOT NULL,
    content MEDIUMTEXT,
    topic_ids JSON,
    view_count BIGINT NOT NULL DEFAULT 0,
    answer_count INT NOT NULL DEFAULT 0,
    upvote_count INT NOT NULL DEFAULT 0,
    status ENUM('ACTIVE', 'CLOSED', 'DELETED') NOT NULL DEFAULT 'ACTIVE',
    is_anonymous TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (question_id),
    INDEX idx_author (author_id, created_at DESC),
    INDEX idx_created (created_at DESC),
    FULLTEXT INDEX idx_title (title)
) ENGINE=InnoDB;

-- Answers (previously sharded by question_id, limiting author-based queries)
CREATE TABLE answers (
    answer_id BIGINT NOT NULL AUTO_RANDOM,
    question_id BIGINT NOT NULL,
    author_id BIGINT NOT NULL,
    content MEDIUMTEXT NOT NULL,
    upvote_count INT NOT NULL DEFAULT 0,
    comment_count INT NOT NULL DEFAULT 0,
    is_collapsed TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (answer_id),
    INDEX idx_question_votes (question_id, upvote_count DESC),
    INDEX idx_author_time (author_id, created_at DESC)
) ENGINE=InnoDB;

-- User feed (previously required cross-shard scatter-gather)
CREATE TABLE user_feed (
    feed_id BIGINT NOT NULL AUTO_RANDOM,
    user_id BIGINT NOT NULL,
    content_type ENUM('QUESTION', 'ANSWER', 'ARTICLE', 'PIN') NOT NULL,
    content_id BIGINT NOT NULL,
    source_type ENUM('FOLLOW', 'TOPIC', 'RECOMMEND', 'HOT') NOT NULL,
    score DOUBLE NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (feed_id),
    INDEX idx_user_feed (user_id, created_at DESC),
    INDEX idx_user_score (user_id, score DESC)
) ENGINE=InnoDB;

-- Enable TiFlash for analytics (content trends, user behavior)
ALTER TABLE questions SET TIFLASH REPLICA 2;
ALTER TABLE answers SET TIFLASH REPLICA 2;
```

### Migration Path from MySQL
1. **De-shard schema** - Consolidate 64-shard schemas into single TiDB tables
2. **Data migration** - TiDB Lightning parallel import from all shards
3. **ID reconciliation** - AUTO_RANDOM eliminates shard-key conflicts
4. **Incremental sync** - DM syncs all 200+ MySQL instances -> single TiDB cluster
5. **Application refactor** - Remove sharding middleware, simplify to direct SQL
6. **Gradual cutover** - Service by service (feed, then questions, then messaging)

### Scale Numbers
- **Before**: 200+ MySQL instances, complex sharding middleware
- **After**: 2 TiDB clusters replacing all MySQL instances
- **Data volume**: 20TB+ across clusters
- **Peak QPS**: 1M+ read queries/second, 100K+ writes/second
- **Latency improvement**: Cross-shard queries from 100ms+ to < 10ms (now single distributed query)
- **Operational overhead**: DBA team reduced from 8 to 3

---

## Use Case 4: Japan's PayPay

### Context
PayPay is Japan's largest mobile payment platform (50M+ users). Needed MySQL-compatible distributed database for financial transactions with strong consistency, replacing vertically-scaled MySQL instances.

### Why TiDB
- **MySQL wire protocol** - existing Java/Spring applications connect unchanged
- **Financial-grade consistency** - distributed ACID transactions
- **Horizontal scale** - handle transaction growth without vertical scaling limits
- **Multi-DC** - disaster recovery across data centers with Raft

### Architecture

```
   ┌────────────────────────────────────────────────────────────────────┐
   │                     PayPay Mobile App (50M+ users)                  │
   └───────────────────────────────┬────────────────────────────────────┘
                                   │
                           ┌───────▼────────┐
                           │  API Gateway   │
                           └───────┬────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
   ┌────▼─────┐            ┌──────▼──────┐           ┌───────▼──────┐
   │ Payment  │            │  Balance    │           │ Transaction  │
   │ Service  │            │  Service    │           │ History      │
   └────┬─────┘            └──────┬──────┘           └───────┬──────┘
        │                         │                          │
        └─────────────────────────┼──────────────────────────┘
                                  │
                          ┌───────▼────────┐
                          │  Connection    │
                          │  Pool (ProxySQL)│
                          └───────┬────────┘
                                  │
   ┌──────────────────────────────▼──────────────────────────────────┐
   │                      TiDB Cluster                                │
   │                                                                  │
   │  Data Center A (Primary)         Data Center B (DR)              │
   │  ┌────────────────────────┐     ┌────────────────────────┐     │
   │  │ TiDB x4               │     │ TiDB x4               │     │
   │  │ TiKV x6 (Raft Leader) │     │ TiKV x6 (Raft Follow) │     │
   │  │ PD x2                 │     │ PD x1                 │     │
   │  └────────────────────────┘     └────────────────────────┘     │
   │                                                                  │
   │  Data Center C (DR)                                              │
   │  ┌────────────────────────┐                                     │
   │  │ TiKV x6 (Raft Follow) │                                     │
   │  │ TiFlash x3            │                                     │
   │  │ PD x1 (tiebreaker)    │                                     │
   │  └────────────────────────┘                                     │
   └──────────────────────────────────────────────────────────────────┘
```

### Schema Design

```sql
-- User wallet/balance
CREATE TABLE wallets (
    wallet_id BIGINT NOT NULL AUTO_RANDOM,
    user_id BIGINT NOT NULL,
    balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    pending_balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    currency CHAR(3) NOT NULL DEFAULT 'JPY',
    status ENUM('ACTIVE', 'SUSPENDED', 'CLOSED') NOT NULL DEFAULT 'ACTIVE',
    version BIGINT NOT NULL DEFAULT 0,  -- optimistic locking for balance updates
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (wallet_id),
    UNIQUE INDEX idx_user (user_id)
) ENGINE=InnoDB;

-- Payment transactions
CREATE TABLE payments (
    payment_id BIGINT NOT NULL AUTO_RANDOM,
    sender_wallet_id BIGINT NOT NULL,
    receiver_wallet_id BIGINT NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    payment_type ENUM('QR_PAY', 'TRANSFER', 'BILL_PAY', 'CASHBACK') NOT NULL,
    status ENUM('INITIATED', 'PROCESSING', 'COMPLETED', 'FAILED', 'REFUNDED') NOT NULL,
    merchant_id BIGINT NULL,
    idempotency_key VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    PRIMARY KEY (payment_id),
    UNIQUE INDEX idx_idempotency (idempotency_key),
    INDEX idx_sender_time (sender_wallet_id, created_at DESC),
    INDEX idx_receiver_time (receiver_wallet_id, created_at DESC),
    INDEX idx_merchant_time (merchant_id, created_at DESC)
) ENGINE=InnoDB;

-- Ledger entries (double-entry bookkeeping)
CREATE TABLE ledger_entries (
    entry_id BIGINT NOT NULL AUTO_RANDOM,
    payment_id BIGINT NOT NULL,
    wallet_id BIGINT NOT NULL,
    entry_type ENUM('DEBIT', 'CREDIT') NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    balance_after DECIMAL(15, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entry_id),
    INDEX idx_wallet_time (wallet_id, created_at DESC),
    INDEX idx_payment (payment_id)
) ENGINE=InnoDB;

-- Distributed transaction example (TiDB handles this natively):
-- BEGIN;
-- UPDATE wallets SET balance = balance - 1000, version = version + 1
--   WHERE user_id = ? AND balance >= 1000 AND version = ?;
-- UPDATE wallets SET balance = balance + 1000, version = version + 1
--   WHERE user_id = ? AND version = ?;
-- INSERT INTO payments (...) VALUES (...);
-- INSERT INTO ledger_entries (...) VALUES (...), (...);
-- COMMIT;
```

### Migration Path from MySQL
1. **Compatibility testing** - Run production queries against TiDB in shadow mode
2. **Data migration** - TiDB Lightning bulk load + DM for ongoing binlog sync
3. **Read split** - Route read-only transaction history to TiDB
4. **Write migration** - Dual-write pattern with consistency verification
5. **Full cutover** - Stop MySQL replication, TiDB becomes primary

### Scale Numbers
- **Users**: 50M+ registered, 30M+ monthly active
- **Daily transactions**: 10M+ payment transactions
- **Cluster**: 3 data centers, 18 TiKV nodes, 12 TiDB nodes
- **Latency**: P99 < 15ms for payment processing
- **Availability**: 99.999% (five 9s) with multi-DC Raft
- **Data volume**: 8TB+ with 90-day retention in hot storage

---

## Use Case 5: Square/Block Payments

### Context
Square (now Block) processes payments for millions of merchants. TiDB provides MySQL-compatible horizontal scaling for transaction processing without the complexity of manual sharding.

### Why TiDB
- **No manual sharding** - automatic region splitting as data grows
- **MySQL ecosystem** - works with existing ORMs, tools, monitoring
- **Linear scalability** - add nodes to handle transaction growth
- **HTAP** - real-time merchant analytics without separate data warehouse

### Architecture

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │                    Merchant POS / Square Terminal                     │
   └────────────────────────────────┬────────────────────────────────────┘
                                    │
                            ┌───────▼────────┐
                            │  API Gateway   │
                            │  (gRPC/REST)   │
                            └───────┬────────┘
                                    │
         ┌──────────────────────────┼─────────────────────────────┐
         │                          │                             │
   ┌─────▼──────┐         ┌────────▼────────┐          ┌─────────▼────────┐
   │ Payment    │         │ Merchant        │          │ Settlement       │
   │ Processing │         │ Dashboard       │          │ Service          │
   │ (OLTP)    │         │ (OLAP)          │          │ (Batch + OLTP)   │
   └─────┬──────┘         └────────┬────────┘          └─────────┬────────┘
         │                         │                             │
         │                         │                             │
   ┌─────▼─────────────────────────▼─────────────────────────────▼───────┐
   │                         TiDB Cluster                                 │
   │                                                                      │
   │   ┌──────────────────────────────────────────────────────────────┐  │
   │   │  TiDB Servers x10 (Stateless SQL Processing)                 │  │
   │   └──────────────────────────┬───────────────────────────────────┘  │
   │                              │                                      │
   │   ┌──────────────────────────▼───────────────────────────────────┐  │
   │   │  PD Cluster x5 (Scheduling, TSO, Metadata)                   │  │
   │   └──────────────────────────┬───────────────────────────────────┘  │
   │                              │                                      │
   │   ┌──────────────────────────▼───────────────────────────────────┐  │
   │   │  TiKV x20 (Row Store, Raft Consensus, 3 replicas)            │  │
   │   └──────────────────────────┬───────────────────────────────────┘  │
   │                              │ Raft Learner                         │
   │   ┌──────────────────────────▼───────────────────────────────────┐  │
   │   │  TiFlash x6 (Columnar, Merchant Analytics)                    │  │
   │   └──────────────────────────────────────────────────────────────┘  │
   └──────────────────────────────────────────────────────────────────────┘
```

### Schema Design

```sql
-- Merchants
CREATE TABLE merchants (
    merchant_id BIGINT NOT NULL AUTO_RANDOM,
    business_name VARCHAR(255) NOT NULL,
    business_type VARCHAR(100),
    country_code CHAR(2) NOT NULL,
    mcc_code CHAR(4) NOT NULL,  -- Merchant Category Code
    status ENUM('ACTIVE', 'SUSPENDED', 'DEACTIVATED') NOT NULL DEFAULT 'ACTIVE',
    settlement_account VARCHAR(50) NOT NULL,
    fee_rate DECIMAL(5, 4) NOT NULL DEFAULT 0.0275,  -- 2.75%
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (merchant_id),
    INDEX idx_country_type (country_code, business_type),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- Payment transactions (high-throughput, append-heavy)
CREATE TABLE payment_transactions (
    tx_id BIGINT NOT NULL AUTO_RANDOM,
    merchant_id BIGINT NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL,
    card_last_four CHAR(4),
    card_brand ENUM('VISA', 'MASTERCARD', 'AMEX', 'DISCOVER', 'JCB'),
    tx_type ENUM('SALE', 'REFUND', 'VOID', 'AUTH', 'CAPTURE') NOT NULL,
    status ENUM('PENDING', 'APPROVED', 'DECLINED', 'SETTLED', 'REFUNDED') NOT NULL,
    fee_amount DECIMAL(10, 2) NOT NULL,
    net_amount DECIMAL(12, 2) NOT NULL,
    device_id VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP NULL,
    PRIMARY KEY (tx_id),
    INDEX idx_merchant_time (merchant_id, created_at DESC),
    INDEX idx_status_time (status, created_at),
    INDEX idx_settlement (status, settled_at)
) ENGINE=InnoDB;

-- Daily settlement batches
CREATE TABLE settlements (
    settlement_id BIGINT NOT NULL AUTO_RANDOM,
    merchant_id BIGINT NOT NULL,
    settlement_date DATE NOT NULL,
    total_sales DECIMAL(14, 2) NOT NULL,
    total_refunds DECIMAL(14, 2) NOT NULL,
    total_fees DECIMAL(12, 2) NOT NULL,
    net_amount DECIMAL(14, 2) NOT NULL,
    tx_count INT NOT NULL,
    status ENUM('PENDING', 'PROCESSING', 'DEPOSITED', 'FAILED') NOT NULL,
    deposited_at TIMESTAMP NULL,
    PRIMARY KEY (settlement_id),
    UNIQUE INDEX idx_merchant_date (merchant_id, settlement_date),
    INDEX idx_status_date (status, settlement_date)
) ENGINE=InnoDB;

-- TiFlash for merchant analytics dashboards
ALTER TABLE payment_transactions SET TIFLASH REPLICA 2;
ALTER TABLE settlements SET TIFLASH REPLICA 2;

-- Example analytics query (automatically routed to TiFlash):
-- SELECT merchant_id, DATE(created_at) as day,
--        SUM(amount) as total_volume, COUNT(*) as tx_count,
--        SUM(fee_amount) as total_fees
-- FROM payment_transactions
-- WHERE created_at >= NOW() - INTERVAL 30 DAY
-- GROUP BY merchant_id, DATE(created_at);
```

### Migration Path from MySQL
1. **Analyze workload** - Identify hot tables and query patterns
2. **Remove sharding** - TiDB replaces Vitess/ProxySQL sharding layer
3. **Bulk migration** - TiDB Lightning for initial data load
4. **Incremental sync** - DM binlog replication during transition
5. **Performance validation** - Run production traffic in shadow mode
6. **Cutover** - Rolling switch with instant rollback capability

### Scale Numbers
- **Transactions**: Billions of transactions stored, millions daily
- **Cluster**: 10 TiDB + 20 TiKV + 5 PD + 6 TiFlash nodes
- **Storage**: 30TB+ across TiKV nodes
- **Throughput**: 200K+ TPS sustained, 500K+ peak
- **Analytics**: TiFlash aggregations over billions of rows in < 5 seconds
- **Growth**: Linear scalability - add 5 TiKV nodes = ~25% more capacity

---

## Replication

### Raft Consensus in TiKV Regions

TiKV splits data into **Regions** (default ~96MB each). Each Region is replicated using Raft consensus (typically 3 replicas).

```
                        Region 1 (key range: [a, m))
   ┌─────────────────────────────────────────────────────────┐
   │                                                         │
   │   TiKV Node 1          TiKV Node 2         TiKV Node 3 │
   │   ┌───────────┐        ┌───────────┐       ┌──────────┐│
   │   │  Region 1 │        │  Region 1 │       │ Region 1 ││
   │   │  (Leader) │───────▶│ (Follower)│       │(Follower)││
   │   │           │        │           │       │          ││
   │   │  Raft Log │───────▶│  Raft Log │       │ Raft Log ││
   │   └───────────┘    │   └───────────┘       └──────────┘│
   │                     │                                   │
   │                     └──────────────────────────────────▶│
   └─────────────────────────────────────────────────────────┘

   Write Path:
   ┌────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
   │ Client │────▶│ TiDB Server  │────▶│ Region Leader│────▶│ Raft Log │
   └────────┘     └──────────────┘     └──────┬──────┘     └──────────┘
                                              │
                                    Propose to Raft Group
                                              │
                              ┌────────────────┼────────────────┐
                              │                │                │
                              ▼                ▼                ▼
                        ┌──────────┐    ┌──────────┐    ┌──────────┐
                        │Follower 1│    │Follower 2│    │ Leader   │
                        │ Append   │    │ Append   │    │ Append   │
                        └──────────┘    └──────────┘    └──────────┘
                              │                │                │
                              └────────────────┼────────────────┘
                                              │
                                    Majority ACK (2/3)
                                              │
                                              ▼
                                       ┌────────────┐
                                       │   Commit   │
                                       │  (Applied) │
                                       └────────────┘
```

### Multi-Raft Group Architecture

```
   TiKV Node 1                TiKV Node 2               TiKV Node 3
   ┌─────────────────┐        ┌─────────────────┐       ┌─────────────────┐
   │ Region 1 (Lead) │◀──────▶│ Region 1 (Foll) │◀─────▶│ Region 1 (Foll) │
   │ Region 2 (Foll) │◀──────▶│ Region 2 (Lead) │◀─────▶│ Region 2 (Foll) │
   │ Region 3 (Foll) │◀──────▶│ Region 3 (Foll) │◀─────▶│ Region 3 (Lead) │
   │ Region 4 (Lead) │◀──────▶│ Region 4 (Foll) │◀─────▶│ Region 4 (Foll) │
   └─────────────────┘        └─────────────────┘       └─────────────────┘

   Key insight: Leaders are distributed across nodes for load balancing.
   PD scheduler ensures even leader distribution.
```

### TiCDC (Change Data Capture)

```
   ┌─────────────────────────────────────────────────────────────┐
   │                    TiDB/TiKV Cluster                         │
   │                                                             │
   │  TiKV regions emit change logs (Raft log entries)           │
   └─────────────────────────┬───────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │     TiCDC        │
                    │  (Captures Raft  │
                    │   log changes)   │
                    └───┬────┬────┬────┘
                        │    │    │
              ┌─────────┘    │    └──────────┐
              │              │               │
              ▼              ▼               ▼
   ┌──────────────┐  ┌────────────┐  ┌─────────────┐
   │ Downstream   │  │   Kafka    │  │  Another    │
   │ TiDB/MySQL   │  │   Topic    │  │  TiDB (DR)  │
   └──────────────┘  └────────────┘  └─────────────┘
```

**TiCDC features:**
- Row-level change events with ordering guarantees
- At-least-once delivery (exactly-once with downstream deduplication)
- Supports MySQL, Kafka, Pulsar, S3 as sinks
- Sub-second latency for replication
- Supports table/database filtering

### Placement Rules for Multi-DC

```sql
-- Define placement rules for multi-datacenter deployment
-- Ensure at least one replica in each DC for disaster recovery

-- Label TiKV nodes:
-- tikv1: zone=dc1, rack=r1
-- tikv2: zone=dc1, rack=r2
-- tikv3: zone=dc2, rack=r1
-- tikv4: zone=dc2, rack=r2
-- tikv5: zone=dc3, rack=r1

-- PD configuration for placement rules:
-- Ensures: 2 replicas in DC1 (primary), 2 in DC2, 1 in DC3
```

```
   DC1 (Primary)           DC2 (Secondary)         DC3 (Witness)
   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
   │ TiKV (Leader)│        │ TiKV (Follow)│        │ TiKV (Follow)│
   │ TiKV (Follow)│        │ TiKV (Follow)│        │              │
   │ TiDB x4      │        │ TiDB x4      │        │ PD (tiebreak)│
   │ PD x2        │        │ PD x1        │        │              │
   │ TiFlash x2   │        │ TiFlash x2   │        │              │
   └──────────────┘        └──────────────┘        └──────────────┘

   RPO = 0 (synchronous Raft)
   RTO < 30s (automatic leader transfer)
```

---

## Scalability

### Region-Based Auto-Sharding

```
   Initial state (1 region):
   ┌──────────────────────────────────────────────────────┐
   │  Region 1: [MinKey, MaxKey)  Size: 200MB             │
   └──────────────────────────────────────────────────────┘
                         │
                    Auto-split at 96MB
                         │
                         ▼
   ┌────────────────────────────┐  ┌─────────────────────────────┐
   │  Region 1: [MinKey, midKey)│  │  Region 2: [midKey, MaxKey) │
   │  Size: ~96MB               │  │  Size: ~96MB                │
   └────────────────────────────┘  └─────────────────────────────┘
                         │
                   Continues splitting as data grows...
                         │
                         ▼
   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
   │ R1   │ │ R2   │ │ R3   │ │ R4   │ │ R5   │ │ R6   │  ...
   │~96MB │ │~96MB │ │~96MB │ │~96MB │ │~96MB │ │~96MB │
   └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘

   PD schedules regions across TiKV nodes for balance:
   
   TiKV-1: [R1-Lead, R3-Foll, R5-Lead, R7-Foll, ...]
   TiKV-2: [R1-Foll, R2-Lead, R4-Lead, R6-Foll, ...]
   TiKV-3: [R1-Foll, R2-Foll, R3-Lead, R5-Foll, ...]
   TiKV-4: [R2-Foll, R4-Foll, R6-Lead, R8-Lead, ...]
```

### HTAP Architecture (TiKV + TiFlash)

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │                          TiDB SQL Layer                              │
   │                                                                      │
   │   Query Optimizer decides:                                           │
   │   - Point lookups / OLTP  ──────────────▶  Route to TiKV (row)     │
   │   - Aggregations / OLAP   ──────────────▶  Route to TiFlash (col)  │
   │   - Mixed (HTAP)          ──────────────▶  Hybrid: both engines    │
   │                                                                      │
   └────────────────────────┬─────────────────────────┬──────────────────┘
                            │                         │
                  OLTP Path │                         │ OLAP Path
                            │                         │
              ┌─────────────▼─────────────┐  ┌───────▼──────────────────┐
              │         TiKV              │  │       TiFlash            │
              │   (Row-oriented store)    │  │  (Columnar store)        │
              │                           │  │                          │
              │  ┌─────────────────────┐  │  │  ┌───────────────────┐  │
              │  │ Key: tableID_rowID  │  │  │  │ Column chunks     │  │
              │  │ Val: [col1,col2,..] │  │  │  │ Vectorized exec   │  │
              │  └─────────────────────┘  │  │  │ MPP (parallel)    │  │
              │                           │  │  └───────────────────┘  │
              │  Write: Raft consensus    │  │                          │
              │  Read: Leader/Follower    │  │  Sync: Raft Learner     │
              │                           │  │  Lag: < 1 second        │
              └───────────────────────────┘  └──────────────────────────┘
                            │                         ▲
                            │    Raft Learner Log     │
                            └─────────────────────────┘
```

### Horizontal Scaling (Adding Nodes)

```
   Before: 3 TiKV nodes, 300 regions

   TiKV-1: 100 regions (Leader: 34)
   TiKV-2: 100 regions (Leader: 33)
   TiKV-3: 100 regions (Leader: 33)

   ───── Add TiKV-4 ─────

   PD detects imbalance → schedules region transfers:

   After rebalancing (~minutes):
   TiKV-1: 75 regions (Leader: 25)
   TiKV-2: 75 regions (Leader: 25)
   TiKV-3: 75 regions (Leader: 25)
   TiKV-4: 75 regions (Leader: 25)    ← New node, auto-balanced

   Key: No downtime, no manual resharding, fully automatic.
   PD moves regions using Raft leadership transfer + snapshot.
```

### Load Balancing

```
   ┌────────────────────────────────────────────────────────┐
   │                Application Tier                         │
   └──────────────────────┬─────────────────────────────────┘
                          │
                ┌─────────▼──────────┐
                │   Load Balancer    │
                │  (HAProxy/LB/VIP)  │
                │  Round-robin to    │
                │  TiDB servers      │
                └──┬──────┬──────┬───┘
                   │      │      │
            ┌──────▼┐  ┌──▼────┐ ┌▼──────┐
            │TiDB-1 │  │TiDB-2 │ │TiDB-3 │   All stateless,
            │       │  │       │ │       │   any can handle
            │       │  │       │ │       │   any query
            └───────┘  └───────┘ └───────┘
   
   TiDB servers are stateless → scale out trivially.
   Add more TiDB nodes for more concurrent connections.
   Each TiDB server can handle ~10K concurrent connections.
```

### TPC-C / TPC-H Benchmark Numbers

| Benchmark | Configuration | Result |
|-----------|--------------|--------|
| TPC-C | 3 TiDB + 3 TiKV (16 vCPU each) | ~30,000 tpmC |
| TPC-C | 6 TiDB + 6 TiKV (16 vCPU each) | ~55,000 tpmC |
| TPC-C | 12 TiDB + 12 TiKV (16 vCPU each) | ~100,000 tpmC |
| TPC-H (100GB) | 3 TiFlash nodes | 22 queries, most < 30s |
| TPC-H (100GB) | TiFlash vs MySQL | 10x-100x faster on aggregations |
| Sysbench OLTP | 3 TiKV nodes | ~120K QPS (point select) |
| Sysbench OLTP | 3 TiKV nodes | ~15K QPS (update index) |

*Note: Numbers are approximate and vary with hardware, configuration, and TiDB version.*

---

## Production Setup

### Cluster Deployment

**Using TiUP (bare metal / VM):**

```bash
# Install TiUP
curl --proto '=https' --tlsv1.2 -sSf https://tiup-mirrors.pingcap.com/install.sh | sh

# Deploy cluster from topology file
tiup cluster deploy my-cluster v7.5.0 topology.yaml --user root -p

# Start cluster
tiup cluster start my-cluster

# Scale out (add TiKV nodes)
tiup cluster scale-out my-cluster scale-out-tikv.yaml

# Scale in (remove node)
tiup cluster scale-in my-cluster --node 10.0.1.5:20160
```

**Topology file (topology.yaml):**

```yaml
global:
  user: "tidb"
  deploy_dir: "/tidb-deploy"
  data_dir: "/tidb-data"

pd_servers:
  - host: 10.0.1.1
  - host: 10.0.1.2
  - host: 10.0.1.3

tidb_servers:
  - host: 10.0.1.4
  - host: 10.0.1.5
  - host: 10.0.1.6

tikv_servers:
  - host: 10.0.1.7
    config:
      server.labels:
        zone: "dc1"
        rack: "r1"
  - host: 10.0.1.8
    config:
      server.labels:
        zone: "dc1"
        rack: "r2"
  - host: 10.0.1.9
    config:
      server.labels:
        zone: "dc2"
        rack: "r1"

tiflash_servers:
  - host: 10.0.1.10
  - host: 10.0.1.11

monitoring_servers:
  - host: 10.0.1.12

grafana_servers:
  - host: 10.0.1.12
```

**Using TiDB Operator (Kubernetes):**

```yaml
apiVersion: pingcap.com/v1alpha1
kind: TidbCluster
metadata:
  name: production
  namespace: tidb
spec:
  version: v7.5.0
  pd:
    replicas: 3
    requests:
      storage: 10Gi
    config:
      schedule:
        leader-schedule-limit: 4
        region-schedule-limit: 2048
  tikv:
    replicas: 5
    requests:
      storage: 500Gi
    config:
      storage:
        block-cache:
          capacity: "16GB"
      raftstore:
        capacity: "500GB"
  tidb:
    replicas: 3
    service:
      type: LoadBalancer
  tiflash:
    replicas: 3
    storageClaims:
      - resources:
          requests:
            storage: 500Gi
```

### PD Scheduling Tuning

```sql
-- Key PD scheduling parameters (via pd-ctl or SQL)

-- Max number of pending peers (regions waiting for snapshot)
-- Increase for faster rebalancing, decrease for stability
pd-ctl config set max-pending-peer-count 64

-- Region merge settings (merge small adjacent regions)
pd-ctl config set max-merge-region-size 20       -- MB
pd-ctl config set max-merge-region-keys 200000

-- Scheduling speed
pd-ctl config set leader-schedule-limit 4        -- concurrent leader transfers
pd-ctl config set region-schedule-limit 2048     -- concurrent region moves
pd-ctl config set hot-region-schedule-limit 4    -- hot region balancing

-- Tolerances
pd-ctl config set tolerant-size-ratio 5          -- 5% imbalance tolerance
pd-ctl config set low-space-ratio 0.8            -- trigger balancing at 80%
pd-ctl config set high-space-ratio 0.7           -- stop moving into node at 70%
```

### TiKV RocksDB Tuning

```toml
# tikv.toml - Key tuning parameters

[rocksdb]
# Block cache - main memory consumer, set to ~45% of system RAM
max-background-jobs = 8
max-sub-compactions = 3

[rocksdb.defaultcf]
block-cache-size = "16GB"          # For default column family
write-buffer-size = "128MB"
max-write-buffer-number = 5
compression-per-level = ["no", "no", "lz4", "lz4", "lz4", "zstd", "zstd"]

[rocksdb.writecf]
block-cache-size = "4GB"           # Write CF (locks, etc.)

[rocksdb.raftcf]
block-cache-size = "2GB"           # Raft log CF

[raftstore]
# Region size tuning
region-max-size = "144MB"          # Split threshold
region-split-size = "96MB"         # Target size after split
region-max-keys = 1440000
region-split-keys = 960000

# Raft tuning
raft-base-tick-interval = "1s"
raft-heartbeat-ticks = 2           # Heartbeat every 2s
raft-election-timeout-ticks = 10   # Election timeout: 10s
raft-log-gc-tick-interval = "3s"

[server]
grpc-concurrency = 8
```

### Monitoring

```
   ┌──────────────────────────────────────────────────────────────────┐
   │                    Monitoring Stack                               │
   │                                                                  │
   │  ┌──────────────┐    ┌────────────┐    ┌─────────────────────┐  │
   │  │  TiDB        │    │ Prometheus │    │   Grafana           │  │
   │  │  Dashboard   │───▶│  (Metrics) │───▶│   (Visualization)   │  │
   │  │  (Built-in)  │    │            │    │                     │  │
   │  └──────────────┘    └────────────┘    └─────────────────────┘  │
   │                                                                  │
   │  ┌──────────────┐    ┌────────────┐    ┌─────────────────────┐  │
   │  │ AlertManager │    │  Node      │    │   Slow Query Log    │  │
   │  │ (Alerts)     │    │  Exporter  │    │   (TiDB built-in)   │  │
   │  └──────────────┘    └────────────┘    └─────────────────────┘  │
   └──────────────────────────────────────────────────────────────────┘
```

**Key metrics to monitor:**

| Category | Metric | Alert Threshold |
|----------|--------|-----------------|
| QPS | `tidb_executor_statement_total` | Baseline dependent |
| Latency | `tidb_server_handle_query_duration_seconds` | P99 > 1s |
| TiKV CPU | `tikv_thread_cpu_seconds_total` | > 80% |
| Region health | `pd_regions_status{type="miss-peer"}` | > 0 for 5min |
| Raft propose | `tikv_raftstore_propose_wait_duration` | P99 > 200ms |
| Storage | `tikv_engine_size_bytes` | > 80% capacity |
| TSO latency | `pd_client_request_handle_requests_duration` | P99 > 5ms |

### Backup and Restore

```bash
# Full backup using BR (Backup & Restore)
tiup br backup full \
  --pd "10.0.1.1:2379" \
  --storage "s3://my-bucket/backup-full" \
  --ratelimit 120 \        # MB/s per TiKV node
  --concurrency 4

# Incremental backup (only changes since last backup)
tiup br backup full \
  --pd "10.0.1.1:2379" \
  --storage "s3://my-bucket/backup-incr" \
  --lastbackupts 431434214122123264

# Restore
tiup br restore full \
  --pd "10.0.1.1:2379" \
  --storage "s3://my-bucket/backup-full"

# Export to SQL (for smaller datasets or cross-platform)
tiup dumpling \
  -h 10.0.1.4 -P 4000 -u root \
  --filetype sql \
  --output "s3://my-bucket/sql-dump" \
  --threads 16

# Fast import (TiDB Lightning - bypasses SQL layer)
tiup tidb-lightning \
  --config lightning.toml
  # Imports at 1TB+ per hour via direct SST file ingestion
```

### Online DDL

```sql
-- TiDB supports online DDL (non-blocking in most cases)

-- Add column (online, instant for nullable columns)
ALTER TABLE payments ADD COLUMN metadata JSON;

-- Add index (online, background job)
ALTER TABLE payments ADD INDEX idx_device (device_id);
-- Check progress:
ADMIN SHOW DDL JOBS;

-- Modify column type (requires rewrite, but online)
ALTER TABLE merchants MODIFY COLUMN business_name VARCHAR(500);

-- TiDB-specific: Control DDL concurrency
SET GLOBAL tidb_ddl_reorg_worker_cnt = 8;
SET GLOBAL tidb_ddl_reorg_batch_size = 1024;
```

---

## Core Concepts

### MySQL Compatibility

TiDB implements the MySQL wire protocol and is compatible with MySQL 5.7/8.0 syntax:

| Feature | Compatibility |
|---------|--------------|
| SQL syntax | 99%+ MySQL 5.7/8.0 compatible |
| Wire protocol | MySQL protocol (use any MySQL driver) |
| Transactions | READ COMMITTED, REPEATABLE READ (SI), Serializable |
| AUTO_INCREMENT | Supported (also AUTO_RANDOM for distributed) |
| Foreign keys | Supported (TiDB 7.0+) |
| Triggers | Not supported |
| Stored procedures | Limited support |
| Window functions | Full support |
| CTEs | Full support |
| JSON | Full support |

**Key differences from MySQL:**
- `AUTO_INCREMENT` is not strictly monotonic (allocated in batches per TiDB node)
- Use `AUTO_RANDOM` to avoid write hotspots on primary key
- `SELECT FOR UPDATE` behavior in optimistic transactions differs
- Default isolation level is Snapshot Isolation (stronger than MySQL's RR)

### Distributed Transaction Protocol (Percolator-based 2PC)

```
   Client                TiDB              TiKV (Primary)       TiKV (Secondary)
     │                    │                      │                      │
     │── BEGIN ──────────▶│                      │                      │
     │                    │── Get TSO (start_ts)▶│                      │
     │                    │◀── start_ts=100 ─────│                      │
     │                    │                      │                      │
     │── INSERT/UPDATE ──▶│                      │                      │
     │                    │── Prewrite (primary)─▶│                      │
     │                    │   key=pk, lock=pk    │                      │
     │                    │◀── OK ───────────────│                      │
     │                    │                      │                      │
     │                    │── Prewrite (secondary)──────────────────────▶│
     │                    │   key=sk, lock=pk    │                      │
     │                    │◀── OK ─────────────────────────────────────│
     │                    │                      │                      │
     │── COMMIT ─────────▶│                      │                      │
     │                    │── Get TSO (commit_ts)▶│                      │
     │                    │◀── commit_ts=110 ────│                      │
     │                    │                      │                      │
     │                    │── Commit (primary) ──▶│                      │
     │                    │   Remove lock,       │                      │
     │                    │   Write commit_ts    │                      │
     │                    │◀── OK ───────────────│                      │
     │◀── SUCCESS ────────│                      │                      │
     │                    │                      │                      │
     │                    │── Async: Commit (secondary) ────────────────▶│
     │                    │   Remove lock, write commit_ts              │
     │                    │                      │                      │
```

**Key properties:**
- **Prewrite phase**: Write locks + data to all involved regions
- **Commit phase**: Only need to commit primary key (secondary resolved lazily)
- **Conflict detection**: If lock found during prewrite → resolve or wait
- **Atomicity**: If primary committed → transaction committed (secondaries will resolve)

### MVCC with Timestamp Oracle (TSO)

```
   PD Leader (TSO)
   ┌────────────────────────────────────────────────────┐
   │  Logical clock: physical_time (ms) + logical_part  │
   │  Allocates monotonically increasing timestamps     │
   │  Batched allocation for performance                │
   │  ~1M timestamps/second per PD leader              │
   └─────────────────────┬──────────────────────────────┘
                         │
              start_ts ──┼── Read snapshot point
             commit_ts ──┼── Write visibility point
                         │
   Data versions in TiKV:
   ┌──────────────────────────────────────────────────┐
   │  Key: user_1                                     │
   │  ├── Version @ts=110: {name: "Bob", age: 31}    │  ← latest
   │  ├── Version @ts=100: {name: "Bob", age: 30}    │
   │  ├── Version @ts=85:  {name: "Alice", age: 30}  │
   │  └── Version @ts=50:  {name: "Alice", age: 25}  │  ← oldest
   │                                                  │
   │  Read at start_ts=105 → sees version @ts=100    │
   │  Read at start_ts=115 → sees version @ts=110    │
   └──────────────────────────────────────────────────┘
```

### Coprocessor (Push-Down Computation)

```
   Traditional approach:
   ┌────────┐                          ┌────────┐
   │  TiDB  │◀── Transfer ALL rows ───│  TiKV  │   Network bottleneck!
   │ Filter │                          │        │
   │  here  │                          │        │
   └────────┘                          └────────┘

   Coprocessor push-down:
   ┌────────┐                          ┌────────────────┐
   │  TiDB  │◀── Only matching rows ──│  TiKV          │
   │        │                          │  ┌───────────┐ │
   │        │                          │  │Coprocessor│ │
   │        │                          │  │ - WHERE   │ │
   │        │                          │  │ - GROUP BY│ │
   │        │                          │  │ - TopN    │ │
   │        │                          │  │ - Agg     │ │
   │        │                          │  └───────────┘ │
   └────────┘                          └────────────────┘

   Pushed down operators:
   - TableScan / IndexScan with predicates
   - Selection (WHERE)
   - Aggregation (COUNT, SUM, AVG, MIN, MAX)
   - TopN (ORDER BY ... LIMIT)
   - Limit
```

### Hot Region Detection and Scheduling

```
   PD monitors per-region metrics:
   ┌────────────────────────────────────────────────────────────┐
   │  Region Hotness Score = read_bytes + write_bytes +          │
   │                         read_keys + write_keys              │
   └────────────────────────────────────────────────────────────┘

   Detection:
   ┌────────────────────────────────────────────────────────────┐
   │  TiKV Node 1                                               │
   │  ┌──────────────────────────────────────┐                  │
   │  │ Region 42 (HOT!) - 90% of node QPS  │ ← Detected!     │
   │  └──────────────────────────────────────┘                  │
   └────────────────────────────────────────────────────────────┘
                              │
                    PD hot-region scheduler
                              │
                              ▼
   Resolution strategies:
   1. Transfer leader to less-loaded node
   2. Split hot region into smaller regions
   3. Move peer replica to distribute reads

   Common causes & solutions:
   ┌─────────────────────┬────────────────────────────────────┐
   │ Cause               │ Solution                           │
   ├─────────────────────┼────────────────────────────────────┤
   │ Sequential PK write │ Use AUTO_RANDOM or SHARD_ROW_ID    │
   │ Single-row hotspot  │ Application-level caching          │
   │ Index hotspot       │ Scatter index regions              │
   │ Small table hot     │ Pre-split regions                  │
   └─────────────────────┴────────────────────────────────────┘
```

```sql
-- Prevent write hotspots
CREATE TABLE orders (
    id BIGINT NOT NULL AUTO_RANDOM(5),  -- 5-bit shard prefix
    ...
    PRIMARY KEY (id)
);

-- Pre-split table into regions
SPLIT TABLE orders BETWEEN (0) AND (9223372036854775807) REGIONS 16;

-- Check hot regions
SELECT * FROM information_schema.tidb_hot_regions_history
WHERE update_time > NOW() - INTERVAL 5 MINUTE
ORDER BY flow_bytes DESC LIMIT 10;
```

### TiFlash Learner Replicas

```
   Raft Group for Region R1:
   ┌──────────────────────────────────────────────────────────────────┐
   │                                                                  │
   │  TiKV-1 (Leader)    TiKV-2 (Follower)    TiKV-3 (Follower)     │
   │  ┌─────────────┐    ┌─────────────┐      ┌─────────────┐       │
   │  │ R1 (Leader) │───▶│ R1 (Voter)  │      │ R1 (Voter)  │       │
   │  │ Row format  │    │ Row format  │      │ Row format  │       │
   │  └─────────────┘    └─────────────┘      └─────────────┘       │
   │         │                                                        │
   │         │ Raft Learner (async, non-voting)                       │
   │         ▼                                                        │
   │  TiFlash-1 (Learner)                                            │
   │  ┌──────────────────────────────────┐                           │
   │  │ R1 (Learner, non-voting)         │                           │
   │  │ Columnar format (Delta + Stable) │                           │
   │  │ - Does NOT participate in votes  │                           │
   │  │ - Does NOT affect write latency  │                           │
   │  │ - Async catch-up from Raft log   │                           │
   │  └──────────────────────────────────┘                           │
   └──────────────────────────────────────────────────────────────────┘

   Key insight: TiFlash is a Raft LEARNER, so:
   - It receives Raft logs but doesn't vote → no write latency impact
   - Data consistency guaranteed by Raft protocol
   - Typical replication lag: < 1 second
   - TiFlash converts row data to columnar format on apply
```

```sql
-- Add TiFlash replica (async, non-blocking)
ALTER TABLE payment_transactions SET TIFLASH REPLICA 2;

-- Check replication progress
SELECT * FROM information_schema.tiflash_replica;

-- Force query to use TiFlash
SET SESSION tidb_isolation_read_engines = 'tiflash';
SELECT COUNT(*), SUM(amount) FROM payment_transactions
WHERE created_at > '2024-01-01';

-- Let optimizer choose (default behavior)
SET SESSION tidb_isolation_read_engines = 'tikv,tiflash';
```

---

## Summary

| Aspect | TiDB |
|--------|------|
| **Protocol** | MySQL 5.7/8.0 compatible |
| **Scaling** | Horizontal (add nodes, auto-rebalance) |
| **Consistency** | Strong (Raft + distributed ACID) |
| **HTAP** | Row store (TiKV) + Columnar (TiFlash) unified |
| **Sharding** | Automatic (region-based, transparent to app) |
| **Max tested** | 500+ nodes, PB-scale data |
| **Typical latency** | OLTP P99: 5-25ms, OLAP: seconds on TB-scale |
| **Replication** | Raft (sync), TiCDC (async to external) |
| **Deployment** | TiUP (bare metal), TiDB Operator (K8s) |
| **Cloud** | TiDB Cloud (fully managed, AWS/GCP) |
