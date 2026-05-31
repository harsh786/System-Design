# Testing Strategies at Scale (Staff Engineer / Architect Level)

Testing JPA/Hibernate applications properly is one of the most misunderstood areas in Spring Boot development. Most teams either over-mock (hiding real bugs) or under-test (missing critical data layer issues). This guide covers battle-tested patterns for testing at scale.

---

## 1. Integration Testing with JPA/Hibernate

### @DataJpaTest vs @SpringBootTest

```java
// @DataJpaTest — thin slice, only JPA components
// Loads: EntityManager, Repositories, Flyway/Liquibase, DataSource
// Does NOT load: Controllers, Services, Security, etc.
@DataJpaTest
class OrderRepositoryTest {
    @Autowired
    private TestEntityManager entityManager; // flush/find helpers
    
    @Autowired
    private OrderRepository orderRepository;
    
    @Test
    void shouldFindOrdersByCustomerId() {
        // Given
        Customer customer = entityManager.persistAndFlush(new Customer("Alice"));
        entityManager.persistAndFlush(new Order(customer, BigDecimal.valueOf(100)));
        entityManager.persistAndFlush(new Order(customer, BigDecimal.valueOf(200)));
        entityManager.clear(); // detach all — forces fresh queries
        
        // When
        List<Order> orders = orderRepository.findByCustomerId(customer.getId());
        
        // Then
        assertThat(orders).hasSize(2);
    }
}

// @SpringBootTest — full context, use when testing cross-cutting concerns
// Use when: testing transactional boundaries, caching, event listeners,
// service-to-repository interaction, or multi-layer flows
@SpringBootTest
@Transactional // BE CAREFUL — read section on why this hides bugs
class OrderServiceIntegrationTest {
    @Autowired
    private OrderService orderService;
    
    @Autowired
    private EntityManager entityManager;
    
    @Test
    void shouldCreateOrderWithAuditFields() {
        OrderRequest request = new OrderRequest("SKU-001", 5);
        Order order = orderService.placeOrder(request);
        
        assertThat(order.getCreatedAt()).isNotNull();
        assertThat(order.getVersion()).isEqualTo(0);
    }
}
```

**Decision Matrix:**

| Scenario | Use |
|----------|-----|
| Testing custom query methods | `@DataJpaTest` |
| Testing entity mappings / constraints | `@DataJpaTest` |
| Testing service transactional behavior | `@SpringBootTest` |
| Testing cache + repository interaction | `@SpringBootTest` |
| Testing event listeners (e.g., `@EntityListeners`) | `@DataJpaTest` |
| Testing multi-service orchestration | `@SpringBootTest` |

### @AutoConfigureTestDatabase: REPLACE vs NONE

```java
// REPLACE (default with @DataJpaTest) — replaces your DataSource with embedded H2
// This is DANGEROUS for production-like testing
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
// ^^^ ALWAYS use NONE when testing with Testcontainers or real DB
class OrderRepositoryTest {
    // Now uses whatever DataSource is configured (e.g., Testcontainers)
}
```

**Why REPLACE is dangerous:**
- Silently swaps your PostgreSQL/MySQL config with H2
- Tests pass locally but fail in production
- You never test your actual dialect, indexes, or constraints

### Why H2 Tests Are Unreliable

```sql
-- Things that work differently or don't work in H2:

-- 1. JSON columns
-- PostgreSQL: jsonb operators @>, ?, #>>
-- H2: No native JSONB support, "compatibility mode" is superficial

-- 2. Locking behavior
-- PostgreSQL: SELECT ... FOR UPDATE SKIP LOCKED (used in job queues)
-- H2: Doesn't support SKIP LOCKED

-- 3. Window functions differences
-- PostgreSQL: Full window function support with FILTER clause
-- H2: Limited window function support

-- 4. Array types
-- PostgreSQL: Native array types with operators (ANY, ALL, @>)
-- H2: Arrays behave differently

-- 5. Partial indexes
-- PostgreSQL: CREATE INDEX idx ON orders(status) WHERE deleted = false
-- H2: Not supported

-- 6. CTEs with INSERT/UPDATE (writeable CTEs)
-- PostgreSQL: WITH updated AS (UPDATE ... RETURNING *) SELECT ...
-- H2: Not supported

-- 7. Advisory locks
-- PostgreSQL: pg_advisory_lock(), pg_try_advisory_lock()
-- H2: Not available

-- 8. LISTEN/NOTIFY
-- PostgreSQL: Pub/sub built into DB
-- H2: Not available
```

```java
// REAL EXAMPLE: This test passes with H2, fails with PostgreSQL
@DataJpaTest // defaults to H2
class BrokenH2Test {
    
    @Test
    void testCaseSensitivity() {
        // H2 default: case-insensitive identifiers
        // PostgreSQL: case-sensitive unless quoted
        // Your @Column(name = "userId") might map differently
    }
    
    @Test
    void testTransactionIsolation() {
        // H2 default: SERIALIZABLE-like behavior
        // PostgreSQL default: READ COMMITTED
        // Phantom reads that happen in prod won't appear in H2 tests
    }
    
    @Test
    void testSequenceGeneration() {
        // H2 uses different sequence caching strategy
        // Gaps in IDs behave differently
        // GENERATED ALWAYS AS IDENTITY has subtle differences
    }
}
```

### Testcontainers Setup with JUnit 5

```java
// build.gradle / pom.xml dependencies
// testImplementation 'org.testcontainers:postgresql:1.19.3'
// testImplementation 'org.testcontainers:junit-jupiter:1.19.3'

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Testcontainers
class OrderRepositoryTestcontainersTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("testdb")
            .withUsername("test")
            .withPassword("test")
            .withInitScript("schema/init.sql"); // optional: pre-load schema

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "validate");
        // Use "validate" — let Flyway handle schema, Hibernate only validates
    }

    @Autowired
    private OrderRepository orderRepository;

    @Test
    void shouldUsePostgreSQLNativeQuery() {
        // This actually runs against PostgreSQL — no dialect surprises
        List<Order> orders = orderRepository.findOrdersWithJsonFilter(
            "{\"priority\": \"high\"}"
        );
        assertThat(orders).isEmpty();
    }
}
```

### Singleton Container Pattern (Performance)

Starting a new container per test class is slow (~2-5 seconds). Use a singleton:

```java
// src/test/java/com/example/testconfig/PostgresContainerConfig.java
public abstract class AbstractPostgresIntegrationTest {

    // Single container shared across ALL test classes
    static final PostgreSQLContainer<?> POSTGRES;

    static {
        POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
                .withDatabaseName("testdb")
                .withUsername("test")
                .withPassword("test")
                .withReuse(true); // enable reuse between runs
        POSTGRES.start();
        // Container stays alive for entire test suite
    }

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
    }
}

// Usage — just extend
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class OrderRepositoryTest extends AbstractPostgresIntegrationTest {
    
    @Autowired
    private OrderRepository orderRepository;
    
    @Test
    void shouldWork() {
        // Runs against the shared PostgreSQL container
    }
}

@SpringBootTest
class OrderServiceTest extends AbstractPostgresIntegrationTest {
    // Same container, different Spring context slice
}
```

### Container Reuse Between Test Runs

```properties
# ~/.testcontainers.properties (user home directory)
testcontainers.reuse.enable=true
```

```java
// In container definition
static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
        .withDatabaseName("testdb")
        .withReuse(true); // keeps container running between `./gradlew test` invocations

// The container persists after JVM exits — massive speedup for iterative development
// First run: ~3s container startup
// Subsequent runs: ~50ms connection to existing container
```

**Cleanup caveat with reuse:** You must handle data cleanup yourself since the container persists:

```java
@BeforeEach
void cleanDatabase(@Autowired JdbcTemplate jdbc) {
    jdbc.execute("TRUNCATE TABLE orders, customers, order_items RESTART IDENTITY CASCADE");
}
```

---

## 2. Test Data Management

### Data Builders Pattern

