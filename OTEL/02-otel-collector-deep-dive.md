# OTEL Collector — Deep Dive

## What is the OTEL Collector?

The OpenTelemetry Collector is a **vendor-agnostic, high-performance telemetry pipeline** that receives, processes, and exports observability data. It decouples instrumentation from backend infrastructure — applications send data to the Collector, and the Collector routes it to any combination of backends.

Think of it as **nginx for telemetry** — a reverse proxy that sits between your applications and your observability backends, providing buffering, retry, transformation, and routing.

---

## Why Use a Collector?

| Without Collector | With Collector |
|---|---|
| Each app configures its own exporters | Apps export to one local endpoint |
| Credential management in every service | Credentials only in Collector config |
| No buffering — data loss on backend outage | Collector buffers and retries |
| Format conversion in application code | Collector handles all transformations |
| Sampling only at SDK level (head-based) | Tail-based sampling possible |
| Hard to add new backends | Add an exporter, zero app changes |
| No central telemetry governance | Central place for filtering, enriching, routing |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OTEL COLLECTOR                                      │
│                                                                               │
│  ┌────────────────┐   ┌─────────────────────┐   ┌──────────────────────┐   │
│  │   RECEIVERS     │   │    PROCESSORS        │   │     EXPORTERS        │   │
│  │                │   │                     │   │                      │   │
│  │ • otlp         │   │ • memory_limiter    │   │ • otlp               │   │
│  │ • prometheus   │──▶│ • batch             │──▶│ • prometheus         │   │
│  │ • kafka        │   │ • filter            │   │ • clickhouse         │   │
│  │ • filelog      │   │ • attributes        │   │ • kafka              │   │
│  │ • hostmetrics  │   │ • tail_sampling     │   │ • loki               │   │
│  │ • jaeger       │   │ • resource          │   │ • debug              │   │
│  │ • zipkin       │   │ • span              │   │ • file               │   │
│  └────────────────┘   └─────────────────────┘   └──────────────────────┘   │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                        CONNECTORS                                       │  │
│  │   (Bridge between pipelines — e.g., traces → metrics via spanmetrics)  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                        EXTENSIONS                                       │  │
│  │   • health_check • pprof • zpages • bearertokenauth • oauth2client    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipelines

A **pipeline** connects receivers → processors → exporters for a specific signal type.

```yaml
service:
  pipelines:
    # Traces pipeline
    traces:
      receivers: [otlp, jaeger, zipkin]
      processors: [memory_limiter, batch, tail_sampling]
      exporters: [otlp/tempo, clickhouse]

    # Metrics pipeline
    metrics:
      receivers: [otlp, prometheus, hostmetrics]
      processors: [memory_limiter, batch, filter/metrics]
      exporters: [prometheusremotewrite/victoriametrics]

    # Logs pipeline
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, batch, attributes/logs]
      exporters: [clickhouse, loki]
```

### Pipeline Rules

1. Each pipeline has exactly **one signal type** (traces, metrics, or logs)
2. A receiver can feed **multiple pipelines**
3. Processors execute **in order** (sequence matters)
4. An exporter can receive from **multiple pipelines**
5. Data flows: `Receiver → Processor₁ → Processor₂ → ... → Exporter`

---

## Receivers (Data Ingestion)

Receivers define **how data enters** the Collector.

### OTLP Receiver (Most Common)

Native OTEL protocol — accepts traces, metrics, and logs over gRPC and HTTP.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
        max_recv_msg_size_mib: 16
        keepalive:
          server_parameters:
            max_connection_age: 60s
        tls:
          cert_file: /certs/server.crt
          key_file: /certs/server.key
      http:
        endpoint: "0.0.0.0:4318"
        cors:
          allowed_origins: ["https://app.example.com"]
```

### Prometheus Receiver

Scrapes Prometheus-format metrics from targets (like Prometheus server does).

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: 'kubernetes-pods'
          scrape_interval: 15s
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
              replacement: ${1}:$$1
```

### Kafka Receiver

