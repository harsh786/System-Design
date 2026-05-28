# Scenario-Based / Design Questions (Q196–Q200)

---

## Q196: Design a Complete E-Commerce Order Management System with JPA Entities

### Question

Design a complete e-commerce order management system with JPA entities. Show entity relationships, cascade types, fetch strategies, and explain your design decisions. Include Order, OrderItem, Product, Customer, Address entities.

### Answer

#### High-Level Entity Relationship Diagram (ASCII)

```
┌──────────────┐       1:N        ┌──────────────┐
│   Customer   │─────────────────▶│    Order     │
└──────┬───────┘                  └──────┬───────┘
       │                                 │
       │ 1:N                             │ 1:N
       ▼                                 ▼
┌──────────────┐                  ┌──────────────┐
│   Address    │                  │  OrderItem   │
└──────────────┘                  └──────┬───────┘
                                         │
                                         │ N:1
                                         ▼
                                  ┌──────────────┐
                                  │   Product    │
                                  └──────┬───────┘
                                         │
                                         │ N:1
                                         ▼
                                  ┌──────────────┐
                                  │   Category   │
                                  └──────────────┘
```

#### Entity Implementations

```java
@Entity
@Table(name = "customers")
public class Customer {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(nullable = false, unique = true)
    private String email;

    @Column(name = "phone_number")
    private String phoneNumber;

    // Addresses are part of the customer lifecycle
    @OneToMany(mappedBy = "customer", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Address> addresses = new ArrayList<>();

    // Orders should NOT be cascade-removed when customer is deleted (business rule)
    @OneToMany(mappedBy = "customer", cascade = {CascadeType.PERSIST, CascadeType.MERGE})
    @OrderBy("orderDate DESC")
    private List<Order> orders = new ArrayList<>();

    @Version
    private Long version; // Optimistic locking

    // Helper methods for bidirectional sync
    public void addAddress(Address address) {
        addresses.add(address);
        address.setCustomer(this);
    }

    public void removeAddress(Address address) {
        addresses.remove(address);
        address.setCustomer(null);
    }
}
```

```java
@Entity
@Table(name = "addresses")
public class Address {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AddressType type; // BILLING, SHIPPING

    @Column(nullable = false)
    private String street;

    private String street2;

    @Column(nullable = false)
    private String city;

    @Column(nullable = false)
    private String state;

    @Column(nullable = false, length = 10)
    private String zipCode;

    @Column(nullable = false, length = 2)
    private String country;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "customer_id", nullable = false)
    private Customer customer;

    @Column(name = "is_default")
    private boolean defaultAddress;
}

public enum AddressType {
    BILLING, SHIPPING
}
```

```java
@Entity
@Table(name = "orders", indexes = {
    @Index(name = "idx_order_customer", columnList = "customer_id"),
    @Index(name = "idx_order_date", columnList = "order_date"),
    @Index(name = "idx_order_status", columnList = "status")
})
public class Order {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "order_number", unique = true, nullable = false, length = 20)
    private String orderNumber;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "customer_id", nullable = false)
    private Customer customer;

    // OrderItems are fully owned by Order
    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderItem> items = new ArrayList<>();

    // Snapshot of address at time of order (not a reference to mutable Address)
    @Embedded
    @AttributeOverrides({
        @AttributeOverride(name = "street", column = @Column(name = "shipping_street")),
        @AttributeOverride(name = "city", column = @Column(name = "shipping_city")),
        @AttributeOverride(name = "state", column = @Column(name = "shipping_state")),
        @AttributeOverride(name = "zipCode", column = @Column(name = "shipping_zip")),
        @AttributeOverride(name = "country", column = @Column(name = "shipping_country"))
    })
    private OrderAddress shippingAddress;

    @Embedded
    @AttributeOverrides({
        @AttributeOverride(name = "street", column = @Column(name = "billing_street")),
        @AttributeOverride(name = "city", column = @Column(name = "billing_city")),
        @AttributeOverride(name = "state", column = @Column(name = "billing_state")),
        @AttributeOverride(name = "zipCode", column = @Column(name = "billing_zip")),
        @AttributeOverride(name = "country", column = @Column(name = "billing_country"))
    })
    private OrderAddress billingAddress;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OrderStatus status = OrderStatus.PENDING;

    @Column(name = "order_date", nullable = false)
    private LocalDateTime orderDate;

    @Column(name = "total_amount", precision = 12, scale = 2)
    private BigDecimal totalAmount;

    @Column(name = "discount_amount", precision = 10, scale = 2)
    private BigDecimal discountAmount = BigDecimal.ZERO;

    @Column(name = "tax_amount", precision = 10, scale = 2)
    private BigDecimal taxAmount;

    @Version
    private Long version;

    @PrePersist
    private void prePersist() {
        this.orderDate = LocalDateTime.now();
        this.orderNumber = generateOrderNumber();
    }

    // Helper methods
    public void addItem(OrderItem item) {
        items.add(item);
        item.setOrder(this);
        recalculateTotal();
    }

    public void removeItem(OrderItem item) {
        items.remove(item);
        item.setOrder(null);
        recalculateTotal();
    }

    private void recalculateTotal() {
        this.totalAmount = items.stream()
            .map(OrderItem::getSubtotal)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    private String generateOrderNumber() {
        return "ORD-" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE)
               + "-" + UUID.randomUUID().toString().substring(0, 6).toUpperCase();
    }
}

public enum OrderStatus {
    PENDING, CONFIRMED, PROCESSING, SHIPPED, DELIVERED, CANCELLED, REFUNDED
}
```

```java
@Embeddable
public class OrderAddress {
    private String street;
    private String city;
    private String state;
    private String zipCode;
    private String country;
}
```

```java
@Entity
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    // Reference to product — NOT cascade. Product has independent lifecycle.
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    // Snapshot the price at order time — products change price
    @Column(name = "unit_price", nullable = false, precision = 10, scale = 2)
    private BigDecimal unitPrice;

    @Column(nullable = false)
    private Integer quantity;

    @Column(name = "discount_percent", precision = 5, scale = 2)
    private BigDecimal discountPercent = BigDecimal.ZERO;

    // Snapshot product name for historical accuracy
    @Column(name = "product_name", nullable = false)
    private String productName;

    @Column(name = "product_sku", nullable = false)
    private String productSku;

    public BigDecimal getSubtotal() {
        BigDecimal base = unitPrice.multiply(BigDecimal.valueOf(quantity));
        BigDecimal discount = base.multiply(discountPercent)
                                  .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP);
        return base.subtract(discount);
    }
}
```

```java
@Entity
@Table(name = "products", indexes = {
    @Index(name = "idx_product_sku", columnList = "sku"),
    @Index(name = "idx_product_category", columnList = "category_id")
})
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 50)
    private String sku;

    @Column(nullable = false)
    private String name;

    @Column(length = 2000)
    private String description;

    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal price;

    @Column(name = "stock_quantity", nullable = false)
    private Integer stockQuantity;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "category_id")
    private Category category;

    @Column(nullable = false)
    private Boolean active = true;

    @Version
    private Long version; // Prevents concurrent stock updates from clobbering

    @Column(name = "created_at", updatable = false)
    @CreationTimestamp
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    public void decrementStock(int qty) {
        if (this.stockQuantity < qty) {
            throw new InsufficientStockException(
                "Product " + sku + " has only " + stockQuantity + " in stock");
        }
        this.stockQuantity -= qty;
    }
}
```

```java
@Entity
@Table(name = "categories")
public class Category {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String name;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "parent_id")
    private Category parent;

    @OneToMany(mappedBy = "parent")
    private List<Category> children = new ArrayList<>();

    @OneToMany(mappedBy = "category")
    private List<Product> products = new ArrayList<>();
}
```

#### Repository Layer with Optimized Queries

```java
public interface OrderRepository extends JpaRepository<Order, Long> {

    // Fetch order with items in a single query to avoid N+1
    @Query("SELECT DISTINCT o FROM Order o " +
           "JOIN FETCH o.items i " +
           "JOIN FETCH i.product " +
           "WHERE o.id = :id")
    Optional<Order> findByIdWithItems(@Param("id") Long id);

    // Paginated order history — no fetch join with collection (would break pagination)
    @EntityGraph(attributePaths = {"customer"})
    Page<Order> findByCustomerIdOrderByOrderDateDesc(Long customerId, Pageable pageable);

    // Projection for listing — don't load full entities
    @Query("SELECT new com.example.dto.OrderSummaryDTO(" +
           "o.id, o.orderNumber, o.status, o.totalAmount, o.orderDate, c.name) " +
           "FROM Order o JOIN o.customer c " +
           "WHERE o.status = :status")
    Page<OrderSummaryDTO> findOrderSummariesByStatus(
        @Param("status") OrderStatus status, Pageable pageable);
}
```

