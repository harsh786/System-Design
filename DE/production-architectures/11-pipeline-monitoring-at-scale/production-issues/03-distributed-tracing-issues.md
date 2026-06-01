# Production Issues #31-45: Distributed Tracing Issues

## Context
At scale: 1B+ spans/day, 100K+ services, 10K+ unique operation types.
Companies: Uber (Jaeger), Google (Dapper), Netflix, Meta running distributed tracing.

---

## Issue #31: Trace Sampling Misses Critical Error Paths

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: 1% Sampling Rate Drops All Traces of Rare Error               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Every rare-but-critical error investigation                │
│                                                                         │
│  SCENARIO:                                                              │
│  Head-based sampling at 1% (keep 1 in 100 traces)                     │
│  Payment timeout occurs 0.01% of transactions (100/day)               │
│  Probability of capturing: 1% × 100 = ~1 trace/day                   │
│  Often 0 traces captured for the exact failure mode                   │
│  → Engineer: "Show me traces where payment timed out"                 │
│  → System: "No traces found"                                           │
│  → Can't debug production payment failures                            │
│                                                                         │
│  MATH OF SAMPLING:                                                      │
│  1B spans/day, 1% sampling = 10M spans stored                         │
│  Error rate 0.01% = 100K error spans/day                              │
│  After 1% sampling = 1,000 error spans stored                         │
│  Specific error type (5% of errors) = 50 spans                        │
│  Specific endpoint + error combination = 2-3 spans (maybe 0)          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Tail-based sampling (decide AFTER seeing full trace)
# OTel Collector with tail_sampling processor
processors:
  tail_sampling:
    decision_wait: 10s  # Wait for full trace before deciding
    policies:
      # Always keep errors
      - name: errors-policy
        type: status_code
        status_code: {status_codes: [ERROR]}
      
      # Always keep slow requests
      - name: latency-policy
        type: latency
        latency: {threshold_ms: 5000}
      
      # Keep specific critical paths
      - name: payment-policy
        type: string_attribute
        string_attribute:
          key: service.name
          values: [payment-service, billing-service]
      
      # Probabilistic for everything else
      - name: default
        type: probabilistic
        probabilistic: {sampling_percentage: 1}

# 2. Error-biased head sampling
# Sample 100% of errors, 1% of success
# Decision at root span creation time
class ErrorBiasedSampler(Sampler):
    def should_sample(self, context, trace_id, name, **kwargs):
        # Always sample if parent had error
        if has_error_in_context(context):
            return SamplingResult(Decision.RECORD_AND_SAMPLE)
        # Probabilistic otherwise
        return SamplingResult(
            Decision.RECORD_AND_SAMPLE if hash(trace_id) % 100 < 1 
            else Decision.DROP
        )
```

---

## Issue #32: Broken Trace Context Propagation Across Async Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Traces Break at Message Queues and Async Workers              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Constant in event-driven architectures                     │
│                                                                         │
│  SCENARIO:                                                              │
│  API → Kafka → Worker → DB                                             │
│  Trace context not propagated through Kafka message headers            │
│  → Two separate traces: API→Kafka and Worker→DB                       │
│  → Can't trace end-to-end request flow                                │
│  → 60% of traces are "orphaned" (no parent)                           │
│                                                                         │
│  BREAKS AT:                                                             │
│  - Kafka/RabbitMQ/SQS message boundaries                              │
│  - Cron jobs processing batched messages                               │
│  - Thread pool handoffs                                                 │
│  - gRPC streaming                                                       │
│  - Database CDC events                                                  │
│  - Lambda/serverless function invocations                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Inject trace context into Kafka headers
from opentelemetry import trace, context
from opentelemetry.propagate import inject, extract

# Producer: inject context into Kafka headers
def produce_message(topic, message):
    headers = {}
    inject(headers)  # Injects traceparent, tracestate
    producer.send(topic, value=message, headers=headers)

# Consumer: extract context from Kafka headers
def consume_message(message):
    ctx = extract(message.headers())
    with trace.get_tracer(__name__).start_as_current_span(
        "process_message",
        context=ctx,
        kind=trace.SpanKind.CONSUMER
    ) as span:
        process(message)

# 2. For batch consumers (multiple messages = one processing span)
# Create a LINK to each source trace instead of parent
def process_batch(messages):
    links = []
    for msg in messages:
        ctx = extract(msg.headers())
        span_ctx = trace.get_current_span(ctx).get_span_context()
        links.append(trace.Link(span_ctx))
    
    with tracer.start_as_current_span("batch_process", links=links):
        # Process all messages
        pass

# 3. For cron jobs / scheduled workers
# Store trace_id with the work item in the queue/database
# Restore context when processing
```

