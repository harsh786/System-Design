# Prometheus - Real World Use Cases & Production Guide

## Core Concepts

### Pull-Based Model vs Push

```
PULL MODEL (Prometheus):                    PUSH MODEL (StatsD/Graphite):
┌──────────────┐                            ┌──────────────┐
│  Prometheus  │──scrape──►/metrics          │   Targets    │──push──►│ Collector │
│   Server     │     (HTTP GET)              │              │         │           │
└──────────────┘                            └──────────────┘         └───────────┘
     │                                       
     ├── Knows what to scrape (service discovery)
     ├── Controls scrape interval
     ├── Detects target down (up == 0)
     └── No client-side buffering needed
```

**Why Pull wins for infrastructure monitoring:**
- Central control of what's monitored
- Target health detection is built-in (`up` metric)
- No thundering herd on restart
- Easier to run locally for development
- Targets are stateless (just expose /metrics)

**When Push is better:**
- Short-lived batch jobs (use Pushgateway)
- Firewall constraints (targets behind NAT)
- Event-driven metrics (not periodic)

### TSDB Engine Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Prometheus TSDB                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────┐                        │
│  │            HEAD BLOCK (in-memory)        │                        │
│  │                                         │                        │
│  │  ┌─────────┐  ┌─────────┐  ┌────────┐  │                        │
│  │  │ Series 1│  │ Series 2│  │Series N│  │  ◄── Active writes     │
│  │  │ chunks  │  │ chunks  │  │ chunks │  │                        │
│  │  └─────────┘  └─────────┘  └────────┘  │                        │
│  │                                         │                        │
│  │  Backed by WAL (Write-Ahead Log)        │                        │
│  └───────────────────┬─────────────────────┘                        │
│                      │ compaction (every 2h)                         │
│                      ▼                                              │
│  ┌─────────────────────────────────────────┐                        │
│  │         PERSISTENT BLOCKS (disk)         │                        │
│  │                                         │                        │
│  │  ┌────────┐  ┌────────┐  ┌────────┐    │                        │
│  │  │Block 1 │  │Block 2 │  │Block 3 │    │  Each block = 2h      │
│  │  │ index  │  │ index  │  │ index  │    │                        │
│  │  │ chunks │  │ chunks │  │ chunks │    │  Compacted into larger │
│  │  │ meta   │  │ meta   │  │ meta   │    │  blocks over time      │
│  │  │tombstone│  │tombstone│  │tombstone│   │                        │
│  │  └────────┘  └────────┘  └────────┘    │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                     │
│  WAL: /data/wal/                                                    │
│  Blocks: /data/01BKGV7JBM69T2G1BGBGM6KB12/                        │
│           ├── meta.json                                             │
│           ├── index                                                 │
│           ├── chunks/                                               │
│           └── tombstones                                            │
└─────────────────────────────────────────────────────────────────────┘
```

**Key TSDB Properties:**
- Samples compressed at ~1.3-1.5 bytes/sample
- Head block: last 2 hours, in-memory + WAL
- Persistent blocks: immutable, 2h initially, compacted to larger
- Index: inverted index on label pairs for fast lookup
- Chunks: 120 samples per chunk, XOR-compressed

### Metric Types

| Type | Description | Use Case | Example |
|------|-------------|----------|---------|
| **Counter** | Monotonically increasing | Requests, errors, bytes | `http_requests_total` |
| **Gauge** | Can go up/down | Temperature, queue size | `node_memory_free_bytes` |
| **Histogram** | Bucketed observations | Latency distributions | `http_request_duration_seconds` |
| **Summary** | Client-side quantiles | Latency (pre-computed) | `go_gc_duration_seconds` |

```
# Counter - use rate() or increase()
rate(http_requests_total[5m])

# Gauge - use directly or with deriv()
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes

# Histogram - use histogram_quantile()
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Summary - already has quantiles
go_gc_duration_seconds{quantile="0.99"}
```

### Labels and Dimensional Data Model

```
Metric name + Labels = Time Series

http_requests_total{method="GET", handler="/api/users", status="200", instance="web-1:8080"}
│                    │                                                                    │
└── metric name      └── labels (key-value pairs)                                        │
                                                                                         │
                     Each unique combination = 1 time series ─────────────────────────────┘

CARDINALITY = product of all label value counts
  method(4) x handler(50) x status(5) x instance(100) = 100,000 series