```java
// Fluent test data builders — composable, readable, maintainable
public class CustomerBuilder {
    private String name = "John Doe";
    private String email = "john@example.com";
    private CustomerStatus status = CustomerStatus.ACTIVE;
    private Address address = AddressBuilder.defaults().build();
    private List<Order> orders = new ArrayList<>();

    public static CustomerBuilder aCustomer() {
        return new CustomerBuilder();
    }

    public static CustomerBuilder defaults() {
        return new CustomerBuilder();
    }

    public CustomerBuilder withName(String name) {
        this.name = name;
        return this;
    }

    public CustomerBuilder withEmail(String email) {
        this.email = email;
        return this;
    }

    public CustomerBuilder withStatus(CustomerStatus status) {
        this.status = status;
        return this;
    }

    public CustomerBuilder withAddress(Address address) {
        this.address = address;
        return this;
    }

    public CustomerBuilder withOrder(Order order) {
        this.orders.add(order);
        return this;
    }

    public CustomerBuilder inactive() {
        this.status = CustomerStatus.INACTIVE;
        return this;
    }

    public Customer build() {
        Customer customer = new Customer();
        customer.setName(name);
        customer.setEmail(email);
        customer.setStatus(status);
        customer.setAddress(address);
        orders.forEach(customer::addOrder);
        return customer;
    }

    // Persist helper — useful for integration tests
    public Customer buildAndPersist(EntityManager em) {
        Customer customer = build();
        em.persist(customer);
        em.flush();
        return customer;
    }
}

public class OrderBuilder {
    private Customer customer;
    private BigDecimal totalAmount = BigDecimal.valueOf(99.99);
    private OrderStatus status = OrderStatus.PENDING;
    private List<OrderItem> items = new ArrayList<>();
    private LocalDateTime createdAt = LocalDateTime.now();

    public static OrderBuilder anOrder() {
        return new OrderBuilder();
    }

    public OrderBuilder forCustomer(Customer customer) {
        this.customer = customer;
        return this;
    }

    public OrderBuilder withTotal(double amount) {
        this.totalAmount = BigDecimal.valueOf(amount);
        return this;
    }

    public OrderBuilder withStatus(OrderStatus status) {
        this.status = status;
        return this;
    }

    public OrderBuilder withItem(String sku, int quantity, double price) {
        items.add(new OrderItem(sku, quantity, BigDecimal.valueOf(price)));
        return this;
    }

    public OrderBuilder completed() {
        this.status = OrderStatus.COMPLETED;
        return this;
    }

    public OrderBuilder cancelled() {
        this.status = OrderStatus.CANCELLED;
        return this;
    }

    public Order build() {
        Order order = new Order();
        order.setCustomer(customer);
        order.setTotalAmount(totalAmount);
        order.setStatus(status);
        order.setCreatedAt(createdAt);
        items.forEach(order::addItem);
        return order;
    }

    public Order buildAndPersist(EntityManager em) {
        if (customer != null && customer.getId() == null) {
            em.persist(customer);
        }
        Order order = build();
        em.persist(order);
        em.flush();
        return order;
    }
}

// Usage in tests — highly readable
@Test
void shouldCalculateRevenueForActiveCustomers() {
    Customer alice = CustomerBuilder.aCustomer()
            .withName("Alice")
            .buildAndPersist(em);

    OrderBuilder.anOrder()
            .forCustomer(alice)
            .withTotal(150.00)
            .completed()
            .buildAndPersist(em);

    OrderBuilder.anOrder()
            .forCustomer(alice)
            .withTotal(75.00)
            .completed()
            .buildAndPersist(em);

    OrderBuilder.anOrder()
            .forCustomer(alice)
            .withTotal(200.00)
            .cancelled()  // should not count
            .buildAndPersist(em);

    em.clear(); // detach — force fresh load

    BigDecimal revenue = orderRepository.calculateRevenueForCustomer(alice.getId());
    assertThat(revenue).isEqualByComparingTo("225.00");
}
```

### Database Cleanup Strategies

```java
// Strategy 1: @Transactional auto-rollback (DEFAULT in @DataJpaTest)
// Pros: Zero cleanup code, fast
// Cons: HIDES REAL BUGS (see next section)
@DataJpaTest
@Transactional // implicit — every test rolls back
class OrderRepositoryTest {
    @Test
    void testSomething() {
        // Changes are never committed — rolled back after test
    }
}

// Strategy 2: TRUNCATE between tests (RECOMMENDED for integration tests)
@SpringBootTest
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class OrderServiceIntegrationTest extends AbstractPostgresIntegrationTest {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void cleanDatabase() {
        // TRUNCATE is faster than DELETE for large tables
        // CASCADE handles foreign keys
        // RESTART IDENTITY resets sequences — predictable IDs in tests
        jdbcTemplate.execute("""
            TRUNCATE TABLE order_items, orders, customers, audit_log
            RESTART IDENTITY CASCADE
        """);
    }

    @Test
    void shouldPlaceOrder() {
        // Test with real transactions, real commits, real constraints
    }
}

// Strategy 3: DELETE FROM in @AfterEach (when TRUNCATE is too aggressive)
@SpringBootTest
class SelectiveCleanupTest extends AbstractPostgresIntegrationTest {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @AfterEach
    void cleanup() {
        // Delete in dependency order (child first)
        jdbcTemplate.execute("DELETE FROM order_items");
        jdbcTemplate.execute("DELETE FROM orders");
        jdbcTemplate.execute("DELETE FROM customers");
        // Leave reference/lookup tables intact
    }
}

// Strategy 4: Dedicated cleanup utility (for large projects)
@Component
public class DatabaseCleaner {

    @Autowired
    private DataSource dataSource;

    private List<String> tableNames;

    @PostConstruct
    void init() throws SQLException {
        try (Connection conn = dataSource.getConnection()) {
            DatabaseMetaData metaData = conn.getMetaData();
            ResultSet rs = metaData.getTables(null, "public", null, new String[]{"TABLE"});
            tableNames = new ArrayList<>();
            while (rs.next()) {
                String tableName = rs.getString("TABLE_NAME");
                if (!tableName.startsWith("flyway_")) { // skip migration tables
                    tableNames.add(tableName);
                }
            }
        }
    }

    @Transactional
    public void cleanAll() {
        EntityManager em = // inject
        em.createNativeQuery("SET CONSTRAINTS ALL DEFERRED").executeUpdate();
        for (String table : tableNames) {
            em.createNativeQuery("TRUNCATE TABLE " + table + " CASCADE").executeUpdate();
        }
    }
}
```

### Why @Transactional Tests Hide Real Bugs

```java
// BUG 1: LazyInitializationException is HIDDEN
@Entity
public class Order {
    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<OrderItem> items;
}

@Service
public class OrderService {
    @Transactional(readOnly = true)
    public OrderDto getOrder(Long id) {
        Order order = orderRepository.findById(id).orElseThrow();
        // BUG: accessing lazy collection OUTSIDE transaction in real app
        // But in @Transactional test, the test's transaction keeps session open!
        return new OrderDto(order.getId(), order.getItems().size());
    }
}

@DataJpaTest
@Transactional // <-- THIS HIDES THE BUG
class OrderRepositoryTest {
    @Test
    void testGetOrder() {
        Order order = entityManager.persistAndFlush(someOrder);
        // The test transaction keeps the session open
        // order.getItems() works fine HERE but throws LazyInitializationException in production
        assertThat(order.getItems()).hasSize(3); // PASSES but shouldn't
    }
}

// BUG 2: Constraint violations are HIDDEN (flush never happens)
@DataJpaTest
@Transactional
class ConstraintTest {
    @Test
    void testUniqueConstraint() {
        Customer c1 = new Customer("alice@test.com");
        Customer c2 = new Customer("alice@test.com"); // duplicate email
        
        entityManager.persist(c1);
        entityManager.persist(c2);
        // NO EXCEPTION! Because flush hasn't happened yet.
        // The rollback at end of test means the constraint is never checked.
        
        // FIX: explicitly flush
        assertThrows(DataIntegrityViolationException.class, () -> {
            entityManager.flush();
        });
    }
}

// BUG 3: Second-level cache behavior is hidden
// In @Transactional tests, everything is in the first-level cache (persistence context)
// You never test cache eviction, stale reads, or cache consistency issues
```

