# Transaction Management in Spring Boot/JPA/Hibernate

## Q116: What is a Transaction? Explain ACID properties

A **transaction** is a logical unit of work that consists of one or more operations which must all succeed or all fail together.

### ACID Properties

| Property | Description |
|----------|-------------|
| **Atomicity** | All operations in a transaction succeed or all are rolled back. No partial completion. |
| **Consistency** | Transaction brings the database from one valid state to another valid state. All rules, constraints, and triggers are satisfied. |
| **Isolation** | Concurrent transactions do not interfere with each other. Each transaction sees a consistent snapshot. |
| **Durability** | Once a transaction is committed, the changes persist even in case of system failure. |

### Example

```java
// Transfer money: debit from A, credit to B
// Both must succeed or both must fail
@Transactional
public void transferMoney(Long fromAccountId, Long toAccountId, BigDecimal amount) {
    Account from = accountRepository.findById(fromAccountId).orElseThrow();
    Account to = accountRepository.findById(toAccountId).orElseThrow();
    
    from.setBalance(from.getBalance().subtract(amount)); // Debit
    to.setBalance(to.getBalance().add(amount));           // Credit
    
    accountRepository.save(from);
    accountRepository.save(to);
    // If any step fails, everything rolls back
}
```

---

## Q117: How does Spring manage transactions? (@Transactional)

Spring provides a **consistent abstraction** over different transaction APIs (JDBC, JPA, Hibernate, JTA) through the `PlatformTransactionManager` interface.

### How It Works

1. Spring uses **AOP proxies** to intercept calls to `@Transactional` methods
2. Before the method executes, Spring begins a transaction
3. If the method completes successfully, Spring commits
4. If a runtime exception is thrown, Spring rolls back

### Basic Usage

```java
@Service
public class OrderService {

    @Transactional
    public Order createOrder(OrderRequest request) {
        Order order = new Order(request);
        orderRepository.save(order);
        inventoryService.reduceStock(request.getItems());
        paymentService.charge(request.getPaymentDetails());
        return order;
    }
}
```

### Configuration

Spring Boot auto-configures transaction management. You just need:

```java
@SpringBootApplication // Includes @EnableTransactionManagement implicitly
public class Application { }
```

Or explicitly:

```java
@Configuration
@EnableTransactionManagement
public class TransactionConfig { }
```

### Transaction Flow (Proxy)

```
Client → Proxy (begin tx) → Actual Bean Method → Proxy (commit/rollback)
```

---

## Q118: What is the difference between programmatic and declarative transaction management?

### Declarative Transaction Management

Uses annotations or XML to define transaction boundaries. Spring handles the boilerplate.

```java
@Transactional
public void processOrder(Order order) {
    // business logic - Spring handles begin/commit/rollback
    orderRepository.save(order);
    notificationService.notify(order);
}
```

### Programmatic Transaction Management

You manually control the transaction in code using `TransactionTemplate` or `PlatformTransactionManager`.

```java
@Service
public class OrderService {

    private final TransactionTemplate transactionTemplate;

    public OrderService(PlatformTransactionManager txManager) {
        this.transactionTemplate = new TransactionTemplate(txManager);
    }

    public Order processOrder(Order order) {
        return transactionTemplate.execute(status -> {
            try {
                orderRepository.save(order);
                notificationService.notify(order);
                return order;
            } catch (Exception e) {
                status.setRollbackOnly();
                throw e;
            }
        });
    }
}
```

### Comparison

| Aspect | Declarative | Programmatic |
|--------|------------|--------------|
| Approach | Annotation/XML | Code-based |
| Boilerplate | Minimal | More verbose |
| Flexibility | Less (fixed boundaries) | More (fine-grained control) |
| Separation of Concerns | Better (tx logic separate from business logic) | Worse (mixed together) |
| Use Case | Most scenarios | Partial rollbacks, conditional tx logic |
| Testability | Easier to mock | Harder to isolate |

---

## Q119: Explain @Transactional annotation attributes

```java
@Transactional(
    propagation = Propagation.REQUIRED,
    isolation = Isolation.READ_COMMITTED,
    timeout = 30,
    readOnly = false,
    rollbackFor = {BusinessException.class},
    noRollbackFor = {LoggingException.class},
    transactionManager = "customTransactionManager"
)
public void someMethod() { }
```

### Attributes Explained

#### 1. propagation
Defines how the transaction relates to an existing transaction. Default: `REQUIRED`.

#### 2. isolation
Defines the isolation level of the transaction. Default: `DEFAULT` (database default).

#### 3. timeout
Maximum time (in seconds) the transaction is allowed to run before being automatically rolled back. Default: -1 (no timeout, uses underlying system default).

```java
@Transactional(timeout = 5) // rolls back if takes > 5 seconds
public void longRunningOperation() { }
```

#### 4. readOnly
Hints to the underlying infrastructure that this is a read-only transaction. Allows optimizations.

```java
@Transactional(readOnly = true)
public List<User> getAllUsers() {
    return userRepository.findAll();
}
```

#### 5. rollbackFor / noRollbackFor
Specifies which exceptions trigger rollback.

```java
// Rollback on checked exceptions too
@Transactional(rollbackFor = Exception.class)
public void riskyOperation() throws CheckedException { }

// Don't rollback on specific runtime exception
@Transactional(noRollbackFor = EmailSendFailException.class)
public void createUserAndNotify() { }
```

#### 6. transactionManager
Specifies which transaction manager to use (useful with multiple datasources).

```java
@Transactional(transactionManager = "secondaryTransactionManager")
public void writeToSecondaryDb() { }
```

---

## Q120: Explain all Transaction Propagation types

