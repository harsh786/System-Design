# Monitoring & Alerting Infrastructure at Scale

## Problem Statement

At scale (100K+ metric time-series, 10TB+ logs/day, millions of spans), the monitoring infrastructure becomes a distributed systems challenge itself. The stack must be:

- **Reliable**: More reliable than the systems it monitors (target 99.99%)
- **Scalable**: Handle 10x growth without re-architecture
- **Cost-effective**: Monitoring should cost <5% of infrastructure spend
- **Low-latency**: Alerts must fire within seconds of threshold breach
- **Queryable**: Engineers must get answers in <10s for troubleshooting

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                        Complete Observability Stack                                    │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                         COLLECTION LAYER                                         │ │
│  │                                                                                 │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌────────────┐                 │ │
│  │  │Prometheus│  │Fluent Bit│  │OTel Collector│  │StatsD /    │                 │ │
│  │  │(scrape)  │  │(logs)    │  │(traces+metrics)│ │Push GW    │                 │ │
│  │  └────┬─────┘  └────┬─────┘  └──────┬───────┘  └─────┬──────┘                 │ │
│  │       │              │               │                 │                        │ │
│  └───────┼──────────────┼───────────────┼─────────────────┼────────────────────────┘ │
│          │              │               │                 │                          │
│  ┌───────┼──────────────┼───────────────┼─────────────────┼────────────────────────┐ │
│  │       │         PROCESSING LAYER     │                 │                        │ │
│  │       │              │               │                 │                        │ │
│  │       │         ┌────▼─────┐    ┌────▼────────┐       │                        │ │
│  │       │         │  Vector  │    │OTel Pipeline│       │                        │ │
│  │       │         │(enrich,  │    │(sample,     │       │                        │ │
│  │       │         │ filter)  │    │ batch)      │       │                        │ │
│  │       │         └────┬─────┘    └─────┬───────┘       │                        │ │
│  │       │              │                │               │                        │ │
│  └───────┼──────────────┼────────────────┼───────────────┼────────────────────────┘ │
│          │              │                │               │                          │
│  ┌───────┼──────────────┼────────────────┼───────────────┼────────────────────────┐ │
│  │       │         STORAGE LAYER         │               │                        │ │
│  │       │              │                │               │                        │ │
│  │  ┌────▼─────┐  ┌────▼─────┐    ┌─────▼──────┐  ┌────▼─────┐                  │ │
│  │  │Thanos /  │  │  Loki    │    │   Tempo    │  │Prometheus│                  │ │
│  │  │Mimir     │  │(chunks+  │    │(S3-backed) │  │(local    │                  │ │
│  │  │(long-term│  │ index)   │    │            │  │ TSDB)    │                  │ │
│  │  │ metrics) │  └──────────┘    └────────────┘  └──────────┘                  │ │
│  │  └──────────┘                                                                  │ │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                         QUERY & VISUALIZATION                                    │ │
│  │                                                                                 │ │
│  │  ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐                   │ │
│  │  │   Grafana    │  │  Thanos Query  │  │  Loki Query      │                   │ │
│  │  │ (Dashboards) │  │  (PromQL)      │  │  (LogQL)         │                   │ │
│  │  └──────────────┘  └────────────────┘  └──────────────────┘                   │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                         ALERTING PIPELINE                                        │ │
│  │                                                                                 │ │
│  │  ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌─────────────────────────┐ │ │
│  │  │Prometheus│──▶│AlertManager  │──▶│ Routing  │──▶│PagerDuty/Slack/Email/WH│ │ │
│  │  │(eval)    │   │(dedup,group) │   │(severity)│   │                         │ │ │
│  │  └──────────┘   └──────────────┘   └──────────┘   └─────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Metrics Pipeline (Prometheus-based)

### Service Discovery & Scrape Configuration

