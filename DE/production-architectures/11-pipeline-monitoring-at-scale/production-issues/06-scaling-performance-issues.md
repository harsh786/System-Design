# Production Issues #76-90: Scaling & Performance Issues

## Context
At scale: 100K+ monitored services, 50M+ time series, petabyte-scale data platforms.
Companies: Google, Meta, Netflix, Uber operating planet-scale observability systems.

---

## Issue #76: Monitoring System Itself Under-Provisioned During Incidents

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Monitoring Crumbles When You Need It Most                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: Every major incident                                       │
│                                                                         │
│  THE PARADOX:                                                           │
│  Normal: 1M metrics/sec, system at 40% capacity                       │
│  Incident: error metrics spike → 5M metrics/sec                       │
│  + 50 engineers open dashboards → 500 queries/sec (10x normal)        │
│  + Log volume spikes 10x → log pipeline saturated                     │
│                                                                         │
│  RESULT:                                                                │
│  Monitoring provisioned for normal load fails during incidents         │
│  → Dashboards timeout → engineers can't see what's broken             │
│  → MONITORING FAILS DURING INCIDENTS (the only time it matters)       │
│                                                                         │
│  IRONY SCALE:                                                           │
│  Calm: monitoring works perfectly, nothing to see                     │
│  Crisis: monitoring breaks, everything to see                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Provision monitoring for 5x peak (not average)
# If normal is 40% utilization → can handle 2.5x spike
# Design for: 10x metric volume + 10x query volume simultaneously

# 2. Query priority queue (incident responders first)
grafana:
  auth:
    # Incident commander gets priority query queue
    priority_users: ["sre-team", "incident-commanders"]

# 3. Pre-computed incident dashboards
# During incidents: serve from pre-aggregated recording rules
# Don't compute from raw metrics in real-time
groups:
  - name: incident_readiness
    interval: 15s  # Pre-compute every 15s
    rules:
      - record: service:error_rate:5m
        expr: sum(rate(errors[5m])) by (service)
      - record: service:latency_p99:5m
        expr: histogram_quantile(0.99, rate(latency_bucket[5m])) by (service)

# 4. Separate read/write infrastructure
# Write path: dedicated ingesters (not shared with queries)
# Read path: dedicated queriers (autoscale on query load)
# During incident: scale read path independently
```

---

## Issue #77: Time Series Database Write Amplification

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: TSDB Compaction I/O Causing Write Latency Spikes              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Every compaction cycle (2-4 hours)                         │
│                                                                         │
│  SCENARIO:                                                              │
│  Prometheus TSDB with 10M series:                                      │
│  - Ingestion: 1M samples/sec continuously                             │
│  - Every 2h: head block compaction → writes 50GB to disk              │
│  - Compaction + ongoing ingestion compete for disk I/O                │
│  - Write latency spikes: normal 1ms → 100ms during compaction        │
│  - Scrapes timeout → gaps in metrics                                   │
│                                                                         │
│  DISK I/O MATH:                                                         │
│  Ingestion: 1M samples × 16 bytes × 2 (WAL + head) = 32MB/sec       │
│  Compaction: 50GB in 10 min = 83MB/sec                                │
│  Total: 115MB/sec sustained → exceeds gp2 EBS throughput (128MB/s)   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Use high-IOPS storage
# EBS gp3 with provisioned throughput: 1000MB/s
# Or: local NVMe (i3.xlarge) for hot data, EBS for cold

# 2. Separate WAL and data directories
# WAL on fast SSD: /mnt/nvme/wal (writes every second)
# Data on throughput disk: /mnt/ebs/data (compaction writes)
prometheus:
  storage:
    tsdb:
      wal-directory: /mnt/nvme/wal
      path: /mnt/ebs/data

# 3. External compaction (Thanos Compactor / Mimir Compactor)
# Don't compact on ingestion nodes
# Separate compactor nodes with burst capacity
# Ingestion nodes only handle recent data (head block)

# 4. Victoria Metrics (alternative)
# Uses merge-tree storage (less write amplification)
# No compaction-related I/O spikes
# Better for high-cardinality workloads
```

---

