# Database Design Patterns & DDD with JPA (Staff Engineer / Architect Level)

> This document covers advanced database design patterns including Domain-Driven Design with JPA, temporal modeling, schema evolution, and sharding - all critical topics for architect-level interviews.

---

## 1. Domain-Driven Design with JPA

### Aggregate Root Pattern

An **Aggregate** is a cluster of domain objects treated as a single unit for data changes. The **Aggregate Root** is the only entry point for external access.

```
┌─────────────────────────────────────────────────────────────┐
│ AGGREGATE BOUNDARY                                           │
│                                                               │
│  ┌─────────────────────────────────────────────┐            │
│  │ Order (AGGREGATE ROOT)                       │            │
│  │                                               │            │
│  │  ├── OrderItem (value object)                │            │
│  │  │     ├── productId: Long                   │            │
│  │  │     ├── quantity: int                     │            │
│  │  │     └── unitPrice: Money                  │            │
│  │  │                                            │            │
│  │  ├── ShippingAddress (value object)          │            │
│  │  │     ├── street, city, zip                 │            │
│  │  │     └── country                           │            │
│  │  │                                            │            │
│  │  ├── OrderStatus (enum)                      │            │
│  │  └── Money total (value object)              │            │
│  └─────────────────────────────────────────────┘            │
│                                                               │
│  Rules:                                                       │
│  1. Only Order is loaded/saved via Repository                │
│  2. OrderItem has no independent lifecycle                   │
│  3. External aggregates referenced by ID only                │
│  4. Invariants enforced through Order's methods              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

#### JPA Implementation

```java
@Entity
@Table(name = "orders")
public class Order {  // AGGREGATE ROOT
    
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;
    
    @Version
    private int version;
    
    // Reference to another aggregate by ID only (NOT @ManyToOne!)
    @Column(nullable = false)
    private Long customerId;
    
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OrderStatus status;
    
    @Embedded
    @AttributeOverrides({
        @AttributeOverride(name = "amount", column = @Column(name = "total_amount")),
        @AttributeOverride(name = "currency", column = @Column(name = "total_currency"))
    })
    private Money total;
    
    @OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)
    @JoinColumn(name = "order_id", nullable = false)
    @OrderColumn(name = "item_index")
    private List<OrderItem> items = new ArrayList<>();
    
    @Embedded
    @AttributeOverrides({
        @AttributeOverride(name = "street", column = @Column(name = "shipping_street")),
        @AttributeOverride(name = "city", column = @Column(name = "shipping_city")),
        @AttributeOverride(name = "zipCode", column = @Column(name = "shipping_zip")),
        @AttributeOverride(name = "country", column = @Column(name = "shipping_country"))
    })
    private Address shippingAddress;
    
    private Instant createdAt;
    private Instant confirmedAt;
    
    // ========= BUSINESS METHODS (encapsulate invariants) =========
    
    protected Order() {} // JPA requires no-arg constructor
    
    public static Order create(Long customerId, Address shippingAddress) {
        Order order = new Order();
        order.customerId = customerId;
        order.shippingAddress = shippingAddress;
        order.status = OrderStatus.DRAFT;
        order.total = Money.ZERO;
        order.createdAt = Instant.now();
        return order;
    }
    
    public void addItem(Long productId, String productName, int quantity, Money unitPrice) {
        assertDraftStatus();
        if (quantity <= 0) throw new IllegalArgumentException("Quantity must be positive");
        
        // Check if product already in order
        items.stream()
            .filter(i -> i.getProductId().equals(productId))
            .findFirst()
            .ifPresentOrElse(
                existing -> existing.increaseQuantity(quantity),
                () -> items.add(OrderItem.create(productId, productName, quantity, unitPrice))
            );
        
        recalculateTotal();
    }
    
    public void removeItem(Long productId) {
        assertDraftStatus();
        items.removeIf(i -> i.getProductId().equals(productId));
        recalculateTotal();
    }
    
    public void confirm() {
        assertDraftStatus();
        if (items.isEmpty()) {
            throw new OrderException("Cannot confirm an empty order");
        }
        this.status = OrderStatus.CONFIRMED;
        this.confirmedAt = Instant.now();
    }
    
    public void cancel(String reason) {
        if (status == OrderStatus.SHIPPED) {
            throw new OrderException("Cannot cancel a shipped order");
        }
        this.status = OrderStatus.CANCELLED;
    }
    
    // ========= PRIVATE HELPERS =========
    
    private void assertDraftStatus() {
        if (status != OrderStatus.DRAFT) {
            throw new OrderException("Order can only be modified in DRAFT status");
        }
    }
    
    private void recalculateTotal() {
        this.total = items.stream()
            .map(OrderItem::getSubtotal)
            .reduce(Money.ZERO, Money::add);
    }
}
```

#### OrderItem (Entity within Aggregate)

```java
@Entity
@Table(name = "order_items")
public class OrderItem {  // NOT an aggregate root - no repository!
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private Long productId;  // Reference by ID to Product aggregate
    
