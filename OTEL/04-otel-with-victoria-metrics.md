# OpenTelemetry with VictoriaMetrics

## What is VictoriaMetrics?

VictoriaMetrics (VM) is a high-performance, cost-effective time-series database designed as a long-term storage solution for metrics. It is **Prometheus-compatible** — accepting PromQL queries and Prometheus remote write protocol — but offers significantly better compression, faster queries, and easier horizontal scaling.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    WHY VICTORIAMETRICS WITH OTEL?                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────┐     ┌──────────────────────────────────────────┐   │
│  │  Prometheus     │     │  VictoriaMetrics                          │   │
│  │  ─────────────  │     │  ──────────────────                       │   │
│  │  • 31-day local │     │  • Years of retention                     │   │
│  │  • Single node  │     │  • Horizontal scaling                     │   │
│  │  • 1.6 bytes/pt │     │  • 0.4 bytes/point (4x compression)      │   │
│  │  • No HA native │     │  • Built-in replication                   │   │
│  │  • PromQL only  │     │  • MetricsQL (superset of PromQL)        │   │
│  │  • Pull only    │     │  • Pull + Push + OTLP native             │   │
│  └─────────────────┘     └──────────────────────────────────────────┘   │
│                                                                           │
│  OTEL + VictoriaMetrics = vendor-neutral instrumentation + cost-         │
│  effective long-term storage with Prometheus query compatibility          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## VictoriaMetrics Architecture

### Single-Node Mode

For small-to-medium deployments (up to ~30M active time series):

```
┌─────────────────────────────────────────────────────────────┐
│                  VictoriaMetrics (Single Node)                │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    victoria-metrics                    │   │
│  │                                                       │   │
│  │  ┌─────────┐  ┌─────────────┐  ┌────────────────┐  │   │
│  │  │ Ingress │  │  Storage    │  │  Query Engine  │  │   │
│  │  │ (write) │  │  (tsdb)     │  │  (MetricsQL)   │  │   │
│  │  └────┬────┘  └──────┬──────┘  └───────┬────────┘  │   │
│  │       │               │                  │           │   │
│  │       └───────────────┴──────────────────┘           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  Ports:                                                       │
│  • :8428/api/v1/write     (Prometheus Remote Write)          │
│  • :8428/api/v1/query     (PromQL/MetricsQL queries)         │
│  • :8428/opentelemetry/*  (Native OTLP ingestion)            │
│  • :8428/metrics          (Self-monitoring)                   │
└─────────────────────────────────────────────────────────────┘
```

### Cluster Mode

For large deployments (30M+ active series, multi-tenant, HA):

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    VictoriaMetrics Cluster Architecture                        │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────┐       │
│  │                         vmauth (Router/LB)                         │       │
│  │  • Multi-tenant routing                                            │       │
│  │  • Authentication                                                  │       │
│  │  • Rate limiting                                                   │       │
│  └────────────────────┬──────────────────────────┬───────────────────┘       │
│                       │                           │                            │
│          Write Path   │              Read Path    │                            │
│                       ▼                           ▼                            │
│  ┌────────────────────────────┐    ┌─────────────────────────────────┐       │
│  │      vminsert (N nodes)     │    │      vmselect (N nodes)         │       │
│  │                             │    │                                  │       │
│  │  • Accepts writes           │    │  • Executes MetricsQL           │       │
│  │  • Parses OTLP/RemoteWrite │    │  • Merges results from         │       │
│  │  • Routes to vmstorage     │    │    multiple vmstorage nodes     │       │
│  │  • Consistent hashing      │    │  • Deduplication at query time  │       │
│  │  • Replication factor       │    │  • Downsampling                 │       │
│  └─────────────┬──────────────┘    └──────────────┬──────────────────┘       │
│                │                                    │                          │
│                ▼                                    ▼                          │
│  ┌─────────────────────────────────────────────────────────────────┐         │
│  │                    vmstorage (N nodes)                            │         │
│  │                                                                   │         │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │         │
│  │  │ Storage  │  │ Storage  │  │ Storage  │  │ Storage  │       │         │
│  │  │ Node 1   │  │ Node 2   │  │ Node 3   │  │ Node N   │       │         │
│  │  │          │  │          │  │          │  │          │       │         │
│  │  │ Shard A  │  │ Shard B  │  │ Shard C  │  │ Shard N  │       │         │
│  │  │ Shard B' │  │ Shard C' │  │ Shard A' │  │ Shard A" │       │         │
│  │  │ (replica)│  │ (replica)│  │ (replica)│  │ (replica)│       │         │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │         │
│  │                                                                   │         │
│  │  • Stores time series data                                        │         │
│  │  • Compression + indexing                                         │         │
│  │  • Retention enforcement                                          │         │
│  │  • Merge tree storage engine                                      │         │
│  └───────────────────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### vmagent — The Metrics Collection Agent