---

## 3. Transaction Testing Pitfalls

### How @Transactional Test Masks LazyInitializationException

```java
@Entity
public class Customer {
    @Id @GeneratedValue
    private Long id;
    
    @OneToMany(mappedBy = "customer", fetch = FetchType.LAZY)
    private List<Order> orders = new ArrayList<>();
}

@Service
public class CustomerService {
    
    private final CustomerRepository customerRepository;
    
    // BUG: no @Transactional — or readOnly transaction ends before DTO mapping
    public CustomerDetailDto getCustomerDetail(Long id) {
        Customer customer = customerRepository.findById(id).orElseThrow();
        // In production: LazyInitializationException here
        // In @Transactional test: works fine because test transaction is still open
        return new CustomerDetailDto(
            customer.getName(),
            customer.getOrders().stream()  // BOOM in production
                .map(Order::getStatus)
                .toList()
        );
    }
}

// CORRECT TEST: Don't use @Transactional — test as production would execute
@SpringBootTest
// NO @Transactional here!
class CustomerServiceRealTransactionTest extends AbstractPostgresIntegrationTest {

    @Autowired private CustomerService customerService;
    @Autowired private CustomerRepository customerRepository;
    @Autowired private EntityManager entityManager;
    @Autowired private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void clean() {
        jdbcTemplate.execute("TRUNCATE TABLE orders, customers RESTART IDENTITY CASCADE");
    }

    @Test
    void shouldThrowLazyInitException_whenAccessingOrdersOutsideTransaction() {
        // Setup — in its own transaction
        TransactionTemplate tx = new TransactionTemplate(transactionManager);
        Long customerId = tx.execute(status -> {
            Customer c = new Customer("Alice");
            c.addOrder(new Order(BigDecimal.TEN));
            return customerRepository.save(c).getId();
        });

        // Act — this will fail with LazyInitializationException
        // Now we've proven the bug exists and can fix it
        assertThrows(LazyInitializationException.class, () -> {
            customerService.getCustomerDetail(customerId);
        });
    }
}
```

### Testing Transaction Propagation Behavior

```java
@Service
public class PaymentService {
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public Payment processPayment(Order order) {
        Payment payment = new Payment(order, order.getTotalAmount());
        paymentRepository.save(payment);
        callExternalGateway(payment); // might throw
        return payment;
    }
}

@Service
public class OrderService {
    
    @Transactional
    public Order placeOrder(OrderRequest request) {
        Order order = createOrder(request);
        orderRepository.save(order);
        
        try {
            paymentService.processPayment(order); // REQUIRES_NEW
        } catch (PaymentException e) {
            order.setStatus(OrderStatus.PAYMENT_FAILED);
            // Order is still saved because payment runs in separate TX
        }
        return order;
    }
}

// Test that REQUIRES_NEW actually creates independent transaction
@SpringBootTest
class TransactionPropagationTest extends AbstractPostgresIntegrationTest {

    @Autowired private OrderService orderService;
    @Autowired private PaymentRepository paymentRepository;
    @Autowired private OrderRepository orderRepository;
    @Autowired private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void clean() {
        jdbcTemplate.execute("TRUNCATE TABLE payments, orders, customers RESTART IDENTITY CASCADE");
    }

    @Test
    void paymentFailure_shouldNotRollbackOrder() {
        // Setup: configure payment gateway mock to fail
        // ...
        
        OrderRequest request = new OrderRequest("SKU-001", 1);
        Order order = orderService.placeOrder(request);
        
        // Order should be persisted (outer TX committed)
        assertThat(orderRepository.findById(order.getId())).isPresent();
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PAYMENT_FAILED);
        
        // Payment should NOT be persisted (inner TX rolled back)
        assertThat(paymentRepository.findByOrderId(order.getId())).isEmpty();
    }
}
```

### Testing Optimistic Locking

```java
@Entity
public class Account {
    @Id @GeneratedValue
    private Long id;
    
    @Version
    private Long version;
    
    private BigDecimal balance;
    
    public void debit(BigDecimal amount) {
        if (balance.compareTo(amount) < 0) {
            throw new InsufficientFundsException();
        }
        this.balance = this.balance.subtract(amount);
    }
}

@SpringBootTest
class OptimisticLockingTest extends AbstractPostgresIntegrationTest {

    @Autowired private AccountRepository accountRepository;
    @Autowired private EntityManager entityManager;
    @Autowired private JdbcTemplate jdbcTemplate;
    @PersistenceUnit private EntityManagerFactory emf;

    @BeforeEach
    void clean() {
        jdbcTemplate.execute("TRUNCATE TABLE accounts RESTART IDENTITY CASCADE");
    }

    @Test
    void shouldThrowOptimisticLockException_onConcurrentModification() {
        // Setup
        Account account = new Account(BigDecimal.valueOf(1000));
        account = accountRepository.saveAndFlush(account);
        Long accountId = account.getId();

        // Simulate concurrent modification using two EntityManagers
        EntityManager em1 = emf.createEntityManager();
        EntityManager em2 = emf.createEntityManager();

        em1.getTransaction().begin();
        em2.getTransaction().begin();

        // Both load the same account (same version)
        Account account1 = em1.find(Account.class, accountId);
        Account account2 = em2.find(Account.class, accountId);

        // First modification succeeds
        account1.debit(BigDecimal.valueOf(100));
        em1.getTransaction().commit();
        em1.close();

        // Second modification should fail — stale version
        account2.debit(BigDecimal.valueOf(200));
        assertThrows(RollbackException.class, () -> {
            em2.getTransaction().commit();
        });
        em2.close();

        // Verify final state
        Account finalAccount = accountRepository.findById(accountId).orElseThrow();
        assertThat(finalAccount.getBalance()).isEqualByComparingTo("900");
        assertThat(finalAccount.getVersion()).isEqualTo(1L);
    }
}
```

### Testing Rollback Scenarios

```java
@Service
public class TransferService {
    
    @Transactional
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        Account from = accountRepository.findById(fromId).orElseThrow();
        Account to = accountRepository.findById(toId).orElseThrow();
        
        from.debit(amount);
        to.credit(amount);
        
        auditService.logTransfer(from, to, amount); // if this throws, all rolls back
    }
}

@SpringBootTest
class RollbackTest extends AbstractPostgresIntegrationTest {

    @Autowired private TransferService transferService;
    @Autowired private AccountRepository accountRepository;
    @Autowired private AuditRepository auditRepository;
    @Autowired private JdbcTemplate jdbcTemplate;

    @MockBean
    private AuditService auditService; // mock to force exception

    @BeforeEach
    void clean() {
        jdbcTemplate.execute("TRUNCATE TABLE audit_log, accounts RESTART IDENTITY CASCADE");
    }

    @Test
    void shouldRollbackEntireTransfer_whenAuditFails() {
        Account from = accountRepository.save(new Account(BigDecimal.valueOf(1000)));
        Account to = accountRepository.save(new Account(BigDecimal.valueOf(500)));
        
        doThrow(new RuntimeException("Audit DB down"))
                .when(auditService).logTransfer(any(), any(), any());
        
        assertThrows(RuntimeException.class, () -> {
            transferService.transfer(from.getId(), to.getId(), BigDecimal.valueOf(200));
        });
        
        // Both accounts should be unchanged — full rollback
        Account fromAfter = accountRepository.findById(from.getId()).orElseThrow();
        Account toAfter = accountRepository.findById(to.getId()).orElseThrow();
        
        assertThat(fromAfter.getBalance()).isEqualByComparingTo("1000");
        assertThat(toAfter.getBalance()).isEqualByComparingTo("500");
    }
}
```

---

## 4. Concurrency Testing

### Testing Optimistic Locking with ExecutorService + CountDownLatch