Consumes telemetry from Kafka topics (for decoupled, high-throughput ingestion).

```yaml
receivers:
  kafka:
    brokers: ["kafka-1:9092", "kafka-2:9092", "kafka-3:9092"]
    topic: "otel-traces"
    encoding: otlp_proto
    group_id: "otel-collector-traces"
    initial_offset: latest
    auth:
      sasl:
        mechanism: SCRAM-SHA-512
        username: ${env:KAFKA_USERNAME}
        password: ${env:KAFKA_PASSWORD}
```

### Filelog Receiver

Tails log files — replaces Filebeat/Fluentd for log collection.

```yaml
receivers:
  filelog:
    include: ["/var/log/pods/**/*.log"]
    exclude: ["/var/log/pods/**/otel-collector-*.log"]
    start_at: end
    include_file_path: true
    include_file_name: true
    operators:
      # Parse container runtime log format
      - type: regex_parser
        regex: '^(?P<time>[^ ]+) (?P<stream>stdout|stderr) (?P<flags>[^ ]*) (?P<log>.*)$'
        timestamp:
          parse_from: attributes.time
          layout: '%Y-%m-%dT%H:%M:%S.%fZ'
      # Parse JSON structured logs
      - type: json_parser
        parse_from: attributes.log
        if: 'attributes.log != nil and attributes.log startsWith "{"'
      # Severity mapping
      - type: severity_parser
        parse_from: attributes.level
        mapping:
          error: [error, err, ERROR]
          warn: [warn, warning, WARN]
          info: [info, INFO]
          debug: [debug, DEBUG]
```

### Host Metrics Receiver

Collects system-level metrics from the host machine.

```yaml
receivers:
  hostmetrics:
    collection_interval: 30s
    scrapers:
      cpu:
        metrics:
          system.cpu.utilization:
            enabled: true
      memory:
      disk:
      filesystem:
      network:
      load:
      paging:
      processes:
```

---

## Processors (Data Transformation)

Processors modify, filter, enrich, or aggregate data **in-flight**.

### Memory Limiter (Always First)

Prevents the Collector from running out of memory. **Should always be the first processor.**

```yaml
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 4096           # Hard limit — start dropping data
    spike_limit_mib: 512      # Soft limit — start refusing new data
    limit_percentage: 80       # Or use percentage of total memory
    spike_limit_percentage: 20
```

**How it works:**
```
Memory usage < (limit - spike) → Accept all data
Memory usage > (limit - spike) → Start refusing new data (backpressure)
Memory usage > limit           → Drop data to survive
```

### Batch Processor

Groups data before exporting for efficiency (reduces number of outgoing requests).

```yaml
processors:
  batch:
    send_batch_size: 8192          # Max items per batch
    send_batch_max_size: 16384     # Absolute max (even if timeout hasn't hit)
    timeout: 5s                     # Send after this time even if batch isn't full
```

**Impact:**
```
Without batching:  1000 spans → 1000 HTTP requests → overwhelming backend
With batching:     1000 spans → ~1-2 HTTP requests → efficient export
```

### Filter Processor

Drops unwanted data based on conditions.

```yaml
processors:
  filter/traces:
    error_mode: ignore
    traces:
      span:
        # Drop health check traces
        - 'attributes["http.route"] == "/health"'
        - 'attributes["http.route"] == "/ready"'
        # Drop short-lived internal spans
        - 'name == "internal.tick" and duration < 1ms'

  filter/metrics:
    error_mode: ignore
    metrics:
      metric:
        # Drop high-cardinality debug metrics
        - 'name == "go_gc_duration_seconds"'
        - 'IsMatch(name, "process_.*")'
      datapoint:
        # Drop dev environment metrics
        - 'resource.attributes["deployment.environment"] == "development"'

  filter/logs:
    error_mode: ignore
    logs:
      log_record:
        # Drop debug logs in production
        - 'severity_number < 9'   # Below INFO
        # Drop noisy health check logs
        - 'body == "Health check OK"'
```

### Attributes Processor

Adds, modifies, or removes attributes on spans/metrics/logs.

