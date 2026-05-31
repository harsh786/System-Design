# Staff Engineer - Part 7: Testing Patterns & Internals
# Mockito internals, Testcontainers, Integration Testing, TDD at Scale

---

## Q264: How does Mockito work internally? (Byte-code generation)

**Under the hood:**
```
1. Mockito.mock(UserService.class) 
   → ByteBuddy generates a SUBCLASS at runtime
   → All methods overridden to return default values
   → Invocations recorded in InvocationContainer

2. when(mock.findById(1L)).thenReturn(user)
   → "when" captures the last invocation from the mock
   → Registers a stubbing (invocation matcher → answer)

3. verify(mock).findById(1L)
   → Checks InvocationContainer for matching invocation
   → Fails if not found or wrong count
```

```java
// Simplified Mockito internals:
class SimpleMock {
    // Each mock has an invocation handler
    static class MockHandler implements InvocationHandler {
        List<Invocation> invocations = new ArrayList<>();
        Map<InvocationMatcher, Answer> stubbings = new LinkedHashMap<>();
        
        @Override
        public Object invoke(Object proxy, Method method, Object[] args) {
            Invocation invocation = new Invocation(method, args);
            invocations.add(invocation);
            
            // Check if there's a stubbing for this invocation
            for (var entry : stubbings.entrySet()) {
                if (entry.getKey().matches(invocation)) {
                    return entry.getValue().answer(invocation);
                }
            }
            
            // Default: return null/0/false
            return getDefaultValue(method.getReturnType());
        }
    }
}

// Why Mockito can't mock final classes (without inline mock maker):
// - Uses SUBCLASS approach: new ByteBuddy().subclass(Target.class)
// - Final classes can't be subclassed!
// - Solution: Inline Mock Maker (Java Agent) rewrites bytecode at load time
// - mockito-extensions/org.mockito.plugins.MockMaker → mock-maker-inline
```

**Key Mockito Limitations:**
1. Cannot mock `final` classes without inline mock maker
2. Cannot mock `static` methods without `mockStatic()` (Mockito 3.4+)
3. Cannot mock constructors without `mockConstruction()` (Mockito 3.5+)
4. Cannot mock `private` methods (use reflection or restructure code)
5. Cannot mock `equals()`/`hashCode()` (used internally by Mockito)

---

## Q265: Mockito Best Practices for Staff Engineers

```java
// ANTI-PATTERN 1: Over-mocking (mocking everything)
@Test
void badTest() {
    // Mocking simple value objects - WHY?
    Money money = mock(Money.class);
    when(money.getAmount()).thenReturn(BigDecimal.TEN);
    // Just use: new Money(BigDecimal.TEN) !
}

// ANTI-PATTERN 2: Testing implementation details
@Test
void fragileTest() {
    service.processOrder(order);
    verify(repo).save(any());  // Breaks if implementation changes to saveAll()
    // Better: verify the OUTCOME, not HOW it got there
}

// ANTI-PATTERN 3: Verify + When on same method
@Test
void redundantTest() {
    when(repo.findById(1L)).thenReturn(Optional.of(user));
    service.getUser(1L);
    verify(repo).findById(1L);  // Redundant! If it wasn't called, when() wouldn't work
}

// BEST PRACTICE: Test behavior, not implementation
@Test
void shouldApplyDiscountForPremiumUsers() {
    // Given
    User premiumUser = UserFixtures.premiumUser();
    when(userRepo.findById(1L)).thenReturn(Optional.of(premiumUser));
    when(pricingService.getDiscount(any())).thenReturn(new Discount(0.2));
    
    // When
    OrderResult result = orderService.placeOrder(1L, orderRequest);
    
    // Then
    assertThat(result.getTotalPrice()).isEqualTo(new Money("80.00"));
    assertThat(result.getDiscountApplied()).isEqualTo("20%");
}

// BEST PRACTICE: Use ArgumentCaptor for complex assertions
@Test
void shouldSendCorrectNotification() {
    ArgumentCaptor<Notification> captor = ArgumentCaptor.forClass(Notification.class);
    
    service.processRefund(orderId);
    
    verify(notificationService).send(captor.capture());
    Notification sent = captor.getValue();
    assertThat(sent.getType()).isEqualTo(NotificationType.REFUND);
    assertThat(sent.getRecipient()).isEqualTo("user@example.com");
    assertThat(sent.getAmount()).isEqualTo(new Money("50.00"));
}

// BEST PRACTICE: Custom Answer for complex behavior
@Test
void shouldRetryOnTransientFailure() {
    AtomicInteger attempts = new AtomicInteger(0);
    when(externalService.call(any())).thenAnswer(invocation -> {
        if (attempts.incrementAndGet() < 3) {
            throw new TransientException("Service unavailable");
        }
        return new Response("success");
    });
    
    Result result = retryableService.callWithRetry(request);
    
    assertThat(result.isSuccess()).isTrue();
    assertThat(attempts.get()).isEqualTo(3);
}
```

