# Staff Engineer - Part 4: Production Patterns, Anti-Patterns & Real Scenarios
# What actually breaks in production and how to fix it

## Production Failure Scenarios

### Q233: How to handle Thundering Herd / Cache Stampede?

**Answer:**

```java
// PROBLEM: Cache expires → 1000 threads simultaneously hit database for same key
// Result: Database overwhelmed, cascading failure

// SOLUTION 1: Singleflight / Request Coalescing
class SingleFlight<K, V> {
    private final ConcurrentHashMap<K, CompletableFuture<V>> inFlight = new ConcurrentHashMap<>();
    
    V get(K key, Supplier<V> loader) throws Exception {
        CompletableFuture<V> future = inFlight.get(key);
        if (future != null) {
            return future.get();  // Wait for in-flight request (don't make duplicate!)
        }
        
        CompletableFuture<V> newFuture = new CompletableFuture<>();
        CompletableFuture<V> existing = inFlight.putIfAbsent(key, newFuture);
        
        if (existing != null) {
            return existing.get();  // Another thread won the race, wait for it
        }
        
        try {
            V value = loader.get();  // Only ONE thread loads from DB!
            newFuture.complete(value);
            return value;
        } catch (Exception e) {
            newFuture.completeExceptionally(e);
            throw e;
        } finally {
            inFlight.remove(key);
        }
    }
}

// SOLUTION 2: Probabilistic Early Expiration
class StampedeProtectedCache<K, V> {
    private final Cache<K, CacheEntry<V>> cache;
    private final Random random = new Random();
    
    V get(K key, Supplier<V> loader, Duration ttl) {
        CacheEntry<V> entry = cache.getIfPresent(key);
        if (entry != null) {
            // Probabilistically refresh BEFORE expiry (XFetch algorithm)
            double remaining = entry.expiresAt - System.currentTimeMillis();
            double delta = ttl.toMillis() * 0.1;  // 10% of TTL
            double random = -delta * Math.log(this.random.nextDouble());
            
            if (remaining - random <= 0) {
                // This thread refreshes early (probabilistic)
                refreshAsync(key, loader, ttl);
            }
            return entry.value;
        }
        // Cache miss - load synchronously
        V value = loader.get();
        cache.put(key, new CacheEntry<>(value, System.currentTimeMillis() + ttl.toMillis()));
        return value;
    }
}

// SOLUTION 3: Mutex on cache miss (simple)
class MutexCache<K, V> {
    private final Map<K, V> cache = new ConcurrentHashMap<>();
    private final Map<K, ReentrantLock> locks = new ConcurrentHashMap<>();
    
    V get(K key, Supplier<V> loader) {
        V value = cache.get(key);
        if (value != null) return value;
        
        ReentrantLock lock = locks.computeIfAbsent(key, k -> new ReentrantLock());
        lock.lock();
        try {
            // Double-check after acquiring lock
            value = cache.get(key);
            if (value != null) return value;
            
            value = loader.get();  // Only one thread loads
            cache.put(key, value);
            return value;
        } finally {
            lock.unlock();
            locks.remove(key);
        }
    }
}
```

---

### Q234: How to handle Hot Key problem?

**Answer:**

```java
// PROBLEM: One key receives 10000x more traffic than others
// (e.g., celebrity post, flash sale item, breaking news)
// Single Redis node / DB row becomes bottleneck

// SOLUTION 1: Local Cache (L1) + Distributed Cache (L2)
class MultiLayerCache<K, V> {
    private final Cache<K, V> localCache;  // Caffeine, per-instance
    private final RedisClient redisCache;   // Shared, distributed
    private final Database db;
    
    V get(K key) {
        // L1: Local (in-memory, per instance, very fast, no network)
        V value = localCache.getIfPresent(key);
        if (value != null) return value;
        
        // L2: Redis (shared across instances)
        value = redisCache.get(key);
        if (value != null) {
            localCache.put(key, value);  // Promote to L1
            return value;
        }
        
        // L3: Database
        value = db.get(key);
        redisCache.set(key, value, Duration.ofMinutes(5));
        localCache.put(key, value);
        return value;
    }
}

// SOLUTION 2: Key Splitting / Replication
class HotKeyReplicator {
    private static final int REPLICAS = 10;
    private final RedisClient redis;
    
    void setHotKey(String key, String value) {
        // Write to multiple replicated keys
        for (int i = 0; i < REPLICAS; i++) {
            redis.set(key + "#" + i, value);
        }
    }
    
    String getHotKey(String key) {
        // Read from random replica (distributes load!)
        int replica = ThreadLocalRandom.current().nextInt(REPLICAS);
        return redis.get(key + "#" + replica);
    }
}

// SOLUTION 3: Request Collapsing with Short TTL
// Hot key gets very short TTL (e.g., 1 second)
// Combined with singleflight → only 1 request per second hits DB
// 10000 req/s → only 1 hits DB, 9999 served from cache
```