## Issue #78: Grafana Dashboard Loading Time > 30 Seconds

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Dashboards Unusable Due to Slow Queries                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: For complex dashboards (daily use)                         │
│                                                                         │
│  SCENARIO:                                                              │
│  "Service Overview" dashboard: 50 panels                               │
│  Each panel: 1-3 PromQL queries                                       │
│  Total: 120 queries fired simultaneously on dashboard load            │
│  Each query: scans 500K series over 6h range                          │
│  → Prometheus query queue saturated                                    │
│  → Dashboard takes 45 seconds to fully load                           │
│  → Engineers stop using dashboards → fly blind                        │
│                                                                         │
│  COMMON OFFENDERS:                                                      │
│  - topk(10, ...) over 1M series → expensive sort                     │
│  - rate() over 24h range → massive data scan                          │
│  - Regex label matchers: {service=~".*api.*"}                         │
│  - Nested subqueries: avg_over_time(rate(...)[1h:1m])                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Recording rules for dashboard queries
# Pre-compute expensive queries, dashboard reads pre-computed results
groups:
  - name: dashboard_precompute
    interval: 30s
    rules:
      - record: service:request_rate:5m
        expr: sum(rate(http_requests_total[5m])) by (service)
      - record: service:error_rate:5m
        expr: sum(rate(http_errors_total[5m])) by (service) / sum(rate(http_requests_total[5m])) by (service)
      - record: service:latency_p99:5m
        expr: histogram_quantile(0.99, sum(rate(http_duration_bucket[5m])) by (service, le))

# Dashboard uses: service:request_rate:5m (instant lookup)
# Instead of: sum(rate(http_requests_total[5m])) by (service) (full scan)

# 2. Query caching (Thanos Query Frontend)
query_frontend:
  cache_results: true
  split_queries_by_interval: 24h
  max_retries: 3
  results_cache:
    cache:
      memcached:
        addresses: memcached:11211
        max_item_size: 10485760

# 3. Dashboard design best practices
# - Max 20 panels per dashboard (split into sub-dashboards)
# - Default time range: 1h (not 24h)
# - Use $__rate_interval instead of hardcoded [5m]
# - Lazy loading: panels load only when scrolled into view
# - Template variables with defined options (not regex search)
```

---

## Issue #79: Kubernetes Pod Churn Creating Metric Series Churn

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Short-Lived Pods Create Millions of Abandoned Series          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Continuous in auto-scaling / CI/CD heavy environments      │
│                                                                         │
│  SCENARIO:                                                              │
│  Kubernetes cluster: 5000 pods normally                                │
│  Auto-scaling: 500 pods created/destroyed per hour                    │
│  Each pod: 100 metrics with pod_name label                            │
│  → 500 × 100 = 50,000 new series per hour                            │
│  → 50,000 series become stale (pod died) per hour                     │
│  → After 1 week: 8.4M stale series in TSDB                           │
│  → Series churn (creation + stale marking) causes memory pressure     │
│                                                                         │
│  EVEN WORSE: CI/CD jobs                                                 │
│  1000 CI jobs/day × unique job_id label × 50 metrics                  │
│  = 50,000 series that live for 5 minutes then go stale                │
│  = TSDB optimized for long-lived series, not ephemeral                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Drop high-churn labels at collection
metric_relabel_configs:
  # Don't use pod name as label (use deployment/statefulset instead)
  - source_labels: [__name__, pod]
    action: labeldrop
    regex: "pod"
  # Keep: deployment, namespace, container (stable labels)

# 2. Aggregate away ephemeral identifiers
# Use recording rules that remove pod-level granularity
- record: deployment:cpu_usage:avg
  expr: avg(container_cpu_usage_seconds_total) by (namespace, deployment)
  # Survives pod churn

# 3. Reduce TSDB head series retention for short-lived series
# Configure out-of-order tolerance and staleness
--storage.tsdb.min-block-duration=30m  # Compact faster
--storage.tsdb.head-chunks-write-queue-size=1000000

# 4. Victoria Metrics (handles churn better)
# Active time series tracking: only count series with recent data
# Automatic cleanup of stale series (no manual intervention)
# -search.maxStalenessInterval=5m
```

---

## Issue #80: Cross-Region Query Latency (500ms+ for Global View)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Querying Metrics Across Regions Takes Too Long                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Every global dashboard load                                │
│                                                                         │
│  SCENARIO:                                                              │
│  5 regions: us-east, us-west, eu-west, ap-south, ap-northeast         │
│  Global dashboard: sum(rate(requests[5m])) by (region)                │
│  Query fans out to 5 Thanos Store Gateways across regions             │
│  → Network round-trip: 50ms (us-east to ap-northeast)                 │
│  → Data transfer: 100MB across WAN (cost + latency)                   │
│  → Slowest region determines query response time                      │
│  → Total: 500ms-2s for simple global query                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Federated recording rules (pre-aggregate per region)
# Each region computes its own aggregates
# Global query reads only aggregated results

