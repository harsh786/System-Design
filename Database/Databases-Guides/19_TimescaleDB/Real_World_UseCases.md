# TimescaleDB - Real World Use Cases & Production Guide

## Table of Contents
- [Core Concepts](#core-concepts)
- [Real-World Use Cases](#real-world-use-cases)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)

---

## Core Concepts

### Hypertable Architecture

A **hypertable** is a virtual table that automatically partitions data into chunks based on time (and optionally space dimensions). You interact with it as a single PostgreSQL table.

```
┌─────────────────────────────────────────────────────────────────┐
│                     HYPERTABLE (virtual)                         │
│                   "sensor_data" table                            │
│                                                                 │
│  INSERT/SELECT/UPDATE/DELETE ─── Full SQL ─── JOINs, CTEs, etc │
├─────────────────────────────────────────────────────────────────┤
│                    Chunk Layer (physical)                        │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Chunk 1  │ │ Chunk 2  │ │ Chunk 3  │ │ Chunk 4  │          │
│  │ Jan 1-7  │ │ Jan 8-14 │ │Jan 15-21 │ │Jan 22-28 │          │
│  │ (active) │ │(compress)│ │(compress)│ │ (dropped)│          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
│  Space Partitioning (optional):                                 │
│  ┌────────────────────┬────────────────────┐                    │
│  │  device_id hash=0  │  device_id hash=1  │  ← per time chunk │
│  └────────────────────┴────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### Chunk Exclusion (Partition Pruning)

```sql
-- TimescaleDB automatically prunes chunks not matching WHERE clause
SELECT * FROM sensor_data
WHERE time > NOW() - INTERVAL '1 hour'
  AND device_id = 'pump-42';

-- Only scans the latest chunk(s), not the entire table
-- EXPLAIN shows: "Chunks excluded: 1456 of 1460"
```

### Continuous Aggregates with Real-Time Aggregation

```
┌───────────────────────────────────────────────────────┐
│           Continuous Aggregate Pipeline                 │
│                                                       │
│  Raw Data ──► Materialized (historical) ──┐           │
│                                           ├──► Query  │
│  Raw Data ──► Real-time (recent unmated) ─┘           │
│                                                       │
│  Background Worker refreshes materialization          │
│  periodically (e.g., every 10 minutes)               │
└───────────────────────────────────────────────────────┘
```

```sql
CREATE MATERIALIZED VIEW sensor_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    AVG(temperature) AS avg_temp,
    MAX(temperature) AS max_temp,
    COUNT(*) AS readings
FROM sensor_data
GROUP BY bucket, device_id
WITH NO DATA;

-- Real-time aggregation: queries combine materialized + recent raw data
ALTER MATERIALIZED VIEW sensor_hourly SET (timescaledb.materialized_only = false);

-- Refresh policy
SELECT add_continuous_aggregate_policy('sensor_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

### Data Compression

TimescaleDB uses **columnar compression** within chunks:

| Algorithm | Used For | Compression Ratio |
|-----------|----------|-------------------|
| Delta-of-delta | Timestamps, monotonic integers | 10-20x |
| Gorilla (XOR) | Floating-point values | 5-15x |
| Dictionary | Low-cardinality strings/enums | 10-50x |
| LZ4 / Array | General fallback | 3-5x |

**Typical overall compression: 10-20x for IoT workloads**

```sql
ALTER TABLE sensor_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby = 'time DESC'
);

-- Compress chunks older than 7 days
SELECT add_compression_policy('sensor_data', INTERVAL '7 days');
```

### Hyperfunctions

```sql
-- time_bucket: uniform time bucketing
SELECT time_bucket('5 minutes', time) AS bucket, AVG(value) FROM metrics GROUP BY bucket;

-- time_bucket_gapfill: fill missing buckets
SELECT time_bucket_gapfill('1 hour', time) AS bucket,
       LOCF(AVG(temperature)) AS temp  -- Last Observation Carried Forward
FROM sensor_data
WHERE time BETWEEN '2024-01-01' AND '2024-01-02'
GROUP BY bucket;

-- Approximate percentiles (t-digest)
SELECT device_id,
       approx_percentile(0.99, percentile_agg(response_time)) AS p99
FROM metrics GROUP BY device_id;

-- Approximate count distinct (HyperLogLog)
SELECT time_bucket('1 day', time) AS day,
       approx_count_distinct(user_id) AS unique_users
FROM events GROUP BY day;
```

---

## Real-World Use Cases

---

### 1. Ndustrial.io - Industrial IoT Manufacturing

**Scale:** 10,000+ machines, 500,000+ sensors, 2M+ rows/second ingestion

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Ndustrial.io Architecture                          │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌────────────┐   ┌──────────────┐  │
│  │ Factory  │   │ Factory  │   │  Factory   │   │   Factory    │  │
│  │ Floor 1  │   │ Floor 2  │   │  Floor 3   │   │   Floor N    │  │
│  │ Sensors  │   │ Sensors  │   │  Sensors   │   │   Sensors    │  │
│  └────┬─────┘   └────┬─────┘   └─────┬──────┘   └──────┬───────┘  │
│       │               │               │                  │          │
│       ▼               ▼               ▼                  ▼          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              MQTT / Kafka Ingestion Layer                    │    │
│  │         (Buffering + Schema Validation)                     │    │
│  └────────────────────────────┬────────────────────────────────┘    │
│                               │                                     │
│                               ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    TimescaleDB Cluster                       │    │
│  │                                                             │    │
│  │   Hypertable: machine_telemetry                             │    │
│  │   Chunk interval: 1 hour (high ingest rate)                 │    │
│  │   Space partitions: 16 (by factory_id hash)                 │    │
│  │   Compression: after 6 hours                                │    │
│  │   Retention: 90 days hot, 2 years cold (S3 tiering)         │    │
│  └─────────────────────────────┬───────────────────────────────┘    │
│                               │                                     │
│               ┌───────────────┼───────────────┐                     │
│               ▼               ▼               ▼                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐          │
│  │  Real-time   │  │  Continuous  │  │  ML Pipeline     │          │
│  │  Dashboard   │  │  Aggregates  │  │  (Anomaly Det.)  │          │
│  │  (Grafana)   │  │  (1m/5m/1h)  │  │  (Python/Spark)  │          │
│  └──────────────┘  └──────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

**Schema:**

```sql
CREATE TABLE machine_telemetry (
    time          TIMESTAMPTZ NOT NULL,
    factory_id    INT NOT NULL,
    machine_id    TEXT NOT NULL,
    sensor_type   TEXT NOT NULL,      -- 'vibration','temperature','pressure','rpm'
    value         DOUBLE PRECISION NOT NULL,
    unit          TEXT,
    quality_flag  SMALLINT DEFAULT 0  -- 0=good, 1=suspect, 2=bad
);

SELECT create_hypertable('machine_telemetry', 'time',
    chunk_time_interval => INTERVAL '1 hour',
    partitioning_column => 'factory_id',
    number_partitions => 16
);

-- Indexes
CREATE INDEX ON machine_telemetry (machine_id, time DESC);
CREATE INDEX ON machine_telemetry (sensor_type, time DESC)
    WHERE quality_flag = 0;
```

**Continuous Aggregates:**

```sql
-- 1-minute rollups for real-time dashboards
CREATE MATERIALIZED VIEW telemetry_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    factory_id, machine_id, sensor_type,
    AVG(value) AS avg_val,
    MIN(value) AS min_val,
    MAX(value) AS max_val,
    STDDEV(value) AS stddev_val,
    COUNT(*) AS sample_count
FROM machine_telemetry
WHERE quality_flag = 0
GROUP BY bucket, factory_id, machine_id, sensor_type;

-- 1-hour rollups for trend analysis (aggregate on aggregate)
CREATE MATERIALIZED VIEW telemetry_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', bucket) AS bucket,
    factory_id, machine_id, sensor_type,
    AVG(avg_val) AS avg_val,
    MIN(min_val) AS min_val,
    MAX(max_val) AS max_val,
    SUM(sample_count) AS sample_count
FROM telemetry_1m
GROUP BY 1, factory_id, machine_id, sensor_type;
```

**Data Retention:**

```sql
-- Drop raw data after 90 days
SELECT add_retention_policy('machine_telemetry', INTERVAL '90 days');

-- Keep 1-minute aggregates for 1 year
SELECT add_retention_policy('telemetry_1m', INTERVAL '1 year');

-- Keep hourly aggregates forever (small footprint)

-- Compression after 6 hours
SELECT add_compression_policy('machine_telemetry', INTERVAL '6 hours');
```

**Queries:**

```sql
-- Real-time: last 5 minutes of vibration for specific machine
SELECT time, value
FROM machine_telemetry
WHERE machine_id = 'CNC-M7-042'
  AND sensor_type = 'vibration'
  AND time > NOW() - INTERVAL '5 minutes'
ORDER BY time DESC;
-- Latency: <10ms (chunk exclusion + index)

-- Anomaly detection: machines exceeding 3 sigma
SELECT machine_id, sensor_type,
       AVG(avg_val) AS mean,
       STDDEV(avg_val) AS sigma
FROM telemetry_1m
WHERE bucket > NOW() - INTERVAL '1 hour'
GROUP BY machine_id, sensor_type
HAVING MAX(max_val) > AVG(avg_val) + 3 * STDDEV(avg_val);
```

**Benchmarks:**
- Ingestion: 2.1M rows/sec (batched COPY, 32 vCPU node)
- Point query (single sensor, 5min window): 3-8ms
- Aggregate query (1h window, 100 machines): 50-120ms
- Compression ratio: 14x (vibration data with gorilla encoding)
- Storage: 2TB raw/day → 140GB compressed

---

### 2. MakerDAO - DeFi Blockchain Analytics

**Scale:** 50K+ rows/sec from Ethereum events, 500GB+ historical data

```
┌─────────────────────────────────────────────────────────────────────┐
│                   MakerDAO Analytics Architecture                     │
│                                                                     │
│  ┌──────────────┐         ┌────────────────┐                        │
│  │  Ethereum    │────────►│  Event Indexer  │                        │
│  │  Full Node   │  events │  (TheGraph/    │                        │
│  │  (Geth/Erigon)│        │   Custom)      │                        │
│  └──────────────┘         └───────┬────────┘                        │
│                                   │                                  │
│  ┌──────────────┐                 │                                  │
│  │  Price Feeds │─────────────────┤                                  │
│  │  (Oracles)   │                 │                                  │
│  └──────────────┘                 ▼                                  │
│                    ┌──────────────────────────────┐                   │
│                    │        TimescaleDB            │                   │
│                    │                              │                   │
│                    │  Hypertables:                │                   │
│                    │  - vault_events              │                   │
│                    │  - token_prices              │                   │
│                    │  - liquidation_events        │                   │
│                    │  - protocol_metrics          │                   │
│                    │                              │                   │
│                    │  Chunk interval: 1 day       │                   │
│                    │  Compression: after 7 days   │                   │
│                    └──────────────┬───────────────┘                   │
│                                  │                                    │
│                    ┌─────────────┼─────────────┐                     │
│                    ▼             ▼             ▼                      │
│             ┌───────────┐ ┌──────────┐ ┌────────────┐               │
│             │  Risk     │ │ Governance│ │  Public    │               │
│             │  Dashboard│ │ Analytics │ │  API       │               │
│             └───────────┘ └──────────┘ └────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

**Schema:**

```sql
CREATE TABLE vault_events (
    time            TIMESTAMPTZ NOT NULL,
    block_number    BIGINT NOT NULL,
    tx_hash         TEXT NOT NULL,
    vault_id        BIGINT NOT NULL,
    collateral_type TEXT NOT NULL,     -- 'ETH-A', 'WBTC-A', etc.
    event_type      TEXT NOT NULL,     -- 'open','deposit','withdraw','generate','payback','liquidate'
    collateral_amt  NUMERIC(78, 18),
    dai_amt         NUMERIC(78, 18),
    collateral_price NUMERIC(30, 8)
);

SELECT create_hypertable('vault_events', 'time',
    chunk_time_interval => INTERVAL '1 day');

CREATE TABLE token_prices (
    time       TIMESTAMPTZ NOT NULL,
    token      TEXT NOT NULL,
    price_usd  NUMERIC(30, 8),
    source     TEXT NOT NULL
);

SELECT create_hypertable('token_prices', 'time',
    chunk_time_interval => INTERVAL '1 day');

-- Compression
ALTER TABLE vault_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'collateral_type',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('vault_events', INTERVAL '7 days');
```

**Continuous Aggregates:**

```sql
-- Protocol-level metrics every hour
CREATE MATERIALIZED VIEW protocol_metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    collateral_type,
    SUM(CASE WHEN event_type = 'generate' THEN dai_amt ELSE 0 END) AS dai_generated,
    SUM(CASE WHEN event_type = 'payback' THEN dai_amt ELSE 0 END) AS dai_repaid,
    COUNT(DISTINCT vault_id) AS active_vaults,
    COUNT(*) AS total_events
FROM vault_events
GROUP BY bucket, collateral_type;

-- TVL tracking (total value locked)
CREATE MATERIALIZED VIEW tvl_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', v.time) AS bucket,
    v.collateral_type,
    SUM(v.collateral_amt * p.price_usd) AS tvl_usd
FROM vault_events v
JOIN LATERAL (
    SELECT price_usd FROM token_prices
    WHERE token = split_part(v.collateral_type, '-', 1)
      AND time <= v.time
    ORDER BY time DESC LIMIT 1
) p ON true
GROUP BY bucket, v.collateral_type;
```

**Queries:**

```sql
-- Collateralization ratio over time
SELECT
    time_bucket('1 day', time) AS day,
    collateral_type,
    SUM(collateral_amt * collateral_price) / NULLIF(SUM(dai_amt), 0) AS coll_ratio
FROM vault_events
WHERE time > NOW() - INTERVAL '30 days'
GROUP BY day, collateral_type
ORDER BY day;

-- Liquidation risk: vaults approaching threshold
WITH latest_prices AS (
    SELECT DISTINCT ON (token) token, price_usd
    FROM token_prices ORDER BY token, time DESC
)
SELECT vault_id, collateral_type,
       collateral_amt * lp.price_usd / NULLIF(dai_amt, 0) AS current_ratio
FROM vault_events v
JOIN latest_prices lp ON lp.token = split_part(v.collateral_type, '-', 1)
WHERE current_ratio < 1.6
ORDER BY current_ratio ASC;
```

**Retention:**

```sql
SELECT add_retention_policy('token_prices', INTERVAL '2 years');
-- vault_events kept indefinitely (compressed)
-- Hourly aggregates kept indefinitely
```

**Benchmarks:**
- Ingestion: 50K events/sec during high-gas periods
- Point query (single vault history): 5-15ms
- TVL calculation (all collateral types, 1 year): 200-500ms
- Compression ratio: 8x (numeric data, many distinct vaults)
- Storage: 500GB total (60GB compressed)

---

### 3. Symantec - Cybersecurity Event Analysis

**Scale:** 1M+ events/sec, 100TB+ data, sub-second threat detection

```
┌─────────────────────────────────────────────────────────────────────┐
│                Symantec Security Analytics Architecture               │
│                                                                     │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                               │
│  │ FW   │ │ IDS  │ │ EDR  │ │ Proxy│  ← Security Appliances        │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘                               │
│     │        │        │        │                                    │
│     ▼        ▼        ▼        ▼                                    │
│  ┌─────────────────────────────────────────┐                        │
│  │           Kafka Cluster                  │                        │
│  │     (Partitioned by source_type)         │                        │
│  │     Retention: 72 hours                  │                        │
│  └────────────────────┬────────────────────┘                        │
│                       │                                             │
│          ┌────────────┼────────────┐                                │
│          ▼            ▼            ▼                                 │
│  ┌─────────────┐ ┌────────┐ ┌──────────────┐                       │
│  │  Stream     │ │ Batch  │ │  TimescaleDB  │                       │
│  │  Processor  │ │ Loader │ │  Cluster      │                       │
│  │  (Flink)    │ │(COPY)  │ │              │                       │
│  │  Real-time  │ │        │ │  3 Access    │                       │
│  │  Alerting   │ │        │ │  Nodes       │                       │
│  └─────────────┘ └───┬────┘ │  12 Data     │                       │
│                       │      │  Nodes       │                       │
│                       ▼      │              │                       │
│              ┌────────────┐  │  Hypertables:│                       │
│              │ Enrichment │  │  - net_events│                       │
│              │ (GeoIP,    │  │  - auth_logs │                       │
│              │  Threat    │──►│  - dns_logs  │                       │
│              │  Intel)    │  │  - alerts    │                       │
│              └────────────┘  └──────┬───────┘                       │
│                                     │                               │
│                          ┌──────────┼──────────┐                    │
│                          ▼          ▼          ▼                    │
│                   ┌──────────┐ ┌────────┐ ┌─────────┐              │
│                   │  SIEM    │ │ Threat │ │ Forensic│              │
│                   │  Console │ │ Hunter │ │ Queries │              │
│                   └──────────┘ └────────┘ └─────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

**Schema:**

```sql
CREATE TABLE network_events (
    time           TIMESTAMPTZ NOT NULL,
    source_ip      INET NOT NULL,
    dest_ip        INET NOT NULL,
    source_port    INT,
    dest_port      INT,
    protocol       SMALLINT,          -- 6=TCP, 17=UDP
    bytes_sent     BIGINT,
    bytes_recv     BIGINT,
    packets        INT,
    action         TEXT,              -- 'allow','deny','drop'
    threat_score   SMALLINT DEFAULT 0,
    geo_source     TEXT,
    geo_dest       TEXT,
    sensor_id      TEXT NOT NULL
);

SELECT create_hypertable('network_events', 'time',
    chunk_time_interval => INTERVAL '15 minutes',  -- very high ingest
    partitioning_column => 'sensor_id',
    number_partitions => 32
);

-- Critical indexes for threat hunting
CREATE INDEX ON network_events (source_ip, time DESC);
CREATE INDEX ON network_events (dest_ip, time DESC);
CREATE INDEX ON network_events (dest_port, time DESC)
    WHERE action = 'deny';
CREATE INDEX ON network_events (time DESC)
    WHERE threat_score > 7;
```

**Continuous Aggregates:**

```sql
-- Traffic baseline per source (for anomaly detection)
CREATE MATERIALIZED VIEW traffic_baseline_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    source_ip,
    COUNT(*) AS connection_count,
    SUM(bytes_sent) AS total_bytes_out,
    COUNT(DISTINCT dest_ip) AS unique_destinations,
    COUNT(DISTINCT dest_port) AS unique_ports,
    AVG(threat_score) AS avg_threat
FROM network_events
GROUP BY bucket, source_ip;

-- Port scan detection aggregate
CREATE MATERIALIZED VIEW port_scan_candidates
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    source_ip,
    COUNT(DISTINCT dest_port) AS ports_scanned,
    COUNT(DISTINCT dest_ip) AS hosts_targeted,
    COUNT(*) FILTER (WHERE action = 'deny') AS denied_count
FROM network_events
GROUP BY bucket, source_ip
HAVING COUNT(DISTINCT dest_port) > 20;
```

**Queries:**

```sql
-- Detect lateral movement: internal host talking to many internal hosts
SELECT source_ip,
       COUNT(DISTINCT dest_ip) AS targets,
       array_agg(DISTINCT dest_port) AS ports_used
FROM network_events
WHERE time > NOW() - INTERVAL '10 minutes'
  AND source_ip <<= '10.0.0.0/8'
  AND dest_ip <<= '10.0.0.0/8'
GROUP BY source_ip
HAVING COUNT(DISTINCT dest_ip) > 50
ORDER BY targets DESC;
-- Latency: 50-200ms

-- Data exfiltration: unusual outbound volume
SELECT source_ip,
       time_bucket('5 minutes', time) AS bucket,
       SUM(bytes_sent) AS bytes_out
FROM network_events
WHERE time > NOW() - INTERVAL '1 hour'
  AND dest_ip NOT IN (SELECT ip FROM known_cdn_ranges)
GROUP BY source_ip, bucket
HAVING SUM(bytes_sent) > 100000000  -- >100MB in 5min
ORDER BY bytes_out DESC;
```

**Retention:**

```sql
-- Raw events: 30 days (massive volume)
SELECT add_retention_policy('network_events', INTERVAL '30 days');

-- 5-minute aggregates: 1 year
SELECT add_retention_policy('traffic_baseline_5m', INTERVAL '1 year');

-- Compression: after 1 hour (data is append-only)
ALTER TABLE network_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'sensor_id',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('network_events', INTERVAL '1 hour');
```

**Benchmarks:**
- Ingestion: 1.2M events/sec (multi-node, parallel COPY)
- Threat query (single IP, 10min window): 15-40ms
- Anomaly scan (all sources, 5min window): 500ms-2s
- Compression ratio: 18x (IP addresses compress well with dictionary)
- Storage: 50TB raw/month → 2.8TB compressed

---

### 4. Siemens Gamesa - Wind Turbine Predictive Maintenance

**Scale:** 30,000+ turbines, 200+ sensors each, 500K rows/sec

```
┌─────────────────────────────────────────────────────────────────────┐
│           Siemens Gamesa Wind Analytics Architecture                  │
│                                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐       ┌─────────┐          │
│  │Turbine 1│  │Turbine 2│  │Turbine 3│  ...  │Turbine N│          │
│  │ 200+    │  │ 200+    │  │ 200+    │       │ 200+    │          │
│  │ sensors │  │ sensors │  │ sensors │       │ sensors │          │
│  └────┬────┘  └────┬────┘  └────┬────┘       └────┬────┘          │
│       │             │            │                  │               │
│       ▼             ▼            ▼                  ▼               │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │              Edge Gateway (per wind farm)                │        │
│  │         Local buffering + downsampling                  │        │
│  │         SCADA protocol translation                      │        │
│  └────────────────────────┬────────────────────────────────┘        │
│                           │  MQTT / AMQP                            │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │              Cloud Ingestion (Azure IoT Hub)             │        │
│  └────────────────────────┬────────────────────────────────┘        │
│                           │                                         │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │                    TimescaleDB                           │        │
│  │                                                         │        │
│  │   Hypertable: turbine_telemetry                         │        │
│  │   Chunk interval: 4 hours                               │        │
│  │   Space partitions: by wind_farm_id (64)                │        │
│  │                                                         │        │
│  │   Continuous Aggregates:                                │        │
│  │   - turbine_10m (power curves, efficiency)              │        │
│  │   - turbine_1h  (maintenance KPIs)                      │        │
│  │   - turbine_1d  (capacity factor, availability)         │        │
│  └──────────────────┬──────────────────────────────────────┘        │
│                     │                                               │
│          ┌──────────┼──────────────┐                                │
│          ▼          ▼              ▼                                 │
│  ┌────────────┐ ┌──────────┐ ┌─────────────────┐                   │
│  │Predictive  │ │ Power    │ │  Fleet          │                   │
│  │Maintenance │ │ Forecast │ │  Management     │                   │
│  │ML Models   │ │ (weather)│ │  Dashboard      │                   │
│  └────────────┘ └──────────┘ └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Schema:**

```sql
CREATE TABLE turbine_telemetry (
    time             TIMESTAMPTZ NOT NULL,
    wind_farm_id     INT NOT NULL,
    turbine_id       TEXT NOT NULL,
    wind_speed       REAL,           -- m/s
    wind_direction   REAL,           -- degrees
    rotor_speed      REAL,           -- RPM
    power_output     REAL,           -- kW
    blade_pitch      REAL,           -- degrees
    nacelle_temp     REAL,           -- Celsius
    gearbox_temp     REAL,
    bearing_temp     REAL,
    vibration_x      REAL,
    vibration_y      REAL,
    vibration_z      REAL,
    yaw_angle        REAL,
    grid_frequency   REAL,
    status_code      SMALLINT       -- 0=running,1=standby,2=fault,3=maintenance
);

SELECT create_hypertable('turbine_telemetry', 'time',
    chunk_time_interval => INTERVAL '4 hours',
    partitioning_column => 'wind_farm_id',
    number_partitions => 64
);

ALTER TABLE turbine_telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'turbine_id',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('turbine_telemetry', INTERVAL '2 days');
```

**Continuous Aggregates:**

```sql
-- 10-minute aggregates for power curve analysis
CREATE MATERIALIZED VIEW turbine_10m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('10 minutes', time) AS bucket,
    wind_farm_id, turbine_id,
    AVG(wind_speed) AS avg_wind,
    AVG(power_output) AS avg_power,
    AVG(rotor_speed) AS avg_rpm,
    MAX(vibration_x) AS max_vib_x,
    MAX(vibration_y) AS max_vib_y,
    MAX(gearbox_temp) AS max_gearbox_temp,
    MAX(bearing_temp) AS max_bearing_temp,
    AVG(blade_pitch) AS avg_pitch,
    COUNT(*) FILTER (WHERE status_code = 0) AS running_samples,
    COUNT(*) AS total_samples
FROM turbine_telemetry
GROUP BY bucket, wind_farm_id, turbine_id;

-- Daily KPIs
CREATE MATERIALIZED VIEW turbine_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', bucket) AS day,
    wind_farm_id, turbine_id,
    AVG(avg_power) AS avg_power,
    MAX(max_gearbox_temp) AS peak_gearbox_temp,
    SUM(running_samples)::FLOAT / NULLIF(SUM(total_samples), 0) AS availability,
    AVG(avg_power) / 3000.0 AS capacity_factor  -- 3MW rated
FROM turbine_10m
GROUP BY 1, wind_farm_id, turbine_id;
```

**Queries:**

```sql
-- Power curve deviation (early fault indicator)
WITH expected_power AS (
    SELECT wind_speed_bin, avg_power AS expected
    FROM turbine_power_curves
    WHERE turbine_model = 'SG-3.4-132'
)
SELECT t.turbine_id,
       ROUND(t.avg_wind) AS wind_bin,
       AVG(t.avg_power) AS actual_power,
       ep.expected,
       (AVG(t.avg_power) - ep.expected) / ep.expected * 100 AS deviation_pct
FROM turbine_10m t
JOIN expected_power ep ON ROUND(t.avg_wind) = ep.wind_speed_bin
WHERE t.bucket > NOW() - INTERVAL '7 days'
  AND t.running_samples > 5
GROUP BY t.turbine_id, wind_bin, ep.expected
HAVING ABS((AVG(t.avg_power) - ep.expected) / ep.expected) > 0.1;

-- Gearbox temperature trend (predictive maintenance)
SELECT turbine_id,
       time_bucket_gapfill('1 day', bucket) AS day,
       LOCF(AVG(max_gearbox_temp)) AS gearbox_temp_trend
FROM turbine_10m
WHERE wind_farm_id = 42
  AND bucket > NOW() - INTERVAL '90 days'
GROUP BY turbine_id, day
ORDER BY turbine_id, day;
```

**Retention:**

```sql
SELECT add_retention_policy('turbine_telemetry', INTERVAL '180 days');
SELECT add_retention_policy('turbine_10m', INTERVAL '3 years');
-- Daily aggregates kept indefinitely
```

**Benchmarks:**
- Ingestion: 500K rows/sec (30K turbines x ~17 readings/sec)
- Single turbine query (7-day window): 20-60ms
- Fleet-wide anomaly scan: 2-5s
- Compression ratio: 12x (sensor floats compress well with gorilla)
- Storage: 800GB raw/day → 67GB compressed

---

### 5. Fleet Management - Automotive Telemetry

**Scale:** 200,000+ vehicles, 1-second GPS + OBD-II, 800K rows/sec

```
┌─────────────────────────────────────────────────────────────────────┐
│              Fleet Management Telemetry Architecture                  │
│                                                                     │
│  ┌──────┐  ┌──────┐  ┌──────┐          ┌──────┐                    │
│  │ Van  │  │ Van  │  │Truck │   ...    │ Van  │  ← 200K vehicles   │
│  │ OBD  │  │ OBD  │  │ OBD  │          │ OBD  │                    │
│  │ GPS  │  │ GPS  │  │ GPS  │          │ GPS  │                    │
│  └──┬───┘  └──┬───┘  └──┬───┘          └──┬───┘                    │
│     │         │         │                  │                        │
│     └─────────┴─────────┴──────────────────┘                        │
│                         │  4G/LTE                                    │
│                         ▼                                           │
│  ┌───────────────────────────────────────────────────┐              │
│  │         API Gateway + Message Queue               │              │
│  │         (NATS / AWS Kinesis)                      │              │
│  └──────────────────────┬────────────────────────────┘              │
│                         │                                           │
│          ┌──────────────┼──────────────┐                            │
│          ▼              ▼              ▼                             │
│  ┌─────────────┐ ┌───────────┐ ┌─────────────┐                     │
│  │  Geofence   │ │  Ingest   │ │  Real-time  │                     │
│  │  Engine     │ │  Workers  │ │  ETA Engine │                     │
│  │  (PostGIS)  │ │  (COPY)   │ │             │                     │
│  └─────────────┘ └─────┬─────┘ └─────────────┘                     │
│                         │                                           │
│                         ▼                                           │
│  ┌───────────────────────────────────────────────────┐              │
│  │              TimescaleDB + PostGIS                  │              │
│  │                                                   │              │
│  │   Hypertables:                                    │              │
│  │   - vehicle_positions (GPS + speed)               │              │
│  │   - vehicle_diagnostics (OBD-II)                  │              │
│  │   - trip_events (start/stop/idle)                 │              │
│  │                                                   │              │
│  │   PostGIS: geofences, route corridors             │              │
│  │   Chunk interval: 2 hours                         │              │
│  └───────────────────────┬───────────────────────────┘              │
│                          │                                          │
│            ┌─────────────┼─────────────┐                            │
│            ▼             ▼             ▼                             │
│     ┌───────────┐ ┌───────────┐ ┌──────────────┐                   │
│     │  Live Map │ │  Route    │ │  Driver      │                   │
│     │  Tracking │ │  Analytics│ │  Scorecards  │                   │
│     └───────────┘ └───────────┘ └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Schema:**

```sql
-- Enable PostGIS (TimescaleDB works alongside PostGIS)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE vehicle_positions (
    time           TIMESTAMPTZ NOT NULL,
    vehicle_id     TEXT NOT NULL,
    fleet_id       INT NOT NULL,
    location       GEOMETRY(Point, 4326) NOT NULL,
    speed_kmh      REAL,
    heading        REAL,
    altitude_m     REAL,
    hdop           REAL,             -- GPS accuracy
    ignition       BOOLEAN,
    odometer_km    DOUBLE PRECISION
);

SELECT create_hypertable('vehicle_positions', 'time',
    chunk_time_interval => INTERVAL '2 hours',
    partitioning_column => 'fleet_id',
    number_partitions => 8
);

CREATE INDEX ON vehicle_positions (vehicle_id, time DESC);
CREATE INDEX ON vehicle_positions USING GIST (location, time);

CREATE TABLE vehicle_diagnostics (
    time           TIMESTAMPTZ NOT NULL,
    vehicle_id     TEXT NOT NULL,
    fleet_id       INT NOT NULL,
    fuel_level_pct REAL,
    engine_rpm     INT,
    coolant_temp   REAL,
    battery_volts  REAL,
    dtc_codes      TEXT[],           -- diagnostic trouble codes
    fuel_rate_lph  REAL
);

SELECT create_hypertable('vehicle_diagnostics', 'time',
    chunk_time_interval => INTERVAL '2 hours',
    partitioning_column => 'fleet_id',
    number_partitions => 8
);

-- Compression
ALTER TABLE vehicle_positions SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'vehicle_id',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('vehicle_positions', INTERVAL '1 day');
```

**Continuous Aggregates:**

```sql
-- Trip summaries (5-minute resolution)
CREATE MATERIALIZED VIEW vehicle_trips_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    vehicle_id, fleet_id,
    AVG(speed_kmh) AS avg_speed,
    MAX(speed_kmh) AS max_speed,
    COUNT(*) FILTER (WHERE speed_kmh > 120) AS speeding_count,
    COUNT(*) FILTER (WHERE speed_kmh = 0 AND ignition) AS idle_count,
    MAX(odometer_km) - MIN(odometer_km) AS distance_km,
    COUNT(*) AS samples
FROM vehicle_positions
GROUP BY bucket, vehicle_id, fleet_id;

-- Daily driver scorecards
CREATE MATERIALIZED VIEW driver_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', bucket) AS day,
    vehicle_id, fleet_id,
    AVG(avg_speed) AS avg_speed,
    MAX(max_speed) AS top_speed,
    SUM(speeding_count) AS total_speeding_events,
    SUM(idle_count) * 5.0 / NULLIF(SUM(samples), 0) * 100 AS idle_pct,
    SUM(distance_km) AS total_km
FROM vehicle_trips_5m
GROUP BY 1, vehicle_id, fleet_id;
```

**Queries:**

```sql
-- Real-time: all vehicles in a geofence
SELECT vehicle_id, speed_kmh, ST_AsGeoJSON(location) AS position
FROM vehicle_positions
WHERE time > NOW() - INTERVAL '30 seconds'
  AND ST_Within(location, (SELECT geom FROM geofences WHERE name = 'warehouse-A'));
-- Latency: 10-30ms

-- Route replay for a vehicle
SELECT time, ST_X(location) AS lng, ST_Y(location) AS lat, speed_kmh
FROM vehicle_positions
WHERE vehicle_id = 'VAN-4521'
  AND time BETWEEN '2024-03-15 08:00' AND '2024-03-15 17:00'
ORDER BY time;

-- Fleet fuel efficiency report
SELECT vehicle_id,
       time_bucket('1 week', time) AS week,
       SUM(fuel_rate_lph) / NULLIF(COUNT(*), 0) * 3600 AS avg_lph,
       (MAX(odometer_km) - MIN(odometer_km)) /
           NULLIF(SUM(fuel_rate_lph) / 3600, 0) AS km_per_liter
FROM vehicle_diagnostics
WHERE fleet_id = 7
  AND time > NOW() - INTERVAL '3 months'
GROUP BY vehicle_id, week
ORDER BY km_per_liter ASC;
```

**Retention:**

```sql
-- Raw positions: 60 days
SELECT add_retention_policy('vehicle_positions', INTERVAL '60 days');

-- Raw diagnostics: 90 days
SELECT add_retention_policy('vehicle_diagnostics', INTERVAL '90 days');

-- 5-minute trips: 2 years
SELECT add_retention_policy('vehicle_trips_5m', INTERVAL '2 years');

-- Daily scorecards: kept forever
```

**Benchmarks:**
- Ingestion: 800K rows/sec (200K vehicles at ~4 readings/sec avg)
- Geofence query (single vehicle, last 30s): 5-15ms
- Route replay (full day): 30-80ms
- Fleet aggregate (1 week, 10K vehicles): 1-3s
- Compression ratio: 16x (GPS coordinates with delta-of-delta)
- Storage: 300GB raw/day → 19GB compressed

---

## Replication

### PostgreSQL Streaming Replication

TimescaleDB is a PostgreSQL extension, so standard PG replication works:

```
┌──────────────────────────────────────────────────────────────┐
│                  Streaming Replication                         │
│                                                              │
│  ┌─────────────┐     WAL Stream      ┌─────────────┐        │
│  │   Primary   │ ──────────────────► │  Replica 1  │        │
│  │  (R/W)      │                      │  (Read-only)│        │
│  │             │     WAL Stream      ┌─────────────┐        │
│  │  TimescaleDB│ ──────────────────► │  Replica 2  │        │
│  │  extension  │                      │  (Read-only)│        │
│  └─────────────┘                      └─────────────┘        │
│                                                              │
│  • Synchronous or async                                      │
│  • Replicas have same chunks, compression, caggs             │
│  • Use pg_basebackup for initial setup                       │
│  • TimescaleDB must be same version on all nodes             │
└──────────────────────────────────────────────────────────────┘
```

### Multi-Node Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              TimescaleDB Multi-Node (Distributed)                  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐      │
│  │                   Access Node (AN)                      │      │
│  │  • Receives all queries and INSERTs                     │      │
│  │  • Distributed hypertable metadata                      │      │
│  │  • Query planning and chunk routing                     │      │
│  │  • No local chunk storage (coordinator only)            │      │
│  └───────────────────────┬────────────────────────────────┘      │
│              ┌────────────┼────────────┐                          │
│              ▼            ▼            ▼                           │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐           │
│  │  Data Node 1  │ │  Data Node 2  │ │  Data Node 3  │           │
│  │               │ │               │ │               │           │
│  │ Chunks:       │ │ Chunks:       │ │ Chunks:       │           │
│  │  t1_chunk_1   │ │  t1_chunk_2   │ │  t1_chunk_3   │           │
│  │  t1_chunk_4   │ │  t1_chunk_5   │ │  t1_chunk_6   │           │
│  │  (replicated  │ │  (replicated  │ │  (replicated  │           │
│  │   to DN2)     │ │   to DN3)     │ │   to DN1)     │           │
│  └───────────────┘ └───────────────┘ └───────────────┘           │
│                                                                  │
│  Setup:                                                          │
│  SELECT add_data_node('dn1', host => 'dn1.internal');            │
│  SELECT add_data_node('dn2', host => 'dn2.internal');            │
│  SELECT add_data_node('dn3', host => 'dn3.internal');            │
│                                                                  │
│  CREATE TABLE metrics (time TIMESTAMPTZ, device TEXT, val FLOAT);│
│  SELECT create_distributed_hypertable('metrics', 'time',         │
│      partitioning_column => 'device',                            │
│      data_nodes => ARRAY['dn1','dn2','dn3'],                     │
│      replication_factor => 2);                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Patroni HA with TimescaleDB

```
┌─────────────────────────────────────────────────────────────────┐
│                  Patroni + TimescaleDB HA                         │
│                                                                 │
│  ┌─────────────────┐                                            │
│  │   HAProxy /     │  ← Clients connect here                    │
│  │   PgBouncer     │     Port 5432 → primary                    │
│  │                 │     Port 5433 → replicas (read)             │
│  └────────┬────────┘                                            │
│           │                                                     │
│  ┌────────┼──────────────────────────────┐                      │
│  │        ▼            ▼            ▼    │                      │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │  │ Patroni  │ │ Patroni  │ │ Patroni  │                     │
│  │  │ Node 1   │ │ Node 2   │ │ Node 3   │                     │
│  │  │ (Leader) │ │ (Replica)│ │ (Replica)│                     │
│  │  │ TSDB ext │ │ TSDB ext │ │ TSDB ext │                     │
│  │  └──────────┘ └──────────┘ └──────────┘                     │
│  │       │             │            │                           │
│  │       ▼             ▼            ▼                           │
│  │  ┌──────────────────────────────────────┐                    │
│  │  │        etcd / Consul / ZooKeeper     │                    │
│  │  │        (DCS - leader election)        │                    │
│  │  └──────────────────────────────────────┘                    │
│  └──────────────────────────────────────────┘                   │
│                                                                 │
│  patroni.yml additions:                                         │
│    postgresql:                                                   │
│      parameters:                                                │
│        shared_preload_libraries: 'timescaledb'                  │
│      pg_hba:                                                    │
│        - host replication replicator 0.0.0.0/0 md5             │
└─────────────────────────────────────────────────────────────────┘
```

### Logical Replication Considerations

- TimescaleDB hypertables **cannot** be directly published via logical replication (chunks are internal)
- Workaround: replicate the underlying chunk tables or use `pglogical` with chunk mapping
- For cross-cluster replication, use `pg_dump` + continuous aggregate materialization
- TimescaleDB 2.10+ supports logical replication for continuous aggregates (materialized hypertables)
- Multi-node uses its own internal 2PC protocol (not PG logical replication)

---

## Scalability

### Hypertables and Chunks Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Chunk Lifecycle & Partitioning                          │
│                                                                         │
│  Time Dimension ──────────────────────────────────────────────────►     │
│                                                                         │
│  Space     ┌─────────┬─────────┬─────────┬─────────┬─────────┐         │
│  Dim       │  Week 1 │  Week 2 │  Week 3 │  Week 4 │  Week 5 │         │
│  (hash)    ├─────────┼─────────┼─────────┼─────────┼─────────┤         │
│    0       │  HOT    │COMPRESS │COMPRESS │ TIERED  │ DROPPED │         │
│            │  (R/W)  │  (10x)  │  (10x)  │  (S3)   │         │         │
│  ──────────┼─────────┼─────────┼─────────┼─────────┼─────────┤         │
│    1       │  HOT    │COMPRESS │COMPRESS │ TIERED  │ DROPPED │         │
│            │  (R/W)  │  (10x)  │  (10x)  │  (S3)   │         │         │
│  ──────────┼─────────┼─────────┼─────────┼─────────┼─────────┤         │
│    2       │  HOT    │COMPRESS │COMPRESS │ TIERED  │ DROPPED │         │
│            │  (R/W)  │  (10x)  │  (10x)  │  (S3)   │         │         │
│  ──────────┼─────────┼─────────┼─────────┼─────────┼─────────┤         │
│    3       │  HOT    │COMPRESS │COMPRESS │ TIERED  │ DROPPED │         │
│            │  (R/W)  │  (10x)  │  (10x)  │  (S3)   │         │         │
│            └─────────┴─────────┴─────────┴─────────┴─────────┘         │
│                                                                         │
│  Policies:                                                              │
│    compress_after: 7 days                                               │
│    tier_after: 30 days (move to object storage)                         │
│    drop_after: 90 days                                                  │
│                                                                         │
│  Each chunk = independent PostgreSQL table                              │
│  Chunk size target: 1-4 GB uncompressed (fits in memory)                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Chunk Interval Selection Guide

| Data Rate | Recommended Chunk Interval | Rationale |
|-----------|---------------------------|-----------|
| <1K rows/sec | 1 week | Fewer chunks, less overhead |
| 1K-10K rows/sec | 1 day | Good balance |
| 10K-100K rows/sec | 4-6 hours | Chunks fit in memory |
| 100K-1M rows/sec | 1-2 hours | Fast compression, parallelism |
| >1M rows/sec | 15-30 minutes | Minimize write amplification |

**Rule of thumb:** Each chunk should be ~25% of available memory when uncompressed.

### Multi-Node Distributed Hypertables

```sql
-- Distribute data across nodes by device_id + time
SELECT create_distributed_hypertable('metrics', 'time',
    partitioning_column => 'device_id',
    number_partitions => 32,
    replication_factor => 2);

-- Queries are pushed down to data nodes
-- Aggregation happens in parallel across nodes
-- Access node merges partial results
```

### Continuous Aggregates Hierarchy

```
┌─────────────────────────────────────────────────────┐
│           Aggregate Hierarchy (Caggs on Caggs)       │
│                                                     │
│   Raw Data (1-sec resolution)                       │
│       │                                             │
│       ▼ refresh every 1 min                         │
│   1-Minute Aggregate                                │
│       │                                             │
│       ▼ refresh every 10 min                        │
│   1-Hour Aggregate                                  │
│       │                                             │
│       ▼ refresh every 1 hour                        │
│   1-Day Aggregate                                   │
│                                                     │
│  Query hits the appropriate level based on           │
│  requested time range and resolution                │
└─────────────────────────────────────────────────────┘
```

### Comparison at Scale

| Feature | TimescaleDB | InfluxDB | Prometheus |
|---------|-------------|----------|------------|
| Query Language | Full SQL | InfluxQL/Flux | PromQL |
| JOINs | Yes (it's PG) | Limited | No |
| Cardinality | Unlimited | Degrades >10M series | Degrades >5M series |
| Compression | 10-20x | 5-10x | 1-2 bytes/sample |
| Ingestion (single node) | 1-2M rows/sec | 500K points/sec | 200K samples/sec |
| Ingestion (cluster) | 10M+ rows/sec | 2M+ points/sec | N/A (federate) |
| Retention Policies | Yes (per hypertable) | Yes (per database) | Yes (global) |
| Ecosystem | PostgreSQL (all tools) | Custom | Custom |
| Replication | PG streaming + multi-node | Raft (Enterprise) | N/A (Thanos/Cortex) |
| Best For | Complex queries, JOINs, mixed workloads | Pure metrics, simple queries | Monitoring, alerting |

---

## Production Setup

### Chunk Interval Sizing

```sql
-- Check current chunk sizes
SELECT hypertable_name,
       chunk_name,
       range_start, range_end,
       pg_size_pretty(total_bytes) AS size,
       pg_size_pretty(table_bytes) AS table_size,
       pg_size_pretty(index_bytes) AS index_size
FROM timescaledb_information.chunks
WHERE hypertable_name = 'sensor_data'
ORDER BY range_start DESC
LIMIT 10;

-- Adjust chunk interval if needed
SELECT set_chunk_time_interval('sensor_data', INTERVAL '4 hours');
-- Only affects NEW chunks; existing chunks unchanged
```

### Compression Configuration

```sql
-- Choose segmentby = columns you filter by most (WHERE clause)
-- Choose orderby = how you typically ORDER results
ALTER TABLE sensor_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, sensor_type',
    timescaledb.compress_orderby = 'time DESC',
    timescaledb.compress_chunk_time_interval = '1 day'  -- merge chunks on compress
);

-- Check compression stats
SELECT
    hypertable_name,
    pg_size_pretty(before_compression_total_bytes) AS before,
    pg_size_pretty(after_compression_total_bytes) AS after,
    ROUND(before_compression_total_bytes::NUMERIC /
          after_compression_total_bytes, 1) AS ratio
FROM timescaledb_information.compression_settings cs
JOIN hypertable_compression_stats('sensor_data') s ON true;

-- Manual compression of specific chunk
SELECT compress_chunk('_timescaledb_internal._hyper_1_42_chunk');

-- Decompress for backfill
SELECT decompress_chunk('_timescaledb_internal._hyper_1_42_chunk');
```

### Background Workers

```
# postgresql.conf
timescaledb.max_background_workers = 16        # default: 8
timescaledb.max_scheduler_workers = 2          # job scheduler
timescaledb.max_compression_workers = 4        # parallel compress

# For multi-node
timescaledb.max_insert_batch_size = 10000      # batch inserts to data nodes
timescaledb.max_copy_batch_size = 10000

# Memory
shared_buffers = '16GB'                        # 25% of RAM
effective_cache_size = '48GB'                   # 75% of RAM
work_mem = '256MB'                             # for sorting/hashing
maintenance_work_mem = '2GB'                   # for compression/reindex
```

### Monitoring

```sql
-- Job status (compression, retention, cagg refresh)
SELECT job_id, application_name, schedule_interval,
       last_run_status, last_run_duration, next_start
FROM timescaledb_information.jobs
JOIN timescaledb_information.job_stats USING (job_id)
ORDER BY next_start;

-- Chunk information
SELECT hypertable_name, COUNT(*) AS num_chunks,
       pg_size_pretty(SUM(total_bytes)) AS total_size,
       pg_size_pretty(SUM(compressed_total_bytes)) AS compressed_size
FROM timescaledb_information.chunks
GROUP BY hypertable_name;

-- Continuous aggregate freshness
SELECT view_name, completed_threshold, invalidation_threshold
FROM timescaledb_information.continuous_aggregates;

-- Slow queries
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
WHERE query LIKE '%sensor_data%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### Backup & Restore

```bash
# Backup (use timescaledb-specific flags)
pg_dump -Fc -f backup.dump \
  --no-tablespaces \
  -d tsdb

# Restore (must pre/post restore for timescaledb)
# 1. Create empty database with timescaledb extension
psql -c "CREATE DATABASE tsdb;"
psql -d tsdb -c "CREATE EXTENSION timescaledb;"

# 2. Run pre-restore
psql -d tsdb -c "SELECT timescaledb_pre_restore();"

# 3. Restore data
pg_restore -Fc -d tsdb backup.dump \
  --no-tablespaces

# 4. Run post-restore
psql -d tsdb -c "SELECT timescaledb_post_restore();"

# For continuous backups: use pgBackRest or WAL-E/WAL-G
# pgBackRest works seamlessly with TimescaleDB (WAL archiving)
```

### Production Checklist

```
[ ] Chunk interval sized to ~25% of RAM
[ ] Compression enabled with correct segmentby/orderby
[ ] Compression policy set (typically 1-7 days)
[ ] Retention policies configured per hypertable
[ ] Continuous aggregates for common query patterns
[ ] Refresh policies set for all continuous aggregates
[ ] Background workers tuned (max_background_workers)
[ ] shared_preload_libraries includes 'timescaledb'
[ ] Monitoring: job_stats, chunk sizes, compression ratios
[ ] Backups with pre/post restore scripts
[ ] pg_stat_statements enabled for query analysis
[ ] Connection pooling (PgBouncer) in front of TimescaleDB
[ ] Streaming replication or Patroni for HA
[ ] WAL archiving for PITR (pgBackRest recommended)
[ ] Tested: decompress_chunk for backfill scenarios
```

---

## Summary: When to Use TimescaleDB

| Use TimescaleDB When | Don't Use When |
|---------------------|----------------|
| You need full SQL + JOINs on time-series | Simple key-value metrics only |
| High cardinality (millions of devices) | InfluxDB cardinality is sufficient |
| Complex queries, CTEs, window functions | PromQL/Flux is enough |
| You already run PostgreSQL | You need a fully managed zero-ops solution |
| You need PostGIS + time-series | Pure geospatial without temporal |
| Mixed workload (OLTP + time-series) | Pure OLAP (use ClickHouse) |
| You want one DB for relational + time-series | Separate concerns mandated |
