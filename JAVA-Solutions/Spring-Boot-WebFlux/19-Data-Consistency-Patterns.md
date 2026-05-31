# Data Consistency Patterns - Staff Engineer / Architect Level

## Target Level: Staff Engineer / Architect
These problems focus on maintaining data consistency in distributed systems -- the hardest problem in microservices. Expect deep discussion on trade-offs, failure modes, and real-world implementations.

---

## Problem 1: Implement the Saga Pattern for Order Processing

**Scenario:** An e-commerce order involves 5 services:
1. Order Service (creates order)
2. Payment Service (charges customer)
3. Inventory Service (reserves items)
4. Shipping Service (schedules delivery)
5. Loyalty Service (awards points)

If payment succeeds but inventory fails, you must compensate (refund).

### Q1: Orchestration vs Choreography - When to use which?

```
CHOREOGRAPHY (event-driven, decentralized):
  
  Order Created → Payment Service listens → Payment Success event →
  Inventory Service listens → Inventory Reserved event →
  Shipping Service listens → Shipment Scheduled event → DONE

  Compensation (if Inventory fails):
  Inventory Failed event → Payment Service listens → Refund issued

  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
  │ Order   │───→│ Payment │───→│Inventory│───→│Shipping │
  │ Service │←───│ Service │←───│ Service │←───│ Service │
  └─────────┘    └─────────┘    └─────────┘    └─────────┘
       Events flow through Kafka/message broker

  Pros:
  - No single point of failure (no orchestrator)
  - Services are truly decoupled
  - Easy to add new participants
  
  Cons:
  - Hard to understand the full flow
  - Hard to debug (trace across services)
  - Cyclic dependencies possible
  - No central view of saga state

ORCHESTRATION (centralized coordinator):

  Order Orchestrator:
    Step 1: Command → Payment Service → Response
    Step 2: Command → Inventory Service → Response
    Step 3: Command → Shipping Service → Response
    On failure at Step 2:
      Compensate Step 1: Refund Payment

  ┌──────────────────────────────────────┐
  │          Order Orchestrator           │
  │  (Spring State Machine / Temporal)    │
  └──┬────────────┬────────────┬─────────┘
     │            │            │
     ▼            ▼            ▼
  ┌──────┐   ┌──────┐   ┌──────┐
  │Payment│   │Invent│   │Shippg│
  └──────┘   └──────┘   └──────┘

  Pros:
  - Easy to understand (one place shows full flow)
  - Easy to debug and monitor
  - Central place for compensation logic
  - Simple to add timeouts and retries
  
  Cons:
  - Orchestrator is a SPOF (must be highly available)
  - Coupling (orchestrator knows all participants)
  - Can become a bottleneck

DECISION FRAMEWORK:
  Use CHOREOGRAPHY when:
  - Simple flows (2-3 steps)
  - Steps are independent (no ordering needed)
  - Teams are autonomous (don't want central coordinator)

  Use ORCHESTRATION when:
  - Complex flows (4+ steps with dependencies)
  - Need clear visibility into saga state
  - Complex compensation logic
  - Timeouts and retries are critical
  - Business stakeholders need to understand the flow
```

### Q2: Implement Saga Orchestration with Spring Boot