```yaml
processors:
  attributes/traces:
    actions:
      # Add environment tag
      - key: deployment.environment
        value: production
        action: upsert
      # Remove sensitive data
      - key: db.statement
        action: delete
      - key: http.request.header.authorization
        action: delete
      # Hash PII
      - key: user.email
        action: hash
      # Extract from regex
      - key: http.url
        pattern: '^https?://(?P<host>[^/]+)/(?P<path>.*)$'
        action: extract

  attributes/logs:
    actions:
      # Ensure service.name is always present
      - key: service.name
        from_attribute: resource.service.name
        action: upsert
```

### Resource Processor

Modifies the resource (identity) of telemetry data.

```yaml
processors:
  resource:
    attributes:
      - key: cloud.provider
        value: aws
        action: upsert
      - key: cloud.region
        value: us-east-1
        action: upsert
      - key: cluster.name
        value: prod-east-1
        action: upsert
```

### Tail Sampling Processor

Makes sampling decisions **after** the complete trace is collected. Requires gateway deployment.

```yaml
processors:
  tail_sampling:
    decision_wait: 10s            # Time to wait for all spans of a trace
    num_traces: 100000            # Max traces held in memory
    expected_new_traces_per_sec: 10000
    policies:
      # Always keep errors
      - name: errors-policy
        type: status_code
        status_code:
          status_codes: [ERROR]

      # Always keep slow traces (>2s)
      - name: latency-policy
        type: latency
        latency:
          threshold_ms: 2000

      # Keep 10% of everything else
      - name: probabilistic-policy
        type: probabilistic
        probabilistic:
          sampling_percentage: 10

      # Always keep specific critical paths
      - name: critical-services
        type: string_attribute
        string_attribute:
          key: service.name
          values: [payment-service, auth-service]

      # Composite policy — combines the above
      - name: composite-policy
        type: composite
        composite:
          max_total_spans_per_second: 5000
          policy_order: [errors-policy, latency-policy, critical-services, probabilistic-policy]
          rate_allocation:
            - policy: errors-policy
              percent: 40
            - policy: latency-policy
              percent: 30
            - policy: critical-services
              percent: 20
            - policy: probabilistic-policy
              percent: 10
```

### Transform Processor (OTTL — OpenTelemetry Transformation Language)

Powerful expression-based transformations using OTTL.

```yaml
processors:
  transform:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          # Truncate long DB statements
          - truncate_all(attributes, 256)
          # Set span name from HTTP route
          - set(name, Concat([attributes["http.request.method"], " ", attributes["http.route"]], ""))
            where attributes["http.route"] != nil
          # Convert status
          - set(status.code, 2) where attributes["http.response.status_code"] >= 500

    metric_statements:
      - context: datapoint
        statements:
          # Convert milliseconds to seconds
          - set(value_double, value_double / 1000.0)
            where metric.name == "http.server.duration"

    log_statements:
      - context: log
        statements:
          # Extract trace context from log body
          - set(trace_id.string, attributes["traceId"])
            where attributes["traceId"] != nil
```

### K8s Attributes Processor

Enriches telemetry with Kubernetes metadata automatically.

```yaml
processors:
  k8sattributes:
    auth_type: "serviceAccount"
    passthrough: false
    extract:
      metadata:
        - k8s.pod.name
        - k8s.pod.uid
        - k8s.namespace.name
        - k8s.node.name
        - k8s.deployment.name
        - k8s.statefulset.name
        - k8s.container.name
      labels:
        - tag_name: app
          key: app.kubernetes.io/name
        - tag_name: version
          key: app.kubernetes.io/version
      annotations:
        - tag_name: team
          key: team
    pod_association:
      - sources:
          - from: resource_attribute
            name: k8s.pod.ip
```

---

## Exporters (Data Output)

Exporters send data to backends.

### OTLP Exporter

Sends data to any OTLP-compatible backend (Tempo, Jaeger, another Collector).

