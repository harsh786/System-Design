# ClickHouse - Real World Use Cases & Production Guide

## Core Concepts

### Columnar Storage

```
Row-Oriented (PostgreSQL, MySQL):        Column-Oriented (ClickHouse):
┌────────┬──────────┬────────┬───────┐   ┌────────────────────────────────┐
│ row_id │ timestamp│ url    │ bytes │   │ timestamp: [t1, t2, t3, t4...]│
├────────┼──────────┼────────┼───────┤   ├────────────────────────────────┤
│   1    │   t1     │ /api   │  420  │   │ url:       [/api, /home, ...]  │
│   2    │   t2     │ /home  │  890  │   ├────────────────────────────────┤
│   3    │   t3     │ /api   │  350  │   │ bytes:     [420, 890, 350...]  │
└────────┴──────────┴────────┴───────┘   └────────────────────────────────┘

Why columnar wins for analytics:
- Query "SELECT avg(bytes)" reads ONLY the bytes column
- Similar values in a column → extreme compression (10-50x)
- SIMD vectorized processing on homogeneous data
- Benchmark: 1B rows scanned in <1 second on commodity hardware
```

### MergeTree Internals: Parts → Granules → Marks → Sparse Index

```
INSERT batch
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    DATA PART (immutable)                  │
│                                                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                │
│  │Granule 0│  │Granule 1│  │Granule 2│  ...            │
│  │8192 rows│  │8192 rows│  │8192 rows│                 │
│  └────┬────┘  └────┬────┘  └────┬────┘                 │
│       │             │             │                      │
│  ┌────▼─────────────▼─────────────▼────┐                │
│  │         primary.idx (sparse)         │                │
│  │  mark0: (2024-01-01, us-east)       │                │
│  │  mark1: (2024-01-01, us-west)       │                │
│  │  mark2: (2024-01-02, eu-west)       │                │
│  └──────────────────────────────────────┘                │
│                                                          │
│  Column files: timestamp.bin, url.bin, bytes.bin         │
│  Mark files:   timestamp.mrk2, url.mrk2, bytes.mrk2     │
└─────────────────────────────────────────────────────────┘

Background merges consolidate parts:
[Part1] [Part2] [Part3]  →  [Merged Part]
   └────────┴────────┘         (larger, fewer parts)
```

### Sparse Primary Index vs B-Tree

```
B-Tree (PostgreSQL):                    Sparse Index (ClickHouse):
┌─────────────┐                         ┌─────────────────────────┐
│  Root Node  │                         │ Mark 0 → granule 0      │
│  [50, 100]  │                         │ Mark 1 → granule 1      │
├──┬────┬──┬──┤                         │ Mark 2 → granule 2      │
│  ▼    ▼  ▼  │                         │ ...                     │
│Leaf  Leaf Leaf                        │ Mark N → granule N      │
│nodes nodes  │                         └─────────────────────────┘
└─────────────┘
                                        Index size: ~rows/8192 entries
Index for every row                     10B rows → ~1.2M entries
10B rows → huge index, RAM-heavy        Fits entirely in RAM (~MBs)
Random I/O per lookup                   Sequential scan of granules

Trade-off:
- B-Tree: O(log N) point lookups, expensive for scans
- Sparse: Skip entire granules, optimized for range scans
- ClickHouse reads only matching granules (data skipping)
```

### Data Skipping Indexes

```sql
-- Secondary indexes that allow skipping granules
CREATE TABLE events (
    timestamp DateTime,
    user_id UInt64,
    event_type String,
    properties String,
    -- Skip index: bloom filter on event_type
    INDEX idx_event_type event_type TYPE bloom_filter GRANULARITY 4,
    -- Skip index: min/max on user_id
    INDEX idx_user_id user_id TYPE minmax GRANULARITY 3,
    -- Skip index: token bloom for text search
    INDEX idx_props properties TYPE tokenbf_v1(10240, 3, 0) GRANULARITY 2
) ENGINE = MergeTree()
ORDER BY (timestamp);
```

### Vectorized Query Execution

```
Traditional (row-at-a-time):          ClickHouse (vectorized):
┌────────────────────┐                ┌─────────────────────────┐
│ for each row:      │                │ Load column chunk (64KB) │
│   read all columns │                │ Process entire vector    │
│   evaluate WHERE   │                │ using SIMD instructions  │
│   compute result   │                │ (AVX2/AVX-512)          │
│   emit row         │                │ Emit result batch       │
└────────────────────┘                └─────────────────────────┘

- Processes 8192 rows at a time in tight loops
- CPU pipeline-friendly: no branch mispredictions
- Cache-friendly: sequential memory access
- SIMD: single instruction processes 4-16 values
```

### Compression Codecs

| Codec | Best For | Ratio | Speed |
|-------|----------|-------|-------|
| LZ4 | Default, general purpose | 4-8x | Fastest decompression |
| ZSTD | Higher compression needed | 8-15x | Slower, better ratio |
| Delta | Monotonically increasing (timestamps) | 20-50x with LZ4 | Excellent |
| DoubleDelta | Timestamps with constant intervals | 50-100x | Excellent |
| Gorilla | Float metrics (small changes) | 10-30x | Excellent |
| T64 | Integers with limited range | 5-20x | Fast |

