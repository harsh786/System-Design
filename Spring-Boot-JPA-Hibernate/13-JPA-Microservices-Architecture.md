# JPA in Microservices Architecture (Staff Engineer / Architect Level)

> This document covers how to use JPA effectively in microservices, solving distributed data management challenges with patterns like Outbox, Saga, CQRS, and CDC.

---

## 1. The Problem: Distributed Transactions

### Why 2PC Doesn't Work in Microservices

```
Traditional Monolith:
┌─────────────────────────────────────────┐
│  Single Database Transaction             │
│  ├─ Create Order                         │
│  ├─ Debit Payment                        │
│  ├─ Reserve Inventory                    │
│  └─ COMMIT (all or nothing)             │
└─────────────────────────────────────────┘

Microservices:
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Order Service │   │Payment Service│   │Inventory Svc │
│ ┌──────────┐ │   │ ┌──────────┐ │   │ ┌──────────┐ │
│ │ Order DB │ │   │ │Payment DB│ │   │ │ Stock DB │ │
│ └──────────┘ │   │ └──────────┘ │   │ └──────────┘ │
└──────────────┘   └──────────────┘   └──────────────┘

Problem: No single transaction spans all 3 databases!
```

**2PC (Two-Phase Commit) problems:**
- **Performance**: Locks held across network calls (high latency)
- **Availability**: If coordinator fails, all participants blocked
- **Coupling**: All services must support XA transactions
- **Scalability**: Distributed locks severely limit throughput
- **NoSQL incompatibility**: Many modern databases don't support 2PC

### The Dual-Write Problem

```
WRONG approach - writing to DB and message broker:
─────────────────────────────────────────────────────
1. orderRepository.save(order);     ← DB write succeeds
2. kafkaTemplate.send("orders", orderEvent);  ← What if this FAILS?
   
   → Order saved but event never published
   → Other services never know about the order
   → INCONSISTENCY!

Or reverse:
1. kafkaTemplate.send("orders", orderEvent);  ← Event published
2. orderRepository.save(order);     ← What if this FAILS?
   
   → Event published but order never saved
   → Other services process a phantom order
   → INCONSISTENCY!
─────────────────────────────────────────────────────

No matter the order: without a single atomic operation
spanning both DB and broker, you risk inconsistency.
```

---

## 2. Transactional Outbox Pattern (Deep Implementation)

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Order Service                                             │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │  @Transactional (SINGLE DB TRANSACTION)            │  │
│  │  ├─ INSERT INTO orders (...)                       │  │
│  │  └─ INSERT INTO outbox_events (...)                │  │
│  │     Both writes in SAME transaction = atomic!      │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌────────────────────────────────┐                      │
│  │ Outbox Publisher               │                      │
│  │ (Polling or CDC)               │──────→ Kafka/RabbitMQ│
│  │ Reads outbox, publishes events │                      │
│  └────────────────────────────────┘                      │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

### JPA Entity Design

```java
@Entity
@Table(name = "outbox_events")
public class OutboxEvent {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private String aggregateType;  // "Order", "Payment"
    
    @Column(nullable = false)
    private String aggregateId;    // "order-123"
    
    @Column(nullable = false)
    private String eventType;      // "OrderCreated", "OrderCancelled"
    
    @Column(columnDefinition = "TEXT", nullable = false)
    private String payload;        // JSON serialized event data
    
    @Column(nullable = false)
    private Instant createdAt;
    
    @Column(nullable = false)
    private boolean published = false;
    
    private Instant publishedAt;
    
    // Used as Kafka partition key for ordering
    // Events for same aggregate go to same partition → ordered
    public String getPartitionKey() {
        return aggregateType + "-" + aggregateId;
    }
}
```

### Service Implementation

