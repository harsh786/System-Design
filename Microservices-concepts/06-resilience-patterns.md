# Resilience and Fault Tolerance Patterns in Microservices

## Table of Contents
- [Stability Patterns](#stability-patterns)
- [Availability Patterns](#availability-patterns)
- [Recovery Patterns](#recovery-patterns)
- [Load Management](#load-management)
- [Chaos Engineering](#chaos-engineering)
- [Libraries and Frameworks](#libraries-and-frameworks)

---

## Stability Patterns

### Circuit Breaker

**Problem:** A downstream service is failing. Continuing to call it wastes resources, increases latency, and can cascade failures across the system.

**How it Works:** The circuit breaker monitors calls to a downstream service. When failures exceed a threshold, it "opens" the circuit, immediately rejecting calls without attempting them. After a timeout, it enters "half-open" state to test if the service has recovered.

**State Diagram:**
```
                    failure threshold exceeded
         ┌──────────────────────────────────────────┐
         │                                          │
         ▼                                          │
    ┌─────────┐         timeout expires        ┌────┴────┐
    │  OPEN   │ ──────────────────────────────►│  CLOSED │
    │(reject  │                                │(allow   │
    │ all)    │         success threshold       │ all)    │
    └────┬────┘◄────────── met ────────────────└─────────┘
         │                                          ▲
         │ timeout expires                          │
         ▼                                          │
    ┌──────────┐         success                    │
    │HALF-OPEN │────────────────────────────────────┘
    │(allow    │
    │ limited) │────── failure ──────► OPEN
    └──────────┘
```

**Configuration Parameters:**
| Parameter | Description | Typical Value |
|-----------|-------------|---------------|
| failureRateThreshold | % failures to trip | 50% |
| slowCallRateThreshold | % slow calls to trip | 100% |
| slowCallDurationThreshold | What's "slow" | 2000ms |
| slidingWindowSize | Number of calls to evaluate | 100 |
| minimumNumberOfCalls | Min calls before evaluating | 10 |
| waitDurationInOpenState | Time before half-open | 60s |
| permittedNumberOfCallsInHalfOpenState | Test calls | 10 |

**Code Example (Resilience4j):**

```java
@Configuration
public class CircuitBreakerConfig {
    @Bean
    public CircuitBreaker orderServiceCircuitBreaker() {
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
            .failureRateThreshold(50)
            .slowCallRateThreshold(80)
            .slowCallDurationThreshold(Duration.ofSeconds(2))
            .slidingWindowType(SlidingWindowType.COUNT_BASED)
            .slidingWindowSize(100)
            .minimumNumberOfCalls(10)
            .waitDurationInOpenState(Duration.ofSeconds(60))
            .permittedNumberOfCallsInHalfOpenState(10)
            .recordExceptions(IOException.class, TimeoutException.class)
            .ignoreExceptions(BusinessException.class)
            .build();
        
        return CircuitBreaker.of("orderService", config);
    }
}

@Service
public class OrderClient {
    private final CircuitBreaker circuitBreaker;
    private final RestTemplate restTemplate;
    
    public Order getOrder(String orderId) {
        return CircuitBreaker.decorateSupplier(circuitBreaker, 
            () -> restTemplate.getForObject("/orders/" + orderId, Order.class)
        ).get();
    }
    
    // With fallback
    public Order getOrderWithFallback(String orderId) {
        return Try.ofSupplier(
            CircuitBreaker.decorateSupplier(circuitBreaker,
                () -> restTemplate.getForObject("/orders/" + orderId, Order.class))
        ).recover(CallNotPermittedException.class, 
            e -> getCachedOrder(orderId)  // fallback
        ).get();
    }
}
```

**Monitoring Considerations:**
- Track circuit state transitions (alert on OPEN)
- Monitor failure rate, slow call rate
- Dashboard showing circuit state per downstream service
- Metrics: `circuit_breaker_state`, `circuit_breaker_failure_rate`, `circuit_breaker_calls_total`

**When to Use:**
- Calling remote services (HTTP, gRPC)
- Database connections to external DBs
- Any I/O operation that can timeout or fail

---

### Retry Pattern

**Problem:** Transient failures (network blips, temporary overload) would succeed if retried.

**How it Works:** Automatically retry failed operations with configurable delays, backoff strategies, and maximum attempts.

**State Diagram:**
```
┌───────┐     success     ┌─────────┐
│ Call  │────────────────►│ Success │
└───┬───┘                 └─────────┘
    │ failure
    ▼
┌────────────┐  retries < max   ┌──────┐
│   Wait     │◄─────────────────│Retry │
│ (backoff)  │                  │      │
└─────┬──────┘                  └──────┘
      │                            ▲
      └────────────────────────────┘
      │
      │ retries >= max
      ▼
┌──────────┐
│  Failure │
└──────────┘
```

**Exponential Backoff with Jitter:**

```java
// Without jitter — all clients retry at same time (thundering herd)
delay = baseDelay * 2^attempt  // 1s, 2s, 4s, 8s...

// With full jitter — randomized spread
delay = random(0, baseDelay * 2^attempt)

// With decorrelated jitter (AWS recommendation)
delay = min(maxDelay, random(baseDelay, previousDelay * 3))
```

**Code Example:**

```java
@Configuration
public class RetryConfig {
    @Bean
    public Retry paymentRetry() {
        RetryConfig config = RetryConfig.custom()
            .maxAttempts(3)
            .waitDuration(Duration.ofMillis(500))
            .intervalFunction(IntervalFunction.ofExponentialRandomBackoff(
                500,      // initial interval ms
                2.0,      // multiplier
                0.5       // randomization factor
            ))
            .retryOnException(e -> e instanceof IOException 
                || e instanceof TimeoutException)
            .retryOnResult(response -> response.getStatusCode() == 503)
            .ignoreExceptions(BusinessValidationException.class)
            .failAfterMaxAttempts(true)
            .build();
        
        return Retry.of("payment", config);
    }
}

@Service
public class PaymentClient {
    public PaymentResult processPayment(PaymentRequest request) {
        return Retry.decorateSupplier(paymentRetry, () -> {
            // Ensure idempotency key is sent
            request.setIdempotencyKey(UUID.randomUUID().toString());
            return httpClient.post("/payments", request, PaymentResult.class);
        }).get();
    }
}
```

**Configuration Parameters:**
| Parameter | Description | Typical Value |
|-----------|-------------|---------------|
| maxAttempts | Total attempts including first | 3-5 |
| waitDuration | Base delay | 100ms-1s |
| multiplier | Exponential factor | 2.0 |
| maxDelay | Cap on delay | 30s-60s |
| retryableExceptions | Which errors to retry | Transient only |
| jitterFactor | Randomization | 0.1-0.5 |

**Monitoring Considerations:**
- Track retry count distribution
- Alert if retry rate exceeds threshold
- Monitor per-endpoint retry rates
- Metrics: `retry_attempts_total`, `retry_calls_succeeded_with_retry`

**When to Use:**
- Transient network errors
- HTTP 429 (Too Many Requests), 503 (Service Unavailable)
- Database connection timeouts
- NOT for: 4xx client errors, business logic failures, non-idempotent operations without idempotency keys

---

### Timeout Pattern

**Problem:** Waiting indefinitely for a response ties up resources and can cascade failures.

**How it Works:** Set a maximum time to wait for a response. If exceeded, fail fast and free resources.

**Code Example:**

```java
// HTTP client timeout
HttpClient client = HttpClient.newBuilder()
    .connectTimeout(Duration.ofSeconds(2))
    .build();

HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("http://order-service/orders/123"))
    .timeout(Duration.ofSeconds(5))  // request timeout
    .build();

// Resilience4j TimeLimiter
TimeLimiterConfig config = TimeLimiterConfig.custom()
    .timeoutDuration(Duration.ofSeconds(3))
    .cancelRunningFuture(true)
    .build();

TimeLimiter timeLimiter = TimeLimiter.of("orderService", config);

CompletableFuture<Order> future = CompletableFuture.supplyAsync(
    () -> orderClient.getOrder(orderId));

Order order = timeLimiter.executeFutureSupplier(() -> future);
```

**Timeout Budget Pattern:**
```
Total timeout: 5s
├── Service A call: 2s max
├── Service B call: 2s max  
└── Processing: 1s
```

Pass remaining timeout in headers: `X-Request-Timeout: 3200ms`

**Configuration Parameters:**
| Parameter | Typical Value |
|-----------|---------------|
| Connection timeout | 1-3s |
| Read/Request timeout | 3-10s |
| Overall operation timeout | 5-30s |

**When to Use:** Always. Every external call should have a timeout. No exceptions.

---

### Bulkhead Pattern

**Problem:** A failure in one part of the system consumes all resources (threads, connections), causing complete system failure.

**How it Works:** Isolate components into pools so that failure in one cannot exhaust resources needed by others.

**Architecture:**
```
┌────────────────────────────────────────────────────┐
│                    Service                          │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐│
│  │  Bulkhead A  │  │  Bulkhead B  │  │Bulkhead C││
│  │ (Order Svc)  │  │ (Payment Svc)│  │(Notif Svc││
│  │              │  │              │  │          ││
│  │ max: 10      │  │ max: 5       │  │ max: 3   ││
│  │ threads      │  │ threads      │  │ threads  ││
│  │              │  │              │  │          ││
│  │ ████░░░░░░  │  │ ███░░        │  │ ██░      ││
│  └──────────────┘  └──────────────┘  └──────────┘│
│                                                    │
│  If Payment pool exhausted, Order & Notif unaffected│
└────────────────────────────────────────────────────┘
```

**Code Example:**

```java
// Thread Pool Bulkhead
ThreadPoolBulkheadConfig config = ThreadPoolBulkheadConfig.custom()
    .maxThreadPoolSize(10)
    .coreThreadPoolSize(5)
    .queueCapacity(20)
    .keepAliveDuration(Duration.ofMillis(100))
    .build();

ThreadPoolBulkhead bulkhead = ThreadPoolBulkhead.of("orderService", config);

CompletionStage<Order> result = bulkhead.executeSupplier(
    () -> orderClient.getOrder(orderId));

// Semaphore Bulkhead (simpler, no thread pool)
BulkheadConfig semaphoreConfig = BulkheadConfig.custom()
    .maxConcurrentCalls(25)
    .maxWaitDuration(Duration.ofMillis(500))
    .build();

Bulkhead semaphoreBulkhead = Bulkhead.of("paymentService", semaphoreConfig);
```

**Configuration Parameters:**
| Parameter | Description |
|-----------|-------------|
| maxThreadPoolSize | Max threads in pool |
| coreThreadPoolSize | Base thread count |
| queueCapacity | Waiting requests before rejection |
| maxConcurrentCalls | (Semaphore) max parallel calls |
| maxWaitDuration | Wait for permit before rejecting |

**Monitoring Considerations:**
- Track available vs used capacity per bulkhead
- Alert when queue depth exceeds threshold
- Monitor rejection rate

**When to Use:**
- Isolating calls to different downstream services
- Separating critical vs non-critical operations
- Connection pool isolation per tenant (multi-tenant)

---

### Rate Limiting / Throttling

**Problem:** Protect services from being overwhelmed by too many requests.

**How it Works:** Limit the rate of requests using various algorithms.

**Algorithms:**

```
TOKEN BUCKET:
┌─────────────────────────┐
│  Bucket (capacity: 10)  │     Tokens added at fixed rate
│  ████████░░             │     (e.g., 10/second)
│  (8 tokens available)   │
└─────────────────────────┘     Request takes 1 token.
                                Empty bucket = rejected.

LEAKY BUCKET:
┌─────────────────────────┐
│  Queue (capacity: 10)   │     Requests processed at
│  ████████░░             │     fixed rate (leak rate).
│  (8 queued)             │     Full queue = rejected.
└────────────┬────────────┘
             │ fixed outflow rate
             ▼

FIXED WINDOW:
|----window 1----|----window 2----|
  ████████░░         ███░░░░░░░░
  (8/10 used)       (3/10 used)
  
  Problem: burst at window boundary (20 requests in 1s)

SLIDING WINDOW LOG:
  Track timestamp of each request in window.
  Count = requests in [now - window, now]
  Precise but memory-intensive.

SLIDING WINDOW COUNTER:
  Weighted: prev_window_count * overlap% + current_count
  Good balance of accuracy and efficiency.
```

**Code Example:**

```java
// Resilience4j Rate Limiter
RateLimiterConfig config = RateLimiterConfig.custom()
    .limitForPeriod(100)                    // 100 calls
    .limitRefreshPeriod(Duration.ofSeconds(1))  // per second
    .timeoutDuration(Duration.ofMillis(500))    // wait for permit
    .build();

RateLimiter rateLimiter = RateLimiter.of("apiGateway", config);

// Redis-based distributed rate limiting (sliding window)
public boolean isAllowed(String clientId, int maxRequests, int windowSeconds) {
    String key = "rate:" + clientId;
    long now = System.currentTimeMillis();
    long windowStart = now - (windowSeconds * 1000L);
    
    // Remove old entries, add current, count
    Pipeline pipe = redis.pipelined();
    pipe.zremrangeByScore(key, 0, windowStart);
    pipe.zadd(key, now, now + ":" + UUID.randomUUID());
    pipe.zcard(key);
    pipe.expire(key, windowSeconds);
    List<Object> results = pipe.syncAndReturnAll();
    
    long count = (Long) results.get(2);
    return count <= maxRequests;
}
```

**Configuration Parameters:**
| Parameter | Description |
|-----------|-------------|
| rate | Requests per time unit |
| burst | Max burst size (token bucket capacity) |
| window | Time window size |
| per-client vs global | Scope of limiting |

**Monitoring Considerations:**
- Track rejection rate by client/endpoint
- Alert on sudden spikes in rejected requests
- Monitor bucket fill levels
- Metrics: `rate_limiter_permitted`, `rate_limiter_rejected`

**When to Use:**
- API gateway (protect backend services)
- Per-tenant/user limits (fair use)
- External API calls (respect third-party rate limits)
- Write-heavy endpoints

---

### Fallback Pattern

**Problem:** Primary path fails and you need a degraded but functional response.

**How it Works:** When the primary operation fails, execute an alternative strategy.

**Fallback Strategies:**
```
┌──────────────────────────────────────────────┐
│           Fallback Chain                      │
│                                              │
│  1. Primary: Call live service                │
│       │ fails                                │
│       ▼                                      │
│  2. Cache: Return cached data                │
│       │ miss                                 │
│       ▼                                      │
│  3. Default: Return static default           │
│       │ not applicable                       │
│       ▼                                      │
│  4. Error: Return graceful error response    │
└──────────────────────────────────────────────┘
```

**Code Example:**

```java
@Service
public class ProductService {
    
    public ProductInfo getProductInfo(String productId) {
        try {
            // Primary: live service call
            return productClient.getProduct(productId);
        } catch (Exception e) {
            log.warn("Primary failed for product {}", productId, e);
        }
        
        // Fallback 1: Local cache
        ProductInfo cached = cache.get("product:" + productId);
        if (cached != null) {
            cached.setStale(true);
            return cached;
        }
        
        // Fallback 2: Default response
        return ProductInfo.builder()
            .id(productId)
            .name("Product Unavailable")
            .available(false)
            .message("Product details temporarily unavailable")
            .build();
    }
}
```

**When to Use:**
- Non-critical features (recommendations, personalization)
- Read operations with stale-but-acceptable data
- Combined with Circuit Breaker (fallback when circuit is open)

---

### Fail Fast Pattern

**Problem:** Wasting resources on requests that are doomed to fail.

**How it Works:** Detect failure conditions early and reject requests immediately without consuming resources.

**Code Example:**

```java
@Service
public class OrderService {
    
    public Order createOrder(CreateOrderRequest request) {
        // Fail fast checks
        if (!inventoryService.isHealthy()) {
            throw new ServiceUnavailableException(
                "Inventory service unavailable, cannot create orders");
        }
        
        if (circuitBreaker.getState() == State.OPEN) {
            throw new ServiceUnavailableException(
                "Payment service circuit is open");
        }
        
        // Proceed with order creation
        return processOrder(request);
    }
}
```

**When to Use:**
- Precondition checks before expensive operations
- Circuit breaker OPEN state
- Health check failures detected upfront
- Queue depth exceeded

---

### Steady State Pattern

**Problem:** Resources (logs, temp files, DB connections, cache) grow unbounded and eventually cause failure.

**How it Works:** Continuously clean up resources to maintain steady state. The system should run indefinitely without manual intervention.

**Implementation Areas:**
- Log rotation and retention policies
- Database connection pool limits
- Cache eviction (LRU, TTL)
- Dead letter queue processing
- Temp file cleanup
- Memory limits on queues

```java
// Example: Bounded queue that drops oldest
BlockingQueue<Event> queue = new ArrayBlockingQueue<>(10000);

// When full, remove oldest and add new
public void addEvent(Event event) {
    while (!queue.offer(event)) {
        Event dropped = queue.poll();
        metrics.increment("events_dropped");
        log.warn("Dropped event to maintain steady state: {}", dropped.getId());
    }
}
```

**When to Use:** Always. Every system should be designed for steady state operation.

---

### Handshaking Pattern

**Problem:** Server accepts more connections than it can handle, leading to degraded performance for all.

**How it Works:** During connection establishment, server communicates its capacity and health. Client adjusts behavior accordingly.

**Implementation:**
- HTTP response headers: `X-RateLimit-Remaining: 45`
- gRPC: return `RESOURCE_EXHAUSTED` status
- Health endpoint returns load factor
- TCP backpressure (stop reading from socket)

**When to Use:**
- Service-to-service communication where clients can adapt
- Load-aware routing
- Connection admission control

---

## Availability Patterns

### Health Check API

**Problem:** Orchestrators (Kubernetes) need to know if a service is alive and ready to serve traffic.

**How it Works:** Expose endpoints that indicate service health status.

**Liveness vs Readiness:**
```
LIVENESS PROBE: "Is the process alive?"
  - Failure → restart container
  - Check: process responding, not deadlocked
  - Should NOT check dependencies

READINESS PROBE: "Can it serve traffic?"
  - Failure → remove from load balancer
  - Check: dependencies connected, warm-up complete
  - Should check critical dependencies

STARTUP PROBE: "Has it finished starting?"
  - Failure → not yet ready, keep waiting
  - Prevents liveness kills during slow startup
```

**Code Example:**

```java
@RestController
@RequestMapping("/health")
public class HealthController {
    
    @GetMapping("/live")
    public ResponseEntity<Map<String, String>> liveness() {
        // Simple: is the app running?
        return ResponseEntity.ok(Map.of("status", "UP"));
    }
    
    @GetMapping("/ready")
    public ResponseEntity<Map<String, Object>> readiness() {
        Map<String, Object> checks = new HashMap<>();
        boolean ready = true;
        
        // Check database
        try {
            jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            checks.put("database", "UP");
        } catch (Exception e) {
            checks.put("database", "DOWN");
            ready = false;
        }
        
        // Check cache
        try {
            redis.ping();
            checks.put("cache", "UP");
        } catch (Exception e) {
            checks.put("cache", "DOWN");
            ready = false;
        }
        
        // Check message broker
        try {
            kafkaAdmin.describeCluster();
            checks.put("kafka", "UP");
        } catch (Exception e) {
            checks.put("kafka", "DOWN");
            ready = false;
        }
        
        checks.put("status", ready ? "UP" : "DOWN");
        return ready 
            ? ResponseEntity.ok(checks)
            : ResponseEntity.status(503).body(checks);
    }
}
```

**Kubernetes Configuration:**
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3

startupProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 0
  periodSeconds: 5
  failureThreshold: 30  # 30 * 5s = 150s max startup
```

**Monitoring Considerations:**
- Track health check response times
- Alert on sustained readiness failures
- Dashboard showing fleet health status

**When to Use:** Every service in a containerized/orchestrated environment.

---

### Heartbeat Mechanism

**Problem:** Need to detect unresponsive services that haven't explicitly failed.

**How it Works:** Services periodically send heartbeat signals. Missing heartbeats indicate failure.

```
┌─────────────┐   heartbeat every 5s   ┌──────────────┐
│  Service A  │ ──────────────────────► │   Monitor    │
│             │                         │   Service    │
└─────────────┘                         │              │
                                        │ If no beat   │
┌─────────────┐   heartbeat every 5s   │ for 15s →    │
│  Service B  │ ──────────────────────► │ mark dead    │
└─────────────┘                         └──────────────┘
```

**When to Use:**
- Service registry / discovery (Eureka, Consul)
- Leader election (ZooKeeper, etcd)
- Cluster membership management
- Long-running worker processes

---

### Watchdog Pattern

**Problem:** Background processes or scheduled jobs fail silently.

**How it Works:** An external watchdog monitors processes and takes corrective action (restart, alert) when they fail.

**Implementation:**
- Systemd watchdog for Linux processes
- Kubernetes liveness probes (watchdog behavior)
- External ping services (Healthchecks.io, PagerDuty)
- Dead man's switch: alert if NOT called within expected interval

**When to Use:**
- Cron jobs / batch processors
- Worker processes consuming queues
- Any long-running daemon

---

### Leaky Bucket Counter

**Problem:** Need to detect anomalous error rates while tolerating occasional errors.

**How it Works:** Errors fill a bucket. The bucket leaks at a fixed rate. Alert only when bucket overflows (sustained error rate exceeded).

```
Errors come in    ┌─────────────┐    Leaks at fixed rate
─────────────────►│   Bucket    │───────────────────────►
                  │   ████░░░░  │    (1 per second)
                  │   (4/8)     │
                  └─────────────┘
                       │
                  If full → ALERT
```

**When to Use:**
- Error rate monitoring without false positives from sporadic errors
- Connection attempt limiting
- Rate limiting (leaky bucket algorithm)

---

## Recovery Patterns

### Compensating Transaction

**Problem:** A multi-step business operation partially completes and needs to be undone.

**How it Works:** For each forward action, define a compensating action that semantically undoes it (not necessarily a database rollback).

**Example:**
```
Forward:                    Compensating:
1. Reserve inventory   →    Release inventory
2. Charge payment      →    Refund payment
3. Create shipment     →    Cancel shipment
4. Send confirmation   →    Send cancellation email
```

**Code Example:**

```java
public class BookingCompensation {
    
    private final Deque<Runnable> compensations = new ArrayDeque<>();
    
    public void execute() {
        try {
            // Step 1
            Reservation reservation = reservationService.reserve(flightId, seats);
            compensations.push(() -> reservationService.cancel(reservation.getId()));
            
            // Step 2
            Payment payment = paymentService.charge(customerId, amount);
            compensations.push(() -> paymentService.refund(payment.getId()));
            
            // Step 3
            Ticket ticket = ticketService.issue(reservation, payment);
            compensations.push(() -> ticketService.void(ticket.getId()));
            
            // Step 4
            notificationService.sendConfirmation(ticket);
            // No compensation needed (or send cancellation)
            
        } catch (Exception e) {
            // Execute compensations in reverse
            while (!compensations.isEmpty()) {
                try {
                    compensations.pop().run();
                } catch (Exception ce) {
                    log.error("Compensation failed", ce);
                    alertService.manualIntervention(ce);
                }
            }
            throw new BookingFailedException(e);
        }
    }
}
```

**When to Use:**
- Saga pattern compensation steps
- Distributed transactions without 2PC
- Any multi-step operation that needs rollback semantics

---

### Retry with Idempotency

**Problem:** Retries can cause duplicate side effects (double charge, duplicate orders).

**How it Works:** Assign a unique idempotency key to each operation. The server detects duplicates and returns the original result.

**Architecture:**
```
┌────────┐  POST /payments          ┌──────────────┐
│ Client │  Idempotency-Key: abc123 │   Service    │
│        │─────────────────────────►│              │
└────────┘                          │ 1. Check key │
                                    │ 2. If exists,│
     ┌─────────────────────────┐    │    return    │
     │   Idempotency Store     │    │    cached    │
     │   (Redis / DB table)    │◄───│ 3. If new,   │
     │                         │    │    process & │
     │  key: abc123            │    │    store     │
     │  status: completed      │    └──────────────┘
     │  response: {id: pay_1}  │
     └─────────────────────────┘
```

**Code Example:**

```java
@Service
public class PaymentService {
    @Autowired private IdempotencyStore idempotencyStore;
    
    public PaymentResult processPayment(String idempotencyKey, PaymentRequest request) {
        // Check for existing result
        Optional<PaymentResult> existing = idempotencyStore.get(idempotencyKey);
        if (existing.isPresent()) {
            return existing.get();  // Return cached result (no re-processing)
        }
        
        // Lock the key (prevent concurrent duplicates)
        if (!idempotencyStore.tryLock(idempotencyKey, Duration.ofMinutes(5))) {
            throw new ConflictException("Request already in progress");
        }
        
        try {
            PaymentResult result = executePayment(request);
            idempotencyStore.store(idempotencyKey, result, Duration.ofHours(24));
            return result;
        } catch (Exception e) {
            idempotencyStore.unlock(idempotencyKey);
            throw e;
        }
    }
}
```

**When to Use:**
- Payment processing
- Order creation
- Any state-changing operation that might be retried
- Webhook delivery

---

### Dead Letter Queue Processing

**Problem:** Messages that repeatedly fail processing block the queue or get lost.

**How it Works:** After N failed attempts, move the message to a Dead Letter Queue (DLQ) for investigation and reprocessing.

**Architecture:**
```
┌──────────┐     ┌─────────────┐     ┌──────────────┐
│ Producer │────►│ Main Queue  │────►│   Consumer   │
└──────────┘     └──────┬──────┘     └──────┬───────┘
                        │                    │
                        │                    │ fails 3x
                        │                    ▼
                        │            ┌──────────────┐
                        │            │     DLQ      │
                        │            │ (dead letter)│
                        │            └──────┬───────┘
                        │                   │
                        │                   ▼
                        │            ┌──────────────┐
                        │            │ DLQ Processor│
                        │            │ (manual/auto)│
                        │            └──────┬───────┘
                        │                   │ reprocess
                        │◄──────────────────┘
```

**Code Example:**

```java
// Kafka DLQ configuration
@Configuration
public class KafkaConfig {
    
    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, String> factory = 
            new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());
        factory.setCommonErrorHandler(new DefaultErrorHandler(
            new DeadLetterPublishingRecoverer(kafkaTemplate,
                (record, ex) -> new TopicPartition(
                    record.topic() + ".DLQ", record.partition())),
            new FixedBackOff(1000L, 3)  // 3 retries, 1s apart
        ));
        return factory;
    }
}

// DLQ Processor
@Service
public class DLQProcessor {
    
    @Scheduled(fixedDelay = 60000)  // every minute
    public void processDLQ() {
        List<ConsumerRecord<String, String>> dlqMessages = 
            consumer.poll("orders.DLQ", 10);
        
        for (ConsumerRecord<String, String> record : dlqMessages) {
            try {
                // Attempt reprocessing with fixes
                processWithFix(record);
                acknowledge(record);
            } catch (Exception e) {
                if (isRetryable(e)) {
                    // Leave in DLQ for next attempt
                } else {
                    // Move to permanent failure store
                    permanentFailureStore.save(record, e);
                    acknowledge(record);
                    alertOps(record, e);
                }
            }
        }
    }
}
```

**When to Use:**
- Message queue consumers
- Event-driven architectures
- Any async processing with potential permanent failures

---

### Circuit Breaker with Fallback Chain

**Problem:** Need multiple levels of degradation when services fail.

**How it Works:** Chain multiple fallback strategies with decreasing quality.

```java
public ProductRecommendations getRecommendations(String userId) {
    // Level 1: Real-time ML recommendations
    return circuitBreaker("ml-service", () -> mlService.getPersonalized(userId))
        // Level 2: Pre-computed recommendations from cache
        .recover(e -> circuitBreaker("rec-cache", () -> cache.get("recs:" + userId)))
        // Level 3: Popular items (generic)
        .recover(e -> circuitBreaker("popular-items", () -> popularItemsService.getTop(10)))
        // Level 4: Static fallback
        .recover(e -> ProductRecommendations.STATIC_DEFAULT)
        .get();
}
```

---

### Graceful Degradation

**Problem:** When system is under stress, maintaining full functionality leads to complete failure.

**How it Works:** Progressively disable non-critical features to preserve core functionality.

**Degradation Levels:**
```
Level 0 (Normal):    All features operational
Level 1 (Warning):   Disable recommendations, analytics tracking
Level 2 (Degraded):  Serve cached content, disable search suggestions
Level 3 (Critical):  Read-only mode, static pages
Level 4 (Survival):  Maintenance page with status
```

**Implementation:**

```java
@Service
public class FeatureFlagService {
    private volatile DegradationLevel currentLevel = DegradationLevel.NORMAL;
    
    public boolean isEnabled(Feature feature) {
        return feature.getMinimumLevel().ordinal() >= currentLevel.ordinal();
    }
    
    // Auto-adjust based on system metrics
    @Scheduled(fixedRate = 10000)
    public void evaluateSystemHealth() {
        double errorRate = metrics.getErrorRate();
        double latencyP99 = metrics.getLatencyP99();
        double cpuUsage = metrics.getCpuUsage();
        
        if (errorRate > 0.5 || cpuUsage > 0.95) {
            currentLevel = DegradationLevel.CRITICAL;
        } else if (errorRate > 0.2 || latencyP99 > 5000) {
            currentLevel = DegradationLevel.DEGRADED;
        } else if (errorRate > 0.05 || latencyP99 > 2000) {
            currentLevel = DegradationLevel.WARNING;
        } else {
            currentLevel = DegradationLevel.NORMAL;
        }
    }
}
```

**When to Use:**
- E-commerce during flash sales
- Social media during viral events
- Any system with clearly tiered feature importance

---

## Load Management

### Load Shedding

**Problem:** System receives more load than it can handle. Attempting to serve everything degrades quality for all.

**How it Works:** Reject excess requests early (preferably at the edge) to protect the system and maintain quality for accepted requests.

**Architecture:**
```
Incoming requests (1000 RPS)
         │
         ▼
┌─────────────────────┐
│   Load Shedder      │
│   Capacity: 500 RPS │
│                     │
│   ██████████░░░░░░  │──── 500 rejected (HTTP 503)
│   (500 accepted)    │     with Retry-After header
└─────────┬───────────┘
          │
          ▼ 500 RPS
┌─────────────────────┐
│   Service (healthy) │
└─────────────────────┘
```

**Strategies:**
- Random rejection (simplest)
- Priority-based (shed low-priority first)
- Client-based (protect premium clients)
- Endpoint-based (protect critical paths)

**Code Example:**

```java
@Component
public class LoadSheddingFilter implements Filter {
    private final Semaphore permits = new Semaphore(500);
    
    @Override
    public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain) 
            throws IOException, ServletException {
        if (!permits.tryAcquire()) {
            HttpServletResponse httpResp = (HttpServletResponse) resp;
            httpResp.setStatus(503);
            httpResp.setHeader("Retry-After", "5");
            httpResp.getWriter().write("{\"error\": \"Service overloaded\"}");
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

**When to Use:**
- API gateways
- During traffic spikes
- Protect critical system resources

---

### Load Leveling (Queue-Based)

**Problem:** Traffic is bursty but the backend can only handle a steady rate.

**How it Works:** Buffer requests in a queue and process them at a steady rate.

**Architecture:**
```
Bursty traffic:  ████ ████   ██   ████████
                    │
                    ▼
         ┌────────────────────┐
         │    Message Queue   │  (buffer)
         │    ████████████    │
         └─────────┬──────────┘
                   │
                   ▼ steady rate
         ┌────────────────────┐
         │   Worker Service   │
         │   (constant rate)  │
         └────────────────────┘
         
Processed: ████ ████ ████ ████  (smoothed)
```

**When to Use:**
- Async workloads (email sending, report generation)
- Spiky traffic patterns
- Backend with fixed processing capacity

---

### Backpressure

**Problem:** Producer is faster than consumer, causing unbounded resource growth.

**How it Works:** Consumer signals to producer to slow down. Information flows backward through the pipeline.

**Mechanisms:**
1. **Blocking** — producer blocks when buffer is full
2. **Dropping** — drop messages when overwhelmed (newest or oldest)
3. **Flow control** — consumer requests N items (reactive streams)
4. **HTTP 429** — explicit "slow down" signal

**Code Example (Reactive Streams):**

```java
// Reactor / Project Reactor backpressure
Flux.create(sink -> {
    // Producer: emits as fast as possible
    for (int i = 0; i < 1_000_000; i++) {
        sink.next(generateEvent(i));
    }
    sink.complete();
}, FluxSink.OverflowStrategy.BUFFER)  // or DROP, LATEST, ERROR
.onBackpressureBuffer(1000, 
    dropped -> log.warn("Dropped: {}", dropped),
    BufferOverflowStrategy.DROP_OLDEST)
.publishOn(Schedulers.boundedElastic(), 100)  // prefetch 100
.subscribe(event -> processSlowly(event));
```

**When to Use:**
- Stream processing pipelines
- Reactive systems
- Producer-consumer patterns with rate mismatch

---

### Throttling

**Problem:** Need to protect downstream services from being overwhelmed by our requests.

**How it Works:** Self-imposed rate limiting on outgoing requests.

**Implementation:**

```java
// Outgoing request throttle
@Service
public class ExternalApiClient {
    private final RateLimiter rateLimiter = RateLimiter.create(10.0); // 10 req/s (Guava)
    
    public ApiResponse callExternalApi(ApiRequest request) {
        rateLimiter.acquire(); // blocks until permitted
        return httpClient.post(externalUrl, request);
    }
}
```

**When to Use:**
- Calling third-party APIs with rate limits
- Protecting downstream internal services
- Batch processing that shouldn't overwhelm systems

---

### Priority Queue

**Problem:** All requests treated equally, but some are more important (premium users, critical operations).

**How it Works:** Assign priorities and process higher-priority items first.

```
┌─────────────────────────────────────┐
│          Priority Queue              │
│                                     │
│  HIGH:    ██████    (processed first)│
│  MEDIUM:  ████████████              │
│  LOW:     ██████████████████        │
└─────────────────────────────────────┘
```

**When to Use:**
- Multi-tenant systems (premium vs free tier)
- Mixed workloads (real-time vs batch)
- SLA-differentiated services

---

### Competing Consumers

**Problem:** Single consumer can't keep up with message production rate.

**How it Works:** Multiple consumer instances process from the same queue in parallel.

**Architecture:**
```
┌──────────┐     ┌─────────────┐     ┌────────────┐
│ Producer │────►│   Queue     │────►│ Consumer 1 │
└──────────┘     │             │────►│ Consumer 2 │
                 │  ████████   │────►│ Consumer 3 │
                 └─────────────┘     └────────────┘
```

**Key Considerations:**
- Message ordering may not be preserved
- Use partition keys for ordering within entity
- Ensure idempotent processing
- Scale consumers based on queue depth

**When to Use:**
- High-throughput event processing
- Work that can be parallelized
- Auto-scaling based on queue backlog

---

## Chaos Engineering

### Principles of Chaos Engineering

**Problem:** You don't know how your system behaves under failure conditions until it actually fails in production.

**How it Works:** Deliberately inject failures in controlled experiments to discover weaknesses before they cause outages.

**The Chaos Engineering Loop:**
```
┌────────────────────────────────────────────────────┐
│                                                    │
│   1. Define steady state (normal behavior)         │
│              │                                     │
│              ▼                                     │
│   2. Hypothesize: "System will remain in steady    │
│      state when X fails"                           │
│              │                                     │
│              ▼                                     │
│   3. Inject failure (controlled blast radius)      │
│              │                                     │
│              ▼                                     │
│   4. Observe: Did steady state hold?               │
│              │                                     │
│         ┌────┴────┐                                │
│         │         │                                │
│        YES       NO → Fix the weakness             │
│         │         │                                │
│         ▼         ▼                                │
│   5. Increase scope / try next experiment          │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Principles:**
1. Build a hypothesis around steady state behavior
2. Vary real-world events (server failure, network partition, disk full)
3. Run experiments in production
4. Automate experiments to run continuously
5. Minimize blast radius

---

### Fault Injection Testing

**Types of Faults to Inject:**

| Fault Type | Examples |
|-----------|----------|
| Infrastructure | Kill VM, fill disk, exhaust CPU |
| Network | Latency injection, packet loss, partition |
| Application | Exception injection, memory leak, thread deadlock |
| Dependency | Kill downstream service, slow response, error response |
| Data | Corrupt data, stale cache, clock skew |

---

### Tools

| Tool | Type | Scope |
|------|------|-------|
| **Chaos Monkey** | Random instance termination | AWS/Netflix |
| **Litmus** | Kubernetes-native chaos | K8s pods, nodes, network |
| **Gremlin** | Enterprise chaos platform | Infrastructure, app, network |
| **Chaos Mesh** | K8s chaos engineering | Pods, network, I/O, time |
| **AWS FIS** | Managed fault injection | AWS resources |
| **Toxiproxy** | Network-level fault injection | TCP connections |

**Litmus Example:**
```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: order-service-chaos
spec:
  appinfo:
    appns: production
    applabel: app=order-service
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "30"
            - name: CHAOS_INTERVAL
              value: "10"
            - name: FORCE
              value: "false"
```

---

### Game Days

**What:** Scheduled chaos engineering exercises where teams simulate major failures and practice incident response.

**Structure:**
1. **Planning** — define scenario, scope, success criteria
2. **Communication** — inform stakeholders, set up war room
3. **Execution** — inject failure, observe
4. **Response** — team responds as if real incident
5. **Debrief** — what worked, what didn't, action items

**Common Game Day Scenarios:**
- Primary database failover
- Entire availability zone failure
- DNS outage
- Third-party payment provider down
- DDoS simulation

---

### Blast Radius Containment

**Problem:** Chaos experiments must not cause real outages.

**Strategies:**
1. Start in staging/pre-prod
2. Use feature flags to limit scope
3. Target single instances first, then expand
4. Have kill switch to immediately stop experiment
5. Run during business hours with team present
6. Monitor closely and abort if SLOs breached

---

## Libraries and Frameworks

### Resilience4j (Java)

**Overview:** Lightweight, modular fault tolerance library for Java 8+. Successor to Hystrix.

**Modules:**
| Module | Purpose |
|--------|---------|
| CircuitBreaker | Prevent cascading failures |
| RateLimiter | Limit call rate |
| Retry | Retry failed operations |
| Bulkhead | Limit concurrent calls |
| TimeLimiter | Set time limits |
| Cache | Memoize results |

**Composition (decorating calls):**

```java
// Compose multiple patterns
Supplier<String> decoratedSupplier = Decorators.ofSupplier(
    () -> backendService.doSomething())
    .withRetry(retry)
    .withCircuitBreaker(circuitBreaker)
    .withBulkhead(bulkhead)
    .withTimeLimiter(timeLimiter, scheduledExecutor)
    .withFallback(asList(TimeoutException.class, CallNotPermittedException.class),
        throwable -> "Fallback response")
    .decorate();

// Spring Boot integration
@CircuitBreaker(name = "backendA", fallbackMethod = "fallback")
@Retry(name = "backendA")
@Bulkhead(name = "backendA")
public String callService() {
    return restTemplate.getForObject("/api/data", String.class);
}

private String fallback(Exception e) {
    return "Fallback response";
}
```

**Configuration (application.yml):**
```yaml
resilience4j:
  circuitbreaker:
    instances:
      backendA:
        slidingWindowSize: 100
        failureRateThreshold: 50
        waitDurationInOpenState: 60000
        permittedNumberOfCallsInHalfOpenState: 10
  retry:
    instances:
      backendA:
        maxAttempts: 3
        waitDuration: 500ms
        exponentialBackoffMultiplier: 2
  bulkhead:
    instances:
      backendA:
        maxConcurrentCalls: 25
        maxWaitDuration: 500ms
```

---

### Polly (.NET)

**Overview:** .NET resilience and transient-fault-handling library.

**Policies:**

```csharp
// Retry with exponential backoff
var retryPolicy = Policy
    .Handle<HttpRequestException>()
    .Or<TimeoutException>()
    .WaitAndRetryAsync(
        retryCount: 3,
        sleepDurationProvider: attempt => 
            TimeSpan.FromSeconds(Math.Pow(2, attempt)) 
            + TimeSpan.FromMilliseconds(Random.Shared.Next(0, 1000)),
        onRetry: (exception, timespan, retryCount, context) =>
            logger.LogWarning("Retry {RetryCount} after {Delay}ms", retryCount, timespan.TotalMilliseconds)
    );

// Circuit Breaker
var circuitBreakerPolicy = Policy
    .Handle<HttpRequestException>()
    .CircuitBreakerAsync(
        exceptionsAllowedBeforeBreaking: 5,
        durationOfBreak: TimeSpan.FromSeconds(30),
        onBreak: (ex, duration) => logger.LogError("Circuit OPEN for {Duration}s", duration.TotalSeconds),
        onReset: () => logger.LogInformation("Circuit CLOSED"),
        onHalfOpen: () => logger.LogInformation("Circuit HALF-OPEN")
    );

// Bulkhead
var bulkheadPolicy = Policy.BulkheadAsync(
    maxParallelization: 10,
    maxQueuingActions: 20,
    onBulkheadRejectedAsync: context => {
        logger.LogWarning("Bulkhead rejected");
        return Task.CompletedTask;
    }
);

// Wrap policies (executed outer to inner)
var policyWrap = Policy.WrapAsync(
    bulkheadPolicy, 
    circuitBreakerPolicy, 
    retryPolicy
);

// Usage with HttpClientFactory
services.AddHttpClient("OrderService")
    .AddPolicyHandler(retryPolicy)
    .AddPolicyHandler(circuitBreakerPolicy);
```

---

### Hystrix (Deprecated but Conceptually Important)

**Overview:** Netflix's original circuit breaker library. Deprecated in favor of Resilience4j, but introduced many core concepts.

**Key Concepts Introduced:**
- Command pattern for wrapping calls
- Thread pool isolation (bulkhead)
- Request collapsing (batching)
- Request caching
- Real-time metrics streaming (Hystrix Dashboard)
- Fallback mechanism

**Architecture Contribution:**
```
Request → HystrixCommand → Thread Pool → Remote Call
              │                               │
              │ timeout/failure                │
              ▼                               │
          Fallback                            │
              │                               │
              ▼                               ▼
          Response ◄──────────────────────────┘
```

**Why Deprecated:**
- Blocking thread model doesn't suit reactive architectures
- Heavy runtime overhead
- Resilience4j is lighter, more modular, supports functional style

**Legacy Impact:** Hystrix Dashboard concept lives on in Resilience4j metrics + Grafana.

---

### Sentinel (Alibaba)

**Overview:** Flow control, circuit breaking, and system adaptive protection for distributed systems. Popular in Chinese tech ecosystem.

**Key Features:**
| Feature | Description |
|---------|-------------|
| Flow control | QPS limiting, thread count limiting, warm-up |
| Circuit breaking | Slow request ratio, error ratio, error count |
| System adaptive | CPU usage, system load, RT-based |
| Hot parameter limiting | Rate limit specific parameter values |
| Cluster flow control | Distributed rate limiting |

**Configuration:**

```java
// Flow rule
FlowRule rule = new FlowRule();
rule.setResource("orderService");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(100);  // 100 QPS
rule.setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_WARM_UP);
rule.setWarmUpPeriodSec(10);
FlowRuleManager.loadRules(Collections.singletonList(rule));

// Degrade (circuit breaker) rule
DegradeRule degradeRule = new DegradeRule();
degradeRule.setResource("paymentService");
degradeRule.setGrade(CircuitBreakerStrategy.SLOW_REQUEST_RATIO.getType());
degradeRule.setCount(0.5);  // 50% slow requests triggers break
degradeRule.setSlowRatioThreshold(0.5);
degradeRule.setMinRequestAmount(10);
degradeRule.setTimeWindow(30);  // 30s recovery window
DegradeRuleManager.loadRules(Collections.singletonList(degradeRule));

// Usage with annotation
@SentinelResource(value = "getOrder", 
    blockHandler = "getOrderBlock",
    fallback = "getOrderFallback")
public Order getOrder(String orderId) {
    return orderClient.getOrder(orderId);
}
```

**Comparison Table:**

| Feature | Resilience4j | Polly | Hystrix | Sentinel |
|---------|-------------|-------|---------|----------|
| Language | Java | .NET | Java | Java |
| Circuit Breaker | Yes | Yes | Yes | Yes |
| Rate Limiting | Yes | Yes | No | Yes (advanced) |
| Bulkhead | Yes | Yes | Yes (thread) | Yes (thread count) |
| Retry | Yes | Yes | No | No |
| Reactive support | Yes | No | No | Limited |
| Dashboard | Via metrics | No | Yes | Yes (rich) |
| Cluster support | No | No | No | Yes |
| Active | Yes | Yes | No (deprecated) | Yes |
| Lightweight | Yes | Yes | No | Medium |
