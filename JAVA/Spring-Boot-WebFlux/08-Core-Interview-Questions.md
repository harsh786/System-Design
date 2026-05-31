# Core Interview Questions - Spring Boot Fundamentals (50 Questions)

## Table of Contents
- [Spring IoC & DI](#spring-ioc--di)
- [Bean Scopes & Lifecycle](#bean-scopes--lifecycle)
- [Configuration & Properties](#configuration--properties)
- [Spring Boot Auto-Configuration](#spring-boot-auto-configuration)
- [REST API Development](#rest-api-development)
- [Data Access](#data-access)
- [Exception Handling](#exception-handling)
- [Validation](#validation)
- [Profiles & Environments](#profiles--environments)
- [Logging & Monitoring](#logging--monitoring)

---

## Spring IoC & DI

### Q1: What is Inversion of Control (IoC) and how does Spring implement it?

**Answer:**

IoC inverts the control of object creation from the application code to the framework. Instead of `new MyService()`, the container creates and manages objects.

Spring implements IoC through:
1. **BeanFactory** - lazy, lightweight container
2. **ApplicationContext** - eager, full-featured (extends BeanFactory)

```java
// WITHOUT IoC (tight coupling)
public class OrderService {
    private PaymentService paymentService = new PaymentService(); // YOU control creation
    private InventoryService inventoryService = new InventoryService();
}

// WITH IoC (loose coupling)
@Service
public class OrderService {
    private final PaymentService paymentService;       // CONTAINER controls creation
    private final InventoryService inventoryService;   // and injection
    
    public OrderService(PaymentService paymentService, InventoryService inventoryService) {
        this.paymentService = paymentService;
        this.inventoryService = inventoryService;
    }
}
```

**Why it matters at Staff/Architect level:**
- Enables testability (mock injections)
- Enables configuration-driven behavior (swap implementations)
- Enables AOP (proxies only possible when container manages objects)
- Enables lifecycle management (startup/shutdown ordering)

### Q2: What are the different types of Dependency Injection?

```java
// 1. CONSTRUCTOR INJECTION (Recommended)
@Service
public class UserService {
    private final UserRepository repo;       // Final = immutable
    private final NotificationService notif;
    
    // Spring injects automatically (single constructor, no @Autowired needed since 4.3)
    public UserService(UserRepository repo, NotificationService notif) {
        this.repo = repo;
        this.notif = notif;
    }
}

// 2. SETTER INJECTION (For optional dependencies)
@Service
public class ReportService {
    private CacheService cacheService; // Optional
    
    @Autowired(required = false)
    public void setCacheService(CacheService cacheService) {
        this.cacheService = cacheService;
    }
}

// 3. FIELD INJECTION (Avoid - hard to test, hides dependencies)
@Service
public class BadService {
    @Autowired
    private UserRepository repo; // Can't set in unit test without reflection!
}
```

### Q3: How does `@Qualifier` work and when do you need it?

```java
// When multiple beans of same type exist
public interface NotificationSender {
    void send(String message);
}

@Service("email")
public class EmailNotification implements NotificationSender { }

@Service("sms")
public class SmsNotification implements NotificationSender { }

// Without @Qualifier → NoUniqueBeanDefinitionException
// With @Qualifier → specifies which one

@Service
public class AlertService {
    private final NotificationSender sender;
    
    public AlertService(@Qualifier("email") NotificationSender sender) {
        this.sender = sender;
    }
}

// Alternative: @Primary (default when no qualifier specified)
@Primary
@Service
public class EmailNotification implements NotificationSender { }
```

### Q4: Explain `@Primary` vs `@Qualifier` vs `@ConditionalOnMissingBean`

```java
// @Primary: "Use me as default if no specific qualifier"
@Primary
@Bean
public DataSource primaryDataSource() { return new HikariDataSource(); }

// @Qualifier: "Use this specific bean"
@Bean
@Qualifier("reporting")
public DataSource reportingDataSource() { return new HikariDataSource(); }

// @ConditionalOnMissingBean: "Only create me if no other bean of this type exists"
// Used in auto-configuration to provide defaults that users can override
@Bean
@ConditionalOnMissingBean(DataSource.class)
public DataSource defaultDataSource() { return new EmbeddedDatabaseBuilder().build(); }

// Priority order:
// 1. Exact @Qualifier match
// 2. @Primary bean
// 3. Bean name matching field name
// 4. Error if ambiguous
```

### Q5: What is the difference between `@Component`, `@Service`, `@Repository`, `@Controller`?

```java
// ALL are stereotypes (specializations of @Component)
// Spring scans and registers them as beans

@Component   // Generic bean - utility, helper classes
@Service     // Business logic layer - NO additional behavior (semantic only)
@Repository  // Data access layer - ADDS exception translation (DataAccessException)
@Controller  // Web layer - ADDS @RequestMapping handling + view resolution
@RestController  // @Controller + @ResponseBody on all methods

// @Repository special behavior:
// Spring wraps DAO exceptions into DataAccessException hierarchy
// Vendor-specific: SQLException, MongoException → Spring's DataAccessException
// This is done by PersistenceExceptionTranslationPostProcessor

// At architect level: These are purely semantic EXCEPT @Repository
// Use them for clarity and for component-scanning filters:
@ComponentScan(
    includeFilters = @ComponentScan.Filter(type = FilterType.ANNOTATION, classes = Service.class),
    excludeFilters = @ComponentScan.Filter(type = FilterType.ANNOTATION, classes = Controller.class)
)
```

---

## Bean Scopes & Lifecycle

### Q6: Explain all bean scopes in detail

```java
// SINGLETON (default) - One instance per ApplicationContext
@Scope("singleton")
@Service
public class SingletonService { }
// Created at context startup (eager), shared by all threads
// MUST be thread-safe if holding mutable state

// PROTOTYPE - New instance every time requested from container
@Scope("prototype")
@Component
public class PrototypeBean { }
// Created on every getBean() call or injection point
// Spring does NOT manage destruction (no @PreDestroy)
// WARNING: Injecting prototype into singleton → same instance always!

// FIX: Inject ObjectProvider or use @Lookup
@Service
public class SingletonService {
    @Autowired
    private ObjectProvider<PrototypeBean> prototypeBeanProvider;
    
    public void doSomething() {
        PrototypeBean fresh = prototypeBeanProvider.getObject(); // New instance each time
    }
    
    // Or use @Lookup (Spring creates subclass at runtime)
    @Lookup
    public PrototypeBean getPrototypeBean() { return null; } // Spring overrides this
}

// REQUEST - One instance per HTTP request
@Scope(value = WebApplicationContext.SCOPE_REQUEST, proxyMode = ScopedProxyMode.TARGET_CLASS)
@Component
public class RequestScopedBean {
    private String userId; // Safe: one instance per request
}
// Proxy mode needed when injecting into singleton (proxy delegates to current request's instance)

// SESSION - One instance per HTTP session
@Scope(value = WebApplicationContext.SCOPE_SESSION, proxyMode = ScopedProxyMode.TARGET_CLASS)
@Component
public class ShoppingCart {
    private List<Item> items = new ArrayList<>();
}

// APPLICATION - One instance per ServletContext (similar to singleton)
@Scope(WebApplicationContext.SCOPE_APPLICATION)

// WEBSOCKET - One instance per WebSocket session
@Scope("websocket")
```

### Q7: What happens with circular dependencies and how to solve them?

```java
// Circular dependency: A depends on B, B depends on A
@Service
public class ServiceA {
    @Autowired private ServiceB serviceB; // Needs B
}

@Service
public class ServiceB {
    @Autowired private ServiceA serviceA; // Needs A
}

// Spring resolves this for SINGLETON beans with field/setter injection:
// 1. Create A (not fully initialized)
// 2. Inject B into A → B needs A → Spring provides early reference to A
// 3. Complete A initialization
// This uses "three-level cache" (singletonFactories, earlySingletonObjects, singletonObjects)

// FAILS with constructor injection:
@Service
public class ServiceA {
    public ServiceA(ServiceB b) { } // Can't create A without B
}
@Service
public class ServiceB {
    public ServiceB(ServiceA a) { } // Can't create B without A
}
// BeanCurrentlyInCreationException!

// Spring Boot 2.6+ disallows circular dependencies by default
// spring.main.allow-circular-references=true (to allow, but DON'T)

// SOLUTIONS (design fixes):
// 1. Extract common logic into third class
// 2. Use @Lazy on one dependency
@Service
public class ServiceA {
    public ServiceA(@Lazy ServiceB b) { } // Proxy injected, resolved later
}

// 3. Use events for decoupling
@Service
public class ServiceA {
    @Autowired private ApplicationEventPublisher publisher;
    
    public void doWork() {
        publisher.publishEvent(new WorkDoneEvent(this));
    }
}

@Service
public class ServiceB {
    @EventListener
    public void onWorkDone(WorkDoneEvent event) {
        // React to A's action without direct dependency
    }
}

// 4. Redesign (BEST) - usually indicates design problem
```

### Q8: Explain `@PostConstruct`, `InitializingBean`, and init-method ordering

```java
@Service
public class CompleteLifecycleBean implements InitializingBean, DisposableBean, 
        BeanNameAware, ApplicationContextAware {
    
    // 1. Constructor
    public CompleteLifecycleBean() {
        log.info("1. Constructor called");
    }
    
    // 2. Aware interfaces (after property injection)
    @Override
    public void setBeanName(String name) {
        log.info("2. BeanNameAware: {}", name);
    }
    
    @Override
    public void setApplicationContext(ApplicationContext ctx) {
        log.info("3. ApplicationContextAware");
    }
    
    // 4. BeanPostProcessor.postProcessBeforeInitialization
    
    // 5. @PostConstruct (JSR-250)
    @PostConstruct
    public void postConstruct() {
        log.info("5. @PostConstruct");
    }
    
    // 6. InitializingBean.afterPropertiesSet()
    @Override
    public void afterPropertiesSet() {
        log.info("6. InitializingBean.afterPropertiesSet()");
    }
    
    // 7. Custom init method (from @Bean(initMethod="init"))
    public void init() {
        log.info("7. Custom init method");
    }
    
    // 8. BeanPostProcessor.postProcessAfterInitialization (AOP proxies here!)
    
    // ---- Bean is now READY ----
    
    // DESTRUCTION (reverse order):
    
    // 9. @PreDestroy
    @PreDestroy
    public void preDestroy() {
        log.info("9. @PreDestroy");
    }
    
    // 10. DisposableBean.destroy()
    @Override
    public void destroy() {
        log.info("10. DisposableBean.destroy()");
    }
    
    // 11. Custom destroy method
    public void cleanup() {
        log.info("11. Custom destroy method");
    }
}
```

---

## Configuration & Properties

### Q9: What is the complete property resolution order in Spring Boot?

```
Priority (highest to lowest):
1.  Command line arguments (--server.port=9090)
2.  SPRING_APPLICATION_JSON (inline JSON)
3.  ServletConfig/ServletContext parameters
4.  JNDI attributes (java:comp/env/)
5.  System properties (System.getProperties())
6.  OS environment variables
7.  RandomValuePropertySource (random.*)
8.  Profile-specific application-{profile}.properties OUTSIDE jar
9.  Profile-specific application-{profile}.properties INSIDE jar
10. Application properties OUTSIDE jar (application.properties/yml)
11. Application properties INSIDE jar
12. @PropertySource on @Configuration classes
13. Default properties (SpringApplication.setDefaultProperties())

Within same level:
  - .properties takes precedence over .yml
  - Profile-specific overrides non-profile
  - Config in config/ subdirectory overrides same-level
```

### Q10: Explain `@ConfigurationProperties` vs `@Value`

```java
// @Value - single property injection
@Component
public class SingleValueConfig {
    @Value("${app.name:DefaultApp}")     // With default
    private String appName;
    
    @Value("${app.timeout:5000}")        // Type conversion
    private int timeout;
    
    @Value("#{${app.map}}")              // SpEL expression
    private Map<String, String> map;
    
    @Value("${app.list}")                // Comma-separated → List
    private List<String> list;
    
    @Value("#{systemProperties['user.home']}")  // System property via SpEL
    private String userHome;
}

// @ConfigurationProperties - structured binding (PREFERRED for groups)
@ConfigurationProperties(prefix = "app.datasource")
@Validated  // Enables JSR-380 validation
public class DataSourceProperties {
    
    @NotEmpty
    private String url;
    
    private String username;
    
    @DurationUnit(ChronoUnit.SECONDS)
    private Duration connectionTimeout = Duration.ofSeconds(30); // Default
    
    @DataSizeUnit(DataUnit.MEGABYTES)
    private DataSize maxSize = DataSize.ofMegabytes(10);
    
    private final Pool pool = new Pool(); // Nested properties
    
    // Getters/setters required for mutable binding
    // Or use @ConstructorBinding for immutable
    
    public static class Pool {
        private int maxActive = 10;
        private int maxIdle = 5;
        // getters/setters
    }
}

// Immutable configuration (Java record, Spring Boot 3.x)
@ConfigurationProperties(prefix = "app.mail")
public record MailProperties(
    @NotEmpty String host,
    int port,
    @DefaultValue("false") boolean ssl,
    @DefaultValue("30s") Duration timeout
) { }

// Enable in main class or configuration
@EnableConfigurationProperties(DataSourceProperties.class)
// Or scan: @ConfigurationPropertiesScan
```

---

## Spring Boot Auto-Configuration

### Q11: How would you create a custom auto-configuration starter?

```java
// Step 1: Create the properties class
@ConfigurationProperties(prefix = "acme.service")
public class AcmeServiceProperties {
    private String endpoint = "http://localhost:8080";
    private Duration timeout = Duration.ofSeconds(5);
    private boolean enabled = true;
    // getters/setters
}

// Step 2: Create the auto-configuration
@AutoConfiguration
@ConditionalOnClass(AcmeClient.class)  // Only if AcmeClient on classpath
@ConditionalOnProperty(prefix = "acme.service", name = "enabled", havingValue = "true", matchIfMissing = true)
@EnableConfigurationProperties(AcmeServiceProperties.class)
public class AcmeServiceAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean  // User can override with their own bean
    public AcmeClient acmeClient(AcmeServiceProperties properties) {
        return new AcmeClient(properties.getEndpoint(), properties.getTimeout());
    }
    
    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnBean(AcmeClient.class)
    public AcmeService acmeService(AcmeClient client) {
        return new AcmeService(client);
    }
}

// Step 3: Register in META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
// Content: com.acme.autoconfigure.AcmeServiceAutoConfiguration

// Step 4: Optional - failure analysis
public class AcmeServiceFailureAnalyzer extends AbstractFailureAnalyzer<AcmeServiceException> {
    @Override
    protected FailureAnalysis analyze(Throwable rootFailure, AcmeServiceException cause) {
        return new FailureAnalysis(
            "Acme Service connection failed: " + cause.getMessage(),
            "Check acme.service.endpoint configuration and network connectivity",
            cause);
    }
}
```

### Q12: How does `@Conditional` work and what custom conditions can you create?

```java
// Create custom condition
public class OnProductionEnvironmentCondition implements Condition {
    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        String env = context.getEnvironment().getProperty("app.environment");
        return "production".equalsIgnoreCase(env);
    }
}

// Use it
@Configuration
@Conditional(OnProductionEnvironmentCondition.class)
public class ProductionOnlyConfig {
    // Only loaded in production
}

// Or create a composed annotation
@Target({ElementType.TYPE, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
@Conditional(OnProductionEnvironmentCondition.class)
public @interface ConditionalOnProduction { }

// Spring Boot's conditions are much more sophisticated:
// They implement ConfigurationCondition with ConfigurationPhase
// PARSE_CONFIGURATION → evaluated during config class parsing
// REGISTER_BEAN → evaluated during bean registration (later)
```

---

## REST API Development

### Q13: Complete REST controller with all best practices

```java
@RestController
@RequestMapping("/api/v1/users")
@Validated
@Tag(name = "Users", description = "User management API")
public class UserController {
    
    private final UserService userService;
    
    public UserController(UserService userService) {
        this.userService = userService;
    }
    
    @GetMapping
    @Operation(summary = "List all users with pagination")
    public ResponseEntity<Page<UserResponse>> listUsers(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") @Max(100) int size,
            @RequestParam(defaultValue = "createdAt,desc") String sort) {
        
        Pageable pageable = PageRequest.of(page, size, Sort.by(parseSortOrders(sort)));
        Page<UserResponse> users = userService.findAll(pageable);
        return ResponseEntity.ok(users);
    }
    
    @GetMapping("/{id}")
    @Operation(summary = "Get user by ID")
    public ResponseEntity<UserResponse> getUser(
            @PathVariable @UUID String id) {
        return userService.findById(id)
            .map(ResponseEntity::ok)
            .orElseThrow(() -> new ResourceNotFoundException("User", "id", id));
    }
    
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create a new user")
    public ResponseEntity<UserResponse> createUser(
            @Valid @RequestBody CreateUserRequest request) {
        UserResponse created = userService.create(request);
        URI location = ServletUriComponentsBuilder
            .fromCurrentRequest()
            .path("/{id}")
            .buildAndExpand(created.getId())
            .toUri();
        return ResponseEntity.created(location).body(created);
    }
    
    @PutMapping("/{id}")
    @Operation(summary = "Update user")
    public ResponseEntity<UserResponse> updateUser(
            @PathVariable String id,
            @Valid @RequestBody UpdateUserRequest request) {
        return ResponseEntity.ok(userService.update(id, request));
    }
    
    @PatchMapping("/{id}")
    @Operation(summary = "Partial update user")
    public ResponseEntity<UserResponse> patchUser(
            @PathVariable String id,
            @RequestBody Map<String, Object> updates) {
        return ResponseEntity.ok(userService.patch(id, updates));
    }
    
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "Delete user")
    public ResponseEntity<Void> deleteUser(@PathVariable String id) {
        userService.delete(id);
        return ResponseEntity.noContent().build();
    }
}
```

### Q14: How does content negotiation work in Spring Boot?

```java
// Spring uses Accept header to determine response format

@GetMapping(value = "/users/{id}", 
    produces = {MediaType.APPLICATION_JSON_VALUE, MediaType.APPLICATION_XML_VALUE})
public User getUser(@PathVariable Long id) {
    return userService.findById(id);
    // If Accept: application/json → Jackson serializes to JSON
    // If Accept: application/xml → JAXB or Jackson XML serializes to XML
}

// Content negotiation configuration
@Configuration
public class WebConfig implements WebMvcConfigurer {
    @Override
    public void configureContentNegotiation(ContentNegotiationConfigurer configurer) {
        configurer
            .favorParameter(true)          // ?format=json
            .parameterName("format")
            .ignoreAcceptHeader(false)      // Still respect Accept header
            .defaultContentType(MediaType.APPLICATION_JSON)
            .mediaType("json", MediaType.APPLICATION_JSON)
            .mediaType("xml", MediaType.APPLICATION_XML)
            .mediaType("csv", new MediaType("text", "csv"));
    }
}

// Custom HttpMessageConverter for CSV
@Component
public class CsvMessageConverter extends AbstractHttpMessageConverter<List<?>> {
    public CsvMessageConverter() {
        super(new MediaType("text", "csv"));
    }
    
    @Override
    protected boolean supports(Class<?> clazz) {
        return List.class.isAssignableFrom(clazz);
    }
    
    @Override
    protected void writeInternal(List<?> list, HttpOutputMessage output) throws IOException {
        // Write CSV format
    }
}
```

### Q15: Explain `@RequestBody` processing and `HttpMessageConverter`

```java
// HttpMessageConverter chain:
// 1. Spring checks Content-Type of request
// 2. Iterates through registered converters
// 3. First converter that canRead(targetType, contentType) wins
// 4. Converter deserializes body → Java object

// Default converters (ordered):
// ByteArrayHttpMessageConverter (application/octet-stream)
// StringHttpMessageConverter (text/plain)
// ResourceHttpMessageConverter (all)
// SourceHttpMessageConverter (application/xml)
// FormHttpMessageConverter (application/x-www-form-urlencoded, multipart/form-data)
// MappingJackson2HttpMessageConverter (application/json) ← Most common

// Customize Jackson for @RequestBody/@ResponseBody
@Configuration
public class JacksonConfig {
    @Bean
    public ObjectMapper objectMapper() {
        return JsonMapper.builder()
            .addModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
            .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
            .serializationInclusion(JsonInclude.Include.NON_NULL)
            .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .build();
    }
    
    // Or customize via application.yml:
    // spring.jackson.serialization.write-dates-as-timestamps: false
    // spring.jackson.default-property-inclusion: non-null
    // spring.jackson.property-naming-strategy: SNAKE_CASE
}
```

---

## Data Access

### Q16: Explain Spring Data JPA repository hierarchy

```java
// Repository hierarchy:
Repository<T, ID>                    // Marker interface
  └── CrudRepository<T, ID>         // CRUD operations (save, findById, delete, etc.)
      └── ListCrudRepository<T, ID> // Returns List instead of Iterable
      └── PagingAndSortingRepository<T, ID>  // + Pageable/Sort support
          └── JpaRepository<T, ID>           // + JPA specific (flush, batch, etc.)

// Custom query methods (derived queries)
public interface UserRepository extends JpaRepository<User, Long> {
    
    // Derived query: method name → JPQL
    List<User> findByLastNameAndFirstName(String lastName, String firstName);
    // → SELECT u FROM User u WHERE u.lastName = ?1 AND u.firstName = ?2
    
    Optional<User> findByEmail(String email);
    
    List<User> findByAgeBetween(int min, int max);
    
    List<User> findByLastNameOrderByFirstNameAsc(String lastName);
    
    @Query("SELECT u FROM User u WHERE u.email LIKE %:domain")
    List<User> findByEmailDomain(@Param("domain") String domain);
    
    @Query(value = "SELECT * FROM users WHERE created_at > :since", nativeQuery = true)
    List<User> findRecentUsers(@Param("since") LocalDateTime since);
    
    @Modifying
    @Query("UPDATE User u SET u.active = false WHERE u.lastLogin < :cutoff")
    int deactivateInactiveUsers(@Param("cutoff") LocalDateTime cutoff);
    
    // Projections
    <T> List<T> findByLastName(String lastName, Class<T> type);
    
    // Specifications (dynamic queries)
    List<User> findAll(Specification<User> spec);
}
```

### Q17: `@Transactional` deep dive - propagation, isolation, rollback

```java
// PROPAGATION TYPES
@Transactional(propagation = Propagation.REQUIRED)  // DEFAULT
// Join existing TX or create new one

@Transactional(propagation = Propagation.REQUIRES_NEW)
// ALWAYS create new TX (suspend existing)
// Use case: Audit logging that must persist even if main TX fails

@Transactional(propagation = Propagation.NESTED)
// Create savepoint within existing TX
// Can rollback to savepoint without rolling back outer TX
// Use case: Batch processing where individual items can fail

@Transactional(propagation = Propagation.SUPPORTS)
// Run in TX if one exists, otherwise non-transactional

@Transactional(propagation = Propagation.NOT_SUPPORTED)
// Suspend existing TX, run non-transactional
// Use case: Read-only operations that don't need TX overhead

@Transactional(propagation = Propagation.MANDATORY)
// MUST run within existing TX, throw exception otherwise

@Transactional(propagation = Propagation.NEVER)
// MUST NOT run within TX, throw exception if TX exists

// ROLLBACK RULES
@Transactional(
    rollbackFor = {BusinessException.class},      // Rollback on these checked exceptions
    noRollbackFor = {NonCriticalException.class}  // Don't rollback on these
)
// Default: Rollback on RuntimeException and Error, NOT on checked exceptions

// IMPORTANT: @Transactional pitfalls
// 1. Only works on PUBLIC methods (proxy-based AOP)
// 2. Self-invocation doesn't go through proxy:
@Service
public class UserService {
    @Transactional
    public void methodA() {
        this.methodB(); // NOT transactional! Direct call bypasses proxy!
    }
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void methodB() { } // This annotation is IGNORED when called from methodA!
}

// Fix: Inject self or use ApplicationContext
@Service
public class UserService {
    @Autowired @Lazy private UserService self; // Inject proxy
    
    @Transactional
    public void methodA() {
        self.methodB(); // Goes through proxy → REQUIRES_NEW works
    }
}
```

### Q18: How does Spring Data create repository implementations at runtime?

```java
// Spring Data creates a PROXY at runtime for your repository interface

// Behind the scenes:
// 1. RepositoryFactorySupport scans for Repository interfaces
// 2. For each interface, creates a JdkDynamicProxy (or CGLIB proxy)
// 3. Proxy delegates to SimpleJpaRepository for standard methods
// 4. For custom query methods:
//    a. Derives query from method name (QueryCreationListener)
//    b. Or uses @Query annotation
//    c. Or uses named queries

// The proxy invocation handler:
public class QueryExecutorMethodInterceptor implements MethodInterceptor {
    @Override
    public Object invoke(MethodInvocation invocation) {
        // 1. Check if it's a base method (save, find, delete) → delegate to SimpleJpaRepository
        // 2. Check if it's a custom method → execute derived/annotated query
        // 3. Check if it's a custom implementation method → delegate to Impl class
    }
}

// Custom implementation
public interface UserRepositoryCustom {
    List<User> findByComplexCriteria(SearchCriteria criteria);
}

public class UserRepositoryImpl implements UserRepositoryCustom {
    @PersistenceContext
    private EntityManager em;
    
    @Override
    public List<User> findByComplexCriteria(SearchCriteria criteria) {
        CriteriaBuilder cb = em.getCriteriaBuilder();
        // ... build dynamic query
    }
}

// Spring Data finds UserRepositoryImpl by naming convention (interface name + "Impl")
public interface UserRepository extends JpaRepository<User, Long>, UserRepositoryCustom {
}
```

---

## Exception Handling

### Q19: Complete exception handling strategy

```java
// GLOBAL EXCEPTION HANDLER
@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class GlobalExceptionHandler {
    
    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);
    
    // Business exceptions (4xx)
    @ExceptionHandler(ResourceNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ErrorResponse handleNotFound(ResourceNotFoundException ex, WebRequest request) {
        return ErrorResponse.builder()
            .timestamp(Instant.now())
            .status(404)
            .error("Not Found")
            .message(ex.getMessage())
            .path(extractPath(request))
            .build();
    }
    
    // Validation errors (400)
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ErrorResponse handleValidation(MethodArgumentNotValidException ex) {
        Map<String, String> errors = ex.getBindingResult().getFieldErrors().stream()
            .collect(Collectors.toMap(
                FieldError::getField,
                error -> error.getDefaultMessage() != null ? error.getDefaultMessage() : "Invalid",
                (first, second) -> first));
        
        return ErrorResponse.builder()
            .status(400)
            .error("Validation Failed")
            .message("Request validation failed")
            .details(errors)
            .build();
    }
    
    // Constraint violation (400)
    @ExceptionHandler(ConstraintViolationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ErrorResponse handleConstraintViolation(ConstraintViolationException ex) {
        Map<String, String> errors = ex.getConstraintViolations().stream()
            .collect(Collectors.toMap(
                v -> v.getPropertyPath().toString(),
                ConstraintViolation::getMessage));
        return ErrorResponse.builder()
            .status(400)
            .error("Constraint Violation")
            .details(errors)
            .build();
    }
    
    // Optimistic lock (409)
    @ExceptionHandler(OptimisticLockingFailureException.class)
    @ResponseStatus(HttpStatus.CONFLICT)
    public ErrorResponse handleConflict(OptimisticLockingFailureException ex) {
        return ErrorResponse.builder()
            .status(409)
            .error("Conflict")
            .message("Resource was modified by another request. Please retry.")
            .build();
    }
    
    // Rate limiting (429)
    @ExceptionHandler(RateLimitExceededException.class)
    public ResponseEntity<ErrorResponse> handleRateLimit(RateLimitExceededException ex) {
        return ResponseEntity.status(429)
            .header("Retry-After", String.valueOf(ex.getRetryAfterSeconds()))
            .body(ErrorResponse.builder()
                .status(429)
                .error("Too Many Requests")
                .message("Rate limit exceeded")
                .build());
    }
    
    // Catch-all for unexpected errors (500)
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ErrorResponse handleAll(Exception ex, WebRequest request) {
        log.error("Unhandled exception for request: {}", extractPath(request), ex);
        return ErrorResponse.builder()
            .status(500)
            .error("Internal Server Error")
            .message("An unexpected error occurred") // Don't expose details!
            .traceId(MDC.get("traceId"))
            .build();
    }
}
```

---

## Validation

### Q20: All validation annotations and custom validators

```java
// Standard JSR-380 annotations
public class CreateUserRequest {
    @NotNull(message = "Name is required")
    @Size(min = 2, max = 100, message = "Name must be between 2 and 100 characters")
    private String name;
    
    @NotBlank @Email(message = "Invalid email format")
    private String email;
    
    @NotNull @Min(18) @Max(150)
    private Integer age;
    
    @Pattern(regexp = "^\\+?[1-9]\\d{1,14}$", message = "Invalid phone number")
    private String phone;
    
    @Past(message = "Birth date must be in the past")
    private LocalDate birthDate;
    
    @Future(message = "Expiry must be in the future")
    private LocalDate expiryDate;
    
    @Positive private BigDecimal amount;
    @PositiveOrZero private Integer quantity;
    
    @NotEmpty
    @Size(max = 10, message = "Maximum 10 tags")
    private List<@NotBlank String> tags; // Validates each element!
    
    @Valid // Cascade validation to nested object
    @NotNull
    private Address address;
}

// Custom validator
@Target({FIELD, PARAMETER})
@Retention(RUNTIME)
@Constraint(validatedBy = UniqueEmailValidator.class)
public @interface UniqueEmail {
    String message() default "Email already exists";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class UniqueEmailValidator implements ConstraintValidator<UniqueEmail, String> {
    @Autowired private UserRepository userRepo;
    
    @Override
    public boolean isValid(String email, ConstraintValidatorContext context) {
        if (email == null) return true; // @NotNull handles null check
        return !userRepo.existsByEmail(email);
    }
}

// Cross-field validation
@Target(TYPE)
@Retention(RUNTIME)
@Constraint(validatedBy = PasswordMatchValidator.class)
public @interface PasswordMatch {
    String message() default "Passwords do not match";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

@PasswordMatch
public class RegistrationRequest {
    private String password;
    private String confirmPassword;
}

// Validation groups (different rules for create vs update)
public interface OnCreate {}
public interface OnUpdate {}

public class UserRequest {
    @Null(groups = OnCreate.class) // ID must be null on create
    @NotNull(groups = OnUpdate.class) // ID required on update
    private Long id;
    
    @NotBlank(groups = {OnCreate.class, OnUpdate.class})
    private String name;
}

@PostMapping
public User create(@Validated(OnCreate.class) @RequestBody UserRequest request) { }

@PutMapping("/{id}")
public User update(@Validated(OnUpdate.class) @RequestBody UserRequest request) { }
```

---

## Profiles & Environments

### Q21: Advanced profile usage patterns

```java
// Multiple active profiles
// spring.profiles.active=production,aws,metrics

// Profile groups (Spring Boot 2.4+)
// application.yml:
spring:
  profiles:
    group:
      production:
        - production-db
        - production-cache
        - production-monitoring
      development:
        - dev-db
        - dev-mock

// Profile-specific beans
@Configuration
public class MessagingConfig {
    
    @Bean
    @Profile("production")
    public MessageBroker kafkaBroker() {
        return new KafkaMessageBroker();
    }
    
    @Bean
    @Profile("development")
    public MessageBroker inMemoryBroker() {
        return new InMemoryMessageBroker();
    }
    
    @Bean
    @Profile("!production") // NOT production (any other profile)
    public DataSeeder dataSeeder() {
        return new DataSeeder();
    }
}

// Programmatic profile activation
@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication app = new SpringApplication(Application.class);
        
        if (System.getenv("KUBERNETES_SERVICE_HOST") != null) {
            app.setAdditionalProfiles("kubernetes");
        }
        
        app.run(args);
    }
}
```

---

## Logging & Monitoring

### Q22: Production logging configuration

```yaml
# application-production.yml
logging:
  level:
    root: WARN
    com.example: INFO
    org.springframework.web: WARN
    org.hibernate.SQL: WARN
    org.apache.kafka: WARN
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] [%X{traceId}] %-5level %logger{36} - %msg%n"
  file:
    name: /var/log/app/application.log
    max-size: 100MB
    max-history: 30
    total-size-cap: 3GB
```

```java
// Structured logging with MDC (Mapped Diagnostic Context)
@Component
public class RequestLoggingFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain) throws Exception {
        
        String traceId = request.getHeader("X-Trace-Id");
        if (traceId == null) traceId = UUID.randomUUID().toString();
        
        MDC.put("traceId", traceId);
        MDC.put("userId", extractUserId(request));
        MDC.put("requestId", UUID.randomUUID().toString());
        
        long start = System.currentTimeMillis();
        try {
            chain.doFilter(request, response);
        } finally {
            long duration = System.currentTimeMillis() - start;
            log.info("HTTP {} {} {} {}ms", 
                request.getMethod(), request.getRequestURI(), 
                response.getStatus(), duration);
            MDC.clear(); // CRITICAL: clean up
        }
    }
}

// Micrometer metrics
@Component
public class BusinessMetrics {
    private final Counter orderCounter;
    private final Timer orderProcessingTimer;
    private final Gauge activeOrdersGauge;
    
    public BusinessMetrics(MeterRegistry registry) {
        this.orderCounter = Counter.builder("orders.created")
            .description("Total orders created")
            .tag("channel", "web")
            .register(registry);
        
        this.orderProcessingTimer = Timer.builder("orders.processing.time")
            .description("Order processing duration")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(registry);
        
        this.activeOrdersGauge = Gauge.builder("orders.active", 
                activeOrdersRef, AtomicInteger::get)
            .register(registry);
    }
    
    public void recordOrderCreated() {
        orderCounter.increment();
    }
    
    public Timer.Sample startTimer() {
        return Timer.start();
    }
    
    public void recordProcessingTime(Timer.Sample sample) {
        sample.stop(orderProcessingTimer);
    }
}
```
