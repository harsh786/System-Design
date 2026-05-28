# OpenTelemetry with Prometheus

## Why Prometheus + OTEL?

Prometheus is the de facto standard for metrics in cloud-native environments. OpenTelemetry does not replace Prometheus — it **complements** it by providing:

1. A unified instrumentation layer (instrument once, export anywhere)
2. Correlation between metrics, logs, and traces
3. A vendor-neutral pipeline for metrics collection and routing
4. Push-based export for environments where pull/scrape doesn't work

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TWO WORLDS, ONE PIPELINE                               │
│                                                                           │
│   PROMETHEUS WORLD              OTEL WORLD                               │
│   ┌──────────────┐            ┌──────────────────┐                      │
│   │ Pull (Scrape) │            │ Push (OTLP/gRPC) │                      │
│   │ PromQL        │            │ Unified SDK       │                      │
│   │ /metrics      │            │ Traces + Metrics  │                      │
│   │ Label-based   │            │ Attribute-based   │                      │
│   └──────┬───────┘            └────────┬─────────┘                      │
│          │                              │                                │
│          └──────────┬───────────────────┘                                │
│                     ▼                                                    │
│          ┌──────────────────────┐                                        │
│          │   OTEL COLLECTOR     │                                        │
│          │   (Bridge Layer)     │                                        │
│          └──────────┬───────────┘                                        │
│                     │                                                    │
│          ┌──────────┴───────────────────────┐                            │
│          ▼                                   ▼                           │
│   ┌──────────────┐                  ┌──────────────────┐                │
│   │ Prometheus   │                  │ VictoriaMetrics   │                │
│   │ /Thanos/Mimir│                  │ /Cortex/M3        │                │
│   └──────────────┘                  └──────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model Comparison

### Prometheus Data Model

```
# Prometheus metric format (exposition format)
http_requests_total{method="GET", path="/api/users", status="200"} 15234 1716900060000

# Structure:
# metric_name{label1="val1", label2="val2"} value timestamp
```

Key characteristics:
- **Time series** identified by metric name + label set
- **Labels** are key-value string pairs (flat)
- **Types**: Counter, Gauge, Histogram, Summary
- Implicit `job` and `instance` labels from scrape config
- Pull-based model: Prometheus scrapes `/metrics` endpoints

### OpenTelemetry Data Model

```json
{
  "resourceMetrics": [{
    "resource": {
      "attributes": {
        "service.name": "user-service",
        "service.version": "1.2.0",
        "host.name": "prod-01"
      }
    },
    "scopeMetrics": [{
      "scope": { "name": "com.myapp.http", "version": "1.0.0" },
      "metrics": [{
        "name": "http.server.request.duration",
        "unit": "s",
        "histogram": {
          "dataPoints": [{
            "attributes": { "http.method": "GET", "http.route": "/api/users" },
            "startTimeUnixNano": "1716900000000000000",
            "timeUnixNano": "1716900060000000000",
            "count": 1500,
            "sum": 425.7,
            "bucketCounts": [200, 500, 400, 250, 100, 50],
            "explicitBounds": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
          }]
        }
      }]
    }]
  }]
}
```

Key characteristics:
- **Resource** describes the entity producing metrics (service metadata)
- **Scope** identifies the instrumentation library
- **Attributes** are typed (string, int, float, bool, array)
- **Types**: Sum (monotonic/non-monotonic), Gauge, Histogram, ExponentialHistogram, Summary
- Push-based model: application pushes via OTLP
- **Temporality**: Delta or Cumulative aggregation

### Mapping Table

| Prometheus | OpenTelemetry | Notes |
|-----------|---------------|-------|
| Counter | Sum (monotonic, cumulative) | Both track monotonically increasing values |
| Gauge | Gauge | Direct mapping |
| Histogram | Histogram | OTEL supports exponential histograms too |
| Summary | Summary | Both deprecated in favor of histograms |
| Labels | Attributes | OTEL attributes are typed, Prom labels are strings |
| `job` label | `service.name` resource attribute | Resource-level in OTEL |
| `instance` label | `service.instance.id` + `host.name` | Resource-level in OTEL |
| Metric name | `name` field in Metric | OTEL uses dots, Prom uses underscores |
| `_total` suffix | Monotonic Sum | Convention difference |
| `_bucket`, `_count`, `_sum` | Single Histogram data point | OTEL is more compact |