#### Service Layer

```java
@Service
@Transactional
public class OrderService {

    private final OrderRepository orderRepository;
    private final ProductRepository productRepository;
    private final CustomerRepository customerRepository;

    public Order createOrder(CreateOrderRequest request) {
        Customer customer = customerRepository.findById(request.getCustomerId())
            .orElseThrow(() -> new EntityNotFoundException("Customer not found"));

        Order order = new Order();
        order.setCustomer(customer);
        order.setShippingAddress(mapAddress(request.getShippingAddress()));
        order.setBillingAddress(mapAddress(request.getBillingAddress()));

        for (OrderItemRequest itemReq : request.getItems()) {
            Product product = productRepository.findById(itemReq.getProductId())
                .orElseThrow(() -> new EntityNotFoundException("Product not found"));

            // Optimistic lock will protect against concurrent stock decrements
            product.decrementStock(itemReq.getQuantity());

            OrderItem item = new OrderItem();
            item.setProduct(product);
            item.setQuantity(itemReq.getQuantity());
            item.setUnitPrice(product.getPrice()); // snapshot current price
            item.setProductName(product.getName());
            item.setProductSku(product.getSku());

            order.addItem(item);
        }

        order.setStatus(OrderStatus.CONFIRMED);
        return orderRepository.save(order);
    }
}
```

#### Design Decisions & Trade-offs

| Decision | Rationale |
|----------|-----------|
| **Embedded OrderAddress instead of FK to Address** | Addresses change over time. An order must preserve the address at time of purchase. |
| **Snapshot `unitPrice`, `productName`, `productSku` in OrderItem** | Products change price/name. Historical orders must remain accurate. |
| **`CascadeType.ALL` on Order→OrderItems** | Items have no meaning without their order. Full lifecycle coupling. |
| **No cascade delete on Customer→Orders** | Business rule: deleting a customer should soft-delete or archive, not destroy order history. |
| **`orphanRemoval = true` on OrderItems** | If an item is removed from the list, it should be deleted from DB. |
| **`FetchType.LAZY` on all `@ManyToOne`** | Default EAGER on ManyToOne causes unwanted joins. Always LAZY, fetch explicitly when needed. |
| **`@Version` on Product and Order** | Optimistic locking prevents lost updates on concurrent stock changes and order edits. |
| **`@Index` on frequently queried columns** | `customer_id`, `order_date`, `status` are common filter/sort columns. |
| **DTO projections for listings** | Full entity loading for list pages wastes memory and bandwidth. |
| **`@EntityGraph` for controlled eager loading** | Avoids N+1 without polluting entity mapping with fetch hints. |

#### Fetch Strategy Summary

```
┌────────────────────┬────────────────┬──────────────────────────────────────┐
│ Use Case           │ Strategy       │ Reason                               │
├────────────────────┼────────────────┼──────────────────────────────────────┤
│ View order detail  │ JOIN FETCH     │ Always need items + products          │
│ Order list page    │ DTO Projection │ Only need summary fields              │
│ Customer profile   │ EntityGraph    │ Need customer + default address       │
│ Product catalog    │ Pagination     │ Large dataset, no collection fetching │
│ Admin dashboard    │ Native query   │ Aggregations, no entities needed      │
└────────────────────┴────────────────┴──────────────────────────────────────┘
```

---

## Q197: Debugging and Optimizing a Production Performance Degradation

### Question

You have a production application with severe performance issues. The response time for listing products has gone from 200ms to 5 seconds. Describe your complete debugging and optimization approach using Hibernate/JPA tools and techniques.

### Answer

#### Phase 1: Immediate Diagnostics

```
┌──────────────────────────────────────────────────────────────────┐
│                    INCIDENT RESPONSE TIMELINE                      │
├──────────────────────────────────────────────────────────────────┤
│  T+0    Alert fires: p95 latency > 3s on GET /api/products       │
│  T+5m   Check APM dashboard (Datadog/NewRelic) for anomalies     │
│  T+10m  Correlate with deployment, data volume, traffic spike    │
│  T+15m  Enable SQL logging on canary instance                    │
│  T+30m  Root cause identified → implement fix                    │
│  T+45m  Deploy fix, monitor recovery                             │
└──────────────────────────────────────────────────────────────────┘
```

#### Step 1: Enable Hibernate SQL Logging

```yaml
# application.yml — TEMPORARY, never in production long-term
logging:
  level:
    org.hibernate.SQL: DEBUG
    org.hibernate.type.descriptor.sql.BasicBinder: TRACE  # Shows bind parameters
    org.hibernate.stat: DEBUG
    org.hibernate.engine.internal.StatisticalLoggingSessionEventListener: INFO

spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true
        session.events.log.LOG_QUERIES_SLOWER_THAN_MS: 100
```

#### Step 2: Analyze Hibernate Statistics

```java
@Component
@Slf4j
public class HibernateStatsLogger {

    @Autowired
    private EntityManagerFactory emf;

    @Scheduled(fixedRate = 60000) // Every minute
    public void logStats() {
        Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();
        log.info("=== Hibernate Statistics ===");
        log.info("Queries executed: {}", stats.getQueryExecutionCount());
        log.info("Slowest query: {} ({}ms)", 
            stats.getQueryExecutionMaxTimeQueryString(),
            stats.getQueryExecutionMaxTime());
        log.info("Second-level cache hit ratio: {}", stats.getSecondLevelCacheHitCount());
        log.info("Entity fetches: {}", stats.getEntityFetchCount());
        log.info("Collection fetches: {}", stats.getCollectionFetchCount());
        log.info("Connections obtained: {}", stats.getConnectCount());
        // Reset for next interval
        stats.clear();
    }
}
```

**Typical output revealing N+1:**
```
Queries executed: 1001   ← RED FLAG: listing 1000 products = 1 + 1000
Entity fetches: 1000     ← Each product triggers a category fetch
Slowest query: SELECT ... FROM categories WHERE id=? (2ms each, but 1000x = 2000ms)
```

#### Step 3: Identifying the N+1 Problem

**The problematic code:**
```java
// Repository
Page<Product> findAll(Pageable pageable);

// Service
public List<ProductDTO> listProducts(Pageable pageable) {
    Page<Product> products = productRepository.findAll(pageable);
    return products.stream()
        .map(p -> new ProductDTO(
            p.getId(),
            p.getName(),
            p.getCategory().getName(),  // ← N+1 TRIGGER!
            p.getPrice()
        ))
        .collect(Collectors.toList());
}
```

**Why it got worse:** The database grew from 100 to 1000 products per page (or someone changed page size), amplifying the N+1 from 101 to 1001 queries.

#### Step 4: Using DataSource Proxy to Count Queries

```java
@Configuration
@Profile("dev")
public class DataSourceProxyConfig {

    @Bean
    public DataSource dataSource(DataSource originalDataSource) {
        return ProxyDataSourceBuilder
            .create(originalDataSource)
            .name("query-counter")
            .countQuery()
            .logQueryBySlf4j(SLF4JLogLevel.INFO)
            .multiline()
            .build();
    }
}
```

Or use the `datasource-proxy-spring-boot-starter` + assertions in tests:

```java
@Test
void listProducts_shouldExecuteAtMost2Queries() {
    // Given 50 products exist
    
    // When
    productService.listProducts(PageRequest.of(0, 50));
    
    // Then — fails if N+1 exists
    assertThat(QueryCountHolder.getGrandTotal().getSelect()).isLessThanOrEqualTo(2);
}
```

#### Phase 2: Implementing Fixes

##### Fix 1: JOIN FETCH / EntityGraph

```java
public interface ProductRepository extends JpaRepository<Product, Long> {

    @EntityGraph(attributePaths = {"category"})
    Page<Product> findAllBy(Pageable pageable); 
    // Note: different method name to avoid overriding default findAll

    // Or with JPQL
    @Query("SELECT p FROM Product p LEFT JOIN FETCH p.category WHERE p.active = true")
    List<Product> findAllActiveWithCategory();
    // WARNING: JOIN FETCH + Pagination = in-memory pagination (bad for large sets)
}
```

