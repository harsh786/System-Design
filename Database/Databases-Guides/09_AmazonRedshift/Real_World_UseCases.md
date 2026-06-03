# Amazon Redshift - Real World Use Cases & Production Guide

## Core Concepts

### Columnar Storage
```
Row-oriented (PostgreSQL):          Columnar (Redshift):
┌────┬───────┬─────┬───────┐       ┌────────────────────────┐
│ id │ name  │ age │ city  │       │ id:  1, 2, 3, 4, 5... │ Block 1
├────┼───────┼─────┼───────┤       ├────────────────────────┤
│ 1  │ Alice │ 30  │ NYC   │       │ name: Alice, Bob, ...  │ Block 2
│ 2  │ Bob   │ 25  │ LA    │       ├────────────────────────┤
│ 3  │ Carol │ 35  │ CHI   │       │ age: 30, 25, 35, ...   │ Block 3
└────┴───────┴─────┴───────┘       ├────────────────────────┤
                                    │ city: NYC, LA, CHI...  │ Block 4
                                    └────────────────────────┘
```

**Why columnar matters:**
- Analytics queries touch 3-5 columns out of 100+ → reads 95% less data
- Same-type data compresses 4-10x better
- CPU-friendly sequential scans within a column

### Zone Maps (Min/Max Metadata)
```
Each 1MB block stores min/max automatically:

Block 0: date [2024-01-01, 2024-01-15]  ← skip if query asks for March
Block 1: date [2024-01-16, 2024-01-31]  ← skip
Block 2: date [2024-02-01, 2024-02-14]  ← skip
Block 3: date [2024-03-01, 2024-03-15]  ← SCAN this block

WHERE date = '2024-03-10' → scans 1 block instead of 4
Sort keys maximize zone map effectiveness!
```

### Compression Encodings
| Encoding | Best For | Ratio |
|----------|----------|-------|
| AZ64 | Numeric/date (default, Amazon proprietary) | 4-8x |
| LZO | VARCHAR with high cardinality | 3-5x |
| ZSTD | General purpose, large VARCHAR | 4-8x |
| Delta | Sequential numbers (timestamps, IDs) | 10-20x |
| Runlength | Low cardinality sorted columns | 20-100x |
| Bytedict | < 256 distinct values | 5-10x |

```sql
-- Let Redshift choose (recommended):
CREATE TABLE events (
    event_id    BIGINT ENCODE AZ64,
    event_date  DATE   ENCODE AZ64,
    event_type  VARCHAR(20) ENCODE BYTEDICT,  -- ~10 distinct values
    user_id     BIGINT ENCODE AZ64,
    payload     VARCHAR(65535) ENCODE ZSTD
);

-- Analyze compression recommendations:
ANALYZE COMPRESSION events;
```

### Query Execution Flow
```
┌─────────────────────────────────────────────────────────┐
│                     CLIENT QUERY                         │
└─────────────────────┬───────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   LEADER NODE                            │
│  1. Parse SQL                                           │
│  2. Check Result Cache (hit? → return immediately)      │
│  3. Generate query plan (optimizer)                     │
│  4. Generate execution segments per slice               │
│  5. Distribute segments to compute nodes                │
└─────────────────────┬───────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────┐
│              COMPUTE NODES (parallel)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Slice 0  │  │ Slice 1  │  │ Slice 2  │  ...        │
│  │ - Scan   │  │ - Scan   │  │ - Scan   │             │
│  │ - Filter │  │ - Filter │  │ - Filter │             │
│  │ - Agg    │  │ - Agg    │  │ - Agg    │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       └──────────────┼──────────────┘                   │
│                      ▼                                  │
│              Redistribute / Broadcast                    │
│              (for JOINs if needed)                       │
└─────────────────────┬───────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────┐
│            LEADER NODE - Merge & Return                  │
└─────────────────────────────────────────────────────────┘
```

### Result Caching & Short Query Acceleration (SQA)
- **Result cache**: identical queries return in <2ms (cached for catalog changes)
- **SQA**: queries predicted to run <5s bypass WLM queues, run on dedicated resources
- Both are automatic, no configuration needed

### Materialized Views
```sql
CREATE MATERIALIZED VIEW mv_daily_revenue AS
SELECT
    date_trunc('day', order_date) AS day,
    product_category,
    SUM(revenue) AS total_revenue,
    COUNT(*) AS order_count
FROM orders
GROUP BY 1, 2;

-- Auto-refresh on schedule:
ALTER MATERIALIZED VIEW mv_daily_revenue AUTO REFRESH YES;

-- Query optimizer automatically rewrites queries to use MVs
SELECT product_category, SUM(revenue)
FROM orders
WHERE order_date >= '2024-01-01'
GROUP BY 1;
-- ↑ Redshift rewrites this to scan mv_daily_revenue instead
```

---

## MPP Architecture