```java
@SpringBootTest
class ConcurrentDebitTest extends AbstractPostgresIntegrationTest {

    @Autowired private AccountService accountService;
    @Autowired private AccountRepository accountRepository;
    @Autowired private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void clean() {
        jdbcTemplate.execute("TRUNCATE TABLE accounts RESTART IDENTITY CASCADE");
    }

    @Test
    void shouldHandleConcurrentDebits_withOptimisticLocking() throws Exception {
        // Setup: account with balance 1000
        Account account = accountRepository.saveAndFlush(
            new Account(BigDecimal.valueOf(1000))
        );
        Long accountId = account.getId();

        int threadCount = 10;
        BigDecimal debitAmount = BigDecimal.valueOf(100); // 10 * 100 = 1000 (exactly balance)
        
        ExecutorService executor = Executors.newFixedThreadPool(threadCount);
        CountDownLatch readyLatch = new CountDownLatch(threadCount);
        CountDownLatch startLatch = new CountDownLatch(1);
        
        AtomicInteger successCount = new AtomicInteger(0);
        AtomicInteger failureCount = new AtomicInteger(0);

        for (int i = 0; i < threadCount; i++) {
            executor.submit(() -> {
                readyLatch.countDown(); // signal ready
                try {
                    startLatch.await(); // wait for go signal
                    accountService.debit(accountId, debitAmount);
                    successCount.incrementAndGet();
                } catch (OptimisticLockingFailureException | StaleStateException e) {
                    failureCount.incrementAndGet();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            });
        }

        readyLatch.await(); // wait for all threads to be ready
        startLatch.countDown(); // fire!
        
        executor.shutdown();
        executor.awaitTermination(10, TimeUnit.SECONDS);

        // With optimistic locking, some will fail
        assertThat(successCount.get() + failureCount.get()).isEqualTo(threadCount);
        assertThat(failureCount.get()).isGreaterThan(0); // at least some conflicts
        
        // Balance should never go negative
        Account finalAccount = accountRepository.findById(accountId).orElseThrow();
        assertThat(finalAccount.getBalance()).isGreaterThanOrEqualTo(BigDecimal.ZERO);
        
        // Verify consistency: balance = 1000 - (successCount * 100)
        BigDecimal expectedBalance = BigDecimal.valueOf(1000)
                .subtract(debitAmount.multiply(BigDecimal.valueOf(successCount.get())));
        assertThat(finalAccount.getBalance()).isEqualByComparingTo(expectedBalance);
    }

    // Service with retry logic
    @Service
    static class AccountService {
        @Autowired private AccountRepository accountRepository;
        
        @Retryable(value = OptimisticLockingFailureException.class, maxAttempts = 3)
        @Transactional
        public void debit(Long accountId, BigDecimal amount) {
            Account account = accountRepository.findById(accountId).orElseThrow();
            account.debit(amount);
            accountRepository.saveAndFlush(account);
        }
    }
}
```

### Testing Deadlocks with CyclicBarrier

```java
@SpringBootTest
class DeadlockDetectionTest extends AbstractPostgresIntegrationTest {

    @Autowired private TransferService transferService;
    @Autowired private AccountRepository accountRepository;
    @Autowired private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void clean() {
        jdbcTemplate.execute("TRUNCATE TABLE accounts RESTART IDENTITY CASCADE");
    }

    @Test
    void shouldDetectDeadlock_onCircularTransfer() throws Exception {
        Account accountA = accountRepository.saveAndFlush(new Account(BigDecimal.valueOf(1000)));
        Account accountB = accountRepository.saveAndFlush(new Account(BigDecimal.valueOf(1000)));

        CyclicBarrier barrier = new CyclicBarrier(2);
        AtomicReference<Exception> thread1Exception = new AtomicReference<>();
        AtomicReference<Exception> thread2Exception = new AtomicReference<>();

        // Thread 1: Transfer A -> B (locks A first, then B)
        Thread t1 = new Thread(() -> {
            try {
                barrier.await(); // synchronize start
                transferService.transferWithLocking(
                    accountA.getId(), accountB.getId(), BigDecimal.valueOf(100)
                );
            } catch (Exception e) {
                thread1Exception.set(e);
            }
        });

        // Thread 2: Transfer B -> A (locks B first, then A) — potential deadlock
        Thread t2 = new Thread(() -> {
            try {
                barrier.await(); // synchronize start
                transferService.transferWithLocking(
                    accountB.getId(), accountA.getId(), BigDecimal.valueOf(50)
                );
            } catch (Exception e) {
                thread2Exception.set(e);
            }
        });

        t1.start();
        t2.start();
        t1.join(5000);
        t2.join(5000);

        // PostgreSQL will detect deadlock and kill one transaction
        // At least one should have failed (or both succeed if no deadlock occurred)
        boolean deadlockDetected = 
            (thread1Exception.get() != null && 
             thread1Exception.get().getMessage().contains("deadlock")) ||
            (thread2Exception.get() != null && 
             thread2Exception.get().getMessage().contains("deadlock"));
        
        // If using ordered locking (lock by lower ID first), no deadlock occurs
        // This test validates your deadlock prevention strategy
        System.out.println("Deadlock detected: " + deadlockDetected);
    }
}

// Deadlock-safe implementation: always lock in consistent order
@Service
public class TransferService {
    
    @Transactional
    public void transferWithLocking(Long fromId, Long toId, BigDecimal amount) {
        // Lock in ID order to prevent deadlocks
        Long firstLock = Math.min(fromId, toId);
        Long secondLock = Math.max(fromId, toId);
        
        Account first = accountRepository.findByIdWithPessimisticLock(firstLock);
        Account second = accountRepository.findByIdWithPessimisticLock(secondLock);
        
        Account from = fromId.equals(firstLock) ? first : second;
        Account to = toId.equals(firstLock) ? first : second;
        
        from.debit(amount);
        to.credit(amount);
    }
}
```

### Load Testing JPA Layer with JMH

```java
// build.gradle
// testImplementation 'org.openjdk.jmh:jmh-core:1.37'
// testAnnotationProcessor 'org.openjdk.jmh:jmh-generator-annprocess:1.37'

@State(Scope.Benchmark)
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.SECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 2)
@Fork(1)
public class OrderRepositoryBenchmark {

    private ConfigurableApplicationContext context;
    private OrderRepository orderRepository;
    private Long customerId;

    @Setup(Level.Trial)
    public void setup() {
        context = new SpringApplicationBuilder(TestApplication.class)
                .profiles("benchmark")
                .run();
        orderRepository = context.getBean(OrderRepository.class);
        
        // Seed test data
        CustomerRepository customerRepo = context.getBean(CustomerRepository.class);
        Customer customer = customerRepo.save(new Customer("Benchmark User"));
        customerId = customer.getId();
        
        for (int i = 0; i < 10_000; i++) {
            orderRepository.save(new Order(customer, BigDecimal.valueOf(i)));
        }
    }

    @TearDown(Level.Trial)
    public void teardown() {
        context.close();
    }

    @Benchmark
    public List<Order> findByCustomerId() {
        return orderRepository.findByCustomerId(customerId);
    }

    @Benchmark
    public Page<Order> findByCustomerIdPaginated() {
        return orderRepository.findByCustomerId(customerId, PageRequest.of(0, 20));
    }

    @Benchmark
    public List<OrderSummaryProjection> findProjection() {
        return orderRepository.findOrderSummariesByCustomerId(customerId);
    }

    // Run: java -jar target/benchmarks.jar OrderRepositoryBenchmark
}
```

---

## 5. Performance Regression Testing

### Query Count Assertions with datasource-proxy

```xml
<!-- pom.xml -->
<dependency>
    <groupId>net.ttddyy</groupId>
    <artifactId>datasource-proxy</artifactId>
    <version>1.9</version>
    <scope>test</scope>
</dependency>
```

