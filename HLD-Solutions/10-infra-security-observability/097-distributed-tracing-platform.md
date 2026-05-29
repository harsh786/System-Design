# Distributed Tracing Platform (like Jaeger/Zipkin)

## 1. Requirements

### Functional Requirements
- Trace/span collection via OpenTelemetry SDK integration
- Sampling strategies: head-based, tail-based, adaptive
- Trace storage with efficient retrieval by trace ID, service, operation
- Trace search by attributes, duration, status, time range
- Trace visualization (waterfall view, flame graph)
- Service dependency map (auto-generated from trace data)
- Latency analysis with critical path identification
- Trace-based alerting (error rate, latency percentiles)
- Correlation with logs and metrics via trace context
- Multi-tenancy with data isolation

### Non-Functional Requirements
- Ingest 1M+ spans/second
- Trace retrieval by ID < 100ms
- Search queries < 3 seconds
- 14-day retention for full traces, 90-day for aggregated data
- 99.9% availability for ingestion pipeline
- < 1% data loss under normal operation
- Support 10,000+ services across the platform

## 2. Core Entities

```
Trace: trace_id (128-bit), root_span_id, service_count, span_count, duration_ms, status
Span: span_id, trace_id, parent_span_id, operation_name, service_name, 
      start_time_us, duration_us, status_code, kind (CLIENT/SERVER/PRODUCER/CONSUMER/INTERNAL)
SpanAttributes: span_id, key, value, type (string/int/float/bool/array)
SpanEvent: span_id, name, timestamp_us, attributes[]
SpanLink: span_id, linked_trace_id, linked_span_id, attributes[]
Resource: service_name, service_version, host, container_id, k8s_pod, attributes[]
ServiceDependency: caller_service, callee_service, protocol, operation, call_count, error_rate, p99_latency
SamplingRule: service, operation, rate, conditions[]
```

## 3. API Design

### Span Ingestion (OpenTelemetry Protocol - OTLP)
```
POST /v1/traces
Content-Type: application/x-protobuf
Authorization: Bearer <API_KEY>

Request (JSON representation of protobuf):
{
  "resource_spans": [
    {
      "resource": {
        "attributes": [
          { "key": "service.name", "value": { "string_value": "payment-service" } },
          { "key": "service.version", "value": { "string_value": "2.1.0" } },
          { "key": "deployment.environment", "value": { "string_value": "production" } }
        ]
      },
      "scope_spans": [
        {
          "scope": { "name": "io.opentelemetry.contrib.httphandler", "version": "1.2.0" },
          "spans": [
            {
              "trace_id": "5b8aa5a2d2c872e8321cf37308d69df2",
              "span_id": "051581bf3cb55c13",
              "parent_span_id": "ab23f45d67890abc",
              "name": "POST /api/v1/payments",
              "kind": "SPAN_KIND_SERVER",
              "start_time_unix_nano": 1700000000000000000,
              "end_time_unix_nano": 1700000000150000000,
              "status": { "code": "STATUS_CODE_OK" },
              "attributes": [
                { "key": "http.method", "value": { "string_value": "POST" } },
                { "key": "http.status_code", "value": { "int_value": 200 } },
                { "key": "http.url", "value": { "string_value": "/api/v1/payments" } }
              ],
              "events": [
                {
                  "name": "payment.processed",
                  "time_unix_nano": 1700000000120000000,
                  "attributes": [
                    { "key": "payment.id", "value": { "string_value": "pay_abc123" } }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}

Response (200):
{
  "partial_success": {
    "rejected_spans": 0,
    "error_message": ""
  }
}
```