---

### Q235: How to implement Graceful Shutdown in Java?

**Answer:**

```java
@Component
class GracefulShutdown {
    private final ExecutorService executor;
    private final DataSource dataSource;
    private final KafkaConsumer<?, ?> consumer;
    
    @PreDestroy  // Spring calls this on shutdown
    void shutdown() {
        log.info("Initiating graceful shutdown...");
        
        // 1. Stop accepting new requests (health check returns 503)
        healthIndicator.markUnhealthy();
        
        // 2. Wait for in-flight requests to complete
        // (Kubernetes sends SIGTERM, then waits terminationGracePeriodSeconds)
        sleep(5000);  // Allow load balancer to drain connections
        
        // 3. Stop consuming messages
        consumer.wakeup();  // Causes poll() to throw WakeupException
        
        // 4. Shutdown thread pools gracefully
        executor.shutdown();
        try {
            if (!executor.awaitTermination(30, TimeUnit.SECONDS)) {
                log.warn("Forcing shutdown of executor");
                executor.shutdownNow();
                executor.awaitTermination(10, TimeUnit.SECONDS);
            }
        } catch (InterruptedException e) {
            executor.shutdownNow();
            Thread.currentThread().interrupt();
        }
        
        // 5. Close connections
        dataSource.close();
        
        log.info("Graceful shutdown complete");
    }
}

// JVM Shutdown Hook (non-Spring):
Runtime.getRuntime().addShutdownHook(new Thread(() -> {
    log.info("Shutdown hook triggered");
    server.stop();
    executor.shutdown();
}));

// Kubernetes configuration:
// terminationGracePeriodSeconds: 60  (time between SIGTERM and SIGKILL)
// preStop hook: sleep 5 (allow LB to deregister)
// readiness probe: /health → false during shutdown

// Spring Boot 2.3+ built-in graceful shutdown:
// server.shutdown=graceful
// spring.lifecycle.timeout-per-shutdown-phase=30s
```

---

### Q236: How to handle Circuit Breaker + Retry + Timeout together?

**Answer:**

```java
// PATTERN: Timeout → Retry → Circuit Breaker (outer to inner)
// Timeout wraps the whole thing
// Retry handles transient failures
// Circuit Breaker prevents cascading failures

// Using Resilience4j:
CircuitBreaker circuitBreaker = CircuitBreaker.of("paymentService", 
    CircuitBreakerConfig.custom()
        .failureRateThreshold(50)
        .slidingWindowSize(10)
        .waitDurationInOpenState(Duration.ofSeconds(30))
        .build());

Retry retry = Retry.of("paymentService",
    RetryConfig.custom()
        .maxAttempts(3)
        .waitDuration(Duration.ofMillis(500))
        .exponentialBackoff(2, Duration.ofSeconds(5))  // 500ms, 1s, 2s
        .retryOnException(e -> e instanceof TransientException)
        .build());

TimeLimiter timeLimiter = TimeLimiter.of(
    TimeLimiterConfig.custom()
        .timeoutDuration(Duration.ofSeconds(3))
        .build());

Bulkhead bulkhead = Bulkhead.of("paymentService",
    BulkheadConfig.custom()
        .maxConcurrentCalls(10)
        .maxWaitDuration(Duration.ofMillis(500))
        .build());

// Compose (order matters! outer → inner):
Supplier<Payment> decorated = Decorators.ofSupplier(() -> paymentService.charge(amount))
    .withCircuitBreaker(circuitBreaker)   // Outermost: fast-fail if circuit open
    .withBulkhead(bulkhead)               // Limit concurrent calls
    .withRetry(retry)                     // Retry transient failures
    .withTimeLimiter(timeLimiter, executor) // Timeout each attempt
    .withFallback(List.of(
        CallNotPermittedException.class,
        TimeoutException.class,
        BulkheadFullException.class
    ), e -> Payment.pending())            // Fallback for all failures
    .decorate();

Payment result = decorated.get();

// DECISION MATRIX:
// Timeout: ALWAYS use (prevent hanging calls)
// Retry: For TRANSIENT failures (network blip, 503)
//   - NOT for: 400, 404, business logic errors
//   - Use exponential backoff + jitter
// Circuit Breaker: When downstream is UNHEALTHY
//   - Prevents flooding a struggling service
//   - Gives downstream time to recover
// Bulkhead: Limit blast radius
//   - One slow service shouldn't consume all threads
```

