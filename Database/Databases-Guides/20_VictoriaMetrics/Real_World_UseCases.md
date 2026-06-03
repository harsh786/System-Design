# VictoriaMetrics - Real World Use Cases & Production Guide

## Table of Contents
- [Core Concepts](#core-concepts)
- [Real-World Use Cases](#real-world-use-cases)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)

---

## Core Concepts

### Merge Tree Storage Engine

VictoriaMetrics uses a custom storage engine optimized for time series data:

```
┌─────────────────────────────────────────────────────┐
│                   Write Path                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Incoming Samples                                   │
│       │                                             │
│       ▼                                             │
│  ┌──────────┐    ┌──────────────┐                   │
│  │ In-Memory │───▶│  Merge Tree  │                   │
│  │  Buffer   │    │   (Parts)    │                   │
│  └──────────┘    └──────┬───────┘                   │
│                         │                           │
│                         ▼                           │
│              ┌─────────────────────┐                │
│              │   Immutable Parts   │                │
│              │  (Sorted by TSID)   │                │
│              └─────────┬───────────┘                │
│                        │                            │
│                        ▼                            │
│              ┌─────────────────────┐                │
│              │  Background Merge   │                │
│              │  (Compaction)       │                │
│              └─────────────────────┘                │
└─────────────────────────────────────────────────────┘
```

**Key Design Principles:**
- Data is organized by **TSID** (Time Series ID) - a unique hash of metric name + labels
- Parts are immutable once written (append-only)
- Background merges compact small parts into larger ones
- Each part stores: timestamps[], values[], and TSID index

### Inverted Index for Label Lookups

```
┌─────────────────────────────────────────────────┐
│              Inverted Index (indexdb)            │
├─────────────────────────────────────────────────┤
│                                                 │
│  Label → TSID Mapping:                          │
│                                                 │
│  __name__=http_requests ──▶ [TSID1, TSID2, ..]│
│  job=api-server          ──▶ [TSID1, TSID3, ..]│
│  instance=10.0.1.5:9090  ──▶ [TSID2, TSID4, ..]│
│  status=200              ──▶ [TSID1, TSID5, ..]│
│                                                 │
│  Composite Index:                               │
│  __name__=http_requests + job=api ──▶ [TSID1]  │
│                                                 │
│  Storage: mergeset (LSM-like structure)         │
│  Rotation: per-day or per-retention-period      │
└─────────────────────────────────────────────────┘
```

### Compression Algorithm

```
┌──────────────────────────────────────────────────────┐
│            Compression Strategy                       │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Timestamps:                                         │
│  ┌───────────────────────────────────────────┐       │
│  │ Delta-of-delta encoding                   │       │
│  │ t1=1000, t2=1015, t3=1030, t4=1045       │       │
│  │ deltas: 15, 15, 15                        │       │
│  │ delta-of-deltas: 0, 0, 0 → near-zero bits│       │
│  └───────────────────────────────────────────┘       │
│                                                      │
│  Values:                                             │
│  ┌───────────────────────────────────────────┐       │
│  │ XOR encoding (Gorilla-style) +            │       │
│  │ Custom ZSTD-like compression              │       │
│  │ Similar consecutive values → minimal bits │       │
│  └───────────────────────────────────────────┘       │
│                                                      │
│  Result: 0.4-0.8 bytes per data point               │
│  (vs Prometheus ~1.3 bytes/point)                    │
└──────────────────────────────────────────────────────┘
```

### Storage Efficiency: VictoriaMetrics vs Prometheus

| Metric                    | VictoriaMetrics | Prometheus | Improvement |
|---------------------------|-----------------|------------|-------------|
| Bytes per data point      | 0.4 - 0.8      | 1.3 - 1.5  | ~2x less    |
| RAM per active series     | ~1 KB           | ~3-4 KB    | ~3x less    |
| Query latency (1M series) | 50-200ms       | 500ms-2s   | ~5x faster  |
| Disk IOPS on ingestion    | Low (sequential)| Higher     | ~3x less    |
| Compaction overhead       | Minimal         | Significant| ~4x less    |

### MetricsQL (Superset of PromQL)

```
# Standard PromQL works as-is:
rate(http_requests_total[5m])

# MetricsQL extensions:

# 1. range_median - more stable than rate for spiky metrics
range_median(http_requests_total[5m])

# 2. rollup functions with implicit lookbehind
http_requests_total   # auto-selects appropriate range

# 3. keep_metric_names - preserves metric name after transform
rate(http_requests_total[5m]) keep_metric_names

# 4. label_set / label_del / label_copy
label_set(up, "env", "prod")

# 5. Subqueries with variable step
rate(http_requests_total[5m])[1h:30s]

# 6. WITH templates (CTE-like)
WITH (
  rps = rate(http_requests_total[5m])
)
rps > 1000

# 7. Limit/sort functions
topk_avg(10, rate(http_requests_total[5m]))
bottomk_last(5, node_memory_available_bytes)
```

### Active Time Series and Cardinality

```
Active Time Series = unique combinations of (metric_name + all_label_values)

Example cardinality explosion:
  http_requests_total{method, endpoint, status, instance, pod}
  
  methods: 4 × endpoints: 500 × statuses: 5 × instances: 100 × pods: 300
  = 300,000,000 potential series (CARDINALITY BOMB!)

VictoriaMetrics handles high cardinality better than Prometheus:
- No 5M series limit (configurable)
- Faster indexdb lookups
- Lower per-series memory overhead
```

### Write Path and Query Path

```
┌───────────────────────────────────────────────────────────┐
│                      WRITE PATH                            │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Prometheus/vmagent                                       │
│       │                                                   │
│       │ remote_write / InfluxDB line protocol              │
│       ▼                                                   │
│  ┌──────────┐     ┌─────────────┐     ┌──────────────┐   │
│  │ vminsert │────▶│  vmstorage  │────▶│  Disk (data  │   │
│  │ (router) │     │  (accepts)  │     │  + indexdb)  │   │
│  └──────────┘     └─────────────┘     └──────────────┘   │
│       │                                                   │
│       │ Consistent hashing by time series ID              │
│       ▼                                                   │
│  Routes to correct vmstorage node                         │
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│                      QUERY PATH                            │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Grafana / API client                                     │
│       │                                                   │
│       │ MetricsQL query                                   │
│       ▼                                                   │
│  ┌──────────┐     ┌─────────────┐     ┌──────────────┐   │
│  │ vmselect │────▶│  vmstorage  │────▶│  Read from   │   │
│  │ (query)  │     │  (serves)   │     │  disk/cache  │   │
│  └──────────┘     └─────────────┘     └──────────────┘   │
│       │                                                   │
│       │ Scatter-gather: query ALL vmstorage nodes         │
│       │ Merge + deduplicate results                       │
│       ▼                                                   │
│  Return aggregated result                                 │
└───────────────────────────────────────────────────────────┘
```

### Downsampling Strategies

```
┌─────────────────────────────────────────────────────────┐
│              Downsampling Options                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. -downsampling.period (Enterprise)                   │
│     Raw data (0-7d) → 1min avg (7-30d) → 5min (30d+)  │
│                                                         │
│  2. Recording Rules (via vmalert)                       │
│     rule: record: job:http_requests:rate5m              │
│           expr: sum(rate(http_requests_total[5m])) by   │
│                                                         │
│  3. Stream Aggregation (vmagent)                        │
│     Aggregate before ingestion:                         │
│     - sum, avg, min, max, count, quantiles             │
│     - Reduces cardinality at source                     │
│                                                         │
│  Timeline:                                              │
│  ├── Raw (15s) ──┤── 1min ──┤── 5min ──┤── 1hr ──┤    │
│  0d              7d         30d        90d      365d    │
└─────────────────────────────────────────────────────────┘
```

---

## Real-World Use Cases

---

### 1. Adidas - Global Infrastructure Monitoring

**Context:** Adidas monitors its global e-commerce infrastructure, microservices, and retail systems across multiple cloud regions. During product launches (e.g., Yeezy drops), traffic spikes 100x.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Adidas Global Monitoring                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │
│  │  EU DC  │  │  US DC  │  │ APAC DC │  │  K8s    │               │
│  │ Prom    │  │ Prom    │  │ Prom    │  │ Prom    │               │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘               │
│       │             │            │             │                     │
│       │      remote_write (protobuf/snappy)    │                     │
│       │             │            │             │                     │
│       ▼             ▼            ▼             ▼                     │
│  ┌──────────────────────────────────────────────────┐               │
│  │                  vmagent (HA pair)                │               │
│  │    Relabeling, filtering, dedup, fan-out         │               │
│  └───────────────────────┬──────────────────────────┘               │
│                          │                                          │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────┐               │
│  │            VictoriaMetrics Cluster                │               │
│  │                                                  │               │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │               │
│  │  │vminsert-1│  │vminsert-2│  │vminsert-3│       │               │
│  │  └─────┬────┘  └─────┬────┘  └────┬─────┘       │               │
│  │        │              │            │             │               │
│  │        ▼              ▼            ▼             │               │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │               │
│  │  │vmstorage1│  │vmstorage2│  │vmstorage3│       │               │
│  │  │  (4TB)   │  │  (4TB)   │  │  (4TB)   │       │               │
│  │  └──────────┘  └──────────┘  └──────────┘       │               │
│  │        │              │            │             │               │
│  │        ▼              ▼            ▼             │               │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │               │
│  │  │vmselect-1│  │vmselect-2│  │vmselect-3│       │               │
│  │  └──────────┘  └──────────┘  └──────────┘       │               │
│  └──────────────────────────────────────────────────┘               │
│                          │                                          │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────┐               │
│  │  Grafana (dashboards) + vmalert (alerting)       │               │
│  └──────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

#### Data Model

```
# E-commerce metrics
http_request_duration_seconds{
  service="checkout",
  region="eu-west-1",
  method="POST",
  endpoint="/api/cart/add",
  status="200",
  pod="checkout-7b4f9-xk2m"
} 0.045 1698765432

# Infrastructure metrics
node_cpu_seconds_total{
  instance="worker-eu-042.adidas.internal:9100",
  cpu="0",
  mode="user",
  datacenter="eu-frankfurt",
  team="platform"
} 845632.12 1698765432

# Business metrics
product_page_views_total{
  product_id="yeezy-350-v2",
  region="us-east",
  channel="mobile-app"
} 4523891 1698765432
```

#### Ingestion Protocol

- **Prometheus remote_write** (primary) - from regional Prometheus servers
- **vmagent** as relay with `-remoteWrite.tmpDataPath` for buffering during network issues
- Relabeling in vmagent to drop high-cardinality labels before storage

#### MetricsQL Queries

```sql
# P99 latency per service during product launch
histogram_quantile(0.99, 
  sum(rate(http_request_duration_seconds_bucket{
    service="checkout"
  }[5m])) by (le, region)
)

# Error rate spike detection
(
  sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
  /
  sum(rate(http_requests_total[5m])) by (service)
) > 0.01

# Capacity planning: growth rate of active series
vm_new_timeseries_created_total[1h]

# Compare current traffic vs last Yeezy drop
http_requests_total offset 90d
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Active time series | ~50M |
| Ingestion rate | ~3M samples/sec |
| Storage (1 year retention) | ~12 TB compressed |
| Data points per day | ~260B |
| Query latency P95 | <200ms |
| Regions monitored | 4 |

---

### 2. Roblox - Gaming Platform Metrics

**Context:** Roblox serves 50M+ daily active users across millions of game servers. Each game server emits performance metrics (FPS, physics step time, network latency, player count). The challenge: extreme scale with low-latency queries for live game health.

#### Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                    Roblox Metrics Pipeline                             │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         ┌──────────┐         │
│  │Game Srv 1│ │Game Srv 2│ │...       │  ...     │Game Srv N│         │
│  │(Lua SDK) │ │(Lua SDK) │ │          │         │(millions)│         │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘         └────┬─────┘         │
│       │             │            │                    │               │
│       │  UDP/Custom binary protocol (batched)         │               │
│       ▼             ▼            ▼                    ▼               │
│  ┌────────────────────────────────────────────────────────┐           │
│  │           Metrics Aggregation Layer                     │           │
│  │      (Pre-aggregates per game_id, region)              │           │
│  │      Reduces cardinality before VM ingestion           │           │
│  └────────────────────────┬───────────────────────────────┘           │
│                           │                                           │
│                           │ InfluxDB line protocol (HTTP)              │
│                           ▼                                           │
│  ┌────────────────────────────────────────────────────────┐           │
│  │              VictoriaMetrics Cluster                    │           │
│  │                                                        │           │
│  │  vminsert (x10)                                        │           │
│  │      │                                                 │           │
│  │      ▼                                                 │           │
│  │  vmstorage (x30 nodes, 8TB NVMe each)                  │           │
│  │      │                                                 │           │
│  │      ▼                                                 │           │
│  │  vmselect (x15, high memory for large queries)         │           │
│  │                                                        │           │
│  └───────────────────────┬────────────────────────────────┘           │
│                          │                                            │
│              ┌───────────┼───────────┐                                │
│              ▼           ▼           ▼                                │
│  ┌──────────────┐ ┌──────────┐ ┌─────────────┐                       │
│  │  Grafana     │ │ vmalert  │ │ Internal    │                       │
│  │  (Live Ops)  │ │ (alerts) │ │ Dashboards  │                       │
│  └──────────────┘ └──────────┘ └─────────────┘                       │
└───────────────────────────────────────────────────────────────────────┘
```

#### Data Model

```
# Game server performance
game_server_fps{
  game_id="5846382910",
  place_version="442",
  server_id="gs-us-east-28a91f",
  region="us-east",
  player_count_bucket="20-30"
} 59.8 1698765432

# Player experience
game_player_latency_ms{
  game_id="5846382910",
  region="eu-west",
  connection_type="wifi"
} 45 1698765432

# Physics engine
game_physics_step_time_ms{
  game_id="5846382910",
  server_id="gs-us-east-28a91f",
  complexity="high"
} 12.3 1698765432

# Matchmaking
matchmaking_queue_size{
  game_id="5846382910",
  region="us-east",
  skill_bracket="gold"
} 342 1698765432
```

#### Ingestion Protocol

- **InfluxDB line protocol** (HTTP) - chosen for simplicity from custom aggregation layer
- Binary UDP from game servers → aggregation layer (custom)
- Stream aggregation in vmagent to pre-compute per-game rollups

#### MetricsQL Queries

```sql
# Average FPS across all servers for a game
avg(game_server_fps{game_id="5846382910"}) by (region)

# Games with degraded performance (FPS < 30)
count(game_server_fps < 30) by (game_id)
  | sort_desc()
  | limit 20

# Player latency P95 by region
histogram_quantile(0.95,
  sum(rate(game_player_latency_ms_bucket[5m])) by (le, region)
)

# Concurrent players trend (using recording rule output)
sum(game_server_player_count) by (region)

# Anomaly detection: sudden FPS drop
(
  avg_over_time(game_server_fps{game_id="5846382910"}[5m])
  < 
  avg_over_time(game_server_fps{game_id="5846382910"}[1h] offset 5m) * 0.7
)
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Active time series | ~200M |
| Ingestion rate | ~15M samples/sec |
| Storage (90-day retention) | ~50 TB compressed |
| Game servers emitting | ~2M simultaneous |
| vmstorage nodes | 30 |
| Query latency P95 | <500ms |

---

### 3. Grammarly - Real-time Application Monitoring

**Context:** Grammarly processes billions of text suggestions daily for 30M+ users. Monitoring covers ML inference latency, NLP pipeline performance, and infrastructure health. Key requirement: sub-second alerting on ML model degradation.

#### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                  Grammarly Observability Stack                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │  ML Infer │  │  NLP Pipe │  │   API GW  │  │  Browser  │    │
│  │  Services │  │  Services │  │  Services │  │ Extension │    │
│  │(Prometheus│  │(StatsD)   │  │(Prometheus│  │(custom)   │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        │               │              │              │           │
│        ▼               ▼              ▼              ▼           │
│  ┌───────────────────────────────────────────────────────┐       │
│  │              vmagent (per-K8s-cluster)                 │       │
│  │  - Scrapes Prometheus endpoints                       │       │
│  │  - Receives StatsD via statsd_exporter               │       │
│  │  - Stream aggregation for high-cardinality metrics    │       │
│  └──────────────────────┬────────────────────────────────┘       │
│                         │                                        │
│                         │  remote_write (HA pair)                 │
│                         ▼                                        │
│  ┌───────────────────────────────────────────────────────┐       │
│  │          VictoriaMetrics Cluster (Multi-AZ)           │       │
│  │                                                       │       │
│  │  vminsert (x4, behind LB)                             │       │
│  │       │                                               │       │
│  │       ▼                                               │       │
│  │  vmstorage (x6, 2TB NVMe, replicationFactor=2)       │       │
│  │       │                                               │       │
│  │       ▼                                               │       │
│  │  vmselect (x6, 64GB RAM each for large queries)      │       │
│  └──────────────────────┬────────────────────────────────┘       │
│                         │                                        │
│              ┌──────────┼──────────┐                             │
│              ▼          ▼          ▼                             │
│  ┌──────────────┐ ┌─────────┐ ┌──────────┐                      │
│  │   Grafana    │ │ vmalert │ │ Internal │                      │
│  │ (ML + Infra) │ │  (15s)  │ │   API    │                      │
│  └──────────────┘ └────┬────┘ └──────────┘                      │
│                         │                                        │
│                         ▼                                        │
│              ┌─────────────────┐                                 │
│              │  PagerDuty /    │                                 │
│              │  Slack alerts   │                                 │
│              └─────────────────┘                                 │
└──────────────────────────────────────────────────────────────────┘
```

#### Data Model

```
# ML inference latency
ml_inference_duration_seconds{
  model="grammar_check_v3",
  model_version="3.2.1",
  language="en",
  input_length_bucket="100-500",
  gpu_type="a100",
  instance="ml-node-12"
} 0.023 1698765432

# Suggestion quality
suggestion_accepted_total{
  suggestion_type="grammar",
  confidence_bucket="0.9-1.0",
  user_tier="premium",
  platform="chrome_extension"
} 892341 1698765432

# NLP pipeline stages
nlp_pipeline_stage_duration_seconds{
  stage="tokenization",
  language="en",
  batch_size="32"
} 0.003 1698765432

# Real-time user experience
editor_keystroke_to_suggestion_ms{
  platform="web",
  region="us-east",
  p_quantile="0.95"
} 180 1698765432
```

#### Ingestion Protocol

- **Prometheus remote_write** - primary path from vmagent
- StatsD → statsd_exporter → vmagent scrape
- Custom SDK → OpenTelemetry Collector → remote_write for browser metrics

#### MetricsQL Queries

```sql
# ML model latency P99 by version (catch regressions)
histogram_quantile(0.99,
  sum(rate(ml_inference_duration_seconds_bucket{
    model="grammar_check_v3"
  }[5m])) by (le, model_version)
)

# Suggestion acceptance rate (quality signal)
sum(rate(suggestion_accepted_total[1h])) by (suggestion_type)
/
sum(rate(suggestion_shown_total[1h])) by (suggestion_type)

# GPU utilization vs inference latency correlation
# (displayed as dual-axis Grafana panel)
avg(nvidia_gpu_utilization{}) by (instance)

# Alert: inference latency spike
WITH (
  p99 = histogram_quantile(0.99, 
    sum(rate(ml_inference_duration_seconds_bucket[5m])) by (le, model))
)
p99 > 0.5  # Alert if P99 > 500ms

# Cardinality check
count(ml_inference_duration_seconds) by (model)
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Active time series | ~30M |
| Ingestion rate | ~2M samples/sec |
| Storage (6-month retention) | ~8 TB compressed |
| ML models monitored | ~50 |
| Alert evaluation interval | 15 seconds |
| Query latency P95 | <150ms |

---

### 4. Wix.com - Website Platform Monitoring

**Context:** Wix hosts 200M+ websites. Each site generates performance metrics (Core Web Vitals, uptime, CDN cache hit ratio). The platform itself runs thousands of microservices. Challenge: monitoring both platform health AND per-customer site metrics.

#### Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                    Wix Monitoring Architecture                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  CUSTOMER-FACING METRICS              PLATFORM METRICS                 │
│                                                                        │
│  ┌──────────────┐                    ┌──────────────────┐              │
│  │  RUM Agent   │                    │  K8s Clusters    │              │
│  │  (browsers)  │                    │  (2000+ nodes)   │              │
│  └──────┬───────┘                    └────────┬─────────┘              │
│         │                                     │                        │
│         ▼                                     ▼                        │
│  ┌──────────────┐                    ┌──────────────────┐              │
│  │  Edge Agg    │                    │  vmagent (per    │              │
│  │  (CDN PoPs)  │                    │  cluster, HA)    │              │
│  │  pre-agg by  │                    │                  │              │
│  │  site_id     │                    │  Scrape + stream │              │
│  └──────┬───────┘                    │  aggregation     │              │
│         │                            └────────┬─────────┘              │
│         │ OpenTSDB format                     │ remote_write           │
│         │                                     │                        │
│         ▼                                     ▼                        │
│  ┌─────────────────────────────────────────────────────────┐           │
│  │              VictoriaMetrics Cluster                     │           │
│  │                                                         │           │
│  │  Tenant 0: Platform metrics    (vminsert -t 0)          │           │
│  │  Tenant 1: Customer site RUM   (vminsert -t 1)          │           │
│  │                                                         │           │
│  │  vminsert (x6) ──▶ vmstorage (x12, 10TB each)          │           │
│  │                         │                               │           │
│  │                    vmselect (x8)                         │           │
│  └────────────────────────┬────────────────────────────────┘           │
│                           │                                            │
│            ┌──────────────┼──────────────┐                             │
│            ▼              ▼              ▼                             │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐                    │
│  │  Grafana     │  │ vmalert  │  │  Customer     │                    │
│  │  (Internal)  │  │          │  │  Dashboard    │                    │
│  └──────────────┘  └──────────┘  │  (per-site)   │                    │
│                                  └───────────────┘                    │
└────────────────────────────────────────────────────────────────────────┘
```

#### Data Model

```
# Core Web Vitals (aggregated per site)
site_lcp_seconds{
  site_id="a1b2c3d4",
  country="US",
  device_type="mobile",
  connection="4g"
} 1.8 1698765432

# CDN performance
cdn_cache_hit_ratio{
  site_id="a1b2c3d4",
  pop="ams-01",
  content_type="image"
} 0.94 1698765432

# Platform service metrics
service_request_duration_seconds{
  service="renderer",
  method="renderPage",
  status="success",
  cluster="prod-us-east-1"
} 0.12 1698765432

# Site availability (synthetic)
site_uptime_check{
  site_id="a1b2c3d4",
  check_region="eu-west",
  protocol="https"
} 1 1698765432
```

#### Ingestion Protocol

- **OpenTSDB telnet/HTTP protocol** - from legacy edge aggregation layer
- **Prometheus remote_write** - from Kubernetes vmagent
- Multi-tenancy via `vm_account_id` HTTP header for isolation

#### MetricsQL Queries

```sql
# Slowest sites by LCP (customer support tool)
topk_avg(100, 
  avg_over_time(site_lcp_seconds{device_type="mobile"}[1h])
)

# CDN cache efficiency per PoP
avg(cdn_cache_hit_ratio) by (pop)
  | sort()

# Platform service error budget burn rate
1 - (
  sum(rate(service_request_duration_seconds_count{status="success"}[1h]))
  /
  sum(rate(service_request_duration_seconds_count[1h]))
)

# Per-customer alerting (multi-tenant query)
site_uptime_check{site_id="a1b2c3d4"} == 0

# Aggregate Core Web Vitals across all sites
histogram_quantile(0.75, 
  sum(rate(site_lcp_seconds_bucket{country="US"}[1d])) by (le)
)
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Active time series | ~150M |
| Ingestion rate | ~10M samples/sec |
| Storage (1-year retention) | ~120 TB compressed |
| Sites monitored | 200M+ |
| Tenants | 2 (platform + customer) |
| vmstorage nodes | 12 |

---

### 5. CERN - Particle Physics Experiment Monitoring

**Context:** CERN's Large Hadron Collider (LHC) and detectors (ATLAS, CMS) generate monitoring data from millions of sensors: temperature, pressure, magnetic fields, beam position, detector channel status. Extreme cardinality from sensor IDs. Long-term retention for experiment reproducibility.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CERN Monitoring Infrastructure                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   ATLAS      │  │    CMS       │  │    LHCb      │                  │
│  │  Detector    │  │  Detector    │  │  Detector    │                  │
│  │  (100M ch)   │  │  (80M ch)    │  │  (25M ch)    │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                 │                          │
│         ▼                  ▼                 ▼                          │
│  ┌────────────────────────────────────────────────────┐                 │
│  │           DCS (Detector Control System)            │                 │
│  │     WinCC-OA → Custom exporter → Prometheus fmt    │                 │
│  └───────────────────────┬────────────────────────────┘                 │
│                          │                                              │
│  ┌──────────────┐        │        ┌──────────────┐                      │
│  │  Accelerator │        │        │   IT Infra   │                      │
│  │  Controls    │        │        │  (50k nodes) │                      │
│  │  (FESA/JAPC) │        │        │  node_exp    │                      │
│  └──────┬───────┘        │        └──────┬───────┘                      │
│         │                │               │                              │
│         ▼                ▼               ▼                              │
│  ┌────────────────────────────────────────────────────┐                 │
│  │                vmagent fleet (x50)                  │                 │
│  │   - Per-experiment / per-accelerator sector        │                 │
│  │   - Relabeling to normalize heterogeneous sources  │                 │
│  └───────────────────────┬────────────────────────────┘                 │
│                          │                                              │
│                          │  remote_write + InfluxDB line protocol        │
│                          ▼                                              │
│  ┌────────────────────────────────────────────────────┐                 │
│  │         VictoriaMetrics Cluster                    │                 │
│  │                                                    │                 │
│  │  vminsert (x8)                                     │                 │
│  │      │                                             │                 │
│  │      ▼                                             │                 │
│  │  vmstorage (x20, 16TB HDD + 2TB NVMe cache each)  │                 │
│  │      │                                             │                 │
│  │      ▼                                             │                 │
│  │  vmselect (x10, 128GB RAM)                         │                 │
│  │                                                    │                 │
│  │  Retention: 5 years                                │                 │
│  │  Downsampling: raw(30d) → 1min(1y) → 10min(5y)   │                 │
│  └───────────────────────┬────────────────────────────┘                 │
│                          │                                              │
│           ┌──────────────┼──────────────┐                               │
│           ▼              ▼              ▼                               │
│  ┌─────────────┐  ┌──────────┐  ┌──────────────┐                       │
│  │  Grafana    │  │ vmalert  │  │  CERN MONIT  │                       │
│  │ (Control)   │  │ (safety) │  │  (Unified UI)│                       │
│  └─────────────┘  └──────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Data Model

```
# Detector channel status
detector_channel_status{
  experiment="ATLAS",
  subsystem="calorimeter",
  layer="electromagnetic",
  module="EMB",
  channel_id="EMB-A-03-128-04",
  fed_id="360"
} 1 1698765432

# Accelerator beam parameters
lhc_beam_position_mm{
  beam="beam1",
  plane="horizontal",
  bpm="BPMSW.1R1.B1",
  sector="1"
} 0.342 1698765432

# Cryogenics
lhc_magnet_temperature_kelvin{
  sector="34",
  cell="14R3",
  magnet_type="dipole",
  sensor_position="cold_mass"
} 1.92 1698765432

# Infrastructure
node_power_consumption_watts{
  rack="CR3-R04",
  datacenter="meyrin",
  pdu="A"
} 4523 1698765432
```

#### Ingestion Protocol

- **Prometheus remote_write** - from vmagent fleet
- **InfluxDB line protocol** - from legacy SCADA/DCS systems via custom bridges
- Some OpenTSDB from older monitoring systems being migrated

#### MetricsQL Queries

```sql
# Detect dead detector channels (no data for 5 minutes)
detector_channel_status{experiment="ATLAS"} 
  unless 
detector_channel_status{experiment="ATLAS"} offset 5m

# Beam position stability (RMS over fill)
stddev_over_time(
  lhc_beam_position_mm{beam="beam1", plane="horizontal"}[1h]
)

# Cryogenics quench early warning
WITH (
  temp = lhc_magnet_temperature_kelvin{sector="34"},
  temp_rate = deriv(temp[5m])
)
temp > 4.0 OR temp_rate > 0.1

# Count operational channels per subsystem
count(detector_channel_status == 1) by (experiment, subsystem)

# Long-term magnet temperature trend (uses downsampled data)
avg_over_time(
  lhc_magnet_temperature_kelvin{sector="34"}[30d:1h]
)
```

#### Scale Numbers

| Metric | Value |
|--------|-------|
| Active time series | ~500M (during runs) |
| Ingestion rate | ~20M samples/sec |
| Storage (5-year retention) | ~300 TB (with downsampling) |
| Detector channels | ~200M |
| vmstorage nodes | 20 |
| Unique label values (cardinality) | ~1B |

---

## Replication

### Cluster Mode with Replication

```
┌──────────────────────────────────────────────────────────────────┐
│                VictoriaMetrics Cluster Replication                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  -replicationFactor=2                                            │
│                                                                  │
│  vminsert writes each sample to N=replicationFactor storage nodes│
│                                                                  │
│  Write Flow (replicationFactor=2):                               │
│                                                                  │
│       Sample: metric_a{job="api"} 42.0                          │
│              │                                                   │
│              ▼                                                   │
│         vminsert                                                 │
│         (hash TSID → primary node)                               │
│              │                                                   │
│         ┌────┴────┐                                              │
│         ▼         ▼                                              │
│   vmstorage-1  vmstorage-2   vmstorage-3                         │
│   [PRIMARY]    [REPLICA]     [ — ]                               │
│   ████████     ████████                                          │
│                                                                  │
│  If vmstorage-1 goes down:                                       │
│  - Writes still go to vmstorage-2 (+ new replica target)         │
│  - Reads served from vmstorage-2                                 │
│                                                                  │
│  Query Flow (vmselect with -dedup.minScrapeInterval=15s):        │
│                                                                  │
│  vmselect queries ALL vmstorage nodes                            │
│       │                                                          │
│       ├──▶ vmstorage-1 → returns data                            │
│       ├──▶ vmstorage-2 → returns duplicate data                  │
│       └──▶ vmstorage-3 → returns nothing for this series         │
│       │                                                          │
│       ▼                                                          │
│  Deduplication: keep one sample per 15s window                   │
│  Return merged result                                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Configuration

```bash
# vminsert
./vminsert \
  -storageNode=vmstorage-1:8400 \
  -storageNode=vmstorage-2:8400 \
  -storageNode=vmstorage-3:8400 \
  -replicationFactor=2

# vmselect (must enable dedup when replication is used)
./vmselect \
  -storageNode=vmstorage-1:8401 \
  -storageNode=vmstorage-2:8401 \
  -storageNode=vmstorage-3:8401 \
  -dedup.minScrapeInterval=15s
```

### High Availability WITHOUT Replication

```
┌────────────────────────────────────────────────────────────┐
│         HA via Independent Instances (Recommended)         │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  vmagent writes to BOTH clusters simultaneously:           │
│                                                            │
│                  vmagent                                    │
│                 /       \                                   │
│                ▼         ▼                                  │
│  ┌──────────────┐   ┌──────────────┐                       │
│  │  VM Cluster  │   │  VM Cluster  │                       │
│  │  (Primary)   │   │  (Secondary) │                       │
│  └──────┬───────┘   └──────┬───────┘                       │
│         │                  │                               │
│         └────────┬─────────┘                               │
│                  ▼                                          │
│           Load Balancer                                     │
│          (query path)                                      │
│                  │                                          │
│                  ▼                                          │
│             Grafana                                         │
│                                                            │
│  Pros: No storage overhead, simple, independent failure    │
│  Cons: 2x write cost, queries may show slight differences  │
└────────────────────────────────────────────────────────────┘
```

**Key tradeoffs:**

| Approach | Storage Cost | Write Overhead | Failure Isolation | Complexity |
|----------|-------------|----------------|-------------------|------------|
| replicationFactor=2 | 2x on same cluster | Minimal | Shared fate | Low |
| Independent clusters | 2x separate | 2x network | Full isolation | Medium |
| No replication | 1x | None | Data loss on node failure | Lowest |

---

## Scalability

### Single-Node vs Cluster Mode

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SINGLE-NODE MODE                                  │
│         (Recommended for < 10M active time series)                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│       Prometheus / vmagent                                          │
│              │                                                      │
│              ▼                                                      │
│  ┌───────────────────────────┐                                      │
│  │    VictoriaMetrics        │                                      │
│  │    (single binary)        │                                      │
│  │                           │                                      │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ │                                      │
│  │  │Write│ │Store│ │Query│ │  ← All-in-one                        │
│  │  │Path │ │     │ │Path │ │                                      │
│  │  └─────┘ └─────┘ └─────┘ │                                      │
│  └───────────────────────────┘                                      │
│              │                                                      │
│              ▼                                                      │
│         Local Disk                                                  │
│                                                                     │
│  Advantages:                                                        │
│  - Zero operational complexity                                      │
│  - Lower resource usage (no network between components)             │
│  - Handles up to ~10M active series on modern hardware              │
│  - Single binary, easy to deploy                                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    CLUSTER MODE                                      │
│         (For > 10M active time series)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│       vmagent (collection + relabeling)                              │
│              │                                                      │
│              ▼                                                      │
│  ┌───────────────────────────────────────────────────────┐          │
│  │  vminsert (stateless, horizontally scalable)          │          │
│  │  ┌────────┐  ┌────────┐  ┌────────┐                  │          │
│  │  │insert-1│  │insert-2│  │insert-3│                  │          │
│  │  └───┬────┘  └───┬────┘  └───┬────┘                  │          │
│  └──────┼────────────┼──────────┼────────────────────────┘          │
│         │            │          │                                    │
│         │  Consistent hash by TSID (jump hash)                      │
│         ▼            ▼          ▼                                    │
│  ┌───────────────────────────────────────────────────────┐          │
│  │  vmstorage (stateful, data sharded)                   │          │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │          │
│  │  │storage-1│  │storage-2│  │storage-3│  │storage-N│ │          │
│  │  │ shard 1 │  │ shard 2 │  │ shard 3 │  │ shard N │ │          │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │          │
│  └──────┬────────────┬──────────┬────────────┬───────────┘          │
│         │            │          │            │                       │
│         ▼            ▼          ▼            ▼                       │
│  ┌───────────────────────────────────────────────────────┐          │
│  │  vmselect (stateless, scatter-gather queries)         │          │
│  │  ┌────────┐  ┌────────┐  ┌────────┐                  │          │
│  │  │select-1│  │select-2│  │select-3│                  │          │
│  │  └────────┘  └────────┘  └────────┘                  │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                     │
│  Scaling rules:                                                     │
│  - vminsert: Scale by ingestion rate (CPU bound)                    │
│  - vmstorage: Scale by data volume + active series (Disk + RAM)     │
│  - vmselect: Scale by query concurrency (CPU + RAM)                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Horizontal Scaling: Adding vmstorage Nodes

```
Step 1: Add new node to vminsert/vmselect -storageNode lists
Step 2: Restart vminsert and vmselect (no vmstorage restart needed)
Step 3: New data is distributed to new node via consistent hashing
Step 4: Old data stays on original nodes (no rebalancing!)

Before:  [storage-1] [storage-2] [storage-3]
          33% data    33% data    33% data

After:   [storage-1] [storage-2] [storage-3] [storage-4]
          25% new     25% new     25% new     25% new
          + old data  + old data  + old data  (empty for old)

Note: VictoriaMetrics does NOT rebalance old data.
      Old data stays on original nodes until retention expires.
      This is a deliberate design choice for operational simplicity.
```

### vmagent for Collection and Fan-out

```
┌─────────────────────────────────────────────────────────────┐
│                   vmagent Capabilities                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────┐                    │
│  │            vmagent                   │                    │
│  │                                      │                    │
│  │  INPUT:                              │                    │
│  │  - Prometheus scrape (service disc.) │                    │
│  │  - remote_write receiver             │                    │
│  │  - InfluxDB line protocol            │                    │
│  │  - Graphite plaintext                │                    │
│  │  - OpenTSDB                          │                    │
│  │  - DataDog agent protocol            │                    │
│  │                                      │                    │
│  │  PROCESSING:                         │                    │
│  │  - Relabeling (drop/keep/replace)    │                    │
│  │  - Stream aggregation (pre-compute)  │                    │
│  │  - Deduplication                     │                    │
│  │  - Filtering by metric name/labels   │                    │
│  │                                      │                    │
│  │  OUTPUT (fan-out):                   │                    │
│  │  - remote_write to VM cluster A      │                    │
│  │  - remote_write to VM cluster B      │                    │
│  │  - remote_write to Cortex/Thanos     │                    │
│  │                                      │                    │
│  │  RELIABILITY:                        │                    │
│  │  - On-disk buffer (-remoteWrite.     │                    │
│  │    tmpDataPath) for backpressure     │                    │
│  │  - Automatic retry with backoff      │                    │
│  └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

### Comparison: VictoriaMetrics vs Prometheus vs Thanos vs Cortex

| Feature | VictoriaMetrics (Cluster) | Prometheus | Thanos | Cortex/Mimir |
|---------|--------------------------|------------|--------|--------------|
| **Architecture** | vminsert/storage/select | Monolithic | Sidecar + Store + Compact | Distributor/Ingester/Store |
| **Horizontal scaling** | Add vmstorage nodes | No (federation) | Object storage scaling | Ring-based sharding |
| **Long-term storage** | Built-in (local disk) | None (needs remote) | Object store (S3) | Object store (S3) |
| **Global query** | Native scatter-gather | No | Store API + Querier | Query-frontend |
| **HA** | Replication or dual-write | 2x instances | Sidecar on each Prom | Built-in replication |
| **Compression** | 0.4-0.8 bytes/point | 1.3 bytes/point | Same as Prom + S3 | ~1 byte/point |
| **RAM per 1M series** | ~1 GB | 3-4 GB | 3-4 GB + sidecar | ~2 GB |
| **Query language** | MetricsQL (PromQL superset) | PromQL | PromQL | PromQL |
| **Downsampling** | Enterprise / recording rules | Recording rules | Built-in (5m, 1h) | Compactor |
| **Operational complexity** | Low-Medium | Low | High | High |
| **Multi-tenancy** | Built-in (cluster) | No | Partial | Built-in |
| **Ingestion protocols** | 10+ (Prom, Influx, Graphite..) | Scrape only | Prometheus only | Prometheus only |
| **License** | Apache 2.0 (OSS) | Apache 2.0 | Apache 2.0 | AGPL 3.0 |

---

## Production Setup

### Hardware Sizing

```
┌─────────────────────────────────────────────────────────────────┐
│                  Hardware Sizing Guidelines                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FORMULA:                                                       │
│                                                                 │
│  RAM (vmstorage) = active_time_series × 1KB                    │
│                  + indexdb cache (10-20% of index size)          │
│                                                                 │
│  Disk (total) = ingestion_rate × bytes_per_point × retention   │
│               = samples/sec × 0.5-1.0 bytes × seconds_retained │
│                                                                 │
│  CPU (vminsert) = ingestion_rate / 500K samples_per_core       │
│  CPU (vmselect) = concurrent_queries × complexity_factor       │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  EXAMPLE: 50M active time series, 3M samples/sec, 1y retention │
│                                                                 │
│  RAM (vmstorage total): 50M × 1KB = 50 GB                      │
│  → Split across 5 nodes = 10 GB per node + overhead = 16 GB    │
│                                                                 │
│  Disk: 3M × 0.5 bytes × 86400 × 365 = ~47 TB                  │
│  → 5 nodes = ~10 TB per node                                   │
│                                                                 │
│  CPU (vminsert): 3M / 500K = 6 cores minimum                   │
│  CPU (vmselect): depends on query load, start with 8 cores     │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  TIER RECOMMENDATIONS:                                          │
│                                                                 │
│  Small   (<1M series):  Single-node, 8GB RAM, 4 CPU, 500GB SSD │
│  Medium  (1-10M series): Single-node, 32GB RAM, 16 CPU, 4TB SSD│
│  Large   (10-100M series): Cluster, 3-5 vmstorage nodes        │
│  XLarge  (100M+ series): Cluster, 10+ vmstorage nodes          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Retention Configuration

```bash
# Single-node
./victoria-metrics \
  -retentionPeriod=12   # months (default is 1 month)
  -storageDataPath=/data/vm

# Cluster (per vmstorage)
./vmstorage \
  -retentionPeriod=365d \   # supports: h, d, w, y
  -storageDataPath=/data/vm \
  -dedup.minScrapeInterval=15s

# Multiple retention periods (run separate clusters or use downsampling)
# Short-term (raw): 30 days
# Long-term (downsampled): 5 years
```

### Monitoring VictoriaMetrics Itself

```bash
# VictoriaMetrics exposes /metrics endpoint in Prometheus format

# Key self-monitoring metrics:
vm_rows_inserted_total                    # ingestion rate
vm_slow_queries_total                     # queries hitting disk heavily
vm_active_timeseries                      # current cardinality
vm_data_size_bytes{type="indexdb"}        # index size
vm_data_size_bytes{type="storage"}        # data size  
vm_merge_need_free_disk_space             # disk pressure
process_resident_memory_bytes             # RAM usage
vm_concurrent_insert_current              # write concurrency
vm_concurrent_select_current              # query concurrency
```

**Essential Grafana dashboard panels:**
1. Ingestion rate (`rate(vm_rows_inserted_total[5m])`)
2. Active time series (`vm_active_timeseries`)
3. Query duration P95 (`vm_request_duration_seconds`)
4. Disk usage and free space
5. RAM usage vs available
6. Cache hit ratios (`vm_cache_hits_total / (vm_cache_hits_total + vm_cache_misses_total)`)

### Backup with vmbackup/vmrestore

```bash
# Backup to S3 (incremental by default)
./vmbackup \
  -storageDataPath=/data/vm \
  -dst=s3://my-bucket/vm-backups/$(date +%Y%m%d) \
  -credsFilePath=/etc/vm/s3-creds.json

# Backup to GCS
./vmbackup \
  -storageDataPath=/data/vm \
  -dst=gs://my-bucket/vm-backups/latest

# Restore
./vmrestore \
  -src=s3://my-bucket/vm-backups/20231101 \
  -storageDataPath=/data/vm-restore

# Schedule with cron (daily incremental, weekly full)
0 2 * * * /usr/local/bin/vmbackup -storageDataPath=/data/vm -dst=s3://bucket/daily -snapshot.createURL=http://localhost:8428/snapshot/create
0 3 * * 0 /usr/local/bin/vmbackup -storageDataPath=/data/vm -dst=s3://bucket/weekly -origin=""
```

**Backup architecture:**
```
┌─────────────┐    snapshot    ┌───────────┐    upload    ┌─────────┐
│  vmstorage  │───────────────▶│ vmbackup  │─────────────▶│   S3    │
│  (running)  │  (consistent)  │           │ (incremental)│  bucket │
└─────────────┘                └───────────┘              └─────────┘
                                                               │
                                                               ▼
┌─────────────┐    restore     ┌───────────┐    download  ┌─────────┐
│  vmstorage  │◀───────────────│vmrestore  │◀─────────────│   S3    │
│  (stopped)  │                │           │              │  bucket │
└─────────────┘                └───────────┘              └─────────┘
```

### Alerting with vmalert

```yaml
# /etc/vmalert/rules/alerts.yml
groups:
  - name: infrastructure
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
          /
          sum(rate(http_requests_total[5m])) by (service)
          > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: VictoriaMetricsTooManySlowQueries
        expr: rate(vm_slow_queries_total[5m]) > 10
        for: 5m
        labels:
          severity: warning

  - name: recording_rules
    interval: 60s
    rules:
      - record: job:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job)
```

```bash
# Run vmalert
./vmalert \
  -rule=/etc/vmalert/rules/*.yml \
  -datasource.url=http://vmselect:8481/select/0/prometheus \
  -remoteWrite.url=http://vminsert:8480/insert/0/prometheus \
  -notifier.url=http://alertmanager:9093 \
  -evaluationInterval=30s
```

### Integration with Grafana

```
# Grafana datasource configuration (provisioning)
# /etc/grafana/provisioning/datasources/vm.yml

apiVersion: 1
datasources:
  - name: VictoriaMetrics
    type: prometheus
    access: proxy
    url: http://vmselect:8481/select/0/prometheus
    isDefault: true
    jsonData:
      timeInterval: "15s"
      httpMethod: POST    # Better for long queries
      
  # For multi-tenant setup
  - name: VictoriaMetrics-Tenant1
    type: prometheus
    access: proxy
    url: http://vmselect:8481/select/1/prometheus
```

**Grafana tips for VictoriaMetrics:**
- Use `POST` method for queries (avoids URL length limits)
- Set min interval to match scrape interval (15s)
- Use MetricsQL extensions like `topk_avg`, `range_median` in panels
- Enable `$__interval` alignment with VM's auto-step selection

### Complete Production Deployment (Docker Compose)

```yaml
# docker-compose.yml (simplified cluster)
version: "3.8"
services:
  vmagent:
    image: victoriametrics/vmagent:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - vmagent-data:/tmp/vmagent-remotewrite-data
    command:
      - "-promscrape.config=/etc/prometheus/prometheus.yml"
      - "-remoteWrite.url=http://vminsert:8480/insert/0/prometheus/api/v1/write"
      - "-remoteWrite.tmpDataPath=/tmp/vmagent-remotewrite-data"

  vminsert:
    image: victoriametrics/vminsert:latest
    command:
      - "-storageNode=vmstorage-1:8400"
      - "-storageNode=vmstorage-2:8400"
      - "-replicationFactor=2"
    ports:
      - "8480:8480"

  vmstorage-1:
    image: victoriametrics/vmstorage:latest
    volumes:
      - storage-1-data:/storage
    command:
      - "-storageDataPath=/storage"
      - "-retentionPeriod=12"

  vmstorage-2:
    image: victoriametrics/vmstorage:latest
    volumes:
      - storage-2-data:/storage
    command:
      - "-storageDataPath=/storage"
      - "-retentionPeriod=12"

  vmselect:
    image: victoriametrics/vmselect:latest
    command:
      - "-storageNode=vmstorage-1:8401"
      - "-storageNode=vmstorage-2:8401"
      - "-dedup.minScrapeInterval=15s"
    ports:
      - "8481:8481"

  vmalert:
    image: victoriametrics/vmalert:latest
    volumes:
      - ./alerts:/etc/alerts
    command:
      - "-rule=/etc/alerts/*.yml"
      - "-datasource.url=http://vmselect:8481/select/0/prometheus"
      - "-remoteWrite.url=http://vminsert:8480/insert/0/prometheus/api/v1/write"
      - "-notifier.url=http://alertmanager:9093"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  vmagent-data:
  storage-1-data:
  storage-2-data:
```

---

## Summary: When to Choose VictoriaMetrics

| Scenario | Recommendation |
|----------|---------------|
| Replacing Prometheus long-term storage | Single-node VM as remote_write target |
| Multi-region metrics aggregation | VM Cluster with vmagent per region |
| Cost-sensitive (need less hardware) | VM (2-3x less RAM/disk vs alternatives) |
| High cardinality workloads | VM (better indexdb than Prometheus TSDB) |
| Need multi-protocol ingestion | VM (Prometheus, InfluxDB, Graphite, OpenTSDB, DataDog) |
| Already using Thanos/Cortex well | May not need to migrate |
| Need strong multi-tenancy governance | Consider Cortex/Mimir (more mature RBAC) |
| Small scale (<1M series) | Single-node VM or just Prometheus |
