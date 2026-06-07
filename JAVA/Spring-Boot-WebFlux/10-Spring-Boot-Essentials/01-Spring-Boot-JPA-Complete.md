# Spring Boot, JPA, and Hibernate — Complete Reference for LLD

---

## 1. Spring Boot Core Concepts

### 1.1 The Main Annotation

```java
@SpringBootApplication  // = @Configuration + @EnableAutoConfiguration + @ComponentScan
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

**What each part does:**
- `@Configuration` — marks class as source of bean definitions
- `@EnableAutoConfiguration` — Spring Boot auto-configures beans based on classpath
- `@ComponentScan` — scans current package and sub-packages for @Component classes

---

### 1.2 Stereotype Annotations

```java
@Component          // Generic Spring-managed bean
@Service            // Business logic layer (semantic — no extra behavior)
@Repository         // Data access layer (translates persistence exceptions)
@Controller         // MVC controller (returns views)
@RestController     // = @Controller + @ResponseBody (returns JSON/XML)
```

**Why use them?**
- Auto-detected by `@ComponentScan`
- `@Repository` adds automatic exception translation (PersistenceExceptionTranslationPostProcessor)
- `@Service` and `@Component` are functionally identical — semantic difference only

---

### 1.3 Dependency Injection

#### Constructor Injection (PREFERRED)

```java
@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final PaymentService paymentService;

    // @Autowired is optional when there's only one constructor (Spring 4.3+)
    public OrderService(OrderRepository orderRepository, PaymentService paymentService) {
        this.orderRepository = orderRepository;
        this.paymentService = paymentService;
    }
}
```

**Why constructor injection is preferred:**
- Fields can be `final` (immutable, thread-safe)
- Impossible to create object without dependencies (no NullPointerException)
- Easy to test — just pass mocks in constructor
- No reflection magic needed

#### Setter Injection

```java
@Service
public class NotificationService {

    private EmailSender emailSender;

    @Autowired
    public void setEmailSender(EmailSender emailSender) {
        this.emailSender = emailSender;
    }
}
```

#### Field Injection (AVOID)

```java
@Service
public class BadService {
    @Autowired  // Don't do this — hard to test, hides dependencies
    private SomeRepository repo;
}
```

#### @Qualifier and @Primary

```java
public interface NotificationSender {
    void send(String message);
}

@Service
@Primary  // Default when no qualifier specified
public class EmailNotificationSender implements NotificationSender {
    public void send(String message) { /* send email */ }
}

@Service("sms")
public class SmsNotificationSender implements NotificationSender {
    public void send(String message) { /* send SMS */ }
}

@Service
public class AlertService {

    private final NotificationSender sender;

    // Use @Qualifier to pick specific implementation
    public AlertService(@Qualifier("sms") NotificationSender sender) {
        this.sender = sender;
    }
}
```

---

### 1.4 Configuration and Properties

#### application.yml

```yaml
spring:
  profiles:
    active: dev
  datasource:
    url: jdbc:postgresql://localhost:5432/mydb
    username: admin
    password: secret
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: validate  # none | validate | update | create | create-drop
    show-sql: true
    properties:
      hibernate:
        format_sql: true
        dialect: org.hibernate.dialect.PostgreSQLDialect

server:
  port: 8080

app:
  jwt:
    secret: my-secret-key
    expiration: 86400000
```

#### @Value Injection

```java
@Service
public class JwtService {

    @Value("${app.jwt.secret}")
    private String secretKey;

    @Value("${app.jwt.expiration:3600000}")  // Default value after colon
    private long expiration;
}
```

#### @ConfigurationProperties (Type-safe)

```java
@Configuration
@ConfigurationProperties(prefix = "app.jwt")
@Validated
public class JwtProperties {

    @NotBlank
    private String secret;

    @Min(60000)
    private long expiration;

    // Getters and setters required
    public String getSecret() { return secret; }
    public void setSecret(String secret) { this.secret = secret; }
    public long getExpiration() { return expiration; }
    public void setExpiration(long expiration) { this.expiration = expiration; }
}
```

#### @Bean and @Configuration

```java
@Configuration
public class AppConfig {

    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }

    @Bean
    @Profile("dev")  // Only active in dev profile
    public CommandLineRunner seedData(UserRepository repo) {
        return args -> {
            repo.save(new User("admin", "admin@test.com"));
        };
    }
}
```

---

### 1.5 @Transactional Deep Dive

```java
@Service
public class TransferService {

    private final AccountRepository accountRepo;

    public TransferService(AccountRepository accountRepo) {
        this.accountRepo = accountRepo;
    }

    @Transactional(
        propagation = Propagation.REQUIRED,        // Default
        isolation = Isolation.READ_COMMITTED,       // Default for most DBs
        rollbackFor = Exception.class,              // Rollback on checked exceptions too
        timeout = 30,                               // Seconds
        readOnly = false
    )
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        Account from = accountRepo.findById(fromId)
            .orElseThrow(() -> new AccountNotFoundException(fromId));
        Account to = accountRepo.findById(toId)
            .orElseThrow(() -> new AccountNotFoundException(toId));

        from.debit(amount);
        to.credit(amount);

        accountRepo.save(from);
        accountRepo.save(to);
    }

    @Transactional(readOnly = true)  // Optimization: no dirty checking
    public Account getAccount(Long id) {
        return accountRepo.findById(id)
            .orElseThrow(() -> new AccountNotFoundException(id));
    }
}
```

**Propagation Levels:**

| Level | Behavior |
|-------|----------|
| `REQUIRED` | Join existing TX, or create new one (DEFAULT) |
| `REQUIRES_NEW` | Always create new TX, suspend existing |
| `NESTED` | Execute within nested TX (savepoint) |
| `SUPPORTS` | Join if TX exists, else run non-transactional |
| `NOT_SUPPORTED` | Always run non-transactional, suspend existing |
| `MANDATORY` | Must run within existing TX, else throw exception |
| `NEVER` | Must NOT run within TX, else throw exception |

**Isolation Levels:**

| Level | Dirty Read | Non-Repeatable Read | Phantom Read |
|-------|-----------|-------------------|-------------|
| `READ_UNCOMMITTED` | Yes | Yes | Yes |
| `READ_COMMITTED` | No | Yes | Yes |
| `REPEATABLE_READ` | No | No | Yes |
| `SERIALIZABLE` | No | No | No |

**Important:** `@Transactional` only works on **public** methods called from **outside** the class (Spring AOP proxy limitation).

```java
@Service
public class OrderService {

    // THIS WON'T WORK — self-invocation bypasses proxy
    public void processOrder(Order order) {
        this.saveOrder(order);  // @Transactional is IGNORED here
    }

    @Transactional
    public void saveOrder(Order order) {
        // ...
    }
}
```

---

### 1.6 @Async and @Scheduled

```java
@Configuration
@EnableAsync
@EnableScheduling
public class AsyncConfig {