---

## Q266: Testcontainers - Integration Testing with Real Dependencies

```java
// Testcontainers: spin up real Docker containers for tests
// No more mocking repositories! Test against REAL database

@Testcontainers
@SpringBootTest
@AutoConfigureTestDatabase(replace = Replace.NONE)
class OrderServiceIntegrationTest {
    
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");
    
    @Container
    static GenericContainer<?> redis = new GenericContainer<>("redis:7")
        .withExposedPorts(6379);
    
    @Container
    static KafkaContainer kafka = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.5.0"));
    
    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.redis.host", redis::getHost);
        registry.add("spring.redis.port", () -> redis.getMappedPort(6379));
        registry.add("spring.kafka.bootstrap-servers", kafka::getBootstrapServers);
    }
    
    @Autowired OrderService orderService;
    @Autowired OrderRepository orderRepository;
    
    @Test
    void shouldPersistOrderAndPublishEvent() {
        // Given
        CreateOrderRequest request = new CreateOrderRequest("user1", 
            List.of(new OrderItem("SKU-001", 2, new Money("25.00"))));
        
        // When - hitting REAL database and REAL Kafka!
        Order order = orderService.createOrder(request);
        
        // Then
        assertThat(order.getId()).isNotNull();
        assertThat(order.getStatus()).isEqualTo(OrderStatus.CREATED);
        
        // Verify persisted in real DB
        Order fromDb = orderRepository.findById(order.getId()).orElseThrow();
        assertThat(fromDb.getItems()).hasSize(1);
        assertThat(fromDb.getTotalAmount()).isEqualTo(new Money("50.00"));
        
        // Verify Kafka event published
        ConsumerRecord<String, String> record = KafkaTestUtils.getSingleRecord(
            consumer, "orders.created");
        assertThat(record.value()).contains(order.getId().toString());
    }
}
```

**Testcontainers Best Practices:**
```java
// 1. Singleton containers (share across all tests - FASTER)
abstract class BaseIntegrationTest {
    static final PostgreSQLContainer<?> POSTGRES;
    static final GenericContainer<?> REDIS;
    
    static {
        POSTGRES = new PostgreSQLContainer<>("postgres:15")
            .withReuse(true);  // Reuse across test runs!
        POSTGRES.start();
        
        REDIS = new GenericContainer<>("redis:7")
            .withExposedPorts(6379)
            .withReuse(true);
        REDIS.start();
    }
}

// 2. Custom container modules for your stack
class AppContainer extends GenericContainer<AppContainer> {
    AppContainer() {
        super("my-service:latest");
        withExposedPorts(8080);
        waitingFor(Wait.forHttp("/actuator/health")
            .forPort(8080)
            .forStatusCode(200)
            .withStartupTimeout(Duration.ofSeconds(30)));
    }
}

// 3. Network for container-to-container communication
@Container
static Network network = Network.newNetwork();

@Container
static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:15")
    .withNetwork(network)
    .withNetworkAliases("db");

@Container
static GenericContainer<?> app = new GenericContainer<>("my-app:latest")
    .withNetwork(network)
    .withEnv("DB_HOST", "db")  // Container-to-container via alias
    .dependsOn(db);
```

---

## Q267: Testing Concurrency - How to test multi-threaded code?