```yaml
# prometheus-scrape-config.yaml
# Production scrape configuration for data pipeline monitoring

global:
  scrape_interval: 15s
  scrape_timeout: 10s
  evaluation_interval: 15s
  external_labels:
    cluster: production
    region: us-east-1

scrape_configs:
  # Kubernetes service discovery for pods with prometheus annotations
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      # Only scrape pods with annotation prometheus.io/scrape=true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      # Use custom port if specified
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
        replacement: ${1}:${2}
        separator: ':'
      # Use custom path if specified
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      # Preserve useful labels
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: app

  # Kafka monitoring via JMX exporter
  - job_name: 'kafka'
    static_configs:
      - targets: ['kafka-0:9308', 'kafka-1:9308', 'kafka-2:9308']
    metric_relabel_configs:
      # Drop high-cardinality JMX metrics we don't need
      - source_labels: [__name__]
        regex: 'kafka_server_brokertopicmetrics_.*_total'
        action: drop
      # Keep only partition-level metrics for critical topics
      - source_labels: [__name__, topic]
        regex: 'kafka_server_replicamanager.*;(?!critical-topic-.*)'
        action: drop

  # Flink job monitoring
  - job_name: 'flink'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: ['flink-jobs']
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_component]
        action: keep
        regex: 'jobmanager|taskmanager'

  # Airflow metrics
  - job_name: 'airflow'
    static_configs:
      - targets: ['airflow-statsd-exporter:9102']
    metric_relabel_configs:
      # Normalize DAG names to prevent cardinality explosion
      - source_labels: [dag_id]
        regex: '(.+)_\d{8}'  # Strip date suffixes
        target_label: dag_id
        replacement: '${1}'

  # Push Gateway for batch jobs
  - job_name: 'pushgateway'
    honor_labels: true
    static_configs:
      - targets: ['pushgateway:9091']
```

### Recording Rules for Performance

```yaml
# recording-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: pipeline-recording-rules
  namespace: monitoring
spec:
  groups:
    - name: pipeline.recording.rules
      interval: 30s
      rules:
        # Pre-compute pipeline throughput (used in 12 dashboards)
        - record: pipeline:events_processed:rate5m
          expr: sum(rate(pipeline_events_processed_total[5m])) by (pipeline, status)

        # Pre-compute error rates
        - record: pipeline:error_rate:ratio5m
          expr: |
            sum(rate(pipeline_events_processed_total{status="failed"}[5m])) by (pipeline)
            /
            sum(rate(pipeline_events_processed_total[5m])) by (pipeline)

        # Pre-compute latency percentiles (expensive query)
        - record: pipeline:latency_seconds:p99_5m
          expr: |
            histogram_quantile(0.99,
              sum(rate(pipeline_processing_duration_seconds_bucket[5m])) by (le, pipeline)
            )

        - record: pipeline:latency_seconds:p95_5m
          expr: |
            histogram_quantile(0.95,
              sum(rate(pipeline_processing_duration_seconds_bucket[5m])) by (le, pipeline)
            )

        # Kafka consumer lag aggregation
        - record: kafka:consumer_lag:sum_by_group
          expr: sum(kafka_consumergroup_lag) by (consumergroup, topic)

        # Pre-compute SLO burn rates
        - record: pipeline:slo_error_budget:remaining
          expr: |
            1 - (
              sum(rate(pipeline_events_processed_total{status="failed"}[30d])) by (pipeline)
              /
              sum(rate(pipeline_events_processed_total[30d])) by (pipeline)
            ) / 0.001  # 99.9% SLO target
```

### Cardinality Management

```yaml
# metric-relabeling.yaml
# Applied at scrape time to prevent cardinality explosion

metric_relabel_configs:
  # Drop Go runtime metrics we don't use
  - source_labels: [__name__]
    regex: 'go_(gc|memstats)_.*'
    action: drop

  # Aggregate HTTP metrics - drop path label (unbounded)
  - source_labels: [__name__]
    regex: 'http_request_duration_seconds_.*'
    action: keep
  - source_labels: [path]
    regex: '/api/v1/.*'
    target_label: path
    replacement: '/api/v1/{endpoint}'

  # Limit user_id label (would be unbounded)
  - source_labels: [user_id]
    regex: '.+'
    target_label: user_id
    replacement: ''  # Drop the label entirely
    action: replace

  # Bucket pruning - remove extreme histogram buckets
  - source_labels: [__name__, le]
    regex: 'pipeline_processing_duration_seconds_bucket;(0\.001|0\.0025|0\.005)'
    action: drop  # Sub-ms buckets not useful for pipeline monitoring
```

---

## Log Pipeline

### Vector Configuration for Log Processing