```
                    ┌─────────────────────────┐
                    │      LEADER NODE        │
                    │  - SQL parsing          │
                    │  - Query optimization   │
                    │  - Result aggregation   │
                    │  - Client connections   │
                    │  (no data storage)      │
                    └────────────┬────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│  COMPUTE NODE 1   │ │  COMPUTE NODE 2   │ │  COMPUTE NODE N   │
│                   │ │                   │ │                   │
│ ┌──────┐┌──────┐ │ │ ┌──────┐┌──────┐ │ │ ┌──────┐┌──────┐ │
│ │Slice0││Slice1│ │ │ │Slice2││Slice3│ │ │ │SliceN││SliceN│ │
│ │ 1MB  ││ 1MB  │ │ │ │ 1MB  ││ 1MB  │ │ │ │ 1MB  ││ 1MB  │ │
│ │blocks││blocks│ │ │ │blocks││blocks│ │ │ │blocks││blocks│ │
│ └──────┘└──────┘ │ │ └──────┘└──────┘ │ │ └──────┘└──────┘ │
│                   │ │                   │ │                   │
│  Local SSD/Cache  │ │  Local SSD/Cache  │ │  Local SSD/Cache  │
└─────────┬─────────┘ └─────────┬─────────┘ └─────────┬─────────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │   REDSHIFT MANAGED      │
                    │   STORAGE (RMS)         │
                    │   S3-backed, RA3 only   │
                    └─────────────────────────┘
```

Each slice:
- Has dedicated CPU, memory, disk
- Processes its portion of data independently
- RA3.xlplus: 2 slices/node, RA3.4xlarge: 4 slices/node, RA3.16xlarge: 16 slices/node

---

## Distribution Styles

| Style | How Data Distributes | Best For | Caveat |
|-------|---------------------|----------|--------|
| KEY | Hash of column → specific slice | Large fact tables joined on that key | Skew if key is uneven |
| EVEN | Round-robin across all slices | No clear join key, staging tables | Redistributes on every join |
| ALL | Full copy on every node | Small dimension tables (<5M rows) | Slow writes, uses memory |
| AUTO | Redshift decides (starts ALL, switches to EVEN/KEY) | Default, let Redshift optimize | May not be optimal |

```sql
-- Fact table: distribute on most-joined key
CREATE TABLE fact_orders (
    order_id     BIGINT,
    customer_id  BIGINT,
    order_date   DATE,
    amount       DECIMAL(12,2)
)
DISTSTYLE KEY
DISTKEY (customer_id)
SORTKEY (order_date);

-- Dimension table: replicate to all nodes
CREATE TABLE dim_product (
    product_id   INT,
    name         VARCHAR(200),
    category     VARCHAR(50)
)
DISTSTYLE ALL;
```

### Sort Keys

**Compound sort key** (default): ordered left-to-right, effective only when query filters on leading columns
```sql
COMPOUND SORTKEY (year, month, day, region)
-- Good:  WHERE year = 2024 AND month = 3
-- Bad:   WHERE region = 'US'  (skips leading columns)
```

**Interleaved sort key**: equal weight to all key columns, good for unpredictable filter patterns
```sql
INTERLEAVED SORTKEY (region, product_category, order_date)
-- Good for any combination of these filters
-- Cost: VACUUM is 4x slower, not recommended for frequently-loaded tables
```

---

## Scalability Features

### Redshift Spectrum (Query S3 Directly)
```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   Redshift   │────▶│  Spectrum Layer      │────▶│    S3 Data Lake   │
│   Cluster    │     │  (thousands of nodes │     │  Parquet/ORC/CSV  │
│              │◀────│   auto-provisioned)  │◀────│  Partitioned      │
└──────────────┘     └─────────────────────┘     └──────────────────┘
```
```sql
-- Create external schema pointing to Glue catalog
CREATE EXTERNAL SCHEMA spectrum_schema
FROM DATA CATALOG
DATABASE 'my_lake_db'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftSpectrumRole';

-- Query S3 data alongside local tables
SELECT l.customer_id, SUM(s.amount)
FROM local_schema.customers l
JOIN spectrum_schema.historical_orders s
  ON l.customer_id = s.customer_id
WHERE s.year = 2023
GROUP BY 1;
```
- Cost: $5 per TB scanned from S3
- Use Parquet + partitioning to minimize scan

### Data Sharing (Zero-Copy)
```sql
-- Producer cluster:
CREATE DATASHARE sales_share;
ALTER DATASHARE sales_share ADD SCHEMA public;
ALTER DATASHARE sales_share ADD TABLE public.orders;
GRANT USAGE ON DATASHARE sales_share TO NAMESPACE 'consumer-namespace-id';

-- Consumer cluster:
CREATE DATABASE sales_db FROM DATASHARE sales_share
OF NAMESPACE 'producer-namespace-id';
SELECT * FROM sales_db.public.orders;
```
No data movement, no ETL, real-time access.