---

## Issue #33: Trace Storage Costs Exceeding Budget (10x Overrun)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Trace Storage Growing Faster Than Budget                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium - Cost)                                          │
│  Frequency: Continuous growth                                           │
│                                                                         │
│  COST CALCULATION:                                                      │
│  1B spans/day × 500 bytes average span size = 500GB/day                │
│  × 14 days retention = 7TB stored                                      │
│  S3 storage: $0.023/GB × 7000GB = $161/month                          │
│  But: indexing, querying, networking costs 10-50x storage              │
│  Actual cost: $5K-15K/month for traces alone                          │
│                                                                         │
│  At 10% sampling → $1.5K/month (acceptable)                           │
│  Problem: teams keep increasing sampling to "debug better"            │
│  No governance → sampling creeps from 1% to 10% to 50%               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Tiered retention
# Hot (Tempo/Jaeger): 3 days, full resolution
# Warm (S3 + Parquet): 14 days, queryable via Athena
# Cold (S3 Glacier): 90 days, for compliance only

# 2. Span size reduction
processors:
  attributes/reduce:
    actions:
      # Drop verbose attributes
      - key: http.request.body
        action: delete
      - key: db.statement
        action: hash  # Hash instead of store full SQL
      # Truncate long values
      - key: http.url
        action: truncate
        max_length: 200

# 3. Quotas per team
# Payment team: 100% sampling (critical)
# Marketing team: 1% sampling (non-critical)
# ML team: 5% sampling (moderate)

# 4. Automatic downsampling based on cost budget
# If daily cost > budget/30, reduce sampling automatically
```

---

## Issue #34: Trace ID Collision in High-Volume Systems

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Two Different Requests Share Same Trace ID                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Rare but impactful when it happens                         │
│                                                                         │
│  SCENARIO:                                                              │
│  At 1M requests/sec with 128-bit trace IDs:                           │
│  Birthday paradox: collision after ~2^64 IDs                           │
│  Normally safe, BUT:                                                    │
│  - Some frameworks use 64-bit IDs (collision after ~4B)               │
│  - Custom ID generators with weak randomness                          │
│  - Clock-based IDs during clock reset                                  │
│  - Container reuse with PID-based components                          │
│                                                                         │
│  IMPACT:                                                                │
│  Two unrelated traces merged in storage                                │
│  → Confusing spans from different services in one trace               │
│  → Debugging leads to wrong conclusion                                │
│  → Wrong service blamed for latency                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Always use W3C 128-bit trace IDs (16 bytes of randomness)
# Never use 64-bit or sequential IDs

# 2. Validate trace ID generation
import os
import struct

def generate_trace_id():
    """Generate cryptographically random 128-bit trace ID."""
    return os.urandom(16).hex()  # Uses /dev/urandom

# BAD: timestamp + counter (predictable, collision-prone)
# BAD: hash(request_data) (same request = same ID)
# GOOD: Random bytes from crypto-safe source

# 3. Detect collisions at storage level
# Jaeger/Tempo: check if incoming trace_id already exists
# with different root span → flag as potential collision

# 4. Use trace_id + service_name as composite key
# Even if IDs collide, spans are distinguishable
```

---

## Issue #35: Clock Skew Making Trace Visualization Incorrect

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Child Span Appears to Start Before Parent                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Common in multi-region / hybrid cloud                      │
│                                                                         │
│  SCENARIO:                                                              │
│  Service A (us-east-1): parent span starts at T=1000ms                │
│  Service B (eu-west-1): child span starts at T=995ms                  │
│  (B's clock is 5ms behind A's clock)                                   │
│                                                                         │
│  TRACE VISUALIZATION:                                                   │
│  Parent:  |=======|                                                    │
│  Child: |====|         ← appears to start BEFORE parent               │
│                                                                         │
│  → Engineers confused about causality                                  │
│  → "How can the DB query start before the API call?"                 │
│  → Root cause analysis misled by time ordering                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Clock skew adjustment in trace backend
# Jaeger performs server-side clock skew correction
# Uses parent-child relationship to detect and fix skew

# Jaeger adjustment algorithm:
# If child.start < parent.start:
#   skew = parent.start - child.start
#   adjust all spans from child's service by +skew