### Trace Query API
```
GET /api/v2/traces?service=payment-service&operation=POST+/api/v1/payments&min_duration=100ms&max_duration=5s&tags=http.status_code:500&start=1700000000&end=1700003600&limit=20
Authorization: Bearer <API_KEY>

Response:
{
  "traces": [
    {
      "trace_id": "5b8aa5a2d2c872e8321cf37308d69df2",
      "root_service": "api-gateway",
      "root_operation": "GET /checkout",
      "duration_ms": 342,
      "span_count": 15,
      "service_count": 5,
      "status": "ERROR",
      "started_at": "2024-01-15T10:00:00.000Z",
      "services": [
        { "name": "api-gateway", "span_count": 2, "error_count": 0 },
        { "name": "payment-service", "span_count": 5, "error_count": 1 },
        { "name": "inventory-service", "span_count": 4, "error_count": 0 }
      ]
    }
  ],
  "total": 156,
  "next_cursor": "eyJvZmZzZXQiOjIwfQ=="
}
```

### Get Trace by ID
```
GET /api/v2/traces/5b8aa5a2d2c872e8321cf37308d69df2
Authorization: Bearer <API_KEY>

Response:
{
  "trace_id": "5b8aa5a2d2c872e8321cf37308d69df2",
  "spans": [
    {
      "span_id": "ab23f45d67890abc",
      "parent_span_id": null,
      "service": "api-gateway",
      "operation": "GET /checkout",
      "start_time": "2024-01-15T10:00:00.000000Z",
      "duration_us": 342000,
      "status": "OK",
      "kind": "SERVER",
      "attributes": { "http.method": "GET", "http.status_code": 200 },
      "children_ids": ["051581bf3cb55c13", "def456789012345a"]
    },
    {
      "span_id": "051581bf3cb55c13",
      "parent_span_id": "ab23f45d67890abc",
      "service": "payment-service",
      "operation": "POST /api/v1/payments",
      "start_time": "2024-01-15T10:00:00.005000Z",
      "duration_us": 150000,
      "status": "OK",
      "kind": "SERVER",
      "attributes": { "http.method": "POST", "http.status_code": 200 }
    }
  ],
  "critical_path": {
    "spans": ["ab23f45d67890abc", "051581bf3cb55c13"],
    "total_duration_us": 342000,
    "bottleneck_span_id": "051581bf3cb55c13",
    "bottleneck_percentage": 43.8
  },
  "service_map": {
    "nodes": ["api-gateway", "payment-service", "inventory-service"],
    "edges": [
      { "from": "api-gateway", "to": "payment-service", "call_count": 1 },
      { "from": "api-gateway", "to": "inventory-service", "call_count": 2 }
    ]
  }
}
```

### Service Dependency Map
```
GET /api/v2/services/dependencies?start=1700000000&end=1700003600
Authorization: Bearer <API_KEY>

Response:
{
  "services": [
    {
      "name": "payment-service",
      "type": "web",
      "metrics": {
        "request_rate": 1500.0,
        "error_rate": 0.02,
        "p50_latency_ms": 12,
        "p99_latency_ms": 145
      }
    }
  ],
  "dependencies": [
    {
      "parent": "api-gateway",
      "child": "payment-service",
      "call_rate": 850.0,
      "error_rate": 0.01,
      "p99_latency_ms": 95
    }
  ]
}
```

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      DISTRIBUTED TRACING PLATFORM                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │  App +   │  │  App +   │  │  App +   │  │  App +   │                    │
│  │  OTel SDK│  │  OTel SDK│  │  OTel SDK│  │  OTel SDK│                    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                    │
│       │              │              │              │                          │
│       └──────────────┴──────┬───────┴──────────────┘                         │
│                             │ (OTLP gRPC/HTTP)                               │
│                             │                                                │
│                    ┌────────▼────────┐                                       │
│                    │  OTel Collector │ (Agent mode - per node)                │
│                    │  - Batching     │                                       │
│                    │  - Head Sampling│                                       │
│                    └────────┬────────┘                                       │
│                             │                                                │
│                    ┌────────▼────────┐                                       │
│                    │  OTel Collector │ (Gateway mode - centralized)           │
│                    │  - Tail Sampling│                                       │
│                    │  - Enrichment   │                                       │
│                    └────────┬────────┘                                       │
│                             │                                                │
│                    ┌────────▼────────┐                                       │
│                    │   Kafka Cluster │                                       │
│                    │   spans-raw     │                                       │
│                    └───┬───────┬─────┘                                       │
│                        │       │                                             │
│           ┌────────────▼──┐ ┌──▼──────────────┐                             │
│           │  Span Writer  │ │ Aggregation     │                             │
│           │  Service      │ │ Service         │                             │
│           └───────┬───────┘ └──────┬──────────┘                             │
│                   │                │                                          │
│           ┌───────▼───────┐ ┌──────▼──────────┐                             │
│           │  ClickHouse   │ │  Service Graph  │                             │
│           │  (Span Store) │ │  DB (Redis)     │                             │
│           └───────┬───────┘ └─────────────────┘                             │
│                   │                                                           │
│           ┌───────▼───────┐                                                  │
│           │  Query Service│                                                  │
│           │  + API        │                                                  │
│           └───────┬───────┘                                                  │
│                   │                                                           │
│           ┌───────▼───────┐                                                  │
│           │  UI (Trace    │                                                  │
│           │  Visualization)│                                                 │
│           └───────────────┘                                                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 5. Deep Dive: Sampling Strategies