```java
@Service
public class OrderService {
    
    @Autowired private OrderRepository orderRepository;
    @Autowired private OutboxEventRepository outboxRepository;
    @Autowired private ObjectMapper objectMapper;
    
    @Transactional  // SINGLE transaction for both writes
    public Order createOrder(CreateOrderRequest request) {
        // 1. Business logic
        Order order = new Order();
        order.setCustomerId(request.getCustomerId());
        order.setItems(mapItems(request.getItems()));
        order.setStatus(OrderStatus.CREATED);
        order.setTotal(calculateTotal(order.getItems()));
        
        Order saved = orderRepository.save(order);
        
        // 2. Write event to outbox (same transaction!)
        OrderCreatedEvent event = new OrderCreatedEvent(
            saved.getId(),
            saved.getCustomerId(),
            saved.getTotal(),
            saved.getItems().stream()
                .map(i -> new OrderItemDTO(i.getProductId(), i.getQuantity()))
                .toList()
        );
        
        OutboxEvent outboxEvent = new OutboxEvent();
        outboxEvent.setAggregateType("Order");
        outboxEvent.setAggregateId(saved.getId().toString());
        outboxEvent.setEventType("OrderCreated");
        outboxEvent.setPayload(objectMapper.writeValueAsString(event));
        outboxEvent.setCreatedAt(Instant.now());
        
        outboxRepository.save(outboxEvent);
        
        return saved;
        // COMMIT: both order AND outbox event persisted atomically
    }
}
```

### Polling Publisher

```java
@Component
public class OutboxPollingPublisher {
    
    @Autowired private OutboxEventRepository outboxRepository;
    @Autowired private KafkaTemplate<String, String> kafkaTemplate;
    
    @Scheduled(fixedDelay = 100)  // Poll every 100ms
    @Transactional
    public void publishPendingEvents() {
        List<OutboxEvent> events = outboxRepository
            .findTop100ByPublishedFalseOrderByCreatedAtAsc();
        
        for (OutboxEvent event : events) {
            try {
                kafkaTemplate.send(
                    "domain-events." + event.getAggregateType().toLowerCase(),
                    event.getPartitionKey(),  // Partition key for ordering
                    event.getPayload()
                ).get();  // Wait for Kafka acknowledgment
                
                event.setPublished(true);
                event.setPublishedAt(Instant.now());
                outboxRepository.save(event);
            } catch (Exception e) {
                log.error("Failed to publish event {}: {}", event.getId(), e.getMessage());
                break;  // Stop processing, retry next cycle
            }
        }
    }
    
    // Cleanup: delete old published events
    @Scheduled(cron = "0 0 2 * * *")  // Daily at 2 AM
    @Transactional
    public void cleanupOldEvents() {
        Instant cutoff = Instant.now().minus(7, ChronoUnit.DAYS);
        outboxRepository.deleteByPublishedTrueAndPublishedAtBefore(cutoff);
    }
}
```

### CDC-Based Publisher (Debezium)

```
┌─────────────────────────────────────────────────────────────┐
│ CDC Approach (No Polling Needed)                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Order Service                                               │
│  ├─ Writes to orders table + outbox_events table            │
│  └─ DONE (no polling publisher in application)              │
│                                                               │
│  Debezium Connector (external process):                      │
│  ├─ Reads PostgreSQL WAL / MySQL binlog                     │
│  ├─ Captures INSERT on outbox_events table                  │
│  ├─ Transforms to event message                              │
│  └─ Publishes to Kafka topic                                 │
│                                                               │
│  Advantages over polling:                                    │
│  ├─ Near real-time (ms latency vs polling interval)         │
│  ├─ No polling queries hitting the database                  │
│  ├─ Exactly-once semantics (with Kafka Connect)             │
│  └─ Outbox table can be truncated immediately               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Debezium outbox connector configuration:**
```json
{
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "db-host",
    "database.port": "5432",
    "database.user": "debezium",
    "database.dbname": "orderdb",
    "table.include.list": "public.outbox_events",
    "transforms": "outbox",
    "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
    "transforms.outbox.table.field.event.key": "aggregate_id",
    "transforms.outbox.table.field.event.type": "event_type",
    "transforms.outbox.table.field.event.payload": "payload",
    "transforms.outbox.route.topic.replacement": "domain-events.${routedByValue}"
}
```

### Idempotency on Consumer Side

```java
@Component
public class PaymentEventConsumer {
    
    @Autowired private ProcessedEventRepository processedEventRepo;
    @Autowired private PaymentService paymentService;
    
    @KafkaListener(topics = "domain-events.order")
    @Transactional
    public void handleOrderCreated(ConsumerRecord<String, String> record) {
        String eventId = record.headers().lastHeader("event-id").value().toString();
        
        // Idempotency check: have we processed this event before?
        if (processedEventRepo.existsById(eventId)) {
            log.info("Event {} already processed, skipping", eventId);
            return;
        }
        
        // Process the event
        OrderCreatedEvent event = objectMapper.readValue(record.value(), OrderCreatedEvent.class);
        paymentService.initiatePayment(event.getOrderId(), event.getTotal());
        
        // Record that we processed this event (same transaction)
        processedEventRepo.save(new ProcessedEvent(eventId, Instant.now()));
    }
}