    @Column(nullable = false)
    private String productName;  // Snapshot at order time
    
    @Column(nullable = false)
    private int quantity;
    
    @Embedded
    @AttributeOverrides({
        @AttributeOverride(name = "amount", column = @Column(name = "unit_price_amount")),
        @AttributeOverride(name = "currency", column = @Column(name = "unit_price_currency"))
    })
    private Money unitPrice;  // Snapshot at order time
    
    protected OrderItem() {}
    
    static OrderItem create(Long productId, String productName, int quantity, Money unitPrice) {
        OrderItem item = new OrderItem();
        item.productId = productId;
        item.productName = productName;
        item.quantity = quantity;
        item.unitPrice = unitPrice;
        return item;
    }
    
    void increaseQuantity(int additionalQuantity) {
        this.quantity += additionalQuantity;
    }
    
    public Money getSubtotal() {
        return unitPrice.multiply(quantity);
    }
}
```

#### Repository Per Aggregate Root

```java
// ONLY aggregate roots get repositories
public interface OrderRepository extends JpaRepository<Order, String> {
    
    // Load complete aggregate
    @EntityGraph(attributePaths = {"items"})
    Optional<Order> findWithItemsById(String id);
    
    // Query methods for the aggregate root
    List<Order> findByCustomerIdAndStatus(Long customerId, OrderStatus status);
    
    @Query("SELECT o FROM Order o WHERE o.status = :status AND o.createdAt < :before")
    List<Order> findStaleOrders(@Param("status") OrderStatus status, 
                                @Param("before") Instant before);
}

// NO OrderItemRepository! OrderItems only accessed through Order
```

### Why Reference Other Aggregates by ID Only

```java
// WRONG: Tight coupling between aggregates
@Entity
public class Order {
    @ManyToOne(fetch = LAZY)
    @JoinColumn(name = "customer_id")
    private Customer customer;  // Cross-aggregate reference!
    
    // Problems:
    // 1. Loading Order may trigger Customer loading
    // 2. Which aggregate "owns" the relationship?
    // 3. In microservices: Customer may be in different database!
    // 4. Transaction boundary unclear (modify Customer in Order's TX?)
}

// RIGHT: Reference by ID
@Entity
public class Order {
    @Column(name = "customer_id", nullable = false)
    private Long customerId;  // Just the ID - loose coupling
    
    // If you need customer data: call CustomerService explicitly
    // Clear ownership: Order doesn't own Customer
    // Microservice-ready: Customer can live anywhere
}
```

### Value Objects with @Embeddable

```java
@Embeddable
public class Money {
    
    @Column(nullable = false)
    private BigDecimal amount;
    
    @Column(nullable = false, length = 3)
    private String currency;
    
    public static final Money ZERO = new Money(BigDecimal.ZERO, "USD");
    
    protected Money() {} // JPA
    
    public Money(BigDecimal amount, String currency) {
        this.amount = Objects.requireNonNull(amount);
        this.currency = Objects.requireNonNull(currency);
    }
    
    public Money add(Money other) {
        assertSameCurrency(other);
        return new Money(this.amount.add(other.amount), this.currency);
    }
    
    public Money multiply(int factor) {
        return new Money(this.amount.multiply(BigDecimal.valueOf(factor)), this.currency);
    }
    
    // Value objects: equality by value, not identity
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Money money)) return false;
        return amount.compareTo(money.amount) == 0 && currency.equals(money.currency);
    }
    
    @Override
    public int hashCode() {
        return Objects.hash(amount.stripTrailingZeros(), currency);
    }
    
    private void assertSameCurrency(Money other) {
        if (!this.currency.equals(other.currency)) {
            throw new IllegalArgumentException("Cannot operate on different currencies");
        }
    }
}

@Embeddable
public class Address {
    private String street;
    private String city;
    private String zipCode;
    private String country;
    
    protected Address() {}
    
    public Address(String street, String city, String zipCode, String country) {
        this.street = Objects.requireNonNull(street);
        this.city = Objects.requireNonNull(city);
        this.zipCode = Objects.requireNonNull(zipCode);
        this.country = Objects.requireNonNull(country);
    }
    
    // Immutable - no setters
    // equals/hashCode by all fields
}
```

### Domain Events with Spring Data

```java
@Entity
public class Order extends AbstractAggregateRoot<Order> {
    
    // ... fields ...
    
    public void confirm() {
        assertDraftStatus();
        if (items.isEmpty()) throw new OrderException("Cannot confirm empty order");
        
        this.status = OrderStatus.CONFIRMED;
        this.confirmedAt = Instant.now();
        
        // Register domain event (published after save)
        registerEvent(new OrderConfirmedEvent(this.id, this.customerId, this.total));
    }
    
    public void cancel(String reason) {
        // ...
        registerEvent(new OrderCancelledEvent(this.id, this.customerId, reason));
    }
}