### Head-Based Sampling

```python
class HeadBasedSampler:
    """
    Decision made at trace start, propagated via context.
    Deterministic by trace ID ensures consistency across services.
    """
    
    def __init__(self, default_rate=0.1, per_service_rates=None):
        self.default_rate = default_rate
        self.per_service_rates = per_service_rates or {}
    
    def should_sample(self, trace_id, service_name, operation, attributes):
        """
        Deterministic sampling based on trace ID.
        Same trace ID always produces same decision across all services.
        """
        # Check per-service/operation overrides
        rate = self._get_rate(service_name, operation)
        
        # Deterministic: use trace ID as hash input
        # Last 8 bytes of trace ID as unsigned int
        hash_value = int(trace_id[-16:], 16)
        threshold = int(rate * (2**63 - 1))
        
        sampled = hash_value < threshold
        
        return SamplingDecision(
            sampled=sampled,
            record_only=not sampled,  # Still record for tail-based
            attributes={"sampling.rate": rate, "sampling.decision": "head"}
        )
    
    def _get_rate(self, service_name, operation):
        key = f"{service_name}/{operation}"
        if key in self.per_service_rates:
            return self.per_service_rates[key]
        if service_name in self.per_service_rates:
            return self.per_service_rates[service_name]
        return self.default_rate


class TraceIDRatioSampler:
    """W3C-compatible trace ID ratio sampler."""
    
    def __init__(self, ratio):
        self.ratio = ratio
        # Threshold = ratio * MAX_TRACE_ID_VALUE
        self.bound = int(ratio * (1 << 63))
    
    def should_sample(self, context, trace_id, name, kind, attributes, links):
        # Extract lower 64 bits of trace_id
        lower_long = int.from_bytes(trace_id[8:], byteorder='big', signed=False)
        
        if lower_long < self.bound:
            return Decision.RECORD_AND_SAMPLE
        return Decision.DROP
```

### Tail-Based Sampling

