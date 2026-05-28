# Concurrency Issues - Problems and Solutions

## Table of Contents
- [Race Conditions](#race-conditions)
- [Deadlocks](#deadlocks)
- [Thread Safety in Spring Beans](#thread-safety-in-spring-beans)
- [Concurrent Data Access](#concurrent-data-access)
- [Database Concurrency](#database-concurrency)
- [Distributed Concurrency](#distributed-concurrency)
- [Atomic Operations](#atomic-operations)
- [Reactive Concurrency Patterns](#reactive-concurrency-patterns)

---

## Race Conditions

### Q1: What is a race condition in Spring Boot and how do you identify it?

**Answer:**

A race condition occurs when multiple threads access shared mutable state without proper synchronization, and the outcome depends on the timing of thread execution.

```java
// CLASSIC RACE CONDITION in Spring Boot
@Service
public class AccountService {
    
    @Autowired
    private AccountRepository accountRepository;
    
    // This is NOT thread-safe!
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        Account from = accountRepository.findById(fromId).orElseThrow();
        Account to = accountRepository.findById(toId).orElseThrow();
        
        // Thread A reads balance: $1000
        // Thread B reads balance: $1000 (SAME value!)
        
        if (from.getBalance().compareTo(amount) >= 0) {
            from.setBalance(from.getBalance().subtract(amount));  // Thread A: $1000 - $800 = $200
            to.setBalance(to.getBalance().add(amount));
            
            // Thread B: $1000 - $800 = $200 (should be $200 - $800 = FAIL!)
            accountRepository.save(from);
            accountRepository.save(to);
        }
    }
}

// Result: Two $800 transfers succeed from a $1000 account!
// Lost update problem: both threads read stale data
```

**Solutions:**

```java
// Solution 1: Optimistic Locking (PREFERRED for most cases)
@Entity
public class Account {
    @Id
    private Long id;
    
    @Version  // JPA Optimistic Lock
    private Long version;
    
    private BigDecimal balance;
}

@Service
public class AccountService {
    @Retryable(value = OptimisticLockingFailureException.class, maxAttempts = 3)
    @Transactional
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        Account from = accountRepository.findById(fromId).orElseThrow();
        Account to = accountRepository.findById(toId).orElseThrow();
        
        if (from.getBalance().compareTo(amount) >= 0) {
            from.setBalance(from.getBalance().subtract(amount));
            to.setBalance(to.getBalance().add(amount));
            // If version mismatch → OptimisticLockingFailureException → retry
        }
    }
}

// Solution 2: Pessimistic Locking
public interface AccountRepository extends JpaRepository<Account, Long> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT a FROM Account a WHERE a.id = :id")
    Optional<Account> findByIdForUpdate(@Param("id") Long id);
}

// Solution 3: Database-level atomic update
@Modifying
@Query("UPDATE Account a SET a.balance = a.balance - :amount WHERE a.id = :id AND a.balance >= :amount")
int debitAccount(@Param("id") Long id, @Param("amount") BigDecimal amount);
// Returns 0 if insufficient balance (atomic check-and-update)

// Solution 4: Serializable transaction isolation
@Transactional(isolation = Isolation.SERIALIZABLE)
public void transfer(Long fromId, Long toId, BigDecimal amount) {
    // Fully serialized - prevents all concurrency anomalies
    // But SEVERELY impacts throughput
}
```

### Q2: Race condition in Singleton beans

```java
// DANGEROUS: Mutable state in a singleton bean
@Service // Singleton scope by default!
public class RequestCounter {
    private int count = 0;  // SHARED MUTABLE STATE
    
    public void increment() {
        count++;  // NOT ATOMIC: read → increment → write
        // Thread A reads 5, Thread B reads 5
        // Thread A writes 6, Thread B writes 6
        // Expected: 7, Actual: 6 (lost update)
    }
}

// Solution 1: AtomicInteger
@Service
public class RequestCounter {
    private final AtomicInteger count = new AtomicInteger(0);
    
    public void increment() {
        count.incrementAndGet();  // Atomic CAS operation
    }
}

// Solution 2: Use proper concurrent collections
@Service
public class UserSessionManager {
    // WRONG
    private Map<String, Session> sessions = new HashMap<>(); // NOT thread-safe
    
    // CORRECT
    private final ConcurrentHashMap<String, Session> sessions = new ConcurrentHashMap<>();
}

// Solution 3: Don't have mutable state in singletons (BEST)
@Service
public class StatelessService {
    // All state is in method parameters or local variables
    // Methods use injected stateless dependencies
    
    public Result process(Input input) {
        // Local variables are thread-safe (each thread has own stack)
        var intermediate = transform(input);
        return buildResult(intermediate);
    }
}
```

---

## Deadlocks

### Q3: How do deadlocks happen in Spring Boot applications?

**Answer:**

```java
// Classic deadlock: Two threads, two locks, opposite order
@Service
public class TransferService {
    
    @Transactional
    public void transferAtoB() {
        Account a = accountRepo.findByIdForUpdate(1L); // Lock row A
        Thread.sleep(100); // Simulates processing delay
        Account b = accountRepo.findByIdForUpdate(2L); // Wait for lock on B
        // DEADLOCK if transferBtoA is running simultaneously!
    }
    
    @Transactional
    public void transferBtoA() {
        Account b = accountRepo.findByIdForUpdate(2L); // Lock row B
        Thread.sleep(100);
        Account a = accountRepo.findByIdForUpdate(1L); // Wait for lock on A
        // Thread 1 holds A, waits for B
        // Thread 2 holds B, waits for A → DEADLOCK!
    }
}
```

**Solution: Consistent lock ordering**

```java
@Service
public class TransferService {
    
    @Transactional
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        // ALWAYS lock in consistent order (e.g., by ID)
        Long firstLock = Math.min(fromId, toId);
        Long secondLock = Math.max(fromId, toId);
        
        Account first = accountRepo.findByIdForUpdate(firstLock);
        Account second = accountRepo.findByIdForUpdate(secondLock);
        
        // Now process transfer
        Account from = fromId.equals(firstLock) ? first : second;
        Account to = toId.equals(firstLock) ? first : second;
        
        from.setBalance(from.getBalance().subtract(amount));
        to.setBalance(to.getBalance().add(amount));
    }
}
```

### Q4: Spring `@Transactional` deadlock with nested calls

```java
// DEADLOCK scenario with Spring proxies
@Service
public class OrderService {
    @Autowired private InventoryService inventoryService;
    @Autowired private PaymentService paymentService;
    
    @Transactional
    public void placeOrder(Order order) {
        // Transaction 1 starts, acquires locks on ORDER table
        orderRepo.save(order);
        
        // Calls InventoryService which has its OWN transaction
        inventoryService.reserve(order.getItems()); // New TX, locks INVENTORY
        
        // If another thread does: inventory.restock() which locks INVENTORY then ORDER
        // → DEADLOCK
    }
}

@Service
public class InventoryService {
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void reserve(List<Item> items) {
        // NEW transaction → different connection → different locks
        // Can deadlock with parent transaction
    }
    
    @Transactional
    public void restock(Item item) {
        inventoryRepo.lock(item); // Lock INVENTORY
        orderRepo.updateQuantities(item); // Try to lock ORDER → DEADLOCK!
    }
}
```

**Solutions:**
```java
// 1. Use REQUIRED propagation (same transaction, same connection)
@Transactional(propagation = Propagation.REQUIRED) // default
public void reserve(List<Item> items) { }

// 2. Set lock timeout
@QueryHints(@QueryHint(name = "javax.persistence.lock.timeout", value = "3000"))
@Lock(LockModeType.PESSIMISTIC_WRITE)
Optional<Account> findByIdForUpdate(Long id);

// 3. Deadlock detection and retry
@Retryable(value = {DeadlockLoserDataAccessException.class}, maxAttempts = 3, backoff = @Backoff(delay = 100))
@Transactional
public void transfer(Long fromId, Long toId, BigDecimal amount) {
    // If deadlock detected by DB, retry
}
```

---

## Thread Safety in Spring Beans

### Q5: Which Spring scopes are thread-safe?

**Answer:**

| Scope | Thread-Safe? | Why |
|-------|-------------|-----|
| Singleton (default) | NO (if mutable state) | One instance, many threads |
| Prototype | YES (typically) | New instance per injection |
| Request | YES | One instance per HTTP request (one thread) |
| Session | MAYBE | One per session, but sessions can have concurrent requests |
| Application | NO (same as singleton) | One instance for entire app |
| WebSocket | MAYBE | One per WebSocket session |

```java
// PATTERNS FOR THREAD-SAFE SINGLETONS

// Pattern 1: Stateless beans (PREFERRED)
@Service
public class CalculationService {
    // No mutable fields - inherently thread-safe
    private final FormulaEngine engine; // immutable dependency
    
    public BigDecimal calculate(Input input) {
        return engine.compute(input); // All state in parameters
    }
}

// Pattern 2: Thread-local state
@Service
public class RequestScopedData {
    // When you need per-request state in a singleton
    private final ThreadLocal<RequestContext> context = new ThreadLocal<>();
    
    public void setContext(RequestContext ctx) {
        context.set(ctx);
    }
    
    public RequestContext getContext() {
        return context.get();
    }
    
    public void clear() {
        context.remove(); // MUST clean up to prevent memory leaks!
    }
}

// Pattern 3: Immutable shared state
@Service
public class ConfigService {
    private final ImmutableMap<String, String> config; // Immutable collection
    
    public ConfigService(@Value("#{${app.config}}") Map<String, String> config) {
        this.config = ImmutableMap.copyOf(config); // Thread-safe: immutable
    }
}

// Pattern 4: Request-scoped bean for mutable request state
@Component
@Scope(value = WebApplicationContext.SCOPE_REQUEST, proxyMode = ScopedProxyMode.TARGET_CLASS)
public class RequestContext {
    private String userId;
    private Instant startTime;
    // Thread-safe because one instance per request
}
```

### Q6: How does Spring's `@Async` affect thread safety?

```java
@Service
public class NotificationService {
    
    // DANGER: shared mutable state accessed from @Async methods
    private List<String> sentNotifications = new ArrayList<>(); // NOT THREAD-SAFE
    
    @Async
    public CompletableFuture<Void> sendEmail(String to, String message) {
        // Runs on a DIFFERENT thread than the caller!
        emailSender.send(to, message);
        sentNotifications.add(to); // RACE CONDITION!
        return CompletableFuture.completedFuture(null);
    }
}

// SOLUTION
@Service
public class NotificationService {
    private final ConcurrentLinkedQueue<String> sentNotifications = new ConcurrentLinkedQueue<>();
    
    @Async("notificationExecutor")
    public CompletableFuture<Void> sendEmail(String to, String message) {
        emailSender.send(to, message);
        sentNotifications.add(to); // Thread-safe
        return CompletableFuture.completedFuture(null);
    }
}

// Configure the async executor
@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean("notificationExecutor")
    public Executor notificationExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("notif-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
}
```

---

## Concurrent Data Access

### Q7: How to handle concurrent cache updates?

```java
// Problem: Cache stampede (thundering herd)
@Service
public class ProductService {
    @Autowired private Cache cache;
    @Autowired private ProductRepository repo;
    
    // PROBLEM: 1000 threads hit this simultaneously when cache expires
    public Product getProduct(Long id) {
        Product cached = cache.get(id, Product.class);
        if (cached == null) {
            // ALL 1000 threads execute this DB query!
            Product product = repo.findById(id).orElseThrow();
            cache.put(id, product);
            return product;
        }
        return cached;
    }
}

// Solution 1: @Cacheable with sync=true
@Service
public class ProductService {
    @Cacheable(value = "products", key = "#id", sync = true)
    public Product getProduct(Long id) {
        // Only ONE thread executes this if cache miss
        // Others wait for the result
        return repo.findById(id).orElseThrow();
    }
}

// Solution 2: Manual locking per key
@Service
public class ProductService {
    private final ConcurrentHashMap<Long, ReentrantLock> locks = new ConcurrentHashMap<>();
    
    public Product getProduct(Long id) {
        Product cached = cache.get(id, Product.class);
        if (cached != null) return cached;
        
        ReentrantLock lock = locks.computeIfAbsent(id, k -> new ReentrantLock());
        lock.lock();
        try {
            // Double-check after acquiring lock
            cached = cache.get(id, Product.class);
            if (cached != null) return cached;
            
            Product product = repo.findById(id).orElseThrow();
            cache.put(id, product);
            return product;
        } finally {
            lock.unlock();
        }
    }
}

// Solution 3: Probabilistic early expiration
@Service
public class ProductService {
    public Product getProduct(Long id) {
        CacheEntry entry = cache.getEntry(id);
        if (entry != null) {
            // Probabilistically refresh before expiry
            double probability = Math.exp(-entry.getTimeToExpiry() / BETA);
            if (Math.random() < probability) {
                refreshAsync(id); // Background refresh
            }
            return entry.getValue();
        }
        return fetchAndCache(id);
    }
}
```

### Q8: Double-checked locking in Spring

```java
// Classic double-checked locking (CORRECT in Java 5+ with volatile)
@Component
public class ExpensiveResourceHolder {
    private volatile ExpensiveResource resource; // MUST be volatile!
    
    public ExpensiveResource getResource() {
        ExpensiveResource local = resource; // Read volatile once
        if (local == null) {
            synchronized (this) {
                local = resource;
                if (local == null) {
                    resource = local = createExpensiveResource();
                }
            }
        }
        return local;
    }
}

// Better: Use supplier-based lazy initialization
@Component
public class LazyResourceHolder {
    private final Supplier<ExpensiveResource> resource = 
        Suppliers.memoize(this::createExpensiveResource); // Guava
    
    public ExpensiveResource getResource() {
        return resource.get(); // Thread-safe, lazy, cached
    }
}
```

---

## Database Concurrency

### Q9: Explain transaction isolation levels and their concurrency trade-offs

```
┌──────────────────┬──────────────┬──────────────────┬──────────────┬──────────────┐
│ Isolation Level  │ Dirty Read   │ Non-Repeatable   │ Phantom Read │ Performance  │
│                  │              │ Read             │              │              │
├──────────────────┼──────────────┼──────────────────┼──────────────┼──────────────┤
│ READ_UNCOMMITTED │ Possible     │ Possible         │ Possible     │ Highest      │
│ READ_COMMITTED   │ Prevented    │ Possible         │ Possible     │ High         │
│ REPEATABLE_READ  │ Prevented    │ Prevented        │ Possible     │ Medium       │
│ SERIALIZABLE     │ Prevented    │ Prevented        │ Prevented    │ Lowest       │
└──────────────────┴──────────────┴──────────────────┴──────────────┴──────────────┘

Default in PostgreSQL: READ_COMMITTED
Default in MySQL InnoDB: REPEATABLE_READ
Default in Spring: Database default (usually READ_COMMITTED)
```

```java
// Setting isolation level
@Transactional(isolation = Isolation.REPEATABLE_READ)
public void processOrder(Long orderId) {
    // Within this transaction, same query returns same results
    Order order = orderRepo.findById(orderId);
    // ... even if other transactions modify data
    Order sameOrder = orderRepo.findById(orderId); // Same result!
}

// Common problem: Lost Update
// Thread A: reads balance = 100
// Thread B: reads balance = 100
// Thread A: writes balance = 100 + 50 = 150
// Thread B: writes balance = 100 + 30 = 130 (Thread A's update LOST!)

// Solution: SELECT FOR UPDATE (pessimistic locking)
@Query("SELECT a FROM Account a WHERE a.id = :id")
@Lock(LockModeType.PESSIMISTIC_WRITE)
Account findAndLock(@Param("id") Long id);
// Blocks Thread B until Thread A commits
```

### Q10: How to handle concurrent insert/upsert operations?

```java
// Problem: Two threads try to create the same resource
@Service
public class UserService {
    
    @Transactional
    public User getOrCreate(String email) {
        Optional<User> existing = userRepo.findByEmail(email);
        if (existing.isEmpty()) {
            // RACE: Both threads see empty, both try to insert!
            return userRepo.save(new User(email)); // DataIntegrityViolationException!
        }
        return existing.get();
    }
}

// Solution 1: Unique constraint + retry
@Service
public class UserService {
    @Retryable(value = DataIntegrityViolationException.class, maxAttempts = 2)
    @Transactional
    public User getOrCreate(String email) {
        return userRepo.findByEmail(email)
            .orElseGet(() -> userRepo.save(new User(email)));
    }
    
    @Recover
    public User getOrCreateRecover(DataIntegrityViolationException e, String email) {
        return userRepo.findByEmail(email).orElseThrow();
    }
}

// Solution 2: Database UPSERT (INSERT ON CONFLICT)
@Modifying
@Query(value = "INSERT INTO users (email, name) VALUES (:email, :name) " +
       "ON CONFLICT (email) DO UPDATE SET name = :name RETURNING *", nativeQuery = true)
User upsert(@Param("email") String email, @Param("name") String name);

// Solution 3: Distributed lock (for distributed systems)
public User getOrCreate(String email) {
    String lockKey = "user:create:" + email;
    return distributedLock.executeWithLock(lockKey, Duration.ofSeconds(5), () -> {
        return userRepo.findByEmail(email)
            .orElseGet(() -> userRepo.save(new User(email)));
    });
}
```

---

## Distributed Concurrency

### Q11: How to implement distributed locking in Spring Boot?

**Answer:**

```java
// Solution 1: Redis-based distributed lock (Redisson)
@Service
public class DistributedLockService {
    @Autowired private RedissonClient redisson;
    
    public <T> T executeWithLock(String lockKey, Duration timeout, Supplier<T> task) {
        RLock lock = redisson.getLock(lockKey);
        boolean acquired = false;
        try {
            acquired = lock.tryLock(timeout.toMillis(), timeout.toMillis(), TimeUnit.MILLISECONDS);
            if (!acquired) {
                throw new LockAcquisitionException("Could not acquire lock: " + lockKey);
            }
            return task.get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Lock interrupted", e);
        } finally {
            if (acquired && lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}

// Usage
@Service
public class OrderService {
    @Autowired private DistributedLockService lockService;
    
    public void processOrder(String orderId) {
        lockService.executeWithLock(
            "order:" + orderId,
            Duration.ofSeconds(30),
            () -> {
                // Only one instance processes this order
                return doProcessOrder(orderId);
            }
        );
    }
}

// Solution 2: Database-based lock (for simpler setups)
@Entity
@Table(name = "distributed_locks")
public class DistributedLock {
    @Id
    private String lockKey;
    private String owner;
    private Instant expiresAt;
}

@Repository
public interface LockRepository extends JpaRepository<DistributedLock, String> {
    @Modifying
    @Query("DELETE FROM DistributedLock l WHERE l.lockKey = :key AND l.owner = :owner")
    int releaseLock(@Param("key") String key, @Param("owner") String owner);
    
    @Modifying
    @Query(value = "INSERT INTO distributed_locks (lock_key, owner, expires_at) " +
           "VALUES (:key, :owner, :expires) " +
           "ON CONFLICT (lock_key) DO NOTHING", nativeQuery = true)
    int tryAcquire(@Param("key") String key, @Param("owner") String owner, 
                   @Param("expires") Instant expires);
}

// Solution 3: Zookeeper-based lock (strong consistency)
@Service
public class ZookeeperLockService {
    @Autowired private CuratorFramework curator;
    
    public <T> T executeWithLock(String path, Supplier<T> task) throws Exception {
        InterProcessMutex lock = new InterProcessMutex(curator, "/locks/" + path);
        if (lock.acquire(10, TimeUnit.SECONDS)) {
            try {
                return task.get();
            } finally {
                lock.release();
            }
        }
        throw new LockAcquisitionException("Timeout acquiring lock: " + path);
    }
}
```

### Q12: How to handle idempotency in distributed systems?

```java
// Problem: Network failures cause duplicate requests
// Client sends payment → Server processes → Response lost → Client retries → DOUBLE PAYMENT!

// Solution: Idempotency key
@RestController
public class PaymentController {
    
    @PostMapping("/payments")
    public ResponseEntity<Payment> createPayment(
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @RequestBody PaymentRequest request) {
        
        // Check if already processed
        Optional<Payment> existing = paymentRepo.findByIdempotencyKey(idempotencyKey);
        if (existing.isPresent()) {
            return ResponseEntity.ok(existing.get()); // Return same result
        }
        
        // Process new payment
        Payment payment = paymentService.process(request, idempotencyKey);
        return ResponseEntity.status(HttpStatus.CREATED).body(payment);
    }
}

// With database constraint
@Entity
public class Payment {
    @Id @GeneratedValue
    private Long id;
    
    @Column(unique = true, nullable = false)
    private String idempotencyKey; // Unique constraint prevents duplicates
    
    private BigDecimal amount;
    private String status;
}

// Atomic idempotent processing
@Service
public class PaymentService {
    @Transactional
    public Payment process(PaymentRequest request, String idempotencyKey) {
        // INSERT with unique key - if duplicate, DB throws exception
        // Caught by @Retryable → returns existing
        Payment payment = new Payment();
        payment.setIdempotencyKey(idempotencyKey);
        payment.setAmount(request.getAmount());
        payment.setStatus("PENDING");
        paymentRepo.save(payment); // Fails if duplicate key
        
        // Process actual payment
        paymentGateway.charge(request);
        payment.setStatus("COMPLETED");
        return paymentRepo.save(payment);
    }
}
```

---

## Atomic Operations

### Q13: Java's Atomic classes and when to use them

```java
// AtomicInteger - thread-safe counter
private final AtomicInteger requestCount = new AtomicInteger(0);
requestCount.incrementAndGet();  // Atomic: CAS (Compare-And-Swap)

// AtomicReference - thread-safe reference update
private final AtomicReference<Config> currentConfig = new AtomicReference<>(defaultConfig);
currentConfig.compareAndSet(oldConfig, newConfig); // Only updates if still oldConfig

// AtomicLong - for IDs, counters
private final AtomicLong idGenerator = new AtomicLong(0);
long newId = idGenerator.getAndIncrement();

// LongAdder - BETTER than AtomicLong for high-contention counters
private final LongAdder hitCounter = new LongAdder(); // Less contention than AtomicLong
hitCounter.increment();
long total = hitCounter.sum();

// ConcurrentHashMap atomic operations
ConcurrentHashMap<String, AtomicInteger> counters = new ConcurrentHashMap<>();
counters.computeIfAbsent("key", k -> new AtomicInteger()).incrementAndGet();
counters.merge("key", 1, Integer::sum); // Atomic merge
```

### Q14: Compare-And-Swap (CAS) vs Locking

```java
// CAS approach (lock-free, better for low contention)
public class CASCounter {
    private final AtomicInteger value = new AtomicInteger(0);
    
    public int increment() {
        int current;
        int next;
        do {
            current = value.get();           // Read current
            next = current + 1;              // Compute new
        } while (!value.compareAndSet(current, next)); // Retry if changed
        return next;
        // Under high contention: spins (busy-wait), wastes CPU
    }
}

// Lock approach (better for high contention or complex operations)
public class LockedCounter {
    private int value = 0;
    private final ReentrantLock lock = new ReentrantLock();
    
    public int increment() {
        lock.lock();
        try {
            return ++value;
        } finally {
            lock.unlock();
        }
        // Under high contention: threads sleep, less CPU waste
    }
}

// When to use which:
// CAS (Atomic*): Simple operations, low-moderate contention, no I/O inside
// Locks: Complex operations, high contention, I/O or long operations inside
// synchronized: When you need wait/notify semantics
```

---

## Reactive Concurrency Patterns

### Q15: How does concurrency work in WebFlux?

```java
// In WebFlux, concurrency is managed differently:
// No shared mutable state (by design)
// No locks needed (single-threaded event loop per connection)
// Concurrency through COMPOSITION, not threads

// Parallel execution with Reactor
public Mono<Dashboard> getDashboard(String userId) {
    // These execute CONCURRENTLY (non-blocking)
    Mono<User> user = userService.findById(userId);
    Mono<List<Order>> orders = orderService.findByUserId(userId);
    Mono<Preferences> prefs = prefsService.findByUserId(userId);
    
    return Mono.zip(user, orders, prefs)
        .map(tuple -> new Dashboard(tuple.getT1(), tuple.getT2(), tuple.getT3()));
    // No thread synchronization needed!
    // Each mono executes independently, zip waits for all
}

// Rate limiting with Reactor
public Flux<Result> processWithRateLimit(Flux<Request> requests) {
    return requests
        .flatMap(
            request -> processAsync(request),
            16  // Max 16 concurrent operations
        );
}

// Mutex in reactive (if shared state needed)
public class ReactiveCounter {
    private final Sinks.One<Void> lock = Sinks.one();
    private int count = 0;
    
    public Mono<Integer> increment() {
        return Mono.defer(() -> {
            count++;
            return Mono.just(count);
        }).subscribeOn(Schedulers.single()); // Serialize access on single thread
    }
}
```

### Q16: Preventing concurrent modification in reactive streams

```java
// Problem: Multiple subscribers modifying shared state
// Solution: Use Sinks for controlled emission

@Service
public class EventBroadcaster {
    // Thread-safe sink
    private final Sinks.Many<Event> sink = Sinks.many()
        .multicast()
        .onBackpressureBuffer(1000);
    
    // Thread-safe emission
    public void broadcast(Event event) {
        Sinks.EmitResult result = sink.tryEmitNext(event);
        if (result.isFailure()) {
            // Handle: retry, drop, or error
            log.warn("Failed to emit event: {}", result);
        }
    }
    
    public Flux<Event> subscribe() {
        return sink.asFlux();
    }
}

// Pattern: Single writer, multiple readers
@Service  
public class PriceService {
    private final AtomicReference<Map<String, BigDecimal>> prices = 
        new AtomicReference<>(Collections.emptyMap());
    
    // Single writer (from Kafka consumer)
    public void updatePrices(Map<String, BigDecimal> newPrices) {
        prices.set(Collections.unmodifiableMap(new HashMap<>(newPrices)));
        // Atomic reference swap - readers always see consistent snapshot
    }
    
    // Many concurrent readers (from HTTP requests)
    public BigDecimal getPrice(String symbol) {
        return prices.get().get(symbol); // Lock-free read
    }
}
```

---

## Common Concurrency Bugs in Production

### Q17: The "check-then-act" anti-pattern

```java
// EVERY check-then-act is a potential race condition

// Bug 1: File existence check
if (!file.exists()) {
    file.createNewFile(); // Another thread might create between check and create!
}

// Bug 2: Collection check
if (!map.containsKey(key)) {
    map.put(key, computeValue()); // Another thread might put between check and put!
}
// Fix: map.computeIfAbsent(key, k -> computeValue());

// Bug 3: Singleton initialization
if (instance == null) {         // Thread A checks: null
    instance = new Singleton(); // Thread A creates
}                               // Thread B checks: null (before A's write visible!)
                                // Thread B creates ANOTHER instance!
// Fix: volatile + double-checked locking or enum singleton

// Bug 4: Inventory check
if (inventory.getQuantity() >= requestedQuantity) {
    inventory.setQuantity(inventory.getQuantity() - requestedQuantity);
    // Between check and update, another thread might reduce quantity!
}
// Fix: atomic conditional update:
// UPDATE inventory SET quantity = quantity - ? WHERE id = ? AND quantity >= ?
```

### Q18: Thread pool starvation

```java
// Problem: Nested async calls using the same thread pool
@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(5); // Only 5 threads!
        return executor;
    }
}

@Service
public class OrderService {
    @Async
    public CompletableFuture<Order> processOrder(Order order) {
        // Uses 1 thread from pool (5 available)
        
        // This ALSO needs a thread from the SAME pool!
        CompletableFuture<Payment> payment = paymentService.processPayment(order); // 1 more thread
        CompletableFuture<Shipment> shipment = shipmentService.schedule(order);    // 1 more thread
        
        return payment.thenCombine(shipment, (p, s) -> completeOrder(order, p, s));
    }
}

// If 5 processOrder() calls come in simultaneously:
// 5 threads busy with processOrder()
// Each tries to get thread for payment/shipment
// No threads available → DEADLOCK (thread pool starvation)!

// Solution: Separate thread pools for different levels
@Bean("orderPool")
public Executor orderPool() {
    return Executors.newFixedThreadPool(10);
}

@Bean("paymentPool")  // DIFFERENT pool
public Executor paymentPool() {
    return Executors.newFixedThreadPool(20);
}
```

### Q19: Visibility issues (happens-before)

```java
// The Java Memory Model problem
public class VisibilityBug {
    private boolean running = true; // NOT volatile!
    
    // Thread 1
    public void runLoop() {
        while (running) { // May NEVER see update from Thread 2!
            doWork();     // JIT may cache 'running' in CPU register
        }
    }
    
    // Thread 2
    public void stop() {
        running = false; // Write might stay in CPU cache
        // No happens-before relationship!
    }
}

// Fix: volatile guarantees visibility
private volatile boolean running = true;

// Or use AtomicBoolean
private final AtomicBoolean running = new AtomicBoolean(true);
```

---

## Best Practices Summary

### Q20: Concurrency best practices checklist for Spring Boot

```
1. STATELESS BEANS
   ✓ Keep singleton beans stateless
   ✓ All mutable state in method locals or request-scoped beans
   
2. IMMUTABILITY
   ✓ Use final fields
   ✓ Use immutable collections (List.of(), Map.of())
   ✓ Use immutable DTOs (records)
   
3. DATABASE CONCURRENCY
   ✓ Use @Version for optimistic locking
   ✓ Use atomic DB operations (UPDATE ... WHERE)
   ✓ Use proper isolation levels
   ✓ Always order lock acquisition consistently
   
4. THREAD POOLS
   ✓ Separate pools for different workloads
   ✓ Size pools appropriately (I/O-bound: larger, CPU-bound: core count)
   ✓ Always set queue bounds (unbounded = OOM risk)
   ✓ Define rejection policies
   
5. CONCURRENT COLLECTIONS
   ✓ ConcurrentHashMap over synchronized HashMap
   ✓ CopyOnWriteArrayList for rare writes, frequent reads
   ✓ BlockingQueue for producer-consumer patterns
   
6. DISTRIBUTED SYSTEMS
   ✓ Implement idempotency (idempotency keys)
   ✓ Use distributed locks sparingly
   ✓ Design for eventual consistency
   ✓ Handle partial failures gracefully
   
7. TESTING
   ✓ Use stress testing (JMeter, Gatling)
   ✓ Use Thread Sanitizer (for native code)
   ✓ Test with reduced thread pools (amplifies race conditions)
   ✓ Use CountDownLatch/CyclicBarrier in tests to force races
```
