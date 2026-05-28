# OpenTelemetry Fundamentals

## What is OpenTelemetry?

OpenTelemetry (OTEL) is a vendor-neutral, open-source observability framework for generating, collecting, transforming, and exporting telemetry data — **metrics**, **logs**, and **traces** — from distributed systems.

It is not a backend. It does not store data. It is the **instrumentation and pipeline layer** that sits between your applications and your observability backends (Prometheus, Jaeger, ClickHouse, Datadog, etc.).

---

## The Three Pillars of Observability

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                                  │
├──────────────────┬──────────────────┬───────────────────────────┤
│     METRICS      │      LOGS        │         TRACES            │
│                  │                  │                           │
│ What happened?   │ Why it happened? │ How it happened across    │
│ (aggregated)     │ (discrete event) │ services? (request flow)  │
│                  │                  │                           │
│ CPU at 92%       │ "NullPointer at  │ Request → Auth → DB →    │
│ Latency p99=2s   │  UserService:42" │ Cache → Response (850ms) │
│ Error rate: 5%   │                  │                           │
└──────────────────┴──────────────────┴───────────────────────────┘
```

### Metrics
- **Numeric measurements** aggregated over time
- Types: Counter, Gauge, Histogram, Summary
- Example: `http_requests_total`, `process_cpu_seconds`
- Low cardinality, low cost, good for alerting

### Logs
- **Discrete events** with timestamp and context
- Structured (JSON) or unstructured (plain text)
- Example: `{"level":"ERROR","msg":"connection timeout","service":"payment"}`
- High cardinality, high volume, good for debugging

### Traces
- **End-to-end request journey** across services
- Composed of spans (units of work)
- Example: HTTP request → API Gateway → Auth Service → Database → Response
- Shows causality, latency breakdown, and dependency mapping

---

## OTEL Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         APPLICATION                                    │
│                                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │  OTEL SDK   │  │  OTEL SDK   │  │  OTEL SDK   │                  │
│  │  (Metrics)  │  │   (Logs)    │  │  (Traces)   │                  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │
│         │                 │                 │                          │
│  ┌──────┴─────────────────┴─────────────────┴──────┐                 │
│  │              OTEL API Layer                       │                 │
│  └──────────────────────┬────────────────────────────┘                │
│                         │                                             │
│  ┌──────────────────────┴────────────────────────────┐               │
│  │           OTEL Exporter (OTLP)                     │               │
│  └──────────────────────┬────────────────────────────┘               │
└─────────────────────────┼────────────────────────────────────────────┘
                          │ OTLP (gRPC/HTTP)
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     OTEL COLLECTOR                                    │
│                                                                       │
│  ┌───────────┐    ┌──────────────┐    ┌────────────────┐            │
│  │ Receivers │───▶│  Processors  │───▶│   Exporters    │            │
│  └───────────┘    └──────────────┘    └────────┬───────┘            │
└────────────────────────────────────────────────┼────────────────────┘
                                                 │
                    ┌────────────────────────────┼─────────────────┐
                    │                            │                  │
                    ▼                            ▼                  ▼
           ┌──────────────┐            ┌──────────────┐   ┌──────────────┐
           │  Prometheus  │            │   Jaeger     │   │  ClickHouse  │
           │  /Victoria   │            │   /Tempo     │   │   (Logs)     │
           │  (Metrics)   │            │   (Traces)   │   │              │
           └──────────────┘            └──────────────┘   └──────────────┘
```

---

## Core Components

### 1. OTEL API

The **API** is the contract. It defines interfaces for:
- `Tracer` — creates spans
- `Meter` — creates metrics instruments
- `Logger` — emits log records

The API is **implementation-free**. Libraries instrument against the API, and applications provide the SDK implementation.

```java
// API usage — library code instruments against this
Tracer tracer = GlobalOpenTelemetry.getTracer("com.myapp.service");
Span span = tracer.spanBuilder("processOrder").startSpan();
```

### 2. OTEL SDK

