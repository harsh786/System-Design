# Production Issues #1-15: Metric Collection & TSDB Storage

## Context
At scale: 10M+ active time series, 500K+ scrape targets, 1M+ samples/sec ingestion rate.
Companies: Netflix, Uber, Cloudflare, Shopify, GitLab running Prometheus/Thanos/Mimir at scale.

---

## Issue #1: Cardinality Explosion from Unbounded Labels

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Cardinality Explosion                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: Weekly at scale                                             │
│  Companies hit: Almost every company scaling past 5M series             │
│                                                                         │
│  SCENARIO:                                                              │
│  Developer adds request_id or user_id as a Prometheus label            │
│  → 100M unique values → 100M time series created                       │
│  → Prometheus OOMs → All monitoring goes blind                         │
│                                                                         │
│  TIMELINE:                                                              │
│  T+0min: New deployment with bad label goes out                        │
│  T+2min: Prometheus ingestion rate spikes 100x                         │
│  T+5min: Prometheus head block fills memory                            │
│  T+8min: Prometheus OOM killed by Kubernetes                           │
│  T+8min: All alerts stop firing                                        │
│  T+8min: Dashboards show "No Data"                                     │
│  T+15min: On-call notices dashboards are empty                         │
│  T+30min: Root cause identified, rollback initiated                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Root Cause**: No guardrails on label cardinality. Labels like `user_id`, `request_id`, 
`trace_id`, `session_id`, `ip_address` create unbounded series.

**Detection**:
```promql
# Alert: Cardinality spike detection
rate(prometheus_tsdb_head_series_created_total[5m]) > 10000

# Track top cardinality offenders
topk(10, count by (__name__)({__name__=~".+"}))

# Per-metric cardinality
count by (__name__)({__name__=~"http_requests_total"})
```

**Resolution Pattern**:
```yaml
# 1. Metric relabeling to drop high-cardinality labels BEFORE ingestion
metric_relabel_configs:
  - source_labels: [user_id]
    action: labeldrop
  - source_labels: [__name__]
    regex: ".*_bucket"
    action: keep  # Only keep histograms you need

# 2. Admission control webhook
# Reject metrics with cardinality > threshold at write time
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: metric-cardinality-guard

# 3. Prom-label-proxy to enforce allowed labels
```

**Prevention**:
- Pre-commit hooks checking for unbounded labels
- Label allowlists in service mesh
- Cardinality quotas per team/namespace
- CI/CD pipeline that rejects high-cardinality metrics

---

## Issue #2: Prometheus TSDB Head Block Corruption

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: TSDB Head Block Corruption                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: Monthly under heavy write load                             │
│                                                                         │
│  SCENARIO:                                                              │
│  Pod killed during head block compaction                                │
│  → WAL corrupted → Prometheus can't restart                            │
│  → 2+ hours of metric gap                                              │
│                                                                         │
│  SYMPTOMS:                                                              │
│  - Prometheus pod in CrashLoopBackOff                                  │
│  - Logs: "opening storage failed: invalid magic number"               │
│  - WAL replay errors                                                    │
│  - Head block checksum mismatch                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Root Cause**: Ungraceful shutdown during compaction, disk full during WAL write, 
or kernel OOM killer hitting Prometheus during memory-intensive operations.

**Detection**:
```promql
# WAL corruption indicators
prometheus_tsdb_wal_corruptions_total > 0
prometheus_tsdb_head_truncations_failed_total > 0
rate(prometheus_tsdb_compactions_failed_total[1h]) > 0
```

**Resolution**:
```bash
# Option 1: Delete corrupted WAL segments
promtool tsdb clean /prometheus/wal

# Option 2: Snapshot and restore
promtool tsdb snapshot /prometheus /prometheus/snapshots/recovery

# Option 3: Nuclear option - delete data, let Thanos fill gaps
rm -rf /prometheus/wal /prometheus/chunks_head
# Prometheus restarts fresh, Thanos/remote-read fills historical queries
```