```sql
CREATE TABLE metrics (
    timestamp DateTime CODEC(DoubleDelta, LZ4),
    value Float64 CODEC(Gorilla, LZ4),
    host_id UInt32 CODEC(Delta, ZSTD),
    metric_name LowCardinality(String)  -- dictionary encoding
) ENGINE = MergeTree()
ORDER BY (metric_name, host_id, timestamp);
```

### Table Engines Comparison

| Engine | Use Case | Features |
|--------|----------|----------|
| MergeTree | Default analytics | Sorting, partitioning, TTL, sampling |
| ReplacingMergeTree | Deduplication by key | Eventually replaces duplicates |
| AggregatingMergeTree | Pre-aggregation | Stores intermediate aggregate states |
| SummingMergeTree | Counter/sum rollups | Automatically sums on merge |
| CollapsingMergeTree | Mutable rows (CDC) | Sign column for insert/delete |
| VersionedCollapsingMergeTree | CDC with out-of-order | Version + sign columns |
| Distributed | Query routing | Shards queries across cluster |
| Buffer | Write buffering | Batches inserts to target table |
| MaterializedView | Continuous transforms | Triggers on INSERT |

### Approximate Functions

```sql
-- Exact: slow on billions of rows
SELECT exact_count = count(DISTINCT user_id) FROM events;

-- Approximate (HyperLogLog): ~2% error, 100x faster
SELECT approx_count = uniq(user_id) FROM events;

-- Quantiles: exact vs approximate
SELECT quantileExact(0.99)(response_time) FROM requests;     -- exact, slow
SELECT quantile(0.99)(response_time) FROM requests;          -- t-digest, fast
SELECT quantileTDigest(0.99)(response_time) FROM requests;   -- explicit t-digest

-- Approximate counts with combinators
SELECT uniqCombined(64)(user_id) FROM events;  -- tunable precision
```

---

## Real-World Use Cases

---

### 1. Cloudflare Analytics

**Scale:** 30M+ HTTP requests/second, 100+ ClickHouse nodes, petabytes of data, sub-second query response.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Cloudflare Edge (300+ cities)                │
└────────────────────────────┬────────────────────────────────────┘
                             │ Kafka (HTTP request logs)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Kafka Cluster                                 │
│            (partitioned by zone_id, ~6M msgs/sec)                │
└───────┬──────────────┬──────────────┬──────────────┬────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ClickHouse   │ │ClickHouse   │ │ClickHouse   │ │ClickHouse   │
│ Shard 1     │ │ Shard 2     │ │ Shard 3     │ │ Shard N     │
│(3 replicas) │ │(3 replicas) │ │(3 replicas) │ │(3 replicas) │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │               │
       └───────────────┴───────┬───────┴───────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Distributed Table  │
                    │   (query router)     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Cloudflare Dashboard │
                    │  (Analytics API)      │
                    └─────────────────────┘
```

**Schema:**

```sql
CREATE TABLE http_requests ON CLUSTER '{cluster}'
(
    timestamp DateTime64(3) CODEC(DoubleDelta, LZ4),
    zone_id UInt64,
    -- Request metadata
    method LowCardinality(String),
    url_host String CODEC(ZSTD(3)),
    url_path String CODEC(ZSTD(3)),
    protocol LowCardinality(String),
    -- Response
    status_code UInt16,
    response_bytes UInt64 CODEC(Delta, LZ4),
    response_time_ms UInt32 CODEC(Delta, LZ4),
    -- Client
    client_ip IPv4,
    client_country LowCardinality(FixedString(2)),
    client_asn UInt32,
    -- Security
    waf_action LowCardinality(String),
    bot_score UInt8,
    threat_score UInt8,
    -- Caching
    cache_status LowCardinality(String),
    
    INDEX idx_status status_code TYPE set(0) GRANULARITY 4,
    INDEX idx_country client_country TYPE set(0) GRANULARITY 2
)
ENGINE = ReplicatedMergeTree('/clickhouse/{cluster}/tables/{shard}/http_requests', '{replica}')
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (zone_id, timestamp)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;
```

**Queries:**

```sql
-- Requests per second for a zone (last hour, sub-second response)
SELECT
    toStartOfMinute(timestamp) AS minute,
    count() AS requests,
    countIf(status_code >= 500) AS errors,
    avg(response_time_ms) AS avg_latency
FROM http_requests
WHERE zone_id = 123456
  AND timestamp >= now() - INTERVAL 1 HOUR
GROUP BY minute
ORDER BY minute;

-- Top attacked paths (WAF triggered)
SELECT url_path, count() AS attacks, uniq(client_ip) AS unique_ips
FROM http_requests
WHERE zone_id = 123456
  AND waf_action = 'block'
  AND timestamp >= today()
GROUP BY url_path
ORDER BY attacks DESC
LIMIT 20;