The **SDK** is the implementation of the API. It handles:
- Span creation and lifecycle management
- Metric aggregation (delta vs cumulative)
- Log record buffering
- Sampling decisions
- Resource detection (hostname, container ID, cloud metadata)
- Exporting batched data

```java
// SDK configuration — application bootstrap
SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
    .addSpanProcessor(BatchSpanProcessor.builder(otlpExporter).build())
    .setSampler(Sampler.traceIdRatioBased(0.1))  // 10% sampling
    .build();
```

### 3. OTLP (OpenTelemetry Protocol)

The **wire protocol** for transmitting telemetry data. Supports:
- **gRPC** (default, binary, efficient, streaming)
- **HTTP/protobuf** (binary over HTTP POST)
- **HTTP/JSON** (human-readable, debugging)

OTLP is the native protocol of OTEL. All data types (metrics, logs, traces) use a unified schema.

### 4. OTEL Collector

A **vendor-agnostic proxy** that receives, processes, and exports telemetry data. Covered in depth in the next file.

### 5. Instrumentation Libraries

Pre-built instrumentation for common frameworks:
- HTTP clients/servers (Express, Spring, Flask)
- Database drivers (JDBC, pg, mysql2)
- Message queues (Kafka, RabbitMQ, SQS)
- gRPC, GraphQL, Redis, etc.

---

## Data Model

### Resource

Represents the entity producing telemetry:

```json
{
  "resource": {
    "attributes": {
      "service.name": "payment-service",
      "service.version": "2.3.1",
      "deployment.environment": "production",
      "host.name": "prod-payment-03",
      "container.id": "abc123def456",
      "cloud.provider": "aws",
      "cloud.region": "us-east-1"
    }
  }
}
```

### Span (Trace Data)

```json
{
  "traceId": "5b8aa5a2d2c872e8321cf37308d69df2",
  "spanId": "051581bf3cb55c13",
  "parentSpanId": "ab23f456de789012",
  "name": "POST /api/orders",
  "kind": "SERVER",
  "startTimeUnixNano": 1716900000000000000,
  "endTimeUnixNano": 1716900000850000000,
  "attributes": {
    "http.method": "POST",
    "http.status_code": 201,
    "http.url": "/api/orders",
    "db.system": "postgresql",
    "db.statement": "INSERT INTO orders..."
  },
  "status": { "code": "OK" },
  "events": [
    {
      "name": "cache.miss",
      "timeUnixNano": 1716900000200000000,
      "attributes": { "cache.key": "user:1234" }
    }
  ]
}
```

### Metric Data Point

```json
{
  "name": "http.server.request.duration",
  "description": "Duration of HTTP server requests",
  "unit": "s",
  "histogram": {
    "dataPoints": [
      {
        "startTimeUnixNano": 1716900000000000000,
        "timeUnixNano": 1716900060000000000,
        "count": 1500,
        "sum": 425.7,
        "bucketCounts": [200, 500, 400, 250, 100, 50],
        "explicitBounds": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
        "attributes": {
          "http.method": "GET",
          "http.route": "/api/users/:id"
        }
      }
    ]
  }
}
```

### Log Record

```json
{
  "timeUnixNano": 1716900000500000000,
  "severityNumber": 17,
  "severityText": "ERROR",
  "body": "Failed to process payment: insufficient funds",
  "attributes": {
    "user.id": "usr_12345",
    "order.id": "ord_67890",
    "payment.amount": 150.00,
    "exception.type": "InsufficientFundsException"
  },
  "traceId": "5b8aa5a2d2c872e8321cf37308d69df2",
  "spanId": "051581bf3cb55c13"
}
```

---

## Context Propagation

The mechanism that ties traces together across service boundaries.

```
Service A                         Service B                        Service C
┌─────────────┐                  ┌─────────────┐                 ┌─────────────┐
│ Span A      │  HTTP Request    │ Span B      │  gRPC Call      │ Span C      │
│ traceId: X  │─────────────────▶│ traceId: X  │────────────────▶│ traceId: X  │
│ spanId: 1   │  Headers:        │ spanId: 2   │  Metadata:      │ spanId: 3   │
│             │  traceparent:    │ parentId: 1 │  traceparent:   │ parentId: 2 │
└─────────────┘  00-X-1-01      └─────────────┘  00-X-2-01      └─────────────┘
```