// Spring publishes these events AFTER repository.save() commits
@Component
public class OrderEventHandler {
    
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onOrderConfirmed(OrderConfirmedEvent event) {
        // Send notification, update analytics, etc.
        notificationService.notifyCustomer(event.getCustomerId(), "Order confirmed!");
    }
}
```

---

## 2. Temporal Data Modeling

### SCD Type 2 (History with Effective Dates)

```java
@Entity
@Table(name = "customer_history",
       indexes = @Index(columnList = "customerId, effectiveTo"))
public class CustomerHistory {
    
    @Id
    @GeneratedValue
    private Long id;
    
    @Column(nullable = false)
    private Long customerId;  // Logical identifier
    
    // All versioned fields
    private String name;
    private String email;
    private String tier;  // BRONZE, SILVER, GOLD
    
    // Temporal columns
    @Column(nullable = false)
    private LocalDate effectiveFrom;
    
    private LocalDate effectiveTo;  // NULL = current record
    
    @Column(nullable = false)
    private boolean current;  // Denormalized flag for easy querying
}

@Repository
public interface CustomerHistoryRepository extends JpaRepository<CustomerHistory, Long> {
    
    // Get current version
    Optional<CustomerHistory> findByCustomerIdAndCurrentTrue(Long customerId);
    
    // Get version as of a specific date
    @Query("SELECT c FROM CustomerHistory c " +
           "WHERE c.customerId = :customerId " +
           "AND c.effectiveFrom <= :asOfDate " +
           "AND (c.effectiveTo IS NULL OR c.effectiveTo > :asOfDate)")
    Optional<CustomerHistory> findAsOf(@Param("customerId") Long customerId,
                                       @Param("asOfDate") LocalDate asOfDate);
    
    // Get full history
    List<CustomerHistory> findByCustomerIdOrderByEffectiveFromDesc(Long customerId);
}

@Service
public class CustomerService {
    
    @Transactional
    public void updateCustomer(Long customerId, CustomerUpdateRequest request) {
        CustomerHistory current = customerHistoryRepo
            .findByCustomerIdAndCurrentTrue(customerId)
            .orElseThrow(() -> new CustomerNotFoundException(customerId));
        
        // Close current record
        current.setEffectiveTo(LocalDate.now());
        current.setCurrent(false);
        
        // Create new version
        CustomerHistory newVersion = new CustomerHistory();
        newVersion.setCustomerId(customerId);
        newVersion.setName(request.getName() != null ? request.getName() : current.getName());
        newVersion.setEmail(request.getEmail() != null ? request.getEmail() : current.getEmail());
        newVersion.setTier(request.getTier() != null ? request.getTier() : current.getTier());
        newVersion.setEffectiveFrom(LocalDate.now());
        newVersion.setEffectiveTo(null);
        newVersion.setCurrent(true);
        
        customerHistoryRepo.save(current);
        customerHistoryRepo.save(newVersion);
    }
}
```

### Bitemporal Modeling

```java
@Entity
@Table(name = "contracts")
public class Contract {
    
    @Id @GeneratedValue
    private Long id;
    
    private Long contractNumber;  // Logical identifier
    
    private String terms;
    private BigDecimal value;
    
    // VALID TIME: when the fact is true in the real world
    @Column(nullable = false)
    private LocalDate validFrom;
    private LocalDate validTo;  // NULL = currently valid
    
    // TRANSACTION TIME: when we recorded this in the database
    @Column(nullable = false)
    private Instant recordedAt;
    private Instant supersededAt;  // NULL = current record
    
    // Combine both for full bitemporal query:
    // "What did we KNOW about contract X at time T1, 
    //  for the period that was VALID at time T2?"
}

@Repository
public interface ContractRepository extends JpaRepository<Contract, Long> {
    
    // Current knowledge, currently valid
    @Query("SELECT c FROM Contract c " +
           "WHERE c.contractNumber = :num " +
           "AND c.supersededAt IS NULL " +
           "AND c.validFrom <= CURRENT_DATE " +
           "AND (c.validTo IS NULL OR c.validTo > CURRENT_DATE)")
    Optional<Contract> findCurrentContract(@Param("num") Long contractNumber);
    
    // What we knew at a specific transaction time, valid at a specific date
    @Query("SELECT c FROM Contract c " +
           "WHERE c.contractNumber = :num " +
           "AND c.recordedAt <= :asOfTxTime " +
           "AND (c.supersededAt IS NULL OR c.supersededAt > :asOfTxTime) " +
           "AND c.validFrom <= :asOfValidDate " +
           "AND (c.validTo IS NULL OR c.validTo > :asOfValidDate)")
    Optional<Contract> findBitemporal(@Param("num") Long contractNumber,
                                      @Param("asOfTxTime") Instant asOfTxTime,
                                      @Param("asOfValidDate") LocalDate asOfValidDate);
}
```

---

## 3. Inheritance Strategy Deep Analysis

### Performance Comparison at Scale

```
Scenario: Vehicle hierarchy with 5 subclasses
- Vehicle (base): id, vin, manufacturer, year
- Car: seats, trunk_capacity
- Truck: payload_capacity, axle_count
- Motorcycle: engine_cc
- Bus: standing_capacity, route_number
- Bicycle: gear_count, frame_material

