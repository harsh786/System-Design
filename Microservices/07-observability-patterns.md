# Observability Patterns in Microservices

## Three Pillars of Observability

Observability is the ability to understand a system's internal state from its external outputs. In microservices, where requests traverse multiple services, observability is critical for debugging, performance optimization, and reliability.

### 1. Logging (What happened)
- Structured, machine-parseable records of discrete events
- Provides detailed context about specific operations

### 2. Metrics (How the system is performing)
- Numeric measurements aggregated over time
- Enables dashboards, alerting, and trend analysis

### 3. Distributed Tracing (How requests flow)
- End-to-end request path across services
- Identifies latency bottlenecks and failure points

---

## Logging Patterns

### Structured Logging (JSON Format)

**What it is:** Logging in a consistent, machine-parseable format (typically JSON) instead of free-form text.

**Why it matters:** Enables automated parsing, querying, and alerting. Free-form logs are nearly impossible to analyze at scale.

**Implementation:**
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "ERROR",
  "service": "order-service",
  "traceId": "abc123def456",
  "spanId": "span789",
  "userId": "user-42",
  "message": "Payment processing failed",
  "error": {
    "type": "PaymentGatewayTimeout",
    "code": "PGW_TIMEOUT",
    "retryable": true
  },
  "context": {
    "orderId": "order-1001",
    "amount": 99.99,
    "currency": "USD"
  }
}
```

**Best practices:**
- Always include traceId, spanId, service name, timestamp
- Use consistent field names across all services
- Include business context (orderId, userId) for debugging
- Never log sensitive data (passwords, tokens, PII)

**Common mistakes:**
- Mixing structured and unstructured logs
- Logging too much (high cardinality fields as log messages)
- Not including correlation IDs

---

### Centralized Log Aggregation

**What it is:** Collecting logs from all services into a central, searchable store.

**Why it matters:** In microservices, a single user request may touch 10+ services. Without centralization, debugging requires SSH-ing into dozens of containers.

**Implementation approaches:**

#### ELK Stack (Elasticsearch, Logstash, Kibana)
```
Services → Filebeat → Logstash → Elasticsearch → Kibana
```
- Logstash: Parsing, enrichment, transformation
- Elasticsearch: Storage and full-text search
- Kibana: Visualization and dashboards
- Best for: Large-scale, complex parsing needs

#### EFK Stack (Elasticsearch, Fluentd, Kibana)
```
Services → Fluentd → Elasticsearch → Kibana
```
- Fluentd: Lightweight, pluggable, CNCF project
- Lower memory footprint than Logstash
- Best for: Kubernetes-native environments

#### Loki + Grafana
```
Services → Promtail → Loki → Grafana
```
- Indexes only metadata (labels), not full text
- Much cheaper storage than Elasticsearch
- Native Grafana integration (logs + metrics in one place)
- Best for: Cost-sensitive environments, Prometheus users

**Best practices:**
- Ship logs asynchronously (don't block application threads)
- Set retention policies (7 days hot, 30 days warm, archive cold)
- Use log levels to control volume in production

**Common mistakes:**
- Making the logging pipeline a single point of failure
- No backpressure handling (log storms crashing the pipeline)
- Not planning for storage costs at scale

---

### Log Correlation with Trace IDs

**What it is:** Including distributed trace identifiers in every log entry so logs from a single request can be correlated across services.

**Implementation:**
```python
# Middleware that extracts/generates trace context
import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar('trace_id')

class TraceMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, request, call_next):
        trace_id = request.headers.get('X-Trace-Id', str(uuid.uuid4()))
        trace_id_var.set(trace_id)
        response = await call_next(request)
        response.headers['X-Trace-Id'] = trace_id
        return response

# Logger automatically includes trace_id
class StructuredLogger:
    def log(self, level, message, **kwargs):
        entry = {
            "traceId": trace_id_var.get(None),
            "level": level,
            "message": message,
            **kwargs
        }
        print(json.dumps(entry))