```
┌──────────────────────────────────────────────────────────────────┐
│                            vmagent                                 │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     Service Discovery                        │ │
│  │  • Kubernetes (pods, services, endpoints, nodes)            │ │
│  │  • Consul, Eureka, DNS, EC2, GCE                           │ │
│  │  • File-based, static configs                               │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                              │                                     │
│  ┌──────────────────────────┴──────────────────────────────────┐ │
│  │                        Scraping                              │ │
│  │  • /metrics endpoints (Prometheus format)                   │ │
│  │  • /opentelemetry/* (OTLP push endpoint)                    │ │
│  │  • Relabeling rules (metric filtering, label manipulation)  │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                              │                                     │
│  ┌──────────────────────────┴──────────────────────────────────┐ │
│  │                     Write-Ahead Log (WAL)                    │ │
│  │  • Buffers data when remote is down                         │ │
│  │  • Prevents data loss during network issues                 │ │
│  │  • Automatic retry with backoff                             │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                              │                                     │
│  ┌──────────────────────────┴──────────────────────────────────┐ │
│  │                    Remote Write (fan-out)                     │ │
│  │  • VictoriaMetrics (primary)                                │ │
│  │  • Prometheus (backup)                                      │ │
│  │  • Multiple destinations simultaneously                     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## OTEL → VictoriaMetrics Integration Patterns

### Pattern 1: OTEL Collector → Prometheus Remote Write → VictoriaMetrics

The most common and production-proven pattern:

```
┌──────────────┐     ┌────────────────────────────────────┐     ┌─────────────────┐
│ Application  │     │         OTEL Collector              │     │ VictoriaMetrics │
│              │     │                                      │     │                 │
│ OTEL SDK     │────▶│ Receiver ──▶ Processor ──▶ Exporter │────▶│ /api/v1/write   │
│ (OTLP push)  │     │ (OTLP)       (batch,       (prom   │     │ (Remote Write)  │
│              │     │              filter)       RW)       │     │                 │
└──────────────┘     └────────────────────────────────────┘     └─────────────────┘
```

**Collector Configuration:**

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    send_batch_size: 10000
    send_batch_max_size: 11000
    timeout: 10s

  memory_limiter:
    check_interval: 1s
    limit_mib: 4096
    spike_limit_mib: 512

  resource:
    attributes:
      - key: cluster
        value: "production-us-east"
        action: upsert

exporters:
  prometheusremotewrite:
    endpoint: "http://victoriametrics:8428/api/v1/write"
    # For cluster mode:
    # endpoint: "http://vminsert:8480/insert/0/prometheus/api/v1/write"
    
    tls:
      insecure: false
      ca_file: /etc/ssl/certs/ca.pem
    
    # Performance tuning
    remote_write_queue:
      num_consumers: 5          # Parallel senders
      queue_size: 10000         # Buffer size
    
    # Retry on failure
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
      max_elapsed_time: 300s
    
    # Resource to label conversion
    resource_to_telemetry_conversion:
      enabled: true             # Converts OTEL resource attributes to metric labels
    
    # External labels added to all metrics
    external_labels:
      environment: production
      region: us-east-1

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [prometheusremotewrite]
```

---

### Pattern 2: OTEL Collector → Native OTLP → VictoriaMetrics

VictoriaMetrics supports **native OTLP ingestion** (since v1.89.0+):

```
┌──────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ Application  │     │     OTEL Collector       │     │    VictoriaMetrics       │
│              │     │                           │     │                          │
│ OTEL SDK     │────▶│ Receiver ──▶ Exporter    │────▶│ /opentelemetry/v1/       │
│ (OTLP push)  │     │ (OTLP)      (OTLP/HTTP) │     │   metrics               │
│              │     │                           │     │ (Native OTLP endpoint)  │
└──────────────┘     └─────────────────────────┘     └─────────────────────────┘
```

**Collector Configuration:**

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    send_batch_size: 5000
    timeout: 5s

exporters:
  otlphttp:
    endpoint: "http://victoriametrics:8428/opentelemetry"
    # For cluster mode:
    # endpoint: "http://vminsert:8480/insert/0/opentelemetry"
    tls:
      insecure: true
    headers:
      "X-Custom-Header": "value"

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp]
```

**VictoriaMetrics OTLP configuration (`/etc/victoriametrics/vm.conf`):**

```bash
# Enable OTLP endpoint
-opentelemetry.usePrometheusNaming=true   # Convert OTEL names to Prometheus conventions
                                           # e.g., http.server.request.duration → http_server_request_duration_seconds

# Sanitize metric names to Prometheus-compatible format
-usePromCompatibleNaming=true
```

---

### Pattern 3: Direct SDK Push → VictoriaMetrics (No Collector)

For simple deployments without a Collector:

```
┌──────────────────────────┐                  ┌─────────────────────────┐
│       Application         │                  │    VictoriaMetrics       │
│                           │                  │                          │
│  OTEL SDK                 │     OTLP/HTTP    │                          │
│  ┌─────────────────────┐ │─────────────────▶│ /opentelemetry/v1/       │
│  │ MeterProvider        │ │                  │   metrics               │
│  │ + OTLPMetricExporter │ │                  │                          │
│  └─────────────────────┘ │                  │                          │
└──────────────────────────┘                  └─────────────────────────┘
```

**Python SDK Example:**

```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