### Serverless vs Provisioned
| Aspect | Provisioned | Serverless |
|--------|-------------|------------|
| Pricing | Per-node-hour ($0.25-$13.04/hr) | Per RPU-hour ($0.375/RPU-hr) |
| Scaling | Manual resize or elastic | Automatic 8-512 RPU |
| Best for | Predictable, steady workloads | Bursty, variable workloads |
| Min cost | ~$180/mo (1x dc2.large) | $0 when idle |
| Concurrency | WLM queues + concurrency scaling | Built-in auto-scaling |

### WLM (Workload Management)
```sql
-- Create queue for short queries:
-- Max 15 concurrent, 30s timeout
-- Create queue for ETL:
-- Max 5 concurrent, 1hr timeout, 50% memory

-- Automatic WLM (recommended):
-- Redshift manages concurrency dynamically (up to 50 queries)
-- Concurrency scaling adds transient clusters for bursts
```

---

## Replication & High Availability

### Architecture
```
┌─────────────────── AZ-1 ───────────────────┐  ┌──────── AZ-2 ────────┐
│                                             │  │                       │
│  ┌─────────────────────────────────┐        │  │  Multi-AZ (RA3):     │
│  │  PRIMARY CLUSTER                │        │  │  ┌─────────────────┐ │
│  │  Leader + Compute Nodes         │        │  │  │ STANDBY CLUSTER │ │
│  │                                 │────────│──│──│ Auto-failover   │ │
│  │  Writes → Redshift Managed      │        │  │  │ RPO=0, RTO<30s  │ │
│  │  Storage (3 copies within AZ)   │        │  │  └─────────────────┘ │
│  └─────────────────────────────────┘        │  │                       │
│                                             │  └───────────────────────┘
│  Automated Snapshots → S3 (same region)     │
│  Cross-region Snapshots → S3 (DR region)    │
└─────────────────────────────────────────────┘

Recovery options:
- Node failure: automatic replacement (<5 min)
- AZ failure: Multi-AZ failover (RPO=0, RTO <30s)
- Region failure: restore cross-region snapshot (RTO ~hours)
```

### Snapshot Strategy
```
Automated snapshots:
- Every 8 hours OR every 5GB of changes (whichever first)
- Retained 1-35 days (default: 1)
- Free (included in cluster cost)

Manual snapshots:
- User-triggered, retained until deleted
- Cross-region copy for DR

Cross-region DR:
- Configure automatic copy to target region
- RTO: ~30-60 min for restore
- RPO: snapshot frequency (8hrs default, configurable)
```

### RA3 Managed Storage
- Data in S3, hot data cached on local NVMe SSDs
- Storage scales independently from compute
- $0.024/GB/month (pay only for what you store)
- Automatically tiers cold data to S3, hot to SSD

### Concurrency Scaling
- Additional clusters spun up automatically when queues fill
- First 1hr/day free per cluster credit
- Linear cost beyond free tier
- Read queries only (no writes to concurrency scaling clusters)

---

## 5 Real-World Use Cases

---

### 1. Lyft - Company-Wide BI & Analytics

**Problem**: 2000+ analysts need sub-minute query response on 500TB+ ride data

**Architecture**:
```
┌────────────┐    ┌──────────┐    ┌─────────────────────────────────┐
│ Ride Events│───▶│ Kafka    │───▶│ Spark ETL (EMR)                 │
│ 30M/day   │    │ Streams  │    │ - Deduplicate                   │
└────────────┘    └──────────┘    │ - Sessionize                    │
                                  │ - Write Parquet → S3            │
┌────────────┐                    └────────────────┬────────────────┘
│ App DBs    │───▶ CDC (Debezium) ──────────────┐  │
│ (Postgres) │                                   ▼  ▼
└────────────┘                    ┌─────────────────────────────────┐
                                  │        REDSHIFT CLUSTER          │
                                  │  Leader Node (ra3.16xlarge)      │
                                  │  ┌─────────┐ ┌─────────┐       │
                                  │  │Compute 1│ │Compute 2│ x16   │
                                  │  │ 16slice │ │ 16slice │       │
                                  │  └─────────┘ └─────────┘       │
                                  │                                  │
                                  │  fact_rides: DISTKEY(rider_id)   │
                                  │  SORTKEY(ride_start_time)        │
                                  │                                  │
                                  │  fact_pricing: DISTKEY(ride_id)  │
                                  │  SORTKEY(timestamp)              │
                                  │                                  │
                                  │  dim_drivers: DISTSTYLE ALL      │
                                  │  dim_cities:  DISTSTYLE ALL      │
                                  └───────────────┬─────────────────┘
                                                  │
                                  ┌───────────────▼─────────────────┐
                                  │  BI Tools: Looker, Mode, Jupyter │
                                  │  2000+ analysts, 50K queries/day │
                                  └─────────────────────────────────┘
```