Data: 1,000,000 vehicles total (200K each type)
```

#### SINGLE_TABLE Strategy

```java
@Entity
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
@DiscriminatorColumn(name = "vehicle_type")
public abstract class Vehicle {
    @Id @GeneratedValue private Long id;
    private String vin;
    private String manufacturer;
    private int year;
}

@Entity @DiscriminatorValue("CAR")
public class Car extends Vehicle {
    private Integer seats;          // NULL for non-cars
    private Integer trunkCapacity;  // NULL for non-cars
}
```

```
Table: vehicles (1 table, all columns, many NULLs)
┌────┬──────┬──────────────┬──────┬─────────────┬───────┬──────────────┬─────────┬─────────┬───────────────┬─────────────┬──────────────┐
│ id │ type │ vin          │ year │manufacturer │ seats │trunk_capacity│payload  │axle_cnt │engine_cc      │standing_cap │gear_count    │
├────┼──────┼──────────────┼──────┼─────────────┼───────┼──────────────┼─────────┼─────────┼───────────────┼─────────────┼──────────────┤
│ 1  │ CAR  │ VIN001       │ 2023 │ Toyota      │ 5     │ 400          │ NULL    │ NULL    │ NULL          │ NULL        │ NULL         │
│ 2  │TRUCK │ VIN002       │ 2022 │ Volvo       │ NULL  │ NULL         │ 20000   │ 3       │ NULL          │ NULL        │ NULL         │
└────┴──────┴──────────────┴──────┴─────────────┴───────┴──────────────┴─────────┴─────────┴───────────────┴─────────────┴──────────────┘

Query performance:
- Polymorphic "SELECT FROM Vehicle": single table scan, fast
- Concrete "SELECT FROM Car": single table scan + discriminator filter, fast
- No JOINs needed
- Storage: wastes space (many NULL columns per row)
- Column limit: databases have max columns (PostgreSQL: 1600, MySQL: 4096)
```

#### JOINED Strategy

```java
@Entity
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class Vehicle {
    @Id @GeneratedValue private Long id;
    private String vin;
    private String manufacturer;
    private int year;
}

@Entity
public class Car extends Vehicle {
    private int seats;
    private int trunkCapacity;
}
```

```
Tables: vehicles + car + truck + motorcycle + bus + bicycle

vehicles:        car:             truck:
┌────┬─────┬──┐  ┌────┬───────┬──┐  ┌────┬─────────┬──┐
│ id │ vin │..│  │ id │ seats │..│  │ id │ payload │..│
└────┴─────┴──┘  └────┴───────┴──┘  └────┴─────────┴──┘

Query performance:
- Polymorphic "SELECT FROM Vehicle": JOIN all 5 subclass tables! EXPENSIVE
  SELECT v.*, c.*, t.*, m.*, b.*, bi.*
  FROM vehicles v
  LEFT JOIN car c ON v.id = c.id
  LEFT JOIN truck t ON v.id = t.id
  LEFT JOIN motorcycle m ON v.id = m.id
  LEFT JOIN bus b ON v.id = b.id
  LEFT JOIN bicycle bi ON v.id = bi.id
  
- Concrete "SELECT FROM Car": JOIN vehicles + car only (fast)
- Storage: efficient (no NULLs, normalized)
- INSERT: requires INSERT into parent + child table
```

#### TABLE_PER_CLASS Strategy

```java
@Entity
@Inheritance(strategy = InheritanceType.TABLE_PER_CLASS)
public abstract class Vehicle {
    @Id @GeneratedValue private Long id;
    private String vin;
    private String manufacturer;
    private int year;
}
```

```
Tables: car, truck, motorcycle, bus, bicycle (each has ALL columns)

car:                              truck:
┌────┬──────┬──────────┬───────┐  ┌────┬──────┬──────────┬─────────┐
│ id │ vin  │ manufact │ seats │  │ id │ vin  │ manufact │ payload │
└────┴──────┴──────────┴───────┘  └────┴──────┴──────────┴─────────┘

Query performance:
- Polymorphic "SELECT FROM Vehicle": UNION ALL across all 5 tables! EXPENSIVE
  SELECT id, vin, manufacturer, year FROM car
  UNION ALL
  SELECT id, vin, manufacturer, year FROM truck
  UNION ALL
  SELECT id, vin, manufacturer, year FROM motorcycle
  ...