---

### Q237: How to implement Idempotency in Java services?

**Answer:**

```java
// PROBLEM: Network retry can cause duplicate processing
// User clicks "Pay" → timeout → retry → charged TWICE!

// SOLUTION: Idempotency Key
@Service
class PaymentService {
    private final IdempotencyStore store;  // Redis or DB
    
    Payment processPayment(String idempotencyKey, PaymentRequest request) {
        // 1. Check if already processed
        Payment existing = store.get(idempotencyKey);
        if (existing != null) {
            return existing;  // Return cached result (idempotent!)
        }
        
        // 2. Acquire lock for this key (prevent concurrent duplicates)
        if (!store.acquireLock(idempotencyKey, Duration.ofMinutes(5))) {
            throw new ConflictException("Request already in progress");
        }
        
        try {
            // 3. Process
            Payment payment = gateway.charge(request);
            
            // 4. Store result for future deduplication
            store.put(idempotencyKey, payment, Duration.ofHours(24));
            
            return payment;
        } catch (Exception e) {
            store.releaseLock(idempotencyKey);
            throw e;
        }
    }
}

// Redis implementation:
class RedisIdempotencyStore {
    Payment get(String key) {
        String json = redis.get("idempotency:" + key);
        return json != null ? deserialize(json) : null;
    }
    
    boolean acquireLock(String key, Duration ttl) {
        // SET NX (only if not exists) with expiry
        return redis.set("idempotency-lock:" + key, "locked", 
                        SetArgs.Builder.nx().px(ttl.toMillis()));
    }
    
    void put(String key, Payment payment, Duration ttl) {
        redis.setex("idempotency:" + key, ttl.getSeconds(), serialize(payment));
        redis.del("idempotency-lock:" + key);
    }
}

// Database approach with unique constraint:
// INSERT INTO processed_requests (idempotency_key, result) VALUES (?, ?)
// ON CONFLICT (idempotency_key) DO NOTHING
// If insert succeeds → first time, process
// If conflict → already processed, return stored result
```

---

### Q238: How to handle Database Connection Pool Exhaustion?

**Answer:**