```toml
# vector.toml - Production log pipeline

[sources.kubernetes_logs]
type = "kubernetes_logs"
auto_partial_merge = true
exclude_paths_glob_patterns = [
  "**/kube-system/**",
  "**/monitoring/prometheus-*/**"
]

[transforms.parse_json]
type = "remap"
inputs = ["kubernetes_logs"]
source = '''
  # Try to parse as JSON
  structured, err = parse_json(.message)
  if err == null {
    . = merge(., structured)
  }
  
  # Enrich with standard fields
  .environment = "production"
  .cluster = "us-east-1-prod"
  
  # Extract trace_id for correlation
  .trace_id = .trace_id ?? .traceId ?? .TraceID ?? ""
'''

[transforms.filter_noise]
type = "filter"
inputs = ["parse_json"]
condition = '''
  # Drop health check logs
  !match(.message, r'GET /health') &&
  !match(.message, r'GET /ready') &&
  # Drop debug logs in production
  .level != "debug" &&
  .level != "DEBUG"
'''

[transforms.sample_high_volume]
type = "sample"
inputs = ["filter_noise"]
rate = 10  # Keep 1 in 10 for high-volume services
condition = '''
  # Only sample non-error logs from high-volume services
  includes(["kafka-consumer", "event-processor"], .kubernetes.pod_labels.app) &&
  .level != "error" && .level != "ERROR"
'''

[transforms.add_metadata]
type = "remap"
inputs = ["sample_high_volume"]
source = '''
  # Create Loki-friendly labels (keep cardinality low)
  .loki_labels = {
    "namespace": .kubernetes.pod_namespace,
    "app": .kubernetes.pod_labels.app ?? "unknown",
    "level": downcase(.level ?? "info"),
    "pipeline": .kubernetes.pod_labels.pipeline ?? ""
  }
  
  # Structured metadata (Loki 3.0+)
  .structured_metadata = {
    "trace_id": .trace_id,
    "span_id": .span_id ?? "",
    "pod": .kubernetes.pod_name
  }
'''

[sinks.loki]
type = "loki"
inputs = ["add_metadata"]
endpoint = "http://loki-gateway.monitoring.svc:80"
encoding.codec = "json"
labels = "{{ loki_labels }}"
remove_label_fields = true
tenant_id = "default"

[sinks.loki.batch]
max_bytes = 10485760  # 10MB
timeout_secs = 5

[sinks.loki.buffer]
type = "disk"
max_size = 5368709120  # 5GB disk buffer
when_full = "block"
```

### Loki Configuration

```yaml
# loki-config.yaml

auth_enabled: true

server:
  http_listen_port: 3100
  grpc_listen_port: 9096
  log_level: info

common:
  path_prefix: /loki
  replication_factor: 3
  storage:
    s3:
      bucketnames: prod-monitoring-loki-chunks
      region: us-east-1

schema_config:
  configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: s3
      schema: v13
      index:
        prefix: loki_index_
        period: 24h

limits_config:
  ingestion_rate_mb: 100
  ingestion_burst_size_mb: 200
  max_query_parallelism: 32
  max_query_series: 5000
  query_timeout: 5m
  max_entries_limit_per_query: 50000
  retention_period: 30d
  per_stream_rate_limit: 5MB
  per_stream_rate_limit_burst: 15MB

  # Structured metadata (for trace correlation)
  allow_structured_metadata: true

query_range:
  parallelise_shardable_queries: true
  cache_results: true
  results_cache:
    cache:
      memcached_client:
        addresses: "memcached.monitoring.svc:11211"

storage_config:
  tsdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache

compactor:
  working_directory: /loki/compactor
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h

ruler:
  storage:
    type: s3
    s3:
      bucketnames: prod-monitoring-loki-rules
  alertmanager_url: http://alertmanager.monitoring.svc:9093
```

---

## Trace Pipeline

### OpenTelemetry Collector Configuration