```yaml
exporters:
  otlp/tempo:
    endpoint: "tempo.monitoring.svc:4317"
    tls:
      insecure: false
      cert_file: /certs/client.crt
      key_file: /certs/client.key
    headers:
      X-Scope-OrgID: "tenant-1"
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
      max_elapsed_time: 300s
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 5000
    timeout: 30s
```

### Prometheus Remote Write Exporter

Pushes metrics to Prometheus-compatible backends (VictoriaMetrics, Mimir, Thanos).

```yaml
exporters:
  prometheusremotewrite/victoriametrics:
    endpoint: "http://vminsert:8480/insert/0/prometheus/api/v1/write"
    tls:
      insecure: true
    external_labels:
      cluster: "prod-east-1"
      environment: "production"
    resource_to_telemetry_conversion:
      enabled: true  # Convert resource attributes to metric labels
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
    sending_queue:
      enabled: true
      num_consumers: 5
      queue_size: 10000
```

### ClickHouse Exporter

Sends traces and logs to ClickHouse for analytical querying.

```yaml
exporters:
  clickhouse:
    endpoint: "tcp://clickhouse-cluster:9000?dial_timeout=10s&compress=lz4"
    database: otel
    username: ${env:CLICKHOUSE_USERNAME}
    password: ${env:CLICKHOUSE_PASSWORD}
    ttl: 72h                          # Data retention
    logs_table_name: otel_logs
    traces_table_name: otel_traces
    metrics_table_name: otel_metrics
    timeout: 10s
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 10000
    create_schema: true               # Auto-create tables
    compress: lz4
```

### Kafka Exporter

Sends data to Kafka for buffering or downstream consumers.

```yaml
exporters:
  kafka/traces:
    brokers: ["kafka-1:9092", "kafka-2:9092", "kafka-3:9092"]
    topic: "otel-traces"
    encoding: otlp_proto
    partition_traces_by_id: true     # Same trace → same partition
    producer:
      max_message_bytes: 10000000
      compression: zstd
      flush_max_messages: 500
    auth:
      sasl:
        mechanism: SCRAM-SHA-512
        username: ${env:KAFKA_USERNAME}
        password: ${env:KAFKA_PASSWORD}
```

### Debug Exporter

Outputs data to stdout/logs for development and troubleshooting.

```yaml
exporters:
  debug:
    verbosity: detailed              # basic | normal | detailed
    sampling_initial: 5              # Log first 5 items
    sampling_thereafter: 200         # Then every 200th item
```

---

## Connectors (Pipeline Bridges)

Connectors act as **both an exporter and a receiver** — they bridge pipelines.

### Span Metrics Connector

Generates RED metrics (Rate, Error, Duration) from traces automatically.

```yaml
connectors:
  spanmetrics:
    histogram:
      explicit:
        buckets: [2ms, 4ms, 6ms, 8ms, 10ms, 50ms, 100ms, 250ms, 500ms, 1s, 2s, 5s]
    dimensions:
      - name: http.method
      - name: http.status_code
      - name: service.name
        default: "unknown"
    exemplars:
      enabled: true
    namespace: traces.spanmetrics

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo, spanmetrics]   # spanmetrics is an exporter here
    metrics:
      receivers: [spanmetrics]                 # spanmetrics is a receiver here
      processors: [batch]
      exporters: [prometheusremotewrite]
```

### Count Connector

Counts spans/logs/datapoints and emits as metrics.

```yaml
connectors:
  count:
    traces:
      spans:
        requests.total:
          description: "Total number of spans"
        requests.errors:
          description: "Total number of error spans"
          conditions:
            - status.code == 2  # ERROR
    logs:
      log_records:
        logs.total:
          description: "Total number of log records"
```

---

## Extensions

Extensions provide auxiliary capabilities (not part of the data pipeline).