```java
// Configuration to wrap DataSource with proxy
@TestConfiguration
public class DataSourceProxyConfig {

    @Bean
    public DataSource dataSource(DataSource originalDataSource) {
        return ProxyDataSourceBuilder.create(originalDataSource)
                .name("query-counter")
                .countQuery()
                .build();
    }
}

// Query counting utility
public class QueryCountAssert {
    
    private final ProxyDataSource proxyDataSource;
    
    public QueryCountAssert(DataSource dataSource) {
        this.proxyDataSource = (ProxyDataSource) dataSource;
    }
    
    public QueryCountAssert reset() {
        QueryCountHolder.clear();
        return this;
    }
    
    public QueryCountAssert assertSelectCount(int expected) {
        QueryCount count = QueryCountHolder.getGrandTotal();
        assertThat(count.getSelect())
            .as("Expected %d SELECT queries but got %d", expected, count.getSelect())
            .isEqualTo(expected);
        return this;
    }
    
    public QueryCountAssert assertSelectCountLessThan(int max) {
        QueryCount count = QueryCountHolder.getGrandTotal();
        assertThat(count.getSelect())
            .as("Expected less than %d SELECT queries but got %d", max, count.getSelect())
            .isLessThan(max);
        return this;
    }
    
    public QueryCountAssert assertInsertCount(int expected) {
        QueryCount count = QueryCountHolder.getGrandTotal();
        assertThat(count.getInsert()).isEqualTo(expected);
        return this;
    }
    
    public QueryCountAssert assertTotalCount(int expected) {
        QueryCount count = QueryCountHolder.getGrandTotal();
        assertThat(count.getTotal()).isEqualTo(expected);
        return this;
    }
}

// Usage in tests
@SpringBootTest
@Import(DataSourceProxyConfig.class)
class QueryCountTest extends AbstractPostgresIntegrationTest {

    @Autowired private OrderService orderService;
    @Autowired private DataSource dataSource;
    
    private QueryCountAssert queryCount;
    
    @BeforeEach
    void setup() {
        queryCount = new QueryCountAssert(dataSource);
    }

    @Test
    void getOrderWithItems_shouldExecuteExactly2Queries() {
        // Setup data...
        
        queryCount.reset();
        
        OrderDto dto = orderService.getOrderWithItems(orderId);
        
        // 1 SELECT for order, 1 SELECT for items (JOIN FETCH)
        queryCount.assertSelectCount(2);
    }

    @Test
    void listOrders_shouldNotCauseNPlus1() {
        // Setup: 50 orders, each with 3 items
        
        queryCount.reset();
        
        List<OrderDto> orders = orderService.listOrders(PageRequest.of(0, 50));
        
        // Should be 2 queries max (orders + batch-loaded items), not 51
        queryCount.assertSelectCountLessThan(5);
    }
}
```

### N+1 Detection in Tests (Fail on Threshold)

```java
// Using Hibernate Statistics
@SpringBootTest
@TestPropertySource(properties = {
    "spring.jpa.properties.hibernate.generate_statistics=true"
})
class NPlus1DetectionTest extends AbstractPostgresIntegrationTest {

    @Autowired private EntityManagerFactory emf;
    @Autowired private OrderService orderService;

    @Test
    void shouldNotExceedQueryThreshold() {
        // Setup: 100 orders
        setupOrders(100);
        
        Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();
        stats.clear();
        
        orderService.listAllOrders();
        
        long queryCount = stats.getQueryExecutionCount();
        long prepareCount = stats.getPrepareStatementCount();
        
        // If we have N+1, this would be 101+ statements
        assertThat(prepareCount)
            .as("Detected N+1 problem! Expected <= 5 queries, got %d", prepareCount)
            .isLessThanOrEqualTo(5);
        
        // Also check for slow queries
        String slowestQuery = stats.getQueryStatistics(
            stats.getQueries()[0]
        ).toString();
        System.out.println("Slowest query: " + slowestQuery);
    }
}

// Custom JUnit 5 Extension for automatic N+1 detection
public class QueryCountExtension implements BeforeEachCallback, AfterEachCallback {

    @Override
    public void beforeEach(ExtensionContext context) {
        // Reset query counter
        QueryCountHolder.clear();
    }

    @Override
    public void afterEach(ExtensionContext context) {
        MaxQueries annotation = context.getRequiredTestMethod()
                .getAnnotation(MaxQueries.class);
        if (annotation != null) {
            QueryCount count = QueryCountHolder.getGrandTotal();
            if (count.getSelect() > annotation.select()) {
                throw new AssertionError(String.format(
                    "Query count exceeded! Max allowed: %d SELECT, actual: %d SELECT. " +
                    "Possible N+1 detected.",
                    annotation.select(), count.getSelect()
                ));
            }
        }
    }
}

// Custom annotation
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface MaxQueries {
    int select() default 10;
    int insert() default 10;
    int total() default 30;
}

// Usage
@ExtendWith(QueryCountExtension.class)
@SpringBootTest
class OrderControllerTest {

    @Test
    @MaxQueries(select = 3)
    void getOrderList_shouldBeEfficient() {
        // If this method causes more than 3 SELECTs, test fails
        orderService.getOrders(PageRequest.of(0, 50));
    }
}
```

### QuickPerf — Declarative Performance Assertions

```xml
<dependency>
    <groupId>org.quickperf</groupId>
    <artifactId>quick-perf-junit5-spring</artifactId>
    <version>1.1.0</version>
    <scope>test</scope>
</dependency>
```

```java
@QuickPerfTest
@SpringBootTest
class QuickPerfQueryTest extends AbstractPostgresIntegrationTest {

    @Autowired private OrderService orderService;

    @Test
    @ExpectSelect(2)  // Exactly 2 SELECT queries expected
    void shouldLoadOrderWithTwoQueries() {
        orderService.getOrderWithItems(1L);
    }

    @Test
    @ExpectMaxSelect(5)  // No more than 5 SELECT queries
    void shouldLoadDashboard_efficiently() {
        orderService.getDashboardData();
    }

    @Test
    @ExpectNoN1Select  // Automatically detects N+1 pattern
    void shouldNotHaveNPlus1_whenLoadingOrders() {
        orderService.listAllOrders();
    }

    @Test
    @DisableExactlySameSelects  // Fails if same SELECT is executed multiple times
    void shouldNotExecuteDuplicateQueries() {
        orderService.getCustomerWithOrders(1L);
    }

    @Test
    @ExpectJdbcBatching(batchSize = 50)  // Verify batch inserts
    void shouldUseBatchInserts() {
        orderService.bulkCreateOrders(generateOrders(200));
    }
}
```

### Execution Plan Validation

```java
@SpringBootTest
class ExecutionPlanTest extends AbstractPostgresIntegrationTest {

    @Autowired private JdbcTemplate jdbcTemplate;

    @Test
    void ordersByStatus_shouldUseIndex() {
        // Seed sufficient data for planner to use index
        seedOrders(10_000);
        
        // Get execution plan
        String plan = jdbcTemplate.queryForObject(
            "EXPLAIN (FORMAT JSON) SELECT * FROM orders WHERE status = 'PENDING' LIMIT 100",
            String.class
        );
        
        // Verify index is used (not sequential scan)
        assertThat(plan).contains("Index Scan");
        assertThat(plan).doesNotContain("Seq Scan");
    }

    @Test
    void complexJoinQuery_shouldNotUseNestedLoop_onLargeData() {
        seedOrders(50_000);
        
        List<Map<String, Object>> plan = jdbcTemplate.queryForList("""
            EXPLAIN (ANALYZE, FORMAT JSON)
            SELECT c.name, COUNT(o.id), SUM(o.total_amount)
            FROM customers c
            JOIN orders o ON o.customer_id = c.id
            WHERE o.created_at > NOW() - INTERVAL '30 days'
            GROUP BY c.id
            HAVING COUNT(o.id) > 5
        """);
        
        String planJson = plan.get(0).values().iterator().next().toString();
        
        // Parse and assert on execution plan
        assertThat(planJson).satisfiesAnyOf(
            p -> assertThat(p).contains("Hash Join"),
            p -> assertThat(p).contains("Merge Join")
        );
        
        // Extract execution time
        // Ensure query completes within acceptable time
        ObjectMapper mapper = new ObjectMapper();
        JsonNode root = mapper.readTree(planJson);
        double executionTime = root.get(0).get("Plan").get("Actual Total Time").asDouble();
        assertThat(executionTime).isLessThan(100.0); // < 100ms
    }
}
```