WARNING: Unbounded labels (user_id, request_id) = cardinality explosion
```

### Service Discovery

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│ Prometheus  │────►│ Service Discovery Mechanisms             │
│ Config      │     │                                          │
└─────────────┘     │  kubernetes_sd_configs:                  │
                    │    - role: pod/node/service/endpoints     │
                    │                                          │
                    │  consul_sd_configs:                      │
                    │    - server: consul:8500                  │
                    │                                          │
                    │  dns_sd_configs:                         │
                    │    - names: [_prometheus._tcp.example.com]│
                    │                                          │
                    │  file_sd_configs:                        │
                    │    - files: ['/etc/prom/targets/*.json'] │
                    │                                          │
                    │  ec2_sd_configs:                         │
                    │    - region: us-east-1                    │
                    └──────────────────────────────────────────┘

Relabeling pipeline:
  discovered targets ──► relabel_configs ──► scrape ──► metric_relabel_configs ──► store
```

### Alertmanager

```
┌───────────────────────────────────────────────────────────────┐
│                      Alertmanager                              │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Alerts In ──► Grouping ──► Inhibition ──► Silencing ──► Route│
│                                                               │
│  Grouping:    cluster + alertname → single notification       │
│  Inhibition:  critical fires → suppress warning               │
│  Silencing:   manual mute during maintenance                  │
│  Routing:     match labels → receiver (slack/pager/email)     │
│                                                               │
│  route:                                                       │
│    receiver: 'default-slack'                                  │
│    group_by: ['alertname', 'cluster']                         │
│    group_wait: 30s                                            │
│    group_interval: 5m                                         │
│    repeat_interval: 4h                                        │
│    routes:                                                    │
│      - match: {severity: critical}                            │
│        receiver: 'pagerduty-critical'                         │
│      - match: {severity: warning}                             │
│        receiver: 'slack-warnings'                             │
└───────────────────────────────────────────────────────────────┘
```

---

## Memory & Storage Benchmarks (per 1M Active Time Series)

| Resource | Estimate | Notes |
|----------|----------|-------|
| **RAM** | 4-8 GB | Head block + index + query buffer |
| **RAM (with recording rules)** | 6-10 GB | Additional evaluation overhead |
| **Disk ingestion rate** | ~16 GB/day | At 15s scrape interval, ~1.5 bytes/sample |
| **Disk (15d retention)** | ~240 GB | Compressed on disk |
| **WAL size** | 2-4 GB | Last 2h of uncompacted data |
| **CPU cores** | 2-4 | Scraping + compaction + queries |
| **Scrape duration** | < 2s for 1000 targets | 1000 series/target avg |

**Formulas:**
```
disk_per_day = active_series × samples_per_day × bytes_per_sample
             = 1,000,000 × 5,760 (at 15s) × 1.5 bytes
             ≈ 8.6 GB/day (before compaction, ~16 GB with overhead)

RAM ≈ active_series × 4-8 KB (series metadata + head chunks)
    = 1,000,000 × 6 KB ≈ 6 GB
```

---

## Real-World Use Cases

### 1. SoundCloud - Origin of Prometheus

**Context:** Prometheus was created at SoundCloud in 2012 by Matt T. Proud and Julius Volz. They had 100+ microservices and existing tools (StatsD/Graphite) couldn't handle the dimensional data model needed.

**Scale:** ~500 microservices, millions of time series, multi-datacenter.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SoundCloud Architecture                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │  Auth    │  │ Playback │  │ Search   │  │ Upload   │           │
│  │ Service  │  │ Service  │  │ Service  │  │ Service  │  ...x500  │
│  │ /metrics │  │ /metrics │  │ /metrics │  │ /metrics │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │              │              │              │                 │
│       └──────────────┴──────┬───────┴──────────────┘                │
│                             │ scrape                                │
│                      ┌──────┴──────┐                                │
│                      │ Prometheus  │                                │
│                      │   Server    │                                │
│                      │ (per-team)  │                                │
│                      └──────┬──────┘                                │
│                             │                                       │
│                    ┌────────┼────────┐                              │
│                    ▼        ▼        ▼                              │
│              ┌─────────┐ ┌───────┐ ┌────────┐                      │
│              │Alertmgr │ │Grafana│ │ Fed.   │                      │
│              │(cluster)│ │       │ │Prom    │                      │
│              └─────────┘ └───────┘ └────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Metrics Design:**
```promql
# Request rate by service
sum(rate(http_requests_total{job="playback"}[5m])) by (method, status)

# Latency P99 per service
histogram_quantile(0.99, 
  sum(rate(http_request_duration_seconds_bucket{job="playback"}[5m])) by (le)
)

# Error budget burn rate
1 - (
  sum(rate(http_requests_total{status=~"5.."}[1h])) /
  sum(rate(http_requests_total[1h]))
)
```