- Concrete "SELECT FROM Car": single table, fast
- No JOINs for concrete queries
- Duplicate base columns in each table
```

### Decision Matrix

```
┌────────────────────────┬─────────────┬──────────┬─────────────────┐
│ Criterion              │ SINGLE_TABLE│ JOINED   │ TABLE_PER_CLASS │
├────────────────────────┼─────────────┼──────────┼─────────────────┤
│ Polymorphic query      │ FAST ★★★    │ SLOW ★   │ SLOW ★          │
│ Concrete query         │ FAST ★★★    │ FAST ★★  │ FAST ★★★        │
│ INSERT                 │ FAST ★★★    │ SLOW ★★  │ FAST ★★★        │
│ Storage efficiency     │ LOW ★       │ HIGH ★★★ │ MEDIUM ★★       │
│ NULL columns           │ MANY        │ NONE     │ NONE            │
│ Schema clarity         │ LOW         │ HIGH     │ MEDIUM          │
│ DB constraints         │ LIMITED ★   │ FULL ★★★ │ LIMITED ★       │
│ Add new subclass       │ Add cols    │ Add table│ Add table       │
│ JPQL polymorphic       │ Works well  │ Works    │ Works           │
│ DB-level FK refs       │ Easy        │ Easy     │ Complex         │
├────────────────────────┼─────────────┼──────────┼─────────────────┤
│ Best when:             │ Few types,  │ Many     │ Rarely query    │
│                        │ similar     │ unique   │ polymorphically │
│                        │ columns     │ columns  │                 │
└────────────────────────┴─────────────┴──────────┴─────────────────┘
```

---

## 4. Sharding Strategies with JPA

### Application-Level Sharding

```java
// AbstractRoutingDataSource for shard selection
public class ShardRoutingDataSource extends AbstractRoutingDataSource {
    
    @Override
    protected Object determineCurrentLookupKey() {
        return ShardContext.getCurrentShard();
    }
}

// ThreadLocal for shard context
public class ShardContext {
    private static final ThreadLocal<String> currentShard = new ThreadLocal<>();
    
    public static void setShard(String shard) { currentShard.set(shard); }
    public static String getCurrentShard() { return currentShard.get(); }
    public static void clear() { currentShard.remove(); }
}

// Shard resolver based on entity ID
@Component
public class ShardResolver {
    
    private static final int SHARD_COUNT = 4;
    
    public String resolveShardForUser(Long userId) {
        int shardIndex = (int) (userId % SHARD_COUNT);
        return "shard-" + shardIndex;
    }
    
    public String resolveShardForTenant(String tenantId) {
        int hash = Math.abs(tenantId.hashCode());
        int shardIndex = hash % SHARD_COUNT;
        return "shard-" + shardIndex;
    }
}

// Configuration
@Configuration
public class ShardingConfig {
    
    @Bean
    public DataSource routingDataSource(
            @Qualifier("shard0") DataSource shard0,
            @Qualifier("shard1") DataSource shard1,
            @Qualifier("shard2") DataSource shard2,
            @Qualifier("shard3") DataSource shard3) {
        
        ShardRoutingDataSource routing = new ShardRoutingDataSource();
        Map<Object, Object> shards = Map.of(
            "shard-0", shard0,
            "shard-1", shard1,
            "shard-2", shard2,
            "shard-3", shard3
        );
        routing.setTargetDataSources(shards);
        routing.setDefaultTargetDataSource(shard0);
        return routing;
    }
}

// Service with shard routing
@Service
public class UserService {
    
    @Autowired private ShardResolver shardResolver;
    @Autowired private UserRepository userRepository;
    
    @Transactional
    public User createUser(CreateUserRequest request) {
        Long userId = idGenerator.nextId();  // Pre-generate ID
        String shard = shardResolver.resolveShardForUser(userId);
        
        try {
            ShardContext.setShard(shard);
            User user = new User(userId, request.getName(), request.getEmail());
            return userRepository.save(user);
        } finally {
            ShardContext.clear();
        }
    }
    
    @Transactional(readOnly = true)
    public Optional<User> findUser(Long userId) {
        String shard = shardResolver.resolveShardForUser(userId);
        try {
            ShardContext.setShard(shard);
            return userRepository.findById(userId);
        } finally {
            ShardContext.clear();
        }
    }
}
```

### JPA Limitations with Sharding

```
┌─────────────────────────────────────────────────────────────┐
│ Challenges:                                                   │
│                                                               │
│ 1. No cross-shard JOINs                                      │
│    SELECT o.*, u.name FROM orders o                          │
│    JOIN users u ON o.user_id = u.id                          │
│    ← Users and Orders may be on different shards!            │
│                                                               │
│ 2. No cross-shard transactions                               │
│    User on shard-0, their Order on shard-1                   │
│    → Cannot be in same @Transactional                        │
│                                                               │
│ 3. No cross-shard unique constraints                         │
│    email UNIQUE across all shards? DB can't enforce this.    │
│    → Need application-level or lookup table                  │
│                                                               │
│ 4. Aggregation queries                                        │
│    SELECT COUNT(*) FROM users                                │
│    → Must query ALL shards and sum results                   │
│                                                               │
│ 5. Pagination across shards                                   │
│    OFFSET 100 LIMIT 10 across 4 shards?                      │
│    → Must over-fetch from each shard, merge, then paginate   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Schema Evolution Patterns