Propagation defines the behavior when a transactional method is called within an existing transaction context.

### 1. REQUIRED (Default)

Join existing transaction, or create a new one if none exists.

```java
@Transactional(propagation = Propagation.REQUIRED)
public void methodA() {
    methodB(); // joins methodA's transaction
}

@Transactional(propagation = Propagation.REQUIRED)
public void methodB() { }
```

### 2. REQUIRES_NEW

Always creates a new transaction. Suspends the existing one if present.

```java
@Transactional
public void processOrder(Order order) {
    orderRepository.save(order);
    auditService.logAudit(order); // runs in separate tx
}

// In AuditService
@Transactional(propagation = Propagation.REQUIRES_NEW)
public void logAudit(Order order) {
    // Even if processOrder rolls back, this audit is committed separately
    auditRepository.save(new AuditEntry(order));
}
```

### 3. SUPPORTS

Join existing transaction if one exists. Otherwise, execute non-transactionally.

```java
@Transactional(propagation = Propagation.SUPPORTS)
public User getUser(Long id) {
    return userRepository.findById(id).orElse(null);
}
```

### 4. NOT_SUPPORTED

Always execute non-transactionally. Suspends existing transaction if present.

```java
@Transactional(propagation = Propagation.NOT_SUPPORTED)
public void sendNotification(String message) {
    // Heavy operation that shouldn't hold a transaction open
    emailService.send(message);
}
```

### 5. MANDATORY

Must run within an existing transaction. Throws exception if no transaction exists.

```java
@Transactional(propagation = Propagation.MANDATORY)
public void updateInventory(Item item) {
    // Throws IllegalTransactionStateException if called without tx
    inventoryRepository.save(item);
}
```

### 6. NEVER

Must NOT run within a transaction. Throws exception if a transaction exists.

```java
@Transactional(propagation = Propagation.NEVER)
public void generateReport() {
    // Throws exception if called within a transaction
}
```

### 7. NESTED

Executes within a nested transaction (using savepoints) if a transaction exists. Falls back to REQUIRED behavior if no transaction exists.

```java
@Transactional(propagation = Propagation.NESTED)
public void addBonusPoints(Long userId) {
    // If this fails, only this nested part rolls back (to savepoint)
    // The outer transaction can continue
    pointsRepository.addPoints(userId, 100);
}
```

### Summary Table

| Propagation | Existing Tx? | No Existing Tx? |
|-------------|-------------|-----------------|
| REQUIRED | Join | Create new |
| REQUIRES_NEW | Suspend, create new | Create new |
| SUPPORTS | Join | Non-transactional |
| NOT_SUPPORTED | Suspend | Non-transactional |
| MANDATORY | Join | Exception |
| NEVER | Exception | Non-transactional |
| NESTED | Nested (savepoint) | Create new |

---

## Q121: Explain Transaction Isolation levels

Isolation levels control the degree to which one transaction is isolated from the effects of other concurrent transactions.

### 1. READ_UNCOMMITTED (Lowest isolation)

Allows reading uncommitted changes from other transactions (dirty reads).

```java
@Transactional(isolation = Isolation.READ_UNCOMMITTED)
public int getApproximateCount() {
    // May read data that another transaction hasn't committed yet
    return productRepository.count();
}
```

### 2. READ_COMMITTED

Only reads committed data. Prevents dirty reads. Default for most databases (PostgreSQL, Oracle, SQL Server).

```java
@Transactional(isolation = Isolation.READ_COMMITTED)
public Product getProduct(Long id) {
    // Will only see data committed by other transactions
    return productRepository.findById(id).orElseThrow();
}
```

### 3. REPEATABLE_READ

Guarantees that if you read a row twice in the same transaction, you get the same data. Prevents dirty reads and non-repeatable reads. Default for MySQL InnoDB.

```java
@Transactional(isolation = Isolation.REPEATABLE_READ)
public void reconcileBalance(Long accountId) {
    BigDecimal balance1 = getBalance(accountId);
    // ... other operations ...
    BigDecimal balance2 = getBalance(accountId);
    // balance1 == balance2 guaranteed
}
```

### 4. SERIALIZABLE (Highest isolation)

Full isolation. Transactions execute as if they were serial (one after another). Prevents all concurrency problems but lowest performance.

```java
@Transactional(isolation = Isolation.SERIALIZABLE)
public void criticalFinancialOperation() {
    // Highest safety, lowest concurrency
}
```

### Comparison

| Level | Dirty Read | Non-Repeatable Read | Phantom Read | Performance |
|-------|-----------|--------------------:|-------------|-------------|
| READ_UNCOMMITTED | Possible | Possible | Possible | Highest |
| READ_COMMITTED | Prevented | Possible | Possible | High |
| REPEATABLE_READ | Prevented | Prevented | Possible | Medium |
| SERIALIZABLE | Prevented | Prevented | Prevented | Lowest |

---

## Q122: What problems do isolation levels solve?

### 1. Dirty Read

Reading data that has been modified by another transaction that hasn't committed yet.

```
Transaction A:                    Transaction B:
UPDATE account SET balance=500    
WHERE id=1;                       
                                  SELECT balance FROM account 
                                  WHERE id=1; -- reads 500 (DIRTY!)
ROLLBACK;                         
                                  -- Transaction B used 500, but actual value is still original
```

**Solved by:** READ_COMMITTED and above.

### 2. Non-Repeatable Read

Reading the same row twice in a transaction yields different results because another committed transaction modified it between reads.

```
Transaction A:                    Transaction B:
SELECT balance FROM account 
WHERE id=1; -- returns 1000
                                  UPDATE account SET balance=500
                                  WHERE id=1;
                                  COMMIT;
SELECT balance FROM account
WHERE id=1; -- returns 500 (DIFFERENT!)
```