```java
class ConcurrentCacheTest {
    
    // Pattern 1: CyclicBarrier to start all threads simultaneously
    @Test
    void shouldHandleConcurrentPuts() throws Exception {
        ConcurrentCache<String, Integer> cache = new ConcurrentCache<>();
        int threadCount = 100;
        CyclicBarrier barrier = new CyclicBarrier(threadCount);
        ExecutorService executor = Executors.newFixedThreadPool(threadCount);
        List<Future<?>> futures = new ArrayList<>();
        
        for (int i = 0; i < threadCount; i++) {
            final int value = i;
            futures.add(executor.submit(() -> {
                barrier.await();  // All threads start at once!
                cache.put("key", value);
                return null;
            }));
        }
        
        // Wait for all to complete
        for (Future<?> f : futures) f.get(5, TimeUnit.SECONDS);
        
        // Verify: exactly one value should be stored
        assertThat(cache.get("key")).isNotNull();
    }
    
    // Pattern 2: Repeat test many times to catch race conditions
    @RepeatedTest(1000)
    void shouldBeThreadSafe() {
        AtomicCounter counter = new AtomicCounter();
        int threads = 10;
        int incrementsPerThread = 1000;
        
        ExecutorService executor = Executors.newFixedThreadPool(threads);
        CountDownLatch latch = new CountDownLatch(threads);
        
        for (int i = 0; i < threads; i++) {
            executor.submit(() -> {
                for (int j = 0; j < incrementsPerThread; j++) {
                    counter.increment();
                }
                latch.countDown();
            });
        }
        
        latch.await(10, TimeUnit.SECONDS);
        assertThat(counter.get()).isEqualTo(threads * incrementsPerThread);
    }
    
    // Pattern 3: Testing for deadlocks
    @Test
    @Timeout(value = 5, unit = TimeUnit.SECONDS)  // Deadlock = test hangs = timeout
    void shouldNotDeadlock() throws Exception {
        Resource r1 = new Resource("A");
        Resource r2 = new Resource("B");
        
        Thread t1 = new Thread(() -> {
            r1.lock();
            Thread.yield();  // Increase chance of interleaving
            r2.lock();
            r2.unlock();
            r1.unlock();
        });
        
        Thread t2 = new Thread(() -> {
            r2.lock();
            Thread.yield();
            r1.lock();
            r1.unlock();
            r2.unlock();
        });
        
        t1.start();
        t2.start();
        t1.join(5000);
        t2.join(5000);
        
        assertThat(t1.isAlive()).isFalse();
        assertThat(t2.isAlive()).isFalse();
    }
    
    // Pattern 4: Using Awaitility for async assertions
    @Test
    void shouldEventuallyProcessMessage() {
        messageBroker.publish("orders", new OrderCreatedEvent(orderId));
        
        Awaitility.await()
            .atMost(Duration.ofSeconds(5))
            .pollInterval(Duration.ofMillis(100))
            .untilAsserted(() -> {
                Order order = orderRepo.findById(orderId).orElseThrow();
                assertThat(order.getStatus()).isEqualTo(OrderStatus.PROCESSED);
            });
    }
}
```

---

## Q268: Test Doubles - Fakes vs Mocks vs Stubs vs Spies

```java
// STUB: Returns canned responses (no verification)
class StubPaymentGateway implements PaymentGateway {
    @Override
    public PaymentResult charge(Money amount, Card card) {
        return PaymentResult.success("txn-123");  // Always succeeds
    }
}

// MOCK: Records interactions for verification (Mockito)
PaymentGateway mock = mock(PaymentGateway.class);
when(mock.charge(any(), any())).thenReturn(PaymentResult.success("txn-123"));
// Later: verify(mock).charge(eq(new Money("50.00")), any());

// FAKE: Working implementation (simplified, in-memory)
class FakePaymentGateway implements PaymentGateway {
    private final Map<String, PaymentResult> transactions = new HashMap<>();
    private double balance = 10000.00;
    
    @Override
    public PaymentResult charge(Money amount, Card card) {
        if (amount.getValue().doubleValue() > balance) {
            return PaymentResult.declined("Insufficient funds");
        }
        balance -= amount.getValue().doubleValue();
        String txnId = UUID.randomUUID().toString();
        PaymentResult result = PaymentResult.success(txnId);
        transactions.put(txnId, result);
        return result;
    }
    
    // Test helper methods
    public double getBalance() { return balance; }
    public int getTransactionCount() { return transactions.size(); }
}

// SPY: Real object with selective overrides
UserService realService = new UserService(repo, emailService);
UserService spy = Mockito.spy(realService);
doReturn(true).when(spy).isFeatureEnabled("new-flow");
// Real methods execute EXCEPT the ones you stub!

// WHEN TO USE WHAT:
// Stub: Simple tests, don't care about interactions
// Mock: Need to verify interactions (was method called with correct args?)
// Fake: Complex integration tests, need realistic behavior
// Spy: Legacy code where you can't inject mocks easily
```