```java
// Approach 1: Spring State Machine

@Configuration
@EnableStateMachineFactory
public class OrderSagaStateMachineConfig 
    extends StateMachineConfigurerAdapter<OrderState, OrderEvent> {

    @Override
    public void configure(StateMachineStateConfigurer<OrderState, OrderEvent> states) throws Exception {
        states.withStates()
            .initial(OrderState.CREATED)
            .state(OrderState.PAYMENT_PENDING)
            .state(OrderState.PAYMENT_CONFIRMED)
            .state(OrderState.INVENTORY_PENDING)
            .state(OrderState.INVENTORY_RESERVED)
            .state(OrderState.SHIPPING_PENDING)
            .state(OrderState.COMPLETED)
            .state(OrderState.COMPENSATING)
            .end(OrderState.FAILED)
            .end(OrderState.CANCELLED);
    }

    @Override
    public void configure(StateMachineTransitionConfigurer<OrderState, OrderEvent> transitions) throws Exception {
        transitions
            // Happy path
            .withExternal().source(CREATED).target(PAYMENT_PENDING).event(START_SAGA)
                .action(requestPaymentAction())
            .and()
            .withExternal().source(PAYMENT_PENDING).target(PAYMENT_CONFIRMED).event(PAYMENT_SUCCESS)
            .and()
            .withExternal().source(PAYMENT_CONFIRMED).target(INVENTORY_PENDING).event(RESERVE_INVENTORY)
                .action(requestInventoryAction())
            .and()
            .withExternal().source(INVENTORY_PENDING).target(INVENTORY_RESERVED).event(INVENTORY_SUCCESS)
            .and()
            .withExternal().source(INVENTORY_RESERVED).target(COMPLETED).event(COMPLETE_ORDER)
                .action(completeOrderAction())
            
            // Compensation path
            .and()
            .withExternal().source(INVENTORY_PENDING).target(COMPENSATING).event(INVENTORY_FAILED)
                .action(compensatePaymentAction())
            .and()
            .withExternal().source(COMPENSATING).target(FAILED).event(COMPENSATION_COMPLETE);
    }
}

// Approach 2: Manual orchestrator with Outbox pattern

@Service
public class OrderSagaOrchestrator {
    
    @Transactional
    public void startSaga(Order order) {
        order.setStatus(OrderStatus.SAGA_STARTED);
        orderRepo.save(order);
        
        // Publish command via outbox (same transaction)
        outboxRepo.save(new OutboxEvent(
            "payment-commands",
            "ProcessPayment",
            new ProcessPaymentCommand(order.getId(), order.getAmount())
        ));
    }
    
    @KafkaListener(topics = "payment-results")
    @Transactional
    public void handlePaymentResult(PaymentResult result) {
        Order order = orderRepo.findById(result.getOrderId()).orElseThrow();
        
        if (result.isSuccess()) {
            order.setStatus(OrderStatus.PAYMENT_CONFIRMED);
            order.setPaymentId(result.getPaymentId());
            orderRepo.save(order);
            
            // Next step: reserve inventory
            outboxRepo.save(new OutboxEvent(
                "inventory-commands",
                "ReserveInventory",
                new ReserveInventoryCommand(order.getId(), order.getItems())
            ));
        } else {
            // Payment failed - no compensation needed (first step)
            order.setStatus(OrderStatus.FAILED);
            order.setFailureReason(result.getError());
            orderRepo.save(order);
        }
    }
    
    @KafkaListener(topics = "inventory-results")
    @Transactional
    public void handleInventoryResult(InventoryResult result) {
        Order order = orderRepo.findById(result.getOrderId()).orElseThrow();
        
        if (result.isSuccess()) {
            order.setStatus(OrderStatus.COMPLETED);
            orderRepo.save(order);
        } else {
            // Inventory failed - compensate payment
            order.setStatus(OrderStatus.COMPENSATING);
            orderRepo.save(order);
            
            outboxRepo.save(new OutboxEvent(
                "payment-commands",
                "RefundPayment",
                new RefundPaymentCommand(order.getId(), order.getPaymentId())
            ));
        }
    }
}
```

### Q3: How do you handle saga timeout and stuck sagas?

```java
// Problem: What if a step never responds?
// Service is down, message lost, consumer crashed

// Solution: Saga Timeout Monitor
@Service
public class SagaTimeoutMonitor {
    
    @Scheduled(fixedDelay = 30000) // Check every 30 seconds
    @SchedulerLock(name = "sagaTimeout", lockAtMostFor = "25s")
    public void checkStuckSagas() {
        Instant timeout = Instant.now().minus(Duration.ofMinutes(5));
        
        List<Order> stuckOrders = orderRepo.findByStatusInAndUpdatedAtBefore(
            List.of(PAYMENT_PENDING, INVENTORY_PENDING, SHIPPING_PENDING),
            timeout
        );
        
        for (Order order : stuckOrders) {
            log.warn("Saga stuck for order: {} in state: {}", order.getId(), order.getStatus());
            
            if (order.getRetryCount() < MAX_RETRIES) {
                // Retry the current step
                retryCurrentStep(order);
                order.setRetryCount(order.getRetryCount() + 1);
            } else {
                // Max retries exceeded - compensate
                startCompensation(order);
            }
            
            orderRepo.save(order);
        }
    }
    
    private void startCompensation(Order order) {
        switch (order.getStatus()) {
            case INVENTORY_PENDING:
            case SHIPPING_PENDING:
                // Compensate all previous successful steps
                compensatePayment(order);
                break;
            case PAYMENT_PENDING:
                // First step stuck - just mark as failed
                order.setStatus(OrderStatus.FAILED);
                break;
        }
    }
}
```