### Slow Query Detection in CI

```java
// application-test.yml
// spring:
//   jpa:
//     properties:
//       hibernate:
//         session.events.log.LOG_QUERIES_SLOWER_THAN_MS: 50

// Custom listener that fails tests on slow queries
@TestConfiguration
public class SlowQueryDetectorConfig {

    @Bean
    public DataSource slowQueryDetectingDataSource(DataSource original) {
        return ProxyDataSourceBuilder.create(original)
                .name("slow-query-detector")
                .listener(new SlowQueryListener())
                .build();
    }

    static class SlowQueryListener implements QueryExecutionListener {
        
        private static final long THRESHOLD_MS = 100;
        private final List<String> slowQueries = new CopyOnWriteArrayList<>();

        @Override
        public void beforeQuery(ExecutionInfo execInfo, List<QueryInfo> queryInfoList) {}

        @Override
        public void afterQuery(ExecutionInfo execInfo, List<QueryInfo> queryInfoList) {
            long elapsedMs = TimeUnit.NANOSECONDS.toMillis(execInfo.getElapsedTime());
            if (elapsedMs > THRESHOLD_MS) {
                String query = queryInfoList.stream()
                        .map(QueryInfo::getQuery)
                        .collect(Collectors.joining("; "));
                slowQueries.add(String.format("[%dms] %s", elapsedMs, query));
            }
        }

        public List<String> getSlowQueries() {
            return Collections.unmodifiableList(slowQueries);
        }
        
        public void reset() {
            slowQueries.clear();
        }
    }
}

// In CI pipeline: aggregate slow query report and fail build if threshold exceeded
```

---

## 6. Testing Complex Scenarios

### Testing Soft Delete

```java
@Entity
@SQLDelete(sql = "UPDATE customers SET deleted = true, deleted_at = NOW() WHERE id = ?")
@SQLRestriction("deleted = false")
public class Customer {
    @Id @GeneratedValue
    private Long id;
    private String name;
    private boolean deleted = false;
    private LocalDateTime deletedAt;
}

@SpringBootTest
class SoftDeleteTest extends AbstractPostgresIntegrationTest {

    @Autowired private CustomerRepository customerRepository;
    @Autowired private EntityManager entityManager;
    @Autowired private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void clean() {
        jdbcTemplate.execute("TRUNCATE TABLE customers RESTART IDENTITY CASCADE");
    }

    @Test
    void delete_shouldSoftDelete_notPhysicallyRemove() {
        Customer customer = customerRepository.save(new Customer("Alice"));
        Long id = customer.getId();
        
        customerRepository.deleteById(id);
        entityManager.flush();
        entityManager.clear();
        
        // Standard JPA query should NOT find it (filtered by @SQLRestriction)
        assertThat(customerRepository.findById(id)).isEmpty();
        
        // But it's still in the database
        Integer count = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM customers WHERE id = ?", Integer.class, id
        );
        assertThat(count).isEqualTo(1);
        
        // Verify soft delete fields
        Boolean deleted = jdbcTemplate.queryForObject(
            "SELECT deleted FROM customers WHERE id = ?", Boolean.class, id
        );
        assertThat(deleted).isTrue();
    }

    @Test
    void findAll_shouldExcludeDeletedRecords() {
        customerRepository.save(new Customer("Alice"));
        Customer bob = customerRepository.save(new Customer("Bob"));
        customerRepository.save(new Customer("Charlie"));
        
        customerRepository.delete(bob);
        entityManager.flush();
        entityManager.clear();
        
        List<Customer> customers = customerRepository.findAll();
        assertThat(customers).hasSize(2);
        assertThat(customers).extracting(Customer::getName)
                .containsExactlyInAnyOrder("Alice", "Charlie");
    }

    @Test
    void nativeQuery_shouldBypassSoftDeleteFilter() {
        Customer alice = customerRepository.save(new Customer("Alice"));
        customerRepository.delete(alice);
        entityManager.flush();
        entityManager.clear();
        
        // Admin use case: find all including deleted
        @SuppressWarnings("unchecked")
        List<Customer> all = entityManager.createNativeQuery(
            "SELECT * FROM customers", Customer.class
        ).getResultList();
        // Note: @SQLRestriction does NOT apply to native queries by default
        // This depends on Hibernate version — verify behavior
    }
}
```

### Testing Auditing

```java
@Entity
@EntityListeners(AuditingEntityListener.class)
public class Order {
    @Id @GeneratedValue
    private Long id;
    
    @CreatedDate
    private LocalDateTime createdAt;
    
    @LastModifiedDate
    private LocalDateTime updatedAt;
    
    @CreatedBy
    private String createdBy;
    
    @LastModifiedBy
    private String updatedBy;
}

@Configuration
@EnableJpaAuditing
public class AuditConfig {
    @Bean
    public AuditorAware<String> auditorProvider() {
        return () -> Optional.ofNullable(SecurityContextHolder.getContext())
                .map(SecurityContext::getAuthentication)
                .filter(Authentication::isAuthenticated)
                .map(Authentication::getName);
    }
}

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(AuditConfig.class)
@EnableJpaAuditing
class AuditingTest extends AbstractPostgresIntegrationTest {

    @Autowired private OrderRepository orderRepository;
    @Autowired private TestEntityManager entityManager;

    @BeforeEach
    void setupSecurity() {
        // Mock security context for @CreatedBy / @LastModifiedBy
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(
            new UsernamePasswordAuthenticationToken("admin@test.com", null, 
                List.of(new SimpleGrantedAuthority("ROLE_ADMIN")))
        );
        SecurityContextHolder.setContext(context);
    }

    @AfterEach
    void clearSecurity() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void shouldPopulateCreatedFields_onPersist() {
        Order order = new Order(BigDecimal.valueOf(100));
        order = orderRepository.saveAndFlush(order);
        
        assertThat(order.getCreatedAt()).isNotNull();
        assertThat(order.getCreatedBy()).isEqualTo("admin@test.com");
        assertThat(order.getUpdatedAt()).isNotNull();
    }

    @Test
    void shouldUpdateModifiedFields_onUpdate() throws InterruptedException {
        Order order = orderRepository.saveAndFlush(new Order(BigDecimal.valueOf(100)));
        LocalDateTime originalCreatedAt = order.getCreatedAt();
        
        Thread.sleep(10); // ensure time difference
        
        // Switch user
        SecurityContextHolder.getContext().setAuthentication(
            new UsernamePasswordAuthenticationToken("user@test.com", null, List.of())
        );
        
        order.setTotalAmount(BigDecimal.valueOf(200));
        order = orderRepository.saveAndFlush(order);
        
        assertThat(order.getCreatedAt()).isEqualTo(originalCreatedAt); // unchanged
        assertThat(order.getCreatedBy()).isEqualTo("admin@test.com"); // unchanged
        assertThat(order.getUpdatedAt()).isAfter(originalCreatedAt);
        assertThat(order.getUpdatedBy()).isEqualTo("user@test.com"); // updated
    }
}
```

### Testing Multi-Tenancy