```python
class TailBasedSampler:
    """
    Buffer complete traces, then decide based on error/latency/attributes.
    Requires collector-level buffering with trace assembly.
    """
    
    def __init__(self, config):
        self.policies = config.policies
        self.trace_buffer = TraceBuffer(
            max_traces=100000,
            decision_wait=30,  # seconds to wait for trace completion
            max_span_per_trace=5000
        )
        self.decided_traces = LRUCache(maxsize=1000000)  # Recently decided
    
    async def process_span(self, span):
        """Buffer span and check if trace is ready for decision."""
        trace_id = span.trace_id
        
        # Check if already decided
        if trace_id in self.decided_traces:
            decision = self.decided_traces[trace_id]
            if decision == Decision.SAMPLE:
                await self._emit_span(span)
            return
        
        # Buffer the span
        self.trace_buffer.add_span(span)
        
        # Check if trace is complete or timeout reached
        trace = self.trace_buffer.get_trace(trace_id)
        if trace and self._is_ready_for_decision(trace):
            decision = self._evaluate_policies(trace)
            self.decided_traces[trace_id] = decision
            
            if decision == Decision.SAMPLE:
                for buffered_span in trace.spans:
                    await self._emit_span(buffered_span)
            
            self.trace_buffer.remove_trace(trace_id)
    
    def _evaluate_policies(self, trace):
        """Evaluate all policies - any match means sample."""
        for policy in self.policies:
            if policy.evaluate(trace):
                return Decision.SAMPLE
        return Decision.DROP
    
    def _is_ready_for_decision(self, trace):
        """Check if we have enough info or hit timeout."""
        age = time.time() - trace.first_span_time
        if age >= self.trace_buffer.decision_wait:
            return True
        # Heuristic: root span ended and no new spans for 5s
        if trace.root_span and trace.root_span.end_time:
            if time.time() - trace.last_span_time > 5:
                return True
        return False


class TailSamplingPolicy:
    """Configurable policies for tail-based sampling decisions."""
    
    @staticmethod
    def error_policy(trace):
        """Always sample traces with errors."""
        return any(span.status_code == StatusCode.ERROR for span in trace.spans)
    
    @staticmethod
    def latency_policy(trace, threshold_ms=1000):
        """Sample traces exceeding latency threshold."""
        return trace.duration_ms > threshold_ms
    
    @staticmethod
    def attribute_policy(trace, key, values):
        """Sample traces with specific attribute values."""
        for span in trace.spans:
            if span.attributes.get(key) in values:
                return True
        return False
    
    @staticmethod
    def probabilistic_policy(trace, rate=0.01):
        """Probabilistic sampling on remaining traces."""
        hash_val = hash(trace.trace_id) % 10000
        return hash_val < (rate * 10000)
    
    @staticmethod
    def rate_limiting_policy(trace, service_rates):
        """Per-service rate limiting to control costs."""
        root_service = trace.root_span.service_name if trace.root_span else "unknown"
        return service_rates.get(root_service, RateLimiter(100)).allow()


class AdaptiveSampler:
    """
    Dynamically adjust sampling rate based on traffic volume.
    Target: maintain consistent trace volume regardless of load.
    """
    
    def __init__(self, target_traces_per_second=1000):
        self.target_tps = target_traces_per_second
        self.service_rates = {}
        self.service_counters = defaultdict(lambda: SlidingWindowCounter(60))
    
    def get_rate(self, service_name):
        """Get current sampling rate for a service."""
        if service_name not in self.service_rates:
            return 1.0  # Default: sample everything until we have data
        return self.service_rates[service_name]
    
    def update_rates(self):
        """Periodically recalculate rates (every 10 seconds)."""
        total_traffic = sum(c.get_count() for c in self.service_counters.values())
        
        for service, counter in self.service_counters.items():
            service_traffic = counter.get_count()
            if service_traffic == 0:
                continue
            
            # Proportional allocation of target budget
            service_budget = self.target_tps * (service_traffic / total_traffic)
            new_rate = min(1.0, service_budget / service_traffic)
            
            # Smooth rate changes to avoid oscillation
            current_rate = self.service_rates.get(service, 1.0)
            smoothed_rate = 0.7 * current_rate + 0.3 * new_rate
            self.service_rates[service] = max(0.001, smoothed_rate)  # Min 0.1%
    
    def record_span(self, service_name):
        """Record that a span was seen (regardless of sampling decision)."""
        self.service_counters[service_name].increment()
```

## 6. Deep Dive: Trace Storage at Scale

### ClickHouse Schema (Columnar Storage)