**Solved by:** REPEATABLE_READ and above.

### 3. Phantom Read

A query returns different sets of rows when executed twice because another committed transaction inserted/deleted rows matching the query criteria.

```
Transaction A:                    Transaction B:
SELECT * FROM orders 
WHERE status='PENDING'; 
-- returns 10 rows
                                  INSERT INTO orders(status) 
                                  VALUES('PENDING');
                                  COMMIT;
SELECT * FROM orders 
WHERE status='PENDING'; 
-- returns 11 rows (PHANTOM!)
```

**Solved by:** SERIALIZABLE.

### Practical Example

```java
@Service
public class AccountService {

    // Prevents dirty reads - safe for most read operations
    @Transactional(isolation = Isolation.READ_COMMITTED)
    public BigDecimal getBalance(Long accountId) {
        return accountRepository.findById(accountId)
            .map(Account::getBalance)
            .orElseThrow();
    }

    // Prevents non-repeatable reads - for operations reading same data multiple times
    @Transactional(isolation = Isolation.REPEATABLE_READ)
    public void transferWithValidation(Long fromId, Long toId, BigDecimal amount) {
        BigDecimal balance = getBalance(fromId);
        validateSufficientFunds(balance, amount);
        // balance won't change between validation and debit
        debit(fromId, amount);
        credit(toId, amount);
    }

    // Prevents phantom reads - for critical aggregate operations
    @Transactional(isolation = Isolation.SERIALIZABLE)
    public BigDecimal calculateTotalLiabilities() {
        // No new rows can appear during this calculation
        return accountRepository.findAll().stream()
            .map(Account::getBalance)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }
}
```

---

## Q123: What is @Transactional(readOnly = true)? What are its benefits?

`readOnly = true` hints that the transaction will only perform read operations. It enables several optimizations.

### Usage

```java
@Service
@Transactional(readOnly = true) // class-level default for reads
public class ProductQueryService {

    public List<Product> findAll() {
        return productRepository.findAll();
    }

    public Product findById(Long id) {
        return productRepository.findById(id).orElseThrow();
    }

    @Transactional // overrides: readOnly = false for writes
    public Product save(Product product) {
        return productRepository.save(product);
    }
}
```

### Benefits

#### 1. Hibernate Flush Mode Optimization
Hibernate sets flush mode to `MANUAL`, skipping dirty checking on all managed entities.

#### 2. No Dirty Checking Overhead
Hibernate doesn't need to compare entity snapshots at the end of the transaction, saving CPU and memory.

#### 3. Database-Level Optimizations
Some databases (e.g., PostgreSQL, MySQL) optimize read-only transactions:
- Skip write-ahead log (WAL) entries
- Reduce locking
- Route to read replicas

#### 4. Spring Data JPA / JDBC Routing
With master-slave setups, `readOnly = true` can route queries to read replicas:

```java
public class RoutingDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        return TransactionSynchronizationManager.isCurrentTransactionReadOnly()
            ? "replica"
            : "primary";
    }
}
```

#### 5. Prevents Accidental Writes
Acts as a safety net — if you accidentally call `save()`, some configurations will throw an exception.

### Performance Impact

For a service reading 10,000 entities:
- Without `readOnly`: Hibernate maintains snapshots for all 10K entities for dirty checking
- With `readOnly`: No snapshots maintained, significantly less memory and CPU

---

## Q124: What is the difference between @Transactional at class level vs method level?

### Class-Level

Applies to **all public methods** of the class.

```java
@Service
@Transactional
public class UserService {

    public User createUser(UserDto dto) { } // transactional

    public void deleteUser(Long id) { }     // transactional

    public User getUser(Long id) { }        // transactional (but ideally should be readOnly)
}
```

### Method-Level

Applies only to the annotated method. **Overrides class-level** settings.

```java
@Service
@Transactional(readOnly = true) // default for all methods
public class UserService {

    public List<User> findAll() { }  // readOnly = true (from class)

    public User findById(Long id) { }  // readOnly = true (from class)

    @Transactional // overrides: readOnly = false, propagation = REQUIRED
    public User createUser(UserDto dto) {
        return userRepository.save(new User(dto));
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void auditAction(String action) { }  // completely overrides class-level
}
```

### Best Practice

```java
@Service
@Transactional(readOnly = true) // safe default
public class OrderService {

    // Read methods inherit readOnly = true
    public Order findById(Long id) { return orderRepository.findById(id).orElseThrow(); }
    public List<Order> findByUser(Long userId) { return orderRepository.findByUserId(userId); }

    // Write methods explicitly override
    @Transactional
    public Order create(OrderRequest req) { return orderRepository.save(new Order(req)); }

    @Transactional
    public void cancel(Long orderId) { orderRepository.updateStatus(orderId, Status.CANCELLED); }
}
```

---

## Q125: Why does @Transactional not work on private methods?

### Reason: Spring AOP Proxy Mechanism

Spring uses **proxies** (JDK dynamic proxy or CGLIB) to implement `@Transactional`. Proxies can only intercept **public** method calls from external callers.

```java
@Service
public class UserService {

    @Transactional
    public void createUser(UserDto dto) { } // ✅ Works - public, called through proxy

    @Transactional
    private void internalSave(User user) { } // ❌ NEVER works - private, proxy can't override
    
    @Transactional
    protected void protectedMethod() { } // ❌ Doesn't work with JDK proxy, works with CGLIB but not recommended
}
```

### Why Proxy Can't Intercept Private Methods