##### Fix 2: DTO Projection (Best for list pages)

```java
public interface ProductRepository extends JpaRepository<Product, Long> {

    @Query("SELECT new com.example.dto.ProductListDTO(" +
           "p.id, p.name, p.sku, p.price, p.stockQuantity, c.name) " +
           "FROM Product p LEFT JOIN p.category c " +
           "WHERE p.active = true")
    Page<ProductListDTO> findProductListDTOs(Pageable pageable);
}
```
**Result: 1 query. No entity management overhead. Minimal data transfer.**

##### Fix 3: Batch Fetching (Quick fix, no query changes)

```yaml
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 32
```

This changes N+1 into N/32+1. For 1000 products → 1 + 32 queries instead of 1001.

##### Fix 4: Subselect Fetching

```java
@ManyToOne(fetch = FetchType.LAZY)
@Fetch(FetchMode.SUBSELECT)
private Category category;
```

Generates: `SELECT ... FROM categories WHERE id IN (SELECT category_id FROM products WHERE ...)`

#### Phase 3: Connection Pool Tuning

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20        # Default 10 may be too low
      minimum-idle: 5
      connection-timeout: 30000    # 30s — how long to wait for a connection
      idle-timeout: 600000         # 10min
      max-lifetime: 1800000        # 30min — must be less than DB wait_timeout
      leak-detection-threshold: 60000  # Log warning if connection held > 60s
```

**Diagnosis: Check if pool exhaustion is the issue:**
```java
@Scheduled(fixedRate = 30000)
public void logPoolStats() {
    HikariPoolMXBean pool = hikariDataSource.getHikariPoolMXBean();
    log.info("Pool stats — Active: {}, Idle: {}, Waiting: {}, Total: {}",
        pool.getActiveConnections(),
        pool.getIdleConnections(),
        pool.getThreadsAwaitingConnection(),
        pool.getTotalConnections());
}
```

**If `ThreadsAwaitingConnection > 0` consistently → pool is saturated.**

Sizing formula:
```
pool_size = Tn × (Cm − 1) + 1

Where:
  Tn = max concurrent threads
  Cm = max simultaneous connections needed per thread (usually 1)

Practical: pool_size ≈ CPU cores × 2 + effective_spindle_count
For most apps: 10-20 is sufficient. More is NOT better.
```

#### Phase 4: Second-Level Cache

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          region.factory_class: org.hibernate.cache.jcache.JCacheRegionFactory
        javax:
          cache:
            provider: org.ehcache.jsr107.EhcacheCachingProvider
```

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)  // For rarely-changing data
@Table(name = "categories")
public class Category {
    // Categories rarely change — excellent cache candidate
}
```

**Cache candidates:**
- Categories (read-heavy, write-rare) ✅
- Products (read-heavy, but prices change) — short TTL ⚠️
- Orders (write-heavy, unique access) ❌

#### Phase 5: Query Cache (Use Sparingly)

```java
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Category> findAllByActiveTrue();
```

**Warning:** Query cache is invalidated on ANY write to the table. Only useful for truly static data.

#### Performance Fix Summary & Results

```
┌───────────────────────┬─────────────┬─────────────┬───────────────────┐
│ Optimization          │ Before      │ After       │ Improvement       │
├───────────────────────┼─────────────┼─────────────┼───────────────────┤
│ DTO Projection        │ 1001 queries│ 1 query     │ 99.9% fewer       │
│ Batch fetch (32)      │ 1001 queries│ 33 queries  │ 96.7% fewer       │
│ L2 Cache on Category  │ 33 queries  │ 1 query     │ 97% fewer         │
│ Connection pool (20)  │ Timeouts    │ No timeouts │ Eliminated waits  │
│ Total response time   │ 5000ms      │ 150ms       │ 97% faster        │
└───────────────────────┴─────────────┴─────────────┴───────────────────┘
```

#### Ongoing Prevention

```java
// In integration tests — fail fast on N+1 regressions
@SpringBootTest
@AutoConfigureTestDatabase
public class PerformanceRegressionTest {

    @Autowired
    private DataSource dataSource; // datasource-proxy wrapped

    @Test
    void productListing_queryCount() {
        QueryCountHolder.clear();
        
        productService.listProducts(PageRequest.of(0, 100));
        
        QueryCount count = QueryCountHolder.getGrandTotal();
        assertThat(count.getSelect())
            .as("Product listing should use at most 2 SELECT queries")
            .isLessThanOrEqualTo(2);
    }
}
```

---

## Q198: Designing a Multi-Tenant SaaS Application with Spring Boot and Hibernate

### Question

Design a multi-tenant SaaS application using Spring Boot and Hibernate. Explain: tenant isolation strategy, how to route requests to correct tenant, schema management, data migration across tenants, handling shared vs tenant-specific data.

### Answer

#### Multi-Tenancy Strategy Options

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-TENANCY ISOLATION STRATEGIES                         │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│                  │ Separate DB      │ Separate Schema  │ Shared Schema      │
│                  │ (Database/tenant)│ (Schema/tenant)  │ (Discriminator)    │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│ Isolation        │ ★★★★★           │ ★★★★             │ ★★                 │
│ Scalability      │ ★★               │ ★★★              │ ★★★★★             │
│ Cost             │ Expensive        │ Moderate          │ Cheapest           │
│ Complexity       │ High             │ Medium            │ Low                │
│ Cross-tenant     │ Impossible       │ Hard              │ Risk of data leak  │
│ Customization    │ Full per-tenant  │ Schema-level      │ Limited            │
│ Maintenance      │ Hard (N DBs)     │ Moderate          │ Easy (1 schema)    │
│ Compliance       │ Best (GDPR etc)  │ Good              │ Challenging        │
│ Backup/Restore   │ Per-tenant easy  │ Moderate          │ All-or-nothing     │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│ Use when         │ Enterprise/      │ Mid-market SaaS  │ High-volume,       │
│                  │ regulated        │ moderate tenants  │ thousands of       │
│                  │ industries       │ (100s)            │ small tenants      │
└──────────────────┴──────────────────┴──────────────────┴────────────────────┘
```

#### Chosen Strategy: Schema-per-Tenant (Balanced approach)

#### Architecture Overview

```
                    ┌─────────────────────┐
                    │   Load Balancer     │
                    │  (extracts tenant   │
                    │   from subdomain)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Spring Boot App    │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │TenantFilter   │  │  ← Extracts tenant ID
                    │  │(OncePerReq)   │  │
                    │  └───────┬───────┘  │
                    │          │           │
                    │  ┌───────▼───────┐  │
                    │  │TenantContext  │  │  ← ThreadLocal storage
                    │  │(ThreadLocal)  │  │
                    │  └───────┬───────┘  │
                    │          │           │
                    │  ┌───────▼───────┐  │
                    │  │MultiTenant    │  │  ← Routes to correct schema
                    │  │ConnectionProv │  │
                    │  └───────┬───────┘  │
                    │          │           │
                    └──────────┼──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐ ┌─────▼──────────┐
    │ schema_tenant_a│ │schema_tenant_b│ │ schema_shared  │
    │ (orders, etc.) │ │(orders, etc.)│ │ (plans, config)│
    └────────────────┘ └──────────────┘ └────────────────┘
```

#### Implementation

##### 1. Tenant Context (ThreadLocal)

```java
public class TenantContext {

    private static final ThreadLocal<String> CURRENT_TENANT = new InheritableThreadLocal<>();

    public static String getCurrentTenant() {
        String tenant = CURRENT_TENANT.get();
        if (tenant == null) {
            throw new TenantNotSetException("No tenant context available");
        }
        return tenant;
    }

    public static void setCurrentTenant(String tenantId) {
        CURRENT_TENANT.set(tenantId);
    }

    public static void clear() {
        CURRENT_TENANT.remove();
    }
}
```

##### 2. Tenant Resolution Filter

