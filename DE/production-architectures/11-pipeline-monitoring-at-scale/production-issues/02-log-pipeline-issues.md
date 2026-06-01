# Production Issues #16-30: Log Pipeline Issues

## Context
At scale: 10-50 TB logs/day, 100K+ log sources, 5M+ log events/sec ingestion.
Companies: Uber (100TB/day), Netflix, Cloudflare, Stripe running centralized logging.

---

## Issue #16: Log Ingestion Backpressure Causing Application Slowdown

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Logging Pipeline Slows Down Application                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: During log storms (errors causing more errors)             │
│                                                                         │
│  SCENARIO:                                                              │
│  Application → Fluentd sidecar → Kafka → Elasticsearch                │
│  ES cluster saturated → Kafka consumer lag grows                       │
│  Fluentd buffer fills → TCP backpressure to application                │
│  Application log() calls block for 500ms                              │
│  → Application p99 latency spikes from 100ms to 600ms                 │
│  → THE MONITORING SYSTEM CAUSES THE OUTAGE                            │
│                                                                         │
│  IRONY:                                                                 │
│  Error causes error logs → more load on log pipeline →                 │
│  pipeline slows app → more errors → more logs → death spiral          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Root Cause**: Synchronous logging with TCP delivery guarantee. No circuit breaker 
between application and logging infrastructure.

**Detection**:
```promql
# Fluentd buffer growing
fluentd_output_status_buffer_total_bytes > 1e9

# Application latency correlated with log volume
correlation(app_latency_p99, log_ingestion_rate) > 0.8

# Kafka consumer lag on log topics
kafka_consumer_group_lag{topic="application-logs"} > 1000000
```

**Resolution**:
```yaml
# 1. Async logging with bounded buffer and DROP policy
# Application side (Java/logback):
<appender name="ASYNC" class="ch.qos.logback.classic.AsyncAppender">
  <queueSize>10000</queueSize>
  <discardingThreshold>80</discardingThreshold>  # Drop DEBUG/INFO at 80% full
  <neverBlock>true</neverBlock>  # NEVER block application thread
  <appender-ref ref="STDOUT"/>
</appender>

# 2. Fluent Bit with overflow action
[OUTPUT]
    Name              kafka
    Brokers           kafka:9092
    Topics            app-logs
    # Buffer settings
    queue_full_behavior  drop_oldest  # Don't block on full queue

# 3. Rate limiting at collector level
[FILTER]
    Name         throttle
    Rate         1000       # Max 1000 logs/sec per pod
    Window       5
    Print_Status true
```

---

## Issue #17: Log Loss During Rolling Deployments

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Logs Lost During Pod Shutdown                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Every deployment (multiple times daily)                    │
│                                                                         │
│  SCENARIO:                                                              │
│  Rolling restart → Pod receives SIGTERM                                │
│  → Application has 10 seconds (terminationGracePeriod)                │
│  → Fluentd sidecar killed simultaneously                              │
│  → Last ~5 seconds of logs in Fluentd buffer LOST                     │
│  → Exactly the logs you need for debugging (shutdown errors)          │
│                                                                         │
│  SCALE IMPACT:                                                          │
│  100 deployments/day × 500 pods × 5 seconds = 250,000 seconds         │
│  of logs lost per day across the organization                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. preStop hook to flush logs before shutdown
lifecycle:
  preStop:
    exec:
      command:
        - /bin/sh
        - -c
        - |
          # Signal fluentd to flush
          kill -USR1 $(cat /var/run/fluentd.pid)
          # Wait for flush to complete
          sleep 10

# 2. terminationGracePeriodSeconds must be larger than flush time
terminationGracePeriodSeconds: 60

# 3. Fluent Bit persistent buffer on emptyDir with memory-backed
[SERVICE]
    storage.path         /var/log/flb-storage/
    storage.sync         normal
    storage.checksum     off
    storage.backlog.mem_limit 50M