---

## Integration Pattern 1: Prometheus Receiver (Scraping)

The Collector scrapes Prometheus endpoints, converting metrics to OTEL format for unified processing.

```
┌────────────────────┐     ┌────────────────────┐     ┌─────────────────┐
│  App with /metrics │     │  App with /metrics │     │ Node Exporter   │
│  (Prometheus SDK)  │     │  (Prometheus SDK)  │     │                 │
└─────────┬──────────┘     └─────────┬──────────┘     └────────┬────────┘
          │ :8080/metrics            │ :8080/metrics            │ :9100
          │                          │                          │
          └──────────────────────────┼──────────────────────────┘
                                     │ scrape
                          ┌──────────┴──────────┐
                          │   OTEL COLLECTOR     │
                          │                      │
                          │  prometheus receiver │
                          │  (replaces Prom      │
                          │   server scraping)   │
                          └──────────┬───────────┘
                                     │ OTEL pipeline
                                     ▼
                          ┌──────────────────────┐
                          │ prometheusremotewrite │
                          │      exporter        │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  Prometheus/Thanos/   │
                          │  VictoriaMetrics/Mimir│
                          └──────────────────────┘
```

### Configuration

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        # Scrape application metrics
        - job_name: 'user-service'
          scrape_interval: 15s
          scrape_timeout: 10s
          metrics_path: '/metrics'
          static_configs:
            - targets: ['user-service:8080']
              labels:
                environment: 'production'
                team: 'platform'

        # Scrape node exporters
        - job_name: 'node-exporter'
          scrape_interval: 30s
          static_configs:
            - targets: ['node1:9100', 'node2:9100', 'node3:9100']

        # Kubernetes service discovery
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
            - source_labels: [__meta_kubernetes_namespace]
              action: replace
              target_label: namespace
            - source_labels: [__meta_kubernetes_pod_name]
              action: replace
              target_label: pod

processors:
  batch:
    send_batch_size: 10000
    timeout: 10s

  # Convert Prometheus metric names to OTEL conventions
  metricstransform:
    transforms:
      - include: http_requests_total
        action: update
        new_name: http.server.request.count
      - include: http_request_duration_seconds
        action: update
        new_name: http.server.request.duration

exporters:
  prometheusremotewrite:
    endpoint: "http://victoriametrics:8428/api/v1/write"
    resource_to_telemetry_conversion:
      enabled: true  # Converts OTEL resource attributes to Prometheus labels

service:
  pipelines:
    metrics:
      receivers: [prometheus]
      processors: [batch, metricstransform]
      exporters: [prometheusremotewrite]
```

---

## Integration Pattern 2: OTEL SDK Push → Prometheus Remote Write

Applications instrumented with OTEL SDK push metrics through the Collector, which exports via Prometheus Remote Write.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Application (OTEL SDK Instrumented)                                     │
│                                                                          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐     │
│  │ MeterProvider   │  │  Histogram:       │  │  Counter:          │     │
│  │                 │  │  request.duration │  │  request.count     │     │
│  │ OTLPExporter    │  │                  │  │                    │     │
│  └────────┬────────┘  └──────────────────┘  └───────────────────┘     │
└───────────┼──────────────────────────────────────────────────────────────┘
            │ OTLP gRPC push
            ▼
┌──────────────────────────────────────────┐
│         OTEL COLLECTOR                    │
│                                           │
│  Receiver: otlp                          │
│  Processor: batch, memory_limiter        │
│  Exporter: prometheusremotewrite         │
└────────────────────┬─────────────────────┘
                     │ Prometheus Remote Write
                     │ (HTTP POST, protobuf/snappy)
                     ▼
┌──────────────────────────────────────────┐
│        PROMETHEUS / THANOS / VM          │
│                                           │
│  Stores as time-series                   │
│  Query with PromQL                       │
└──────────────────────────────────────────┘
```