---

## Problem 2: Implement Event Sourcing

**Scenario:** A financial system needs:
- Complete audit trail of all state changes
- Ability to rebuild state at any point in time
- Support for "what happened between T1 and T2?"
- Regulatory compliance (immutable history)

### Q4: How does Event Sourcing differ from traditional CRUD?

```
TRADITIONAL CRUD:
  Database stores CURRENT STATE only
  
  accounts table:
  | id | balance | last_modified |
  | 1  | 500.00  | 2024-03-15    |
  
  Problem: How did balance go from 1000 to 500?
  Answer: No idea! History is lost.

EVENT SOURCING:
  Database stores SEQUENCE OF EVENTS
  
  account_events table:
  | event_id | account_id | type       | amount | timestamp           |
  | 1        | 1          | CREATED    | 1000   | 2024-03-01 10:00:00 |
  | 2        | 1          | WITHDRAWAL | -200   | 2024-03-05 14:30:00 |
  | 3        | 1          | DEPOSIT    | 100    | 2024-03-10 09:15:00 |
  | 4        | 1          | WITHDRAWAL | -400   | 2024-03-15 16:45:00 |
  
  Current balance = replay all events: 1000 - 200 + 100 - 400 = 500
  Balance at March 10 = replay events 1-3: 1000 - 200 + 100 = 900
  
  COMPLETE HISTORY PRESERVED

Key Concepts:
  - Events are IMMUTABLE (append-only, never modify/delete)
  - Current state = fold(initialState, allEvents)
  - Snapshot: periodically save current state to avoid replaying all events
  - Event Store: specialized database for event streams
```

### Q5: Implement Event Sourcing in Spring Boot

