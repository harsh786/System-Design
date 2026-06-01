# TimescaleDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Hypertables & Chunks](#hypertables--chunks)
3. [Data Model & Schema Design](#data-model--schema-design)
4. [Continuous Aggregates](#continuous-aggregates)
5. [Data Retention & Compression](#data-retention--compression)
6. [Query Performance & Optimization](#query-performance--optimization)
7. [Multi-Node / Distributed TimescaleDB](#multi-node--distributed-timescaledb)
8. [Replication & High Availability](#replication--high-availability)
9. [Ingestion Patterns & Performance](#ingestion-patterns--performance)
10. [Production Configuration & Tuning](#production-configuration--tuning)
11. [Integration & Ecosystem](#integration--ecosystem)
12. [Use Case Architectures](#use-case-architectures)
13. [Staff Architect Interview Questions](#staff-architect-interview-questions)
14. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is TimescaleDB?
```
TimescaleDB is a time-series database built as a PostgreSQL extension.
It provides automatic time-based partitioning, compression, continuous
aggregates, and time-series-specific optimizations while maintaining
full SQL compatibility.

Key characteristics:
- PostgreSQL extension (not a fork - full compatibility)
- Automatic time-based partitioning (hypertables → chunks)
- Native compression (95%+ compression ratios)
- Continuous aggregates (materialized views that auto-update)
- Full SQL support (JOINs, subqueries, CTEs, window functions)
- All PostgreSQL extensions work (PostGIS, pgvector, etc.)
- ACID compliant (transactions, constraints, foreign keys)

NOT designed for:
- Prometheus-style pull-based metrics (use VictoriaMetrics)
- Ultra-high cardinality label-based metrics (100M+ series)
- Sub-millisecond query latency at extreme scale
```

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                            │
│  (Grafana, Custom Apps, Telegraf, Prometheus remote_write)      │
└─────────────────────────────┬───────────────────────────────────┘
                              │ SQL (standard PostgreSQL protocol)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Server                              │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  Query Planner/Executor                     │  │
│  │  - Standard PostgreSQL planner                             │  │
│  │  - TimescaleDB hooks for chunk exclusion                  │  │
│  │  - Parallel query across chunks                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │               TimescaleDB Extension                        │  │
│  │                                                            │  │
│  │  ┌──────────────┐ ┌───────────────┐ ┌────────────────┐   │  │
│  │  │  Hypertable   │ │  Continuous   │ │  Compression   │   │  │
│  │  │  Management   │ │  Aggregates   │ │  Engine        │   │  │
│  │  └──────────────┘ └───────────────┘ └────────────────┘   │  │
│  │                                                            │  │
│  │  ┌──────────────┐ ┌───────────────┐ ┌────────────────┐   │  │
│  │  │  Data         │ │  Retention    │ │  Background    │   │  │
│  │  │  Tiering      │ │  Policies     │ │  Workers       │   │  │
│  │  └──────────────┘ └───────────────┘ └────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │               PostgreSQL Storage Layer                     │  │
│  │                                                            │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐      │  │
│  │  │Chunk│ │Chunk│ │Chunk│ │Chunk│ │Chunk│ │Chunk│      │  │
│  │  │ T1  │ │ T2  │ │ T3  │ │ T4  │ │ T5  │ │ T6  │      │  │
│  │  │(hot)│ │(hot)│ │(warm│ │(warm│ │(cold│ │(cold│      │  │
│  │  │     │ │     │ │comp)│ │comp)│ │comp)│ │comp)│      │  │
│  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘      │  │
│  │                                                            │  │
│  │  Each chunk = independent PostgreSQL table                │  │
│  │  Own indexes, statistics, constraints                     │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Why Extension vs Fork?
```
┌───────────────────────────────────────────────────────────────┐
│ Extension Approach (TimescaleDB)  │ Fork Approach             │
├───────────────────────────────────┼───────────────────────────┤
│ ✓ All PG upgrades automatically  │ ✗ Must port every PG fix  │
│ ✓ All PG extensions work         │ ✗ Extensions may break    │
│ ✓ Standard PG tools (pg_dump,    │ ✗ Custom tooling needed   │
│   pgBackRest, Patroni)           │                           │
│ ✓ Any PG driver works            │ ✗ May need custom drivers │
│ ✓ Easy adoption (just CREATE     │ ✗ Replace entire DB       │
│   EXTENSION)                     │                           │
│ ✓ Existing PG expertise applies  │ ✗ New skills needed       │
│                                   │                           │
│ ✗ Constrained by PG internals    │ ✓ Can optimize freely     │
│ ✗ Some overhead from hooks       │ ✓ Direct optimization     │
└───────────────────────────────────────────────────────────────┘
```

---

## Hypertables & Chunks

### Hypertable Concept
```
A hypertable is a virtual table that automatically partitions data
across many "chunks" (regular PostgreSQL tables) by time.

┌─────────────────────────────────────────────────────────────┐
│                   HYPERTABLE (Virtual)                        │
│                   "sensor_data"                               │
│                                                               │
│  CREATE TABLE sensor_data (                                  │
│    time        TIMESTAMPTZ NOT NULL,                         │
│    device_id   INTEGER,                                      │
│    temperature DOUBLE PRECISION,                             │
│    humidity    DOUBLE PRECISION                              │
│  );                                                          │
│  SELECT create_hypertable('sensor_data', 'time');            │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Chunk 1            Chunk 2            Chunk 3               │
│  [Jan 1-7]         [Jan 8-14]         [Jan 15-21]          │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐         │
│  │ time     │      │ time     │      │ time     │         │
│  │ device   │      │ device   │      │ device   │         │
│  │ temp     │      │ temp     │      │ temp     │         │
│  │ humidity │      │ humidity │      │ humidity │         │
│  │          │      │          │      │          │         │
│  │ 500K rows│      │ 500K rows│      │ 500K rows│         │
│  └──────────┘      └──────────┘      └──────────┘         │
│  _hyper_1_1_chunk  _hyper_1_2_chunk  _hyper_1_3_chunk      │
│  (own indexes)     (own indexes)     (own indexes)         │
│                                                               │
│  Auto-created when data arrives for a new time range        │
└─────────────────────────────────────────────────────────────┘
```

### Space Partitioning (Multi-Dimensional)
```
For high-cardinality deployments, partition by BOTH time AND space:

SELECT create_hypertable('sensor_data', 'time',
  partitioning_column => 'device_id',
  number_partitions => 4
);

                        TIME DIMENSION →
            │  Jan 1-7  │  Jan 8-14  │  Jan 15-21  │
   S    ────┼───────────┼────────────┼─────────────┤
   P    D1  │  Chunk_1  │  Chunk_5   │  Chunk_9    │
   A    ────┼───────────┼────────────┼─────────────┤
   C    D2  │  Chunk_2  │  Chunk_6   │  Chunk_10   │
   E    ────┼───────────┼────────────┼─────────────┤
        D3  │  Chunk_3  │  Chunk_7   │  Chunk_11   │
   ↓    ────┼───────────┼────────────┼─────────────┤
        D4  │  Chunk_4  │  Chunk_8   │  Chunk_12   │
        ────┴───────────┴────────────┴─────────────┘

Benefits:
- Query for specific device touches fewer chunks
- Better parallelism (parallel scan across space partitions)
- Lock contention reduced (concurrent inserts to different chunks)

When to use space partitioning:
- > 10M rows per time interval
- Queries frequently filter by the space column
- Many concurrent writers (reduces lock contention)
- Many distinct devices/tenants
```

### Chunk Interval Selection
```
┌───────────────────────────────────────────────────────────────┐
│ Rule of thumb: Each chunk should contain 25% of available     │
│ memory worth of data (uncompressed)                           │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│ Ingestion Rate    │ RAM    │ Recommended Interval             │
├───────────────────┼────────┼──────────────────────────────────┤
│ 10K rows/sec      │ 16 GB  │ 1 week                          │
│ 100K rows/sec     │ 32 GB  │ 1 day                           │
│ 1M rows/sec       │ 64 GB  │ 6 hours                         │
│ 10M rows/sec      │ 128 GB │ 1 hour                          │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│ Too small intervals:                                         │
│ - Many chunks → slow planning, many indexes in memory        │
│ - More metadata overhead                                     │
│ - Compression less effective (smaller batches)               │
│                                                               │
│ Too large intervals:                                         │
│ - Chunks don't fit in memory → poor I/O performance         │
│ - Compression/retention only at chunk granularity            │
│ - Index maintenance more expensive                           │
│                                                               │
│ Change interval (only affects future chunks):                │
│ SELECT set_chunk_time_interval('sensor_data', INTERVAL '1d');│
└───────────────────────────────────────────────────────────────┘
```

### Chunk Exclusion (Query Optimization)
```
-- Query with time filter:
SELECT avg(temperature) FROM sensor_data
WHERE time > now() - INTERVAL '7 days';

PostgreSQL constraint exclusion:
┌─────────────────────────────────────────────────────────────┐
│  Chunk 1 [Jan 1-7]    → EXCLUDED (time constraint fails)   │
│  Chunk 2 [Jan 8-14]   → EXCLUDED                           │
│  Chunk 3 [Jan 15-21]  → EXCLUDED                           │
│  ...                                                         │
│  Chunk 50 [Dec 18-24] → EXCLUDED                           │
│  Chunk 51 [Dec 25-31] → SCANNED ✓ (matches time range)    │
│  Chunk 52 [Jan 1-7]   → SCANNED ✓ (matches time range)    │
└─────────────────────────────────────────────────────────────┘

Only 2 chunks scanned out of 52 total → 96% data skipped!

This works because:
- Each chunk has CHECK constraints on time range
- PostgreSQL planner uses constraint exclusion
- TimescaleDB adds additional optimizations for chunk pruning
- Works with both time AND space dimensions
```

---

## Data Model & Schema Design

### Wide vs Narrow Table Design
```
═══════════════════════════════════════════════════════════════
NARROW TABLE (one metric per row) - "Long format"
═══════════════════════════════════════════════════════════════
CREATE TABLE metrics (
    time        TIMESTAMPTZ NOT NULL,
    device_id   INTEGER,
    metric_name TEXT,           -- 'temperature', 'humidity', etc.
    value       DOUBLE PRECISION
);

Pros: Flexible schema, easy to add new metrics
Cons: More rows, JOIN needed for correlated metrics, higher cardinality

═══════════════════════════════════════════════════════════════
WIDE TABLE (all metrics per row) - "Wide format" [RECOMMENDED]
═══════════════════════════════════════════════════════════════
CREATE TABLE sensor_data (
    time        TIMESTAMPTZ NOT NULL,
    device_id   INTEGER,
    temperature DOUBLE PRECISION,
    humidity    DOUBLE PRECISION,
    pressure    DOUBLE PRECISION,
    battery     DOUBLE PRECISION
);

Pros: Fewer rows, better compression, correlated metrics together
Cons: Schema changes need ALTER TABLE, NULL for missing metrics

Recommendation: Wide tables for known metric sets, narrow for dynamic

═══════════════════════════════════════════════════════════════
HYBRID (tags + metrics)
═══════════════════════════════════════════════════════════════
CREATE TABLE iot_data (
    time          TIMESTAMPTZ NOT NULL,
    device_id     INTEGER NOT NULL,
    location      TEXT,              -- tag (low cardinality)
    device_type   TEXT,              -- tag
    temperature   DOUBLE PRECISION,  -- metric
    humidity      DOUBLE PRECISION,  -- metric
    battery_pct   DOUBLE PRECISION   -- metric
);
```

### Production Schema Examples
```
═══════════════════════════════════════════════════════════════
IoT SENSOR DATA
═══════════════════════════════════════════════════════════════
CREATE TABLE sensor_readings (
    time          TIMESTAMPTZ NOT NULL,
    sensor_id     INTEGER NOT NULL,
    location_id   INTEGER NOT NULL,
    temperature   REAL,
    humidity      REAL,
    pressure      REAL,
    battery_level SMALLINT,
    signal_rssi   SMALLINT
);

SELECT create_hypertable('sensor_readings', 'time',
    partitioning_column => 'sensor_id',
    number_partitions => 4,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX ON sensor_readings (sensor_id, time DESC);
CREATE INDEX ON sensor_readings (location_id, time DESC);

═══════════════════════════════════════════════════════════════
FINANCIAL TICK DATA
═══════════════════════════════════════════════════════════════
CREATE TABLE ticks (
    time      TIMESTAMPTZ NOT NULL,
    symbol    TEXT NOT NULL,
    price     NUMERIC(12,4) NOT NULL,
    volume    BIGINT NOT NULL,
    bid       NUMERIC(12,4),
    ask       NUMERIC(12,4),
    exchange  TEXT
);

SELECT create_hypertable('ticks', 'time',
    chunk_time_interval => INTERVAL '1 hour'  -- High frequency
);

CREATE INDEX ON ticks (symbol, time DESC);

═══════════════════════════════════════════════════════════════
APPLICATION METRICS / APM
═══════════════════════════════════════════════════════════════
CREATE TABLE app_metrics (
    time            TIMESTAMPTZ NOT NULL,
    service_name    TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    http_status     SMALLINT,
    response_ms     REAL,
    request_size    INTEGER,
    response_size   INTEGER,
    error_count     INTEGER DEFAULT 0
);

SELECT create_hypertable('app_metrics', 'time',
    chunk_time_interval => INTERVAL '6 hours'
);

CREATE INDEX ON app_metrics (service_name, time DESC);
CREATE INDEX ON app_metrics (service_name, endpoint, time DESC)
    WHERE http_status >= 500;  -- Partial index for errors
```

---

## Continuous Aggregates

### How Continuous Aggregates Work
```
Continuous aggregates are incrementally-maintained materialized views
that automatically stay up to date as new data arrives.

┌─────────────────────────────────────────────────────────────────┐
│             CONTINUOUS AGGREGATE REFRESH FLOW                     │
│                                                                   │
│  Raw Data (Hypertable)                                           │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐            │
│  │10:00│ │10:01│ │10:02│ │10:03│ │10:04│ │10:05│  ← inserts  │
│  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘            │
│     │       │       │       │       │       │                  │
│     └───────┴───────┴───────┴───────┴───────┘                  │
│                        │                                         │
│            Invalidation Tracker                                   │
│            (tracks which buckets                                  │
│             have new/modified data)                               │
│                        │                                         │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────┐                │
│  │         Refresh Policy (Background Job)      │                │
│  │  - Runs every refresh_interval               │                │
│  │  - Only recomputes invalidated buckets      │                │
│  │  - Incremental (not full recomputation)     │                │
│  └──────────────────────┬──────────────────────┘                │
│                         │                                        │
│                         ▼                                        │
│  Materialized Data (Continuous Aggregate)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │10:00 avg │ │10:05 avg │ │10:10 avg │  ← pre-computed      │
│  │  = 42.3  │ │  = 43.1  │ │  = 41.8  │    5-min buckets     │
│  └──────────┘ └──────────┘ └──────────┘                       │
│                                                                   │
│  Real-Time Query (combines materialized + recent raw):          │
│  ┌──────────────────────────────────────────────┐               │
│  │  SELECT time_bucket('5 min', time), avg(temp)│               │
│  │  FROM sensor_data_5min;  -- continuous agg   │               │
│  │                                               │               │
│  │  Result = materialized buckets                │               │
│  │         + live computation of recent data     │               │
│  └──────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### Creating Continuous Aggregates
```sql
-- 5-minute aggregation
CREATE MATERIALIZED VIEW sensor_data_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    device_id,
    AVG(temperature) AS avg_temp,
    MIN(temperature) AS min_temp,
    MAX(temperature) AS max_temp,
    COUNT(*) AS sample_count
FROM sensor_data
GROUP BY bucket, device_id
WITH NO DATA;  -- Don't backfill immediately

-- Add refresh policy (auto-refresh)
SELECT add_continuous_aggregate_policy('sensor_data_5min',
    start_offset    => INTERVAL '1 hour',   -- Refresh from 1h ago
    end_offset      => INTERVAL '5 minutes', -- Don't refresh last 5min
    schedule_interval => INTERVAL '5 minutes' -- Run every 5 min
);

-- Hierarchical: 1-hour aggregate ON TOP of 5-min aggregate
CREATE MATERIALIZED VIEW sensor_data_1hr
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', bucket) AS bucket,
    device_id,
    AVG(avg_temp) AS avg_temp,
    MIN(min_temp) AS min_temp,
    MAX(max_temp) AS max_temp,
    SUM(sample_count) AS sample_count
FROM sensor_data_5min
GROUP BY 1, device_id
WITH NO DATA;

-- Backfill historical data
CALL refresh_continuous_aggregate('sensor_data_5min',
    '2024-01-01', '2024-12-31');
```

### Performance Impact
```
Without continuous aggregates:
  Query: SELECT avg(temp) FROM sensor_data WHERE time > now() - '30d'
  Scans: 30 days × 1M rows/day = 30M rows
  Time: 5-30 seconds

With continuous aggregates (5-min buckets):
  Query: SELECT avg(avg_temp) FROM sensor_data_5min WHERE bucket > now() - '30d'
  Scans: 30 days × 288 buckets/day = 8,640 rows
  Time: 5-50 milliseconds

Speedup: 100-1000x for dashboard queries!

Cost:
- Storage: ~1-5% overhead for materialized data
- Background CPU for refresh (minimal, incremental)
- Slight insert overhead for invalidation tracking
```

---

## Data Retention & Compression

### Compression Architecture
```
TimescaleDB compression converts row-based chunks to column-based:

┌─────────────────────────────────────────────────────────────────┐
│                    COMPRESSION INTERNALS                          │
│                                                                   │
│  UNCOMPRESSED CHUNK (row storage):                               │
│  ┌──────────┬───────────┬──────┬──────────┬──────────┐         │
│  │ time     │ device_id │ temp │ humidity │ pressure │         │
│  ├──────────┼───────────┼──────┼──────────┼──────────┤         │
│  │ 10:00:01 │ 1         │ 22.5 │ 45.2     │ 1013.2   │         │
│  │ 10:00:01 │ 2         │ 23.1 │ 44.8     │ 1013.1   │         │
│  │ 10:00:02 │ 1         │ 22.6 │ 45.1     │ 1013.2   │         │
│  │ ...      │ ...       │ ...  │ ...      │ ...      │         │
│  └──────────┴───────────┴──────┴──────────┴──────────┘         │
│                          │                                       │
│                          │ ALTER TABLE sensor_data               │
│                          │ SET (timescaledb.compress,            │
│                          │   timescaledb.compress_segmentby =    │
│                          │     'device_id',                      │
│                          │   timescaledb.compress_orderby =      │
│                          │     'time DESC');                     │
│                          ▼                                       │
│  COMPRESSED CHUNK (columnar storage):                            │
│  ┌───────────────────────────────────────────────────────┐      │
│  │ Segment: device_id = 1                                 │      │
│  │ ┌────────────────────────────────────────────────┐    │      │
│  │ │ time:     [delta-of-delta encoded array]        │    │      │
│  │ │ temp:     [Gorilla XOR encoded array]           │    │      │
│  │ │ humidity: [Gorilla XOR encoded array]           │    │      │
│  │ │ pressure: [Gorilla XOR encoded array]           │    │      │
│  │ │ (1000 rows per compressed row)                  │    │      │
│  │ └────────────────────────────────────────────────┘    │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │ Segment: device_id = 2                                 │      │
│  │ ┌────────────────────────────────────────────────┐    │      │
│  │ │ time:     [delta-of-delta encoded array]        │    │      │
│  │ │ temp:     [Gorilla XOR encoded array]           │    │      │
│  │ │ ...                                             │    │      │
│  │ └────────────────────────────────────────────────┘    │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
│  Compression Algorithms by Data Type:                            │
│  ┌──────────────┬────────────────────────┬────────────────┐     │
│  │ Data Type    │ Algorithm              │ Typical Ratio  │     │
│  ├──────────────┼────────────────────────┼────────────────┤     │
│  │ Timestamps   │ Delta-of-delta         │ 20-50x         │     │
│  │ Floats       │ Gorilla (XOR)          │ 10-20x         │     │
│  │ Integers     │ Delta + Simple8b       │ 10-30x         │     │
│  │ Text (low)   │ Dictionary encoding    │ 50-100x        │     │
│  │ Text (high)  │ LZ4                    │ 3-5x           │     │
│  │ Overall      │ Combined               │ 10-30x typical │     │
│  └──────────────┴────────────────────────┴────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### Data Lifecycle Management
```
┌─────────────────────────────────────────────────────────────────┐
│                  DATA LIFECYCLE PIPELINE                          │
│                                                                   │
│   HOT (0-7 days)      WARM (7-90 days)     COLD (90+ days)     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Uncompressed │    │  Compressed  │    │  Compressed  │      │
│  │ Full indexes │    │  Min indexes │    │  Archived    │      │
│  │ Fast inserts │ →  │  10-30x less │ →  │  Move to S3  │      │
│  │ Fast queries │    │  Queryable   │    │  or DROP     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                   │
│  Configuration:                                                   │
│                                                                   │
│  -- Compress chunks older than 7 days                            │
│  SELECT add_compression_policy('sensor_data',                    │
│      compress_after => INTERVAL '7 days');                       │
│                                                                   │
│  -- Drop chunks older than 1 year                                │
│  SELECT add_retention_policy('sensor_data',                      │
│      drop_after => INTERVAL '1 year');                           │
│                                                                   │
│  -- Tiered storage (TimescaleDB 2.13+)                          │
│  -- Move old data to cheaper object storage                      │
│  SELECT add_tiering_policy('sensor_data',                        │
│      move_after => INTERVAL '90 days');                          │
│                                                                   │
│  Timeline:                                                        │
│  ──────────────────────────────────────────────────────────►    │
│  │← HOT →│←──── WARM (compressed) ────→│←── COLD/DROP ──→│    │
│  │ 7 days│         83 days              │    archived      │    │
│  │       │                              │                  │    │
│  insert  compress                   tier to S3         drop │    │
│                                                               │
└─────────────────────────────────────────────────────────────────┘

Production compression ratios (real-world):
- IoT sensor data: 20-30x compression
- Financial tick data: 10-15x compression
- Application metrics: 15-25x compression
- Infrastructure metrics: 20-40x compression (lots of zeros)
```

---

## Query Performance & Optimization

### time_bucket Function
```sql
-- The core function for time-series aggregation
SELECT
    time_bucket('1 hour', time) AS hour,
    device_id,
    AVG(temperature) AS avg_temp,
    percentile_agg(temperature) AS pct_agg
FROM sensor_data
WHERE time > now() - INTERVAL '7 days'
GROUP BY hour, device_id
ORDER BY hour DESC;

-- Time buckets with custom origin (align to business hours)
SELECT time_bucket('1 hour', time, 
    origin => '2024-01-01 08:00:00') AS bucket;

-- Variable-width buckets (for monthly aggregation)
SELECT time_bucket('1 month', time) AS month;

-- Gapfilling (fill missing time buckets)
SELECT
    time_bucket_gapfill('1 hour', time) AS hour,
    device_id,
    COALESCE(AVG(temperature), locf(AVG(temperature))) AS temp
FROM sensor_data
WHERE time > now() - INTERVAL '24 hours'
GROUP BY hour, device_id;
-- locf = Last Observation Carried Forward
-- interpolate() for linear interpolation
```

### Index Strategies
```
┌─────────────────────────────────────────────────────────────────┐
│                    INDEX RECOMMENDATIONS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  DEFAULT (created automatically):                                │
│  CREATE INDEX ON sensor_data (time DESC);                        │
│  -- B-tree on time (per chunk)                                   │
│                                                                   │
│  COMMON PATTERNS:                                                │
│                                                                   │
│  -- Single device lookup (most common query pattern)             │
│  CREATE INDEX ON sensor_data (device_id, time DESC);             │
│                                                                   │
│  -- Multi-column for filtered aggregation                        │
│  CREATE INDEX ON sensor_data (location_id, device_type, time DESC);│
│                                                                   │
│  -- Partial index (only errors, saves space)                     │
│  CREATE INDEX ON metrics (service, time DESC)                    │
│      WHERE status >= 500;                                        │
│                                                                   │
│  COMPARISON:                                                      │
│  ┌────────────┬────────────────────────┬──────────────────┐     │
│  │ Index Type │ Best For               │ Space            │     │
│  ├────────────┼────────────────────────┼──────────────────┤     │
│  │ B-tree     │ Point lookups, < / >   │ Standard         │     │
│  │ BRIN       │ Time column (sorted)   │ Very small (1%)  │     │
│  │ Hash       │ Exact equality only    │ Smaller          │     │
│  │ GiST       │ Range types, geo       │ Moderate         │     │
│  └────────────┴────────────────────────┴──────────────────┘     │
│                                                                   │
│  BRIN for time-series (when time is naturally sorted):           │
│  CREATE INDEX ON sensor_data USING BRIN (time)                   │
│      WITH (pages_per_range = 32);                                │
│  -- 1000x smaller than B-tree, nearly as fast for range scans   │
│                                                                   │
│  NOTE: Indexes are PER-CHUNK (small, fast to maintain)          │
│  Each chunk typically has < 100M rows → index stays small        │
└─────────────────────────────────────────────────────────────────┘
```

### Query Optimization Patterns
```sql
-- EXPLAIN ANALYZE to understand query plan
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT time_bucket('1 hour', time) AS hour, avg(temperature)
FROM sensor_data
WHERE time > now() - INTERVAL '7 days'
  AND device_id = 42
GROUP BY hour;

-- What to look for in EXPLAIN:
-- ✓ "Chunks excluded: 50"  (chunk exclusion working)
-- ✓ "Index Scan using ..."  (using index, not seq scan)
-- ✓ "Parallel Append"       (parallel across chunks)
-- ✗ "Seq Scan on _hyper_..." (scanning full chunks)
-- ✗ "Chunks excluded: 0"    (no chunk pruning)

-- Optimize: Push filters into WHERE (not HAVING)
-- BAD:
SELECT device_id, avg(temp) FROM sensor_data
GROUP BY device_id HAVING device_id = 42;

-- GOOD:
SELECT device_id, avg(temp) FROM sensor_data
WHERE device_id = 42 GROUP BY device_id;

-- Optimize: Use continuous aggregates for dashboards
-- Instead of:  SELECT avg(temp) FROM raw WHERE time > now() - '90d'
-- Use:         SELECT avg(avg_temp) FROM hourly_agg WHERE ...

-- Optimize: Limit chunks with explicit time bounds
-- BAD (scans all chunks):
SELECT * FROM sensor_data WHERE device_id = 42 LIMIT 100;

-- GOOD (chunk exclusion works):
SELECT * FROM sensor_data 
WHERE device_id = 42 AND time > now() - INTERVAL '1 day'
ORDER BY time DESC LIMIT 100;
```

---

## Multi-Node / Distributed TimescaleDB

### Distributed Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│              DISTRIBUTED TIMESCALEDB CLUSTER                      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    ACCESS NODE                             │   │
│  │  (Receives queries, coordinates execution)                │   │
│  │                                                           │   │
│  │  - Query planning and optimization                       │   │
│  │  - Distributed query execution                           │   │
│  │  - Pushdown aggregations to data nodes                   │   │
│  │  - Metadata about chunk distribution                     │   │
│  │  - No local data storage (stateless for data)           │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                       │
│              ┌────────────┼────────────┐                         │
│              │            │            │                          │
│              ▼            ▼            ▼                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │  DATA NODE 1 │ │  DATA NODE 2 │ │  DATA NODE 3 │            │
│  │              │ │              │ │              │            │
│  │ Chunks:      │ │ Chunks:      │ │ Chunks:      │            │
│  │ [Dev 1-100]  │ │ [Dev 101-200]│ │ [Dev 201-300]│            │
│  │ [Jan-Mar]    │ │ [Jan-Mar]    │ │ [Jan-Mar]    │            │
│  │              │ │              │ │              │            │
│  │ Local:       │ │ Local:       │ │ Local:       │            │
│  │ - Indexes    │ │ - Indexes    │ │ - Indexes    │            │
│  │ - Compress   │ │ - Compress   │ │ - Compress   │            │
│  │ - Continuous │ │ - Continuous │ │ - Continuous │            │
│  │   aggregates │ │   aggregates │ │   aggregates │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│                                                                   │
│  Query Pushdown:                                                 │
│  SELECT device_id, avg(temp) WHERE device_id = 42               │
│       → Only DATA NODE 1 is queried (partition pruning)         │
│                                                                   │
│  SELECT avg(temp) WHERE time > now() - '7 days'                 │
│       → All nodes compute partial avg, access node merges       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

Setup:
-- On access node:
SELECT add_data_node('dn1', host => 'data-node-1');
SELECT add_data_node('dn2', host => 'data-node-2');
SELECT add_data_node('dn3', host => 'data-node-3');

-- Create distributed hypertable:
SELECT create_distributed_hypertable('sensor_data', 'time',
    partitioning_column => 'device_id',
    number_partitions => 3,
    data_nodes => ARRAY['dn1', 'dn2', 'dn3']
);
```

---

## Replication & High Availability

### HA Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│              HIGH AVAILABILITY SETUP                              │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐         │
│  │                   HAProxy / PgBouncer                │         │
│  │  (Connection pooling + read/write splitting)       │         │
│  └───────────┬──────────────────────────┬─────────────┘         │
│              │ writes                    │ reads                  │
│              ▼                           ▼                        │
│  ┌──────────────────┐        ┌──────────────────┐              │
│  │   PRIMARY         │        │   REPLICA 1       │              │
│  │   (Read/Write)    │───────→│   (Read Only)     │              │
│  │                   │ stream │                   │              │
│  │  TimescaleDB      │  repl  │  TimescaleDB      │              │
│  │  PostgreSQL 15    │        │  PostgreSQL 15    │              │
│  └────────┬──────────┘        └──────────────────┘              │
│           │                                                       │
│           │ streaming replication                                 │
│           ▼                                                       │
│  ┌──────────────────┐                                            │
│  │   REPLICA 2       │                                            │
│  │   (Read Only)     │                                            │
│  │   + Standby for   │                                            │
│  │   failover        │                                            │
│  └──────────────────┘                                            │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐         │
│  │                    Patroni                          │         │
│  │  - Automatic failover (< 30 seconds)              │         │
│  │  - Leader election via etcd/ZooKeeper/Consul      │         │
│  │  - Health monitoring                              │         │
│  │  - Switchover (planned maintenance)               │         │
│  └────────────────────────────────────────────────────┘         │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐         │
│  │                  pgBackRest                         │         │
│  │  - Full + incremental backups                     │         │
│  │  - Point-in-time recovery (PITR)                  │         │
│  │  - Backup to S3/GCS/Azure Blob                    │         │
│  │  - Parallel backup and restore                    │         │
│  └────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Ingestion Patterns & Performance

### High-Performance Ingestion
```
┌─────────────────────────────────────────────────────────────────┐
│                  INGESTION OPTIMIZATION                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Method 1: Batch INSERT (100K-500K rows/sec)                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  INSERT INTO sensor_data VALUES                          │   │
│  │    ('2024-01-01 00:00:00', 1, 22.5, 45.2),            │   │
│  │    ('2024-01-01 00:00:00', 2, 23.1, 44.8),            │   │
│  │    ... (1000-10000 rows per statement)                  │   │
│  │                                                          │   │
│  │  Batch size sweet spot: 1000-10000 rows                 │   │
│  │  Beyond 10K: diminishing returns                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Method 2: COPY (1M-5M rows/sec) [FASTEST]                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  COPY sensor_data FROM '/data/import.csv'               │   │
│  │  WITH (FORMAT csv, HEADER true);                        │   │
│  │                                                          │   │
│  │  -- Or from program:                                    │   │
│  │  COPY sensor_data FROM STDIN WITH (FORMAT binary);      │   │
│  │                                                          │   │
│  │  Parallel COPY (TimescaleDB 2.10+):                     │   │
│  │  timescaledb.max_copy_workers = 8                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Method 3: Prepared Statements (high throughput with driver)    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  PREPARE insert_sensor AS                               │   │
│  │  INSERT INTO sensor_data VALUES ($1, $2, $3, $4);       │   │
│  │                                                          │   │
│  │  EXECUTE insert_sensor('2024-01-01', 1, 22.5, 45.2);   │   │
│  │  -- Avoids re-parsing for repeated inserts              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Connection Pooling (CRITICAL for high concurrency):            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  PgBouncer in transaction mode:                         │   │
│  │  - 100 application connections → 20 PG connections     │   │
│  │  - Eliminates connection overhead                       │   │
│  │  - pool_mode = transaction                              │   │
│  │  - max_client_conn = 1000                               │   │
│  │  - default_pool_size = 20-50                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Benchmark Numbers (single node, 16 cores, 64GB RAM, NVMe):    │
│  ┌──────────────────┬──────────────────────────────────────┐   │
│  │ Method           │ Throughput                           │   │
│  ├──────────────────┼──────────────────────────────────────┤   │
│  │ Single INSERT    │ 10-20K rows/sec                      │   │
│  │ Batch INSERT     │ 200-500K rows/sec                    │   │
│  │ COPY             │ 1-5M rows/sec                        │   │
│  │ Parallel COPY    │ 5-10M rows/sec (8 workers)          │   │
│  └──────────────────┴──────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Production Configuration & Tuning

### Key Configuration Parameters
```
═══════════════════════════════════════════════════════════════
POSTGRESQL SETTINGS (postgresql.conf)
═══════════════════════════════════════════════════════════════

# Memory (for 64GB RAM machine)
shared_buffers = 16GB                # 25% of RAM
effective_cache_size = 48GB          # 75% of RAM
work_mem = 64MB                      # Per-sort operation
maintenance_work_mem = 2GB           # For VACUUM, CREATE INDEX

# WAL
wal_level = replica                  # For streaming replication
max_wal_size = 8GB                   # Before checkpoint
min_wal_size = 2GB
wal_compression = on                 # Reduce WAL I/O
checkpoint_completion_target = 0.9

# Query
max_parallel_workers_per_gather = 4  # Parallel query
max_parallel_workers = 8
jit = on                             # JIT compilation
random_page_cost = 1.1               # For SSD (default 4.0!)
effective_io_concurrency = 200       # For NVMe

# Connections
max_connections = 200                # Use PgBouncer for more
tcp_keepalives_idle = 300

═══════════════════════════════════════════════════════════════
TIMESCALEDB SETTINGS
═══════════════════════════════════════════════════════════════

# Background workers
timescaledb.max_background_workers = 16  # For compression + refresh

# Chunk settings
-- Set per hypertable, not globally
-- chunk_time_interval: see sizing guide above

# Compression
timescaledb.compress_segmentby = 'device_id'  # Per-hypertable
timescaledb.compress_orderby = 'time DESC'     # Per-hypertable

═══════════════════════════════════════════════════════════════
HARDWARE SIZING GUIDE
═══════════════════════════════════════════════════════════════
┌────────────────┬──────────────────┬──────────────────────────┐
│ Scale          │ Hardware         │ Supports                 │
├────────────────┼──────────────────┼──────────────────────────┤
│ Small          │ 8 CPU, 32GB RAM  │ 100K inserts/sec         │
│ (dev/staging)  │ 500GB NVMe       │ 1TB data                 │
├────────────────┼──────────────────┼──────────────────────────┤
│ Medium         │ 16 CPU, 64GB RAM │ 500K inserts/sec         │
│ (production)   │ 2TB NVMe        │ 10TB data                │
├────────────────┼──────────────────┼──────────────────────────┤
│ Large          │ 32 CPU, 128GB    │ 2M inserts/sec           │
│ (high-scale)   │ 8TB NVMe RAID   │ 50TB+ data               │
├────────────────┼──────────────────┼──────────────────────────┤
│ Distributed    │ 3-10 data nodes  │ 10M+ inserts/sec         │
│                │ each: 16C/64GB   │ 100TB+ data              │
└────────────────┴──────────────────┴──────────────────────────┘
```

---

## Integration & Ecosystem

### Integration Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                  TIMESCALEDB ECOSYSTEM                            │
│                                                                   │
│  DATA SOURCES:                                                   │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌──────────┐      │
│  │Telegraf  │ │Prometheus │ │ Kafka      │ │ Custom   │      │
│  │(metrics) │ │(remote_wr)│ │ Connect   │ │ Apps     │      │
│  └────┬─────┘ └─────┬─────┘ └──────┬─────┘ └────┬─────┘      │
│       │              │               │             │             │
│       └──────────────┴───────────────┴─────────────┘             │
│                              │                                    │
│                              ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      TimescaleDB                           │  │
│  │                                                            │  │
│  │  + PostGIS (geospatial time-series)                       │  │
│  │  + pgvector (AI/ML embeddings)                            │  │
│  │  + pg_stat_statements (query monitoring)                  │  │
│  │  + pg_cron (scheduled jobs)                               │  │
│  │  + any PostgreSQL extension                               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│  VISUALIZATION & ALERTING:                                       │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌──────────┐      │
│  │ Grafana  │ │ Superset  │ │ Custom     │ │ Alerting │      │
│  │(native   │ │           │ │ Dashboards │ │ (pgwatch)│      │
│  │datasource│ │           │ │            │ │          │      │
│  └──────────┘ └───────────┘ └────────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Use Case Architectures

### IoT Platform at Scale
```
┌─────────────────────────────────────────────────────────────────┐
│                    IoT MONITORING PLATFORM                        │
│                                                                   │
│  100K Sensors                                                    │
│  ┌───┐┌───┐┌───┐                                               │
│  │ S ││ S ││ S │...                                             │
│  └─┬─┘└─┬─┘└─┬─┘                                               │
│    │     │     │   MQTT / HTTP                                   │
│    └─────┴─────┘                                                 │
│          │                                                        │
│          ▼                                                        │
│  ┌──────────────────────────────────────┐                       │
│  │         Message Broker (Kafka)        │                       │
│  │  - Buffer for burst handling          │                       │
│  │  - Exactly-once semantics             │                       │
│  │  - 1M msgs/sec capacity              │                       │
│  └──────────────────┬───────────────────┘                       │
│                     │                                             │
│                     ▼                                             │
│  ┌──────────────────────────────────────┐                       │
│  │      Kafka Connect (JDBC Sink)        │                       │
│  │  - Batch inserts (10K rows/batch)    │                       │
│  │  - 8 parallel tasks                  │                       │
│  │  - Exactly-once delivery             │                       │
│  └──────────────────┬───────────────────┘                       │
│                     │                                             │
│                     ▼                                             │
│  ┌──────────────────────────────────────┐                       │
│  │           TimescaleDB                  │                       │
│  │                                        │                       │
│  │  Hypertable: sensor_readings           │                       │
│  │  - chunk_interval: 6 hours            │                       │
│  │  - space_partitions: 8 (by sensor_id) │                       │
│  │  - compression after 24 hours         │                       │
│  │  - retention: 2 years                 │                       │
│  │                                        │                       │
│  │  Continuous aggregates:               │                       │
│  │  - 5-min rollups (real-time)          │                       │
│  │  - 1-hour rollups                     │                       │
│  │  - 1-day rollups                      │                       │
│  │                                        │                       │
│  │  Compression: 25x (2TB → 80GB/month) │                       │
│  └──────────────────┬───────────────────┘                       │
│                     │                                             │
│                     ▼                                             │
│  ┌──────────────────────────────────────┐                       │
│  │           Grafana                      │                       │
│  │  - Real-time dashboards               │                       │
│  │  - Alerting (threshold + anomaly)     │                       │
│  │  - 100ms query response (from aggs)  │                       │
│  └──────────────────────────────────────┘                       │
│                                                                   │
│  Performance:                                                    │
│  - Ingestion: 500K rows/sec sustained                           │
│  - Query (last 24h, single device): < 10ms                     │
│  - Query (last 7d, 100 devices, aggregated): < 100ms           │
│  - Storage: 80GB/month (compressed from 2TB raw)               │
└─────────────────────────────────────────────────────────────────┘
```

### DevOps Infrastructure Monitoring
```
┌─────────────────────────────────────────────────────────────────┐
│            INFRASTRUCTURE MONITORING (replacing InfluxDB)         │
│                                                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐             │
│  │ Servers │ │  K8s    │ │Databases│ │ Network │             │
│  │ (node_  │ │ (kube-  │ │ (pg,    │ │ (SNMP)  │             │
│  │ exporter│ │ state)  │ │ mysql)  │ │         │             │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘             │
│       │           │            │           │                     │
│       └───────────┴────────────┴───────────┘                     │
│                        │                                          │
│                        ▼                                          │
│  ┌──────────────────────────────────────────┐                   │
│  │              Telegraf Fleet                │                   │
│  │  - Collection interval: 10s               │                   │
│  │  - Output: postgresql (batch writer)      │                   │
│  │  - 50K metrics/sec per agent             │                   │
│  └──────────────────────┬───────────────────┘                   │
│                         │                                         │
│                         ▼                                         │
│  ┌──────────────────────────────────────────┐                   │
│  │            TimescaleDB                    │                   │
│  │                                           │                   │
│  │  Benefits over InfluxDB:                  │                   │
│  │  - Full SQL (complex correlations)       │                   │
│  │  - JOINs with metadata tables            │                   │
│  │  - Standard PostgreSQL tooling           │                   │
│  │  - Better compression                    │                   │
│  │  - No cardinality limits                 │                   │
│  └──────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: How does TimescaleDB achieve better performance than vanilla PostgreSQL for time-series?
```
Key optimizations:

1. Chunk-based partitioning:
   - Each chunk is small → fits in memory
   - Indexes per chunk are small → faster B-tree traversal
   - INSERT only touches latest chunk → no contention with reads on old data
   - Chunk exclusion skips 95%+ of data for time-filtered queries

2. Continuous aggregates:
   - Pre-computed rollups avoid scanning raw data
   - Incremental refresh (only recompute changed buckets)
   - Hierarchical (5min → 1hr → 1day)

3. Native compression:
   - 10-30x compression → less I/O
   - Columnar within compressed chunks → read only needed columns
   - Gorilla/delta encoding optimized for time-series patterns

4. Specialized functions:
   - time_bucket: optimized time grouping
   - Approximate functions (percentile_agg, hyperloglog)
   - Gap-filling and interpolation

vs Vanilla PostgreSQL:
- Single large table with billions of rows → index bloat
- No automatic partition management
- No time-series compression
- No continuous aggregates
- Query planning slow with 1000+ partitions (TimescaleDB handles this)
```

### Q2: When would you choose TimescaleDB over InfluxDB or Prometheus?
```
Choose TimescaleDB when:
- Need SQL (JOINs, subqueries, CTEs)
- Data has relational aspects (foreign keys, constraints)
- Need transactions (ACID)
- Team knows PostgreSQL
- Need rich ecosystem (PostGIS, pgvector, any PG extension)
- Complex analytics beyond simple aggregations
- Moderate cardinality (< 10M active series)

Choose InfluxDB when:
- Pure metrics workload, no relational data
- Flux query language fits your needs
- Managed cloud offering preferred
- Simple deployment priority

Choose Prometheus when:
- Kubernetes-native monitoring
- Pull-based collection model
- AlertManager integration
- Short retention (15-30 days)
- PromQL ecosystem (Grafana alerts, etc.)

Choose VictoriaMetrics when:
- Very high cardinality (100M+ series)
- Need Prometheus compatibility but better performance
- Multi-tenant metrics platform
- Long-term storage for Prometheus data

TimescaleDB sweet spot:
- IoT platforms needing SQL + time-series
- Financial data (transactions + time-series)
- Application analytics (events + aggregations)
- Any case where you'd want "PostgreSQL but faster for time data"
```

### Q3: How do you select chunk_time_interval for a production deployment?
```
Framework for selection:

Step 1: Calculate data volume per interval
  - Rows per second × seconds per interval × row size
  - Target: each chunk ≈ 25% of shared_buffers

Step 2: Consider query patterns
  - Most queries look back how far? (chunk should be ≤ lookback)
  - Dashboard refresh interval?
  
Step 3: Consider compression granularity
  - Compression is per-chunk (can't partially compress)
  - Chunk must be "cold" before compression
  - Smaller intervals → compress sooner

Step 4: Consider retention granularity
  - drop_chunks drops whole chunks
  - Finer retention → smaller intervals

Example calculation:
  Given: 50K rows/sec, 200 bytes/row, 64GB RAM, shared_buffers=16GB
  Target chunk size: 16GB × 25% = 4GB
  Time for 4GB: 4GB / (50K × 200B) = 4GB / 10MB/sec = 400 sec ≈ 7 min
  
  That's too small! Adjust:
  - With compression columns (only 50 bytes effective): ~26 min
  - Practical minimum: 1 hour
  - Use space partitioning to split further
  
  Final: chunk_time_interval = '1 hour', space_partitions = 4
  Each chunk: ~2.5GB (fits comfortably in shared_buffers)
```

### Q4: How does compression interact with queries and inserts?
```
Compressed chunks:
- READ: Transparent to queries (decompress on-the-fly, segment pruning)
- WRITE: Cannot INSERT into compressed chunks directly
  - Must decompress first: SELECT decompress_chunk('chunk_name')
  - Or use INSERT with on_conflict (auto-decompresses relevant segments)

Segment-based access (key optimization):
  compress_segmentby = 'device_id'
  
  Query: WHERE device_id = 42 AND time > now() - '7d'
  - Only decompresses segments for device_id = 42
  - Skips all other device segments
  - Much faster than decompressing entire chunk

orderby optimization:
  compress_orderby = 'time DESC'
  
  Query: ORDER BY time DESC LIMIT 10
  - Reads compressed data in sorted order
  - Can stop early (only decompress first segment)

Performance characteristics:
  - Compressed query: 2-5x slower than uncompressed (decompression cost)
  - BUT: 10-30x less I/O (compressed data is tiny)
  - Net effect: often FASTER for cold data (I/O bound → CPU bound)
  - Bulk scan of compressed data: matches or beats uncompressed
```

### Q5: Design a multi-tenant SaaS metrics platform on TimescaleDB.
```
Architecture:

Option A: Schema per tenant (strong isolation)
  - Each tenant gets own schema with hypertables
  - Pros: Easy to drop tenant, no data leakage
  - Cons: Many schemas → management overhead, connection pooling harder
  - Best for: < 100 tenants, strict isolation requirements

Option B: Row-level tenancy (shared tables)
  - All tenants in same hypertable, tenant_id column
  - Space partitioning by tenant_id
  - Row-level security (RLS) for access control
  
  CREATE POLICY tenant_isolation ON metrics
    USING (tenant_id = current_setting('app.tenant_id')::int);
  
  Pros: Simple, efficient, easy to query across tenants (admin)
  Cons: Noisy neighbor (one tenant's burst affects all)
  Best for: 100-10000 tenants, similar workloads

Option C: Separate database per large tenant
  - Small tenants share one DB
  - Large tenants get dedicated DB instance
  - Route at application/proxy layer

Capacity planning per tenant:
  - Assign quota: max ingestion rate, max active series
  - Monitor: per-tenant chunk count, query duration
  - Alert: tenant approaching limits
  
Compression strategy:
  - segment_by = 'tenant_id' (efficient per-tenant queries)
  - Each tenant's data compressed independently
  - Different retention per tenant tier (free=7d, pro=1y, enterprise=5y)
```

---

## Scenario-Based Questions

### Scenario 1: Design monitoring system ingesting 1M metrics/sec
```
Requirements: 1M inserts/sec, 90-day retention, 100ms dashboard queries

Architecture:
┌─────────────────────────────────────────────────────────┐
│                                                           │
│  Ingest Layer (distributed):                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ Ingest   │ │ Ingest   │ │ Ingest   │ × 4 nodes    │
│  │ Worker 1 │ │ Worker 2 │ │ Worker 3 │               │
│  │ 250K/sec │ │ 250K/sec │ │ 250K/sec │               │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘               │
│       │             │             │                      │
│       └─────────────┴─────────────┘                      │
│                     │ batch COPY (5K rows/batch)         │
│                     ▼                                     │
│  ┌─────────────────────────────────────────────┐        │
│  │           PgBouncer (transaction mode)       │        │
│  │           pool_size = 50 per node            │        │
│  └──────────────────────┬──────────────────────┘        │
│                         │                                │
│                         ▼                                │
│  ┌─────────────────────────────────────────────┐        │
│  │        TimescaleDB (Primary)                 │        │
│  │  - 32 cores, 128GB RAM, NVMe RAID           │        │
│  │  - chunk_time_interval: 1 hour              │        │
│  │  - space_partitions: 8                      │        │
│  │  - Parallel COPY workers: 8                 │        │
│  │                                              │        │
│  │  Continuous aggregates:                      │        │
│  │  - 1-min rollup (real-time)                 │        │
│  │  - 1-hour rollup                            │        │
│  │  - 1-day rollup                             │        │
│  │                                              │        │
│  │  Policies:                                   │        │
│  │  - Compress after 24 hours (20x ratio)      │        │
│  │  - Drop raw after 90 days                   │        │
│  │  - Keep 1-hour aggs for 2 years             │        │
│  └─────────────────────────────────────────────┘        │
│                                                           │
│  Storage calculation:                                    │
│  Raw: 1M/sec × 100 bytes × 86400 sec = 8.6 TB/day      │
│  Compressed (20x): 430 GB/day                           │
│  90 days: 38.7 TB compressed                            │
│  → Need: 50TB NVMe (with headroom)                      │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Scenario 2: Migrate from InfluxDB to TimescaleDB
```
Migration plan:

Phase 1: Schema Design (Week 1)
  InfluxDB measurement → TimescaleDB hypertable
  InfluxDB tags → indexed columns (TEXT, segment_by)
  InfluxDB fields → metric columns (REAL, DOUBLE PRECISION)
  
  -- Example: InfluxDB measurement "cpu"
  -- tags: host, cpu, region
  -- fields: usage_user, usage_system, usage_idle
  
  CREATE TABLE cpu (
    time          TIMESTAMPTZ NOT NULL,
    host          TEXT NOT NULL,
    cpu_core      TEXT NOT NULL,
    region        TEXT NOT NULL,
    usage_user    REAL,
    usage_system  REAL,
    usage_idle    REAL
  );
  SELECT create_hypertable('cpu', 'time',
    chunk_time_interval => INTERVAL '6 hours');

Phase 2: Dual-Write (Week 2-3)
  - Write to both InfluxDB and TimescaleDB
  - Compare query results for correctness
  - Tune TimescaleDB configuration

Phase 3: Historical Migration (Week 3-4)
  - Export from InfluxDB: influx export --start 2023-01-01
  - Transform to CSV
  - COPY into TimescaleDB (parallel, 5M rows/sec)
  - Compress historical chunks immediately
  
Phase 4: Query Migration (Week 4-6)
  InfluxQL / Flux → SQL mapping:
  - MEAN(field) → AVG(column)
  - GROUP BY time(5m) → GROUP BY time_bucket('5 min', time)
  - FILL(previous) → locf(avg(col))
  - derivative() → (val - lag(val)) / extract(epoch from time - lag(time))

Phase 5: Cutover (Week 6)
  - Switch Grafana datasource to PostgreSQL/TimescaleDB
  - Stop writes to InfluxDB
  - Keep InfluxDB read-only for 2 weeks (rollback)
  - Decommission InfluxDB

Benefits gained:
  - SQL JOINs with business data
  - 40% storage reduction (better compression)
  - Standard PostgreSQL tooling
  - No cardinality explosion issues
  - Full ACID transactions
```

### Scenario 3: Optimize query for 90-day lookback dashboard
```
Problem: Dashboard query takes 30 seconds for 90-day aggregate

-- Slow query:
SELECT time_bucket('1 hour', time) AS hour,
       service_name,
       avg(response_ms) AS avg_latency,
       percentile_cont(0.99) WITHIN GROUP (ORDER BY response_ms) AS p99
FROM app_metrics
WHERE time > now() - INTERVAL '90 days'
  AND service_name = 'payment-service'
GROUP BY hour, service_name
ORDER BY hour;

Optimization steps:

1. Create continuous aggregate (biggest win):
   CREATE MATERIALIZED VIEW app_metrics_1hr
   WITH (timescaledb.continuous) AS
   SELECT time_bucket('1 hour', time) AS bucket,
          service_name,
          avg(response_ms) AS avg_latency,
          percentile_agg(response_ms) AS pct_agg,
          count(*) AS request_count
   FROM app_metrics
   GROUP BY bucket, service_name;
   
   -- Dashboard query now:
   SELECT bucket, avg_latency,
          approx_percentile(0.99, pct_agg) AS p99
   FROM app_metrics_1hr
   WHERE bucket > now() - INTERVAL '90 days'
     AND service_name = 'payment-service';
   
   Result: 30 sec → 50ms (600x improvement)

2. Add appropriate index:
   CREATE INDEX ON app_metrics (service_name, time DESC)
   INCLUDE (response_ms);

3. Ensure compression is configured:
   compress_segmentby = 'service_name'
   compress_orderby = 'time DESC'
   → Only reads payment-service segments

4. Monitor with EXPLAIN:
   - Verify chunk exclusion: should scan ~90 chunks (1/day)
   - Verify index usage on continuous aggregate
   - Check for sequential scans (add indexes if needed)
```