```yaml
extensions:
  # Health check endpoint for load balancers
  health_check:
    endpoint: "0.0.0.0:13133"
    path: "/health"

  # Performance profiling
  pprof:
    endpoint: "0.0.0.0:1888"

  # Internal debugging pages
  zpages:
    endpoint: "0.0.0.0:55679"

  # Bearer token auth for incoming requests
  bearertokenauth:
    token: ${env:COLLECTOR_AUTH_TOKEN}

  # OAuth2 for outgoing requests
  oauth2client:
    client_id: ${env:OAUTH_CLIENT_ID}
    client_secret: ${env:OAUTH_CLIENT_SECRET}
    token_url: "https://auth.example.com/oauth/token"
    scopes: ["telemetry:write"]

service:
  extensions: [health_check, pprof, zpages]
```

---

## Deployment Patterns

### Pattern 1: Agent Mode (DaemonSet / Sidecar)

Runs on every node or alongside every pod. Handles local collection.

```
┌─────────────────── Node ───────────────────────────┐
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │  App A   │  │  App B   │  │  App C   │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │              │              │                │
│       └──────────────┼──────────────┘                │
│                      │ localhost:4317                 │
│               ┌──────┴──────┐                        │
│               │  Collector  │  ← DaemonSet           │
│               │   (Agent)   │    (1 per node)        │
│               └──────┬──────┘                        │
└──────────────────────┼───────────────────────────────┘
                       │
                       ▼ OTLP to Gateway
```

**Agent config:**
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
  hostmetrics:
    collection_interval: 30s
    scrapers:
      cpu:
      memory:
      disk:

processors:
  memory_limiter:
    limit_mib: 512
  batch:
    send_batch_size: 1024
    timeout: 2s
  k8sattributes:
    passthrough: false
  resource:
    attributes:
      - key: collector.type
        value: agent
        action: upsert

exporters:
  otlp/gateway:
    endpoint: "otel-gateway.monitoring.svc:4317"
    tls:
      insecure: false

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/gateway]
    metrics:
      receivers: [otlp, hostmetrics]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/gateway]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/gateway]
```

### Pattern 2: Gateway Mode (Centralized)

A pool of Collector instances that handle heavy processing and routing.

```
Agents ──────┐
Agents ──────┤      ┌──────────────────────────────┐
Agents ──────┼─────▶│  Load Balancer (L4/gRPC)     │
Agents ──────┤      └─────────────┬────────────────┘
Agents ──────┘                    │
                    ┌─────────────┼─────────────┐
                    │             │              │
              ┌─────▼───┐  ┌─────▼───┐  ┌──────▼──┐
              │ Gateway  │  │ Gateway  │  │ Gateway │
              │    #1    │  │    #2    │  │    #3   │
              └─────┬────┘  └─────┬────┘  └────┬────┘
                    │             │              │
                    └─────────────┼──────────────┘
                                  │
               ┌──────────────────┼────────────────────┐
               │                  │                     │
               ▼                  ▼                     ▼
        ┌────────────┐    ┌────────────┐       ┌────────────┐
        │VictoriaM.  │    │ ClickHouse │       │   Tempo    │
        │ (Metrics)  │    │(Logs+Traces)│      │  (Traces)  │
        └────────────┘    └────────────┘       └────────────┘
```

**Gateway config:**
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
        max_recv_msg_size_mib: 64
        max_concurrent_streams: 256

processors:
  memory_limiter:
    limit_mib: 8192
    spike_limit_mib: 2048

  batch/traces:
    send_batch_size: 16384
    timeout: 5s

  batch/metrics:
    send_batch_size: 8192
    timeout: 10s

  tail_sampling:
    decision_wait: 10s
    num_traces: 200000
    policies:
      - name: errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: slow
        type: latency
        latency: { threshold_ms: 2000 }
      - name: sample
        type: probabilistic
        probabilistic: { sampling_percentage: 5 }

  filter/drop-debug-logs:
    logs:
      log_record:
        - 'severity_number < 9'

exporters:
  prometheusremotewrite/vm:
    endpoint: "http://vminsert:8480/insert/0/prometheus/api/v1/write"
  clickhouse:
    endpoint: "tcp://clickhouse:9000"
    database: otel
  otlp/tempo:
    endpoint: "tempo:4317"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, tail_sampling, batch/traces]
      exporters: [otlp/tempo, clickhouse]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch/metrics]
      exporters: [prometheusremotewrite/vm]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, filter/drop-debug-logs, batch/traces]
      exporters: [clickhouse]
```