@Entity
@Table(name = "processed_events")
public class ProcessedEvent {
    @Id
    private String eventId;  // Unique event identifier
    private Instant processedAt;
}
```

---

## 3. Saga Pattern with JPA

### Orchestration-Based Saga

```
┌─────────────────────────────────────────────────────────────┐
│                   SAGA ORCHESTRATOR                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  OrderSaga orchestrates:                                     │
│                                                               │
│  Step 1: Create Order (PENDING)                              │
│       │                                                       │
│       ▼                                                       │
│  Step 2: Reserve Payment ─────── fail? ──→ Cancel Order     │
│       │                                                       │
│       ▼                                                       │
│  Step 3: Reserve Inventory ───── fail? ──→ Refund Payment   │
│       │                                       │               │
│       ▼                                       └──→ Cancel Ord│
│  Step 4: Confirm Order                                       │
│       │                                                       │
│       ▼                                                       │
│  SUCCESS: Order CONFIRMED                                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

#### Saga State Entity

```java
@Entity
@Table(name = "saga_instances")
public class SagaInstance {
    
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String sagaId;
    
    @Column(nullable = false)
    private String sagaType;  // "OrderPlacementSaga"
    
    @Enumerated(EnumType.STRING)
    private SagaStatus status;  // STARTED, COMPENSATING, COMPLETED, FAILED
    
    @Column(nullable = false)
    private int currentStep;
    
    @Column(columnDefinition = "TEXT")
    private String sagaData;  // JSON: all data needed across steps
    
    @Column(columnDefinition = "TEXT")
    private String stepResults;  // JSON: results from each completed step
    
    private Instant startedAt;
    private Instant completedAt;
    private String failureReason;
    
    @Version
    private int version;  // Optimistic locking for concurrent saga updates
}
```

#### Saga Step Definition

```java
public interface SagaStep<T> {
    String getStepName();
    StepResult execute(T sagaData);
    StepResult compensate(T sagaData);
}

@Component
public class ReservePaymentStep implements SagaStep<OrderSagaData> {
    
    @Autowired private PaymentServiceClient paymentClient;
    
    @Override
    public String getStepName() { return "RESERVE_PAYMENT"; }
    
    @Override
    public StepResult execute(OrderSagaData data) {
        try {
            PaymentReservation reservation = paymentClient.reservePayment(
                data.getCustomerId(), data.getTotalAmount(), data.getOrderId());
            data.setPaymentReservationId(reservation.getId());
            return StepResult.success();
        } catch (InsufficientFundsException e) {
            return StepResult.failure("Insufficient funds");
        }
    }
    
    @Override
    public StepResult compensate(OrderSagaData data) {
        if (data.getPaymentReservationId() != null) {
            paymentClient.cancelReservation(data.getPaymentReservationId());
        }
        return StepResult.success();
    }
}
```

#### Saga Orchestrator