```java
// SYMPTOMS:
// - HikariPool-1 - Connection is not available, request timed out after 30000ms
// - Threads blocked waiting for connection
// - Application appears hung

// DIAGNOSIS:
// 1. Check pool metrics:
HikariPoolMXBean poolBean = hikariDataSource.getHikariPoolMXBean();
int active = poolBean.getActiveConnections();  // In-use
int idle = poolBean.getIdleConnections();      // Available
int waiting = poolBean.getThreadsAwaitingConnection();  // Threads blocked!
int total = poolBean.getTotalConnections();

// If active == maxPoolSize AND waiting > 0 → EXHAUSTION!

// COMMON CAUSES:
// 1. Connection leak (not returning to pool)
@Transactional
void processOrder(Order order) {
    orderRepo.save(order);
    externalService.notify(order);  // If this times out (30s)...
    // Connection held for 30s doing NOTHING → pool starvation
}

// FIX: Separate DB operations from external calls
@Transactional
void saveOrder(Order order) {
    orderRepo.save(order);  // Fast DB operation
}
void processOrder(Order order) {
    saveOrder(order);
    externalService.notify(order);  // Outside transaction!
}

// 2. Long-running queries holding connections
// FIX: Set query timeout
spring.datasource.hikari.connection-timeout: 10000
spring.jpa.properties.javax.persistence.query.timeout: 5000

// 3. N+1 query problem (fetching 1000 items = 1001 queries)
// FIX: Use JOIN FETCH or @EntityGraph
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.customerId = :id")
List<Order> findByCustomerIdWithItems(@Param("id") String id);

// 4. Leak detection:
spring.datasource.hikari.leak-detection-threshold: 30000  # Warn if held > 30s

// PREVENTION:
// - Always use try-with-resources for manual connections
// - Keep transactions SHORT (no external calls inside @Transactional)
// - Set reasonable timeouts on ALL operations
// - Monitor pool metrics with alerts
// - Load test to find pool size sweet spot
```

---

## Performance Anti-Patterns

### Q239: What are the top Java Performance Anti-Patterns?

**Answer:**

```java
// 1. STRING CONCATENATION IN LOOPS
// BAD: O(n²) - creates new String object each iteration
String result = "";
for (int i = 0; i < 100000; i++) {
    result += i;  // Creates new String + copies all previous content!
}
// GOOD: O(n)
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 100000; i++) {
    sb.append(i);
}

// 2. AUTOBOXING IN HOT LOOPS
// BAD: Creates ~1M Long objects
Long sum = 0L;
for (long i = 0; i < 1_000_000; i++) {
    sum += i;  // Unbox, add, rebox → new Long object each iteration!
}
// GOOD:
long sum = 0L;
for (long i = 0; i < 1_000_000; i++) {
    sum += i;
}

// 3. ITERATOR / FOREACH ON ARRAYLIST WITH RANDOM ACCESS
// Not terrible but: ArrayList random access is O(1), iterator adds overhead
// For performance-critical inner loops:
// GOOD ENOUGH: for (String s : list) { }
// FASTEST: for (int i = 0, n = list.size(); i < n; i++) { list.get(i); }

// 4. SYNCHRONIZED ON WRONG SCOPE
// BAD: Lock held during I/O!
synchronized (lock) {
    data = processData();           // CPU work (OK to hold lock)
    result = httpClient.post(data); // I/O!! Other threads blocked for seconds!
}
// GOOD: Minimize critical section
Data data;
synchronized (lock) {
    data = processData();  // Only lock during computation
}
result = httpClient.post(data);  // I/O outside lock!

// 5. CREATING OBJECTS IN TIGHT LOOPS (GC pressure)
// BAD:
for (int i = 0; i < 1_000_000; i++) {
    Point p = new Point(i, i);  // 1M allocations, GC pressure
    if (p.distanceFromOrigin() > threshold) count++;
}
// GOOD: Reuse or use primitives
int x, y;
for (int i = 0; i < 1_000_000; i++) {
    x = i; y = i;
    if (Math.sqrt(x*x + y*y) > threshold) count++;
}

// 6. EXCEPTION FOR FLOW CONTROL
// BAD: Exceptions are EXPENSIVE (capture stack trace!)
try {
    return Integer.parseInt(input);
} catch (NumberFormatException e) {
    return defaultValue;  // Exception overhead for normal flow!
}
// GOOD: Check first
if (isNumeric(input)) return Integer.parseInt(input);
return defaultValue;

// 7. UNBOUNDED COLLECTIONS (Memory leak disguised as feature)
// BAD:
Map<String, Session> sessions = new ConcurrentHashMap<>();
// Never cleaned! Grows forever!
// GOOD:
Cache<String, Session> sessions = Caffeine.newBuilder()
    .maximumSize(100_000)
    .expireAfterAccess(30, TimeUnit.MINUTES)
    .build();

// 8. OVER-SYNCHRONIZATION (contention)
// BAD: All methods synchronized (even reads!)
class Counter {
    private int count;
    synchronized int get() { return count; }  // Read blocked by writes!
    synchronized void increment() { count++; }
}
// GOOD: Use atomic or read-write lock
class Counter {
    private final AtomicInteger count = new AtomicInteger();
    int get() { return count.get(); }  // Lock-free!
    void increment() { count.incrementAndGet(); }
}

// 9. REFLECTION IN HOT PATH
// BAD: 10-100x slower than direct access
for (Object obj : objects) {
    Method m = obj.getClass().getMethod("process");  // Lookup every time!
    m.invoke(obj);
}
// GOOD: Cache method reference, or use interface/lambda
for (Processable obj : objects) {
    obj.process();  // Direct virtual call, JIT can inline
}

// 10. BLOCKING I/O IN EVENT LOOP / COMMON POOL
// BAD: Blocks all parallel streams in JVM!
list.parallelStream().map(item -> {
    return httpClient.send(request);  // BLOCKS carrier thread!
}).collect(toList());
// GOOD: Use dedicated I/O pool or virtual threads
```