# 2. Use NTP with sub-millisecond accuracy
# chrony with multiple NTP sources
# Monitor: abs(clock_offset) < 1ms

# 3. Record both wall-clock and monotonic timestamps
# Wall clock: for display (subject to NTP adjustments)
# Monotonic: for duration calculation (never goes backward)

# 4. Client-side span timing (avoid network time)
# Measure duration on the service that owns the span
# Don't calculate duration from start/end across services
```

---

## Issue #36: Trace Fanout Query Overwhelming Backend (Dependency Query)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Service Dependency Graph Query Takes Down Trace Backend       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: When SRE team opens service map dashboard                  │
│                                                                         │
│  SCENARIO:                                                              │
│  Query: "Show all service dependencies in last 24 hours"              │
│  → Scans ALL spans from last 24h (1B spans)                           │
│  → Extracts unique (caller, callee) pairs                             │
│  → Backend CPU 100% for 10 minutes                                    │
│  → All other trace queries timeout during this period                 │
│  → SRE checking service map DURING incident kills trace search        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Pre-compute service graph using SpanMetrics processor
processors:
  spanmetrics:
    metrics_exporter: prometheus
    dimensions:
      - name: service.name
      - name: peer.service
    # Generates: traces_service_graph_request_total{client, server}
    # No need to scan all spans for dependency graph

# 2. Materialized service map (updated incrementally)
# Flink/Spark job processes spans in near-real-time
# Maintains edge list: (serviceA → serviceB, last_seen, request_count)
# Dashboard reads from materialized table, not raw spans

# 3. Query limits
tempo:
  query_frontend:
    max_duration: 1h  # Don't allow 24h queries
    max_bytes_per_tag_values_query: 5000000
  
  querier:
    max_concurrent_queries: 20
    search:
      max_duration: 1h
```

---

## Issue #37: Instrumentation Overhead Causing Latency in Hot Path

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Tracing Adds 5-15% Latency to Critical Path                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Discovered during performance testing                      │
│                                                                         │
│  SCENARIO:                                                              │
│  Payment processing: SLA = 50ms p99                                    │
│  With tracing enabled: 57ms p99 (14% overhead)                        │
│  Sources of overhead:                                                   │
│  - Span creation: 0.5ms (object allocation)                           │
│  - Context propagation: 1ms (header injection/extraction)             │
│  - Span export (sync): 5ms (network call to collector)                │
│  - Baggage propagation: 0.5ms (additional headers)                    │
│  Total: 7ms added to every request                                     │
│                                                                         │
│  AT SCALE:                                                              │
│  10 spans per request × 100K requests/sec                             │
│  = 1M span objects created per second                                  │
│  = Significant GC pressure in Java services                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Async span export (never block hot path)
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# BAD: SimpleSpanProcessor (sync export)
# GOOD: BatchSpanProcessor (async, batched)
provider.add_span_processor(
    BatchSpanProcessor(
        exporter,
        max_queue_size=10000,
        max_export_batch_size=512,
        schedule_delay_millis=5000,  # Batch for 5 seconds
    )
)

# 2. Reduce span count in hot loops
# BAD: Span per iteration
for item in items:
    with tracer.start_span("process_item"):  # 1000 spans!
        process(item)

# GOOD: Single span for batch
with tracer.start_span("process_batch") as span:
    span.set_attribute("batch.size", len(items))
    for item in items:
        process(item)

# 3. Conditional instrumentation
# Only create detailed spans when sampled
if span.is_recording():
    span.set_attribute("db.statement", query)  # Expensive to capture
```

---

## Issue #38: Missing Spans Creating Incomplete Traces

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: 30% of Traces Have Missing Intermediate Spans                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Constant (structural problem)                              │
│                                                                         │
│  SCENARIO:                                                              │
│  Expected trace: A → B → C → D → E                                   │
│  Actual trace: A → B → ? → D → E  (C missing)                        │
│                                                                         │
│  CAUSES:                                                                │
│  1. Service C not instrumented (legacy service)                        │
│  2. Span dropped by collector (rate limit / OOM)                      │
│  3. Span arrived after trace TTL (late span)                          │
│  4. Different sampling decisions at different services                 │
│  5. Network partition between C's collector and backend                │
│                                                                         │
│  IMPACT:                                                                │
│  - Trace visualization has gaps                                        │
│  - Latency attribution incorrect (C's time attributed to B)           │
│  - Service dependency graph incomplete                                 │
│  - Root cause analysis misses the actual culprit                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Monitor span completeness
# Expected spans per trace type vs actual
# Metric: trace_completeness_ratio = actual_spans / expected_spans

# 2. Consistent sampling decision (propagate sampling flag)
# If root decides to sample → ALL downstream services must sample
# W3C traceflags: sampled bit propagated in traceparent header
# traceparent: 00-<trace_id>-<span_id>-01  (01 = sampled)

# 3. OTel Collector with memory limiter (graceful degradation)
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 4000
    spike_limit_mib: 800
    # When memory high: reduce batch size, don't drop spans

# 4. Service mesh sidecar tracing (catch uninstrumented services)
# Istio/Envoy creates spans for ALL HTTP traffic automatically
# Even if application isn't instrumented, mesh captures the call
```