### Zero-Downtime Migration (Expand-Contract)

```
Phase 1: EXPAND (add new column, backward compatible)
─────────────────────────────────────────────────────
Migration:
  ALTER TABLE users ADD COLUMN full_name VARCHAR(200);
  -- New column is NULLABLE (backward compatible)

Application v1 (current): 
  Still reads/writes first_name + last_name
  Ignores full_name column (unmapped in entity)

Deploy application v2 (dual-write):
  Writes to BOTH old columns AND new column
  Reads from old columns (still source of truth)

@Entity
public class User {
    private String firstName;
    private String lastName;
    private String fullName;  // NEW: writes here too
    
    @PrePersist @PreUpdate
    void syncFullName() {
        this.fullName = firstName + " " + lastName;
    }
}

Phase 2: MIGRATE (backfill existing data)
─────────────────────────────────────────
Migration (background job, not blocking):
  UPDATE users SET full_name = first_name || ' ' || last_name
  WHERE full_name IS NULL;
  -- Run in batches to avoid long locks

Phase 3: SWITCH (read from new column)
─────────────────────────────────────────
Deploy application v3:
  Reads from full_name (new source of truth)
  Still writes to all columns (backward compatible for rollback)

Phase 4: CONTRACT (remove old columns)
─────────────────────────────────────────
Migration:
  ALTER TABLE users DROP COLUMN first_name;
  ALTER TABLE users DROP COLUMN last_name;
  ALTER TABLE users ALTER COLUMN full_name SET NOT NULL;

Deploy application v4:
  Only uses full_name
  Removes old columns from entity

TOTAL TIME: May span multiple deployment cycles (days/weeks)
DOWNTIME: ZERO (each phase is independently deployable/rollbackable)
```

### Safe vs Unsafe Schema Changes

```
┌───────────────────────────────────────────────────────────────┐
│ SAFE (backward compatible):                                    │
│ ├── Add nullable column                                        │
│ ├── Add new table                                              │
│ ├── Add index (CREATE INDEX CONCURRENTLY in PostgreSQL)        │
│ ├── Add column with default value (PostgreSQL 11+: instant)    │
│ ├── Widen column type (VARCHAR(50) → VARCHAR(200))            │
│ └── Add new enum value (at the END for @Enumerated ORDINAL)   │
│                                                                 │
│ UNSAFE (requires expand-contract):                             │
│ ├── Remove column                                              │
│ ├── Rename column                                              │
│ ├── Change column type                                         │
│ ├── Add NOT NULL constraint to existing column                 │
│ ├── Remove table                                               │
│ ├── Rename table                                               │
│ └── Remove enum value                                          │
│                                                                 │
│ DANGEROUS (may lock table):                                    │
│ ├── ALTER TABLE ... ADD COLUMN with DEFAULT (old PostgreSQL)   │
│ ├── CREATE INDEX (non-concurrent)                              │
│ ├── ALTER TABLE ... ALTER COLUMN TYPE                          │
│ └── Adding FK constraint (must scan for violations)            │
│                                                                 │
└───────────────────────────────────────────────────────────────┘
```

### JPA Entity Compatibility During Migration

```java
// Key principle: JPA entity must work with BOTH old and new schema
// during the transition period

// Phase: new column added to DB but not all app instances updated

// Old app instance (v1) entity:
@Entity @Table(name = "products")
public class Product {
    @Id private Long id;
    private String name;
    private BigDecimal price;
    // Does NOT have 'category' field
    // → Hibernate ignores unknown DB columns (by default)
    // → Works fine! (unless using ddl-auto=validate)
}

// New app instance (v2) entity:
@Entity @Table(name = "products")
public class Product {
    @Id private Long id;
    private String name;
    private BigDecimal price;
    private String category;  // NEW - nullable
}

// IMPORTANT: Use ddl-auto=validate in production
// This catches entity-schema mismatches at startup
spring.jpa.hibernate.ddl-auto=validate
// But: during migration transition, you may need to relax this temporarily
```

---

## 6. Soft Delete Patterns (Production-Grade)

### Basic Implementation

```java
@Entity
@Table(name = "documents")
@Where(clause = "deleted = false")  // Hibernate filter: auto-exclude deleted
@SQLDelete(sql = "UPDATE documents SET deleted = true, deleted_at = NOW(), deleted_by = ? WHERE id = ?")
public class Document {
    
    @Id @GeneratedValue
    private Long id;
    
    private String title;
    private String content;
    
    @Column(nullable = false)
    private boolean deleted = false;
    
    private Instant deletedAt;
    private String deletedBy;
    
    @Version
    private int version;
}
```

### Unique Constraints with Soft Delete