-- Bandwidth by country
SELECT client_country, sum(response_bytes) AS total_bytes,
       bar(total_bytes, 0, 1e12, 40) AS visual
FROM http_requests
WHERE zone_id = 123456 AND timestamp >= today()
GROUP BY client_country
ORDER BY total_bytes DESC
LIMIT 10;
```

**Performance:** Queries over 6+ trillion rows/day return in <1s using partition pruning + sparse index on (zone_id, timestamp).

---

### 2. Uber Operational Analytics

**Scale:** Real-time dashboards for millions of trips/day, driver positions every 4 seconds, surge pricing calculations.

```
┌────────────────────┐    ┌────────────────────┐
│  Driver App        │    │  Rider App          │
│  (GPS every 4s)   │    │  (trip events)      │
└────────┬───────────┘    └────────┬────────────┘
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────────────┐
│              Apache Kafka                         │
│  Topics: driver_locations, trip_events,          │
│          surge_signals, eta_calculations         │
└────────┬──────────────────────┬─────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌──────────────────────┐
│ Flink Streaming │    │ ClickHouse Cluster    │
│ (enrichment,    │    │                       │
│  sessionization)│───▶│ Shard1  Shard2  Shard3│
└─────────────────┘    │ (R1,R2) (R1,R2)(R1,R2│)
                       └──────────┬───────────┘
                                  │
              ┌───────────────────┼────────────────┐
              ▼                   ▼                 ▼
    ┌──────────────┐   ┌──────────────┐  ┌──────────────┐
    │ Ops Dashboard │   │ Surge Pricing│  │ City Metrics │
    │ (Grafana)     │   │ Engine       │  │ Reports      │
    └──────────────┘   └──────────────┘  └──────────────┘
```

**Schema:**

```sql
CREATE TABLE trip_events ON CLUSTER '{cluster}'
(
    trip_id UUID,
    event_time DateTime64(3) CODEC(DoubleDelta, LZ4),
    event_type Enum8('request'=1,'accept'=2,'pickup'=3,'dropoff'=4,'cancel'=5),
    city_id UInt16,
    -- Location
    pickup_lat Float32 CODEC(Gorilla, LZ4),
    pickup_lon Float32 CODEC(Gorilla, LZ4),
    dropoff_lat Float32 CODEC(Gorilla, LZ4),
    dropoff_lon Float32 CODEC(Gorilla, LZ4),
    -- Metrics
    surge_multiplier Float32,
    eta_seconds UInt16 CODEC(Delta, LZ4),
    distance_meters UInt32 CODEC(Delta, LZ4),
    fare_cents UInt32,
    -- Participants
    driver_id UInt64,
    rider_id UInt64,
    vehicle_type LowCardinality(String)
)
ENGINE = ReplicatedMergeTree('/clickhouse/{cluster}/tables/{shard}/trip_events', '{replica}')
PARTITION BY (city_id, toYYYYMM(event_time))
ORDER BY (city_id, event_type, event_time)
TTL event_time + INTERVAL 2 YEAR;

-- Pre-aggregated materialized view for city-level metrics
CREATE MATERIALIZED VIEW city_metrics_mv
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMMDD(window_start)
ORDER BY (city_id, window_start)
AS SELECT
    city_id,
    toStartOfFiveMinutes(event_time) AS window_start,
    countState() AS trip_count,
    avgState(surge_multiplier) AS avg_surge,
    avgState(eta_seconds) AS avg_eta,
    sumState(fare_cents) AS total_fare
FROM trip_events
WHERE event_type = 'dropoff'
GROUP BY city_id, window_start;
```

**Queries:**

```sql
-- Real-time city operations dashboard
SELECT
    toStartOfMinute(event_time) AS minute,
    countIf(event_type = 'request') AS requests,
    countIf(event_type = 'accept') AS accepts,
    countIf(event_type = 'cancel') AS cancels,
    round(accepts / greatest(requests, 1) * 100, 1) AS accept_rate,
    avg(eta_seconds) AS avg_eta
FROM trip_events
WHERE city_id = 42 AND event_time >= now() - INTERVAL 30 MINUTE
GROUP BY minute ORDER BY minute;

-- Surge pricing analysis by geo-hex
SELECT
    geoToH3(pickup_lat, pickup_lon, 7) AS h3_index,
    count() AS demand,
    avg(surge_multiplier) AS avg_surge
FROM trip_events
WHERE city_id = 42
  AND event_time >= now() - INTERVAL 10 MINUTE
  AND event_type = 'request'
GROUP BY h3_index
ORDER BY demand DESC;
```

---

### 3. GitLab Observability

**Scale:** Error tracking across millions of projects, product analytics for 30M+ registered users, traces and logs.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ GitLab Rails │  │ GitLab Runner│  │ User SDKs   │
│ (errors,     │  │ (CI metrics) │  │ (product     │
│  traces)     │  │              │  │  analytics)  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────┐
│                 Snowplow / PubSub                     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              ClickHouse Cluster                       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ Errors  │  │ Events  │  │ Traces  │            │
│  │ Table   │  │ Table   │  │ Table   │            │
│  └─────────┘  └─────────┘  └─────────┘            │
│                                                      │
│  Materialized Views: rollups per project/day         │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│Error Tracking│ │ Product  │ │ Observability│
│  UI          │ │ Analytics│ │ Dashboards   │
└──────────────┘ └──────────┘ └──────────────┘
```

