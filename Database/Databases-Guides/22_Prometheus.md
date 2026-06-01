# Prometheus - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [TSDB Storage Engine Internals](#tsdb-storage-engine-internals)
3. [Data Model & PromQL](#data-model--promql)
4. [Service Discovery & Scraping](#service-discovery--scraping)
5. [Federation & Remote Storage](#federation--remote-storage)
6. [Alerting & Recording Rules](#alerting--recording-rules)
7. [High Availability & Scaling (Thanos/Cortex/Mimir)](#high-availability--scaling)
8. [Performance & Resource Optimization](#performance--resource-optimization)
9. [Production Deployment Patterns](#production-deployment-patterns)
10. [Monitoring Prometheus Itself](#monitoring-prometheus-itself)
11. [Security & Multi-tenancy](#security--multi-tenancy)
12. [Use Case Architectures](#use-case-architectures)
13. [Staff Architect Interview Questions](#staff-architect-interview-questions)
14. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is Prometheus?
```
Prometheus is an open-source systems monitoring and alerting toolkit
originally built at SoundCloud (2012), now a CNCF graduated project.
It is the de-facto standard for cloud-native monitoring.

Key characteristics:
- Pull-based model (scrapes targets via HTTP)
- Multi-dimensional data model (metric name + key/value labels)
- PromQL - powerful functional query language
- No distributed storage dependency (single-node by default)
- Service discovery (Kubernetes, Consul, EC2, DNS, file-based)
- Built-in alerting (Alertmanager integration)
- Time-series database (custom TSDB)
- Written in Go (single binary)

What Prometheus is NOT designed for:
- Long-term storage (default 15d retention)
- 100% accuracy billing/auditing data
- Log aggregation or event storage
- Distributed tracing
- High-cardinality wide events

Comparison:
┌────────────────────┬────────────┬───────────────┬──────────────┬──────────────┐
│                    │ Prometheus │ VictoriaM.    │ InfluxDB     │ Datadog      │
├────────────────────┼────────────┼───────────────┼──────────────┼──────────────┤
│ Collection Model   │ Pull       │ Pull+Push     │ Push         │ Push (agent) │
│ Query Language     │ PromQL     │ MetricsQL     │ Flux/InfluxQL│ Proprietary  │
│ Storage            │ Local TSDB │ Custom TSDB   │ TSM/IOx      │ SaaS         │
│ Scalability        │ Vertical   │ Horizontal    │ Cluster(Ent) │ Managed      │
│ HA Built-in        │ No         │ Yes           │ Enterprise   │ Yes          │
│ Cost               │ Free/OSS   │ Free/OSS      │ OSS+Ent      │ $$$/host     │
│ Cardinality Limit  │ ~10M series│ ~100M series  │ ~10M series  │ Custom Tags  │
│ Long-term Storage  │ External   │ Built-in      │ Built-in     │ Built-in     │
└────────────────────┴────────────┴───────────────┴──────────────┴──────────────┘
```

### Pull-Based Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PROMETHEUS PULL-BASED ARCHITECTURE                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        TARGETS (Exporters)                            │   │
│  │                                                                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │   │
│  │  │ Node     │  │ App      │  │ MySQL    │  │ Kubernetes       │    │   │
│  │  │ Exporter │  │ /metrics │  │ Exporter │  │ kube-state-metrics│    │   │
│  │  │ :9100    │  │ :8080    │  │ :9104    │  │ :8080            │    │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘    │   │
│  │       │              │              │                  │              │   │
│  └───────┼──────────────┼──────────────┼──────────────────┼──────────────┘   │
│          │   HTTP GET   │   /metrics   │                  │                   │
│          │   scrape     │              │                  │                   │
│          ▼              ▼              ▼                  ▼                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      PROMETHEUS SERVER                                │   │
│  │                                                                       │   │
│  │  ┌────────────────┐    ┌────────────────┐    ┌──────────────────┐   │   │
│  │  │ Service        │    │ Scrape         │    │ Rule Engine      │   │   │
│  │  │ Discovery      │───▶│ Manager        │    │ (Recording +     │   │   │
│  │  │                │    │                │    │  Alerting Rules) │   │   │
│  │  │ - Kubernetes   │    │ - Interval     │    │                  │   │   │
│  │  │ - Consul       │    │ - Timeout      │    │ Evaluates every  │   │   │
│  │  │ - EC2/GCE      │    │ - Relabeling   │    │ evaluation_interval│  │   │
│  │  │ - DNS          │    │                │    └────────┬─────────┘   │   │
│  │  │ - File         │    └───────┬────────┘             │             │   │
│  │  └────────────────┘            │                      │             │   │
│  │                                ▼                      ▼             │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │                     LOCAL TSDB                                  │  │   │
│  │  │  ┌─────────┐  ┌──────────────┐  ┌────────────────────────┐   │  │   │
│  │  │  │  HEAD   │  │   WAL        │  │  Persistent Blocks     │   │  │   │
│  │  │  │ (memory)│  │ (write-ahead │  │  (2-hour blocks on     │   │  │   │
│  │  │  │         │  │  log)        │  │   disk, compacted)     │   │  │   │
│  │  │  └─────────┘  └──────────────┘  └────────────────────────┘   │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │  ┌──────────────┐    ┌────────────────────────────────────────────┐  │   │
│  │  │ HTTP API     │    │ Remote Write / Remote Read                  │  │   │
│  │  │ /api/v1/     │    │ (to long-term storage: Thanos/Cortex/VM)   │  │   │
│  │  └──────┬───────┘    └───────────────────┬────────────────────────┘  │   │
│  │         │                                 │                           │   │
│  └─────────┼─────────────────────────────────┼───────────────────────────┘   │
│            │                                 │                               │
│            ▼                                 ▼                               │
│  ┌──────────────────┐              ┌──────────────────────┐                  │
│  │ Grafana          │              │ Long-term Storage     │                  │
│  │ Dashboards       │              │ (Thanos/Mimir/VM)    │                  │
│  └──────────────────┘              └──────────────────────┘                  │
│                                                                              │
│            ┌──────────────────┐                                              │
│            │ ALERTMANAGER     │◀── Firing alerts from Rule Engine            │
│            │ - Routing        │                                              │
│            │ - Grouping       │──▶ PagerDuty / Slack / Email / Webhook       │
│            │ - Silencing      │                                              │
│            │ - Inhibition     │                                              │
│            └──────────────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Pull-Based?
```
Pull model advantages:
1. Target health detection - if scrape fails, Prometheus knows target is down
2. No client-side buffering - targets are stateless metric endpoints
3. Easy to debug - you can curl /metrics yourself
4. Central control - Prometheus decides what/when to scrape
5. No firewall issues for most deployments (Prometheus initiates)

Pull model challenges:
1. Short-lived jobs (solved with Pushgateway)
2. Firewall/NAT traversal (solved with Proxy or Agent mode)
3. Scale: single Prometheus must reach all targets

Push vs Pull tradeoff:
┌─────────────────────────────────────────────────────┐
│   PUSH MODEL (InfluxDB, Datadog)                     │
│   - Client pushes → central collector                │
│   - Client must know destination                     │
│   - Backpressure handling needed                     │
│   - Works through firewalls/NAT                      │
│                                                      │
│   PULL MODEL (Prometheus)                            │
│   - Server pulls ← targets                           │
│   - Server must discover targets                     │
│   - No backpressure on targets                       │
│   - Health inherent in scrape success/failure        │
└─────────────────────────────────────────────────────┘
```

---

## TSDB Storage Engine Internals

### Storage Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PROMETHEUS TSDB ARCHITECTURE                           │
│                                                                              │
│  Incoming Samples (from scrapes)                                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         HEAD BLOCK (in-memory)                        │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                    WRITE-AHEAD LOG (WAL)                      │    │    │
│  │  │  On-disk durability for in-memory data                        │    │    │
│  │  │  Segments: 128MB each, sequential writes                      │    │    │
│  │  │  Contains: series records + sample records                    │    │    │
│  │  │  Replayed on crash recovery                                   │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                    IN-MEMORY CHUNKS                           │    │    │
│  │  │                                                               │    │    │
│  │  │  Series 1: ──[chunk 120samples]──[chunk 80samples (active)]  │    │    │
│  │  │  Series 2: ──[chunk 120samples]──[chunk 45samples (active)]  │    │    │
│  │  │  Series 3: ──[chunk 120samples]──[chunk 120samples]──[...]   │    │    │
│  │  │                                                               │    │    │
│  │  │  Encoding: XOR (Gorilla) for values                          │    │    │
│  │  │            Delta-of-delta for timestamps                      │    │    │
│  │  │  Each chunk: min 120 samples or 2 hours                       │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                    MMAP'D HEAD CHUNKS                         │    │    │
│  │  │  Completed chunks are mmap'd to disk to save RAM              │    │    │
│  │  │  File: chunks_head/000001                                     │    │    │
│  │  │  Still part of head block (queryable as "recent data")        │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │                                                                       │    │
│  │  Head block time range: [now - 2h, now]  (min_block_duration)        │    │
│  └──────────────────────────────────────┬──────────────────────────────┘    │
│                                          │ COMPACTION (every 2 hours)        │
│                                          ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     PERSISTENT BLOCKS (on disk)                       │    │
│  │                                                                       │    │
│  │  Block 01 (2h)   Block 02 (2h)   Block 03 (6h)    Block 04 (18h)   │    │
│  │  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐    │    │
│  │  │ meta.json │   │ meta.json │   │ meta.json │   │ meta.json │    │    │
│  │  │ chunks/   │   │ chunks/   │   │ chunks/   │   │ chunks/   │    │    │
│  │  │ index     │   │ index     │   │ index     │   │ index     │    │    │
│  │  │ tombstones│   │ tombstones│   │ tombstones│   │ tombstones│    │    │
│  │  └───────────┘   └───────────┘   └───────────┘   └───────────┘    │    │
│  │                                                                       │    │
│  │  Compaction merges blocks:  2h + 2h + 2h = 6h block                  │    │
│  │  Max block size: 10% of retention or 31 days                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Block Structure:                                                            │
│  ./data/                                                                     │
│  ├── 01BKGV7JBM69T2G1BGBGM6KB12/   ← Block ULID                           │
│  │   ├── meta.json                    ← Block metadata (time range, stats)  │
│  │   ├── chunks/                                                             │
│  │   │   └── 000001                   ← Chunk data (series samples)         │
│  │   ├── index                        ← Inverted index + postings           │
│  │   └── tombstones                   ← Deleted series markers              │
│  ├── chunks_head/                     ← mmap'd head chunks                  │
│  │   └── 000001                                                              │
│  ├── wal/                             ← Write-ahead log                     │
│  │   ├── 00000001                                                            │
│  │   └── 00000002                                                            │
│  └── lock                             ← File lock                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Compaction Process
```
Compaction Strategy:
- Level 1: 2h blocks (raw from head)
- Level 2: 6h blocks (3 × 2h merged)
- Level 3: 18h blocks (3 × 6h merged)
- Level 4: 54h blocks (3 × 18h merged)
- Max: min(retention/10, 31 days)

Compaction does:
1. Merges overlapping blocks
2. Re-indexes for optimal query performance
3. Removes deleted series (tombstones)
4. Re-encodes chunks for better compression
5. Drops out-of-retention-window data

Timeline:
  Time ────────────────────────────────────────────────▶
  
  │2h│2h│2h│2h│2h│2h│2h│2h│2h│   ← Initial blocks
  │───6h───│───6h───│───6h───│   ← After L1 compaction
  │────────18h────────│           ← After L2 compaction
```

### Index Structure
```
Index file contains:
1. Symbol table: All label names and values (deduplicated strings)
2. Series: list of (labels → chunk references)
3. Label index: label_name → [sorted values]
4. Postings: (label_name, label_value) → [series_ids]
5. Postings offset table: lookup for postings lists

Query path example: http_requests_total{method="GET", status="200"}
1. Look up postings for __name__="http_requests_total" → [1, 5, 8, 12, 15]
2. Look up postings for method="GET" → [1, 3, 5, 8, 10, 12]
3. Look up postings for status="200" → [1, 5, 12, 20]
4. Intersect: [1, 5, 12]
5. For each series, read chunk data for requested time range
```

---

## Data Model & PromQL

### Metric Types
```
┌─────────────────────────────────────────────────────────────────┐
│                    PROMETHEUS METRIC TYPES                        │
├──────────────┬───────────────────────────────────────────────────┤
│ COUNTER      │ Monotonically increasing value (resets on restart)│
│              │ Examples: http_requests_total, errors_total        │
│              │ Operations: rate(), increase(), resets()           │
│              │                                                    │
│              │   Value                                            │
│              │     ▲      reset                                   │
│              │     │    ╱╲   ╱                                    │
│              │     │   ╱  ╲ ╱                                     │
│              │     │  ╱    ╱                                      │
│              │     │ ╱    ╱                                       │
│              │     │╱   ╱                                         │
│              │     ────────────▶ Time                             │
├──────────────┼───────────────────────────────────────────────────┤
│ GAUGE        │ Value that goes up and down                        │
│              │ Examples: temperature, memory_usage, queue_length  │
│              │ Operations: avg_over_time(), max_over_time()       │
│              │                                                    │
│              │   Value                                            │
│              │     ▲   ╱╲      ╱╲                                │
│              │     │  ╱  ╲    ╱  ╲                               │
│              │     │ ╱    ╲  ╱    ╲                              │
│              │     │╱      ╲╱      ╲                             │
│              │     ────────────────▶ Time                         │
├──────────────┼───────────────────────────────────────────────────┤
│ HISTOGRAM    │ Observations bucketed by size                      │
│              │ Creates: _bucket{le="X"}, _sum, _count            │
│              │ Examples: request_duration_seconds                  │
│              │ Operations: histogram_quantile(0.99, ...)          │
│              │                                                    │
│              │  Series generated:                                 │
│              │  request_duration_seconds_bucket{le="0.005"}       │
│              │  request_duration_seconds_bucket{le="0.01"}        │
│              │  request_duration_seconds_bucket{le="0.025"}       │
│              │  request_duration_seconds_bucket{le="0.05"}        │
│              │  request_duration_seconds_bucket{le="0.1"}         │
│              │  request_duration_seconds_bucket{le="+Inf"}        │
│              │  request_duration_seconds_sum                      │
│              │  request_duration_seconds_count                    │
├──────────────┼───────────────────────────────────────────────────┤
│ SUMMARY      │ Client-side calculated quantiles                   │
│              │ Creates: {quantile="0.5"}, {quantile="0.99"},     │
│              │          _sum, _count                              │
│              │ Cannot be aggregated across instances!             │
│              │ Prefer histograms in most cases                    │
└──────────────┴───────────────────────────────────────────────────┘
```

### Label Cardinality
```
Cardinality = unique combinations of label values for a metric

CRITICAL RULE: Total series = metric × Π(label_cardinality)

Example:
  http_requests_total{method, status, endpoint, instance}
  method: 5 values (GET, POST, PUT, DELETE, PATCH)
  status: 10 values (200, 201, 204, 301, 400, 401, 403, 404, 500, 503)
  endpoint: 50 values
  instance: 20 instances
  
  Total series = 5 × 10 × 50 × 20 = 100,000 series ← Acceptable

DANGER - High cardinality labels:
  - user_id (millions of values)
  - request_id / trace_id (unbounded)
  - email addresses
  - full URLs with query params
  - timestamps as labels

Production guidelines:
  - Keep total active series < 5-10 million per Prometheus
  - Any single metric with > 100K series needs review
  - Use recording rules to pre-aggregate high-cardinality queries
```

### PromQL Deep Dive
```
PromQL Expression Types:
1. Instant vector: single sample per series at a point in time
2. Range vector: set of samples over time range per series
3. Scalar: single numeric value
4. String: single string value (rarely used)

Key Operations:

# Rate of counter over 5 minutes (per-second)
rate(http_requests_total[5m])

# 99th percentile latency from histogram
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m])) * 100

# Top 5 memory consumers
topk(5, container_memory_usage_bytes)

# Predict disk full in 4 hours
predict_linear(node_filesystem_avail_bytes[1h], 4*3600) < 0

# Aggregation across dimensions
sum by (service) (rate(http_requests_total[5m]))
sum without (instance) (rate(http_requests_total[5m]))

# Subquery (evaluate inner at 1m resolution over 30m)
max_over_time(rate(http_requests_total[5m])[30m:1m])

Important gotchas:
- rate() only works with counters (handles resets)
- irate() uses last two samples only (spiky, for dashboards)
- increase() = rate() × time_range (extrapolated, can be non-integer)
- offset modifier: http_requests_total offset 1h
- @ modifier: http_requests_total @ 1609459200 (unix timestamp)
```

---

## Service Discovery & Scraping

### Service Discovery Mechanisms
```
┌─────────────────────────────────────────────────────────────────┐
│                  SERVICE DISCOVERY FLOW                           │
│                                                                   │
│  ┌──────────────┐     ┌───────────────┐     ┌───────────────┐  │
│  │  Discovery   │────▶│  Relabeling   │────▶│  Target       │  │
│  │  Provider    │     │  (before      │     │  List         │  │
│  │              │     │   scrape)     │     │              │  │
│  └──────────────┘     └───────────────┘     └───────┬───────┘  │
│                                                      │          │
│  Providers:                                          ▼          │
│  - kubernetes_sd    ┌────────────────────────────────────────┐  │
│  - consul_sd        │  SCRAPE                                 │  │
│  - ec2_sd           │  GET /metrics HTTP/1.1                  │  │
│  - dns_sd           │  + honor_labels                         │  │
│  - file_sd          │  + honor_timestamps                     │  │
│  - static_configs   │  + metric_relabel_configs (after parse)│  │
│  - azure_sd         └────────────────────────────────────────┘  │
│  - gce_sd                                                        │
│  - openstack_sd                                                  │
└─────────────────────────────────────────────────────────────────┘

Kubernetes SD discovers:
- node: each Kubernetes node
- pod: each pod (all containers)
- service: each service
- endpoints: each endpoint (pod behind service)
- endpointslice: scalable endpoint discovery
- ingress: each ingress

Labels available in kubernetes_sd (endpoints role):
  __meta_kubernetes_namespace
  __meta_kubernetes_service_name
  __meta_kubernetes_pod_name
  __meta_kubernetes_pod_ip
  __meta_kubernetes_pod_container_name
  __meta_kubernetes_pod_annotation_*
  __meta_kubernetes_pod_label_*
```

### Relabeling
```
Relabeling use cases:
1. Drop unwanted targets (keep/drop)
2. Override target labels (replace)
3. Set scrape path (__metrics_path__)
4. Map annotations to labels
5. Hash-based sharding across multiple Prometheus

Example configurations:

# Keep only pods with annotation prometheus.io/scrape: "true"
relabel_configs:
  - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
    action: keep
    regex: "true"

# Use pod annotation for metrics path
  - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
    action: replace
    target_label: __metrics_path__
    regex: (.+)

# Hash-based sharding (this Prometheus handles 1/3 of targets)
  - source_labels: [__address__]
    modulus: 3
    target_label: __tmp_hash
    action: hashmod
  - source_labels: [__tmp_hash]
    regex: "0"
    action: keep

metric_relabel_configs (post-scrape):
# Drop expensive high-cardinality metrics
  - source_labels: [__name__]
    regex: "go_gc_.*"
    action: drop

# Remove a label to reduce cardinality
  - regex: "pod_template_hash"
    action: labeldrop
```

---

## Federation & Remote Storage

### Federation Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HIERARCHICAL FEDERATION                                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     GLOBAL PROMETHEUS                                │    │
│  │  - Scrapes /federate from regional Prometheus                       │    │
│  │  - Stores aggregated metrics only (recording rules)                 │    │
│  │  - Cross-region dashboards and alerting                             │    │
│  │  - Lower resolution (longer scrape_interval)                        │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                    │ /federate                               │
│                ┌───────────────────┼──────────────────┐                      │
│                │                   │                   │                      │
│                ▼                   ▼                   ▼                      │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │
│  │ Regional Prom    │ │ Regional Prom    │ │ Regional Prom    │            │
│  │ US-EAST          │ │ EU-WEST          │ │ AP-SOUTH         │            │
│  │                  │ │                  │ │                  │            │
│  │ - Full resolution│ │ - Full resolution│ │ - Full resolution│            │
│  │ - Local alerting │ │ - Local alerting │ │ - Local alerting │            │
│  │ - Recording rules│ │ - Recording rules│ │ - Recording rules│            │
│  └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘            │
│           │                     │                     │                      │
│           ▼                     ▼                     ▼                      │
│     ┌──────────┐          ┌──────────┐          ┌──────────┐               │
│     │ Targets  │          │ Targets  │          │ Targets  │               │
│     │ (1000s)  │          │ (1000s)  │          │ (1000s)  │               │
│     └──────────┘          └──────────┘          └──────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘

Federation limitations:
- Single point of failure (global Prometheus)
- Data loss during network partitions
- Cannot handle high cardinality at global level
- Better alternatives: Thanos, Cortex, Mimir
```

### Remote Write / Remote Read
```
┌─────────────────────────────────────────────────────────────────┐
│                  REMOTE WRITE PROTOCOL                            │
│                                                                   │
│  Prometheus ──────remote_write──────▶ Remote Storage             │
│                                                                   │
│  Protocol: HTTP POST with protobuf + snappy compression          │
│  Endpoint: /api/v1/write                                         │
│  Batching: Sends samples in batches (configurable)               │
│  Retry: Exponential backoff on failure                            │
│  WAL-based: Reads from WAL for durable delivery                  │
│                                                                   │
│  Configuration:                                                   │
│  remote_write:                                                    │
│    - url: "http://victoriametrics:8428/api/v1/write"             │
│      queue_config:                                                │
│        capacity: 10000          # Buffer size                    │
│        max_shards: 200          # Parallel senders               │
│        max_samples_per_send: 5000                                │
│        batch_send_deadline: 5s                                   │
│      write_relabel_configs:     # Filter what to send            │
│        - source_labels: [__name__]                               │
│          regex: "expensive_.*"                                    │
│          action: drop                                             │
│                                                                   │
│  Remote Read (less common):                                       │
│  remote_read:                                                     │
│    - url: "http://thanos-store:10901/api/v1/read"               │
│      read_recent: false         # Don't read recent (use local) │
└─────────────────────────────────────────────────────────────────┘
```

---

## Alerting & Recording Rules

### Alertmanager Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ALERTING PIPELINE                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │ PROMETHEUS (Rule Evaluation)                         │                    │
│  │                                                      │                    │
│  │  alerting_rules.yml:                                │                    │
│  │  - alert: HighErrorRate                             │                    │
│  │    expr: rate(http_errors[5m]) / rate(http_total[5m]) > 0.05           │  │
│  │    for: 5m        ← Must be firing for 5m           │                    │
│  │    labels:                                           │                    │
│  │      severity: critical                              │                    │
│  │    annotations:                                      │                    │
│  │      summary: "High error rate on {{ $labels.instance }}"              │  │
│  │                                                      │                    │
│  │  States: INACTIVE → PENDING (for duration) → FIRING │                    │
│  └──────────────────────────┬───────────────────────────┘                    │
│                              │  POST /api/v2/alerts                           │
│                              ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        ALERTMANAGER                                   │    │
│  │                                                                       │    │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐  │    │
│  │  │ Grouping │───▶│ Inhibit  │───▶│ Silence  │───▶│   Routing    │  │    │
│  │  │          │    │          │    │          │    │   Tree       │  │    │
│  │  │ group_by:│    │ If alert │    │ Matchers │    │              │  │    │
│  │  │ [cluster,│    │ A fires, │    │ suppress │    │ Match labels │  │    │
│  │  │  service]│    │ suppress │    │ alerts   │    │ → receiver   │  │    │
│  │  └──────────┘    │ alert B  │    │ for time │    └──────┬───────┘  │    │
│  │                   └──────────┘    └──────────┘           │          │    │
│  │                                                          ▼          │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │                      RECEIVERS                                │  │    │
│  │  │                                                               │  │    │
│  │  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────────┐  │  │    │
│  │  │  │PagerDuty│ │  Slack  │ │  Email   │ │  Webhook        │  │  │    │
│  │  │  └─────────┘ └─────────┘ └──────────┘ └─────────────────┘  │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                                                                       │    │
│  │  Clustering: Multiple Alertmanager instances for HA                  │    │
│  │  - Gossip protocol (hashicorp/memberlist)                            │    │
│  │  - Deduplicates notifications across instances                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

Routing Tree Example:
route:
  receiver: 'default-receiver'
  group_by: ['alertname', 'cluster']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      continue: false
    - match:
        severity: warning
      receiver: 'slack-warnings'
    - match_re:
        service: "database|cache"
      receiver: 'dba-team'
```

### Recording Rules
```
Recording rules pre-compute expensive queries:

groups:
  - name: http_metrics
    interval: 30s
    rules:
      # Pre-compute request rate by service
      - record: service:http_requests:rate5m
        expr: sum by (service) (rate(http_requests_total[5m]))
      
      # Pre-compute error ratio
      - record: service:http_errors:ratio_rate5m
        expr: |
          sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
          /
          sum by (service) (rate(http_requests_total[5m]))
      
      # Pre-compute p99 latency
      - record: service:http_duration:p99_5m
        expr: |
          histogram_quantile(0.99,
            sum by (service, le) (
              rate(http_request_duration_seconds_bucket[5m])
            )
          )

Benefits:
- Dashboard queries are instant (pre-computed)
- Alerting rules use recording rules (faster evaluation)
- Reduces query load on TSDB
- Lower cardinality stored result
```

---

## High Availability & Scaling

### Thanos Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         THANOS ARCHITECTURE                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         QUERY LAYER                                   │    │
│  │                                                                       │    │
│  │  ┌───────────────────────────────────────────────────────────────┐   │    │
│  │  │                    THANOS QUERY                                 │   │    │
│  │  │  - Implements PromQL                                           │   │    │
│  │  │  - Deduplicates data from multiple Prometheus                  │   │    │
│  │  │  - Fan-out to multiple StoreAPI backends                       │   │    │
│  │  │  - Partial response (handles some stores being down)           │   │    │
│  │  └───────────────────┬────────────────┬───────────────────────────┘   │    │
│  │                       │                │                               │    │
│  └───────────────────────┼────────────────┼───────────────────────────────┘    │
│                          │ StoreAPI       │ StoreAPI                           │
│              ┌───────────┘                └──────────┐                         │
│              ▼                                        ▼                         │
│  ┌──────────────────────────┐           ┌──────────────────────────┐          │
│  │   THANOS SIDECAR          │           │   THANOS STORE GATEWAY   │          │
│  │   (per Prometheus)        │           │                          │          │
│  │                           │           │  - Reads blocks from     │          │
│  │  ┌─────────────────────┐ │           │    object storage        │          │
│  │  │ Prometheus          │ │           │  - Caches index locally  │          │
│  │  │ (local TSDB)        │ │           │  - Serves historical     │          │
│  │  └─────────────────────┘ │           │    queries              │          │
│  │                           │           │  - Index & chunk caching │          │
│  │  Sidecar:                 │           └─────────────┬────────────┘          │
│  │  - Proxies recent data    │                          │                      │
│  │  - Uploads blocks to      │                          ▼                      │
│  │    object storage         │           ┌──────────────────────────┐          │
│  └────────────┬──────────────┘           │   OBJECT STORAGE         │          │
│               │ upload 2h blocks         │   (S3/GCS/Azure Blob)    │          │
│               └─────────────────────────▶│                          │          │
│                                          │  - Infinite retention    │          │
│                                          │  - Cheap storage         │          │
│                                          │  - Immutable blocks      │          │
│                                          └──────────────────────────┘          │
│                                                     ▲                          │
│  ┌──────────────────────────┐                       │                          │
│  │   THANOS COMPACTOR        │───────────────────────┘                          │
│  │                           │   reads + writes compacted blocks               │
│  │  - Compacts blocks        │                                                  │
│  │  - Downsamples (5m, 1h)   │                                                  │
│  │  - Deduplicates replicas  │                                                  │
│  │  - Retention enforcement  │                                                  │
│  │  - MUST be singleton      │                                                  │
│  └───────────────────────────┘                                                  │
│                                                                                  │
│  ┌──────────────────────────┐                                                   │
│  │   THANOS RULER            │                                                   │
│  │                           │                                                   │
│  │  - Evaluates rules against│                                                   │
│  │    Thanos Query           │                                                   │
│  │  - Global alerting        │                                                   │
│  │  - Uploads rule results   │                                                   │
│  └───────────────────────────┘                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Grafana Mimir (Cortex successor)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GRAFANA MIMIR ARCHITECTURE                                 │
│                                                                              │
│  Prometheus ──remote_write──▶ ┌──────────────────────────────────────────┐  │
│  Prometheus ──remote_write──▶ │         MIMIR CLUSTER                     │  │
│  Prometheus ──remote_write──▶ │                                           │  │
│                               │  ┌─────────────────────────────────────┐ │  │
│  Write Path:                  │  │        DISTRIBUTOR                   │ │  │
│                               │  │  - Validates/rate-limits incoming    │ │  │
│                               │  │  - Hash ring → choose ingesters     │ │  │
│                               │  │  - Replication factor (default: 3)  │ │  │
│                               │  └──────────────┬──────────────────────┘ │  │
│                               │                  │                        │  │
│                               │  ┌───────────────▼─────────────────────┐ │  │
│                               │  │         INGESTER                     │ │  │
│                               │  │  - In-memory TSDB (head block)       │ │  │
│                               │  │  - WAL for durability                │ │  │
│                               │  │  - Flushes 2h blocks to storage     │ │  │
│                               │  │  - Hash ring membership             │ │  │
│                               │  └──────────────┬──────────────────────┘ │  │
│                               │                  │ flush                  │  │
│                               │                  ▼                        │  │
│                               │  ┌─────────────────────────────────────┐ │  │
│                               │  │      OBJECT STORAGE (S3/GCS)        │ │  │
│                               │  └─────────────────────────────────────┘ │  │
│                               │                  ▲                        │  │
│  Read Path:                   │                  │ read blocks           │  │
│  Grafana ──query──▶           │  ┌───────────────┴─────────────────────┐ │  │
│                               │  │      STORE-GATEWAY                   │ │  │
│                               │  │  - Lazy-loads block indexes          │ │  │
│                               │  │  - Serves chunks from object store   │ │  │
│                               │  └──────────────▲──────────────────────┘ │  │
│                               │                  │                        │  │
│                               │  ┌───────────────┴─────────────────────┐ │  │
│                               │  │         QUERIER                      │ │  │
│                               │  │  - Merges data from ingesters       │ │  │
│                               │  │    + store-gateways                 │ │  │
│                               │  │  - Deduplication                    │ │  │
│                               │  └──────────────▲──────────────────────┘ │  │
│                               │                  │                        │  │
│                               │  ┌───────────────┴─────────────────────┐ │  │
│                               │  │      QUERY-FRONTEND                  │ │  │
│                               │  │  - Query splitting (by time)         │ │  │
│                               │  │  - Results caching                  │ │  │
│                               │  │  - Query scheduling                 │ │  │
│                               │  └─────────────────────────────────────┘ │  │
│                               └──────────────────────────────────────────┘  │
│                                                                              │
│  Key Mimir advantages over Thanos:                                          │
│  - No sidecar needed (pure remote_write)                                    │
│  - Horizontally scalable all components                                     │
│  - Native multi-tenancy                                                     │
│  - Lower query latency (no sidecar hop)                                    │
│  - Simpler operations (single binary mode available)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Performance & Resource Optimization

### Memory Usage Breakdown
```
Prometheus memory consumption:

┌──────────────────────────────────────────────────────────────┐
│ Component                      │ Memory Impact               │
├────────────────────────────────┼─────────────────────────────┤
│ Head block (active series)     │ ~3-5 KB per active series   │
│ Head chunks (in-memory)        │ ~120 samples × 1.5 bytes    │
│ WAL replay buffer              │ Spikes during restart       │
│ Query evaluation               │ Depends on query complexity │
│ Scrape buffers                 │ ~10KB per target            │
│ Label index (in-memory)        │ Proportional to cardinality │
│ Postings (for head block)      │ Proportional to series      │
│ mmap'd chunks/blocks           │ OS page cache (not Go heap) │
└────────────────────────────────┴─────────────────────────────┘

Sizing formula:
  RAM ≈ (active_series × 5KB) + (scrape_targets × 10KB) + query_buffer + 1GB_base

  Example: 2 million active series
  RAM ≈ (2,000,000 × 5KB) + base = ~10GB + 1GB = ~12GB recommended

Disk calculation:
  Disk per day ≈ active_series × scrapes_per_day × 1.5 bytes_per_sample
  
  Example: 2M series, 15s scrape interval
  Samples/day = 2,000,000 × (86400/15) = 11.52 billion samples/day
  Disk/day ≈ 11.52B × 1.5 bytes ≈ 17.3 GB/day (after compression)
  
  With 15-day retention: ~260 GB disk needed
```

### Cardinality Management
```
Diagnosis queries:

# Count total active series
prometheus_tsdb_head_series

# Top 10 metrics by series count
topk(10, count by (__name__) ({__name__=~".+"}))

# Series count per job
count by (job) ({__name__=~".+"})

# Metrics with most label combinations
# Use /api/v1/status/tsdb endpoint for cardinality stats

Mitigation strategies:
1. Drop high-cardinality labels (metric_relabel_configs)
2. Limit scrape targets (relabel_configs drop)
3. Use recording rules for pre-aggregation
4. Reduce histogram bucket count
5. Increase scrape_interval for non-critical targets
6. Use exemplars instead of high-cardinality labels
```

---

## Production Deployment Patterns

### Kubernetes Deployment (Prometheus Operator)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              PRODUCTION KUBERNETES MONITORING STACK                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    kube-prometheus-stack                              │    │
│  │                                                                       │    │
│  │  ┌───────────────────────────────────────────────────────────────┐   │    │
│  │  │  Prometheus Operator (manages CRDs)                            │   │    │
│  │  │  - Prometheus (StatefulSet per Prometheus CR)                  │   │    │
│  │  │  - ServiceMonitor (declares scrape targets)                   │   │    │
│  │  │  - PodMonitor (pod-level scraping)                            │   │    │
│  │  │  - PrometheusRule (alerting/recording rules)                  │   │    │
│  │  │  - Alertmanager (manages Alertmanager clusters)               │   │    │
│  │  └───────────────────────────────────────────────────────────────┘   │    │
│  │                                                                       │    │
│  │  ┌────────────────────┐  ┌────────────────────┐                     │    │
│  │  │ Prometheus         │  │ Prometheus         │  ← HA pair          │    │
│  │  │ Replica 0          │  │ Replica 1          │  (identical config) │    │
│  │  │ (StatefulSet)      │  │ (StatefulSet)      │                     │    │
│  │  │                    │  │                    │                     │    │
│  │  │ PVC: 200Gi SSD    │  │ PVC: 200Gi SSD    │                     │    │
│  │  │ CPU: 4 cores      │  │ CPU: 4 cores      │                     │    │
│  │  │ RAM: 16Gi         │  │ RAM: 16Gi         │                     │    │
│  │  └─────────┬──────────┘  └────────┬───────────┘                     │    │
│  │            │ remote_write          │ remote_write                    │    │
│  │            └───────────┬───────────┘                                 │    │
│  │                        ▼                                              │    │
│  │  ┌────────────────────────────────────────────────┐                  │    │
│  │  │  Thanos Receive / Mimir / VictoriaMetrics      │                  │    │
│  │  │  (Long-term storage + Global view)             │                  │    │
│  │  └────────────────────────────────────────────────┘                  │    │
│  │                                                                       │    │
│  │  ┌────────────────────┐  ┌────────────────────┐                     │    │
│  │  │ Alertmanager       │  │ Alertmanager       │                     │    │
│  │  │ Replica 0          │  │ Replica 1          │  ← HA cluster       │    │
│  │  │ (gossip protocol)  │  │ (gossip protocol)  │                     │    │
│  │  └────────────────────┘  └────────────────────┘                     │    │
│  │                                                                       │    │
│  │  Exporters:                                                           │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐    │    │
│  │  │ node-exporter│ │kube-state-   │ │ cAdvisor (kubelet)       │    │    │
│  │  │ (DaemonSet)  │ │metrics       │ │ (built into kubelet)     │    │    │
│  │  └──────────────┘ └──────────────┘ └──────────────────────────┘    │    │
│  │                                                                       │    │
│  │  ┌────────────────────────────────────────────────────────────────┐  │    │
│  │  │ Grafana (Dashboards)                                            │  │    │
│  │  │ - Pre-built dashboards for K8s, node, pods                     │  │    │
│  │  │ - Custom application dashboards                                 │  │    │
│  │  └────────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sizing Guidelines
```
┌─────────────────────────────────────────────────────────────────┐
│ Scale Tier    │ Series    │ Targets │ CPU  │ RAM   │ Disk      │
├───────────────┼───────────┼─────────┼──────┼───────┼───────────┤
│ Small         │ < 500K    │ < 500   │ 2    │ 8 GB  │ 100 GB    │
│ Medium        │ 500K-2M   │ 500-2K  │ 4    │ 16 GB │ 300 GB    │
│ Large         │ 2M-5M    │ 2K-5K  │ 8    │ 32 GB │ 500 GB    │
│ Very Large    │ 5M-10M   │ 5K-10K │ 16   │ 64 GB │ 1 TB      │
│ Beyond        │ > 10M    │ > 10K  │ Shard or use Mimir/Thanos │
└───────────────┴───────────┴─────────┴──────┴───────┴───────────┘

Key configuration:
storage:
  tsdb:
    retention.time: 15d         # Time-based retention
    retention.size: 200GB       # Size-based retention (use one)
    wal-compression: true       # 50% WAL size reduction
    min-block-duration: 2h      # Head compaction interval
    max-block-duration: 36h     # Max block size

scrape_interval: 15s            # Global default (don't go below 10s)
evaluation_interval: 15s        # Rule evaluation frequency
```

---

## Monitoring Prometheus Itself

### Key Internal Metrics
```
Critical metrics to alert on:

# Scrape health
prometheus_target_scrape_pool_targets          # Expected targets
prometheus_target_scrape_pools_failed_total     # SD failures
up                                              # Target reachability

# TSDB health
prometheus_tsdb_head_series                    # Active series count
prometheus_tsdb_head_chunks                    # In-memory chunks
prometheus_tsdb_compactions_failed_total        # Compaction failures
prometheus_tsdb_wal_corruptions_total           # WAL corruption
prometheus_tsdb_reloads_failures_total          # Config reload failures

# Resource pressure
process_resident_memory_bytes                   # RSS memory
prometheus_tsdb_head_gc_duration_seconds        # GC pauses
prometheus_engine_query_duration_seconds        # Query latency
prometheus_rule_evaluation_duration_seconds     # Rule eval time

# Remote write health
prometheus_remote_storage_samples_pending       # Queue depth
prometheus_remote_storage_samples_failed_total  # Write failures
prometheus_remote_storage_samples_dropped_total # Dropped samples
prometheus_remote_storage_bytes_total           # Bandwidth

# Alerting
prometheus_rule_group_iterations_missed_total   # Missed evaluations
prometheus_notifications_errors_total           # Alertmanager send failures
prometheus_notifications_dropped_total          # Dropped notifications
```

---

## Security & Multi-tenancy

### Security Configuration
```
# TLS for scraping
scrape_configs:
  - job_name: 'secure-app'
    scheme: https
    tls_config:
      ca_file: /etc/prometheus/ca.pem
      cert_file: /etc/prometheus/cert.pem
      key_file: /etc/prometheus/key.pem
      insecure_skip_verify: false

# TLS for Prometheus HTTP server (web.yml)
tls_server_config:
  cert_file: /etc/prometheus/server.crt
  key_file: /etc/prometheus/server.key
  client_auth_type: RequireAndVerifyClientCert
  client_ca_file: /etc/prometheus/ca.crt

# Basic auth for HTTP API
basic_auth_users:
  admin: $2y$12$...  # bcrypt hash

# Multi-tenancy approaches:
# 1. Separate Prometheus per tenant (simple, resource wasteful)
# 2. Label-based isolation (external_labels + query filtering)
# 3. Mimir/Cortex native multi-tenancy (X-Scope-OrgID header)
# 4. Thanos multi-tenancy (limited, label-based)
```

---

## Use Case Architectures

### Microservices Monitoring
```
┌─────────────────────────────────────────────────────────────────┐
│             MICROSERVICES MONITORING WITH PROMETHEUS              │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Application Layer (instrumented with client libraries)   │    │
│  │                                                          │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐  │    │
│  │  │ Service │ │ Service │ │ Service │ │ Service     │  │    │
│  │  │   A     │ │   B     │ │   C     │ │   D        │  │    │
│  │  │/metrics │ │/metrics │ │/metrics │ │/metrics    │  │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  RED Method metrics per service:                                 │
│  - Rate: requests per second                                     │
│  - Errors: error rate / error ratio                              │
│  - Duration: latency percentiles (p50, p95, p99)                │
│                                                                   │
│  USE Method metrics per resource:                                │
│  - Utilization: CPU%, memory%, disk%                             │
│  - Saturation: queue depth, thread pool exhaustion               │
│  - Errors: hardware errors, connection failures                  │
│                                                                   │
│  Four Golden Signals (Google SRE):                               │
│  - Latency, Traffic, Errors, Saturation                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: How does Prometheus handle high availability without built-in clustering?
```
Answer:
Prometheus itself has no clustering. HA is achieved through:

1. Replica pairs: Two identical Prometheus scraping same targets
   - Both collect same data independently
   - Small timestamp differences between replicas
   - Grafana queries either (no dedup needed for dashboards)
   - Alertmanager clusters handle alert deduplication

2. Long-term storage deduplication:
   - Thanos: Compactor deduplicates replica data in object storage
   - Mimir: Distributor replicates to N ingesters, querier deduplicates
   
3. Alerting HA:
   - Both Prometheus send alerts to Alertmanager cluster
   - Alertmanager gossip protocol deduplicates notifications
   - group_wait ensures only one notification per group

Trade-offs:
- Simple (no consensus protocol needed)
- Double resource usage
- Small gaps possible during rolling restarts
- No global query without Thanos/Mimir
```

### Q2: Explain cardinality explosion and how to prevent it
```
Answer:
Cardinality explosion = exponential growth of time series from label combinations.

Root causes:
- Unbounded label values (user IDs, request IDs)
- Too many histogram buckets × high-cardinality labels
- Auto-generated labels from service meshes
- Uncontrolled metric naming conventions

Impact:
- Memory OOM (head block grows linearly with series)
- Slow queries (more postings to intersect)
- Slow compaction (more data to merge)
- WAL replay takes longer on restart

Prevention:
1. Governance: Metric naming + labeling standards
2. Limits: --storage.tsdb.max-block-bytes, sample_limit per scrape
3. Relabeling: Drop unnecessary labels/metrics
4. Recording rules: Pre-aggregate before querying
5. Tooling: Use prom-label-proxy, mimirtool analyze
6. Alerting: Alert on prometheus_tsdb_head_series growth rate
```

### Q3: Compare Thanos vs Mimir for long-term storage
```
Answer:
┌─────────────────────┬──────────────────────┬──────────────────────┐
│ Aspect              │ Thanos               │ Mimir                │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ Architecture        │ Sidecar + components │ Pure remote_write    │
│ Data flow           │ Pull (sidecar upload)│ Push (remote_write)  │
│ Query path          │ Fan-out to stores    │ Query-frontend split │
│ Multi-tenancy       │ Label-based only     │ Native (header)      │
│ Operational         │ Many components      │ Single binary option │
│ Deduplication       │ Compactor (offline)  │ Querier (online)     │
│ Query caching       │ Query-frontend       │ Query-frontend       │
│ Downsampling        │ Yes (5m, 1h)         │ No (query-time)      │
│ Maturity            │ CNCF Incubating      │ Grafana Labs (OSS)   │
│ Best for            │ Existing Prometheus  │ New deployments      │
│ Partial responses   │ Yes                  │ Yes                  │
└─────────────────────┴──────────────────────┴──────────────────────┘
```

### Q4: How does the TSDB handle out-of-order samples?
```
Answer:
Historically, Prometheus rejected out-of-order samples. Since v2.39+:

Out-of-order ingestion support:
- Enabled via: --storage.tsdb.out-of-order-time-window=30m
- Maintains separate in-memory "OOO" head alongside regular head
- OOO samples written to separate WAL segment
- During compaction, OOO data merged with regular blocks

Why it matters:
- Remote write retries can deliver samples out of order
- Multi-replica setups with clock skew
- Batch ingestion of historical data
- Agent mode buffering during network issues

Implementation:
- OOO head uses WBL (Write Behind Log) for persistence
- Memory overhead: additional series references
- Query path merges OOO chunks with regular chunks
- Compactor creates unified blocks
```

### Q5: Design a monitoring architecture for 10,000 microservices across 5 regions
```
Answer:
Architecture:
- Per-region: 3 Prometheus pairs (sharded by hashmod on __address__)
- Each Prometheus: ~3.3M series (10K services × ~1000 series/service ÷ 3 shards)
- Remote write to regional Mimir cluster
- Global Mimir query federation across regions

Components per region:
- 6 Prometheus (3 shards × 2 replicas)
- 1 Mimir cluster (3 ingesters, 2 distributors, 2 queriers, 1 compactor)
- 3 Alertmanager cluster nodes
- Object storage (S3/GCS)

Global layer:
- Query federation across 5 regional Mimir clusters
- Global Grafana with multi-datasource
- Cross-region alerting via Mimir ruler

Total series: ~10K × 1000 = 10M per region, 50M globally
Storage: ~50M × 86400/15 × 1.5B ≈ 430 GB/day globally
```

### Q6-Q10: Additional Questions
```
Q6: How does rate() handle counter resets?
- Detects decrease in counter value
- Assumes reset to 0 at that point
- Adjusts calculation: adds pre-reset value to post-reset values
- extrapolation at boundaries of the range

Q7: Explain the WAL and its role in crash recovery
- Sequential append-only log (128MB segments)
- Records: series creation + sample appends
- On crash: head block rebuilt from WAL replay
- Checkpoint: periodic WAL truncation (keeps last 2/3)
- wal-compression reduces size by ~50%

Q8: What are exemplars and how do they bridge metrics and traces?
- Exemplars: sample metadata attached to a histogram observation
- Contains: traceID, spanID (or custom labels)
- Storage: separate from TSDB main storage
- Query: via /api/v1/query_exemplars
- Use: Click point on graph → jump to trace
- Cardinality: not indexed as labels (safe)

Q9: How would you migrate from Prometheus to VictoriaMetrics?
- Phase 1: Deploy VM, configure Prometheus remote_write to VM
- Phase 2: Point Grafana to VM as datasource (parallel)
- Phase 3: Migrate historical data (vmctl)
- Phase 4: Switch alerting to VM (vmalert)
- Phase 5: Decommission Prometheus
- Considerations: MetricsQL differences, retention policies

Q10: Explain Prometheus Agent mode
- Lightweight mode: scrapes + remote_writes only
- No local TSDB, no queries, no alerting
- Designed for edge/IoT where central query not needed
- Lower resource usage (no head block)
- WAL-only for buffering before remote_write
- Use case: Kubernetes DaemonSet at edge locations
```

---

## Scenario-Based Questions

### Scenario 1: Prometheus OOM crashes every few days
```
Diagnosis:
1. Check prometheus_tsdb_head_series - is it growing?
2. Check for cardinality explosion: topk(10, count by (__name__)({__name__=~".+"}))
3. Check scrape targets: are new services adding uncontrolled metrics?
4. Check query patterns: expensive queries using lots of memory?

Resolution:
- Immediate: Increase memory limits
- Short-term: Add sample_limit to scrape configs, drop expensive metrics
- Medium-term: Implement cardinality governance, recording rules
- Long-term: Shard Prometheus or move to Mimir
```

### Scenario 2: Alerts not firing during an incident
```
Diagnosis path:
1. Is Prometheus scraping the target? Check up{job="..."} 
2. Is the metric being collected? Query raw metric
3. Does the alert expression evaluate to true? Test in UI
4. Is the "for" duration met? Check PENDING state
5. Is Alertmanager receiving? Check prometheus_notifications_sent_total
6. Is Alertmanager routing correctly? Check amtool
7. Is the alert silenced or inhibited? Check Alertmanager UI

Common causes:
- "for" clause too long (5m means 5 min of continuous firing)
- Label mismatch in routing
- Inhibition rule suppressing the alert
- Alertmanager cluster split-brain
- Network partition between Prom and Alertmanager
```

### Scenario 3: Dashboard queries taking 30+ seconds
```
Optimization steps:
1. Check query complexity: nested subqueries, high-cardinality selectors
2. Use recording rules for dashboard queries
3. Check time range: 7-day queries scan more blocks
4. Check block count: excessive blocks = compaction lag
5. Add more specific label matchers (reduce series scanned)
6. Use query_log to find expensive queries
7. Consider Thanos query-frontend for caching + splitting

Architecture change:
- Add query-frontend with results caching
- Use Grafana's $__rate_interval instead of hardcoded ranges
- Implement tiered dashboards (overview → detail on drill-down)
```

### Scenario 4: Remote write falling behind
```
Indicators:
- prometheus_remote_storage_samples_pending increasing
- prometheus_remote_storage_highest_timestamp_in_seconds lagging

Tuning:
remote_write:
  - url: "..."
    queue_config:
      max_shards: 200          # Increase parallelism
      max_samples_per_send: 5000
      capacity: 50000          # Larger buffer
      batch_send_deadline: 10s

Other fixes:
- Check network bandwidth to remote storage
- Check remote storage ingestion capacity
- Filter with write_relabel_configs (send only what's needed)
- Enable compression (send_compressed: true by default in v2.x)
- Consider multiple remote_write endpoints for load distribution
```

### Scenario 5: Migrating 500 microservices to Prometheus from Datadog
```
Migration plan:
Phase 1 - Instrumentation (4 weeks):
  - Add Prometheus client libraries to services
  - Expose /metrics endpoints (RED method metrics)
  - Use OpenTelemetry SDK for dual export (Datadog + Prometheus)

Phase 2 - Infrastructure (2 weeks):
  - Deploy Prometheus Operator in K8s
  - Configure ServiceMonitors for each service
  - Set up Alertmanager with existing notification channels
  - Deploy Grafana with dashboard provisioning

Phase 3 - Parallel Run (4 weeks):
  - Both systems active simultaneously
  - Compare data accuracy between systems
  - Migrate dashboards from Datadog to Grafana
  - Migrate alert definitions to PrometheusRules

Phase 4 - Cutover (2 weeks):
  - Switch primary alerting to Prometheus
  - Keep Datadog as backup for 2 weeks
  - Final validation
  - Decommission Datadog agents

Cost savings: Datadog ~$15-23/host/month → Prometheus $0 (compute costs only)
For 500 services × 3 instances = 1500 hosts × $20 = $30K/month saved
```