```yaml
# otel-collector-config.yaml

receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_recv_msg_size_mib: 16
      http:
        endpoint: 0.0.0.0:4318

  # Kafka receiver for async trace ingestion
  kafka:
    brokers:
      - kafka-0:9092
      - kafka-1:9092
      - kafka-2:9092
    topic: otel-traces
    group_id: otel-collector-traces
    encoding: otlp_proto

processors:
  # Batch traces for efficient export
  batch:
    send_batch_size: 10000
    send_batch_max_size: 11000
    timeout: 5s

  # Memory limiter to prevent OOM
  memory_limiter:
    check_interval: 1s
    limit_mib: 4096
    spike_limit_mib: 1024

  # Tail-based sampling
  tail_sampling:
    decision_wait: 10s
    num_traces: 100000
    expected_new_traces_per_sec: 10000
    policies:
      # Always keep errors
      - name: errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      # Always keep slow traces
      - name: slow-traces
        type: latency
        latency:
          threshold_ms: 5000
      # Sample 1% of normal traces
      - name: probabilistic
        type: probabilistic
        probabilistic:
          sampling_percentage: 1
      # Always keep traces from critical pipelines
      - name: critical-pipelines
        type: string_attribute
        string_attribute:
          key: pipeline.name
          values: [payment-processing, fraud-detection]

  # Add resource attributes
  resource:
    attributes:
      - key: environment
        value: production
        action: upsert
      - key: collector.name
        value: otel-gateway
        action: upsert

  # Span metrics connector (derive metrics from traces)
  spanmetrics:
    metrics_exporter: prometheusremotewrite
    dimensions:
      - name: http.method
      - name: http.status_code
      - name: pipeline.name
    histogram:
      explicit:
        buckets: [5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 5s, 10s, 30s]

exporters:
  # Tempo for trace storage
  otlp/tempo:
    endpoint: tempo-distributor.monitoring.svc:4317
    tls:
      insecure: true

  # Prometheus Remote Write for span metrics
  prometheusremotewrite:
    endpoint: http://prometheus:9090/api/v1/write
    resource_to_telemetry_conversion:
      enabled: true

  # Debug exporter (for development)
  debug:
    verbosity: basic

extensions:
  health_check:
    endpoint: 0.0.0.0:13133
  zpages:
    endpoint: 0.0.0.0:55679

service:
  extensions: [health_check, zpages]
  pipelines:
    traces:
      receivers: [otlp, kafka]
      processors: [memory_limiter, tail_sampling, batch, resource]
      exporters: [otlp/tempo]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheusremotewrite]
```

### Tempo Configuration

```yaml
# tempo-config.yaml

server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317

  ring:
    kvstore:
      store: memberlist

ingester:
  max_block_duration: 5m
  max_block_bytes: 524288000  # 500MB

compactor:
  compaction:
    block_retention: 168h  # 7 days

storage:
  trace:
    backend: s3
    s3:
      bucket: prod-monitoring-tempo-traces
      endpoint: s3.us-east-1.amazonaws.com
      region: us-east-1
    wal:
      path: /var/tempo/wal
    pool:
      max_workers: 100
      queue_depth: 10000

metrics_generator:
  registry:
    external_labels:
      source: tempo
  storage:
    path: /var/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
  traces_storage:
    path: /var/tempo/generator/traces
  processor:
    service_graphs:
      dimensions:
        - pipeline.name
        - http.method
    span_metrics:
      dimensions:
        - pipeline.name
        - http.status_code

overrides:
  defaults:
    metrics_generator:
      processors: [service-graphs, span-metrics]
```

---

## Alert Pipeline

### AlertManager Routing Configuration