```sql
-- Problem: UNIQUE(email) + soft delete
-- User deletes account → email marked deleted
-- Same user wants to re-register with same email → UNIQUE violation!

-- Solution: Partial unique index (PostgreSQL)
CREATE UNIQUE INDEX idx_users_email_active 
ON users (email) 
WHERE deleted = false;
-- Only enforces uniqueness among non-deleted rows!

-- MySQL workaround (no partial indexes):
-- Include deleted_at in unique constraint
CREATE UNIQUE INDEX idx_users_email_unique 
ON users (email, deleted_at);
-- Non-deleted: email + NULL (NULL != NULL in unique constraints!)
-- Deleted: email + timestamp (unique timestamps)
```

### Cascading Soft Delete

```java
@Service
public class ProjectService {
    
    @Transactional
    public void deleteProject(Long projectId, String deletedBy) {
        Project project = projectRepository.findById(projectId)
            .orElseThrow(() -> new NotFoundException("Project not found"));
        
        // Soft delete project
        project.setDeleted(true);
        project.setDeletedAt(Instant.now());
        project.setDeletedBy(deletedBy);
        
        // Cascade soft delete to related entities
        taskRepository.softDeleteByProjectId(projectId, deletedBy);
        commentRepository.softDeleteByProjectId(projectId, deletedBy);
        attachmentRepository.softDeleteByProjectId(projectId, deletedBy);
    }
}

public interface TaskRepository extends JpaRepository<Task, Long> {
    
    @Modifying
    @Query("UPDATE Task t SET t.deleted = true, t.deletedAt = :now, t.deletedBy = :by " +
           "WHERE t.projectId = :projectId AND t.deleted = false")
    int softDeleteByProjectId(@Param("projectId") Long projectId,
                              @Param("by") String deletedBy);
}
```

### Querying Including Deleted Records

```java
// Normal queries: @Where automatically filters deleted
List<Document> docs = documentRepository.findAll();  // Only non-deleted

// Admin view: need to see deleted records too
// Option 1: Native query bypassing @Where
@Query(value = "SELECT * FROM documents WHERE owner_id = :ownerId", nativeQuery = true)
List<Document> findAllIncludingDeleted(@Param("ownerId") Long ownerId);

// Option 2: Use @Filter (can be toggled)
@Entity
@FilterDef(name = "deletedFilter", parameters = @ParamDef(name = "isDeleted", type = Boolean.class))
@Filter(name = "deletedFilter", condition = "deleted = :isDeleted")
public class Document { ... }

// In service:
Session session = em.unwrap(Session.class);
session.enableFilter("deletedFilter").setParameter("isDeleted", false);
// Or disable for admin:
session.disableFilter("deletedFilter");
```

---

## 7. Performance-Oriented Schema Design

### Indexing Strategies for JPA Queries

```java
@Entity
@Table(name = "orders",
    indexes = {
        // Single column index for status queries
        @Index(name = "idx_orders_status", columnList = "status"),
        
        // Composite index matching common query pattern
        @Index(name = "idx_orders_customer_status", columnList = "customer_id, status"),
        
        // Composite index for date range + status (covering most dashboard queries)
        @Index(name = "idx_orders_status_created", columnList = "status, created_at DESC"),
        
        // Partial unique (via Flyway, not JPA annotation)
        // CREATE UNIQUE INDEX idx_orders_external_active ON orders(external_id) WHERE deleted = false
    })
public class Order {
    @Id @GeneratedValue private Long id;
    
    @Column(name = "customer_id", nullable = false)
    private Long customerId;
    
    @Enumerated(STRING)
    private OrderStatus status;
    
    @Column(name = "created_at", nullable = false)
    private Instant createdAt;
}

// Index design principle: match your most common query patterns
// Query: findByCustomerIdAndStatus → needs idx(customer_id, status)
// Query: findByStatusAndCreatedAtAfter → needs idx(status, created_at)
// Column ORDER in composite index matters! (leftmost prefix rule)
```

### Denormalization with JPA

```java
// Materialized aggregate count (avoid COUNT(*) every time)
@Entity
public class Category {
    @Id @GeneratedValue private Long id;
    private String name;
    
    // Denormalized count - updated when products are added/removed
    @Column(nullable = false)
    private int productCount = 0;
    
    public void incrementProductCount() { this.productCount++; }
    public void decrementProductCount() { this.productCount--; }
}

// Computed column with @Formula
@Entity
public class Product {
    @Id @GeneratedValue private Long id;
    private BigDecimal price;
    private BigDecimal discount;
    
    @Formula("price - discount")  // Computed by database, not stored
    private BigDecimal finalPrice;
    
    @Formula("(SELECT AVG(r.rating) FROM reviews r WHERE r.product_id = id)")
    private Double averageRating;  // Subquery formula
}

// @Generated for DB-computed columns
@Entity
public class AuditLog {
    @Id @GeneratedValue private Long id;
    
    @Generated(GenerationTime.INSERT)
    @Column(insertable = false, updatable = false)
    private Instant createdAt;  // DEFAULT NOW() in DB
}
```

