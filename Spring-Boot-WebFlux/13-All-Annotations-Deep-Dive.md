# Spring Boot Annotations Deep Dive - Staff Engineer/Architect Level

## Table of Contents
1. [Core Spring Annotations](#1-core-spring-annotations)
2. [Web Annotations](#2-web-annotations)
3. [Data/Transaction Annotations](#3-datatransaction-annotations)
4. [AOP Annotations](#4-aop-annotations)
5. [Async/Scheduling Annotations](#5-asyncscheduling-annotations)
6. [Validation Annotations](#6-validation-annotations)
7. [Security Annotations](#7-security-annotations)
8. [Testing Annotations](#8-testing-annotations)
9. [Caching Annotations](#9-caching-annotations)
10. [Spring Boot Specific](#10-spring-boot-specific)

---

## 1. Core Spring Annotations

### @Component

**What it does internally:**
- Marks a class as a Spring-managed bean
- During component scanning, `ClassPathBeanDefinitionScanner` detects classes annotated with `@Component` (or its stereotypes)
- Creates a `BeanDefinition` and registers it with the `BeanDefinitionRegistry`
- The bean name defaults to the class name with the first letter lowercased

```java
@Component
public class EmailNotifier {
    // Spring manages lifecycle of this bean
}

@Component("customName")
public class SmsNotifier {
    // Registered with name "customName"
}
```

**Internal Flow:**
1. `ConfigurationClassPostProcessor` triggers scanning
2. `ClassPathScanningCandidateComponentProvider` uses ASM to read class metadata without loading classes
3. `AnnotationTypeFilter` matches `@Component` and meta-annotations
4. `BeanDefinitionReaderUtils.registerBeanDefinition()` registers it

**Pitfalls:**
- Placing `@Component` on a class outside the component scan base package
- Using `@Component` for configuration classes (use `@Configuration` instead)
- Not understanding that `@Component` beans use CGLIB proxying only when needed (unlike `@Configuration`)

---

### @Service

**What it does internally:**
- Semantically identical to `@Component` — it's meta-annotated with `@Component`
- Signals that the class holds business logic
- No additional behavior out of the box (Spring may add behavior in future versions)

```java
@Service
public class OrderService {
    private final OrderRepository orderRepository;
    
    public OrderService(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }
    
    public Order createOrder(OrderRequest request) {
        // business logic
        return orderRepository.save(mapToEntity(request));
    }
}
```

**Best Practice:** Use `@Service` for service-layer classes to communicate intent, even though functionally it's the same as `@Component`.

---

### @Repository

**What it does internally:**
- Meta-annotated with `@Component`
- **Critical additional behavior:** `PersistenceExceptionTranslationPostProcessor` automatically translates platform-specific persistence exceptions (e.g., `SQLException`, Hibernate exceptions) into Spring's `DataAccessException` hierarchy
- This translation happens via AOP proxy wrapping

```java
@Repository
public class JdbcOrderRepository implements OrderRepository {
    
    private final JdbcTemplate jdbcTemplate;
    
    // If a SQLException is thrown, it's automatically translated
    // to a DataAccessException subclass
    public Order findById(Long id) {
        return jdbcTemplate.queryForObject(
            "SELECT * FROM orders WHERE id = ?",
            new OrderRowMapper(), id);
    }
}
```

**Internal mechanism:**
```
Method call → AOP Proxy → PersistenceExceptionTranslationInterceptor
  → catches platform exception → PersistenceExceptionTranslator.translateExceptionIfPossible()
  → throws DataAccessException subclass
```

**Pitfalls:**
- Not including `spring-aspects` or not having exception translation enabled — the annotation becomes purely semantic
- When using Spring Data JPA, your interfaces don't need `@Repository` — the framework adds it automatically via `JpaRepositoryFactoryBean`

---

### @Controller

**What it does internally:**
- Meta-annotated with `@Component`
- Detected by `RequestMappingHandlerMapping` as a handler for web requests
- Return values are resolved as view names by default (via `ViewResolver`)

```java
@Controller
public class HomeController {
    
    @GetMapping("/")
    public String home(Model model) {
        model.addAttribute("message", "Hello");
        return "home"; // resolved to a view (e.g., home.html)
    }
}
```

---

### @RestController

**What it does internally:**
- Composed of `@Controller` + `@ResponseBody`
- Every handler method's return value is serialized directly to the response body (via `HttpMessageConverter`)
- No view resolution occurs

```java
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {
    
    @GetMapping("/{id}")
    public OrderResponse getOrder(@PathVariable Long id) {
        // Return value is serialized to JSON via Jackson's MappingJackson2HttpMessageConverter
        return orderService.getOrder(id);
    }
}
```

**Internal Processing:**
1. `RequestMappingHandlerAdapter` invokes the handler method
2. `RequestResponseBodyMethodProcessor` handles the return value
3. Content negotiation determines the `MediaType`
4. Appropriate `HttpMessageConverter` serializes the object

---

### @Bean

**What it does internally:**
- Declares a method as a bean factory method
- The returned object is registered as a bean in the ApplicationContext
- Method name becomes the bean name (unless overridden)
- Called by the Spring container, NOT by you directly

```java
@Configuration
public class AppConfig {
    
    @Bean
    public RestTemplate restTemplate(RestTemplateBuilder builder) {
        return builder
            .setConnectTimeout(Duration.ofSeconds(5))
            .setReadTimeout(Duration.ofSeconds(10))
            .build();
    }
    
    @Bean(initMethod = "init", destroyMethod = "cleanup")
    public DataSourcePool dataSourcePool() {
        return new DataSourcePool();
    }
    
    @Bean
    @Scope("prototype")
    public RequestContext requestContext() {
        return new RequestContext();
    }
}
```

**Key attributes:**
- `name` / `value`: Bean name(s), supports aliases
- `initMethod`: Called after properties set
- `destroyMethod`: Called on context shutdown (defaults to `"(inferred)"` which detects `close()`/`shutdown()` methods)
- `autowireCandidate`: Whether this bean is a candidate for autowiring (default true)

**Pitfall - Inter-bean references in `@Configuration` vs `@Component`:**

```java
@Configuration // CGLIB proxy ensures singleton semantics
public class AppConfig {
    
    @Bean
    public ServiceA serviceA() {
        return new ServiceA(commonDependency()); // calls the PROXY, returns same instance
    }
    
    @Bean
    public ServiceB serviceB() {
        return new ServiceB(commonDependency()); // same instance as above
    }
    
    @Bean
    public CommonDependency commonDependency() {
        return new CommonDependency();
    }
}
```

If you use `@Component` instead of `@Configuration`, each call to `commonDependency()` creates a NEW instance (no CGLIB interception). This is called "lite mode."

---

### @Configuration

**What it does internally:**
- Meta-annotated with `@Component`
- **Critical:** Processed by `ConfigurationClassPostProcessor`
- The class is subclassed via CGLIB at runtime to intercept `@Bean` method calls
- Ensures that `@Bean` methods returning singletons always return the same instance, even when called directly from other `@Bean` methods

```java
@Configuration(proxyBeanMethods = true) // default
public class DatabaseConfig {
    
    @Bean
    public DataSource dataSource() {
        HikariDataSource ds = new HikariDataSource();
        ds.setJdbcUrl("jdbc:postgresql://localhost:5432/mydb");
        ds.setUsername("user");
        ds.setPassword("pass");
        ds.setMaximumPoolSize(20);
        return ds;
    }
    
    @Bean
    public JdbcTemplate jdbcTemplate() {
        return new JdbcTemplate(dataSource()); // returns SAME DataSource due to CGLIB proxy
    }
}
```

**`proxyBeanMethods = false` (Lite Mode):**
```java
@Configuration(proxyBeanMethods = false) // No CGLIB subclass
public class LiteConfig {
    // Faster startup, but inter-bean method calls create new instances
    // Use constructor injection of @Bean results instead
    
    @Bean
    public JdbcTemplate jdbcTemplate(DataSource dataSource) { // inject instead
        return new JdbcTemplate(dataSource);
    }
}
```

**Best Practice:** Use `proxyBeanMethods = false` in libraries and auto-configurations for faster startup. Use parameter injection instead of inter-bean method calls.

---

### @Import

**What it does internally:**
- Allows importing additional `@Configuration` classes, `ImportSelector` implementations, or `ImportBeanDefinitionRegistrar` implementations
- Processed by `ConfigurationClassParser`

```java
@Configuration
@Import({DatabaseConfig.class, SecurityConfig.class})
public class AppConfig {
}

// ImportSelector - dynamic conditional import
public class MyImportSelector implements ImportSelector {
    @Override
    public String[] selectImports(AnnotationMetadata importingClassMetadata) {
        if (someCondition()) {
            return new String[]{RedisConfig.class.getName()};
        }
        return new String[]{InMemoryCacheConfig.class.getName()};
    }
}

// ImportBeanDefinitionRegistrar - programmatic bean registration
public class MyRegistrar implements ImportBeanDefinitionRegistrar {
    @Override
    public void registerBeanDefinitions(AnnotationMetadata metadata, 
                                         BeanDefinitionRegistry registry) {
        GenericBeanDefinition bd = new GenericBeanDefinition();
        bd.setBeanClass(MyDynamicBean.class);
        registry.registerBeanDefinition("myDynamicBean", bd);
    }
}
```

**This is how Spring Boot auto-configuration works internally** — `@EnableAutoConfiguration` uses `AutoConfigurationImportSelector` which implements `DeferredImportSelector`.

---

### @ImportResource

```java
@Configuration
@ImportResource("classpath:legacy-beans.xml")
public class LegacyIntegrationConfig {
    // Imports XML-defined beans into the application context
}
```

---

### @Autowired

**What it does internally:**
- Processed by `AutowiredAnnotationBeanPostProcessor`
- Resolves dependencies by type from the ApplicationContext
- Can be applied to constructors, fields, setter methods, and arbitrary methods
- Since Spring 4.3, if a class has a single constructor, `@Autowired` is implicit

**Resolution algorithm:**
1. Find all beans matching the type
2. If multiple candidates: filter by `@Qualifier`, `@Primary`, bean name matching parameter name
3. If still ambiguous: throw `NoUniqueBeanDefinitionException`

```java
@Service
public class NotificationService {
    
    // Field injection (discouraged - untestable, hides dependencies)
    @Autowired
    private EmailSender emailSender;
    
    // Constructor injection (preferred - immutable, explicit dependencies)
    private final SmsSender smsSender;
    
    public NotificationService(SmsSender smsSender) { // @Autowired implicit
        this.smsSender = smsSender;
    }
    
    // Setter injection (optional dependencies)
    private PushNotifier pushNotifier;
    
    @Autowired(required = false)
    public void setPushNotifier(PushNotifier pushNotifier) {
        this.pushNotifier = pushNotifier;
    }
    
    // Collection injection - injects ALL beans of this type
    @Autowired
    private List<NotificationChannel> allChannels;
    
    // Map injection - keyed by bean name
    @Autowired
    private Map<String, NotificationChannel> channelMap;
}
```

**Pitfalls:**
- Circular dependencies with constructor injection cause `BeanCurrentlyInCreationException`
- Field injection makes unit testing hard (requires reflection or Spring context)
- `@Autowired` on a field of a non-Spring-managed object does nothing

---

### @Qualifier

**What it does internally:**
- Narrows down the autowiring candidate when multiple beans of the same type exist
- Matched by `QualifierAnnotationAutowireCandidateResolver`

```java
@Configuration
public class DataSourceConfig {
    
    @Bean
    @Qualifier("primary")
    public DataSource primaryDataSource() {
        return createDataSource("jdbc:postgresql://primary:5432/db");
    }
    
    @Bean
    @Qualifier("replica")
    public DataSource replicaDataSource() {
        return createDataSource("jdbc:postgresql://replica:5432/db");
    }
}

@Service
public class ReportService {
    
    private final DataSource dataSource;
    
    public ReportService(@Qualifier("replica") DataSource dataSource) {
        this.dataSource = dataSource; // Uses replica for read-heavy reports
    }
}
```

**Custom qualifier annotations:**
```java
@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Qualifier
public @interface ReadOnly {
}

@Service
public class ReportService {
    public ReportService(@ReadOnly DataSource dataSource) { ... }
}
```

---

### @Primary

**What it does internally:**
- Marks a bean as the default candidate when multiple beans of the same type exist
- If no `@Qualifier` is specified at the injection point, the `@Primary` bean wins

```java
@Configuration
public class ObjectMapperConfig {
    
    @Bean
    @Primary
    public ObjectMapper defaultObjectMapper() {
        return new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }
    
    @Bean("xmlMapper")
    public ObjectMapper xmlObjectMapper() {
        return new XmlMapper();
    }
}
```

---

### @Lazy

**What it does internally:**
- Defers bean initialization until first access
- On fields/parameters: creates a proxy that resolves the bean on first method call
- Useful for breaking circular dependencies and improving startup time

```java
@Configuration
public class ExpensiveConfig {
    
    @Bean
    @Lazy
    public ExpensiveService expensiveService() {
        // Not created at startup — only when first injected/accessed
        return new ExpensiveService(loadLargeModel());
    }
}

// Breaking circular dependency with @Lazy
@Service
public class ServiceA {
    public ServiceA(@Lazy ServiceB serviceB) {
        // serviceB is a proxy; actual ServiceB created on first method call
        this.serviceB = serviceB;
    }
}
```

---

### @Scope

**What it does internally:**
- Defines the lifecycle scope of a bean
- Default is `singleton` (one instance per ApplicationContext)
- `prototype`: new instance on every injection/lookup
- Web scopes: `request`, `session`, `application`, `websocket`

```java
@Component
@Scope("prototype")
public class ShoppingCart {
    private List<Item> items = new ArrayList<>();
}

// Injecting prototype into singleton requires special handling
@Service
public class OrderService {
    
    @Autowired
    private ObjectProvider<ShoppingCart> cartProvider;
    
    public void processOrder() {
        ShoppingCart cart = cartProvider.getObject(); // new instance each time
    }
}

// Scoped proxy approach
@Component
@Scope(value = "request", proxyMode = ScopedProxyMode.TARGET_CLASS)
public class RequestScopedAuditContext {
    private String userId;
    private Instant requestTime;
}
```

**Pitfall:** Injecting a prototype-scoped bean into a singleton — the prototype is only created ONCE. Use `ObjectProvider`, `@Lookup`, or scoped proxy.

---

### @Lookup

**What it does internally:**
- Spring overrides the method at runtime using CGLIB to return a new bean from the context on each call
- Solves the prototype-in-singleton problem

```java
@Service
public abstract class CommandProcessorService {
    
    public void process(String commandType) {
        Command command = createCommand(); // new prototype each time
        command.execute(commandType);
    }
    
    @Lookup
    protected abstract Command createCommand(); // Spring implements this via CGLIB
}
```

---

### @Value

**What it does internally:**
- Resolved by `AutowiredAnnotationBeanPostProcessor`
- Uses Spring Expression Language (SpEL) or property placeholder resolution
- `PropertySourcesPlaceholderConfigurer` resolves `${...}` placeholders

```java
@Service
public class PaymentService {
    
    @Value("${payment.gateway.url}")
    private String gatewayUrl;
    
    @Value("${payment.timeout:5000}") // default value
    private int timeout;
    
    @Value("${payment.enabled:true}")
    private boolean enabled;
    
    // SpEL expressions
    @Value("#{systemProperties['user.region'] ?: 'US'}")
    private String region;
    
    @Value("#{T(java.lang.Math).random() * 100}")
    private double randomId;
    
    @Value("${payment.allowed-currencies}")
    private List<String> allowedCurrencies; // comma-separated in properties
    
    @Value("#{${payment.fee-map}}") // SpEL to parse map from properties
    private Map<String, Double> feeMap;
}
```

**Pitfalls:**
- `@Value` doesn't work on `static` fields
- `@Value` doesn't work in `@Configuration` classes' `@Bean` methods if the property isn't resolved yet (ordering issue)
- Missing properties without defaults cause `BeanCreationException` at startup

---

### @PropertySource

```java
@Configuration
@PropertySource("classpath:payment.properties")
@PropertySource(value = "classpath:payment-${spring.profiles.active}.properties", 
                ignoreResourceNotFound = true)
public class PaymentConfig {
    
    @Value("${payment.api.key}")
    private String apiKey;
}
```

---

### @ConfigurationProperties

**What it does internally:**
- Binds external configuration (application.yml/properties) to a POJO
- Processed by `ConfigurationPropertiesBindingPostProcessor`
- Uses relaxed binding: `my-property`, `myProperty`, `MY_PROPERTY` all map to the same field
- Type-safe alternative to `@Value`

```java
@ConfigurationProperties(prefix = "app.datasource")
@Validated
public class DataSourceProperties {
    
    @NotBlank
    private String url;
    
    private String username;
    private String password;
    
    @Min(1)
    @Max(100)
    private int maxPoolSize = 10;
    
    @DurationUnit(ChronoUnit.SECONDS)
    private Duration connectionTimeout = Duration.ofSeconds(30);
    
    private Map<String, String> additionalProperties = new HashMap<>();
    
    private final Pool pool = new Pool();
    
    // Nested class
    public static class Pool {
        private int minIdle = 5;
        private int maxIdle = 10;
        // getters/setters
    }
    
    // getters and setters required for binding
}

// Enable it
@Configuration
@EnableConfigurationProperties(DataSourceProperties.class)
public class AppConfig { }

// Or use @ConfigurationPropertiesScan
@SpringBootApplication
@ConfigurationPropertiesScan
public class Application { }
```

**application.yml:**
```yaml
app:
  datasource:
    url: jdbc:postgresql://localhost:5432/mydb
    username: admin
    password: secret
    max-pool-size: 20
    connection-timeout: 10s
    additional-properties:
      ssl: "true"
      sslmode: require
    pool:
      min-idle: 2
      max-idle: 15
```

**Immutable `@ConfigurationProperties` (Spring Boot 2.2+):**
```java
@ConfigurationProperties(prefix = "app.mail")
public record MailProperties(
    String host,
    int port,
    @DefaultValue("true") boolean auth,
    @DefaultValue("smtp") String protocol
) { }
```

---

### @Profile

**What it does internally:**
- Beans are registered only when the specified profile is active
- Checked during bean definition registration phase
- Profiles activated via `spring.profiles.active`

```java
@Configuration
@Profile("production")
public class ProductionDataSourceConfig {
    
    @Bean
    public DataSource dataSource() {
        // Real database connection pool
        HikariDataSource ds = new HikariDataSource();
        ds.setJdbcUrl("jdbc:postgresql://prod-db:5432/app");
        return ds;
    }
}

@Configuration
@Profile("!production") // NOT production
public class DevDataSourceConfig {
    
    @Bean
    public DataSource dataSource() {
        return new EmbeddedDatabaseBuilder()
            .setType(EmbeddedDatabaseType.H2)
            .build();
    }
}

// Profile expressions (Spring 5.1+)
@Profile("production & us-east")
@Profile("staging | development")
```

---

### @Conditional and @ConditionalOn* Variants

**@Conditional — the foundation:**
```java
public class RedisAvailableCondition implements Condition {
    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        try {
            Class.forName("redis.clients.jedis.Jedis");
            return true;
        } catch (ClassNotFoundException e) {
            return false;
        }
    }
}

@Configuration
@Conditional(RedisAvailableCondition.class)
public class RedisCacheConfig { }
```

**Spring Boot @ConditionalOn* variants:**

| Annotation | Condition |
|---|---|
| `@ConditionalOnClass` | Class is on classpath |
| `@ConditionalOnMissingClass` | Class is NOT on classpath |
| `@ConditionalOnBean` | Bean exists in context |
| `@ConditionalOnMissingBean` | Bean does NOT exist |
| `@ConditionalOnProperty` | Property has specific value |
| `@ConditionalOnResource` | Resource exists |
| `@ConditionalOnWebApplication` | Is a web app |
| `@ConditionalOnExpression` | SpEL evaluates to true |
| `@ConditionalOnJava` | Java version matches |
| `@ConditionalOnCloudPlatform` | Running on specific cloud |

```java
@Configuration
@ConditionalOnClass(RedisTemplate.class)
@ConditionalOnProperty(prefix = "app.cache", name = "type", havingValue = "redis")
public class RedisCacheAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean
    public CacheManager cacheManager(RedisConnectionFactory factory) {
        return RedisCacheManager.builder(factory).build();
    }
}
```

---

### @ComponentScan

```java
@Configuration
@ComponentScan(
    basePackages = "com.example.app",
    excludeFilters = @ComponentScan.Filter(
        type = FilterType.REGEX, 
        pattern = "com\\.example\\.app\\.legacy\\..*"
    ),
    includeFilters = @ComponentScan.Filter(
        type = FilterType.ANNOTATION, 
        classes = MyCustomAnnotation.class
    )
)
public class AppConfig { }
```

**Filter types:** `ANNOTATION`, `ASSIGNABLE_TYPE`, `ASPECTJ`, `REGEX`, `CUSTOM`

---

### @EntityScan and @EnableJpaRepositories

```java
@SpringBootApplication
@EntityScan(basePackages = "com.example.domain.entities")
@EnableJpaRepositories(
    basePackages = "com.example.domain.repositories",
    entityManagerFactoryRef = "primaryEntityManagerFactory",
    transactionManagerRef = "primaryTransactionManager"
)
public class Application { }
```

---

## 2. Web Annotations

### @RequestMapping

**What it does internally:**
- Detected by `RequestMappingHandlerMapping` during initialization
- Creates a `RequestMappingInfo` object combining all constraints
- The `DispatcherServlet` uses this mapping info to route requests

```java
@RestController
@RequestMapping(
    path = "/api/v1/products",
    produces = MediaType.APPLICATION_JSON_VALUE
)
public class ProductController {
    
    @RequestMapping(
        method = RequestMethod.GET,
        params = "category",
        headers = "X-Api-Version=1"
    )
    public List<Product> getByCategory(@RequestParam String category) {
        return productService.findByCategory(category);
    }
    
    // Consumes restricts by Content-Type header
    @RequestMapping(
        method = RequestMethod.POST,
        consumes = MediaType.APPLICATION_JSON_VALUE
    )
    public Product create(@RequestBody Product product) {
        return productService.save(product);
    }
}
```

**Request matching priority:** Most specific mapping wins. Specificity is determined by number of path variables, params, headers, consumes, produces constraints.

---

### @GetMapping, @PostMapping, @PutMapping, @DeleteMapping, @PatchMapping

Shortcuts for `@RequestMapping(method = ...)`:

```java
@RestController
@RequestMapping("/api/v1/users")
public class UserController {
    
    @GetMapping
    public Page<UserDto> list(Pageable pageable) { ... }
    
    @GetMapping("/{id}")
    public UserDto get(@PathVariable Long id) { ... }
    
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public UserDto create(@Valid @RequestBody CreateUserRequest req) { ... }
    
    @PutMapping("/{id}")
    public UserDto update(@PathVariable Long id, @Valid @RequestBody UpdateUserRequest req) { ... }
    
    @PatchMapping("/{id}")
    public UserDto patch(@PathVariable Long id, @RequestBody Map<String, Object> updates) { ... }
    
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id) { ... }
}
```

---

### @RequestBody

**What it does internally:**
- Processed by `RequestResponseBodyMethodProcessor`
- Reads the HTTP request body using the appropriate `HttpMessageConverter`
- For JSON: `MappingJackson2HttpMessageConverter` uses Jackson `ObjectMapper`
- Content-Type header determines which converter to use

```java
@PostMapping("/orders")
public OrderResponse createOrder(
    @Valid @RequestBody OrderRequest request) { // deserialized from JSON
    return orderService.create(request);
}
```

**Pitfalls:**
- Request body can only be read ONCE (it's a stream). Using `@RequestBody` on multiple parameters fails.
- Missing `Content-Type` header → 415 Unsupported Media Type

---

### @ResponseBody

Implicit in `@RestController`. Tells Spring to serialize the return value directly to the response body.

---

### @ResponseStatus

```java
@PostMapping
@ResponseStatus(HttpStatus.CREATED) // 201 instead of default 200
public UserDto create(@RequestBody CreateUserRequest req) { ... }

// On exception classes
@ResponseStatus(HttpStatus.NOT_FOUND)
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String resource, Long id) {
        super(resource + " not found with id: " + id);
    }
}
```

---

### @PathVariable

```java
@GetMapping("/users/{userId}/orders/{orderId}")
public OrderDto getOrder(
    @PathVariable Long userId,
    @PathVariable("orderId") Long id) { // explicit name binding
    return orderService.findByUserAndId(userId, id);
}

// Optional path variable
@GetMapping({"/files/{path}", "/files"})
public Resource getFile(@PathVariable(required = false) String path) { ... }

// Regex in path
@GetMapping("/files/{filename:.+}") // allows dots in path variable
public Resource getFile(@PathVariable String filename) { ... }
```

---

### @RequestParam

```java
@GetMapping("/search")
public Page<Product> search(
    @RequestParam String query,
    @RequestParam(defaultValue = "0") int page,
    @RequestParam(defaultValue = "20") int size,
    @RequestParam(required = false) String category,
    @RequestParam List<String> tags) { // ?tags=a&tags=b or ?tags=a,b
    ...
}

// All params as Map
@GetMapping("/filter")
public List<Product> filter(@RequestParam Map<String, String> allParams) { ... }
```

---

### @RequestHeader

```java
@GetMapping("/info")
public ResponseEntity<Info> getInfo(
    @RequestHeader("Authorization") String authHeader,
    @RequestHeader(value = "X-Request-Id", defaultValue = "unknown") String requestId,
    @RequestHeader HttpHeaders headers) { // all headers
    ...
}
```

---

### @CookieValue

```java
@GetMapping("/preferences")
public Preferences getPrefs(
    @CookieValue(name = "session_id") String sessionId,
    @CookieValue(name = "theme", defaultValue = "light") String theme) {
    ...
}
```

---

### @MatrixVariable

Matrix variables appear in path segments: `/cars;color=red;year=2024`

```java
// Enable in WebMvcConfigurer: 
// configurer.setRemoveSemicolonContent(false);

@GetMapping("/cars/{make}")
public List<Car> getCars(
    @PathVariable String make,
    @MatrixVariable(pathVar = "make") Map<String, String> matrixVars) {
    // GET /cars/toyota;color=red;year=2024
    // matrixVars = {color=red, year=2024}
    ...
}
```

---

### @ModelAttribute

```java
// On method parameter - binds request params to object
@PostMapping("/register")
public String register(@ModelAttribute @Valid UserForm form, BindingResult result) {
    if (result.hasErrors()) return "register";
    userService.register(form);
    return "redirect:/login";
}

// On method - adds to model before every handler in this controller
@ModelAttribute("categories")
public List<Category> categories() {
    return categoryService.findAll(); // available in all views
}
```

---

### @SessionAttributes

```java
@Controller
@SessionAttributes("wizard") // keeps "wizard" model attribute in session
public class WizardController {
    
    @ModelAttribute("wizard")
    public WizardForm wizardForm() {
        return new WizardForm();
    }
    
    @PostMapping("/wizard/step1")
    public String step1(@ModelAttribute("wizard") WizardForm form) {
        return "wizard/step2";
    }
    
    @PostMapping("/wizard/complete")
    public String complete(@ModelAttribute("wizard") WizardForm form, 
                          SessionStatus status) {
        wizardService.complete(form);
        status.setComplete(); // removes from session
        return "redirect:/done";
    }
}
```

---

### @RequestAttribute

```java
// Access attributes set by filters/interceptors
@GetMapping("/dashboard")
public String dashboard(@RequestAttribute("tenantId") String tenantId) {
    // Set by a filter: request.setAttribute("tenantId", resolved);
    ...
}
```

---

### @CrossOrigin

```java
@RestController
@CrossOrigin(origins = "https://frontend.example.com", maxAge = 3600)
@RequestMapping("/api/data")
public class DataController {
    
    @CrossOrigin(origins = "*") // override class-level for this endpoint
    @GetMapping("/public")
    public PublicData getPublicData() { ... }
}
```

**Internal:** `CorsInterceptor` / `CorsFilter` handles preflight OPTIONS requests and adds CORS headers.

---

### @ExceptionHandler

```java
@RestController
public class OrderController {
    
    @PostMapping("/orders")
    public Order create(@RequestBody OrderRequest req) {
        return orderService.create(req); // may throw OrderValidationException
    }
    
    // Handles exceptions thrown by this controller's methods
    @ExceptionHandler(OrderValidationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ErrorResponse handleValidation(OrderValidationException ex) {
        return new ErrorResponse(ex.getErrors());
    }
}
```

---

### @ControllerAdvice / @RestControllerAdvice

**What it does internally:**
- Detected by `ExceptionHandlerExceptionResolver`
- Provides global exception handling, model attributes, and data binding customization
- `@RestControllerAdvice` = `@ControllerAdvice` + `@ResponseBody`

```java
@RestControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(ResourceNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ProblemDetail handleNotFound(ResourceNotFoundException ex) {
        ProblemDetail pd = ProblemDetail.forStatus(HttpStatus.NOT_FOUND);
        pd.setTitle("Resource Not Found");
        pd.setDetail(ex.getMessage());
        return pd;
    }
    
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ProblemDetail handleValidation(MethodArgumentNotValidException ex) {
        ProblemDetail pd = ProblemDetail.forStatus(HttpStatus.BAD_REQUEST);
        pd.setTitle("Validation Failed");
        Map<String, String> errors = ex.getBindingResult().getFieldErrors().stream()
            .collect(Collectors.toMap(
                FieldError::getField, 
                FieldError::getDefaultMessage,
                (a, b) -> a));
        pd.setProperty("errors", errors);
        return pd;
    }
    
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ProblemDetail handleGeneral(Exception ex) {
        log.error("Unhandled exception", ex);
        ProblemDetail pd = ProblemDetail.forStatus(HttpStatus.INTERNAL_SERVER_ERROR);
        pd.setTitle("Internal Server Error");
        return pd;
    }
}

// Scoped to specific controllers
@RestControllerAdvice(assignableTypes = {OrderController.class, PaymentController.class})
@RestControllerAdvice(basePackages = "com.example.api.v2")
@RestControllerAdvice(annotations = AdminController.class)
```

---

## 3. Data/Transaction Annotations

### @Transactional

**What it does internally:**
1. Spring creates a proxy (JDK dynamic proxy for interfaces, CGLIB for classes)
2. `TransactionInterceptor` intercepts the method call
3. `PlatformTransactionManager` begins a transaction
4. Method executes
5. On success: commit. On `RuntimeException`/`Error`: rollback

**Every attribute explained:**

```java
@Service
public class OrderService {
    
    @Transactional(
        propagation = Propagation.REQUIRED,      // default
        isolation = Isolation.READ_COMMITTED,     // default depends on DB
        timeout = 30,                             // seconds
        readOnly = false,                         // hint for optimization
        rollbackFor = {BusinessException.class},  // rollback on checked exceptions too
        noRollbackFor = {IgnorableException.class},
        transactionManager = "primaryTxManager",  // which TM to use
        label = {"order-creation"}                // Spring 5.3+
    )
    public Order createOrder(OrderRequest request) {
        Order order = orderRepository.save(mapToOrder(request));
        paymentService.charge(order); // participates in same transaction
        inventoryService.reserve(order.getItems()); 
        return order;
    }
}
```

**Propagation levels:**

| Propagation | Behavior |
|---|---|
| `REQUIRED` | Join existing or create new (default) |
| `REQUIRES_NEW` | Suspend existing, always create new |
| `SUPPORTS` | Join existing or run non-transactional |
| `NOT_SUPPORTED` | Suspend existing, run non-transactional |
| `MANDATORY` | Must have existing, else exception |
| `NEVER` | Must NOT have existing, else exception |
| `NESTED` | Savepoint within existing (JDBC only) |

```java
@Service
public class AuditService {
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void logAuditEvent(AuditEvent event) {
        // Always commits independently, even if caller rolls back
        auditRepository.save(event);
    }
}
```

**Critical Pitfalls:**

1. **Self-invocation bypass:**
```java
@Service
public class UserService {
    
    public void registerUser(User user) {
        saveUser(user); // DIRECT call — NO proxy — NO transaction!
    }
    
    @Transactional
    public void saveUser(User user) {
        userRepository.save(user);
    }
}
// Fix: inject self, or extract to another bean, or use AopContext.currentProxy()
```

2. **Checked exceptions don't trigger rollback by default:**
```java
@Transactional // only rolls back on RuntimeException/Error
public void process() throws IOException {
    // ... 
    throw new IOException("fail"); // COMMITS! Transaction does NOT rollback
}

// Fix:
@Transactional(rollbackFor = Exception.class)
```

3. **`readOnly = true` doesn't prevent writes** — it's a hint. Hibernate may skip dirty checking for performance.

---

### @Entity, @Table, @Column, @Id, @GeneratedValue

```java
@Entity
@Table(
    name = "orders",
    schema = "ecommerce",
    indexes = {
        @Index(name = "idx_order_user", columnList = "user_id"),
        @Index(name = "idx_order_status_date", columnList = "status, created_at")
    },
    uniqueConstraints = {
        @UniqueConstraint(name = "uk_order_number", columnNames = "order_number")
    }
)
public class Order {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY) // DB auto-increment
    private Long id;
    
    // GenerationType options:
    // IDENTITY - DB auto-increment (no batch inserts possible)
    // SEQUENCE - DB sequence (preferred for PostgreSQL, allows batching)
    // TABLE - simulated sequence via table (poor performance)
    // UUID - Spring 6+ UUID generation
    // AUTO - provider chooses
    
    @Column(name = "order_number", nullable = false, unique = true, length = 36)
    private String orderNumber;
    
    @Column(precision = 10, scale = 2)
    private BigDecimal totalAmount;
    
    @Column(columnDefinition = "TEXT")
    private String notes;
    
    @Enumerated(EnumType.STRING) // NEVER use ORDINAL in production
    @Column(nullable = false)
    private OrderStatus status;
    
    @Column(updatable = false) // set once, never updated
    private LocalDateTime createdAt;
    
    @Column(insertable = false) // only set on updates
    private LocalDateTime updatedAt;
}
```

---

### @OneToMany, @ManyToOne, @ManyToMany, @OneToOne

```java
@Entity
public class Order {
    
    // Parent side (inverse/non-owning)
    @OneToMany(
        mappedBy = "order",              // field name in OrderItem
        cascade = CascadeType.ALL,       // cascade all operations
        orphanRemoval = true,            // delete items removed from collection
        fetch = FetchType.LAZY           // ALWAYS use LAZY for collections
    )
    private List<OrderItem> items = new ArrayList<>();
    
    // Owning side
    @ManyToOne(fetch = FetchType.LAZY)   // LAZY even for *ToOne (default is EAGER!)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;
    
    // Helper methods for bidirectional sync
    public void addItem(OrderItem item) {
        items.add(item);
        item.setOrder(this);
    }
    
    public void removeItem(OrderItem item) {
        items.remove(item);
        item.setOrder(null);
    }
}

@Entity
public class OrderItem {
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "product_id")
    private Product product;
}
```

**@ManyToMany:**
```java
@Entity
public class Student {
    
    @ManyToMany(cascade = {CascadeType.PERSIST, CascadeType.MERGE})
    @JoinTable(
        name = "student_course",
        joinColumns = @JoinColumn(name = "student_id"),
        inverseJoinColumns = @JoinColumn(name = "course_id")
    )
    private Set<Course> courses = new HashSet<>();
}

@Entity
public class Course {
    
    @ManyToMany(mappedBy = "courses")
    private Set<Student> students = new HashSet<>();
}
```

**@OneToOne:**
```java
@Entity
public class User {
    
    @OneToOne(
        mappedBy = "user",
        cascade = CascadeType.ALL,
        fetch = FetchType.LAZY,
        optional = false
    )
    private UserProfile profile;
}

@Entity
public class UserProfile {
    
    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    @MapsId // shares PK with User
    private User user;
}
```

**Cascade Types:**
- `PERSIST` — propagate persist
- `MERGE` — propagate merge
- `REMOVE` — propagate delete
- `REFRESH` — propagate refresh
- `DETACH` — propagate detach
- `ALL` — all of the above

**Pitfall:** `CascadeType.REMOVE` on `@ManyToMany` deletes the related entity, not just the association.

---

### @MappedSuperclass and @Inheritance

```java
@MappedSuperclass
public abstract class BaseEntity {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @CreatedDate
    private LocalDateTime createdAt;
    
    @LastModifiedDate
    private LocalDateTime updatedAt;
    
    @Version
    private Long version;
}

// Inheritance strategies
@Entity
@Inheritance(strategy = InheritanceType.SINGLE_TABLE) // one table, discriminator column
@DiscriminatorColumn(name = "payment_type", discriminatorType = DiscriminatorType.STRING)
public abstract class Payment {
    @Id @GeneratedValue private Long id;
    private BigDecimal amount;
}

@Entity
@DiscriminatorValue("CREDIT_CARD")
public class CreditCardPayment extends Payment {
    private String cardNumber;
    private String expiryDate;
}

@Entity
@DiscriminatorValue("BANK_TRANSFER")
public class BankTransferPayment extends Payment {
    private String accountNumber;
    private String routingNumber;
}
```

**Inheritance strategies comparison:**
- `SINGLE_TABLE`: Best performance (no joins), but nullable columns for subclass fields
- `JOINED`: Normalized, one table per class joined via FK. Clean but slow for deep hierarchies
- `TABLE_PER_CLASS`: Each concrete class has its own table. Poor polymorphic query performance

---

### @Query, @Modifying, @EntityGraph, @NamedQuery

```java
public interface OrderRepository extends JpaRepository<Order, Long> {
    
    // JPQL
    @Query("SELECT o FROM Order o WHERE o.user.id = :userId AND o.status = :status")
    List<Order> findByUserAndStatus(@Param("userId") Long userId, 
                                     @Param("status") OrderStatus status);
    
    // Native SQL
    @Query(value = "SELECT * FROM orders WHERE created_at > :since", nativeQuery = true)
    List<Order> findRecentNative(@Param("since") LocalDateTime since);
    
    // Modifying queries (UPDATE/DELETE)
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("UPDATE Order o SET o.status = :status WHERE o.id = :id")
    int updateStatus(@Param("id") Long id, @Param("status") OrderStatus status);
    
    // EntityGraph to solve N+1 problem
    @EntityGraph(attributePaths = {"items", "items.product", "user"})
    @Query("SELECT o FROM Order o WHERE o.id = :id")
    Optional<Order> findByIdWithDetails(@Param("id") Long id);
    
    // Projection
    @Query("SELECT o.id as id, o.orderNumber as orderNumber, o.totalAmount as totalAmount FROM Order o")
    List<OrderSummary> findAllSummaries();
}

// Named EntityGraph on entity
@Entity
@NamedEntityGraph(
    name = "Order.withItems",
    attributeNodes = @NamedAttributeNode(value = "items", subgraph = "items.product"),
    subgraphs = @NamedSubgraph(name = "items.product", attributeNodes = @NamedAttributeNode("product"))
)
public class Order { ... }
```

**`@Modifying` pitfalls:**
- Without `clearAutomatically = true`, the persistence context may contain stale data
- Bulk operations bypass entity lifecycle callbacks and Hibernate caches

---

### @Version (Optimistic Locking)

```java
@Entity
public class Account {
    
    @Id
    private Long id;
    
    private BigDecimal balance;
    
    @Version
    private Long version; // auto-incremented on each UPDATE
    // Hibernate adds: WHERE id = ? AND version = ?
    // If row count = 0 → throws OptimisticLockException
}
```

**Supported types:** `int`, `Integer`, `long`, `Long`, `short`, `Short`, `Timestamp`

---

### Auditing: @CreatedDate, @LastModifiedDate, @CreatedBy

```java
@Configuration
@EnableJpaAuditing(auditorAwareRef = "auditorProvider")
public class JpaAuditConfig {
    
    @Bean
    public AuditorAware<String> auditorProvider() {
        return () -> Optional.ofNullable(SecurityContextHolder.getContext())
            .map(SecurityContext::getAuthentication)
            .filter(Authentication::isAuthenticated)
            .map(Authentication::getName);
    }
}

@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class AuditableEntity {
    
    @CreatedDate
    @Column(updatable = false)
    private LocalDateTime createdAt;
    
    @LastModifiedDate
    private LocalDateTime updatedAt;
    
    @CreatedBy
    @Column(updatable = false)
    private String createdBy;
    
    @LastModifiedBy
    private String updatedBy;
}
```

---

## 4. AOP Annotations

### @Aspect

**What it does internally:**
- Detected by `AnnotationAwareAspectJAutoProxyCreator` (a `BeanPostProcessor`)
- Weaves advice into matching beans at proxy creation time
- Uses Spring AOP (proxy-based) not AspectJ (compile-time/load-time weaving)

```java
@Aspect
@Component // Must also be a Spring bean
@Order(1) // execution order when multiple aspects match
public class LoggingAspect {
    
    private static final Logger log = LoggerFactory.getLogger(LoggingAspect.class);
    
    @Pointcut("execution(* com.example.service..*.*(..))")
    public void serviceMethods() {} // reusable pointcut
    
    @Before("serviceMethods()")
    public void logBefore(JoinPoint jp) {
        log.info("Calling: {}.{}({})", 
            jp.getTarget().getClass().getSimpleName(),
            jp.getSignature().getName(),
            Arrays.toString(jp.getArgs()));
    }
    
    @AfterReturning(pointcut = "serviceMethods()", returning = "result")
    public void logAfterReturning(JoinPoint jp, Object result) {
        log.info("Returned: {} from {}", result, jp.getSignature().getName());
    }
    
    @AfterThrowing(pointcut = "serviceMethods()", throwing = "ex")
    public void logAfterThrowing(JoinPoint jp, Exception ex) {
        log.error("Exception in {}: {}", jp.getSignature().getName(), ex.getMessage());
    }
    
    @After("serviceMethods()") // finally — runs regardless of outcome
    public void logAfter(JoinPoint jp) {
        log.debug("Completed: {}", jp.getSignature().getName());
    }
    
    @Around("serviceMethods()")
    public Object logAround(ProceedingJoinPoint pjp) throws Throwable {
        long start = System.nanoTime();
        try {
            Object result = pjp.proceed();
            return result;
        } finally {
            long duration = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);
            log.info("{}.{} took {}ms",
                pjp.getTarget().getClass().getSimpleName(),
                pjp.getSignature().getName(), duration);
        }
    }
}
```

---

### @Pointcut Expressions

```java
@Aspect
@Component
public class SecurityAspect {
    
    // Method execution in specific package
    @Pointcut("execution(* com.example.api..*Controller.*(..))")
    public void controllerMethods() {}
    
    // Any method with specific annotation
    @Pointcut("@annotation(com.example.annotation.Audited)")
    public void auditedMethods() {}
    
    // Any method in a class annotated with @Service
    @Pointcut("@within(org.springframework.stereotype.Service)")
    public void withinServices() {}
    
    // Methods with specific argument types
    @Pointcut("args(com.example.dto.OrderRequest,..)")
    public void methodsWithOrderRequest() {}
    
    // Bind annotation value
    @Around("@annotation(rateLimited)")
    public Object enforceRateLimit(ProceedingJoinPoint pjp, RateLimited rateLimited) throws Throwable {
        String key = rateLimited.key();
        int limit = rateLimited.requestsPerSecond();
        if (!rateLimiter.tryAcquire(key, limit)) {
            throw new RateLimitExceededException();
        }
        return pjp.proceed();
    }
    
    // Combining pointcuts
    @Pointcut("controllerMethods() && !auditedMethods()")
    public void unauditedControllerMethods() {}
    
    // execution pattern: execution(modifiers? return-type declaring-type? method-name(params) throws?)
    @Pointcut("execution(public * com.example..*Service.find*(..))")
    public void publicFindMethods() {}
    
    // within: limits to types
    @Pointcut("within(com.example.service..*)")
    public void inServicePackage() {}
    
    // this/target: proxy type / actual type
    @Pointcut("target(com.example.service.Auditable)")
    public void auditableTargets() {}
    
    // bean: Spring bean name pattern
    @Pointcut("bean(*Service)")
    public void anyServiceBean() {}
}
```

---

### @EnableAspectJAutoProxy

```java
@Configuration
@EnableAspectJAutoProxy(
    proxyTargetClass = true,  // force CGLIB (class-based) proxies
    exposeProxy = true        // allow AopContext.currentProxy() for self-invocation
)
public class AopConfig { }
```

**Spring Boot auto-configures this** — you rarely need it explicitly.

---

## 5. Async/Scheduling Annotations

### @Async and @EnableAsync

**What it does internally:**
- `AsyncAnnotationBeanPostProcessor` wraps the bean in a proxy
- Method calls are submitted to a `TaskExecutor` (thread pool)
- Returns immediately with a `Future`/`CompletableFuture`

```java
@Configuration
@EnableAsync
public class AsyncConfig implements AsyncConfigurer {
    
    @Override
    public Executor getAsyncExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-");
        executor.setRejectedExecutionHandler(new CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
    
    @Override
    public AsyncUncaughtExceptionHandler getAsyncUncaughtExceptionHandler() {
        return (throwable, method, params) -> 
            log.error("Async exception in {}: {}", method.getName(), throwable.getMessage());
    }
}

@Service
public class NotificationService {
    
    @Async
    public void sendEmailAsync(String to, String subject, String body) {
        // Runs in thread pool — caller doesn't wait
        emailClient.send(to, subject, body);
    }
    
    @Async
    public CompletableFuture<Report> generateReport(Long userId) {
        Report report = reportGenerator.generate(userId);
        return CompletableFuture.completedFuture(report);
    }
    
    @Async("customExecutor") // specific executor bean
    public void processWithCustomPool(Task task) { ... }
}
```

**Pitfalls:**
- Self-invocation bypasses proxy (same as `@Transactional`)
- `void` return: exceptions are lost unless you configure `AsyncUncaughtExceptionHandler`
- `@Async` + `@Transactional` on the same method: transaction starts in new thread (no propagation from caller)

---

### @Scheduled and @EnableScheduling

```java
@Configuration
@EnableScheduling
public class SchedulingConfig implements SchedulingConfigurer {
    
    @Override
    public void configureTasks(ScheduledTaskRegistrar registrar) {
        registrar.setScheduler(Executors.newScheduledThreadPool(5));
    }
}

@Component
public class ScheduledTasks {
    
    // Fixed rate: every 5 seconds regardless of execution time
    @Scheduled(fixedRate = 5000)
    public void pollExternalSystem() { ... }
    
    // Fixed delay: 5 seconds AFTER previous execution completes
    @Scheduled(fixedDelay = 5000, initialDelay = 10000)
    public void processQueue() { ... }
    
    // Cron: every day at 2 AM
    @Scheduled(cron = "0 0 2 * * *")
    public void dailyCleanup() { ... }
    
    // Externalized cron
    @Scheduled(cron = "${app.reporting.cron}")
    public void generateDailyReport() { ... }
    
    // Time zone
    @Scheduled(cron = "0 0 9 * * MON-FRI", zone = "America/New_York")
    public void businessHoursTask() { ... }
}
```

**Pitfall:** By default, scheduled tasks share a SINGLE thread. If one task blocks, others are delayed. Always configure a thread pool.

---

### @EventListener and @TransactionalEventListener

```java
// Publishing events
@Service
public class OrderService {
    
    private final ApplicationEventPublisher publisher;
    
    @Transactional
    public Order createOrder(OrderRequest req) {
        Order order = orderRepository.save(mapToOrder(req));
        publisher.publishEvent(new OrderCreatedEvent(order));
        return order;
    }
}

// Domain event
public record OrderCreatedEvent(Order order) {}

// Listener
@Component
public class OrderEventListener {
    
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        // Runs synchronously in same thread by default
        log.info("Order created: {}", event.order().getId());
    }
    
    @Async
    @EventListener
    public void handleOrderCreatedAsync(OrderCreatedEvent event) {
        // Runs asynchronously
        notificationService.notifyUser(event.order());
    }
    
    // Only runs AFTER the transaction commits successfully
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void afterOrderCommitted(OrderCreatedEvent event) {
        // Safe to send notifications — order is guaranteed persisted
        emailService.sendOrderConfirmation(event.order());
    }
    
    @TransactionalEventListener(phase = TransactionPhase.AFTER_ROLLBACK)
    public void afterOrderRollback(OrderCreatedEvent event) {
        log.warn("Order creation rolled back: {}", event.order().getId());
    }
    
    // Conditional listening
    @EventListener(condition = "#event.order().totalAmount > 1000")
    public void handleHighValueOrder(OrderCreatedEvent event) { ... }
    
    // Return value publishes a new event
    @EventListener
    public InventoryReservationEvent handleOrderForInventory(OrderCreatedEvent event) {
        return new InventoryReservationEvent(event.order().getItems());
    }
}
```

**`TransactionPhase` options:**
- `BEFORE_COMMIT`
- `AFTER_COMMIT` (default)
- `AFTER_ROLLBACK`
- `AFTER_COMPLETION` (commit or rollback)

**Pitfall:** `@TransactionalEventListener` with `AFTER_COMMIT` — if there's no active transaction, the listener is NOT called by default. Use `fallbackExecution = true` to always execute.

---

## 6. Validation Annotations

### JSR-380 Bean Validation

```java
public class CreateUserRequest {
    
    @NotNull(message = "Username is required")
    @Size(min = 3, max = 50, message = "Username must be 3-50 characters")
    @Pattern(regexp = "^[a-zA-Z0-9_]+$", message = "Username can only contain alphanumeric and underscore")
    private String username;
    
    @NotBlank(message = "Email is required")
    @Email(message = "Must be a valid email address")
    private String email;
    
    @NotNull
    @Min(value = 18, message = "Must be at least 18")
    @Max(value = 150)
    private Integer age;
    
    @NotEmpty(message = "At least one role required")
    private List<@NotBlank String> roles;
    
    @Past(message = "Birth date must be in the past")
    private LocalDate birthDate;
    
    @Future(message = "Expiry must be in the future")
    private LocalDateTime accountExpiry;
    
    @Positive
    private BigDecimal balance;
    
    @PositiveOrZero
    private int loginAttempts;
    
    @DecimalMin(value = "0.01")
    @DecimalMax(value = "999999.99")
    private BigDecimal salary;
    
    @Valid // cascading validation to nested object
    @NotNull
    private AddressDto address;
}

public class AddressDto {
    @NotBlank private String street;
    @NotBlank private String city;
    @Size(min = 5, max = 5) private String zipCode;
}
```

**Difference: `@NotNull` vs `@NotEmpty` vs `@NotBlank`:**
- `@NotNull`: value != null
- `@NotEmpty`: value != null AND not empty (size > 0) — for String, Collection, Map, Array
- `@NotBlank`: value != null AND trimmed length > 0 — String only

---

### @Valid vs @Validated

```java
@RestController
public class UserController {
    
    // @Valid — JSR-380 standard, triggers cascading validation
    @PostMapping("/users")
    public UserDto create(@Valid @RequestBody CreateUserRequest req) { ... }
    
    // @Validated — Spring extension, supports validation groups
    @PutMapping("/users/{id}")
    public UserDto update(@Validated(UpdateGroup.class) @RequestBody UpdateUserRequest req) { ... }
}

// Validation groups
public interface CreateGroup {}
public interface UpdateGroup {}

public class UserRequest {
    @Null(groups = CreateGroup.class)
    @NotNull(groups = UpdateGroup.class)
    private Long id;
    
    @NotBlank(groups = {CreateGroup.class, UpdateGroup.class})
    private String name;
}

// Method-level validation (service layer)
@Service
@Validated
public class UserService {
    public User findById(@NotNull @Positive Long id) { ... }
    public List<User> search(@Size(min = 2) String query) { ... }
}
```

---

### Custom Constraint Annotation

```java
@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = UniqueEmailValidator.class)
@Documented
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
        if (email == null) return true; // let @NotNull handle null
        return !userRepository.existsByEmail(email);
    }
}

// Cross-field validation
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = PasswordMatchValidator.class)
public @interface PasswordMatch {
    String message() default "Passwords do not match";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

@PasswordMatch
public class RegistrationForm {
    private String password;
    private String confirmPassword;
}
```

---

## 7. Security Annotations

### Method Security

```java
@Configuration
@EnableMethodSecurity // Spring Security 6+ (replaces @EnableGlobalMethodSecurity)
public class SecurityConfig { }

@Service
public class DocumentService {
    
    @PreAuthorize("hasRole('ADMIN')")
    public void deleteAll() { ... }
    
    @PreAuthorize("hasAuthority('document:read') and #userId == authentication.principal.id")
    public Document getDocument(Long userId, Long docId) { ... }
    
    // SpEL with bean reference
    @PreAuthorize("@documentSecurity.canAccess(authentication, #docId)")
    public Document getDocument(Long docId) { ... }
    
    @PostAuthorize("returnObject.owner == authentication.name")
    public Document findById(Long id) {
        // Executes method, then checks condition on return value
        return documentRepository.findById(id).orElseThrow();
    }
    
    @PreFilter("filterObject.tenantId == authentication.principal.tenantId")
    public void batchDelete(List<Document> documents) {
        // Only documents matching the filter are passed in
    }
    
    @PostFilter("filterObject.visibility == 'PUBLIC' or filterObject.owner == authentication.name")
    public List<Document> findAll() {
        return documentRepository.findAll();
    }
    
    // Old-style annotations (still work but less flexible)
    @Secured("ROLE_ADMIN")
    public void adminOnly() { ... }
    
    @RolesAllowed({"ADMIN", "MODERATOR"}) // JSR-250
    public void modAction() { ... }
}
```

---

### @EnableWebSecurity

```java
@Configuration
@EnableWebSecurity
public class WebSecurityConfig {
    
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

---

## 8. Testing Annotations

### @SpringBootTest

**What it does internally:**
- Finds `@SpringBootApplication` class and loads full application context
- Starts embedded server if `webEnvironment` is set

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OrderIntegrationTest {
    
    @Autowired
    private TestRestTemplate restTemplate;
    
    @LocalServerPort
    private int port;
    
    @Test
    void createOrder_returns201() {
        var request = new OrderRequest("item1", 2);
        var response = restTemplate.postForEntity("/api/orders", request, OrderResponse.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }
}
```

---

### @WebMvcTest

Loads only the web layer (controllers, filters, advice). No services, repos, etc.

```java
@WebMvcTest(OrderController.class)
class OrderControllerTest {
    
    @Autowired
    private MockMvc mockMvc;
    
    @MockBean
    private OrderService orderService;
    
    @Test
    void getOrder_returnsOrder() throws Exception {
        when(orderService.getOrder(1L)).thenReturn(new OrderDto(1L, "ORD-001", BigDecimal.TEN));
        
        mockMvc.perform(get("/api/orders/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.orderNumber").value("ORD-001"));
    }
}
```

---

### @DataJpaTest

Loads only JPA components. Auto-configures an embedded H2 database. Each test is transactional and rolls back.

```java
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE) // use real DB
class OrderRepositoryTest {
    
    @Autowired
    private OrderRepository orderRepository;
    
    @Autowired
    private TestEntityManager entityManager;
    
    @Test
    void findByStatus_returnsMatchingOrders() {
        entityManager.persist(new Order("ORD-1", OrderStatus.PENDING));
        entityManager.persist(new Order("ORD-2", OrderStatus.COMPLETED));
        entityManager.flush();
        
        List<Order> pending = orderRepository.findByStatus(OrderStatus.PENDING);
        assertThat(pending).hasSize(1);
    }
}
```

---

### @WebFluxTest

```java
@WebFluxTest(OrderController.class)
class OrderControllerWebFluxTest {
    
    @Autowired
    private WebTestClient webTestClient;
    
    @MockBean
    private OrderService orderService;
    
    @Test
    void getOrder_returnsOrder() {
        when(orderService.getOrder(1L)).thenReturn(Mono.just(new OrderDto(1L, "ORD-001")));
        
        webTestClient.get().uri("/api/orders/1")
            .exchange()
            .expectStatus().isOk()
            .expectBody(OrderDto.class)
            .value(dto -> assertThat(dto.orderNumber()).isEqualTo("ORD-001"));
    }
}
```

---

### @MockBean and @SpyBean

```java
@SpringBootTest
class PaymentServiceTest {
    
    @MockBean // replaces real bean in context with Mockito mock
    private PaymentGatewayClient gatewayClient;
    
    @SpyBean // wraps real bean — real methods unless stubbed
    private AuditService auditService;
    
    @Autowired
    private PaymentService paymentService;
    
    @Test
    void processPayment_callsGateway() {
        when(gatewayClient.charge(any())).thenReturn(new ChargeResult("txn-123"));
        
        paymentService.process(new PaymentRequest(100.00));
        
        verify(gatewayClient).charge(any());
        verify(auditService).logEvent(any()); // verify spy was called
    }
}
```

---

### @TestConfiguration

```java
@SpringBootTest
class ServiceTest {
    
    @TestConfiguration // does NOT prevent auto-detection of main config
    static class TestConfig {
        
        @Bean
        public ExternalClient externalClient() {
            return new FakeExternalClient(); // test double
        }
    }
    
    @Autowired
    private MyService myService;
}

// Or import explicitly
@SpringBootTest
@Import(ServiceTest.TestConfig.class)
class ServiceTest { ... }
```

---

### @AutoConfigureMockMvc

```java
@SpringBootTest
@AutoConfigureMockMvc
class FullStackMvcTest {
    
    @Autowired
    private MockMvc mockMvc; // full context but no HTTP server
    
    @Test
    void endToEnd() throws Exception {
        mockMvc.perform(post("/api/orders")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"product": "item1", "quantity": 2}
                    """))
            .andExpect(status().isCreated());
    }
}
```

---

## 9. Caching Annotations

### @EnableCaching

```java
@Configuration
@EnableCaching
public class CacheConfig {
    
    @Bean
    public CacheManager cacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager();
        manager.setCaffeine(Caffeine.newBuilder()
            .maximumSize(10_000)
            .expireAfterWrite(Duration.ofMinutes(10))
            .recordStats());
        return manager;
    }
}
```

---

### @Cacheable, @CachePut, @CacheEvict, @Caching

```java
@Service
public class ProductService {
    
    // Cache the result. Subsequent calls with same key skip the method.
    @Cacheable(value = "products", key = "#id")
    public Product getProduct(Long id) {
        return productRepository.findById(id).orElseThrow();
    }
    
    // Conditional caching
    @Cacheable(
        value = "products",
        key = "#id",
        unless = "#result.price < 10", // don't cache cheap products
        condition = "#id > 0"          // don't cache if id <= 0
    )
    public Product getProductConditional(Long id) { ... }
    
    // Custom key generator
    @Cacheable(value = "search", key = "#query + '_' + #page + '_' + #size")
    public Page<Product> search(String query, int page, int size) { ... }
    
    // Always execute method AND update cache
    @CachePut(value = "products", key = "#product.id")
    public Product updateProduct(Product product) {
        return productRepository.save(product);
    }
    
    // Remove from cache
    @CacheEvict(value = "products", key = "#id")
    public void deleteProduct(Long id) {
        productRepository.deleteById(id);
    }
    
    // Evict entire cache
    @CacheEvict(value = "products", allEntries = true)
    public void refreshAll() { }
    
    // Multiple cache operations
    @Caching(
        put = @CachePut(value = "products", key = "#result.id"),
        evict = @CacheEvict(value = "productList", allEntries = true)
    )
    public Product create(CreateProductRequest req) {
        return productRepository.save(mapToEntity(req));
    }
}
```

**Pitfalls:**
- Self-invocation bypasses cache proxy (same as `@Transactional`)
- Default key is all parameters — be careful with complex objects (need proper `hashCode`/`equals`)
- `@Cacheable` on void methods is useless

---

## 10. Spring Boot Specific

### @SpringBootApplication

**Composition:**
```java
@SpringBootConfiguration      // → @Configuration
@EnableAutoConfiguration       // triggers auto-config via spring.factories / AutoConfiguration.imports
@ComponentScan                 // scans current package and below
public @interface SpringBootApplication { }
```

```java
@SpringBootApplication(
    scanBasePackages = "com.example",
    exclude = {DataSourceAutoConfiguration.class}
)
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

---

### @EnableAutoConfiguration

**What it does internally:**
1. `AutoConfigurationImportSelector` (a `DeferredImportSelector`) is triggered
2. Reads `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` (Spring Boot 3.x) or `META-INF/spring.factories` (2.x)
3. Filters candidates based on `@Conditional*` annotations
4. Imports matching configuration classes

---

### @ConditionalOnClass / @ConditionalOnMissingBean / @ConditionalOnProperty

These are the backbone of auto-configuration:

```java
@AutoConfiguration
@ConditionalOnClass(DataSource.class)
@ConditionalOnProperty(prefix = "spring.datasource", name = "url")
public class DataSourceAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean
    public DataSource dataSource(DataSourceProperties properties) {
        return properties.initializeDataSourceBuilder().build();
    }
}

// Writing your own auto-configuration
@AutoConfiguration(
    after = DataSourceAutoConfiguration.class,
    before = FlywayAutoConfiguration.class
)
@ConditionalOnBean(DataSource.class)
@ConditionalOnClass(name = "com.example.MyLib")
@ConditionalOnProperty(
    prefix = "app.feature",
    name = "enabled",
    havingValue = "true",
    matchIfMissing = true // default behavior if property absent
)
public class MyLibAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean
    public MyLibService myLibService(DataSource dataSource) {
        return new MyLibService(dataSource);
    }
}
```

**Registration (Spring Boot 3.x):**
Create file: `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
```
com.example.autoconfigure.MyLibAutoConfiguration
```

---

### @AutoConfiguration, @AutoConfigureBefore, @AutoConfigureAfter

```java
@AutoConfiguration(
    after = {JacksonAutoConfiguration.class},
    before = {WebMvcAutoConfiguration.class}
)
public class CustomWebAutoConfiguration {
    // Guaranteed ordering relative to other auto-configurations
}
```

---

## Quick Reference: Common Pitfall Summary

| Pitfall | Affected Annotations | Solution |
|---|---|---|
| Self-invocation bypasses proxy | `@Transactional`, `@Async`, `@Cacheable` | Extract to separate bean or use `AopContext.currentProxy()` |
| Checked exceptions don't rollback | `@Transactional` | Add `rollbackFor = Exception.class` |
| N+1 queries | `@OneToMany`, `@ManyToOne` | Use `@EntityGraph` or join fetch |
| Prototype in singleton | `@Scope("prototype")` | Use `ObjectProvider` or `@Lookup` |
| `@Value` on static fields | `@Value` | Use setter injection or `@PostConstruct` |
| EAGER fetch on collections | `@OneToMany` default | Always set `fetch = FetchType.LAZY` |
| Single scheduler thread | `@Scheduled` | Configure `ScheduledTaskRegistrar` with thread pool |
| `@Async` void — lost exceptions | `@Async` | Return `CompletableFuture` or configure `AsyncUncaughtExceptionHandler` |
| `@Configuration` lite mode | Inter-bean method calls | Use `proxyBeanMethods = true` or inject via parameters |

---

## Interview Tips

1. **Explain proxy mechanism**: Most Spring magic works through proxies (JDK dynamic or CGLIB). Understanding this explains why self-invocation fails.

2. **Bean lifecycle order**: Constructor → `@PostConstruct` → `afterPropertiesSet()` → `initMethod` → Ready → `@PreDestroy` → `destroy()` → `destroyMethod`

3. **Auto-configuration**: Know the flow from `@EnableAutoConfiguration` → `ImportSelector` → condition evaluation → bean registration.

4. **Transaction propagation**: Draw the thread/transaction boundary for `REQUIRED` vs `REQUIRES_NEW` scenarios.

5. **`@Conditional` hierarchy**: All Spring Boot conditions extend `@Conditional`. Know how to write custom conditions.