**Schema:**

```sql
CREATE TABLE error_events ON CLUSTER '{cluster}'
(
    project_id UInt64,
    error_id UInt64,
    timestamp DateTime64(3) CODEC(DoubleDelta, LZ4),
    -- Error details
    error_class String CODEC(ZSTD(3)),
    error_message String CODEC(ZSTD(3)),
    fingerprint UInt64,  -- grouping hash
    -- Context
    environment LowCardinality(String),
    release String CODEC(ZSTD(1)),
    platform LowCardinality(String),
    -- Stack trace (stored as array)
    stack_frames Array(String) CODEC(ZSTD(5)),
    -- User context
    user_id String CODEC(ZSTD(1)),
    
    INDEX idx_fingerprint fingerprint TYPE set(1000) GRANULARITY 4,
    INDEX idx_environment environment TYPE set(0) GRANULARITY 1
)
ENGINE = ReplicatedMergeTree('/clickhouse/{cluster}/tables/{shard}/error_events', '{replica}')
PARTITION BY (project_id % 64, toYYYYMM(timestamp))
ORDER BY (project_id, fingerprint, timestamp)
TTL timestamp + INTERVAL 90 DAY;

-- Product analytics: page views, feature usage
CREATE TABLE product_events ON CLUSTER '{cluster}'
(
    namespace_id UInt64,
    user_id UInt64,
    event_time DateTime CODEC(DoubleDelta, LZ4),
    event_name LowCardinality(String),
    plan LowCardinality(String),
    properties Map(String, String) CODEC(ZSTD(3))
)
ENGINE = ReplicatedMergeTree('/clickhouse/{cluster}/tables/{shard}/product_events', '{replica}')
PARTITION BY toYYYYMM(event_time)
ORDER BY (namespace_id, event_name, event_time)
TTL event_time + INTERVAL 1 YEAR;
```

**Queries:**

```sql
-- Error group trending (spike detection)
SELECT
    fingerprint,
    any(error_class) AS error_class,
    count() AS occurrences,
    uniq(user_id) AS affected_users,
    min(timestamp) AS first_seen,
    max(timestamp) AS last_seen
FROM error_events
WHERE project_id = 278964
  AND timestamp >= now() - INTERVAL 24 HOUR
GROUP BY fingerprint
ORDER BY occurrences DESC
LIMIT 20;

-- Feature adoption funnel
SELECT
    event_name,
    uniq(user_id) AS unique_users,
    count() AS total_events
FROM product_events
WHERE namespace_id = 9970
  AND event_time >= today() - 30
  AND event_name IN ('viewed_merge_request', 'approved_merge_request', 'merged')
GROUP BY event_name;
```

---

### 4. Contentsquare

**Scale:** Billions of user interactions/day (clicks, scrolls, hovers), session replay analytics, digital experience scoring.

```
┌──────────────────────────────────────────────────────────────┐
│  Customer Websites (JS SDK - captures every interaction)      │
│  Clicks, scrolls, mouse moves, form interactions, rage clicks│
└───────────────────────────┬──────────────────────────────────┘
                            │ (100K+ events/sec per customer)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              Collection Layer (edge ingestion)                 │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    Kafka (partitioned by customer_id)          │
└──────┬────────────────────┬────────────────────┬─────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐
│ Spark/Flink │    │ Sessionizer │    │  ClickHouse Cluster  │
│ (ML scoring,│    │ (builds     │    │                      │
│  heatmaps)  │    │  sessions)  │───▶│  200+ nodes          │
└─────────────┘    └─────────────┘    │  Multi-DC            │
                                      └──────────┬───────────┘
                                                 │
                              ┌───────────────────┼──────────┐
                              ▼                   ▼          ▼
                    ┌──────────────┐  ┌────────────┐ ┌──────────┐
                    │ Zone-Based   │  │ Journey    │ │ Revenue  │
                    │ Heatmaps     │  │ Analysis   │ │ Impact   │
                    └──────────────┘  └────────────┘ └──────────┘
```

**Schema:**