**Table Design**:
```sql
CREATE TABLE fact_rides (
    ride_id         BIGINT ENCODE AZ64,
    rider_id        BIGINT ENCODE AZ64,
    driver_id       BIGINT ENCODE AZ64,
    city_id         INT ENCODE AZ64,
    ride_start_time TIMESTAMP ENCODE AZ64,
    ride_end_time   TIMESTAMP ENCODE AZ64,
    distance_miles  DECIMAL(8,2) ENCODE AZ64,
    fare_amount     DECIMAL(10,2) ENCODE AZ64,
    surge_multiplier DECIMAL(4,2) ENCODE AZ64,
    ride_status     VARCHAR(20) ENCODE BYTEDICT
)
DISTSTYLE KEY
DISTKEY (rider_id)
COMPOUND SORTKEY (ride_start_time, city_id);
-- 500TB, ~200B rows
```

**ETL Pipeline**:
- Spark on EMR writes Parquet to S3 (hourly micro-batches)
- COPY command loads into Redshift staging tables
- MERGE (upsert) into production tables
- Spectrum for historical data >90 days (cold tier on S3)

**Scale & Cost**:
- 16x RA3.16xlarge nodes = $3,340/hr on-demand (~$200K/mo)
- With 3-year reserved: ~$70K/month
- 500TB managed storage: ~$12K/month
- 50,000 queries/day, p50 latency: 3s, p95: 25s
- Concurrency scaling handles 3x burst during Monday morning dashboards

---

### 2. McDonald's - Customer Loyalty Analytics

**Problem**: Unified view of 40K restaurants, 50M loyalty members, personalize offers in real-time

**Architecture**:
```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ POS Systems      │  │ Mobile App       │  │ Delivery Partners│
│ 40K restaurants  │  │ 50M users        │  │ (UberEats, etc) │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                      │
         ▼                     ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Kinesis Data Streams                       │
│                    (500 shards, 500K events/sec)                  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Kinesis Firehose      │
                    │   → Parquet → S3        │
                    │   (5-min micro-batch)   │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────┐
│  S3 Data Lake   │  │   REDSHIFT CLUSTER   │  │  Redshift       │
│  (raw + curated)│  │   8x RA3.4xlarge     │  │  Spectrum       │
│                 │──│                       │──│  (historical)   │
└─────────────────┘  │  Leader Node          │  └─────────────────┘
                     │  ┌──────┐ ┌──────┐   │
                     │  │Node 1│ │Node 2│x8 │
                     │  │4slice│ │4slice│   │
                     │  └──────┘ └──────┘   │
                     │                       │
                     │  fact_transactions     │
                     │  DISTKEY(customer_id)  │
                     │  SORTKEY(txn_time)     │
                     │                       │
                     │  fact_loyalty_events   │
                     │  DISTKEY(customer_id)  │
                     │  SORTKEY(event_time)   │
                     │                       │
                     │  dim_restaurants: ALL  │
                     │  dim_menu_items: ALL   │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │  Tableau + Custom      │
                     │  Offer Engine (Lambda) │
                     │  Marketing Automation  │
                     └───────────────────────┘
```

**Table Design**:
```sql
CREATE TABLE fact_transactions (
    txn_id          BIGINT ENCODE AZ64,
    customer_id     BIGINT ENCODE AZ64,
    restaurant_id   INT ENCODE AZ64,
    txn_timestamp   TIMESTAMP ENCODE AZ64,
    order_total     DECIMAL(8,2) ENCODE AZ64,
    payment_method  VARCHAR(20) ENCODE BYTEDICT,
    channel         VARCHAR(10) ENCODE BYTEDICT,  -- POS/APP/DELIVERY
    loyalty_points  INT ENCODE AZ64,
    items_json      VARCHAR(65535) ENCODE ZSTD
)
DISTSTYLE KEY
DISTKEY (customer_id)
COMPOUND SORTKEY (txn_timestamp, restaurant_id);
-- ~80TB, 100B+ transactions historically

CREATE TABLE dim_restaurants (
    restaurant_id   INT ENCODE AZ64,
    name            VARCHAR(200) ENCODE LZO,
    country         VARCHAR(50) ENCODE BYTEDICT,
    region          VARCHAR(50) ENCODE BYTEDICT,
    city            VARCHAR(100) ENCODE LZO,
    format_type     VARCHAR(30) ENCODE BYTEDICT  -- Drive-thru/Dine-in/Express
)
DISTSTYLE ALL;
-- 40K rows, ALL distribution
```

**ETL Pipeline**:
- Kinesis → Firehose → Parquet on S3 (5-min windows)
- AWS Glue jobs: dedupe, enrich with geo data, write curated layer
- Redshift COPY from curated S3 (every 15 min)
- Nightly: full dim refresh, VACUUM on fact tables
- Spectrum: queries spanning >1 year hit S3 directly

**Scale & Cost**:
- 8x RA3.4xlarge: $832/hr on-demand → ~$50K/month (reserved: ~$20K/mo)
- 80TB managed storage: ~$2K/month
- Kinesis: ~$5K/month (500 shards)
- Total platform: ~$30K/month (reserved)
- Query volume: 10K/day, p50: 5s, p95: 45s

---

### 3. Nasdaq - Market Analytics & Compliance Reporting