---

## Microservices Patterns (Detailed Implementation)

### Q240: Implement Bulkhead Pattern (Thread Pool Isolation)

**Answer:**

```java
// BULKHEAD: Isolate failures to prevent cascading
// If PaymentService is slow, it shouldn't consume ALL threads
// and starve OrderService calls

class BulkheadedService {
    // Separate thread pools for each downstream service
    private final ExecutorService paymentPool = new ThreadPoolExecutor(
        5, 10, 60L, TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(50),
        new ThreadPoolExecutor.AbortPolicy()  // Fail fast if pool exhausted
    );
    
    private final ExecutorService inventoryPool = new ThreadPoolExecutor(
        5, 10, 60L, TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(50),
        new ThreadPoolExecutor.AbortPolicy()
    );
    
    CompletableFuture<Payment> chargePayment(Order order) {
        return CompletableFuture.supplyAsync(
            () -> paymentService.charge(order), 
            paymentPool  // Isolated! If slow, only this pool fills up
        );
    }
    
    CompletableFuture<Void> reserveInventory(Order order) {
        return CompletableFuture.supplyAsync(
            () -> inventoryService.reserve(order.getItems()),
            inventoryPool  // Independent pool
        );
    }
}

// Resilience4j Bulkhead:
Bulkhead bulkhead = Bulkhead.of("paymentService",
    BulkheadConfig.custom()
        .maxConcurrentCalls(10)      // Max 10 concurrent calls
        .maxWaitDuration(Duration.ofMillis(100))  // Wait max 100ms if full
        .build());

// Semaphore-based bulkhead (lighter than thread pool):
Supplier<Payment> bulkheaded = Bulkhead.decorateSupplier(bulkhead, 
    () -> paymentService.charge(amount));
```

---

### Q241: Implement Outbox Pattern (Reliable Event Publishing)

**Answer:**

```java
// PROBLEM: After saving to DB, publishing event to Kafka might fail
// DB committed but event lost → inconsistency!

// OUTBOX PATTERN: Write event to DB in same transaction, then relay to Kafka

// Step 1: Save entity AND outbox event in same transaction
@Transactional
void createOrder(OrderRequest request) {
    Order order = orderRepository.save(new Order(request));
    
    // Write to outbox table (same transaction!)
    OutboxEvent event = new OutboxEvent(
        UUID.randomUUID(),
        "OrderCreated",
        objectMapper.writeValueAsString(new OrderCreatedEvent(order)),
        Instant.now()
    );
    outboxRepository.save(event);
    // Both committed atomically!
}

// Step 2: Background poller reads outbox and publishes to Kafka
@Scheduled(fixedDelay = 100)  // Poll every 100ms
void publishOutboxEvents() {
    List<OutboxEvent> events = outboxRepository.findUnpublished(100);
    for (OutboxEvent event : events) {
        try {
            kafkaTemplate.send("events", event.getPayload()).get();
            outboxRepository.markPublished(event.getId());
        } catch (Exception e) {
            // Will retry on next poll (at-least-once delivery)
            log.warn("Failed to publish event: {}", event.getId());
        }
    }
}

// Outbox table:
// CREATE TABLE outbox_events (
//   id UUID PRIMARY KEY,
//   event_type VARCHAR(100),
//   payload JSONB,
//   created_at TIMESTAMP,
//   published_at TIMESTAMP NULL  -- NULL = not yet published
// );

// Alternative: Debezium CDC (Change Data Capture)
// Reads MySQL/Postgres binlog/WAL → publishes changes to Kafka automatically
// No polling needed! Real-time, exactly-once with log-based approach
```