```sql
CREATE TABLE user_interactions ON CLUSTER '{cluster}'
(
    customer_id UInt32,
    session_id UInt64,
    visitor_id UInt64,
    event_time DateTime64(3) CODEC(DoubleDelta, LZ4),
    -- Interaction
    event_type Enum8(
        'click'=1,'scroll'=2,'hover'=3,'input'=4,
        'rage_click'=5,'dead_click'=6,'page_view'=7
    ),
    page_url String CODEC(ZSTD(3)),
    -- Element targeting
    css_selector String CODEC(ZSTD(3)),
    element_text String CODEC(ZSTD(3)),
    zone_id UInt32,
    -- Position/viewport
    x UInt16 CODEC(Delta, LZ4),
    y UInt16 CODEC(Delta, LZ4),
    viewport_width UInt16,
    viewport_height UInt16,
    scroll_depth_pct UInt8,
    -- Session context
    device_type LowCardinality(String),
    country LowCardinality(FixedString(2)),
    converted UInt8  -- did this session convert?
)
ENGINE = ReplicatedMergeTree('/clickhouse/{cluster}/tables/{shard}/interactions', '{replica}')
PARTITION BY (customer_id, toYYYYMMDD(event_time))
ORDER BY (customer_id, session_id, event_time)
TTL event_time + INTERVAL 13 MONTH
SETTINGS index_granularity = 8192;

-- Pre-aggregated zone metrics
CREATE MATERIALIZED VIEW zone_metrics_mv
ENGINE = AggregatingMergeTree()
ORDER BY (customer_id, page_url, zone_id, day)
AS SELECT
    customer_id,
    page_url,
    zone_id,
    toDate(event_time) AS day,
    countState() AS impressions,
    countIfState(event_type = 'click') AS clicks,
    uniqState(visitor_id) AS unique_visitors,
    avgIfState(converted, event_type = 'click') AS click_conversion_rate
FROM user_interactions
GROUP BY customer_id, page_url, zone_id, day;
```

**Queries:**

```sql
-- Frustration signals: rage clicks by page element
SELECT
    css_selector,
    count() AS rage_clicks,
    uniq(session_id) AS affected_sessions,
    round(affected_sessions / (SELECT uniq(session_id) FROM user_interactions
        WHERE customer_id = 100 AND event_time >= today() - 7) * 100, 2) AS pct_sessions
FROM user_interactions
WHERE customer_id = 100
  AND event_type = 'rage_click'
  AND event_time >= today() - 7
GROUP BY css_selector
ORDER BY rage_clicks DESC LIMIT 10;

-- Scroll depth distribution
SELECT
    page_url,
    quantiles(0.25, 0.5, 0.75, 0.9)(scroll_depth_pct) AS scroll_percentiles,
    uniq(visitor_id) AS visitors
FROM user_interactions
WHERE customer_id = 100
  AND event_type = 'scroll'
  AND event_time >= today() - 7
GROUP BY page_url
ORDER BY visitors DESC;
```

---

### 5. Deutsche Bank - Financial Market Data

**Scale:** Microsecond-granularity tick data, billions of quotes/day, regulatory compliance (MiFID II requires 1μs timestamps).

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Exchange Feed│  │ Dark Pools   │  │ Internal OMS │
│ (FIX/ITCH)  │  │              │  │ (orders)     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────┐
│         Ultra-Low-Latency Capture Layer              │
│      (kernel bypass, FPGA timestamping)              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              ClickHouse Cluster                       │
│  ┌───────────────────────────────────────────────┐  │
│  │ Hot Tier: NVMe SSD (last 7 days)              │  │
│  ├───────────────────────────────────────────────┤  │
│  │ Warm Tier: SSD (last 90 days)                 │  │
│  ├───────────────────────────────────────────────┤  │
│  │ Cold Tier: S3 (archive, years)                │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌────────────────┐
│ Risk Calcs │  │ Surveillance│  │ MiFID II       │
│ (real-time)│  │ (pattern   │  │ Reporting      │
│            │  │  detection)│  │ (audit trail)  │
└────────────┘  └────────────┘  └────────────────┘
```

**Schema:**

```sql
CREATE TABLE market_ticks ON CLUSTER '{cluster}'
(
    -- Microsecond precision timestamp
    exchange_timestamp DateTime64(6) CODEC(DoubleDelta, LZ4),
    capture_timestamp DateTime64(6) CODEC(DoubleDelta, LZ4),
    -- Instrument
    symbol LowCardinality(String),
    exchange LowCardinality(String),
    instrument_type Enum8('equity'=1,'bond'=2,'fx'=3,'derivative'=4),
    -- Quote/Trade
    event_type Enum8('quote'=1,'trade'=2,'cancel'=3,'amend'=4),
    bid_price Decimal64(8) CODEC(Gorilla, LZ4),
    ask_price Decimal64(8) CODEC(Gorilla, LZ4),
    bid_size UInt64 CODEC(Delta, LZ4),
    ask_size UInt64 CODEC(Delta, LZ4),
    trade_price Decimal64(8) CODEC(Gorilla, LZ4),
    trade_volume UInt64 CODEC(Delta, LZ4),
    -- Regulatory
    sequence_number UInt64 CODEC(Delta, LZ4),
    order_id String CODEC(ZSTD(1)),
    
    INDEX idx_symbol symbol TYPE set(5000) GRANULARITY 1
)
ENGINE = ReplicatedMergeTree('/clickhouse/{cluster}/tables/{shard}/market_ticks', '{replica}')
PARTITION BY (instrument_type, toYYYYMMDD(exchange_timestamp))
ORDER BY (symbol, exchange_timestamp, sequence_number)
TTL exchange_timestamp + INTERVAL 7 DAY TO VOLUME 'warm',
    exchange_timestamp + INTERVAL 90 DAY TO VOLUME 's3_cold'