# Direct push to VictoriaMetrics OTLP endpoint
exporter = OTLPMetricExporter(
    endpoint="http://victoriametrics:8428/opentelemetry/v1/metrics",
    headers={"X-Scope-OrgID": "tenant-1"}  # Multi-tenancy header
)

reader = PeriodicExportingMetricReader(
    exporter,
    export_interval_millis=60000  # Push every 60s
)

provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

# Create and use instruments
meter = metrics.get_meter("payment-service")
request_counter = meter.create_counter(
    "http.server.request.count",
    unit="1",
    description="Total HTTP requests"
)
request_duration = meter.create_histogram(
    "http.server.request.duration",
    unit="s",
    description="HTTP request duration"
)
```

---

### Pattern 4: vmagent + OTEL Collector (Hybrid)

Combines vmagent's scraping power with OTEL Collector's processing:

```
                                ┌─────────────────────────┐
                                │      OTEL Collector      │
┌──────────────┐   OTLP Push   │                          │    Remote Write
│ App (OTEL    │───────────────▶│ Receiver → Processor →  │─────────────────┐
│ instrumented)│                │ Exporter (Prom RW)       │                  │
└──────────────┘                └─────────────────────────┘                  │
                                                                              │
┌──────────────┐   Scrape       ┌─────────────────────────┐                  │
│ App (Prom    │◀──────────────│        vmagent           │                  │
│ /metrics)    │                │                          │    Remote Write  │
└──────────────┘                │ • Service Discovery      │─────────────────┐│
                                │ • Relabeling             │                  ││
┌──────────────┐   Scrape       │ • WAL buffer             │                  ││
│ Node Exporter│◀──────────────│ • Fan-out                │                  ││
└──────────────┘                └─────────────────────────┘                  ││
                                                                              ││
                                                                              ▼▼
                                                          ┌─────────────────────────┐
                                                          │    VictoriaMetrics       │
                                                          │    (Cluster)             │
                                                          │                          │
                                                          │  vminsert → vmstorage   │
                                                          │            → vmselect    │
                                                          └─────────────────────────┘
```

**vmagent configuration (`vmagent.yml`):**

```yaml
global:
  scrape_interval: 30s
  external_labels:
    cluster: production
    region: us-east-1

scrape_configs:
  # Scrape Kubernetes pods with prometheus.io annotations
  - job_name: kubernetes-pods
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
        target_label: __address__
        regex: (.+);(.+)
        replacement: $2:$1

  # Scrape node exporters
  - job_name: node-exporter
    kubernetes_sd_configs:
      - role: node
    relabel_configs:
      - action: replace
        target_label: __address__
        replacement: ${1}:9100
        source_labels: [__meta_kubernetes_node_address_InternalIP]

  # Scrape OTEL Collector self-metrics
  - job_name: otel-collector
    static_configs:
      - targets: ['otel-collector:8888']

remote_write:
  - url: http://vminsert:8480/insert/0/prometheus/api/v1/write
    queue_config:
      max_samples_per_send: 10000
      capacity: 50000
      max_shards: 30
    write_relabel_configs:
      - source_labels: [__name__]
        regex: "go_.*"
        action: drop  # Drop Go runtime metrics to reduce cardinality
```

---

## Multi-Tenancy with VictoriaMetrics

### Architecture for Multi-Tenant OTEL

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        Multi-Tenant Architecture                            │
│                                                                             │
│  Tenant A (Team Orders)       Tenant B (Team Payments)                     │
│  ┌───────────────────┐        ┌───────────────────┐                       │
│  │ App + OTEL SDK     │        │ App + OTEL SDK     │                       │
│  │ Header: X-Scope-   │        │ Header: X-Scope-   │                       │
│  │  OrgID: orders     │        │  OrgID: payments   │                       │
│  └─────────┬─────────┘        └─────────┬─────────┘                       │
│            │                              │                                  │
│            ▼                              ▼                                  │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │               OTEL Collector (Gateway)               │                   │
│  │  Routing by tenant header or resource attribute      │                   │
│  └──────────────────────┬──────────────────────────────┘                   │
│                          │                                                   │
│                          ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │                     vmauth                           │                   │
│  │  Routes:                                             │                   │
│  │  • /insert/1/... → vminsert (tenant 1 = orders)    │                   │
│  │  • /insert/2/... → vminsert (tenant 2 = payments)  │                   │
│  │  • /select/1/... → vmselect (tenant 1 queries)     │                   │
│  │  • /select/2/... → vmselect (tenant 2 queries)     │                   │
│  └──────────────────────┬──────────────────────────────┘                   │
│                          │                                                   │
│                          ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │  vminsert → vmstorage (data isolated per tenant)    │                   │
│  └─────────────────────────────────────────────────────┘                   │
└───────────────────────────────────────────────────────────────────────────┘
```

**OTEL Collector with tenant routing:**

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    send_batch_size: 5000
    timeout: 5s

  # Route metrics to different tenant endpoints based on resource attribute
  routing:
    from_attribute: "tenant.id"
    table:
      - value: "orders"
        exporters: [prometheusremotewrite/tenant-orders]
      - value: "payments"
        exporters: [prometheusremotewrite/tenant-payments]
    default_exporters: [prometheusremotewrite/default]