# 4. Use DaemonSet collector (not sidecar) reading from hostPath
# Logs persist on node even after pod dies
```

---

## Issue #18: Elasticsearch Cluster Red Status from Log Spike

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Log Spike Takes Down Elasticsearch                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: During incidents (2-3x per month)                          │
│                                                                         │
│  SCENARIO:                                                              │
│  Application throws exception in hot loop                              │
│  → 100K error logs/sec instead of normal 1K/sec                       │
│  → Elasticsearch indexing queue full → rejections                      │
│  → Bulk indexing failures → retries compound load                     │
│  → JVM heap pressure → GC storms                                      │
│  → Cluster goes RED (primary shards unassigned)                       │
│  → ALL log search broken for ALL teams                                │
│                                                                         │
│  CASCADING FAILURES:                                                    │
│  Incident → debug with logs → logs unavailable                         │
│  → Blind debugging → longer MTTR                                      │
│  → More customer impact → more errors → more logs                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Detection**:
```promql
# ES cluster health
elasticsearch_cluster_health_status{color="red"} == 1

# Indexing pressure
elasticsearch_indexing_index_total_rate > 500000
elasticsearch_thread_pool_rejected_count{name="write"} > 0

# JVM heap
elasticsearch_jvm_memory_used_bytes / elasticsearch_jvm_memory_max_bytes > 0.85
```

**Resolution**:
```yaml
# 1. Index-level rate limiting with ILM
PUT _cluster/settings
{
  "persistent": {
    "cluster.routing.allocation.total_shards_per_node": 1000,
    "indices.memory.index_buffer_size": "30%"
  }
}

# 2. Circuit breaker at ingestion layer
# Vector/Fluent Bit rate limiting per source
[transforms.rate_limit]
  type = "throttle"
  inputs = ["source_app_logs"]
  threshold = 10000  # Max 10K events/sec per app
  window_secs = 1

# 3. Dedicated hot-tier for recent logs, cold-tier for archive
# 4. Index per team with resource quotas
# 5. Automatic index rollover at size/time threshold
```

---

## Issue #19: Log Parsing Failures Causing Data Loss

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Unstructured Logs Fail Parsing → Dropped                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: After any application logging format change                │
│                                                                         │
│  SCENARIO:                                                              │
│  Team changes log format from JSON to key=value                        │
│  → Log pipeline JSON parser fails → events routed to dead letter      │
│  → 30% of logs for that service silently lost                         │
│  → Discovered 3 days later when debugging an issue                    │
│                                                                         │
│  VARIANTS:                                                              │
│  - Multi-line log (stack traces) split across records                 │
│  - Encoding changes (UTF-8 to Latin-1)                                │
│  - Timestamp format change (ISO → epoch)                              │
│  - New fields exceeding index mapping limit                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Detection**:
```promql
# Parse error rate
rate(fluentd_output_status_retry_count[5m]) > 0
vector_component_errors_total{component_type="transform"} > 0

# Dead letter queue growth
kafka_topic_partition_current_offset{topic="logs-dlq"} - 
  kafka_topic_partition_committed_offset{topic="logs-dlq"} > 10000

# Log volume drop per service (abnormal)
rate(log_events_total{service="payment-api"}[5m]) 
  < 0.5 * avg_over_time(rate(log_events_total{service="payment-api"}[5m])[1d:5m])
```

**Resolution**:
```yaml
# 1. Schema-on-read approach (store raw, parse at query time)
# Use Loki (stores unstructured) instead of ES (requires mapping)

# 2. Fallback parser chain
[PARSER]
    Name        json_primary
    Format      json
    Time_Key    timestamp

[PARSER]
    Name        kv_fallback
    Format      logfmt

[PARSER]
    Name        raw_fallback
    Format      regex
    Regex       ^(?<message>.*)$