```
Client → Spring Proxy (intercepts public methods) → Target Bean
                ↓
         begin transaction
         call target.createUser()
         commit/rollback
```

- **JDK Dynamic Proxy**: Implements interfaces. Private methods aren't part of any interface.
- **CGLIB Proxy**: Creates a subclass. Private methods cannot be overridden in subclasses.

### What Happens at Compile Time

Spring doesn't throw an error — it **silently ignores** `@Transactional` on private methods. This is a dangerous gotcha.

### Solution

Keep `@Transactional` methods **public**:

```java
@Service
public class UserService {

    @Transactional
    public void createUser(UserDto dto) {
        User user = mapToEntity(dto);
        saveUser(user); // internal call - no separate tx needed
    }

    private void saveUser(User user) {
        userRepository.save(user);  // participates in createUser's transaction
    }
}
```

### AspectJ Alternative

If you truly need `@Transactional` on private methods, use AspectJ compile-time or load-time weaving:

```java
@EnableTransactionManagement(mode = AdviceMode.ASPECTJ)
@Configuration
public class TransactionConfig { }
```

---

## Q126: What is the self-invocation problem with @Transactional? How to solve it?

### The Problem

When a method within the same class calls another `@Transactional` method, the proxy is bypassed. The called method's transaction settings are ignored.

```java
@Service
public class OrderService {

    public void processOrder(OrderRequest request) {
        // This is a SELF-INVOCATION - bypasses the proxy!
        createOrder(request); // @Transactional is IGNORED
    }

    @Transactional
    public void createOrder(OrderRequest request) {
        orderRepository.save(new Order(request));
        paymentService.charge(request); // No transaction wrapping this!
    }
}
```

### Why It Happens

```
Client → Proxy.processOrder() → this.createOrder()  [bypasses proxy!]
                                  ↑
                          Direct call to target object,
                          NOT through the proxy
```

The `this` reference inside the bean points to the actual object, not the proxy.

### Solutions

#### 1. Refactor into Separate Service (Recommended)

```java
@Service
public class OrderFacade {
    
    private final OrderService orderService;

    public void processOrder(OrderRequest request) {
        orderService.createOrder(request); // Goes through proxy ✅
    }
}

@Service
public class OrderService {

    @Transactional
    public void createOrder(OrderRequest request) {
        orderRepository.save(new Order(request));
    }
}
```

#### 2. Self-Inject the Proxy

```java
@Service
public class OrderService {

    @Lazy
    @Autowired
    private OrderService self; // Injects the proxy

    public void processOrder(OrderRequest request) {
        self.createOrder(request); // Goes through proxy ✅
    }

    @Transactional
    public void createOrder(OrderRequest request) {
        orderRepository.save(new Order(request));
    }
}
```

#### 3. Use ApplicationContext

```java
@Service
public class OrderService {

    @Autowired
    private ApplicationContext context;

    public void processOrder(OrderRequest request) {
        context.getBean(OrderService.class).createOrder(request); // Proxy ✅
    }

    @Transactional
    public void createOrder(OrderRequest request) {
        orderRepository.save(new Order(request));
    }
}
```

#### 4. Use AspectJ Weaving

```java
@EnableTransactionManagement(mode = AdviceMode.ASPECTJ)
```

This weaves transaction logic directly into the bytecode, eliminating the proxy entirely.

---

## Q127: What is the difference between checked and unchecked exception handling in @Transactional?

### Default Behavior

| Exception Type | Default Rollback? |
|---------------|-------------------|
| `RuntimeException` (unchecked) | **Yes** - auto rollback |
| `Error` | **Yes** - auto rollback |
| Checked `Exception` | **No** - commits normally |

### Example of Default Behavior

```java
@Transactional
public void createUser(UserDto dto) throws CustomCheckedException {
    userRepository.save(new User(dto));
    
    if (someCondition) {
        throw new RuntimeException("fails"); // ✅ Transaction ROLLS BACK
    }
    
    if (otherCondition) {
        throw new CustomCheckedException("fails"); // ❌ Transaction COMMITS!
    }
}
```

### Customizing Rollback Behavior

#### Rollback on Checked Exceptions

```java
@Transactional(rollbackFor = Exception.class) // rollback on ALL exceptions
public void riskyOperation() throws IOException {
    // Now rolls back on IOException too
}

@Transactional(rollbackFor = {BusinessException.class, IOException.class})
public void specificRollback() throws BusinessException, IOException { }
```

#### Don't Rollback on Specific Runtime Exceptions

```java
@Transactional(noRollbackFor = NotificationFailureException.class)
public void createOrderWithNotification(Order order) {
    orderRepository.save(order);
    try {
        notificationService.send(order); // may throw NotificationFailureException
    } catch (NotificationFailureException e) {
        log.warn("Notification failed, but order is saved", e);
        throw e; // transaction still commits
    }
}
```

### Best Practice

```java
// Be explicit about rollback behavior
@Transactional(rollbackFor = Exception.class) // safest: rollback on everything
public void criticalOperation() throws Exception {
    // ...
}
```

### Why This Design?

Spring follows EJB conventions where:
- Checked exceptions are "expected" business conditions (recoverable)
- Unchecked exceptions are "unexpected" failures (unrecoverable)

Most modern applications override this with `rollbackFor = Exception.class`.

---

## Q128: How does Spring Transaction proxy work? (AOP-based)

### Architecture

```
Caller → TransactionInterceptor (AOP Proxy) → Target Method
              ↓                                      ↓
     1. Get TransactionManager              4. Execute business logic
     2. Begin Transaction                   5. Return result or throw
     3. Set up synchronization              
              ↓
     6. Commit (on success) OR Rollback (on exception)
```