**W3C TraceContext** header format:
```
traceparent: 00-<trace-id>-<parent-span-id>-<trace-flags>
traceparent: 00-5b8aa5a2d2c872e8321cf37308d69df2-051581bf3cb55c13-01
```

### Propagators
- **W3C TraceContext** (default, standard)
- **B3** (Zipkin compatibility)
- **Jaeger** (legacy Jaeger format)
- **Baggage** (key-value pairs propagated across services)

---

## Semantic Conventions

Standardized attribute names ensuring consistency across services:

| Domain | Attribute | Example |
|--------|-----------|---------|
| HTTP | `http.request.method` | `GET` |
| HTTP | `http.response.status_code` | `200` |
| HTTP | `url.full` | `https://api.example.com/users` |
| Database | `db.system` | `postgresql` |
| Database | `db.statement` | `SELECT * FROM users` |
| Messaging | `messaging.system` | `kafka` |
| Messaging | `messaging.destination.name` | `orders-topic` |
| RPC | `rpc.system` | `grpc` |
| RPC | `rpc.method` | `GetUser` |

---

## Sampling Strategies

Not all traces need to be captured. Sampling reduces cost while maintaining visibility.

### Head-Based Sampling
Decision made at trace start (root span):
- **AlwaysOn** — capture 100% (dev/staging)
- **AlwaysOff** — capture 0% (disable tracing)
- **TraceIdRatioBased** — probabilistic (e.g., 10%)
- **ParentBased** — respect parent's decision

### Tail-Based Sampling
Decision made after the trace completes:
- Capture all errors regardless of ratio
- Capture all slow requests (latency > threshold)
- Capture all requests for specific users or features
- Requires buffering complete traces → needs Collector

```
┌─────────────┐         ┌──────────────────────┐         ┌─────────────┐
│ Application │────────▶│  Collector (buffering │────────▶│   Backend   │
│ (all spans) │  100%   │  tail-based sampler)  │  ~5%    │  (storage)  │
└─────────────┘         └──────────────────────┘         └─────────────┘
                              Keeps:
                              - All errors
                              - p99 latency
                              - 5% random
```

---

## Instrumentation Approaches

### 1. Automatic (Zero-Code) Instrumentation
```bash
# Java agent — attaches to JVM, instruments all supported libraries
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.service.name=payment-service \
     -Dotel.exporter.otlp.endpoint=http://collector:4317 \
     -jar app.jar
```

### 2. Manual Instrumentation
```python
from opentelemetry import trace

tracer = trace.get_tracer("payment.processor")

def process_payment(order_id, amount):
    with tracer.start_as_current_span("process_payment") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("payment.amount", amount)
        
        # Business logic
        result = charge_card(amount)
        
        if result.failed:
            span.set_status(StatusCode.ERROR, "Payment declined")
            span.record_exception(result.error)
        
        return result
```

### 3. SDK-Based (Programmatic Configuration)
```go
func initTracer() *sdktrace.TracerProvider {
    exporter, _ := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName("order-service"),
            semconv.DeploymentEnvironment("production"),
        )),
        sdktrace.WithSampler(sdktrace.TraceIDRatioBased(0.1)),
    )
    
    otel.SetTracerProvider(tp)
    return tp
}
```

---

## Key Design Principles

| Principle | Description |
|-----------|-------------|
| **Vendor Neutral** | Instrument once, export to any backend |
| **Separation of Concerns** | API (contract) vs SDK (implementation) vs Collector (pipeline) |
| **Low Overhead** | Async batching, sampling, minimal hot-path allocation |
| **Correlation** | TraceID links logs, metrics, and traces for the same request |
| **Semantic Conventions** | Standardized attribute names for interoperability |
| **Backwards Compatible** | Supports Prometheus, Zipkin, Jaeger formats |