```yaml
# alertmanager-config.yaml

global:
  resolve_timeout: 5m
  http_config:
    follow_redirects: true
  pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'
  slack_api_url_file: '/etc/alertmanager/secrets/slack-url'

# Inhibition rules - suppress lower severity when higher fires
inhibit_rules:
  # If critical fires, suppress warning for same alertname
  - source_matchers:
      - severity = critical
    target_matchers:
      - severity = warning
    equal: [alertname, namespace, pipeline]

  # If cluster is down, suppress all pod-level alerts
  - source_matchers:
      - alertname = KubeNodeNotReady
    target_matchers:
      - severity =~ "warning|critical"
    equal: [node]

  # If pipeline is paused intentionally, suppress lag alerts
  - source_matchers:
      - alertname = PipelinePausedIntentional
    target_matchers:
      - alertname =~ "PipelineLag.*"
    equal: [pipeline]

route:
  receiver: 'slack-default'
  group_by: ['namespace', 'alertname', 'pipeline']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    # Critical data pipeline alerts → PagerDuty immediately
    - matchers:
        - severity = critical
        - team = data-engineering
      receiver: 'pagerduty-data-eng'
      repeat_interval: 30m
      continue: true  # Also send to Slack

    # Critical infrastructure alerts
    - matchers:
        - severity = critical
        - team = platform
      receiver: 'pagerduty-platform'
      repeat_interval: 30m

    # SLO burn rate alerts (multi-window)
    - matchers:
        - alertname =~ "SLOBurnRate.*"
        - severity = page
      receiver: 'pagerduty-data-eng'
      repeat_interval: 1h

    # Warning alerts → Slack channel
    - matchers:
        - severity = warning
        - team = data-engineering
      receiver: 'slack-data-eng-warnings'
      repeat_interval: 4h

    # Business hours only alerts
    - matchers:
        - severity = info
      receiver: 'slack-data-eng-info'
      repeat_interval: 12h
      active_time_intervals:
        - business-hours

    # Monitoring self-health → dedicated channel
    - matchers:
        - namespace = monitoring
      receiver: 'slack-monitoring-health'
      repeat_interval: 1h

receivers:
  - name: 'slack-default'
    slack_configs:
      - channel: '#alerts-default'
        send_resolved: true
        title: '{{ .Status | toUpper }}: {{ .CommonLabels.alertname }}'
        text: >-
          {{ range .Alerts }}
          *Alert:* {{ .Annotations.summary }}
          *Pipeline:* {{ .Labels.pipeline }}
          *Severity:* {{ .Labels.severity }}
          *Details:* {{ .Annotations.description }}
          {{ end }}

  - name: 'pagerduty-data-eng'
    pagerduty_configs:
      - routing_key_file: '/etc/alertmanager/secrets/pd-data-eng-key'
        severity: '{{ .CommonLabels.severity }}'
        description: '{{ .CommonAnnotations.summary }}'
        details:
          pipeline: '{{ .CommonLabels.pipeline }}'
          namespace: '{{ .CommonLabels.namespace }}'
          runbook: '{{ .CommonAnnotations.runbook_url }}'

  - name: 'pagerduty-platform'
    pagerduty_configs:
      - routing_key_file: '/etc/alertmanager/secrets/pd-platform-key'
        severity: '{{ .CommonLabels.severity }}'

  - name: 'slack-data-eng-warnings'
    slack_configs:
      - channel: '#data-eng-alerts'
        send_resolved: true
        color: '{{ if eq .Status "firing" }}warning{{ else }}good{{ end }}'
        title: '{{ .CommonLabels.alertname }}'
        text: >-
          {{ range .Alerts }}
          • {{ .Annotations.summary }} ({{ .Labels.pipeline }})
          {{ end }}

  - name: 'slack-data-eng-info'
    slack_configs:
      - channel: '#data-eng-info'
        send_resolved: false

  - name: 'slack-monitoring-health'
    slack_configs:
      - channel: '#monitoring-health'
        send_resolved: true

time_intervals:
  - name: business-hours
    time_intervals:
      - weekdays: ['monday:friday']
        times:
          - start_time: '09:00'
            end_time: '18:00'
```

### Custom Alert Webhook Handler