### Proxy Creation

Spring creates a proxy around `@Transactional` beans at startup:

```java
// What you write:
@Service
public class UserService {
    @Transactional
    public void save(User user) { userRepository.save(user); }
}

// What Spring creates (conceptually):
public class UserService$$EnhancerBySpringCGLIB extends UserService {
    private UserService target;
    private PlatformTransactionManager txManager;

    @Override
    public void save(User user) {
        TransactionStatus status = txManager.getTransaction(new DefaultTransactionDefinition());
        try {
            target.save(user);  // call actual method
            txManager.commit(status);
        } catch (RuntimeException e) {
            txManager.rollback(status);
            throw e;
        }
    }
}
```

### Two Proxy Types

#### JDK Dynamic Proxy (interface-based)
```java
public interface UserService { void save(User user); }

@Service
public class UserServiceImpl implements UserService { }
// Spring creates: Proxy implementing UserService interface
```

#### CGLIB Proxy (subclass-based, default in Spring Boot)
```java
@Service
public class UserService { } // no interface needed
// Spring creates: UserService$$EnhancerBySpringCGLIB extends UserService
```

### TransactionInterceptor Internals

The key class is `TransactionInterceptor` which extends `TransactionAspectSupport`:

```java
// Simplified internal logic
public Object invoke(MethodInvocation invocation) {
    // 1. Get transaction attribute (@Transactional settings)
    TransactionAttribute txAttr = getTransactionAttribute(method);
    
    // 2. Determine transaction manager
    PlatformTransactionManager tm = determineTransactionManager(txAttr);
    
    // 3. Create/join transaction based on propagation
    TransactionInfo txInfo = createTransactionIfNecessary(tm, txAttr, methodId);
    
    Object result;
    try {
        // 4. Invoke actual method
        result = invocation.proceed();
    } catch (Throwable ex) {
        // 5. Handle exception (rollback if applicable)
        completeTransactionAfterThrowing(txInfo, ex);
        throw ex;
    }
    
    // 6. Commit on success
    commitTransactionAfterReturning(txInfo);
    return result;
}
```

### Verifying Proxy at Runtime

```java
@Autowired
private UserService userService;

@PostConstruct
public void checkProxy() {
    System.out.println(userService.getClass().getName());
    // Output: com.example.UserService$$EnhancerBySpringCGLIB$$abc123
    System.out.println(AopUtils.isAopProxy(userService)); // true
}
```

---

## Q129: What is TransactionTemplate for programmatic transactions?

`TransactionTemplate` provides programmatic transaction management with a callback pattern, similar to `JdbcTemplate`.

### Basic Usage

```java
@Service
public class PaymentService {

    private final TransactionTemplate transactionTemplate;
    private final PaymentRepository paymentRepository;

    public PaymentService(PlatformTransactionManager txManager,
                          PaymentRepository paymentRepository) {
        this.transactionTemplate = new TransactionTemplate(txManager);
        this.paymentRepository = paymentRepository;
    }

    // With return value
    public Payment processPayment(PaymentRequest request) {
        return transactionTemplate.execute(status -> {
            Payment payment = new Payment(request);
            paymentRepository.save(payment);
            externalGateway.charge(request);
            return payment;
        });
    }

    // Without return value
    public void deleteExpiredPayments() {
        transactionTemplate.executeWithoutResult(status -> {
            paymentRepository.deleteByExpiryBefore(LocalDate.now());
        });
    }
}
```

### Configuring TransactionTemplate

```java
TransactionTemplate template = new TransactionTemplate(txManager);
template.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
template.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
template.setTimeout(10);
template.setReadOnly(false);
```

### Manual Rollback

```java
transactionTemplate.execute(status -> {
    try {
        performOperation();
    } catch (BusinessException e) {
        status.setRollbackOnly(); // mark for rollback
        return null;
    }
    return result;
});
```

### When to Use

- Need partial transaction control within a method
- Conditional transaction boundaries
- Multiple independent transactions in one method

```java
public void batchProcess(List<Order> orders) {
    for (Order order : orders) {
        transactionTemplate.executeWithoutResult(status -> {
            try {
                processOrder(order); // each order in its own transaction
            } catch (Exception e) {
                status.setRollbackOnly(); // only this order rolls back
                log.error("Failed to process order: {}", order.getId(), e);
            }
        });
    }
}
```

---

## Q130: What is PlatformTransactionManager?

`PlatformTransactionManager` is Spring's central interface for transaction management. It abstracts the underlying transaction infrastructure.

### Interface Definition

```java
public interface PlatformTransactionManager extends TransactionManager {
    TransactionStatus getTransaction(TransactionDefinition definition) 
        throws TransactionException;
    void commit(TransactionStatus status) throws TransactionException;
    void rollback(TransactionStatus status) throws TransactionException;
}
```

### Implementations

| Implementation | Use Case |
|---------------|----------|
| `DataSourceTransactionManager` | Plain JDBC |
| `JpaTransactionManager` | JPA/Hibernate |
| `HibernateTransactionManager` | Native Hibernate |
| `JtaTransactionManager` | Distributed (XA) transactions |
| `ChainedTransactionManager` | Multiple datasources (best effort) |

### Auto-Configuration in Spring Boot

Spring Boot auto-configures the appropriate transaction manager:

```java
// With spring-boot-starter-data-jpa:
// Auto-configures JpaTransactionManager

// With spring-boot-starter-jdbc (no JPA):
// Auto-configures DataSourceTransactionManager
```

### Custom Configuration