    @Bean
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(10);
        executor.setQueueCapacity(25);
        executor.setThreadNamePrefix("async-");
        executor.initialize();
        return executor;
    }
}

@Service
public class EmailService {

    @Async
    public CompletableFuture<Void> sendEmailAsync(String to, String body) {
        // Runs in separate thread
        sendEmail(to, body);
        return CompletableFuture.completedFuture(null);
    }

    @Scheduled(fixedRate = 60000)  // Every 60 seconds
    public void cleanupExpiredTokens() {
        // Periodic cleanup
    }

    @Scheduled(cron = "0 0 2 * * ?")  // Every day at 2 AM
    public void generateDailyReport() {
        // Daily report generation
    }
}
```

---

## 2. JPA / Hibernate

### 2.1 Entity Mapping

```java
@Entity
@Table(name = "users", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"email"}),
    @UniqueConstraint(columnNames = {"username"})
})
@EntityListeners(AuditingEntityListener.class)  // For @CreatedDate etc.
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)  // Auto-increment
    private Long id;

    @Column(name = "username", nullable = false, unique = true, length = 50)
    private String username;

    @Column(nullable = false, unique = true)
    private String email;

    @Column(nullable = false)
    private String password;

    @Enumerated(EnumType.STRING)  // Store as "ADMIN", not 0
    @Column(nullable = false)
    private Role role;

    @Column(name = "is_active")
    private boolean active = true;

    @Lob  // Large object — TEXT or BLOB
    private String bio;

    @Transient  // Not stored in DB
    private String confirmPassword;

    @CreatedDate
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    // Constructors
    protected User() {} // JPA requires no-arg constructor

    public User(String username, String email) {
        this.username = username;
        this.email = email;
    }

    // Getters and setters...
}

public enum Role {
    USER, ADMIN, MODERATOR
}
```

**@GeneratedValue Strategies:**

| Strategy | Description |
|----------|-------------|
| `IDENTITY` | Auto-increment (DB manages). Disables batch inserts. |
| `SEQUENCE` | DB sequence (preferred for PostgreSQL). Allows batch inserts. |
| `TABLE` | Simulates sequence with a table (portable but slow). |
| `AUTO` | Hibernate picks strategy based on DB dialect. |

```java
// Sequence strategy (recommended for production)
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "user_seq")
@SequenceGenerator(name = "user_seq", sequenceName = "user_sequence", allocationSize = 50)
private Long id;
```

---

### 2.2 Relationships

#### @OneToOne

```java
@Entity
@Table(name = "users")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String username;

    @OneToOne(mappedBy = "user", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private UserProfile profile;
}

@Entity
@Table(name = "user_profiles")
public class UserProfile {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String fullName;
    private String avatarUrl;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", referencedColumnName = "id")
    private User user;
}
```

#### @OneToMany / @ManyToOne (Most Common)

```java
@Entity
@Table(name = "orders")
public class Order {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "order_number", unique = true)
    private String orderNumber;

    @ManyToOne(fetch = FetchType.LAZY)  // LAZY is NOT default for @ManyToOne!
    @JoinColumn(name = "customer_id", nullable = false)
    private Customer customer;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderItem> items = new ArrayList<>();

    @Enumerated(EnumType.STRING)
    private OrderStatus status;

    private BigDecimal totalAmount;

    // Helper methods to maintain bidirectional consistency
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
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    private int quantity;
    private BigDecimal unitPrice;
}

@Entity
@Table(name = "customers")
public class Customer {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;
    private String email;

    @OneToMany(mappedBy = "customer", cascade = CascadeType.ALL)
    private List<Order> orders = new ArrayList<>();
}
```

#### @ManyToMany

```java
@Entity
@Table(name = "students")
public class Student {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;

    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(
        name = "student_courses",  // Junction table
        joinColumns = @JoinColumn(name = "student_id"),
        inverseJoinColumns = @JoinColumn(name = "course_id")
    )
    private Set<Course> courses = new HashSet<>();
}

@Entity
@Table(name = "courses")
public class Course {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String title;

    @ManyToMany(mappedBy = "courses")
    private Set<Student> students = new HashSet<>();
}
```

**Important Defaults:**

| Annotation | Default FetchType |
|-----------|-------------------|
| `@OneToOne` | EAGER |
| `@ManyToOne` | EAGER |
| `@OneToMany` | LAZY |
| `@ManyToMany` | LAZY |

**Best Practice:** Always set `FetchType.LAZY` explicitly on `@ManyToOne` and `@OneToOne`.

#### CascadeType

```java
@OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
private List<OrderItem> items = new ArrayList<>();
```

| CascadeType | Effect |
|------------|--------|
| `PERSIST` | Save child when parent is saved |
| `MERGE` | Update child when parent is updated |
| `REMOVE` | Delete child when parent is deleted |
| `REFRESH` | Refresh child when parent is refreshed |
| `DETACH` | Detach child when parent is detached |
| `ALL` | All of the above |

`orphanRemoval = true` — removes child from DB when removed from parent's collection.

---

### 2.3 Spring Data JPA Repository

```java
public interface UserRepository extends JpaRepository<User, Long> {

    // ========== Derived Query Methods ==========

    Optional<User> findByEmail(String email);

    Optional<User> findByUsername(String username);

    List<User> findByRole(Role role);

    List<User> findByActiveTrue();

    List<User> findByActiveFalse();

    List<User> findByUsernameContainingIgnoreCase(String keyword);

    List<User> findByCreatedAtAfter(LocalDateTime date);

    List<User> findByRoleAndActiveTrue(Role role);

    long countByRole(Role role);

    boolean existsByEmail(String email);

    void deleteByUsername(String username);

    List<User> findByAgeGreaterThanEqual(int age);

    List<User> findByAgeBetween(int min, int max);

    List<User> findTop5ByOrderByCreatedAtDesc();  // Top 5 newest users

    // ========== @Query with JPQL ==========

    @Query("SELECT u FROM User u WHERE u.email = :email AND u.active = true")
    Optional<User> findActiveByEmail(@Param("email") String email);

    @Query("SELECT u FROM User u WHERE u.role = :role ORDER BY u.createdAt DESC")
    List<User> findByRoleSorted(@Param("role") Role role);

    @Query("SELECT u FROM User u JOIN FETCH u.orders WHERE u.id = :id")
    Optional<User> findByIdWithOrders(@Param("id") Long id);

    @Query("SELECT new com.example.dto.UserSummary(u.id, u.username, u.email) FROM User u")
    List<UserSummary> findAllSummaries();

    // ========== Native SQL ==========

    @Query(value = "SELECT * FROM users WHERE email LIKE %:domain", nativeQuery = true)
    List<User> findByEmailDomain(@Param("domain") String domain);

    // ========== @Modifying (UPDATE/DELETE) ==========