```python
#!/usr/bin/env python3
"""
alert_webhook_handler.py
Receives AlertManager webhooks, enriches alerts, and performs automated actions.
"""

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import httpx
import json
import logging
from datetime import datetime

app = FastAPI(title="Alert Webhook Handler")
logger = logging.getLogger(__name__)

# --- Models ---

class AlertLabel(BaseModel):
    alertname: str
    severity: str
    pipeline: Optional[str] = None
    namespace: Optional[str] = None
    team: Optional[str] = None

class AlertAnnotation(BaseModel):
    summary: Optional[str] = None
    description: Optional[str] = None
    runbook_url: Optional[str] = None

class Alert(BaseModel):
    status: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: str
    endsAt: Optional[str] = None
    fingerprint: str

class AlertManagerPayload(BaseModel):
    version: str
    status: str
    receiver: str
    alerts: List[Alert]
    groupLabels: Dict[str, str]
    commonLabels: Dict[str, str]
    commonAnnotations: Dict[str, str]
    externalURL: str

# --- Enrichment ---

async def enrich_with_ownership(alert: Alert) -> Dict:
    """Look up service ownership from catalog."""
    pipeline = alert.labels.get("pipeline", "")
    
    # Query DataHub or service catalog
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"http://datahub-api:8080/v2/entities/{pipeline}/ownership",
                timeout=5.0
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"Failed to enrich ownership: {e}")
    
    return {"team": "unknown", "oncall": "unknown"}

async def get_recent_changes(pipeline: str) -> List[Dict]:
    """Check for recent deployments that might correlate."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"http://argocd-server:8080/api/v1/applications/{pipeline}/events",
                params={"limit": 5},
                timeout=5.0
            )
            if resp.status_code == 200:
                return resp.json().get("items", [])
        except Exception:
            pass
    return []

# --- Automated Actions ---

async def auto_scale_pipeline(pipeline: str, alert: Alert):
    """Auto-scale a pipeline if lag is high."""
    if alert.labels.get("alertname") == "PipelineLagCritical":
        logger.info(f"Auto-scaling pipeline: {pipeline}")
        async with httpx.AsyncClient() as client:
            await client.patch(
                f"http://flink-operator:8081/v1/deployments/{pipeline}/scale",
                json={"parallelism": "auto"},
                timeout=10.0
            )

async def create_incident(alert: Alert, enrichment: Dict):
    """Create an incident in incident management system."""
    incident = {
        "title": alert.annotations.get("summary", alert.labels["alertname"]),
        "severity": alert.labels["severity"],
        "team": enrichment.get("team", "data-engineering"),
        "source": "alertmanager",
        "alert_fingerprint": alert.fingerprint,
        "started_at": alert.startsAt,
    }
    
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://incident-service:8080/v1/incidents",
            json=incident,
            timeout=10.0
        )

# --- Endpoints ---

@app.post("/webhook/alertmanager")
async def handle_alert(payload: AlertManagerPayload):
    """Main webhook endpoint for AlertManager."""
    logger.info(
        f"Received {len(payload.alerts)} alerts, status={payload.status}, "
        f"receiver={payload.receiver}"
    )
    
    for alert in payload.alerts:
        if alert.status != "firing":
            continue
        
        pipeline = alert.labels.get("pipeline", "")
        
        # Enrich
        enrichment = await enrich_with_ownership(alert)
        changes = await get_recent_changes(pipeline) if pipeline else []
        
        # Automated actions based on alert type
        alertname = alert.labels.get("alertname", "")
        
        if alertname == "PipelineLagCritical" and alert.labels.get("auto_remediate") == "true":
            await auto_scale_pipeline(pipeline, alert)
        
        if alert.labels.get("severity") == "critical":
            await create_incident(alert, enrichment)
        
        # Log enriched alert for audit
        logger.info(json.dumps({
            "event": "alert_processed",
            "alertname": alertname,
            "pipeline": pipeline,
            "severity": alert.labels.get("severity"),
            "ownership": enrichment,
            "recent_changes": len(changes),
            "timestamp": datetime.utcnow().isoformat(),
        }))
    
    return {"status": "ok", "processed": len(payload.alerts)}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

## Pipeline Alert Rules for Data Engineering

```yaml
# pipeline-alert-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: data-pipeline-alerts
  namespace: monitoring
  labels:
    team: data-engineering