# 3. Dead letter queue with replay capability
# Failed logs → DLQ topic → manual review → fix parser → replay
```

---

## Issue #20: Loki Query Timeout on High-Cardinality Labels

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: LogQL Queries Take 60+ Seconds or Timeout                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Daily during incident investigation                        │
│                                                                         │
│  SCENARIO:                                                              │
│  Engineer investigating incident runs:                                  │
│  {app="api"} |= "error" | json | user_id != ""                       │
│  → Loki scans 50TB of chunks for last 24h                             │
│  → Query timeout after 120 seconds                                     │
│  → Engineer can't find relevant logs during active incident            │
│                                                                         │
│  ROOT CAUSE:                                                            │
│  - Too many streams (high cardinality labels = many small chunks)     │
│  - No bloom filter indexes for content search                         │
│  - Query covers too wide a time range                                  │
│  - Insufficient querier resources                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Limit label cardinality in Loki config
limits_config:
  max_label_name_length: 1024
  max_label_value_length: 2048
  max_label_names_per_series: 30
  max_streams_per_user: 10000

# 2. Use structured metadata (Loki 3.0) instead of labels
# Labels: {app="api", env="prod"}  (indexed, low cardinality)
# Structured metadata: user_id, request_id  (not indexed, queryable)

# 3. Query splitting and caching
query_range:
  split_queries_by_interval: 15m
  cache_results: true
  results_cache:
    cache:
      memcached:
        addresses: memcached:11211

# 4. Bloom filters for content-based queries (Loki 3.0+)
bloom_gateway:
  enabled: true
```

---

## Issue #21: Log Timestamp Mismatch Causing Out-of-Order Ingestion

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Logs Appearing in Wrong Time Window                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Constant in multi-timezone/multi-region setups             │
│                                                                         │
│  SCENARIO:                                                              │
│  Service A: logs timestamp in UTC                                      │
│  Service B: logs timestamp in local time (PST = UTC-8)                │
│  Service C: logs timestamp as epoch milliseconds                      │
│  Service D: no timestamp (uses ingestion time)                        │
│                                                                         │
│  → Searching "last 1 hour" misses Service B logs (8 hours in future) │
│  → Log correlation across services impossible                         │
│  → Out-of-order rejection in Loki/ES                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Normalize timestamps at collection layer
[FILTER]
    Name         lua
    Script       normalize_timestamp.lua
    Call         normalize_ts
    # Convert any format to RFC3339 UTC

# 2. Loki: increase out-of-order window
limits_config:
  unordered_writes: true
  max_chunk_age: 2h

# 3. Elasticsearch: index.mapping.timestamp.format accept multiple
PUT _template/logs
{
  "mappings": {
    "properties": {
      "@timestamp": {
        "type": "date",
        "format": "strict_date_optional_time||epoch_millis||yyyy-MM-dd HH:mm:ss"
      }
    }
  }
}

# 4. Organizational: mandate UTC + ISO8601 in all services
# Enforce via linting rules on logging libraries
```

---

## Issue #22: Multi-line Log Aggregation Breaking (Stack Traces)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Stack Traces Split Across Multiple Log Entries                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Constant for Java/Python applications                      │
│                                                                         │
│  SCENARIO:                                                              │
│  Java exception:                                                        │
│  2024-01-15 ERROR PaymentService - Transaction failed                  │
│  java.lang.NullPointerException                                         │
│      at com.payments.PaymentService.process(PaymentService.java:42)    │
│      at com.payments.Handler.handle(Handler.java:15)                   │
│                                                                         │
│  Collector treats each line as separate log entry                      │
│  → Stack trace fragments useless for debugging                        │
│  → "at" lines have no timestamp → rejected as malformed              │
│  → Search for "NullPointerException" finds line without context       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Fluent Bit multiline parser
[MULTILINE_PARSER]
    name          java_multiline
    type          regex
    flush_timeout 1000
    # First line starts with timestamp
    rule "start_state" "/^\d{4}-\d{2}-\d{2}/" "cont"
    # Continuation lines start with whitespace or "at" or "Caused by"
    rule "cont"        "/^(\s+at|\s+\.{3}|Caused by|\s+\.\.\.)/" "cont"

[INPUT]
    Name              tail
    Path              /var/log/app/*.log
    multiline.parser  java_multiline

# 2. BETTER: Use structured logging (JSON per line)
# Each log entry = one JSON line, stack trace as field
{"timestamp":"2024-01-15T10:00:00Z","level":"ERROR",
 "message":"Transaction failed",
 "exception":"java.lang.NullPointerException\n\tat com.payments..."}
```