exporters:
  prometheusremotewrite/tenant-orders:
    endpoint: "http://vminsert:8480/insert/1/prometheus/api/v1/write"
  
  prometheusremotewrite/tenant-payments:
    endpoint: "http://vminsert:8480/insert/2/prometheus/api/v1/write"
  
  prometheusremotewrite/default:
    endpoint: "http://vminsert:8480/insert/0/prometheus/api/v1/write"

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch, routing]
      exporters: [prometheusremotewrite/tenant-orders, prometheusremotewrite/tenant-payments, prometheusremotewrite/default]
```

**vmauth configuration (`vmauth.yml`):**

```yaml
users:
  - username: "orders-team"
    password: "secret1"
    url_prefix: "http://vminsert:8480/insert/1/prometheus"
    
  - username: "payments-team"
    password: "secret2"
    url_prefix: "http://vminsert:8480/insert/2/prometheus"

  - username: "grafana-orders"
    password: "readonly1"
    url_prefix: "http://vmselect:8481/select/1/prometheus"
    
  - username: "grafana-payments"
    password: "readonly2"
    url_prefix: "http://vmselect:8481/select/2/prometheus"

  # Header-based routing (for OTEL Collector)
  - bearer_token: "collector-token-abc"
    url_map:
      - src_paths: ["/insert/.*"]
        url_prefix: "http://vminsert:8480"
      - src_paths: ["/select/.*"]
        url_prefix: "http://vmselect:8481"
```

---

## Data Model: OTEL → VictoriaMetrics Mapping

### How OTEL Metrics Become VM Time Series

```
┌─────────────────────────────────────────────────────────────────────────┐
│                OTEL Metric → VictoriaMetrics Mapping                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  OTEL Metric:                                                            │
│  {                                                                        │
│    name: "http.server.request.duration"                                  │
│    unit: "s"                                                              │
│    type: Histogram                                                        │
│    resource: { service.name: "orders", k8s.namespace: "prod" }           │
│    attributes: { http.method: "GET", http.route: "/api/orders" }         │
│    buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]│
│  }                                                                        │
│                                                                           │
│  ──────────── Conversion (with -usePromCompatibleNaming) ──────────────  │
│                                                                           │
│  VictoriaMetrics Time Series:                                            │
│                                                                           │
│  http_server_request_duration_seconds_bucket{                            │
│    service="orders",                                                      │
│    namespace="prod",                                                      │
│    method="GET",                                                          │
│    route="/api/orders",                                                   │
│    le="0.005"                                                             │
│  } = 150                                                                  │
│                                                                           │
│  http_server_request_duration_seconds_bucket{..., le="0.01"} = 450      │
│  http_server_request_duration_seconds_bucket{..., le="0.025"} = 820     │
│  ...                                                                      │
│  http_server_request_duration_seconds_bucket{..., le="+Inf"} = 1500     │
│  http_server_request_duration_seconds_sum{...} = 425.7                   │
│  http_server_request_duration_seconds_count{...} = 1500                  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Naming Conventions

| OTEL Name | VM Name (with Prom naming) | Rule Applied |
|-----------|----------------------------|--------------|
| `http.server.request.duration` (unit: s) | `http_server_request_duration_seconds` | dots → underscores + unit suffix |
| `http.server.active_requests` (unit: 1) | `http_server_active_requests` | unitless = no suffix |
| `system.cpu.utilization` (unit: 1) | `system_cpu_utilization_ratio` | ratio suffix for 0-1 values |
| `process.runtime.jvm.memory.usage` (unit: By) | `process_runtime_jvm_memory_usage_bytes` | By → bytes |
| `custom.counter` (type: Sum, monotonic) | `custom_counter_total` | _total suffix for counters |

---

## MetricsQL — Enhanced Querying

VictoriaMetrics extends PromQL with MetricsQL, offering powerful additional functions:

### Key MetricsQL Enhancements

```promql
# ── Range Functions (not in PromQL) ──

# Median over time (PromQL only has quantile_over_time)
median_over_time(http_request_duration_seconds[5m])

# Running total (cumulative sum)
running_sum(rate(http_requests_total[1m]))

# Lag detection — time since last sample
scrape_series_current_lag(up{service="orders"})

# ── Label Manipulation ──

# Keep only specific labels (PromQL needs complex group_left)
label_keep(http_requests_total, "method", "status")

# Replace label values with regex
label_replace(http_requests_total, "short_service", "$1", "service", "(.{1,10}).*")

# ── Rollup Functions ──

# Increase that handles counter resets properly
increase_pure(http_requests_total[5m])

# Rate with automatic step alignment
rate(http_requests_total[5m:1m])

# ── Multi-Range ──

# Compare current value to value 1 day ago
http_requests_total - http_requests_total offset 1d

# Forecast using linear regression
predict_linear(disk_usage_bytes[7d], 30*24*3600)  # 30-day forecast
```

### Querying OTEL Metrics in Grafana via VM