### Pattern 3: Multi-Tier (Agent + Gateway)

Production-recommended pattern combining both.

```
┌─────────────────────────────────────────────────────────────────────┐
│                           TIER 1: AGENTS                             │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Agent (Node1)│  │ Agent (Node2)│  │ Agent (Node3)│  ...         │
│  │ - Local recv │  │ - Local recv │  │ - Local recv │              │
│  │ - K8s enrich │  │ - K8s enrich │  │ - K8s enrich │              │
│  │ - Batch      │  │ - Batch      │  │ - Batch      │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         └──────────────────┼──────────────────┘                      │
└────────────────────────────┼─────────────────────────────────────────┘
                             │ OTLP (gRPC with LB)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        TIER 2: GATEWAYS                              │
│                                                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ Gateway #1      │  │ Gateway #2      │  │ Gateway #3      │    │
│  │ - Tail sampling │  │ - Tail sampling │  │ - Tail sampling │    │
│  │ - Filtering     │  │ - Filtering     │  │ - Filtering     │    │
│  │ - Routing       │  │ - Routing       │  │ - Routing       │    │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘    │
│           └─────────────────────┼──────────────────────┘            │
└─────────────────────────────────┼────────────────────────────────────┘
                                  │
                    ┌─────────────┼────────────────┐
                    ▼             ▼                 ▼
              ┌──────────┐ ┌──────────┐     ┌──────────┐
              │  Metrics │ │  Traces  │     │   Logs   │
              │ Backend  │ │ Backend  │     │ Backend  │
              └──────────┘ └──────────┘     └──────────┘
```

---

## Load Balancing for Tail Sampling

Tail sampling requires all spans of a trace to arrive at the **same gateway**. Use a trace-ID-aware load balancer.

```yaml
# On each Agent — routes by trace ID to consistent gateway
exporters:
  loadbalancing:
    routing_key: traceID
    protocol:
      otlp:
        timeout: 10s
        tls:
          insecure: true
    resolver:
      dns:
        hostname: otel-gateway-headless.monitoring.svc
        port: 4317
      # Or use static IPs
      # static:
      #   hostnames:
      #     - gateway-1:4317
      #     - gateway-2:4317
      #     - gateway-3:4317
```

---

## Configuration Best Practices

### Environment Variables

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "${env:OTEL_COLLECTOR_ENDPOINT}"

exporters:
  clickhouse:
    endpoint: "${env:CLICKHOUSE_ENDPOINT}"
    username: "${env:CLICKHOUSE_USER}"
    password: "${env:CLICKHOUSE_PASSWORD}"
```

### Multi-Config File Composition

```bash
# Start Collector with multiple config files
otelcol --config=base.yaml --config=receivers.yaml --config=exporters.yaml
```

### Resource Limits (Kubernetes)

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: otel-agent
spec:
  template:
    spec:
      containers:
        - name: otel-collector
          image: otel/opentelemetry-collector-contrib:0.96.0
          resources:
            requests:
              cpu: 200m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 512Mi
          ports:
            - containerPort: 4317  # gRPC
            - containerPort: 4318  # HTTP
            - containerPort: 13133 # Health check
          livenessProbe:
            httpGet:
              path: /health
              port: 13133
            initialDelaySeconds: 5
          readinessProbe:
            httpGet:
              path: /health
              port: 13133
            initialDelaySeconds: 5
```

---

## Complete Production Config Example

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
      http:
        endpoint: "0.0.0.0:4318"
  prometheus:
    config:
      scrape_configs:
        - job_name: 'otel-collector'
          scrape_interval: 10s
          static_configs:
            - targets: ['0.0.0.0:8888']
  hostmetrics:
    collection_interval: 30s
    scrapers:
      cpu:
      memory:
      disk:
      network:

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 4096
    spike_limit_mib: 1024
  batch:
    send_batch_size: 8192
    timeout: 5s
  k8sattributes:
    extract:
      metadata:
        - k8s.pod.name
        - k8s.namespace.name
        - k8s.deployment.name
  resource:
    attributes:
      - key: cluster.name
        value: "prod-east-1"
        action: upsert
  filter/health:
    traces:
      span:
        - 'attributes["http.route"] == "/health"'
        - 'attributes["http.route"] == "/ready"'