```java
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TenantResolutionFilter extends OncePerRequestFilter {

    private final TenantRepository tenantRepository;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        try {
            String tenantId = resolveTenant(request);
            if (tenantId != null) {
                validateTenant(tenantId);
                TenantContext.setCurrentTenant(tenantId);
            }
            chain.doFilter(request, response);
        } finally {
            TenantContext.clear(); // CRITICAL: prevent tenant leakage
        }
    }

    private String resolveTenant(HttpServletRequest request) {
        // Strategy 1: Subdomain — acme.myapp.com → "acme"
        String host = request.getServerName();
        if (host.contains(".")) {
            String subdomain = host.split("\\.")[0];
            if (!"www".equals(subdomain) && !"api".equals(subdomain)) {
                return subdomain;
            }
        }

        // Strategy 2: Header — X-Tenant-ID: acme
        String headerTenant = request.getHeader("X-Tenant-ID");
        if (headerTenant != null) {
            return headerTenant;
        }

        // Strategy 3: JWT claim
        // Extract from security context after authentication
        return null;
    }

    private void validateTenant(String tenantId) {
        // Validate against a shared registry (cached)
        if (!tenantRepository.existsByTenantId(tenantId)) {
            throw new TenantNotFoundException("Unknown tenant: " + tenantId);
        }
    }
}
```

##### 3. Hibernate Multi-Tenancy Configuration

```java
@Configuration
public class HibernateMultiTenantConfig {

    @Bean
    public LocalContainerEntityManagerFactoryBean entityManagerFactory(
            DataSource dataSource,
            MultiTenantConnectionProvider connectionProvider,
            CurrentTenantIdentifierResolver tenantResolver) {

        LocalContainerEntityManagerFactoryBean em = new LocalContainerEntityManagerFactoryBean();
        em.setDataSource(dataSource);
        em.setPackagesToScan("com.example.tenant.entity");

        Map<String, Object> properties = new HashMap<>();
        properties.put(Environment.MULTI_TENANT, MultiTenancyStrategy.SCHEMA);
        properties.put(Environment.MULTI_TENANT_CONNECTION_PROVIDER, connectionProvider);
        properties.put(Environment.MULTI_TENANT_IDENTIFIER_RESOLVER, tenantResolver);
        properties.put(Environment.HBM2DDL_AUTO, "none"); // Flyway handles schema
        properties.put(Environment.SHOW_SQL, false);

        HibernateJpaVendorAdapter vendor = new HibernateJpaVendorAdapter();
        vendor.setDatabase(Database.POSTGRESQL);
        em.setJpaVendorAdapter(vendor);
        em.setJpaPropertyMap(properties);

        return em;
    }
}
```

##### 4. Connection Provider

```java
@Component
public class SchemaMultiTenantConnectionProvider implements MultiTenantConnectionProvider {

    private final DataSource dataSource;

    @Override
    public Connection getAnyConnection() throws SQLException {
        return dataSource.getConnection();
    }

    @Override
    public void releaseAnyConnection(Connection connection) throws SQLException {
        connection.close();
    }

    @Override
    public Connection getConnection(String tenantIdentifier) throws SQLException {
        Connection connection = getAnyConnection();
        // Set the search_path for PostgreSQL
        connection.createStatement().execute(
            "SET search_path TO " + sanitizeSchemaName(tenantIdentifier));
        return connection;
    }

    @Override
    public void releaseConnection(String tenantIdentifier, Connection connection) 
            throws SQLException {
        // Reset to default schema
        connection.createStatement().execute("SET search_path TO public");
        connection.close();
    }

    private String sanitizeSchemaName(String tenantId) {
        // CRITICAL: Prevent SQL injection in schema name
        if (!tenantId.matches("^[a-z0-9_]+$")) {
            throw new IllegalArgumentException("Invalid tenant identifier: " + tenantId);
        }
        return "tenant_" + tenantId;
    }

    @Override
    public boolean supportsAggressiveRelease() {
        return false;
    }

    @Override
    public boolean isUnwrappableAs(Class<?> unwrapType) {
        return false;
    }

    @Override
    public <T> T unwrap(Class<T> unwrapType) {
        throw new UnsupportedOperationException();
    }
}
```

##### 5. Tenant Identifier Resolver

```java
@Component
public class CurrentTenantIdentifierResolverImpl implements CurrentTenantIdentifierResolver {

    @Override
    public String resolveCurrentTenantIdentifier() {
        try {
            return TenantContext.getCurrentTenant();
        } catch (TenantNotSetException e) {
            return "public"; // Fallback for non-tenant operations (migrations, health checks)
        }
    }

    @Override
    public boolean validateExistingCurrentSessions() {
        return true;
    }
}
```

##### 6. Schema Management with Flyway

```java
@Service
public class TenantSchemaManager {

    private final DataSource dataSource;
    
    @Value("classpath:db/tenant")
    private String tenantMigrationsLocation;

    /**
     * Called when a new tenant signs up.
     */
    public void provisionTenant(String tenantId) {
        String schema = "tenant_" + tenantId;

        // Create schema
        try (Connection conn = dataSource.getConnection();
             Statement stmt = conn.createStatement()) {
            stmt.execute("CREATE SCHEMA IF NOT EXISTS " + schema);
        }

        // Run Flyway migrations for the new schema
        Flyway flyway = Flyway.configure()
            .dataSource(dataSource)
            .schemas(schema)
            .locations("classpath:db/tenant")
            .baselineOnMigrate(true)
            .load();
        flyway.migrate();
    }

    /**
     * Called on application startup to ensure all tenants are up to date.
     */
    @EventListener(ApplicationReadyEvent.class)
    public void migrateAllTenants() {
        List<String> tenantIds = getAllTenantIds();
        for (String tenantId : tenantIds) {
            provisionTenant(tenantId);
        }
    }

    private List<String> getAllTenantIds() {
        // Query from shared schema's tenant registry
        try (Connection conn = dataSource.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(
                 "SELECT tenant_id FROM public.tenants WHERE active = true")) {
            List<String> ids = new ArrayList<>();
            while (rs.next()) {
                ids.add(rs.getString("tenant_id"));
            }
            return ids;
        } catch (SQLException e) {
            throw new RuntimeException("Failed to load tenant list", e);
        }
    }
}
```

##### 7. Handling Shared vs Tenant-Specific Data

```java
// Shared entities use a separate EntityManagerFactory pointing to "public" schema
@Configuration
public class SharedDataConfig {

    @Bean(name = "sharedEntityManagerFactory")
    public LocalContainerEntityManagerFactoryBean sharedEntityManagerFactory(
            DataSource dataSource) {
        LocalContainerEntityManagerFactoryBean em = new LocalContainerEntityManagerFactoryBean();
        em.setDataSource(dataSource);
        em.setPackagesToScan("com.example.shared.entity");
        em.setPersistenceUnitName("shared");

        Map<String, Object> props = new HashMap<>();
        props.put(Environment.DEFAULT_SCHEMA, "public");
        em.setJpaPropertyMap(props);

        return em;
    }

    @Bean(name = "sharedTransactionManager")
    public PlatformTransactionManager sharedTransactionManager(
            @Qualifier("sharedEntityManagerFactory") EntityManagerFactory emf) {
        return new JpaTransactionManager(emf);
    }
}
```

```java
// Shared entities — visible to all tenants
@Entity
@Table(name = "subscription_plans", schema = "public")
public class SubscriptionPlan {
    @Id
    private Long id;
    private String name;
    private BigDecimal monthlyPrice;
    private Integer maxUsers;
}

// Tenant-specific entity — automatically routed
@Entity
@Table(name = "projects")
public class Project {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    // No tenant_id column needed — schema isolation handles it
}
```

##### 8. Cross-Tenant Data Migration

```java
@Service
public class TenantDataMigrationService {

    private final DataSource dataSource;

    /**
     * Migrate a user's data from one tenant to another (e.g., company acquisition).
     */
    @Transactional
    public void migrateUserData(String sourceTenant, String targetTenant, Long userId) {
        String sourceSchema = "tenant_" + sourceTenant;
        String targetSchema = "tenant_" + targetTenant;

        try (Connection conn = dataSource.getConnection();
             Statement stmt = conn.createStatement()) {

            // Migrate user's projects
            stmt.execute(String.format(
                "INSERT INTO %s.projects (name, description, created_by, created_at) " +
                "SELECT name, description, %d, NOW() " +
                "FROM %s.projects WHERE created_by = %d",
                targetSchema, userId, sourceSchema, userId));

            // Mark as migrated in source
            stmt.execute(String.format(
                "UPDATE %s.projects SET migrated = true WHERE created_by = %d",
                sourceSchema, userId));
        } catch (SQLException e) {
            throw new DataMigrationException("Failed to migrate user data", e);
        }
    }
}
```