```promql
# Request rate by service (OTEL-generated metrics)
sum(rate(http_server_request_duration_seconds_count{
  environment="production"
}[5m])) by (service, method)

# P99 latency from OTEL histogram
histogram_quantile(0.99,
  sum(rate(http_server_request_duration_seconds_bucket{
    service="payment-service"
  }[5m])) by (le, route)
)

# Error rate percentage
100 * sum(rate(http_server_request_duration_seconds_count{
  http_response_status_code=~"5.."
}[5m])) by (service)
/
sum(rate(http_server_request_duration_seconds_count[5m])) by (service)

# Apdex score (satisfied < 0.5s, tolerating < 2s)
(
  sum(rate(http_server_request_duration_seconds_bucket{le="0.5"}[5m])) by (service)
  +
  sum(rate(http_server_request_duration_seconds_bucket{le="2"}[5m])) by (service)
) / 2
/
sum(rate(http_server_request_duration_seconds_count[5m])) by (service)
```

---

## Retention and Downsampling

### Configuring Retention

```bash
# Single node
victoria-metrics \
  -retentionPeriod=90d \             # Keep raw data for 90 days
  -storage.minFreeDiskSpaceBytes=1GB  # Stop ingestion if disk < 1GB free

# Cluster mode (per vmstorage node)
vmstorage \
  -retentionPeriod=1y \              # 1 year retention
  -dedup.minScrapeInterval=30s       # Dedup samples within 30s window
```

### Downsampling with vmagent + Recording Rules

```yaml
# vmrule configuration for downsampling
groups:
  - name: otel_downsampling
    interval: 5m
    rules:
      # Aggregate 5-minute request rate per service
      - record: service:http_request_rate:5m
        expr: sum(rate(http_server_request_duration_seconds_count[5m])) by (service, environment)
      
      # Pre-compute p99 latency
      - record: service:http_request_latency_p99:5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_server_request_duration_seconds_bucket[5m])) by (le, service)
          )
      
      # Error rate pre-computation
      - record: service:http_error_rate:5m
        expr: |
          sum(rate(http_server_request_duration_seconds_count{
            http_response_status_code=~"5.."
          }[5m])) by (service)
          /
          sum(rate(http_server_request_duration_seconds_count[5m])) by (service)
```

### Multi-Tier Retention Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Multi-Tier Retention Strategy                       │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ Tier 1: Hot Storage (NVMe SSD)                                    ││
│  │ • Retention: 7 days                                               ││
│  │ • Data: Raw metrics at full resolution (30s intervals)           ││
│  │ • Use case: Real-time dashboards, alerting, debugging            ││
│  └──────────────────────────┬───────────────────────────────────────┘│
│                              │ (downsampled via recording rules)       │
│  ┌──────────────────────────▼───────────────────────────────────────┐│
│  │ Tier 2: Warm Storage (SSD)                                        ││
│  │ • Retention: 90 days                                              ││
│  │ • Data: 5-minute aggregated (avg, min, max, count)               ││
│  │ • Use case: Trend analysis, capacity planning                    ││
│  └──────────────────────────┬───────────────────────────────────────┘│
│                              │ (further aggregated)                    │
│  ┌──────────────────────────▼───────────────────────────────────────┐│
│  │ Tier 3: Cold Storage (HDD / Object Storage)                       ││
│  │ • Retention: 2 years                                              ││
│  │ • Data: Hourly aggregated (service-level summaries)              ││
│  │ • Use case: Year-over-year comparison, compliance                ││
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

---

## Deduplication Strategies

When running HA pairs of OTEL Collectors or vmagents, duplicate data arrives at VM:

```
┌────────────────┐                    ┌─────────────────────────┐
│ OTEL Collector │────── write ──────▶│                          │
│  (Primary)     │                    │   VictoriaMetrics        │
└────────────────┘                    │                          │
                                      │   -dedup.minScrapeInterval=30s
┌────────────────┐                    │                          │
│ OTEL Collector │────── write ──────▶│   Keeps ONE sample per  │
│  (Replica)     │                    │   30s window per series  │
└────────────────┘                    └─────────────────────────┘
```

**Configuration:**

```bash
# On vmstorage nodes (cluster) or single-node
-dedup.minScrapeInterval=30s

# How it works:
# If two identical samples arrive for the same time series within a 30s window,
# only one is stored. This handles:
# - HA collector pairs sending the same data
# - vmagent replicas scraping the same targets
# - Network retries causing duplicate pushes
```

**OTEL Collector HA Configuration:**

```yaml
# collector-1.yaml and collector-2.yaml (identical config)
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  prometheusremotewrite:
    endpoint: "http://vminsert:8480/insert/0/prometheus/api/v1/write"
    # Both collectors push the same data
    # VictoriaMetrics deduplicates at storage level

# Load balancer distributes apps across both collectors
# If one collector dies, the other handles all traffic
# When both are healthy, duplicate data is written but deduped
```

---