    @Modifying
    @Transactional
    @Query("UPDATE User u SET u.active = false WHERE u.lastLoginAt < :cutoff")
    int deactivateInactiveUsers(@Param("cutoff") LocalDateTime cutoff);

    @Modifying
    @Transactional
    @Query("DELETE FROM User u WHERE u.active = false AND u.createdAt < :date")
    int deleteOldInactiveUsers(@Param("date") LocalDateTime date);
}
```

#### Pagination and Sorting

```java
public interface ProductRepository extends JpaRepository<Product, Long> {

    Page<Product> findByCategory(String category, Pageable pageable);

    @Query("SELECT p FROM Product p WHERE p.price BETWEEN :min AND :max")
    Page<Product> findByPriceRange(
        @Param("min") BigDecimal min,
        @Param("max") BigDecimal max,
        Pageable pageable
    );
}

// Usage in service
@Service
public class ProductService {

    private final ProductRepository productRepo;

    public ProductService(ProductRepository productRepo) {
        this.productRepo = productRepo;
    }

    public Page<ProductDto> getProducts(int page, int size, String sortBy, String direction) {
        Sort sort = direction.equalsIgnoreCase("desc")
            ? Sort.by(sortBy).descending()
            : Sort.by(sortBy).ascending();

        Pageable pageable = PageRequest.of(page, size, sort);
        Page<Product> products = productRepo.findAll(pageable);

        return products.map(this::toDto);
    }

    public Page<ProductDto> searchByCategory(String category, int page, int size) {
        Pageable pageable = PageRequest.of(page, size, Sort.by("name").ascending());
        return productRepo.findByCategory(category, pageable).map(this::toDto);
    }

    private ProductDto toDto(Product p) {
        return new ProductDto(p.getId(), p.getName(), p.getPrice(), p.getCategory());
    }
}
```

#### Projections

```java
// Interface-based projection (Spring generates proxy)
public interface UserSummaryProjection {
    Long getId();
    String getUsername();
    String getEmail();
}

// Class-based projection (DTO)
public record UserSummary(Long id, String username, String email) {}

public interface UserRepository extends JpaRepository<User, Long> {

    // Interface projection
    List<UserSummaryProjection> findByActiveTrue();

    // DTO projection with @Query
    @Query("SELECT new com.example.dto.UserSummary(u.id, u.username, u.email) FROM User u WHERE u.role = :role")
    List<UserSummary> findSummariesByRole(@Param("role") Role role);
}
```

#### Specifications (Dynamic Queries)

```java
public class UserSpecifications {

    public static Specification<User> hasRole(Role role) {
        return (root, query, cb) -> cb.equal(root.get("role"), role);
    }

    public static Specification<User> isActive() {
        return (root, query, cb) -> cb.isTrue(root.get("active"));
    }

    public static Specification<User> emailContains(String domain) {
        return (root, query, cb) -> cb.like(root.get("email"), "%" + domain + "%");
    }

    public static Specification<User> createdAfter(LocalDateTime date) {
        return (root, query, cb) -> cb.greaterThan(root.get("createdAt"), date);
    }
}

// Repository must extend JpaSpecificationExecutor
public interface UserRepository extends JpaRepository<User, Long>, JpaSpecificationExecutor<User> {
}

// Usage — compose specifications dynamically
@Service
public class UserSearchService {

    private final UserRepository userRepo;

    public Page<User> search(Role role, String emailDomain, Boolean active, Pageable pageable) {
        Specification<User> spec = Specification.where(null);

        if (role != null) {
            spec = spec.and(UserSpecifications.hasRole(role));
        }
        if (emailDomain != null) {
            spec = spec.and(UserSpecifications.emailContains(emailDomain));
        }
        if (Boolean.TRUE.equals(active)) {
            spec = spec.and(UserSpecifications.isActive());
        }

        return userRepo.findAll(spec, pageable);
    }
}
```

---

### 2.4 JPA Entity Lifecycle

```
   new Entity()          persist()           detach() / close()
       |                    |                       |
  [TRANSIENT] ---------> [MANAGED] ------------> [DETACHED]
                            |                       |
                            |    merge()            |
                            | <---------------------+
                            |
                     remove()|
                            v
                        [REMOVED]
```

| State | In Persistence Context? | In Database? |
|-------|------------------------|-------------|
| Transient | No | No |
| Managed | Yes | Yes (after flush) |
| Detached | No | Yes |
| Removed | Yes (marked for deletion) | Will be deleted on flush |

```java
@Service
public class EntityLifecycleDemo {

    @PersistenceContext
    private EntityManager em;

    @Transactional
    public void demonstrate() {
        // TRANSIENT — not tracked, not in DB
        User user = new User("john", "john@test.com");

        // MANAGED — tracked by persistence context, will be synced to DB
        em.persist(user);

        // Changes to managed entities are auto-detected (dirty checking)
        user.setEmail("john.doe@test.com");  // No explicit save needed!

        // DETACHED — no longer tracked
        em.detach(user);

        // Changes to detached entities are NOT tracked
        user.setEmail("ignored@test.com");  // This won't be saved

        // Re-attach by merging (returns NEW managed instance)
        User managedUser = em.merge(user);

        // REMOVED — will be deleted on flush/commit
        em.remove(managedUser);

        // Flush sends SQL to DB (within transaction)
        em.flush();

        // Clear removes all entities from persistence context
        em.clear();
    }
}
```

---

### 2.5 N+1 Problem and Solutions

#### The Problem

```java
// N+1 Problem Example:
@Transactional(readOnly = true)
public List<OrderDto> getAllOrders() {
    List<Order> orders = orderRepo.findAll();  // 1 query: SELECT * FROM orders

    return orders.stream()
        .map(order -> {
            // N queries: SELECT * FROM order_items WHERE order_id = ?
            // One query PER order to load items!
            List<OrderItem> items = order.getItems();
            return new OrderDto(order, items);
        })
        .toList();
}
// Total: 1 + N queries (where N = number of orders)
```

#### Solution 1: JOIN FETCH (JPQL)

```java
public interface OrderRepository extends JpaRepository<Order, Long> {

    @Query("SELECT DISTINCT o FROM Order o JOIN FETCH o.items JOIN FETCH o.customer")
    List<Order> findAllWithItemsAndCustomer();

    @Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.id = :id")
    Optional<Order> findByIdWithItems(@Param("id") Long id);
}
```

#### Solution 2: @EntityGraph

```java
public interface OrderRepository extends JpaRepository<Order, Long> {

    @EntityGraph(attributePaths = {"items", "customer"})
    @Query("SELECT o FROM Order o")
    List<Order> findAllWithGraph();

    @EntityGraph(attributePaths = {"items", "items.product"})
    Optional<Order> findById(Long id);  // Override default findById
}

