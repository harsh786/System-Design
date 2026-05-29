# Inter-Service Communication Patterns

---

## 1. Synchronous Communication

### 1.1 Request/Response (REST, gRPC, GraphQL)

**Problem:** Services need to exchange data in real-time with immediate confirmation.

**Solution:** Client sends a request and blocks (or awaits) until the server responds.

```
┌────────┐         ┌────────┐
│Client  │──req──▶│Service │
│        │◀──res──│        │
└────────┘         └────────┘
```

**REST Example:**
```python
# Python - FastAPI service
@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    return {"id": order_id, "status": "shipped"}

# Client call
import httpx
resp = await httpx.AsyncClient().get("http://order-service/orders/123")
```

**gRPC Example:**
```protobuf
service OrderService {
  rpc GetOrder(OrderRequest) returns (OrderResponse);
}
```

**GraphQL Example:**
```graphql
query {
  order(id: "123") { id status items { name qty } }
}
```

| Pros | Cons |
|------|------|
| Simple mental model | Temporal coupling |
| Immediate consistency | Cascading failures |
| Easy debugging | Latency accumulates |

**When to use:** Queries requiring immediate response, simple CRUD, low-latency reads.

---

### 1.2 Remote Procedure Call (RPC)

**Problem:** Calling remote services should feel like calling local functions.

**Solution:** Use an RPC framework that generates client stubs from an IDL (Interface Definition Language).

```
┌────────┐    stub     ┌────────┐    skeleton   ┌────────┐
│Caller  │───────────▶│Network │──────────────▶│Callee  │
│        │◀───────────│        │◀──────────────│        │
└────────┘             └────────┘               └────────┘
```

```go
// gRPC Go client
conn, _ := grpc.Dial("order-service:50051", grpc.WithInsecure())
client := pb.NewOrderServiceClient(conn)
resp, err := client.GetOrder(ctx, &pb.OrderRequest{Id: "123"})
```

| Pros | Cons |
|------|------|
| Strongly typed contracts | Tight coupling to IDL |
| High performance (binary) | Harder to debug on wire |
| Code generation | Version management complexity |

**When to use:** Internal service-to-service calls where performance matters, polyglot environments needing strict contracts.

---

### 1.3 API Gateway Pattern

**Problem:** Clients must call multiple microservices; managing cross-cutting concerns (auth, rate limiting, routing) is duplicated.

**Solution:** Single entry point that routes, aggregates, and applies policies.

```
┌──────┐       ┌───────────┐       ┌──────────┐
│Client│──────▶│API Gateway│──────▶│Service A │
│      │       │           │──────▶│Service B │
│      │◀──────│           │──────▶│Service C │
└──────┘       └───────────┘       └──────────┘
```

```yaml
# Kong/nginx-style config
routes:
  - path: /api/orders
    service: order-service
    plugins: [rate-limiting, jwt-auth, cors]
  - path: /api/users
    service: user-service
```

| Pros | Cons |
|------|------|
| Single entry point | Single point of failure |
| Cross-cutting concerns centralized | Additional latency hop |
| Response aggregation | Can become a bottleneck |
| Protocol translation | Deployment coupling risk |

**When to use:** Public-facing APIs, mobile/web clients needing aggregated responses, enforcing security at the edge.

---

### 1.4 Backend for Frontend (BFF)

**Problem:** Different clients (web, mobile, IoT) need different API shapes and aggregations.

**Solution:** Dedicated backend per frontend type, each tailored to that client's needs.

```
┌───────┐     ┌─────────┐
│Web App│────▶│Web BFF  │───┐
└───────┘     └─────────┘   │    ┌──────────┐
                             ├───▶│Services  │
┌───────┐     ┌─────────┐   │    └──────────┘
│Mobile │────▶│Mobile   │───┘
│  App  │     │  BFF    │
└───────┘     └─────────┘
```

```typescript
// Mobile BFF - returns minimal payload
app.get('/api/orders/:id', async (req, res) => {
  const order = await orderService.get(req.params.id);
  res.json({ id: order.id, status: order.status }); // slim response
});

// Web BFF - returns rich payload
app.get('/api/orders/:id', async (req, res) => {
  const [order, user, tracking] = await Promise.all([
    orderService.get(req.params.id),
    userService.get(order.userId),
    trackingService.get(order.trackingId),
  ]);
  res.json({ ...order, user, tracking }); // full response
});
```

| Pros | Cons |
|------|------|
| Optimized per client | More services to maintain |
| Independent deployability per frontend | Code duplication across BFFs |
| Teams own their BFF | Consistency challenges |

**When to use:** Multiple client types with divergent needs, separate frontend teams.

---

### 1.5 Service-to-Service Direct Calls

**Problem:** One service needs data from another during request processing.

**Solution:** Direct HTTP/gRPC call using service discovery.

```
┌─────────┐    GET /users/42    ┌─────────┐
│Order Svc│────────────────────▶│User Svc │
│         │◀────────────────────│         │
└─────────┘    {name: "John"}   └─────────┘
```

```java
// Spring WebClient
WebClient client = WebClient.create("http://user-service");
Mono<User> user = client.get()
    .uri("/users/{id}", userId)
    .retrieve()
    .bodyToMono(User.class);
```

| Pros | Cons |
|------|------|
| Simple | Runtime dependency |
| Immediate data | Cascading failures |
| No middleware needed | Hard to trace in complex graphs |

**When to use:** Simple service dependencies, data needed synchronously, low fan-out scenarios.

---

### 1.6 Circuit Breaker in Sync Communication

**Problem:** A failing downstream service causes cascading failures and resource exhaustion upstream.

**Solution:** Monitor failures; when threshold is exceeded, "open" the circuit to fail fast without calling the downstream.

