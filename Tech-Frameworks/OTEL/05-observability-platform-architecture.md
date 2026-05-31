# Real-World Observability Platform Architecture

## OTEL + VictoriaMetrics + ClickHouse — Unified Logging, Tracing & APM

---

## 1. Platform Vision & Design Philosophy

### Why Build a Custom Observability Platform?

| Concern | SaaS (Datadog/New Relic) | Custom (OTEL + VM + CH) |
|---------|--------------------------|-------------------------|
| Cost at scale | $15-50/host/month + ingestion | Infrastructure cost only |
| Data ownership | Vendor-locked | Full control |
| Retention | 15-30 days standard | Unlimited (tiered storage) |
| Customization | Limited | Fully extensible |
| Vendor lock-in | High (proprietary agents) | Zero (OTEL standard) |
| Data residency | Limited regions | Any region/on-prem |

### Design Principles

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DESIGN PRINCIPLES                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. OTEL-Native: Use OpenTelemetry as the ONLY instrumentation layer │
│  2. Separation of Concerns: Each backend optimized for its signal     │
│  3. Horizontal Scalability: Every component scales independently      │
│  4. Multi-Tenancy: Isolate teams/services at the platform level       │
│  5. Cost Efficiency: Tiered storage, aggressive downsampling          │
│  6. Correlation: Link metrics ↔ traces ↔ logs via trace_id           │
│  7. Open Standards: No proprietary protocols or formats               │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                      │
│                                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Service A│  │ Service B│  │ Service C│  │ Service D│  │ Infrastructure   │ │
│  │ (Java)   │  │ (Go)     │  │ (Python) │  │ (Node.js)│  │ (K8s, VMs, DBs)  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
│       │              │              │              │                  │           │
│       │    OTEL SDK  │   OTEL SDK   │   OTEL SDK  │                  │           │
│       │  (auto-inst) │  (manual)    │  (auto-inst) │                  │           │
└───────┼──────────────┼──────────────┼──────────────┼──────────────────┼───────────┘
        │              │              │              │                  │
        ▼              ▼              ▼              ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        COLLECTION LAYER (OTEL Collectors)                         │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │              OTEL Collector — Agent Mode (DaemonSet)                      │    │
│  │  ┌──────────┐   ┌────────────────┐   ┌───────────────────────────┐     │    │
│  │  │Receivers │   │  Processors    │   │  Exporters                │     │    │
│  │  │• OTLP    │──▶│• Batch         │──▶│• OTLP (to Gateway)       │     │    │
│  │  │• Host    │   │• Memory Limit  │   │• (local buffering/WAL)   │     │    │
│  │  │• Kubelet │   │• K8s Attributes│   └───────────────────────────┘     │    │
│  │  │• Filelog │   │• Resource      │                                      │    │
│  │  └──────────┘   └────────────────┘                                      │    │
│  └──────────────────────────────────┬──────────────────────────────────────┘    │
│                                     │                                            │
│                                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │           OTEL Collector — Gateway Mode (Deployment, 3+ replicas)        │    │
│  │  ┌──────────┐   ┌────────────────┐   ┌───────────────────────────┐     │    │
│  │  │Receivers │   │  Processors    │   │  Exporters                │     │    │
│  │  │• OTLP    │   │• Tail Sampling │   │• Prometheus Remote Write  │──┐  │    │
│  │  │          │   │• Span Metrics  │   │  (→ VictoriaMetrics)      │  │  │    │
│  │  │          │   │• Log Transform │   │• ClickHouse (→ Logs)      │──┼──│──┐ │
│  │  │          │   │• Filter        │   │• ClickHouse (→ Traces)    │──┼──│──┤ │
│  │  │          │   │• Routing       │   │• Kafka (overflow buffer)  │  │  │  │ │
│  │  └──────────┘   └────────────────┘   └───────────────────────────┘  │  │  │ │
│  └──────────────────────────────────────────────────────────────────────┘  │  │ │
└─────────────────────────────────────────────────────────────────────────────┼──┼─┘
                                                                              │  │
        ┌─────────────────────────────────────────────────────────────────────┘  │
        │                                                                        │
        ▼                                                                        ▼
┌──────────────────────────┐                              ┌──────────────────────────┐
│    METRICS BACKEND       │                              │   LOGS + TRACES BACKEND   │
│                          │                              │                            │
│  ┌────────────────────┐  │                              │  ┌────────────────────┐   │
│  │   VictoriaMetrics  │  │                              │  │    ClickHouse      │   │
│  │   Cluster          │  │                              │  │    Cluster         │   │
│  │                    │  │                              │  │                    │   │
│  │  ┌──────────────┐ │  │                              │  │  ┌──────────────┐  │   │
│  │  │   vminsert   │ │  │                              │  │  │  Logs Table  │  │   │
│  │  │  (write path)│ │  │                              │  │  │  (MergeTree) │  │   │
│  │  └──────┬───────┘ │  │                              │  │  └──────────────┘  │   │
│  │         ▼         │  │                              │  │  ┌──────────────┐  │   │
│  │  ┌──────────────┐ │  │                              │  │  │ Traces Table │  │   │
│  │  │  vmstorage   │ │  │                              │  │  │  (MergeTree) │  │   │
│  │  │  (storage)   │ │  │                              │  │  └──────────────┘  │   │
│  │  └──────┬───────┘ │  │                              │  │  ┌──────────────┐  │   │
│  │         ▼         │  │                              │  │  │ Span Metrics │  │   │
│  │  ┌──────────────┐ │  │                              │  │  │ (Materialized│  │   │
│  │  │  vmselect    │ │  │                              │  │  │  View)       │  │   │
│  │  │  (read path) │ │  │                              │  │  └──────────────┘  │   │
│  │  └──────────────┘ │  │                              │  └────────────────────┘   │
│  └────────────────────┘  │                              └──────────────────────────┘
│                          │
│  ┌────────────────────┐  │
│  │   vmalert          │  │
│  │   (alerting rules) │  │
│  └────────────────────┘  │
└──────────────────────────┘
        │                                                        │
        ▼                                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           QUERY & VISUALIZATION LAYER                             │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐│
│  │   Grafana    │  │  Alert       │  │   Custom     │  │   API Gateway        ││
│  │  Dashboards  │  │  Manager     │  │   APM UI     │  │  (internal portal)   ││
│  │  • Metrics   │  │  (routing,   │  │  (service    │  │                      ││
│  │  • Logs      │  │   silencing, │  │   topology,  │  │  • Self-service      ││
│  │  • Traces    │  │   grouping)  │  │   dependency │  │  • SLO dashboard     ││
│  │  • Correlate │  │              │  │   map, RED)  │  │  • Cost attribution  ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Signal Flows — How Data Moves Through the Platform

### 3.1 Metrics Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         METRICS PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────┘

  Application (OTEL SDK)
       │
       │  OTLP/gRPC (port 4317)
       │  Metrics: Counter, Histogram, Gauge
       ▼
  ┌──────────────────────────────────┐
  │  OTEL Collector (Agent)          │
  │                                  │
  │  Receivers:                      │
  │   • otlp (app metrics)          │
  │   • hostmetrics (CPU/mem/disk)   │
  │   • kubeletstats (pod metrics)   │
  │   • prometheus (scrape targets)  │
  │                                  │
  │  Processors:                     │
  │   • resource: add k8s metadata   │
  │   • batch: 5000 metrics/5s       │
  │   • memory_limiter: 512MB        │
  │                                  │
  │  Exporter:                       │
  │   • otlp → Gateway Collector     │
  └───────────────┬──────────────────┘
                  │
                  │  OTLP/gRPC (internal)
                  ▼
  ┌──────────────────────────────────┐
  │  OTEL Collector (Gateway)        │
  │                                  │
  │  Processors:                     │
  │   • filter: drop debug metrics   │
  │   • transform: rename/relabel    │
  │   • routing: tenant isolation    │
  │                                  │
  │  Exporters:                      │
  │   • prometheusremotewrite        │
  │     endpoint: vminsert:8480      │
  │     resource_to_telemetry: true  │
  │     add_metric_suffixes: false   │
  └───────────────┬──────────────────┘
                  │
                  │  Prometheus Remote Write Protocol
                  │  (Snappy-compressed protobufs)
                  ▼
  ┌──────────────────────────────────┐
  │  VictoriaMetrics (vminsert)      │
  │                                  │
  │  • Accepts remote write          │
  │  • Routes to vmstorage shards    │
  │  • Replication factor: 2         │
  │                                  │
  │  Storage:                        │
  │  • Hot: 15 days (NVMe SSD)      │
  │  • Warm: 90 days (SSD)          │
  │  • Cold: 2 years (S3/GCS)       │
  └──────────────────────────────────┘
                  │
                  │  MetricsQL queries
                  ▼
  ┌──────────────────────────────────┐
  │  Grafana (Prometheus datasource) │
  │  • Service dashboards            │
  │  • SLO burn rate                 │
  │  • Infrastructure metrics        │
  └──────────────────────────────────┘
