# ClickHouse - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Column-Oriented Storage](#column-oriented-storage)
3. [MergeTree Engine Family](#mergetree-engine-family)
4. [Indexing & Data Skipping](#indexing--data-skipping)
5. [Distributed Architecture](#distributed-architecture)
6. [Replication & Sharding](#replication--sharding)
7. [Query Execution](#query-execution)
8. [Data Modeling Patterns](#data-modeling-patterns)
9. [Performance Optimization](#performance-optimization)
10. [Staff Architect Interview Questions](#staff-architect-interview-questions)
11. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### ClickHouse Design Philosophy
```
OLAP (Online Analytical Processing) optimized:
- Columnar storage (read only needed columns)
- Vectorized query execution (SIMD, batch processing)
- Massive parallelism (all cores for single query)
- Real-time ingestion + instant queries
- Sparse indexing (not every row, every N rows)
- Aggressive compression (columns compress better)

NOT designed for:
- OLTP (high-frequency single-row updates)
- Point lookups by arbitrary key
- Transactions (no ACID)
- Frequent UPDATEs/DELETEs
```

### Server Architecture
```
┌─────────────────────────────────────────────────┐
│              ClickHouse Server                    │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │            Query Pipeline                  │    │
│  │  SQL Parser → AST → Analyzer → Planner   │    │
│  │      → Optimizer → Execution DAG          │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         Execution Engine                   │    │
│  │  Vectorized (batches of 8192 rows)        │    │
│  │  SIMD instructions (SSE4.2, AVX2, AVX512) │    │
│  │  Parallel across cores                     │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         Storage Engine                     │    │
│  │  MergeTree family (columnar parts)        │    │
│  │  Background merges                         │    │
│  │  Mutations (async ALTER/DELETE)            │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         Replication (ZooKeeper/Keeper)     │    │
│  │  Replicated tables                        │    │
│  │  Distributed DDL                          │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

---

## Column-Oriented Storage

### Row vs Column Storage
```
Row-oriented (MySQL, PostgreSQL):
┌──────┬───────┬─────┬────────┐
│ id   │ name  │ age │ salary │
├──────┼───────┼─────┼────────┤
│ 1    │ Alice │ 30  │ 80000  │
│ 2    │ Bob   │ 25  │ 60000  │
│ 3    │ Carol │ 35  │ 90000  │
└──────┴───────┴─────┴────────┘
On disk: [1,Alice,30,80000][2,Bob,25,60000][3,Carol,35,90000]

Column-oriented (ClickHouse):
On disk:
  id.bin:     [1, 2, 3]
  name.bin:   [Alice, Bob, Carol]
  age.bin:    [30, 25, 35]
  salary.bin: [80000, 60000, 90000]

Benefits:
1. Read only needed columns (skip name/age for salary aggregation)
2. Better compression (similar values together)
3. SIMD-friendly (process column vectors)
4. Better CPU cache utilization

Compression ratios:
- Typical: 5-20x for analytics data
- With codec: LZ4 (fast, 3-5x), ZSTD (better, 5-10x)
- Specialized: Delta, DoubleDelta, Gorilla (time-series: 10-40x)
```

### Part Structure
```
MergeTree data is organized into "parts":

Table directory:
└── table_name/
    ├── 202401_1_5_1/          ← Part (merged from parts 1-5, level 1)
    │   ├── checksums.txt
    │   ├── columns.txt
    │   ├── count.txt
    │   ├── primary.idx        ← Sparse primary index
    │   ├── id.bin             ← Column data
    │   ├── id.mrk2            ← Mark file (index → offset)
    │   ├── name.bin
    │   ├── name.mrk2
    │   ├── age.bin
    │   ├── age.mrk2
    │   └── minmax_date.idx    ← Partition key min/max
    ├── 202401_6_6_0/          ← Part (single insert, level 0)
    └── 202402_7_10_2/         ← Part (different partition)

Part = immutable set of rows, sorted by ORDER BY key
Merge = background process combining parts (like LSM compaction)
```

---

## MergeTree Engine Family

### MergeTree (Base)
```sql
CREATE TABLE events (
    event_date Date,
    event_time DateTime,
    user_id UInt64,
    event_type String,
    properties String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)    -- Monthly partitions
ORDER BY (user_id, event_time)        -- Sort key (also primary key by default)
TTL event_time + INTERVAL 90 DAY     -- Auto-delete after 90 days
SETTINGS index_granularity = 8192;    -- Rows per index entry
```

### ReplacingMergeTree (Deduplication)
```sql
-- Keeps latest version of each row (by ORDER BY key)
CREATE TABLE user_profiles (
    user_id UInt64,
    name String,
    email String,
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)  -- Keep row with max updated_at
ORDER BY user_id;

-- IMPORTANT: Deduplication happens during merge (not guaranteed at query time!)
-- Use FINAL for guaranteed dedup: SELECT * FROM user_profiles FINAL;
-- Or: SELECT argMax(name, updated_at) FROM user_profiles GROUP BY user_id;
```

### AggregatingMergeTree (Pre-Aggregation)
```sql
-- Stores pre-aggregated states, merges on read
CREATE TABLE daily_stats (
    date Date,
    site_id UInt32,
    visits AggregateFunction(sum, UInt64),
    uniques AggregateFunction(uniq, UInt64)
) ENGINE = AggregatingMergeTree()
ORDER BY (date, site_id);

-- Insert with state functions:
INSERT INTO daily_stats
SELECT date, site_id, sumState(1), uniqState(user_id)
FROM events GROUP BY date, site_id;

-- Query with merge functions:
SELECT date, site_id, sumMerge(visits), uniqMerge(uniques)
FROM daily_stats GROUP BY date, site_id;
```

### SummingMergeTree
```sql
-- Automatically sums numeric columns during merge
CREATE TABLE page_views (
    date Date,
    page String,
    views UInt64,
    unique_users UInt64
) ENGINE = SummingMergeTree((views, unique_users))
ORDER BY (date, page);

-- Multiple inserts with same key → summed during merge
-- SELECT * may show partial sums (before merge)
-- SELECT sum(views) GROUP BY date, page → always correct
```

### CollapsingMergeTree / VersionedCollapsingMergeTree
```sql
-- For mutable data: Insert new state + cancel old state
CREATE TABLE sessions (
    user_id UInt64,
    session_start DateTime,
    duration UInt32,
    sign Int8  -- 1 = active state, -1 = cancelled state
) ENGINE = CollapsingMergeTree(sign)
ORDER BY (user_id, session_start);

-- Update: Insert cancellation (-1) + new state (1)
INSERT INTO sessions VALUES (1, '2024-01-15 10:00:00', 0, -1);   -- cancel old
INSERT INTO sessions VALUES (1, '2024-01-15 10:00:00', 3600, 1); -- new state

-- Query (handles non-merged pairs):
SELECT user_id, sum(duration * sign) FROM sessions GROUP BY user_id HAVING sum(sign) > 0;
```

---

## Indexing & Data Skipping

### Primary Index (Sparse)
```
Unlike B-Tree (every row indexed), ClickHouse indexes every Nth row:

Data (sorted by ORDER BY key):
Row 0:    user_id=1,    time=10:00
Row 1:    user_id=1,    time=10:01
...
Row 8191: user_id=5,    time=11:30    ← Granule boundary
Row 8192: user_id=5,    time=11:31    ← New granule
...
Row 16383: user_id=12,  time=14:00
Row 16384: user_id=12,  time=14:01

Primary index (sparse, in memory):
Granule 0: (user_id=1, time=10:00)
Granule 1: (user_id=5, time=11:31)
Granule 2: (user_id=12, time=14:01)
...

Query: WHERE user_id = 5
→ Binary search primary index
→ Read granule 1 (rows 8192-16383)
→ Skip all other granules

Index size: Extremely small (one entry per 8192 rows)
1 billion rows → ~122K index entries → fits in RAM
```

### Data Skipping Indexes
```sql
-- MinMax index
ALTER TABLE events ADD INDEX idx_amount minmax(amount) GRANULARITY 4;
-- Stores min/max per 4 granules (32768 rows)
-- Skips granules where range doesn't match

-- Set index (discrete values)
ALTER TABLE events ADD INDEX idx_status set(status, 100) GRANULARITY 2;
-- Stores unique values per 2 granules
-- Skips if value not in set

-- Bloom filter
ALTER TABLE events ADD INDEX idx_url bloom_filter(0.01) GRANULARITY 3;
-- 1% false positive rate
-- Good for: String equality, IN queries

-- Token bloom filter (for tokenized strings)
ALTER TABLE events ADD INDEX idx_message tokenbf_v1(10240, 3, 0) GRANULARITY 2;
-- Good for: LIKE '%word%' queries

-- N-gram bloom filter
ALTER TABLE events ADD INDEX idx_log ngrambf_v1(3, 10240, 3, 0) GRANULARITY 2;
-- Good for: Substring matches
```

---

## Distributed Architecture

### Cluster Topology
```
┌────────────────────────────────────────────────────────┐
│                  ClickHouse Cluster                      │
│                                                          │
│  Shard 1                    Shard 2                      │
│  ┌────────────────────┐    ┌────────────────────┐       │
│  │ Replica 1A         │    │ Replica 2A         │       │
│  │ (node1.ch.local)   │    │ (node3.ch.local)   │       │
│  └────────────────────┘    └────────────────────┘       │
│  ┌────────────────────┐    ┌────────────────────┐       │
│  │ Replica 1B         │    │ Replica 2B         │       │
│  │ (node2.ch.local)   │    │ (node4.ch.local)   │       │
│  └────────────────────┘    └────────────────────┘       │
│                                                          │
│  ZooKeeper / ClickHouse Keeper (coordination)           │
│  ┌─────┐  ┌─────┐  ┌─────┐                            │
│  │ ZK1 │  │ ZK2 │  │ ZK3 │                            │
│  └─────┘  └─────┘  └─────┘                            │
└────────────────────────────────────────────────────────┘

Distributed table (query layer):
CREATE TABLE events_distributed AS events_local
ENGINE = Distributed(cluster_name, database, events_local, rand());
-- Routes queries to all shards, aggregates results
-- rand() = random shard for inserts (or use sharding_key)
```

### Replication (ReplicatedMergeTree)
```sql
CREATE TABLE events ON CLUSTER my_cluster (
    event_date Date,
    user_id UInt64,
    event_type String
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/events', '{replica}')
PARTITION BY toYYYYMM(event_date)
ORDER BY (user_id, event_date);

-- ZooKeeper paths:
-- /clickhouse/tables/{shard}/events/replicas/{replica}
-- /clickhouse/tables/{shard}/events/log  (replication log)
-- /clickhouse/tables/{shard}/events/blocks  (deduplication)

-- Replication is:
-- - Asynchronous (eventual consistency between replicas)
-- - Part-level (entire parts replicated, not individual rows)
-- - Automatic (no manual setup beyond table creation)
-- - Deduplicating (same insert block won't be duplicated)
```

---

## Query Execution

### Vectorized Processing
```
Traditional (row-by-row):
for each row:
    read value
    apply function
    write result
→ Branch mispredictions, cache misses, no SIMD

Vectorized (column-batch):
for each column block (8192 values):
    load block into CPU registers (SIMD)
    apply function to entire block
    write block
→ No branches, cache-friendly, SIMD acceleration

Example: SUM(amount) WHERE status = 'completed'
1. Load status column block (8192 values)
2. SIMD compare: status == 'completed' → bitmask
3. Load amount column block
4. SIMD masked sum: sum only where bitmask = 1
5. Repeat for all blocks

Performance: 1-10 billion rows/second/core for simple aggregations
```

### Query Pipeline
```
SELECT user_id, count(), sum(amount)
FROM events
WHERE event_date >= '2024-01-01'
  AND event_type = 'purchase'
GROUP BY user_id
ORDER BY count() DESC
LIMIT 10;

Execution:
1. Partition pruning: Skip partitions outside date range
2. Primary index: Find relevant granules
3. Data skipping: Skip granules using secondary indexes
4. Column reading: Read only event_date, event_type, user_id, amount
5. Filtering: Vectorized WHERE evaluation
6. Aggregation: Hash table (parallel per thread, merge at end)
7. Sort: Top-N sort (partial, for LIMIT)
8. Return results
```

---

## Data Modeling Patterns

### Pre-Aggregation with Materialized Views
```sql
-- Raw events (high volume)
CREATE TABLE raw_events (
    timestamp DateTime,
    user_id UInt64,
    event_type String,
    amount Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (event_type, user_id, timestamp)
TTL timestamp + INTERVAL 7 DAY;  -- Keep raw for 7 days

-- Materialized view for real-time aggregation
CREATE MATERIALIZED VIEW hourly_stats
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, event_type)
AS SELECT
    toStartOfHour(timestamp) AS hour,
    event_type,
    count() AS event_count,
    sum(amount) AS total_amount,
    uniq(user_id) AS unique_users
FROM raw_events
GROUP BY hour, event_type;

-- Query aggregated data (much faster):
SELECT * FROM hourly_stats WHERE hour >= '2024-01-15 00:00:00';
```

### Denormalization with Dictionaries
```sql
-- External dictionary (enrichment at query time)
CREATE DICTIONARY user_dict (
    user_id UInt64,
    name String,
    country String,
    segment String
) PRIMARY KEY user_id
SOURCE(MYSQL(host 'mysql.host' port 3306 db 'users' table 'users'))
LIFETIME(MIN 300 MAX 600)
LAYOUT(HASHED());

-- Query with dictionary lookup (no JOIN needed):
SELECT 
    dictGet('user_dict', 'country', user_id) AS country,
    count() AS events
FROM raw_events
GROUP BY country;
-- Extremely fast: Dictionary is in-memory hash lookup
```

---

## Performance Optimization

### Insert Optimization
```sql
-- BATCH inserts (not single rows!)
-- Each INSERT creates a new part
-- Too many parts = "Too many parts" error + slow merges

-- Best practice: Insert in batches of 10K-100K rows
-- Or use Buffer table:
CREATE TABLE events_buffer AS events
ENGINE = Buffer(currentDatabase(), events, 
    16,    -- num_layers
    10,    -- min_time (seconds before flush)
    100,   -- max_time
    10000, -- min_rows
    1000000, -- max_rows
    10000000, -- min_bytes
    100000000  -- max_bytes
);

-- Insert into buffer, auto-flushes to main table
INSERT INTO events_buffer VALUES (...);

-- Async inserts (ClickHouse 21.11+):
SET async_insert = 1;
SET wait_for_async_insert = 0;
-- Server batches small inserts automatically
```

### Query Optimization
```sql
-- 1. Use PREWHERE (automatic in most cases)
SELECT * FROM events PREWHERE user_id = 123 WHERE event_type = 'click';
-- PREWHERE reads fewer columns first, filters, then reads remaining columns

-- 2. Use proper types (smaller = faster)
-- UInt8 (0-255) instead of UInt64 for small numbers
-- LowCardinality(String) for strings with < 10K unique values
-- Nullable() only when truly needed (adds overhead)

-- 3. Avoid SELECT * (columnar DB penalty)
SELECT user_id, count() FROM events GROUP BY user_id;  -- Fast
SELECT * FROM events;  -- Slow (reads ALL columns)

-- 4. Partition pruning
SELECT count() FROM events WHERE event_date = '2024-01-15';
-- Only reads partition 202401 (if partitioned by month)

-- 5. ORDER BY alignment
-- Query WHERE clause should match table ORDER BY prefix
-- Table ORDER BY (user_id, event_time)
-- Good: WHERE user_id = 123  (uses primary index)
-- Bad:  WHERE event_time > '2024-01-01'  (skips first key column)
```

---

## Staff Architect Interview Questions

**Q1: When would you choose ClickHouse over PostgreSQL or Elasticsearch for analytics?**
**A:**
- ClickHouse: Structured analytics, known queries, high-volume aggregations, time-series, real-time dashboards. 100-1000x faster than PostgreSQL for analytical queries on large datasets.
- PostgreSQL: Mixed OLTP+OLAP, complex transactions, small-medium datasets, ad-hoc queries with JOINs.
- Elasticsearch: Full-text search, unstructured logs, flexible schemas, approximate aggregations.

ClickHouse excels at: `SELECT count(), avg(amount) FROM events WHERE date >= '2024-01-01' GROUP BY user_segment` over billions of rows in milliseconds.

**Q2: How does ClickHouse handle mutations (UPDATE/DELETE)?**
**A:** ClickHouse handles mutations asynchronously:
1. `ALTER TABLE events DELETE WHERE user_id = 123` creates a mutation
2. Mutation rewrites affected parts in background (not in-place!)
3. Old parts marked for deletion, new parts created without deleted rows
4. This is expensive: rewrites entire parts
5. Not suitable for frequent row-level updates

Alternatives for mutable data:
- ReplacingMergeTree (dedup on merge, query with FINAL)
- CollapsingMergeTree (insert cancellation row)
- AggregatingMergeTree (merge pre-aggregated states)
- Sign column pattern (positive/negative state)

**Q3: Design a real-time analytics pipeline with ClickHouse.**
**A:**
```
Data sources → Kafka → ClickHouse (Kafka engine) → Materialized Views

Architecture:
1. Kafka Engine table (consumes from topic):
   CREATE TABLE events_queue
   ENGINE = Kafka('brokers', 'topic', 'group', 'JSONEachRow');

2. Materialized View (transforms & inserts):
   CREATE MATERIALIZED VIEW events_consumer TO events
   AS SELECT * FROM events_queue;

3. Pre-aggregation MVs:
   CREATE MATERIALIZED VIEW hourly_agg TO hourly_stats
   AS SELECT toStartOfHour(ts) h, count() cnt
   FROM events GROUP BY h;

4. Query layer:
   - Grafana → ClickHouse (direct query for dashboards)
   - API → ClickHouse (parameterized queries)
   
Throughput: 500K-2M events/second per node
Query latency: Sub-second for pre-aggregated, 1-5s for raw scans
```

**Q4: How would you handle joining large tables in ClickHouse?**
**A:**
ClickHouse JOIN limitations and strategies:
1. **Dictionary JOIN**: For dimension tables (< few GB), load into memory dictionary
2. **Broadcast JOIN**: Small right table broadcast to all nodes (default)
3. **IN subquery**: Often faster than JOIN for filtering
4. **Denormalization**: Pre-join at ingestion time (preferred for analytics)
5. **Distributed JOIN**: For large-large joins (expensive, avoid if possible)
6. **Join with ENGINE = Join**: Persistent in-memory join table

Best practice: Denormalize at write time, minimize JOINs at query time.

---

## Scenario-Based Questions

### Scenario 1: Design Event Analytics for 1 Billion Events/Day

```sql
-- Table design
CREATE TABLE events (
    event_date Date,
    event_time DateTime64(3),
    user_id UInt64,
    session_id String,
    event_type LowCardinality(String),
    page_url String,
    referrer String,
    device LowCardinality(String),
    country LowCardinality(String),
    properties String  -- JSON as string, extract with JSONExtract
) ENGINE = ReplicatedMergeTree()
PARTITION BY toYYYYMMDD(event_date)
ORDER BY (event_type, user_id, event_time)
TTL event_date + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Sizing:
-- 1B events × 200 bytes avg = 200GB/day raw
-- With compression (10x): ~20GB/day stored
-- 90 days retention: ~1.8TB total
-- Cluster: 3 shards × 2 replicas = 6 nodes
-- Each node: 16 cores, 64GB RAM, 2TB NVMe SSD

-- Pre-aggregation for dashboards:
CREATE MATERIALIZED VIEW dashboard_metrics
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, event_type, country)
AS SELECT
    toDate(event_time) AS date,
    event_type,
    country,
    count() AS events,
    uniq(user_id) AS users,
    uniq(session_id) AS sessions
FROM events
GROUP BY date, event_type, country;
```

### Scenario 2: Migrating from Elasticsearch to ClickHouse for Log Analytics

```
Why migrate:
- Elasticsearch: Expensive at scale (RAM-heavy, index overhead)
- ClickHouse: 5-10x better compression, faster aggregations
- ClickHouse: Lower hardware cost for same query performance

Migration approach:
1. Define log schema in ClickHouse:
   - Map Elasticsearch fields to ClickHouse columns
   - Use LowCardinality for low-cardinality strings
   - Use Nullable() sparingly (prefer defaults)

2. Dual-write period:
   - Logstash/Vector → Both ES and ClickHouse
   - Compare query results

3. Handle full-text search:
   - ClickHouse: tokenbf_v1 or ngrambf_v1 indexes for LIKE queries
   - For complex full-text: Keep small ES cluster for search, ClickHouse for analytics
   - Or: Use ClickHouse's full-text index (experimental in newer versions)

4. Replace Kibana dashboards with Grafana + ClickHouse plugin

Limitations to address:
- No true full-text search scoring (relevance ranking)
- No dynamic mapping (schema must be defined)
- Updates are expensive (append-only preferred)
```