SETTINGS index_granularity = 8192,
         storage_policy = 'tiered';
```

**Queries:**

```sql
-- VWAP calculation (Volume Weighted Average Price)
SELECT
    toStartOfMinute(exchange_timestamp) AS minute,
    sum(trade_price * trade_volume) / sum(trade_volume) AS vwap,
    max(trade_price) AS high,
    min(trade_price) AS low,
    sum(trade_volume) AS volume
FROM market_ticks
WHERE symbol = 'DBK.DE'
  AND event_type = 'trade'
  AND exchange_timestamp >= today()
GROUP BY minute ORDER BY minute;

-- Latency analysis: exchange → capture (MiFID II compliance)
SELECT
    exchange,
    quantiles(0.5, 0.95, 0.99)(
        dateDiff('microsecond', exchange_timestamp, capture_timestamp)
    ) AS latency_us_p50_p95_p99,
    count() AS tick_count
FROM market_ticks
WHERE exchange_timestamp >= now() - INTERVAL 1 HOUR
GROUP BY exchange;

-- Spread analysis
SELECT
    symbol,
    avg(ask_price - bid_price) AS avg_spread,
    min(ask_price - bid_price) AS min_spread,
    count() AS quotes
FROM market_ticks
WHERE event_type = 'quote'
  AND exchange_timestamp >= today()
  AND bid_price > 0 AND ask_price > 0
GROUP BY symbol
ORDER BY avg_spread DESC LIMIT 20;
```

---

## Replication

### ReplicatedMergeTree + ZooKeeper/ClickHouse Keeper

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZooKeeper / ClickHouse Keeper                  │
│                    (3 or 5 node ensemble)                         │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                     │
│  │ Node 1  │◄──▶│ Node 2  │◄──▶│ Node 3  │                     │
│  │(leader) │    │(follower)│    │(follower)│                     │
│  └─────────┘    └─────────┘    └─────────┘                     │
│                                                                  │
│  Stores: replication log, part checksums, leader election        │
│  Does NOT store actual data (only metadata)                      │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │  Replica 1  │ │  Replica 2  │ │  Replica 3  │
            │  (active)   │ │  (active)   │ │  (active)   │
            │             │ │             │ │             │
            │ INSERT ───▶ │ │  fetches    │ │  fetches    │
            │ writes log  │ │  from log   │ │  from log   │
            │ entry to ZK │ │  or peer    │ │  or peer    │
            └─────────────┘ └─────────────┘ └─────────────┘
            
All replicas are equal (multi-master for reads)
INSERT can go to ANY replica → log entry in ZK → others fetch
```

### Multi-Shard Cluster Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ClickHouse Cluster                            │
│                                                                      │
│  Shard 1                Shard 2                Shard 3               │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │ Replica 1-1  │      │ Replica 2-1  │      │ Replica 3-1  │      │
│  │ (DC: us-east)│      │ (DC: us-east)│      │ (DC: us-east)│      │
│  └──────────────┘      └──────────────┘      └──────────────┘      │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │ Replica 1-2  │      │ Replica 2-2  │      │ Replica 3-2  │      │
│  │ (DC: us-west)│      │ (DC: us-west)│      │ (DC: us-west)│      │
│  └──────────────┘      └──────────────┘      └──────────────┘      │
│                                                                      │
│  Data distribution: hash(zone_id) % 3 → shard assignment            │
└─────────────────────────────────────────────────────────────────────┘
```

### Distributed Table Engine

```sql
-- Local table on each shard (actual data)
CREATE TABLE events_local ON CLUSTER '{cluster}'
(
    event_time DateTime,
    user_id UInt64,
    event String
) ENGINE = ReplicatedMergeTree('/clickhouse/{cluster}/tables/{shard}/events', '{replica}')
ORDER BY (user_id, event_time);

-- Distributed table (query router, no data storage)
CREATE TABLE events_distributed ON CLUSTER '{cluster}'
AS events_local
ENGINE = Distributed('{cluster}', default, events_local, sipHash64(user_id));

-- Query hits distributed → fans out to all shards → merges results
SELECT user_id, count() FROM events_distributed
WHERE event_time >= today() GROUP BY user_id;

-- INSERT to distributed → routes to correct shard by sharding key
INSERT INTO events_distributed VALUES (now(), 12345, 'login');
```

### Cross-Datacenter Replication Pattern

```
           DC: us-east-1                         DC: eu-west-1
┌─────────────────────────────┐     ┌─────────────────────────────┐
│  Shard 1: Replica A (write) │◄───▶│  Shard 1: Replica B (read)  │
│  Shard 2: Replica A (write) │◄───▶│  Shard 2: Replica B (read)  │
│  Shard 3: Replica A (write) │◄───▶│  Shard 3: Replica B (read)  │
│                              │     │                              │
│  ZK Node 1, ZK Node 2       │     │  ZK Node 3                  │
└─────────────────────────────┘     └─────────────────────────────┘