# In each region's Prometheus:
- record: region:requests:rate5m
  expr: sum(rate(http_requests_total[5m]))
  labels:
    region: "us-east-1"

# Global Thanos only needs to read 5 time series (one per region)
# Instead of 50M series across regions

# 2. Global view replica (push aggregates to central)
# Each region → remote_write aggregated metrics → central Thanos
# Central has pre-aggregated global view
# No cross-region fan-out for common queries

# 3. Caching layer for global dashboards
# Cache results for 30s (acceptable staleness for global view)
# Serve from cache during network issues

# 4. Partial response mode
thanos_query:
  --query.partial-response  # Return data from available regions
  # Don't fail entire query if one region is slow/down
  # Show: "4/5 regions reporting" indicator on dashboard
```

---

## Issue #81: OpenTelemetry Collector Memory Leak Under Load

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: OTel Collector Memory Grows Until OOM                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Weekly (under sustained high load)                         │
│                                                                         │
│  SCENARIO:                                                              │
│  OTel Collector processing 500K spans/min                              │
│  Batch processor queues spans for 5 seconds before flush              │
│  Backend (Tempo) slows down → flush takes 10s instead of 1s           │
│  → Queue grows: 500K/min × 10s buffer = 83K spans in memory          │
│  → Memory: 83K × 5KB avg span = 415MB in batch queue                 │
│  → Backend stays slow → queue keeps growing                           │
│  → 30 minutes: 2.5GB in queue → OOM at 4GB limit                    │
│                                                                         │
│  AFTER OOM:                                                             │
│  Pod restarts → all queued spans lost → gap in traces                 │
│  Flood of re-sent spans from upstream buffers → immediate OOM again   │
│  → OOM loop: restart → flood → OOM → restart                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Memory limiter processor (MUST be first in pipeline)
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 3500       # Hard limit (under pod limit of 4GB)
    spike_limit_mib: 800  # Headroom for spikes
    # When limit reached: start dropping data (not OOM)

# 2. Sending queue with bounded size
exporters:
  otlp:
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 5000  # Max 5000 batches queued (bounded!)
    retry_on_failure:
      enabled: true
      max_elapsed_time: 300s  # Give up after 5 minutes

# 3. Backpressure propagation (tell upstream to slow down)
receivers:
  otlp:
    protocols:
      grpc:
        max_recv_msg_size_mib: 4
        max_concurrent_streams: 100  # Limit concurrent streams

# 4. Monitor collector memory trend
- alert: OTelCollectorMemoryGrowing
  expr: |
    deriv(process_runtime_total_alloc_bytes{service="otel-collector"}[10m]) > 50000000
  for: 5m
  annotations:
    summary: "OTel Collector memory growing at >50MB/min - will OOM"
```

---

## Issue #82: Prometheus Vertical Scaling Ceiling (Single Node Limit)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Can't Add More Series to Single Prometheus                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High - Architectural)                                   │
│  Frequency: Once (growth ceiling hit)                                   │
│                                                                         │
│  SCENARIO:                                                              │
│  Single Prometheus instance: 15M active time series                    │
│  Memory: 120GB (approaching maximum practical node size)              │
│  Ingestion: 2M samples/sec (approaching write throughput limit)       │
│  Query: some queries scan 15M series → 60s timeout                    │
│                                                                         │
│  OPTIONS (all painful):                                                 │
│  1. Bigger node → diminishing returns, cost prohibitive               │
│  2. Horizontal sharding → application-level complexity                │
│  3. Move to Mimir/Cortex → migration risk                            │
│  4. Reduce metrics → organizational resistance                        │
│                                                                         │
│  PROMETHEUS LIMITS (practical):                                         │
│  - 20-30M series per instance (memory bound)                          │
│  - 3-5M samples/sec ingestion (CPU bound)                             │
│  - 100GB+ RAM for large instances                                      │
│  - 2h head block compaction can cause issues                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# Migration path: Prometheus → Mimir (horizontal)

# Phase 1: Add Mimir as remote write target (parallel)
remote_write:
  - url: http://mimir-distributor:8080/api/v1/push