**Problem**: Process 30B+ market events/day, regulatory reporting with audit trails, sub-second dashboard refresh

**Architecture**:
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Market Feeds    │  │ Trade Execution │  │ Compliance      │
│ 30B events/day │  │ Systems         │  │ Submissions     │
└───────┬─────────┘  └───────┬─────────┘  └───────┬─────────┘
        │                    │                     │
        ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│              AWS MSK (Kafka Managed)                          │
│              100+ partitions, 7-day retention                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    Flink on EMR         │
              │    - Aggregate ticks    │
              │    - Detect anomalies   │
              │    - Write to S3/RS     │
              └────────────┬────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 REDSHIFT CLUSTER                              │
│                 24x RA3.16xlarge                              │
│                                                              │
│   Leader Node                                                │
│   ┌────────┐┌────────┐┌────────┐┌────────┐                 │
│   │Node 01 ││Node 02 ││  ...   ││Node 24 │                 │
│   │16 slice││16 slice││        ││16 slice│  = 384 slices   │
│   └────────┘└────────┘└────────┘└────────┘                 │
│                                                              │
│   fact_market_events: DISTKEY(symbol_id)                     │
│   SORTKEY(event_timestamp, exchange_id)                      │
│                                                              │
│   fact_trades: DISTKEY(symbol_id)                            │
│   SORTKEY(trade_timestamp)                                   │
│                                                              │
│   fact_compliance_audit: DISTKEY(entity_id)                  │
│   SORTKEY(audit_timestamp)                                   │
│                                                              │
│   dim_symbols: ALL (50K instruments)                         │
│   dim_members: ALL (4K broker-dealers)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Compliance   │  │ Internal BI  │  │ Client       │
│ Reporting    │  │ Dashboards   │  │ Analytics    │
│ (SEC/FINRA)  │  │ (Tableau)    │  │ Portal       │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Table Design**:
```sql
CREATE TABLE fact_market_events (
    event_id         BIGINT ENCODE AZ64,
    symbol_id        INT ENCODE AZ64,
    exchange_id      SMALLINT ENCODE AZ64,
    event_timestamp  TIMESTAMP ENCODE AZ64,
    event_type       VARCHAR(10) ENCODE BYTEDICT,  -- TRADE/QUOTE/ORDER
    price            DECIMAL(12,6) ENCODE AZ64,
    quantity         BIGINT ENCODE AZ64,
    bid_price        DECIMAL(12,6) ENCODE AZ64,
    ask_price        DECIMAL(12,6) ENCODE AZ64,
    participant_id   INT ENCODE AZ64
)
DISTSTYLE KEY
DISTKEY (symbol_id)
COMPOUND SORTKEY (event_timestamp, exchange_id);
-- 2PB+ historical (Spectrum), 30TB hot in Redshift (rolling 30 days)
```

**ETL Pipeline**:
- Flink: real-time aggregation (1-min OHLCV bars) → direct Redshift INSERT
- Batch: S3 Parquet (hourly) → COPY into Redshift
- Compliance: immutable append-only tables, no UPDATEs
- 7-year retention via Spectrum on S3 (Glacier for >3yr)
- Materialized views for SEC/FINRA report pre-computation

**Scale & Cost**:
- 24x RA3.16xlarge: ~$500K/month on-demand, ~$180K reserved
- 2PB Spectrum storage (S3): ~$47K/month
- 30TB managed storage: ~$720/month
- Total: ~$250K/month (reserved + storage + Spectrum scans)
- 384 slices, 30B events ingested/day
- Query: p50 2s, p95 15s for compliance dashboards

---

### 4. Samsung - Mobile Device Telemetry

**Problem**: Telemetry from 2B+ Galaxy devices worldwide, crash analytics, feature usage, OTA update monitoring

**Architecture**:
```
┌───────────────────────────────────────────────────────────────┐
│  2B+ Galaxy Devices (Phones, Watches, Tablets, TVs)           │
│  Telemetry: crashes, battery, app usage, network quality      │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTPS (batched every 15min)
                                ▼
┌───────────────────────────────────────────────────────────────┐
│  API Gateway + Kinesis Data Streams (2000 shards)             │
│  ~2M events/sec peak                                          │
└───────────────────────────────┬───────────────────────────────┘
                                │
                   ┌────────────▼────────────┐
                   │  EMR (Spark Streaming)   │
                   │  - Parse/validate        │
                   │  - Enrich (device model) │
                   │  - Partition by date/    │
                   │    device_family         │
                   │  - Write Parquet → S3    │
                   └────────────┬────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                                       ▼
┌───────────────────────┐              ┌────────────────────────┐
│  S3 Data Lake         │              │  REDSHIFT CLUSTER       │
│  (Petabytes, all raw) │              │  12x RA3.16xlarge       │
│                       │◀── Spectrum──│                         │
│  Partitioned:         │              │  Leader                 │
│  /year/month/day/     │              │  ┌──────┐ x12 nodes    │
│   device_family/      │              │  │16slc │ = 192 slices │
└───────────────────────┘              │  └──────┘              │
                                       │                         │
                                       │  fact_crashes           │
                                       │  DISTKEY(device_model)  │
                                       │  SORTKEY(crash_time)    │
                                       │                         │
                                       │  fact_telemetry_daily   │
                                       │  DISTKEY(device_id)     │
                                       │  SORTKEY(report_date)   │
                                       │                         │
                                       │  dim_devices: ALL       │
                                       │  dim_app_versions: ALL  │
                                       └────────────┬───────────┘
                                                    │
                                       ┌────────────▼───────────┐
                                       │ Internal dashboards     │
                                       │ OTA rollout monitoring  │
                                       │ Crash triage system     │
                                       │ Product analytics       │
                                       └────────────────────────┘
```