## High Availability Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    Production HA Architecture                                  │
│                                                                                │
│     ┌───────────────────────────────────────────────────────┐                 │
│     │                  Applications                          │                 │
│     │         (OTEL SDK → OTLP push)                        │                 │
│     └──────────────────────┬────────────────────────────────┘                 │
│                             │                                                  │
│                             ▼                                                  │
│     ┌────────────────────────────────────────────────┐                        │
│     │          Load Balancer (L4/TCP)                  │                        │
│     │          (health check: /healthz on :13133)     │                        │
│     └───────┬─────────────────────────┬──────────────┘                        │
│             │                          │                                       │
│             ▼                          ▼                                       │
│     ┌──────────────┐          ┌──────────────┐                                │
│     │ OTEL Collector│          │ OTEL Collector│                                │
│     │  (Pod 1)     │          │  (Pod 2)     │                                │
│     │  HPA: 2-10   │          │  HPA: 2-10   │                                │
│     └──────┬───────┘          └──────┬───────┘                                │
│            │                          │                                        │
│            └──────────┬───────────────┘                                        │
│                       │                                                        │
│                       ▼                                                        │
│     ┌────────────────────────────────────────────────┐                        │
│     │              vmauth (HA pair)                    │                        │
│     │  • Authentication                               │                        │
│     │  • Load balancing across vminsert nodes         │                        │
│     │  • Automatic failover                           │                        │
│     └───────┬─────────────────────────┬──────────────┘                        │
│             │                          │                                       │
│             ▼                          ▼                                       │
│     ┌──────────────┐          ┌──────────────┐                                │
│     │  vminsert-1  │          │  vminsert-2  │                                │
│     │  (stateless) │          │  (stateless) │                                │
│     └──────┬───────┘          └──────┬───────┘                                │
│            │  replicationFactor=2     │                                        │
│            └──────────┬───────────────┘                                        │
│                       │                                                        │
│            ┌──────────┼───────────────┐                                        │
│            ▼          ▼               ▼                                        │
│     ┌───────────┐ ┌───────────┐ ┌───────────┐                                │
│     │vmstorage-1│ │vmstorage-2│ │vmstorage-3│                                │
│     │ (NVMe)    │ │ (NVMe)    │ │ (NVMe)    │                                │
│     │ AZ-1      │ │ AZ-2      │ │ AZ-3      │                                │
│     └───────────┘ └───────────┘ └───────────┘                                │
│                                                                                │
│     ┌──────────────┐          ┌──────────────┐                                │
│     │  vmselect-1  │          │  vmselect-2  │  ← Grafana queries here       │
│     │  (stateless) │          │  (stateless) │                                │
│     └──────────────┘          └──────────────┘                                │
│                                                                                │
│     ┌─────────────────────────────────────────────┐                           │
│     │  vmalert (alerting + recording rules)        │                           │
│     │  • Evaluates MetricsQL alert expressions     │                           │
│     │  • Sends alerts to Alertmanager              │                           │
│     │  • Writes recording rule results back to VM  │                           │
│     └─────────────────────────────────────────────┘                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Kubernetes Deployment

### Helm Chart (victoria-metrics-k8s-stack)

```bash
helm repo add vm https://victoriametrics.github.io/helm-charts/
helm repo update

helm install victoria vm/victoria-metrics-k8s-stack \
  --namespace monitoring \
  --create-namespace \
  --values values.yaml
```

**values.yaml:**

```yaml
# VictoriaMetrics Cluster
vmcluster:
  enabled: true
  spec:
    retentionPeriod: "90d"
    replicationFactor: 2
    
    vmstorage:
      replicaCount: 3
      storage:
        volumeClaimTemplate:
          spec:
            storageClassName: gp3-nvme
            resources:
              requests:
                storage: 500Gi
      resources:
        requests:
          cpu: "2"
          memory: "8Gi"
        limits:
          cpu: "4"
          memory: "16Gi"
      extraArgs:
        dedup.minScrapeInterval: "30s"
    
    vminsert:
      replicaCount: 2
      resources:
        requests:
          cpu: "1"
          memory: "2Gi"
      extraArgs:
        maxLabelsPerTimeseries: "40"
    
    vmselect:
      replicaCount: 2
      resources:
        requests:
          cpu: "2"
          memory: "4Gi"
      extraArgs:
        search.maxQueryDuration: "60s"
        search.maxSeries: "100000"

# vmagent for scraping
vmagent:
  enabled: true
  spec:
    scrapeInterval: "30s"
    extraArgs:
      remoteWrite.maxDiskUsagePerURL: "2GB"  # WAL buffer
      promscrape.maxScrapeSize: "32MB"
    additionalScrapeConfigs:
      name: additional-scrape-configs
      key: scrape-configs.yaml

# vmalert for alerting
vmalert:
  enabled: true
  spec:
    evaluationInterval: "30s"
    externalLabels:
      cluster: production
      environment: prod

# Grafana with VM datasource
grafana:
  enabled: true
  additionalDataSources:
    - name: VictoriaMetrics
      type: prometheus
      url: http://vmselect-victoria-metrics:8481/select/0/prometheus
      isDefault: true
      jsonData:
        timeInterval: "30s"

# OTEL Collector integration
opentelemetry-collector:
  enabled: true
  config:
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
    processors:
      batch:
        send_batch_size: 10000
        timeout: 10s
    exporters:
      prometheusremotewrite:
        endpoint: http://vminsert-victoria-metrics:8480/insert/0/prometheus/api/v1/write
    service:
      pipelines:
        metrics:
          receivers: [otlp]
          processors: [batch]
          exporters: [prometheusremotewrite]
```

