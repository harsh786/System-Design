# Top Production Issues - Real-World Problems & Solutions

## Table of Contents
- [Connection Pool Exhaustion](#connection-pool-exhaustion)
- [Memory Leaks in Production](#memory-leaks-in-production)
- [Thread Pool Starvation](#thread-pool-starvation)
- [Database Connection Issues](#database-connection-issues)
- [Cascading Failures](#cascading-failures)
- [Slow Queries and N+1 Problems](#slow-queries-and-n1-problems)
- [Timeout Storms](#timeout-storms)
- [GC Pauses](#gc-pauses)
- [ClassLoader Leaks](#classloader-leaks)
- [DNS Resolution Issues](#dns-resolution-issues)
- [SSL/TLS Issues](#ssltls-issues)
- [Log Flooding](#log-flooding)
- [Graceful Shutdown Failures](#graceful-shutdown-failures)
- [Configuration Drift](#configuration-drift)
- [Health Check Failures](#health-check-failures)

---

## Connection Pool Exhaustion

### Symptoms
```
- HikariPool-1 - Connection is not available, request timed out after 30000ms
- Application hangs, all requests timeout
- Threads in TIMED_WAITING state waiting for connections
- Sudden spike in response time
```

### Root Causes
```java
// CAUSE 1: Connection leak - transaction not closed
@Service
public class BrokenService {
    @Autowired private DataSource dataSource;
    
    public void processData() {
        Connection conn = dataSource.getConnection(); // LEAKS!
        try {
            // If exception here, connection never returned to pool
            Statement stmt = conn.createStatement();
            stmt.execute("UPDATE ...");
            // Forgot conn.close()!
        } catch (Exception e) {
            log.error("Error", e);
            // Connection leaked on exception path!
        }
    }
}

// CAUSE 2: Long-running transactions holding connections
@Transactional // Holds connection for ENTIRE method duration
public void processLargeOrder(Long orderId) {
    Order order = orderRepo.findById(orderId); // Gets connection
    
    // External HTTP call while holding DB connection!
    PaymentResult result = paymentClient.charge(order); // 2-5 seconds!
    
    // Connection held for 2-5 seconds doing NOTHING
    order.setStatus("PAID");
    orderRepo.save(order);
}

// CAUSE 3: Blocking operations inside @Transactional
@Transactional
public void sendNotification(Long userId) {
    User user = userRepo.findById(userId);
    emailService.send(user.getEmail()); // BLOCKS for 1-3 seconds
    user.setNotified(true);
    userRepo.save(user);
    // Connection held during entire email send!
}
```

### Solutions
```java
// SOLUTION 1: Enable leak detection
spring:
  datasource:
    hikari:
      leak-detection-threshold: 60000  # Log warning if connection held > 60s

// SOLUTION 2: Separate transaction from I/O
@Service
public class OrderService {
    
    public void processLargeOrder(Long orderId) {
        // Step 1: Quick transaction - get data
        Order order = getOrder(orderId);
        
        // Step 2: External call WITHOUT holding DB connection
        PaymentResult result = paymentClient.charge(order);
        
        // Step 3: Quick transaction - update
        updateOrderStatus(orderId, "PAID");
    }
    
    @Transactional(readOnly = true)
    public Order getOrder(Long orderId) {
        return orderRepo.findById(orderId).orElseThrow();
    }
    
    @Transactional
    public void updateOrderStatus(Long orderId, String status) {
        orderRepo.updateStatus(orderId, status);
    }
}

// SOLUTION 3: Connection pool monitoring
@Component
public class PoolHealthCheck implements HealthIndicator {
    @Autowired private HikariDataSource dataSource;
    
    @Override
    public Health health() {
        HikariPoolMXBean pool = dataSource.getHikariPoolMXBean();
        int waiting = pool.getThreadsAwaitingConnection();
        int active = pool.getActiveConnections();
        int total = pool.getTotalConnections();
        
        if (waiting > 5) {
            return Health.down()
                .withDetail("waitingThreads", waiting)
                .withDetail("activeConnections", active)
                .withDetail("totalConnections", total)
                .build();
        }
        return Health.up()
            .withDetail("active", active)
            .withDetail("idle", pool.getIdleConnections())
            .build();
    }
}
```

---

## Thread Pool Starvation

### Symptoms
```
- Requests queuing up, response times growing linearly
- Thread dump shows all threads BLOCKED or WAITING
- Tomcat access log shows requests taking 30+ seconds
- New connections refused (accept queue full)
```

### Root Causes & Solutions
```java
// CAUSE 1: Synchronous call to slow downstream service
@RestController
public class ApiController {
    @GetMapping("/data")
    public Data getData() {
        // If external-service takes 10s and we have 200 threads:
        // Max throughput = 200/10 = 20 requests/second!
        return restTemplate.getForObject("http://slow-service/api", Data.class);
    }
}

// SOLUTION: Set aggressive timeouts
@Bean
public RestTemplate restTemplate() {
    HttpComponentsClientHttpRequestFactory factory = new HttpComponentsClientHttpRequestFactory();
    factory.setConnectTimeout(2000);   // 2s connect timeout
    factory.setReadTimeout(5000);      // 5s read timeout
    return new RestTemplate(factory);
}

// CAUSE 2: @Async methods using same thread pool as HTTP
@Configuration
@EnableAsync
public class BadAsyncConfig {
    // Uses SimpleAsyncTaskExecutor by default - UNBOUNDED THREADS!
    // Or if configured with same pool as Tomcat → starvation
}

// SOLUTION: Separate, bounded thread pool for async
@Bean("asyncExecutor")
public Executor asyncExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(10);
    executor.setMaxPoolSize(50);
    executor.setQueueCapacity(500);
    executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
    executor.setThreadNamePrefix("async-");
    executor.setWaitForTasksToCompleteOnShutdown(true);
    executor.setAwaitTerminationSeconds(30);
    executor.initialize();
    return executor;
}

// CAUSE 3: Deadlock in application code (see Concurrency chapter)

// SOLUTION: Monitor thread pool saturation
@Component
public class ThreadPoolMetrics {
    @Autowired private MeterRegistry registry;
    
    @PostConstruct
    public void registerMetrics() {
        // Expose Tomcat thread pool metrics
        new TomcatMetrics(null, List.of()).bindTo(registry);
    }
}
// Alert when: tomcat_threads_busy / tomcat_threads_max > 0.8
```

---

## Cascading Failures

### Pattern
```
Service A → Service B → Service C (fails)
                              ↓
Service B threads exhausted waiting for C
                              ↓
Service A threads exhausted waiting for B
                              ↓
ENTIRE SYSTEM DOWN (cascade)

Timeline:
  T+0s:  Service C goes down
  T+5s:  Service B threads blocked waiting for C (timeout 30s default!)
  T+30s: Service B thread pool exhausted, starts rejecting
  T+35s: Service A threads blocked waiting for B
  T+60s: Service A thread pool exhausted
  T+60s: All user requests failing
```

### Solutions
```java
// SOLUTION 1: Circuit Breaker (Resilience4j)
@Service
public class OrderService {
    
    @CircuitBreaker(name = "inventory", fallbackMethod = "inventoryFallback")
    @TimeLimiter(name = "inventory")
    @Retry(name = "inventory")
    public CompletableFuture<Stock> checkInventory(String productId) {
        return CompletableFuture.supplyAsync(() -> 
            inventoryClient.getStock(productId));
    }
    
    private CompletableFuture<Stock> inventoryFallback(String productId, Throwable t) {
        log.warn("Inventory service unavailable, using cached data", t);
        return CompletableFuture.completedFuture(cachedInventory.get(productId));
    }
}

// Configuration
resilience4j:
  circuitbreaker:
    instances:
      inventory:
        sliding-window-size: 10
        minimum-number-of-calls: 5
        failure-rate-threshold: 50         # Open at 50% failure
        wait-duration-in-open-state: 30s   # Stay open 30s
        permitted-number-of-calls-in-half-open-state: 3
        slow-call-rate-threshold: 80       # 80% slow calls → open
        slow-call-duration-threshold: 2s   # What's "slow"
  timelimiter:
    instances:
      inventory:
        timeout-duration: 3s               # Hard timeout
  retry:
    instances:
      inventory:
        max-attempts: 3
        wait-duration: 500ms
        retry-exceptions:
          - java.io.IOException
          - java.net.SocketTimeoutException
        ignore-exceptions:
          - com.example.BusinessException

// SOLUTION 2: Bulkhead (Thread isolation)
@Bulkhead(name = "inventory", type = Bulkhead.Type.THREADPOOL,
          fallbackMethod = "inventoryFallback")
public CompletableFuture<Stock> checkInventory(String productId) {
    // Limited to 10 concurrent calls - can't exhaust main thread pool
    return CompletableFuture.supplyAsync(() -> inventoryClient.getStock(productId));
}

resilience4j:
  bulkhead:
    instances:
      inventory:
        max-concurrent-calls: 10
        max-wait-duration: 500ms

// SOLUTION 3: Timeout at every boundary
// HTTP client timeout
WebClient webClient = WebClient.builder()
    .clientConnector(new ReactorClientHttpConnector(
        HttpClient.create()
            .responseTimeout(Duration.ofSeconds(3))
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 2000)))
    .build();

// Database timeout
spring:
  datasource:
    hikari:
      connection-timeout: 5000    # Wait for connection
      validation-timeout: 3000    # Validate connection
  jpa:
    properties:
      javax.persistence.query.timeout: 5000  # Query timeout
```

---

## Slow Queries and N+1 Problems

### Detection
```java
// Enable slow query logging
spring:
  jpa:
    properties:
      hibernate:
        session.events.log.LOG_QUERIES_SLOWER_THAN_MS: 100  # Log queries > 100ms
        generate_statistics: true   # Log query stats

logging:
  level:
    org.hibernate.SQL: DEBUG                    # Log all SQL
    org.hibernate.type.descriptor.sql: TRACE   # Log bind parameters
    org.hibernate.stat: DEBUG                  # Log statistics

// P6Spy for detailed SQL logging with timing
// Add dependency: p6spy:p6spy
spring:
  datasource:
    url: jdbc:p6spy:postgresql://localhost:5432/mydb
    driver-class-name: com.p6spy.engine.spy.P6SpyDriver
```

### N+1 Problem Deep Dive
```java
// THE PROBLEM
@Entity
public class Order {
    @Id private Long id;
    
    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<OrderItem> items; // LAZY loaded
}

@Service
public class OrderService {
    public List<OrderDTO> getAllOrders() {
        List<Order> orders = orderRepo.findAll(); // 1 query: SELECT * FROM orders
        
        return orders.stream()
            .map(order -> {
                // For EACH order, triggers: SELECT * FROM order_items WHERE order_id = ?
                // N additional queries!
                List<OrderItem> items = order.getItems();
                return new OrderDTO(order, items);
            })
            .collect(Collectors.toList());
    }
}
// Total: 1 + N queries (if 1000 orders → 1001 queries!)

// SOLUTION 1: JOIN FETCH
@Query("SELECT o FROM Order o JOIN FETCH o.items")
List<Order> findAllWithItems(); // 1 query with JOIN

// SOLUTION 2: @EntityGraph
@EntityGraph(attributePaths = {"items"})
List<Order> findAll(); // 1 query with LEFT JOIN

// SOLUTION 3: @BatchSize (for when you can't JOIN FETCH all)
@Entity
public class Order {
    @OneToMany(mappedBy = "order")
    @BatchSize(size = 50) // Load items in batches of 50
    private List<OrderItem> items;
}
// Instead of N queries → ceil(N/50) queries

// SOLUTION 4: Projection (don't load entities at all)
public interface OrderSummary {
    Long getId();
    String getStatus();
    Integer getItemCount();
}

@Query("SELECT o.id as id, o.status as status, SIZE(o.items) as itemCount FROM Order o")
List<OrderSummary> findOrderSummaries(); // 1 lightweight query

// SOLUTION 5: Hibernate default_batch_fetch_size
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 50  # Global batch loading
```

---

## Timeout Storms

### Problem
```
Normal: Service responds in 100ms, timeout set at 5s
Incident: Service becomes slow (responds in 4.9s)

Without proper handling:
  - Each request holds a thread for 4.9s (instead of 100ms)
  - Thread pool capacity drops 49x (200/4.9 ≈ 40 concurrent only)
  - Requests queue up exponentially
  - Load balancer sees "healthy" (200 OK after 4.9s) → keeps sending traffic
  - Downstream gets MORE load → gets SLOWER → positive feedback loop

Result: 5s timeout × 200 threads = 40 req/sec max
Normal: 100ms × 200 threads = 2000 req/sec
```

### Solutions
```java
// SOLUTION 1: Aggressive timeouts with circuit breaker
// Set timeout MUCH lower than SLA
// SLA = 500ms → Timeout = 2s → Circuit breaker at 80% slow calls

// SOLUTION 2: Deadline propagation
@Component
public class DeadlineFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
            HttpServletResponse response, FilterChain chain) {
        
        String deadline = request.getHeader("X-Request-Deadline");
        if (deadline != null) {
            Instant deadlineTime = Instant.parse(deadline);
            if (Instant.now().isAfter(deadlineTime)) {
                response.setStatus(504); // Already past deadline, don't bother
                return;
            }
            // Set remaining time as timeout for downstream calls
            Duration remaining = Duration.between(Instant.now(), deadlineTime);
            RequestContext.setDeadline(remaining);
        }
        chain.doFilter(request, response);
    }
}

// SOLUTION 3: Load shedding
@Component
public class LoadSheddingFilter extends OncePerRequestFilter {
    private final AtomicInteger activeRequests = new AtomicInteger(0);
    private static final int MAX_CONCURRENT = 150; // Below thread pool max
    
    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain) throws Exception {
        
        int current = activeRequests.incrementAndGet();
        try {
            if (current > MAX_CONCURRENT) {
                response.setStatus(503); // Service Unavailable
                response.getWriter().write("Server overloaded, please retry");
                return;
            }
            chain.doFilter(request, response);
        } finally {
            activeRequests.decrementAndGet();
        }
    }
}

// SOLUTION 4: Adaptive timeout
@Component
public class AdaptiveTimeoutService {
    private final MovingAverage p99Latency = new MovingAverage(100);
    
    public Duration getTimeout(String service) {
        double current = p99Latency.get(service);
        // Timeout = 3x p99 latency (adapts to actual performance)
        return Duration.ofMillis((long) (current * 3));
    }
    
    public void recordLatency(String service, long millis) {
        p99Latency.add(service, millis);
    }
}
```

---

## DNS Resolution Issues

### Problem
```
Java caches DNS lookups BY DEFAULT:
  - Successful lookups: cached FOREVER (networkaddress.cache.ttl = -1 in security policy)
  - Failed lookups: cached for 10 seconds

Problem in cloud environments:
  - Load balancer IP changes (AWS ELB, etc.)
  - Service discovery returns new IPs
  - Blue-green deployments change IPs
  - Java keeps using OLD cached IP → connection failures!
```

### Solutions
```java
// SOLUTION 1: Set DNS TTL
// In code (early in application startup):
java.security.Security.setProperty("networkaddress.cache.ttl", "30");
java.security.Security.setProperty("networkaddress.cache.negative.ttl", "5");

// Or JVM argument:
// -Dsun.net.inetaddr.ttl=30

// SOLUTION 2: Use connection pools that refresh DNS
// OkHttp (used by some Spring RestTemplate implementations)
ConnectionPool pool = new ConnectionPool(50, 5, TimeUnit.MINUTES);
OkHttpClient client = new OkHttpClient.Builder()
    .connectionPool(pool)
    .dns(hostname -> InetAddress.getAllByName(hostname)) // Fresh resolution
    .build();

// SOLUTION 3: For Netty/WebFlux
@Bean
public ReactorResourceFactory resourceFactory() {
    ReactorResourceFactory factory = new ReactorResourceFactory();
    factory.setConnectionProvider(ConnectionProvider.builder("custom")
        .maxConnections(500)
        .maxLifeTime(Duration.ofMinutes(5)) // Force reconnect → fresh DNS
        .build());
    return factory;
}
```

---

## Graceful Shutdown Failures

### Problem
```
Pod termination sequence:
  1. SIGTERM sent to process
  2. Kubernetes removes pod from Service endpoints
  3. Application starts shutting down
  4. BUT: Load balancer might still route traffic (race condition!)
  5. In-flight requests might be killed

Result: 502/503 errors during deployments
```

### Solutions
```yaml
# Spring Boot graceful shutdown
server:
  shutdown: graceful  # Wait for in-flight requests to complete

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # Max wait time

---
# Kubernetes: Add preStop hook for safety
spec:
  containers:
    - name: app
      lifecycle:
        preStop:
          exec:
            command: ["sh", "-c", "sleep 10"]
            # Wait 10s for load balancer to remove this pod
            # THEN Spring Boot starts graceful shutdown
      terminationGracePeriodSeconds: 60
      # Total time: 10s (preStop) + 30s (Spring shutdown) = 40s < 60s
```

```java
// Custom shutdown hook for cleanup
@Component
public class GracefulShutdownHandler {
    
    @PreDestroy
    public void onShutdown() {
        log.info("Shutdown initiated - completing in-flight requests");
        
        // Deregister from service discovery
        serviceRegistry.deregister();
        
        // Wait for in-flight requests
        // (Spring handles this with server.shutdown=graceful)
        
        // Close external connections gracefully
        kafkaProducer.flush();
        redisConnection.close();
        
        log.info("Shutdown complete");
    }
    
    @EventListener(ContextClosedEvent.class)
    public void onContextClosed() {
        // Stop accepting new scheduled tasks
        scheduledExecutor.shutdown();
    }
}
```

---

## Health Check Failures

### Deep Health Checks vs Shallow
```java
// ANTI-PATTERN: Deep health check that causes cascading failures
@Component
public class DeepHealthIndicator implements HealthIndicator {
    @Override
    public Health health() {
        // If DB is slow, this health check makes Pod "unhealthy"
        // K8s kills it → more load on remaining pods → they become slow too
        // → ALL pods get killed → TOTAL OUTAGE
        jdbcTemplate.queryForObject("SELECT COUNT(*) FROM users", Long.class);
        redisTemplate.ping();
        externalService.healthCheck();
        return Health.up().build();
    }
}

// CORRECT: Separate liveness and readiness
// Liveness = "is the process alive?" (shallow, fast)
// Readiness = "can it serve traffic?" (checks dependencies)

// application.yml
management:
  endpoint:
    health:
      probes:
        enabled: true
      group:
        liveness:
          include: livenessState  # Just process alive
        readiness:
          include: readinessState, db, redis  # Can serve traffic

// Custom readiness that doesn't cause cascading
@Component
public class SmartReadinessIndicator implements HealthIndicator {
    private final AtomicBoolean dbAvailable = new AtomicBoolean(true);
    
    // Check periodically in background, not on health check request
    @Scheduled(fixedRate = 10000)
    public void checkDb() {
        try {
            jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            dbAvailable.set(true);
        } catch (Exception e) {
            dbAvailable.set(false);
        }
    }
    
    @Override
    public Health health() {
        // Instant response, no I/O during health check
        return dbAvailable.get() ? Health.up().build() 
            : Health.down().withDetail("reason", "DB unavailable").build();
    }
}
```

---

## Log Flooding

### Problem
```
Error occurs → exception logged with stack trace → error causes MORE errors
→ each error logged → disk fills up / log aggregator overwhelmed
→ application slows down due to I/O → more timeouts → more errors → MORE logs

Peak: 100GB+ logs per hour in severe cases
```

### Solutions
```java
// SOLUTION 1: Rate-limit error logging
@Component
public class RateLimitedLogger {
    private final Cache<String, AtomicInteger> errorCounts = Caffeine.newBuilder()
        .expireAfterWrite(Duration.ofMinutes(1))
        .build();
    
    public void logError(String key, String message, Throwable t) {
        AtomicInteger count = errorCounts.get(key, k -> new AtomicInteger(0));
        int current = count.incrementAndGet();
        
        if (current == 1) {
            log.error(message, t); // First occurrence: full stack trace
        } else if (current % 100 == 0) {
            log.error("{} (repeated {} times in last minute)", message, current);
        }
        // Skip intermediate occurrences
    }
}

// SOLUTION 2: Logback rate limiting
// logback-spring.xml
<configuration>
  <appender name="RATE_LIMITED" class="ch.qos.logback.classic.AsyncAppender">
    <queueSize>1000</queueSize>
    <discardingThreshold>50</discardingThreshold> <!-- Drop 50% when queue is 80% full -->
    <neverBlock>true</neverBlock> <!-- Don't block application -->
    <appender-ref ref="FILE"/>
  </appender>
  
  <!-- Turbo filter to limit repetitive messages -->
  <turboFilter class="ch.qos.logback.classic.turbo.DuplicateMessageFilter">
    <AllowedRepetitions>5</AllowedRepetitions>
    <CacheSize>500</CacheSize>
  </turboFilter>
</configuration>

// SOLUTION 3: Structured logging with sampling
@Service
public class OrderService {
    public void processOrder(Order order) {
        try {
            // ...
        } catch (TransientException e) {
            // Sample: log 1% of transient errors
            if (ThreadLocalRandom.current().nextInt(100) == 0) {
                log.warn("Transient error processing order (sampled 1%)", e);
            }
            Metrics.counter("order.transient.errors").increment();
        }
    }
}
```

---

## Configuration Drift

### Problem
```
Multiple instances with different configurations:
  - One instance has old config (deployed last week)
  - Another has new config (deployed today)
  - Feature flags out of sync
  - Different timeouts causing inconsistent behavior
```

### Solutions
```java
// SOLUTION 1: Centralized configuration (Spring Cloud Config)
// application.yml:
spring:
  cloud:
    config:
      uri: http://config-server:8888
      fail-fast: true
      retry:
        max-attempts: 5
        initial-interval: 1000

// SOLUTION 2: Dynamic configuration refresh
@RefreshScope
@Component
public class DynamicConfig {
    @Value("${feature.new-algorithm.enabled:false}")
    private boolean newAlgorithmEnabled;
    
    // Changes when /actuator/refresh is called or config changes detected
}

// SOLUTION 3: Feature flags with consistent evaluation
@Service
public class FeatureFlagService {
    @Autowired private ConfigClient configClient;
    
    // Always evaluates from central source
    public boolean isEnabled(String flag, String userId) {
        return configClient.evaluate(flag, userId);
    }
}

// SOLUTION 4: Configuration validation on startup
@Component
public class ConfigValidator implements ApplicationRunner {
    @Value("${app.database.pool-size}") private int poolSize;
    @Value("${app.timeout.read-ms}") private int readTimeout;
    
    @Override
    public void run(ApplicationArguments args) {
        if (poolSize < 5 || poolSize > 100) {
            throw new IllegalStateException("Invalid pool size: " + poolSize);
        }
        if (readTimeout < 100 || readTimeout > 30000) {
            throw new IllegalStateException("Invalid read timeout: " + readTimeout);
        }
        log.info("Configuration validated successfully");
    }
}
```

---

## Real Production Incident Patterns

### Q: Top 10 production incident patterns at scale companies

```
1. THUNDERING HERD (Cache expiry)
   - Millions of requests hit same cache key
   - Key expires → ALL requests hit DB simultaneously
   - DB overwhelmed → application fails
   Solution: Probabilistic early expiry, cache warming, singleflight

2. RETRY STORM
   - Service returns 503 → all clients retry immediately
   - 3 retries × 1000 clients = 3000 extra requests
   - Overwhelms recovering service → stays down longer
   Solution: Exponential backoff, jitter, circuit breaker

3. METASTABLE FAILURE
   - System appears recovered but is actually in degraded state
   - High queue depth → slow processing → timeout → more retries → higher queue
   - Self-reinforcing cycle even after root cause resolved
   Solution: Load shedding, queue depth limits, automatic recovery

4. CLOCK SKEW
   - Different servers have different clock times
   - Distributed locks expire prematurely/late
   - Token validation fails (JWT "nbf" check)
   - Event ordering broken
   Solution: NTP, fencing tokens, logical clocks

5. SPLIT BRAIN
   - Network partition → two leaders elected
   - Both accept writes → data divergence
   Solution: Quorum-based consensus, fencing tokens

6. HOT PARTITION
   - Celebrity user or viral content → single DB shard/partition overloaded
   - Other shards fine, but hot shard degrades everything
   Solution: Scatter-gather, secondary indexing, hot key splitting

7. MEMORY LEAK (Slow)
   - Grows over days/weeks
   - OOM in production at unpredictable times
   - Often: ThreadLocal leaks, classloader leaks, listener accumulation
   Solution: Heap dump analysis, monitoring trends, regular restarts

8. DEPENDENCY VERSION CONFLICT
   - Library A needs Jackson 2.14, Library B needs Jackson 2.12
   - NoSuchMethodError at runtime
   Solution: BOM (Bill of Materials), dependency convergence checks

9. CONNECTION POOL DEADLOCK
   - Nested transactions using multiple connections from same pool
   - All connections held → inner transactions can't get connections
   Solution: Pool sizing > max nesting, separate pools for nested

10. GC PAUSE STORM
    - Long GC pause → missed heartbeats → marked as dead
    - Traffic redistributed → other nodes overloaded → they GC too
    - Cascade of GC pauses across cluster
    Solution: Tune GC, increase heartbeat timeouts, use ZGC
```
