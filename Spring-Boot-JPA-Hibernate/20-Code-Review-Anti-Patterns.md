# Code Review Scenarios & Anti-Patterns (Staff Engineer / Architect Level)

## Anti-Pattern 1: God Transaction (External HTTP + Email + DB in One @Transactional)

### Bad Code
```java
@Service
public class OrderService {

    @Autowired private OrderRepository orderRepository;
    @Autowired private PaymentGatewayClient paymentClient;
    @Autowired private EmailService emailService;
    @Autowired private InventoryClient inventoryClient;
    @Autowired private AuditLogRepository auditLogRepository;

    @Transactional
    public OrderResponse createOrder(OrderRequest request) {
        // 1. Validate and save order
        Order order = new Order();
        order.setCustomerId(request.getCustomerId());
        order.setItems(mapItems(request.getItems()));
        order.setStatus(OrderStatus.PENDING);
        orderRepository.save(order);

        // 2. Call payment gateway (HTTP - 2-5 seconds)
        PaymentResult payment = paymentClient.charge(
            request.getPaymentMethod(), order.getTotal());
        order.setPaymentId(payment.getTransactionId());
        order.setStatus(OrderStatus.PAID);
        orderRepository.save(order);

        // 3. Reserve inventory (HTTP - 1-2 seconds)
        inventoryClient.reserve(order.getItems());

        // 4. Send confirmation email (SMTP - 1-3 seconds)
        emailService.sendOrderConfirmation(order);

        // 5. Write audit log
        auditLogRepository.save(new AuditLog("ORDER_CREATED", order.getId()));

        return OrderResponse.from(order);
    }
}
```

### Problems
1. **DB connection held 5-10 seconds** for external HTTP + SMTP calls
2. **Connection pool exhaustion** under load (10 connections × 8s = only 1.25 req/s)
3. **Partial failure leaves inconsistent state**: if email fails, entire transaction rolls back including successful payment
4. **Payment charged but order rolled back** — money taken, no order record
5. **No timeout on external calls** — if payment gateway hangs, connection held forever
6. **Unrelated operations coupled** — audit log failure kills the order

### Impact
- Connection pool exhaustion under moderate load
- Inconsistent state between systems (payment charged, order missing)
- Cascading failures when any external system is slow/down
- Users see timeouts even when the actual DB work takes 5ms

### Correct Code
```java
@Service
public class OrderService {

    @Autowired private OrderRepository orderRepository;
    @Autowired private ApplicationEventPublisher eventPublisher;

    @Transactional
    public Order createOrder(OrderRequest request) {
        // ONLY database work inside the transaction
        Order order = new Order();
        order.setCustomerId(request.getCustomerId());
        order.setItems(mapItems(request.getItems()));
        order.setStatus(OrderStatus.PENDING);
        Order saved = orderRepository.save(order);

        // Publish domain event — listeners run AFTER commit
        eventPublisher.publishEvent(new OrderCreatedEvent(saved.getId()));

        return saved;
    }
}

@Service
public class OrderOrchestrator {

    @Autowired private OrderService orderService;
    @Autowired private PaymentGatewayClient paymentClient;
    @Autowired private InventoryClient inventoryClient;

    // NO @Transactional — orchestrates steps with individual transactions
    public OrderResponse processOrder(OrderRequest request) {
        // Step 1: Create order (short transaction)
        Order order = orderService.createOrder(request);

        // Step 2: Charge payment (no DB connection held)
        PaymentResult payment = paymentClient.charge(
            request.getPaymentMethod(), order.getTotal());

        // Step 3: Update order with payment info (short transaction)
        orderService.markAsPaid(order.getId(), payment.getTransactionId());

        // Step 4: Reserve inventory (no DB connection held)
        try {
            inventoryClient.reserve(order.getItems());
        } catch (Exception e) {
            // Compensating transaction if inventory fails
            orderService.markAsFailedInventory(order.getId());
            paymentClient.refund(payment.getTransactionId());
            throw new OrderProcessingException("Inventory reservation failed", e);
        }

        return OrderResponse.from(order);
    }
}

// Email sent asynchronously via event listener
@Component
public class OrderEventListener {

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Async
    public void onOrderCreated(OrderCreatedEvent event) {
        emailService.sendOrderConfirmation(event.getOrderId());
    }
}
```

### PR Review Comment
> 🚫 This transaction holds a DB connection for 5-10s while doing HTTP calls and sending email. Under 20 concurrent users, this will exhaust the connection pool (default 10). External calls must happen OUTSIDE the transaction. Use an orchestrator pattern with compensating transactions, and move email to an async event listener.

---

## Anti-Pattern 2: N+1 in Disguise (Lazy Collections in DTO Mapping)

### Bad Code
```java
@RestController
public class TeamController {

    @Autowired private TeamRepository teamRepository;

    @GetMapping("/teams")
    public List<TeamDTO> getAllTeams() {
        List<Team> teams = teamRepository.findAll();  // 1 query

        return teams.stream()
            .map(this::toDTO)
            .toList();
    }

    private TeamDTO toDTO(Team team) {
        TeamDTO dto = new TeamDTO();
        dto.setName(team.getName());
        dto.setMemberCount(team.getMembers().size());  // LAZY LOAD per team
        dto.setProjectNames(
            team.getProjects().stream()  // LAZY LOAD per team
                .map(Project::getName)
                .toList()
        );
        dto.setLeaderName(team.getLeader().getFullName());  // LAZY LOAD per team
        return dto;
    }
}

@Entity
public class Team {
    @Id @GeneratedValue
    private Long id;
    private String name;

    @OneToMany(mappedBy = "team", fetch = FetchType.LAZY)
    private List<Member> members;

    @OneToMany(mappedBy = "team", fetch = FetchType.LAZY)
    private List<Project> projects;

    @ManyToOne(fetch = FetchType.LAZY)
    private Employee leader;
}
```

### Problems
1. **N+1 (actually N*3+1)**: For 50 teams → 1 + 50 + 50 + 50 = 151 queries
2. **Hidden by OSIV**: Works without error because OSIV keeps session open, masking the problem
3. **Performance degrades linearly with data**: 500 teams = 1501 queries
4. **Database connection held for entire mapping loop**
5. **Each lazy load is a separate round-trip** to DB

### Impact
- API response time: O(N) database round trips
- 50 teams → ~500ms, 500 teams → ~5 seconds
- Database connection held for entire duration
- Under load: connection pool exhaustion + high DB CPU

### Correct Code
```java
@RestController
public class TeamController {

    @Autowired private TeamRepository teamRepository;

    @GetMapping("/teams")
    public List<TeamDTO> getAllTeams() {
        // Option 1: JOIN FETCH query
        List<Team> teams = teamRepository.findAllWithMembersAndProjects();
        return teams.stream().map(this::toDTO).toList();
    }
}

public interface TeamRepository extends JpaRepository<Team, Long> {

    // Option 1: Single query with JOIN FETCH (watch for Cartesian product)
    @Query("SELECT DISTINCT t FROM Team t " +
           "LEFT JOIN FETCH t.members " +
           "LEFT JOIN FETCH t.leader")
    List<Team> findAllWithMembersAndLeader();

    // Option 2: EntityGraph
    @EntityGraph(attributePaths = {"members", "projects", "leader"})
    @Override
    List<Team> findAll();

    // Option 3: Best for DTOs - projection query (no entities loaded)
    @Query("SELECT new com.myapp.dto.TeamDTO(" +
           "t.name, SIZE(t.members), t.leader.fullName) " +
           "FROM Team t LEFT JOIN t.leader")
    List<TeamDTO> findAllTeamSummaries();
}

// Option 4: Use @BatchSize for cases where you can't change the query
@Entity
public class Team {
    @OneToMany(mappedBy = "team")
    @BatchSize(size = 100)  // Loads members for 100 teams in 1 query
    private List<Member> members;
}
```

### PR Review Comment
> 🚫 Classic N+1: `findAll()` loads 50 teams in 1 query, then `.getMembers()`, `.getProjects()`, and `.getLeader()` each trigger a lazy load per team = 151 queries. Use `@EntityGraph` or a `JOIN FETCH` query. Better yet, use a projection query that returns DTOs directly without loading entities.

---

## Anti-Pattern 3: Broken equals/hashCode (Using @Id for New Entities)