# Both Prometheus and Mimir have data (no gap during migration)

# Phase 2: Point Grafana to Mimir for reads
# Validate: same query, same results from both sources

# Phase 3: Shard Prometheus by service/namespace
# prometheus-infra: scrapes infrastructure metrics
# prometheus-apps: scrapes application metrics  
# Both write to central Mimir

# Phase 4: Consider removing Prometheus entirely
# Use Mimir ingesters directly (Prometheus-compatible)
# Or: Grafana Agent/Alloy as lightweight scraper → Mimir

# Mimir architecture for 100M+ series:
# Distributors: 5 replicas (handle writes)
# Ingesters: 20 replicas (in-memory recent data)
# Store gateways: 10 replicas (read from S3)
# Compactor: 3 replicas (compact blocks)
# Queriers: 10 replicas (handle queries, auto-scale)
```

---

## Issue #83: Log Storage Costs Exceeding Compute Costs

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Spending More on Log Storage Than Application Compute         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium - Cost)                                          │
│  Frequency: Continuous (architecture problem)                          │
│                                                                         │
│  COST BREAKDOWN (typical large company):                                │
│  Application compute (EKS): $200K/month                               │
│  Log storage & processing:                                              │
│  - Elasticsearch cluster: $150K/month (20 nodes × r5.4xlarge)        │
│  - S3 log archive: $30K/month                                          │
│  - Log processing (Fluentd/Vector): $20K/month                        │
│  - DataDog log management: $180K/month                                 │
│  TOTAL LOGGING: $380K/month (1.9x application cost!)                  │
│                                                                         │
│  WHY:                                                                   │
│  - Logs are verbose (full request/response bodies)                    │
│  - Every service logs everything at INFO level                        │
│  - 30-day retention of ALL logs (no tiering)                          │
│  - No sampling or aggregation of repetitive logs                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Log level governance by environment
# Production: WARN + ERROR (except sampled DEBUG)
# Staging: INFO
# Development: DEBUG
# Saves: 80% of log volume (most logs are DEBUG/INFO)

# 2. Tiered storage with different retention
# Hot (Loki/ES): 3 days, full searchability - $$$
# Warm (S3 + Athena): 30 days, queryable on demand - $$
# Cold (S3 Glacier): 1 year, compliance only - $

# 3. Structured metrics instead of logs
# BAD: log.info(f"Request processed in {duration}ms for user {user_id}")
# 1000 req/sec × 200 bytes = 200KB/sec of logs
# 
# GOOD: request_duration.observe(duration, labels={"endpoint": path})
# 1 time series, 8 bytes/sample, 1 sample/15s = 0.5 bytes/sec
# 400,000x more efficient for the same information!

# 4. Smart sampling for repetitive logs
# Same error message 10,000 times → keep first + count
# "Connection timeout to db-host" × 10,000 → store 1 + count=10000
transforms:
  reduce_repetitive:
    type: "reduce"
    inputs: ["app_logs"]
    group_by: ["message_template", "service"]
    merge_strategies:
      message: "retain"
      count: "sum"
    ends_when: "duration_ms > 30000"  # Aggregate over 30s windows
```

---

## Issue #84: Monitoring Agent CPU Overhead on Application Nodes

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Observability Agents Consuming 15%+ of Node CPU               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Continuous (accumulates with each new agent)               │
│                                                                         │
│  TYPICAL NODE OVERHEAD:                                                 │
│  - Prometheus node_exporter: 1% CPU                                    │
│  - Fluent Bit (log collector): 3% CPU                                  │
│  - OTel Collector: 2% CPU                                              │
│  - DataDog agent: 3% CPU                                               │
│  - kube-state-metrics: 2% CPU                                          │
│  - cAdvisor: 2% CPU                                                    │
│  - Security agent (Falco): 3% CPU                                      │
│  TOTAL: 16% CPU consumed by agents                                     │
│                                                                         │
│  AT SCALE:                                                              │
│  1000 nodes × 16% = 160 nodes worth of compute for monitoring        │
│  Cost: 160 × $500/month = $80,000/month just for agent overhead       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Consolidate agents (one agent to rule them all)
# Replace: node_exporter + Fluent Bit + OTel Collector + DD agent
# With: Single OTel Collector (or Grafana Alloy)
# Handles: metrics scraping + log collection + trace reception
# Overhead: 3-5% instead of 16%

