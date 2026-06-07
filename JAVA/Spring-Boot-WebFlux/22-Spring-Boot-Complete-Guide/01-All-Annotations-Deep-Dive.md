# Spring Boot Annotations - Complete Deep Dive

## Table of Contents
1. [Core Spring Annotations](#core-spring-annotations)
2. [Spring Boot Specific Annotations](#spring-boot-specific-annotations)
3. [Web Layer Annotations](#web-layer-annotations)
4. [Data/Persistence Annotations](#datapersistence-annotations)
5. [Security Annotations](#security-annotations)
6. [Testing Annotations](#testing-annotations)
7. [Conditional Annotations](#conditional-annotations)
8. [AOP Annotations](#aop-annotations)
9. [Scheduling & Async Annotations](#scheduling--async-annotations)
10. [Configuration Annotations](#configuration-annotations)

---

## Core Spring Annotations

### @Component
```java
@Component
public class EmailService {
    // Generic Spring-managed bean
    // Detected by component scanning
}
```
**How it works internally:**
- During `@ComponentScan`, Spring scans classpath for classes annotated with `@Component`
- Creates a `BeanDefinition` for each discovered class
- Registers in `BeanDefinitionRegistry`
- Default scope: Singleton

### @Service
```java
@Service
public class OrderService {
    // Semantically indicates business logic layer
    // Functionally identical to @Component
}
```
**Key Points:**
- Meta-annotated with `@Component` (it IS a @Component)
- Provides semantic clarity - "this is a service layer bean"
- Spring may add special behavior in future versions for @Service-annotated classes
- Exception translation is NOT automatic (that's @Repository)

### @Repository
```java
@Repository
public class UserRepository {
    // Indicates data access layer
    // Provides automatic exception translation
}
```
**Special Behavior:**
- `PersistenceExceptionTranslationPostProcessor` catches platform-specific exceptions
- Translates them to Spring's `DataAccessException` hierarchy
- Example: `SQLException` → `DataAccessException`
- This is the ONLY stereotype annotation with actual extra behavior

### @Controller
```java
@Controller
public class HomeController {
    @GetMapping("/")
    public String home(Model model) {
        model.addAttribute("message", "Hello");
        return "home"; // Returns VIEW name
    }
}
```

### @RestController
```java
@RestController // = @Controller + @ResponseBody
public class ApiController {
    @GetMapping("/api/users")
    public List<User> getUsers() {
        return userService.findAll(); // Returns JSON directly
    }
}
```
**Difference from @Controller:**
- `@Controller` returns view names (for Thymeleaf/JSP)
- `@RestController` returns response body directly (JSON/XML)
- `@RestController` = `@Controller` + `@ResponseBody` on every method

### @Configuration
```java
@Configuration
public class AppConfig {
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
    
    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }
}
```
**How it works internally:**
- Spring creates a CGLIB proxy of the @Configuration class
- This ensures @Bean method calls within the class return the SAME singleton instance
- Without @Configuration (using @Component), each @Bean method call creates a NEW instance

```java
@Configuration
public class AppConfig {
    @Bean
    public ServiceA serviceA() {
        return new ServiceA(commonDependency()); // Returns SAME instance
    }
    
    @Bean
    public ServiceB serviceB() {
        return new ServiceB(commonDependency()); // Returns SAME instance
    }
    
    @Bean
    public CommonDependency commonDependency() {
        return new CommonDependency(); // Called once due to CGLIB proxy
    }
}
```

### @Bean
```java
@Bean(name = "customDataSource")
@Primary
public DataSource dataSource() {
    HikariDataSource ds = new HikariDataSource();
    ds.setJdbcUrl("jdbc:mysql://localhost:3306/mydb");
    ds.setUsername("root");
    return ds;
}

@Bean(initMethod = "init", destroyMethod = "cleanup")
public CacheManager cacheManager() {
    return new ConcurrentMapCacheManager("users", "orders");
}
```

### @Autowired
```java
// Constructor Injection (RECOMMENDED)
@Service
public class OrderService {
    private final UserRepository userRepository;
    private final PaymentService paymentService;
    
    // @Autowired is optional for single constructor (Spring 4.3+)
    public OrderService(UserRepository userRepository, PaymentService paymentService) {
        this.userRepository = userRepository;
        this.paymentService = paymentService;
    }
}

// Field Injection (NOT recommended - harder to test)
@Service
public class OrderService {
    @Autowired
    private UserRepository userRepository;
}

// Setter Injection
@Service
public class OrderService {
    private UserRepository userRepository;
    
    @Autowired
    public void setUserRepository(UserRepository userRepository) {
        this.userRepository = userRepository;
    }
}
```

**Why Constructor Injection is preferred:**
1. Immutability - fields can be `final`
2. Testability - easy to pass mocks in unit tests
3. Required dependencies are obvious
4. No reflection hacks needed
5. Fails fast if dependency is missing

### @Qualifier
```java
public interface NotificationService { void send(String msg); }

@Service("emailNotification")
public class EmailNotificationService implements NotificationService { ... }

@Service("smsNotification")  
public class SmsNotificationService implements NotificationService { ... }

@Service
public class OrderService {
    public OrderService(@Qualifier("emailNotification") NotificationService service) {
        // Resolves ambiguity when multiple beans of same type exist
    }
}
```

### @Primary
```java
@Primary
@Bean
public DataSource primaryDataSource() {
    // This will be injected by default when type is ambiguous
    return new HikariDataSource(primaryConfig());
}

@Bean
public DataSource secondaryDataSource() {
    return new HikariDataSource(secondaryConfig());
}
```

### @Scope
```java
@Component
@Scope("prototype") // New instance every time it's injected
public class ShoppingCart { }

@Component
@Scope(value = WebApplicationContext.SCOPE_REQUEST, proxyMode = ScopedProxyMode.TARGET_CLASS)
public class RequestScopedBean { }

// Available scopes:
// singleton (default) - one instance per Spring container
// prototype - new instance per injection point
// request - one per HTTP request
// session - one per HTTP session
// application - one per ServletContext
// websocket - one per WebSocket session
```

### @Lazy
```java
@Component
@Lazy // Bean created only when first accessed, not at startup
public class HeavyResourceLoader {
    public HeavyResourceLoader() {
        // This constructor runs only when bean is first requested
        loadHeavyResources();
    }
}

// Lazy injection
@Service
public class MyService {
    @Lazy
    @Autowired
    private HeavyResourceLoader loader; // Proxy injected, real bean created on first use
}
```

### @Value
```java
@Component
public class AppProperties {
    @Value("${app.name}")
    private String appName;
    
    @Value("${app.timeout:5000}") // With default value
    private int timeout;
    
    @Value("#{systemProperties['java.home']}")  // SpEL expression
    private String javaHome;
    
    @Value("${app.servers}") // Comma-separated to list
    private List<String> servers;
    
    @Value("#{${app.map}}") // SpEL to parse map
    private Map<String, String> configMap;
}
```

---

## Spring Boot Specific Annotations

### @SpringBootApplication
```java
@SpringBootApplication // = @Configuration + @EnableAutoConfiguration + @ComponentScan
public class MyApplication {
    public static void main(String[] args) {
        SpringApplication.run(MyApplication.class, args);
    }
}

// Equivalent to:
@Configuration
@EnableAutoConfiguration
@ComponentScan(basePackages = "com.example")
public class MyApplication { }
```

### @EnableAutoConfiguration
```java
@EnableAutoConfiguration(exclude = {DataSourceAutoConfiguration.class})
public class MyApplication { }
```
**How Auto-Configuration Works:**
1. Spring Boot reads `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
2. Each auto-config class has `@Conditional*` annotations
3. If conditions are met (class on classpath, no existing bean, etc.), config activates
4. Example: If `HikariCP` is on classpath AND no `DataSource` bean exists → auto-configure HikariCP

### @ConfigurationProperties
```java
@ConfigurationProperties(prefix = "app.mail")
@Validated
public class MailProperties {
    @NotEmpty
    private String host;
    private int port = 587;
    private String username;
    private String password;
    private Map<String, String> headers = new HashMap<>();
    private Security security = new Security();
    
    // Getters and setters required
    
    public static class Security {
        private boolean enabled;
        private String protocol = "TLS";
        // getters/setters
    }
}

// In application.yml:
// app:
//   mail:
//     host: smtp.gmail.com
//     port: 587
//     security:
//       enabled: true
//       protocol: TLS

// Enable it:
@Configuration
@EnableConfigurationProperties(MailProperties.class)
public class MailConfig { }
```

### @ConditionalOnProperty
```java
@Configuration
@ConditionalOnProperty(name = "feature.cache.enabled", havingValue = "true", matchIfMissing = false)
public class CacheConfiguration {
    @Bean
    public CacheManager cacheManager() {
        return new RedisCacheManager(...);
    }
}
```

### @ConditionalOnClass / @ConditionalOnMissingClass
```java
@Configuration
@ConditionalOnClass(name = "com.fasterxml.jackson.databind.ObjectMapper")
public class JacksonAutoConfiguration {
    // Only activates if Jackson is on the classpath
}
```

### @ConditionalOnBean / @ConditionalOnMissingBean
```java
@Configuration
public class DefaultConfig {
    @Bean
    @ConditionalOnMissingBean(DataSource.class)
    public DataSource defaultDataSource() {
        // Only creates if user hasn't defined their own DataSource
        return new EmbeddedDatabaseBuilder().build();
    }
}
```

### @EnableScheduling
```java
@Configuration
@EnableScheduling
public class SchedulingConfig { }

@Component
public class ScheduledTasks {
    @Scheduled(fixedRate = 5000) // Every 5 seconds
    public void reportCurrentTime() {
        log.info("Time: {}", LocalDateTime.now());
    }
    
    @Scheduled(cron = "0 0 2 * * ?") // Every day at 2 AM
    public void dailyCleanup() {
        cleanupService.run();
    }
    
    @Scheduled(fixedDelay = 10000, initialDelay = 5000)
    public void processQueue() {
        // Runs 10s after previous execution COMPLETES, starts 5s after app startup
    }
}
```

### @EnableAsync
```java
@Configuration
@EnableAsync
public class AsyncConfig implements AsyncConfigurer {
    @Override
    public Executor getAsyncExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(10);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-");
        executor.initialize();
        return executor;
    }
    
    @Override
    public AsyncUncaughtExceptionHandler getAsyncUncaughtExceptionHandler() {
        return new CustomAsyncExceptionHandler();
    }
}

@Service
public class EmailService {
    @Async
    public CompletableFuture<String> sendEmailAsync(String to, String body) {
        // Runs in separate thread from the async thread pool
        emailClient.send(to, body);
        return CompletableFuture.completedFuture("Sent");
    }
}
```

### @Profile
```java
@Configuration
@Profile("production")
public class ProductionConfig {
    @Bean
    public DataSource dataSource() {
        return new HikariDataSource(productionConfig());
    }
}

@Configuration
@Profile("!production") // NOT production
public class DevConfig {
    @Bean
    public DataSource dataSource() {
        return new EmbeddedDatabaseBuilder().setType(H2).build();
    }
}

@Component
@Profile({"dev", "test"}) // Active in dev OR test
public class MockPaymentGateway implements PaymentGateway { }
```

---

## Web Layer Annotations

### @RequestMapping & HTTP Method Annotations
```java
@RestController
@RequestMapping("/api/v1/users")
public class UserController {
    
    @GetMapping  // GET /api/v1/users
    public List<User> getAllUsers() { ... }
    
    @GetMapping("/{id}")  // GET /api/v1/users/123
    public User getUser(@PathVariable Long id) { ... }
    
    @GetMapping("/search")  // GET /api/v1/users/search?name=John&age=25
    public List<User> search(
        @RequestParam String name,
        @RequestParam(required = false, defaultValue = "0") int age) { ... }
    
    @PostMapping  // POST /api/v1/users
    @ResponseStatus(HttpStatus.CREATED)
    public User createUser(@Valid @RequestBody CreateUserRequest request) { ... }
    
    @PutMapping("/{id}")  // PUT /api/v1/users/123
    public User updateUser(@PathVariable Long id, @Valid @RequestBody UpdateUserRequest request) { ... }
    
    @PatchMapping("/{id}")  // PATCH /api/v1/users/123
    public User partialUpdate(@PathVariable Long id, @RequestBody Map<String, Object> updates) { ... }
    
    @DeleteMapping("/{id}")  // DELETE /api/v1/users/123
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteUser(@PathVariable Long id) { ... }
}
```

### @RequestBody & @ResponseBody
```java
@PostMapping("/orders")
public ResponseEntity<Order> createOrder(
    @Valid @RequestBody OrderRequest request  // Deserializes JSON → Java object
) {
    Order order = orderService.create(request);
    return ResponseEntity
        .created(URI.create("/orders/" + order.getId()))
        .body(order); // Serializes Java object → JSON
}
```
**How it works:**
- `HttpMessageConverter` handles serialization/deserialization
- `MappingJackson2HttpMessageConverter` for JSON (if Jackson on classpath)
- Content-Type header determines which converter to use
- `@ResponseBody` is implicit in `@RestController`

### @PathVariable
```java
@GetMapping("/users/{userId}/orders/{orderId}")
public Order getOrder(
    @PathVariable Long userId,
    @PathVariable("orderId") Long id  // Different variable name
) { ... }

@GetMapping("/files/{*path}") // Captures rest of path (Spring 5.3+)
public Resource getFile(@PathVariable String path) { ... }
```

### @RequestParam
```java
@GetMapping("/products")
public Page<Product> getProducts(
    @RequestParam(defaultValue = "0") int page,
    @RequestParam(defaultValue = "20") int size,
    @RequestParam(required = false) String category,
    @RequestParam List<String> tags  // ?tags=java&tags=spring
) { ... }
```

### @RequestHeader & @CookieValue
```java
@GetMapping("/info")
public String getInfo(
    @RequestHeader("Authorization") String authToken,
    @RequestHeader(value = "X-Request-Id", required = false) String requestId,
    @CookieValue(name = "sessionId", defaultValue = "none") String sessionId
) { ... }
```

### @ModelAttribute
```java
@Controller
public class UserFormController {
    
    @ModelAttribute("departments") // Runs before EVERY handler method in this controller
    public List<String> populateDepartments() {
        return List.of("Engineering", "Marketing", "Sales");
    }
    
    @PostMapping("/register")
    public String register(@ModelAttribute("user") @Valid UserForm form, BindingResult result) {
        if (result.hasErrors()) return "register";
        userService.register(form);
        return "redirect:/success";
    }
}
```

### @ExceptionHandler & @ControllerAdvice
```java
@RestControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(ResourceNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ErrorResponse handleNotFound(ResourceNotFoundException ex) {
        return new ErrorResponse("NOT_FOUND", ex.getMessage());
    }
    
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ErrorResponse handleValidation(MethodArgumentNotValidException ex) {
        Map<String, String> errors = ex.getBindingResult().getFieldErrors().stream()
            .collect(Collectors.toMap(
                FieldError::getField,
                FieldError::getDefaultMessage
            ));
        return new ErrorResponse("VALIDATION_FAILED", errors);
    }
    
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ErrorResponse handleGeneral(Exception ex) {
        log.error("Unhandled exception", ex);
        return new ErrorResponse("INTERNAL_ERROR", "An unexpected error occurred");
    }
}
```

### @CrossOrigin
```java
@RestController
@CrossOrigin(origins = "http://localhost:3000", maxAge = 3600)
public class ApiController { }

// Or global configuration:
@Configuration
public class WebConfig implements WebMvcConfigurer {
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
            .allowedOrigins("https://example.com")
            .allowedMethods("GET", "POST", "PUT", "DELETE")
            .allowedHeaders("*")
            .allowCredentials(true)
            .maxAge(3600);
    }
}
```

---

## Data/Persistence Annotations

### @Entity & JPA Annotations
```java
@Entity
@Table(name = "users", indexes = {
    @Index(name = "idx_email", columnList = "email", unique = true),
    @Index(name = "idx_status_created", columnList = "status,created_at")
})
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(name = "email", nullable = false, unique = true, length = 255)
    private String email;
    
    @Column(name = "full_name", nullable = false)
    private String fullName;
    
    @Enumerated(EnumType.STRING)
    @Column(name = "status")
    private UserStatus status;
    
    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;
    
    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
    
    @Version // Optimistic locking
    private Long version;
    
    @OneToMany(mappedBy = "user", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Order> orders = new ArrayList<>();
    
    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(
        name = "user_roles",
        joinColumns = @JoinColumn(name = "user_id"),
        inverseJoinColumns = @JoinColumn(name = "role_id")
    )
    private Set<Role> roles = new HashSet<>();
    
    @Embedded
    private Address address;
}

@Embeddable
public class Address {
    private String street;
    private String city;
    private String zipCode;
    private String country;
}
```

### @Transactional (Detailed in separate file)
```java
@Service
public class TransferService {
    @Transactional(
        propagation = Propagation.REQUIRED,
        isolation = Isolation.READ_COMMITTED,
        timeout = 30,
        rollbackFor = {BusinessException.class},
        noRollbackFor = {NotificationException.class}
    )
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        accountRepository.debit(fromId, amount);
        accountRepository.credit(toId, amount);
        auditService.log(fromId, toId, amount);
    }
}
```

### @Query (Spring Data JPA)
```java
public interface UserRepository extends JpaRepository<User, Long> {
    
    // Derived query methods
    List<User> findByStatusAndCreatedAtAfter(UserStatus status, LocalDateTime after);
    Optional<User> findByEmailIgnoreCase(String email);
    boolean existsByEmail(String email);
    
    // JPQL
    @Query("SELECT u FROM User u WHERE u.email LIKE %:domain")
    List<User> findByEmailDomain(@Param("domain") String domain);
    
    // Native SQL
    @Query(value = "SELECT * FROM users WHERE created_at > :date", nativeQuery = true)
    List<User> findRecentUsers(@Param("date") LocalDateTime date);
    
    // Modifying queries
    @Modifying
    @Query("UPDATE User u SET u.status = :status WHERE u.lastLoginAt < :date")
    int deactivateInactiveUsers(@Param("status") UserStatus status, @Param("date") LocalDateTime date);
    
    // Projections
    @Query("SELECT u.email as email, u.fullName as name FROM User u WHERE u.status = :status")
    List<UserSummary> findSummaryByStatus(@Param("status") UserStatus status);
}
```

### @EnableJpaRepositories
```java
@Configuration
@EnableJpaRepositories(
    basePackages = "com.example.repository",
    entityManagerFactoryRef = "primaryEntityManagerFactory",
    transactionManagerRef = "primaryTransactionManager"
)
public class PrimaryJpaConfig { }
```

---

## Security Annotations

### @EnableWebSecurity
```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity(prePostEnabled = true)
public class SecurityConfig {
    
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated())
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

### @PreAuthorize / @PostAuthorize
```java
@Service
public class DocumentService {
    
    @PreAuthorize("hasRole('ADMIN') or #userId == authentication.principal.id")
    public Document getDocument(Long userId, Long docId) { ... }
    
    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")
    public void deleteDocument(Long docId) { ... }
    
    @PostAuthorize("returnObject.owner == authentication.name")
    public Document findById(Long id) { ... }
    
    @PreAuthorize("@securityService.canAccess(authentication, #resourceId)")
    public Resource accessResource(Long resourceId) { ... }
}
```

### @Secured
```java
@Secured({"ROLE_ADMIN", "ROLE_MANAGER"})
public void performAdminTask() { ... }
```

---

## Testing Annotations

### @SpringBootTest
```java
@SpringBootTest(
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = {"spring.datasource.url=jdbc:h2:mem:test"}
)
class OrderServiceIntegrationTest {
    @Autowired
    private TestRestTemplate restTemplate;
    
    @LocalServerPort
    private int port;
    
    @Test
    void shouldCreateOrder() {
        ResponseEntity<Order> response = restTemplate.postForEntity(
            "/api/orders", new OrderRequest(...), Order.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }
}
```

### @WebMvcTest
```java
@WebMvcTest(UserController.class) // Only loads web layer for this controller
class UserControllerTest {
    @Autowired
    private MockMvc mockMvc;
    
    @MockBean
    private UserService userService;
    
    @Test
    void shouldReturnUser() throws Exception {
        when(userService.findById(1L)).thenReturn(new User("John"));
        
        mockMvc.perform(get("/api/users/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name").value("John"));
    }
}
```

### @DataJpaTest
```java
@DataJpaTest // Configures in-memory DB, scans @Entity classes, configures Spring Data JPA repos
class UserRepositoryTest {
    @Autowired
    private TestEntityManager entityManager;
    
    @Autowired
    private UserRepository userRepository;
    
    @Test
    void shouldFindByEmail() {
        entityManager.persist(new User("test@example.com", "Test User"));
        Optional<User> found = userRepository.findByEmail("test@example.com");
        assertThat(found).isPresent();
    }
}
```

### @MockBean & @SpyBean
```java
@SpringBootTest
class OrderServiceTest {
    @MockBean // Replaces bean in context with Mockito mock
    private PaymentGateway paymentGateway;
    
    @SpyBean // Wraps real bean with Mockito spy
    private EmailService emailService;
    
    @Autowired
    private OrderService orderService;
    
    @Test
    void shouldProcessOrder() {
        when(paymentGateway.charge(any())).thenReturn(new PaymentResult(true));
        orderService.process(new Order(...));
        verify(emailService, times(1)).sendConfirmation(any());
    }
}
```

---

## Conditional Annotations

```java
// @ConditionalOnProperty - Based on config property
@ConditionalOnProperty(name = "cache.type", havingValue = "redis")
public class RedisCacheConfig { }

// @ConditionalOnClass - Based on class availability on classpath
@ConditionalOnClass(RedisTemplate.class)
public class RedisAutoConfig { }

// @ConditionalOnMissingBean - Only if bean NOT already defined
@ConditionalOnMissingBean(CacheManager.class)
@Bean
public CacheManager defaultCacheManager() { ... }

// @ConditionalOnBean - Only if bean IS defined
@ConditionalOnBean(DataSource.class)
@Bean
public JdbcTemplate jdbcTemplate(DataSource ds) { ... }

// @ConditionalOnExpression - SpEL expression
@ConditionalOnExpression("${feature.enabled:true} && ${feature.mode} == 'advanced'")
public class AdvancedFeatureConfig { }

// @ConditionalOnWebApplication / @ConditionalOnNotWebApplication
@ConditionalOnWebApplication(type = Type.SERVLET)
public class ServletWebConfig { }

// @ConditionalOnJava
@ConditionalOnJava(range = Range.EQUAL_OR_NEWER, value = JavaVersion.SEVENTEEN)
public class Java17Config { }
```

---

## AOP Annotations

### @Aspect
```java
@Aspect
@Component
public class LoggingAspect {
    
    @Before("execution(* com.example.service.*.*(..))")
    public void logBefore(JoinPoint joinPoint) {
        log.info("Entering: {}", joinPoint.getSignature().getName());
    }
    
    @After("execution(* com.example.service.*.*(..))")
    public void logAfter(JoinPoint joinPoint) {
        log.info("Exiting: {}", joinPoint.getSignature().getName());
    }
    
    @AfterReturning(pointcut = "execution(* com.example.service.*.*(..))", returning = "result")
    public void logReturn(JoinPoint joinPoint, Object result) {
        log.info("Method {} returned: {}", joinPoint.getSignature().getName(), result);
    }
    
    @AfterThrowing(pointcut = "execution(* com.example.service.*.*(..))", throwing = "ex")
    public void logException(JoinPoint joinPoint, Exception ex) {
        log.error("Method {} threw: {}", joinPoint.getSignature().getName(), ex.getMessage());
    }
    
    @Around("@annotation(com.example.annotation.Timed)")
    public Object measureTime(ProceedingJoinPoint pjp) throws Throwable {
        long start = System.currentTimeMillis();
        try {
            return pjp.proceed();
        } finally {
            long elapsed = System.currentTimeMillis() - start;
            log.info("Method {} took {}ms", pjp.getSignature().getName(), elapsed);
        }
    }
}
```

### Pointcut Expressions
```java
@Aspect
@Component
public class SecurityAspect {
    
    // All methods in service package
    @Pointcut("execution(* com.example.service.*.*(..))")
    public void serviceLayer() {}
    
    // All methods annotated with @Secured
    @Pointcut("@annotation(org.springframework.security.access.annotation.Secured)")
    public void securedMethods() {}
    
    // Combine pointcuts
    @Before("serviceLayer() && securedMethods()")
    public void checkSecurity(JoinPoint joinPoint) { ... }
    
    // Within specific type
    @Pointcut("within(com.example.controller..*)")
    public void controllerLayer() {}
    
    // Target specific interface
    @Pointcut("target(com.example.service.PaymentService)")
    public void paymentServiceMethods() {}
}
```

---

## Scheduling & Async Annotations

### @Scheduled
```java
@Component
public class ScheduledJobs {
    
    @Scheduled(fixedRate = 60000) // Every 60 seconds (from START of previous)
    public void pollExternalService() { }
    
    @Scheduled(fixedDelay = 60000) // 60s after COMPLETION of previous
    public void processQueue() { }
    
    @Scheduled(cron = "0 0 */2 * * *") // Every 2 hours
    public void aggregateMetrics() { }
    
    @Scheduled(cron = "0 30 9 * * MON-FRI", zone = "America/New_York")
    public void weekdayReport() { }
    
    @Scheduled(fixedRateString = "${jobs.poll.interval:5000}") // From properties
    public void configurablePoll() { }
}
```

### @Async
```java
@Service
public class NotificationService {
    
    @Async("emailExecutor") // Use specific thread pool
    public CompletableFuture<Boolean> sendEmail(String to, String subject) {
        // Runs asynchronously
        boolean sent = emailClient.send(to, subject);
        return CompletableFuture.completedFuture(sent);
    }
    
    @Async
    public void fireAndForget(String event) {
        // No return value - truly fire and forget
        eventBus.publish(event);
    }
}

// GOTCHA: @Async only works when called from OUTSIDE the class
// Self-invocation bypasses the proxy!
@Service
public class BadExample {
    @Async
    public void asyncMethod() { }
    
    public void callerMethod() {
        asyncMethod(); // THIS RUNS SYNCHRONOUSLY! Proxy is bypassed.
    }
}
```

---

## Configuration Annotations

### @PropertySource
```java
@Configuration
@PropertySource("classpath:custom.properties")
@PropertySource("classpath:${env}.properties") // Dynamic
public class PropertyConfig { }
```

### @Import
```java
@Configuration
@Import({SecurityConfig.class, CacheConfig.class, BatchConfig.class})
public class AppConfig { }
```

### @ImportResource
```java
@Configuration
@ImportResource("classpath:legacy-beans.xml") // Import XML config
public class LegacyConfig { }
```

### @EventListener
```java
@Component
public class OrderEventHandler {
    
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        log.info("Order created: {}", event.getOrderId());
    }
    
    @EventListener(condition = "#event.amount > 1000")
    public void handleLargeOrder(OrderCreatedEvent event) {
        notifyManager(event);
    }
    
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void afterOrderCommitted(OrderCreatedEvent event) {
        // Only executes after transaction is committed
        sendConfirmationEmail(event);
    }
    
    @Async
    @EventListener
    public void asyncHandler(OrderCreatedEvent event) {
        // Runs in separate thread
    }
}
```

---

## Validation Annotations

```java
public class CreateUserRequest {
    @NotBlank(message = "Name is required")
    @Size(min = 2, max = 100)
    private String name;
    
    @NotNull
    @Email(message = "Invalid email format")
    private String email;
    
    @NotNull
    @Min(18)
    @Max(150)
    private Integer age;
    
    @Pattern(regexp = "^\\+?[1-9]\\d{1,14}$", message = "Invalid phone number")
    private String phone;
    
    @NotEmpty
    @Size(min = 1, max = 5)
    private List<@NotBlank String> tags;
    
    @Valid // Cascade validation to nested object
    @NotNull
    private AddressDTO address;
    
    @Future
    private LocalDate startDate;
    
    @PastOrPresent
    private LocalDate birthDate;
}

// Custom validator
@Target({ElementType.FIELD})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = UniqueEmailValidator.class)
public @interface UniqueEmail {
    String message() default "Email already exists";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class UniqueEmailValidator implements ConstraintValidator<UniqueEmail, String> {
    @Autowired
    private UserRepository userRepository;
    
    @Override
    public boolean isValid(String email, ConstraintValidatorContext context) {
        return !userRepository.existsByEmail(email);
    }
}
```

---

## Annotation Processing Order & Lifecycle

```
Application Startup:
1. @ComponentScan → Discovers @Component, @Service, @Repository, @Controller
2. @Configuration → Processes @Bean methods
3. @EnableAutoConfiguration → Applies auto-configuration
4. @Conditional* → Evaluates conditions
5. Bean instantiation → Constructor injection (@Autowired)
6. @PostConstruct → Initialization callbacks
7. @EventListener(ApplicationReadyEvent) → App is ready

Request Processing:
1. @RequestMapping → Route matched
2. @PreAuthorize → Security check
3. @Valid → Input validation
4. Handler method executes
5. @Transactional → Transaction boundary
6. @Cacheable → Cache check
7. Response serialization
8. @PostAuthorize → Output security check
```

---

## Common Mistakes & Best Practices

| Mistake | Correct Approach |
|---------|-----------------|
| `@Autowired` on field | Use constructor injection |
| `@Transactional` on private method | Must be public (proxy-based AOP) |
| Self-invocation with `@Async`/`@Transactional` | Call from another bean |
| `@Component` on everything | Use appropriate stereotype |
| Missing `@EnableAsync` for `@Async` | Always enable the feature |
| `@Transactional` on read-only operations | Use `@Transactional(readOnly = true)` |
| Forgetting `@Valid` for validation | Must annotate parameter |
| Using `@RequestParam` for body data | Use `@RequestBody` for JSON |