### Bad Code
```java
@Entity
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String productName;
    private int quantity;
    private BigDecimal price;

    @ManyToOne
    @JoinColumn(name = "order_id")
    private Order order;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        OrderItem that = (OrderItem) o;
        return Objects.equals(id, that.id);  // BUG: id is null before persist!
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);  // BUG: returns hash(null) = 0 for all new entities
    }
}

// Usage that breaks:
@Service
public class OrderService {

    @Transactional
    public void createOrder(OrderRequest request) {
        Order order = new Order();
        Set<OrderItem> items = new HashSet<>();

        for (ItemRequest ir : request.getItems()) {
            OrderItem item = new OrderItem();  // id is null
            item.setProductName(ir.getName());
            item.setQuantity(ir.getQuantity());
            item.setPrice(ir.getPrice());
            item.setOrder(order);
            items.add(item);  // All have hashCode=0, equals returns true for all!
        }

        order.setItems(items);  // Set may contain only 1 item regardless of how many added!
        orderRepository.save(order);
    }
}
```

### Problems
1. **All new entities have `id=null`** → `hashCode()` returns 0 for all → same bucket
2. **`equals()` returns true for all new entities** → Set deduplicates them incorrectly
3. **HashSet only stores one item** when multiple items are added before persist
4. **After persist, hashCode changes** (id gets value) → entity "lost" in HashSet (can't find it)
5. **Breaks `contains()`, `remove()`** on any collection after entity state change

### Impact
- Silent data loss: orders created with fewer items than expected
- Inconsistent behavior: works sometimes (with existing entities), fails with new ones
- Extremely hard to debug: no errors thrown, just wrong data

### Correct Code
```java
@Entity
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Use a natural/business key for equals/hashCode
    @Column(nullable = false, updatable = false)
    private UUID itemUuid = UUID.randomUUID();

    private String productName;
    private int quantity;
    private BigDecimal price;

    @ManyToOne
    @JoinColumn(name = "order_id")
    private Order order;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        OrderItem that = (OrderItem) o;
        return Objects.equals(itemUuid, that.itemUuid);
    }

    @Override
    public int hashCode() {
        return Objects.hash(itemUuid);  // Stable across entity lifecycle
    }
}

// Alternative: Use natural business key if available
@Entity
public class Employee {

    @Id @GeneratedValue
    private Long id;

    @Column(unique = true, nullable = false, updatable = false)
    private String employeeNumber;  // Natural key - assigned at creation

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Employee)) return false;
        Employee that = (Employee) o;
        return Objects.equals(employeeNumber, that.employeeNumber);
    }

    @Override
    public int hashCode() {
        return Objects.hash(employeeNumber);
    }
}

// Alternative 2: Fixed hashCode (Vlad Mihalcea recommendation)
@Entity
public class OrderItem {
    @Id @GeneratedValue
    private Long id;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof OrderItem)) return false;
        OrderItem that = (OrderItem) o;
        return id != null && Objects.equals(id, that.id);
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();  // Constant - all in same bucket but equals() differentiates
    }
}
```

### PR Review Comment
> 🚫 Using `@Id` in `equals()`/`hashCode()` breaks Set/Map operations for transient entities (id is null before persist). All new items have hashCode=0 and are considered equal — your `HashSet<OrderItem>` will silently drop items. Use a UUID business key or a natural key that's assigned at construction time.

---

## Anti-Pattern 4: CascadeType.ALL Everywhere

### Bad Code
```java
@Entity
public class Department {

    @Id @GeneratedValue
    private Long id;
    private String name;

    @OneToMany(mappedBy = "department", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Employee> employees = new ArrayList<>();

    @ManyToOne(cascade = CascadeType.ALL)
    @JoinColumn(name = "company_id")
    private Company company;

    @ManyToMany(cascade = CascadeType.ALL)
    @JoinTable(name = "department_tags")
    private Set<Tag> tags = new HashSet<>();
}

@Service
public class DepartmentService {

    @Transactional
    public void deleteDepartment(Long deptId) {
        Department dept = departmentRepository.findById(deptId).orElseThrow();
        departmentRepository.delete(dept);
        // CascadeType.ALL on company → DELETES THE ENTIRE COMPANY
        // CascadeType.ALL on tags → DELETES SHARED TAGS used by other departments
        // orphanRemoval on employees → deletes all employees (maybe intended, maybe not)
    }

    @Transactional
    public void addTagToDepartment(Long deptId, String tagName) {
        Department dept = departmentRepository.findById(deptId).orElseThrow();
        Tag tag = new Tag(tagName);
        dept.getTags().add(tag);
        departmentRepository.save(dept);
        // Creates a NEW tag entity even if one with same name exists
        // Over time: thousands of duplicate Tag records
    }
}
```

### Problems
1. **`CascadeType.ALL` on `@ManyToOne`**: Deleting department deletes the shared Company entity!
2. **`CascadeType.ALL` on `@ManyToMany`**: Deleting department deletes Tags used by OTHER departments
3. **Unintended cascade PERSIST**: Adding tags creates duplicates instead of referencing existing ones
4. **Performance**: Saving department dirty-checks ALL cascaded entities
5. **Hidden side effects**: Developer intends to save department, unknowingly modifies company/tags

### Impact
- Data loss: deleting one entity cascades deletion to shared entities
- Duplicate reference data (tags, categories) accumulating over time
- Unexpected `ConstraintViolationException` when cascaded delete violates FK from other entities
- Performance degradation as entity graphs grow

### Correct Code
```java
@Entity
public class Department {

    @Id @GeneratedValue
    private Long id;
    private String name;

    // CASCADE only on truly owned entities (parent→child lifecycle)
    @OneToMany(mappedBy = "department", cascade = {CascadeType.PERSIST, CascadeType.MERGE},
               orphanRemoval = true)
    private List<Employee> employees = new ArrayList<>();

    // NO CASCADE on @ManyToOne - Department doesn't own Company
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "company_id")
    private Company company;

    // NO CASCADE on @ManyToMany - Tags are shared, managed independently
    @ManyToMany
    @JoinTable(name = "department_tags")
    private Set<Tag> tags = new HashSet<>();

    // Helper methods for bidirectional relationship management
    public void addEmployee(Employee employee) {
        employees.add(employee);
        employee.setDepartment(this);
    }

    public void removeEmployee(Employee employee) {
        employees.remove(employee);
        employee.setDepartment(null);
    }
}

@Service
public class DepartmentService {

    @Transactional
    public void addTagToDepartment(Long deptId, String tagName) {
        Department dept = departmentRepository.findById(deptId).orElseThrow();
        // Find or create tag - managed independently
        Tag tag = tagRepository.findByName(tagName)
            .orElseGet(() -> tagRepository.save(new Tag(tagName)));
        dept.getTags().add(tag);
    }
}
```

### PR Review Comment
> 🚫 `CascadeType.ALL` on `@ManyToOne` and `@ManyToMany` is almost always wrong. Deleting this department will cascade-delete the Company (affecting all other departments) and all shared Tags. Use cascade only on true parent-child `@OneToMany` relationships where the child cannot exist without the parent. For shared entities, manage their lifecycle independently.

---

## Anti-Pattern 5: Entity Exposed as REST Response

### Bad Code
```java
@Entity
public class User {
    @Id @GeneratedValue
    private Long id;
    private String username;
    private String email;
    private String passwordHash;       // SECURITY: exposed in API!
    private String ssn;                // SECURITY: PII exposed!
    private LocalDateTime createdAt;
    private boolean isAdmin;

    @OneToMany(mappedBy = "user", fetch = FetchType.LAZY)
    @JsonManagedReference
    private List<Order> orders;

    @ManyToMany(fetch = FetchType.LAZY)
    private Set<Role> roles;

    @OneToOne(fetch = FetchType.LAZY)
    private UserProfile profile;

    // Getters and setters...
}

@RestController
public class UserController {

    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) {
        return userRepository.findById(id).orElseThrow();
        // Returns the ENTIRE entity as JSON including:
        // - passwordHash (security vulnerability)
        // - ssn (PII leak)
        // - All lazy associations (LazyInitializationException without OSIV)
        // - Internal DB schema exposed
    }

    @GetMapping("/users")
    public List<User> getAllUsers() {
        return userRepository.findAll();
        // Serializing lazy collections → either LazyInitializationException
        // or (with OSIV) N+1 queries loading all orders for all users
    }

    @PostMapping("/users")
    public User createUser(@RequestBody User user) {
        // Accepts ANY field including isAdmin = true!
        // Mass assignment vulnerability
        return userRepository.save(user);
    }
}
```

### Problems
1. **Security**: `passwordHash`, `ssn` exposed in API response
2. **Mass assignment**: Client can set `isAdmin=true` in POST body
3. **`LazyInitializationException`**: Without OSIV, serializing lazy collections fails
4. **Circular references**: `User→Orders→User` causes infinite JSON recursion
5. **API coupling to DB schema**: Renaming a column breaks all clients
6. **Over-fetching**: Every endpoint returns all fields regardless of need
7. **N+1**: Jackson serializer triggers lazy loads for all associations

### Impact
- Security vulnerabilities (data exposure, privilege escalation)
- Runtime exceptions in production (LazyInitializationException)
- API breaks on any entity refactoring
- Performance issues from unnecessary data loading

### Correct Code
```java
// DTOs — separate from entities
public record UserResponse(
    Long id,
    String username,
    String email,
    LocalDateTime createdAt
) {
    public static UserResponse from(User user) {
        return new UserResponse(user.getId(), user.getUsername(),
            user.getEmail(), user.getCreatedAt());
    }
}

public record CreateUserRequest(
    @NotBlank String username,
    @Email String email,
    @NotBlank String password
    // No isAdmin field — cannot be set by client
) {}

public record UserDetailResponse(
    Long id,
    String username,
    String email,
    List<String> roles,
    UserProfileResponse profile
) {}

@RestController
public class UserController {

    @Autowired private UserService userService;

    @GetMapping("/users/{id}")
    public UserResponse getUser(@PathVariable Long id) {
        User user = userService.findById(id);
        return UserResponse.from(user);
    }

    @GetMapping("/users/{id}/details")
    public UserDetailResponse getUserDetails(@PathVariable Long id) {
        // Use a dedicated query that fetches only needed associations
        return userService.getUserDetails(id);
    }

    @PostMapping("/users")
    public UserResponse createUser(@RequestBody @Valid CreateUserRequest request) {
        User user = userService.createUser(request);
        return UserResponse.from(user);
    }
}

@Service
public class UserService {

    @Transactional(readOnly = true)
    public UserDetailResponse getUserDetails(Long id) {
        User user = userRepository.findByIdWithRolesAndProfile(id)
            .orElseThrow(() -> new ResourceNotFoundException("User", id));
        return new UserDetailResponse(
            user.getId(),
            user.getUsername(),
            user.getEmail(),
            user.getRoles().stream().map(Role::getName).toList(),
            UserProfileResponse.from(user.getProfile())
        );
    }
}
```

### PR Review Comment
> 🚫 Never expose JPA entities directly as REST responses. This leaks `passwordHash` and `ssn` to every client, allows mass-assignment of `isAdmin`, couples your API contract to your DB schema, and will throw `LazyInitializationException` for associations. Use DTOs with explicit field mapping. Add `@JsonIgnore` as a safety net but don't rely on it as primary defense.

---

## Anti-Pattern 6: EAGER Fetch Everywhere

### Bad Code
```java
@Entity
public class Order {
    @Id @GeneratedValue
    private Long id;
    private LocalDateTime createdAt;
    private OrderStatus status;

    @ManyToOne(fetch = FetchType.EAGER)
    private Customer customer;

    @OneToMany(mappedBy = "order", fetch = FetchType.EAGER)
    private List<OrderItem> items;

    @OneToMany(mappedBy = "order", fetch = FetchType.EAGER)
    private List<Payment> payments;

    @OneToMany(mappedBy = "order", fetch = FetchType.EAGER)
    private List<ShipmentTracking> trackingEvents;

    @ManyToOne(fetch = FetchType.EAGER)
    private Warehouse warehouse;

    @OneToOne(fetch = FetchType.EAGER)
    private Invoice invoice;
}

@Entity
public class Customer {
    @Id @GeneratedValue
    private Long id;

    @OneToMany(mappedBy = "customer", fetch = FetchType.EAGER)
    private List<Order> orders;  // Loads ALL orders for the customer!

    @OneToMany(mappedBy = "customer", fetch = FetchType.EAGER)
    private List<Address> addresses;

    @OneToMany(mappedBy = "customer", fetch = FetchType.EAGER)
    private List<PaymentMethod> paymentMethods;
}

// Simple status check loads the ENTIRE object graph
@Service
public class OrderService {

    public boolean isOrderDelivered(Long orderId) {
        Order order = orderRepository.findById(orderId).orElseThrow();
        // Just needs order.status, but loads:
        // - Customer (+ all customer's other orders + addresses + payment methods)
        // - All OrderItems
        // - All Payments
        // - All TrackingEvents
        // - Warehouse
        // - Invoice
        return order.getStatus() == OrderStatus.DELIVERED;
    }
}
```

### Problems
1. **Loads entire object graph for every query** — even when you only need one field
2. **Cartesian product explosion**: Multiple EAGER collections generate massive JOINs
3. **`MultipleBagFetchException`**: Can't EAGER fetch two `List` collections simultaneously
4. **Circular loading**: Order→Customer→Orders→Customer→... (Hibernate handles, but with N+1)
5. **Cannot override EAGER at query time** — once EAGER, always EAGER
6. **Memory waste**: Loading KB of data to check a boolean field

### Impact
- Simple queries execute 10+ JOINs or N+1 selects
- Memory usage 10-100x higher than necessary
- `MultipleBagFetchException` runtime errors
- Cannot optimize individual use cases

### Correct Code
```java
@Entity
public class Order {
    @Id @GeneratedValue
    private Long id;
    private LocalDateTime createdAt;
    private OrderStatus status;

    @ManyToOne(fetch = FetchType.LAZY)  // LAZY is default for @ManyToOne
    private Customer customer;

    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)  // Already default
    private List<OrderItem> items;

    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<Payment> payments;

    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<ShipmentTracking> trackingEvents;

    @ManyToOne(fetch = FetchType.LAZY)
    private Warehouse warehouse;

    @OneToOne(fetch = FetchType.LAZY)
    private Invoice invoice;
}

// Fetch only what you need per use case
public interface OrderRepository extends JpaRepository<Order, Long> {

    // Use case: Order detail page (needs items + customer)
    @Query("SELECT o FROM Order o " +
           "JOIN FETCH o.customer " +
           "JOIN FETCH o.items " +
           "WHERE o.id = :id")
    Optional<Order> findByIdWithCustomerAndItems(@Param("id") Long id);

    // Use case: Shipping page (needs tracking + warehouse)
    @Query("SELECT o FROM Order o " +
           "JOIN FETCH o.trackingEvents " +
           "JOIN FETCH o.warehouse " +
           "WHERE o.id = :id")
    Optional<Order> findByIdWithShipping(@Param("id") Long id);

    // Use case: Just need status — don't load entity at all
    @Query("SELECT o.status FROM Order o WHERE o.id = :id")
    Optional<OrderStatus> findStatusById(@Param("id") Long id);
}

@Service
public class OrderService {

    public boolean isOrderDelivered(Long orderId) {
        // Single column query - no entity loaded
        return orderRepository.findStatusById(orderId)
            .map(status -> status == OrderStatus.DELIVERED)
            .orElseThrow();
    }
}
```

### PR Review Comment
> 🚫 `FetchType.EAGER` on all associations creates a "Fetch Everything" pattern. Loading an Order now requires 6+ JOINs and pulls in the entire Customer (with all their other orders). EAGER cannot be overridden per-query. Default everything to LAZY and use `JOIN FETCH` or `@EntityGraph` for specific use cases. For the status check, use a scalar projection.

---

## Anti-Pattern 7: @Transactional on Private Method / Self-Invocation

### Bad Code
```java
@Service
public class PaymentService {

    @Autowired private PaymentRepository paymentRepository;
    @Autowired private LedgerRepository ledgerRepository;

    public void processPayments(List<PaymentRequest> requests) {
        for (PaymentRequest request : requests) {
            processSinglePayment(request);  // Self-invocation — proxy NOT involved!
        }
    }

    @Transactional  // THIS DOES NOTHING — called from within same class
    private void processSinglePayment(PaymentRequest request) {
        Payment payment = new Payment(request);
        paymentRepository.save(payment);

        LedgerEntry entry = new LedgerEntry(payment);
        ledgerRepository.save(entry);

        if (payment.getAmount().compareTo(BigDecimal.valueOf(10000)) > 0) {
            throw new ComplianceException("Amount exceeds limit");
            // Developer expects rollback of payment + ledger entry
            // But no transaction is active — data is already committed via auto-commit!
        }
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void auditPayment(Long paymentId) {
        // Called from processPayments — self-invocation, REQUIRES_NEW is ignored
        // Runs in the SAME transaction (or no transaction) as caller
    }
}
```

### Problems
1. **`@Transactional` on private method is ignored** — Spring proxies can't intercept private methods
2. **Self-invocation bypasses proxy** — even public `@Transactional` methods don't work when called from within the same class
3. **No transaction active** — saves go through without rollback capability
4. **`Propagation.REQUIRES_NEW` ignored** — doesn't create new transaction on self-call
5. **Silent failure** — no error message, just wrong behavior

### Impact
- Data inconsistency: partial writes committed without rollback on exception
- Compliance violations: large payments saved without proper transaction boundary
- Difficult to debug: works in unit tests (no proxy), fails in production

### Correct Code
```java
@Service
public class PaymentService {

    @Autowired private PaymentProcessor paymentProcessor;  // Separate bean for proxy

    public void processPayments(List<PaymentRequest> requests) {
        for (PaymentRequest request : requests) {
            // Call through another bean — Spring proxy IS involved
            paymentProcessor.processSinglePayment(request);
        }
    }
}

@Service
public class PaymentProcessor {

    @Autowired private PaymentRepository paymentRepository;
    @Autowired private LedgerRepository ledgerRepository;

    @Transactional  // Works — called through proxy from different bean
    public void processSinglePayment(PaymentRequest request) {
        Payment payment = new Payment(request);
        paymentRepository.save(payment);

        LedgerEntry entry = new LedgerEntry(payment);
        ledgerRepository.save(entry);

        if (payment.getAmount().compareTo(BigDecimal.valueOf(10000)) > 0) {
            throw new ComplianceException("Amount exceeds limit");
            // Now correctly rolls back both payment and ledger entry
        }
    }
}

// Alternative: Use TransactionTemplate for programmatic control
@Service
public class PaymentService {

    @Autowired private TransactionTemplate transactionTemplate;

    public void processPayments(List<PaymentRequest> requests) {
        for (PaymentRequest request : requests) {
            transactionTemplate.execute(status -> {
                processSinglePayment(request);  // Runs in transaction
                return null;
            });
        }
    }

    private void processSinglePayment(PaymentRequest request) {
        // No annotation needed — transaction managed by TransactionTemplate
        Payment payment = new Payment(request);
        paymentRepository.save(payment);
        // ...
    }
}
```

### PR Review Comment
> 🚫 `@Transactional` on a private method does nothing (Spring AOP can't proxy private methods). Even if made public, self-invocation (`this.processSinglePayment()`) bypasses the proxy — no transaction is created. Extract to a separate `@Service` bean or use `TransactionTemplate` for programmatic control.

---

## Anti-Pattern 8: @Version Without Retry Logic

### Bad Code
```java
@Entity
public class Product {
    @Id @GeneratedValue
    private Long id;

    @Version
    private Long version;

    private String name;
    private BigDecimal price;
    private int stockQuantity;
}

@RestController
public class ProductController {

    @Autowired private ProductService productService;

    @PutMapping("/products/{id}")
    public ResponseEntity<ProductResponse> updateProduct(
            @PathVariable Long id, @RequestBody ProductUpdateRequest request) {
        // If another transaction updated this product, user gets HTTP 500
        // with a stack trace in the response
        Product product = productService.updateProduct(id, request);
        return ResponseEntity.ok(ProductResponse.from(product));
    }
}

@Service
public class ProductService {

    @Transactional
    public Product updateProduct(Long id, ProductUpdateRequest request) {
        Product product = productRepository.findById(id).orElseThrow();
        product.setName(request.getName());
        product.setPrice(request.getPrice());
        return productRepository.save(product);
        // Throws ObjectOptimisticLockingFailureException if version mismatch
        // No handling — bubbles up as 500 Internal Server Error
    }
}
```

### Problems
1. **Raw exception exposed to client** — ugly 500 error with stack trace
2. **No retry mechanism** — user must manually retry
3. **Lost user input** — if form data was complex, user has to re-enter
4. **No conflict information** — user doesn't know what changed
5. **High failure rate in concurrent environments** — e.g., popular product being edited by multiple admins

### Impact
- Poor user experience: cryptic 500 errors
- Data entry frustration: users lose their work
- Support tickets: "save keeps failing"
- Workaround: users stop using the system or refresh obsessively before saving

### Correct Code
```java
@RestController
public class ProductController {

    @PutMapping("/products/{id}")
    public ResponseEntity<?> updateProduct(
            @PathVariable Long id,
            @RequestBody ProductUpdateRequest request) {
        try {
            Product product = productService.updateProduct(id, request);
            return ResponseEntity.ok(ProductResponse.from(product));
        } catch (OptimisticLockConflictException e) {
            // Return 409 Conflict with helpful information
            return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ConflictResponse(
                    "Product was modified by another user",
                    e.getCurrentVersion(),
                    ProductResponse.from(e.getCurrentState())
                ));
        }
    }
}

@Service
public class ProductService {

    private static final int MAX_RETRIES = 3;

    @Retryable(
        retryFor = OptimisticLockingFailureException.class,
        maxAttempts = MAX_RETRIES,
        backoff = @Backoff(delay = 50, multiplier = 2, random = true)
    )
    @Transactional
    public Product updateProduct(Long id, ProductUpdateRequest request) {
        Product product = productRepository.findById(id).orElseThrow();
        product.setName(request.getName());
        product.setPrice(request.getPrice());
        return productRepository.save(product);
    }

    @Recover
    public Product recoverFromOptimisticLock(
            OptimisticLockingFailureException ex, Long id, ProductUpdateRequest request) {
        // After max retries, throw a domain exception with current state
        Product current = productRepository.findById(id).orElseThrow();
        throw new OptimisticLockConflictException(
            "Conflict after " + MAX_RETRIES + " retries",
            current.getVersion(),
            current
        );
    }
}

// For API consumers that send version — reject stale updates immediately
@PutMapping("/products/{id}")
public ResponseEntity<?> updateProduct(
        @PathVariable Long id,
        @RequestHeader("If-Match") Long expectedVersion,  // Client sends expected version
        @RequestBody ProductUpdateRequest request) {

    Product product = productService.findById(id);
    if (!product.getVersion().equals(expectedVersion)) {
        return ResponseEntity.status(HttpStatus.PRECONDITION_FAILED)
            .header("ETag", product.getVersion().toString())
            .body(ProductResponse.from(product));
    }

    Product updated = productService.updateProduct(id, request);
    return ResponseEntity.ok()
        .header("ETag", updated.getVersion().toString())
        .body(ProductResponse.from(updated));
}
```

### PR Review Comment
> 🚫 `@Version` without retry or conflict handling means users get raw 500 errors on concurrent edits. Add `@Retryable` for automatic retries on `OptimisticLockingFailureException`, and return HTTP 409 with the current state after max retries. Consider using `If-Match`/`ETag` headers for explicit version passing from the client.

---

## Anti-Pattern 9: External HTTP Call Inside @Transactional

### Bad Code
```java
@Service
public class UserRegistrationService {

    @Autowired private UserRepository userRepository;
    @Autowired private AddressValidationClient addressClient;
    @Autowired private CreditCheckClient creditClient;
    @Autowired private WelcomeEmailClient emailClient;

    @Transactional
    public User registerUser(RegistrationRequest request) {
        // Validate address via external API (500ms - 3s)
        AddressResult address = addressClient.validate(request.getAddress());
        if (!address.isValid()) {
            throw new InvalidAddressException("Address not deliverable");
        }

        // Check credit score via external API (1-5s)
        CreditScore score = creditClient.check(request.getSsn());
        if (score.getScore() < 600) {
            throw new CreditCheckFailedException("Credit score too low");
        }

        // Save user (5ms)
        User user = new User(request);
        user.setAddress(address.getNormalized());
        user.setCreditTier(score.getTier());
        userRepository.save(user);

        // Send welcome email via external API (500ms - 2s)
        emailClient.sendWelcome(user.getEmail(), user.getName());

        return user;
        // Total: DB connection held for 2-10 SECONDS
    }
}
```

### Problems
1. **DB connection held 2-10 seconds** — most of it idle during HTTP I/O
2. **Connection pool exhaustion** under moderate load
3. **Cascading failure**: If address API is slow, ALL endpoints starve of connections
4. **Unnecessary rollback scope**: Email failure rolls back valid user creation
5. **Read-write transaction for mostly read/external operations**
6. **No timeout on HTTP calls** — if credit check hangs, connection held indefinitely

### Impact
- With pool size 10 and 5s avg hold time: max throughput = 2 registrations/second
- Any external API degradation takes down the entire application
- Users experience timeouts on unrelated endpoints (shared pool)

### Correct Code
```java
@Service
public class UserRegistrationService {

    @Autowired private UserRepository userRepository;
    @Autowired private AddressValidationClient addressClient;
    @Autowired private CreditCheckClient creditClient;
    @Autowired private ApplicationEventPublisher eventPublisher;

    // NO @Transactional — orchestration method
    public User registerUser(RegistrationRequest request) {
        // Step 1: External validations — no DB connection needed
        AddressResult address = addressClient.validate(request.getAddress());
        if (!address.isValid()) {
            throw new InvalidAddressException("Address not deliverable");
        }

        CreditScore score = creditClient.check(request.getSsn());
        if (score.getScore() < 600) {
            throw new CreditCheckFailedException("Credit score too low");
        }

        // Step 2: DB write — short transaction, connection held <10ms
        User user = saveUser(request, address, score);

        // Step 3: Post-commit actions — async, no DB connection
        eventPublisher.publishEvent(new UserRegisteredEvent(user.getId()));

        return user;
    }

    @Transactional  // Short transaction — only DB operations
    protected User saveUser(RegistrationRequest request, AddressResult address, CreditScore score) {
        User user = new User(request);
        user.setAddress(address.getNormalized());
        user.setCreditTier(score.getTier());
        return userRepository.save(user);
    }
}

// Async event listener for email — decoupled from main flow
@Component
public class UserRegistrationEventListener {

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onUserRegistered(UserRegisteredEvent event) {
        emailClient.sendWelcome(event.getUserId());
    }
}
```

### PR Review Comment
> 🚫 This transaction holds a DB connection for 2-10 seconds while calling 3 external APIs. Move all HTTP calls OUTSIDE the transaction. Pattern: validate externally first → short DB transaction → async post-commit events. The email especially should never be in the transaction — its failure shouldn't roll back a valid registration.

---

## Anti-Pattern 10: 100K Entities Saved in Loop Without Batching

### Bad Code
```java
@Service
public class DataImportService {

    @Autowired private ProductRepository productRepository;

    @Transactional
    public void importProducts(List<ProductCSVRow> csvRows) {
        // csvRows has 100,000 entries
        for (ProductCSVRow row : csvRows) {
            Product product = new Product();
            product.setName(row.getName());
            product.setSku(row.getSku());
            product.setPrice(row.getPrice());
            product.setCategory(row.getCategory());

            productRepository.save(product);  // Individual INSERT per entity
        }
        // 100,000 individual INSERT statements
        // Persistence context holds 100,000 entities in memory
        // Single massive transaction — locks held for minutes
        // OOM likely before commit
    }
}
```

### Problems
1. **100K individual INSERT statements** — no JDBC batching
2. **Persistence context holds 100K entities** — GBs of memory
3. **Single transaction** — all-or-nothing, timeout risk, holds locks for minutes
4. **No progress visibility** — if it fails at row 99,999, everything is lost
5. **Auto-flush before each query** if any SELECT happens mid-loop
6. **GenerationType.IDENTITY disables batching** — Hibernate can't batch with IDENTITY

### Impact
- OOM crash with large datasets
- Transaction timeout (default 30s may not be enough for 100K inserts)
- Database lock contention for minutes
- If any row fails, entire import is lost

### Correct Code
```java
@Service
public class DataImportService {

    @Autowired private EntityManagerFactory emf;
    @PersistenceContext private EntityManager em;

    private static final int BATCH_SIZE = 50;

    // Option 1: Manual batching with EntityManager
    @Transactional
    public ImportResult importProducts(List<ProductCSVRow> csvRows) {
        int count = 0;
        for (ProductCSVRow row : csvRows) {
            Product product = new Product();
            product.setName(row.getName());
            product.setSku(row.getSku());
            product.setPrice(row.getPrice());

            em.persist(product);

            if (++count % BATCH_SIZE == 0) {
                em.flush();   // Execute batch INSERT
                em.clear();   // Release entities from persistence context (free memory)
            }
        }
        em.flush();
        em.clear();
        return new ImportResult(count, 0);
    }

    // Option 2: Chunked transactions (better for very large imports)
    public ImportResult importProductsChunked(List<ProductCSVRow> csvRows) {
        AtomicInteger successCount = new AtomicInteger(0);
        AtomicInteger failCount = new AtomicInteger(0);

        Lists.partition(csvRows, 500).forEach(chunk -> {
            try {
                importChunk(chunk);
                successCount.addAndGet(chunk.size());
            } catch (Exception e) {
                log.error("Chunk failed, {} rows skipped", chunk.size(), e);
                failCount.addAndGet(chunk.size());
            }
        });

        return new ImportResult(successCount.get(), failCount.get());
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void importChunk(List<ProductCSVRow> chunk) {
        for (ProductCSVRow row : chunk) {
            Product product = new Product();
            product.setName(row.getName());
            product.setSku(row.getSku());
            product.setPrice(row.getPrice());
            em.persist(product);
        }
        // Flush happens at commit — batch INSERT for 500 rows
    }

    // Option 3: JdbcTemplate for maximum performance (skip JPA overhead)
    @Autowired private JdbcTemplate jdbcTemplate;

    public void importProductsJdbc(List<ProductCSVRow> csvRows) {
        String sql = "INSERT INTO products (name, sku, price, category) VALUES (?, ?, ?, ?)";

        jdbcTemplate.batchUpdate(sql, csvRows, 1000, (ps, row) -> {
            ps.setString(1, row.getName());
            ps.setString(2, row.getSku());
            ps.setBigDecimal(3, row.getPrice());
            ps.setString(4, row.getCategory());
        });
        // Executes in batches of 1000, ~100x faster than individual saves
    }
}

// Required configuration for JPA batching:
// application.yml:
// spring.jpa.properties.hibernate.jdbc.batch_size: 50
// spring.jpa.properties.hibernate.order_inserts: true
// spring.jpa.properties.hibernate.order_updates: true
// spring.jpa.properties.hibernate.jdbc.batch_versioned_data: true
//
// IMPORTANT: GenerationType.IDENTITY disables batching!
// Use GenerationType.SEQUENCE with allocationSize:
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "product_seq")
@SequenceGenerator(name = "product_seq", sequenceName = "product_seq", allocationSize = 50)
private Long id;
```

### PR Review Comment
> 🚫 Saving 100K entities one-by-one: no JDBC batching, persistence context holding all entities (OOM risk), single giant transaction. Use batch processing: `flush()`+`clear()` every 50 rows, enable `hibernate.jdbc.batch_size=50`, and switch from `IDENTITY` to `SEQUENCE` generation. For pure imports without entity logic, prefer `JdbcTemplate.batchUpdate()` — it's 100x faster.

---

## Anti-Pattern 11: String Concatenation in JPQL (SQL Injection + No Plan Cache)

### Bad Code
```java
@Repository
public class ProductSearchRepository {

    @PersistenceContext
    private EntityManager em;

    public List<Product> searchProducts(String name, String category, BigDecimal minPrice) {
        StringBuilder jpql = new StringBuilder("SELECT p FROM Product p WHERE 1=1");

        if (name != null) {
            jpql.append(" AND p.name LIKE '%" + name + "%'");  // SQL INJECTION!
        }
        if (category != null) {
            jpql.append(" AND p.category = '" + category + "'");  // SQL INJECTION!
        }
        if (minPrice != null) {
            jpql.append(" AND p.price >= " + minPrice);
        }

        return em.createQuery(jpql.toString(), Product.class).getResultList();
    }

    // Another common mistake: concatenation in @Query
    public List<Product> findByDynamicField(String fieldName, String value) {
        String jpql = "SELECT p FROM Product p WHERE p." + fieldName + " = '" + value + "'";
        return em.createQuery(jpql, Product.class).getResultList();
    }
}
```

### Problems
1. **SQL Injection**: `name = "'; DROP TABLE products; --"` executes destructive SQL
2. **No query plan caching**: Every unique string is a new query → DB parses every time
3. **No PreparedStatement caching**: JDBC driver can't reuse statements
4. **Hibernate query plan cache miss**: Each concatenated query is unique
5. **Type safety lost**: No parameter type validation
6. **Field injection attack**: `fieldName = "1=1 OR p.id"` bypasses all filtering

### Impact
- **Critical security vulnerability**: Full database compromise possible
- **Performance**: No plan reuse, constant hard-parsing in database
- **Memory leak**: Hibernate's query plan cache grows unbounded with unique queries

### Correct Code
```java
@Repository
public class ProductSearchRepository {

    @PersistenceContext
    private EntityManager em;

    // Option 1: Parameterized JPQL
    public List<Product> searchProducts(String name, String category, BigDecimal minPrice) {
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<Product> cq = cb.createQuery(Product.class);
        Root<Product> root = cq.from(Product.class);

        List<Predicate> predicates = new ArrayList<>();

        if (name != null) {
            predicates.add(cb.like(cb.lower(root.get("name")),
                "%" + name.toLowerCase() + "%"));  // Safe — parameterized internally
        }
        if (category != null) {
            predicates.add(cb.equal(root.get("category"), category));
        }
        if (minPrice != null) {
            predicates.add(cb.greaterThanOrEqualTo(root.get("price"), minPrice));
        }

        cq.where(predicates.toArray(new Predicate[0]));
        return em.createQuery(cq).getResultList();
    }

    // Option 2: Named parameters (if dynamic query needed)
    public List<Product> searchProductsJpql(String name, String category, BigDecimal minPrice) {
        StringBuilder jpql = new StringBuilder("SELECT p FROM Product p WHERE 1=1");
        Map<String, Object> params = new HashMap<>();

        if (name != null) {
            jpql.append(" AND LOWER(p.name) LIKE :name");
            params.put("name", "%" + name.toLowerCase() + "%");
        }
        if (category != null) {
            jpql.append(" AND p.category = :category");
            params.put("category", category);
        }
        if (minPrice != null) {
            jpql.append(" AND p.price >= :minPrice");
            params.put("minPrice", minPrice);
        }

        TypedQuery<Product> query = em.createQuery(jpql.toString(), Product.class);
        params.forEach(query::setParameter);
        return query.getResultList();
    }

    // Option 3: Spring Data Specifications (reusable predicates)
    public List<Product> search(ProductSearchCriteria criteria) {
        Specification<Product> spec = Specification.where(null);

        if (criteria.getName() != null) {
            spec = spec.and((root, query, cb) ->
                cb.like(cb.lower(root.get("name")), "%" + criteria.getName().toLowerCase() + "%"));
        }
        if (criteria.getCategory() != null) {
            spec = spec.and((root, query, cb) ->
                cb.equal(root.get("category"), criteria.getCategory()));
        }

        return productRepository.findAll(spec);
    }
}
```

### PR Review Comment
> 🚫 **SECURITY CRITICAL**: String concatenation in JPQL = SQL injection vulnerability. Input `name = "' OR '1'='1"` returns all products; worse inputs can drop tables. Also kills query plan caching (every search is a unique query string). Use named parameters (`:param`), Criteria API, or Spring Specifications. Never concatenate user input into queries.

---

## Anti-Pattern 12: findAll() + Java Stream Filter Instead of WHERE Clause

### Bad Code
```java
@Service
public class InvoiceService {

    @Autowired private InvoiceRepository invoiceRepository;

    public List<Invoice> getOverdueInvoices() {
        return invoiceRepository.findAll().stream()  // Loads ALL invoices into memory
            .filter(inv -> inv.getStatus() == InvoiceStatus.UNPAID)
            .filter(inv -> inv.getDueDate().isBefore(LocalDate.now()))
            .filter(inv -> inv.getAmount().compareTo(BigDecimal.ZERO) > 0)
            .sorted(Comparator.comparing(Invoice::getDueDate))
            .toList();
    }

    public Optional<Invoice> findByInvoiceNumber(String number) {
        return invoiceRepository.findAll().stream()  // Loads ALL invoices to find ONE
            .filter(inv -> inv.getInvoiceNumber().equals(number))
            .findFirst();
    }

    public BigDecimal getTotalRevenue(int year) {
        return invoiceRepository.findAll().stream()  // Loads ALL invoices for aggregation
            .filter(inv -> inv.getCreatedAt().getYear() == year)
            .filter(inv -> inv.getStatus() == InvoiceStatus.PAID)
            .map(Invoice::getAmount)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    public Map<InvoiceStatus, Long> getStatusCounts() {
        return invoiceRepository.findAll().stream()  // Loads ALL invoices for counting
            .collect(Collectors.groupingBy(Invoice::getStatus, Collectors.counting()));
    }
}
```

### Problems
1. **Loads entire table into JVM memory** — with 1M invoices, that's GBs of heap
2. **Database indexes completely unused** — full table scan every time
3. **O(N) memory and O(N) time** for operations that DB can do in O(log N)
4. **Network transfer of entire table** — moves all data from DB to app
5. **Aggregations in Java** instead of SQL — orders of magnitude slower
6. **No pagination** — response time grows linearly with data

### Impact
- OOM with production data volumes
- API response time: seconds to minutes (vs. milliseconds with proper query)
- Unnecessary database and network load
- Works in dev (100 rows), fails in production (1M rows)

### Correct Code
```java
@Service
public class InvoiceService {

    @Autowired private InvoiceRepository invoiceRepository;

    public List<Invoice> getOverdueInvoices() {
        // Database does the filtering — uses indexes, returns only matching rows
        return invoiceRepository.findOverdueInvoices(LocalDate.now());
    }

    public Optional<Invoice> findByInvoiceNumber(String number) {
        // Single indexed lookup — O(log N) instead of O(N)
        return invoiceRepository.findByInvoiceNumber(number);
    }

    public BigDecimal getTotalRevenue(int year) {
        // Aggregation in SQL — DB sums without transferring all rows
        return invoiceRepository.sumPaidAmountByYear(year);
    }

    public Map<InvoiceStatus, Long> getStatusCounts() {
        // GROUP BY in SQL — DB returns only the aggregated counts
        return invoiceRepository.countByStatus().stream()
            .collect(Collectors.toMap(
                StatusCount::getStatus, StatusCount::getCount));
    }
}

public interface InvoiceRepository extends JpaRepository<Invoice, Long> {

    @Query("SELECT i FROM Invoice i " +
           "WHERE i.status = 'UNPAID' AND i.dueDate < :today AND i.amount > 0 " +
           "ORDER BY i.dueDate")
    List<Invoice> findOverdueInvoices(@Param("today") LocalDate today);

    Optional<Invoice> findByInvoiceNumber(String invoiceNumber);

    @Query("SELECT COALESCE(SUM(i.amount), 0) FROM Invoice i " +
           "WHERE i.status = 'PAID' AND YEAR(i.createdAt) = :year")
    BigDecimal sumPaidAmountByYear(@Param("year") int year);

    @Query("SELECT new com.myapp.dto.StatusCount(i.status, COUNT(i)) " +
           "FROM Invoice i GROUP BY i.status")
    List<StatusCount> countByStatus();
}
```

### PR Review Comment
> 🚫 `findAll()` loads the entire `invoices` table into memory then filters in Java. With production data (1M+ rows), this causes OOM and takes minutes instead of milliseconds. Move ALL filtering, sorting, and aggregation to the database via proper queries. The DB has indexes and is optimized for this — Java Stream is not a substitute for SQL WHERE.

---

## Anti-Pattern 13: @Transactional(readOnly=false) for Pure Read Operations

### Bad Code
```java
@Service
public class ReportService {

    @Autowired private OrderRepository orderRepository;
    @Autowired private ProductRepository productRepository;

    @Transactional  // Defaults to readOnly=false — acquires write locks
    public DashboardReport generateDashboard() {
        List<Order> recentOrders = orderRepository.findByCreatedAfter(
            LocalDateTime.now().minusDays(7));
        long totalProducts = productRepository.count();
        BigDecimal revenue = orderRepository.sumRevenueForPeriod(
            LocalDateTime.now().minusDays(30));

        return new DashboardReport(recentOrders.size(), totalProducts, revenue);
    }

    @Transactional  // Writes nothing, but uses read-write transaction
    public List<ProductDTO> searchProducts(String query) {
        return productRepository.findByNameContaining(query).stream()
            .map(ProductDTO::from)
            .toList();
    }

    @Transactional  // Every read method has full read-write transaction
    public Optional<Order> getOrder(Long id) {
        return orderRepository.findById(id);
    }
}
```

### Problems
1. **Unnecessary dirty checking**: Hibernate checks all loaded entities for modifications at flush time
2. **No routing to read replica**: Spring's `AbstractRoutingDataSource` uses `readOnly` flag to route
3. **Heavier database transaction**: Read-write transactions acquire stronger locks
4. **Snapshot overhead**: DB maintains undo log for potential rollback
5. **Missed Hibernate optimization**: `readOnly=true` sets FlushMode.MANUAL (skips dirty checking)
6. **Connection pool waste**: Read-write connections may be limited separately from read-only

### Impact
- 10-30% slower for read-heavy workloads (dirty checking overhead)
- Cannot leverage read replicas for read traffic
- Unnecessary lock contention on read-heavy tables
- Heavier database resource usage

### Correct Code
```java
@Service
@Transactional(readOnly = true)  // Default for the class — most methods are reads
public class ReportService {

    @Autowired private OrderRepository orderRepository;
    @Autowired private ProductRepository productRepository;

    // Inherits class-level @Transactional(readOnly = true)
    public DashboardReport generateDashboard() {
        List<Order> recentOrders = orderRepository.findByCreatedAfter(
            LocalDateTime.now().minusDays(7));
        long totalProducts = productRepository.count();
        BigDecimal revenue = orderRepository.sumRevenueForPeriod(
            LocalDateTime.now().minusDays(30));

        return new DashboardReport(recentOrders.size(), totalProducts, revenue);
        // No dirty checking at end of transaction — faster
        // Routed to read replica — reduces primary load
    }

    public List<ProductDTO> searchProducts(String query) {
        return productRepository.findByNameContaining(query).stream()
            .map(ProductDTO::from)
            .toList();
    }

    public Optional<Order> getOrder(Long id) {
        return orderRepository.findById(id);
    }

    // Only override for methods that actually write
    @Transactional(readOnly = false)
    public void archiveOldOrders() {
        orderRepository.archiveOrdersBefore(LocalDateTime.now().minusYears(1));
    }
}

// DataSource routing configuration
@Configuration
public class DataSourceConfig {

    @Bean
    public DataSource routingDataSource() {
        Map<Object, Object> targetDataSources = new HashMap<>();
        targetDataSources.put("primary", primaryDataSource());
        targetDataSources.put("replica", replicaDataSource());

        AbstractRoutingDataSource routingDataSource = new AbstractRoutingDataSource() {
            @Override
            protected Object determineCurrentLookupKey() {
                return TransactionSynchronizationManager.isCurrentTransactionReadOnly()
                    ? "replica" : "primary";
            }
        };
        routingDataSource.setTargetDataSources(targetDataSources);
        routingDataSource.setDefaultTargetDataSource(primaryDataSource());
        return routingDataSource;
    }
}
```

### PR Review Comment
> 🚫 Read-only operations using read-write transactions: unnecessary dirty checking (~15% overhead), prevents routing to read replicas, and holds stronger DB locks. Add `@Transactional(readOnly = true)` at class level for read-heavy services, and override with `readOnly = false` only for mutating methods. This also enables read-replica routing if configured.

---

## Anti-Pattern 14: Anemic Domain Model (Entities as Data Bags)

### Bad Code
```java
@Entity
public class BankAccount {
    @Id @GeneratedValue
    private Long id;
    private String accountNumber;
    private BigDecimal balance;
    private AccountStatus status;
    private BigDecimal overdraftLimit;
    private LocalDateTime lastTransactionAt;

    // Only getters and setters — no business logic
    public BigDecimal getBalance() { return balance; }
    public void setBalance(BigDecimal balance) { this.balance = balance; }
    public AccountStatus getStatus() { return status; }
    public void setStatus(AccountStatus status) { this.status = status; }
    // ... etc
}

@Service
public class BankAccountService {

    @Transactional
    public void withdraw(Long accountId, BigDecimal amount) {
        BankAccount account = accountRepository.findById(accountId).orElseThrow();

        // All business rules scattered in service — not in entity
        if (account.getStatus() != AccountStatus.ACTIVE) {
            throw new AccountInactiveException("Account is not active");
        }
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new InvalidAmountException("Amount must be positive");
        }
        BigDecimal minBalance = account.getBalance().subtract(account.getOverdraftLimit());
        if (account.getBalance().subtract(amount).compareTo(minBalance.negate()) < 0) {
            throw new InsufficientFundsException("Exceeds overdraft limit");
        }

        account.setBalance(account.getBalance().subtract(amount));
        account.setLastTransactionAt(LocalDateTime.now());
        accountRepository.save(account);
    }

    @Transactional
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        BankAccount from = accountRepository.findById(fromId).orElseThrow();
        BankAccount to = accountRepository.findById(toId).orElseThrow();

        // Duplicate validation logic — same checks as withdraw
        if (from.getStatus() != AccountStatus.ACTIVE) { throw new AccountInactiveException("..."); }
        if (to.getStatus() != AccountStatus.ACTIVE) { throw new AccountInactiveException("..."); }
        if (amount.compareTo(BigDecimal.ZERO) <= 0) { throw new InvalidAmountException("..."); }
        // ... same overdraft check duplicated ...

        from.setBalance(from.getBalance().subtract(amount));
        to.setBalance(to.getBalance().add(amount));
        from.setLastTransactionAt(LocalDateTime.now());
        to.setLastTransactionAt(LocalDateTime.now());
    }
}
```

### Problems
1. **Business rules scattered across services** — not encapsulated in the entity
2. **Duplication**: Validation logic repeated in every service method
3. **Invariant violations possible**: Any code can `setBalance()` to an invalid value
4. **No domain protection**: Entity allows impossible states (negative balance below overdraft)
5. **Testing requires mocking repository** instead of unit-testing domain logic directly
6. **New developers bypass rules**: They call `setBalance()` directly, skipping validation

### Impact
- Business logic duplication → inconsistency when one copy is updated but not others
- Bugs from skipped validation (new code that calls setters directly)
- Difficult to understand: must read all services to know business rules
- Cannot unit test domain logic without Spring context

### Correct Code
```java
@Entity
public class BankAccount {
    @Id @GeneratedValue
    private Long id;
    private String accountNumber;
    private BigDecimal balance;

    @Enumerated(EnumType.STRING)
    private AccountStatus status;

    private BigDecimal overdraftLimit;
    private LocalDateTime lastTransactionAt;

    // No public setters for balance/status — only through business methods

    public void withdraw(BigDecimal amount) {
        requireActive();
        requirePositiveAmount(amount);
        requireSufficientFunds(amount);

        this.balance = this.balance.subtract(amount);
        this.lastTransactionAt = LocalDateTime.now();
    }

    public void deposit(BigDecimal amount) {
        requireActive();
        requirePositiveAmount(amount);

        this.balance = this.balance.add(amount);
        this.lastTransactionAt = LocalDateTime.now();
    }

    public void freeze() {
        if (this.status == AccountStatus.CLOSED) {
            throw new IllegalStateException("Cannot freeze a closed account");
        }
        this.status = AccountStatus.FROZEN;
    }

    public boolean canWithdraw(BigDecimal amount) {
        return status == AccountStatus.ACTIVE
            && amount.compareTo(BigDecimal.ZERO) > 0
            && balance.subtract(amount).compareTo(overdraftLimit.negate()) >= 0;
    }

    // Private invariant checks — encapsulated
    private void requireActive() {
        if (status != AccountStatus.ACTIVE) {
            throw new AccountInactiveException("Account " + accountNumber + " is " + status);
        }
    }

    private void requirePositiveAmount(BigDecimal amount) {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new InvalidAmountException("Amount must be positive, got: " + amount);
        }
    }

    private void requireSufficientFunds(BigDecimal amount) {
        if (balance.subtract(amount).compareTo(overdraftLimit.negate()) < 0) {
            throw new InsufficientFundsException(
                "Cannot withdraw " + amount + " from balance " + balance +
                " (overdraft limit: " + overdraftLimit + ")");
        }
    }
}

@Service
public class BankAccountService {

    @Transactional
    public void withdraw(Long accountId, BigDecimal amount) {
        BankAccount account = accountRepository.findById(accountId).orElseThrow();
        account.withdraw(amount);  // All validation inside entity
        // No explicit save needed — dirty checking handles it
    }

    @Transactional
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        BankAccount from = accountRepository.findById(fromId).orElseThrow();
        BankAccount to = accountRepository.findById(toId).orElseThrow();

        from.withdraw(amount);  // Validates and debits
        to.deposit(amount);     // Validates and credits
        // No duplication — logic lives in entity
    }
}

// Unit testable without Spring or mocks:
@Test
void withdraw_withInsufficientFunds_throwsException() {
    BankAccount account = new BankAccount("ACC-001", new BigDecimal("100.00"),
        new BigDecimal("50.00"));  // balance=100, overdraft=50

    assertThatThrownBy(() -> account.withdraw(new BigDecimal("200.00")))
        .isInstanceOf(InsufficientFundsException.class);

    assertThat(account.getBalance()).isEqualByComparingTo("100.00");  // Unchanged
}
```

### PR Review Comment
> 🚫 Anemic domain model: entity is just getters/setters, all business rules live in the service and are duplicated across methods. Encapsulate invariants in the entity (`withdraw()`, `deposit()`) with private setters. This eliminates duplication, makes impossible states unrepresentable, and enables pure unit testing without Spring context. Service should orchestrate, not contain domain logic.

---

## Anti-Pattern 15: Catching All Exceptions Inside @Transactional Preventing Rollback

### Bad Code
```java
@Service
public class OrderFulfillmentService {

    @Autowired private OrderRepository orderRepository;
    @Autowired private InventoryRepository inventoryRepository;
    @Autowired private ShipmentRepository shipmentRepository;

    @Transactional
    public FulfillmentResult fulfillOrder(Long orderId) {
        try {
            Order order = orderRepository.findById(orderId).orElseThrow();
            order.setStatus(OrderStatus.PROCESSING);
            orderRepository.save(order);

            // Decrement inventory
            for (OrderItem item : order.getItems()) {
                Inventory inv = inventoryRepository.findByProductId(item.getProductId());
                inv.setQuantity(inv.getQuantity() - item.getQuantity());
                if (inv.getQuantity() < 0) {
                    throw new InsufficientInventoryException("Out of stock: " + item.getProductId());
                }
                inventoryRepository.save(inv);
            }

            // Create shipment
            Shipment shipment = new Shipment(order);
            shipmentRepository.save(shipment);

            order.setStatus(OrderStatus.SHIPPED);
            orderRepository.save(order);

            return FulfillmentResult.success(shipment.getTrackingNumber());

        } catch (Exception e) {
            // CATCHES EVERYTHING — including the InsufficientInventoryException
            // Transaction does NOT roll back — order is stuck in PROCESSING status
            // Inventory was decremented for items before the out-of-stock one
            log.error("Error fulfilling order {}", orderId, e);
            return FulfillmentResult.failure(e.getMessage());
        }
    }
}

// Another variant: catching and wrapping in checked exception
@Transactional
public void processPayment(Long orderId) {
    try {
        // ... payment logic ...
        throw new RuntimeException("Connection refused");
    } catch (RuntimeException e) {
        // Catches RuntimeException that would trigger rollback
        // Wraps in checked exception — Spring doesn't rollback for checked exceptions by default!
        throw new PaymentProcessingException("Payment failed", e);
    }
}
```

### Problems
1. **Catch-all prevents rollback**: `@Transactional` only rolls back on uncaught `RuntimeException`
2. **Partial state committed**: Order is `PROCESSING` but inventory partially decremented
3. **Data inconsistency**: Some items decremented, others not — inventory is wrong
4. **Checked exception wrapping**: Spring doesn't rollback for checked exceptions by default
5. **Error is hidden**: Returns "failure" result but data is already corrupted
6. **Cannot distinguish recoverable vs fatal errors**: Treats all exceptions the same

### Impact
- Data corruption: partial writes committed
- Inventory discrepancies requiring manual reconciliation
- Orders stuck in intermediate states
- Silent data corruption — no alerts, discovered days later by accounting

### Correct Code
```java
@Service
public class OrderFulfillmentService {

    @Autowired private OrderRepository orderRepository;
    @Autowired private InventoryRepository inventoryRepository;
    @Autowired private ShipmentRepository shipmentRepository;

    // Option 1: Let exceptions propagate — transaction rolls back automatically
    @Transactional
    public FulfillmentResult fulfillOrder(Long orderId) {
        Order order = orderRepository.findById(orderId).orElseThrow();
        order.setStatus(OrderStatus.PROCESSING);

        for (OrderItem item : order.getItems()) {
            Inventory inv = inventoryRepository.findByProductIdWithLock(item.getProductId());
            inv.decrementQuantity(item.getQuantity());  // Throws if insufficient
        }

        Shipment shipment = new Shipment(order);
        shipmentRepository.save(shipment);
        order.setStatus(OrderStatus.SHIPPED);

        return FulfillmentResult.success(shipment.getTrackingNumber());
        // If any exception occurs, entire transaction rolls back — consistent state
    }

    // Option 2: If you must handle errors, use rollbackFor or mark for rollback
    @Transactional(rollbackFor = Exception.class)  // Rollback on ALL exceptions
    public FulfillmentResult fulfillOrderWithHandling(Long orderId) {
        try {
            // ... same logic ...
            return FulfillmentResult.success(trackingNumber);
        } catch (InsufficientInventoryException e) {
            // Handle known business exception — but STILL rollback
            TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
            return FulfillmentResult.failure("Out of stock: " + e.getProductId());
        }
        // Unknown exceptions propagate naturally — rollback happens
    }

    // Option 3: Separate transaction for status update, main logic can fail safely
    @Transactional
    public FulfillmentResult fulfillOrderSafe(Long orderId) {
        Order order = orderRepository.findById(orderId).orElseThrow();

        // Validate first — before any mutations
        validateInventoryAvailable(order);

        // All validations passed — now mutate
        order.setStatus(OrderStatus.PROCESSING);
        decrementInventory(order);
        Shipment shipment = createShipment(order);
        order.setStatus(OrderStatus.SHIPPED);

        return FulfillmentResult.success(shipment.getTrackingNumber());
    }

    private void validateInventoryAvailable(Order order) {
        for (OrderItem item : order.getItems()) {
            Inventory inv = inventoryRepository.findByProductId(item.getProductId());
            if (inv.getQuantity() < item.getQuantity()) {
                throw new InsufficientInventoryException(item.getProductId(), inv.getQuantity());
            }
        }
    }
}

// Controller handles the exception and returns appropriate response
@RestControllerAdvice
public class FulfillmentExceptionHandler {

    @ExceptionHandler(InsufficientInventoryException.class)
    public ResponseEntity<ErrorResponse> handleInsufficientInventory(InsufficientInventoryException e) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
            .body(new ErrorResponse("INSUFFICIENT_INVENTORY", e.getMessage()));
    }
}
```

### PR Review Comment
> 🚫 **Data corruption risk**: The catch-all block prevents transaction rollback. If `InsufficientInventoryException` is thrown mid-loop, earlier inventory decrements are committed but the order is stuck in `PROCESSING`. Either: (1) let exceptions propagate for automatic rollback, (2) use `@Transactional(rollbackFor = Exception.class)`, or (3) call `setRollbackOnly()` before returning a failure result. Validate-then-mutate is preferred over catch-and-continue.

---

## Summary: Code Review Checklist

| # | Anti-Pattern | Key Signal | Fix |
|---|---|---|---|
| 1 | God Transaction | HTTP/email calls inside `@Transactional` | Orchestrator pattern + async events |
| 2 | N+1 in disguise | `.getCollection()` in loop/mapping | `JOIN FETCH` / `@EntityGraph` / projection |
| 3 | Broken equals/hashCode | `Objects.equals(id, ...)` on `@Id` field | Use natural key or UUID assigned at construction |
| 4 | CascadeType.ALL | `cascade = ALL` on `@ManyToOne`/`@ManyToMany` | Cascade only on owned `@OneToMany` children |
| 5 | Entity as response | Returning `@Entity` from controller | Use DTOs/records with explicit field mapping |
| 6 | EAGER everywhere | `fetch = FetchType.EAGER` | Default LAZY + per-use-case fetch strategies |
| 7 | Private @Transactional | `@Transactional` on private or self-invocation | Separate bean or `TransactionTemplate` |
| 8 | @Version without retry | `@Version` + no exception handling | `@Retryable` + HTTP 409 response |
| 9 | HTTP in transaction | `httpClient.call()` inside `@Transactional` | External calls outside transaction boundary |
| 10 | No batching | `save()` in 100K loop | `flush()`+`clear()` + batch_size + SEQUENCE |
| 11 | String concat JPQL | `"... WHERE x = '" + input + "'"` | Named parameters or Criteria API |
| 12 | findAll + Stream | `findAll().stream().filter(...)` | Database WHERE clause + proper queries |
| 13 | Missing readOnly | `@Transactional` on read methods | `@Transactional(readOnly = true)` at class level |
| 14 | Anemic domain | Entity with only getters/setters | Rich domain methods encapsulating invariants |
| 15 | Catch-all in tx | `catch (Exception e)` swallowing rollback | Let propagate or `setRollbackOnly()` |