```java
@Service
public class OrderSagaOrchestrator {
    
    private final List<SagaStep<OrderSagaData>> steps;
    private final SagaInstanceRepository sagaRepository;
    private final ObjectMapper objectMapper;
    
    public OrderSagaOrchestrator(
            ReservePaymentStep paymentStep,
            ReserveInventoryStep inventoryStep,
            ConfirmOrderStep confirmStep,
            SagaInstanceRepository sagaRepository,
            ObjectMapper objectMapper) {
        this.steps = List.of(paymentStep, inventoryStep, confirmStep);
        this.sagaRepository = sagaRepository;
        this.objectMapper = objectMapper;
    }
    
    @Transactional
    public String startSaga(OrderSagaData data) {
        SagaInstance saga = new SagaInstance();
        saga.setSagaType("OrderPlacementSaga");
        saga.setStatus(SagaStatus.STARTED);
        saga.setCurrentStep(0);
        saga.setSagaData(objectMapper.writeValueAsString(data));
        saga.setStartedAt(Instant.now());
        
        sagaRepository.save(saga);
        
        // Execute first step
        executeNextStep(saga, data);
        
        return saga.getSagaId();
    }
    
    @Transactional
    public void executeNextStep(SagaInstance saga, OrderSagaData data) {
        while (saga.getCurrentStep() < steps.size()) {
            SagaStep<OrderSagaData> step = steps.get(saga.getCurrentStep());
            
            StepResult result = step.execute(data);
            
            if (result.isSuccess()) {
                saga.setCurrentStep(saga.getCurrentStep() + 1);
                saga.setSagaData(objectMapper.writeValueAsString(data));
                sagaRepository.save(saga);
            } else {
                // Step failed → start compensation
                saga.setStatus(SagaStatus.COMPENSATING);
                saga.setFailureReason(result.getErrorMessage());
                sagaRepository.save(saga);
                compensate(saga, data);
                return;
            }
        }
        
        // All steps completed
        saga.setStatus(SagaStatus.COMPLETED);
        saga.setCompletedAt(Instant.now());
        sagaRepository.save(saga);
    }
    
    @Transactional
    public void compensate(SagaInstance saga, OrderSagaData data) {
        // Compensate in reverse order up to current step
        for (int i = saga.getCurrentStep() - 1; i >= 0; i--) {
            SagaStep<OrderSagaData> step = steps.get(i);
            StepResult result = step.compensate(data);
            
            if (!result.isSuccess()) {
                // Compensation failed! Need manual intervention
                saga.setStatus(SagaStatus.FAILED);
                saga.setFailureReason("Compensation failed at step: " + step.getStepName());
                sagaRepository.save(saga);
                alertOpsTeam(saga);
                return;
            }
        }
        
        saga.setStatus(SagaStatus.COMPENSATED);
        saga.setCompletedAt(Instant.now());
        sagaRepository.save(saga);
    }
}
```

### Choreography-Based Saga

```
┌────────────────────────────────────────────────────────────────┐
│ Choreography: Each service reacts to events independently      │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Order Service          Payment Service       Inventory Service │
│       │                       │                      │          │
│  OrderCreated ───────────────→│                      │          │
│       │                       │                      │          │
│       │               PaymentReserved ──────────────→│          │
│       │                       │                      │          │
│       │                       │              InventoryReserved  │
│       │←──────────────────────────────────────────────│          │
│       │                       │                      │          │
│  OrderConfirmed               │                      │          │
│                                                                  │
│  If InventoryReservationFailed:                                 │
│       │                       │                      │          │
│       │               PaymentRefunded ←──────────────│          │
│       │                       │                      │          │
│  OrderCancelled ←─────────────│                      │          │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

```java
// Payment Service - reacts to OrderCreated
@Component
public class OrderCreatedHandler {
    
    @Autowired private PaymentRepository paymentRepo;
    @Autowired private OutboxEventRepository outboxRepo;
    
    @KafkaListener(topics = "domain-events.order")
    @Transactional
    public void handle(OrderCreatedEvent event) {
        try {
            Payment payment = new Payment();
            payment.setOrderId(event.getOrderId());
            payment.setAmount(event.getTotal());
            payment.setStatus(PaymentStatus.RESERVED);
            paymentRepo.save(payment);
            
            // Publish success event via outbox
            publishEvent("PaymentReserved", event.getOrderId(), 
                new PaymentReservedEvent(payment.getId(), event.getOrderId()));
                
        } catch (InsufficientFundsException e) {
            // Publish failure event via outbox
            publishEvent("PaymentFailed", event.getOrderId(),
                new PaymentFailedEvent(event.getOrderId(), "Insufficient funds"));
        }
    }
}
```

---

## 4. CQRS with JPA

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CQRS ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  COMMAND SIDE (Write Model)          QUERY SIDE (Read Model)    │
│  ┌─────────────────────────┐        ┌─────────────────────────┐│
│  │ Rich Domain Entities     │        │ Denormalized Read DTOs  ││
│  │ ├─ Order (aggregate root)│        │ ├─ OrderSummaryView     ││
│  │ ├─ OrderItem             │  CDC/  │ ├─ CustomerOrdersView   ││
│  │ ├─ Business rules        │ Events│ ├─ DashboardStatsView   ││
│  │ └─ Validations           │───────→│ └─ Optimized for reads  ││
│  │                           │        │                         ││
│  │ Normalized schema:        │        │ Denormalized schema:    ││
│  │ orders, order_items,      │        │ order_summaries (flat)  ││
│  │ customers, products       │        │ Pre-computed joins      ││
│  └─────────────────────────┘        └─────────────────────────┘│
│                                                                   │
│  JPA + rich domain model             JPA + simple entities      │
│  @Transactional writes               @Transactional(readOnly)   │
│  Small, focused transactions         Large read queries OK       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Write Side (Command)

```java
// Rich domain entity with business logic
@Entity
@Table(name = "orders")
public class Order {
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private String id;
    