---

## Q269: Testing Spring Boot Applications - Layered Testing Strategy

```java
// LAYER 1: Unit Tests (no Spring context, fastest)
class OrderServiceTest {
    OrderService service;
    OrderRepository repo = mock(OrderRepository.class);  // Mock dependencies
    PaymentService payment = mock(PaymentService.class);
    
    @BeforeEach
    void setup() {
        service = new OrderService(repo, payment);  // Manual wiring
    }
    
    @Test
    void shouldCalculateTotal() {
        Order order = OrderFixtures.withItems(
            item("SKU-1", 2, "10.00"),
            item("SKU-2", 1, "30.00"));
        assertThat(service.calculateTotal(order)).isEqualTo(new Money("50.00"));
    }
}

// LAYER 2: Slice Tests (partial Spring context)
@WebMvcTest(OrderController.class)  // Only web layer
class OrderControllerTest {
    @Autowired MockMvc mockMvc;
    @MockBean OrderService orderService;  // Mock service layer
    
    @Test
    void shouldReturn404ForUnknownOrder() throws Exception {
        when(orderService.findById(999L)).thenReturn(Optional.empty());
        
        mockMvc.perform(get("/api/orders/999"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error").value("Order not found"));
    }
    
    @Test
    void shouldValidateInput() throws Exception {
        mockMvc.perform(post("/api/orders")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""
                {"userId": null, "items": []}
                """))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.errors[0].field").value("userId"));
    }
}

@DataJpaTest  // Only JPA layer (embedded H2 by default)
class OrderRepositoryTest {
    @Autowired OrderRepository repo;
    @Autowired TestEntityManager em;
    
    @Test
    void shouldFindOrdersByStatus() {
        em.persist(OrderFixtures.order(OrderStatus.PENDING));
        em.persist(OrderFixtures.order(OrderStatus.COMPLETED));
        em.persist(OrderFixtures.order(OrderStatus.PENDING));
        
        List<Order> pending = repo.findByStatus(OrderStatus.PENDING);
        assertThat(pending).hasSize(2);
    }
}

// LAYER 3: Integration Tests (full context + Testcontainers)
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@Testcontainers
class OrderIntegrationTest {
    @Autowired TestRestTemplate restTemplate;
    
    @Test
    void fullOrderLifecycle() {
        // Create order
        ResponseEntity<Order> created = restTemplate.postForEntity(
            "/api/orders", createRequest, Order.class);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        
        // Get order
        ResponseEntity<Order> fetched = restTemplate.getForEntity(
            "/api/orders/" + created.getBody().getId(), Order.class);
        assertThat(fetched.getBody().getStatus()).isEqualTo(OrderStatus.CREATED);
        
        // Pay order
        restTemplate.postForEntity(
            "/api/orders/" + created.getBody().getId() + "/pay", 
            paymentRequest, Void.class);
        
        // Verify state changed
        ResponseEntity<Order> paid = restTemplate.getForEntity(
            "/api/orders/" + created.getBody().getId(), Order.class);
        assertThat(paid.getBody().getStatus()).isEqualTo(OrderStatus.PAID);
    }
}

// LAYER 4: Contract Tests (API compatibility between services)
@SpringBootTest
@AutoConfigureMockMvc
@AutoConfigureStubRunner(ids = "com.example:payment-service:+:stubs:8090")
class OrderServiceContractTest {
    // Uses Spring Cloud Contract stubs from payment-service
    // Verifies our service correctly calls payment service
}
```

