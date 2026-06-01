# InfluxDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Storage Engine Internals](#storage-engine-internals)
3. [Data Model & Schema Design](#data-model--schema-design)
4. [Query Languages (Flux & InfluxQL)](#query-languages)
5. [Write Path & Ingestion](#write-path--ingestion)
6. [Continuous Queries & Tasks](#continuous-queries--tasks)
7. [Clustering & High Availability](#clustering--high-availability)
8. [Performance & Resource Optimization](#performance--resource-optimization)
9. [Production Deployment Patterns](#production-deployment-patterns)
10. [Telegraf & Ecosystem](#telegraf--ecosystem)
11. [Security & Multi-tenancy](#security--multi-tenancy)
12. [Use Case Architectures](#use-case-architectures)
13. [Staff Architect Interview Questions](#staff-architect-interview-questions)
14. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is InfluxDB?
```
InfluxDB is a purpose-built time-series database designed for high-write
throughput, compressed storage, and real-time querying of timestamped data.
Developed by InfluxData, it is the "I" in the TICK stack (Telegraf, InfluxDB,
Chronograf, Kapacitor).

Version history:
- InfluxDB 1.x: InfluxQL, TSM engine, retention policies
- InfluxDB 2.x: Flux language, unified platform (UI, tasks, alerts)
- InfluxDB 3.x (IOx): Apache Arrow, DataFusion, Parquet, object storage

Key characteristics:
- Purpose-built for time-series workloads
- Schema-on-write (no predefined schema required)
- High write throughput (millions of points/second)
- Columnar compression (TSM engine)
- Built-in downsampling and retention
- Line protocol (simple text-based ingestion)
- SQL support (InfluxDB 3.x)

NOT designed for:
- General-purpose OLTP workloads
- Complex joins across measurements
- Transactions with ACID guarantees
- Document storage or full-text search
- Pull-based monitoring (use Prometheus)

Comparison:
┌────────────────────┬────────────┬──────────────┬──────────────┬────────────┐
│                    │ InfluxDB   │ Prometheus   │ TimescaleDB  │ VictoriaM. │
├────────────────────┼────────────┼──────────────┼──────────────┼────────────┤
│ Data Model         │ Tags+Fields│ Labels+Value │ Relational   │ Labels+Val │
│ Write Model        │ Push       │ Pull         │ Push (SQL)   │ Pull+Push  │
│ Query Language     │ Flux/SQL   │ PromQL       │ SQL          │ MetricsQL  │
│ Schema             │ Schemaless │ Schemaless   │ Schema       │ Schemaless │
│ Best For           │ IoT/Metrics│ K8s/Infra    │ Analytics    │ Metrics    │
│ Cardinality        │ Moderate   │ Moderate     │ High         │ Very High  │
│ Joins              │ Limited    │ None         │ Full SQL     │ None       │
│ Compression        │ TSM/Parquet│ Gorilla      │ PG + custom  │ Custom     │
│ Retention          │ Built-in   │ Per-instance │ Policies     │ Built-in   │
└────────────────────┴────────────┴──────────────┴──────────────┴────────────┘
```

### Architecture Diagram (InfluxDB 2.x OSS)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     INFLUXDB 2.x SINGLE-NODE ARCHITECTURE                    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        CLIENT LAYER                                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │   │
│  │  │ Telegraf │  │ Client   │  │ InfluxDB │  │ Third-party      │    │   │
│  │  │ Agent    │  │ Libraries│  │ CLI      │  │ (Grafana, etc.)  │    │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘    │   │
│  │       │Line Protocol │ API         │                   │ API          │   │
│  └───────┼──────────────┼─────────────┼───────────────────┼──────────────┘   │
│          │              │             │                   │                   │
│          ▼              ▼             ▼                   ▼                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      HTTP API SERVER                                   │   │
│  │  /api/v2/write  │  /api/v2/query  │  /api/v2/tasks  │  /api/v2/...  │   │
│  └───────┬───────────────┬────────────────┬─────────────────────────────┘   │
│          │               │                │                                  │
│          ▼               │                ▼                                  │
│  ┌──────────────────┐   │   ┌──────────────────────────────────────────┐   │
│  │   WRITE PATH     │   │   │   TASK ENGINE                             │   │
│  │                   │   │   │   - Scheduled Flux scripts                │   │
│  │  Parse Line Proto │   │   │   - Downsampling                         │   │
│  │  Validate         │   │   │   - Alerting (checks + notifications)    │   │
│  │  Points → WAL     │   │   │   - ETL transformations                  │   │
│  │  WAL → Cache      │   │   └──────────────────────────────────────────┘   │
│  │  Cache → TSM      │   │                                                   │
│  └────────┬──────────┘   │                                                   │
│           │              ▼                                                    │
│           │   ┌──────────────────────────────────────────────────────────┐  │
│           │   │   QUERY ENGINE                                            │  │
│           │   │                                                           │  │
│           │   │   ┌──────────────┐  ┌──────────────┐                    │  │
│           │   │   │  Flux Engine │  │  InfluxQL    │                    │  │
│           │   │   │  (functional │  │  (SQL-like   │                    │  │
│           │   │   │   pipeline)  │  │   compat)    │                    │  │
│           │   │   └──────┬───────┘  └──────┬───────┘                    │  │
│           │   │          │                  │                             │  │
│           │   │          └────────┬─────────┘                            │  │
│           │   │                   ▼                                       │  │
│           │   │   ┌──────────────────────────────────────────────┐      │  │
│           │   │   │   Storage Access Layer (read)                 │      │  │
│           │   │   └──────────────────────────────────────────────┘      │  │
│           │   └──────────────────────────────────────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    TSM STORAGE ENGINE                                  │   │
│  │                                                                       │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │                      WAL (Write-Ahead Log)                      │  │   │
│  │  │  - Append-only file for durability                              │  │   │
│  │  │  - Snappy compressed                                            │  │   │
│  │  │  - Segments: 10MB each                                          │  │   │
│  │  └──────────────────────────┬─────────────────────────────────────┘  │   │
│  │                              │                                        │   │
│  │  ┌──────────────────────────▼─────────────────────────────────────┐  │   │
│  │  │                      CACHE (in-memory)                          │  │   │
│  │  │  - Sorted by time per series                                    │  │   │
│  │  │  - Size limit triggers snapshot + flush                         │  │   │
│  │  │  - Default: 1GB max (cache-max-memory-size)                    │  │   │
│  │  └──────────────────────────┬─────────────────────────────────────┘  │   │
│  │                              │ Flush (snapshot)                       │   │
│  │  ┌──────────────────────────▼─────────────────────────────────────┐  │   │
│  │  │                      TSM FILES (on disk)                        │  │   │
│  │  │                                                                 │  │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │  │   │
│  │  │  │ TSM L1  │ │ TSM L1  │ │ TSM L2  │ │ TSM L3  │            │  │   │
│  │  │  │ (2GB max│ │ (2GB max│ │(compacted│ │(compacted│            │  │   │
│  │  │  │  each)  │ │  each)  │ │  merge) │ │  merge) │            │  │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘            │  │   │
│  │  │                                                                 │  │   │
│  │  │  Structure per file:                                            │  │   │
│  │  │  [Header][Blocks...][Index][Footer]                            │  │   │
│  │  │  - Blocks: compressed time+value data per series               │  │   │
│  │  │  - Index: series key → block offsets + min/max time            │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │  Organization: data/{org_id}/{bucket_id}/autogen/{shard_id}/         │   │
│  │  Shards: time-based (shard group duration = 1 week default)          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### InfluxDB 3.x (IOx) Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INFLUXDB 3.x (IOx) NEW ARCHITECTURE                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        INGESTION                                      │   │
│  │  Line Protocol → Write Buffer (in-memory, WAL-backed)                │   │
│  └────────────────────────────────┬─────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                   QUERY ENGINE (DataFusion)                            │   │
│  │                                                                       │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │  Apache DataFusion (Rust-based SQL query engine)                │  │   │
│  │  │  - SQL & InfluxQL support                                       │  │   │
│  │  │  - Vectorized execution (Apache Arrow columnar format)          │  │   │
│  │  │  - Predicate pushdown to Parquet                                │  │   │
│  │  │  - Parallel execution                                           │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │  Data Format Stack:                                                   │   │
│  │  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────────┐    │   │
│  │  │ Apache Arrow│  │ Apache Parquet  │  │ Object Storage       │    │   │
│  │  │ (in-memory  │  │ (on-disk        │  │ (S3/GCS/Azure)       │    │   │
│  │  │  columnar)  │  │  columnar       │  │                      │    │   │
│  │  │             │  │  compressed)    │  │  Infinite scale      │    │   │
│  │  └─────────────┘  └─────────────────┘  └──────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Key improvements over TSM:                                                  │
│  - Parquet: industry-standard columnar format (interop with Spark, DuckDB)  │
│  - Unlimited cardinality (no series key limitation)                          │
│  - Object storage native (separate compute/storage)                         │
│  - SQL-first query language                                                  │
│  - Apache Arrow for zero-copy data sharing                                  │
│  - Better compression ratios                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Storage Engine Internals

### TSM (Time-Structured Merge Tree)
```
TSM is inspired by LSM trees but optimized for time-series:

Write Path:
  1. Parse line protocol points
  2. Append to WAL (durability)
  3. Insert into Cache (sorted in-memory structure)
  4. When cache full → snapshot + flush to TSM file
  5. Background compaction merges TSM files

┌────────────────────────────────────────────────────────────────┐
│                    TSM FILE INTERNALS                            │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  HEADER (5 bytes)                                          │ │
│  │  Magic number (4B) + Version (1B)                          │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  DATA BLOCKS                                               │ │
│  │                                                            │ │
│  │  Block 1: [CRC32][Length][Compressed timestamps+values]    │ │
│  │  Block 2: [CRC32][Length][Compressed timestamps+values]    │ │
│  │  Block 3: ...                                              │ │
│  │                                                            │ │
│  │  Compression per type:                                     │ │
│  │  - Timestamps: Delta-of-delta + simple8b / RLE             │ │
│  │  - Float64: XOR (Gorilla) encoding                         │ │
│  │  - Integer: Delta + ZigZag + simple8b                      │ │
│  │  - Boolean: Bit-packed                                     │ │
│  │  - String: Snappy compression                              │ │
│  │                                                            │ │
│  │  Max 1000 values per block                                 │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  INDEX SECTION                                             │ │
│  │                                                            │ │
│  │  Index Entry per series:                                   │ │
│  │  [Key Length][Key (measurement+tags+field)]                │ │
│  │  [Type][Count]                                             │ │
│  │  [MinTime][MaxTime][Offset][Size] × Count                 │ │
│  │                                                            │ │
│  │  Enables: binary search by series key + time range         │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  FOOTER (8 bytes)                                          │ │
│  │  Index offset (8B) - pointer to index start                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Max file size: 2GB                                              │
│  Files are immutable once written                                │
└────────────────────────────────────────────────────────────────┘

Compaction Levels:
  Level 1: Flush from cache (small files, many)
  Level 2: Merge multiple L1 files
  Level 3: Merge multiple L2 files  
  Level 4: Full compaction (optimal for reads)

  Each level reduces file count and improves read performance
  Compaction also removes deleted/expired data
```

### Series Key & Shard Organization
```
Series Key = measurement + sorted tag set + field name
Example: "cpu,host=server01,region=us-west usage_idle"

Shard organization:
┌────────────────────────────────────────────────────────────┐
│ Database/Bucket                                             │
│ ├── Retention Policy / Bucket retention                    │
│ │   ├── Shard Group 1 (time range: 2024-01-01 to 01-07)  │
│ │   │   ├── Shard 1 (series subset via hashing)           │
│ │   │   │   ├── WAL files                                 │
│ │   │   │   ├── Cache                                     │
│ │   │   │   └── TSM files                                 │
│ │   │   └── Shard 2                                       │
│ │   ├── Shard Group 2 (time range: 2024-01-07 to 01-14)  │
│ │   │   ├── Shard 3                                       │
│ │   │   └── Shard 4                                       │
│ │   └── ...                                               │
│ └── ...                                                    │
└────────────────────────────────────────────────────────────┘

Shard Group Duration (auto-calculated):
- Retention < 2 days  → 1 hour groups
- Retention < 6 months → 1 day groups  
- Retention ≥ 6 months → 7 day groups

Implication: Deleting old data = dropping entire shard groups (efficient)
```

---

## Data Model & Schema Design

### Core Concepts
```
Line Protocol Format:
  measurement,tag_key=tag_val field_key=field_val timestamp
  
Examples:
  cpu,host=server01,region=us-west usage_idle=98.3,usage_user=1.2 1609459200000000000
  weather,location=NYC temperature=72.5,humidity=45i 1609459200000000000

┌─────────────────────────────────────────────────────────────────┐
│ Concept         │ Description                                    │
├─────────────────┼────────────────────────────────────────────────┤
│ Measurement     │ Logical grouping (like a table)                │
│ Tag (key=value) │ Indexed metadata (string only)                 │
│ Field (key=val) │ Actual data values (float, int, string, bool) │
│ Timestamp       │ Nanosecond precision Unix time                  │
│ Series          │ Unique combination: measurement + tag set       │
│ Point           │ Single observation (series + timestamp + fields)│
│ Bucket          │ Container with retention policy (2.x)           │
│ Organization    │ Multi-tenant namespace (2.x)                    │
└─────────────────┴────────────────────────────────────────────────┘

Critical distinction - Tags vs Fields:
┌─────────────────┬────────────────────────┬────────────────────────┐
│                 │ TAGS                    │ FIELDS                  │
├─────────────────┼────────────────────────┼────────────────────────┤
│ Indexed         │ YES (fast lookups)      │ NO (scan required)     │
│ Data type       │ String only             │ Float/Int/String/Bool  │
│ Cardinality     │ Impacts series count    │ No cardinality impact  │
│ GROUP BY        │ Yes                     │ No (in InfluxQL)       │
│ Required        │ No                      │ At least one required  │
│ Use for         │ Metadata, dimensions    │ Measurements, values   │
└─────────────────┴────────────────────────┴────────────────────────┘
```

### Schema Design Best Practices
```
GOOD schema design:
  # Separate measurements for different metric types
  cpu,host=srv01,cpu=cpu0 usage_idle=98.3,usage_system=0.5
  mem,host=srv01 used_percent=45.2,available=8589934592
  disk,host=srv01,device=sda1 used_percent=67.1

BAD schema design:
  # Don't encode data in measurement names
  cpu.server01.us-west.usage_idle value=98.3  ← WRONG
  
  # Don't use high-cardinality tags
  requests,user_id=a8f3b2c1 duration=0.234   ← WRONG (millions of users)
  
  # Don't store time in tags
  sensor,date=2024-01-15 temp=23.5            ← WRONG

Series cardinality calculation:
  Cardinality = Σ (unique_tag_combinations per measurement)
  
  Example:
  cpu measurement: 100 hosts × 16 CPUs = 1,600 series
  mem measurement: 100 hosts = 100 series
  disk measurement: 100 hosts × 4 devices = 400 series
  Total: 2,100 series ← healthy

  WARNING zones:
  - < 100K series: Comfortable
  - 100K - 1M: Monitor carefully
  - 1M - 10M: Performance tuning needed
  - > 10M: Architecture redesign needed (InfluxDB 1.x/2.x)
```

---

## Query Languages

### Flux Language
```
Flux is a functional data scripting language:

// Basic query
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage_idle")
  |> filter(fn: (r) => r.host == "server01")
  |> mean()

// Windowed aggregation (5-minute averages)
from(bucket: "metrics")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> aggregateWindow(every: 5m, fn: mean)

// Join two measurements
cpu = from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")

mem = from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "mem")

join(tables: {cpu: cpu, mem: mem}, on: ["host", "_time"])

// Moving average
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor")
  |> movingAverage(n: 10)

// Alert condition (threshold check)
from(bucket: "metrics")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage_idle")
  |> mean()
  |> map(fn: (r) => ({r with level:
    if r._value < 10.0 then "critical"
    else if r._value < 30.0 then "warning"
    else "ok"
  }))

// Downsampling task
option task = {name: "downsample_cpu", every: 1h}

from(bucket: "metrics")
  |> range(start: -task.every)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> aggregateWindow(every: 5m, fn: mean)
  |> to(bucket: "metrics_downsampled")
```

### InfluxQL (SQL-like)
```
-- Basic SELECT
SELECT usage_idle FROM cpu WHERE host = 'server01' AND time > now() - 1h

-- GROUP BY time (windowed aggregation)
SELECT MEAN(usage_idle) FROM cpu 
WHERE time > now() - 24h 
GROUP BY time(5m), host

-- Subqueries
SELECT MAX(mean_idle) FROM (
  SELECT MEAN(usage_idle) AS mean_idle FROM cpu 
  GROUP BY time(5m), host
) GROUP BY time(1h)

-- Continuous Queries (auto-downsampling, 1.x only)
CREATE CONTINUOUS QUERY "cq_cpu_5m" ON "mydb"
BEGIN
  SELECT MEAN(usage_idle) INTO "mydb"."rp_1year"."cpu_5m"
  FROM "cpu"
  GROUP BY time(5m), *
END

-- Regular expressions
SELECT * FROM /cpu|mem/ WHERE host =~ /server0[1-5]/
```

---

## Write Path & Ingestion

### Write Path Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                    WRITE PATH DETAILED FLOW                       │
│                                                                   │
│  Client sends: POST /api/v2/write                                │
│  Body: line protocol points                                      │
│                                                                   │
│  Step 1: PARSE                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Parse line protocol → Point structs                         │ │
│  │ Validate: measurement, tags, fields, timestamp             │ │
│  │ Sort tags alphabetically (canonical form)                   │ │
│  │ Generate series key: measurement + sorted_tags              │ │
│  └────────────────────────────────┬───────────────────────────┘ │
│                                    │                              │
│  Step 2: WAL WRITE                 ▼                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Append points to WAL segment                                │ │
│  │ - WAL entry: [type][length][compressed_data]               │ │
│  │ - Snappy compression                                        │ │
│  │ - fsync based on config (performance vs durability)        │ │
│  │ - New segment every 10MB                                    │ │
│  └────────────────────────────────┬───────────────────────────┘ │
│                                    │                              │
│  Step 3: CACHE INSERT              ▼                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Insert into in-memory cache                                 │ │
│  │ - Map: series_key → sorted []Values                        │ │
│  │ - Deduplication by timestamp                                │ │
│  │ - Serves reads for recent un-flushed data                  │ │
│  └────────────────────────────────┬───────────────────────────┘ │
│                                    │                              │
│  Step 4: FLUSH (when cache full)   ▼                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Snapshot cache → Write TSM file                             │ │
│  │ - Sort all series keys                                      │ │
│  │ - Compress blocks per series (1000 values max per block)   │ │
│  │ - Build index (key → block offsets)                        │ │
│  │ - Write atomically (temp file → rename)                    │ │
│  │ - Delete WAL segments that are fully flushed               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Step 5: COMPACTION (background)                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Merge multiple TSM files into fewer, larger files           │ │
│  │ - Level 1→2→3→4 progression                                │ │
│  │ - Removes tombstoned data                                   │ │
│  │ - Optimizes block boundaries                                │ │
│  │ - Rate-limited to avoid I/O spikes                         │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

Performance tuning:
  cache-max-memory-size: 1GB (default) - larger = fewer flushes
  cache-snapshot-memory-size: 25MB - trigger snapshot threshold
  wal-fsync-delay: 0s (default) - set to 100ms for throughput
  max-concurrent-compactions: 0 (auto = GOMAXPROCS/2)
  compact-throughput: 48MB/s - rate limit compaction I/O
```

### Batch Write Best Practices
```
Optimal write patterns:

1. Batch size: 5,000 - 10,000 points per request
2. Line protocol sorting: Group by series key (better compression)
3. Compression: Enable gzip on HTTP client (Content-Encoding: gzip)
4. Precision: Use seconds if nanoseconds not needed (smaller payload)
5. Retry with exponential backoff on 429/503

Write throughput benchmarks (single node, SSD):
┌────────────────────────────────────────────────────────────┐
│ Series Cardinality │ Write Throughput │ CPU (8 core) │ RAM │
├────────────────────┼──────────────────┼──────────────┼─────┤
│ 10K series         │ 1M points/sec    │ 30%          │ 4GB │
│ 100K series        │ 500K points/sec  │ 50%          │ 8GB │
│ 1M series          │ 200K points/sec  │ 70%          │ 16GB│
│ 10M series         │ 50K points/sec   │ 90%          │ 32GB│
└────────────────────┴──────────────────┴──────────────┴─────┘
```

---

## Continuous Queries & Tasks

### InfluxDB 2.x Tasks
```
Tasks replace Continuous Queries from 1.x:

// Downsample raw 10s data to 5-minute averages
option task = {
  name: "downsample_5m",
  every: 5m,
  offset: 30s  // Start 30s after window close
}

from(bucket: "raw_metrics")
  |> range(start: -task.every)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
  |> to(bucket: "metrics_5m", org: "my-org")

// Alert task (threshold check)
option task = {name: "high_cpu_alert", every: 1m}

import "influxdata/influxdb/monitor"
import "slack"

data = from(bucket: "metrics")
  |> range(start: -2m)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage_idle")
  |> mean()

data
  |> monitor.check(
    crit: (r) => r._value < 10.0,
    warn: (r) => r._value < 30.0,
  )

// Materialized aggregation for dashboards
option task = {name: "hourly_summary", every: 1h}

from(bucket: "raw_events")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "api_requests")
  |> group(columns: ["service", "status_code"])
  |> count()
  |> to(bucket: "hourly_summaries")
```

---

## Clustering & High Availability

### InfluxDB Enterprise Cluster Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                INFLUXDB ENTERPRISE CLUSTER ARCHITECTURE                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      META NODES (Raft consensus)                      │   │
│  │                                                                       │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                       │   │
│  │  │ Meta 1   │◄──►│ Meta 2   │◄──►│ Meta 3   │                       │   │
│  │  │ (Leader) │    │(Follower)│    │(Follower)│                       │   │
│  │  └──────────┘    └──────────┘    └──────────┘                       │   │
│  │                                                                       │   │
│  │  Stores: cluster metadata, user info, shard assignments,             │   │
│  │          continuous queries, retention policies                       │   │
│  │  Consensus: Raft (odd number, minimum 3)                             │   │
│  └──────────────────────────────────────┬───────────────────────────────┘   │
│                                          │ metadata                          │
│                                          ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      DATA NODES                                       │   │
│  │                                                                       │   │
│  │  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐       │   │
│  │  │ Data Node 1    │   │ Data Node 2    │   │ Data Node 3    │       │   │
│  │  │                │   │                │   │                │       │   │
│  │  │ Shards:        │   │ Shards:        │   │ Shards:        │       │   │
│  │  │ [1,3,5,7]      │   │ [1,2,4,6]      │   │ [2,3,5,7]      │       │   │
│  │  │                │   │                │   │                │       │   │
│  │  │ ┌───────────┐  │   │ ┌───────────┐  │   │ ┌───────────┐  │       │   │
│  │  │ │ TSM Engine│  │   │ │ TSM Engine│  │   │ │ TSM Engine│  │       │   │
│  │  │ │ + Cache   │  │   │ │ + Cache   │  │   │ │ + Cache   │  │       │   │
│  │  │ │ + WAL     │  │   │ │ + WAL     │  │   │ │ + WAL     │  │       │   │
│  │  │ └───────────┘  │   │ └───────────┘  │   │ └───────────┘  │       │   │
│  │  └────────────────┘   └────────────────┘   └────────────────┘       │   │
│  │                                                                       │   │
│  │  Replication: Each shard replicated to N data nodes (RF=2 default)   │   │
│  │  Writes: Hinted handoff for temporarily unavailable nodes            │   │
│  │  Reads: Query coordinator fans out to nodes with relevant shards     │   │
│  │  Anti-entropy: Background repair of inconsistent replicas            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Write path in cluster:                                                      │
│  1. Client → any Data Node (coordinator)                                    │
│  2. Coordinator determines target shard(s) by timestamp                     │
│  3. Coordinator writes to all replicas of the shard                         │
│  4. Returns success when write_consistency met (one/quorum/all/any)         │
│  5. If replica unavailable → hinted handoff queue                           │
│                                                                              │
│  Read path in cluster:                                                       │
│  1. Client → any Data Node (coordinator)                                    │
│  2. Coordinator identifies shards covering time range                       │
│  3. Fan-out queries to nodes holding those shards                           │
│  4. Merge results and return                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### InfluxDB OSS HA (without Enterprise)
```
Options for HA without Enterprise license:

1. Dual-write pattern:
   Client → writes to both InfluxDB A and InfluxDB B
   Load balancer → reads from either
   Problem: No consistency guarantee, complexity in client

2. Relay pattern (influxdb-relay, deprecated):
   Client → Relay → InfluxDB A + InfluxDB B
   Problem: No read deduplication, WAL divergence

3. InfluxDB + Kafka:
   Client → Kafka → Consumer → InfluxDB A
                   → Consumer → InfluxDB B
   Better: Kafka provides durability and replay

4. Migrate to InfluxDB Cloud (managed, HA built-in)

5. Use alternative: VictoriaMetrics (free clustering)
```

---

## Performance & Resource Optimization

### Series Cardinality Management
```
Cardinality is the #1 performance factor in InfluxDB:

Diagnosis:
  # InfluxQL
  SHOW SERIES CARDINALITY
  SHOW SERIES CARDINALITY ON "mydb"
  SHOW TAG VALUES CARDINALITY WITH KEY = "host"
  
  # API
  GET /api/v2/buckets/{id}/measurements
  
  # Internal metrics
  influxdb_series_cardinality (gauge)

Symptoms of high cardinality:
- Slow writes (index lookup for each new series)
- High memory usage (series index in RAM)
- Slow queries (large postings lists)
- Compaction backlog
- OOM kills

Solutions:
1. Reduce tag cardinality:
   - Move high-cardinality data to fields
   - Use tag values with bounded sets
   - Aggregate before writing

2. Shard group duration:
   - Shorter groups = fewer series per shard
   - But more shards = more file handles

3. max-series-per-database (1.x):
   - Default: 1,000,000
   - Hard limit prevents runaway cardinality
   - Writes rejected with 413 when exceeded

4. TSI (Time Series Index):
   - Disk-based index (vs in-memory inmem)
   - Handles higher cardinality
   - Enable: index-version = "tsi1"
   - Trade-off: Slightly slower queries but much less RAM
```

### Memory & Disk Tuning
```
Key configuration parameters:

[data]
  # Cache settings
  cache-max-memory-size = "1g"          # Max cache before rejecting writes
  cache-snapshot-memory-size = "25m"    # Trigger flush threshold
  cache-snapshot-write-cold-duration = "10m"  # Flush idle cache
  
  # Compaction
  compact-full-write-cold-duration = "4h"  # Full compaction on idle shards
  max-concurrent-compactions = 0           # 0 = auto (GOMAXPROCS/2)
  compact-throughput = "48m"               # Rate limit bytes/sec
  compact-throughput-burst = "48m"
  
  # TSI index
  max-index-log-file-size = "1m"           # WAL per TSI partition
  series-id-set-cache-size = 100           # Cache size for series lookups
  
  # WAL
  wal-fsync-delay = "0s"                   # 0 = fsync every write (safe)
                                            # "100ms" = batch fsync (faster)

[coordinator]
  write-timeout = "10s"
  max-concurrent-queries = 0               # 0 = unlimited
  query-timeout = "0s"                     # 0 = no timeout
  max-select-point = 0                     # 0 = unlimited
  max-select-series = 0                    # Limit series per query
  max-select-buckets = 0                   # Limit GROUP BY buckets

Disk sizing:
  Raw data rate: points/sec × bytes/point × seconds/day
  Compression ratio: typically 3-5x for TSM
  
  Example: 100K points/sec, 50 bytes/point average
  Raw: 100K × 50 × 86400 = 432 GB/day
  Compressed: 432 / 4 = ~108 GB/day
  30-day retention: ~3.2 TB
```

---

## Production Deployment Patterns

### Sizing Guidelines
```
┌───────────────────────────────────────────────────────────────────┐
│ Workload        │ Series   │ Writes/s │ CPU   │ RAM   │ Disk     │
├─────────────────┼──────────┼──────────┼───────┼───────┼──────────┤
│ Dev/Test        │ < 10K    │ < 10K    │ 2     │ 4 GB  │ 50 GB    │
│ Small Prod      │ 10-100K  │ 10-100K  │ 4     │ 16 GB │ 200 GB   │
│ Medium Prod     │ 100K-1M  │ 100K-500K│ 8     │ 32 GB │ 1 TB     │
│ Large Prod      │ 1-5M    │ 500K-2M  │ 16    │ 64 GB │ 4 TB     │
│ Very Large      │ 5-10M   │ > 2M     │ 32+   │ 128GB │ 10 TB+   │
│ Beyond          │ > 10M   │ > 5M     │ Enterprise cluster needed │
└─────────────────┴──────────┴──────────┴───────┴───────┴──────────┘

Critical: Use SSDs (NVMe preferred) for all production deployments
- WAL requires low-latency writes
- Compaction is I/O intensive
- TSI index requires random reads
```

### Backup & Restore
```
# Online backup (InfluxDB 2.x)
influx backup /path/to/backup/ --host http://localhost:8086 --token $TOKEN

# Restore
influx restore /path/to/backup/ --host http://localhost:8086 --token $TOKEN

# Selective backup (specific bucket)
influx backup /path/to/backup/ --bucket my-bucket

# Backup strategies for production:
1. Snapshot-based: Periodic full + incremental
2. Remote write: Stream to secondary instance
3. Object storage: InfluxDB 3.x native backup to S3
4. Volume snapshots: EBS/Persistent Disk snapshots

RPO/RTO targets:
- RPO: WAL fsync setting determines max data loss
  - fsync-delay=0: RPO ≈ 0 (every write synced)
  - fsync-delay=100ms: RPO ≈ 100ms of data
- RTO: Depends on WAL replay time + backup restore
  - Small instance: 1-5 minutes
  - Large instance (10M series): 15-30 minutes
```

---

## Telegraf & Ecosystem

### Telegraf Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TELEGRAF COLLECTION ARCHITECTURE                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         TELEGRAF AGENT                                │   │
│  │                                                                       │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │  INPUT PLUGINS (300+ available)                                 │  │   │
│  │  │                                                                 │  │   │
│  │  │  System:    cpu, mem, disk, net, processes                      │  │   │
│  │  │  Databases: mysql, postgresql, mongodb, redis                   │  │   │
│  │  │  Cloud:     cloudwatch, azure_monitor, stackdriver              │  │   │
│  │  │  Network:   snmp, ping, dns_query, net_response                │  │   │
│  │  │  Apps:      apache, nginx, haproxy, rabbitmq, kafka             │  │   │
│  │  │  Custom:    exec, http, tail, file, socket_listener             │  │   │
│  │  └──────────────────────────────┬─────────────────────────────────┘  │   │
│  │                                  │                                    │   │
│  │  ┌──────────────────────────────▼─────────────────────────────────┐  │   │
│  │  │  PROCESSOR PLUGINS                                              │  │   │
│  │  │  - rename: Rename metrics/tags                                  │  │   │
│  │  │  - converter: Change field types                                │  │   │
│  │  │  - filter: Include/exclude metrics                              │  │   │
│  │  │  - starlark: Custom transformations                             │  │   │
│  │  │  - dedup: Remove duplicate points                               │  │   │
│  │  └──────────────────────────────┬─────────────────────────────────┘  │   │
│  │                                  │                                    │   │
│  │  ┌──────────────────────────────▼─────────────────────────────────┐  │   │
│  │  │  AGGREGATOR PLUGINS                                             │  │   │
│  │  │  - basicstats: min, max, mean, count                           │  │   │
│  │  │  - histogram: Bucket observations                               │  │   │
│  │  │  - quantile: Calculate percentiles                              │  │   │
│  │  └──────────────────────────────┬─────────────────────────────────┘  │   │
│  │                                  │                                    │   │
│  │  ┌──────────────────────────────▼─────────────────────────────────┐  │   │
│  │  │  OUTPUT PLUGINS (50+ available)                                 │  │   │
│  │  │                                                                 │  │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │  │   │
│  │  │  │ InfluxDB │ │Prometheus│ │  Kafka   │ │ File/stdout  │     │  │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘     │  │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │  │   │
│  │  │  │Datadog   │ │CloudWatch│ │Elasticsearch│ │ HTTP POST  │     │  │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘     │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │  Internal buffer: metric_buffer_limit (10000 default)                │   │
│  │  Batching: metric_batch_size (1000 default)                          │   │
│  │  Collection: interval (10s default)                                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security & Multi-tenancy

### InfluxDB 2.x Security Model
```
┌────────────────────────────────────────────────────────────────┐
│ Layer              │ Mechanism                                   │
├────────────────────┼─────────────────────────────────────────────┤
│ Authentication     │ Token-based (API tokens)                    │
│ Authorization      │ Organization + Bucket-level permissions     │
│ Transport          │ TLS (HTTPS)                                 │
│ Multi-tenancy      │ Organizations (logical isolation)           │
│ Data isolation     │ Buckets per org (physical separation)       │
│ Token types        │ All-Access, Read/Write, Custom              │
└────────────────────┴─────────────────────────────────────────────┘

Token hierarchy:
  Operator Token (root) → manages orgs, users
    └── All-Access Token → full access within an org
          └── Read/Write Token → specific bucket access
                └── Custom Token → fine-grained permissions

Organization model:
  Org "TeamA" → Bucket "metrics", Bucket "logs"
  Org "TeamB" → Bucket "iot_data", Bucket "analytics"
  
  Complete isolation: Org A cannot see Org B data
  Shared instance: Cost-efficient multi-tenancy
```

---

## Use Case Architectures

### IoT Monitoring Platform
```
┌─────────────────────────────────────────────────────────────────┐
│                IoT MONITORING WITH INFLUXDB                       │
│                                                                   │
│  IoT Devices (100K+)                                             │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                              │
│  │Sens1│ │Sens2│ │Sens3│ │SensN│  → MQTT/HTTP                  │
│  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘                              │
│     └────────┴───────┴───────┘                                   │
│              │                                                    │
│              ▼                                                    │
│  ┌────────────────────┐                                         │
│  │ MQTT Broker /      │                                         │
│  │ IoT Gateway        │                                         │
│  └─────────┬──────────┘                                         │
│            │                                                     │
│            ▼                                                     │
│  ┌────────────────────┐    ┌────────────────────────────────┐  │
│  │ Telegraf           │───▶│ InfluxDB                        │  │
│  │ (MQTT consumer     │    │                                 │  │
│  │  input plugin)     │    │ Buckets:                        │  │
│  │                    │    │ - raw_telemetry (7d retention)  │  │
│  │ Processors:        │    │ - aggregated_5m (90d retention) │  │
│  │ - Unit conversion  │    │ - aggregated_1h (2yr retention) │  │
│  │ - Anomaly flag     │    │                                 │  │
│  └────────────────────┘    │ Tasks:                          │  │
│                            │ - Downsample raw → 5m averages  │  │
│                            │ - Alert on anomalies            │  │
│                            │ - Export to data lake (Parquet) │  │
│                            └────────────────────────────────┘  │
│                                        │                        │
│                            ┌───────────┼───────────┐            │
│                            │           │           │            │
│                            ▼           ▼           ▼            │
│                    ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│                    │ Grafana  │ │ Alert    │ │ Data Lake│     │
│                    │ Dashboard│ │ (PagerD.)│ │ (S3)    │     │
│                    └──────────┘ └──────────┘ └──────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: Explain TSM compaction and its impact on performance
```
Answer:
TSM compaction merges smaller TSM files into larger, optimized ones.

Levels:
- L1: Flushed from cache (many small files, unoptimized)
- L2: Merged L1 files (moderate optimization)
- L3: Merged L2 files (good optimization)
- L4: Full optimization (optimal for reads)

Impact:
- During compaction: I/O contention (reads compete with compaction I/O)
- After compaction: Better read performance (fewer files to scan)
- Write amplification: Data rewritten multiple times through levels
- Space amplification: Temporary 2x space during compaction

Tuning:
- compact-throughput: Rate-limit to prevent I/O storms
- max-concurrent-compactions: Limit CPU usage
- Schedule full compactions during low-traffic periods
- Monitor: influxdb_compactions_active, influxdb_compactions_duration
```

### Q2: How does InfluxDB handle series cardinality differently from Prometheus?
```
Answer:
Key differences:

InfluxDB:
- Series = measurement + tag set (not including field names in older versions)
- Tags are indexed (fast filter), fields are not
- TSI index can handle higher cardinality on disk
- Explicit cardinality limits (max-series-per-database)
- New series = new index entry = incremental cost
- Shard-group-based: cardinality is per-shard-group

Prometheus:
- Series = metric_name + label set
- All labels are indexed (postings lists)
- In-memory index for head block (RAM-bound)
- No explicit limits (OOM is the limit)
- Active series concept (inactive series eventually compacted out)
- Series churn affects memory more than InfluxDB

InfluxDB advantage: TSI disk-based index handles higher static cardinality
Prometheus advantage: Better for high-churn environments (series come and go)
```

### Q3: Design a multi-region InfluxDB architecture for a global IoT platform
```
Answer:
Architecture:
- Each region: InfluxDB cluster (Enterprise) or InfluxDB Cloud
- Edge: Telegraf agents with buffer for network interruption
- Aggregation: Regional Kapacitor/Tasks for local alerting
- Replication: Cross-region via Kafka or InfluxDB Enterprise replication

┌──────────┐     ┌──────────┐     ┌──────────┐
│ Region A │     │ Region B │     │ Region C │
│InfluxDB  │◄───►│InfluxDB  │◄───►│InfluxDB  │
│ Cluster  │     │ Cluster  │     │ Cluster  │
└──────────┘     └──────────┘     └──────────┘
      ↑                ↑                ↑
  Regional         Regional         Regional
  IoT devices     IoT devices     IoT devices

Global view options:
1. Query federation (query router across regions)
2. Replicate aggregates to central InfluxDB
3. Export to data lake for cross-region analytics
4. InfluxDB Cloud with built-in replication
```

### Q4: Compare InfluxDB 2.x TSM vs 3.x IOx architecture
```
Answer:
┌──────────────────────┬────────────────────────┬──────────────────────────┐
│ Aspect               │ TSM (2.x)              │ IOx (3.x)                │
├──────────────────────┼────────────────────────┼──────────────────────────┤
│ Storage format       │ Custom TSM files       │ Apache Parquet           │
│ In-memory format     │ Custom                 │ Apache Arrow             │
│ Query engine         │ Custom + Flux          │ Apache DataFusion (SQL)  │
│ Storage backend      │ Local disk only        │ Object storage (S3)      │
│ Compute/storage      │ Coupled                │ Separated                │
│ Cardinality limits   │ Yes (practical)        │ Virtually unlimited      │
│ Ecosystem interop    │ InfluxDB only          │ Parquet/Arrow ecosystem  │
│ Compression          │ Gorilla + delta        │ Parquet columnar         │
│ Query language       │ Flux + InfluxQL        │ SQL + InfluxQL           │
│ Scaling              │ Vertical (OSS)         │ Horizontal               │
└──────────────────────┴────────────────────────┴──────────────────────────┘

IOx advantages:
- Query Parquet files directly with DuckDB, Spark, etc.
- Elastic compute scaling (add query nodes)
- Cheaper storage (object store vs local SSD)
- Standard SQL (no Flux learning curve)
- Better for analytics workloads
```

### Q5-Q10: Additional Questions
```
Q5: How to handle write failures and backpressure?
- Client-side: Retry with exponential backoff (respect 429 headers)
- Telegraf: metric_buffer_limit for local buffering
- Kafka buffer: Persist to Kafka, consume at InfluxDB rate
- Cache pressure: 503 when cache full (increase cache-max-memory-size)
- Monitor: influxdb_write_errors, influxdb_cache_size

Q6: Explain retention policies and downsampling strategy
- Retention policy = auto-delete after time period
- Shard groups dropped when all data expired (efficient)
- Downsampling pipeline:
  Raw (15s) → 7 days retention
  5m averages → 90 days retention
  1h averages → 2 years retention
  1d averages → forever
- Implementation: Tasks (2.x) or Continuous Queries (1.x)

Q7: What causes write amplification in InfluxDB?
- WAL write (1st write)
- Cache flush to L1 TSM (2nd write)
- L1→L2 compaction (3rd write)
- L2→L3 compaction (4th write)
- L3→L4 compaction (5th write)
- Total amplification: ~5x in worst case
- Mitigation: Larger cache (fewer flushes), rate-limited compaction

Q8: How to migrate from InfluxDB 1.x to 2.x?
- Phase 1: Deploy 2.x alongside 1.x
- Phase 2: Use influx upgrade tool (converts data + config)
- Phase 3: Update DBRP mappings (database/rp → org/bucket)
- Phase 4: Migrate CQs to Tasks (manual rewrite in Flux)
- Phase 5: Update client code (new API + tokens)
- Gotcha: Flux is very different from InfluxQL (learning curve)

Q9: How does InfluxDB compare to TimescaleDB for time-series?
- InfluxDB: Schema-free, line protocol, purpose-built
- TimescaleDB: Full SQL, PostgreSQL ecosystem, relational features
- Choose InfluxDB: Pure metrics, IoT, high write throughput
- Choose TimescaleDB: Need JOINs, complex analytics, existing PG stack

Q10: Explain the Hinted Handoff mechanism in Enterprise
- When replica node unavailable, writes queued locally
- Hinted handoff queue: disk-backed, per-node
- When node returns, queued writes replayed
- Configuration: max-size, max-age, retry-interval
- Risk: Queue overflow → data loss (monitor queue size)
- Alternative: Anti-entropy repair (background consistency)
```

---

## Scenario-Based Questions

### Scenario 1: Write throughput drops 10x suddenly
```
Diagnosis:
1. Check cache size: influxdb_cache_size > cache-max-memory-size?
   - Yes → writes backed up, cache not flushing fast enough
   - Solution: Increase cache size, check disk I/O

2. Check compaction: influxdb_compactions_active at max?
   - Yes → compaction I/O starving writes
   - Solution: Reduce compact-throughput, add IOPS

3. Check series cardinality: SHOW SERIES CARDINALITY
   - Sudden spike? → New high-cardinality tag introduced
   - Solution: Identify and fix the source

4. Check disk: iostat shows 100% utilization?
   - Yes → I/O bottleneck
   - Solution: Move to faster SSD, separate WAL disk

5. Check TSI: index building for new series?
   - Many new series → index rebuild overhead
   - Solution: Pre-create measurements, batch new series
```

### Scenario 2: Query latency increasing over time
```
Root causes:
1. Growing data volume: More shards to scan
2. Compaction lag: Too many small TSM files
3. High cardinality: Large postings lists to intersect
4. Missing optimization: Full table scans

Solutions:
- Add time bounds to all queries (range filter)
- Create tasks for pre-aggregation (downsample)
- Increase max-concurrent-compactions
- Review query patterns: ensure tag filters used
- Check TSM file count per shard (should be < 5 after compaction)
- Consider partitioning strategy (shard group duration)
```

### Scenario 3: OOM kill during peak hours
```
Immediate: Increase container memory limits

Analysis:
1. Profile memory: influxdb_memstats_alloc_bytes
2. Cache size: influxdb_cache_inuse_bytes (biggest consumer)
3. Series index: proportional to total series
4. Query memory: concurrent expensive queries

Solutions:
- Reduce cache-max-memory-size (triggers more frequent flushes)
- Add max-concurrent-queries limit
- Add query-timeout to kill long queries
- Switch to TSI index (moves index to disk)
- Reduce max-select-series to limit query memory
- Consider sharding across multiple instances
```

### Scenario 4: Data loss after crash
```
Investigation:
1. Check WAL integrity: wal-fsync-delay setting
   - If > 0: Data written in last fsync window may be lost
   - If 0: Only in-flight write at crash time lost

2. Check data directory permissions and disk health
3. Review logs for corruption messages
4. Attempt repair: influxd inspect

Recovery:
- Replay WAL: Automatic on restart
- If WAL corrupt: influxd inspect export-lp (salvage what's possible)
- Restore from backup: influx restore
- If using replication: Anti-entropy repair from replica

Prevention:
- wal-fsync-delay: "0s" for maximum durability
- Regular backups (hourly incremental, daily full)
- Filesystem: XFS or ext4 with data=ordered
- UPS / battery-backed write cache on disk controller
```

### Scenario 5: Migrating 500 IoT gateways from CSV files to InfluxDB
```
Migration plan:

Phase 1 - Data modeling (1 week):
  - Analyze CSV schemas across gateways
  - Design measurements, tags, fields
  - Identify cardinality implications
  - Plan retention and downsampling

Phase 2 - Infrastructure (1 week):
  - Deploy InfluxDB (size based on projected cardinality + write rate)
  - Deploy Telegraf on each gateway
  - Configure MQTT/HTTP collection
  - Set up monitoring of InfluxDB itself

Phase 3 - Historical import (2 weeks):
  - Convert CSV to line protocol (script)
  - Use influx write --file for bulk import
  - Batch: 10K points per request, rate-limited
  - Validate: Compare counts and aggregates

Phase 4 - Live cutover (1 week):
  - Enable real-time Telegraf collection
  - Parallel: Write to CSV + InfluxDB for 1 week
  - Validate: Compare recent data
  - Switch dashboards/alerts to InfluxDB

Phase 5 - Optimization (ongoing):
  - Set up downsampling tasks
  - Configure retention policies
  - Add alerting (checks + notifications)
  - Decommission CSV pipeline
```