```
        ┌─────────────────────────────────────┐
        │          Circuit Breaker            │
        │                                     │
 req ──▶│  CLOSED ──(failures)──▶ OPEN       │
        │    ▲                      │         │
        │    │                   (timeout)    │
        │    │                      ▼         │
        │  CLOSED ◀──(success)── HALF-OPEN   │
        └─────────────────────────────────────┘
```

```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=30)
def call_payment_service(order_id):
    resp = httpx.post(f"http://payment-service/charge", json={"order": order_id})
    resp.raise_for_status()
    return resp.json()

# Usage - throws CircuitBreakerError when open
try:
    result = call_payment_service("order-123")
except CircuitBreakerError:
    return fallback_response()
```

| Pros | Cons |
|------|------|
| Prevents cascade failures | Adds complexity |
| Fails fast | Needs tuning (thresholds) |
| Allows recovery time | Partial failures still possible |

**When to use:** Any synchronous call to an external or unreliable service.

---

### 1.7 Timeouts and Retries

**Problem:** Network calls can hang indefinitely or fail transiently.

**Solution:** Set explicit timeouts; retry with exponential backoff and jitter for transient errors.

```
Client          Service
  │── req ──────▶│
  │   (timeout)  │
  │── retry 1 ──▶│  (after 100ms + jitter)
  │   (timeout)  │
  │── retry 2 ──▶│  (after 200ms + jitter)
  │◀── response ─│
```

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, max=2),
    retry=retry_if_exception_type(httpx.TimeoutException)
)
async def fetch_user(user_id: str):
    async with httpx.AsyncClient(timeout=2.0) as client:
        return await client.get(f"http://user-service/users/{user_id}")
```

**Key principles:**
- Always set timeouts (connect + read)
- Only retry on transient/5xx errors, not 4xx
- Use exponential backoff with jitter to avoid thundering herd
- Set a retry budget (e.g., max 3 attempts)
- Make operations idempotent before retrying

| Pros | Cons |
|------|------|
| Handles transient failures | Can amplify load if misconfigured |
| Improves reliability | Increases latency on failures |
| Simple to implement | Retry storms possible |

**When to use:** Every synchronous network call.

---

### 1.8 Client-Side Load Balancing vs Server-Side

**Problem:** Distributing traffic across service instances.

**Server-Side (L4/L7 Load Balancer):**
```
Client ──▶ [Load Balancer] ──▶ Instance 1
                           ──▶ Instance 2
                           ──▶ Instance 3
```

**Client-Side (Service Registry):**
```
┌────────────────┐
│Service Registry│
└───────┬────────┘
        │ (discover)
┌───────▼────────┐
│Client + LB     │──▶ Instance 1
│(round-robin)   │──▶ Instance 2
└────────────────┘──▶ Instance 3
```

```java
// Spring Cloud LoadBalancer (client-side)
@LoadBalanced
@Bean
public WebClient.Builder webClientBuilder() {
    return WebClient.builder();
}
// Calls automatically distributed
webClient.get().uri("http://order-service/orders").retrieve();
```

| Aspect | Server-Side | Client-Side |
|--------|-------------|-------------|
| Extra hop | Yes | No |
| Client complexity | Low | Higher |
| Stale endpoints | No | Possible |
| Examples | AWS ALB, Nginx, Envoy | Ribbon, gRPC built-in |

**When to use:**
- Server-side: External traffic, simple setup, language-agnostic
- Client-side: Internal service mesh, latency-sensitive, gRPC

---

## 2. Asynchronous Communication

### 2.1 Message Queues (Point-to-Point)

**Problem:** A producer needs to send work to exactly one consumer, decoupled in time.

**Solution:** Messages placed on a queue; one consumer picks up each message.

```
┌────────┐      ┌───────┐      ┌────────┐
│Producer│─────▶│ Queue │─────▶│Consumer│
└────────┘      └───────┘      └────────┘
                                (one consumer per msg)
```

```python
# RabbitMQ with pika
import pika

# Producer
channel.basic_publish(exchange='', routing_key='tasks', body='process-order-123')

# Consumer
def callback(ch, method, properties, body):
    process(body)
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(queue='tasks', on_message_callback=callback)
```

| Pros | Cons |
|------|------|
| Decoupled in time | No broadcast |
| Guaranteed delivery | Queue can become bottleneck |
| Natural backpressure | Message ordering challenges |

**When to use:** Task distribution, work queues, command processing.

---

### 2.2 Publish/Subscribe (Fan-Out)

**Problem:** An event must be delivered to multiple interested consumers.

**Solution:** Publisher sends to a topic/exchange; all subscribers receive a copy.

```
                    ┌────────────┐
               ┌───▶│Subscriber A│
┌────────┐     │    └────────────┘
│Publisher│──▶[Topic]
└────────┘     │    ┌────────────┐
               └───▶│Subscriber B│
                    └────────────┘
```

```python
# Redis Pub/Sub
import redis
r = redis.Redis()

# Publisher
r.publish('order-events', json.dumps({"type": "OrderCreated", "id": "123"}))

# Subscriber
pubsub = r.pubsub()
pubsub.subscribe('order-events')
for message in pubsub.listen():
    handle(message['data'])
```

| Pros | Cons |
|------|------|
| Loose coupling | Message loss if subscriber offline (without persistence) |
| Multiple consumers | Harder to debug |
| Easy to add new subscribers | Ordering across subscribers not guaranteed |

**When to use:** Event notification, broadcasting state changes, decoupled integrations.

---

### 2.3 Event Streaming (Kafka, Pulsar)

**Problem:** Need durable, ordered, replayable stream of events at scale.

**Solution:** Append-only log with consumer offsets; consumers read at their own pace.

```
Producer ──▶ [Topic: Partition 0] ──▶ Consumer Group A
             [Topic: Partition 1] ──▶ Consumer Group A
             [Topic: Partition 2] ──▶ Consumer Group B
                                      (independent offset per group)
```

```java
// Kafka Producer
ProducerRecord<String, String> record =
    new ProducerRecord<>("orders", orderId, orderJson);
producer.send(record);