# 2. Resource limits on agents
resources:
  requests:
    cpu: 100m     # 10% of 1 core
    memory: 256Mi
  limits:
    cpu: 500m     # Hard cap at 50% of 1 core
    memory: 512Mi

# 3. Sampling at the agent level (reduce processing)
# Don't process every log line
# Sample traces at 10% at agent level (not backend)
# Scrape less frequently (30s → 60s) for non-critical metrics

# 4. eBPF-based observability (zero-agent approach)
# Pixie / Cilium Hubble: kernel-level observability
# No sidecar, no agent, minimal CPU overhead
# Captures: network traffic, syscalls, HTTP/gRPC automatically
```

---

## Issue #85: Alert Rule Evaluation Backlog (Rules Not Evaluated on Time)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: 10,000 Alert Rules Can't All Evaluate in 15 Seconds           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: When alert rule count exceeds threshold                    │
│                                                                         │
│  SCENARIO:                                                              │
│  10,000 alert rules, evaluation interval: 15 seconds                  │
│  Some rules are expensive (regex, high cardinality, subqueries)       │
│  Total evaluation time exceeds 15 seconds                              │
│  → Rules evaluated late → alerts fire late → detection delay          │
│  → Some rules skipped entirely → silent alert failure                 │
│                                                                         │
│  MATH:                                                                  │
│  10,000 rules × 50ms average evaluation = 500 seconds                 │
│  With 8 concurrent evaluators: 500/8 = 62.5 seconds                  │
│  Evaluation interval: 15 seconds → 4x behind                         │
│  → Rules evaluated every 60s instead of 15s                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Monitor rule evaluation performance
- alert: RuleEvaluationSlow
  expr: |
    prometheus_rule_group_last_duration_seconds 
    > prometheus_rule_group_interval_seconds
  for: 5m
  annotations:
    summary: "Rule group {{ $labels.rule_group }} takes longer than its interval"

# 2. Optimize expensive rules
# Find slow rules:
topk(10, prometheus_rule_evaluation_duration_seconds)

# Common fixes:
# - Add recording rules for subexpressions
# - Reduce label matchers (be more specific)
# - Replace regex with exact match where possible
# - Reduce range vectors (5m → 2m)

# 3. Distribute rules across multiple Prometheus instances
# Shard rule evaluation:
# prometheus-rules-1: rules for services A-M
# prometheus-rules-2: rules for services N-Z
# Each evaluates fewer rules, finishes faster

# 4. Use Mimir Ruler (horizontally scalable)
# Distributes rule evaluation across multiple pods
# Auto-scales based on rule count and complexity
mimir:
  ruler:
    ring:
      num_tokens: 128
    evaluation_concurrency: 4
    max_rules_per_rule_group: 100
```

---

## Issue #86: Kafka Consumer Lag Monitor Itself Lagging

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Lag Monitoring Tool Can't Keep Up with Kafka Scale            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: As Kafka cluster grows                                     │
│                                                                         │
│  SCENARIO:                                                              │
│  Kafka: 500 topics × 100 partitions = 50,000 partitions               │
│  Consumer groups: 200                                                   │
│  Total offset checks: 50,000 × 200 = 10M offset lookups per cycle    │
│                                                                         │
│  Burrow/Kafka Lag Exporter: polls offsets every 30 seconds            │
│  10M lookups in 30s = 333K requests/sec to Kafka                      │
│  → Kafka coordinator overwhelmed                                       │
│  → Lag monitor itself falls behind                                     │
│  → Reports stale lag numbers (20 minutes old)                          │
│  → Lag looks "stable" because numbers aren't updating                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Use Kafka's built-in consumer lag metrics (JMX)
# Instead of external polling: expose from broker directly
# records-lag-max per consumer group (already computed by Kafka)
kafka:
  jmx:
    metrics:
      - name: kafka.consumer.fetch-manager-metrics.records-lag-max
        labels: [client-id, topic, partition]

# 2. Strimzi/Kafka Exporter (efficient batch queries)
# Queries __consumer_offsets topic directly (not per-partition API)
# Single read of offsets topic → all consumer group lags

# 3. Tiered monitoring frequency
# Critical consumer groups: check every 10s
# Standard: check every 60s
# Low-priority: check every 5 minutes
# Reduces load by 80% while keeping critical monitoring fast