**Scaling Strategy:**
- One Prometheus per team/service-group
- Federation Prometheus for global aggregates
- Retention: 15 days local, long-term in separate store

---

### 2. DigitalOcean - Hypervisor & Droplet Fleet

**Context:** DigitalOcean monitors thousands of hypervisors across 14+ data centers, hosting millions of customer droplets.

**Scale:** ~5,000 hypervisors, millions of droplets, 10M+ active series.

```
┌─────────────────────────────────────────────────────────────────────┐
│               DigitalOcean - Per Datacenter                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Hypervisor Fleet (thousands per DC)                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
│  │  HV-001  │  │  HV-002  │  │  HV-N    │                          │
│  │node_exp. │  │node_exp. │  │node_exp. │                          │
│  │libvirt_e │  │libvirt_e │  │libvirt_e │                          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                          │
│       └──────────────┴──────┬───────┘                               │
│                             │                                       │
│  ┌────────────────┐   ┌────┴───────────┐   ┌────────────────┐      │
│  │ Prometheus     │   │ Prometheus     │   │ Prometheus     │      │
│  │ (shard A)      │   │ (shard B)      │   │ (shard C)      │      │
│  │ HV 1-1500     │   │ HV 1501-3000  │   │ HV 3001+      │      │
│  └───────┬────────┘   └───────┬────────┘   └───────┬────────┘      │
│          │                    │                    │                 │
│          └────────────────────┼────────────────────┘                │
│                               ▼                                     │
│                    ┌──────────────────┐                              │
│                    │  Thanos Query    │◄── Global view               │
│                    │  (fanout)        │                              │
│                    └────────┬─────────┘                              │
│                             │                                       │
│               ┌─────────────┼─────────────┐                        │
│               ▼             ▼             ▼                         │
│        ┌───────────┐ ┌───────────┐ ┌───────────┐                   │
│        │Alertmanager│ │  Grafana  │ │Thanos Store│                   │
│        │ (HA pair) │ │           │ │ (S3/GCS)  │                   │
│        └───────────┘ └───────────┘ └───────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Metrics:**
```promql
# Hypervisor CPU saturation
avg(1 - rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance) > 0.85

# Droplet density per hypervisor
count(libvirt_domain_info_virtual_cpus) by (instance)

# Network bandwidth approaching capacity
rate(node_network_transmit_bytes_total{device="bond0"}[5m]) / 
  node_network_speed_bytes{device="bond0"} > 0.8

# Disk IOPS saturation
rate(node_disk_io_time_seconds_total[5m]) > 0.95

# Memory overcommit ratio
sum(libvirt_domain_info_maximum_memory_bytes) by (instance) / 
  node_memory_MemTotal_bytes > 3.0
```

**Scaling Strategy:**
- Sharding by target hash (hypervisor ranges)
- Thanos sidecar on each Prometheus for global queries
- Object storage (S3) for unlimited retention
- Recording rules to pre-aggregate per-DC summaries

---

### 3. GitLab SaaS - Observability for GitLab.com

**Context:** GitLab.com serves 13M+ users with a complex Ruby/Go microservice architecture. They use Prometheus extensively for SLO-based alerting.

**Scale:** 500+ services, 50M+ active time series, 3M+ samples/second ingestion.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GitLab.com Monitoring                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  GKE Clusters                                                       │
│  ┌─────────────────────────────────────────────────────┐            │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │            │
│  │  │Rails │ │Gitaly│ │Redis │ │Sidekiq│ │Pgbnc │     │            │
│  │  │pods  │ │pods  │ │exp.  │ │pods   │ │exp.  │     │            │
│  │  └──┬───┘ └──┬───┘ └──┬───┘ └──┬────┘ └──┬───┘     │            │
│  │     └────────┴────────┴────┬───┴─────────┘         │            │
│  └────────────────────────────┼────────────────────────┘            │
│                               │                                     │
│  ┌────────────────────────────┼──────────────────────────┐          │
│  │  Prometheus Fleet          │                          │          │
│  │  ┌──────────────┐  ┌──────┴───────┐  ┌────────────┐  │          │
│  │  │ Prom (app)   │  │ Prom (infra) │  │ Prom (db)  │  │          │
│  │  │ 20M series   │  │ 15M series   │  │ 15M series │  │          │
│  │  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │          │
│  │         └─────────────────┼─────────────────┘         │          │
│  └───────────────────────────┼───────────────────────────┘          │
│                              ▼                                      │
│                    ┌──────────────────┐                              │
│                    │  Thanos Query    │                              │
│                    │  (global view)   │                              │
│                    └────────┬─────────┘                              │
│                             │                                       │
│              ┌──────────────┼──────────────┐                        │
│              ▼              ▼              ▼                         │
│       ┌───────────┐  ┌──────────┐  ┌───────────┐                   │
│       │Alertmanager│  │  Grafana │  │Thanos     │                   │
│       │  (HA x3)  │  │  (SLO)  │  │Compact+   │                   │
│       └───────────┘  └──────────┘  │Store (GCS)│                   │
│                                    └───────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Metrics (SLO-Based):**
```promql
# Apdex score for web requests (SLI)
(
  sum(rate(http_request_duration_seconds_bucket{le="1"}[5m]))
  + sum(rate(http_request_duration_seconds_bucket{le="5"}[5m]))
) / 2 / sum(rate(http_request_duration_seconds_count[5m]))