**Prevention**:
- Set `terminationGracePeriodSeconds: 600` (10 min for graceful shutdown)
- Memory limits at 80% of node capacity (avoid kernel OOM)
- EBS gp3 with provisioned IOPS for WAL directory
- Separate WAL disk from data disk
- Regular TSDB snapshots to S3

---

## Issue #3: Scrape Target Discovery Lag

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: New Services Invisible for 5-15 Minutes                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Every deployment at scale                                   │
│                                                                         │
│  SCENARIO:                                                              │
│  New pod deploys → Kubernetes service discovery → Prometheus config     │
│  reload → First scrape. At 10K+ services with 30s scrape interval,     │
│  new targets can be invisible for 5-15 minutes.                        │
│                                                                         │
│  IMPACT:                                                                │
│  - Canary deployments have no metrics for first 5 min                  │
│  - Auto-scaling decisions based on stale data                          │
│  - New service launches have monitoring blind spot                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Root Cause**: Service discovery sync interval + scrape interval + config reload time.
Kubernetes API server throttling during large cluster operations.

**Detection**:
```promql
# Track discovery lag
prometheus_sd_kubernetes_cache_last_resource_version
time() - prometheus_target_sync_length_seconds

# Count targets not yet scraped
prometheus_target_scrape_pools_total - prometheus_target_scrape_pool_targets
```

**Resolution**:
```yaml
# Reduce discovery refresh interval
kubernetes_sd_configs:
  - role: pod
    refresh_interval: 10s  # Default is 30s

# Use push-based registration
# New services push to a gateway that Prometheus already scrapes
# Or use remote-write from service itself on startup
```

---

## Issue #4: Remote Write Queue Backlog & Data Loss

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Remote Write Falling Behind                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: During traffic spikes                                       │
│                                                                         │
│  SCENARIO:                                                              │
│  Prometheus → remote_write → Thanos Receive / Cortex / Mimir           │
│  Backend slows down → queue fills up → WAL grows unbounded →           │
│  Disk fills → Prometheus OOM or samples dropped                        │
│                                                                         │
│  REAL-WORLD NUMBERS:                                                    │
│  Normal: 500K samples/sec remote write                                 │
│  Spike: 2M samples/sec (4x during incident)                           │
│  Queue capacity: 500MB → fills in 3 minutes                            │
│  Disk: WAL grows 1GB/min → fills 100GB disk in 100 min                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Detection**:
```promql
# Remote write lag
prometheus_remote_storage_highest_timestamp_in_seconds 
  - prometheus_remote_storage_queue_highest_sent_timestamp_seconds > 120

# Queue nearly full
prometheus_remote_storage_pending_samples > 90000

# Dropped samples
rate(prometheus_remote_storage_samples_dropped_total[5m]) > 0

# WAL size growing
prometheus_tsdb_wal_storage_size_bytes > 50e9
```

**Resolution**:
```yaml
remote_write:
  - url: https://thanos-receive:19291/api/v1/receive
    queue_config:
      capacity: 100000        # Increase buffer
      max_shards: 200         # More parallel writers
      min_shards: 10
      max_samples_per_send: 5000
      batch_send_deadline: 5s
    write_relabel_configs:
      # Drop non-essential metrics during backpressure
      - source_labels: [__name__]
        regex: "go_.*|process_.*"
        action: drop
```

---

## Issue #5: Stale Metrics After Pod Restarts (Staleness Handling)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Ghost Metrics from Dead Pods                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Continuous in dynamic environments                         │
│                                                                         │
│  SCENARIO:                                                              │
│  Pod-A dies → Pod-B starts with same service but different pod name    │
│  → Pod-A metrics still showing in dashboards for 5 min (staleness)    │
│  → Aggregation queries (sum by service) double-count during overlap   │
│  → Alerts fire on phantom metrics                                      │
│                                                                         │
│  EXAMPLE:                                                               │
│  sum(rate(http_requests_total{service="api"}[5m]))                    │
│  Shows 2x actual during rolling restart (old + new pods both counted) │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Root Cause**: Prometheus marks series stale after 5 minutes of no scrapes. During rolling 
restarts, old series coexist with new series causing double-counting.