##### 9. Async Operations & Tenant Context Propagation

```java
@Configuration
@EnableAsync
public class AsyncConfig implements AsyncConfigurer {

    @Override
    public Executor getAsyncExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        // Wrap with tenant-aware decorator
        executor.setTaskDecorator(new TenantAwareTaskDecorator());
        executor.initialize();
        return executor;
    }
}

public class TenantAwareTaskDecorator implements TaskDecorator {
    @Override
    public Runnable decorate(Runnable runnable) {
        // Capture tenant from current thread
        String tenantId = TenantContext.getCurrentTenant();
        return () -> {
            try {
                TenantContext.setCurrentTenant(tenantId);
                runnable.run();
            } finally {
                TenantContext.clear();
            }
        };
    }
}
```

#### Security Considerations

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY CHECKLIST                             │
├─────────────────────────────────────────────────────────────────┤
│ ✓ Sanitize tenant ID before using in schema name (SQL injection)│
│ ✓ Always clear ThreadLocal after request (tenant leakage)       │
│ ✓ Validate tenant exists before setting context                 │
│ ✓ JWT tenant claim must match request tenant (cross-tenant)     │
│ ✓ Row-level security in DB as defense-in-depth                  │
│ ✓ Separate connection pool per tenant for noisy-neighbor guard  │
│ ✓ Audit log all cross-tenant operations                         │
│ ✓ Encrypt tenant data at rest with tenant-specific keys         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Q199: Migrating a Legacy JDBC Application to Spring Data JPA

### Question

You need to migrate a legacy application from plain JDBC to Spring Data JPA. Describe the complete migration strategy.

### Answer

#### Migration Strategy Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MIGRATION PHASES                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4 ──▶ Phase 5            │
│  Assess      Parallel     Migrate     Migrate     Remove             │
│  & Plan      Run (JPA     Simple      Complex     Legacy             │
│              alongside)   CRUD        Queries                        │
│                                                                       │
│  Duration:   Duration:    Duration:   Duration:   Duration:           │
│  1-2 weeks   1 week       2-4 weeks   2-4 weeks   1-2 weeks          │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

#### Phase 1: Assessment & Entity Design

##### Analyzing Existing Tables

```sql
-- Legacy schema (what we're working with)
CREATE TABLE customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    status CHAR(1) DEFAULT 'A',  -- 'A'ctive, 'I'nactive, 'S'uspended
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    loyalty_points INT DEFAULT 0
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    cust_id INT REFERENCES customers(customer_id),
    order_dt TIMESTAMP,
    total_amt DECIMAL(10,2),
    status VARCHAR(20),
    notes TEXT,
    -- Legacy: some columns are denormalized
    cust_name VARCHAR(100),  -- duplicated from customers
    cust_email VARCHAR(100)  -- duplicated from customers
);

-- Legacy stored procedure
DELIMITER //
CREATE PROCEDURE sp_calculate_loyalty(IN cust_id INT, OUT points INT)
BEGIN
    SELECT SUM(total_amt) * 10 INTO points
    FROM orders
    WHERE cust_id = cust_id AND order_dt > DATE_SUB(NOW(), INTERVAL 1 YEAR);
END //
```

##### Designing JPA Entities from Legacy Tables

```java
@Entity
@Table(name = "customers")  // Map to EXISTING table — no schema changes yet
public class Customer {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "customer_id")  // Legacy column name mapping
    private Long id;

    @Column(name = "first_name", nullable = false, length = 50)
    private String firstName;

    @Column(name = "last_name", nullable = false, length = 50)
    private String lastName;

    @Column(unique = true, length = 100)
    private String email;

    // Legacy CHAR(1) status — use converter instead of enum
    @Convert(converter = CustomerStatusConverter.class)
    @Column(name = "status", columnDefinition = "CHAR(1)")
    private CustomerStatus status;

    @Column(name = "created_date", updatable = false)
    private LocalDateTime createdDate;

    @Column(name = "loyalty_points")
    private Integer loyaltyPoints;

    @OneToMany(mappedBy = "customer", fetch = FetchType.LAZY)
    private List<Order> orders = new ArrayList<>();
}

// Converter for legacy CHAR(1) status codes
@Converter
public class CustomerStatusConverter implements AttributeConverter<CustomerStatus, String> {

    @Override
    public String convertToDatabaseColumn(CustomerStatus status) {
        if (status == null) return null;
        return switch (status) {
            case ACTIVE -> "A";
            case INACTIVE -> "I";
            case SUSPENDED -> "S";
        };
    }

    @Override
    public CustomerStatus convertToEntityAttribute(String code) {
        if (code == null) return null;
        return switch (code) {
            case "A" -> CustomerStatus.ACTIVE;
            case "I" -> CustomerStatus.INACTIVE;
            case "S" -> CustomerStatus.SUSPENDED;
            default -> throw new IllegalArgumentException("Unknown status: " + code);
        };
    }
}
```

#### Phase 2: Parallel Infrastructure (Both JDBC and JPA coexist)

```java
@Configuration
public class DualDataAccessConfig {

    // Keep legacy JdbcTemplate available
    @Bean
    public JdbcTemplate jdbcTemplate(DataSource dataSource) {
        return new JdbcTemplate(dataSource);
    }

    // JPA EntityManager uses same DataSource
    // Both share the same transaction manager
    @Bean
    public PlatformTransactionManager transactionManager(EntityManagerFactory emf) {
        return new JpaTransactionManager(emf);
        // JpaTransactionManager also supports JDBC operations on same DataSource
    }
}
```

```java
// Feature flag to toggle between legacy and new implementation
@Service
public class CustomerService {

    private final CustomerLegacyDao legacyDao;   // JDBC-based
    private final CustomerRepository jpaRepo;     // JPA-based
    
    @Value("${feature.use-jpa-customers:false}")
    private boolean useJpa;

    public Customer findById(Long id) {
        if (useJpa) {
            return jpaRepo.findById(id).orElseThrow();
        }
        return legacyDao.findById(id);
    }
}
```

#### Phase 3: Migrating Simple CRUD

**Legacy JDBC code:**
```java
// BEFORE — 50+ lines for a simple findById
public class CustomerLegacyDao {
    private final JdbcTemplate jdbc;

    public Customer findById(Long id) {
        return jdbc.queryForObject(
            "SELECT * FROM customers WHERE customer_id = ?",
            new Object[]{id},
            (rs, rowNum) -> {
                Customer c = new Customer();
                c.setId(rs.getLong("customer_id"));
                c.setFirstName(rs.getString("first_name"));
                c.setLastName(rs.getString("last_name"));
                c.setEmail(rs.getString("email"));
                // ... more boilerplate
                return c;
            });
    }

    public void save(Customer customer) {
        if (customer.getId() == null) {
            KeyHolder keyHolder = new GeneratedKeyHolder();
            jdbc.update(conn -> {
                PreparedStatement ps = conn.prepareStatement(
                    "INSERT INTO customers (first_name, last_name, email, status) VALUES (?,?,?,?)",
                    Statement.RETURN_GENERATED_KEYS);
                ps.setString(1, customer.getFirstName());
                ps.setString(2, customer.getLastName());
                ps.setString(3, customer.getEmail());
                ps.setString(4, "A");
                return ps;
            }, keyHolder);
            customer.setId(keyHolder.getKey().longValue());
        } else {
            jdbc.update(
                "UPDATE customers SET first_name=?, last_name=?, email=? WHERE customer_id=?",
                customer.getFirstName(), customer.getLastName(),
                customer.getEmail(), customer.getId());
        }
    }
}
```

**After — JPA replacement:**
```java
// AFTER — 5 lines
public interface CustomerRepository extends JpaRepository<Customer, Long> {
    Optional<Customer> findByEmail(String email);
    List<Customer> findByStatus(CustomerStatus status);
}
```

#### Phase 4: Handling Complex Legacy Queries and Stored Procedures

##### Complex Native Queries