```sql
-- Main spans table (columnar, time-partitioned)
CREATE TABLE spans (
    trace_id        FixedString(32),
    span_id         FixedString(16),
    parent_span_id  FixedString(16),
    operation_name  LowCardinality(String),
    service_name    LowCardinality(String),
    span_kind       Enum8('UNSPECIFIED'=0, 'INTERNAL'=1, 'SERVER'=2, 'CLIENT'=3, 'PRODUCER'=4, 'CONSUMER'=5),
    start_time      DateTime64(6),  -- microsecond precision
    duration_us     UInt64,
    status_code     Enum8('UNSET'=0, 'OK'=1, 'ERROR'=2),
    status_message  String,
    
    -- Denormalized resource attributes
    resource_service_version    LowCardinality(String),
    resource_host               LowCardinality(String),
    resource_container_id       String,
    resource_k8s_pod            LowCardinality(String),
    resource_k8s_namespace      LowCardinality(String),
    
    -- Span attributes as nested arrays (for flexible querying)
    attribute_keys      Array(LowCardinality(String)),
    attribute_values    Array(String),
    
    -- Events
    event_names         Array(String),
    event_timestamps    Array(DateTime64(6)),
    
    -- For efficient trace assembly
    tenant_id           UInt64,
    
    -- Indexes
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_service service_name TYPE set(0) GRANULARITY 1,
    INDEX idx_operation operation_name TYPE set(0) GRANULARITY 4,
    INDEX idx_status status_code TYPE set(3) GRANULARITY 1,
    INDEX idx_duration duration_us TYPE minmax GRANULARITY 1,
    INDEX idx_attrs attribute_keys TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY (tenant_id, toYYYYMMDD(start_time))
ORDER BY (tenant_id, service_name, operation_name, start_time, trace_id)
TTL start_time + INTERVAL 14 DAY
SETTINGS index_granularity = 8192;

-- Materialized view for trace-level aggregates
CREATE MATERIALIZED VIEW trace_summaries
ENGINE = AggregatingMergeTree()
PARTITION BY (tenant_id, toYYYYMMDD(min_start_time))
ORDER BY (tenant_id, trace_id)
AS SELECT
    tenant_id,
    trace_id,
    min(start_time) AS min_start_time,
    max(start_time + duration_us) AS max_end_time,
    countState() AS span_count,
    uniqState(service_name) AS service_count,
    maxState(duration_us) AS root_duration_us,
    anyState(status_code = 'ERROR') AS has_error,
    groupArrayState(service_name) AS services
FROM spans
GROUP BY tenant_id, trace_id;

-- Service dependency edges (aggregated)
CREATE MATERIALIZED VIEW service_edges
ENGINE = SummingMergeTree()
PARTITION BY (tenant_id, toYYYYMM(timestamp))
ORDER BY (tenant_id, caller_service, callee_service, protocol, timestamp)
AS SELECT
    tenant_id,
    toStartOfMinute(s1.start_time) AS timestamp,
    s1.service_name AS caller_service,
    s2.service_name AS callee_service,
    extractFromAttributes(s1.attribute_keys, s1.attribute_values, 'rpc.system') AS protocol,
    count() AS call_count,
    countIf(s2.status_code = 'ERROR') AS error_count,
    quantilesState(0.5, 0.95, 0.99)(s2.duration_us) AS latency_quantiles
FROM spans s1
INNER JOIN spans s2 ON s1.trace_id = s2.trace_id AND s1.span_id = s2.parent_span_id
WHERE s1.service_name != s2.service_name
GROUP BY tenant_id, timestamp, caller_service, callee_service, protocol;
```

### Inverted Index for Attribute Search