```

**Key Metrics Collected:**

| Category | Metrics | Source |
|----------|---------|--------|
| RED (Request/Error/Duration) | `http_server_request_duration_seconds` | OTEL SDK |
| Runtime | `process_runtime_jvm_memory_usage` | OTEL auto-instrumentation |
| Infrastructure | `system_cpu_utilization`, `system_memory_usage` | hostmetrics receiver |
| Kubernetes | `k8s_pod_cpu_utilization`, `k8s_container_restarts` | kubeletstats receiver |
| Custom Business | `orders_processed_total`, `payment_amount_sum` | Manual OTEL SDK |
| Database | `db_client_connections_usage` | OTEL SDK (db instrumentation) |

---

### 3.2 Logs Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LOGS PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────┘

  Application (structured JSON logs)
       │
       │  Two ingestion paths:
       │
       ├──── Path A: OTEL SDK Log Bridge ────┐
       │     (programmatic, rich context)     │
       │                                      │
       ├──── Path B: File-based collection ───┤
       │     (stdout → container log files)   │
       │                                      ▼
  ┌──────────────────────────────────────────────────────┐
  │  OTEL Collector (Agent - DaemonSet)                   │
  │                                                       │
  │  Receivers:                                           │
  │   • otlp (SDK log bridge — has trace_id, span_id)   │
  │   • filelog (container logs from /var/log/pods/*)     │
  │     ├── multiline: Java stack traces                 │
  │     ├── parse: JSON operator                         │
  │     └── extract: timestamp, severity, body           │
  │                                                       │
  │  Processors:                                          │
  │   • k8sattributes:                                   │
  │     ├── pod_name, namespace, deployment              │
  │     ├── container_name, node_name                    │
  │     └── labels (app, version, team)                  │
  │   • transform:                                       │
  │     ├── extract trace_id from JSON body              │
  │     └── normalize severity levels                    │
  │   • filter:                                          │
  │     └── drop health-check logs (noise)              │
  │   • batch: 10000 logs / 10s                          │
  │                                                       │
  │  Exporter: otlp → Gateway                            │
  └────────────────────────┬─────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────┐
  │  OTEL Collector (Gateway)                             │
  │                                                       │
  │  Processors:                                          │
  │   • routing: by severity                             │
  │     ├── ERROR/FATAL → priority pipeline              │
  │     └── INFO/DEBUG → standard pipeline               │
  │   • transform:                                       │
  │     ├── truncate body > 64KB                         │
  │     └── hash PII fields (email, IP)                  │
  │                                                       │
  │  Exporters:                                           │
  │   • clickhouse:                                      │
  │     ├── endpoint: clickhouse-cluster:9000             │
  │     ├── database: otel_logs                          │
  │     ├── logs_table_name: logs                        │
  │     └── ttl: 30d (hot), 180d (warm)                 │
  │                                                       │
  │  Overflow Protection:                                 │
  │   • kafka exporter (dead letter queue)               │
  │     topic: otel-logs-overflow                        │
  └────────────────────────┬─────────────────────────────┘
                           │
                           │  Native ClickHouse protocol (port 9000)
                           ▼
  ┌──────────────────────────────────────────────────────┐
  │  ClickHouse Cluster                                   │
  │                                                       │
  │  Table: otel_logs.logs                               │
  │  Engine: ReplicatedMergeTree                          │
  │  ORDER BY (ServiceName, SeverityText, Timestamp)      │
  │  PARTITION BY toDate(Timestamp)                       │
  │  TTL Timestamp + INTERVAL 30 DAY TO VOLUME 'warm',   │
  │      Timestamp + INTERVAL 180 DAY DELETE              │
  │                                                       │
  │  Indexes:                                             │
  │   • Primary: ServiceName, Severity, Timestamp        │
  │   • Skip index: TraceId (bloom_filter)               │
  │   • Skip index: Body (tokenbf_v1 — full-text)       │
  └──────────────────────────────────────────────────────┘
                           │
                           │  ClickHouse datasource
                           ▼
  ┌──────────────────────────────────────────────────────┐
  │  Grafana (Logs panel / Explore)                       │
  │  • Full-text search across all logs                  │
  │  • Filter by service, severity, trace_id            │
  │  • Jump from log → trace (via trace_id link)         │
  └──────────────────────────────────────────────────────┘
```

---

### 3.3 Traces Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRACES PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────┘

  Application (OTEL SDK — auto + manual spans)
       │
       │  OTLP/gRPC (port 4317)
       │  TraceContext: traceparent header propagated
       │  across all service-to-service calls
       ▼
  ┌──────────────────────────────────────────────────────┐
  │  OTEL Collector (Agent)                               │
  │                                                       │
  │  Receivers:                                           │
  │   • otlp (all spans from local pods)                 │
  │                                                       │
  │  Processors:                                          │
  │   • resource:                                        │
  │     └── add k8s.pod.name, k8s.namespace.name         │
  │   • memory_limiter: 256MB check_interval=1s          │
  │   • batch: 5000 spans / 5s                           │
  │                                                       │
  │  Exporter: otlp → Gateway (load-balanced)            │
  │            using loadbalancing exporter               │
  │            routing_key: traceID                       │
  │            (ensures all spans of one trace            │
  │             reach the same gateway instance)          │
  └────────────────────────┬─────────────────────────────┘
                           │
                           │  Load-balanced by trace_id
                           ▼
  ┌──────────────────────────────────────────────────────┐
  │  OTEL Collector (Gateway) — Trace Processing          │
  │                                                       │
  │  Processors:                                          │
  │   • groupbytrace:                                    │
  │     └── wait_duration: 10s (assemble full trace)     │
  │   • tail_sampling:                                   │
  │     ├── error spans: always keep                     │
  │     ├── latency > P99: always keep                   │
  │     ├── specific attributes: always keep             │
  │     └── probabilistic: 10% of remaining             │
  │   • spanmetrics:                                     │
  │     ├── generates request/error/duration metrics     │
  │     └── dimensions: service, operation, status_code  │
  │   • servicegraph:                                    │
  │     └── generates inter-service dependency metrics   │
  │                                                       │
  │  Connectors:                                          │
  │   • spanmetrics → metrics pipeline                   │
  │     (feeds VictoriaMetrics with RED metrics          │
  │      derived from traces — no manual instrumentation) │
  │                                                       │
  │  Exporters:                                           │
  │   • clickhouse:                                      │
  │     ├── database: otel_traces                        │
  │     ├── traces_table_name: traces                    │
  │     └── create_schema: true                          │
  └────────────────────────┬─────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────┐
  │  ClickHouse Cluster                                   │
  │                                                       │
  │  Table: otel_traces.traces                           │
  │  Engine: ReplicatedMergeTree                          │
  │  ORDER BY (ServiceName, SpanName, toDateTime(Start))  │
  │  PARTITION BY toDate(Start)                           │
  │                                                       │
  │  Materialized View: otel_traces.trace_id_ts          │
  │  (TraceId → Timestamp mapping for fast trace lookup) │
  │                                                       │
  │  Materialized View: otel_traces.service_graph        │
  │  (Parent → Child service dependency edges)           │
  └──────────────────────────────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────┐
  │  Grafana (Tempo datasource — ClickHouse backend)     │
  │  • Trace waterfall view                              │
  │  • Service dependency map                            │
  │  • Search traces by service, duration, error         │
  │  • Jump from trace → logs (via trace_id)            │
  │  • Jump from trace → metrics (same time window)     │
  └──────────────────────────────────────────────────────┘
