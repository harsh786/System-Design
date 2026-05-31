# Event-Driven Architecture (EDA) - Complete Guide

## Table of Contents
- [Foundations](#foundations)
- [Core Patterns](#core-patterns)
- [Messaging Patterns](#messaging-patterns)
- [Stream Processing](#stream-processing)
- [Implementation Patterns](#implementation-patterns)
- [Schema Management](#schema-management)
- [Real-world Architectures](#real-world-architectures)

---

## Foundations

### What is Event-Driven Architecture

Event-Driven Architecture is a software design paradigm where the flow of the program is determined by events — significant changes in state that the system needs to react to.

**Key Principles:**
- Loose coupling between producers and consumers
- Asynchronous communication
- Events are immutable facts about something that happened
- Systems react to events rather than being commanded

```
┌──────────┐    Event     ┌──────────────┐    Event     ┌──────────┐
│ Producer │───────────▶  │ Event Broker │───────────▶  │ Consumer │
└──────────┘              └──────────────┘              └──────────┘
                                │
                                │  Event
                                ▼
                          ┌──────────┐
                          │ Consumer │
                          └──────────┘
```

**Benefits:**
- Decoupled services can evolve independently
- Better scalability (consumers scale independently)
- Natural audit trail (events are facts)
- Resilience (buffering via event broker)

**Challenges:**
- Eventual consistency
- Debugging distributed flows
- Event ordering
- Duplicate handling

---

### Events vs Commands vs Queries

| Aspect | Event | Command | Query |
|--------|-------|---------|-------|
| Intent | "Something happened" | "Do something" | "Tell me something" |
| Direction | Broadcast (1:N) | Targeted (1:1) | Targeted (1:1) |
| Naming | Past tense (`OrderPlaced`) | Imperative (`PlaceOrder`) | Question (`GetOrder`) |
| Coupling | Loose (producer doesn't know consumers) | Tight (sender knows receiver) | Tight |
| Failure | Producer doesn't care if nobody listens | Sender expects result/ack | Sender expects response |
| Mutability | Immutable fact | Can be rejected | No side effects |

```python
# Event - something that happened (immutable fact)
class OrderPlaced:
    order_id: str
    customer_id: str
    total_amount: Decimal
    placed_at: datetime  # when it happened

# Command - request to do something (can be rejected)
class PlaceOrder:
    customer_id: str
    items: List[OrderItem]
    shipping_address: Address

# Query - request for information (no side effects)
class GetOrderStatus:
    order_id: str
```

**Gotchas:**
- Don't name events as commands (`SendEmail` is a command, `EmailRequested` or `OrderPlaced` is an event)
- Events should contain enough context for consumers to act
- Commands have exactly one handler; events can have zero to many

---

### Event Types

#### 1. Domain Events

Events that represent something meaningful in the business domain.

```python
class OrderPlaced:
    """Raised within the bounded context when an order is placed."""
    order_id: str
    customer_id: str
    items: List[OrderItem]
    total: Decimal
    placed_at: datetime

class PaymentReceived:
    """Raised when payment is confirmed."""
    payment_id: str
    order_id: str
    amount: Decimal
    method: str
    received_at: datetime
```

**When to use:** Within a bounded context to notify other aggregates/services about domain state changes.

#### 2. Integration Events

Events published across bounded context boundaries for inter-service communication.

```python
class OrderPlacedIntegrationEvent:
    """Published to message broker for other services."""
    event_id: str  # for deduplication
    event_type: str = "order.placed.v1"
    occurred_at: datetime
    data: {
        "order_id": str,
        "customer_id": str,
        "total": Decimal
        # Only include what consumers need!
    }
```

**Key differences from Domain Events:**
- Serializable (cross-process boundary)
- Versioned (schema evolution)
- Contain only data consumers need (not internal domain details)
- Include metadata (event_id, timestamp, correlation_id)

#### 3. Event Notifications

Thin events that notify something happened but carry minimal data. Consumers must call back for details.

```
┌───────────┐  {order_id: "123"}  ┌──────────────┐
│  Orders   │────────────────────▶│  Shipping    │
└───────────┘                     └──────┬───────┘
      ▲                                  │
      │  GET /orders/123                 │
      └──────────────────────────────────┘
```

```python
# Thin notification event
class OrderPlacedNotification:
    order_id: str
    occurred_at: datetime
    # That's it - consumer calls back for details
```

**Pros:** Small payloads, producer controls data access, always fresh data
**Cons:** Temporal coupling (producer must be available), extra network calls, higher latency

#### 4. Event-Carried State Transfer

Fat events that carry all data consumers need, eliminating callback queries.

```python
class OrderPlacedStateTransfer:
    order_id: str
    customer_id: str
    customer_name: str
    customer_email: str
    items: List[{
        "product_id": str,
        "product_name": str,
        "quantity": int,
        "unit_price": Decimal
    }]
    shipping_address: Address
    total: Decimal
    placed_at: datetime
    # Everything consumers might need
```

**Pros:** No callback needed, consumer autonomy, works offline, lower latency
**Cons:** Larger payloads, potential stale data, coupling to producer's data model

---

### Eventual Consistency and Why It Matters

**Strong Consistency:** After a write, all reads return the updated value.
**Eventual Consistency:** After a write, reads will *eventually* return the updated value (given no new writes).

```
Timeline:
─────────────────────────────────────────────────────────▶ time

Service A:  [Order Placed] ──event──▶
Service B:                            [Processing...]  [Order Visible]
                                      ◀── inconsistency window ──▶
```

**Why it matters in EDA:**
1. **Scalability** - No distributed locks, no 2PC overhead
2. **Availability** - Services operate independently (CAP theorem: AP over CP)
3. **Resilience** - One service being down doesn't block others

**Handling Eventual Consistency:**

```python
# Strategy 1: Optimistic UI
# Show user their action succeeded immediately, reconcile later
@app.post("/orders")
async def place_order(order: OrderRequest):
    event = OrderPlaced(...)
    await publish(event)
    return {"status": "accepted", "order_id": event.order_id}
    # Don't wait for downstream processing

# Strategy 2: Polling/Webhooks for completion
@app.get("/orders/{order_id}/status")
async def get_status(order_id: str):
    return await order_projection.get_status(order_id)

# Strategy 3: Compensation on failure
class OrderSaga:
    async def on_payment_failed(self, event: PaymentFailed):
        await publish(OrderCancelled(order_id=event.order_id))
```

**Common patterns for managing:**
- Saga pattern for distributed transactions
- Read-your-own-writes (route reads to the service that just wrote)
- Causal consistency (vector clocks, version vectors)
- Compensation (undo on failure)

---

### Temporal Coupling vs Spatial Coupling

#### Temporal Coupling
Services must be available **at the same time** to communicate.

```
Synchronous (temporally coupled):
┌─────────┐  HTTP request  ┌─────────┐
│Service A│───────────────▶│Service B│  ← B must be up!
└─────────┘◀───────────────└─────────┘
              HTTP response
```

#### Spatial Coupling
Services must know **where** each other is (address, endpoint).

```
Direct call (spatially coupled):
Service A must know: http://service-b:8080/api/orders
```

**EDA reduces both:**

```
Event-driven (decoupled):
┌─────────┐   event   ┌────────┐   event   ┌─────────┐
│Service A│──────────▶│ Broker │──────────▶│Service B│
└─────────┘           └────────┘           └─────────┘

- A doesn't know B exists (no spatial coupling)
- B can be down; broker buffers (no temporal coupling)
- B processes when ready
```

| | Synchronous | Asynchronous (EDA) |
|---|---|---|
| Temporal coupling | High | Low |
| Spatial coupling | High | Low (via broker) |
| Latency | Immediate response | Eventually |
| Complexity | Lower | Higher |
| Failure handling | Cascading | Isolated |

---

## Core Patterns

### Event Sourcing

**Problem:** Traditional CRUD loses history. You only have current state. Audit trails are afterthoughts. You can't ask "how did we get here?"

**Solution:** Store state as a sequence of immutable events. Current state is derived by replaying events.

```
Traditional CRUD:                    Event Sourcing:
┌─────────────────┐                 ┌─────────────────────────────┐
│ orders table    │                 │ event_store                 │
├─────────────────┤                 ├─────────────────────────────┤
│ id: 123         │                 │ OrderCreated {id:123,...}   │
│ status: shipped │                 │ ItemAdded {id:123, sku:..}  │
│ total: $50      │                 │ PaymentReceived {id:123,..} │
│ items: [...]    │                 │ OrderShipped {id:123,...}   │
└─────────────────┘                 └─────────────────────────────┘
  (only current state)                (full history, derive state)
```

#### Event Store Design (Append-Only, Immutable)

```sql
CREATE TABLE event_store (
    global_position  BIGSERIAL PRIMARY KEY,    -- global ordering
    stream_id        VARCHAR(255) NOT NULL,     -- e.g., "order-123"
    stream_position  INTEGER NOT NULL,          -- position within stream
    event_type       VARCHAR(255) NOT NULL,     -- e.g., "OrderPlaced"
    event_data       JSONB NOT NULL,            -- event payload
    metadata         JSONB NOT NULL,            -- correlation_id, causation_id, user_id
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(stream_id, stream_position)          -- optimistic concurrency
);

-- Index for reading streams
CREATE INDEX idx_stream ON event_store(stream_id, stream_position);

-- NEVER UPDATE OR DELETE - append only!
```

```python
class EventStore:
    async def append(self, stream_id: str, events: List[Event], 
                     expected_version: int) -> None:
        """Append events with optimistic concurrency control."""
        async with self.db.transaction():
            current_version = await self._get_stream_version(stream_id)
            
            if current_version != expected_version:
                raise ConcurrencyError(
                    f"Expected version {expected_version}, "
                    f"but stream is at {current_version}"
                )
            
            for i, event in enumerate(events):
                await self.db.execute(
                    """INSERT INTO event_store 
                       (stream_id, stream_position, event_type, event_data, metadata)
                       VALUES ($1, $2, $3, $4, $5)""",
                    stream_id,
                    expected_version + i + 1,
                    event.__class__.__name__,
                    event.to_dict(),
                    event.metadata
                )
    
    async def read_stream(self, stream_id: str, 
                          from_version: int = 0) -> List[StoredEvent]:
        """Read all events for a stream."""
        rows = await self.db.fetch(
            """SELECT * FROM event_store 
               WHERE stream_id = $1 AND stream_position > $2
               ORDER BY stream_position""",
            stream_id, from_version
        )
        return [self._deserialize(row) for row in rows]
```

#### Snapshots for Performance

**Problem:** Replaying thousands of events for every read is slow.

```python
class SnapshotStore:
    async def save_snapshot(self, stream_id: str, version: int, state: dict):
        await self.db.execute(
            """INSERT INTO snapshots (stream_id, version, state, created_at)
               VALUES ($1, $2, $3, NOW())
               ON CONFLICT (stream_id) DO UPDATE 
               SET version = $2, state = $3, created_at = NOW()""",
            stream_id, version, json.dumps(state)
        )
    
    async def load_aggregate(self, stream_id: str) -> Aggregate:
        # 1. Try to load snapshot
        snapshot = await self.snapshot_store.get_latest(stream_id)
        
        if snapshot:
            aggregate = Aggregate.from_snapshot(snapshot.state)
            from_version = snapshot.version
        else:
            aggregate = Aggregate()
            from_version = 0
        
        # 2. Replay only events after snapshot
        events = await self.event_store.read_stream(stream_id, from_version)
        for event in events:
            aggregate.apply(event)
        
        # 3. Maybe take new snapshot
        if len(events) > SNAPSHOT_THRESHOLD:
            await self.save_snapshot(
                stream_id, aggregate.version, aggregate.to_snapshot()
            )
        
        return aggregate
```

**Snapshot strategies:**
- Every N events (e.g., every 100 events)
- Time-based (every hour)
- On read, if too many events since last snapshot

#### Event Replay and Projection Rebuilding

```python
class ProjectionRebuilder:
    """Rebuild read models by replaying all events."""
    
    async def rebuild(self, projection: Projection):
        # 1. Clear existing projection data
        await projection.reset()
        
        # 2. Read ALL events from event store
        position = 0
        batch_size = 1000
        
        while True:
            events = await self.event_store.read_all(
                from_position=position, 
                limit=batch_size
            )
            if not events:
                break
            
            for event in events:
                await projection.handle(event)
                position = event.global_position
            
            # Checkpoint for resumability
            await projection.save_checkpoint(position)
        
        print(f"Rebuilt projection up to position {position}")

# Example projection
class OrderSummaryProjection:
    async def handle(self, event: StoredEvent):
        if event.event_type == "OrderPlaced":
            await self.db.execute(
                "INSERT INTO order_summary (id, customer, total, status) VALUES...",
                event.data
            )
        elif event.event_type == "OrderShipped":
            await self.db.execute(
                "UPDATE order_summary SET status='shipped' WHERE id=$1",
                event.data["order_id"]
            )
```

**Use cases for replay:**
- Bug fix in projection logic → rebuild with corrected code
- New projection/read model → build from scratch
- Migration to new system → replay into new store
- Analytics → replay with new aggregation logic

#### Versioning Events (Upcasting)

**Problem:** Event schemas evolve. Old events in store have old format.

```python
# V1 of the event (stored months ago)
{"event_type": "OrderPlaced", "version": 1,
 "data": {"order_id": "123", "amount": 50.0}}

# V2 adds currency (new events)
{"event_type": "OrderPlaced", "version": 2,
 "data": {"order_id": "123", "amount": {"value": 50.0, "currency": "USD"}}}

# Upcaster transforms V1 → V2 on read
class OrderPlacedUpcaster:
    def can_upcast(self, event_type: str, version: int) -> bool:
        return event_type == "OrderPlaced" and version == 1
    
    def upcast(self, event_data: dict) -> dict:
        """Transform V1 to V2 format."""
        return {
            "order_id": event_data["order_id"],
            "amount": {
                "value": event_data["amount"],
                "currency": "USD"  # default for old events
            }
        }

class EventDeserializer:
    def deserialize(self, stored_event: StoredEvent) -> Event:
        data = stored_event.data
        version = stored_event.version
        
        # Apply upcasters in sequence: V1 → V2 → V3 → ...
        for upcaster in self.upcasters:
            if upcaster.can_upcast(stored_event.event_type, version):
                data = upcaster.upcast(data)
                version += 1
        
        return self.event_registry[stored_event.event_type](data)
```

**Strategies:**
1. **Upcasting** - Transform on read (recommended)
2. **Lazy migration** - Rewrite events on next read (controversial, breaks immutability)
3. **Copy-transform** - New stream with transformed events (expensive)
4. **Weak schema** - Use flexible formats (JSON), handle missing fields

**Gotchas:**
- Never delete or modify events in the store
- Version number in each event for upcasting
- Keep all upcasters forever (chain: V1→V2→V3→...)
- Test upcasters with old event fixtures

---

### CQRS + Event Sourcing Combined

```
                    ┌─────────────────────────────────────────────┐
                    │              WRITE SIDE                      │
  Command ────────▶│  Command Handler → Aggregate → Event Store  │
                    └─────────────────────┬───────────────────────┘
                                          │ events
                                          ▼
                                    ┌───────────┐
                                    │  Pub/Sub  │
                                    └─────┬─────┘
                                          │
                    ┌─────────────────────┼───────────────────────┐
                    │              READ SIDE                       │
                    │  Event Handler → Projection → Read DB       │
  Query ──────────▶│                                    │         │
                    │  Query Handler ◀──────────────────┘         │
                    └─────────────────────────────────────────────┘
```

```python
# Write side
class PlaceOrderHandler:
    async def handle(self, command: PlaceOrder):
        # Load aggregate from event store
        order = await self.repository.load(command.order_id)
        
        # Business logic produces events
        order.place(command.customer_id, command.items)
        
        # Save events to event store
        await self.repository.save(order)

class Order:  # Aggregate
    def __init__(self):
        self.events = []
        self.status = None
    
    def place(self, customer_id, items):
        if self.status is not None:
            raise DomainError("Order already exists")
        self._apply(OrderPlaced(customer_id=customer_id, items=items))
    
    def _apply(self, event):
        self._handle(event)
        self.events.append(event)
    
    def _handle(self, event):
        if isinstance(event, OrderPlaced):
            self.status = "placed"
        elif isinstance(event, OrderShipped):
            self.status = "shipped"

# Read side
class OrderReadModelUpdater:
    async def handle(self, event: OrderPlaced):
        await self.read_db.execute(
            """INSERT INTO orders_view 
               (id, customer_id, status, total, placed_at)
               VALUES ($1, $2, 'placed', $3, $4)""",
            event.order_id, event.customer_id, 
            event.total, event.placed_at
        )

class OrderQueryHandler:
    async def get_order(self, order_id: str):
        return await self.read_db.fetch_one(
            "SELECT * FROM orders_view WHERE id = $1", order_id
        )
```

---

### Event Notification Pattern

**Problem:** Services need to know something happened in another service but don't need the full data.

**Solution:** Publish thin events; consumers call back for details if needed.

```python
# Producer publishes thin event
await broker.publish("orders", {
    "event_type": "order.placed",
    "order_id": "123",
    "occurred_at": "2024-01-15T10:30:00Z"
})

# Consumer receives and calls back
class ShippingService:
    async def on_order_placed(self, event):
        # Get full details via API call
        order = await self.order_client.get_order(event["order_id"])
        await self.create_shipment(order)
```

**When to use:** When data changes frequently and you want consumers to always get fresh data.
**Gotchas:** Creates temporal coupling (producer must be up for callback). Consider Event-Carried State Transfer if availability matters more.

---

### Event-Carried State Transfer Pattern

**Problem:** Consumers need data from producers but don't want runtime coupling.

**Solution:** Include all relevant data in the event so consumers can maintain local copies.

```python
# Producer publishes fat event
await broker.publish("customers", {
    "event_type": "customer.address_updated",
    "customer_id": "456",
    "data": {
        "name": "John Doe",
        "email": "john@example.com",
        "shipping_address": {
            "street": "123 Main St",
            "city": "Seattle",
            "state": "WA",
            "zip": "98101"
        }
    }
})

# Consumer maintains local copy
class OrderService:
    async def on_customer_updated(self, event):
        await self.local_db.execute(
            """INSERT INTO customer_cache (id, name, email, address)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (id) DO UPDATE SET ...""",
            event["customer_id"], 
            event["data"]["name"],
            event["data"]["email"],
            json.dumps(event["data"]["shipping_address"])
        )
    
    # Now orders can use local cache - no API call needed!
    async def place_order(self, customer_id, items):
        customer = await self.local_db.fetch("SELECT * FROM customer_cache WHERE id=$1", customer_id)
        # ...
```

**When to use:** High availability requirements, performance-sensitive consumers, offline capability.
**Gotchas:** Data may be stale; larger event payloads; consumers must handle out-of-order updates.

---

### Domain Event Pattern

**Problem:** Different parts of the system need to react to business-significant occurrences without tight coupling.

**Solution:** Model business occurrences as first-class objects and dispatch them.

```python
class DomainEvent:
    def __init__(self):
        self.occurred_at = datetime.utcnow()
        self.event_id = str(uuid4())

class OrderPlaced(DomainEvent):
    def __init__(self, order_id: str, customer_id: str, total: Decimal):
        super().__init__()
        self.order_id = order_id
        self.customer_id = customer_id
        self.total = total

# Aggregate raises domain events
class Order:
    def __init__(self):
        self._domain_events: List[DomainEvent] = []
    
    def place(self, customer_id: str, items: List[Item]):
        # Business rules...
        self.status = "placed"
        self._domain_events.append(
            OrderPlaced(self.id, customer_id, self.calculate_total(items))
        )
    
    def collect_events(self) -> List[DomainEvent]:
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events

# Application service dispatches after persistence
class OrderService:
    async def place_order(self, command: PlaceOrder):
        order = Order()
        order.place(command.customer_id, command.items)
        
        await self.repository.save(order)
        
        # Dispatch after successful persistence
        for event in order.collect_events():
            await self.event_dispatcher.dispatch(event)
```

---

## Messaging Patterns

### Publish/Subscribe

**Problem:** Multiple consumers need to receive the same message.

**Solution:** Producer publishes to a topic; all subscribers receive a copy.

```
┌──────────┐         ┌─────────┐         ┌────────────┐
│ Producer │────────▶│  Topic  │────────▶│Subscriber A│
└──────────┘         │         │         └────────────┘
                     │         │────────▶┌────────────┐
                     │         │         │Subscriber B│
                     └─────────┘         └────────────┘
```

```python
# Kafka example
from confluent_kafka import Producer, Consumer

# Publisher
producer = Producer({'bootstrap.servers': 'localhost:9092'})
producer.produce('order-events', key='order-123', value=json.dumps(event))
producer.flush()

# Subscriber (each consumer group gets all messages)
consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'shipping-service',  # each group = independent subscriber
    'auto.offset.reset': 'earliest'
})
consumer.subscribe(['order-events'])
```

**When to use:** Broadcasting events to multiple independent consumers.
**Gotchas:** Message ordering only guaranteed within a partition (Kafka) or not at all (some brokers).

---

### Point-to-Point Channel

**Problem:** A message should be processed by exactly one consumer (competing consumers).

**Solution:** Multiple consumers read from the same queue; only one gets each message.

```
┌──────────┐         ┌─────────┐         ┌────────────┐
│ Producer │────────▶│  Queue  │────────▶│Consumer A  │ (gets msg 1,3,5)
└──────────┘         │         │────────▶│Consumer B  │ (gets msg 2,4,6)
                     └─────────┘         └────────────┘
```

```python
# RabbitMQ example
import pika

channel.queue_declare(queue='order-processing')

# Multiple workers consume from same queue
channel.basic_qos(prefetch_count=1)  # fair dispatch
channel.basic_consume(queue='order-processing', on_message_callback=process_order)
```

**When to use:** Work distribution, task queues, load balancing across workers.

---

### Dead Letter Channel

**Problem:** Messages that can't be processed (poison messages) block the queue.

**Solution:** Move failed messages to a separate "dead letter" queue for investigation.

```
┌──────────┐    ┌────────────┐    ┌──────────┐
│  Queue   │───▶│  Consumer  │    │  DLQ     │
└──────────┘    └─────┬──────┘    └──────────┘
                      │ fails 3x       ▲
                      └────────────────┘
```

```python
# RabbitMQ DLQ setup
channel.exchange_declare('dlx', exchange_type='direct')
channel.queue_declare('order-processing', arguments={
    'x-dead-letter-exchange': 'dlx',
    'x-dead-letter-routing-key': 'order-processing-dlq',
    'x-message-ttl': 60000,  # optional TTL
    'x-max-delivery-count': 3  # retry limit (RabbitMQ quorum queues)
})
channel.queue_declare('order-processing-dlq')
channel.queue_bind('order-processing-dlq', 'dlx', 'order-processing-dlq')

# Kafka DLQ pattern
class ConsumerWithDLQ:
    async def process(self, message):
        try:
            await self.handle(message)
        except RetryableError:
            await self.retry_topic.send(message)  # retry later
        except Exception:
            await self.dlq_topic.send(message)  # give up, investigate
            logger.error(f"Message sent to DLQ: {message}")
```

**When to use:** Always. Every production messaging system needs a DLQ strategy.
**Best practices:**
- Monitor DLQ size (alert if growing)
- Include original error reason in DLQ message metadata
- Build tooling to replay from DLQ after fixing bugs

---

### Invalid Message Channel

**Problem:** Messages that are malformed or fail schema validation.

**Solution:** Route invalid messages to a dedicated channel for inspection without blocking processing.

```python
class MessageValidator:
    async def process(self, raw_message):
        try:
            message = self.schema.validate(raw_message)
        except ValidationError as e:
            await self.invalid_channel.send({
                "original_message": raw_message,
                "error": str(e),
                "received_at": datetime.utcnow().isoformat()
            })
            return  # Don't process invalid messages
        
        await self.handler.handle(message)
```

**Difference from DLQ:** Invalid messages fail *validation* (bad format). DLQ messages fail *processing* (valid format but business logic error or transient failure).

---

### Message Router

**Problem:** Different messages need different processing pipelines.

**Solution:** A router examines each message and directs it to the appropriate channel.

```
                         ┌──────────────┐
                    ┌───▶│ Handler A    │
┌───────────┐      │    └──────────────┘
│  Message  │──▶┌──┴──┐
│  Channel  │   │Router│
└───────────┘   └──┬──┘
                    │    ┌──────────────┐
                    └───▶│ Handler B    │
                         └──────────────┘
```

```python
class MessageRouter:
    def __init__(self):
        self.routes: Dict[str, Handler] = {}
    
    def register(self, message_type: str, handler: Handler):
        self.routes[message_type] = handler
    
    async def route(self, message: Message):
        handler = self.routes.get(message.type)
        if handler:
            await handler.handle(message)
        else:
            await self.dead_letter.send(message)
```

---

### Content-Based Router

**Problem:** Route messages based on message content (not just type).

```python
class ContentBasedRouter:
    async def route(self, order_event):
        if order_event.total > 10000:
            await self.high_value_handler.handle(order_event)
        elif order_event.region == "EU":
            await self.eu_handler.handle(order_event)
        else:
            await self.default_handler.handle(order_event)
```

**Gotchas:** Can become complex; consider if message type granularity should be finer instead.

---

### Message Filter

**Problem:** Consumer only interested in subset of messages on a channel.

```python
class OrderFilter:
    def __init__(self, handler, min_amount=0, region=None):
        self.handler = handler
        self.min_amount = min_amount
        self.region = region
    
    async def handle(self, event):
        if event.total < self.min_amount:
            return  # filtered out
        if self.region and event.region != self.region:
            return  # filtered out
        await self.handler.handle(event)
```

---

### Claim Check Pattern

**Problem:** Large payloads (files, images) bloat the message broker.

**Solution:** Store large payload externally; pass only a reference (claim check) in the message.

```
┌──────────┐   large file   ┌─────────┐   reference    ┌─────────┐
│ Producer │───────────────▶│  Blob   │                │  Broker │
└──────────┘                │  Store  │                └────┬────┘
                            └─────────┘                     │
                                 ▲                          │ {claim_check: "s3://..."}
                                 │                          ▼
                                 │   download          ┌──────────┐
                                 └─────────────────────│ Consumer │
                                                       └──────────┘
```

```python
# Producer
async def publish_with_claim_check(self, data: bytes, metadata: dict):
    # Store large payload in S3
    key = f"events/{uuid4()}"
    await self.s3.put_object(Bucket="event-payloads", Key=key, Body=data)
    
    # Publish small message with reference
    await self.broker.publish({
        "metadata": metadata,
        "payload_ref": f"s3://event-payloads/{key}"  # claim check
    })

# Consumer
async def consume(self, message):
    # Retrieve payload using claim check
    payload = await self.s3.get_object(
        Bucket="event-payloads", 
        Key=message["payload_ref"].split("//")[1]
    )
    await self.process(payload, message["metadata"])
```

**When to use:** Messages > 256KB (Kafka limit), files, images, large documents.

---

### Message Sequencing

**Problem:** Messages arrive out of order but must be processed in sequence.

```python
class SequencedConsumer:
    """Process messages in order using sequence numbers."""
    
    def __init__(self):
        self.expected_seq = {}  # stream_id -> next expected seq
        self.buffer = {}  # stream_id -> {seq: message}
    
    async def handle(self, message):
        stream_id = message.stream_id
        seq = message.sequence_number
        expected = self.expected_seq.get(stream_id, 1)
        
        if seq == expected:
            # Process this and any buffered subsequent messages
            await self.process(message)
            self.expected_seq[stream_id] = seq + 1
            await self._flush_buffer(stream_id)
        elif seq > expected:
            # Buffer for later
            self.buffer.setdefault(stream_id, {})[seq] = message
        else:
            # Duplicate, ignore
            pass
    
    async def _flush_buffer(self, stream_id):
        buf = self.buffer.get(stream_id, {})
        while self.expected_seq[stream_id] in buf:
            seq = self.expected_seq[stream_id]
            await self.process(buf.pop(seq))
            self.expected_seq[stream_id] = seq + 1
```

---

### Guaranteed Delivery

**Problem:** Messages must not be lost, even if broker or consumer crashes.

**Solution:** Combine persistent storage, acknowledgments, and retries.

```python
# Producer: Transactional outbox (see Outbox Pattern below)
# Broker: Replication + persistence
# Consumer: Manual acknowledgment after processing

class ReliableConsumer:
    async def consume(self):
        while True:
            message = await self.broker.receive()
            try:
                await self.process(message)
                await self.broker.acknowledge(message)  # only after success
            except RetryableError:
                await self.broker.nack(message)  # redelivery
            except Exception:
                await self.broker.nack_to_dlq(message)
```

**Three guarantees:**
- **At-most-once:** Ack before processing (may lose messages)
- **At-least-once:** Ack after processing (may get duplicates) ← most common
- **Exactly-once:** Idempotent processing + at-least-once delivery

---

## Stream Processing

### Apache Kafka Architecture (Deep Dive)

```
┌─────────────────────────────────────────────────────────────┐
│                      Kafka Cluster                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Topic: order-events                     │   │
│  │                                                     │   │
│  │  Partition 0: [msg0][msg1][msg2][msg3][msg4]───▶   │   │
│  │  Partition 1: [msg0][msg1][msg2]───▶               │   │
│  │  Partition 2: [msg0][msg1][msg2][msg3]───▶         │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Broker 1 (Leader P0, Follower P2)                         │
│  Broker 2 (Leader P1, Follower P0)                         │
│  Broker 3 (Leader P2, Follower P1)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Concepts:**

| Concept | Description |
|---------|-------------|
| **Topic** | Named feed of messages (like a table) |
| **Partition** | Ordered, immutable sequence of records. Unit of parallelism |
| **Offset** | Sequential ID within a partition |
| **Producer** | Writes to partitions (chooses partition by key hash or round-robin) |
| **Consumer** | Reads from partitions, tracks offset |
| **Consumer Group** | Set of consumers that share partition assignments |
| **Replication Factor** | Copies of each partition across brokers |
| **ISR** | In-Sync Replicas - followers that are caught up to leader |

**Partitioning:**
```python
# Key-based partitioning ensures ordering per entity
producer.produce(
    topic='order-events',
    key=order_id.encode(),  # Same order_id → same partition → ordered
    value=json.dumps(event).encode()
)

# Partition count determines max parallelism
# 12 partitions → max 12 consumers in a group
```

**Consumer Groups:**
```
Consumer Group "shipping":     Consumer Group "analytics":
  Consumer 1 → P0, P1           Consumer A → P0
  Consumer 2 → P2               Consumer B → P1
                                 Consumer C → P2

Each group independently reads ALL messages.
Within a group, each partition is assigned to exactly one consumer.
```

**Replication:**
```
Partition 0 (replication factor = 3):
  Broker 1: [Leader]    msg0, msg1, msg2, msg3
  Broker 2: [Follower]  msg0, msg1, msg2, msg3  (ISR)
  Broker 3: [Follower]  msg0, msg1, msg2        (lagging, may leave ISR)

acks=all → producer waits for all ISR to confirm
acks=1   → producer waits for leader only
acks=0   → fire and forget
```

**Key configurations:**
```properties
# Producer
acks=all                          # Durability
enable.idempotence=true           # Exactly-once producer
max.in.flight.requests.per.connection=5  # With idempotence

# Consumer
enable.auto.commit=false          # Manual offset control
isolation.level=read_committed    # For transactional reads
max.poll.records=500              # Batch size

# Topic
retention.ms=604800000            # 7 days
cleanup.policy=delete             # or compact
min.insync.replicas=2             # With acks=all, ensures 2 copies
```

---

### Kafka Streams

Lightweight stream processing library (runs in your JVM app, no separate cluster).

```java
StreamsBuilder builder = new StreamsBuilder();

// Read from topic
KStream<String, OrderEvent> orders = builder.stream("order-events");

// Process
KTable<String, Long> orderCounts = orders
    .filter((key, event) -> event.getStatus().equals("PLACED"))
    .groupByKey()
    .count(Materialized.as("order-counts-store"));

// Windowed aggregation
KTable<Windowed<String>, Long> hourlyOrders = orders
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofHours(1)))
    .count();

// Write results
orderCounts.toStream().to("order-counts");
```

---

### Apache Flink

Full-featured distributed stream processing engine.

```java
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

DataStream<OrderEvent> orders = env
    .addSource(new FlinkKafkaConsumer<>("order-events", schema, properties));

// Complex event processing
DataStream<FraudAlert> alerts = orders
    .keyBy(OrderEvent::getCustomerId)
    .window(SlidingEventTimeWindows.of(Time.minutes(5), Time.minutes(1)))
    .process(new FraudDetectionFunction());

// Exactly-once with checkpointing
env.enableCheckpointing(60000, CheckpointingMode.EXACTLY_ONCE);
```

**Flink vs Kafka Streams:**

| Aspect | Kafka Streams | Flink |
|--------|--------------|-------|
| Deployment | Library (in your app) | Separate cluster |
| Source | Kafka only | Kafka, files, sockets, custom |
| Processing | Stream only | Stream + Batch |
| State | RocksDB (local) | RocksDB + distributed snapshots |
| Exactly-once | Within Kafka | End-to-end |
| Complexity | Low | High |
| Scale | Good | Massive |

---

### Apache Pulsar (vs Kafka Comparison)

| Feature | Kafka | Pulsar |
|---------|-------|--------|
| Architecture | Monolithic broker | Separate serving (brokers) + storage (BookKeeper) |
| Multi-tenancy | Limited | Native (tenants, namespaces) |
| Geo-replication | MirrorMaker (complex) | Built-in |
| Queuing + Streaming | Streaming only | Both (shared subscriptions) |
| Message ack | Offset-based (sequential) | Individual message ack |
| Tiered storage | Kafka Tiered Storage | Native (offload to S3) |
| Schema | Schema Registry (separate) | Built-in schema registry |
| Protocol | Custom | Custom + Kafka-compatible proxy |

---

### AWS Kinesis

```python
import boto3

# Producer
kinesis = boto3.client('kinesis')
kinesis.put_record(
    StreamName='order-events',
    Data=json.dumps(event).encode(),
    PartitionKey=order_id  # determines shard
)

# Consumer (KCL-style)
# Each shard: 1MB/s write, 2MB/s read, up to 1000 records/s write
# Resharding: split (scale up) or merge (scale down)
```

**Kinesis vs Kafka:**

| Aspect | Kinesis | Kafka |
|--------|---------|-------|
| Management | Serverless | Self-managed or managed (MSK) |
| Retention | 24h - 365 days | Configurable (unlimited) |
| Throughput | Per-shard limits | Per-partition (higher) |
| Cost | Per shard-hour + PUT | Infrastructure cost |
| Scaling | Shard split/merge | Add partitions (easier) |

---

### Event Time vs Processing Time

```
Event Time:      When the event actually occurred (in source system)
Processing Time: When the event is processed by the system

Example:
  Event created at:  10:00:00 (event time)
  Arrives at broker: 10:00:05 (ingestion time)
  Processed by app:  10:00:12 (processing time)

Late data: Event with event_time=9:55 arriving at processing_time=10:05
```

```python
# Using event time for accurate analytics
class EventTimeProcessor:
    def assign_timestamp(self, event):
        return event.occurred_at  # Use event time, not wall clock
    
    # Window based on when events HAPPENED, not when they ARRIVED
    # This handles out-of-order and late events correctly
```

---

### Windowing

```
Tumbling Window (fixed, non-overlapping):
|──── 1min ────|──── 1min ────|──── 1min ────|
[  events A  ] [  events B  ] [  events C  ]

Hopping Window (fixed, overlapping):
|──── 1min ────|
     |──── 1min ────|
          |──── 1min ────|
(hop = 30s, size = 1min)

Sliding Window (triggered by events, overlapping):
   [event]         [event]    [event]
|←─ 1min ─→|   |←─ 1min ─→|
        |←─ 1min ─→|

Session Window (gap-based, variable size):
[events...][gap > 30s][events...][gap > 30s][events]
|─ session 1 ─|       |─ session 2 ─|       |─ s3 ─|
```

```java
// Flink examples
// Tumbling: non-overlapping fixed windows
.window(TumblingEventTimeWindows.of(Time.minutes(5)))

// Hopping: overlapping fixed windows
.window(SlidingEventTimeWindows.of(Time.minutes(10), Time.minutes(5)))

// Session: gap-based
.window(EventTimeSessionWindows.withGap(Time.minutes(30)))
```

---

### Watermarks and Late Data Handling

**Watermark:** A timestamp W meaning "no events with timestamp < W will arrive."

```
Events:    [t=3] [t=1] [t=5] [t=2] [t=7] [t=4]
                                         ↑
                              Watermark = 5 (allows 2s lateness)
                              "All events up to t=5 have arrived"

If event [t=3] arrives now → LATE (after watermark passed 3)
```

```java
// Flink watermark strategy
WatermarkStrategy
    .<Event>forBoundedOutOfOrderness(Duration.ofSeconds(5))
    .withTimestampAssigner((event, timestamp) -> event.getTimestamp());

// Handle late data
.window(TumblingEventTimeWindows.of(Time.minutes(1)))
.allowedLateness(Time.minutes(5))  // still update window
.sideOutputLateData(lateOutputTag)  // capture very late data
```

---

### Exactly-Once Semantics

**Three levels:**
1. **At-most-once:** May lose messages (ack before process)
2. **At-least-once:** May duplicate messages (ack after process)
3. **Exactly-once:** Each message processed exactly once

**Achieving exactly-once (Kafka):**

```python
# Producer idempotence (handles retries without duplicates)
producer = Producer({
    'enable.idempotence': True,  # Producer dedup via sequence numbers
    'acks': 'all'
})

# Transactional producer (atomic multi-partition writes)
producer.init_transactions()
producer.begin_transaction()
producer.produce('topic-a', value=msg1)
producer.produce('topic-b', value=msg2)
producer.send_offsets_to_transaction(consumer_offsets, consumer_group)
producer.commit_transaction()  # All or nothing

# Consumer: read_committed isolation
consumer = Consumer({
    'isolation.level': 'read_committed'  # Only see committed messages
})
```

**True exactly-once = idempotent processing + at-least-once delivery:**
```python
class ExactlyOnceConsumer:
    async def process(self, message):
        # Idempotency check
        if await self.is_processed(message.id):
            return  # Already handled
        
        # Process in transaction with dedup record
        async with self.db.transaction():
            await self.handle(message)
            await self.mark_processed(message.id)  # dedup table
            await self.commit_offset(message.offset)
```

---

## Implementation Patterns

### Outbox Pattern (with Debezium CDC)

**Problem:** You need to update a database AND publish an event atomically. Dual writes can fail inconsistently.

```
WRONG (dual write):
  1. UPDATE orders SET status='placed'   ← succeeds
  2. PUBLISH OrderPlaced to Kafka        ← fails! Inconsistency!

RIGHT (outbox):
  1. In ONE transaction:
     - UPDATE orders SET status='placed'
     - INSERT INTO outbox (event_type, payload, ...)
  2. Separate process reads outbox → publishes to Kafka
```

```python
class OrderService:
    async def place_order(self, command: PlaceOrder):
        async with self.db.transaction():
            # Business logic
            order = Order.create(command)
            await self.order_repo.save(order)
            
            # Write to outbox in SAME transaction
            await self.db.execute(
                """INSERT INTO outbox 
                   (id, aggregate_type, aggregate_id, event_type, payload, created_at)
                   VALUES ($1, $2, $3, $4, $5, NOW())""",
                uuid4(), 'Order', order.id, 'OrderPlaced',
                json.dumps(order.to_event_payload())
            )
```

```sql
CREATE TABLE outbox (
    id              UUID PRIMARY KEY,
    aggregate_type  VARCHAR(255) NOT NULL,
    aggregate_id    VARCHAR(255) NOT NULL,
    event_type      VARCHAR(255) NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMP NOT NULL,
    published_at    TIMESTAMP NULL  -- NULL = not yet published
);
```

**Debezium CDC (Change Data Capture):**
```json
// Debezium connector config - captures outbox inserts via WAL/binlog
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "database.hostname": "postgres",
  "database.port": "5432",
  "database.dbname": "orders",
  "table.include.list": "public.outbox",
  "transforms": "outbox",
  "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
  "transforms.outbox.table.field.event.key": "aggregate_id",
  "transforms.outbox.table.field.event.type": "event_type",
  "transforms.outbox.table.field.event.payload": "payload",
  "transforms.outbox.route.topic.replacement": "events.${routedByValue}"
}
```

```
┌───────────┐  transaction  ┌──────────────────┐
│  Service  │──────────────▶│  DB + Outbox     │
└───────────┘               └────────┬─────────┘
                                     │ WAL/CDC
                                     ▼
                              ┌─────────────┐
                              │  Debezium   │
                              └──────┬──────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │    Kafka    │
                              └─────────────┘
```

---

### Inbox Pattern

**Problem:** Consumer might process the same message twice (at-least-once delivery).

**Solution:** Track processed message IDs; skip duplicates.

```python
class InboxConsumer:
    async def handle(self, message):
        async with self.db.transaction():
            # Check inbox (deduplication)
            exists = await self.db.fetch_one(
                "SELECT 1 FROM inbox WHERE message_id = $1",
                message.id
            )
            if exists:
                return  # Already processed
            
            # Process the message
            await self.process(message)
            
            # Record in inbox
            await self.db.execute(
                """INSERT INTO inbox (message_id, processed_at)
                   VALUES ($1, NOW())""",
                message.id
            )

CREATE TABLE inbox (
    message_id  VARCHAR(255) PRIMARY KEY,
    processed_at TIMESTAMP NOT NULL
);
-- Periodically clean old entries: DELETE FROM inbox WHERE processed_at < NOW() - INTERVAL '7 days'
```

---

### Idempotent Consumer

**Problem:** Messages may be delivered more than once.

**Solution:** Design handlers so processing the same message multiple times has the same effect as once.

```python
# Strategy 1: Dedup table (Inbox pattern above)

# Strategy 2: Natural idempotency (upsert)
async def handle_address_updated(self, event):
    await self.db.execute(
        """INSERT INTO customer_addresses (customer_id, address, updated_at)
           VALUES ($1, $2, $3)
           ON CONFLICT (customer_id) DO UPDATE 
           SET address = $2, updated_at = $3
           WHERE customer_addresses.updated_at < $3""",  # Only if newer
        event.customer_id, event.address, event.occurred_at
    )

# Strategy 3: Conditional processing (version check)
async def handle_order_shipped(self, event):
    result = await self.db.execute(
        """UPDATE orders SET status = 'shipped', version = version + 1
           WHERE id = $1 AND version = $2""",
        event.order_id, event.expected_version
    )
    if result.rowcount == 0:
        pass  # Already processed or outdated - skip
```

---

### Event Deduplication

```python
class EventDeduplicator:
    def __init__(self, redis_client, window_seconds=3600):
        self.redis = redis_client
        self.window = window_seconds
    
    async def is_duplicate(self, event_id: str) -> bool:
        key = f"event:seen:{event_id}"
        # SET NX returns True only if key didn't exist
        is_new = await self.redis.set(key, "1", nx=True, ex=self.window)
        return not is_new  # If set failed, it's a duplicate
    
    async def process(self, event):
        if await self.is_duplicate(event.id):
            return
        await self.handler.handle(event)
```

---

### Event Ordering Guarantees

**Strategies:**

```python
# 1. Partition key ordering (Kafka)
# All events for same entity go to same partition → ordered
producer.produce(topic='orders', key=order_id, value=event)

# 2. Sequence numbers in events
class OrderEvent:
    order_id: str
    sequence: int  # Monotonically increasing per order
    
# Consumer validates sequence
async def handle(self, event):
    last_seq = await self.get_last_sequence(event.order_id)
    if event.sequence <= last_seq:
        return  # Duplicate or out-of-order, skip
    if event.sequence > last_seq + 1:
        await self.buffer(event)  # Gap - buffer and wait
        return
    await self.process(event)
    await self.save_sequence(event.order_id, event.sequence)

# 3. Causal ordering (vector clocks)
# Only order events that are causally related
```

---

### Saga with Events (Choreography)

**Problem:** Distributed transaction across services.

**Solution:** Each service reacts to events and publishes its own events. No central coordinator.

```
┌─────────┐ OrderPlaced ┌─────────┐ PaymentProcessed ┌──────────┐
│  Order  │────────────▶│ Payment │──────────────────▶│ Shipping │
│ Service │             │ Service │                   │ Service  │
└────┬────┘             └────┬────┘                   └────┬─────┘
     │                       │                              │
     │  PaymentFailed        │                              │
     │◀──────────────────────┘                              │
     │                                                      │
     │  ShipmentCreated                                     │
     │◀─────────────────────────────────────────────────────┘
     │
     │ [Compensate if needed]
```

```python
# Order Service
class OrderService:
    async def handle_payment_processed(self, event: PaymentProcessed):
        order = await self.repo.get(event.order_id)
        order.confirm_payment()
        await self.repo.save(order)
        # ShippingRequested event auto-published via domain events
    
    async def handle_payment_failed(self, event: PaymentFailed):
        order = await self.repo.get(event.order_id)
        order.cancel("Payment failed")
        await self.repo.save(order)
        # OrderCancelled event triggers refund if needed

# Payment Service
class PaymentService:
    async def handle_order_placed(self, event: OrderPlaced):
        try:
            payment = await self.process_payment(event.customer_id, event.total)
            await publish(PaymentProcessed(order_id=event.order_id, payment_id=payment.id))
        except PaymentError:
            await publish(PaymentFailed(order_id=event.order_id, reason="declined"))
```

**Gotchas:**
- Hard to understand full flow (distributed across services)
- Hard to handle failures (what if event is lost?)
- Cyclic dependencies possible
- Use orchestration (Process Manager) for complex flows

---

### Process Manager Pattern

**Problem:** Complex business processes with many steps and conditional logic need coordination.

**Solution:** A stateful component tracks progress through a business process, sending commands and reacting to events.

```python
class OrderProcessManager:
    """Orchestrates the order fulfillment process."""
    
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.state = "started"
        self.payment_confirmed = False
        self.inventory_reserved = False
    
    async def handle(self, event):
        if isinstance(event, OrderPlaced) and self.state == "started":
            self.state = "awaiting_payment_and_inventory"
            await self.send_command(ProcessPayment(order_id=self.order_id, amount=event.total))
            await self.send_command(ReserveInventory(order_id=self.order_id, items=event.items))
        
        elif isinstance(event, PaymentProcessed):
            self.payment_confirmed = True
            await self._check_ready_to_ship()
        
        elif isinstance(event, InventoryReserved):
            self.inventory_reserved = True
            await self._check_ready_to_ship()
        
        elif isinstance(event, PaymentFailed):
            self.state = "compensating"
            await self.send_command(ReleaseInventory(order_id=self.order_id))
            await self.send_command(CancelOrder(order_id=self.order_id))
    
    async def _check_ready_to_ship(self):
        if self.payment_confirmed and self.inventory_reserved:
            self.state = "ready_to_ship"
            await self.send_command(CreateShipment(order_id=self.order_id))
```

**Difference from Choreography:**
- Choreography: no coordinator, services react independently
- Process Manager: central coordinator tracks state and sends commands

---

### Event Aggregator

**Problem:** Need to combine multiple events into a single aggregated event.

```python
class OrderCompletionAggregator:
    """Waits for all required events before emitting aggregated event."""
    
    def __init__(self, timeout_seconds=300):
        self.pending: Dict[str, Dict] = {}  # order_id -> collected events
        self.timeout = timeout_seconds
    
    async def handle_payment_confirmed(self, event):
        self._collect(event.order_id, "payment", event)
        await self._try_complete(event.order_id)
    
    async def handle_inventory_reserved(self, event):
        self._collect(event.order_id, "inventory", event)
        await self._try_complete(event.order_id)
    
    async def handle_fraud_cleared(self, event):
        self._collect(event.order_id, "fraud_check", event)
        await self._try_complete(event.order_id)
    
    async def _try_complete(self, order_id: str):
        collected = self.pending.get(order_id, {})
        required = {"payment", "inventory", "fraud_check"}
        
        if required.issubset(collected.keys()):
            await publish(OrderReadyForFulfillment(
                order_id=order_id,
                payment=collected["payment"],
                inventory=collected["inventory"]
            ))
            del self.pending[order_id]
```

---

## Schema Management

### Schema Registry

```
┌──────────┐    register schema    ┌─────────────────┐
│ Producer │──────────────────────▶│ Schema Registry │
└────┬─────┘                       └────────┬────────┘
     │ produce (schema_id + data)           │
     ▼                                      │
┌──────────┐                               │
│  Kafka   │                               │
└────┬─────┘                               │
     │ consume                              │
     ▼                                      │
┌──────────┐    fetch schema               │
│ Consumer │──────────────────────────────▶│
└──────────┘                               │
```

```python
# Confluent Schema Registry
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

schema_registry = SchemaRegistryClient({'url': 'http://schema-registry:8081'})

# Register/use Avro schema
avro_serializer = AvroSerializer(
    schema_registry,
    schema_str='''
    {
        "type": "record",
        "name": "OrderPlaced",
        "namespace": "com.example.events",
        "fields": [
            {"name": "order_id", "type": "string"},
            {"name": "customer_id", "type": "string"},
            {"name": "total", "type": "double"},
            {"name": "currency", "type": "string", "default": "USD"}
        ]
    }
    '''
)
```

---

### Avro vs Protobuf vs JSON Schema

| Aspect | Avro | Protobuf | JSON Schema |
|--------|------|----------|-------------|
| Format | Binary | Binary | Text (JSON) |
| Schema required to read | Yes | Yes (.proto) | No |
| Size | Smallest | Small | Largest |
| Speed | Fast | Fastest | Slowest |
| Schema evolution | Excellent | Good | Limited |
| Human readable | No (binary) | No (binary) | Yes |
| Language support | Good | Excellent | Excellent |
| Dynamic schema | Yes (schema in message or registry) | No (compile-time) | Yes |
| Best for | Kafka events | gRPC, internal APIs | REST APIs, config |

---

### Schema Evolution

```
Backward Compatible (new schema can read old data):
  Old: {order_id, amount}
  New: {order_id, amount, currency: "USD"}  ← added field with default
  New consumer reads old message → currency defaults to "USD" ✓

Forward Compatible (old schema can read new data):
  Old: {order_id, amount, currency}
  New: {order_id, amount}  ← removed optional field
  Old consumer reads new message → ignores missing optional field ✓

Full Compatible (both backward AND forward):
  Only add optional fields with defaults
  Only remove optional fields

Breaking Change (NOT compatible):
  - Removing required field
  - Changing field type
  - Renaming field
```

```python
# Confluent Schema Registry compatibility modes
# Set per subject (topic-key or topic-value)
requests.put(
    'http://schema-registry:8081/config/order-events-value',
    json={"compatibility": "BACKWARD"}  # BACKWARD, FORWARD, FULL, NONE
)
```

---

### Event Versioning Strategies

```python
# Strategy 1: Version in event type
"order.placed.v1"
"order.placed.v2"

# Strategy 2: Version field in event
{"event_type": "OrderPlaced", "version": 2, "data": {...}}

# Strategy 3: Content-based (duck typing)
# Consumer checks which fields exist and adapts

# Strategy 4: Envelope with schema reference
{
    "schema": "urn:com.example:OrderPlaced:v2",
    "data": {...}
}
```

---

## Real-world Architectures

### Netflix Event-Driven Architecture

**Key components:**
- **Keystone Pipeline:** Unified event streaming platform (trillions of events/day)
- **Apache Kafka** at the core for data pipeline
- **Real-time stream processing** for personalization, A/B testing, monitoring
- **Event Sourcing** for user interaction tracking (viewing history, ratings)

**Architecture:**
```
┌──────────┐     ┌─────────┐     ┌──────────────┐     ┌────────────┐
│ Services │────▶│  Kafka  │────▶│ Flink/Spark  │────▶│   S3/ES/   │
│(producers)│    │ clusters│     │  Processing  │     │  Cassandra │
└──────────┘     └─────────┘     └──────────────┘     └────────────┘
                                         │
                                         ▼
                                 ┌──────────────┐
                                 │  Real-time   │
                                 │   Alerts/    │
                                 │   ML Models  │
                                 └──────────────┘
```

**Key decisions:**
- Multiple Kafka clusters by use case (logging vs business events)
- Schema evolution with Avro + Schema Registry
- At-least-once delivery with idempotent consumers
- 700+ billion events/day

---

### Uber Event Processing

**Key components:**
- **Apache Kafka** with custom extensions
- **uReplicator** for cross-datacenter replication
- **Apache Flink** for real-time processing (trip pricing, fraud detection, ETA)
- **Event Sourcing** for trip state management

**Challenges solved:**
- Millions of trips/day → partitioning by city/region
- Real-time surge pricing → sub-second stream processing
- Driver-rider matching → event-driven state machines
- Cross-datacenter consistency → active-active with conflict resolution

---

### LinkedIn Kafka Usage

LinkedIn created Kafka! Key usage:
- **Activity tracking:** Billions of events/day (page views, clicks, searches)
- **Operational metrics:** System health monitoring
- **Change data capture:** Database changes streamed to consumers
- **Commit log:** Source of truth for derived systems

Scale: **7 trillion messages/day**, **100+ PB** stored.

---

### Walmart Event Sourcing

**Problem:** Black Friday scale (millions of concurrent checkouts) with consistency.

**Solution:**
- Event-sourced shopping cart (append-only, no locks)
- CQRS for cart reads (materialized views)
- Kafka for inter-service communication
- Saga pattern for checkout flow

```
Cart events: ItemAdded, ItemRemoved, QuantityChanged, CouponApplied
Derived: cart read model, inventory reservations, recommendations
```

**Benefits at scale:**
- No database contention (append-only writes)
- Cart state can be rebuilt from events
- Natural audit trail for disputes
- Horizontal scaling via partitioning

---

## Summary: Decision Matrix

| Scenario | Pattern |
|----------|---------|
| Need full audit trail | Event Sourcing |
| Different read/write models | CQRS |
| Cross-service data sync | Event-Carried State Transfer |
| Minimal coupling, fresh data OK | Event Notification |
| Atomic DB + event publish | Outbox Pattern |
| Distributed transactions | Saga (choreography or orchestration) |
| Complex multi-step process | Process Manager |
| Large payloads | Claim Check |
| Exactly-once processing | Idempotent Consumer + Inbox |
| High-throughput streaming | Kafka + Flink |
| Need replay/rebuild | Event Sourcing + Projections |
