# Data Management Patterns in Microservices

## Table of Contents
- [Database Patterns](#database-patterns)
- [Data Consistency Patterns](#data-consistency-patterns)
- [Data Query Patterns](#data-query-patterns)
- [Data Replication & Sync](#data-replication--sync)
- [Schema Evolution](#schema-evolution)

---

## Database Patterns

### Database per Service

**Problem:** Services sharing a single database creates tight coupling, schema change conflicts, and prevents independent deployment.

**Solution:** Each microservice owns its private database. No other service can access it directly.

**Architecture:**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Order Svc  │    │  User Svc   │    │ Product Svc │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                   │
       ▼                  ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Order DB   │    │  User DB    │    │ Product DB  │
│ (PostgreSQL)│    │  (MongoDB)  │    │   (Redis)   │
└─────────────┘    └─────────────┘    └─────────────┘
```

**Implementation Details:**
- Each service has exclusive ownership of its data store
- Communication happens only through APIs or events
- Services can choose the most appropriate database technology
- Database credentials are not shared between services

**Trade-offs:**
| Pros | Cons |
|------|------|
| Independent scaling | Cross-service queries are complex |
| Technology freedom | Data consistency is harder |
| Fault isolation | Data duplication |
| Independent deployment | Operational overhead (multiple DBs) |

**Real-world Example:** Netflix uses Cassandra for user viewing history, MySQL for billing, and ElasticSearch for search — each owned by different services.

---

### Shared Database (Anti-Pattern)

**Problem:** Teams want simplicity and strong consistency across services.

**Solution:** Multiple services share a single database instance and schema.

**Architecture:**
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Order Svc  │  │  User Svc   │  │ Product Svc │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                 │
       └────────────────┼─────────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │  Shared Database │
               │   (PostgreSQL)   │
               └─────────────────┘
```

**Why It's an Anti-Pattern:**
- Schema changes require coordinating all services
- Runtime coupling — one service's heavy query affects others
- Prevents polyglot persistence
- Tight coupling defeats the purpose of microservices
- Single point of failure

**When It Might Be Acceptable:**
- Early stages of migration from monolith
- Read-only reference data
- Small teams with few services (< 5)

**Trade-offs:**
| Pros | Cons |
|------|------|
| ACID transactions across services | Tight coupling |
| Simple queries | Schema change coordination |
| No data duplication | Cannot scale independently |
| Familiar development model | Technology lock-in |

**Real-world Example:** Many organizations start here during monolith decomposition and gradually migrate to database-per-service.

---

### Schema per Service

**Problem:** Need isolation benefits without managing multiple database instances.

**Solution:** Each service gets its own schema within a shared database instance, with strict access controls.

**Architecture:**
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Order Svc  │     │  User Svc   │     │ Product Svc │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌──────────────────────────────────────────────────────┐
│              PostgreSQL Instance                       │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐     │
│  │ orders   │   │ users    │   │ products     │     │
│  │ schema   │   │ schema   │   │ schema       │     │
│  └──────────┘   └──────────┘   └──────────────┘     │
└──────────────────────────────────────────────────────┘
```

**Implementation:**
```sql
-- Create schemas
CREATE SCHEMA orders AUTHORIZATION order_service;
CREATE SCHEMA users AUTHORIZATION user_service;
CREATE SCHEMA products AUTHORIZATION product_service;

-- Grant access only to owning service
GRANT ALL ON SCHEMA orders TO order_service;
REVOKE ALL ON SCHEMA orders FROM PUBLIC;
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| Logical isolation | Shared instance = shared resources |
| Lower operational cost | Still a single point of failure |
| Easy to set up | Temptation to do cross-schema joins |
| Good stepping stone | Same DB technology for all |

**Real-world Example:** Startups and small teams use this as a pragmatic middle ground while building out their microservices infrastructure.

---

### Private Tables per Service

**Problem:** Even lighter isolation needed within a shared database.

**Solution:** Each service has ownership over specific tables. Convention and access controls prevent other services from accessing those tables.

**Architecture:**
```
┌──────────────────────────────────────────┐
│            Shared Database                │
│                                          │
│  Order Svc owns:    User Svc owns:       │
│  ┌────────────┐    ┌─────────────┐      │
│  │ orders     │    │ users       │      │
│  │ order_items│    │ addresses   │      │
│  └────────────┘    └─────────────┘      │
│                                          │
│  Product Svc owns:                       │
│  ┌──────────────┐                        │
│  │ products     │                        │
│  │ categories   │                        │
│  └──────────────┘                        │
└──────────────────────────────────────────┘
```

**Implementation:**
- Use naming conventions (prefix tables with service name)
- Use database users with table-level grants
- Enforce via code reviews and CI checks

**Trade-offs:**
| Pros | Cons |
|------|------|
| Minimal infrastructure | Weakest isolation |
| Simple operations | Easy to violate boundaries |
| Good for migration | No technology diversity |

**Real-world Example:** Commonly used during early stages of monolith decomposition — "strangler fig" pattern where services are carved out one module at a time.

---

### Polyglot Persistence

**Problem:** Different services have different data access patterns — one size doesn't fit all.

**Solution:** Choose the optimal database technology for each service based on its specific requirements.

**Architecture:**
```
┌──────────────────────────────────────────────────────────────┐
│                    Microservices System                        │
│                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │ Catalog │    │  Order  │    │ Session │    │  Search │  │
│  │  Svc    │    │  Svc    │    │  Svc    │    │  Svc    │  │
│  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘  │
│       │              │              │              │         │
│       ▼              ▼              ▼              ▼         │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌──────────┐   │
│  │ MongoDB │   │PostgreSQL│   │  Redis  │   │Elastic   │   │
│  │(flexible│   │ (ACID,  │   │(fast    │   │Search    │   │
│  │ schema) │   │ relations│   │ expiry) │   │(full-text│   │
│  └─────────┘   └─────────┘   └─────────┘   └──────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**Choosing the Right Database:**

| Use Case | Database | Reason |
|----------|----------|--------|
| Transactions, relations | PostgreSQL/MySQL | ACID, joins |
| Flexible schema, documents | MongoDB | Schema evolution |
| Caching, sessions | Redis | Speed, TTL |
| Full-text search | Elasticsearch | Inverted index |
| Time series | InfluxDB/TimescaleDB | Time-based queries |
| Graph relationships | Neo4j | Traversal queries |
| Wide column, high write | Cassandra | Write throughput |
| Event streaming | Kafka (log) | Append-only, replay |

**Trade-offs:**
| Pros | Cons |
|------|------|
| Optimal performance per service | Operational complexity |
| Best tool for the job | Team must know multiple DBs |
| Independent scaling | Backup/monitoring complexity |

**Real-world Example:** Amazon uses DynamoDB for cart, RDS for orders, ElastiCache for sessions, Neptune for recommendations, and OpenSearch for product search.

---

## Data Consistency Patterns

### Saga Pattern

**Problem:** In a microservices architecture, a business transaction spans multiple services. You cannot use a traditional distributed transaction (2PC) due to availability concerns.

**Solution:** Implement a saga — a sequence of local transactions where each step publishes events or messages that trigger the next step. If a step fails, compensating transactions undo the preceding steps.

**Two Approaches:**

#### 1. Choreography-Based Saga

Each service listens for events and decides what to do next.

```
┌───────┐  OrderCreated  ┌────────┐  PaymentDone  ┌───────────┐
│ Order │ ──────────────► │Payment │ ─────────────►│ Inventory │
│  Svc  │                 │  Svc   │               │    Svc    │
└───┬───┘                 └────┬───┘               └─────┬─────┘
    │                          │                         │
    │    PaymentFailed         │   StockReserved         │
    │◄─────────────────────────┘         │               │
    │                                    ▼               │
    │                          ┌────────────────┐        │
    │                          │  Shipping Svc  │◄───────┘
    │                          └────────────────┘
    │                                    │
    │         ShipmentScheduled          │
    │◄───────────────────────────────────┘
```

**Code Example (Choreography with events):**

```java
// Order Service
@Service
public class OrderService {
    @Autowired private EventPublisher eventPublisher;
    @Autowired private OrderRepository orderRepo;

    public Order createOrder(CreateOrderRequest request) {
        Order order = new Order(request);
        order.setStatus(OrderStatus.PENDING);
        orderRepo.save(order);
        
        eventPublisher.publish(new OrderCreatedEvent(
            order.getId(),
            order.getCustomerId(),
            order.getItems(),
            order.getTotalAmount()
        ));
        return order;
    }

    @EventHandler
    public void onPaymentFailed(PaymentFailedEvent event) {
        Order order = orderRepo.findById(event.getOrderId());
        order.setStatus(OrderStatus.CANCELLED);
        orderRepo.save(order);
        // Compensating action: reject order
    }
}

// Payment Service
@Service
public class PaymentService {
    @EventHandler
    public void onOrderCreated(OrderCreatedEvent event) {
        try {
            Payment payment = processPayment(event.getCustomerId(), event.getAmount());
            eventPublisher.publish(new PaymentCompletedEvent(
                event.getOrderId(), payment.getId()
            ));
        } catch (InsufficientFundsException e) {
            eventPublisher.publish(new PaymentFailedEvent(
                event.getOrderId(), e.getMessage()
            ));
        }
    }
}

// Inventory Service
@Service
public class InventoryService {
    @EventHandler
    public void onPaymentCompleted(PaymentCompletedEvent event) {
        try {
            reserveStock(event.getOrderId());
            eventPublisher.publish(new StockReservedEvent(event.getOrderId()));
        } catch (OutOfStockException e) {
            // Compensating: trigger payment refund
            eventPublisher.publish(new StockReservationFailedEvent(event.getOrderId()));
        }
    }
}
```

#### 2. Orchestration-Based Saga

A central orchestrator tells participants what to do.

```
                    ┌──────────────────────┐
                    │   Saga Orchestrator  │
                    │   (Order Saga)       │
                    └──────────┬───────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ Payment Svc │    │Inventory Svc│    │Shipping Svc │
    │             │    │             │    │             │
    │ charge()    │    │ reserve()   │    │ schedule()  │
    │ refund()    │    │ release()   │    │ cancel()    │
    └─────────────┘    └─────────────┘    └─────────────┘
         action         action              action
         compensate     compensate          compensate
```

**Code Example (Orchestration):**

```java
// Saga Orchestrator
@Service
public class OrderSagaOrchestrator {
    
    private final StateMachine<OrderSagaState, OrderSagaEvent> stateMachine;
    
    public void startSaga(Order order) {
        SagaExecution saga = new SagaExecution(order.getId());
        saga.addStep(new SagaStep(
            "payment",
            () -> paymentService.charge(order.getCustomerId(), order.getAmount()),
            () -> paymentService.refund(order.getCustomerId(), order.getAmount())
        ));
        saga.addStep(new SagaStep(
            "inventory",
            () -> inventoryService.reserve(order.getItems()),
            () -> inventoryService.release(order.getItems())
        ));
        saga.addStep(new SagaStep(
            "shipping",
            () -> shippingService.schedule(order.getId(), order.getAddress()),
            () -> shippingService.cancel(order.getId())
        ));
        saga.execute();
    }
}

// Generic Saga Execution Engine
public class SagaExecution {
    private final List<SagaStep> steps = new ArrayList<>();
    private final String sagaId;
    
    public void execute() {
        int completedSteps = 0;
        try {
            for (SagaStep step : steps) {
                step.execute();
                completedSteps++;
            }
        } catch (Exception e) {
            // Compensate in reverse order
            for (int i = completedSteps - 1; i >= 0; i--) {
                try {
                    steps.get(i).compensate();
                } catch (Exception compensationError) {
                    log.error("Compensation failed for step {}", i, compensationError);
                    // Alert, manual intervention needed
                }
            }
        }
    }
}
```

**Choreography vs Orchestration:**

| Aspect | Choreography | Orchestration |
|--------|-------------|---------------|
| Coupling | Loose | Centralized |
| Complexity | Grows with services | Contained in orchestrator |
| Visibility | Hard to trace | Easy to monitor |
| Single point of failure | No | Orchestrator |
| Best for | Simple flows (3-4 steps) | Complex flows |

**Trade-offs:**
| Pros | Cons |
|------|------|
| No distributed transactions | Complexity |
| High availability | Eventual consistency |
| Service autonomy | Debugging is harder |
| Compensating actions handle failures | Compensations can fail too |

**Real-world Example:** Uber uses orchestrated sagas for ride booking — driver matching, fare calculation, payment, and notification are saga steps with compensations.

---

### Event Sourcing

**Problem:** Traditional CRUD overwrites state, losing history. You need a complete audit trail, temporal queries, and the ability to rebuild state.

**Solution:** Store state changes as a sequence of immutable events. Current state is derived by replaying events.

**Architecture:**
```
                    Commands                    Queries
                       │                          │
                       ▼                          ▼
              ┌─────────────────┐       ┌─────────────────┐
              │  Command Handler │       │  Query Handler  │
              └────────┬────────┘       └────────┬────────┘
                       │                         │
                       ▼                         ▼
              ┌─────────────────┐       ┌─────────────────┐
              │   Event Store   │──────►│  Read Model     │
              │  (append-only)  │ proj. │ (materialized)  │
              │                 │       │                 │
              │ OrderCreated    │       │ ┌─────────────┐ │
              │ ItemAdded       │       │ │ Order View  │ │
              │ ItemRemoved     │       │ └─────────────┘ │
              │ OrderConfirmed  │       └─────────────────┘
              │ OrderShipped    │
              └─────────────────┘
```

**Event Store Design:**

```sql
CREATE TABLE event_store (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id    UUID NOT NULL,
    aggregate_type  VARCHAR(255) NOT NULL,
    event_type      VARCHAR(255) NOT NULL,
    event_data      JSONB NOT NULL,
    metadata        JSONB,
    version         INTEGER NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (aggregate_id, version)  -- Optimistic concurrency
);

CREATE INDEX idx_events_aggregate ON event_store(aggregate_id, version);
CREATE INDEX idx_events_type ON event_store(event_type);
CREATE INDEX idx_events_created ON event_store(created_at);
```

**Implementation:**

```java
// Events
public sealed interface OrderEvent {
    UUID orderId();
}
public record OrderCreated(UUID orderId, UUID customerId, List<OrderItem> items) 
    implements OrderEvent {}
public record OrderItemAdded(UUID orderId, OrderItem item) implements OrderEvent {}
public record OrderConfirmed(UUID orderId, Instant confirmedAt) implements OrderEvent {}
public record OrderShipped(UUID orderId, String trackingNumber) implements OrderEvent {}

// Aggregate
public class OrderAggregate {
    private UUID id;
    private OrderStatus status;
    private List<OrderItem> items = new ArrayList<>();
    private int version = 0;
    
    // Rebuild state from events
    public static OrderAggregate fromEvents(List<OrderEvent> events) {
        OrderAggregate order = new OrderAggregate();
        for (OrderEvent event : events) {
            order.apply(event);
        }
        return order;
    }
    
    // Apply event to update state (no side effects)
    private void apply(OrderEvent event) {
        switch (event) {
            case OrderCreated e -> {
                this.id = e.orderId();
                this.status = OrderStatus.CREATED;
                this.items = new ArrayList<>(e.items());
            }
            case OrderItemAdded e -> this.items.add(e.item());
            case OrderConfirmed e -> this.status = OrderStatus.CONFIRMED;
            case OrderShipped e -> this.status = OrderStatus.SHIPPED;
        }
        this.version++;
    }
    
    // Command handler — validate, then produce event
    public OrderEvent confirm() {
        if (this.status != OrderStatus.CREATED) {
            throw new IllegalStateException("Can only confirm CREATED orders");
        }
        if (this.items.isEmpty()) {
            throw new IllegalStateException("Cannot confirm empty order");
        }
        return new OrderConfirmed(this.id, Instant.now());
    }
}

// Event Store Repository
@Repository
public class EventStoreRepository {
    @Autowired private JdbcTemplate jdbc;
    
    public void save(UUID aggregateId, String aggregateType, 
                     OrderEvent event, int expectedVersion) {
        try {
            jdbc.update("""
                INSERT INTO event_store (aggregate_id, aggregate_type, event_type, 
                                        event_data, version)
                VALUES (?, ?, ?, ?::jsonb, ?)
                """,
                aggregateId, aggregateType, 
                event.getClass().getSimpleName(),
                objectMapper.writeValueAsString(event),
                expectedVersion + 1
            );
        } catch (DuplicateKeyException e) {
            throw new OptimisticConcurrencyException(
                "Aggregate modified concurrently", e);
        }
    }
    
    public List<OrderEvent> getEvents(UUID aggregateId) {
        return jdbc.query("""
            SELECT event_type, event_data FROM event_store
            WHERE aggregate_id = ? ORDER BY version ASC
            """, (rs, row) -> deserialize(rs), aggregateId);
    }
}

// Snapshotting for performance
public class SnapshotStore {
    public void saveSnapshot(UUID aggregateId, OrderAggregate state, int version) {
        // Save every N events to avoid replaying entire history
    }
    
    public OrderAggregate loadWithSnapshot(UUID aggregateId) {
        Snapshot snapshot = getLatestSnapshot(aggregateId);
        List<OrderEvent> recentEvents = eventStore.getEventsAfter(
            aggregateId, snapshot.getVersion());
        OrderAggregate aggregate = snapshot.getState();
        recentEvents.forEach(aggregate::apply);
        return aggregate;
    }
}
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| Complete audit trail | Complexity |
| Temporal queries | Eventual consistency for reads |
| Event replay / debugging | Event schema evolution |
| Natural fit for CQRS | Storage grows indefinitely |
| Easy to add new projections | Steep learning curve |

**Real-world Example:** Banking systems use event sourcing for transaction history. Datomic database is built on immutable facts. Event Store DB is purpose-built for this pattern.

---

### CQRS (Command Query Responsibility Segregation)

**Problem:** Read and write models have different optimization needs. Complex queries slow down write operations. Read-heavy systems need different scaling than write-heavy ones.

**Solution:** Separate the read model (queries) from the write model (commands). Each can be independently optimized, scaled, and evolved.

**Architecture:**
```
         ┌─────────────────────────────────────────────────┐
         │                   Client                         │
         └──────────┬──────────────────────┬───────────────┘
                    │                      │
              Commands                  Queries
                    │                      │
                    ▼                      ▼
         ┌──────────────────┐    ┌──────────────────┐
         │  Command Service │    │  Query Service   │
         │  (Write Model)   │    │  (Read Model)    │
         └────────┬─────────┘    └────────┬─────────┘
                  │                        │
                  ▼                        ▼
         ┌──────────────────┐    ┌──────────────────┐
         │  Write Database  │    │  Read Database   │
         │  (Normalized,    │───►│  (Denormalized,  │
         │   PostgreSQL)    │events│  Elasticsearch) │
         └──────────────────┘    └──────────────────┘
```

**Implementation:**

```java
// Commands
public record CreateOrderCommand(UUID customerId, List<OrderItemDTO> items) {}
public record AddItemCommand(UUID orderId, OrderItemDTO item) {}

// Command Handler
@Service
public class OrderCommandHandler {
    @Autowired private EventStoreRepository eventStore;
    
    @CommandHandler
    public UUID handle(CreateOrderCommand cmd) {
        UUID orderId = UUID.randomUUID();
        OrderCreated event = new OrderCreated(orderId, cmd.customerId(), cmd.items());
        eventStore.save(orderId, "Order", event, 0);
        return orderId;
    }
    
    @CommandHandler
    public void handle(AddItemCommand cmd) {
        OrderAggregate order = loadAggregate(cmd.orderId());
        OrderEvent event = order.addItem(cmd.item());
        eventStore.save(cmd.orderId(), "Order", event, order.getVersion());
    }
}

// Query Model (Denormalized view)
@Document(indexName = "orders")
public class OrderView {
    private String orderId;
    private String customerName;  // denormalized
    private String customerEmail; // denormalized
    private List<OrderItemView> items;
    private BigDecimal totalAmount;
    private String status;
    private Instant createdAt;
}

// Projection — listens to events, updates read model
@Service
public class OrderProjection {
    @Autowired private ElasticsearchRepository<OrderView> readRepo;
    @Autowired private CustomerService customerService;
    
    @EventHandler
    public void on(OrderCreated event) {
        Customer customer = customerService.getCustomer(event.customerId());
        OrderView view = new OrderView();
        view.setOrderId(event.orderId().toString());
        view.setCustomerName(customer.getName());
        view.setItems(mapItems(event.items()));
        view.setTotalAmount(calculateTotal(event.items()));
        view.setStatus("CREATED");
        view.setCreatedAt(Instant.now());
        readRepo.save(view);
    }
    
    @EventHandler
    public void on(OrderShipped event) {
        OrderView view = readRepo.findById(event.orderId().toString());
        view.setStatus("SHIPPED");
        readRepo.save(view);
    }
}

// Query Handler
@Service
public class OrderQueryHandler {
    @Autowired private ElasticsearchRepository<OrderView> readRepo;
    
    public OrderView getOrder(UUID orderId) {
        return readRepo.findById(orderId.toString())
            .orElseThrow(() -> new OrderNotFoundException(orderId));
    }
    
    public Page<OrderView> searchOrders(String query, Pageable pageable) {
        return readRepo.search(query, pageable);
    }
    
    public List<OrderView> getCustomerOrders(UUID customerId, OrderStatus status) {
        return readRepo.findByCustomerIdAndStatus(customerId.toString(), status.name());
    }
}
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| Independent read/write scaling | Eventual consistency |
| Optimized read models | Complexity |
| Multiple read models possible | Data synchronization |
| Better separation of concerns | More infrastructure |

**Real-world Example:** Twitter separates write (tweet creation) from read (timeline generation). The timeline is a pre-computed read model (fan-out on write).

---

### Transactional Outbox Pattern

**Problem:** A service needs to update its database AND publish an event atomically. If the DB write succeeds but event publish fails (or vice versa), the system becomes inconsistent.

**Solution:** Write events to an "outbox" table in the same database transaction. A separate process reads the outbox and publishes to the message broker.

**Architecture:**
```
┌─────────────────────────────────────────────┐
│              Order Service                    │
│                                             │
│  ┌─────────────┐    ┌───────────────────┐  │
│  │  Business   │───►│  Same Transaction │  │
│  │   Logic     │    │                   │  │
│  └─────────────┘    │ 1. UPDATE orders  │  │
│                      │ 2. INSERT outbox  │  │
│                      └───────────────────┘  │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │         Database                     │    │
│  │  ┌──────────┐  ┌─────────────────┐  │    │
│  │  │  orders  │  │  outbox_events  │  │    │
│  │  └──────────┘  └────────┬────────┘  │    │
│  └─────────────────────────┼───────────┘    │
│                             │                │
│  ┌──────────────────────────┼──────────┐    │
│  │  Message Relay (poller / CDC)       │    │
│  └──────────────────────────┼──────────┘    │
└─────────────────────────────┼───────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Message Broker  │
                    │    (Kafka)       │
                    └──────────────────┘
```

**Implementation:**

```sql
CREATE TABLE outbox_events (
    id              UUID PRIMARY KEY,
    aggregate_type  VARCHAR(255) NOT NULL,
    aggregate_id    VARCHAR(255) NOT NULL,
    event_type      VARCHAR(255) NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMP NULL,
    status          VARCHAR(20) DEFAULT 'PENDING'
);
```

```java
@Service
@Transactional
public class OrderService {
    
    public Order createOrder(CreateOrderRequest request) {
        // 1. Business logic
        Order order = new Order(request);
        orderRepository.save(order);
        
        // 2. Write to outbox in same transaction
        OutboxEvent event = new OutboxEvent(
            UUID.randomUUID(),
            "Order",
            order.getId().toString(),
            "OrderCreated",
            objectMapper.writeValueAsString(new OrderCreatedPayload(order))
        );
        outboxRepository.save(event);
        
        return order;
    }
}

// Message Relay — polls outbox and publishes
@Scheduled(fixedDelay = 100)
public void publishOutboxEvents() {
    List<OutboxEvent> events = outboxRepo.findByStatus("PENDING", Limit.of(100));
    for (OutboxEvent event : events) {
        try {
            kafkaTemplate.send(event.getAggregateType(), event.getAggregateId(), 
                             event.getPayload()).get();
            event.setStatus("PUBLISHED");
            event.setPublishedAt(Instant.now());
            outboxRepo.save(event);
        } catch (Exception e) {
            log.warn("Failed to publish event {}", event.getId(), e);
        }
    }
}
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| Atomicity guaranteed | At-least-once delivery (consumers need idempotency) |
| No 2PC needed | Polling adds latency |
| Simple to implement | Outbox table grows (needs cleanup) |
| Works with any DB | Extra table and process |

**Real-world Example:** Debezium's outbox connector is the industry-standard implementation. Shopify uses this pattern for order processing events.

---

### Change Data Capture (CDC) with Debezium

**Problem:** You need to react to database changes in real-time without modifying application code or adding outbox logic.

**Solution:** Capture row-level changes from the database's transaction log (WAL in Postgres, binlog in MySQL) and stream them as events.

**Architecture:**
```
┌─────────────┐         ┌─────────────────────────────────┐
│  Service A  │────────►│         PostgreSQL               │
│  (writes)   │         │                                 │
└─────────────┘         │  ┌───────────────────────────┐  │
                        │  │  WAL (Write-Ahead Log)    │  │
                        │  └────────────┬──────────────┘  │
                        └───────────────┼─────────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │     Debezium Connector        │
                        │  (reads WAL, no app changes)  │
                        └───────────────┬───────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │       Apache Kafka            │
                        │  topic: dbserver.schema.table │
                        └───────────┬───────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │  Service B  │ │  Search Idx │ │  Analytics  │
            │  (reacts)   │ │  (updates)  │ │  (streams)  │
            └─────────────┘ └─────────────┘ └─────────────┘
```

**Debezium Configuration:**
```json
{
  "name": "orders-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "secret",
    "database.dbname": "orderdb",
    "database.server.name": "orderserver",
    "table.include.list": "public.orders,public.order_items",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_orders",
    "transforms": "outbox",
    "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
    "transforms.outbox.table.field.event.key": "aggregate_id",
    "transforms.outbox.table.field.event.payload": "payload",
    "transforms.outbox.route.topic.replacement": "orders.events"
  }
}
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| No application code changes | Infrastructure complexity |
| Captures all changes (even raw SQL) | Coupling to DB schema |
| Low latency | WAL retention management |
| Exactly-once with proper config | Connector failures need monitoring |

**Real-world Example:** LinkedIn uses CDC to keep their search index in sync. Airbnb uses Debezium for real-time data warehouse updates.

---

### Two-Phase Commit (2PC) and Why to Avoid

**Problem:** Need atomic transactions across multiple databases or services.

**Solution:** A coordinator manages a prepare phase (can you commit?) and a commit phase (do commit) across all participants.

**Architecture:**
```
┌──────────────────┐
│  Transaction     │
│  Coordinator     │
└────────┬─────────┘
         │
    Phase 1: PREPARE
         │
    ┌────┼────┐
    ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐
│ DB1 ││ DB2 ││ DB3 │   "Can you commit?"
└──┬──┘└──┬──┘└──┬──┘
   │      │      │
   └──────┼──────┘      All vote YES
          │
    Phase 2: COMMIT
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
┌─────┐┌─────┐┌─────┐
│ DB1 ││ DB2 ││ DB3 │   "Commit now!"
└─────┘└─────┘└─────┘
```

**Why to Avoid in Microservices:**
1. **Blocking** — participants hold locks during entire protocol
2. **Single point of failure** — coordinator crash leaves participants in doubt
3. **Reduced availability** — if any participant is down, all block
4. **Latency** — network round trips add significant delay
5. **Doesn't scale** — adding participants increases failure probability
6. **CAP theorem** — 2PC sacrifices availability for consistency

**When 2PC Might Be Acceptable:**
- Within a single service with multiple DBs (rare)
- XA transactions in a monolith
- When strong consistency is absolutely required AND the number of participants is small (2-3)

**Better Alternatives:**
| Instead of 2PC | Use |
|---------------|-----|
| Cross-service transactions | Saga Pattern |
| Atomic DB + event publish | Transactional Outbox |
| Data sync across services | CDC / Event Sourcing |

**Real-world Example:** Google Spanner uses a variant of 2PC internally but with TrueTime to reduce lock contention — most teams should not attempt this.

---

## Data Query Patterns

### API Composition

**Problem:** A query needs data from multiple services that each own different data.

**Solution:** An API composer (or API gateway) calls multiple services and joins/aggregates the results in memory.

**Architecture:**
```
┌──────────┐
│  Client  │
└────┬─────┘
     │
     ▼
┌──────────────────┐
│  API Composer    │
│  (Gateway/BFF)   │
└───┬──────┬───────┬─┘
    │      │       │
    ▼      ▼       ▼
┌──────┐┌───────┐┌────────┐
│Order ││Customer││Product │
│ Svc  ││  Svc  ││  Svc   │
└──────┘└───────┘└────────┘
```

**Implementation:**

```java
@RestController
public class OrderDetailController {
    
    @GetMapping("/order-details/{orderId}")
    public OrderDetailView getOrderDetail(@PathVariable UUID orderId) {
        // Parallel calls
        CompletableFuture<Order> orderFuture = 
            CompletableFuture.supplyAsync(() -> orderClient.getOrder(orderId));
        CompletableFuture<Customer> customerFuture = 
            orderFuture.thenCompose(order -> 
                CompletableFuture.supplyAsync(() -> 
                    customerClient.getCustomer(order.getCustomerId())));
        CompletableFuture<List<Product>> productsFuture = 
            orderFuture.thenCompose(order ->
                CompletableFuture.supplyAsync(() ->
                    productClient.getProducts(order.getProductIds())));
        
        // Compose result
        Order order = orderFuture.join();
        Customer customer = customerFuture.join();
        List<Product> products = productsFuture.join();
        
        return new OrderDetailView(order, customer, products);
    }
}
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| Simple to implement | Performance (multiple network calls) |
| No data duplication | Availability reduced (depends on all services) |
| Services stay decoupled | In-memory joins have limits |
| Works for simple queries | Not suitable for complex aggregations |

**Real-world Example:** E-commerce product pages composing data from inventory, pricing, reviews, and recommendation services.

---

### CQRS with Materialized Views

**Problem:** Complex read queries require joining data from multiple services, causing slow response times and high load.

**Solution:** Pre-compute and store query results as materialized views, updated asynchronously via events.

**Architecture:**
```
┌─────────┐  events  ┌────────────────────┐
│Order Svc│─────────►│                    │
└─────────┘          │  View Updater      │     ┌──────────────────┐
┌─────────┐  events  │  (Event Consumer)  │────►│ Materialized     │
│User Svc │─────────►│                    │     │ View Store       │
└─────────┘          │                    │     │ (Redis/Elastic)  │
┌─────────┐  events  │                    │     └────────┬─────────┘
│Prod Svc │─────────►│                    │              │
└─────────┘          └────────────────────┘              │
                                                         ▼
                                               ┌──────────────────┐
                                               │  Query Service   │
                                               │  (fast reads)    │
                                               └──────────────────┘
```

**Implementation:**

```java
// Materialized view: Customer Order Summary
@Document(collection = "customer_order_summaries")
public class CustomerOrderSummary {
    private String customerId;
    private String customerName;
    private int totalOrders;
    private BigDecimal totalSpent;
    private List<RecentOrder> recentOrders; // last 10
    private String preferredCategory;
    private Instant lastOrderDate;
}

// Event consumer that maintains the view
@Service
public class CustomerOrderSummaryProjection {
    
    @KafkaListener(topics = "order-events")
    public void onOrderEvent(OrderEvent event) {
        switch (event) {
            case OrderCreated e -> {
                CustomerOrderSummary summary = 
                    viewRepo.findById(e.customerId()).orElse(new CustomerOrderSummary());
                summary.setTotalOrders(summary.getTotalOrders() + 1);
                summary.setTotalSpent(summary.getTotalSpent().add(e.amount()));
                summary.getRecentOrders().add(0, new RecentOrder(e.orderId(), e.amount()));
                if (summary.getRecentOrders().size() > 10) {
                    summary.getRecentOrders().remove(10);
                }
                summary.setLastOrderDate(Instant.now());
                viewRepo.save(summary);
            }
        }
    }
}
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| Fast reads (pre-computed) | Eventual consistency |
| Scales read side independently | Storage duplication |
| Query-optimized data shape | View rebuild can be slow |
| Reduces load on source services | Event ordering matters |

**Real-world Example:** Netflix pre-computes personalized homepages as materialized views, updated when user activity events arrive.

---

### Event Sourcing Projections

**Problem:** You have an event store but need different query-optimized read models.

**Solution:** Create projections — event handlers that build specific read models by processing the event stream.

**Architecture:**
```
┌────────────────────────────┐
│        Event Store         │
│  (single source of truth) │
└──────┬───────┬───────┬─────┘
       │       │       │
       ▼       ▼       ▼
┌──────────┐┌──────────┐┌──────────────┐
│Projection││Projection││Projection    │
│    A     ││    B     ││    C         │
│(list view││(search)  ││(analytics)   │
└────┬─────┘└────┬─────┘└────┬─────────┘
     │           │            │
     ▼           ▼            ▼
┌─────────┐┌──────────┐┌──────────────┐
│PostgreSQL││Elastic   ││ClickHouse   │
│(relational││Search   ││(columnar)   │
│  views)  ││(full-text││             │
└──────────┘└──────────┘└─────────────┘
```

**Key Concepts:**
- Projections can be rebuilt from scratch by replaying events
- Each projection tracks its last processed event position
- New projections can be added without changing the write side
- Projections can be caught up at different rates

**Real-world Example:** Event-sourced banking systems project account balances, transaction histories, monthly statements, and fraud detection models — all from the same event stream.

---

### GraphQL Federation for Distributed Queries

**Problem:** Clients need to query data across multiple services in a single request without knowing service boundaries.

**Solution:** Each service exposes a GraphQL subgraph. A federation gateway composes them into a unified supergraph.

**Architecture:**
```
┌──────────┐
│  Client  │  single GraphQL query
└────┬─────┘
     │
     ▼
┌──────────────────────┐
│  Federation Gateway  │
│  (Apollo Router)     │
│  Unified Supergraph  │
└───┬──────┬───────┬───┘
    │      │       │
    ▼      ▼       ▼
┌───────┐┌───────┐┌────────┐
│Users  ││Orders ││Products│
│Subgraph│Subgraph│Subgraph│
└───────┘└───────┘└────────┘
```

**Implementation:**

```graphql
# Users Subgraph
type User @key(fields: "id") {
  id: ID!
  name: String!
  email: String!
}

# Orders Subgraph
type Order @key(fields: "id") {
  id: ID!
  user: User!    # resolved via federation
  items: [OrderItem!]!
  total: Float!
}

type User @key(fields: "id") @extends {
  id: ID! @external
  orders: [Order!]!  # extend User with orders
}

# Client can query:
query {
  user(id: "123") {
    name
    email
    orders {
      id
      total
      items { productName }
    }
  }
}
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| Single client query | Gateway complexity |
| Type-safe schema | N+1 query problem |
| Each team owns their subgraph | Performance overhead |
| Automatic query planning | Schema coordination needed |

**Real-world Example:** Netflix, Expedia, and Walmart use Apollo Federation to unify hundreds of microservices behind a single GraphQL API.

---

## Data Replication & Sync

### Event-Driven Data Replication

**Problem:** Services need local copies of data owned by other services for performance and availability.

**Solution:** Services publish domain events when their data changes. Consuming services maintain local replicas by processing these events.

**Architecture:**
```
┌─────────────┐  UserUpdated   ┌──────────────────┐
│  User Svc   │───────────────►│  Message Broker  │
│ (source of  │                │     (Kafka)      │
│   truth)    │                └───────┬──────────┘
└─────────────┘                        │
                                ┌──────┼──────┐
                                ▼      ▼      ▼
                         ┌──────┐┌──────┐┌──────┐
                         │Order ││Notif ││Billing│
                         │ Svc  ││ Svc  ││ Svc  │
                         │      ││      ││      │
                         │local ││local ││local │
                         │copy  ││copy  ││copy  │
                         └──────┘└──────┘└──────┘
```

**Key Principles:**
- Source of truth remains with the owning service
- Replicas are eventually consistent
- Consumers store only the fields they need
- Events should include enough data (fat events vs thin events)

**Trade-offs:**
| Pros | Cons |
|------|------|
| Service autonomy | Eventual consistency |
| No runtime dependency | Data duplication |
| Fast local reads | Event ordering challenges |
| Fault tolerance | Stale data possible |

---

### Data Mesh Principles

**Problem:** Centralized data teams become bottlenecks. Data lakes turn into swamps. No clear ownership of data quality.

**Solution:** Apply microservices principles to data architecture — domain ownership, data as a product, self-serve infrastructure, and federated governance.

**Four Principles:**

```
┌─────────────────────────────────────────────────────────┐
│                     DATA MESH                            │
│                                                         │
│  1. Domain Ownership     2. Data as a Product           │
│  ┌──────────────────┐   ┌──────────────────┐           │
│  │ Each domain team │   │ Discoverable     │           │
│  │ owns its data    │   │ Addressable      │           │
│  │ (analytical too) │   │ Trustworthy      │           │
│  └──────────────────┘   │ Self-describing  │           │
│                          │ Secure           │           │
│  3. Self-Serve Platform  └──────────────────┘           │
│  ┌──────────────────┐   4. Federated Governance        │
│  │ Infrastructure   │   ┌──────────────────┐           │
│  │ as a platform    │   │ Global standards │           │
│  │ (data infra,     │   │ Local autonomy   │           │
│  │  pipelines)      │   │ Interoperability │           │
│  └──────────────────┘   └──────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

**Real-world Example:** Zalando, ThoughtWorks clients, and JP Morgan Chase have adopted data mesh to scale analytical data ownership across hundreds of teams.

---

### Data Lake vs Data Warehouse in Microservices

| Aspect | Data Lake | Data Warehouse |
|--------|-----------|----------------|
| Schema | Schema-on-read | Schema-on-write |
| Data types | Raw, unstructured | Structured, curated |
| Users | Data scientists | Business analysts |
| Processing | Batch + streaming | Mostly batch |
| Cost | Cheaper storage | Expensive compute |
| Tools | Spark, Flink | Snowflake, BigQuery, Redshift |
| In microservices | Collect all events raw | Curated business views |

**Modern approach: Lakehouse** (Delta Lake, Apache Iceberg) — combines both.

---

### Master Data Management

**Problem:** Core entities (Customer, Product) are referenced across many services. Which service is the "master"?

**Solution:** Designate a single service as the system of record for each entity. Other services maintain local projections.

```
┌─────────────────────────────────────────┐
│  Customer MDM (Master Data Management)  │
│  System of Record: Customer Service     │
│                                         │
│  Golden Record:                         │
│  - customer_id (globally unique)        │
│  - canonical name, email, address       │
│  - created/updated timestamps           │
└─────────────────────┬───────────────────┘
                      │ events
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ Billing │  │  Order  │  │Marketing│
   │(name,   │  │(name,   │  │(name,   │
   │ address)│  │ address)│  │ email,  │
   │         │  │         │  │ prefs)  │
   └─────────┘  └─────────┘  └─────────┘
```

---

### Reference Data Management

**Problem:** Slowly-changing lookup data (countries, currencies, product categories) is needed by many services.

**Solution:** Centralize reference data in a dedicated service or configuration, replicate to consumers.

**Approaches:**
1. **Reference Data Service** — API for lookups, cached locally
2. **Configuration-based** — embedded in service config, deployed with updates
3. **Event-based sync** — publish changes, services update local copies

---

### Cache-Aside Pattern

**Problem:** Database reads are slow for frequently accessed data.

**Solution:** Application checks cache first. On miss, loads from DB, then populates cache.

**Flow:**
```
┌────────┐     1. GET     ┌─────────┐
│ Client │───────────────►│  Cache  │
└────────┘                │ (Redis) │
     │                    └────┬────┘
     │                         │
     │    2. Cache MISS        │
     │                         │
     │    3. Query DB     ┌────┴────┐
     │───────────────────►│   DB    │
     │                    └────┬────┘
     │                         │
     │    4. Return data       │
     │◄────────────────────────┘
     │
     │    5. PUT in cache ┌─────────┐
     │───────────────────►│  Cache  │
     │                    └─────────┘
```

**Implementation:**

```java
public Product getProduct(String productId) {
    // 1. Check cache
    Product cached = cache.get("product:" + productId);
    if (cached != null) return cached;
    
    // 2. Load from DB
    Product product = productRepository.findById(productId)
        .orElseThrow(() -> new NotFoundException(productId));
    
    // 3. Populate cache with TTL
    cache.put("product:" + productId, product, Duration.ofMinutes(30));
    
    return product;
}

// Invalidation on write
public Product updateProduct(String productId, UpdateRequest request) {
    Product product = productRepository.save(mapToEntity(request));
    cache.evict("product:" + productId);  // invalidate
    return product;
}
```

**Trade-offs:**
| Pros | Cons |
|------|------|
| Simple to implement | Cache invalidation complexity |
| Reduces DB load | Stale data possible |
| Lazy population (only hot data) | Cache miss penalty |
| Resilient (cache failure = slower, not broken) | Thundering herd on expiry |

---

### Write-Through / Write-Behind Caching

**Write-Through:** Write to cache and DB synchronously.

```
Client ──► Cache ──► DB   (both updated on write)
```

**Write-Behind (Write-Back):** Write to cache immediately, async flush to DB.

```
Client ──► Cache ──async──► DB   (cache updated first, DB eventually)
```

| Aspect | Write-Through | Write-Behind |
|--------|--------------|--------------|
| Consistency | Strong | Eventual |
| Write latency | Higher (both writes) | Lower (cache only) |
| Data loss risk | Low | Risk if cache fails before flush |
| Use case | Financial data | High write throughput |

---

### Read Replicas

**Problem:** Read-heavy workload overwhelms the primary database.

**Solution:** Create read-only copies of the database. Route reads to replicas, writes to primary.

```
┌────────────┐
│   Primary  │───replication──┬──────────────┐
│   (writes) │                │              │
└────────────┘                ▼              ▼
                        ┌──────────┐   ┌──────────┐
                        │ Replica 1│   │ Replica 2│
                        │ (reads)  │   │ (reads)  │
                        └──────────┘   └──────────┘
```

**Key considerations:**
- Replication lag (reads may see stale data)
- Read-after-write consistency (route user's own writes to primary)
- Failover / promotion strategy

---

## Schema Evolution

### Schema Registry (Avro, Protobuf)

**Problem:** Services exchange messages. Schema changes can break consumers.

**Solution:** Use a schema registry to manage, validate, and enforce compatibility of message schemas.

**Architecture:**
```
┌──────────────┐                    ┌──────────────┐
│  Producer    │───register────────►│   Schema     │
│  (serialize) │◄──schema id────────│   Registry   │
└──────┬───────┘                    │  (Confluent) │
       │                            └──────┬───────┘
       │ message (schema id + data)        │
       ▼                                   │
┌──────────────┐                           │
│    Kafka     │                           │
└──────┬───────┘                           │
       │                                   │
       ▼                                   │
┌──────────────┐                           │
│  Consumer    │───fetch schema───────────►│
│ (deserialize)│◄──schema────────────────── │
└──────────────┘
```

**Avro Schema Example:**
```json
{
  "type": "record",
  "name": "OrderEvent",
  "namespace": "com.example.orders",
  "fields": [
    {"name": "orderId", "type": "string"},
    {"name": "customerId", "type": "string"},
    {"name": "amount", "type": "double"},
    {"name": "currency", "type": "string", "default": "USD"},
    {"name": "metadata", "type": ["null", "string"], "default": null}
  ]
}
```

---

### Backward/Forward Compatibility

| Compatibility Type | Rule | Example |
|-------------------|------|---------|
| **Backward** | New schema can read old data | Add field with default |
| **Forward** | Old schema can read new data | Remove optional field |
| **Full** | Both directions work | Only add/remove optional fields |
| **None** | No guarantees | Breaking change |

**Safe Changes:**
- Add a field with a default value (backward compatible)
- Remove a field that had a default (forward compatible)
- Add an optional field

**Breaking Changes:**
- Remove a required field
- Rename a field
- Change field type

---

### Schema Versioning Strategies

1. **URL versioning:** `/api/v1/orders`, `/api/v2/orders`
2. **Header versioning:** `Accept: application/vnd.company.v2+json`
3. **Schema Registry versioning:** Schema ID embedded in message
4. **Event type versioning:** `OrderCreatedV1`, `OrderCreatedV2`

**Best Practice:** Support N-1 and N versions simultaneously. Deprecate with long runways.

---

### Database Migration Strategies (Flyway, Liquibase)

**Problem:** Database schema must evolve with service code. Manual migrations are error-prone.

**Solution:** Version-controlled, automated database migrations that run on deployment.

**Flyway Example:**

```
src/main/resources/db/migration/
├── V1__create_orders_table.sql
├── V2__add_status_column.sql
├── V3__create_order_items_table.sql
└── V4__add_index_on_customer_id.sql
```

```sql
-- V1__create_orders_table.sql
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- V2__add_status_column.sql
ALTER TABLE orders ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PENDING';
```

**Zero-Downtime Migration Strategy (Expand-Contract):**

```
Phase 1 (Expand):     Add new column (nullable)
Phase 2 (Migrate):    Backfill data, deploy code that writes both
Phase 3 (Contract):   Remove old column after all services updated
```

**Trade-offs:**
| Flyway | Liquibase |
|--------|-----------|
| SQL-based (simple) | XML/YAML/JSON (flexible) |
| Convention over config | Rollback support built-in |
| Lightweight | Database diff generation |
| Linear versioning | Changelog with changesets |

**Real-world Example:** Stripe uses expand-contract migrations to maintain zero downtime during schema changes across thousands of tables.