Strategy:
- Writes go to primary DC (us-east-1)
- Replication is async via ZK log (eventual consistency)
- Reads can go to either DC (prefer local for latency)
- Failover: promote eu-west-1 replicas if us-east-1 down
- Cross-DC bandwidth: only compressed parts transferred
```

---

## Scalability

### MergeTree Data Parts and Merges

```
Time ──────────────────────────────────────────────────────▶

INSERT batch 1    INSERT batch 2    INSERT batch 3
     │                 │                 │
     ▼                 ▼                 ▼
┌─────────┐      ┌─────────┐      ┌─────────┐
│ Part_1  │      │ Part_2  │      │ Part_3  │
│ (small) │      │ (small) │      │ (small) │
└────┬────┘      └────┬────┘      └────┬────┘
     │                │                │
     └────────────────┴────────────────┘
                      │
              Background merge
                      │
                      ▼
              ┌──────────────┐
              │  Part_1_3    │
              │  (merged,    │
              │   larger)    │
              └──────┬───────┘
                     │          + new Part_4, Part_5
                     │               │
                     └───────────────┘
                             │
                     Background merge
                             │
                             ▼
                     ┌──────────────┐
                     │  Part_1_5    │  (even larger)
                     └──────────────┘

Properties:
- Each INSERT creates 1 new part (immutable)
- Background merges reduce part count
- Merges: re-sort, deduplicate (Replacing), aggregate (Aggregating)
- Controlled by: max_bytes_to_merge_at_max_space_in_pool
- "Too many parts" error if inserts outpace merges → use Buffer tables
```

### Sharding Strategies

| Strategy | Pros | Cons | Use When |
|----------|------|------|----------|
| `rand()` | Even distribution | No co-location | No common query filter |
| `sipHash64(key)` | Key co-location | Possible hotspots | Query always filters by key |
| `key % N` | Predictable routing | Uneven if key skewed | Simple integer keys |
| By time range | Natural partitioning | Latest shard is hot | Time-series append |
| By tenant | Isolation | Uneven sizes | Multi-tenant SaaS |

### Materialized Views (Continuous Aggregation)

```sql
-- Source table: raw events (billions/day)
CREATE TABLE raw_pageviews (
    timestamp DateTime,
    domain String,
    path String,
    user_id UInt64
) ENGINE = MergeTree() ORDER BY (domain, timestamp);

-- Materialized view: auto-aggregates on INSERT
CREATE MATERIALIZED VIEW hourly_pageviews_mv
ENGINE = SummingMergeTree()
ORDER BY (domain, path, hour)
AS SELECT
    domain,
    path,
    toStartOfHour(timestamp) AS hour,
    count() AS views,
    uniq(user_id) AS unique_visitors
FROM raw_pageviews
GROUP BY domain, path, hour;

-- Query the MV (milliseconds over pre-aggregated data)
SELECT domain, sum(views), sum(unique_visitors)
FROM hourly_pageviews_mv
WHERE hour >= today() - 7
GROUP BY domain ORDER BY sum(views) DESC;
```

### Tiered Storage (Hot/Warm/Cold with S3)

```xml
<!-- storage.xml -->
<storage_configuration>
  <disks>
    <nvme>
      <path>/data/nvme/clickhouse/</path>
    </nvme>
    <ssd>
      <path>/data/ssd/clickhouse/</path>
    </ssd>
    <s3_cold>
      <type>s3</type>
      <endpoint>https://s3.amazonaws.com/my-bucket/clickhouse/</endpoint>
      <access_key_id>***</access_key_id>
      <secret_access_key>***</secret_access_key>
    </s3_cold>
  </disks>
  <policies>
    <tiered>
      <volumes>
        <hot>  <disk>nvme</disk>  </hot>
        <warm> <disk>ssd</disk>   </warm>
        <cold> <disk>s3_cold</disk> </cold>
      </volumes>
      <move_factor>0.1</move_factor>
    </tiered>
  </policies>
</storage_configuration>
```

```sql
-- Table with TTL-based movement between tiers
CREATE TABLE metrics (...)
ENGINE = MergeTree()
ORDER BY (metric_name, timestamp)
TTL timestamp + INTERVAL 1 DAY TO VOLUME 'hot',
    timestamp + INTERVAL 30 DAY TO VOLUME 'warm',
    timestamp + INTERVAL 365 DAY TO VOLUME 'cold',
    timestamp + INTERVAL 3 YEAR DELETE
SETTINGS storage_policy = 'tiered';
```

---

## Production Setup

### Hardware Sizing Guidelines

```
Ingestion-Heavy (logs, events):
- CPU: Not bottleneck for writes
- RAM: 64-128GB (for merges + caches)
- Disk: NVMe SSD, 3-10x raw data size (merges need temp space)
- Network: 10Gbps+

Query-Heavy (dashboards, ad-hoc):
- CPU: High core count (64+ cores), AVX2 support critical
- RAM: 128-256GB (for large GROUP BY, JOINs)
- Disk: NVMe for hot data, can tier to S3
- Network: 25Gbps for distributed queries