# Error budget remaining (30-day window)
1 - (
  (1 - (sum(rate(gitlab_transaction_duration_seconds_bucket{le="5"}[30d])) 
   / sum(rate(gitlab_transaction_duration_seconds_count[30d]))))
  / (1 - 0.995)  # SLO = 99.5%
)

# Gitaly (Git storage) RPC latency
histogram_quantile(0.95,
  sum(rate(gitaly_service_client_requests_bucket[5m])) by (le, grpc_method)
)

# Sidekiq job queue saturation
sum(sidekiq_queue_size) by (queue) > 10000

# PostgreSQL connection pool saturation  
pgbouncer_pools_server_active_connections / 
  pgbouncer_pools_server_max_connections > 0.8
```

**Scaling Strategy:**
- Functional sharding (app metrics, infra metrics, DB metrics)
- Recording rules for SLO calculations (expensive to compute live)
- Thanos for cross-shard queries and GCS long-term storage
- 90-day retention in Thanos, 7-day local

---

### 4. Shopify - Kubernetes Cluster Monitoring

**Context:** Shopify runs one of the largest Kubernetes deployments, handling flash sales (e.g., Black Friday/Cyber Monday) with extreme traffic spikes.

**Scale:** 10,000+ pods, hundreds of nodes, multiple clusters, 20M+ active series across clusters.

```
┌─────────────────────────────────────────────────────────────────────┐
│              Shopify - Per K8s Cluster                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │  Kubernetes Cluster                                     │        │
│  │                                                         │        │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │        │
│  │  │kube-    │ │kubelet/ │ │app pods │ │istio-   │      │        │
│  │  │state-   │ │cAdvisor │ │(custom  │ │proxy    │      │        │
│  │  │metrics  │ │         │ │ metrics)│ │(envoy)  │      │        │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘      │        │
│  │       └───────────┴───────────┴────────────┘           │        │
│  └───────────────────────────┬─────────────────────────────┘        │
│                              │ kubernetes_sd (pod/node role)        │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  Prometheus Operator (manages Prometheus CRs)        │           │
│  │                                                      │           │
│  │  ┌──────────────┐   ┌──────────────┐                │           │
│  │  │ Prometheus   │   │ Prometheus   │  (HA pair)     │           │
│  │  │  replica-0   │   │  replica-1   │                │           │
│  │  └──────┬───────┘   └──────┬───────┘                │           │
│  │         └───────────┬───────┘                        │           │
│  └─────────────────────┼────────────────────────────────┘           │
│                        ▼                                            │
│           ┌────────────────────────┐                                │
│           │   Cortex / Mimir       │◄── Remote write from all       │
│           │   (multi-tenant)       │    clusters                    │
│           │   Long-term storage    │                                │
│           └────────────┬───────────┘                                │
│                        │                                            │
│              ┌─────────┼─────────┐                                  │
│              ▼         ▼         ▼                                  │
│        ┌─────────┐ ┌───────┐ ┌─────────────┐                       │
│        │Alertmgr │ │Grafana│ │BFCM Dashboard│                       │
│        │(global) │ │       │ │(real-time)   │                       │
│        └─────────┘ └───────┘ └─────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Metrics:**
```promql
# Pod resource requests vs actual usage (right-sizing)
sum(container_memory_working_set_bytes{container!=""}) by (namespace, pod) /
sum(kube_pod_container_resource_requests{resource="memory"}) by (namespace, pod)

# Node pressure detection
kube_node_status_condition{condition="MemoryPressure", status="true"} == 1

# HPA scaling lag
kube_horizontalpodautoscaler_status_desired_replicas - 
  kube_horizontalpodautoscaler_status_current_replicas > 0

# Orders per second (BFCM critical)
sum(rate(shopify_orders_total[1m]))

# Checkout latency P99 (revenue-critical)
histogram_quantile(0.99,
  sum(rate(checkout_duration_seconds_bucket[1m])) by (le)
)

# Pod restart storm detection
sum(increase(kube_pod_container_status_restarts_total[15m])) by (namespace) > 50
```