```java
@Configuration
public class TransactionConfig {

    @Bean
    @Primary
    public PlatformTransactionManager primaryTransactionManager(EntityManagerFactory emf) {
        return new JpaTransactionManager(emf);
    }

    @Bean
    public PlatformTransactionManager secondaryTransactionManager(
            @Qualifier("secondaryDataSource") DataSource dataSource) {
        return new DataSourceTransactionManager(dataSource);
    }
}
```

### Direct Usage (Low-Level Programmatic)

```java
@Service
public class LowLevelService {

    private final PlatformTransactionManager txManager;

    public void manualTransaction() {
        DefaultTransactionDefinition def = new DefaultTransactionDefinition();
        def.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRED);
        
        TransactionStatus status = txManager.getTransaction(def);
        try {
            // business logic
            repository.save(entity);
            txManager.commit(status);
        } catch (Exception e) {
            txManager.rollback(status);
            throw e;
        }
    }
}
```

---

## Q131: How to handle transactions with multiple datasources?

### Challenge

A single `@Transactional` only applies to one transaction manager. Operations spanning multiple databases need special handling.

### Approach 1: Separate Transaction Managers

```java
@Configuration
public class MultiDataSourceConfig {

    @Bean
    @Primary
    public PlatformTransactionManager primaryTxManager(
            @Qualifier("primaryEntityManagerFactory") EntityManagerFactory emf) {
        return new JpaTransactionManager(emf);
    }

    @Bean
    public PlatformTransactionManager secondaryTxManager(
            @Qualifier("secondaryEntityManagerFactory") EntityManagerFactory emf) {
        return new JpaTransactionManager(emf);
    }
}

@Service
public class MultiDbService {

    @Transactional("primaryTxManager")
    public void writeToPrimary() { }

    @Transactional("secondaryTxManager")
    public void writeToSecondary() { }
}
```

### Approach 2: ChainedTransactionManager (Best Effort 1PC)

Commits multiple transaction managers in sequence. Not truly atomic — if the second commit fails, the first is already committed.

```java
@Bean
public PlatformTransactionManager chainedTxManager(
        PlatformTransactionManager primaryTxManager,
        PlatformTransactionManager secondaryTxManager) {
    return new ChainedTransactionManager(primaryTxManager, secondaryTxManager);
}

@Transactional("chainedTxManager")
public void writeToMultipleDbs() {
    primaryRepo.save(entity1);
    secondaryRepo.save(entity2);
    // Both committed in sequence (secondary first, then primary)
}
```

> **Note:** `ChainedTransactionManager` is deprecated. Consider JTA or the Saga pattern instead.

### Approach 3: JTA (Java Transaction API) - True Distributed Transactions

Uses a JTA transaction manager (like Atomikos or Narayana) for true 2PC.

```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-jta-atomikos</artifactId>
</dependency>
```

```java
@Configuration
public class JtaConfig {

    @Bean
    public DataSource primaryDataSource() {
        AtomikosDataSourceBean ds = new AtomikosDataSourceBean();
        ds.setUniqueResourceName("primary");
        ds.setXaDataSourceClassName("org.postgresql.xa.PGXADataSource");
        // configure properties
        return ds;
    }

    @Bean
    public DataSource secondaryDataSource() {
        AtomikosDataSourceBean ds = new AtomikosDataSourceBean();
        ds.setUniqueResourceName("secondary");
        ds.setXaDataSourceClassName("com.mysql.cj.jdbc.MysqlXADataSource");
        return ds;
    }
}

// Now a single @Transactional spans both databases atomically
@Transactional
public void distributedWrite() {
    primaryRepo.save(entity1);   // PostgreSQL
    secondaryRepo.save(entity2); // MySQL
    // Truly atomic across both
}
```

### Approach 4: Saga Pattern (Microservices)

For distributed systems where 2PC is impractical:

```java
@Service
public class OrderSaga {

    public void createOrder(OrderRequest request) {
        try {
            Order order = orderService.create(request);        // Step 1
            Payment payment = paymentService.charge(request);  // Step 2
            inventoryService.reserve(request);                  // Step 3
        } catch (PaymentFailedException e) {
            orderService.cancel(order.getId());                // Compensate Step 1
        } catch (InventoryException e) {
            paymentService.refund(payment.getId());            // Compensate Step 2
            orderService.cancel(order.getId());                // Compensate Step 1
        }
    }
}
```

---

## Q132: What is two-phase commit (2PC)?

Two-phase commit is a distributed protocol ensuring all participants in a distributed transaction either commit or abort together.

### Phases

#### Phase 1: Prepare (Voting)

The coordinator asks all participants: "Can you commit?"

```
Coordinator → Participant A: PREPARE
Coordinator → Participant B: PREPARE

Participant A → Coordinator: YES (prepared/ready)
Participant B → Coordinator: YES (prepared/ready)
```