**Table Design**:
```sql
CREATE TABLE fact_crashes (
    crash_id        BIGINT ENCODE AZ64,
    device_id       VARCHAR(64) ENCODE LZO,
    device_model    VARCHAR(50) ENCODE BYTEDICT,  -- ~500 models
    os_version      VARCHAR(20) ENCODE BYTEDICT,
    app_package     VARCHAR(100) ENCODE LZO,
    crash_time      TIMESTAMP ENCODE AZ64,
    crash_type      VARCHAR(20) ENCODE BYTEDICT,  -- ANR/CRASH/NATIVE
    stack_hash      VARCHAR(64) ENCODE LZO,
    region          VARCHAR(10) ENCODE BYTEDICT,
    carrier         VARCHAR(50) ENCODE BYTEDICT
)
DISTSTYLE KEY
DISTKEY (device_model)
COMPOUND SORTKEY (crash_time, os_version);
-- 50TB hot (30 days), 3PB cold on S3

-- Pre-aggregated daily rollup (materialized view):
CREATE MATERIALIZED VIEW mv_crash_daily AS
SELECT
    date_trunc('day', crash_time) AS day,
    device_model,
    os_version,
    crash_type,
    COUNT(*) AS crash_count,
    COUNT(DISTINCT device_id) AS affected_devices
FROM fact_crashes
GROUP BY 1,2,3,4;
```

**ETL Pipeline**:
- Spark Streaming: 5-min micro-batches → Parquet on S3
- COPY into Redshift every 15 minutes (hot 30-day window)
- Daily aggregation jobs refresh materialized views
- Spectrum for ad-hoc deep-dives into historical data
- Data lifecycle: hot (Redshift, 30d) → warm (S3-IA, 1yr) → cold (Glacier, 7yr)

**Scale & Cost**:
- 12x RA3.16xlarge: ~$250K/month reserved
- 3PB S3 storage: ~$70K/month (mixed tiers)
- EMR Spark cluster: ~$40K/month
- Total platform: ~$380K/month
- 2M events/sec ingestion, 50TB hot, 3PB cold
- Query: p50 4s, p95 30s

---

### 5. Electronic Arts (EA) - Gaming Analytics

**Problem**: Optimize player engagement, monetization, matchmaking across 500M+ player accounts, 10+ live-service titles

**Architecture**:
```
┌──────────────────────────────────────────────────────────────┐
│  Game Clients (FIFA, Apex, Battlefield, Sims, Madden...)     │
│  500M+ accounts, 100M+ MAU                                   │
│  Events: match results, purchases, sessions, social          │
└──────────────────────────────┬───────────────────────────────┘
                               │ 
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  Event Collection (Kinesis + custom ingest service)           │
│  Peak: 5M events/sec (new game launches)                     │
└──────────────────────────────┬───────────────────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │  Spark ETL (EMR)                 │
              │  - Sessionize player activity    │
              │  - Calculate engagement scores   │
              │  - Flag churn risk               │
              │  - Matchmaking fairness metrics  │
              └────────────────┬────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                    REDSHIFT CLUSTER                            │
│                    10x RA3.16xlarge                            │
│                                                               │
│  Leader Node                                                  │
│  ┌────────┐┌────────┐┌────────┐┌────────┐... x10            │
│  │Node 01 ││Node 02 ││Node 03 ││Node 10 │  = 160 slices    │
│  │16 slc  ││16 slc  ││16 slc  ││16 slc  │                  │
│  └────────┘└────────┘└────────┘└────────┘                  │
│                                                               │
│  fact_player_sessions: DISTKEY(player_id)                     │
│  SORTKEY(session_start, game_title)                           │
│                                                               │
│  fact_transactions: DISTKEY(player_id)                        │
│  SORTKEY(txn_time)                                            │
│                                                               │
│  fact_match_results: DISTKEY(match_id)                        │
│  SORTKEY(match_end_time)                                      │
│                                                               │
│  dim_players: DISTKEY(player_id)  -- 500M rows, too big for ALL│
│  dim_items: ALL  -- 50K virtual items                         │
│  dim_games: ALL  -- ~50 titles                                │
└──────────────────────────────┬───────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│ Game Teams   │    │ Monetization │    │ ML Platform       │
│ Dashboards   │    │ Analytics    │    │ (churn prediction,│
│ (Tableau)    │    │ (A/B tests)  │    │  matchmaking)     │
└──────────────┘    └──────────────┘    └──────────────────┘
```