```

**Best practices:**
- Propagate trace context via HTTP headers (W3C Traceparent)
- Include traceId in all async message metadata (Kafka headers, SQS attributes)
- Make correlation automatic via middleware, not manual

---

### Log Levels Strategy in Production

| Level | Use For | Production Default |
|-------|---------|-------------------|
| ERROR | Failures requiring attention | Always on |
| WARN | Degraded but functional | Always on |
| INFO | Business-significant events | On (sampled for high-traffic) |
| DEBUG | Developer diagnostics | Off (enable per-service dynamically) |
| TRACE | Extremely detailed flow | Off |

**Best practices:**
- Support dynamic log level changes without restart (feature flag or config reload)
- ERROR should always be actionable (if no one needs to act, it's WARN)
- INFO should tell the story of what the system is doing at a business level

---

### Log Sampling Strategies

**What it is:** Reducing log volume while maintaining visibility by only recording a percentage of events.

**Approaches:**
- **Rate-based:** Log 1 in N events for high-volume endpoints
- **Error-biased:** Always log errors, sample successes
- **Tail-based:** Decide after request completes (log everything if slow/errored)
- **Dynamic:** Increase sampling when anomalies detected

**Implementation:**
```python
import random

class SampledLogger:
    def __init__(self, sample_rate=0.1):
        self.sample_rate = sample_rate

    def info(self, message, **kwargs):
        # Always log errors, sample info
        if random.random() < self.sample_rate:
            self._emit("INFO", message, **kwargs)

    def error(self, message, **kwargs):
        # Never sample errors
        self._emit("ERROR", message, **kwargs)
```

---

## Metrics Patterns

### RED Method (Rate, Errors, Duration)

**What it is:** A methodology for instrumenting request-driven services.

**The three signals:**
- **Rate:** Requests per second
- **Errors:** Failed requests per second
- **Duration:** Distribution of request latency (p50, p95, p99)

**Why it matters:** These three metrics answer "Is my service healthy?" for any request-driven workload.

**Implementation (Prometheus):**
```python
from prometheus_client import Counter, Histogram