    @Version private int version;
    
    private String customerId;
    
    @Enumerated(STRING)
    private OrderStatus status;
    
    @OneToMany(cascade = ALL, orphanRemoval = true)
    @JoinColumn(name = "order_id")
    private List<OrderItem> items = new ArrayList<>();
    
    @Embedded
    private Money total;
    
    // Domain method with business rules
    public void addItem(String productId, int quantity, Money unitPrice) {
        if (status != OrderStatus.DRAFT) {
            throw new IllegalStateException("Cannot modify confirmed order");
        }
        if (quantity <= 0) {
            throw new IllegalArgumentException("Quantity must be positive");
        }
        
        items.add(new OrderItem(productId, quantity, unitPrice));
        recalculateTotal();
    }
    
    public void confirm() {
        if (items.isEmpty()) {
            throw new IllegalStateException("Cannot confirm empty order");
        }
        this.status = OrderStatus.CONFIRMED;
        registerEvent(new OrderConfirmedEvent(this.id, this.total));
    }
    
    // Spring Data domain events
    @Transient
    private List<Object> domainEvents = new ArrayList<>();
    
    @DomainEvents
    public Collection<Object> domainEvents() { return domainEvents; }
    
    @AfterDomainEventPublication
    public void clearDomainEvents() { domainEvents.clear(); }
    
    protected void registerEvent(Object event) { domainEvents.add(event); }
}
```

### Read Side (Query)

```java
// Denormalized read model - optimized for specific queries
@Entity
@Table(name = "order_summary_view")
@Immutable  // Hibernate optimization: no dirty checking
public class OrderSummaryView {
    @Id
    private String orderId;
    
    private String customerName;  // Denormalized (no join needed)
    private String customerEmail;
    private String status;
    private BigDecimal totalAmount;
    private String currency;
    private int itemCount;
    private String firstItemName;  // Preview
    private Instant createdAt;
    private Instant confirmedAt;
}

// Read-only repository
public interface OrderSummaryViewRepository extends JpaRepository<OrderSummaryView, String> {
    
    @Query("SELECT o FROM OrderSummaryView o WHERE o.customerEmail = :email " +
           "ORDER BY o.createdAt DESC")
    Page<OrderSummaryView> findByCustomer(@Param("email") String email, Pageable page);
    
    @Query("SELECT o FROM OrderSummaryView o WHERE o.status = :status " +
           "AND o.createdAt > :since")
    List<OrderSummaryView> findRecentByStatus(@Param("status") String status,
                                              @Param("since") Instant since);
}

// Service uses read-only transaction
@Service
public class OrderQueryService {
    
    @Transactional(readOnly = true)
    public Page<OrderSummaryView> getCustomerOrders(String email, Pageable page) {
        return orderSummaryViewRepository.findByCustomer(email, page);
    }
}
```

### Projection (Sync Write → Read)

```java
@Component
public class OrderSummaryProjection {
    