Each participant:
- Executes the transaction locally
- Writes changes to a persistent log (but doesn't commit)
- Acquires all necessary locks
- Responds YES (can commit) or NO (cannot commit)

#### Phase 2: Commit/Abort (Decision)

If ALL participants voted YES:
```
Coordinator → Participant A: COMMIT
Coordinator → Participant B: COMMIT
```

If ANY participant voted NO (or timed out):
```
Coordinator → Participant A: ABORT
Coordinator → Participant B: ABORT
```

### Implementation with JTA/XA

```java
// Spring + Atomikos handles 2PC transparently
@Transactional
public void transferBetweenBanks(TransferRequest request) {
    // XA Resource 1: Debit from Bank A (PostgreSQL)
    bankARepository.debit(request.getFromAccount(), request.getAmount());
    
    // XA Resource 2: Credit to Bank B (MySQL)
    bankBRepository.credit(request.getToAccount(), request.getAmount());
    
    // Atomikos coordinates 2PC:
    // Phase 1: Both DBs prepare
    // Phase 2: Both DBs commit (or both abort)
}
```

### Drawbacks of 2PC

| Issue | Description |
|-------|-------------|
| **Blocking** | Participants hold locks until the protocol completes |
| **Single Point of Failure** | If coordinator crashes after prepare, participants are stuck |
| **Performance** | Additional network round trips and disk writes |
| **Availability** | Any participant being unavailable blocks the whole transaction |

### Alternatives

- **Saga Pattern**: Compensating transactions for eventual consistency
- **Outbox Pattern**: Reliable event publishing with local transactions
- **TCC (Try-Confirm-Cancel)**: Business-level 2PC without XA

---

## Q133: What is @TransactionalEventListener?

`@TransactionalEventListener` processes events only after a transaction completes (or at a specific phase). This ensures event handlers only execute when the triggering transaction succeeds.

### Problem with Regular @EventListener

```java
// PROBLEM: Event fires even if transaction rolls back!
@EventListener
public void handleOrderCreated(OrderCreatedEvent event) {
    emailService.sendConfirmation(event.getOrder()); // Email sent even if order save rolls back!
}
```

### Solution: @TransactionalEventListener

```java
@Component
public class OrderEventHandler {

    // Only fires AFTER the transaction commits successfully
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleOrderCreated(OrderCreatedEvent event) {
        emailService.sendConfirmation(event.getOrder());
    }

    // Fires after rollback
    @TransactionalEventListener(phase = TransactionPhase.AFTER_ROLLBACK)
    public void handleOrderFailed(OrderCreatedEvent event) {
        log.error("Order creation failed: {}", event.getOrder().getId());
    }

    // Fires after completion (commit or rollback)
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMPLETION)
    public void cleanUp(OrderCreatedEvent event) {
        cacheService.invalidate(event.getOrder().getId());
    }

    // Fires before commit (still within the transaction)
    @TransactionalEventListener(phase = TransactionPhase.BEFORE_COMMIT)
    public void validateBeforeCommit(OrderCreatedEvent event) {
        auditRepository.save(new AuditEntry(event)); // participates in same tx
    }
}
```

### Publishing Events

```java
@Service
public class OrderService {

    private final ApplicationEventPublisher eventPublisher;

    @Transactional
    public Order createOrder(OrderRequest request) {
        Order order = orderRepository.save(new Order(request));
        
        // Event is registered but not delivered yet
        eventPublisher.publishEvent(new OrderCreatedEvent(order));
        
        return order;
        // After this method returns and tx commits, AFTER_COMMIT listeners fire
    }
}
```

### Transaction Phases

| Phase | When | In Transaction? |
|-------|------|-----------------|
| `BEFORE_COMMIT` | Just before commit | Yes |
| `AFTER_COMMIT` (default) | After successful commit | No |
| `AFTER_ROLLBACK` | After rollback | No |
| `AFTER_COMPLETION` | After commit or rollback | No |

### Important: fallbackExecution

By default, if no transaction is active, the event is **not processed**. Use `fallbackExecution`:

```java
@TransactionalEventListener(fallbackExecution = true)
public void handle(MyEvent event) {
    // Executes even if there's no active transaction
}
```

---

## Q134: How to test transactions in Spring Boot?

### 1. @Transactional in Tests (Auto-Rollback)

By default, `@Transactional` on test methods rolls back after each test.

```java
@SpringBootTest
@Transactional // Each test auto-rolls back
class UserServiceTest {

    @Autowired
    private UserService userService;

    @Autowired
    private UserRepository userRepository;

    @Test
    void shouldCreateUser() {
        userService.createUser(new UserDto("John", "john@test.com"));
        
        assertEquals(1, userRepository.count());
        // Auto-rolls back after test - DB is clean
    }
}
```

### 2. Testing Rollback Behavior

```java
@SpringBootTest
class TransactionRollbackTest {

    @Autowired
    private OrderService orderService;

    @Autowired
    private OrderRepository orderRepository;

    @Test
    void shouldRollbackOnException() {
        assertThrows(InsufficientFundsException.class, () ->
            orderService.createOrder(invalidRequest)
        );

        // Verify nothing was persisted
        assertEquals(0, orderRepository.count());
    }
}
```

### 3. Testing Propagation with @Commit

```java
@SpringBootTest
class PropagationTest {

    @Test
    @Commit // or @Rollback(false) - actually commits to DB
    void shouldPersistData() {
        // Use with caution - leaves data in DB
    }
}
```

### 4. Testing Transaction Boundaries

```java
@SpringBootTest
class TransactionBoundaryTest {

    @Autowired
    private UserService userService;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    @Transactional
    void shouldLazyLoadWithinTransaction() {
        User user = userService.findWithOrders(1L);
        // Lazy collection accessible within test's transaction
        assertFalse(user.getOrders().isEmpty());
    }
}
```

### 5. Verifying Transaction Isolation

```java
@SpringBootTest
class IsolationTest {

    @Autowired
    private AccountService accountService;

    @Test
    void shouldHandleConcurrentAccess() throws Exception {
        Long accountId = createAccountWithBalance(1000);

        ExecutorService executor = Executors.newFixedThreadPool(2);
        
        Future<?> f1 = executor.submit(() -> accountService.debit(accountId, 600));
        Future<?> f2 = executor.submit(() -> accountService.debit(accountId, 600));

        // One should succeed, one should fail (insufficient funds)
        // Verifies isolation prevents double-spending
    }
}
```

### 6. Using TransactionTemplate in Tests

```java
@SpringBootTest
class ManualTxTest {

    @Autowired
    private TransactionTemplate txTemplate;

    @Autowired
    private UserRepository userRepository;

    @Test
    void shouldVerifyDataAfterCommit() {
        Long userId = txTemplate.execute(status -> {
            User user = userRepository.save(new User("John"));
            return user.getId();
        });

        // New transaction to verify
        txTemplate.executeWithoutResult(status -> {
            assertTrue(userRepository.findById(userId).isPresent());
            status.setRollbackOnly(); // clean up
        });
    }
}
```

### 7. TestTransaction Utility

```java
@SpringBootTest
@Transactional
class TestTransactionUtilTest {

    @Test
    void shouldUseTestTransaction() {
        userRepository.save(new User("John"));
        
        // Force flush and commit mid-test
        TestTransaction.flagForCommit();
        TestTransaction.end();
        
        // Start a new transaction
        TestTransaction.start();
        assertEquals(1, userRepository.count());
    }
}
```

---

## Q135: What are common @Transactional pitfalls and best practices?

### Common Pitfalls

#### 1. Self-Invocation (Most Common)

```java
// ❌ WRONG: @Transactional ignored on internal call
@Service
public class UserService {
    public void register(UserDto dto) {
        saveUser(dto); // self-invocation - NO transaction!
    }

    @Transactional
    public void saveUser(UserDto dto) { userRepository.save(new User(dto)); }
}
```

#### 2. Private/Protected Methods

```java
// ❌ WRONG: @Transactional silently ignored
@Transactional
private void saveInternal() { }
```

#### 3. Catching Exceptions Inside

```java
// ❌ WRONG: Swallowing exception prevents rollback
@Transactional
public void process() {
    try {
        riskyOperation();
    } catch (Exception e) {
        log.error("Failed", e); // Transaction commits despite failure!
    }
}
```

#### 4. Long-Running Transactions

```java
// ❌ WRONG: Holds DB connection for the entire HTTP call + email send
@Transactional
public void createAndNotify(UserDto dto) {
    userRepository.save(new User(dto));
    emailService.sendWelcomeEmail(dto.getEmail()); // Slow network call inside tx!
}
```

#### 5. Checked Exception Not Rolling Back

```java
// ❌ WRONG: Checked exception = no rollback by default
@Transactional
public void transfer() throws InsufficientFundsException {
    throw new InsufficientFundsException(); // Transaction COMMITS!
}
```

#### 6. Missing @EnableTransactionManagement (rare in Boot)

Non-Boot projects may forget this, silently disabling all `@Transactional`.

#### 7. Wrong Transaction Manager

```java
// ❌ WRONG: Using JPA repo but JDBC transaction manager
@Transactional("jdbcTransactionManager")
public void jpaOperation() {
    jpaRepository.save(entity); // May not be managed correctly
}
```

### Best Practices

#### 1. Keep Transactions Short

```java
// ✅ GOOD: Only the DB operation is transactional
@Service
public class OrderService {

    @Transactional
    public Order createOrder(OrderRequest req) {
        return orderRepository.save(new Order(req));
    }

    // Non-transactional orchestration
    public OrderResponse processOrder(OrderRequest req) {
        Order order = createOrder(req);          // short tx
        emailService.sendConfirmation(order);     // outside tx
        return new OrderResponse(order);
    }
}
```

#### 2. Use readOnly for Queries

```java
// ✅ GOOD
@Service
@Transactional(readOnly = true)
public class ReportService {
    public Report generateReport() { return reportRepository.getReport(); }
    
    @Transactional
    public void saveReport(Report report) { reportRepository.save(report); }
}
```

#### 3. Explicit rollbackFor

```java
// ✅ GOOD: Explicit about rollback behavior
@Transactional(rollbackFor = Exception.class)
public void criticalOperation() throws Exception { }
```

#### 4. Use Events for Post-Commit Actions

```java
// ✅ GOOD: Email only sent after successful commit
@Transactional
public Order createOrder(OrderRequest req) {
    Order order = orderRepository.save(new Order(req));
    eventPublisher.publishEvent(new OrderCreatedEvent(order));
    return order;
}

@TransactionalEventListener
public void onOrderCreated(OrderCreatedEvent event) {
    emailService.sendConfirmation(event.getOrder());
}
```

#### 5. Set Timeouts

```java
// ✅ GOOD: Prevents indefinite blocking
@Transactional(timeout = 5)
public void timeSensitiveOperation() { }
```

#### 6. Avoid Returning Lazy Entities Outside Transaction

```java
// ❌ WRONG
@Transactional
public User getUser(Long id) {
    return userRepository.findById(id).orElseThrow();
    // After method returns, tx closes. Accessing user.getOrders() → LazyInitializationException
}

// ✅ GOOD: Use DTO or fetch eagerly
@Transactional(readOnly = true)
public UserDto getUser(Long id) {
    User user = userRepository.findById(id).orElseThrow();
    return new UserDto(user.getName(), user.getOrders().size()); // accessed within tx
}
```

#### 7. Log Transaction Issues

```properties
# application.properties - debug transaction behavior
logging.level.org.springframework.transaction=DEBUG
logging.level.org.springframework.orm.jpa=DEBUG
```

### Summary Checklist

- [ ] Methods are `public`
- [ ] No self-invocation
- [ ] Transactions are short (no external calls inside)
- [ ] `readOnly = true` for queries
- [ ] `rollbackFor = Exception.class` for critical operations
- [ ] Timeout set for long-running operations
- [ ] Post-commit actions use `@TransactionalEventListener`
- [ ] No lazy loading outside transaction boundaries
- [ ] Exceptions not swallowed inside `@Transactional` methods