// Kafka Consumer
while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, String> record : records) {
        process(record.value());
    }
    consumer.commitSync();
}
```

| Pros | Cons |
|------|------|
| Durable, replayable | Operational complexity |
| High throughput | Ordering only within partition |
| Multiple consumer groups | Higher latency than queues |
| Event sourcing friendly | Storage costs at scale |

**When to use:** Event sourcing, audit logs, high-throughput streaming, multi-consumer scenarios.

---

### 2.4 Request/Async Response Pattern

**Problem:** Client needs a response but doesn't want to block.

**Solution:** Send request message with a reply-to address; consumer processes and sends response to that address.

```
┌────────┐   request    ┌───────┐   process   ┌────────┐
│Requester│────────────▶│ Queue │────────────▶│Responder│
│         │             └───────┘              │        │
│         │◀────────────────────────────────────│        │
│         │   response (to reply-to queue)      └────────┘
└─────────┘
```

```python
# RabbitMQ RPC pattern
import uuid

corr_id = str(uuid.uuid4())
channel.basic_publish(
    exchange='',
    routing_key='rpc_queue',
    properties=pika.BasicProperties(
        reply_to='amq.rabbitmq.reply-to',
        correlation_id=corr_id,
    ),
    body=request
)
# Await response on reply queue, match by correlation_id
```

| Pros | Cons |
|------|------|
| Non-blocking | More complex than sync |
| Temporal decoupling | Correlation management |
| Resilient to downtime | Timeout handling needed |

**When to use:** Long-running operations, when you need async but still require a response.

---

### 2.5 Event Notification Pattern

**Problem:** Services need to know something happened, but don't need full details.

**Solution:** Publish a lightweight event (just ID + type); interested services query for details if needed.

```
Order Service ──▶ Event: {type: "OrderPlaced", orderId: "123"}