---

## Q270: Testing Anti-Patterns to Avoid

```java
// 1. ANTI-PATTERN: Testing private methods
// If you feel the need to test a private method, it means:
// a) The class is doing too much (extract a new class)
// b) Test it through the public API

// 2. ANTI-PATTERN: Test coupled to implementation
@Test
void bad_tightlyCoupled() {
    service.processOrder(order);
    verify(repo, times(1)).save(any());      // What if it batches?
    verify(cache, times(1)).invalidate(any()); // What if caching strategy changes?
    // This test breaks on every refactor!
}

@Test
void good_testBehavior() {
    Order result = service.processOrder(order);
    assertThat(result.getStatus()).isEqualTo(PROCESSED);
    // Test WHAT happened, not HOW
}

// 3. ANTI-PATTERN: Shared mutable state between tests
class BadTest {
    static List<Order> orders = new ArrayList<>();  // Shared! Tests interfere!
    
    @Test void test1() { orders.add(new Order()); }
    @Test void test2() { assertThat(orders).isEmpty(); }  // Fails if test1 runs first!
}

// 4. ANTI-PATTERN: Excessive setup (God tests)
@Test
void godTest() {
    // 50 lines of setup...
    User user = new User(); user.setName("..."); user.setEmail("...");
    Address addr = new Address(); addr.setStreet("..."); // ...
    // Better: Use test fixtures / builders
}

// BEST PRACTICE: Test Data Builders
class OrderBuilder {
    private String userId = "default-user";
    private List<OrderItem> items = List.of(defaultItem());
    private OrderStatus status = OrderStatus.CREATED;
    
    static OrderBuilder anOrder() { return new OrderBuilder(); }
    OrderBuilder withUserId(String id) { this.userId = id; return this; }
    OrderBuilder withStatus(OrderStatus s) { this.status = s; return this; }
    OrderBuilder withItems(OrderItem... items) { this.items = List.of(items); return this; }
    Order build() { return new Order(userId, items, status); }
}

// Usage:
Order order = anOrder().withStatus(PAID).withItems(item("SKU-1", 3, "10.00")).build();

// 5. ANTI-PATTERN: Sleep in tests
@Test
void bad_sleep() throws Exception {
    service.processAsync(order);
    Thread.sleep(5000);  // Flaky! Sometimes 5s isn't enough
    assertThat(repo.findById(id)).isPresent();
}

@Test
void good_awaitility() {
    service.processAsync(order);
    Awaitility.await()
        .atMost(Duration.ofSeconds(10))
        .untilAsserted(() -> assertThat(repo.findById(id)).isPresent());
}
```

---

## Q271: Property-Based Testing (jqwik)

```java
// Instead of testing specific examples, test PROPERTIES that should always hold

@Property
void additionIsCommutative(@ForAll int a, @ForAll int b) {
    assertThat(a + b).isEqualTo(b + a);
}

@Property
void sortedListIsAlwaysSorted(@ForAll List<Integer> list) {
    List<Integer> sorted = new ArrayList<>(list);
    Collections.sort(sorted);
    
    for (int i = 0; i < sorted.size() - 1; i++) {
        assertThat(sorted.get(i)).isLessThanOrEqualTo(sorted.get(i + 1));
    }
}

// Real-world: test JSON serialization roundtrip
@Property
void jsonRoundTrip(@ForAll("validOrders") Order order) {
    String json = objectMapper.writeValueAsString(order);
    Order deserialized = objectMapper.readValue(json, Order.class);
    assertThat(deserialized).isEqualTo(order);
}

@Provide
Arbitrary<Order> validOrders() {
    return Combinators.combine(
        Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(50),
        Arbitraries.integers().between(1, 100),
        Arbitraries.of(OrderStatus.values())
    ).as((name, qty, status) -> new Order(name, qty, status));
}

// Test invariants of your data structures
@Property
void concurrentMapNeverLosesData(
    @ForAll @Size(min = 1, max = 100) List<@AlphaChars @StringLength(min = 1, max = 10) String> keys,
    @ForAll @Size(min = 1, max = 100) List<@IntRange(min = 0, max = 1000) Integer> values
) {
    ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
    
    // Put all entries
    for (int i = 0; i < Math.min(keys.size(), values.size()); i++) {
        map.put(keys.get(i), values.get(i));
    }
    
    // Invariant: size never exceeds distinct keys
    assertThat(map.size()).isLessThanOrEqualTo(new HashSet<>(keys).size());
}
```

