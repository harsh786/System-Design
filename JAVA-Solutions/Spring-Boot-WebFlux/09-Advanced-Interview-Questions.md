# Advanced Interview Questions - Staff/Architect Level (50 Questions)

## Table of Contents
- [Spring Internals (Q1-Q10)](#spring-internals)
- [Performance & Optimization (Q11-Q20)](#performance--optimization)
- [Architecture Decisions (Q21-Q30)](#architecture-decisions)
- [Distributed Systems (Q31-Q40)](#distributed-systems)
- [Security Deep Dive (Q41-Q50)](#security-deep-dive)

---

## Spring Internals

### Q1: How does Spring create proxies - JDK Dynamic Proxy vs CGLIB?

**Answer:**

```
Spring AOP creates proxies for beans that need cross-cutting concerns:

JDK Dynamic Proxy:
  - Uses java.lang.reflect.Proxy
  - Requires the bean to IMPLEMENT an interface
  - Creates a proxy implementing the SAME interfaces
  - Proxy delegates to InvocationHandler
  - Limitation: Only interface methods are intercepted

CGLIB Proxy:
  - Uses bytecode generation (subclass of target)
  - Does NOT require interface
  - Creates a SUBCLASS of the target bean
  - Overrides methods with interceptor logic
  - Limitation: Cannot proxy final classes/methods

Spring Boot DEFAULT: CGLIB (spring.aop.proxy-target-class=true)
```

```java
// How proxy invocation works
// JDK Dynamic Proxy:
public class JdkDynamicProxy implements InvocationHandler {
    private final Object target;
    private final TransactionInterceptor interceptor;

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        // Before advice (e.g., start transaction)
        interceptor.beforeInvocation(method);
        try {
            Object result = method.invoke(target, args); // Call actual method
            interceptor.afterSuccess(method);
            return result;
        } catch (Throwable t) {
            interceptor.afterException(method, t);
            throw t;
        }
    }
}

// CGLIB Proxy (simplified):
public class UserService$$EnhancerBySpringCGLIB extends UserService {
    private MethodInterceptor interceptor;

    @Override
    public User findById(Long id) {
        // interceptor decides whether to invoke super or apply advice
        return (User) interceptor.intercept(this, findByIdMethod, new Object[]{id}, methodProxy);
    }
}
```

**When does Spring choose which proxy?**
```java
// Force JDK proxy:
@EnableAspectJAutoProxy(proxyTargetClass = false)
// Or: spring.aop.proxy-target-class=false

// Result:
// Interface UserService → JDK proxy (implements UserService interface)
// No interface → CGLIB proxy (always)

// PITFALL: Casting issue with JDK proxy
UserServiceImpl impl = (UserServiceImpl) context.getBean("userService");
// ClassCastException! JDK proxy only implements UserService interface, not UserServiceImpl
```

---

### Q2: How does @Transactional work under the hood?

**Answer:**

```
@Transactional Processing Chain:

1. BeanPostProcessor creates proxy during bean initialization
   → AbstractAutoProxyCreator.postProcessAfterInitialization()
   → Checks if bean has @Transactional → creates proxy

2. When method called on proxy:
   → TransactionInterceptor.invoke()
   → TransactionAspectSupport.invokeWithinTransaction()

3. Transaction lifecycle:
   a. Determine TransactionAttribute (propagation, isolation, etc.)
   b. Get PlatformTransactionManager (or ReactiveTransactionManager)
   c. Create/join transaction based on propagation
   d. Invoke actual method
   e. On success: commit
   f. On exception: rollback (if matches rollbackFor rules)
```

```java
// Simplified internal flow
public class TransactionInterceptor extends TransactionAspectSupport {

    public Object invoke(MethodInvocation invocation) {
        // 1. Get transaction attribute
        TransactionAttribute txAttr = getTransactionAttributeSource()
            .getTransactionAttribute(invocation.getMethod(), targetClass);

        // 2. Get transaction manager
        PlatformTransactionManager tm = determineTransactionManager(txAttr);

        // 3. Create transaction info
        TransactionInfo txInfo = createTransactionIfNecessary(tm, txAttr, joinpointId);

        Object result;
        try {
            // 4. Proceed with actual method
            result = invocation.proceed();
        } catch (Throwable ex) {
            // 5. Handle exception (rollback if needed)
            completeTransactionAfterThrowing(txInfo, ex);
            throw ex;
        }

        // 6. Commit on success
        commitTransactionAfterReturning(txInfo);
        return result;
    }
}

// CRITICAL PITFALL: Self-invocation bypasses proxy!
@Service
public class OrderService {
    @Transactional
    public void processOrder(Long id) {
        this.updateInventory(id); // DIRECT call - NO proxy - NO transaction!
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void updateInventory(Long id) { ... }
}

// FIX: Inject self or use AopContext
@Service
public class OrderService {
    @Lazy @Autowired private OrderService self;

    @Transactional
    public void processOrder(Long id) {
        self.updateInventory(id); // Through proxy - works!
    }
}
```

---

### Q3: BeanFactoryPostProcessor vs BeanPostProcessor - what's the difference?

**Answer:**

```
TIMING IN LIFECYCLE:

1. Load Bean Definitions (from @Component, @Bean, XML)
         ↓
2. BeanFactoryPostProcessor.postProcessBeanFactory()
   → Modifies BEAN DEFINITIONS (metadata) before any bean is created
   → Example: PropertySourcesPlaceholderConfigurer resolves ${...}
         ↓
3. Instantiate beans (constructor)
         ↓
4. BeanPostProcessor.postProcessBeforeInitialization()
   → Modifies BEAN INSTANCES after creation but before init
         ↓
5. Init methods (@PostConstruct, afterPropertiesSet)
         ↓
6. BeanPostProcessor.postProcessAfterInitialization()
   → Modifies BEAN INSTANCES after initialization
   → This is where AOP PROXIES are created!
```

```java
// BeanFactoryPostProcessor - modify definitions
@Component
public class CustomBeanFactoryPostProcessor implements BeanFactoryPostProcessor {
    @Override
    public void postProcessBeanFactory(ConfigurableListableBeanFactory factory) {
        // Runs BEFORE any bean is instantiated
        // Can modify bean definitions
        BeanDefinition bd = factory.getBeanDefinition("myService");
        bd.setScope("prototype"); // Change scope
        bd.getPropertyValues().add("timeout", "5000"); // Add property
    }
}

// BeanPostProcessor - modify instances
@Component
public class CustomBeanPostProcessor implements BeanPostProcessor {
    @Override
    public Object postProcessBeforeInitialization(Object bean, String beanName) {
        // Runs after instantiation, before @PostConstruct
        if (bean instanceof DataSource ds) {
            // Wrap with monitoring
            return new MonitoringDataSourceWrapper(ds);
        }
        return bean;
    }

    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        // Runs after @PostConstruct
        // AOP proxies are created HERE by AbstractAutoProxyCreator
        return bean; // Can return proxy instead of original bean
    }
}
```

**Key difference:**
| Aspect | BeanFactoryPostProcessor | BeanPostProcessor |
|--------|------------------------|-------------------|
| Operates on | Bean definitions (metadata) | Bean instances (objects) |
| When | Before any bean instantiated | During each bean creation |
| Can change | Class, scope, properties, etc. | The actual object (wrap/replace) |
| Example | PropertyPlaceholderConfigurer | AutowiredAnnotationBPP, AbstractAutoProxyCreator |

---

### Q4: How does Spring resolve circular dependencies (3-level cache)?

**Answer:**

```java
// Spring uses THREE maps (caches) to resolve circular dependencies:

// Level 1: Fully initialized singletons
Map<String, Object> singletonObjects = new ConcurrentHashMap<>(256);

// Level 2: Early references (partially initialized - exposed to break cycles)
Map<String, Object> earlySingletonObjects = new ConcurrentHashMap<>(16);

// Level 3: Factory methods that create early references
Map<String, ObjectFactory<?>> singletonFactories = new HashMap<>(16);

// Resolution process for A → B → A cycle:
// 1. Start creating A
//    - A is "currently in creation" (marked)
//    - A constructor called
//    - A's ObjectFactory put in Level 3 (singletonFactories)
//
// 2. Inject B into A → need to create B
//    - B is "currently in creation"
//    - B constructor called
//    - B's ObjectFactory put in Level 3
//
// 3. Inject A into B → A is "currently in creation"!
//    - Check Level 1 (singletonObjects): not there
//    - Check Level 2 (earlySingletonObjects): not there
//    - Check Level 3 (singletonFactories): FOUND A's factory!
//    - Call factory → get early reference to A (possibly wrapped by BPP)
//    - Move A from Level 3 to Level 2
//    - Inject early A reference into B
//
// 4. B initialization completes → B moves to Level 1
// 5. Back to A: B is now available → inject B into A
// 6. A initialization completes → A moves to Level 1, removed from Level 2

// WHY does constructor injection FAIL?
// Because Spring can't put A into Level 3 until AFTER constructor completes
// But constructor NEEDS B → B needs A → A's constructor hasn't finished → DEADLOCK
```

---

### Q5: What is a FactoryBean and how does it differ from BeanFactory?

```java
// BeanFactory: The CONTAINER that creates and manages beans
// FactoryBean: A BEAN that itself is a factory for other beans

// BeanFactory = ApplicationContext (container)
ApplicationContext ctx = new AnnotationConfigApplicationContext(AppConfig.class);
Object bean = ctx.getBean("myService"); // BeanFactory creates myService

// FactoryBean = A factory pattern for complex bean creation
public class SqlSessionFactoryBean implements FactoryBean<SqlSessionFactory> {
    private DataSource dataSource;
    private Resource[] mapperLocations;

    @Override
    public SqlSessionFactory getObject() {
        // Complex creation logic
        SqlSessionFactoryBuilder builder = new SqlSessionFactoryBuilder();
        Configuration config = new Configuration();
        config.setDataSource(dataSource);
        // ... complex setup
        return builder.build(config);
    }

    @Override
    public Class<?> getObjectType() {
        return SqlSessionFactory.class;
    }

    @Override
    public boolean isSingleton() {
        return true;
    }
}

// When you call getBean("sqlSessionFactory"):
// → Returns SqlSessionFactory (the product), NOT the SqlSessionFactoryBean itself
// To get the factory bean itself: getBean("&sqlSessionFactory") (prefix &)

// Real-world FactoryBeans in Spring:
// - ProxyFactoryBean (creates AOP proxies)
// - JndiObjectFactoryBean (JNDI lookups)
// - LocalContainerEntityManagerFactoryBean (JPA EntityManager)
// - SqlSessionFactoryBean (MyBatis)
```

---

### Q6: How does @Async work internally?

```java
// @Async is implemented via AOP proxy (AsyncAnnotationBeanPostProcessor)

// Internal flow:
// 1. AsyncAnnotationBeanPostProcessor detects @Async methods
// 2. Creates proxy (JDK or CGLIB) that wraps the method
// 3. On invocation, proxy submits method to TaskExecutor

// Simplified proxy logic:
public class AsyncExecutionInterceptor implements MethodInterceptor {
    private AsyncTaskExecutor executor;

    @Override
    public Object invoke(MethodInvocation invocation) {
        // Determine executor
        AsyncTaskExecutor executor = determineAsyncExecutor(invocation.getMethod());

        // Submit to executor
        Callable<Object> task = () -> {
            try {
                Object result = invocation.proceed(); // Actual method execution
                if (result instanceof Future) return ((Future<?>) result).get();
                return null;
            } catch (Throwable t) {
                handleError(t, invocation.getMethod(), invocation.getArguments());
                return null;
            }
        };

        return executor.submit(task); // Returns Future
    }
}

// Return types for @Async methods:
@Async
public void asyncVoid() { }                    // Fire and forget

@Async
public Future<String> asyncFuture() {          // Legacy
    return new AsyncResult<>("result");
}

@Async
public CompletableFuture<String> asyncCF() {   // Preferred
    return CompletableFuture.completedFuture("result");
}

// PITFALL 1: @Async on same class (self-invocation doesn't work)
// PITFALL 2: @Async with @Transactional (transaction in caller's thread, not async thread!)
// PITFALL 3: Exception handling - exceptions in void methods are LOST by default

// Custom async exception handler:
@Configuration
@EnableAsync
public class AsyncConfig implements AsyncConfigurer {
    @Override
    public AsyncUncaughtExceptionHandler getAsyncUncaughtExceptionHandler() {
        return (throwable, method, params) -> {
            log.error("Async error in method {}: {}", method.getName(), throwable.getMessage());
        };
    }
}
```

---

### Q7: How does component scanning work internally?

```java
// @ComponentScan triggers ClassPathBeanDefinitionScanner

// Steps:
// 1. Resolve base packages (from @ComponentScan or @SpringBootApplication package)
// 2. Use ASM (bytecode reader) to scan classes WITHOUT loading them
//    → Reads .class files, checks for annotations
//    → Much faster than Class.forName() + reflection
// 3. Apply include/exclude filters
// 4. Register matching classes as BeanDefinitions

// Internal scanner logic (simplified):
public class ClassPathScanningCandidateComponentProvider {

    public Set<BeanDefinition> findCandidateComponents(String basePackage) {
        Set<BeanDefinition> candidates = new LinkedHashSet<>();

        // Resolve to filesystem path: com.example → com/example/**/*.class
        String packageSearchPath = "classpath*:" + basePackage.replace('.', '/') + "/**/*.class";

        // Use PathMatchingResourcePatternResolver to find all .class files
        Resource[] resources = resourcePatternResolver.getResources(packageSearchPath);

        for (Resource resource : resources) {
            // Read class metadata using ASM (no class loading!)
            MetadataReader metadataReader = metadataReaderFactory.getMetadataReader(resource);

            // Check filters: @Component, @Service, @Repository, @Controller, @Configuration
            if (isCandidateComponent(metadataReader)) {
                ScannedGenericBeanDefinition bd = new ScannedGenericBeanDefinition(metadataReader);
                candidates.add(bd);
            }
        }
        return candidates;
    }
}

// Performance optimization: spring-context-indexer
// At compile time, generates META-INF/spring.components
// Lists all @Component classes → no classpath scanning at runtime!
// Add dependency: spring-context-indexer (annotation processor)
```

---

### Q8: What happens during ApplicationContext.refresh()?

```java
// THE most important method in Spring - creates the entire container

public void refresh() {
    // 1. Prepare (set start date, active flag, validate required properties)
    prepareRefresh();

    // 2. Get fresh BeanFactory (or create DefaultListableBeanFactory)
    ConfigurableListableBeanFactory beanFactory = obtainFreshBeanFactory();

    // 3. Configure BeanFactory (classloader, BeanPostProcessors, environment)
    prepareBeanFactory(beanFactory);

    // 4. Template method for subclass post-processing
    postProcessBeanFactory(beanFactory);

    // 5. Invoke BeanFactoryPostProcessors
    //    → ConfigurationClassPostProcessor: processes @Configuration, @ComponentScan, @Import, @Bean
    //    → PropertySourcesPlaceholderConfigurer: resolves ${} placeholders
    invokeBeanFactoryPostProcessors(beanFactory);

    // 6. Register BeanPostProcessors (AutowiredAnnotationBPP, etc.)
    registerBeanPostProcessors(beanFactory);

    // 7. Initialize MessageSource (i18n)
    initMessageSource();

    // 8. Initialize event multicaster
    initApplicationEventMulticaster();

    // 9. Template method for special beans (embedded web server created HERE!)
    onRefresh();

    // 10. Register listeners
    registerListeners();

    // 11. Instantiate ALL remaining singletons (non-lazy)
    //     → This is where ALL your beans are created
    //     → Dependency injection happens here
    //     → @PostConstruct called here
    finishBeanFactoryInitialization(beanFactory);

    // 12. Publish ContextRefreshedEvent, start lifecycle beans, web server
    finishRefresh();
}
```

---

### Q9: How does Spring handle multiple ApplicationContexts?

```java
// Parent-Child Context Hierarchy:
// Child context can access beans from parent, NOT vice versa

// Traditional Spring MVC (before Spring Boot):
// Root Context (parent): Service, Repository, Infrastructure beans
// Servlet Context (child): Controllers, ViewResolvers, HandlerMappings

// Spring Boot: Single context by default (simplified)
// But can create hierarchy:
SpringApplicationBuilder builder = new SpringApplicationBuilder();
builder.parent(ParentConfig.class)     // Parent context
    .child(ChildConfig.class)          // Child context
    .run(args);

// Use cases for multiple contexts:
// 1. Modular applications (each module = own context)
// 2. Multi-servlet applications (different DispatcherServlets)
// 3. Testing (test context with overrides)

// Spring Cloud creates Bootstrap context (parent of application context)
// For config server, encryption, discovery initialization
```

---

### Q10: How does SpEL (Spring Expression Language) work internally?

```java
// SpEL is a powerful expression language for runtime evaluation

// Parser → AST → Evaluation
ExpressionParser parser = new SpelExpressionParser();
Expression exp = parser.parseExpression("'Hello World'.length()");
Integer length = exp.getValue(Integer.class); // 11

// In annotations:
@Value("#{systemProperties['user.home']}") String home;
@Value("#{@myBean.computeValue()}") int computed;
@Value("#{T(java.lang.Math).random() * 100}") double random;
@Value("#{${app.timeout:5000} * 2}") int doubleTimeout;

// In @PreAuthorize:
@PreAuthorize("hasRole('ADMIN') or #user.id == authentication.principal.id")
public void updateUser(User user) { }

// SpEL features:
// - Property access: user.name
// - Method invocation: list.size()
// - Type references: T(java.lang.Math).PI
// - Bean references: @myBean.method()
// - Ternary operator: condition ? 'yes' : 'no'
// - Elvis operator: value ?: 'default'
// - Safe navigation: user?.address?.city
// - Collection selection: users.?[age > 18]
// - Collection projection: users.![name]
// - Template expressions: "Hello #{name}"

// Performance consideration:
// SpEL compilation (since Spring 4.1):
SpelParserConfiguration config = new SpelParserConfiguration(
    SpelCompilerMode.IMMEDIATE, // Compile to bytecode after first evaluation
    this.getClass().getClassLoader());
ExpressionParser parser = new SpelExpressionParser(config);
// After first evaluation, expression is compiled to bytecode for speed
```

---

## Performance & Optimization

### Q11: How to optimize Spring Boot startup time?

```java
// 1. Lazy Initialization
spring.main.lazy-initialization=true
// Beans created on first access, not at startup
// Drawback: First request is slower, errors detected later

// 2. Selective lazy
@Configuration
public class LazyConfig {
    @Lazy
    @Bean
    public ExpensiveService expensiveService() { return new ExpensiveService(); }
}

// 3. Spring Boot AOT (Ahead of Time) - Spring Boot 3
// At build time, generates:
// - Bean definitions as code (no runtime reflection)
// - Configuration class proxies
// - Autoconfiguration hints
// Build: mvn spring-boot:aot-generate

// 4. GraalVM Native Image
// Compiles to native binary, ~50ms startup
// Build: mvn -Pnative spring-boot:build-image
// Limitations: No runtime reflection, limited dynamic features

// 5. Class Data Sharing (CDS)
// Step 1: Create class list
java -Xshare:off -XX:DumpLoadedClassList=classes.lst -jar app.jar
// Step 2: Create archive
java -Xshare:dump -XX:SharedClassListFile=classes.lst -XX:SharedArchiveFile=app.jsa
// Step 3: Use archive
java -Xshare:on -XX:SharedArchiveFile=app.jsa -jar app.jar
// Benefit: 10-30% faster startup (classes pre-verified and pre-linked)

// 6. Reduce auto-configuration
@SpringBootApplication(exclude = {
    DataSourceAutoConfiguration.class,
    HibernateJpaAutoConfiguration.class,
    MongoAutoConfiguration.class
})
// Only include what you actually use

// 7. spring-context-indexer
// Generates META-INF/spring.components at compile time
// Eliminates classpath scanning at runtime
// Add: spring-context-indexer as annotation processor dependency

// 8. Startup actuator analysis
management.endpoint.startup.enabled=true
// GET /actuator/startup → shows exactly where time is spent
```

---

### Q12: How to implement CQRS in Spring Boot?

```java
// CQRS: Separate read and write models

// WRITE SIDE (Commands)
@Service
public class OrderCommandService {
    @Autowired private OrderRepository writeRepo; // PostgreSQL
    @Autowired private KafkaTemplate<String, OrderEvent> kafka;

    @Transactional
    public Order createOrder(CreateOrderCommand cmd) {
        Order order = Order.create(cmd);
        writeRepo.save(order);

        // Publish event for read model sync
        kafka.send("order-events", order.getId(),
            new OrderCreatedEvent(order.getId(), order.getItems(), order.getTotal()));

        return order;
    }
}

// READ SIDE (Queries) - Denormalized for fast reads
@Service
public class OrderQueryService {
    @Autowired private OrderReadRepository readRepo; // MongoDB/Elasticsearch

    public OrderView getOrder(String id) {
        return readRepo.findById(id); // Optimized read model
    }

    public List<OrderSummary> searchOrders(OrderSearchCriteria criteria) {
        return readRepo.search(criteria); // Full-text search, aggregations
    }
}

// Event consumer: Syncs write events to read model
@Component
public class OrderEventConsumer {
    @Autowired private OrderReadRepository readRepo;

    @KafkaListener(topics = "order-events")
    public void handleOrderEvent(OrderEvent event) {
        if (event instanceof OrderCreatedEvent created) {
            OrderView view = new OrderView(
                created.getOrderId(),
                created.getItems(),
                created.getTotal(),
                "CREATED"
            );
            readRepo.save(view); // Update read model
        }
    }
}
```

---

### Q13: How to implement multi-tenancy in Spring Boot?

```java
// Strategy 1: Schema per tenant (recommended for data isolation)
@Component
public class TenantIdentifierResolver implements CurrentTenantIdentifierResolver {
    @Override
    public String resolveCurrentTenantIdentifier() {
        return TenantContext.getCurrentTenant(); // From ThreadLocal/Request header
    }
}

@Component
public class TenantConnectionProvider implements MultiTenantConnectionProvider {
    @Autowired private DataSource dataSource;

    @Override
    public Connection getConnection(String tenantId) throws SQLException {
        Connection conn = dataSource.getConnection();
        conn.setSchema(tenantId); // Switch to tenant's schema
        return conn;
    }
}

// Configuration
spring.jpa.properties.hibernate.multiTenancy=SCHEMA
spring.jpa.properties.hibernate.tenant_identifier_resolver=com.example.TenantIdentifierResolver
spring.jpa.properties.hibernate.multi_tenant_connection_provider=com.example.TenantConnectionProvider

// Filter to extract tenant from request
@Component
public class TenantFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain) throws Exception {
        String tenant = request.getHeader("X-Tenant-Id");
        if (tenant == null) tenant = "default";
        TenantContext.setCurrentTenant(tenant);
        try {
            chain.doFilter(request, response);
        } finally {
            TenantContext.clear();
        }
    }
}

// Strategy 2: Discriminator column (shared schema)
@Entity
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = String.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class Order {
    @Column(name = "tenant_id")
    private String tenantId;
}
```

---

### Q14: Event Sourcing implementation in Spring Boot

```java
// Event Store
@Entity
@Table(name = "event_store")
public class StoredEvent {
    @Id @GeneratedValue private Long eventId;
    private String aggregateId;
    private String aggregateType;
    private int version;
    private String eventType;
    private String payload; // JSON
    private Instant timestamp;
}

@Repository
public interface EventStoreRepository extends JpaRepository<StoredEvent, Long> {
    List<StoredEvent> findByAggregateIdOrderByVersionAsc(String aggregateId);
    Optional<StoredEvent> findTopByAggregateIdOrderByVersionDesc(String aggregateId);
}

// Aggregate
public class OrderAggregate {
    private String id;
    private String status;
    private List<OrderItem> items;
    private BigDecimal total;
    private int version;
    private List<DomainEvent> uncommittedEvents = new ArrayList<>();

    // Reconstruct from events
    public static OrderAggregate fromEvents(List<DomainEvent> events) {
        OrderAggregate aggregate = new OrderAggregate();
        events.forEach(aggregate::apply);
        aggregate.uncommittedEvents.clear();
        return aggregate;
    }

    // Command handler
    public void createOrder(CreateOrderCommand cmd) {
        if (this.id != null) throw new IllegalStateException("Already created");
        apply(new OrderCreatedEvent(cmd.getOrderId(), cmd.getItems()));
    }

    public void confirmOrder() {
        if (!"PENDING".equals(status)) throw new IllegalStateException("Cannot confirm");
        apply(new OrderConfirmedEvent(this.id));
    }

    // Event handler (mutates state)
    private void apply(DomainEvent event) {
        if (event instanceof OrderCreatedEvent e) {
            this.id = e.getOrderId();
            this.items = e.getItems();
            this.status = "PENDING";
        } else if (event instanceof OrderConfirmedEvent e) {
            this.status = "CONFIRMED";
        }
        this.version++;
        this.uncommittedEvents.add(event);
    }
}

// Command handler service
@Service
public class OrderCommandHandler {
    @Autowired private EventStoreRepository eventStore;
    @Autowired private KafkaTemplate<String, DomainEvent> kafka;

    @Transactional
    public void handle(CreateOrderCommand cmd) {
        // Load aggregate from events
        List<StoredEvent> stored = eventStore.findByAggregateIdOrderByVersionAsc(cmd.getOrderId());
        OrderAggregate aggregate = OrderAggregate.fromEvents(toDomainEvents(stored));

        // Execute command
        aggregate.createOrder(cmd);

        // Persist new events
        for (DomainEvent event : aggregate.getUncommittedEvents()) {
            StoredEvent se = new StoredEvent(cmd.getOrderId(), "Order",
                aggregate.getVersion(), event.getClass().getName(),
                toJson(event), Instant.now());
            eventStore.save(se);
            kafka.send("order-events", event); // Publish for read models
        }
    }
}
```

---

### Q15: Saga pattern - Orchestration vs Choreography

```java
// ORCHESTRATION (central coordinator)
@Service
public class OrderSagaOrchestrator {
    @Autowired private PaymentService paymentService;
    @Autowired private InventoryService inventoryService;
    @Autowired private ShippingService shippingService;

    @Transactional
    public OrderResult processOrder(Order order) {
        SagaState saga = new SagaState(order.getId());

        try {
            // Step 1: Reserve inventory
            saga.setStep("INVENTORY_RESERVE");
            inventoryService.reserve(order.getItems());

            // Step 2: Process payment
            saga.setStep("PAYMENT");
            paymentService.charge(order.getPayment());

            // Step 3: Schedule shipping
            saga.setStep("SHIPPING");
            shippingService.schedule(order);

            saga.setStatus("COMPLETED");
            return OrderResult.success(order);

        } catch (PaymentFailedException e) {
            // Compensate: release inventory
            inventoryService.release(order.getItems());
            saga.setStatus("COMPENSATED");
            return OrderResult.failed("Payment failed");

        } catch (ShippingException e) {
            // Compensate: refund + release inventory
            paymentService.refund(order.getPayment());
            inventoryService.release(order.getItems());
            saga.setStatus("COMPENSATED");
            return OrderResult.failed("Shipping failed");
        }
    }
}

// CHOREOGRAPHY (event-driven, no coordinator)
// Each service listens for events and reacts

@Service  // In Inventory Service
public class InventoryEventHandler {
    @KafkaListener(topics = "order-created")
    public void onOrderCreated(OrderCreatedEvent event) {
        try {
            inventoryRepo.reserve(event.getItems());
            kafka.send("inventory-reserved", new InventoryReservedEvent(event.getOrderId()));
        } catch (Exception e) {
            kafka.send("inventory-failed", new InventoryFailedEvent(event.getOrderId(), e.getMessage()));
        }
    }

    @KafkaListener(topics = "payment-failed")
    public void onPaymentFailed(PaymentFailedEvent event) {
        // Compensating action
        inventoryRepo.release(event.getOrderId());
    }
}

@Service  // In Payment Service
public class PaymentEventHandler {
    @KafkaListener(topics = "inventory-reserved")
    public void onInventoryReserved(InventoryReservedEvent event) {
        try {
            paymentGateway.charge(event.getOrderId());
            kafka.send("payment-completed", new PaymentCompletedEvent(event.getOrderId()));
        } catch (Exception e) {
            kafka.send("payment-failed", new PaymentFailedEvent(event.getOrderId()));
        }
    }
}
```

| Aspect | Orchestration | Choreography |
|--------|--------------|--------------|
| Coupling | Central coordinator knows all steps | Services independent |
| Complexity | Logic in one place | Distributed logic |
| Debugging | Easier (one place) | Harder (trace events) |
| Single point of failure | Orchestrator | None |
| Scalability | Orchestrator can be bottleneck | Better |
| Best for | Complex workflows | Simple 2-3 step processes |

---

## Distributed Systems

### Q31: How to implement distributed tracing with Micrometer Tracing?

```java
// Spring Boot 3 uses Micrometer Tracing (replaces Spring Cloud Sleuth)

// Dependencies:
// - micrometer-tracing-bridge-brave (Zipkin)
// - or micrometer-tracing-bridge-otel (OpenTelemetry)

// Configuration
management:
  tracing:
    sampling:
      probability: 1.0  # 100% sampling (lower in production)
  zipkin:
    tracing:
      endpoint: http://zipkin:9411/api/v2/spans

// Automatic propagation:
// Spring Boot auto-instruments:
// - RestTemplate / WebClient calls (inject trace headers)
// - @Async methods
// - Kafka producers/consumers
// - Spring Data repositories

// Trace context propagation:
// HTTP Header: traceparent: 00-<trace-id>-<span-id>-<flags>
// W3C Trace Context format (OpenTelemetry standard)

// Custom spans:
@Service
public class OrderService {
    @Autowired private Tracer tracer;

    public Order processOrder(Order order) {
        Span span = tracer.nextSpan().name("process-order").start();
        try (Tracer.SpanInScope ws = tracer.withSpan(span)) {
            span.tag("order.id", order.getId());
            span.tag("order.amount", order.getTotal().toString());

            // Business logic
            Order result = doProcess(order);

            span.event("order.processed");
            return result;
        } catch (Exception e) {
            span.error(e);
            throw e;
        } finally {
            span.end();
        }
    }
}

// With @Observed annotation (Micrometer Observation API)
@Observed(name = "order.process", contextualName = "processing-order")
public Order processOrder(Order order) {
    return doProcess(order);
}
```

---

### Q32: How to implement idempotency?

```java
// Pattern: Idempotency key stored in database

@RestController
public class PaymentController {
    @PostMapping("/payments")
    public ResponseEntity<Payment> createPayment(
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @RequestBody PaymentRequest request) {
        return paymentService.processIdempotent(idempotencyKey, request);
    }
}

@Service
public class PaymentService {
    @Autowired private IdempotencyRepository idempotencyRepo;
    @Autowired private PaymentGateway gateway;

    @Transactional
    public ResponseEntity<Payment> processIdempotent(String key, PaymentRequest request) {
        // Check if already processed
        Optional<IdempotencyRecord> existing = idempotencyRepo.findByKey(key);
        if (existing.isPresent()) {
            // Return cached response (idempotent!)
            return ResponseEntity.ok(deserialize(existing.get().getResponse()));
        }

        // Process new request
        Payment payment = gateway.charge(request);

        // Store result for future duplicate requests
        idempotencyRepo.save(new IdempotencyRecord(
            key, serialize(payment), HttpStatus.CREATED.value(),
            Instant.now().plus(Duration.ofHours(24)) // Expire after 24h
        ));

        return ResponseEntity.status(HttpStatus.CREATED).body(payment);
    }
}

@Entity
@Table(name = "idempotency_keys")
public class IdempotencyRecord {
    @Id
    @Column(unique = true)
    private String idempotencyKey;
    private String response;
    private int statusCode;
    private Instant expiresAt;
    private Instant createdAt;
}

// For database operations: Use INSERT ON CONFLICT DO NOTHING
// For message processing: Store processed message IDs
@KafkaListener(topics = "orders")
public void handleOrder(OrderEvent event) {
    if (processedEvents.contains(event.getEventId())) {
        return; // Already processed - skip (idempotent)
    }
    processOrder(event);
    processedEvents.add(event.getEventId());
}
```

---

## Security Deep Dive

### Q41: OAuth2 Authorization Code with PKCE flow

```java
// Spring Security OAuth2 Client configuration
spring:
  security:
    oauth2:
      client:
        registration:
          my-provider:
            client-id: my-app
            client-secret: ${CLIENT_SECRET}
            scope: openid,profile,email
            authorization-grant-type: authorization_code
            redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"
        provider:
          my-provider:
            authorization-uri: https://auth.example.com/authorize
            token-uri: https://auth.example.com/token
            user-info-uri: https://auth.example.com/userinfo
            jwk-set-uri: https://auth.example.com/.well-known/jwks.json

// PKCE Flow (Proof Key for Code Exchange):
// 1. Client generates: code_verifier (random 43-128 chars)
// 2. Client computes: code_challenge = BASE64URL(SHA256(code_verifier))
// 3. Authorization request includes: code_challenge + code_challenge_method=S256
// 4. Auth server stores code_challenge with auth code
// 5. Token request includes: code_verifier
// 6. Auth server verifies: SHA256(code_verifier) == stored code_challenge
// 7. If match → issue tokens

// Security config
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**").permitAll()
                .anyRequest().authenticated())
            .oauth2Login(oauth2 -> oauth2
                .userInfoEndpoint(userInfo -> userInfo
                    .userService(customOAuth2UserService())))
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthConverter())))
            .build();
    }
}
```

---

### Q42: JWT token validation internals

```java
// JWT Structure: header.payload.signature
// Header: {"alg":"RS256","typ":"JWT","kid":"key-id-1"}
// Payload: {"sub":"user123","roles":["ADMIN"],"exp":1700000000,"iss":"auth.example.com"}
// Signature: RS256(base64url(header) + "." + base64url(payload), private_key)

// Spring Security JWT validation steps:
// 1. Extract token from Authorization: Bearer <token>
// 2. Decode header → get algorithm and key ID
// 3. Fetch public key from JWK Set endpoint (cached)
// 4. Verify signature using public key
// 5. Validate claims:
//    - exp (not expired)
//    - nbf (not before)
//    - iss (issuer matches)
//    - aud (audience matches)
// 6. Map claims to Spring Security authorities

@Bean
public JwtDecoder jwtDecoder() {
    NimbusJwtDecoder decoder = NimbusJwtDecoder
        .withJwkSetUri("https://auth.example.com/.well-known/jwks.json")
        .build();

    // Custom validation
    OAuth2TokenValidator<Jwt> validator = new DelegatingOAuth2TokenValidator<>(
        JwtValidators.createDefaultWithIssuer("https://auth.example.com"),
        new AudienceValidator("my-api"),
        new CustomClaimValidator()
    );
    decoder.setJwtValidator(validator);
    return decoder;
}

// Custom JWT to Authentication converter
@Bean
public JwtAuthenticationConverter jwtAuthConverter() {
    JwtGrantedAuthoritiesConverter authConverter = new JwtGrantedAuthoritiesConverter();
    authConverter.setAuthoritiesClaimName("roles"); // Map "roles" claim
    authConverter.setAuthorityPrefix("ROLE_");

    JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
    converter.setJwtGrantedAuthoritiesConverter(authConverter);
    return converter;
}
```

---

### Q43: Spring Security filter chain - complete order

```
Security Filter Chain Order (Spring Security 6):

1.  DisableEncodeUrlFilter             - Prevent session ID in URLs
2.  WebAsyncManagerIntegrationFilter   - Async security context
3.  SecurityContextHolderFilter        - Load/save SecurityContext
4.  HeaderWriterFilter                 - Security headers (HSTS, X-Frame, etc.)
5.  CorsFilter                         - CORS handling
6.  CsrfFilter                         - CSRF token validation
7.  LogoutFilter                        - Process /logout
8.  OAuth2AuthorizationRequestRedirectFilter - OAuth2 authorization redirect
9.  OAuth2LoginAuthenticationFilter     - OAuth2 callback processing
10. UsernamePasswordAuthenticationFilter - Form login
11. BearerTokenAuthenticationFilter     - JWT/OAuth2 resource server
12. RequestCacheAwareFilter             - Saved request handling
13. SecurityContextHolderAwareRequestFilter - Servlet API integration
14. AnonymousAuthenticationFilter       - Anonymous user creation
15. ExceptionTranslationFilter          - Handles access denied/auth required
16. AuthorizationFilter                 - URL-based authorization check

// Each filter calls chain.doFilter() to pass to next
// Any filter can short-circuit the chain (e.g., return 401)
```

```java
// Custom filter insertion:
@Bean
public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    return http
        .addFilterBefore(new ApiKeyFilter(), UsernamePasswordAuthenticationFilter.class)
        .addFilterAfter(new AuditFilter(), AuthorizationFilter.class)
        .build();
}
```

---

### Q44: Rate limiting implementation

```java
// Token Bucket Algorithm
@Component
public class TokenBucketRateLimiter {
    private final ConcurrentHashMap<String, Bucket> buckets = new ConcurrentHashMap<>();

    public boolean tryConsume(String clientId) {
        Bucket bucket = buckets.computeIfAbsent(clientId, this::createBucket);
        return bucket.tryConsume(1);
    }

    private Bucket createBucket(String clientId) {
        Bandwidth limit = Bandwidth.classic(100, Refill.greedy(100, Duration.ofMinutes(1)));
        return Bucket.builder().addLimit(limit).build();
    }
}

// Redis-based distributed rate limiter (Spring Cloud Gateway)
@Bean
public KeyResolver userKeyResolver() {
    return exchange -> Mono.just(
        exchange.getRequest().getHeaders().getFirst("X-API-Key"));
}

// application.yml for Spring Cloud Gateway:
spring:
  cloud:
    gateway:
      routes:
        - id: api-route
          uri: lb://api-service
          predicates:
            - Path=/api/**
          filters:
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 100  # 100 req/sec steady
                redis-rate-limiter.burstCapacity: 200  # Allow burst to 200
                redis-rate-limiter.requestedTokens: 1
                key-resolver: "#{@userKeyResolver}"

// Sliding window rate limiter with Redis
@Service
public class SlidingWindowRateLimiter {
    @Autowired private RedisTemplate<String, String> redis;

    public boolean isAllowed(String clientId, int maxRequests, Duration window) {
        String key = "rate:" + clientId;
        long now = Instant.now().toEpochMilli();
        long windowStart = now - window.toMillis();

        // Remove old entries
        redis.opsForZSet().removeRangeByScore(key, 0, windowStart);

        // Count current window
        Long count = redis.opsForZSet().zCard(key);
        if (count != null && count >= maxRequests) {
            return false; // Rate limited
        }

        // Add current request
        redis.opsForZSet().add(key, String.valueOf(now), now);
        redis.expire(key, window);
        return true;
    }
}
```

---

### Q45-Q50: Additional topics covered briefly

**Q45: Secrets management with HashiCorp Vault**
```java
// spring-cloud-vault-config dependency
spring:
  cloud:
    vault:
      uri: https://vault.example.com:8200
      authentication: KUBERNETES  # or TOKEN, APPROLE
      kubernetes:
        role: my-app
      kv:
        enabled: true
        backend: secret
        application-name: my-app
// Secrets injected as properties: ${db.password}
```

**Q46: mTLS between microservices**
```yaml
server:
  ssl:
    key-store: classpath:keystore.p12
    key-store-password: ${KEYSTORE_PASS}
    client-auth: need  # Require client certificate
    trust-store: classpath:truststore.p12
```

**Q47: CAP theorem in practice**
```
CP Systems: ZooKeeper, etcd, Consul (consistency over availability)
AP Systems: Cassandra, DynamoDB, Couchbase (availability over consistency)
CA Systems: Traditional RDBMS (single node, no partition tolerance)

In microservices: Usually choose AP with eventual consistency
Use sagas, event sourcing, compensating transactions
```

**Q48: Exactly-once semantics with Kafka**
```java
// Producer: enable.idempotence=true + transactional.id
// Consumer: read_committed isolation + manual offset commit
@KafkaListener(topics = "orders")
@Transactional
public void process(ConsumerRecord<String, Order> record) {
    orderService.process(record.value()); // DB write
    // Kafka offset committed with DB transaction (transactional outbox)
}
```

**Q49: Leader election with Redis**
```java
// Using Redisson
RLock lock = redisson.getLock("leader-election");
if (lock.tryLock(0, 30, TimeUnit.SECONDS)) {
    // I am the leader for 30 seconds
    performLeaderTasks();
}
```

**Q50: Database migration strategies**
```java
// Flyway (declarative migrations)
// V1__Create_users.sql, V2__Add_email_column.sql
// Runs migrations in order, tracks in flyway_schema_history table

// Blue-Green database migration:
// 1. Add new column (nullable) - backward compatible
// 2. Deploy new code that writes to both columns
// 3. Backfill old data to new column
// 4. Deploy code that reads from new column
// 5. Remove old column

// This ensures zero-downtime deployment with schema changes
```
