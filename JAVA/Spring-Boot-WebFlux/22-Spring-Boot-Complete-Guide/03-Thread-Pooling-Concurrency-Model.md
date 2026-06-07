# Thread Pooling & Concurrency Model in Spring Boot

## Table of Contents
1. [Tomcat Thread Model](#tomcat-thread-model)
2. [Thread Pool Configuration](#thread-pool-configuration)
3. [Request-Per-Thread Model Explained](#request-per-thread-model-explained)
4. [Async Processing](#async-processing)
5. [@Async Thread Pool](#async-thread-pool)
6. [Scheduler Thread Pool](#scheduler-thread-pool)
7. [Database Connection Pool Threads](#database-connection-pool-threads)
8. [Virtual Threads (Java 21+)](#virtual-threads-java-21)
9. [Thread Safety in Spring](#thread-safety-in-spring)
10. [Thread Dumps & Monitoring](#thread-dumps--monitoring)
11. [Common Concurrency Issues](#common-concurrency-issues)
12. [Thread Pool Sizing Strategies](#thread-pool-sizing-strategies)

---

## Tomcat Thread Model

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TOMCAT NIO THREAD MODEL                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐                                                     │
│  │  Acceptor    │  1 thread - accepts new TCP connections            │
│  │  Thread      │  Hands off to Poller                               │
│  └──────┬───────┘                                                    │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────┐                                                     │
│  │  Poller      │  1-2 threads - monitors NIO channels for           │
│  │  Thread(s)   │  read/write readiness using Selector               │
│  └──────┬───────┘                                                    │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────┐                     │
│  │          Worker Thread Pool                   │                    │
│  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ... ┌────┐    │                    │
│  │  │ T1 │ │ T2 │ │ T3 │ │ T4 │     │T200│    │                    │
│  │  └────┘ └────┘ └────┘ └────┘     └────┘    │                    │
│  │  (default max: 200 threads)                  │                    │
│  │                                              │                    │
│  │  Each thread handles one request at a time:  │                    │
│  │  - Parse HTTP request                        │                    │
│  │  - Execute DispatcherServlet                 │                    │
│  │  - Call controller → service → repository    │                    │
│  │  - Write HTTP response                       │                    │
│  └──────────────────────────────────────────────┘                    │
│                                                                      │
│  ┌─────────────────────────────────────────────┐                     │
│  │  Accept Queue (default: 100)                 │                    │
│  │  When all worker threads busy, new           │                    │
│  │  connections wait here                       │                    │
│  │  If queue full → connection refused          │                    │
│  └──────────────────────────────────────────────┘                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### How a Request Flows Through Threads

```
Client Request → TCP Connection
    │
    ├── Acceptor Thread: accepts() connection
    │       │
    │       ▼
    ├── Poller Thread: registers SocketChannel with Selector
    │       │
    │       ▼ (when data available)
    │
    ├── Worker Thread (from pool): 
    │       │
    │       ├── Read HTTP request from socket
    │       ├── Parse headers, body
    │       ├── Create HttpServletRequest/Response
    │       ├── Pass to Filter Chain
    │       ├── DispatcherServlet processes
    │       ├── Controller method executes
    │       │       │
    │       │       ├── Service layer (same thread)
    │       │       ├── DB query (same thread - BLOCKS!)
    │       │       ├── External API call (same thread - BLOCKS!)
    │       │       └── Response prepared
    │       │
    │       ├── Write response to socket
    │       └── Thread returned to pool
    │
    └── Response sent to client
```

---

## Thread Pool Configuration

### Tomcat Configuration

```yaml
server:
  tomcat:
    threads:
      max: 200            # Maximum worker threads
      min-spare: 10       # Minimum idle threads kept alive
    max-connections: 8192  # Max simultaneous connections (NIO handles this)
    accept-count: 100      # Queue size when max-connections reached
    connection-timeout: 20000  # Connection timeout in ms
    
    # NIO connector specific
    max-keep-alive-requests: 100  # Max requests per keep-alive connection
    keep-alive-timeout: 20000     # Keep-alive timeout
```

### Understanding the Numbers

```
┌─────────────────────────────────────────────────────────────┐
│  max-connections = 8192                                      │
│  ├── These are NIO connections (non-blocking I/O)           │
│  ├── Can have 8192 open TCP connections simultaneously      │
│  └── NOT the same as concurrent request processing          │
│                                                              │
│  threads.max = 200                                          │
│  ├── Maximum 200 requests processed concurrently            │
│  ├── Each request BLOCKS one thread until complete          │
│  └── If request takes 100ms → max throughput = 2000 req/s  │
│                                                              │
│  accept-count = 100                                         │
│  ├── If max-connections reached, 100 more can queue         │
│  └── After queue full → connection refused (TCP RST)        │
│                                                              │
│  THROUGHPUT FORMULA:                                        │
│  Max RPS = threads.max / avg_response_time_in_seconds       │
│  Example: 200 threads / 0.050s = 4000 requests/second       │
│                                                              │
│  WARNING: If avg response time = 2s (slow DB/API):          │
│  200 threads / 2s = only 100 requests/second!               │
└─────────────────────────────────────────────────────────────┘
```

### Jetty Configuration

```yaml
server:
  jetty:
    threads:
      max: 200
      min: 8
      idle-timeout: 60000
    max-http-form-post-size: 200000
```

### Undertow Configuration

```yaml
server:
  undertow:
    threads:
      io: 4          # I/O threads (usually = CPU cores)
      worker: 64     # Worker threads for blocking operations
    buffer-size: 1024
    direct-buffers: true
```

---

## Request-Per-Thread Model Explained

### The Traditional Servlet Model (Spring MVC)

```java
// Each request occupies ONE thread for its ENTIRE duration

@RestController
public class OrderController {
    
    @GetMapping("/orders/{id}")
    public Order getOrder(@PathVariable Long id) {
        // Thread: http-nio-8080-exec-1 handles EVERYTHING:
        
        User user = userService.findById(getCurrentUserId());
        // Thread BLOCKED while DB query runs (~5ms)
        
        Order order = orderRepository.findById(id);
        // Thread BLOCKED while DB query runs (~10ms)
        
        PaymentInfo payment = paymentClient.getPayment(order.getPaymentId());
        // Thread BLOCKED while HTTP call to payment service (~100ms)
        
        EnrichmentData data = enrichmentService.enrich(order);
        // Thread BLOCKED while another service call (~50ms)
        
        return buildResponse(order, payment, data);
        // Total: thread blocked ~165ms for ONE request
    }
}
```

### Thread Utilization Problem

```
Timeline for one request (thread occupied for 200ms):
┌────────────────────────────────────────────────────────────┐
│ Thread: http-nio-8080-exec-1                               │
│                                                            │
│ |--Parse--|--DB--|--DB--|----HTTP Call----|--Build--|--Write-│
│ |  5ms    | 5ms | 10ms |     100ms      |  10ms  |  5ms   │
│                                                            │
│ CPU active: ~20ms (Parse + Build + Write)                  │
│ Thread IDLE but BLOCKED: ~115ms (waiting for I/O)          │
│ Thread utilization: only 15% CPU work!                     │
└────────────────────────────────────────────────────────────┘

With 200 threads and 200ms avg response time:
- Max throughput: 200 / 0.2 = 1000 requests/second
- But CPU is only 15% utilized!
- Threads are mostly WAITING, not COMPUTING
```

### Why This Matters

```
Scenario: E-commerce with 200 Tomcat threads

Normal load (50ms avg response):
  - 200 / 0.05 = 4000 req/s ✓ Fine

Peak load + slow downstream service (2s response):
  - 200 / 2.0 = 100 req/s ✗ THREAD STARVATION!
  - All 200 threads blocked waiting for slow service
  - New requests queue up → timeouts → cascading failure
  - This is called "thread pool exhaustion"
```

---

## Async Processing

### DeferredResult (Release thread early)

```java
@RestController
public class AsyncController {
    
    @GetMapping("/async/orders/{id}")
    public DeferredResult<Order> getOrderAsync(@PathVariable Long id) {
        // Immediately releases the Tomcat worker thread!
        DeferredResult<Order> result = new DeferredResult<>(5000L); // 5s timeout
        
        // Processing happens on a different thread
        CompletableFuture.supplyAsync(() -> orderService.findById(id), asyncExecutor)
            .thenAccept(result::setResult)
            .exceptionally(ex -> {
                result.setErrorResult(ex);
                return null;
            });
        
        return result; // Tomcat thread freed immediately
    }
}
```

### Callable (Spring-managed async)

```java
@GetMapping("/callable/orders/{id}")
public Callable<Order> getOrderCallable(@PathVariable Long id) {
    // Returns immediately, Spring executes Callable on MvcAsync thread
    return () -> {
        // This runs on a different thread pool (taskExecutor)
        return orderService.findById(id);
    };
}
```

### StreamingResponseBody

```java
@GetMapping("/download/{fileId}")
public ResponseEntity<StreamingResponseBody> downloadFile(@PathVariable Long fileId) {
    StreamingResponseBody stream = outputStream -> {
        // Streams data without loading entire file into memory
        // Runs on async thread, Tomcat thread freed
        try (InputStream is = storageService.getFileStream(fileId)) {
            byte[] buffer = new byte[8192];
            int bytesRead;
            while ((bytesRead = is.read(buffer)) != -1) {
                outputStream.write(buffer, 0, bytesRead);
                outputStream.flush();
            }
        }
    };
    
    return ResponseEntity.ok()
        .contentType(MediaType.APPLICATION_OCTET_STREAM)
        .body(stream);
}
```

---

## @Async Thread Pool

### Configuration

```java
@Configuration
@EnableAsync
public class AsyncConfig {
    
    @Bean("taskExecutor")
    public TaskExecutor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);        // Always-alive threads
        executor.setMaxPoolSize(50);         // Max threads under load
        executor.setQueueCapacity(200);      // Queue before scaling up
        executor.setThreadNamePrefix("async-");
        executor.setKeepAliveSeconds(60);    // Idle thread TTL
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        executor.initialize();
        return executor;
    }
    
    @Bean("emailExecutor")
    public TaskExecutor emailExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(500);
        executor.setThreadNamePrefix("email-");
        executor.initialize();
        return executor;
    }
}
```

### How ThreadPoolTaskExecutor Scales

```
┌──────────────────────────────────────────────────────────────┐
│  ThreadPoolTaskExecutor Scaling Behavior                      │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Tasks arrive → Use core threads (corePoolSize = 10)      │
│                                                               │
│  2. All core threads busy → Queue tasks (queueCapacity = 200)│
│                                                               │
│  3. Queue FULL → Create new threads up to maxPoolSize = 50   │
│                                                               │
│  4. Max threads reached + Queue full → RejectedExecution!    │
│                                                               │
│  NOTE: Threads scale to max ONLY AFTER queue is full!        │
│  This is Java ThreadPoolExecutor behavior.                    │
│                                                               │
│  Timeline with 100 concurrent tasks:                         │
│  ├── Tasks 1-10: Handled by core threads                     │
│  ├── Tasks 11-210: Queued (200 capacity)                     │
│  ├── Tasks 211-250: New threads created (up to max 50)       │
│  └── Task 251+: RejectedExecutionException!                  │
│                                                               │
│  Rejection Policies:                                         │
│  - AbortPolicy (default): Throws exception                   │
│  - CallerRunsPolicy: Calling thread executes the task        │
│  - DiscardPolicy: Silently drops the task                    │
│  - DiscardOldestPolicy: Drops oldest queued task             │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### @Async Usage Patterns

```java
@Service
public class NotificationService {
    
    // Fire and forget
    @Async("emailExecutor")
    public void sendWelcomeEmail(User user) {
        emailClient.send(user.getEmail(), buildWelcomeTemplate(user));
        // If this throws, exception is lost unless AsyncUncaughtExceptionHandler configured
    }
    
    // With return value
    @Async("taskExecutor")
    public CompletableFuture<NotificationResult> sendNotification(Notification n) {
        NotificationResult result = gateway.send(n);
        return CompletableFuture.completedFuture(result);
    }
    
    // Combining async results
    public OrderSummary getOrderSummary(Long orderId) {
        CompletableFuture<Order> orderFuture = orderService.findByIdAsync(orderId);
        CompletableFuture<Payment> paymentFuture = paymentService.findByOrderAsync(orderId);
        CompletableFuture<List<Item>> itemsFuture = itemService.findByOrderAsync(orderId);
        
        // All three calls run in parallel!
        CompletableFuture.allOf(orderFuture, paymentFuture, itemsFuture).join();
        
        return new OrderSummary(
            orderFuture.join(),
            paymentFuture.join(),
            itemsFuture.join()
        );
    }
}
```

### @Async Gotchas

```java
// GOTCHA 1: Self-invocation bypasses proxy
@Service
public class MyService {
    @Async
    public void asyncMethod() { /* runs async */ }
    
    public void callerMethod() {
        asyncMethod(); // RUNS SYNCHRONOUSLY! No proxy involved.
        // Fix: Inject self or use ApplicationContext.getBean()
    }
}

// GOTCHA 2: @Async with @Transactional
@Service
public class OrderService {
    @Async
    @Transactional // Transaction runs in the ASYNC thread
    public void processOrder(Long orderId) {
        // New transaction in new thread
        // Parent transaction (if any) is NOT propagated
    }
}

// GOTCHA 3: Exception handling
@Service
public class RiskyService {
    @Async
    public void riskyOperation() {
        throw new RuntimeException("Boom!"); // SILENTLY SWALLOWED!
    }
    
    @Async
    public CompletableFuture<String> saferOperation() {
        throw new RuntimeException("Boom!"); // Caller can handle via .exceptionally()
    }
}
```

---

## Scheduler Thread Pool

### Configuration

```java
@Configuration
@EnableScheduling
public class SchedulerConfig implements SchedulingConfigurer {
    
    @Override
    public void configureTasks(ScheduledTaskRegistrar taskRegistrar) {
        // Default scheduler uses SINGLE THREAD! Configure properly:
        taskRegistrar.setScheduler(schedulerThreadPool());
    }
    
    @Bean(destroyMethod = "shutdown")
    public ScheduledExecutorService schedulerThreadPool() {
        return Executors.newScheduledThreadPool(10,
            new CustomizableThreadFactory("scheduler-"));
    }
}
```

### Default Behavior (IMPORTANT!)

```
┌──────────────────────────────────────────────────────────────┐
│  DEFAULT SCHEDULER: SINGLE THREAD!                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  If you have:                                                │
│  @Scheduled(fixedRate = 1000)  // Task A - takes 5 seconds   │
│  @Scheduled(fixedRate = 1000)  // Task B - takes 1 second    │
│                                                               │
│  With single thread:                                         │
│  |--Task A (5s)--|--Task B (1s)--|--Task A (5s)--|           │
│  Task B is DELAYED because Task A blocks the only thread!    │
│                                                               │
│  With pool of 10 threads:                                    │
│  Thread 1: |--Task A (5s)--|--Task A (5s)--|                 │
│  Thread 2: |--Task B--|--Task B--|--Task B--|                │
│  Both run independently!                                     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### fixedRate vs fixedDelay

```java
// fixedRate: Runs every N ms from START of previous execution
@Scheduled(fixedRate = 5000)
public void fixedRateTask() {
    // If task takes 3s, next starts 2s after completion
    // If task takes 7s, next starts IMMEDIATELY (overlapping possible with pool > 1)
}

// fixedDelay: Runs N ms after COMPLETION of previous execution
@Scheduled(fixedDelay = 5000)
public void fixedDelayTask() {
    // Always 5s gap between end of one and start of next
    // No overlap possible
}
```

---

## Database Connection Pool Threads

### HikariCP (Default in Spring Boot)

```yaml
spring:
  datasource:
    hikari:
      pool-name: MyHikariPool
      minimum-idle: 5           # Min idle connections
      maximum-pool-size: 20     # Max connections
      idle-timeout: 300000      # 5 min - idle connection removed
      max-lifetime: 1800000     # 30 min - connection recycled
      connection-timeout: 30000 # 30s - wait for connection from pool
      leak-detection-threshold: 60000  # 60s - warn if connection held too long
      
      # Connection validation
      connection-test-query: SELECT 1  # For databases without JDBC4
      validation-timeout: 5000
```

### Connection Pool Sizing

```
┌──────────────────────────────────────────────────────────────┐
│  CONNECTION POOL vs THREAD POOL RELATIONSHIP                  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Tomcat threads: 200                                         │
│  DB connections: 20                                          │
│                                                               │
│  If ALL 200 requests need DB access simultaneously:          │
│  - 20 get connections immediately                            │
│  - 180 BLOCK waiting for connection (up to connectionTimeout)│
│  - If timeout → SQLTransientConnectionException              │
│                                                               │
│  FORMULA (from HikariCP wiki):                               │
│  connections = ((core_count * 2) + effective_spindle_count)  │
│                                                               │
│  For SSD-based DB server with 4 cores:                       │
│  connections = (4 * 2) + 1 = 9 (surprisingly low!)           │
│                                                               │
│  Rule of thumb:                                              │
│  - DB pool size << Tomcat thread count                       │
│  - If DB is the bottleneck, more connections won't help      │
│  - More connections = more DB overhead (memory, locks)       │
│                                                               │
│  ANTI-PATTERN:                                               │
│  maximum-pool-size: 200  ← Same as Tomcat threads            │
│  This overwhelms the database!                               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Connection Pool Monitoring

```java
@Component
public class HikariMetrics {
    
    @Autowired
    private DataSource dataSource;
    
    @Scheduled(fixedRate = 30000)
    public void logPoolStats() {
        if (dataSource instanceof HikariDataSource hikari) {
            HikariPoolMXBean pool = hikari.getHikariPoolMXBean();
            log.info("Pool Stats - Active: {}, Idle: {}, Waiting: {}, Total: {}",
                pool.getActiveConnections(),
                pool.getIdleConnections(),
                pool.getThreadsAwaitingConnection(),
                pool.getTotalConnections()
            );
            
            // Alert if threads waiting for connections
            if (pool.getThreadsAwaitingConnection() > 5) {
                alertService.warn("Connection pool pressure detected!");
            }
        }
    }
}
```

---

## Virtual Threads (Java 21+)

### Enabling Virtual Threads in Spring Boot 3.2+

```yaml
# application.yml
spring:
  threads:
    virtual:
      enabled: true  # That's it! Tomcat uses virtual threads
```

### What Changes with Virtual Threads

```
┌──────────────────────────────────────────────────────────────┐
│  PLATFORM THREADS vs VIRTUAL THREADS                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Platform Threads (Traditional):                             │
│  - 1 OS thread per Java thread                               │
│  - ~1MB stack per thread                                     │
│  - 200 threads = 200MB just for stacks                       │
│  - Context switching is expensive                            │
│  - Thread pool is NECESSARY (can't create millions)          │
│                                                               │
│  Virtual Threads (Java 21):                                  │
│  - Lightweight, managed by JVM                               │
│  - ~few KB per thread                                        │
│  - Can have MILLIONS simultaneously                          │
│  - Mounted on carrier (platform) threads when running        │
│  - Unmounted when blocking (I/O, sleep, lock)                │
│  - NO thread pool needed (create per-task)                   │
│                                                               │
│  Blocking I/O with Virtual Threads:                          │
│                                                               │
│  Platform Thread:                                            │
│  |--work--|========BLOCKED on I/O========|--work--|          │
│  (thread idle, wasted)                                       │
│                                                               │
│  Virtual Thread:                                             │
│  |--work--|  UNMOUNTED  |--work--|                           │
│              ↓                                                │
│  Carrier thread freed for other virtual threads!             │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Impact on Spring Boot

```java
// Before (Platform Threads): Need careful thread pool sizing
server.tomcat.threads.max=200  // Limited by memory

// After (Virtual Threads): Essentially unlimited concurrency
// Each request gets its own virtual thread
// No thread pool exhaustion!
// 10,000 concurrent requests? No problem!

// BUT: Database connection pool is still the bottleneck!
// Virtual threads don't give you more DB connections.
```

### When Virtual Threads Help/Don't Help

```
HELPS (I/O-bound workloads):
✓ REST API calling downstream services
✓ Database queries (waiting for results)
✓ File I/O operations
✓ Message queue consumers
✓ Long-polling endpoints

DOESN'T HELP (CPU-bound workloads):
✗ Complex calculations
✗ Image processing
✗ Data transformation
✗ Encryption/decryption
✗ CPU-intensive algorithms

CAUTION:
⚠ synchronized blocks pin the carrier thread
⚠ Use ReentrantLock instead of synchronized with virtual threads
⚠ ThreadLocal may have unexpected behavior (use ScopedValue)
```

---

## Thread Safety in Spring

### Singleton Beans are NOT Thread-Safe by Default

```java
// DANGEROUS: Mutable state in singleton bean
@Service
public class CounterService {
    private int count = 0; // SHARED across all threads!
    
    public void increment() {
        count++; // NOT ATOMIC - race condition!
    }
}

// FIX 1: Use AtomicInteger
@Service
public class CounterService {
    private final AtomicInteger count = new AtomicInteger(0);
    
    public void increment() {
        count.incrementAndGet(); // Thread-safe
    }
}

// FIX 2: Use synchronized (poor performance under contention)
@Service
public class CounterService {
    private int count = 0;
    
    public synchronized void increment() {
        count++;
    }
}

// FIX 3: Use ConcurrentHashMap for caches
@Service
public class CacheService {
    private final ConcurrentHashMap<String, Object> cache = new ConcurrentHashMap<>();
    
    public Object getOrCompute(String key, Supplier<Object> supplier) {
        return cache.computeIfAbsent(key, k -> supplier.get());
    }
}
```

### Thread-Local Pattern

```java
@Component
public class RequestContext {
    private static final ThreadLocal<UserInfo> currentUser = new ThreadLocal<>();
    
    public static void setUser(UserInfo user) {
        currentUser.set(user);
    }
    
    public static UserInfo getUser() {
        return currentUser.get();
    }
    
    public static void clear() {
        currentUser.remove(); // MUST clear to prevent memory leaks!
    }
}

// In a filter:
@Component
public class UserContextFilter implements Filter {
    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
        try {
            UserInfo user = extractUser((HttpServletRequest) req);
            RequestContext.setUser(user);
            chain.doFilter(req, res);
        } finally {
            RequestContext.clear(); // CRITICAL: thread returns to pool!
        }
    }
}
```

### Request-Scoped Beans (Safe Alternative)

```java
@Component
@Scope(value = WebApplicationContext.SCOPE_REQUEST, proxyMode = ScopedProxyMode.TARGET_CLASS)
public class RequestScopedContext {
    private UserInfo user;
    private String correlationId;
    // Each request gets its own instance - no thread safety issues
}
```

---

## Thread Dumps & Monitoring

### Getting Thread Dumps

```bash
# Method 1: jstack
jstack <PID> > thread-dump.txt

# Method 2: Actuator endpoint
curl http://localhost:8080/actuator/threaddump | jq

# Method 3: kill -3 (prints to stdout/stderr)
kill -3 <PID>

# Method 4: JVisualVM, JConsole, or IntelliJ Profiler
```

### Understanding Thread Dump

```
"http-nio-8080-exec-1" #30 daemon prio=5 os_prio=0 tid=0x... nid=0x... WAITING
   java.lang.Thread.State: TIMED_WAITING (parking)
        at jdk.internal.misc.Unsafe.park(Native Method)
        at java.util.concurrent.locks.LockSupport.parkNanos(LockSupport.java:252)
        at com.zaxxer.hikari.pool.HikariPool.createTimeoutException(HikariPool.java:696)
        ...

# This tells you:
# - Thread "http-nio-8080-exec-1" is a Tomcat worker thread
# - It's WAITING for a database connection from HikariPool
# - If many threads show this → connection pool exhaustion
```

### Key Thread States to Monitor

```
RUNNABLE    → Thread actively executing (CPU work)
WAITING     → Waiting indefinitely (Object.wait(), Thread.join())
TIMED_WAIT  → Waiting with timeout (Thread.sleep(), park with timeout)
BLOCKED     → Waiting to acquire monitor lock (synchronized)

Problems to look for:
- Many threads in BLOCKED → Lock contention
- Many threads WAITING on HikariPool → DB pool exhaustion
- Many threads WAITING on HTTP client → Slow downstream service
- Deadlock detected → Two threads waiting on each other's locks
```

---

## Common Concurrency Issues

### 1. Thread Pool Exhaustion

```java
// Problem: All Tomcat threads blocked waiting for slow service
@GetMapping("/data")
public Data getData() {
    return slowExternalService.call(); // Takes 30 seconds!
    // All 200 threads quickly get stuck here
}

// Solution 1: Circuit Breaker (Resilience4j)
@CircuitBreaker(name = "slowService", fallbackMethod = "fallback")
@TimeLimiter(name = "slowService") // Timeout after 3s
public CompletableFuture<Data> getData() {
    return CompletableFuture.supplyAsync(() -> slowExternalService.call());
}

// Solution 2: Bulkhead (limit threads for this operation)
@Bulkhead(name = "slowService", type = Bulkhead.Type.THREADPOOL)
public CompletableFuture<Data> getData() { ... }
```

### 2. Race Condition in Lazy Initialization

```java
// Problem: Double initialization
@Service
public class ExpensiveService {
    private volatile ExpensiveResource resource; // Must be volatile!
    
    public ExpensiveResource getResource() {
        if (resource == null) { // Check 1
            synchronized (this) {
                if (resource == null) { // Check 2 (double-checked locking)
                    resource = initializeExpensiveResource();
                }
            }
        }
        return resource;
    }
}
```

### 3. Lost Updates

```java
// Problem: Read-modify-write without synchronization
@Service
public class InventoryService {
    @Transactional
    public void decrementStock(Long productId) {
        Product p = productRepo.findById(productId).orElseThrow();
        p.setStock(p.getStock() - 1); // Race condition!
        productRepo.save(p);
    }
    
    // Fix: Pessimistic locking
    @Transactional
    public void decrementStockSafe(Long productId) {
        Product p = productRepo.findByIdForUpdate(productId); // SELECT ... FOR UPDATE
        p.setStock(p.getStock() - 1);
        productRepo.save(p);
    }
    
    // Fix: Optimistic locking with @Version
    @Transactional
    public void decrementStockOptimistic(Long productId) {
        // @Version field causes OptimisticLockException on concurrent update
        // Retry logic needed
    }
    
    // Fix: Atomic update query
    @Modifying
    @Query("UPDATE Product p SET p.stock = p.stock - 1 WHERE p.id = :id AND p.stock > 0")
    int decrementStock(@Param("id") Long id); // Returns 0 if no stock
}
```

---

## Thread Pool Sizing Strategies

### CPU-Bound Tasks

```
Optimal threads = Number of CPU cores (or cores + 1)

Rationale: 
- Each thread uses one core fully
- More threads = context switching overhead
- No benefit from extra threads (CPU is the bottleneck)

Example: Image processing service
  CPU cores = 8
  Thread pool = 8-9 threads
```

### I/O-Bound Tasks

```
Optimal threads = CPU cores * (1 + Wait Time / Service Time)

Example: API that calls database
  CPU cores = 8
  Avg wait time (DB I/O) = 100ms
  Avg service time (CPU) = 10ms
  Optimal = 8 * (1 + 100/10) = 8 * 11 = 88 threads

Example: API that calls slow external service
  CPU cores = 8
  Avg wait time = 500ms
  Avg service time = 5ms
  Optimal = 8 * (1 + 500/5) = 8 * 101 = 808 threads!
  (But limited by memory/DB connections in practice)
```

### Little's Law for Thread Pool Sizing

```
L = λ * W

L = Number of threads needed (concurrency level)
λ = Arrival rate (requests/second)
W = Average response time (seconds)

Example:
  Target: Handle 2000 requests/second
  Average response time: 100ms = 0.1s
  
  L = 2000 * 0.1 = 200 threads needed

If response time increases to 500ms:
  L = 2000 * 0.5 = 1000 threads needed!
  (This is why slow services cause cascading failures)
```

### Production Configuration Template

```yaml
# Conservative production configuration
server:
  tomcat:
    threads:
      max: 200
      min-spare: 20
    max-connections: 10000
    accept-count: 200
    connection-timeout: 10000

spring:
  datasource:
    hikari:
      maximum-pool-size: 30  # Much less than Tomcat threads
      minimum-idle: 10
      connection-timeout: 5000  # Fail fast if no connection

  task:
    execution:
      pool:
        core-size: 10
        max-size: 50
        queue-capacity: 200
      thread-name-prefix: "app-async-"
    scheduling:
      pool:
        size: 5
      thread-name-prefix: "app-scheduler-"
```