### Configuration

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 1024
    spike_limit_mib: 256

  batch:
    send_batch_size: 10000
    timeout: 10s

  # Add resource attributes as metric labels
  resource:
    attributes:
      - key: environment
        value: production
        action: upsert

exporters:
  prometheusremotewrite:
    endpoint: "http://prometheus:9090/api/v1/write"
    tls:
      insecure: false
      cert_file: /certs/client.crt
      key_file: /certs/client.key
    headers:
      X-Scope-OrgID: "tenant-1"  # Multi-tenant (Cortex/Mimir)
    resource_to_telemetry_conversion:
      enabled: true
    # Retry configuration
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
      max_elapsed_time: 300s
    # Queue for backpressure handling
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 5000

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch, resource]
      exporters: [prometheusremotewrite]
```

---

## Integration Pattern 3: Prometheus Exporter (Collector exposes /metrics)

The Collector itself exposes a `/metrics` endpoint that Prometheus can scrape. Useful when you want Prometheus to remain the scraper.

```
┌───────────────┐        ┌───────────────────────────┐       ┌──────────────┐
│  Application  │ OTLP   │      OTEL COLLECTOR       │scrape │  Prometheus  │
│  (OTEL SDK)   │───────▶│                           │◀──────│  Server      │
│               │ push   │  Receiver: otlp           │       │              │
└───────────────┘        │  Exporter: prometheus     │       │  Stores TSDB │
                         │    endpoint: :8889        │       │  PromQL      │
                         └───────────────────────────┘       └──────────────┘
```

### Configuration

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
    namespace: "myapp"                    # Prefix for all metrics
    const_labels:                         # Static labels added to all metrics
      environment: "production"
    send_timestamps: true
    metric_expiration: 5m                 # Remove stale metrics after 5 minutes
    resource_to_telemetry_conversion:
      enabled: true
    enable_open_metrics: true             # Enable OpenMetrics format

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

Then in Prometheus `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'otel-collector'
    scrape_interval: 15s
    static_configs:
      - targets: ['otel-collector:8889']