```java
// Domain Events
public sealed interface AccountEvent {
    String accountId();
    Instant timestamp();
    
    record AccountCreated(String accountId, BigDecimal initialBalance, 
                          Instant timestamp) implements AccountEvent {}
    record MoneyDeposited(String accountId, BigDecimal amount, String reference,
                          Instant timestamp) implements AccountEvent {}
    record MoneyWithdrawn(String accountId, BigDecimal amount, String reference,
                          Instant timestamp) implements AccountEvent {}
    record AccountClosed(String accountId, String reason,
                         Instant timestamp) implements AccountEvent {}
}

// Aggregate (reconstructed from events)
public class Account {
    private String id;
    private BigDecimal balance;
    private AccountStatus status;
    private int version;
    private List<AccountEvent> uncommittedEvents = new ArrayList<>();
    
    // Reconstruct from events
    public static Account fromEvents(List<AccountEvent> events) {
        Account account = new Account();
        for (AccountEvent event : events) {
            account.apply(event);
            account.version++;
        }
        return account;
    }
    
    // Command: deposit money
    public void deposit(BigDecimal amount, String reference) {
        if (status != AccountStatus.ACTIVE) {
            throw new IllegalStateException("Account is not active");
        }
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Amount must be positive");
        }
        
        // Create event (not applied yet)
        MoneyDeposited event = new MoneyDeposited(id, amount, reference, Instant.now());
        apply(event);
        uncommittedEvents.add(event);
    }
    
    // Command: withdraw money
    public void withdraw(BigDecimal amount, String reference) {
        if (status != AccountStatus.ACTIVE) {
            throw new IllegalStateException("Account is not active");
        }
        if (balance.compareTo(amount) < 0) {
            throw new InsufficientFundsException("Balance: " + balance + ", Requested: " + amount);
        }
        
        MoneyWithdrawn event = new MoneyWithdrawn(id, amount, reference, Instant.now());
        apply(event);
        uncommittedEvents.add(event);
    }
    
    // Apply event to state (event handler)
    private void apply(AccountEvent event) {
        switch (event) {
            case AccountCreated e -> {
                this.id = e.accountId();
                this.balance = e.initialBalance();
                this.status = AccountStatus.ACTIVE;
            }
            case MoneyDeposited e -> this.balance = this.balance.add(e.amount());
            case MoneyWithdrawn e -> this.balance = this.balance.subtract(e.amount());
            case AccountClosed e -> this.status = AccountStatus.CLOSED;
        }
    }
    
    public List<AccountEvent> getUncommittedEvents() {
        return Collections.unmodifiableList(uncommittedEvents);
    }
    
    public void markCommitted() {
        uncommittedEvents.clear();
    }
}

// Event Store
@Repository
public class EventStore {
    private final JdbcTemplate jdbc;
    
    @Transactional
    public void saveEvents(String aggregateId, int expectedVersion, List<AccountEvent> events) {
        // Optimistic concurrency check
        int currentVersion = getCurrentVersion(aggregateId);
        if (currentVersion != expectedVersion) {
            throw new ConcurrencyException(
                "Expected version " + expectedVersion + " but found " + currentVersion);
        }
        
        int version = expectedVersion;
        for (AccountEvent event : events) {
            version++;
            jdbc.update(
                "INSERT INTO events (aggregate_id, version, event_type, event_data, timestamp) VALUES (?, ?, ?, ?, ?)",
                aggregateId, version, event.getClass().getSimpleName(),
                serialize(event), event.timestamp()
            );
        }
    }
    
    public List<AccountEvent> getEvents(String aggregateId) {
        return jdbc.query(
            "SELECT * FROM events WHERE aggregate_id = ? ORDER BY version",
            (rs, row) -> deserialize(rs.getString("event_type"), rs.getString("event_data")),
            aggregateId
        );
    }
    
    public List<AccountEvent> getEventsAfterVersion(String aggregateId, int afterVersion) {
        return jdbc.query(
            "SELECT * FROM events WHERE aggregate_id = ? AND version > ? ORDER BY version",
            (rs, row) -> deserialize(rs.getString("event_type"), rs.getString("event_data")),
            aggregateId, afterVersion
        );
    }
}

// Application Service
@Service
public class AccountService {
    private final EventStore eventStore;
    private final SnapshotStore snapshotStore;
    private final ApplicationEventPublisher publisher;
    
    @Transactional
    public void deposit(String accountId, BigDecimal amount, String reference) {
        // Load aggregate from events
        Account account = loadAccount(accountId);
        
        // Execute command (generates events)
        account.deposit(amount, reference);
        
        // Save events
        eventStore.saveEvents(accountId, account.getVersion(), account.getUncommittedEvents());
        
        // Publish events for projections/other services
        account.getUncommittedEvents().forEach(publisher::publishEvent);
        account.markCommitted();
    }
    
    private Account loadAccount(String accountId) {
        // Check for snapshot first (optimization)
        Optional<Snapshot> snapshot = snapshotStore.getLatest(accountId);
        
        if (snapshot.isPresent()) {
            Account account = snapshot.get().getAccount();
            // Load only events AFTER snapshot
            List<AccountEvent> newEvents = eventStore.getEventsAfterVersion(
                accountId, snapshot.get().getVersion());
            newEvents.forEach(account::apply);
            return account;
        }
        
        // No snapshot - replay all events
        List<AccountEvent> events = eventStore.getEvents(accountId);
        if (events.isEmpty()) {
            throw new AccountNotFoundException(accountId);
        }
        return Account.fromEvents(events);
    }
}
```

### Q6: How do you build read models (projections) from events?

```java
// CQRS Read Model (Projection)
// Events → Projector → Read-optimized database

@Component
public class AccountBalanceProjection {
    private final JdbcTemplate jdbc;
    
    @EventListener
    @Transactional
    public void on(AccountCreated event) {
        jdbc.update(
            "INSERT INTO account_balances (account_id, balance, status, created_at) VALUES (?, ?, ?, ?)",
            event.accountId(), event.initialBalance(), "ACTIVE", event.timestamp()
        );
    }
    
    @EventListener
    @Transactional
    public void on(MoneyDeposited event) {
        jdbc.update(
            "UPDATE account_balances SET balance = balance + ?, last_transaction_at = ? WHERE account_id = ?",
            event.amount(), event.timestamp(), event.accountId()
        );
    }
    
    @EventListener
    @Transactional
    public void on(MoneyWithdrawn event) {
        jdbc.update(
            "UPDATE account_balances SET balance = balance - ?, last_transaction_at = ? WHERE account_id = ?",
            event.amount(), event.timestamp(), event.accountId()
        );
    }
}

// Transaction History Projection (different read model, same events)
@Component
public class TransactionHistoryProjection {
    
    @EventListener
    public void on(MoneyDeposited event) {
        transactionRepo.save(new TransactionRecord(
            event.accountId(), "DEPOSIT", event.amount(), event.reference(), event.timestamp()
        ));
    }
    
    @EventListener
    public void on(MoneyWithdrawn event) {
        transactionRepo.save(new TransactionRecord(
            event.accountId(), "WITHDRAWAL", event.amount(), event.reference(), event.timestamp()
        ));
    }
}

// Rebuild projection from scratch (when schema changes or bug fix)
@Service
public class ProjectionRebuilder {
    
    public void rebuildProjection(String projectionName) {
        // 1. Clear existing projection data
        projectionStore.clear(projectionName);
        
        // 2. Replay ALL events from event store
        eventStore.streamAllEvents()
            .forEach(event -> {
                projectionHandlers.get(projectionName).handle(event);
            });
        
        // 3. Mark projection as up-to-date
        projectionStore.markRebuilt(projectionName, eventStore.getLastPosition());
    }
}
```