---

## Q272: Mutation Testing (PITest) - Finding Weak Tests

```java
// Mutation testing: modifies your code and checks if tests catch the mutation

// Original code:
public boolean isEligible(int age, boolean hasLicense) {
    return age >= 18 && hasLicense;
}

// Mutations PITest will try:
// 1. age >= 18  →  age > 18    (boundary mutation)
// 2. age >= 18  →  age <= 18   (negation)
// 3. &&         →  ||          (logical operator)
// 4. return ... →  return true (return value)

// If ANY mutation survives (tests still pass), your tests are WEAK!

// WEAK test (mutation "age > 18" survives):
@Test
void testEligible() {
    assertTrue(isEligible(25, true));   // Passes with >= AND >
    assertFalse(isEligible(15, true));  // Doesn't catch boundary!
}

// STRONG test (kills all mutations):
@Test
void testEligibleBoundary() {
    assertTrue(isEligible(18, true));   // Kills "> 18" mutation!
    assertFalse(isEligible(17, true));  // Kills "<= 18" mutation
    assertFalse(isEligible(18, false)); // Kills "||" mutation
    assertFalse(isEligible(17, false)); // Extra coverage
}

// Maven config:
// <plugin>
//   <groupId>org.pitest</groupId>
//   <artifactId>pitest-maven</artifactId>
//   <configuration>
//     <mutationThreshold>80</mutationThreshold>  <!-- 80% mutations killed -->
//     <targetClasses>com.myapp.service.*</targetClasses>
//   </configuration>
// </plugin>
```

---

## Q273: Architecture Testing (ArchUnit)

```java
// Enforce architectural rules as tests (prevent architectural decay!)

@AnalyzeClasses(packages = "com.myapp")
class ArchitectureTest {
    
    // Layered architecture enforcement
    @ArchTest
    static final ArchRule layeredArchitecture = layeredArchitecture()
        .consideringAllDependencies()
        .layer("Controller").definedBy("..controller..")
        .layer("Service").definedBy("..service..")
        .layer("Repository").definedBy("..repository..")
        .layer("Domain").definedBy("..domain..")
        
        .whereLayer("Controller").mayNotBeAccessedByAnyLayer()
        .whereLayer("Service").mayOnlyBeAccessedByLayers("Controller")
        .whereLayer("Repository").mayOnlyBeAccessedByLayers("Service")
        .whereLayer("Domain").mayOnlyBeAccessedByLayers("Service", "Repository");
    
    // No cyclic dependencies
    @ArchTest
    static final ArchRule noCycles = slices()
        .matching("com.myapp.(*)..")
        .should().beFreeOfCycles();
    
    // Controllers should not access repositories directly
    @ArchTest
    static final ArchRule controllersDoNotAccessRepos = noClasses()
        .that().resideInAPackage("..controller..")
        .should().accessClassesThat().resideInAPackage("..repository..");
    
    // Services should not use Spring MVC annotations
    @ArchTest
    static final ArchRule servicesAreFrameworkFree = noClasses()
        .that().resideInAPackage("..service..")
        .should().beAnnotatedWith(RestController.class)
        .orShould().beAnnotatedWith(RequestMapping.class);
    
    // Domain classes should not depend on infrastructure
    @ArchTest
    static final ArchRule domainIsClean = noClasses()
        .that().resideInAPackage("..domain..")
        .should().dependOnClassesThat()
        .resideInAnyPackage("..repository..", "..controller..", 
            "org.springframework..", "javax.persistence..");
    
    // Naming conventions
    @ArchTest
    static final ArchRule controllerNaming = classes()
        .that().areAnnotatedWith(RestController.class)
        .should().haveSimpleNameEndingWith("Controller");
    
    @ArchTest
    static final ArchRule serviceNaming = classes()
        .that().resideInAPackage("..service..")
        .and().areNotInterfaces()
        .should().haveSimpleNameEndingWith("Service")
        .orShould().haveSimpleNameEndingWith("ServiceImpl");
}
```