```

---

## 4. ClickHouse Schema Design

### 4.1 Logs Table

```sql
CREATE TABLE otel_logs.logs ON CLUSTER '{cluster}'
(
    -- Timestamp and identification
    Timestamp          DateTime64(9) CODEC(Delta, ZSTD(1)),
    TimestampDate      Date DEFAULT toDate(Timestamp),
    TraceId            String CODEC(ZSTD(1)),
    SpanId             String CODEC(ZSTD(1)),
    TraceFlags         UInt32 CODEC(ZSTD(1)),
    
    -- Severity
    SeverityText       LowCardinality(String) CODEC(ZSTD(1)),
    SeverityNumber     Int32 CODEC(ZSTD(1)),
    
    -- Body (the actual log message)
    Body               String CODEC(ZSTD(1)),
    
    -- Resource attributes (service identity)
    ResourceSchemaUrl  String CODEC(ZSTD(1)),
    ResourceAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    ServiceName        LowCardinality(String) CODEC(ZSTD(1)),
    
    -- Scope (instrumentation library info)
    ScopeName          String CODEC(ZSTD(1)),
    ScopeVersion       String CODEC(ZSTD(1)),
    
    -- Log record attributes
    LogAttributes      Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    
    -- Derived columns for fast filtering
    Tenant             LowCardinality(String) 
                       MATERIALIZED ResourceAttributes['tenant.id'],
    Environment        LowCardinality(String)
                       MATERIALIZED ResourceAttributes['deployment.environment'],
    
    -- Projection for full-text search
    INDEX idx_trace_id TraceId TYPE bloom_filter(0.001) GRANULARITY 1,
    INDEX idx_body Body TYPE tokenbf_v1(10240, 3, 0) GRANULARITY 1,
    INDEX idx_severity SeverityText TYPE set(10) GRANULARITY 1
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/otel_logs', '{replica}')
PARTITION BY toDate(Timestamp)
ORDER BY (ServiceName, SeverityText, toUnixTimestamp(Timestamp), TraceId)
TTL 
    Timestamp + INTERVAL 15 DAY TO VOLUME 'warm',
    Timestamp + INTERVAL 90 DAY TO VOLUME 'cold',
    Timestamp + INTERVAL 365 DAY DELETE
SETTINGS 
    index_granularity = 8192,
    ttl_only_drop_parts = 1,
    storage_policy = 'tiered';
```

### 4.2 Traces Table

```sql
CREATE TABLE otel_traces.traces ON CLUSTER '{cluster}'
(
    -- Timestamp
    Timestamp          DateTime64(9) CODEC(Delta, ZSTD(1)),
    
    -- Trace identification
    TraceId            String CODEC(ZSTD(1)),
    SpanId             String CODEC(ZSTD(1)),
    ParentSpanId       String CODEC(ZSTD(1)),
    TraceState         String CODEC(ZSTD(1)),
    
    -- Span details
    SpanName           LowCardinality(String) CODEC(ZSTD(1)),
    SpanKind           LowCardinality(String) CODEC(ZSTD(1)),
    Duration           Int64 CODEC(ZSTD(1)),  -- nanoseconds
    StatusCode         LowCardinality(String) CODEC(ZSTD(1)),
    StatusMessage      String CODEC(ZSTD(1)),
    
    -- Service identity
    ServiceName        LowCardinality(String) CODEC(ZSTD(1)),
    
    -- Resource attributes
    ResourceAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    
    -- Span attributes
    SpanAttributes     Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    
    -- Events (logs attached to spans)
    Events             Nested(
        Timestamp      DateTime64(9),
        Name           LowCardinality(String),
        Attributes     Map(LowCardinality(String), String)
    ) CODEC(ZSTD(1)),
    
    -- Links (to other traces)
    Links              Nested(
        TraceId        String,
        SpanId         String,
        TraceState     String,
        Attributes     Map(LowCardinality(String), String)
    ) CODEC(ZSTD(1)),
    
    -- Indexes
    INDEX idx_trace_id TraceId TYPE bloom_filter(0.001) GRANULARITY 1,
    INDEX idx_duration Duration TYPE minmax GRANULARITY 1,
    INDEX idx_status StatusCode TYPE set(5) GRANULARITY 1
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/otel_traces', '{replica}')
PARTITION BY toDate(Timestamp)
ORDER BY (ServiceName, SpanName, toUnixTimestamp(Timestamp), TraceId)
TTL 
    Timestamp + INTERVAL 7 DAY TO VOLUME 'warm',
    Timestamp + INTERVAL 30 DAY DELETE
SETTINGS 
    index_granularity = 8192,
    ttl_only_drop_parts = 1;
```

### 4.3 Materialized Views for APM

```sql
-- Service-level RED metrics (derived from traces)
CREATE MATERIALIZED VIEW otel_traces.service_metrics
ENGINE = ReplicatedSummingMergeTree('/clickhouse/tables/{shard}/service_metrics', '{replica}')
PARTITION BY toDate(Timestamp)
ORDER BY (ServiceName, SpanName, StatusCode, toStartOfMinute(Timestamp))
AS SELECT
    toStartOfMinute(Timestamp) AS Timestamp,
    ServiceName,
    SpanName,
    StatusCode,
    count() AS RequestCount,
    countIf(StatusCode = 'STATUS_CODE_ERROR') AS ErrorCount,
    sum(Duration) AS TotalDuration,
    quantileState(0.5)(Duration) AS P50Duration,
    quantileState(0.95)(Duration) AS P95Duration,
    quantileState(0.99)(Duration) AS P99Duration
FROM otel_traces.traces
WHERE SpanKind IN ('SPAN_KIND_SERVER', 'SPAN_KIND_CONSUMER')
GROUP BY Timestamp, ServiceName, SpanName, StatusCode;

-- Service dependency graph (which service calls which)
CREATE MATERIALIZED VIEW otel_traces.service_graph
ENGINE = ReplicatedSummingMergeTree('/clickhouse/tables/{shard}/service_graph', '{replica}')
PARTITION BY toDate(Timestamp)
ORDER BY (SourceService, DestinationService, toStartOfHour(Timestamp))
AS SELECT
    toStartOfHour(t.Timestamp) AS Timestamp,
    parent.ServiceName AS SourceService,
    t.ServiceName AS DestinationService,
    count() AS CallCount,
    countIf(t.StatusCode = 'STATUS_CODE_ERROR') AS ErrorCount,
    avg(t.Duration) AS AvgDuration
FROM otel_traces.traces AS t
INNER JOIN otel_traces.traces AS parent
    ON t.ParentSpanId = parent.SpanId 
    AND t.TraceId = parent.TraceId
WHERE t.SpanKind = 'SPAN_KIND_SERVER'
    AND parent.SpanKind = 'SPAN_KIND_CLIENT'
GROUP BY Timestamp, SourceService, DestinationService;

-- Trace ID lookup (find trace by ID in O(1))
CREATE MATERIALIZED VIEW otel_traces.trace_id_ts
ENGINE = ReplicatedReplacingMergeTree('/clickhouse/tables/{shard}/trace_id_ts', '{replica}')
ORDER BY (TraceId)
AS SELECT
    TraceId,
    min(Timestamp) AS Start,
    max(Timestamp) AS End,
    groupUniqArrayArray([ServiceName]) AS Services
FROM otel_traces.traces
GROUP BY TraceId;
```

---

## 5. APM Layer Architecture

### 5.1 How APM Is Built on Top of Signals

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APM LAYER                                     │
│                                                                      │
│  APM is NOT a separate system — it's a QUERY LAYER over             │
│  the three signals (metrics, logs, traces) that provides:           │
│                                                                      │
│  1. Service Catalog (what services exist, who owns them)            │
│  2. Service Health (RED metrics per service from span metrics)      │
│  3. Service Topology (dependency map from trace data)               │
│  4. Error Analysis (grouped errors with stack traces from logs)     │
│  5. Transaction Tracing (end-to-end trace waterfall)                │
│  6. SLO Monitoring (derived from metrics)                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│                    ┌──────────────┐                                  │
│                    │   APM UI     │                                  │
│                    │  (Grafana /  │                                  │
│                    │  Custom SPA) │                                  │
│                    └──────┬───────┘                                  │
│                           │                                          │
│                    ┌──────┴───────┐                                  │
│                    │  APM API     │                                  │
│                    │  Service     │                                  │
│                    └──┬───┬───┬───┘                                  │
│                       │   │   │                                      │
│           ┌───────────┘   │   └───────────┐                         │
│           ▼               ▼               ▼                         │
│  ┌────────────────┐ ┌──────────┐ ┌───────────────┐                │
│  │ VictoriaMetrics│ │ClickHouse│ │  ClickHouse   │                │
│  │  (Metrics)     │ │ (Traces) │ │  (Logs)       │                │
│  │                │ │          │ │               │                │
│  │ • RED metrics  │ │ • Spans  │ │ • Error logs  │                │
│  │ • SLOs         │ │ • Graph  │ │ • Stack trace │                │
│  │ • Saturation   │ │ • P50/99 │ │ • Context     │                │
│  └────────────────┘ └──────────┘ └───────────────┘                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Span Metrics Connector (The APM Secret Weapon)

The OTEL Collector's `spanmetrics` connector automatically derives RED metrics from trace data — this is the core of the APM layer:

```yaml
# Gateway Collector Configuration
connectors:
  spanmetrics:
    histogram:
      explicit:
        buckets: [2ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s]
    dimensions:
      - name: http.method
      - name: http.status_code
      - name: rpc.method
      - name: db.system
      - name: messaging.system
    exemplars:
      enabled: true
    resource_metrics_key_attributes:
      - service.name
      - service.namespace
      - deployment.environment

  servicegraph:
    latency_histogram_buckets: [1ms, 5ms, 10ms, 50ms, 100ms, 500ms, 1s, 5s]
    dimensions:
      - http.method
    store:
      ttl: 2s
      max_items: 1000

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [tail_sampling, batch]
      exporters: [clickhouse/traces, spanmetrics, servicegraph]
    
    # Auto-generated metrics from traces flow here
    metrics/spanmetrics:
      receivers: [spanmetrics, servicegraph]
      processors: [batch]
      exporters: [prometheusremotewrite/victoriametrics]
```

**Generated Metrics (automatic, no SDK code needed):**

| Metric | Type | Description |
|--------|------|-------------|
| `traces_spanmetrics_calls_total` | Counter | Total requests per service/operation |
| `traces_spanmetrics_duration_seconds_bucket` | Histogram | Latency distribution |
| `traces_service_graph_request_total` | Counter | Inter-service call count |
| `traces_service_graph_request_failed_total` | Counter | Inter-service failure count |
| `traces_service_graph_request_server_seconds_bucket` | Histogram | Inter-service latency |

### 5.3 Correlation — Linking Signals Together

```
┌────────────────────────────────────────────────────────────────────────┐
│                    SIGNAL CORRELATION ENGINE                             │
│                                                                         │
│  The secret to a great APM: every signal carries identifiers           │
│  that let you jump between views instantly.                            │
│                                                                         │
│  ┌──────────┐    trace_id     ┌──────────┐    trace_id    ┌─────────┐│
│  │  METRICS │ ◄──(exemplar)──► │  TRACES  │ ◄────────────► │  LOGS   ││
│  │          │                  │          │                │         ││
│  │ time     │    time window   │ span_id  │   span_id     │trace_id ││
│  │ service  │ ◄──────────────► │ service  │ ◄────────────► │span_id  ││
│  └──────────┘                  └──────────┘                └─────────┘│
│                                                                         │
│  HOW IT WORKS:                                                          │
│                                                                         │
│  1. Metric → Trace:                                                    │
│     Metric has exemplar with trace_id                                  │
│     → Click exemplar → Opens trace in Grafana Tempo view               │
│                                                                         │
│  2. Trace → Logs:                                                      │
│     Span has trace_id and span_id                                      │
│     → Query ClickHouse: WHERE TraceId = 'abc' AND SpanId = 'xyz'      │
│     → Shows all logs emitted during that span                          │
│                                                                         │
│  3. Log → Trace:                                                       │
│     Log record has TraceId field                                       │
│     → Click trace_id → Opens full trace waterfall                      │
│                                                                         │
│  4. Metrics → Logs:                                                    │
│     Same service + time window                                         │
│     → Query: WHERE ServiceName = X AND Timestamp BETWEEN t1 AND t2    │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

**Grafana Configuration for Correlation:**

```yaml
# Grafana provisioning/datasources.yaml
apiVersion: 1
datasources:
  - name: VictoriaMetrics
    type: prometheus
    url: http://vmselect:8481/select/0/prometheus
    jsonData:
      exemplarTraceIdDestinations:
        - name: traceID
          datasourceUid: clickhouse-traces

  - name: ClickHouse-Traces
    type: grafana-clickhouse-datasource
    uid: clickhouse-traces
    url: http://clickhouse:8123
    jsonData:
      defaultDatabase: otel_traces
      tracesTable: traces
      traceIdColumn: TraceId
      spanIdColumn: SpanId
      durationColumn: Duration
      serviceName: ServiceName
      operationName: SpanName
      tags:
        - name: ServiceName
          column: ServiceName
      correlations:
        logs:
          datasourceUid: clickhouse-logs
          query: "SELECT * FROM otel_logs.logs WHERE TraceId = '${__trace.traceId}'"

  - name: ClickHouse-Logs
    type: grafana-clickhouse-datasource
    uid: clickhouse-logs
    url: http://clickhouse:8123
    jsonData:
      defaultDatabase: otel_logs
      logsTable: logs
      timeColumn: Timestamp
      messageColumn: Body
      levelColumn: SeverityText
      correlations:
        traces:
          datasourceUid: clickhouse-traces
          field: TraceId
```

---

## 6. End-to-End Request Lifecycle

### A Single HTTP Request — From Ingress to Storage

```
User → API Gateway → Service A → Service B → Database
                                      ↓
                                  Message Queue → Service C

TIME ─────────────────────────────────────────────────────────────────────►

T=0ms   User sends POST /api/orders
        │
        │  [API Gateway creates root span]
        │  traceparent: 00-abc123-span001-01
        ▼
T=2ms   Service A receives request
        │
        │  [OTEL SDK: auto-creates SERVER span]
        │  Span: "POST /api/orders" (span002, parent=span001)
        │  
        │  [Application logs]:
        │  {"msg": "Processing order", "trace_id": "abc123", "user_id": "u789"}
        │  → Collected by filelog receiver, trace_id extracted
        │
        │  [Metrics recorded]:
        │  http_server_active_requests{service="order-svc"} +1
        │
        ├──── HTTP call to Service B ────────────────────────────┐
        │     [OTEL SDK: auto-creates CLIENT span]               │
        │     Span: "POST service-b/validate" (span003)          │
        │     traceparent header propagated automatically         │
        │                                                        ▼
        │                                               T=5ms   Service B
        │                                                       │
        │                                                       │ [SERVER span: span004]
        │                                                       │ [DB query span: span005]
        │                                                       │  db.statement: "SELECT..."
        │                                                       │  db.duration_ms: 12
        │                                                       │
        │                                               T=20ms  Response → Service A
        │                                                       │
        ◄───────────────────────────────────────────────────────┘
        │
T=22ms  Service A publishes to Kafka
        │  [OTEL SDK: PRODUCER span: span006]
        │  messaging.system: kafka
        │  messaging.destination: orders.created
        │
T=25ms  Service A returns 201 Created
        │  [Span span002 ends: duration=25ms, status=OK]
        │
        │  [Metric recorded]:
        │  http_server_request_duration_seconds{status="201"} = 0.025
        │
        ════════════════════════════════════════════════════
        
T=100ms Service C consumes from Kafka
        │  [OTEL SDK: CONSUMER span: span007, parent=span006 via link]
        │  [Processing span: span008]
        │
T=150ms Service C completes
        │  [Log]: {"msg": "Order processed", "order_id": "ord-456", "trace_id": "abc123"}


═══════════════════════════════════════════════════════════════════════════
                      DATA AS STORED IN BACKENDS
═══════════════════════════════════════════════════════════════════════════

VictoriaMetrics (metrics):
  http_server_request_duration_seconds_bucket{
    service_name="order-svc", http_method="POST", 
    http_status_code="201", le="0.05"
  } = 1  @ T=25ms

ClickHouse — Traces:
  TraceId=abc123, SpanId=span002, ParentSpanId=span001
    ServiceName=order-svc, SpanName="POST /api/orders"
    Duration=25000000 (ns), StatusCode=OK
  TraceId=abc123, SpanId=span004, ParentSpanId=span003
    ServiceName=validation-svc, SpanName="POST /validate"
    Duration=15000000 (ns), StatusCode=OK
  TraceId=abc123, SpanId=span005, ParentSpanId=span004
    ServiceName=validation-svc, SpanName="SELECT users"
    Duration=12000000 (ns), SpanKind=CLIENT
  ... (7 spans total in trace abc123)

ClickHouse — Logs:
  Timestamp=T+2ms, ServiceName=order-svc, TraceId=abc123
    Body="Processing order", SeverityText=INFO
  Timestamp=T+150ms, ServiceName=notification-svc, TraceId=abc123
    Body="Order processed", SeverityText=INFO
```

---

## 7. Complete OTEL Collector Configuration

### 7.1 Agent Collector (DaemonSet)

```yaml
# otel-agent-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_recv_msg_size_mib: 4
      http:
        endpoint: 0.0.0.0:4318

  # Collect host-level metrics
  hostmetrics:
    collection_interval: 30s
    scrapers:
      cpu:
        metrics:
          system.cpu.utilization:
            enabled: true
      memory:
        metrics:
          system.memory.utilization:
            enabled: true
      disk: {}
      network: {}
      filesystem:
        exclude_mount_points:
          mount_points: ["/proc/*", "/sys/*"]

  # Collect Kubernetes pod metrics
  kubeletstats:
    collection_interval: 30s
    auth_type: serviceAccount
    endpoint: "https://${env:NODE_IP}:10250"
    insecure_skip_verify: true
    metric_groups:
      - pod
      - container
      - node

  # Collect container logs from filesystem
  filelog:
    include:
      - /var/log/pods/*/*/*.log
    exclude:
      - /var/log/pods/*/otel-collector/*.log  # don't collect own logs
    start_at: end
    include_file_path: true
    include_file_name: false
    operators:
      # Parse container runtime format
      - type: router
        routes:
          - output: parser-docker
            expr: 'body matches "^\\{"'
          - output: parser-cri
            expr: 'body matches "^[^ Z]+ "'
      
      # Docker JSON format
      - id: parser-docker
        type: json_parser
        timestamp:
          parse_from: attributes.time
          layout: "%Y-%m-%dT%H:%M:%S.%LZ"
      
      # CRI format
      - id: parser-cri
        type: regex_parser
        regex: '^(?P<time>[^ Z]+) (?P<stream>stdout|stderr) (?P<logtag>[^ ]*) ?(?P<log>.*)$'
        timestamp:
          parse_from: attributes.time
          layout: "%Y-%m-%dT%H:%M:%S.%L%j"
      
      # Extract trace_id if present in JSON body
      - type: json_parser
        if: 'body matches "trace_id"'
        parse_from: body
        parse_to: attributes

processors:
  # Prevent OOM
  memory_limiter:
    check_interval: 1s
    limit_mib: 512
    spike_limit_mib: 128

  # Add Kubernetes metadata
  k8sattributes:
    auth_type: serviceAccount
    passthrough: false
    extract:
      metadata:
        - k8s.pod.name
        - k8s.pod.uid
        - k8s.namespace.name
        - k8s.node.name
        - k8s.deployment.name
        - k8s.statefulset.name
        - k8s.daemonset.name
        - k8s.container.name
      labels:
        - tag_name: app
          key: app.kubernetes.io/name
        - tag_name: team
          key: team
        - tag_name: version
          key: app.kubernetes.io/version
    pod_association:
      - sources:
          - from: resource_attribute
            name: k8s.pod.ip
      - sources:
          - from: connection

  # Add resource attributes
  resource:
    attributes:
      - key: cluster.name
        value: ${env:CLUSTER_NAME}
        action: upsert
      - key: deployment.environment
        value: ${env:ENVIRONMENT}
        action: upsert

  # Batch for efficiency
  batch:
    send_batch_size: 5000
    send_batch_max_size: 10000
    timeout: 5s

  # Filter noise
  filter/logs:
    logs:
      exclude:
        match_type: regexp
        bodies:
          - ".*healthz.*"
          - ".*readyz.*"
          - ".*livez.*"

exporters:
  # Forward all signals to Gateway
  otlp/gateway:
    endpoint: otel-gateway.observability.svc:4317
    tls:
      insecure: true
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
    sending_queue:
      enabled: true
      num_consumers: 4
      queue_size: 5000
    compression: zstd

extensions:
  health_check:
    endpoint: 0.0.0.0:13133
  pprof:
    endpoint: 0.0.0.0:1777
  zpages:
    endpoint: 0.0.0.0:55679

service:
  extensions: [health_check, pprof, zpages]
  pipelines:
    metrics:
      receivers: [otlp, hostmetrics, kubeletstats]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/gateway]
    
    traces:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/gateway]
    
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, k8sattributes, resource, filter/logs, batch]
      exporters: [otlp/gateway]
  
  telemetry:
    metrics:
      address: 0.0.0.0:8888
    logs:
      level: info
```

### 7.2 Gateway Collector (Deployment)

```yaml
# otel-gateway-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_recv_msg_size_mib: 16

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 2048
    spike_limit_mib: 512

  # Tail-based sampling (keep interesting traces)
  tail_sampling:
    decision_wait: 10s
    num_traces: 100000
    expected_new_traces_per_sec: 1000
    policies:
      # Always keep errors
      - name: errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      # Always keep slow traces
      - name: latency
        type: latency
        latency:
          threshold_ms: 2000
      # Always keep specific operations
      - name: important-operations
        type: string_attribute
        string_attribute:
          key: http.route
          values: ["/api/payments", "/api/orders"]
      # Sample 10% of everything else
      - name: probabilistic
        type: probabilistic
        probabilistic:
          sampling_percentage: 10

  # Transform log records
  transform/logs:
    log_statements:
      - context: log
        statements:
          # Truncate extremely long log bodies
          - truncate_all(attributes, 4096)
          - truncate_all(resource.attributes, 4096)
          # Set severity from numeric if text is missing
          - set(severity_text, "INFO") where severity_number >= 9 and severity_number <= 12 and severity_text == ""
          - set(severity_text, "WARN") where severity_number >= 13 and severity_number <= 16 and severity_text == ""
          - set(severity_text, "ERROR") where severity_number >= 17 and severity_number <= 20 and severity_text == ""

  # Metrics filtering
  filter/metrics:
    metrics:
      exclude:
        match_type: regexp
        metric_names:
          - ".*_debug_.*"
          - "go_gc_.*"

  # Routing by tenant
  routing/metrics:
    from_attribute: tenant.id
    attribute_source: resource
    default_exporters: [prometheusremotewrite/default]
    table:
      - value: team-payments
        exporters: [prometheusremotewrite/payments]
      - value: team-platform
        exporters: [prometheusremotewrite/platform]

  batch/metrics:
    send_batch_size: 10000
    timeout: 10s

  batch/traces:
    send_batch_size: 5000
    timeout: 5s

  batch/logs:
    send_batch_size: 10000
    timeout: 10s

connectors:
  # Generate RED metrics from traces automatically
  spanmetrics:
    histogram:
      explicit:
        buckets: [2ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s]
    dimensions:
      - name: http.method
      - name: http.status_code
      - name: rpc.method
      - name: db.system
      - name: messaging.system
      - name: deployment.environment
    exemplars:
      enabled: true
    resource_metrics_key_attributes:
      - service.name
      - service.namespace

  # Generate service dependency graph metrics
  servicegraph:
    latency_histogram_buckets: [5ms, 10ms, 50ms, 100ms, 500ms, 1s, 5s]
    dimensions:
      - http.method
    store:
      ttl: 5s
      max_items: 5000

exporters:
  # Metrics → VictoriaMetrics
  prometheusremotewrite/default:
    endpoint: http://vminsert.victoriametrics.svc:8480/insert/0/prometheus/api/v1/write
    resource_to_telemetry_conversion:
      enabled: true
    tls:
      insecure: true
    retry_on_failure:
      enabled: true
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 10000

  prometheusremotewrite/payments:
    endpoint: http://vminsert.victoriametrics.svc:8480/insert/1/prometheus/api/v1/write
    resource_to_telemetry_conversion:
      enabled: true

  prometheusremotewrite/platform:
    endpoint: http://vminsert.victoriametrics.svc:8480/insert/2/prometheus/api/v1/write
    resource_to_telemetry_conversion:
      enabled: true

  # Traces → ClickHouse
  clickhouse/traces:
    endpoint: tcp://clickhouse.clickhouse.svc:9000?dial_timeout=10s&compress=lz4
    database: otel_traces
    traces_table_name: traces
    timeout: 10s
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 10000

  # Logs → ClickHouse
  clickhouse/logs:
    endpoint: tcp://clickhouse.clickhouse.svc:9000?dial_timeout=10s&compress=lz4
    database: otel_logs
    logs_table_name: logs
    timeout: 10s
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 10000

  # Dead letter queue for overflow
  kafka:
    brokers: [kafka-0:9092, kafka-1:9092, kafka-2:9092]
    topic: otel-overflow
    encoding: otlp_proto
    producer:
      compression: zstd
      flush_max_messages: 1000

service:
  pipelines:
    # Metrics from applications
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, filter/metrics, routing/metrics, batch/metrics]
      exporters: [prometheusremotewrite/default]

    # Span-derived metrics (RED + service graph)
    metrics/spanmetrics:
      receivers: [spanmetrics, servicegraph]
      processors: [batch/metrics]
      exporters: [prometheusremotewrite/default]

    # Traces with tail sampling
    traces:
      receivers: [otlp]
      processors: [memory_limiter, tail_sampling, batch/traces]
      exporters: [clickhouse/traces, spanmetrics, servicegraph]

    # Logs
    logs:
      receivers: [otlp]
      processors: [memory_limiter, transform/logs, batch/logs]
      exporters: [clickhouse/logs]
```

---

## 8. Kubernetes Deployment Architecture

### 8.1 Namespace Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                                   │
│                                                                       │
│  Namespace: observability                                            │
│  ├── OTEL Collector Agent (DaemonSet, 1 per node)                   │
│  ├── OTEL Collector Gateway (Deployment, 3-5 replicas, HPA)         │
│  ├── VictoriaMetrics Cluster                                        │
│  │   ├── vminsert (Deployment, 3 replicas)                          │
│  │   ├── vmstorage (StatefulSet, 3 replicas, PVCs)                  │
│  │   ├── vmselect (Deployment, 3 replicas)                          │
│  │   ├── vmauth (Deployment, 2 replicas)                            │
│  │   └── vmalert (Deployment, 2 replicas)                           │
│  ├── ClickHouse Cluster                                             │
│  │   ├── ClickHouse Keeper (StatefulSet, 3 replicas)                │
│  │   └── ClickHouse Server (StatefulSet, 3 shards × 2 replicas)    │
│  ├── Grafana (Deployment, 2 replicas)                               │
│  ├── Alertmanager (StatefulSet, 3 replicas)                         │
│  └── Kafka (optional, for overflow buffering)                       │
│      └── StatefulSet, 3 brokers                                     │
│                                                                       │
│  Namespace: application                                              │
│  ├── Service A, B, C, D... (instrumented with OTEL SDK)             │
│  └── Each pod sends OTLP to Agent on the same node via hostPort     │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Resource Sizing Guide

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage | Replicas |
|-----------|-------------|-----------|----------------|--------------|---------|----------|
| OTEL Agent | 100m | 500m | 256Mi | 512Mi | — | 1/node |
| OTEL Gateway | 500m | 2000m | 1Gi | 4Gi | — | 3-5 (HPA) |
| vminsert | 500m | 2000m | 512Mi | 2Gi | — | 3 |
| vmstorage | 1000m | 4000m | 4Gi | 16Gi | 500Gi NVMe | 3 |
| vmselect | 500m | 2000m | 1Gi | 4Gi | — | 3 |
| vmalert | 100m | 500m | 256Mi | 1Gi | — | 2 |
| ClickHouse | 2000m | 8000m | 8Gi | 32Gi | 1Ti NVMe | 3s×2r |
| CH Keeper | 200m | 500m | 512Mi | 1Gi | 10Gi SSD | 3 |
| Grafana | 200m | 1000m | 256Mi | 1Gi | — | 2 |

**Throughput capacity at this sizing:**
- Metrics: ~500K samples/sec ingestion
- Logs: ~200K logs/sec ingestion
- Traces: ~50K spans/sec (after sampling)

### 8.3 HPA for OTEL Gateway

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: otel-gateway
  namespace: observability
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: otel-gateway
  minReplicas: 3
  maxReplicas: 15
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: otelcol_exporter_queue_size
        target:
          type: AverageValue
          averageValue: "5000"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

---

## 9. Alerting Architecture

### 9.1 Alert Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                       ALERTING FLOW                                  │
│                                                                      │
│  VictoriaMetrics ──► vmalert ──► Alertmanager ──► Notification      │
│  (data)              (rules)     (routing)        (PagerDuty/Slack) │
│                                                                      │
│  ClickHouse ──► Custom Alert Service ──► Alertmanager               │
│  (log-based alerts via scheduled queries)                           │
└────────────────────────────────────────────────────────────────────┘
```

### 9.2 SLO-Based Alerting (Multiwindow Multi-Burn-Rate)

```yaml
# vmalert recording rules for SLO
groups:
  - name: slo_recording_rules
    interval: 30s
    rules:
      # Error budget consumption rate (5m window)
      - record: slo:error_budget_consumption:rate5m
        expr: |
          1 - (
            sum(rate(traces_spanmetrics_calls_total{status_code!="STATUS_CODE_ERROR"}[5m])) by (service_name)
            /
            sum(rate(traces_spanmetrics_calls_total[5m])) by (service_name)
          )
      
      # Error budget consumption rate (1h window)
      - record: slo:error_budget_consumption:rate1h
        expr: |
          1 - (
            sum(rate(traces_spanmetrics_calls_total{status_code!="STATUS_CODE_ERROR"}[1h])) by (service_name)
            /
            sum(rate(traces_spanmetrics_calls_total[1h])) by (service_name)
          )

  - name: slo_alerts
    rules:
      # Fast burn (consuming budget 14x normal rate in 5m AND 1h)
      - alert: SLOHighErrorBudgetBurn
        expr: |
          slo:error_budget_consumption:rate5m > (14 * 0.001)
          and
          slo:error_budget_consumption:rate1h > (14 * 0.001)
        for: 2m
        labels:
          severity: critical
          team: "{{ $labels.service_name }}"
        annotations:
          summary: "{{ $labels.service_name }} is burning error budget 14x faster than normal"
          dashboard: "https://grafana.internal/d/slo/{{ $labels.service_name }}"
      
      # Slow burn (consuming budget 3x normal rate in 6h)
      - alert: SLOSlowErrorBudgetBurn  
        expr: |
          slo:error_budget_consumption:rate1h > (3 * 0.001)
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.service_name }} slow error budget burn detected"
```

---

## 10. Data Retention & Cost Optimization

### 10.1 Tiered Retention Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA LIFECYCLE                                     │
│                                                                       │
│  Signal    │ Hot (NVMe)  │ Warm (SSD)  │ Cold (S3)   │ Delete       │
│  ──────────┼─────────────┼─────────────┼─────────────┼────────────  │
│  Metrics   │ 0-15 days   │ 15-90 days  │ 90d-2yr     │ > 2 years   │
│            │ Full res    │ Full res    │ 5m downsamp │              │
│  ──────────┼─────────────┼─────────────┼─────────────┼────────────  │
│  Traces    │ 0-7 days    │ 7-30 days   │ —           │ > 30 days   │
│            │ Full spans  │ Full spans  │             │              │
│  ──────────┼─────────────┼─────────────┼─────────────┼────────────  │
│  Logs      │ 0-15 days   │ 15-90 days  │ 90d-1yr    │ > 1 year    │
│            │ Full detail │ Full detail │ Compressed  │              │
│  ──────────┼─────────────┼─────────────┼─────────────┼────────────  │
│  Span Mtx  │ 0-90 days   │ 90d-1yr    │ 1-3 years  │ > 3 years   │
│  (derived) │ 1m res      │ 5m res     │ 1h res     │              │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 Cost Estimation (100 microservices, moderate traffic)

| Resource | Specification | Monthly Cost (AWS) |
|----------|--------------|-------------------|
| OTEL Agents (20 nodes) | Runs on app nodes, no extra infra | $0 (shared) |
| OTEL Gateway (3× c5.xlarge) | 4 vCPU, 8 GB each | ~$300 |
| VictoriaMetrics (3× i3.xlarge) | 4 vCPU, 30 GB RAM, 950GB NVMe | ~$900 |
| ClickHouse (6× i3.2xlarge) | 8 vCPU, 61 GB RAM, 1.9TB NVMe | ~$4,800 |
| S3 cold storage (10 TB) | Infrequent Access tier | ~$125 |
| Grafana (2× t3.medium) | 2 vCPU, 4 GB each | ~$60 |
| Network transfer | Internal, ~5 TB/month | ~$50 |
| **Total** | | **~$6,235/month** |

**Comparison: Datadog for same scale** ≈ $25,000-50,000/month

---

## 11. High Availability Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MULTI-AZ HA DEPLOYMENT                               │
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────┐  │
│  │      AZ-1            │  │      AZ-2            │  │    AZ-3      │  │
│  │                      │  │                      │  │              │  │
│  │  OTEL Agent (DS)     │  │  OTEL Agent (DS)     │  │ OTEL Agent   │  │
│  │  OTEL Gateway ×1     │  │  OTEL Gateway ×1     │  │ Gateway ×1   │  │
│  │                      │  │                      │  │              │  │
│  │  vminsert ×1         │  │  vminsert ×1         │  │ vminsert ×1  │  │
│  │  vmstorage ×1        │  │  vmstorage ×1        │  │ vmstorage ×1 │  │
│  │  vmselect ×1         │  │  vmselect ×1         │  │ vmselect ×1  │  │
│  │                      │  │                      │  │              │  │
│  │  ClickHouse ×2       │  │  ClickHouse ×2       │  │ CH ×2        │  │
│  │  (shard1-r1,shard2-r2│  │  (shard2-r1,shard3-r2│  │ (shard3-r1,  │  │
│  │                      │  │                      │  │  shard1-r2)  │  │
│  │  CH Keeper ×1        │  │  CH Keeper ×1        │  │ CH Keeper ×1 │  │
│  │                      │  │                      │  │              │  │
│  │  Grafana ×1          │  │  Grafana ×1          │  │              │  │
│  └──────────────────────┘  └──────────────────────┘  └──────────────┘  │
│                                                                          │
│  HA Guarantees:                                                          │
│  • Any single AZ can go down with zero data loss                        │
│  • VictoriaMetrics: replicationFactor=2 across AZs                      │
│  • ClickHouse: each shard has replica in different AZ                   │
│  • OTEL Gateway: traffic routes to healthy AZs via k8s service          │
│  • Dedup on read for VictoriaMetrics (handles duplicate writes)         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Security & Multi-Tenancy

### 12.1 Security Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                                     │
│                                                                          │
│  1. Transport Security                                                   │
│     • mTLS between all OTEL Collectors (agent ↔ gateway)                │
│     • TLS for ClickHouse connections                                    │
│     • Internal traffic via Kubernetes NetworkPolicies                   │
│                                                                          │
│  2. Authentication                                                       │
│     • OTEL Collector: bearer token auth extension                       │
│     • VictoriaMetrics: vmauth with per-tenant tokens                    │
│     • ClickHouse: per-team user accounts with row-level security        │
│     • Grafana: OIDC/SAML integration with team-based access             │
│                                                                          │
│  3. Data Isolation                                                       │
│     • Metrics: tenant label injected by Collector, enforced by vmauth   │
│     • Logs/Traces: ClickHouse row policies filter by ServiceName/team   │
│     • Grafana: datasource-level auth with team scoping                  │
│                                                                          │
│  4. Data Privacy                                                         │
│     • PII scrubbing in OTEL Collector transform processor               │
│     • Log body hashing for sensitive fields                             │
│     • Attribute redaction rules in gateway config                       │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

### 12.2 OTEL Collector PII Scrubbing

```yaml
processors:
  transform/pii:
    log_statements:
      - context: log
        statements:
          # Hash email addresses
          - replace_pattern(body, "([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+)", "REDACTED_EMAIL")
          # Mask credit card numbers
          - replace_pattern(body, "\\b\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}\\b", "REDACTED_CC")
          # Remove bearer tokens from attributes
          - delete_key(attributes, "http.request.header.authorization")
    
    trace_statements:
      - context: span
        statements:
          # Remove sensitive query parameters
          - replace_pattern(attributes["http.url"], "password=[^&]*", "password=REDACTED")
          - replace_pattern(attributes["http.url"], "token=[^&]*", "token=REDACTED")
          # Mask database queries with literals
          - replace_pattern(attributes["db.statement"], "'[^']*'", "'?'")