---

## Problem 3: CQRS (Command Query Responsibility Segregation)

### Q7: When is CQRS justified and what are the trade-offs?

```
WHEN TO USE CQRS:

✅ Justified when:
  - Read and write patterns are fundamentally different
  - Read model needs different structure than write model
  - Different scaling needs (reads >> writes)
  - Complex domain with business rules on writes
  - Multiple read models needed for same data

❌ Over-engineering when:
  - Simple CRUD application
  - Read/write patterns are similar
  - Small team (added complexity cost > benefit)
  - Eventual consistency is unacceptable

TRADE-OFFS:
  ┌──────────────────┬──────────────────────┬──────────────────────┐
  │ Aspect           │ Without CQRS         │ With CQRS            │
  ├──────────────────┼──────────────────────┼──────────────────────┤
  │ Consistency      │ Strong (same DB)     │ Eventual (async)     │
  │ Complexity       │ Low                  │ High (2 models)      │
  │ Read performance │ Limited (normalized) │ Optimal (denormalized)│
  │ Write performance│ Limited (indexes)    │ Optimal (no indexes) │
  │ Scalability      │ Coupled              │ Independent scaling  │
  │ Query flexibility│ Limited              │ Multiple read models │
  │ Debugging        │ Simple               │ More complex         │
  │ Team size needed │ 1-3 devs             │ 3+ devs              │
  └──────────────────┴──────────────────────┴──────────────────────┘
```

### Q8: Implement CQRS in Spring Boot

