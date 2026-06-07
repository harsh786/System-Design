# @Transactional & Transaction Management - Complete Guide

## Table of Contents
1. [How @Transactional Works Internally](#how-transactional-works-internally)
2. [Proxy Mechanism](#proxy-mechanism)
3. [Propagation Levels](#propagation-levels)
4. [Isolation Levels](#isolation-levels)
5. [Rollback Rules](#rollback-rules)
6. [Read-Only Transactions](#read-only-transactions)
7. [Transaction Timeout](#transaction-timeout)
8. [Programmatic Transactions](#programmatic-transactions)
9. [Distributed Transactions](#distributed-transactions)
10. [Common Pitfalls & Anti-Patterns](#common-pitfalls--anti-patterns)
11. [Testing Transactions](#testing-transactions)
12. [Production Best Practices](#production-best-practices)

---

## How @Transactional Works Internally

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│              @TRANSACTIONAL INTERNALS                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  When you annotate a method with @Transactional:                 │
│                                                                   │
│  1. Spring creates a PROXY around your bean                      │
│  2. Proxy INTERCEPTS the method call                             │
│  3. Before method: Opens transaction (gets DB connection)        │
│  4. Method executes (your business logic)                        │
│  5. If success: COMMIT                                           │
│  6. If RuntimeException: ROLLBACK                                │
│  7. After: Release connection back to pool                       │
│                                                                   │
│  ┌──────────────────────────────────────────────────┐           │
│  │                PROXY (CGLIB)                       │           │
│  │  ┌────────────────────────────────────────────┐  │           │
│  │  │  TransactionInterceptor                     │  │           │
│  │  │                                            │  │           │
│  │  │  1. PlatformTransactionManager.getTransaction│ │           │
│  │  │     → Get connection from DataSource pool   │  │           │
│  │  │     → Set autoCommit = false                │  │           │
│  │  │     → Bind to ThreadLocal                   │  │           │
│  │  │                                            │  │           │
│  │  │  2. Call actual method                      │  │           │
│  │  │     → Your code runs                        │  │           │
│  │  │     → JPA/JDBC uses ThreadLocal connection  │  │           │
│  │  │                                            │  │           │
│  │  │  3a. No exception → COMMIT                  │  │           │
│  │  │  3b. RuntimeException → ROLLBACK            │  │           │
│  │  │                                            │  │           │
│  │  │  4. Unbind connection from ThreadLocal      │  │           │
│  │  │     → Return connection to pool             │  │           │
│  │  └────────────────────────────────────────────┘  │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Detailed Internal Flow

```java
// What Spring generates (simplified pseudo-code of the proxy):

public class OrderService$$EnhancerBySpringCGLIB extends OrderService {
    
    private TransactionInterceptor transactionInterceptor;
    
    @Override
    public Order createOrder(OrderRequest request) {
        // 1. Get transaction attributes from @Transactional annotation
        TransactionAttribute txAttr = getTransactionAttribute(method);
        
        // 2. Get PlatformTransactionManager
        PlatformTransactionManager tm = getTransactionManager();
        
        // 3. Create/join transaction
        TransactionStatus status = tm.getTransaction(txAttr);
        // Internally:
        //   - Gets Connection from DataSource (HikariPool)
        //   - connection.setAutoCommit(false)
        //   - Binds connection to TransactionSynchronizationManager (ThreadLocal)
        
        try {
            // 4. Call actual method
            Order result = super.createOrder(request); // YOUR CODE
            
            // 5. Commit
            tm.commit(status);
            // Internally: connection.commit()
            
            return result;
            
        } catch (RuntimeException ex) {
            // 6. Rollback
            tm.rollback(status);
            // Internally: connection.rollback()
            throw ex;
            
        } finally {
            // 7. Cleanup
            // Unbind connection from ThreadLocal
            // Return connection to pool
        }
    }
}
```

### ThreadLocal Connection Binding

```java
// This is how JPA/JDBC operations in your service use the SAME connection:

@Transactional
public void transferMoney(Long from, Long to, BigDecimal amount) {
    // Spring has already bound a connection to current thread
    
    accountRepo.debit(from, amount);
    // JPA internally calls: TransactionSynchronizationManager.getResource(dataSource)
    // Gets the SAME connection that was bound by the proxy
    
    accountRepo.credit(to, amount);
    // Same connection - same transaction!
    
    auditRepo.save(new AuditLog(from, to, amount));
    // Still same connection!
}
// All three operations are in ONE transaction
// Either ALL commit or ALL rollback
```

---

## Proxy Mechanism

### CGLIB Proxy (Default)

```java
// Spring Boot default: CGLIB proxy (subclass-based)
// Works with concrete classes (no interface needed)

@Service
public class OrderService { // Concrete class
    
    @Transactional
    public void processOrder(Order order) { ... }
}

// Spring creates: OrderService$$EnhancerBySpringCGLIB$$abc123
// This is a SUBCLASS of OrderService
// Overrides transactional methods to add transaction logic
```

### JDK Dynamic Proxy (Interface-based)

```java
// If you code to interfaces, JDK proxy is used:
public interface OrderService {
    void processOrder(Order order);
}

@Service
public class OrderServiceImpl implements OrderService {
    @Transactional
    @Override
    public void processOrder(Order order) { ... }
}

// Spring creates: $Proxy123 implementing OrderService
// Delegates to real OrderServiceImpl through InvocationHandler
```

### The Self-Invocation Problem (CRITICAL!)

```java
@Service
public class OrderService {
    
    @Transactional
    public void processOrder(Order order) {
        // This is transactional ✓
    }
    
    public void batchProcess(List<Order> orders) {
        for (Order order : orders) {
            processOrder(order); // NO TRANSACTION! Self-invocation bypasses proxy!
        }
    }
}
```

**Why self-invocation fails:**

```
External call:
  Caller → Proxy.processOrder() → TransactionInterceptor → Real.processOrder()
  ✓ Transaction is created

Self-invocation:
  Real.batchProcess() → this.processOrder() → Real.processOrder()
  ✗ Proxy is bypassed! "this" refers to the real object, not the proxy!
```

**Solutions:**

```java
// Solution 1: Inject self (Spring 4.3+)
@Service
public class OrderService {
    @Autowired
    private OrderService self; // Injects the PROXY
    
    public void batchProcess(List<Order> orders) {
        for (Order order : orders) {
            self.processOrder(order); // Goes through proxy ✓
        }
    }
    
    @Transactional
    public void processOrder(Order order) { ... }
}

// Solution 2: Extract to separate class
@Service
public class OrderProcessor {
    @Transactional
    public void processOrder(Order order) { ... }
}

@Service
public class OrderBatchService {
    private final OrderProcessor processor;
    
    public void batchProcess(List<Order> orders) {
        for (Order order : orders) {
            processor.processOrder(order); // Different bean → proxy works ✓
        }
    }
}

// Solution 3: Use TransactionTemplate (programmatic)
@Service
public class OrderService {
    private final TransactionTemplate txTemplate;
    
    public void batchProcess(List<Order> orders) {
        for (Order order : orders) {
            txTemplate.execute(status -> {
                processOrderInternal(order);
                return null;
            });
        }
    }
}
```

---

## Propagation Levels

### All 7 Propagation Types

```java
@Transactional(propagation = Propagation.REQUIRED) // DEFAULT
```

```
┌─────────────────────────────────────────────────────────────────┐
│  PROPAGATION LEVELS                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  REQUIRED (DEFAULT)                                              │
│  ─────────────────                                               │
│  - Join existing transaction if one exists                       │
│  - Create NEW transaction if none exists                         │
│  - Most common choice                                           │
│                                                                   │
│  Caller has TX │ Behavior                                        │
│  ─────────────┼─────────────────────                            │
│  YES          │ JOIN caller's transaction                        │
│  NO           │ CREATE new transaction                           │
│                                                                   │
│  ┌─── ServiceA (TX1) ───────────────────┐                       │
│  │ @Transactional                        │                       │
│  │ serviceA.method() {                   │                       │
│  │     serviceB.method();  ──────┐       │                       │
│  │ }                              │       │                       │
│  └────────────────────────────────│───────┘                       │
│                                   │                               │
│  ┌─── ServiceB (SAME TX1) ───────▼──────┐                       │
│  │ @Transactional(REQUIRED)              │                       │
│  │ serviceB.method() {                   │                       │
│  │     // Runs in TX1!                   │                       │
│  │     // If B throws → TX1 rolls back  │                       │
│  │ }                                     │                       │
│  └───────────────────────────────────────┘                       │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  REQUIRES_NEW                                                    │
│  ────────────                                                    │
│  - ALWAYS creates a NEW transaction                              │
│  - Suspends current transaction if one exists                    │
│  - Inner TX commits/rollbacks independently                      │
│                                                                   │
│  ┌─── ServiceA (TX1) ──────────────────────────┐                │
│  │ @Transactional                                │                │
│  │ serviceA.method() {                           │                │
│  │     // TX1 SUSPENDED here                     │                │
│  │     serviceB.method();  ──────┐               │                │
│  │     // TX1 RESUMED here       │               │                │
│  │ }                              │               │                │
│  └────────────────────────────────│───────────────┘                │
│                                   │                               │
│  ┌─── ServiceB (NEW TX2) ────────▼──────┐                       │
│  │ @Transactional(REQUIRES_NEW)          │                       │
│  │ serviceB.method() {                   │                       │
│  │     // Runs in TX2 (independent!)     │                       │
│  │     // TX2 commit ≠ TX1 commit        │                       │
│  │     // TX2 rollback ≠ TX1 rollback    │                       │
│  │ }                                     │                       │
│  └───────────────────────────────────────┘                       │
│                                                                   │
│  USE CASE: Audit logging that must persist even if main TX fails │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  NESTED                                                          │
│  ──────                                                          │
│  - Creates a SAVEPOINT within the current transaction            │
│  - Inner failure rolls back to savepoint (not whole TX)          │
│  - Outer TX can catch exception and continue                     │
│  - Requires JDBC 3.0+ savepoint support                         │
│                                                                   │
│  ┌─── ServiceA (TX1) ──────────────────────────┐                │
│  │ @Transactional                                │                │
│  │ serviceA.method() {                           │                │
│  │     serviceB.method();  ──────┐               │                │
│  │     // If B fails: TX1 intact │               │                │
│  │     // (rolled back to savepoint only)        │                │
│  │ }                              │               │                │
│  └────────────────────────────────│───────────────┘                │
│                                   │                               │
│  ┌─── ServiceB (SAVEPOINT in TX1)▼──────┐                       │
│  │ @Transactional(NESTED)                │                       │
│  │ serviceB.method() {                   │                       │
│  │     // SAVEPOINT created              │                       │
│  │     // Failure → rollback to savepoint│                       │
│  │     // Success → savepoint released   │                       │
│  │ }                                     │                       │
│  └───────────────────────────────────────┘                       │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SUPPORTS                                                        │
│  ────────                                                        │
│  - Run within TX if one exists                                   │
│  - Run WITHOUT TX if none exists                                 │
│  - "I don't care either way"                                     │
│                                                                   │
│  Caller has TX │ Behavior                                        │
│  ─────────────┼─────────────────────                            │
│  YES          │ JOIN caller's transaction                        │
│  NO           │ Run non-transactionally                          │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  NOT_SUPPORTED                                                   │
│  ─────────────                                                   │
│  - NEVER run in a transaction                                    │
│  - Suspends current TX if one exists                             │
│                                                                   │
│  USE CASE: Long-running read operation that shouldn't hold TX    │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  MANDATORY                                                       │
│  ─────────                                                       │
│  - MUST run within existing TX                                   │
│  - Throws exception if no TX exists                              │
│                                                                   │
│  USE CASE: Repository method that should never be called         │
│            outside a transaction                                  │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  NEVER                                                           │
│  ─────                                                           │
│  - MUST NOT run within a transaction                             │
│  - Throws exception if TX exists                                 │
│                                                                   │
│  USE CASE: Method that must never participate in a transaction   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Practical Propagation Examples

```java
@Service
public class OrderService {
    
    @Transactional // REQUIRED (default)
    public void createOrder(OrderRequest request) {
        Order order = orderRepo.save(new Order(request));
        
        // This runs in SAME transaction
        inventoryService.reserve(order.getItems());
        
        // This runs in NEW transaction (audit always persists)
        auditService.logOrderCreation(order);
        
        // If this throws, order and inventory rollback
        // But audit log persists (REQUIRES_NEW)
        paymentService.charge(order);
    }
}

@Service
public class AuditService {
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void logOrderCreation(Order order) {
        // Even if caller's transaction rolls back,
        // this audit log is COMMITTED
        auditRepo.save(new AuditLog("ORDER_CREATED", order.getId()));
    }
}

@Service
public class InventoryService {
    @Transactional(propagation = Propagation.MANDATORY)
    public void reserve(List<Item> items) {
        // MUST be called within a transaction
        // Throws IllegalTransactionStateException if not
        items.forEach(item -> inventoryRepo.decrementStock(item.getId(), item.getQty()));
    }
}
```

---

## Isolation Levels

### Database Isolation Problems

```
┌──────────────────────────────────────────────────────────────────┐
│  ISOLATION PROBLEMS                                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  DIRTY READ:                                                      │
│  TX1 reads data that TX2 has modified but NOT YET COMMITTED       │
│  If TX2 rolls back, TX1 has read "phantom" data                   │
│                                                                    │
│  TX1: SELECT balance → 100                                        │
│  TX2: UPDATE balance = 200 (not committed)                        │
│  TX1: SELECT balance → 200 (DIRTY! TX2 might rollback)            │
│  TX2: ROLLBACK                                                    │
│  TX1: Made decision based on 200, but actual is 100!              │
│                                                                    │
│  NON-REPEATABLE READ:                                             │
│  TX1 reads same row twice, gets different values                  │
│  (Another TX committed between the reads)                         │
│                                                                    │
│  TX1: SELECT balance → 100                                        │
│  TX2: UPDATE balance = 50; COMMIT                                 │
│  TX1: SELECT balance → 50 (Different! Non-repeatable!)            │
│                                                                    │
│  PHANTOM READ:                                                    │
│  TX1 runs same query twice, gets different ROWS                   │
│  (Another TX inserted/deleted rows between queries)               │
│                                                                    │
│  TX1: SELECT * WHERE age > 20 → 5 rows                           │
│  TX2: INSERT (age=25); COMMIT                                     │
│  TX1: SELECT * WHERE age > 20 → 6 rows (Phantom!)                │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### Isolation Levels

```java
@Transactional(isolation = Isolation.READ_COMMITTED) // Most common
```

```
┌────────────────────────────────────────────────────────────────────┐
│  ISOLATION LEVELS                                                   │
├─────────────────┬────────────┬──────────────────┬─────────────────┤
│ Level           │ Dirty Read │ Non-Repeatable   │ Phantom Read    │
├─────────────────┼────────────┼──────────────────┼─────────────────┤
│ READ_UNCOMMITTED│ Possible   │ Possible         │ Possible        │
│ READ_COMMITTED  │ Prevented  │ Possible         │ Possible        │
│ REPEATABLE_READ │ Prevented  │ Prevented        │ Possible        │
│ SERIALIZABLE    │ Prevented  │ Prevented        │ Prevented       │
├─────────────────┼────────────┼──────────────────┼─────────────────┤
│ DEFAULT         │ Uses DB default (usually READ_COMMITTED)        │
└─────────────────┴────────────┴──────────────────┴─────────────────┘

Performance:  READ_UNCOMMITTED > READ_COMMITTED > REPEATABLE_READ > SERIALIZABLE
Safety:       READ_UNCOMMITTED < READ_COMMITTED < REPEATABLE_READ < SERIALIZABLE

Database defaults:
- PostgreSQL: READ_COMMITTED
- MySQL (InnoDB): REPEATABLE_READ
- Oracle: READ_COMMITTED
- SQL Server: READ_COMMITTED
```

### Practical Isolation Examples

```java
// Financial transfer - use SERIALIZABLE for critical operations
@Transactional(isolation = Isolation.SERIALIZABLE)
public void transferMoney(Long fromId, Long toId, BigDecimal amount) {
    Account from = accountRepo.findById(fromId).orElseThrow();
    Account to = accountRepo.findById(toId).orElseThrow();
    
    if (from.getBalance().compareTo(amount) < 0) {
        throw new InsufficientFundsException();
    }
    
    from.setBalance(from.getBalance().subtract(amount));
    to.setBalance(to.getBalance().add(amount));
    
    accountRepo.save(from);
    accountRepo.save(to);
}

// Report generation - REPEATABLE_READ for consistent snapshot
@Transactional(isolation = Isolation.REPEATABLE_READ, readOnly = true)
public Report generateDailyReport() {
    // All queries in this method see the SAME data snapshot
    // Even if other transactions modify data during report generation
    BigDecimal totalRevenue = orderRepo.sumRevenueForToday();
    long orderCount = orderRepo.countTodayOrders();
    List<TopProduct> topProducts = productRepo.findTopSelling(10);
    return new Report(totalRevenue, orderCount, topProducts);
}

// Default - READ_COMMITTED for most operations
@Transactional // Uses DB default (READ_COMMITTED typically)
public void updateUserProfile(Long userId, ProfileUpdate update) {
    User user = userRepo.findById(userId).orElseThrow();
    user.setName(update.getName());
    user.setEmail(update.getEmail());
    userRepo.save(user);
}
```

---

## Rollback Rules

### Default Behavior

```java
// DEFAULT: Rollback on unchecked exceptions (RuntimeException + Error)
//          NO rollback on checked exceptions (Exception)

@Transactional
public void defaultBehavior() {
    throw new RuntimeException("Rolls back!");      // ROLLBACK ✓
    throw new NullPointerException("Rolls back!");  // ROLLBACK ✓ (RuntimeException)
    throw new OutOfMemoryError("Rolls back!");      // ROLLBACK ✓ (Error)
    throw new IOException("NO rollback!");          // NO ROLLBACK ✗ (Checked)
    throw new SQLException("NO rollback!");         // NO ROLLBACK ✗ (Checked)
}
```

### Custom Rollback Rules

```java
// Rollback for specific checked exceptions
@Transactional(rollbackFor = {IOException.class, BusinessException.class})
public void customRollback() {
    throw new IOException("Now it rolls back!"); // ROLLBACK ✓
}

// Don't rollback for specific runtime exceptions
@Transactional(noRollbackFor = {EmailSendException.class})
public void noRollbackForEmail() {
    orderRepo.save(order);
    throw new EmailSendException("Email failed"); // NO ROLLBACK ✗
    // Order is still committed! Email failure is non-critical.
}

// Rollback for all exceptions
@Transactional(rollbackFor = Exception.class)
public void rollbackForAll() {
    throw new Exception("Rolls back!"); // ROLLBACK ✓
}
```

### Manual Rollback

```java
@Transactional
public void manualRollback() {
    orderRepo.save(order);
    
    if (someCondition) {
        // Programmatically mark for rollback without throwing exception
        TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
        return; // Method returns normally, but transaction WILL rollback
    }
}
```

---

## Read-Only Transactions

### What readOnly = true Does

```java
@Transactional(readOnly = true)
public List<User> findAllUsers() {
    return userRepo.findAll();
}
```

```
┌──────────────────────────────────────────────────────────────┐
│  readOnly = true EFFECTS                                      │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. HIBERNATE/JPA:                                           │
│     - Sets FlushMode to MANUAL (no auto-flush)               │
│     - Disables dirty checking (no snapshot comparison)        │
│     - Entities loaded in read-only mode (no change tracking)  │
│     → PERFORMANCE GAIN: Less memory, no unnecessary flushes  │
│                                                               │
│  2. JDBC/DATABASE:                                           │
│     - Sets connection.setReadOnly(true)                      │
│     - Database MAY optimize (e.g., skip write-ahead log)     │
│     - Some DBs route to read replica automatically            │
│                                                               │
│  3. SPRING:                                                  │
│     - TransactionSynchronizationManager marks TX as readOnly │
│     - Custom routing DataSource can route to replica         │
│                                                               │
│  DOES NOT prevent writes from occurring!                     │
│  It's a HINT, not enforcement (in most DBs).                 │
│  But Hibernate will throw on flush if dirty changes detected. │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Best Practices for Read Operations

```java
@Service
public class UserService {
    
    // GOOD: Read-only for queries
    @Transactional(readOnly = true)
    public User findById(Long id) {
        return userRepo.findById(id).orElseThrow();
    }
    
    // GOOD: Read-only for complex queries with multiple repo calls
    @Transactional(readOnly = true)
    public UserDashboard getDashboard(Long userId) {
        User user = userRepo.findById(userId).orElseThrow();
        List<Order> recentOrders = orderRepo.findRecentByUser(userId);
        UserStats stats = statsRepo.findByUser(userId);
        return new UserDashboard(user, recentOrders, stats);
    }
    
    // BAD: Read-only when you actually write
    @Transactional(readOnly = true)
    public User updateUser(User user) {
        return userRepo.save(user); // May throw or silently not persist!
    }
}
```

---

## Transaction Timeout

```java
// Timeout in seconds - transaction rolls back if exceeded
@Transactional(timeout = 30) // 30 seconds
public void longRunningOperation() {
    // If this takes > 30 seconds:
    // - TransactionTimedOutException thrown
    // - Transaction rolled back
    // - Applies to DB operations, not the entire method!
    
    processItems(); // If a DB call within this exceeds timeout...
}

// Global default timeout
@Configuration
public class TransactionConfig {
    @Bean
    public PlatformTransactionManager transactionManager(DataSource ds) {
        DataSourceTransactionManager tm = new DataSourceTransactionManager(ds);
        tm.setDefaultTimeout(30); // 30 seconds default for all transactions
        return tm;
    }
}
```

---

## Programmatic Transactions

### TransactionTemplate

```java
@Service
public class OrderService {
    private final TransactionTemplate txTemplate;
    private final TransactionTemplate readOnlyTxTemplate;
    
    public OrderService(PlatformTransactionManager txManager) {
        this.txTemplate = new TransactionTemplate(txManager);
        this.txTemplate.setTimeout(30);
        
        this.readOnlyTxTemplate = new TransactionTemplate(txManager);
        this.readOnlyTxTemplate.setReadOnly(true);
    }
    
    // With return value
    public Order createOrder(OrderRequest request) {
        return txTemplate.execute(status -> {
            Order order = orderRepo.save(new Order(request));
            inventoryService.reserve(order.getItems());
            
            if (someCondition) {
                status.setRollbackOnly(); // Manual rollback
                return null;
            }
            
            return order;
        });
    }
    
    // Without return value
    public void processOrders(List<Long> orderIds) {
        for (Long id : orderIds) {
            txTemplate.executeWithoutResult(status -> {
                try {
                    processOneOrder(id);
                } catch (Exception e) {
                    status.setRollbackOnly(); // Rollback just this order
                    log.error("Failed to process order {}", id, e);
                }
            });
        }
    }
}
```

### PlatformTransactionManager Directly

```java
@Service
public class LowLevelTransactionService {
    
    @Autowired
    private PlatformTransactionManager txManager;
    
    public void complexOperation() {
        DefaultTransactionDefinition def = new DefaultTransactionDefinition();
        def.setName("complexTx");
        def.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRED);
        def.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
        def.setTimeout(30);
        
        TransactionStatus status = txManager.getTransaction(def);
        
        try {
            // Business logic
            step1();
            step2();
            step3();
            
            txManager.commit(status);
        } catch (Exception e) {
            txManager.rollback(status);
            throw e;
        }
    }
}
```

---

## Distributed Transactions

### The Problem

```
┌─────────────────────────────────────────────────────────────┐
│  DISTRIBUTED TRANSACTION PROBLEM                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  OrderService.createOrder():                                │
│  1. Save order to Orders DB (MySQL)      ← TX1              │
│  2. Send message to Kafka                ← TX2              │
│  3. Update inventory in Inventory DB     ← TX3              │
│                                                              │
│  What if step 1 succeeds but step 3 fails?                  │
│  @Transactional only covers ONE database!                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Solution 1: Saga Pattern (Choreography)

```java
// Each service publishes events and reacts to events
// No central coordinator

@Service
public class OrderService {
    @Transactional
    public void createOrder(OrderRequest request) {
        Order order = orderRepo.save(new Order(request, OrderStatus.PENDING));
        eventPublisher.publish(new OrderCreatedEvent(order.getId()));
    }
    
    @EventListener
    @Transactional
    public void onPaymentFailed(PaymentFailedEvent event) {
        // Compensating action
        Order order = orderRepo.findById(event.getOrderId()).orElseThrow();
        order.setStatus(OrderStatus.CANCELLED);
        orderRepo.save(order);
    }
}

@Service
public class PaymentService {
    @EventListener
    @Transactional
    public void onOrderCreated(OrderCreatedEvent event) {
        try {
            paymentGateway.charge(event.getAmount());
            eventPublisher.publish(new PaymentSucceededEvent(event.getOrderId()));
        } catch (PaymentException e) {
            eventPublisher.publish(new PaymentFailedEvent(event.getOrderId(), e.getMessage()));
        }
    }
}

@Service
public class InventoryService {
    @EventListener
    @Transactional
    public void onPaymentSucceeded(PaymentSucceededEvent event) {
        try {
            inventoryRepo.reserve(event.getItems());
            eventPublisher.publish(new InventoryReservedEvent(event.getOrderId()));
        } catch (InsufficientStockException e) {
            eventPublisher.publish(new InventoryFailedEvent(event.getOrderId()));
            // This triggers compensating actions in Payment and Order services
        }
    }
}
```

### Solution 2: Saga Pattern (Orchestration)

```java
@Service
public class OrderSagaOrchestrator {
    
    @Transactional
    public OrderResult executeOrderSaga(OrderRequest request) {
        // Step 1: Create order
        Order order = orderService.createOrder(request);
        
        // Step 2: Process payment
        try {
            paymentService.charge(order);
        } catch (PaymentException e) {
            // Compensate step 1
            orderService.cancelOrder(order.getId());
            return OrderResult.failed("Payment failed");
        }
        
        // Step 3: Reserve inventory
        try {
            inventoryService.reserve(order.getItems());
        } catch (InsufficientStockException e) {
            // Compensate steps 1 & 2
            paymentService.refund(order.getPaymentId());
            orderService.cancelOrder(order.getId());
            return OrderResult.failed("Insufficient stock");
        }
        
        // All steps succeeded
        orderService.confirmOrder(order.getId());
        return OrderResult.success(order);
    }
}
```

### Solution 3: Transactional Outbox

```java
// Ensure DB write and message publish are atomic
@Service
public class OrderService {
    
    @Transactional // Single DB transaction
    public Order createOrder(OrderRequest request) {
        // Business write
        Order order = orderRepo.save(new Order(request));
        
        // Event saved in SAME transaction as business data
        outboxRepo.save(OutboxEvent.builder()
            .aggregateId(order.getId().toString())
            .aggregateType("Order")
            .eventType("OrderCreated")
            .payload(toJson(order))
            .build());
        
        return order;
        // Both order AND event commit atomically
    }
}

// Separate process reads outbox and publishes to Kafka
// (Debezium CDC is even better - no polling needed)
```

---

## Common Pitfalls & Anti-Patterns

### Pitfall 1: @Transactional on Private Methods

```java
@Service
public class UserService {
    
    @Transactional // DOES NOTHING! Private methods can't be proxied!
    private void updateUser(User user) {
        userRepo.save(user);
    }
    
    // Fix: Make it public (or use TransactionTemplate)
    @Transactional
    public void updateUser(User user) {
        userRepo.save(user);
    }
}
```

### Pitfall 2: Exception Swallowing

```java
@Service
public class OrderService {
    
    @Transactional
    public void processOrder(Order order) {
        orderRepo.save(order);
        
        try {
            paymentService.charge(order); // Throws RuntimeException
        } catch (Exception e) {
            log.error("Payment failed", e);
            // SWALLOWED! Transaction will COMMIT despite failure!
            // Order saved without payment!
        }
    }
    
    // Fix: Re-throw or setRollbackOnly
    @Transactional
    public void processOrderFixed(Order order) {
        orderRepo.save(order);
        
        try {
            paymentService.charge(order);
        } catch (Exception e) {
            log.error("Payment failed", e);
            throw e; // Or: TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
        }
    }
}
```

### Pitfall 3: Transaction Too Large

```java
// BAD: Entire batch in one transaction
@Transactional
public void processAllOrders() {
    List<Order> orders = orderRepo.findPending(); // 10,000 orders
    for (Order order : orders) {
        processOneOrder(order); // If #9999 fails, ALL 9998 roll back!
    }
}

// GOOD: Transaction per item (or per batch)
public void processAllOrders() {
    List<Order> orders = orderRepo.findPending();
    for (Order order : orders) {
        try {
            processOneOrder(order); // Each has its own transaction
        } catch (Exception e) {
            log.error("Failed to process order {}", order.getId(), e);
            // Other orders still process
        }
    }
}

@Transactional(propagation = Propagation.REQUIRES_NEW)
public void processOneOrder(Order order) { ... }
```

### Pitfall 4: Long-Running Transaction Holding Connection

```java
// BAD: HTTP call inside transaction holds DB connection!
@Transactional
public void createOrder(OrderRequest request) {
    Order order = orderRepo.save(new Order(request));
    
    // This HTTP call takes 2-5 seconds!
    // DB connection held the entire time!
    PaymentResult result = paymentClient.charge(order.getTotal());
    
    order.setPaymentId(result.getId());
    orderRepo.save(order);
}

// GOOD: Split transaction boundaries
public void createOrder(OrderRequest request) {
    // TX 1: Create order
    Order order = createOrderInDb(request);
    
    // NO transaction: Call external service
    PaymentResult result = paymentClient.charge(order.getTotal());
    
    // TX 2: Update with payment info
    updateOrderPayment(order.getId(), result.getId());
}

@Transactional
public Order createOrderInDb(OrderRequest request) {
    return orderRepo.save(new Order(request, OrderStatus.PENDING));
}

@Transactional
public void updateOrderPayment(Long orderId, String paymentId) {
    Order order = orderRepo.findById(orderId).orElseThrow();
    order.setPaymentId(paymentId);
    order.setStatus(OrderStatus.PAID);
}
```

### Pitfall 5: UnexpectedRollbackException

```java
// This happens when inner method marks TX for rollback
// but outer method catches the exception

@Service
public class OuterService {
    @Transactional
    public void outerMethod() {
        try {
            innerService.innerMethod(); // Throws, marks TX for rollback
        } catch (Exception e) {
            log.warn("Inner failed, but I'll continue...");
            // WRONG! Transaction is ALREADY marked for rollback!
            // When outerMethod exits, commit attempt → UnexpectedRollbackException!
        }
    }
}

@Service
public class InnerService {
    @Transactional // Same TX as outer (REQUIRED propagation)
    public void innerMethod() {
        throw new RuntimeException("Fail!");
        // Spring marks the SHARED transaction for rollback
    }
}

// Fix: Use REQUIRES_NEW for inner if it should be independent
@Transactional(propagation = Propagation.REQUIRES_NEW)
public void innerMethod() { ... }
```

---

## Testing Transactions

### @Transactional in Tests (Auto-Rollback)

```java
@SpringBootTest
@Transactional // Rolls back after each test! DB stays clean.
class OrderServiceTest {
    
    @Autowired
    private OrderService orderService;
    
    @Autowired
    private OrderRepository orderRepo;
    
    @Test
    void shouldCreateOrder() {
        OrderRequest request = new OrderRequest("item1", 2);
        Order order = orderService.createOrder(request);
        
        assertThat(order.getId()).isNotNull();
        assertThat(orderRepo.findById(order.getId())).isPresent();
        // After test: ROLLED BACK automatically
    }
    
    @Test
    @Rollback(false) // Override: actually commit
    void shouldPersistOrder() {
        // This test's data persists in DB
    }
}
```

### Testing Transaction Behavior

```java
@SpringBootTest
class TransactionBehaviorTest {
    
    @Autowired
    private OrderService orderService;
    
    @Autowired
    private OrderRepository orderRepo;
    
    @Test
    void shouldRollbackOnException() {
        assertThrows(PaymentException.class, () -> 
            orderService.createOrderWithPayment(failingRequest()));
        
        // Verify rollback occurred
        assertThat(orderRepo.count()).isEqualTo(0);
    }
    
    @Test
    void shouldNotRollbackOnNonCriticalException() {
        Order order = orderService.createOrderIgnoringEmailFailure(request());
        
        // Order persisted despite email exception
        assertThat(orderRepo.findById(order.getId())).isPresent();
    }
}
```

---

## Production Best Practices

### Transaction Configuration Guidelines

```java
// 1. Always specify readOnly for read operations
@Transactional(readOnly = true)
public User findById(Long id) { ... }

// 2. Keep transactions SHORT - no external calls inside
@Transactional
public Order createOrder(OrderRequest request) {
    // ONLY DB operations here
    return orderRepo.save(new Order(request));
}

// 3. Use explicit rollbackFor for checked exceptions
@Transactional(rollbackFor = Exception.class)
public void criticalOperation() { ... }

// 4. Use REQUIRES_NEW for independent operations (audit, logging)
@Transactional(propagation = Propagation.REQUIRES_NEW)
public void audit(String action) { ... }

// 5. Set appropriate timeouts
@Transactional(timeout = 10) // 10 seconds max
public void processWithTimeout() { ... }

// 6. Use @Transactional at SERVICE level, not REPOSITORY level
// Repository methods are already transactional (Spring Data)

// 7. Monitor transaction metrics
// - Transaction duration (P95, P99)
// - Rollback rate
// - Connection pool utilization during transactions
```

### Transaction Monitoring

```java
@Aspect
@Component
public class TransactionMonitoringAspect {
    
    private final MeterRegistry meterRegistry;
    
    @Around("@annotation(transactional)")
    public Object monitorTransaction(ProceedingJoinPoint pjp, Transactional transactional) throws Throwable {
        String methodName = pjp.getSignature().toShortString();
        Timer.Sample sample = Timer.start(meterRegistry);
        
        try {
            Object result = pjp.proceed();
            sample.stop(Timer.builder("transaction.duration")
                .tag("method", methodName)
                .tag("outcome", "commit")
                .register(meterRegistry));
            return result;
        } catch (Exception e) {
            sample.stop(Timer.builder("transaction.duration")
                .tag("method", methodName)
                .tag("outcome", "rollback")
                .register(meterRegistry));
            meterRegistry.counter("transaction.rollback", "method", methodName).increment();
            throw e;
        }
    }
}
```

### Summary Decision Table

| Scenario | Propagation | Isolation | readOnly | timeout |
|----------|-------------|-----------|----------|---------|
| Simple CRUD write | REQUIRED | DEFAULT | false | 10s |
| Read query | REQUIRED | DEFAULT | true | 30s |
| Report generation | REQUIRED | REPEATABLE_READ | true | 60s |
| Audit logging | REQUIRES_NEW | DEFAULT | false | 5s |
| Money transfer | REQUIRED | SERIALIZABLE | false | 30s |
| Batch processing (per item) | REQUIRES_NEW | DEFAULT | false | 10s |
| Event publishing | REQUIRED | DEFAULT | false | 5s |
| Long read (no TX needed) | NOT_SUPPORTED | - | - | - |