    @Autowired private OrderSummaryViewRepository viewRepository;
    @Autowired private CustomerServiceClient customerClient;
    
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Transactional
    public void onOrderConfirmed(OrderConfirmedEvent event) {
        // Rebuild the read model from the event
        CustomerDTO customer = customerClient.getCustomer(event.getCustomerId());
        
        OrderSummaryView view = viewRepository.findById(event.getOrderId())
            .orElse(new OrderSummaryView());
        
        view.setOrderId(event.getOrderId());
        view.setCustomerName(customer.getName());
        view.setCustomerEmail(customer.getEmail());
        view.setStatus("CONFIRMED");
        view.setTotalAmount(event.getTotal().getAmount());
        view.setCurrency(event.getTotal().getCurrency());
        view.setItemCount(event.getItemCount());
        view.setConfirmedAt(Instant.now());
        
        viewRepository.save(view);
    }
}
```

---

## 5. Change Data Capture (CDC) with JPA

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  CDC ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Application                                                     │
│  ├─ JPA entities write to database normally                     │
│  ├─ No special event publishing code needed!                    │
│  └─ Just standard @Transactional CRUD                           │
│                                                                   │
│  Database (PostgreSQL)                                           │
│  ├─ WAL (Write-Ahead Log) captures all changes                 │
│  └─ Logical replication slot for Debezium                       │
│                                                                   │
│  Debezium (CDC Connector)                                        │
│  ├─ Reads WAL/binlog                                            │
│  ├─ Converts row changes to events                              │
│  ├─ Publishes to Kafka topics                                   │
│  │   └─ Topic per table: dbserver.schema.tablename             │
│  └─ Tracks position (offset) for exactly-once delivery         │
│                                                                   │
│  Consumers                                                       │
│  ├─ Search Service: updates Elasticsearch index                 │
│  ├─ Cache Service: invalidates Redis cache                      │
│  ├─ Analytics Service: populates data warehouse                 │
│  └─ Notification Service: triggers alerts on changes            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Use Cases with JPA

```java
// JPA entity - NO special code for CDC
@Entity
@Table(name = "products")
public class Product {
    @Id @GeneratedValue
    private Long id;
    private String name;
    private BigDecimal price;
    private String category;
    private boolean active;
}

// Normal CRUD operations
@Transactional
public Product updatePrice(Long id, BigDecimal newPrice) {
    Product product = productRepository.findById(id).get();
    product.setPrice(newPrice);
    return product;
    // CDC captures this UPDATE automatically from WAL
    // Elasticsearch index updated by CDC consumer
    // Redis cache invalidated by CDC consumer
    // No dual-write problem!
}
```

### Debezium Event Format

```json
{
    "schema": {...},
    "payload": {
        "before": {
            "id": 1,
            "name": "Widget",
            "price": 10.00,
            "category": "electronics",
            "active": true
        },
        "after": {
            "id": 1,
            "name": "Widget",
            "price": 12.00,
            "category": "electronics", 
            "active": true
        },
        "source": {
            "version": "2.4.0",
            "connector": "postgresql",
            "ts_ms": 1678901234567,
            "db": "productdb",
            "schema": "public",
            "table": "products"
        },
        "op": "u",
        "ts_ms": 1678901234600
    }
}
```

### Schema Evolution with CDC

```
Challenge: JPA entity changes (add column) must not break CDC consumers

Strategy: BACKWARD COMPATIBLE changes only
├─ Add nullable column: CDC publishes new field, consumers ignore unknown fields
├─ Remove column: First remove from consumers, then remove from entity
├─ Rename column: Add new column, backfill, update consumers, remove old
└─ Use Avro schema registry for schema evolution contracts
```

---

## 6. Database-Per-Service Pattern

### Entity Boundary Design

```
WRONG: Shared database across services
┌──────────────┐     ┌──────────────┐
│Order Service │────→│  Shared DB   │←────│Payment Service│
└──────────────┘     │ orders       │     └──────────────┘
                     │ payments     │
                     │ products     │
                     └──────────────┘
Problem: Tight coupling, schema changes affect all services

RIGHT: Database per service, reference by ID
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│Order Service │     │Payment Service│     │Product Service│
│ ┌──────────┐ │     │ ┌──────────┐ │     │ ┌──────────┐ │
│ │ Order    │ │     │ │ Payment  │ │     │ │ Product  │ │
│ │ customer │ │     │ │ order_id │ │     │ │ name     │ │
│ │ _id (ref)│ │     │ │ (ref)    │ │     │ │ price    │ │
│ └──────────┘ │     │ └──────────┘ │     │ └──────────┘ │
└──────────────┘     └──────────────┘     └──────────────┘
```

```java
// Order entity: references customer by ID only (not FK)
@Entity
public class Order {
    @Id @GeneratedValue
    private Long id;
    
    // NOT @ManyToOne - just store the ID
    // Customer lives in a different service/database
    private Long customerId;
    
    // Product details COPIED at order time (denormalized)
    // Because product price may change later
    @OneToMany(cascade = ALL)
    private List<OrderItem> items;
}

@Entity  
public class OrderItem {
    @Id @GeneratedValue
    private Long id;
    
