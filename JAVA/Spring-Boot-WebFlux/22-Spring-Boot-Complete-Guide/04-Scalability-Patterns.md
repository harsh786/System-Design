# Scalability Patterns in Spring Boot

## Table of Contents
1. [Scalability Fundamentals](#scalability-fundamentals)
2. [Horizontal vs Vertical Scaling](#horizontal-vs-vertical-scaling)
3. [Stateless Application Design](#stateless-application-design)
4. [Caching Strategies](#caching-strategies)
5. [Database Scalability](#database-scalability)
6. [Async & Event-Driven Architecture](#async--event-driven-architecture)
7. [Connection Pooling Optimization](#connection-pooling-optimization)
8. [Load Balancing Patterns](#load-balancing-patterns)
9. [Microservices Scalability](#microservices-scalability)
10. [Resilience Patterns](#resilience-patterns)
11. [Performance Tuning Checklist](#performance-tuning-checklist)
12. [Scaling Metrics & Monitoring](#scaling-metrics--monitoring)

---

## Scalability Fundamentals

### What Limits Scalability?

```
┌──────────────────────────────────────────────────────────────┐
│                BOTTLENECK HIERARCHY                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Most Common Bottlenecks (in order):                         │
│                                                               │
│  1. DATABASE                                                 │
│     └── Connection pool exhaustion                           │
│     └── Slow queries / missing indexes                       │
│     └── Lock contention                                      │
│     └── Single DB can't handle load                          │
│                                                               │
│  2. THREAD POOL                                              │
│     └── All Tomcat threads blocked on I/O                    │
│     └── Thread starvation from slow downstream services      │
│                                                               │
│  3. MEMORY                                                   │
│     └── Large object creation per request                    │
│     └── Memory leaks                                         │
│     └── GC pauses under load                                 │
│                                                               │
│  4. NETWORK                                                  │
│     └── Chatty services (too many calls)                     │
│     └── Large payloads                                       │
│     └── DNS resolution                                       │
│                                                               │
│  5. CPU                                                      │
│     └── Serialization/deserialization overhead               │
│     └── Encryption/compression                               │
│     └── Complex business logic                               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Horizontal vs Vertical Scaling

### Vertical Scaling (Scale Up)

```yaml
# JVM Tuning for vertical scaling
# More CPU + More RAM = Handle more load on single instance

# JVM Options:
JAVA_OPTS: >
  -Xms4g -Xmx4g           # Fixed heap size
  -XX:+UseG1GC             # G1 garbage collector
  -XX:MaxGCPauseMillis=200 # Target GC pause
  -XX:+UseStringDeduplication
  -XX:MetaspaceSize=256m

# Increase thread pools proportionally:
server:
  tomcat:
    threads:
      max: 400  # More threads with more CPU cores
spring:
  datasource:
    hikari:
      maximum-pool-size: 50  # More connections with more RAM
```

### Horizontal Scaling (Scale Out)

```
┌─────────────────────────────────────────────────────────────┐
│  HORIZONTAL SCALING ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│               ┌───────────────┐                              │
│               │ Load Balancer │                              │
│               └───────┬───────┘                              │
│          ┌────────────┼────────────┐                         │
│          │            │            │                          │
│    ┌─────▼─────┐┌─────▼─────┐┌─────▼─────┐                 │
│    │ Instance 1 ││ Instance 2 ││ Instance 3 │                │
│    │ (Pod/VM)  ││ (Pod/VM)  ││ (Pod/VM)  │                  │
│    └─────┬─────┘└─────┬─────┘└─────┬─────┘                 │
│          │            │            │                          │
│          └────────────┼────────────┘                         │
│                       │                                      │
│    ┌──────────────────┼──────────────────┐                   │
│    │                  │                   │                   │
│  ┌─▼──────┐   ┌──────▼──┐   ┌───────────▼──┐              │
│  │ Redis  │   │ Database │   │ Message Queue │              │
│  │(Cache) │   │(Primary) │   │  (Kafka/RMQ)  │              │
│  └────────┘   └──────────┘   └──────────────┘              │
│                                                              │
│  Requirements for horizontal scaling:                        │
│  ✓ Stateless application (no in-memory session)             │
│  ✓ Externalized session/cache (Redis)                       │
│  ✓ Shared nothing architecture                              │
│  ✓ Idempotent operations                                    │
│  ✓ Database can handle multiple connections                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Stateless Application Design

### Session Externalization

```java
// PROBLEM: In-memory sessions don't scale horizontally
// If user hits Instance 1, then Instance 2 loses their session

// SOLUTION 1: Spring Session with Redis
@Configuration
@EnableRedisHttpSession(maxInactiveIntervalInSeconds = 3600)
public class SessionConfig {
    @Bean
    public LettuceConnectionFactory connectionFactory() {
        return new LettuceConnectionFactory("redis-host", 6379);
    }
}

// application.yml
spring:
  session:
    store-type: redis
    redis:
      namespace: myapp:session
  redis:
    host: redis-cluster.internal
    port: 6379

// SOLUTION 2: JWT (Stateless - PREFERRED for APIs)
@Configuration
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()))
            .build();
    }
}
// No server-side session needed! Token contains all auth info.
```

### Stateless Service Design

```java
// GOOD: Stateless service - all state comes from request or DB
@Service
public class OrderService {
    private final OrderRepository orderRepo;
    private final PaymentClient paymentClient;
    
    public OrderResponse processOrder(OrderRequest request) {
        // All input from request
        Order order = createOrder(request);
        // All state in DB
        Order saved = orderRepo.save(order);
        // All external state from external service
        PaymentResult payment = paymentClient.charge(request.getPaymentInfo());
        return new OrderResponse(saved, payment);
    }
}

// BAD: Stateful service - state in instance memory
@Service
public class BadOrderService {
    private Map<String, Order> pendingOrders = new HashMap<>(); // LOST on restart!
    private int orderCount = 0; // Wrong count with multiple instances!
    
    public void addPendingOrder(Order order) {
        pendingOrders.put(order.getId(), order); // Only visible to this instance!
    }
}
```

---

## Caching Strategies

### Multi-Level Caching

```
┌────────────────────────────────────────────────────────────┐
│              MULTI-LEVEL CACHE ARCHITECTURE                  │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Request → L1 Cache (in-memory, per instance)              │
│              │                                              │
│              │ Miss                                         │
│              ▼                                              │
│            L2 Cache (Redis, shared across instances)        │
│              │                                              │
│              │ Miss                                         │
│              ▼                                              │
│            Database (source of truth)                       │
│              │                                              │
│              │ Result                                       │
│              ▼                                              │
│            Populate L2 → Populate L1 → Return               │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Spring Cache Implementation

```java
@Configuration
@EnableCaching
public class CacheConfig {
    
    @Bean
    public CacheManager cacheManager(RedisConnectionFactory factory) {
        // L2: Redis cache
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(10))
            .serializeKeysWith(RedisSerializationContext.SerializationPair
                .fromSerializer(new StringRedisSerializer()))
            .serializeValuesWith(RedisSerializationContext.SerializationPair
                .fromSerializer(new GenericJackson2JsonRedisSerializer()))
            .disableCachingNullValues();
        
        return RedisCacheManager.builder(factory)
            .cacheDefaults(config)
            .withCacheConfiguration("users",
                config.entryTtl(Duration.ofMinutes(5)))
            .withCacheConfiguration("products",
                config.entryTtl(Duration.ofHours(1)))
            .build();
    }
    
    // L1: Caffeine (in-memory, per instance)
    @Bean
    public CacheManager localCacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager();
        manager.setCaffeine(Caffeine.newBuilder()
            .maximumSize(10_000)
            .expireAfterWrite(Duration.ofMinutes(2))
            .recordStats());
        return manager;
    }
}
```

### Cache Annotations

```java
@Service
public class ProductService {
    
    @Cacheable(value = "products", key = "#id", unless = "#result == null")
    public Product findById(Long id) {
        return productRepository.findById(id).orElse(null);
    }
    
    @Cacheable(value = "products", key = "#category + '-' + #page")
    public Page<Product> findByCategory(String category, int page) {
        return productRepository.findByCategory(category, PageRequest.of(page, 20));
    }
    
    @CachePut(value = "products", key = "#product.id") // Updates cache
    public Product update(Product product) {
        return productRepository.save(product);
    }
    
    @CacheEvict(value = "products", key = "#id")
    public void delete(Long id) {
        productRepository.deleteById(id);
    }
    
    @CacheEvict(value = "products", allEntries = true)
    public void clearCache() {
        // Evicts all entries in "products" cache
    }
    
    @Caching(evict = {
        @CacheEvict(value = "products", key = "#product.id"),
        @CacheEvict(value = "productsByCategory", key = "#product.category")
    })
    public Product updateProduct(Product product) {
        return productRepository.save(product);
    }
}
```

### Cache-Aside vs Write-Through vs Write-Behind

```java
// CACHE-ASIDE (most common with @Cacheable)
// App manages cache explicitly
@Cacheable("users")
public User getUser(Long id) {
    return db.findUser(id); // Only called on cache miss
}

// WRITE-THROUGH
// Write to cache AND DB synchronously
@CachePut(value = "users", key = "#user.id")
@Transactional
public User saveUser(User user) {
    return userRepo.save(user); // Saves to DB, return value cached
}

// WRITE-BEHIND (async write to DB)
// Write to cache immediately, batch-write to DB later
// Not natively supported by Spring Cache - use custom implementation
public void saveUserWriteBehind(User user) {
    cacheManager.getCache("users").put(user.getId(), user);
    asyncWriteQueue.enqueue(user); // Writes to DB asynchronously
}
```

---

## Database Scalability

### Read Replicas

```java
// Route read queries to replicas, writes to primary
@Configuration
public class DataSourceConfig {
    
    @Bean
    @Primary
    public DataSource routingDataSource() {
        Map<Object, Object> targetDataSources = new HashMap<>();
        targetDataSources.put(DataSourceType.PRIMARY, primaryDataSource());
        targetDataSources.put(DataSourceType.REPLICA, replicaDataSource());
        
        RoutingDataSource routingDS = new RoutingDataSource();
        routingDS.setTargetDataSources(targetDataSources);
        routingDS.setDefaultTargetDataSource(primaryDataSource());
        return routingDS;
    }
}

public class RoutingDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        return TransactionSynchronizationManager.isCurrentTransactionReadOnly()
            ? DataSourceType.REPLICA
            : DataSourceType.PRIMARY;
    }
}

// Usage:
@Service
public class UserService {
    @Transactional(readOnly = true) // Routes to REPLICA
    public User findById(Long id) {
        return userRepo.findById(id).orElseThrow();
    }
    
    @Transactional // Routes to PRIMARY
    public User save(User user) {
        return userRepo.save(user);
    }
}
```

### Connection Pool Optimization

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      # Key performance settings:
      connection-timeout: 3000    # Fail fast
      validation-timeout: 2000
      leak-detection-threshold: 30000
      
      # Prepared statement caching
      data-source-properties:
        cachePrepStmts: true
        prepStmtCacheSize: 250
        prepStmtCacheSqlLimit: 2048
        useServerPrepStmts: true
```

### Pagination & Efficient Queries

```java
// ALWAYS paginate large result sets
public interface OrderRepository extends JpaRepository<Order, Long> {
    
    // Offset pagination (simple but slow for large offsets)
    Page<Order> findByStatus(OrderStatus status, Pageable pageable);
    
    // Keyset/Cursor pagination (efficient for large datasets)
    @Query("SELECT o FROM Order o WHERE o.id > :lastId ORDER BY o.id LIMIT :size")
    List<Order> findAfter(@Param("lastId") Long lastId, @Param("size") int size);
    
    // Projections - only fetch needed columns
    @Query("SELECT new com.example.dto.OrderSummary(o.id, o.status, o.total) FROM Order o")
    Page<OrderSummary> findSummaries(Pageable pageable);
}

// N+1 Query Prevention
@EntityGraph(attributePaths = {"items", "customer"})
@Query("SELECT o FROM Order o WHERE o.status = :status")
List<Order> findByStatusWithDetails(@Param("status") OrderStatus status);
```

### Database Sharding Concepts

```
┌────────────────────────────────────────────────────────────┐
│              DATABASE SHARDING                               │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Shard Key: user_id                                        │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Shard 0  │  │ Shard 1  │  │ Shard 2  │  │ Shard 3  │  │
│  │ users    │  │ users    │  │ users    │  │ users    │  │
│  │ 0-999    │  │1000-1999 │  │2000-2999 │  │3000-3999 │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  Routing: shard_number = user_id % num_shards              │
│                                                             │
│  Spring Boot Implementation:                               │
│  - ShardingSphere-JDBC (transparent sharding)              │
│  - Custom AbstractRoutingDataSource                        │
│  - Vitess (for MySQL)                                      │
│  - Citus (for PostgreSQL)                                  │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

## Async & Event-Driven Architecture

### Application Events

```java
// Event class
public record OrderCreatedEvent(Long orderId, Long userId, BigDecimal amount) {}

// Publisher
@Service
public class OrderService {
    private final ApplicationEventPublisher eventPublisher;
    
    @Transactional
    public Order createOrder(OrderRequest request) {
        Order order = orderRepo.save(new Order(request));
        
        // Publish event AFTER transaction commits
        eventPublisher.publishEvent(new OrderCreatedEvent(
            order.getId(), order.getUserId(), order.getTotal()));
        
        return order;
    }
}

// Listeners (run in parallel, decoupled)
@Component
public class InventoryEventListener {
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleOrderCreated(OrderCreatedEvent event) {
        inventoryService.reserve(event.orderId());
    }
}

@Component
public class NotificationEventListener {
    @Async
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        emailService.sendOrderConfirmation(event.userId(), event.orderId());
    }
}

@Component
public class AnalyticsEventListener {
    @Async
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        analyticsService.trackPurchase(event.userId(), event.amount());
    }
}
```

### Message Queue Integration (Kafka)

```java
// Producer
@Service
public class OrderEventProducer {
    private final KafkaTemplate<String, OrderEvent> kafkaTemplate;
    
    public void publishOrderCreated(Order order) {
        OrderEvent event = new OrderEvent(order.getId(), "CREATED", Instant.now());
        kafkaTemplate.send("orders", order.getId().toString(), event)
            .whenComplete((result, ex) -> {
                if (ex != null) {
                    log.error("Failed to publish event", ex);
                    // Store in outbox table for retry
                }
            });
    }
}

// Consumer (separate service or same service)
@Component
public class OrderEventConsumer {
    
    @KafkaListener(
        topics = "orders",
        groupId = "inventory-service",
        concurrency = "3"  // 3 consumer threads
    )
    public void processOrderEvent(OrderEvent event, Acknowledgment ack) {
        try {
            inventoryService.processOrder(event);
            ack.acknowledge(); // Manual ack after processing
        } catch (Exception e) {
            // Don't ack - message will be redelivered
            log.error("Failed to process order event", e);
        }
    }
}
```

### Outbox Pattern (Reliable Event Publishing)

```java
// Ensures event is published exactly once, even if Kafka is down
@Entity
@Table(name = "outbox_events")
public class OutboxEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String aggregateType;
    private String aggregateId;
    private String eventType;
    private String payload; // JSON
    private Instant createdAt;
    private boolean published;
}

@Service
public class OrderService {
    @Transactional // Same transaction as business logic
    public Order createOrder(OrderRequest request) {
        Order order = orderRepo.save(new Order(request));
        
        // Save event to outbox IN SAME TRANSACTION
        outboxRepo.save(new OutboxEvent(
            "Order", order.getId().toString(), "OrderCreated",
            objectMapper.writeValueAsString(order), Instant.now(), false
        ));
        
        return order;
    }
}

// Separate publisher reads outbox and publishes to Kafka
@Scheduled(fixedDelay = 1000)
@Transactional
public void publishPendingEvents() {
    List<OutboxEvent> events = outboxRepo.findByPublishedFalse(Limit.of(100));
    for (OutboxEvent event : events) {
        kafkaTemplate.send("orders", event.getAggregateId(), event.getPayload());
        event.setPublished(true);
    }
}
```

---

## Connection Pooling Optimization

### HTTP Client Connection Pooling

```java
@Configuration
public class HttpClientConfig {
    
    @Bean
    public RestClient restClient() {
        // Connection pool for outgoing HTTP calls
        var connectionManager = PoolingHttpClientConnectionManager.custom()
            .setMaxConnTotal(200)           // Total connections across all routes
            .setMaxConnPerRoute(50)          // Max connections per host
            .setDefaultConnectionConfig(ConnectionConfig.custom()
                .setConnectTimeout(Timeout.ofSeconds(3))
                .setSocketTimeout(Timeout.ofSeconds(10))
                .build())
            .build();
        
        var httpClient = HttpClients.custom()
            .setConnectionManager(connectionManager)
            .setKeepAliveStrategy((response, context) -> TimeValue.ofSeconds(30))
            .evictIdleConnections(TimeValue.ofSeconds(60))
            .build();
        
        return RestClient.builder()
            .requestFactory(new HttpComponentsClientHttpRequestFactory(httpClient))
            .build();
    }
}
```

### WebClient Connection Pooling (Reactive)

```java
@Configuration
public class WebClientConfig {
    
    @Bean
    public WebClient webClient() {
        ConnectionProvider provider = ConnectionProvider.builder("custom")
            .maxConnections(200)
            .maxIdleTime(Duration.ofSeconds(30))
            .maxLifeTime(Duration.ofMinutes(5))
            .pendingAcquireTimeout(Duration.ofSeconds(5))
            .evictInBackground(Duration.ofSeconds(30))
            .metrics(true)
            .build();
        
        HttpClient httpClient = HttpClient.create(provider)
            .responseTimeout(Duration.ofSeconds(10))
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 3000);
        
        return WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .build();
    }
}
```

---

## Load Balancing Patterns

### Client-Side Load Balancing (Spring Cloud)

```java
// With Spring Cloud LoadBalancer
@Configuration
public class LoadBalancerConfig {
    @Bean
    @LoadBalanced  // Enables service discovery & load balancing
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}

@Service
public class OrderService {
    @Autowired
    private RestTemplate restTemplate;
    
    public PaymentResult processPayment(PaymentRequest request) {
        // "payment-service" resolved via service registry (Eureka/Consul)
        return restTemplate.postForObject(
            "http://payment-service/api/payments", request, PaymentResult.class);
    }
}
```

### Health Checks for Load Balancer

```java
@Component
public class CustomHealthIndicator implements HealthIndicator {
    
    @Override
    public Health health() {
        if (canServeTraffic()) {
            return Health.up()
                .withDetail("db", "connected")
                .withDetail("cache", "available")
                .build();
        }
        return Health.down()
            .withDetail("reason", "Database unreachable")
            .build();
    }
}

// application.yml
management:
  endpoint:
    health:
      show-details: always
      probes:
        enabled: true  # Kubernetes liveness/readiness probes
  health:
    livenessState:
      enabled: true
    readinessState:
      enabled: true
```

### Graceful Shutdown

```yaml
server:
  shutdown: graceful  # Wait for active requests to complete

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # Max wait before forcing shutdown

# Shutdown sequence:
# 1. Stop accepting new requests
# 2. Load balancer health check returns DOWN
# 3. Wait for in-flight requests to complete (up to 30s)
# 4. Close connections
# 5. Destroy beans (@PreDestroy)
# 6. JVM exits
```

---

## Microservices Scalability

### Independent Scaling

```
┌──────────────────────────────────────────────────────────┐
│  INDEPENDENT SERVICE SCALING                              │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Service         Load Profile       Scaling Strategy      │
│  ─────────────   ──────────────     ──────────────────   │
│  API Gateway     High RPS, low CPU  Scale horizontally   │
│  Auth Service    Moderate, bursty   HPA on CPU           │
│  Order Service   High, I/O bound   Scale on queue depth  │
│  Search Service  CPU intensive      Scale on CPU + RAM   │
│  Report Service  Batch/scheduled    Scale on schedule    │
│  Notification    Async, high volume Scale on queue depth │
│                                                           │
│  Kubernetes HPA Example:                                 │
│  apiVersion: autoscaling/v2                              │
│  kind: HorizontalPodAutoscaler                           │
│  spec:                                                   │
│    scaleTargetRef:                                       │
│      kind: Deployment                                    │
│      name: order-service                                 │
│    minReplicas: 3                                        │
│    maxReplicas: 20                                       │
│    metrics:                                              │
│    - type: Resource                                      │
│      resource:                                           │
│        name: cpu                                         │
│        target:                                           │
│          averageUtilization: 70                           │
│    - type: Pods                                          │
│      pods:                                               │
│        metric:                                           │
│          name: http_requests_per_second                   │
│        target:                                           │
│          averageValue: 1000                              │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### API Gateway Pattern

```java
// Spring Cloud Gateway for routing & rate limiting
@Configuration
public class GatewayConfig {
    
    @Bean
    public RouteLocator routes(RouteLocatorBuilder builder) {
        return builder.routes()
            .route("order-service", r -> r
                .path("/api/orders/**")
                .filters(f -> f
                    .circuitBreaker(c -> c
                        .setName("order-cb")
                        .setFallbackUri("forward:/fallback/orders"))
                    .retry(retryConfig -> retryConfig
                        .setRetries(3)
                        .setStatuses(HttpStatus.SERVICE_UNAVAILABLE))
                    .requestRateLimiter(rl -> rl
                        .setRateLimiter(redisRateLimiter())
                        .setKeyResolver(userKeyResolver())))
                .uri("lb://order-service"))
            .build();
    }
    
    @Bean
    public RedisRateLimiter redisRateLimiter() {
        return new RedisRateLimiter(100, 200); // 100 req/s, burst 200
    }
}
```

---

## Resilience Patterns

### Circuit Breaker (Resilience4j)

```java
@Service
public class PaymentService {
    
    @CircuitBreaker(name = "payment", fallbackMethod = "paymentFallback")
    @Retry(name = "payment", fallbackMethod = "paymentFallback")
    @TimeLimiter(name = "payment")
    public CompletableFuture<PaymentResult> processPayment(PaymentRequest request) {
        return CompletableFuture.supplyAsync(() -> 
            paymentClient.charge(request));
    }
    
    private CompletableFuture<PaymentResult> paymentFallback(PaymentRequest request, Throwable t) {
        log.warn("Payment circuit open, queuing for later: {}", t.getMessage());
        return CompletableFuture.completedFuture(PaymentResult.queued(request.getId()));
    }
}

// Configuration
resilience4j:
  circuitbreaker:
    instances:
      payment:
        sliding-window-size: 10
        minimum-number-of-calls: 5
        failure-rate-threshold: 50  # Open circuit if 50% failures
        wait-duration-in-open-state: 30s
        permitted-number-of-calls-in-half-open-state: 3
        
  retry:
    instances:
      payment:
        max-attempts: 3
        wait-duration: 1s
        exponential-backoff-multiplier: 2
        retry-exceptions:
          - java.io.IOException
          - java.util.concurrent.TimeoutException
          
  timelimiter:
    instances:
      payment:
        timeout-duration: 5s
        cancel-running-future: true
        
  bulkhead:
    instances:
      payment:
        max-concurrent-calls: 25  # Max 25 concurrent calls to payment
        max-wait-duration: 0      # Don't wait, fail immediately
```

### Rate Limiting

```java
@Configuration
public class RateLimitConfig {
    
    @Bean
    public RateLimiter rateLimiter() {
        RateLimiterConfig config = RateLimiterConfig.custom()
            .limitForPeriod(100)           // 100 calls per period
            .limitRefreshPeriod(Duration.ofSeconds(1))  // Per second
            .timeoutDuration(Duration.ofMillis(500))    // Wait max 500ms
            .build();
        return RateLimiter.of("api-limiter", config);
    }
}

// Per-user rate limiting with Bucket4j + Redis
@Component
public class RateLimitFilter extends OncePerRequestFilter {
    
    private final ProxyManager<String> buckets; // Redis-backed
    
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        String userId = extractUserId(request);
        Bucket bucket = buckets.builder()
            .build(userId, () -> BucketConfiguration.builder()
                .addLimit(Bandwidth.classic(100, Refill.intervally(100, Duration.ofMinutes(1))))
                .build());
        
        if (bucket.tryConsume(1)) {
            chain.doFilter(request, response);
        } else {
            response.setStatus(429);
            response.getWriter().write("Rate limit exceeded");
        }
    }
}
```

### Bulkhead Pattern

```java
// Thread Pool Bulkhead - isolates operations into separate thread pools
@Service
public class OrderService {
    
    @Bulkhead(name = "payment", type = Bulkhead.Type.THREADPOOL,
              fallbackMethod = "paymentBulkheadFallback")
    public CompletableFuture<PaymentResult> processPayment(PaymentRequest request) {
        // Runs in isolated thread pool (max 10 threads)
        // If payment service is slow, only 10 threads blocked
        // Other operations (inventory, notifications) unaffected
        return CompletableFuture.supplyAsync(() -> paymentClient.charge(request));
    }
}

// Configuration
resilience4j:
  thread-pool-bulkhead:
    instances:
      payment:
        max-thread-pool-size: 10
        core-thread-pool-size: 5
        queue-capacity: 20
```

---

## Performance Tuning Checklist

### JVM Tuning

```bash
# Production JVM settings
JAVA_OPTS="\
  -server \
  -Xms4g -Xmx4g \
  -XX:+UseG1GC \
  -XX:MaxGCPauseMillis=200 \
  -XX:+UseStringDeduplication \
  -XX:+OptimizeStringConcat \
  -XX:MetaspaceSize=256m \
  -XX:MaxMetaspaceSize=256m \
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/var/log/heapdump.hprof \
  -Djava.security.egd=file:/dev/./urandom \
  -XX:+ExitOnOutOfMemoryError"
```

### Spring Boot Specific Tuning

```yaml
# Performance-optimized application.yml
spring:
  jpa:
    open-in-view: false  # CRITICAL: Disable OSIV for performance
    properties:
      hibernate:
        jdbc:
          batch_size: 50
          batch_versioned_data: true
        order_inserts: true
        order_updates: true
        generate_statistics: false  # Disable in production
        
  jackson:
    serialization:
      FAIL_ON_EMPTY_BEANS: false
    default-property-inclusion: non_null  # Smaller JSON payloads
    
  mvc:
    converters:
      preferred-json-mapper: jackson
      
  main:
    lazy-initialization: false  # true for faster startup (but slower first request)

server:
  compression:
    enabled: true
    mime-types: application/json,text/html,text/plain,text/css,application/javascript
    min-response-size: 1024
```

### Key Optimizations Summary

| Area | Optimization | Impact |
|------|-------------|--------|
| JPA | Disable OSIV | Prevents lazy loading in view, reduces DB connections |
| JPA | Batch operations | 10-100x faster for bulk inserts |
| JPA | Projections | Less data transferred from DB |
| Cache | Redis for shared cache | Reduces DB load by 50-90% |
| HTTP | Response compression | 60-80% smaller responses |
| HTTP | Connection pooling | Reuse connections to downstream services |
| Thread | Right-size thread pools | Prevent thread starvation |
| DB | Read replicas | Distribute read load |
| DB | Query optimization | Biggest single impact usually |
| JVM | G1GC tuning | Predictable pause times |

---

## Scaling Metrics & Monitoring

### Key Metrics to Monitor

```java
@Configuration
public class MetricsConfig {
    
    @Bean
    public MeterRegistryCustomizer<MeterRegistry> metricsCommonTags() {
        return registry -> registry.config()
            .commonTags("app", "order-service", "env", "production");
    }
}

// Custom business metrics
@Service
public class OrderService {
    private final MeterRegistry registry;
    private final Counter orderCounter;
    private final Timer orderProcessingTimer;
    
    public OrderService(MeterRegistry registry) {
        this.registry = registry;
        this.orderCounter = Counter.builder("orders.created")
            .description("Number of orders created")
            .register(registry);
        this.orderProcessingTimer = Timer.builder("orders.processing.time")
            .description("Order processing duration")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(registry);
    }
    
    public Order createOrder(OrderRequest request) {
        return orderProcessingTimer.record(() -> {
            Order order = processOrder(request);
            orderCounter.increment();
            return order;
        });
    }
}
```

### Metrics to Watch for Scaling Decisions

```
┌─────────────────────────────────────────────────────────────┐
│  SCALING DECISION METRICS                                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Scale UP when:                                             │
│  - CPU > 70% sustained for 5 min                           │
│  - Request latency P95 > SLA threshold                     │
│  - Thread pool utilization > 80%                            │
│  - Connection pool exhaustion events > 0                    │
│  - Error rate > 1%                                          │
│  - Queue depth growing (Kafka consumer lag)                 │
│                                                              │
│  Scale DOWN when:                                           │
│  - CPU < 30% sustained for 15 min                          │
│  - Thread pool utilization < 20%                            │
│  - No queue depth growth                                    │
│                                                              │
│  Key Prometheus queries:                                    │
│  - rate(http_server_requests_seconds_count[5m])  # RPS     │
│  - http_server_requests_seconds{quantile="0.95"} # P95     │
│  - hikari_connections_active / hikari_connections_max        │
│  - jvm_threads_states{state="blocked"}                      │
│  - process_cpu_usage                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```