# 4. Push-based lag reporting from consumers
# Each consumer reports its own lag (no external polling)
from prometheus_client import Gauge

consumer_lag = Gauge('kafka_consumer_lag', 'Consumer lag',
                     ['topic', 'partition', 'group'])

# Consumer calculates: high_watermark - committed_offset
# Pushes to Prometheus directly (no external poller needed)
```

---

## Issue #87: Dashboard Sprawl (5000 Dashboards, Nobody Knows Which to Use)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Too Many Dashboards, Can't Find the Right One                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium - Organizational)                                │
│  Frequency: Constant                                                    │
│                                                                         │
│  SCENARIO:                                                              │
│  Search "payment" in Grafana → 47 dashboards                          │
│  - "Payment Service (OLD)"                                             │
│  - "Payment Service v2"                                                 │
│  - "Payment Service - John's Copy"                                     │
│  - "Payments Overview (deprecated)"                                    │
│  - "Payment Metrics - DO NOT DELETE"                                   │
│  - "Payment SLA Dashboard (CURRENT)"                                   │
│  → Which one is correct? → Ask in Slack → 15 min delay               │
│                                                                         │
│  DURING INCIDENT:                                                       │
│  New on-call opens wrong dashboard → misleading data                  │
│  → Wrong diagnosis → wrong fix attempted → incident extended          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Dashboard ownership and lifecycle
# Every dashboard must have:
# - Owner (team)
# - Status: active / deprecated / archive
# - Last used date (auto-tracked)
# - Review date (quarterly)

# Automated cleanup:
# Dashboard not viewed in 90 days → flag for deletion
# Dashboard with "DEPRECATED" in title → auto-archive after 30 days

# 2. Dashboard hierarchy (Golden Signals)
# Level 0: Executive (1 dashboard - everything green/red)
# Level 1: Service overview (1 per service - 4 golden signals)
# Level 2: Debug dashboards (per subsystem - detailed)
# Level 3: Ad-hoc exploration (temporary, auto-expire in 7 days)

# 3. Dashboard registry in service catalog
# Each service links to exactly ONE canonical dashboard
# Alert annotations link to canonical dashboard
# On-call runbook links to canonical dashboard

# 4. Grafana: folder structure + permissions
# /Production/Service-Name/Overview → THE dashboard
# /Production/Service-Name/Debug → detailed panels
# /Sandbox/ → auto-delete after 30 days
# /Deprecated/ → read-only, scheduled deletion
```

---

## Issue #88: Metric Name Collision Across Teams

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Two Teams Use Same Metric Name, Different Meaning             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: As organization grows                                      │
│                                                                         │
│  SCENARIO:                                                              │
│  Team A (Payments): requests_total = API requests received             │
│  Team B (Shipping): requests_total = shipping requests to carrier      │
│                                                                         │
│  Global dashboard: sum(requests_total)                                  │
│  → Combines payment API requests + carrier requests                   │
│  → Meaningless aggregate that nobody understands                       │
│                                                                         │
│  WORSE:                                                                 │
│  Team A: error_rate = errors / total_requests (ratio)                 │
│  Team C: error_rate = count_of_errors_per_second (absolute)           │
│  Alert: error_rate > 0.05 → fires for Team C at 5 errors/sec         │
│  (which is fine for them, but alert assumed it was a ratio)           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Metric naming convention (enforced)
# Pattern: <domain>_<subsystem>_<metric>_<unit>_<type>
# payment_api_requests_total (counter)
# payment_api_duration_seconds (histogram)
# shipping_carrier_requests_total (counter)
# shipping_delivery_duration_seconds (histogram)

# 2. Namespace enforcement at admission
# Prometheus relabel: prepend team namespace
metric_relabel_configs:
  - source_labels: [__name__, namespace]
    target_label: __name__
    regex: '(.*);(payment-service)'
    replacement: 'payment_${1}'

# 3. Metric registry (central catalog)
# Register metric name → definition → owner → consumers
# CI/CD: reject metric names that collide with existing ones
# Linting: check naming conventions before merge