    private Long productId;           // Reference to Product service
    private String productName;        // COPIED at order time
    private BigDecimal unitPrice;      // COPIED at order time
    private int quantity;
}
```

---

## 7. Event Sourcing with JPA

### Event Store Entity

```java
@Entity
@Table(name = "domain_events",
       indexes = @Index(columnList = "aggregateId, sequenceNumber"))
public class StoredEvent {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long globalSequence;  // Global ordering
    
    @Column(nullable = false)
    private String aggregateId;
    
    @Column(nullable = false)
    private String aggregateType;
    
    @Column(nullable = false)
    private int sequenceNumber;  // Per-aggregate ordering
    
    @Column(nullable = false)
    private String eventType;
    
    @Column(columnDefinition = "TEXT", nullable = false)
    private String eventData;  // JSON payload
    
    @Column(nullable = false)
    private Instant occurredAt;
    
    private String metadata;  // Correlation ID, causation ID, user ID
}

@Repository
public interface EventStoreRepository extends JpaRepository<StoredEvent, Long> {
    
    List<StoredEvent> findByAggregateIdOrderBySequenceNumberAsc(String aggregateId);
    
    List<StoredEvent> findByAggregateIdAndSequenceNumberGreaterThan(
        String aggregateId, int afterSequence);
    
    @Query("SELECT MAX(e.sequenceNumber) FROM StoredEvent e WHERE e.aggregateId = :aggId")
    Optional<Integer> findMaxSequenceNumber(@Param("aggId") String aggregateId);
}
```

### Aggregate Reconstruction

```java
public abstract class EventSourcedAggregate {
    
    @Transient
    private final List<Object> uncommittedEvents = new ArrayList<>();
    
    private String id;
    private int version;
    
    // Apply event to update state
    protected abstract void apply(Object event);
    
    // Reconstruct from event history
    public void loadFromHistory(List<Object> events) {
        for (Object event : events) {
            apply(event);
            this.version++;
        }
    }
    
    // Record new event
    protected void raiseEvent(Object event) {
        apply(event);
        uncommittedEvents.add(event);
        this.version++;
    }
    
    public List<Object> getUncommittedEvents() {
        return Collections.unmodifiableList(uncommittedEvents);
    }
}

// Concrete aggregate
public class ShoppingCart extends EventSourcedAggregate {
    private Map<String, Integer> items = new HashMap<>();
    private boolean checkedOut = false;
    
    public void addItem(String productId, int quantity) {
        if (checkedOut) throw new IllegalStateException("Cart is checked out");
        raiseEvent(new ItemAddedEvent(getId(), productId, quantity));
    }
    
    @Override
    protected void apply(Object event) {
        if (event instanceof ItemAddedEvent e) {
            items.merge(e.getProductId(), e.getQuantity(), Integer::sum);
        } else if (event instanceof CartCheckedOutEvent) {
            checkedOut = true;
        }
    }
}
```

### Event-Sourced Repository

```java
@Service
public class EventSourcedCartRepository {
    
    @Autowired private EventStoreRepository eventStore;
    @Autowired private ObjectMapper objectMapper;
    
    @Transactional(readOnly = true)
    public ShoppingCart load(String cartId) {
        List<StoredEvent> events = eventStore
            .findByAggregateIdOrderBySequenceNumberAsc(cartId);
        
        if (events.isEmpty()) throw new AggregateNotFoundException(cartId);
        
        ShoppingCart cart = new ShoppingCart(cartId);
        List<Object> domainEvents = events.stream()
            .map(this::deserializeEvent)
            .toList();
        cart.loadFromHistory(domainEvents);
        
        return cart;
    }
    
    @Transactional
    public void save(ShoppingCart cart) {
        Optional<Integer> currentVersion = eventStore
            .findMaxSequenceNumber(cart.getId());
        int expectedVersion = currentVersion.orElse(0);
        
        // Optimistic concurrency: check no new events since we loaded
        if (cart.getVersion() - cart.getUncommittedEvents().size() != expectedVersion) {
            throw new ConcurrencyException("Aggregate was modified concurrently");
        }
        
        int sequence = expectedVersion;
        for (Object event : cart.getUncommittedEvents()) {
            sequence++;
            StoredEvent stored = new StoredEvent();
            stored.setAggregateId(cart.getId());
            stored.setAggregateType("ShoppingCart");
            stored.setSequenceNumber(sequence);
            stored.setEventType(event.getClass().getSimpleName());
            stored.setEventData(objectMapper.writeValueAsString(event));
            stored.setOccurredAt(Instant.now());
            
            eventStore.save(stored);
        }
    }
}
```

---

## 8. Anti-Patterns

### 1. Distributed Monolith (Shared Database)

```
ANTI-PATTERN:
- Multiple services sharing same database
- Direct table access across service boundaries
- JPA entities referencing tables owned by other services