---

## Alerting with vmalert + OTEL Metrics

```yaml
# alerting-rules.yaml
groups:
  - name: otel_service_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          sum(rate(http_server_request_duration_seconds_count{
            http_response_status_code=~"5.."
          }[5m])) by (service, environment)
          /
          sum(rate(http_server_request_duration_seconds_count[5m])) by (service, environment)
          > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          description: "Error rate is {{ $value | humanizePercentage }} for {{ $labels.service }}"
          runbook: "https://runbooks.internal/high-error-rate"
      
      # High latency (P99 > 2s)
      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_server_request_duration_seconds_bucket[5m])) by (le, service)
          ) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency > 2s on {{ $labels.service }}"
          description: "P99 latency is {{ $value }}s"
      
      # Service down (no metrics received)
      - alert: ServiceDown
        expr: |
          absent_over_time(
            http_server_request_duration_seconds_count{service="payment-service"}[5m]
          )
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "payment-service is not reporting metrics"
```

---

## Performance Tuning

### VictoriaMetrics Tuning for OTEL Workloads

```bash
# vmstorage optimization for high-cardinality OTEL metrics
vmstorage \
  -retentionPeriod=90d \
  -dedup.minScrapeInterval=30s \
  -search.maxUniqueTimeseries=5000000 \      # Max series in a single query
  -storage.cacheSizeIndexDBDataBlocks=512MB \ # Index cache
  -storage.cacheSizeIndexDBIndexBlocks=256MB \# Tag index cache  
  -bigMergeConcurrency=2 \                    # Background merge threads
  -smallMergeConcurrency=4

# vminsert optimization
vminsert \
  -maxLabelsPerTimeseries=40 \       # Reject metrics with too many labels
  -maxLabelValueLen=1024 \           # Max label value length
  -disableRerouting=false            # Reroute to healthy vmstorage nodes

# vmselect optimization
vmselect \
  -search.maxQueryDuration=60s \     # Query timeout
  -search.maxSeries=500000 \         # Max series per query
  -search.maxPointsPerTimeseries=86400 \  # Max points returned per series
  -cacheExpireDuration=30s                # Query cache duration
```

### OTEL Collector Tuning for VM Backend

```yaml
exporters:
  prometheusremotewrite:
    endpoint: "http://vminsert:8480/insert/0/prometheus/api/v1/write"
    
    # Batching — critical for throughput
    remote_write_queue:
      num_consumers: 10          # Parallel HTTP senders (increase for high volume)
      queue_size: 50000          # Internal queue before dropping
    
    # Timeout tuning
    timeout: 30s                 # VM can handle large batches; allow time
    
    # Compression
    compression: snappy          # Reduce network bandwidth
    
    # WAL for durability (if supported by exporter version)
    wal:
      directory: /var/lib/otel/wal
      buffer_size: 300           # MB
      truncate_frequency: 60s
```

---

## Comparison: OTEL → VictoriaMetrics vs Other Backends

| Feature | VictoriaMetrics | Prometheus | Thanos | Mimir (Grafana) |
|---------|----------------|------------|--------|-----------------|
| **OTLP Native** | Yes (v1.89+) | No | No | Yes |
| **Remote Write** | Yes | Yes (receive) | Yes (receive) | Yes |
| **Compression** | ~0.4 bytes/pt | ~1.6 bytes/pt | ~1.5 bytes/pt | ~1.0 bytes/pt |
| **Multi-tenancy** | Built-in (accountID) | No | Partial | Yes |
| **Horizontal Scale** | vminsert/vmstorage/vmselect | No (single node) | Sidecar + Store | Ingesters + Store |
| **Deduplication** | Built-in | No | At query time | At compaction |
| **Downsampling** | Recording rules | Recording rules | Automatic (5m, 1h) | Automatic |
| **Query Language** | MetricsQL (PromQL superset) | PromQL | PromQL | PromQL |
| **HA Approach** | Replication factor | Separate instances | Redundant sidecars | Replication factor |
| **Object Storage** | Not needed (local disk) | Not applicable | Required (S3/GCS) | Required (S3/GCS) |
| **Operational Complexity** | Low-Medium | Low | High | High |
| **Cost Efficiency** | Very High | Medium | Medium | Medium |

---

## Complete Production Configuration

### End-to-End: Application → OTEL → VictoriaMetrics → Grafana

