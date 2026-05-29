# Technologies and Frameworks for Microservices

## Table of Contents
- [Programming Languages](#programming-languages-for-microservices)
- [Java/Spring Ecosystem](#javaspring-ecosystem)
- [Messaging and Streaming](#messaging-and-streaming)
- [Databases](#databases)
- [Infrastructure and DevOps](#infrastructure-and-devops)
- [Observability Stack](#observability-stack)
- [API Tools](#api-tools)
- [Testing Tools](#testing-tools)
- [Cloud-Native Platforms](#cloud-native-platforms)
- [Emerging Technologies](#emerging-technologies)

---

## Programming Languages for Microservices

### Language Selection Criteria

| Criteria | Java/Kotlin | Go | Node.js/TS | Python | Rust | .NET |
|----------|------------|-----|-----------|--------|------|------|
| Startup time | Slow (improved with GraalVM) | Fast | Fast | Moderate | Fast | Fast |
| Memory footprint | High | Low | Moderate | Moderate | Very Low | Moderate |
| Concurrency | Threads + Virtual Threads | Goroutines (excellent) | Event loop | asyncio/threads | async + threads | async/Tasks |
| Ecosystem | Massive | Growing | Massive (npm) | Large | Growing | Large |
| Team availability | High | Growing | High | High | Low | Moderate |
| Cloud-native fit | Good | Excellent | Good | Good | Excellent | Good |
| Best for | Enterprise, complex domains | Infrastructure, high-perf APIs | I/O heavy, BFF | ML/AI, prototyping | Performance-critical | Enterprise, Azure |

### Java/Kotlin

```java
// Spring Boot microservice
@SpringBootApplication
@RestController
public class OrderService {
    @GetMapping("/orders/{id}")
    public Order getOrder(@PathVariable String id) {
        return orderRepository.findById(id);
    }
}
```

**Frameworks:**
- **Spring Boot**: De facto standard, massive ecosystem
- **Micronaut**: Compile-time DI, low memory, fast startup
- **Quarkus**: GraalVM native, "supersonic subatomic Java"
- **Vert.x**: Reactive, event-driven, polyglot

### Go

```go
// Standard library HTTP server
func main() {
    http.HandleFunc("/orders/", getOrder)
    log.Fatal(http.ListenAndServe(":8080", nil))
}

// With Gin framework
r := gin.Default()
r.GET("/orders/:id", func(c *gin.Context) {
    id := c.Param("id")
    c.JSON(200, getOrder(id))
})
r.Run(":8080")
```

**Why Go for microservices:**
- Single binary deployment (no runtime dependencies)
- ~5MB container images
- Goroutines handle massive concurrency
- Fast compilation, fast execution
- Built-in HTTP server is production-ready
- First-class gRPC support

### Node.js/TypeScript

```typescript
// NestJS microservice
@Controller('orders')
export class OrdersController {
  constructor(private readonly ordersService: OrdersService) {}

  @Get(':id')
  findOne(@Param('id') id: string): Promise<Order> {
    return this.ordersService.findOne(id);
  }

  @MessagePattern('order_created')
  handleOrderCreated(@Payload() data: CreateOrderDto) {
    return this.ordersService.handleCreated(data);
  }
}
```

**Frameworks:**
- **NestJS**: Enterprise-grade, opinionated, decorators
- **Express**: Minimal, flexible, widely known
- **Fastify**: High performance, schema-based validation

### Python

```python
# FastAPI
from fastapi import FastAPI

app = FastAPI()

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    return await order_service.find(order_id)

# Automatic OpenAPI docs at /docs
```

**Frameworks:**
- **FastAPI**: Modern, async, auto-docs, type hints
- **Flask**: Lightweight, flexible
- **Django**: Full-featured (better for monoliths, but Django REST for APIs)

### Rust

```rust
// Axum
use axum::{routing::get, Router, extract::Path};

async fn get_order(Path(id): Path<String>) -> impl IntoResponse {
    Json(order_service::find(&id).await)
}

#[tokio::main]
async fn main() {
    let app = Router::new().route("/orders/:id", get(get_order));
    axum::Server::bind(&"0.0.0.0:8080".parse().unwrap())
        .serve(app.into_make_service())
        .await.unwrap();
}
```

**Best for:** API gateways, proxy layers, real-time systems, performance-critical paths.

### .NET

```csharp
// ASP.NET Core Minimal API
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapGet("/orders/{id}", async (string id, OrderService service) =>
    await service.GetOrderAsync(id));

app.Run();
```

**Dapr integration:** Distributed Application Runtime provides building blocks (service invocation, state, pub/sub) as sidecars.

---

## Java/Spring Ecosystem

### Spring Boot for Microservices

```xml
<!-- Core dependencies -->
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>
</dependencies>
```

### Spring Cloud Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Spring Cloud Ecosystem                     │
│                                                              │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐   │
│  │ Spring Cloud │  │ Spring Cloud  │  │ Spring Cloud   │   │
│  │   Gateway    │  │    Config     │  │ Circuit Breaker│   │
│  │(API routing) │  │(centralized)  │  │ (Resilience4j) │   │
│  └──────────────┘  └───────────────┘  └────────────────┘   │
│                                                              │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐   │
│  │ Spring Cloud │  │ Spring Cloud  │  │ Spring Cloud   │   │
│  │   Stream     │  │    Sleuth     │  │  Kubernetes    │   │
│  │(messaging)   │  │(tracing→OTel)│  │(K8s native)    │   │
│  └──────────────┘  └───────────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### Spring Cloud Gateway

```yaml
spring:
  cloud:
    gateway:
      routes:
      - id: order-service
        uri: lb://order-service
        predicates:
        - Path=/api/orders/**
        filters:
        - StripPrefix=1
        - name: CircuitBreaker
          args:
            name: orderCB
            fallbackUri: forward:/fallback/orders
        - name: RequestRateLimiter
          args:
            redis-rate-limiter.replenishRate: 10
            redis-rate-limiter.burstCapacity: 20
```

#### Spring Cloud Config

```yaml
# Config server
spring:
  cloud:
    config:
      server:
        git:
          uri: https://github.com/org/config-repo
          default-label: main

# Client bootstrap
spring:
  config:
    import: configserver:http://config-server:8888
  application:
    name: order-service
  profiles:
    active: production
```

#### Spring Cloud Circuit Breaker (Resilience4j)

```java
@CircuitBreaker(name = "paymentService", fallbackMethod = "paymentFallback")
@Retry(name = "paymentService")
@TimeLimiter(name = "paymentService")
public CompletableFuture<Payment> processPayment(Order order) {
    return CompletableFuture.supplyAsync(() ->
        paymentClient.charge(order));
}

public CompletableFuture<Payment> paymentFallback(Order order, Throwable t) {
    return CompletableFuture.completedFuture(Payment.pending(order));
}
```

```yaml
resilience4j:
  circuitbreaker:
    instances:
      paymentService:
        slidingWindowSize: 10
        failureRateThreshold: 50
        waitDurationInOpenState: 30s
        permittedNumberOfCallsInHalfOpenState: 3
  retry:
    instances:
      paymentService:
        maxAttempts: 3
        waitDuration: 1s
        exponentialBackoffMultiplier: 2
  timelimiter:
    instances:
      paymentService:
        timeoutDuration: 5s
```

#### Spring Cloud Stream

```java
@Bean
public Function<Order, ShipmentRequest> processOrder() {
    return order -> new ShipmentRequest(order.getId(), order.getAddress());
}

// application.yml
// spring.cloud.stream.bindings.processOrder-in-0.destination=orders
// spring.cloud.stream.bindings.processOrder-out-0.destination=shipments
```

### Micronaut

```java
@Controller("/orders")
public class OrderController {
    @Get("/{id}")
    public Order getOrder(String id) {
        return orderService.find(id);
    }
}
// Compile-time DI - no reflection
// Startup: ~100ms, Memory: ~50MB
```

**Key advantages:**
- Compile-time dependency injection (no reflection)
- AOT (Ahead of Time) compilation
- ~10x faster startup than Spring Boot
- ~50% less memory

### Quarkus

```java
@Path("/orders")
@ApplicationScoped
public class OrderResource {
    @GET
    @Path("/{id}")
    @Produces(MediaType.APPLICATION_JSON)
    public Order getOrder(@PathParam("id") String id) {
        return Order.findById(id);
    }
}
// Native binary: startup <50ms, memory ~12MB
```

```bash
# Build native image
./mvnw package -Pnative
# Result: single binary, 12MB memory, 10ms startup
```

### Helidon

Oracle's microservices framework with two programming models:
- **Helidon SE**: Reactive, functional style
- **Helidon MP**: MicroProfile standard (Jakarta EE compatible)

---

## Messaging and Streaming

### Comparison Matrix

| System | Model | Ordering | Retention | Throughput | Best For |
|--------|-------|----------|-----------|------------|----------|
| **Kafka** | Log-based | Per partition | Configurable (forever) | Very high | Event streaming, event sourcing |
| **RabbitMQ** | Queue/Exchange | Per queue | Until consumed | Moderate | Task queues, RPC |
| **Pulsar** | Log-based | Per partition | Tiered storage | Very high | Multi-tenant, geo-replication |
| **NATS** | Pub/Sub | Per subject (JetStream) | Configurable | Very high | Low latency, edge |
| **SQS** | Queue | FIFO available | 14 days max | High | Serverless, simple queuing |
| **Redis Streams** | Log-based | Per stream | Memory-limited | Very high | Real-time, ephemeral |

### Apache Kafka

```
┌─────────────────────────────────────────────────────────────┐
│                    Kafka Ecosystem                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │Kafka Brokers │  │Kafka Connect │  │ Schema Registry  │  │
│  │(core)        │  │(integration) │  │ (Avro/Protobuf)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │Kafka Streams │  │    ksqlDB    │  │   MirrorMaker 2  │  │
│  │(processing)  │  │(SQL on Kafka)│  │(replication)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

```java
// Producer
Properties props = new Properties();
props.put("bootstrap.servers", "kafka:9092");
props.put("key.serializer", StringSerializer.class);
props.put("value.serializer", KafkaAvroSerializer.class);
props.put("acks", "all");
props.put("enable.idempotence", true);

Producer<String, Order> producer = new KafkaProducer<>(props);
producer.send(new ProducerRecord<>("orders", order.getId(), order));

// Consumer
Properties consumerProps = new Properties();
consumerProps.put("group.id", "order-processor");
consumerProps.put("enable.auto.commit", false);
consumerProps.put("isolation.level", "read_committed");

Consumer<String, Order> consumer = new KafkaConsumer<>(consumerProps);
consumer.subscribe(List.of("orders"));
while (true) {
    ConsumerRecords<String, Order> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, Order> record : records) {
        processOrder(record.value());
    }
    consumer.commitSync();
}
```

**Key concepts:**
- Topics with partitions for parallelism
- Consumer groups for horizontal scaling
- Exactly-once semantics (EOS) with transactions
- Log compaction for latest-value retention
- Kafka Connect for CDC and integration

### RabbitMQ

```
┌──────────┐    ┌──────────────┐    ┌─────────┐    ┌──────────┐
│ Producer │───►│   Exchange   │───►│  Queue  │───►│ Consumer │
└──────────┘    │(direct/topic/│    └─────────┘    └──────────┘
                │ fanout/headers)│    ┌─────────┐    ┌──────────┐
                │              │───►│  Queue  │───►│ Consumer │
                └──────────────┘    └─────────┘    └──────────┘
```

```python
# Publisher
import pika
connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
channel = connection.channel()
channel.exchange_declare(exchange='orders', exchange_type='topic')
channel.basic_publish(
    exchange='orders',
    routing_key='order.created',
    body=json.dumps(order),
    properties=pika.BasicProperties(delivery_mode=2)  # persistent
)

# Consumer
channel.queue_declare(queue='payment-processor', durable=True)
channel.queue_bind(queue='payment-processor', exchange='orders', routing_key='order.created')
channel.basic_qos(prefetch_count=10)
channel.basic_consume(queue='payment-processor', on_message_callback=process_payment)
```

**Best for:** Task queues, RPC patterns, complex routing, message acknowledgment.

### Apache Pulsar

**Key differentiators from Kafka:**
- Separation of compute (brokers) and storage (BookKeeper)
- Multi-tenancy built-in (tenants/namespaces)
- Geo-replication native
- Tiered storage (offload to S3)
- Unified queuing + streaming model
- Schema registry built-in

### NATS / NATS JetStream

```go
// NATS Core (at-most-once)
nc, _ := nats.Connect("nats://localhost:4222")
nc.Publish("orders.created", data)
nc.Subscribe("orders.created", func(m *nats.Msg) {
    processOrder(m.Data)
})

// JetStream (at-least-once, persistence)
js, _ := nc.JetStream()
js.AddStream(&nats.StreamConfig{
    Name:     "ORDERS",
    Subjects: []string{"orders.>"},
    Storage:  nats.FileStorage,
    Retention: nats.WorkQueuePolicy,
})
js.Publish("orders.created", data)
```

**Best for:** Low latency (<1ms), edge computing, IoT, lightweight messaging.

### Cloud Messaging Services

| Service | Provider | Best For |
|---------|----------|----------|
| **SQS/SNS** | AWS | Serverless, decoupling, fan-out |
| **Azure Service Bus** | Azure | Enterprise messaging, sessions, transactions |
| **Google Pub/Sub** | GCP | Global messaging, analytics pipelines |

---

## Databases

### Database Selection Guide

```
┌─────────────────────────────────────────────────────────────┐
│              Database Selection Decision Tree                 │
│                                                              │
│  Need ACID transactions?                                    │
│  ├─ Yes → Need horizontal scale?                           │
│  │        ├─ Yes → CockroachDB, TiDB, Spanner             │
│  │        └─ No → PostgreSQL, MySQL                         │
│  └─ No → What's the access pattern?                        │
│           ├─ Key-Value → Redis, DynamoDB                    │
│           ├─ Document → MongoDB                             │
│           ├─ Wide-column (high write) → Cassandra, ScyllaDB│
│           ├─ Search/text → Elasticsearch, OpenSearch        │
│           ├─ Time-series → TimescaleDB, InfluxDB           │
│           ├─ Graph → Neo4j, Neptune                         │
│           └─ Analytics → ClickHouse, BigQuery              │
└─────────────────────────────────────────────────────────────┘
```

### PostgreSQL

```sql
-- Extensions for microservices
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Fuzzy search
CREATE EXTENSION IF NOT EXISTS "hstore";         -- Key-value in column

-- Citus (distributed PostgreSQL)
SELECT create_distributed_table('orders', 'customer_id');

-- TimescaleDB (time-series)
SELECT create_hypertable('metrics', 'timestamp');
```

**Key features:** JSONB support, full-text search, extensions, MVCC, streaming replication, logical replication.
**Best for:** General purpose OLTP, complex queries, strong consistency requirements.

### MongoDB

```javascript
// Document model - flexible schema
db.orders.insertOne({
  _id: ObjectId(),
  customerId: "cust-123",
  items: [
    { productId: "prod-1", quantity: 2, price: 29.99 }
  ],
  status: "pending",
  metadata: { source: "web", campaign: "summer-sale" }
});

// Aggregation pipeline
db.orders.aggregate([
  { $match: { status: "completed" } },
  { $group: { _id: "$customerId", total: { $sum: "$amount" } } },
  { $sort: { total: -1 } }
]);
```

**Best for:** Flexible schemas, document-oriented data, rapid prototyping, content management.

### Apache Cassandra

```cql
-- Designed for write-heavy, partition-key access
CREATE TABLE orders (
    customer_id UUID,
    order_date TIMESTAMP,
    order_id UUID,
    total DECIMAL,
    items LIST<FROZEN<item_type>>,
    PRIMARY KEY ((customer_id), order_date, order_id)
) WITH CLUSTERING ORDER BY (order_date DESC);

-- Reads must include partition key
SELECT * FROM orders WHERE customer_id = ? AND order_date > ?;
```

**Best for:** High write throughput, time-series, geo-distributed, no single point of failure.

### Redis

```bash
# Data structures
SET user:123:session "token-abc" EX 3600
HSET order:456 status "processing" total "99.99"
LPUSH notifications:user:123 "Order shipped"
ZADD leaderboard 1000 "player1"

# Streams (event log)
XADD orders * customer_id "123" product "widget"
XREADGROUP GROUP processors consumer1 COUNT 10 BLOCK 5000 STREAMS orders >
```

**Best for:** Caching, session store, rate limiting, real-time leaderboards, pub/sub.

### Elasticsearch / OpenSearch

```json
// Index a document
PUT /orders/_doc/1
{
  "customer": "John Doe",
  "items": ["laptop", "mouse"],
  "total": 1299.99,
  "timestamp": "2024-01-15T10:30:00Z"
}

// Full-text search with aggregations
GET /orders/_search
{
  "query": {
    "bool": {
      "must": [{ "match": { "items": "laptop" } }],
      "filter": [{ "range": { "total": { "gte": 100 } } }]
    }
  },
  "aggs": {
    "avg_total": { "avg": { "field": "total" } }
  }
}
```

**Best for:** Full-text search, log analytics, product search, real-time dashboards.

### CockroachDB

Distributed SQL database with PostgreSQL compatibility:
- Survives zone/region failures automatically
- Serializable isolation by default
- Horizontal scaling with automatic sharding
- PostgreSQL wire protocol compatible

**Best for:** Global applications needing strong consistency with horizontal scale.

### ClickHouse

```sql
-- Columnar storage, extremely fast analytics
CREATE TABLE events (
    timestamp DateTime,
    user_id UInt64,
    event_type String,
    properties String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event_type, timestamp);

-- Billions of rows in seconds
SELECT event_type, count(), avg(duration)
FROM events
WHERE timestamp > now() - INTERVAL 1 HOUR
GROUP BY event_type;
```

**Best for:** Real-time analytics, log analysis, time-series aggregations, OLAP.

### DynamoDB

```python
# Serverless, pay-per-request
import boto3
table = boto3.resource('dynamodb').Table('Orders')

# Single-table design
table.put_item(Item={
    'PK': f'CUSTOMER#{customer_id}',
    'SK': f'ORDER#{order_id}',
    'total': Decimal('99.99'),
    'status': 'pending'
})

# Query by partition key
response = table.query(
    KeyConditionExpression=Key('PK').eq(f'CUSTOMER#{customer_id}')
)
```

**Best for:** Serverless workloads, predictable latency at any scale, simple access patterns.

---

## Infrastructure and DevOps

### Kubernetes Managed Services

| Service | Provider | Differentiator |
|---------|----------|---------------|
| **EKS** | AWS | Deep AWS integration, Fargate support |
| **GKE** | GCP | Autopilot mode, most mature |
| **AKS** | Azure | Azure AD integration, virtual nodes |

### Infrastructure as Code

```hcl
# Terraform - EKS cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "microservices-prod"
  cluster_version = "1.28"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    default = {
      min_size     = 3
      max_size     = 10
      desired_size = 5
      instance_types = ["m6i.xlarge"]
    }
  }
}
```

| Tool | Language | State | Best For |
|------|----------|-------|----------|
| **Terraform** | HCL | Remote (S3, TFC) | Multi-cloud, mature ecosystem |
| **Pulumi** | TypeScript/Python/Go | Managed | Developers preferring real code |
| **CDK** | TypeScript/Python | CloudFormation | AWS-only, developer-friendly |

### GitOps (ArgoCD / Flux)

```yaml
# ArgoCD Application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: order-service
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/k8s-manifests
    targetRevision: main
    path: services/order-service/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

### Helm / Kustomize

```yaml
# Kustomize overlay (production)
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
- ../../base
patchesStrategicMerge:
- deployment-patch.yaml
configMapGenerator:
- name: app-config
  literals:
  - ENV=production
  - LOG_LEVEL=warn
images:
- name: my-app
  newTag: v2.1.0
replicas:
- name: my-app
  count: 5
```

### HashiCorp Vault

```bash
# Dynamic secrets
vault secrets enable database
vault write database/config/postgres \
    plugin_name=postgresql-database-plugin \
    connection_url="postgresql://{{username}}:{{password}}@postgres:5432/mydb" \
    allowed_roles="readonly"

vault write database/roles/readonly \
    db_name=postgres \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    default_ttl="1h" \
    max_ttl="24h"
```

---

## Observability Stack

### The Three Pillars

```
┌─────────────────────────────────────────────────────────────┐
│                    Observability                              │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Metrics    │  │    Logs      │  │    Traces        │  │
│  │ (Prometheus) │  │ (ELK/Loki)  │  │ (Jaeger/Tempo)   │  │
│  │              │  │              │  │                    │  │
│  │ "What is     │  │ "What       │  │ "What path did   │  │
│  │  happening?" │  │  happened?" │  │  the request      │  │
│  │              │  │              │  │  take?"           │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  Unified with: OpenTelemetry                                │
└─────────────────────────────────────────────────────────────┘
```

### Prometheus + Grafana + Alertmanager

```yaml
# Prometheus scrape config
scrape_configs:
- job_name: 'kubernetes-pods'
  kubernetes_sd_configs:
  - role: pod
  relabel_configs:
  - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
    action: keep
    regex: true

# Alert rule
groups:
- name: microservices
  rules:
  - alert: HighErrorRate
    expr: |
      sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
      /
      sum(rate(http_requests_total[5m])) by (service)
      > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate on {{ $labels.service }}"
```

### ELK/EFK Stack

```
┌─────────────────────────────────────────────────┐
│  EFK Stack (Kubernetes)                          │
│                                                  │
│  App → Fluentd/Fluent Bit → Elasticsearch       │
│              (DaemonSet)       → Kibana          │
│                                                  │
│  Alternative: Loki (Grafana) - log labels only  │
│  App → Promtail → Loki → Grafana               │
└─────────────────────────────────────────────────┘
```

### OpenTelemetry

```java
// Auto-instrumentation (Java agent)
// java -javaagent:opentelemetry-javaagent.jar -jar myapp.jar

// Manual instrumentation
Tracer tracer = GlobalOpenTelemetry.getTracer("order-service");
Span span = tracer.spanBuilder("processOrder").startSpan();
try (Scope scope = span.makeCurrent()) {
    span.setAttribute("order.id", orderId);
    processOrder(orderId);
} catch (Exception e) {
    span.setStatus(StatusCode.ERROR);
    span.recordException(e);
} finally {
    span.end();
}
```

```yaml
# OpenTelemetry Collector config
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

exporters:
  prometheus:
    endpoint: 0.0.0.0:8889
  jaeger:
    endpoint: jaeger:14250
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [loki]
```

### Commercial Observability

| Tool | Strength | Pricing Model |
|------|----------|--------------|
| **Datadog** | All-in-one, great UX | Per host + ingestion |
| **New Relic** | Full stack, generous free tier | Per GB ingested |
| **Dynatrace** | AI-powered, auto-discovery | Per host |
| **Honeycomb** | High-cardinality exploration | Per event |
| **Grafana Cloud** | Open-source based, flexible | Per metric/log/trace |

---

## API Tools

### API Gateways

| Gateway | Type | Best For |
|---------|------|----------|
| **Kong** | Open source / Enterprise | Plugin ecosystem, Lua extensions |
| **Envoy** | Proxy (building block) | Service mesh, high performance |
| **Traefik** | Cloud-native | Auto-discovery, Let's Encrypt |
| **AWS API Gateway** | Managed | Serverless, AWS integration |
| **Apigee** | Enterprise | API management, monetization |
| **APISIX** | Open source | Dynamic, plugin-based |

### gRPC + Protocol Buffers

```protobuf
// order.proto
syntax = "proto3";
package order;

service OrderService {
  rpc CreateOrder(CreateOrderRequest) returns (OrderResponse);
  rpc GetOrder(GetOrderRequest) returns (OrderResponse);
  rpc StreamOrders(StreamOrdersRequest) returns (stream OrderResponse);
}

message CreateOrderRequest {
  string customer_id = 1;
  repeated OrderItem items = 2;
}

message OrderItem {
  string product_id = 1;
  int32 quantity = 2;
  double price = 3;
}

message OrderResponse {
  string order_id = 1;
  string status = 2;
  google.protobuf.Timestamp created_at = 3;
}
```

**When to use gRPC:**
- Service-to-service communication (internal)
- High-performance requirements (HTTP/2, binary)
- Streaming (server, client, bidirectional)
- Strong typing with code generation
- Polyglot environments

### GraphQL

```graphql
# Schema
type Order {
  id: ID!
  customer: Customer!
  items: [OrderItem!]!
  total: Float!
  status: OrderStatus!
}

type Query {
  order(id: ID!): Order
  orders(customerId: ID!, status: OrderStatus): [Order!]!
}

type Mutation {
  createOrder(input: CreateOrderInput!): Order!
}

type Subscription {
  orderStatusChanged(orderId: ID!): Order!
}
```

**When to use GraphQL:**
- Frontend-driven APIs (BFF pattern)
- Multiple clients needing different data shapes
- Reducing over-fetching/under-fetching
- Rapid frontend iteration

### AsyncAPI

```yaml
asyncapi: '2.6.0'
info:
  title: Order Events
  version: '1.0.0'
channels:
  orders/created:
    publish:
      message:
        payload:
          type: object
          properties:
            orderId:
              type: string
            customerId:
              type: string
            total:
              type: number
```

---

## Testing Tools

### Testing Pyramid for Microservices

```
          ┌─────────────┐
         /│   E2E Tests  │\        Few, expensive
        / │  (Playwright) │ \
       /  └───────────────┘  \
      /  ┌─────────────────┐  \
     /   │ Contract Tests   │   \    Medium
    /    │    (Pact)        │    \
   /     └─────────────────┘     \
  /    ┌───────────────────────┐  \
 /     │  Integration Tests     │   \  More
/      │  (TestContainers)      │    \
───────┼────────────────────────┼─────
       │     Unit Tests         │      Many, fast
       │   (JUnit, Jest)        │
       └────────────────────────┘
```

### TestContainers (Integration Testing)

```java
@Testcontainers
@SpringBootTest
class OrderServiceIT {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
        .withDatabaseName("orders");

    @Container
    static KafkaContainer kafka = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.5.0"));

    @DynamicPropertySource
    static void configure(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.kafka.bootstrap-servers", kafka::getBootstrapServers);
    }

    @Test
    void shouldCreateOrder() {
        // Full integration test with real DB and Kafka
    }
}
```

### Pact (Contract Testing)

```javascript
// Consumer test (frontend defines contract)
const interaction = {
  state: 'an order exists',
  uponReceiving: 'a request for order 123',
  withRequest: { method: 'GET', path: '/orders/123' },
  willRespondWith: {
    status: 200,
    body: { id: '123', status: like('pending') }
  }
};

// Provider verification (backend verifies contract)
// Runs automatically in CI - ensures both sides agree
```

### Load Testing

```javascript
// k6 load test
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },   // ramp up
    { duration: '5m', target: 100 },   // steady
    { duration: '2m', target: 500 },   // spike
    { duration: '2m', target: 0 },     // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],   // 95% under 500ms
    http_req_failed: ['rate<0.01'],     // <1% errors
  },
};

export default function () {
  const res = http.get('http://api.example.com/orders');
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1);
}
```

### Chaos Testing

| Tool | Type | Best For |
|------|------|----------|
| **Chaos Monkey** | Random instance termination | Netflix-style resilience |
| **Litmus** | Kubernetes-native chaos | K8s pod/node failures |
| **Gremlin** | Enterprise chaos platform | Controlled experiments |
| **Chaos Mesh** | CNCF, K8s-native | Network, I/O, time chaos |
| **Toxiproxy** | Network condition simulation | Development/CI testing |

---

## Cloud-Native Platforms

### AWS Microservices

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Microservices                          │
│                                                              │
│  Compute:    ECS Fargate | EKS | Lambda                     │
│  API:        API Gateway | ALB                               │
│  Messaging:  SQS | SNS | EventBridge | Kinesis             │
│  Database:   RDS | DynamoDB | ElastiCache                   │
│  Orchestration: Step Functions                               │
│  Service Mesh: App Mesh | EKS + Istio                       │
│  Observability: CloudWatch | X-Ray | OpenSearch             │
│  Secrets:    Secrets Manager | Parameter Store               │
│  CI/CD:      CodePipeline | CodeBuild | CodeDeploy          │
└─────────────────────────────────────────────────────────────┘
```

### Azure Microservices

```
┌─────────────────────────────────────────────────────────────┐
│                   Azure Microservices                         │
│                                                              │
│  Compute:    AKS | Container Apps | Functions               │
│  API:        API Management | Application Gateway           │
│  Messaging:  Service Bus | Event Hubs | Event Grid          │
│  Database:   Azure SQL | Cosmos DB | Redis Cache            │
│  Orchestration: Durable Functions | Logic Apps              │
│  Service Mesh: AKS + Istio | Open Service Mesh             │
│  Observability: Monitor | App Insights | Log Analytics      │
│  Secrets:    Key Vault                                       │
│  CI/CD:      Azure DevOps | GitHub Actions                  │
└─────────────────────────────────────────────────────────────┘
```

### GCP Microservices

```
┌─────────────────────────────────────────────────────────────┐
│                   GCP Microservices                           │
│                                                              │
│  Compute:    GKE | Cloud Run | Cloud Functions              │
│  API:        Apigee | Cloud Endpoints                       │
│  Messaging:  Pub/Sub | Cloud Tasks                          │
│  Database:   Cloud SQL | Firestore | Spanner | Bigtable    │
│  Orchestration: Workflows                                    │
│  Service Mesh: GKE + Anthos Service Mesh (Istio)           │
│  Observability: Cloud Monitoring | Cloud Trace | Logging   │
│  Secrets:    Secret Manager                                  │
│  CI/CD:      Cloud Build | Cloud Deploy                     │
└─────────────────────────────────────────────────────────────┘
```

### Platform Comparison

| Capability | AWS | Azure | GCP |
|-----------|-----|-------|-----|
| **Serverless containers** | Fargate | Container Apps | Cloud Run |
| **Managed K8s** | EKS | AKS | GKE (best) |
| **Serverless functions** | Lambda | Functions | Cloud Functions |
| **Event streaming** | Kinesis | Event Hubs | Pub/Sub |
| **Managed DB (SQL)** | Aurora | Azure SQL | Cloud Spanner |
| **Managed DB (NoSQL)** | DynamoDB | Cosmos DB | Firestore |
| **Workflow** | Step Functions | Durable Functions | Workflows |

---

## Emerging Technologies

### Dapr (Distributed Application Runtime)

```
┌─────────────────────────────────────────────────────────────┐
│                         Dapr                                  │
│                                                              │
│  Your App ←→ Dapr Sidecar ←→ Components (pluggable)        │
│                                                              │
│  Building Blocks:                                           │
│  • Service invocation (with mTLS)                           │
│  • State management (Redis, Cosmos, DynamoDB)               │
│  • Pub/sub (Kafka, RabbitMQ, Pub/Sub)                      │
│  • Bindings (input/output triggers)                         │
│  • Secrets (Vault, K8s secrets, Key Vault)                 │
│  • Configuration                                            │
│  • Distributed lock                                         │
│  • Workflows                                                │
└─────────────────────────────────────────────────────────────┘
```

```yaml
# Dapr component - state store
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.redis
  version: v1
  metadata:
  - name: redisHost
    value: redis:6379
```

```python
# Using Dapr SDK
from dapr.clients import DaprClient

with DaprClient() as d:
    # State management
    d.save_state("statestore", "order-123", json.dumps(order))

    # Service invocation
    resp = d.invoke_method("payment-service", "charge", data=json.dumps(charge))

    # Pub/sub
    d.publish_event("pubsub", "orders", json.dumps(order))
```

**Best for:** Simplifying microservices without framework lock-in, multi-language teams, portable across cloud/edge.

### WebAssembly (Wasm) for Microservices

- **Near-native performance** with sandboxed execution
- **Language-agnostic**: Compile Rust, Go, C++ to Wasm
- **Cold start < 1ms** (vs ~100ms containers)
- **Tiny binaries** (~1MB vs 50MB+ containers)
- **Security**: Memory-safe sandboxing

**Use cases:**
- Edge computing (Cloudflare Workers, Fastly Compute)
- Plugin systems in microservices
- Serverless functions with minimal overhead
- Envoy proxy filters (Wasm extensions)

### eBPF for Networking and Observability

```
┌────────────────────────────────────────────────────────┐
│                    eBPF                                  │
│                                                         │
│  Programs that run in the Linux kernel safely           │
│                                                         │
│  Use in microservices:                                  │
│  • Cilium: networking without iptables (10x faster)    │
│  • Pixie: auto-instrumentation without code changes    │
│  • Falco: runtime security monitoring                  │
│  • Hubble: network observability                       │
│                                                         │
│  Benefits:                                              │
│  • No sidecar needed (kernel-level)                    │
│  • Zero application changes                            │
│  • Minimal performance overhead                        │
│  • Deep visibility into system calls                   │
└────────────────────────────────────────────────────────┘
```

### Serverless Containers

| Service | Provider | Key Feature |
|---------|----------|-------------|
| **Fargate** | AWS | ECS/EKS without managing nodes |
| **Cloud Run** | GCP | Scale to zero, pay per request |
| **Container Apps** | Azure | Dapr built-in, KEDA scaling |

**Best for:** Variable traffic, cost optimization, teams not wanting to manage infrastructure.

### AI/ML in Microservices

```
┌─────────────────────────────────────────────────────────────┐
│              ML in Microservices Architecture                 │
│                                                              │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Feature   │  │Model Serving │  │  Model Training  │   │
│  │   Store    │  │  (online)    │  │   Pipeline       │   │
│  │(Feast,     │  │(Seldon,      │  │(Kubeflow,        │   │
│  │ Tecton)    │  │ KServe,      │  │ MLflow)          │   │
│  │            │  │ Triton)      │  │                   │   │
│  └────────────┘  └──────────────┘  └──────────────────┘   │
│                                                              │
│  Patterns:                                                  │
│  • Model-as-a-service (separate microservice)              │
│  • Embedded model (in-process inference)                   │
│  • A/B testing models via traffic splitting                │
│  • Shadow mode (mirror traffic to new model)              │
│  • Feature flags for model rollout                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Selection Framework

### Decision Criteria

1. **Team expertise**: Don't choose bleeding-edge if team can't support it
2. **Operational maturity**: Consider monitoring, debugging, hiring
3. **Scale requirements**: Right-size technology to actual (not projected) needs
4. **Ecosystem**: Libraries, community, support, documentation
5. **Total cost of ownership**: License + infrastructure + engineering time
6. **Lock-in risk**: How hard is it to migrate away?
7. **Production readiness**: Battle-tested > bleeding edge

### Recommended Starting Stack

| Layer | Recommendation | Why |
|-------|---------------|-----|
| Language | Go or Java (Spring Boot) | Ecosystem, hiring, performance |
| API | REST + gRPC (internal) | Simplicity + performance |
| Messaging | Kafka | Event sourcing, replay, ecosystem |
| Database | PostgreSQL + Redis | Versatile + fast caching |
| Infrastructure | Kubernetes (managed) | Industry standard |
| CI/CD | GitHub Actions + ArgoCD | GitOps, widely adopted |
| Observability | OpenTelemetry + Grafana stack | Vendor-neutral, cost-effective |
| Service Mesh | Start without, add Linkerd when needed | Simplicity first |

### Maturity-Based Adoption

```
Phase 1 (< 5 services): Basic stack
  → Monorepo, shared DB OK, simple deployment

Phase 2 (5-20 services): Core infrastructure
  → Kubernetes, Kafka, separate DBs, CI/CD

Phase 3 (20-50 services): Platform investment
  → Service mesh, OpenTelemetry, platform team

Phase 4 (50+ services): Full platform
  → Internal developer platform, self-service, automation
```