```java
public interface OrderRepository extends JpaRepository<Order, Long> {

    // Legacy complex query — keep as native to avoid rewrite risk
    @Query(value = """
        SELECT o.order_id, o.order_dt, o.total_amt,
               c.first_name, c.last_name,
               (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = o.order_id) as item_count
        FROM orders o
        JOIN customers c ON o.cust_id = c.customer_id
        WHERE o.order_dt BETWEEN :startDate AND :endDate
          AND o.status IN (:statuses)
          AND o.total_amt > :minAmount
        ORDER BY o.order_dt DESC
        """, nativeQuery = true)
    List<Object[]> findOrdersForReport(
        @Param("startDate") LocalDateTime startDate,
        @Param("endDate") LocalDateTime endDate,
        @Param("statuses") List<String> statuses,
        @Param("minAmount") BigDecimal minAmount);

    // Better: use interface projection
    @Query(value = "...", nativeQuery = true)
    List<OrderReportProjection> findOrdersForReportProjected(...);
}

interface OrderReportProjection {
    Long getOrderId();
    LocalDateTime getOrderDt();
    BigDecimal getTotalAmt();
    String getFirstName();
    String getLastName();
    Integer getItemCount();
}
```

##### Calling Stored Procedures

```java
@Entity
@NamedStoredProcedureQuery(
    name = "Customer.calculateLoyalty",
    procedureName = "sp_calculate_loyalty",
    parameters = {
        @StoredProcedureParameter(name = "cust_id", mode = ParameterMode.IN, type = Long.class),
        @StoredProcedureParameter(name = "points", mode = ParameterMode.OUT, type = Integer.class)
    }
)
public class Customer { /* ... */ }

// Usage in repository
public interface CustomerRepository extends JpaRepository<Customer, Long> {

    @Procedure(name = "Customer.calculateLoyalty")
    Integer calculateLoyalty(@Param("cust_id") Long customerId);
}

// Or programmatically
@Service
public class LoyaltyService {

    @PersistenceContext
    private EntityManager em;

    public int calculateLoyaltyPoints(Long customerId) {
        StoredProcedureQuery query = em
            .createStoredProcedureQuery("sp_calculate_loyalty")
            .registerStoredProcedureParameter("cust_id", Long.class, ParameterMode.IN)
            .registerStoredProcedureParameter("points", Integer.class, ParameterMode.OUT)
            .setParameter("cust_id", customerId);

        query.execute();
        return (Integer) query.getOutputParameterValue("points");
    }
}
```

##### Long-term Plan: Replace Stored Procedures with Application Logic

```java
// Phase 4b: Rewrite stored procedure logic in Java
@Service
public class LoyaltyService {

    private final OrderRepository orderRepository;

    /**
     * Replaces sp_calculate_loyalty stored procedure.
     * Easier to test, version, and deploy.
     */
    public int calculateLoyaltyPoints(Long customerId) {
        LocalDateTime oneYearAgo = LocalDateTime.now().minusYears(1);
        BigDecimal totalSpent = orderRepository.sumOrderAmountByCustomerSince(
            customerId, oneYearAgo);
        return totalSpent.multiply(BigDecimal.TEN).intValue();
    }
}
```

#### Phase 5: Transaction Management Migration

**Legacy:**
```java
// BEFORE — manual transaction management
public void transferOrder(Long orderId, Long newCustomerId) {
    Connection conn = null;
    try {
        conn = dataSource.getConnection();
        conn.setAutoCommit(false);

        // Update order
        PreparedStatement ps1 = conn.prepareStatement(
            "UPDATE orders SET cust_id = ? WHERE order_id = ?");
        ps1.setLong(1, newCustomerId);
        ps1.setLong(2, orderId);
        ps1.executeUpdate();

        // Update denormalized fields
        PreparedStatement ps2 = conn.prepareStatement(
            "UPDATE orders SET cust_name = (SELECT CONCAT(first_name,' ',last_name) " +
            "FROM customers WHERE customer_id = ?) WHERE order_id = ?");
        ps2.setLong(1, newCustomerId);
        ps2.setLong(2, orderId);
        ps2.executeUpdate();

        conn.commit();
    } catch (Exception e) {
        if (conn != null) conn.rollback();
        throw new RuntimeException(e);
    } finally {
        if (conn != null) conn.close();
    }
}
```

**After:**
```java
// AFTER — declarative transactions
@Service
@Transactional
public class OrderTransferService {

    private final OrderRepository orderRepository;
    private final CustomerRepository customerRepository;

    public void transferOrder(Long orderId, Long newCustomerId) {
        Order order = orderRepository.findById(orderId)
            .orElseThrow(() -> new EntityNotFoundException("Order not found"));
        Customer newCustomer = customerRepository.findById(newCustomerId)
            .orElseThrow(() -> new EntityNotFoundException("Customer not found"));

        order.setCustomer(newCustomer);
        // Denormalized fields handled by @PreUpdate or removed entirely
    }
}
```

#### Testing Strategy

```java
// 1. Verification tests: ensure JPA produces same results as JDBC
@SpringBootTest
public class MigrationVerificationTest {

    @Autowired private CustomerLegacyDao legacyDao;
    @Autowired private CustomerRepository jpaRepo;

    @Test
    void findById_sameResult() {
        Customer legacy = legacyDao.findById(1L);
        Customer jpa = jpaRepo.findById(1L).orElseThrow();

        assertThat(jpa.getFirstName()).isEqualTo(legacy.getFirstName());
        assertThat(jpa.getLastName()).isEqualTo(legacy.getLastName());
        assertThat(jpa.getEmail()).isEqualTo(legacy.getEmail());
        assertThat(jpa.getStatus()).isEqualTo(legacy.getStatus());
    }

    @Test
    void save_producesIdenticalDbState() {
        Customer c = new Customer();
        c.setFirstName("Test");
        c.setLastName("User");
        c.setEmail("migration-test@example.com");
        c.setStatus(CustomerStatus.ACTIVE);

        Customer saved = jpaRepo.save(c);

        // Verify using raw JDBC that DB state is correct
        Map<String, Object> row = jdbcTemplate.queryForMap(
            "SELECT * FROM customers WHERE customer_id = ?", saved.getId());

        assertThat(row.get("first_name")).isEqualTo("Test");
        assertThat(row.get("status")).isEqualTo("A");
    }
}

// 2. Performance regression test
@Test
void orderListing_noPerformanceRegression() {
    long start = System.currentTimeMillis();
    List<Order> orders = orderRepository.findByCustomerId(1L, PageRequest.of(0, 100));
    long elapsed = System.currentTimeMillis() - start;

    assertThat(elapsed).isLessThan(500); // Must be under 500ms
}
```

#### Rollback Plan

```yaml
# Feature flags in application.yml
feature:
  use-jpa:
    customers: true    # Flip to false to rollback customers to JDBC
    orders: false      # Not yet migrated
    products: true     # Migrated and verified
```

```java
@Service
public class CustomerService {

    @Autowired private CustomerLegacyDao legacyDao;
    @Autowired private CustomerRepository jpaRepo;

    @Value("${feature.use-jpa.customers:false}")
    private boolean useJpa;

    public Customer findById(Long id) {
        return useJpa
            ? jpaRepo.findById(id).orElseThrow()
            : legacyDao.findById(id);
    }
}
```

#### Migration Checklist