```java
// COMMAND SIDE (Write Model)

// Commands
public record CreateOrderCommand(String customerId, List<OrderItem> items) {}
public record CancelOrderCommand(String orderId, String reason) {}

// Command Handler
@Service
public class OrderCommandHandler {
    private final OrderRepository orderRepo;
    private final EventPublisher eventPublisher;
    
    @Transactional
    public String handle(CreateOrderCommand cmd) {
        // Business rules validation
        validateCustomer(cmd.customerId());
        validateInventory(cmd.items());
        
        // Create aggregate
        Order order = Order.create(cmd.customerId(), cmd.items());
        orderRepo.save(order);
        
        // Publish domain event
        eventPublisher.publish(new OrderCreatedEvent(
            order.getId(), order.getCustomerId(), order.getItems(), order.getTotal()
        ));
        
        return order.getId();
    }
    
    @Transactional
    public void handle(CancelOrderCommand cmd) {
        Order order = orderRepo.findById(cmd.orderId()).orElseThrow();
        order.cancel(cmd.reason()); // Domain logic + validation
        orderRepo.save(order);
        
        eventPublisher.publish(new OrderCancelledEvent(order.getId(), cmd.reason()));
    }
}

// Write model: normalized, enforces business rules
@Entity
@Table(name = "orders")
public class Order {
    @Id private String id;
    private String customerId;
    @Enumerated private OrderStatus status;
    @OneToMany(cascade = ALL) private List<OrderLineItem> lineItems;
    private BigDecimal total;
    @Version private Long version; // Optimistic locking
}

// -------------------------------------------------------------------

// QUERY SIDE (Read Model)

// Read model: denormalized, optimized for queries
@Document(collection = "order_views") // MongoDB for flexible queries
public class OrderView {
    private String orderId;
    private String customerId;
    private String customerName;      // Denormalized (no JOIN needed)
    private String customerEmail;     // Denormalized
    private List<ItemView> items;
    private BigDecimal total;
    private String status;
    private Instant createdAt;
    private Instant lastUpdatedAt;
    // Pre-computed fields for common queries:
    private int itemCount;
    private String primaryCategory;
}

// Projection: Events → Read Model
@Component
public class OrderViewProjection {
    private final MongoTemplate mongo;
    
    @EventListener
    public void on(OrderCreatedEvent event) {
        OrderView view = new OrderView();
        view.setOrderId(event.orderId());
        view.setCustomerId(event.customerId());
        view.setCustomerName(customerService.getName(event.customerId())); // Enrich
        view.setItems(event.items().stream().map(this::toItemView).toList());
        view.setTotal(event.total());
        view.setStatus("CREATED");
        view.setCreatedAt(event.timestamp());
        view.setItemCount(event.items().size());
        mongo.save(view);
    }
    
    @EventListener
    public void on(OrderCancelledEvent event) {
        Query query = Query.query(Criteria.where("orderId").is(event.orderId()));
        Update update = new Update()
            .set("status", "CANCELLED")
            .set("cancellationReason", event.reason())
            .set("lastUpdatedAt", event.timestamp());
        mongo.updateFirst(query, update, OrderView.class);
    }
}

// Query Handler (fast, no business logic)
@RestController
@RequestMapping("/api/orders")
public class OrderQueryController {
    private final MongoTemplate mongo;
    
    @GetMapping("/{id}")
    public OrderView getOrder(@PathVariable String id) {
        return mongo.findById(id, OrderView.class); // Single document fetch
    }
    
    @GetMapping("/customer/{customerId}")
    public List<OrderView> getCustomerOrders(
            @PathVariable String customerId,
            @RequestParam(defaultValue = "createdAt") String sortBy) {
        Query query = Query.query(Criteria.where("customerId").is(customerId))
            .with(Sort.by(Sort.Direction.DESC, sortBy))
            .limit(50);
        return mongo.find(query, OrderView.class);
    }
    
    @GetMapping("/search")
    public List<OrderView> searchOrders(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) BigDecimal minTotal) {
        Criteria criteria = new Criteria();
        if (status != null) criteria.and("status").is(status);
        if (category != null) criteria.and("primaryCategory").is(category);
        if (minTotal != null) criteria.and("total").gte(minTotal);
        return mongo.find(Query.query(criteria), OrderView.class);
    }
}
```

---

## Problem 4: Handling Eventual Consistency in Practice

### Q9: How do you deal with "read-your-own-writes" in eventually consistent systems?

```
PROBLEM:
  User creates order → Redirected to order details page → "Order not found!" (404)
  Why? Write went to command DB, read model not yet updated (50-500ms lag)

SOLUTIONS:

1. WRITE-RETURN-ID + POLLING:
   POST /orders → returns { orderId: "123", status: "PROCESSING" }
   Client polls: GET /orders/123 until read model is ready
   
   @PostMapping("/orders")
   public ResponseEntity<OrderResponse> createOrder(@RequestBody CreateOrderCommand cmd) {
       String orderId = commandHandler.handle(cmd);
       return ResponseEntity.accepted()
           .header("Location", "/orders/" + orderId)
           .body(new OrderResponse(orderId, "PROCESSING"));
   }

2. COMMAND RETURNS READ MODEL (bypass query side temporarily):
   @PostMapping("/orders")
   public OrderView createOrder(@RequestBody CreateOrderCommand cmd) {
       String orderId = commandHandler.handle(cmd);
       // Return a "synthetic" view built from command data
       // Not from projection (which may be stale)
       return OrderView.fromCommand(orderId, cmd);
   }

3. CAUSAL CONSISTENCY TOKEN:
   // Write returns a version/sequence number
   POST /orders → { orderId: "123", version: 42 }
   
   // Read waits until projection catches up to that version
   GET /orders/123?afterVersion=42
   
   @GetMapping("/orders/{id}")
   public Mono<OrderView> getOrder(
           @PathVariable String id,
           @RequestParam(required = false) Long afterVersion) {
       if (afterVersion != null) {
           // Wait until projection processes up to this version
           return waitForProjection(id, afterVersion, Duration.ofSeconds(5))
               .then(Mono.fromCallable(() -> orderViewRepo.findById(id)));
       }
       return Mono.fromCallable(() -> orderViewRepo.findById(id));
   }

4. SYNCHRONOUS PROJECTION (for critical reads):
   // For the creating user only, update read model synchronously
   @Transactional
   public String handle(CreateOrderCommand cmd) {
       Order order = Order.create(cmd);
       orderRepo.save(order);
       
       // Synchronous projection update (only for the creator's view)
       orderViewRepo.save(OrderView.fromOrder(order));
       
       // Async event for other projections
       eventPublisher.publish(new OrderCreatedEvent(order));
       return order.getId();
   }
```