---

## Issue #23: PII Leaking into Centralized Logs

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Sensitive Data in Log Storage (GDPR/PCI Violation)            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical - Compliance)                                  │
│  Frequency: Constant (discovered during audits)                        │
│                                                                         │
│  SCENARIO:                                                              │
│  Developer debug logs: "Processing payment for card=4111111111111111   │
│  user_email=john@example.com SSN=123-45-6789"                         │
│  → Stored in Elasticsearch accessible to 500 engineers                 │
│  → Retained for 90 days (beyond GDPR requirements)                    │
│  → PCI audit discovers card numbers in logs                           │
│  → $10M+ fine risk                                                     │
│                                                                         │
│  SCALE:                                                                 │
│  10TB logs/day × 0.1% contain PII = 10GB of PII stored daily         │
│  90 days retention = 900GB of PII-containing logs                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Real-time PII scrubbing at collection layer
[FILTER]
    Name    lua
    Script  scrub_pii.lua
    Call    scrub

# scrub_pii.lua
function scrub(tag, timestamp, record)
    local msg = record["message"] or ""
    -- Credit card (Luhn-validated)
    msg = msg:gsub("%d%d%d%d[%s%-]?%d%d%d%d[%s%-]?%d%d%d%d[%s%-]?%d%d%d%d", "REDACTED_CC")
    -- Email
    msg = msg:gsub("[%w%.]+@[%w%.]+%.[%a]+", "REDACTED_EMAIL")
    -- SSN
    msg = msg:gsub("%d%d%d[%-]?%d%d[%-]?%d%d%d%d", "REDACTED_SSN")
    record["message"] = msg
    return 2, timestamp, record  -- 2 = modified record
end

# 2. Vector transform for PII detection
[transforms.redact_pii]
  type = "remap"
  inputs = ["raw_logs"]
  source = '''
    .message = redact(.message, filters: [
      r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
      r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
      r'\b\d{3}-\d{2}-\d{4}\b'
    ])
  '''

# 3. Organizational controls
# - Log review in CI/CD (scan for PII patterns in log statements)
# - Structured logging with explicit allow-list of fields
# - Field-level encryption for sensitive logs
# - Separate PII-containing logs with stricter access control
```

---

## Issue #24: Log Volume Cost Explosion (10x Overnight)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Logging Costs Spike from $50K to $500K/month                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High - Cost)                                            │
│  Frequency: Quarterly (after major launches)                           │
│                                                                         │
│  SCENARIO:                                                              │
│  New service launches with DEBUG logging in production                 │
│  → 10x log volume increase (5TB → 50TB/day)                          │
│  → Elasticsearch cluster needs 10x more nodes                         │
│  → Or: DataDog bill goes from $50K to $500K/month                     │
│  → CFO asks "why did observability cost 10x?"                         │
│                                                                         │
│  COST MATH (DataDog pricing example):                                  │
│  $0.10/GB ingestion + $1.70/million events for indexing               │
│  50TB/day = 50,000 GB × $0.10 = $5,000/day = $150K/month             │
│  + event indexing: 50B events × $1.70/M = $85,000/day                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Log level governance
# Production: WARN + ERROR only (by default)
# Sampled DEBUG: 1% sampling for debug logs
# Dynamic: increase to DEBUG during active incident

# 2. Tiered logging strategy
# Hot (7 days): Full text search, all logs - Elasticsearch/Loki
# Warm (30 days): Sampled logs, ERROR only - S3 + Athena
# Cold (1 year): Compressed archive - S3 Glacier

# 3. Per-team cost attribution
# Tag every log with team/service → chargeback
# Teams pay for their own logging → incentive to reduce

# 4. Smart sampling at collector
[transforms.sample_verbose]
  type = "sample"
  inputs = ["app_logs"]
  rate = 10  # Keep 1 in 10 for DEBUG level
  key_field = "level"
  exclude.level.equals = ["ERROR", "WARN"]  # Keep all errors
```