```java
// Tenant context
public class TenantContext {
    private static final ThreadLocal<String> CURRENT_TENANT = new ThreadLocal<>();
    
    public static void setTenant(String tenant) { CURRENT_TENANT.set(tenant); }
    public static String getTenant() { return CURRENT_TENANT.get(); }
    public static void clear() { CURRENT_TENANT.remove(); }
}

// Schema-per-tenant approach
@Component
public class TenantSchemaResolver implements CurrentTenantIdentifierResolver {
    @Override
    public String resolveCurrentTenantIdentifier() {
        return Optional.ofNullable(TenantContext.getTenant()).orElse("public");
    }
    @Override
    public boolean validateExistingCurrentSessions() { return true; }
}

@SpringBootTest
class MultiTenancyIsolationTest extends AbstractPostgresIntegrationTest {

    @Autowired private OrderRepository orderRepository;
    @Autowired private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void setupTenantSchemas() {
        jdbcTemplate.execute("CREATE SCHEMA IF NOT EXISTS tenant_a");
        jdbcTemplate.execute("CREATE SCHEMA IF NOT EXISTS tenant_b");
        jdbcTemplate.execute("""
            CREATE TABLE IF NOT EXISTS tenant_a.orders (
                id BIGSERIAL PRIMARY KEY, total_amount DECIMAL(19,2)
            )
        """);
        jdbcTemplate.execute("""
            CREATE TABLE IF NOT EXISTS tenant_b.orders (
                id BIGSERIAL PRIMARY KEY, total_amount DECIMAL(19,2)
            )
        """);
    }

    @Test
    void tenantA_shouldNotSeeTenantB_data() {
        // Insert as Tenant A
        TenantContext.setTenant("tenant_a");
        orderRepository.save(new Order(BigDecimal.valueOf(100)));
        orderRepository.save(new Order(BigDecimal.valueOf(200)));
        
        // Insert as Tenant B
        TenantContext.setTenant("tenant_b");
        orderRepository.save(new Order(BigDecimal.valueOf(999)));
        
        // Query as Tenant A — should only see own data
        TenantContext.setTenant("tenant_a");
        List<Order> tenantAOrders = orderRepository.findAll();
        assertThat(tenantAOrders).hasSize(2);
        assertThat(tenantAOrders).allMatch(o -> 
            o.getTotalAmount().compareTo(BigDecimal.valueOf(999)) != 0
        );
        
        // Query as Tenant B
        TenantContext.setTenant("tenant_b");
        List<Order> tenantBOrders = orderRepository.findAll();
        assertThat(tenantBOrders).hasSize(1);
        
        TenantContext.clear();
    }

    @Test
    void crossTenantAccess_shouldBeImpossible() {
        TenantContext.setTenant("tenant_a");
        Order order = orderRepository.save(new Order(BigDecimal.valueOf(500)));
        Long orderId = order.getId();
        
        TenantContext.setTenant("tenant_b");
        // Tenant B should NOT be able to access Tenant A's order by ID
        assertThat(orderRepository.findById(orderId)).isEmpty();
        
        TenantContext.clear();
    }
}
```

### Testing Database Migrations

```java
// Testing Flyway migrations execute correctly
@SpringBootTest(properties = {
    "spring.flyway.enabled=true",
    "spring.jpa.hibernate.ddl-auto=validate" // only validate, don't generate
})
class FlywayMigrationTest extends AbstractPostgresIntegrationTest {

    @Autowired private Flyway flyway;
    @Autowired private JdbcTemplate jdbcTemplate;

    @Test
    void allMigrations_shouldApplyCleanly() {
        // Clean and re-migrate from scratch
        flyway.clean();
        MigrateResult result = flyway.migrate();
        
        assertThat(result.success).isTrue();
        assertThat(result.migrationsExecuted).isGreaterThan(0);
    }

    @Test
    void migration_V5__AddIndexes_shouldCreateExpectedIndexes() {
        // Verify specific migration created what we expect
        List<Map<String, Object>> indexes = jdbcTemplate.queryForList("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE schemaname = 'public' AND tablename = 'orders'
        """);
        
        assertThat(indexes).extracting(m -> m.get("indexname").toString())
                .contains("idx_orders_customer_id", "idx_orders_status_created_at");
    }

    @Test
    void migrationsShouldBeIdempotent_afterAppStarts() {
        // Verify no pending migrations
        MigrationInfo[] pending = flyway.info().pending();
        assertThat(pending).isEmpty();
    }

    @Test
    void entityMappings_shouldMatchDatabaseSchema() {
        // This test ensures Hibernate's entity model matches the actual schema
        // If they diverge, this will throw on context startup
        // (using ddl-auto=validate ensures this)
        // Simply starting the Spring context IS the test
        assertThat(true).isTrue(); // context loaded successfully
    }
}

// Testing individual migration scripts
class MigrationScriptTest extends AbstractPostgresIntegrationTest {

    @Autowired private JdbcTemplate jdbcTemplate;

    @Test
    void dataMigration_V7__BackfillCustomerStatus_shouldSetDefaults() {
        // Simulate pre-migration state
        jdbcTemplate.execute("""
            INSERT INTO customers (id, name, email) VALUES 
            (1, 'Alice', 'a@test.com'),
            (2, 'Bob', 'b@test.com')
        """);
        
        // Run the specific migration logic
        jdbcTemplate.execute("""
            UPDATE customers SET status = 'ACTIVE' WHERE status IS NULL
        """);
        
        // Verify
        Integer nullStatusCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM customers WHERE status IS NULL", Integer.class
        );
        assertThat(nullStatusCount).isZero();
    }
}
```

---

## 7. Test Architecture for Large Projects

### Test Slicing Strategy

```
┌─────────────────────────────────────────────────────┐
│ E2E Tests (< 5%)                                     │
│ Full application, real DB, real external services     │
│ @SpringBootTest + Testcontainers + WireMock          │
├─────────────────────────────────────────────────────┤
│ Integration Tests (20-30%)                           │
│ Spring context slice, real DB, mocked externals      │
│ @DataJpaTest / @SpringBootTest + Testcontainers      │
├─────────────────────────────────────────────────────┤
│ Slice Tests (20-30%)                                 │
│ Thin context, specific layer only                    │
│ @WebMvcTest, @DataJpaTest with embedded              │
├─────────────────────────────────────────────────────┤
│ Unit Tests (40-50%)                                  │
│ No Spring, no DB, pure logic                         │
│ JUnit 5 + Mockito, entity business logic, mappers    │
└─────────────────────────────────────────────────────┘
```

```java
// UNIT TEST — No Spring, no DB
class OrderTest {
    @Test
    void shouldCalculateTotal() {
        Order order = new Order();
        order.addItem(new OrderItem("SKU-1", 2, BigDecimal.valueOf(10)));
        order.addItem(new OrderItem("SKU-2", 1, BigDecimal.valueOf(25)));
        
        assertThat(order.calculateTotal()).isEqualByComparingTo("45.00");
    }
    
    @Test
    void shouldNotAllowNegativeQuantity() {
        Order order = new Order();
        assertThrows(IllegalArgumentException.class, () -> {
            order.addItem(new OrderItem("SKU-1", -1, BigDecimal.valueOf(10)));
        });
    }
}

// SLICE TEST — JPA layer only
@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE)
class OrderRepositorySliceTest extends AbstractPostgresIntegrationTest {
    @Test
    void customQuery_shouldWork() { ... }
}

// INTEGRATION TEST — Service + Repository + real transactions
@SpringBootTest
class OrderServiceIntegrationTest extends AbstractPostgresIntegrationTest {
    @Test
    void placeOrder_shouldPersistAndPublishEvent() { ... }
}

// E2E TEST — Full stack
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class OrderApiE2ETest extends AbstractPostgresIntegrationTest {
    @Autowired TestRestTemplate restTemplate;
    
    @Test
    void shouldCreateAndRetrieveOrder() {
        ResponseEntity<OrderDto> response = restTemplate.postForEntity(
            "/api/orders", new OrderRequest(...), OrderDto.class
        );
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }
}
```

### Test Parallelization with JPA (Schema-per-Test-Class)

