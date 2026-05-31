# Scalability - Making Spring Boot Applications Scale

## Table of Contents
- [Horizontal vs Vertical Scaling](#horizontal-vs-vertical-scaling)
- [Stateless Architecture](#stateless-architecture)
- [Database Scaling](#database-scaling)
- [Caching Strategies](#caching-strategies)
- [Asynchronous Processing](#asynchronous-processing)
- [Connection Pool Optimization](#connection-pool-optimization)
- [Load Balancing](#load-balancing)
- [Microservices Patterns for Scale](#microservices-patterns-for-scale)
- [Reactive Scaling](#reactive-scaling)
- [Auto-Scaling Strategies](#auto-scaling-strategies)

---

## Horizontal vs Vertical Scaling

### Q1: What is the difference and when to use each?

**Answer:**

```
VERTICAL SCALING (Scale Up):
  ┌─────────────────┐         ┌─────────────────────────┐
  │  Before          │         │  After                   │
  │  2 CPU cores    │  ───→   │  16 CPU cores            │
  │  4GB RAM        │         │  64GB RAM                │
  │  100 IOPS       │         │  10,000 IOPS             │
  └─────────────────┘         └─────────────────────────┘
  
  Pros: Simple, no code changes, no distributed complexity
  Cons: Has limits, expensive, single point of failure
  When: Database servers, early-stage applications

HORIZONTAL SCALING (Scale Out):
  ┌──────────┐                ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ Instance │   ───→         │Instance 1│ │Instance 2│ │Instance 3│
  │  (1x)    │                │          │ │          │ │          │
  └──────────┘                └──────────┘ └──────────┘ └──────────┘
                                     ↑ Load Balancer ↑
  
  Pros: Unlimited scale, fault tolerance, cost effective
  Cons: Requires stateless design, distributed complexity
  When: Application tier, stateless services, read replicas
```

### Q2: How to make a Spring Boot application horizontally scalable?

```java
// KEY PRINCIPLE: Application instances must be STATELESS

// ANTI-PATTERN 1: In-memory session storage
// This breaks when requests go to different instances!
@Controller
public class CartController {
    @GetMapping("/cart")
    public String getCart(HttpSession session) {
        List<Item> cart = (List<Item>) session.getAttribute("cart");
        // Session is LOCAL to this instance - other instances can't see it!
    }
}

// SOLUTION: Externalize session to Redis
// application.yml
// spring:
//   session:
//     store-type: redis
//   redis:
//     host: redis-cluster.example.com

// ANTI-PATTERN 2: Local file storage
@Service
public class FileService {
    public void saveFile(MultipartFile file) {
        file.transferTo(new File("/local/uploads/" + file.getName()));
        // File only on THIS instance! Other instances can't serve it!
    }
}

// SOLUTION: Use S3/GCS/Azure Blob
@Service
public class FileService {
    @Autowired private S3Client s3Client;
    
    public void saveFile(MultipartFile file) {
        s3Client.putObject(PutObjectRequest.builder()
            .bucket("my-uploads")
            .key(file.getOriginalFilename())
            .build(), RequestBody.fromInputStream(file.getInputStream(), file.getSize()));
    }
}

// ANTI-PATTERN 3: In-memory cache
@Service
public class ProductService {
    private final Map<Long, Product> cache = new ConcurrentHashMap<>();
    // Each instance has different cache state!
}

// SOLUTION: Use Redis/Hazelcast distributed cache
@Service
public class ProductService {
    @Cacheable(value = "products", key = "#id")
    public Product getProduct(Long id) {
        return productRepo.findById(id).orElseThrow();
    }
}
// Redis stores cache - all instances share it
```

---

## Stateless Architecture

### Q3: Complete checklist for stateless Spring Boot application

```
STATELESS CHECKLIST:

✅ Session Management:
   □ Use Redis/JDBC session store (Spring Session)
   □ Or use JWT tokens (no server-side session)
   □ No HttpSession.setAttribute() with local state

✅ File Storage:
   □ Use object storage (S3, GCS, Azure Blob)
   □ Never store on local filesystem
   □ Serve files via CDN

✅ Caching:
   □ Use distributed cache (Redis, Hazelcast)
   □ Or accept cache inconsistency across instances
   □ Local cache only for immutable data

✅ Scheduled Jobs:
   □ Use distributed scheduler (ShedLock, Quartz cluster mode)
   □ Prevent same job running on multiple instances

✅ WebSocket:
   □ Use message broker for cross-instance messaging (Redis Pub/Sub)
   □ Sticky sessions for WebSocket OR
   □ Use Redis/RabbitMQ as WebSocket message relay

✅ Database:
   □ Connection pool per instance (not shared)
   □ Database is the shared state
   □ Use database-level locking for coordination
```

```java
// Distributed Scheduling with ShedLock
@Configuration
@EnableScheduling
public class SchedulerConfig {
    @Bean
    public LockProvider lockProvider(DataSource dataSource) {
        return new JdbcTemplateLockProvider(
            JdbcTemplateLockProvider.Configuration.builder()
                .withJdbcTemplate(new JdbcTemplate(dataSource))
                .usingDbTime() // Use DB time for consistency
                .build());
    }
}

@Service
public class DataCleanupService {
    @Scheduled(cron = "0 0 2 * * *") // Every day at 2 AM
    @SchedulerLock(name = "cleanupOldData", lockAtLeastFor = "10m", lockAtMostFor = "30m")
    public void cleanupOldData() {
        // Only ONE instance executes this, even with 10 instances running
        dataRepo.deleteOlderThan(Instant.now().minus(Duration.ofDays(30)));
    }
}
```

---

## Database Scaling

### Q4: How to scale database access in Spring Boot?

```
DATABASE SCALING STRATEGIES:

1. READ REPLICAS (Read Scaling)
   ┌──────────┐     Writes     ┌──────────┐
   │  App     │ ──────────────→│  Primary │
   │ Instance │                 │  (Write) │
   │          │     Reads       └──────────┘
   │          │ ──────────────→     │ Replication
   │          │                     ▼
   └──────────┘              ┌──────────┐
                             │ Replica 1│
                             │  (Read)  │
                             └──────────┘
                             ┌──────────┐
                             │ Replica 2│
                             │  (Read)  │
                             └──────────┘

2. SHARDING (Write Scaling)
   ┌──────────┐     User A-M    ┌──────────┐
   │  App     │ ───────────────→│  Shard 1 │
   │ Instance │                  └──────────┘
   │          │     User N-Z    ┌──────────┐
   │          │ ───────────────→│  Shard 2 │
   └──────────┘                  └──────────┘

3. CQRS (Command Query Responsibility Segregation)
   Commands → Write Model (normalized) → Event → Read Model (denormalized)
   Queries  → Read Model (optimized for reads)
```

```java
// Read/Write Split with Spring Boot
@Configuration
public class DataSourceConfig {
    
    @Bean
    @Primary
    public DataSource routingDataSource(
            @Qualifier("writeDataSource") DataSource writeDs,
            @Qualifier("readDataSource") DataSource readDs) {
        
        Map<Object, Object> targetDataSources = new HashMap<>();
        targetDataSources.put("WRITE", writeDs);
        targetDataSources.put("READ", readDs);
        
        AbstractRoutingDataSource routingDs = new AbstractRoutingDataSource() {
            @Override
            protected Object determineCurrentLookupKey() {
                return TransactionSynchronizationManager.isCurrentTransactionReadOnly() 
                    ? "READ" : "WRITE";
            }
        };
        routingDs.setTargetDataSources(targetDataSources);
        routingDs.setDefaultTargetDataSource(writeDs);
        return routingDs;
    }
    
    @Bean("writeDataSource")
    public DataSource writeDataSource() {
        return DataSourceBuilder.create()
            .url("jdbc:postgresql://primary:5432/mydb")
            .build();
    }
    
    @Bean("readDataSource")
    public DataSource readDataSource() {
        return DataSourceBuilder.create()
            .url("jdbc:postgresql://replica:5432/mydb")
            .build();
    }
}

// Usage: @Transactional(readOnly = true) routes to replica
@Service
public class UserService {
    
    @Transactional(readOnly = true) // → Routes to READ replica
    public List<User> findAll() {
        return userRepo.findAll();
    }
    
    @Transactional // → Routes to WRITE primary
    public User save(User user) {
        return userRepo.save(user);
    }
}
```

### Q5: How to implement database sharding?

```java
// Sharding strategy: Hash-based routing
@Configuration
public class ShardingConfig {
    
    @Bean
    public DataSource shardedDataSource() {
        Map<Object, Object> shardMap = new HashMap<>();
        shardMap.put("SHARD_0", createDataSource("shard0-host", "mydb"));
        shardMap.put("SHARD_1", createDataSource("shard1-host", "mydb"));
        shardMap.put("SHARD_2", createDataSource("shard2-host", "mydb"));
        shardMap.put("SHARD_3", createDataSource("shard3-host", "mydb"));
        
        AbstractRoutingDataSource routing = new AbstractRoutingDataSource() {
            @Override
            protected Object determineCurrentLookupKey() {
                Long userId = ShardContext.getCurrentUserId();
                if (userId == null) return "SHARD_0";
                int shard = (int) (userId % 4); // Hash-based sharding
                return "SHARD_" + shard;
            }
        };
        routing.setTargetDataSources(shardMap);
        return routing;
    }
}

// Shard context (ThreadLocal)
public class ShardContext {
    private static final ThreadLocal<Long> currentUserId = new ThreadLocal<>();
    
    public static void setUserId(Long userId) {
        currentUserId.set(userId);
    }
    
    public static Long getCurrentUserId() {
        return currentUserId.get();
    }
    
    public static void clear() {
        currentUserId.remove();
    }
}

// AOP to set shard context
@Aspect
@Component
public class ShardingAspect {
    @Around("@annotation(sharded)")
    public Object routeToShard(ProceedingJoinPoint pjp, Sharded sharded) throws Throwable {
        // Extract userId from method arguments
        Long userId = extractUserId(pjp);
        ShardContext.setUserId(userId);
        try {
            return pjp.proceed();
        } finally {
            ShardContext.clear();
        }
    }
}
```

---

## Caching Strategies

### Q6: Multi-level caching for maximum performance

```java
// L1 Cache: In-process (Caffeine) - microsecond access
// L2 Cache: Distributed (Redis) - millisecond access
// L3 Cache: Database - tens of milliseconds

@Configuration
@EnableCaching
public class CacheConfig {
    
    @Bean
    public CacheManager cacheManager(RedisConnectionFactory redisConnectionFactory) {
        // L1: Caffeine (local)
        CaffeineCacheManager caffeineManager = new CaffeineCacheManager();
        caffeineManager.setCaffeine(Caffeine.newBuilder()
            .maximumSize(10_000)
            .expireAfterWrite(Duration.ofMinutes(5))
            .recordStats());
        
        // L2: Redis (distributed)
        RedisCacheManager redisManager = RedisCacheManager.builder(redisConnectionFactory)
            .cacheDefaults(RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofMinutes(30))
                .serializeValuesWith(SerializationPair.fromSerializer(
                    new GenericJackson2JsonRedisSerializer())))
            .build();
        
        // Composite: Try L1 first, then L2
        return new CompositeCacheManager(caffeineManager, redisManager);
    }
}

// Cache-aside pattern implementation
@Service
public class ProductService {
    @Autowired private CaffeineCacheManager l1Cache;
    @Autowired private RedisTemplate<String, Product> redisTemplate;
    @Autowired private ProductRepository productRepo;
    
    public Product getProduct(Long id) {
        String key = "product:" + id;
        
        // L1: Check local cache
        Product product = l1Cache.getCache("products").get(id, Product.class);
        if (product != null) return product;
        
        // L2: Check Redis
        product = redisTemplate.opsForValue().get(key);
        if (product != null) {
            l1Cache.getCache("products").put(id, product); // Populate L1
            return product;
        }
        
        // L3: Database
        product = productRepo.findById(id).orElseThrow();
        redisTemplate.opsForValue().set(key, product, Duration.ofMinutes(30)); // Populate L2
        l1Cache.getCache("products").put(id, product); // Populate L1
        return product;
    }
    
    // Cache invalidation (write-through)
    @CacheEvict(value = "products", key = "#product.id")
    public Product updateProduct(Product product) {
        Product saved = productRepo.save(product);
        redisTemplate.delete("product:" + saved.getId());
        // Broadcast invalidation to other instances
        redisTemplate.convertAndSend("cache-invalidation", "product:" + saved.getId());
        return saved;
    }
}
```

### Q7: Cache invalidation strategies

```
1. TIME-BASED (TTL):
   Simple, eventual consistency
   Good for: rarely changing data, acceptable staleness
   
2. WRITE-THROUGH:
   Update cache on every write
   Strong consistency, write overhead
   Good for: frequently read, occasionally written data
   
3. WRITE-BEHIND (WRITE-BACK):
   Update cache immediately, persist asynchronously
   Risk of data loss on crash
   Good for: high write throughput requirements
   
4. CACHE-ASIDE (LAZY LOADING):
   Load into cache on first read, invalidate on write
   Most common pattern
   Good for: read-heavy workloads
   
5. EVENT-DRIVEN INVALIDATION:
   Publish events on data change, listeners invalidate cache
   Good for: distributed systems, eventual consistency acceptable
```

```java
// Event-driven cache invalidation across instances
@Service
public class CacheInvalidationListener {
    @Autowired private CacheManager cacheManager;
    
    // Listen to Redis Pub/Sub for invalidation messages
    @EventListener
    public void onCacheInvalidation(CacheInvalidationEvent event) {
        Cache cache = cacheManager.getCache(event.getCacheName());
        if (cache != null) {
            cache.evict(event.getKey());
        }
    }
}

// Using Spring Cloud Stream for cache invalidation
@Component
public class CacheInvalidationProcessor {
    @Autowired private CacheManager cacheManager;
    
    @StreamListener("cache-invalidation-input")
    public void invalidate(CacheInvalidationMessage message) {
        cacheManager.getCache(message.getCacheName()).evict(message.getKey());
    }
}
```

---

## Asynchronous Processing

### Q8: How to scale with async processing?

```java
// Pattern 1: Async with CompletableFuture
@Service
public class OrderService {
    @Autowired private PaymentService paymentService;
    @Autowired private InventoryService inventoryService;
    @Autowired private NotificationService notificationService;
    
    public Order placeOrder(OrderRequest request) {
        Order order = createOrder(request);
        
        // Non-critical operations run async
        CompletableFuture.runAsync(() -> notificationService.sendConfirmation(order));
        CompletableFuture.runAsync(() -> analyticsService.trackOrder(order));
        
        return order; // Return immediately
    }
}

// Pattern 2: Message Queue for decoupling (RabbitMQ/Kafka)
@Service
public class OrderService {
    @Autowired private RabbitTemplate rabbitTemplate;
    
    @Transactional
    public Order placeOrder(OrderRequest request) {
        Order order = orderRepo.save(createOrder(request));
        
        // Publish event - consumers process asynchronously
        rabbitTemplate.convertAndSend("order-exchange", "order.created", 
            new OrderCreatedEvent(order.getId(), order.getUserId()));
        
        return order; // Return immediately, processing happens async
    }
}

// Consumer (can be on different instances, auto-scaled independently)
@Component
public class OrderEventConsumer {
    
    @RabbitListener(queues = "order-notifications")
    public void handleOrderCreated(OrderCreatedEvent event) {
        emailService.sendOrderConfirmation(event.getUserId(), event.getOrderId());
    }
    
    @RabbitListener(queues = "order-inventory")
    public void handleInventoryReservation(OrderCreatedEvent event) {
        inventoryService.reserve(event.getOrderId());
    }
}

// Pattern 3: Outbox pattern (reliable messaging)
@Service
public class OrderService {
    
    @Transactional // Same transaction guarantees event is saved with order
    public Order placeOrder(OrderRequest request) {
        Order order = orderRepo.save(createOrder(request));
        
        // Save event to outbox table (same transaction as order)
        outboxRepo.save(new OutboxEvent(
            "OrderCreated",
            objectMapper.writeValueAsString(new OrderCreatedEvent(order.getId())),
            Instant.now()
        ));
        
        return order;
    }
}

// Separate process reads outbox and publishes to message broker
@Scheduled(fixedDelay = 1000)
@SchedulerLock(name = "outboxPublisher")
public void publishOutboxEvents() {
    List<OutboxEvent> events = outboxRepo.findUnpublished(100);
    for (OutboxEvent event : events) {
        rabbitTemplate.convertAndSend("events", event.getType(), event.getPayload());
        event.setPublished(true);
        outboxRepo.save(event);
    }
}
```

---

## Connection Pool Optimization

### Q9: How to optimize HikariCP for scale?

```yaml
# application.yml
spring:
  datasource:
    hikari:
      # CRITICAL SETTINGS
      maximum-pool-size: 20        # Max connections (see formula below)
      minimum-idle: 5              # Min idle connections
      idle-timeout: 300000         # 5 min - close idle connections
      max-lifetime: 1800000        # 30 min - prevent stale connections
      connection-timeout: 30000    # 30 sec - wait for connection from pool
      
      # ADVANCED SETTINGS
      leak-detection-threshold: 60000  # Log if connection held > 60s
      validation-timeout: 5000         # Validate connection in 5s
      connection-test-query: SELECT 1  # Validate query (for drivers without isValid)
```

**Connection Pool Sizing Formula:**

```
Optimal pool size = (core_count * 2) + effective_spindle_count

For SSD: spindle_count ≈ 0 (no mechanical disk head)
For 4-core machine with SSD: (4 * 2) + 0 = 8 connections

But also consider:
- Number of application instances
- Total connections database can handle
- PostgreSQL default max_connections = 100

Formula with instances:
  pool_per_instance = max_db_connections / number_of_instances
  
  E.g., 100 max DB connections, 5 instances:
  pool_per_instance = 100 / 5 = 20
```

```java
// Monitor connection pool
@Component
public class ConnectionPoolMonitor {
    @Autowired private DataSource dataSource;
    
    @Scheduled(fixedRate = 60000)
    public void logPoolStats() {
        if (dataSource instanceof HikariDataSource hikari) {
            HikariPoolMXBean pool = hikari.getHikariPoolMXBean();
            log.info("Pool stats - Active: {}, Idle: {}, Waiting: {}, Total: {}",
                pool.getActiveConnections(),
                pool.getIdleConnections(),
                pool.getThreadsAwaitingConnection(),
                pool.getTotalConnections());
            
            // Alert if waiting threads
            if (pool.getThreadsAwaitingConnection() > 0) {
                alertService.warn("Connection pool exhaustion risk!");
            }
        }
    }
}
```

---

## Load Balancing

### Q10: Load balancing strategies for Spring Boot

```
┌─────────────────────────────────────────────────────────┐
│                  LOAD BALANCING LAYERS                    │
│                                                          │
│  L4 (TCP): AWS NLB, HAProxy (TCP mode)                  │
│    → Routes based on IP/port, very fast                  │
│    → No request inspection                               │
│                                                          │
│  L7 (HTTP): AWS ALB, Nginx, HAProxy (HTTP mode)         │
│    → Routes based on URL, headers, cookies               │
│    → Can do path-based routing, SSL termination          │
│    → Health checks at HTTP level                         │
│                                                          │
│  Service Mesh: Istio, Linkerd                            │
│    → Client-side routing                                 │
│    → mTLS, circuit breaking, retries                     │
└─────────────────────────────────────────────────────────┘
```

**Load Balancing Algorithms:**

```
1. ROUND ROBIN: A → B → C → A → B → C
   Simple, equal distribution
   Problem: Doesn't account for server capacity or response time

2. LEAST CONNECTIONS: Route to server with fewest active connections
   Better for varying request durations
   Problem: Doesn't account for server capacity

3. WEIGHTED ROUND ROBIN: A(3) → B(2) → C(1) → A(3) → ...
   Accounts for different server sizes
   Good for heterogeneous fleet

4. IP HASH: hash(client_ip) % num_servers
   Ensures same client goes to same server
   Good for: session affinity (before Redis sessions)

5. LEAST RESPONSE TIME: Route to fastest server
   Best for varying server performance
   Requires active monitoring

6. RANDOM: Pick random server
   Simple, works well at scale (law of large numbers)
```

```java
// Client-side load balancing with Spring Cloud LoadBalancer
@Configuration
public class LoadBalancerConfig {
    
    @Bean
    @LoadBalanced
    public WebClient.Builder webClientBuilder() {
        return WebClient.builder();
    }
}

@Service
public class OrderService {
    @Autowired private WebClient.Builder webClientBuilder;
    
    public Mono<Payment> processPayment(PaymentRequest request) {
        return webClientBuilder.build()
            .post()
            .uri("http://payment-service/api/payments") // Service name, not hostname!
            // LoadBalancer resolves to actual instance
            .bodyValue(request)
            .retrieve()
            .bodyToMono(Payment.class);
    }
}
```

---

## Microservices Patterns for Scale

### Q11: Key patterns for scalable microservices

```java
// 1. CIRCUIT BREAKER (Resilience4j)
@Service
public class PaymentService {
    
    @CircuitBreaker(name = "payment", fallbackMethod = "paymentFallback")
    @Retry(name = "payment", fallbackMethod = "paymentFallback")
    @TimeLimiter(name = "payment")
    public CompletableFuture<Payment> processPayment(PaymentRequest request) {
        return CompletableFuture.supplyAsync(() -> 
            paymentClient.charge(request));
    }
    
    public CompletableFuture<Payment> paymentFallback(PaymentRequest request, Throwable t) {
        // Queue for later processing
        return CompletableFuture.completedFuture(Payment.pending(request));
    }
}

// Circuit breaker configuration
// application.yml:
// resilience4j:
//   circuitbreaker:
//     instances:
//       payment:
//         sliding-window-size: 10
//         failure-rate-threshold: 50
//         wait-duration-in-open-state: 30s
//         permitted-number-of-calls-in-half-open-state: 5

// 2. BULKHEAD (Thread Isolation)
@Service
public class OrderService {
    
    @Bulkhead(name = "orderProcessing", type = Bulkhead.Type.THREADPOOL)
    public CompletableFuture<Order> processOrder(OrderRequest request) {
        // Limited concurrent executions - prevents cascade failures
        return CompletableFuture.supplyAsync(() -> doProcess(request));
    }
}

// resilience4j:
//   bulkhead:
//     instances:
//       orderProcessing:
//         max-concurrent-calls: 20
//         max-wait-duration: 500ms

// 3. RATE LIMITING
@RestController
public class ApiController {
    
    @RateLimiter(name = "api", fallbackMethod = "rateLimitFallback")
    @GetMapping("/api/resource")
    public ResponseEntity<Data> getResource() {
        return ResponseEntity.ok(service.getData());
    }
    
    public ResponseEntity<Data> rateLimitFallback(Throwable t) {
        return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS).build();
    }
}

// 4. API GATEWAY PATTERN
// Spring Cloud Gateway configuration
// spring:
//   cloud:
//     gateway:
//       routes:
//         - id: user-service
//           uri: lb://user-service
//           predicates:
//             - Path=/api/users/**
//           filters:
//             - CircuitBreaker=name=userCircuitBreaker
//             - RequestRateLimiter=redis-rate-limiter
//             - Retry=retries=3,statuses=BAD_GATEWAY
```

### Q12: Event-driven architecture for scale

```java
// Apache Kafka for event-driven scaling
@Configuration
public class KafkaConfig {
    @Bean
    public NewTopic orderTopic() {
        return TopicBuilder.name("orders")
            .partitions(12)  // 12 partitions = up to 12 parallel consumers
            .replicas(3)     // 3 replicas for fault tolerance
            .build();
    }
}

@Service
public class OrderProducer {
    @Autowired private KafkaTemplate<String, OrderEvent> kafkaTemplate;
    
    public void publishOrder(Order order) {
        // Key = userId → same user's orders go to same partition (ordering)
        kafkaTemplate.send("orders", order.getUserId().toString(), 
            new OrderEvent(order));
    }
}

@Component
public class OrderConsumer {
    
    @KafkaListener(
        topics = "orders",
        groupId = "order-processing",
        concurrency = "4"  // 4 consumer threads (up to 12 for 12 partitions)
    )
    public void processOrder(OrderEvent event, Acknowledgment ack) {
        try {
            orderService.process(event);
            ack.acknowledge(); // Manual ack after successful processing
        } catch (TransientException e) {
            // Don't ack - will be redelivered
            throw e;
        }
    }
}

// Scaling consumers:
// 12 partitions → up to 12 consumer instances in same group
// Add more instances → Kafka rebalances partitions automatically
// Each partition processed by exactly ONE consumer in the group
```

---

## Reactive Scaling

### Q13: How does WebFlux enable better scaling?

```java
// WebFlux can handle 100K+ concurrent connections with minimal resources

@Configuration
public class NettyConfig {
    @Bean
    public ReactorResourceFactory reactorResourceFactory() {
        ReactorResourceFactory factory = new ReactorResourceFactory();
        factory.setUseGlobalResources(false);
        factory.setLoopResources(LoopResources.create("http", 
            1,  // select count (acceptor threads)
            Runtime.getRuntime().availableProcessors(),  // worker count
            true)); // daemon threads
        factory.setConnectionProvider(ConnectionProvider.builder("custom")
            .maxConnections(10000)
            .pendingAcquireMaxCount(50000)
            .build());
        return factory;
    }
}

// Scaling patterns with WebFlux
@RestController
public class StreamController {
    
    // Can handle thousands of simultaneous SSE connections
    @GetMapping(value = "/stream/prices", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<Price> streamPrices() {
        return priceService.getPriceStream()
            .onBackpressureLatest(); // Drop old prices if client is slow
    }
    
    // Fan-out: Call multiple services concurrently
    @GetMapping("/dashboard/{userId}")
    public Mono<Dashboard> getDashboard(@PathVariable String userId) {
        return Mono.zip(
            userService.getProfile(userId),        // Concurrent
            orderService.getRecentOrders(userId),   // Concurrent
            recommendationService.getRecommendations(userId), // Concurrent
            analyticsService.getUserStats(userId)   // Concurrent
        ).map(tuple -> Dashboard.from(tuple.getT1(), tuple.getT2(), tuple.getT3(), tuple.getT4()));
        // All 4 calls execute simultaneously, combine when ALL complete
    }
}
```

---

## Auto-Scaling Strategies

### Q14: How to configure auto-scaling for Spring Boot on Kubernetes?

```yaml
# Kubernetes HPA (Horizontal Pod Autoscaler)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3
  maxReplicas: 50
  metrics:
    # Scale based on CPU
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    # Scale based on memory
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    # Scale based on custom metric (requests per second)
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
    # Scale based on queue depth
    - type: External
      external:
        metric:
          name: rabbitmq_queue_messages
          selector:
            matchLabels:
              queue: order-processing
        target:
          type: Value
          value: "100"  # Scale up if queue > 100 messages
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5 min before scaling down
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60
```

```java
// Spring Boot Actuator metrics for custom auto-scaling
@Component
public class CustomMetrics {
    private final MeterRegistry registry;
    private final AtomicInteger activeConnections = new AtomicInteger(0);
    
    public CustomMetrics(MeterRegistry registry) {
        this.registry = registry;
        // Expose metric for HPA
        Gauge.builder("app.connections.active", activeConnections, AtomicInteger::get)
            .register(registry);
    }
}

// Graceful shutdown for scaling down
@Configuration
public class GracefulShutdownConfig {
    // application.yml:
    // server:
    //   shutdown: graceful
    // spring:
    //   lifecycle:
    //     timeout-per-shutdown-phase: 30s
    
    @Bean
    public GracefulShutdown gracefulShutdown() {
        return new GracefulShutdown();
    }
}
```

### Q15: Pre-warming and readiness probes

```java
// Readiness probe - don't receive traffic until ready
@Component
public class WarmupHealthIndicator implements HealthIndicator {
    private volatile boolean warmedUp = false;
    
    @EventListener(ApplicationReadyEvent.class)
    public void onReady() {
        // Pre-warm caches, establish connections
        cacheService.warmUp();
        dbConnectionPool.validate();
        warmedUp = true;
    }
    
    @Override
    public Health health() {
        if (warmedUp) {
            return Health.up().build();
        }
        return Health.down().withDetail("reason", "Warming up").build();
    }
}
```

```yaml
# Kubernetes probes
spec:
  containers:
    - name: order-service
      readinessProbe:
        httpGet:
          path: /actuator/health/readiness
          port: 8080
        initialDelaySeconds: 30
        periodSeconds: 10
        failureThreshold: 3
      livenessProbe:
        httpGet:
          path: /actuator/health/liveness
          port: 8080
        initialDelaySeconds: 60
        periodSeconds: 30
        failureThreshold: 5
      startupProbe:
        httpGet:
          path: /actuator/health
          port: 8080
        initialDelaySeconds: 10
        periodSeconds: 5
        failureThreshold: 30  # Up to 150s to start
```

---

## Summary: Scaling Checklist

```
APPLICATION LAYER:
  □ Stateless instances (externalize state)
  □ Async processing for non-critical paths
  □ Circuit breakers for external calls
  □ Rate limiting to protect resources
  □ Connection pool tuning
  □ Proper thread pool sizing

DATA LAYER:
  □ Read replicas for read scaling
  □ Caching (multi-level: L1 local, L2 Redis)
  □ Database connection pooling
  □ Consider sharding for write scaling
  □ Use CDN for static content

INFRASTRUCTURE:
  □ Load balancer (L7 for HTTP)
  □ Auto-scaling (CPU, memory, custom metrics)
  □ Graceful shutdown
  □ Health checks (readiness + liveness)
  □ Container orchestration (Kubernetes)

ARCHITECTURE:
  □ Event-driven for decoupling
  □ CQRS for different read/write patterns
  □ API Gateway for cross-cutting concerns
  □ Message queues for async work distribution
  □ Service mesh for observability
```