```

---

## Metric Name Conversion

When metrics flow between Prometheus and OTEL, names are converted:

### OTEL → Prometheus

| OTEL Name | OTEL Type | Prometheus Name | Prometheus Type |
|-----------|-----------|-----------------|-----------------|
| `http.server.request.duration` | Histogram | `http_server_request_duration_seconds_bucket/count/sum` | histogram |
| `http.server.request.count` | Sum (monotonic) | `http_server_request_count_total` | counter |
| `system.cpu.utilization` | Gauge | `system_cpu_utilization_ratio` | gauge |
| `process.runtime.jvm.memory.usage` | Sum (non-monotonic) | `process_runtime_jvm_memory_usage_bytes` | gauge |

Rules:
1. Dots (`.`) → underscores (`_`)
2. Monotonic sums get `_total` suffix
3. Unit is appended: `s` → `_seconds`, `By` → `_bytes`, `1` → `_ratio`
4. Histograms generate `_bucket`, `_count`, `_sum` series

### Prometheus → OTEL

| Prometheus Name | Prometheus Type | OTEL Name | OTEL Type |
|-----------------|-----------------|-----------|-----------|
| `http_requests_total` | counter | `http_requests` | Sum (monotonic, cumulative) |
| `temperature_celsius` | gauge | `temperature_celsius` | Gauge |
| `request_duration_seconds` | histogram | `request_duration_seconds` | Histogram |

Rules:
1. `_total` suffix is stripped for Sum metrics
2. `_bucket`, `_count`, `_sum` series are merged into one Histogram
3. Underscores remain (no conversion to dots by default)

---

## Exemplars: Linking Metrics to Traces

Exemplars are references from a metric data point to a specific trace, enabling drill-down from high-level metrics to detailed traces.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXEMPLAR FLOW                                      │
│                                                                           │
│  ┌─────────────────────────────────┐                                    │
│  │   Grafana Dashboard              │                                    │
│  │                                  │                                    │
│  │   p99 latency spike at 14:32 ─────── Click exemplar dot             │
│  │   ████████████████████▓           │              │                    │
│  └──────────────────────────────────┘              │                    │
│                                                     ▼                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │   Jaeger/Tempo Trace View                                         │  │
│  │                                                                    │  │
│  │   TraceID: abc123... (the slow request)                           │  │
│  │   ├── API Gateway (12ms)                                          │  │
│  │   ├── Auth Service (45ms)                                         │  │
│  │   └── Database Query (890ms) ← ROOT CAUSE                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### How Exemplars Work

```json
{
  "name": "http.server.request.duration",
  "histogram": {
    "dataPoints": [{
      "count": 1500,
      "sum": 425.7,
      "bucketCounts": [200, 500, 400, 250, 100, 50],
      "explicitBounds": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
      "exemplars": [
        {
          "filteredAttributes": { "http.status_code": 500 },
          "timeUnixNano": "1716900045000000000",
          "value": 0.892,
          "traceId": "5b8aa5a2d2c872e8321cf37308d69df2",
          "spanId": "051581bf3cb55c13"
        }
      ]
    }]
  }
}
```

### SDK Configuration for Exemplars

```java
// Java — enable exemplars on histograms
SdkMeterProvider meterProvider = SdkMeterProvider.builder()
    .registerMetricReader(
        PeriodicMetricReader.builder(otlpExporter)
            .setInterval(Duration.ofSeconds(60))
            .build()
    )
    .setExemplarFilter(ExemplarFilter.traceBased())  // Attach trace context
    .build();
```

### Prometheus Remote Write with Exemplars

```yaml
exporters:
  prometheusremotewrite:
    endpoint: "http://prometheus:9090/api/v1/write"
    resource_to_telemetry_conversion:
      enabled: true
    # Exemplars are included automatically in remote write payload
```

Prometheus storage must have exemplars enabled:

```yaml
# prometheus.yml
storage:
  exemplars:
    max_exemplars: 100000
```

---

## Temporality: Delta vs Cumulative

A critical concept when bridging OTEL and Prometheus.

### Cumulative (Prometheus default)

Each data point contains the running total since process start:

```
t0: counter = 10   (10 requests since start)
t1: counter = 25   (25 requests since start, delta = 15)
t2: counter = 42   (42 requests since start, delta = 17)
```

Prometheus REQUIRES cumulative temporality. It computes rates using `rate()` / `increase()`.

### Delta (OTEL SDK option)

Each data point contains the change since the last report:

```
t0: counter = 10   (10 new requests in this interval)
t1: counter = 15   (15 new requests in this interval)
t2: counter = 17   (17 new requests in this interval)
```

Some backends (Datadog, CloudWatch) prefer delta. Prometheus does NOT support delta.

### Collector Handles Conversion

```yaml
exporters:
  prometheusremotewrite:
    endpoint: "http://prometheus:9090/api/v1/write"
    # The exporter automatically converts delta → cumulative for Prometheus
    # This is handled internally using cumulative-to-delta or delta-to-cumulative processors
```

The OTEL Collector's Prometheus Remote Write exporter automatically handles temporality conversion when needed. If your SDK sends delta metrics, the exporter accumulates them into cumulative before writing.

---

## Migration Strategy: From Prometheus SDK to OTEL SDK

### Phase 1: Dual-Write (Zero Risk)

Run both instrumentation systems in parallel.

```
┌─────────────────────────────────────────────────────┐
│  Application                                         │
│                                                      │
│  ┌─────────────────┐    ┌──────────────────────┐   │
│  │ Prometheus SDK   │    │ OTEL SDK              │   │
│  │ /metrics :8080  │    │ OTLP → Collector     │   │
│  └────────┬────────┘    └───────────┬──────────┘   │
└───────────┼──────────────────────────┼───────────────┘
            │ scrape                    │ push
            ▼                          ▼
     ┌──────────────┐          ┌─────────────┐
     │  Prometheus   │          │  Collector   │
     │  (existing)   │          │    → Prom    │
     └──────────────┘          └─────────────┘

     Compare dashboards — ensure parity
