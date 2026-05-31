# Design Patterns & Architecture for Staff Engineer/Architect Interviews

## Table of Contents
- [1. GoF Patterns in Spring Boot](#1-gof-patterns-in-spring-boot)
- [2. Enterprise Integration Patterns](#2-enterprise-integration-patterns)
- [3. Architectural Patterns](#3-architectural-patterns)
- [4. Spring-Specific Patterns](#4-spring-specific-patterns)
- [5. Architecture Decision Records](#5-architecture-decision-records)

---

## 1. GoF Patterns in Spring Boot

### 1.1 Singleton Pattern

**Problem:** Ensure a class has only one instance and provide global access to it.

**Spring Boot Implementation:**
Spring's default bean scope is singleton — one instance per ApplicationContext. Spring manages this via the IoC container, not through the classic double-checked locking.

```java
// Spring singleton (preferred) - container manages lifecycle
@Service
public class CacheService {
    private final ConcurrentHashMap<String, Object> cache = new ConcurrentHashMap<>();
    
    public void put(String key, Object value) { cache.put(key, value); }
    public Object get(String key) { return cache.get(key); }
}

// Classic double-checked locking (rare in Spring, used for non-bean singletons)
public class ExpensiveResource {
    private static volatile ExpensiveResource instance;
    
    private ExpensiveResource() { /* heavy initialization */ }
    
    public static ExpensiveResource getInstance() {
        if (instance == null) {
            synchronized (ExpensiveResource.class) {
                if (instance == null) {
                    instance = new ExpensiveResource();
                }
            }
        }
        return instance;
    }
}

// Enum singleton (safest for non-Spring contexts)
public enum ConnectionRegistry {
    INSTANCE;
    
    private final Map<String, Connection> connections = new ConcurrentHashMap<>();
    
    public void register(String id, Connection conn) { connections.put(id, conn); }
    public Connection get(String id) { return connections.get(id); }
}
```

**When to use:**
- Shared resources (connection pools, caches, configuration holders)
- Stateless services (Spring's default — most `@Service`, `@Repository`, `@Component`)

**When to avoid:**
- When bean holds mutable per-request state (use `@Scope("request")` or `@Scope("prototype")`)
- Testing becomes harder if singleton has hidden state

**Real-world:** HikariCP connection pool, Spring's `ApplicationContext` itself, metrics registries.

---

### 1.2 Factory Pattern

**Problem:** Decouple object creation from usage. Allow runtime selection of implementations.

**Spring Boot Implementation:**

```java
// 1. FactoryBean - Spring's factory abstraction
public class PaymentProcessorFactoryBean implements FactoryBean<PaymentProcessor> {
    private String type;
    
    @Override
    public PaymentProcessor getObject() {
        return switch (type) {
            case "stripe" -> new StripeProcessor();
            case "paypal" -> new PayPalProcessor();
            case "square" -> new SquareProcessor();
            default -> throw new IllegalArgumentException("Unknown type: " + type);
        };
    }
    
    @Override
    public Class<?> getObjectType() { return PaymentProcessor.class; }
    
    public void setType(String type) { this.type = type; }
}

// 2. Abstract Factory with Spring (Strategy + Factory)
public interface NotificationFactory {
    Notification create(NotificationRequest request);
    boolean supports(NotificationType type);
}

@Component
public class EmailNotificationFactory implements NotificationFactory {
    private final EmailClient emailClient;
    
    public EmailNotificationFactory(EmailClient emailClient) {
        this.emailClient = emailClient;
    }
    
    @Override
    public Notification create(NotificationRequest request) {
        return new EmailNotification(emailClient, request.getRecipient(), request.getBody());
    }
    
    @Override
    public boolean supports(NotificationType type) {
        return type == NotificationType.EMAIL;
    }
}

@Component
public class SmsNotificationFactory implements NotificationFactory {
    private final SmsGateway gateway;
    
    public SmsNotificationFactory(SmsGateway gateway) { this.gateway = gateway; }
    
    @Override
    public Notification create(NotificationRequest request) {
        return new SmsNotification(gateway, request.getPhone(), request.getBody());
    }
    
    @Override
    public boolean supports(NotificationType type) {
        return type == NotificationType.SMS;
    }
}

// 3. Factory registry using Spring's DI
@Component
public class NotificationDispatcher {
    private final List<NotificationFactory> factories;
    
    public NotificationDispatcher(List<NotificationFactory> factories) {
        this.factories = factories;
    }
    
    public Notification dispatch(NotificationRequest request) {
        return factories.stream()
            .filter(f -> f.supports(request.getType()))
            .findFirst()
            .orElseThrow(() -> new UnsupportedOperationException(
                "No factory for: " + request.getType()))
            .create(request);
    }
}
```

**When to use:**
- Multiple implementations selected at runtime
- Complex object creation logic that shouldn't leak into business code
- Plugin architectures

**When to avoid:**
- Simple cases where `@Qualifier` suffices
- Over-engineering when there's only one implementation

**Real-world:** `BeanFactory` in Spring, `SessionFactory` in Hibernate, `ConnectionFactory` in JMS.

---

### 1.3 Builder Pattern

**Problem:** Construct complex objects step-by-step, separate construction from representation.

```java
// Configuration builder
@ConfigurationProperties(prefix = "retry")
public class RetryConfig {
    private int maxAttempts;
    private Duration backoff;
    private Set<Class<? extends Throwable>> retryableExceptions;
    
    // Standard getters/setters for Spring binding
    
    // Builder for programmatic use
    public static Builder builder() { return new Builder(); }
    
    public static class Builder {
        private int maxAttempts = 3;
        private Duration backoff = Duration.ofSeconds(1);
        private Set<Class<? extends Throwable>> retryableExceptions = new HashSet<>();
        
        public Builder maxAttempts(int maxAttempts) {
            this.maxAttempts = maxAttempts;
            return this;
        }
        
        public Builder backoff(Duration backoff) {
            this.backoff = backoff;
            return this;
        }
        
        public Builder retryOn(Class<? extends Throwable> ex) {
            this.retryableExceptions.add(ex);
            return this;
        }
        
        public RetryConfig build() {
            RetryConfig config = new RetryConfig();
            config.maxAttempts = this.maxAttempts;
            config.backoff = this.backoff;
            config.retryableExceptions = Collections.unmodifiableSet(this.retryableExceptions);
            return config;
        }
    }
}

// API Response builder
public class ApiResponse<T> {
    private final int status;
    private final T data;
    private final String message;
    private final Map<String, String> metadata;
    private final Instant timestamp;
    
    private ApiResponse(Builder<T> builder) {
        this.status = builder.status;
        this.data = builder.data;
        this.message = builder.message;
        this.metadata = Collections.unmodifiableMap(builder.metadata);
        this.timestamp = Instant.now();
    }
    
    public static <T> Builder<T> builder() { return new Builder<>(); }
    
    public static class Builder<T> {
        private int status = 200;
        private T data;
        private String message;
        private Map<String, String> metadata = new HashMap<>();
        
        public Builder<T> status(int status) { this.status = status; return this; }
        public Builder<T> data(T data) { this.data = data; return this; }
        public Builder<T> message(String message) { this.message = message; return this; }
        public Builder<T> meta(String key, String value) { 
            this.metadata.put(key, value); return this; 
        }
        public ApiResponse<T> build() { return new ApiResponse<>(this); }
    }
}

// Usage with WebClient (Spring's built-in builder pattern)
@Bean
public WebClient webClient(WebClient.Builder builder) {
    return builder
        .baseUrl("https://api.example.com")
        .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
        .filter(ExchangeFilterFunction.ofRequestProcessor(req -> {
            log.debug("Request: {} {}", req.method(), req.url());
            return Mono.just(req);
        }))
        .build();
}
```

**When to use:** Objects with many optional parameters, immutable objects, fluent APIs, configuration.

**When to avoid:** Simple objects with few fields (just use constructor).

**Real-world:** `WebClient.Builder`, `UriComponentsBuilder`, `RestTemplateBuilder`, `SecurityFilterChain` builder.

---

### 1.4 Proxy Pattern

**Problem:** Provide a surrogate to control access to another object (lazy loading, security, transactions, caching).

**Spring Boot Implementation:**

Spring AOP is built entirely on the Proxy pattern:
- **JDK Dynamic Proxy**: Used when target implements an interface. Creates a proxy implementing the same interface.
- **CGLIB Proxy**: Used when target has no interface. Creates a subclass at runtime.

```java
// Transaction proxy (Spring does this automatically)
@Service
public class OrderService {
    
    @Transactional // Spring creates a proxy that wraps this method
    public Order placeOrder(OrderRequest request) {
        Order order = new Order(request);
        orderRepository.save(order);
        inventoryService.reserve(order.getItems());
        paymentService.charge(order.getTotal());
        return order;
    }
}

// What Spring generates conceptually:
public class OrderService$$EnhancerBySpringCGLIB extends OrderService {
    private final TransactionInterceptor txInterceptor;
    private final OrderService target;
    
    @Override
    public Order placeOrder(OrderRequest request) {
        TransactionStatus status = txInterceptor.beginTransaction();
        try {
            Order result = target.placeOrder(request);
            txInterceptor.commit(status);
            return result;
        } catch (Exception e) {
            txInterceptor.rollback(status);
            throw e;
        }
    }
}

// Custom AOP proxy for cross-cutting concerns
@Aspect
@Component
public class PerformanceMonitorAspect {
    
    @Around("@annotation(monitored)")
    public Object monitor(ProceedingJoinPoint pjp, Monitored monitored) throws Throwable {
        String name = monitored.value().isEmpty() ? 
            pjp.getSignature().toShortString() : monitored.value();
        
        Timer.Sample sample = Timer.start();
        try {
            Object result = pjp.proceed();
            sample.stop(Timer.builder(name)
                .tag("status", "success")
                .register(meterRegistry));
            return result;
        } catch (Exception e) {
            sample.stop(Timer.builder(name)
                .tag("status", "error")
                .tag("exception", e.getClass().getSimpleName())
                .register(meterRegistry));
            throw e;
        }
    }
}

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface Monitored {
    String value() default "";
}

// JDK Dynamic Proxy example (manual)
public class CachingInvocationHandler implements InvocationHandler {
    private final Object target;
    private final Cache cache;
    
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        if (method.isAnnotationPresent(Cacheable.class)) {
            String key = generateKey(method, args);
            Object cached = cache.get(key);
            if (cached != null) return cached;
            Object result = method.invoke(target, args);
            cache.put(key, result);
            return result;
        }
        return method.invoke(target, args);
    }
}
```

**Key pitfall:** Self-invocation bypass — calling `this.method()` within the same class bypasses the proxy. Solution: inject self or use `AopContext.currentProxy()`.

```java
@Service
public class UserService {
    @Lazy @Autowired private UserService self; // inject proxy
    
    public void createUser(UserRequest req) {
        User user = mapToUser(req);
        self.saveAndNotify(user); // goes through proxy - @Transactional works
    }
    
    @Transactional
    public void saveAndNotify(User user) {
        userRepository.save(user);
        eventPublisher.publish(new UserCreatedEvent(user));
    }
}
```

**When to use:** Cross-cutting concerns (transactions, caching, security, logging, metrics).

**When to avoid:** When the proxy overhead matters in tight loops (rare in web apps).

**Real-world:** `@Transactional`, `@Cacheable`, `@Async`, `@PreAuthorize`, `@Retryable`.

---

### 1.5 Template Method Pattern

**Problem:** Define the skeleton of an algorithm, letting subclasses override specific steps without changing the overall structure.

```java
// Spring's JdbcTemplate is the classic example
@Repository
public class UserJdbcRepository {
    private final JdbcTemplate jdbcTemplate;
    
    public List<User> findByStatus(String status) {
        return jdbcTemplate.query(
            "SELECT * FROM users WHERE status = ?",
            (rs, rowNum) -> new User(
                rs.getLong("id"),
                rs.getString("name"),
                rs.getString("email"),
                rs.getString("status")
            ),
            status
        );
    }
}

// Custom template method for data import
public abstract class DataImportTemplate<T> {
    
    // Template method - defines the skeleton
    public final ImportResult execute(InputStream source) {
        List<T> rawRecords = parse(source);
        List<T> validated = rawRecords.stream()
            .filter(this::validate)
            .toList();
        List<T> transformed = validated.stream()
            .map(this::transform)
            .toList();
        int saved = persist(transformed);
        postProcess(saved);
        return new ImportResult(rawRecords.size(), validated.size(), saved);
    }
    
    protected abstract List<T> parse(InputStream source);
    protected abstract boolean validate(T record);
    protected abstract T transform(T record);
    protected abstract int persist(List<T> records);
    
    // Hook method - optional override
    protected void postProcess(int savedCount) {
        // default: do nothing
    }
}

@Component
public class CsvUserImport extends DataImportTemplate<UserRecord> {
    private final UserRepository userRepository;
    
    @Override
    protected List<UserRecord> parse(InputStream source) {
        return new CsvParser<>(UserRecord.class).parse(source);
    }
    
    @Override
    protected boolean validate(UserRecord record) {
        return record.getEmail() != null && record.getEmail().contains("@");
    }
    
    @Override
    protected UserRecord transform(UserRecord record) {
        record.setEmail(record.getEmail().toLowerCase().trim());
        return record;
    }
    
    @Override
    protected int persist(List<UserRecord> records) {
        return userRepository.saveAll(records).size();
    }
    
    @Override
    protected void postProcess(int savedCount) {
        log.info("Imported {} users, sending welcome emails", savedCount);
    }
}

// TransactionTemplate - programmatic transaction management
@Service
public class TransferService {
    private final TransactionTemplate txTemplate;
    
    public TransferResult transfer(TransferRequest request) {
        return txTemplate.execute(status -> {
            Account from = accountRepo.findForUpdate(request.getFromId());
            Account to = accountRepo.findForUpdate(request.getToId());
            
            if (from.getBalance().compareTo(request.getAmount()) < 0) {
                status.setRollbackOnly();
                return TransferResult.insufficientFunds();
            }
            
            from.debit(request.getAmount());
            to.credit(request.getAmount());
            accountRepo.save(from);
            accountRepo.save(to);
            return TransferResult.success();
        });
    }
}
```

**When to use:** Common algorithm structure with varying steps, framework code that users extend.

**When to avoid:** When composition (Strategy pattern) would be simpler and more flexible.

**Real-world:** `JdbcTemplate`, `RestTemplate`, `TransactionTemplate`, `AbstractRoutingDataSource`.

---

### 1.6 Observer Pattern

**Problem:** Define a one-to-many dependency so that when one object changes state, all dependents are notified.

```java
// Spring's ApplicationEvent system
public class OrderPlacedEvent extends ApplicationEvent {
    private final Order order;
    
    public OrderPlacedEvent(Object source, Order order) {
        super(source);
        this.order = order;
    }
    
    public Order getOrder() { return order; }
}

// Publishing
@Service
@RequiredArgsConstructor
public class OrderService {
    private final ApplicationEventPublisher publisher;
    
    @Transactional
    public Order placeOrder(OrderRequest request) {
        Order order = createOrder(request);
        orderRepository.save(order);
        publisher.publishEvent(new OrderPlacedEvent(this, order));
        return order;
    }
}

// Listening - multiple independent observers
@Component
public class InventoryEventHandler {
    
    @EventListener
    public void onOrderPlaced(OrderPlacedEvent event) {
        inventoryService.reserve(event.getOrder().getItems());
    }
}

@Component
public class NotificationEventHandler {
    
    @EventListener
    public void onOrderPlaced(OrderPlacedEvent event) {
        emailService.sendOrderConfirmation(event.getOrder());
    }
}

@Component
public class AnalyticsEventHandler {
    
    @Async // Non-blocking observer
    @EventListener
    public void onOrderPlaced(OrderPlacedEvent event) {
        analyticsService.trackOrder(event.getOrder());
    }
}

// Transactional event listener - fires after commit
@Component
public class PaymentEventHandler {
    
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onOrderPlaced(OrderPlacedEvent event) {
        paymentService.initiateCharge(event.getOrder());
    }
}

// Reactive Observer with Project Reactor
@Component
public class ReactiveOrderProcessor {
    private final Sinks.Many<OrderEvent> orderSink = 
        Sinks.many().multicast().onBackpressureBuffer();
    
    public void publishOrder(OrderEvent event) {
        orderSink.tryEmitNext(event);
    }
    
    public Flux<OrderEvent> getOrderStream() {
        return orderSink.asFlux();
    }
    
    @PostConstruct
    public void setupSubscribers() {
        orderSink.asFlux()
            .filter(e -> e.getType() == OrderEventType.PLACED)
            .flatMap(this::processNewOrder)
            .subscribe();
    }
}
```

**When to use:** Decoupling event producers from consumers, plugins, audit logging, notifications.

**When to avoid:** When you need guaranteed ordering or transactional consistency across listeners.

**Real-world:** Spring events, Kafka consumers, WebSocket push, SSE streams.

---

### 1.7 Strategy Pattern

**Problem:** Define a family of algorithms, encapsulate each one, and make them interchangeable.

```java
// Strategy interface
public interface PricingStrategy {
    BigDecimal calculatePrice(Order order);
    boolean supports(CustomerTier tier);
}

@Component
public class StandardPricingStrategy implements PricingStrategy {
    @Override
    public BigDecimal calculatePrice(Order order) {
        return order.getItems().stream()
            .map(item -> item.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())))
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }
    
    @Override
    public boolean supports(CustomerTier tier) {
        return tier == CustomerTier.STANDARD;
    }
}

@Component
public class PremiumPricingStrategy implements PricingStrategy {
    private static final BigDecimal DISCOUNT = new BigDecimal("0.85"); // 15% off
    
    @Override
    public BigDecimal calculatePrice(Order order) {
        BigDecimal base = order.getItems().stream()
            .map(item -> item.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())))
            .reduce(BigDecimal.ZERO, BigDecimal::add);
        return base.multiply(DISCOUNT);
    }
    
    @Override
    public boolean supports(CustomerTier tier) {
        return tier == CustomerTier.PREMIUM;
    }
}

// Strategy selection via Spring DI
@Service
public class PricingService {
    private final Map<CustomerTier, PricingStrategy> strategies;
    
    public PricingService(List<PricingStrategy> strategyList) {
        this.strategies = strategyList.stream()
            .collect(Collectors.toMap(
                s -> Arrays.stream(CustomerTier.values())
                    .filter(s::supports).findFirst().orElseThrow(),
                Function.identity()
            ));
    }
    
    public BigDecimal calculatePrice(Order order, CustomerTier tier) {
        PricingStrategy strategy = strategies.get(tier);
        if (strategy == null) {
            throw new IllegalArgumentException("No pricing strategy for tier: " + tier);
        }
        return strategy.calculatePrice(order);
    }
}

// Strategy with @Qualifier for explicit selection
@Service
public class FileStorageService {
    private final StorageStrategy strategy;
    
    public FileStorageService(
            @Qualifier("s3Storage") StorageStrategy strategy) {
        this.strategy = strategy;
    }
}
```

**When to use:** Multiple algorithms/behaviors selectable at runtime, replacing complex conditionals.

**When to avoid:** Only one algorithm exists — don't over-abstract prematurely.

**Real-world:** Authentication strategies, serialization formats, compression algorithms, rate limiting algorithms.

---

### 1.8 Decorator Pattern

**Problem:** Attach additional responsibilities to an object dynamically, without modifying its class.

```java
// BeanPostProcessor - Spring's decorator mechanism
@Component
public class LoggingBeanPostProcessor implements BeanPostProcessor {
    
    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        if (bean instanceof DataService) {
            return createLoggingProxy((DataService) bean);
        }
        return bean;
    }
    
    private DataService createLoggingProxy(DataService target) {
        return new DataService() {
            @Override
            public Data fetch(String id) {
                log.info("Fetching data: {}", id);
                Data result = target.fetch(id);
                log.info("Fetched data: {} bytes", result.size());
                return result;
            }
        };
    }
}

// Classic decorator chain
public interface MessageSender {
    void send(Message message);
}

@Component("baseSender")
public class BasicMessageSender implements MessageSender {
    @Override
    public void send(Message message) {
        transport.deliver(message);
    }
}

public class EncryptingMessageSender implements MessageSender {
    private final MessageSender delegate;
    private final EncryptionService encryption;
    
    @Override
    public void send(Message message) {
        Message encrypted = encryption.encrypt(message);
        delegate.send(encrypted);
    }
}

public class CompressingMessageSender implements MessageSender {
    private final MessageSender delegate;
    
    @Override
    public void send(Message message) {
        Message compressed = compress(message);
        delegate.send(compressed);
    }
}

// Wire decorators with Spring config
@Configuration
public class MessagingConfig {
    
    @Bean
    @Primary
    public MessageSender messageSender(
            @Qualifier("baseSender") MessageSender base,
            EncryptionService encryption) {
        return new CompressingMessageSender(
            new EncryptingMessageSender(base, encryption)
        );
    }
}

// Servlet Filter as decorator
@Component
@Order(1)
public class RequestTimingFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
            HttpServletResponse response, FilterChain chain) throws Exception {
        long start = System.nanoTime();
        try {
            chain.doFilter(request, response); // delegate to next
        } finally {
            long duration = System.nanoTime() - start;
            response.addHeader("X-Response-Time", duration / 1_000_000 + "ms");
        }
    }
}
```

**When to use:** Adding behavior without modifying existing code, composable transformations.

**When to avoid:** When a simple subclass or AOP aspect is clearer.

**Real-world:** Servlet filters, `BufferedInputStream`, Spring Security filter chain, HTTP client interceptors.

---

### 1.9 Chain of Responsibility

**Problem:** Pass a request along a chain of handlers. Each handler decides to process or pass it along.

```java
// Spring Security Filter Chain is the canonical example
// Custom handler chain for request validation
public interface ValidationHandler {
    ValidationResult handle(Request request, ValidationChain chain);
}

public class ValidationChain {
    private final List<ValidationHandler> handlers;
    private int index = 0;
    
    public ValidationChain(List<ValidationHandler> handlers) {
        this.handlers = handlers;
    }
    
    public ValidationResult next(Request request) {
        if (index >= handlers.size()) {
            return ValidationResult.success();
        }
        return handlers.get(index++).handle(request, this);
    }
}

@Component
@Order(1)
public class AuthenticationHandler implements ValidationHandler {
    @Override
    public ValidationResult handle(Request request, ValidationChain chain) {
        if (!isAuthenticated(request)) {
            return ValidationResult.failure("Unauthenticated");
        }
        return chain.next(request); // pass to next handler
    }
}

@Component
@Order(2)
public class RateLimitHandler implements ValidationHandler {
    @Override
    public ValidationResult handle(Request request, ValidationChain chain) {
        if (isRateLimited(request.getClientId())) {
            return ValidationResult.failure("Rate limited");
        }
        return chain.next(request);
    }
}

@Component
@Order(3)
public class InputSanitizationHandler implements ValidationHandler {
    @Override
    public ValidationResult handle(Request request, ValidationChain chain) {
        request.sanitize();
        return chain.next(request);
    }
}

// Spring MVC Interceptor chain
@Component
public class AuditInterceptor implements HandlerInterceptor {
    
    @Override
    public boolean preHandle(HttpServletRequest request, 
            HttpServletResponse response, Object handler) {
        request.setAttribute("startTime", System.currentTimeMillis());
        return true; // continue chain
    }
    
    @Override
    public void afterCompletion(HttpServletRequest request, 
            HttpServletResponse response, Object handler, Exception ex) {
        long start = (Long) request.getAttribute("startTime");
        auditLog.record(request.getRequestURI(), System.currentTimeMillis() - start);
    }
}
```

**When to use:** Multiple handlers that may or may not process a request, middleware pipelines.

**When to avoid:** When processing order doesn't matter (use Observer instead).

**Real-world:** Spring Security `FilterChainProxy`, servlet filter chain, Spring MVC interceptors, Netty pipeline.

---

### 1.10 Adapter Pattern

**Problem:** Convert the interface of one class into another interface clients expect.

```java
// HandlerAdapter in Spring MVC - adapts various handler types to common interface
// Spring provides: RequestMappingHandlerAdapter, SimpleControllerHandlerAdapter, etc.

// Custom adapter: Legacy system integration
public interface ModernPaymentGateway {
    PaymentResult charge(PaymentRequest request);
    PaymentResult refund(String transactionId, BigDecimal amount);
}

// Legacy third-party SDK with incompatible interface
public class LegacyPaymentSDK {
    public int processPayment(String cardNum, int amountCents, String currency) { ... }
    public int reverseTransaction(int txnId, int amountCents) { ... }
}

@Component
public class LegacyPaymentAdapter implements ModernPaymentGateway {
    private final LegacyPaymentSDK sdk;
    
    @Override
    public PaymentResult charge(PaymentRequest request) {
        int amountCents = request.getAmount()
            .multiply(BigDecimal.valueOf(100)).intValue();
        int txnId = sdk.processPayment(
            request.getCardNumber(), amountCents, request.getCurrency());
        return txnId > 0 
            ? PaymentResult.success(String.valueOf(txnId))
            : PaymentResult.failure("Payment declined");
    }
    
    @Override
    public PaymentResult refund(String transactionId, BigDecimal amount) {
        int amountCents = amount.multiply(BigDecimal.valueOf(100)).intValue();
        int result = sdk.reverseTransaction(
            Integer.parseInt(transactionId), amountCents);
        return result > 0 
            ? PaymentResult.success(transactionId)
            : PaymentResult.failure("Refund failed");
    }
}

// MessageConverter as adapter
@Component
public class ProtobufHttpMessageConverter extends AbstractHttpMessageConverter<Message> {
    
    @Override
    protected boolean supports(Class<?> clazz) {
        return Message.class.isAssignableFrom(clazz);
    }
    
    @Override
    protected Message readInternal(Class<? extends Message> clazz, 
            HttpInputMessage inputMessage) throws IOException {
        Method parseFrom = clazz.getMethod("parseFrom", InputStream.class);
        return (Message) parseFrom.invoke(null, inputMessage.getBody());
    }
    
    @Override
    protected void writeInternal(Message message, HttpOutputMessage outputMessage) 
            throws IOException {
        message.writeTo(outputMessage.getBody());
    }
}
```

**When to use:** Integrating third-party libraries, legacy system wrappers, protocol bridges.

**When to avoid:** When you control both interfaces — just make them compatible directly.

**Real-world:** `HandlerAdapter`, `MessageConverter`, JDBC drivers, Spring Data repository adapters.

---

### 1.11 Command Pattern

**Problem:** Encapsulate a request as an object, enabling parameterization, queuing, logging, and undo.

```java
// Command interface
public interface Command<R> {
    R execute();
    default void undo() { throw new UnsupportedOperationException(); }
}

// Concrete commands
public class CreateOrderCommand implements Command<Order> {
    private final OrderRequest request;
    private final OrderRepository orderRepo;
    private final InventoryService inventory;
    
    @Override
    public Order execute() {
        inventory.reserve(request.getItems());
        Order order = Order.from(request);
        return orderRepo.save(order);
    }
    
    @Override
    public void undo() {
        inventory.release(request.getItems());
        orderRepo.deleteByRequestId(request.getId());
    }
}

// Command bus with Spring
@Component
public class CommandBus {
    private final ApplicationContext ctx;
    private final List<CommandInterceptor> interceptors;
    
    public <R> R dispatch(Command<R> command) {
        for (CommandInterceptor interceptor : interceptors) {
            interceptor.before(command);
        }
        R result = command.execute();
        for (CommandInterceptor interceptor : interceptors) {
            interceptor.after(command, result);
        }
        return result;
    }
    
    // Async dispatch
    @Async
    public <R> CompletableFuture<R> dispatchAsync(Command<R> command) {
        return CompletableFuture.completedFuture(dispatch(command));
    }
}

// Queued commands with Spring + Kafka
@Component
public class CommandQueue {
    private final KafkaTemplate<String, CommandMessage> kafka;
    
    public void enqueue(Command<?> command) {
        CommandMessage msg = serialize(command);
        kafka.send("commands", msg.getId(), msg);
    }
}

@KafkaListener(topics = "commands")
public void processCommand(CommandMessage msg) {
    Command<?> command = deserialize(msg);
    command.execute();
}
```

**When to use:** Task queues, undo/redo, audit logging of operations, async processing, CQRS.

**When to avoid:** Simple CRUD where direct service calls are clearer.

**Real-world:** Job schedulers, transaction logs, event stores, Celery-style task queues.

---

### 1.12 State Pattern

**Problem:** Allow an object to change behavior when its internal state changes.

```java
// Order state machine
public enum OrderState {
    CREATED, PAYMENT_PENDING, PAID, SHIPPED, DELIVERED, CANCELLED;
}

public interface OrderStateHandler {
    OrderState getState();
    OrderState pay(Order order);
    OrderState ship(Order order);
    OrderState deliver(Order order);
    OrderState cancel(Order order);
}

@Component
public class CreatedStateHandler implements OrderStateHandler {
    @Override public OrderState getState() { return OrderState.CREATED; }
    
    @Override
    public OrderState pay(Order order) {
        order.setPaymentDate(Instant.now());
        return OrderState.PAID;
    }
    
    @Override
    public OrderState cancel(Order order) {
        order.setCancelledDate(Instant.now());
        return OrderState.CANCELLED;
    }
    
    @Override public OrderState ship(Order order) { 
        throw new IllegalStateException("Cannot ship unpaid order"); 
    }
    @Override public OrderState deliver(Order order) { 
        throw new IllegalStateException("Cannot deliver unshipped order"); 
    }
}

// State machine service
@Service
public class OrderStateMachine {
    private final Map<OrderState, OrderStateHandler> handlers;
    
    public OrderStateMachine(List<OrderStateHandler> handlerList) {
        this.handlers = handlerList.stream()
            .collect(Collectors.toMap(OrderStateHandler::getState, Function.identity()));
    }
    
    @Transactional
    public Order transition(Order order, OrderAction action) {
        OrderStateHandler handler = handlers.get(order.getState());
        OrderState newState = switch (action) {
            case PAY -> handler.pay(order);
            case SHIP -> handler.ship(order);
            case DELIVER -> handler.deliver(order);
            case CANCEL -> handler.cancel(order);
        };
        order.setState(newState);
        return orderRepository.save(order);
    }
}

// Spring Statemachine (framework approach)
@Configuration
@EnableStateMachineFactory
public class OrderStateMachineConfig 
        extends EnumStateMachineConfigurerAdapter<OrderState, OrderEvent> {
    
    @Override
    public void configure(StateMachineTransitionConfigurer<OrderState, OrderEvent> transitions) 
            throws Exception {
        transitions
            .withExternal().source(CREATED).target(PAID).event(PAY)
            .and()
            .withExternal().source(PAID).target(SHIPPED).event(SHIP)
            .and()
            .withExternal().source(SHIPPED).target(DELIVERED).event(DELIVER)
            .and()
            .withExternal().source(CREATED).target(CANCELLED).event(CANCEL)
            .and()
            .withExternal().source(PAID).target(CANCELLED).event(CANCEL)
                .guard(ctx -> canCancelPaidOrder(ctx));
    }
}
```

**When to use:** Objects with well-defined states and transitions (orders, workflows, connections).

**When to avoid:** When states are simple and few — if/else is fine for 2-3 states.

**Real-world:** Order processing, payment flows, CI/CD pipeline stages, connection lifecycle.

---

### 1.13 Iterator Pattern

**Problem:** Access elements of a collection sequentially without exposing its underlying representation.

```java
// Spring Data Page/Slice - paginated iteration
@Repository
public interface ProductRepository extends JpaRepository<Product, Long> {
    Page<Product> findByCategory(String category, Pageable pageable);
    Slice<Product> findByPriceLessThan(BigDecimal price, Pageable pageable);
}

@Service
public class ProductExportService {
    
    // Iterate through all products without loading everything in memory
    public void exportAll(OutputStream out) {
        int page = 0;
        Slice<Product> slice;
        do {
            slice = productRepo.findAll(PageRequest.of(page, 1000));
            slice.getContent().forEach(p -> writeToStream(out, p));
            page++;
        } while (slice.hasNext());
    }
}

// Reactive streaming iteration with Flux
@RestController
public class EventStreamController {
    
    @GetMapping(value = "/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<Event>> streamEvents() {
        return eventRepository.findAllAsStream()
            .map(event -> ServerSentEvent.<Event>builder()
                .id(event.getId().toString())
                .event(event.getType())
                .data(event)
                .build());
    }
}

// Custom iterator for tree traversal
public class CategoryTreeIterator implements Iterator<Category> {
    private final Deque<Category> stack = new ArrayDeque<>();
    
    public CategoryTreeIterator(Category root) {
        stack.push(root);
    }
    
    @Override
    public boolean hasNext() { return !stack.isEmpty(); }
    
    @Override
    public Category next() {
        Category current = stack.pop();
        current.getChildren().forEach(stack::push);
        return current;
    }
}
```

**When to use:** Large datasets requiring pagination, streaming responses, lazy loading.

**When to avoid:** When the full collection fits comfortably in memory.

**Real-world:** Spring Data pagination, Kafka consumer iteration, cursor-based GraphQL pagination.

---

### 1.14 Mediator Pattern

**Problem:** Reduce chaotic dependencies between objects by centralizing communication through a mediator.

```java
// ApplicationContext as mediator - components don't know about each other
// They communicate through events (see Observer pattern above)

// Explicit Mediator for complex workflows
public interface WorkflowMediator {
    <R> R send(Request<R> request);
    void publish(Notification notification);
}

@Component
public class SpringMediator implements WorkflowMediator {
    private final ApplicationContext ctx;
    
    @Override
    public <R> R send(Request<R> request) {
        RequestHandler<Request<R>, R> handler = resolveHandler(request);
        return handler.handle(request);
    }
    
    @Override
    public void publish(Notification notification) {
        List<NotificationHandler<Notification>> handlers = resolveNotificationHandlers(notification);
        handlers.forEach(h -> h.handle(notification));
    }
    
    @SuppressWarnings("unchecked")
    private <R> RequestHandler<Request<R>, R> resolveHandler(Request<R> request) {
        String handlerName = request.getClass().getSimpleName() + "Handler";
        return (RequestHandler<Request<R>, R>) ctx.getBean(handlerName);
    }
}

// Usage - components only know about the mediator
@RestController
@RequiredArgsConstructor
public class OrderController {
    private final WorkflowMediator mediator;
    
    @PostMapping("/orders")
    public ResponseEntity<OrderResponse> create(@RequestBody CreateOrderRequest request) {
        OrderResponse response = mediator.send(request);
        return ResponseEntity.created(URI.create("/orders/" + response.getId())).body(response);
    }
}
```

**When to use:** Complex interactions between many components, reducing coupling in event-driven systems.

**When to avoid:** Small systems where direct dependencies are clearer.

**Real-world:** MediatR pattern, Spring's `ApplicationContext`, message brokers, UI event buses.

---

### 1.15 Facade Pattern

**Problem:** Provide a simplified interface to a complex subsystem.

```java
// Service layer as facade over multiple repositories and services
@Service
@RequiredArgsConstructor
public class CheckoutFacade {
    private final CartService cartService;
    private final InventoryService inventoryService;
    private final PricingService pricingService;
    private final PaymentService paymentService;
    private final ShippingService shippingService;
    private final NotificationService notificationService;
    
    @Transactional
    public CheckoutResult checkout(CheckoutRequest request) {
        // Orchestrates complex subsystem interactions
        Cart cart = cartService.getCart(request.getUserId());
        
        // Validate inventory
        InventoryCheck check = inventoryService.checkAvailability(cart.getItems());
        if (!check.isAllAvailable()) {
            return CheckoutResult.itemsUnavailable(check.getUnavailable());
        }
        
        // Calculate final price
        PriceSummary price = pricingService.calculate(cart, request.getPromoCode());
        
        // Process payment
        PaymentResult payment = paymentService.charge(
            request.getPaymentMethod(), price.getTotal());
        if (!payment.isSuccess()) {
            return CheckoutResult.paymentFailed(payment.getError());
        }
        
        // Create shipping
        ShipmentInfo shipment = shippingService.createShipment(
            cart.getItems(), request.getShippingAddress());
        
        // Send confirmation
        notificationService.sendOrderConfirmation(request.getUserId(), shipment);
        
        cartService.clear(request.getUserId());
        return CheckoutResult.success(payment.getTransactionId(), shipment.getTrackingId());
    }
}

// API Gateway as facade (Spring Cloud Gateway)
@Configuration
public class GatewayConfig {
    
    @Bean
    public RouteLocator routes(RouteLocatorBuilder builder) {
        return builder.routes()
            .route("users", r -> r.path("/api/users/**")
                .uri("lb://user-service"))
            .route("orders", r -> r.path("/api/orders/**")
                .uri("lb://order-service"))
            .route("payments", r -> r.path("/api/payments/**")
                .uri("lb://payment-service"))
            .build();
    }
}
```

**When to use:** Simplifying complex subsystems, providing a unified API, orchestration logic.

**When to avoid:** When the facade becomes a god class — split into smaller facades.

**Real-world:** Service layer in any Spring app, API Gateways, SDK wrapper libraries.

---

## 2. Enterprise Integration Patterns

### 2.1 Message Channel

**Problem:** How to connect applications so they can communicate via messaging.

```java
// Spring Integration - Direct Channel (synchronous)
@Configuration
public class ChannelConfig {
    
    @Bean
    public MessageChannel orderChannel() {
        return new DirectChannel();
    }
    
    // Queue Channel (asynchronous, buffered)
    @Bean
    public MessageChannel asyncOrderChannel() {
        return new QueueChannel(100); // capacity 100
    }
    
    // Publish-Subscribe Channel
    @Bean
    public MessageChannel notificationChannel() {
        return new PublishSubscribeChannel();
    }
}

// Spring Cloud Stream with Kafka
@Configuration
public class StreamConfig {
    
    @Bean
    public Function<Flux<OrderEvent>, Flux<ShipmentEvent>> processOrders() {
        return orderEvents -> orderEvents
            .filter(e -> e.getStatus() == OrderStatus.PAID)
            .map(this::createShipment);
    }
}

// application.yml
// spring.cloud.stream.bindings.processOrders-in-0.destination=orders
// spring.cloud.stream.bindings.processOrders-out-0.destination=shipments
```

---

### 2.2 Message Router

**Problem:** Route messages to different channels based on conditions.

```java
// Content-Based Router
@Bean
public IntegrationFlow routingFlow() {
    return IntegrationFlow.from("incomingOrders")
        .<Order, String>route(
            order -> order.getType().name(),
            mapping -> mapping
                .subFlowMapping("DIGITAL", sf -> sf.channel("digitalOrderChannel"))
                .subFlowMapping("PHYSICAL", sf -> sf.channel("physicalOrderChannel"))
                .defaultSubFlowMapping(sf -> sf.channel("unknownOrderChannel"))
        )
        .get();
}

// Spring Cloud Stream router
@Bean
public Function<OrderEvent, Message<OrderEvent>> routeOrder() {
    return event -> {
        String destination = switch (event.getRegion()) {
            case "US" -> "orders-us";
            case "EU" -> "orders-eu";
            default -> "orders-global";
        };
        return MessageBuilder.withPayload(event)
            .setHeader("spring.cloud.stream.sendto.destination", destination)
            .build();
    };
}
```

---

### 2.3 Message Transformer

**Problem:** Convert a message from one format to another.

```java
@Bean
public IntegrationFlow transformFlow() {
    return IntegrationFlow.from("rawOrderChannel")
        .transform(Transformers.fromJson(OrderDto.class))
        .transform(Order.class, dto -> Order.builder()
            .id(UUID.randomUUID())
            .items(dto.getItems().stream().map(this::mapItem).toList())
            .total(calculateTotal(dto))
            .build())
        .transform(Transformers.toJson())
        .channel("processedOrderChannel")
        .get();
}

// Spring Cloud Stream transformer
@Bean
public Function<OrderCreatedEvent, OrderNotification> transformToNotification() {
    return event -> OrderNotification.builder()
        .orderId(event.getOrderId())
        .customerEmail(event.getCustomerEmail())
        .summary(formatSummary(event))
        .build();
}
```

---

### 2.4 Message Filter

**Problem:** Remove unwanted messages from a channel.

```java
@Bean
public IntegrationFlow filterFlow() {
    return IntegrationFlow.from("allEventsChannel")
        .filter(Order.class, order -> order.getTotal().compareTo(BigDecimal.TEN) > 0,
            f -> f.discardChannel("lowValueChannel"))
        .channel("highValueOrderChannel")
        .get();
}

// Spring Cloud Stream
@Bean
public Function<Flux<Event>, Flux<Event>> filterEvents() {
    return events -> events
        .filter(e -> e.getType() != EventType.HEARTBEAT)
        .filter(e -> !e.isTest());
}
```

---

### 2.5 Splitter/Aggregator

**Problem:** Process individual elements of a composite message, then reassemble results.

```java
@Bean
public IntegrationFlow splitAggregateFlow() {
    return IntegrationFlow.from("batchOrderChannel")
        // Split batch into individual orders
        .split(BatchOrder.class, BatchOrder::getOrders)
        // Process each
        .channel(c -> c.executor(Executors.newFixedThreadPool(10)))
        .handle((payload, headers) -> processOrder((Order) payload))
        // Aggregate results
        .aggregate(a -> a
            .correlationStrategy(msg -> msg.getHeaders().get("batchId"))
            .releaseStrategy(group -> group.size() == group.getSequenceSize())
            .outputProcessor(group -> new BatchResult(
                group.getMessages().stream()
                    .map(m -> (OrderResult) m.getPayload())
                    .toList()))
            .expireGroupsUponCompletion(true)
            .groupTimeout(30_000))
        .channel("batchResultChannel")
        .get();
}
```

---

### 2.6 Scatter-Gather

**Problem:** Send a message to multiple recipients and aggregate their replies.

```java
@Bean
public IntegrationFlow scatterGatherFlow() {
    return IntegrationFlow.from("quoteRequestChannel")
        .scatterGather(
            scatterer -> scatterer
                .recipientFlow(f -> f.handle(supplierAHandler()))
                .recipientFlow(f -> f.handle(supplierBHandler()))
                .recipientFlow(f -> f.handle(supplierCHandler())),
            gatherer -> gatherer
                .releaseStrategy(group -> group.size() >= 2) // need at least 2 quotes
                .groupTimeout(5000)) // 5s timeout
        .transform(this::selectBestQuote)
        .channel("bestQuoteChannel")
        .get();
}
```

---

### 2.7 Dead Letter Queue

**Problem:** Handle messages that cannot be processed successfully.

```java
// Spring Cloud Stream DLQ config (application.yml)
// spring.cloud.stream.kafka.bindings.processOrders-in-0.consumer:
//   enableDlq: true
//   dlqName: orders-dlq
//   dlqPartitions: 3

// Manual DLQ handling
@Component
public class OrderConsumer {
    private final KafkaTemplate<String, OrderEvent> kafka;
    
    @KafkaListener(topics = "orders")
    public void process(OrderEvent event, Acknowledgment ack) {
        try {
            orderService.process(event);
            ack.acknowledge();
        } catch (RetryableException e) {
            throw e; // let retry mechanism handle
        } catch (Exception e) {
            // Send to DLQ
            kafka.send("orders-dlq", event.getId(), event);
            ack.acknowledge(); // don't reprocess
            log.error("Sent to DLQ: {}", event.getId(), e);
        }
    }
    
    @KafkaListener(topics = "orders-dlq")
    public void processDlq(OrderEvent event) {
        alertService.notifyOps("DLQ message", event);
        dlqRepository.save(new DlqEntry(event));
    }
}

// RabbitMQ DLQ with Spring
@Configuration
public class RabbitDlqConfig {
    
    @Bean
    public Queue orderQueue() {
        return QueueBuilder.durable("orders")
            .withArgument("x-dead-letter-exchange", "dlx")
            .withArgument("x-dead-letter-routing-key", "orders-dlq")
            .withArgument("x-message-ttl", 60000)
            .build();
    }
    
    @Bean
    public Queue dlq() {
        return QueueBuilder.durable("orders-dlq").build();
    }
}
```

---

### 2.8 Wire Tap

**Problem:** Inspect messages flowing through a channel without disrupting the flow.

```java
@Bean
public IntegrationFlow mainFlow() {
    return IntegrationFlow.from("inputChannel")
        .wireTap("auditChannel") // non-intrusive copy
        .handle(orderService, "process")
        .get();
}

@Bean
public IntegrationFlow auditFlow() {
    return IntegrationFlow.from("auditChannel")
        .handle(msg -> auditLog.record(msg))
        .get();
}

// HTTP interceptor as wire tap
@Component
public class RequestAuditInterceptor implements HandlerInterceptor {
    @Override
    public boolean preHandle(HttpServletRequest request, 
            HttpServletResponse response, Object handler) {
        auditService.logRequest(request); // observe without modifying
        return true; // always continue
    }
}
```

---

### 2.9 Idempotent Receiver

**Problem:** Handle duplicate message delivery gracefully.

```java
@Component
public class IdempotentOrderProcessor {
    private final RedisTemplate<String, String> redis;
    private static final Duration TTL = Duration.ofHours(24);
    
    @KafkaListener(topics = "orders")
    public void process(OrderEvent event) {
        String idempotencyKey = "processed:" + event.getEventId();
        
        // Atomic check-and-set
        Boolean isNew = redis.opsForValue()
            .setIfAbsent(idempotencyKey, "1", TTL);
        
        if (Boolean.FALSE.equals(isNew)) {
            log.info("Duplicate event ignored: {}", event.getEventId());
            return;
        }
        
        try {
            orderService.process(event);
        } catch (Exception e) {
            redis.delete(idempotencyKey); // allow retry
            throw e;
        }
    }
}

// Database-based idempotency
@Service
public class IdempotentCommandHandler {
    
    @Transactional
    public <R> R execute(String idempotencyKey, Supplier<R> command) {
        Optional<ProcessedCommand> existing = processedRepo.findById(idempotencyKey);
        if (existing.isPresent()) {
            return deserialize(existing.get().getResult());
        }
        
        R result = command.get();
        processedRepo.save(new ProcessedCommand(idempotencyKey, serialize(result)));
        return result;
    }
}

// REST API idempotency
@PostMapping("/payments")
public ResponseEntity<PaymentResult> createPayment(
        @RequestHeader("Idempotency-Key") String key,
        @RequestBody PaymentRequest request) {
    return ResponseEntity.ok(
        idempotentHandler.execute(key, () -> paymentService.charge(request))
    );
}
```

---

## 3. Architectural Patterns

### 3.1 Hexagonal Architecture (Ports & Adapters)

**Problem:** Decouple business logic from infrastructure, making the application testable and adaptable.

```
                    ┌─────────────────────────┐
   Driving          │      Application        │         Driven
   Adapters         │                         │         Adapters
                    │   ┌───────────────┐     │
┌──────────┐        │   │               │     │      ┌──────────┐
│REST API  │───Port──│──▶│  Domain Core  │──Port──│───▶│  DB      │
└──────────┘        │   │               │     │      └──────────┘
┌──────────┐        │   │  (Use Cases)  │     │      ┌──────────┐
│GraphQL   │───Port──│──▶│               │──Port──│───▶│  Kafka   │
└──────────┘        │   └───────────────┘     │      └──────────┘
                    └─────────────────────────┘
```

```
src/main/java/com/example/order/
├── domain/                          # Core - no Spring dependencies
│   ├── model/
│   │   ├── Order.java
│   │   ├── OrderItem.java
│   │   └── OrderStatus.java
│   ├── port/
│   │   ├── in/                      # Driving/Primary ports
│   │   │   ├── CreateOrderUseCase.java
│   │   │   └── GetOrderQuery.java
│   │   └── out/                     # Driven/Secondary ports
│   │       ├── OrderRepository.java
│   │       ├── PaymentGateway.java
│   │       └── EventPublisher.java
│   └── service/                     # Domain services (use case implementations)
│       └── OrderDomainService.java
├── application/                     # Use case orchestration
│   └── OrderApplicationService.java
├── adapter/
│   ├── in/                          # Driving adapters
│   │   ├── web/
│   │   │   ├── OrderController.java
│   │   │   └── OrderDto.java
│   │   └── messaging/
│   │       └── OrderEventListener.java
│   └── out/                         # Driven adapters
│       ├── persistence/
│       │   ├── OrderJpaRepository.java
│       │   ├── OrderEntity.java
│       │   └── OrderPersistenceAdapter.java
│       ├── payment/
│       │   └── StripePaymentAdapter.java
│       └── messaging/
│           └── KafkaEventPublisher.java
└── config/
    └── BeanConfig.java
```

```java
// Port (interface in domain)
public interface OrderRepository {
    Order save(Order order);
    Optional<Order> findById(OrderId id);
}

// Domain service - pure business logic, no framework dependencies
public class OrderDomainService implements CreateOrderUseCase {
    private final OrderRepository orderRepo;
    private final PaymentGateway paymentGateway;
    private final EventPublisher eventPublisher;
    
    // Constructor injection (no @Autowired needed in domain)
    public OrderDomainService(OrderRepository orderRepo, 
            PaymentGateway paymentGateway, EventPublisher eventPublisher) {
        this.orderRepo = orderRepo;
        this.paymentGateway = paymentGateway;
        this.eventPublisher = eventPublisher;
    }
    
    @Override
    public Order createOrder(CreateOrderCommand command) {
        Order order = Order.create(command.getCustomerId(), command.getItems());
        order.validate(); // domain validation
        
        PaymentResult payment = paymentGateway.authorize(order.getTotal());
        if (!payment.isAuthorized()) {
            throw new PaymentDeclinedException(payment.getReason());
        }
        
        order.markPaid(payment.getTransactionId());
        Order saved = orderRepo.save(order);
        eventPublisher.publish(new OrderCreatedEvent(saved));
        return saved;
    }
}

// Driven adapter - implements port using infrastructure
@Component
public class OrderPersistenceAdapter implements OrderRepository {
    private final OrderJpaRepository jpaRepo;
    private final OrderMapper mapper;
    
    @Override
    public Order save(Order order) {
        OrderEntity entity = mapper.toEntity(order);
        OrderEntity saved = jpaRepo.save(entity);
        return mapper.toDomain(saved);
    }
    
    @Override
    public Optional<Order> findById(OrderId id) {
        return jpaRepo.findById(id.getValue()).map(mapper::toDomain);
    }
}

// Configuration wires it all together
@Configuration
public class BeanConfig {
    @Bean
    public CreateOrderUseCase createOrderUseCase(
            OrderRepository orderRepo, 
            PaymentGateway paymentGateway, 
            EventPublisher eventPublisher) {
        return new OrderDomainService(orderRepo, paymentGateway, eventPublisher);
    }
}
```

**When to use:** Complex business domains, long-lived systems, when testability is critical.

**When to avoid:** Simple CRUD apps, prototypes, when the overhead isn't justified.

---

### 3.2 Clean Architecture

**Problem:** Same goals as Hexagonal, but with explicit layer dependency rules (dependencies point inward).

```
┌──────────────────────────────────────────┐
│  Frameworks & Drivers (outermost)        │
│  ┌────────────────────────────────────┐  │
│  │  Interface Adapters                │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │  Use Cases / Application     │  │  │
│  │  │  ┌────────────────────────┐  │  │  │
│  │  │  │  Entities / Domain     │  │  │  │
│  │  │  └────────────────────────┘  │  │  │
│  │  └──────────────────────────────┘  │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

Key rules:
1. Inner layers know nothing about outer layers
2. Data flows inward through interfaces (ports)
3. Entities contain enterprise-wide business rules
4. Use Cases contain application-specific business rules

Implementation is structurally the same as Hexagonal (see above) with stricter layering.

---

### 3.3 CQRS (Command Query Responsibility Segregation)

**Problem:** Separate read and write models to optimize each independently.

```java
// Command side
public record CreateOrderCommand(String customerId, List<OrderItem> items) {}
public record CancelOrderCommand(String orderId, String reason) {}

@Service
public class OrderCommandService {
    private final OrderRepository writeRepo; // normalized, relational
    private final EventPublisher publisher;
    
    @Transactional
    public String createOrder(CreateOrderCommand cmd) {
        Order order = Order.create(cmd.customerId(), cmd.items());
        writeRepo.save(order);
        publisher.publish(new OrderCreatedEvent(order)); // project to read side
        return order.getId();
    }
}

// Query side
public record OrderSummaryQuery(String customerId, OrderStatus status, Pageable page) {}

@Service
public class OrderQueryService {
    private final OrderReadRepository readRepo; // denormalized, optimized for reads
    
    public Page<OrderSummary> findOrders(OrderSummaryQuery query) {
        return readRepo.findByCustomerIdAndStatus(
            query.customerId(), query.status(), query.page());
    }
}

// Read model projection (event handler that builds read models)
@Component
public class OrderProjection {
    private final OrderReadRepository readRepo;
    
    @EventListener
    public void on(OrderCreatedEvent event) {
        OrderSummary summary = OrderSummary.builder()
            .orderId(event.getOrderId())
            .customerId(event.getCustomerId())
            .totalItems(event.getItems().size())
            .total(event.getTotal())
            .status(OrderStatus.CREATED)
            .createdAt(event.getTimestamp())
            .build();
        readRepo.save(summary);
    }
    
    @EventListener
    public void on(OrderShippedEvent event) {
        readRepo.updateStatus(event.getOrderId(), OrderStatus.SHIPPED);
    }
}

// Separate databases for read/write
// Write: PostgreSQL (ACID, normalized)
// Read: Elasticsearch or MongoDB (denormalized, fast queries)
```

**When to use:** High read-to-write ratio, complex queries requiring different data shapes, scalability needs.

**When to avoid:** Simple domains, when eventual consistency is unacceptable, small teams.

---

### 3.4 Event Sourcing

**Problem:** Store state changes as a sequence of events rather than current state only.

```java
// Event store
public interface EventStore {
    void append(String aggregateId, List<DomainEvent> events, long expectedVersion);
    List<DomainEvent> getEvents(String aggregateId);
    List<DomainEvent> getEventsSince(String aggregateId, long version);
}

// Aggregate root with event sourcing
public class Order {
    private String id;
    private OrderStatus status;
    private List<OrderItem> items;
    private BigDecimal total;
    private long version;
    
    private final List<DomainEvent> uncommittedEvents = new ArrayList<>();
    
    // Reconstruct from events
    public static Order fromHistory(List<DomainEvent> events) {
        Order order = new Order();
        events.forEach(order::apply);
        return order;
    }
    
    // Command handlers produce events
    public void place(String customerId, List<OrderItem> items) {
        if (this.status != null) throw new IllegalStateException("Already placed");
        raise(new OrderPlacedEvent(id, customerId, items, calculateTotal(items)));
    }
    
    public void cancel(String reason) {
        if (status != OrderStatus.PLACED) throw new IllegalStateException("Cannot cancel");
        raise(new OrderCancelledEvent(id, reason, Instant.now()));
    }
    
    // Event handlers mutate state
    private void apply(DomainEvent event) {
        switch (event) {
            case OrderPlacedEvent e -> {
                this.id = e.getOrderId();
                this.status = OrderStatus.PLACED;
                this.items = e.getItems();
                this.total = e.getTotal();
            }
            case OrderCancelledEvent e -> {
                this.status = OrderStatus.CANCELLED;
            }
            default -> throw new IllegalArgumentException("Unknown event: " + event);
        }
        this.version++;
    }
    
    private void raise(DomainEvent event) {
        apply(event);
        uncommittedEvents.add(event);
    }
    
    public List<DomainEvent> getUncommittedEvents() {
        return Collections.unmodifiableList(uncommittedEvents);
    }
}

// Repository using event store
@Component
public class EventSourcedOrderRepository {
    private final EventStore eventStore;
    
    public Order findById(String id) {
        List<DomainEvent> events = eventStore.getEvents(id);
        if (events.isEmpty()) throw new OrderNotFoundException(id);
        return Order.fromHistory(events);
    }
    
    public void save(Order order) {
        eventStore.append(order.getId(), order.getUncommittedEvents(), order.getVersion());
    }
}

// Snapshot optimization for aggregates with many events
@Component
public class SnapshotStore {
    public void saveSnapshot(String aggregateId, long version, byte[] state) { ... }
    public Optional<Snapshot> getLatest(String aggregateId) { ... }
}

public Order findById(String id) {
    Optional<Snapshot> snapshot = snapshotStore.getLatest(id);
    List<DomainEvent> events;
    Order order;
    
    if (snapshot.isPresent()) {
        order = deserialize(snapshot.get().getState());
        events = eventStore.getEventsSince(id, snapshot.get().getVersion());
    } else {
        order = new Order();
        events = eventStore.getEvents(id);
    }
    
    events.forEach(order::apply);
    return order;
}
```

**When to use:** Audit requirements, temporal queries ("what was the state at time T"), complex domains with undo.

**When to avoid:** Simple CRUD, when storage costs are a concern, when team lacks event sourcing experience.

---

### 3.5 Saga Pattern

**Problem:** Manage distributed transactions across multiple services without 2PC.

```java
// ORCHESTRATION-BASED SAGA
@Component
public class OrderSaga {
    private final PaymentService paymentService;
    private final InventoryService inventoryService;
    private final ShippingService shippingService;
    
    @Transactional
    public SagaResult execute(OrderSagaData data) {
        try {
            // Step 1: Reserve inventory
            ReservationId reservation = inventoryService.reserve(data.getItems());
            data.setReservationId(reservation);
            
            // Step 2: Charge payment
            PaymentId payment = paymentService.charge(data.getPaymentInfo(), data.getTotal());
            data.setPaymentId(payment);
            
            // Step 3: Create shipment
            ShipmentId shipment = shippingService.create(data.getAddress(), data.getItems());
            data.setShipmentId(shipment);
            
            return SagaResult.success(data);
            
        } catch (PaymentFailedException e) {
            // Compensate step 1
            inventoryService.release(data.getReservationId());
            return SagaResult.failure("Payment failed", e);
            
        } catch (ShippingException e) {
            // Compensate steps 1 and 2
            paymentService.refund(data.getPaymentId());
            inventoryService.release(data.getReservationId());
            return SagaResult.failure("Shipping failed", e);
        }
    }
}

// CHOREOGRAPHY-BASED SAGA (event-driven)
// Each service listens to events and publishes its own events

// Inventory Service
@KafkaListener(topics = "order-created")
public void onOrderCreated(OrderCreatedEvent event) {
    try {
        inventoryService.reserve(event.getItems());
        kafkaTemplate.send("inventory-reserved", 
            new InventoryReservedEvent(event.getOrderId()));
    } catch (InsufficientStockException e) {
        kafkaTemplate.send("inventory-failed",
            new InventoryFailedEvent(event.getOrderId(), e.getMessage()));
    }
}

// Payment Service
@KafkaListener(topics = "inventory-reserved")
public void onInventoryReserved(InventoryReservedEvent event) {
    try {
        paymentService.charge(event.getOrderId());
        kafkaTemplate.send("payment-completed",
            new PaymentCompletedEvent(event.getOrderId()));
    } catch (PaymentDeclinedException e) {
        kafkaTemplate.send("payment-failed",
            new PaymentFailedEvent(event.getOrderId()));
    }
}

// Inventory Service - compensating action
@KafkaListener(topics = "payment-failed")
public void onPaymentFailed(PaymentFailedEvent event) {
    inventoryService.release(event.getOrderId()); // compensate
}
```

**Orchestration vs Choreography:**
| Aspect | Orchestration | Choreography |
|--------|---------------|--------------|
| Coupling | Central coordinator | Decentralized |
| Complexity | In orchestrator | Distributed |
| Debugging | Easier (single point) | Harder (trace events) |
| Single point of failure | Yes | No |
| Best for | Complex flows | Simple flows, few steps |

---

### 3.6 Outbox Pattern

**Problem:** Ensure atomicity between database writes and message publishing (avoid dual-write problem).

```java
// 1. Write to outbox table in same transaction as business data
@Entity
@Table(name = "outbox_events")
public class OutboxEvent {
    @Id private UUID id;
    private String aggregateType;
    private String aggregateId;
    private String eventType;
    private String payload; // JSON
    private Instant createdAt;
    private boolean published;
}

@Service
public class OrderService {
    
    @Transactional // Single transaction for both
    public Order createOrder(CreateOrderCommand cmd) {
        Order order = orderRepository.save(Order.create(cmd));
        
        // Write event to outbox (same DB transaction)
        outboxRepository.save(OutboxEvent.builder()
            .id(UUID.randomUUID())
            .aggregateType("Order")
            .aggregateId(order.getId())
            .eventType("OrderCreated")
            .payload(objectMapper.writeValueAsString(new OrderCreatedEvent(order)))
            .createdAt(Instant.now())
            .published(false)
            .build());
        
        return order;
    }
}

// 2. Outbox poller publishes events to Kafka
@Component
public class OutboxPoller {
    
    @Scheduled(fixedDelay = 100) // Poll every 100ms
    @Transactional
    public void publishPendingEvents() {
        List<OutboxEvent> events = outboxRepository
            .findByPublishedFalseOrderByCreatedAtAsc(PageRequest.of(0, 100));
        
        for (OutboxEvent event : events) {
            try {
                kafkaTemplate.send(event.getAggregateType(), 
                    event.getAggregateId(), event.getPayload()).get();
                event.setPublished(true);
                outboxRepository.save(event);
            } catch (Exception e) {
                log.error("Failed to publish event: {}", event.getId(), e);
                break; // preserve ordering
            }
        }
    }
}

// Alternative: Debezium CDC-based outbox (no polling needed)
// Debezium reads the WAL/binlog and publishes changes automatically
```

**When to use:** Any microservice that must reliably publish events after state changes.

**When to avoid:** When using event sourcing (the event store IS the source of truth).

---

### 3.7 Strangler Fig Pattern

**Problem:** Incrementally migrate a legacy system to a new architecture without big-bang rewrites.

```java
// API Gateway routes traffic between legacy and new services
@Configuration
public class StranglerGatewayConfig {
    
    @Bean
    public RouteLocator stranglerRoutes(RouteLocatorBuilder builder) {
        return builder.routes()
            // New service handles user management (migrated)
            .route("users-new", r -> r.path("/api/users/**")
                .uri("http://new-user-service:8080"))
            
            // Legacy still handles orders (not yet migrated)
            .route("orders-legacy", r -> r.path("/api/orders/**")
                .uri("http://legacy-monolith:8080"))
            
            // Feature flag controlled migration
            .route("products-canary", r -> r.path("/api/products/**")
                .and().header("X-Use-New-Service", "true")
                .uri("http://new-product-service:8080"))
            .route("products-legacy", r -> r.path("/api/products/**")
                .uri("http://legacy-monolith:8080"))
            .build();
    }
}

// Anti-corruption layer between old and new
@Component
public class LegacyOrderAdapter implements OrderPort {
    private final LegacyOrderClient legacyClient;
    
    @Override
    public Order getOrder(String orderId) {
        LegacyOrderResponse legacy = legacyClient.fetchOrder(orderId);
        return mapToDomain(legacy); // translate legacy model to new domain model
    }
}
```

---

### 3.8 Anti-Corruption Layer

**Problem:** Protect your domain model from external system concepts leaking in.

```java
// ACL translates between your bounded context and external system
@Component
public class PaymentAntiCorruptionLayer implements PaymentGateway {
    private final StripeClient stripeClient; // third-party SDK
    
    @Override
    public PaymentResult charge(Money amount, PaymentMethod method) {
        // Translate our domain concepts to Stripe's API model
        StripeChargeRequest stripeReq = StripeChargeRequest.builder()
            .amount(amount.toCents())
            .currency(amount.getCurrency().getCode())
            .source(mapPaymentMethod(method))
            .idempotencyKey(UUID.randomUUID().toString())
            .build();
        
        try {
            StripeCharge charge = stripeClient.charges().create(stripeReq);
            // Translate Stripe response back to our domain
            return PaymentResult.success(
                new TransactionId(charge.getId()),
                Money.of(charge.getAmount(), charge.getCurrency())
            );
        } catch (StripeCardException e) {
            return PaymentResult.declined(e.getDeclineCode(), e.getMessage());
        } catch (StripeException e) {
            throw new PaymentGatewayException("Stripe error", e);
        }
    }
    
    private String mapPaymentMethod(PaymentMethod method) {
        // Our domain model != Stripe's model
        return switch (method.getType()) {
            case CREDIT_CARD -> method.getTokenizedId();
            case BANK_TRANSFER -> "ba_" + method.getAccountId();
            default -> throw new UnsupportedPaymentMethodException(method.getType());
        };
    }
}
```

**When to use:** Integrating with any external system whose model differs from yours.

---

### 3.9 Domain-Driven Design with Spring

```java
// Value Object
public record Money(BigDecimal amount, Currency currency) {
    public Money {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) < 0)
            throw new IllegalArgumentException("Amount must be non-negative");
        Objects.requireNonNull(currency);
    }
    
    public Money add(Money other) {
        if (!this.currency.equals(other.currency))
            throw new CurrencyMismatchException(this.currency, other.currency);
        return new Money(this.amount.add(other.amount), this.currency);
    }
}

// Aggregate Root
@Entity
public class Order {
    @Id private UUID id;
    @Embedded private CustomerId customerId;
    @Enumerated(EnumType.STRING) private OrderStatus status;
    @OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderLine> lines = new ArrayList<>();
    
    @Transient
    private List<DomainEvent> domainEvents = new ArrayList<>();
    
    // Business methods enforce invariants
    public void addItem(Product product, int quantity) {
        if (status != OrderStatus.DRAFT) 
            throw new OrderNotEditableException(id);
        if (quantity <= 0) 
            throw new InvalidQuantityException(quantity);
        
        lines.stream()
            .filter(l -> l.getProductId().equals(product.getId()))
            .findFirst()
            .ifPresentOrElse(
                line -> line.increaseQuantity(quantity),
                () -> lines.add(OrderLine.create(product, quantity))
            );
        
        domainEvents.add(new ItemAddedToOrderEvent(id, product.getId(), quantity));
    }
    
    public void submit() {
        if (lines.isEmpty()) throw new EmptyOrderException(id);
        this.status = OrderStatus.SUBMITTED;
        domainEvents.add(new OrderSubmittedEvent(id, getTotal()));
    }
}

// Domain Service (logic that doesn't belong to a single aggregate)
public class TransferService {
    public void transfer(Account from, Account to, Money amount) {
        from.debit(amount);
        to.credit(amount);
    }
}

// Repository (DDD-style - returns aggregates, not entities)
public interface OrderRepository {
    Order findById(OrderId id);
    void save(Order order);
    // No generic findAll - intentional to prevent unbounded queries
}

// Specification pattern
public interface Specification<T> {
    Predicate toPredicate(Root<T> root, CriteriaQuery<?> query, CriteriaBuilder cb);
}

public class OrderSpecifications {
    public static Specification<Order> hasStatus(OrderStatus status) {
        return (root, query, cb) -> cb.equal(root.get("status"), status);
    }
    
    public static Specification<Order> createdAfter(Instant date) {
        return (root, query, cb) -> cb.greaterThan(root.get("createdAt"), date);
    }
    
    public static Specification<Order> totalGreaterThan(BigDecimal amount) {
        return (root, query, cb) -> cb.greaterThan(root.get("total"), amount);
    }
}

// Usage
List<Order> orders = orderRepo.findAll(
    hasStatus(SUBMITTED).and(createdAfter(yesterday)).and(totalGreaterThan(hundred))
);
```

---

## 4. Spring-Specific Patterns

### 4.1 Auto-Configuration Pattern

**Problem:** Automatically configure beans based on classpath and properties.

```java
@AutoConfiguration
@ConditionalOnClass(RedisTemplate.class)
@EnableConfigurationProperties(RedisCacheProperties.class)
public class RedisCacheAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnProperty(prefix = "app.cache", name = "type", havingValue = "redis")
    public CacheManager cacheManager(RedisConnectionFactory factory, 
            RedisCacheProperties props) {
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(props.getTtl())
            .serializeValuesWith(
                SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer()));
        
        return RedisCacheManager.builder(factory)
            .cacheDefaults(config)
            .build();
    }
}

// spring.factories or META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
// com.example.RedisCacheAutoConfiguration
```

---

### 4.2 Starter Pattern

```
my-spring-boot-starter/
├── my-starter-autoconfigure/
│   ├── src/main/java/.../MyAutoConfiguration.java
│   ├── src/main/java/.../MyProperties.java
│   └── src/main/resources/META-INF/spring/
│       └── org.springframework.boot.autoconfigure.AutoConfiguration.imports
└── my-starter/
    └── pom.xml  (depends on autoconfigure + required libs)
```

---

### 4.3 Health Indicator Pattern

```java
@Component
public class ExternalServiceHealthIndicator implements HealthIndicator {
    private final ExternalServiceClient client;
    
    @Override
    public Health health() {
        try {
            long start = System.currentTimeMillis();
            client.ping();
            long latency = System.currentTimeMillis() - start;
            
            if (latency > 5000) {
                return Health.down()
                    .withDetail("latency", latency + "ms")
                    .withDetail("reason", "Response too slow")
                    .build();
            }
            return Health.up().withDetail("latency", latency + "ms").build();
        } catch (Exception e) {
            return Health.down(e).build();
        }
    }
}
```

---

### 4.4 Configuration Properties Pattern

```java
@ConfigurationProperties(prefix = "app.notification")
@Validated
public class NotificationProperties {
    @NotNull private EmailConfig email;
    @NotNull private SmsConfig sms;
    private RetryConfig retry = new RetryConfig();
    
    @Valid
    public static class EmailConfig {
        @NotBlank private String from;
        @Min(1) private int maxRecipients = 50;
        private boolean enabled = true;
        // getters/setters
    }
    
    @Valid
    public static class RetryConfig {
        @Min(1) @Max(10) private int maxAttempts = 3;
        @DurationMin(millis = 100) private Duration backoff = Duration.ofSeconds(1);
        // getters/setters
    }
}
```

---

### 4.5 Conditional Bean Registration

```java
@Configuration
public class StorageConfig {
    
    @Bean
    @ConditionalOnProperty(name = "storage.type", havingValue = "s3")
    public StorageService s3Storage(S3Client s3) {
        return new S3StorageService(s3);
    }
    
    @Bean
    @ConditionalOnProperty(name = "storage.type", havingValue = "local", matchIfMissing = true)
    public StorageService localStorage() {
        return new LocalFileStorageService();
    }
    
    @Bean
    @ConditionalOnProperty(name = "storage.type", havingValue = "gcs")
    @ConditionalOnClass(name = "com.google.cloud.storage.Storage")
    public StorageService gcsStorage() {
        return new GcsStorageService();
    }
}
```

---

### 4.6 Profile-Based Configuration

```java
@Configuration
@Profile("production")
public class ProductionConfig {
    @Bean
    public DataSource dataSource(DatabaseProperties props) {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(props.getUrl());
        config.setMaximumPoolSize(20);
        config.setConnectionTimeout(5000);
        return new HikariDataSource(config);
    }
}

@Configuration
@Profile("test")
public class TestConfig {
    @Bean
    public DataSource dataSource() {
        return new EmbeddedDatabaseBuilder()
            .setType(EmbeddedDatabaseType.H2)
            .build();
    }
}
```

---

### 4.7 Repository Pattern (Spring Data)

```java
// Basic repository with custom queries
public interface OrderRepository extends JpaRepository<Order, UUID> {
    
    // Derived query
    List<Order> findByStatusAndCreatedAtAfter(OrderStatus status, Instant after);
    
    // Custom JPQL
    @Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.customerId = :customerId")
    List<Order> findWithItemsByCustomerId(@Param("customerId") String customerId);
    
    // Native query for performance
    @Query(value = "SELECT * FROM orders WHERE total > :min FOR UPDATE SKIP LOCKED LIMIT :limit",
           nativeQuery = true)
    List<Order> findOrdersForProcessing(@Param("min") BigDecimal min, @Param("limit") int limit);
    
    // Projections
    <T> List<T> findByStatus(OrderStatus status, Class<T> projection);
}

// Projection interface
public interface OrderSummary {
    UUID getId();
    OrderStatus getStatus();
    BigDecimal getTotal();
    @Value("#{target.items.size()}")
    int getItemCount();
}
```

---

### 4.8 Specification Pattern (Spring Data)

```java
// Composable, reusable query specifications
public class OrderSpecs {
    
    public static Specification<Order> hasCustomer(String customerId) {
        return (root, query, cb) -> cb.equal(root.get("customerId"), customerId);
    }
    
    public static Specification<Order> isActive() {
        return (root, query, cb) -> root.get("status").in(
            OrderStatus.CREATED, OrderStatus.PROCESSING, OrderStatus.SHIPPED);
    }
    
    public static Specification<Order> totalBetween(BigDecimal min, BigDecimal max) {
        return (root, query, cb) -> cb.between(root.get("total"), min, max);
    }
    
    public static Specification<Order> createdInLast(Duration duration) {
        return (root, query, cb) -> cb.greaterThan(
            root.get("createdAt"), Instant.now().minus(duration));
    }
}

// Usage - compose dynamically based on request params
@GetMapping("/orders")
public Page<Order> search(OrderSearchRequest req, Pageable pageable) {
    Specification<Order> spec = Specification.where(null);
    
    if (req.getCustomerId() != null) spec = spec.and(hasCustomer(req.getCustomerId()));
    if (req.isActiveOnly()) spec = spec.and(isActive());
    if (req.getMinTotal() != null) spec = spec.and(totalBetween(req.getMinTotal(), req.getMaxTotal()));
    
    return orderRepository.findAll(spec, pageable);
}
```

---

## 5. Architecture Decision Records

### 5.1 Synchronous vs Asynchronous Communication

| Factor | Synchronous | Asynchronous |
|--------|-------------|--------------|
| Latency requirement | Low, immediate response needed | Acceptable delay |
| Coupling | Temporal coupling (both must be up) | Decoupled |
| Failure handling | Caller must handle/retry | Broker handles retry |
| Data consistency | Easier strong consistency | Eventual consistency |
| Debugging | Simpler request tracing | Distributed tracing needed |
| Throughput | Limited by slowest service | Buffered, handles spikes |

**Decision framework:**
- Use **sync** when: user expects immediate response, simple request-reply, < 3 services in chain
- Use **async** when: fire-and-forget, long-running processing, fan-out to multiple consumers, handling traffic spikes

---

### 5.2 Monolith vs Microservices

**Choose Monolith when:**
- Small team (< 8 engineers)
- Unclear domain boundaries
- Startup/MVP phase
- Strong consistency requirements
- Simple deployment needs

**Choose Microservices when:**
- Multiple independent teams owning different domains
- Different scaling requirements per component
- Different technology needs per component
- Need independent deployment cycles
- Domain boundaries are well-understood

**Hybrid approach:** Start monolith, extract services at natural boundaries when team/scale demands.

---

### 5.3 SQL vs NoSQL Decision Framework

| Criteria | SQL (PostgreSQL/MySQL) | Document (MongoDB) | Key-Value (Redis) | Wide-Column (Cassandra) |
|----------|------------------------|--------------------|--------------------|------------------------|
| Data model | Structured, relationships | Flexible schema | Simple lookups | Time-series, high write |
| Consistency | Strong (ACID) | Tunable | Eventual | Tunable |
| Query flexibility | High (joins, aggregates) | Medium | Low | Limited |
| Scale pattern | Vertical (or read replicas) | Horizontal | Horizontal | Horizontal |
| Best for | Transactions, reporting | Catalogs, content | Cache, sessions | IoT, logs, analytics |

---

### 5.4 Caching Strategies

```java
// Cache-Aside (Lazy Loading) - most common
@Service
public class ProductService {
    @Cacheable(value = "products", key = "#id", unless = "#result == null")
    public Product findById(String id) {
        return productRepository.findById(id).orElse(null);
    }
    
    @CacheEvict(value = "products", key = "#product.id")
    public Product update(Product product) {
        return productRepository.save(product);
    }
}

// Write-Through - write to cache and DB simultaneously
@Service
public class WriteThoughProductService {
    @CachePut(value = "products", key = "#product.id")
    @Transactional
    public Product save(Product product) {
        return productRepository.save(product); // returned value is cached
    }
}

// Write-Behind (Write-Back) - write to cache, async flush to DB
@Component
public class WriteBehindCache {
    private final Cache cache;
    private final BlockingQueue<WriteOperation> writeQueue = new LinkedBlockingQueue<>();
    
    public void put(String key, Object value) {
        cache.put(key, value);
        writeQueue.offer(new WriteOperation(key, value));
    }
    
    @Scheduled(fixedDelay = 1000)
    public void flush() {
        List<WriteOperation> batch = new ArrayList<>();
        writeQueue.drainTo(batch, 100);
        if (!batch.isEmpty()) {
            repository.batchSave(batch);
        }
    }
}
```

| Strategy | Consistency | Read Performance | Write Performance | Use Case |
|----------|-------------|-----------------|-------------------|----------|
| Cache-Aside | Eventual | High (cache hit) | Normal | General read-heavy |
| Write-Through | Strong | High | Slower (2 writes) | Can't tolerate stale data |
| Write-Behind | Eventual | High | High | Write-heavy, batch-friendly |
| Read-Through | Eventual | High | Normal | Simplified cache management |

---

### 5.5 Consistency vs Availability Tradeoffs (CAP/PACELC)

**CAP Theorem in practice:**
- Network partitions WILL happen — you must choose between C and A during partition
- **CP systems:** PostgreSQL, MongoDB (default), ZooKeeper — reject writes during partition
- **AP systems:** Cassandra, DynamoDB, CouchDB — accept writes, reconcile later

**PACELC (more practical):**
- During **P**artition: choose **A** or **C**
- **E**lse (normal operation): choose **L**atency or **C**onsistency

**Practical patterns:**
```java
// Strong consistency (CP) - distributed lock
@Service
public class InventoryService {
    @Transactional(isolation = Isolation.SERIALIZABLE)
    public boolean reserve(String productId, int quantity) {
        Inventory inv = inventoryRepo.findByIdForUpdate(productId); // SELECT FOR UPDATE
        if (inv.getAvailable() >= quantity) {
            inv.setAvailable(inv.getAvailable() - quantity);
            inventoryRepo.save(inv);
            return true;
        }
        return false;
    }
}

// Eventual consistency (AP) - accept-then-reconcile
@Service
public class EventualInventoryService {
    public void reserve(String productId, int quantity) {
        // Optimistically accept
        kafkaTemplate.send("inventory-commands", 
            new ReserveCommand(productId, quantity));
        // Reconciliation happens asynchronously
    }
    
    @KafkaListener(topics = "inventory-commands")
    public void processReservation(ReserveCommand cmd) {
        boolean success = tryReserve(cmd);
        if (!success) {
            kafkaTemplate.send("reservation-failed",
                new ReservationFailedEvent(cmd));
        }
    }
}
```

---

### 5.6 Stateful vs Stateless Service Design

**Stateless (preferred for web services):**
```java
@RestController
public class OrderController {
    // No instance state - request carries all needed context
    @PostMapping("/orders")
    public Order create(@RequestBody OrderRequest request,
                        @RequestHeader("Authorization") String token) {
        User user = tokenService.extractUser(token); // state from token
        return orderService.create(user, request);
    }
}
```

**When stateful is necessary:**
- WebSocket connections (session affinity)
- In-memory caches (replicated or partitioned)
- Workflow orchestrators with in-progress state
- Game servers

**Mitigation strategies for stateful services:**
1. Sticky sessions (load balancer affinity)
2. Externalize state to Redis/database
3. Replicate state across instances (Hazelcast, Infinispan)
4. Session clustering

```java
// Externalize session state
@EnableRedisHttpSession
@Configuration
public class SessionConfig {
    @Bean
    public RedisConnectionFactory connectionFactory() {
        return new LettuceConnectionFactory();
    }
}
```

**Decision:** Default to stateless. Only go stateful when latency requirements make external state stores unacceptable, and then externalize that state to a shared store.

---

## Summary: Pattern Selection Quick Reference

| Scenario | Pattern(s) |
|----------|------------|
| Multiple algorithms, select at runtime | Strategy |
| Add behavior without modifying class | Decorator, Proxy (AOP) |
| Complex object construction | Builder |
| Decouple event producer/consumer | Observer, Mediator |
| Workflow with defined states | State Machine |
| Distributed transaction | Saga + Outbox |
| Read/write optimization | CQRS |
| Full audit trail | Event Sourcing |
| Legacy migration | Strangler Fig + ACL |
| External system integration | Adapter + ACL |
| Reliable messaging | Outbox + Idempotent Receiver + DLQ |
| Complex business domain | DDD + Hexagonal Architecture |
| Cross-cutting concerns | Proxy (AOP), Chain of Responsibility |