### Q10: How do you handle cross-service data consistency without distributed transactions?

```
SCENARIO: Order needs customer info + product info + inventory check
         across 3 different services' databases

OPTIONS:

1. API COMPOSITION (at query time):
   @GetMapping("/orders/{id}/details")
   public Mono<OrderDetails> getOrderDetails(@PathVariable String id) {
       Mono<Order> order = orderService.getOrder(id);
       return order.flatMap(o -> {
           Mono<Customer> customer = customerService.getCustomer(o.getCustomerId());
           Mono<List<Product>> products = productService.getProducts(o.getProductIds());
           return Mono.zip(customer, products)
               .map(tuple -> new OrderDetails(o, tuple.getT1(), tuple.getT2()));
       });
   }
   
   Pros: Always fresh data, simple
   Cons: Slow (network calls), fragile (if any service is down)

2. DATA DENORMALIZATION (via events):
   // When customer changes name:
   CustomerNameChanged event → Order service stores customer_name locally
   
   // Order read model has all data it needs locally
   // No cross-service calls at query time
   
   Pros: Fast queries, resilient
   Cons: Eventual consistency, data duplication

3. SHARED DATA PLATFORM (data mesh):
   // Each service publishes "data products" to shared platform
   // Consumers subscribe to the data they need
   
   Customer Service → publishes customer data product
   Order Service → subscribes to customer data product
   
   Implementation: Kafka + Schema Registry + CDC (Debezium)

4. SAGA FOR WRITES (maintain consistency):
   Create order:
     1. Validate customer exists (sync call, cached)
     2. Reserve inventory (saga step)
     3. Create order (saga step)
     4. Process payment (saga step)
   
   Each step is atomic within its service
   Saga ensures overall consistency (with compensation)
```

---

## Problem 5: Idempotency Deep Dive

### Q11: Design a bulletproof idempotency mechanism