```java
// Problem: Parallel test execution with shared DB causes data conflicts
// Solution: Each test class gets its own schema

public abstract class AbstractParallelIntegrationTest {

    static final PostgreSQLContainer<?> POSTGRES;
    
    static {
        POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
                .withReuse(true);
        POSTGRES.start();
    }

    private static String schemaForClass(Class<?> testClass) {
        // Deterministic schema name from class
        return "test_" + testClass.getSimpleName().toLowerCase()
                .replaceAll("[^a-z0-9]", "_");
    }

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
    }

    @BeforeAll
    static void createSchema(@Autowired JdbcTemplate jdbc, TestInfo testInfo) {
        String schema = schemaForClass(testInfo.getTestClass().orElseThrow());
        jdbc.execute("CREATE SCHEMA IF NOT EXISTS " + schema);
        jdbc.execute("SET search_path TO " + schema);
    }

    @BeforeEach
    void setSchema(@Autowired JdbcTemplate jdbc, TestInfo testInfo) {
        String schema = schemaForClass(testInfo.getTestClass().orElseThrow());
        jdbc.execute("SET search_path TO " + schema);
    }
}

// build.gradle — enable parallel execution
// test {
//     systemProperty 'junit.jupiter.execution.parallel.enabled', 'true'
//     systemProperty 'junit.jupiter.execution.parallel.mode.default', 'concurrent'
//     systemProperty 'junit.jupiter.execution.parallel.mode.classes.default', 'concurrent'
//     maxParallelForks = Runtime.runtime.availableProcessors().intdiv(2) ?: 1
// }
```

### CI/CD Pipeline Integration

```yaml
# .github/workflows/test.yml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      # Alternative to Testcontainers — use GitHub Actions service containers
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: testdb
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
          cache: 'gradle'
      
      # Cache Testcontainer images (if using Testcontainers instead of service)
      - name: Cache Docker images
        uses: actions/cache@v4
        with:
          path: /tmp/.docker-cache
          key: docker-${{ runner.os }}-postgres16
      
      - name: Load cached Docker images
        run: |
          if [ -f /tmp/.docker-cache/postgres.tar ]; then
            docker load < /tmp/.docker-cache/postgres.tar
          fi
      
      - name: Run tests
        run: ./gradlew test --parallel
        env:
          SPRING_DATASOURCE_URL: jdbc:postgresql://localhost:5432/testdb
          SPRING_DATASOURCE_USERNAME: test
          SPRING_DATASOURCE_PASSWORD: test
          TESTCONTAINERS_REUSE_ENABLE: true
      
      - name: Save Docker images to cache
        run: |
          mkdir -p /tmp/.docker-cache
          docker save postgres:16-alpine > /tmp/.docker-cache/postgres.tar
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: build/reports/tests/
```

---

## 8. Mocking vs Real Database

### Decision Framework

| Scenario | Mock | Real DB | Why |
|----------|------|---------|-----|
| Service business logic (no queries) | ✅ | | Fast, isolated |
| Custom JPQL/native queries | | ✅ | Only DB can validate SQL |
| Entity mapping correctness | | ✅ | Hibernate dialect issues |
| Transaction boundaries | | ✅ | Mocking hides TX bugs |
| Optimistic locking | | ✅ | Needs real version checking |
| Constraint validation | | ✅ | DB enforces constraints |
| Performance (N+1) | | ✅ | Need real query execution |
| Controller input validation | ✅ | | No DB needed |
| Cache behavior | | ✅ | Needs real round-trips |

### @MockBean vs @SpyBean

```java
// @MockBean — FULL mock, no real behavior
// Use when: testing service logic, external dependency doesn't matter
@SpringBootTest
class OrderServiceMockTest {

    @Autowired private OrderService orderService;
    
    @MockBean
    private PaymentGateway paymentGateway; // external service — always mock
    
    @MockBean
    private OrderRepository orderRepository; // mock for pure service logic tests
    
    @Test
    void shouldRejectOrder_whenPaymentDeclined() {
        when(orderRepository.findById(1L)).thenReturn(Optional.of(testOrder()));
        when(paymentGateway.charge(any())).thenReturn(PaymentResult.DECLINED);
        
        assertThrows(PaymentDeclinedException.class, () -> {
            orderService.processPayment(1L);
        });
        
        verify(orderRepository, never()).save(any()); // order not updated
    }
}

// @SpyBean — REAL behavior with selective overrides
// Use when: you want real repository behavior but need to verify interactions
// or override specific methods
@SpringBootTest
class OrderServiceSpyTest extends AbstractPostgresIntegrationTest {

    @Autowired private OrderService orderService;
    
    @SpyBean
    private OrderRepository orderRepository; // real DB, but we can verify/stub
    
    @SpyBean
    private NotificationService notificationService; // real logic, stub external calls
    
    @Test
    void shouldSaveAndNotify() {
        // Real save happens against real DB
        doNothing().when(notificationService).sendEmail(any()); // stub email only
        
        Order order = orderService.placeOrder(new OrderRequest("SKU-1", 1));
        
        // Verify real save happened
        verify(orderRepository).save(any(Order.class));
        assertThat(orderRepository.findById(order.getId())).isPresent();
        
        // Verify notification was triggered
        verify(notificationService).sendEmail(any());
    }
}
```

### In-Memory Testing Dangers

```java
// DANGER 1: HashMap-based mock repository
// This is common in "clean architecture" projects — it's testing nothing useful
class InMemoryOrderRepository implements OrderRepository {
    private final Map<Long, Order> store = new HashMap<>();
    private final AtomicLong idGenerator = new AtomicLong(1);
    
    @Override
    public Order save(Order order) {
        if (order.getId() == null) order.setId(idGenerator.getAndIncrement());
        store.put(order.getId(), order);
        return order;
    }
    // ... 
    // PROBLEMS:
    // - No constraint checking
    // - No lazy loading behavior
    // - No flush/clear semantics
    // - No transaction boundaries
    // - JPQL/native queries can't be tested
    // - No cascade behavior
    // - Behaves nothing like a real database
}

// DANGER 2: H2 "compatibility mode" is NOT compatible
// spring.datasource.url=jdbc:h2:mem:testdb;MODE=PostgreSQL
// This mode handles maybe 60% of PostgreSQL syntax
// Complex queries, functions, and features silently behave differently

// WHEN IT'S OK to use mocks:
// 1. Testing a service method that does pure computation
// 2. Testing error handling paths (repository throws exception)
// 3. Testing event publishing after repository call
// 4. Testing retry logic around repository calls

@Service
public class DiscountCalculator {
    // Pure business logic — mock the repository, test the math
    public BigDecimal calculateDiscount(Customer customer, Order order) {
        BigDecimal baseDiscount = BigDecimal.ZERO;
        if (customer.isVip()) baseDiscount = baseDiscount.add(BigDecimal.valueOf(0.1));
        if (order.getTotalAmount().compareTo(BigDecimal.valueOf(500)) > 0) {
            baseDiscount = baseDiscount.add(BigDecimal.valueOf(0.05));
        }
        return order.getTotalAmount().multiply(baseDiscount);
    }
}

// This is FINE to unit test without a database:
class DiscountCalculatorTest {
    @Test
    void vipCustomer_largeOrder_getsMaxDiscount() {
        Customer vip = mock(Customer.class);
        when(vip.isVip()).thenReturn(true);
        
        Order order = mock(Order.class);
        when(order.getTotalAmount()).thenReturn(BigDecimal.valueOf(1000));
        
        BigDecimal discount = calculator.calculateDiscount(vip, order);
        assertThat(discount).isEqualByComparingTo("150.00"); // 15% of 1000
    }
}
```

---

## Summary: Testing Principles for JPA at Scale

1. **Use Testcontainers with the real database** — H2 is a lie detector that always says "pass"
2. **Avoid @Transactional on integration tests** — it hides flush, constraint, and lazy-loading bugs
3. **Use TRUNCATE for cleanup** — predictable, fast, honest
4. **Assert query counts** — N+1 problems are regressions; catch them in CI
5. **Test concurrency explicitly** — optimistic locking bugs only appear under load
6. **Singleton containers + reuse** — keep tests fast (50ms container connect vs 3s startup)
7. **Mock external services, not repositories** — repository mocks test nothing useful
8. **Validate execution plans** — indexes might not be used after data grows
9. **Test migrations separately** — schema drift is a production incident waiting to happen
10. **Parallelize with schema isolation** — fast CI without data conflicts