---

## Issue #39: Trace Backend Query Latency During Peak Hours

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Trace Queries Take 30+ Seconds During Business Hours          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Daily during peak (9 AM - 5 PM)                           │
│                                                                         │
│  SCENARIO:                                                              │
│  Tempo/Jaeger backend stores 500M spans                                │
│  Engineer searches: {service="api"} && {status=error} last 1h         │
│  → Full scan of 1 hour of data (20M spans)                            │
│  → 30 second query time                                                │
│  → During peak: 50 concurrent queries → all timeout                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Trace search indexes (Tempo with search enabled)
tempo:
  search_enabled: true
  storage:
    trace:
      search:
        chunk_size_bytes: 1000000
        # Creates bloom filter indexes for service, status, duration

# 2. Query frontend with result caching
query_frontend:
  search:
    concurrent_jobs: 2000
    target_bytes_per_job: 104857600
  cache:
    memcached:
      host: memcached:11211
      timeout: 500ms

# 3. Tag-based indexes for common queries
# Pre-index: service.name, http.status_code, error
# Makes filtered queries O(1) instead of full scan

# 4. TraceQL query optimization
# BAD: {} | select(status = error)  (scans everything)
# GOOD: {status = error && service.name = "api"}  (uses index)
```

---

## Issue #40: Span Explosion from Retry Logic

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Retries Create 10x Expected Span Volume                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: During partial outages (most dangerous time)               │
│                                                                         │
│  SCENARIO:                                                              │
│  Service A calls Service B (3 retries configured)                      │
│  Service B partially down (50% success rate)                           │
│  Average requests per successful call: 2.5 attempts                   │
│  Normal: 100K spans/min → During outage: 250K spans/min              │
│  Each retry: new HTTP span + new connection span                       │
│  Actual volume: 250K × 3 (levels) = 750K spans/min                   │
│                                                                         │
│  CASCADING:                                                             │
│  A retries → B overwhelmed → B retries to C → C overwhelmed           │
│  Span volume: 750K × 3 = 2.25M spans/min (22x normal)                │
│  Trace backend overwhelmed by retry spans                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Don't create new span per retry (use span events instead)
with tracer.start_span("call_service_b") as span:
    for attempt in range(max_retries):
        try:
            result = call_service_b()
            span.set_attribute("retry.count", attempt)
            break
        except Exception as e:
            span.add_event("retry", attributes={
                "attempt": attempt,
                "error": str(e)
            })
            if attempt == max_retries - 1:
                span.set_status(StatusCode.ERROR)
                raise

# 2. Aggregate retry spans at collector
# If 5 spans with same (parent_id, operation) in 10s → merge into 1
processors:
  groupbyattrs:
    keys:
      - parent_span_id
      - operation_name

# 3. Client-side span suppression during circuit-breaker open
# When circuit breaker is OPEN, don't create spans for rejected calls
```

---

## Issue #41: Trace Context Lost in Service Mesh mTLS Termination

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: mTLS Proxy Strips Trace Headers                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: After service mesh upgrade/misconfiguration                │
│                                                                         │
│  SCENARIO:                                                              │
│  App → Envoy sidecar → Network → Envoy sidecar → App                  │
│  Envoy configuration error: trace headers not in allowed_headers      │
│  → traceparent header dropped at mTLS termination point               │
│  → Every service-to-service call starts a NEW trace                   │
│  → Instead of 1 trace with 50 spans, get 50 traces with 1 span       │
│  → Service dependency graph completely disconnected                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Ensure trace headers in Envoy passthrough
# Istio: trace headers propagated by default
# Custom Envoy: explicit header configuration required
route_config:
  request_headers_to_add:
    - header:
        key: x-request-id
        value: "%REQ(X-REQUEST-ID)%"
  internal_redirect_policy:
    allow_cross_scheme_redirect: true
  # Ensure W3C trace context headers propagated
  request_headers_to_remove: []  # DON'T remove traceparent!