// Named EntityGraph on entity
@Entity
@NamedEntityGraph(
    name = "Order.withItems",
    attributeNodes = @NamedAttributeNode("items")
)
public class Order { /* ... */ }

// Usage
@EntityGraph(value = "Order.withItems")
List<Order> findByStatus(OrderStatus status);
```

#### Solution 3: @BatchSize

```java
@Entity
public class Order {

    @OneToMany(mappedBy = "order")
    @BatchSize(size = 20)  // Load items in batches of 20 (uses IN clause)
    private List<OrderItem> items;
}
// Instead of N queries, does ceil(N/20) queries
```

#### Solution 4: DTO Projection (Best for Read-Only)

```java
@Query("""
    SELECT new com.example.dto.OrderSummaryDto(
        o.id, o.orderNumber, o.totalAmount, c.name
    )
    FROM Order o JOIN o.customer c
    WHERE o.status = :status
    """)
Page<OrderSummaryDto> findOrderSummaries(@Param("status") OrderStatus status, Pageable pageable);
```

---

### 2.6 Auditing

```java
@Configuration
@EnableJpaAuditing
public class JpaConfig {

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
public abstract class BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @CreatedDate
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @CreatedBy
    @Column(name = "created_by", updatable = false)
    private String createdBy;

    @LastModifiedBy
    @Column(name = "updated_by")
    private String updatedBy;

    @Version  // Optimistic locking
    private Long version;

    // Getters and setters...
}

// All entities extend this
@Entity
@Table(name = "products")
public class Product extends BaseEntity {
    private String name;
    private BigDecimal price;
    // ...
}
```

---

## 3. REST API Design

### 3.1 Controller Layer

```java
@RestController
@RequestMapping("/api/v1/users")
@Validated
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public ResponseEntity<Page<UserResponse>> getAllUsers(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "createdAt") String sortBy,
            @RequestParam(defaultValue = "desc") String direction) {

        Page<UserResponse> users = userService.getAllUsers(page, size, sortBy, direction);
        return ResponseEntity.ok(users);
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserResponse> getUserById(@PathVariable Long id) {
        UserResponse user = userService.getUserById(id);
        return ResponseEntity.ok(user);
    }

    @PostMapping
    public ResponseEntity<UserResponse> createUser(@Valid @RequestBody CreateUserRequest request) {
        UserResponse created = userService.createUser(request);
        URI location = URI.create("/api/v1/users/" + created.id());
        return ResponseEntity.created(location).body(created);
    }

    @PutMapping("/{id}")
    public ResponseEntity<UserResponse> updateUser(
            @PathVariable Long id,
            @Valid @RequestBody UpdateUserRequest request) {
        UserResponse updated = userService.updateUser(id, request);
        return ResponseEntity.ok(updated);
    }

    @PatchMapping("/{id}")
    public ResponseEntity<UserResponse> patchUser(
            @PathVariable Long id,
            @RequestBody Map<String, Object> updates) {
        UserResponse patched = userService.patchUser(id, updates);
        return ResponseEntity.ok(patched);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteUser(@PathVariable Long id) {
        userService.deleteUser(id);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/search")
    public ResponseEntity<Page<UserResponse>> searchUsers(
            @RequestParam(required = false) String name,
            @RequestParam(required = false) String email,
            @RequestParam(required = false) Role role,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {

        Page<UserResponse> results = userService.search(name, email, role, page, size);
        return ResponseEntity.ok(results);
    }
}
```

### 3.2 DTOs (Request/Response)

```java
// Request DTO with validation
public record CreateUserRequest(
    @NotBlank(message = "Username is required")
    @Size(min = 3, max = 50, message = "Username must be 3-50 characters")
    String username,

    @NotBlank(message = "Email is required")
    @Email(message = "Invalid email format")
    String email,

    @NotBlank(message = "Password is required")
    @Size(min = 8, message = "Password must be at least 8 characters")
    @Pattern(regexp = "^(?=.*[A-Z])(?=.*[a-z])(?=.*\\d).*$",
             message = "Password must contain uppercase, lowercase, and digit")
    String password,

    @NotNull(message = "Role is required")
    Role role
) {}

public record UpdateUserRequest(
    @NotBlank @Size(min = 3, max = 50)
    String username,

    @NotBlank @Email
    String email,

    @NotNull
    Role role
) {}

// Response DTO
public record UserResponse(
    Long id,
    String username,
    String email,
    Role role,
    boolean active,
    LocalDateTime createdAt
) {
    // Factory method from entity
    public static UserResponse from(User user) {
        return new UserResponse(
            user.getId(),
            user.getUsername(),
            user.getEmail(),
            user.getRole(),
            user.isActive(),
            user.getCreatedAt()
        );
    }
}
```

### 3.3 HTTP Status Codes

| Code | Meaning | When to Use |
|------|---------|-------------|
| `200 OK` | Success | GET, PUT, PATCH |
| `201 Created` | Resource created | POST (include Location header) |
| `204 No Content` | Success, no body | DELETE |
| `400 Bad Request` | Validation failed | Invalid input |
| `401 Unauthorized` | Not authenticated | Missing/invalid credentials |
| `403 Forbidden` | Not authorized | Insufficient permissions |
| `404 Not Found` | Resource not found | Entity doesn't exist |
| `409 Conflict` | Conflict | Duplicate email, optimistic lock failure |
| `422 Unprocessable Entity` | Semantic error | Valid syntax but business rule violation |
| `500 Internal Server Error` | Server error | Unexpected exception |

---

### 3.4 Exception Handling

```java
// Custom exception classes
public class ResourceNotFoundException extends RuntimeException {
    private final String resourceName;
    private final String fieldName;
    private final Object fieldValue;

    public ResourceNotFoundException(String resourceName, String fieldName, Object fieldValue) {
        super(String.format("%s not found with %s: '%s'", resourceName, fieldName, fieldValue));
        this.resourceName = resourceName;
        this.fieldName = fieldName;
        this.fieldValue = fieldValue;
    }
}

public class DuplicateResourceException extends RuntimeException {
    public DuplicateResourceException(String message) {
        super(message);
    }
}

public class BusinessRuleException extends RuntimeException {
    public BusinessRuleException(String message) {
        super(message);
    }
}

// Global exception handler
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ProblemDetail handleNotFound(ResourceNotFoundException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
            HttpStatus.NOT_FOUND, ex.getMessage()
        );
        problem.setTitle("Resource Not Found");
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }

    @ExceptionHandler(DuplicateResourceException.class)
    @ResponseStatus(HttpStatus.CONFLICT)
    public ProblemDetail handleDuplicate(DuplicateResourceException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
            HttpStatus.CONFLICT, ex.getMessage()
        );
        problem.setTitle("Duplicate Resource");
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ProblemDetail handleValidation(MethodArgumentNotValidException ex) {
        ProblemDetail problem = ProblemDetail.forStatus(HttpStatus.BAD_REQUEST);
        problem.setTitle("Validation Failed");

        Map<String, String> errors = new HashMap<>();
        ex.getBindingResult().getFieldErrors().forEach(error ->
            errors.put(error.getField(), error.getDefaultMessage())
        );
        problem.setProperty("errors", errors);
        return problem;
    }

    @ExceptionHandler(ConstraintViolationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ProblemDetail handleConstraintViolation(ConstraintViolationException ex) {
        ProblemDetail problem = ProblemDetail.forStatus(HttpStatus.BAD_REQUEST);
        problem.setTitle("Constraint Violation");

        Map<String, String> errors = new HashMap<>();
        ex.getConstraintViolations().forEach(violation ->
            errors.put(violation.getPropertyPath().toString(), violation.getMessage())
        );
        problem.setProperty("errors", errors);
        return problem;
    }

    @ExceptionHandler(OptimisticLockingFailureException.class)
    @ResponseStatus(HttpStatus.CONFLICT)
    public ProblemDetail handleOptimisticLock(OptimisticLockingFailureException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
            HttpStatus.CONFLICT, "Resource was modified by another user. Please retry."
        );
        problem.setTitle("Concurrent Modification");
        return problem;
    }

    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ProblemDetail handleGeneral(Exception ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
            HttpStatus.INTERNAL_SERVER_ERROR, "An unexpected error occurred"
        );
        problem.setTitle("Internal Server Error");
        // Don't expose internal details in production
        return problem;
    }
}
```

### 3.5 Custom Validator

```java
// Custom annotation
@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = UniqueEmailValidator.class)
public @interface UniqueEmail {
    String message() default "Email already exists";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

// Validator implementation
@Component
public class UniqueEmailValidator implements ConstraintValidator<UniqueEmail, String> {