---

### Q242: What is Backpressure in microservices and how to implement it?

**Answer:**

```java
// BACKPRESSURE: Signal upstream to slow down when downstream can't keep up

// MECHANISM 1: Bounded queue + CallerRunsPolicy (simplest)
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    10, 10, 0L, TimeUnit.MILLISECONDS,
    new ArrayBlockingQueue<>(100),
    new CallerRunsPolicy()  // When queue full: caller thread executes task
    // This naturally slows down the producer!
);

// MECHANISM 2: Rate limiting at API Gateway
// 429 Too Many Requests → client backs off

// MECHANISM 3: Reactive Streams (built-in backpressure)
Flux<Event> events = eventSource.getEvents()
    .onBackpressureBuffer(1000)      // Buffer up to 1000
    .onBackpressureDrop(dropped ->   // Then start dropping
        metrics.increment("events.dropped"))
    .limitRate(100);                 // Request only 100 at a time

// MECHANISM 4: Kafka Consumer (natural backpressure)
// Consumer polls at its own rate
// If consumer is slow → lag increases
// Consumer doesn't crash (it just falls behind)
// Scale consumers to keep up with producers

// MECHANISM 5: HTTP response with Retry-After header
@GetMapping("/process")
ResponseEntity<?> process() {
    if (overloaded()) {
        return ResponseEntity.status(503)
            .header("Retry-After", "5")  // "Try again in 5 seconds"
            .body("Service overloaded");
    }
    return ResponseEntity.ok(doProcess());
}

// MECHANISM 6: Token Bucket at service boundary
@Component
class BackpressureFilter implements Filter {
    private final Semaphore permits = new Semaphore(100);  // Max 100 concurrent
    
    @Override
    public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain) 
            throws IOException, ServletException {
        if (!permits.tryAcquire(100, TimeUnit.MILLISECONDS)) {
            ((HttpServletResponse) resp).sendError(503, "Server busy");
            return;
        }
        try {
            chain.doFilter(req, resp);
        } finally {
            permits.release();
        }
    }
}
```

---

## Advanced Spring Internals

### Q243: Explain Spring Transaction Propagation Levels.

**Answer:**

```java
// REQUIRED (default): Join existing TX or create new one
@Transactional(propagation = Propagation.REQUIRED)
void method() { }  
// Called with TX → uses same TX (rollback affects caller!)
// Called without TX → creates new TX

// REQUIRES_NEW: Always create new TX (suspend current if exists)
@Transactional(propagation = Propagation.REQUIRES_NEW)
void auditLog() { }
// Always independent TX → commits even if outer TX rolls back
// Use case: Audit logging must persist regardless of business TX outcome

// NESTED: Nested TX within current (savepoint-based)
@Transactional(propagation = Propagation.NESTED)
void nestedOp() { }
// Creates savepoint → can rollback to savepoint without affecting outer TX
// Only works with JDBC (not JTA)

// SUPPORTS: Run in TX if one exists, otherwise non-transactional
@Transactional(propagation = Propagation.SUPPORTS)
void readData() { }

// NOT_SUPPORTED: Suspend current TX, run non-transactional
@Transactional(propagation = Propagation.NOT_SUPPORTED)
void nonTxOperation() { }

// MANDATORY: Must run within existing TX (throw if none)
@Transactional(propagation = Propagation.MANDATORY)
void mustBeInTx() { }

// NEVER: Must NOT run within TX (throw if one exists)
@Transactional(propagation = Propagation.NEVER)
void neverInTx() { }

// COMMON PITFALL: Self-invocation bypasses proxy!
@Service
class OrderService {
    @Transactional
    public void createOrder(Order order) {
        save(order);
        this.sendNotification(order);  // THIS DOESN'T WORK!
        // 'this' is the actual bean, not the proxy
        // @Transactional on sendNotification is IGNORED!
    }
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void sendNotification(Order order) { }
}

// FIX 1: Inject self
@Autowired @Lazy private OrderService self;
self.sendNotification(order);  // Goes through proxy!

// FIX 2: Separate into different class
@Service
class NotificationService {
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void sendNotification(Order order) { }
}
```