---

## 8. Real-World Architecture Scenarios

### Scenario: Product Catalog with Variants

```java
// Product aggregate (core catalog)
@Entity
public class Product {
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private String id;
    
    private String name;
    private String brand;
    
    @Enumerated(STRING)
    private ProductType type;
    
    @OneToMany(cascade = ALL, orphanRemoval = true)
    @JoinColumn(name = "product_id")
    private List<ProductVariant> variants = new ArrayList<>();
    
    // Flexible attributes stored as JSON
    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> attributes;  // color, size options, material, etc.
    
    @ElementCollection
    @CollectionTable(name = "product_images")
    private List<String> imageUrls;
}

@Entity
public class ProductVariant {
    @Id @GeneratedValue
    private Long id;
    
    private String sku;
    
    @Embedded
    @AttributeOverride(name = "amount", column = @Column(name = "price_amount"))
    @AttributeOverride(name = "currency", column = @Column(name = "price_currency"))
    private Money price;
    
    // Variant-specific attributes (e.g., color=Red, size=XL)
    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb")
    private Map<String, String> variantAttributes;
    
    private int stockQuantity;
    private boolean active;
}

// Pricing tiers (separate aggregate - complex pricing logic)
@Entity
public class PricingTier {
    @Id @GeneratedValue
    private Long id;
    
    private String productId;  // Reference by ID
    private String tierName;   // "wholesale", "vip", "regular"
    private int minQuantity;
    
    @Embedded
    private Money unitPrice;
    
    private LocalDate validFrom;
    private LocalDate validTo;
}
```

### Scenario: RBAC + ABAC Permission System

```java
// Role-Based Access Control entities
@Entity
public class Role {
    @Id @GeneratedValue
    private Long id;
    
    @Column(unique = true, nullable = false)
    private String name;  // ADMIN, EDITOR, VIEWER
    
    @ManyToMany
    @JoinTable(name = "role_permissions",
        joinColumns = @JoinColumn(name = "role_id"),
        inverseJoinColumns = @JoinColumn(name = "permission_id"))
    private Set<Permission> permissions = new HashSet<>();
}

@Entity
public class Permission {
    @Id @GeneratedValue
    private Long id;
    
    @Column(nullable = false)
    private String resource;  // "orders", "products", "reports"
    
    @Column(nullable = false)
    private String action;    // "read", "write", "delete", "approve"
    
    // Attribute-Based condition (ABAC extension)
    @Column(columnDefinition = "jsonb")
    @Type(JsonType.class)
    private Map<String, Object> conditions;
    // e.g., {"department": "same_as_user", "amount_max": 10000}
}

@Entity
public class UserRole {
    @Id @GeneratedValue
    private Long id;
    
    private Long userId;
    
    @ManyToOne(fetch = LAZY)
    private Role role;
    
    // Scope: where does this role apply?
    private String scope;     // "global", "department:engineering", "project:123"
    
    private LocalDate validFrom;
    private LocalDate validTo;  // Temporary role assignments
}

// Authorization check
@Service
public class AuthorizationService {
    
    public boolean hasPermission(Long userId, String resource, String action, 
                                  Map<String, Object> context) {
        List<UserRole> userRoles = userRoleRepository
            .findActiveRolesForUser(userId, LocalDate.now());
        
        return userRoles.stream()
            .flatMap(ur -> ur.getRole().getPermissions().stream())
            .filter(p -> p.getResource().equals(resource) && p.getAction().equals(action))
            .anyMatch(p -> evaluateConditions(p.getConditions(), context));
    }
}
```

---

## 9. Key Interview Talking Points

### "How do you design aggregates with JPA?"

1. **Identify invariants** - what rules must always be true?
2. **Draw consistency boundaries** - what must be transactionally consistent?
3. **Keep aggregates small** - performance and concurrency benefit
4. **Reference other aggregates by ID** - loose coupling
5. **One repository per aggregate root** - no repository for child entities
6. **Use domain events** for cross-aggregate communication

### "How do you handle schema evolution in production?"

1. **Never use ddl-auto=update in production** - use Flyway/Liquibase
2. **Expand-contract pattern** for breaking changes
3. **Backward-compatible changes only** per deployment
4. **Test migrations** against production schema copy in CI
5. **Consider running versions** - old and new app versions coexist
6. **Monitor migration time** - large table ALTERs can lock for minutes

### "When do you choose JPA inheritance vs composition?"

- Use **@Embeddable** (composition) when: shared structure, no polymorphic queries needed
- Use **SINGLE_TABLE** when: few subtypes, similar columns, need polymorphic queries
- Use **JOINED** when: many unique columns per subtype, storage matters
- Use **TABLE_PER_CLASS** when: subtypes are independent, never query polymorphically
- Consider **no inheritance**: use enum discriminator + nullable fields (simplest)