spec:
  groups:
    # --- Pipeline Health ---
    - name: pipeline.health
      rules:
        - alert: PipelineDown
          expr: |
            up{job=~".*pipeline.*"} == 0
          for: 2m
          labels:
            severity: critical
            team: data-engineering
          annotations:
            summary: "Pipeline {{ $labels.job }} is down"
            runbook_url: "https://runbooks.company.com/pipeline-down"

        - alert: PipelineHighErrorRate
          expr: |
            pipeline:error_rate:ratio5m > 0.05
          for: 5m
          labels:
            severity: critical
            team: data-engineering
          annotations:
            summary: "Pipeline {{ $labels.pipeline }} error rate {{ $value | humanizePercentage }}"

        - alert: PipelineLatencyP99High
          expr: |
            pipeline:latency_seconds:p99_5m > 30
          for: 10m
          labels:
            severity: warning
            team: data-engineering
          annotations:
            summary: "Pipeline {{ $labels.pipeline }} p99 latency {{ $value }}s (>30s)"

    # --- Kafka Consumer Lag ---
    - name: pipeline.kafka.lag
      rules:
        - alert: KafkaConsumerLagCritical
          expr: |
            kafka:consumer_lag:sum_by_group > 1000000
          for: 5m
          labels:
            severity: critical
            team: data-engineering
            auto_remediate: "true"
          annotations:
            summary: "Consumer group {{ $labels.consumergroup }} lag {{ $value | humanize }}"
            description: "Topic: {{ $labels.topic }}. Auto-scaling will be attempted."

        - alert: KafkaConsumerLagGrowing
          expr: |
            deriv(kafka:consumer_lag:sum_by_group[15m]) > 100
          for: 15m
          labels:
            severity: warning
            team: data-engineering
          annotations:
            summary: "Consumer lag growing for {{ $labels.consumergroup }}"

    # --- Data Freshness ---
    - name: pipeline.freshness
      rules:
        - alert: DataFreshnessViolation
          expr: |
            time() - pipeline_last_successful_run_timestamp_seconds > 3600
          for: 5m
          labels:
            severity: critical
            team: data-engineering
          annotations:
            summary: "Pipeline {{ $labels.pipeline }} hasn't produced data in {{ $value | humanizeDuration }}"

        - alert: DataFreshnessDegraded
          expr: |
            time() - pipeline_last_successful_run_timestamp_seconds > 1800
          for: 5m
          labels:
            severity: warning
            team: data-engineering
          annotations:
            summary: "Pipeline {{ $labels.pipeline }} data is {{ $value | humanizeDuration }} stale"

    # --- SLO Burn Rate (Multi-Window) ---
    - name: pipeline.slo
      rules:
        # Fast burn - 2% budget consumed in 1 hour (pages immediately)
        - alert: SLOBurnRateFast
          expr: |
            (
              sum(rate(pipeline_events_processed_total{status="failed"}[1h])) by (pipeline)
              / sum(rate(pipeline_events_processed_total[1h])) by (pipeline)
            ) > (14.4 * 0.001)
            and
            (
              sum(rate(pipeline_events_processed_total{status="failed"}[5m])) by (pipeline)
              / sum(rate(pipeline_events_processed_total[5m])) by (pipeline)
            ) > (14.4 * 0.001)
          for: 2m
          labels:
            severity: page
            team: data-engineering
            window: 1h
          annotations:
            summary: "High SLO burn rate for {{ $labels.pipeline }} (fast window)"

        # Slow burn - 10% budget consumed in 3 days
        - alert: SLOBurnRateSlow
          expr: |
            (
              sum(rate(pipeline_events_processed_total{status="failed"}[6h])) by (pipeline)
              / sum(rate(pipeline_events_processed_total[6h])) by (pipeline)
            ) > (1 * 0.001)
            and
            (
              sum(rate(pipeline_events_processed_total{status="failed"}[30m])) by (pipeline)
              / sum(rate(pipeline_events_processed_total[30m])) by (pipeline)
            ) > (1 * 0.001)
          for: 15m
          labels:
            severity: warning
            team: data-engineering
            window: 6h
          annotations:
            summary: "Sustained SLO burn for {{ $labels.pipeline }} (slow window)"

    # --- Resource Utilization ---
    - name: pipeline.resources
      rules:
        - alert: PipelineMemoryPressure
          expr: |
            container_memory_working_set_bytes{namespace=~".*pipeline.*"}
            / container_spec_memory_limit_bytes > 0.9
          for: 5m
          labels:
            severity: warning
            team: data-engineering
          annotations:
            summary: "Pipeline pod {{ $labels.pod }} memory at {{ $value | humanizePercentage }}"

        - alert: PipelineCPUThrottled
          expr: |
            rate(container_cpu_cfs_throttled_periods_total{namespace=~".*pipeline.*"}[5m])
            / rate(container_cpu_cfs_periods_total[5m]) > 0.5
          for: 10m
          labels:
            severity: warning
            team: data-engineering
          annotations:
            summary: "Pipeline pod {{ $labels.pod }} CPU throttled {{ $value | humanizePercentage }}"