---

### Q244: Explain Spring Circular Dependency and how it's resolved.

**Answer:**

```java
// CIRCULAR DEPENDENCY: A depends on B, B depends on A

@Service
class ServiceA {
    @Autowired private ServiceB b;  // Needs B to construct
}
@Service
class ServiceB {
    @Autowired private ServiceA a;  // Needs A to construct
}

// HOW SPRING RESOLVES (for singleton scope with field/setter injection):
// 1. Spring starts creating A (constructor called, not yet injected)
// 2. A registered in "early singleton" cache (partially constructed!)
// 3. Spring starts creating B (constructor called)
// 4. B needs A → finds A in early singleton cache → injects partial A
// 5. B fully constructed
// 6. A gets B injected → A fully constructed
// 7. Both beans complete

// THREE-LEVEL CACHE:
// singletonObjects: Fully initialized beans
// earlySingletonObjects: Partially initialized (exposed for circular ref)
// singletonFactories: ObjectFactory to create early reference

// DOES NOT WORK WITH CONSTRUCTOR INJECTION:
@Service
class ServiceA {
    private final ServiceB b;
    ServiceA(ServiceB b) { this.b = b; }  // Cannot create A without B!
}
@Service
class ServiceB {
    private final ServiceA a;
    ServiceB(ServiceA a) { this.a = a; }  // Cannot create B without A!
}
// → BeanCurrentlyInCreationException!

// FIXES:
// 1. @Lazy on one dependency
@Service
class ServiceA {
    private final ServiceB b;
    ServiceA(@Lazy ServiceB b) { this.b = b; }  // Injects proxy, resolved later
}

// 2. Redesign (best approach - circular dependency = design smell)
// Extract shared logic into a third service

// 3. Use setter injection for one of them
// 4. Use @PostConstruct for initialization logic

// Spring Boot 2.6+ DISABLES circular references by default!
// spring.main.allow-circular-references=true  (to re-enable, not recommended)
```

---

### Q245: How does Spring Boot Auto-Configuration ordering work?

**Answer:**

```java
// Auto-configuration classes are ordered by:
// 1. @AutoConfigureBefore / @AutoConfigureAfter
// 2. @AutoConfigureOrder (Ordered.LOWEST_PRECEDENCE default)
// 3. Alphabetical as tiebreaker

@AutoConfiguration
@AutoConfigureAfter(DataSourceAutoConfiguration.class)  // Run after DataSource
@ConditionalOnClass(JdbcTemplate.class)
@ConditionalOnSingleCandidate(DataSource.class)
class JdbcTemplateAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean  // Only if user hasn't defined their own
    JdbcTemplate jdbcTemplate(DataSource dataSource) {
        return new JdbcTemplate(dataSource);
    }
}

// Condition evaluation order:
// 1. @ConditionalOnClass - is the class on classpath?
// 2. @ConditionalOnBean / @ConditionalOnMissingBean - bean exists?
// 3. @ConditionalOnProperty - property set?
// 4. @ConditionalOnResource - resource file exists?
// 5. @ConditionalOnWebApplication - is this a web app?
// 6. Custom @Conditional implementations

// Debug auto-configuration:
// --debug flag or debug=true in application.properties
// Shows: CONDITIONS EVALUATION REPORT
// Positive matches (applied) and Negative matches (skipped)
```

---

## Kafka / Messaging Deep Dive

### Q246: Explain Kafka Consumer Group mechanics and rebalancing.

**Answer:**