```python
class SpanAttributeIndex:
    """
    Inverted index on span attributes for flexible search.
    Stored in ClickHouse with bloom filters + secondary data skipping.
    """
    
    def build_query(self, search_params):
        """Build efficient ClickHouse query from search parameters."""
        conditions = []
        
        if search_params.service:
            conditions.append(f"service_name = '{search_params.service}'")
        
        if search_params.operation:
            conditions.append(f"operation_name = '{search_params.operation}'")
        
        if search_params.min_duration:
            conditions.append(f"duration_us >= {search_params.min_duration * 1000}")
        
        if search_params.max_duration:
            conditions.append(f"duration_us <= {search_params.max_duration * 1000}")
        
        if search_params.status == 'error':
            conditions.append("status_code = 'ERROR'")
        
        # Tag/attribute filters using array functions
        for key, value in search_params.tags.items():
            conditions.append(
                f"attribute_values[indexOf(attribute_keys, '{key}')] = '{value}'"
            )
        
        # Time range (critical for partition pruning)
        conditions.append(f"start_time >= toDateTime64('{search_params.start}', 6)")
        conditions.append(f"start_time <= toDateTime64('{search_params.end}', 6)")
        conditions.append(f"tenant_id = {search_params.tenant_id}")
        
        query = f"""
            SELECT DISTINCT trace_id,
                   min(start_time) as trace_start,
                   max(start_time + duration_us) as trace_end,
                   count() as span_count
            FROM spans
            WHERE {' AND '.join(conditions)}
            GROUP BY trace_id
            ORDER BY trace_start DESC
            LIMIT {search_params.limit}
        """
        return query
```

## 7. Deep Dive: Critical Path Analysis

```python
class CriticalPathAnalyzer:
    """
    Find the critical path through a distributed trace.
    The critical path is the longest chain of sequential operations
    that determines the total trace duration.
    """
    
    def analyze(self, trace):
        """
        Build DAG from spans and find critical path.
        Accounts for parallelism - only sequential dependencies matter.
        """
        # Build span tree
        spans_by_id = {s.span_id: s for s in trace.spans}
        children = defaultdict(list)
        root = None
        
        for span in trace.spans:
            if span.parent_span_id:
                children[span.parent_span_id].append(span)
            else:
                root = span
        
        if not root:
            return CriticalPath(spans=[], total_duration=0)
        
        # Calculate critical path using DFS with "self time" concept
        critical_path = self._find_critical_path(root, children)
        
        # Calculate bottleneck percentages
        total_duration = root.duration_us
        for entry in critical_path:
            entry.percentage = (entry.self_time_us / total_duration) * 100
        
        # Identify top bottleneck
        bottleneck = max(critical_path, key=lambda e: e.self_time_us)
        
        return CriticalPath(
            spans=critical_path,
            total_duration_us=total_duration,
            bottleneck_span_id=bottleneck.span_id,
            bottleneck_percentage=bottleneck.percentage
        )
    
    def _find_critical_path(self, span, children_map):
        """
        Recursive critical path finding.
        Self-time = span duration - time covered by children.
        Critical child = the child that ends latest (determines parent's end time).
        """
        span_children = children_map.get(span.span_id, [])
        
        if not span_children:
            # Leaf span: entire duration is self-time
            return [CriticalPathEntry(
                span_id=span.span_id,
                service=span.service_name,
                operation=span.operation_name,
                duration_us=span.duration_us,
                self_time_us=span.duration_us,
                start_time=span.start_time
            )]
        
        # Find which child is on the critical path
        # Critical child = one whose completion time is latest
        child_paths = []
        for child in span_children:
            child_end_time = child.start_time_us + child.duration_us
            child_critical_path = self._find_critical_path(child, children_map)
            child_paths.append((child_end_time, child, child_critical_path))
        
        # The critical child is the one that finishes last
        _, critical_child, critical_child_path = max(child_paths, key=lambda x: x[0])
        
        # Self-time = total duration - duration of critical child
        # (simplified: time not covered by any child)
        children_coverage = self._calculate_children_coverage(span, span_children)
        self_time = span.duration_us - children_coverage
        
        # Build path: self entry + critical child's path
        self_entry = CriticalPathEntry(
            span_id=span.span_id,
            service=span.service_name,
            operation=span.operation_name,
            duration_us=span.duration_us,
            self_time_us=max(0, self_time),
            start_time=span.start_time
        )
        
        return [self_entry] + critical_child_path
    
    def _calculate_children_coverage(self, parent, children):
        """
        Calculate total time covered by children (handling overlaps).
        Uses interval merging to handle parallel children.
        """
        if not children:
            return 0
        
        # Convert to intervals relative to parent start
        intervals = []
        for child in children:
            start = child.start_time_us - parent.start_time_us
            end = start + child.duration_us
            intervals.append((max(0, start), min(end, parent.duration_us)))
        
        # Merge overlapping intervals
        intervals.sort()
        merged = [intervals[0]]
        for start, end in intervals[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        
        # Sum merged interval lengths
        return sum(end - start for start, end in merged)


class ServiceDependencyBuilder:
    """Build service dependency graph from trace data in real-time."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def process_trace(self, trace):
        """Extract service-to-service edges from trace."""
        spans_by_id = {s.span_id: s for s in trace.spans}
        
        for span in trace.spans:
            if span.parent_span_id and span.parent_span_id in spans_by_id:
                parent = spans_by_id[span.parent_span_id]
                if parent.service_name != span.service_name:
                    await self._record_edge(
                        caller=parent.service_name,
                        callee=span.service_name,
                        duration_us=span.duration_us,
                        is_error=span.status_code == StatusCode.ERROR,
                        timestamp=span.start_time
                    )
    
    async def _record_edge(self, caller, callee, duration_us, is_error, timestamp):
        """Update edge metrics in Redis with sliding window."""
        edge_key = f"svc_edge:{caller}:{callee}"
        minute_bucket = int(timestamp // 60) * 60
        
        pipe = self.redis.pipeline()
        pipe.hincrby(f"{edge_key}:{minute_bucket}", "calls", 1)
        if is_error:
            pipe.hincrby(f"{edge_key}:{minute_bucket}", "errors", 1)
        pipe.lpush(f"{edge_key}:latencies:{minute_bucket}", duration_us)
        pipe.ltrim(f"{edge_key}:latencies:{minute_bucket}", 0, 9999)
        pipe.expire(f"{edge_key}:{minute_bucket}", 3600)
        pipe.expire(f"{edge_key}:latencies:{minute_bucket}", 3600)
        await pipe.execute()
```