```

---

## 13. Disaster Recovery & Backup

### 13.1 DR Strategy

| Component | RPO | RTO | Strategy |
|-----------|-----|-----|----------|
| VictoriaMetrics | 1 hour | 4 hours | vmbackup to S3, cross-region replication |
| ClickHouse Logs | 15 min | 2 hours | Replicated tables + S3 backups |
| ClickHouse Traces | 1 hour | 4 hours | Replicated tables (traces less critical) |
| OTEL Config | 0 (GitOps) | 15 min | ArgoCD / Flux from Git |
| Grafana Dashboards | 0 (GitOps) | 15 min | Dashboard-as-code in Git |
| Alert Rules | 0 (GitOps) | 15 min | vmalert rules in Git |

### 13.2 Backpressure & Overflow Handling

```
┌────────────────────────────────────────────────────────────────────┐
│                  BACKPRESSURE MANAGEMENT                             │
│                                                                      │
│  Problem: Backend (ClickHouse/VM) is overloaded or down             │
│                                                                      │
│  Solution: Multi-layer defense                                      │
│                                                                      │
│  Layer 1: OTEL Collector Memory Limiter                             │
│  ├── Soft limit: 80% → start refusing new data                     │
│  └── Hard limit: 90% → force GC and drop data                      │
│                                                                      │
│  Layer 2: Sending Queue (per exporter)                              │
│  ├── In-memory queue: 10,000 items                                  │
│  ├── Persistent queue (file-backed): enabled for critical signals  │
│  └── Retry with exponential backoff: 5s → 30s → 5m max            │
│                                                                      │
│  Layer 3: Kafka Overflow Buffer                                     │
│  ├── When ClickHouse is unreachable → write to Kafka               │
│  ├── Kafka retains data for 24h                                    │
│  └── Kafka consumer backfills ClickHouse when healthy              │
│                                                                      │
│  Layer 4: Adaptive Sampling                                         │
│  ├── When queue > 80% full → increase probabilistic sampling      │
│  └── Drop lowest-priority signals first (DEBUG logs, short traces) │
│                                                                      │
└────────────────────────────────────────────────────────────────────┘
```

---

## 14. Grafana Dashboard Architecture

### 14.1 Dashboard Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│  GRAFANA DASHBOARD HIERARCHY                                         │
│                                                                       │
│  Level 1: Platform Overview                                          │
│  ├── Total request rate across all services                         │
│  ├── Platform-wide error rate                                       │
│  ├── Top 10 slowest services (P99)                                  │
│  └── Infrastructure utilization                                     │
│                                                                       │
│  Level 2: Service Dashboard (one per service)                       │
│  ├── RED metrics (Request rate, Error rate, Duration)               │
│  ├── Saturation (CPU, memory, connections, queue depth)             │
│  ├── SLO burn rate and error budget remaining                       │
│  ├── Recent deployments (annotations)                               │
│  └── Dependency health (upstream/downstream)                        │
│                                                                       │
│  Level 3: Trace Explorer                                            │
│  ├── Search by service, operation, duration, status                 │
│  ├── Trace waterfall with span details                              │
│  └── Jump to related logs                                           │
│                                                                       │
│  Level 4: Log Explorer                                              │
│  ├── Full-text search with filters                                  │
│  ├── Log volume histogram                                          │
│  ├── Structured field extraction                                    │
│  └── Jump to related trace                                          │
│                                                                       │
│  Level 5: Infrastructure                                            │
│  ├── Node metrics (CPU, memory, disk, network)                     │
│  ├── Kubernetes pod/container metrics                               │
│  └── Database metrics (connections, queries, replication lag)       │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 14.2 Key Queries

**Service Error Rate (MetricsQL on VictoriaMetrics):**
```promql
sum(rate(traces_spanmetrics_calls_total{
  status_code="STATUS_CODE_ERROR",
  service_name="$service"
}[5m])) 
/ 
sum(rate(traces_spanmetrics_calls_total{
  service_name="$service"
}[5m]))
```

**P99 Latency (MetricsQL):**
```promql
histogram_quantile(0.99,
  sum(rate(traces_spanmetrics_duration_seconds_bucket{
    service_name="$service",
    span_name="$operation"
  }[5m])) by (le)
)
```

**Error Logs for Service (ClickHouse SQL):**
```sql
SELECT 
    Timestamp,
    Body,
    TraceId,
    LogAttributes['error.type'] AS error_type