**Detection**:
```promql
# Detect stale series
prometheus_target_scrapes_exceeded_sample_limit_total
up == 0  # Target disappeared but metrics still queryable

# Count active vs stale targets
count(up == 1) by (job) / count(up) by (job)
```

**Resolution**:
```yaml
# Use consistent labels that survive pod restarts
# BAD: pod="api-7f8c9d-x2k4a"  (changes every restart)
# GOOD: deployment="api", replica_set="api-7f8c9d"

# Reduce staleness period
--storage.tsdb.min-block-duration=1m

# Use recording rules that handle staleness
- record: service:http_requests:rate5m
  expr: sum without(pod, instance)(rate(http_requests_total[5m]))
```

---

## Issue #6: Histogram Bucket Explosion

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Histogram Metrics Creating 50x Series                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Design-time mistake, discovered at scale                   │
│                                                                         │
│  MATH:                                                                  │
│  1 histogram with default buckets = 11 le buckets + _sum + _count      │
│  = 13 series PER unique label combination                              │
│                                                                         │
│  http_request_duration_seconds{method, path, status}                   │
│  → 5 methods × 200 paths × 10 statuses = 10,000 combinations          │
│  → 10,000 × 13 = 130,000 time series FROM ONE METRIC                  │
│                                                                         │
│  At 1000 services: 130,000 × 1000 = 130 MILLION series                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Root Cause**: Histograms multiply cardinality by bucket count. Combined with 
high-cardinality labels (path, user-agent), this explodes series count.

**Detection**:
```promql
# Find histogram metrics with high cardinality
count by (__name__)({__name__=~".*_bucket"}) > 100000

# Bucket count per histogram
count by (__name__, le)({__name__=~".*_bucket"})
```

**Resolution**:
```python
# Use native histograms (Prometheus 2.40+) - exponential bucketing
# Reduces series count by 10-50x

# Or reduce buckets
from prometheus_client import Histogram

# BAD: default 11 buckets
request_latency = Histogram('http_request_duration_seconds', 'Request latency')

# GOOD: Custom buckets matching your SLO
request_latency = Histogram(
    'http_request_duration_seconds', 
    'Request latency',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]  # 8 buckets
)

# BETTER: Use summary for non-aggregatable percentiles
# Or group paths into categories
# /api/users/123 → /api/users/:id
```

---

## Issue #7: Clock Skew Causing Metric Gaps

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Samples Rejected Due to Clock Drift                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Common in multi-cloud / hybrid environments                │
│                                                                         │
│  SCENARIO:                                                              │
│  Node clock drifts 2+ minutes ahead of Prometheus server               │
│  → Prometheus receives samples "from the future"                       │
│  → Samples rejected with "out of order" or "too far in future"        │
│  → Metrics gap for affected nodes until clock syncs                    │
│                                                                         │
│  OR:                                                                    │
│  Node clock is behind → samples appear "old"                           │
│  → Prometheus rejects as "out of bounds"                               │
│  → Silent data loss                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Detection**:
```promql
# Detect clock skew across nodes
abs(node_timex_offset_seconds) > 1

# Track rejected samples
prometheus_target_scrapes_sample_out_of_order_total > 0
prometheus_target_scrapes_sample_duplicate_timestamp_total > 0
```

**Resolution**:
```bash
# Ensure NTP is running on all nodes
systemctl enable chronyd
chronyc tracking

# Kubernetes: Use node-level NTP validation as admission requirement
# Alert on clock drift before it causes issues
```

---