    private final UserRepository userRepository;

    public UniqueEmailValidator(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public boolean isValid(String email, ConstraintValidatorContext context) {
        if (email == null) return true;  // Let @NotNull handle null
        return !userRepository.existsByEmail(email);
    }
}

// Usage
public record CreateUserRequest(
    @NotBlank String username,
    @NotBlank @Email @UniqueEmail String email,
    @NotBlank @Size(min = 8) String password
) {}
```

---

## 4. Security Basics

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtFilter;

    public SecurityConfig(JwtAuthenticationFilter jwtFilter) {
        this.jwtFilter = jwtFilter;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/auth/**").permitAll()
                .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.GET, "/api/v1/products/**").permitAll()
                .anyRequest().authenticated()
            )
            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)
            .build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration config)
            throws Exception {
        return config.getAuthenticationManager();
    }
}
```

### JWT Authentication Filter

```java
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private final UserDetailsService userDetailsService;

    public JwtAuthenticationFilter(JwtService jwtService, UserDetailsService userDetailsService) {
        this.jwtService = jwtService;
        this.userDetailsService = userDetailsService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        String authHeader = request.getHeader("Authorization");

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            filterChain.doFilter(request, response);
            return;
        }

        String token = authHeader.substring(7);
        String username = jwtService.extractUsername(token);

        if (username != null && SecurityContextHolder.getContext().getAuthentication() == null) {
            UserDetails userDetails = userDetailsService.loadUserByUsername(username);

            if (jwtService.isTokenValid(token, userDetails)) {
                UsernamePasswordAuthenticationToken authToken =
                    new UsernamePasswordAuthenticationToken(
                        userDetails, null, userDetails.getAuthorities()
                    );
                authToken.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                SecurityContextHolder.getContext().setAuthentication(authToken);
            }
        }

        filterChain.doFilter(request, response);
    }
}
```

### JWT Service

```java
@Service
public class JwtService {

    @Value("${app.jwt.secret}")
    private String secretKey;

    @Value("${app.jwt.expiration}")
    private long expiration;

    public String generateToken(UserDetails userDetails) {
        return Jwts.builder()
            .subject(userDetails.getUsername())
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + expiration))
            .signWith(getSigningKey())
            .compact();
    }

    public String extractUsername(String token) {
        return extractClaim(token, Claims::getSubject);
    }

    public boolean isTokenValid(String token, UserDetails userDetails) {
        String username = extractUsername(token);
        return username.equals(userDetails.getUsername()) && !isTokenExpired(token);
    }

    private boolean isTokenExpired(String token) {
        return extractClaim(token, Claims::getExpiration).before(new Date());
    }

    private <T> T extractClaim(String token, Function<Claims, T> resolver) {
        Claims claims = Jwts.parser()
            .verifyWith(getSigningKey())
            .build()
            .parseSignedClaims(token)
            .getPayload();
        return resolver.apply(claims);
    }

    private SecretKey getSigningKey() {
        byte[] keyBytes = Decoders.BASE64.decode(secretKey);
        return Keys.hmacShaKeyFor(keyBytes);
    }
}
```

---

## 5. Testing

### 5.1 Repository Layer (@DataJpaTest)

```java
@DataJpaTest  // Loads only JPA components, uses in-memory H2 by default
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)  // Use real DB
class UserRepositoryTest {

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    void findByEmail_shouldReturnUser_whenExists() {
        // Given
        User user = new User("john", "john@test.com");
        user.setRole(Role.USER);
        user.setActive(true);
        entityManager.persistAndFlush(user);

        // When
        Optional<User> found = userRepository.findByEmail("john@test.com");

        // Then
        assertThat(found).isPresent();
        assertThat(found.get().getUsername()).isEqualTo("john");
    }

    @Test
    void findByEmail_shouldReturnEmpty_whenNotExists() {
        Optional<User> found = userRepository.findByEmail("nobody@test.com");
        assertThat(found).isEmpty();
    }

    @Test
    void findByRole_shouldReturnAllUsersWithRole() {
        entityManager.persist(createUser("admin1", "a1@test.com", Role.ADMIN));
        entityManager.persist(createUser("admin2", "a2@test.com", Role.ADMIN));
        entityManager.persist(createUser("user1", "u1@test.com", Role.USER));
        entityManager.flush();

        List<User> admins = userRepository.findByRole(Role.ADMIN);

        assertThat(admins).hasSize(2);
        assertThat(admins).allMatch(u -> u.getRole() == Role.ADMIN);
    }

    private User createUser(String username, String email, Role role) {
        User user = new User(username, email);
        user.setRole(role);
        user.setActive(true);
        return user;
    }
}
```

### 5.2 Service Layer (Unit Test)

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @InjectMocks
    private UserService userService;

    @Test
    void createUser_shouldReturnCreatedUser() {
        // Given
        CreateUserRequest request = new CreateUserRequest("john", "john@test.com", "Pass123!", Role.USER);

        when(userRepository.existsByEmail("john@test.com")).thenReturn(false);
        when(passwordEncoder.encode("Pass123!")).thenReturn("encoded_password");
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> {
            User saved = invocation.getArgument(0);
            // Simulate DB setting ID
            ReflectionTestUtils.setField(saved, "id", 1L);
            return saved;
        });