FROM otel_logs.logs
WHERE ServiceName = {service:String}
    AND SeverityText IN ('ERROR', 'FATAL')
    AND Timestamp >= now() - INTERVAL 1 HOUR
ORDER BY Timestamp DESC
LIMIT 100
```

**Trace Search (ClickHouse SQL):**
```sql
SELECT 
    TraceId,
    ServiceName,
    SpanName,
    Duration / 1e6 AS duration_ms,
    StatusCode,
    Timestamp
FROM otel_traces.traces
WHERE ServiceName = {service:String}
    AND Duration > {min_duration:UInt64} * 1000000
    AND Timestamp >= now() - INTERVAL 1 HOUR
ORDER BY Duration DESC
LIMIT 50
```

---

## 15. Migration Path from Existing Monitoring

### Phase 1: Parallel Run (Week 1-2)
```
Existing (Prometheus/ELK) ──── still primary
                              │
Application ──── OTEL SDK ──── OTEL Collector ──── New Platform
                              (shadow mode, no alerts)
```

### Phase 2: Validate (Week 3-4)
```
Compare dashboards between old and new platform.
Verify data completeness, latency, accuracy.
Enable alerts in new platform (shadow, don't page).
```

### Phase 3: Cutover (Week 5-6)
```
Route alerts to new platform.
Make new Grafana dashboards primary.
Keep old system running (read-only) for comparison.
```

### Phase 4: Decommission (Week 7-8)
```
Remove old exporters and agents.
Shut down Prometheus/ELK.
Complete migration documentation.
```

---

## 16. Summary — Technology Choice Rationale

| Signal | Backend | Why This Choice |
|--------|---------|-----------------|
| Metrics | VictoriaMetrics | 10x less RAM than Prometheus, native clustering, long-term retention, MetricsQL superset |
| Logs | ClickHouse | Columnar compression (10:1), blazing-fast full-text search, SQL interface, handles PB scale |
| Traces | ClickHouse | Same engine = fewer ops, excellent for time-series + high-cardinality, trace search in ms |
| Collection | OTEL Collector | Vendor-neutral, pluggable processors, single agent for all signals, community-driven |
| Instrumentation | OTEL SDK | One SDK for all signals, auto-instrumentation for 11+ languages, standard semantic conventions |
| Visualization | Grafana | Supports all backends, correlation links, mature alerting, large community |
| Alerting | vmalert + Alertmanager | PromQL-compatible rules, battle-tested routing, silencing, grouping |
| APM | Span Metrics + Custom UI | Zero-cost RED metrics from traces, no separate APM agent needed |

---

## 17. Agent vs Gateway — Architecture Deep Dive

### 17.1 What Are They?

| Aspect | Agent Collector | Gateway Collector |
|--------|----------------|-------------------|
| **Deployment** | DaemonSet (one per node) | Deployment with HPA (pool of replicas) |
| **Location** | Co-located on every K8s node | Centralized in observability namespace |
| **Scope** | Sees only local node's telemetry | Sees telemetry from ALL nodes/agents |
| **Weight** | Lightweight — strict memory limits (128-512 MB) | Heavier — can use more resources for processing |
| **Scaling** | Scales with node count (automatic) | Scales with telemetry volume (HPA on CPU/queue) |
| **Failure blast radius** | One node loses telemetry | Entire cluster loses telemetry (mitigated by replicas) |

### 17.2 Responsibilities

#### Agent Collector (The "Local Post Office")

```
┌─────────────────────────────────────────────────┐
│               K8s Node                          │
│                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  App A  │  │  App B  │  │  App C  │       │
│  └────┬────┘  └────┬────┘  └────┬────┘       │
│       │             │             │             │
│       └─────────────┼─────────────┘             │
│                     ▼                           │
│  ┌─────────────────────────────────────┐       │
│  │         Agent Collector             │       │
│  │  • Receive app telemetry (OTLP)     │       │
│  │  • Scrape node metrics (hostmetrics)│       │
│  │  • Scrape pod metrics (kubelet)     │       │
│  │  • Collect container logs (filelog)  │       │
│  │  • Enrich with K8s metadata         │       │
│  │  • Batch and forward to Gateway     │       │
│  └─────────────────┬───────────────────┘       │
│                     │                           │
└─────────────────────┼───────────────────────────┘
                      │ OTLP/gRPC
                      ▼
              ┌───────────────┐
              │    Gateway    │
              └───────────────┘
```

**Responsibilities:**
1. **Collection** — Gather all signals (metrics, logs, traces) from the local node
2. **Enrichment** — Attach K8s metadata (pod name, namespace, node, labels) while that context is locally available
3. **Protection** — Memory limiter prevents OOM killing (critical for DaemonSets sharing node resources)
4. **Batching** — Aggregate data into efficient chunks before network transmission
5. **Forwarding** — Send everything to Gateway via OTLP/gRPC

#### Gateway Collector (The "Central Sorting Facility")

```
┌───────────────────────────────────────────────────────┐
│              Gateway Collector Pool                     │
│                                                       │
│  Agent-1 ──┐                                          │
│  Agent-2 ──┼──▶ ┌──────────────────────────────┐     │
│  Agent-3 ──┤    │  Gateway Collector (HPA)      │     │
│  Agent-N ──┘    │                               │     │
│                 │  • Global tail-based sampling  │     │
│                 │  • Complex transformations     │     │
│                 │  • Signal routing decisions    │     │
│                 │  • Span-to-metrics generation  │     │
│                 │  • Multi-backend fan-out       │     │
│                 └──────────┬──────┬──────┬──────┘     │
│                            │      │      │            │
└────────────────────────────┼──────┼──────┼────────────┘
                             │      │      │
                   ┌─────────┘      │      └─────────┐
                   ▼                ▼                 ▼
            VictoriaMetrics    ClickHouse           Kafka
            (metrics)          (logs+traces)    (overflow buffer)
```

**Responsibilities:**
1. **Global Decisions** — Tail-based sampling needs ALL spans of a trace (spread across nodes)
2. **Heavy Processing** — Complex transformations, aggregations, metric generation from spans
3. **Routing** — Direct different signals to appropriate backends
4. **Fan-out** — Export to multiple destinations (metrics DB, log store, trace store, Kafka)
5. **Buffering** — Manage backpressure with sending queues and Kafka overflow

### 17.3 Why Two Separate Tiers? (Not Just One Big Collector)

#### Reason 1: Locality Principle

```
WITHOUT Agent (anti-pattern):
  App Pod → Network → Central Collector → Backend
  Problems:
  - Network hop for every span/metric (latency, bandwidth)
  - K8s metadata requires API call FROM the app (expensive)
  - No local buffering if central collector is down

WITH Agent:
  App Pod → localhost → Agent → Network → Gateway → Backend
  Benefits:
  - Apps send to localhost (zero network latency, no DNS)
  - Agent has local access to kubelet API (fast metadata)
  - Agent buffers during Gateway unavailability
```

K8s metadata enrichment is the killer reason — the Agent runs on the same node and can efficiently query the local kubelet for pod labels, namespace, service account, etc. A central collector would need to make cross-node API calls for every piece of telemetry.

#### Reason 2: Failure Isolation

```
Scenario: OOM Kill

Agent OOM (on Node-3):
  - Only Node-3 loses telemetry temporarily
  - Other 99 nodes unaffected
  - DaemonSet auto-restarts the Agent

Gateway OOM (centralized):
  - ALL nodes lose ability to export telemetry
  - But: Agents buffer locally during outage
  - HPA spins up replacement replicas
  - Partial data loss, not total
```

The two-tier model gives you **defense in depth** — a failure at either tier is survivable, not catastrophic.

#### Reason 3: Independent Scaling

```
Agent scaling:
  - Tied to node count (DaemonSet = automatic)
  - Each Agent handles ~50-500 pods worth of telemetry
  - Memory-constrained (shares node with workloads)

Gateway scaling:
  - Tied to telemetry volume (HPA on CPU/queue depth)
  - Each Gateway replica handles thousands of requests/sec
  - Can vertically scale (more CPU/memory for heavy processing)
  - Can horizontally scale (more replicas via HPA)
```

If you combined them, you'd either waste resources (heavy processors on every node) or starve resources (not enough processing power on nodes with many pods).

#### Reason 4: Tail-Based Sampling Requires Global View

```
Trace: user-request-xyz
  Span A (Node-1, Agent-1) → Duration: 5ms    ← looks fine locally
  Span B (Node-2, Agent-2) → Duration: 3ms    ← looks fine locally
  Span C (Node-3, Agent-3) → Duration: 8000ms ← ERROR!

Agent CAN'T decide: "Is this trace interesting?"
  → It only sees its own node's spans
  → Span A looks boring in isolation

Gateway CAN decide: "This trace has an error span"
  → It sees ALL spans from ALL agents
  → It can keep the entire trace (A + B + C)
  → Or drop boring traces where ALL spans are fast and successful
```

This is architecturally impossible without a centralized tier that collects all spans before making sampling decisions.

### 17.4 Data Flow Summary

```
┌─────────────────────── Data Flow ───────────────────────┐
│                                                         │
│  1. GENERATION      App emits spans/metrics/logs        │
│         │                                               │
│         ▼                                               │
│  2. COLLECTION      Agent receives via OTLP (localhost) │
│         │           Agent scrapes hostmetrics/kubelet    │
│         │           Agent tails container log files      │
│         │                                               │
│         ▼                                               │
│  3. ENRICHMENT      Agent adds K8s metadata             │
│         │           Agent adds resource attributes      │
│         │                                               │
│         ▼                                               │
│  4. BATCHING        Agent batches into 200ms windows    │
│         │                                               │
│         ▼                                               │
│  5. FORWARDING      Agent exports via OTLP/gRPC        │
│         │                                               │
│         ▼                                               │
│  6. AGGREGATION     Gateway receives from ALL agents    │
│         │                                               │
│         ▼                                               │
│  7. GLOBAL PROCESS  Gateway: tail sampling, transform,  │
│         │           spanmetrics, routing                 │
│         │                                               │
│         ▼                                               │
│  8. FAN-OUT         Gateway exports to backends         │
│                     • Metrics → VictoriaMetrics         │
│                     • Traces  → ClickHouse              │
│                     • Logs    → ClickHouse              │
│                     • Overflow → Kafka                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 18. Agent Pipeline Components — When Each Is Required

The Agent Collector has three pipeline stages: **Receivers** (data in), **Processors** (data transform), and **Exporters** (data out). Here's exactly when and why each component is needed.

### 18.1 Agent Receivers — "What Data Enters the Agent"

| Receiver | When Required | What It Collects | Without It |
|----------|--------------|------------------|------------|
| `otlp` | **Always** — any app instrumented with OpenTelemetry SDK | Application traces, metrics, and logs sent via gRPC/HTTP to localhost:4317/4318 | Apps have nowhere to send telemetry; data is dropped silently |
| `hostmetrics` | **When you need node-level infra metrics** (CPU, memory, disk, network per node) | System metrics from /proc and /sys: cpu, memory, disk, filesystem, network, load | No visibility into node health; can't correlate app issues with infrastructure |
| `kubeletstats` | **When running in Kubernetes** and you need pod/container resource metrics | Per-pod CPU, memory, network, filesystem usage from the kubelet API | No pod-level resource metrics; can't identify which pod is consuming resources |
| `filelog` | **When you need container logs** collected from node filesystem | Container stdout/stderr logs from /var/log/pods/**/*.log | Must use separate log shipper (Fluentd/Fluent Bit); duplicated infrastructure |

#### Decision Matrix:

```
"Do I need this receiver?"

otlp:
  ✓ You have apps instrumented with OTEL SDK  → YES (always)
  ✓ You receive traces/metrics/logs from apps  → YES
  ✗ You only need infra metrics, no app telemetry → Still YES (future-proof)

hostmetrics:
  ✓ You want node CPU/memory/disk utilization  → YES
  ✓ You need to correlate app issues with node saturation → YES
  ✗ You already have node-exporter + Prometheus → OPTIONAL (avoid duplication)
  ✗ Managed K8s with built-in node monitoring → OPTIONAL

kubeletstats:
  ✓ Running in Kubernetes → YES
  ✓ Need per-pod resource consumption → YES
  ✓ Need container restart counts → YES
  ✗ Bare-metal/VM deployment → N/A (not applicable)
  ✗ Already using kube-state-metrics for this → OPTIONAL

filelog:
  ✓ Want unified log collection in the OTEL pipeline → YES
  ✓ Want logs correlated with traces (trace_id in logs) → YES
  ✗ Already using Fluent Bit/Fluentd/Promtail → OPTIONAL
  ✗ Apps send logs directly via OTLP → NOT NEEDED for those apps
```

### 18.2 Agent Processors — "How Data Is Transformed Before Forwarding"

| Processor | When Required | What It Does | Without It |
|-----------|--------------|--------------|------------|
| `memory_limiter` | **ALWAYS — non-negotiable** | Monitors Agent memory usage, drops data when approaching OOM | Agent gets OOM-killed by K8s, ALL telemetry from that node stops |
| `k8sattributes` | **Always in Kubernetes** | Enriches telemetry with K8s metadata (pod, namespace, node, labels) | Telemetry arrives at backends without context — can't filter by namespace/service |
| `resource` | **When you need static attributes** | Adds fixed attributes like cluster name, environment, region | No way to distinguish which cluster/env telemetry came from |
| `batch` | **ALWAYS — critical for efficiency** | Batches data into time-windows (200ms) and size-limits (8192 items) | Every single span/metric sent as individual request — massive network overhead |
| `filter` | **When you need to drop noise at source** | Drops specific metrics/logs that are known noise (health checks, verbose debug logs) | Useless data flows all the way to Gateway and backends, wasting bandwidth and storage |

#### Processing Order (Critical!):

```yaml
processors:
  # ORDER MATTERS — this is the correct sequence:
  
  1. memory_limiter    # FIRST: protect the Agent from OOM
                       # Must be first — if memory is full, stop accepting data
  
  2. k8sattributes    # SECOND: enrich while on the same node
                       # K8s metadata is only cheaply available locally
  
  3. resource         # THIRD: add static attributes
                       # Must be after k8sattributes (doesn't override dynamic attrs)
  
  4. filter           # FOURTH: drop noise
                       # After enrichment — filter rules may use K8s labels
  
  5. batch            # LAST: batch before export
                       # Must be last — batches the final, filtered, enriched data
```

**Why this order?**
- `memory_limiter` first → prevents OOM before any processing happens
- `k8sattributes` before `filter` → you might filter based on K8s labels (e.g., drop all telemetry from namespace `kube-system`)
- `batch` last → you want to batch the final data, not batch and then drop half of it

#### Decision Matrix:

```
"Do I need this processor?"

memory_limiter:
  ✓ Running as DaemonSet → YES (ALWAYS)
  ✓ Running anywhere with memory constraints → YES (ALWAYS)
  ✗ Never optional. If you skip this, you WILL get OOM-killed eventually.

k8sattributes:
  ✓ Running in Kubernetes → YES
  ✓ Need pod/namespace/labels on telemetry → YES
  ✗ Bare-metal with no K8s → NOT APPLICABLE
  ✗ Apps already embed all metadata via OTEL SDK resource → OPTIONAL

resource:
  ✓ Multi-cluster setup (need cluster name) → YES
  ✓ Multi-environment (need env=prod/staging) → YES
  ✓ Need region/zone attribution → YES
  ✗ Single cluster, single env → OPTIONAL (but still recommended)

batch:
  ✓ Exporting over network → YES (ALWAYS)
  ✗ Never optional. Unbatched export = 10-100x more network calls.

filter:
  ✓ Health check endpoints generating noise → YES
  ✓ Debug-level logs in production → YES
  ✓ Internal K8s system metrics you don't need → YES
  ✗ All telemetry is valuable, nothing to drop → NOT NEEDED
  ✗ Filtering handled at Gateway tier → NOT NEEDED here
```

### 18.3 Agent Exporter — "Where Data Goes After Processing"

| Exporter | When Required | What It Does | Without It |
|----------|--------------|--------------|------------|
| `otlp` (gRPC to Gateway) | **ALWAYS — the only exporter an Agent needs** | Forwards all processed telemetry to the Gateway Collector pool | Data is processed but never leaves the node — total data loss |

#### Why Only OTLP?

```
WRONG (anti-pattern): Agent exports directly to backends
  Agent → VictoriaMetrics  (metrics)
  Agent → ClickHouse       (traces)
  Agent → ClickHouse       (logs)
  
  Problems:
  - Every agent needs credentials for ALL backends
  - No global sampling possible
  - Agent config changes when backends change
  - N agents × M backends = N×M connections
  - Backend overload (100 agents hitting ClickHouse directly)

RIGHT: Agent exports only to Gateway
  Agent → Gateway (single OTLP/gRPC connection)
  
  Benefits:
  - Agent config never changes (always points to gateway-svc:4317)
  - Gateway handles authentication to backends
  - Gateway handles routing, sampling, fan-out
  - 100 agents → 3 gateway replicas → backends (connection pooling)
  - Adding a new backend = change Gateway config only
```

### 18.4 Complete Agent Pipeline — Config with Annotations

```yaml
receivers:
  otlp:                          # ← App telemetry (traces, metrics, logs)
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

  hostmetrics:                   # ← Node-level CPU/memory/disk/network
    collection_interval: 30s
    scrapers:
      cpu: {}
      memory: {}
      disk: {}
      filesystem: {}
      network: {}
      load: {}

  kubeletstats:                  # ← Pod/container resource metrics
    collection_interval: 30s
    auth_type: serviceAccount
    endpoint: "https://${env:K8S_NODE_NAME}:10250"
    insecure_skip_verify: true

  filelog:                       # ← Container stdout/stderr logs
    include: [/var/log/pods/**/*.log]
    operators:
      - type: container
        id: container-parser

processors:
  memory_limiter:                # ← 1st: OOM protection (non-negotiable)
    check_interval: 1s
    limit_mib: 400
    spike_limit_mib: 100

  k8sattributes:                 # ← 2nd: K8s metadata enrichment
    auth_type: serviceAccount
    extract:
      metadata:
        - k8s.pod.name
        - k8s.namespace.name
        - k8s.node.name
        - k8s.deployment.name
      labels:
        - tag_name: app
          key: app.kubernetes.io/name
        - tag_name: version
          key: app.kubernetes.io/version

  resource:                      # ← 3rd: Static attributes
    attributes:
      - key: cluster.name
        value: "production-us-east-1"
        action: upsert
      - key: environment
        value: "production"
        action: upsert

  filter:                        # ← 4th: Noise reduction
    error_mode: ignore
    metrics:
      exclude:
        match_type: strict
        metric_names:
          - k8s.pod.status_reason    # noisy, rarely useful
    logs:
      exclude:
        match_type: regexp
        bodies:
          - "^GET /health"           # health check spam
          - "^GET /ready"

  batch:                         # ← 5th (LAST): Efficient batching
    timeout: 200ms
    send_batch_size: 8192
    send_batch_max_size: 16384

exporters:
  otlp:                          # ← Single destination: Gateway
    endpoint: "otel-gateway.observability.svc:4317"
    tls:
      insecure: false
      ca_file: /etc/tls/ca.crt
    sending_queue:
      enabled: true
      num_consumers: 4
      queue_size: 1000
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp]
    metrics:
      receivers: [otlp, hostmetrics, kubeletstats]
      processors: [memory_limiter, k8sattributes, resource, filter, batch]
      exporters: [otlp]
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, k8sattributes, resource, filter, batch]
      exporters: [otlp]
```

### 18.5 Key Takeaways

| Principle | Agent | Gateway |
|-----------|-------|---------|
| Collect from | Local sources (apps, node, kubelet, files) | Other collectors (Agents) |
| Process | Lightweight: enrich, protect, batch | Heavyweight: sample, transform, generate metrics |
| Export to | Gateway only (single OTLP) | Multiple backends (VM, CH, Kafka) |
| Scale with | Node count (DaemonSet) | Telemetry volume (HPA) |
| Memory budget | Strict (128-512 MB, shares node) | Generous (1-4 GB, dedicated pods) |
| Config changes | Rare (same pipeline for all nodes) | Frequent (sampling rules, routing, backends) |

---

## Next Steps

→ See `06-scalability-and-production-design.md` for:
- Horizontal scaling patterns for each component
- Capacity planning formulas
- Federation across clusters/regions
- Performance benchmarking results
- Operational runbooks