CONSEQUENCE:
- Schema changes in one service break others
- No independent deployment
- Shared connection pool → contention
- All "benefits" of microservices with none of the advantages
```

### 2. JPA Entities in API Contracts

```java
// WRONG: Exposing JPA entity as REST response
@GetMapping("/orders/{id}")
public Order getOrder(@PathVariable Long id) {
    return orderRepository.findById(id).get();
    // Problems:
    // - Lazy loading exceptions (Jackson triggers getters outside session)
    // - Circular references (Order → Customer → Orders → ...)
    // - Internal fields exposed (version, audit columns)
    // - API contract tied to database schema
    // - @JsonIgnore spreading everywhere
}

// RIGHT: DTO layer
@GetMapping("/orders/{id}")
public OrderResponse getOrder(@PathVariable Long id) {
    Order order = orderService.findById(id);
    return OrderResponse.from(order);  // Explicit mapping
}
```

### 3. Lazy Loading Across Service Boundaries

```java
// DANGEROUS in microservices:
@Entity
public class Order {
    @ManyToOne(fetch = LAZY)
    private Customer customer;  // Customer is in ANOTHER service's DB!
}
// This @ManyToOne should NOT exist in database-per-service architecture
// Replace with: private Long customerId; (just the ID)
```

### 4. Open Session in View in Microservices

```
Problem in microservices:
- OSIV holds DB connection for entire HTTP request
- If request calls other services (HTTP/gRPC): connection held during network I/O
- Connection pool exhausted under moderate load
- Solution: ALWAYS disable OSIV in microservices

spring.jpa.open-in-view=false  # ALWAYS set this
```

---

## 9. Decision Framework

### When to Use Which Pattern

```
┌──────────────────────────────────────────────────────────────┐
│ Pattern Selection Guide                                       │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│ Single service, single DB:                                    │
│ → Standard JPA @Transactional (simple, ACID)                 │
│                                                                │
│ Multiple services need to react to changes:                   │
│ → Outbox Pattern (guaranteed delivery, simple)               │
│                                                                │
│ Multiple services must coordinate for consistency:            │
│ → Saga Pattern (orchestration for complex flows)             │
│                                                                │
│ High read:write ratio, different read patterns:              │
│ → CQRS (separate read/write models)                          │
│                                                                │
│ Need to sync data across services without code changes:      │
│ → CDC with Debezium (transparent, infrastructure-level)      │
│                                                                │
│ Need complete audit trail + time travel:                      │
│ → Event Sourcing (events as source of truth)                 │
│                                                                │
│ Complexity order (simple → complex):                          │
│ Outbox < CDC < CQRS < Saga < Event Sourcing                 │
│                                                                │
│ Start simple! Most systems only need Outbox + CDC.           │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 10. Interview Talking Points

### "How do you handle data consistency across microservices?"

**Structured answer:**
1. Accept that we can't have distributed ACID - embrace eventual consistency
2. Define consistency boundaries using DDD aggregates (strong consistency within aggregate)
3. Use Transactional Outbox pattern for reliable event publishing
4. Implement Saga pattern for multi-service operations that require coordination
5. Consumer idempotency is critical - use processed_events table
6. Monitor for inconsistency: reconciliation jobs, alerting on event processing lag
7. Design for failure: compensating transactions, dead letter queues, manual resolution

### "When would you NOT use JPA in a microservice?"

1. **Event Store**: Raw JDBC or specialized event store (EventStoreDB) is better for append-only event streams
2. **High-throughput writes**: JPA overhead (dirty checking, persistence context) is unnecessary for fire-and-forget writes
3. **Complex analytical queries**: JPA/JPQL less expressive than SQL for analytics; use jOOQ or raw JDBC
4. **Simple CRUD with no domain logic**: Spring Data JDBC is lighter than JPA (no lazy loading, no session)
5. **Polyglot persistence**: when using NoSQL (MongoDB, DynamoDB), JPA doesn't apply