```java
// CONSUMER GROUP: Multiple consumers sharing partition assignment
// Each partition assigned to EXACTLY ONE consumer in the group
// If consumers > partitions → some consumers idle

// PARTITION ASSIGNMENT:
// Topic: orders (6 partitions)
// Consumer Group: order-processors (3 consumers)
//
// Assignment: 
// Consumer-1: [P0, P1]
// Consumer-2: [P2, P3]  
// Consumer-3: [P4, P5]

// REBALANCING triggers:
// 1. Consumer joins group (new instance scaled up)
// 2. Consumer leaves group (crash, shutdown, timeout)
// 3. Topic metadata change (partition count increased)
// 4. Consumer fails to heartbeat within session.timeout.ms

// REBALANCING IS EXPENSIVE:
// - All consumers stop processing during rebalance
// - Partitions reassigned (may cause duplicate processing)
// - Offset commits may be lost

// COOPERATIVE REBALANCING (incremental, Kafka 2.4+):
properties.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
    CooperativeStickyAssignor.class.getName());
// Only affected partitions are revoked/assigned
// Other consumers continue processing!

// EXACTLY-ONCE SEMANTICS:
// Producer: enable.idempotence=true, transactional.id=my-producer
// Consumer: isolation.level=read_committed
producer.initTransactions();
try {
    producer.beginTransaction();
    producer.send(new ProducerRecord<>("output-topic", key, value));
    producer.sendOffsetsToTransaction(offsets, consumerGroupId);
    producer.commitTransaction();
} catch (Exception e) {
    producer.abortTransaction();
}

// Consumer configuration for reliability:
Properties props = new Properties();
props.put("bootstrap.servers", "kafka:9092");
props.put("group.id", "order-processors");
props.put("enable.auto.commit", "false");  // Manual commit!
props.put("auto.offset.reset", "earliest");
props.put("max.poll.records", 500);
props.put("max.poll.interval.ms", 300000);  // 5 min max processing time
props.put("session.timeout.ms", 30000);
props.put("heartbeat.interval.ms", 10000);

// Manual commit pattern:
while (running) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(1000));
    for (ConsumerRecord<String, String> record : records) {
        process(record);  // Process BEFORE committing!
    }
    consumer.commitSync();  // Commit AFTER processing
    // At-least-once: if crash between process and commit → reprocess
}
```

---

### Q247: What are the key differences between Kafka and RabbitMQ?

**Answer:**

| Feature | Kafka | RabbitMQ |
|---------|-------|----------|
| Model | Distributed log (append-only) | Message broker (queue) |
| Ordering | Per-partition guaranteed | Per-queue (with single consumer) |
| Retention | Time/size-based (replay possible!) | Until consumed (deleted after ack) |
| Throughput | Very high (millions/sec) | High (tens of thousands/sec) |
| Consumer model | Pull (consumer polls) | Push (broker delivers) |
| Replay | Yes (seek to any offset) | No (message gone after consumed) |
| Routing | Topics + partitions | Exchanges + routing keys + bindings |
| Use case | Event streaming, log aggregation | Task queues, RPC, routing |
| Scaling | Add partitions | Add queues + consumers |
| Message size | Optimized for small (< 1MB) | Flexible |
| Protocol | Custom binary | AMQP, MQTT, STOMP |

---

## Summary: What separates Staff Engineers in interviews

| Capability | What they look for |
|-----------|-------------------|
| **Depth** | Can explain WHY (not just WHAT). E.g., "Why does ConcurrentHashMap use CAS for empty buckets?" |
| **Trade-offs** | Every design decision has trade-offs. Always articulate both sides. |
| **Production thinking** | "What happens at 10x traffic? What if this service goes down? How do we monitor?" |
| **System thinking** | Understand how your code affects GC, CPU cache, network, downstream services |
| **Failure modes** | Can enumerate what can go wrong and how to handle each case |
| **Code quality** | Implementation is clean, handles edge cases, has proper error handling |
| **Scale awareness** | Solutions that work for 1 user vs 1M users vs 1B events/day |
| **Debugging ability** | Can systematically diagnose production issues (not just guess) |