```

### Phase 2: Collector Scrapes Existing /metrics

Replace Prometheus server scraping with Collector scraping. Same data, new pipeline.

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: 'existing-apps'
          # Same config as your prometheus.yml
          static_configs:
            - targets: ['app1:8080', 'app2:8080']
```

### Phase 3: Migrate to OTEL SDK

Replace Prometheus client libraries with OTEL SDK. Push via OTLP.

```python
# Before (Prometheus SDK)
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('http_requests_total', 'Total requests', ['method', 'path'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'Request duration')

# After (OTEL SDK)
from opentelemetry import metrics

meter = metrics.get_meter("myapp")
request_count = meter.create_counter("http.server.request.count", unit="1")
request_duration = meter.create_histogram("http.server.request.duration", unit="s")
```

### Phase 4: Full OTEL Pipeline

Remove all Prometheus SDKs. All metrics flow through OTEL.

```
Applications ──OTLP──▶ Collector ──Remote Write──▶ Prometheus/VictoriaMetrics
                              │
                              ├──OTLP──▶ Tempo (traces)
                              └──OTLP──▶ ClickHouse (logs)
```

---

## Prometheus vs OTEL: When to Use What

| Aspect | Prometheus (Native) | OTEL + Prometheus |
|--------|--------------------|--------------------|
| **Pull vs Push** | Pull (scrape) | Both (scrape via receiver, push via OTLP) |
| **Best for** | Infra metrics, node exporters | Application metrics with trace correlation |
| **Trace correlation** | Limited (exemplars only) | Native (same TraceID across metrics/traces) |
| **Multi-signal** | Metrics only | Metrics + Traces + Logs in one SDK |
| **Protocol** | Exposition format, Remote Write | OTLP (unified for all signals) |
| **Service discovery** | Built-in (K8s, Consul, DNS) | Via Prometheus receiver config |
| **Alerting** | PromQL + Alertmanager | Via Prometheus (metrics still land there) |
| **Vendor lock-in** | Prometheus ecosystem | Vendor-neutral, export anywhere |
| **Maturity** | Production-proven (10+ years) | Stable (metrics GA since 2023) |

### Recommendation

- **Keep Prometheus** for: infrastructure metrics (node_exporter, kube-state-metrics), alerting via Alertmanager, existing dashboards
- **Use OTEL** for: application-level metrics (business metrics, request metrics), when you need trace-metric correlation, multi-signal observability, new greenfield services

---

## Production Configuration: Complete Pipeline