## Issue #8: Federation Query Timeout at Scale

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Global View Queries Timing Out                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Daily during business hours                                │
│                                                                         │
│  SCENARIO:                                                              │
│  Global Grafana dashboard queries Thanos Query across 20 clusters      │
│  → Fan-out to 20 store gateways + 20 sidecars                         │
│  → One slow cluster causes entire query to timeout at 30s             │
│  → Dashboard shows "504 Gateway Timeout"                               │
│  → Executives lose trust in monitoring platform                        │
│                                                                         │
│  SCALE:                                                                 │
│  - 20 clusters × 5M series each = 100M series                         │
│  - Query: sum(rate(requests_total[5m])) by (region)                   │
│  - Touches all 100M series, returns 20 results                        │
│  - Network: 2GB transferred for a single dashboard panel              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Recording rules to pre-aggregate at cluster level
groups:
  - name: cluster_aggregates
    interval: 30s
    rules:
      - record: cluster:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (cluster, service)

# 2. Thanos query frontend with caching
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thanos-query-frontend
spec:
  template:
    spec:
      containers:
        - name: query-frontend
          args:
            - --query-range.split-interval=12h
            - --query-range.max-retries-per-request=3
            - --cache.memcached.addresses=memcached:11211

# 3. Partial response mode (return available data, skip slow clusters)
# --query.partial-response in Thanos Query
```

---

## Issue #9: Metric Ingestion Rate Limiting Dropping Critical Metrics

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Rate Limits Drop Business-Critical Metrics                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: During incidents (when you need monitoring most)           │
│                                                                         │
│  SCENARIO:                                                              │
│  Incident causes metric explosion (error metrics spike 100x)          │
│  → Ingestion rate limit kicks in at backend                            │
│  → Rate limiter doesn't distinguish critical vs nice-to-have          │
│  → Payment success rate metric gets dropped                            │
│  → Can't see that payments are failing during the incident            │
│  → MONITORING FAILS EXACTLY WHEN YOU NEED IT MOST                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# Priority-based ingestion in Mimir/Cortex
# Critical metrics get guaranteed ingestion
overrides:
  critical_metrics:
    ingestion_rate: 1000000  # No limit for critical
    patterns:
      - "payment_.*"
      - "order_.*"
      - "sla_.*"
  
  default:
    ingestion_rate: 100000
    ingestion_burst_size: 200000

# Or: Separate Prometheus for critical vs non-critical
# Critical: dedicated Prometheus with reserved resources
# Non-critical: shared Prometheus with rate limits
```

---

## Issue #10: Thanos Compactor Halted - Overlapping Blocks

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Thanos Compactor Stops, Storage Grows Unbounded               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Monthly at scale                                           │
│                                                                         │
│  SCENARIO:                                                              │
│  Two Prometheus replicas (HA pair) upload blocks with overlapping      │
│  time ranges → Compactor detects overlap → Halts to prevent data      │
│  corruption → Old blocks never compacted → S3 storage grows           │
│  indefinitely → Query performance degrades → Storage costs spike      │
│                                                                         │
│  IMPACT:                                                                │
│  - S3 bill goes from $5K/month to $50K/month                          │
│  - Query latency increases 10x (scanning uncompacted blocks)          │
│  - Eventually queries time out                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Detection**:
```promql
thanos_compact_halted == 1
thanos_compact_group_compaction_failures_total > 0
thanos_objstore_bucket_operation_failures_total{operation="upload"} > 0
```

**Resolution**:
```bash
# Mark overlapping blocks for deletion
thanos tools bucket mark \
  --id=<block-id> \
  --marker=deletion-mark.json \
  --details="overlapping block from HA replica"

# Or use deduplication at query time
thanos query \
  --dedup.replica-label=replica \
  --dedup.replica-label=prometheus_replica

# Prevention: Use unique external labels per replica
# prometheus-0: external_labels: {replica: "0"}
# prometheus-1: external_labels: {replica: "1"}
```