---

## Q274: Test Fixtures and Object Mothers

```java
// Object Mother pattern: centralized test data creation
class UserFixtures {
    public static User defaultUser() {
        return User.builder()
            .id(1L)
            .name("John Doe")
            .email("john@example.com")
            .role(Role.USER)
            .createdAt(Instant.parse("2024-01-01T00:00:00Z"))
            .build();
    }
    
    public static User adminUser() {
        return defaultUser().toBuilder()
            .id(2L)
            .name("Admin")
            .email("admin@example.com")
            .role(Role.ADMIN)
            .build();
    }
    
    public static User premiumUser() {
        return defaultUser().toBuilder()
            .subscription(Subscription.PREMIUM)
            .build();
    }
}

// Instancio: Auto-generate test objects with random data
@Test
void shouldCreateUser() {
    User user = Instancio.of(User.class)
        .set(field(User::getRole), Role.USER)
        .ignore(field(User::getId))  // Will be generated by DB
        .create();
    
    User saved = userService.create(user);
    assertThat(saved.getId()).isNotNull();
}

// Faker for realistic test data
class TestDataFactory {
    private static final Faker faker = new Faker();
    
    static User randomUser() {
        return User.builder()
            .name(faker.name().fullName())
            .email(faker.internet().emailAddress())
            .phone(faker.phoneNumber().cellPhone())
            .address(faker.address().fullAddress())
            .build();
    }
}
```

---

## Q275: Contract Testing with Spring Cloud Contract

```java
// Producer side: define contract
// src/test/resources/contracts/shouldReturnOrder.groovy
Contract.make {
    description "should return order by ID"
    request {
        method GET()
        url "/api/orders/1"
        headers {
            header("Authorization", "Bearer valid-token")
        }
    }
    response {
        status 200
        headers {
            contentType applicationJson()
        }
        body([
            id: 1,
            userId: "user-123",
            status: "CREATED",
            totalAmount: 50.00
        ])
    }
}

// Auto-generates:
// 1. Server-side test (verifies producer implements contract)
// 2. Client-side stub (WireMock stub for consumers)

// Consumer side: use stubs
@SpringBootTest
@AutoConfigureStubRunner(
    ids = "com.example:order-service:+:stubs:8090",
    stubsMode = StubRunnerProperties.StubsMode.LOCAL
)
class PaymentServiceContractTest {
    
    @Autowired PaymentService paymentService;
    
    @Test
    void shouldGetOrderFromOrderService() {
        // This calls the WireMock stub (not real service!)
        Order order = paymentService.getOrder(1L);
        assertThat(order.getStatus()).isEqualTo("CREATED");
        assertThat(order.getTotalAmount()).isEqualTo(50.00);
    }
}
```

---

## Q276: Performance Testing in Unit Tests (JMH Microbenchmarks)

```java
// JMH: Java Microbenchmark Harness (proper benchmarking)
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@State(Scope.Benchmark)
@Warmup(iterations = 5, time = 1)
@Measurement(iterations = 10, time = 1)
@Fork(2)
public class CollectionBenchmark {
    
    private List<Integer> arrayList;
    private List<Integer> linkedList;
    
    @Setup
    public void setup() {
        arrayList = new ArrayList<>(IntStream.range(0, 10000).boxed().toList());
        linkedList = new LinkedList<>(IntStream.range(0, 10000).boxed().toList());
    }
    
    @Benchmark
    public int arrayListIteration() {
        int sum = 0;
        for (int i : arrayList) sum += i;
        return sum;
    }
    
    @Benchmark
    public int linkedListIteration() {
        int sum = 0;
        for (int i : linkedList) sum += i;
        return sum;
    }
    
    @Benchmark
    public void arrayListMiddleInsert() {
        arrayList.add(5000, 42);
        arrayList.remove(5000);
    }
    
    @Benchmark
    public void linkedListMiddleInsert() {
        linkedList.add(5000, 42);
        linkedList.remove(5000);
    }
}

// Run: java -jar benchmarks.jar
// Results show ops/ms with confidence intervals

// IMPORTANT: Never benchmark in @Test methods! JMH handles:
// - JIT warmup
// - Dead code elimination prevention
// - Loop optimization prevention
// - GC noise reduction
```

