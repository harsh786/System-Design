# VictoriaMetrics - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Storage Engine Internals](#storage-engine-internals)
3. [Cluster Architecture Deep Dive](#cluster-architecture-deep-dive)
4. [Data Ingestion](#data-ingestion)
5. [MetricsQL Query Language](#metricsql-query-language)
6. [Retention, Downsampling & Storage](#retention-downsampling--storage)
7. [High Availability & Disaster Recovery](#high-availability--disaster-recovery)
8. [Performance & Resource Optimization](#performance--resource-optimization)
9. [Monitoring VictoriaMetrics Itself](#monitoring-victoriametrics-itself)
10. [Production Deployment Patterns](#production-deployment-patterns)
11. [Ecosystem & Integrations](#ecosystem--integrations)
12. [Multi-Tenancy](#multi-tenancy)
13. [Use Case Architectures](#use-case-architectures)
14. [Staff Architect Interview Questions](#staff-architect-interview-questions)
15. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is VictoriaMetrics?
```
VictoriaMetrics is a high-performance, cost-effective time-series database
and monitoring solution. It serves as a long-term storage for Prometheus
and as a standalone monitoring solution.

Key characteristics:
- 10x less RAM than Prometheus for same data
- 7x better compression than Prometheus TSDB
- PromQL-compatible (MetricsQL superset)
- Supports multiple ingestion protocols
- Horizontal and vertical scaling
- No external dependencies (no ZooKeeper, etcd, Kafka)
- Written in Go (single binary deployment)

Two deployment modes:
1. Single-node: All-in-one binary (simpler, up to 30M active series)
2. Cluster: vminsert + vmselect + vmstorage (horizontal scale)

Comparison:
┌────────────────┬───────────┬──────────────┬──────────────┐
│                │ Prometheus│ Thanos       │ VictoriaM.   │
├────────────────┼───────────┼──────────────┼──────────────┤
│ RAM per 1M    │ 3-5 GB    │ 4-6 GB       │ 0.5-1 GB     │
│ series         │           │              │              │
│ Compression    │ 1.3 B/s   │ 1.3 B/s      │ 0.4 B/s      │
│ bytes/sample   │           │              │              │
│ Query speed    │ Baseline  │ 2-5x slower  │ 2-10x faster │
│ HA complexity  │ Moderate  │ High (6+     │ Low (built-  │
│                │           │  components) │  in repl.)   │
│ Multi-tenancy  │ No        │ Limited      │ Yes (native) │
│ Long-term      │ No (local)│ Yes (S3)     │ Yes (local)  │
│ storage        │           │              │              │
└────────────────┴───────────┴──────────────┴──────────────┘
```

### Single-Node Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│              VICTORIAMETRICS SINGLE-NODE                          │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  INGESTION LAYER                            │  │
│  │                                                            │  │
│  │  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ Prometheus │ │ InfluxDB │ │ Graphite │ │OpenTSDB  │  │  │
│  │  │ remote_wr  │ │ line prot│ │plaintext │ │  put     │  │  │
│  │  └─────┬──────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │  │
│  │        └──────────────┴────────────┴─────────────┘        │  │
│  │                       │                                    │  │
│  │                       ▼                                    │  │
│  │  ┌────────────────────────────────────────────────────┐   │  │
│  │  │         Relabeling & Deduplication                   │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────┬───────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────┼───────────────────────────────┐  │
│  │                  STORAGE ENGINE                             │  │
│  │                           │                                │  │
│  │  ┌───────────────────────────────────────────────────┐    │  │
│  │  │              INDEX DB (inverted index)              │    │  │
│  │  │  metric_name{label=value} → TSID (time-series ID) │    │  │
│  │  │  label=value → list of TSIDs                       │    │  │
│  │  │  (mergeset-based, similar to LSM)                  │    │  │
│  │  └───────────────────────────────────────────────────┘    │  │
│  │                                                            │  │
│  │  ┌───────────────────────────────────────────────────┐    │  │
│  │  │              DATA DB (time-series data)             │    │  │
│  │  │  TSID + timestamp → value                          │    │  │
│  │  │  Organized by: partition/TSID/block                │    │  │
│  │  │  Compression: Gorilla + delta-of-delta             │    │  │
│  │  │  Partitioned by month (or day)                     │    │  │
│  │  └───────────────────────────────────────────────────┘    │  │
│  │                                                            │  │
│  │  ┌───────────────────────────────────────────────────┐    │  │
│  │  │              CACHE LAYER                            │    │  │
│  │  │  - MetricName → TSID cache                        │    │  │
│  │  │  - TSID → MetricName cache (reverse)              │    │  │
│  │  │  - Date+MetricID → exists cache                   │    │  │
│  │  │  - Index block cache                              │    │  │
│  │  │  - Data block cache                               │    │  │
│  │  └───────────────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  QUERY LAYER                               │  │
│  │  MetricsQL engine → scan data → aggregate → return        │  │
│  │  /api/v1/query, /api/v1/query_range, /api/v1/export      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Single binary: victoria-metrics                                 │
│  Flags: -storageDataPath, -retentionPeriod, -httpListenAddr     │
└─────────────────────────────────────────────────────────────────┘
```

### Cluster Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│              VICTORIAMETRICS CLUSTER MODE                         │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  VMINSERT (stateless, horizontally scalable)               │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │  │
│  │  │vminsert-1│ │vminsert-2│ │vminsert-3│                  │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘                  │  │
│  │       │             │             │                        │  │
│  │  Responsibilities:                                        │  │
│  │  - Accept data from all protocols                         │  │
│  │  - Compute consistent hash of metric labels              │  │
│  │  - Route to appropriate vmstorage node                   │  │
│  │  - Buffer during vmstorage unavailability                │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                          │ consistent hashing                     │
│                          ▼                                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  VMSTORAGE (stateful, stores data)                         │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │  │
│  │  │ vmstorage-1  │ │ vmstorage-2  │ │ vmstorage-3  │      │  │
│  │  │              │ │              │ │              │      │  │
│  │  │ indexdb/     │ │ indexdb/     │ │ indexdb/     │      │  │
│  │  │ datadb/      │ │ datadb/      │ │ datadb/      │      │  │
│  │  │ cache/       │ │ cache/       │ │ cache/       │      │  │
│  │  │              │ │              │ │              │      │  │
│  │  │ 1/3 of data │ │ 1/3 of data │ │ 1/3 of data │      │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘      │  │
│  │                                                            │  │
│  │  With -replicationFactor=2:                               │  │
│  │  Each series stored on 2 different vmstorage nodes        │  │
│  │  (lose 1 node → no data loss)                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          ▲                                        │
│                          │ parallel scatter-gather                │
│  ┌───────────────────────┴───────────────────────────────────┐  │
│  │  VMSELECT (stateless, horizontally scalable)               │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │  │
│  │  │vmselect-1│ │vmselect-2│ │vmselect-3│                  │  │
│  │  └──────────┘ └──────────┘ └──────────┘                  │  │
│  │                                                            │  │
│  │  Responsibilities:                                        │  │
│  │  - Accept MetricsQL/PromQL queries                       │  │
│  │  - Fan out to ALL vmstorage nodes                        │  │
│  │  - Merge and deduplicate results                         │  │
│  │  - Apply final aggregations                              │  │
│  │  - Return results to client                              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Key properties:                                                 │
│  - vminsert + vmselect = STATELESS (easy to scale/replace)      │
│  - vmstorage = STATEFUL (needs persistent disks)                │
│  - No coordination between vmstorage nodes (no gossip/raft)    │
│  - No external dependencies (no ZK, no etcd, no Kafka)         │
│  - Scale each tier independently                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Storage Engine Internals

### Data Organization
```
┌─────────────────────────────────────────────────────────────────┐
│                  STORAGE ENGINE DESIGN                            │
│                                                                   │
│  On-disk layout:                                                 │
│  /storage-data/                                                  │
│  ├── data/                                                       │
│  │   ├── big/                    (large time-series blocks)     │
│  │   │   ├── 2024_01/           (monthly partition)             │
│  │   │   │   ├── part_0/        (merged part)                   │
│  │   │   │   │   ├── timestamps.bin  (delta-of-delta encoded)  │
│  │   │   │   │   ├── values.bin      (Gorilla XOR encoded)     │
│  │   │   │   │   ├── index.bin       (TSID → offset mapping)   │
│  │   │   │   │   └── metaindex.bin   (block index)             │
│  │   │   │   └── part_1/                                        │
│  │   │   └── 2024_02/                                           │
│  │   └── small/                  (recently ingested, not merged)│
│  │       └── ...                                                 │
│  ├── indexdb/                                                    │
│  │   ├── current/               (current inverted index)        │
│  │   │   ├── parts/            (mergeset parts)                 │
│  │   │   └── ...                                                │
│  │   └── previous/             (previous day index, for search) │
│  └── cache/                                                      │
│      ├── metricName_tsid/      (name → ID mapping cache)        │
│      └── tsid_metricName/      (ID → name reverse cache)        │
│                                                                   │
│  Key Design Decisions:                                           │
│  1. NOT LSM-tree, NOT B-tree                                    │
│     - Custom "mergeset" for index (similar to LSM but optimized)│
│     - Custom columnar format for data                           │
│  2. Partition by time (monthly by default)                      │
│     - Fast deletion of old data (drop partition)               │
│     - Good locality for time-range queries                     │
│  3. Columnar storage for timestamps and values                  │
│     - Timestamps: delta-of-delta encoding                      │
│     - Values: Gorilla XOR encoding (from Facebook paper)       │
│  4. Per-TSID blocks within partitions                          │
│     - Each time-series has its own data blocks                 │
│     - Fast access to specific series                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Compression Deep Dive
```
┌─────────────────────────────────────────────────────────────────┐
│                  COMPRESSION TECHNIQUES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  TIMESTAMPS (delta-of-delta encoding):                           │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Raw:    [1000, 1015, 1030, 1045, 1060, 1075]      │       │
│  │  Delta:  [1000, 15, 15, 15, 15, 15]                │       │
│  │  D-of-D: [1000, 15, 0, 0, 0, 0]                   │       │
│  │                                                      │       │
│  │  Regular scrape intervals → mostly zeros            │       │
│  │  Encode zeros with run-length encoding              │       │
│  │  Result: ~1-2 bits per timestamp (vs 64 bits raw)  │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                   │
│  VALUES (Gorilla XOR encoding):                                  │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Based on Facebook Gorilla paper (2015)             │       │
│  │                                                      │       │
│  │  Observation: consecutive metric values are similar  │       │
│  │  XOR of consecutive floats has many leading zeros   │       │
│  │                                                      │       │
│  │  Example (CPU usage hovering around 45%):           │       │
│  │  v1 = 45.2 → stored as-is (64 bits)               │       │
│  │  v2 = 45.3 → XOR(v1, v2) = small number            │       │
│  │            → encode with variable-length prefix     │       │
│  │  v3 = 45.3 → XOR = 0 → encode as "same" (1 bit)  │       │
│  │                                                      │       │
│  │  Average: 1-3 bits per value for smooth metrics    │       │
│  │  Worst case: 68 bits (large value change)          │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                   │
│  OVERALL COMPRESSION RATIO:                                      │
│  ┌───────────────────────────────────────┐                      │
│  │  Raw sample size: 16 bytes            │                      │
│  │    (8B timestamp + 8B float64)        │                      │
│  │                                        │                      │
│  │  VictoriaMetrics: ~0.4 bytes/sample   │                      │
│  │  Prometheus TSDB: ~1.3 bytes/sample   │                      │
│  │  InfluxDB:        ~2-3 bytes/sample   │                      │
│  │                                        │                      │
│  │  Compression ratio: 40x (VM) vs 12x (Prom)                  │
│  │  Result: Same data, 3x less disk in VM                       │
│  └───────────────────────────────────────┘                      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Inverted Index (indexdb)
```
┌─────────────────────────────────────────────────────────────────┐
│                  INVERTED INDEX STRUCTURE                         │
│                                                                   │
│  Purpose: Map metric name + labels → TSID (time-series ID)     │
│                                                                   │
│  Example metric:                                                 │
│  http_requests_total{method="GET", handler="/api", status="200"}│
│                                                                   │
│  Index entries created:                                          │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  __name__=http_requests_total  → [TSID_1, TSID_5...] │      │
│  │  method=GET                     → [TSID_1, TSID_3...] │      │
│  │  handler=/api                   → [TSID_1, TSID_7...] │      │
│  │  status=200                     → [TSID_1, TSID_9...] │      │
│  │                                                        │      │
│  │  Composite:                                            │      │
│  │  __name__=http_requests_total+method=GET+handler=/api │      │
│  │  +status=200  → TSID_1                                │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  Query: http_requests_total{method="GET"}                       │
│  1. Lookup __name__=http_requests_total → set A                 │
│  2. Lookup method=GET → set B                                    │
│  3. Intersect A ∩ B → result TSIDs                              │
│  4. Fetch data for those TSIDs                                   │
│                                                                   │
│  Implementation: "mergeset" (custom LSM-like structure)         │
│  - Sorted string table with bloom filters                       │
│  - Background merging of parts                                   │
│  - Optimized for time-series label patterns                     │
│  - Date-based partitioning (per-day index entries)             │
│                                                                   │
│  Why NOT a regular database for index?                          │
│  - Need ultra-fast prefix scans for label matching             │
│  - Need efficient set intersections                            │
│  - Need to handle high-cardinality label values                │
│  - Regular B-tree would be too slow for regex matching         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Cluster Architecture Deep Dive

### Write Path (Cluster)
```
┌─────────────────────────────────────────────────────────────────┐
│                     CLUSTER WRITE PATH                            │
│                                                                   │
│  Prometheus/vmagent sends remote_write:                          │
│  POST /api/v1/write                                              │
│  Body: [metric1{labels}, metric2{labels}, ...]                  │
│                                                                   │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────┐                   │
│  │           vminsert                         │                   │
│  │                                            │                   │
│  │  1. Parse incoming data                   │                   │
│  │  2. Apply relabeling rules (if any)       │                   │
│  │  3. For each time-series:                 │                   │
│  │     hash = jump_hash(labels) % N_storage  │                   │
│  │  4. Route to vmstorage[hash]              │                   │
│  │                                            │                   │
│  │  With -replicationFactor=2:               │                   │
│  │     Send to vmstorage[hash]               │                   │
│  │     AND vmstorage[(hash+1) % N]           │                   │
│  │                                            │                   │
│  │  Buffering:                               │                   │
│  │  - If vmstorage is unavailable, buffer    │                   │
│  │    in memory (configurable limit)         │                   │
│  │  - Retry with exponential backoff          │                   │
│  └──────────────────┬───────────────────────┘                   │
│                     │                                             │
│         ┌───────────┼───────────┐                                │
│         ▼           ▼           ▼                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                  │
│  │vmstorage-0 │ │vmstorage-1 │ │vmstorage-2 │                  │
│  │            │ │            │ │            │                  │
│  │ 1. Assign  │ │            │ │            │                  │
│  │    TSID    │ │            │ │            │                  │
│  │ 2. Write   │ │            │ │            │                  │
│  │    to small│ │            │ │            │                  │
│  │    parts   │ │            │ │            │                  │
│  │ 3. Update  │ │            │ │            │                  │
│  │    indexdb │ │            │ │            │                  │
│  │ 4. Merge   │ │            │ │            │                  │
│  │    in bg   │ │            │ │            │                  │
│  └────────────┘ └────────────┘ └────────────┘                  │
│                                                                   │
│  Ingestion rates (cluster):                                      │
│  - Per vminsert: 1-2M samples/sec                               │
│  - Per vmstorage: 500K-1M samples/sec                           │
│  - 3 vminsert + 3 vmstorage: ~3M samples/sec                   │
│  - Scale linearly by adding nodes                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Read Path (Cluster)
```
┌─────────────────────────────────────────────────────────────────┐
│                     CLUSTER READ PATH                             │
│                                                                   │
│  Client sends query:                                             │
│  GET /api/v1/query_range?query=rate(http_total[5m])&start=...   │
│                                                                   │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────┐                   │
│  │           vmselect                         │                   │
│  │                                            │                   │
│  │  1. Parse MetricsQL query                 │                   │
│  │  2. Determine time range and series       │                   │
│  │  3. Fan out to ALL vmstorage nodes        │                   │
│  │     (cannot know which node has which     │                   │
│  │      series without querying all)         │                   │
│  │  4. Wait for all responses                │                   │
│  │  5. Merge results                         │                   │
│  │  6. Deduplicate (if replicationFactor>1)  │                   │
│  │  7. Apply final aggregations              │                   │
│  │  8. Return to client                      │                   │
│  └──────────────────┬───────────────────────┘                   │
│                     │                                             │
│         ┌───────────┼───────────┐                                │
│         ▼           ▼           ▼                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                  │
│  │vmstorage-0 │ │vmstorage-1 │ │vmstorage-2 │                  │
│  │            │ │            │ │            │                  │
│  │ 1. Find    │ │ 1. Find    │ │ 1. Find    │                  │
│  │    matching│ │    matching│ │    matching│                  │
│  │    TSIDs   │ │    TSIDs   │ │    TSIDs   │                  │
│  │    (index) │ │    (index) │ │    (index) │                  │
│  │ 2. Fetch   │ │ 2. Fetch   │ │ 2. Fetch   │                  │
│  │    data    │ │    data    │ │    data    │                  │
│  │    blocks  │ │    blocks  │ │    blocks  │                  │
│  │ 3. Return  │ │ 3. Return  │ │ 3. Return  │                  │
│  │    partial │ │    partial │ │    partial │                  │
│  │    results │ │    results │ │    results │                  │
│  └────────────┘ └────────────┘ └────────────┘                  │
│                                                                   │
│  Query performance:                                              │
│  - Simple query (1 series, 1h): < 10ms                         │
│  - Dashboard query (100 series, 24h): 50-200ms                 │
│  - Heavy aggregation (10K series, 7d): 1-5 sec                 │
│  - Scales with more vmselect nodes (query parallelism)         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Ingestion

### Supported Protocols
```
┌─────────────────────────────────────────────────────────────────┐
│                  INGESTION PROTOCOLS                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Protocol            │ Endpoint                  │ Use Case      │
│  ────────────────────┼───────────────────────────┼───────────────│
│  Prometheus          │ /api/v1/write             │ Standard      │
│  remote_write        │ (snappy compressed proto) │ monitoring    │
│                      │                           │               │
│  InfluxDB line       │ /write                    │ InfluxDB      │
│  protocol            │ host,dc=us cpu=42.5 ts    │ migration     │
│                      │                           │               │
│  Graphite            │ :2003 (plaintext)         │ Legacy        │
│  plaintext           │ metric.path value ts      │ systems       │
│                      │                           │               │
│  OpenTSDB            │ /api/put (JSON)           │ OpenTSDB      │
│  HTTP/telnet         │ :4242 (telnet)            │ migration     │
│                      │                           │               │
│  DataDog             │ /datadog/api/v2/series    │ DataDog       │
│  agent protocol      │                           │ migration     │
│                      │                           │               │
│  OpenTelemetry       │ /opentelemetry/v1/metrics │ OTLP          │
│  (OTLP)             │                           │ ecosystem     │
│                      │                           │               │
│  CSV import          │ /api/v1/import/csv        │ Bulk load     │
│                      │                           │               │
│  JSON lines          │ /api/v1/import            │ Custom apps   │
│                      │                           │               │
│  Native binary       │ /api/v1/import/native     │ vmctl         │
│  (VM format)         │                           │ migration     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### vmagent (Collection Agent)
```
┌─────────────────────────────────────────────────────────────────┐
│                      VMAGENT ARCHITECTURE                         │
│                                                                   │
│  vmagent = lightweight Prometheus-compatible scraper + forwarder │
│  Uses 10x less RAM than Prometheus for scraping                  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                       vmagent                              │   │
│  │                                                           │   │
│  │  ┌─────────────────────────────────────────────────┐     │   │
│  │  │         Service Discovery                        │     │   │
│  │  │  - Kubernetes (pods, services, endpoints)       │     │   │
│  │  │  - Consul, EC2, DNS, file-based                 │     │   │
│  │  │  - Same as Prometheus SD                        │     │   │
│  │  └────────────────────────┬────────────────────────┘     │   │
│  │                           │                               │   │
│  │  ┌────────────────────────▼────────────────────────┐     │   │
│  │  │         Scrape Engine                            │     │   │
│  │  │  - Scrapes /metrics endpoints                   │     │   │
│  │  │  - Same scrape_configs as Prometheus            │     │   │
│  │  │  - Supports relabeling                          │     │   │
│  │  │  - stream_parse mode (for large targets)       │     │   │
│  │  └────────────────────────┬────────────────────────┘     │   │
│  │                           │                               │   │
│  │  ┌────────────────────────▼────────────────────────┐     │   │
│  │  │         Persistent Queue (WAL)                   │     │   │
│  │  │  - Buffers data on disk during remote outages  │     │   │
│  │  │  - No data loss if VM is temporarily down      │     │   │
│  │  │  - Configurable max disk usage                 │     │   │
│  │  └────────────────────────┬────────────────────────┘     │   │
│  │                           │                               │   │
│  │  ┌────────────────────────▼────────────────────────┐     │   │
│  │  │         Remote Write (fan-out)                   │     │   │
│  │  │  - Send to multiple remote targets             │     │   │
│  │  │  - Sharding by labels (for multi-tenant)       │     │   │
│  │  │  - Configurable batch size and concurrency     │     │   │
│  │  └─────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  RAM comparison:                                                 │
│  - Prometheus scraping 1000 targets: 2-4 GB RAM                 │
│  - vmagent scraping 1000 targets: 200-400 MB RAM                │
│                                                                   │
│  Key flags:                                                      │
│  -promscrape.config=/etc/vmagent/scrape.yml                     │
│  -remoteWrite.url=http://vminsert:8480/insert/0/prometheus/     │
│  -remoteWrite.tmpDataPath=/tmp/vmagent-queue                    │
│  -remoteWrite.maxDiskUsagePerURL=1GB                            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## MetricsQL Query Language

### MetricsQL Extensions over PromQL
```
┌─────────────────────────────────────────────────────────────────┐
│                  METRICSQL vs PROMQL                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  100% PromQL compatible (all valid PromQL works in MetricsQL)   │
│  + Additional powerful features:                                 │
│                                                                   │
│  1. WITH TEMPLATES (subqueries / CTEs):                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  WITH (                                                  │   │
│  │    commonFilters = {job="api", env="prod"},             │   │
│  │    errorRate = rate(http_errors_total{commonFilters}[5m])│   │
│  │  )                                                       │   │
│  │  errorRate / rate(http_total{commonFilters}[5m])        │   │
│  │                                                          │   │
│  │  -- Reusable expressions, cleaner complex queries        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  2. KEEP_METRIC_NAMES:                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  rate(http_requests_total[5m]) keep_metric_names         │   │
│  │  -- Result keeps "http_requests_total" name             │   │
│  │  -- PromQL would lose the metric name                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  3. RANGE FUNCTIONS (over entire range):                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  range_avg(cpu_usage[24h])        -- avg over 24h       │   │
│  │  range_quantile(0.99, latency[1h]) -- p99 over 1h      │   │
│  │  range_median(memory_usage[7d])    -- median over 7d    │   │
│  │  range_first(metric[1h])           -- first value       │   │
│  │  range_last(metric[1h])            -- last value        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  4. LABEL MANIPULATION:                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  label_set(metric, "env", "prod")   -- add/set label    │   │
│  │  label_del(metric, "instance")      -- remove label     │   │
│  │  label_keep(metric, "job", "env")   -- keep only these  │   │
│  │  label_copy(metric, "src", "dst")   -- copy label       │   │
│  │  label_move(metric, "old", "new")   -- rename label     │   │
│  │  label_graphite_group(metric, 0, 2) -- for graphite     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  5. ROLLUP FUNCTIONS:                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  rollup(metric[5m])         -- returns min, max, avg    │   │
│  │  rollup_rate(metric[5m])    -- rate with proper handling│   │
│  │  rollup_deriv(metric[5m])   -- derivative               │   │
│  │  rollup_increase(metric[5m])-- increase with resets     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  6. DEFAULT VALUE:                                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  rate(errors[5m]) default 0    -- returns 0 if no data  │   │
│  │  -- PromQL returns nothing (gap in graph)               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  7. LIMIT and OFFSET:                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  topk(10, http_requests_total) limit 5 offset 5        │   │
│  │  -- Pagination for large result sets                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Retention, Downsampling & Storage

### Storage Management
```
┌─────────────────────────────────────────────────────────────────┐
│                  STORAGE MANAGEMENT                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Retention:                                                      │
│  -retentionPeriod=12 (months, default: 1 month)                 │
│  - Data older than retention is automatically deleted            │
│  - Deletion happens at partition granularity (monthly)           │
│  - No performance impact (just drops directory)                  │
│                                                                   │
│  Storage Space Calculation:                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                          │   │
│  │  disk_space = active_series                              │   │
│  │             × scrape_interval_seconds                    │   │
│  │             × retention_seconds                          │   │
│  │             × bytes_per_sample (0.4-1.5 depending on    │   │
│  │                                  data regularity)        │   │
│  │                                                          │   │
│  │  Example:                                                │   │
│  │  5M active series × every 15s × 90 days                 │   │
│  │  = 5M × (90 × 86400 / 15) × 0.5 bytes                 │   │
│  │  = 5M × 518,400 × 0.5                                  │   │
│  │  = 1.3 TB                                               │   │
│  │                                                          │   │
│  │  Prometheus for same data: ~4 TB (1.3 bytes/sample)    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Deduplication:                                                  │
│  -dedup.minScrapeInterval=15s                                   │
│  - When HA Prometheus pairs scrape same targets                 │
│  - Keeps only one sample per dedup interval                     │
│  - Reduces storage by ~50% for HA setups                        │
│                                                                   │
│  Downsampling (via recording rules):                            │
│  - VictoriaMetrics doesn't have built-in downsampling          │
│  - Use vmalert recording rules to create rollups:              │
│                                                                   │
│  # vmalert recording rule:                                      │
│  groups:                                                         │
│    - name: downsample                                           │
│      interval: 5m                                                │
│      rules:                                                      │
│        - record: cpu_usage:5m_avg                               │
│          expr: avg_over_time(cpu_usage[5m])                     │
│        - record: http_requests:5m_rate                          │
│          expr: rate(http_requests_total[5m])                    │
│                                                                   │
│  Multi-retention setup:                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  VM instance 1: raw data, retention=30d                  │   │
│  │  VM instance 2: 5-min rollups, retention=1y             │   │
│  │  VM instance 3: 1-hour rollups, retention=5y            │   │
│  │                                                          │   │
│  │  Grafana: query appropriate instance based on range     │   │
│  │  - Last 30d → instance 1                               │   │
│  │  - 30d-1y → instance 2                                 │   │
│  │  - 1y-5y → instance 3                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## High Availability & Disaster Recovery

### HA Patterns
```
┌─────────────────────────────────────────────────────────────────┐
│            HIGH AVAILABILITY ARCHITECTURES                        │
│                                                                   │
│  PATTERN 1: Single-Node HA (vmbackup + vmrestore)               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Primary VM ──── vmbackup (hourly) ───→ S3 Bucket      │   │
│  │       │                                      │          │   │
│  │       │ (failure)                            │          │   │
│  │       ▼                                      ▼          │   │
│  │  New VM ◄──── vmrestore ──── restore from S3            │   │
│  │                                                          │   │
│  │  RPO: 1 hour (time between backups)                     │   │
│  │  RTO: 10-30 minutes (restore time)                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  PATTERN 2: Cluster with Replication                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                          │   │
│  │  vminsert (-replicationFactor=2)                        │   │
│  │       │          │          │                            │   │
│  │       ▼          ▼          ▼                            │   │
│  │  vmstorage-1  vmstorage-2  vmstorage-3                  │   │
│  │  [data A,B]   [data B,C]   [data C,A]  ← replicated   │   │
│  │                                                          │   │
│  │  If vmstorage-2 dies:                                   │   │
│  │  - data B available from vmstorage-1                    │   │
│  │  - data C available from vmstorage-3                    │   │
│  │  - vmselect deduplicates results                        │   │
│  │  - No data loss, no downtime!                           │   │
│  │                                                          │   │
│  │  vmselect flags:                                        │   │
│  │  -dedup.minScrapeInterval=15s (deduplicate replicas)   │   │
│  │  -replicationFactor=2 (expect 2 copies)                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  PATTERN 3: Multi-DC Active-Active                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                          │   │
│  │  DC-1 (US-East)              DC-2 (US-West)            │   │
│  │  ┌──────────────────┐       ┌──────────────────┐      │   │
│  │  │ vmagent          │       │ vmagent          │      │   │
│  │  │   ↓ remote_write │       │   ↓ remote_write │      │   │
│  │  │ vmcluster-1      │       │ vmcluster-2      │      │   │
│  │  └────────┬─────────┘       └────────┬─────────┘      │   │
│  │           │                           │                 │   │
│  │           │    cross-DC replication    │                 │   │
│  │           │  (vmagent remote_write     │                 │   │
│  │           │   to both clusters)        │                 │   │
│  │           └───────────┬───────────────┘                 │   │
│  │                       │                                  │   │
│  │                       ▼                                  │   │
│  │              vmselect (federated)                        │   │
│  │              queries both clusters                       │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Backup Strategy:                                                │
│  - vmbackup → S3/GCS/Azure Blob (incremental)                  │
│  - Hourly incremental backups (only new data parts)             │
│  - Daily full backup verification                               │
│  - Retention: keep 7 daily + 4 weekly + 12 monthly             │
│                                                                   │
│  vmbackup command:                                               │
│  vmbackup -storageDataPath=/data -snapshot.createURL=...        │
│           -dst=s3://bucket/path/$(date +%Y%m%d)                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Performance & Resource Optimization

### Capacity Planning
```
┌─────────────────────────────────────────────────────────────────┐
│                  CAPACITY PLANNING FORMULAS                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  RAM Sizing:                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RAM = active_time_series × 1KB  (for indexdb cache)    │   │
│  │      + ingestion_rate × 2KB      (for write buffers)    │   │
│  │      + query_concurrency × 256MB (for query processing)  │   │
│  │                                                          │   │
│  │  Examples:                                               │   │
│  │  1M series, 100K samples/sec, 10 concurrent queries:   │   │
│  │  = 1M × 1KB + 100K × 2KB + 10 × 256MB                 │   │
│  │  = 1GB + 0.2GB + 2.5GB = ~4 GB                         │   │
│  │                                                          │   │
│  │  10M series, 1M samples/sec, 50 concurrent queries:    │   │
│  │  = 10GB + 2GB + 12.5GB = ~25 GB                        │   │
│  │                                                          │   │
│  │  (Prometheus would need 30-50GB for 10M series)        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  CPU Sizing:                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Ingestion: 1 core per 300K samples/sec                 │   │
│  │  Queries:   1 core per 10 concurrent queries            │   │
│  │  Merging:   1-2 cores for background operations         │   │
│  │                                                          │   │
│  │  Example: 1M samples/sec + moderate queries            │   │
│  │  = 4 (ingest) + 4 (query) + 2 (merge) = 10 cores     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Disk Sizing:                                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  disk = active_series × samples_per_day × bytes_per_sample│  │
│  │       × retention_days × 1.2 (overhead)                  │   │
│  │                                                          │   │
│  │  bytes_per_sample ≈ 0.4-1.5 (avg 0.5 for regular data) │   │
│  │  samples_per_day = 86400 / scrape_interval              │   │
│  │                                                          │   │
│  │  Example: 5M series, 15s interval, 90d retention       │   │
│  │  = 5M × 5760 × 0.5 × 90 × 1.2 = 1.55 TB             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Disk IOPS:                                                      │
│  - Ingestion: mostly sequential writes (100-500 IOPS)           │
│  - Queries: random reads (1000-5000 IOPS for heavy queries)    │
│  - NVMe recommended for > 5M active series                     │
│  - SATA SSD sufficient for < 1M series                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Performance Tuning
```
┌─────────────────────────────────────────────────────────────────┐
│                  KEY TUNING FLAGS                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Memory tuning:                                                  │
│  -memory.allowedPercent=80     # Use up to 80% of system RAM    │
│  -search.maxMemoryPerQuery=2GB # Limit per-query memory         │
│  -search.maxUniqueTimeseries=300000 # Limit series per query   │
│                                                                   │
│  Ingestion tuning:                                               │
│  -maxInsertRequestSize=64MB   # Max request body size           │
│  -maxLabelsPerTimeseries=40   # Prevent cardinality explosion   │
│  -storage.minFreeDiskSpaceBytes=10GB # Stop before disk full    │
│                                                                   │
│  Query tuning:                                                   │
│  -search.maxConcurrentRequests=32  # Parallel queries           │
│  -search.maxQueryDuration=120s     # Query timeout              │
│  -search.maxPointsPerTimeseries=30000 # Max points returned     │
│  -search.cacheTimestampOffset=5m   # Query cache duration       │
│                                                                   │
│  Merge/compaction tuning:                                        │
│  -bigMergeConcurrency=2            # Background merge threads   │
│  -smallMergeConcurrency=4          # For recent data merges     │
│  -retentionTimezoneOffset=0h       # When to do daily cleanup   │
│                                                                   │
│  Network tuning:                                                 │
│  -httpListenAddr=:8428             # Listen address             │
│  -http.maxGracefulShutdownDuration=30s                          │
│  -insert.maxQueueDuration=1m       # Buffer during overload     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Production Deployment Patterns

### Kubernetes Deployment
```
┌─────────────────────────────────────────────────────────────────┐
│              KUBERNETES CLUSTER DEPLOYMENT                        │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Namespace: monitoring                                │      │
│  │                                                       │      │
│  │  ┌─────────────────────────────────────────────────┐ │      │
│  │  │  Deployment: vminsert (replicas: 3)             │ │      │
│  │  │  Resources: 2 CPU, 4GB RAM each                 │ │      │
│  │  │  Service: vminsert-svc (ClusterIP)              │ │      │
│  │  │  HPA: scale on CPU > 70%                        │ │      │
│  │  └─────────────────────────────────────────────────┘ │      │
│  │                                                       │      │
│  │  ┌─────────────────────────────────────────────────┐ │      │
│  │  │  StatefulSet: vmstorage (replicas: 3)           │ │      │
│  │  │  Resources: 8 CPU, 32GB RAM each                │ │      │
│  │  │  PVC: 2TB NVMe per pod                          │ │      │
│  │  │  Service: vmstorage-svc (headless)              │ │      │
│  │  │  Anti-affinity: spread across AZs               │ │      │
│  │  └─────────────────────────────────────────────────┘ │      │
│  │                                                       │      │
│  │  ┌─────────────────────────────────────────────────┐ │      │
│  │  │  Deployment: vmselect (replicas: 3)             │ │      │
│  │  │  Resources: 4 CPU, 8GB RAM each                 │ │      │
│  │  │  Service: vmselect-svc (ClusterIP)              │ │      │
│  │  │  HPA: scale on memory > 60%                     │ │      │
│  │  └─────────────────────────────────────────────────┘ │      │
│  │                                                       │      │
│  │  ┌─────────────────────────────────────────────────┐ │      │
│  │  │  DaemonSet: vmagent                             │ │      │
│  │  │  Resources: 0.5 CPU, 512MB RAM each             │ │      │
│  │  │  Scrapes all pods via service discovery         │ │      │
│  │  │  Sends to vminsert-svc                          │ │      │
│  │  └─────────────────────────────────────────────────┘ │      │
│  │                                                       │      │
│  │  ┌─────────────────────────────────────────────────┐ │      │
│  │  │  Deployment: vmalert (replicas: 2)              │ │      │
│  │  │  Alerting + recording rules                     │ │      │
│  │  │  Queries vmselect, sends to Alertmanager        │ │      │
│  │  └─────────────────────────────────────────────────┘ │      │
│  │                                                       │      │
│  │  ┌─────────────────────────────────────────────────┐ │      │
│  │  │  Deployment: vmauth (replicas: 2)               │ │      │
│  │  │  Authentication proxy + routing                 │ │      │
│  │  │  Ingress → vmauth → vminsert/vmselect          │ │      │
│  │  └─────────────────────────────────────────────────┘ │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  Helm chart: victoria-metrics-k8s-stack                          │
│  Operator: victoria-metrics-operator                             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Multi-Tenancy

### Tenant Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                  MULTI-TENANT DESIGN                              │
│                                                                   │
│  Cluster mode supports native multi-tenancy via URL path:       │
│                                                                   │
│  Write: POST /insert/<accountID>/prometheus/api/v1/write        │
│  Read:  GET /select/<accountID>/prometheus/api/v1/query         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      vmauth (proxy)                       │   │
│  │                                                           │   │
│  │  Route by header/token → inject accountID in path        │   │
│  │                                                           │   │
│  │  Config:                                                  │   │
│  │  users:                                                   │   │
│  │    - bearer_token: "tenant-a-token"                      │   │
│  │      url_prefix: "http://vminsert/insert/1/"             │   │
│  │    - bearer_token: "tenant-b-token"                      │   │
│  │      url_prefix: "http://vminsert/insert/2/"             │   │
│  │    - username: "admin"                                    │   │
│  │      password: "..."                                      │   │
│  │      url_prefix: "http://vmselect/select/0/"             │   │
│  │      # accountID 0 = access all tenants                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Data isolation:                                                 │
│  - Each accountID has separate TSID space                       │
│  - No cross-tenant data leakage                                 │
│  - Query only sees own tenant data                              │
│  - accountID=0 is "super-tenant" (sees all)                    │
│                                                                   │
│  Rate limiting per tenant (vmgateway):                          │
│  - Max ingestion rate (samples/sec)                             │
│  - Max active time-series                                       │
│  - Max query concurrency                                        │
│  - Max query duration                                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Use Case Architectures

### Replace Prometheus + Thanos with VictoriaMetrics
```
┌─────────────────────────────────────────────────────────────────┐
│  BEFORE (Prometheus + Thanos):                                   │
│                                                                   │
│  ┌──────┐ ┌──────┐ ┌──────┐                                    │
│  │Prom 1│ │Prom 2│ │Prom 3│  (per-cluster)                     │
│  │+Side │ │+Side │ │+Side │                                     │
│  │ car  │ │ car  │ │ car  │                                     │
│  └──┬───┘ └──┬───┘ └──┬───┘                                    │
│     │        │        │                                          │
│     └────────┼────────┘                                          │
│              │                                                    │
│  ┌───────┐  │  ┌──────────┐  ┌──────────┐  ┌─────────┐       │
│  │ Store │  │  │Compactor │  │  Query   │  │  Ruler  │       │
│  │Gateway│◄─┘  │          │  │          │  │         │       │
│  └───┬───┘     └──────────┘  └────┬─────┘  └─────────┘       │
│      │                             │                             │
│      └────── S3 Bucket ────────────┘                            │
│                                                                   │
│  Components: 6+ (complex operations, many failure modes)        │
│  RAM: 3× Prometheus + Thanos overhead = massive                 │
│                                                                   │
│  ═══════════════════════════════════════════════════════════     │
│                                                                   │
│  AFTER (VictoriaMetrics Cluster):                                │
│                                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │ vmagent  │ │ vmagent  │ │ vmagent  │  (per-cluster)        │
│  │(200MB RAM│ │          │ │          │                        │
│  │ vs 3GB) │ │          │ │          │                        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                       │
│       │             │             │                              │
│       └─────────────┼─────────────┘                              │
│                     │ remote_write                                │
│                     ▼                                             │
│  ┌──────────────────────────────────────────────────┐           │
│  │          VictoriaMetrics Cluster                   │           │
│  │  vminsert(×2) + vmstorage(×3) + vmselect(×2)    │           │
│  │  + vmalert(×2)                                    │           │
│  │                                                    │           │
│  │  Total RAM: 80GB (vs 300GB+ for Prom+Thanos)    │           │
│  │  Total disk: 2TB (vs 6TB in Thanos S3)          │           │
│  │  Operational complexity: LOW                      │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                   │
│  Benefits:                                                       │
│  - 70% less RAM                                                  │
│  - 60% less disk (better compression)                           │
│  - 5-10x faster queries                                         │
│  - No S3 dependency (local disk)                                │
│  - Simpler operations (fewer components)                        │
│  - Native multi-tenancy                                         │
│  - Same Prometheus scrape configs work in vmagent              │
│  - Same Grafana dashboards work (PromQL compatible)            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Large-Scale Kubernetes Monitoring
```
┌─────────────────────────────────────────────────────────────────┐
│        KUBERNETES MONITORING (10K+ PODS, 5M ACTIVE SERIES)      │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Kubernetes Cluster (multiple)                          │    │
│  │                                                         │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐                    │    │
│  │  │  Node  │ │  Node  │ │  Node  │ ... (100+ nodes)  │    │
│  │  │┌──────┐│ │┌──────┐│ │┌──────┐│                    │    │
│  │  ││Pods  ││ ││Pods  ││ ││Pods  ││                    │    │
│  │  ││/metr.││ ││/metr.││ ││/metr.││                    │    │
│  │  │└──────┘│ │└──────┘│ │└──────┘│                    │    │
│  │  │┌──────┐│ │┌──────┐│ │┌──────┐│                    │    │
│  │  ││node_ ││ ││node_ ││ ││node_ ││                    │    │
│  │  ││export││ ││export││ ││export││                    │    │
│  │  │└──────┘│ │└──────┘│ │└──────┘│                    │    │
│  │  └────────┘ └────────┘ └────────┘                    │    │
│  │                                                         │    │
│  │  ┌──────────────────────────────────────────────┐     │    │
│  │  │  vmagent (DaemonSet, 1 per node)              │     │    │
│  │  │  - Kubernetes SD (discover all pods/services) │     │    │
│  │  │  - Scrape interval: 30s                       │     │    │
│  │  │  - stream_parse for large targets             │     │    │
│  │  │  - Relabeling: drop high-cardinality labels  │     │    │
│  │  │  - On-disk queue: 5GB per vmagent            │     │    │
│  │  └──────────────────────────┬───────────────────┘     │    │
│  └─────────────────────────────┼─────────────────────────┘    │
│                                │                               │
│                                ▼                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │           VictoriaMetrics Cluster                      │    │
│  │                                                        │    │
│  │  vminsert (×3):  4 CPU, 8GB RAM                      │    │
│  │  vmstorage (×5): 16 CPU, 64GB RAM, 4TB NVMe each    │    │
│  │  vmselect (×3):  8 CPU, 16GB RAM                     │    │
│  │                                                        │    │
│  │  -replicationFactor=2 (survive 1 node loss)          │    │
│  │  -retentionPeriod=6 (6 months raw data)              │    │
│  │  -dedup.minScrapeInterval=30s                        │    │
│  │                                                        │    │
│  │  Expected load:                                       │    │
│  │  - 5M active time-series                             │    │
│  │  - 2M samples/sec ingestion                          │    │
│  │  - 100 concurrent dashboard queries                  │    │
│  │  - 8TB total storage (6 months)                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: Why is VictoriaMetrics more memory-efficient than Prometheus?
```
Key reasons:

1. No in-memory time-series head block:
   - Prometheus keeps last 2 hours of ALL series in RAM
   - VM writes to disk immediately (small parts → merged in bg)
   - For 10M series at 15s interval: Prom needs ~20GB just for head
   - VM needs only index cache (~10GB)

2. Better compression → smaller cache needs:
   - VM: 0.4 bytes/sample vs Prometheus: 1.3 bytes/sample
   - Less data to cache = less RAM needed
   - Disk reads are smaller (less I/O buffer RAM)

3. Efficient index structure:
   - VM uses mergeset with careful memory allocation
   - Prometheus uses PostingsForMatchers (memory-heavy for complex queries)
   - VM caches only hot paths in index

4. Go runtime optimization:
   - VM uses manual memory management in hot paths (arena allocation)
   - Avoids GC pressure for time-series data
   - Custom allocators for fixed-size structures

5. No WAL for raw samples:
   - Prometheus writes samples to WAL (memory-mapped file)
   - VM writes directly to storage parts
   - Less memory-mapped file overhead

Practical numbers:
- 1M active series: Prometheus ~4GB, VM ~500MB
- 10M active series: Prometheus ~40GB, VM ~5GB
- 50M active series: Prometheus impossible (OOM), VM ~25GB
```

### Q2: How does VictoriaMetrics handle node failures in cluster mode?
```
Scenario: vmstorage-2 out of 3 nodes goes down

Write path:
- vminsert detects vmstorage-2 is unavailable
- With -replicationFactor=2:
  - Data destined for node 2 is also on node 1 or 3
  - vminsert routes new writes to remaining nodes
  - Some writes buffered until node returns or timeout
- Without replication:
  - 1/3 of incoming data has nowhere to go
  - vminsert buffers briefly, then drops if node doesn't return
  - Data gap for that shard

Read path:
- vmselect fans out to all 3 vmstorage nodes
- vmstorage-2 timeout → partial results
- With -replicationFactor=2:
  - All data available from surviving nodes
  - vmselect deduplicates (same TSID from multiple nodes)
  - Full results, no gap
- vmselect flag: -search.maxQueryDuration handles slow/dead nodes

Recovery:
1. vmstorage-2 comes back online
2. During downtime gap:
   - With replication: data exists on other nodes (no loss)
   - Without replication: gap in data (acceptable for monitoring)
3. No data re-balancing needed (unlike Cassandra/Kafka)
4. Node immediately starts receiving new writes

Key insight: VictoriaMetrics intentionally avoids complex consensus
protocols (no Raft, no Paxos). Simple replication + client-side
routing is sufficient for monitoring workloads where brief gaps
are acceptable.
```

### Q3: When would you choose VictoriaMetrics over Prometheus+Thanos?
```
Choose VictoriaMetrics when:
- > 5M active time-series (Prometheus struggles)
- Need long-term retention without object storage complexity
- Want simpler operations (fewer components to manage)
- Need multi-tenancy
- Want to reduce infrastructure costs (70% less RAM)
- Need faster queries for large time ranges
- Have multiple Prometheus instances to consolidate

Choose Prometheus + Thanos when:
- Already heavily invested in Thanos ecosystem
- Need object storage (S3) for unlimited retention
- Want downsampling built-in (5m, 1h resolutions)
- Organization mandates Prometheus as standard
- Small scale (< 1M series) where complexity doesn't matter
- Need Prometheus recording rules with local evaluation

Choose Prometheus + Cortex/Mimir when:
- Need multi-tenant SaaS metrics platform
- Already on AWS/GCP with good object storage
- Want Grafana Labs ecosystem integration
- Need write-ahead log for durability guarantees
- Enterprise support important

VictoriaMetrics advantages summary:
- 10x less RAM for same workload
- 3x better compression (less disk)
- 2-10x faster queries
- Simpler architecture (no ZK, no etcd, no S3)
- Drop-in Prometheus replacement (same configs, same Grafana)
- Native multi-tenancy in cluster mode
- MetricsQL extensions (WITH templates, keep_metric_names)
```

### Q4: How would you migrate from Prometheus to VictoriaMetrics?
```
Migration strategy (zero downtime):

Phase 1: Add VictoriaMetrics alongside Prometheus (Week 1)
  - Deploy VM single-node or cluster
  - Configure Prometheus remote_write to VM:
    remote_write:
      - url: http://victoria-metrics:8428/api/v1/write
  - Both Prometheus and VM now have same data
  - No changes to Grafana yet

Phase 2: Validate (Week 2)
  - Add VM as additional Grafana datasource
  - Compare query results between Prometheus and VM
  - Check: same values? same graphs? any gaps?
  - Validate alerting rules work with VM (vmalert)
  - Run load tests on VM

Phase 3: Historical migration (Week 2-3)
  - Use vmctl to migrate historical data:
    vmctl prometheus \
      --prom-snapshot=/prometheus/data \
      --vm-addr=http://vm:8428
  - Or: keep Prometheus for historical, VM for new data
  
Phase 4: Switch Grafana to VM (Week 3)
  - Change default datasource to VM
  - All dashboards work unchanged (PromQL compatible)
  - Monitor for any query differences (MetricsQL vs PromQL edge cases)

Phase 5: Replace Prometheus with vmagent (Week 4)
  - Deploy vmagent with same scrape_configs
  - vmagent uses same service discovery (Kubernetes SD, etc.)
  - Same relabeling rules work
  - 10x less RAM than Prometheus for scraping
  - Remove Prometheus instances

Phase 6: Cleanup (Week 5)
  - Remove Prometheus datasource from Grafana
  - Set up vmalert for alerting rules
  - Configure vmbackup for disaster recovery
  - Document new architecture

Rollback plan:
  - Keep Prometheus running in parallel for 2 weeks
  - Grafana can switch back to Prometheus datasource instantly
  - No data loss in either system during parallel period
```

### Q5: Explain the consistent hashing in vminsert and its implications.
```
vminsert uses jump consistent hash to route time-series to vmstorage:

Algorithm:
  hash = jump_hash(metric_labels_hash, num_storage_nodes)

Properties:
1. Deterministic: same metric always goes to same node
2. Uniform distribution: roughly equal data per node
3. Minimal redistribution: adding node N+1 moves only 1/(N+1) data

Example with 3 vmstorage nodes:
  metric{job="api"} → hash → node 0
  metric{job="web"} → hash → node 2
  metric{job="db"}  → hash → node 1

When adding vmstorage-3 (total 4 nodes):
  ~25% of series move to new node (minimal disruption)
  Remaining 75% stay on same node (no re-routing)

Implications:

1. Data locality:
   - All samples for one time-series are on same node
   - Queries for specific series only need that node's data
   - BUT vmselect doesn't know which node → queries all (fan-out)

2. Rebalancing on node addition:
   - New node starts receiving ~1/N of new writes
   - Old data stays on original nodes (not moved)
   - Historical queries still hit old nodes
   - Gradual migration (new data goes to new distribution)

3. Node removal:
   - Re-hash routes orphaned series to remaining nodes
   - Old data on removed node is lost (unless replicated)
   - Plan: decommission gradually, let retention expire

4. With replication (factor=2):
   - Series goes to node[hash] AND node[(hash+1) % N]
   - Both nodes have complete copy of that series
   - vmselect deduplicates (picks any copy)

5. Sharding limitations:
   - Cannot query single vmstorage for "all data" (distributed)
   - Global aggregations always fan out to ALL nodes
   - No partial query routing optimization (unlike Thanos)
```

---

## Scenario-Based Questions

### Scenario 1: Design monitoring for 10K Kubernetes pods (5M active series)
```
Requirements:
- 10K pods across 3 clusters
- ~500 metrics per pod = 5M active time-series
- 15-second scrape interval
- 90-day retention
- < 200ms dashboard query latency

Architecture:
┌──────────────────────────────────────────────────────────┐
│  Cluster 1        Cluster 2        Cluster 3             │
│  ┌────────┐      ┌────────┐      ┌────────┐            │
│  │vmagent │      │vmagent │      │vmagent │            │
│  │DaemonSet│     │DaemonSet│     │DaemonSet│            │
│  │(3 nodes)│     │(3 nodes)│     │(4 nodes)│           │
│  └────┬───┘      └────┬───┘      └────┬───┘            │
│       │               │               │                  │
│       └───────────────┼───────────────┘                  │
│                       │ remote_write                      │
│                       ▼                                   │
│  ┌────────────────────────────────────────────────────┐ │
│  │        Central VictoriaMetrics Cluster              │ │
│  │                                                     │ │
│  │  vminsert (×3): 4 CPU, 8GB RAM                    │ │
│  │  vmstorage (×3): 16 CPU, 64GB RAM, 3TB NVMe      │ │
│  │  vmselect (×3): 8 CPU, 16GB RAM                   │ │
│  │                                                     │ │
│  │  Flags:                                            │ │
│  │  -replicationFactor=2                              │ │
│  │  -retentionPeriod=3 (3 months)                    │ │
│  │  -dedup.minScrapeInterval=15s                     │ │
│  │  -search.maxConcurrentRequests=64                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                           │
│  Capacity:                                               │
│  - Ingestion: 5M / 15s = 333K samples/sec              │
│  - Disk: 5M × 5760/day × 0.5B × 90d = 1.3 TB         │
│  - With replication×2: 2.6 TB total → 3TB per node ok │
│  - RAM: 5M × 1KB + overhead = ~8GB per vmstorage       │
│                                                           │
│  Recording rules (vmalert):                             │
│  - Pre-compute common dashboard queries                 │
│  - 5-min aggregates for: CPU, memory, network, errors  │
│  - Reduces dashboard query scan from 90d to seconds    │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Scenario 2: Migrate from Thanos to VictoriaMetrics cluster
```
Current state: 4 Prometheus + Thanos (Sidecar, Store, Compactor, Query)
Problem: Query latency 5-30s for week-long queries, high S3 costs

Migration plan:

Week 1: Deploy VM cluster alongside Thanos
  - Add remote_write to all 4 Prometheus instances → vminsert
  - VM receives same data as Thanos from this point forward
  - Validate: compare query results

Week 2: Historical data migration
  - Use vmctl to import from Thanos S3:
    vmctl prometheus --prom-snapshot (from each Prometheus)
  - OR accept: only new data in VM, old data from Thanos
  - Hybrid Grafana: old queries → Thanos, new → VM

Week 3: Switch queries to VM
  - Change Grafana datasource: Thanos Query → vmselect
  - Verify: all dashboards work
  - Verify: alert rules work via vmalert
  - Expected improvement: queries 5-10x faster

Week 4: Replace Prometheus with vmagent
  - Deploy vmagent with same scrape_configs
  - Stop Prometheus instances
  - Keep Thanos read-only for 30 days (rollback safety)

Week 5: Decommission Thanos
  - Remove Thanos components (Sidecar, Store, Compactor, Query)
  - Remove S3 bucket (after confirming all data in VM)
  - Final architecture: vmagent → VM cluster → Grafana

Results:
  - Query latency: 30s → 200ms (150x improvement)
  - RAM: 300GB → 90GB (70% reduction)
  - Storage cost: S3 $500/mo → NVMe $200/mo (60% reduction)
  - Operational: 6 components → 3 (vminsert, vmstorage, vmselect)
  - Complexity: significantly reduced
```

### Scenario 3: Handle 10x traffic spike during Black Friday
```
Context: E-commerce platform, normal: 500K series, spike: 5M series

Preparation (2 weeks before):

1. Capacity analysis:
   - Current: 3 vmstorage × 16GB RAM = handles 2M series
   - Spike: need 5M series = need ~50GB RAM total
   - Add 2 more vmstorage nodes (5 total)
   - Scale vminsert from 2 → 4 (handle ingestion burst)

2. Pre-scale (1 week before):
   - Add vmstorage-4 and vmstorage-5 to cluster
   - Data will gradually distribute to new nodes
   - Existing data stays on old nodes
   - Scale vmselect to 4 (handle dashboard traffic)

3. Optimize queries:
   - Pre-compute recording rules for key metrics:
     - Revenue per second
     - Error rate by service
     - Cart abandonment rate
   - These recording rules survive any spike

4. Set resource limits:
   -search.maxUniqueTimeseries=500000    # Per query limit
   -search.maxConcurrentRequests=128      # Allow more parallel
   -maxLabelsPerTimeseries=30             # Prevent explosion
   -insert.maxQueueDuration=2m            # Buffer during spikes

During Black Friday:

   Monitoring:
   - Watch vm_rows_inserted_total rate (ingestion)
   - Watch vm_active_time_series (cardinality)
   - Watch process_resident_memory_bytes (RAM)
   - Watch vm_slow_queries_total (query performance)

   If overloaded:
   - HPA scales vminsert/vmselect automatically
   - vmstorage: cannot auto-scale (stateful) → pre-provisioned
   - Emergency: increase -search.maxQueryDuration from 60s to 120s
   - Emergency: reduce scrape granularity (30s → 60s via vmagent relabel)

After Black Friday:
   - Spike series naturally expire after retention period
   - Scale down vminsert/vmselect (stateless, easy)
   - Keep vmstorage (data needs to age out)
   - Post-mortem: analyze cardinality growth, tune limits
```