```
┌───────────────────────────────────────────────────────────────────────┐
│ □ Audit all JDBC DAOs — list methods, queries, transactions           │
│ □ Map tables to entities with correct column names                    │
│ □ Handle all legacy quirks (CHAR codes, nullable FKs, denormalized)   │
│ □ Keep schema UNCHANGED — JPA maps to existing structure              │
│ □ Stored procedures: wrap first, rewrite later                        │
│ □ Verification tests for every DAO method before switching            │
│ □ Feature flags for per-entity rollback                               │
│ □ Monitor query count and response time after each switch             │
│ □ One entity at a time — never big-bang                               │
│ □ Remove legacy code only after 2+ weeks stable in production         │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Q200: Designing a High-Throughput Event Logging System

### Question

Design a high-throughput event logging system that needs to persist millions of events per day using Spring Boot and JPA/Hibernate. Cover: batch insertion strategy, connection pool sizing, async processing, partitioning strategy, when to bypass JPA for raw JDBC, read vs write optimization, archival strategy.

### Answer

#### System Requirements

```
┌─────────────────────────────────────────────────────────────────────┐
│ REQUIREMENTS                                                         │
├─────────────────────────────────────────────────────────────────────┤
│ • 10 million events/day (~115 events/second avg, 1000/sec peak)     │
│ • Event size: ~1KB average                                           │
│ • Write latency: < 50ms (p99) from application perspective          │
│ • Read: dashboard queries (aggregations), event search by criteria  │
│ • Retention: hot (30 days), warm (1 year), cold (archive forever)   │
│ • Zero data loss — events must not be dropped                        │
└─────────────────────────────────────────────────────────────────────┘
```

#### Architecture Overview

```
┌──────────┐     ┌──────────────────┐     ┌─────────────────┐
│ App/API  │────▶│  In-Memory Queue │────▶│  Batch Writer   │
│ (Events) │     │  (Disruptor/     │     │  (Scheduled     │
└──────────┘     │   BlockingQueue) │     │   flush every   │
                 └──────────────────┘     │   100ms or 500  │
                                          │   events)       │
                                          └────────┬────────┘
                                                   │
                              ┌─────────────────────┼────────────────────┐
                              │                     │                    │
                              ▼                     ▼                    ▼
                    ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐
                    │  PostgreSQL     │  │  PostgreSQL      │  │  PostgreSQL   │
                    │  Partition:     │  │  Partition:      │  │  Partition:   │
                    │  events_2024_01 │  │  events_2024_02  │  │  events_cur  │
                    └─────────────────┘  └──────────────────┘  └───────────────┘
                                                                       │
                    ┌──────────────────────────────────────────────────┘
                    │ Nightly archival job
                    ▼
           ┌─────────────────┐
           │  S3 / Cold      │
           │  Storage        │
           │  (Parquet)      │
           └─────────────────┘
```

#### Entity Design

```java
@Entity
@Table(name = "events", indexes = {
    @Index(name = "idx_events_timestamp", columnList = "event_timestamp"),
    @Index(name = "idx_events_type", columnList = "event_type"),
    @Index(name = "idx_events_source", columnList = "source_service"),
    @Index(name = "idx_events_correlation", columnList = "correlation_id")
})
public class Event {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "event_seq")
    @SequenceGenerator(name = "event_seq", sequenceName = "event_id_seq", allocationSize = 500)
    // allocationSize=500: pre-allocates 500 IDs per call — critical for batch performance
    private Long id;

    @Column(name = "event_type", nullable = false, length = 50)
    private String eventType;

    @Column(name = "source_service", nullable = false, length = 100)
    private String sourceService;

    @Column(name = "correlation_id", length = 36)
    private String correlationId;

    @Column(name = "event_timestamp", nullable = false)
    private Instant eventTimestamp;

    @Column(name = "payload", columnDefinition = "jsonb")
    private String payload; // JSON string — no entity graph complexity

    @Column(name = "user_id")
    private String userId;

    @Column(name = "severity", length = 10)
    private String severity;

    @Column(name = "ingested_at", nullable = false)
    private Instant ingestedAt;
}
```

**Key decision: No relationships.** Events are denormalized documents. No `@ManyToOne`, no lazy loading, no N+1 possibility. This is intentional for write throughput.

#### Batch Insertion Strategy

##### Option A: JPA with Hibernate Batching (for moderate throughput)

```yaml
spring:
  jpa:
    properties:
      hibernate:
        jdbc:
          batch_size: 500
          batch_versioned_data: true
        order_inserts: true
        order_updates: true
        # CRITICAL: Use SEQUENCE strategy, not IDENTITY
        # IDENTITY disables batching because DB must return each ID immediately
```

```java
@Service
public class EventBatchWriter {

    @PersistenceContext
    private EntityManager em;

    @Transactional
    public void writeBatch(List<Event> events) {
        for (int i = 0; i < events.size(); i++) {
            em.persist(events.get(i));
            if (i % 500 == 0 && i > 0) {
                em.flush();   // Push to DB
                em.clear();   // Free memory — prevent persistence context bloat
            }
        }
    }
}
```

##### Option B: Bypass JPA — Raw JDBC Batch (for maximum throughput)

```java
@Repository
public class EventJdbcBatchWriter {

    private final JdbcTemplate jdbcTemplate;

    private static final String INSERT_SQL =
        "INSERT INTO events (id, event_type, source_service, correlation_id, " +
        "event_timestamp, payload, user_id, severity, ingested_at) " +
        "VALUES (nextval('event_id_seq'), ?, ?, ?, ?, ?::jsonb, ?, ?, ?)";

    /**
     * 3-5x faster than JPA batching for pure inserts.
     * No entity state management overhead.
     */
    public void writeBatch(List<EventDTO> events) {
        jdbcTemplate.batchUpdate(INSERT_SQL, new BatchPreparedStatementSetter() {
            @Override
            public void setValues(PreparedStatement ps, int i) throws SQLException {
                EventDTO e = events.get(i);
                ps.setString(1, e.getEventType());
                ps.setString(2, e.getSourceService());
                ps.setString(3, e.getCorrelationId());
                ps.setTimestamp(4, Timestamp.from(e.getEventTimestamp()));
                ps.setString(5, e.getPayload());
                ps.setString(6, e.getUserId());
                ps.setString(7, e.getSeverity());
                ps.setTimestamp(8, Timestamp.from(Instant.now()));
            }

            @Override
            public int getBatchSize() {
                return events.size();
            }
        });
    }
}
```

##### Option C: PostgreSQL COPY (fastest possible — 10x JDBC batch)

```java
@Repository
public class EventCopyWriter {

    private final DataSource dataSource;

    /**
     * Uses PostgreSQL COPY protocol — fastest bulk load mechanism.
     * 50,000+ rows/second on modest hardware.
     */
    public void writeBatch(List<EventDTO> events) throws SQLException {
        try (Connection conn = dataSource.getConnection()) {
            PGConnection pgConn = conn.unwrap(PGConnection.class);
            CopyManager copyManager = pgConn.getCopyAPI();

            String copySql = "COPY events (event_type, source_service, correlation_id, " +
                "event_timestamp, payload, user_id, severity, ingested_at) " +
                "FROM STDIN WITH (FORMAT csv)";

            StringBuilder csv = new StringBuilder();
            for (EventDTO e : events) {
                csv.append(escapeCsv(e.getEventType())).append(',')
                   .append(escapeCsv(e.getSourceService())).append(',')
                   .append(escapeCsv(e.getCorrelationId())).append(',')
                   .append(e.getEventTimestamp()).append(',')
                   .append(escapeCsv(e.getPayload())).append(',')
                   .append(escapeCsv(e.getUserId())).append(',')
                   .append(escapeCsv(e.getSeverity())).append(',')
                   .append(Instant.now()).append('\n');
            }

            copyManager.copyIn(copySql, new StringReader(csv.toString()));
        }
    }
}
```

#### Async Processing Pipeline

```java
@Service
public class EventIngestionService {

    private final BlockingQueue<EventDTO> buffer = new LinkedBlockingQueue<>(100_000);
    private final EventJdbcBatchWriter writer;
    private final MeterRegistry metrics;

    /**
     * Non-blocking event acceptance — returns immediately.
     * Events are buffered and flushed in batches.
     */
    public void ingest(EventDTO event) {
        boolean accepted = buffer.offer(event);
        if (!accepted) {
            // Queue full — apply backpressure or write to overflow (Kafka, file)
            metrics.counter("events.dropped").increment();
            throw new EventBufferFullException("Event buffer exhausted");
        }
        metrics.counter("events.accepted").increment();
    }

    @Scheduled(fixedDelay = 100) // Flush every 100ms
    public void flushBuffer() {
        List<EventDTO> batch = new ArrayList<>(500);
        buffer.drainTo(batch, 500); // Take up to 500 events

        if (!batch.isEmpty()) {
            try {
                writer.writeBatch(batch);
                metrics.counter("events.persisted").increment(batch.size());
            } catch (Exception e) {
                // Dead letter queue — don't lose events
                deadLetterQueue.addAll(batch);
                metrics.counter("events.failed").increment(batch.size());
            }
        }
    }
}
```

#### Connection Pool Sizing

```yaml
spring:
  datasource:
    hikari:
      # For write-heavy workload on 8-core machine:
      # Formula: connections = (cores * 2) + spindles
      # With SSD: connections ≈ cores * 2 = 16
      maximum-pool-size: 16
      minimum-idle: 8

      # Batch operations hold connections longer
      connection-timeout: 5000     # Fail fast if pool exhausted
      max-lifetime: 1800000        # 30min
      
      # Separate pool for reads (if using read replicas)
      # Configure via AbstractRoutingDataSource