**Scaling Strategy:**
- Prometheus Operator for lifecycle management
- HA pairs per cluster (identical scrape configs)
- Remote write to Cortex/Mimir for global view
- Pre-BFCM: increase retention, add recording rules, pre-scale
- Cardinality limits enforced via admission webhooks

---

### 5. Reddit - High-Traffic Platform Peak Monitoring

**Context:** Reddit handles massive traffic spikes (viral posts, events like Super Bowl). They need to monitor thousands of services with sub-minute granularity.

**Scale:** 2,000+ services, 100K+ containers, 15M+ active series, traffic spikes of 10x baseline.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Reddit Monitoring Stack                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────────────────────┐              │
│  │  K8s Clusters (multi-region)                      │              │
│  │                                                   │              │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │              │
│  │  │Feed  │ │Auth  │ │Media │ │Search│ │Ads   │   │              │
│  │  │svc   │ │svc   │ │svc   │ │svc   │ │svc   │   │              │
│  │  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘   │              │
│  │     └────────┴────────┴────┬───┴─────────┘       │              │
│  └────────────────────────────┼──────────────────────┘              │
│                               │                                     │
│  ┌────────────────────────────┼──────────────────────────────┐      │
│  │  Regional Prometheus Fleet │                              │      │
│  │                            ▼                              │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │      │
│  │  │Prom      │  │Prom      │  │Prom      │  │Prom      │ │      │
│  │  │(feed+    │  │(infra)   │  │(ads)     │  │(media)   │ │      │
│  │  │ comments)│  │          │  │          │  │          │ │      │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │      │
│  │       └──────────────┴─────┬──────┴──────────────┘       │      │
│  └────────────────────────────┼──────────────────────────────┘      │
│                               │ remote_write                        │
│                               ▼                                     │
│                    ┌──────────────────┐                              │
│                    │   Mimir          │                              │
│                    │ (long-term,      │                              │
│                    │  global query)   │                              │
│                    └────────┬─────────┘                              │
│                             │                                       │
│              ┌──────────────┼──────────────┐                        │
│              ▼              ▼              ▼                         │
│       ┌───────────┐  ┌──────────┐  ┌───────────────┐               │
│       │Alertmanager│  │  Grafana │  │Peak Event     │               │
│       │ (gossip)  │  │(+Explore)│  │War Room Dash  │               │
│       └───────────┘  └──────────┘  └───────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Metrics:**
```promql
# Requests per second (global)
sum(rate(http_server_requests_total[1m]))

# Feed generation latency (user-facing critical)
histogram_quantile(0.95,
  sum(rate(feed_generation_duration_seconds_bucket[5m])) by (le, region)
)

# Cache hit ratio (critical for scale)
sum(rate(cache_hits_total[5m])) / 
  (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# Viral post detection (traffic anomaly)
rate(post_views_total[5m]) > 10 * avg_over_time(rate(post_views_total[5m])[1h:5m])

# CDN origin pressure
sum(rate(cdn_origin_requests_total[1m])) by (pop) > 100000

# Database connection exhaustion
pg_stat_activity_count / pg_settings_max_connections > 0.8
```

**Scaling Strategy:**
- Domain-sharded Prometheus (feed, ads, infra, media)
- Remote write to Mimir for cross-region queries
- 10s scrape interval for critical paths, 30s for infra
- Event-based scaling: pre-provision for known events (Super Bowl, AMAs)
- Recording rules for expensive cross-service aggregations

---

## Replication & High Availability

### HA Pairs (Duplicate Scraping)

```
┌─────────────────────────────────────────────────────────────┐
│                    HA Pair Setup                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐              ┌─────────────┐              │
│  │ Prometheus  │              │ Prometheus  │              │
│  │  (primary)  │              │  (replica)  │              │
│  │             │              │             │              │
│  │ SAME config │              │ SAME config │              │
│  │ scrapes ALL │              │ scrapes ALL │              │
│  │ targets     │              │ targets     │              │
│  └──────┬──────┘              └──────┬──────┘              │
│         │                            │                     │
│         │  external_labels:          │  external_labels:   │
│         │    replica: "a"            │    replica: "b"     │
│         │                            │                     │
│         └────────────┬───────────────┘                     │
│                      ▼                                     │
│           ┌──────────────────┐                             │
│           │  Thanos Query    │  deduplicates by            │
│           │  --query.replica │  replica label              │
│           │    -label=replica│                             │
│           └──────────────────┘                             │
│                                                            │
│  OR:                                                       │
│           ┌──────────────────┐                             │
│           │  Alertmanager    │  Both send alerts;          │
│           │  (gossip cluster)│  AM deduplicates            │
│           └──────────────────┘                             │
│                                                            │
│  Trade-off: 2x scrape load, 2x storage, but zero gaps     │
└─────────────────────────────────────────────────────────────┘
```