## 8. Database Schema

### PostgreSQL (Configuration & Metadata)

```sql
CREATE TABLE services (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    name            VARCHAR(256) NOT NULL,
    type            VARCHAR(32),  -- web, db, cache, queue, serverless
    framework       VARCHAR(128),
    language        VARCHAR(64),
    first_seen      TIMESTAMPTZ DEFAULT NOW(),
    last_seen       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE operations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id      UUID NOT NULL REFERENCES services(id),
    name            VARCHAR(512) NOT NULL,
    span_kind       VARCHAR(32),
    first_seen      TIMESTAMPTZ DEFAULT NOW(),
    last_seen       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (service_id, name, span_kind)
);

CREATE TABLE sampling_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    service_pattern VARCHAR(256),  -- glob pattern
    operation_pattern VARCHAR(256),
    sampling_type   VARCHAR(32) NOT NULL,  -- head, tail, adaptive
    rate            DECIMAL(5,4),
    conditions      JSONB,  -- for tail-based: {"min_duration_ms": 1000, "status": "error"}
    priority        INT DEFAULT 0,
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_tenant_rules (tenant_id, priority DESC)
);

CREATE TABLE trace_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    name            VARCHAR(256) NOT NULL,
    service         VARCHAR(256),
    operation       VARCHAR(256),
    alert_type      VARCHAR(32),  -- error_rate, latency_p99, throughput
    threshold       JSONB NOT NULL,
    window_seconds  INT DEFAULT 300,
    notification_channels JSONB,
    enabled         BOOLEAN DEFAULT TRUE,
    last_triggered  TIMESTAMPTZ,
    INDEX idx_tenant_alerts (tenant_id)
);
```

## 9. Kafka & Redis Configuration

### Kafka Configuration

