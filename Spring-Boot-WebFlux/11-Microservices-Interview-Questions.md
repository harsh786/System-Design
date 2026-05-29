# Microservices Interview Questions (50 Questions)

## Table of Contents
- [Service Design & Communication (Q1-Q15)](#service-design--communication)
- [Resilience Patterns (Q16-Q25)](#resilience-patterns)
- [Data Management (Q26-Q35)](#data-management)
- [Observability (Q36-Q45)](#observability)
- [Spring Cloud (Q46-Q50)](#spring-cloud)

---

## Service Design & Communication

### Q1: Synchronous vs Asynchronous communication - when to use which?

```
SYNCHRONOUS (Request-Response):
  Client ──request──→ Service ──response──→ Client
  
  Use when:
  - Client NEEDS the response to continue
  - Simple CRUD operations
  - Low latency required (<100ms)
  - Strong consistency needed
  
  Protocols: HTTP/REST, gRPC, GraphQL
  
  Risks:
  - Temporal coupling (both must be available)
  - Cascading failures
  - Increased latency with call chains

ASYNCHRONOUS (Event-Driven):
  Producer ──event──→ Message Broker ──event──→ Consumer
  
  Use when:
  - Fire-and-forget operations
  - Long-running processes
  - Decoupling services
  - Handling traffic spikes (queue absorbs burst)
  - Multiple consumers need same event
  
  Protocols: Kafka, RabbitMQ, AWS SQS
  
  Risks:
  - Complexity (eventual consistency)
  - Message ordering challenges
  - Debugging harder (distributed trace needed)
  - Duplicate handling (idempotency required)
```

```java
// Synchronous: Direct HTTP call
@Service
public class OrderService {
    @Autowired private WebClient webClient;
    
    public Order createOrder(OrderRequest request) {
        // MUST get inventory check result before proceeding
        InventoryResponse inventory = webClient.get()
            .uri("http://inventory-service/api/check/{sku}", request.getSku())
            .retrieve()
            .bodyToMono(InventoryResponse.class)
            .block(Duration.ofSeconds(3));
        
        if (!inventory.isAvailable()) {
            throw new OutOfStockException();
        }
        return orderRepo.save(new Order(request));
    }
}

// Asynchronous: Event-driven
@Service
public class OrderService {
    @Autowired private KafkaTemplate<String, OrderEvent> kafka;
    
    public Order createOrder(OrderRequest request) {
        Order order = orderRepo.save(new Order(request, "PENDING"));
        
        // Publish event - don't wait for inventory check
        kafka.send("order-events", order.getId(), 
            new OrderCreatedEvent(order.getId(), request.getSku(), request.getQuantity()));
        
        return order; // Return immediately with PENDING status
    }
}

// Consumer handles asynchronously
@Component
public class InventoryConsumer {
    @KafkaListener(topics = "order-events", groupId = "inventory")
    public void handleOrderCreated(OrderCreatedEvent event) {
        boolean available = inventoryService.checkAndReserve(event.getSku(), event.getQuantity());
        if (available) {
            kafka.send("inventory-events", new InventoryReservedEvent(event.getOrderId()));
        } else {
            kafka.send("inventory-events", new InventoryFailedEvent(event.getOrderId()));
        }
    }
}
```

---

### Q2: REST vs gRPC vs GraphQL - decision matrix

```
┌─────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Aspect      │ REST             │ gRPC             │ GraphQL          │
├─────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Protocol    │ HTTP/1.1, HTTP/2 │ HTTP/2 always    │ HTTP (usually)   │
│ Format      │ JSON (text)      │ Protobuf (binary)│ JSON             │
│ Performance │ Good             │ Excellent (10x)  │ Good             │
│ Streaming   │ SSE, WebSocket   │ Native bidirect. │ Subscriptions    │
│ Schema      │ OpenAPI (opt.)   │ .proto (required)│ SDL (required)   │
│ Code gen    │ Optional         │ Built-in         │ Optional         │
│ Browser     │ Native           │ grpc-web needed  │ Native           │
│ Caching     │ HTTP caching     │ No standard      │ Complex          │
│ File upload │ Multipart        │ Streaming        │ Complex          │
│ Learning    │ Low              │ Medium           │ Medium-High      │
├─────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Best for    │ Public APIs      │ Internal service │ Mobile/frontend  │
│             │ Simple CRUD      │ High performance │ Flexible queries │
│             │ Browser clients  │ Low latency      │ Multiple clients │
└─────────────┴──────────────────┴──────────────────┴──────────────────┘
```

```java
// gRPC with Spring Boot
// 1. Define proto
// service UserService {
//   rpc GetUser (GetUserRequest) returns (User);
//   rpc StreamUsers (StreamRequest) returns (stream User);
// }

// 2. Implement
@GrpcService
public class UserGrpcService extends UserServiceGrpc.UserServiceImplBase {
    @Override
    public void getUser(GetUserRequest request, StreamObserver<User> observer) {
        User user = userRepo.findById(request.getId());
        observer.onNext(user);
        observer.onCompleted();
    }
    
    @Override
    public void streamUsers(StreamRequest request, StreamObserver<User> observer) {
        userRepo.findAll().forEach(observer::onNext);
        observer.onCompleted();
    }
}

// GraphQL with Spring Boot (Spring for GraphQL)
@Controller
public class UserGraphQLController {
    @QueryMapping
    public User userById(@Argument String id) {
        return userService.findById(id);
    }
    
    @SchemaMapping(typeName = "User", field = "orders")
    public List<Order> orders(User user) {
        return orderService.findByUserId(user.getId());
    }
    
    @MutationMapping
    public User createUser(@Argument CreateUserInput input) {
        return userService.create(input);
    }
}
```

---

### Q3: API Gateway pattern with Spring Cloud Gateway

```java
// Spring Cloud Gateway (reactive, Netty-based)
@Configuration
public class GatewayConfig {
    
    @Bean
    public RouteLocator customRoutes(RouteLocatorBuilder builder) {
        return builder.routes()
            // Route to user service
            .route("user-service", r -> r
                .path("/api/users/**")
                .filters(f -> f
                    .stripPrefix(1)                    // Remove /api prefix
                    .addRequestHeader("X-Gateway", "true")
                    .circuitBreaker(c -> c
                        .setName("userCB")
                        .setFallbackUri("forward:/fallback/users"))
                    .retry(retryConfig -> retryConfig
                        .setRetries(3)
                        .setStatuses(HttpStatus.SERVICE_UNAVAILABLE))
                    .requestRateLimiter(rl -> rl
                        .setRateLimiter(redisRateLimiter())
                        .setKeyResolver(userKeyResolver())))
                .uri("lb://user-service"))             // Load balanced
            
            // Route to order service
            .route("order-service", r -> r
                .path("/api/orders/**")
                .and()
                .method(HttpMethod.GET, HttpMethod.POST)
                .filters(f -> f
                    .stripPrefix(1)
                    .addResponseHeader("X-Response-Time", 
                        String.valueOf(System.currentTimeMillis())))
                .uri("lb://order-service"))
            .build();
    }
    
    @Bean
    public RedisRateLimiter redisRateLimiter() {
        return new RedisRateLimiter(100, 200); // 100 req/s, burst 200
    }
    
    @Bean
    public KeyResolver userKeyResolver() {
        return exchange -> Mono.just(
            exchange.getRequest().getHeaders().getFirst("X-API-Key"));
    }
}
```

**Gateway responsibilities:**
```
1. ROUTING: Path-based routing to services
2. AUTHENTICATION: Validate tokens before forwarding
3. RATE LIMITING: Protect services from overload
4. CIRCUIT BREAKING: Fail fast on unhealthy services
5. LOAD BALANCING: Distribute across instances
6. REQUEST TRANSFORMATION: Add/remove headers, rewrite paths
7. RESPONSE AGGREGATION: Combine multiple service responses
8. CACHING: Cache responses for read-heavy endpoints
9. LOGGING/MONITORING: Centralized access logging
10. SSL TERMINATION: HTTPS → HTTP internally
```

---

### Q4: Service Discovery patterns

```
CLIENT-SIDE DISCOVERY (Spring Cloud + Eureka):
  ┌────────────┐
  │  Service   │ ← Register/heartbeat
  │  Registry  │
  │  (Eureka)  │
  └─────┬──────┘
        │ Query
  ┌─────▼──────┐         ┌──────────┐
  │  Client    │ ──────→ │ Service  │ (direct call)
  │  (with LB) │         │ Instance │
  └────────────┘         └──────────┘
  
  - Client fetches registry, does client-side load balancing
  - Pro: Client controls routing, no SPOF proxy
  - Con: Client must implement discovery logic

SERVER-SIDE DISCOVERY (Kubernetes, AWS ALB):
  ┌──────────┐
  │  Client  │
  └────┬─────┘
       │ Request
  ┌────▼─────┐         ┌──────────┐
  │   Load   │ ──────→ │ Service  │
  │ Balancer │         │ Instance │
  └──────────┘         └──────────┘
       ↑ Register
  ┌────┴─────┐
  │ Service  │
  │ Registry │
  └──────────┘
  
  - Load balancer queries registry, routes request
  - Pro: Client is simple, no discovery logic
  - Con: Extra hop, load balancer is potential SPOF
```

```java
// Client-side with Spring Cloud (Eureka)
// application.yml:
eureka:
  client:
    service-url:
      defaultZone: http://eureka-server:8761/eureka/
  instance:
    prefer-ip-address: true

// Usage: WebClient with @LoadBalanced
@Bean
@LoadBalanced
public WebClient.Builder webClientBuilder() {
    return WebClient.builder();
}

// Call by service name (not IP/port!)
webClient.get()
    .uri("http://user-service/api/users/{id}", userId) // "user-service" resolved via registry
    .retrieve()
    .bodyToMono(User.class);

// Kubernetes DNS-based discovery (no Eureka needed):
// Service name: user-service.namespace.svc.cluster.local
// Spring Cloud Kubernetes auto-discovers via K8s API
spring:
  cloud:
    kubernetes:
      discovery:
        enabled: true
        all-namespaces: false
```

---

### Q5: Saga pattern - Orchestration vs Choreography

```
ORCHESTRATION:
  ┌─────────────────────────────────────────────┐
  │           Saga Orchestrator                  │
  │  Step 1 → Step 2 → Step 3                   │
  │  Compensate ← Compensate ← Compensate       │
  └─────────┬───────────┬───────────┬───────────┘
            │           │           │
            ▼           ▼           ▼
       ┌─────────┐ ┌─────────┐ ┌─────────┐
       │ Service │ │ Service │ │ Service │
       │    A    │ │    B    │ │    C    │
       └─────────┘ └─────────┘ └─────────┘

CHOREOGRAPHY:
       ┌─────────┐     ┌─────────┐     ┌─────────┐
       │ Service │ ──→ │ Service │ ──→ │ Service │
       │    A    │ evt │    B    │ evt │    C    │
       └─────────┘     └─────────┘     └─────────┘
            ↑               │               │
            └───────────────┴───────────────┘
                    compensating events
```

```java
// ORCHESTRATION EXAMPLE (using Spring StateMachine or custom)
@Service
public class OrderSagaOrchestrator {
    
    enum SagaState { STARTED, INVENTORY_RESERVED, PAYMENT_PROCESSED, SHIPPING_SCHEDULED, COMPLETED, COMPENSATING, FAILED }
    
    @Transactional
    public OrderResult execute(CreateOrderCommand cmd) {
        SagaLog saga = sagaRepo.save(new SagaLog(cmd.getOrderId(), SagaState.STARTED));
        
        try {
            // Step 1: Reserve inventory
            inventoryClient.reserve(cmd.getItems());
            saga.setState(SagaState.INVENTORY_RESERVED);
            sagaRepo.save(saga);
            
            // Step 2: Process payment
            paymentClient.charge(cmd.getPaymentInfo());
            saga.setState(SagaState.PAYMENT_PROCESSED);
            sagaRepo.save(saga);
            
            // Step 3: Schedule shipping
            shippingClient.schedule(cmd.getAddress());
            saga.setState(SagaState.COMPLETED);
            sagaRepo.save(saga);
            
            return OrderResult.success();
            
        } catch (PaymentException e) {
            compensate(saga, SagaState.INVENTORY_RESERVED);
            return OrderResult.failed("Payment failed: " + e.getMessage());
        } catch (ShippingException e) {
            compensate(saga, SagaState.PAYMENT_PROCESSED);
            return OrderResult.failed("Shipping failed: " + e.getMessage());
        }
    }
    
    private void compensate(SagaLog saga, SagaState failedAt) {
        saga.setState(SagaState.COMPENSATING);
        sagaRepo.save(saga);
        
        switch (failedAt) {
            case PAYMENT_PROCESSED:
                paymentClient.refund(saga.getOrderId());
                // fall through
            case INVENTORY_RESERVED:
                inventoryClient.release(saga.getOrderId());
                break;
        }
        
        saga.setState(SagaState.FAILED);
        sagaRepo.save(saga);
    }
}

// CHOREOGRAPHY EXAMPLE (event-driven)
// Order Service publishes OrderCreated event
// Inventory Service listens, reserves, publishes InventoryReserved
// Payment Service listens to InventoryReserved, charges, publishes PaymentCompleted
// Shipping Service listens to PaymentCompleted, schedules
// If any step fails, compensating events are published

@Component
public class InventoryEventHandler {
    @KafkaListener(topics = "order-events")
    public void onOrderCreated(OrderCreatedEvent event) {
        try {
            inventoryService.reserve(event.getItems());
            kafka.send("inventory-events", 
                new InventoryReservedEvent(event.getOrderId()));
        } catch (InsufficientStockException e) {
            kafka.send("inventory-events", 
                new InventoryFailedEvent(event.getOrderId(), e.getMessage()));
        }
    }
    
    // Compensation: Release reserved stock
    @KafkaListener(topics = "payment-events")
    public void onPaymentFailed(PaymentFailedEvent event) {
        inventoryService.release(event.getOrderId());
    }
}
```

---

## Resilience Patterns

### Q16: Circuit Breaker states and configuration (Resilience4j)

```
STATE MACHINE:
  ┌──────────┐   failure rate     ┌──────────┐
  │  CLOSED  │ ─── > threshold ──→│   OPEN   │
  │(normal)  │                     │(fail fast)│
  └──────────┘                     └────┬─────┘
       ↑                                │
       │    success rate               │ wait duration
       │    > threshold                │ expires
       │                          ┌────▼─────┐
       └──────────────────────────│HALF-OPEN │
                                  │(testing) │
                                  └──────────┘

CLOSED: All calls go through. Monitor failure rate.
OPEN: All calls fail immediately (fallback). Timer running.
HALF-OPEN: Allow limited calls through. Test if service recovered.
```

```yaml
# Resilience4j configuration
resilience4j:
  circuitbreaker:
    instances:
      payment-service:
        # Sliding window
        sliding-window-type: COUNT_BASED      # or TIME_BASED
        sliding-window-size: 10                # Last 10 calls
        minimum-number-of-calls: 5             # Min calls before evaluating
        
        # Thresholds
        failure-rate-threshold: 50             # 50% failures → OPEN
        slow-call-rate-threshold: 80           # 80% slow calls → OPEN
        slow-call-duration-threshold: 2s       # What's "slow"
        
        # State transitions
        wait-duration-in-open-state: 30s       # Stay OPEN for 30s
        permitted-number-of-calls-in-half-open-state: 3  # Test with 3 calls
        automatic-transition-from-open-to-half-open-enabled: true
        
        # Exception handling
        record-exceptions:
          - java.io.IOException
          - java.net.SocketTimeoutException
        ignore-exceptions:
          - com.example.BusinessException      # Don't count business errors
```

---

### Q17: Bulkhead pattern (Thread pool vs Semaphore)

```java
// SEMAPHORE BULKHEAD: Limits concurrent calls (no thread pool)
@Bulkhead(name = "inventoryService", fallbackMethod = "inventoryFallback")
public String checkInventory(String sku) {
    return inventoryClient.check(sku);
}

resilience4j:
  bulkhead:
    instances:
      inventoryService:
        max-concurrent-calls: 10        # Max 10 concurrent
        max-wait-duration: 500ms        # Wait 500ms for permit

// THREAD POOL BULKHEAD: Separate thread pool (true isolation)
@Bulkhead(name = "paymentService", type = Bulkhead.Type.THREADPOOL)
public CompletableFuture<Payment> processPayment(PaymentRequest req) {
    return CompletableFuture.supplyAsync(() -> paymentClient.charge(req));
}

resilience4j:
  thread-pool-bulkhead:
    instances:
      paymentService:
        max-thread-pool-size: 10       # Max 10 threads
        core-thread-pool-size: 5       # Core 5 threads
        queue-capacity: 20             # Queue up to 20
        keep-alive-duration: 60s

// COMPARISON:
// Semaphore: Lower overhead, caller's thread used
//   Use when: Limiting concurrency, same thread acceptable
// Thread Pool: True isolation, separate threads
//   Use when: Need timeout enforcement, thread isolation from caller
```

---

## Data Management

### Q26: Database per service pattern

```
                    ┌─────────────┐
                    │ Order       │
                    │ Service     │
                    │      ┌──────┤
                    │      │Orders│ (PostgreSQL)
                    └──────┴──────┘
                    
                    ┌─────────────┐
                    │ User        │
                    │ Service     │
                    │      ┌──────┤
                    │      │Users │ (PostgreSQL)
                    └──────┴──────┘
                    
                    ┌─────────────┐
                    │ Product     │
                    │ Service     │
                    │     ┌───────┤
                    │     │Catalog│ (MongoDB)
                    └─────┴───────┘
                    
                    ┌─────────────┐
                    │ Search      │
                    │ Service     │
                    │    ┌────────┤
                    │    │Index   │ (Elasticsearch)
                    └────┴────────┘

Benefits:
  - Independent scaling
  - Polyglot persistence (best DB for each use case)
  - Loose coupling
  - Independent schema evolution

Challenges:
  - Cross-service queries (no JOIN)
  - Distributed transactions
  - Data consistency
  - Data duplication
```

```java
// Cross-service query: API Composition pattern
@Service
public class OrderDetailsService {
    @Autowired private WebClient webClient;
    
    public Mono<OrderDetails> getOrderDetails(String orderId) {
        Mono<Order> order = webClient.get()
            .uri("http://order-service/api/orders/{id}", orderId)
            .retrieve().bodyToMono(Order.class);
        
        Mono<User> user = order.flatMap(o -> webClient.get()
            .uri("http://user-service/api/users/{id}", o.getUserId())
            .retrieve().bodyToMono(User.class));
        
        Mono<List<Product>> products = order.flatMap(o -> 
            Flux.fromIterable(o.getProductIds())
                .flatMap(pid -> webClient.get()
                    .uri("http://product-service/api/products/{id}", pid)
                    .retrieve().bodyToMono(Product.class))
                .collectList());
        
        return Mono.zip(order, user, products)
            .map(t -> new OrderDetails(t.getT1(), t.getT2(), t.getT3()));
    }
}
```

---

### Q27: Transactional Outbox pattern

```java
// PROBLEM: "Dual write" - updating DB AND sending message can fail partially
// DB committed but message lost, OR message sent but DB rolled back

// SOLUTION: Store event in same DB transaction, publish from outbox

@Entity
@Table(name = "outbox_events")
public class OutboxEvent {
    @Id @GeneratedValue
    private Long id;
    private String aggregateId;
    private String aggregateType;
    private String eventType;
    
    @Column(columnDefinition = "jsonb")
    private String payload;
    
    private Instant createdAt;
    private boolean published;
}

@Service
public class OrderService {
    @Transactional  // SAME transaction for both!
    public Order createOrder(CreateOrderRequest request) {
        // 1. Save order
        Order order = orderRepo.save(new Order(request));
        
        // 2. Save event to outbox (same transaction!)
        outboxRepo.save(new OutboxEvent(
            order.getId(),
            "Order",
            "OrderCreated",
            toJson(new OrderCreatedEvent(order)),
            Instant.now(),
            false
        ));
        
        return order;
        // If TX commits: both order AND event are saved
        // If TX fails: neither is saved → consistent!
    }
}

// Outbox publisher (polls and publishes)
@Component
public class OutboxPublisher {
    @Scheduled(fixedDelay = 1000)  // Every 1 second
    @SchedulerLock(name = "outboxPublisher", lockAtLeastFor = "500ms")
    @Transactional
    public void publishOutboxEvents() {
        List<OutboxEvent> events = outboxRepo.findByPublishedFalseOrderByCreatedAt(
            PageRequest.of(0, 100));
        
        for (OutboxEvent event : events) {
            try {
                kafka.send(event.getAggregateType() + "-events",
                    event.getAggregateId(), event.getPayload());
                event.setPublished(true);
                outboxRepo.save(event);
            } catch (Exception e) {
                log.error("Failed to publish event: {}", event.getId(), e);
                break; // Retry next cycle
            }
        }
    }
}

// Alternative: CDC (Change Data Capture) with Debezium
// Debezium reads PostgreSQL WAL (Write-Ahead Log)
// Publishes outbox table changes to Kafka automatically
// No polling needed, near real-time, exactly-once possible
```

---

### Q28: CDC with Debezium

```json
// Debezium PostgreSQL connector configuration
{
  "name": "order-outbox-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "secret",
    "database.dbname": "orderdb",
    "table.include.list": "public.outbox_events",
    "transforms": "outbox",
    "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
    "transforms.outbox.table.field.event.key": "aggregate_id",
    "transforms.outbox.table.field.event.type": "event_type",
    "transforms.outbox.table.field.event.payload": "payload",
    "transforms.outbox.route.by.field": "aggregate_type",
    "transforms.outbox.route.topic.replacement": "${routedByValue}-events"
  }
}
```

---

## Observability

### Q36: Distributed tracing with Micrometer Tracing

```java
// Spring Boot 3 auto-configuration:
// Dependencies:
// - micrometer-tracing-bridge-brave (Zipkin)
// - zipkin-reporter-brave

// application.yml:
management:
  tracing:
    sampling:
      probability: 0.1  # Sample 10% in production
  zipkin:
    tracing:
      endpoint: http://zipkin:9411/api/v2/spans

// Automatic instrumentation includes:
// - HTTP server requests (incoming)
// - RestTemplate / WebClient (outgoing)
// - @Async methods
// - Kafka producer/consumer
// - Spring Data repositories
// - Spring Security authentication

// Custom span creation:
@Service
public class PaymentService {
    private final Tracer tracer;
    
    public Payment processPayment(PaymentRequest request) {
        Span span = tracer.nextSpan().name("process-payment").start();
        try (Tracer.SpanInScope ws = tracer.withSpan(span)) {
            span.tag("payment.amount", request.getAmount().toString());
            span.tag("payment.method", request.getMethod());
            
            Payment result = doProcess(request);
            
            span.event("payment.completed");
            return result;
        } catch (Exception e) {
            span.error(e);
            throw e;
        } finally {
            span.end();
        }
    }
}

// Using @Observed (simpler):
@Observed(name = "payment.process", 
    contextualName = "processing-payment",
    lowCardinalityKeyValues = {"payment.type", "credit-card"})
public Payment processPayment(PaymentRequest request) {
    return doProcess(request);
}
```

---

### Q37: SLOs, SLIs, and SLAs

```
SLI (Service Level Indicator): A metric that measures service behavior
  - Request latency (p99 < 200ms)
  - Error rate (< 0.1%)
  - Availability (successful requests / total requests)
  - Throughput (requests per second)

SLO (Service Level Objective): Target value for an SLI
  - "99.9% of requests complete within 200ms"
  - "99.95% availability per month"
  - "Error rate below 0.1% per hour"

SLA (Service Level Agreement): Business contract with consequences
  - "If availability drops below 99.9%, customer gets credit"
  - SLA ≤ SLO (SLO should be stricter than SLA)

ERROR BUDGET = 1 - SLO
  - SLO 99.9% → Error budget = 0.1%
  - Per month: 0.1% of 43,200 minutes = 43.2 minutes of downtime allowed
  - If budget exhausted: freeze deployments, focus on reliability
```

```java
// Implementing SLI monitoring with Micrometer
@Component
public class SLIMonitor {
    private final MeterRegistry registry;
    
    @PostConstruct
    public void registerSLIs() {
        // Availability SLI
        Gauge.builder("sli.availability", this, SLIMonitor::calculateAvailability)
            .description("Success rate over last 5 minutes")
            .register(registry);
    }
    
    private double calculateAvailability() {
        double total = registry.get("http.server.requests").timer().count();
        double errors = registry.get("http.server.requests")
            .tag("status", "5xx").timer().count();
        return total > 0 ? (total - errors) / total : 1.0;
    }
}

// Prometheus alerting rule:
// alert: SLO_Availability_Violation
// expr: (1 - rate(http_server_requests_seconds_count{status=~"5.."}[5m]) 
//        / rate(http_server_requests_seconds_count[5m])) < 0.999
// for: 5m
// labels:
//   severity: critical
```

---

### Q38: Zero-downtime deployment patterns

```yaml
# ROLLING UPDATE (Kubernetes default)
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0     # Never reduce below desired count
      maxSurge: 1           # Add 1 extra pod during update
  
# Process:
# 1. Create new pod (v2)
# 2. Wait for readiness probe to pass
# 3. Start routing traffic to v2
# 4. Terminate old pod (v1)
# 5. Repeat until all pods updated

# BLUE-GREEN
# Two identical environments:
# Blue (current) ← All traffic
# Green (new)    ← Deploy and test here
# Switch: Move load balancer from Blue to Green (instant cutover)
# Rollback: Switch back to Blue

# CANARY
# Route small % of traffic to new version
# Monitor error rates, latency
# Gradually increase % if healthy
# Roll back if issues detected

# Canary with Istio:
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
spec:
  hosts: ["order-service"]
  http:
    - route:
        - destination:
            host: order-service
            subset: v1
          weight: 95        # 95% to old version
        - destination:
            host: order-service
            subset: v2
          weight: 5         # 5% to new version (canary)
```

---

## Spring Cloud

### Q46: Spring Cloud Config Server

```java
// Config Server (centralized configuration)
@SpringBootApplication
@EnableConfigServer
public class ConfigServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(ConfigServerApplication.class, args);
    }
}

// Config Server application.yml:
spring:
  cloud:
    config:
      server:
        git:
          uri: https://github.com/org/config-repo
          default-label: main
          search-paths: "{application}"
        encrypt:
          enabled: true

// Client configuration:
spring:
  config:
    import: "configserver:http://config-server:8888"
  cloud:
    config:
      fail-fast: true
      retry:
        max-attempts: 5

// Dynamic refresh:
@RefreshScope
@Component
public class DynamicConfig {
    @Value("${feature.new-ui.enabled:false}")
    private boolean newUiEnabled;
    // Changes when /actuator/refresh is called
}

// Encrypted properties in config repo:
// db.password: '{cipher}AQBHOGq...'
// Decrypted by config server before serving to clients
```

---

### Q47: Spring Cloud Stream with Kafka

```java
// Producer
@Service
public class OrderEventProducer {
    @Autowired
    private StreamBridge streamBridge;
    
    public void publishOrderCreated(Order order) {
        streamBridge.send("orderEvents-out-0", 
            MessageBuilder.withPayload(new OrderCreatedEvent(order))
                .setHeader("partitionKey", order.getUserId())
                .build());
    }
}

// Consumer
@Bean
public Consumer<Message<OrderCreatedEvent>> orderEvents() {
    return message -> {
        OrderCreatedEvent event = message.getPayload();
        log.info("Processing order: {}", event.getOrderId());
        orderService.process(event);
    };
}

// Configuration:
spring:
  cloud:
    stream:
      bindings:
        orderEvents-out-0:
          destination: order-events
          content-type: application/json
        orderEvents-in-0:
          destination: order-events
          group: order-processor   # Consumer group
          content-type: application/json
      kafka:
        binder:
          brokers: kafka:9092
          auto-create-topics: true
        bindings:
          orderEvents-in-0:
            consumer:
              start-offset: latest
              enable-dlq: true     # Dead letter queue
              dlq-name: order-events-dlq
              max-attempts: 3
              back-off-initial-interval: 1000

// Function composition:
@Bean
public Function<Flux<Order>, Flux<Notification>> processAndNotify() {
    return orders -> orders
        .filter(order -> order.getTotal().compareTo(BigDecimal.valueOf(100)) > 0)
        .map(order -> new Notification(order.getUserId(), "High value order!"));
}
```

---

### Q48: Spring Cloud Circuit Breaker

```java
// Reactive circuit breaker factory
@Service
public class ResilientOrderService {
    private final ReactiveCircuitBreakerFactory cbFactory;
    private final WebClient webClient;
    
    public Mono<Inventory> checkInventory(String productId) {
        return cbFactory.create("inventory")
            .run(
                webClient.get()
                    .uri("http://inventory-service/api/{id}", productId)
                    .retrieve()
                    .bodyToMono(Inventory.class),
                throwable -> {
                    log.warn("Inventory service down, using fallback");
                    return Mono.just(Inventory.unknown(productId));
                }
            );
    }
}

// Customization:
@Bean
public Customizer<Resilience4JCircuitBreakerFactory> defaultCustomizer() {
    return factory -> factory.configureDefault(id -> 
        new Resilience4JConfigBuilder(id)
            .circuitBreakerConfig(CircuitBreakerConfig.custom()
                .slidingWindowSize(10)
                .failureRateThreshold(50)
                .waitDurationInOpenState(Duration.ofSeconds(30))
                .build())
            .timeLimiterConfig(TimeLimiterConfig.custom()
                .timeoutDuration(Duration.ofSeconds(3))
                .build())
            .build());
}
```

---

### Q49: Spring Cloud Kubernetes

```java
// Auto-discovery via Kubernetes API
spring:
  cloud:
    kubernetes:
      discovery:
        enabled: true
        all-namespaces: false
      config:
        enabled: true
        sources:
          - name: ${spring.application.name}
            namespace: default
      reload:
        enabled: true
        mode: event           # Watch for ConfigMap changes
        strategy: refresh     # Refresh @RefreshScope beans

// ConfigMap as application properties:
apiVersion: v1
kind: ConfigMap
metadata:
  name: order-service
data:
  application.yml: |
    app:
      feature:
        new-checkout: true
      timeout:
        payment: 5000

// Secrets as properties:
apiVersion: v1
kind: Secret
metadata:
  name: order-service-secrets
type: Opaque
data:
  db-password: cGFzc3dvcmQ=  # base64 encoded
```

---

### Q50: Choosing between Spring Cloud components

```
SERVICE DISCOVERY:
  - Eureka: Self-contained, CP system, Java ecosystem
  - Consul: Multi-language, KV store, health checks
  - Kubernetes DNS: Native K8s, no extra infra

CONFIGURATION:
  - Spring Cloud Config: Git-backed, encryption, audit trail
  - Consul KV: Real-time, no git needed
  - Kubernetes ConfigMaps: Native K8s, simple

API GATEWAY:
  - Spring Cloud Gateway: Reactive, Netty, programmable
  - Kong: Plugin-based, multi-language, admin API
  - Istio: Service mesh, sidecar proxy, advanced traffic control

MESSAGING:
  - Spring Cloud Stream (Kafka): High throughput, ordering, replay
  - Spring Cloud Stream (RabbitMQ): Flexible routing, lower latency
  - Spring Cloud Stream (AWS): SQS/SNS, managed, no infra

CIRCUIT BREAKER:
  - Resilience4j: Lightweight, functional, Spring Boot native
  - (Hystrix: DEPRECATED - don't use in new projects)

TRACING:
  - Micrometer Tracing (Zipkin): Simple, well-integrated
  - Micrometer Tracing (OpenTelemetry): Vendor-neutral, emerging standard
```