---

## Issue #25: Cross-Service Log Correlation Failure

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Can't Trace Request Across Services in Logs                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Every incident investigation                               │
│                                                                         │
│  SCENARIO:                                                              │
│  Request flows: API Gateway → Auth → Orders → Payments → Notify       │
│  User reports failed order                                              │
│  → Search logs for user_id across 5 services                          │
│  → Each service uses different correlation ID field name:              │
│     API: x-request-id                                                   │
│     Auth: correlation_id                                                │
│     Orders: trace_id                                                    │
│     Payments: transaction_id                                            │
│     Notify: msg_id                                                      │
│  → Manual joining across services takes 45+ minutes                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Standardize on W3C Trace Context propagation
# All services must log: trace_id, span_id from OpenTelemetry context
# Logger MDC integration:
logging:
  pattern: "%d{ISO8601} [%X{trace_id}] [%X{span_id}] %-5level %logger - %msg%n"

# 2. Automatic trace_id injection via service mesh
# Istio/Envoy propagates trace headers automatically
# Application logging framework reads from context

# 3. Grafana: Logs → Traces correlation
# Configure derived fields in Loki data source
datasources:
  - name: Loki
    jsonData:
      derivedFields:
        - name: TraceID
          matcherRegex: "trace_id=(\\w+)"
          url: "$${__value.raw}"
          datasourceUid: tempo

# 4. Index trace_id as label in Loki
# Enables: {trace_id="abc123"} to find all logs for a request
```

---

## Issue #26: Log Pipeline Single Point of Failure (Kafka Broker Down)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Kafka Broker Failure Causes Log Loss                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: Quarterly (hardware failures)                              │
│                                                                         │
│  SCENARIO:                                                              │
│  Kafka cluster: 5 brokers, replication factor 2                        │
│  2 brokers fail simultaneously (rack power failure)                    │
│  → Some partitions have no leader (under-replicated)                  │
│  → Log producers get timeout errors                                    │
│  → Fluent Bit/Vector drops logs (buffer overflow)                     │
│  → 30 minutes of logs lost across all services                        │
│  → The 30 minutes you most need (during the outage)                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Replication factor 3 with min.insync.replicas=2
kafka:
  topics:
    logs:
      replication_factor: 3
      min.insync.replicas: 2
      # Can survive 1 broker failure without data loss

# 2. Multi-path logging (primary + fallback)
# Vector configuration:
[sinks.primary]
  type = "kafka"
  topic = "logs"
  bootstrap_servers = "kafka-primary:9092"
  healthcheck.enabled = true

[sinks.fallback]
  type = "file"
  path = "/var/log/buffer/{{ source }}.log"
  # Write to local disk if Kafka unavailable
  # Replay when Kafka recovers

# 3. Collector-level disk buffering
[SERVICE]
    storage.path        /var/log/flb-buffer/
    storage.sync        normal
    storage.backlog.mem_limit 100M
    # Buffer up to 10GB on disk during outages
```

---