```java
// The Problem: Network failures cause duplicate requests
// Client → Server: "charge $100" (request 1)
// Server processes, charges $100
// Response lost (network failure)
// Client retries: "charge $100" (request 2 - DUPLICATE!)
// Without idempotency: $200 charged instead of $100

// Bulletproof Implementation:

@Entity
@Table(name = "idempotency_keys")
public class IdempotencyRecord {
    @Id
    private String key;                    // Client-provided unique key
    
    @Column(nullable = false)
    private String requestHash;            // Hash of request body (detect different requests with same key)
    
    @Column(columnDefinition = "TEXT")
    private String responseBody;           // Cached response
    
    private int responseStatus;            // Cached HTTP status
    
    @Enumerated
    private ProcessingStatus status;       // PROCESSING, COMPLETED, FAILED
    
    private Instant createdAt;
    private Instant expiresAt;             // Auto-cleanup after TTL
    
    @Version
    private Long version;
}

@Service
public class IdempotencyService {
    private final IdempotencyRepository repo;
    
    /**
     * Execute an operation idempotently.
     * Returns cached result for duplicate requests.
     */
    @Transactional
    public <T> IdempotencyResult<T> executeIdempotent(
            String idempotencyKey, 
            String requestHash,
            Supplier<T> operation,
            Function<T, String> serializer) {
        
        // Check for existing record
        Optional<IdempotencyRecord> existing = repo.findById(idempotencyKey);
        
        if (existing.isPresent()) {
            IdempotencyRecord record = existing.get();
            
            // Same key, different request → error
            if (!record.getRequestHash().equals(requestHash)) {
                throw new IdempotencyKeyReusedException(
                    "Key already used for a different request");
            }
            
            switch (record.getStatus()) {
                case COMPLETED:
                    // Return cached response (idempotent!)
                    return IdempotencyResult.cached(record.getResponseBody(), record.getResponseStatus());
                    
                case PROCESSING:
                    // Another request with same key is in progress
                    // Could be: parallel retry, or previous attempt still running
                    if (record.getCreatedAt().plus(Duration.ofMinutes(5)).isBefore(Instant.now())) {
                        // Stale - previous attempt likely failed without cleanup
                        record.setStatus(ProcessingStatus.FAILED);
                        repo.save(record);
                        // Fall through to reprocess
                    } else {
                        throw new ProcessingInProgressException("Request is being processed");
                    }
                    break;
                    
                case FAILED:
                    // Previous attempt failed - allow retry
                    break;
            }
        }
        
        // Mark as processing (prevents concurrent duplicates)
        IdempotencyRecord record = new IdempotencyRecord();
        record.setKey(idempotencyKey);
        record.setRequestHash(requestHash);
        record.setStatus(ProcessingStatus.PROCESSING);
        record.setCreatedAt(Instant.now());
        record.setExpiresAt(Instant.now().plus(Duration.ofHours(24)));
        
        try {
            repo.save(record); // Unique constraint prevents race condition
        } catch (DataIntegrityViolationException e) {
            // Lost race - another thread inserted first
            return executeIdempotent(idempotencyKey, requestHash, operation, serializer);
        }
        
        try {
            // Execute the actual operation
            T result = operation.get();
            
            // Cache the response
            record.setResponseBody(serializer.apply(result));
            record.setResponseStatus(200);
            record.setStatus(ProcessingStatus.COMPLETED);
            repo.save(record);
            
            return IdempotencyResult.fresh(result);
        } catch (Exception e) {
            record.setStatus(ProcessingStatus.FAILED);
            record.setResponseBody(e.getMessage());
            repo.save(record);
            throw e;
        }
    }
}

// Controller usage:
@PostMapping("/payments")
public ResponseEntity<PaymentResponse> createPayment(
        @RequestHeader("Idempotency-Key") String idempotencyKey,
        @RequestBody PaymentRequest request) {
    
    String requestHash = DigestUtils.sha256Hex(objectMapper.writeValueAsString(request));
    
    IdempotencyResult<PaymentResponse> result = idempotencyService.executeIdempotent(
        idempotencyKey,
        requestHash,
        () -> paymentService.processPayment(request),
        response -> objectMapper.writeValueAsString(response)
    );
    
    if (result.isCached()) {
        return ResponseEntity.ok()
            .header("X-Idempotency-Replayed", "true")
            .body(result.getValue());
    }
    
    return ResponseEntity.status(HttpStatus.CREATED).body(result.getValue());
}
```

---

## Problem 6: Distributed Transactions - When You Actually Need Them

### Q12: When are distributed transactions acceptable (and how to implement)?

```
WHEN DISTRIBUTED TX IS JUSTIFIED:
  - Two databases that MUST be atomically consistent
  - Regulatory requirement (financial systems)
  - All participants are within same data center (low latency)
  - Small number of participants (2-3 max)

WHEN TO AVOID:
  - Cross-service coordination (use Saga instead)
  - High throughput requirements (2PC is slow)
  - Across data centers (network partition risk)
  - More than 3 participants

Implementation Options:

1. JTA (Java Transaction API) with Atomikos/Narayana:
   // Spring Boot with Atomikos
   @Transactional // Spans multiple data sources via JTA
   public void transferBetweenBanks(TransferRequest request) {
       // Both operations are in the SAME distributed transaction
       accountDbTemplate.update("UPDATE accounts SET balance = balance - ? WHERE id = ?",
           request.amount(), request.fromAccountId());
       
       externalBankDbTemplate.update("INSERT INTO transfers (amount, recipient) VALUES (?, ?)",
           request.amount(), request.toAccountId());
       // If either fails, BOTH roll back (2PC protocol)
   }

2. Transactional Outbox (preferred alternative):
   @Transactional // LOCAL transaction only
   public void transfer(TransferRequest request) {
       // Debit locally (atomic with event)
       accountRepo.debit(request.fromAccountId(), request.amount());
       outboxRepo.save(new TransferInitiatedEvent(request));
   }
   // Separate process: publish event → external bank processes → confirm event back

3. CDC-based (Change Data Capture):
   // Just write to your database
   // Debezium captures the change → publishes to Kafka
   // Other service consumes and acts
   // No distributed transaction needed!
```