        // When
        UserResponse response = userService.createUser(request);

        // Then
        assertThat(response.username()).isEqualTo("john");
        assertThat(response.email()).isEqualTo("john@test.com");
        verify(userRepository).save(any(User.class));
    }

    @Test
    void createUser_shouldThrowException_whenEmailExists() {
        CreateUserRequest request = new CreateUserRequest("john", "existing@test.com", "Pass123!", Role.USER);
        when(userRepository.existsByEmail("existing@test.com")).thenReturn(true);

        assertThatThrownBy(() -> userService.createUser(request))
            .isInstanceOf(DuplicateResourceException.class)
            .hasMessageContaining("Email already exists");

        verify(userRepository, never()).save(any());
    }

    @Test
    void getUserById_shouldThrowNotFound_whenUserDoesNotExist() {
        when(userRepository.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.getUserById(99L))
            .isInstanceOf(ResourceNotFoundException.class);
    }
}
```

### 5.3 Controller Layer (@WebMvcTest)

```java
@WebMvcTest(UserController.class)
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private UserService userService;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void createUser_shouldReturn201_whenValidRequest() throws Exception {
        CreateUserRequest request = new CreateUserRequest("john", "john@test.com", "Pass123!", Role.USER);
        UserResponse response = new UserResponse(1L, "john", "john@test.com", Role.USER, true, LocalDateTime.now());

        when(userService.createUser(any())).thenReturn(response);

        mockMvc.perform(post("/api/v1/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.id").value(1))
            .andExpect(jsonPath("$.username").value("john"))
            .andExpect(jsonPath("$.email").value("john@test.com"))
            .andExpect(header().exists("Location"));
    }

    @Test
    void createUser_shouldReturn400_whenInvalidRequest() throws Exception {
        CreateUserRequest request = new CreateUserRequest("", "invalid-email", "short", null);

        mockMvc.perform(post("/api/v1/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.title").value("Validation Failed"))
            .andExpect(jsonPath("$.errors.username").exists())
            .andExpect(jsonPath("$.errors.email").exists());
    }

    @Test
    void getUserById_shouldReturn404_whenNotFound() throws Exception {
        when(userService.getUserById(99L))
            .thenThrow(new ResourceNotFoundException("User", "id", 99L));

        mockMvc.perform(get("/api/v1/users/99"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.title").value("Resource Not Found"));
    }

    @Test
    void getAllUsers_shouldReturnPagedResults() throws Exception {
        Page<UserResponse> page = new PageImpl<>(List.of(
            new UserResponse(1L, "john", "john@test.com", Role.USER, true, LocalDateTime.now())
        ));

        when(userService.getAllUsers(0, 20, "createdAt", "desc")).thenReturn(page);

        mockMvc.perform(get("/api/v1/users")
                .param("page", "0")
                .param("size", "20"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.content").isArray())
            .andExpect(jsonPath("$.content[0].username").value("john"))
            .andExpect(jsonPath("$.totalElements").value(1));
    }
}
```

### 5.4 Integration Test (@SpringBootTest)

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers  // Use real PostgreSQL in Docker
@ActiveProfile("test")
class UserIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
        .withDatabaseName("testdb");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private UserRepository userRepository;

    @BeforeEach
    void setUp() {
        userRepository.deleteAll();
    }

    @Test
    void fullCrudLifecycle() {
        // Create
        CreateUserRequest createRequest = new CreateUserRequest("john", "john@test.com", "Pass123!", Role.USER);
        ResponseEntity<UserResponse> createResponse = restTemplate.postForEntity(
            "/api/v1/users", createRequest, UserResponse.class
        );

        assertThat(createResponse.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        Long userId = createResponse.getBody().id();

        // Read
        ResponseEntity<UserResponse> getResponse = restTemplate.getForEntity(
            "/api/v1/users/" + userId, UserResponse.class
        );
        assertThat(getResponse.getBody().username()).isEqualTo("john");

        // Update
        UpdateUserRequest updateRequest = new UpdateUserRequest("john_updated", "john@test.com", Role.ADMIN);
        restTemplate.put("/api/v1/users/" + userId, updateRequest);

        UserResponse updated = restTemplate.getForObject("/api/v1/users/" + userId, UserResponse.class);
        assertThat(updated.username()).isEqualTo("john_updated");

        // Delete
        restTemplate.delete("/api/v1/users/" + userId);
        ResponseEntity<Void> deleted = restTemplate.getForEntity(
            "/api/v1/users/" + userId, Void.class
        );
        assertThat(deleted.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }
}
```

---

## 6. Common LLD Patterns in Spring Boot

### 6.1 Layered Architecture

```
┌─────────────────────────────────────────┐
│           Controller Layer               │  ← HTTP concerns, validation
│   @RestController, DTOs, ResponseEntity  │
├─────────────────────────────────────────┤
│             Service Layer                │  ← Business logic, transactions
│   @Service, @Transactional              │
├─────────────────────────────────────────┤
│           Repository Layer               │  ← Data access
│   @Repository, JpaRepository            │
├─────────────────────────────────────────┤
│              Database                    │
└─────────────────────────────────────────┘
```

### 6.2 Strategy Pattern with @Qualifier

```java
// Strategy interface
public interface PaymentProcessor {
    PaymentResult process(PaymentRequest request);
    PaymentMethod getSupportedMethod();
}

@Service
public class CreditCardProcessor implements PaymentProcessor {
    public PaymentResult process(PaymentRequest request) {
        // Credit card logic
        return new PaymentResult(true, "CC-" + UUID.randomUUID());
    }
    public PaymentMethod getSupportedMethod() { return PaymentMethod.CREDIT_CARD; }
}

@Service
public class PayPalProcessor implements PaymentProcessor {
    public PaymentResult process(PaymentRequest request) {
        // PayPal logic
        return new PaymentResult(true, "PP-" + UUID.randomUUID());
    }
    public PaymentMethod getSupportedMethod() { return PaymentMethod.PAYPAL; }
}

@Service
public class UpiProcessor implements PaymentProcessor {
    public PaymentResult process(PaymentRequest request) {
        // UPI logic
        return new PaymentResult(true, "UPI-" + UUID.randomUUID());
    }
    public PaymentMethod getSupportedMethod() { return PaymentMethod.UPI; }
}

// Strategy registry — Spring injects ALL implementations
@Service
public class PaymentService {

    private final Map<PaymentMethod, PaymentProcessor> processors;

    public PaymentService(List<PaymentProcessor> processorList) {
        this.processors = processorList.stream()
            .collect(Collectors.toMap(
                PaymentProcessor::getSupportedMethod,
                Function.identity()
            ));
    }

    public PaymentResult processPayment(PaymentRequest request) {
        PaymentProcessor processor = processors.get(request.method());
        if (processor == null) {
            throw new UnsupportedOperationException(
                "No processor for: " + request.method()
            );
        }
        return processor.process(request);
    }
}
```

### 6.3 Factory Pattern with ApplicationContext

```java
public interface NotificationChannel {
    void send(Notification notification);
}

@Component("email")
public class EmailChannel implements NotificationChannel {
    public void send(Notification notification) { /* send email */ }
}

@Component("sms")
public class SmsChannel implements NotificationChannel {
    public void send(Notification notification) { /* send SMS */ }
}

@Component("push")
public class PushChannel implements NotificationChannel {
    public void send(Notification notification) { /* send push */ }
}

// Factory using ApplicationContext
@Service
public class NotificationFactory {

    private final ApplicationContext context;

    public NotificationFactory(ApplicationContext context) {
        this.context = context;
    }

    public NotificationChannel getChannel(String channelType) {
        try {
            return context.getBean(channelType, NotificationChannel.class);
        } catch (NoSuchBeanDefinitionException e) {
            throw new IllegalArgumentException("Unknown channel: " + channelType);
        }
    }
}

// Usage
@Service
public class NotificationService {

    private final NotificationFactory factory;

    public NotificationService(NotificationFactory factory) {
        this.factory = factory;
    }

    public void notify(String channelType, Notification notification) {
        NotificationChannel channel = factory.getChannel(channelType);
        channel.send(notification);
    }
}
```

### 6.4 Observer Pattern with @EventListener

```java
// Event class
public record OrderPlacedEvent(Long orderId, Long customerId, BigDecimal amount) {}

public record PaymentCompletedEvent(Long orderId, String transactionId) {}

// Publisher
@Service
public class OrderService {

    private final OrderRepository orderRepo;
    private final ApplicationEventPublisher eventPublisher;

    public OrderService(OrderRepository orderRepo, ApplicationEventPublisher eventPublisher) {
        this.orderRepo = orderRepo;
        this.eventPublisher = eventPublisher;
    }

    @Transactional
    public Order placeOrder(CreateOrderRequest request) {
        Order order = new Order(request.customerId(), request.items());
        order = orderRepo.save(order);

        // Publish event — listeners are decoupled
        eventPublisher.publishEvent(new OrderPlacedEvent(
            order.getId(), order.getCustomerId(), order.getTotalAmount()
        ));

        return order;
    }
}

// Listeners — separate concerns
@Component
public class InventoryListener {

    @EventListener
    public void handleOrderPlaced(OrderPlacedEvent event) {
        // Reserve inventory
        System.out.println("Reserving inventory for order: " + event.orderId());
    }
}

@Component
public class NotificationListener {

    @Async  // Run in separate thread
    @EventListener
    public void handleOrderPlaced(OrderPlacedEvent event) {
        // Send confirmation email
        System.out.println("Sending confirmation for order: " + event.orderId());
    }
}

@Component
public class AnalyticsListener {

    @Async
    @EventListener
    public void handleOrderPlaced(OrderPlacedEvent event) {
        // Track analytics
        System.out.println("Tracking order event: " + event.orderId());
    }

    @EventListener
    public void handlePaymentCompleted(PaymentCompletedEvent event) {
        // Track payment
        System.out.println("Payment tracked: " + event.transactionId());
    }
}

// Transactional event listener — executes only after TX commits
@Component
public class PostCommitListener {

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleAfterCommit(OrderPlacedEvent event) {
        // Safe to send external notifications here
        // Order is guaranteed to be persisted
    }
}
```

### 6.5 Builder + DTO Pattern

```java
// Lombok-free builder (for interview clarity)
public class OrderResponse {
    private final Long id;
    private final String orderNumber;
    private final String customerName;
    private final BigDecimal totalAmount;
    private final OrderStatus status;
    private final List<OrderItemResponse> items;
    private final LocalDateTime createdAt;

    private OrderResponse(Builder builder) {
        this.id = builder.id;
        this.orderNumber = builder.orderNumber;
        this.customerName = builder.customerName;
        this.totalAmount = builder.totalAmount;
        this.status = builder.status;
        this.items = builder.items;
        this.createdAt = builder.createdAt;
    }

    public static Builder builder() { return new Builder(); }

    public static class Builder {
        private Long id;
        private String orderNumber;
        private String customerName;
        private BigDecimal totalAmount;
        private OrderStatus status;
        private List<OrderItemResponse> items;
        private LocalDateTime createdAt;

        public Builder id(Long id) { this.id = id; return this; }
        public Builder orderNumber(String v) { this.orderNumber = v; return this; }
        public Builder customerName(String v) { this.customerName = v; return this; }
        public Builder totalAmount(BigDecimal v) { this.totalAmount = v; return this; }
        public Builder status(OrderStatus v) { this.status = v; return this; }
        public Builder items(List<OrderItemResponse> v) { this.items = v; return this; }
        public Builder createdAt(LocalDateTime v) { this.createdAt = v; return this; }
        public OrderResponse build() { return new OrderResponse(this); }
    }

    // Getters...

    // Mapper method
    public static OrderResponse from(Order order) {
        return OrderResponse.builder()
            .id(order.getId())
            .orderNumber(order.getOrderNumber())
            .customerName(order.getCustomer().getName())
            .totalAmount(order.getTotalAmount())
            .status(order.getStatus())
            .items(order.getItems().stream()
                .map(OrderItemResponse::from)
                .toList())
            .createdAt(order.getCreatedAt())
            .build();
    }
}
```

### 6.6 Complete CRUD Example — User Management

```java
// ============ Entity ============

@Entity
@Table(name = "users")
@EntityListeners(AuditingEntityListener.class)
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 50)
    private String username;

    @Column(nullable = false, unique = true)
    private String email;

    @Column(nullable = false)
    private String password;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Role role = Role.USER;

    @Column(name = "is_active")
    private boolean active = true;

    @CreatedDate
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @Version
    private Long version;

    protected User() {}

    public User(String username, String email, String password, Role role) {
        this.username = username;
        this.email = email;
        this.password = password;
        this.role = role;
    }

    // Getters and setters
    public Long getId() { return id; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
    public Role getRole() { return role; }
    public void setRole(Role role) { this.role = role; }
    public boolean isActive() { return active; }
    public void setActive(boolean active) { this.active = active; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
}

// ============ Repository ============

public interface UserRepository extends JpaRepository<User, Long>, JpaSpecificationExecutor<User> {

    Optional<User> findByEmail(String email);
    Optional<User> findByUsername(String username);
    boolean existsByEmail(String email);
    boolean existsByUsername(String username);

    @Query("SELECT u FROM User u WHERE u.active = true AND u.role = :role")
    Page<User> findActiveByRole(@Param("role") Role role, Pageable pageable);
}

// ============ Service ============

@Service
@Transactional
public class UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public UserService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional(readOnly = true)
    public Page<UserResponse> getAllUsers(int page, int size, String sortBy, String direction) {
        Sort sort = direction.equalsIgnoreCase("desc")
            ? Sort.by(sortBy).descending()
            : Sort.by(sortBy).ascending();

        Pageable pageable = PageRequest.of(page, size, sort);
        return userRepository.findAll(pageable).map(UserResponse::from);
    }

    @Transactional(readOnly = true)
    public UserResponse getUserById(Long id) {
        User user = userRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("User", "id", id));
        return UserResponse.from(user);
    }

    public UserResponse createUser(CreateUserRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new DuplicateResourceException("Email already exists: " + request.email());
        }
        if (userRepository.existsByUsername(request.username())) {
            throw new DuplicateResourceException("Username already exists: " + request.username());
        }

        User user = new User(
            request.username(),
            request.email(),
            passwordEncoder.encode(request.password()),
            request.role()
        );

        User saved = userRepository.save(user);
        return UserResponse.from(saved);
    }

    public UserResponse updateUser(Long id, UpdateUserRequest request) {
        User user = userRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("User", "id", id));

        // Check uniqueness if email/username changed
        if (!user.getEmail().equals(request.email()) && userRepository.existsByEmail(request.email())) {
            throw new DuplicateResourceException("Email already exists: " + request.email());
        }

        user.setUsername(request.username());
        user.setEmail(request.email());
        user.setRole(request.role());

        User saved = userRepository.save(user);
        return UserResponse.from(saved);
    }

    public UserResponse patchUser(Long id, Map<String, Object> updates) {
        User user = userRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("User", "id", id));

        updates.forEach((key, value) -> {
            switch (key) {
                case "username" -> user.setUsername((String) value);
                case "email" -> user.setEmail((String) value);
                case "active" -> user.setActive((Boolean) value);
                case "role" -> user.setRole(Role.valueOf((String) value));
            }
        });

        User saved = userRepository.save(user);
        return UserResponse.from(saved);
    }

    public void deleteUser(Long id) {
        if (!userRepository.existsById(id)) {
            throw new ResourceNotFoundException("User", "id", id);
        }
        userRepository.deleteById(id);
    }

    @Transactional(readOnly = true)
    public Page<UserResponse> search(String name, String email, Role role, int page, int size) {
        Specification<User> spec = Specification.where(null);

        if (name != null && !name.isBlank()) {
            spec = spec.and((root, query, cb) ->
                cb.like(cb.lower(root.get("username")), "%" + name.toLowerCase() + "%"));
        }
        if (email != null && !email.isBlank()) {
            spec = spec.and((root, query, cb) ->
                cb.like(cb.lower(root.get("email")), "%" + email.toLowerCase() + "%"));
        }
        if (role != null) {
            spec = spec.and((root, query, cb) -> cb.equal(root.get("role"), role));
        }

        Pageable pageable = PageRequest.of(page, size, Sort.by("createdAt").descending());
        return userRepository.findAll(spec, pageable).map(UserResponse::from);
    }
}

// ============ Controller ============
// (See section 3.1 above for the full controller)
```

---

## 7. Quick Reference — Common Pitfalls

| Pitfall | Problem | Solution |
|---------|---------|----------|
| N+1 queries | Lazy loading fires N extra queries | Use JOIN FETCH or @EntityGraph |
| Self-invocation | @Transactional ignored on internal calls | Extract to separate bean |
| LazyInitializationException | Access lazy field outside TX | Keep access within @Transactional or use DTO projection |
| equals/hashCode on entities | Breaks Set/Map with proxy objects | Use business key or ID-based (not generated before persist) |
| Cascade on @ManyToMany | Deleting one side deletes shared data | Avoid CascadeType.REMOVE on @ManyToMany |
| EAGER fetching | Loads unnecessary data always | Always use LAZY, fetch when needed |
| Missing no-arg constructor | JPA can't instantiate entity | Add `protected Entity() {}` |
| EnumType.ORDINAL | Enum order change breaks DB data | Always use `EnumType.STRING` |
| Not using @Version | Lost updates in concurrent writes | Add optimistic locking with @Version |
| Returning entities from controllers | Exposes internal structure, circular refs | Always use DTOs |

---

## 8. Project Structure

```
src/main/java/com/example/myapp/
├── MyAppApplication.java
├── config/
│   ├── SecurityConfig.java
│   ├── JpaConfig.java
│   └── AsyncConfig.java
├── controller/
│   ├── UserController.java
│   ├── OrderController.java
│   └── ProductController.java
├── service/
│   ├── UserService.java
│   ├── OrderService.java
│   └── PaymentService.java
├── repository/
│   ├── UserRepository.java
│   ├── OrderRepository.java
│   └── ProductRepository.java
├── entity/
│   ├── BaseEntity.java
│   ├── User.java
│   ├── Order.java
│   ├── OrderItem.java
│   └── Product.java
├── dto/
│   ├── request/
│   │   ├── CreateUserRequest.java
│   │   └── UpdateUserRequest.java
│   └── response/
│       ├── UserResponse.java
│       └── OrderResponse.java
├── exception/
│   ├── ResourceNotFoundException.java
│   ├── DuplicateResourceException.java
│   └── GlobalExceptionHandler.java
├── specification/
│   └── UserSpecifications.java
└── security/
    ├── JwtService.java
    └── JwtAuthenticationFilter.java
```

---

## 9. Key Dependencies (pom.xml)

```xml
<dependencies>
    <!-- Core -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-security</artifactId>
    </dependency>

    <!-- Database -->
    <dependency>
        <groupId>org.postgresql</groupId>
        <artifactId>postgresql</artifactId>
        <scope>runtime</scope>
    </dependency>

    <!-- JWT -->
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt-api</artifactId>
        <version>0.12.5</version>
    </dependency>
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt-impl</artifactId>
        <version>0.12.5</version>
        <scope>runtime</scope>
    </dependency>

    <!-- Test -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.testcontainers</groupId>
        <artifactId>postgresql</artifactId>
        <scope>test</scope>
    </dependency>
</dependencies>
```

---

## 10. Interview Tips

1. **Always use DTOs** — never expose entities directly from controllers
2. **Constructor injection** — mention it's preferred and why
3. **@Transactional placement** — on service layer, not repository or controller
4. **Lazy loading** — always set LAZY, explain N+1 and solutions
5. **Pagination** — always paginate list endpoints
6. **Exception handling** — use @ControllerAdvice for centralized handling
7. **Validation** — use Bean Validation annotations, not manual if-checks
8. **Layered architecture** — controller (thin) → service (business logic) → repository (data)
9. **Optimistic locking** — @Version for concurrent modification detection
10. **Auditing** — @CreatedDate, @LastModifiedDate with BaseEntity

---