### Thanos Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Thanos Architecture                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Cluster A                  Cluster B                  Cluster C    │
│  ┌──────────────┐           ┌──────────────┐          ┌──────────┐ │
│  │ Prometheus A │           │ Prometheus B │          │ Prom C   │ │
│  │ ┌──────────┐ │           │ ┌──────────┐ │          │┌────────┐│ │
│  │ │  Thanos  │ │           │ │  Thanos  │ │          ││ Thanos ││ │
│  │ │ Sidecar  │ │           │ │ Sidecar  │ │          ││Sidecar ││ │
│  │ └────┬─────┘ │           │ └────┬─────┘ │          │└───┬────┘│ │
│  └──────┼───────┘           └──────┼───────┘          └────┼─────┘ │
│         │                          │                       │       │
│         │    ┌─────────────────────┼───────────────────────┘       │
│         │    │                     │                               │
│         ▼    ▼                     ▼                               │
│  ┌──────────────────────────────────────────┐                      │
│  │           Thanos Query (Fanout)          │                      │
│  │   Deduplicates HA pairs                  │                      │
│  │   Partial response on failures           │                      │
│  └───────────────────┬──────────────────────┘                      │
│                      │                                             │
│         ┌────────────┼────────────┐                                │
│         ▼            │            ▼                                 │
│  ┌─────────────┐     │     ┌─────────────┐                         │
│  │   Grafana   │     │     │ Thanos Rule │                         │
│  └─────────────┘     │     └─────────────┘                         │
│                      ▼                                             │
│  ┌──────────────────────────────────────────┐                      │
│  │         Object Storage (S3/GCS)          │                      │
│  │   Sidecars upload blocks every 2h        │                      │
│  └───────────────────┬──────────────────────┘                      │
│                      │                                             │
│         ┌────────────┼────────────┐                                │
│         ▼                         ▼                                 │
│  ┌─────────────┐           ┌─────────────┐                         │
│  │Thanos Store │           │Thanos       │                         │
│  │ Gateway     │           │ Compactor   │                         │
│  │(serves old  │           │(downsamples,│                         │
│  │ blocks)     │           │ dedup,      │                         │
│  └─────────────┘           │ compact)    │                         │
│                            └─────────────┘                         │
│                                                                     │
│  Retention: raw=30d, 5m downsample=1y, 1h downsample=unlimited    │
└─────────────────────────────────────────────────────────────────────┘
```

**Thanos Components:**
| Component | Role |
|-----------|------|
| **Sidecar** | Uploads blocks to object store, proxies real-time queries |
| **Query** | Fanout to sidecars + store gateways, deduplication |
| **Store Gateway** | Serves historical data from object storage |
| **Compactor** | Downsamples, deduplicates, compacts blocks |
| **Ruler** | Evaluates recording/alerting rules against global view |
| **Receive** | Alternative to sidecar; accepts remote_write |

### Cortex / Mimir (Multi-Tenant Long-Term Storage)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Grafana Mimir Architecture                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Prometheus instances (any cluster/team)                            │
│       │            │            │                                   │
│       │ remote_write (with X-Scope-OrgID header for multi-tenancy) │
│       ▼            ▼            ▼                                   │
│  ┌──────────────────────────────────────────────┐                   │
│  │              Distributors                     │                   │
│  │  (validate, rate-limit, shard by series)     │                   │
│  └───────────────────┬──────────────────────────┘                   │
│                      │ consistent hashing                           │
│                      ▼                                              │
│  ┌──────────────────────────────────────────────┐                   │
│  │              Ingesters (stateful)             │                   │
│  │  (write to in-memory + WAL, flush to store)  │                   │
│  │  Replication factor: 3                        │                   │
│  └───────────────────┬──────────────────────────┘                   │
│                      │ flush every 2h                               │
│                      ▼                                              │
│  ┌──────────────────────────────────────────────┐                   │
│  │           Object Storage (S3/GCS/Azure)       │                   │
│  └───────────────────┬──────────────────────────┘                   │
│                      │                                              │
│                      ▼                                              │
│  ┌──────────────────────────────────────────────┐                   │
│  │           Query Frontend + Queriers          │                   │
│  │  (split, cache, deduplicate, merge)          │                   │
│  └──────────────────────────────────────────────┘                   │
│                                                                     │
│  Benefits over vanilla Prometheus:                                  │
│  - Multi-tenant isolation                                          │
│  - Horizontally scalable ingestion & queries                       │
│  - Per-tenant limits (series, rate, query)                         │
│  - No single-instance TSDB limits                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Remote Write

```yaml
# prometheus.yml
remote_write:
  - url: "http://mimir:9009/api/v1/push"
    headers:
      X-Scope-OrgID: "team-platform"
    queue_config:
      capacity: 10000
      max_shards: 50
      max_samples_per_send: 2000
    write_relabel_configs:
      - source_labels: [__name__]
        regex: "go_.*"
        action: drop  # Don't send Go runtime metrics