# 2. Monitor trace linkage
# Alert when orphan_span_ratio > threshold
- alert: TraceLinkageBroken
  expr: |
    sum(rate(traces_orphan_spans_total[5m])) 
    / sum(rate(traces_total_spans[5m])) > 0.1
  for: 5m
  annotations:
    summary: "10% of spans are orphans - trace context propagation broken"

# 3. Smoke test: synthetic traces across all services
# Canary request that verifies full trace captured end-to-end
```

---

## Issue #42: OTel Collector Pipeline Dropping Spans Under Load

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Collector Drops 20% of Spans During Traffic Spike             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: During peak traffic (daily)                                │
│                                                                         │
│  SCENARIO:                                                              │
│  OTel Collector: 8 CPU, 16GB RAM                                       │
│  Normal load: 500K spans/min (60% utilization)                         │
│  Peak load: 2M spans/min (240% utilization)                           │
│  → Collector queues fill → memory_limiter triggers                    │
│  → Spans dropped (refused at receiver) → 20% data loss               │
│                                                                         │
│  SILENT FAILURE:                                                        │
│  No client-side error (fire-and-forget UDP/gRPC)                      │
│  Drop only visible in collector's own metrics                         │
│  Teams don't know their traces are being lost                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Collector auto-scaling (HPA on custom metric)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: otel-collector-hpa
spec:
  scaleTargetRef:
    kind: Deployment
    name: otel-collector
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Pods
      pods:
        metric:
          name: otelcol_exporter_queue_size
        target:
          type: AverageValue
          averageValue: "5000"  # Scale when queue building up

# 2. Backpressure-aware pipeline
receivers:
  otlp:
    protocols:
      grpc:
        max_recv_msg_size_mib: 16
        max_concurrent_streams: 200

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 12000
    spike_limit_mib: 4000
  
  batch:
    send_batch_size: 10000
    timeout: 5s
    send_batch_max_size: 20000

# 3. Monitor collector health
- alert: OTelCollectorDroppingSpans
  expr: rate(otelcol_receiver_refused_spans_total[5m]) > 0
  for: 1m
  labels:
    severity: critical
```

---

## Issue #43: Trace-Metric-Log Correlation Broken

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Can't Jump from Metric Alert to Relevant Traces               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Every incident investigation                               │
│                                                                         │
│  SCENARIO:                                                              │
│  Alert fires: "p99 latency > 5s for payment-service"                  │
│  Engineer wants to see: which specific requests were slow?             │
│  → Grafana metric panel has no link to trace search                   │
│  → Engineer copies time range, goes to Jaeger, searches manually      │
│  → Finds 100 traces, no way to correlate with the metric spike       │
│  → Spends 30 min finding relevant traces                             │
│                                                                         │
│  SHOULD BE:                                                             │
│  Alert → click → see exemplar traces for the specific spike          │
│  Metric point → click → see the exact trace that caused it           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Exemplars: attach trace_id to metric samples
# Prometheus 2.26+ supports exemplars
from prometheus_client import Histogram
from opentelemetry import trace

request_duration = Histogram('http_request_duration_seconds', 'Request duration')

def handle_request():
    start = time.time()
    # ... process ...
    duration = time.time() - start
    
    # Attach current trace_id as exemplar
    span = trace.get_current_span()
    trace_id = span.get_span_context().trace_id
    request_duration.observe(duration, exemplar={'trace_id': format(trace_id, '032x')})

# 2. Grafana: Configure exemplar data source
datasources:
  - name: Prometheus
    jsonData:
      exemplarTraceIdDestinations:
        - name: trace_id
          datasourceUid: tempo
          urlDisplayLabel: "View Trace"