## Issue #27: Elasticsearch Index Mapping Explosion

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Too Many Fields → Index Fails                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Monthly (new services with nested JSON logs)               │
│                                                                         │
│  SCENARIO:                                                              │
│  Service logs request/response bodies as nested JSON                   │
│  → Dynamic mapping creates field for every JSON key                   │
│  → API responses have 500+ unique keys across requests                │
│  → Index hits 1000 field limit → new documents rejected               │
│  → "mapper_parsing_exception: Limit of total fields exceeded"        │
│                                                                         │
│  WORSE:                                                                 │
│  Each field = memory for inverted index                               │
│  10,000 fields × 1000 shards = significant heap usage                 │
│  Field data circuit breaker trips → search failures                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```json
// 1. Strict mapping with explicit field definitions
PUT _template/app-logs
{
  "index_patterns": ["app-logs-*"],
  "mappings": {
    "dynamic": "strict",  // Reject unknown fields
    "properties": {
      "@timestamp": {"type": "date"},
      "level": {"type": "keyword"},
      "service": {"type": "keyword"},
      "message": {"type": "text"},
      "trace_id": {"type": "keyword"},
      "metadata": {"type": "flattened"}  // Catch-all for dynamic fields
    }
  }
}

// 2. Use "flattened" type for dynamic content
// Allows searching but doesn't create per-field mappings

// 3. Flatten nested objects at ingestion
// Before: {"response": {"body": {"user": {"name": "John"}}}}
// After: {"response_body": "{\"user\":{\"name\":\"John\"}}"}  // Store as string
```

---

## Issue #28: Log Retention Policy Accidentally Deleting Compliance Logs

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: ILM Deletes Logs Needed for Audit                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical - Compliance)                                  │
│  Frequency: Discovered during audits (annually)                        │
│                                                                         │
│  SCENARIO:                                                              │
│  ILM policy: delete indices older than 30 days                        │
│  Regulatory requirement: retain financial logs for 7 years            │
│  All logs in same index pattern → ALL deleted at 30 days             │
│  Auditor requests 6-month-old transaction logs → NOT FOUND            │
│  → Regulatory violation → investigation → potential fines             │
│                                                                         │
│  ROOT CAUSE:                                                            │
│  No separation between operational logs (short retention) and         │
│  compliance logs (long retention). Same ILM policy for all.           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Separate log streams by retention requirement
# compliance-logs → 7 year retention (S3 Glacier)
# security-logs → 1 year retention (warm tier)
# operational-logs → 30 day retention (hot tier)
# debug-logs → 7 day retention (delete aggressively)

# 2. Route at collector level
[transforms.route_by_retention]
  type = "route"
  inputs = ["all_logs"]
  route.compliance = '.tags == "audit" || .tags == "financial"'
  route.security = '.tags == "security" || .tags == "access"'
  route._unmatched = "operational"

# 3. Different ILM policies per stream
PUT _ilm/policy/compliance-policy
{
  "policy": {
    "phases": {
      "hot": {"actions": {"rollover": {"max_size": "50GB"}}},
      "warm": {"min_age": "30d", "actions": {"shrink": {"number_of_shards": 1}}},
      "cold": {"min_age": "90d", "actions": {"freeze": {}}},
      "delete": {"min_age": "2555d"}  // 7 years
    }
  }
}
```

---

## Issue #29: Log Search Unusable During Incidents (When You Need It Most)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Log Search Slow/Broken During High-Error Periods              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: Every major incident                                       │
│                                                                         │
│  SCENARIO:                                                              │
│  Production incident → engineers flood log search UI                   │
│  → 50 engineers all running expensive queries simultaneously          │
│  → Query queue saturated → 60+ second query times                     │
│  → Meanwhile, indexing backed up → recent logs unavailable            │
│  → Engineers can't debug → incident duration extends                  │
│                                                                         │
│  PARADOX:                                                               │
│  Incidents generate 10-100x normal log volume                         │
│  Incidents also generate 10-50x normal query volume                   │
│  System designed for normal load fails at exactly the wrong time      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Separate read and write paths
# Dedicated query nodes (not shared with indexing)
elasticsearch:
  roles:
    ingest_nodes: 10  # Only handle writes
    query_nodes: 5    # Only handle searches
    data_nodes: 20    # Storage only

# 2. Query priority queuing
# Incident responders get priority queue access
# Casual browsing deprioritized during incidents

# 3. Pre-built incident queries (saved searches)
# Don't let engineers write ad-hoc during incidents
# Have pre-optimized queries for common scenarios

# 4. Emergency log tailing (bypass search)
# Direct Kafka consumer for real-time tail
# Doesn't depend on indexing pipeline
kafka-console-consumer --topic app-logs \
  --bootstrap-server kafka:9092 \
  --property print.key=true \
  | grep "ERROR"

# 5. Burst capacity (auto-scale query nodes)
# Scale query nodes 3x during incidents automatically
```