# Rate & Errors
request_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Duration
request_duration = Histogram(
    'http_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)
```

**Best practices:**
- Use histograms (not summaries) for duration - they're aggregatable
- Label with method, endpoint, status code
- Set meaningful histogram buckets based on your SLOs

---

### USE Method (Utilization, Saturation, Errors)

**What it is:** A methodology for instrumenting resource-providing systems (databases, queues, caches).

**The three signals:**
- **Utilization:** % of resource capacity being used (CPU at 70%)
- **Saturation:** Work queued because resource is full (queue depth)
- **Errors:** Error events from the resource

**When to use:** For infrastructure components - databases, connection pools, thread pools, disk, network.

**Examples:**
| Resource | Utilization | Saturation | Errors |
|----------|-------------|------------|--------|
| CPU | CPU % | Run queue length | - |
| Memory | Memory used % | Swap usage | OOM kills |
| Disk | Disk used % | IO queue depth | Read/write errors |
| Connection Pool | Active/Total | Pending requests | Timeouts |

---

### Four Golden Signals (Google SRE)

**What it is:** Google's SRE book defines four signals that matter most for any user-facing system.

1. **Latency:** Time to serve a request (distinguish success vs error latency)
2. **Traffic:** Demand on the system (req/s, sessions, transactions)
3. **Errors:** Rate of failed requests (explicit 5xx, implicit timeouts, wrong results)
4. **Saturation:** How full the service is (resource constrained?)

**Relationship to RED/USE:**
- RED ≈ Golden Signals for request-driven services
- USE ≈ Golden Signals for resources
- Golden Signals is the superset philosophy

---

### Custom Business Metrics

**What it is:** Application-specific metrics that track business value, not just technical health.

**Examples:**
```python
# Business metrics
orders_placed = Counter('orders_placed_total', 'Orders placed', ['payment_method'])
cart_abandonment = Counter('cart_abandoned_total', 'Cart abandonments', ['stage'])
revenue = Counter('revenue_dollars_total', 'Revenue in dollars', ['product_category'])
signup_funnel = Histogram('signup_duration_seconds', 'Time to complete signup')
```

**Why it matters:** Technical metrics tell you something is broken; business metrics tell you if it matters.

---

### Prometheus + Grafana Setup

**Architecture:**
```
Services (expose /metrics) → Prometheus (scrape & store) → Grafana (visualize & alert)
```

**Prometheus configuration:**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerting_rules.yml"

scrape_configs:
  - job_name: 'order-service'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

**Best practices:**
- Use recording rules for expensive queries
- Set up federation for multi-cluster
- Use Thanos or Cortex for long-term storage
- Label cardinality: keep it low (don't use userId as a label)

**Common mistakes:**
- High-cardinality labels causing Prometheus OOM
- No retention planning
- Scraping too frequently for non-critical services

---

### SLI, SLO, SLA Definitions and Implementation

**Definitions:**
- **SLI (Service Level Indicator):** A measurable metric (e.g., "99.2% of requests complete in < 200ms")
- **SLO (Service Level Objective):** Target for an SLI (e.g., "99.9% of requests should complete in < 200ms over 30 days")
- **SLA (Service Level Agreement):** Contractual commitment with consequences (e.g., "99.9% uptime or we refund 10%")

**Implementation:**
```yaml
# SLO definition
slo:
  name: order-service-availability
  description: "Order service should successfully process requests"
  sli:
    type: availability
    good_events: 'http_requests_total{status=~"2..|3.."}'
    total_events: 'http_requests_total'
  objective: 99.9  # percent
  window: 30d      # rolling window
```

**Error Budgets:**
- If SLO is 99.9%, error budget = 0.1% = ~43 minutes/month
- When budget is consumed: freeze deployments, focus on reliability
- When budget is healthy: deploy faster, take more risks

**Best practices:**
- Start with fewer, meaningful SLOs (3-5 per service)
- SLOs should reflect user experience, not internal metrics
- Review and adjust SLOs quarterly
- Automate error budget tracking and alerting

---

## Distributed Tracing

### OpenTelemetry (OTEL) - Complete Guide

**What it is:** A vendor-neutral, open-source observability framework providing APIs, SDKs, and tools for collecting telemetry data (traces, metrics, logs).

**Why it matters:** Single standard replacing OpenTracing + OpenCensus. Prevents vendor lock-in.

**Architecture:**
```
Application (OTEL SDK) → OTEL Collector → Backend (Jaeger/Zipkin/Tempo/X-Ray)
```

**Implementation (Python):**
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Setup
provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Auto-instrumentation
FlaskInstrumentor().instrument()
RequestsInstrumentor().instrument()

# Manual instrumentation
tracer = trace.get_tracer(__name__)

def process_order(order_id):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        validate_order(order_id)
        charge_payment(order_id)

def validate_order(order_id):
    with tracer.start_as_current_span("validate_order") as span:
        span.set_attribute("order.id", order_id)
        # validation logic
```

**OTEL Collector configuration:**
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
    timeout: 5s
    send_batch_size: 1024
  memory_limiter:
    check_interval: 1s
    limit_mib: 512

exporters:
  jaeger:
    endpoint: jaeger:14250
  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, memory_limiter]
      exporters: [jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

---

### W3C Trace Context Standard

**What it is:** A standardized HTTP header format for propagating trace context across services.

**Headers:**
```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
              version-trace_id-parent_id-trace_flags

tracestate: vendor1=value1,vendor2=value2
```

**Why it matters:** Enables interoperability between different tracing systems. All major vendors support it.

---

### Jaeger, Zipkin, AWS X-Ray

| Feature | Jaeger | Zipkin | AWS X-Ray |
|---------|--------|--------|-----------|
| Origin | Uber (CNCF) | Twitter | AWS |
| Storage | Cassandra, ES, Kafka | MySQL, ES, Cassandra | AWS managed |
| Best for | K8s/cloud-native | Simple setups | AWS-native apps |
| UI | Rich, dependency graph | Simple, functional | AWS Console integrated |
| OTEL support | Native | Native | Via OTEL Collector |

---

### Trace Propagation Across Async Boundaries

**Challenge:** Message queues (Kafka, RabbitMQ, SQS) break trace context because there's no HTTP request.

**Solution:** Embed trace context in message metadata.

```python
# Producer - inject context into message headers
from opentelemetry.propagate import inject

def publish_event(event, topic):
    with tracer.start_as_current_span("publish_event") as span:
        headers = {}
        inject(headers)  # Injects traceparent into headers dict
        kafka_producer.produce(
            topic=topic,
            value=json.dumps(event),
            headers=headers
        )

# Consumer - extract context from message headers
from opentelemetry.propagate import extract

def consume_event(message):
    context = extract(message.headers())
    with tracer.start_as_current_span("process_event", context=context) as span:
        # Processing logic - linked to original trace
        pass
```

---

### Sampling Strategies

#### Head-based Sampling
- Decision made at trace start (before any processing)
- Simple: sample 10% of all traces
- Problem: May miss rare errors

#### Tail-based Sampling
- Decision made after trace completes
- Can keep all errors, slow requests, and sample successes
- Requires buffering complete traces before decision
- More complex but much better signal

**OTEL Collector tail-based sampling:**
```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: errors
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: slow-requests
        type: latency
        latency: {threshold_ms: 1000}
      - name: percentage
        type: probabilistic
        probabilistic: {sampling_percentage: 10}
```

---

### Span Annotations and Baggage

**Span attributes:** Key-value pairs attached to a single span.
```python
span.set_attribute("http.method", "POST")
span.set_attribute("user.tier", "premium")
span.add_event("cache_miss", {"key": "user:42"})
```

**Baggage:** Key-value pairs propagated across ALL spans in a trace (context that flows downstream).
```python
from opentelemetry import baggage
baggage.set_baggage("tenant.id", "acme-corp")
# All downstream services can read tenant.id
```

**Warning:** Baggage adds to every request's header size. Keep it minimal.

---

## Alerting Patterns

### Alert Fatigue Prevention

**What it is:** Designing alerts that only fire when human action is needed, preventing on-call burnout.

**Principles:**
1. **Alert on symptoms, not causes** - Alert "error rate > 1%" not "pod restarted"
2. **Every alert must be actionable** - If no one needs to act, it's a dashboard metric
3. **Include runbook link** - Every alert has a link to resolution steps
4. **Multi-window, multi-burn-rate alerting** - Avoid flapping

**Implementation (Prometheus alerting rules):**
```yaml
groups:
  - name: slo_alerts
    rules:
      # Fast burn (2% of budget in 1 hour)
      - alert: HighErrorRate_Fast
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[5m]))
            / sum(rate(http_requests_total[5m]))
          ) > 14.4 * 0.001
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Error rate burning SLO budget fast"
          runbook: "https://wiki.internal/runbooks/high-error-rate"

      # Slow burn (5% of budget in 6 hours)
      - alert: HighErrorRate_Slow
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[30m]))
            / sum(rate(http_requests_total[30m]))
          ) > 6 * 0.001
        for: 15m
        labels:
          severity: warning
```

**Common mistakes:**
- Alerting on every 5xx (should alert on error *rate*)
- No deduplication (same issue fires 50 alerts)
- CPU > 80% alerts (saturation matters more than utilization)

---

### Symptom-Based vs Cause-Based Alerting

| Symptom-based (preferred) | Cause-based (avoid) |
|--------------------------|---------------------|
| Error rate > 1% | Pod OOMKilled |
| Latency p99 > 2s | CPU > 90% |
| Orders/min dropped 50% | Kafka lag increasing |
| Users can't login | Auth service restarted |

**Why symptom-based wins:** One symptom alert covers many causes. Cause-based alerts explode in number and most aren't actionable.

---

### Runbook Automation

**What it is:** Documented (and ideally automated) procedures for resolving common alerts.

**Structure:**
```markdown
# Runbook: High Error Rate - Order Service

## Impact
Users unable to place orders.

## Investigation
1. Check error logs: `{service="order-service", level="error"}`
2. Check dependency health: payment-service, inventory-service
3. Check recent deployments: `kubectl rollout history`

## Remediation
- If recent deploy: `kubectl rollout undo deployment/order-service`
- If downstream failure: Enable circuit breaker override
- If capacity: `kubectl scale deployment/order-service --replicas=10`

## Escalation
If unresolved in 15 min, page backend-oncall-secondary
```

---

## Advanced Observability

### Service Dependency Mapping

**What it is:** Automatically discovering and visualizing how services communicate.

**Tools:** Jaeger dependency view, Kiali (Istio), AWS X-Ray service map

**Why it matters:** Understand blast radius, identify critical paths, detect unexpected dependencies.

---

### Distributed Profiling (Continuous Profiling)

**What it is:** Always-on, low-overhead CPU/memory profiling across all service instances.

**Tools:** Pyroscope, Parca, Google Cloud Profiler, Datadog Continuous Profiler

**Why it matters:** Answers "why is this service slow?" without reproducing the issue. Complementary to tracing (tracing shows *where*, profiling shows *why*).

---

### Real User Monitoring (RUM)

**What it is:** Collecting performance data from actual user browsers/devices.

**Metrics:** Page load time, First Contentful Paint, Time to Interactive, Core Web Vitals

**Tools:** Datadog RUM, New Relic Browser, Elastic RUM, Google Analytics

---

### Synthetic Monitoring

**What it is:** Automated, scheduled tests that simulate user journeys from external locations.

**Why it matters:** Detects outages before users report them. Validates SLOs continuously.

**Tools:** Grafana Synthetic Monitoring, Datadog Synthetics, Pingdom, Checkly

---

### AIOps and Anomaly Detection

**What it is:** Using ML to detect unusual patterns, correlate events, and reduce alert noise.

**Capabilities:**
- Anomaly detection on metrics (seasonal-aware)
- Automatic root cause correlation
- Intelligent alert grouping
- Predictive alerting (forecast SLO breach)

**Tools:** Moogsoft, BigPanda, Datadog Watchdog, Dynatrace Davis AI

---

### OpenTelemetry Collector Architecture

**Deployment patterns:**

1. **Agent mode:** Sidecar or DaemonSet alongside applications
   - Low latency, local buffering
   - Per-node resource usage

2. **Gateway mode:** Centralized collector cluster
   - Easier management, tail-based sampling
   - Single point of scaling

3. **Combined:** Agent → Gateway pipeline
   ```
   App → OTEL Agent (DaemonSet) → OTEL Gateway (Deployment) → Backends
   ```

**Best practices:**
- Use memory_limiter processor to prevent OOM
- Enable batch processor for efficiency
- Separate pipelines for traces/metrics/logs
- Use load balancing exporter for consistent hashing (tail sampling)

---

### Observability as Code

**What it is:** Defining dashboards, alerts, and SLOs as version-controlled code.

**Tools:**
- **Grafana:** Jsonnet/Grafonnet for dashboards
- **Terraform:** Provider for Datadog, PagerDuty, Grafana
- **SLO frameworks:** Google's slo-generator, Sloth (Prometheus)

**Example (Sloth SLO definition):**
```yaml
version: "prometheus/v1"
service: "order-service"
slos:
  - name: "requests-availability"
    objective: 99.9
    description: "Order service request availability"
    sli:
      events:
        error_query: sum(rate(http_requests_total{service="order",code=~"5.."}[{{.window}}]))
        total_query: sum(rate(http_requests_total{service="order"}[{{.window}}]))
    alerting:
      page_alert:
        labels:
          severity: critical
      ticket_alert:
        labels:
          severity: warning
```

**Why it matters:** Dashboards and alerts drift without code review. Enables consistent observability across teams and environments.