# 4. OpenMetrics with UNIT and HELP metadata
# HELP payment_api_requests_total Total API requests received by payment service
# TYPE payment_api_requests_total counter
# UNIT payment_api_requests_total requests
```

---

## Issue #89: Observability Data Lake Query Performance Degradation

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Historical Metric Queries Slow as Data Grows                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Continuous degradation over months                         │
│                                                                         │
│  SCENARIO:                                                              │
│  Month 1: "Show me error rate for last 30 days" → 2 seconds           │
│  Month 6: Same query → 15 seconds                                     │
│  Month 12: Same query → 60+ seconds (timeout)                         │
│                                                                         │
│  WHY:                                                                   │
│  - Thanos Store Gateway scanning more blocks over time                │
│  - Block metadata growing (compactor can't merge everything)          │
│  - S3 listing API slower with more objects                            │
│  - Index not sized for current data volume                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Downsampling for historical data
# Thanos/Mimir: automatic downsampling
# Raw (5s resolution): keep 14 days
# 5-minute downsample: keep 90 days
# 1-hour downsample: keep 1 year
# 1-day downsample: keep forever

thanos:
  compactor:
    downsampling:
      enabled: true
    retention:
      raw: 14d
      5m: 90d
      1h: 365d

# 2. Block index caching
# Store Gateway: cache block index in memory
# Faster block selection without S3 listing
store_gateway:
  index_cache:
    type: memcached
    memcached:
      addresses: memcached:11211
      max_item_size: 128000000

# 3. Partition by time (daily/weekly blocks)
# Query for "last 7 days" only touches 7 blocks
# Not scanning entire history

# 4. Query frontend caching
# Cache 30-day query results
# Only recompute last 1 day (partial update)
```

---

## Issue #90: Service Discovery Overwhelm During Mass Deployment

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: 10,000 Pod Deployment Overwhelms Service Discovery            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: During major deployments / cluster migrations              │
│                                                                         │
│  SCENARIO:                                                              │
│  Large deployment: 10,000 pods restart simultaneously                  │
│  Kubernetes API server: flood of endpoint updates                      │
│  Prometheus service discovery: 10,000 target changes in 2 minutes     │
│  → SD refresh overwhelms Prometheus config reload                      │
│  → Stale targets scraped (old IPs) → connection errors                │
│  → New targets not discovered for 5+ minutes                          │
│  → Metric gap during largest deployment (most risky time!)            │
│                                                                         │
│  ALSO:                                                                  │
│  kube-apiserver overwhelmed by watch requests                         │
│  → All SD-dependent systems affected simultaneously                   │
│  → Monitoring, load balancers, mesh all disrupted                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Rolling deployments (never restart all at once)
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 10%       # Only 10% at a time
    maxUnavailable: 5%  # Max 5% down at once

# 2. Prometheus SD rate limiting
# kubernetes_sd_config with slower refresh during large events
kubernetes_sd_configs:
  - role: pod
    # Use informer (watch) instead of poll
    # Handles updates incrementally, not full list

# 3. Intermediary service registry (reduce API server load)
# kube-state-metrics as cache layer
# Prometheus reads from KSM (cached) not directly from API server
# KSM handles the watch storm, serves stable state

# 4. Stagger monitoring updates
# Don't refresh all Prometheus instances simultaneously
# Jitter: each instance refreshes at random offset within interval

# 5. Graceful scrape target transition
# Old pod: keep scraping until returns 404 (graceful shutdown)
# New pod: wait for readiness probe before first scrape
# Overlap window ensures no gap
```

---

## Summary: Scaling & Performance Issues

| # | Issue | Severity | Scale Threshold |
|---|-------|----------|----------------|
| 76 | Monitoring under-provisioned for incidents | P0 | Any scale during crisis |
| 77 | TSDB write amplification | P2 | >5M series |
| 78 | Dashboard load time > 30s | P2 | >100 panels, >1M series |
| 79 | K8s pod churn metric explosion | P1 | >500 pods/hour churn |
| 80 | Cross-region query latency | P2 | >3 regions |
| 81 | OTel Collector memory leak | P1 | >500K spans/min |
| 82 | Prometheus single-node ceiling | P1 | >15M series |
| 83 | Log storage > compute cost | P2 | >10TB logs/day |
| 84 | Agent CPU overhead on nodes | P2 | >3 agents per node |
| 85 | Alert rule evaluation backlog | P1 | >5000 rules |
| 86 | Kafka lag monitor lagging | P1 | >50K partitions |
| 87 | Dashboard sprawl | P2 | >1000 dashboards |
| 88 | Metric name collision | P2 | >50 teams |
| 89 | Historical query degradation | P2 | >1 year of data |
| 90 | SD overwhelm during deployment | P1 | >5000 pod changes |