Rule of thumb:
- 1 core can decompress+scan ~200MB/s of compressed data
- 1B rows with 10 columns × 8 bytes avg = ~80GB raw
- With 10x compression = 8GB on disk
- Full scan: 8GB / 200MB per core = 40s on 1 core, <1s on 64 cores
```

### Buffer Tables and Async Inserts

```sql
-- Problem: many small INSERTs → "too many parts"
-- Solution 1: Buffer table (client-side transparent)
CREATE TABLE events_buffer AS events_local
ENGINE = Buffer(default, events_local,
    16,       -- num_layers
    10, 100,  -- min/max time (seconds)
    10000, 1000000,  -- min/max rows
    10000000, 100000000  -- min/max bytes
);

-- INSERT to buffer (instant, in-memory)
INSERT INTO events_buffer VALUES (...);
-- Buffer flushes to events_local based on thresholds
```

```sql
-- Solution 2: Async inserts (server-side batching, preferred)
SET async_insert = 1;
SET wait_for_async_insert = 0;  -- fire-and-forget
SET async_insert_max_data_size = 10000000;  -- 10MB batch
SET async_insert_busy_timeout_ms = 1000;    -- flush every 1s

-- Now small INSERTs are batched server-side automatically
INSERT INTO events VALUES (...);  -- returns immediately
```

### system.* Monitoring Tables

```sql
-- Active queries and resource usage
SELECT query_id, user, elapsed, read_rows, memory_usage,
       formatReadableSize(memory_usage) AS mem
FROM system.processes ORDER BY memory_usage DESC;

-- Slow query log
SELECT query, query_duration_ms, read_rows, result_rows,
       formatReadableSize(read_bytes) AS data_read
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query_duration_ms > 5000
  AND event_date = today()
ORDER BY query_duration_ms DESC LIMIT 10;

-- Table sizes and compression
SELECT database, table,
    formatReadableSize(sum(bytes_on_disk)) AS disk_size,
    formatReadableSize(sum(data_uncompressed_bytes)) AS raw_size,
    round(sum(data_uncompressed_bytes) / sum(bytes_on_disk), 1) AS compression_ratio,
    sum(rows) AS total_rows,
    count() AS parts
FROM system.parts
WHERE active
GROUP BY database, table
ORDER BY sum(bytes_on_disk) DESC;

-- Merge progress
SELECT database, table, elapsed, progress,
       formatReadableSize(total_size_bytes_compressed) AS size
FROM system.merges;

-- Replication status
SELECT database, table, is_leader, total_replicas, active_replicas,
       log_pointer, queue_size, inserts_in_queue, merges_in_queue
FROM system.replicas WHERE queue_size > 0;

-- Key metrics for alerting:
-- system.asynchronous_metrics: OS + CH metrics
-- system.metrics: current gauges
-- system.events: cumulative counters
```

### Backup with clickhouse-backup

```bash
# Install
wget https://github.com/Altinity/clickhouse-backup/releases/latest/download/clickhouse-backup-linux-amd64.tar.gz

# Create backup
clickhouse-backup create daily_$(date +%Y%m%d)

# Upload to S3
clickhouse-backup upload daily_$(date +%Y%m%d)

# Restore
clickhouse-backup download daily_20240101
clickhouse-backup restore daily_20240101

# Incremental backup (only new parts since last backup)
clickhouse-backup create_remote --diff-from-remote=daily_20240101 daily_20240102
```

```yaml
# /etc/clickhouse-backup/config.yml
general:
  remote_storage: s3
  backups_to_keep_local: 3
  backups_to_keep_remote: 30
s3:
  bucket: "my-ch-backups"
  region: "us-east-1"
  path: "clickhouse/backups"
  compression_format: "zstd"
```

---

## Benchmarks Summary

| Metric | Value |
|--------|-------|
| Full scan 1B rows (single node, 64 cores) | < 1 second |
| Compression ratio (typical analytics) | 10-50x |
| Ingestion rate (single node) | 1-2M rows/sec |
| Ingestion rate (cluster, 10 nodes) | 10-20M rows/sec |
| Point query (by primary key) | 1-10ms |
| Aggregation over 100M rows | 100-500ms |
| Columnar scan throughput | 1-10 GB/s per node (decompressed) |
| Concurrent queries (typical) | 100-200 (CPU-bound) |

---

## Quick Reference: When to Use ClickHouse

**Use ClickHouse for:**
- Analytics queries (GROUP BY, COUNT, SUM over large datasets)
- Time-series at scale (logs, metrics, events)
- Real-time dashboards with sub-second latency
- Data that is append-mostly (immutable events)
- Wide tables (100+ columns, read few per query)

**Do NOT use ClickHouse for:**
- OLTP workloads (frequent single-row updates)
- Transactions (no ACID transactions)
- Point lookups by arbitrary key (use Redis/PostgreSQL)
- Small datasets (<1M rows, PostgreSQL is fine)
- Normalized relational data with complex JOINs
