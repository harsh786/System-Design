# AOP, Caching, Profiles, Error Handling & Other Spring Boot Internals

## Table of Contents
1. [Aspect-Oriented Programming (AOP)](#aspect-oriented-programming-aop)
2. [Spring Cache Abstraction](#spring-cache-abstraction)
3. [Profiles & Environment](#profiles--environment)
4. [Error Handling & Exception Management](#error-handling--exception-management)
5. [Spring Boot Actuator](#spring-boot-actuator)
6. [Logging Configuration](#logging-configuration)
7. [Data Validation](#data-validation)
8. [Event System](#event-system)
9. [Interceptors & Filters](#interceptors--filters)
10. [Spring Boot DevTools & Hot Reload](#spring-boot-devtools--hot-reload)
11. [Configuration Externalization](#configuration-externalization)
12. [Spring Security Internals](#spring-security-internals)
13. [Spring Boot Testing Strategies](#spring-boot-testing-strategies)

---

## Aspect-Oriented Programming (AOP)

### How AOP Works in Spring

```
┌─────────────────────────────────────────────────────────────────┐
│                    AOP INTERNALS                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  AOP = Cross-cutting concerns applied WITHOUT modifying code     │
│                                                                   │
│  Examples: Logging, Security, Transactions, Metrics, Caching     │
│                                                                   │
│  HOW IT WORKS:                                                   │
│  1. You write an @Aspect class with advice methods               │
│  2. Spring detects beans matching your pointcut expressions      │
│  3. Spring creates PROXY for those beans                         │
│  4. Proxy intercepts method calls and executes advice            │
│                                                                   │
│  Caller → PROXY → Before Advice → TARGET METHOD → After Advice  │
│                                                                   │
│  Two proxy mechanisms:                                           │
│  - CGLIB (default): Creates subclass of target class             │
│  - JDK Dynamic: Creates implementation of target interface       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### AOP Terminology

```
┌─────────────────────────────────────────────────────────────┐
│  TERM          │ MEANING                                    │
├────────────────┼────────────────────────────────────────────┤
│  Aspect        │ Class that contains cross-cutting logic    │
│  Advice        │ The action taken (before, after, around)   │
│  Pointcut      │ Expression that matches join points        │
│  Join Point    │ A point during execution (method call)     │
│  Weaving       │ Process of applying aspects to targets     │
│  Target Object │ The original bean being proxied            │
│  Proxy         │ The object created by AOP framework        │
└────────────────┴────────────────────────────────────────────┘
```

### Complete AOP Examples

```java
@Aspect
@Component
@Order(1) // Lower number = higher priority (runs first)
public class LoggingAspect {
    
    private static final Logger log = LoggerFactory.getLogger(LoggingAspect.class);
    
    // ===== POINTCUT EXPRESSIONS =====
    
    // All methods in service package
    @Pointcut("execution(* com.example.service.*.*(..))")
    public void serviceLayer() {}
    
    // All methods annotated with @Loggable
    @Pointcut("@annotation(com.example.annotation.Loggable)")
    public void loggable() {}
    
    // All public methods
    @Pointcut("execution(public * *(..))")
    public void publicMethods() {}
    
    // Methods with specific return type
    @Pointcut("execution(com.example.model.Order com.example.service.*.*(..))")
    public void orderReturningMethods() {}
    
    // ===== ADVICE TYPES =====
    
    // BEFORE: Runs before method execution
    @Before("serviceLayer()")
    public void logMethodEntry(JoinPoint joinPoint) {
        String method = joinPoint.getSignature().getName();
        Object[] args = joinPoint.getArgs();
        log.info("Entering: {}({})", method, Arrays.toString(args));
    }
    
    // AFTER RETURNING: Runs after successful return
    @AfterReturning(pointcut = "serviceLayer()", returning = "result")
    public void logMethodReturn(JoinPoint joinPoint, Object result) {
        log.info("Method {} returned: {}", 
            joinPoint.getSignature().getName(), result);
    }
    
    // AFTER THROWING: Runs after exception
    @AfterThrowing(pointcut = "serviceLayer()", throwing = "ex")
    public void logException(JoinPoint joinPoint, Exception ex) {
        log.error("Method {} threw: {}", 
            joinPoint.getSignature().getName(), ex.getMessage());
    }
    
    // AFTER (finally): Runs always (success or exception)
    @After("serviceLayer()")
    public void logMethodExit(JoinPoint joinPoint) {
        log.debug("Exiting: {}", joinPoint.getSignature().getName());
    }
    
    // AROUND: Full control (most powerful)
    @Around("serviceLayer()")
    public Object logAround(ProceedingJoinPoint pjp) throws Throwable {
        String method = pjp.getSignature().toShortString();
        long start = System.currentTimeMillis();
        
        log.info(">>> {}", method);
        try {
            Object result = pjp.proceed(); // Call actual method
            long elapsed = System.currentTimeMillis() - start;
            log.info("<<< {} completed in {}ms", method, elapsed);
            return result;
        } catch (Exception e) {
            long elapsed = System.currentTimeMillis() - start;
            log.error("<<< {} failed in {}ms: {}", method, elapsed, e.getMessage());
            throw e;
        }
    }
}
```

### Custom Annotation-Based AOP

```java
// 1. Define custom annotation
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface RateLimit {
    int value() default 100;        // Max calls
    int period() default 60;        // Period in seconds
    String key() default "";        // Rate limit key
}

// 2. Create aspect
@Aspect
@Component
public class RateLimitAspect {
    
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();
    
    @Around("@annotation(rateLimit)")
    public Object enforceRateLimit(ProceedingJoinPoint pjp, RateLimit rateLimit) throws Throwable {
        String key = resolveKey(pjp, rateLimit);
        Bucket bucket = buckets.computeIfAbsent(key, k -> createBucket(rateLimit));
        
        if (bucket.tryConsume(1)) {
            return pjp.proceed();
        } else {
            throw new RateLimitExceededException("Rate limit exceeded for: " + key);
        }
    }
    
    private Bucket createBucket(RateLimit rateLimit) {
        return Bucket.builder()
            .addLimit(Bandwidth.classic(rateLimit.value(), 
                Refill.intervally(rateLimit.value(), Duration.ofSeconds(rateLimit.period()))))
            .build();
    }
}

// 3. Use it
@RestController
public class ApiController {
    
    @RateLimit(value = 10, period = 60, key = "createOrder")
    @PostMapping("/orders")
    public Order createOrder(@RequestBody OrderRequest request) { ... }
}
```

### AOP Execution Order

```
┌────────────────────────────────────────────────────────────────┐
│  EXECUTION ORDER WITH MULTIPLE ASPECTS                          │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  @Order(1): SecurityAspect                                      │
│  @Order(2): LoggingAspect                                       │
│  @Order(3): MetricsAspect                                       │
│                                                                  │
│  Execution flow:                                                │
│                                                                  │
│  SecurityAspect.before()                                        │
│    └── LoggingAspect.before()                                   │
│          └── MetricsAspect.before()                             │
│                └── TARGET METHOD                                │
│          └── MetricsAspect.after()                              │
│    └── LoggingAspect.after()                                    │
│  SecurityAspect.after()                                         │
│                                                                  │
│  Like nested function calls (onion model)                       │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## Spring Cache Abstraction

### Cache Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 SPRING CACHE ABSTRACTION                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Application Code                                                │
│       │                                                          │
│       ▼                                                          │
│  Spring Cache Annotations (@Cacheable, @CacheEvict, etc.)       │
│       │                                                          │
│       ▼                                                          │
│  CacheManager (interface)                                        │
│       │                                                          │
│       ├── ConcurrentMapCacheManager (simple, in-memory)          │
│       ├── CaffeineCacheManager (high-performance local)          │
│       ├── RedisCacheManager (distributed)                        │
│       ├── EhCacheCacheManager (local with overflow to disk)      │
│       └── CompositeCacheManager (chain multiple)                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration

```java
@Configuration
@EnableCaching
public class CacheConfig {
    
    // Option 1: Redis (distributed, shared across instances)
    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory factory) {
        RedisCacheConfiguration defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(10))
            .serializeKeysWith(SerializationPair.fromSerializer(new StringRedisSerializer()))
            .serializeValuesWith(SerializationPair.fromSerializer(
                new GenericJackson2JsonRedisSerializer()))
            .disableCachingNullValues();
        
        Map<String, RedisCacheConfiguration> cacheConfigs = Map.of(
            "users", defaultConfig.entryTtl(Duration.ofMinutes(30)),
            "products", defaultConfig.entryTtl(Duration.ofHours(1)),
            "config", defaultConfig.entryTtl(Duration.ofHours(24))
        );
        
        return RedisCacheManager.builder(factory)
            .cacheDefaults(defaultConfig)
            .withInitialCacheConfigurations(cacheConfigs)
            .transactionAware() // Commits cache ops with DB transaction
            .build();
    }
    
    // Option 2: Caffeine (local, per-instance, very fast)
    @Bean
    public CaffeineCacheManager localCacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager();
        manager.setCaffeine(Caffeine.newBuilder()
            .initialCapacity(100)
            .maximumSize(10_000)
            .expireAfterWrite(Duration.ofMinutes(5))
            .expireAfterAccess(Duration.ofMinutes(2))
            .weakValues() // Allow GC to collect cached values
            .recordStats()); // Enable statistics
        return manager;
    }
}
```

### Cache Usage Patterns

```java
@Service
public class ProductService {
    
    // Basic caching
    @Cacheable(value = "products", key = "#id")
    public Product findById(Long id) {
        log.info("DB hit for product {}", id); // Only logs on cache miss
        return productRepo.findById(id).orElseThrow();
    }
    
    // Conditional caching
    @Cacheable(value = "products", key = "#id", 
               condition = "#id > 0",           // Don't cache if id <= 0
               unless = "#result.price == 0")    // Don't cache free products
    public Product findByIdConditional(Long id) {
        return productRepo.findById(id).orElseThrow();
    }
    
    // Cache with complex key
    @Cacheable(value = "productSearch", key = "#category + '-' + #page + '-' + #size")
    public Page<Product> search(String category, int page, int size) {
        return productRepo.findByCategory(category, PageRequest.of(page, size));
    }
    
    // Custom key generator
    @Cacheable(value = "products", keyGenerator = "customKeyGenerator")
    public List<Product> findByFilters(ProductFilter filter) {
        return productRepo.findByFilters(filter);
    }
    
    // Update cache on save
    @CachePut(value = "products", key = "#product.id")
    public Product save(Product product) {
        return productRepo.save(product);
    }
    
    // Evict on delete
    @CacheEvict(value = "products", key = "#id")
    public void delete(Long id) {
        productRepo.deleteById(id);
    }
    
    // Evict all entries
    @CacheEvict(value = "products", allEntries = true)
    @Scheduled(fixedRate = 3600000) // Every hour
    public void evictAllProducts() {
        log.info("Evicting all product cache");
    }
    
    // Multiple cache operations
    @Caching(
        cacheable = @Cacheable(value = "products", key = "#id"),
        evict = @CacheEvict(value = "productList", allEntries = true)
    )
    public Product findAndRefreshList(Long id) {
        return productRepo.findById(id).orElseThrow();
    }
}
```

### Cache Gotchas

```java
// GOTCHA 1: Self-invocation bypasses cache (same as @Transactional)
@Service
public class ProductService {
    @Cacheable("products")
    public Product findById(Long id) { ... }
    
    public Product getProductDetails(Long id) {
        return findById(id); // BYPASSES CACHE! Self-invocation.
    }
}

// GOTCHA 2: Caching null values
@Cacheable(value = "users", unless = "#result == null")
public User findById(Long id) {
    return userRepo.findById(id).orElse(null); // null NOT cached
}

// GOTCHA 3: Cache key collisions
// Two methods with same cache name and same key type:
@Cacheable("data")
public User findUser(Long id) { ... }   // key = 1

@Cacheable("data")
public Product findProduct(Long id) { ... } // key = 1 → COLLISION!

// Fix: Use different cache names or include method name in key

// GOTCHA 4: Mutable cached objects
@Cacheable("users")
public User findById(Long id) {
    return userRepo.findById(id).orElseThrow();
}

// Caller modifies the cached reference!
User user = findById(1L);
user.setName("Modified"); // This MODIFIES the cached object!
// Next call to findById(1) returns the modified version!
// Fix: Return copies or use immutable objects
```

---

## Profiles & Environment

### Profile Activation

```yaml
# application.yml (common config)
spring:
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev}
    group:
      production: proddb, prodcache, monitoring
      development: devdb, devcache

---
# application-dev.yml
server:
  port: 8080
spring:
  datasource:
    url: jdbc:h2:mem:devdb
  jpa:
    show-sql: true
    hibernate:
      ddl-auto: create-drop
logging:
  level:
    com.example: DEBUG
    org.hibernate.SQL: DEBUG

---
# application-production.yml
server:
  port: 8443
  ssl:
    enabled: true
spring:
  datasource:
    url: jdbc:postgresql://prod-db:5432/myapp
    hikari:
      maximum-pool-size: 30
  jpa:
    show-sql: false
    hibernate:
      ddl-auto: validate
logging:
  level:
    com.example: WARN
```

### Profile-Specific Beans

```java
@Configuration
public class StorageConfig {
    
    @Bean
    @Profile("dev")
    public StorageService localStorageService() {
        return new LocalFileStorageService("/tmp/uploads");
    }
    
    @Bean
    @Profile("production")
    public StorageService s3StorageService(S3Client s3Client) {
        return new S3StorageService(s3Client, "prod-bucket");
    }
    
    @Bean
    @Profile("test")
    public StorageService mockStorageService() {
        return new InMemoryStorageService();
    }
}

// Profile as a condition
@Component
@Profile("!production") // Active in ALL profiles EXCEPT production
public class DataSeeder implements CommandLineRunner {
    @Override
    public void run(String... args) {
        // Seed test data
    }
}
```

### Environment Abstraction

```java
@Component
public class EnvironmentAwareService {
    
    @Autowired
    private Environment environment;
    
    public void doSomething() {
        // Check active profiles
        if (environment.acceptsProfiles(Profiles.of("production"))) {
            // Production-specific logic
        }
        
        // Get property with default
        String apiUrl = environment.getProperty("api.url", "http://localhost:8080");
        
        // Get required property (throws if missing)
        String secret = environment.getRequiredProperty("app.secret");
        
        // Type-safe property
        int timeout = environment.getProperty("app.timeout", Integer.class, 5000);
    }
}
```

---

## Error Handling & Exception Management

### Global Exception Handling

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {
    
    // Validation errors (400)
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiError> handleValidation(MethodArgumentNotValidException ex) {
        List<FieldError> fieldErrors = ex.getBindingResult().getFieldErrors().stream()
            .map(error -> new FieldError(error.getField(), error.getDefaultMessage()))
            .toList();
        
        ApiError error = ApiError.builder()
            .status(HttpStatus.BAD_REQUEST.value())
            .code("VALIDATION_ERROR")
            .message("Request validation failed")
            .fieldErrors(fieldErrors)
            .timestamp(Instant.now())
            .build();
        
        return ResponseEntity.badRequest().body(error);
    }
    
    // Resource not found (404)
    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ApiError> handleNotFound(ResourceNotFoundException ex) {
        ApiError error = ApiError.builder()
            .status(HttpStatus.NOT_FOUND.value())
            .code("RESOURCE_NOT_FOUND")
            .message(ex.getMessage())
            .timestamp(Instant.now())
            .build();
        
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
    }
    
    // Business logic errors (422)
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiError> handleBusiness(BusinessException ex) {
        ApiError error = ApiError.builder()
            .status(HttpStatus.UNPROCESSABLE_ENTITY.value())
            .code(ex.getErrorCode())
            .message(ex.getMessage())
            .timestamp(Instant.now())
            .build();
        
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY).body(error);
    }
    
    // Duplicate resource (409)
    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ApiError> handleDuplicate(DataIntegrityViolationException ex) {
        ApiError error = ApiError.builder()
            .status(HttpStatus.CONFLICT.value())
            .code("DUPLICATE_RESOURCE")
            .message("Resource already exists")
            .timestamp(Instant.now())
            .build();
        
        return ResponseEntity.status(HttpStatus.CONFLICT).body(error);
    }
    
    // Catch-all (500)
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleGeneral(Exception ex, WebRequest request) {
        log.error("Unhandled exception for request: {}", request.getDescription(false), ex);
        
        ApiError error = ApiError.builder()
            .status(HttpStatus.INTERNAL_SERVER_ERROR.value())
            .code("INTERNAL_ERROR")
            .message("An unexpected error occurred") // Don't expose internals!
            .timestamp(Instant.now())
            .build();
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
    }
}

// Error response structure
@Builder
public record ApiError(
    int status,
    String code,
    String message,
    List<FieldError> fieldErrors,
    Instant timestamp,
    String traceId
) {}

public record FieldError(String field, String message) {}
```

### Custom Exception Hierarchy

```java
// Base exception
public abstract class BaseException extends RuntimeException {
    private final String errorCode;
    private final HttpStatus httpStatus;
    
    protected BaseException(String message, String errorCode, HttpStatus httpStatus) {
        super(message);
        this.errorCode = errorCode;
        this.httpStatus = httpStatus;
    }
}

// Specific exceptions
public class ResourceNotFoundException extends BaseException {
    public ResourceNotFoundException(String resource, Object id) {
        super(String.format("%s not found with id: %s", resource, id),
              "RESOURCE_NOT_FOUND", HttpStatus.NOT_FOUND);
    }
}

public class BusinessRuleException extends BaseException {
    public BusinessRuleException(String message) {
        super(message, "BUSINESS_RULE_VIOLATION", HttpStatus.UNPROCESSABLE_ENTITY);
    }
}

public class InsufficientFundsException extends BusinessRuleException {
    public InsufficientFundsException(BigDecimal required, BigDecimal available) {
        super(String.format("Insufficient funds. Required: %s, Available: %s", required, available));
    }
}
```

### Problem Details (RFC 7807) - Spring Boot 3

```java
@Configuration
public class ProblemDetailsConfig {
    // Spring Boot 3 supports RFC 7807 out of the box
}

@RestControllerAdvice
public class ProblemDetailsExceptionHandler extends ResponseEntityExceptionHandler {
    
    @ExceptionHandler(ResourceNotFoundException.class)
    public ProblemDetail handleNotFound(ResourceNotFoundException ex) {
        ProblemDetail problem = ProblemDetail.forStatus(HttpStatus.NOT_FOUND);
        problem.setTitle("Resource Not Found");
        problem.setDetail(ex.getMessage());
        problem.setProperty("errorCode", "RESOURCE_NOT_FOUND");
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }
}

// Response:
// {
//   "type": "about:blank",
//   "title": "Resource Not Found",
//   "status": 404,
//   "detail": "User not found with id: 123",
//   "instance": "/api/users/123",
//   "errorCode": "RESOURCE_NOT_FOUND",
//   "timestamp": "2024-01-15T10:30:00Z"
// }
```

---

## Spring Boot Actuator

### Setup & Endpoints

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus,env,loggers,threaddump,heapdump
      base-path: /actuator
  endpoint:
    health:
      show-details: when_authorized
      show-components: always
      probes:
        enabled: true
    shutdown:
      enabled: true  # POST /actuator/shutdown to stop app
  metrics:
    export:
      prometheus:
        enabled: true
    distribution:
      percentiles-histogram:
        http.server.requests: true
      percentiles:
        http.server.requests: 0.5,0.95,0.99
```

### Key Actuator Endpoints

```
GET /actuator/health          → Application health status
GET /actuator/health/liveness → Kubernetes liveness probe
GET /actuator/health/readiness→ Kubernetes readiness probe
GET /actuator/info            → Application information
GET /actuator/metrics         → All available metrics
GET /actuator/metrics/http.server.requests → HTTP request metrics
GET /actuator/env             → Environment properties
GET /actuator/loggers         → Logger levels
POST /actuator/loggers/com.example → Change log level at runtime
GET /actuator/threaddump      → Current thread states
GET /actuator/heapdump        → Heap dump (large file!)
GET /actuator/prometheus      → Prometheus-format metrics
```

### Custom Health Indicator

```java
@Component
public class DatabaseHealthIndicator implements HealthIndicator {
    
    private final DataSource dataSource;
    
    @Override
    public Health health() {
        try (Connection conn = dataSource.getConnection()) {
            if (conn.isValid(2)) {
                return Health.up()
                    .withDetail("database", "PostgreSQL")
                    .withDetail("connection_pool", getPoolStats())
                    .build();
            }
        } catch (SQLException e) {
            return Health.down()
                .withDetail("error", e.getMessage())
                .build();
        }
        return Health.down().build();
    }
}

@Component
public class ExternalServiceHealthIndicator implements HealthIndicator {
    
    private final RestClient restClient;
    
    @Override
    public Health health() {
        try {
            ResponseEntity<Void> response = restClient.get()
                .uri("https://api.external.com/health")
                .retrieve()
                .toBodilessEntity();
            
            if (response.getStatusCode().is2xxSuccessful()) {
                return Health.up().build();
            }
            return Health.down()
                .withDetail("status", response.getStatusCode())
                .build();
        } catch (Exception e) {
            return Health.down()
                .withException(e)
                .build();
        }
    }
}
```

### Custom Metrics

```java
@Component
public class BusinessMetrics {
    
    private final Counter orderCounter;
    private final Timer orderProcessingTimer;
    private final AtomicInteger activeOrders;
    private final DistributionSummary orderAmountSummary;
    
    public BusinessMetrics(MeterRegistry registry) {
        this.orderCounter = Counter.builder("business.orders.total")
            .description("Total orders processed")
            .tag("type", "all")
            .register(registry);
        
        this.orderProcessingTimer = Timer.builder("business.orders.processing_time")
            .description("Order processing duration")
            .publishPercentiles(0.5, 0.95, 0.99)
            .publishPercentileHistogram()
            .register(registry);
        
        this.activeOrders = registry.gauge("business.orders.active",
            new AtomicInteger(0));
        
        this.orderAmountSummary = DistributionSummary.builder("business.orders.amount")
            .description("Order amounts")
            .baseUnit("dollars")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(registry);
    }
    
    public void recordOrder(Order order, Duration processingTime) {
        orderCounter.increment();
        orderProcessingTimer.record(processingTime);
        orderAmountSummary.record(order.getTotal().doubleValue());
    }
}
```

---

## Logging Configuration

### Logback Configuration (Default)

```xml
<!-- logback-spring.xml (Spring Boot enhanced) -->
<configuration>
    <!-- Use Spring profiles in logback config -->
    <springProfile name="dev">
        <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
            <encoder>
                <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
            </encoder>
        </appender>
        <root level="DEBUG">
            <appender-ref ref="CONSOLE" />
        </root>
    </springProfile>
    
    <springProfile name="production">
        <!-- Structured JSON logging for production -->
        <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
            <encoder class="net.logstash.logback.encoder.LogstashEncoder">
                <customFields>{"service":"order-service","env":"production"}</customFields>
            </encoder>
        </appender>
        
        <!-- Async appender for performance -->
        <appender name="ASYNC" class="ch.qos.logback.classic.AsyncAppender">
            <appender-ref ref="JSON" />
            <queueSize>512</queueSize>
            <discardingThreshold>0</discardingThreshold>
            <includeCallerData>false</includeCallerData>
        </appender>
        
        <root level="WARN">
            <appender-ref ref="ASYNC" />
        </root>
        <logger name="com.example" level="INFO" />
    </springProfile>
</configuration>
```

### MDC (Mapped Diagnostic Context) for Request Tracing

```java
@Component
public class RequestTracingFilter extends OncePerRequestFilter {
    
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        String traceId = request.getHeader("X-Trace-Id");
        if (traceId == null) {
            traceId = UUID.randomUUID().toString();
        }
        
        MDC.put("traceId", traceId);
        MDC.put("userId", extractUserId(request));
        MDC.put("requestPath", request.getRequestURI());
        
        response.setHeader("X-Trace-Id", traceId);
        
        try {
            chain.doFilter(request, response);
        } finally {
            MDC.clear(); // MUST clear - thread pool reuse!
        }
    }
}

// In logback pattern:
// %d{ISO8601} [%X{traceId}] [%X{userId}] %level %logger - %msg%n
// Output: 2024-01-15T10:30:00 [abc-123] [user-456] INFO OrderService - Order created
```

---

## Data Validation

### Bean Validation with Custom Validators

```java
// DTO with validation
public record CreateOrderRequest(
    @NotNull(message = "Customer ID is required")
    Long customerId,
    
    @NotEmpty(message = "At least one item required")
    @Size(max = 50, message = "Maximum 50 items per order")
    List<@Valid OrderItemRequest> items,
    
    @ValidAddress // Custom annotation
    AddressDTO shippingAddress,
    
    @FutureOrPresent(message = "Delivery date must be in the future")
    LocalDate requestedDeliveryDate
) {}

public record OrderItemRequest(
    @NotNull Long productId,
    @Min(1) @Max(999) int quantity,
    @Positive BigDecimal unitPrice
) {}

// Custom validator
@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = AddressValidator.class)
public @interface ValidAddress {
    String message() default "Invalid address";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class AddressValidator implements ConstraintValidator<ValidAddress, AddressDTO> {
    @Override
    public boolean isValid(AddressDTO address, ConstraintValidatorContext context) {
        if (address == null) return true; // Use @NotNull separately
        
        boolean valid = true;
        
        if (isBlank(address.street())) {
            context.buildConstraintViolationWithTemplate("Street is required")
                .addPropertyNode("street").addConstraintViolation();
            valid = false;
        }
        
        if (isBlank(address.zipCode()) || !address.zipCode().matches("\\d{5}(-\\d{4})?")) {
            context.buildConstraintViolationWithTemplate("Invalid ZIP code")
                .addPropertyNode("zipCode").addConstraintViolation();
            valid = false;
        }
        
        if (!valid) {
            context.disableDefaultConstraintViolation();
        }
        return valid;
    }
}
```

### Validation Groups

```java
// Different validation rules for create vs update
public interface CreateValidation {}
public interface UpdateValidation {}

public class UserDTO {
    @Null(groups = CreateValidation.class)      // Must be null on create
    @NotNull(groups = UpdateValidation.class)    // Must exist on update
    private Long id;
    
    @NotBlank(groups = {CreateValidation.class, UpdateValidation.class})
    private String name;
    
    @NotBlank(groups = CreateValidation.class)   // Required only on create
    private String password;
}

@RestController
public class UserController {
    @PostMapping("/users")
    public User create(@Validated(CreateValidation.class) @RequestBody UserDTO dto) { ... }
    
    @PutMapping("/users/{id}")
    public User update(@Validated(UpdateValidation.class) @RequestBody UserDTO dto) { ... }
}
```

---

## Event System

### Application Events Deep Dive

```java
// Custom events
public class OrderEvent extends ApplicationEvent {
    private final Order order;
    private final OrderAction action;
    
    public OrderEvent(Object source, Order order, OrderAction action) {
        super(source);
        this.order = order;
        this.action = action;
    }
}

// Or using record (Spring 5.3+, no need to extend ApplicationEvent)
public record OrderCreatedEvent(Long orderId, Long userId, BigDecimal amount, Instant timestamp) {}

// Publishing
@Service
public class OrderService {
    private final ApplicationEventPublisher publisher;
    
    @Transactional
    public Order createOrder(OrderRequest request) {
        Order order = orderRepo.save(new Order(request));
        publisher.publishEvent(new OrderCreatedEvent(
            order.getId(), order.getUserId(), order.getTotal(), Instant.now()));
        return order;
    }
}

// Synchronous listener (runs in SAME thread & transaction)
@Component
public class InventoryListener {
    @EventListener
    @Order(1) // Priority
    public void reserveInventory(OrderCreatedEvent event) {
        // Runs synchronously, in same transaction as publisher
        // If this throws, publisher's transaction rolls back!
    }
}

// Async listener (separate thread, separate transaction)
@Component
public class EmailListener {
    @Async
    @EventListener
    public void sendConfirmation(OrderCreatedEvent event) {
        // Different thread, different transaction
        // Publisher doesn't wait for this
    }
}

// Transactional event listener
@Component
public class AnalyticsListener {
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void trackOrder(OrderCreatedEvent event) {
        // ONLY runs if publisher's transaction successfully commits
        // Runs in separate transaction
    }
    
    @TransactionalEventListener(phase = TransactionPhase.AFTER_ROLLBACK)
    public void handleFailedOrder(OrderCreatedEvent event) {
        // Runs only if transaction rolled back
    }
}
```

### Built-in Spring Events

```java
@Component
public class AppLifecycleListener {
    
    @EventListener(ApplicationStartedEvent.class)
    public void onStarted() {
        log.info("Application started - context refreshed, beans created");
    }
    
    @EventListener(ApplicationReadyEvent.class)
    public void onReady() {
        log.info("Application ready - runners executed, accepting traffic");
    }
    
    @EventListener(ContextClosedEvent.class)
    public void onShutdown() {
        log.info("Application shutting down");
    }
    
    @EventListener(ApplicationFailedEvent.class)
    public void onFailed(ApplicationFailedEvent event) {
        log.error("Application failed to start", event.getException());
    }
}
```

---

## Interceptors & Filters

### Filter vs Interceptor vs AOP

```
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST PROCESSING LAYERS                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  HTTP Request                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌── SERVLET FILTER ───────────────────────────────┐            │
│  │  - Lowest level                                  │            │
│  │  - Works with ServletRequest/Response            │            │
│  │  - Can modify request/response                   │            │
│  │  - Runs BEFORE DispatcherServlet                 │            │
│  │  - Use for: Auth, CORS, Logging, Compression     │            │
│  └──────────────────────────────────────────────────┘            │
│       │                                                          │
│       ▼                                                          │
│  ┌── HANDLER INTERCEPTOR ─────────────────────────┐             │
│  │  - Spring MVC level                             │             │
│  │  - Has access to handler (controller method)    │             │
│  │  - preHandle / postHandle / afterCompletion     │             │
│  │  - Can access ModelAndView                      │             │
│  │  - Use for: Auth, Logging, Locale, Tenant       │             │
│  └──────────────────────────────────────────────────┘            │
│       │                                                          │
│       ▼                                                          │
│  ┌── CONTROLLER (AOP can intercept here) ─────────┐             │
│  │  @PreAuthorize, @Valid, handler method           │             │
│  └──────────────────────────────────────────────────┘            │
│       │                                                          │
│       ▼                                                          │
│  ┌── SERVICE (AOP typical target) ─────────────────┐            │
│  │  @Transactional, @Cacheable, @Async              │            │
│  └──────────────────────────────────────────────────┘            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Filter Implementation

```java
@Component
@Order(1) // Lower = runs first
public class RequestLoggingFilter extends OncePerRequestFilter {
    
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        long startTime = System.currentTimeMillis();
        String requestId = UUID.randomUUID().toString().substring(0, 8);
        
        // Wrap response to capture status
        ContentCachingResponseWrapper wrappedResponse = 
            new ContentCachingResponseWrapper(response);
        
        try {
            chain.doFilter(request, wrappedResponse);
        } finally {
            long duration = System.currentTimeMillis() - startTime;
            log.info("[{}] {} {} → {} ({}ms)",
                requestId,
                request.getMethod(),
                request.getRequestURI(),
                wrappedResponse.getStatus(),
                duration);
            wrappedResponse.copyBodyToResponse();
        }
    }
    
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // Skip filtering for actuator endpoints
        return request.getRequestURI().startsWith("/actuator");
    }
}
```

### Interceptor Implementation

```java
@Component
public class TenantInterceptor implements HandlerInterceptor {
    
    @Override
    public boolean preHandle(HttpServletRequest request, 
                             HttpServletResponse response, 
                             Object handler) throws Exception {
        String tenantId = request.getHeader("X-Tenant-Id");
        
        if (tenantId == null) {
            response.setStatus(HttpStatus.BAD_REQUEST.value());
            response.getWriter().write("Missing X-Tenant-Id header");
            return false; // Stop processing
        }
        
        TenantContext.setCurrentTenant(tenantId);
        return true; // Continue to controller
    }
    
    @Override
    public void postHandle(HttpServletRequest request, 
                           HttpServletResponse response,
                           Object handler, ModelAndView modelAndView) {
        // After controller, before view rendering
    }
    
    @Override
    public void afterCompletion(HttpServletRequest request, 
                                HttpServletResponse response,
                                Object handler, Exception ex) {
        // Always runs (even on exception) - cleanup
        TenantContext.clear();
    }
}

// Register interceptor
@Configuration
public class WebConfig implements WebMvcConfigurer {
    
    @Autowired
    private TenantInterceptor tenantInterceptor;
    
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(tenantInterceptor)
            .addPathPatterns("/api/**")
            .excludePathPatterns("/api/public/**", "/api/health");
    }
}
```

---

## Configuration Externalization

### @ConfigurationProperties Deep Dive

```java
@ConfigurationProperties(prefix = "app")
@Validated
public class AppProperties {
    
    @NotBlank
    private String name;
    
    @Valid
    private Server server = new Server();
    
    @Valid
    private Security security = new Security();
    
    private Map<String, ServiceConfig> services = new HashMap<>();
    
    // Nested classes
    public static class Server {
        @Min(1) @Max(65535)
        private int port = 8080;
        
        @DurationUnit(ChronoUnit.SECONDS)
        private Duration timeout = Duration.ofSeconds(30);
        
        @DataSizeUnit(DataUnit.MEGABYTES)
        private DataSize maxUploadSize = DataSize.ofMegabytes(10);
    }
    
    public static class Security {
        private boolean enabled = true;
        private String jwtSecret;
        
        @DurationUnit(ChronoUnit.HOURS)
        private Duration tokenExpiration = Duration.ofHours(24);
        
        private List<String> allowedOrigins = List.of("*");
    }
    
    public static class ServiceConfig {
        private String url;
        private Duration timeout = Duration.ofSeconds(5);
        private int maxRetries = 3;
    }
    
    // Getters and setters...
}
```

```yaml
# application.yml
app:
  name: MyApp
  server:
    port: 8080
    timeout: 30s
    max-upload-size: 10MB
  security:
    enabled: true
    jwt-secret: ${JWT_SECRET}
    token-expiration: 24h
    allowed-origins:
      - https://example.com
      - https://app.example.com
  services:
    payment:
      url: https://payment.internal
      timeout: 5s
      max-retries: 3
    inventory:
      url: https://inventory.internal
      timeout: 3s
      max-retries: 2
```

### Configuration Immutability (Constructor Binding)

```java
@ConfigurationProperties(prefix = "app.mail")
public record MailProperties(
    @NotBlank String host,
    @Min(1) @Max(65535) int port,
    String username,
    String password,
    @DefaultValue("TLS") String protocol,
    @DefaultValue("true") boolean starttls
) {
    // Record is immutable by default - best practice!
}
```

---

## Spring Security Internals

### Security Filter Chain

```
┌─────────────────────────────────────────────────────────────────┐
│              SECURITY FILTER CHAIN (Ordered)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. SecurityContextPersistenceFilter                             │
│     └── Loads SecurityContext from session/storage               │
│                                                                   │
│  2. HeaderWriterFilter                                           │
│     └── Adds security headers (X-Frame-Options, etc.)           │
│                                                                   │
│  3. CorsFilter                                                   │
│     └── Handles CORS preflight and headers                      │
│                                                                   │
│  4. CsrfFilter                                                   │
│     └── Validates CSRF token                                    │
│                                                                   │
│  5. LogoutFilter                                                 │
│     └── Processes /logout requests                              │
│                                                                   │
│  6. UsernamePasswordAuthenticationFilter                         │
│     └── Form login processing                                   │
│                                                                   │
│  7. BearerTokenAuthenticationFilter                              │
│     └── JWT/OAuth2 token validation                             │
│                                                                   │
│  8. RequestCacheAwareFilter                                      │
│     └── Restores saved request after auth                       │
│                                                                   │
│  9. SecurityContextHolderAwareRequestFilter                      │
│     └── Wraps request with security methods                     │
│                                                                   │
│  10. AnonymousAuthenticationFilter                               │
│      └── Creates anonymous auth if none exists                  │
│                                                                   │
│  11. SessionManagementFilter                                     │
│      └── Session fixation, concurrent session control           │
│                                                                   │
│  12. ExceptionTranslationFilter                                  │
│      └── Translates security exceptions to HTTP responses       │
│                                                                   │
│  13. AuthorizationFilter (FilterSecurityInterceptor)             │
│      └── Final access decision (permit/deny)                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### JWT Authentication Flow

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.GET, "/api/products/**").permitAll()
                .anyRequest().authenticated())
            .addFilterBefore(jwtAuthFilter(), UsernamePasswordAuthenticationFilter.class)
            .build();
    }
}

@Component
public class JwtAuthFilter extends OncePerRequestFilter {
    
    private final JwtService jwtService;
    private final UserDetailsService userDetailsService;
    
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        
        if (header == null || !header.startsWith("Bearer ")) {
            chain.doFilter(request, response);
            return;
        }
        
        String token = header.substring(7);
        String username = jwtService.extractUsername(token);
        
        if (username != null && SecurityContextHolder.getContext().getAuthentication() == null) {
            UserDetails userDetails = userDetailsService.loadUserByUsername(username);
            
            if (jwtService.isTokenValid(token, userDetails)) {
                UsernamePasswordAuthenticationToken authToken =
                    new UsernamePasswordAuthenticationToken(
                        userDetails, null, userDetails.getAuthorities());
                authToken.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                SecurityContextHolder.getContext().setAuthentication(authToken);
            }
        }
        
        chain.doFilter(request, response);
    }
}
```

---

## Spring Boot Testing Strategies

### Testing Pyramid

```
┌─────────────────────────────────────────────────────────┐
│              SPRING BOOT TESTING PYRAMID                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│               /\                                         │
│              /  \     E2E Tests                          │
│             / @  \    @SpringBootTest + TestContainers   │
│            /  ST  \   Full application context           │
│           /────────\                                     │
│          /          \   Integration Tests               │
│         / @WebMvcTest\  @DataJpaTest                    │
│        / @RestClientTest                                │
│       /────────────────\                                │
│      /                  \  Unit Tests                   │
│     /   Mockito + JUnit  \ No Spring context            │
│    /  Fast, isolated tests \                            │
│   /──────────────────────────\                          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Test Slices

```java
// @WebMvcTest - Tests ONLY web layer
@WebMvcTest(OrderController.class)
class OrderControllerTest {
    @Autowired MockMvc mockMvc;
    @MockBean OrderService orderService; // Mock service layer
    
    @Test
    void shouldReturn404WhenOrderNotFound() throws Exception {
        when(orderService.findById(999L)).thenThrow(new ResourceNotFoundException("Order", 999L));
        
        mockMvc.perform(get("/api/orders/999"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
    }
}

// @DataJpaTest - Tests ONLY JPA/repository layer
@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE) // Use real DB (TestContainers)
class OrderRepositoryTest {
    @Autowired TestEntityManager em;
    @Autowired OrderRepository orderRepo;
    
    @Test
    void shouldFindByStatus() {
        em.persist(new Order("item1", OrderStatus.PENDING));
        em.persist(new Order("item2", OrderStatus.COMPLETED));
        
        List<Order> pending = orderRepo.findByStatus(OrderStatus.PENDING);
        assertThat(pending).hasSize(1);
    }
}

// @SpringBootTest - Full integration test
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@Testcontainers
class OrderIntegrationTest {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");
    
    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }
    
    @Autowired TestRestTemplate restTemplate;
    
    @Test
    void shouldCreateAndRetrieveOrder() {
        // Full round-trip test
        ResponseEntity<Order> createResponse = restTemplate.postForEntity(
            "/api/orders", new OrderRequest("item1", 2), Order.class);
        assertThat(createResponse.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        
        Long orderId = createResponse.getBody().getId();
        ResponseEntity<Order> getResponse = restTemplate.getForEntity(
            "/api/orders/" + orderId, Order.class);
        assertThat(getResponse.getBody().getStatus()).isEqualTo(OrderStatus.PENDING);
    }
}
```

---

## Spring Boot DevTools & Hot Reload

### How DevTools Works

```yaml
# DevTools auto-configures:
# - Automatic restart on classpath changes
# - LiveReload for browser refresh
# - Disables template caching
# - H2 console enabled

spring:
  devtools:
    restart:
      enabled: true
      exclude: static/**,public/**  # Don't restart for static files
      poll-interval: 1s
      quiet-period: 400ms
    livereload:
      enabled: true
```

### Two ClassLoader Trick

```
┌──────────────────────────────────────────────────────────┐
│  DEVTOOLS RESTART MECHANISM                               │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Base ClassLoader (doesn't restart):                     │
│  ├── JDK classes                                         │
│  ├── Spring Framework                                    │
│  ├── Third-party libraries                               │
│  └── Stays in memory → fast restart                      │
│                                                           │
│  Restart ClassLoader (thrown away & recreated):           │
│  ├── Your application classes                            │
│  ├── Discarded on file change                            │
│  └── New classloader created → loads your new classes    │
│                                                           │
│  Result: ~1-3 second restart vs 10-30 second cold start  │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

## Summary: How Everything Connects

```
┌─────────────────────────────────────────────────────────────────────┐
│              SPRING BOOT REQUEST LIFECYCLE (COMPLETE)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. CLIENT sends HTTP request                                        │
│                                                                       │
│  2. TOMCAT accepts connection (NIO), assigns worker thread           │
│                                                                       │
│  3. FILTER CHAIN executes (security, CORS, logging)                  │
│                                                                       │
│  4. DISPATCHER SERVLET routes to controller                          │
│                                                                       │
│  5. INTERCEPTOR preHandle (tenant, auth checks)                      │
│                                                                       │
│  6. ARGUMENT RESOLUTION (@PathVariable, @RequestBody, @Valid)        │
│                                                                       │
│  7. SECURITY CHECK (@PreAuthorize via AOP)                           │
│                                                                       │
│  8. CONTROLLER method invoked                                        │
│                                                                       │
│  9. SERVICE method called → AOP PROXY intercepts:                    │
│     a. @Transactional → Open transaction (get DB connection)         │
│     b. @Cacheable → Check cache first                                │
│     c. Custom aspects (logging, metrics)                             │
│                                                                       │
│  10. REPOSITORY executes query (using transactional connection)      │
│                                                                       │
│  11. Transaction COMMITS (or ROLLS BACK on exception)                │
│                                                                       │
│  12. RESPONSE serialized (Jackson → JSON)                            │
│                                                                       │
│  13. INTERCEPTOR postHandle                                          │
│                                                                       │
│  14. RESPONSE written to client                                      │
│                                                                       │
│  15. INTERCEPTOR afterCompletion (cleanup)                           │
│                                                                       │
│  16. Worker thread RETURNED to Tomcat pool                           │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```