```yaml
# ─── OTEL Collector (otel-collector-config.yaml) ───────────────────────────

receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_recv_msg_size_mib: 16
      http:
        endpoint: 0.0.0.0:4318

  # Also receive from Prometheus-instrumented apps
  prometheus:
    config:
      scrape_configs:
        - job_name: 'legacy-apps'
          kubernetes_sd_configs:
            - role: pod
          relabel_configs:
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
              action: keep
              regex: true

processors:
  batch:
    send_batch_size: 10000
    send_batch_max_size: 11000
    timeout: 10s

  memory_limiter:
    check_interval: 1s
    limit_mib: 4096
    spike_limit_mib: 1024

  resource:
    attributes:
      - key: cluster
        value: "prod-us-east-1"
        action: upsert
      - key: collector.version
        value: "0.96.0"
        action: upsert

  # Drop high-cardinality debug metrics in production
  filter/drop-debug:
    metrics:
      exclude:
        match_type: regexp
        metric_names:
          - ".*_debug_.*"
          - "go_.*"
          - "process_.*"

  # Limit label cardinality
  transform:
    metric_statements:
      - context: datapoint
        statements:
          # Truncate URL paths to reduce cardinality
          - replace_pattern(attributes["url.path"], "^(/api/v[0-9]+/[^/]+).*", "$$1/{id}")

exporters:
  # Primary: VictoriaMetrics cluster
  prometheusremotewrite/victoria:
    endpoint: "http://vminsert.monitoring:8480/insert/0/prometheus/api/v1/write"
    resource_to_telemetry_conversion:
      enabled: true
    remote_write_queue:
      num_consumers: 10
      queue_size: 50000
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
    external_labels:
      cluster: prod-us-east-1
      environment: production

  # Backup: Second VM cluster (DR)
  prometheusremotewrite/victoria-dr:
    endpoint: "http://vminsert.monitoring-dr:8480/insert/0/prometheus/api/v1/write"
    resource_to_telemetry_conversion:
      enabled: true

extensions:
  health_check:
    endpoint: 0.0.0.0:13133
  
  zpages:
    endpoint: 0.0.0.0:55679

service:
  extensions: [health_check, zpages]
  telemetry:
    metrics:
      address: 0.0.0.0:8888
  pipelines:
    metrics:
      receivers: [otlp, prometheus]
      processors: [memory_limiter, resource, filter/drop-debug, transform, batch]
      exporters: [prometheusremotewrite/victoria, prometheusremotewrite/victoria-dr]
```

---

## Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| **Metrics not appearing in VM** | OTEL metric names not converted to Prom format | Enable `-usePromCompatibleNaming=true` on VM |
| **High cardinality explosion** | OTEL resource attributes all becoming labels | Use `resource_to_telemetry_conversion` selectively; filter in processor |
| **Duplicate samples** | HA collectors sending same data | Enable `-dedup.minScrapeInterval=30s` on vmstorage |
| **Slow queries on VM** | Too many time series matching | Add more specific label selectors; pre-aggregate with recording rules |
| **VM OOM** | All data in hot storage | Increase retention-based downsampling; add more vmstorage nodes |
| **OTLP ingestion errors** | Delta temporality sent to VM | OTEL Collector with `cumulativetodelta` processor or set SDK to cumulative |
| **Label name conflicts** | OTEL attribute names with dots | VM auto-converts dots to underscores; ensure Grafana queries use underscores |
| **Missing histograms** | Exponential histograms not supported | Use explicit bucket histograms or enable conversion in Collector |
| **Stale series in VM** | Pods restarting frequently | Set appropriate `-search.maxStalenessInterval` on vmselect |
| **Write amplification** | Replication factor too high | Balance RF with storage cost; RF=2 is usually sufficient |

---

## Migration from Prometheus to VictoriaMetrics with OTEL

### Phase 1: Parallel Write

```
┌──────────────┐     ┌────────────────────────┐     ┌──────────────────┐
│ Applications │     │    OTEL Collector       │     │  Prometheus      │
│ (OTEL SDK)   │────▶│                         │────▶│  (existing)      │
└──────────────┘     │  Exports to BOTH:       │     └──────────────────┘
                     │  • Prometheus (existing) │
                     │  • VictoriaMetrics (new) │     ┌──────────────────┐
                     │                         │────▶│ VictoriaMetrics   │
                     └────────────────────────┘     │  (new)            │
                                                     └──────────────────┘
```

### Phase 2: Validation

```promql
# Compare query results between Prometheus and VM
# Run same query against both and verify < 1% difference

# On Prometheus:
sum(rate(http_requests_total[5m])) by (service)

# On VictoriaMetrics (same query, different datasource):
sum(rate(http_requests_total[5m])) by (service)
```

### Phase 3: Cutover

```
┌──────────────┐     ┌────────────────────────┐     ┌──────────────────┐
│ Applications │     │    OTEL Collector       │     │ VictoriaMetrics   │
│ (OTEL SDK)   │────▶│                         │────▶│  (primary)        │
└──────────────┘     │  Exports to:            │     └──────────────────┘
                     │  • VictoriaMetrics only  │
                     └────────────────────────┘     ┌──────────────────┐
                                                     │  Prometheus       │
                                                     │  (decommission)   │
                                                     └──────────────────┘
```

### Phase 4: Advanced Features

After migration, leverage VM-specific features not available in Prometheus:
- **Streaming aggregation** (vmagent)
- **MetricsQL** extensions (absent_over_time, range_quantile, etc.)
- **Multi-retention** per tenant
- **Anomaly detection** (vmanomaly enterprise feature)
- **Built-in downsampling**