**Table Design**:
```sql
CREATE TABLE fact_player_sessions (
    session_id      BIGINT ENCODE AZ64,
    player_id       BIGINT ENCODE AZ64,
    game_title_id   SMALLINT ENCODE AZ64,
    platform        VARCHAR(10) ENCODE BYTEDICT,  -- PS5/XBOX/PC/MOBILE
    session_start   TIMESTAMP ENCODE AZ64,
    session_end     TIMESTAMP ENCODE AZ64,
    duration_sec    INT ENCODE AZ64,
    mode_played     VARCHAR(30) ENCODE BYTEDICT,  -- RANKED/CASUAL/STORY
    matches_played  SMALLINT ENCODE AZ64,
    mtx_spend       DECIMAL(8,2) ENCODE AZ64,     -- in-session spending
    region          VARCHAR(10) ENCODE BYTEDICT
)
DISTSTYLE KEY
DISTKEY (player_id)
COMPOUND SORTKEY (session_start, game_title_id);
-- 200TB, ~1T+ sessions historically

CREATE TABLE fact_match_results (
    match_id        BIGINT ENCODE AZ64,
    game_title_id   SMALLINT ENCODE AZ64,
    match_end_time  TIMESTAMP ENCODE AZ64,
    duration_sec    INT ENCODE AZ64,
    mode            VARCHAR(30) ENCODE BYTEDICT,
    map_id          INT ENCODE AZ64,
    player_count    SMALLINT ENCODE AZ64,
    avg_skill_diff  DECIMAL(6,2) ENCODE AZ64,
    quitter_count   SMALLINT ENCODE AZ64
)
DISTSTYLE KEY
DISTKEY (match_id)
COMPOUND SORTKEY (match_end_time, game_title_id);
```

**ETL Pipeline**:
- Kinesis → S3 (Firehose, 5-min batches)
- Spark: sessionization, engagement scoring, churn features
- Hourly COPY into Redshift (hot 90-day window)
- Spectrum for historical player lifetime analytics
- ML feature store: UNLOAD to S3 → SageMaker training
- A/B test results computed as materialized views

**Scale & Cost**:
- 10x RA3.16xlarge: ~$210K/month reserved
- 200TB managed storage: ~$5K/month
- 2PB S3 (Spectrum): ~$47K/month
- EMR + Kinesis: ~$30K/month
- Total: ~$300K/month
- 5M events/sec peak, 160 slices, 20K queries/day
- Query: p50 3s, p95 20s

---

## Production Setup

### Node Type Selection

| Node Type | vCPU | RAM | Storage | Slices | Best For | On-Demand $/hr |
|-----------|------|-----|---------|--------|----------|----------------|
| dc2.large | 2 | 15GB | 160GB SSD | 2 | Dev/test, <500GB | $0.25 |
| dc2.8xlarge | 32 | 244GB | 2.56TB SSD | 16 | Fixed storage, hot data | $4.80 |
| ra3.xlplus | 4 | 32GB | 32TB RMS | 2 | Small-medium workloads | $1.086 |
| ra3.4xlarge | 12 | 96GB | 128TB RMS | 4 | General production | $3.26 |
| ra3.16xlarge | 48 | 384GB | 128TB RMS | 16 | Large-scale analytics | $13.04 |

**Decision guide**:
- < 500GB data, predictable: dc2.8xlarge (fast local SSD)
- Storage grows independently from compute: RA3 (almost always)
- Don't know yet: start with ra3.xlplus, resize later

### VACUUM & ANALYZE Automation

```sql
-- Redshift auto-runs VACUUM DELETE and ANALYZE in background
-- But for heavy write tables, schedule manual runs:

-- Check which tables need vacuum:
SELECT "table", unsorted, tbl_rows, vacuum_sort_benefit
FROM svv_table_info
WHERE unsorted > 5  -- more than 5% unsorted
ORDER BY vacuum_sort_benefit DESC;

-- Run during maintenance window:
VACUUM FULL fact_orders;          -- re-sorts + reclaims space
VACUUM DELETE ONLY fact_events;   -- just reclaim deleted rows (faster)
VACUUM SORT ONLY fact_sessions;   -- just re-sort (no space reclaim)

-- Update statistics for query planner:
ANALYZE fact_orders;
ANALYZE fact_orders PREDICATE COLUMNS;  -- only columns used in predicates

-- Automate via Lambda + EventBridge (nightly at 2am UTC):
-- Lambda executes: VACUUM DELETE ONLY on tables with >5% dead rows
-- Then: ANALYZE on tables with stale statistics
```

### Monitoring