---

## Q277: Testing Event-Driven Systems

```java
// Testing Kafka consumers/producers
@EmbeddedKafka(partitions = 1, topics = {"orders.created", "payments.processed"})
@SpringBootTest
class KafkaIntegrationTest {
    
    @Autowired KafkaTemplate<String, String> kafkaTemplate;
    @Autowired OrderEventConsumer consumer;
    
    @Test
    void shouldProcessOrderCreatedEvent() throws Exception {
        // Publish event
        String event = """
            {"orderId": "ord-1", "userId": "user-1", "amount": 50.00}
            """;
        kafkaTemplate.send("orders.created", "ord-1", event).get();
        
        // Wait for consumer to process
        Awaitility.await()
            .atMost(Duration.ofSeconds(10))
            .untilAsserted(() -> {
                Payment payment = paymentRepo.findByOrderId("ord-1");
                assertThat(payment).isNotNull();
                assertThat(payment.getAmount()).isEqualTo(new Money("50.00"));
            });
    }
    
    @Test
    void shouldHandlePoisonMessage() {
        // Publish invalid message
        kafkaTemplate.send("orders.created", "bad", "not-json").get();
        
        // Verify it ends up in DLQ, not infinite retry
        Awaitility.await()
            .atMost(Duration.ofSeconds(10))
            .untilAsserted(() -> {
                ConsumerRecord<String, String> dlq = KafkaTestUtils.getSingleRecord(
                    dlqConsumer, "orders.created.DLT");
                assertThat(dlq.value()).isEqualTo("not-json");
            });
    }
}

// Testing with in-memory event bus (unit test level)
class InMemoryEventBus implements EventBus {
    private final List<DomainEvent> publishedEvents = new ArrayList<>();
    
    @Override
    public void publish(DomainEvent event) {
        publishedEvents.add(event);
    }
    
    public List<DomainEvent> getPublishedEvents() {
        return Collections.unmodifiableList(publishedEvents);
    }
    
    public <T extends DomainEvent> T getLastEvent(Class<T> type) {
        return publishedEvents.stream()
            .filter(type::isInstance)
            .map(type::cast)
            .reduce((a, b) -> b)
            .orElseThrow();
    }
}

@Test
void shouldPublishOrderCompletedEvent() {
    InMemoryEventBus eventBus = new InMemoryEventBus();
    OrderService service = new OrderService(repo, eventBus);
    
    service.completeOrder(orderId);
    
    OrderCompletedEvent event = eventBus.getLastEvent(OrderCompletedEvent.class);
    assertThat(event.getOrderId()).isEqualTo(orderId);
    assertThat(event.getCompletedAt()).isNotNull();
}
```

---

## Q278: Testing Strategy for Staff Engineers

```
TEST PYRAMID (recommended ratio):

        /  E2E  \          5%  - Selenium/Playwright, full system
       /  Integ  \        15%  - Testcontainers, real DB/Kafka
      / Contract  \       10%  - Spring Cloud Contract
     /   Slice    \       20%  - @WebMvcTest, @DataJpaTest
    /    Unit     \       50%  - Plain JUnit, fast, isolated
   ────────────────

GUIDELINES:
1. Unit tests: pure logic, domain rules, calculations
2. Slice tests: web layer validation, repository queries
3. Integration tests: cross-cutting concerns, transactions
4. Contract tests: API compatibility between services
5. E2E tests: critical business flows only

METRICS TO TRACK:
- Code coverage: 80%+ line coverage (but don't worship it)
- Mutation score: 70%+ (more meaningful than coverage)
- Test execution time: full suite < 5 minutes
- Flaky test rate: < 1% (zero tolerance policy)
- Test-to-code ratio: 1:1 to 3:1

WHAT NOT TO TEST:
- Getters/setters (waste of time)
- Framework code (Spring, Hibernate do their own testing)
- Private methods (test through public API)
- Trivial delegation (method just calls another method)
```