---

## Issue #11: Hot Tenant Starving Shared Monitoring Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: One Team's Metrics Overwhelm Shared Platform                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Quarterly (new high-volume service onboarding)             │
│                                                                         │
│  SCENARIO:                                                              │
│  ML team deploys new model serving infrastructure                      │
│  → Emits 5M new time series (per-request embeddings metrics)          │
│  → Shared Mimir cluster at 80% capacity                               │
│  → Ingestion delays for ALL teams                                      │
│  → Other teams' alerts delayed by 3+ minutes                          │
│  → Multiple teams affected by one team's behavior                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# Tenant-based rate limiting in Mimir
overrides:
  ml_team:
    max_global_series_per_user: 2000000
    ingestion_rate: 200000
    ingestion_burst_size: 400000
  
  payments_team:  # Higher priority
    max_global_series_per_user: 5000000
    ingestion_rate: 500000
    
# Per-tenant resource isolation
# Separate ingester pools per priority tier
```

---

## Issue #12: Counter Reset Misinterpretation

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: rate() Produces Negative Values or Spikes After Restarts      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Every rolling restart (daily in CI/CD environments)        │
│                                                                         │
│  SCENARIO:                                                              │
│  Counter: http_requests_total = 1,000,000                              │
│  Pod restarts → counter resets to 0                                    │
│  Next scrape: http_requests_total = 50                                 │
│  rate() correctly handles reset, BUT:                                  │
│  - increase() over the restart window shows wrong value               │
│  - sum(increase(x[1d])) is inaccurate on restart-heavy days          │
│  - Billing/reporting based on counters shows discrepancies            │
│                                                                         │
│  WORSE CASE:                                                            │
│  Pod uses persistent counter across restarts (statefulset)             │
│  Sometimes counter file corrupts → reset to 0 → HUGE spike in rate() │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```promql
# Use rate() not increase() for counter-based alerts
# rate() handles resets correctly

# For billing/reporting, track via:
# 1. Recording rules that capture rate continuously
- record: service:requests:rate1m
  expr: sum(rate(http_requests_total[1m])) by (service)

# 2. For accurate totals, use event-based counting (Kafka/DB)
# not Prometheus counters

# 3. Use resets() to track restart frequency
resets(http_requests_total[1h]) > 5  # Too many restarts
```

---

## Issue #13: Service Mesh Sidecar Proxy Metrics Doubling

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Istio/Envoy + App Metrics = Double Counting                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Constant in service mesh environments                      │
│                                                                         │
│  SCENARIO:                                                              │
│  App reports: http_requests_total (from app code)                      │
│  Envoy reports: istio_requests_total (from sidecar)                    │
│  Both represent same requests but with different label sets            │
│  Dashboard using wrong metric → inaccurate by 2x                      │
│  OR: Teams build alerts on both → alert storms                        │
│                                                                         │
│  WORSE:                                                                 │
│  App metric: response_time includes processing                        │
│  Envoy metric: response_time includes app + serialization + network   │
│  Different numbers for "same thing" → confusion                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# Standardize: use mesh metrics as source of truth for traffic
# Use app metrics only for business-specific counters

# Drop app-level HTTP metrics when mesh is present
metric_relabel_configs:
  - source_labels: [__name__]
    regex: "http_(requests|response)_(total|duration).*"
    action: drop  # Use istio_* instead

# Document clearly which metric to use for what
# App metrics: business logic (orders_created, items_sold)
# Mesh metrics: traffic (requests, latency, error rate)
```

---