```sql
-- Key STL/SVV system tables:

-- Slow queries (last 24h):
SELECT query, elapsed/1000000.0 AS sec, substring(querytxt,1,100)
FROM stl_query
WHERE elapsed > 30000000  -- > 30 seconds
AND starttime > GETDATE() - INTERVAL '24 hours'
ORDER BY elapsed DESC LIMIT 20;

-- Disk usage by table:
SELECT "table", size AS mb, tbl_rows, unsorted, stats_off
FROM svv_table_info
ORDER BY size DESC LIMIT 20;

-- Query queue waits (WLM):
SELECT query, service_class, total_queue_time/1000000.0 AS queue_sec
FROM stl_wlm_query
WHERE total_queue_time > 5000000  -- waited > 5s
ORDER BY total_queue_time DESC;

-- Distribution skew (data skew across slices):
SELECT trim(name) AS tablename,
       slice, num_values, minvalue, maxvalue
FROM svv_diskusage
WHERE name = 'fact_orders'
ORDER BY slice;

-- Alerts (missing stats, nested loops, etc):
SELECT * FROM stl_alert_event_log
WHERE event_time > GETDATE() - INTERVAL '24 hours';

-- CloudWatch metrics to alarm on:
-- - CPUUtilization > 80% sustained
-- - PercentageDiskSpaceUsed > 75% (DC2 only)
-- - ReadIOPS spike
-- - WLMQueueWaitTime > 30s
-- - ConcurrencyScalingSeconds (cost tracking)
```

### COPY Optimization

```sql
-- Best practices for loading data:

-- 1. Match file count to slice count (or multiples)
--    160 slices → split into 160, 320, 640 files
COPY fact_orders
FROM 's3://bucket/orders/2024/03/'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftLoadRole'
FORMAT PARQUET;  -- Parquet auto-handles compression + types

-- 2. For CSV/JSON, specify options:
COPY staging_events
FROM 's3://bucket/events/'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftLoadRole'
FORMAT CSV
GZIP                          -- compressed files
IGNOREHEADER 1
DATEFORMAT 'auto'
TIMEFORMAT 'auto'
MAXERROR 100                  -- tolerate some bad rows
COMPUPDATE ON                 -- auto-apply compression
STATUPDATE ON;                -- update statistics after load

-- 3. Use manifest for exact file control:
COPY fact_orders
FROM 's3://bucket/manifests/orders_2024_03.manifest'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftLoadRole'
MANIFEST
FORMAT PARQUET;

-- 4. UNLOAD to S3 (for ML, archival, sharing):
UNLOAD ('SELECT * FROM fact_orders WHERE order_date >= ''2024-01-01''')
TO 's3://bucket/unload/orders_2024/'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftUnloadRole'
FORMAT PARQUET
PARTITION BY (order_month)    -- Hive-style partitions
MAXFILESIZE 256 MB
ALLOWOVERWRITE;
```

### Performance Tips Checklist

1. **Distribution**: co-locate joined tables on same key (DISTKEY)
2. **Sort keys**: match your most common WHERE/ORDER BY columns
3. **Compression**: use ANALYZE COMPRESSION, trust AZ64 for numerics
4. **File splits**: COPY files = N * slice_count for parallel load
5. **Parquet**: always prefer over CSV (columnar, compressed, typed)
6. **VACUUM**: schedule during low-traffic windows
7. **Materialized views**: pre-compute expensive aggregations
8. **Result caching**: identical queries return in <2ms (automatic)
9. **Spectrum**: offload cold data, keep hot window in local storage
10. **Concurrency scaling**: enable for read-heavy burst workloads

---

## Cost Estimation Summary

| Workload Size | Config | Monthly Cost (Reserved) | Data Volume |
|---------------|--------|------------------------|-------------|
| Small | 2x ra3.xlplus | ~$1,600 | <1TB |
| Medium | 4x ra3.4xlarge | ~$9,500 | 1-10TB |
| Large | 8x ra3.4xlarge | ~$19,000 | 10-50TB |
| Enterprise | 16x ra3.16xlarge | ~$150,000 | 50-500TB |
| Mega | 24x ra3.16xlarge + Spectrum | ~$250,000 | 500TB-PB+ |

Additional costs:
- Managed storage (RA3): $0.024/GB/month
- Spectrum scans: $5/TB scanned
- Concurrency scaling: same rate as cluster (first 1hr/day free)
- Snapshots (beyond free): $0.024/GB/month
- Data transfer out: standard AWS rates

---

## Performance Benchmarks (Typical)

| Metric | Small (2-node) | Medium (8-node) | Large (24-node) |
|--------|----------------|-----------------|-----------------|
| Simple aggregation (1TB) | 8s | 2s | <1s |
| Complex JOIN (5 tables, 10TB) | 45s | 12s | 4s |
| COPY 100GB Parquet | 5 min | 90s | 30s |
| Concurrent users (sustained) | 10 | 50 | 200+ |
| Result cache hit | <2ms | <2ms | <2ms |
| Spectrum scan 1TB Parquet | 15s | 8s | 5s |
