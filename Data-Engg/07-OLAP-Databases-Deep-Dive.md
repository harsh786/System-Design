# OLAP Databases - Staff Architect Deep Dive

## Table of Contents
1. [OLAP Fundamentals](#1-olap-fundamentals)
2. [ClickHouse](#2-clickhouse)
3. [Apache Druid](#3-apache-druid)
4. [Apache Pinot](#4-apache-pinot)
5. [Google BigQuery](#5-google-bigquery)
6. [Amazon Redshift](#6-amazon-redshift)
7. [Snowflake](#7-snowflake)
8. [DuckDB](#8-duckdb)
9. [Apache Doris/StarRocks](#9-apache-dorisstarrocks)
10. [Comparison Matrix](#10-comparison-matrix)

---

## 1. OLAP Fundamentals

### OLAP vs OLTP

```
┌───────────────────┬──────────────────┬──────────────────┐
│ Dimension         │ OLTP             │ OLAP             │
├───────────────────┼──────────────────┼──────────────────┤
│ Workload          │ Read/Write       │ Read-heavy       │
│ Queries           │ Point lookups    │ Aggregations     │
│ Data model        │ Normalized (3NF) │ Denormalized     │
│ Rows per query    │ 1-100            │ Millions-Billions│
│ Columns per query │ Many (SELECT *)  │ Few (SELECT agg) │
│ Latency           │ < 10ms           │ 100ms - minutes  │
│ Concurrency       │ Thousands        │ 10s - 100s       │
│ Storage format    │ Row-oriented     │ Column-oriented  │
│ Updates           │ Frequent         │ Batch / append   │
│ Transaction       │ ACID critical    │ Less critical    │
│ Examples          │ MySQL, Postgres  │ ClickHouse, BQ   │
└───────────────────┴──────────────────┴──────────────────┘
```

### Columnar Storage Advantage

```
ROW STORAGE (OLTP):
┌──────────┬────────────┬────────┬────────┐
│ order_id │ customer   │ amount │ status │
├──────────┼────────────┼────────┼────────┤
│ 1        │ Alice      │ 100.00 │ done   │ → Row 1 on disk
│ 2        │ Bob        │ 250.00 │ pending│ → Row 2 on disk
│ 3        │ Charlie    │ 75.00  │ done   │ → Row 3 on disk
└──────────┴────────────┴────────┴────────┘

SELECT SUM(amount) → Must read ALL columns (wasteful!)

COLUMN STORAGE (OLAP):
order_id: [1, 2, 3, ...]           → Column file 1
customer: [Alice, Bob, Charlie, ...] → Column file 2
amount:   [100.00, 250.00, 75.00, ...] → Column file 3
status:   [done, pending, done, ...] → Column file 4

SELECT SUM(amount) → Only read "amount" column (fast!)

Benefits:
  1. Read only needed columns (I/O reduction)
  2. Better compression (same data type, similar values)
  3. Vectorized execution (SIMD operations on column arrays)
  4. Late materialization (work with column indices, construct rows last)
```

### Vectorized Execution

```
TUPLE-AT-A-TIME (traditional):
  for each row:
    if row.status == 'done':
      sum += row.amount
  → Virtual function calls per row, poor CPU cache usage

VECTORIZED (modern OLAP):
  Load 1024 values of 'status' column into register
  Evaluate filter: mask = [1, 0, 1, ...]  (SIMD)
  Load 1024 values of 'amount' column
  Apply mask + sum (SIMD)
  → 10-100x faster, CPU pipeline friendly, no virtual dispatch

SIMD example (AVX-512):
  Process 8 doubles (64-bit) per instruction
  Sum: 8 additions in 1 CPU cycle
  Throughput: ~10 billion rows/second/core for simple aggregations
```

---

## 2. ClickHouse

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     CLICKHOUSE CLUSTER                        │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Shard 1    │  │   Shard 2    │  │   Shard 3    │       │
│  │              │  │              │  │              │       │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │       │
│  │ │Replica 1 │ │  │ │Replica 1 │ │  │ │Replica 1 │ │       │
│  │ │(primary) │ │  │ │(primary) │ │  │ │(primary) │ │       │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │       │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │       │
│  │ │Replica 2 │ │  │ │Replica 2 │ │  │ │Replica 2 │ │       │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │         ClickHouse Keeper (replaces ZooKeeper)        │    │
│  │         Raft-based consensus for metadata             │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### MergeTree Family

```sql
-- MergeTree: Base engine, no dedup/aggregation
CREATE TABLE events (
    event_date Date,
    event_time DateTime,
    user_id UInt64,
    event_type String,
    amount Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_type, user_id, event_time)
TTL event_date + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- ReplacingMergeTree: Deduplication by ORDER BY key
-- Keeps latest version (by ver column)
CREATE TABLE users (
    user_id UInt64,
    name String,
    email String,
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY user_id;
-- NOTE: Dedup happens at merge time, not query time!
-- Use FINAL to force dedup at query: SELECT * FROM users FINAL;

-- SummingMergeTree: Pre-aggregate numeric columns
CREATE TABLE metrics (
    date Date,
    dimension String,
    impressions UInt64,
    clicks UInt64,
    cost Float64
) ENGINE = SummingMergeTree((impressions, clicks, cost))
PARTITION BY toYYYYMM(date)
ORDER BY (date, dimension);
-- Rows with same ORDER BY key are summed at merge time

-- AggregatingMergeTree: Complex aggregations with AggregateFunction
CREATE TABLE metrics_agg (
    date Date,
    dimension String,
    uniq_users AggregateFunction(uniq, UInt64),
    avg_amount AggregateFunction(avg, Float64)
) ENGINE = AggregatingMergeTree()
ORDER BY (date, dimension);

-- CollapsingMergeTree: Track state changes with sign column
CREATE TABLE orders_state (
    order_id UInt64,
    status String,
    amount Float64,
    sign Int8  -- 1 = insert, -1 = cancel previous
) ENGINE = CollapsingMergeTree(sign)
ORDER BY order_id;
-- Update: Insert (sign=-1, old values) + Insert (sign=1, new values)
```

### ClickHouse Internals: Parts, Partitions, Granules

```
Table data on disk:
/var/lib/clickhouse/data/db/events/

Partition: toYYYYMM(event_date)
├── 202401_1_5_2/           ← Part (merged from parts 1-5, merge level 2)
│   ├── checksums.txt
│   ├── columns.txt
│   ├── count.txt
│   ├── event_date.bin      ← Column data (compressed)
│   ├── event_date.mrk3     ← Marks (index into column data)
│   ├── event_time.bin
│   ├── event_time.mrk3
│   ├── user_id.bin
│   ├── user_id.mrk3
│   ├── primary.idx         ← Primary key index (sparse)
│   └── ...
├── 202401_6_6_0/           ← Unmerged part
└── 202402_1_3_1/           ← Different partition

GRANULE = 8192 rows (index_granularity)
Primary index stores first value of each granule
For 1 billion rows: ~122K index entries (fits in memory!)

Query: WHERE user_id = 12345
1. Binary search primary index → find granule range
2. Read only those granules from column files
3. Filter within granules
```

### Materialized Views

```sql
-- Source table
CREATE TABLE events_raw (
    timestamp DateTime,
    user_id UInt64,
    event_type String,
    properties String
) ENGINE = MergeTree()
ORDER BY (event_type, timestamp);

-- Materialized view: auto-populated from inserts to source
CREATE MATERIALIZED VIEW events_hourly_mv
ENGINE = SummingMergeTree()
ORDER BY (hour, event_type)
AS SELECT
    toStartOfHour(timestamp) AS hour,
    event_type,
    count() AS event_count,
    uniqExact(user_id) AS unique_users
FROM events_raw
GROUP BY hour, event_type;

-- Inserts to events_raw automatically populate events_hourly_mv
-- Query pre-aggregated data (100x+ faster than raw)
SELECT hour, event_type, sum(event_count), sum(unique_users)
FROM events_hourly_mv
WHERE hour >= '2024-01-01'
GROUP BY hour, event_type;
```

---

## 3. Apache Druid

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        APACHE DRUID                               │
│                                                                    │
│  QUERY PATH:                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐            │
│  │  Router  │───▶│  Broker  │───▶│  Historical      │            │
│  │ (LB/API) │    │ (scatter/│    │  (immutable segs)│            │
│  │          │    │  gather) │    │                  │            │
│  └──────────┘    └──────────┘    └──────────────────┘            │
│                       │                                           │
│                       └────────▶ ┌──────────────────┐            │
│                                  │  MiddleManager    │            │
│  INGESTION:                      │  (real-time segs) │            │
│  ┌──────────────┐               └──────────────────┘            │
│  │  Overlord    │                                                │
│  │  (ingestion  │──▶ MiddleManagers (Peons)                      │
│  │   tasks)     │                                                │
│  └──────────────┘                                                │
│                                                                    │
│  COORDINATION:                                                    │
│  ┌──────────────┐    ┌──────────────────────────┐                │
│  │ Coordinator  │    │  Deep Storage (S3/HDFS)   │                │
│  │ (segment     │    │  + Metadata Store (MySQL) │                │
│  │  management) │    │  + ZooKeeper              │                │
│  └──────────────┘    └──────────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘
```

### Segments and Rollup

```
SEGMENT = Immutable columnar data file (5-10 million rows typically)

Segment structure:
  Time chunk: 2024-01-15T00:00:00/2024-01-15T01:00:00
  Datasource: page_views
  Version: 2024-01-15T00:00:00.000Z
  Partition: 0
  
  Contents:
  ├── version.bin       (metadata)
  ├── __time            (timestamp column, always present)
  ├── page_url          (dimension, dictionary encoded)
  ├── country           (dimension, bitmap indexed)
  ├── views             (metric, aggregated)
  └── unique_users      (metric, HyperLogLog sketch)

ROLLUP (pre-aggregation at ingestion):
  Raw: 
    2024-01-15 10:00:01, /home, US, 1 view
    2024-01-15 10:00:05, /home, US, 1 view
    2024-01-15 10:00:12, /home, EU, 1 view
  
  After rollup (granularity=MINUTE):
    2024-01-15 10:00:00, /home, US, 2 views, 2 unique_users
    2024-01-15 10:00:00, /home, EU, 1 view,  1 unique_user
  
  Compression: 3 rows → 2 rows (can be 10-100x in practice)
```

---

## 4. Apache Pinot

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        APACHE PINOT                               │
│                                                                    │
│  ┌──────────────┐                                                │
│  │  Controller  │  Cluster management, schema, table config       │
│  └──────┬───────┘                                                │
│         │                                                         │
│  ┌──────▼───────┐    ┌──────────────────┐                        │
│  │    Broker    │───▶│     Server       │                        │
│  │  (query     │    │                  │                        │
│  │   routing,  │    │  Offline Segments│ ← Batch ingested       │
│  │   scatter/  │    │  (immutable)     │   (Spark/Hadoop)       │
│  │   gather)   │    │                  │                        │
│  └──────────────┘    │  Realtime Segs  │ ← Stream ingested      │
│                      │  (mutable)      │   (Kafka)              │
│  ┌──────────────┐    │                  │                        │
│  │    Minion    │    └──────────────────┘                        │
│  │  (offline    │                                                │
│  │   tasks:     │                                                │
│  │   compaction,│                                                │
│  │   purge)     │                                                │
│  └──────────────┘                                                │
└──────────────────────────────────────────────────────────────────┘
```

### Star-Tree Index

```
Unique to Pinot: Pre-computed aggregation tree for fast lookups

Dimensions: [country, browser, OS]
Metrics: [impressions, clicks]

Star-Tree:
                     [*, *, *]  total: 1M impressions, 50K clicks
                    /    |     \
           [US,*,*]  [EU,*,*]  [APAC,*,*]
           /    \      /    \
    [US,Chrome,*] [US,Firefox,*]  ...
    /         \
[US,Chrome,Win] [US,Chrome,Mac]

Query: SELECT SUM(impressions) WHERE country='US' AND browser='Chrome'
→ Direct lookup to [US,Chrome,*] node → instant result!
No scanning millions of rows

Config:
  "starTreeIndexConfigs": [{
    "dimensionsSplitOrder": ["country", "browser", "os"],
    "skipStarNodeCreationForDimensions": [],
    "functionColumnPairs": ["SUM__impressions", "SUM__clicks"],
    "maxLeafRecords": 10000
  }]
```

---

## 5. Google BigQuery

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      GOOGLE BIGQUERY                              │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    Dremel Engine                           │    │
│  │  (Multi-level serving tree)                               │    │
│  │                                                            │    │
│  │      ┌─────────┐                                         │    │
│  │      │  Root    │ ← Aggregates results                   │    │
│  │      │  Server  │                                         │    │
│  │      └────┬─────┘                                         │    │
│  │       ┌───┼───┐                                          │    │
│  │       ▼   ▼   ▼                                          │    │
│  │     ┌───┐ ┌───┐ ┌───┐  ← Intermediate servers           │    │
│  │     │   │ │   │ │   │                                    │    │
│  │     └─┬─┘ └─┬─┘ └─┬─┘                                   │    │
│  │      ┌┴┐   ┌┴┐   ┌┴┐                                    │    │
│  │      │L│   │L│   │L│   ← Leaf servers (scan data)       │    │
│  │      └─┘   └─┘   └─┘                                    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              │                                    │
│  ┌──────────────────────────▼───────────────────────────┐       │
│  │                  Colossus (Storage)                    │       │
│  │  Capacitor format (columnar, compressed)              │       │
│  │  Automatic replication, encryption                    │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                    │
│  ┌──────────────────────────▼───────────────────────────┐       │
│  │                  Jupiter (Network)                     │       │
│  │  Petabit bisection bandwidth                          │       │
│  │  Decouples compute and storage                        │       │
│  └──────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────┘
```

### Key Features

```sql
-- Partitioning + Clustering
CREATE TABLE `project.dataset.events`
(
    event_id STRING,
    user_id STRING,
    event_type STRING,
    event_time TIMESTAMP,
    properties STRUCT<
        page STRING,
        referrer STRING,
        device STRUCT<type STRING, os STRING>
    >,
    amount FLOAT64
)
PARTITION BY DATE(event_time)      -- Partition pruning
CLUSTER BY user_id, event_type     -- Sort within partitions
OPTIONS(
    partition_expiration_days=365,
    require_partition_filter=true   -- Force partition filter
);

-- Nested/Repeated fields (avoid joins!)
SELECT
    event_id,
    properties.page,
    properties.device.os
FROM `project.dataset.events`
WHERE DATE(event_time) = '2024-01-15'
    AND event_type = 'page_view';

-- Approximate aggregation
SELECT APPROX_COUNT_DISTINCT(user_id) AS approx_users
FROM `project.dataset.events`
WHERE DATE(event_time) BETWEEN '2024-01-01' AND '2024-01-31';
-- Much faster than COUNT(DISTINCT ...) on billions of rows

-- Materialized views (auto-refreshed)
CREATE MATERIALIZED VIEW `project.dataset.daily_metrics` AS
SELECT
    DATE(event_time) AS event_date,
    event_type,
    COUNT(*) AS event_count,
    APPROX_COUNT_DISTINCT(user_id) AS unique_users
FROM `project.dataset.events`
GROUP BY event_date, event_type;
```

---

## 6. Amazon Redshift

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      AMAZON REDSHIFT                          │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                    Leader Node                        │    │
│  │  - SQL parsing and optimization                       │    │
│  │  - Query planning and distribution                    │    │
│  │  - Result aggregation                                 │    │
│  └──────────────────────┬───────────────────────────────┘    │
│                          │                                    │
│           ┌──────────────┼──────────────┐                    │
│           ▼              ▼              ▼                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Compute Node │ │ Compute Node │ │ Compute Node │        │
│  │              │ │              │ │              │        │
│  │ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────┐ │        │
│  │ │ Slice 0  │ │ │ │ Slice 0  │ │ │ │ Slice 0  │ │        │
│  │ │ Slice 1  │ │ │ │ Slice 1  │ │ │ │ Slice 1  │ │        │
│  │ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │        │
│  │              │ │              │ │              │        │
│  │ RA3: Managed │ │              │ │              │        │
│  │ Storage (S3) │ │              │ │              │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### Distribution Styles

```sql
-- KEY: Rows with same key on same node (co-locate for joins)
CREATE TABLE orders (
    order_id BIGINT,
    customer_id BIGINT,
    amount DECIMAL(10,2)
)
DISTSTYLE KEY
DISTKEY(customer_id)
SORTKEY(order_date);
-- Best for: Large fact tables joined on customer_id

-- ALL: Full copy on every node (small dimension tables)
CREATE TABLE regions (
    region_id INT,
    region_name VARCHAR(100)
)
DISTSTYLE ALL;
-- Best for: Small tables (< 1M rows) used in many joins

-- EVEN: Round-robin distribution
CREATE TABLE staging_data (...)
DISTSTYLE EVEN;
-- Best for: Tables not joined frequently

-- AUTO (default): Redshift chooses based on table size
CREATE TABLE events (...) DISTSTYLE AUTO;
```

---

## 7. Snowflake

### Multi-Cluster Shared Data Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        SNOWFLAKE                                  │
│                                                                    │
│  LAYER 1: CLOUD SERVICES (Brain)                                  │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Query parsing, optimization, metadata, access control,    │   │
│  │  infrastructure management, transaction management         │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  LAYER 2: VIRTUAL WAREHOUSES (Muscle - Compute)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  WH: ETL     │  │  WH: BI      │  │  WH: DS      │           │
│  │  Size: 2XL   │  │  Size: L     │  │  Size: XL    │           │
│  │  Clusters: 3 │  │  Clusters: 2 │  │  Clusters: 1 │           │
│  │              │  │              │  │              │           │
│  │  Auto-suspend│  │  Auto-scale  │  │              │           │
│  │  after 5 min │  │  1-5 clusters│  │              │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                         ▲ Independent, no contention              │
│                                                                    │
│  LAYER 3: STORAGE (Data - S3/Azure Blob/GCS)                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Micro-partitions (50-500MB compressed, columnar)          │   │
│  │  Automatic clustering, compression, encryption             │   │
│  │  Immutable files (copy-on-write for updates)               │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Key Features

```sql
-- Time Travel (up to 90 days on Enterprise)
SELECT * FROM orders AT(TIMESTAMP => '2024-01-15 10:00:00'::timestamp);
SELECT * FROM orders BEFORE(STATEMENT => '<query_id>');

-- Zero-Copy Clone (instant, no storage cost until changes)
CREATE TABLE orders_dev CLONE orders;
CREATE DATABASE analytics_dev CLONE analytics;
-- Cloned data shares storage until modified

-- Streams (CDC on Snowflake tables)
CREATE STREAM orders_changes ON TABLE orders;
-- Stream captures INSERTs, UPDATEs, DELETEs
-- Columns: METADATA$ACTION, METADATA$ISUPDATE, METADATA$ROW_ID

SELECT * FROM orders_changes;
-- Returns: action=INSERT/DELETE, is_update=true/false

-- Tasks (scheduled SQL)
CREATE TASK process_changes
    WAREHOUSE = etl_wh
    SCHEDULE = '5 MINUTE'
    WHEN SYSTEM$STREAM_HAS_DATA('orders_changes')
AS
    MERGE INTO orders_curated t
    USING orders_changes s ON t.order_id = s.order_id
    WHEN MATCHED AND s.METADATA$ACTION = 'DELETE' THEN DELETE
    WHEN MATCHED AND s.METADATA$ACTION = 'INSERT' THEN UPDATE SET *
    WHEN NOT MATCHED AND s.METADATA$ACTION = 'INSERT' THEN INSERT *;

-- Data Sharing (no data copy, real-time)
CREATE SHARE analytics_share;
GRANT USAGE ON DATABASE analytics TO SHARE analytics_share;
GRANT SELECT ON TABLE analytics.public.metrics TO SHARE analytics_share;
-- Consumer account can query shared data directly
```

---

## 8. DuckDB

### In-Process OLAP

```
┌──────────────────────────────────────────┐
│  Python Process / Application            │
│                                           │
│  ┌─────────────────────────────────────┐ │
│  │           DuckDB Engine              │ │
│  │                                       │ │
│  │  ┌──────────┐  ┌──────────────────┐ │ │
│  │  │ Vectorized│  │  Columnar        │ │ │
│  │  │ Execution │  │  Storage         │ │ │
│  │  │ (batches  │  │  (persistent or  │ │ │
│  │  │  of 2048) │  │   in-memory)     │ │ │
│  │  └──────────┘  └──────────────────┘ │ │
│  │                                       │ │
│  │  ┌──────────────────────────────┐   │ │
│  │  │  Zero-copy integration:       │   │ │
│  │  │  - Pandas DataFrames          │   │ │
│  │  │  - Apache Arrow               │   │ │
│  │  │  - Parquet files (direct)     │   │ │
│  │  │  - CSV files (direct)         │   │ │
│  │  │  - S3/GCS/HTTP (remote)       │   │ │
│  │  └──────────────────────────────┘   │ │
│  └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

```python
import duckdb

# Query Parquet files directly (no loading needed)
result = duckdb.sql("""
    SELECT 
        event_type,
        COUNT(*) AS cnt,
        AVG(amount) AS avg_amount
    FROM read_parquet('s3://bucket/events/*.parquet')
    WHERE event_date >= '2024-01-01'
    GROUP BY event_type
    ORDER BY cnt DESC
""").df()

# Query Pandas DataFrame (zero-copy via Arrow)
import pandas as pd
df = pd.read_csv('large_file.csv')
result = duckdb.sql("SELECT * FROM df WHERE amount > 100").df()

# Persistent database
con = duckdb.connect('analytics.duckdb')
con.sql("CREATE TABLE events AS SELECT * FROM read_parquet('events.parquet')")
con.sql("SELECT COUNT(*) FROM events").show()
```

---

## 9. Apache Doris/StarRocks

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    APACHE DORIS / STARROCKS                   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Frontend (FE) - Java                     │    │
│  │  Query parsing, planning, metadata, load coordination │    │
│  │  MySQL protocol compatible (connect with MySQL client)│    │
│  │  Leader + Followers (Raft-based HA)                   │    │
│  └──────────────────────┬───────────────────────────────┘    │
│                          │                                    │
│           ┌──────────────┼──────────────┐                    │
│           ▼              ▼              ▼                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │  Backend (BE)│ │  Backend (BE)│ │  Backend (BE)│        │
│  │  C++         │ │  C++         │ │  C++         │        │
│  │              │ │              │ │              │        │
│  │ Vectorized   │ │ Vectorized   │ │ Vectorized   │        │
│  │ execution    │ │ execution    │ │ execution    │        │
│  │              │ │              │ │              │        │
│  │ Tablet       │ │ Tablet       │ │ Tablet       │        │
│  │ storage      │ │ storage      │ │ storage      │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└──────────────────────────────────────────────────────────────┘

Key Features:
  - MySQL protocol wire-compatible
  - Vectorized execution engine (SIMD)
  - CBO with histogram statistics
  - Materialized views with automatic query rewriting
  - Real-time updates (UPSERT support)
  - Colocation join (data co-located for join elimination)
```

---

## 10. Comparison Matrix

### When to Use Which

```
┌──────────────┬───────────┬──────────┬───────────┬──────────┬──────────┐
│ Requirement  │ClickHouse│ Druid    │ Pinot     │ BigQuery │ Snowflake│
├──────────────┼───────────┼──────────┼───────────┼──────────┼──────────┤
│ Sub-second   │ ✓✓✓      │ ✓✓✓     │ ✓✓✓      │ ✓        │ ✓        │
│ queries      │           │          │           │          │          │
│ Real-time    │ ✓✓       │ ✓✓✓     │ ✓✓✓      │ ✓        │ ✓        │
│ ingestion    │           │          │           │          │          │
│ Ad-hoc SQL   │ ✓✓✓      │ ✓       │ ✓✓       │ ✓✓✓     │ ✓✓✓     │
│ Concurrency  │ ✓✓       │ ✓✓✓     │ ✓✓✓      │ ✓✓✓     │ ✓✓✓     │
│ (>1000 QPS)  │           │          │           │          │          │
│ Joins        │ ✓✓       │ ✗       │ ✓        │ ✓✓✓     │ ✓✓✓     │
│ Updates      │ ✓ (async)│ ✗       │ ✓ (upsert│ ✓✓      │ ✓✓✓     │
│ Managed      │ ClickHouse│ Imply   │ StarTree │ ✓✓✓     │ ✓✓✓     │
│ service      │ Cloud    │ Polaris │ Cloud    │ (native) │ (native) │
│ Cost (low    │ ✓✓✓      │ ✓       │ ✓✓       │ ✓✓      │ ✓        │
│ volume)      │           │          │           │          │          │
│ Operational  │ Medium   │ High    │ High     │ None     │ None     │
│ complexity   │           │          │           │(managed) │(managed) │
├──────────────┼───────────┼──────────┼───────────┼──────────┼──────────┤
│ Best for     │ General  │ Real-time│ User-    │ Ad-hoc   │ DW +     │
│              │ analytics│ event    │ facing   │ analytics│ governed │
│              │ logs     │ analytics│ analytics│ BI       │ data     │
└──────────────┴───────────┴──────────┴───────────┴──────────┴──────────┘

Decision guide:
  Need sub-second on pre-defined queries → Druid / Pinot (star-tree)
  Need flexible SQL on large datasets → ClickHouse / BigQuery
  Need full warehouse capabilities → Snowflake / BigQuery / Redshift
  Need embedded analytics → DuckDB
  Need real-time + historical → Druid/Pinot (Lambda ingestion)
  Need MySQL compatibility → Doris/StarRocks
  Cost-conscious, self-managed → ClickHouse
  Zero-ops, pay-per-query → BigQuery (serverless)
```