# 3. Logs: Include trace_id in every log line
# Enables: Log → click trace_id → see full trace
# And: Trace → see all logs for this trace_id
```

---

## Issue #44: Trace Data Used for Billing Disagrees with Actual

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Trace-based Request Counting Doesn't Match Revenue            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Monthly (billing reconciliation)                           │
│                                                                         │
│  SCENARIO:                                                              │
│  Platform charges API consumers per request (usage-based billing)     │
│  Billing system counts requests from trace data (root spans)          │
│  But: sampling means only 1% of traces captured                       │
│  Extrapolation: 100K root spans × 100 = estimated 10M requests       │
│  Actual (from access logs): 10.5M requests                            │
│  5% discrepancy = $50K billing error per month                        │
│                                                                         │
│  CAUSES OF DISCREPANCY:                                                │
│  - Sampling bias (errors oversampled → inflates error rate)           │
│  - Missing spans (head sampling rejects short requests)               │
│  - Clock skew attribution errors                                       │
│  - Trace deduplication aggressive                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# RULE: Never use sampled trace data for billing/counting
# Use dedicated counters (100% accurate) for billing

# 1. SpanMetrics connector (generates metrics FROM spans)
# But: still affected by sampling
# Only use if sampling rate is consistent and known

# 2. Separate billing counter (independent of tracing)
# This counter is NEVER sampled, ALWAYS incremented
billing_counter = Counter(
    'api_requests_billable_total',
    'Billable API requests',
    ['customer_id', 'endpoint', 'status_class']
)

def handle_request(customer_id, endpoint):
    # Always count, regardless of trace sampling decision
    billing_counter.labels(
        customer_id=customer_id,
        endpoint=endpoint,
        status_class="2xx"
    ).inc()

# 3. Reconcile monthly
# billing_counter total vs trace-estimated total
# Flag if discrepancy > 2%
```

---

## Issue #45: Distributed Trace Visualization Unusable (10,000+ Spans)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Trace UI Crashes on Large Traces                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: When debugging batch operations                            │
│                                                                         │
│  SCENARIO:                                                              │
│  Batch job processes 10,000 records                                    │
│  Each record: DB read + transform + DB write = 3 spans               │
│  Total: 30,000+ spans in one trace                                    │
│  → Jaeger UI takes 60 seconds to render                              │
│  → Browser tab crashes (2GB memory usage)                             │
│  → Engineer can't investigate the slow batch job                      │
│                                                                         │
│  ALSO:                                                                  │
│  Microservice architecture: single user request                        │
│  → API → Auth → 5 services → each calls 3 more → 200+ spans         │
│  → Trace waterfall is a wall of tiny bars                             │
│  → Information overload, not information                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Don't create per-item spans in batch operations
# Use span events or attributes instead
with tracer.start_span("batch_process") as span:
    span.set_attribute("batch.total_items", 10000)
    errors = []
    for i, item in enumerate(items):
        try:
            process(item)
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
    
    span.set_attribute("batch.errors", len(errors))
    span.set_attribute("batch.success", 10000 - len(errors))
    # ONE span instead of 30,000

# 2. Trace depth limiting
# Maximum span depth = 20 levels
# Maximum spans per trace = 1000
# Beyond that: aggregate into summary spans

# 3. UI-level aggregation
# Jaeger: --query.max-clock-skew-adjustment=0s
# Group repeated spans: "process_item" ×10,000 → shown as single group
# Collapse/expand UI for large traces

# 4. Separate trace for batch sub-operations
# Batch trace: 1 span with links to sub-traces
# Sub-trace per partition: manageable size (50 spans)
```

---

## Summary: Distributed Tracing Issues

| # | Issue | Severity | Key Takeaway |
|---|-------|----------|-------------|
| 31 | Sampling misses errors | P1 | Tail-based sampling for errors |
| 32 | Context lost at async boundaries | P1 | Inject into message headers |
| 33 | Storage cost explosion | P2 | Tiered retention + quotas |
| 34 | Trace ID collision | P2 | Always use 128-bit random IDs |
| 35 | Clock skew visualization | P2 | NTP + backend correction |
| 36 | Dependency query overwhelms backend | P1 | Pre-compute service graph |
| 37 | Instrumentation latency overhead | P1 | Async export + batch spans |
| 38 | Missing spans incomplete traces | P2 | Consistent sampling + mesh |
| 39 | Query timeout at peak | P2 | Search indexes + caching |
| 40 | Retry span explosion | P2 | Events instead of spans |
| 41 | mTLS strips trace headers | P1 | Verify header propagation |
| 42 | Collector drops under load | P1 | Auto-scale + backpressure |
| 43 | Metric-trace correlation broken | P2 | Exemplars + trace_id in logs |
| 44 | Trace-based billing inaccurate | P1 | Never bill from sampled data |
| 45 | Large trace UI crashes | P2 | Aggregate spans in batches |