## Issue #14: Prometheus Memory Spike During Compaction

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: OOM During TSDB Compaction                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Every 2 hours (compaction cycle)                           │
│                                                                         │
│  SCENARIO:                                                              │
│  Prometheus at 10M series, 32GB RAM, runs fine                         │
│  Every 2h, compaction merges head block → persistent block            │
│  Memory spikes to 2x normal during compaction (64GB needed)           │
│  Kubernetes memory limit: 48GB → OOM Kill                             │
│  → Restart → WAL replay (30 min) → Another compaction → OOM loop     │
│                                                                         │
│  ROOT CAUSE:                                                            │
│  Compaction needs to hold both old + new block in memory              │
│  High series churn amplifies this (many series created/deleted)       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Set memory limits with compaction headroom (2.5x base usage)
resources:
  limits:
    memory: 80Gi  # For 32GB base usage
  requests:
    memory: 40Gi

# 2. Reduce head block size to reduce compaction memory
# --storage.tsdb.max-block-duration=1h (default 2h)

# 3. Use out-of-order ingestion to avoid in-memory sorting
# --storage.tsdb.out-of-order-time-window=5m

# 4. Consider vertical sharding (split by __name__)
# Or move to Mimir which handles compaction separately
```

---

## Issue #15: Metric Relabeling Breaking Existing Dashboards

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: "Optimization" Breaks 200 Dashboards                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Quarterly (during optimization sprints)                    │
│                                                                         │
│  SCENARIO:                                                              │
│  Platform team adds metric_relabel_configs to reduce cardinality       │
│  Drops label "instance" from all metrics (saves 2M series)            │
│  → 200 dashboards that filter by instance stop working                │
│  → 50 alert rules referencing instance label return no data           │
│  → Alerts stop firing → silent monitoring failure                     │
│  → Discovered 4 hours later when someone checks a dashboard           │
│                                                                         │
│  MAKES IT WORSE:                                                        │
│  No dependency tracking between relabel rules and dashboards          │
│  No testing of dashboard queries before config changes                │
│  No alerting on "alert rule returns no data"                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Dashboard dependency scanner
# Parse all Grafana dashboards, extract label references
# Compare against proposed relabel rules

import json
import re

def scan_dashboard_dependencies(dashboard_json):
    """Extract all label references from dashboard queries."""
    labels_used = set()
    panels = dashboard_json.get('panels', [])
    for panel in panels:
        for target in panel.get('targets', []):
            expr = target.get('expr', '')
            # Find all label matchers
            labels_used.update(re.findall(r'(\w+)=[~!]?"', expr))
    return labels_used

# 2. Alert on "alert rule evaluating to no data"
# ALERTS{alertstate="pending"} unless ALERTS{alertstate="firing"}
# If no results, the alert rule itself may be broken

# 3. CI/CD pipeline for relabel changes
# - Dry-run relabeling against sample data
# - Check all dashboards/alerts for affected labels
# - Require approval from affected teams
```

---

## Summary: Metric Collection & Storage Issues

| # | Issue | Severity | Detection Time | MTTR |
|---|-------|----------|---------------|------|
| 1 | Cardinality explosion | P0 | 2-5 min | 30 min |
| 2 | TSDB head corruption | P0 | Immediate | 2 hours |
| 3 | Scrape discovery lag | P1 | 5-15 min | 10 min |
| 4 | Remote write backlog | P1 | 2 min | 15 min |
| 5 | Stale metrics after restart | P2 | 5 min | N/A (design) |
| 6 | Histogram bucket explosion | P1 | Hours | Days |
| 7 | Clock skew metric gaps | P1 | 5 min | 30 min |
| 8 | Federation query timeout | P2 | Immediate | 1 hour |
| 9 | Rate limiting critical metrics | P0 | 2 min | 15 min |
| 10 | Compactor halted | P1 | 1 hour | 2 hours |
| 11 | Hot tenant starvation | P1 | 5 min | 1 hour |
| 12 | Counter reset misinterpretation | P2 | Variable | Design fix |
| 13 | Service mesh double counting | P2 | Variable | Design fix |
| 14 | Compaction OOM | P1 | Immediate | 30 min |
| 15 | Relabeling breaking dashboards | P1 | 4 hours | 1 hour |