exporters:
  prometheusremotewrite:
    endpoint: "http://vminsert:8480/insert/0/prometheus/api/v1/write"
    resource_to_telemetry_conversion:
      enabled: true
  clickhouse:
    endpoint: "tcp://clickhouse:9000"
    database: otel
    logs_table_name: otel_logs
    traces_table_name: otel_traces
  otlp/tempo:
    endpoint: "tempo:4317"
    tls:
      insecure: true
  debug:
    verbosity: basic

connectors:
  spanmetrics:
    histogram:
      explicit:
        buckets: [5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s]
    dimensions:
      - name: http.request.method
      - name: http.response.status_code
      - name: service.name
    exemplars:
      enabled: true

extensions:
  health_check:
    endpoint: "0.0.0.0:13133"
  pprof:
    endpoint: "0.0.0.0:1888"

service:
  extensions: [health_check, pprof]
  telemetry:
    logs:
      level: info
    metrics:
      address: "0.0.0.0:8888"

  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, filter/health, k8sattributes, resource, batch]
      exporters: [otlp/tempo, clickhouse, spanmetrics]

    metrics:
      receivers: [otlp, prometheus, hostmetrics, spanmetrics]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [prometheusremotewrite]

    logs:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [clickhouse]
```

---

## Collector Distributions

| Distribution | Description | Use Case |
|---|---|---|
| `otel/opentelemetry-collector` | Core distribution — only essential components | Minimal, production |
| `otel/opentelemetry-collector-contrib` | Community distribution — 200+ components | Most production setups |
| Custom (via `ocb`) | Build your own with only needed components | Security-hardened, minimal attack surface |

### Building a Custom Collector

```yaml
# builder-config.yaml
dist:
  name: my-otel-collector
  output_path: ./dist

receivers:
  - gomod: go.opentelemetry.io/collector/receiver/otlpreceiver v0.96.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/kafkareceiver v0.96.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/filelogreceiver v0.96.0

processors:
  - gomod: go.opentelemetry.io/collector/processor/batchprocessor v0.96.0
  - gomod: go.opentelemetry.io/collector/processor/memorylimiterprocessor v0.96.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/processor/filterprocessor v0.96.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/processor/tailsamplingprocessor v0.96.0

exporters:
  - gomod: go.opentelemetry.io/collector/exporter/otlpexporter v0.96.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/exporter/clickhouseexporter v0.96.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/exporter/prometheusremotewriteexporter v0.96.0

extensions:
  - gomod: go.opentelemetry.io/collector/extension/healthcheckextension v0.96.0

connectors:
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/connector/spanmetricsconnector v0.96.0
```

```bash
# Build custom collector
ocb --config builder-config.yaml
```

---

## Observability of the Collector Itself

The Collector exposes its own telemetry:

```
# Internal metrics (Prometheus format on :8888)
otelcol_receiver_accepted_spans{receiver="otlp"}
otelcol_receiver_refused_spans{receiver="otlp"}
otelcol_exporter_sent_spans{exporter="otlp/tempo"}
otelcol_exporter_send_failed_spans{exporter="clickhouse"}
otelcol_processor_dropped_spans{processor="filter/health"}
otelcol_exporter_queue_size{exporter="clickhouse"}
otelcol_exporter_queue_capacity{exporter="clickhouse"}
```

Key metrics to alert on:
- `otelcol_exporter_send_failed_*` > 0 (backend connectivity issues)
- `otelcol_exporter_queue_size` approaching capacity (backpressure)
- `otelcol_receiver_refused_*` > 0 (memory limiter triggering)
- Process memory usage approaching `memory_limiter.limit_mib`