```yaml
topics:
  spans-raw:
    partitions: 128
    replication_factor: 3
    retention_ms: 7200000  # 2 hours
    cleanup_policy: delete
    compression_type: zstd
    max_message_bytes: 2097152  # 2MB (large traces)
    
  spans-sampled:
    partitions: 64
    replication_factor: 3
    retention_ms: 86400000  # 24 hours
    cleanup_policy: delete
    compression_type: lz4

  service-metrics:
    partitions: 32
    replication_factor: 3
    retention_ms: 604800000  # 7 days
    
# Consumer config for span writers
consumer:
  group_id: span-writers
  auto_offset_reset: latest
  max_poll_records: 5000
  fetch_max_bytes: 104857600  # 100MB
  # Partition assignment: cooperative sticky for minimal rebalance disruption
  partition_assignment_strategy: CooperativeStickyAssignor

# Consumer config for tail sampling
consumer_tail_sampling:
  group_id: tail-samplers
  # IMPORTANT: All spans of same trace must go to same consumer
  # Partition by trace_id to ensure trace completeness
  auto_offset_reset: latest
  max_poll_records: 10000
```

### Redis Configuration

```yaml
redis:
  cluster:
    nodes: 6
    node_memory: 16GB
    maxmemory_policy: allkeys-lru
  
  usage:
    # Tail sampling trace buffer
    trace_buffer: "trace:{trace_id}"  # Hash with span data, TTL 60s
    
    # Service dependency graph (real-time)
    service_edge: "svc_edge:{caller}:{callee}:{minute}"
    service_edge_latencies: "svc_edge:{caller}:{callee}:latencies:{minute}"
    
    # Adaptive sampling state
    sampling_counters: "sample_count:{service}:{minute}"
    sampling_rates: "sample_rate:{service}"
    
    # Rate limiting
    ingestion_rate: "ingest_rate:{tenant_id}"
```

## 10. Scalability & Performance

### Ingestion Scaling
- **Collector auto-scaling**: Scale gateway collectors based on Kafka lag
- **Trace ID partitioning**: Hash trace_id for Kafka partition → ensures all spans of a trace go to same tail-sampling consumer
- **Batch writes to ClickHouse**: Buffer 10K spans per batch, write every 5 seconds
- **Async indexing**: Bloom filter and attribute index updates are asynchronous

### Query Optimization
- **Partition pruning**: Time + tenant in partition key eliminates 99% of scans
- **Trace ID bloom filter**: Skip granules without matching trace IDs
- **Two-phase query**: First find matching trace IDs, then fetch full traces
- **Result caching**: Cache frequently accessed traces in Redis (5-minute TTL)

### Storage Optimization
- **Columnar compression**: LowCardinality for service/operation (90%+ compression)
- **Tiered storage**: Recent data on NVMe SSD, older on object storage
- **Aggressive TTL**: 14 days raw, 90 days aggregated summaries

### Capacity Planning
```
1M spans/sec ingestion:
- Kafka: 128 partitions × 8K spans/sec/partition
- ClickHouse: 6 nodes × 170K inserts/sec
- Storage: 1M spans × 500 bytes avg × 86400 sec × 14 days / 10x compression = ~60TB
- Tail sampling buffer: 100K traces × 10KB avg = 1GB Redis
```

## 11. Failure Handling & Reliability

### Span Loss Prevention
- OTel SDK: In-memory queue with disk spillover
- Collector: Persistent queue with WAL before Kafka produce
- Kafka: Replication factor 3 with min.insync.replicas=2

### Tail Sampling Failures
- Trace timeout: If decision not made in 60s, apply probabilistic fallback
- Consumer rebalance: Trace buffer replicated to standby consumer
- Memory pressure: Evict oldest unbuffered traces, log skipped count

### ClickHouse Failures
- ReplicatedMergeTree: Automatic replication across 3 nodes
- Async insert retry: Failed batches queued to Kafka DLQ
- Query failover: Route to replica if primary shard unavailable

### Data Consistency
- Trace completeness is best-effort (network may drop spans)
- Service graph is eventually consistent (refreshed every minute)
- Sampling decisions are consistent per-trace (trace ID determinism)

### Disaster Recovery
- ClickHouse: Cross-DC replication with async lag < 30s
- Kafka: MirrorMaker2 for cross-region topic replication
- Configuration: PostgreSQL streaming replication
- RTO: 2 minutes for ingestion, 5 minutes for query