```yaml
# Full production config: OTEL Collector bridging OTEL SDK apps + Prometheus targets
# to a Prometheus-compatible TSDB backend

receivers:
  # Receive from OTEL-instrumented applications
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_recv_msg_size_mib: 16
      http:
        endpoint: 0.0.0.0:4318

  # Scrape existing Prometheus endpoints
  prometheus:
    config:
      global:
        scrape_interval: 15s
        scrape_timeout: 10s
      scrape_configs:
        - job_name: 'kubernetes-pods'
          kubernetes_sd_configs:
            - role: pod
          relabel_configs:
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
              action: keep
              regex: true
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
              action: replace
              target_label: __address__
              regex: (.+)
              replacement: ${1}:${2}
              source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            - source_labels: [__meta_kubernetes_namespace]
              target_label: namespace
            - source_labels: [__meta_kubernetes_pod_name]
              target_label: pod

        - job_name: 'node-exporter'
          static_configs:
            - targets: ['node-exporter:9100']

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 2048
    spike_limit_mib: 512

  batch:
    send_batch_size: 10000
    send_batch_max_size: 15000
    timeout: 10s

  # Enrich with K8s metadata
  k8sattributes:
    auth_type: "serviceAccount"
    extract:
      metadata:
        - k8s.namespace.name
        - k8s.deployment.name
        - k8s.pod.name

  # Filter noisy metrics
  filter/metrics:
    metrics:
      exclude:
        match_type: regexp
        metric_names:
          - "go_.*"           # Go runtime metrics (usually too verbose)
          - "process_.*"      # Process metrics from every pod

  # Add cluster label
  resource:
    attributes:
      - key: cluster
        value: "prod-us-east-1"
        action: upsert

exporters:
  # Primary: Prometheus Remote Write to VictoriaMetrics
  prometheusremotewrite/primary:
    endpoint: "http://victoriametrics-vminsert:8480/insert/0/prometheus/api/v1/write"
    resource_to_telemetry_conversion:
      enabled: true
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 10000

  # Secondary: Another Prometheus for alerting
  prometheusremotewrite/alerting:
    endpoint: "http://prometheus-alerting:9090/api/v1/write"
    resource_to_telemetry_conversion:
      enabled: true

extensions:
  health_check:
    endpoint: 0.0.0.0:13133

service:
  extensions: [health_check]
  pipelines:
    metrics:
      receivers: [otlp, prometheus]
      processors: [memory_limiter, k8sattributes, filter/metrics, resource, batch]
      exporters: [prometheusremotewrite/primary, prometheusremotewrite/alerting]
```

---

## Common Issues and Solutions

### Issue 1: Metric Name Conflicts

When both Prometheus receiver and OTLP receiver produce metrics with the same name but different schemas:

```yaml
processors:
  metricstransform:
    transforms:
      # Prefix OTLP metrics to avoid collision
      - include: "http.server.request.duration"
        action: update
        new_name: "otel_http_server_request_duration"
```

### Issue 2: High Cardinality Explosion

Prometheus label cardinality must be controlled to prevent memory issues:

```yaml
processors:
  filter/high-cardinality:
    metrics:
      datapoint:
        - 'IsMatch(attributes["http.url"], ".*\\?.*")'  # Remove URL params
  
  transform:
    metric_statements:
      - context: datapoint
        statements:
          # Remove high-cardinality attributes before export
          - delete_key(attributes, "user.id")
          - delete_key(attributes, "request.id")
```

### Issue 3: Stale Metrics After Pod Restart

Prometheus uses staleness markers. When using OTEL SDK push, the Collector's prometheus exporter handles this:

```yaml
exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
    metric_expiration: 5m  # Remove metrics not updated in 5 minutes
```

### Issue 4: Duplicate Metrics from Multiple Collectors

When running Collectors in agent mode (per-node), ensure deduplication at the backend:

```yaml
# In VictoriaMetrics:
# -dedup.minScrapeInterval=15s

# In Thanos:
# --deduplication.replica-label="pod"
```

---

## Summary: Prometheus + OTEL Integration Points

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    OTEL COLLECTOR                                 │    │
│  │                                                                   │    │
│  │  RECEIVERS              PROCESSORS           EXPORTERS           │    │
│  │  ┌─────────────┐      ┌────────────┐      ┌───────────────┐   │    │
│  │  │ prometheus  │─────▶│ batch      │─────▶│ prometheusrw  │───────▶ VM/Prom
│  │  │ (scraper)   │      │ filter     │      │ (push)        │   │    │
│  │  └─────────────┘      │ transform  │      └───────────────┘   │    │
│  │  ┌─────────────┐      │ k8sattribs │      ┌───────────────┐   │    │
│  │  │ otlp        │─────▶│            │─────▶│ prometheus    │───────▶ Prom scrape
│  │  │ (push from  │      └────────────┘      │ (pull/expose) │   │    │
│  │  │  OTEL SDK)  │                          └───────────────┘   │    │
│  │  └─────────────┘                                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

The Collector acts as the universal bridge — whether your metrics originate from Prometheus SDKs (scraped) or OTEL SDKs (pushed), they all flow through a unified pipeline with consistent processing before landing in your Prometheus-compatible backend.
