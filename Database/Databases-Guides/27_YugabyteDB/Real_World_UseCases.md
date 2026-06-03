# YugabyteDB - Real World Use Cases & Production Guide

## Table of Contents
- [Real-World Use Cases](#real-world-use-cases)
- [Core Concepts](#core-concepts)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)

---

## Real-World Use Cases

---

### 1. Kroger Grocery Platform

**Problem:** Multi-region grocery ordering and inventory management for 2,800+ stores across the US. Need real-time inventory updates with strong consistency and < 10ms reads for local stores.

**Why YugabyteDB:**
- PostgreSQL compatibility (existing app stack migrated without rewrites)
- Geo-partitioned tables pin store data to the nearest region
- Distributed transactions ensure inventory counts never go negative
- Survives entire region failures without data loss

**Scale Numbers:**
- 60M+ households served
- 2,800+ stores across US regions
- 500K+ orders/day during peak
- < 5ms p99 reads for local store inventory
- 3 regions (us-east, us-central, us-west), RF=3 per region

**Architecture:**

```
                         ┌─────────────────────────────────────────┐
                         │           Global Load Balancer           │
                         └────────┬──────────────┬─────────────────┘
                                  │              │              │
                    ┌─────────────▼──┐  ┌────────▼────────┐  ┌─▼────────────────┐
                    │   US-East DC    │  │  US-Central DC   │  │   US-West DC      │
                    │                 │  │                  │  │                   │
                    │ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐  │
                    │ │ YB-Master   │ │  │ │ YB-Master   │ │  │ │ YB-Master   │  │
                    │ │ (Leader)    │ │  │ │ (Follower)  │ │  │ │ (Follower)  │  │
                    │ └─────────────┘ │  │ └─────────────┘ │  │ └─────────────┘  │
                    │                 │  │                  │  │                   │
                    │ ┌───┐┌───┐┌───┐│  │ ┌───┐┌───┐┌───┐ │  │ ┌───┐┌───┐┌───┐ │
                    │ │ T ││ T ││ T ││  │ │ T ││ T ││ T │ │  │ │ T ││ T ││ T │ │
                    │ │ S ││ S ││ S ││  │ │ S ││ S ││ S │ │  │ │ S ││ S ││ S │ │
                    │ │ 1 ││ 2 ││ 3 ││  │ │ 4 ││ 5 ││ 6 │ │  │ │ 7 ││ 8 ││ 9 │ │
                    │ └───┘└───┘└───┘│  │ └───┘└───┘└───┘ │  │ └───┘└───┘└───┘ │
                    │                 │  │                  │  │                   │
                    │  Tablets:       │  │  Tablets:        │  │  Tablets:         │
                    │  East stores    │  │  Central stores  │  │  West stores      │
                    └─────────────────┘  └──────────────────┘  └───────────────────┘
```

**Schema Design:**

```sql
-- Geo-partitioned tablespaces
CREATE TABLESPACE ts_us_east WITH (
  replica_placement = '{"num_replicas": 3, "placement_blocks": [
    {"cloud": "aws", "region": "us-east-1", "zone": "us-east-1a", "min_num_replicas": 1},
    {"cloud": "aws", "region": "us-east-1", "zone": "us-east-1b", "min_num_replicas": 1},
    {"cloud": "aws", "region": "us-east-1", "zone": "us-east-1c", "min_num_replicas": 1}
  ]}'
);

CREATE TABLESPACE ts_us_central WITH (
  replica_placement = '{"num_replicas": 3, "placement_blocks": [
    {"cloud": "aws", "region": "us-central-1", "zone": "us-central-1a", "min_num_replicas": 1},
    {"cloud": "aws", "region": "us-central-1", "zone": "us-central-1b", "min_num_replicas": 1},
    {"cloud": "aws", "region": "us-central-1", "zone": "us-central-1c", "min_num_replicas": 1}
  ]}'
);

-- Partitioned inventory table (geo-pinned)
CREATE TABLE store_inventory (
    store_id        UUID NOT NULL,
    sku             VARCHAR(50) NOT NULL,
    region          VARCHAR(20) NOT NULL,
    quantity        INT NOT NULL DEFAULT 0,
    reserved_qty    INT NOT NULL DEFAULT 0,
    aisle_location  VARCHAR(20),
    last_restocked  TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (region, store_id, sku)
) PARTITION BY LIST (region);

CREATE TABLE store_inventory_east PARTITION OF store_inventory
    FOR VALUES IN ('us-east') TABLESPACE ts_us_east;

CREATE TABLE store_inventory_central PARTITION OF store_inventory
    FOR VALUES IN ('us-central') TABLESPACE ts_us_central;

CREATE TABLE store_inventory_west PARTITION OF store_inventory
    FOR VALUES IN ('us-west') TABLESPACE ts_us_west;

-- Orders table (hash-sharded globally)
CREATE TABLE orders (
    order_id        UUID DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL,
    store_id        UUID NOT NULL,
    region          VARCHAR(20) NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending',
    total_amount    DECIMAL(10,2),
    items           JSONB NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (order_id HASH)
);

CREATE INDEX idx_orders_customer ON orders (customer_id HASH, created_at DESC);
CREATE INDEX idx_orders_store ON orders (store_id HASH, status);

-- Atomic inventory reservation
CREATE OR REPLACE FUNCTION reserve_inventory(
    p_store_id UUID, p_sku VARCHAR, p_region VARCHAR, p_qty INT
) RETURNS BOOLEAN AS $$
DECLARE
    available INT;
BEGIN
    SELECT quantity - reserved_qty INTO available
    FROM store_inventory
    WHERE store_id = p_store_id AND sku = p_sku AND region = p_region
    FOR UPDATE;

    IF available >= p_qty THEN
        UPDATE store_inventory
        SET reserved_qty = reserved_qty + p_qty, updated_at = NOW()
        WHERE store_id = p_store_id AND sku = p_sku AND region = p_region;
        RETURN TRUE;
    END IF;
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;
```

**Geo-Distribution Configuration:**

```bash
# Create universe with geo-partitioning
yb-admin -master_addresses master1:7100,master2:7100,master3:7100 \
  modify_placement_info aws.us-east-1.us-east-1a,aws.us-east-1.us-east-1b,aws.us-central-1.us-central-1a 3

# Set preferred leader zones for low-latency writes
yb-admin set_preferred_zones aws.us-east-1.us-east-1a aws.us-central-1.us-central-1a aws.us-west-2.us-west-2a
```

---

### 2. Narvar E-commerce Post-Purchase Platform

**Problem:** Post-purchase experience platform (tracking, returns, notifications) for 800+ retailers handling billions of shipment events. Need to handle bursty holiday traffic (10x normal) with consistent latency.

**Why YugabyteDB:**
- Horizontal scale-out for Black Friday/Cyber Monday spikes
- JSONB support for varied retailer-specific event schemas
- PostgreSQL compatibility for existing analytics queries
- Automatic tablet splitting handles organic data growth

**Scale Numbers:**
- 800+ retailers (Nordstrom, GAP, Levi's, etc.)
- 1.5B+ shipment tracking events/month
- 150M+ consumers reached
- Peak: 50K writes/sec during holiday season
- < 10ms p99 read latency
- 12-node cluster, 48TB total data

**Architecture:**

```
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  Retailer A  │   │  Retailer B  │   │  Retailer N  │
    │   (Webhook)  │   │   (Webhook)  │   │   (Webhook)  │
    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
           │                  │                   │
           ▼                  ▼                   ▼
    ┌─────────────────────────────────────────────────────┐
    │              Kafka Event Bus (Partitioned)           │
    └────────┬────────────────┬───────────────┬───────────┘
             │                │               │
             ▼                ▼               ▼
    ┌────────────────┐ ┌─────────────┐ ┌─────────────────┐
    │ Event Ingester │ │   Ingester  │ │    Ingester     │
    │   (Pod 1-4)   │ │  (Pod 5-8)  │ │   (Pod 9-12)   │
    └────────┬───────┘ └──────┬──────┘ └────────┬────────┘
             │                │                  │
             ▼                ▼                  ▼
    ┌─────────────────────────────────────────────────────┐
    │                  YugabyteDB Cluster                  │
    │                                                     │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
    │  │YB-Master│  │YB-Master│  │YB-Master│  (3 nodes) │
    │  │ Leader  │  │Follower │  │Follower │            │
    │  └─────────┘  └─────────┘  └─────────┘            │
    │                                                     │
    │  ┌────────┐┌────────┐┌────────┐ ... ┌────────┐    │
    │  │TServer1││TServer2││TServer3│     │TServer12│    │
    │  │ 100 TB ││ 100 TB ││ 100 TB │     │ 100 TB │    │
    │  └────────┘└────────┘└────────┘     └────────┘    │
    │                                                     │
    │  Total: ~1200 tablets, RF=3                         │
    └─────────────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  Consumer App   │
    │  (Tracking Page)│
    └─────────────────┘
```

**Schema Design:**

```sql
-- Shipments table (hash-sharded by tracking_id for even distribution)
CREATE TABLE shipments (
    tracking_id     VARCHAR(64) NOT NULL,
    retailer_id     UUID NOT NULL,
    consumer_email  VARCHAR(255),
    carrier         VARCHAR(50),
    origin          JSONB,
    destination     JSONB,
    status          VARCHAR(30) DEFAULT 'created',
    estimated_delivery DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (tracking_id HASH)
);

-- Tracking events (range-sharded on time within each shipment)
CREATE TABLE tracking_events (
    tracking_id     VARCHAR(64) NOT NULL,
    event_ts        TIMESTAMPTZ NOT NULL,
    event_id        UUID DEFAULT gen_random_uuid(),
    event_type      VARCHAR(50) NOT NULL,  -- 'in_transit', 'out_for_delivery', 'delivered'
    location        JSONB,
    carrier_status  VARCHAR(100),
    raw_payload     JSONB,
    PRIMARY KEY ((tracking_id) HASH, event_ts DESC)
);

-- Notifications sent
CREATE TABLE notifications (
    notification_id UUID DEFAULT gen_random_uuid(),
    tracking_id     VARCHAR(64) NOT NULL,
    retailer_id     UUID NOT NULL,
    channel         VARCHAR(20) NOT NULL,  -- 'email', 'sms', 'push'
    template_id     VARCHAR(50),
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    status          VARCHAR(20) DEFAULT 'sent',
    PRIMARY KEY (notification_id HASH)
);

CREATE INDEX idx_notifications_tracking ON notifications (tracking_id HASH, sent_at DESC);
CREATE INDEX idx_shipments_retailer ON shipments (retailer_id HASH, created_at DESC);
CREATE INDEX idx_shipments_consumer ON shipments (consumer_email HASH, updated_at DESC);

-- Return requests
CREATE TABLE returns (
    return_id       UUID DEFAULT gen_random_uuid(),
    order_id        VARCHAR(64) NOT NULL,
    retailer_id     UUID NOT NULL,
    items           JSONB NOT NULL,
    reason          VARCHAR(255),
    status          VARCHAR(30) DEFAULT 'initiated',
    label_url       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (return_id HASH)
);
```

---

### 3. GE Healthcare (Predix) - Global IoT Platform

**Problem:** Global IoT platform ingesting telemetry from 500K+ medical devices (MRI, CT, ultrasound) across hospitals worldwide. Data sovereignty requirements per country. Need time-series writes + complex analytical queries.

**Why YugabyteDB:**
- Geo-partitioned tables enforce data residency (GDPR, HIPAA)
- High write throughput for continuous device telemetry
- YSQL for complex analytical queries on device data
- Strong consistency ensures accurate alert thresholds
- Survives AZ/region failures (critical for healthcare)

**Scale Numbers:**
- 500K+ connected medical devices globally
- 2M+ telemetry writes/sec aggregate
- 100TB+ data across regions
- Data retained for 7 years (compliance)
- < 50ms alert detection latency
- 5 regions: US, EU (Frankfurt), UK, Japan, Australia

**Architecture:**

```
    Medical Devices (MRI, CT, Ultrasound, Monitors)
         │         │         │         │
         ▼         ▼         ▼         ▼
    ┌─────────────────────────────────────┐
    │       IoT Gateway (Edge Layer)      │
    │  Protocol Translation (DICOM/HL7)   │
    └──────────────────┬──────────────────┘
                       │
                       ▼
    ┌─────────────────────────────────────┐
    │     Event Streaming (Kafka/Pulsar)  │
    └───┬──────────┬──────────┬───────────┘
        │          │          │
        ▼          ▼          ▼
    ┌────────┐ ┌────────┐ ┌────────┐
    │US Cluster│ │EU Cluster│ │APAC Cluster│
    │         │ │         │ │           │
    │ Masters │ │ Masters │ │  Masters  │
    │ [3]     │ │ [3]     │ │  [3]      │
    │         │ │         │ │           │
    │ TServer │ │ TServer │ │  TServer  │
    │ [6]     │ │ [6]     │ │  [6]      │
    │         │ │         │ │           │
    │ ~30TB   │ │ ~35TB   │ │  ~25TB    │
    └────┬────┘ └────┬────┘ └─────┬─────┘
         │           │             │
         └───────────┼─────────────┘
                     │
              xCluster Replication
             (Async, for analytics)
                     │
                     ▼
         ┌───────────────────────┐
         │  Analytics Cluster    │
         │  (Read Replicas)      │
         │  ML/Predictive Maint. │
         └───────────────────────┘
```

**Schema Design:**

```sql
-- Device registry (global, replicated everywhere)
CREATE TABLE devices (
    device_id       UUID DEFAULT gen_random_uuid(),
    serial_number   VARCHAR(100) UNIQUE NOT NULL,
    device_type     VARCHAR(50) NOT NULL,  -- 'MRI', 'CT', 'ULTRASOUND'
    manufacturer    VARCHAR(100),
    model           VARCHAR(100),
    hospital_id     UUID NOT NULL,
    country_code    VARCHAR(3) NOT NULL,
    firmware_ver    VARCHAR(20),
    status          VARCHAR(20) DEFAULT 'active',
    commissioned_at TIMESTAMPTZ,
    PRIMARY KEY (device_id HASH)
);

-- Telemetry (geo-partitioned by country for data sovereignty)
CREATE TABLE device_telemetry (
    device_id       UUID NOT NULL,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    country_code    VARCHAR(3) NOT NULL,
    metric_name     VARCHAR(50) NOT NULL,
    metric_value    DOUBLE PRECISION NOT NULL,
    unit            VARCHAR(20),
    metadata        JSONB,
    PRIMARY KEY ((device_id, country_code) HASH, ts DESC)
) PARTITION BY LIST (country_code);

CREATE TABLE telemetry_us PARTITION OF device_telemetry
    FOR VALUES IN ('US', 'CA') TABLESPACE ts_us;
CREATE TABLE telemetry_eu PARTITION OF device_telemetry
    FOR VALUES IN ('DE', 'FR', 'IT', 'ES', 'NL') TABLESPACE ts_eu;
CREATE TABLE telemetry_uk PARTITION OF device_telemetry
    FOR VALUES IN ('GB', 'IE') TABLESPACE ts_uk;
CREATE TABLE telemetry_apac PARTITION OF device_telemetry
    FOR VALUES IN ('JP', 'AU', 'SG', 'IN') TABLESPACE ts_apac;

-- Alerts (needs strong consistency, low latency)
CREATE TABLE device_alerts (
    alert_id        UUID DEFAULT gen_random_uuid(),
    device_id       UUID NOT NULL,
    severity        VARCHAR(10) NOT NULL,  -- 'CRITICAL', 'WARNING', 'INFO'
    alert_type      VARCHAR(100) NOT NULL,
    description     TEXT,
    metric_snapshot JSONB,
    acknowledged    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    PRIMARY KEY (alert_id HASH)
);

CREATE INDEX idx_alerts_device ON device_alerts (device_id HASH, created_at DESC);
CREATE INDEX idx_alerts_severity ON device_alerts (severity, acknowledged) WHERE NOT acknowledged;

-- Maintenance predictions (ML output)
CREATE TABLE maintenance_predictions (
    prediction_id   UUID DEFAULT gen_random_uuid(),
    device_id       UUID NOT NULL,
    predicted_failure_date DATE,
    confidence      DECIMAL(5,4),
    component       VARCHAR(100),
    recommendation  TEXT,
    model_version   VARCHAR(20),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (prediction_id HASH)
);
```

**Data Sovereignty Configuration:**

```bash
# EU cluster - data never leaves EU
yb-admin modify_placement_info \
  aws.eu-central-1.eu-central-1a,aws.eu-central-1.eu-central-1b,aws.eu-west-1.eu-west-1a 3

# xCluster replication (EU -> Analytics, redacted PII)
yb-admin setup_universe_replication \
  analytics_cluster_uuid eu_master1:7100,eu_master2:7100 \
  device_telemetry_eu_table_id device_alerts_table_id
```

---

### 4. Zerodha (Indian Stock Trading Platform)

**Problem:** India's largest stock broker processing 15M+ orders/day with strict latency requirements. Market hours see extreme burst traffic. Need ACID transactions for financial data with horizontal scalability.

**Why YugabyteDB:**
- Distributed ACID transactions for financial correctness
- Handles 10x traffic bursts during market open/close
- Horizontal scaling without application changes
- PostgreSQL compatibility (migrated from standalone PostgreSQL)
- Consistent sub-5ms reads for order book queries

**Scale Numbers:**
- 10M+ active traders
- 15M+ orders/day (peak market hours)
- 200K+ concurrent connections
- < 2ms p99 reads for portfolio queries
- < 5ms p99 writes for order placement
- 800K+ orders/minute during market open
- 18-node cluster (6 per AZ in Mumbai region)

**Architecture:**

```
    ┌──────────────────────────────────────────────────────────┐
    │                    Trading Clients                        │
    │   (Web/Mobile/API - 200K+ concurrent connections)        │
    └──────────────────────────┬───────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │              Connection Pooler (PgBouncer)                │
    │              (Transaction mode, 5000 server conns)        │
    └──────────────────────────┬───────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │                Order Management Service                   │
    │              (Stateless, 50+ pods)                        │
    └──────────────────────────┬───────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │                  YugabyteDB Cluster                       │
    │            (Mumbai Region, 3 AZs, RF=3)                  │
    │                                                          │
    │   AZ-1 (ap-south-1a)   AZ-2 (ap-south-1b)   AZ-3      │
    │  ┌───────────────────┐ ┌──────────────────┐ ┌────────┐  │
    │  │ YB-Master (Leader)│ │ YB-Master        │ │Master  │  │
    │  ├───────────────────┤ ├──────────────────┤ ├────────┤  │
    │  │ TServer-1  [L]    │ │ TServer-4  [F]   │ │TS-7 [F]│  │
    │  │ TServer-2  [L]    │ │ TServer-5  [F]   │ │TS-8 [F]│  │
    │  │ TServer-3  [L]    │ │ TServer-6  [F]   │ │TS-9 [F]│  │
    │  │ (NVMe SSDs)       │ │ (NVMe SSDs)      │ │(NVMe)  │  │
    │  └───────────────────┘ └──────────────────┘ └────────┘  │
    │                                                          │
    │  [L] = Raft Leader tablets (preferred)                   │
    │  [F] = Raft Follower tablets                             │
    │  Total: ~2000 tablets, ~5TB data                         │
    └──────────────────────────────────────────────────────────┘
                               │
                               │ (Async xCluster)
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │           DR Cluster (Hyderabad Region)                   │
    │           (Standby, async replication lag < 1s)           │
    └──────────────────────────────────────────────────────────┘
```

**Schema Design:**

```sql
-- User accounts and portfolio
CREATE TABLE trading_accounts (
    account_id      UUID DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL UNIQUE,
    pan_number      VARCHAR(10) NOT NULL UNIQUE,
    balance         DECIMAL(15,2) NOT NULL DEFAULT 0,
    margin_used     DECIMAL(15,2) NOT NULL DEFAULT 0,
    margin_available DECIMAL(15,2) GENERATED ALWAYS AS (balance - margin_used) STORED,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (account_id HASH)
);

-- Orders table (hot table, heavy writes during market hours)
CREATE TABLE orders (
    order_id        UUID DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    exchange        VARCHAR(10) NOT NULL,  -- 'NSE', 'BSE'
    order_type      VARCHAR(10) NOT NULL,  -- 'LIMIT', 'MARKET', 'SL'
    side            VARCHAR(4) NOT NULL,   -- 'BUY', 'SELL'
    quantity        INT NOT NULL,
    price           DECIMAL(10,2),
    filled_qty      INT DEFAULT 0,
    avg_fill_price  DECIMAL(10,2),
    status          VARCHAR(20) DEFAULT 'pending',
    placed_at       TIMESTAMPTZ DEFAULT NOW(),
    executed_at     TIMESTAMPTZ,
    PRIMARY KEY (order_id HASH)
);

-- Indexes for common query patterns
CREATE INDEX idx_orders_account_time ON orders (account_id HASH, placed_at DESC);
CREATE INDEX idx_orders_symbol_status ON orders (symbol HASH, status) WHERE status IN ('pending', 'partial');

-- Holdings (portfolio)
CREATE TABLE holdings (
    account_id      UUID NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    exchange        VARCHAR(10) NOT NULL,
    quantity        INT NOT NULL,
    avg_buy_price   DECIMAL(10,2) NOT NULL,
    current_value   DECIMAL(15,2),
    pnl             DECIMAL(15,2),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY ((account_id) HASH, symbol, exchange)
);

-- Trade executions (immutable ledger)
CREATE TABLE trades (
    trade_id        UUID DEFAULT gen_random_uuid(),
    order_id        UUID NOT NULL,
    account_id      UUID NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    exchange        VARCHAR(10) NOT NULL,
    side            VARCHAR(4) NOT NULL,
    quantity        INT NOT NULL,
    price           DECIMAL(10,2) NOT NULL,
    fees            DECIMAL(10,4) DEFAULT 0,
    executed_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (trade_id HASH)
) SPLIT INTO 64 TABLETS;

-- Atomic order execution with margin check
CREATE OR REPLACE FUNCTION execute_order(
    p_order_id UUID, p_fill_qty INT, p_fill_price DECIMAL
) RETURNS BOOLEAN AS $$
DECLARE
    v_account_id UUID;
    v_side VARCHAR(4);
    v_required_margin DECIMAL;
BEGIN
    SELECT account_id, side INTO v_account_id, v_side
    FROM orders WHERE order_id = p_order_id FOR UPDATE;

    v_required_margin := p_fill_qty * p_fill_price;

    IF v_side = 'BUY' THEN
        UPDATE trading_accounts
        SET margin_used = margin_used + v_required_margin
        WHERE account_id = v_account_id
          AND (balance - margin_used) >= v_required_margin;

        IF NOT FOUND THEN RETURN FALSE; END IF;
    END IF;

    UPDATE orders SET filled_qty = filled_qty + p_fill_qty,
        avg_fill_price = p_fill_price, status = 'filled', executed_at = NOW()
    WHERE order_id = p_order_id;

    INSERT INTO trades (order_id, account_id, symbol, exchange, side, quantity, price)
    SELECT p_order_id, account_id, symbol, exchange, side, p_fill_qty, p_fill_price
    FROM orders WHERE order_id = p_order_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
```

---

### 5. Nutanix Database Service (NDB)

**Problem:** Enterprise DBaaS product offering managed database instances (PostgreSQL, MySQL, SQL Server) on Nutanix infrastructure. Need a distributed metadata store that is itself highly available and manages lifecycle of thousands of DB instances.

**Why YugabyteDB:**
- Control plane metadata store that survives node failures
- Manages provisioning state machines with distributed transactions
- PostgreSQL API for familiar tooling/ORM integration
- Colocated tables for small metadata datasets (low overhead)
- Linear scalability as customer count grows

**Scale Numbers:**
- 10K+ managed database instances orchestrated
- 500+ enterprise customers
- 99.999% control plane availability target
- < 100ms for provisioning state transitions
- 3-node metadata cluster per NDB deployment (RF=3)
- Colocated mode (single tablet group for all metadata)

**Architecture:**

```
    ┌──────────────────────────────────────────────────────────┐
    │                  NDB Control Plane                        │
    │                                                          │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
    │  │Provisioner│  │ Monitor  │  │ Backup   │              │
    │  │ Service   │  │ Service  │  │ Service  │              │
    │  └─────┬─────┘  └─────┬────┘  └─────┬────┘              │
    │        │              │              │                    │
    │        ▼              ▼              ▼                    │
    │  ┌─────────────────────────────────────────────────┐     │
    │  │        YugabyteDB (Metadata Store)              │     │
    │  │                                                 │     │
    │  │  Node-1          Node-2          Node-3         │     │
    │  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   │     │
    │  │  │YB-Master │   │YB-Master │   │YB-Master │   │     │
    │  │  │YB-TServer│   │YB-TServer│   │YB-TServer│   │     │
    │  │  │          │   │          │   │          │   │     │
    │  │  │[Colocated│   │[Colocated│   │[Colocated│   │     │
    │  │  │ Tablet]  │   │ Tablet]  │   │ Tablet]  │   │     │
    │  │  └──────────┘   └──────────┘   └──────────┘   │     │
    │  │                                                 │     │
    │  │  All metadata tables in single tablet group     │     │
    │  │  (Raft consensus across 3 nodes)                │     │
    │  └─────────────────────────────────────────────────┘     │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
                               │
              Orchestrates     │
                               ▼
    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
    │ PG Inst │  │ PG Inst │  │MySQL Inst│  │ MS SQL  │
    │  (HA)   │  │  (HA)   │  │  (HA)   │  │  (HA)   │
    └─────────┘  └─────────┘  └─────────┘  └─────────┘
       Customer DB Instances (managed by NDB)
```

**Schema Design:**

```sql
-- Create a colocated database (all tables share one tablet group)
-- This is set at database creation time:
-- CREATE DATABASE ndb_metadata WITH COLOCATED = true;

-- Database instances managed by NDB
CREATE TABLE db_instances (
    instance_id     UUID DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL,
    name            VARCHAR(100) NOT NULL,
    engine          VARCHAR(20) NOT NULL,   -- 'postgresql', 'mysql', 'mssql'
    engine_version  VARCHAR(20) NOT NULL,
    status          VARCHAR(30) DEFAULT 'provisioning',
    compute_profile JSONB NOT NULL,          -- {vcpus, ram_gb, storage_gb}
    network_config  JSONB,
    ha_enabled      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (instance_id)
) WITH (COLOCATED = true);

-- Provisioning state machine
CREATE TABLE provisioning_tasks (
    task_id         UUID DEFAULT gen_random_uuid(),
    instance_id     UUID NOT NULL REFERENCES db_instances(instance_id),
    task_type       VARCHAR(50) NOT NULL,
    status          VARCHAR(20) DEFAULT 'queued',
    step_current    INT DEFAULT 0,
    step_total      INT NOT NULL,
    steps_detail    JSONB,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    PRIMARY KEY (task_id)
) WITH (COLOCATED = true);

-- Backup catalog
CREATE TABLE backups (
    backup_id       UUID DEFAULT gen_random_uuid(),
    instance_id     UUID NOT NULL REFERENCES db_instances(instance_id),
    backup_type     VARCHAR(20) NOT NULL,  -- 'full', 'incremental', 'pitr'
    status          VARCHAR(20) DEFAULT 'in_progress',
    size_bytes      BIGINT,
    storage_path    TEXT,
    retention_days  INT DEFAULT 30,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    PRIMARY KEY (backup_id)
) WITH (COLOCATED = true);

-- SLA monitoring
CREATE TABLE sla_events (
    event_id        UUID DEFAULT gen_random_uuid(),
    instance_id     UUID NOT NULL,
    event_type      VARCHAR(50) NOT NULL,
    downtime_sec    INT DEFAULT 0,
    description     TEXT,
    occurred_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id)
) WITH (COLOCATED = true);

CREATE INDEX idx_instances_customer ON db_instances (customer_id, status);
CREATE INDEX idx_tasks_instance ON provisioning_tasks (instance_id, status);
CREATE INDEX idx_backups_instance ON backups (instance_id, created_at DESC);
```

---

## Core Concepts

### DocDB Storage Engine

YugabyteDB's storage layer (DocDB) uses a modified RocksDB instance per tablet.

```
┌─────────────────────────────────────────────────────────┐
│                    YB-TServer Process                    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              YSQL Layer (PostgreSQL)             │    │
│  │         (Query parsing, planning, execution)    │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         │                               │
│  ┌──────────────────────▼──────────────────────────┐    │
│  │              DocDB (Document Store)              │    │
│  │                                                 │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │    │
│  │  │ Tablet-1 │  │ Tablet-2 │  │ Tablet-N │     │    │
│  │  │          │  │          │  │          │     │    │
│  │  │┌────────┐│  │┌────────┐│  │┌────────┐│     │    │
│  │  ││RocksDB ││  ││RocksDB ││  ││RocksDB ││     │    │
│  │  ││Instance││  ││Instance││  ││Instance││     │    │
│  │  │├────────┤│  │├────────┤│  │├────────┤│     │    │
│  │  ││WAL(Raft)│  ││WAL(Raft)│  ││WAL(Raft)│     │    │
│  │  │└────────┘│  │└────────┘│  │└────────┘│     │    │
│  │  └──────────┘  └──────────┘  └──────────┘     │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

Key encoding in DocDB:
┌──────────────────────────────────────────────────────────┐
│ SubDocKey = DocKey + SubKey + HybridTimestamp             │
│                                                          │
│ DocKey = HashCode + HashComponents + RangeComponents     │
│                                                          │
│ Example for row (user_id=100, name='Alice', age=30):     │
│   Key: H(100) | 100 | "name" | T(ts1) -> "Alice"        │
│   Key: H(100) | 100 | "age"  | T(ts1) -> 30             │
└──────────────────────────────────────────────────────────┘
```

### Hybrid Logical Clock (HLC)

```
┌───────────────────────────────────────────────────────┐
│                  HLC Timestamp                         │
│                                                       │
│  ┌────────────────────────┬──────────────────────┐    │
│  │   Physical Component   │  Logical Component   │    │
│  │   (wall clock, ~ms)    │  (monotonic counter) │    │
│  │      48 bits           │      16 bits         │    │
│  └────────────────────────┴──────────────────────┘    │
│                                                       │
│  Properties:                                          │
│  - Causally consistent (e → e' implies HLC(e) < HLC(e'))│
│  - Close to physical time (bounded drift)             │
│  - Tolerates clock skew up to --max_clock_skew_usec   │
│    (default: 500ms)                                   │
│                                                       │
│  Used for:                                            │
│  - MVCC (multi-version concurrency control)           │
│  - Snapshot isolation reads                           │
│  - Distributed transaction ordering                   │
└───────────────────────────────────────────────────────┘

Timeline example:
  Node A:  [100,0] ──> [101,0] ──> [102,0] ──────> [105,0]
                              │
                         msg to Node B
                              │
  Node B:  [99,0] ───> [101,1] ──> [102,0] ──> [103,0]
                        ^
                 max(local=99, msg=101)+logical
```

### Distributed Transactions (Spanner-inspired)

```
┌─────────────────────────────────────────────────────────────┐
│            Distributed Transaction Flow (2PC + Raft)         │
│                                                             │
│  Client                                                     │
│    │                                                        │
│    │  BEGIN; UPDATE t1 SET...; UPDATE t2 SET...; COMMIT;    │
│    ▼                                                        │
│  ┌──────────────────┐                                       │
│  │ Transaction Mgr  │  (on TServer handling the txn)        │
│  │ (Coordinator)    │                                       │
│  └────────┬─────────┘                                       │
│           │                                                 │
│    Phase 1: Write Intents (provisional writes)              │
│           │                                                 │
│           ├──────────────────────┐                          │
│           ▼                      ▼                          │
│  ┌────────────────┐    ┌────────────────┐                   │
│  │  Tablet-A      │    │  Tablet-B      │                   │
│  │  (has key k1)  │    │  (has key k2)  │                   │
│  │                │    │                │                   │
│  │  Write intent  │    │  Write intent  │                   │
│  │  k1=v1 @txn_id │    │  k2=v2 @txn_id │                   │
│  │  (Raft commit) │    │  (Raft commit) │                   │
│  └────────────────┘    └────────────────┘                   │
│           │                      │                          │
│    Phase 2: Commit                                          │
│           │                      │                          │
│  ┌────────────────┐                                         │
│  │ Transaction    │  Status: COMMITTED @commit_ts           │
│  │ Status Tablet  │  (Raft-replicated)                      │
│  └────────────────┘                                         │
│           │                                                 │
│    Phase 3: Apply (async cleanup of intents)                │
│           │                                                 │
│           ├──────────────────────┐                          │
│           ▼                      ▼                          │
│  Tablet-A: k1=v1 @commit_ts    Tablet-B: k2=v2 @commit_ts  │
│  (intent removed)              (intent removed)            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Transaction Isolation Levels:
- Snapshot Isolation (default): reads see consistent snapshot
- Serializable: uses read locks + write locks (pessimistic)
```

### Tablet Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Raft Group (per Tablet)                       │
│                                                                 │
│  TServer-1 (AZ-a)     TServer-2 (AZ-b)     TServer-3 (AZ-c)   │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐   │
│  │  Tablet-42    │    │  Tablet-42    │    │  Tablet-42    │   │
│  │  ┌─────────┐  │    │  ┌─────────┐  │    │  ┌─────────┐  │   │
│  │  │ LEADER  │  │◄──►│  │FOLLOWER │  │◄──►│  │FOLLOWER │  │   │
│  │  └─────────┘  │    │  └─────────┘  │    │  └─────────┘  │   │
│  │  ┌─────────┐  │    │  ┌─────────┐  │    │  ┌─────────┐  │   │
│  │  │RocksDB  │  │    │  │RocksDB  │  │    │  │RocksDB  │  │   │
│  │  │MemTable │  │    │  │MemTable │  │    │  │MemTable │  │   │
│  │  │SST Files│  │    │  │SST Files│  │    │  │SST Files│  │   │
│  │  └─────────┘  │    │  └─────────┘  │    │  └─────────┘  │   │
│  │  ┌─────────┐  │    │  ┌─────────┐  │    │  ┌─────────┐  │   │
│  │  │Raft WAL │  │    │  │Raft WAL │  │    │  │Raft WAL │  │   │
│  │  └─────────┘  │    │  └─────────┘  │    │  └─────────┘  │   │
│  └───────────────┘    └───────────────┘    └───────────────┘   │
│                                                                 │
│  Write path: Client → Leader → Raft log → Majority ACK → Apply │
│  Read path:  Client → Leader → Read from RocksDB (latest)      │
│  Follower read: Client → Follower → Safe read @HLC timestamp   │
└─────────────────────────────────────────────────────────────────┘
```

### YSQL vs YCQL

| Feature | YSQL | YCQL |
|---------|------|------|
| Wire Protocol | PostgreSQL | Cassandra CQL |
| SQL Support | Full SQL (joins, CTEs, subqueries) | CQL (no joins) |
| Transactions | Distributed ACID | Row-level + lightweight txns |
| Indexes | B-tree, GIN, partial, expression | Secondary indexes |
| Use Case | General purpose, migrations from PG | High-throughput key-value/wide-column |
| Latency | 2-5ms (single-row), 10-50ms (joins) | 1-3ms (single-row) |
| Port | 5433 | 9042 |

---

## Replication

### Raft Consensus per Tablet

```
┌─────────────────────────────────────────────────────────────┐
│              Raft Consensus Protocol (per tablet)            │
│                                                             │
│  Normal Operation (steady state):                           │
│                                                             │
│  Client ──Write──► Leader                                   │
│                      │                                      │
│                      ├──AppendEntries──► Follower-1         │
│                      │                      │               │
│                      ├──AppendEntries──► Follower-2         │
│                      │                      │               │
│                      │◄──── ACK ────────────┘               │
│                      │                                      │
│                      │  (Majority = 2/3 ACKs)               │
│                      │                                      │
│                      ├──Commit + Apply──► Response to Client│
│                                                             │
│  Leader Election (on leader failure):                       │
│                                                             │
│  Follower timeout ──► RequestVote ──► Majority votes        │
│                                        │                    │
│                                        ▼                    │
│                                    New Leader               │
│  (Election timeout: 1.5s default)                           │
│  (Heartbeat interval: 500ms)                                │
│                                                             │
│  Latency Impact:                                            │
│  - Same AZ: ~0.5ms Raft round-trip                          │
│  - Cross AZ (same region): ~1-2ms                           │
│  - Cross region: ~50-200ms (why geo-partitioning matters)   │
└─────────────────────────────────────────────────────────────┘
```

### xCluster Replication (Async Cross-Region)

```
┌────────────────────────┐              ┌────────────────────────┐
│   Source Universe       │              │   Target Universe       │
│   (Primary, US-East)    │              │   (DR, US-West)         │
│                         │              │                         │
│  ┌───────────────────┐  │   Async      │  ┌───────────────────┐  │
│  │ TServer (Leader)   │  │─────WAL────►│  │ TServer (applies)  │  │
│  │ Tablet-1 WAL      │  │  streaming   │  │ Tablet-1           │  │
│  └───────────────────┘  │              │  └───────────────────┘  │
│                         │              │                         │
│  ┌───────────────────┐  │              │  ┌───────────────────┐  │
│  │ TServer (Leader)   │  │─────WAL────►│  │ TServer (applies)  │  │
│  │ Tablet-2 WAL      │  │              │  │ Tablet-2           │  │
│  └───────────────────┘  │              │  └───────────────────┘  │
│                         │              │                         │
│  Replication lag: ~1-5s (async)        │                         │
│  RPO: seconds                          │  RTO: minutes (manual)  │
└────────────────────────┘              └────────────────────────┘

Setup:
  yb-admin -master_addresses <target_masters> \
    setup_universe_replication <replication_id> \
    <source_masters> <table_id_1> <table_id_2>

Modes:
  - Unidirectional: Primary → DR
  - Bidirectional: Active-Active (with conflict resolution)
  - Transactional xCluster: preserves transaction atomicity
```

### Geo-Partitioned Tables

```
┌─────────────────────────────────────────────────────────────────┐
│                   Geo-Partitioned Table                          │
│                                                                 │
│  CREATE TABLE users (...) PARTITION BY LIST (region);            │
│                                                                 │
│   US Partition          EU Partition          APAC Partition     │
│   (Tablespace: US)      (Tablespace: EU)      (Tablespace: APAC)│
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐    │
│   │ us-east-1a  │      │eu-central-1a│      │ap-south-1a  │    │
│   │ us-east-1b  │      │eu-central-1b│      │ap-south-1b  │    │
│   │ us-west-2a  │      │eu-west-1a   │      │ap-east-1a   │    │
│   │ (RF=3)      │      │ (RF=3)      │      │ (RF=3)      │    │
│   └─────────────┘      └─────────────┘      └─────────────┘    │
│                                                                 │
│   Data NEVER leaves     GDPR compliant       Low-latency for    │
│   US boundaries         data residency       APAC users         │
└─────────────────────────────────────────────────────────────────┘
```

### Read Replicas

```
┌──────────────────────┐         ┌──────────────────────────┐
│  Primary Cluster      │         │  Read Replica Cluster     │
│  (US-East, RF=3)      │  Async  │  (EU-West, RF=1)          │
│                       │────────►│                           │
│  Handles all writes   │  Raft   │  Serves local reads only  │
│  + reads              │  log    │  Stale reads OK (< 1s)    │
│                       │         │  Cannot accept writes     │
└──────────────────────┘         └──────────────────────────┘

Config:
  yb-admin modify_placement_info aws.us-east-1.* 3
  yb-admin add_read_replica_placement_info aws.eu-west-1.* 1
```

---

## Scalability

### Full Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      YugabyteDB Architecture                        │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     YB-Master (Control Plane)                  │  │
│  │                                                               │  │
│  │  Responsibilities:                                            │  │
│  │  - Tablet-to-TServer mapping (metadata)                       │  │
│  │  - DDL operations (CREATE TABLE, ALTER, etc.)                 │  │
│  │  - Load balancing (tablet moves between TServers)             │  │
│  │  - Cluster membership (node join/leave)                       │  │
│  │  - Tablet splitting decisions                                 │  │
│  │                                                               │  │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐                  │  │
│  │  │ Master-1 │   │ Master-2 │   │ Master-3 │  (Raft group)    │  │
│  │  │ (LEADER) │◄─►│(FOLLOWER)│◄─►│(FOLLOWER)│                  │  │
│  │  └──────────┘   └──────────┘   └──────────┘                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                  Heartbeats + Load reports                           │
│                              │                                       │
│  ┌───────────────────────────▼───────────────────────────────────┐  │
│  │                  YB-TServer (Data Plane)                       │  │
│  │                                                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │  │
│  │  │  TServer-1  │  │  TServer-2  │  │  TServer-N  │           │  │
│  │  │             │  │             │  │             │           │  │
│  │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │           │  │
│  │  │ │YSQL Port│ │  │ │YSQL Port│ │  │ │YSQL Port│ │           │  │
│  │  │ │  :5433  │ │  │ │  :5433  │ │  │ │  :5433  │ │           │  │
│  │  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │           │  │
│  │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │           │  │
│  │  │ │YCQL Port│ │  │ │YCQL Port│ │  │ │YCQL Port│ │           │  │
│  │  │ │  :9042  │ │  │ │  :9042  │ │  │ │  :9042  │ │           │  │
│  │  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │           │  │
│  │  │             │  │             │  │             │           │  │
│  │  │ Tablet Tablet│  │ Tablet Tablet│  │ Tablet Tablet│           │  │
│  │  │  [L]   [F]  │  │  [F]   [L]  │  │  [F]   [L]  │           │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Tablet-Based Sharding

```
Hash Sharding (default for YSQL):
┌─────────────────────────────────────────────────────────┐
│  PRIMARY KEY (user_id HASH)                             │
│                                                         │
│  Hash space: 0x0000 ─────────────────────────── 0xFFFF  │
│              │         │         │         │            │
│              ▼         ▼         ▼         ▼            │
│          Tablet-1  Tablet-2  Tablet-3  Tablet-4         │
│         [0000-3FFF][4000-7FFF][8000-BFFF][C000-FFFF]    │
│                                                         │
│  Pros: Even data distribution, parallel scans           │
│  Cons: No range scans on hash key                       │
└─────────────────────────────────────────────────────────┘

Range Sharding:
┌─────────────────────────────────────────────────────────┐
│  PRIMARY KEY (created_at ASC)                           │
│                                                         │
│  Tablet-1     Tablet-2      Tablet-3      Tablet-4     │
│  [Jan-Mar]    [Apr-Jun]     [Jul-Sep]     [Oct-Dec]    │
│                                                         │
│  Pros: Efficient range scans, ordered iteration         │
│  Cons: Hot spots on latest partition (time-series)      │
└─────────────────────────────────────────────────────────┘

Composite:
  PRIMARY KEY ((tenant_id) HASH, created_at DESC)
  → Hash-partition by tenant, range-ordered within tenant
```

### Automatic Tablet Splitting

```
Trigger: tablet_size > tablet_split_low_phase_size_threshold_bytes (1GB default)

Before split:
  Tablet-A: [0000 ─────────────────────── 7FFF] (2GB)

After split:
  Tablet-A: [0000 ─────── 3FFF] (1GB)
  Tablet-B: [4000 ─────── 7FFF] (1GB)   ← New tablet, new Raft group

Split is online (no downtime), orchestrated by YB-Master.
```

### Multi-Region Deployment Topologies

```
1. Synchronous Multi-AZ (Single Region):
   - RF=3 across 3 AZs
   - Write latency: ~2-4ms
   - Survives: 1 AZ failure

2. Synchronous Multi-Region (Stretched):
   - RF=3 across 3 regions
   - Write latency: ~50-200ms (cross-region Raft)
   - Survives: 1 region failure
   - Use: when RPO=0 required globally

3. Geo-Partitioned:
   - Data pinned to region via tablespaces
   - Write latency: ~2-4ms (local writes)
   - Survives: 1 AZ per region
   - Use: data sovereignty, low-latency local access

4. xCluster (Active-Passive):
   - Async replication, RPO=seconds
   - Write latency: local only (~2-4ms)
   - RTO: minutes (manual failover)

5. xCluster (Active-Active):
   - Bidirectional async replication
   - Last-writer-wins conflict resolution
   - Use: multi-region writes with eventual consistency
```

---

## Production Setup

### Cluster Deployment

```bash
# Option 1: yugabyted (simplest, dev/small prod)
yugabyted start --base_dir=/data/yb1 \
  --advertise_address=10.0.1.1 \
  --cloud_location=aws.us-east-1.us-east-1a \
  --fault_tolerance=zone

yugabyted start --base_dir=/data/yb2 \
  --advertise_address=10.0.1.2 \
  --join=10.0.1.1 \
  --cloud_location=aws.us-east-1.us-east-1b \
  --fault_tolerance=zone

yugabyted start --base_dir=/data/yb3 \
  --advertise_address=10.0.1.3 \
  --join=10.0.1.1 \
  --cloud_location=aws.us-east-1.us-east-1c \
  --fault_tolerance=zone

# Option 2: Kubernetes Operator
# Install YugabyteDB Operator
helm install yugabyte-operator yugabytedb/yugabyte-operator \
  --namespace yb-operator --create-namespace

# Deploy cluster
cat <<EOF | kubectl apply -f -
apiVersion: operator.yugabyte.io/v1alpha1
kind: YBCluster
metadata:
  name: prod-cluster
spec:
  replicationFactor: 3
  master:
    replicas: 3
    storage:
      size: 50Gi
    resources:
      requests:
        cpu: 2
        memory: 4Gi
  tserver:
    replicas: 6
    storage:
      size: 500Gi
      storageClass: gp3-iops
    resources:
      requests:
        cpu: 8
        memory: 32Gi
    gflags:
      ysql_num_shards_per_tserver: "4"
      rocksdb_compact_flush_rate_limit_bytes_per_sec: "268435456"
EOF
```

### Performance Tuning

```bash
# Key TServer gflags for production
--ysql_num_shards_per_tserver=8         # tablets per table per tserver (default: 8)
--yb_num_shards_per_tserver=8           # YCQL tablets per table per tserver
--tablet_split_low_phase_size_threshold_bytes=5368709120  # 5GB before split
--rocksdb_compact_flush_rate_limit_bytes_per_sec=268435456  # 256MB/s compaction
--rpc_workers_limit=256                 # RPC thread pool
--ysql_max_connections=300              # per tserver
--ysql_sequence_cache_minval=100        # batch sequence values

# Key Master gflags
--load_balancer_max_concurrent_tablet_remote_bootstraps=4
--load_balancer_max_over_replicated_tablets=3

# OS tuning (Linux)
echo 'vm.swappiness=0' >> /etc/sysctl.conf
echo 'net.core.somaxconn=65535' >> /etc/sysctl.conf
echo 'never' > /sys/kernel/mm/transparent_hugepage/enabled

# Recommended hardware per TServer (production):
# - 8-16 vCPUs
# - 32-64 GB RAM
# - NVMe SSD (3000+ IOPS)
# - 10 Gbps network
```

### Monitoring

```
Built-in Web UIs:
  - YB-Master:  http://<master-ip>:7000  (cluster overview, tablet map)
  - YB-TServer: http://<tserver-ip>:9000 (tablet details, metrics)
  - YSQL:       http://<tserver-ip>:13000 (active queries, connections)

Prometheus Integration:
  - Master metrics:  http://<master>:7000/prometheus-metrics
  - TServer metrics: http://<tserver>:9000/prometheus-metrics
  - Key metrics to alert on:

┌────────────────────────────────────────────────────────────────┐
│ Metric                              │ Alert Threshold          │
├────────────────────────────────────────────────────────────────┤
│ handler_latency_yb_tserver_* (p99)  │ > 100ms                 │
│ tablet_data_size (per tablet)       │ > 50GB (consider split) │
│ log_bytes_logged (WAL growth)       │ > 100MB/s sustained     │
│ cpu_stime + cpu_utime               │ > 80%                   │
│ generic_heap_size                   │ > 80% of RAM            │
│ rpc_connections_alive               │ > 80% of max            │
│ follower_lag_ms                     │ > 5000ms                │
│ leader_lease_lost                   │ any occurrence           │
│ transaction_conflicts               │ spike detection          │
└────────────────────────────────────────────────────────────────┘
```

### Backup and Restore

```bash
# Option 1: ysql_dump (logical, small databases)
ysql_dump -h 10.0.1.1 -p 5433 -U yugabyte --no-tablespaces mydb > backup.sql

# Option 2: Distributed snapshots (recommended for production)
# Create snapshot
yb-admin -master_addresses master1:7100 create_snapshot ysql.mydb

# List snapshots
yb-admin list_snapshots

# Export snapshot to external storage (S3)
yb-admin export_snapshot <snapshot_id> <s3://bucket/path>

# Restore from snapshot
yb-admin import_snapshot <s3://bucket/path/snapshot_meta>
yb-admin restore_snapshot <snapshot_id>

# Point-in-time recovery (PITR)
yb-admin create_snapshot_schedule 1440 10080 ysql.mydb
# (snapshot every 1440 min, retain 10080 min = 7 days)

# Restore to specific time
yb-admin restore_snapshot_schedule <schedule_id> "2024-01-15 10:30:00"
```

### Rolling Upgrades

```bash
# YugabyteDB supports online rolling upgrades (zero downtime)

# Step 1: Upgrade YB-Masters one at a time
for master in master1 master2 master3; do
  # Stop master
  ssh $master "yugabyted stop --base_dir=/data/yb"
  # Install new version
  ssh $master "rpm -Uvh yugabyte-<new-version>.rpm"
  # Start master
  ssh $master "yugabyted start --base_dir=/data/yb --upgrade"
  # Wait for master to rejoin Raft group
  sleep 30
done

# Step 2: Upgrade TServers one at a time
for tserver in ts1 ts2 ts3 ts4 ts5 ts6; do
  # Blacklist node (moves leaders away)
  yb-admin change_blacklist ADD $tserver:9100
  sleep 60  # wait for leader transfer

  ssh $tserver "yugabyted stop --base_dir=/data/yb"
  ssh $tserver "rpm -Uvh yugabyte-<new-version>.rpm"
  ssh $tserver "yugabyted start --base_dir=/data/yb --upgrade"

  # Remove from blacklist
  yb-admin change_blacklist REMOVE $tserver:9100
  sleep 30
done

# Step 3: Finalize upgrade (enables new features)
yb-admin -master_addresses master1:7100 upgrade_ysql
```

### Connection Pooling

```bash
# PgBouncer (recommended for YSQL)
# /etc/pgbouncer/pgbouncer.ini

[databases]
mydb = host=yb-tserver-service port=5433 dbname=mydb

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
pool_mode = transaction          # MUST use transaction mode with YugabyteDB
max_client_conn = 10000
default_pool_size = 50           # per user/db pair
min_pool_size = 10
reserve_pool_size = 5
server_idle_timeout = 300

# YugabyteDB Smart Driver (built-in connection pooling + topology awareness)
# JDBC connection string:
jdbc:yugabytedb://node1:5433,node2:5433,node3:5433/mydb?
  load-balance=true&
  topology-keys=aws.us-east-1.us-east-1a,aws.us-east-1.us-east-1b&
  yb-servers-refresh-interval=300
```

---

## Benchmarks

### Latency (RF=3, 3-AZ single region)

| Operation | p50 | p99 | p999 |
|-----------|-----|-----|------|
| Single-row read (by PK) | 1.2ms | 3ms | 8ms |
| Single-row write | 2.5ms | 5ms | 12ms |
| Short txn (2 statements) | 4ms | 10ms | 25ms |
| Index scan (100 rows) | 5ms | 15ms | 40ms |
| Distributed txn (cross-tablet) | 8ms | 20ms | 50ms |
| Follower read (stale) | 0.8ms | 2ms | 5ms |

### Throughput (per node, 8 vCPU, 32GB RAM)

| Workload | Ops/sec | Notes |
|----------|---------|-------|
| 100% reads (YCSB-B) | 50K | 1KB rows |
| 50/50 read/write (YCSB-A) | 30K | 1KB rows |
| 100% writes | 20K | With Raft replication |
| YCQL single-row | 75K reads | Lower overhead than YSQL |

### Scale-out linearity

```
Nodes:   3    6    9    12    18    24
         │    │    │     │     │     │
Reads:  150K 295K 440K  580K  870K  1.15M  ops/sec
Writes:  60K 118K 175K  232K  345K  460K   ops/sec
         │    │    │     │     │     │
         └────┴────┴─────┴─────┴─────┘
         ~Linear scaling (90-95% efficiency)
```

---

## Quick Reference

```
Ports:
  7000  - YB-Master Web UI
  7100  - YB-Master RPC
  9000  - YB-TServer Web UI
  9100  - YB-TServer RPC
  5433  - YSQL (PostgreSQL wire protocol)
  9042  - YCQL (Cassandra wire protocol)
  13000 - YSQL Web UI (active queries)

CLI Tools:
  yugabyted   - Simplified cluster management
  yb-admin    - Advanced cluster administration
  yb-ctl      - Local dev cluster management
  ysqlsh      - PostgreSQL-compatible shell
  ycqlsh      - Cassandra-compatible shell
  yb-ts-cli   - TServer diagnostics
```