Shipping Service receives event ──▶ GET /orders/123 (to get full data)
```

```json
{
  "eventType": "OrderPlaced",
  "orderId": "123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Pros | Cons |
|------|------|
| Minimal coupling | Requires callback to source |
| Small message size | Extra network call for details |
| Source controls data access | Source must be available |

**When to use:** When consumers rarely need full data, or data is sensitive and access-controlled.

---

### 2.6 Event-Carried State Transfer

**Problem:** Consumers shouldn't need to call back to the source for data.

**Solution:** Include all relevant state in the event itself; consumers maintain local copies.

```
Order Service ──▶ Event: {
  type: "OrderPlaced",
  orderId: "123",
  customer: { id: "42", name: "John", email: "john@ex.com" },
  items: [ { sku: "A1", qty: 2, price: 29.99 } ],
  total: 59.98
}

Shipping Service: stores locally, no callback needed
```

| Pros | Cons |
|------|------|
| No callback needed | Larger messages |
| Source can be offline | Data duplication |
| Lower latency | Eventual consistency |
| Better autonomy | Schema evolution harder |

**When to use:** When consumers need full data autonomy, high availability requirements, reducing runtime coupling.

---

### 2.7 Domain Events

**Problem:** Expressing something meaningful that happened within a bounded context.

**Solution:** Named past-tense events representing business facts within a domain.

```python
# Domain Event
@dataclass
class OrderPlaced:
    order_id: str
    customer_id: str
    items: list[OrderItem]
    placed_at: datetime

# Publishing within aggregate
class Order:
    def place(self):
        self.status = "placed"
        self._events.append(OrderPlaced(
            order_id=self.id,
            customer_id=self.customer_id,
            items=self.items,
            placed_at=datetime.utcnow()
        ))
```

| Pros | Cons |
|------|------|
| Ubiquitous language | Requires domain modeling |
| Clear business semantics | Event versioning complexity |
| Audit trail | Can proliferate |

**When to use:** Domain-driven design, expressing business-significant occurrences within a bounded context.

---

### 2.8 Integration Events

**Problem:** Communicating across bounded contexts/services.

**Solution:** Events published on a shared bus that cross context boundaries, with explicit contracts.

```
┌─────────────────┐                        ┌──────────────────┐
│ Order Context    │  IntegrationEvent:     │ Shipping Context │
│                  │  OrderPlacedEvent      │                  │
│ Domain Event     │──────────────────────▶│ Handles event    │
│ → published to   │  (shared schema)       │ → creates        │
│   message bus    │                        │   shipment       │
└─────────────────┘                        └──────────────────┘
```

```csharp
// Integration Event (shared contract)
public record OrderPlacedIntegrationEvent(
    Guid OrderId,
    string CustomerId,
    List<OrderItemDto> Items,
    DateTime OccurredAt
);

// Publisher (Order context)
await _eventBus.PublishAsync(new OrderPlacedIntegrationEvent(...));

// Handler (Shipping context)
public class OrderPlacedHandler : IIntegrationEventHandler<OrderPlacedIntegrationEvent>
{
    public async Task Handle(OrderPlacedIntegrationEvent @event)
    {
        await _shipmentService.CreateShipment(@event.OrderId, @event.Items);
    }
}
```

| Pros | Cons |
|------|------|
| Decoupled contexts | Shared schema = coupling point |
| Asynchronous | Eventual consistency |
| Scalable | Versioning needed |

**When to use:** Cross-service communication, inter-team contracts, system integration.

---

### 2.9 Competing Consumers Pattern

**Problem:** Single consumer can't keep up with message volume.

**Solution:** Multiple consumers read from the same queue; each message processed by exactly one.

```
                    ┌──────────┐
               ┌───▶│Consumer 1│
┌───────┐      │    └──────────┘
│ Queue │──────┤
└───────┘      │    ┌──────────┐
               ├───▶│Consumer 2│
               │    └──────────┘
               │    ┌──────────┐
               └───▶│Consumer 3│
                    └──────────┘
```

```python
# Multiple workers consuming from same queue
# Each message delivered to exactly one worker
# Scale by adding more consumer instances

# Kafka: partition-based parallelism
# consumer group with 3 consumers, 3 partitions → 1:1 mapping
```

| Pros | Cons |
|------|------|
| Horizontal scaling | Message ordering lost (across consumers) |
| Natural load distribution | Duplicate processing possible |
| Fault tolerant | Rebalancing overhead |

**When to use:** High-throughput processing, scaling consumers independently, work distribution.

---

### 2.10 Message Broker vs Event Broker

| Aspect | Message Broker | Event Broker |
|--------|---------------|--------------|
| Model | Queue (point-to-point) | Log (append-only) |
| Consumption | Destructive (removed after ack) | Non-destructive (offset-based) |
| Replay | No | Yes |
| Retention | Until consumed | Time/size-based |
| Examples | RabbitMQ, SQS, ActiveMQ | Kafka, Pulsar, EventStoreDB |
| Use case | Task queues, commands | Event sourcing, streaming |

**When to use message broker:** Commands, work distribution, transient messages.
**When to use event broker:** Event sourcing, audit logs, replay, multiple consumers.

---

### 2.11 Dead Letter Queue (DLQ)

**Problem:** Messages that cannot be processed (poison messages) block the queue.

**Solution:** After N failed attempts, move message to a separate DLQ for investigation.

```
┌───────┐     ┌──────────┐     fail x3     ┌─────┐
│ Queue │────▶│Consumer  │────────────────▶│ DLQ │
└───────┘     └──────────┘                  └─────┘
                                               │
                                         (manual review/
                                          reprocessing)
```

```python
# RabbitMQ DLQ setup
channel.queue_declare(queue='orders', arguments={
    'x-dead-letter-exchange': '',
    'x-dead-letter-routing-key': 'orders-dlq',
    'x-message-ttl': 60000,
})
channel.queue_declare(queue='orders-dlq')
```

| Pros | Cons |
|------|------|
| Unblocks main queue | Requires monitoring |
| Preserves failed messages | Manual intervention needed |
| Debugging aid | Can accumulate silently |

**When to use:** Always. Every queue should have a DLQ.

---

### 2.12 Poison Message Handling

**Problem:** A single malformed message causes repeated consumer crashes.

**Solution:** Track delivery count; after threshold, route to DLQ and alert.

```python
def on_message(message):
    delivery_count = message.headers.get('x-delivery-count', 0)
    if delivery_count > 3:
        send_to_dlq(message)
        send_alert(f"Poison message detected: {message.id}")
        return

    try:
        process(message)
        message.ack()
    except TransientError:
        message.nack(requeue=True)
    except PermanentError:
        send_to_dlq(message)
        message.ack()
```

| Pros | Cons |
|------|------|
| Prevents infinite loops | Need retry count tracking |
| System stays healthy | May lose messages if misconfigured |

**When to use:** Whenever consuming from queues with untrusted or complex payloads.

---

### 2.13 Idempotent Consumer Pattern

**Problem:** Messages may be delivered more than once (at-least-once delivery).

**Solution:** Track processed message IDs; skip duplicates.

```
Consumer receives msg(id=abc):
  1. Check: processed_ids contains "abc"?
  2. No → process, store "abc" in processed_ids
  3. Yes → skip (already processed)
```

```python
async def handle_message(message):
    msg_id = message.headers['message-id']

    # Atomic check-and-set
    if not await redis.set(f"processed:{msg_id}", "1", nx=True, ex=86400):
        return  # Already processed

    await process_order(message.body)
    await message.ack()
```

| Pros | Cons |
|------|------|
| Exactly-once semantics | Storage for dedup state |
| Safe retries | TTL management |
| Simple pattern | Distributed dedup is harder |

**When to use:** Any at-least-once delivery system (which is most of them).

---

### 2.14 Message Deduplication

**Problem:** Network issues or retries produce duplicate messages at the broker level.

**Solution:** Broker-level or producer-level deduplication using unique message IDs.

```python
# Kafka: enable.idempotence=true (producer-level dedup)
producer = KafkaProducer(
    enable_idempotence=True,  # Ensures exactly-once per partition
    acks='all',
)

# SQS: Content-based deduplication or explicit MessageDeduplicationId
sqs.send_message(
    QueueUrl=fifo_queue_url,
    MessageBody=payload,
    MessageGroupId="order-123",
    MessageDeduplicationId=hashlib.sha256(payload.encode()).hexdigest()
)
```

| Pros | Cons |
|------|------|
| Prevents duplicates at source | Broker support needed |
| Reduces consumer complexity | Window-based (5 min for SQS FIFO) |

**When to use:** FIFO queues, financial transactions, when combined with idempotent consumers.

---

### 2.15 Outbox Pattern

**Problem:** Need to atomically update a database AND publish an event (dual-write problem).

**Solution:** Write the event to an "outbox" table in the same DB transaction; a separate process publishes it.

```
┌─────────────────────────────────┐
│         Database                │
│  ┌────────┐    ┌─────────────┐ │
│  │ Orders │    │   Outbox    │ │
│  │ table  │    │   table     │ │
│  └────────┘    └──────┬──────┘ │
└───────────────────────┼────────┘
                        │ (poll or CDC)
                        ▼
                 ┌─────────────┐
                 │Message Broker│
                 └─────────────┘
```

```python
# Single transaction
async with db.transaction():
    await db.execute("INSERT INTO orders (...) VALUES (...)")
    await db.execute("""
        INSERT INTO outbox (id, aggregate_type, event_type, payload, created_at)
        VALUES ($1, 'Order', 'OrderPlaced', $2, NOW())
    """, event_id, json.dumps(event_payload))

# Separate publisher process
async def publish_outbox():
    rows = await db.fetch("SELECT * FROM outbox WHERE published = false ORDER BY created_at LIMIT 100")
    for row in rows:
        await broker.publish(row['event_type'], row['payload'])
        await db.execute("UPDATE outbox SET published = true WHERE id = $1", row['id'])
```

| Pros | Cons |
|------|------|
| Atomic consistency | Extra table + process |
| No distributed transactions | Slight delay |
| Reliable delivery | Polling overhead |

**When to use:** Whenever you need to update state AND publish events reliably.

---

### 2.16 Inbox Pattern

**Problem:** Consumer may process the same incoming event multiple times across restarts.

**Solution:** Store incoming message ID in an "inbox" table; process only if not already seen.

```python
async def handle_event(event):
    # Atomic: check inbox + process + mark in single transaction
    async with db.transaction():
        exists = await db.fetchval(
            "SELECT 1 FROM inbox WHERE message_id = $1", event.id
        )
        if exists:
            return  # Already processed

        await db.execute(
            "INSERT INTO inbox (message_id, processed_at) VALUES ($1, NOW())",
            event.id
        )
        await process_business_logic(event)
```

| Pros | Cons |
|------|------|
| Exactly-once processing | Extra table |
| Works with any broker | Needs cleanup/TTL |
| Transactional guarantee | Slight overhead per message |

**When to use:** Consumer side of at-least-once messaging when idempotency via business logic isn't natural.

---

### 2.17 Transactional Outbox

Same as Outbox Pattern (2.15) — the "transactional" prefix emphasizes that the outbox write occurs within the same ACID transaction as the business state change.

**Key implementation detail:** The outbox relay (publisher) must be separate from the application to avoid coupling.

---

### 2.18 Polling Publisher

**Problem:** How to relay messages from the outbox table to the message broker.

**Solution:** A background process polls the outbox table at intervals.

```python
# Polling publisher (runs as separate process/cron)
async def poll_and_publish():
    while True:
        async with db.transaction():
            rows = await db.fetch("""
                SELECT * FROM outbox
                WHERE published = false
                ORDER BY created_at
                LIMIT 50
                FOR UPDATE SKIP LOCKED
            """)
            for row in rows:
                await broker.publish(row['topic'], row['payload'])
                await db.execute("UPDATE outbox SET published = true WHERE id = $1", row['id'])
        await asyncio.sleep(1)  # Poll interval
```

| Pros | Cons |
|------|------|
| Simple to implement | Polling delay (latency) |
| No CDC infrastructure needed | DB load from frequent queries |
| Works with any database | Scaling challenges |

**When to use:** Simple deployments, when CDC is overkill, low-to-medium throughput.

---

### 2.19 Transaction Log Tailing

**Problem:** Polling is inefficient; need real-time capture of DB changes for event publishing.

**Solution:** Read the database's transaction log (WAL/binlog) to capture changes as they're committed.

```
┌──────────┐     WAL/binlog      ┌───────────┐      ┌─────────────┐
│ Database │────────────────────▶│ Log Tailer│─────▶│Message Broker│
│          │                     │(Debezium) │      └─────────────┘
└──────────┘                     └───────────┘
```

```yaml
# Debezium connector config
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "database.hostname": "db-host",
  "database.dbname": "orders",
  "table.include.list": "public.outbox",
  "transforms": "outbox",
  "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter"
}
```

| Pros | Cons |
|------|------|
| Real-time (low latency) | Operational complexity |
| No polling overhead | DB-specific setup |
| Captures all changes | Log format coupling |

**When to use:** High-throughput systems, CDC pipelines, when polling latency is unacceptable.

---

### 2.20 Change Data Capture (CDC)

**Problem:** Need to propagate data changes across systems without modifying application code.

**Solution:** Capture row-level changes from the DB and stream them as events.

```
┌──────────┐  CDC   ┌─────────┐  stream  ┌──────────┐
│ Source DB│───────▶│Debezium │────────▶│  Kafka   │───▶ Consumers
└──────────┘        └─────────┘          └──────────┘
```

**Use cases:**
- Outbox pattern relay
- Data replication
- Cache invalidation
- Search index updates
- Analytics pipelines

| Pros | Cons |
|------|------|
| No app code changes | Infrastructure overhead |
| Complete change history | Schema evolution challenges |
| Real-time | Ordering guarantees vary |

**When to use:** Legacy integration, data sync, materializing views, when you can't modify source code.

---

## 3. Hybrid Patterns

### 3.1 Saga Pattern (Orchestration vs Choreography)

**Problem:** Distributed transaction spanning multiple services — can't use ACID across services.

**Solution:** Sequence of local transactions with compensating actions on failure.

#### Choreography (Event-driven)

```
OrderSvc          PaymentSvc         InventorySvc        ShippingSvc
    │                  │                   │                  │
    │─OrderCreated───▶│                   │                  │
    │                  │─PaymentCharged──▶│                  │
    │                  │                   │─StockReserved──▶│
    │                  │                   │                  │─ShipmentCreated
    │                  │                   │                  │
    │         (On failure: compensate backwards)              │
    │                  │                   │◀─StockFailed─────│
    │                  │◀─RefundIssued─────│                  │
    │◀─OrderCancelled──│                   │                  │
```

```python
# Choreography - each service listens and reacts
class PaymentService:
    @event_handler("OrderCreated")
    async def handle(self, event):
        try:
            await self.charge(event.customer_id, event.total)
            await publish("PaymentCharged", {"order_id": event.order_id})
        except PaymentFailed:
            await publish("PaymentFailed", {"order_id": event.order_id})
```

#### Orchestration (Central coordinator)

```
┌────────────────┐
│  Saga          │
│  Orchestrator  │
└───────┬────────┘
        │
        ├──▶ OrderSvc.create()
        ├──▶ PaymentSvc.charge()
        ├──▶ InventorySvc.reserve()
        ├──▶ ShippingSvc.ship()
        │
        │ (on failure at step 3)
        ├──▶ PaymentSvc.refund()      ← compensate
        └──▶ OrderSvc.cancel()        ← compensate
```

```python
# Orchestration - saga coordinator
class OrderSaga:
    steps = [
        SagaStep(action=create_order, compensation=cancel_order),
        SagaStep(action=charge_payment, compensation=refund_payment),
        SagaStep(action=reserve_stock, compensation=release_stock),
        SagaStep(action=create_shipment, compensation=cancel_shipment),
    ]

    async def execute(self, order_data):
        completed = []
        for step in self.steps:
            try:
                await step.action(order_data)
                completed.append(step)
            except Exception:
                # Compensate in reverse
                for s in reversed(completed):
                    await s.compensation(order_data)
                raise SagaFailed()
```

| Aspect | Choreography | Orchestration |
|--------|-------------|---------------|
| Coupling | Loose | Centralized |
| Complexity | Distributed (hard to track) | Concentrated (easier to follow) |
| Single point of failure | No | Orchestrator |
| Best for | Simple sagas (2-3 steps) | Complex multi-step flows |

**When to use:** Multi-service transactions, order processing, booking systems.

---

### 3.2 Two-Phase Commit (2PC) — Why to Avoid

**Problem:** Need atomic commit across multiple databases/services.

**Solution:** Coordinator asks all participants to prepare, then commit (or abort).

```
Coordinator        Participant A    Participant B
     │── prepare ────▶│                │
     │── prepare ───────────────────▶│
     │◀── vote YES ───│                │
     │◀── vote YES ──────────────────│
     │── commit ─────▶│                │
     │── commit ──────────────────▶│
```

**Why to avoid in microservices:**
- Locks resources during prepare phase (blocking)
- Coordinator is single point of failure
- Network partitions → uncertain state
- Doesn't scale
- Violates service autonomy

| Pros | Cons |
|------|------|
| Strong consistency | Blocking protocol |
| ACID guarantees | Performance killer |
| | Single point of failure |
| | Not partition-tolerant |

**When to use:** Almost never in microservices. Use Sagas instead. Acceptable only within a single database system.

---

### 3.3 Try-Confirm/Cancel (TCC)

**Problem:** Need reservation-style distributed transactions without locks.

**Solution:** Three phases: Try (reserve resources), Confirm (finalize), Cancel (release).

```
Coordinator        Payment           Inventory
     │── TRY ────────▶│(hold $50)       │
     │── TRY ─────────────────────────▶│(reserve 2 items)
     │                 │                 │
     │── CONFIRM ─────▶│(charge $50)     │
     │── CONFIRM ──────────────────────▶│(deduct 2 items)
     │                 │                 │
     │ (or on failure) │                 │
     │── CANCEL ──────▶│(release hold)   │
     │── CANCEL ───────────────────────▶│(unreserve)
```

```python
class PaymentTCC:
    async def try_action(self, order_id, amount):
        # Reserve/hold funds
        await self.hold_funds(order_id, amount)

    async def confirm(self, order_id):
        # Finalize the charge
        await self.capture_hold(order_id)

    async def cancel(self, order_id):
        # Release the hold
        await self.release_hold(order_id)
```

| Pros | Cons |
|------|------|
| No long-held locks | Every service needs 3 operations |
| Business-level protocol | Complex to implement correctly |
| Timeout handling built-in | Try phase can expire |

**When to use:** Financial systems, booking systems, resource reservation with time limits.

---

### 3.4 Compensation Transactions

**Problem:** A completed local transaction needs to be "undone" as part of a saga rollback.

**Solution:** Define a compensating action for each forward action that semantically reverses its effect.

```python
# Compensation is NOT a rollback — it's a new transaction that reverses the effect
compensations = {
    "charge_payment": "refund_payment",
    "reserve_stock": "release_stock",
    "create_shipment": "cancel_shipment",
    "send_email": "send_cancellation_email",  # Can't unsend, but can notify
}

# Key: compensations must be idempotent
async def refund_payment(order_id):
    if not await already_refunded(order_id):
        await payment_gateway.refund(order_id)
        await mark_refunded(order_id)
```

**Key principles:**
- Compensations are semantically opposite, not DB rollbacks
- Must be idempotent (may be retried)
- Some actions can't be perfectly compensated (emails, external APIs)
- Record compensation status for auditability

**When to use:** Always paired with Saga pattern.

---

### 3.5 Request-Reply over Messaging

**Problem:** Need RPC-like semantics but over asynchronous messaging.

**Solution:** Include reply-to destination and correlation ID in request message.

```
┌──────────┐   request (correlation: X,    ┌──────────┐
│Requester │   reply-to: response-queue)   │Responder │
│          │─────────────────────────────▶│          │
│          │                               │          │
│          │◀─────────────────────────────│          │
│          │   response (correlation: X)   │          │
└──────────┘                               └──────────┘
```

```python
# NServiceBus / MassTransit style
class RequestClient:
    async def request(self, command, timeout=30):
        correlation_id = uuid4()
        await self.bus.send(command, headers={
            'reply-to': self.reply_queue,
            'correlation-id': str(correlation_id)
        })
        return await self.wait_for_reply(correlation_id, timeout)
```

| Pros | Cons |
|------|------|
| Decoupled via broker | Higher latency than direct call |
| Resilient to downtime | Timeout management |
| Load-leveled | Correlation complexity |

**When to use:** When you need response confirmation but want messaging benefits.

---

### 3.6 Claim Check Pattern

**Problem:** Large payloads are expensive to send through message brokers.

**Solution:** Store the large payload externally; pass only a reference (claim check) in the message.

```
Producer                           Consumer
   │                                  │
   │─store payload──▶[Blob/S3]        │
   │                    │             │
   │─send claim key──▶[Broker]──────▶│
   │                                  │─retrieve payload──▶[Blob/S3]
   │                                  │◀─────────────────────────────
```

```python
# Producer
payload_key = f"events/{event_id}/payload.json"
await s3.put_object(Bucket="events", Key=payload_key, Body=large_payload)
await broker.publish("order-events", {
    "type": "OrderCreated",
    "claim_check": f"s3://events/{payload_key}"
})

# Consumer
event = await broker.consume()
payload = await s3.get_object(Bucket="events", Key=event["claim_check"])
```

| Pros | Cons |
|------|------|
| Keeps messages small | Extra storage call |
| Avoids broker limits | Payload availability dependency |
| Cost efficient | More moving parts |

**When to use:** Messages with large payloads (images, documents, reports), broker has size limits.

---

### 3.7 Content-Based Router

**Problem:** Messages need to go to different destinations based on their content.

**Solution:** Inspect message content and route to the appropriate channel.

```
                    ┌──────────────────┐
                    │ Content-Based    │──▶ Queue A (priority orders)
Incoming ──────────▶│ Router           │──▶ Queue B (standard orders)
                    │                  │──▶ Queue C (international)
                    └──────────────────┘
```

```python
async def route_message(message):
    order = json.loads(message.body)
    if order["priority"] == "high":
        await publish_to("priority-orders", message)
    elif order["country"] != "US":
        await publish_to("international-orders", message)
    else:
        await publish_to("standard-orders", message)
```

| Pros | Cons |
|------|------|
| Flexible routing | Routing logic can get complex |
| Decouples producer from destinations | Single point of failure |
| Easy to add new routes | Performance overhead for inspection |

**When to use:** Multi-tenant systems, priority handling, geographic routing.

---

### 3.8 Message Enricher

**Problem:** Message lacks data needed by downstream consumers.

**Solution:** Intermediate component augments the message with additional data before forwarding.

```
┌────────┐    partial     ┌──────────┐    enriched    ┌────────┐
│Producer│──────────────▶│Enricher  │───────────────▶│Consumer│
└────────┘               │          │                 └────────┘
                         │ ┌──────┐ │
                         │ │DB/API│ │
                         │ └──────┘ │
                         └──────────┘
```

```python
async def enrich_order_event(event):
    # Original event has only customer_id
    customer = await customer_service.get(event["customer_id"])
    event["customer_name"] = customer["name"]
    event["customer_tier"] = customer["tier"]
    await publish("enriched-orders", event)
```

| Pros | Cons |
|------|------|
| Keeps producer simple | Extra latency |
| Centralized enrichment | Dependency on data sources |
| Consumers get complete data | Can become bottleneck |

**When to use:** When producers can't/shouldn't include all needed data.

---

### 3.9 Splitter and Aggregator

**Splitter Problem:** A single message contains multiple items that need independent processing.

**Aggregator Problem:** Multiple related messages need to be combined into one.

```
Splitter:
┌───────────────┐      ┌──────────┐     ┌──────────┐
│Batch of 100   │─────▶│ Splitter │────▶│100 single│
│orders         │      └──────────┘     │messages  │
└───────────────┘                       └──────────┘

Aggregator:
┌──────────┐      ┌────────────┐     ┌───────────────┐
│100 results│────▶│ Aggregator │────▶│Combined result│
└──────────┘      └────────────┘     └───────────────┘
```

```python
# Splitter
async def split_batch(batch_message):
    orders = json.loads(batch_message.body)["orders"]
    for order in orders:
        await publish("individual-orders", order, 
                     headers={"batch_id": batch_message.id})

# Aggregator
class Aggregator:
    def __init__(self, expected_count, timeout=30):
        self.results = {}
    
    async def collect(self, message):
        batch_id = message.headers["batch_id"]
        self.results.setdefault(batch_id, []).append(message)
        if len(self.results[batch_id]) == self.expected_count:
            await self.emit_combined(batch_id)
```

**When to use:** Batch processing, parallel fan-out/fan-in, map-reduce style workflows.

---

### 3.10 Wire Tap

**Problem:** Need to observe messages flowing through a channel without affecting processing.

**Solution:** Copy messages to a secondary channel for monitoring/auditing.

```
Producer ──▶ [Channel] ──▶ Consumer
                 │
                 └──(copy)──▶ [Monitor/Audit Log]
```

```python
# Middleware/interceptor approach
async def wiretap_middleware(message, next_handler):
    # Copy to audit topic (non-blocking)
    asyncio.create_task(
        publish("audit-stream", {
            "original_topic": message.topic,
            "payload": message.body,
            "timestamp": datetime.utcnow().isoformat()
        })
    )
    # Continue normal processing
    await next_handler(message)
```

| Pros | Cons |
|------|------|
| Non-intrusive monitoring | Extra storage/bandwidth |
| Debugging aid | Must not slow main flow |
| Audit compliance | Privacy considerations |

**When to use:** Debugging, auditing, compliance logging, monitoring message flows.

---

### 3.11 Correlation ID Propagation

**Problem:** Tracing a request across multiple services in distributed systems.

**Solution:** Generate a unique ID at the edge; propagate it through all calls and messages.

```
Client (generates: corr-id=abc-123)
  │
  ▼
API Gateway (header: X-Correlation-ID: abc-123)
  │
  ├──▶ Order Service (logs with abc-123, passes in headers)
  │       │
  │       ├──▶ Payment Service (logs with abc-123)
  │       │
  │       └──▶ Message: {headers: {correlation-id: abc-123}, ...}
  │                │
  │                ▼
  │            Notification Service (logs with abc-123)
```

```python
# Middleware
from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar('correlation_id')

@app.middleware("http")
async def correlation_middleware(request, call_next):
    corr_id = request.headers.get("X-Correlation-ID", str(uuid4()))
    correlation_id.set(corr_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response

# Logging filter automatically includes it
class CorrelationFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id.get("")
        return True

# Propagate in outgoing calls
async def call_service(url):
    return await httpx.get(url, headers={
        "X-Correlation-ID": correlation_id.get()
    })
```

| Pros | Cons |
|------|------|
| End-to-end tracing | Must be propagated everywhere |
| Debugging distributed issues | Discipline required |
| Works with any observability tool | Slight overhead |

**When to use:** Always. Every distributed system should propagate correlation IDs.

---

## 4. Protocol Comparisons

### 4.1 REST vs gRPC vs GraphQL vs WebSocket vs SSE

| Aspect | REST | gRPC | GraphQL | WebSocket | SSE |
|--------|------|------|---------|-----------|-----|
| Protocol | HTTP/1.1+ | HTTP/2 | HTTP | TCP (upgraded) | HTTP |
| Format | JSON (usually) | Protobuf (binary) | JSON | Any | Text/JSON |
| Contract | OpenAPI/Swagger | .proto files | Schema/SDL | None standard | None |
| Streaming | No (polling) | Bidirectional | Subscriptions | Bidirectional | Server→Client |
| Browser support | Full | Via grpc-web | Full | Full | Full |
| Performance | Medium | High | Medium | High | Medium |
| Use case | Public APIs, CRUD | Internal services, high perf | Flexible queries, BFF | Real-time bidirectional | Live feeds, notifications |
| Caching | HTTP cache built-in | Manual | Complex (GET queries) | No | No |
| Learning curve | Low | Medium | Medium-High | Low | Low |

**Decision guide:**
- **REST**: Default for public APIs, broad compatibility
- **gRPC**: Internal service-to-service, performance-critical, polyglot
- **GraphQL**: Complex client needs, multiple frontends, reducing over-fetching
- **WebSocket**: Chat, gaming, collaborative editing
- **SSE**: Dashboards, notifications, live logs (one-way)

---

### 4.2 JSON vs Protocol Buffers vs Avro vs MessagePack

| Aspect | JSON | Protobuf | Avro | MessagePack |
|--------|------|----------|------|-------------|
| Format | Text | Binary | Binary | Binary |
| Schema | Optional (JSON Schema) | Required (.proto) | Required (JSON schema) | Optional |
| Size | Large | Small (~3-10x smaller) | Small | Medium |
| Speed | Slow | Fast | Fast | Fast |
| Human readable | Yes | No | No | No |
| Schema evolution | Flexible but fragile | Excellent (field numbers) | Good (named fields) | N/A |
| Language support | Universal | Excellent (codegen) | Good (JVM-heavy) | Good |
| Best for | APIs, config, debugging | gRPC, high-perf messaging | Kafka, data pipelines | Cache, real-time |

---

### 4.3 HTTP/1.1 vs HTTP/2 vs HTTP/3 (QUIC)

| Aspect | HTTP/1.1 | HTTP/2 | HTTP/3 (QUIC) |
|--------|----------|--------|----------------|
| Transport | TCP | TCP | UDP (QUIC) |
| Multiplexing | No (connection per request) | Yes (streams) | Yes (independent streams) |
| Head-of-line blocking | Yes | At TCP level | No (per-stream) |
| Header compression | No | HPACK | QPACK |
| Connection setup | TCP + TLS (2-3 RTT) | TCP + TLS (2-3 RTT) | 0-1 RTT |
| Server push | No | Yes | Deprecated |
| Best for | Legacy, simple | Most modern services | Mobile, lossy networks |

---

### 4.4 Kafka vs RabbitMQ vs AWS SQS vs NATS vs Pulsar

| Aspect | Kafka | RabbitMQ | AWS SQS | NATS | Pulsar |
|--------|-------|----------|---------|------|--------|
| Model | Log (stream) | Broker (queue/exchange) | Queue | Pub/Sub + Queue | Log (stream) |
| Ordering | Per partition | Per queue | Best-effort (FIFO option) | Per subject | Per partition |
| Retention | Configurable (days/forever) | Until consumed | 4-14 days | Memory/JetStream | Tiered (infinite) |
| Replay | Yes | No | No | JetStream: Yes | Yes |
| Throughput | Very high (millions/s) | High (tens of thousands/s) | High (auto-scales) | Very high | Very high |
| Latency | Low-medium (batching) | Low | Medium | Ultra-low | Low |
| Multi-tenancy | Topics + ACLs | Vhosts | Account isolation | Accounts | Native |
| Managed options | Confluent, MSK, Aiven | CloudAMQP, AmazonMQ | Native AWS | Synadia | StreamNative |
| Best for | Event streaming, sourcing | Task queues, routing | Serverless, AWS-native | IoT, edge, low-latency | Multi-tenant streaming |
| Complexity | High (ZooKeeper/KRaft) | Medium | Low (serverless) | Low | High |
| Dead letter | Manual (topic) | Built-in | Built-in | JetStream | Built-in |
| Exactly-once | Transactions (limited) | No | FIFO + dedup | No | Transactions |

**Decision guide:**
- **Kafka**: Event sourcing, high-throughput streaming, audit logs
- **RabbitMQ**: Task queues, complex routing, RPC over messaging
- **SQS**: AWS-native, serverless, simple queue needs, low ops overhead
- **NATS**: Ultra-low latency, IoT, edge computing, simple pub/sub
- **Pulsar**: Multi-tenant streaming, tiered storage, geo-replication

---

## Summary: Choosing a Communication Pattern

```
┌─────────────────────────────────────────────────────────┐
│ Need immediate response?                                │
│   YES → Sync (REST/gRPC)                               │
│     └─ Need resilience? → Add Circuit Breaker + Retry  │
│   NO → Async                                           │
│     ├─ One consumer? → Queue (point-to-point)          │
│     ├─ Many consumers? → Pub/Sub or Streaming          │
│     ├─ Need replay? → Event Streaming (Kafka/Pulsar)   │
│     └─ Multi-step tx? → Saga                           │
│         ├─ Simple flow? → Choreography                 │
│         └─ Complex flow? → Orchestration               │
└─────────────────────────────────────────────────────────┘
```

**Universal rules:**
1. Always use correlation IDs
2. Always have DLQs
3. Always make consumers idempotent
4. Always set timeouts
5. Use the Outbox pattern for reliable event publishing
6. Prefer async over sync for cross-domain communication