```

### Recording Rules

```yaml
# Pre-compute expensive queries
groups:
  - name: slo_recording_rules
    interval: 30s
    rules:
      - record: job:http_request_duration_seconds:p99
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (job, le)
          )

      - record: job:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job)

      - record: job:http_errors:ratio_rate5m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)
          / sum(rate(http_requests_total[5m])) by (job)

      # Aggregation for federation
      - record: instance:node_cpu:ratio
        expr: |
          1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)
```

---

## Scalability

### Vertical Limits

```
Single Prometheus Instance Limits (approximate):
┌────────────────────────────────────┬─────────────────────┐
│ Metric                             │ Practical Limit     │
├────────────────────────────────────┼─────────────────────┤
│ Active time series                 │ ~10M                │
│ Samples ingested/sec               │ ~1M                 │
│ Scrape targets                     │ ~50,000             │
│ RAM required at 10M series         │ 64-80 GB            │
│ Disk write throughput              │ 200-400 MB/s SSD    │
│ Query performance (10M series)     │ Seconds for complex │
└────────────────────────────────────┴─────────────────────┘

Beyond these: shard or use Thanos/Mimir
```

### Federation

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Hierarchical Federation                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Level 1: Leaf Prometheus (per-cluster/team)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Prom     │  │ Prom     │  │ Prom     │  │ Prom     │           │
│  │ team-a   │  │ team-b   │  │ team-c   │  │ team-d   │           │
│  │ (full    │  │ (full    │  │ (full    │  │ (full    │           │
│  │  detail) │  │  detail) │  │  detail) │  │  detail) │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │              │              │              │                 │
│       │  recording rules pre-aggregate                              │
│       └──────────────┴──────┬───────┴──────────────┘                │
│                             │ /federate?match[]={__name__=~"job:.*"}│
│                             ▼                                       │
│  Level 2: Global Prometheus                                         │
│  ┌──────────────────────────────────┐                               │
│  │  Prom (global)                   │                               │
│  │  - Only aggregated metrics       │                               │
│  │  - Cross-team dashboards         │                               │
│  │  - Capacity planning queries     │                               │
│  └──────────────────────────────────┘                               │
│                                                                     │
│  IMPORTANT: Only federate pre-aggregated (recording rule) metrics   │
│  Never federate raw high-cardinality metrics                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Sharding by Targets

```yaml
# Using hashmod relabeling to shard
# Shard 0 of 3:
scrape_configs:
  - job_name: 'large-fleet'
    relabel_configs:
      - source_labels: [__address__]
        modulus: 3
        target_label: __tmp_hash
        action: hashmod
      - source_labels: [__tmp_hash]
        regex: "0"          # This instance handles shard 0
        action: keep
```

### Cardinality Management

```promql
# Find high-cardinality metrics
topk(10, count by (__name__)({__name__=~".+"}))

# Find label dimensions causing explosion
count(http_requests_total) by (handler)  # too many handlers?

# TSDB stats endpoint
# GET /api/v1/status/tsdb
# Shows: seriesCountByMetricName, labelValueCountByLabelName
```

**Cardinality Best Practices:**
- Never use unbounded labels (user_id, IP, request_id)
- Use `metric_relabel_configs` to drop unused metrics
- Set `sample_limit` per scrape job
- Use `keep` relabeling to only scrape needed targets
- Monitor `prometheus_tsdb_head_series` for growth alerts

---

## Production Setup

### Scrape Configuration

```yaml
global:
  scrape_interval: 15s       # Default; 10s for critical, 30s for infra
  scrape_timeout: 10s        # Must be < scrape_interval
  evaluation_interval: 15s   # Rule evaluation frequency

  external_labels:
    cluster: "prod-us-east-1"
    environment: "production"
    replica: "a"             # For HA deduplication