---

## Issue #30: Log Deduplication Failure After Collector Restart

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Duplicate Logs After Collector Pod Restart                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Every collector restart (daily)                            │
│                                                                         │
│  SCENARIO:                                                              │
│  Fluent Bit tails /var/log/app.log, tracks position in offset file    │
│  Pod restarts → offset file lost (emptyDir) → re-reads entire file   │
│  → Millions of duplicate log entries sent                              │
│  → Elasticsearch double-counts errors in dashboards                   │
│  → Alert: "Error rate doubled!" (false positive)                      │
│  → On-call paged unnecessarily at 3 AM                               │
│                                                                         │
│  SCALE:                                                                 │
│  1000 collector pods × daily restart × 1GB buffer each                │
│  = 1TB of duplicate logs ingested daily                                │
│  = $3,000/day wasted on storage + indexing                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Persistent offset tracking (PVC or hostPath)
volumes:
  - name: flb-storage
    hostPath:
      path: /var/log/flb-positions  # Survives pod restart
      type: DirectoryOrCreate

# 2. Deduplication at sink level
# Elasticsearch: Use document ID based on content hash
[OUTPUT]
    Name  es
    Id_Key _hash  # Use computed hash as document ID
    # Duplicate documents with same ID are rejected (no-op)

# 3. Content-hash based dedup in Vector
[transforms.dedup]
  type = "dedupe"
  inputs = ["raw_logs"]
  fields.match = ["message", "timestamp", "source"]
  cache.num_events = 1000000

# 4. Kafka exactly-once with idempotent producer
# Producer uses sequence numbers → broker deduplicates
```

---

## Summary: Log Pipeline Issues

| # | Issue | Severity | Root Cause | Key Learning |
|---|-------|----------|-----------|--------------|
| 16 | Backpressure app slowdown | P0 | Sync logging + no circuit breaker | Never block on log write |
| 17 | Log loss during deploy | P1 | Sidecar killed with pod | preStop hooks + flush |
| 18 | ES red from log spike | P0 | No ingestion rate limiting | Rate limit at collector |
| 19 | Parse failure data loss | P1 | Format change no coordination | Schema-on-read + DLQ |
| 20 | Loki query timeout | P2 | High cardinality + wide range | Structured metadata |
| 21 | Timestamp mismatch | P2 | No timestamp standard | Mandate UTC + ISO8601 |
| 22 | Multi-line breakage | P2 | Line-by-line processing | Structured JSON logging |
| 23 | PII in logs | P0 | No scrubbing pipeline | Real-time PII redaction |
| 24 | Cost explosion | P1 | DEBUG in prod + no governance | Tiered + sampled logging |
| 25 | Cross-service correlation | P2 | No standard correlation ID | W3C Trace Context |
| 26 | Kafka SPOF log loss | P0 | Low replication + no fallback | RF=3 + disk buffer |
| 27 | ES mapping explosion | P1 | Dynamic mapping + nested JSON | Strict mapping + flattened |
| 28 | Compliance logs deleted | P0 | One retention policy for all | Separate streams by retention |
| 29 | Search broken during incidents | P0 | Shared read/write nodes | Separate paths + priority |
| 30 | Duplicate logs after restart | P2 | Lost offset file | Persistent offsets + dedup |