```

**Separate pools for read vs write:**
```java
@Configuration
public class DataSourceRoutingConfig {

    @Bean
    @Primary
    public DataSource routingDataSource(
            @Qualifier("writeDataSource") DataSource write,
            @Qualifier("readDataSource") DataSource read) {

        ReadWriteRoutingDataSource routing = new ReadWriteRoutingDataSource();
        Map<Object, Object> targets = new HashMap<>();
        targets.put(DataSourceType.WRITE, write);
        targets.put(DataSourceType.READ, read);
        routing.setTargetDataSources(targets);
        routing.setDefaultTargetDataSource(write);
        return routing;
    }
}

public class ReadWriteRoutingDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        return TransactionSynchronizationManager.isCurrentTransactionReadOnly()
            ? DataSourceType.READ
            : DataSourceType.WRITE;
    }
}
```

#### Table Partitioning Strategy

```sql
-- PostgreSQL declarative partitioning by time
CREATE TABLE events (
    id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    source_service VARCHAR(100) NOT NULL,
    correlation_id VARCHAR(36),
    event_timestamp TIMESTAMPTZ NOT NULL,
    payload JSONB,
    user_id VARCHAR(100),
    severity VARCHAR(10),
    ingested_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (event_timestamp);

-- Monthly partitions
CREATE TABLE events_2024_01 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE events_2024_02 PARTITION OF events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... auto-created by cron job or pg_partman

-- Indexes are per-partition (local indexes)
CREATE INDEX idx_events_2024_01_type ON events_2024_01 (event_type);
CREATE INDEX idx_events_2024_01_source ON events_2024_01 (source_service);
```

**Auto-partition management:**
```java
@Component
public class PartitionManager {

    @Autowired private JdbcTemplate jdbc;

    @Scheduled(cron = "0 0 0 25 * *") // 25th of each month — create next month's partition
    public void createNextPartition() {
        YearMonth next = YearMonth.now().plusMonths(1);
        YearMonth afterNext = next.plusMonths(1);

        String partitionName = "events_" + next.format(DateTimeFormatter.ofPattern("yyyy_MM"));
        String sql = String.format(
            "CREATE TABLE IF NOT EXISTS %s PARTITION OF events " +
            "FOR VALUES FROM ('%s-01') TO ('%s-01')",
            partitionName, next, afterNext);

        jdbc.execute(sql);
        log.info("Created partition: {}", partitionName);
    }
}
```

#### When to Bypass JPA

```
┌──────────────────────────────────────────────────────────────────────────┐
│           WHEN TO USE JPA vs RAW JDBC vs COPY                            │
├─────────────────────┬──────────────┬──────────────┬──────────────────────┤
│ Operation           │ JPA          │ JDBC Batch   │ COPY / bulk          │
├─────────────────────┼──────────────┼──────────────┼──────────────────────┤
│ Single event CRUD   │ ✅ (simple)  │              │                      │
│ < 100 inserts/sec   │ ✅           │              │                      │
│ 100-1000 inserts/s  │              │ ✅           │                      │
│ > 1000 inserts/sec  │              │              │ ✅                   │
│ Complex queries     │ ✅ (JPQL)    │              │                      │
│ Aggregation reports │              │ ✅ (native)  │                      │
│ Dashboard reads     │ ✅ (DTO proj)│              │                      │
│ Full table scan     │              │ ✅ (stream)  │                      │
│ Data migration      │              │              │ ✅                   │
└─────────────────────┴──────────────┴──────────────┴──────────────────────┘
```

#### Read Optimization

```java
// For dashboard queries — use read replica + native queries
@Repository
public class EventAnalyticsRepository {

    @PersistenceContext
    private EntityManager em;

    @Transactional(readOnly = true) // Routes to read replica
    public List<EventCountByType> getHourlyEventCounts(Instant from, Instant to) {
        return em.createNativeQuery("""
            SELECT date_trunc('hour', event_timestamp) as hour,
                   event_type,
                   COUNT(*) as count
            FROM events
            WHERE event_timestamp BETWEEN :from AND :to
            GROUP BY 1, 2
            ORDER BY 1 DESC
            """, "EventCountByTypeMapping")
            .setParameter("from", from)
            .setParameter("to", to)
            .setHint("org.hibernate.readOnly", true)
            .setHint("org.hibernate.fetchSize", 1000)
            .getResultList();
    }
}
```

#### Archival Strategy

```java
@Service
public class EventArchivalService {

    @Autowired private JdbcTemplate jdbc;
    @Autowired private S3Client s3;

    /**
     * Archive partitions older than 30 days to S3.
     * Runs nightly.
     */
    @Scheduled(cron = "0 0 2 * * *") // 2 AM daily
    public void archiveOldPartitions() {
        YearMonth archiveMonth = YearMonth.now().minusMonths(2);
        String partitionName = "events_" + archiveMonth.format(
            DateTimeFormatter.ofPattern("yyyy_MM"));

        // 1. Export to Parquet/CSV on local disk
        String exportPath = "/tmp/archive/" + partitionName + ".parquet";
        exportToParquet(partitionName, exportPath);

        // 2. Upload to S3
        s3.putObject(PutObjectRequest.builder()
            .bucket("event-archive")
            .key("events/" + archiveMonth.getYear() + "/" + partitionName + ".parquet")
            .build(),
            Path.of(exportPath));

        // 3. Detach partition (fast, no data deleted yet)
        jdbc.execute("ALTER TABLE events DETACH PARTITION " + partitionName);

        // 4. Drop after confirming S3 upload
        jdbc.execute("DROP TABLE " + partitionName);

        log.info("Archived and dropped partition: {}", partitionName);
    }
}
```

#### Complete Application Configuration

```yaml
spring:
  datasource:
    url: jdbc:postgresql://write-db:5432/events_db
    hikari:
      maximum-pool-size: 16
      minimum-idle: 8
      connection-timeout: 5000
  jpa:
    open-in-view: false  # CRITICAL for performance
    properties:
      hibernate:
        jdbc.batch_size: 500
        order_inserts: true
        generate_statistics: true
        connection.provider_disables_autocommit: true  # Saves a round-trip per tx

# Custom properties
event-ingestion:
  buffer-size: 100000
  flush-interval-ms: 100
  batch-size: 500
  dead-letter-retry-interval-ms: 60000
```

#### Performance Benchmarks (Expected)

```
┌────────────────────────┬───────────────┬─────────────────────────────────┐
│ Method                 │ Events/sec    │ Notes                           │
├────────────────────────┼───────────────┼─────────────────────────────────┤
│ JPA single persist     │ ~500          │ Unacceptable for this use case  │
│ JPA batch (500)        │ ~5,000        │ OK for moderate load            │
│ JDBC batch (500)       │ ~15,000       │ Good for most scenarios         │
│ COPY protocol          │ ~50,000+      │ Maximum throughput              │
│ With async buffering   │ ~100,000+     │ App-perceived (non-blocking)    │
└────────────────────────┴───────────────┴─────────────────────────────────┘
```

#### Trade-offs Summary

| Decision | Trade-off |
|----------|-----------|
| **Bypass JPA for writes** | Lose entity lifecycle hooks, dirty checking. Gain 10x throughput. |
| **Keep JPA for reads** | Benefit from type safety, projections, Spring Data query methods. |
| **In-memory buffer** | Risk: event loss on crash. Mitigation: WAL/Kafka for durability. |
| **Time-based partitioning** | Queries without timestamp filter scan all partitions. Always include time range. |
| **Denormalized events** | More storage, but no joins needed. Events are immutable append-only. |
| **SEQUENCE with large allocationSize** | Gaps in IDs on restart (acceptable). But avoids per-insert DB call. |
| **Separate read/write pools** | Operational complexity. But writes don't starve reads. |

#### When This Design Isn't Enough

If you need > 100K events/sec sustained, consider:
- **Kafka + ClickHouse/TimescaleDB** instead of PostgreSQL
- **Apache Flink** for stream processing before persistence
- **Elasticsearch** for search over events
- **Event sourcing** patterns with eventual consistency

JPA/Hibernate is the wrong tool for ultra-high-volume event stores. Use it for your domain model; use specialized systems for analytics/logging at extreme scale.