```

### Storage Sizing & Retention

```yaml
# CLI flags
--storage.tsdb.path=/prometheus/data
--storage.tsdb.retention.time=15d          # Time-based retention
--storage.tsdb.retention.size=500GB        # Size-based (whichever hits first)
--storage.tsdb.wal-compression             # Enable WAL compression (~50% savings)
--storage.tsdb.min-block-duration=2h       # Don't change unless Thanos
--storage.tsdb.max-block-duration=2h       # Required for Thanos sidecar

# Sizing formula:
# disk_needed = retention_seconds / scrape_interval * series_count * 1.5 bytes * 1.2 (overhead)
# Example: 15d * 86400 / 15 * 5,000,000 * 1.5 * 1.2 ≈ 780 GB
```

### Alertmanager Routing & Inhibition

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/...'

inhibit_rules:
  - source_matchers: [severity="critical"]
    target_matchers: [severity="warning"]
    equal: [alertname, cluster, service]

  - source_matchers: [alertname="NodeDown"]
    target_matchers: [alertname=~".*"]
    equal: [instance]  # Suppress all alerts for a down node

route:
  receiver: 'default-slack'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
      continue: true
    - match:
        severity: critical
      receiver: 'slack-critical'
    - match:
        team: platform
      receiver: 'slack-platform'
      routes:
        - match:
            severity: warning
          receiver: 'slack-platform-warnings'

receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<key>'
        severity: '{{ .CommonLabels.severity }}'
  - name: 'slack-critical'
    slack_configs:
      - channel: '#alerts-critical'
        title: '{{ .CommonAnnotations.summary }}'
  - name: 'default-slack'
    slack_configs:
      - channel: '#alerts'
```

### Service Discovery (Kubernetes)

```yaml
scrape_configs:
  # Discover all pods with prometheus.io annotations
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port, __meta_kubernetes_pod_ip]
        action: replace
        regex: (\d+);(([\d\.]+))
        replacement: ${2}:${1}
        target_label: __address__
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod

  # Node metrics via node-exporter DaemonSet
  - job_name: 'kubernetes-nodes'
    kubernetes_sd_configs:
      - role: node
    relabel_configs:
      - action: labelmap
        regex: __meta_kubernetes_node_label_(.+)
```

### Meta-Monitoring (Monitor the Monitor)

```yaml
# Alert if Prometheus itself is unhealthy
groups:
  - name: prometheus_meta
    rules:
      - alert: PrometheusTargetDown
        expr: up == 0
        for: 5m
        labels:
          severity: warning

      - alert: PrometheusTSDBCompactionsFailing
        expr: increase(prometheus_tsdb_compactions_failed_total[1h]) > 0
        labels:
          severity: critical

      - alert: PrometheusHighMemory
        expr: process_resident_memory_bytes / node_memory_MemTotal_bytes > 0.8
        for: 10m
        labels:
          severity: warning

      - alert: PrometheusHighCardinality
        expr: prometheus_tsdb_head_series > 8000000
        for: 15m
        labels:
          severity: warning
          
      - alert: PrometheusRuleEvaluationSlow
        expr: prometheus_rule_group_last_duration_seconds > prometheus_rule_group_interval_seconds
        for: 5m
        labels:
          severity: warning

      - alert: PrometheusRemoteWriteBehind
        expr: |
          (prometheus_remote_storage_highest_timestamp_in_seconds 
           - ignoring(remote_name, url) 
           prometheus_remote_storage_queue_highest_sent_timestamp_seconds) > 120
        for: 5m
        labels:
          severity: critical
```

---

## Summary: When to Use What

| Scale | Architecture |
|-------|-------------|
| < 1M series | Single Prometheus + Alertmanager |
| 1-10M series | Single Prometheus + Thanos (for HA + long-term) |
| 10-50M series | Sharded Prometheus + Thanos |
| 50M+ series | Mimir/Cortex (horizontally scaled) |
| Multi-tenant | Mimir/Cortex (native multi-tenancy) |

| Need | Solution |
|------|----------|
| HA (no gaps) | HA pairs + Thanos Query dedup |
| Long-term storage | Thanos Store + Object Storage |
| Global view | Thanos Query or Mimir |
| Multi-tenant | Mimir with per-tenant limits |
| Sub-second alerting | Not Prometheus (use streaming) |
| Logs + Traces | Loki + Tempo (not Prometheus) |