```

---

## Scaling the Monitoring Stack

### Horizontal Scaling Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Scaled Monitoring Architecture                       │
│                                                                 │
│  Write Path (Horizontal)          Read Path (Horizontal)        │
│  ─────────────────────            ──────────────────────        │
│                                                                 │
│  ┌─────────┐ ┌─────────┐         ┌─────────────────────┐      │
│  │Prom     │ │Prom     │         │   Thanos Query      │      │
│  │Shard 0  │ │Shard 1  │         │   (Fan-out)         │      │
│  │(A-M)    │ │(N-Z)    │         └────────┬────────────┘      │
│  └────┬────┘ └────┬────┘                  │                   │
│       │           │              ┌─────────┼──────────┐        │
│       ▼           ▼              │         │          │        │
│  ┌─────────────────────┐   ┌────▼───┐ ┌───▼───┐ ┌───▼───┐   │
│  │  Thanos Receive     │   │Store-0 │ │Store-1│ │Store-2│   │
│  │  (Write gateway)    │   │(2024Q1)│ │(2024Q2│ │(2024Q3│   │
│  └──────────┬──────────┘   └────────┘ └───────┘ └───────┘   │
│             │                                                  │
│             ▼                                                  │
│  ┌────────────────────────────────────────────────────┐       │
│  │                 Object Storage (S3)                 │       │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │       │
│  │  │Block │ │Block │ │Block │ │Block │ │Block │   │       │
│  │  │  1   │ │  2   │ │  3   │ │  N   │ │ ...  │   │       │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘   │       │
│  └────────────────────────────────────────────────────┘       │
│                                                                 │
│  Compaction (Background)                                        │
│  ┌─────────────────────────────┐                               │
│  │  Thanos Compact             │                               │
│  │  - Merge overlapping blocks │                               │
│  │  - Downsample (5m → 1h)    │                               │
│  │  - Retention enforcement    │                               │
│  └─────────────────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

### Prometheus Sharding Strategy

```yaml
# prometheus-sharding.yaml
# Shard Prometheus instances by hashmod of target labels

apiVersion: monitoring.coreos.com/v1
kind: Prometheus
metadata:
  name: prometheus-shard-0
  namespace: monitoring
spec:
  replicas: 2  # HA within shard
  shards: 4    # Total 4 shards (auto-distributes targets)
  
  # Each shard gets ~25% of targets via hashmod
  # Prometheus Operator handles this automatically with shards field
  
  externalLabels:
    prometheus_shard: "0"
    cluster: production
  
  thanos:
    image: quay.io/thanos/thanos:v0.33.0
    objectStorageConfig:
      key: objstore.yml
      name: thanos-objstore-config
  
  resources:
    requests:
      cpu: "4"
      memory: "16Gi"
    limits:
      cpu: "8"
      memory: "32Gi"
  
  storage:
    volumeClaimTemplate:
      spec:
        storageClassName: gp3-io2
        resources:
          requests:
            storage: 200Gi
```

### Multi-Cluster Monitoring

```yaml
# multi-cluster-thanos.yaml
# Central Thanos Query that federates across clusters

apiVersion: apps/v1
kind: Deployment
metadata:
  name: thanos-query-global
  namespace: monitoring
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: thanos-query
          image: quay.io/thanos/thanos:v0.33.0
          args:
            - query
            - --log.level=info
            - --query.replica-label=prometheus_replica
            - --query.replica-label=rule_replica
            # Local cluster stores
            - --store=dnssrv+_grpc._tcp.thanos-store.monitoring.svc
            # Remote cluster stores (via VPN/peering)
            - --store=thanos-sidecar.us-west-2.internal:10901
            - --store=thanos-sidecar.eu-west-1.internal:10901
            - --store=thanos-sidecar.ap-south-1.internal:10901
            # Query timeout
            - --query.timeout=2m
            - --query.max-concurrent=20
```

---

## Storage Tiering

| Tier | Duration | Resolution | Storage | Cost |
|------|----------|-----------|---------|------|
| Hot | 0-2h | Raw (15s) | Prometheus TSDB (SSD) | $$$ |
| Warm | 2h-15d | Raw (15s) | Thanos Store (S3 Standard) | $$ |
| Cool | 15d-90d | Downsampled (5m) | S3 Standard-IA | $ |
| Cold | 90d-1y | Downsampled (1h) | S3 Glacier | ¢ |

---

## Summary

Building monitoring infrastructure at scale requires treating it as a first-class distributed system:

1. **Separate write and read paths** - Scale independently
2. **Shard by workload** - Prevent hot spots
3. **Use object storage** - Infinite scale for long-term data
4. **Downsample aggressively** - Old data doesn't need second resolution
5. **Alert on alerts** - Monitor the monitoring system independently
6. **Budget monitoring costs** - Track cost per team/service
